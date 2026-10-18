#!/usr/bin/env bash
# Safeer OS AppImage (Safeer OS + Safeer Control). Release builds run on Ubuntu 24.04 (glibc 2.39): GTK4 and
# WebKitGTK 6.0 exist from Linux Mint 22 on; newer hosts are diagnostic only (ALLOW_NEWER_GLIBC=1).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[ "$(uname -m)" = x86_64 ] || { echo 'AppImage currently supports x86_64 only' >&2; exit 1; }
# Safeer OS na GTK4 (WebKitGTK 6.0) tece od Linux Mint 22 / Ubuntu 24.04 naprej (Mint 21 WebKitGTK 6.0 nima), zato
# se AppImage gradi na Ubuntu 24.04 (glibc 2.39). Brskalnik (build_appimage.sh) ostane na 22.04.
if [ "$(getconf GNU_LIBC_VERSION | cut -d' ' -f2)" != 2.39 ] && [ "${ALLOW_NEWER_GLIBC:-0}" != 1 ]; then
    echo 'Build the Safeer OS AppImage on Ubuntu 24.04. Set ALLOW_NEWER_GLIBC=1 for a host-specific diagnostic build.' >&2
    exit 1
fi
: "${LINUXDEPLOY:?Set LINUXDEPLOY to the verified linuxdeploy executable}"
export APPIMAGE_EXTRACT_AND_RUN=1
APPID=io.github.memelandfaner.SafeerOS
STAGE="$ROOT/build/stage-os-appimage"
APPDIR="$ROOT/build/SafeerOS.AppDir"
rm -rf "$STAGE" "$APPDIR"
mkdir -p "$APPDIR" "$ROOT/dist"
bash packaging/install_control_payload.sh "$STAGE/usr"
bash packaging/install_os_payload.sh "$STAGE/usr"
# Pure-Python modules of Safeer Link from the build host's dist-packages: qrcode (QR code for signing in) and
# zeroconf + ifaddr (finding devices over mDNS; without them there is no QR code and no 6-digit code at all).
mkdir -p "$STAGE/usr/lib/python3/dist-packages"
for modul in qrcode zeroconf ifaddr; do
    if [ -d "/usr/lib/python3/dist-packages/$modul" ]; then
        cp -a "/usr/lib/python3/dist-packages/$modul" "$STAGE/usr/lib/python3/dist-packages/"
    elif [ -n "${CI:-}" ]; then
        echo "manjka /usr/lib/python3/dist-packages/$modul (apt install python3-$modul)" >&2; exit 1
    fi
done
cp -a "$STAGE/usr" "$APPDIR/"
# Safeer DRM iz tovora (SAFEER_DRM_TOVOR, packaging/namesti_safeer_drm.sh) izven usr/, kot PySide6: linuxdeploy razresuje
# knjiznice pod usr/ (tudi libwidevinecdm.so, libffmpeg.so) in jih ne sme spreminjati. AppRun poda pot v SAFEER_DRM_MAPA.
if [ -d "$APPDIR/usr/lib/safeer-os/safeer-drm" ]; then
    mkdir -p "$APPDIR/opt"
    mv "$APPDIR/usr/lib/safeer-os/safeer-drm" "$APPDIR/opt/safeer-drm"
fi
python3 packaging/prepare_appdir.py "$APPDIR" "$APPID" safeer-os
install -m755 packaging/AppRun-os "$APPDIR/AppRun"
export LDAI_RUNTIME_FILE="${LDAI_RUNTIME_FILE:-$ROOT/build/tools/runtime-x86_64}"
[ -f "$LDAI_RUNTIME_FILE" ] || { echo "Run packaging/fetch_linuxdeploy.sh first" >&2; exit 1; }
export VERSION="$(cat packaging/VERSION_OS)"
export OUTPUT="$ROOT/dist/Safeer-OS-${VERSION}-x86_64.AppImage"
# Lupina QML: PySide6 kot v paketu .deb (packaging/pyside6_vendor.py), a izven usr/: Qt pride z lastnimi knjiznicami
# (RPATH $ORIGIN) in linuxdeploy jih ne sme razresevati - moduli PySide6, ki jih lupina ne rabi (npr. Qt 3D), bi gradnjo
# ustavili zaradi manjkajocih knjiznic (14. 10. 2026). AppRun-os poda pot v SAFEER_PYSIDE6.
python3 packaging/pyside6_vendor.py "$APPDIR/opt/pyside6"
"$LINUXDEPLOY" --appdir "$APPDIR" --executable "$APPDIR/usr/bin/python3" \
    --desktop-file "$APPDIR/usr/share/applications/$APPID.desktop" \
    --icon-file "$APPDIR/usr/share/icons/hicolor/256x256/apps/safeer-os.png" \
    --custom-apprun "$ROOT/packaging/AppRun-os" --output appimage
