"""Strict canonical UTF-8 LSTL text, CCR-0003 C2."""

import json
from collections.abc import Iterable
from unicodedata import is_normalized

from ..tokens import LSTLItem
from .automaton import ITEM, LSTLError, validate_sequence

ORDER: dict[str, tuple[str, ...]] = {
    "clef": ("sign", "courtesy"),
    "key": ("fifths", "cancel", "courtesy"),
    "time": ("beats", "beatType", "symbol", "courtesy"),
    "bar": ("style",),
    "note": (
        "dur",
        "dots",
        "pos",
        "head",
        "v",
        "acc",
        "accParen",
        "tie",
        "slur",
        "chord",
        "join",
        "grace",
        "tup3",
        "fermata",
        "stem",
        "beam",
    ),
    "rest": ("dur", "dots", "v", "join", "pos", "measureRest", "fermata", "tup3"),
    "mrest": ("count",),
    "ending": ("numbers", "mark"),
    "segno": (),
    "coda": (),
}
INTEGER = frozenset(
    ("dots", "pos", "v", "chord", "join", "fifths", "cancel", "beats", "beatType", "count")
)
BOOLEAN = frozenset(("accParen", "fermata", "measureRest", "courtesy"))


def _line(item: LSTLItem) -> str:
    data = item.model_dump(by_alias=True, exclude_none=True)
    parts: list[str] = [item.type]
    for key in ORDER[item.type]:
        if key not in data or (key == "dots" and data[key] == 0):
            continue
        value = data[key]
        if isinstance(value, bool):
            encoded = str(int(value))
        elif isinstance(value, list):
            encoded = json.dumps(value, separators=(",", ":"))
        else:
            encoded = str(value)
        parts.append(f"{key}={encoded}")
    return " ".join(parts)


def serialize(items: Iterable[LSTLItem]) -> bytes:
    sequence = list(items)
    validate_sequence(sequence)
    # Empty system has one LF, too. No empty item is introduced.
    return ("\n".join(_line(item) for item in sequence) + "\n").encode("utf-8")


def parse(payload: bytes | str) -> list[LSTLItem]:
    try:
        text = payload.decode("utf-8") if isinstance(payload, bytes) else payload
    except UnicodeDecodeError as exc:
        raise LSTLError("NONCANONICAL_TEXT") from exc
    if not is_normalized("NFC", text) or "\r" in text or not text.endswith("\n"):
        raise LSTLError("NONCANONICAL_TEXT")
    if text == "\n":
        return []
    result: list[LSTLItem] = []
    for line in text[:-1].split("\n"):
        parts = line.split(" ")
        kind = parts[0]
        if kind not in ORDER:
            raise LSTLError("UNKNOWN_ITEM")
        data: dict[str, object] = {"type": kind}
        for part in parts[1:]:
            key, sep, raw = part.partition("=")
            if not sep or key not in ORDER[kind] or key in data:
                raise LSTLError("UNKNOWN_OR_DUPLICATE_ATTRIBUTE")
            try:
                if key in INTEGER:
                    value: object = int(raw)
                elif key in BOOLEAN:
                    if raw not in ("0", "1"):
                        raise ValueError("boolean must be 0 or 1")
                    value = raw == "1"
                elif key == "numbers":
                    value = json.loads(raw)
                else:
                    value = raw
            except (ValueError, TypeError) as exc:
                raise LSTLError("INVALID_ATTRIBUTE") from exc
            data[key] = value
        if kind in ("note", "rest") and "dots" not in data:
            data["dots"] = 0
        item = ITEM.validate_python(data)
        if _line(item) != line:
            raise LSTLError("NONCANONICAL_TEXT")
        result.append(item)
    validate_sequence(result)
    return result
