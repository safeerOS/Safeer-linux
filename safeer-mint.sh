#!/usr/bin/env bash
# Resolve the source checkout even when launched through a desktop symlink.
set -e
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
DIR="$(dirname "$SCRIPT_PATH")"
# Let WebKit select a supported compositor. Do not change desktop-wide settings.
export PULSE_LATENCY_MSEC="${PULSE_LATENCY_MSEC:-120}"
export GST_PULSE_BUFFER_MS="${GST_PULSE_BUFFER_MS:-120}"
# Python owns the single-instance handoff and respects XDG_CONFIG_HOME.
# Privzeto GTK4 brskalnik (WebKitGTK 6.0, kot .deb, Flatpak in AppImage); SAFEER_BRSKALNIK_GTK3=1 zazene zastareli
# GTK3 brskalnik safeer_mint.py do umika.
if [ "${SAFEER_BRSKALNIK_GTK3:-0}" = 1 ]; then
    exec /usr/bin/python3 "$DIR/safeer_mint.py" "$@"
fi
exec /usr/bin/python3 "$DIR/safeer_brskalnik.py" "$@"
