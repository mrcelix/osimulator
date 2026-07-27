# tools — source-extracted settings trees

These scripts build parts of `index.html` **from the operating system's own
source code** instead of from hand-written notes, so the menu structure in the
simulator is verifiably the structure the OS ships.

## Android (AOSP)

```sh
git clone --depth 1 --filter=blob:none --sparse \
    -b android-14.0.0_r75 \
    https://github.com/aosp-mirror/platform_packages_apps_Settings /tmp/a14
git -C /tmp/a14 sparse-checkout set res/xml res/values src

python3 tools/aosp-extract.py /tmp/a14 /tmp/android14.json   # source -> JSON tree
python3 tools/aosp-to-dsl.py                                  # JSON -> ANDROID_TREE js
```

Repeat with `-b android-13.0.0_r83` into `/tmp/a13` → `/tmp/android13.json`.
`aosp-to-dsl.py` reads both and writes `/tmp/android_tree.js`, which is pasted
into `index.html` just above the `ANDROID SETTINGS` banner.

### What the extractor does

`res/xml/*.xml` holds the preference trees; `res/values/strings.xml` and
`arrays.xml` hold the labels. A row that drills into another screen carries an
`android:fragment` class name rather than an XML reference, so the extractor
parses the Java sources for `getPreferenceScreenResId`,
`BaseSearchIndexProvider(R.xml.X)` and `addPreferencesFromResource` to map each
fragment class back to its backing XML, then keeps walking. The result is the
full nested tree, labels and summary lines verbatim.

A few deliberate departures from a naive dump, each grounded in the same source:

- `LayoutPreference` / `ProgressPreference` / `JumpPreference` are runtime
  status banners a controller injects ("Airplane mode is on"), not menu rows —
  dropped.
- `FooterPreference` becomes an on-screen note rather than a tappable row.
- AOSP ships every conditional variant of a row side by side and picks one at
  run time; `dedupe()` keeps the richest variant so a screen doesn't show
  "Security" twice.
- Strings carry `product=` variants (`About phone` / `About tablet` /
  `About emulated device`). The handset (`product="default"`) form wins.
- `Communal` is dropped: its own controller reads
  `R.bool.config_show_communal_settings`, which `res/values/config.xml`
  declares `false`, so a shipping handset never shows it.

### What is *not* from source

Menu **structure** comes from source. Device **state** cannot — the serial
number, build number, IP address, battery percentage and the on/off position of
a switch are read from real hardware at run time. Those live in two clearly
marked tables in `aosp-to-dsl.py` (`VALUES` and `ON_BY_DEFAULT`) and are
illustrative values for the simulator's Pixel 8 Pro persona. They never change
which rows exist or what they are called.

Screens that live in a different APK than Settings (the wallpaper picker,
Safety Center, the vendor support app) have a real menu entry here but no page
behind it; rather than invent one, the entry says where its content comes from.
