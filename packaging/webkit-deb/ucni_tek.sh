#!/usr/bin/env bash
# Ucni tek za PGO nasega WebKitGTK v paketih .deb: instrumentiran WebKit (zgradi.sh s SAFEER_WEBKIT_PGO=ucenje) pozene
# Speedometer 3.1 (ista pripeta kopija in packaging/webkit/pgo_trening.py kot ucni tek Flatpaka) pod Xvfb.
#
#   ucni_tek.sh PREDPONA MAPA_PROFRAW      npr. ucni_tek.sh /usr/lib/safeer-browser/webkit build/pgo/profraw
#
# Spletni proces tece brez peskovnika samo v tem teku (lokalna vsebina): podeduje LLVM_PROFILE_FILE in ob SIGTERM
# zapise profil; %m loci knjiznici (libwebkitgtk, libjavascriptcoregtk) v istem procesu.
set -euo pipefail
KOREN="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PREDPONA="${1:?PREDPONA}"
P="$(mkdir -p "${2:?MAPA_PROFRAW}" && cd "$2" && pwd)"
SPEEDOMETER="$KOREN/build/pgo/speedometer"
if [ ! -d "$SPEEDOMETER/.git" ]; then
    git clone -q -b release/3.1 https://github.com/WebKit/Speedometer.git "$SPEEDOMETER"
fi
git -C "$SPEEDOMETER" checkout -q 1386415be8fef2f6b6bbdbe1828872471c5d802a
python3 -m http.server 8123 --bind 127.0.0.1 --directory "$SPEEDOMETER" >/dev/null 2>&1 &
SRV=$!
trap 'kill "$SRV" 2>/dev/null || true' EXIT
sleep 2
GI_TYPELIB_PATH="$PREDPONA/lib/girepository-1.0" LLVM_PROFILE_FILE="$P/%p-%m.profraw" \
    WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1 xvfb-run -a -s "-screen 0 1920x1080x24" dbus-run-session -- \
    python3 "$KOREN/packaging/webkit/pgo_trening.py" "http://127.0.0.1:8123/?startAutomatically&iterationCount=5" 150
for _ in $(seq 60); do pgrep -f 'WebKit(Network|Web)Process' >/dev/null || break; sleep 1; done
ls -l "$P"
[ "$(find "$P" -name '*.profraw' -size +1k | wc -l)" -ge 2 ] || { echo "ucni_tek.sh: premalo profilov v $P" >&2; exit 1; }
