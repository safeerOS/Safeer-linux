#!/usr/bin/env bash
# ==============================================================================
# Safeer Browser — Debian / Ubuntu / Linux Mint .deb Package Builder
# Produces production-ready safeer-browser_<version>_amd64.deb with our WebKitGTK and libsoup
# (SAFEER_WEBKIT_TAR, packaging/webkit-deb) or, without it, safeer-browser_<version>_all.deb on the system WebKitGTK
# (local builds and tests).
# ==============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_NAME="safeer-browser"
VERSION="$(cat "$DIR/packaging/VERSION")"
# Polje Version: beta 1.0.128-beta.1 kot 1.0.128~beta.1, da jo koncna 1.0.128 posodobi (packaging/deb_razlicica.sh).
DEB_VERSION="$(bash "$DIR/packaging/deb_razlicica.sh" "$VERSION")"
# Nas WebKitGTK 6.0 in libsoup 3.8 (lastnik, 15. 10. 2026: .deb dobi vse izboljsave Flatpaka): arhiv iz
# packaging/webkit-deb/zgradi.sh za predpono /usr/lib/safeer-browser/webkit (CI: posel webkit-deb). Z njim je paket amd64.
# SAFEER_DAV1D=MAPA (CI: posel dav1d-deb) doda dekoder AV1 dav1ddec v predpono (packaging/webkit-deb/vgradi.sh).
WEBKIT_TAR="${SAFEER_WEBKIT_TAR:-}"
# Safeer DRM (SAFEER_DRM_TOVOR, packaging/namesti_safeer_drm.sh) ima programe za x86_64: paket je tudi z njim amd64.
if [ -n "$WEBKIT_TAR" ] || [ -n "${SAFEER_DRM_TOVOR:-}" ]; then ARCH="amd64"; else ARCH="all"; fi
DEB_PACKAGE="${PKG_NAME}_${VERSION}_${ARCH}.deb"
TAR_PACKAGE="safeer-browser-linux.tar.gz"
BUILD_ROOT="$DIR/build/deb"

echo "=========================================================="
echo "📦 Gradnja Debian paketa: $DEB_PACKAGE"
echo "=========================================================="

# Assemble the same payload as Flatpak and AppImage.
bash "$DIR/packaging/build_app_stage.sh"
rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT/DEBIAN"
cp -a "$DIR/build/stage/usr" "$BUILD_ROOT/"
# The system package knows where it lives: an absolute Exec cannot be shadowed by a stale
# "safeer" earlier in the user's PATH (e.g. an old ~/.local/bin symlink to a source checkout).
sed -i 's|^Exec=safeer|Exec=/usr/bin/safeer|' "$BUILD_ROOT/usr/share/applications/safeer-browser.desktop"
# Profil AppArmor (Ubuntu 24.04+: peskovnik WebKita potrebuje uporabniske imenske prostore) - core/peskovnik_userns.py.
bash "$DIR/packaging/apparmor/namesti.sh" "$BUILD_ROOT" safeer-browser
WEBKIT_ODVISNOSTI=""
if [ -n "$WEBKIT_TAR" ]; then
    WEBKIT_ODVISNOSTI="$(bash "$DIR/packaging/webkit-deb/vgradi.sh" "$BUILD_ROOT" "$PKG_NAME" "$WEBKIT_TAR")"
fi

# 6. Create DEBIAN/control
echo "📝 Generiranje DEBIAN/control..."
# GTK4 brskalnik (privzeto) potrebuje WebKitGTK 6.0 in GTK4: Linux Mint 22 / Ubuntu 24.04 naprej. Paket izdaje (amd64) ima
# nas WebKitGTK in libsoup v /usr/lib/safeer-browser/webkit (core/zasebni_webkit.py): odvisnosti njunih knjiznic izracuna
# dpkg-shlibdeps, peskovnik potrebuje bwrap in xdg-dbus-proxy, TLS za libsoup glib-networking. Brez arhiva (lokalna
# gradnja) paket uporabi WebKitGTK sistema. GDebi ne namesti priporocenih paketov: kar mora delovati takoj, je v Depends
# (kodeki GStreamer za video na straneh - isti kot v paketu safeer-os).
if [ -n "$WEBKIT_TAR" ]; then
    ODVISNOSTI="python3 (>= 3.10), python3-gi (>= 3.42), python3-gi-cairo, gir1.2-gtk-4.0, gir1.2-glib-2.0, ${WEBKIT_ODVISNOSTI}, bubblewrap, xdg-dbus-proxy, glib-networking, gstreamer1.0-plugins-base, gstreamer1.0-plugins-good, gstreamer1.0-plugins-bad, gstreamer1.0-libav, gstreamer1.0-gl"
    PRIPOROCILA="Recommends: python3-cryptography, xdg-utils
"
    OPIS_GTK=" specifically for Linux Mint 22+ and Ubuntu 24.04+. Built natively with GTK4 and
 its own WebKitGTK 6.0 and libsoup 3 (Clang ThinLTO build with Safeer fixes), it includes
 ad filtering, a local threat blocklist,"
else
    ODVISNOSTI="python3 (>= 3.10), python3-gi (>= 3.42), python3-gi-cairo, gir1.2-gtk-4.0, gir1.2-webkit-6.0, gir1.2-soup-3.0, gir1.2-glib-2.0, gstreamer1.0-plugins-base, gstreamer1.0-plugins-good, gstreamer1.0-plugins-bad, gstreamer1.0-libav, gstreamer1.0-gl"
    PRIPOROCILA="Recommends: python3-cryptography, xdg-utils
"
    OPIS_GTK=" specifically for Linux Mint 22+ and Ubuntu 24.04+. Built natively with GTK4 and
 WebKitGTK 6.0, it includes ad filtering, a local threat blocklist,"
fi
# Safeer DRM v paketu (packaging/namesti_safeer_drm.sh, SAFEER_DRM_TOVOR): knjiznice sistema, ki jih ECS potrebuje.
if [ -x "$BUILD_ROOT/usr/lib/safeer-browser/safeer-drm/safeer-drm" ]; then
    ODVISNOSTI="${ODVISNOSTI}, $(python3 "$DIR/packaging/safeer_drm_paket.py" odvisnosti-deb)"
fi
cat << EOF > "$BUILD_ROOT/DEBIAN/control"
Package: safeer-browser
Version: ${DEB_VERSION}
Section: web
Priority: optional
Architecture: ${ARCH}
Depends: ${ODVISNOSTI}
Maintainer: Safeer <info@safeer.si>
${PRIPOROCILA}Homepage: https://github.com/safeerOS/Safeer-linux
Description: Sovereign, ultra-fast, and private web browser for Linux Mint & Ubuntu
 Safeer Browser is an open-source, ultra-fast web browser engineered
${OPIS_GTK}
 bookmarks import from Firefox and Chrome, customizable portals,
 user CSS styling, and configurable JavaScript userscripts.
EOF
chmod 644 "$BUILD_ROOT/DEBIAN/control"

# 7. Create DEBIAN/postinst & DEBIAN/postrm
cat << 'EOF' > "$BUILD_ROOT/DEBIAN/postinst"
#!/bin/sh
# dpkg runs maintainer scripts with /bin/sh (dash): POSIX options only.
set -eu

if [ -x /usr/bin/update-desktop-database ]; then
    /usr/bin/update-desktop-database -q /usr/share/applications || true
fi

if [ -x /usr/bin/gtk-update-icon-cache ]; then
    /usr/bin/gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
fi

# Register Safeer Browser into Debian alternatives system for default browser
if [ -x /usr/sbin/update-alternatives ] || [ -x /usr/bin/update-alternatives ]; then
    update-alternatives --install /usr/bin/x-www-browser x-www-browser /usr/bin/safeer 40 || true
    update-alternatives --install /usr/bin/gnome-www-browser gnome-www-browser /usr/bin/safeer 40 || true
fi

# Byte-compile once, as root. A user cannot write into /usr/lib, so without this Python would compile every
# module again at each start. If it fails, the program still runs from source.
if [ -x /usr/bin/python3 ]; then
    /usr/bin/python3 -m compileall -q /usr/lib/safeer-browser >/dev/null 2>&1 || true
fi

# AppArmor: Ubuntu 24.04+ omejuje uporabniske imenske prostore - brez profila se peskovnik WebKita (bwrap) ne zazene in
# Splet bi padel. Profila nasih zaganjalnikov nalozimo takoj (ne sele ob naslednjem zagonu racunalnika); brez AppArmorja
# (vsebnik, sistem brez njega) se ne zgodi nic. Kot dh_apparmor: -r zamenja nalozenega, -T -W osvezi predpomnilnik.
if [ "${1:-}" = "configure" ] && [ -d /sys/kernel/security/apparmor ] && command -v apparmor_parser >/dev/null 2>&1; then
    for profil in safeer-browser; do
        if [ -f "/etc/apparmor.d/$profil" ]; then
            apparmor_parser -r -T -W "/etc/apparmor.d/$profil" >/dev/null 2>&1 || true
        fi
    done
fi

exit 0
EOF
chmod 755 "$BUILD_ROOT/DEBIAN/postinst"

cat << 'EOF' > "$BUILD_ROOT/DEBIAN/prerm"
#!/bin/sh
# dpkg runs maintainer scripts with /bin/sh (dash): POSIX options only.
set -eu
# Remove the byte-code that postinst compiled (and what Python wrote when the program was run as root). dpkg does
# not know these files; with them it would leave /usr/lib/safeer-browser behind after removal.
if [ -d /usr/lib/safeer-browser ] && [ -x /usr/bin/find ]; then
    /usr/bin/find /usr/lib/safeer-browser -depth \( -name '*.pyc' -o -name __pycache__ \) -delete 2>/dev/null || true
fi
exit 0
EOF
chmod 755 "$BUILD_ROOT/DEBIAN/prerm"

cat << 'EOF' > "$BUILD_ROOT/DEBIAN/postrm"
#!/bin/sh
# dpkg runs maintainer scripts with /bin/sh (dash): POSIX options only.
set -eu

if [ "${1:-}" = "remove" ] || [ "${1:-}" = "purge" ]; then
    if [ -x /usr/bin/update-desktop-database ]; then
        /usr/bin/update-desktop-database -q /usr/share/applications || true
    fi
    if [ -x /usr/bin/gtk-update-icon-cache ]; then
        /usr/bin/gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor || true
    fi
    if [ -x /usr/sbin/update-alternatives ] || [ -x /usr/bin/update-alternatives ]; then
        update-alternatives --remove x-www-browser /usr/bin/safeer 2>/dev/null || true
        update-alternatives --remove gnome-www-browser /usr/bin/safeer 2>/dev/null || true
    fi
fi
# AppArmor: ob odstranitvi profil umaknemo iz jedra (datoteka v /etc ostane do purge, kot vsaka nastavitev).
if [ "${1:-}" = "remove" ] && [ -d /sys/kernel/security/apparmor ] && command -v apparmor_parser >/dev/null 2>&1; then
    for profil in safeer-browser; do
        if [ -f "/etc/apparmor.d/$profil" ]; then
            apparmor_parser -R "/etc/apparmor.d/$profil" >/dev/null 2>&1 || true
        fi
    done
fi

exit 0
EOF
chmod 755 "$BUILD_ROOT/DEBIAN/postrm"

# Fix directory and control permissions strictly for dpkg-deb
find "$BUILD_ROOT" -type d -exec chmod 755 {} +
chmod 755 "$BUILD_ROOT/DEBIAN"
chmod 644 "$BUILD_ROOT/DEBIAN/control"
chmod 755 "$BUILD_ROOT/DEBIAN/postinst"
chmod 755 "$BUILD_ROOT/DEBIAN/prerm"
chmod 755 "$BUILD_ROOT/DEBIAN/postrm"
chmod 755 "$BUILD_ROOT/usr/bin/safeer"

# Maintainer scripts must be valid for dash, which dpkg uses as /bin/sh.
for script in "$BUILD_ROOT/DEBIAN/postinst" "$BUILD_ROOT/DEBIAN/prerm" "$BUILD_ROOT/DEBIAN/postrm"; do
    if command -v dash >/dev/null 2>&1; then dash -n "$script"; else sh -n "$script"; fi
    if grep -q pipefail "$script"; then echo "pipefail is not supported by /bin/sh: $script" >&2; exit 1; fi
done

# 8. Build Debian package (amd64 with our WebKitGTK, otherwise all)
echo "🔨 Izdelava paketa z dpkg-deb..."
# Installed-Size (KiB): namestitveni programi (GDebi, Captain, apt) uporabniku pokazejo, koliko prostora paket zasede
# (z nasim WebKitom ~135 MiB vec); dpkg-deb ga sam ne izracuna.
echo "Installed-Size: $(du -sk --exclude=DEBIAN "$BUILD_ROOT" | cut -f1)" >> "$BUILD_ROOT/DEBIAN/control"
dpkg-deb --build --root-owner-group "$BUILD_ROOT" "$DIR/$DEB_PACKAGE"

# 9. Build portable tar.gz package
# Prenosni arhiv je namestitev iz izvorne kode (install.sh, safeer-mint.sh): brskalnik GTK4 safeer_brskalnik.py
# (kot .deb, Flatpak in AppImage); packaging/ da vnos .desktop in VERSION za --version.
echo "📦 Izdelava prenosnega arhiva: $TAR_PACKAGE..."
tar -czf "$DIR/$TAR_PACKAGE" \
    --exclude="__pycache__" \
    --exclude="*.pyc" \
    --exclude=".git" \
    --exclude="build" \
    -C "$DIR" \
    safeer_brskalnik.py core ui assets safeer-mint.sh install.sh uninstall.sh \
    packaging/safeer-browser.desktop packaging/VERSION README.md LICENSE
TAR_DATOTEKE="$TAR_PACKAGE"

# 10. Generate SHA256SUMS
echo "🔒 Računanje SHA256 kontrolnih vsot..."
cd "$DIR"
sha256sum "$DEB_PACKAGE" $TAR_DATOTEKE > "$DIR/SHA256SUMS"

# 12. Verify package
echo ""
echo "=========================================================="
echo "✅ PAKETI USPEŠNO ZGRAJENI:"
echo "   .deb ($ARCH): $DIR/$DEB_PACKAGE"
[ -z "$TAR_DATOTEKE" ] || echo "   Portable tar : $DIR/$TAR_PACKAGE"
cat "$DIR/SHA256SUMS"
echo "=========================================================="
echo ""
echo "Preverjanje vsebine paketa:"
dpkg-deb -I "$DIR/$DEB_PACKAGE"
echo ""
echo "Paket lahko namestite z:"
echo "   sudo apt install ./$DEB_PACKAGE"
echo "ali z dvojnim klikom preko Gdebi / Upravitelja programov."
