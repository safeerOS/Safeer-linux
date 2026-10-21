#!/usr/bin/env bash
# ==============================================================================
# Paket safeer-webkit_<razlicica>_amd64.deb: nas WebKitGTK 6.0 in libsoup 3 (s popravki Safeerja, Clang 22, ThinLTO, PGO,
# BOLT) v /usr/lib/safeer-webkit - EN paket za Safeer OS in Safeer Browser (lastnik, 19. 10. 2026).
#
#   paket.sh ARHIV.tar.zst [IZHODNA_MAPA]     npr. SAFEER_DAV1D=build/dav1d paket.sh build/safeer-webkit.tar.zst build
#
# Zakaj en paket: do 1.0.127~pred je imel vsak paket svojo kopijo (/usr/lib/safeer-os/webkit, /usr/lib/safeer-browser/webkit,
# ~135 MB vsaka, razlicni datoteki zaradi predpone). Meritev 18. 10. 2026 na testnem PC: ko teceta oba programa, so strani
# kode podvojene (~60-70 MiB libwebkitgtk + ~30 MiB JavaScriptCore), CI pa je WebKit gradil dvakrat (~2,5 h vsaka gradnja).
# Z eno predpono jadro deli strani kode med procesi obeh programov, CI pa gradi enkrat.
#
# Razlicica paketa je razlicica izdaje (packaging/VERSION, oblika dpkg iz packaging/deb_razlicica.sh): vsaka izdaja
# zgradi safeer-os, safeer-browser in safeer-webkit v istem teku, programa zahtevata safeer-webkit (>= te razlicice).
# Spodnja meja (ne natancna): uporabnik, ki posodobi samo enega od programov, drugega ne izgubi - API WebKitGTK 6.0 in
# soname libwebkitgtk-6.0.so.4 sta stabilna, novejsi safeer-webkit dela s starejsim programom (kot sistemski WebKitGTK).
# Brez skript vzdrzevalca: zasebna predpona z DT_RPATH (brez ldconfig), nic izven /usr/lib/safeer-webkit in doc.
# Nadgradnja s paketov z lastno kopijo: dpkg ob posodobitvi safeer-os/safeer-browser sam odstrani datoteke, ki jih novi
# paket nima (/usr/lib/<paket>/webkit) - preverjeno z dpkg -i v ubuntu:24.04 (tests/test_packaging.py, tools/mint_namestitev).
# ==============================================================================
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARHIV="${1:?Uporaba: paket.sh ARHIV.tar.zst [IZHODNA_MAPA]}"
IZHOD="${2:-$DIR}"
PAKET="safeer-webkit"
PREDPONA="/usr/lib/$PAKET"
VERSION="$(cat "$DIR/packaging/VERSION")"
DEB_VERSION="$(bash "$DIR/packaging/deb_razlicica.sh" "$VERSION")"
BUILD_ROOT="${SAFEER_WEBKIT_PAKET_DREVO:-$DIR/build/deb-webkit}"
DEB="$IZHOD/${PAKET}_${VERSION}_amd64.deb"

rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT/DEBIAN" "$IZHOD"
ODVISNOSTI="$(bash "$DIR/packaging/webkit-deb/vgradi.sh" "$BUILD_ROOT" "$ARHIV")"
G="$BUILD_ROOT$PREDPONA/share/webkitgtk-safeer/gradnja.txt"
# Razlicici iz zapisa gradnje (vrstici »webkitgtk: webkitgtk-2.54.1 <sha>« in »libsoup: libsoup-3.8.0 <sha>«).
WEBKIT_RAZLICICA="$(sed -n 's/^webkitgtk: webkitgtk-\([0-9][0-9.]*\) .*/\1/p' "$G")"
SOUP_RAZLICICA="$(sed -n 's/^libsoup: libsoup-\([0-9][0-9.]*\) .*/\1/p' "$G")"
LIBXML_RAZLICICA="$(sed -n 's/^libxml2: libxml2-\([0-9][0-9.]*\) .*/\1/p' "$G")"
LIBXSLT_RAZLICICA="$(sed -n 's/^libxslt: libxslt-\([0-9][0-9.]*\) .*/\1/p' "$G")"
[ -n "$WEBKIT_RAZLICICA" ] && [ -n "$SOUP_RAZLICICA" ] \
    || { cat "$G" >&2; echo "paket.sh: v $G ni razlicic WebKitGTK in libsoup" >&2; exit 1; }

# Odtis gradnje (core/zasebni_webkit.pot_odtisa): SHA-256 knjiznic in pomoznih procesov. Ista gradnja (arhiv iz
# predpomnilnika CI) da isti odtis, nova gradnja drugega. Safeer OS in Safeer Control ob drugem odtisu zazeneta znova
# (core/nova_razlicica.py), ko safeer-webkit posodobi drug program (npr. Safeer Browser): stara knjiznica v pomnilniku in
# novi spletni procesi iz nove gradnje bi se lahko ne razumeli (sporocila IPC so iz izvora gradnje).
( cd "$BUILD_ROOT$PREDPONA" && find lib libexec -type f \( -name '*.so*' -o -path 'libexec/*' \) -print0 | LC_ALL=C sort -z \
    | xargs -0 sha256sum ) | sha256sum | cut -c1-16 > "$BUILD_ROOT$PREDPONA/share/webkitgtk-safeer/odtis"
chmod 644 "$BUILD_ROOT$PREDPONA/share/webkitgtk-safeer/odtis"

# Licence in izvor (WebKitGTK in libsoup sta LGPL-2.1+ z deli BSD; dav1ddec MIT/Apache-2.0 v share/doc predpone).
install -d "$BUILD_ROOT/usr/share/doc/$PAKET"
{
    echo "Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/"
    echo "Upstream-Name: WebKitGTK $WEBKIT_RAZLICICA, libsoup $SOUP_RAZLICICA${LIBXML_RAZLICICA:+, libxml2 $LIBXML_RAZLICICA}${LIBXSLT_RAZLICICA:+, libxslt $LIBXSLT_RAZLICICA} (with Safeer fixes)"
    echo "Source: https://webkitgtk.org/releases/ https://download.gnome.org/sources/libsoup/ https://download.gnome.org/sources/libxml2/ https://download.gnome.org/sources/libxslt/"
    echo "Comment: Built by Safeer (https://github.com/safeerOS/Safeer-linux, packaging/webkit-deb) from the archives,"
    echo " patches and options in $PREDPONA/share/webkitgtk-safeer/gradnja.txt (SHA-256 of every archive and patch)."
    echo
    echo "Files: $PREDPONA/*"
    echo "Copyright: The WebKit project contributors, The GNOME Project and libsoup contributors"
    echo "License: LGPL-2.1+ and BSD-2-clause"
    echo " On Debian systems the LGPL 2.1 is in /usr/share/common-licenses/LGPL-2.1. WebKit's BSD-licensed parts carry"
    echo " their notice in the source files of the upstream archive."
    if [ -n "$LIBXML_RAZLICICA" ] || [ -n "$LIBXSLT_RAZLICICA" ]; then
        echo
        echo "Files: $PREDPONA/lib/libwebkitgtk-6.0.so.4"
        echo "Comment: Statically includes libxml2 ${LIBXML_RAZLICICA:-} and libxslt ${LIBXSLT_RAZLICICA:-}"
        echo "Copyright: Daniel Veillard, Bjorn Reese, William Brack, Igor Zlatkovic, Aleksey Sanin and other contributors"
        echo "License: MIT"
        echo " Permission is hereby granted, free of charge, to any person obtaining a copy"
        echo " of this software and associated documentation files (the \"Software\"), to deal"
        echo " in the Software without restriction, including without limitation the rights"
        echo " to use, copy, modify, merge, publish, distribute, sublicense, and/or sell"
        echo " copies of the Software, and to permit persons to whom the Software is"
        echo " furnished to do so, subject to the following conditions:"
        echo " The above copyright notice and this permission notice shall be included in"
        echo " all copies or substantial portions of the Software."
    fi
    echo
    echo "Files: $PREDPONA/lib/gstreamer-1.0/*"
    echo "Copyright: The gst-plugins-rs contributors"
    echo "License: MIT or Apache-2.0"
    echo " See $PREDPONA/share/doc/gst-plugin-dav1d/."
    # Knjiznice, ki jih vgradi.sh vgradi zaradi prenosnosti .deb (pregled Gemini 1.0.131: glavna datoteka jih mora navesti).
    for d in "$BUILD_ROOT$PREDPONA"/share/doc/vgrajene/*/; do
        [ -f "$d/copyright" ] || continue
        pkg="$(basename "$d")"
        echo
        echo "Files: $PREDPONA/lib/ (library from the Ubuntu 24.04 package $pkg, bundled for Linux Mint 23 / Ubuntu 26.04 / Debian 13)"
        echo "Copyright: see $PREDPONA/share/doc/vgrajene/$pkg/copyright"
        echo "License: see $PREDPONA/share/doc/vgrajene/$pkg/copyright"
    done
} > "$BUILD_ROOT/usr/share/doc/$PAKET/copyright"

# Polje Depends: knjiznice (dpkg-shlibdeps iz vgradi.sh), peskovnik spletnih procesov (bubblewrap, xdg-dbus-proxy) in TLS za
# libsoup (glib-networking) - brez njih WebKit ne nalozi nobene strani.
cat > "$BUILD_ROOT/DEBIAN/control" <<EOF
Package: safeer-webkit
Version: $DEB_VERSION
Section: libs
Priority: optional
Architecture: amd64
Depends: $ODVISNOSTI, bubblewrap, xdg-dbus-proxy, glib-networking
Maintainer: Safeer <info@safeer.si>
Homepage: https://github.com/safeerOS/Safeer-linux
Description: WebKitGTK $WEBKIT_RAZLICICA and libsoup $SOUP_RAZLICICA with Safeer fixes (shared web engine)
 The web engine of Safeer OS (Splet) and Safeer Browser: WebKitGTK 6.0 and
 libsoup 3 with the Safeer fixes, built by Safeer with Clang ThinLTO; release
 builds add profile-guided optimization, BOLT and the AV1 decoder dav1ddec
 (build record: $PREDPONA/share/webkitgtk-safeer/gradnja.txt).
 Installed in its own prefix ($PREDPONA); the system WebKitGTK and libsoup
 are neither needed nor touched. One copy serves both programs, so they
 share the engine's memory when they run together.
EOF
find "$BUILD_ROOT" -type d -exec chmod 755 {} +
chmod 644 "$BUILD_ROOT/DEBIAN/control" "$BUILD_ROOT/usr/share/doc/$PAKET/copyright"
echo "Installed-Size: $(du -sk --exclude=DEBIAN "$BUILD_ROOT" | cut -f1)" >> "$BUILD_ROOT/DEBIAN/control"
rm -f "$DEB"
dpkg-deb --build --root-owner-group "$BUILD_ROOT" "$DEB" >&2
dpkg-deb -f "$DEB" Package Version Architecture Installed-Size >&2
echo "$DEB"
