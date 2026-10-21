#!/usr/bin/env bash
# Nas WebKitGTK in libsoup (arhiv iz packaging/webkit-deb/zgradi.sh) v drevo paketa safeer-webkit (packaging/webkit-deb/paket.sh).
#
#   vgradi.sh KOREN_PAKETA ARHIV.tar.zst     npr. vgradi.sh build/deb-webkit build/safeer-webkit.tar.zst
#
# Razpakira /usr/lib/safeer-webkit, preveri, da je arhiv zgrajen za to predpono (poti pomoznih procesov so prevedene v
# knjiznico) in s Clangom 22 + ThinLTO, ter na stdout izpise odvisnosti knjiznic (dpkg-shlibdeps) za polje Depends.
# Sporocila gredo na stderr.
#
# SAFEER_DAV1D=MAPA (izhod packaging/webkit-deb/dav1d.sh): dekoder AV1 dav1ddec v PREDPONA/lib/gstreamer-1.0 - noble
# nima vticnika GStreamer za libdav1d; core/zasebni_webkit.py mapo doda v GST_PLUGIN_PATH. Odvisnost libdav1d7 zapise
# dpkg-shlibdeps iz knjiznice vticnika.
set -euo pipefail
KOREN="${1:?KOREN_PAKETA}"
ARHIV="${2:?ARHIV}"
[ "$#" = 2 ] || { echo "vgradi.sh: KOREN_PAKETA ARHIV.tar.zst (od 19. 10. 2026 ena predpona, brez imena paketa)" >&2; exit 2; }
PAKET="safeer-webkit"
PREDPONA="/usr/lib/$PAKET"
WK="$KOREN$PREDPONA"
[ -f "$ARHIV" ] || { echo "vgradi.sh: arhiva $ARHIV ni" >&2; exit 1; }
rm -rf "$WK"
mkdir -p "$KOREN"
tar -C "$KOREN" -I zstd -xf "$ARHIV" "${PREDPONA#/}"
G="$WK/share/webkitgtk-safeer/gradnja.txt"
for vzorec in "^predpona: $PREDPONA\$" 'clang version 22\.' '^LTO_MODE:.*=thin$' '^build.ninja -fuse-ld=lld: [1-9]'; do
    grep -qE -- "$vzorec" "$G" || { cat "$G" >&2; echo "vgradi.sh: $G nima '$vzorec'" >&2; exit 1; }
done
for f in lib/libwebkitgtk-6.0.so.4 lib/libjavascriptcoregtk-6.0.so.1 lib/libsoup-3.0.so.0 \
         lib/girepository-1.0/WebKit-6.0.typelib lib/girepository-1.0/Soup-3.0.typelib \
         libexec/webkitgtk-6.0/WebKitWebProcess libexec/webkitgtk-6.0/WebKitNetworkProcess; do
    [ -e "$WK/$f" ] || { echo "vgradi.sh: v arhivu manjka $f" >&2; exit 1; }
done
DAV1D="${SAFEER_DAV1D:-}"
if [ -n "$DAV1D" ]; then
    [ -f "$DAV1D/libgstdav1d.so" ] || { echo "vgradi.sh: v $DAV1D ni libgstdav1d.so (packaging/webkit-deb/dav1d.sh)" >&2; exit 1; }
    install -D -m 644 "$DAV1D/libgstdav1d.so" "$WK/lib/gstreamer-1.0/libgstdav1d.so"
    install -D -m 644 -t "$WK/share/doc/gst-plugin-dav1d" "$DAV1D/LICENSE-MIT" "$DAV1D/LICENSE-APACHE" "$DAV1D/gradnja.txt"
    echo "vgradi.sh: dav1ddec $(stat -c %s "$DAV1D/libgstdav1d.so") B v $PREDPONA/lib/gstreamer-1.0 ($(head -1 "$DAV1D/gradnja.txt"))" >&2
fi
# Knjiznice, ki jih ima vsak sistem v drugi razlicici (soname), gredo v paket (RUNPATH $ORIGIN), da se .deb namesti tudi
# na Linux Mint 23 / Ubuntu 26.04 in Debian 13 (21. 10. 2026 izmerjeno v vsebnikih: libicu74, libjxl0.7, libjpeg8,
# libxml2 (26.04: libxml2.so.16) niso na voljo - »not installable«; prototip z vgrajenimi se namesti, ldd brez manjkajocih,
# WebKit 2.54.1 se nalozi). libxslt gre zraven, ker je na novih sistemih povezan z drugim libxml2. Zaprtje odvisnosti:
# vgrajena knjiznica, ki potrebuje drugo prenosno (libjxl -> libhwy, libxml2 -> ICU), jo dobi tudi.
PRENOSNE='^(libicu(uc|i18n|data)\.so\.[0-9]+|libjxl(_threads|_cms)?\.so\.[0-9.]+|libhwy\.so\.[0-9]+|libjpeg\.so\.8|libxml2\.so\.2|libxslt\.so\.1|libexslt\.so\.0)$'
vgrajeno=1
while [ "$vgrajeno" = 1 ]; do
    vgrajeno=0
    while IFS= read -r -d '' f; do
        file -b "$f" | grep -q '^ELF' || continue
        for so in $(readelf -d "$f" 2>/dev/null | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p'); do
            [[ "$so" =~ $PRENOSNE ]] || continue
            [ -e "$WK/lib/$so" ] && continue
            pot="$(ldconfig -p | awk -v s="$so" '$1==s && /x86-64/ {print $NF; exit}')"
            [ -n "$pot" ] || { echo "vgradi.sh: prenosne knjiznice $so ni na sistemu gradnje (knjiznice.sh)" >&2; exit 1; }
            cp -L "$pot" "$WK/lib/$so"
            patchelf --set-rpath '$ORIGIN' "$WK/lib/$so"
            pkg="$(dpkg -S "$(readlink -f "$pot")" | head -1 | cut -d: -f1)"
            install -D -m 644 "/usr/share/doc/$pkg/copyright" "$WK/share/doc/vgrajene/$pkg/copyright"
            basename "$(readlink -f "$pot")" > "$WK/share/doc/vgrajene/$pkg/razlicica"
            echo "vgradi.sh: vgrajena $so iz $pkg ($(stat -c %s "$WK/lib/$so") B)" >&2
            vgrajeno=1
        done
    done < <(find "$WK" -type f -print0)
done

# Pravice kot v paketih Debiana (arhiv je iz gradnje kot root, a umask CI ni nujno 022).
find "$WK" -type d -exec chmod 755 {} +
find "$WK" -type f -exec chmod go-w {} +
echo "vgradi.sh: $(du -sh "$WK" | cut -f1) v $PREDPONA ($(grep -m1 'clang version' "$G"))" >&2

# Odvisnosti ELF datotek. Nase knjiznice (libsoup, libjavascriptcoregtk, libwebkitgtk) so v paketu in nimajo podatkov
# o paketu - zato --ignore-missing-info; vse druge mora dpkg-shlibdeps najti v namescenih paketih noble.
ELF=()
while IFS= read -r -d '' f; do
    if file -b "$f" | grep -q '^ELF'; then ELF+=("$f"); fi
done < <(find "$WK" -type f -print0)
DELO="$(mktemp -d)"
mkdir -p "$DELO/debian"
printf 'Source: %s\n\nPackage: %s\nArchitecture: any\n' "$PAKET" "$PAKET" > "$DELO/debian/control"
( cd "$DELO" && dpkg-shlibdeps -O --ignore-missing-info -l"$WK/lib" -e "${ELF[@]}" 2>"$DELO/opozorila" ) \
    | sed -n 's/^shlibs:Depends=//p' > "$DELO/odvisnosti" || { cat "$DELO/opozorila" >&2; exit 1; }
grep -v -e "no dependency information found for" -e "binaries to analyze should already be installed" "$DELO/opozorila" >&2 || true
[ -s "$DELO/odvisnosti" ] || { echo "vgradi.sh: dpkg-shlibdeps ni vrnil odvisnosti" >&2; exit 1; }
if [ -n "$DAV1D" ] && ! grep -qE '(^|, )libdav1d7( |,|$)' "$DELO/odvisnosti"; then
    cat "$DELO/odvisnosti" >&2; echo "vgradi.sh: med odvisnostmi ni libdav1d7 (dav1ddec)" >&2; exit 1
fi
cat "$DELO/odvisnosti"
rm -rf "$DELO"
