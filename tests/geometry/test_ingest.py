"""Synthetic raster boundary tests, independent of any score or private image."""

import dataclasses
import hashlib
import io

import cv2
import jsonschema
import numpy as np
import pytest
from PIL import Image

from clavis.geometry.barlines import propose_barlines
from clavis.ingest.decode import InputError, decode_images, load_limits, luminance, orient


def encoded(image, fmt, **kwargs):
    stream = io.BytesIO()
    image.save(stream, format=fmt, **kwargs)
    return stream.getvalue()


@pytest.mark.parametrize("fmt", ["PNG", "JPEG", "WEBP", "TIFF", "BMP"])
def test_formats_frames_and_digest(fmt):
    source = Image.fromarray(np.arange(600, dtype=np.uint8).reshape(20, 30))
    data = encoded(source, fmt)
    first = decode_images(data, load_limits())[0]
    second = decode_images(data, load_limits())[0]
    assert first.page_input.model_dump_json() == second.page_input.model_dump_json()
    assert first.processed.tobytes() == second.processed.tobytes()
    assert first.page_input.source.bytes_sha256 == hashlib.sha256(data).hexdigest()
    assert first.page_input.original.pixels_sha256 == hashlib.sha256(first.original).hexdigest()
    assert first.page_input.model_dump(by_alias=True)["schema"] == "clavis-ir-0.1.1"
    jsonschema.validate(
        first.page_input.model_dump(mode="json", by_alias=True),
        first.page_input.model_json_schema(by_alias=True),
    )


@pytest.mark.parametrize("orientation", range(1, 9))
@pytest.mark.parametrize(
    "fmt,compression", [("PNG", None), ("TIFF", "raw"), ("TIFF", "tiff_deflate")]
)
def test_exif_applied_once_and_exact_pixel_mapping(orientation, fmt, compression):
    original = np.arange(35, dtype=np.uint8).reshape(5, 7)
    exif = Image.Exif()
    exif[274] = orientation
    kwargs = {"exif": exif}
    if compression:
        kwargs["compression"] = compression
    page = decode_images(encoded(Image.fromarray(original), fmt, **kwargs), load_limits())[0]
    np.testing.assert_array_equal(page.original, original)
    matrix = np.array(page.page_input.transforms[0].matrix).reshape(3, 3)
    for y, x in np.ndindex(original.shape):
        u, v, _ = matrix @ [x, y, 1]
        assert page.processed[int(v), int(u)] == original[y, x]
    np.testing.assert_allclose(np.linalg.inv(matrix) @ matrix, np.eye(3))


def test_precision_alpha_palette():
    high = Image.fromarray(np.array([[0, 32768, 65535]], np.uint16))
    assert luminance(high).tolist() == [[0, 128, 255]]
    rgba = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
    rgba.putpixel((1, 0), (0, 0, 0, 255))
    assert luminance(rgba).tolist() == [[255, 0]]
    palette = rgba.convert("P")
    np.testing.assert_array_equal(luminance(palette), luminance(rgba))
    with pytest.raises(InputError):
        luminance(Image.fromarray(np.array([[-1]], np.int32)))
    with pytest.raises(InputError):
        luminance(Image.fromarray(np.ones((2, 2), np.float32)))


def test_limits_all_frames_before_return():
    a = Image.new("L", (8, 9))
    b = Image.new("L", (20, 30))
    data = encoded(a, "TIFF", save_all=True, append_images=[b])
    pages = decode_images(data, load_limits())
    assert [p.original.shape for p in pages] == [(9, 8), (30, 20)]
    for values in (
        {"max_pages": 1},
        {"max_pixels": 100},
        {"max_total_pixels": 650},
        {"max_bytes": 10},
        {"max_compression_ratio": 0.01},
    ):
        with pytest.raises(InputError) as error:
            decode_images(data, dataclasses.replace(load_limits(), **values))
        assert error.value.code == "CLAVIS_INPUT_TOO_LARGE"
    with pytest.raises(ValueError):
        dataclasses.replace(load_limits(), max_pages=0)


def test_bad_input_and_orientation():
    for data in (b"", b"GIF89a", b"\x89PNG\r\n\x1a\ninvalid"):
        with pytest.raises(InputError):
            decode_images(data, load_limits())
    with pytest.raises(InputError):
        orient(np.zeros((2, 2), np.uint8), 9)


def test_determinism_one_four_threads_three_runs():
    image = np.full((240, 320), 255, np.uint8)
    image[96:161, 60] = 0
    data = encoded(Image.fromarray(image), "PNG")
    before = cv2.getNumThreads()
    results = []
    try:
        for threads in (1, 4):
            cv2.setNumThreads(threads)
            for _ in range(3):
                page = decode_images(data, load_limits())[0]
                results.append(
                    (
                        page.page_input.model_dump_json(),
                        page.processed.tobytes(),
                        propose_barlines(page.processed, 16, 6),
                    )
                )
    finally:
        cv2.setNumThreads(before)
    assert all(result == results[0] for result in results)
