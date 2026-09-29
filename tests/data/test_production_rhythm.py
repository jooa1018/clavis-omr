from fractions import Fraction
from pathlib import Path

import numpy as np
import pytest
import yaml

from training.data.production_rhythm import Value, catalog, fit, seeded


def test_pattern_catalog_follows_meter_groups_and_preserves_time() -> None:
    config = yaml.safe_load(Path("configs/data/leadgen-rhythm.yaml").read_text())
    config["mixed_patterns_per_grouping"] = 4
    for meter, groupings in config["groupings"].items():
        patterns = catalog(meter, config)
        legal = {tuple(Fraction(str(v)) for v in grouping) for grouping in groupings}
        assert patterns
        for pattern in patterns:
            assert tuple(sum((v.quarters for v in group), Fraction()) for group in pattern) in legal
        assert patterns == catalog(meter, config)
    assert Value("eighth", 2).quarters == Fraction(7, 8)


def test_empirical_fit_improves_marginal_and_keeps_raw_reference() -> None:
    config = yaml.safe_load(Path("configs/data/leadgen-rhythm.yaml").read_text())
    config["mixed_patterns_per_grouping"] = 4
    config["fit_iterations"] = 150
    target = {"note:quarter:dots=0": 900, "note:eighth:dots=0": 100}
    calibrated = fit("4/4", target, config)
    assert calibrated.empirical_counts == target
    assert sum(calibrated.probabilities) == pytest.approx(1)
    assert calibrated.fitted_note_probabilities["note:quarter:dots=0"] > 0.7
    assert calibrated.sample(seeded("train-repeat")) == calibrated.sample(seeded("train-repeat"))
    assert calibrated.sample(seeded("eval-w4-api")) in calibrated.patterns
    with pytest.raises(ValueError):
        fit("4/4", {}, config)
    with pytest.raises(ValueError):
        fit("4/4", {"note:quarter:dots=0": -1}, config)
    with pytest.raises(ValueError):
        fit("4/4", {"unsupported": 10}, config)
    with pytest.raises(ValueError):
        seeded("unknown")
    assert np.isfinite(calibrated.probabilities).all()
