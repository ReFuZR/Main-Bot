// XBDM client (TCP 730 on RGH/JTAG consoles) with JRPC2 remote calls.
// XBDM is line based: "201- connected" on connect, then e.g. "getmem addr=0x.. length=0x.."
// -> "211- ...", hex lines ("??" = unreadable), ".". The JRPC2 plugin adds "consolefeatures",
// which calls a function in the game. The Xbox 360 is big-endian PowerPC.
using System.Buffers.Binary;
using System.Globalization;
using System.Net.Sockets;
using System.Text;
using System.Text.RegularExpressions;

namespace Bo2Tool;

public class XbdmException(string message, Exception? inner = null) : Exception(message, inner);

public static class Codec
{
    public static readonly Encoding Latin1 = Encoding.Latin1;

    /// <summary>Text -> bytes for str/string, hex/bytes, u32, i32 or float. size = fixed field size.</summary>
    public static byte[] Encode(string kind, string value, int? size = null)
    {
        switch (kind)
        {
            case "str" or "string":
                var text = Latin1.GetBytes(value);
                if (size is int n)
                {
                    if (text.Length >= n) throw new ArgumentException($"string too long for {n}-byte field");
                    Array.Resize(ref text, n); // terminate and pad with zeros
                }
                return text;
            case "hex" or "bytes":
                var data = Convert.FromHexString(value.Replace(" ", ""));
                if (kind == "bytes" && size is int m && data.Length != m) throw new ArgumentException($"expected {m} bytes");
                return data;
            case "float":
                var f = new byte[4];
                BinaryPrimitives.WriteSingleBigEndian(f, float.Parse(value, CultureInfo.InvariantCulture));
                return f;
            case "u32" or "i32":
                var i = new byte[4];
                BinaryPrimitives.WriteUInt32BigEndian(i, unchecked((uint)ParseInt(value)));
                return i;
            default:
                throw new ArgumentException($"unknown type '{kind}' (hex/u32/i32/float/str)");
        }
    }

    public static long ParseInt(string s) => s.Trim().StartsWith("0x", StringComparison.OrdinalIgnoreCase)
        ? Convert.ToInt64(s.Trim()[2..], 16) : long.Parse(s, CultureInfo.InvariantCulture);

    public static uint ParseAddr(string s) => checked((uint)ParseInt(s));

    /// <summary>One JRPC2 argument: int "1\n\", float "3\f\", string/bytes "7/len\HEX\".</summary>
    public static string JrpcArg(object arg) => arg switch
    {
        float f => $"3\\{f.ToString("R", CultureInfo.InvariantCulture)}\\",
        int i => $"1\\{i}\\",
        uint u => $"1\\{unchecked((int)u)}\\",
        string s => JrpcArg(Latin1.GetBytes(s)),
        byte[] b => $"7/{b.Length + 1}\\{Convert.ToHexString(b)}00\\", // C strings need their terminator
        _ => throw new ArgumentException($"unsupported JRPC argument type: {arg.GetType().Name}"),
    };

    public static string Printable(byte[] data) => new(data.Select(b => b is >= 32 and < 127 ? (char)b : '.').ToArray());

    public static string HexDump(uint addr, byte[] data) => string.Join(Environment.NewLine,
        data.Chunk(16).Select((row, i) => $"{addr + i * 16:X8}  {Spaced(row),-47}  {Printable(row)}"));

    public static string Spaced(byte[] data) => string.Join(" ", data.Select(b => b.ToString("X2")));
}

public sealed class Xbdm : IDisposable
{
    static readonly uint[] Prologues = [0x7D8802A6, 0x7C0802A6]; // mflr r12 / mflr r0
    TcpClient? client;
    BufferedStream? stream;

    public bool Connected => client?.Connected == true;

    public Xbdm Connect(string host, int port = 730, int timeoutMs = 5000)
    {
        Dispose();
        client = new TcpClient { NoDelay = true, ReceiveTimeout = timeoutMs, SendTimeout = timeoutMs }; // lots of tiny round trips
        try
        {
            if (!client.ConnectAsync(host, port).Wait(timeoutMs)) throw new XbdmException($"timed out connecting to {host}:{port}");
        }
        catch (AggregateException e) { throw new XbdmException(e.InnerException!.Message, e); }
        stream = new BufferedStream(client.GetStream());
        if (Status().Code != 201) throw new XbdmException("unexpected greeting");
        return this;
    }

    public void Dispose()
    {
        if (client == null) return;
        try { Write("bye\r\n"); } catch (Exception) { }
        client.Dispose();
        client = null;
        stream = null;
    }

    void Write(string text)
    {
        stream!.Write(Codec.Latin1.GetBytes(text));
        stream.Flush();
    }

    string Line()
    {
        if (stream == null) throw new XbdmException("not connected");
        var sb = new StringBuilder();
        while (true)
        {
            int b = stream.ReadByte();
            if (b < 0) throw new XbdmException("connection closed by console");
            if (b == '\n' && sb.Length > 0 && sb[^1] == '\r') return sb.ToString(0, sb.Length - 1);
            sb.Append((char)b);
        }
    }

    (int Code, string Message) Status()
    {
        var line = Line();
        if (line.Length < 3 || !int.TryParse(line[..3], out int code)) throw new XbdmException($"malformed response: {line}");
        return (code, line.Length > 5 ? line[5..] : "");
    }

    /// <summary>Body of a multiline reply, up to the closing ".".</summary>
    public List<string> Lines()
    {
        var lines = new List<string>();
        for (var line = Line(); line != "."; line = Line()) lines.Add(line);
        return lines;
    }

    public (int Code, string Message) Send(string command)
    {
        if (stream == null) throw new XbdmException("not connected");
        Write(command + "\r\n");
        var (code, msg) = Status();
        if (code >= 400) throw new XbdmException($"{command.Split(' ')[0]}: {code}- {msg}");
        return (code, msg);
    }

    // -- console ----------------------------------------------------------------
    public string Name() => Send("dbgname").Message;

    public string Xex()
    {
        Send("xbeinfo running");
        return Lines().FirstOrDefault(l => l.StartsWith("name="))?[5..].Trim('"') ?? "?";
    }

    public void Reboot(bool cold = false) => Send(cold ? "magicboot cold" : "magicboot");

    // -- memory -----------------------------------------------------------------
    public byte[] Read(uint addr, int n)
    {
        var output = new List<byte>(n);
        for (long a = addr; a < addr + (long)n; a += 0x1000)
        {
            Send($"getmem addr=0x{a:X8} length=0x{Math.Min(0x1000, addr + n - a):X}");
            var data = string.Concat(Lines());
            if (data.Contains("??")) throw new XbdmException($"unreadable memory near 0x{a:X8}");
            output.AddRange(Convert.FromHexString(data));
        }
        return [.. output];
    }

    public void Write(uint addr, byte[] data)
    {
        for (int i = 0; i < data.Length; i += 128) // stay under XBDM's line limit
            Send($"setmem addr=0x{addr + i:X8} data={Convert.ToHexString(data, i, Math.Min(128, data.Length - i))}");
    }

    public object Get(uint addr, string kind, int size = 4) => kind switch
    {
        "string" => Codec.Latin1.GetString(Read(addr, size)).Split('\0')[0],
        "bytes" => Convert.ToHexString(Read(addr, size)),
        "i32" => BinaryPrimitives.ReadInt32BigEndian(Read(addr, 4)),
        "u32" => BinaryPrimitives.ReadUInt32BigEndian(Read(addr, 4)),
        "float" => BinaryPrimitives.ReadSingleBigEndian(Read(addr, 4)),
        _ => throw new ArgumentException($"unknown type '{kind}'"),
    };

    public void Put(uint addr, string kind, string value, int? size = null) => Write(addr, Codec.Encode(kind, value, size));

    /// <summary>Every address in [start, end) holding pattern. Unreadable chunks are skipped.</summary>
    public List<uint> Scan(uint start, uint end, byte[] pattern, int chunk = 0x10000,
                           Action<long, long>? progress = null, CancellationToken cancel = default)
    {
        var hits = new List<uint>();
        for (long a = start; a < end; a += chunk)
        {
            cancel.ThrowIfCancellationRequested();
            int n = (int)Math.Min(chunk, end - a);
            byte[] data;
            try { data = Read((uint)a, a + n < end ? n + pattern.Length - 1 : n); } // a little extra for matches across edges
            catch (XbdmException) { continue; }
            for (int i = 0, j; (j = data.AsSpan(i).IndexOf(pattern)) >= 0 && i + j < n; i += j + 1)
                hits.Add((uint)(a + i + j));
            progress?.Invoke(a + n - start, end - start);
        }
        return hits;
    }

    public List<uint> Refine(IEnumerable<uint> hits, byte[] pattern) => hits.Where(a =>
    {
        try { return Read(a, pattern.Length).AsSpan().SequenceEqual(pattern); }
        catch (XbdmException) { return false; }
    }).ToList();

    // -- JRPC2 ------------------------------------------------------------------
    /// <summary>Cheap check before calling an address: does it start like a function?</summary>
    public bool IsFunction(uint addr)
    {
        uint word = BinaryPrimitives.ReadUInt32BigEndian(Read(addr, 4));
        return Prologues.Contains(word) || word >> 16 == 0x9421; // or stwu r1,-x(r1)
    }

    /// <summary>Call a void game function. Clean reimplementation of JRPC2; unverified on hardware.</summary>
    public void Call(uint address, params object[] args)
    {
        var parameters = $"A\\{address:X}\\{args.Length}\\" + string.Concat(args.Select(Codec.JrpcArg));
        string msg;
        try { msg = Send($"consolefeatures ver=2 type=0 system as=0 params=\"{parameters}\"").Message; }
        catch (XbdmException e) when (e.Message.Contains("407") || e.Message.Contains("unknown command", StringComparison.OrdinalIgnoreCase))
        {
            throw new XbdmException("console doesn't understand 'consolefeatures': is the JRPC2 plugin loaded?", e);
        }
        var deadline = DateTime.UtcNow.AddSeconds(5);
        for (Match m; (m = Regex.Match(msg, "buf_addr=(0x[0-9A-Fa-f]+)")).Success;) // still running: poll
        {
            if (DateTime.UtcNow > deadline) throw new XbdmException("timed out waiting for the call to finish");
            Thread.Sleep(50);
            msg = Send($"consolefeatures buf_addr={m.Groups[1].Value}").Message;
        }
        if (msg.Contains("error=")) throw new XbdmException(msg);
    }
}
