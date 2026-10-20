#!/usr/bin/env bash
# Nas WebKitGTK (paket safeer-webkit iz istega teka CI) VGRAJEN v paket programa: safeer-os (namizno okolje),
# safeer-os-app (aplikacija) in safeer-browser (lastnik, 20. 10. 2026: »WebKit mora biti vgrajen«, vsak prenos je ena
# datoteka - dvoklik in namesceno).
#
#   vgradi_v_program.sh KOREN_PAKETA PROGRAM SAFEER_WEBKIT_DEB     npr. vgradi_v_program.sh build/deb-os safeer-os build/safeer-webkit_1.0.129_amd64.deb
#
# Drevo /usr/lib/safeer-webkit iz paketa safeer-webkit gre v KOREN/usr/lib/PROGRAM/webkit-vgrajen (vir; ime NI »webkit«,
# ker core/zasebni_webkit.predpona najprej isce KOREN/webkit). Namesti ga postinst (packaging/webkit-deb/postinst-webkit.sh)
# v skupno /usr/lib/safeer-webkit - predpono, prevedeno v knjiznice -, samo ce ista gradnja (odtis) se ni namescena; tako
# Safeer Browser ob namizju Safeer OS WebKita ne namesti ponovno in na disku ni druge kopije (trde povezave).
# Na stdout izpise odvisnosti WebKita (polje Depends paketa safeer-webkit: knjiznice, peskovnik, TLS) za polje Depends
# programa. Sporocila gredo na stderr.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
KOREN="${1:?KOREN_PAKETA}"
PROGRAM="${2:?PROGRAM (safeer-os, safeer-os-app, safeer-browser)}"
DEB="${3:?SAFEER_WEBKIT_DEB}"
case "$PROGRAM" in
    safeer-os|safeer-os-app|safeer-browser) ;;
    *) echo "vgradi_v_program.sh: neznan program $PROGRAM" >&2; exit 2 ;;
esac
# Isti paket, ista razlicica izdaje in amd64 kot doslej za odvisnost (razlicica_odvisnosti.sh preveri vse tri).
bash "$DIR/packaging/webkit-deb/razlicica_odvisnosti.sh" "$DEB" >/dev/null
RAZLICICA="$(dpkg-deb -f "$DEB" Version)"
ODVISNOSTI="$(dpkg-deb -f "$DEB" Depends)"
[ -n "$ODVISNOSTI" ] || { echo "vgradi_v_program.sh: $DEB nima polja Depends" >&2; exit 1; }
DELO="$(mktemp -d)"
trap 'rm -rf "$DELO"' EXIT
dpkg-deb -x "$DEB" "$DELO"
VIR="$KOREN/usr/lib/$PROGRAM/webkit-vgrajen"
[ -f "$DELO/usr/lib/safeer-webkit/share/webkitgtk-safeer/odtis" ] \
    || { echo "vgradi_v_program.sh: $DEB nima odtisa gradnje (packaging/webkit-deb/paket.sh)" >&2; exit 1; }
rm -rf "$VIR"
mkdir -p "$(dirname "$VIR")"
mv "$DELO/usr/lib/safeer-webkit" "$VIR"
# Razlicica za primerjavo v postinst (starejse ne namesti cez novejso).
echo "$RAZLICICA" > "$VIR/share/webkitgtk-safeer/razlicica"
chmod 644 "$VIR/share/webkitgtk-safeer/razlicica"
install -D -m 644 "$DELO/usr/share/doc/safeer-webkit/copyright" "$KOREN/usr/share/doc/$PROGRAM/safeer-webkit.copyright"
echo "vgradi_v_program.sh: safeer-webkit $RAZLICICA ($(du -sh "$VIR" | cut -f1), odtis $(cat "$VIR/share/webkitgtk-safeer/odtis")) v /usr/lib/$PROGRAM/webkit-vgrajen" >&2
echo "$ODVISNOSTI"
