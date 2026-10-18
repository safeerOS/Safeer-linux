#!/usr/bin/env bash
# Knjiznice noble, s katerimi je povezan nas WebKitGTK in libsoup (packaging/webkit-deb/zgradi.sh) - za pakiranje:
# dpkg-shlibdeps (packaging/webkit-deb/vgradi.sh) mora vsako knjiznico najti v namescenem paketu, da zapise odvisnost.
# Sistemski libwebkitgtk-6.0-4 (2.52.6) jih ne potegne vseh: Ubuntu ga gradi brez JPEG XL, AVIF in WOFF2.
# libdav1d7: dekoder AV1 dav1ddec v predponi (packaging/webkit-deb/dav1d.sh).
# Tece kot root (CI: posla brskalnik in safeer-os). Paketi so iz main in universe (Linux Mint ima oba).
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -q --no-install-recommends \
    libgtk-4-1 libjxl0.7 libavif16 libwoff1 libmanette-0.2-0 libhyphen0 libenchant-2-2 libsecret-1-0 \
    libgstreamer1.0-0 libgstreamer-plugins-base1.0-0 libgstreamer-plugins-bad1.0-0 libgstreamer-gl1.0-0 \
    liblcms2-2 libharfbuzz-icu0 libgbm1 libepoxy0 libdrm2 libatspi2.0-0t64 libseccomp2 libsystemd0 libtasn1-6 \
    libgcrypt20 libxslt1.1 libxml2 libsqlite3-0 libicu74 libwayland-client0 libwayland-egl1 libwayland-server0 \
    libwebp7 libwebpdemux2 libwebpmux3 libjpeg-turbo8 libpng16-16t64 libfontconfig1 libfreetype6 libx11-6 \
    libnghttp2-14 libpsl5t64 libbrotli1 libzstd1 libgssapi-krb5-2 libgudev-1.0-0 libdav1d7 \
    bubblewrap xdg-dbus-proxy glib-networking dpkg-dev file zstd
