"""Read-only STFS (CON/LIVE/PIRS) extractor.

Usage: python -I stfs.py <package> <outdir> [--list]
"""
import os
import struct
import sys

BLOCK = 0x1000


def i24le(b, o):
    return b[o] | b[o + 1] << 8 | b[o + 2] << 16


def i24be(b, o):
    return b[o] << 16 | b[o + 1] << 8 | b[o + 2]


class Stfs:
    def __init__(self, data):
        self.d = data
        self.magic = data[:4]
        self.header_size = struct.unpack_from(">I", data, 0x340)[0]
        vd = 0x379
        self.block_sep = data[vd + 2]
        self.ft_blocks = struct.unpack_from("<H", data, vd + 3)[0]
        self.ft_start = i24le(data, vd + 5)
        self.data_start = (self.header_size + 0xFFF) & ~0xFFF
        # read-only LIVE/PIRS packages keep one hash-table copy; only CON doubles them
        self.shift = 0
        if self.magic == b"CON ":
            self.shift = 0 if self.block_sep & 1 else 1

    def fix(self, n):
        sh = self.shift
        r = n + (((n + 0xAA) // 0xAA) << sh)
        if n >= 0xAA:
            r += ((n + 0x70E4) // 0x70E4) << sh
            if n >= 0x70E4:
                r += 1 << sh
        return r

    def block(self, n):
        o = self.data_start + self.fix(n) * BLOCK
        return self.d[o:o + BLOCK]

    def hash_entry(self, n):
        spacing = (0xAB, 0x718F) if self.shift == 0 else (0xAC, 0x723A)
        rec = n % 0xAA
        t = (n // 0xAA) * spacing[0]
        if n >= 0xAA:
            t += ((n // 0x70E4) + 1) << self.shift
            if n >= 0x70E4:
                t += 1 << self.shift
        o = self.data_start + t * BLOCK + rec * 0x18
        return self.d[o:o + 0x18]

    def chain(self, first, count, consecutive):
        n = first
        for _ in range(count):
            yield n
            n = n + 1 if consecutive else i24be(self.hash_entry(n), 0x15)

    def entries(self):
        raw = b"".join(self.block(b) for b in self.chain(self.ft_start, self.ft_blocks, False))
        out = []
        for i in range(len(raw) // 0x40):
            e = raw[i * 0x40:(i + 1) * 0x40]
            flags = e[0x28]
            nl = flags & 0x3F
            if nl == 0:
                break
            out.append({
                "name": e[:nl].decode("latin-1"),
                "dir": bool(flags & 0x80),
                "consecutive": bool(flags & 0x40),
                "blocks": i24le(e, 0x29),
                "first": i24le(e, 0x2F),
                "parent": struct.unpack_from(">h", e, 0x32)[0],
                "size": struct.unpack_from(">I", e, 0x34)[0],
            })
        return out

    def path(self, ents, i):
        parts = []
        while i != -1:
            if len(parts) > 64:
                raise ValueError("directory cycle")
            parts.append(ents[i]["name"])
            i = ents[i]["parent"]
        return "/".join(reversed(parts))

    def read(self, e):
        buf = b"".join(self.block(b) for b in self.chain(e["first"], e["blocks"], e["consecutive"]))
        return buf[:e["size"]]


def main():
    src, outdir = sys.argv[1], sys.argv[2]
    s = Stfs(open(src, "rb").read())
    ents = s.entries()
    for i, e in enumerate(ents):
        p = s.path(ents, i)
        if "--list" in sys.argv:
            print(f"{'d' if e['dir'] else ' '} {e['size']:10d}  {p}")
            continue
        if ".." in p.split("/"):
            raise ValueError(f"bad path {p}")
        dst = os.path.join(outdir, p)
        if e["dir"]:
            os.makedirs(dst, exist_ok=True)
        else:
            os.makedirs(os.path.dirname(dst) or outdir, exist_ok=True)
            open(dst, "wb").write(s.read(e))


if __name__ == "__main__":
    main()
