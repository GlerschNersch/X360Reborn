"""XEX2 parser: decrypt + decompress the PE image and dump embedded resources.

Usage: python -I xex2.py <file.xex> <outdir> [--info]
"""
import hashlib
import os
import struct
import sys

from Crypto.Cipher import AES

# The retail XEX key is Microsoft's and is not distributed with this repo. Encrypted modules
# only decrypt when XEX_RETAIL_KEY (32 hex chars) is set; unencrypted ones never need it.
RETAIL_KEY = bytes.fromhex(os.environ["XEX_RETAIL_KEY"]) if os.environ.get("XEX_RETAIL_KEY") else None
DEVKIT_KEY = bytes(16)

H_RESOURCE_INFO = 0x000002FF
H_FILE_FORMAT = 0x000003FF
H_ORIG_PE_NAME = 0x000183FF
H_EXEC_ID = 0x00040006


def u32(b, o):
    return struct.unpack_from(">I", b, o)[0]


def u16(b, o):
    return struct.unpack_from(">H", b, o)[0]


class Xex:
    def __init__(self, data):
        if data[:4] != b"XEX2":
            raise ValueError("not XEX2")
        self.data = data
        self.module_flags = u32(data, 4)
        self.pe_offset = u32(data, 8)
        self.sec_offset = u32(data, 0x10)
        count = u32(data, 0x14)
        self.headers = {}
        for i in range(count):
            k, v = u32(data, 0x18 + i * 8), u32(data, 0x1C + i * 8)
            self.headers[k] = v
        sec = self.sec_offset
        self.image_size = u32(data, sec + 4)
        self.load_address = u32(data, sec + 0x110)
        self.file_key = data[sec + 0x150:sec + 0x160]

    def header_blob(self, key):
        off = self.headers.get(key)
        if off is None:
            return None
        size = key & 0xFF
        if size == 0xFF:
            return self.data[off + 4:off + u32(self.data, off)]
        if size <= 1:
            return off
        return self.data[off:off + size * 4]

    def orig_name(self):
        b = self.header_blob(H_ORIG_PE_NAME)
        return b.split(b"\0")[0].decode("ascii", "replace") if b else None

    def file_format(self):
        b = self.header_blob(H_FILE_FORMAT)
        enc, comp = u16(b, 0), u16(b, 2)
        return enc, comp, b[4:]

    def resources(self):
        b = self.header_blob(H_RESOURCE_INFO)
        out = []
        if not b:
            return out
        for i in range(len(b) // 16):
            e = b[i * 16:(i + 1) * 16]
            out.append((e[:8].split(b"\0")[0].decode("ascii", "replace"), u32(e, 8), u32(e, 12)))
        return out

    def session_key(self, master):
        return AES.new(master, AES.MODE_ECB).decrypt(self.file_key)

    def payload(self):
        return self.data[self.pe_offset:]

    def image(self):
        enc, comp, extra = self.file_format()
        raw = self.payload()
        for master in (k for k in (RETAIL_KEY, DEVKIT_KEY) if k is not None):
            if enc:
                key = self.session_key(master)
                body = AES.new(key, AES.MODE_CBC, bytes(16)).decrypt(raw[: len(raw) // 16 * 16])
            else:
                body = raw
            try:
                img = self._decompress(comp, extra, body)
            except Exception:
                if not enc:
                    raise
                continue
            # Unencrypted resource-only modules (huduiskin, XimeDic) carry no PE header.
            if img[:2] == b"MZ" or not enc:
                return img
        raise ValueError("could not decrypt image (unknown key?)")

    def _decompress(self, comp, extra, body):
        if comp == 0:
            return body
        if comp == 1:  # basic: (data_size, zero_size) pairs
            out = bytearray()
            pos = 0
            for i in range(len(extra) // 8):
                ds, zs = u32(extra, i * 8), u32(extra, i * 8 + 4)
                out += body[pos:pos + ds]
                out += bytes(zs)
                pos += ds
            return bytes(out)
        if comp == 2:  # normal: hashed blocks of LZX chunks
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # -I drops the script dir
            from lzx import LzxDecoder

            window = u32(extra, 0)
            block_size = u32(extra, 4)
            block_hash = extra[8:28]
            pos = 0
            stream = bytearray()
            while block_size:
                block = body[pos:pos + block_size]
                if hashlib.sha1(block).digest() != block_hash:
                    raise ValueError("block hash mismatch")
                next_size = u32(block, 0)
                next_hash = block[4:24]
                p = 24
                while p + 2 <= len(block):
                    clen = u16(block, p)
                    p += 2
                    if clen == 0:
                        break
                    stream += block[p:p + clen]
                    p += clen
                pos += block_size
                block_size, block_hash = next_size, next_hash
            return LzxDecoder(window).decompress_chunks(bytes(stream), self.image_size)
        raise ValueError(f"unknown compression {comp}")


def main():
    path, outdir = sys.argv[1], sys.argv[2]
    x = Xex(open(path, "rb").read())
    enc, comp, _ = x.file_format()
    print(f"{os.path.basename(path)}: name={x.orig_name()} load=0x{x.load_address:08X} "
          f"img=0x{x.image_size:X} enc={enc} comp={comp} flags=0x{x.module_flags:X}")
    res = x.resources()
    for n, a, s in res:
        print(f"  res {n:8s} @0x{a:08X} size=0x{s:X}")
    if "--info" in sys.argv:
        return
    img = x.image()
    os.makedirs(outdir, exist_ok=True)
    base = os.path.splitext(os.path.basename(path))[0]
    open(os.path.join(outdir, base + ".pe"), "wb").write(img)
    for n, a, s in res:
        off = a - x.load_address
        open(os.path.join(outdir, f"{base}.{n}.bin"), "wb").write(img[off:off + s])


if __name__ == "__main__":
    main()
