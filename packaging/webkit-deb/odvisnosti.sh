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

apt-get update -q
apt-get install -y -q --no-install-recommends ca-certificates curl gnupg xz-utils zstd patch file python3 python3-yaml
# Kljuc apt.llvm.org (oklepni zapis .asc apt prebere neposredno, brez gpg --dearmor).
install -d /etc/apt/keyrings
curl -fsSL https://apt.llvm.org/llvm-snapshot.gpg.key -o /etc/apt/keyrings/apt.llvm.org.asc
echo "deb [signed-by=/etc/apt/keyrings/apt.llvm.org.asc] https://apt.llvm.org/${VERSION_CODENAME:-noble}/ llvm-toolchain-${VERSION_CODENAME:-noble}-22 main" \
    > /etc/apt/sources.list.d/llvm-22.list
apt-get update -q
apt-get install -y -q --no-install-recommends \
    clang-22 lld-22 llvm-22 libclang-rt-22-dev \
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
