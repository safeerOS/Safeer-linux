# Safeer Browser for Linux

A fast, light, privacy-first browser for Linux Mint, Ubuntu and Debian — native GTK4 and
WebKitGTK 6.0 with our own engine fixes, so it starts instantly and leaves the fans alone.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux_Mint_%7C_Ubuntu_%7C_Debian-87cf3e?style=flat-square)](#requirements)
[![Packages](https://img.shields.io/badge/Packages-deb_%7C_Flatpak-cyan?style=flat-square)](../../releases/latest)

Slovenian: [README.sl.md](README.sl.md) · Website: [safeer.si](https://safeer.si)

> **Safeer is a security layer, not a guarantee.** It reduces exposure and blocks known
> threats. It cannot protect against every new or unknown attack.

---

## Current version

| | |
|---|---|
| **Safeer Browser for Linux** | **1.0.132** — tag [`v1.0.132`](../../releases/tag/v1.0.132) |
| **Safeer OS for Linux** (with Safeer Control 2.1.87) | **0.4.90** — same release |
| Versions in the code | `packaging/VERSION`, `packaging/VERSION_OS`, `packaging/VERSION_CONTROL` (checked by `packaging/check_version.py`) |
| What changed | [CHANGELOG.md](CHANGELOG.md) · every version: [docs/releases/](docs/releases/) |
| Download | [safeer.si](https://safeer.si/#prenosi) · [GitHub Releases](../../releases/latest) |

Other editions: Windows 1.0.51 in [safeerOS/Safeer-windows](https://github.com/safeerOS/Safeer-windows) ·
Android TV browser 2.1.215, Safeer OS 0.5.93 for TV, tablet and phone, and Safeer Player 0.2.77 in
[safeerOS/Android-tv](https://github.com/safeerOS/Android-tv) · phone browser in
[safeerOS/Mobile-android](https://github.com/safeerOS/Mobile-android).

## What it does

**Native GTK4, our own WebKit.** Native GTK4 with WebKitGTK 6.0 — no Electron, no second browser
engine, no background updater. The Flatpak and the .deb packages ship WebKitGTK 2.54.2 built with
Clang 22, ThinLTO and profile-guided optimisation (plus BOLT in the .deb), hardened like a
distribution package ([packaging/webkit](packaging/webkit)). Both engine fixes we used to carry are
part of WebKitGTK 2.54.2: backdrop-filter layers in the Skia compositor no longer redraw 2ⁿ times
(our fix, 324100@main), and muted off-screen MediaSource video no longer leaves streams stuck in
"buffering" (323810@main), so the engine is built from unmodified upstream source.

**Same engine as Safeer OS.** The browser and the web view in Safeer OS are one code base, so every
improvement to the web lands in both at once.

**Chats and mail on the side.** A side panel holds web chats and mail (WhatsApp, Messenger,
Telegram, Gmail …) from the same list as Messages in Safeer OS, signed in with the same session as
your tabs and protected by the same shield. Unread counts come from each page's title.

**Protected video.** Safeer DRM, a helper that is part of the package and starts only on demand, plays Widevine-protected video
(Netflix, Disney+ …) inside the browser tab while the web engine stays fully sandboxed. Google's Widevine module is
fetched automatically from Google's servers the first time you play protected video.

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

## Usenet

- Safeer is a client, like a newsreader. You are responsible for your account with your Usenet provider, for the
  content you access and for using it lawfully.
- No NZB indexer is preset and Safeer bundles none. You add your own indexer (Newznab address and API key).
- Any NNTP provider works through one generic setting: server, port, TLS, username, password and number of
  connections.
- With the built-in Usenet engine everything happens on your device: Safeer connects only to your indexer and your
  NNTP provider (TLS by default). Nothing goes to a Safeer server or any other cloud.
- Safeer gives no recommendations about content or providers.

Status: the built-in Usenet engine (NNTP straight from your device) is in development and not yet in a release. Until
then Usenet plays through a debrid service you set up yourself - in that case the NZB file and playback go through
that service.

## Install

[![Release](https://img.shields.io/badge/Release-v1.0.132-2dd4bf?style=flat-square)](../../releases/tag/v1.0.132)

Latest release: **v1.0.132** — [release notes and downloads](../../releases/tag/v1.0.132)

```bash
# Debian, Ubuntu, Linux Mint (one file: our web engine is built in)
sudo apt install ./safeer-browser_1.0.132_amd64.deb
```


Download from [Releases](../../releases/latest). From 1.0.132 every release has the `.deb` and the Flatpak, both with
our own web engine. The AppImage is paused: up to 1.0.131 it carried the WebKitGTK and libsoup of the build system,
not ours; it returns once it carries our web engine.

```bash
# Debian / Ubuntu / Linux Mint (one file: our web engine is built in, from 1.0.129)
sudo apt install ./safeer-browser_<version>_amd64.deb

# Flatpak
flatpak install ./Safeer-Browser-<version>-x86_64.flatpak
```

Or double-click the `.deb` file in your file manager (1.0.128 still had a separate `safeer-webkit` package: install it first).

The `.deb` and the **Flatpak** both carry our own WebKitGTK 2.54 and libsoup 3.8 (Clang ThinLTO build
with Safeer's fixes, `packaging/webkit`, `packaging/webkit-deb`); the `.deb` keeps them in
`/usr/lib/safeer-webkit` (built into every Safeer `.deb`; installed once and shared with Safeer OS: a second Safeer
package detects the same build and does not install it again) and never replaces the system's WebKitGTK. When both the `.deb` and the Flatpak are installed, the
`safeer` command starts the Flatpak (same settings, sign-ins and bookmarks). All packages are built for
x86_64 (amd64) only.

Verify what you downloaded against `SHA256SUMS` from the same release:

```bash
sha256sum -c --ignore-missing SHA256SUMS
```

The checksums catch a damaged download. They are not signed yet, so they do not protect
against someone who can replace files in the release itself.

**Safeer Control** — pairs this computer with a Safeer phone or television over your own network —
is part of both Safeer OS packages in the same release: the desktop environment `safeer-os_<version>_amd64.deb`
(Safeer OS, Control and the Safeer Cinnamon look) and the app in a window for any desktop
`safeer-os-app_<version>_amd64.deb` (Safeer OS and Control); one replaces the other and does not require the browser. It also brings `safeerctl`, Safeer Link from the command
line (`safeerctl devices`, `safeerctl send file --to DEVICE`, `--json` for scripts): see
[docs/SAFEERCTL.md](docs/SAFEERCTL.md). With a phone running Safeer OS Mobile it can also send this
computer's internet through the phone while the home connection is down — no hotspot needed: see
[docs/INTERNET-GATEWAY.md](docs/INTERNET-GATEWAY.md).

**Back to Cinnamon.** Safeer OS Settings → *Back to Cinnamon* (or `safeer-os --nazaj-na-cinnamon` in a terminal,
also when the desktop does not work) stops Safeer OS from starting at sign-in and restores the Mint panel, dock
and look saved before Safeer OS. Nothing is uninstalled and your data stays; open Safeer OS from the menu to come back.

## Requirements

`.deb` and AppImage: Linux Mint 22 or newer, Ubuntu 24.04 or newer, or Debian 13, with GTK4 and
WebKitGTK 6.0 (AppImages are built against glibc 2.39). Older systems such as Linux Mint 21: use the
Flatpak — it brings GTK4 and our WebKit with it.

From a source checkout, `bash install.sh` installs the same GTK4 browser (`safeer_brskalnik.py`) for
the current user and checks the same packages as the `.deb`; `bash uninstall.sh` removes it
(`--purge` also removes the profile).

## Build from source

```bash
bash build_deb.sh                  # Debian package
bash packaging/build_appimage.sh   # AppImage
bash packaging/build_flatpak.sh    # Flatpak
```

Tests (one process, GTK 4 only; details in [CONTRIBUTING.md](CONTRIBUTING.md#running-the-tests)):

```bash
PYTHONPATH=tests xvfb-run -a python3 -m pytest -q tests/
```

## Fork it

Whoever controls the browser sets the rules of the web. This project is Apache-2.0 so that you
can take it, change the block lists, change the look, add what you need, and ship your own.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security issues go through [SECURITY.md](SECURITY.md),
privately, not in a public issue.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
