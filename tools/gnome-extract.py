#!/usr/bin/env python3
"""Extract the real GNOME Settings menu tree from gnome-control-center source.

GNOME Settings is built from GtkBuilder .ui files: an AdwPreferencesPage holds
AdwPreferencesGroups (the boxed sections you see on screen), each holding rows
(AdwSwitchRow, AdwComboRow, CcListRow, ...). Every user-visible string is a
translatable <property> in those files, so the whole menu can be read straight
out of the source with no guessing.

usage: gnome_extract.py <checkout> <out.json> [gsettings-schema-dir ...]

The optional trailing directories are checkouts of gnome-settings-daemon and
gsettings-desktop-schemas.  When given, the default key binding printed next to
every row on the Keyboard Shortcuts screen is resolved from the GSettings
schemas those projects ship, instead of being left blank.
"""
import os, re, sys, json, glob
import xml.etree.ElementTree as ET

ROOT = sys.argv[1]
OUT = sys.argv[2]
SCHEMA_DIRS = sys.argv[3:]

# ---------------------------------------------------------------- text helpers
def clean(t):
    if t is None:
        return None
    t = t.replace('&amp;', '&')
    # Pango markup in labels: <a href='…'>Privacy Policy</a> -> Privacy Policy
    t = re.sub(r'</?(?:a|b|i|u|span|small|big|tt)\b[^>]*>', '', t)
    # GtkBuilder mnemonics: "_Region & Language" -> "Region & Language"
    t = re.sub(r'_(?=\w)', '', t)
    t = re.sub(r'%[0-9]?\$?[sdu]', '…', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t or None

def props(el):
    """direct <property> children of a GtkBuilder object"""
    out = {}
    for p in el:
        if p.tag == 'property' and p.get('name'):
            name = p.get('name').replace('_', '-')
            if name not in out:
                out[name] = ''.join(p.itertext())
    return out

# ---------------------------------------------------------------- .ui indexing
UI = {}           # path -> root <interface>
BY_TEMPLATE = {}  # template class -> element
TMPL_PARENT = {}  # template class -> parent class
BY_ID = {}        # (panel dir, object id) -> element
BY_TAG = {}       # (panel dir, nav tag) -> element
TAG_ANY = {}      # nav tag -> element

PAGE_PARENTS = {'AdwNavigationPage', 'AdwWindow', 'AdwDialog', 'AdwPreferencesPage',
                'AdwPreferencesDialog', 'GtkWindow', 'GtkDialog', 'AdwApplicationWindow'}

def panel_of(path):
    rel = os.path.relpath(path, os.path.join(ROOT, 'panels'))
    return rel.split(os.sep)[0]

def load_ui():
    for p in glob.glob(os.path.join(ROOT, 'panels/**/*.ui'), recursive=True):
        try:
            root = ET.parse(p).getroot()
        except ET.ParseError:
            continue
        UI[p] = root
        pdir = panel_of(p)
        for t in root.iter('template'):
            cls = t.get('class')
            if cls:
                BY_TEMPLATE.setdefault(cls, t)
                TMPL_PARENT.setdefault(cls, t.get('parent') or '')
                tag = props(t).get('tag')
                if tag:
                    BY_TAG.setdefault((pdir, tag), t)
                    TAG_ANY.setdefault(tag, t)
        for o in root.iter('object'):
            if o.get('id'):
                BY_ID.setdefault((pdir, o.get('id')), o)
            tag = props(o).get('tag')
            if tag:
                BY_TAG.setdefault((pdir, tag), o)
                TAG_ANY.setdefault(tag, o)

load_ui()

# --------------------------------------------------- widget classes defined in C
# e.g. G_DEFINE_TYPE (CcDefaultAppsRow, cc_default_apps_row, ADW_TYPE_COMBO_ROW)
C_PARENT = {}
GTYPE_KIND = {
    'ADW_TYPE_COMBO_ROW': 'combo', 'ADW_TYPE_SWITCH_ROW': 'toggle',
    'ADW_TYPE_EXPANDER_ROW': 'expander', 'ADW_TYPE_ENTRY_ROW': 'entry',
    'ADW_TYPE_SPIN_ROW': 'spin', 'ADW_TYPE_ACTION_ROW': 'value',
    'ADW_TYPE_PREFERENCES_ROW': 'value', 'CC_TYPE_LIST_ROW': 'value',
    'CC_TYPE_VERTICAL_ROW': 'value',
}
def load_c():
    for p in glob.glob(os.path.join(ROOT, 'panels/**/*.c'), recursive=True):
        try:
            src = open(p, encoding='utf-8', errors='replace').read()
        except OSError:
            continue
        for m in re.finditer(r'G_DEFINE_(?:FINAL_)?TYPE(?:_WITH_[A-Z_]+)?\s*\(\s*'
                             r'(\w+)\s*,\s*\w+\s*,\s*([A-Z_]+)', src):
            C_PARENT.setdefault(m.group(1), m.group(2))
load_c()

# CcDateTimePage vs a datetime_row: same words, different casing
TMPL_NORM = {re.sub(r'[^a-z0-9]', '', c.lower()): t for c, t in BY_TEMPLATE.items()}

def is_page_template(cls):
    return cls in BY_TEMPLATE and TMPL_PARENT.get(cls) in PAGE_PARENTS

# ---------------------------------------------------------------- class → kind
CONTAINER = {
    'AdwToolbarView', 'AdwBin', 'GtkBox', 'GtkStack', 'GtkStackPage',
    'AdwNavigationView', 'AdwClamp', 'GtkScrolledWindow', 'GtkViewport',
    'AdwLeaflet', 'GtkGrid', 'GtkFrame', 'AdwOverlaySplitView', 'GtkOverlay',
    'AdwViewStack', 'AdwViewStackPage', 'GtkCenterBox', 'GtkFlowBox',
    'GtkRevealer', 'GtkNotebook', 'GtkPaned',
}
# widgets that only ever hold runtime-generated content (device lists, battery
# rows, printer lists...) or window chrome — they are not menu items
DROP = {
    'AdwHeaderBar', 'GtkHeaderBar', 'GtkSearchBar', 'GtkSearchEntry',
    'GtkListStore', 'GtkTreeView', 'GtkTreeViewColumn', 'GtkCellRendererText',
    'GtkSizeGroup', 'GtkAdjustment', 'GtkGestureClick', 'GtkEventControllerKey',
    'GtkShortcutController', 'GtkPopoverMenu', 'GtkMenuButton', 'GtkImage',
    'GtkSeparator', 'GtkProgressBar', 'GtkLevelBar', 'GtkSpinner',
    'GtkDrawingArea', 'GtkPicture', 'GtkToggleButton', 'GtkCheckButton',
    'GtkSwitch', 'GtkButton', 'GtkLabel', 'GtkEntry', 'GtkSpinButton',
    'GtkStringList', 'GtkNoSelection', 'AdwEnumListModel', 'GtkListItemFactory',
    'GtkBuilderListItemFactory', 'CcPermissionInfobar', 'CcListRowInfoButton',
    'AdwStatusPage', 'GtkLinkButton', 'GtkVolumeButton',
}
# CcToggleRow (panels/applications/cc-toggle-row.c) is an AdwActionRow whose
# suffix is a GtkSwitch -- cc_toggle_row_set_allowed() calls gtk_switch_set_active()
# on it -- so it is a switch row even though its template lives in a separate .ui
# the panel never inlines.  Likewise a CcListRow carrying show-switch=True packs a
# GtkSwitch; that is how GNOME 42 draws Airplane Mode and friends (handled below).
TOGGLE  = {'AdwSwitchRow', 'CcSwitchRow', 'CcToggleRow'}
COMBO   = {'AdwComboRow'}
ENTRY   = {'AdwEntryRow', 'AdwPasswordEntryRow'}
SPIN    = {'AdwSpinRow'}
EXPAND  = {'AdwExpanderRow'}
BUTTON  = {'AdwButtonRow'}
ACTION  = {'AdwActionRow', 'CcListRow', 'CcInfoEntry', 'CcHostnameEntry',
           'CcNumberRow', 'CcSplitRow', 'CcIllustratedRow', 'CcVerticalRow',
           'AdwPreferencesRow'}
GROUP   = {'AdwPreferencesGroup'}
PAGE    = {'AdwPreferencesPage', 'AdwNavigationPage', 'AdwWindow', 'AdwDialog',
           'AdwPreferencesDialog', 'GtkWindow', 'GtkDialog'}

def camel(idname):
    parts = [p for p in re.split(r'[_-]', idname) if p and p != 'row']
    return ''.join(p.capitalize() for p in parts)

# Rows whose target is built in C rather than named by a navigation tag.
# Each mapping is grounded in the panel's own .c file (the call that creates it).
SPECIAL = {
    ('search', 'settings_row'):        'CcSearchLocationsDialog',   # cc-search-panel.c:301
    ('sound', 'alert_sound_row'):      'CcAlertChooserWindow',      # cc-sound-panel.c:257
    ('system', 'language_row'):        'CcLanguageChooser',         # cc-region-page.c:397
    ('system', 'login_language_row'):  'CcLanguageChooser',
    ('system', 'formats_row'):         'CcFormatChooser',           # cc-region-page.c:460
    ('system', 'login_formats_row'):   'CcFormatChooser',
    ('keyboard', 'alt_chars_row'):     'CcXkbModifierDialog',       # cc-keyboard-panel.c:106
    ('keyboard', 'compose_row'):       'CcXkbModifierDialog',
    # GNOME 42 laid these panels out separately
    ('region', 'language_row'):        'CcLanguageChooser',
    ('region', 'login_language_row'):  'CcLanguageChooser',
    ('region', 'formats_row'):         'CcFormatChooser',
    ('region', 'login_formats_row'):   'CcFormatChooser',
    ('user-accounts', 'language_row'): 'CcLanguageChooser',
    ('universal-access', 'zoom_row'):         'CcZoomOptionsDialog',
    ('universal-access', 'accessx_row'):      'CcTypingDialog',
    ('universal-access', 'click_assist_row'): 'CcPointingDialog',
    ('user-accounts', 'add_user_button'):  'CcAddUserDialog',      # cc-user-panel.c:337
    ('user-accounts', 'last_login_row'):   'CcLoginHistoryDialog', # cc-user-panel.c:1154
}
# same idea, but the target is a plain <object id=…> in the panel's own .ui
SPECIAL_ID = {
    ('info-overview', 'hostname_row'):    'hostname_editor',  # cc-info-overview-panel.c:917
    ('applications', 'other_media_row'):  'other_type_dialog',
    ('removable-media', 'other_media_row'): 'other_type_dialog',
}
# rows with no id: matched on their label instead
SPECIAL_TITLE = {
    ('system', 'Secure Shell'):   'CcRemoteLoginPage',       # cc-system-panel.c
    ('system', 'System Details'): 'CcSystemDetailsWindow',   # cc-about-page.c
    ('sound', 'Volume Levels'):   'CcVolumeLevelsWindow',    # cc-sound-panel.c
    # GNOME 42 wraps the night-light page in a GtkDialog built in C
    ('display', 'Night Light'):   'CcNightLightPage',        # cc-display-panel.c:499
}
# rows that hand off to a different application, so Settings has no page for
# them.  GNOME 46 marks these with adw-external-link-symbolic; in 42 the only
# signal is the C handler, so they are listed explicitly with its location.
EXTERNAL = {
    ('info-overview', 'software_updates_row'),   # open_software_update() -> gnome-software
    ('user-accounts', 'parental_controls_row'),  # spawn_malcontent_control() -> malcontent
    ('system', 'parental_controls_row'),         # GNOME 46 moved Users under System
}
# a dialog's OK/Cancel buttons are window chrome, not menu rows
DIALOG_ACTIONS = {'Select', 'Cancel', 'Close', 'Done', 'Apply', 'OK', 'Back',
                  'Continue', 'Next', 'Previous', 'Undo', 'Help'}
# handled by a dedicated builder instead of a .ui walk
SHORTCUT_ROWS = {('keyboard', 'common_shortcuts_row')}

def subpage_for(o, pdir, title):
    """Resolve a drill-in row to the element of the page it opens."""
    p = props(o)
    objid = o.get('id')
    # 1. AdwNavigationView: <property name="action-name">navigation.push</property>
    #    <property name="action-target">'screenlock'</property>
    if 'navigation.push' in (p.get('action-name') or ''):
        tag = (p.get('action-target') or '').strip().strip("'\"")
        hit = BY_TAG.get((pdir, tag)) or TAG_ANY.get(tag)
        if hit is not None:
            return hit
    # 2. explicit C-side binding
    spec = SPECIAL.get((pdir, objid)) or SPECIAL_TITLE.get((pdir, title))
    if spec and spec in BY_TEMPLATE:
        return BY_TEMPLATE[spec]
    sid = SPECIAL_ID.get((pdir, objid))
    if sid and (pdir, sid) in BY_ID:
        return BY_ID[(pdir, sid)]
    if not objid:
        return None
    # 3. naming convention: users_row -> CcUsersPage / users_dialog
    base = camel(objid)
    for suffix in ('Page', 'Dialog', 'Window', 'Subpage', 'Panel'):
        hit = BY_TEMPLATE.get('Cc' + base + suffix)
        if hit is not None:
            return hit
    # class names do not always word-split the way the row id does
    # (datetime_row -> CcDateTimePage), so try again ignoring word boundaries
    for suffix in ('page', 'dialog', 'window', 'subpage', 'panel'):
        hit = TMPL_NORM.get('cc' + base.lower() + suffix)
        if hit is not None:
            return hit
    stem = re.sub(r'_(row|button)$', '', objid)
    for suffix in ('_page', '_dialog', '_window', '_subpage'):
        hit = BY_ID.get((pdir, stem + suffix))
        if hit is not None:
            return hit
    return None

stats = {'pages': 0, 'unresolved': set()}
MAXDEPTH = 6

# which navigation tags are actually pushed by a row, per panel directory
PUSHED = {}
for _p, _root in UI.items():
    _d = panel_of(_p)
    for _o in _root.iter('object'):
        _pr = props(_o)
        if 'navigation.push' in (_pr.get('action-name') or ''):
            PUSHED.setdefault(_d, set()).add(
                (_pr.get('action-target') or '').strip().strip("'\""))

def children_objects(el):
    """GtkBuilder nests objects under <child> and under <property name="child">"""
    for c in el:
        if c.tag == 'child':
            for o in c:
                if o.tag == 'object':
                    yield o
        elif c.tag == 'property' and c.get('name') in ('child', 'content'):
            for o in c:
                if o.tag == 'object':
                    yield o
        elif c.tag == 'object':
            yield c

def descendant_classes(el, depth=3):
    """classes of widgets nested inside a row (switch / radio detection)"""
    if depth == 0:
        return
    for c in el.iter('object'):
        if c is not el:
            yield c

SLIDER = {'CcVolumeSlider', 'CcBalanceSlider', 'CcFadeSlider', 'CcSubwooferSlider',
          'GtkScale', 'CcScale'}
INNER_COMBO = {'CcDeviceComboBox', 'CcProfileComboBox', 'GtkComboBoxText',
               'GtkDropDown', 'GtkAppChooserButton'}

def inner_label(o):
    """A row built by hand (AdwPreferencesRow + GtkBox + GtkLabel + widget)
       carries its name in the first translatable GtkLabel inside it."""
    for c in o.iter('object'):
        if c.get('class') == 'GtkLabel':
            for p in c:
                if p.tag == 'property' and p.get('name') in ('label',) \
                        and p.get('translatable') == 'yes':
                    return clean(''.join(p.itertext()))
    return None

def has_next_arrow(o):
    """GNOME 42 marks a drill-in row with a go-next arrow image."""
    for c in o.iter('object'):
        if c.get('class') == 'GtkImage' and \
                (props(c).get('icon-name') or '').startswith('go-next'):
            return True
    return False

C_TEXT = {}
def panel_c(pdir):
    if pdir not in C_TEXT:
        buf = []
        for p in glob.glob(os.path.join(ROOT, 'panels', pdir, '*.c')):
            try:
                buf.append(open(p, encoding='utf-8', errors='replace').read())
            except OSError:
                pass
        C_TEXT[pdir] = '\n'.join(buf)
    return C_TEXT[pdir]

def grid_rows(o, pdir):
    """GNOME 42's Default Applications panel is a GtkGrid of labels paired with
       app chooser buttons; the buttons are added from C, so only the labels
       are in the .ui."""
    classes = {c.get('class') for c in o.iter('object')}
    if 'GtkAppChooserButton' not in classes and \
            'gtk_app_chooser_button_new' not in panel_c(pdir):
        return []
    out = []
    for c in o.iter('object'):
        if c.get('class') != 'GtkLabel':
            continue
        for p in c:
            if p.tag == 'property' and p.get('name') == 'label' \
                    and p.get('translatable') == 'yes':
                t = clean(''.join(p.itertext()))
                if t:
                    out.append({'title': t, 'summary': None, 'kind': 'combo',
                                'children': []})
    return out

def toggle_button_choices(o):
    """A row of GtkToggleButtons sharing a group is a picker, not a list box —
    the Appearance panel's Default/Dark style chooser is built this way.  Each
    button is named by the GtkLabel that claims it as its mnemonic-widget."""
    def column(el):
        lay = el.find('layout')
        if lay is None:
            return None
        for pr in lay:
            if pr.get('name') == 'column':
                return ''.join(pr.itertext()).strip()
        return None

    labels, by_col = {}, {}
    for c in o.iter('object'):
        if c.get('class') == 'GtkLabel':
            p = props(c)
            mw = p.get('mnemonic-widget')
            if mw:
                labels[mw] = clean(p.get('label'))
            col = column(c)
            if col is not None:
                by_col.setdefault(col, clean(p.get('label')))
    btns = [c for c in o.iter('object') if c.get('class') == 'GtkToggleButton']
    # GNOME 42 has no mnemonic-widget here: the caption sits directly under the
    # button in the same GtkGrid column.
    for b in btns:
        if b.get('id') and b.get('id') not in labels:
            col = column(b)
            if col is not None and by_col.get(col):
                labels[b.get('id')] = by_col[col]
    if len(btns) < 2:
        return []
    ids = {b.get('id') for b in btns}
    if not any(props(b).get('group') in ids for b in btns):
        return []
    out = []
    for b in btns:
        t = labels.get(b.get('id'))
        if t:
            out.append({'title': t, 'summary': None, 'kind': 'radio',
                        'group': o.get('id') or 'style', 'children': []})
    return out

def is_external(o):
    """GNOME marks a row that leaves Settings with the external-link icon."""
    for c in o.iter('object'):
        if c.get('class') == 'GtkImage' and \
                props(c).get('icon-name') == 'adw-external-link-symbolic':
            return True
    return False

def combo_options(o):
    """AdwComboRow model: <object class="GtkStringList"><items><item>…"""
    for m in o.iter('object'):
        if m.get('class') == 'GtkStringList':
            items = [clean(''.join(i.itertext())) for i in m.iter('item')]
            items = [i for i in items if i]
            if items:
                return items
    return None

# ------------------------------------------------------------ key bindings
# A KeyListEntry names a GSettings schema and key; the accelerator itself is
# the default value of that key, which lives in gnome-settings-daemon /
# gsettings-desktop-schemas rather than in gnome-control-center.  The media
# keys carry two definitions of every binding: the modern list-typed key in
# the plugin schema, and the single-string key in its ".deprecated" companion,
# which is where the bare hardware keysyms (XF86AudioRaiseVolume and friends)
# still live and which gnome-settings-daemon binds statically
# (plugins/media-keys/shortcuts-list.h, static_setting = TRUE).  Take the
# modern value and fall back to the deprecated one when it is empty, which is
# what the panel ends up showing.
def load_schemas():
    out = {}
    for d in SCHEMA_DIRS:
        for f in glob.glob(os.path.join(d, '**', '*.gschema.xml*'), recursive=True):
            try:
                src = open(f, encoding='utf-8').read()
            except OSError:
                continue
            marks = [(m.group(1), m.start())
                     for m in re.finditer(r'<schema[^>]*id="([^"]+)"', src)]
            if not marks:
                continue
            for m in re.finditer(r'<key name="([^"]+)"[^>]*>(.*?)</key>', src, re.S):
                sid = None
                for cand, at in marks:
                    if at < m.start():
                        sid = cand
                dv = re.search(r'<default>(.*?)</default>', m.group(2), re.S)
                if sid and dv:
                    out.setdefault((sid, m.group(1)), dv.group(1).strip())
    return out

SCHEMAS = load_schemas()

KEYNAME = {'Primary': 'Ctrl', 'Control': 'Ctrl', 'Ctrl': 'Ctrl', 'Alt': 'Alt',
           'Shift': 'Shift', 'Super': 'Super', 'Meta': 'Meta', 'Hyper': 'Hyper'}

def accel_label(raw):
    """render a GVariant accelerator default the way GTK labels it"""
    if raw is None:
        return None
    raw = raw.replace('<![CDATA[', '').replace(']]>', '').strip()
    raw = raw.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    vals = re.findall(r"'([^']*)'", raw)
    accel = next((v for v in vals if v), None)
    if not accel:
        return None
    mods = [KEYNAME.get(m, m) for m in re.findall(r'<([^>]+)>', accel)]
    key = re.sub(r'<[^>]*>', '', accel)
    key = re.sub(r'^XF86', '', key)
    if len(key) == 1:
        key = key.upper()
    elif key.islower():
        key = key[:1].upper() + key[1:]
    return '+'.join(mods + [key]) if key else None

def binding_for(schema, key):
    if not schema or not key:
        return None
    lab = accel_label(SCHEMAS.get((schema, key)))
    if lab:
        return lab
    return accel_label(SCHEMAS.get((schema + '.deprecated', key)))

def build_shortcuts():
    """The Keyboard Shortcuts screen is generated from the shipped keybinding
       lists: panels/keyboard/*.xml.in, one <KeyListEntries> per section."""
    out = []
    for f in sorted(glob.glob(os.path.join(ROOT, 'panels/keyboard/*.xml.in'))):
        try:
            root = ET.parse(f).getroot()
        except ET.ParseError:
            continue
        name = clean(root.get('name'))
        schema = root.get('schema')
        rows = []
        for e in root.iter('KeyListEntry'):
            d = clean(e.get('description') or ''.join(e.itertext()))
            if d:
                rows.append({'title': d, 'summary': None, 'kind': 'value',
                             'binding': binding_for(e.get('schema') or schema,
                                                    e.get('name')),
                             'children': []})
        if name and rows:
            out.append({'kind': 'group', 'title': name, 'footer': None,
                        'children': rows})
    return out

def walk(el, pdir, depth, seen):
    out = []
    p_self = props(el)
    if el.get('class') in PAGE or el.tag == 'template':
        d = clean(p_self.get('description'))
        if d:
            out.append({'kind': 'note', 'title': d, 'summary': None, 'children': []})

    at_page = el.get('class') in PAGE or el.tag == 'template'

    radio_group = None
    for o in children_objects(el):
        cls = o.get('class') or ''
        # a standalone button sitting on the page body rather than inside a row
        # ("Add User…", "Add Printer…") is a real control, not chrome
        if cls == 'GtkButton' and at_page:
            bt = clean(props(o).get('label'))
            if bt and bt not in DIALOG_ACTIONS:
                out.append({'title': bt, 'summary': None, 'kind': 'button',
                            'children': []})
                continue
        if cls in DROP:
            continue
        # a page-like template dropped in as a placeholder is reached through
        # its navigation tag, not inline — but only when a row in this panel
        # actually pushes it.  CcUserPage is placed inline inside CcUsersPage.
        if is_page_template(cls):
            tm = BY_TEMPLATE[cls]
            tmtag = props(tm).get('tag')
            if tmtag and tmtag in PUSHED.get(pdir, ()):
                continue
            if id(tm) in seen:
                continue
            out += walk(tm, pdir, depth, seen | {id(tm)}) + \
                walk(o, pdir, depth, seen | {id(tm)})
            continue
        # an empty instance of a content template (CcNightLightPage,
        # CcRemovableMediaSettings) is filled in from that template's own .ui
        if cls in BY_TEMPLATE and not list(children_objects(o)) and \
                TMPL_PARENT.get(cls) in ('AdwBin', 'GtkBox', 'AdwPreferencesGroup',
                                         'AdwPreferencesPage', 'GtkWidget'):
            tm = BY_TEMPLATE[cls]
            if id(tm) not in seen:
                kids = walk(tm, pdir, depth, seen | {id(tm)})
                gt = clean(props(tm).get('title'))
                if kids and TMPL_PARENT[cls] == 'AdwPreferencesGroup' and gt:
                    out.append({'kind': 'group', 'title': gt, 'footer': None,
                                'children': kids})
                else:
                    out += kids
            continue
        p = props(o)
        title = clean(p.get('title') or p.get('label'))
        subtitle = clean(p.get('subtitle'))

        # a navigation destination carries a tag; if a row in this panel pushes
        # it, it is reached from that row rather than drawn where it sits.
        # Pages pushed only from C (the per-app page of the Apps panel) have no
        # row to hang off, so they stay inline.
        if cls == 'AdwNavigationPage' and p.get('tag') in PUSHED.get(pdir, ()):
            continue

        if cls in ('AdwViewStackPage', 'GtkStackPage') and title:
            kids = walk(o, pdir, depth, seen)
            if kids:
                out.append({'kind': 'group', 'title': title, 'footer': None,
                            'children': kids})
            continue

        if cls == 'GtkGrid':
            g = grid_rows(o, pdir)
            out += g if g else walk(o, pdir, depth, seen)
            continue

        if cls in CONTAINER or cls in PAGE:
            out += walk(o, pdir, depth, seen)
            continue

        if cls in GROUP:
            if 'no_devices' in (o.get('id') or ''):
                continue        # the "No Output Devices" empty state
            kids = walk(o, pdir, depth, seen) or toggle_button_choices(o)
            foot = clean(p.get('description'))
            if not kids:
                # a group with no rows in the .ui is a list box the panel fills
                # at run time from real hardware/accounts.  Keep it if it is
                # named or described — the heading is real, the contents are not.
                if not title and not foot:
                    continue
                out.append({'kind': 'group', 'title': title, 'footer': foot,
                            'runtime': True, 'children': []})
                continue
            out.append({'kind': 'group', 'title': title,
                        'footer': foot, 'children': kids})
            continue

        if cls == 'GtkListBox':
            out += walk(o, pdir, depth, seen)
            continue

        inner = [c.get('class') for c in descendant_classes(o)]

        if not title and (cls in ACTION or cls == 'GtkListBoxRow') and (
                set(inner) & (SLIDER | INNER_COMBO)
                or 'GtkSwitch' in inner or has_next_arrow(o)):
            title = inner_label(o)

        if not title:
            out += walk(o, pdir, depth, seen)
            continue

        node = {'title': title, 'summary': subtitle, 'children': []}

        if set(inner) & SLIDER:
            node['kind'] = 'slider'
        elif not p.get('title') and (set(inner) & INNER_COMBO):
            node['kind'] = 'combo'
        elif is_external(o) or (pdir, o.get('id')) in EXTERNAL:
            node['kind'] = 'external'
        elif (cls in TOGGLE or 'GtkSwitch' in inner
              or str(p.get('show-switch', '')).lower() == 'true'):
            node['kind'] = 'toggle'
            node['default'] = p.get('active')
        elif 'GtkCheckButton' in inner:
            node['kind'] = 'radio'
            # first radio of a group is the one the others point at
            gid = None
            for c in o.iter('object'):
                if c.get('class') == 'GtkCheckButton':
                    gid = props(c).get('group') or c.get('id')
                    break
            node['group'] = gid or radio_group or title
            radio_group = node['group']
        elif cls in COMBO:
            node['kind'] = 'combo'
            opts = combo_options(o)
            if opts:
                node['options'] = opts
        elif cls in SPIN:
            node['kind'] = 'spin'
        elif cls in ENTRY:
            node['kind'] = 'entry'
        elif cls in BUTTON:
            node['kind'] = 'button'
        elif cls in EXPAND:
            node['kind'] = 'expander'
            node['children'] = walk(o, pdir, depth + 1, seen)
        elif cls in ACTION or cls == 'GtkListBoxRow':
            drills = ('navigation.push' in (p.get('action-name') or '')
                      or p.get('show-arrow') == 'True'
                      or p.get('activatable') == 'True'
                      or has_next_arrow(o)
                      or bool(o.get('id') and (SPECIAL.get((pdir, o.get('id')))
                                               or SPECIAL_ID.get((pdir, o.get('id')))))
                      or (pdir, title) in SPECIAL_TITLE
                      or (pdir, o.get('id')) in SHORTCUT_ROWS)
            node['kind'] = 'link' if drills else 'value'
        elif cls in C_PARENT and GTYPE_KIND.get(C_PARENT[cls]):
            # a row class implemented in C; its GType says what it behaves like
            node['kind'] = GTYPE_KIND[C_PARENT[cls]]
        else:
            out += walk(o, pdir, depth, seen)
            continue

        if node['kind'] == 'link' and depth < MAXDEPTH:
            if (pdir, o.get('id')) in SHORTCUT_ROWS:
                node['children'] = build_shortcuts()
                stats['pages'] += 1
            else:
                tgt = subpage_for(o, pdir, title)
                if tgt is not None:
                    mark = id(tgt)
                    if mark not in seen:
                        stats['pages'] += 1
                        node['children'] = walk(tgt, pdir, depth + 1, seen | {mark})
                elif o.get('id'):
                    stats['unresolved'].add(pdir + '/' + o.get('id'))
                else:
                    stats['unresolved'].add(pdir + '/<' + title + '>')

        out.append(node)
    return out

# ---------------------------------------------------------------- panel list
def registered_panels():
    """the panels gnome-control-center actually builds (cc-panel-loader.c)"""
    src = open(os.path.join(ROOT, 'shell/cc-panel-loader.c'), encoding='utf-8').read()
    body = src[src.index('default_panels[]'):]
    body = body[:body.index('};')]
    return [m.group(1) for m in re.finditer(r'PANEL_TYPE\s*\(\s*"([^"]+)"', body)]

def sidebar_order():
    """the order the shell sorts the sidebar in (cc-panel-list.c panel_order[])"""
    src = open(os.path.join(ROOT, 'shell/cc-panel-list.c'), encoding='utf-8').read()
    body = src[src.index('panel_order[] = {'):]
    body = body[:body.index('};')]
    return [m.group(1) for m in re.finditer(r'"([^"]+)"', body)]

def panel_order():
    """registered panels, in sidebar order; anything unlisted keeps loader order"""
    reg = registered_panels()
    want = [p for p in sidebar_order() if p != 'separator']
    ordered = [p for p in want if p in reg]
    return ordered + [p for p in reg if p not in ordered]

def desktop_categories(pdir, panel):
    for f in sorted(glob.glob(os.path.join(ROOT, 'panels', pdir, '*.desktop.in*')) +
                    glob.glob(os.path.join(ROOT, 'panels', pdir, 'data/*.desktop.in*'))):
        m = re.search(r'^Categories=(.+)$', open(f, encoding='utf-8').read(), re.M)
        if m:
            return m.group(1).split(';')
    return []

def desktop_name(pdir, panel):
    cands = ['gnome-%s-panel.desktop.in' % panel,
             'gnome-%s-panel.desktop.in.in' % panel,
             'data/gnome-%s-panel.desktop.in' % panel,
             'data/gnome-%s-panel.desktop.in.in' % panel,
             '*.desktop.in', '*.desktop.in.in',
             'data/*.desktop.in', 'data/*.desktop.in.in']
    for pat in cands:
        for f in sorted(glob.glob(os.path.join(ROOT, 'panels', pdir, pat))):
            txt = open(f, encoding='utf-8').read()
            m = re.search(r'^Name=(.+)$', txt, re.M)
            c = re.search(r'^Comment=(.+)$', txt, re.M)
            if m:
                return clean(m.group(1)), clean(c.group(1)) if c else None
    return None, None

DIRMAP = {'wifi': 'network'}

def panel_template(pdir, panel):
    want = 'Cc' + camel(panel) + 'Panel'
    best = None
    for p in sorted(glob.glob(os.path.join(ROOT, 'panels', pdir, '*.ui'))):
        root = UI.get(p)
        if root is None:
            continue
        for t in root.iter('template'):
            cls = t.get('class', '')
            if t.get('parent') in ('CcPanel', 'AdwBin') and cls.endswith('Panel'):
                if cls == want:
                    return t
                best = best if best is not None else t
    return best

tree = []
for panel in panel_order():
    pdir = DIRMAP.get(panel, panel)
    if not os.path.isdir(os.path.join(ROOT, 'panels', pdir)):
        continue
    tmpl = panel_template(pdir, panel)
    name, comment = desktop_name(pdir, panel)
    if tmpl is None:
        # GNOME 42's printers panel is assembled in C from printers.ui rather
        # than declared as a template.  The panel is real and registered, so it
        # keeps its sidebar slot; its body is runtime state.
        if name:
            tree.append({'panel': panel, 'kind': 'panel', 'title': name,
                         'summary': None, 'comment': comment,
                         'category': desktop_categories(pdir, panel),
                         'status_pages': [], 'children': []})
        continue
    kids = walk(tmpl, pdir, 0, frozenset())
    # <child type="titlebar-end"><object class="GtkSwitch"> is the panel-wide
    # master switch drawn in the header bar (Bluetooth, Camera, Microphone,
    # Location Services).  The header bar itself is chrome, so the walk drops
    # it; the switch is a real control and belongs at the top of the panel.
    hdr = [o for o in tmpl.iter('object')
           if o.get('class') in ('AdwHeaderBar', 'GtkHeaderBar')]
    hdr += [o for ch in tmpl if ch.tag == 'child'
            and (ch.get('type') or '').startswith('titlebar')
            for o in ch.iter('object')]
    if any(sw.get('class') == 'GtkSwitch' for h in hdr for sw in h.iter('object')):
        kids.insert(0, {'title': name or panel.title(), 'summary': None,
                        'kind': 'toggle', 'children': []})
    # AdwStatusPage = the full-panel message shown when there is nothing to
    # list (no adapter, no printer, no tablet).  A panel can declare several
    # and picks one at run time, so they are kept as panel metadata rather
    # than drawn inline.
    status = []
    for sp in tmpl.iter('object'):
        if sp.get('class') != 'AdwStatusPage':
            continue
        sp_p = props(sp)
        st = clean(sp_p.get('title'))
        if st:
            status.append({'id': sp.get('id'), 'title': st,
                           'description': clean(sp_p.get('description'))})
    tree.append({'panel': panel, 'kind': 'panel', 'title': name or panel.title(),
                 'summary': None, 'comment': comment,
                 'category': desktop_categories(pdir, panel),
                 'status_pages': status, 'children': kids})

# ------------------------------------------------- GNOME 42's Privacy sub-list
# cc-panel-list.c gives panels whose .desktop declares X-GNOME-PrivacySettings
# their own sub-list behind a synthetic "Privacy" row (cc-window.c:242).
# GNOME 46 dropped this and ships a real "privacy" panel instead.
if not any(p['panel'] == 'privacy' for p in tree):
    priv = [p for p in tree if 'X-GNOME-PrivacySettings' in (p.get('category') or [])]
    if priv:
        order = [x for x in sidebar_order()]
        priv.sort(key=lambda p: order.index(p['panel']) if p['panel'] in order else 99)
        for p in priv:
            tree.remove(p)
        node = {'panel': 'privacy', 'kind': 'panel', 'title': 'Privacy',
                'summary': None, 'comment': None, 'category': [],
                'status_pages': [], 'children': [
                    {'title': p['title'], 'summary': p.get('comment'),
                     'kind': 'link', 'panel': p['panel'],
                     'status_pages': p.get('status_pages') or [],
                     'children': p['children']} for p in priv]}
        at = next((i for i, p in enumerate(tree)
                   if order.index(p['panel']) > order.index('privacy')
                   if p['panel'] in order), len(tree)) if 'privacy' in order else len(tree)
        tree.insert(at, node)

# ---------------------------------------------------------------- tidy up
RANK = {'link': 6, 'expander': 5, 'toggle': 4, 'combo': 4, 'slider': 4,
        'spin': 4, 'entry': 4, 'external': 4, 'radio': 3, 'button': 2,
        'value': 1, 'note': 0, 'group': 0}

def dedupe(nodes):
    """GNOME ships alternate versions of a row side by side (a switch when the
       permission can be changed, a plain info row when it cannot) and shows
       one at run time. Keep the richest of each title."""
    out, byname = [], {}
    for n in nodes:
        n['children'] = dedupe(n.get('children') or [])
        key = (n.get('kind') == 'group', n.get('title'))
        if n.get('title') and key in byname:
            prev = byname[key]
            if RANK.get(n.get('kind'), 0) > RANK.get(prev.get('kind'), 0):
                prev.update(n)
            elif n.get('kind') == 'group':
                prev['children'] += n['children']
            continue
        if n.get('title'):
            byname[key] = n
        out.append(n)
    return out

for p in tree:
    p['children'] = dedupe(p['children'])

# ------------------------------------------------- sidebar separator groups
# panel_order[] in cc-panel-list.c interleaves the literal string "separator"
# between the runs of panels the shell draws a divider between.  GNOME 42 has
# no separators at all, so every panel lands in group 0 and the sidebar stays
# the single flat list that release actually shows.
_ord = sidebar_order()
_grp, _g = {}, 0
for _p in _ord:
    if _p == 'separator':
        _g += 1
        continue
    _grp[_p] = _g
for p in tree:
    p['sidebar_group'] = _grp.get(p['panel'], _g)

json.dump(tree, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

def count(ns):
    return sum(1 + count(n.get('children') or []) for n in ns)
def depth(ns, d=1):
    return max([d] + [depth(n['children'], d + 1) for n in ns if n.get('children')])

print('panels:', len(tree), '| subpages followed:', stats['pages'])
print('TOTAL NODES:', count(tree), '| max depth:', depth(tree))
for p in tree:
    print('   %-16s %-24s %d' % (p['panel'], p['title'], count(p['children'])))
print('unresolved drill-in rows:', len(stats['unresolved']))
for u in sorted(stats['unresolved'])[:30]:
    print('   ?', u)
