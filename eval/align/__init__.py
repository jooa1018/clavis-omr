"""Exact rational, lexicographic dynamic programming (ADR-012)."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from fractions import Fraction
from typing import Protocol

from eval.policy import limit
from eval.projection.model import EvaluationUnsupported, Event, Measure

type Cost = tuple[int, int, Fraction]


class Timed(Protocol):
    @property
    def onset(self) -> Fraction: ...


@dataclass
class Budget:
    remaining: int = field(default_factory=lambda: limit("maxAlignmentCells"))

    def use(self, cells: int) -> None:
        self.remaining -= cells
        if self.remaining < 0:
            raise EvaluationUnsupported("alignment-cell-budget")


@dataclass(frozen=True)
class Pair[T]:
    reference: T | None
    prediction: T | None
    errors: tuple[str, ...]
    operations: int


@dataclass(frozen=True)
class AlignedMeasure:
    reference: tuple[Measure, ...]
    prediction: tuple[Measure, ...]
    operation: str
    events: tuple[Pair[Event], ...]
    cost: Cost


def add(left: Cost, right: Cost) -> Cost:
    return left[0] + right[0], left[1] + right[1], left[2] + right[2]


def event_errors(a: Event, b: Event) -> tuple[str, ...]:
    return tuple(
        name
        for name in ("kind", "pitch", "duration", "tie_start", "tie_stop")
        if getattr(a, name) != getattr(b, name)
    )


def align_items[T: Timed](
    reference: Sequence[T],
    prediction: Sequence[T],
    fields: Callable[[T, T], tuple[str, ...]],
    budget: Budget,
    *,
    charge_onset: bool = False,
) -> tuple[Cost, tuple[Pair[T], ...]]:
    """Stable precedence: match, reference-only (delete), prediction-only (insert)."""
    budget.use((len(reference) + 1) * (len(prediction) + 1))
    costs: dict[tuple[int, int], Cost] = {(0, 0): (0, 0, Fraction(0))}
    back: dict[tuple[int, int], tuple[int, int, Pair[T]]] = {}
    for i in range(len(reference) + 1):
        for j in range(len(prediction) + 1):
            if i == j == 0:
                continue
            candidates: list[tuple[Cost, tuple[int, int, Pair[T]]]] = []
            if i and j:
                a, b = reference[i - 1], prediction[j - 1]
                errors = fields(a, b)
                delta = abs(a.onset - b.onset)
                operations = int(bool(errors) or (charge_onset and bool(delta)))
                all_errors = errors + (("onset",) if delta else ())
                pair = Pair(a, b, all_errors, operations)
                candidates.append(
                    (
                        add(costs[i - 1, j - 1], (operations, len(errors), delta)),
                        (i - 1, j - 1, pair),
                    )
                )
            if i:
                candidates.append(
                    (
                        add(costs[i - 1, j], (1, 0, Fraction(0))),
                        (i - 1, j, Pair(reference[i - 1], None, ("missing",), 1)),
                    )
                )
            if j:
                candidates.append(
                    (
                        add(costs[i, j - 1], (1, 0, Fraction(0))),
                        (i, j - 1, Pair(None, prediction[j - 1], ("extra",), 1)),
                    )
                )
            costs[i, j], back[i, j] = min(candidates, key=lambda candidate: candidate[0])
    i, j = len(reference), len(prediction)
    pairs = []
    while i or j:
        i, j, pair = back[i, j]
        pairs.append(pair)
    return costs[len(reference), len(prediction)], tuple(reversed(pairs))


def joined_events(measures: Sequence[Measure]) -> tuple[Event, ...]:
    offset = Fraction(0)
    events: list[Event] = []
    for measure in measures:
        events.extend(replace(e, onset=e.onset + offset) for e in measure.events)
        offset += measure.length
    return tuple(events)


def subtract(a: Cost, b: Cost) -> Cost:
    return a[0] - b[0], a[1] - b[1], a[2] - b[2]


def assignment(costs: Sequence[Sequence[Cost]]) -> list[int]:
    """Hungarian shortest augmenting paths over ordered lexicographic costs.

    Rows/columns are traversed in document order; equal reduced costs retain
    their first predecessor. Tuple addition/subtraction preserve the objective.
    """
    size = len(costs)
    zero: Cost = (0, 0, Fraction(0))
    u, v = [zero] * (size + 1), [zero] * (size + 1)
    matched, previous = [0] * (size + 1), [0] * (size + 1)
    for row in range(1, size + 1):
        matched[0], column = row, 0
        best: list[Cost | None] = [None] * (size + 1)
        used = [False] * (size + 1)
        while True:
            used[column] = True
            active, next_column = matched[column], 0
            delta: Cost | None = None
            for candidate in range(1, size + 1):
                if used[candidate]:
                    continue
                reduced = subtract(
                    subtract(costs[active - 1][candidate - 1], u[active]), v[candidate]
                )
                old = best[candidate]
                if old is None or reduced < old:
                    best[candidate], previous[candidate] = reduced, column
                current = best[candidate]
                assert current is not None
                if delta is None or current < delta:
                    delta, next_column = current, candidate
            assert delta is not None
            for candidate in range(size + 1):
                if used[candidate]:
                    u[matched[candidate]] = add(u[matched[candidate]], delta)
                    v[candidate] = subtract(v[candidate], delta)
                elif best[candidate] is not None:
                    current = best[candidate]
                    assert current is not None
                    best[candidate] = subtract(current, delta)
            column = next_column
            if matched[column] == 0:
                break
        while column:
            prior = previous[column]
            matched[column] = matched[prior]
            column = prior
    result = [0] * size
    for column in range(1, size + 1):
        result[matched[column] - 1] = column - 1
    return result


def align_voices(
    a: Sequence[Event], b: Sequence[Event], budget: Budget
) -> tuple[Cost, tuple[Pair[Event], ...]]:
    voices_a, voices_b = (
        list(dict.fromkeys(e.voice for e in a)),
        list(dict.fromkeys(e.voice for e in b)),
    )
    if max(len(voices_a), len(voices_b)) > limit("maxVoices"):
        raise EvaluationUnsupported("voice-limit")
    # Dummy rows and columns allow entire unmatched voices on either side.
    left = [tuple(e for e in a if e.voice == voice) for voice in voices_a] + [()] * len(voices_b)
    right = [tuple(e for e in b if e.voice == voice) for voice in voices_b] + [()] * len(voices_a)
    if not left:
        return (0, 0, Fraction(0)), ()
    cells = [[align_items(x, y, event_errors, budget) for y in right] for x in left]
    selected = assignment([[c[0] for c in row] for row in cells])
    cost: Cost = (0, 0, Fraction(0))
    pairs: list[Pair[Event]] = []
    for i, j in enumerate(selected):
        cost = add(cost, cells[i][j][0])
        pairs.extend(cells[i][j][1])
    return cost, tuple(pairs)


def align_measures(
    reference: Sequence[Measure], prediction: Sequence[Measure], budget: Budget
) -> tuple[AlignedMeasure, ...]:
    """Match/split/merge/delete/insert in the approved order, with event DP costs."""
    budget.use((len(reference) + 1) * (len(prediction) + 1))
    costs: dict[tuple[int, int], Cost] = {(0, 0): (0, 0, Fraction(0))}
    back: dict[tuple[int, int], tuple[int, int, AlignedMeasure]] = {}
    for i in range(len(reference) + 1):
        for j in range(len(prediction) + 1):
            if i == j == 0:
                continue
            candidates = []
            for di, dj, name in (
                (1, 1, "match"),
                (1, 2, "split"),
                (2, 1, "merge"),
                (1, 0, "delete"),
                (0, 1, "insert"),
            ):
                if i < di or j < dj:
                    continue
                a, b = tuple(reference[i - di : i]), tuple(prediction[j - dj : j])
                cost, pairs = align_voices(joined_events(a), joined_events(b), budget)
                if name != "match":
                    cost = add(cost, (1, 0, Fraction(0)))
                group = AlignedMeasure(a, b, name, pairs, cost)
                candidates.append((add(costs[i - di, j - dj], cost), (i - di, j - dj, group)))
            costs[i, j], back[i, j] = min(candidates, key=lambda candidate: candidate[0])
    i, j = len(reference), len(prediction)
    result = []
    while i or j:
        i, j, group = back[i, j]
        result.append(group)
    return tuple(reversed(result))
