"""Authored synthetic grammar examples only; no raster or score corpus."""

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "fixtures/lstl"
NOTE = "note dur=quarter pos=0 head=normal v=1"
GOLDEN = {
    "01-initial": "clef sign=G2\nkey fifths=0\ntime beats=4 beatType=4\nbar style=repeatStart",
    "02-single": NOTE,
    "03-chord": NOTE + "\nnote dur=quarter pos=2 head=normal v=1 chord=1",
    "04-note-rest-join": NOTE + "\nrest dur=half v=2 join=1 pos=0",
    "05-rest-note-join": "rest dur=whole v=1\nnote dur=quarter pos=-4 head=normal v=2 join=1",
    "06-four-voices": NOTE
    + "\nrest dur=half v=2 join=1\nrest dur=quarter v=3 join=1\nrest dur=eighth v=4 join=1",
    "07-two-chords": NOTE
    + (
        "\nnote dur=quarter pos=2 head=normal v=1 chord=1\nnote dur=half "
        "pos=-8 head=normal v=2 join=1\nnote dur=half pos=-4 head=normal v=2 "
        "chord=1"
    ),
    "08-new-column": NOTE + "\nrest dur=half v=2 join=1\n" + NOTE,
    "09-grace": "note dur=eighth pos=1 head=normal v=1 grace=acciaccatura\n" + NOTE,
    "10-grace-chord": (
        "note dur=eighth pos=1 head=normal v=1 grace=appoggiatura\nnote "
        "dur=eighth pos=3 head=normal v=1 chord=1 grace=appoggiatura\n"
    )
    + NOTE,
    "11-courtesy": NOTE
    + (
        "\nbar style=double\nclef sign=F4 courtesy=1\nkey fifths=-2 "
        "courtesy=1\ntime beats=3 beatType=4 courtesy=1"
    ),
    "12-ending": "bar style=repeatEnd\nending numbers=[1,2] mark=start\n" + NOTE,
    "13-navigation": "segno\n" + NOTE + "\nbar style=regular\ncoda",
    "14-multirest": "mrest count=2\nbar style=regular\nmrest count=64",
    "15-rest-options": "rest dur=whole dots=2 v=1 pos=0 measureRest=1 fermata=1 tup3=start",
    "16-note-options": (
        "note dur=quarter dots=1 pos=0 head=diamond v=1 acc=sharp accParen=1 "
        "tie=both slur=start tup3=continue fermata=1 stem=up beam=begin"
    ),
    "17-duration-range": (
        "note dur=breve pos=-14 head=slash v=1\nnote dur=64th dots=2 pos=22 head=x v=4"
    ),
    "18-key-cancel": "key fifths=-7 cancel=7\nkey fifths=7",
    "19-time-symbols": "time beats=4 beatType=4 symbol=common\ntime beats=2 beatType=2 symbol=cut",
    "20-bar-boundary": NOTE
    + (
        "\nclef sign=C3\nbar style=regular\nkey fifths=1\ntime beats=3 "
        "beatType=8\nbar style=repeatStart\n"
    )
    + NOTE,
    "21-tie-cross-system": NOTE + " tie=stop\nnote dur=quarter pos=1 head=normal v=1 tie=start",
    "22-empty": "",
    "23-rest-rest": "rest dur=half v=1\nrest dur=whole v=4 join=1",
    "24-join-chord-order": NOTE
    + (
        "\nnote dur=quarter pos=-10 head=normal v=3 join=1\nnote dur=quarter "
        "pos=-9 head=normal v=3 chord=1\nrest dur=eighth v=4 join=1"
    ),
}
N = {"type": "note", "dur": "quarter", "dots": 0, "pos": 0, "head": "normal", "v": 1}
R = {"type": "rest", "dur": "half", "dots": 0, "v": 1}


def invalid_sequences():
    cases = {}
    cases["ending-without-bar"] = [{"type": "ending", "numbers": [1], "mark": "start"}]
    cases["ending-after-note"] = [N, {"type": "ending", "numbers": [1], "mark": "stop"}]
    for predecessor, label in [
        (None, "start"),
        (R, "rest"),
        ({"type": "bar", "style": "regular"}, "bar"),
        ({"type": "clef", "sign": "G2"}, "clef"),
        ({"type": "mrest", "count": 2}, "mrest"),
        ({"type": "segno"}, "segno"),
        ({"type": "coda"}, "coda"),
    ]:
        cases[f"chord-after-{label}"] = ([] if predecessor is None else [predecessor]) + [
            {**N, "chord": 1}
        ]
    for field, value in [
        ("v", 2),
        ("dur", "half"),
        ("dots", 1),
        ("grace", "acciaccatura"),
        ("pos", -1),
    ]:
        cases[f"chord-mismatch-{field}"] = [N, {**N, "chord": 1, field: value}]
    cases["chord-grace-to-normal"] = [{**N, "grace": "appoggiatura"}, {**N, "chord": 1}]
    for predecessor, label in [
        (None, "start"),
        ({"type": "bar", "style": "regular"}, "bar"),
        ({"type": "time", "beats": 4, "beatType": 4}, "time"),
        ({"type": "mrest", "count": 2}, "mrest"),
        ({**N, "grace": "acciaccatura"}, "grace"),
    ]:
        for target, name in [(N, "note"), (R, "rest")]:
            cases[f"join-{name}-after-{label}"] = ([] if predecessor is None else [predecessor]) + [
                {**target, "v": 2, "join": 1}
            ]
    for voice in (1, 2, 3):
        cases[f"join-voice-order-{voice}"] = [{**N, "v": 3}, {**R, "v": voice, "join": 1}]
    cases["join-chord"] = [N, {**N, "v": 2, "chord": 1, "join": 1}]
    cases["join-grace"] = [N, {**N, "v": 2, "grace": "appoggiatura", "join": 1}]
    for target in [{"type": "mrest", "count": 2}, {"type": "key", "fifths": 0}, {"type": "coda"}]:
        cases[f"join-forbidden-{target['type']}"] = [N, {**target, "join": 1}]
    for value, label in [
        (0, "default"),
        (2, "two"),
        (-1, "negative"),
        (True, "boolean"),
        (1.0, "float"),
        (None, "null"),
    ]:
        cases[f"join-invalid-{label}"] = [N, {**R, "v": 2, "join": value}]
    cases["courtesy-start"] = [{"type": "clef", "sign": "G2", "courtesy": True}]
    cases["courtesy-after-note"] = [
        {"type": "bar", "style": "regular"},
        N,
        {"type": "key", "fifths": 0, "courtesy": True},
    ]
    cases["courtesy-not-tail"] = [
        {"type": "bar", "style": "regular"},
        {"type": "clef", "sign": "G2", "courtesy": True},
        N,
    ]
    return copy.deepcopy(cases)


def invalid_text():
    return {
        "missing-lf": NOTE,
        "two-lf": NOTE + "\n\n",
        "crlf": NOTE + "\r\n",
        "bom": "\ufeff" + NOTE + "\n",
        "unknown": NOTE + " bogus=1\n",
        "duplicate": NOTE + " v=2\n",
        "wrong-order": "note pos=0 dur=quarter head=normal v=1\n",
        "dots-zero": "note dur=quarter dots=0 pos=0 head=normal v=1\n",
        "default-acc": NOTE + " acc=none\n",
        "default-chord": NOTE + " chord=0\n",
        "default-join": NOTE + " join=0\n",
        "default-boolean": NOTE + " fermata=0\n",
        "default-grace": NOTE + " grace=none\n",
        "unknown-type": "sound\n",
        "leading-space": " " + NOTE + "\n",
        "double-space": NOTE.replace(" pos=", "  pos=") + "\n",
        "trailing-space": NOTE + " \n",
        "tab": NOTE.replace(" pos=", "\tpos=") + "\n",
        "leading-zero": NOTE.replace("pos=0", "pos=00") + "\n",
        "positive-sign": NOTE.replace("pos=0", "pos=+0") + "\n",
        "omitted-pos": "note dur=quarter head=normal v=1\n",
        "ending-spaces": "ending numbers=[1, 2] mark=start\n",
        "ending-scalar": "ending numbers=1 mark=start\n",
        "ending-float": "ending numbers=[1.0] mark=start\n",
        "boolean-word": NOTE + " fermata=true\n",
        "invalid-integer": NOTE.replace("pos=0", "pos=x") + "\n",
        "nfc": "clef sign=e\u0301\n",
        "rest-default-extra": "rest dur=quarter v=1 acc=none\n",
        "note-null": NOTE + " join=null\n",
        "missing-attribute": "time beats=4\n",
    }


def build():
    (ROOT / "golden").mkdir(parents=True, exist_ok=True)
    for name, text in GOLDEN.items():
        (ROOT / "golden" / f"{name}.lstl").write_bytes((text + "\n").encode())
    for name, data in [
        ("invalid-sequences", invalid_sequences()),
        ("invalid-text", invalid_text()),
    ]:
        (ROOT / f"{name}.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )


if __name__ == "__main__":
    build()
