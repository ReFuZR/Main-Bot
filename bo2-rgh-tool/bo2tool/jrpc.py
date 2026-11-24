"""Remote function calls through the JRPC2 console plugin.

Plain XBDM can only read and write memory. The JRPC2 plugin (loaded on the
console like xbdm.xex) adds a `consolefeatures` XBDM command that calls a
function inside the running game. That is what lets us run the game's own
console commands via Cbuf_AddText.

Wire format (JRPC protocol version 2), one XBDM line:

    consolefeatures ver=2 type=<ret> system as=0 params="A\\<ADDR>\\<argc>\\<args>"

each argument being `<type>\\<value>\\`:
    int     1\\<decimal>\\
    float   3\\<value>\\
    string  7/<length>\\<hex bytes>\\     (sent as a byte array)

The console answers `200- <return value>`, or `buf_addr=0x...` while the
call is still running, which is polled with `consolefeatures buf_addr=0x...`.

This is a clean reimplementation of that protocol, not copied from any tool.
It has been tested against the mock console only; plugin builds differ, so
treat real-console behaviour as unverified until you've tried it.
"""

from __future__ import annotations

import re
import struct
import time

from .xbdm import Xbdm, XbdmError

JRPC_VERSION = 2

# return/argument type codes
T_VOID = 0
T_INT = 1
T_FLOAT = 3
T_BYTE_ARRAY = 7

# Common PowerPC function prologues: mflr r12 / mflr r0 / stwu r1,-x(r1)
PROLOGUES = (0x7D8802A6, 0x7C0802A6)
STWU_R1 = 0x9421


class JrpcError(XbdmError):
    pass


def encode_arg(arg) -> str:
    if isinstance(arg, bool):
        return f"{T_INT}\\{int(arg)}\\"
    if isinstance(arg, int):
        # JRPC carries ints as signed 32-bit decimals
        return f"{T_INT}\\{struct.unpack('>i', struct.pack('>I', arg & 0xFFFFFFFF))[0]}\\"
    if isinstance(arg, float):
        return f"{T_FLOAT}\\{arg!r}\\"
    if isinstance(arg, str):
        arg = arg.encode("latin-1")
    if isinstance(arg, (bytes, bytearray)):
        data = bytes(arg)
        if not data.endswith(b"\x00"):
            data += b"\x00"  # C strings need their terminator
        return f"{T_BYTE_ARRAY}/{len(data)}\\{data.hex().upper()}\\"
    raise TypeError(f"unsupported JRPC argument type: {type(arg).__name__}")


def build_call(address: int, args=(), ret_type: int = T_VOID, system_thread: bool = True) -> str:
    params = f"A\\{address:X}\\{len(args)}\\" + "".join(encode_arg(a) for a in args)
    system = " system" if system_thread else ""
    return f'consolefeatures ver={JRPC_VERSION} type={ret_type}{system} as=0 params="{params}"'


_BUF = re.compile(r"buf_addr=(0x[0-9A-Fa-f]+)")


def call(xb: Xbdm, address: int, *args, ret_type: int = T_VOID, timeout: float = 5.0):
    try:
        _, msg = xb.send(build_call(address, args, ret_type))
    except XbdmError as e:
        if "407" in str(e) or "unknown command" in str(e).lower():
            raise JrpcError("console doesn't understand 'consolefeatures': "
                            "is the JRPC2 plugin loaded?") from e
        raise
    deadline = time.monotonic() + timeout
    while (m := _BUF.search(msg)):
        if time.monotonic() > deadline:
            raise JrpcError("timed out waiting for the call to finish")
        time.sleep(0.05)
        _, msg = xb.send(f"consolefeatures buf_addr={m.group(1)}")
    if "error=" in msg:
        raise JrpcError(msg)
    if ret_type == T_VOID:
        return None
    token = msg.split()[-1] if msg.split() else "0"
    if ret_type == T_FLOAT:
        return float(token)
    return int(token, 16) if token.lower().startswith("0x") else int(token)


def looks_like_function(xb: Xbdm, address: int) -> bool:
    """Cheap sanity check before calling an address: does it start like a function?"""
    word = xb.read_u32(address)
    return word in PROLOGUES or (word >> 16) == STWU_R1
