"""Canonical UTF-8 JSON, CONTRACTS 1/3.5 and CCR-0001 C4/C5."""

import json
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path

from pydantic import JsonValue

from .common import WireModel, nfc
from .outputs import ReviewHints
from .symbols import SymbolGraph


def _encode(value: JsonValue, places: int) -> str:
    if isinstance(value, str):
        return json.dumps(nfc(value), ensure_ascii=False)
    if isinstance(value, float):
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError("non-finite JSON value")
        with localcontext() as context:
            context.prec = max(
                28, len(number.as_tuple().digits) + abs(number.adjusted()) + places + 1
            )
            rounded = number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)
        if rounded == 0:
            rounded = abs(rounded)
        return format(rounded, f".{places}f")
    if isinstance(value, list):
        return "[" + ",".join(_encode(v, places) for v in value) + "]"
    if isinstance(value, dict):
        return (
            "{"
            + ",".join(_encode(k, places) + ":" + _encode(value[k], places) for k in sorted(value))
            + "}"
        )
    return json.dumps(value, allow_nan=False)


def canonical_json(model: WireModel) -> bytes:
    """Preserve semantic array order; emit every float at the approved precision."""
    data = model.model_dump(mode="json", by_alias=True, exclude_none=True)
    # The hints envelope explicitly requires null when no threshold is frozen.
    if isinstance(model, ReviewHints):
        data["thresholdArtifactDigest"] = model.threshold_artifact_digest
    return (_encode(data, 2 if isinstance(model, SymbolGraph) else 3) + "\n").encode("utf-8")


def write_json(path: Path, model: WireModel) -> None:
    path.write_bytes(canonical_json(model))
