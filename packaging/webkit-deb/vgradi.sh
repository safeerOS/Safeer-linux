#!/usr/bin/env bash
# Nas WebKitGTK in libsoup (arhiv iz packaging/webkit-deb/zgradi.sh) v drevo paketa .deb.
#
#   vgradi.sh KOREN_PAKETA PAKET ARHIV.tar.zst     npr. vgradi.sh build/deb safeer-browser build/webkit-safeer-browser.tar.zst
#
# Razpakira /usr/lib/PAKET/webkit, preveri, da je arhiv zgrajen za to predpono (poti pomoznih procesov so prevedene v
# knjiznico) in s Clangom 22 + ThinLTO, ter na stdout izpise odvisnosti knjiznic (dpkg-shlibdeps) za polje Depends.
# Sporocila gredo na stderr.
#
# SAFEER_DAV1D=MAPA (izhod packaging/webkit-deb/dav1d.sh): dekoder AV1 dav1ddec v PREDPONA/lib/gstreamer-1.0 - noble
# nima vticnika GStreamer za libdav1d; core/zasebni_webkit.py mapo doda v GST_PLUGIN_PATH. Odvisnost libdav1d7 zapise
# dpkg-shlibdeps iz knjiznice vticnika.
set -euo pipefail
KOREN="${1:?KOREN_PAKETA}"
PAKET="${2:?PAKET}"
ARHIV="${3:?ARHIV}"
PREDPONA="/usr/lib/$PAKET/webkit"
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
