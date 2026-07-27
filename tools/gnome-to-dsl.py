#!/usr/bin/env python3
"""Turn the extracted GNOME Control Center trees (JSON) into osimulator DSL JS.

Reads /tmp/gnome46.json and /tmp/gnome42.json (produced by gnome_extract.py)
and writes /tmp/ubuntu_tree.js containing `const UBUNTU_TREE = {46:[...],42:[...]}`.

Everything structural — panel names, sidebar order, sidebar separators, group
headings, group footers, row labels, row summaries, combo option lists — comes
out of the JSON verbatim, i.e. out of gnome-control-center's own .ui/.desktop
sources.  The only hand-written material is in the three clearly marked tables
below (VALUES, ON_BY_DEFAULT, RUNTIME), which supply *device state*: the text
printed on the right of a row, the position of a switch, and the contents of a
list that a real machine fills from hardware at run time.  None of them can
add, rename or remove a row.
"""
import json, re, sys

def norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())

def jstr(s):
    s = (s or '')
    s = s.replace('\\', '\\\\').replace("'", "\\'")
    s = s.replace('\n', ' ').replace('\r', ' ')
    return "'" + s + "'"

def fmt_opts(o):
    return (',{' + ','.join(o) + '}') if o else ''

# --------------------------------------------------------------------------
# panel id -> (sidebar id, icon glyph, icon colour).  The sidebar *order* and
# the separator groups are read from the JSON (cc-panel-list.c panel_order[]);
# only the pictogram and its colour are chosen here, since GNOME ships named
# themed icons the simulator does not carry.  Colours are the Ubuntu palette.
ORANGE, AUBERGINE, PURPLE, GREY = '#e95420', '#77216f', '#772953', '#5f6368'
PANEL_ICON = {
    'wifi':             ('wifi',       'wifi',          ORANGE),
    'network':          ('network',    'network',       GREY),
    'wwan':             ('wwan',       'cellular',      GREY),
    'bluetooth':        ('bluetooth',  'bluetooth',     GREY),
    'display':          ('display',    'display',       AUBERGINE),
    'sound':            ('sound',      'sounds',        AUBERGINE),
    'power':            ('power',      'battery',       AUBERGINE),
    'multitasking':     ('multitask',  'desktop',       AUBERGINE),
    'background':       ('appearance', 'appearance',    ORANGE),
    'applications':     ('apps',       'apps',          ORANGE),
    'notifications':    ('notif',      'notifications', ORANGE),
    'search':           ('search',     'search',        ORANGE),
    'online-accounts':  ('accounts',   'personcircle',  ORANGE),
    'sharing':          ('sharing',    'network',       ORANGE),
    'mouse':            ('mouse',      'general',       GREY),
    'keyboard':         ('keyboard',   'keyboard',      GREY),
    'color':            ('color',      'appearance',    GREY),
    'printers':         ('printers',   'files',         GREY),
    'wacom':            ('wacom',      'pencil',        GREY),
    'removable-media':  ('media',      'storage',       GREY),
    'region':           ('region',     'language',      GREY),
    'universal-access': ('access',     'accessibility', PURPLE),
    'privacy':          ('privacy',    'privacy',       PURPLE),
    'system':           ('system',     'gear',          PURPLE),
    'user-accounts':    ('users',      'users',         PURPLE),
    'default-apps':     ('defapps',    'appstore',      PURPLE),
    'datetime':         ('datetime',   'datetime',      PURPLE),
    'info-overview':    ('about',      'info',          PURPLE),
    'location':         ('location',   'location',      PURPLE),
    'camera':           ('camera',     'camera',        PURPLE),
    'microphone':       ('mic',        'mic',           PURPLE),
    'thunderbolt':      ('thunder',    'general',       PURPLE),
    'usage':            ('usage',      'storage',       PURPLE),
    'lock':             ('lock',       'passcode',      PURPLE),
    'diagnostics':      ('diag',       'info',          PURPLE),
}

SLIDER_GLYPH = [
    (('bright', 'contrast', 'temperature', 'colour', 'color', 'zoom', 'text', 'scal'), 'display'),
    (('volume', 'sound', 'alert', 'balance', 'fade', 'subwoofer'), 'sounds'),
]
def slider_glyph(title):
    n = (title or '').lower()
    for keys, g in SLIDER_GLYPH:
        if any(k in n for k in keys):
            return g
    return 'general'

# --------------------------------------------------------------------------
# DEVICE STATE, table 1 of 3 — the text printed on the right of a value row.
# gnome-control-center's sources define that "IPv4 Address" is a row and what
# it is called; the address itself is read from NetworkManager at run time and
# cannot come from source.  These are the simulator's stand-in values for its
# Ubuntu-on-a-ThinkPad persona.  Illustrative, never structural.
VALUES = {
    # About / System Details
    'devicename':        'john-thinkpad',
    'hostname':          'john-thinkpad',
    'hardwaremodel':     'ThinkPad X1 Carbon Gen 11',
    'memory':            '32.0 GiB',
    'processor':         '13th Gen Intel® Core™ i7-1365U × 12',
    'graphics':          'Intel® Iris® Xe Graphics',
    'diskcapacity':      '1.0 TB',
    'osname':            'Ubuntu 24.04.1 LTS',
    'osbuild':           '24.04.1 LTS (Noble Numbat)',
    'ostype':            '64-bit',
    'gnomeversion':      '46',
    'windowingsystem':   'Wayland',
    'kernelversion':     'Linux 6.8.0-45-generic',
    'firmwareversion':   'N3AET92W (1.62)',
    'softwareupdates':   'Up to date',
    # Network
    'ipv4address':       '192.168.1.42',
    'ipv6address':       'fe80::1c4b:2aff:fe57:9d31',
    'hardwareaddress':   'F0:2F:74:C1:88:A0',
    'defaultroute':      '192.168.1.1',
    'dns':               '192.168.1.1',
    'linkspeed':         '1200 Mb/s',
    'strength':          'Excellent',
    'security':          'WPA3',
    'port':              '3389',
    'username':          'john',
    'password':          '••••••••',
    'devicenameremote':  'john-thinkpad',
    # Users
    'name':              'John Wick',
    'language':          'English (United Kingdom)',
    'formats':           'United Kingdom',
    'lastlogin':         'Today, 09:12',
    'fingerprintlogin':  'Not set up',
    # Date & time
    'datetime':          '24 July 2026, 14:05',
    'timezone':          'Europe/Istanbul (GMT+3)',
    'timeformat':        '24-hour',
    # Power
    'batterylevel':      '87%',
    'remainingtime':     '4 hours 12 minutes',
    # credential fields and the odd generic row
    'newpassword':       '••••••••',
    'currentpassword':   '••••••••',
    'confirmpassword':   '••••••••',
    'confirm':           '••••••••',
    'url':               'https://ubuntu.com',
    'configurationurl':  'http://proxy.local/proxy.pac',
    'ignoredhosts':      'localhost, 127.0.0.0/8, ::1',
    'domain':            'Not joined',
    'day':               '24',
    'color':             'Blue',
    'delay':             'Short',
    'testentry':         'Type here to test settings',
    'donotdisturb':      'Off',
    'filesharing':       'Off',
    'lockscreennotifications': 'On',
    'notset up':         'Not set up',
}

# Rows whose label is generic enough to collide across panels get a
# panel-qualified entry here; VALUES above is the global fallback.
PANEL_VALUES = {
    ('applications', 'web'):          'Firefox',
    ('applications', 'mail'):         'Thunderbird',
    ('applications', 'calendar'):     'Calendar',
    ('applications', 'music'):        'Music',
    ('applications', 'video'):        'Videos',
    ('applications', 'photos'):       'Image Viewer',
    ('applications', 'calls'):        'Calls',
    ('applications', 'sms'):          'Messages',
    ('applications', 'cdaudio'):      'Ask what to do',
    ('applications', 'dvdvideo'):     'Ask what to do',
    ('applications', 'musicplayer'):  'Ask what to do',
    ('applications', 'software'):     'Ask what to do',
    ('applications', 'type'):         'Audio CD',
    ('applications', 'action'):       'Ask what to do',
    ('applications', 'storage'):      '148.2 MB',
    ('applications', 'filelinkassociations'): '3 associations',
    ('applications', 'requiredaccess'): 'Network, Devices',
    ('applications', 'builtinpermissions'): 'Network, Devices',
    ('default-apps', 'web'):          'Firefox',
    ('default-apps', 'mail'):         'Thunderbird',
    ('default-apps', 'calendar'):     'Calendar',
    ('default-apps', 'music'):        'Music',
    ('default-apps', 'video'):        'Videos',
    ('default-apps', 'photos'):       'Image Viewer',
    ('removable-media', 'cdaudio'):   'Ask what to do',
    ('removable-media', 'dvdvideo'):  'Ask what to do',
    ('removable-media', 'musicplayer'): 'Ask what to do',
    ('removable-media', 'photos'):    'Ask what to do',
    ('removable-media', 'software'):  'Ask what to do',
    ('removable-media', 'type'):      'Audio CD',
    ('removable-media', 'action'):    'Ask what to do',
    ('display', 'multipledisplays'):  'Join Displays',
    ('display', 'schedule'):          'Sunset to Sunrise',
    ('display', 'times'):             '20:00 to 06:00',
    ('mouse', 'primarybutton'):       'Left',
    ('mouse', 'scrolldirection'):     'Traditional',
    ('mouse', 'scrollmethod'):        'Two-finger Scrolling',
    ('mouse', 'secondaryclick'):      'Two-finger Push',
    ('mouse', 'testentry'):           'Move the pointer to test',
    ('multitasking', 'numberofworkspaces'): '4',
    ('sharing', 'remotedesktopaddress'): 'rdp://john-thinkpad.local',
    ('sharing', 'sshlogincommand'):   'ssh john@john-thinkpad.local',
    ('sharing', 'mediasharing'):      'Off',
    ('system', 'remotedesktopaddress'): 'rdp://john-thinkpad.local',
    ('system', 'sshlogincommand'):    'ssh john@john-thinkpad.local',
    ('system', 'operatingsystem'):    'Ubuntu 24.04.1 LTS',
    ('system', 'virtualization'):     'None',
    ('system', 'domain'):             'Not joined',
    ('info-overview', 'operatingsystem'): 'Ubuntu 22.04.5 LTS',
    ('info-overview', 'virtualization'):  'None',
    ('universal-access', 'magnificationfactor'): '2.0×',
    ('universal-access', 'delay'):    'Short',
    ('universal-access', 'testflash'): 'Flash the screen to test',
    ('privacy', 'times'):             '30 days',
    ('privacy', 'url'):               'https://ubuntu.com/legal/data-privacy',
    ('datetime', 'year'):             '2026',
}

def value_of(node, panel=None):
    t = norm(node.get('title'))
    if panel and (panel, t) in PANEL_VALUES:
        return PANEL_VALUES[(panel, t)]
    return VALUES.get(t)

# --------------------------------------------------------------------------
# DEVICE STATE, table 2 of 3 — switch positions.  A handful of GNOME switches
# carry an `active` property in the .ui (those arrive as node['default'] and
# win); the rest are bound to a GSetting and resolved at run time.  Where the
# source says nothing, show the position a freshly installed Ubuntu has.
ON_BY_DEFAULT = {norm(x) for x in (
    'Wi-Fi', 'Bluetooth', 'Connect Automatically', 'Location Services',
    'Camera', 'Microphone', 'Automatic Screen Lock', 'Lock Screen on Suspend',
    'Automatic Date & Time', 'Automatic Time Zone', 'Automatic Suspend',
    'Dim Screen', 'Show Battery Percentage', 'Natural Scrolling',
    'Tap to Click', 'Two-finger Scrolling', 'Notification Popups',
    'Show Message Content in Popups', 'Lock Screen Notifications',
    'File History', 'Automatically Delete Trash Content',
    'Automatically Delete Temporary Files', 'Sound Effects',
    'Over-Amplification', 'Software Sources', 'Automatic Updates',
    'Hot Corner', 'Active Screen Edges', 'Fixed Number of Workspaces',
    'Workspaces on Primary Display Only', 'Include Applications from All Workspaces',
    'App Search', 'Show in Overview', 'Screen Time Limits',
    'Alert Sound', 'Volume Levels', 'Week Day', 'Date', 'Seconds',
    'Month Day', 'Week Numbers', 'Search', 'Ambient Backlight',
)}

def truthy(node):
    d = node.get('default')
    if d is not None:
        return 'true' if str(d).lower() in ('true', '1', 'yes') else 'false'
    return 'true' if norm(node.get('title')) in ON_BY_DEFAULT else 'false'

# --------------------------------------------------------------------------
# DEVICE STATE, table 3 of 3 — runtime lists.  The extractor marks a group
# `runtime: true` when the .ui declares the heading but no rows, because the
# panel fills that list from real hardware/accounts when it opens (visible
# Wi-Fi networks, paired devices, installed apps, printers...).  The heading
# and its footer are still source-derived; only the rows below are the
# simulator's sample contents.  Keyed by (panel, group heading).  A group with
# no entry here renders GNOME's own empty state instead of inventing rows.
APPS = ['Firefox', 'Files', 'Text Editor', 'Terminal', 'Software',
        'Thunderbird', 'LibreOffice Writer', 'Image Viewer']

RUNTIME = {
    # -- GNOME 46 -------------------------------------------------------
    ('network', 'Bluetooth'):            None,
    ('power', 'Connected Devices'): [
        "L('Logitech MX Master 3S',{value:'64%'})",
        "L('WH-1000XM5',{value:'92%'})",
    ],
    ('power', 'Power Mode'):        ["CH('Balanced Power',true)", "CH('Power Saver',false)",
                                     "CH('Performance',false)"],
    ('background', 'Background'):   ["{type:'wallpaperPreview'}"],
    ('notifications', 'App Notifications'): [
        "L(%r,{value:'On'})" % a for a in APPS[:5]],
    ('search', 'Default Locations'): ["T('Home',true)", "T('Documents',true)",
                                      "T('Downloads',true)", "T('Music',false)",
                                      "T('Pictures',false)", "T('Videos',false)"],
    ('search', 'Bookmarked Locations'): ["T('Projects',true)"],
    ('search', 'Custom Locations'):  None,
    ('search', 'Search Results'):    ["T('Files',true)", "T('Software',true)",
                                      "T('Characters',true)", "T('Terminal',true)",
                                      "T('Calculator',true)", "T('Settings',true)"],
    ('online-accounts', 'Your Accounts'): [
        "L('john@ubuntu.com',{value:'Ubuntu Single Sign-On'})"],
    ('online-accounts', 'Connect an Account'): [
        "L('Google')", "L('Nextcloud')", "L('Microsoft 365')",
        "L('Microsoft Exchange')", "L('Fedora')", "L('Kerberos')"],
    ('online-accounts', 'Add an account'): [
        "L('Google')", "L('Nextcloud')", "L('Microsoft Exchange')",
        "L('Last.fm')", "L('IMAP and SMTP')", "L('Kerberos')"],
    ('sharing', 'Networks'):        ["T('Home-5G',true)"],
    ('sharing', 'Folders'):         ["L('Public',{value:'/home/john/Public'})"],
    ('privacy', 'Permitted Apps'):  ["T('Firefox',true)", "T('Maps',false)"],
    ('privacy', 'Devices'):         None,
    ('privacy', 'Security Events'): None,
    ('system', 'Other Users'):      ["L('Guest Session',{value:'Standard'})"],
    ('user-accounts', 'Other Users'): ["L('Guest Session',{value:'Standard'})"],
    # -- GNOME 42 -------------------------------------------------------
    ('network', 'Other Devices'):   None,
    ('notifications', 'Applications'): [
        "L(%r,{value:'On'})" % a for a in APPS[:5]],
    ('search', 'Places'):           ["T('Home',true)", "T('Documents',true)",
                                     "T('Downloads',true)"],
    ('search', 'Bookmarks'):        ["T('Projects',true)"],
    ('search', 'Others'):           None,
    ('sound', 'System Volume'):     ["SL(62,'sounds','sounds')", "T('Over-Amplification',false)"],
    ('sound', 'Volume Levels'):     ["SL(80,'sounds','sounds')"],
    ('sound', 'Alert Sound'):       ["CH('Default',true)", "CH('Bark',false)",
                                     "CH('Drip',false)", "CH('Glass',false)",
                                     "CH('Sonar',false)"],
    ('power', 'Battery'):           ["V('Battery Level','87%')",
                                     "V('Remaining Time','4 hours 12 minutes')"],
    ('power', 'Devices'):           ["L('Logitech MX Master 3S',{value:'64%'})"],
    ('keyboard', 'Input Sources'):  ["L('English (UK)')", "L('Turkish')"],
}

# Panels whose entire body is built in C from live hardware, so the .ui has no
# rows at all to extract.  The heading text below is GNOME's own; the entries
# under it are the simulator's sample hardware, exactly like RUNTIME above.
PANEL_EXTRA = {
    'wifi': ["S([" + ','.join([
        "L('Home-5G',{value:'Connected',detail:D('Home-5G',[S([V('Signal Strength','Excellent'),V('Link Speed','1200 Mb/s'),V('Security','WPA3'),V('IPv4 Address','192.168.1.42'),V('IPv6 Address','fe80::1c4b:2aff:fe57:9d31'),V('Hardware Address','F0:2F:74:C1:88:A0'),V('Default Route','192.168.1.1'),V('DNS','192.168.1.1')]),S([T('Connect Automatically',true),T('Make Available to Other Users',false),T('Metered Connection',false)]),S([B('Forget Connection',{style:'link'})])])})",
        "L('Cafe-Guest')", "L('TP-Link_9F2A')", "L('eduroam')",
    ]) + "],{header:'Visible Networks'})"],
    'bluetooth': ["S([L('Logitech MX Master 3S',{value:'Connected'}),"
                  "L('WH-1000XM5',{value:'Disconnected'})],{header:'Devices'})"],
    'printers': ["S([L('HP LaserJet Pro M404dn',{value:'Ready'})],{header:'Printers'})"],
    'color':    ["S([L('Built-in Display',{value:'No profile'})],{header:'Devices'})"],
}

# --------------------------------------------------------------------------
def choice_run(run):
    """a consecutive run of radio rows sharing a GtkCheckButton group is one
    picker, so it renders as a CHOICE rather than as N separate rows"""
    return 'CHOICE(null,[%s],0)' % ','.join(jstr(r.get('title')) for r in run)

def opts_of(node, extra=None):
    o = []
    if node.get('summary'):
        o.append('sub:' + jstr(node['summary']))
    if extra:
        o += extra
    return o

def row(node, panel, depth):
    k = node.get('kind')
    title = node.get('title')
    kids = [c for c in (node.get('children') or []) if c.get('kind') != 'group'] \
        or (node.get('children') or [])

    if k == 'note':
        return 'NOTE(' + jstr(title) + ')'

    if k == 'button':
        return 'B(%s%s)' % (jstr(title), fmt_opts(opts_of(node)))

    if k == 'external':
        det = "D(%s,[S([NOTE(%s)])])" % (jstr(title), jstr(
            'This row hands off to a separate application, so gnome-control-center '
            'has no page behind it.'))
        return 'L(%s,{%s})' % (jstr(title), ','.join(opts_of(node, ['detail:' + det])))

    if k == 'combo':
        o = node.get('options') or []
        if o:
            det = 'D(%s,[CHOICE(null,[%s],0)])' % (jstr(title), ','.join(jstr(x) for x in o))
            return 'L(%s,{%s})' % (jstr(title), ','.join(
                opts_of(node, ['value:' + jstr(o[0]), 'detail:' + det])))
        v = value_of(node, panel)
        return 'L(%s%s)' % (jstr(title), fmt_opts(opts_of(
            node, ['value:' + jstr(v)] if v else None)))

    if k in ('entry', 'spin', 'value'):
        if 'binding' in node:
            # a Keyboard Shortcuts row: the accelerator resolved from the
            # GSettings schema, or GNOME's own word for "no binding".
            return 'V(%s,%s)' % (jstr(title), jstr(node['binding'] or 'Disabled'))
        v = value_of(node, panel) or ''
        return 'V(%s,%s%s)' % (jstr(title), jstr(v), fmt_opts(opts_of(node)))

    if k == 'toggle' and not node.get('children'):
        return 'T(%s,%s%s)' % (jstr(title), truthy(node), fmt_opts(opts_of(node)))

    # anything left with children is a drill-in page
    if node.get('children'):
        secs = sections(node['children'], panel, depth + 1)
        if secs:
            det = 'D(%s,[%s])' % (jstr(title), ','.join(secs))
            extra = ['detail:' + det]
            if k == 'toggle':
                extra.insert(0, 'value:' + ("'On'" if truthy(node) == 'true' else "'Off'"))
            else:
                v = value_of(node, panel)
                if v:
                    extra.insert(0, 'value:' + jstr(v))
            return 'L(%s,{%s})' % (jstr(title), ','.join(opts_of(node, extra)))

    if k == 'toggle':
        return 'T(%s,%s%s)' % (jstr(title), truthy(node), fmt_opts(opts_of(node)))
    v = value_of(node, panel)
    if v:
        return 'V(%s,%s%s)' % (jstr(title), jstr(v), fmt_opts(opts_of(node)))
    return 'L(%s%s)' % (jstr(title), fmt_opts(opts_of(node)))

def runtime_group(node, panel):
    """render a heading whose rows a real machine supplies at run time"""
    title, foot = node.get('title'), node.get('footer')
    body = RUNTIME.get((panel, title))
    if body is None:
        body = ["NOTE(%s)" % jstr(
            'This list is filled from the hardware and accounts present on the '
            'machine, so it is empty here.')]
    o = []
    if title:
        o.append('header:' + jstr(title))
    if foot:
        o.append('footer:' + jstr(foot))
    return 'S([%s]%s)' % (','.join(body), (',{' + ','.join(o) + '}') if o else '')

def sections(nodes, panel, depth):
    """turn a list of child nodes into S(...) section literals"""
    out, buf = [], []
    def flush(hdr=None, foot=None):
        if buf or hdr or foot:
            o = []
            if hdr:
                o.append('header:' + jstr(hdr))
            if foot:
                o.append('footer:' + jstr(foot))
            out.append('S([%s]%s)' % (','.join(buf), (',{' + ','.join(o) + '}') if o else ''))
            buf.clear()

    i = 0
    while i < len(nodes):
        n = nodes[i]
        k = n.get('kind')

        if k == 'group':
            flush()
            if n.get('runtime') and not n.get('children'):
                out.append(runtime_group(n, panel))
                i += 1
                continue
            inner = sections(n.get('children') or [], panel, depth + 1)
            if not inner:
                i += 1
                continue
            hdr, foot = n.get('title'), n.get('footer')
            if hdr or foot:
                first = inner[0]
                o = []
                if hdr:
                    o.append('header:' + jstr(hdr))
                if foot and len(inner) == 1:
                    o.append('footer:' + jstr(foot))
                if first.endswith('])'):
                    inner[0] = first[:-1] + ',{' + ','.join(o) + '})'
                elif first.endswith('})'):
                    inner[0] = first[:-2] + ',' + ','.join(o) + '})'
                if foot and len(inner) > 1:
                    last = inner[-1]
                    if last.endswith('])'):
                        inner[-1] = last[:-1] + ',{footer:' + jstr(foot) + '})'
                    elif last.endswith('})'):
                        inner[-1] = last[:-2] + ',footer:' + jstr(foot) + '})'
            out += inner
            i += 1
            continue

        if k == 'slider':
            flush()
            g = slider_glyph(n.get('title'))
            o = ['header:' + jstr(n.get('title') or 'Level')]
            if n.get('summary'):
                o.append('footer:' + jstr(n['summary']))
            out.append('S([SL(50,%s,%s)],{%s})' % (jstr(g), jstr(g), ','.join(o)))
            i += 1
            continue

        if k == 'radio':
            j = i
            grp = n.get('group')
            while j < len(nodes) and nodes[j].get('kind') == 'radio' \
                    and nodes[j].get('group') == grp:
                j += 1
            flush()
            out.append(choice_run(nodes[i:j]))
            i = j
            continue

        buf.append(row(n, panel, depth))
        i += 1
    flush()
    return out

def status_section(panel):
    """GNOME's own AdwStatusPage text is the literally correct screen for a
    panel whose whole body is hardware that is not attached."""
    sp = (panel.get('status_pages') or [])
    sp = [s for s in sp if s.get('title')]
    if not sp:
        return None
    s = sp[0]
    rows = ['NOTE(' + jstr(s['title']) + ')']
    if s.get('description'):
        rows.append('NOTE(' + jstr(s['description']) + ')')
    return 'S([%s])' % ','.join(rows)

def applications_panel(p):
    """cc-applications-panel shows a list of installed apps and, once one is
    picked, that app's own page.  Both live in the same .ui template, so a flat
    walk stacks them on top of each other.  Split them back apart: the Default
    Apps row stays on the panel, and every other group is the per-app page,
    reached through a row per installed app.  The app list itself is runtime
    (GAppInfo enumeration), so its contents are sample data like RUNTIME above.
    """
    kids = p.get('children') or []
    panel_level, per_app = [], []
    for n in kids:
        titles = {c.get('title') for c in (n.get('children') or [])}
        (panel_level if 'Default Apps' in titles else per_app).append(n)
    out = sections(panel_level, 'applications', 1)
    app_secs = sections(per_app, 'applications', 2)
    if app_secs:
        rows = ["L(%s,{detail:D(%s,[%s])})" % (jstr(a), jstr(a), ','.join(app_secs))
                for a in APPS]
        out.append("S([%s],{header:'Installed Apps'})" % ','.join(rows))
    return out

def top_items(tree):
    items, used = [], {}
    for p in tree:
        pid = p['panel']
        title = p.get('title') or pid
        sid, icon, bg = PANEL_ICON.get(pid, (re.sub(r'[^a-z0-9]+', '', pid)[:12], 'gear', GREY))
        used[sid] = used.get(sid, 0) + 1
        if used[sid] > 1:
            sid = '%s%d' % (sid, used[sid])
        if pid == 'applications':
            secs = applications_panel(p)
        else:
            secs = sections(p.get('children') or [], pid, 1)
        secs = PANEL_EXTRA.get(pid, []) + secs
        st = status_section(p)
        if not secs and st:
            secs = [st]
        if not secs:
            secs = ["S([NOTE(%s)])" % jstr(
                'This panel is built from live hardware, so it has no rows here.')]
        detail = 'D(%s,[%s])' % (jstr(title), ','.join(secs))
        # GNOME's own sidebar is icon + panel name only; the .desktop Comment is
        # search metadata (it feeds the panel search index), never a subtitle, so
        # it is carried as `search` rather than shown under the row.
        sub = (',search:' + jstr(p['comment'])) if p.get('comment') else ''
        items.append("{id:%s,title:%s%s,icon:%s,iconBg:%s,group:%s,detail:%s}" % (
            jstr(sid), jstr(title), sub, jstr(icon), jstr(bg),
            jstr('u%d' % (p.get('sidebar_group') or 0)), detail))
    return items

if __name__ == '__main__':
    out = {}
    for ver, path in (('46', '/tmp/gnome46.json'), ('42', '/tmp/gnome42.json')):
        out[ver] = top_items(json.load(open(path, encoding='utf-8')))
    js = []
    js.append("/* ================= UBUNTU / GNOME SETTINGS · MACHINE-EXTRACTED =================")
    js.append("   Generated 1:1 from GNOME Control Center's own source tree.")
    js.append("   Source: GNOME/gnome-control-center, tags 46.4 (Ubuntu 24.04 LTS)")
    js.append("                                        and 42.4 (Ubuntu 22.04 LTS)")
    js.append("   Inputs: panels/<panel>/*.ui GtkBuilder trees (AdwPreferencesPage / -Group / rows),")
    js.append("           panels/<panel>/*.desktop.in panel names, panels/keyboard/*.xml.in shortcut lists,")
    js.append("           shell/cc-panel-loader.c for which panels are built and")
    js.append("           shell/cc-panel-list.c panel_order[] for sidebar order and separators.")
    js.append("   Every panel name, group heading, footer, row label, row summary and combo")
    js.append("   option list below is the string GNOME ships. Device state (values on the")
    js.append("   right, switch positions, runtime lists) is marked as such in the three")
    js.append("   tables in tools/gnome-to-dsl.py. Regenerate with tools/gnome-extract.py.")
    js.append("   ============================================================================= */")
    js.append('const UBUNTU_TREE={')
    for ver in ('46', '42'):
        js.append(' %s:[\n%s\n ],' % (ver, ',\n'.join('  ' + i for i in out[ver])))
    js.append('};')
    src = '\n'.join(js)
    open('/tmp/ubuntu_tree.js', 'w', encoding='utf-8').write(src)
    print('bytes:', len(src))
    print('top items 46:', len(out['46']), '| 42:', len(out['42']))
