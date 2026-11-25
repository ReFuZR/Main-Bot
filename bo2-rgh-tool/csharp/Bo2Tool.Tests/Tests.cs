// Runs the C# core against the Python fake console (python -m bo2tool.mock_console), so both
// versions are checked against the same fake. Needs python3 (or python) on PATH.
using System.Diagnostics;
using System.Net;
using System.Net.Sockets;
using Bo2Tool;
using Xunit;

public sealed class MockConsole : IDisposable
{
    public const uint Name = 0x83551E00, Prestige = 0x83551E40, Fov = 0x83551E44, Cbuf = 0x824015E0;
    readonly Process process;
    public int Port { get; }

    public MockConsole()
    {
        var listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        Port = ((IPEndPoint)listener.LocalEndpoint).Port;
        listener.Stop();
        var python = OperatingSystem.IsWindows() ? "python" : "python3";
        var root = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "../../../../.."));
        process = Process.Start(new ProcessStartInfo(python, $"-m bo2tool.mock_console --port {Port}")
            { WorkingDirectory = root, RedirectStandardOutput = true })!;
        for (var deadline = DateTime.UtcNow.AddSeconds(10); ; Thread.Sleep(100))
        {
            try { new TcpClient("127.0.0.1", Port).Dispose(); return; }
            catch (SocketException) when (DateTime.UtcNow < deadline) { }
        }
    }

    public Xbdm Connect() => new Xbdm().Connect("127.0.0.1", Port);

    public void Dispose() { process.Kill(); process.Dispose(); }
}

public class OfflineTests
{
    [Fact]
    public void EncodesValuesBigEndian()
    {
        Assert.Equal("DEADBEEF", Convert.ToHexString(Codec.Encode("u32", "0xDEADBEEF")));
        Assert.Equal("FFFFFFFF", Convert.ToHexString(Codec.Encode("i32", "-1")));
        Assert.Equal("42B40000", Convert.ToHexString(Codec.Encode("float", "90")));
        Assert.Equal(5, Codec.Encode("string", "Tag", 5).Length);
        Assert.Throws<ArgumentException>(() => Codec.Encode("string", "TOOLONG", 5));
    }

    [Fact]
    public void JrpcArgumentsMatchThePythonVersion()
    {
        Assert.Equal("7/11\\63675F666F762039300A00\\", Codec.JrpcArg("cg_fov 90\n"));
        Assert.Equal("1\\-1\\", Codec.JrpcArg(0xFFFFFFFFu));
        Assert.Equal("1\\0\\", Codec.JrpcArg(0));
    }

    [Fact]
    public void CatalogLoadsTheSharedCommandsJson()
    {
        var cat = Catalog.Load(Path.Combine(AppContext.BaseDirectory, "commands.json"));
        Assert.True(cat.Commands.Count > 50);
        Assert.All(cat.Commands, c => Assert.Subset(GameData.Games.Select(g => g.Short).ToHashSet(), c.Games.ToHashSet()));
        Assert.Equal("scr_<gametype>_scorelimit", cat.Lookup("scr_dm_scorelimit")?.Name);
        var (run, skipped) = cat.PresetCommands("fov", "cod4");
        Assert.Equal(["cg_fov 90"], run);
        Assert.Equal(["cg_fovScale 1.15"], skipped);
        Assert.DoesNotContain(cat.Search("bo2", "player"), c => c.Name == "cg_thirdPersonAngle");
        Assert.Contains("host setting", cat.Note("g_gravity 100", "bo2"));
        Assert.Equal("RedGuy", GameData.StripColors("^1Red^7Guy"));
    }

    [Fact]
    public void ProfileSavesInThePythonFormat()
    {
        var path = Path.GetTempFileName();
        new Profile(GameData.GameByShort("bo2"), path).Save("name", 0x83551E00);
        Assert.Contains("\"name\": \"0x83551E00\"", File.ReadAllText(path));
        Assert.Equal(0x83551E00u, new Profile(GameData.GameByShort("bo2"), path).Addr("name"));
        Assert.Throws<InvalidOperationException>(() => new Profile(GameData.GameByShort("bo2"), path).Addr("prestige"));
        File.Delete(path);
    }
}

public class ConsoleTests(MockConsole mock) : IClassFixture<MockConsole>
{
    [Fact]
    public void ReadsAndWritesTypedValues()
    {
        using var xb = mock.Connect();
        Assert.Equal("MockXbox", xb.Name());
        Assert.EndsWith("default_mp.xex", xb.Xex());
        Assert.Equal("MockPlayer", xb.Get(MockConsole.Name, "string", 32));
        Assert.Equal(10, xb.Get(MockConsole.Prestige, "i32"));
        xb.Put(MockConsole.Fov, "float", "90");
        Assert.Equal(90f, xb.Get(MockConsole.Fov, "float"));
        xb.Put(MockConsole.Fov, "float", "65");
    }

    [Fact]
    public void ChunkedWritesAndUnmappedReads()
    {
        using var xb = mock.Connect();
        var data = Enumerable.Range(0, 768).Select(i => (byte)i).ToArray();
        xb.Write(0x83000000, data);
        Assert.Equal(data, xb.Read(0x83000000, data.Length));
        Assert.Throws<XbdmException>(() => xb.Read(0x10000000, 4));
    }

    [Fact]
    public void ScanFindsAcrossChunksSkipsUnmappedAndRefines()
    {
        using var xb = mock.Connect();
        xb.Write(0x8310FFFE, "ABCD"u8.ToArray());
        Assert.Equal([0x8310FFFEu], xb.Scan(0x83100000, 0x83120000, "ABCD"u8.ToArray()));
        xb.Write(0x82000010, "Needle"u8.ToArray());
        Assert.Equal([0x82000010u], xb.Scan(0x81FE0000, 0x82010000, "Needle"u8.ToArray()));
        xb.Put(0x83200000, "i32", "77");
        xb.Put(0x83200100, "i32", "77");
        var hits = xb.Scan(0x83200000, 0x83201000, Codec.Encode("i32", "77"));
        xb.Put(0x83200100, "i32", "78");
        Assert.Equal([0x83200100u], xb.Refine(hits, Codec.Encode("i32", "78")));
    }

    [Fact]
    public void RunsConsoleCommandsThroughJrpc()
    {
        using var xb = mock.Connect();
        Assert.True(xb.IsFunction(MockConsole.Cbuf));
        Assert.False(xb.IsFunction(0x83000100));
        xb.Call(MockConsole.Cbuf, 0, "cg_fov 90\n"); // mock answers buf_addr first, so this also tests polling
        var e = Assert.Throws<XbdmException>(() => xb.Call(0x83000100, 0, "x"));
        Assert.Contains("no function", e.Message);
    }
}
