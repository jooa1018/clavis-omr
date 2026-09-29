import pytest

from eval.integrity.hardcode_scan import scan_source


@pytest.mark.parametrize(
    "condition",
    [
        "image.width == 1170",
        "2532 == image.height",
        "image.shape[0] != 3",
        "1 < image.shape[1] <= 2532",
        "image.width * image.height == 2048",
        "image.shape[0] in {1170, 2532}",
        "image.shape == (32, 32)",
        "image.height == -2",
        "pixel_count > 42",
        "image.shape[1] == 4",
    ],
)
def test_spatial_literals_positive(condition: str) -> None:
    for body in ("pass", "raise ValueError()"):
        assert "H3" in {x.rule for x in scan_source(f"if {condition}: {body}", "eval/example.py")}


@pytest.mark.parametrize(
    "condition",
    [
        "image.width == 0",
        "image.height <= 1",
        "1 >= image.shape[0]",
        "0 < image.shape[0] * image.shape[1] <= budget",
        "image.ndim in {2, 3}",
        "len(image.shape) not in (2, 3)",
        "image.shape[2] in {1, 3, 4}",
        "image.shape[-1] == 4",
        "image.channels in (1, 3, 4)",
        "image.width == expected",
        "labels.boxes.shape[1] != 4",
        "points.shape[-1:] != (2,)",
    ],
)
def test_format_literals_negative(condition: str) -> None:
    for body in ("pass", "raise ValueError()"):
        assert not scan_source(f"if {condition}: {body}", "eval/example.py")
