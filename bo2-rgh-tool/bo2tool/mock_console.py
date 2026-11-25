"""A fake XBDM + JRPC2 console for trying the tool without an Xbox.

    python -m bo2tool.mock_console --port 7300
    python -m bo2tool 127.0.0.1 --port 7300

It plays BO2 with "MockPlayer" at NAME, prestige 10 at PRESTIGE, FOV 65.0 at FOV,
and a fake Cbuf_AddText at CBUF that records (and prints) each command it gets.
Memory outside 0x82000000-0x86000000 reads as '??' like unmapped pages.
"""

from __future__ import annotations

import argparse
import re
import socket
import socketserver
import struct
import threading

BASE, SIZE = 0x82000000, 0x04000000
NAME, PRESTIGE, FOV, CBUF = 0x83551E00, 0x83551E40, 0x83551E44, 0x824015E0


class Memory:
    def __init__(self):
        self.data = bytearray(SIZE)
        for addr, raw in ((NAME, b"MockPlayer\0"), (PRESTIGE, struct.pack(">i", 10)),
                          (FOV, struct.pack(">f", 65.0)), (CBUF, struct.pack(">I", 0x7D8802A6))):  # mflr r12
            self.write(addr, raw)

    def read_hex(self, addr: int, n: int) -> str:
        lo, hi = max(addr, BASE), min(addr + n, BASE + SIZE)
        if lo >= hi:
            return "??" * n
        return "??" * (lo - addr) + self.data[lo - BASE:hi - BASE].hex().upper() + "??" * (addr + n - hi)

    def write(self, addr: int, raw: bytes) -> int:
        n = max(0, min(len(raw), BASE + SIZE - addr)) if addr >= BASE else 0
        if n:
            self.data[addr - BASE:addr - BASE + n] = raw[:n]
        return n


def parse_jrpc(line: str) -> tuple[int, list]:
    """Decode a consolefeatures call into (address, args)."""
    t = re.search(r'params="(.*)"', line).group(1).split("\\")
    if t[0] != "A":
        raise ValueError("bad params")
    args = []
    for i in range(3, 3 + 2 * int(t[2]), 2):
        kind, value = t[i], t[i + 1]
        if kind == "1":
            args.append(int(value))
        elif kind == "3":
            args.append(float(value))
        elif kind.startswith("7/") and len(bytes.fromhex(value)) == int(kind[2:]):
            args.append(bytes.fromhex(value))
        else:
            raise ValueError(f"bad argument {kind}")
    return int(t[1], 16), args


class Handler(socketserver.StreamRequestHandler):
    def setup(self):
        self.request.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        super().setup()

    def send(self, *lines: str) -> None:
        self.wfile.write(b"".join(l.encode("latin-1") + b"\r\n" for l in lines))

    def handle(self):
        mem = self.server.mem
        self.send("201- connected")
        for raw in self.rfile:
            line = raw.decode("latin-1").strip()
            cmd = line.split()[0].lower() if line else ""
            args = dict(t.partition("=")[::2] for t in line.split()[1:])
            if cmd == "bye":
                return self.send("200- bye")
            elif cmd == "dbgname":
                self.send("200- MockXbox")
            elif cmd == "xbeinfo":
                self.send("202- multiline response follows", "timestamp=0x50a3c1f0 checksum=0x00000000",
                          'name="\\Device\\Harddisk0\\Partition1\\Content\\BO2\\default_mp.xex"', ".")
            elif cmd == "magicboot":
                self.send("200- OK")
            elif cmd == "getmem":
                data = mem.read_hex(int(args["addr"], 16), int(args["length"], 16))
                self.send("211- memory data follows", *(data[i:i + 256] for i in range(0, len(data), 256)), ".")
            elif cmd == "setmem":
                n = mem.write(int(args["addr"], 16), bytes.fromhex(args["data"]))
                self.send(f"200- set {n} bytes" if n else "404- memory not mapped")
            elif cmd == "consolefeatures":
                self.send(self.jrpc(line))
            elif cmd:
                self.send("407- unknown command")

    def jrpc(self, line: str) -> str:
        if "buf_addr=" in line:  # polling a pending call
            return "200- 0"
        try:
            addr, args = parse_jrpc(line)
        except (ValueError, AttributeError, IndexError) as e:
            return f"200- error={e}"
        if addr != CBUF or len(args) != 2 or not isinstance(args[1], bytes):
            return f"200- error=no function at 0x{addr:08X}"
        text = args[1].rstrip(b"\0").decode("latin-1").strip()
        self.server.executed.append(text)
        print(f"[mock] Cbuf_AddText({args[0]}, {text!r})")
        return "200- buf_addr=0x40001000"  # pretend it's still running, so the client polls


class MockConsole(socketserver.ThreadingTCPServer):
    allow_reuse_address = daemon_threads = True

    def __init__(self, addr=("127.0.0.1", 0)):
        self.mem, self.executed = Memory(), []
        super().__init__(addr, Handler)

    @property
    def port(self) -> int:
        return self.server_address[1]

    def start_background(self) -> "MockConsole":
        threading.Thread(target=self.serve_forever, daemon=True).start()
        return self


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="fake XBDM console")
    ap.add_argument("--port", type=int, default=7300)
    srv = MockConsole(("127.0.0.1", ap.parse_args().port))
    print(f"mock console on 127.0.0.1:{srv.port} (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
