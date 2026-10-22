"""LZX decoder (the CAB/XEX variant: 32 KiB frames, 24-bit block sizes, optional E8 translation).

Pure Python, written from the format description; fast enough for the few MB of flash modules.
"""

FRAME = 32768

EXTRA_BITS = []
POSITION_BASE = []
_j = 0
for _i in range(0, 52, 2):
    EXTRA_BITS += [_j, _j]
    if _i != 0 and _j < 17:
        _j += 1
_b = 0
for _e in EXTRA_BITS:
    POSITION_BASE.append(_b)
    _b += 1 << _e

POSITION_SLOTS = {15: 30, 16: 32, 17: 34, 18: 36, 19: 38, 20: 42, 21: 50}


class LzxError(ValueError):
    pass


class _Bits:
    """16-bit little-endian words, consumed most-significant bit first."""

    def __init__(self, data):
        self.d = data
        self.p = 0
        self.buf = 0
        self.n = 0

    def ensure(self, k):
        while self.n < k:
            d, p = self.d, self.p
            w = (d[p] | d[p + 1] << 8) if p + 1 < len(d) else 0
            self.p = p + 2
            self.buf = (self.buf << 16) | w
            self.n += 16

    def peek(self, k):
        self.ensure(k)
        return (self.buf >> (self.n - k)) & ((1 << k) - 1)

    def remove(self, k):
        self.n -= k
        self.buf &= (1 << self.n) - 1

    def read(self, k):
        if k == 0:
            return 0
        v = self.peek(k)
        self.remove(k)
        return v

    def align16(self):
        if self.n > 0:
            self.ensure(16)
        if self.n & 15:
            self.remove(self.n & 15)


class _Huff:
    TABLE_BITS = 16

    def __init__(self, lengths):
        self.lengths = lengths
        tb = self.TABLE_BITS
        table = [-1] * (1 << tb)
        code = 0
        for length in range(1, tb + 1):
            for sym, l in enumerate(lengths):
                if l != length:
                    continue
                span = 1 << (tb - length)
                start = code << (tb - length)
                if start + span > len(table):
                    raise LzxError("over-subscribed Huffman table")
                table[start:start + span] = [sym] * span
                code += 1
            code <<= 1
        self.table = table
        self.empty = not any(lengths)

    def decode(self, bits):
        sym = self.table[bits.peek(self.TABLE_BITS)]
        if sym < 0:
            raise LzxError("bad Huffman code")
        bits.remove(self.lengths[sym])
        return sym


class LzxDecoder:
    def __init__(self, window_size):
        wbits = window_size.bit_length() - 1
        if (1 << wbits) != window_size or wbits not in POSITION_SLOTS:
            raise LzxError(f"unsupported window {window_size:#x}")
        self.main_elements = 256 + POSITION_SLOTS[wbits] * 8
        self.window = window_size

    def _read_lengths(self, bits, lens, first, last):
        pre = _Huff([bits.read(4) for _ in range(20)])
        x = first
        while x < last:
            z = pre.decode(bits)
            # Runs are clamped to the range so they never spill into the next table's lengths.
            if z == 17:
                run = min(4 + bits.read(4), last - x)
                lens[x:x + run] = [0] * run
                x += run
            elif z == 18:
                run = min(20 + bits.read(5), last - x)
                lens[x:x + run] = [0] * run
                x += run
            elif z == 19:
                run = min(4 + bits.read(1), last - x)
                z = pre.decode(bits)
                v = (lens[x] - z + 17) % 17
                lens[x:x + run] = [v] * run
                x += run
            else:
                lens[x] = (lens[x] - z + 17) % 17
                x += 1

    def decompress_chunks(self, data, out_size):
        bits = _Bits(data)
        out = bytearray()
        main_lens = [0] * self.main_elements
        len_lens = [0] * 249
        r0 = r1 = r2 = 1
        intel = bits.read(1)
        intel_size = (bits.read(16) << 16 | bits.read(16)) if intel else 0

        block_type = 0
        block_remaining = 0
        block_length = 0
        main = length = aligned = None
        frame_no = 0
        while len(out) < out_size:
            frame_end = min((frame_no + 1) * FRAME, out_size)
            while len(out) < frame_end:
                if block_remaining == 0:
                    if block_type == 3 and block_length & 1:
                        bits.p += 1  # uncompressed blocks are padded to an even length
                    block_type = bits.read(3)
                    block_remaining = block_length = bits.read(16) << 8 | bits.read(8)
                    if block_type == 2:
                        aligned = _Huff([bits.read(3) for _ in range(8)])
                    if block_type in (1, 2):
                        self._read_lengths(bits, main_lens, 0, 256)
                        self._read_lengths(bits, main_lens, 256, self.main_elements)
                        main = _Huff(main_lens)
                        self._read_lengths(bits, len_lens, 0, 249)
                        length = _Huff(len_lens)
                    elif block_type == 3:
                        bits.ensure(16)
                        if bits.n > 16:
                            bits.p -= 2
                        bits.buf = bits.n = 0
                        d, p = bits.d, bits.p
                        r0, r1, r2 = (int.from_bytes(d[p + i:p + i + 4], "little") for i in (0, 4, 8))
                        bits.p += 12
                    else:
                        raise LzxError(f"bad block type {block_type} at out {len(out):#x}")

                run = min(block_remaining, frame_end - len(out))
                start = len(out)
                if block_type == 3:
                    p = bits.p
                    out += bits.d[p:p + run]
                    bits.p += run
                else:
                    target = start + run
                    while len(out) < target:
                        m = main.decode(bits)
                        if m < 256:
                            out.append(m)
                            continue
                        m -= 256
                        ml = m & 7
                        if ml == 7:
                            ml += length.decode(bits)
                        ml += 2
                        slot = m >> 3
                        if slot == 0:
                            off = r0
                        elif slot == 1:
                            off = r1
                            r1 = r0
                            r0 = off
                        elif slot == 2:
                            off = r2
                            r2 = r0
                            r0 = off
                        else:
                            extra = EXTRA_BITS[slot]
                            off = POSITION_BASE[slot] - 2
                            if block_type == 2 and extra >= 3:
                                off += (bits.read(extra - 3) << 3) + aligned.decode(bits)
                            else:
                                off += bits.read(extra)
                            r2, r1, r0 = r1, r0, off
                        src = len(out) - off
                        if src < 0:
                            raise LzxError(f"match before start (off {off}) at {len(out):#x}")
                        if off >= ml:
                            out += out[src:src + ml]
                        else:
                            for i in range(ml):
                                out.append(out[src + i])
                produced = len(out) - start
                if produced > block_remaining:
                    raise LzxError("match ran past the end of its block")
                block_remaining -= produced
            bits.align16()
            frame_no += 1

        del out[out_size:]
        if intel:
            self._e8(out, intel_size)
        return bytes(out)

    @staticmethod
    def _e8(out, file_size):
        for f in range(0, len(out), FRAME):
            end = min(f + FRAME, len(out))
            if end - f <= 10:
                continue
            i = f
            while i < end - 10:
                if out[i] != 0xE8:
                    i += 1
                    continue
                cur = i
                v = int.from_bytes(out[i + 1:i + 5], "little", signed=True)
                if -cur <= v < file_size:
                    v = v - cur if v >= 0 else v + file_size
                    out[i + 1:i + 5] = (v & 0xFFFFFFFF).to_bytes(4, "little")
                i += 5
