#!/usr/bin/env bash
# Vstavi bloka vgrajenega WebKita (packaging/webkit-deb/postinst-webkit.sh, postrm-webkit.sh) v skripte vzdrzevalca
# paketa programa namesto vrstic »# @safeer-webkit-postinst@« in »# @safeer-webkit-postrm@«.
#
#   vstavi_skripte.sh KOREN_PAKETA PROGRAM
#
# Bloka sta v skriptah dpkg (ne v namescenem pomocnem programu): postrm tece, ko so datoteke paketa ze odstranjene.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KOREN="${1:?KOREN_PAKETA}"
PROGRAM="${2:?PROGRAM}"
case "$PROGRAM" in
    safeer-os|safeer-os-app|safeer-browser) ;;
    *) echo "vstavi_skripte.sh: neznan program $PROGRAM" >&2; exit 2 ;;
esac
for vrsta in postinst postrm; do
    S="$KOREN/DEBIAN/$vrsta"
    [ "$(grep -cx "# @safeer-webkit-$vrsta@" "$S")" = 1 ] || { echo "vstavi_skripte.sh: $S nima natanko ene oznake @safeer-webkit-$vrsta@" >&2; exit 1; }
    BLOK="$(mktemp)"
    sed "s|@PROGRAM@|$PROGRAM|g" "$DIR/$vrsta-webkit.sh" > "$BLOK"
    sed -i -e "/^# @safeer-webkit-$vrsta@\$/{r $BLOK" -e 'd}' "$S"
    rm -f "$BLOK"
    if grep -q '@PROGRAM@\|@safeer-webkit-' "$S"; then echo "vstavi_skripte.sh: v $S je ostala oznaka" >&2; exit 1; fi
    if command -v dash >/dev/null 2>&1; then dash -n "$S"; else sh -n "$S"; fi
done
