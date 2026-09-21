# Safeer Browser for Linux

A fast, light, privacy-first browser for Linux Mint, Ubuntu and Debian — GTK3 and WebKit2GTK,
so it starts instantly and leaves the fans alone.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux_Mint_%7C_Ubuntu_%7C_Debian-87cf3e?style=flat-square)](#requirements)
[![Packages](https://img.shields.io/badge/Packages-deb_%7C_AppImage_%7C_Flatpak-cyan?style=flat-square)](../../releases/latest)

Slovenian: [README.sl.md](README.sl.md) · Website: [safeer.si](https://safeer.si)

> **Safeer is a security layer, not a guarantee.** It reduces exposure and blocks known
> threats. It cannot protect against every new or unknown attack.

---

## What it does

**Starts fast and stays light.** Native GTK3 with WebKit2GTK — no Electron, no second browser
engine, no background updater.

**Local threat shield.** Botnet C2, malware distribution and phishing hosts from abuse.ch
(Feodo Tracker, URLhaus, ThreatFox) and Phishing Army, matched locally in O(k) against a
reverse-domain trie. Nothing about your browsing is sent anywhere to make that decision.
The list arrives as an Ed25519-signed feed after the first start; until it has been
downloaded, only a small built-in fallback list applies.

**Ads and trackers blocked**, third-party cookies blocked, tracking parameters stripped from
links, no telemetry. DuckDuckGo is the default search engine.

**Encrypted DNS** over HTTPS with working HTTP/2, and no silent fallback to plaintext DNS when
it fails. Providers reached by name (Quad9, AdGuard) have their own server address looked up
once through the system resolver; Cloudflare and Google are reached by IP. Lookups are IPv4
(A records) for now.

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

[![Release](https://img.shields.io/badge/Release-v1.0.45-2dd4bf?style=flat-square)](../../releases/tag/v1.0.45)

Latest release: **v1.0.45** — [release notes and downloads](../../releases/tag/v1.0.45)

```bash
# Debian, Ubuntu, Linux Mint
sudo apt install ./safeer-browser_1.0.45_all.deb
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

The AppImage and Flatpak are built for x86_64 only. The `.deb` is architecture-independent
(Python on the system's GTK and WebKit2GTK), but it is not tested on ARM64 for every release.

Verify what you downloaded against `SHA256SUMS` from the same release:

```bash
sha256sum -c --ignore-missing SHA256SUMS
```

The checksums catch a damaged download. They are not signed yet, so they do not protect
against someone who can replace files in the release itself.

**Safeer Control** — the companion desktop app that pairs this computer with a Safeer phone or
television over your own network — ships as `safeer-control_<version>_all.deb` in the same
release and does not require the browser.

## Requirements

A current Linux Mint, Ubuntu or Debian with GTK3 and WebKit2GTK. Release AppImages are built
against glibc 2.35 (Ubuntu 22.04) so they keep running on older systems.

## Build from source

```bash
bash build_deb.sh                  # Debian package
bash packaging/build_appimage.sh   # AppImage
bash packaging/build_flatpak.sh    # Flatpak
```

Tests:

```bash
python3 -m unittest discover -s tests
```

## Fork it

Whoever controls the browser sets the rules of the web. This project is Apache-2.0 so that you
can take it, change the block lists, change the look, add what you need, and ship your own.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Security issues go through [SECURITY.md](SECURITY.md),
privately, not in a public issue.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
