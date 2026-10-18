#!/usr/bin/env bash
# Odvisnost programa od skupnega WebKita: izpise »safeer-webkit (>= RAZLICICA)« za polje Depends paketov safeer-os in
# safeer-browser (build_os_deb.sh, build_deb.sh).
#
#   razlicica_odvisnosti.sh POT/safeer-webkit_<razlicica>_amd64.deb
#
# Paket mora biti safeer-webkit za amd64 z razlicico te izdaje (packaging/VERSION v obliki dpkg): program, zgrajen v istem
# teku, nikoli ne zahteva starejsega ali tujega WebKita. Spodnja meja (ne natancna, glej packaging/webkit-deb/paket.sh):
# posodobitev enega programa ne odstrani drugega.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEB="${1:?Uporaba: razlicica_odvisnosti.sh POT/safeer-webkit_*_amd64.deb}"
[ -f "$DEB" ] || { echo "razlicica_odvisnosti.sh: paketa $DEB ni" >&2; exit 1; }
PAKET="$(dpkg-deb -f "$DEB" Package)"
ARCH="$(dpkg-deb -f "$DEB" Architecture)"
RAZLICICA="$(dpkg-deb -f "$DEB" Version)"
PRICAKOVANA="$(bash "$DIR/packaging/deb_razlicica.sh" "$(cat "$DIR/packaging/VERSION")")"
[ "$PAKET" = safeer-webkit ] || { echo "razlicica_odvisnosti.sh: $DEB ni paket safeer-webkit ($PAKET)" >&2; exit 1; }
[ "$ARCH" = amd64 ] || { echo "razlicica_odvisnosti.sh: $DEB ni amd64 ($ARCH)" >&2; exit 1; }
[ "$RAZLICICA" = "$PRICAKOVANA" ] \
    || { echo "razlicica_odvisnosti.sh: safeer-webkit $RAZLICICA ni iz te izdaje ($PRICAKOVANA)" >&2; exit 1; }
echo "safeer-webkit (>= $RAZLICICA)"
