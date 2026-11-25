// Game profiles, player fields and the console-command catalog (same data as the Python version).
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Bo2Tool;

/// <summary>Cbuf = community-reported Cbuf_AddText addresses: unverified, Setup checks them first.</summary>
public record Game(string Short, string Name, string TitleId, string Tu, int Prestige, params string[] Cbuf)
{
    public override string ToString() => $"{Name} ({Tu})";
}

public record Field(string Name, string Type, int Size, string Desc)
{
    public string FindKind => Type == "string" ? "str" : Type == "bytes" ? "hex" : Type;
}

public static class GameData
{
    public const string Cbuf = "Cbuf_AddText"; // Cbuf_AddText(int localClientNum, const char *text) queues console commands

    public static readonly Game[] Games =
    [
        new("bo2", "Call of Duty: Black Ops II", "415608C3", "TU18", 15, "0x824015E0"),
        new("bo1", "Call of Duty: Black Ops", "41560855", "TU11", 15),
        new("mw2", "Call of Duty: Modern Warfare 2", "41560817", "TU9", 10, "0x82224990"),
        new("mw3", "Call of Duty: Modern Warfare 3", "415608CB", "TU24", 20, "0x8228DAC0", "0x82287F68"), // conflicting reports
        new("ghosts", "Call of Duty: Ghosts", "415608FC", "TU17", 10),
        new("cod4", "Call of Duty 4: Modern Warfare", "415607E6", "TU4", 10),
        new("waw", "Call of Duty: World at War", "4156081C", "TU7", 10),
        new("aw", "Call of Duty: Advanced Warfare", "41560914", "TU17", 10),
    ];

    public static readonly Field[] Fields =
    [
        new("name", "string", 32, "In-game name. Supports colour codes like ^1 (red) ... ^7 (white)."),
        new("clan_tag", "string", 5, "Clan tag (4 characters + terminator)."),
        new("prestige", "i32", 4, "Prestige level."),
        new("rank_xp", "i32", 4, "Rank XP."),
        new("fov", "float", 4, "cg_fov value (default 65.0)."),
        new("kills", "i32", 4, "Career kills. Goes up as you play, easy to refine."),
        new("deaths", "i32", 4, "Career deaths."),
        new("wins", "i32", 4, "Career wins."),
        new("losses", "i32", 4, "Career losses."),
        new("score", "i32", 4, "Career score."),
        new("headshots", "i32", 4, "Career headshots."),
        new("time_played", "i32", 4, "Time played in seconds."),
        new("match_kills", "i32", 4, "Kills in the current match (resets each match)."),
        new("match_score", "i32", 4, "Score in the current match (resets each match)."),
    ];

    public static Game GameByShort(string s) => Games.FirstOrDefault(g => g.Short == s)
        ?? throw new KeyNotFoundException($"unknown game '{s}' (known: {string.Join(", ", Games.Select(g => g.Short))})");

    public static string StripColors(string name) => Regex.Replace(name, @"\^[0-9]", "");
}

/// <summary>A game plus the addresses found for it, saved as {"name": "0x8...", ...} (same format as Python).</summary>
public class Profile
{
    public Game Game { get; }
    public string Path { get; }
    public Dictionary<string, uint> Addrs { get; } = [];

    public Profile(Game game, string? path = null)
    {
        Game = game;
        Path = path ?? System.IO.Path.Combine(AppContext.BaseDirectory, "offsets", $"{game.Short}.json");
        if (File.Exists(Path) && File.ReadAllText(Path).Trim() is { Length: > 0 } json) // a missing or empty file = nothing found yet
            foreach (var (k, v) in JsonSerializer.Deserialize<Dictionary<string, string>>(json)!)
                Addrs[k] = Codec.ParseAddr(v);
    }

    public uint Addr(string name) => Addrs.TryGetValue(name, out var a) ? a : throw new InvalidOperationException(
        $"'{name}' has no address yet; " + (name == GameData.Cbuf ? "use Setup or set it by hand" : "find it on the Finder tab first"));

    public void Save(string name, uint addr)
    {
        Addrs[name] = addr;
        Directory.CreateDirectory(System.IO.Path.GetDirectoryName(Path)!);
        File.WriteAllText(Path, JsonSerializer.Serialize(Addrs.ToDictionary(kv => kv.Key, kv => $"0x{kv.Value:X8}"),
                                                         new JsonSerializerOptions { WriteIndented = true }) + "\n");
    }
}

/// <summary>Flags: H = affects everyone in a match you host, C = needs sv_cheats 1.</summary>
public record Command(string Name, string Cat, string Flags, string[] Games, string Desc, string? Default, string? Example)
{
    readonly Regex pattern = new("^" + Regex.Replace(Regex.Escape(Name), "<[^>]+>", ".+") + "$", RegexOptions.IgnoreCase);
    public bool Matches(string word) => pattern.IsMatch(word); // scr_<gametype>_timelimit matches scr_dm_timelimit
}

public record Preset(string Name, string Desc, string[] Commands);

public class Catalog
{
    public List<Command> Commands { get; } = [];
    public Dictionary<string, Preset> Presets { get; } = [];

    public static Catalog Load(string path)
    {
        using var doc = JsonDocument.Parse(File.ReadAllText(path));
        var root = doc.RootElement;
        string[] Strings(JsonElement e) => e.EnumerateArray().Select(x => x.GetString()!).ToArray();
        string? Opt(JsonElement e, string key) => e.TryGetProperty(key, out var v) ? v.GetString() : null;
        var catalog = new Catalog();
        foreach (var c in root.GetProperty("commands").EnumerateArray())
        {
            var games = c.GetProperty("games");
            catalog.Commands.Add(new(c.GetProperty("name").GetString()!, c.GetProperty("cat").GetString()!,
                c.GetProperty("flags").GetString()!,
                Strings(games.ValueKind == JsonValueKind.String ? root.GetProperty("groups").GetProperty(games.GetString()!) : games),
                c.GetProperty("desc").GetString()!, Opt(c, "default"), Opt(c, "example")));
        }
        foreach (var p in root.GetProperty("presets").EnumerateObject())
            catalog.Presets[p.Name] = new(p.Name, p.Value.GetProperty("desc").GetString()!, Strings(p.Value.GetProperty("commands")));
        return catalog;
    }

    public Command? Lookup(string word) => Commands.FirstOrDefault(c => c.Matches(word));

    public List<Command> Search(string game, string term = "")
    {
        term = term.Trim().ToLowerInvariant();
        var mine = Commands.Where(c => c.Games.Contains(game));
        return (Commands.Any(c => c.Cat == term)
            ? mine.Where(c => c.Cat == term)
            : mine.Where(c => c.Name.Contains(term, StringComparison.OrdinalIgnoreCase) || c.Desc.Contains(term, StringComparison.OrdinalIgnoreCase)))
            .OrderBy(c => c.Cat).ThenBy(c => c.Name).ToList();
    }

    /// <summary>(commands to run, commands skipped because this game doesn't have them).</summary>
    public (List<string> Run, List<string> Skipped) PresetCommands(string name, string game)
    {
        if (!Presets.TryGetValue(name, out var preset)) throw new KeyNotFoundException($"unknown preset '{name}'");
        var groups = preset.Commands.ToLookup(c => Lookup(c.Split(' ')[0]) is not { } cmd || cmd.Games.Contains(game));
        return (groups[true].ToList(), groups[false].ToList());
    }

    /// <summary>Notes to show before sending a command (unknown, not for this game, host setting).</summary>
    public string? Note(string command, string game)
    {
        var word = command.Split(' ')[0];
        return Lookup(word) switch
        {
            null => $"'{word}' isn't in the catalog; sending anyway",
            var c when !c.Games.Contains(game) => $"'{c.Name}' isn't listed for {game}; sending anyway",
            var c when c.Flags.Contains('H') => "host setting: affects everyone in your lobby - use a private match",
            _ => null,
        };
    }
}
