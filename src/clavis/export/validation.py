"""Pinned MusicXML 4.0 XSD, with local-only xmlschema resource resolution."""

import hashlib
import json
import warnings
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from threading import Lock
from time import perf_counter_ns
from typing import NoReturn

import xmlschema


def schema_directory() -> Path:
    return Path(__file__).parent / "schemas" / "musicxml-4.0"


def verify_manifest() -> None:
    directory = schema_directory()
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if {row["file"] for row in manifest["files"]} != {"musicxml.xsd", "xlink.xsd", "xml.xsd"}:
        raise ValueError("unexpected schema manifest")
    for row in manifest["files"]:
        data = (directory / row["file"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError("MusicXML schema digest mismatch")


class LocalResolver:
    def __call__(self, url: str) -> str:
        directory = schema_directory().resolve()
        allowed = {}
        for name in ("musicxml.xsd", "xlink.xsd", "xml.xsd"):
            local = (directory / name).as_uri()
            allowed[f"http://www.musicxml.org/xsd/{name}"] = local
            allowed[local] = local
        if url not in allowed:
            raise ValueError("unresolved external schema resource")
        return allowed[url]


class _DocumentBuilder(ET.TreeBuilder):
    def doctype(self, name: str, pubid: str | None, system: str | None) -> NoReturn:
        raise ValueError("DOCTYPE is forbidden")

    def pi(self, target: str, text: str | None = None) -> NoReturn:
        raise ValueError("processing instructions are forbidden")


def parser() -> ET.XMLParser:
    # Reject declarations before entity expansion; ElementTree never loads external DTDs.
    return ET.XMLParser(target=_DocumentBuilder())


@lru_cache(maxsize=1)
def _schema_cache() -> tuple[xmlschema.XMLSchema10, int]:
    start = perf_counter_ns()
    verify_manifest()
    with warnings.catch_warnings():
        # An unresolved import must fail, not leave a partially loaded schema.
        warnings.simplefilter("error", xmlschema.XMLSchemaImportWarning)
        schema = xmlschema.XMLSchema(
            (schema_directory().resolve() / "musicxml.xsd").as_uri(),
            uri_mapper=LocalResolver(),
            allow="local",
            defuse="always",
            use_fallback=False,
        )
    return schema, perf_counter_ns() - start


# A lock also prevents concurrent first calls from compiling the cached schema twice.
_schema_lock = Lock()


def validate_musicxml(data: bytes) -> dict[str, int]:
    """Raise on invalid/unsafe XML. Return timing only, never a decision threshold."""
    document = ET.fromstring(data, parser())
    resource = xmlschema.XMLResource(document, allow="none", defuse="always")
    with _schema_lock:
        schema, load_ns = _schema_cache()
        start = perf_counter_ns()
        schema.validate(resource, use_location_hints=False)
        validation_ns = perf_counter_ns() - start
    return {"schemaLoadNs": load_ns, "validationNs": validation_ns}
