# X360 Reborn

An Android home-screen launcher in the style of the Xbox 360 "Metro" dashboard (2.0.17559).

It is a clean-room rebuild. Layout sizes, colours and animation timings were measured from the
dashboard's own UI scenes (see [docs/RE_NOTES.md](docs/RE_NOTES.md)), but no Microsoft code, images,
sounds or fonts are included. All graphics are drawn in code.

## Features

- Pivot strip ("home / games / tv & movies / music / apps / settings") over swipeable channel pages
- Home grid from the dashboard's Template1HD layout, with a hero tile for your pinned or most recent app
- Green live tiles with the dashboard's focus animation (1.08x scale, flash, corner sheen, shadow)
- Phone portrait layout, plus three tile sizes (pinch, or the "tile size" tile in settings)
- D-pad / gamepad support (L1/R1 switch channels, A launch, B home, X options)
- Long-press a tile to pin it, remove it from recents, open app info or uninstall

## Build

Needs the Android SDK and JDK 17.

```
./gradlew :app:assembleDebug
adb install -r app/build/outputs/apk/debug/app-debug.apk
```

Then pick X360 Reborn under Settings → Apps → Default apps → Home app.

## Reverse-engineering tools

`re/tools` holds the Python scripts used to read the update package (XEX2, XUIZ archives, STFS packages,
XUI scene trees). They operate on files you supply yourself; no firmware is distributed here.
