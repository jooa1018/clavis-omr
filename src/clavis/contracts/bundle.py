"""Cross-document referential validation; no object is synthesized or repaired."""

from dataclasses import dataclass

from .common import Severity, references, unique
from .geometry import PageInput, PageLayout
from .outputs import ElementConfidence, EvidenceBundle, Report, ReviewHints
from .score import ScoreIR
from .symbols import StaffLattice, SymbolGraph
from .text import TextIR


@dataclass(frozen=True)
class ContractBundle:
    """In-process validation context, not a new serialized contract envelope."""

    pages: list[PageInput]
    layouts: list[PageLayout]
    graphs: list[SymbolGraph]
    lattices: list[StaffLattice]
    texts: list[TextIR]
    score: ScoreIR
    evidence: EvidenceBundle
    hints: ReviewHints
    confidence: ElementConfidence
    report: Report

    def validate(self) -> None:
        for docs in (self.pages, self.layouts, self.graphs, self.lattices, self.texts):
            unique([d.id for d in docs], "document id within type")
        pages = {p.id: p for p in self.pages}
        references([p.id for p in self.layouts] + [p.id for p in self.texts], set(pages), "page IR")
        staff_ids = {s.staff_id for p in self.layouts for s in p.staves}
        systems = {s.system_id: p.id for p in self.layouts for s in p.systems}
        strips = {s.strip_id: s for p in self.layouts for s in p.strips}
        texts = {t.text_id: t for p in self.texts for t in p.items}
        symbols = {s.symbol_id for g in self.graphs for s in g.symbols}
        graphs = {g.id: g for g in self.graphs}
        for layout in self.layouts:
            if layout.non_staff_mask is not None:
                mask = layout.non_staff_mask
                frames = {f.id: f for f in pages[layout.id].frames}
                frame = frames.get(mask.frame_id)
                if frame is None or (mask.width, mask.height) != (
                    frame.width_pixels,
                    frame.height_pixels,
                ):
                    raise ValueError("mask frame/size mismatch")
        references(
            [g.strip_id for g in self.graphs] + [g.strip_id for g in self.lattices],
            set(strips),
            "IR strip",
        )
        for graph in self.graphs:
            strip = strips[graph.strip_id]
            for candidate in [*graph.symbols, *graph.rejected_candidates]:
                x, y, w, h = candidate.box_strip
                if x < 0 or y < 0 or x + w > strip.width or y + h > strip.height:
                    raise ValueError("symbol outside strip")
        for lattice in self.lattices:
            references([lattice.id], set(graphs), "lattice graph")
            local_symbols = {s.symbol_id for s in graphs[lattice.id].symbols}
            for hypothesis in lattice.hypotheses:
                for item in hypothesis.items:
                    references(item.symbol_ids, local_symbols, "lattice symbol")
        for text_page in self.texts:
            page = pages[text_page.id]
            for text_item in text_page.items:
                if text_item.page_index != page.page_index:
                    raise ValueError("text page mismatch")
                references([text_item.staff_link.staff_id], staff_ids, "text staff")
        for part in self.score.parts:
            references(
                [s for slot in part.staff_slots for s in slot.staff_ids], staff_ids, "part staff"
            )
        xml_ids: set[str] = set()
        target_ids: set[str] = set(texts)
        referenced_evidence: list[str] = []
        events = []
        harmonies = []
        staff_measures = []
        for measure in self.score.measures:
            if systems.get(measure.system_id) != f"pg{measure.page_index}":
                raise ValueError("measure system/page mismatch")
            xml_ids.add(measure.measure_id)
            harmonies += measure.harmonies
            for harmony in measure.harmonies:
                references([harmony.text_id], set(texts), "harmony text")
                referenced_evidence += harmony.evidence_ids
                xml_ids.add(harmony.harmony_id)
            for direction in measure.directions:
                if direction.text_id is not None:
                    references([direction.text_id], set(texts), "direction text")
                if direction.symbol_id is not None:
                    references([direction.symbol_id], symbols, "direction symbol")
                xml_ids.add(direction.direction_id)
            for sm in measure.staff_measures:
                staff_measures.append(sm)
                if not any(
                    s.staff_id == sm.staff_id and s.system_id == measure.system_id
                    for p in self.layouts
                    for s in p.staves
                ):
                    raise ValueError("staffMeasure system mismatch")
                referenced_evidence += sm.evidence_ids
                for voice in sm.voices:
                    for event in voice.events:
                        events.append(event)
                        xml_ids.add(event.event_id)
                        referenced_evidence += event.evidence_ids
                        references(
                            [lyric.text_id for lyric in event.lyrics], set(texts), "lyric text"
                        )
                        target_ids.update(
                            f"{event.event_id}-l{lyric.verse}" for lyric in event.lyrics
                        )
        target_ids.update(xml_ids)
        ev_ids = {e.id for e in self.evidence.evidence}
        references(referenced_evidence, ev_ids, "score evidence")
        references(
            [e.vendor_target_id for e in self.evidence.evidence if e.vendor_target_id],
            xml_ids,
            "evidence XML target",
        )
        references(
            [p.staff_id for p in self.evidence.extensions.staff_polygons],
            staff_ids,
            "polygon staff",
        )
        references(
            [m.staff_measure_id for m in self.evidence.extensions.measure_boxes],
            {s.staff_measure_id for s in staff_measures},
            "evidence staffMeasure",
        )
        original_frames = {
            f.id: f for p in self.pages for f in p.frames if f.coordinate_space == "original-pixels"
        }
        for frame in self.evidence.frames:
            if original_frames.get(frame.id) != frame:
                raise ValueError("evidence/source frame mismatch")
        typed_targets = {
            "event": {e.event_id for e in events},
            "harmony": {h.harmony_id for h in harmonies},
            "text": set(texts),
            "lyric": {f"{e.event_id}-l{lyric.verse}" for e in events for lyric in e.lyrics},
            "measure": {m.measure_id for m in self.score.measures},
            "measureStart": {m.measure_id for m in self.score.measures},
            "measureEnd": {m.measure_id for m in self.score.measures},
            "flow": {m.measure_id for m in self.score.measures}
            | {d.direction_id for m in self.score.measures for d in m.directions},
        }
        if self.evidence.granularity == "measure":
            references(
                list(typed_targets["measure"]),
                {
                    e.vendor_target_id
                    for e in self.evidence.evidence
                    if e.vendor_target_id is not None and e.granularity == "measure"
                },
                "guaranteed measure evidence",
            )
        for hint in self.hints.hints:
            references([hint.target.id], typed_targets[hint.target.kind], "hint target kind")
            references([hint.target.id], target_ids, "hint target")
            references(hint.evidence_ids, ev_ids, "hint evidence")
        for diagnostic in [*self.score.diagnostics, *self.report.diagnostics]:
            if diagnostic.target is not None:
                references([diagnostic.target.id], target_ids, "diagnostic target")
        for entry in self.confidence.elements:
            references(
                [entry.parent_id if entry.parent_id is not None else entry.id],
                target_ids,
                "confidence target",
            )
        required_confidence = xml_ids | {
            f"{e.event_id}-l{lyric.verse}" for e in events for lyric in e.lyrics
        }
        references(
            list(required_confidence),
            {c.id for c in self.confidence.elements},
            "missing confidence element",
        )
        if self.report.status != self.score.status:
            raise ValueError("report/score status mismatch")
        counts = self.report.counts
        if (
            counts.systems,
            counts.staves,
            counts.measures,
            counts.events,
            counts.harmonies,
            counts.lyrics,
        ) != (
            len(systems),
            len(staff_ids),
            len(self.score.measures),
            len(events),
            len(harmonies),
            sum(len(e.lyrics) for e in events),
        ):
            raise ValueError("report counts mismatch")
        severities: tuple[Severity, ...] = ("blocking", "warning", "info")
        if any(
            counts.hints_by_severity.get(severity, 0)
            != sum(h.severity == severity for h in self.hints.hints)
            for severity in severities
        ):
            raise ValueError("hint counts mismatch")
