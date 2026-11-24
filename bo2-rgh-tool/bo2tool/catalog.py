"""Catalog of the games' built-in console commands and presets (commands.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

CATALOG_PATH = Path(__file__).resolve().parent.parent / "commands.json"


@dataclass
class Entry:
    name: str
    kind: str
    category: str
    desc: str
    scope: str = "local"
    cheat: bool = False
    games: list[str] = field(default_factory=list)
    example: str = ""
    default: str | None = None

    def matches(self, name: str) -> bool:
        if "<" in self.name:  # templated, e.g. scr_<gametype>_scorelimit
            head, _, rest = self.name.partition("<")
            tail = rest.partition(">")[2]
            return name.startswith(head) and name.endswith(tail) and len(name) > len(head) + len(tail)
        return name.lower() == self.name.lower()


@dataclass
class Preset:
    name: str
    desc: str
    commands: list[str]


class Catalog:
    def __init__(self, path: Path = CATALOG_PATH):
        raw = json.loads(Path(path).read_text())
        self.notes = raw.get("notes", "")
        self.entries = [Entry(**c) for c in raw["commands"]]
        self.presets = {n: Preset(n, p["desc"], p["commands"]) for n, p in raw.get("presets", {}).items()}

    def lookup(self, name: str) -> Entry | None:
        for entry in self.entries:
            if entry.matches(name):
                return entry
        return None

    def for_game(self, game: str) -> list[Entry]:
        return [e for e in self.entries if game in e.games]

    def search(self, game: str, term: str = "") -> list[Entry]:
        term = term.lower()
        entries = self.for_game(game)
        if term in {e.category for e in self.entries}:
            return [e for e in entries if e.category == term]
        return [e for e in entries if not term or term in e.name.lower() or term in e.desc.lower()]

    def preset_commands(self, name: str, game: str) -> tuple[list[str], list[str]]:
        """(commands to run, commands skipped because this game doesn't have them)."""
        if name not in self.presets:
            raise KeyError(f"unknown preset '{name}' (known: {', '.join(self.presets)})")
        run, skipped = [], []
        for c in self.presets[name].commands:
            entry = self.lookup(c.split()[0])
            (run if entry is None or game in entry.games else skipped).append(c)
        return run, skipped
