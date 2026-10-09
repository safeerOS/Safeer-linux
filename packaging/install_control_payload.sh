#!/usr/bin/env bash
# Safeer Control payload: only what the desktop app needs (Safeer Link core + the Link page).
# No browser code is shipped; Control works on a computer without Safeer Browser.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${1:?Usage: install_control_payload.sh DESTINATION_PREFIX}"
ID="safeer-control"
LIB="$PREFIX/lib/safeer-control"
mkdir -p "$PREFIX/bin" "$LIB/core" "$LIB/assets" "$LIB/packaging" "$PREFIX/share/applications" "$PREFIX/share/pixmaps"
cp -a "$ROOT/safeer_control.py" "$ROOT/safeerctl.py" "$LIB/"
# Vsi moduli core, ki jih safeer_control.py uvozi - tudi posredno. Brez link_programi in
# link_zaslon (ta uvozi link_vnos) se namesceni Control sploh ne zazene: uvoz pade takoj.
# Seznam varuje tests/test_packaging.py: namesti tovor in ga uvozi brez izvorne mape.
for modul in budnost link_daljinec link_datoteke link_shramba link_pretvorba link_deljenje link_gledalec link_urejanje link_fokus link_hub link_hub_streznik link_obramba link_varovalka link_hub_deljenje link_posiljanje link_zmoznosti link_mesh link_rele link_pretok link_sprotno link_predvajanje link_seznami viri_sink knjiznica_kroga os_torrent_tok os_posodobitve signed_feed link_iskanje link_krog link_dostop link_e2e link_mediji link_plosek link_programi link_ws link_vticnik sistemski_posrednik link_internet_posrednik link_internet \
             link_kripto link_seja link_sway link_tls link_vnos link_zaslon link_zaslon_meritve link_zvok os_dvd iskalni_kljuc os_knjiznica os_sporocila os_stabilnost os_torrent podnapisi safeer_link spake2 odlozisce_varuh; do
    cp -a "$ROOT/core/$modul.py" "$LIB/core/"
done
[ -f "$ROOT/core/__init__.py" ] && cp -a "$ROOT/core/__init__.py" "$LIB/core/" || true
# Safeer Chat: Control vpise sporocila z drugih naprav v Sporocila Safeer OS (core/sporocila).
mkdir -p "$LIB/core/sporocila" && cp -a "$ROOT"/core/sporocila/*.py "$LIB/core/sporocila/"
cp -a "$ROOT/assets/link" "$LIB/assets/"
cp -a "$ROOT/packaging/VERSION_CONTROL" "$LIB/packaging/"
find "$LIB" -type d -name __pycache__ -exec rm -rf {} +
find "$LIB" -name '*.pyc' -delete
# Izvorna delovna kopija ima lahko zasebne pravice (0600). Paket bo v lasti root,
# zato morajo biti Python, HTML, CSS in JS datoteke berljive navadnemu uporabniku.
find "$LIB" -type d -exec chmod 755 {} +
find "$LIB" -type f -exec chmod 644 {} +
install -m755 "$ROOT/packaging/safeer-control-launcher" "$PREFIX/bin/safeer-control"
# safeerctl: Safeer Link iz ukazne vrstice (govori s Controlom, ki tece v ozadju).
install -m755 "$ROOT/packaging/safeerctl-launcher" "$PREFIX/bin/safeerctl"
install -Dm644 "$ROOT/LICENSE" "$PREFIX/share/doc/safeer-control/LICENSE"
install -m644 "$ROOT/packaging/safeer-control.desktop" "$PREFIX/share/applications/$ID.desktop"
install -m644 "$ROOT/assets/icon.png" "$PREFIX/share/pixmaps/$ID.png"
for icon in "$ROOT/packaging/icons/hicolor"/*/apps/safeer-browser.png; do
    size=$(basename "$(dirname "$(dirname "$icon")")")
    install -Dm644 "$icon" "$PREFIX/share/icons/hicolor/$size/apps/$ID.png"
done
