package dev.x360reborn.home

enum class Category { GAME, VIDEO, MUSIC, OTHER }

/** A launchable activity, reduced to what layout needs. [key] is the flattened component. */
data class AppInfo(val key: String, val label: String, val category: Category = Category.OTHER)

sealed interface Target {
    data class App(val key: String) : Target
    data class Action(val name: String) : Target
    data class Channel(val index: Int) : Target
}

enum class Kind { TILE, HERO, WIDE }

data class Tile(
    val label: String,
    val target: Target,
    val kind: Kind = Kind.TILE,
    val sub: String = "",
    /** App whose icon the tile shows, or null for a drawn glyph. */
    val iconKey: String? = (target as? Target.App)?.key,
    val glyph: Glyph = Glyph.NONE,
)

enum class Glyph { NONE, ALL_APPS, SETTINGS, TILE_SIZE }

/** One template instance on the horizon. Tiles line up with [Template.slots]; extra slots stay empty. */
data class Page(val channel: Int, val template: Template, val tiles: List<Tile>)

data class Channel(val title: String, val firstPage: Int, val pageCount: Int)

class Hub(val channels: List<Channel>, val pages: List<Page>, val layout: Layout) {
    fun channelOf(page: Int) = pages[page].channel
}

data class SettingsEntry(val label: String, val action: String, val iconKey: String? = null, val glyph: Glyph = Glyph.SETTINGS)

object HubBuilder {
    /**
     * Mirrors dashhome-offline.xml: home, then the content hubs, then apps and settings.
     * Content hubs with no apps are dropped, as the dash hides channels it has no content for.
     */
    fun build(
        apps: List<AppInfo>,
        recent: List<String>,
        pins: List<String>,
        settings: List<SettingsEntry>,
        layout: Layout = Layout.LANDSCAPE,
    ): Hub {
        val byKey = apps.associateBy { it.key }
        val alpha = apps.sortedBy { it.label.lowercase() }

        val titles = ArrayList<String>()
        val content = ArrayList<List<AppInfo>>()
        fun add(title: String, list: List<AppInfo>) { titles += title; content += list }

        val homeOrder = LinkedHashSet<String>().apply {
            pins.filter { it in byKey }.forEach(::add)
            recent.filter { it in byKey }.forEach(::add)
            alpha.forEach { add(it.key) }
        }.map { byKey.getValue(it) }

        val heroKey = homeOrder.firstOrNull()?.key
        val heroSub = when {
            heroKey == null -> ""
            heroKey in pins -> "pinned"
            heroKey in recent -> "recent"
            else -> ""
        }
        add("home", homeOrder)
        for ((title, cat) in listOf("games" to Category.GAME, "tv & movies" to Category.VIDEO, "music" to Category.MUSIC)) {
            val list = alpha.filter { it.category == cat }
            if (list.isNotEmpty()) add(title, list)
        }
        add("apps", alpha)
        val appsIndex = titles.size - 1
        add("settings", emptyList())
        val settingsIndex = titles.size - 1

        val pages = ArrayList<Page>()
        val channels = ArrayList<Channel>()
        for ((i, title) in titles.withIndex()) {
            val start = pages.size
            when (i) {
                0 -> pages += homePage(layout.home, homeOrder, appsIndex, settingsIndex, heroSub)
                appsIndex -> pages += gridPages(layout.grid, i, alpha.map(::appTile))
                settingsIndex -> pages += gridPages(layout.grid, i, settings.map {
                    Tile(it.label, Target.Action(it.action), iconKey = it.iconKey,
                        glyph = if (it.iconKey == null) it.glyph else Glyph.NONE)
                })
                else -> pages += contentPages(layout, i, content[i])
            }
            channels += Channel(title, start, pages.size - start)
        }
        return Hub(channels, pages, layout)
    }

    private fun appTile(a: AppInfo) = Tile(a.label, Target.App(a.key))

    private fun homePage(t: Template, order: List<AppInfo>, appsIndex: Int, settingsIndex: Int, heroSub: String): Page {
        val tiles = arrayOfNulls<Tile>(t.slots.size)
        val shortcuts = listOf(
            Tile("all apps", Target.Channel(appsIndex), Kind.WIDE, glyph = Glyph.ALL_APPS),
            Tile("settings", Target.Channel(settingsIndex), Kind.WIDE, glyph = Glyph.SETTINGS),
        )
        if (t.compact) {
            // Keep the last cells for the shortcuts, fill apps, then drop the shortcuts into the
            // first free cells: the reserved ones on a full page, right after the last app otherwise.
            fillTemplate(t, tiles, order, heroSub, skip = t.wide.toSet())
            val free = readingOrder(t).filter { tiles[it] == null }
            shortcuts.forEachIndexed { i, s -> free.getOrNull(i)?.let { tiles[it] = s } }
        } else {
            t.wide.getOrNull(0)?.let { tiles[it] = shortcuts[0] }
            t.wide.getOrNull(1)?.let { tiles[it] = shortcuts[1] }
            fillTemplate(t, tiles, order, heroSub)
        }
        return Page(0, t, tiles.toList().filterNotNullPreservingSlots())
    }

    private fun contentPages(layout: Layout, channel: Int, apps: List<AppInfo>): List<Page> {
        val t = layout.home
        val tiles = arrayOfNulls<Tile>(t.slots.size)
        val used = fillTemplate(t, tiles, apps, "")
        val first = Page(channel, t, tiles.toList().filterNotNullPreservingSlots())
        return listOf(first) + gridPages(layout.grid, channel, apps.drop(used).map(::appTile), allowEmpty = false)
    }

    /** Hero slot takes the first app, the remaining open slots take the rest in reading order. */
    private fun readingOrder(t: Template) =
        t.slots.indices.sortedWith(compareBy({ t.slots[it].y }, { t.slots[it].x }))

    private fun fillTemplate(t: Template, tiles: Array<Tile?>, apps: List<AppInfo>, heroSub: String, skip: Set<Int> = emptySet()): Int {
        var n = 0
        if (apps.isNotEmpty() && t.hero >= 0) {
            val a = apps[n++]
            tiles[t.hero] = Tile(a.label, Target.App(a.key), Kind.HERO, sub = heroSub)
        }
        // Reading order, with the reserved cells taken off the end of the page.
        val open = readingOrder(t).filter { tiles[it] == null && it !in skip }
        for (slot in open) {
            if (n >= apps.size) break
            tiles[slot] = appTile(apps[n++])
        }
        return n
    }

    private fun gridPages(t: Template, channel: Int, tiles: List<Tile>, allowEmpty: Boolean = true): List<Page> {
        val per = t.slots.size
        if (tiles.isEmpty()) return if (allowEmpty) listOf(Page(channel, t, emptyList())) else emptyList()
        return tiles.chunked(per).map { Page(channel, t, it) }
    }

    private fun List<Tile?>.filterNotNullPreservingSlots(): List<Tile> =
        map { it ?: EMPTY }

    /** Placeholder for template slots with nothing to show; never focusable. */
    val EMPTY = Tile("", Target.Action(""))
}

fun Page.focusable(slot: Int) = slot in tiles.indices && tiles[slot] !== HubBuilder.EMPTY
