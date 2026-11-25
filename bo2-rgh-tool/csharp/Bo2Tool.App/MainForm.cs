// Windows app for BO2 and the other Xbox 360 CoD games on an RGH console.
// Tabs: Player (your values), Finder (find addresses), Commands (console commands via JRPC2),
// Memory (peek/poke). Everything talks to the console off the UI thread, one request at a time.
using System.Globalization;

namespace Bo2Tool.App;

static class Program
{
    [STAThread]
    static void Main()
    {
        Application.SetHighDpiMode(HighDpiMode.SystemAware);
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Application.Run(new MainForm());
    }
}

sealed class MainForm : Form
{
    static readonly Font Mono = new("Consolas", 9f);
    readonly Xbdm xb = new();
    readonly SemaphoreSlim busy = new(1, 1);
    readonly Catalog catalog = Catalog.Load(Path.Combine(AppContext.BaseDirectory, "commands.json"));
    Profile profile = new(GameData.Games[0]);
    CancellationTokenSource? scanCancel;
    List<uint> hits = [];
    bool hostNoteShown;

    // top bar + log
    readonly TextBox ipBox = new() { Text = "192.168.1.", Width = 130 };
    readonly ComboBox gameBox = new() { DropDownStyle = ComboBoxStyle.DropDownList, Width = 260 };
    readonly Button connectBtn = Btn("Connect"), rebootBtn = Btn("Reboot");
    readonly Label statusLbl = Lbl("not connected");
    readonly TextBox logBox = new() { Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Vertical, Dock = DockStyle.Bottom, Height = 120, Font = Mono };

    // Player tab
    readonly ListView fieldList = Grid(("Field", 110), ("Type", 60), ("Address", 95), ("Value", 160), ("Description", 380));
    readonly TextBox valueBox = new() { Width = 200 };
    readonly Button readBtn = Btn("Read all"), setBtn = Btn("Set value");
    readonly CheckBox freezeBox = new() { Text = "Freeze (keep writing)", AutoSize = true, Padding = new(0, 4, 0, 0) };
    readonly System.Windows.Forms.Timer freezeTimer = new() { Interval = 500 };

    // Finder tab
    readonly ComboBox findField = new() { DropDownStyle = ComboBoxStyle.DropDownList, Width = 130 };
    readonly TextBox findValue = new() { Width = 160 }, rangeStart = new() { Text = "0x82000000", Width = 90 }, rangeEnd = new() { Text = "0x86000000", Width = 90 };
    readonly Button newScanBtn = Btn("New scan"), nextScanBtn = Btn("Next scan"), cancelBtn = Btn("Cancel"), saveHitBtn = Btn("Save selected address");
    readonly ProgressBar scanProgress = new() { Width = 200, Height = 20 };
    readonly ListBox hitList = new() { Dock = DockStyle.Fill, Font = Mono };

    // Commands tab
    readonly Label cbufLbl = Lbl("");
    readonly Button setupBtn = Btn("Setup"), setCbufBtn = Btn("Set address");
    readonly TextBox cbufBox = new() { Width = 100 }, searchBox = new() { Width = 200 }, cmdBox = new() { Width = 320 };
    readonly Button sendBtn = Btn("Send"), presetBtn = Btn("Run preset");
    readonly ComboBox presetBox = new() { DropDownStyle = ComboBoxStyle.DropDownList, Width = 130 };
    readonly Label presetLbl = Lbl("");
    readonly ListView cmdList = Grid(("Command", 200), ("Flags", 45), ("Default", 65), ("Description", 500));

    // Memory tab
    readonly TextBox peekAddr = new() { Text = "0x82000000", Width = 100 }, peekLen = new() { Text = "256", Width = 60 };
    readonly TextBox pokeAddr = new() { Width = 100 }, pokeValue = new() { Width = 200 };
    readonly ComboBox pokeType = new() { DropDownStyle = ComboBoxStyle.DropDownList, Width = 70 };
    readonly Button peekBtn = Btn("Peek"), pokeBtn = Btn("Poke");
    readonly TextBox dumpBox = new() { Multiline = true, ReadOnly = true, ScrollBars = ScrollBars.Both, WordWrap = false, Dock = DockStyle.Fill, Font = Mono };

    public MainForm()
    {
        Text = "BO2 RGH Tool - just for fun, offline / private matches";
        Size = new(1000, 680);
        StartPosition = FormStartPosition.CenterScreen;

        gameBox.Items.AddRange(GameData.Games);
        findField.Items.AddRange(GameData.Fields.Select(f => f.Name).ToArray());
        presetBox.Items.AddRange(catalog.Presets.Keys.ToArray());
        pokeType.Items.AddRange(["hex", "u32", "i32", "float", "str"]);
        findField.SelectedIndex = presetBox.SelectedIndex = pokeType.SelectedIndex = 0;

        var tabs = new TabControl { Dock = DockStyle.Fill };
        tabs.TabPages.Add(Page("Player", fieldList,
            Row(Lbl("Value:"), valueBox, setBtn, freezeBox, readBtn),
            Row(Lbl("Select a field, type a value, Set. Fields without an address are found on the Finder tab."))));
        tabs.TabPages.Add(Page("Finder", hitList,
            Row(Lbl("1. Pick a field, type the value you see in game, New scan.  2. Change it in game, type the new value, Next scan.")),
            Row(Lbl("3. Repeat until one is left (it's saved for you), or select one and save it.  Previews show for 50 or fewer.")),
            Row(Lbl("Field:"), findField, Lbl("Value:"), findValue, newScanBtn, nextScanBtn, cancelBtn, scanProgress),
            Row(Lbl("Range:"), rangeStart, Lbl("to"), rangeEnd, saveHitBtn)));
        tabs.TabPages.Add(Page("Commands", cmdList,
            Row(Lbl("Cbuf_AddText:"), cbufLbl, setupBtn, cbufBox, setCbufBtn, Lbl("(needs the JRPC2 plugin on the console)")),
            Row(Lbl("Command:"), cmdBox, sendBtn, Lbl("Preset:"), presetBox, presetBtn, presetLbl),
            Row(Lbl("Search:"), searchBox, Lbl("Double-click fills the command box.  H = affects everyone in a lobby you host (use private matches).  C = needs sv_cheats 1."))));
        tabs.TabPages.Add(Page("Memory", dumpBox,
            Row(Lbl("Address:"), peekAddr, Lbl("Length:"), peekLen, peekBtn),
            Row(Lbl("Poke address:"), pokeAddr, pokeType, pokeValue, pokeBtn)));

        Controls.Add(tabs);
        Controls.Add(logBox);
        Controls.Add(Row(Lbl("Console IP:"), ipBox, Lbl("Game:"), gameBox, connectBtn, rebootBtn, statusLbl));

        gameBox.SelectedIndexChanged += (_, _) => LoadGame((Game)gameBox.SelectedItem!);
        gameBox.SelectedIndex = 0;
        connectBtn.Click += async (_, _) => await ConnectAsync();
        rebootBtn.Click += async (_, _) => await Run("reboot", () => { xb.Reboot(); Log("reboot sent; connect again when the console is back"); });
        readBtn.Click += async (_, _) => await ReadFields();
        setBtn.Click += async (_, _) => await SetField();
        freezeTimer.Tick += async (_, _) => await Freeze();
        freezeBox.CheckedChanged += (_, _) => freezeTimer.Enabled = freezeBox.Checked;
        newScanBtn.Click += async (_, _) => await Scan(newScan: true);
        nextScanBtn.Click += async (_, _) => await Scan(newScan: false);
        cancelBtn.Click += (_, _) => scanCancel?.Cancel();
        saveHitBtn.Click += (_, _) => { if (hitList.SelectedIndex >= 0) SaveHit(GameData.Fields[findField.SelectedIndex], hits[hitList.SelectedIndex]); };
        setupBtn.Click += async (_, _) => await Setup();
        setCbufBtn.Click += async (_, _) => await SetCbuf();
        sendBtn.Click += async (_, _) => await SendCommands(cmdBox.Text.Split(';', StringSplitOptions.TrimEntries | StringSplitOptions.RemoveEmptyEntries));
        cmdBox.KeyDown += (_, e) => { if (e.KeyCode == Keys.Enter) { e.SuppressKeyPress = true; sendBtn.PerformClick(); } };
        presetBtn.Click += async (_, _) => await RunPreset();
        presetBox.SelectedIndexChanged += (_, _) => presetLbl.Text = catalog.Presets[(string)presetBox.SelectedItem!].Desc;
        searchBox.TextChanged += (_, _) => FillCommands();
        cmdList.DoubleClick += (_, _) => { if (cmdList.SelectedItems.Count > 0) cmdBox.Text = (string)cmdList.SelectedItems[0].Tag!; };
        peekBtn.Click += async (_, _) => await Peek();
        pokeBtn.Click += async (_, _) => await Poke();
        presetLbl.Text = catalog.Presets[(string)presetBox.SelectedItem!].Desc;
        FormClosing += (_, _) => { scanCancel?.Cancel(); xb.Dispose(); };
        Log("Load xbdm.xex (and JRPC2 for console commands) as Dashlaunch plugins, start the game, then Connect.");
    }

    // -- layout helpers -----------------------------------------------------------
    static Button Btn(string text) => new() { Text = text, AutoSize = true };
    static Label Lbl(string text) => new() { Text = text, AutoSize = true, Padding = new(0, 6, 0, 0) };

    static FlowLayoutPanel Row(params Control[] controls)
    {
        var row = new FlowLayoutPanel { Dock = DockStyle.Top, AutoSize = true, Padding = new(4, 2, 4, 2) };
        row.Controls.AddRange(controls);
        return row;
    }

    static ListView Grid(params (string Name, int Width)[] columns)
    {
        var list = new ListView { View = View.Details, FullRowSelect = true, MultiSelect = false, Dock = DockStyle.Fill, HideSelection = false };
        foreach (var (name, width) in columns) list.Columns.Add(name, width);
        return list;
    }

    static TabPage Page(string title, Control fill, params Control[] rows)
    {
        var page = new TabPage(title);
        page.Controls.Add(fill); // Fill first, then Top rows in reverse so they stack in order
        foreach (var row in rows.Reverse()) page.Controls.Add(row);
        return page;
    }

    // -- plumbing -----------------------------------------------------------------
    void Log(string text)
    {
        if (InvokeRequired) { BeginInvoke(() => Log(text)); return; }
        logBox.AppendText(text + Environment.NewLine);
    }

    /// <summary>Run console work off the UI thread, one request at a time, logging any error.</summary>
    async Task Run(string what, Action work, bool quiet = false)
    {
        if (!xb.Connected) { if (!quiet) Log("connect first"); return; }
        if (!await busy.WaitAsync(0)) { if (!quiet) Log("busy - wait for the current operation to finish"); return; }
        try { await Task.Run(work); }
        catch (OperationCanceledException) { Log($"{what}: cancelled"); }
        catch (Exception e) { Log($"{what}: {e.Message}"); }
        finally { busy.Release(); }
    }

    async Task ConnectAsync()
    {
        var ip = ipBox.Text.Trim();
        statusLbl.Text = "connecting...";
        try
        {
            var info = await Task.Run(() => { xb.Connect(ip); return (Name: xb.Name(), Xex: xb.Xex()); });
            statusLbl.Text = $"connected: {info.Name}";
            Log($"connected to {info.Name} ({ip}), running {info.Xex}");
            if (!info.Xex.Contains("default_mp.xex", StringComparison.OrdinalIgnoreCase))
                Log("warning: doesn't look like multiplayer (default_mp.xex); wrong game or mode?");
            await ReadFields();
        }
        catch (Exception e)
        {
            statusLbl.Text = "not connected";
            Log($"could not connect to {ip}: {e.Message}. Is the console on, the dashboard loaded and the XBDM plugin enabled?");
        }
    }

    void LoadGame(Game game)
    {
        profile = new Profile(game);
        hits = [];
        hitList.Items.Clear();
        FillFields();
        FillCommands();
        cbufLbl.Text = profile.Addrs.TryGetValue(GameData.Cbuf, out var a) ? $"0x{a:X8}"
            : "not set" + (game.Cbuf.Length > 0 ? $" (suggested {string.Join(", ", game.Cbuf)})" : "");
    }

    // -- Player tab ---------------------------------------------------------------
    void FillFields(Dictionary<string, string>? values = null)
    {
        fieldList.BeginUpdate();
        var selected = fieldList.SelectedIndices.Count > 0 ? fieldList.SelectedIndices[0] : -1;
        fieldList.Items.Clear();
        foreach (var f in GameData.Fields)
        {
            var addr = profile.Addrs.TryGetValue(f.Name, out var a) ? $"0x{a:X8}" : "(not found)";
            var desc = f.Name == "prestige" ? $"Prestige level (0-{profile.Game.Prestige})." : f.Desc;
            fieldList.Items.Add(new ListViewItem([f.Name, f.Type, addr, values?.GetValueOrDefault(f.Name) ?? "", desc]) { Tag = f });
        }
        if (selected >= 0) fieldList.Items[selected].Selected = true;
        fieldList.EndUpdate();
    }

    Field? SelectedField() => fieldList.SelectedItems.Count > 0 ? (Field)fieldList.SelectedItems[0].Tag! : null;

    static string Show(object value) => value is string s
        ? (s.Contains('^') ? $"{s}   ({GameData.StripColors(s)})" : s)
        : Convert.ToString(value, CultureInfo.InvariantCulture)!;

    async Task ReadFields() => await Run("read", () =>
    {
        var values = GameData.Fields.Where(f => profile.Addrs.ContainsKey(f.Name))
            .ToDictionary(f => f.Name, f => { try { return Show(xb.Get(profile.Addrs[f.Name], f.Type, f.Size)); } catch (XbdmException e) { return e.Message; } });
        BeginInvoke(() => FillFields(values));
    });

    async Task SetField()
    {
        if (SelectedField() is not { } f) { Log("select a field first"); return; }
        var value = valueBox.Text;
        await Run($"set {f.Name}", () =>
        {
            xb.Put(profile.Addr(f.Name), f.Type, value, f.Size);
            Log($"{f.Name} -> {Show(xb.Get(profile.Addr(f.Name), f.Type, f.Size))}");
        });
        await ReadFields();
    }

    async Task Freeze()
    {
        if (SelectedField() is not { } f || !profile.Addrs.ContainsKey(f.Name)) return;
        var value = valueBox.Text;
        await Run("freeze", () => xb.Put(profile.Addr(f.Name), f.Type, value, f.Size), quiet: true);
    }

    // -- Finder tab ---------------------------------------------------------------
    async Task Scan(bool newScan)
    {
        var field = GameData.Fields[findField.SelectedIndex];
        string value = findValue.Text, startText = rangeStart.Text, endText = rangeEnd.Text; // read controls on the UI thread
        if (!newScan && hits.Count == 0) { Log("no previous results: start with New scan"); return; }
        scanCancel = new CancellationTokenSource();
        var token = scanCancel.Token;
        scanProgress.Value = 0;
        await Run("scan", () =>
        {
            var pattern = Codec.Encode(field.FindKind, value);
            if (newScan)
            {
                uint start = Codec.ParseAddr(startText), end = Codec.ParseAddr(endText);
                Log($"searching 0x{start:X8}-0x{end:X8} for {field.Name} = {value}...");
                int last = -1;
                hits = xb.Scan(start, end, pattern, progress: (done, total) =>
                {
                    int pct = (int)(done * 100 / total);
                    if (pct != last) { last = pct; BeginInvoke(() => scanProgress.Value = pct); }
                }, cancel: token);
            }
            else hits = xb.Refine(hits, pattern);
            var lines = hits.Select(a => $"0x{a:X8}" + (hits.Count <= 50 ? $"  {Preview(a)}" : "")).ToArray();
            Log($"{hits.Count} match(es)" + (hits.Count > 1 ? $": change {field.Name} in game, type the new value, Next scan" : ""));
            BeginInvoke(() =>
            {
                hitList.Items.Clear();
                hitList.Items.AddRange(lines.Take(1000).ToArray<object>());
                scanProgress.Value = 100;
                if (hits.Count == 1) SaveHit(field, hits[0]);
            });
        });
    }

    string Preview(uint addr)
    {
        try { var raw = xb.Read(addr, 16); return $"{Codec.Spaced(raw)}  {Codec.Printable(raw)}"; }
        catch (XbdmException) { return "(unreadable)"; }
    }

    void SaveHit(Field field, uint addr)
    {
        if (MessageBox.Show(this, $"Save 0x{addr:X8} as {field.Name} for {profile.Game.Short}?", "Save address", MessageBoxButtons.YesNo) != DialogResult.Yes) return;
        profile.Save(field.Name, addr);
        Log($"saved {field.Name} = 0x{addr:X8} to {profile.Path}");
        FillFields();
    }

    // -- Commands tab -------------------------------------------------------------
    void FillCommands()
    {
        cmdList.BeginUpdate();
        cmdList.Items.Clear();
        foreach (var c in catalog.Search(profile.Game.Short, searchBox.Text))
            cmdList.Items.Add(new ListViewItem([c.Name, c.Flags, c.Default ?? "", c.Desc]) { Tag = c.Example ?? c.Name });
        cmdList.EndUpdate();
    }

    async Task SendCommands(IReadOnlyList<string> commands)
    {
        if (commands.Count == 0) { Log("type a command first, e.g. cg_fov 90"); return; }
        var game = profile.Game.Short;
        await Run("cmd", () =>
        {
            var addr = profile.Addr(GameData.Cbuf);
            foreach (var c in commands)
            {
                if (catalog.Note(c, game) is { } note && (!note.StartsWith("host") || !hostNoteShown))
                {
                    Log("  note: " + note);
                    hostNoteShown |= note.StartsWith("host");
                }
                xb.Call(addr, 0, c + "\n");
                Log($"  > {c}");
            }
        });
    }

    async Task RunPreset()
    {
        var (run, skipped) = catalog.PresetCommands((string)presetBox.SelectedItem!, profile.Game.Short);
        if (skipped.Count > 0) Log($"  skipping (not in {profile.Game.Short}): {string.Join(", ", skipped)}");
        await SendCommands(run);
    }

    async Task Setup() => await Run("setup", () =>
    {
        if (profile.Addrs.TryGetValue(GameData.Cbuf, out var current))
        {
            Log($"{GameData.Cbuf}: 0x{current:X8} " + (xb.IsFunction(current) ? "looks good" : "does NOT look like a function"));
            return;
        }
        if (profile.Game.Cbuf.Length == 0) Log($"no suggested {GameData.Cbuf} address for {profile.Game.Short}; find it yourself and set it by hand");
        foreach (var addr in profile.Game.Cbuf.Select(Codec.ParseAddr))
        {
            if (!xb.IsFunction(addr)) { Log($"suggested 0x{addr:X8} doesn't look like a function on your console (different title update?)"); continue; }
            var answer = Invoke(() => MessageBox.Show(this,
                $"Suggested {GameData.Cbuf} 0x{addr:X8} looks like a function start.\n\nIt's community-reported and unverified; a wrong address " +
                "can crash the game (just restart it).\n\nSave it? Then test with something harmless like cg_drawFPS 1.",
                "Setup", MessageBoxButtons.YesNo, MessageBoxIcon.Question));
            if (answer != DialogResult.Yes) continue;
            profile.Save(GameData.Cbuf, addr);
            Log($"saved {GameData.Cbuf} = 0x{addr:X8}");
            BeginInvoke(() => { cbufLbl.Text = $"0x{addr:X8}"; cmdBox.Text = "cg_drawFPS 1"; });
            return;
        }
    });

    async Task SetCbuf()
    {
        var text = cbufBox.Text;
        await Run("set address", () =>
        {
            var addr = Codec.ParseAddr(text);
            if (!xb.IsFunction(addr) && Invoke(() => MessageBox.Show(this, $"0x{addr:X8} doesn't start like a function. Save it anyway?",
                    "Set address", MessageBoxButtons.YesNo, MessageBoxIcon.Warning)) != DialogResult.Yes) return;
            profile.Save(GameData.Cbuf, addr);
            Log($"saved {GameData.Cbuf} = 0x{addr:X8}");
            BeginInvoke(() => cbufLbl.Text = $"0x{addr:X8}");
        });
    }

    // -- Memory tab ---------------------------------------------------------------
    async Task Poke()
    {
        string addrText = pokeAddr.Text, type = (string)pokeType.SelectedItem!, value = pokeValue.Text; // read controls on the UI thread
        await Run("poke", () =>
        {
            xb.Write(Codec.ParseAddr(addrText), Codec.Encode(type, value));
            Log($"poked 0x{Codec.ParseAddr(addrText):X8}");
        });
    }

    async Task Peek()
    {
        string addrText = peekAddr.Text, lenText = peekLen.Text;
        await Run("peek", () =>
        {
            var addr = Codec.ParseAddr(addrText);
            var dump = Codec.HexDump(addr, xb.Read(addr, (int)Codec.ParseInt(lenText)));
            BeginInvoke(() => dumpBox.Text = dump);
        });
    }
}
