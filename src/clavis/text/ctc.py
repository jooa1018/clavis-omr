"""Raw CTC observations, not grammar-constrained chord recognition.

CTC collapse: Graves et al. (2006), https://doi.org/10.1145/1143844.1143891.
Score quantization/ties: CONTRACTS 11. No language model or text correction.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from math import fsum, isfinite
from unicodedata import is_normalized, normalize

BASIS_POINTS = 10_000  # CONTRACTS 1: exact probability unit conversion, not a threshold.


@dataclass(frozen=True)
class CtcObservation:
    """Token times are CTC frame indices, never inferred glyph bounding boxes."""

    text: str
    tokens: tuple[str, ...]
    token_frames: tuple[int, ...]
    token_prob_bp: tuple[int, ...]


@dataclass(frozen=True)
class CtcLimits:
    """Resource limits supplied from configs/text/constants.yaml."""

    max_frames: int
    max_classes: int
    max_cells: int

    def __post_init__(self) -> None:
        for value in (self.max_frames, self.max_classes, self.max_cells):
            if type(value) is not int or value <= 0:
                raise ValueError("CTC limits must be positive integers")


def greedy_observation(
    probabilities: Sequence[Sequence[float]],
    alphabet: Sequence[str],
    *,
    blank_index: int,
    limits: CtcLimits,
    enabled: bool,
) -> CtcObservation | None:
    """Decode normalized CTC probabilities; disabling TEXT-CTC-001 abstains.

    Alphabet order must come from the exact model export, including the blank.
    Scores are raw per-token values; neither a calibrated confidence nor a
    sequence posterior. A future chord decoder must consume the full tensor.
    """
    if not enabled:
        return None
    if (
        not alphabet
        or len(alphabet) > limits.max_classes
        or type(blank_index) is not int
        or not 0 <= blank_index < len(alphabet)
    ):
        raise ValueError("invalid alphabet size or blank index")
    if len(set(alphabet)) != len(alphabet):
        raise ValueError("alphabet entries must be unique")
    if any(not is_normalized("NFC", token) for token in alphabet):
        raise ValueError("alphabet entries must be NFC")
    if any(not token for i, token in enumerate(alphabet) if i != blank_index):
        raise ValueError("nonblank alphabet entries must be nonempty")
    if (
        len(probabilities) > limits.max_frames
        or len(probabilities) * len(alphabet) > limits.max_cells
    ):
        raise ValueError("CTC tensor exceeds the resource budget")

    tokens: list[str] = []
    frames: list[int] = []
    scores: list[int] = []
    previous = blank_index
    for frame, row in enumerate(probabilities):
        if len(row) != len(alphabet):
            raise ValueError("CTC classes do not match the model alphabet")
        if any(not isfinite(p) or not 0 <= p <= 1 for p in row):
            raise ValueError("CTC probabilities must be finite and in [0, 1]")
        if abs(fsum(row) - 1) > 1 / BASIS_POINTS:
            raise ValueError("expected normalized probabilities, not logits")
        quantized = tuple(round(p * BASIS_POINTS) for p in row)
        # max preserves the first class index on quantized ties (CONTRACTS 11).
        selected = max(range(len(alphabet)), key=quantized.__getitem__)
        if selected != blank_index and selected != previous:
            tokens.append(alphabet[selected])
            frames.append(frame)
            scores.append(quantized[selected])
        previous = selected
    return CtcObservation(
        normalize("NFC", "".join(tokens)), tuple(tokens), tuple(frames), tuple(scores)
    )
