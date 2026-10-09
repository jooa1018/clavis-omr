"""Validated requests for the local CPU queue (not an engine IR contract)."""

import hashlib
import json
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class JobSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["batch", "benchmark"] = "batch"
    module: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
    arguments: list[str] = Field(default_factory=list)
    cwd: str
    config: dict[str, Any]
    seed: int = Field(ge=0)
    data_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    git_sha: str = Field(pattern=r"^[0-9a-f]{40}$")
    threads: int = Field(default=8, ge=1, le=8)
    ram_bytes: int = Field(default=3_000_000_000, ge=1, le=3_000_000_000)
    wall_seconds: int = Field(default=14400, ge=1, le=14400)

    @model_validator(mode="after")
    def benchmark_threads(self) -> Self:
        if self.kind == "benchmark" and self.threads != 4:
            raise ValueError("benchmark jobs require exactly four compute threads")
        return self

    def digest(self) -> str:
        # Preserve pre-benchmark batch checkpoint digests.
        excluded = {"kind"} if self.kind == "batch" else set()
        return hashlib.sha256(self.model_dump_json(exclude=excluded).encode()).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        import os

        os.fsync(stream.fileno())
    temporary.replace(path)
