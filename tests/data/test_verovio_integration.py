import json
import subprocess
import sys

import pytest

from training.data.smoke import CONFIG, ROOT
from training.data.smoke_inputs import score
from training.data.staff_svg import extract


@pytest.mark.parametrize("font", ["Leipzig", "Bravura", "Leland"])
def test_actual_renderer_preserves_staff_provenance(font: str) -> None:
    xml = score("train-integration", fifths=-2, beats=3, staves=2)
    result = subprocess.run(
        [sys.executable, "-m", "training.data.verovio_worker", str(CONFIG), font],
        cwd=ROOT,
        input=xml.encode(),
        capture_output=True,
        timeout=60,
        check=True,
    )
    rendered = json.loads(result.stdout)
    repeated = subprocess.run(
        [sys.executable, "-m", "training.data.verovio_worker", str(CONFIG), font],
        cwd=ROOT,
        input=xml.encode(),
        capture_output=True,
        timeout=60,
        check=True,
    )
    assert json.loads(repeated.stdout)["pages"] == rendered["pages"]
    assert rendered["version"].startswith("6.3.0")
    assert 0 < rendered["peak_rss_bytes"] < 3_000_000_000
    assert len(rendered["pages"]) == 1
    labels, overlay = extract(rendered["pages"][0], max_bytes=8_388_608)
    assert len(labels) == 8
    assert {label.staff_number for label in labels} == {"1", "2"}
    assert len({label.system_id for label in labels}) == 2
    assert 'style="stroke:#e00078"' in overlay
