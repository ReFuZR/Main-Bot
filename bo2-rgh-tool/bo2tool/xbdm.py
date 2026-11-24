"""Minimal XBDM (Xbox Debug Monitor) client.

XBDM listens on TCP port 730 on RGH/JTAG/devkit consoles. It speaks a simple
line-based text protocol:

    -> (on connect)            201- connected
    <- getmem addr=0x.. length=0x..
    -> 211- memory data follows
    -> 0011AABB...             (hex lines, '??' for unreadable bytes)
    -> .
    <- setmem addr=0x.. data=AABBCC
    -> 200- set 3 bytes

The Xbox 360 CPU is big-endian PowerPC, so all numeric helpers use '>' formats.
"""

from __future__ import annotations

import socket
import struct

XBDM_PORT = 730
# Keep setmem lines comfortably below XBDM's ~512 byte line limit.
SETMEM_CHUNK = 128
GETMEM_CHUNK = 0x1000


class XbdmError(Exception):
    pass


class Xbdm:
    def __init__(self, host: str, port: int = XBDM_PORT, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None
        self._buf = b""

    # ---------------------------------------------------------------- transport
    def connect(self) -> None:
        self._sock = socket.create_connection((self.host, self.port), self.timeout)
        self._sock.settimeout(self.timeout)
        # Lots of tiny request/response round trips: don't let Nagle batch them.
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        status, msg = self._read_status()
        if status != 201:
            raise XbdmError(f"unexpected greeting: {status}- {msg}")

    def close(self) -> None:
        if self._sock:
            try:
                self._sock.sendall(b"bye\r\n")
            except OSError:
                pass
            self._sock.close()
            self._sock = None

    def __enter__(self) -> "Xbdm":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _readline(self) -> str:
        if self._sock is None:
            raise XbdmError("not connected")
        while b"\r\n" not in self._buf:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise XbdmError("connection closed by console")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\r\n", 1)
        return line.decode("latin-1")

    def _read_status(self) -> tuple[int, str]:
        line = self._readline()
        try:
            code = int(line[:3])
        except ValueError:
            raise XbdmError(f"malformed response: {line!r}")
        return code, line[5:] if line[3:5] == "- " else line[4:]

    def _read_multiline(self) -> list[str]:
        lines = []
        while True:
            line = self._readline()
            if line == ".":
                return lines
            lines.append(line)

    def send(self, command: str) -> tuple[int, str]:
        """Send a raw command and return (status, message) for single-line replies."""
        if self._sock is None:
            raise XbdmError("not connected")
        self._sock.sendall(command.encode("latin-1") + b"\r\n")
        code, msg = self._read_status()
        if code >= 400:
            raise XbdmError(f"{command.split()[0]}: {code}- {msg}")
        return code, msg

    def command_multiline(self, command: str) -> list[str]:
        code, msg = self.send(command)
        if code not in (202, 211):
            return [msg]
        return self._read_multiline()

    # ---------------------------------------------------------------- console
    def console_name(self) -> str:
        return self.send("dbgname")[1]

    def running_xex(self) -> str:
        for line in self.command_multiline("xbeinfo running"):
            if line.startswith("name="):
                return line[5:].strip('"')
        return "?"

    def reboot(self, cold: bool = False) -> None:
        self.send("magicboot cold" if cold else "magicboot")

    # ---------------------------------------------------------------- memory
    def read(self, addr: int, length: int) -> bytes:
        out = bytearray()
        while length > 0:
            n = min(length, GETMEM_CHUNK)
            code, msg = self.send(f"getmem addr=0x{addr:08X} length=0x{n:X}")
            if code != 211:
                raise XbdmError(f"getmem: {code}- {msg}")
            hexdata = "".join(self._read_multiline())
            if "??" in hexdata:
                raise XbdmError(f"unreadable memory near 0x{addr:08X}")
            out += bytes.fromhex(hexdata)
            addr += n
            length -= n
        return bytes(out)

    def write(self, addr: int, data: bytes) -> None:
        for i in range(0, len(data), SETMEM_CHUNK):
            part = data[i : i + SETMEM_CHUNK]
            self.send(f"setmem addr=0x{addr + i:08X} data={part.hex().upper()}")

    # typed helpers (big-endian)
    def read_u32(self, addr: int) -> int:
        return struct.unpack(">I", self.read(addr, 4))[0]

    def write_u32(self, addr: int, value: int) -> None:
        self.write(addr, struct.pack(">I", value & 0xFFFFFFFF))

    def read_i32(self, addr: int) -> int:
        return struct.unpack(">i", self.read(addr, 4))[0]

    def write_i32(self, addr: int, value: int) -> None:
        self.write(addr, struct.pack(">i", value))

    def read_float(self, addr: int) -> float:
        return struct.unpack(">f", self.read(addr, 4))[0]

    def write_float(self, addr: int, value: float) -> None:
        self.write(addr, struct.pack(">f", value))

    def read_string(self, addr: int, max_len: int = 64) -> str:
        raw = self.read(addr, max_len)
        return raw.split(b"\x00", 1)[0].decode("latin-1")

    def write_string(self, addr: int, text: str, field_len: int | None = None) -> None:
        data = text.encode("latin-1") + b"\x00"
        if field_len is not None:
            if len(data) > field_len:
                raise ValueError(f"string too long for {field_len}-byte field")
            data = data.ljust(field_len, b"\x00")
        self.write(addr, data)

    def scan(self, start: int, end: int, pattern: bytes, chunk: int = 0x10000,
             progress=None) -> list[int]:
        """Find every occurrence of `pattern` in [start, end). Skips unreadable pages."""
        hits = []
        overlap = len(pattern) - 1
        addr = start
        while addr < end:
            n = min(chunk, end - addr)
            try:
                data = self.read(addr, n + overlap if addr + n < end else n)
            except XbdmError:
                addr += n
                continue
            i = data.find(pattern)
            while i != -1:
                if i < n:
                    hits.append(addr + i)
                i = data.find(pattern, i + 1)
            addr += n
            if progress:
                progress(addr - start, end - start)
        return hits
