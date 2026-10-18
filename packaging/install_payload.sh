#!/usr/bin/env bash
# Safeer Browser payload (.deb, Flatpak, AppImage): od 14. 10. 2026 brskalnik na GTK4 in WebKitGTK 6.0
# (safeer_brskalnik.py: Splet iz core/os_splet.py v svojem oknu, ena koda s Spletom v Safeer OS).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${1:?Usage: install_payload.sh DESTINATION_PREFIX [desktop-id]}"
ID="${2:-safeer-browser}"
LIB="$PREFIX/lib/safeer-browser"
VSTOP=safeer_brskalnik.py
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
sed "s|safeer-browser.desktop|$ID.desktop|" "$ROOT/io.github.memelandfaner.SafeerBrowser.metainfo.xml" > "$PREFIX/share/metainfo/io.github.memelandfaner.SafeerBrowser.metainfo.xml"
# Svoja ikona (globus z »S«, assets/brskalnik.svg), ne scit Safeer OS: lastnik, 17. 10. 2026 - »uporabnik mora na hitro
# lociti«. PNG v packaging/icons/hicolor so izrisani iz iste SVG (tools/izrisi_ikone.py).
install -Dm644 "$ROOT/assets/brskalnik.svg" "$PREFIX/share/icons/hicolor/scalable/apps/$ID.svg"
install -m644 "$ROOT/packaging/icons/hicolor/256x256/apps/safeer-browser.png" "$PREFIX/share/pixmaps/$ID.png"
for icon in "$ROOT/packaging/icons/hicolor"/*/apps/safeer-browser.png; do
    size=$(basename "$(dirname "$(dirname "$icon")")")
    install -Dm644 "$icon" "$PREFIX/share/icons/hicolor/$size/apps/$ID.png"
done
