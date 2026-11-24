import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from bo2tool import jrpc
from bo2tool import mock_console as mc
from bo2tool.catalog import Catalog
from bo2tool.cli import Shell
from bo2tool.game import Offsets, available_games, offsets_path
from bo2tool.xbdm import Xbdm, XbdmError

ROOT = Path(__file__).resolve().parent.parent


class JrpcEncodingTests(unittest.TestCase):
    def test_build_call_format(self):
        line = jrpc.build_call(0x824015E0, (0, "cg_fov 90\n"))
        self.assertEqual(
            line,
            'consolefeatures ver=2 type=0 system as=0 '
            'params="A\\824015E0\\2\\1\\0\\7/11\\63675F666F762039300A00\\"',
        )

    def test_ints_are_signed_32_bit(self):
        self.assertEqual(jrpc.encode_arg(0xFFFFFFFF), "1\\-1\\")
        self.assertEqual(jrpc.encode_arg(True), "1\\1\\")
        self.assertEqual(jrpc.encode_arg(1.5), "3\\1.5\\")

    def test_round_trip_through_mock_parser(self):
        addr, args = mc.parse_jrpc(jrpc.build_call(0x82000000, (7, -3, 2.5, "hi")))
        self.assertEqual(addr, 0x82000000)
        self.assertEqual(args, [7, -3, 2.5, b"hi\x00"])

    def test_missing_plugin_is_explained(self):
        class NoJrpc:
            def send(self, _):
                raise XbdmError("consolefeatures: 407- unknown command")
        with self.assertRaisesRegex(jrpc.JrpcError, "JRPC2 plugin"):
            jrpc.call(NoJrpc(), 0x82000000)


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.cat = Catalog()

    def test_every_entry_names_known_games(self):
        games = set(available_games())
        for e in self.cat.entries:
            self.assertTrue(e.games, e.name)
            self.assertLessEqual(set(e.games), games, e.name)
            self.assertIn(e.scope, ("local", "host"), e.name)

    def test_preset_commands_are_in_catalog(self):
        for p in self.cat.presets.values():
            for c in p.commands:
                self.assertIsNotNone(self.cat.lookup(c.split()[0]), f"{p.name}: {c}")

    def test_templated_lookup(self):
        self.assertEqual(self.cat.lookup("scr_dm_scorelimit").name, "scr_<gametype>_scorelimit")
        self.assertIsNone(self.cat.lookup("scr__scorelimit"))

    def test_preset_skips_commands_a_game_lacks(self):
        run, skipped = self.cat.preset_commands("fov", "cod4")
        self.assertEqual(run, ["cg_fov 90"])
        self.assertEqual(skipped, ["cg_fovScale 1.15"])


class GameProfileTests(unittest.TestCase):
    def test_all_profiles_load_with_same_fields(self):
        bo2 = Offsets(offsets_path("bo2"))
        for short in available_games():
            o = Offsets(offsets_path(short))
            self.assertEqual(o.short, short)
            self.assertEqual(list(o.fields), list(bo2.fields))
            self.assertIn("Cbuf_AddText", o.functions)
            self.assertTrue(all(f.addr is None for f in o.fields.values()),
                            f"{short} should ship without addresses")

    def test_unknown_game(self):
        with self.assertRaises(KeyError):
            offsets_path("mw19")


class CommandShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = mc.MockConsole().start_background()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def setUp(self):
        self.srv.mem = mc.seeded_memory()
        self.srv.executed.clear()
        self.xb = Xbdm("127.0.0.1", self.srv.port)
        self.xb.connect()
        self.tmp = Path(tempfile.mkdtemp())
        self.path = self.tmp / "bo2.json"
        shutil.copy(ROOT / "offsets" / "bo2.json", self.path)
        self.shell = Shell(self.xb, Offsets(self.path))

    def tearDown(self):
        self.xb.close()
        shutil.rmtree(self.tmp)

    def run_cmd(self, line, answers=()):
        answers = list(answers)
        self.shell.ask = lambda _: answers.pop(0) if answers else "n"
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.shell.onecmd(line)
        return buf.getvalue()

    def test_cmd_needs_function_address(self):
        out = self.run_cmd("cmd cg_fov 90")
        self.assertIn("no address yet", out)
        self.assertIn("setup", out)

    def test_setup_saves_suggested_then_cmd_runs(self):
        out = self.run_cmd("setup", ["y"])
        self.assertIn("looks like a function start", out)
        self.assertEqual(json.loads(self.path.read_text())["functions"]["Cbuf_AddText"]["addr"],
                         "0x824015E0")
        self.run_cmd("cmd cg_fov 90; cg_drawFPS 1")
        self.assertEqual(self.srv.executed, ["cg_fov 90", "cg_drawFPS 1"])

    def test_setup_tries_each_suggestion(self):
        self.shell.offsets.functions["Cbuf_AddText"].suggested = [0x83000000, mc.CBUF_ADDR]
        out = self.run_cmd("setup", ["y"])
        self.assertIn("0x83000000 doesn't look like a function", out)
        self.assertEqual(self.shell.offsets.functions["Cbuf_AddText"].addr, mc.CBUF_ADDR)

    def test_profiles_with_suggestions(self):
        for short, n in (("bo2", 1), ("mw2", 1), ("mw3", 2), ("bo1", 0)):
            self.assertEqual(len(Offsets(offsets_path(short)).functions["Cbuf_AddText"].suggested), n)

    def test_setup_declined_saves_nothing(self):
        self.run_cmd("setup", ["n"])
        self.assertIsNone(json.loads(self.path.read_text())["functions"]["Cbuf_AddText"]["addr"])

    def test_setup_rejects_suggestion_that_isnt_a_function(self):
        self.xb.write_u32(mc.CBUF_ADDR, 0)  # as if on another title update
        out = self.run_cmd("setup", ["y"])
        self.assertIn("doesn't look like a function", out)
        self.assertIsNone(json.loads(self.path.read_text())["functions"]["Cbuf_AddText"]["addr"])

    def test_setfunc_checks_prologue(self):
        out = self.run_cmd("setfunc Cbuf_AddText 0x83000000")
        self.assertIn("doesn't start like a function", out)
        out = self.run_cmd("setfunc Cbuf_AddText 0x83000000 --force")
        self.assertIn("saved", out)

    def test_preset_and_host_note(self):
        self.shell.offsets.set_func_addr("Cbuf_AddText", mc.CBUF_ADDR)
        out = self.run_cmd("preset moon")
        self.assertIn("affect everyone in your lobby", out)
        self.assertEqual(self.srv.executed[0], "sv_cheats 1")
        self.assertIn("g_gravity 100", self.srv.executed)

    def test_unknown_command_is_sent_with_note(self):
        self.shell.offsets.set_func_addr("Cbuf_AddText", mc.CBUF_ADDR)
        out = self.run_cmd("cmd some_new_dvar 1")
        self.assertIn("isn't in the catalog", out)
        self.assertEqual(self.srv.executed, ["some_new_dvar 1"])

    def test_commands_search(self):
        out = self.run_cmd("commands fov")
        self.assertIn("cg_fov", out)
        self.assertIn("cg_fovScale", out)
        self.assertNotIn("g_gravity", out)
        out = self.run_cmd("commands world")
        self.assertIn("g_gravity", out)
        out = self.run_cmd("commands player")  # a category: no description matches
        self.assertNotIn("cg_thirdPersonAngle", out)

    def test_cod4_profile_hides_newer_commands(self):
        shutil.copy(ROOT / "offsets" / "cod4.json", self.tmp / "cod4.json")
        self.shell = Shell(self.xb, Offsets(self.tmp / "cod4.json"))
        out = self.run_cmd("commands fov")
        self.assertNotIn("cg_fovScale", out)
        self.assertEqual(self.shell.prompt, "cod4> ")


if __name__ == "__main__":
    unittest.main()
