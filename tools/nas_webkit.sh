#!/usr/bin/env bash
# tools/nas_webkit.sh - Nastavi okolje na nas WebKit in izpise razlicico + pot knjiznice.
# Meritve in preizkusi na napravah naj ga uporabljajo namesto rocnega LD_LIBRARY_PATH.
#
# Uporaba:
#   source tools/nas_webkit.sh       # nalozi spremenljivke v trenutno lupino
#   ./tools/nas_webkit.sh            # izpise razlicico in pot knjiznice
#   ./tools/nas_webkit.sh <ukaz>...  # izvede podani ukaz v okolju nasega WebKita

SKRIPTA_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KOREN="$(cd "$SKRIPTA_DIR/.." && pwd)"

if [[ "${BASH_SOURCE[0]}" != "${0}" ]]; then
    eval "$(python3 "$SKRIPTA_DIR/nas_webkit.py" --export)"
    python3 "$SKRIPTA_DIR/nas_webkit.py" --info
else
    exec python3 "$SKRIPTA_DIR/nas_webkit.py" "$@"
fi
