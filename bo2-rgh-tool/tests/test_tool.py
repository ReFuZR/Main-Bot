import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from bo2tool import mock_console as mc
from bo2tool.cli import Shell
from bo2tool.data import CBUF, GAMES, Catalog, Profile, strip_colors
from bo2tool.xbdm import Xbdm, XbdmError, jrpc_arg


class Offline(unittest.TestCase):
    def test_jrpc_call_format_round_trips(self):
        params = 'consolefeatures params="A\\82000000\\4\\' + "".join(map(jrpc_arg, (7, -3, 2.5, "hi"))) + '"'
        self.assertEqual(mc.parse_jrpc(params), (0x82000000, [7, -3, 2.5, b"hi\0"]))
        self.assertEqual(jrpc_arg("cg_fov 90\n"), "7/11\\63675F666F762039300A00\\")
        self.assertEqual(jrpc_arg(0xFFFFFFFF), "1\\-1\\")

    def test_missing_jrpc_plugin_is_explained(self):
        xb = Xbdm("unused")
        xb.send = lambda _: (_ for _ in ()).throw(XbdmError("consolefeatures: 407- unknown command"))
        with self.assertRaisesRegex(XbdmError, "JRPC2 plugin"):
            xb.call(0x82000000)

    def test_catalog(self):
        cat = Catalog()
        for e in cat.entries:
            self.assertTrue(e["games"] and set(e["games"]) <= set(GAMES), e["name"])
        for name, p in cat.presets.items():
            for c in p["commands"]:
                self.assertIsNotNone(cat.lookup(c.split()[0]), f"{name}: {c}")
        self.assertEqual(cat.lookup("scr_dm_scorelimit")["name"], "scr_<gametype>_scorelimit")
        self.assertIsNone(cat.lookup("scr__scorelimit"))
        self.assertEqual(cat.preset("fov", "cod4"), (["cg_fov 90"], ["cg_fovScale 1.15"]))

    def test_profiles(self):
        self.assertEqual({g: len(GAMES[g].get("cbuf", [])) for g in ("bo2", "mw2", "mw3", "bo1")},
                         {"bo2": 1, "mw2": 1, "mw3": 2, "bo1": 0})
        with self.assertRaises(KeyError):
            Profile("mw19")
        self.assertEqual(strip_colors("^1Red^7Guy"), "RedGuy")


class WithConsole(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = mc.MockConsole().start_background()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        self.srv.mem, self.srv.executed = mc.Memory(), []
        self.xb = Xbdm("127.0.0.1", self.srv.port).connect()
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "bo2.json"
        self.shell = Shell(self.xb, Profile("bo2", self.path))

    def tearDown(self):
        self.xb.close()
        self.tmp.cleanup()

    def run_cmd(self, line, *answers):
        """Run a shell command. An answer may be (callback, text): the callback 'plays the game' first."""
        answers = list(answers)

        def ask(_):
            if not answers:
                raise EOFError
            a = answers.pop(0)
            if isinstance(a, tuple):
                a[0]()
                return a[1]
            return a

        self.shell.ask, buf = ask, io.StringIO()
        with redirect_stdout(buf):
            self.shell.onecmd(line)
        return buf.getvalue()

    def saved(self):
        return json.loads(self.path.read_text()) if self.path.exists() else {}

    # -- xbdm ----------------------------------------------------------------
    def test_console_and_typed_values(self):
        self.assertEqual((self.xb.name(), self.xb.xex()[-14:]), ("MockXbox", "default_mp.xex"))
        self.assertEqual(self.xb.get(mc.NAME, "string", 32), "MockPlayer")
        self.assertEqual(self.xb.get(mc.PRESTIGE, "i32"), 10)
        self.xb.put(mc.FOV, "float", "90")
        self.assertEqual(self.xb.get(mc.FOV, "float"), 90.0)

    def test_large_write_and_unmapped_read(self):
        data = bytes(range(256)) * 3
        self.xb.write(0x83000000, data)
        self.assertEqual(self.xb.read(0x83000000, len(data)), data)
        with self.assertRaises(XbdmError):
            self.xb.read(0x10000000, 4)

    def test_scan_across_chunks_and_unmapped(self):
        self.xb.write(0x8300FFFE, b"ABCD")
        self.assertEqual(self.xb.scan(0x83000000, 0x83020000, b"ABCD"), [0x8300FFFE])
        self.xb.write(0x82000010, b"Needle")
        self.assertEqual(self.xb.scan(0x81FE0000, 0x82010000, b"Needle"), [0x82000010])

    # -- fields ----------------------------------------------------------------
    def test_find_setaddr_set_get(self):
        self.assertIn("1 hit(s)", self.run_cmd("find str MockPlayer 0x83500000 0x83600000"))
        self.run_cmd(f"setaddr name 0x{mc.NAME:08X}")
        self.assertEqual(self.saved(), {"name": "0x83551E00"})
        self.run_cmd("set name ^1Red^7Guy")
        self.assertIn("(plain: 'RedGuy')", self.run_cmd("get name"))

    def test_refine(self):
        self.xb.put(0x83400000, "i32", "10")
        self.run_cmd("find i32 10 0x83400000 0x83560000")
        self.xb.put(mc.PRESTIGE, "i32", "11")
        self.assertIn("one hit", self.run_cmd("refine 11"))
        self.assertEqual(self.shell.hits, [mc.PRESTIGE])

    def test_field_errors(self):
        self.assertIn("no address yet", self.run_cmd("get prestige"))
        self.run_cmd(f"setaddr clan_tag 0x{mc.NAME:08X}")
        self.assertIn("too long", self.run_cmd("set clan_tag TOOLONG"))
        self.assertIn("unknown field", self.run_cmd("get nope"))

    def test_peek_poke(self):
        self.run_cmd("poke 0x83000000 u32 0xDEADBEEF")
        self.assertIn("DE AD BE EF", self.run_cmd("peek 0x83000000 16"))

    # -- wizard ----------------------------------------------------------------
    def test_wizard_unique_string(self):
        self.assertIn("found it: name = 0x83551E00", self.run_cmd("wizard name --range 0x83500000 0x83600000", "MockPlayer"))

    def test_wizard_narrows_by_playing(self):
        self.xb.put(0x83400000, "i32", "10")
        self.xb.put(0x83400100, "i32", "10")
        put = self.xb.put
        out = self.run_cmd("wizard prestige --range 0x83400000 0x83560000", "10",
                           (lambda: (put(mc.PRESTIGE, "i32", "11"), put(0x83400100, "i32", "11")), "11"),
                           (lambda: put(mc.PRESTIGE, "i32", "12"), "12"))
        self.assertIn("3 matches", out)
        self.assertIn("2 matches", out)
        self.assertEqual(self.saved(), {"prestige": "0x83551E40"})

    def test_wizard_pick_skip_quit_and_misses(self):
        self.xb.write(0x83400000, b"MockPlayer\0")
        self.run_cmd("wizard name --range 0x83400000 0x83560000", "MockPlayer", "pick 2")
        self.assertEqual(self.saved(), {"name": "0x83551E00"})
        out = self.run_cmd("wizard --range 0x83500000 0x83600000", "skip", "quit")
        self.assertIn("not found: clan_tag, prestige, rank_xp, fov, kills", out)
        self.assertIn("no matches", self.run_cmd("wizard name --range 0x83500000 0x83600000", "NotThere"))

    # -- console commands ------------------------------------------------------
    def test_setup_then_cmd_and_preset(self):
        self.assertIn("no address yet", self.run_cmd("cmd cg_fov 90"))
        self.run_cmd("setup", "n")
        self.assertEqual(self.saved(), {})
        self.assertIn("looks like a function start", self.run_cmd("setup", "y"))
        self.assertEqual(self.saved(), {CBUF: "0x824015E0"})
        self.run_cmd("cmd cg_fov 90; cg_drawFPS 1")
        self.assertIn("affect everyone in your lobby", self.run_cmd("preset moon"))
        self.assertIn("isn't in the catalog", self.run_cmd("cmd some_new_dvar 1"))
        self.assertEqual(self.srv.executed[:3], ["cg_fov 90", "cg_drawFPS 1", "sv_cheats 1"])
        self.assertEqual(self.srv.executed[-1], "some_new_dvar 1")

    def test_setup_tries_each_suggestion(self):
        self.shell.p.info = dict(GAMES["bo2"], cbuf=["0x83000000", "0x824015E0"])
        out = self.run_cmd("setup", "y")
        self.assertIn("0x83000000 doesn't look like a function", out)
        self.assertEqual(self.shell.p.addrs[CBUF], mc.CBUF)

    def test_setfunc_checks_prologue(self):
        self.assertIn("doesn't start like a function", self.run_cmd(f"setfunc {CBUF} 0x83000000"))
        self.assertIn("saved", self.run_cmd(f"setfunc {CBUF} 0x83000000 --force"))

    def test_commands_search_by_game(self):
        out = self.run_cmd("commands fov")
        self.assertIn("cg_fovScale", out)
        self.assertNotIn("g_gravity", out)
        self.assertNotIn("cg_thirdPersonAngle", self.run_cmd("commands player"))
        self.shell = Shell(self.xb, Profile("cod4", self.path))
        self.assertNotIn("cg_fovScale", self.run_cmd("commands fov"))
        self.assertEqual(self.shell.prompt, "cod4> ")


if __name__ == "__main__":
    unittest.main()
