#!/usr/bin/env bash
# ==============================================================================
# Nas WebKitGTK 6.0 (GTK4) in libsoup 3 za pakete .deb (Linux Mint 22 / Ubuntu 24.04) - ISTI izvor, popravki in
# moznosti kot v Flatpaku (packaging/webkit/webkitgtk6-safeer.yml, packaging/libsoup/libsoup3-safeer.yml, prebere ju
# packaging/webkit-deb/modul.py), prevedeno s Clangom 22 (apt.llvm.org), ThinLTO in lld.
#
#   zgradi.sh PREDPONA [IZHOD.tar.zst]      npr. zgradi.sh /usr/lib/safeer-browser/webkit build/webkit-brskalnik.tar.zst
#
# Namesti v zasebno PREDPONO (nikoli v /usr/lib/x86_64-linux-gnu): sistemski libwebkitgtk-6.0-4 in libsoup-3.0-0 ostaneta
# nedotaknjena in se z nasima ne tepeta. WebKit ima poti pomoznih procesov (WebKitWebProcess, WebKitNetworkProcess,
# WebKitGPUProcess) prevedene v knjiznico (LIBEXECDIR v PREDPONI) - zato ima vsak paket svojo gradnjo s svojo predpono
# (glej build_deb.sh, build_os_deb.sh). Knjiznice imajo DT_RPATH na PREDPONA/lib (WebKit povezuje z
# --disable-new-dtags), typelibi pa absolutno pot do knjiznice - Python jih najde prek core/zasebni_webkit.py
# (GI_TYPELIB_PATH), brez LD_LIBRARY_PATH, ki bi se prenesel v vse programe, ki jih zazene Safeer OS.
# Peskovnik bubblewrap ostane vklopljen (sistemska /usr/bin/bwrap in /usr/bin/xdg-dbus-proxy).
#
# PGO (neobvezno, enako kot packaging/webkit/pgo.py za Flatpak):
#   SAFEER_WEBKIT_PGO=ucenje                          instrumentirana gradnja (-DENABLE_LLVM_PROFILE_GENERATION=ON)
#   SAFEER_WEBKIT_PGO=uporaba SAFEER_WEBKIT_PROFRAW=MAPA   gradnja s profilom (*.profraw iz ucnega teka TE gradnje)
# Odvisnosti: packaging/webkit-deb/odvisnosti.sh. Tece kot root (namesti v PREDPONO); traja 2-3 h na 4 jedrih.
# ==============================================================================
set -euo pipefail
KOREN="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PREDPONA="${1:?Uporaba: zgradi.sh PREDPONA [IZHOD.tar.zst]}"
IZHOD="${2:-}"
case "$PREDPONA" in /usr/lib/safeer-*/webkit) ;; *) echo "PREDPONA mora biti /usr/lib/safeer-<paket>/webkit" >&2; exit 2 ;; esac
DELO="${SAFEER_WEBKIT_DELO:-$KOREN/build/webkit-deb}"
PGO="${SAFEER_WEBKIT_PGO:-}"
LLVM=/usr/lib/llvm-22/bin
[ -x "$LLVM/clang" ] || { echo "Ni Clanga 22 ($LLVM/clang): najprej packaging/webkit-deb/odvisnosti.sh" >&2; exit 1; }
JEDRA="$(nproc)"

modul() { python3 "$KOREN/packaging/webkit-deb/modul.py" "$1"; }
polje() { python3 -c 'import json,sys; v=json.load(sys.stdin)[sys.argv[1]]; print("\n".join(v) if isinstance(v,list) else v)' "$1"; }
SOUP_JSON="$(modul "$KOREN/packaging/libsoup/libsoup3-safeer.yml")"
WK_JSON="$(modul "$KOREN/packaging/webkit/webkitgtk6-safeer.yml")"

# Prenos z obvezno preverbo SHA-256 iz modula (isti arhiv kot Flatpak).
prenesi() {
    local url="$1" sha="$2" cilj="$DELO/prenosi/$(basename "$1")"
    mkdir -p "$DELO/prenosi"
    if [ ! -f "$cilj" ] || ! echo "$sha  $cilj" | sha256sum -c --quiet - 2>/dev/null; then
        curl -fL --retry 3 -o "$cilj.del" "$url"
        mv "$cilj.del" "$cilj"
    fi
    echo "$sha  $cilj" | sha256sum -c --quiet -
    echo "$cilj"
}
razpakiraj() {   # arhiv, popravki (vrstice) -> mapa izvora
    local arhiv="$1" popravki="$2" mapa
    mapa="$DELO/izvor/$(basename "$arhiv" .tar.xz)"
    rm -rf "$mapa" && mkdir -p "$DELO/izvor"
    tar -xf "$arhiv" -C "$DELO/izvor"
    [ -d "$mapa" ] || { echo "Arhiv $arhiv nima mape $(basename "$mapa")" >&2; exit 1; }
    while IFS= read -r p; do
        [ -n "$p" ] || continue
        echo "Popravek: $(basename "$p")" >&2
        patch -d "$mapa" -p1 --forward --batch < "$p" >&2
    done <<< "$popravki"
    echo "$mapa"
}

export PATH="$LLVM:$PATH" CC="$LLVM/clang" CXX="$LLVM/clang++" AR="$LLVM/llvm-ar" NM="$LLVM/llvm-nm" RANLIB="$LLVM/llvm-ranlib"
# Gradnja vidi nas libsoup (pkg-config, gir za g-ir-scanner, knjiznica za izpis introspekcije); paket teh spremenljivk
# ne potrebuje (DT_RPATH in absolutne poti v typelibih).
export PKG_CONFIG_PATH="$PREDPONA/lib/pkgconfig"
export LD_LIBRARY_PATH="$PREDPONA/lib"
export XDG_DATA_DIRS="$PREDPONA/share:/usr/share"
export GI_TYPELIB_PATH="$PREDPONA/lib/girepository-1.0"

rm -rf "$PREDPONA"
mkdir -p "$PREDPONA"

# --- libsoup 3 (pred WebKitom: WebKit se prevede in poveze z njim) ------------------------------------------------
SOUP_ARHIV="$(prenesi "$(polje url <<< "$SOUP_JSON")" "$(polje sha256 <<< "$SOUP_JSON")")"
SOUP_IZVOR="$(razpakiraj "$SOUP_ARHIV" "$(polje popravki <<< "$SOUP_JSON")")"
mapfile -t SOUP_MOZNOSTI < <(polje moznosti <<< "$SOUP_JSON")
rm -rf "$DELO/soup"
CFLAGS="-O2" meson setup "$DELO/soup" "$SOUP_IZVOR" --prefix="$PREDPONA" --buildtype=release \
    -Dintrospection=enabled "${SOUP_MOZNOSTI[@]}"
ninja -C "$DELO/soup" -j "$JEDRA"
ninja -C "$DELO/soup" install

# --- WebKitGTK 6.0 -------------------------------------------------------------------------------------------------
WK_ARHIV="$(prenesi "$(polje url <<< "$WK_JSON")" "$(polje sha256 <<< "$WK_JSON")")"
WK_IZVOR="$(razpakiraj "$WK_ARHIV" "$(polje popravki <<< "$WK_JSON")")"
mapfile -t WK_MOZNOSTI < <(polje moznosti <<< "$WK_JSON")
while IFS='=' read -r k v; do [ -n "$k" ] && [ "$k" != CC ] && [ "$k" != CXX ] && export "$k=$v"; done \
    < <(python3 -c 'import json,sys; [print("%s=%s" % kv) for kv in json.load(sys.stdin)["okolje"].items()]' <<< "$WK_JSON")
PGO_MOZNOSTI=()
case "$PGO" in
    "") ;;
    ucenje) PGO_MOZNOSTI=(-DENABLE_LLVM_PROFILE_GENERATION=ON) ;;
    uporaba)
        PROFRAW="${SAFEER_WEBKIT_PROFRAW:?SAFEER_WEBKIT_PROFRAW=mapa z .profraw}"
        mkdir -p "$DELO/pgo"
        # Profil mora biti iz te gradnje (isti izvor, popravki, sistemske glave noble in Clang 22): llvm-profdata iste
        # razlicice kot prevajalnik. Profil iz Flatpaka (glave GNOME 50) bi se za del funkcij ne ujemal.
        "$LLVM/llvm-profdata" merge --output="$DELO/pgo/webkit.profdata" "$PROFRAW"/*.profraw
        "$LLVM/llvm-profdata" show --detailed-summary "$DELO/pgo/webkit.profdata" | head -n 30
        PGO_MOZNOSTI=(-DUSE_PGO_PROFILE=ON "-DPGO_PROFILE_PATH=$DELO/pgo/webkit.profdata") ;;
    *) echo "SAFEER_WEBKIT_PGO je ucenje ali uporaba" >&2; exit 2 ;;
esac
rm -rf "$DELO/webkit"
cmake -S "$WK_IZVOR" -B "$DELO/webkit" -G Ninja \
    "${WK_MOZNOSTI[@]}" "${PGO_MOZNOSTI[@]}" \
    -DCMAKE_INSTALL_PREFIX="$PREDPONA" \
    -DCMAKE_INSTALL_RPATH="$PREDPONA/lib" \
    -DCMAKE_C_FLAGS="$(polje cflags <<< "$WK_JSON")" \
    -DCMAKE_CXX_FLAGS="$(polje cxxflags <<< "$WK_JSON")" \
    -DBWRAP_EXECUTABLE=/usr/bin/bwrap \
    -DDBUS_PROXY_EXECUTABLE=/usr/bin/xdg-dbus-proxy
# Hitra preverba skripte (minute namesto ur): libsoup, nastavitev CMake WebKita in vsi koraki za prevodom (typelibi,
# zapis gradnje, pospravljanje, arhiv) - brez prevoda WebKita. Samo za preizkus; arhiv brez WebKita ni za paket.
if [ "${SAFEER_WEBKIT_SAMO_CMAKE:-0}" = 1 ]; then
    echo "SAFEER_WEBKIT_SAMO_CMAKE: CMake WebKita je uspel, prevod WebKita preskocen"
else
    ninja -C "$DELO/webkit" -j "$JEDRA"
    ninja -C "$DELO/webkit" install
fi

# --- typelibi z absolutno potjo do nasih knjiznic (packaging/webkit-deb/typelibi.py) -------------------------------
python3 "$KOREN/packaging/webkit-deb/typelibi.py" "$PREDPONA"
ls -l "$PREDPONA/lib/girepository-1.0"

# --- zapis gradnje (kot post-install modula Flatpak; tests in CI ga berejo) -----------------------------------------
d="$PREDPONA/share/webkitgtk-safeer"
mkdir -p "$d"
{
    "$LLVM/clang" --version | head -n 1
    grep -E '^(CMAKE_BUILD_TYPE|CMAKE_CXX_COMPILER|CMAKE_INSTALL_PREFIX|LTO_MODE|ENABLE_LLVM_PROFILE_GENERATION|USE_PGO_PROFILE):' "$DELO/webkit/CMakeCache.txt"
    for z in -fuse-ld=lld -flto=thin -fprofile-generate -fprofile-use; do echo "build.ninja $z: $(grep -c -e "$z" "$DELO/webkit/build.ninja")"; done
    echo "webkitgtk: $(basename "$WK_ARHIV" .tar.xz) $(polje sha256 <<< "$WK_JSON")"
    echo "libsoup: $(basename "$SOUP_ARHIV" .tar.xz) $(polje sha256 <<< "$SOUP_JSON")"
    for p in $(polje popravki <<< "$WK_JSON") $(polje popravki <<< "$SOUP_JSON"); do echo "popravek: $(basename "$p") $(sha256sum "$p" | cut -d' ' -f1)"; done
    echo "predpona: $PREDPONA"
    echo "sistem: $(. /etc/os-release; echo "$PRETTY_NAME") $(getconf GNU_LIBC_VERSION)"
} > "$d/gradnja.txt"
cat "$d/gradnja.txt"

# --- pospravi kot cleanup modulov Flatpak in odstrani simbole (kot dh_strip) ------------------------------------------
rm -rf "$PREDPONA/include" "$PREDPONA/lib/pkgconfig" "$PREDPONA/share/gir-1.0" "$PREDPONA/bin" "$PREDPONA/share/doc" \
    "$PREDPONA/libexec/installed-tests" "$PREDPONA/share/installed-tests"
find "$PREDPONA" -type f \( -name '*.so*' -o -perm -u+x \) -exec sh -c \
    'for f; do if file -b "$f" | grep -q "^ELF"; then "$0" --strip-unneeded "$f"; fi; done' "$LLVM/llvm-strip" {} +
find "$PREDPONA" -name '*.la' -delete
du -sh "$PREDPONA"

if [ -n "$IZHOD" ]; then
    mkdir -p "$(dirname "$IZHOD")"
    tar -C / -I 'zstd -19 -T0' -cf "$IZHOD" "${PREDPONA#/}"
    ls -l "$IZHOD"
fi
