"""CTC prefix beam with CCR-0002 prefix constraints, without a language model.

Prefix recurrence: https://arxiv.org/abs/1408.2873. Export class IDs remain
distinct even when spellings coincide. Returned mass is a pruned, quantized
CTC mass, NOT calibrated correctness or a renormalized top-k distribution.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from math import exp, floor, log, log1p
from unicodedata import normalize

from .chord import ChordGrammar, ChordState
from .ctc import BASIS_POINTS, CtcLimits, greedy_observation

NEG_INF = float("-inf")


def _add(a: float, b: float) -> float:
    if a == NEG_INF:
        return b
    if b == NEG_INF:
        return a
    hi, lo = max(a, b), min(a, b)
    return hi + log1p(exp(lo - hi))


@dataclass(frozen=True)
class BeamLimits:
    width: int
    top_k: int
    max_transitions: int

    def __post_init__(self) -> None:
        if any(type(x) is not int or x <= 0 for x in vars(self).values()):
            raise ValueError("beam limits must be positive integers")


@dataclass(frozen=True)
class ChordCandidate:
    text: str
    normalized: str
    mass_bp: int


def chord_beam(
    probabilities: Sequence[Sequence[float]],
    alphabet: Sequence[str],
    *,
    blank_index: int,
    grammar: ChordGrammar,
    ctc_limits: CtcLimits,
    limits: BeamLimits,
    enabled: bool,
) -> tuple[ChordCandidate, ...]:
    if not enabled or not grammar.enabled:
        return ()
    # Reuse the established tensor/export boundary, including resource validation.
    greedy_observation(
        probabilities,
        alphabet,
        blank_index=blank_index,
        limits=ctc_limits,
        enabled=True,
        preserve_export_alphabet=True,
    )
    beams: dict[tuple[int, ...], tuple[float, float]] = {(): (0.0, NEG_INF)}
    states: dict[tuple[int, ...], ChordState] = {(): grammar.start()}
    transitions = 0
    for row in probabilities:
        counts = [round(p * BASIS_POINTS) for p in row]
        total = sum(counts)
        if not total:
            raise ValueError("CTC row has no mass after quantization")
        active = [(i, log(n / total)) for i, n in enumerate(counts) if n]
        updated: dict[tuple[int, ...], tuple[float, float]] = {}
        next_states: dict[tuple[int, ...], ChordState] = {}

        def put(
            prefix: tuple[int, ...],
            mass: float,
            blank: bool,
            state: ChordState,
            updated: dict[tuple[int, ...], tuple[float, float]] = updated,
            next_states: dict[tuple[int, ...], ChordState] = next_states,
        ) -> None:
            if mass == NEG_INF:
                return
            pb, pn = updated.get(prefix, (NEG_INF, NEG_INF))
            updated[prefix] = (_add(pb, mass), pn) if blank else (pb, _add(pn, mass))
            next_states[prefix] = state

        for prefix, (pb, pn) in beams.items():
            state = states[prefix]
            for cls, lp in active:
                transitions += 1
                if transitions > limits.max_transitions:
                    raise ValueError("CTC beam transition budget exceeded")
                if cls == blank_index:
                    put(prefix, _add(pb, pn) + lp, True, state)
                    continue
                repeat = bool(prefix and prefix[-1] == cls)
                if repeat:
                    put(prefix, pn + lp, False, state)
                mass = (pb if repeat else _add(pb, pn)) + lp
                if mass == NEG_INF:
                    continue
                advanced = grammar.advance(state, alphabet[cls])
                if advanced.viable:
                    put(prefix + (cls,), mass, False, advanced)
        # CONTRACTS 11 quantized score tie, then deterministic class ID sequence.
        ordered = sorted(updated, key=lambda p: (-round(_add(*updated[p]) * BASIS_POINTS), p))
        beams = {p: updated[p] for p in ordered[: limits.width]}
        states = {p: next_states[p] for p in beams}
    grouped: dict[str, tuple[float, float, str]] = {}
    for prefix, masses in beams.items():
        if not states[prefix].accepting:
            continue
        observed = normalize("NFC", "".join(alphabet[i] for i in prefix))
        parsed = grammar.parse(observed)
        if parsed is None:
            continue
        mass = _add(*masses)
        old = grouped.get(parsed.normalized)
        if old is None:
            grouped[parsed.normalized] = (mass, mass, observed)
        else:
            best = min(
                (old[1], old[2]),
                (mass, observed),
                key=lambda x: (-round(x[0] * BASIS_POINTS), x[1]),
            )
            grouped[parsed.normalized] = (_add(old[0], mass), *best)
    result = [
        ChordCandidate(text, normalized, min(BASIS_POINTS, floor(exp(mass) * BASIS_POINTS)))
        for normalized, (mass, _, text) in grouped.items()
    ]
    return tuple(sorted(result, key=lambda c: (-c.mass_bp, c.normalized, c.text))[: limits.top_k])
