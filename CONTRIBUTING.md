# Contributing to Safeer

*Slovenščina: [CONTRIBUTING.sl.md](CONTRIBUTING.sl.md)*

Thank you for taking the time. Safeer is Apache-2.0, built by a small team, and every patch,
bug report and translation fix is read by a person. We would rather help you land your first
change than receive a perfect one.

## The one rule that is not negotiable

**No per-site recipes.** Safeer must not contain code written for one named website: no
`if (hostname === "example.com")`, no `site_example.js`, no selector list copied from one
page's markup. Everything works by what a page *is* — its markup, its stream format, its
request pattern — not by who publishes it.

This is not style. It is the promise the product makes: your sites work, not just ours. A
build guard (`tests/test_brez_receptov_za_strani.py`) enforces it and will fail your build. The only standing exception is YouTube, whose own player and ad pipeline are a product feature, not a fix for one page. If a site is broken, the right patch is a
generic rule that fixes that whole class of sites, and a test that proves it.

Bookmarks, start-page tiles and voice shortcuts are not adaptations — those are just entries
in a list, and they are fine.

## Where to start

- **Issues labelled `good first issue`** are scoped so that one evening is enough, and each one
  names the files to read first.
- **Translations.** The interface ships in Slovenian, English, German, Spanish, French and
  Italian. If one of those is your language, reading the `BESEDILA` / `TEXTS` dictionaries in
  `core/` and fixing what sounds wrong is one of the most useful things you can do.
- **Bugs you hit yourself.** A precise report with steps to reproduce is a contribution on its own.

Not sure if an idea fits? Open an issue first and ask — that is cheaper for both of us than a
large pull request in the wrong direction.

## Development setup

New work happens on the **`gtk4`** branch (GTK 4, WebKitGTK 6.0, Qt Quick for the Safeer OS
shell). Linux Mint 22 or Ubuntu 24.04 is the reference system.

```bash
git clone https://github.com/safeerOS/Safeer-linux.git
cd Safeer-linux && git switch gtk4

sudo apt install python3-gi python3-gi-cairo python3-pytest python3-cryptography \
  gir1.2-gtk-4.0 gir1.2-gtk-3.0 gir1.2-webkit-6.0 gir1.2-webkit2-4.1 gir1.2-soup-3.0 \
  gir1.2-secret-1 gir1.2-gstreamer-1.0 gstreamer1.0-plugins-good gstreamer1.0-plugins-bad \
  gstreamer1.0-libav glib-networking xvfb

python3 safeer_brskalnik.py        # Safeer Browser (GTK 4)
python3 safeer_os.py               # Safeer OS shell
```

### Running the tests

GTK 3 and GTK 4 cannot be loaded into the same Python process, so the suite is split into two
groups. `tools/razdeli_teste.py` picks the group from each test's imports:

```bash
PYTHONPATH=tests xvfb-run -a python3 -m unittest $(python3 tools/razdeli_teste.py gtk3)
PYTHONPATH=tests xvfb-run -a python3 -m unittest $(python3 tools/razdeli_teste.py gtk4)
```

The `gtk4` group also needs PySide6 for the Qt Quick shell (`pip install PySide6`, or
`python3 packaging/pyside6_vendor.py build/vendor` and add `build/vendor` to `PYTHONPATH`, as
CI does). One test file at a time is fine while you work:
`xvfb-run -a python3 -m pytest -q tests/test_pojavna_okna.py`.

## How the code is organised

- `core/` — shared modules. Logic that does not need a window (download naming, pop-up rules,
  tracking-protection levels, site permissions …) lives in GTK-free modules here, so the
  browser, Safeer OS and their tests share one implementation.
- `safeer_brskalnik.py` — Safeer Browser (GTK 4). `safeer_mint.py` — the older GTK 3 browser.
- `safeer_os.py`, `assets/os/` — the Safeer OS shell (QML, HTML/JS panels, `os.css` holds all
  colours and themes).
- `packaging/` — .deb, AppImage, Flatpak (the Flatpak carries our patched WebKitGTK).
- A new module in `core/` must be added to `packaging/install_os_payload.sh` or
  `install_control_payload.sh`; `tests/test_tovor_uvozi.py` checks it.

Identifiers and comments are mostly in Slovenian, because that is the team's language. You do
not have to write Slovenian: English comments and commit messages are welcome. If a Slovenian
name is unclear, ask in the issue — we will explain, and maybe rename it.

## Before you open a pull request

- Run the tests. A red suite is not ready.
- Keep the change focused. One problem per pull request reviews far faster than five.
- Explain the *why* in the commit message. What was broken, how you know it is fixed, and on
  which device or distribution you saw it work.
- New behaviour needs a test. A bug fix without a failing-then-passing test tends to come back.
- User-visible text goes into every language the file already has. If you cannot translate
  one, write English there and say so in the pull request; we will fill it in.
- No placeholders in the interface: a button that does nothing yet does not ship.
- Never commit personal data — names, home paths, host names, e-mail addresses, keys or
  tokens. `tests/test_brez_skrivnosti.py` checks for common secrets.

## Reporting a bug

Open an issue with: what you did, what you expected, what happened, the version (Settings, or
`safeer --version` on Linux), and the device or distribution. For a rendering problem, the URL
matters — if the page is private, a screenshot and the page's framework are usually enough.

**Security issues do not go in the issue tracker.** See [SECURITY.md](SECURITY.md).

## Fixes we send upstream

When a bug turns out to be in a project we build on — WebKitGTK, libsoup, GStreamer,
Cinnamon — we fix it there too, with a test, and report it to its maintainers. The patched
WebKitGTK in our Flatpak and a libsoup connection-leak fix reported to Ubuntu came out of this. If you
find such a bug while working on Safeer, the upstream report and patch are as welcome as a
patch here, and we are happy to help you write them.

## Claims must be true

If your change alters what the browser does, update the README in the same pull request. We do
not ship documentation that promises something the code does not do, and we do not name a
version number in prose where a link to the release will stay correct on its own.

## Code of conduct

Participation is covered by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
