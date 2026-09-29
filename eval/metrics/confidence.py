"""K2/K3 using only the public MusicXML and element-confidence wire format."""

import re
from typing import Any
from xml.etree import ElementTree as ET

from pydantic import ValidationError

from clavis.contracts.outputs import ElementConfidence
from eval.metrics import rate
from eval.policy import limit
from eval.projection.model import EvaluationUnsupported


def confidence_metrics(
    xml: bytes, confidence: bytes, traces: list[dict[str, Any]], total: int
) -> dict[str, Any]:
    if len(confidence) > limit("maxXmlBytes"):
        raise EvaluationUnsupported("confidence-byte-limit")
    try:
        entries = ElementConfidence.model_validate_json(confidence).elements
    except ValidationError:
        raise EvaluationUnsupported("invalid-element-confidence") from None
    root = ET.fromstring(xml)
    addressable = [node for node in root.iter() if node.get("id") and node.tag != "score-part"]
    ids = {node.get("id"): node for node in addressable}
    if len(ids) != len(addressable):
        raise EvaluationUnsupported("duplicate-xml-id")
    targets: dict[int, list[str]] = {}
    flagged: set[str] = set()
    for entry in entries:
        node = ids.get(entry.parent_id or entry.id)
        if entry.path is not None:
            for step in entry.path.split("/"):
                match = re.fullmatch(r"([^\[]+)\[([0-9]+)\]", step)
                assert match is not None
                children = node.findall(match[1]) if node is not None else []
                index = int(match[2]) - 1
                node = children[index] if index < len(children) else None
        if node is None:
            raise EvaluationUnsupported("confidence-target-not-in-public-xml")
        targets.setdefault(id(node), []).append(entry.id)
        if entry.flagged:
            flagged.add(entry.id)
    refs: dict[str, ET.Element] = {}
    for mi, measure in enumerate(root.findall("part/measure")):
        key = f"m{mi}"
        refs[key] = measure
        for prefix, tag in (("e", "note"), ("h", "harmony")):
            refs.update({f"{key}/{prefix}{i}": node for i, node in enumerate(measure.findall(tag))})
        for tag in ("key", "time", "clef"):
            node = measure.find(f"attributes/{tag}")
            if node is not None:
                refs[f"{key}/{tag}"] = node
                refs[f"{key}/state/{tag}"] = node

    correct_flags: set[str] = set()
    errors = marked = 0

    def account(element: str | None, measures: list[str]) -> None:
        nonlocal errors, marked
        errors += 1
        candidates = [*measures, *([element] if element else [])]
        flags = {
            identifier
            for ref in candidates
            if ref in refs
            for identifier in targets.get(id(refs[ref]), [])
        } & flagged
        marked += bool(flags)
        correct_flags.update(flags)

    for group in traces:
        measures = group["prediction"]
        for pair in group["events"]:
            if pair["operations"]:
                prediction = pair["prediction"]
                ref = prediction["ref"] if prediction else None
                account(ref, [ref.split("/")[0]] if ref else measures)
        if group["operation"] != "match":
            account(None, measures)
        if group["reference"] and measures:
            for pair in [*group["harmonies"], *group["attributes"]]:
                if pair["operations"]:
                    prediction = pair["prediction"]
                    ref = prediction["ref"] if prediction else None
                    account(ref, [ref.split("/")[0]] if ref else measures)
    if errors != sum(g["k1Operations"] for g in traces):
        raise EvaluationUnsupported("k2-object-accounting-mismatch")
    return {
        "K2": rate(errors - marked, total),
        "harmonizationReadyRate": rate(int(errors == marked), 1),
        "flagBurden": rate(len(flagged), len(entries)),
        "flagPrecision": rate(len(correct_flags), len(flagged)),
        "errorRecall": rate(marked, errors),
    }
