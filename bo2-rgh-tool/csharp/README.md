# BO2 RGH Tool: C# Windows app

A Windows app with buttons, doing the same things as the Python version in
the folder above. It talks to the console directly over XBDM, so you **don't
need the Xbox 360 SDK** or XDevkit installed.

> Not tested on Windows or a real console yet. The core (connection, memory,
> console commands, data) is tested against the fake console, and the window
> code compiles, but nobody has clicked through it. Please report what breaks.

## Build and run

You need the [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0) on Windows.

- **Visual Studio:** open `Bo2Tool.sln`, set **Bo2Tool.App** as the startup
  project, and press F5.
- **Command line:**
  ```
  cd bo2-rgh-tool\csharp
  dotnet run --project Bo2Tool.App
  ```
- **A single .exe to share:**
  ```
  dotnet publish Bo2Tool.App -c Release -r win-x64 --self-contained -p:PublishSingleFile=true
  ```
  The exe is in `Bo2Tool.App\bin\Release\net8.0-windows\win-x64\publish\`.
  Keep `commands.json` next to it.

## Using it

Set up the console as in the [main README](../README.md#console-setup):
`xbdm.xex` as a Dashlaunch plugin, plus `JRPC2.xex` for console commands.
Then type the console IP, pick the game and click **Connect**.

| Tab | What it does |
|---|---|
| **Player** | Your values (name, clan tag, prestige, XP, FOV, kills, position, ...). Select one, type a value, **Set value**. **Freeze** keeps writing it. **Save position** / **Load position** (5 slots) teleport you back to a saved spot, once `pos_x`/`pos_y`/`pos_z` are found (offline or a private match you host). |
| **Finder** | Finds field addresses, like the Python `wizard`. Pick a field, type the value you see in game (or `?` for one you can't see, like your position), **New scan**. Change it in game, then type the new value or pick **same / changed / more / less**, and **Next scan**. When one match is left it offers to save it. The list shows each match with its current value (up to 1,000). Select one and **Save selected address** to pick it yourself. |
| **Commands** | Game console commands. **Setup** checks the suggested `Cbuf_AddText` address (BO2, MW2, MW3) on your console and asks before saving it. Then type a command (`cg_fov 90`, several joined with `;`) and **Send**, or run a **preset**. The list shows every catalog command for the game: **H** = affects everyone in a lobby you host, **C** = needs `sv_cheats 1`. |
| **Memory** | Hexdump (**Peek**) and raw writes (**Poke**). |

Found addresses are saved to `offsets\<game>.json` next to the exe, in the
same format as the Python version, so you can copy the files between the two.

> Changing stats (prestige, XP, kills...) and then playing online can get the
> account banned. Use host settings in private matches.

## Projects

| Project | What it is |
|---|---|
| `Bo2Tool.Core` | XBDM + JRPC2 client, games, fields and the command catalog. Runs anywhere. |
| `Bo2Tool.App` | The Windows Forms app. Windows only. |
| `Bo2Tool.Tests` | Tests for the core. They start the Python fake console, so `python` must be on PATH: `dotnet test Bo2Tool.Tests` |
