"""XUIZ (.xzp) archive unpacker.

Layout (big-endian): 'XUIZ' u32 version u32 data_size u32 0 u32 toc_size u16 count,
then count x { u32 size, u32 offset (from data base), u8 name_len, ascii name }.
Data base = 0x16 + toc_size.

Usage: python -I xzp.py <archive> <outdir> [--list]
"""
import os
import struct
import sys


def entries(data):
    if data[:4] != b"XUIZ":
        raise ValueError("not XUIZ")
    toc_size = struct.unpack_from(">I", data, 0x10)[0]
    count = struct.unpack_from(">H", data, 0x14)[0]
    base = 0x16 + toc_size
    p = 0x16
    out = []
    for _ in range(count):
        size, off = struct.unpack_from(">II", data, p)
        n = data[p + 8]
        name = data[p + 9:p + 9 + n].decode("ascii")
        p += 9 + n
        out.append((name, base + off, size))
    return out


def main():
    src, outdir = sys.argv[1], sys.argv[2]
    data = open(src, "rb").read()
    for name, off, size in entries(data):
        if "--list" in sys.argv:
            print(f"{size:9d}  {name}")
            continue
        # controlp archives reference siblings via "..\"; keep them inside outdir
        rel = name.replace("\\", "/").replace("../", "_parent/")
        dst = os.path.normpath(os.path.join(outdir, rel))
        if not dst.startswith(os.path.normpath(outdir)):
            raise ValueError(f"path escapes outdir: {name}")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, "wb").write(data[off:off + size])


if __name__ == "__main__":
    main()
