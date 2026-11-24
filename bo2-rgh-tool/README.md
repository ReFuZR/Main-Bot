# BO2 RGH Tool

A just-for-fun Black Ops 2 tool for an RGH/JTAG Xbox 360. It talks to the
console over **XBDM**, the debug monitor on TCP port 730, so you can read and
write game memory from your PC: name changer (with colour codes), prestige,
FOV and anything else you can find.

It needs Python 3.10+ and nothing else.

> Stick to offline play, private matches or your own stealth servers. Modifying
> stats on official servers can get the account banned.

## Console setup

1. Boot your RGH into a dashboard that loads `xbdm.xex` as a plugin
   (Aurora/FSD/Dashlaunch `plugin1 = ...\xbdm.xex`).
2. Find the console's IP (Aurora shows it in the status bar).
3. Start BO2.

## Usage

```sh
cd bo2-rgh-tool
python -m bo2tool 192.168.1.50            # interactive shell
python -m bo2tool 192.168.1.50 -c info -c "get name"   # one-shot commands
```

| Command | What it does |
|---|---|
| `info` | Console name and the running XEX (warns if it isn't `default_mp.xex`) |
| `fields` | List the named fields in `offsets.json` and their addresses |
| `get <field>` | Read a field, e.g. `get name` |
| `set <field> <value>` | Write a field, e.g. `set name ^1Red^7Guy` |
| `freeze <field> <value> [secs]` | Keep re-writing a value until Ctrl+C |
| `find <type> <value> [start end]` | Scan memory. Type is `hex`/`u32`/`i32`/`float`/`str` |
| `refine <value>` | Keep only the previous `find` hits that now hold `<value>` |
| `setaddr <field> <addr>` | Save an address into `offsets.json` |
| `peek <addr> [len]` | Hexdump memory |
| `poke <addr> <type> <value>` | Write raw memory |
| `raw <xbdm cmd>` | Send any XBDM command, e.g. `raw systime` |
| `reboot [cold]` | Reboot the console |

## Finding offsets

`offsets.json` ships **empty on purpose**. Addresses change between title
updates, and copied offset lists are often wrong. Finding them yourself is
the fun part, cheat-engine style:

```
bo2> find str YourGamertag            # the in-game name
3 hit(s)
  0x8xxxxxxx ...
bo2> peek 0x8xxxxxxx                  # look at each to pick the right one
bo2> setaddr name 0x8xxxxxxx
bo2> set name ^5Blue^7Name

bo2> find i32 4                       # e.g. your current prestige
812 hit(s)
   ...prestige up / change it in game...
bo2> refine 5
1 hit(s)
bo2> setaddr prestige 0x8xxxxxxx
```

The default scan range is `0x82000000-0x86000000`. Pass `start end` to
narrow or move it. Over XBDM a full 64 MB scan takes a while.

Xbox 360 is big-endian, and the tool handles that for `u32`/`i32`/`float`.

## Trying it without an Xbox

A fake console is included:

```sh
python -m bo2tool.mock_console --port 7300          # terminal 1
python -m bo2tool 127.0.0.1 --port 7300             # terminal 2
bo2> find str MockPlayer
```

## Tests

```sh
python -m unittest discover -s tests -t .
```
