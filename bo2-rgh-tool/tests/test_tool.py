import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from bo2tool import mock_console as mc
from bo2tool.cli import Shell
from bo2tool.game import Offsets, strip_colors
from bo2tool.xbdm import Xbdm, XbdmError

ROOT = Path(__file__).resolve().parent.parent


class ToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = mc.MockConsole().start_background()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        self.srv.mem = mc.seeded_memory()
        self.xb = Xbdm("127.0.0.1", self.srv.port)
        self.xb.connect()
        self.tmp = Path(tempfile.mkdtemp())
        self.offsets_path = self.tmp / "offsets.json"
        shutil.copy(ROOT / "offsets.json", self.offsets_path)
        self.shell = Shell(self.xb, Offsets(self.offsets_path))

    def tearDown(self):
        self.xb.close()
        shutil.rmtree(self.tmp)

    def run_cmd(self, line: str) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.shell.onecmd(line)
        return buf.getvalue()

    # -- protocol -------------------------------------------------------------
    def test_info(self):
        self.assertEqual(self.xb.console_name(), "MockXbox")
        self.assertIn("default_mp.xex", self.xb.running_xex())

    def test_typed_round_trips(self):
        self.assertEqual(self.xb.read_string(mc.NAME_ADDR), "MockPlayer")
        self.assertEqual(self.xb.read_i32(mc.PRESTIGE_ADDR), 10)
        self.assertEqual(self.xb.read_float(mc.FOV_ADDR), 65.0)
        self.xb.write_float(mc.FOV_ADDR, 90.0)
        self.assertEqual(self.xb.read_float(mc.FOV_ADDR), 90.0)

    def test_large_write_is_chunked(self):
        data = bytes(range(256)) * 3
        self.xb.write(0x83000000, data)
        self.assertEqual(self.xb.read(0x83000000, len(data)), data)

    def test_unmapped_read_raises(self):
        with self.assertRaises(XbdmError):
            self.xb.read(0x10000000, 4)

    def test_scan_finds_pattern_across_chunk_boundary(self):
        self.xb.write(0x8300FFFE, b"ABCD")
        hits = self.xb.scan(0x83000000, 0x83020000, b"ABCD", chunk=0x10000)
        self.assertEqual(hits, [0x8300FFFE])

    def test_scan_skips_unmapped(self):
        self.xb.write(0x82000010, b"MockPlayer")
        hits = self.xb.scan(0x81FE0000, 0x82010000, b"MockPlayer")
        self.assertEqual(hits, [0x82000010])

    # -- shell workflow -------------------------------------------------------
    def test_find_then_save_then_set_name(self):
        out = self.run_cmd("find str MockPlayer 0x83500000 0x83600000")
        self.assertIn("1 hit(s)", out)
        self.run_cmd(f"setaddr name 0x{mc.NAME_ADDR:08X}")
        saved = json.loads(self.offsets_path.read_text())
        self.assertEqual(saved["fields"]["name"]["addr"], "0x83551E00")

        out = self.run_cmd("set name ^1Red^7Guy")
        self.assertIn("^1Red^7Guy", out)
        self.assertEqual(self.xb.read_string(mc.NAME_ADDR), "^1Red^7Guy")

    def test_refine_narrows_hits(self):
        self.xb.write_i32(0x83400000, 10)  # a decoy with the same value
        self.run_cmd("find i32 10 0x83400000 0x83560000")
        self.assertEqual(len(self.shell.last_hits), 2)
        self.xb.write_i32(mc.PRESTIGE_ADDR, 11)  # "prestige up in game"
        out = self.run_cmd("refine 11")
        self.assertEqual(self.shell.last_hits, [mc.PRESTIGE_ADDR])
        self.assertIn("one hit", out)

    def test_name_too_long_is_rejected(self):
        self.run_cmd(f"setaddr clan_tag 0x{mc.NAME_ADDR:08X}")
        out = self.run_cmd("set clan_tag TOOLONG")
        self.assertIn("too long", out)

    def test_get_without_address_explains(self):
        out = self.run_cmd("get prestige")
        self.assertIn("no address yet", out)

    def test_peek_and_poke(self):
        self.run_cmd("poke 0x83000000 u32 0xDEADBEEF")
        out = self.run_cmd("peek 0x83000000 16")
        self.assertIn("DE AD BE EF", out)

    def test_strip_colors(self):
        self.assertEqual(strip_colors("^1Red^7Guy"), "RedGuy")


if __name__ == "__main__":
    unittest.main()
