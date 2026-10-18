#!/usr/bin/env bash
# Pred potiskom na gtk4-deb-webkit, main ali oznako zazene polne gtk3 in gtk4 teste na TOCNO tistem, kar se potiska.
# Znana okoljska napaka laptopa (test_predvaja_in_tipke) ne zadrzi potiska. Preskok: SAFEER_PRESKOCI_TESTE=1 git push ...
set -u
[ "${SAFEER_PRESKOCI_TESTE:-}" = "1" ] && { echo "pre-push: testi preskoceni (SAFEER_PRESKOCI_TESTE=1)"; exit 0; }
korenin="$(git rev-parse --show-toplevel)"
potisk=0; sha=""
while read -r lokalna lsha oddaljena rsha; do
  case "$oddaljena" in refs/heads/gtk4-deb-webkit|refs/heads/main|refs/tags/*) potisk=1; sha="$lsha";; esac
done
[ "$potisk" = 1 ] || exit 0
case "$sha" in 0000000*) exit 0;; esac
T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
git -C "$korenin" archive "$sha" | tar -x -C "$T"
cd "$T" || exit 1
# Oba sklopa kot v CI: gtk3 in gtk4. WebKitGTK 6.0 za GTK 4 je tisti, ki ga prinese namesceni Safeer OS.
W=/usr/lib/safeer-os/webkit/lib
: > "$T/testi.log"
for g in gtk3 gtk4; do
  echo "pre-push: $g testi na ${sha:0:7} ..."
  GI_TYPELIB_PATH="$W/x86_64-linux-gnu/girepository-1.0:$W/girepository-1.0${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}" \
  LD_LIBRARY_PATH="$W${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" PYTHONPATH=tests:build/vendor \
    env -u DISPLAY -u WAYLAND_DISPLAY python3 -m pytest -q -p no:cacheprovider \
    $(python3 tools/razdeli_teste.py $g --poti) >> "$T/testi.log" 2>&1
  grep -E "passed|failed" "$T/testi.log" | tail -1
done
padli="$(grep -E '^FAILED' "$T/testi.log" | grep -v 'test_predvajaj_na.py::NamizjeQmlZivo::test_predvaja_in_tipke')"
if [ -n "$padli" ]; then
  echo "pre-push: TESTI PADLI, potisk ustavljen:"; echo "$padli" | cut -c1-200
  cp "$T/testi.log" /tmp/pre-push-testi.log; echo "Celoten izpis: /tmp/pre-push-testi.log"
  exit 1
fi
echo "pre-push: testi v redu."
