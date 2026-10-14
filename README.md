# Safeer Browser for Linux

A fast, light, privacy-first browser for Linux Mint, Ubuntu and Debian — native GTK4 and
WebKitGTK 6.0 with our own engine fixes, so it starts instantly and leaves the fans alone.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux_Mint_%7C_Ubuntu_%7C_Debian-87cf3e?style=flat-square)](#requirements)
[![Packages](https://img.shields.io/badge/Packages-deb_%7C_AppImage_%7C_Flatpak-cyan?style=flat-square)](../../releases/latest)

Slovenian: [README.sl.md](README.sl.md) · Website: [safeer.si](https://safeer.si)

> **Safeer is a security layer, not a guarantee.** It reduces exposure and blocks known
> threats. It cannot protect against every new or unknown attack.

---

## What it does

**Native GTK4, our own WebKit.** Native GTK4 with WebKitGTK 6.0 — no Electron, no second browser
engine, no background updater. The Flatpak ships WebKitGTK 2.54.1 built with fixes we developed
ourselves ([packaging/webkit](packaging/webkit)): backdrop-filter layers in the Skia compositor no
longer redraw 2ⁿ times, and muted off-screen MediaSource video no longer leaves streams stuck in
"buffering". The fixes are written for upstream WebKit; once WebKitGTK itself has them, our own
build goes away.

**Same engine as Safeer OS.** The browser and the web view in Safeer OS are one code base, so every
improvement to the web lands in both at once.

**Protected video.** Safeer DRM, a small helper started on demand, plays Widevine-protected video
(Netflix, Disney+ …) inside the browser tab while the web engine stays fully sandboxed.

**Local threat shield.** Botnet C2, malware distribution and phishing hosts from abuse.ch
(Feodo Tracker, URLhaus, ThreatFox) and Phishing Army, matched locally in O(k) against a
reverse-domain trie. Nothing about your browsing is sent anywhere to make that decision.
The list arrives as an Ed25519-signed feed after the first start; until it has been
downloaded, only a small built-in fallback list applies.

**Ads and trackers blocked**, third-party cookies blocked, tracking parameters stripped from
links, no telemetry. DuckDuckGo is the default search engine.

**Unwanted pop-ups blocked, sign-in windows kept.** A page can open a window only after your click.
Windows a script opens to another site are blocked with a bar that lets you open them anyway or
always allow that site; sign-in and payment windows (Google, Microsoft, Apple, PayPal, `/login`,
`/oauth` …) and windows of the same site always open, with the opener intact, so "Sign in with …"
works.

**Safe downloads.** Files go to your Downloads folder under the name the server gives, never
overwrite an existing file, and programs or installers (`.deb`, `.AppImage`, `.exe`, `.sh` …) are
downloaded only after you confirm.

**Links to other apps ask first.** `mailto:`, `magnet:`, `zoommtg:` and similar open the program
installed on your computer after you confirm, and the browser can remember "always" per site.

**Encrypted DNS** over HTTPS (your choice of Quad9, AdGuard, Cloudflare, Google, your own server,
or off) with working HTTP/2, and no silent fallback to plaintext DNS when
it fails. Providers reached by name (Quad9, AdGuard) have their own server address looked up
once through the system resolver; Cloudflare and Google are reached by IP. Lookups ask for an IPv4 address (A record) first and
fall back to IPv6 (AAAA) only when a site has no A record; a site that is IPv6-only and cannot be reached
over your network says so instead of failing silently. Names that a custom DoH server (Pi-hole, router)
resolves to home-network addresses are refused unless you turn on "Allow the local network" in the
privacy settings; loopback and cloud-metadata addresses stay refused either way.

**Background playback.** Music and podcasts keep playing when you switch tabs, at a CPU cost
low enough that a laptop stays quiet.

**One-click bookmark import.** Reads Firefox profiles (`places.sqlite`) and Chrome, Brave or
Chromium (`Bookmarks`) directly, merges without duplicates, and also imports Netscape HTML
exports from anything else.

**Keyboard shortcuts you already know.** `Ctrl+T`, `Ctrl+W`, `Ctrl+Shift+T`, `Ctrl+Tab`,
`Ctrl+1`…`Ctrl+9`, `Alt+Home`, and `Ctrl+B` / `Ctrl+Shift+B` for the bookmarks bar and menu.

**A good citizen on the desktop.** Ships AppStream metainfo so it appears properly in the
Software Manager, installs a launcher under Internet, registers as an alternative web browser,
and never grabs the default-browser role behind your back — `safeer --set-default` is there if
you want it.

## Install

[![Release](https://img.shields.io/badge/Release-v1.0.126-2dd4bf?style=flat-square)](../../releases/tag/v1.0.126)

Latest release: **v1.0.126** — [release notes and downloads](../../releases/tag/v1.0.126)

```bash
# Debian, Ubuntu, Linux Mint
sudo apt install ./safeer-browser_1.0.126_all.deb
```


Download from [Releases](../../releases/latest). Three formats are built for every release:

```bash
# Debian / Ubuntu / Linux Mint
sudo apt install ./safeer-browser_<version>_all.deb

# AppImage — no installation, just make it executable
chmod +x Safeer-Browser-<version>-x86_64.AppImage && ./Safeer-Browser-<version>-x86_64.AppImage

# Flatpak
flatpak install ./Safeer-Browser-<version>-x86_64.flatpak
```

Or double-click the `.deb` in your file manager.

Our patched WebKit is in the **Flatpak**; the `.deb` and the AppImage use the system's WebKitGTK 6.0.
When both the `.deb` and the Flatpak are installed, the `safeer` command starts the Flatpak (same
settings, sign-ins and bookmarks). The AppImage and Flatpak are built for x86_64 only. The `.deb` is
architecture-independent (Python on the system's GTK4 and WebKitGTK), but it is not tested on ARM64 for
every release.

Verify what you downloaded against `SHA256SUMS` from the same release:

```bash
sha256sum -c --ignore-missing SHA256SUMS
```

The checksums catch a damaged download. They are not signed yet, so they do not protect
against someone who can replace files in the release itself.

**Safeer Control** — pairs this computer with a Safeer phone or television over your own network —
is part of the single Safeer OS package `safeer-os_<version>_all.deb` in the same release (one
install for Safeer OS, Control and the Safeer Cinnamon look) and does not require the browser. It also brings `safeerctl`, Safeer Link from the command
line (`safeerctl devices`, `safeerctl send file --to DEVICE`, `--json` for scripts): see
[docs/SAFEERCTL.md](docs/SAFEERCTL.md). With a phone running Safeer OS Mobile it can also send this
computer's internet through the phone while the home connection is down — no hotspot needed: see
[docs/INTERNET-GATEWAY.md](docs/INTERNET-GATEWAY.md).

## Requirements

`.deb` and AppImage: Linux Mint 22 or newer, Ubuntu 24.04 or newer, or Debian 13, with GTK4 and
WebKitGTK 6.0 (AppImages are built against glibc 2.39). Older systems such as Linux Mint 21: use the
Flatpak — it brings GTK4 and our WebKit with it.

## Build from source

```bash
bash build_deb.sh                  # Debian package
bash packaging/build_appimage.sh   # AppImage
bash packaging/build_flatpak.sh    # Flatpak
```

Tests (GTK 3 and GTK 4 run in separate processes; details in [CONTRIBUTING.md](CONTRIBUTING.md#running-the-tests)):

```bash
PYTHONPATH=tests xvfb-run -a python3 -m pytest -q $(python3 tools/razdeli_teste.py gtk3 --poti)
PYTHONPATH=tests xvfb-run -a python3 -m pytest -q $(python3 tools/razdeli_teste.py gtk4 --poti)
```

## Fork it

Whoever controls the browser sets the rules of the web. This project is Apache-2.0 so that you
can take it, change the block lists, change the look, add what you need, and ship your own.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security issues go through [SECURITY.md](SECURITY.md),
privately, not in a public issue.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
