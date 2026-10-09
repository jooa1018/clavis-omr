"""TextIR boundary for visual OCR observations and explicit upstream role/link.

No role classifier, staff inference, confidence calibration or harmonic
interpretation is implied. Unsupported structure remains absent, with a review
diagnostic. CTC time indices never become image-space glyph boxes.
"""

from dataclasses import dataclass, field
from unicodedata import normalize

from clavis.contracts.score import ChordParseResult
from clavis.contracts.text import Role, StaffLink, Syllable, TextAlternative, TextIR, TextItem

from .beam import ChordCandidate
from .chord import ChordGrammar
from .detection import TextRegion


@dataclass(frozen=True)
class TextObservation:
    region: TextRegion
    text: str
    role: Role
    role_probs: dict[Role, int]
    staff_link: StaffLink
    confidence_bp: int
    candidates: tuple[ChordCandidate, ...] = ()
    syllables: tuple[Syllable, ...] = ()
    chord: ChordParseResult | None = None


@dataclass(frozen=True)
class TextResult:
    ir: TextIR
    diagnostics: tuple[str, ...] = field(default_factory=tuple)


def text_ir(
    observations: tuple[TextObservation, ...],
    *,
    page_index: int,
    grammar: ChordGrammar,
    enabled: bool,
) -> TextResult:
    items: list[TextItem] = []
    diagnostics: list[str] = []
    ordered = sorted(observations, key=lambda o: (o.region.box[1], o.region.box[0], o.text))
    for observation in ordered if enabled else ():
        text = normalize("NFC", observation.text)
        identity = f"pg{page_index}-txt{len(items)}"
        alternatives: list[TextAlternative] = []
        if observation.role == "chord":
            if grammar.parse(text) is None:
                diagnostics.append(f"{identity}: rejected non-grammatical chord observation")
                continue
            seen = set()
            for candidate in observation.candidates:
                parsed = grammar.parse(candidate.text)
                if parsed is None or parsed.normalized != candidate.normalized:
                    raise ValueError("unverified chord candidate")
                if candidate.normalized in seen:
                    raise ValueError("duplicate normalized chord candidate")
                seen.add(candidate.normalized)
                alternatives.append(
                    TextAlternative(text=candidate.normalized, prob_bp=candidate.mass_bp)
                )
            alternatives.sort(key=lambda a: (-a.prob_bp, a.text))
            if sum(a.prob_bp for a in alternatives) > 10000:
                raise ValueError("candidate mass exceeds one")
            if observation.chord is None:
                diagnostics.append(f"{identity}: harmonic interpretation not provided")
            else:
                parsed = grammar.parse(text)
                assert parsed is not None
                if (
                    observation.chord.normalized != parsed.normalized
                    or observation.chord.kind_text != parsed.kind_text
                ):
                    raise ValueError(
                        "chord structure must preserve observed kind text and normal form"
                    )
        elif observation.candidates:
            raise ValueError("chord candidates require chord role")
        if observation.syllables and observation.role != "lyric":
            raise ValueError("syllables require lyric role")
        x, y, w, h = observation.region.box
        for syllable in observation.syllables:
            sx, sy, sw, sh = syllable.box
            if not (x <= sx and y <= sy and sx + sw <= x + w and sy + sh <= y + h):
                raise ValueError("syllable evidence box must lie inside text region")
        items.append(
            TextItem(
                text_id=identity,
                page_index=page_index,
                box_processed=observation.region.box,
                polygon=observation.region.polygon,
                role=observation.role,
                role_probs=observation.role_probs,
                text=text,
                alternatives=alternatives,
                confidence_bp=observation.confidence_bp,
                staff_link=observation.staff_link,
                syllables=list(observation.syllables) or None,
                chord=observation.chord,
            )
        )
    diagnostics.append("OCR scores are uncalibrated; role and staff link are supplied upstream")
    return TextResult(
        TextIR(schema="clavis-ir-0.1.1", id=f"pg{page_index}", items=items), tuple(diagnostics)
    )
