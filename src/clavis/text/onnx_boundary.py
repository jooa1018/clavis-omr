"""Offline, hash-verified CPU session boundary; no model acquisition or preprocessing."""

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from string import hexdigits
from typing import Protocol


class CpuSession(Protocol):
    """The subset of ONNX Runtime used by the text boundary."""

    def get_providers(self) -> list[str]: ...

    def run(self, output_names: list[str], input_feed: dict[str, object]) -> list[object]: ...


SessionFactory = Callable[[bytes, int], CpuSession]


@dataclass(frozen=True)
class VerifiedCpuModel:
    """Only instantiate through load(); the factory receives verified bytes, never a path."""

    session: CpuSession
    digest: str

    @classmethod
    def load(
        cls,
        path: Path,
        expected_sha256: str,
        *,
        max_bytes: int,
        threads: int,
        factory: SessionFactory,
    ) -> "VerifiedCpuModel":
        """Load one manifest-pinned artifact with an injected CPU session factory.

        The host owns ONNX Runtime installation and sets intra-op threads to the
        supplied count, inter-op threads to one, and sequential execution. No
        constructor defaults choose a model, dictionary, or preprocessing profile.
        """
        if (
            len(expected_sha256) != sha256().digest_size * 2
            or expected_sha256 != expected_sha256.lower()
            or any(c not in hexdigits for c in expected_sha256)
        ):
            raise ValueError("expected a lowercase SHA-256 digest")
        if type(max_bytes) is not int or max_bytes <= 0:
            raise ValueError("max_bytes must be a positive integer")
        if type(threads) is not int or threads not in (1, 4):
            raise ValueError("this boundary supports determinism profiles 1 and 4")
        with path.open("rb") as handle:
            blob = handle.read(max_bytes + 1)
        if not blob or len(blob) > max_bytes:
            raise ValueError("model is empty or exceeds the artifact byte budget")
        if sha256(blob).hexdigest() != expected_sha256:
            raise ValueError("model digest mismatch")
        session = factory(blob, threads)
        if session.get_providers() != ["CPUExecutionProvider"]:
            raise ValueError("text models require the CPU execution provider exclusively")
        return cls(session, expected_sha256)

    def run(self, output_name: str, inputs: dict[str, object]) -> object:
        """Return one raw detector map or recognition tensor, not an accepted chord."""
        if not output_name or not inputs or any(not key for key in inputs):
            raise ValueError("explicit output and input names are required")
        if self.session.get_providers() != ["CPUExecutionProvider"]:
            raise ValueError("session providers changed after verification")
        outputs = self.session.run([output_name], inputs)
        if len(outputs) != 1:
            raise ValueError("expected exactly one named model output")
        return outputs[0]
