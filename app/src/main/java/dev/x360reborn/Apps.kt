package dev.x360reborn

import android.content.ComponentName
import android.content.Context
import android.content.pm.ApplicationInfo
import android.content.pm.LauncherActivityInfo
import android.content.pm.LauncherApps
import android.graphics.Bitmap
import android.graphics.Canvas
import android.os.Process
import android.provider.Settings
import dev.x360reborn.home.AppInfo
import dev.x360reborn.home.Category
import dev.x360reborn.home.Glyph
import dev.x360reborn.home.TileSize
import dev.x360reborn.home.SettingsEntry
import java.util.concurrent.ConcurrentHashMap

/** Installed apps, their icons, and the launcher's own recents/pins (kept in prefs, no usage-stats permission). */
class Apps(private val context: Context) {
    private val launcherApps = context.getSystemService(LauncherApps::class.java)
    private val prefs = context.getSharedPreferences("hub", Context.MODE_PRIVATE)
    private val icons = ConcurrentHashMap<String, Bitmap>()
    @Volatile private var activities: Map<String, LauncherActivityInfo> = emptyMap()

    fun load(): List<AppInfo> {
        val list = launcherApps.getActivityList(null, Process.myUserHandle())
            .filter { it.componentName.packageName != context.packageName }
        activities = list.associateBy { it.componentName.flattenToShortString() }
        icons.keys.retainAll(activities.keys)
        return activities.map { (key, info) -> AppInfo(key, info.label.toString(), category(info.applicationInfo)) }
    }

    /** Renders missing icons, [first] keys before the rest; calls [progress] every few icons. */
    fun loadIcons(first: List<String>, progress: () -> Unit) {
        val iconPx = (context.resources.displayMetrics.density * 64).toInt().coerceAtLeast(96)
        val order = LinkedHashSet(first).apply { addAll(activities.keys) }
        var n = 0
        for (key in order) {
            val info = activities[key] ?: continue
            if (icons.containsKey(key)) continue
            icons[key] = render(info, iconPx)
            if (++n % 8 == 0) progress()
        }
        progress()
    }

    private fun category(ai: ApplicationInfo) = when {
        ai.category == ApplicationInfo.CATEGORY_GAME || ai.flags and ApplicationInfo.FLAG_IS_GAME != 0 -> Category.GAME
        ai.category == ApplicationInfo.CATEGORY_VIDEO -> Category.VIDEO
        ai.category == ApplicationInfo.CATEGORY_AUDIO -> Category.MUSIC
        else -> Category.OTHER
    }

    private fun render(info: LauncherActivityInfo, px: Int): Bitmap {
        val d = info.getIcon(0)
        val bmp = Bitmap.createBitmap(px, px, Bitmap.Config.ARGB_8888)
        d.setBounds(0, 0, px, px)
        d.draw(Canvas(bmp))
        return bmp
    }

    fun icon(key: String): Bitmap? = icons[key]

    fun component(key: String): ComponentName? = activities[key]?.componentName

    fun recent(): List<String> = prefs.all.entries
        .filter { it.key.startsWith(RECENT) }
        .sortedByDescending { it.value as? Long ?: 0L }
        .map { it.key.removePrefix(RECENT) }

    fun pins(): List<String> = prefs.getString(PINS, "")!!.split('\n').filter { it.isNotEmpty() }

    fun markLaunched(key: String) = prefs.edit().putLong(RECENT + key, System.currentTimeMillis()).apply()

    fun togglePin(key: String) {
        val now = pins().toMutableList()
        if (!now.remove(key)) now.add(0, key)
        prefs.edit().putString(PINS, now.joinToString("\n")).apply()
    }

    fun forget(key: String) = prefs.edit().remove(RECENT + key).apply()

    var tileSize: TileSize
        get() = TileSize.entries.firstOrNull { it.name == prefs.getString(TILE_SIZE, null) } ?: TileSize.LARGE
        set(v) = prefs.edit().putString(TILE_SIZE, v.name).apply()

    fun settingsEntries(): List<SettingsEntry> {
        val settingsApp = activities.keys.firstOrNull { it.startsWith("com.android.settings/") }
        return listOf(
            SettingsEntry("tile size: ${tileSize.label}", ACTION_TILE_SIZE, glyph = Glyph.TILE_SIZE),
            SettingsEntry("system settings", Settings.ACTION_SETTINGS, settingsApp),
            SettingsEntry("wi-fi", Settings.ACTION_WIFI_SETTINGS),
            SettingsEntry("bluetooth", Settings.ACTION_BLUETOOTH_SETTINGS),
            SettingsEntry("display", Settings.ACTION_DISPLAY_SETTINGS),
            SettingsEntry("sound", Settings.ACTION_SOUND_SETTINGS),
            SettingsEntry("battery", "android.intent.action.POWER_USAGE_SUMMARY"),
            SettingsEntry("storage", Settings.ACTION_INTERNAL_STORAGE_SETTINGS),
            SettingsEntry("apps", Settings.ACTION_APPLICATION_SETTINGS),
            SettingsEntry("home app", Settings.ACTION_HOME_SETTINGS),
            SettingsEntry("about", Settings.ACTION_DEVICE_INFO_SETTINGS),
        )
    }

    companion object {
        /** Launcher-internal action: cycle the tile size. */
        const val ACTION_TILE_SIZE = "dev.x360reborn.TILE_SIZE"
        private const val RECENT = "recent:"
        private const val PINS = "pins"
        private const val TILE_SIZE = "tileSize"
    }
}
