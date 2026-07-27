#!/usr/bin/env python3
"""Extract the real Android Settings menu tree from AOSP source.

Reads res/xml/*.xml preference trees + res/values/strings.xml + arrays.xml,
resolves @string/@array references, maps android:fragment -> backing XML by
parsing the Java sources, and walks the whole thing from top_level_settings.xml
into a fully nested JSON tree.
"""
import os, re, sys, json, glob
import xml.etree.ElementTree as ET

ROOT = sys.argv[1]
OUT  = sys.argv[2]
A = '{http://schemas.android.com/apk/res/android}'

# ---------------------------------------------------------------- resources
def clean(t):
    if t is None:
        return None
    t = t.replace('\\n', ' ').replace('\\t', ' ')
    t = t.replace("\\'", "'").replace('\\"', '"')
    t = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), t)
    t = re.sub(r'%[0-9]?\$?[sd]', '…', t)
    t = re.sub(r'<[^>]+>', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def parse_values(path):
    if not os.path.exists(path):
        return None
    raw = open(path, encoding='utf-8').read()
    try:
        return ET.fromstring(raw)
    except ET.ParseError:
        return ET.fromstring(re.sub(r'xmlns:\w+="[^"]*"', '', raw))

def load_strings(path):
    """AOSP ships product variants of some strings:
         <string name="about_settings" product="default">About phone</string>
         <string name="about_settings" product="tablet">About tablet</string>
         <string name="about_settings" product="emulator">About emulated device</string>
       The simulator models a handset, so prefer the no-product / product="default"
       form and only fall back to a variant when nothing else is declared."""
    out, weak = {}, {}
    root = parse_values(path)
    if root is None:
        return out
    for el in root:
        if el.tag.split('}')[-1] != 'string' or not el.get('name'):
            continue
        name = el.get('name')
        val = clean(''.join(el.itertext()))
        product = el.get('product')
        if product in (None, 'default'):
            out[name] = val
        else:
            weak.setdefault(name, val)
    for k, v in weak.items():
        out.setdefault(k, v)
    return out

# Strings referenced by res/xml here but declared in a module outside this repo
# (SettingsLib / product overlays). Values below are the verbatim handset
# (product="default") strings as shipped in the same repo's Android 13 tree.
STRING_FALLBACK = {
    'about_settings': 'About phone',
}

def load_arrays(path):
    out = {}
    root = parse_values(path)
    if root is None:
        return out
    for el in root:
        if el.tag.split('}')[-1] in ('string-array', 'array') and el.get('name'):
            out[el.get('name')] = [clean(''.join(i.itertext())) for i in el]
    return out

STR = load_strings(os.path.join(ROOT, 'res/values/strings.xml'))
ARR = load_arrays(os.path.join(ROOT, 'res/values/arrays.xml'))

PLACEHOLDER = {'summary_placeholder', 'loading_injected_setting_summary'}

def res(v):
    if v is None:
        return None
    if v.startswith('@string/'):
        key = v[len('@string/'):]
        if key in PLACEHOLDER:
            return None
        return STR.get(key) or STRING_FALLBACK.get(key)
    if '/' in v and v.startswith('@') and 'array' in v.split('/')[0]:
        return ARR.get(v.split('/', 1)[1])
    if v.startswith('@'):
        return None
    return clean(v)

# ---------------------------------------------- fragment class -> xml res id
FRAG2XML = {}
SHORT2XML = {}
def build_frag_map():
    pats = [re.compile(r'getPreferenceScreenResId\s*\([^)]*\)\s*\{[^}]*?R\.xml\.(\w+)', re.S),
            re.compile(r'BaseSearchIndexProvider\s*\(\s*R\.xml\.(\w+)'),
            re.compile(r'addPreferencesFromResource\s*\(\s*R\.xml\.(\w+)'),
            re.compile(r'R\.xml\.(\w+)')]
    for jf in glob.glob(os.path.join(ROOT, 'src/**/*.java'), recursive=True):
        try:
            src = open(jf, encoding='utf-8', errors='ignore').read()
        except OSError:
            continue
        if 'R.xml.' not in src:
            continue
        pkg = re.search(r'^\s*package\s+([\w.]+)\s*;', src, re.M)
        if not pkg:
            continue
        cls = os.path.basename(jf)[:-5]
        for p in pats:
            m = p.search(src)
            if m:
                FRAG2XML[pkg.group(1) + '.' + cls] = m.group(1)
                SHORT2XML.setdefault(cls, m.group(1))
                break
build_frag_map()

def kind_of(tag):
    t = tag.split('.')[-1]
    # runtime status banners injected by controllers at run time, not menu items
    if t in ('LayoutPreference', 'ProgressPreference', 'JumpPreference'):
        return 'runtime'
    if t.endswith('FooterPreference') or t == 'FooterPreference':
        return 'note'
    if t == 'PreferenceCategory':
        return 'category'
    if t == 'PreferenceScreen':
        return 'screen'
    if 'SwitchPreference' in t or 'CheckBoxPreference' in t or t == 'TwoStatePreference':
        return 'toggle'
    if 'SeekBar' in t or 'Slider' in t:
        return 'slider'
    if 'ListPreference' in t or t == 'DropDownPreference':
        return 'list'
    return 'plain'

SKIP_TAGS = {'intent', 'extra'}
MAXDEPTH = 7
stats = {'screens': 0, 'missing': set()}

xml_cache = {}
def load_xml(name):
    if name in xml_cache:
        return xml_cache[name]
    p = os.path.join(ROOT, 'res/xml', name + '.xml')
    t = None
    if os.path.exists(p):
        try:
            t = ET.parse(p).getroot()
        except ET.ParseError:
            t = None
    xml_cache[name] = t
    return t

def norm(s):
    return re.sub(r'[^a-z0-9]', '', (s or '').lower())

def dedupe(nodes):
    """AOSP ships conditional variants of the same row; keep the richest one."""
    out, seen = [], {}
    for n in nodes:
        k = norm(n.get('title'))
        if not k:
            out.append(n)
            continue
        if k in seen:
            prev = out[seen[k]]
            if len(n.get('children') or []) > len(prev.get('children') or []):
                out[seen[k]] = n
            continue
        seen[k] = len(out)
        out.append(n)
    return out

def walk_children(el, path, depth):
    out = []
    for c in el:
        tag = c.tag.split('}')[-1]
        if tag.lower() in SKIP_TAGS:
            continue
        n = make_node(c, tag, path, depth)
        if n:
            out.append(n)
    return dedupe(out)

def make_node(c, tag, path, depth):
    title = res(c.get(A + 'title'))
    summary = res(c.get(A + 'summary'))
    if isinstance(title, list):
        title = None
    if isinstance(summary, list):
        summary = None
    frag = c.get(A + 'fragment')
    kind = kind_of(tag)
    try:
        order = int(c.get(A + 'order'))
    except (TypeError, ValueError):
        order = None

    if kind == 'runtime':
        return None

    kids = walk_children(c, path, depth)

    if kind == 'note':
        return {'kind': 'note', 'title': title or summary, 'children': []} if (title or summary) else None

    if kind == 'category' and not title:
        return {'kind': 'group', 'title': None, 'children': kids} if kids else None
    if not title and not kids:
        return None

    # long prose with no children and no fragment = an on-screen footer note
    if (title and not kids and not frag and kind == 'plain'
            and (len(title) > 58 or title.rstrip().endswith('.'))):
        return {'kind': 'note', 'title': title, 'children': []}

    node = {'kind': kind, 'title': title, 'summary': summary,
            'order': order, 'children': kids}

    dv = c.get(A + 'defaultValue')
    if dv is not None:
        node['default'] = dv

    if kind == 'list':
        ents = res(c.get(A + 'entries'))
        if isinstance(ents, list) and ents:
            node['entries'] = [e for e in ents if e]

    if frag and depth < MAXDEPTH:
        xmlname = FRAG2XML.get(frag) or SHORT2XML.get(frag.split('.')[-1])
        if xmlname:
            if xmlname not in path:
                sub = load_xml(xmlname)
                if sub is not None:
                    stats['screens'] += 1
                    node['children'] = dedupe(
                        node['children'] + walk_children(sub, path + [xmlname], depth + 1))
                    node['src'] = xmlname
        else:
            stats['missing'].add(frag)

    if node['children']:
        node['children'].sort(key=lambda n: n.get('order') if n.get('order') is not None else 0)
    return node

root_el = load_xml('top_level_settings')
if root_el is None:
    sys.exit('top_level_settings.xml not found in ' + ROOT)

tree = walk_children(root_el, ['top_level_settings'], 0)
tree.sort(key=lambda n: n.get('order') if n.get('order') is not None else 0)
json.dump(tree, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

def count(ns):
    return sum(1 + count(n.get('children') or []) for n in ns)
def depth(ns, d=1):
    return max([d] + [depth(n['children'], d + 1) for n in ns if n.get('children')])

print('strings:', len(STR), 'arrays:', len(ARR), 'fragmap:', len(FRAG2XML))
print('top-level:', len(tree), '| screens expanded:', stats['screens'])
print('TOTAL NODES:', count(tree), '| max depth:', depth(tree))
print('unresolved fragments:', len(stats['missing']))
for f in sorted(stats['missing']):
    print('   ?', f)
