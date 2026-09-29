"""ADR-011: sampled-band rejection, capped uniform draws and accountable batches."""

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
import yaml

from tests.degrade.test_ops import fixture
from training.degrade.presets import run_preset
from training.degrade.sampling import SampleRejected, SamplingStats, draw_interline


def catalog():
    return yaml.safe_load(Path("configs/degrade/presets.yaml").read_text(encoding="utf-8"))


def distribution():
    return catalog()["definitions"]["resolution"]["target_interline"]["interline_distribution"]


@pytest.mark.parametrize(
    "source,band,upper", [(80, 3, 40), (28, 3, 28), (24, 3, 24), (20, 2, 20), (8, 0, 8)]
)
def test_cap_and_no_upscale(source, band, upper):
    config = distribution()
    config["weights"] = [int(i == band) for i in range(4)]
    rng = np.random.default_rng(0)
    draws = [draw_interline(rng, source, config)["target_interline_px"] for _ in range(100)]
    assert min(draws) >= config["bands"][band][0]
    assert max(draws) <= upper <= source


def test_select_band_before_rejection_and_never_redraw():
    config = distribution()
    stats = SamplingStats(0.01)
    rng = np.random.default_rng(42)
    oracle = np.random.default_rng(42)
    for _ in range(1000):
        index = int(oracle.choice(4, p=config["weights"]))
        if index == 3:
            with pytest.raises(SampleRejected) as caught:
                draw_interline(rng, 20, config, stats)
            assert caught.value.record["band_index"] == index
        else:
            upper = min(config["bands"][index][1], 20)
            expected = oracle.uniform(config["bands"][index][0], upper)
            assert draw_interline(rng, 20, config, stats)["target_interline_px"] == expected
    assert rng.bit_generator.state == oracle.bit_generator.state
    summary = stats.summary()
    assert summary["attempted"] == 1000
    assert summary["rejected"] == summary["by_band"]["3"]["attempted"] > 0
    assert summary["w2_report_required"]
    json.dumps(summary)


@pytest.mark.parametrize("source", [28, 40, 80])
def test_w2_minimum_source_has_no_sampling_rejection(source):
    stats = SamplingStats(0.01)
    rng = np.random.default_rng(13)
    config = distribution()
    for _ in range(1000):
        draw_interline(rng, source, config, stats)
    assert stats.summary()["rejection_rate"] == 0
    assert not stats.summary()["w2_report_required"]


def test_empty_stats_and_rejection_trace():
    stats = SamplingStats(0.01)
    assert stats.summary()["rejection_rate"] is None
    image, labels = fixture()
    config = catalog()
    config = deepcopy(config)
    config["presets"]["scan-300"]["operations"][0]["target_interline"]["interline_distribution"][
        "bands"
    ] = [[25, 28]]
    config["presets"]["scan-300"]["operations"][0]["target_interline"]["interline_distribution"][
        "weights"
    ] = [1]
    with pytest.raises(SampleRejected) as caught:
        run_preset(image, labels, np.random.default_rng(1), config, "scan-300", stats)
    assert caught.value.record["preset"] == "scan-300"
    assert caught.value.record["sampling_stats"]["rejected"] == 1
    assert caught.value.record["render_interline_px"] == 24


@pytest.mark.parametrize("source", [0, -1, float("nan"), float("inf")])
def test_invalid_source_does_not_count_as_sample_rejection(source):
    stats = SamplingStats(0.01)
    with pytest.raises(ValueError, match="Invalid"):
        draw_interline(np.random.default_rng(0), source, distribution(), stats)
    assert stats.attempted == 0
