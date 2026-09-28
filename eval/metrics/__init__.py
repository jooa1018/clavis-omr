"""First-PR object correction and exactness metrics, EVALUATION v1.1."""

from collections.abc import Callable, Sequence
from dataclasses import asdict, replace
from fractions import Fraction
from typing import Any

from eval.align import Budget, Pair, align_items, align_measures
from eval.projection.model import Attribute, Event, Harmony, Measure, Score


def rate(numerator: int, denominator: int, scale: int = 1) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "value": numerator / denominator * scale if denominator else None,
    }


def joined(measures: Sequence[Measure], name: str) -> list[Any]:
    offset = Fraction(0)
    result: list[Any] = []
    for measure in measures:
        result.extend(replace(item, onset=item.onset + offset) for item in getattr(measure, name))
        offset += measure.length
    return result


def value_errors(a: Harmony | Attribute, b: Harmony | Attribute) -> tuple[str, ...]:
    return ("value",) if a.value != b.value else ()


def attribute_pairs(
    reference: Sequence[Measure], prediction: Sequence[Measure], name: str
) -> tuple[list[Pair[Attribute]], set[str]]:
    a_changes = [a for a in joined(reference, "changes") if a.name == name]
    b_changes = [a for a in joined(prediction, "changes") if a.name == name]

    def active(measures: Sequence[Measure], onset: Fraction) -> Attribute | None:
        offset = Fraction(0)
        result = None
        for m in measures:
            if offset > onset:
                break
            value = dict(m.state).get(name)
            if value is not None:
                result = Attribute(f"{m.ref}/state/{name}", name, onset, value)
            offset += m.length
        return result

    pairs = []
    for onset in sorted({a.onset for a in (*a_changes, *b_changes)}):
        a = next((a for a in a_changes if a.onset == onset), None) or active(reference, onset)
        b = next((b for b in b_changes if b.onset == onset), None) or active(prediction, onset)
        errors = ("extra",) if a is None else ("missing",) if b is None else value_errors(a, b)
        pairs.append(Pair(a, b, errors, int(bool(errors))))
    return pairs, {a.ref for a in a_changes}


def lyric_pairs(pair: Pair[Event]) -> list[dict[str, Any]]:
    a = (
        {v: (text, syllabic) for v, text, syllabic in pair.reference.lyrics}
        if pair.reference
        else {}
    )
    b = (
        {v: (text, syllabic) for v, text, syllabic in pair.prediction.lyrics}
        if pair.prediction
        else {}
    )
    return [
        {
            "verse": v,
            "reference": a.get(v),
            "prediction": b.get(v),
            "errors": [] if a.get(v) == b.get(v) else ["lyric"],
            "operations": int(a.get(v) != b.get(v)),
        }
        for v in sorted(a.keys() | b.keys())
    ]


def measure(reference: Score, prediction: Score) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return metrics and complete alignment traces for a single score/page pair."""
    budget = Budget()
    groups = align_measures(reference.measures, prediction.measures, budget)
    event_pairs = [p for group in groups for p in group.events]
    metrics: dict[str, Any] = {}

    def exact(
        name: str,
        eligible: Callable[[Event, Event | None], bool],
        same: Callable[[Event, Event], bool],
    ) -> None:
        selected = [
            (p.reference, p.prediction)
            for p in event_pairs
            if p.reference is not None and eligible(p.reference, p.prediction)
        ]
        metrics[name] = rate(sum(b is not None and same(a, b) for a, b in selected), len(selected))

    exact(
        "pitchExactRate",
        lambda a, b: a.kind == "note" and not a.grace,
        lambda a, b: b.kind == "note" and not b.grace and a.pitch == b.pitch,
    )
    exact(
        "durationExactRate",
        lambda a, b: not a.grace,
        lambda a, b: not b.grace and a.duration == b.duration,
    )
    exact("restExactRate", lambda a, b: a.kind == "rest", lambda a, b: b.kind == "rest")
    exact(
        "tieExactRate",
        lambda a, b: (
            (a.kind == "note" and (a.tie_start or a.tie_stop))
            or (b is not None and b.kind == "note" and (b.tie_start or b.tie_stop))
        ),
        lambda a, b: (
            a.kind == b.kind == "note" and (a.tie_start, a.tie_stop) == (b.tie_start, b.tie_stop)
        ),
    )
    exact(
        "accidentalExactRate",
        lambda a, b: a.kind == "note" and a.accidental,
        lambda a, b: a.pitch is not None and b.pitch is not None and a.pitch[1] == b.pitch[1],
    )
    exact(
        "graceExact",
        lambda a, b: a.grace,
        lambda a, b: (
            b.grace
            and all(
                getattr(a, key) == getattr(b, key)
                for key in ("kind", "pitch", "onset", "tie_start", "tie_stop")
            )
        ),
    )
    operations = sum(g.cost[0] for g in groups)
    exact_measures = exact_with_lyrics = lyric_ops = lyric_total = lyric_correct = 0
    chord_correct = chord_total = 0
    attr_counts = {name: [0, 0] for name in ("key", "time")}
    traces = []
    for group in groups:
        lyrics = [item for pair in group.events for item in lyric_pairs(pair)]
        lyric_ops += sum(item["operations"] for item in lyrics)
        lyric_total += sum(item["reference"] is not None for item in lyrics)
        lyric_correct += sum(
            item["reference"] is not None and not item["errors"] for item in lyrics
        )
        _, harmonies = align_items(
            joined(group.reference, "harmonies"),
            joined(group.prediction, "harmonies"),
            value_errors,
            budget,
            charge_onset=True,
        )
        chord_total += sum(p.reference is not None for p in harmonies)
        chord_correct += sum(p.reference is not None and not p.errors for p in harmonies)
        attributes: list[Pair[Attribute]] = []
        for name in ("key", "time", "clef"):
            pairs, reference_changes = attribute_pairs(group.reference, group.prediction, name)
            attributes.extend(pairs)
            if name in attr_counts:
                attr_counts[name][0] += sum(
                    p.reference is not None
                    and p.reference.ref in reference_changes
                    and not p.errors
                    for p in pairs
                )
                attr_counts[name][1] += len(reference_changes)
        # A missing/extra measure is one structural object plus its events; do not
        # charge its contained attributes/harmonies again (ADR-012 measure gap).
        additional = (
            sum(p.operations for p in (*harmonies, *attributes))
            if group.reference and group.prediction
            else 0
        )
        operations += additional
        is_exact = (
            group.operation == "match"
            and not any(p.errors for p in group.events)
            and not any(p.errors for p in (*harmonies, *attributes))
            and group.reference[0].state == group.prediction[0].state
            and group.reference[0].marks == group.prediction[0].marks
        )
        exact_measures += is_exact
        exact_with_lyrics += is_exact and not any(item["errors"] for item in lyrics)
        traces.append(
            {
                "reference": [m.ref for m in group.reference],
                "prediction": [m.ref for m in group.prediction],
                "operation": group.operation,
                "alignmentCost": group.cost,
                "k1Operations": group.cost[0] + additional,
                "events": [{**asdict(p), "lyrics": lyric_pairs(p)} for p in group.events],
                "harmonies": [asdict(p) for p in harmonies],
                "attributes": [asdict(p) for p in attributes],
                "states": {
                    "reference": [m.state for m in group.reference],
                    "prediction": [m.state for m in group.prediction],
                },
                "marks": {
                    "reference": [m.marks for m in group.reference],
                    "prediction": [m.marks for m in group.prediction],
                },
                "measureExact": is_exact,
                "measureErrors": (
                    ["structure"]
                    if group.operation != "match"
                    else [
                        key
                        for key, differs in (
                            ("events", any(p.errors for p in group.events)),
                            ("harmonies", any(p.errors for p in harmonies)),
                            ("attributes", any(p.errors for p in attributes)),
                            ("state", group.reference[0].state != group.prediction[0].state),
                            (
                                "repeatOrVolta",
                                group.reference[0].marks != group.prediction[0].marks,
                            ),
                        )
                        if differs
                    ]
                ),
                "measureExactWithLyrics": is_exact and not any(item["errors"] for item in lyrics),
            }
        )
    total = sum(len(m.events) for m in reference.measures)
    metrics.update(
        {
            "K1": rate(operations, total, 100),
            "K1-L": rate(lyric_ops, lyric_total, 100),
            "lyricExactRate": rate(lyric_correct, lyric_total),
            "chordSymbolExactRate": rate(chord_correct, chord_total),
            "measureExactMatchRate": rate(exact_measures, len(reference.measures)),
            "measureExactWithLyrics": rate(exact_with_lyrics, len(reference.measures)),
            "keySignatureExactRate": rate(*attr_counts["key"]),
            "timeSignatureExactRate": rate(*attr_counts["time"]),
        }
    )
    return {
        "metrics": metrics,
        "k1Operations": operations,
        "onsetOnlyMismatch": sum(p.errors == ("onset",) for p in event_pairs),
    }, traces
