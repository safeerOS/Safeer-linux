#!/usr/bin/env bash
# ==============================================================================
# Nadaljevanje gradnje safeer-webkit iz stanja pred BOLT (lastnik, 19. 10. 2026: »gradnja lahko jemlje iz predpomnilnika
# in nadaljuje tam, kjer je padla«). CI 39185371479: BOLT je padel po 2 h 25 min prevajanja, stanja ni bilo nikjer.
#
#   SAFEER_BOLT_PREDBOLT=ARHIV.tar.zst nadaljuj.sh /usr/lib/safeer-webkit IZHOD.tar.zst
#
# ARHIV zapise bolt.sh pred prvim poskusom (namescena predpona s simboli in relokacijami, zapis CMake in stevci
# build.ninja); CI ga shrani v predpomnilnik tudi, ce BOLT pade. Tu: razpakiraj, BOLT (bolt.sh), zapis gradnje, strip in
# arhiv - isti koraki in isti gradnja.txt kot konec zgradi.sh. zgradi.sh ostane nespremenjen: je v kljucu profila PGO
# (posel webkit-deb-profil) in sprememba bi pomenila novo instrumentirano gradnjo in ucni tek.
# ==============================================================================
set -euo pipefail
KOREN="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PREDPONA="${1:?Uporaba: nadaljuj.sh /usr/lib/safeer-webkit IZHOD.tar.zst}"
IZHOD="${2:?Uporaba: nadaljuj.sh /usr/lib/safeer-webkit IZHOD.tar.zst}"
[ "$PREDPONA" = /usr/lib/safeer-webkit ] || { echo "PREDPONA mora biti /usr/lib/safeer-webkit (paket safeer-webkit)" >&2; exit 2; }
ARHIV="${SAFEER_BOLT_PREDBOLT:?SAFEER_BOLT_PREDBOLT=arhiv stanja pred BOLT}"
[ -f "$ARHIV" ] || { echo "nadaljuj.sh: ni $ARHIV - polna gradnja je zgradi.sh" >&2; exit 1; }
DELO="${SAFEER_WEBKIT_DELO:-$KOREN/build/webkit-deb}"
LLVM=/usr/lib/llvm-22/bin
[ -x "$LLVM/clang" ] || { echo "Ni Clanga 22 ($LLVM/clang): najprej packaging/webkit-deb/odvisnosti.sh" >&2; exit 1; }

modul() { python3 "$KOREN/packaging/webkit-deb/modul.py" "$1"; }
polje() { python3 -c 'import json,sys; v=json.load(sys.stdin)[sys.argv[1]]; print("\n".join(v) if isinstance(v,list) else v)' "$1"; }
SOUP_JSON="$(modul "$KOREN/packaging/libsoup/libsoup3-safeer.yml")"
WK_JSON="$(modul "$KOREN/packaging/webkit/webkitgtk6-safeer.yml")"

# Okolje kot v zgradi.sh (ucni tek BOLT nalozi nase knjiznice in typelibe).
export PATH="$LLVM:$PATH" CC="$LLVM/clang" CXX="$LLVM/clang++" AR="$LLVM/llvm-ar" NM="$LLVM/llvm-nm" RANLIB="$LLVM/llvm-ranlib"
export PKG_CONFIG_PATH="$PREDPONA/lib/pkgconfig"
export LD_LIBRARY_PATH="$PREDPONA/lib"
export XDG_DATA_DIRS="$PREDPONA/share:/usr/share"
export GI_TYPELIB_PATH="$PREDPONA/lib/girepository-1.0"

# --- stanje pred BOLT ---------------------------------------------------------------------------------------------------
Z="$DELO/predbolt"
rm -rf "$PREDPONA" "$Z"
zstd -q -t "$ARHIV"
tar -C / -I zstd -xf "$ARHIV"
for f in "$Z/cmake.txt" "$Z/stevci.txt" "$PREDPONA/lib/libwebkitgtk-6.0.so.4" "$PREDPONA/lib/libjavascriptcoregtk-6.0.so.1"; do
    [ -e "$f" ] || { echo "nadaljuj.sh: arhiv $ARHIV nima $f" >&2; exit 1; }
done
ls -l "$PREDPONA/lib"

# --- BOLT -----------------------------------------------------------------------------------------------------------------
rm -f "$DELO/bolt/povzetek.txt"
bash "$KOREN/packaging/webkit-deb/bolt.sh" "$PREDPONA" "$DELO/bolt"

# --- zapis gradnje (enak kot v zgradi.sh; zapis CMake in stevci build.ninja iz gradnje, ki je ustvarila arhiv) ---------
d="$PREDPONA/share/webkitgtk-safeer"
mkdir -p "$d"
WK_ARHIV="$(basename "$(polje url <<< "$WK_JSON")")"
SOUP_ARHIV="$(basename "$(polje url <<< "$SOUP_JSON")")"
{
    "$LLVM/clang" --version | head -n 1
    cat "$Z/cmake.txt"
    cat "$Z/stevci.txt"
    if [ -f "$DELO/bolt/povzetek.txt" ]; then cat "$DELO/bolt/povzetek.txt"; else echo "bolt: ne"; fi
    echo "webkitgtk: $(basename "$WK_ARHIV" .tar.xz) $(polje sha256 <<< "$WK_JSON")"
    echo "libsoup: $(basename "$SOUP_ARHIV" .tar.xz) $(polje sha256 <<< "$SOUP_JSON")"
    for p in $(polje popravki <<< "$WK_JSON") $(polje popravki <<< "$SOUP_JSON"); do echo "popravek: $(basename "$p") $(sha256sum "$p" | cut -d' ' -f1)"; done
    echo "predpona: $PREDPONA"
    echo "sistem: $(. /etc/os-release; echo "$PRETTY_NAME") $(getconf GNU_LIBC_VERSION)"
} > "$d/gradnja.txt"
cat "$d/gradnja.txt"

# --- pospravi in odstrani simbole (kot zgradi.sh) -----------------------------------------------------------------------
rm -rf "$PREDPONA/include" "$PREDPONA/lib/pkgconfig" "$PREDPONA/share/gir-1.0" "$PREDPONA/bin" "$PREDPONA/share/doc" \
    "$PREDPONA/libexec/installed-tests" "$PREDPONA/share/installed-tests"
find "$PREDPONA" -type f \( -name '*.so*' -o -perm -u+x \) -exec sh -c \
    'for f; do if file -b "$f" | grep -q "^ELF"; then "$0" --strip-unneeded "$f"; fi; done' "$LLVM/llvm-strip" {} +
find "$PREDPONA" -name '*.la' -delete
du -sh "$PREDPONA"

mkdir -p "$(dirname "$IZHOD")"
rm -f "$IZHOD" "$IZHOD.del"
tar -C / -I 'zstd -19 -T0' -cf "$IZHOD.del" "${PREDPONA#/}"
zstd -q -t "$IZHOD.del"
mv "$IZHOD.del" "$IZHOD"
ls -l "$IZHOD"
