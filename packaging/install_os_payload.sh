#!/usr/bin/env bash
# Safeer OS (Linux) payload: the Safeer OS shell for the desktop (safeer_os.py, its core modules and
# the page in assets/os). It talks to Safeer Control over D-Bus and starts it when needed, so a
# package built from this payload depends on the Safeer Control payload (deb: safeer-control;
# AppImage and Flatpak: both payloads in one bundle).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${1:?Usage: install_os_payload.sh DESTINATION_PREFIX [desktop-id]}"
ID="${2:-safeer-os}"
LIB="$PREFIX/lib/safeer-os"
mkdir -p "$PREFIX/bin" "$LIB/core" "$LIB/assets" "$LIB/packaging" "$PREFIX/share/applications" "$PREFIX/share/metainfo" "$PREFIX/share/pixmaps"
cp -a "$ROOT/safeer_os.py" "$LIB/"
# Everything safeer_os.py imports, directly or lazily (core/os_* plus the Safeer Link modules it reads:
# identity, sessions, circle of trust, hub discovery, programs). tests/test_packaging.py installs this
# payload and imports it without the source tree, so a missing module fails the test, not the user.
for modul in os_datoteke os_jbl os_okna os_omrezje os_programi os_scit os_sistem os_stabilnost os_zvok \
             link_datoteke link_urejanje link_hub link_krog link_programi link_seja link_tls spake2 signed_feed threat_intel; do
    cp -a "$ROOT/core/$modul.py" "$LIB/core/"
done
[ -f "$ROOT/core/__init__.py" ] && cp -a "$ROOT/core/__init__.py" "$LIB/core/" || true
cp -a "$ROOT/assets/os" "$LIB/assets/"
cp -a "$ROOT/packaging/VERSION_OS" "$LIB/packaging/"
find "$LIB" -type d -name __pycache__ -exec rm -rf {} +
find "$LIB" -name '*.pyc' -delete
install -m755 "$ROOT/packaging/safeer-os-launcher" "$PREFIX/bin/safeer-os"
install -Dm644 "$ROOT/LICENSE" "$PREFIX/share/doc/safeer-os/LICENSE"
sed "s/^Icon=.*/Icon=$ID/" "$ROOT/packaging/safeer-os.desktop" > "$PREFIX/share/applications/$ID.desktop"
sed "s|safeer-os.desktop|$ID.desktop|" "$ROOT/io.github.memelandfaner.SafeerOS.metainfo.xml" > "$PREFIX/share/metainfo/io.github.memelandfaner.SafeerOS.metainfo.xml"
install -Dm644 "$ROOT/assets/os/znak.svg" "$PREFIX/share/icons/hicolor/scalable/apps/$ID.svg"
install -m644 "$ROOT/assets/icon.png" "$PREFIX/share/pixmaps/$ID.png"
for icon in "$ROOT/packaging/icons/hicolor"/*/apps/safeer-browser.png; do
    size=$(basename "$(dirname "$(dirname "$icon")")")
    install -Dm644 "$icon" "$PREFIX/share/icons/hicolor/$size/apps/$ID.png"
done
