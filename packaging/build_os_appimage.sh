#!/usr/bin/env bash
# Safeer OS AppImage (Safeer OS + Safeer Control). Release builds run on Ubuntu 22.04 (glibc 2.35),
# like the browser AppImage; newer hosts are diagnostic only (ALLOW_NEWER_GLIBC=1).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[ "$(uname -m)" = x86_64 ] || { echo 'AppImage currently supports x86_64 only' >&2; exit 1; }
if [ "$(getconf GNU_LIBC_VERSION | cut -d' ' -f2)" != 2.35 ] && [ "${ALLOW_NEWER_GLIBC:-0}" != 1 ]; then
    echo 'Build release AppImages on Ubuntu 22.04. Set ALLOW_NEWER_GLIBC=1 for a host-specific diagnostic build.' >&2
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
# python3-qrcode (QR code in the Safeer Link window) comes from the build host's dist-packages when present.
if [ -d /usr/lib/python3/dist-packages/qrcode ]; then
    cp -a /usr/lib/python3/dist-packages/qrcode "$STAGE/usr/lib/python3/dist-packages/" 2>/dev/null \
        || { mkdir -p "$STAGE/usr/lib/python3/dist-packages"; cp -a /usr/lib/python3/dist-packages/qrcode "$STAGE/usr/lib/python3/dist-packages/"; }
fi
cp -a "$STAGE/usr" "$APPDIR/"
python3 packaging/prepare_appdir.py "$APPDIR" "$APPID" safeer-os
install -m755 packaging/AppRun-os "$APPDIR/AppRun"
export LDAI_RUNTIME_FILE="${LDAI_RUNTIME_FILE:-$ROOT/build/tools/runtime-x86_64}"
[ -f "$LDAI_RUNTIME_FILE" ] || { echo "Run packaging/fetch_linuxdeploy.sh first" >&2; exit 1; }
export VERSION="$(cat packaging/VERSION_OS)"
export OUTPUT="$ROOT/dist/Safeer-OS-${VERSION}-x86_64.AppImage"
"$LINUXDEPLOY" --appdir "$APPDIR" --executable "$APPDIR/usr/bin/python3" \
    --desktop-file "$APPDIR/usr/share/applications/$APPID.desktop" \
    --icon-file "$APPDIR/usr/share/icons/hicolor/256x256/apps/safeer-os.png" \
    --custom-apprun "$ROOT/packaging/AppRun-os" --output appimage
