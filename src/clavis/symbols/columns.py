"""W6 column evidence; W1 owns canonical ordering and sequence validation."""

from clavis.contracts.lstl import LSTLError, PrintedItem, normalize, parse, serialize
from clavis.contracts.symbols import Hypothesis, LatticeItem, SymbolGraph
from clavis.contracts.tokens import NoteItem

BP = 10000  # CONTRACTS 1: basis points.


def normalize_hypothesis(hypothesis: Hypothesis) -> Hypothesis:
    """Validate printed order and the canonical text with the shared APIs."""
    printed = [PrintedItem(entry.item, entry.span_u) for entry in hypothesis.items]
    source = {id(entry): item for entry, item in zip(printed, hypothesis.items, strict=True)}
    ordered = normalize(printed)
    tokens = [entry.item for entry in ordered]
    if parse(serialize(tokens)) != tokens:
        raise ValueError("Canonical LSTL roundtrip changed tokens")
    return Hypothesis(
        rank=hypothesis.rank,
        log_prob_micro=hypothesis.log_prob_micro,
        items=[source[id(entry)] for entry in ordered],
    )


def mark_columns(
    items: list[LatticeItem],
    graph: SymbolGraph,
    *,
    chords_enabled: bool,
    joins_enabled: bool,
) -> tuple[list[LatticeItem], int]:
    """SYM-READ-003/004: selected shared stems and overlapping head boxes.

    Overlap alone cannot establish a musical onset. Keep both join values with
    equal provisional mass; choose the joined reading for canonical validation.
    Ambiguous overlap chains or multiple stems in one voice fail closed.
    """
    by_id = {symbol.symbol_id: symbol for symbol in graph.symbols}
    stems, spans = [], []
    notes: list[NoteItem] = []
    for entry in items:
        heads = [
            by_id[sid]
            for sid in entry.symbol_ids
            if any(shape.startswith("notehead") for shape, _ in by_id[sid].class_top_k)
        ]
        if len(heads) != 1 or not isinstance(entry.item, NoteItem):
            raise LSTLError("UNSUPPORTED_COLUMN_EVIDENCE")
        head = heads[0]
        notes.append(entry.item)
        stems.append(
            frozenset(
                relation.from_id
                for relation in graph.relations
                if relation.kind == "stemOf"
                and relation.to == head.symbol_id
                and relation.from_id in entry.symbol_ids
            )
        )
        spans.append((head.box_strip[0], head.box_strip[0] + head.box_strip[2]))

    def overlap(a: int, b: int) -> bool:
        return max(spans[a][0], spans[b][0]) < min(spans[a][1], spans[b][1])

    def linked(a: int, b: int) -> bool:
        return bool(chords_enabled and stems[a] & stems[b]) or (joins_enabled and overlap(a, b))

    pending = set(range(len(items)))
    result: list[LatticeItem] = []
    uncertain = 0
    while pending:
        group = {min(pending)}
        while additions := {i for i in pending - group if any(linked(i, j) for j in group)}:
            group.update(additions)
        pending -= group
        # Connected overlap is insufficient: each pair needs direct evidence.
        if any(not linked(a, b) for a in group for b in group if a != b):
            raise LSTLError("AMBIGUOUS_COLUMN_EVIDENCE")
        if any(stems[a] & stems[b] and notes[a].v != notes[b].v for a in group for b in group):
            raise LSTLError("CONFLICTING_STEM_VOICE")
        ordered = sorted(group, key=lambda i: (notes[i].v, notes[i].pos))
        for offset, index in enumerate(ordered):
            entry = items[index]
            data = entry.model_dump(by_alias=True, exclude_none=True)
            if offset:
                previous = ordered[offset - 1]
                same_stem = bool(stems[index] & stems[previous])
                if same_stem:
                    if not chords_enabled or notes[index].v != notes[previous].v:
                        raise LSTLError("CONFLICTING_STEM_VOICE")
                    if notes[index].pos == notes[previous].pos:
                        raise LSTLError("AMBIGUOUS_HEAD_ORDER")
                    data["item"]["chord"] = 1
                else:
                    if not joins_enabled or notes[index].v <= notes[previous].v:
                        raise LSTLError("AMBIGUOUS_VOICE_COLUMN")
                    data["item"]["join"] = 1
                    # Symmetric ignorance prior, not a fitted confidence.
                    data["attrTopK"]["join"] = [(0, BP // 2), (1, BP // 2)]
                    data["itemProbBp"] = min(entry.item_prob_bp, BP // 2)
                    uncertain += 1
            result.append(LatticeItem.model_validate(data))
    return result, uncertain
