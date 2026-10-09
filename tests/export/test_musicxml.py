import json
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from pathlib import Path
from typing import get_args

import pytest
import xmlschema

from clavis.assemble.staff import wire
from clavis.contracts.common import ClefSign
from clavis.export.musicxml import write_musicxml
from clavis.export.reparse import read_projection, score_projection
from clavis.export.validation import (
    LocalResolver,
    _schema_cache,
    parser,
    schema_directory,
    validate_musicxml,
    verify_manifest,
)
from tests.assemble.helpers import assemble, bar, events, note, prefix

from .oracle_smoke import oracle_items, run_smoke


def test_authored_oracle_blackbox(tmp_path):
    report = run_smoke(tmp_path)
    assert report["status"] == "evaluated"
    # Evaluate output is inspected as a public JSON, never an engine/eval shared projection.
    assert "k1" in json.dumps(report).lower()
    assert report["k1Operations"] == 0
    assert report["metrics"]["measureExactMatchRate"]["value"] == 1


@pytest.mark.parametrize("clef", get_args(ClefSign))
def test_all_clefs_xsd_reparse(clef):
    items = prefix()
    items[0]["sign"] = clef
    a = assemble(items + [note(dur="whole"), bar("final")])
    data, timings = write_musicxml(a.score)
    assert read_projection(data) == score_projection(a.score)
    assert timings["schemaLoadNs"] >= 0 and timings["validationNs"] >= 0


@pytest.mark.parametrize(
    "style", ["regular", "double", "final", "repeatStart", "repeatEnd", "dashed", "heavy"]
)
def test_bar_styles_are_schema_valid(style):
    a = assemble(prefix() + [bar(style), note(dur="whole"), bar("final")])
    write_musicxml(a.score)


@pytest.mark.parametrize("acc", ["sharp", "flat", "natural", "doubleSharp", "doubleFlat"])
def test_accidentals_chords_and_voices(acc):
    a = assemble(
        prefix()
        + [
            note(dur="whole", acc=acc),
            note(dur="whole", pos=2, chord=1),
            note(dur="half", v=2, join=1),
            bar("final"),
        ]
    )
    data, _ = write_musicxml(a.score)
    root = ET.fromstring(data)
    assert len(root.findall(".//note")) == 3
    assert root.find(".//backup/duration").text == "4"
    assert root.find(".//forward/duration").text == "2"
    assert root.find(".//note/chord") is not None


def test_grace_tuplet_slash_rest_fermata():
    a = assemble(
        prefix(1)
        + [
            note(grace="acciaccatura", slur="start"),
            note(dur="eighth", tup3="start", slur="stop"),
            note(dur="eighth", tup3="continue", head="slash"),
            dict(type="rest", dur="eighth", dots=0, v=1, tup3="stop", fermata=True),
            bar(),
            dict(type="rest", dur="whole", dots=0, v=1, measureRest=True),
            bar("final"),
        ]
    )
    data, _ = write_musicxml(a.score)
    root = ET.fromstring(data)
    assert root.find(".//grace") is not None
    assert root.find(".//notehead").text == "slash"
    assert root.find(".//notations/fermata") is not None
    assert all(
        e.find("duration") is None for e in root.findall(".//note") if e.find("grace") is not None
    )


def test_forward_gap_and_pickup_have_no_fabricated_rest():
    a = assemble(prefix() + [note(), bar()])
    assert a.score.measures[0].implicit
    data, _ = write_musicxml(a.score)
    assert ET.fromstring(data).find(".//measure").get("implicit") == "yes"
    a.score.measures[0].implicit = False
    events(a)[0].onset = wire(Fraction(1))
    data, _ = write_musicxml(a.score)
    root = ET.fromstring(data)
    assert len(root.findall(".//note")) == 1 and not root.findall(".//rest")
    assert len(root.findall(".//forward")) == 2


def test_determinism_and_single_schema_load():
    score = assemble(oracle_items()).score
    outputs = []
    for workers in (1, 4):
        with ThreadPoolExecutor(max_workers=workers) as pool:
            outputs.extend(pool.map(lambda _: write_musicxml(score)[0], range(3)))
    assert len(set(outputs)) == 1
    assert _schema_cache.cache_info().misses == 1


def test_pinned_manifest_and_offline_resolution():
    verify_manifest()
    manifest = json.loads((schema_directory() / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["tag"] == "v4.0"

    doc = ET.fromstring(b"<root/>", parser())
    assert doc.tag == "root"
    with pytest.raises(ValueError, match="unresolved"):
        LocalResolver()("https://invalid.example/not-local.xsd")


@pytest.mark.parametrize(
    "xml",
    [
        b'<!DOCTYPE score-partwise [<!ENTITY x "unsafe">]><score-partwise version="4.0"/>',
        b'<?unsafe x?><score-partwise version="4.0"/>',
        b'<score-partwise version="4.0"><?unsafe x?></score-partwise>',
        b'<score-partwise version="4.0"><unknown/></score-partwise>',
    ],
)
def test_invalid_xml_is_rejected(xml):
    with pytest.raises((ValueError, xmlschema.XMLSchemaValidationError, ET.ParseError)):
        validate_musicxml(xml)


def test_writer_rejects_overfull_missing_chord_and_overlap():
    with pytest.raises(ValueError, match="overfull"):
        write_musicxml(assemble(prefix() + [note(dur="breve")]).score)
    a = assemble(prefix() + [note(), note()])
    events(a)[0].chord_with_prev = True
    with pytest.raises(ValueError, match="preceding"):
        write_musicxml(a.score)
    events(a)[0].chord_with_prev = False
    events(a)[1].onset = wire(Fraction(0))
    with pytest.raises(ValueError, match="overlapping"):
        write_musicxml(a.score)


def test_reference_itself_is_xsd_valid():
    validate_musicxml((Path(__file__).parent / "fixtures" / "oracle.musicxml").read_bytes())


def test_manifest_tampering_rejected(tmp_path, monkeypatch):
    import clavis.export.validation as validation

    directory = schema_directory()
    for name in ("manifest.json", "musicxml.xsd", "xlink.xsd", "xml.xsd"):
        (tmp_path / name).write_bytes((directory / name).read_bytes())
    monkeypatch.setattr(validation, "schema_directory", lambda: tmp_path)
    (tmp_path / "xml.xsd").write_bytes(b"modified")
    with pytest.raises(ValueError, match="digest"):
        verify_manifest()
    manifest = json.loads((tmp_path / "manifest.json").read_bytes())
    manifest["files"].pop()
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="manifest"):
        verify_manifest()


def test_projection_detects_attribute_and_notation_changes():
    score = assemble(oracle_items()).score
    data, _ = write_musicxml(score)
    root = ET.fromstring(data)
    root.find(".//key/fifths").text = "3"
    assert read_projection(ET.tostring(root)) != score_projection(score)
    root.find(".//notations/tied").set("type", "stop")
    with pytest.raises(ValueError, match="playback/notation"):
        read_projection(ET.tostring(root))


def test_multi_rest_and_reinterpreted_slur_export():
    write_musicxml(assemble(prefix(3) + [dict(type="mrest", count=3), bar("final")]).score)
    data, _ = write_musicxml(
        assemble(prefix(2) + [note(tie="start"), note(pos=1, tie="stop")]).score
    )
    root = ET.fromstring(data)
    assert not root.findall(".//tie")
    assert len(root.findall(".//notations/slur")) == 2


def test_join_delayed_voice_round_trip_without_extra_events():
    a = assemble(prefix() + [note(dur="half"), note(), note(v=2, join=1)])
    data, _ = write_musicxml(a.score)
    root = ET.fromstring(data)
    assert len(root.findall(".//note")) == 3
    assert not root.findall(".//rest")
    assert root.find(".//forward/duration").text == "2"
    assert read_projection(data) == score_projection(a.score)


def test_cold_schema_load_without_network_and_instance_hints():
    import subprocess
    import sys

    script = """
import socket
from concurrent.futures import ThreadPoolExecutor
print("phase=imports", flush=True)
attempts = []
def refuse(*args, **kwargs):
    attempts.append("network")
    raise AssertionError("network forbidden")
socket.socket.connect = refuse
socket.socket.connect_ex = refuse
socket.create_connection = refuse
socket.getaddrinfo = refuse
from clavis.export.validation import validate_musicxml
from tests.export.oracle_smoke import oracle_items
from tests.assemble.helpers import assemble
from clavis.export.musicxml import write_musicxml
score = assemble(oracle_items()).score
print("phase=concurrent-output", flush=True)
with ThreadPoolExecutor(max_workers=4) as pool:
    outputs = list(pool.map(lambda _: write_musicxml(score)[0], range(8)))
assert len(set(outputs)) == 1, "concurrent validated outputs differ"
print("phase=instance-hints", flush=True)
xml = outputs[0].replace(
    b'<score-partwise ',
    b'<score-partwise xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
    b'xsi:noNamespaceSchemaLocation="https://invalid.example/never.xsd" '
)
validate_musicxml(xml)
assert not attempts, f"unexpected network attempts: {len(attempts)}"
print("phase=complete", flush=True)
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    diagnostic = (
        f"cold schema subprocess failed: returncode={result.returncode} "
        f"(0x{result.returncode & 0xFFFFFFFF:08X})\n"
        f"stdout:\n{result.stdout or '<empty>'}\nstderr:\n{result.stderr or '<empty>'}"
    )
    # Keep the failure cause while removing local profile/checkout paths from assertions.
    for path, label in (
        (Path.cwd(), "<repo>"),
        (Path(sys.prefix), "<venv>"),
        (Path(sys.base_prefix), "<python>"),
        (Path.home(), "<user-profile>"),
    ):
        for spelling in (str(path), path.as_posix()):
            diagnostic = diagnostic.replace(spelling, label)
    # Avoid pytest appending the unsanitized CompletedProcess repr to this message.
    if result.returncode != 0:
        raise AssertionError(diagnostic)


def test_cold_schema_child_failure_reports_reason(monkeypatch):
    import subprocess

    def failed_child(*args, **kwargs):
        return subprocess.CompletedProcess(
            args[0],
            0xC000070A,
            "phase=imports\n",
            f"synthetic import failure at {Path.cwd()} and {Path.home()}",
        )

    monkeypatch.setattr(subprocess, "run", failed_child)
    with pytest.raises(AssertionError) as caught:
        test_cold_schema_load_without_network_and_instance_hints()
    message = str(caught.value)
    assert "0xC000070A" in message and "phase=imports" in message
    assert "synthetic import failure" in message
    assert "CompletedProcess(" not in message
    assert str(Path.cwd()) not in message and str(Path.home()) not in message


@pytest.mark.parametrize("encoding", ["utf-8", "utf-16"])
def test_dtd_is_rejected_before_loading_or_entity_expansion(encoding):
    payload = (
        '<!DOCTYPE score-partwise SYSTEM "https://invalid.example/never.dtd"><score-partwise/>'
    )
    with pytest.raises(ValueError, match="DOCTYPE"):
        validate_musicxml(payload.encode(encoding))
