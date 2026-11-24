"""Game layer: named fields and functions loaded from offsets/<game>.json."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .xbdm import Xbdm

OFFSETS_DIR = Path(__file__).resolve().parent.parent / "offsets"
TYPES = ("string", "i32", "u32", "float", "bytes")


def available_games() -> dict[str, str]:
    """short name -> full game name, for every file in offsets/."""
    out = {}
    for path in sorted(OFFSETS_DIR.glob("*.json")):
        out[path.stem] = json.loads(path.read_text()).get("game", path.stem)
    return out


def offsets_path(game: str) -> Path:
    path = OFFSETS_DIR / f"{game}.json"
    if not path.exists():
        raise KeyError(f"unknown game '{game}' (known: {', '.join(available_games())})")
    return path


@dataclass
class Field:
    name: str
    addr: int | None
    type: str
    size: int = 4
    desc: str = ""


@dataclass
class Function:
    name: str
    addr: int | None
    suggested: int | None
    desc: str = ""


def _parse_addr(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    return int(str(value), 0)


class Offsets:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.raw = json.loads(self.path.read_text())
        self.game = self.raw.get("game", self.path.stem)
        self.short = self.raw.get("short", self.path.stem)
        self.xex = self.raw.get("xex", "default_mp.xex")
        self.title_update = self.raw.get("title_update", "?")
        self.fields: dict[str, Field] = {}
        for name, f in self.raw.get("fields", {}).items():
            if f["type"] not in TYPES:
                raise ValueError(f"{name}: unknown type {f['type']!r}")
            self.fields[name] = Field(name, _parse_addr(f.get("addr")), f["type"],
                                      f.get("size", 4), f.get("desc", ""))
        self.functions: dict[str, Function] = {}
        for name, f in self.raw.get("functions", {}).items():
            self.functions[name] = Function(name, _parse_addr(f.get("addr")),
                                            _parse_addr(f.get("suggested")), f.get("desc", ""))

    def _save(self) -> None:
        self.path.write_text(json.dumps(self.raw, indent=2) + "\n")

    # -- fields ---------------------------------------------------------------
    def get(self, name: str) -> Field:
        if name not in self.fields:
            raise KeyError(f"unknown field '{name}' (known: {', '.join(self.fields)})")
        field = self.fields[name]
        if field.addr is None:
            raise LookupError(f"'{name}' has no address yet; use 'wizard {name}' or 'setaddr' first")
        return field

    def set_addr(self, name: str, addr: int) -> None:
        if name not in self.fields:
            raise KeyError(f"unknown field '{name}'")
        self.fields[name].addr = addr
        self.raw["fields"][name]["addr"] = f"0x{addr:08X}"
        self._save()

    # -- functions ------------------------------------------------------------
    def func(self, name: str) -> Function:
        if name not in self.functions:
            raise KeyError(f"unknown function '{name}' (known: {', '.join(self.functions) or 'none'})")
        fn = self.functions[name]
        if fn.addr is None:
            hint = " (try 'setup' to check the suggested address)" if fn.suggested else ""
            raise LookupError(f"{name} has no address yet; use 'setfunc {name} <addr>'{hint}")
        return fn

    def set_func_addr(self, name: str, addr: int) -> None:
        if name not in self.functions:
            raise KeyError(f"unknown function '{name}'")
        self.functions[name].addr = addr
        self.raw["functions"][name]["addr"] = f"0x{addr:08X}"
        self._save()


def read_field(xb: Xbdm, field: Field):
    if field.type == "string":
        return xb.read_string(field.addr, field.size)
    if field.type == "i32":
        return xb.read_i32(field.addr)
    if field.type == "u32":
        return xb.read_u32(field.addr)
    if field.type == "float":
        return xb.read_float(field.addr)
    return xb.read(field.addr, field.size).hex().upper()


def write_field(xb: Xbdm, field: Field, value: str) -> None:
    if field.type == "string":
        xb.write_string(field.addr, value, field.size)
    elif field.type == "i32":
        xb.write_i32(field.addr, int(value, 0))
    elif field.type == "u32":
        xb.write_u32(field.addr, int(value, 0))
    elif field.type == "float":
        xb.write_float(field.addr, float(value))
    else:
        data = bytes.fromhex(value)
        if len(data) != field.size:
            raise ValueError(f"expected {field.size} bytes")
        xb.write(field.addr, data)


_COLOR = re.compile(r"\^[0-9]")


def strip_colors(name: str) -> str:
    """'^1Red^7Name' -> 'RedName'."""
    return _COLOR.sub("", name)
