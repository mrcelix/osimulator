#!/usr/bin/env python3
"""ChromeOS Settings: the string-resolution layer.

A label in a Polymer template is written `$i18n{someCamelCaseKey}`.  That key is
registered in a C++ "section" file as `{"someCamelCaseKey", IDS_SOMETHING}` and
the English text of `IDS_SOMETHING` lives in a GRIT `.grdp` file.  This module
walks that chain backwards so a template key can be turned into the English
string ChromeOS actually paints.
"""
import os
import re
import sys
import html as htmllib

# ---------------------------------------------------------------- GRIT layer

# GRIT lets a message carry branch-specific text.  A ChromeOS device runs the
# Google-branded build, so when a <if expr> names the branding we take the
# Chrome side; `use_titlecase` is the desktop convention ChromeOS follows.
GRIT_TRUE = {
    '_google_chrome', 'is_chrome_branded', 'chromeos_ash', 'is_chromeos',
    'is_chromeos_ash', 'use_titlecase', 'not is_ios', 'not is_android',
    'not is_macosx', 'not use_ozone', 'is_linux', 'not is_win',
}
GRIT_FALSE = {
    'not _google_chrome', 'not is_chrome_branded', 'not chromeos_ash',
    'not is_chromeos', 'not is_chromeos_ash', 'not use_titlecase',
    'is_ios', 'is_android', 'is_macosx', 'is_win', 'not is_linux',
    'is_chromeos_lacros', 'lacros', 'not is_chromeos_device',
}


def _grit_expr(expr):
    """True / False / None (unknown) for a GRIT <if expr> string."""
    e = ' '.join(expr.split())
    if e in GRIT_TRUE:
        return True
    if e in GRIT_FALSE:
        return False
    return None


# The attribute run must be matched quote-aware: a `desc="Internet > Network
# details: ..."` contains a literal '>' and a naive `.*?>` would end the tag
# inside it, spilling the rest of the description into the visible string.
_MSG_RE = re.compile(
    r'<message\s+name="(IDS_[A-Z0-9_]+)"((?:[^>"]|"[^"]*")*)>(.*?)</message>',
    re.S)
_IF_RE = re.compile(r'<if\s+expr="([^"]*)">(.*?)</if>', re.S)
_PH_RE = re.compile(r'<ph\s+[^>]*>(.*?)</ph>', re.S)
_EX_RE = re.compile(r'<ex>.*?</ex>', re.S)


def _clean_message(body):
    """Turn the body of a <message> into the string a user sees."""
    # A <ph> wraps a runtime placeholder and carries an <ex> sample; keep the
    # placeholder token itself ($1, {COUNT}, ...) and drop the example.
    def ph(m):
        return _EX_RE.sub('', m.group(1)).strip()
    body = _PH_RE.sub(ph, body)
    body = re.sub(r'<[^>]+>', '', body)
    # Inline markup inside a message is written escaped (&lt;a href=...&gt;),
    # so unescape first and then strip again -- otherwise the anchor tags
    # would survive into the visible string.
    body = htmllib.unescape(body)
    body = re.sub(r'<[^>]+>', '', body)
    # GRIT strips the leading/trailing whitespace of a message and collapses
    # the indentation it was written with.
    body = ' '.join(body.split())
    return body


def load_grd_messages(root):
    """IDS_NAME -> English string, over every settings-related GRIT file."""
    out = {}
    app = os.path.join(root, 'chrome', 'app')
    # Settings embeds shared components (the network list, the caption
    # controls) whose strings ship from other GRIT bundles.
    extra = [
        os.path.join(root, 'chromeos', 'chromeos_strings.grd'),
        os.path.join(root, 'ui', 'chromeos', 'ui_chromeos_strings.grd'),
    ]
    names = [
        # Later files win only when the earlier one had no entry, except that
        # the Chrome-branded overrides are applied last on purpose.
        'chromeos_strings.grdp',
        'chromeos_shared_strings.grdp',
        'os_settings_strings.grdp',
        'os_settings_search_tag_strings.grdp',
        'settings_strings.grdp',
        'shared_settings_strings.grdp',
        'app_management_strings.grdp',
        'printing_strings.grdp',
        'nearby_share_strings.grdp',
        'password_manager_ui_strings.grdp',
        'profiles_strings.grdp',
        'settings_chromium_strings.grdp',
        'settings_google_chrome_strings.grdp',
    ]
    for p in [os.path.join(app, n) for n in names] + extra:
        if not os.path.exists(p):
            continue
        raw = open(p, encoding='utf-8').read()

        # Resolve GRIT branch conditionals before pulling messages out, so a
        # message only defined on the non-Chrome branch never wins.
        def branch(m):
            v = _grit_expr(m.group(1))
            return m.group(2) if v is not False else ''
        prev = None
        while prev != raw:
            prev = raw
            raw = _IF_RE.sub(branch, raw)

        for m in _MSG_RE.finditer(raw):
            out[m.group(1)] = _clean_message(m.group(3))
    return out


# ------------------------------------------------------------- C++ key layer

_LOCALIZED_PAIR = re.compile(
    r'\{\s*"([A-Za-z0-9_]+)"\s*,\s*(IDS_[A-Z0-9_]+)\s*\}', re.S)
# A handful of keys pick their string from the wayfinding-revamp flag:
#   {"mouseSwapButtonsLabel", kIsRevampEnabled ? IDS_OS_..._REVAMP : IDS_...}
# Every ternary in the settings WebUI is that same flag, so it resolves from
# the release being extracted rather than needing a general C++ evaluator.
_LOCALIZED_TERNARY = re.compile(
    r'\{\s*"([A-Za-z0-9_]+)"\s*,\s*[^{}]*?[Rr]evamp[^{}?]*?\?'
    r'\s*(IDS_[A-Z0-9_]+)\s*:\s*(IDS_[A-Z0-9_]+)\s*\}', re.S)
_ADD_LOCALIZED = re.compile(
    r'AddLocalizedString\s*\(\s*"([A-Za-z0-9_]+)"\s*,\s*(IDS_[A-Z0-9_]+)\s*\)',
    re.S)
_ADD_STRING_F = re.compile(
    r'AddString\s*\(\s*"([A-Za-z0-9_]+)"\s*,[^;]*?(IDS_[A-Z0-9_]+)', re.S)
# A key whose string depends on a device capability:
#   AddLocalizedString("osSearchPageTitle",
#                      is_assistant_allowed ? IDS_..._AND_ASSISTANT : IDS_...)
# The first branch is the capable device; that is the persona here.
_ADD_TERNARY = re.compile(
    r'Add(?:Localized)?String\s*\(\s*"([A-Za-z0-9_]+)"\s*,[^;]*?\?'
    r'\s*(IDS_[A-Z0-9_]+)\s*:\s*(IDS_[A-Z0-9_]+)', re.S)
# Some keys are registered through a `const char name[] = "key";` indirection.
_KEY_ALIAS = re.compile(
    r'const char\s+([A-Za-z0-9_]+)\s*\[\]\s*=\s*"([A-Za-z0-9_]+)"\s*;')
# ...and some resolve their resource id through a helper function.
_INT_FN = re.compile(
    r'\bint\s+([A-Za-z0-9_]+)\s*\([^)]*\)\s*\{\s*return\s+(IDS_[A-Z0-9_]+)\s*;')
_ADD_VIA_FN = re.compile(
    r'Add(?:Localized)?String\s*\(\s*"([A-Za-z0-9_]+)"\s*,[^;]*?'
    r'\b([A-Za-z0-9_]+)\(\)\s*\)', re.S)
# AddLocalizedString(kVariable, IDS_X) -- the plain form only, so that when a
# key has both a placeholder variant and a plain one we take the plain text.
_ADD_ALIASED = re.compile(
    r'AddLocalizedString\s*\(\s*([A-Za-z][A-Za-z0-9_]*)\s*,\s*'
    r'(IDS_[A-Z0-9_]+)\s*\)', re.S)


def load_i18n_keys(root, revamp):
    """$i18n{key} -> IDS_NAME, from the WebUI C++ that registers each key."""
    out = {}
    # ChromeOS Settings registers most of its own keys, but reuses the shared
    # browser-settings and cross-WebUI providers for the pieces it embeds
    # (captions, network element, Bluetooth pairing, Nearby Share).
    roots = [
        os.path.join(root, 'chrome', 'browser', 'ui', 'webui', 'ash',
                     'settings'),
        os.path.join(root, 'chrome', 'browser', 'ui', 'webui', 'ash'),
        os.path.join(root, 'chrome', 'browser', 'ui', 'webui', 'settings'),
        os.path.join(root, 'ash', 'webui', 'common'),
        os.path.join(root, 'ui', 'webui', 'resources', 'cr_components'),
        os.path.join(root, 'ui', 'chromeos', 'strings'),
    ]
    for base in roots:
        if not os.path.isdir(base):
            continue
        for dirpath, _dirs, files in os.walk(base):
            for f in files:
                if not f.endswith(('.cc', '.h')):
                    continue
                if 'test' in f or 'unittest' in f:
                    continue
                raw = open(os.path.join(dirpath, f), encoding='utf-8',
                           errors='replace').read()

                # Per-file indirection tables, built before the registrations
                # that use them.
                alias_of = {m.group(1): m.group(2)
                            for m in _KEY_ALIAS.finditer(raw)}
                fn_ids = {m.group(1): m.group(2)
                          for m in _INT_FN.finditer(raw)}

                for m in _LOCALIZED_TERNARY.finditer(raw):
                    out.setdefault(m.group(1),
                                   m.group(2) if revamp else m.group(3))
                # A capability ternary: take the first branch, which is the
                # capable device -- the same persona the walker assumes.
                for m in _ADD_TERNARY.finditer(raw):
                    out.setdefault(m.group(1), m.group(2))
                for rx in (_LOCALIZED_PAIR, _ADD_LOCALIZED, _ADD_STRING_F):
                    for m in rx.finditer(raw):
                        out.setdefault(m.group(1), m.group(2))
                # AddLocalizedString(kSomeName, IDS_X) where kSomeName is a
                # `const char kSomeName[] = "actualKey";`
                for m in _ADD_ALIASED.finditer(raw):
                    key = alias_of.get(m.group(1))
                    if key:
                        out.setdefault(key, m.group(2))
                # AddString("key", GetStringUTF16(SomeHelper()))
                for m in _ADD_VIA_FN.finditer(raw):
                    ids = fn_ids.get(m.group(2))
                    if ids:
                        out.setdefault(m.group(1), ids)
    return out


class Strings:
    def __init__(self, root, revamp=True):
        self.ids = load_grd_messages(root)
        self.keys = load_i18n_keys(root, revamp)
        self.missing_key = set()
        self.missing_ids = set()

    def get(self, key):
        """English text for an $i18n{} key, or None."""
        ids = self.keys.get(key)
        if ids is None:
            self.missing_key.add(key)
            return None
        s = self.ids.get(ids)
        if s is None:
            self.missing_ids.add(ids)
            return None
        return s


if __name__ == '__main__':
    root = sys.argv[1] if len(sys.argv) > 1 else '/tmp/cros'
    st = Strings(root)
    print('IDS messages   :', len(st.ids))
    print('i18n keys      :', len(st.keys))
    probes = ['internetPageTitle', 'bluetoothPageTitle', 'devicePageTitle',
              'privacyHubTitle', 'privacyHubSubtext', 'aboutOsPageTitle',
              'systemPreferencesTitle', 'a11yPageTitle', 'osPeoplePageTitle',
              'mouseSwapButtonsLabel', 'primaryMouseButtonLeft',
              'enableContentProtectionAttestation', 'manageOtherPeople',
              'savedDevicesLabel', 'deviceOn', 'deviceOff']
    for p in probes:
        print('  %-38s %r' % (p, st.get(p)))
