"""Cheat Engine style memory search: an exact value, or an unknown value narrowed down by how it changes."""

from __future__ import annotations

import re
import struct
from array import array

from .xbdm import FMT, Xbdm, XbdmError, encode

CHUNK = 0x10000
OPS = ("same", "changed", "more", "less")


class Search:
    """find: start(value or '?'), then refine(new value or same/changed/more/less) until one hit is left."""

    def __init__(self, xb: Xbdm, kind: str):
        self.xb, self.kind = xb, kind
        self.lo, self.width = 0, 4
        self.snap: dict[int, bytes] = {}  # chunk start -> last memory seen there
        self.hits: array | None = None    # None = every 4-byte aligned address in snap (unknown start)

    def _base(self, addr: int) -> int:
        return self.lo + (addr - self.lo) // CHUNK * CHUNK

    def _at(self, snap: dict[int, bytes], addr: int) -> bytes:
        base = self._base(addr)
        data = snap.get(base, b"")[addr - base:addr - base + self.width]
        return data + snap.get(base + CHUNK, b"")[:self.width - len(data)]  # value crossing a chunk edge

    def _candidates(self):
        if self.hits is not None:
            return self.hits
        return (a for base, data in self.snap.items() for a in range(base + -base % 4, base + len(data) - 3, 4))

    @property
    def count(self) -> int:
        return len(self.hits) if self.hits is not None else sum(len(d) // 4 for d in self.snap.values())

    def value(self, addr: int):
        raw = self._at(self.snap, addr)
        return struct.unpack(FMT[self.kind], raw)[0] if self.kind in FMT else raw

    def start(self, value: str, lo: int, hi: int, progress=None) -> int:
        """Remember [lo, hi) and find `value`, or keep every address for '?' (number types only)."""
        if value == "?" and self.kind not in FMT:
            raise ValueError("an unknown-value search needs a number type (i32/u32/float)")
        self.lo, self.snap = lo, {}
        for a in range(lo, hi, CHUNK):
            try:
                self.snap[a] = self.xb.read(a, min(CHUNK, hi - a))
            except XbdmError:
                pass  # unmapped: skip
            if progress:
                progress(min(a + CHUNK, hi) - lo, hi - lo)
        if value == "?":
            self.hits, self.width = None, 4
            return self.count
        pattern = encode(self.kind, value)
        self.width, find = len(pattern), re.compile(b"(?=" + re.escape(pattern) + b")")
        self.hits = array("I")
        for base, data in self.snap.items():
            tail = self.snap.get(base + CHUNK, b"")[:len(pattern) - 1]
            self.hits.extend(base + m.start() for m in find.finditer(data + tail) if m.start() < len(data))
        self._trim()
        return self.count

    def refine(self, answer: str) -> int:
        """Keep hits that now hold `answer`, or that are the same/changed/more/less than last time."""
        if answer in ("more", "less") and self.kind not in FMT:
            raise ValueError("more/less need a number type (i32/u32/float)")
        target = None if answer in OPS else encode(self.kind, answer)
        if target is not None and len(target) != self.width:
            raise ValueError(f"new value must be {self.width} bytes long like the first one")
        new = {}
        for base, old in self.snap.items():  # re-read only chunks that still hold hits
            try:
                new[base] = self.xb.read(base, len(old))
            except XbdmError:
                pass
        fmt = FMT.get(self.kind)
        kept = array("I")
        for addr in self._candidates():
            before, now = self._at(self.snap, addr), self._at(new, addr)
            if len(now) < self.width:
                continue
            if target is not None:
                ok = now == target
            elif answer == "same":
                ok = now == before
            elif answer == "changed":
                ok = now != before
            else:
                a, b = struct.unpack(fmt, before)[0], struct.unpack(fmt, now)[0]
                ok = b > a if answer == "more" else b < a
            if ok:
                kept.append(addr)
        self.snap, self.hits = new, kept
        self._trim()
        return self.count

    def _trim(self) -> None:
        """Forget chunks with no hits left, to keep memory use down."""
        keep = {self._base(a) for a in self.hits} | {self._base(a) + CHUNK for a in self.hits}
        self.snap = {b: d for b, d in self.snap.items() if b in keep}
