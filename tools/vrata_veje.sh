#!/usr/bin/env bash
# Vrata veje: noben commit z druge veje ne sme ostati zunaj izdaje brez razloga.
# Za vsak commit '+' (git cherry) razvrsti: PRENESEN (vsebina ze v HEAD), MANJKA (se cisto uporabi), SPOR.
# MANJKA in SPOR ustavita izdajo, razen ce je commit v tools/vrata_opusceni.txt (vrstica: <sha8> <razlog>).
# Uporaba: tools/vrata_veje.sh [dni=30]
set -u
DNI="${1:-30}"
OPUSCENI="$(dirname "$0")/vrata_opusceni.txt"
IDX=/tmp/vrata-veje.indeks
IZPIS=/tmp/vrata-veje.izpis
git fetch -q origin || echo "OPOZORILO: fetch ni uspel"
for veja in $(git for-each-ref --format='%(refname:short)' refs/remotes/origin | grep -v -e '/HEAD$' -e '/main$'); do
  [ -n "$(git log -1 --since="$DNI days ago" --format=%h "$veja")" ] || continue
  for c in $(git cherry HEAD "$veja" | grep '^+' | cut -c3-); do
    GIT_INDEX_FILE="$IDX" git read-tree HEAD
    if [ -n "$(git log HEAD -1 --format=%h --grep="cherry picked from commit $c")" ]; then st=PRENESEN
    elif git diff-tree -p --root "$c" | GIT_INDEX_FILE="$IDX" git apply --cached --check -R 2>/dev/null; then st=PRENESEN
    elif git diff-tree -p --root "$c" | GIT_INDEX_FILE="$IDX" git apply --cached --check 2>/dev/null; then st=MANJKA
    else st=SPOR; fi
    if [ "$st" != PRENESEN ] && grep -q "^${c:0:8}" "$OPUSCENI" 2>/dev/null; then st=OPUSCEN; fi
    printf '%s %s %s %s\n' "$st" "${c:0:8}" "$veja" "$(git log -1 --format=%s "$c" | cut -c1-90)"
  done
done | sort | tee "$IZPIS"
if grep -qE '^(MANJKA|SPOR) ' "$IZPIS"; then echo "VRATA VEJE: USTAVI (MANJKA/SPOR brez razloga)"; exit 1; fi
echo "VRATA VEJE: OK"
