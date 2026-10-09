"""CCR-0002 character pushdown automaton and observed-spelling normalization.

CONTRACTS 6 permits recursive parentheses, so a finite-state regex alone is
insufficient. Configuration contains the approved vocabulary, never song data.
This module does not infer MusicXML kinds, probabilities, roles or missing text.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType


@dataclass(frozen=True)
class ChordState:
    """Immutable character-prefix configurations, suitable for CTC beam branches."""

    stacks: frozenset[tuple[str, ...]]
    length: int = 0

    @property
    def accepting(self) -> bool:
        return () in self.stacks

    @property
    def viable(self) -> bool:
        return bool(self.stacks)


@dataclass(frozen=True)
class ChordSpelling:
    """Not ChordParseResult: harmonic interpretation belongs to a later adapter."""

    text: str
    kind_text: str
    normalized: str
    outside_consumer_vocab: bool


class ChordGrammar:
    """Load an explicit catalog; all mutable parsing state stays in each call."""

    def __init__(self, catalog: Path, *, max_chars: int, max_states: int) -> None:
        if any(type(n) is not int or n <= 0 for n in (max_chars, max_states)):
            raise ValueError("grammar limits must be positive integers")
        self.max_chars, self.max_states = max_chars, max_states
        rules = {r["id"]: r for r in json.loads(catalog.read_text(encoding="utf-8"))}
        grammar = rules["TEXT-GRAMMAR-001"]
        normalization = rules["TEXT-NORMALIZE-001"]
        glyphs = rules["TEXT-GLYPH-001"]
        consumer = rules["TEXT-CONSUMER-001"]
        self.enabled = bool(grammar["enabled"] and normalization["enabled"])
        self.consumer_enabled = bool(consumer["enabled"])
        self.aliases: Mapping[str, Mapping[str, str]] = MappingProxyType(
            {
                k: MappingProxyType(dict(grammar[k]))
                for k in ("quality", "primary", "sus", "composite")
            }
        )
        self.modifiers: tuple[str, ...] = tuple(grammar["modifiers"])
        self.alterations = tuple(normalization["alteration_order"])
        self.glyphs: Mapping[str, str] = MappingProxyType(
            {r["source"]: r["target"] for r in glyphs["mapping"]} if glyphs["enabled"] else {}
        )
        if any(len(a) != 1 or len(b) != 1 for a, b in self.glyphs.items()):
            raise ValueError("glyph substitutions must preserve character offsets")
        self.outside_primary = frozenset(consumer["outside_primary"])
        self.outside_modifiers = frozenset(consumer["outside_modifiers"])
        # Nonterminals are angle-bracketed; terminal symbols are single characters.
        productions: dict[str, list[tuple[str, ...]]] = {
            "<chord>": [("N", ".", "C", "."), ("<root>", "<body>", "<bass>")],
            "<root>": [("<step>", "<acc>")],
            "<step>": [(x,) for x in "ABCDEFG"],
            "<acc>": [(), ("#",), ("b",)],
            "<bass>": [(), ("/", "<root>")],
            "<body>": [("<composite>", "<mods>"), ("<q>", "<p>", "<s>", "<mods>")],
            "<mods>": [(), ("<mod>", "<mods>")],
            "<mod>": [tuple(x) for x in self.modifiers] + [("(", "<mod>", "<more>", ")")],
            "<more>": [(), (",", "<mod>", "<more>")],
        }
        for nonterminal, group in (("q", "quality"), ("p", "primary"), ("s", "sus")):
            productions[f"<{nonterminal}>"] = [()] + [tuple(x) for x in self.aliases[group]]
        productions["<composite>"] = [tuple(x) for x in self.aliases["composite"]]
        self.productions = MappingProxyType({k: tuple(v) for k, v in productions.items()})

    def _closure(self, stacks: set[tuple[str, ...]]) -> frozenset[tuple[str, ...]]:
        pending, seen, ready = list(stacks), set(stacks), set()
        while pending:
            stack = pending.pop()
            if not stack or stack[0] not in self.productions:
                ready.add(stack)
                continue
            for production in self.productions[stack[0]]:
                expanded = production + stack[1:]
                if expanded not in seen:
                    seen.add(expanded)
                    pending.append(expanded)
                    if len(seen) > self.max_states:
                        raise ValueError("grammar state budget exceeded")
        return frozenset(ready)

    def start(self) -> ChordState:
        return ChordState(self._closure({("<chord>",)}) if self.enabled else frozenset())

    def advance(self, state: ChordState, observed: str) -> ChordState:
        """Consume observed characters without inventing or repairing a glyph."""
        if state.length + len(observed) > self.max_chars:
            raise ValueError("chord character budget exceeded")
        for char in observed:
            char = self.glyphs.get(char, char)
            state = ChordState(
                self._closure({s[1:] for s in state.stacks if s and s[0] == char}),
                state.length + 1,
            )
        return state

    def accepts(self, observed: str) -> bool:
        return self.advance(self.start(), observed).accepting

    def _matches(self, group: str, body: str, offset: int) -> list[tuple[str, str, int]]:
        matches = [("", "", offset)] if group != "composite" else []
        return matches + [
            (token, canonical, offset + len(token))
            for token, canonical in self.aliases[group].items()
            if body.startswith(token, offset)
        ]

    def _mods(self, body: str) -> tuple[str, ...] | None:
        # Full structural validity was already proved by the stack automaton.
        flat = body.translate(str.maketrans("", "", "(),"))
        result = []
        while flat:
            token = next((m for m in self.modifiers if flat.startswith(m)), None)
            if token is None:
                return None
            result.append(token)
            flat = flat[len(token) :]
        return tuple(result)

    def _canonical(self, quality: str, primary: str, sus: str, mods: tuple[str, ...]) -> str:
        if quality == "m" and primary in ("maj7", "maj9"):
            base = "mM" + primary[1:]
        else:
            base = quality + primary
        # Major-quality + 7/9 has the same meaning as the longest maj7/maj9 token.
        ordinary = "".join(m for m in mods if m not in self.alterations)
        altered = "".join(m for a in self.alterations for m in mods if m == a)
        return base + sus + ordinary + altered

    def _derivations(self, body: str) -> list[tuple[tuple[int, ...], str, bool]]:
        results: list[tuple[tuple[int, ...], str, bool]] = []
        for token, canonical, end in self._matches("composite", body, 0):
            mods = self._mods(body[end:])
            if mods is not None:
                if canonical == "m7b5":
                    canonical = self._canonical("m", "7", "", ("b5",) + mods)
                else:
                    canonical = self._canonical(canonical, "", "", mods)
                results.append(
                    ((len(token),), canonical, bool(self.outside_modifiers.intersection(mods)))
                )
        for qt, quality, qi in self._matches("quality", body, 0):
            for pt, primary, pi in self._matches("primary", body, qi):
                for st, sus, si in self._matches("sus", body, pi):
                    mods = self._mods(body[si:])
                    if mods is None:
                        continue
                    if qt in ("maj", "M", "Δ") and primary in ("7", "9"):
                        primary = "maj" + primary
                    canonical = self._canonical(quality, primary, sus, mods)
                    outside = primary in self.outside_primary or bool(
                        self.outside_modifiers.intersection(mods)
                    )
                    results.append(((len(qt), len(pt), len(st)), canonical, outside))
        return results

    def derivation_normal_forms(self, observed: str) -> tuple[str, ...]:
        """Expose every grammatical body derivation for consistency audits."""
        parts = self._parts(observed)
        if parts is None:
            return ()
        root, body, bass = parts
        if root == "N.C.":
            return (root,)
        return tuple(root + form + bass for _, form, _ in self._derivations(body))

    def _parts(self, observed: str) -> tuple[str, str, str] | None:
        if not self.accepts(observed):
            return None
        text = "".join(self.glyphs.get(c, c) for c in observed)
        if text == "N.C.":
            return text, "", ""
        root_end = 2 if len(text) > 1 and text[1] in ("#", "b") else 1
        # A slash before a pitch is bass; the numeric slash in 6/9 stays in body.
        slash = text.rfind("/")
        has_bass = slash >= root_end and text[slash + 1] in "ABCDEFG"
        return (
            text[:root_end],
            text[root_end:slash] if has_bass else text[root_end:],
            text[slash:] if has_bass else "",
        )

    def parse(self, observed: str) -> ChordSpelling | None:
        """Return a checked spelling, preserving exact observed text and suffix."""
        parts = self._parts(observed)
        if parts is None:
            return None
        root, body, bass = parts
        if root == "N.C.":
            return ChordSpelling(observed, observed, root, False)
        derivations = self._derivations(body)
        forms = {canonical for _, canonical, _ in derivations}
        if len(forms) != 1:
            raise ValueError("ambiguous chord normal form")
        # Compare token lengths in consumed order; ties preserve catalog order.
        _, canonical, outside = max(derivations, key=lambda d: tuple(n for n in d[0] if n))
        normalized = root + canonical + bass
        if not self.accepts(normalized):
            raise ValueError("normal form failed grammar")
        end = len(observed) - len(bass) if bass else len(observed)
        return ChordSpelling(
            observed, observed[len(root) : end], normalized, self.consumer_enabled and outside
        )
