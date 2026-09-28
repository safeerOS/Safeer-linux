#!/usr/bin/env bash
# ==============================================================================
# Safeer OS tema (Linux Mint) — .deb: Safeer OS kot namizje nad Linux Mint.
# Tema Safeer-OS (GTK 3/4, okna, Cinnamon), samodejni zagon ob prijavi (safeer-os --namizje)
# in "Vrni Linux Mint". Program sam je v paketu safeer-os (ta se odpre tudi v oknu).
# ==============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(cat "$DIR/packaging/VERSION_OS")"
DEB_PACKAGE="safeer-os-tema_${VERSION}_all.deb"
ROOT="$DIR/build/deb-os-tema"
T="$DIR/packaging/tema"

rm -rf "$ROOT"
mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/share/themes" "$ROOT/usr/bin" "$ROOT/etc/xdg/autostart" \
         "$ROOT/usr/share/applications" "$ROOT/usr/share/doc/safeer-os-tema"
cp -a "$T/Safeer-OS" "$ROOT/usr/share/themes/"
install -D -m 644 "$T/ozadje/safeer-gore.jpg" "$ROOT/usr/share/backgrounds/safeer-os/safeer-gore.jpg"
install -m 755 "$T/safeer-os-tema" "$ROOT/usr/bin/safeer-os-tema"
install -m 644 "$T/safeer-os-tema-autostart.desktop" "$ROOT/etc/xdg/autostart/safeer-os-tema.desktop"
install -m 644 "$T/safeer-os-namizje.desktop" "$ROOT/usr/share/applications/safeer-os-namizje.desktop"
install -m 644 "$T/safeer-os-vrni-mint.desktop" "$ROOT/usr/share/applications/safeer-os-vrni-mint.desktop"
install -m 644 "$T/COPYING.tema" "$ROOT/usr/share/doc/safeer-os-tema/copyright"

cat > "$ROOT/DEBIAN/control" <<EOF2
Package: safeer-os-tema
Version: ${VERSION}
Section: x11
Priority: optional
Architecture: all
Depends: safeer-os (>= ${VERSION}), libglib2.0-bin
Recommends: cinnamon
Maintainer: Safeer <info@safeer.si>
Homepage: https://safeer.si/os/
Description: Safeer OS as your desktop over Linux Mint
 Makes Safeer OS your desktop: the Safeer-OS theme for GTK, window borders
 and Cinnamon, and Safeer OS starts full-screen when you log in, with its own
 bottom bar instead of the Mint panel. Linux Mint stays underneath: "Return to
 Linux Mint" in the menu (or safeer-os-tema --izklopi) restores your previous
 look and turns the start-up off.
EOF2
chmod 644 "$ROOT/DEBIAN/control"
find "$ROOT" -type d -exec chmod 755 {} +
find "$ROOT/usr/share/themes" -type f -exec chmod 644 {} +

dpkg-deb --root-owner-group --build "$ROOT" "$DIR/$DEB_PACKAGE"
echo "OK: $DEB_PACKAGE"
