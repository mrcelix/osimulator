<h1 align="center">osimulator</h1>

<p align="center">
  <strong>Explore the real Settings menus of 19 operating systems — right in your browser.</strong><br>
  Pick an OS, choose a version, and navigate its interface as if you were on the real device.
</p>

<p align="center">
  <a href="https://osimulator.com/">Live demo</a> ·
  <a href="#operating-systems">Operating systems</a> ·
  <a href="#features">Features</a> ·
  <a href="#running-locally">Run locally</a>
</p>

---

**osimulator** is a single-file, 100% offline web app that recreates the **Settings** experience of 19 operating systems across 38 versions. Nothing is installed and no apps actually run — the goal is to *discover* how each system's interface and settings are structured, and how they differ between versions.

## Operating systems

| Category | Systems |
|---|---|
| 📱 Phone | iOS, Android, HarmonyOS |
| 📲 Tablet | iPadOS |
| 💻 Desktop | macOS, Windows 11/10, Ubuntu (GNOME), ChromeOS, Windows 7, Mac OS X |
| ⌚ Watch | watchOS, Wear OS |
| 📺 TV | tvOS, Google TV |
| 🚗 Car | Apple CarPlay, Android Auto |
| 🥽 XR | visionOS |
| 🎮 Console | PlayStation, Xbox |

Each system renders version-accurate menus, layout and wallpaper — 100+ settings screens in total.

## Features

- **Record & Play guides** — sign in, hit Record, tap through Settings to describe a task, then share a link. Anyone can replay the step-by-step walkthrough (no account needed) with on-screen highlights.
- **Deep links** — every OS, version and settings screen has its own shareable URL (e.g. `/#/ios/17.5/general`).
- **Real, navigable menus** — drill into Settings exactly like the real device, down to deep sub-pages.
- **Version-accurate differences** — the same OS shows different menus and styling per release.
- **19 systems · 38 versions · 100+ settings screens.**
- **Built-in OS AI assistant** — a local how-to helper for Wi-Fi, eSIM, dark mode, screenshots, resets and more.
- **12 languages** with full RTL support.
- **Quick OS picker, trending shortcuts and a ✨ "Magic" teleport** to a random system.
- **100% offline, single HTML file** — no backend, no build step, no tracking.

## Running locally

No server or build step is required — the app is one self-contained file.

```bash
# clone
git clone https://github.com/mrcelix/osimulator.git
cd osimulator

# then just open index.html in any modern browser
```

Or simply double-click `index.html`. It also works from `file://`.

## Deploying (GitHub Pages)

This repo is Pages-ready (`index.html` at the root, `.nojekyll` included):

1. Repository **Settings → Pages**.
2. **Source:** *Deploy from a branch* → **main** → **/ (root)**.
3. Your site goes live at `https://osimulator.com/`.

## Tech

Vanilla HTML, CSS and JavaScript — no frameworks, no dependencies. The entire UI, data model, icons and logic live in `index.html`. Membership and preferences are stored client-side (`localStorage`); the Google sign-in and AI assistant are simulated and never leave your browser.

---

## Türkçe

**osimulator**, 19 işletim sisteminin (38 sürüm) gerçek **Ayarlar** menülerini tarayıcıda birebir gezmeni sağlayan, tek dosyalık ve %100 çevrimdışı bir web uygulamasıdır. Uygulamalar çalışmaz; amaç her sistemin arayüzünü ve ayar yapısını, sürümler arası farklarıyla birlikte keşfetmektir.

Çalıştırmak için `index.html` dosyasını herhangi bir modern tarayıcıda açman yeterli — sunucu veya kurulum gerekmez.

## License

[MIT](LICENSE) — an independent educational project, not affiliated with Apple, Google, Microsoft or any OS vendor. All trademarks belong to their respective owners.
