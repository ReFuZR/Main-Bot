"""Interactive shell for BO2 and the other Xbox 360 CoD games on an RGH console."""

from __future__ import annotations

import argparse
import cmd
import shlex
import sys
import time
from pathlib import Path

from .data import CBUF, FIELDS, GAMES, Catalog, Profile, strip_colors
from .xbdm import Xbdm, XbdmError, encode

SCAN = (0x82000000, 0x86000000)
FIND_KIND = {"string": "str", "bytes": "hex"}  # field type -> find type, where they differ
BANNER = r"""
  ___  ___ ___   ___  ___ _  _   _____         _
 | _ )/ _ \_  ) | _ \/ __| || | |_   _|__  ___| |
 | _ \ (_) / /  |   / (_ | __ |   | |/ _ \/ _ \ |
 |___/\___/___| |_|_\\___|_||_|   |_|\___/\___/_|
   just for fun - offline / private matches - Xbox 360 CoD
Type 'help' for commands.
"""


def printable(data: bytes) -> str:
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data)


def hexdump(addr: int, data: bytes) -> str:
    return "\n".join(f"{addr + i:08X}  {data[i:i + 16].hex(' ').upper():<47}  {printable(data[i:i + 16])}"
                     for i in range(0, len(data), 16))


def progress():
    last = [-1]

    def show(done: int, total: int) -> None:
        pct = done * 100 // total
        if sys.stdout.isatty() and pct != last[0]:
            last[0] = pct
            print(f"\r  scanning... {pct:3d}%", end="\n" if done >= total else "", flush=True)

    return show


class Shell(cmd.Cmd):
    def __init__(self, xb: Xbdm, profile: Profile, catalog: Catalog | None = None):
        super().__init__()
        self.xb, self.p, self.cat = xb, profile, catalog or Catalog()
        self.prompt, self.hits, self.kind, self.warned = f"{profile.short}> ", [], "", False
        self.ask = input  # swapped out in tests

    def onecmd(self, line):
        try:
            return super().onecmd(line)
        except (XbdmError, ValueError, KeyError, LookupError, OSError) as e:
            print(f"error: {e.args[0] if isinstance(e, KeyError) else e}")
        except KeyboardInterrupt:
            print("\ninterrupted")

    def emptyline(self):
        pass

    def default(self, line):
        print(f"unknown command: {line.split()[0]} (try 'help')")

    def _ask(self, prompt: str) -> str:
        try:
            return self.ask(prompt).strip()
        except EOFError:
            return "quit"

    def _field(self, name: str) -> tuple[int, str, int]:
        if name not in FIELDS:
            raise KeyError(f"unknown field '{name}' (known: {', '.join(FIELDS)})")
        return self.p.addr(name), FIELDS[name][0], FIELDS[name][1]

    # -- console ----------------------------------------------------------------
    def do_info(self, _):
        """info - console name, running game and loaded profile"""
        xex = self.xb.xex()
        print(f"console : {self.xb.name()}\nrunning : {xex}\n"
              f"profile : {self.p.info['game']} ({self.p.info['tu']}) - {self.p.path.name}")
        if "default_mp.xex" not in xex.lower():
            print("warning : doesn't look like multiplayer (default_mp.xex); wrong game or mode?")

    def do_reboot(self, arg):
        """reboot [cold] - reboot the console"""
        self.xb.reboot(cold=arg.strip() == "cold")
        print("reboot sent; reconnect when the console is back")
        return True

    def do_raw(self, arg):
        """raw <xbdm command> - send any XBDM command, e.g. 'raw systime'"""
        code, msg = self.xb.send(arg)
        print(f"{code}- {msg}", *(f"  {l}" for l in (self.xb.lines() if code in (202, 211) else [])), sep="\n")

    # -- your player's values ---------------------------------------------------
    def do_fields(self, _):
        """fields - list the fields and their addresses"""
        for name, (kind, _, desc) in FIELDS.items():
            where = f"0x{self.p.addrs[name]:08X}" if name in self.p.addrs else "(not found)"
            print(f"  {name:<12} {kind:<6} {where:<12} {desc.format(**self.p.info)}")

    def do_get(self, arg):
        """get <field> - read a field, e.g. 'get name'"""
        name = arg.strip()
        value = self.xb.get(*self._field(name))
        print(f"{name} = {value!r}")
        if isinstance(value, str) and "^" in value:
            print(f"  (plain: {strip_colors(value)!r})")

    def do_set(self, arg):
        """set <field> <value> - write a field, e.g. 'set name ^1Red^7Guy'"""
        name, _, value = arg.strip().partition(" ")
        if not value:
            raise ValueError("usage: set <field> <value>")
        addr, kind, size = self._field(name)
        self.xb.put(addr, kind, value, size)
        print(f"{name} -> {self.xb.get(addr, kind, size)!r}")

    def do_freeze(self, arg):
        """freeze <field> <value> [seconds] - keep re-writing a value until Ctrl+C"""
        parts = shlex.split(arg)
        if len(parts) < 2:
            raise ValueError("usage: freeze <field> <value> [seconds]")
        addr, kind, size = self._field(parts[0])
        interval = float(parts[2]) if len(parts) > 2 else 0.5
        print(f"freezing {parts[0]} = {parts[1]} every {interval}s (Ctrl+C to stop)")
        try:
            while True:
                self.xb.put(addr, kind, parts[1], size)
                time.sleep(interval)
        except KeyboardInterrupt:
            print("\nstopped")

    def do_setaddr(self, arg):
        """setaddr <field> <addr> - save a field address by hand"""
        name, addr = arg.split()
        if name not in FIELDS:
            raise KeyError(f"unknown field '{name}'")
        self.p.save(name, int(addr, 0))
        print(f"saved {name} = 0x{int(addr, 0):08X}")

    # -- finding addresses ------------------------------------------------------
    def _scan(self, kind: str, value: str, start: int, end: int) -> list[int]:
        pattern = encode(kind, value)
        print(f"searching 0x{start:08X}-0x{end:08X} for {pattern.hex().upper()}")
        return self.xb.scan(start, end, pattern, progress=progress())

    def _refine(self, kind: str, value: str, hits: list[int]) -> list[int]:
        pattern, kept = encode(kind, value), []
        for addr in hits:
            try:
                if self.xb.read(addr, len(pattern)) == pattern:
                    kept.append(addr)
            except XbdmError:
                pass
        return kept

    def _show_hits(self):
        print(f"{len(self.hits)} hit(s)", *(f"  0x{a:08X}" for a in self.hits[:20]), sep="\n")
        if len(self.hits) > 20:
            print("  ... use 'refine' to narrow down")
        if len(self.hits) == 1:
            print(f"one hit, save it with: setaddr <field> 0x{self.hits[0]:08X}")

    def do_find(self, arg):
        """find <type> <value> [start end] - scan memory (type: hex/u32/i32/float/str)

        Example: 'find str MyGamertag'. Then change the value in game and 'refine'."""
        parts = shlex.split(arg)
        if len(parts) < 2:
            raise ValueError("usage: find <type> <value> [start end]")
        start, end = (int(parts[2], 0), int(parts[3], 0)) if len(parts) >= 4 else SCAN
        self.kind, self.hits = parts[0], self._scan(parts[0], parts[1], start, end)
        self._show_hits()

    def do_refine(self, arg):
        """refine <value> - keep only previous hits that now hold <value>"""
        if not self.hits:
            raise ValueError("nothing to refine; run 'find' first")
        self.hits = self._refine(self.kind, arg.strip(), self.hits)
        self._show_hits()

    def do_wizard(self, arg):
        """wizard [field ...] [--range start end] - guided search that finds and saves addresses

        Does every field without an address (or the ones you name). Type 'skip'
        to move to the next field, 'quit' to stop."""
        parts, (start, end) = shlex.split(arg), SCAN
        if "--range" in parts:
            i = parts.index("--range")
            start, end = int(parts[i + 1], 0), int(parts[i + 2], 0)
            del parts[i:i + 3]
        for name in parts:
            if name not in FIELDS:
                raise KeyError(f"unknown field '{name}'")
        names = parts or [n for n in FIELDS if n not in self.p.addrs]
        if not names:
            return print("every field already has an address (name fields to redo them)")
        print(f"wizard: {len(names)} field(s) to find: {', '.join(names)}\n"
              "type 'skip' to move to the next field, 'quit' to stop\n")
        found = []
        for name in names:
            result = self._wizard_field(name, start, end)
            if result == "quit":
                break
            if result:
                found.append(name)
        missing = [n for n in names if n not in found]
        print(f"\nwizard done: found {len(found)}" + (f" ({', '.join(found)})" if found else ""))
        if missing:
            print(f"not found: {', '.join(missing)} (run 'wizard {' '.join(missing)}' to retry)")

    def _wizard_field(self, name: str, start: int, end: int):
        """True if saved, False if skipped, 'quit' to stop the wizard."""
        ftype, _, desc = FIELDS[name]
        kind, hits = FIND_KIND.get(ftype, ftype), None
        print(f"== {name} ({ftype}) - {desc.format(**self.p.info)}")
        answer = self._ask(f"  current value of {name} in game: ")
        while True:
            if answer in ("skip", "quit"):
                print()
                return answer == "quit" and "quit"
            if hits and answer.startswith("pick "):
                try:
                    hits = [hits[int(answer.split()[1]) - 1]]
                except (ValueError, IndexError):
                    print("  invalid pick")
            else:
                hits = self._scan(kind, answer, start, end) if hits is None else self._refine(kind, answer, hits)
            if not hits:
                print("  no matches. Check the value (and the scan range) and retry later.")
                return False
            if len(hits) == 1:
                self.p.save(name, hits[0])
                print(f"  found it: {name} = 0x{hits[0]:08X} (saved)\n")
                return True
            print(f"  {len(hits)} matches")
            if len(hits) <= 8:
                for i, a in enumerate(hits, 1):
                    print(f"   {i}) 0x{a:08X}  {self._preview(a)}")
                print("  type 'pick N' to choose one of these, or keep narrowing:")
            answer = self._ask(f"  change {name} in game, then type the new value: ")

    def _preview(self, addr: int) -> str:
        try:
            raw = self.xb.read(addr, 16)
        except XbdmError:
            return "(unreadable)"
        return f"{raw.hex(' ').upper()}  {printable(raw)}"

    # -- raw memory -------------------------------------------------------------
    def do_peek(self, arg):
        """peek <addr> [length] - hexdump memory (default 64 bytes)"""
        parts = arg.split()
        addr = int(parts[0], 0)
        print(hexdump(addr, self.xb.read(addr, int(parts[1], 0) if len(parts) > 1 else 64)))

    def do_poke(self, arg):
        """poke <addr> <type> <value> - write memory (type: hex/u32/i32/float/str)"""
        parts = shlex.split(arg)
        if len(parts) != 3:
            raise ValueError("usage: poke <addr> <type> <value>")
        self.xb.write(int(parts[0], 0), encode(parts[1], parts[2]))
        print("ok")

    # -- game console commands (JRPC2) ------------------------------------------
    def do_cmd(self, arg):
        """cmd <console command> - run a built-in game command, e.g. 'cmd cg_fov 90'

        Needs the JRPC2 plugin and the Cbuf_AddText address (see 'setup').
        Join several commands with ';'."""
        commands = [c.strip() for c in arg.split(";") if c.strip()]
        if not commands:
            raise ValueError("usage: cmd <console command>")
        self._run(commands)

    def _run(self, commands: list[str]) -> None:
        addr = self.p.addr(CBUF)
        for c in commands:
            e = self.cat.lookup(c.split()[0])
            if e is None:
                print(f"  note: '{c.split()[0]}' isn't in the catalog; sending anyway")
            elif self.p.short not in e["games"]:
                print(f"  note: '{e['name']}' isn't listed for {self.p.short}; sending anyway")
            elif "H" in e["flags"] and not self.warned:
                print("  note: host settings affect everyone in your lobby - use a private match")
                self.warned = True
            self.xb.call(addr, 0, c + "\n")
            print(f"  > {c}")

    def do_commands(self, arg):
        """commands [search] - list built-in commands for this game, e.g. 'commands fov'

        Searches names and descriptions, or a category (view, hud, player, world,
        match, misc). H = affects the lobby when you host, C = needs sv_cheats 1."""
        entries = sorted(self.cat.search(self.p.short, arg.strip()), key=lambda e: (e["cat"], e["name"]))
        if not entries:
            return print("no matching commands")
        width, cat = max(len(e["name"]) for e in entries), None
        for e in entries:
            if e["cat"] != cat:
                cat = e["cat"]
                print(f"[{cat}]")
            default = f" (default {e['default']})" if "default" in e else ""
            print(f"  {e['name']:<{width}} {e['flags']:<2} {e['desc']}{default}")
        print(f"{len(entries)} command(s). Example: cmd {entries[0].get('example', entries[0]['name'])}")

    def do_presets(self, _):
        """presets - list command presets"""
        for name, p in self.cat.presets.items():
            print(f"  {name:<12} {p['desc']}\n  {'':<12} {'; '.join(p['commands'])}")

    def do_preset(self, arg):
        """preset <name> - run a group of commands, e.g. 'preset thirdperson'"""
        run, skipped = self.cat.preset(arg.strip(), self.p.short)
        if skipped:
            print(f"  skipping (not in {self.p.short}): {', '.join(skipped)}")
        self._run(run)

    def do_funcs(self, _):
        """funcs - show the Cbuf_AddText address"""
        sugg = ", ".join(self.p.info.get("cbuf", []))
        where = f"0x{self.p.addrs[CBUF]:08X}" if CBUF in self.p.addrs else "(not set)" + (f"  suggested {sugg}" if sugg else "")
        print(f"  {CBUF}  {where}  - runs console commands")

    def do_setfunc(self, arg):
        """setfunc Cbuf_AddText <addr> [--force] - save the function address after a sanity check"""
        parts = arg.split()
        if len(parts) < 2 or parts[0] != CBUF:
            raise ValueError(f"usage: setfunc {CBUF} <addr> [--force]")
        addr = int(parts[1], 0)
        if "--force" not in parts and not self.xb.is_function(addr):
            raise ValueError(f"0x{addr:08X} doesn't start like a function; double-check it or add --force")
        self.p.save(CBUF, addr)
        print(f"saved {CBUF} = 0x{addr:08X}")

    def do_setup(self, _):
        """setup - check the Cbuf_AddText address, or try the suggested ones"""
        if CBUF in self.p.addrs:
            ok = self.xb.is_function(self.p.addrs[CBUF])
            return print(f"  {CBUF}: 0x{self.p.addrs[CBUF]:08X} {'looks good' if ok else 'does NOT look like a function'}")
        suggestions = [int(a, 16) for a in self.p.info.get("cbuf", [])]
        if not suggestions:
            print(f"  no suggested {CBUF} address for {self.p.short}; find it yourself and use 'setfunc {CBUF} <addr>'")
        for addr in suggestions:
            if not self.xb.is_function(addr):
                print(f"  suggested 0x{addr:08X} doesn't look like a function on your console (different title update?)")
                continue
            print(f"  suggested 0x{addr:08X} looks like a function start.\n"
                  "  It's community-reported and unverified; a wrong address can crash the game.\n"
                  "  Test it with something harmless right after: cmd cg_drawFPS 1")
            if self._ask("  save it? [y/N] ").lower() in ("y", "yes"):
                self.p.save(CBUF, addr)
                return print("  saved.")

    def do_quit(self, _):
        """quit - disconnect"""
        return True

    do_exit = do_EOF = do_quit


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="bo2tool", description="BO2 / 360 CoD RGH tool over XBDM")
    ap.add_argument("host", nargs="?", help="console IP address")
    ap.add_argument("--port", type=int, default=730)
    ap.add_argument("--game", default="bo2", choices=GAMES, help="game profile (default bo2)")
    ap.add_argument("--offsets", type=Path, help="addresses file (default offsets/<game>.json)")
    ap.add_argument("--list-games", action="store_true", help="list game profiles and exit")
    ap.add_argument("-c", "--command", action="append", help="run a command and exit (repeatable)")
    args = ap.parse_args(argv)
    if args.list_games:
        print("\n".join(f"  {k:<8} {v['game']}" for k, v in GAMES.items()))
        return 0
    if not args.host:
        ap.error("host is required")
    xb = Xbdm(args.host, args.port)
    try:
        xb.connect()
    except (OSError, XbdmError) as e:
        print(f"could not connect to {args.host}:{args.port}: {e}\n"
              "is the console on, the dashboard loaded, and the XBDM plugin enabled?")
        return 1
    shell = Shell(xb, Profile(args.game, args.offsets))
    try:
        for c in args.command or []:
            shell.onecmd(c)
        if not args.command:
            print(BANNER)
            shell.onecmd("info")
            shell.cmdloop()
    finally:
        xb.close()
    return 0
