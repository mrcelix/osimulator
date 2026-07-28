#!/usr/bin/env python3
"""Turn the extracted Gaia (Firefox OS) settings tree into the simulator's DSL.

`gaia-extract.py` produces a JSON tree whose every label came out of Gaia's own
`apps/settings/elements/*.html` fragments and `*.en-US.properties` bundles.
This script renders that tree as the `GAIA_TREE` literal `index.html` consumes,
and it is the only place where anything *not* from the source is allowed in --
see the DeviceState class at the bottom of this file.

Usage:
    python3 gaia-to-dsl.py gaia25.json gaia22.json > GAIA_TREE.js
"""
import json
import re
import sys

# --------------------------------------------------------------- presentation

# Gaia draws its sidebar icons from its own sprite sheet; the simulator has a
# small glyph set of its own, so each row is mapped to the nearest glyph.  This
# is presentation only -- it cannot change which sections exist or what they
# say.  Keys are the English row labels the extractor produced.
ICON = {
    'Airplane Mode': 'airplane',
    'Geolocation': 'location',
    'Wi-Fi': 'wifi',
    'SIM Manager': 'cellular',
    'Call Settings': 'message',
    'Messaging Settings': 'message',
    'Cellular & Data': 'cellular',
    'Bluetooth': 'bluetooth',
    'NFC': 'network',
    'Internet Sharing': 'network',
    'Sound': 'sounds',
    'Display': 'display',
    'Home Screens': 'homescreen',
    'Homescreen': 'homescreen',
    'Homescreens': 'homescreen',
    'Search': 'search',
    'Navigation': 'maps',
    'Notifications': 'notifications',
    'Date & Time': 'datetime',
    'Language': 'language',
    'Keyboards': 'keyboard',
    'Themes': 'appearance',
    'Add-ons': 'apps',
    'Achievements': 'gamepad',
    'Firefox Accounts': 'personcircle',
    'Find My Device': 'location',
    'Screen Lock': 'passcode',
    'SIM Security': 'passcode',
    'App Permissions': 'privacy',
    'Privacy Controls': 'privacy',
    'Do Not Track': 'privacy',
    'Browsing Privacy': 'safari',
    'USB Storage': 'storage',
    'Media Storage': 'storage',
    'Application Storage': 'storage',
    'Device Information': 'info',
    'Downloads': 'files',
    'Battery': 'battery',
    'Accessibility': 'accessibility',
    'Developer': 'pencil',
    'Improve Firefox OS': 'info',
    'Help': 'info',
}

# A slider is drawn between two glyphs; which pair reads right depends on what
# the slider controls.  Presentation only.
SLIDER_GLYPH = {
    'Brightness': 'display',
    'Media': 'sounds',
    'Ringtones & Notifications': 'sounds',
    'Alarm': 'sounds',
}

ACCENT = '#00caf2'          # Firefox OS system blue


def sid(item):
    """The sidebar id the simulator routes on.

    Derived from Gaia's own panel name (`href="#wifi"`) so it stays stable
    across the two releases; sections with no panel fall back to the label.
    """
    base = item.get('panel') or item.get('title') or ''
    return re.sub(r'[^a-z0-9]', '', base.lower()) or 'x'


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
        # route -> subpage, so a link row can carry the screen it opens.
        self.subpages = subpages
        self.state = state
        self.used = set()

    # -- one row ----------------------------------------------------------
    def row(self, r, screen):
        k = r.get('kind')
        title = r.get('title')
        if not title:
            return None
        o = []

        if k == 'link':
            route = r.get('route')
            val = self.state.value(screen, title)
            if val:
                o.append('value:' + q(val))
            det = None
            if route and route in self.subpages and route not in self.used:
                self.used.add(route)
                det = self.detail(self.subpages[route])
            if det:
                o.append('detail:' + det)
            return 'L(%s%s)' % (q(title), (',{' + ','.join(o) + '}') if o else '')

        if k == 'toggle':
            # Gaia's markup carries the switch's shipped position in `checked`;
            # the extractor kept it, and DeviceState may override it for a
            # radio the simulated handset has turned on.
            on = self.state.toggle(screen, title, r.get('on', False))
            return 'T(%s,%s)' % (q(title), 'true' if on else 'false')

        if k == 'combo':
            if r.get('options'):
                return ('CHOICE', q(title), opts(r['options']))
            val = self.state.value(screen, title)
            if val:
                o.append('value:' + q(val))
            return 'L(%s%s)' % (q(title), (',{' + ','.join(o) + '}') if o else '')

        if k == 'slider':
            return ('SLIDER', q(title), SLIDER_GLYPH.get(title, 'general'))

        if k == 'button':
            return 'B(%s)' % q(title)

        if k == 'note':
            return 'NOTE(%s)' % q(title)

        if k == 'value':
            # A `value` row is one Gaia leaves an empty <small> in for the
            # device to fill; the right-hand text is device state.
            return 'V(%s,%s)' % (q(title), q(self.state.value(screen, title)))

        return None

    # -- a run of rows into S(...) blocks ---------------------------------
    def blocks(self, rows, screen, header=None):
        """Emit S()/CHOICE() blocks for a flat list of rows.

        A `heading` row starts a new block -- that is exactly what Gaia's
        `<header><h2>` does inside a panel -- and a `combo` carrying its own
        `<option>` list or a slider each become their own headered block,
        because that is how the DSL renders them.
        """
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
            if isinstance(v, tuple) and v[0] == 'SLIDER':
                flush()
                out.append("S([SL(50,'%s','%s')],{header:%s})"
                           % (v[2], v[2], v[1]))
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
    """The one place a value that is NOT in the Gaia source may appear.

    Gaia's markup gives the menu: every panel, row label, heading, switch and
    `<option>` above is the string Firefox OS itself ships.  What the markup
    cannot give is the *state* of the handset -- its phone number, its build
    string, how much storage is free, which networks are in range.  Gaia leaves
    an empty `<small>` for each of those and fills it at runtime; this table
    fills them instead, and they are the only invented text in the tree.

    The same rule the other emitters obey applies here: this table may set the
    value shown on the right of a row, the position of a switch, or append a
    clearly-marked list of hardware.  It may never add, rename or remove a row
    of the menu itself.
    """

    # screen title -> row label -> value on the right
    VALUES = {
        'Cellular & Data': {'Operator': 'Turkcell'},
        'Manage Networks': {'MAC Address': '9c:4f:da:31:0b:77'},
        'Device Information': {
            'Phone Number': '+90 532 000 00 00',
            'Model': 'ZTE Open C',
            'Software': 'Boot2Gecko 2.5.0.0-prerelease',
            'Last Updated': '2016-03-08',
        },
        'More Information': {
            'Model': 'ZTE Open C',
            'Software': 'Boot2Gecko 2.5.0.0-prerelease',
            'Hardware Revision': 'P821A10-ENG',
            'MAC Address': '9c:4f:da:31:0b:77',
            'Bluetooth Address': '9c:4f:da:31:0b:78',
            'IMEI': '35 209900 176148 1',
            'ICCID': '8990 0101 2345 6789 012',
            'Platform Version': '44.0',
            'Build Identifier': '20160308064126',
            'Build Number': '20160308064126',
            'Update Channel': 'release',
            'Git Commit Info': 'gaia 885647d / gecko 44.0',
        },
        'Application Storage': {'Total Space': '3.5 GB', 'Used': '1.1 GB',
                                'Left': '2.4 GB'},
        'Battery': {'Current Level': '68%'},
        'Firefox Accounts': {'Signed in as': 'john.wick@example.com'},
    }

    # switch positions: screen title -> row label -> on/off.  Anything not
    # named here keeps the position Gaia's own markup ships.
    TOGGLES = {
        'Wi-Fi': {'Wi-Fi': True},
        'Bluetooth': {'Bluetooth': True},
        'Cellular & Data': {'Data Connection': True},
    }

    # screens that would otherwise be blank because their whole content is a
    # runtime list; the appended block is labelled as hardware or as user data,
    # never as menu.
    EXTRA = {
        'Wi-Fi': ["S([L('Home-5G',{value:'Connected'}),"
                  "L('Cafe-Guest',{value:'Secured'})],"
                  "{header:'Networks in range'})"],
        'Bluetooth': ["S([L('Jabra Talk 45',{value:'Paired'})],"
                      "{header:'Paired devices'})"],
    }

    # Gaia builds these screens entirely from what is on the device, so there
    # is no menu to show -- say so rather than leaving a blank screen.
    RUNTIME = {
        'Themes': 'Firefox OS lists the themes installed on the handset here, '
                  'so this screen has no fixed rows.',
        'Achievements': 'This screen lists the achievements the handset has '
                        'earned, so it is empty until the device fills it.',
        'App Permissions': 'Firefox OS builds one row per installed app here, '
                           'so this screen has no fixed rows.',
        'Downloads': 'This screen lists the files already downloaded on the '
                     'handset, so it is empty until the device fills it.',
    }

    DEFAULT_RUNTIME = 'Firefox OS fills this screen from the device at runtime.'

    def __init__(self):
        # An extra block is written once even when a section and one of its
        # subpages share a title.
        self._done = set()

    def value(self, screen, label):
        return (self.VALUES.get(screen) or {}).get(label, '')

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
    items, groups = [], {}
    for s in data['sections']:
        g = s.get('group') or ''
        if g not in groups:
            groups[g] = 'f%d' % (len(groups) + 1)
        icon = ICON.get(s['title'], 'gear')
        head = "{id:%s,title:%s,icon:'%s',iconBg:'%s',group:'%s'" % (
            q(sid(s)), q(s['title']), icon, ACCENT, groups[g])

        # A sidebar row that is itself a switch -- Airplane Mode, Geolocation
        # and NFC are `<gaia-switch>` in root.html and open no panel at all.
        if s['kind'] == 'toggle':
            items.append(head + ',toggle:%s}' % ('true' if s.get('on') else
                                                 'false'))
            continue

        state = DeviceState()
        subpages = {p['route']: p for p in s['subpages'] if p.get('route')}
        em = Emitter(subpages, state)
        screen = s.get('screen') or s['title']
        body = em.blocks(s['rows'], screen)
        body += state.extra(screen)
        # A panel Gaia reaches by script rather than by `href` still exists;
        # keep it reachable rather than silently dropping a whole screen.
        orphans = [p for r, p in subpages.items() if r not in em.used]
        if orphans:
            links = ['L(%s,{detail:%s})' % (q(p['title']), em.detail(p))
                     for p in orphans]
            body.append('S([%s],{header:%s})'
                        % (','.join(links), q('More in ' + s['title'])))
        if not body:
            body = [state.runtime_note(screen)]
        items.append(head + ',detail:D(%s,[%s])}' % (q(screen), ','.join(body)))
    return items


def main():
    v25, v22 = sys.argv[1], sys.argv[2]
    out = []
    out.append('/* ' + '=' * 74)
    out.append('   Firefox OS (Gaia) settings tree -- extracted from the Gaia source.')
    out.append('')
    out.append('   Generated by tools/gaia-to-dsl.py from tools/gaia-extract.py')
    out.append('   output, over the v2.5 and v2.2 branches of')
    out.append('   https://github.com/mozilla-b2g/gaia.')
    out.append('')
    out.append('   Every sidebar row, panel, heading, switch and <option> is the')
    out.append('   string Firefox OS ships: apps/settings/elements/*.html gives')
    out.append('   the structure -- elements/root.html *is* the sidebar -- and')
    out.append('   each data-l10n-id resolves into English through')
    out.append('   apps/settings/locales/settings.en-US.properties, the')
    out.append('   locales/device_type/phone overlay that names the device')
    out.append('   ("Reset Phone"), and the shared/locales bundles.')
    out.append('')
    out.append('   2.5 and 2.2 differ in the menu itself: 2.5 has Home Screens,')
    out.append('   Add-ons and Achievements, 2.2 has Homescreen, Homescreens and')
    out.append('   Privacy Controls instead.')
    out.append('')
    out.append('   This is upstream Gaia, not a vendor build. KaiOS forked Gaia')
    out.append('   2.5 and its own tree is not public, so KaiOS handsets differ')
    out.append('   from what is shown here.')
    out.append('')
    out.append('   Device state -- phone number, build strings, storage figures,')
    out.append('   networks in range, switch positions -- is NOT from the source')
    out.append('   and lives in the DeviceState table in tools/gaia-to-dsl.py.')
    out.append('   ' + '=' * 74 + ' */')
    out.append('const GAIA_TREE={')
    out.append(' 25:[' + ',\n  '.join(render(v25)) + ' ],')
    out.append(' 22:[' + ',\n  '.join(render(v22)) + ' ]')
    out.append('};')
    sys.stdout.write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
