#!/usr/bin/env bash
# ==============================================================================
# Safeer Control — Debian / Ubuntu / Linux Mint .deb Package Builder
# Produces safeer-control_<version>_all.deb (desktop app; no browser required).
# ==============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_NAME="safeer-control"
VERSION="$(cat "$DIR/packaging/VERSION_CONTROL")"
ARCH="all"
DEB_PACKAGE="${PKG_NAME}_${VERSION}_${ARCH}.deb"
STAGE="$DIR/build/stage-control"
BUILD_ROOT="$DIR/build/deb-control"

echo "=========================================================="
echo "📦 Gradnja Debian paketa: $DEB_PACKAGE"
echo "=========================================================="

rm -rf "$STAGE" "$BUILD_ROOT"
bash "$DIR/packaging/install_control_payload.sh" "$STAGE/usr"
mkdir -p "$BUILD_ROOT/DEBIAN"
cp -a "$STAGE/usr" "$BUILD_ROOT/"
sed -i 's|^Exec=safeer-control|Exec=/usr/bin/safeer-control|' "$BUILD_ROOT/usr/share/applications/safeer-control.desktop"

cat << EOF2 > "$BUILD_ROOT/DEBIAN/control"
Package: safeer-control
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: python3, python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, gir1.2-webkit2-4.1, gir1.2-soup-3.0, gir1.2-glib-2.0, gir1.2-atspi-2.0, sway, wf-recorder, wtype, wmctrl
Recommends: pulseaudio-utils
Maintainer: Safeer <info@safeer.si>
Homepage: https://safeer.si/control/
Description: Control your TV and phone over Safeer Link, without the cloud
 Safeer Control is a small desktop app with Safeer Link built in. Pair it with
 the Safeer Link on your home network with a 6-digit code and control your
 Android TV and phone from this computer: voice commands, remote keys, app
 launching, volume, screenshots, and sharing of text, files and your screen.
 Everything stays on your home network; no account, no cloud, no browser needed.
EOF2
chmod 644 "$BUILD_ROOT/DEBIAN/control"

cat << 'EOF2' > "$BUILD_ROOT/DEBIAN/postinst"
#!/bin/sh
set -eu
if [ -x /usr/bin/update-desktop-database ]; then
    /usr/bin/update-desktop-database -q /usr/share/applications || true
fi
if [ -x /usr/bin/gtk-update-icon-cache ]; then
    /usr/bin/gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
exit 0
EOF2
cat << 'EOF2' > "$BUILD_ROOT/DEBIAN/postrm"
#!/bin/sh
set -eu
if [ "${1:-}" = "remove" ] || [ "${1:-}" = "purge" ]; then
    if [ -x /usr/bin/update-desktop-database ]; then
        /usr/bin/update-desktop-database -q /usr/share/applications || true
    fi
    if [ -x /usr/bin/gtk-update-icon-cache ]; then
        /usr/bin/gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
    fi
fi
exit 0
EOF2
chmod 755 "$BUILD_ROOT/DEBIAN/postinst" "$BUILD_ROOT/DEBIAN/postrm"
find "$BUILD_ROOT" -type d -exec chmod 755 {} +
chmod 755 "$BUILD_ROOT/usr/bin/safeer-control"
for script in "$BUILD_ROOT/DEBIAN/postinst" "$BUILD_ROOT/DEBIAN/postrm"; do
    if command -v dash >/dev/null 2>&1; then dash -n "$script"; else sh -n "$script"; fi
done

echo "🔨 Izdelava paketa z dpkg-deb..."
dpkg-deb --build --root-owner-group "$BUILD_ROOT" "$DIR/$DEB_PACKAGE"
echo "✅ $DIR/$DEB_PACKAGE"
dpkg-deb -I "$DIR/$DEB_PACKAGE"
