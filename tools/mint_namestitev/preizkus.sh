#!/bin/bash
# Paketi .deb na pravem Linux Mintu: namestitev, zagon in odstranitev - tako, kot to naredi uporabnik.
#
# Posel »deb-appimage« pakete zgradi in namesti na Ubuntu 22.04. Tam se paketa videza (safeer-os-tema,
# safeer-cinnamon) sploh ne dasta namestiti (mint-themes obstaja samo v Linux Mintu), odvisnosti pa razresi drugo
# skladisce kot pri uporabniku. Ta preizkus namesti VSE pakete v sliki Linux Minta (skladisca Minta + Ubuntuja).
#
#   preizkus.sh SLIKA MAPA_S_PAKETI [MAPA_S_PREJSNJO_IZDAJO]      npr. preizkus.sh linuxmintd/mint22.3-amd64 .
#
# S tretjim parametrom (paketi .deb zadnje objavljene izdaje) preizkusi tudi posodobitev: najprej namesti prejsnjo
# izdajo, nato cez njo nove pakete - z istim ukazom, kot jih namesti Safeer OS sam. To je pot vsakega uporabnika.
#
# Vsebnik je privilegiran, da se lahko zazene peskovnik WebKita (kot pri uporabniku).
set -euo pipefail
SLIKA="${1:?slika Linux Minta, npr. linuxmintd/mint22.3-amd64}"
PAKETI="$(cd "${2:-.}" && pwd)"
TU="$(cd "$(dirname "$0")" && pwd)"
PREJSNJI=()
if [ -n "${3:-}" ] && ls "$3"/*.deb >/dev/null 2>&1; then PREJSNJI=(-v "$(cd "$3" && pwd):/prejsnji:ro"); fi
docker run --rm --privileged -v "$PAKETI:/paketi:ro" "${PREJSNJI[@]}" -v "$TU/v_vsebniku.sh:/v_vsebniku.sh:ro" \
  -v "$TU/dvojni_klik.py:/dvojni_klik.py:ro" "$SLIKA" bash /v_vsebniku.sh
