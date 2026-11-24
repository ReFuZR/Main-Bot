"""Interactive shell for poking at BO2 on an RGH console."""

from __future__ import annotations

import argparse
import cmd
import shlex
import struct
import sys
import time
from pathlib import Path

from .game import BO2_XEX_HINT, Offsets, read_field, strip_colors, write_field
from .xbdm import XBDM_PORT, Xbdm, XbdmError

DEFAULT_OFFSETS = Path(__file__).resolve().parent.parent / "offsets.json"
DEFAULT_SCAN = (0x82000000, 0x86000000)

BANNER = r"""
  ___  ___ ___   ___  ___ _  _   _____         _
 | _ )/ _ \_  ) | _ \/ __| || | |_   _|__  ___| |
 | _ \ (_) / /  |   / (_ | __ |   | |/ _ \/ _ \ |
 |___/\___/___| |_|_\\___|_||_|   |_|\___/\___/_|
        just for fun - offline / private matches
Type 'help' for commands.
"""


def hexdump(addr: int, data: bytes) -> str:
    lines = []
    for i in range(0, len(data), 16):
        row = data[i : i + 16]
        hx = " ".join(f"{b:02X}" for b in row)
        asc = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
        lines.append(f"{addr + i:08X}  {hx:<47}  {asc}")
    return "\n".join(lines)


def encode_value(kind: str, value: str) -> bytes:
    if kind == "hex":
        return bytes.fromhex(value)
    if kind == "u32":
        return struct.pack(">I", int(value, 0) & 0xFFFFFFFF)
    if kind == "i32":
        return struct.pack(">i", int(value, 0))
    if kind == "float":
        return struct.pack(">f", float(value))
    if kind == "str":
        return value.encode("latin-1")
    raise ValueError(f"unknown type {kind!r} (hex/u32/i32/float/str)")


def _make_progress():
    last = [-1]

    def progress(done: int, total: int) -> None:
        if not sys.stdout.isatty():
            return
        pct = done * 100 // total
        if pct != last[0]:
            last[0] = pct
            sys.stdout.write(f"\r  scanning... {pct:3d}%")
            sys.stdout.flush()
        if done >= total:
            sys.stdout.write("\n")

    return progress


class Shell(cmd.Cmd):
    prompt = "bo2> "

    def __init__(self, xb: Xbdm, offsets: Offsets):
        super().__init__()
        self.xb = xb
        self.offsets = offsets
        self.last_hits: list[int] = []
        self.last_kind = ""

    # -- plumbing -------------------------------------------------------------
    def onecmd(self, line):
        try:
            return super().onecmd(line)
        except (XbdmError, ValueError, KeyError, LookupError, OSError) as e:
            print(f"error: {e}")
        except KeyboardInterrupt:
            print("\ninterrupted")

    def emptyline(self):
        pass

    def default(self, line):
        print(f"unknown command: {line.split()[0]} (try 'help')")

    # -- console --------------------------------------------------------------
    def do_info(self, _):
        """info - console name and the running game"""
        xex = self.xb.running_xex()
        print(f"console : {self.xb.console_name()}")
        print(f"running : {xex}")
        if BO2_XEX_HINT not in xex.lower():
            print(f"warning : doesn't look like BO2 multiplayer ({BO2_XEX_HINT})")

    def do_reboot(self, arg):
        """reboot [cold] - reboot the console"""
        self.xb.reboot(cold=arg.strip() == "cold")
        print("reboot sent; reconnect when the console is back")
        return True

    def do_raw(self, arg):
        """raw <xbdm command> - send any XBDM command, e.g. 'raw systime'"""
        code, msg = self.xb.send(arg)
        print(f"{code}- {msg}")
        if code in (202, 211):
            for line in self.xb._read_multiline():
                print(f"  {line}")

    # -- named fields ---------------------------------------------------------
    def do_fields(self, _):
        """fields - list fields from offsets.json"""
        for f in self.offsets.fields.values():
            where = f"0x{f.addr:08X}" if f.addr is not None else "(not found)"
            print(f"  {f.name:<10} {f.type:<6} {where:<12} {f.desc}")

    def do_get(self, arg):
        """get <field> - read a field, e.g. 'get name'"""
        field = self.offsets.get(arg.strip())
        value = read_field(self.xb, field)
        print(f"{field.name} = {value!r}")
        if field.type == "string" and "^" in value:
            print(f"  (plain: {strip_colors(value)!r})")

    def do_set(self, arg):
        """set <field> <value> - write a field, e.g. 'set name ^1Red^7Guy'"""
        name, _, value = arg.strip().partition(" ")
        if not value:
            raise ValueError("usage: set <field> <value>")
        field = self.offsets.get(name)
        write_field(self.xb, field, value)
        print(f"{name} -> {read_field(self.xb, field)!r}")

    def do_freeze(self, arg):
        """freeze <field> <value> [seconds] - keep re-writing a value until Ctrl+C"""
        parts = shlex.split(arg)
        if len(parts) < 2:
            raise ValueError("usage: freeze <field> <value> [seconds]")
        field = self.offsets.get(parts[0])
        interval = float(parts[2]) if len(parts) > 2 else 0.5
        print(f"freezing {field.name} = {parts[1]} every {interval}s (Ctrl+C to stop)")
        try:
            while True:
                write_field(self.xb, field, parts[1])
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nstopped")

    def do_setaddr(self, arg):
        """setaddr <field> <addr> - save an address into offsets.json"""
        name, addr = arg.split()
        self.offsets.set_addr(name, int(addr, 0))
        print(f"saved {name} = 0x{int(addr, 0):08X}")

    # -- finding addresses ----------------------------------------------------
    def do_find(self, arg):
        """find <type> <value> [start end] - scan memory for a value

        type is hex/u32/i32/float/str. Example: 'find str MyGamertag'.
        After that, change the value in game and use 'refine' to narrow it down."""
        parts = shlex.split(arg)
        if len(parts) < 2:
            raise ValueError("usage: find <type> <value> [start end]")
        kind, value = parts[0], parts[1]
        start, end = DEFAULT_SCAN
        if len(parts) >= 4:
            start, end = int(parts[2], 0), int(parts[3], 0)
        pattern = encode_value(kind, value)
        print(f"searching 0x{start:08X}-0x{end:08X} for {pattern.hex().upper()}")
        self.last_hits = self.xb.scan(start, end, pattern, progress=_make_progress())
        self.last_kind = kind
        self._show_hits()

    def do_refine(self, arg):
        """refine <value> - keep only previous hits that now hold <value>"""
        if not self.last_hits:
            raise ValueError("nothing to refine; run 'find' first")
        pattern = encode_value(self.last_kind, arg.strip())
        kept = []
        for addr in self.last_hits:
            try:
                if self.xb.read(addr, len(pattern)) == pattern:
                    kept.append(addr)
            except XbdmError:
                pass
        self.last_hits = kept
        self._show_hits()

    def _show_hits(self):
        print(f"{len(self.last_hits)} hit(s)")
        for addr in self.last_hits[:20]:
            print(f"  0x{addr:08X}")
        if len(self.last_hits) > 20:
            print("  ... use 'refine' to narrow down")
        if len(self.last_hits) == 1:
            print("one hit, save it with: setaddr <field> " f"0x{self.last_hits[0]:08X}")

    # -- raw memory -----------------------------------------------------------
    def do_peek(self, arg):
        """peek <addr> [length] - hexdump memory (default 64 bytes)"""
        parts = arg.split()
        addr = int(parts[0], 0)
        length = int(parts[1], 0) if len(parts) > 1 else 64
        print(hexdump(addr, self.xb.read(addr, length)))

    def do_poke(self, arg):
        """poke <addr> <type> <value> - write memory, type is hex/u32/i32/float/str"""
        parts = shlex.split(arg)
        if len(parts) != 3:
            raise ValueError("usage: poke <addr> <type> <value>")
        addr = int(parts[0], 0)
        self.xb.write(addr, encode_value(parts[1], parts[2]))
        print("ok")

    def do_quit(self, _):
        """quit - disconnect"""
        return True

    do_exit = do_quit
    do_EOF = do_quit


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bo2tool", description="BO2 RGH tool over XBDM")
    ap.add_argument("host", help="console IP address")
    ap.add_argument("--port", type=int, default=XBDM_PORT)
    ap.add_argument("--offsets", type=Path, default=DEFAULT_OFFSETS)
    ap.add_argument("-c", "--command", action="append",
                    help="run a command and exit (can be repeated)")
    args = ap.parse_args(argv)

    offsets = Offsets(args.offsets)
    xb = Xbdm(args.host, args.port)
    try:
        xb.connect()
    except (OSError, XbdmError) as e:
        print(f"could not connect to {args.host}:{args.port}: {e}")
        print("is the console on, RGH dashboard loaded, and XBDM plugin enabled?")
        return 1

    shell = Shell(xb, offsets)
    try:
        if args.command:
            for c in args.command:
                shell.onecmd(c)
        else:
            print(BANNER)
            shell.onecmd("info")
            shell.cmdloop()
    finally:
        xb.close()
    return 0
