"""Bounded raster decoding and explicit original-to-processed EXIF frames."""

import hashlib
import io
import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import numpy as np
from numpy.typing import NDArray
from PIL import ExifTags, Image, UnidentifiedImageError

from clavis.contracts.geometry import Homography, ImageCoordinateFrame, Original, PageInput, Source

Gray = NDArray[np.uint8]


@dataclass(frozen=True)
class DecodeLimits:
    """Operational limits supplied from the pending ingest registry."""

    max_bytes: int
    max_pixels: int
    max_pages: int
    max_total_pixels: int
    max_compression_ratio: float

    def __post_init__(self) -> None:
        if min(self.max_bytes, self.max_pixels, self.max_pages, self.max_total_pixels) <= 0:
            raise ValueError("Decode limits must be positive")
        if not np.isfinite(self.max_compression_ratio) or self.max_compression_ratio <= 0:
            raise ValueError("Compression limit must be finite and positive")


def load_limits(directory: Path | None = None) -> DecodeLimits:
    directory = directory or Path(__file__).resolve().parents[3] / "configs" / "ingest"
    entries = json.loads((directory / "limits.yaml").read_text(encoding="utf-8"))
    return DecodeLimits(**{row["name"]: row["value"] for row in entries})


@dataclass(frozen=True)
class DecodedPage:
    page_input: PageInput
    original: Gray
    processed: Gray


class InputError(ValueError):
    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code


def image_format(data: bytes) -> tuple[str, str]:
    """Protocol signatures, not recognition rules or filename guesses."""
    for prefix, name, mime in (
        (b"\x89PNG\r\n\x1a\n", "PNG", "image/png"),
        (b"\xff\xd8\xff", "JPEG", "image/jpeg"),
        (b"II\x2a\x00", "TIFF", "image/tiff"),
        (b"MM\x00\x2a", "TIFF", "image/tiff"),
        (b"II\x2b\x00", "TIFF", "image/tiff"),
        (b"MM\x00\x2b", "TIFF", "image/tiff"),
        (b"BM", "BMP", "image/bmp"),
    ):
        if data.startswith(prefix):
            return name, mime
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "WEBP", "image/webp"
    raise InputError("CLAVIS_INPUT_UNSUPPORTED", "Unrecognized image signature")


def luminance(image: Image.Image) -> Gray:
    """Normalize precision and composite alpha over white before luminance."""
    if image.mode.startswith("I;16") or image.mode == "I":
        integers = np.asarray(image, dtype=np.int64)
        maximum = np.iinfo(np.uint16).max
        if np.any(integers < 0) or np.any(integers > maximum):
            raise InputError("CLAVIS_INPUT_UNSUPPORTED", "Integer pixels outside uint16")
        return np.rint(integers * np.iinfo(np.uint8).max / maximum).astype(np.uint8)
    if image.mode == "F":
        raise InputError("CLAVIS_INPUT_UNSUPPORTED", "Floating-point image normalization undefined")
    rgba = image.convert("RGBA")
    white = Image.new("RGBA", rgba.size, "white")
    composited = Image.alpha_composite(white, rgba)
    return np.asarray(composited.convert("L"), dtype=np.uint8).copy()


def orient(original: Gray, orientation: int) -> tuple[Gray, NDArray[np.float64]]:
    """EXIF 1..8 transforms use integer pixel centres, including reflections."""
    height, width = original.shape
    w, h = float(width - 1), float(height - 1)
    mappings = {
        1: (None, [[1, 0, 0], [0, 1, 0], [0, 0, 1]]),
        2: (Image.Transpose.FLIP_LEFT_RIGHT, [[-1, 0, w], [0, 1, 0], [0, 0, 1]]),
        3: (Image.Transpose.ROTATE_180, [[-1, 0, w], [0, -1, h], [0, 0, 1]]),
        4: (Image.Transpose.FLIP_TOP_BOTTOM, [[1, 0, 0], [0, -1, h], [0, 0, 1]]),
        5: (Image.Transpose.TRANSPOSE, [[0, 1, 0], [1, 0, 0], [0, 0, 1]]),
        6: (Image.Transpose.ROTATE_270, [[0, -1, h], [1, 0, 0], [0, 0, 1]]),
        7: (Image.Transpose.TRANSVERSE, [[0, -1, h], [-1, 0, w], [0, 0, 1]]),
        8: (Image.Transpose.ROTATE_90, [[0, 1, 0], [-1, 0, w], [0, 0, 1]]),
    }
    if orientation not in mappings:
        raise InputError("CLAVIS_INPUT_CORRUPT", "Invalid EXIF orientation")
    method, matrix = mappings[orientation]
    source = Image.fromarray(original)
    result = source if method is None else source.transpose(method)
    return np.array(result, dtype=np.uint8), np.asarray(matrix, dtype=np.float64)


def decode_images(data: bytes, limits: DecodeLimits) -> tuple[DecodedPage, ...]:
    """Decode all supported pages with size checks before allocating pixels."""
    if len(data) > limits.max_bytes:
        raise InputError("CLAVIS_INPUT_TOO_LARGE", "Encoded bytes exceed configured limit")
    expected, mime = image_format(data)
    digest = hashlib.sha256(data).hexdigest()
    try:
        with warnings.catch_warnings(), Image.open(io.BytesIO(data)) as image:
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            if image.format != expected:
                raise InputError("CLAVIS_INPUT_CORRUPT", "Signature/decoder mismatch")
            frames = getattr(image, "n_frames", 1)
            if frames > limits.max_pages:
                raise InputError("CLAVIS_INPUT_TOO_LARGE", "Page count exceeds configured limit")
            if expected != "TIFF" and frames > 1:
                raise InputError("CLAVIS_INPUT_UNSUPPORTED", "Animated images are unsupported")
            total = 0
            # Check every frame before decoding the first; heterogeneous TIFF sizes matter.
            for index in range(frames):
                image.seek(index)
                pixels = image.width * image.height
                total += pixels
                if pixels > limits.max_pixels or total > limits.max_total_pixels:
                    raise InputError(
                        "CLAVIS_INPUT_TOO_LARGE", "Decoded pixels exceed configured limit"
                    )
            if total / max(len(data), 1) > limits.max_compression_ratio:
                raise InputError("CLAVIS_INPUT_TOO_LARGE", "Decoded/encoded ratio exceeds limit")
            pages = []
            for index in range(frames):
                image.seek(index)
                orientation = image.getexif().get(ExifTags.Base.Orientation, 1)
                original = luminance(image)
                if expected == "TIFF":
                    # Pillow 11.2 applies TIFF orientation during load; recover stored pixels first.
                    inverse = {6: 8, 8: 6}.get(orientation, orientation)
                    original, _ = orient(original, inverse)
                processed, matrix = orient(original, orientation)
                original_digest = hashlib.sha256(original.tobytes()).hexdigest()
                processed_digest = hashlib.sha256(processed.tobytes()).hexdigest()
                page_id = f"pg{index}"
                original_id, processed_id = f"{page_id}-original", f"{page_id}-processed"
                frames_ir = [
                    ImageCoordinateFrame(
                        id=frame_id,
                        page_index=index,
                        coordinate_space=cast(
                            Literal["original-pixels", "processed-pixels"], space
                        ),
                        width_pixels=pixels.shape[1],
                        height_pixels=pixels.shape[0],
                        image_digest=sha,
                    )
                    for frame_id, space, pixels, sha in (
                        (original_id, "original-pixels", original, original_digest),
                        (processed_id, "processed-pixels", processed, processed_digest),
                    )
                ]
                ir = PageInput(
                    schema="clavis-ir-0.1.1",
                    id=page_id,
                    page_index=index,
                    source=Source(kind="image", mime=mime, bytes_sha256=digest),
                    original=Original(
                        width=original.shape[1],
                        height=original.shape[0],
                        pixels_sha256=original_digest,
                    ),
                    frames=frames_ir,
                    transforms=[
                        Homography(
                            id=f"{page_id}-normalize",
                            from_frame_id=original_id,
                            to_frame_id=processed_id,
                            kind="homography",
                            matrix=matrix.reshape(-1).tolist(),
                        )
                    ],
                )
                pages.append(DecodedPage(ir, original, processed))
            return tuple(pages)
    except InputError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, EOFError, ValueError, TypeError) as error:
        raise InputError("CLAVIS_INPUT_CORRUPT", "Image decoder rejected the content") from error
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise InputError(
            "CLAVIS_INPUT_TOO_LARGE", "Decoder decompression limit exceeded"
        ) from error
