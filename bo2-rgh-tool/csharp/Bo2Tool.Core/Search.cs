// Cheat Engine style memory search: an exact value, or an unknown value narrowed down by how it changes.
using System.Buffers.Binary;

namespace Bo2Tool;

/// <summary>Start(value or "?"), then Refine(new value or same/changed/more/less) until one hit is left.</summary>
public sealed class Search(Xbdm xb, string kind)
{
    public const int Chunk = 0x10000;
    public static readonly string[] Ops = ["same", "changed", "more", "less"];

    uint lo;
    int width = 4;
    Dictionary<uint, byte[]> snap = []; // chunk start -> last memory seen there

    public string Kind { get; } = kind;
    public bool IsNumber => Kind is "i32" or "u32" or "float";
    /// <summary>null = every 4-byte aligned address in the remembered memory (unknown-value start).</summary>
    public List<uint>? Hits { get; private set; }
    public long Count => Hits?.Count ?? snap.Values.Sum(d => (long)(d.Length / 4));

    uint Base(uint a) => lo + (a - lo) / Chunk * Chunk;

    byte[] At(Dictionary<uint, byte[]> s, uint a)
    {
        uint b = Base(a);
        var data = s.GetValueOrDefault(b) ?? [];
        int off = (int)(a - b);
        byte[] head = off < data.Length ? data[off..Math.Min(data.Length, off + width)] : [];
        return head.Length == width ? head : [.. head, .. (s.GetValueOrDefault(b + Chunk) ?? []).Take(width - head.Length)]; // crosses a chunk edge
    }

    IEnumerable<uint> Candidates() => Hits ?? snap.SelectMany(kv => Enumerable.Range(0, kv.Value.Length / 4).Select(i => kv.Key + (uint)i * 4));

    double Number(byte[] raw) => Kind switch
    {
        "i32" => BinaryPrimitives.ReadInt32BigEndian(raw),
        "u32" => BinaryPrimitives.ReadUInt32BigEndian(raw),
        _ => BinaryPrimitives.ReadSingleBigEndian(raw),
    };

    /// <summary>The value last seen at a hit, for display.</summary>
    public string Value(uint a)
    {
        var raw = At(snap, a);
        return raw.Length < width ? "?" : IsNumber ? Number(raw).ToString(System.Globalization.CultureInfo.InvariantCulture) : Codec.Printable(raw);
    }

    /// <summary>Remember [start, end) and find value, or keep every address for "?" (number types only).</summary>
    public long Start(string value, uint start, uint end, Action<long, long>? progress = null, CancellationToken cancel = default)
    {
        if (value == "?" && !IsNumber) throw new ArgumentException("an unknown-value search needs a number type (i32/u32/float)");
        lo = start & ~3u;
        snap = [];
        for (long a = lo; a < end; a += Chunk)
        {
            cancel.ThrowIfCancellationRequested();
            try { snap[(uint)a] = xb.Read((uint)a, (int)Math.Min(Chunk, end - a)); }
            catch (XbdmException) { } // unmapped: skip
            progress?.Invoke(Math.Min(a + Chunk, end) - lo, end - lo);
        }
        if (value == "?")
        {
            (Hits, width) = (null, 4);
            return Count;
        }
        var pattern = Codec.Encode(Kind, value);
        (Hits, width) = ([], pattern.Length);
        foreach (var (b, data) in snap)
        {
            byte[] buf = [.. data, .. (snap.GetValueOrDefault(b + Chunk) ?? []).Take(pattern.Length - 1)];
            for (int i = 0, j; (j = buf.AsSpan(i).IndexOf(pattern)) >= 0 && i + j < data.Length; i += j + 1)
                Hits.Add(b + (uint)(i + j));
        }
        Trim();
        return Count;
    }

    /// <summary>Keep hits that now hold answer, or that are the same/changed/more/less than last time.</summary>
    public long Refine(string answer, CancellationToken cancel = default)
    {
        if (answer is "more" or "less" && !IsNumber) throw new ArgumentException("more/less need a number type (i32/u32/float)");
        byte[]? target = Ops.Contains(answer) ? null : Codec.Encode(Kind, answer);
        if (target != null && target.Length != width) throw new ArgumentException($"new value must be {width} bytes long like the first one");
        var now = new Dictionary<uint, byte[]>();
        foreach (var (b, old) in snap) // re-read only chunks that still hold hits
        {
            cancel.ThrowIfCancellationRequested();
            try { now[b] = xb.Read(b, old.Length); }
            catch (XbdmException) { }
        }
        var kept = new List<uint>();
        foreach (var a in Candidates())
        {
            byte[] before = At(snap, a), after = At(now, a);
            if (after.Length < width) continue;
            bool ok = target != null ? after.AsSpan().SequenceEqual(target)
                : answer == "same" ? after.AsSpan().SequenceEqual(before)
                : answer == "changed" ? !after.AsSpan().SequenceEqual(before)
                : answer == "more" ? Number(after) > Number(before) : Number(after) < Number(before);
            if (ok) kept.Add(a);
        }
        (snap, Hits) = (now, kept);
        Trim();
        return Count;
    }

    public void Pick(int index) => Hits = [Hits![index]];

    /// <summary>Forget chunks with no hits left, to keep memory use down.</summary>
    void Trim()
    {
        var keep = Hits!.Select(Base).SelectMany(b => new[] { b, b + Chunk }).ToHashSet();
        snap = snap.Where(kv => keep.Contains(kv.Key)).ToDictionary();
    }
}
