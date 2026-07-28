#!/usr/bin/env python3
"""Turn the extracted webOS OSE settings tree into the simulator's DSL.

`webos-ose-extract.py` produces a JSON tree whose every label came out of the
Enact source of `webosose/com.webos.app.settings`.  This script renders that
tree as the `WEBOS_OSE_TREE` literal `index.html` consumes, and it is the only
place where anything *not* from the source is allowed in -- see the DeviceState
class at the bottom of this file.

Usage:
    python3 webos-ose-to-dsl.py webos-ose.json > WEBOS_OSE_TREE.js
"""
import json
import re
import sys

# --------------------------------------------------------------- presentation

# webOS OSE has exactly two top-level panels, so the icon map is short.  This
# is presentation only -- it cannot change which panels exist or what they say.
ICON = {
    'General': 'general',
    'Network': 'network',
}

# `@moon-accent: #cf0652` in src/style/main.module.less -- the app's own accent.
ACCENT = '#cf0652'


def sid(name):
    return re.sub(r'[^a-z0-9]', '', (name or '').lower()) or 'x'


# --------------------------------------------------------------- DSL emitters

def q(s):
    """A JS single-quoted string."""
    s = (s or '')
    s = s.replace('\\', '\\\\').replace("'", "\\'")
    s = s.replace('\n', ' ').replace('\r', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    return "'" + s + "'"


def opts(o):
    return '[' + ','.join(q(x) for x in o) + ']'


class Emitter:
    def __init__(self, subpages, state):
        # route -> subpage, so a row can carry the screen it opens.
        self.subpages = subpages
        self.state = state
        self.used = set()

    def _detail_of(self, route):
        if route and route in self.subpages and route not in self.used:
            self.used.add(route)
            return self.detail(self.subpages[route])
        return None

    # -- one row ----------------------------------------------------------
    def row(self, r, screen):
        k = r.get('kind')
        title = r.get('title')
        if not title:
            return None
        o = []

        # A row whose `label=` names both outcomes -- `label={connected ?
        # $L('Connected to Internet') : $L('Not Connected')}` -- shows one of
        # them depending on the box; which one is device state.
        if r.get('states'):
            o.append('value:' + q(self.state.pick(screen, title, r['states'])))
        elif r.get('runtime') and k in ('value', 'input'):
            pass                       # filled below, as the row's own value

        if k in ('link', 'button') and r.get('route'):
            # webOS draws a few of these as `<Button>` rather than an item, but
            # pressing them opens a screen, so they render as a row you can
            # follow -- otherwise a whole panel would be unreachable.
            det = self._detail_of(r['route'])
            if det:
                o.append('detail:' + det)
            return 'L(%s%s)' % (q(title), (',{' + ','.join(o) + '}') if o else '')

        if k == 'link':
            val = self.state.value(screen, title)
            if val and not r.get('states'):
                o.append('value:' + q(val))
            return 'L(%s%s)' % (q(title), (',{' + ','.join(o) + '}') if o else '')

        if k == 'toggle':
            on = self.state.toggle(screen, title, r.get('on', False))
            return 'T(%s,%s)' % (q(title), 'true' if on else 'false')

        if k == 'combo':
            if r.get('options'):
                return ('CHOICE', q(title), opts(r['options']))
            return 'L(%s)' % q(title)

        if k == 'button':
            return 'B(%s)' % q(title)

        if k == 'note':
            return 'NOTE(%s)' % q(title)

        if k in ('value', 'input'):
            # Both are slots webOS fills from the box: a reading on the right,
            # or an empty field waiting to be typed into.
            return 'V(%s,%s)' % (q(title), q(self.state.value(screen, title)))

        return None

    # -- a run of rows into S(...) blocks ---------------------------------
    def blocks(self, rows, screen, header=None):
        out, cur, cur_head = [], [], header

        def flush():
            nonlocal cur, cur_head
            if cur:
                o = (",{header:%s}" % q(cur_head)) if cur_head else ''
                out.append('S([%s]%s)' % (','.join(cur), o))
            cur, cur_head = [], None

        for r in rows:
            if r.get('kind') == 'heading':
                flush()
                cur_head = r.get('title')
                continue
            v = self.row(r, screen)
            if v is None:
                continue
            if isinstance(v, tuple) and v[0] == 'CHOICE':
                flush()
                out.append('CHOICE(%s,%s,0)' % (v[1], v[2]))
                continue
            cur.append(v)
        flush()
        return out

    def detail(self, page):
        title = page.get('title')
        body = self.blocks(page.get('rows') or [], title)
        body += self.state.extra(title)
        if not body:
            body = [self.state.runtime_note(title)]
        return 'D(%s,[%s])' % (q(title), ','.join(body))


# ------------------------------------------------------------- device state

class DeviceState:
    """The one place a value that is NOT in the webOS OSE source may appear.

    The Enact source gives the menu: every panel, screen, row label and
    dropdown choice above is the string webOS OSE itself ships, because Enact's
    `$L()` keeps the English literal in the call.  What the source cannot give
    is the *state* of the box -- its device name, its build string, its MAC
    addresses, which networks are in range.  Those slots are `$L('Loading...')`
    in source and are filled from this table instead, so a screen is not blank.

    The rule the other emitters obey applies here too: this table may set the
    value shown on the right of a row, the position of a switch, or append a
    clearly-marked list of hardware.  It may never add, rename or remove a row
    of the menu itself.
    """

    # screen title -> row label -> value on the right
    VALUES = {
        'Network': {'Device Name': 'webOS-OSE'},
        'System Information': {
            'Device Name': 'webOS-OSE',
            'Software Version': 'webOS OSE 2.24.0',
            'MAC Address (Wired)': 'a4:5e:60:c2:19:04',
            'MAC Address (Wireless)': 'a4:5e:60:c2:19:05',
        },
        'Wired Connection (Ethernet)': {
            'IP Address': '192.168.1.42', 'Subnet Mask': '255.255.255.0',
            'Gateway': '192.168.1.1', 'DNS Server': '192.168.1.1',
            'MAC Address': 'a4:5e:60:c2:19:04',
        },
        'Advanced': {
            'IP Address': '192.168.1.77', 'Subnet Mask': '255.255.255.0',
            'Gateway': '192.168.1.1', 'DNS Server': '8.8.8.8',
            'MAC Address': 'a4:5e:60:c2:19:05',
        },
        # The two edit forms open pre-filled with what the box is using; the
        # Add Network / Wi-Fi Security forms are blank on purpose, because
        # that is how they open.
        'Wired Edit': {
            'IP Address': '192.168.1.42', 'Subnet Mask': '255.255.255.0',
            'Gateway': '192.168.1.1', 'DNS Server': '192.168.1.1',
        },
        'Edit': {
            'IP Address': '192.168.1.77', 'Subnet Mask': '255.255.255.0',
            'Gateway': '192.168.1.1', 'DNS Server': '8.8.8.8',
        },
        'Time & Date': {'Time': '21:40', 'Date': '24.07.2026',
                        'Region': 'Türkiye', 'TimeZone': 'Europe/Istanbul'},
        'Language': {'Menu Language': 'English', 'Keyboard Languages': 'English'},
    }

    # which of the two states a `label={a ? $L(x) : $L(y)}` row shows
    STATES = {
        'Network': {'Wired Connection (Ethernet)': 'Connected to Internet',
                    'Wi-Fi Connection': 'Not Connected'},
    }

    TOGGLES = {}

    # screens whose whole content is a live list; the appended block is
    # labelled as what the box found, never as menu.
    EXTRA = {
        'Wi-Fi Connection': ["S([L('Home-5G',{value:'Secured'}),"
                             "L('Cafe-Guest',{value:'Open'})],"
                             "{header:'Networks in range'})"],
    }

    # Screens webOS OSE builds entirely from a VirtualList of live data, so
    # there is no menu in the source at all -- say so rather than inventing one.
    RUNTIME = {
        'Menu Language': 'webOS OSE builds this screen from the language '
                         'packs installed on the box, so it has no fixed rows.',
        'Keyboard Languages': 'webOS OSE builds this screen from the keyboard '
                              'layouts installed on the box, so it has no '
                              'fixed rows.',
    }

    DEFAULT_RUNTIME = 'webOS OSE fills this screen from the device at runtime.'

    def __init__(self):
        self._done = set()

    def value(self, screen, label):
        return (self.VALUES.get(screen) or {}).get(label, '')

    def pick(self, screen, label, states):
        v = (self.STATES.get(screen) or {}).get(label)
        return v if v in states else states[0]

    def toggle(self, screen, label, shipped):
        return (self.TOGGLES.get(screen) or {}).get(label, shipped)

    def extra(self, screen):
        if screen in self._done:
            return []
        self._done.add(screen)
        return list(self.EXTRA.get(screen) or [])

    def runtime_note(self, screen):
        return 'S([NOTE(%s)])' % q(self.RUNTIME.get(screen,
                                                    self.DEFAULT_RUNTIME))


# --------------------------------------------------------------------- main

def render(path):
    data = json.load(open(path, encoding='utf-8'))
    items = []
    for s in data['sections']:
        state = DeviceState()
        subpages = {p['route']: p for p in s['subpages'] if p.get('route')}
        em = Emitter(subpages, state)
        screen = s.get('screen') or s['title']
        body = em.blocks(s['rows'], screen)
        body += state.extra(screen)
        # A screen the panelMap declares but no row links to still exists in
        # the app; keep it reachable rather than dropping it.
        orphans = [p for r, p in subpages.items() if r not in em.used]
        if orphans:
            links = ['L(%s,{detail:%s})' % (q(p['title']), em.detail(p))
                     for p in orphans]
            body.append('S([%s],{header:%s})'
                        % (','.join(links), q('More in ' + s['title'])))
        if not body:
            body = [state.runtime_note(screen)]
        items.append(
            "{id:%s,title:%s,icon:'%s',iconBg:'%s',group:'w1',detail:D(%s,[%s])}"
            % (q(sid(s['title'])), q(s['title']), ICON.get(s['title'], 'gear'),
               ACCENT, q(screen), ','.join(body)))
    return items


def main():
    out = []
    out.append('/* ' + '=' * 74)
    out.append('   webOS OSE settings tree -- extracted from the webOS OSE source.')
    out.append('')
    out.append('   Generated by tools/webos-ose-to-dsl.py from')
    out.append('   tools/webos-ose-extract.py output, over')
    out.append('   https://github.com/webosose/com.webos.app.settings')
    out.append('   (app version 1.1.0; the panel graph is identical across the')
    out.append('   submissions/20, /25, /30 and /37 tags, so there is one')
    out.append('   version here rather than two).')
    out.append('')
    out.append('   Every panel, screen, row label and dropdown choice is the')
    out.append('   string the app ships: src/views/MainPanels.js holds the')
    out.append('   top-level panelMap, each <X>Panel.js holds the screen graph,')
    out.append('   a row is one JSX element, and Enact\'s $L() keeps the English')
    out.append('   literal in the call.')
    out.append('')
    out.append('   webOS OSE is the Open Source Edition -- a two-panel Settings')
    out.append('   app for developer boards and embedded devices. It is NOT the')
    out.append('   closed webOS that ships on LG televisions, which the')
    out.append('   simulator carries separately as "LG webOS".')
    out.append('')
    out.append('   Device state -- device name, build string, MAC and IP')
    out.append('   addresses, networks in range, connection status -- is NOT')
    out.append('   from the source and lives in the DeviceState table in')
    out.append('   tools/webos-ose-to-dsl.py.')
    out.append('   ' + '=' * 74 + ' */')
    out.append('const WEBOS_OSE_TREE=[' +
               ',\n  '.join(render(sys.argv[1])) + ' ];')
    sys.stdout.write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
