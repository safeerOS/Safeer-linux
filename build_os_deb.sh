#!/usr/bin/env bash
# ==============================================================================
# Safeer OS (Linux) — Debian / Ubuntu / Linux Mint .deb Package Builder
# Produces safeer-os_<version>_all.deb. Depends on safeer-control (Safeer Link, devices, D-Bus).
# ==============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_NAME="safeer-os"
VERSION="$(cat "$DIR/packaging/VERSION_OS")"
CONTROL_VERSION="$(cat "$DIR/packaging/VERSION_CONTROL")"
ARCH="all"
DEB_PACKAGE="${PKG_NAME}_${VERSION}_${ARCH}.deb"
STAGE="$DIR/build/stage-os"
BUILD_ROOT="$DIR/build/deb-os"

echo "=========================================================="
echo "📦 Gradnja Debian paketa: $DEB_PACKAGE"
echo "=========================================================="

rm -rf "$STAGE" "$BUILD_ROOT"
bash "$DIR/packaging/install_os_payload.sh" "$STAGE/usr"
mkdir -p "$BUILD_ROOT/DEBIAN"
cp -a "$STAGE/usr" "$BUILD_ROOT/"
sed -i 's|^Exec=safeer-os|Exec=/usr/bin/safeer-os|' "$BUILD_ROOT/usr/share/applications/safeer-os.desktop"

cat << EOF2 > "$BUILD_ROOT/DEBIAN/control"
Package: safeer-os
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: safeer-control (>= ${CONTROL_VERSION}), python3, python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, gir1.2-webkit2-4.1, gir1.2-glib-2.0, gir1.2-secret-1
Recommends: network-manager, pulseaudio-utils, policykit-1, xdg-utils, gir1.2-wnck-3.0, x11-utils, gir1.2-gstreamer-1.0, gstreamer1.0-plugins-good, gstreamer1.0-plugins-bad, gstreamer1.0-libav, gstreamer1.0-gtk3
Maintainer: Safeer <info@safeer.si>
Homepage: https://safeer.si/os/
Description: Safeer OS - your computer in your hands, on top of Linux Mint
 Safeer OS is a full-screen shell over your existing desktop: programs,
 files, devices, network, sound and settings in one place, made for a
 TV-like experience with the keyboard, mouse or the remote of a Safeer
 device. Through Safeer Link it opens apps of your phone, tablet and TV,
 plays your computer's sound on them and shares files - at home, without
 the cloud and without an account. Shield: DNS filtering of ads, trackers
 and dangerous domains for the whole computer. Linux Mint stays underneath:
 one click returns you to the Mint desktop.
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
# Byte-compile once, as root. A user cannot write into /usr/lib, so without this Python would compile every
# module again at each start. If it fails, the program still runs from source.
if [ -x /usr/bin/python3 ]; then
    /usr/bin/python3 -m compileall -q /usr/lib/safeer-os >/dev/null 2>&1 || true
fi
exit 0
EOF2
cat << 'EOF2' > "$BUILD_ROOT/DEBIAN/prerm"
#!/bin/sh
# dpkg runs maintainer scripts with /bin/sh (dash): POSIX options only.
set -eu
# Remove the byte-code that postinst compiled (and what Python wrote when the program was run as root). dpkg does
# not know these files; with them it would leave /usr/lib/safeer-os behind after removal.
if [ -d /usr/lib/safeer-os ] && [ -x /usr/bin/find ]; then
    /usr/bin/find /usr/lib/safeer-os -depth \( -name '*.pyc' -o -name __pycache__ \) -delete 2>/dev/null || true
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
chmod 755 "$BUILD_ROOT/DEBIAN/postinst" "$BUILD_ROOT/DEBIAN/prerm" "$BUILD_ROOT/DEBIAN/postrm"
find "$BUILD_ROOT" -type d -exec chmod 755 {} +
chmod 755 "$BUILD_ROOT/usr/bin/safeer-os"
for script in "$BUILD_ROOT/DEBIAN/postinst" "$BUILD_ROOT/DEBIAN/prerm" "$BUILD_ROOT/DEBIAN/postrm"; do
    if command -v dash >/dev/null 2>&1; then dash -n "$script"; else sh -n "$script"; fi
done

echo "🔨 Izdelava paketa z dpkg-deb..."
dpkg-deb --build --root-owner-group "$BUILD_ROOT" "$DIR/$DEB_PACKAGE"
echo "✅ $DIR/$DEB_PACKAGE"
dpkg-deb -I "$DIR/$DEB_PACKAGE"
