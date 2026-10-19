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
for modul in budnost en_proces storitve_na_zahtevo poraba_zgodovina obvestila peskovnik_userns node_izvajalnik nova_razlicica pomnilnik zasebni_webkit okolje_procesa root_ukaz https_prenos video_dekoderji runtime_safety link_daljinec link_datoteke link_delta link_nadaljuj link_teamwork os_okna os_datoteke link_shramba link_pretvorba link_deljenje x11 seja_prikaza portal_zaslon zajem_pipewire link_gledalec link_urejanje link_fokus link_hub link_spremembe link_hub_streznik link_obramba link_viri link_varovalka link_hub_deljenje link_posiljanje link_prejem link_nemo link_zmoznosti link_mesh link_rele link_neposredno gneca link_pretok link_sprotno link_predvajanje link_seznami viri_sink knjiznica_kroga os_torrent_tok os_posodobitve signed_feed link_iskanje link_krog link_dostop link_e2e link_mediji link_plosek link_programi gostitelj link_ws link_vticnik link_pot sistemski_posrednik link_internet_posrednik link_internet \
             link_kripto link_seja link_sway link_tls link_vnos link_zaslon link_zaslon_meritve link_zvok os_dvd iskalni_kljuc os_knjiznica os_police os_sporocila predogled_datotek splet_prenosi os_pretvorba_datotek os_stabilnost os_deskriptorji os_torrent podnapisi safeer_link spake2 odlozisce_varuh pladenj_sni x11 \
             spletni_klepeti poraba_kanalov; do
    cp -a "$ROOT/core/$modul.py" "$LIB/core/"
done
[ -f "$ROOT/core/__init__.py" ] && cp -a "$ROOT/core/__init__.py" "$LIB/core/" || true
# Safeer Chat: Control vpise sporocila z drugih naprav v Sporocila Safeer OS (core/sporocila).
mkdir -p "$LIB/core/sporocila" && cp -a "$ROOT"/core/sporocila/*.py "$LIB/core/sporocila/"
# Safeer Agent (agent.ask): stavek z druge naprave -> naloge na napravah v Linku (core/agent).
mkdir -p "$LIB/core/agent" && cp -a "$ROOT"/core/agent/*.py "$LIB/core/agent/"
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
# Svoja ikona (daljinec v scitu), ne zeleni »S« Safeer OS in Safeer Browserja: v pultu in docku so okna Controla
# loceno od Safeer OS (lastnik, 16. 10. 2026). Samo SVG - PNG iste velikosti bi ga v temi ikon prehitel.
install -Dm644 "$ROOT/assets/link/control.svg" "$PREFIX/share/icons/hicolor/scalable/apps/$ID.svg"
# Iste poti PNG kot v starem paketu safeer-control (Replaces mora prevzeti VSE njegove datoteke, sicer ostane namescen),
# a iz istega control.svg - PNG ni vec zeleni »S«, zato SVG v temi ikon ne prehiti nic drugega.
for icon in "$ROOT/packaging/icons/control/hicolor"/*/apps/safeer-control.png; do
    size=$(basename "$(dirname "$(dirname "$icon")")")
    install -Dm644 "$icon" "$PREFIX/share/icons/hicolor/$size/apps/$ID.png"
done
install -m644 "$ROOT/assets/icon.png" "$PREFIX/share/pixmaps/$ID.png"
