#!/usr/bin/env bash
# ==============================================================================
# Safeer Desktop & OS Package Builder (4. krog)
# Nova zasnova:
# 1. safeer-os (v0.5.0): GLAVNI paket (Safeer OS + Control + Link), neodvisen od namizja
# 2. safeer-control (v2.2.0): PREHODNI paket (Depends: safeer-os >= 0.5.0)
# 3. safeer-cinnamon (v1.3.0): LOČEN paket s temo za Cinnamon (Depends: safeer-os >= 0.5.0)
# 4. safeer-os-tema (v0.5.0): PREHODNI paket (Depends: safeer-cinnamon >= 1.3.0)
# ==============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT_DIR="$(cd "$DIR/.." && pwd)"

VERSION_OS="0.5.0"
VERSION_CONTROL="2.2.0"
VERSION_CINNAMON="1.3.0"
ARCH="all"

echo "=========================================================="
echo "📦 Gradnja paketov nove zasnove (safeer-os v$VERSION_OS)"
echo "=========================================================="

# ------------------------------------------------------------------------------
# 1. GLAVNI PAKET: safeer-os (0.5.0)
# ------------------------------------------------------------------------------
ROOT_OS="$DIR/build/deb-safeer-os"
rm -rf "$ROOT_OS"
mkdir -p "$ROOT_OS/DEBIAN"

echo "-> Priprava vsebin safeer-control in safeer-os za safeer-os..."
bash "$DIR/packaging/install_control_payload.sh" "$ROOT_OS/usr"
bash "$DIR/packaging/install_os_payload.sh" "$ROOT_OS/usr"

# Popravki poti v desktop datotekah
sed -i 's|^Exec=safeer-os|Exec=/usr/bin/safeer-os|' "$ROOT_OS/usr/share/applications/safeer-os.desktop" 2>/dev/null || true
sed -i 's|^Exec=safeer-control|Exec=/usr/bin/safeer-control|' "$ROOT_OS/usr/share/applications/safeer-control.desktop" 2>/dev/null || true

# Pravilo enotnega vnosa: safeer-control.desktop je skrit (NoDisplay=true)
if grep -q '^NoDisplay=' "$ROOT_OS/usr/share/applications/safeer-control.desktop" 2>/dev/null; then
    sed -i 's|^NoDisplay=.*|NoDisplay=true|' "$ROOT_OS/usr/share/applications/safeer-control.desktop"
else
    echo "NoDisplay=true" >> "$ROOT_OS/usr/share/applications/safeer-control.desktop"
fi

cat << EOF > "$ROOT_OS/DEBIAN/control"
Package: safeer-os
Version: ${VERSION_OS}
Section: utils
Priority: optional
Architecture: ${ARCH}
Replaces: safeer-control (<< ${VERSION_CONTROL})
Breaks: safeer-control (<< ${VERSION_CONTROL})
Provides: safeer-control (= ${VERSION_CONTROL})
Depends: python3, python3-cryptography, python3-gi, python3-gi-cairo, gir1.2-gtk-3.0, gir1.2-webkit2-4.1, gir1.2-soup-3.0, gir1.2-glib-2.0, gir1.2-secret-1, gir1.2-gstreamer-1.0, gir1.2-atspi-2.0, gstreamer1.0-gtk3, gstreamer1.0-libav, gstreamer1.0-plugins-bad, gstreamer1.0-plugins-base, python3-qrcode, sway, wf-recorder, wtype, wmctrl
Recommends: network-manager, pulseaudio-utils, policykit-1, xdg-utils, gir1.2-wnck-3.0, x11-utils, python3-pil, libglib2.0-bin
Suggests: safeer-cinnamon
Maintainer: Safeer <info@safeer.si>
Homepage: https://safeer.si/os/
Description: Safeer OS - unified system and control without cloud
 Safeer OS is a full-screen shell and desktop controller. Through Safeer Link
 it controls your Android TV and phone, plays sound, shares files, and protects
 privacy with Shield DNS filtering. Everything runs locally without an account.
EOF
chmod 644 "$ROOT_OS/DEBIAN/control"

cat << 'EOF' > "$ROOT_OS/DEBIAN/postinst"
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
EOF

cat << 'EOF' > "$ROOT_OS/DEBIAN/prerm"
#!/bin/sh
set -eu
if [ -d /usr/lib/safeer-control ] && [ -x /usr/bin/find ]; then
    /usr/bin/find /usr/lib/safeer-control -depth \( -name '*.pyc' -o -name __pycache__ \) -delete 2>/dev/null || true
fi
if [ -d /usr/lib/safeer-os ] && [ -x /usr/bin/find ]; then
    /usr/bin/find /usr/lib/safeer-os -depth \( -name '*.pyc' -o -name __pycache__ \) -delete 2>/dev/null || true
fi
exit 0
EOF

cat << 'EOF' > "$ROOT_OS/DEBIAN/postrm"
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
EOF

chmod 755 "$ROOT_OS/DEBIAN/postinst" "$ROOT_OS/DEBIAN/prerm" "$ROOT_OS/DEBIAN/postrm"
find "$ROOT_OS" -type d -exec chmod 755 {} +
chmod 755 "$ROOT_OS/usr/bin/safeer-os" "$ROOT_OS/usr/bin/safeer-control" "$ROOT_OS/usr/bin/safeerctl"

dpkg-deb --build --root-owner-group "$ROOT_OS" "$OUT_DIR/safeer-os_${VERSION_OS}_${ARCH}.deb"
echo "✅ Glavni paket: $OUT_DIR/safeer-os_${VERSION_OS}_${ARCH}.deb"

# ------------------------------------------------------------------------------
# 2. PREHODNI PAKET: safeer-control (2.2.0)
# ------------------------------------------------------------------------------
ROOT_CTRL="$DIR/build/deb-prehodni-control"
rm -rf "$ROOT_CTRL"
mkdir -p "$ROOT_CTRL/DEBIAN"

cat << EOF > "$ROOT_CTRL/DEBIAN/control"
Package: safeer-control
Version: ${VERSION_CONTROL}
Section: oldlibs
Priority: optional
Architecture: ${ARCH}
Depends: safeer-os (>= ${VERSION_OS})
Maintainer: Safeer <info@safeer.si>
Description: Transitional dummy package for safeer-control -> safeer-os
 This is a transitional dummy package to automatically upgrade existing installs
 of safeer-control to the unified safeer-os package. It can be safely removed.
EOF
chmod 644 "$ROOT_CTRL/DEBIAN/control"

cat << 'EOF' > "$ROOT_CTRL/DEBIAN/postinst"
#!/bin/sh
set -eu
exit 0
EOF
chmod 755 "$ROOT_CTRL/DEBIAN/postinst"

dpkg-deb --build --root-owner-group "$ROOT_CTRL" "$OUT_DIR/safeer-control_${VERSION_CONTROL}_${ARCH}.deb"
echo "✅ Prehodni paket: $OUT_DIR/safeer-control_${VERSION_CONTROL}_${ARCH}.deb"

# ------------------------------------------------------------------------------
# 3. TEMA PAKET: safeer-cinnamon (1.3.0)
# ------------------------------------------------------------------------------
ROOT_CIN="$DIR/build/deb-safeer-cinnamon"
rm -rf "$ROOT_CIN"
mkdir -p "$ROOT_CIN/DEBIAN" "$ROOT_CIN/usr/share/themes" "$ROOT_CIN/usr/bin" "$ROOT_CIN/usr/share/applications" \
         "$ROOT_CIN/usr/share/safeer-cinnamon/plank" "$ROOT_CIN/usr/share/backgrounds/safeer" \
         "$ROOT_CIN/usr/share/cinnamon-background-properties" "$ROOT_CIN/usr/share/doc/safeer-cinnamon" \
         "$ROOT_CIN/usr/share/plymouth/themes/safeer" "$ROOT_CIN/usr/lib/safeer-cinnamon" "$ROOT_CIN/usr/share/polkit-1/actions" \
         "$ROOT_CIN/etc/xdg/autostart"

T_CIN="$DIR/packaging/tema-cinnamon"
T_OS="$DIR/packaging/tema"

# Teme (Cinnamon, GTK)
cp -a "$T_CIN/Safeer-Cinnamon" "$T_CIN/Safeer-Cinnamon-Kontrast" "$ROOT_CIN/usr/share/themes/"
if [ -d "$T_OS/Safeer-OS" ]; then
    cp -a "$T_OS/Safeer-OS" "$ROOT_CIN/usr/share/themes/"
fi

# Povezave za metacity in gtk-2.0
for tema in Safeer-Cinnamon Safeer-Cinnamon-Kontrast; do
    ln -s /usr/share/themes/Mint-Y/metacity-1 "$ROOT_CIN/usr/share/themes/$tema/metacity-1"
    ln -s /usr/share/themes/Mint-Y-Dark-Blue/gtk-2.0 "$ROOT_CIN/usr/share/themes/$tema/gtk-2.0"
done

install -m 755 "$T_CIN/safeer-cinnamon" "$ROOT_CIN/usr/bin/safeer-cinnamon"
install -m 755 "$T_CIN/izbira" "$ROOT_CIN/usr/lib/safeer-cinnamon/izbira"
install -m 644 "$T_CIN/plank/dock.theme" "$ROOT_CIN/usr/share/safeer-cinnamon/plank/dock.theme"
install -m 644 "$T_CIN"/ozadje/*.jpg "$T_CIN/ozadje/safeer-gore-3840x2160.png" "$T_CIN/ozadje/safeer-gore-16-9.svg" "$ROOT_CIN/usr/share/backgrounds/safeer/"
install -m 644 "$T_CIN/safeer-cinnamon-ozadje.xml" "$ROOT_CIN/usr/share/cinnamon-background-properties/safeer-cinnamon.xml"
install -m 644 "$T_CIN/safeer-cinnamon-vklopi.desktop" "$ROOT_CIN/usr/share/applications/safeer-cinnamon.desktop"
install -m 644 "$T_CIN/safeer-cinnamon-izklopi.desktop" "$ROOT_CIN/usr/share/applications/safeer-cinnamon-izklopi.desktop"
install -m 644 "$T_CIN/COPYING" "$ROOT_CIN/usr/share/doc/safeer-cinnamon/copyright"

install -m 644 "$T_CIN"/plymouth/safeer/* "$ROOT_CIN/usr/share/plymouth/themes/safeer/"
install -m 755 "$T_CIN/od-vklopa" "$ROOT_CIN/usr/lib/safeer-cinnamon/od-vklopa"
install -m 644 "$T_CIN/si.safeer.cinnamon.od-vklopa.policy" "$ROOT_CIN/usr/share/polkit-1/actions/si.safeer.cinnamon.od-vklopa.policy"
install -m 644 "$T_CIN/safeer-cinnamon-od-vklopa.desktop" "$ROOT_CIN/usr/share/applications/safeer-cinnamon-od-vklopa.desktop"
install -m 644 "$T_CIN/safeer-cinnamon-od-vklopa-izklopi.desktop" "$ROOT_CIN/usr/share/applications/safeer-cinnamon-od-vklopa-izklopi.desktop"

# Zagonska skripta za sejo
install -m 755 "$T_OS/safeer-os-tema" "$ROOT_CIN/usr/bin/safeer-os-tema"
install -m 644 "$T_OS/safeer-os-tema-autostart.desktop" "$ROOT_CIN/etc/xdg/autostart/safeer-os-tema.desktop"

cat << EOF > "$ROOT_CIN/DEBIAN/control"
Package: safeer-cinnamon
Version: ${VERSION_CINNAMON}
Section: x11
Priority: optional
Architecture: ${ARCH}
Replaces: safeer-os-tema (<< 0.5.0)
Breaks: safeer-os-tema (<< 0.5.0)
Provides: safeer-os-tema (= 0.5.0)
Depends: safeer-os (>= ${VERSION_OS}), mint-themes | yaru-theme-gtk, libglib2.0-bin, python3, python3-gi, gir1.2-gtk-3.0, plank, dconf-cli
Recommends: cinnamon, papirus-icon-theme
Suggests: plymouth, slick-greeter
Maintainer: Safeer <info@safeer.si>
Homepage: https://safeer.si/os/
Description: Safeer Cinnamon - desktop theme and layout for Cinnamon
 A calm blue theme for Cinnamon, GTK 3/4 and window borders, Safeer wallpapers
 and matching Plank dock. Integrates with Safeer OS.
EOF
chmod 644 "$ROOT_CIN/DEBIAN/control"

cat << 'EOF' > "$ROOT_CIN/DEBIAN/prerm"
#!/bin/sh
set -eu
exit 0
EOF
chmod 755 "$ROOT_CIN/DEBIAN/prerm"

find "$ROOT_CIN" -type d -exec chmod 755 {} +
find "$ROOT_CIN/usr/share" -type f -exec chmod 644 {} +
chmod 755 "$ROOT_CIN/usr/bin/safeer-cinnamon" "$ROOT_CIN/usr/lib/safeer-cinnamon/izbira" "$ROOT_CIN/usr/lib/safeer-cinnamon/od-vklopa" "$ROOT_CIN/usr/bin/safeer-os-tema"

dpkg-deb --build --root-owner-group "$ROOT_CIN" "$OUT_DIR/safeer-cinnamon_${VERSION_CINNAMON}_${ARCH}.deb"
echo "✅ Tema paket: $OUT_DIR/safeer-cinnamon_${VERSION_CINNAMON}_${ARCH}.deb"

# ------------------------------------------------------------------------------
# 4. PREHODNI PAKET: safeer-os-tema (0.5.0)
# ------------------------------------------------------------------------------
ROOT_OSTEMA="$DIR/build/deb-prehodni-os-tema"
rm -rf "$ROOT_OSTEMA"
mkdir -p "$ROOT_OSTEMA/DEBIAN"

cat << EOF > "$ROOT_OSTEMA/DEBIAN/control"
Package: safeer-os-tema
Version: 0.5.0
Section: oldlibs
Priority: optional
Architecture: ${ARCH}
Depends: safeer-cinnamon (>= ${VERSION_CINNAMON})
Maintainer: Safeer <info@safeer.si>
Description: Transitional dummy package for safeer-os-tema -> safeer-cinnamon
 This is a transitional dummy package to consolidate theme packages into safeer-cinnamon.
 It can be safely removed.
EOF
chmod 644 "$ROOT_OSTEMA/DEBIAN/control"

cat << 'EOF' > "$ROOT_OSTEMA/DEBIAN/postinst"
#!/bin/sh
set -eu
exit 0
EOF
chmod 755 "$ROOT_OSTEMA/DEBIAN/postinst"

dpkg-deb --build --root-owner-group "$ROOT_OSTEMA" "$OUT_DIR/safeer-os-tema_0.5.0_${ARCH}.deb"
echo "✅ Prehodni paket: $OUT_DIR/safeer-os-tema_0.5.0_${ARCH}.deb"

echo "🎉 Vsi paketi uspešno zgrajeni v $OUT_DIR!"
