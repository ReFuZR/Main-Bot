"""XBDM client (TCP 730 on RGH/JTAG consoles) with JRPC2 remote calls.

XBDM is line based: '201- connected' on connect, then e.g.
'getmem addr=0x.. length=0x..' -> '211- ...', hex lines ('??' = unreadable), '.'.
The JRPC2 plugin adds 'consolefeatures', which calls a function in the game.
The Xbox 360 is big-endian PowerPC.
"""

from __future__ import annotations

import re
import socket
import struct
import time

FMT = {"u32": ">I", "i32": ">i", "float": ">f"}
PROLOGUES = (0x7D8802A6, 0x7C0802A6)  # mflr r12 / mflr r0


class XbdmError(Exception):
    pass


def encode(kind: str, value: str, size: int | None = None) -> bytes:
    """Text -> bytes for str/string, hex/bytes, u32, i32 or float. `size` = fixed field size."""
    if kind in ("str", "string"):
        data = value.encode("latin-1")
        if size and len(data) >= size:
            raise ValueError(f"string too long for {size}-byte field")
        return data.ljust(size, b"\0") if size else data
    if kind in ("hex", "bytes"):
        data = bytes.fromhex(value)
        if size and kind == "bytes" and len(data) != size:
            raise ValueError(f"expected {size} bytes")
        return data
    if kind not in FMT:
        raise ValueError(f"unknown type {kind!r} (hex/u32/i32/float/str)")
    if kind == "float":
        return struct.pack(">f", float(value))
    n = int(value, 0)
    return struct.pack(FMT[kind], n & 0xFFFFFFFF if kind == "u32" else n)


def jrpc_arg(arg) -> str:
    """One JRPC2 argument: int '1\\<n>\\', float '3\\<f>\\', string/bytes '7/<len>\\<hex>\\'."""
    if isinstance(arg, float):
        return f"3\\{arg!r}\\"
    if isinstance(arg, int):
        return f"1\\{struct.unpack('>i', struct.pack('>I', arg & 0xFFFFFFFF))[0]}\\"
    data = (arg.encode("latin-1") if isinstance(arg, str) else bytes(arg)).rstrip(b"\0") + b"\0"
    return f"7/{len(data)}\\{data.hex().upper()}\\"


class Xbdm:
    def __init__(self, host: str, port: int = 730, timeout: float = 5.0):
        self.addr, self.timeout, self.sock, self.buf = (host, port), timeout, None, b""

    def connect(self) -> "Xbdm":
        self.sock = socket.create_connection(self.addr, self.timeout)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # lots of tiny round trips
        if self._status()[0] != 201:
            raise XbdmError("unexpected greeting")
        return self

    def close(self) -> None:
        if self.sock:
            try:
                self.sock.sendall(b"bye\r\n")
            except OSError:
                pass
            self.sock.close()
            self.sock = None

    def _line(self) -> str:
        while b"\r\n" not in self.buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise XbdmError("connection closed by console")
            self.buf += chunk
        line, self.buf = self.buf.split(b"\r\n", 1)
        return line.decode("latin-1")

    def _status(self) -> tuple[int, str]:
        line = self._line()
        if not line[:3].isdigit():
            raise XbdmError(f"malformed response: {line!r}")
        return int(line[:3]), line[5:]

    def lines(self) -> list[str]:
        """Body of a multiline reply, up to the closing '.'."""
        out = []
        while (line := self._line()) != ".":
            out.append(line)
        return out

    def send(self, command: str) -> tuple[int, str]:
        if not self.sock:
            raise XbdmError("not connected")
        self.sock.sendall(command.encode("latin-1") + b"\r\n")
        code, msg = self._status()
        if code >= 400:
            raise XbdmError(f"{command.split()[0]}: {code}- {msg}")
        return code, msg

    # -- console ----------------------------------------------------------------
    def name(self) -> str:
        return self.send("dbgname")[1]

    def xex(self) -> str:
        self.send("xbeinfo running")
        return next((l[5:].strip('"') for l in self.lines() if l.startswith("name=")), "?")

    def reboot(self, cold: bool = False) -> None:
        self.send("magicboot cold" if cold else "magicboot")

    # -- memory -----------------------------------------------------------------
    def read(self, addr: int, n: int) -> bytes:
        out = b""
        for a in range(addr, addr + n, 0x1000):
            self.send(f"getmem addr=0x{a:08X} length=0x{min(0x1000, addr + n - a):X}")
            data = "".join(self.lines())
            if "??" in data:
                raise XbdmError(f"unreadable memory near 0x{a:08X}")
            out += bytes.fromhex(data)
        return out

    def write(self, addr: int, data: bytes) -> None:
        for i in range(0, len(data), 128):  # stay under XBDM's line limit
            self.send(f"setmem addr=0x{addr + i:08X} data={data[i:i + 128].hex().upper()}")

    def get(self, addr: int, kind: str, size: int = 4):
        if kind == "string":
            return self.read(addr, size).split(b"\0")[0].decode("latin-1")
        if kind == "bytes":
            return self.read(addr, size).hex().upper()
        return struct.unpack(FMT[kind], self.read(addr, 4))[0]

    def put(self, addr: int, kind: str, value: str, size: int | None = None) -> None:
        self.write(addr, encode(kind, value, size))

    # -- JRPC2 ------------------------------------------------------------------
    def is_function(self, addr: int) -> bool:
        """Cheap check before calling an address: does it start like a function?"""
        word = struct.unpack(">I", self.read(addr, 4))[0]
        return word in PROLOGUES or word >> 16 == 0x9421  # or stwu r1,-x(r1)

    def call(self, address: int, *args, timeout: float = 5.0) -> None:
        """Call a void game function. Clean reimplementation of JRPC2; unverified on hardware."""
        params = f"A\\{address:X}\\{len(args)}\\" + "".join(map(jrpc_arg, args))
        try:
            _, msg = self.send(f'consolefeatures ver=2 type=0 system as=0 params="{params}"')
        except XbdmError as e:
            if "407" in str(e) or "unknown command" in str(e).lower():
                raise XbdmError("console doesn't understand 'consolefeatures': is the JRPC2 plugin loaded?") from e
            raise
        deadline = time.monotonic() + timeout
        while m := re.search(r"buf_addr=(0x[0-9A-Fa-f]+)", msg):  # still running: poll
            if time.monotonic() > deadline:
                raise XbdmError("timed out waiting for the call to finish")
            time.sleep(0.05)
            _, msg = self.send(f"consolefeatures buf_addr={m.group(1)}")
        if "error=" in msg:
            raise XbdmError(msg)
