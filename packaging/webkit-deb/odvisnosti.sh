#!/usr/bin/env bash
# Orodja in knjiznice za gradnjo nasega WebKitGTK in libsoup za pakete .deb (packaging/webkit-deb/zgradi.sh) na
# Ubuntu 24.04 / Linux Mint 22 (noble). Tece kot root (CI: vsebnik ubuntu:24.04; testni PC: sudo).
#
# Clang/LLVM 22 iz apt.llvm.org (skladisce llvm-toolchain-noble-22, preverjeno 15. 10. 2026: clang-22 1:22.1.8) - isti
# glavni prevajalnik kot razsiritev Flatpak org.freedesktop.Sdk.Extension.llvm22. WebKitGTK od 2.53.1 podpira ThinLTO
# in PGO samo s Clangom. Knjiznice so Ubuntujeve (noble): seznam je Build-Depends Ubuntujevega webkit2gtk 2.52.6 za
# noble brez GTK3 in dokumentacije, z libsoup (nghttp2, psl, brotli, zstd, krb5) in z Rubyjem/Perlom/Pythonom za
# generatorje WebKita. Najmanjse razlicice iz Source/cmake/OptionsGTK.cmake 2.54.1 (GLib 2.70, GTK 4.6, GStreamer 1.18.4,
# ICU 70.1, HarfBuzz 2.7.4, libxml2 2.9.13, CMake 3.20, meson 0.62 za libsoup) noble izpolni brez dodatnih knjiznic.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
. /etc/os-release
[ "${VERSION_CODENAME:-}" = noble ] || echo "Opozorilo: gradnja je preverjena na noble (Ubuntu 24.04), to je ${VERSION_CODENAME:-?}." >&2

# Pripeto (lastnik 18. 10. 2026: ne zaupamo prenosu na slepo). Prstni odtis kljuca apt.llvm.org (»Sylvestre Ledru - Debian
# LLVM packages«) je objavljen na https://apt.llvm.org/; kljuc, ki ga prenesemo, mora imeti natanko tega - sicer gradnja
# konca, preden apt kateremukoli paketu zaupa. Clang je pripet na natancno gradnjo apt.llvm.org (preverjeno 18. 10. 2026,
# Packages.gz llvm-toolchain-noble-22): drug prevajalnik ne sme tiho priti v WebKit iz predpomnilnika. Ko ga apt.llvm.org
# umakne, gradnja pove, kaj ponuja; nova vrednost tu spremeni kljuc predpomnilnika (nova gradnja WebKita - tako mora biti).
LLVM_KLJUC_ODTIS="6084F3CF814B57C1CF12EFD515CF4D18AF4F7421"
LLVM_RAZLICICA="22.1.8"
LLVM_PAKET="1:22.1.8~++20260714014902+ca7933e47d3a-1~exp1~20260714135019.80"

apt-get update -q
apt-get install -y -q --no-install-recommends ca-certificates curl gnupg xz-utils zstd patch file python3 python3-yaml
# Kljuc apt.llvm.org (oklepni zapis .asc apt prebere neposredno, brez gpg --dearmor) - najprej v zacasno mapo in preverba.
install -d /etc/apt/keyrings
ZACASNO="$(mktemp -d)"
trap 'gpgconf --homedir "$ZACASNO" --kill all >/dev/null 2>&1 || true; rm -rf "$ZACASNO"' EXIT
curl -fsSL https://apt.llvm.org/llvm-snapshot.gpg.key -o "$ZACASNO/llvm.asc"
ODTISI="$(gpg --batch --homedir "$ZACASNO" --show-keys --with-colons "$ZACASNO/llvm.asc" 2>/dev/null \
    | awk -F: '$1 == "pub" { p = 1; next } $1 == "fpr" && p { print $10; p = 0 }')"
if [ "$ODTISI" != "$LLVM_KLJUC_ODTIS" ]; then
    echo "NAPAKA: kljuc apt.llvm.org ima prstni odtis '${ODTISI//$'\n'/ }', pripet je $LLVM_KLJUC_ODTIS - ne zaupamo mu." >&2
    exit 1
fi
install -m 644 "$ZACASNO/llvm.asc" /etc/apt/keyrings/apt.llvm.org.asc
echo "deb [signed-by=/etc/apt/keyrings/apt.llvm.org.asc] https://apt.llvm.org/${VERSION_CODENAME:-noble}/ llvm-toolchain-${VERSION_CODENAME:-noble}-22 main" \
    > /etc/apt/sources.list.d/llvm-22.list
apt-get update -q
# BOLT (post-link optimizacija v zgradi.sh, packaging/webkit-deb/bolt.sh) iz iste gradnje LLVM kot prevajalnik
# (apt.llvm.org noble-22 ponuja bolt-22 v LLVM_PAKET, preverjeno 18. 10. 2026 v Packages llvm-toolchain-noble-22).
for PAKET in clang-22 bolt-22; do
    PONUDBA="$(apt-cache madison "$PAKET" | awk -F'|' '{ gsub(/ /, "", $2); print $2 }' | tr '\n' ' ')"
    case " $PONUDBA " in
        *" $LLVM_PAKET "*) ;;
        *) echo "NAPAKA: apt.llvm.org nima vec $PAKET $LLVM_PAKET (ponuja: ${PONUDBA:-nic}). Posodobi LLVM_PAKET v" \
                "packaging/webkit-deb/odvisnosti.sh - to sprozi novo gradnjo WebKita." >&2
           exit 1 ;;
    esac
done
apt-get install -y -q --no-install-recommends \
    "clang-22=$LLVM_PAKET" "lld-22=$LLVM_PAKET" "llvm-22=$LLVM_PAKET" "libclang-rt-22-dev=$LLVM_PAKET" \
    "bolt-22=$LLVM_PAKET" "libbolt-22-dev=$LLVM_PAKET" \
    cmake ninja-build meson pkgconf gperf bison flex ruby perl python3 unifdef \
    gobject-introspection libgirepository1.0-dev libglib2.0-dev libglib2.0-dev-bin \
    libgtk-4-dev libcairo2-dev libharfbuzz-dev libicu-dev libfontconfig-dev libfreetype-dev libgcrypt20-dev \
    libtasn1-6-dev libjpeg-dev libpng-dev libwebp-dev libavif-dev libjxl-dev libwoff-dev liblcms2-dev libopenjp2-7-dev \
    libxml2-dev libxslt1-dev libsqlite3-dev zlib1g-dev libepoxy-dev libdrm-dev libgbm-dev libegl-dev libgl-dev libgles-dev \
    libwayland-dev wayland-protocols libx11-dev libxt-dev libatspi2.0-dev \
    libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev libgstreamer-plugins-bad1.0-dev \
    libhyphen-dev libenchant-2-dev libsecret-1-dev libmanette-0.2-dev libgudev-1.0-dev libsystemd-dev libseccomp-dev \
    libsysprof-capture-4-dev bubblewrap xdg-dbus-proxy \
    libnghttp2-dev libpsl-dev libbrotli-dev libzstd-dev libkrb5-dev glib-networking \
    gettext dpkg-dev
/usr/lib/llvm-22/bin/clang --version | head -n 1
[ "$(dpkg-query -W -f '${Version}' clang-22)" = "$LLVM_PAKET" ]
[ "$(dpkg-query -W -f '${Version}' bolt-22)" = "$LLVM_PAKET" ] || { echo "NAPAKA: bolt-22 ni $LLVM_PAKET" >&2; exit 1; }
/usr/lib/llvm-22/bin/clang --version | head -n 1 | grep -qE "clang version ${LLVM_RAZLICICA//./\\.}( |$)" \
    || { echo "NAPAKA: clang-22 ni razlicica $LLVM_RAZLICICA" >&2; exit 1; }
