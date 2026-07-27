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

## Ubuntu (GNOME Control Center)

```sh
# the panels themselves
git clone --depth 1 --filter=blob:none --sparse -b 46.4 \
    https://github.com/GNOME/gnome-control-center /tmp/gcc46
git -C /tmp/gcc46 sparse-checkout set panels shell po

# the keyboard shortcut defaults live in two other projects
git clone --depth 1 --filter=blob:none --sparse -b 46.0 \
    https://github.com/GNOME/gnome-settings-daemon /tmp/gsd46
git -C /tmp/gsd46 sparse-checkout set data plugins/media-keys
git clone --depth 1 --filter=blob:none --sparse -b 46.0 \
    https://github.com/GNOME/gsettings-desktop-schemas /tmp/gds46
git -C /tmp/gds46 sparse-checkout set schemas

python3 tools/gnome-extract.py /tmp/gcc46 /tmp/gnome46.json /tmp/gsd46 /tmp/gds46
python3 tools/gnome-to-dsl.py                       # JSON -> UBUNTU_TREE js
```

Repeat with tags `42.4` (gnome-control-center), `42.1` (gnome-settings-daemon)
and `42.0` (gsettings-desktop-schemas) into `/tmp/gcc42`, `/tmp/gsd42`,
`/tmp/gds42` → `/tmp/gnome42.json`. `gnome-to-dsl.py` reads both and writes
`/tmp/ubuntu_tree.js`, which is pasted into `index.html` just above the
`Ubuntu (GNOME)` banner. GNOME 46 is what Ubuntu 24.04 LTS ships and GNOME 42
is what 22.04 LTS ships, so `osSidebar()` picks the tree from the version.

Note that gitlab.gnome.org is the upstream home; the `GNOME/*` repositories on
GitHub are the official mirrors and are what these commands use.

### What the extractor does

GNOME builds its panels from GtkBuilder `.ui` files, so the tree is read
straight out of the XML: an `AdwPreferencesPage` is a screen, an
`AdwPreferencesGroup` is a boxed section (its `title` becomes the heading and
its `description` the small print underneath), and the rows are the row widget
classes — `AdwSwitchRow`, `AdwComboRow`, `AdwActionRow`, `AdwEntryRow`,
`AdwSpinRow`, `AdwExpanderRow`, `AdwButtonRow`, `CcListRow`, `CcSplitRow`,
`CcIllustratedRow`. Combo option lists come from the `GtkStringList` the row
points at, so the choices on a sub-screen are also the shipped strings.

Following a row into the next screen differs between the two generations, and
both are handled: GNOME 46 rows carry `action-name="navigation.push"` with an
`action-target` naming the destination page's `tag`, while GNOME 42 marks a
drill-in with a `go-next` `GtkImage` and the destination is a `GtkDialog`
template. Both generations extract with zero unresolved drill-in rows.

Three things come from C rather than XML, because that is where GNOME keeps
them:

- Which panels exist is `shell/cc-panel-loader.c`.
- The sidebar order, and where the dividers fall, is the `panel_order[]` array
  in `shell/cc-panel-list.c` — not the loader's registration list, which is in
  a different order. `panel_order[]` interleaves the literal string
  `"separator"`, which is how GNOME 46 gets its five sidebar blocks; GNOME 42
  has no separators at all, which is why its sidebar is one flat list here.
- `CcToggleRow` and `CcListRow show-switch=True` are switch rows even though
  their switch lives in a separate template
  (`cc_toggle_row_set_allowed()` calls `gtk_switch_set_active()`), so they are
  classified as switches rather than plain rows.

The Keyboard Shortcuts screen is generated from `panels/keyboard/*.xml.in`,
which names a GSettings schema and key per shortcut but not the accelerator.
The accelerator is that key's default value, which ships in
gnome-settings-daemon and gsettings-desktop-schemas — hence the two extra
checkouts. The media keys carry two definitions of every binding: the modern
list-typed key in `org.gnome.settings-daemon.plugins.media-keys`, which is
often empty, and the single-string key in the `.deprecated` companion schema,
which still holds the bare hardware keysyms (`XF86AudioRaiseVolume` and
friends) that gnome-settings-daemon binds statically
(`plugins/media-keys/shortcuts-list.h`, `static_setting = TRUE`). The extractor
takes the modern value and falls back to the deprecated one when it is empty,
which is what the panel ends up showing. Four shortcuts resolve to nothing in
either schema; those genuinely ship unbound and show as `Disabled`.

### What is *not* from source

Same boundary as Android. Structure is source-derived; device state is not, and
lives in clearly marked tables in `gnome-to-dsl.py`: `VALUES` and
`PANEL_VALUES` supply the text on the right of a row, `ON_BY_DEFAULT` the
position of a switch, and `RUNTIME` and `PANEL_EXTRA` the contents of lists a
real machine fills from hardware and online accounts at run time (visible
Wi-Fi networks, paired Bluetooth devices, printers, installed apps). None of
them can add, rename or remove a row. The persona is Ubuntu on a ThinkPad X1
Carbon Gen 11.

One departure worth naming: this is **upstream GNOME**, not Ubuntu's patched
build. Ubuntu carries downstream panels — the "Ubuntu Desktop" appearance panel
in particular — that do not exist in the GNOME source tree, so they are absent
here. Extracting those would mean a checkout of Ubuntu's packaging branch
rather than the GNOME tag, which is a separate job.
