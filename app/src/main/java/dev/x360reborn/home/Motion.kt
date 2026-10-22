package dev.x360reborn.home

import kotlin.math.max
import kotlin.math.min

/**
 * hubscene.xur named-frame transitions applied to the whole Hub (twist + panels), pivoting on the
 * centre. Keys are linear between holds; frames at 60 fps.
 */
enum class Trans(val delayF: Float, val durF: Float, val scaleFrom: Float, val scaleTo: Float, val alphaFrom: Float, val alphaTo: Float) {
    TO(4f, 41f, 0.8f, 1f, 0f, 1f),        // frames 1-46: cold start
    FROM(0f, 28f, 1f, 1.5f, 1f, 0f),      // frames 47-75: leaving for an app
    BACK_TO(8f, 42f, 1.5f, 1f, 0f, 1f);   // frames 76-126: returning from an app

    val totalMs get() = (delayF + durF) * Metrics.FRAME_MS

    /** (scale, alpha) at [ms] since the transition started. */
    fun at(ms: Float): Pair<Float, Float> {
        val t = ((ms / Metrics.FRAME_MS - delayF) / durF).coerceIn(0f, 1f)
        return Pair(scaleFrom + (scaleTo - scaleFrom) * t, alphaFrom + (alphaTo - alphaFrom) * t)
    }
}

/**
 * Tile focus/press curves from the HubSlotContainer timelines. XUI keyframes here are linear
 * (Interpolation=0), so these are piecewise-linear in frame time.
 */
object Motion {
    private val focusMs = Metrics.FOCUS_FRAMES * Metrics.FRAME_MS
    private val pressDownMs = Metrics.PRESS_DOWN_FRAMES * Metrics.FRAME_MS
    private val pressMs = (Metrics.PRESS_DOWN_FRAMES + Metrics.PRESS_UP_FRAMES) * Metrics.FRAME_MS

    /** Focus progress per ms; KillFocus (14 frames) is a little quicker than Focus (16). */
    val focusRate = 1f / focusMs
    val blurRate = 1f / (14f * Metrics.FRAME_MS)
    val pressDuration = pressMs

    fun scale(focus: Float, pressMsElapsed: Float): Float {
        val base = 1f + (Metrics.FOCUS_SCALE - 1f) * focus
        if (pressMsElapsed < 0f || pressMsElapsed >= pressMs) return base
        val dip = if (pressMsElapsed < pressDownMs) pressMsElapsed / pressDownMs
        else 1f - (pressMsElapsed - pressDownMs) / (pressMs - pressDownMs)
        return base - (base - 1f) * dip
    }

    /** White flash: peaks at 0.08 seven frames into the focus ramp, gone by its end. */
    fun flash(focus: Float, rising: Boolean): Float {
        if (!rising || focus <= 0f || focus >= 1f) return 0f
        val p = Metrics.FLASH_PEAK_AT
        return Metrics.FLASH_PEAK * if (focus < p) focus / p else (1f - focus) / (1f - p)
    }

    fun pressFlash(pressMsElapsed: Float): Float {
        if (pressMsElapsed < 0f || pressMsElapsed >= pressMs) return 0f
        val t = pressMsElapsed / pressDownMs
        return Metrics.FLASH_PEAK * if (t < 1f) t else max(0f, 1f - (pressMsElapsed - pressDownMs) / (pressMs - pressDownMs))
    }

    /** Ease-out used for horizon and twist scrolling (not measured; the HorizonControl is native). */
    fun easeOut(t: Float): Float {
        val c = min(1f, max(0f, t))
        val inv = 1f - c
        return 1f - inv * inv * inv
    }

    /** Twist selected-glow loop: 0 -> 0.9 -> 0 once, then 0 -> 0.7 -> 0 every 180 frames. */
    fun twistGlow(ms: Float): Float {
        val f = ms / Metrics.FRAME_MS
        return when {
            f < 13f -> 0.9f * f / 13f
            f < 64f -> 0.9f * (1f - (f - 13f) / 51f)
            f < 83f -> 0f
            else -> {
                val l = (f - 83f) % 179f
                if (l < 89f) 0.7f * l / 89f else 0.7f * (1f - (l - 89f) / 90f)
            }
        }
    }
}
