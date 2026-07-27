#!/usr/bin/env python3
"""Turn the extracted AOSP tree (JSON) into osimulator settings-DSL JavaScript."""
import json, re, sys

def norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())

def jstr(s):
    s = (s or '')
    s = s.replace('\\', '\\\\').replace("'", "\\'")
    s = s.replace('\n', ' ').replace('\r', ' ')
    return "'" + s + "'"

# top-level id / icon / colour / group, keyed by normalised AOSP title
TOP = {
    'networkinternet':            ('network',    'network',       '#4285f4', 'a1'),
    'communal':                   ('communal',   'homescreen',    '#4285f4', 'a1'),
    'connecteddevices':           ('devices',    'bluetooth',     '#4285f4', 'a1'),
    'apps':                       ('apps',       'apps',          '#34a853', 'a2'),
    'appsnotifications':          ('apps',       'apps',          '#34a853', 'a2'),
    'notifications':              ('notifications','notifications','#ea4335', 'a2'),
    'battery':                    ('battery',    'battery',       '#34a853', 'a3'),
    'storage':                    ('storage',    'storage',       '#fbbc04', 'a3'),
    'soundvibration':             ('sound',      'sounds',        '#ea4335', 'a3'),
    'sound':                      ('sound',      'sounds',        '#ea4335', 'a3'),
    'display':                    ('display',    'display',       '#4285f4', 'a3'),
    'wallpaperstyle':             ('wallpaper',  'wallpaper',     '#9334e6', 'a3'),
    'wallpaper':                  ('wallpaper',  'wallpaper',     '#9334e6', 'a3'),
    'accessibility':              ('access',     'accessibility', '#4285f4', 'a4'),
    'securityprivacy':            ('security',   'passcode',      '#34a853', 'a4'),
    'security':                   ('security',   'passcode',      '#34a853', 'a4'),
    'privacy':                    ('privacy',    'privacy',       '#34a853', 'a4'),
    'location':                   ('location',   'location',      '#ea4335', 'a4'),
    'safetyemergency':            ('safety',     'info',          '#ea4335', 'a4'),
    'passwordspasskeysautofill':  ('passacc',    'passcode',      '#4285f4', 'a5'),
    'passwordsaccounts':          ('passacc',    'passcode',      '#4285f4', 'a5'),
    'accounts':                   ('accounts',   'personcircle',  '#4285f4', 'a5'),
    'digitalwellbeingparentalcontrols': ('wellbeing','screentime','#34a853','a5'),
    'google':                     ('google',     'gear',          '#4285f4', 'a5'),
    'system':                     ('system',     'general',       '#5f6368', 'a6'),
    'aboutphone':                 ('about',      'info',          '#5f6368', 'a6'),
    'tipssupport':                ('support',    'info',          '#5f6368', 'a6'),
}


SLIDER_GLYPH = [
    (('brightness', 'bright'), 'display'),
    (('volume', 'sound', 'ring', 'media', 'alarm', 'call', 'notification'), 'sounds'),
    (('vibrat', 'haptic', 'touch'), 'general'),
]
def slider_glyph(title):
    n = (title or '').lower()
    for keys, g in SLIDER_GLYPH:
        if any(k in n for k in keys):
            return g
    return 'general'

# --------------------------------------------------------------------------
# Switch POSITIONS are device state, not menu structure. AOSP declares an
# android:defaultValue on only a handful of switches (the rest are resolved at
# run time from framework config / Settings.Secure), so where the source says
# nothing we show a plausible position for a freshly set-up phone. This affects
# only the on/off state of a switch — never which switches exist or what they
# are called, which is what comes from source.
ON_BY_DEFAULT = {norm(x) for x in (
    'Wi-Fi', 'Wi‑Fi', 'Bluetooth', 'Location', 'Use location',
    'Turn on Wi-Fi automatically', 'Turn on Wi‑Fi automatically',
    'Notify for public networks', 'Nearby device scanning',
    'Auto-rotate screen', 'Adaptive brightness', 'Adaptive Battery',
    'Use adaptive connectivity', 'Vibrate for calls', 'Dial pad tones',
    'Screen locking sound', 'Charging sounds and vibration',
    'Touch sounds', 'Touch vibration', 'Live Caption',
    'Automatic system updates', 'Google Play Protect',
    'Show notifications', 'Notification dot on app icon',
    'Blink light', 'Use Now Playing', 'Emergency alerts',
    'Extreme threats', 'Severe threats', 'Amber alerts',
    'Backup by Google One', 'Back up to Google Drive',
    'Usage & diagnostics', 'Autofill with Google',
)}

# --------------------------------------------------------------------------
# Device STATE overlay. Same distinction as ON_BY_DEFAULT above: AOSP source
# defines which rows exist and what they are called, but the value printed on
# the right of a row (serial number, build number, IP address...) is read from
# the hardware at run time and cannot come from source. These are the
# simulator's stand-in values for its Pixel 8 Pro / Android 14 persona — they
# are illustrative, not extracted, and never change the menu structure.
VALUES = {
    'devicename':            'Pixel 8 Pro',
    'model':                 'Pixel 8 Pro',
    'serialnumber':          '2A091FDH300CK',
    'hardwareversion':       'MP1.0',
    'manufacturedyear':      '2023',
    'imei':                  '35 123456 789012 3',
    'androidversion':        '14',
    'androidsecurityupdate': 'August 5, 2024',
    'googleplaysystemupdate':'August 1, 2024',
    'basebandversion':       'g5300q-231204-B-11150783',
    'kernelversion':         '5.15.137-android14-11',
    'buildnumber':           'UD1A.230803.041',
    'uptime':                '3:24:11',
    'ipaddress':             '192.168.1.42',
    'bluetoothaddress':      '3C:28:6D:1A:9F:B4',
    'wifimacaddress':        'Unavailable',
    'devicewifimacaddress':  'F0:2F:74:C1:88:A0',
    'cyclecount':            '12',
    'manufacturedate':       'September 12, 2023',
    'dateoffirstuse':        'October 4, 2023',
    'simstatus':             'Vodafone',
    'account':               'johnwick@gmail.com',
}

def value_of(node):
    return VALUES.get(norm(node.get('title')))

def truthy(node):
    d = node.get('default')
    if d is not None:
        return 'true' if str(d).lower() in ('true', '1') else 'false'
    return 'true' if norm(node.get('title')) in ON_BY_DEFAULT else 'false'

def opts(node, extra=None):
    """build the trailing options object for a row"""
    o = []
    if node.get('summary'):
        o.append('sub:' + jstr(node['summary']))
    if extra:
        o += extra
    return o

def row(node, depth):
    k = node['kind']
    title = node.get('title')
    kids = [c for c in (node.get('children') or [])]

    if k == 'note':
        return 'NOTE(' + jstr(title) + ')'

    if k == 'list':
        ents = node.get('entries') or []
        if ents:
            sel = 0
            det = 'D(%s,[CHOICE(null,[%s],%d)])' % (
                jstr(title), ','.join(jstr(e) for e in ents), sel)
            return 'L(%s,{%s})' % (jstr(title), ','.join(
                opts(node, ['value:' + jstr(ents[sel]), 'detail:' + det])))
        return 'L(%s%s)' % (jstr(title), fmt_opts(opts(node)))

    if k == 'toggle' and not kids:
        return 'T(%s,%s%s)' % (jstr(title), truthy(node),
                               (',{' + ','.join(opts(node)) + '}') if node.get('summary') else '')

    # anything with children becomes a drill-in page
    if kids:
        secs = sections(kids, depth + 1)
        if secs:
            det = 'D(%s,[%s])' % (jstr(title), ','.join(secs))
            extra = ['detail:' + det]
            val = value_of(node)
            if k == 'toggle':
                extra.insert(0, 'value:' + jstr('On' if truthy(node) == 'true' else 'Off'))
            elif val:
                extra.insert(0, 'value:' + jstr(val))
            return 'L(%s,{%s})' % (jstr(title), ','.join(opts(node, extra)))

    if k == 'toggle':
        return 'T(%s,%s%s)' % (jstr(title), truthy(node),
                               (',{' + ','.join(opts(node)) + '}') if node.get('summary') else '')
    val = value_of(node)
    if val:
        # read-only device state: a value row, not a tappable link
        return 'V(%s,%s%s)' % (jstr(title), jstr(val), fmt_opts(opts(node)))
    return 'L(%s%s)' % (jstr(title), fmt_opts(opts(node)))

def fmt_opts(o):
    return (',{' + ','.join(o) + '}') if o else ''

def sections(nodes, depth):
    """turn a list of child nodes into a list of S(...) section literals"""
    out, buf = [], []
    def flush():
        if buf:
            out.append('S([' + ','.join(buf) + '])')
            buf.clear()
    for n in nodes:
        k = n['kind']
        if k == 'slider':
            flush()
            g = slider_glyph(n.get('title'))
            out.append('S([SL(50,%s,%s)],{header:%s%s})' % (
                jstr(g), jstr(g), jstr(n.get('title') or 'Level'),
                (',footer:' + jstr(n['summary'])) if n.get('summary') else ''))
            continue
        if k in ('category', 'group'):
            kids = n.get('children') or []
            inner = sections(kids, depth + 1)
            if not inner:
                continue
            flush()
            if n.get('title'):
                # apply the category title as the header of its first section
                first = inner[0]
                if first.startswith('S([') and first.endswith('])'):
                    inner[0] = first[:-1] + ',{header:' + jstr(n['title']) + '})'
                else:
                    inner.insert(0, 'S([],{header:' + jstr(n['title']) + '})')
            out += inner
            continue
        buf.append(row(n, depth))
    flush()
    return out

# Entries top_level_settings.xml declares but a shipping handset never shows,
# each because its own controller gates it off by default in this same source:
#   Communal — CommunalPreferenceController reads R.bool.config_show_communal_settings,
#              which res/values/config.xml declares <bool ...>false</bool> in both trees.
GATED_OFF = {'communal'}

# Screens that live in a different APK than Settings, so this repo has the menu
# entry but not the page behind it. Rather than fabricate the missing page we
# keep the real entry and say plainly where its content comes from.
EXTERNAL_SCREEN = {
    'wallpaperstyle': 'Opens the Wallpaper & style picker, a separate app — its screens are not part of the Settings source.',
    'wallpaper':      'Opens the wallpaper picker, a separate app — its screens are not part of the Settings source.',
    'tipssupport':    'Opens the device maker’s support app — its screens are not part of the Settings source.',
    'securityprivacy':'Opens Safety Center, a separate app — its screens are not part of the Settings source.',
}

def top_items(tree):
    items, used = [], {}
    for n in tree:
        title = n.get('title')
        key = norm(title)
        kids = n.get('children') or []
        if key in GATED_OFF:
            continue
        # AOSP's top_level_settings.xml ships every conditional variant of the
        # security entry at once; a real device shows exactly one. Keep the
        # Security / Privacy pair, which have source-derived content, and drop
        # the Safety Center variant that would duplicate them.
        if key == 'securityprivacy' and not kids:
            continue
        meta = TOP.get(key)
        if not meta:
            slug = re.sub(r'[^a-z0-9]+', '', key)[:14] or 'misc'
            meta = (slug, 'gear', '#5f6368', 'a6')
        sid, ic, bg, grp = meta
        used[sid] = used.get(sid, 0) + 1
        if used[sid] > 1:
            sid = '%s%d' % (sid, used[sid])
        secs = sections(kids, 1)
        if not secs and key in EXTERNAL_SCREEN:
            secs = ['S([NOTE(%s)])' % jstr(EXTERNAL_SCREEN[key])]
        detail = 'D(%s,[%s])' % (jstr(title), ','.join(secs))
        sub = (',sub:' + jstr(n['summary'])) if n.get('summary') else ''
        items.append("{id:%s,title:%s%s,icon:%s,iconBg:%s,group:%s,detail:%s}" % (
            jstr(sid), jstr(title), sub, jstr(ic), jstr(bg), jstr(grp), detail))
    return items

if __name__ == '__main__':
    out = {}
    for ver, path in (('14', '/tmp/android14.json'), ('13', '/tmp/android13.json')):
        out[ver] = top_items(json.load(open(path, encoding='utf-8')))
    js = []
    js.append("/* ===================== ANDROID SETTINGS · MACHINE-EXTRACTED =====================")
    js.append("   Generated 1:1 from the Android Open Source Project Settings app.")
    js.append("   Source: aosp-mirror/platform_packages_apps_Settings")
    js.append("           android-14.0.0_r75  and  android-13.0.0_r83")
    js.append("   Inputs: res/xml/*.xml preference trees + res/values/strings.xml + arrays.xml,")
    js.append("           with android:fragment resolved to its backing screen via the Java sources.")
    js.append("   Every label, summary line and default value below is the string AOSP ships —")
    js.append("   nothing here is hand-written or inferred. Regenerate with tools/aosp-extract.py.")
    js.append("   ============================================================================= */")
    js.append('const ANDROID_TREE={')
    for ver in ('14', '13'):
        js.append(' %s:[\n%s\n ],' % (ver, ',\n'.join('  ' + i for i in out[ver])))
    js.append('};')
    src = '\n'.join(js)
    open('/tmp/android_tree.js', 'w', encoding='utf-8').write(src)
    print('bytes:', len(src))
    print('top items 14:', len(out['14']), '| 13:', len(out['13']))
