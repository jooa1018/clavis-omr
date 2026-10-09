import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from pathlib import Path

import pytest

from clavis.text.ctc import CtcLimits, greedy_observation
from clavis.text.onnx_boundary import VerifiedCpuModel

ROOT = Path(__file__).resolve().parents[2]
VALUES = {
    entry["name"]: entry["value"]
    for entry in json.loads((ROOT / "configs/text/constants.yaml").read_text(encoding="utf-8"))
}
LIMITS = CtcLimits(
    *(VALUES[f"text.ctc.{key}"] for key in ("max_frames", "max_classes", "max_cells"))
)


class FakeSession:
    def __init__(self, providers=None, outputs=None):
        self.providers = providers if providers is not None else ["CPUExecutionProvider"]
        self.outputs = outputs if outputs is not None else [[[0, 1], [1, 0], [0, 1]]]
        self.calls = []

    def get_providers(self):
        return self.providers

    def run(self, names, inputs):
        self.calls.append((names, inputs))
        return self.outputs


def decode(rows, alphabet=("", "a"), **kwargs):
    return greedy_observation(rows, alphabet, blank_index=0, limits=LIMITS, enabled=True, **kwargs)


def test_repeated_characters_blank_and_frame_evidence():
    result = decode([[0, 1], [0, 1], [1, 0], [0, 1]])
    assert result.text == "aa"
    assert result.token_frames == (0, 3)
    assert result.token_prob_bp == (10000, 10000)
    assert result.tokens == ("a", "a")


def test_decoder_bytes_identical_with_one_and_four_workers():
    def run(_):
        result = decode([[0.1, 0.9], [1, 0], [0.1, 0.9]])
        return json.dumps(asdict(result), sort_keys=True).encode("utf-8")

    outputs = []
    for workers in (1, 4):
        with ThreadPoolExecutor(max_workers=workers) as pool:
            outputs.extend(pool.map(run, range(3)))
    assert len(set(outputs)) == 1


def test_quantize_before_argmax_and_break_tie_by_index():
    result = decode([[0.49999, 0.50001]])
    assert result.text == ""


def test_nonzero_blank_and_nfc_text():
    result = greedy_observation(
        [[1, 0, 0], [0, 1, 0]],
        ("ᄀ", "ᅡ", ""),
        blank_index=2,
        limits=LIMITS,
        enabled=True,
    )
    assert result.text == "가"
    assert result.tokens == ("ᄀ", "ᅡ")  # Tokens are not claimed to be glyphs.


def test_empty_and_disabled():
    assert decode([]).text == ""
    assert decode([[1, 0]]).token_prob_bp == ()
    assert greedy_observation([], [], blank_index=0, limits=LIMITS, enabled=False) is None


@pytest.mark.parametrize("row", [[float("nan"), 1], [float("inf"), 0], [-1, 2], [0, 2], [0, 0]])
def test_reject_invalid_probabilities(row):
    with pytest.raises(ValueError):
        decode([row])


@pytest.mark.parametrize(
    ("alphabet", "blank"),
    [
        ([], 0),
        (["", "a"], -1),
        (["", "a"], 2),
        (["", "a"], True),
        (["a", "a"], 0),
        (["", "e\u0301"], 0),
        (["x", ""], 0),
    ],
)
def test_reject_bad_alphabet(alphabet, blank):
    with pytest.raises(ValueError):
        greedy_observation([], alphabet, blank_index=blank, limits=LIMITS, enabled=True)


@pytest.mark.parametrize("limits", [(1, 2, 4), (2, 1, 4), (2, 2, 3)])
def test_fail_closed_on_resource_limits(limits):
    with pytest.raises(ValueError):
        greedy_observation(
            [[1, 0], [0, 1]],
            ["", "a"],
            blank_index=0,
            limits=CtcLimits(*limits),
            enabled=True,
        )


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_invalid_limits(value):
    with pytest.raises(ValueError):
        CtcLimits(value, 2, 3)


def test_reject_dictionary_dimension_mismatch():
    with pytest.raises(ValueError, match="classes"):
        decode([[1]])


def model(tmp_path, factory, **kwargs):
    path = tmp_path / "synthetic-artifact"
    path.write_bytes(b"synthetic test artifact; not ONNX or pretrained weights")
    options = {"max_bytes": VALUES["text.onnx.max_model_bytes"], "threads": 1, **kwargs}
    digest = options.pop("digest", hashlib.sha256(path.read_bytes()).hexdigest())
    return VerifiedCpuModel.load(path, digest, factory=factory, **options)


def test_verified_bytes_and_thread_profiles(tmp_path):
    results = []
    for threads in (1, 4):
        for _ in range(3):
            session = FakeSession()

            def factory(blob, count, expected=threads, result=session):
                assert count == expected
                assert blob.startswith(b"synthetic test artifact")
                return result

            loaded = model(tmp_path, factory, threads=threads)
            tensor = loaded.run("ctc", {"x": "synthetic input"})
            assert session.calls == [(["ctc"], {"x": "synthetic input"})]
            results.append(decode(tensor))
    assert all(result == results[0] for result in results)


@pytest.mark.parametrize(
    "options",
    [
        {"digest": "bad"},
        {"digest": "z" * 64},
        {"digest": "a" * 64},
        {"max_bytes": 1},
        {"max_bytes": 0},
        {"max_bytes": True},
        {"threads": 2},
        {"threads": True},
    ],
)
def test_reject_before_factory(tmp_path, options):
    def forbidden_factory(*args):
        pytest.fail("invalid artifact must not reach the session factory")

    with pytest.raises(ValueError):
        model(tmp_path, forbidden_factory, **options)


def test_empty_artifact(tmp_path):
    path = tmp_path / "empty"
    path.touch()
    with pytest.raises(ValueError, match="empty"):
        VerifiedCpuModel.load(
            path,
            hashlib.sha256(b"").hexdigest(),
            max_bytes=1,
            threads=1,
            factory=lambda *_: pytest.fail("empty artifact"),
        )


@pytest.mark.parametrize(
    "providers", [[], ["CUDAExecutionProvider"], ["CPUExecutionProvider", "CUDAExecutionProvider"]]
)
def test_reject_non_cpu_provider(tmp_path, providers):
    with pytest.raises(ValueError, match="CPU"):
        model(tmp_path, lambda *_: FakeSession(providers=providers))


def test_recheck_provider_and_reject_output_cardinality(tmp_path):
    session = FakeSession()
    loaded = model(tmp_path, lambda *_: session)
    session.providers = []
    with pytest.raises(ValueError, match="providers changed"):
        loaded.run("ctc", {"x": 1})
    session.providers = ["CPUExecutionProvider"]
    session.outputs = []
    with pytest.raises(ValueError, match="exactly one"):
        loaded.run("ctc", {"x": 1})


@pytest.mark.parametrize(("name", "inputs"), [("", {"x": 1}), ("y", {}), ("y", {"": 1})])
def test_require_explicit_tensor_names(tmp_path, name, inputs):
    with pytest.raises(ValueError, match="explicit"):
        model(tmp_path, lambda *_: FakeSession()).run(name, inputs)
