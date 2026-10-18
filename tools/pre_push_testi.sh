#!/usr/bin/env bash
# Pred potiskom na gtk4-deb-webkit, main ali oznako zazene polne gtk3 teste na TOCNO tistem, kar se potiska.
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
echo "pre-push: gtk3 testi na ${sha:0:7} (okoli 8 min) ..."
cd "$T" || exit 1
PYTHONPATH=tests:build/vendor env -u DISPLAY -u WAYLAND_DISPLAY python3 -m pytest -q -p no:cacheprovider \
  $(python3 tools/razdeli_teste.py gtk3 --poti) > "$T/testi.log" 2>&1
padli="$(grep -E '^FAILED' "$T/testi.log" | grep -v 'test_predvajaj_na.py::NamizjeQmlZivo::test_predvaja_in_tipke')"
tail -2 "$T/testi.log" | head -1
if [ -n "$padli" ]; then
  echo "pre-push: TESTI PADLI, potisk ustavljen:"; echo "$padli" | cut -c1-200
  cp "$T/testi.log" /tmp/pre-push-testi.log; echo "Celoten izpis: /tmp/pre-push-testi.log"
  exit 1
fi
echo "pre-push: testi v redu."
