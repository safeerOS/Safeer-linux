#!/usr/bin/env bash
# Safeer Browser payload (.deb, Flatpak, AppImage): od 14. 10. 2026 brskalnik na GTK4 in WebKitGTK 6.0
# (safeer_brskalnik.py: Splet iz core/os_splet.py v svojem oknu, ena koda s Spletom v Safeer OS).
# SAFEER_BRSKALNIK_GTK3=1: prejsnji brskalnik (safeer_mint.py, GTK3, WebKit2GTK 4.1) za posel deb-appimage na
# Ubuntu 22.04 (Mint 21 WebKitGTK 6.0 nima), dokler ga ne umaknemo.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${1:?Usage: install_payload.sh DESTINATION_PREFIX [desktop-id]}"
ID="${2:-safeer-browser}"
LIB="$PREFIX/lib/safeer-browser"
if [ "${SAFEER_BRSKALNIK_GTK3:-0}" = 1 ]; then VSTOP=safeer_mint.py; else VSTOP=safeer_brskalnik.py; fi
mkdir -p "$PREFIX/bin" "$LIB/packaging" "$PREFIX/share/applications" "$PREFIX/share/metainfo" "$PREFIX/share/pixmaps"
# Cel core/ (ne seznam kot pri Safeer OS): brskalnik uvozi os_splet in z njim ~30 modulov, tudi lene (zgodovina,
# uvoz zavihkov, Safeer DRM) - z mapo ne more manjkati noben (tests/test_tovor_uvozi.py preveri prehodne uvoze).
cp -a "$ROOT/$VSTOP" "$ROOT/core" "$ROOT/ui" "$ROOT/assets" "$LIB/"
# --version in sporocila o napakah berejo razlicico iz packaging/VERSION (safeer_brskalnik.razlicica()).
cp -a "$ROOT/packaging/VERSION" "$LIB/packaging/"
# Interni poskus (preklop vhoda JBL) ne gre v uradni paket - kot v install_os_payload.sh.
rm -f "$LIB/core/os_jbl.py"
find "$LIB" -type d -name __pycache__ -exec rm -rf {} +
find "$LIB" -name '*.pyc' -delete
install -m755 "$ROOT/packaging/safeer-launcher" "$PREFIX/bin/safeer"
install -Dm644 "$ROOT/LICENSE" "$PREFIX/share/doc/safeer-browser/LICENSE"
ln -sf safeer "$PREFIX/bin/safeer-browser"
sed "s/^Icon=.*/Icon=$ID/" "$ROOT/packaging/safeer-browser.desktop" > "$PREFIX/share/applications/$ID.desktop"
if [ "$VSTOP" = safeer_mint.py ]; then
    # GTK3 brskalnik sam nastavi WM_CLASS safeer-browser (safeer_mint.py, set_wmclass).
    sed -i "s/^StartupWMClass=.*/StartupWMClass=safeer-browser/" "$PREFIX/share/applications/$ID.desktop"
fi
sed "s|safeer-browser.desktop|$ID.desktop|" "$ROOT/io.github.memelandfaner.SafeerBrowser.metainfo.xml" > "$PREFIX/share/metainfo/io.github.memelandfaner.SafeerBrowser.metainfo.xml"
install -m644 "$ROOT/assets/icon.png" "$PREFIX/share/pixmaps/$ID.png"
for icon in "$ROOT/packaging/icons/hicolor"/*/apps/safeer-browser.png; do
    size=$(basename "$(dirname "$(dirname "$icon")")")
    install -Dm644 "$icon" "$PREFIX/share/icons/hicolor/$size/apps/$ID.png"
done
