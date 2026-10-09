"""CCR-0003 column grammar. State contains no geometry or external column context."""

import copy
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from pydantic import TypeAdapter

from ..tokens import LSTLItem, NoteItem, RestItem

ITEM: TypeAdapter[LSTLItem] = TypeAdapter(LSTLItem)


class LSTLError(ValueError):
    """Stable machine-readable code, without input data in the message."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class State:
    previous: LSTLItem | None = None
    column: int = -1
    after_bar: bool = False
    courtesy: bool = False


def advance(state: State, item: LSTLItem) -> State:
    # Revalidate even model_construct/model_copy values at this public boundary.
    item = ITEM.validate_python(item.model_dump(by_alias=True, exclude_none=True))
    previous = state.previous
    courtesy = getattr(item, "courtesy", None) is True
    if state.courtesy and not courtesy:
        raise LSTLError("COURTESY_MUST_END_SYSTEM")
    if courtesy and not state.after_bar:
        raise LSTLError("COURTESY_REQUIRES_FINAL_BAR")
    if item.type == "ending" and (previous is None or previous.type != "bar"):
        raise LSTLError("ENDING_REQUIRES_BAR")
    chord = isinstance(item, NoteItem) and item.chord == 1
    join = isinstance(item, (NoteItem, RestItem)) and item.join == 1
    if chord and isinstance(item, NoteItem):
        if not isinstance(previous, NoteItem):
            raise LSTLError("CHORD_REQUIRES_NOTE")
        if (item.v, item.dur, item.dots, item.grace) != (
            previous.v,
            previous.dur,
            previous.dots,
            previous.grace,
        ):
            raise LSTLError("CHORD_ATTRIBUTES_MISMATCH")
        if item.pos < previous.pos:
            raise LSTLError("CHORD_POSITION_ORDER")
    if join and isinstance(item, (NoteItem, RestItem)):
        if not isinstance(previous, (NoteItem, RestItem)) or (
            isinstance(previous, NoteItem) and previous.grace is not None
        ):
            raise LSTLError("JOIN_REQUIRES_TIME_COLUMN")
        if item.v <= previous.v:
            raise LSTLError("JOIN_VOICE_ORDER")
    after_bar = state.after_bar
    if item.type == "bar":
        after_bar = True
    elif item.type in ("note", "rest", "mrest"):
        after_bar = False
    return State(
        previous=item,
        column=state.column + (0 if chord or join else 1),
        after_bar=after_bar,
        courtesy=state.courtesy or courtesy,
    )


def validate_sequence(items: Iterable[LSTLItem]) -> State:
    state = State()
    for item in items:
        state = advance(state, item)
    return state


def allowed(state: State) -> list[dict[str, Any]]:
    """Union of JSON Schema masks for the next item, one per type/column mode.

    Each branch preserves correlated chord/join constraints. Missing optional
    attributes mean their default; masks never require explicit default values.
    Validate the completed candidate with advance as the final authority.
    """
    schema = ITEM.json_schema()
    definitions = schema["$defs"]
    masks: list[dict[str, Any]] = []
    for definition in definitions.values():
        properties = definition["properties"]
        kind = properties["type"]["const"]
        if kind == "ending" and (state.previous is None or state.previous.type != "bar"):
            continue
        props: dict[str, Any] = {}
        for key, value in properties.items():
            value = dict(value)
            if "anyOf" in value:
                value = next(v.copy() for v in value["anyOf"] if v.get("type") != "null")
            # Optional defaults are absent on the wire.
            if key in ("chord", "join"):
                value = {"const": 1}
            elif key in ("accParen", "fermata", "measureRest", "courtesy"):
                value = {"const": True}
            elif key == "cancel":
                value["minimum"] = 1
            elif "enum" in value and "none" in value["enum"]:
                value["enum"] = [v for v in value["enum"] if v != "none"]
            props[key] = value
        required = list(definition.get("required", []))
        if state.courtesy:
            if "courtesy" not in props:
                continue
            required.append("courtesy")
        elif not state.after_bar:
            props.pop("courtesy", None)
        base: dict[str, Any] = {
            "type": "object",
            "properties": props,
            "required": required,
            "additionalProperties": False,
        }
        # A new column never carries a continuation marker.
        new = copy.deepcopy(base)
        new["properties"].pop("chord", None)
        new["properties"].pop("join", None)
        masks.append(new)
        previous = state.previous
        if state.courtesy:
            continue
        if kind == "note" and isinstance(previous, NoteItem):
            chord = copy.deepcopy(base)
            cp = chord["properties"]
            cp.pop("join", None)
            chord["required"].append("chord")
            for name in ("v", "dur", "dots"):
                cp[name] = {"const": getattr(previous, name)}
            cp["pos"]["minimum"] = previous.pos
            if previous.grace is None:
                cp.pop("grace", None)
            else:
                cp["grace"] = {"const": previous.grace}
                chord["required"].append("grace")
            masks.append(chord)
        if kind in ("note", "rest") and isinstance(previous, (NoteItem, RestItem)):
            if previous.v == 4 or (isinstance(previous, NoteItem) and previous.grace is not None):
                continue
            joined = copy.deepcopy(base)
            jp = joined["properties"]
            jp.pop("chord", None)
            jp.pop("grace", None)
            jp["v"] = {"type": "integer", "minimum": previous.v + 1, "maximum": 4}
            joined["required"].append("join")
            masks.append(joined)
    return masks
