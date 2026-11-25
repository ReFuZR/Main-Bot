# BO2 RGH Tool

A just-for-fun tool for Black Ops 2 and the other Xbox 360 Call of Duty
games on an RGH/JTAG console. From your PC it can:

- read and write your own player's values (name with colour codes, clan tag,
  prestige, XP, FOV, kills, wins and more) over **XBDM**
- find those addresses for you with a guided `wizard`
- run the game's own **console commands** (`cg_fov 90`, `cg_thirdPerson 1`,
  `god`, `noclip`, ...) through the **JRPC2** plugin, with a built-in catalog
  and presets

It needs Python 3.10+ and nothing else.

Prefer a Windows app with buttons? There's a C# version in [`csharp/`](csharp/README.md).

> Use it offline, in private matches, or on your own stealth servers.
> Changing stats (prestige, XP, kills...) and then playing online can get the
> account banned. Commands marked **H** affect everyone in a match you host,
> so use them in private matches. This tool deliberately has nothing that
> targets other players.

## Supported games

`--game` picks the game. The default is `bo2`.

| `--game` | Game | Title ID |
|---|---|---|
| `bo2` | Black Ops II | 415608C3 |
| `bo1` | Black Ops | 41560855 |
| `mw2` | Modern Warfare 2 | 41560817 |
| `mw3` | Modern Warfare 3 | 415608CB |
| `ghosts` | Ghosts | 415608FC |
| `cod4` | Call of Duty 4 | 415607E6 |
| `waw` | World at War | 4156081C |
| `aw` | Advanced Warfare | 41560914 |

Every game has the same fields and ships with **no addresses**. They differ
per title update, so you find them on your console (see `wizard`). What you
find is saved to `offsets/<game>.json` (`--offsets` picks another file).

## Console setup

1. Boot your RGH into a dashboard that loads plugins (Aurora/FSD + Dashlaunch).
2. Load `xbdm.xex`. That covers memory reading/writing, `wizard`, `get`/`set`.
3. For game console commands (`cmd`, `preset`), also load the **JRPC2**
   plugin (`JRPC2.xex`) as another Dashlaunch plugin.
4. Find the console's IP (Aurora shows it), then start the game.

## Usage

```sh
cd bo2-rgh-tool
python -m bo2tool 192.168.1.50                 # BO2, interactive shell
python -m bo2tool 192.168.1.50 --game mw2      # another game
python -m bo2tool --list-games
python -m bo2tool 192.168.1.50 -c "preset fov" # one-shot commands
```

### Your player's values (XBDM)

| Command | What it does |
|---|---|
| `info` | Console name, running XEX, and which game profile is loaded |
| `fields` | List the fields and their addresses |
| `wizard [field ...] [--range start end]` | Guided search that finds and saves missing addresses |
| `get <field>` / `set <field> <value>` | Read/write a field, e.g. `set name ^1Red^7Guy` |
| `freeze <field> <value> [secs]` | Keep re-writing a value until Ctrl+C |
| `find <type> <value> [start end]` / `refine <value>` | Manual memory search (`hex`/`u32`/`i32`/`float`/`str`) |
| `setaddr <field> <addr>` | Save a field address by hand |
| `peek <addr> [len]` / `poke <addr> <type> <value>` | Raw memory |
| `raw <xbdm cmd>` / `reboot [cold]` | Anything else |

Fields in every game: `name`, `clan_tag`, `prestige`, `rank_xp`, `fov`,
`kills`, `deaths`, `wins`, `losses`, `score`, `headshots`, `time_played`,
`match_kills`, `match_score`.

### Game console commands (JRPC2)

| Command | What it does |
|---|---|
| `setup` | Check the `Cbuf_AddText` address and offer the suggested one |
| `cmd <command>` | Run any console command, e.g. `cmd cg_fov 90`. Join several with `;` |
| `commands [search]` | Browse the catalog: `commands fov`, `commands world` |
| `presets` / `preset <name>` | Groups of commands: `fov`, `thirdperson`, `cinematic`, `noir`, `moon`, `slowmo`, `sandbox`, `reset`, ... |
| `funcs` / `setfunc Cbuf_AddText <addr>` | Show / save the function address |

How it works: the game has a function, `Cbuf_AddText`, that queues console
commands. JRPC2 lets the PC call it. Its address differs per title update:

- **BO2 TU18, MW2 TU9 and MW3 TU24** have community-reported addresses
  (MW3 has two conflicting reports, and `setup` tries both). `setup` checks
  each one starts like a function on *your* console, then asks before saving.
  They're unverified, and a wrong address can crash the game (just restart).
- **Other games** have no suggestion. Find the address yourself (for example
  from a disassembly of `default_mp.xex`) and save it with
  `setfunc Cbuf_AddText 0x8xxxxxxx`. The tool refuses addresses that don't
  start like a function unless you add `--force`.

The catalog (`commands.json`, 58 commands) marks each entry:

- **H**: host setting. It changes the match for everyone in your lobby.
- **C**: cheat-protected. Run `sv_cheats 1` first, in a match you host.

`cmd` still sends commands that aren't in the catalog, so anything else the
engine has works too. Add your own entries or presets to `commands.json`.

## Finding offsets: `wizard`

```
bo2> wizard
wizard: 14 field(s) to find: name, clan_tag, prestige, ...
== name (string) - In-game name...
  current value of name in game: YourGamertag
  3 matches
   1) 0x8xxxxxxx  59 6F 75 72 ...  YourGamertag....
  type 'pick N' to choose one of these, or keep narrowing:
  change name in game, then type the new value: pick 1
  found it: name = 0x8xxxxxxx (saved)
== kills (i32) - Career kills...
  current value of kills in game: 15234
  change kills in game, then type the new value: 15241
  found it: kills = 0x8xxxxxxx (saved)
```

It asks for the value you see in game and scans for it. Then you change the
value in game (play a bit, prestige, rename) and type the new one, until only
one match is left. That address is saved to `offsets/<game>.json`. With 8 or fewer
matches it shows previews, and you can `pick N`. `skip` moves on, `quit`
stops, and `wizard kills wins` redoes just those fields.

Tips:
- Career stats (kills, wins, score) are easy: play a match and refine.
- `match_kills` / `match_score` reset each match, so refine mid-game.
- FOV can't be changed in game on the 360. Use `pick` or skip it.
- Your gamertag appears in several places. The one used in game usually sits
  next to the clan tag.
- Full 64 MB scans over XBDM take a few minutes. Narrowing down is quick.

## Trying it without an Xbox

The fake console plays BO2, with `MockPlayer` in memory and a fake
`Cbuf_AddText` at the suggested address that prints each command it gets:

```sh
python -m bo2tool.mock_console --port 7300          # terminal 1
python -m bo2tool 127.0.0.1 --port 7300             # terminal 2
bo2> setup
bo2> preset thirdperson
```

## Tests

```sh
python -m unittest discover -s tests -t .
```

Everything is tested against the fake console only. The JRPC2 wire format is
a clean reimplementation of the protocol, so check it on real hardware
before relying on it.
