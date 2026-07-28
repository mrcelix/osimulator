#!/usr/bin/env python3
"""Gaia (Firefox OS) Settings: source -> JSON settings tree.

Gaia builds its Settings app out of plain HTML fragments.  Each screen is one
`<element name="x">` in `apps/settings/elements/x.html`, a row is an `<li>`, and
the words are not in the markup at all -- every visible string is a
`data-l10n-id` key that resolves in `apps/settings/locales/settings.en-US.properties`
(plus the `shared/locales` bundles for strings several apps share).

So the whole menu is machine-readable: the `<li>` tells you what kind of control
it is, the `href="#panel"` tells you which screen it opens, and the l10n key
tells you what it says.  This script walks that graph from the `root` element
and writes the same JSON shape the other extractors in this directory produce.

Usage:
    python3 gaia-extract.py /tmp/gaia /tmp/gaia25.json
"""
import json
import os
import re
import sys
from html.parser import HTMLParser

# ------------------------------------------------------------ string layer

# A .properties line is `key=value`, and an attribute of that same string is
# `key.attribute=value`.  Continuation lines and comments are not used by Gaia's
# settings bundle, so the format needs no more than this.
_PROP = re.compile(r'^([A-Za-z0-9_.\-]+)\s*=\s*(.*)$')


def load_properties(root, device_type='phone'):
    """l10n key -> English text, over every en-US bundle Settings can reach."""
    out = {}
    loc = os.path.join(root, 'apps', 'settings', 'locales')
    # Gaia ships one build for phones, tablets and TVs, and the strings that
    # name the device live in a per-type overlay ("Reset Phone" / "Reset TV").
    # The overlay is read first so it wins; the simulated device is a phone.
    files = [os.path.join(loc, 'device_type', device_type,
                          'settings.device.en-US.properties'),
             os.path.join(loc, 'settings.en-US.properties')]
    shared = os.path.join(root, 'shared', 'locales')
    for dirpath, _dirs, names in os.walk(shared):
        # branding/ has an `official` and an `unofficial` bundle -- the shipped
        # build is the official one, where brandShortName is "Firefox OS".
        if os.path.basename(dirpath) == 'unofficial':
            continue
        for n in names:
            if n.endswith('.en-US.properties'):
                files.append(os.path.join(dirpath, n))
    for p in files:
        if not os.path.exists(p):
            continue
        for line in open(p, encoding='utf-8'):
            line = line.rstrip('\n')
            if not line or line.lstrip().startswith('#'):
                continue
            m = _PROP.match(line.strip())
            if not m:
                continue
            # The settings bundle is loaded first and wins: a shared bundle may
            # define the same key for another app's wording.
            out.setdefault(m.group(1), m.group(2).strip())
    return out


class Strings:
    def __init__(self, root):
        self.props = load_properties(root)
        self.missing = set()

    def plain(self, key, args=None):
        """The text of a key, or None when the key only carries attributes.

        Gaia writes `data-l10n-id="wifiSection"` on a row whose *visible* words
        come from a child `<span data-l10n-id="wifi">`; `wifiSection` itself is
        defined only as `wifiSection.ariaLabel`.  Returning None for that case
        is what lets the walker fall through to the child.

        `args` is the parsed `data-l10n-args` of the element -- markup-level
        data, so substituting it keeps the result source-derived.
        """
        if key is None:
            return None
        v = self.props.get(key)
        if v is None:
            if key not in self.props and not any(
                    k.startswith(key + '.') for k in self.props):
                self.missing.add(key)
            return None
        return clean(self.expand(v, args=args))

    def expand(self, v, depth=0, args=None):
        """Fill `{{name}}` from the element's own args, then from the bundle.

        Gaia uses this for branding (`{{brandShortName}}` -> Firefox OS, from
        shared/locales/branding/official), for plain aliasing, as in
        `screenReader-header = {{screenReader}}`, and for per-element values
        written into the markup, as in
        `<option data-l10n-id="powerSave-threshold" data-l10n-args='{"level": "5"}'>`.
        A name that neither source defines is a runtime value and is left
        standing so the DSL layer can see it.
        """
        if depth > 4 or '{{' not in v:
            return v
        def one(m):
            name = m.group(1).strip()
            if args and name in args:
                return str(args[name])
            return self.props.get(name, m.group(0))
        out = _VAR.sub(one, v)
        return out if out == v else self.expand(out, depth + 1, args=args)


# `{{name}}` is a runtime substitution and `<a>...</a>` inline markup.  The name
# may contain a hyphen: Gaia aliases whole strings that way, as in
# `more-info-header = {{more-info}}`.
_VAR = re.compile(r"\{\{\s*([A-Za-z0-9_.\[\]\-]+)\s*\}\}")


def clean(v):
    v = re.sub(r'<[^>]+>', '', v)
    v = ' '.join(v.split())
    return v


# --------------------------------------------------------------- HTML layer

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
        'meta', 'param', 'source', 'track', 'wbr'}


class Node:
    __slots__ = ('tag', 'attrs', 'kids', 'parent')

    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = attrs or {}
        self.kids = []
        self.parent = parent

    def find_all(self, *tags, cls=None):
        """Every descendant with one of `tags` (and optionally a class)."""
        out = []
        for k in self.kids:
            if isinstance(k, Node):
                if (not tags or k.tag in tags) and \
                        (cls is None or cls in k.attrs.get('class', '').split()):
                    out.append(k)
                out.extend(k.find_all(*tags, cls=cls))
        return out

    def first(self, *tags, cls=None):
        r = self.find_all(*tags, cls=cls)
        return r[0] if r else None


class Tree(HTMLParser):
    """A tolerant tree builder -- Gaia's fragments are HTML, not XML."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node('#root')
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = Node(tag, dict(attrs), self.cur)
        self.cur.kids.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.kids.append(Node(tag, dict(attrs), self.cur))

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        if data.strip():
            self.cur.kids.append(data)


def parse(path):
    t = Tree()
    t.feed(open(path, encoding='utf-8').read())
    return t.root


# ---------------------------------------------------------------- the walker

# Controls, in the order they must be tested: a range lives inside a <label>
# that may also hold a <p>, and a <select> lives inside a <span class="button">,
# so the specific shapes have to win over the generic ones.
SWITCHES = ('gaia-switch', 'gaia-checkbox')


def l10n_args(node):
    """`data-l10n-args='{"level": "5"}'` -> {'level': '5'}."""
    raw = node.attrs.get('data-l10n-args')
    if not raw:
        return None
    try:
        v = json.loads(raw)
    except ValueError:
        return None
    return v if isinstance(v, dict) else None


def index_ids(el):
    """id -> node, so `aria-labelledby` can be followed."""
    out = {}
    for n in el.find_all():
        i = n.attrs.get('id')
        if i and i not in out:
            out[i] = n
    return out


class Walker:
    def __init__(self, root, st):
        self.dir = os.path.join(root, 'apps', 'settings', 'elements')
        self.st = st
        self.panels = {}          # name -> parsed <element> node
        self.cache = {}           # name -> extracted screen
        self.stack = []           # panels currently being expanded
        self.ids = {}             # id -> node, for the panel being walked
        for f in sorted(os.listdir(self.dir)):
            if not f.endswith('.html'):
                continue
            for e in parse(os.path.join(self.dir, f)).find_all('element'):
                name = e.attrs.get('name')
                if name:
                    self.panels[name] = e

    # -- labels -----------------------------------------------------------
    def label(self, node):
        """The words a node shows, following Gaia's own fallback order."""
        if node is None:
            return None
        v = self.st.plain(node.attrs.get('data-l10n-id'), l10n_args(node))
        if v:
            return v
        # No plain string of its own: the visible words are in a child, which
        # is how every `...Section` aria-label row in Gaia is written.
        for k in node.kids:
            if isinstance(k, Node):
                if k.tag in ('small', 'button') or \
                        'desc' in k.attrs.get('class', ''):
                    continue
                v = self.label(k)
                if v:
                    return v
            elif isinstance(k, str) and k.strip():
                return clean(k)
        return None

    # -- one <li> ---------------------------------------------------------
    def row(self, li, heading=None):
        rng = li.first('input')
        if rng is not None and rng.attrs.get('type') == 'range':
            # A range has no text of its own -- the brightness slider is a bare
            # <input> between two icons.  Gaia names it with `aria-labelledby`
            # pointing at the section's <h2>, so follow that before falling
            # back to the heading the row sits under.
            by = self.ids.get(rng.attrs.get('aria-labelledby'))
            return {'kind': 'slider',
                    'title': self.label(li.first('p')) or self.label(by) or
                             self.label(li) or heading}

        sel = li.first('select')
        if sel is not None:
            options = []
            for o in sel.find_all('option'):
                t = self.label(o)
                if t:
                    options.append(t)
            title = self.label(li.first('p')) or self.label(li)
            if not title:
                return None
            r = {'kind': 'combo', 'title': title}
            if options:
                r['options'] = options
            return r

        sw = None
        for t in SWITCHES:
            sw = li.first(t)
            if sw is not None:
                break
        if sw is None:
            box = li.first('input')
            if box is not None and box.attrs.get('type') == 'checkbox':
                sw = box
        if sw is not None:
            title = self.label(sw.first('label')) or self.label(sw) or \
                self.label(li)
            if not title:
                return None
            # `checked` in the markup is the state Gaia ships the switch in.
            return {'kind': 'toggle', 'title': title,
                    'on': 'checked' in sw.attrs}

        a = li.first('a')
        if a is not None:
            title = self.label(a)
            if not title:
                return None
            r = {'kind': 'link', 'title': title}
            href = (a.attrs.get('href') or '').strip()
            if href.startswith('#') and len(href) > 1:
                r['route'] = href[1:]
            return r

        btn = li.first('button')
        if btn is not None:
            title = self.label(btn)
            return {'kind': 'button', 'title': title} if title else None

        title = self.label(li)
        if not title:
            return None
        # Two shapes are left, and about.html shows both side by side.  A row
        # that carries a runtime reading has an empty <small> waiting for it
        # (`<li><span data-l10n-id="model-name"></span><small
        # data-name="deviceinfo.product_model"></small></li>`) -- that is a
        # value.  A row without one is static prose
        # (`<li class="description"><p data-l10n-id="powerSave-explanation">`).
        if li.first('small') is not None:
            return {'kind': 'value', 'title': title}
        return {'kind': 'note', 'title': title}

    # -- one panel --------------------------------------------------------
    def screen(self, name, depth=0):
        if name in self.cache:
            return self.cache[name]
        el = self.panels.get(name)
        if el is None or name in self.stack:
            return None
        self.stack.append(name)
        outer_ids = self.ids
        self.ids = index_ids(el)
        title = self.label(el.first('h1')) or name
        rows, links = [], []
        heading = [None]
        tpl = el.first('template') or el

        def visit(node):
            for k in node.kids:
                if not isinstance(k, Node):
                    continue
                if k.tag == 'header':
                    t = self.label(k.first('h2'))
                    if t:
                        rows.append({'kind': 'heading', 'title': t})
                        heading[0] = t
                    continue
                if k.tag == 'ul':
                    for li in k.kids:
                        if isinstance(li, Node) and li.tag == 'li':
                            r = self.row(li, heading[0])
                            if r and r.get('title'):
                                rows.append(r)
                                if r.get('route'):
                                    links.append(r['route'])
                    continue
                if k.tag in ('gaia-header', 'panel', 'script', 'style',
                             'form', 'dialog'):
                    continue
                visit(k)

        visit(tpl)
        out = {'panel': name, 'title': title, 'rows': rows, 'subpages': []}
        self.cache[name] = out
        # Depth is bounded because a few panels link back into their own
        # family (call forwarding <-> call settings); the stack already stops
        # a cycle, this stops a very deep chain from exploding the tree.
        if depth < 3:
            for r in links:
                s = self.screen(r, depth + 1)
                if s:
                    out['subpages'].append(dict(s, route=r))
        self.stack.pop()
        self.ids = outer_ids
        return out


# --------------------------------------------------------------------- main

def count(rows):
    n = 0
    for r in rows:
        n += 1
        n += count(r.get('rows') or [])
    return n


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else '/tmp/gaia'
    out_path = sys.argv[2] if len(sys.argv) > 2 else '/tmp/gaia.json'

    st = Strings(root)
    w = Walker(root, st)
    top = w.panels.get('root')
    if top is None:
        sys.exit('no root element found under %s' % root)

    # The root panel *is* the sidebar: its <header><h2> runs are the groups the
    # simulator draws separators between, and each <li> is one sidebar item.
    sections, group = [], None
    w.ids = index_ids(top)
    tpl = top.first('template') or top

    def visit(node):
        nonlocal group
        for k in node.kids:
            if not isinstance(k, Node):
                continue
            if k.tag == 'header':
                t = w.label(k.first('h2'))
                if t:
                    group = t
                continue
            if k.tag == 'ul':
                for li in k.kids:
                    if not (isinstance(li, Node) and li.tag == 'li'):
                        continue
                    r = w.row(li)
                    if not r or not r.get('title'):
                        continue
                    entry = {'group': group, 'kind': r['kind'],
                             'title': r['title'], 'panel': r.get('route')}
                    if r['kind'] == 'toggle':
                        entry['on'] = r.get('on', False)
                    if r.get('route'):
                        s = w.screen(r['route'])
                        entry['rows'] = (s or {}).get('rows') or []
                        entry['subpages'] = (s or {}).get('subpages') or []
                        entry['screen'] = (s or {}).get('title') or r['title']
                    else:
                        entry['rows'] = []
                        entry['subpages'] = []
                        entry['screen'] = r['title']
                    sections.append(entry)
                continue
            if k.tag in ('gaia-header', 'panel', 'script', 'style', 'form'):
                continue
            visit(k)

    visit(tpl)

    json.dump({'sections': sections}, open(out_path, 'w', encoding='utf-8'),
              indent=1, ensure_ascii=False)

    nrow = sum(count(s['rows']) for s in sections)
    nrow += sum(count(p['rows']) for s in sections for p in s['subpages'])
    print('l10n strings     :', len(st.props))
    print('panels on disk   :', len(w.panels))
    print('sidebar items    :', len(sections))
    print('screens reached  :', len(w.cache))
    print('rows             :', nrow)
    if st.missing:
        print('unresolved keys  :', len(st.missing))
        for k in sorted(st.missing)[:20]:
            print('   ', k)
    print('->', out_path)


if __name__ == '__main__':
    main()
