#!/usr/bin/env bash
# Safeer DRM (Widevine) v tovor paketa: lastnik, 18. 10. 2026 - DRM je del paketa kot vse drugo, med delovanjem se nic
# ne prenese. SAFEER_DRM_TOVOR je mapa iz `packaging/safeer_drm_paket.py pripravi` (pripet castLabs ECS in Widevine CDM,
# preverjena s SHA-256); tu gre v <LIB>/safeer-drm, samo za branje, obvestila o licencah pa v share/doc.
# Brez SAFEER_DRM_TOVOR (gradnja iz izvorne kode, preizkusi, paket iz debian/) je paket brez Safeer DRM - CI paketov izdaje
# zato preveri, da je v .deb, AppImage in Flatpaku (.github/workflows/linux-packages.yml).
# Uporaba: namesti_safeer_drm.sh PREDPONA MAPA_TOVORA IME_ZA_DOC
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${1:?Uporaba: namesti_safeer_drm.sh PREDPONA MAPA_TOVORA IME_ZA_DOC}"
LIB="${2:?}"
DOC="${3:?}"
TOVOR="${SAFEER_DRM_TOVOR:-}"
if [ -z "$TOVOR" ]; then
    echo "Safeer DRM: SAFEER_DRM_TOVOR ni nastavljen - ta paket bo brez Safeer DRM" >&2
    exit 0
fi
[ -d "$TOVOR" ] || { echo "Safeer DRM: mapa $TOVOR ne obstaja" >&2; exit 1; }
rm -rf "$LIB/safeer-drm"
mkdir -p "$LIB"
cp -a "$TOVOR" "$LIB/safeer-drm"
rm -f "$LIB/safeer-drm/.safeer-drm-tovor"
# Pripeti odtisi programa in CDM, brez setuid in simbolnih povezav - tudi po kopiranju.
python3 "$ROOT/packaging/safeer_drm_paket.py" preveri "$LIB/safeer-drm"
D="$PREFIX/share/doc/$DOC/safeer-drm"
mkdir -p "$D"
install -m644 "$LIB/safeer-drm/OBVESTILO.txt" "$D/OBVESTILO.txt"
install -m644 "$LIB/safeer-drm/LICENSE" "$D/LICENSE.electron"
for licenca in "$LIB/safeer-drm/WidevineCdm"/*/LICENSE; do
    install -m644 "$licenca" "$D/LICENSE.widevine-cdm"
done
