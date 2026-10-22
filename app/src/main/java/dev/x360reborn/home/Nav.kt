package dev.x360reborn.home

import kotlin.math.abs

/** Geometric d-pad navigation between template slots, as XUI resolves NavLeft/Right/Up/Down by position. */
object Nav {
    /** Best slot from [from] in direction (dx, dy), or -1 when nothing lies that way. */
    fun move(boxes: List<Box>, ok: (Int) -> Boolean, from: Int, dx: Int, dy: Int): Int {
        val f = boxes[from]
        var best = -1
        var bestScore = Float.MAX_VALUE
        for ((i, b) in boxes.withIndex()) {
            if (i == from || !ok(i)) continue
            val ahead = when {
                dx > 0 -> b.x >= f.right - 1f
                dx < 0 -> b.right <= f.x + 1f
                dy > 0 -> b.y >= f.bottom - 1f
                else -> b.bottom <= f.y + 1f
            }
            if (!ahead) continue
            val along = if (dx != 0) abs(b.cx - f.cx) else abs(b.cy - f.cy)
            // Overlap on the cross axis beats centre distance, so tall/wide slots still line up.
            val cross = if (dx != 0) gap(f.y, f.bottom, b.y, b.bottom, f.cy, b.cy)
            else gap(f.x, f.right, b.x, b.right, f.cx, b.cx)
            // Among overlapping candidates prefer the one aligned with our leading edge (reading order).
            val lead = if (dx != 0) abs(b.y - f.y) else abs(b.x - f.x)
            val score = along + cross * 3f + lead * 0.01f
            if (score < bestScore) { bestScore = score; best = i }
        }
        return best
    }

    private fun gap(a0: Float, a1: Float, b0: Float, b1: Float, ac: Float, bc: Float): Float =
        if (a1 > b0 && b1 > a0) abs(ac - bc) * 0.1f else abs(ac - bc)

    /** Slot to land on when entering a page from its left or right edge at height [y]. */
    fun enter(boxes: List<Box>, ok: (Int) -> Boolean, fromLeft: Boolean, y: Float): Int {
        var best = -1
        var bestScore = Float.MAX_VALUE
        for ((i, b) in boxes.withIndex()) {
            if (!ok(i)) continue
            val edge = if (fromLeft) b.x else -b.right
            val score = edge * 2f + if (y in b.y..b.bottom) 0f else abs(b.cy - y)
            if (score < bestScore) { bestScore = score; best = i }
        }
        return best
    }
}
