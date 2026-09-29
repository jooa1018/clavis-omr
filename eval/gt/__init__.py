"""Private local GT intake models; independent of engine contracts."""

from __future__ import annotations

from datetime import date
from math import isfinite
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Positive = Annotated[int, Field(gt=0, strict=True)]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Rights(Record):
    basis: Literal["self-authored", "public-domain", "licensed", "user-confirmed-rights"]
    allowedUses: list[Literal["evaluation", "training", "redistribution"]]
    reference: Annotated[str, Field(min_length=1)]


class LeadStaff(Record):
    part: str
    staff: Positive
    voices: Annotated[list[str], Field(min_length=1)]


class Region(Record):
    systemIndex: Positive
    sourceMeasureLabels: Annotated[list[str], Field(min_length=1)]
    xmlMeasureStart: Positive
    xmlMeasureEnd: Positive
    # All coordinates refer to the unchanged original page, not a crop.
    bbox: tuple[float, float, float, float]

    @model_validator(mode="after")
    def valid(self) -> Self:
        if not all(isfinite(v) for v in self.bbox):
            raise ValueError("nonfinite rectangle")
        if (
            self.xmlMeasureEnd < self.xmlMeasureStart
            or len(self.sourceMeasureLabels) != self.xmlMeasureEnd - self.xmlMeasureStart + 1
        ):
            raise ValueError("region measure map mismatch")
        if self.bbox[0] < 0 or self.bbox[1] < 0 or self.bbox[2] <= 0 or self.bbox[3] <= 0:
            raise ValueError("invalid region rectangle")
        return self


class Illegible(Record):
    systemIndex: Positive
    sourceMeasureLabel: str
    bbox: tuple[float, float, float, float]
    reason: Literal["unreadable", "edition-mismatch", "boundary-context-unknown"]

    @model_validator(mode="after")
    def valid(self) -> Self:
        if (
            not all(isfinite(v) for v in self.bbox)
            or min(self.bbox[:2]) < 0
            or min(self.bbox[2:]) <= 0
        ):
            raise ValueError("invalid illegible rectangle")
        return self


class Selection(Record):
    method: Literal["sha256-rank-v1", "whole-page", "legacy-existing"]
    seed: str
    totalSystems: Positive
    selectedSystems: Annotated[list[Positive], Field(min_length=1)]
    recordedOn: date


class Review(Record):
    transcribedOn: date
    renderedComparedOn: date
    reviewedOn: date
    reviewer: Identifier
    independentReviewer: bool
    allSelectedMeasuresChecked: Literal[True]

    @model_validator(mode="after")
    def different_day(self) -> Self:
        if not self.transcribedOn <= self.renderedComparedOn < self.reviewedOn:
            raise ValueError("review must occur on a later day than render comparison")
        return self


class Sidecar(Record):
    schemaVersion: Literal["clavis-gt-1"]
    pageId: Identifier
    songId: Identifier
    captureId: Identifier
    printId: Identifier | None
    tier: Literal["SYN", "R-PC", "R-LIED", "R-TGT", "R-LEGACY"]
    split: Literal["dev", "sealed"]
    devPartition: Literal["Dev-Tune", "Dev-Check"] | None
    sourceKind: Literal["digital-pdf", "scanned-pdf", "camera-photo"]
    captureChannel: str
    captureDevice: str | None
    engravingTool: str | None
    musicFont: str | None
    publicationFont: str | None = None
    editingProgram: str | None = None
    measuredInterlinePx: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    meter: Literal["4/4", "6/8", "other"]
    keyMode: Literal["major", "minor"]
    features: list[Literal["accidentals", "dotted-notes", "ties"]]
    notationFeatures: list[str]
    leadStaff: LeadStaff
    imagePath: str
    imageDigest: Digest
    musicXmlPath: str
    groundTruthDigest: Digest
    renderPath: str
    renderDigest: Digest
    evalRegions: list[Region]
    illegibleRegions: list[Illegible]
    selection: Selection
    rights: Rights
    review: Review
    legacy: bool
    contaminated: bool
    assisted: bool
    notes: str

    @model_validator(mode="after")
    def provenance(self) -> Self:
        if (self.split == "dev") != (self.devPartition is not None):
            raise ValueError("Dev partition inconsistent with split")
        if "evaluation" not in self.rights.allowedUses:
            raise ValueError("evaluation rights required")
        if self.tier in {"R-TGT", "R-LEGACY", "R-LIED"} and "training" in self.rights.allowedUses:
            raise ValueError("evaluation-only corpus cannot allow training")
        if self.tier == "R-LEGACY" and not (
            self.legacy and self.contaminated and self.split == "dev"
        ):
            raise ValueError("legacy must be contaminated Dev")
        if self.legacy and self.tier != "R-LEGACY":
            raise ValueError("legacy tier mismatch")
        if self.split == "sealed" and (self.assisted or self.contaminated):
            raise ValueError("sealed provenance is invalid")
        selected = self.selection.selectedSystems
        if self.selection.recordedOn > self.review.transcribedOn:
            raise ValueError("selection must precede transcription")
        if len(set(self.features)) != len(self.features) or len(set(self.leadStaff.voices)) != len(
            self.leadStaff.voices
        ):
            raise ValueError("duplicate feature or voice")
        if any(region.systemIndex not in selected for region in self.illegibleRegions):
            raise ValueError("illegible region outside selection")
        if selected != sorted(set(selected)) or max(selected) > self.selection.totalSystems:
            raise ValueError("invalid selected systems")
        if self.evalRegions and [r.systemIndex for r in self.evalRegions] != selected:
            raise ValueError("region selection mismatch")
        if not self.evalRegions and selected != list(range(1, self.selection.totalSystems + 1)):
            raise ValueError("partial transcription requires region map")
        if self.selection.method == "sha256-rank-v1" and not 2 <= len(selected) <= 4:
            raise ValueError("random partial GT requires 2 to 4 systems")
        if self.selection.method == "legacy-existing" and self.tier != "R-LEGACY":
            raise ValueError("existing transcription selection is legacy only")
        return self


class Manifest(Record):
    schemaVersion: Literal["clavis-gt-manifest-1"]
    datasetVersion: str
    sidecars: Annotated[list[str], Field(min_length=1)]
