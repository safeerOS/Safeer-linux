#!/usr/bin/env bash
# Lokalni tek preizkusov z ENAKIM okoljem kot CI (posel z nasim WebKitGTK, .github/workflows/linux-packages.yml):
# typelibi in vticniki GStreamer nase predpone (/usr/lib/safeer-webkit, paket safeer-webkit), xvfb-run kot zaslon,
# brez sejnega vodila D-Bus uporabnika (preizkusi imajo svoje: tests/zasebno_vodilo). Brez tega sistemski Python
# WebKitGTK 6.0 ne najde in ~300 preizkusov pade z »Namespace WebKit not available« (tedenski pregled 4. 11. 2026).
#
# Uporaba:  tools/pozeni-preizkuse.sh [moznosti pytest ...] [poti]     (privzeto: tests/)
#           SAFEER_WEBKIT_LIB=/druga/predpona/lib tools/pozeni-preizkuse.sh tests/test_x.py
# Okolje dobi samo podproces pytest (env), lupina klicatelja ostane nespremenjena.
set -euo pipefail
koren="$(cd "$(dirname "$0")/.." && pwd)"
W="${SAFEER_WEBKIT_LIB:-/usr/lib/safeer-webkit/lib}"
[ -f "$W/girepository-1.0/WebKit-6.0.typelib" ] || {
  echo "pozeni-preizkuse: v $W ni WebKit-6.0.typelib (namesti paket safeer-webkit ali nastavi SAFEER_WEBKIT_LIB)" >&2
  exit 2
}
command -v xvfb-run >/dev/null || { echo "pozeni-preizkuse: manjka xvfb-run (paket xvfb)" >&2; exit 2; }
[ "$#" -gt 0 ] || set -- tests/
cd "$koren"
# Brez LD_LIBRARY_PATH kot v CI: knjiznice nase predpone najdejo druga drugo prek RUNPATH.
exec env -u DISPLAY -u WAYLAND_DISPLAY -u DBUS_SESSION_BUS_ADDRESS \
  GI_TYPELIB_PATH="$W/girepository-1.0" GST_PLUGIN_PATH="$W/gstreamer-1.0" \
  PYTHONPATH="tests:build/vendor" QT_QUICK_BACKEND=software PYTHONDONTWRITEBYTECODE=1 \
  xvfb-run -a -s "-screen 0 1920x1080x24" python3 -m pytest -q -rs -p no:cacheprovider "$@"
