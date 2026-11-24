"""A fake XBDM console for trying the tool without an Xbox.

    python -m bo2tool.mock_console            # listens on 127.0.0.1:7300
    python -m bo2tool 127.0.0.1 --port 7300

It pretends BO2 is running and plants a few values in memory:
  0x83551E00  name      "MockPlayer"
  0x83551E40  prestige  10 (big-endian i32)
  0x83551E44  fov       65.0 (big-endian float)
  0x824015E0  a function prologue, standing in for Cbuf_AddText
Memory outside 0x82000000-0x86000000 reads back as '??' like unmapped pages.

It also answers JRPC2 'consolefeatures' calls. Calls to the fake
Cbuf_AddText are printed and recorded in `server.executed`.
"""

from __future__ import annotations

import argparse
import socket
import re
import socketserver
import struct
import threading

MEM_BASE = 0x82000000
MEM_SIZE = 0x04000000

NAME_ADDR = 0x83551E00
PRESTIGE_ADDR = 0x83551E40
FOV_ADDR = 0x83551E44
CBUF_ADDR = 0x824015E0


class FakeMemory:
    def __init__(self):
        # Sparse: only pages that were touched are stored.
        self.pages: dict[int, bytearray] = {}
        self.lock = threading.Lock()

    def _page(self, addr: int) -> bytearray:
        base = addr & ~0xFFF
        if base not in self.pages:
            self.pages[base] = bytearray(0x1000)
        return self.pages[base]

    @staticmethod
    def mapped(addr: int) -> bool:
        return MEM_BASE <= addr < MEM_BASE + MEM_SIZE

    def read_hex(self, addr: int, n: int) -> str:
        """Hex string for [addr, addr+n), with '??' for unmapped bytes."""
        with self.lock:
            parts = []
            a, end = addr, addr + n
            while a < end:
                page_end = min((a & ~0xFFF) + 0x1000, end)
                if not self.mapped(a):
                    parts.append("??" * (page_end - a))
                else:
                    page = self.pages.get(a & ~0xFFF)
                    chunk = page[a & 0xFFF : (a & 0xFFF) + page_end - a] if page else bytes(page_end - a)
                    parts.append(bytes(chunk).hex().upper())
                a = page_end
            return "".join(parts)

    def write(self, addr: int, data: bytes) -> int:
        with self.lock:
            written = 0
            for i, b in enumerate(data):
                a = addr + i
                if not self.mapped(a):
                    break
                self._page(a)[a & 0xFFF] = b
                written += 1
            return written


def seeded_memory() -> FakeMemory:
    mem = FakeMemory()
    mem.write(NAME_ADDR, b"MockPlayer\x00")
    mem.write(PRESTIGE_ADDR, struct.pack(">i", 10))
    mem.write(FOV_ADDR, struct.pack(">f", 65.0))
    mem.write(CBUF_ADDR, struct.pack(">I", 0x7D8802A6))  # mflr r12
    return mem


_PARAMS = re.compile(r'params="(.*)"')


def parse_jrpc(line: str) -> tuple[int, list]:
    """Decode a consolefeatures call into (address, args)."""
    tokens = _PARAMS.search(line).group(1).split("\\")
    if tokens[0] != "A":
        raise ValueError("bad params")
    addr, argc = int(tokens[1], 16), int(tokens[2])
    args, i = [], 3
    for _ in range(argc):
        kind, value = tokens[i], tokens[i + 1]
        i += 2
        if kind == "1":
            args.append(int(value))
        elif kind == "3":
            args.append(float(value))
        elif kind.startswith("7/"):
            data = bytes.fromhex(value)
            if len(data) != int(kind[2:]):
                raise ValueError("byte array length mismatch")
            args.append(data)
        else:
            raise ValueError(f"unsupported arg type {kind}")
    return addr, args


def _args(line: str) -> dict[str, str]:
    out = {}
    for tok in line.split()[1:]:
        k, _, v = tok.partition("=")
        out[k.lower()] = v
    return out


class Handler(socketserver.StreamRequestHandler):
    def send(self, text: str) -> None:
        self.wfile.write(text.encode("latin-1") + b"\r\n")

    def setup(self):
        self.request.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        super().setup()

    def handle(self):
        mem: FakeMemory = self.server.mem
        self.send("201- connected")
        for raw in self.rfile:
            line = raw.decode("latin-1").strip()
            if not line:
                continue
            cmd = line.split()[0].lower()
            a = _args(line)
            if cmd == "bye":
                self.send("200- bye")
                return
            elif cmd == "dbgname":
                self.send("200- MockXbox")
            elif cmd == "xbeinfo":
                self.send("202- multiline response follows")
                self.send("timestamp=0x50a3c1f0 checksum=0x00000000")
                self.send('name="\\Device\\Harddisk0\\Partition1\\Content\\BO2\\default_mp.xex"')
                self.send(".")
            elif cmd == "consolefeatures":
                if "buf_addr=" in line:  # polling a pending call
                    self.send("200- 0")
                    continue
                try:
                    addr, args = parse_jrpc(line)
                except (ValueError, AttributeError, IndexError) as e:
                    self.send(f"200- error={e}")
                    continue
                if addr == CBUF_ADDR and len(args) == 2 and isinstance(args[1], bytes):
                    text = args[1].rstrip(b"\x00").decode("latin-1").strip()
                    self.server.executed.append(text)
                    print(f"[mock] Cbuf_AddText({args[0]}, {text!r})")
                    self.send("200- buf_addr=0x40001000")  # pretend it's still running
                else:
                    self.send(f"200- error=no function at 0x{addr:08X}")
            elif cmd == "magicboot":
                self.send("200- OK")
            elif cmd == "getmem":
                addr, n = int(a["addr"], 16), int(a["length"], 16)
                data = mem.read_hex(addr, n)
                self.send("211- memory data follows")
                for i in range(0, len(data), 256):  # 128 bytes per line
                    self.send(data[i : i + 256])
                self.send(".")
            elif cmd == "setmem":
                addr = int(a["addr"], 16)
                n = mem.write(addr, bytes.fromhex(a["data"]))
                if n == 0:
                    self.send("404- memory not mapped")
                else:
                    self.send(f"200- set {n} bytes")
            else:
                self.send("407- unknown command")


class MockConsole(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, addr=("127.0.0.1", 0), mem: FakeMemory | None = None):
        self.mem = mem or seeded_memory()
        self.executed: list[str] = []
        super().__init__(addr, Handler)

    @property
    def port(self) -> int:
        return self.server_address[1]

    def start_background(self) -> "MockConsole":
        threading.Thread(target=self.serve_forever, daemon=True).start()
        return self


def main():
    ap = argparse.ArgumentParser(description="fake XBDM console")
    ap.add_argument("--port", type=int, default=7300)
    args = ap.parse_args()
    srv = MockConsole(("127.0.0.1", args.port))
    print(f"mock console on 127.0.0.1:{srv.port} (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
