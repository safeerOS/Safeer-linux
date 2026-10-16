#!/usr/bin/env bash
# Nas WebKitGTK in libsoup (arhiv iz packaging/webkit-deb/zgradi.sh) v drevo paketa .deb.
#
#   vgradi.sh KOREN_PAKETA PAKET ARHIV.tar.zst     npr. vgradi.sh build/deb safeer-browser build/webkit-safeer-browser.tar.zst
#
# Razpakira /usr/lib/PAKET/webkit, preveri, da je arhiv zgrajen za to predpono (poti pomoznih procesov so prevedene v
# knjiznico) in s Clangom 22 + ThinLTO, ter na stdout izpise odvisnosti knjiznic (dpkg-shlibdeps) za polje Depends.
# Sporocila gredo na stderr.
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
cat "$DELO/odvisnosti"
rm -rf "$DELO"
