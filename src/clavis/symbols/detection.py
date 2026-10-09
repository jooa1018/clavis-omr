"""Provisional notehead and vertical-line evidence for normalized strips."""

import json
from dataclasses import dataclass
from math import exp
from pathlib import Path
from typing import cast

import cv2
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from clavis.contracts.common import Producer
from clavis.contracts.symbols import SymbolGraph
from clavis.symbols.templates import Gray, template_responses


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    candidate_bp: int = Field(ge=0, le=10000)
    accept_bp: int = Field(ge=0, le=10000)
    nms_spaces: float = Field(gt=0)
    ink_ratio: float = Field(gt=0, lt=1)
    line_height_spaces: float = Field(gt=0)
    line_width_spaces: float = Field(gt=0)
    bar_end_tolerance_spaces: float = Field(gt=0)
    line_class_bp: int = Field(ge=0, le=10000)
    line_alternative_bp: int = Field(ge=0, le=10000)
    pos_sigma_steps: float = Field(gt=0)
    stem_dx_spaces: float = Field(gt=0)
    stem_dy_spaces: float = Field(gt=0)

    @model_validator(mode="after")
    def consistent(self) -> "Settings":
        if self.candidate_bp > self.accept_bp:
            raise ValueError("Candidate floor must not exceed acceptance floor")
        if self.line_class_bp + self.line_alternative_bp > 10000:
            raise ValueError("Line class probabilities exceed one")
        return self

    @classmethod
    def load(cls, path: Path) -> "Settings":
        """The registry uses JSON, a YAML subset; no runtime YAML dependency."""
        rows = json.loads(path.read_text(encoding="utf-8"))
        return cls.model_validate({row["name"]: row["value"] for row in rows})


@dataclass(frozen=True)
class Template:
    symbol_class: str
    pixels: Gray


def detect(
    original: Gray,
    staff_removed: Gray,
    *,
    staff_id: str,
    staff_space: float,
    v_top: float,
    templates: list[Template],
    settings: Settings,
    producer: Producer,
    disabled: frozenset[str] = frozenset(),
) -> SymbolGraph:
    """Return provisional evidence; never infer pitch or missing beam/dot attributes."""
    if not np.isfinite(staff_space) or staff_space <= 0 or not np.isfinite(v_top):
        raise ValueError("Expected finite strip geometry with positive staff spacing")
    maps = template_responses(
        original,
        staff_removed,
        [t.pixels for t in templates],
        enabled="SYM-TEMPLATE-001" not in disabled,
    )
    radius = max(1, round(settings.nms_spaces * staff_space))
    kernel = np.ones((2 * radius + 1, 2 * radius + 1), np.uint8)
    hits: list[tuple[int, int, int, int]] = []
    for index, channels in enumerate(maps):
        response = np.maximum(*channels)
        peak = cv2.dilate(response.astype(np.float32), kernel)
        ys, xs = np.where((response == peak) & (response >= settings.candidate_bp))
        hits.extend(
            (int(response[y, x]), index, int(x), int(y)) for y, x in zip(ys, xs, strict=True)
        )
    hits.sort(key=lambda h: (-h[0], h[2], h[3], h[1]))
    records: list[dict[str, object]] = []
    centers: list[tuple[float, float]] = []
    for score, index, x, y in hits:
        template = templates[index]
        height, width = template.pixels.shape
        center = (x + width / 2, y + height / 2)
        if any(abs(center[0] - u) <= radius and abs(center[1] - v) <= radius for u, v in centers):
            continue
        centers.append(center)
        # Keep other head shapes in the graph instead of argmaxing their classes.
        classes: dict[str, int] = {template.symbol_class: score}
        for other_score, other_index, ox, oy in hits:
            oh, ow = templates[other_index].pixels.shape
            if abs(ox + ow / 2 - center[0]) <= radius and abs(oy + oh / 2 - center[1]) <= radius:
                name = templates[other_index].symbol_class
                classes[name] = max(classes.get(name, 0), other_score)
        classes["reject"] = max(1, 10000 - score)
        total = sum(classes.values())
        top = sorted(
            ((c, p * 10000 // total) for c, p in classes.items()), key=lambda v: (-v[1], v[0])
        )[:5]
        record: dict[str, object] = {
            "sources": ["template"],
            "classTopK": top,
            "boxStrip": [x, y, width, height],
            "centerStrip": center,
            "accepted": score >= settings.accept_bp,
        }
        if "SYM-POS-001" not in disabled:
            # CONTRACTS 4.1: bottom line pos=0, top line pos=8; no pitch calculation.
            position = 2 * (v_top + 4 * staff_space - center[1]) / staff_space
            values = [
                (p, exp(-(((position - p) / settings.pos_sigma_steps) ** 2) / 2))
                for p in range(-14, 23)
            ]
            denominator = sum(w for _, w in values)
            if denominator:
                record["posTopK"] = sorted(
                    ((p, int(w * 10000 / denominator)) for p, w in values),
                    key=lambda pair: (-pair[1], pair[0]),
                )[:3]
        records.append(record)
    if "SYM-VLINE-001" not in disabled:
        mask = (original <= settings.ink_ratio * np.iinfo(np.uint8).max).astype(np.uint8)
        height = max(1, round(settings.line_height_spaces * staff_space)) // 2 * 2 + 1
        opened = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((height, 1), np.uint8))
        count, _, stats, _ = cv2.connectedComponentsWithStats(opened)
        for component in range(1, count):
            x, y, width, length = (int(v) for v in stats[component, :4])
            if width > settings.line_width_spaces * staff_space:
                continue
            tolerance = settings.bar_end_tolerance_spaces * staff_space
            bar = (
                abs(y - v_top) <= tolerance
                and abs(y + length - (v_top + 4 * staff_space)) <= tolerance
            )
            primary, secondary = ("barline", "stem") if bar else ("stem", "barline")
            top = [
                (primary, settings.line_class_bp),
                (secondary, settings.line_alternative_bp),
                ("reject", 10000 - settings.line_class_bp - settings.line_alternative_bp),
            ]
            records.append(
                {
                    "sources": ["vline"],
                    "classTopK": sorted(top, key=lambda v: (-v[1], v[0])),
                    "boxStrip": [x, y, width, length],
                    "centerStrip": [x + width / 2, y + length / 2],
                    "accepted": True,
                }
            )
    records.sort(key=lambda r: tuple(cast(list[float], r["centerStrip"])))
    accepted: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    for index, record in enumerate(records):
        target = accepted if record.pop("accepted") else rejected
        target.append({**record, "symbolId": f"{staff_id}-s{index}"})
    graph = SymbolGraph.model_validate(
        {
            "schema": "clavis-ir-0.1.1",
            "id": staff_id,
            "stripId": staff_id,
            "producer": producer,
            "symbols": accepted,
            "rejectedCandidates": rejected,
            "relations": [],
        }
    )
    if "SYM-REL-001" not in disabled:
        relations = []
        for head in graph.symbols:
            if not head.class_top_k[0][0].startswith("notehead"):
                continue
            hx, hy, hw, hh = head.box_strip
            candidates = []
            for stem in graph.symbols:
                if stem.class_top_k[0][0] != "stem":
                    continue
                sx, sy, sw, sh = stem.box_strip
                dx = min(abs(sx - (hx + hw)), abs(sx + sw - hx)) / staff_space
                dy = min(abs(sy - (hy + hh / 2)), abs(sy + sh - (hy + hh / 2))) / staff_space
                if dx <= settings.stem_dx_spaces and dy <= settings.stem_dy_spaces:
                    p = round(settings.line_class_bp * exp(-(dx + dy)))
                    candidates.append((p, stem.symbol_id))
            for p, stem_id in sorted(candidates, key=lambda c: (-c[0], c[1]))[:2]:
                relations.append(
                    {"kind": "stemOf", "from": stem_id, "to": head.symbol_id, "probBp": p}
                )
        return SymbolGraph.model_validate(
            {**graph.model_dump(by_alias=True), "relations": relations}
        )
    return graph
