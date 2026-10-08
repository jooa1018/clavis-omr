import csv
import hashlib
import io
import json
import tarfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from training.data import pdmx_stream as worker
from training.data.pdmx_aggregate import eligible, notation_counts, unpack_mxl


def mxl(xml: bytes) -> bytes:
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "META-INF/container.xml",
            '<container><rootfiles><rootfile full-path="score.xml" '
            'media-type="application/vnd.recordare.musicxml+xml"/></rootfiles></container>',
        )
        archive.writestr("score.xml", xml)
    return data.getvalue()


def xml() -> bytes:
    return (
        b"<score-partwise><part><measure><attributes><time><beats>4</beats>"
        b"<beat-type>4</beat-type></time></attributes><note><pitch/><type>quarter</type>"
        b"<dot/></note><note><rest/><type>half</type></note><note><grace/><pitch/>"
        b"<type>eighth</type></note></measure><measure><attributes><time><beats>6</beats>"
        b"<beat-type>8</beat-type></time></attributes><note><pitch/><type>eighth</type>"
        b"</note></measure></part></score-partwise>"
    )


def row(name: str) -> dict[str, str]:
    return {
        "mxl": f"./mxl/{name}.mxl",
        "subset:no_license_conflict": "True",
        "license_conflict": "False",
        "license_url": "https://creativecommons.org/publicdomain/mark/1.0/",
    }


def test_license_filter_and_notation() -> None:
    assert eligible(row("a"))
    for key, value in [
        ("license_conflict", "True"),
        ("subset:no_license_conflict", "False"),
        ("license_url", "https://example.org/"),
        ("mxl", "../mxl/a.mxl"),
    ]:
        assert not eligible(dict(row("a"), **{key: value}))
    result = notation_counts(
        unpack_mxl(mxl(xml()), max_xml_bytes=10000, max_ratio=1000), {"4/4", "6/8"}
    )
    assert result["4/4"] == {"note:quarter:dots=1": 1, "rest": 1, "grace": 1}
    assert result["6/8"] == {"note:eighth:dots=0": 1}
    with pytest.raises(ValueError):
        unpack_mxl(mxl(xml()), max_xml_bytes=10, max_ratio=1000)
    with pytest.raises(ValueError):
        notation_counts(b'<!DOCTYPE a [<!ENTITY x "x">]><score-partwise/>', {"4/4"})


def test_stream_resume_has_identical_aggregate_without_song_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    csv_text = io.StringIO(newline="")
    writer = csv.DictWriter(csv_text, fieldnames=list(row("a")))
    writer.writeheader()
    valid_names = ["alpha-secret-id", "beta-secret-id"]
    names = valid_names + [f"bad-secret-id-{i}" for i in range(20)]
    for name in names:
        writer.writerow(row(name))
    manifest = csv_text.getvalue().encode()
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as archive:
        for index, name in enumerate(names):
            payload = mxl(
                xml()
                if name in valid_names
                else b"<score-partwise>" + b"\n" * index + b"&broken;</score-partwise>"
            )
            info = tarfile.TarInfo(f"mxl/{name}.mxl")
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    archive_bytes = buf.getvalue()
    inputs = {"manifest": manifest, "archive": archive_bytes}
    config = json.loads(Path("configs/data/pdmx-aggregate.json").read_text())
    config["checkpoint_every"] = 1
    for key, url in [("PDMX.csv", "manifest"), ("mxl.tar.gz", "archive")]:
        config["files"][key] = {
            "url": url,
            "size": len(inputs[url]),
            "checksum": "md5:" + hashlib.md5(inputs[url], usedforsecurity=False).hexdigest(),
        }
    monkeypatch.setattr(worker, "ROOT", tmp_path)
    monkeypatch.setattr(worker.shutil, "disk_usage", lambda _: MagicMock(free=10**10))
    cache = tmp_path / "sources"
    cache.mkdir()
    (cache / "PDMX.csv").write_bytes(manifest)
    (cache / "mxl.tar.gz").write_bytes(archive_bytes)
    complete, resumed = tmp_path / "work/full", tmp_path / "work/resume"
    worker.run(config, complete, cache)
    original = worker.write_json

    def interrupt(path: Path, data: object) -> None:
        original(path, data)
        raise RuntimeError("simulated interruption")

    with patch.object(worker, "write_json", interrupt), pytest.raises(RuntimeError):
        worker.run(config, resumed, cache)
    worker.run(config, resumed, cache)
    assert (complete / "aggregate.json").read_bytes() == (resumed / "aggregate.json").read_bytes()
    for output in (complete, resumed):
        for artifact in output.glob("*.json"):
            assert "secret-id" not in artifact.read_text()
    result = json.loads((resumed / "aggregate.json").read_text())
    assert result["counts"]["4/4"]["songs"] == 2
    assert result["counts"]["6/8"]["note:eighth:dots=0"] == 2
    assert result["statistics"] == {"parsed_songs": 2, "rejected_invalid_xml": 20}
    assert result["licensing"]["eligible"] == 22
    (cache / "mxl.tar.gz").write_bytes(b"corrupt")
    unpublished = tmp_path / "work/unpublished"
    with pytest.raises(ValueError, match="verification failed"):
        worker.run(config, unpublished, cache)
    assert not (unpublished / "aggregate.json").exists()


def test_hash_stream_bounds_and_authentication() -> None:
    wrapped = worker.HashStream(io.BytesIO(b"abc"), 2)
    with pytest.raises(ValueError):
        io.BufferedReader(wrapped).read()
    wrapped = worker.HashStream(io.BytesIO(b"abc"), 3)
    assert io.BufferedReader(wrapped).read() == b"abc"
    with pytest.raises(ValueError):
        wrapped.verify({"size": 3, "checksum": "md5:wrong"})


@pytest.mark.parametrize("interrupt", [False, True])
def test_cli_cleans_sources_only_after_success(tmp_path, monkeypatch, interrupt):
    from training.data import pdmx_download, pdmx_windows

    cache, output = tmp_path / "cache", tmp_path / "work"
    cache.mkdir()
    output.mkdir()
    for name in ("PDMX.csv", "mxl.tar.gz"):
        (cache / name).write_bytes(b"source")
        (cache / (name + ".ranges.json")).write_text("{}")
    (cache / "unrelated").write_bytes(b"keep")
    config = tmp_path / "config.json"
    config.write_bytes(Path("configs/data/pdmx-aggregate.json").read_bytes())
    monkeypatch.setattr(
        "sys.argv", ["job", "--config", str(config), "--cache", str(cache), "--output", str(output)]
    )
    monkeypatch.setattr(pdmx_windows, "constrain", lambda *args: 1)

    def prepare(config, cache, transferred):
        transferred(17)
        return {"verified": True}

    def run(config, output, cache, telemetry, report):
        report()
        if interrupt:
            raise RuntimeError("synthetic processing interruption")
        return {}

    monkeypatch.setattr(pdmx_download, "prepare", prepare)
    monkeypatch.setattr(worker, "run", run)
    if interrupt:
        with pytest.raises(RuntimeError, match="interruption"):
            worker.main()
    else:
        worker.main()
    metrics = json.loads((output / "run-metrics.json").read_text())
    assert metrics["status"] == ("INTERRUPTED" if interrupt else "COMPLETE")
    assert metrics["transfer_bytes"] == 17
    assert metrics["peak_rss_bytes"] > 0
    assert (cache / "mxl.tar.gz").exists() == interrupt
    assert (cache / "PDMX.csv").exists() == interrupt
    assert (cache / "unrelated").read_bytes() == b"keep"


def test_numbered_meter_and_unknown_type() -> None:
    payload = (
        b"<score-partwise><part><measure><attributes><time><beats>4</beats><beat-type>"
        b'4</beat-type></time><time number="2"><beats>3</beats><beat-type>4</beat-type'
        b"></time></attributes><note><pitch/><type>invalid-label</type></note><note><p"
        b"itch/><type>half</type><staff>2</staff></note><note><unpitched/></note></mea"
        b"sure></part></score-partwise>"
    )
    result = notation_counts(payload, {"4/4", "3/4"})
    assert result["4/4"] == {"note:unknown:dots=0": 1, "unpitched_or_missing_pitch": 1}
    assert result["3/4"] == {"note:half:dots=0": 1}
    assert notation_counts(payload, {"6/8"}) == {}
    with pytest.raises(ValueError):
        notation_counts(b"<score-timewise/>", {"4/4"})


@pytest.mark.parametrize("variant", range(20))
def test_standard_container_default_media_type(variant: int) -> None:
    payload = io.BytesIO()
    name = f"folder/score-{variant}.xml"
    namespace = ' xmlns="urn:test:container"' if variant % 2 else ""
    media = ' media-type="application/vnd.recordare.musicxml+xml"' if variant % 3 else ""
    other = '<rootfile full-path="alternate.pdf" media-type="application/pdf"/>'
    with zipfile.ZipFile(payload, "w") as bundle:
        bundle.writestr(
            "META-INF/container.xml",
            f'<container{namespace}><rootfiles><rootfile full-path="{name}"{media}/>'
            f"{other if variant % 4 else ''}</rootfiles></container>",
        )
        bundle.writestr(name, xml())
    assert unpack_mxl(payload.getvalue(), max_xml_bytes=10000, max_ratio=1000) == xml()


@pytest.mark.parametrize(
    "root", ["", "<rootfile/>", '<rootfile full-path="x" media-type="application/pdf"/>']
)
def test_container_missing_or_non_musicxml_root_is_rejected(root: str) -> None:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as bundle:
        bundle.writestr(
            "META-INF/container.xml", f"<container><rootfiles>{root}</rootfiles></container>"
        )
    with pytest.raises(ValueError, match="rootfile"):
        unpack_mxl(payload.getvalue(), max_xml_bytes=10000, max_ratio=1000)


def test_windows_limits_are_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    import ctypes
    import sys

    from training.data import pdmx_windows

    if sys.platform != "win32":
        pytest.skip("Actual Windows limit API validation")
    fake = MagicMock()
    fake.CreateJobObjectW.return_value = 123
    fake.GetCurrentProcess.return_value = 456

    def affinity(process, allowed, system):
        allowed._obj.value = 15
        system._obj.value = 15
        return 1

    fake.GetProcessAffinityMask.side_effect = affinity
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: fake)
    assert pdmx_windows.constrain(1500000000, 2) == 123
    assert fake.SetPriorityClass.call_args.args == (456, 0x4000)
    assert fake.SetProcessAffinityMask.call_args.args == (456, 3)
    limit = fake.SetInformationJobObject.call_args.args[2]._obj
    assert limit.process_memory == 1500000000
    assert limit.basic.active == 1
    fake.AssignProcessToJobObject.return_value = 0
    with pytest.raises(OSError):
        pdmx_windows.constrain(1500000000, 2)
    fake.GetProcessAffinityMask.return_value = 0
    fake.GetProcessAffinityMask.side_effect = None
    with pytest.raises(OSError):
        pdmx_windows.constrain(1500000000, 2)
    with pytest.raises(ValueError):
        pdmx_windows.constrain(1500000000, 3)
