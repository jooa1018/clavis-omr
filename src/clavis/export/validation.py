"""Pinned MusicXML 4.0 schema, resolved entirely from package resources."""

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from threading import Lock
from time import perf_counter_ns
from typing import Any

from lxml import etree  # type: ignore[import-untyped]


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


class LocalResolver(etree.Resolver):  # type: ignore[misc]
    def resolve(self, url: str, public_id: str | None, context: Any) -> Any:
        allowed = {
            f"http://www.musicxml.org/xsd/{name}": name
            for name in ("musicxml.xsd", "xlink.xsd", "xml.xsd")
        }
        if url not in allowed:
            raise ValueError("unresolved external schema resource")
        return self.resolve_string((schema_directory() / allowed[url]).read_bytes(), context)


def parser() -> Any:
    result = etree.XMLParser(
        no_network=True,
        resolve_entities=False,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
    )
    result.resolvers.add(LocalResolver())
    return result


@lru_cache(maxsize=1)
def _schema_cache() -> tuple[Any, int]:
    start = perf_counter_ns()
    verify_manifest()
    document = etree.fromstring((schema_directory() / "musicxml.xsd").read_bytes(), parser())
    return etree.XMLSchema(document), perf_counter_ns() - start


# A lock also prevents concurrent first calls from compiling the cached schema twice.
_schema_lock = Lock()


def validate_musicxml(data: bytes) -> dict[str, int]:
    """Raise on invalid/unsafe XML. Return timing only, never a decision threshold."""
    document = etree.fromstring(data, parser())
    if document.getroottree().docinfo.doctype or document.xpath("//processing-instruction()"):
        raise ValueError("DOCTYPE and processing instructions are forbidden")
    with _schema_lock:
        schema, load_ns = _schema_cache()
        start = perf_counter_ns()
        schema.assertValid(document)
        validation_ns = perf_counter_ns() - start
    return {"schemaLoadNs": load_ns, "validationNs": validation_ns}
