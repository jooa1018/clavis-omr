"""Evidence-only draft reader; production requires W1 sequence validation."""

from dataclasses import dataclass
from itertools import product
from math import log

from clavis.contracts.common import Producer, top_k_value_key
from clavis.contracts.symbols import (
    AttrValue,
    Hypothesis,
    LatticeItem,
    StaffLattice,
    Symbol,
    SymbolGraph,
)
from clavis.symbols.columns import mark_columns, normalize_hypothesis

BP = 10000  # CONTRACTS 1: basis points.
MICRO = 1000000  # CONTRACTS 3.4: log-probability microunits.
MAX_HYPOTHESES = 8  # CONTRACTS 3.4.
BEAM_DURATIONS = ("quarter", "eighth", "16th", "32nd", "64th")


@dataclass(frozen=True)
class ReadingDraft:
    """A wire-valid proposal is not a grammar-validated production lattice."""

    lattice: StaffLattice
    unresolved_symbol_ids: tuple[str, ...]

    def finalize(self) -> StaffLattice:
        """Use the W1 normalizer, canonical parser and sequence automaton."""
        if self.unresolved_symbol_ids:
            raise ValueError("Unresolved visual evidence requires review before finalization")
        hypotheses = [normalize_hypothesis(h) for h in self.lattice.hypotheses]
        return StaffLattice.model_validate({**self.lattice.model_dump(), "hypotheses": hypotheses})


def _rank(values: list[tuple[AttrValue, int]]) -> list[tuple[AttrValue, int]]:
    return sorted(values, key=lambda pair: (-pair[1], top_k_value_key(pair[0])))


def _durations(shape: str, stem: Symbol | None) -> list[tuple[AttrValue, int]]:
    """SYM-READ-001: head shape and observed beams/flags determine duration."""
    if shape == "noteheadWhole":
        return [("whole", BP)]
    if stem is None:
        return []
    if shape == "noteheadHollow":
        return [("half", BP)]
    if stem.attrs is None:
        return []
    # A missing distribution is unknown, never an asserted zero count.
    beams = stem.attrs.beam_count_top_k
    flags = stem.attrs.flag_count_top_k
    if beams is None or flags is None:
        return []
    masses: dict[str, float] = {}
    for (beam, pb), (flag, pf) in product(beams, flags):
        count = max(beam, flag)
        if count >= len(BEAM_DURATIONS):
            return []
        dur = BEAM_DURATIONS[count]
        masses[dur] = masses.get(dur, 0) + pb * pf / BP
    # Do not silently truncate a distribution wider than the v0.1 top-k limit.
    if len(masses) > 3:
        return []
    return _rank([(dur, int(p)) for dur, p in masses.items() if p >= 1])


def _choices(head: Symbol, graph: SymbolGraph) -> list[tuple[float, LatticeItem]]:
    attrs = head.attrs
    if head.pos_top_k is None or attrs is None:
        return []
    if attrs.dots_top_k is None or attrs.voice_top_k is None:
        return []
    by_id = {s.symbol_id: s for s in graph.symbols}
    links: list[tuple[Symbol | None, int]] = [
        (by_id[r.from_id], r.prob_bp * dict(by_id[r.from_id].class_top_k).get("stem", 0) // BP)
        for r in graph.relations
        if r.kind == "stemOf"
        and r.to == head.symbol_id
        and dict(by_id[r.from_id].class_top_k).get("stem", 0) > 0
    ]
    alternatives: list[tuple[float, LatticeItem]] = []
    branches = [
        (shape, class_bp, stem, link_bp)
        for shape, class_bp in head.class_top_k
        if shape in ("noteheadFilled", "noteheadHollow", "noteheadWhole")
        for stem, link_bp in ([(None, BP)] if shape == "noteheadWhole" else links)
    ]
    for shape, class_bp, stem, link_bp in branches:
        durations = _durations(shape, stem)
        if not durations:
            continue
        evidence = [head] if stem is None else [head, stem]
        targets = {s.symbol_id for s in evidence}
        evidence.extend(
            by_id[r.from_id]
            for r in graph.relations
            if r.kind in ("beamOf", "flagOf", "dotOf") and r.to in targets
        )
        distributions: dict[str, list[tuple[AttrValue, int]]] = {
            "dur": durations,
            "pos": [(v, p) for v, p in head.pos_top_k],
            "dots": [(v, p) for v, p in attrs.dots_top_k],
            "v": [(v, p) for v, p in attrs.voice_top_k],
        }
        # Attributes already live in attrTopK. Spending N-best slots on their
        # Cartesian product would crowd out lower-probability stem connections.
        combination = [values[0] for values in distributions.values()]
        probabilities = [class_bp, link_bp]
        probabilities.extend(p for _, p in combination)
        if not all(probabilities):
            continue
        score = sum(log(p / BP) for p in probabilities)
        token = dict(zip(distributions, (v for v, _ in combination), strict=True))
        item = LatticeItem.model_validate(
            {
                "item": {"type": "note", "head": "normal", **token},
                "attrTopK": distributions,
                "spanU": [
                    min(s.box_strip[0] for s in evidence),
                    max(s.box_strip[0] + s.box_strip[2] for s in evidence),
                ],
                "itemProbBp": min(probabilities),
                "symbolIds": sorted({s.symbol_id for s in evidence}),
            }
        )
        alternatives.append((score, item))
    return alternatives


def draft_reading(
    graph: SymbolGraph,
    producer: Producer,
    *,
    enabled: bool = True,
    durations_enabled: bool = True,
    chords_enabled: bool = True,
    joins_enabled: bool = True,
) -> ReadingDraft:
    """SYM-READ-002: enumerate independent local choices, retaining attribute top-k.

    This implements the narrow notehead/stem development path, not clefs, bars,
    or ties. Selected stem chords and uncertain voice columns are normalized
    through W1's shared API. Unconsumed evidence is
    exposed and prevents production finalization. Probabilities are uncalibrated.
    """
    paths: list[tuple[float, list[LatticeItem]]] = [(0.0, [])]
    if enabled and durations_enabled:
        for head in sorted(graph.symbols, key=lambda s: (*s.center_strip, s.symbol_id)):
            if not any(
                c in ("noteheadFilled", "noteheadHollow", "noteheadWhole")
                for c, _ in head.class_top_k
            ):
                continue
            choices = _choices(head, graph)
            if not choices:
                continue
            expanded = [(p + q, items + [item]) for p, items in paths for q, item in choices]
            expanded.sort(
                key=lambda path: (
                    -round(path[0] * MICRO),
                    tuple(i.model_dump_json(by_alias=True) for i in path[1]),
                )
            )
            paths = expanded[:MAX_HYPOTHESES]
    validated = []
    for score, items in paths:
        try:
            marked, uncertain = mark_columns(
                items, graph, chords_enabled=chords_enabled, joins_enabled=joins_enabled
            )
            hypothesis = normalize_hypothesis(
                Hypothesis(
                    rank=0,
                    log_prob_micro=round((score + uncertain * log(1 / 2)) * MICRO),
                    items=marked,
                )
            )
        except ValueError:
            # Invalid geometry/grammar never becomes an invented musical item.
            continue
        validated.append(hypothesis)
    validated.sort(key=lambda h: (-h.log_prob_micro, h.model_dump_json(by_alias=True)))
    for rank, hypothesis in enumerate(validated):
        hypothesis.rank = rank
    lattice = StaffLattice.model_validate(
        {
            "schema": "clavis-ir-0.1.1",
            "id": graph.id,
            "stripId": graph.strip_id,
            "producer": producer,
            "hypotheses": validated,
        }
    )
    consumed = {sid for h in validated for item in h.items for sid in item.symbol_ids}
    unresolved = {s.symbol_id for s in graph.symbols} - consumed
    unresolved.update(s.symbol_id for s in graph.rejected_candidates)
    # Relations outside the supported stem path must also remain reviewable.
    for relation in graph.relations:
        if relation.kind not in ("stemOf", "beamOf", "flagOf", "dotOf"):
            unresolved.update((relation.from_id, relation.to))
    return ReadingDraft(lattice, tuple(sorted(unresolved)))
