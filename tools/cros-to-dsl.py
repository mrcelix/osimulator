#!/usr/bin/env python3
"""Turn the extracted ChromeOS settings tree into the simulator's DSL.

`cros-extract.py` produces a JSON tree whose every label came out of the
Chromium source.  This script renders that tree as the `CHROMEOS_TREE` literal
`index.html` consumes, and it is the only place where anything *not* from the
source is allowed in -- see the DeviceState class at the bottom of this file.

Usage:
    python3 cros-to-dsl.py chromeos124.json chromeos120.json > CHROMEOS_TREE.js
"""
import json
import re
import sys

# --------------------------------------------------------------- presentation

# ChromeOS names its sidebar icons after its own icon set; the simulator has
# its own small glyph set, so each one is mapped to the nearest glyph.  This is
# presentation only -- it cannot change which sections exist or what they say.
ICON = {
    'os-settings:network-wifi': 'network',
    'cr:bluetooth': 'bluetooth',
    'os-settings:connected-devices': 'cellular',
    'os-settings:multidevice-better-together-suite': 'cellular',
    'os-settings:account': 'users',
    'cr:person': 'users',
    'os-settings:auth-key': 'passcode',
    'os-settings:laptop-chromebook': 'desktop',
    'os-settings:personalization': 'appearance',
    'os-settings:paint-brush': 'appearance',
    'cr:security': 'privacy',
    'os-settings:apps': 'apps',
    'os-settings:accessibility-revamp': 'accessibility',
    'os-settings:accessibility': 'accessibility',
    'os-settings:system-preferences': 'gear',
    'os-settings:chrome': 'info',
    'cr:search': 'search',
    'os-settings:access-time': 'datetime',
    'os-settings:language': 'language',
    'os-settings:folder-outline': 'files',
    'os-settings:print': 'general',
    'os-settings:developer-tags': 'keyboard',
    'os-settings:restore': 'update',
}

# The sidebar id the simulator routes on.  Derived from the section's own URL
# path so it stays stable across releases.
def sid(section, path):
    return re.sub(r'[^a-z0-9]', '', (path or section).lower()) or \
        section.lower()


ACCENT = '#1a73e8'


# --------------------------------------------------------------- DSL emitters

# A GRIT message can carry a runtime placeholder: `$1` is the device's own
# name in most of these and a count in two of them.  What ChromeOS puts there
# is device state, so filling it is governed by the same rule as DeviceState
# below -- it changes no label, only the blank inside one.
PLACEHOLDERS = [
    ('$1 of $2 apps can send notifications',
     '3 of 24 apps can send notifications'),
    ('Browsing data $1', 'Browsing data'),
]


def fill_placeholders(s):
    for a, b in PLACEHOLDERS:
        s = s.replace(a, b)
    return re.sub(r'\$\d', 'Chromebook', s)


def q(s):
    """A JS single-quoted string."""
    s = (s or '')
    if '$' in s:
        s = fill_placeholders(s)
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
        sub = r.get('sub')
        o = []
        if sub:
            o.append('sub:' + q(sub))

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
            on = self.state.toggle(screen, title)
            return 'T(%s,%s%s)' % (q(title), 'true' if on else 'false',
                                   (',{' + ','.join(o) + '}') if o else '')

        if k == 'check':
            return 'CH(%s,false)' % q(title)

        if k == 'combo':
            if r.get('options'):
                return ('CHOICE', q(title), opts(r['options']))
            val = self.state.value(screen, title)
            if val:
                o.append('value:' + q(val))
            return 'L(%s%s)' % (q(title), (',{' + ','.join(o) + '}') if o else '')

        if k == 'slider':
            return ('SLIDER', q(title))

        if k == 'button':
            return 'B(%s)' % q(title)

        if k == 'note':
            return 'NOTE(%s)' % q(title)

        if k == 'input':
            return 'V(%s,%s)' % (q(title), q(self.state.value(screen, title)))

        return None

    # -- a run of rows into S(...) blocks ---------------------------------
    def blocks(self, rows, screen, header=None):
        """Emit S()/CHOICE() blocks for a flat list of rows.

        A `heading` row starts a new block, a `combo` with options and a
        `slider` each become their own block (the DSL renders those as
        headered sections), and everything else accumulates.
        """
        out, cur, cur_head = [], [], header

        def flush():
            nonlocal cur, cur_head
            if cur:
                o = (",{header:%s}" % q(cur_head)) if cur_head else ''
                out.append('S([%s]%s)' % (','.join(cur), o))
            cur, cur_head = [], None

        for r in rows:
            if r.get('kind') == 'group':
                flush()
                out.extend(self.blocks(r['rows'], screen, r.get('title')))
                continue
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
                out.append("S([SL(50,'general','general')],{header:%s})" % v[1])
                continue
            cur.append(v)
        flush()
        return out

    def detail(self, page):
        title = page.get('title')
        body = self.blocks(page.get('rows') or [], title)
        body += self.state.extra(title)
        if not body:
            return None
        return 'D(%s,[%s])' % (q(title), ','.join(body))


# ------------------------------------------------------------- device state

class DeviceState:
    """The one place a value that is NOT in the Chromium source may appear.

    Chromium's templates give the menu: every section, subpage, row label and
    sub-label above is the string ChromeOS itself ships.  What Chromium cannot
    give is the *state* of the machine -- which networks are in range, which
    Bluetooth accessories are paired, how much storage is used, what the build
    number is.  Those are filled from this table so a screen is not blank, and
    they are the only invented text in the tree.

    A rule this table obeys: it may set the value shown on the right of a row,
    the position of a switch, or append a clearly-marked list of hardware to a
    screen.  It may never add, rename or remove a row of the menu itself.
    """

    # screen title -> row label -> value on the right
    VALUES = {
        'Network': {'Wi-Fi': 'Home-5G', 'Mobile data': 'No network',
                    'VPN': 'Not connected'},
        'Bluetooth': {'Bluetooth': 'On'},
        'Device': {'Display': 'Built-in, 1920 x 1200'},
        'Storage management': {'Available storage': '42.1 GB'},
        'Time zone': {'Time zone': '(GMT+3:00) Istanbul'},
        'About ChromeOS': {'ChromeOS Version': '124.0.6367.201 (Official Build)'},
        'Detailed build information': {
            'ChromeOS Version': '124.0.6367.201 (Official Build) (64-bit)',
            'Platform': '15823.50.0 (Official Build) stable-channel volteer',
            'Firmware Version': 'Google_Volteer.13672.291.0',
            'Channel': 'Stable',
            'Device name': 'Chromebook',
        },
    }

    # switch positions: screen title -> row label -> on/off
    TOGGLES = {
        'Bluetooth': {'Bluetooth': True},
        'Privacy controls': {'Camera access': True, 'Microphone access': True,
                             'Location access': True},
    }

    # screens that would otherwise be blank because their whole content is a
    # runtime list; the appended block is labelled as hardware, not as menu.
    EXTRA = {
        'Network': ["S([L('Home-5G',{value:'Connected'}),"
                    "L('Cafe-Guest',{value:'Saved'})],"
                    "{header:'Wi-Fi networks in range'})"],
        'Bluetooth': ["S([L('Pixel Buds Pro',{value:'Connected'}),"
                      "L('Logitech MX Master 3S',{value:'Paired'})],"
                      "{header:'Paired accessories'})"],
        'Mouse': ["S([NOTE('ChromeOS builds this screen once per connected "
                  "mouse, so its controls exist only while one is plugged "
                  "in.')])"],
        'Touchpad': ["S([NOTE('ChromeOS builds this screen once per connected "
                     "touchpad, so its controls exist only on a device that "
                     "has one.')])"],
    }

    def __init__(self):
        # An extra block is written once even when a section and one of its
        # subpages share a title (Bluetooth / Bluetooth).
        self._done = set()

    def value(self, screen, label):
        return (self.VALUES.get(screen) or {}).get(label, '')

    def toggle(self, screen, label):
        return (self.TOGGLES.get(screen) or {}).get(label, False)

    def extra(self, screen):
        if screen in self._done:
            return []
        self._done.add(screen)
        return list(self.EXTRA.get(screen) or [])


# --------------------------------------------------------------------- main

def render(path, group_of):
    data = json.load(open(path, encoding='utf-8'))
    items = []
    for bucket in ('sections', 'advanced', 'about'):
        for s in data.get(bucket) or []:
            subpages = {p['route']: p for p in s['subpages'] if p.get('title')}
            em = Emitter(subpages, DeviceState())
            body = em.blocks(s['rows'], s['title'])
            # The hardware list belongs above the fallback block, where the
            # real screen shows it.
            body += em.state.extra(s['title'])
            # Subpages nobody linked to still exist in ChromeOS; keep them
            # reachable rather than silently dropping a whole screen.
            orphans = [p for r, p in subpages.items() if r not in em.used]
            if orphans:
                links = []
                for p in orphans:
                    d = em.detail(p)
                    links.append('L(%s%s)' % (q(p['title']),
                                              (',{detail:%s}' % d) if d else ''))
                body.append('S([%s],{header:%s})'
                            % (','.join(links), q('More in ' + s['title'])))
            if not body:
                body = ["S([NOTE('This screen is filled from the device at "
                        "runtime.')])"]
            items.append(
                "{id:%s,title:%s,icon:'%s',iconBg:'%s',group:'%s',detail:D(%s,[%s])}"
                % (q(sid(s['section'], s['path'])), q(s['title']),
                   ICON.get(s['icon'], 'gear'), ACCENT,
                   group_of(bucket), q(s['title']), ','.join(body)))
    return items


def main():
    m124, m120 = sys.argv[1], sys.argv[2]
    out = []
    out.append('/* ' + '=' * 74)
    out.append('   ChromeOS settings tree -- extracted from the Chromium source.')
    out.append('')
    out.append('   Generated by tools/cros-to-dsl.py from tools/cros-extract.py')
    out.append('   output, over the release tags 124.0.6367.201 and')
    out.append('   120.0.6099.315 of https://chromium.googlesource.com/chromium/src.')
    out.append('')
    out.append('   Every section, subpage, row label and sub-label is the string')
    out.append('   ChromeOS ships: the Polymer templates under')
    out.append('   chrome/browser/resources/ash/settings give the structure, the')
    out.append('   $i18n{} keys resolve through chrome/browser/ui/webui/ash/settings')
    out.append('   *_section.cc into IDS_ ids, and those resolve into English in')
    out.append('   the GRIT .grdp bundles under chrome/app.')
    out.append('')
    out.append('   124 and 120 differ because kOsSettingsRevampWayfinding is')
    out.append('   enabled by default at M124 and disabled at M120')
    out.append('   (ash/constants/ash_features.cc): the revamped build has a')
    out.append('   12-item menu and no Advanced section at all, the older one has')
    out.append('   an 11-item menu plus a six-item Advanced group.')
    out.append('')
    out.append('   Device state -- network names, paired accessories, build')
    out.append('   numbers, switch positions -- is NOT from the source and lives')
    out.append('   in the DeviceState table in tools/cros-to-dsl.py.')
    out.append('   ' + '=' * 74 + ' */')
    # The group is only a separator in the sidebar; it mirrors how the menu
    # itself is split.  M124 is one flat list, M120 is Basic / Advanced /
    # About ChromeOS, which is how os_settings_menu.html paints it.
    groups120 = {'sections': 'c1', 'advanced': 'c2', 'about': 'c3'}
    out.append('const CHROMEOS_TREE={')
    out.append(' 124:[' + ',\n  '.join(render(m124, lambda b: 'c1')) + ' ],')
    out.append(' 120:[' + ',\n  '.join(
        render(m120, lambda b: groups120[b])) + ' ]')
    out.append('};')
    sys.stdout.write('\n'.join(out) + '\n')


if __name__ == '__main__':
    main()
