"""Game profiles, player fields and the console-command catalog."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OFFSETS_DIR = ROOT / "offsets"
CATALOG = ROOT / "commands.json"
CBUF = "Cbuf_AddText"  # Cbuf_AddText(int localClientNum, const char *text) queues console commands

# 'cbuf' = community-reported Cbuf_AddText addresses: unverified, and 'setup' checks them first.
GAMES = {
    "bo2": {"game": "Call of Duty: Black Ops II", "title_id": "415608C3", "tu": "TU18", "prestige": 15, "cbuf": ["0x824015E0"]},
    "bo1": {"game": "Call of Duty: Black Ops", "title_id": "41560855", "tu": "TU11", "prestige": 15},
    "mw2": {"game": "Call of Duty: Modern Warfare 2", "title_id": "41560817", "tu": "TU9", "prestige": 10, "cbuf": ["0x82224990"]},
    "mw3": {"game": "Call of Duty: Modern Warfare 3", "title_id": "415608CB", "tu": "TU24", "prestige": 20,
            "cbuf": ["0x8228DAC0", "0x82287F68"]},  # two conflicting reports
    "ghosts": {"game": "Call of Duty: Ghosts", "title_id": "415608FC", "tu": "TU17", "prestige": 10},
    "cod4": {"game": "Call of Duty 4: Modern Warfare", "title_id": "415607E6", "tu": "TU4", "prestige": 10},
    "waw": {"game": "Call of Duty: World at War", "title_id": "4156081C", "tu": "TU7", "prestige": 10},
    "aw": {"game": "Call of Duty: Advanced Warfare", "title_id": "41560914", "tu": "TU17", "prestige": 10},
}

FIELDS = {  # name: (type, size, description)
    "name": ("string", 32, "In-game name. Supports colour codes like ^1 (red) ... ^7 (white)."),
    "clan_tag": ("string", 5, "Clan tag (4 characters + terminator)."),
    "prestige": ("i32", 4, "Prestige level (0-{prestige})."),
    "rank_xp": ("i32", 4, "Rank XP."),
    "fov": ("float", 4, "cg_fov value (default 65.0)."),
    "kills": ("i32", 4, "Career kills. Goes up as you play, easy to refine."),
    "deaths": ("i32", 4, "Career deaths."),
    "wins": ("i32", 4, "Career wins."),
    "losses": ("i32", 4, "Career losses."),
    "score": ("i32", 4, "Career score."),
    "headshots": ("i32", 4, "Career headshots."),
    "time_played": ("i32", 4, "Time played in seconds."),
    "match_kills": ("i32", 4, "Kills in the current match (resets each match)."),
    "match_score": ("i32", 4, "Score in the current match (resets each match)."),
    "pos_x": ("float", 4, "Your X position (for savepos/loadpos). Find with ? and more/less while moving."),
    "pos_y": ("float", 4, "Your Y position (for savepos/loadpos)."),
    "pos_z": ("float", 4, "Your height (for savepos/loadpos). Easiest: ?, go up stairs, more."),
}


def strip_colors(name: str) -> str:
    """'^1Red^7Name' -> 'RedName'."""
    return re.sub(r"\^[0-9]", "", name)


class Profile:
    """A game plus the addresses found for it, saved in offsets/<game>.json."""

    def __init__(self, game: str, path: Path | None = None):
        if game not in GAMES:
            raise KeyError(f"unknown game '{game}' (known: {', '.join(GAMES)})")
        self.short, self.info = game, GAMES[game]
        self.path = Path(path or OFFSETS_DIR / f"{game}.json")
        saved = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.addrs = {k: int(v, 16) for k, v in saved.items()}

    def addr(self, name: str) -> int:
        if name not in self.addrs:
            how = f"use 'setup' or 'setfunc {name} <addr>'" if name == CBUF else f"use 'wizard {name}' or 'setaddr' first"
            raise LookupError(f"'{name}' has no address yet; {how}")
        return self.addrs[name]

    def save(self, name: str, addr: int) -> None:
        self.addrs[name] = addr
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({k: f"0x{v:08X}" for k, v in self.addrs.items()}, indent=2) + "\n")


class Catalog:
    """commands.json: built-in console commands (flags H = host setting, C = needs sv_cheats) and presets."""

    def __init__(self, path: Path = CATALOG):
        raw = json.loads(Path(path).read_text())
        self.presets = raw["presets"]
        self.entries = []
        for e in raw["commands"]:
            games = raw["groups"].get(e["games"]) if isinstance(e["games"], str) else e["games"]
            pattern = re.sub(r"<[^>]+>", ".+", re.escape(e["name"]))  # scr_<gametype>_timelimit
            self.entries.append(dict(e, games=games, re=re.compile(pattern, re.I)))

    def lookup(self, word: str) -> dict | None:
        return next((e for e in self.entries if e["re"].fullmatch(word)), None)

    def search(self, game: str, term: str = "") -> list[dict]:
        term, mine = term.lower(), [e for e in self.entries if game in e["games"]]
        if term in {e["cat"] for e in self.entries}:
            return [e for e in mine if e["cat"] == term]
        return [e for e in mine if term in e["name"].lower() or term in e["desc"].lower()]

    def preset(self, name: str, game: str) -> tuple[list[str], list[str]]:
        """(commands to run, commands skipped because this game doesn't have them)."""
        if name not in self.presets:
            raise KeyError(f"unknown preset '{name}' (known: {', '.join(self.presets)})")
        run, skipped = [], []
        for c in self.presets[name]["commands"]:
            e = self.lookup(c.split()[0])
            (run if e is None or game in e["games"] else skipped).append(c)
        return run, skipped
