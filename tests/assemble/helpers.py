"""Authored symbolic fixtures only; symbol IDs stand for mock evidence."""

from hashlib import sha256

from clavis.assemble.staff import assemble_staff
from clavis.contracts.score import ScoreEngine
from clavis.contracts.symbols import StaffLattice


def note(**changes):
    return dict(type="note", dur="quarter", dots=0, pos=0, head="normal", v=1) | changes


def bar(style="regular"):
    return dict(type="bar", style=style)


def lattice(items):
    return StaffLattice.model_validate(
        dict(
            schema="clavis-ir-0.1.1",
            id="pg0-sy0-st0",
            stripId="pg0-sy0-st0",
            producer=dict(
                name="authored-smoke",
                version="0.1",
                sha256=sha256(b"self-authored-symbolic-smoke").hexdigest(),
            ),
            hypotheses=[
                dict(
                    rank=0,
                    logProbMicro=0,
                    items=[
                        dict(
                            item=item,
                            attrTopK={},
                            itemProbBp=9000,
                            spanU=[float(i * 2), float(i * 2 + 1)],
                            symbolIds=[f"pg0-sy0-st0-s{i}"],
                        )
                        for i, item in enumerate(items)
                    ],
                )
            ],
        )
    )


def assemble(items, **kwargs):
    return assemble_staff(
        lattice(items),
        engine=ScoreEngine(version="0.0.1", build_digest=sha256(b"test-build").hexdigest()),
        **kwargs,
    )


def prefix(beats=4, beat_type=4):
    return [
        dict(type="clef", sign="G2"),
        dict(type="key", fifths=0),
        dict(type="time", beats=beats, beatType=beat_type),
    ]


def events(assembly):
    return [
        e
        for m in assembly.score.measures
        for sm in m.staff_measures
        for v in sm.voices
        for e in v.events
    ]
