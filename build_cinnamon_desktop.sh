#!/usr/bin/env bash
# ==============================================================================
# Safeer Cinnamon Desktop — Unified Debian .deb Package Builder + Transitional Packages
# Combines Safeer OS, Safeer Control, Safeer Player, and Cinnamon Theme into ONE package.
# Main package: safeer-cinnamon-desktop_0.5.0_all.deb
# Transitional packages: safeer-os_0.5.0_all.deb, safeer-control_2.2.0_all.deb, etc.
# ==============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_NAME="safeer-cinnamon-desktop"
VERSION="0.5.0"
ARCH="all"
OUT_DIR="$(cd "$DIR/.." && pwd)"
DEB_PACKAGE="${PKG_NAME}_${VERSION}_${ARCH}.deb"

BUILD_ROOT="$DIR/build/deb-unified"

echo "=========================================================="
echo "📦 Gradnja enotnega Debian paketa: $DEB_PACKAGE (v$VERSION)"
echo "=========================================================="

rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT/DEBIAN"

# 1. Namestitev Safeer Control tovora
bash "$DIR/packaging/install_control_payload.sh" "$BUILD_ROOT/usr"

# 2. Namestitev Safeer OS tovora
bash "$DIR/packaging/install_os_payload.sh" "$BUILD_ROOT/usr"

# 3. Namestitev Teme (Safeer OS / Cinnamon)
T_CINNAMON="$DIR/packaging/tema-cinnamon"
T_OS="$DIR/packaging/tema"

mkdir -p "$BUILD_ROOT/usr/share/themes" "$BUILD_ROOT/etc/xdg/autostart" \
         "$BUILD_ROOT/usr/share/backgrounds/safeer" "$BUILD_ROOT/usr/share/cinnamon-background-properties"

if [ -d "$T_CINNAMON/Safeer-Cinnamon" ]; then
    cp -a "$T_CINNAMON/Safeer-Cinnamon" "$T_CINNAMON/Safeer-Cinnamon-Kontrast" "$BUILD_ROOT/usr/share/themes/"
fi

if [ -d "$T_OS/Safeer-OS" ]; then
    cp -a "$T_OS/Safeer-OS" "$BUILD_ROOT/usr/share/themes/"
fi

# Pristaniški pult in ozadja
if [ -d "$T_CINNAMON/ozadje" ]; then
    cp -a "$T_CINNAMON"/ozadje/* "$BUILD_ROOT/usr/share/backgrounds/safeer/" 2>/dev/null || true
fi

# Zagonska skripta teme in autostart
install -m 755 "$T_OS/safeer-os-tema" "$BUILD_ROOT/usr/bin/safeer-os-tema"
install -m 644 "$T_OS/safeer-os-tema-autostart.desktop" "$BUILD_ROOT/etc/xdg/autostart/safeer-os-tema.desktop"

# Popravek poti Exec v .desktop datotekah
sed -i 's|^Exec=safeer-os|Exec=/usr/bin/safeer-os|' "$BUILD_ROOT/usr/share/applications/safeer-os.desktop" 2>/dev/null || true
sed -i 's|^Exec=safeer-control|Exec=/usr/bin/safeer-control|' "$BUILD_ROOT/usr/share/applications/safeer-control.desktop" 2>/dev/null || true
# Odločitev lastnika: v meniju je natanko EN vnos (Safeer OS), Safeer Control okno je dostopno iz Safeer OS
if grep -q '^NoDisplay=' "$BUILD_ROOT/usr/share/applications/safeer-control.desktop" 2>/dev/null; then
    sed -i 's|^NoDisplay=.*|NoDisplay=true|' "$BUILD_ROOT/usr/share/applications/safeer-control.desktop"
else
    echo "NoDisplay=true" >> "$BUILD_ROOT/usr/share/applications/safeer-control.desktop"
fi

# Generiranje DEBIAN/control z zamenjavo starih paketov (Replaces/Breaks/Provides)
# Opomba: mint-themes premaknjen v Recommends / alternativno odvisnost zaradi Ubuntu Cinnamon združljivosti.
cat << EOF2 > "$BUILD_ROOT/DEBIAN/control"
Package: ${PKG_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Replaces: safeer-os (<< 0.5.0), safeer-control (<< 2.2.0), safeer-os-tema (<< 0.5.0), safeer-cinnamon (<< 1.3.0)
Breaks: safeer-os (<< 0.5.0), safeer-control (<< 2.2.0), safeer-os-tema (<< 0.5.0), safeer-cinnamon (<< 1.3.0)
Provides: safeer-os, safeer-control, safeer-os-tema, safeer-cinnamon
Depends: python3, python3-cryptography, python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, gir1.2-webkit2-4.1, gir1.2-soup-3.0, gir1.2-glib-2.0, gir1.2-secret-1, gir1.2-gstreamer-1.0, gir1.2-atspi-2.0, gstreamer1.0-gtk3, gstreamer1.0-libav, gstreamer1.0-plugins-bad, gstreamer1.0-plugins-base, python3-qrcode, dconf-cli
Recommends: mint-themes | yaru-theme-gtk, network-manager, pulseaudio-utils, policykit-1, xdg-utils, gir1.2-wnck-3.0, x11-utils, cinnamon, plank, python3-pil
Maintainer: Safeer <info@safeer.si>
Homepage: https://safeer.si/os/
Description: Safeer Desktop Environment on Linux Mint & Ubuntu Cinnamon
 Unified package containing Safeer OS, Safeer Control, Safeer Player, and the
 Safeer Cinnamon theme into one sovereign desktop experience.
EOF2
chmod 644 "$BUILD_ROOT/DEBIAN/control"

# Maintainer skripte
cat << 'EOF2' > "$BUILD_ROOT/DEBIAN/postinst"
#!/bin/sh
set -eu
if [ -x /usr/bin/update-desktop-database ]; then
    /usr/bin/update-desktop-database -q /usr/share/applications || true
fi
if [ -x /usr/bin/gtk-update-icon-cache ]; then
    /usr/bin/gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi
if [ -x /usr/bin/python3 ]; then
    /usr/bin/python3 -m compileall -q /usr/lib/safeer-control >/dev/null 2>&1 || true
    /usr/bin/python3 -m compileall -q /usr/lib/safeer-os >/dev/null 2>&1 || true
fi
exit 0
EOF2

cat << 'EOF2' > "$BUILD_ROOT/DEBIAN/prerm"
#!/bin/sh
set -eu
if [ -d /usr/lib/safeer-control ] && [ -x /usr/bin/find ]; then
    /usr/bin/find /usr/lib/safeer-control -depth \( -name '*.pyc' -o -name __pycache__ \) -delete 2>/dev/null || true
fi
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

for script in "$BUILD_ROOT/DEBIAN/postinst" "$BUILD_ROOT/DEBIAN/prerm" "$BUILD_ROOT/DEBIAN/postrm"; do
    if command -v dash >/dev/null 2>&1; then dash -n "$script"; else sh -n "$script"; fi
done

echo "🔨 Izdelava enotnega paketa z dpkg-deb..."
dpkg-deb --build --root-owner-group "$BUILD_ROOT" "$OUT_DIR/$DEB_PACKAGE"
echo "✅ Paket uspešno zgrajen: $OUT_DIR/$DEB_PACKAGE"

# ==============================================================================
# Gradnja PREHODNIH PAKETOV (Transitional Dummy Packages)
# ==============================================================================
zgradi_prehodni() {
    local p_ime="$1"
    local p_ver="$2"
    local p_root="$DIR/build/deb-prehodni-$p_ime"
    local p_deb="${p_ime}_${p_ver}_all.deb"

    rm -rf "$p_root"
    mkdir -p "$p_root/DEBIAN"

    cat << EOF > "$p_root/DEBIAN/control"
Package: ${p_ime}
Version: ${p_ver}
Section: oldlibs
Priority: optional
Architecture: all
Depends: safeer-cinnamon-desktop (>= ${VERSION})
Maintainer: Safeer <info@safeer.si>
Description: Transitional dummy package for ${p_ime} -> safeer-cinnamon-desktop
 This is a transitional dummy package to automatically upgrade existing installs
 of ${p_ime} to the unified safeer-cinnamon-desktop package. It can be safely removed.
EOF
    chmod 644 "$p_root/DEBIAN/control"

    cat << 'EOF' > "$p_root/DEBIAN/postinst"
#!/bin/sh
set -eu
exit 0
EOF
    chmod 755 "$p_root/DEBIAN/postinst"

    dpkg-deb --build --root-owner-group "$p_root" "$OUT_DIR/$p_deb"
    echo "✅ Prehodni paket zgrajen: $OUT_DIR/$p_deb"
}

zgradi_prehodni "safeer-os" "0.5.0"
zgradi_prehodni "safeer-control" "2.2.0"
zgradi_prehodni "safeer-os-tema" "0.5.0"
zgradi_prehodni "safeer-cinnamon" "1.3.0"
