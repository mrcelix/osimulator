#!/usr/bin/env python3
"""ChromeOS (Chromium OS) Settings tree, extracted from Chromium's own source.

ChromeOS Settings is a WebUI app.  Its screens are Polymer templates that live
next to the TypeScript classes that own them, its navigation is a route tree
declared in TypeScript over path constants declared in a mojom file, and every
label is an `$i18n{}` key that resolves through C++ to a GRIT message.  This
script reads all four of those and emits the menu tree as JSON.

    python3 cros-extract.py /tmp/cros /tmp/chromeos124.json --revamp

Nothing here is written from memory: a label that cannot be resolved back to a
shipped English string is reported rather than invented.
"""
import json
import os
import re
import sys
from html.parser import HTMLParser

# The sibling module is named with a hyphen to match the other extractors, so
# it is loaded by path rather than imported by name.
import importlib.util as _ilu  # noqa: E402
_spec = _ilu.spec_from_file_location(
    'cros_strings',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cros-strings.py'))
cros_strings = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(cros_strings)
Strings = cros_strings.Strings

SETTINGS_RES = os.path.join('chrome', 'browser', 'resources', 'ash', 'settings')
ROUTES_MOJOM = os.path.join('ash', 'webui', 'settings', 'public', 'constants',
                            'routes.mojom')


# ---------------------------------------------------------------- tiny DOM

VOID = {'br', 'img', 'input', 'hr', 'meta', 'link', 'source', 'area', 'base'}


class Node:
    __slots__ = ('tag', 'attrs', 'kids', 'text', 'parent')

    def __init__(self, tag, attrs=None):
        self.tag = tag
        self.attrs = attrs or {}
        self.kids = []
        self.text = ''
        self.parent = None

    def add(self, n):
        n.parent = self
        self.kids.append(n)

    def cls(self):
        return (self.attrs.get('class') or '').split()

    def walk(self):
        for k in self.kids:
            yield k
            for x in k.walk():
                yield x

    def inner_text(self):
        out = [self.text]
        for k in self.kids:
            out.append(k.inner_text())
        return ' '.join(t for t in out if t.strip())

    def __repr__(self):
        return '<%s %s>' % (self.tag, list(self.attrs)[:3])


class _P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('#root')
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        n = Node(tag, {k: (v if v is not None else '') for k, v in attrs})
        self.stack[-1].add(n)
        if tag not in VOID:
            self.stack.append(n)

    def handle_startendtag(self, tag, attrs):
        n = Node(tag, {k: (v if v is not None else '') for k, v in attrs})
        self.stack[-1].add(n)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        if data.strip():
            self.stack[-1].text += (' ' if self.stack[-1].text else '') + \
                ' '.join(data.split())


def parse_template(src):
    src = re.sub(r'<style\b.*?</style>', '', src, flags=re.S)
    src = re.sub(r'<!--.*?-->', '', src, flags=re.S)
    p = _P()
    p.feed(src)
    return p.root


# -------------------------------------------------------- runtime conditions

def build_env(revamp):
    """Boolean environment for the `dom-if` guards in the templates.

    The persona is a personally-owned consumer Chromebook: signed in to a
    Google Account, not enterprise-managed, not a guest or child session, with
    an Android container available.  These are *device* facts, not menu facts;
    they decide which optional rows a real machine would show.  Anything not
    named here is left unresolved and the branch is kept, so a row is never
    dropped merely because this table does not know about it.
    """
    e = {
        'isRevampWayfindingEnabled_': revamp,
        'isRevampEnabled_': revamp,
        'isRevampWayfindingEnabled': revamp,

        'isGuestMode_': False,
        'isGuest_': False,
        'isSecondaryUser_': False,
        'isChild_': False,
        'isChildUser_': False,
        'isManaged_': False,
        'isDeviceManaged_': False,
        'isAccountManaged_': False,
        'isDemoMode_': False,
        'isKioskModeActive_': False,
        'isRevenBranding_': False,
        'showParentalControls_': False,

        'isAndroidAppsEnabled_': True,
        'androidAppsVisible': True,
        'showCrostini_': True,
        'isPowerwashAllowed_': True,
        'showSecureDnsSetting_': True,
    }
    return e


_NEG = re.compile(r'^\s*!\s*(.+?)\s*$')


def eval_cond(expr, env):
    """True / False / None for a Polymer `if=` expression."""
    if not expr:
        return None
    m = re.match(r'^\s*\[\[(.*)\]\]\s*$|^\s*\{\{(.*)\}\}\s*$', expr, re.S)
    if not m:
        return None
    body = (m.group(1) or m.group(2) or '').strip()
    neg = False
    n = _NEG.match(body)
    if n:
        neg, body = True, n.group(1).strip()
    if not re.match(r'^[A-Za-z0-9_.]+$', body):
        return None            # a computed function call -- not decidable here
    v = env.get(body)
    if v is None:
        return None
    return (not v) if neg else v


# GRIT branch markers can also appear inside a template.
_grit_expr = cros_strings._grit_expr


def prune(node, env):
    """Resolve conditional wrappers in place.

    A `dom-if` whose condition is known-false is deleted; one that is known-true
    or undecidable is unwrapped so its rows sit where they would be painted.
    A `dom-if` carrying a `route-path` is a subpage declaration and is left
    alone -- it is navigation, not a conditional.
    """
    out = []
    for k in node.kids:
        if k.tag == 'if':                       # GRIT <if expr="...">
            v = _grit_expr(k.attrs.get('expr', ''))
            if v is False:
                continue
            prune(k, env)
            out.extend(k.kids)
            for c in k.kids:
                c.parent = node
            continue
        if k.tag == 'template':
            is_ = k.attrs.get('is', '')
            if 'route-path' in k.attrs:
                prune(k, env)
                out.append(k)
                continue
            if is_ == 'dom-if':
                v = eval_cond(k.attrs.get('if', ''), env)
                if v is False:
                    continue
                prune(k, env)
                out.extend(k.kids)
                for c in k.kids:
                    c.parent = node
                continue
            if is_ == 'dom-repeat':
                # A runtime list (paired devices, installed apps, accounts).
                # Keep the wrapper as a marker; its body describes one item of
                # a list a real machine fills in, not a fixed menu row.
                k.attrs['__repeat'] = '1'
                out.append(k)
                continue
            # A bare <template> is a lazily stamped page body.
            prune(k, env)
            out.extend(k.kids)
            for c in k.kids:
                c.parent = node
            continue
        prune(k, env)
        out.append(k)
    node.kids = out


# --------------------------------------------------------------- label layer

_I18N = re.compile(r'^\s*\$i18n(?:Polymer|Raw)?\{([A-Za-z0-9_]+)\}\s*$')
# `[[i18n('k')]]` and `[[i18nAdvanced('k')]]` are the binding forms of the same
# lookup that `$i18n{k}` does -- "Advanced" only means the string may carry
# markup.  The key is static either way, so both resolve here.
_I18N_CALL = re.compile(
    r"^\s*\[\[i18n(?:Advanced|Dynamic)?\(\s*'([A-Za-z0-9_]+)'\s*\)\s*\]\]\s*$",
    re.S)
_I18N_ANY = re.compile(r'\$i18n(?:Polymer|Raw)?\{([A-Za-z0-9_]+)\}')
# A Polymer one-way/two-way binding left over in a string that was otherwise
# resolvable, e.g. the "On"/"Off" pair inside
# `[[getOnOffString_(isBluetoothToggleOn_, '$i18nPolymer{deviceOn}', ...)]]`.
_BINDING = re.compile(r'(\[\[.*?\]\]|\{\{.*?\}\})', re.S)


def _drop_bindings(v):
    """Text with any unresolved binding removed, or None if nothing is left.

    A label that is *entirely* a computed binding has no English form to show,
    so it is dropped; one that merely ends in a runtime value ("...smaller or
    larger [[logicalResolutionText_]]") keeps the part ChromeOS wrote.
    """
    if v is None or ('[[' not in v and '{{' not in v):
        return v
    v = _BINDING.sub(' ', v)
    v = re.sub(r'\s+([,.;:!?])', r'\1', ' '.join(v.split())).strip(' ,;:-')
    return v if re.search(r'[A-Za-z]', v) else None


class Labels:
    """Resolves a template attribute to the English text ChromeOS paints."""

    def __init__(self, strings, ts_index):
        self.st = strings
        self.ts = ts_index
        self.unresolved = {}

    def text(self, raw, ctx=''):
        if raw is None:
            return None
        raw = raw.strip()
        if not raw:
            return None
        m = _I18N.match(raw) or _I18N_CALL.match(raw)
        if m:
            return self.st.get(m.group(1))
        # A literal with placeholders interpolated, e.g. "$i18n{a} - $i18n{b}"
        if _I18N_ANY.search(raw):
            def sub(mm):
                return self.st.get(mm.group(1)) or ''
            v = _I18N_ANY.sub(sub, raw).strip()
            # The interpolation can leave a computed binding wrapped around the
            # resolved pieces -- `[[getOnOffString_(x, 'On', 'Off')]]`.  Which
            # of the two ChromeOS shows is device state, so nothing here can be
            # shown as the label.
            if '[[' in v or '{{' in v:
                self.unresolved.setdefault(ctx, set()).add(raw)
                return _drop_bindings(v)
            return v or None
        if raw.startswith('[[') or raw.startswith('{{'):
            # A computed binding: the label is produced by a method on the
            # element.  Resolve the simple, overwhelmingly common shape where
            # that method just returns one of two i18n strings.
            fn = re.match(r'^\[\[([A-Za-z0-9_]+)\(', raw)
            if fn:
                got = self.ts.method_string(ctx, fn.group(1))
                if got:
                    return self.st.get(got)
            self.unresolved.setdefault(ctx, set()).add(raw)
            return None
        if raw.startswith('$'):
            return None
        return _drop_bindings(raw)


class TsIndex:
    """Cross-references the TypeScript half of each Polymer element."""

    def __init__(self, base, env=None):
        self.base = base
        self.tag_to_html = {}
        self.src = {}
        # The same persona table the template walker uses, so that a label
        # method branching on `this.isChildUser_` resolves the same way the
        # markup guarded by `[[isChildUser_]]` does.
        self.env = env or {}
        self._scan()

    def _scan(self):
        for dirpath, _d, files in os.walk(self.base):
            for f in files:
                if not f.endswith('.ts') or f.endswith('.d.ts'):
                    continue
                p = os.path.join(dirpath, f)
                raw = open(p, encoding='utf-8', errors='replace').read()
                self.src[p] = raw
                html = p[:-3] + '.html'
                if not os.path.exists(html):
                    continue
                for m in re.finditer(
                        r"static get is\(\)[^{]*\{\s*return\s*'([a-z0-9-]+)'",
                        raw):
                    self.tag_to_html.setdefault(m.group(1), (html, p))
                for m in re.finditer(r"^\s*is:\s*'([a-z0-9-]+)'", raw, re.M):
                    self.tag_to_html.setdefault(m.group(1), (html, p))

    def method_string(self, ts_path, name):
        """i18n key returned by a trivial label-producing method, else None."""
        raw = self.src.get(ts_path)
        if not raw:
            return None
        m = re.search(r'\b' + re.escape(name) + r'\s*\([^)]*\)\s*:'
                      r'?[^{]*\{(.{0,600}?)\n  \}', raw, re.S)
        if not m:
            return None
        body = m.group(1)
        _KEYCALL = r"(?:i18nAdvanced|i18nDynamic|i18n)\(\s*'([A-Za-z0-9_]+)'"
        keys = re.findall(_KEYCALL, body) or \
            re.findall(r"loadTimeData\.getString\('([A-Za-z0-9_]+)'\)", body)
        if len(set(keys)) == 1:
            return keys[0]
        if not keys:
            return None

        # More than one candidate: the method picks between them on a device
        # property.  Resolve it with the persona table when every guard in the
        # method is a property the table knows, and give up otherwise rather
        # than guessing.
        def truth(expr):
            expr = expr.strip()
            if '||' in expr:
                parts = [truth(p) for p in expr.split('||')]
                return True if any(p is True for p in parts) else (
                    False if all(p is False for p in parts) else None)
            if '&&' in expr:
                parts = [truth(p) for p in expr.split('&&')]
                return False if any(p is False for p in parts) else (
                    True if all(p is True for p in parts) else None)
            neg = False
            while expr.startswith('!'):
                neg = not neg
                expr = expr[1:].strip()
            expr = expr.removeprefix('this.').strip().strip('()')
            if expr not in self.env:
                return None
            v = bool(self.env[expr])
            return (not v) if neg else v

        # `return cond ? this.i18n('a') : this.i18n('b');`
        tern = re.search(
            r'return\s+([^;?]+?)\s*\?\s*(?:this\.)?' + _KEYCALL +
            r"[^;]*?:\s*(?:this\.)?" + _KEYCALL, body, re.S)
        if tern:
            v = truth(tern.group(1))
            if v is True:
                return tern.group(2)
            if v is False:
                return tern.group(3)
            return None

        # `if (cond) { return this.i18n('a'); } ... return this.i18n('b');`
        for gm in re.finditer(
                r'if\s*\(([^)]*)\)\s*\{\s*return\s+(?:this\.)?' + _KEYCALL,
                body, re.S):
            v = truth(gm.group(1))
            if v is True:
                return gm.group(2)
            if v is None:
                return None
        tail = re.findall(r'\n\s*return\s+(?:this\.)?' + _KEYCALL, body)
        if tail:
            return tail[-1]
        return None

    def navigate_target(self, ts_path, handler):
        """`routes.X` a click handler navigates to, else None."""
        raw = self.src.get(ts_path)
        if not raw:
            return None
        m = re.search(r'\b' + re.escape(handler) +
                      r'\s*\([^)]*\)\s*:?[^{]*\{(.{0,900}?)\n  \}', raw, re.S)
        if not m:
            return None
        t = re.search(r'navigateTo\(\s*routes\.([A-Z0-9_]+)', m.group(1))
        return t.group(1) if t else None

    def menu_options(self, ts_path, prop):
        """Option labels of a `settings-dropdown-menu`'s menu-options array."""
        raw = self.src.get(ts_path)
        if not raw:
            return None
        m = re.search(re.escape(prop) + r'\s*:\s*\{(.{0,2500}?)\n      \}',
                      raw, re.S)
        blk = m.group(1) if m else None
        if blk is None:
            m = re.search(re.escape(prop) + r'\s*(?::[^=]*)?=\s*\[(.{0,2500}?)\];',
                          raw, re.S)
            blk = m.group(1) if m else None
        if blk is None:
            return None
        keys = re.findall(r"name:\s*loadTimeData\.getString\('([A-Za-z0-9_]+)'\)",
                          blk)
        keys += re.findall(r"name:\s*this\.i18n\('([A-Za-z0-9_]+)'\)", blk)
        return keys or None


# ------------------------------------------------------------- routes layer

def load_route_paths(root):
    """`NETWORK_SECTION_PATH` -> `internet`, from routes.mojom."""
    raw = open(os.path.join(root, ROUTES_MOJOM), encoding='utf-8').read()
    out = {}
    for m in re.finditer(r'const string k([A-Za-z0-9]+)\s*=\s*"([^"]*)"', raw):
        name = m.group(1)
        screaming = re.sub(r'(?<!^)(?=[A-Z])', '_', name).upper()
        out[screaming] = m.group(2)
    return out


def load_routes(root, mojom_paths):
    """`routes.X` -> URL path, by replaying os_settings_routes.ts."""
    p = os.path.join(root, SETTINGS_RES, 'os_settings_routes.ts')
    raw = open(p, encoding='utf-8').read()
    routes = {'BASIC': '/', 'ADVANCED': '/advanced'}
    parents = {}

    def path_expr(txt):
        m = re.search(r'routesMojom\.([A-Z0-9_]+)', txt)
        if m:
            return mojom_paths.get(m.group(1))
        m = re.search(r"'([^']+)'", txt)
        return m.group(1) if m else None

    # createSection(parent, path, section) and createSubpage(parent, path, sub)
    for m in re.finditer(
            r'r\.([A-Z0-9_]+)\s*=\s*\n?\s*create(Section|Subpage)\('
            r'(.{0,300}?)\);', raw, re.S):
        name, kind, args = m.group(1), m.group(2), m.group(3)
        par = re.match(r'\s*r\.([A-Z0-9_]+)', args)
        seg = path_expr(args.split(',', 1)[1] if ',' in args else '')
        if seg is None:
            continue
        parent = par.group(1) if par else 'BASIC'
        parents[name] = parent
        routes[name] = '/' + seg.lstrip('/')
    # createChild() calls extend their parent's path.
    for m in re.finditer(r'r\.([A-Z0-9_]+)\s*=\s*\n?\s*r\.([A-Z0-9_]+)'
                         r'\.createChild\(\s*([^,)]+)', raw, re.S):
        name, parent, seg = m.group(1), m.group(2), path_expr(m.group(3))
        if seg is None:
            continue
        base = routes.get(parent, '')
        routes[name] = seg if seg.startswith('/') else \
            base.rstrip('/') + '/' + seg
        parents[name] = parent
    return routes, parents


# ------------------------------------------------------------- menu layer

_MENU_ITEM = re.compile(
    r'\{\s*section:\s*Section\.(k[A-Za-z0-9]+),\s*'
    r'path:\s*(.{0,120}?),\s*'
    r"icon:\s*'([^']*)',\s*"
    r'label:\s*this\.i18n\(\'([A-Za-z0-9_]+)\'\)'
    r'(.{0,200}?)\},', re.S)


def load_menu(root, mojom_paths, revamp):
    """The sidebar, from the menu-item arrays in os_settings_menu.ts."""
    p = os.path.join(root, SETTINGS_RES, 'os_settings_menu',
                     'os_settings_menu.ts')
    raw = open(p, encoding='utf-8').read()

    def arrays(fn_name):
        m = re.search(r'private compute' + fn_name +
                      r'MenuItems_\(\).{0,80}?\{(.*?)\n  \}', raw, re.S)
        if not m:
            return []
        body = m.group(1)
        # The revamp deletes the Advanced menu outright:
        #   if (this.isRevampWayfindingEnabled_) { return []; }
        if re.search(r'if\s*\(this\.isRevampWayfindingEnabled_\)\s*\{\s*'
                     r'return\s*\[\];', body):
            if revamp:
                return []
            body = re.sub(r'if\s*\(this\.isRevampWayfindingEnabled_\)\s*\{\s*'
                          r'return\s*\[\];\s*\}', '', body)
        if 'isRevampWayfindingEnabled_' in body and '} else {' in body:
            head, tail = body.split('} else {', 1)
            body = head if revamp else tail
        out = []
        for mm in _MENU_ITEM.finditer(body):
            path_txt = mm.group(2)
            pm = re.search(r'routesMojom\.([A-Z0-9_]+)', path_txt)
            path = '/' + mojom_paths[pm.group(1)] if pm and \
                pm.group(1) in mojom_paths else None
            if path is None and 'aboutMenuItemPath_' in path_txt:
                path = '/' + mojom_paths.get('ABOUT_CHROME_OS_SECTION_PATH',
                                             'help')
            sub = re.search(r"sublabel:\s*this\.i18n\('([A-Za-z0-9_]+)'\)",
                            mm.group(5))
            out.append({
                'section': mm.group(1),
                'path': path,
                'icon': mm.group(3),
                'label_key': mm.group(4),
                'sub_key': sub.group(1) if sub else None,
            })
        return out

    basic, advanced = arrays('Basic'), arrays('Advanced')

    # Before the revamp, About ChromeOS is in neither array: the menu template
    # paints it as a standalone item below a separator, inside
    # `<template is="dom-if" if="[[!isRevampWayfindingEnabled_]]">`.  The
    # revamped menu instead carries it as the last Basic item, so this only
    # fires for the older release.
    about = []
    if not revamp and not any(i['section'] == 'kAboutChromeOs'
                              for i in basic + advanced):
        html = open(os.path.join(root, SETTINGS_RES, 'os_settings_menu',
                                 'os_settings_menu.html'),
                    encoding='utf-8').read()
        if 'aboutMenuItemPath_' in html:
            about.append({
                'section': 'kAboutChromeOs',
                'path': '/' + mojom_paths.get('ABOUT_CHROME_OS_SECTION_PATH',
                                              'help'),
                'icon': 'os-settings:chrome',
                'label_key': 'aboutOsPageTitle',
                'sub_key': None,
            })
    return basic, advanced, about


def load_section_elements(root):
    """`Section.kNetwork` -> the custom element that paints that section."""
    p = os.path.join(root, SETTINGS_RES, 'main_page_container',
                     'main_page_container.html')
    raw = open(p, encoding='utf-8').read()
    out = {}
    for m in re.finditer(
            r'<page-displayer\s+section="\[\[Section\.(k[A-Za-z0-9]+)\]\]"\s*>'
            r'\s*<([a-z0-9-]+)', raw, re.S):
        out.setdefault(m.group(1), m.group(2))
    return out


# ------------------------------------------------------------- the row walk

ROW_TAGS = {
    'cr-link-row', 'settings-toggle-button', 'settings-dropdown-menu',
    'settings-slider', 'cr-toggle', 'cr-button', 'cr-input', 'cr-checkbox',
    'localized-link', 'settings-multidevice-feature-item', 'cr-radio-button',
    'cr-expand-button', 'settings-radio-group', 'cr-icon-button',
}

# Wrappers that only exist to lay a page out.
TRANSPARENT = {'div', 'span', 'settings-card', 'os-settings-subpage',
               'settings-subpage', 'iron-collapse', 'section', 'main'}


class Walker:
    def __init__(self, root, labels, ts, routes, strings):
        self.root = root
        self.lab = labels
        self.ts = ts
        self.routes = routes
        self.st = strings
        self.cache = {}
        self.stats = {'rows': 0, 'screens': 0, 'unlabelled': 0}
        # `_box_label` reports the row's secondary line through here, since a
        # bare control's sub-label lives in the enclosing box, not on the tag.
        self._last_sub = None

    # -- template loading -------------------------------------------------
    def template_for(self, tag):
        got = self.ts.tag_to_html.get(tag)
        if not got:
            return None, None
        html, tsp = got
        return html, tsp

    def load(self, tag, env):
        if tag in self.cache:
            return self.cache[tag]
        html, tsp = self.template_for(tag)
        if not html:
            self.cache[tag] = (None, None)
            return None, None
        tree = parse_template(open(html, encoding='utf-8',
                                   errors='replace').read())
        prune(tree, env)
        self.cache[tag] = (tree, tsp)
        return tree, tsp

    # -- one screen -------------------------------------------------------
    def rows_of(self, node, tsp, env, depth, seen):
        """Flatten a subtree into simulator rows."""
        out = []
        for k in node.kids:
            out.extend(self.row_from(k, tsp, env, depth, seen))
        return out

    def row_from(self, n, tsp, env, depth, seen):
        t = n.tag

        if t == 'template' and 'route-path' in n.attrs:
            return []                      # subpages are collected separately
        if t == 'template' and n.attrs.get('__repeat'):
            return [{'kind': 'runtime-list',
                     'items': n.attrs.get('items', '')}]

        if t == 'h2':
            txt = self.lab.text(n.attrs.get('_', None)) or \
                self.lab.text(n.inner_text(), tsp)
            return [{'kind': 'heading', 'title': txt}] if txt else []

        if t == 'settings-card':
            title = self.lab.text(n.attrs.get('header-text'), tsp)
            kids = self.rows_of(n, tsp, env, depth, seen)
            return [{'kind': 'group', 'title': title, 'rows': kids}]

        if t == 'cr-link-row':
            lbl = self.lab.text(n.attrs.get('label'), tsp)
            sub = self.lab.text(n.attrs.get('sub-label'), tsp)
            tgt = None
            h = n.attrs.get('on-click')
            if h:
                tgt = self.ts.navigate_target(tsp, h)
            if not tgt and 'route-path' in n.attrs:
                tgt = n.attrs['route-path']
            row = {'kind': 'link', 'title': lbl, 'sub': sub}
            if tgt:
                row['route'] = self.routes.get(tgt, tgt)
            return [row] if lbl else self._unlabelled(n)

        if t == 'settings-toggle-button':
            lbl = self.lab.text(n.attrs.get('label'), tsp)
            sub = self.lab.text(n.attrs.get('sub-label'), tsp)
            return [{'kind': 'toggle', 'title': lbl, 'sub': sub,
                     'pref': n.attrs.get('pref', '')}] if lbl \
                else self._unlabelled(n)

        if t == 'settings-multidevice-feature-item':
            lbl = self.lab.text(n.attrs.get('feature-name'), tsp) or \
                self.lab.text(n.attrs.get('label'), tsp)
            sub = self.lab.text(n.attrs.get('feature-summary-html'), tsp) or \
                self.lab.text(n.attrs.get('sub-label-text'), tsp)
            return [{'kind': 'toggle', 'title': lbl, 'sub': sub}] if lbl else []

        if t in ('settings-dropdown-menu', 'settings-slider', 'cr-toggle',
                 'cr-input', 'cr-checkbox'):
            self._last_sub = None
            if t == 'cr-checkbox' and (n.kids or (n.text or '').strip()):
                lbl, sub = self._split_secondary(n, tsp)
                if not lbl:
                    lbl = self._box_label(n, tsp)
                    sub = self._last_sub
            else:
                lbl = self._box_label(n, tsp)
                sub = self._last_sub
            if not lbl:
                return self._unlabelled(n)
            kind = {'settings-dropdown-menu': 'combo',
                    'settings-slider': 'slider',
                    'cr-toggle': 'toggle',
                    'cr-input': 'input',
                    'cr-checkbox': 'check'}[t]
            row = {'kind': kind, 'title': lbl}
            if sub:
                row['sub'] = sub
            if t == 'settings-dropdown-menu':
                prop = re.search(r'\[\[([A-Za-z0-9_]+)\]\]',
                                 n.attrs.get('menu-options', ''))
                if prop:
                    keys = self.ts.menu_options(tsp, prop.group(1))
                    if keys:
                        opts = [self.st.get(k) for k in keys]
                        row['options'] = [o for o in opts if o]
            return [row]

        if t == 'cr-button':
            lbl, _ = self._split_secondary(n, tsp)
            return [{'kind': 'button', 'title': lbl}] if lbl else []

        if t == 'localized-link':
            txt = self.lab.text(n.attrs.get('localized-string'), tsp)
            return [{'kind': 'note', 'title': txt}] if txt else []

        if t in ('cr-dialog', 'cr-action-menu', 'paper-tooltip', 'style',
                 'cr-policy-indicator', 'cr-policy-pref-indicator',
                 'cr-tooltip-icon', 'iron-icon', 'cr-icon-button', 'slot',
                 'settings-languages', 'iron-list', 'select', 'option',
                 'cr-lazy-render', 'settings-idle-load'):
            return []

        if t in TRANSPARENT or t == '#root':
            # `.settings-box` is one visual row built from a label div and a
            # control; let the control claim the whole box rather than emitting
            # the label text as a row of its own.
            return self.rows_of(n, tsp, env, depth, seen)

        # Any other custom element is a composed piece of the page: expand it
        # from its own template so the rows it contributes appear in place.
        if '-' in t and depth < 6 and t not in seen:
            tree, sub_ts = self.load(t, env)
            if tree is not None:
                return self.rows_of(tree, sub_ts, env, depth + 1,
                                    seen | {t})
        return self.rows_of(n, tsp, env, depth, seen)

    def _split_secondary(self, node, tsp):
        """(label, sub) for a container that holds both.

        ChromeOS writes a two-line row as the label text followed by a
        `<div class="secondary">` holding the explanatory line.  Reading the
        container's inner text alone would run the two sentences together, so
        the secondary part is pulled out and returned as the sub-label.
        """
        head, tail = [], []
        def visit(k, into):
            if 'secondary' in k.cls():
                into = tail
            if k.text and k.text.strip():
                into.append(k.text.strip())
            for c in k.kids:
                visit(c, into)
        if node.text and node.text.strip():
            head.append(node.text.strip())
        for c in node.kids:
            visit(c, head)
        lab = self.lab.text(' '.join(head), tsp) if head else None
        sub = self.lab.text(' '.join(tail), tsp) if tail else None
        return lab, sub

    def _box_label(self, n, tsp):
        """Label of the `.settings-box` row a bare control sits in."""
        p = n.parent
        for _ in range(3):
            if p is None:
                break
            if 'settings-box' in p.cls() or p.tag in ('div',):
                for c in p.kids:
                    if c is n:
                        continue
                    if c.tag in ('div', 'span', 'h2') and \
                            ('start' in c.cls() or c.tag == 'h2'):
                        v, s = self._split_secondary(c, tsp)
                        if v:
                            self._last_sub = s
                            return v
                    if c.tag == 'localized-link':
                        v = self.lab.text(c.attrs.get('localized-string'), tsp)
                        if v:
                            return v
            p = p.parent
        for a in ('label', 'label-aria', 'aria-label'):
            v = self.lab.text(n.attrs.get(a), tsp)
            if v:
                return v
        return None

    def _unlabelled(self, n):
        self.stats['unlabelled'] += 1
        return []

    # -- a whole section --------------------------------------------------
    def section(self, tag, env):
        tree, tsp = self.load(tag, env)
        if tree is None:
            return None
        landing, subpages = None, []
        for n in tree.walk():
            if n.tag == 'div' and n.attrs.get('route-path') == 'default':
                landing = n
            if n.tag == 'template' and 'route-path' in n.attrs and \
                    n.attrs['route-path'] != 'default':
                sp = None
                for c in n.walk():
                    if c.tag in ('os-settings-subpage', 'settings-subpage'):
                        sp = c
                        break
                if sp is None:
                    continue
                title = self.lab.text(sp.attrs.get('page-title'), tsp)
                subpages.append({
                    'route': n.attrs['route-path'],
                    'title': title,
                    'rows': self.rows_of(sp, tsp, env, 1, {tag}),
                })
        rows = self.rows_of(landing, tsp, env, 1, {tag}) if landing is not None \
            else self.rows_of(tree, tsp, env, 1, {tag})
        return {'element': tag, 'rows': rows, 'subpages': subpages}


# ------------------------------------------------------------------- main

def strip_empty(rows):
    out = []
    for r in rows:
        if r.get('kind') == 'group':
            r['rows'] = strip_empty(r.get('rows', []))
            if not r['rows'] and not r.get('title'):
                continue
        if r.get('kind') == 'runtime-list':
            continue
        if not r.get('title'):
            continue
        out.append(r)
    # Collapse the duplicate a row's conditional variants leave behind.
    seen, ded = set(), []
    for r in out:
        k = (r.get('kind'), r.get('title'), r.get('sub'))
        if k in seen:
            continue
        seen.add(k)
        ded.append(r)
    return ded


def count_rows(rows):
    n = 0
    for r in rows:
        n += 1
        if r.get('kind') == 'group':
            n += count_rows(r.get('rows', []))
    return n


def main():
    root = sys.argv[1]
    out_path = sys.argv[2]
    revamp = '--revamp' in sys.argv

    strings = Strings(root, revamp)
    base = os.path.join(root, SETTINGS_RES)
    env = build_env(revamp)
    ts = TsIndex(base, env)
    labels = Labels(strings, ts)
    mojom = load_route_paths(root)
    routes, _parents = load_routes(root, mojom)
    basic, advanced, about = load_menu(root, mojom, revamp)
    sect_el = load_section_elements(root)
    w = Walker(root, labels, ts, routes, strings)

    result = {'revamp': revamp, 'sections': [], 'advanced': [], 'about': []}
    for bucket, items in (('sections', basic), ('advanced', advanced),
                          ('about', about)):
        for it in items:
            tag = sect_el.get(it['section'])
            data = w.section(tag, env) if tag else None
            entry = {
                'section': it['section'],
                'path': it['path'],
                'icon': it['icon'],
                'title': strings.get(it['label_key']),
                'sub': strings.get(it['sub_key']) if it['sub_key'] else None,
                'element': tag,
                'rows': strip_empty(data['rows']) if data else [],
                'subpages': [
                    {'route': s['route'], 'title': s['title'],
                     'rows': strip_empty(s['rows'])}
                    for s in (data['subpages'] if data else [])
                    if s['title']],
            }
            result[bucket].append(entry)

    json.dump(result, open(out_path, 'w', encoding='utf-8'),
              indent=1, ensure_ascii=False)

    every = result['sections'] + result['advanced'] + result['about']
    nsec = len(every)
    nsub = sum(len(s['subpages']) for s in every)
    nrow = sum(count_rows(s['rows']) for s in every)
    nrow += sum(count_rows(p['rows']) for s in every for p in s['subpages'])
    print('revamp menu      :', revamp)
    print('sections         :', nsec, '(%d basic, %d advanced, %d about)' %
          (len(result['sections']), len(result['advanced']),
           len(result['about'])))
    print('subpages         :', nsub)
    print('rows             :', nrow)
    print('unresolved labels:', sum(len(v) for v in labels.unresolved.values()))
    print('missing i18n keys:', len(strings.missing_key))
    if strings.missing_key:
        print('   e.g.', sorted(strings.missing_key)[:8])


if __name__ == '__main__':
    main()
