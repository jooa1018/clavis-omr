"""Approved XSD dependency smoke: original schema assets, local resources only."""

import socket
from pathlib import Path

import pytest
import xmlschema


def test_musicxml_validation_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access during XSD validation")

    monkeypatch.setattr(socket.socket, "connect", reject_network)
    root = Path("src/clavis/export/schemas/musicxml-4.0").resolve()
    schema = xmlschema.XMLSchema(
        root / "musicxml.xsd",
        locations={
            "http://www.w3.org/XML/1998/namespace": str(root / "xml.xsd"),
            "http://www.w3.org/1999/xlink": str(root / "xlink.xsd"),
        },
        allow="local",
        defuse="always",
        use_fallback=False,
    )
    valid = (
        '<score-partwise version="4.0"><part-list><score-part id="P1">'
        "<part-name>Synthetic</part-name></score-part></part-list>"
        '<part id="P1"><measure number="1"><attributes><divisions>1</divisions>'
        "</attributes><note><pitch><step>C</step><octave>4</octave></pitch>"
        "<duration>1</duration><type>quarter</type></note></measure></part></score-partwise>"
    )
    schema.validate(valid)
    assert not schema.is_valid(valid.replace("<step>C</step>", "<step>H</step>"))
