#!/usr/bin/env python3
"""webOS OSE Settings: source -> JSON settings tree.

`webosose/com.webos.app.settings` is the Settings app of webOS Open Source
Edition -- an Enact/React app, not a markup tree, so there is no manifest to
read.  What it has instead is just as mechanical:

  * `src/views/MainPanels.js` holds `const panelMap = ['General', 'Network']`
    -- that array *is* the top-level menu, in order.
  * each `<X>Panel.js` holds a second `panelMap`, an object mapping a screen
    name to the component that draws it.  That is the screen graph.
  * inside a component, a row is one JSX element (`LabeledItem`, `SplitItem`,
    `Button`, `CheckboxItem`, ...) and its words are `$L('English literal')`.
    Enact's `$L` keeps the English string in the call and looks translations up
    by it, so the literal in the source is exactly what the device shows.
  * navigation is `props.addPath.bind(this, 'System Information')` in the
    constructor, wired to a row with `onClick={this.pushPathSystemInformation}`
    -- so a row's destination is resolvable without running anything.

Two things are deliberately *not* claimed as source: the `label={...}` slot of
a row is a runtime reading (device name, MAC address, software version) whose
placeholder is `$L('Loading...')`, and rows drawn from a `VirtualList` of live
data (Wi-Fi networks, the language list) have no rows in source at all.  Both
come out marked so the DSL layer can label them honestly.

NOTE: webOS OSE is a different product from the closed webOS that ships on LG
televisions.  Nothing here describes a retail TV.

Usage:
    python3 webos-ose-extract.py /tmp/webos /tmp/webos-ose.json
"""
import json
import os
import re
import sys

# --------------------------------------------------------------- JSX scanning

# `$L('text')` / `$L("text")`.  Enact also has `$L({value, key})`, which this
# app does not use.
_L = re.compile(r"""\$L\(\s*(['"])(.*?)(?<!\\)\1""", re.S)


def strings(expr):
    """Every `$L()` literal in a fragment of JSX, in source order."""
    return [m.group(2).replace("\\'", "'").replace('\\"', '"')
            for m in _L.finditer(expr or '')]


def scan(src, tags):
    """Yield (tag, attrs, children) for each JSX element with one of `tags`.

    Written as a scanner rather than a regex because attributes hold arbitrary
    JS: `label={a ? $L('x') : $L('y')}` has braces, quotes and `>` inside it.
    """
    out = []
    i = 0
    n = len(src)
    while i < n:
        if src[i] != '<':
            i += 1
            continue
        m = re.match(r'<([A-Za-z][A-Za-z0-9_.]*)', src[i:])
        if not m:
            i += 1
            continue
        tag = m.group(1)
        j = i + m.end()
        depth = 0
        quote = None
        while j < n:
            c = src[j]
            if quote:
                if c == '\\':
                    j += 2
                    continue
                if c == quote:
                    quote = None
            elif c in '\'"`':
                quote = c
            elif c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
            elif depth == 0 and c == '>':
                break
            j += 1
        if j >= n:
            break
        attrs = src[i + m.end():j]
        self_closing = attrs.rstrip().endswith('/')
        if tag in tags:
            kids = ''
            if not self_closing:
                # Children run to the matching `</tag>`; these components are
                # not nested inside themselves anywhere in this app.
                end = src.find('</%s>' % tag, j)
                if end != -1:
                    kids = src[j + 1:end]
            out.append((tag, attrs, kids))
        i = j + 1
    return out


def attr(attrs, name):
    """The raw value of `name={...}` or `name="..."`, or None."""
    m = re.search(r'(?<![A-Za-z0-9_])%s\s*=\s*' % re.escape(name), attrs)
    if not m:
        return None
    i = m.end()
    if i < len(attrs) and attrs[i] in '\'"':
        q = attrs[i]
        j = attrs.find(q, i + 1)
        return attrs[i + 1:j] if j != -1 else None
    if i >= len(attrs) or attrs[i] != '{':
        return None
    depth = 0
    quote = None
    j = i
    while j < len(attrs):
        c = attrs[j]
        if quote:
            if c == '\\':
                j += 2
                continue
            if c == quote:
                quote = None
        elif c in '\'"`':
            quote = c
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return attrs[i + 1:j]
        j += 1
    return None


# ------------------------------------------------------------------ the views

# Every JSX element this app uses to draw a settings row, and what each is.
ROW_TAGS = {
    'LabeledItem': 'item',      # title in children, runtime reading in label=
    'Item':        'item',
    'SplitItem':   'split',     # title in label=, runtime reading in children
    'SplitInput':  'input',
    'CheckboxItem': 'toggle',
    'RadioItem':   'toggle',
    'Button':      'button',
    'InputField':  'input',
    'Input':       'input',
    'Divider':     'heading',
    'BodyText':    'note',
    'Dropdown':    'combo',
    'Marquee':     'field',    # only when it is the `label` half of a row
    'div':         'field',    # same, written as a plain div on some screens
}

# `<div className={css.row}><Marquee className={css.label}>{$L('Password')}</Marquee>`
# -- the row's caption is a Marquee, and the control next to it is a spread.
_FIELD_LABEL = re.compile(r'className=\{css\.label\}')

# `this.pushPathLanguage = props.addPath.bind(this, 'Language')`
_BIND = re.compile(r"""this\.(\w+)\s*=\s*(?:props|this\.props)\.addPath\.bind\(\s*this\s*,\s*(['"])(.*?)\2""")
# `addPath('Wi-Fi Security')` called straight from a handler
_ADD = re.compile(r"""addPath\(\s*(['"])(.*?)\1\s*\)""")

# The placeholder a row shows while its runtime reading loads -- seeing only
# this in `label=` is how we know the slot is device state, not a fixed string.
LOADING = 'Loading...'


# Overlays: a popup, an alert or a countdown notification is not a settings
# row, it is a transient dialog, so its buttons ("Cancel", "Retry", "OK") must
# not be read as menu entries.  Blanking the subtree is the whole fix.
OVERLAY = ('Alert', 'TimerNotification', 'InputPopup', 'Popup', 'Dialog',
           'Notification')


def strip_overlays(src):
    for tag in OVERLAY:
        while True:
            m = re.search(r'<%s[\s>]' % tag, src)
            if not m:
                break
            end = src.find('</%s>' % tag, m.end())
            if end == -1:
                # self-closing
                end = src.find('/>', m.end())
                src = src[:m.start()] + src[end + 2:] if end != -1 else \
                    src[:m.start()]
            else:
                src = src[:m.start()] + src[end + len(tag) + 3:]
    return src


_EXPORT = re.compile(r'export\s+default\s+(?:connect\([^;]*?\)\s*\(\s*)?(\w+)')


def render_body(src):
    """The JSX of the exported component's own `render()`.

    Several of these files define a small helper component *above* the one they
    export -- `WifiConnection.js` opens with a `TimerNotification` wrapper that
    has a `render()` of its own.  Taking the first `render()` in the file would
    read the helper, so the exported name is resolved first and only that
    class's body is scanned.
    """
    body = src
    m = _EXPORT.search(src)
    if m:
        c = re.search(r'\bclass\s+%s\b' % re.escape(m.group(1)), src)
        if c:
            body = block(src, c.end())
    r = re.search(r'\brender\s*\(\s*\)\s*\{', body)
    return strip_overlays(body[r.start():] if r else body)


def block(src, i):
    """The `{...}` starting at or after `i`, brace-matched."""
    i = src.find('{', i)
    if i == -1:
        return ''
    depth = 0
    j = i
    while j < len(src):
        if src[j] == '{':
            depth += 1
        elif src[j] == '}':
            depth -= 1
            if depth == 0:
                return src[i:j]
        j += 1
    return src[i:]


# `addHiddenNetwork() { ... }` and `myWifiClickHander = () => { ... }`
_METHOD = re.compile(r'\n\t(\w+)\s*(?:\([^)\n]*\)\s*\{|=\s*\([^)\n]*\)\s*=>\s*\{)')
# a handler that just calls another bound handler: `this.pushPathAddNetwork()`
_CALL = re.compile(r'this\.(\w+)\s*\(')


def handlers(src):
    """handler name -> screen it pushes.

    Two hops are needed because a row's `onClick` is often a method that does
    some work and *then* navigates: `addHiddenNetwork()` ends in
    `this.pushPathAddNetwork()`, which is the bind that names the screen.
    """
    out = {}
    for m in _BIND.finditer(src):
        out[m.group(1)] = m.group(3)
    bodies = {}
    for m in _METHOD.finditer(src):
        bodies.setdefault(m.group(1), block(src, m.end() - 1))
    for name, body in bodies.items():
        if name in out:
            continue
        a = _ADD.search(body)
        if a:
            out[name] = a.group(2)
    for name, body in bodies.items():
        if name in out:
            continue
        for c in _CALL.finditer(body):
            if c.group(1) in out:
                out[name] = out[c.group(1)]
                break
    return out


# `<CheckboxItem {...showPasswordProps} />` -- the words are in the method.
_SPREAD = re.compile(r'\{\s*\.\.\.\s*(\w+)\s*\}')
# `const showPasswordProps = this.showPasswordProps();`
_ALIAS = re.compile(r'const\s+(\w+)\s*=\s*this\.(\w+)\s*\(')
# what a props method puts on screen
_PROP_STR = re.compile(r"""\b(?:children|title)\s*:\s*\$L\(\s*(['"])(.*?)(?<!\\)\1""")


def propsets(src, body):
    """spread name -> the string that spread puts on screen.

    The wifi screens hand their controls a bag of props
    (`<Button {...connectButtonProps} />`) built by a method that holds the
    label: `connectButtonProps() { return {..., children: $L('Connect')}; }`.
    Resolving the two is what keeps those screens from coming out empty.
    """
    methods = {}
    for m in _METHOD.finditer(src):
        b = block(src, m.end() - 1)
        s = _PROP_STR.search(b)
        if s:
            methods[m.group(1)] = s.group(2)
    out = dict(methods)
    for a in _ALIAS.finditer(body):
        if a.group(2) in methods:
            out[a.group(1)] = methods[a.group(2)]
    return out


# `this.securityTypes = {none: $L('Open'), wep: $L('WEP'), ...}` -- a dropdown's
# choices are a lookup table in the constructor, not JSX, so they have to be
# read separately from the rows.
_OBJ_ASSIGN = re.compile(r'this\.(\w+)\s*=\s*\{')


def option_tables(src):
    """`this.<name> = { ... }` -> the visible strings it holds, in order.

    Only a table whose every entry is a `$L()` string counts: that is a list of
    choices.  `this.securityIndex = {none: 0, wep: 1}` holds no words and is
    skipped.
    """
    out = {}
    for m in _OBJ_ASSIGN.finditer(src):
        b = block(src, m.end() - 1)
        vals = [t for _q, t in _L.findall(b)]
        if vals and len(vals) == b.count(':'):
            out[m.group(1)] = vals
    return out


def propopts(src, body):
    """spread name -> the option list its `<Dropdown>` shows.

    `<Dropdown {...securityTypeProps} />` gets its choices through two hops:
    `securityTypeProps()` calls `makeSecurityList()`, which walks
    `this.securityTypes`.  Following that chain is what keeps the Security
    dropdown from coming out as a bare label with no options.
    """
    tables = option_tables(src)
    if not tables:
        return {}
    bodies = {m.group(1): block(src, m.end() - 1)
              for m in _METHOD.finditer(src)}

    def resolve(name, depth=0):
        b = bodies.get(name)
        if b is None or depth > 2:
            return None
        for t, vals in tables.items():
            if re.search(r'this\.%s\b' % re.escape(t), b):
                return vals
        for c in sorted(set(_CALL.findall(b))):
            if c != name:
                v = resolve(c, depth + 1)
                if v:
                    return v
        return None

    out = {}
    for name in bodies:
        v = resolve(name)
        if v:
            out[name] = v
    for a in _ALIAS.finditer(body):
        if a.group(2) in out:
            out[a.group(1)] = out[a.group(2)]
    return out


def rows_of(path):
    """Every source-defined row of one view component."""
    src = open(path, encoding='utf-8').read()
    hnd = handlers(src)
    body = render_body(src)
    spreads = propsets(src, body)
    choices = propopts(src, body)
    rows = []
    for tag, attrs, kids in scan(body, set(ROW_TAGS)):
        kind = ROW_TAGS[tag]
        if kind == 'field':
            # A Marquee is a caption only when it carries the row's label class;
            # otherwise it is the value half and holds no fixed words.
            if not _FIELD_LABEL.search(attrs):
                continue
            kind = 'input'
        label_expr = attr(attrs, 'label')
        label_str = strings(label_expr)
        kid_str = strings(kids)
        if not kid_str and not label_str:
            sp = _SPREAD.search(attrs)
            if sp and sp.group(1) in spreads:
                kid_str = [spreads[sp.group(1)]]
        if kind in ('split', 'input'):
            # `label=` names the field; the children are the live value typed
            # into it, so there is no second state hiding in there.
            title = label_str[0] if label_str else (
                kid_str[0] if kid_str else None)
            reading = True
            states = []
        else:
            title = kid_str[0] if kid_str else (
                label_str[0] if label_str else None)
            # `label={x ? $L('Connected to Internet') : $L('Not Connected')}`
            # names both states in source; `label={x ? x : $L('Loading...')}`
            # names none of them.
            states = [s for s in label_str if s != LOADING]
            reading = bool(label_expr) and not states
        if not title or title == LOADING:
            # Either a bare text child holding no `$L()` at all, or a control
            # whose *only* string is the loading placeholder -- the Network
            # device-name button reads `{this.state.deviceName || $L('Loading...')}`
            # and so has no fixed label of its own.
            continue
        r = {'kind': {'item': 'link', 'split': 'value', 'toggle': 'toggle',
                      'button': 'button', 'input': 'input',
                      'heading': 'heading', 'note': 'note',
                      'combo': 'combo'}[kind],
             'title': title}
        click = (attr(attrs, 'onClick') or '').strip()
        m = re.search(r'this\.(\w+)', click)
        dest = hnd.get(m.group(1)) if m else None
        if dest:
            r['route'] = dest
        elif kind == 'item' and not click:
            # An item with no handler at all is a read-only reading; one with a
            # handler that stays on the page (the My Wi-Fi / Other Wi-Fi list
            # expanders) is still something you press.
            r['kind'] = 'value'
        if states:
            r['states'] = states
        if reading:
            r['runtime'] = True
        if kind == 'toggle':
            r['on'] = 'selected' in attrs and 'selected={false}' not in attrs
        if kind == 'combo':
            sp = _SPREAD.search(attrs)
            o = choices.get(sp.group(1)) if sp else None
            if o:
                r['options'] = o
        rows.append(r)
    return rows


# -------------------------------------------------------------------- the app

_TOP = re.compile(r"const\s+panelMap\s*=\s*\[(.*?)\]", re.S)
_MAP = re.compile(r"const\s+panelMap\s*=\s*\{(.*?)\n\};", re.S)
_ENTRY = re.compile(r"""(['"])(.*?)\1\s*:\s*<(\w+)""")


def panel_screens(path):
    """screen name -> component name, from a `<X>Panel.js` panelMap."""
    src = open(path, encoding='utf-8').read()
    m = _MAP.search(src)
    if not m:
        return {}
    return {e.group(2): e.group(3) for e in _ENTRY.finditer(m.group(1))}


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else '/tmp/webos'
    out_path = sys.argv[2] if len(sys.argv) > 2 else '/tmp/webos-ose.json'
    views = os.path.join(root, 'src', 'views')

    src = open(os.path.join(views, 'MainPanels.js'), encoding='utf-8').read()
    m = _TOP.search(src)
    if not m:
        sys.exit('no top-level panelMap in MainPanels.js')
    tops = re.findall(r"""['"]([^'"]+)['"]""", m.group(1))

    sections = []
    for top in tops:
        pdir = os.path.join(views, top)
        screens = panel_screens(os.path.join(pdir, top + 'Panel.js'))
        # The screen whose name equals the panel is the panel's own first page.
        built = {}
        for name, comp in screens.items():
            f = os.path.join(pdir, comp + '.js')
            built[name] = rows_of(f) if os.path.exists(f) else []
        entry = {'group': None, 'kind': 'link', 'title': top, 'panel': top,
                 'screen': top, 'rows': built.get(top, []), 'subpages': []}
        for name, rows in built.items():
            if name == top:
                continue
            entry['subpages'].append({'panel': name, 'route': name,
                                      'title': name, 'rows': rows,
                                      'subpages': []})
        sections.append(entry)

    json.dump({'sections': sections}, open(out_path, 'w', encoding='utf-8'),
              indent=1, ensure_ascii=False)

    nrow = sum(len(s['rows']) + sum(len(p['rows']) for p in s['subpages'])
               for s in sections)
    print('top panels       :', len(sections), '->', ', '.join(tops))
    print('screens          :', sum(1 + len(s['subpages']) for s in sections))
    print('rows             :', nrow)
    for s in sections:
        print('  %-10s %2d rows' % (s['title'], len(s['rows'])))
        for p in s['subpages']:
            print('     %-32s %2d rows' % (p['title'], len(p['rows'])))
    print('->', out_path)


if __name__ == '__main__':
    main()
