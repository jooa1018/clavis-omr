"""Unique printed order of columns already encoded by chord/join.

This function reorders complete columns, never infers which marks share a
musical onset. Callers supply printed spans from render truth or symbol boxes.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from math import isfinite

from ..tokens import LSTLItem
from .automaton import LSTLError, validate_sequence


@dataclass(frozen=True)
class PrintedItem:
    item: LSTLItem
    span_u: tuple[float, float]


def _precedes(a: LSTLItem, b: LSTLItem, initial: bool) -> bool:
    if initial:
        order = {"clef": 0, "key": 1, "time": 2}
        if a.type in order and b.type in order:
            return order[a.type] < order[b.type]
        if a.type in order and b.type == "bar" and b.style == "repeatStart":
            return True
    else:
        if a.type == "clef" and b.type == "bar":
            return True
        if a.type == "bar" and a.style != "repeatStart" and b.type in ("key", "time"):
            return True
        if a.type in ("key", "time") and b.type == "bar" and b.style == "repeatStart":
            return True
        if a.type == "key" and b.type == "time":
            return True
    return a.type == "bar" and b.type == "ending"


def normalize(items: Sequence[PrintedItem]) -> list[PrintedItem]:
    """Sort encoded columns; ambiguity/cycles fail closed, without tie-breakers."""
    columns: list[list[PrintedItem]] = []
    for entry in items:
        left, right = entry.span_u
        if not isfinite(left) or not isfinite(right) or left > right:
            raise LSTLError("INVALID_SPAN")
        continuation = getattr(entry.item, "join", None) == 1 or (
            getattr(entry.item, "chord", None) == 1
        )
        if continuation:
            if not columns:
                raise LSTLError("ORPHAN_COLUMN_CONTINUATION")
            columns[-1].append(entry)
        else:
            columns.append([entry])
    # Validate encoded membership before sorting. No inferred voice/chord labels.
    for column in columns:
        if column[0].item.type != "ending" and not getattr(column[0].item, "courtesy", None):
            validate_sequence(entry.item for entry in column)
    spans = [(min(e.span_u[0] for e in col), max(e.span_u[1] for e in col)) for col in columns]
    timed = [
        spans[i][0]
        for i, col in enumerate(columns)
        if col[0].item.type in ("note", "rest", "mrest")
    ]
    edges: list[set[int]] = [set() for _ in columns]
    for i, a in enumerate(columns):
        for j, b in enumerate(columns):
            if i == j:
                continue
            if spans[i][1] < spans[j][0]:
                edges[i].add(j)
            elif spans[j][1] >= spans[i][0]:
                initial = not timed or max(spans[i][1], spans[j][1]) < min(timed)
                if _precedes(a[0].item, b[0].item, initial):
                    edges[i].add(j)
                # "Immediately after that barline": when a regular boundary
                # shares its span with ending/key/time, ending precedes changes.
                if a[0].item.type == "ending" and b[0].item.type in ("key", "time"):
                    for k, column in enumerate(columns):
                        bar = column[0].item
                        if bar.type != "bar" or bar.style == "repeatStart":
                            continue
                        if all(
                            spans[k][0] <= spans[target][1] and spans[target][0] <= spans[k][1]
                            for target in (i, j)
                        ):
                            edges[i].add(j)
    pending = set(range(len(columns)))
    result: list[PrintedItem] = []
    while pending:
        ready = [i for i in pending if not any(i in edges[j] for j in pending)]
        if len(ready) != 1:
            raise LSTLError("AMBIGUOUS_COLUMN_ORDER")
        index = ready[0]
        result.extend(columns[index])
        pending.remove(index)
    validate_sequence(entry.item for entry in result)
    return result
