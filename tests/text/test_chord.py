import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from itertools import product
from pathlib import Path

import pytest

from clavis.text.chord import ChordGrammar

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "configs/text/rules.yaml"
LIMITS = {
    r["name"].removeprefix("text.grammar."): r["value"]
    for r in json.loads((ROOT / "configs/text/constants.yaml").read_text())
    if r["name"].startswith("text.grammar.")
}


@pytest.fixture(scope="module")
def grammar():
    return ChordGrammar(CATALOG, **LIMITS)


# Independent fixture transcribed from CONTRACTS 12.6, not the implementation catalog.
VOCAB = {
    "": "",
    "m": "m",
    "min": "m",
    "-": "m",
    "dim": "dim",
    "°": "dim",
    "aug": "aug",
    "+": "aug",
    "maj": "",
    "Δ": "",
    "M": "",
    "2": "2",
    "6": "6",
    "6/9": "6/9",
    "7": "7",
    "9": "9",
    "maj7": "maj7",
    "MAJ7": "maj7",
    "Maj7": "maj7",
    "M7": "maj7",
    "Δ7": "maj7",
    "maj9": "maj9",
    "MAJ9": "maj9",
    "Maj9": "maj9",
    "M9": "maj9",
    "Δ9": "maj9",
    "sus": "sus4",
    "sus2": "sus2",
    "sus4": "sus4",
    "add2": "add2",
    "add4": "add4",
    "add6": "add6",
    "add9": "add9",
    "add11": "add11",
    "add13": "add13",
    "b5": "b5",
    "#5": "#5",
    "b9": "b9",
    "#9": "#9",
    "#11": "#11",
    "b13": "b13",
    "no3": "no3",
    "no5": "no5",
    "m7b5": "m7b5",
    "min7b5": "m7b5",
    "ø": "m7b5",
    "ø7": "m7b5",
    "dim7": "dim7",
    "°7": "dim7",
    "mMaj7": "mMaj7",
    "minMaj7": "mMaj7",
    "mMaj9": "mMaj9",
    "minMaj9": "mMaj9",
}


@pytest.mark.parametrize("suffix,canonical", VOCAB.items())
def test_full_consumer_vocabulary(grammar, suffix, canonical):
    # Put alteration vocabulary behind a seventh to distinguish it from root accidentals.
    prefix = "C7" if suffix.startswith(("b", "#")) else "C"
    printed = prefix + suffix
    result = grammar.parse(printed)
    assert result is not None
    assert result.normalized == prefix + canonical
    assert not result.outside_consumer_vocab
    assert result.text == printed
    assert grammar.parse(result.normalized).normalized == result.normalized


@pytest.mark.parametrize("root,acc,bass", product("ABCDEFG", ("", "#", "b"), ("", "/F#", "/Bb")))
def test_root_and_slash_bass(grammar, root, acc, bass):
    printed = root + acc + "min7(#11,b9)" + bass
    parsed = grammar.parse(printed)
    assert parsed.normalized == root + acc + "m7b9#11" + bass
    assert parsed.kind_text == "min7(#11,b9)"
    assert not parsed.outside_consumer_vocab


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Ｃ♯△⁷／Ｇ♭", "C#maj7/Gb"),
        ("B♭Ø⁷", "Bbm7b5"),
        ("F♯-⁷", "F#m7"),
        ("G7((#11,b9),b5)", "G7b5b9#11"),
        ("C6/9/E", "C6/9/E"),
        ("Cm7(b5)", "Cm7b5"),
        ("Cmaj7", "Cmaj7"),
        ("CM7", "Cmaj7"),
        ("CΔ9", "Cmaj9"),
        ("CmM7", "CmMaj7"),
        ("CminΔ9", "CmMaj9"),
        ("N.C.", "N.C."),
        ("Cm7b5add9", "Cm7add9b5"),
        ("C7(b9,b9)", "C7b9b9"),
    ],
)
def test_normalization_and_print_preservation(grammar, text, expected):
    result = grammar.parse(text)
    assert result.normalized == expected
    assert result.text == text
    assert grammar.parse(expected).normalized == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "H7",
        "c7",
        " C7",
        "C7 ",
        "C 7",
        "C\n7",
        "N.C./C",
        "N.C.7",
        "NC",
        "C8",
        "C14",
        "C7/",
        "C/Eb7",
        "C//G",
        "C6/9/9",
        "Cbb7",
        "C##7",
        "C7()",
        "C7(b9,)",
        "C7(,b9)",
        "C7(b9#11)",
        "C7(b9",
        "C7b9)",
        "C7((b9),())",
        "C(add3)",
        "C(no7)",
        "C7alt",
        "C0",
        "Co",
        "Cᵒ",
        "Caugdim",
        "Csus7",
        "Cm7b5sus4",
        "C7\x00",
        "C𝟟",
        "Cⁿ",
        "C7\u200b",
    ],
)
def test_rejections(grammar, text):
    assert not grammar.accepts(text)
    assert grammar.parse(text) is None
    assert grammar.derivation_normal_forms(text) == ()


@pytest.mark.parametrize("suffix", ["5", "11", "13", "7(b11)", "7(#13)"])
def test_outside_vocabulary_is_preserved(grammar, suffix):
    result = grammar.parse("C" + suffix)
    assert result.outside_consumer_vocab
    assert grammar.accepts(result.normalized)


def test_all_ambiguous_derivations_agree(grammar):
    ambiguous = [
        "M7",
        "Δ7",
        "maj7",
        "M9",
        "Δ9",
        "maj9",
        "m7b5",
        "min7b5",
        "dim7",
        "°7",
        "mMaj7",
        "minMaj7",
        "mMaj9",
        "minMaj9",
    ]
    for suffix, modifier in product(ambiguous, ("", "(b9)", "(add9,#11)/Bb")):
        forms = grammar.derivation_normal_forms("F#" + suffix + modifier)
        assert len(forms) > 1
        assert len(set(forms)) == 1
        assert grammar.parse(forms[0]).normalized == forms[0]


def test_generated_bodies_all_derivations_and_idempotence(grammar):
    for quality, primary, sus in product(
        ("", "m", "min", "maj", "M", "Δ", "dim", "+"),
        ("", "7", "M7", "Δ9", "6/9", "13"),
        ("", "sus", "sus2"),
    ):
        text = "Ab" + quality + primary + sus + "(b9,add11)/F#"
        forms = grammar.derivation_normal_forms(text)
        assert forms and len(set(forms)) == 1
        result = grammar.parse(text)
        assert grammar.parse(result.normalized).normalized == result.normalized


def test_prefix_state_branching_and_recursive_modifiers(grammar):
    start = grammar.start()
    root = grammar.advance(start, "C")
    assert root.accepting and root.viable and not start.accepting
    major = grammar.advance(root, "M")
    assert grammar.advance(major, "7").accepting
    assert grammar.advance(major, "9").accepting
    assert not grammar.advance(root, "H").viable
    assert not grammar.advance(root, "(").accepting
    assert grammar.advance(root, "(((b9)),#11)").accepting
    assert root == grammar.advance(start, "C")


def test_byte_determinism_one_and_four_workers(grammar):
    def run(_):
        return json.dumps(
            [asdict(grammar.parse(x)) for x in ("F♯△⁷/G♭", "Cm7b5", "C7(#11,b9)")],
            ensure_ascii=False,
            sort_keys=True,
        ).encode()

    outputs = []
    for threads in (1, 4):
        with ThreadPoolExecutor(max_workers=threads) as pool:
            outputs.extend(pool.map(run, range(3)))
    assert len(set(outputs)) == 1


@pytest.mark.parametrize(
    "rule", ["TEXT-GRAMMAR-001", "TEXT-NORMALIZE-001", "TEXT-GLYPH-001", "TEXT-CONSUMER-001"]
)
def test_ablation_flags(tmp_path, rule):
    rules = json.loads(CATALOG.read_text(encoding="utf-8"))
    for entry in rules:
        if entry["id"] == rule:
            entry["enabled"] = False
    path = tmp_path / "rules.json"
    path.write_text(json.dumps(rules), encoding="utf-8")
    grammar = ChordGrammar(path, **LIMITS)
    if rule in ("TEXT-GRAMMAR-001", "TEXT-NORMALIZE-001"):
        assert grammar.parse("C7") is None
    elif rule == "TEXT-GLYPH-001":
        assert grammar.parse("C△⁷") is None
        assert grammar.parse("Cmaj7").normalized == "Cmaj7"
    else:
        assert not grammar.parse("C13").outside_consumer_vocab


def test_limits_and_glyph_catalog(grammar, tmp_path):
    for limits in ({"max_chars": 0, "max_states": 1}, {"max_chars": True, "max_states": 1}):
        with pytest.raises(ValueError):
            ChordGrammar(CATALOG, **limits)
    with pytest.raises(ValueError, match="character budget"):
        grammar.accepts("C" * (LIMITS["max_chars"] + 1))
    with pytest.raises(ValueError, match="state budget"):
        ChordGrammar(CATALOG, max_chars=1, max_states=1).start()
    assert grammar.glyphs.get("A", "A") == "A"
    for visual in "0o°":
        assert grammar.glyphs.get(visual, visual) == visual
    rules = json.loads(CATALOG.read_text(encoding="utf-8"))
    glyph = next(r for r in rules if r["id"] == "TEXT-GLYPH-001")
    assert all(entry["rationale"] for entry in glyph["mapping"])
    for entry in glyph["mapping"]:
        assert grammar.glyphs[entry["source"]] == entry["target"]
    glyph["mapping"][0]["target"] = "bad"
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(rules))
    with pytest.raises(ValueError, match="offsets"):
        ChordGrammar(path, **LIMITS)
