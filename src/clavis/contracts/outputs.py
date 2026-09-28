"""External output envelopes and review patches (CONTRACTS 3.8, 8)."""

from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, model_validator

from .common import (
    Alter,
    Bp,
    Diagnostic,
    Digest,
    Id,
    Key,
    NonnegativeFraction,
    Pitch,
    PositiveInt,
    Severity,
    Status,
    Target,
    Text,
    Time,
    UInt,
    WireModel,
    unique,
)
from .geometry import ImageCoordinateFrame, QualityReport
from .score import ChordParseResult, Event

ReasonCode = Literal[
    "DURATION_MISMATCH",
    "LOW_CONFIDENCE_PITCH",
    "LOW_CONFIDENCE_DURATION",
    "ACCIDENTAL_AMBIGUOUS",
    "TIE_SLUR_AMBIGUOUS",
    "KEY_SIGNATURE_UNCERTAIN",
    "TIME_SIGNATURE_UNCERTAIN",
    "CLEF_UNCERTAIN",
    "BARLINE_UNCERTAIN",
    "VOICE_ASSIGNMENT_UNCERTAIN",
    "CHORD_TEXT_UNCERTAIN",
    "CHORD_POSITION_UNCERTAIN",
    "CHORD_OUTSIDE_CONSUMER_VOCAB",
    "LYRIC_TEXT_UNCERTAIN",
    "LYRIC_ALIGNMENT_UNCERTAIN",
    "FLOW_UNRESOLVED",
    "EVIDENCE_MISSING",
    "MODEL_DISAGREEMENT",
    "OOD_REGION",
    "ILLEGIBLE_REGION",
]
ErrorCode = Literal[
    "CLAVIS_INPUT_UNSUPPORTED",
    "CLAVIS_INPUT_CORRUPT",
    "CLAVIS_INPUT_TOO_LARGE",
    "CLAVIS_QUALITY_RETAKE",
    "CLAVIS_NO_STAFF_FOUND",
    "CLAVIS_OOD",
    "CLAVIS_OUTPUT_INCOMPLETE",
    "CLAVIS_OUTPUT_BLOCKED",
    "CLAVIS_RESOURCE_LIMIT",
    "CLAVIS_TIMEOUT",
    "CLAVIS_CANCELLED",
    "CLAVIS_INTERNAL",
]
Granularity = Literal["none", "page", "staff", "measure", "symbol"]


class PitchPatch(WireModel):
    kind: Literal["pitch"]
    pitch: Pitch


class DurationPatch(WireModel):
    kind: Literal["duration"]
    duration: NonnegativeFraction


class AccidentalPatch(WireModel):
    kind: Literal["accidental"]
    alter: Alter


class TiePatch(WireModel):
    kind: Literal["tie"]
    tie_start: StrictBool
    tie_stop: StrictBool


class ChordPatch(WireModel):
    kind: Literal["chord"]
    parse_result: ChordParseResult


class TimeSignaturePatch(WireModel):
    kind: Literal["timeSignature"]
    value: Time


class KeySignaturePatch(WireModel):
    kind: Literal["keySignature"]
    value: Key


class ReplaceEventPatch(WireModel):
    kind: Literal["replaceEvent"]
    event: Event


class ReplaceSourceTextPatch(WireModel):
    kind: Literal["replaceSourceText"]
    text: Text


class InsertBarlinePatch(WireModel):
    kind: Literal["insertBarline"]


class DeleteBarlinePatch(WireModel):
    kind: Literal["deleteBarline"]


Patch = Annotated[
    PitchPatch
    | DurationPatch
    | AccidentalPatch
    | TiePatch
    | ChordPatch
    | TimeSignaturePatch
    | KeySignaturePatch
    | ReplaceEventPatch
    | ReplaceSourceTextPatch
    | InsertBarlinePatch
    | DeleteBarlinePatch,
    Field(discriminator="kind"),
]


class Alternative(WireModel):
    alternative_id: Id
    label_ko: Text
    patch: Patch
    confidence_bp: Bp


class ReviewHint(WireModel):
    hint_id: Id
    target: Target
    reason_code: ReasonCode
    severity: Severity
    confidence_bp: Bp
    alternatives: list[Alternative]
    evidence_ids: list[Id]

    @model_validator(mode="after")
    def ids(self) -> Self:
        unique([a.alternative_id for a in self.alternatives], "alternative id")
        return self


class ReviewHints(WireModel):
    schema_version: Literal["clavis-hints-0.1"] = Field(alias="schema")
    threshold_artifact_digest: Digest | None
    hints: list[ReviewHint]

    @model_validator(mode="after")
    def ids(self) -> Self:
        unique([h.hint_id for h in self.hints], "hint id")
        return self


class BoundingBox(WireModel):
    frame_id: Id
    x_mu: UInt
    y_mu: UInt
    width_mu: UInt
    height_mu: UInt


class OmrEvidence(WireModel):
    id: Id
    vendor_target_id: Id | None = None
    granularity: Granularity
    box: BoundingBox
    transform_id: None = None
    confidence_bp: Bp | None = None
    vendor_id: Text


class StaffPolygon(WireModel):
    staff_id: Id
    frame_id: Id
    points_mu: Annotated[list[tuple[UInt, UInt]], Field(min_length=3)]


class MeasureBox(WireModel):
    staff_measure_id: Id
    box: BoundingBox


class EvidenceExtensions(WireModel):
    staff_polygons: list[StaffPolygon]
    measure_boxes: list[MeasureBox]


class EvidenceBundle(WireModel):
    schema_version: Literal["clavis-evidence-0.1"] = Field(alias="schema")
    granularity: Granularity
    frames: list[ImageCoordinateFrame]
    transforms: Annotated[list[None], Field(max_length=0)]
    evidence: list[OmrEvidence]
    extensions: EvidenceExtensions

    @model_validator(mode="after")
    def bounds(self) -> Self:
        unique([f.id for f in self.frames], "frame id")
        unique([e.id for e in self.evidence], "evidence id")
        unique(
            [e.vendor_target_id for e in self.evidence if e.vendor_target_id is not None],
            "evidence target",
        )
        unique([p.staff_id for p in self.extensions.staff_polygons], "staff polygon")
        unique([b.staff_measure_id for b in self.extensions.measure_boxes], "measure box")
        frames = {f.id: f for f in self.frames}
        if any(f.coordinate_space != "original-pixels" for f in self.frames):
            raise ValueError("external frames must be original")
        points = [
            (b.frame_id, b.x_mu + b.width_mu, b.y_mu + b.height_mu)
            for b in [
                *[e.box for e in self.evidence],
                *[m.box for m in self.extensions.measure_boxes],
            ]
        ]
        points += [
            (p.frame_id, x, y) for p in self.extensions.staff_polygons for x, y in p.points_mu
        ]
        for frame_id, x, y in points:
            frame = frames.get(frame_id)
            if frame is None:
                raise ValueError("dangling evidence frame")
            if x > frame.width_pixels * 1000000 or y > frame.height_pixels * 1000000:
                raise ValueError("external coordinates outside frame")
        return self


class ConfidenceElement(WireModel):
    id: Id
    kind: Text
    confidence_bp: Bp
    flagged: StrictBool
    parent_id: Id | None = None
    path: (
        Annotated[
            Text,
            Field(
                pattern=r"^[A-Za-z_][A-Za-z0-9_-]*\[[1-9][0-9]*\](?:/[A-Za-z_][A-Za-z0-9_-]*\[[1-9][0-9]*\])*$"
            ),
        ]
        | None
    ) = None

    @model_validator(mode="after")
    def parent_path(self) -> Self:
        if (self.parent_id is None) != (self.path is None):
            raise ValueError("parentId/path must occur together")
        return self


class ElementConfidence(WireModel):
    schema_version: Literal["clavis-confidence-0.1"] = Field(alias="schema")
    elements: list[ConfidenceElement]

    @model_validator(mode="after")
    def ids(self) -> Self:
        unique([e.id for e in self.elements], "confidence id")
        return self


class EngineInfo(WireModel):
    name: Text
    version: Text
    git_sha: Annotated[Text, Field(pattern=r"^[0-9a-f]{40}$")]
    build_digest: Digest


class ModelInfo(WireModel):
    name: Text
    version: Text
    sha256: Digest


class InputPage(WireModel):
    page_index: UInt
    bytes_sha256: Digest
    width: PositiveInt
    height: PositiveInt
    source_kind: Literal["image", "pdf"]
    raster_dpi: PositiveInt | None = None


class ReportInput(WireModel):
    pages: list[InputPage]


class Counts(WireModel):
    systems: UInt
    staves: UInt
    measures: UInt
    events: UInt
    harmonies: UInt
    lyrics: UInt
    hints_by_severity: dict[Severity, UInt]


class Report(WireModel):
    schema_version: Literal["clavis-report-0.1"] = Field(alias="schema")
    engine: EngineInfo
    models: list[ModelInfo]
    config_digest: Digest
    input: ReportInput
    quality: list[QualityReport]
    status: Status
    error_code: ErrorCode | None = None
    counts: Counts
    diagnostics: list[Diagnostic]

    @model_validator(mode="after")
    def ids(self) -> Self:
        unique([p.page_index for p in self.input.pages], "report page")
        unique([q.id for q in self.quality], "quality id")
        return self


class RuntimeValues(WireModel):
    threads: PositiveInt
    elapsed_ms: UInt
    cpu_ms: UInt
    peak_rss_bytes: UInt


class StageRuntime(RuntimeValues):
    stage_id: Id


class Platform(WireModel):
    os: Text
    python_version: Text
    onnxruntime_version: Text | None = None


class RuntimeReport(RuntimeValues):
    schema_version: Literal["clavis-runtime-0.1"] = Field(alias="schema")
    stages: list[StageRuntime]
    platform: Platform | None = None

    @model_validator(mode="after")
    def ids(self) -> Self:
        unique([s.stage_id for s in self.stages], "stage id")
        return self
