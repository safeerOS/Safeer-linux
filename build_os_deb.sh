#!/usr/bin/env bash
# ==============================================================================
# Safeer OS (Linux) — Debian / Ubuntu / Linux Mint .deb Package Builder
# Produces safeer-os_<version>_amd64.deb: THE one Safeer package for Linux (since 12. 10. 2026). Since 15. 10. 2026 it
# carries our WebKitGTK 6.0 and libsoup 3 (SAFEER_WEBKIT_TAR, packaging/webkit-deb) in /usr/lib/safeer-os/webkit, the same
# engine as the Flatpak. Without SAFEER_WEBKIT_TAR (local builds, tests) it is safeer-os_<version>_all.deb on the
# system WebKitGTK.
# One download, one install, one update: Safeer OS with its desktop workspace, Safeer Control (Safeer Link,
# devices, D-Bus, safeerctl) and Safeer Cinnamon (look, dock, workspace layout, boot/login look).
#
# Earlier releases shipped safeer-control and safeer-cinnamon as separate packages. This package carries every file
# they had and declares Replaces + Provides for both. safeer-cinnamon gets NO Conflicts/Breaks: dpkg takes its files
# over and the old package "disappears" (postrm disappear). That matters: with Conflicts the old safeer-cinnamon would
# be removed with `prerm remove`, which turns the user's Safeer Cinnamon look off during the update.
# safeer-control cannot disappear: the old safeer-os it is upgraded from depends on it, and dpkg never lets a package
# that an installed package still depends on disappear (measured on Mint 22.3: it stayed "ii"). So it gets a versioned
# Conflicts and is removed in the same step; its prerm/postrm only clean byte-code and caches (checked in 2.1.81).
# tools/mint_namestitev checks on Linux Mint that an update from the last release leaves no old package behind.
# ==============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_NAME="safeer-os"
VERSION="$(cat "$DIR/packaging/VERSION_OS")"
CONTROL_VERSION="$(cat "$DIR/packaging/VERSION_CONTROL")"
CINNAMON_VERSION="$(cat "$DIR/packaging/VERSION_CINNAMON")"
# Polja paketa (Version, Provides, Conflicts): beta 0.4.86-beta.1 kot 0.4.86~beta.1, da jo koncna 0.4.86 posodobi
# (packaging/deb_razlicica.sh). Ime datoteke ostane z »-beta.N« kot oznaka izdaje.
DEB_VERSION="$(bash "$DIR/packaging/deb_razlicica.sh" "$VERSION")"
DEB_CONTROL_VERSION="$(bash "$DIR/packaging/deb_razlicica.sh" "$CONTROL_VERSION")"
DEB_CINNAMON_VERSION="$(bash "$DIR/packaging/deb_razlicica.sh" "$CINNAMON_VERSION")"
WEBKIT_TAR="${SAFEER_WEBKIT_TAR:-}"
# Node.js (x86_64) je v paketu vedno, razen v preizkusih paketa (SAFEER_DEB_BREZ_NODE=1, brez 30 MB prenosa).
NODE=1
[ "${SAFEER_DEB_BREZ_NODE:-0}" = 1 ] && NODE=0
# Safeer DRM (SAFEER_DRM_TOVOR, packaging/namesti_safeer_drm.sh) ima programe za x86_64: paket je tudi z njim amd64.
if [ -n "$WEBKIT_TAR" ] || [ -n "${SAFEER_DRM_TOVOR:-}" ] || [ "$NODE" = 1 ]; then ARCH="amd64"; else ARCH="all"; fi
DEB_PACKAGE="${PKG_NAME}_${VERSION}_${ARCH}.deb"
STAGE="$DIR/build/stage-os"
BUILD_ROOT="$DIR/build/deb-os"

echo "=========================================================="
echo "📦 Gradnja Debian paketa: $DEB_PACKAGE (Safeer OS + Control + Cinnamon)"
echo "=========================================================="

rm -rf "$STAGE" "$BUILD_ROOT"
bash "$DIR/packaging/install_os_payload.sh" "$STAGE/usr"
bash "$DIR/packaging/install_control_payload.sh" "$STAGE/usr"
mkdir -p "$BUILD_ROOT/DEBIAN"
cp -a "$STAGE/usr" "$BUILD_ROOT/"
bash "$DIR/packaging/install_cinnamon_payload.sh" "$BUILD_ROOT"
# Profila AppArmor (Ubuntu 24.04+: peskovnik WebKita potrebuje uporabniske imenske prostore) - core/peskovnik_userns.py.
bash "$DIR/packaging/apparmor/namesti.sh" "$BUILD_ROOT" safeer-os safeer-control
# Lupina QML (GTK4 + Qt Quick v istem procesu): PySide6, ki ga Linux Mint 22 nima v svojih paketih - ista kolesa kot v
# Flatpaku (packaging/pyside6_vendor.py). Brez njih bi Safeer OS tekel s prejsnjo delovno povrsino v WebKitu.
# SAFEER_DEB_BREZ_QT=1: preizkus paketa (tests/test_delovna.py) brez 80 MB prenosa - PySide6 preverja CI (job safeer-os).
if [ "${SAFEER_DEB_BREZ_QT:-0}" != 1 ]; then
    python3 "$DIR/packaging/pyside6_vendor.py" "$BUILD_ROOT/usr/lib/safeer-os/vendor"
fi
# Node.js 22 LTS (lastnik: nacin »deb«) v zasebni predponi /usr/lib/safeer-os/node: pripeta razlicica, SHA-256 arhiva
# preverjena pred uporabo (packaging/node_vendor.py). Ne v PATH in ne v /usr/bin - sistemski node ostane nedotaknjen;
# programi Safeer OS ga najdejo prek core/node_izvajalnik.py. Licenca (z licencami V8, OpenSSL, ICU ...) gre v doc.
NODE_ODVISNOSTI=""
if [ "$NODE" = 1 ]; then
    python3 "$DIR/packaging/node_vendor.py" "$BUILD_ROOT/usr/lib/safeer-os/node"
    install -d "$BUILD_ROOT/usr/share/doc/safeer-os/nodejs"
    mv "$BUILD_ROOT/usr/lib/safeer-os/node/LICENSE" "$BUILD_ROOT/usr/share/doc/safeer-os/nodejs/LICENSE"
    # bin/node: glibc >= 2.28 in libstdc++ (GLIBCXX_3.4.21) - objdump -T, 18. 10. 2026.
    NODE_ODVISNOSTI=", libc6 (>= 2.28), libstdc++6 (>= 5.2), libgcc-s1"
fi
sed -i 's|^Exec=safeer-os|Exec=/usr/bin/safeer-os|' "$BUILD_ROOT/usr/share/applications/safeer-os.desktop" \
    "$BUILD_ROOT/usr/share/applications/safeer-os.Player.desktop" \
    "$BUILD_ROOT"/usr/share/applications/safeer-os.{splet,sporocila,zapiski,nastavitve,scit}.desktop
sed -i 's|^Exec=safeer-control|Exec=/usr/bin/safeer-control|' "$BUILD_ROOT/usr/share/applications/safeer-control.desktop"
# SAFEER_DAV1D=MAPA (CI: posel dav1d-deb): se dekoder AV1 dav1ddec v predpono (packaging/webkit-deb/vgradi.sh).
# Nas WebKitGTK in libsoup (core/zasebni_webkit.py; Safeer Control iz /usr/lib/safeer-control uporabi istega). Njune
# knjiznice dobijo odvisnosti iz dpkg-shlibdeps, peskovnik bwrap in xdg-dbus-proxy, libsoup glib-networking (TLS).
if [ -n "$WEBKIT_TAR" ]; then
    WEBKIT_ODVISNOSTI="$(bash "$DIR/packaging/webkit-deb/vgradi.sh" "$BUILD_ROOT" "$PKG_NAME" "$WEBKIT_TAR")"
    SPLET_ODVISNOSTI="${WEBKIT_ODVISNOSTI}, bubblewrap, xdg-dbus-proxy, glib-networking"
else
    SPLET_ODVISNOSTI="gir1.2-webkit-6.0, gir1.2-soup-3.0"
fi

# Safeer DRM v paketu (packaging/namesti_safeer_drm.sh, SAFEER_DRM_TOVOR): knjiznice sistema, ki jih ECS potrebuje.
DRM_ODVISNOSTI=""
if [ -x "$BUILD_ROOT/usr/lib/safeer-os/safeer-drm/safeer-drm" ]; then
    DRM_ODVISNOSTI=", $(python3 "$DIR/packaging/safeer_drm_paket.py" odvisnosti-deb)"
fi
# GDebi (dvoklik na paket) ne namesti priporocenih paketov: kar mora delovati takoj, je v Depends.
# Vticnik Qt xcb (lupina QML, PySide6 iz paketa) nalozi libxcb-* neposredno: vse so nastete, ne le tiste, ki jih prinese
# kaksen drug paket (readelf/ldd libqxcb.so PySide6 6.11.2, 18. 10. 2026); CI preveri z packaging/preveri_qxcb.sh.
# python3-zeroconf: brez nje Safeer Link ne najde nobene naprave (mDNS) - ni QR kode in ne 6-mestne kode za prijavo
# (testni racunalnik, cista namestitev 12. 10. 2026; do 0.4.83 je ni zahteval noben paket).
# mint-themes obstaja samo v Linux Mintu - ostane priporocilo, da se paket namesti tudi na Ubuntu in Debianu
# (tam tema Safeer Cinnamon nima obrob oken Mint-Y, vse ostalo deluje).
# poppler-utils (pdftoppm): slika prve strani PDF - slicica priponke v Sporocilih in predogled v Datotekah.
# Wayland (Ubuntu 24.04 GNOME, 18. 10. 2026): libwayland-* za vticnik Qt wayland (lupina QML nativno, ldd libqwayland.so
# PySide6 6.11.2); gstreamer1.0-pipewire (pipewiresrc) za deljenje zaslona v Linku prek portala ScreenCast
# (core/portal_zaslon.py); xdg-desktop-portal je na Ubuntu in Mintu ze namescen, zato samo priporocilo.
cat << EOF2 > "$BUILD_ROOT/DEBIAN/control"
Package: safeer-os
Version: ${DEB_VERSION}
Section: x11
Priority: optional
Architecture: ${ARCH}
Depends: python3 (>= 3.10), python3-cryptography, python3-gi (>= 3.42), python3-gi-cairo, python3-qrcode, python3-zeroconf, gir1.2-gtk-4.0, ${SPLET_ODVISNOSTI}, gir1.2-glib-2.0, gir1.2-secret-1, gir1.2-atspi-2.0, gir1.2-gstreamer-1.0, gstreamer1.0-libav, gstreamer1.0-plugins-bad, gstreamer1.0-plugins-base, gstreamer1.0-plugins-good, gstreamer1.0-gl, libxcb-cursor0, libxkbcommon-x11-0, libxcb-icccm4, libxcb-keysyms1, libxcb-shape0, libxcb-image0, libxcb-randr0, libxcb-render-util0, libxcb-render0, libxcb-shm0, libxcb-sync1, libxcb-util1, libxcb-xfixes0, libxcb-xkb1, libxcb1, libx11-xcb1, libxkbcommon0, libgl1, libegl1, libfontconfig1, libwayland-client0, libwayland-cursor0, libwayland-egl1, gstreamer1.0-pipewire, sway, wf-recorder, wtype, wmctrl, libglib2.0-bin, plank, dconf-cli, poppler-utils${DRM_ODVISNOSTI}${NODE_ODVISNOSTI}
Recommends: mint-themes, cinnamon, xdg-desktop-portal, network-manager, pulseaudio-utils, policykit-1, xdg-utils, x11-utils, imagemagick, ffmpeg, python3-pil, python3-numpy, papirus-icon-theme
Suggests: libreoffice-writer, libreoffice-calc, libreoffice-impress, plymouth, slick-greeter
Provides: safeer-control (= ${DEB_CONTROL_VERSION}), safeer-cinnamon (= ${DEB_CINNAMON_VERSION})
Replaces: safeer-control, safeer-cinnamon
Conflicts: safeer-control (<< ${DEB_CONTROL_VERSION}~)
Maintainer: Safeer <info@safeer.si>
Homepage: https://safeer.si/os/
Description: Safeer OS - the Safeer desktop on top of Linux Mint
 Safeer OS turns Linux Mint into a complete Safeer desktop: a workspace with
 search, your programs, files, media and the devices of your home in one
 place, with the dock below. Through Safeer Link it opens apps of your phone,
 tablet and TV, plays your computer's sound on them and shares files - at
 home, without the cloud and without an account. Shield: DNS filtering of
 ads, trackers and dangerous domains for the whole computer. Splet: a fast
 built-in web browser with tabs, bookmarks and import from other browsers.
 .
 One package contains everything: Safeer OS, Safeer Control (Safeer Link and
 safeerctl) and the Safeer Cinnamon look. Installing changes nothing on your
 desktop: open "Safeer Cinnamon" in the menu and choose the look only, the
 look with a dock or the full Safeer workspace. Linux Mint stays underneath:
 "Restore previous look" puts everything back.
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
    /usr/bin/python3 -m compileall -q /usr/lib/safeer-control >/dev/null 2>&1 || true
fi
# AppArmor: Ubuntu 24.04+ omejuje uporabniske imenske prostore - brez profila se peskovnik WebKita (bwrap) ne zazene in
# Splet bi padel. Profila nasih zaganjalnikov nalozimo takoj (ne sele ob naslednjem zagonu racunalnika); brez AppArmorja
# (vsebnik, sistem brez njega) se ne zgodi nic. Kot dh_apparmor: -r zamenja nalozenega, -T -W osvezi predpomnilnik.
if [ "${1:-}" = "configure" ] && [ -d /sys/kernel/security/apparmor ] && command -v apparmor_parser >/dev/null 2>&1; then
    for profil in safeer-os safeer-control; do
        if [ -f "/etc/apparmor.d/$profil" ]; then
            apparmor_parser -r -T -W "/etc/apparmor.d/$profil" >/dev/null 2>&1 || true
        fi
    done
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
if [ -d /usr/lib/safeer-control ] && [ -x /usr/bin/find ]; then
    /usr/bin/find /usr/lib/safeer-control -depth \( -name '*.pyc' -o -name __pycache__ \) -delete 2>/dev/null || true
fi
# The layout chooser (/usr/lib/safeer-cinnamon/izbira) is Python too: byte-code written when it ran as root.
if [ -d /usr/lib/safeer-cinnamon ] && [ -x /usr/bin/find ]; then
    /usr/bin/find /usr/lib/safeer-cinnamon -depth \( -name '*.pyc' -o -name __pycache__ \) -delete 2>/dev/null || true
fi
# Safeer Cinnamon: on removal (not on an update) every user who has it turned on gets the previous look back while
# the command and the theme still exist (a logged-in user in their own session, the others in a temporary D-Bus
# session). Without this Cinnamon would fall back to the default theme and the panel, dock and wallpaper would stay
# changed.
if [ "${1:-}" = "remove" ] && [ -x /usr/bin/safeer-cinnamon ]; then
    getent passwd | awk -F: '$3 >= 1000 && $3 < 60000 { print $1 ":" $3 ":" $6 }' | while IFS=: read -r ime uid dom; do
        [ -f "$dom/.config/safeer-cinnamon/vklopljeno" ] || continue
        if [ -S "/run/user/$uid/bus" ]; then
            zaslon=":0"
            pid="$(pgrep -u "$uid" -x cinnamon 2>/dev/null | head -n1)" || true
            if [ -n "$pid" ] && [ -r "/proc/$pid/environ" ]; then
                z="$(tr '\0' '\n' < "/proc/$pid/environ" | sed -n 's/^DISPLAY=//p' | head -n1)" || true
                [ -n "$z" ] && zaslon="$z"
            fi
            timeout 60 runuser -u "$ime" -- env HOME="$dom" XDG_RUNTIME_DIR="/run/user/$uid" \
                DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" DISPLAY="$zaslon" \
                SAFEER_CINNAMON_BREZ_SISTEMA=1 /usr/bin/safeer-cinnamon --izklopi >/dev/null 2>&1 || true
        elif command -v dbus-run-session >/dev/null 2>&1; then
            timeout 60 runuser -u "$ime" -- env HOME="$dom" SAFEER_CINNAMON_BREZ_SISTEMA=1 \
                dbus-run-session -- /usr/bin/safeer-cinnamon --izklopi >/dev/null 2>&1 || true
        fi
        if [ -f "$dom/.config/safeer-cinnamon/vklopljeno" ]; then
            echo "Safeer Cinnamon: uporabniku $ime prejsnjega videza ni bilo mogoce vrniti samodejno."
        else
            echo "Safeer Cinnamon: uporabniku $ime je vrnjen prejsnji videz."
        fi
    done
    # Zagonski in prijavni zaslon sta sistemska: vrnemo ju, preden izginejo datoteke teme.
    if [ -x /usr/lib/safeer-cinnamon/od-vklopa ]; then /usr/lib/safeer-cinnamon/od-vklopa izklopi || true; fi
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
if [ "${1:-}" = "purge" ]; then rm -rf /var/lib/safeer-cinnamon; fi
# AppArmor: ob odstranitvi profil umaknemo iz jedra (datoteka v /etc ostane do purge, kot vsaka nastavitev).
if [ "${1:-}" = "remove" ] && [ -d /sys/kernel/security/apparmor ] && command -v apparmor_parser >/dev/null 2>&1; then
    for profil in safeer-os safeer-control; do
        if [ -f "/etc/apparmor.d/$profil" ]; then
            apparmor_parser -R "/etc/apparmor.d/$profil" >/dev/null 2>&1 || true
        fi
    done
fi
exit 0
EOF2
chmod 755 "$BUILD_ROOT/DEBIAN/postinst" "$BUILD_ROOT/DEBIAN/prerm" "$BUILD_ROOT/DEBIAN/postrm"
find "$BUILD_ROOT" -type d -exec chmod 755 {} +
chmod 755 "$BUILD_ROOT/usr/bin/safeer-os" "$BUILD_ROOT/usr/bin/safeer-control" "$BUILD_ROOT/usr/bin/safeerctl" \
    "$BUILD_ROOT/usr/bin/safeer-cinnamon" "$BUILD_ROOT/usr/lib/safeer-cinnamon/izbira" "$BUILD_ROOT/usr/lib/safeer-cinnamon/od-vklopa"
for script in "$BUILD_ROOT/DEBIAN/postinst" "$BUILD_ROOT/DEBIAN/prerm" "$BUILD_ROOT/DEBIAN/postrm"; do
    if command -v dash >/dev/null 2>&1; then dash -n "$script"; else sh -n "$script"; fi
done

echo "🔨 Izdelava paketa z dpkg-deb..."
# Installed-Size (KiB): namestitveni programi (GDebi, Captain, apt) uporabniku pokazejo, koliko prostora paket zasede
# (z nasim WebKitom ~135 MiB vec); dpkg-deb ga sam ne izracuna.
echo "Installed-Size: $(du -sk --exclude=DEBIAN "$BUILD_ROOT" | cut -f1)" >> "$BUILD_ROOT/DEBIAN/control"
dpkg-deb --build --root-owner-group "$BUILD_ROOT" "$DIR/$DEB_PACKAGE"
echo "✅ $DIR/$DEB_PACKAGE"
dpkg-deb -I "$DIR/$DEB_PACKAGE"
