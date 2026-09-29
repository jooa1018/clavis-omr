"""Page geometry wire structures (CONTRACTS 2, 3.1–3.3, CCR-0001 C4)."""

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .common import (
    BarStyle,
    Box,
    Bp,
    Digest,
    Id,
    NonnegativeReal,
    PageIR,
    Polyline,
    PositiveInt,
    PositiveReal,
    Real,
    Text,
    UInt,
    WireModel,
    references,
    unique,
)


class ImageCoordinateFrame(WireModel):
    id: Id
    page_index: UInt
    coordinate_space: Literal["original-pixels", "processed-pixels"]
    width_pixels: PositiveInt
    height_pixels: PositiveInt
    image_digest: Digest


class Homography(WireModel):
    id: Id
    from_frame_id: Id
    to_frame_id: Id
    kind: Literal["homography"]
    matrix: Annotated[list[Real], Field(min_length=9, max_length=9)]

    @model_validator(mode="after")
    def normalized(self) -> Self:
        if self.matrix[-1] != 1:
            raise ValueError("homography must have m[8]=1")
        return self


class Source(WireModel):
    kind: Literal["image", "pdf"]
    mime: Text
    bytes_sha256: Digest
    pdf_page_index: UInt | None = None
    raster_dpi: PositiveReal | None = None


class Original(WireModel):
    width: PositiveInt
    height: PositiveInt
    pixels_sha256: Digest


class PageInput(PageIR):
    page_index: UInt
    source: Source
    original: Original
    frames: list[ImageCoordinateFrame]
    transforms: list[Homography]

    @model_validator(mode="after")
    def frame_links(self) -> Self:
        unique([f.id for f in self.frames], "frame id")
        unique([t.id for t in self.transforms], "transform id")
        available = {f.id for f in self.frames}
        references(
            [v for t in self.transforms for v in (t.from_frame_id, t.to_frame_id)],
            available,
            "transform frame",
        )
        if self.id != f"pg{self.page_index}" or any(
            f.page_index != self.page_index for f in self.frames
        ):
            raise ValueError("page identity mismatch")
        return self


class QualityReport(PageIR):
    blur_bp: Bp
    perspective_bp: Bp
    glare_bp: Bp
    crop_risk_bp: Bp
    estimated_staff_space_pixels: PositiveReal | None = None
    status: Literal["pass", "warn", "retake"]
    reasons: list[Text]
    contrast_bp: Bp
    noise_bp: Bp
    jpeg_quality_estimate: Annotated[UInt, Field(le=100)] | None = None
    interline_spread_bp: Bp
    expected_burden_bucket: Literal["low", "medium", "high"] | None = None


class InterlineSample(WireModel):
    x: Real
    interline_px: PositiveReal


class Staff(WireModel):
    staff_id: Id
    system_id: Id
    lines: Annotated[list[Polyline], Field(min_length=5, max_length=5)]
    interline_px: PositiveReal
    interline_profile: list[InterlineSample]
    line_thickness_px: PositiveReal
    bbox: Box
    line_count: PositiveInt
    ood: Literal["tablature", "percussion", "unknown"] | None = None
    confidence_bp: Bp

    @model_validator(mode="after")
    def ordered_profile(self) -> Self:
        xs = [p.x for p in self.interline_profile]
        if xs != sorted(set(xs)):
            raise ValueError("interlineProfile x must increase")
        return self


class StaffGroup(WireModel):
    type: Literal["brace", "bracket", "none"]
    staff_ids: list[Id]


class LayoutBarline(WireModel):
    x_processed: Real
    u_by_staff: dict[Id, Real]
    span_staff_ids: list[Id]
    style_guess: BarStyle
    confidence_bp: Bp


class System(WireModel):
    system_id: Id
    staff_ids: list[Id]
    groups: list[StaffGroup]
    barlines: list[LayoutBarline]

    @model_validator(mode="after")
    def staff_links(self) -> Self:
        unique(self.staff_ids, "system staff id")
        available = set(self.staff_ids)
        references([s for g in self.groups for s in g.staff_ids], available, "group staff")
        for bar in self.barlines:
            references(bar.span_staff_ids + list(bar.u_by_staff), available, "barline staff")
        return self


class DewarpMesh(WireModel):
    u_step: PositiveReal
    x: Annotated[list[Real], Field(min_length=2)]
    y_top: list[Real]
    interline: list[PositiveReal]

    @model_validator(mode="after")
    def samples(self) -> Self:
        if not len(self.x) == len(self.y_top) == len(self.interline):
            raise ValueError("mesh arrays must have equal length")
        if any(b <= a for a, b in zip(self.x, self.x[1:], strict=False)):
            raise ValueError("mesh x must increase")
        return self


class StripRef(WireModel):
    strip_id: Id
    s_star: PositiveReal
    width: PositiveInt
    height: PositiveInt
    margin_above_spaces: NonnegativeReal
    margin_below_spaces: NonnegativeReal
    mesh: DewarpMesh
    pixels_sha256: Digest


class NonStaffMask(WireModel):
    frame_id: Id
    width: PositiveInt
    height: PositiveInt
    counts: Annotated[list[UInt], Field(min_length=1)]

    @model_validator(mode="after")
    def rle_size(self) -> Self:
        if sum(self.counts) != self.width * self.height:
            raise ValueError("RLE length must equal pixel count")
        return self


class PageLayout(PageIR):
    staves: list[Staff]
    systems: list[System]
    strips: list[StripRef]
    reading_order: list[Id]
    non_staff_mask: NonStaffMask | None = None
    ood_flags: list[Text]

    @model_validator(mode="after")
    def links(self) -> Self:
        for values in (
            [s.staff_id for s in self.staves],
            [s.system_id for s in self.systems],
            [s.strip_id for s in self.strips],
            self.reading_order,
        ):
            unique(values, "layout id")
        staff_map = {s.staff_id: s for s in self.staves}
        systems = {s.system_id for s in self.systems}
        if set(self.reading_order) != systems:
            raise ValueError("readingOrder must list every system")
        references([s.system_id for s in self.staves], systems, "staff system")
        references([s.strip_id for s in self.strips], set(staff_map), "strip staff")
        for system in self.systems:
            references(system.staff_ids, set(staff_map), "system staff")
            if set(system.staff_ids) != {
                s.staff_id for s in self.staves if s.system_id == system.system_id
            }:
                raise ValueError("system/staff membership mismatch")
        return self
