#!/usr/bin/env bash
# Safeer OS (Linux) payload: the Safeer OS shell for the desktop (safeer_os.py, its core modules and
# the page in assets/os). Since 12. 10. 2026 it also carries Safeer Control and runs it in its own process
# (core/en_proces.py, one process instead of two); a separately running Control is still used over D-Bus, so every
# package built from this payload also carries the Safeer Control payload (deb: build_os_deb.sh, one package with
# Control and Safeer Cinnamon; AppImage and Flatpak: both payloads in one bundle).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${1:?Usage: install_os_payload.sh DESTINATION_PREFIX [desktop-id]}"
ID="${2:-safeer-os}"
LIB="$PREFIX/lib/safeer-os"
mkdir -p "$PREFIX/bin" "$LIB/core" "$LIB/assets" "$LIB/packaging" "$PREFIX/share/applications" "$PREFIX/share/metainfo" "$PREFIX/share/pixmaps"
cp -a "$ROOT/safeer_os.py" "$LIB/"
# Everything safeer_os.py imports, directly or lazily (core/os_* plus the Safeer Link modules it reads:
# identity, sessions, circle of trust, hub discovery, programs). tests/test_packaging.py installs this
# payload and imports it without the source tree, so a missing module fails the test, not the user.
# core/os_jbl.py (JBL input switching) is an internal experiment and is deliberately NOT shipped.
# Lazy imports count too: core/os_splet.py is imported only when the user opens Splet, and it needs
# filter_lists -> webkit_filters. tests/test_tovor_uvozi.py walks every import in the payload.
for modul in budnost en_proces obvestila priljubljeno pladenj_sni uvoz_zavihkov zgodovina iskalni_kljuc os_datoteke os_dock pomnilnik zasebni_webkit os_iskalnik os_odpri_z os_knjiznica os_police samodejni_seznami os_media_besedila os_medijska_plast os_mediji os_mpris os_oblak_igre os_ponudniki_programov os_github_programi os_posodobitve os_predvajalnik os_pretvorba_datotek os_torrent os_torrent_tok podnapisi os_dvd os_okna x11 os_lupina os_omrezje os_govor os_lupa os_programi os_scit os_sistem os_sporocila os_predogled predogled_datotek gostitelj os_spletne os_stabilnost os_deskriptorji os_tema_namizja os_zapiski os_zvok \
             link_datoteke link_delta link_nadaljuj link_teamwork link_urejanje link_hub link_hub_streznik link_obramba link_varovalka link_hub_deljenje link_mesh link_rele link_neposredno link_pretok link_sprotno link_predvajanje link_iskanje link_krog link_dostop link_e2e link_kripto link_mediji link_programi link_seja link_tls link_ws link_vticnik link_pot spake2 signed_feed threat_intel \
             os_katalog os_media os_vgrajeni_viri meritve_virov knjiznica_kroga media_servers jellyfin_vticniki tok_izbira watch_providers zakoniti_viri izvirni_jezik uvoz_seznama youtube_racun twitch twitch_hls seznami_sink viri_sink predvajalnik_moznosti podnapisi_splet spotify_racun \
             os_splet splet_temno splet_varuh jeziki_strani ikone_strani dlna_zvocniki zvok_na_zvocnik adblock config bookmarks_importer doh_proxy filter_lists webkit_filters bank_guard odlozisce_varuh ozadje_strani drm safeer_drm splet_prenosi external_apps i18n pojavna_okna network_errors zascita dovoljenja_strani \
             spletni_klepeti os_kanali_sporocil vstavi_okno namizni_programi znacke_programov \
             poraba_kanalov os_poraba_kanalov; do
    cp -a "$ROOT/core/$modul.py" "$LIB/core/"
done
mkdir -p "$LIB/core/sporocila" && install -m 644 "$ROOT"/core/sporocila/*.py "$LIB/core/sporocila/"
# Dark Reader (MIT) za »vsili temno« v Spletu (core/splet_temno.py preveri SHA-256 pred uporabo).
mkdir -p "$LIB/core/darkreader" && install -m 644 "$ROOT"/core/darkreader/darkreader.js "$ROOT"/core/darkreader/LICENSE "$LIB/core/darkreader/"
[ -f "$ROOT/core/__init__.py" ] && cp -a "$ROOT/core/__init__.py" "$LIB/core/" || true
cp -a "$ROOT/assets/os" "$LIB/assets/"
# Safeer DRM (Widevine): logika predvajalnika (main.js); paket ECS se prenese ob prvi potrebi (core/safeer_drm.py).
cp -a "$ROOT/assets/safeer_drm" "$LIB/assets/"
# Splet v Safeer OS: skupna zacetna stran in podatki BankGuarda (iste datoteke kot na Windows/Androidu).
mkdir -p "$LIB/ui" && cp -a "$ROOT"/ui/splet.html "$ROOT"/ui/splet.css "$ROOT"/ui/splet.js "$ROOT"/ui/splet-gore.webp "$LIB/ui/"
for dat in banks.json bank_guard_page.js; do [ -f "$ROOT/core/$dat" ] && cp -a "$ROOT/core/$dat" "$LIB/core/"; done
cp -a "$ROOT/packaging/VERSION_OS" "$LIB/packaging/"
# En proces (core/en_proces.py): Safeer OS zazene Safeer Control v svojem procesu, zato ima ves tovor Controla
# (safeer_control.py, moduli Linka, stran assets/link). Iz istega izvora - nicesar ne prepisemo (cp -n).
TOVOR_CONTROL="$(mktemp -d)"
bash "$ROOT/packaging/install_control_payload.sh" "$TOVOR_CONTROL/usr" >/dev/null
( cd "$TOVOR_CONTROL/usr/lib/safeer-control" && find . -type f ) | while IFS= read -r dat; do
    [ -e "$LIB/$dat" ] || install -D -m 644 "$TOVOR_CONTROL/usr/lib/safeer-control/$dat" "$LIB/$dat"
done
rm -rf "$TOVOR_CONTROL"
find "$LIB" -type d -name __pycache__ -exec rm -rf {} +
find "$LIB" -name '*.pyc' -delete
# Pri sistemski namestitvi je vsebina v lasti root; uporabniški proces jo mora
# kljub morebitnim zasebnim pravicam izvorne kopije lahko prebrati.
find "$LIB" -type d -exec chmod 755 {} +
find "$LIB" -type f -exec chmod 644 {} +
install -m755 "$ROOT/packaging/safeer-os-launcher" "$PREFIX/bin/safeer-os"
install -Dm644 "$ROOT/LICENSE" "$PREFIX/share/doc/safeer-os/LICENSE"
sed "s/^Icon=.*/Icon=$ID/" "$ROOT/packaging/safeer-os.desktop" > "$PREFIX/share/applications/$ID.desktop"
# Magnet povezave (x-scheme-handler/magnet) odpre Safeer Media; vnos se v meniju ne kaze.
sed "s/^Icon=.*/Icon=$ID/" "$ROOT/packaging/safeer-os-magnet.desktop" > "$PREFIX/share/applications/$ID.Magnet.desktop"
# Gumb »Install« dodatkov Stremio (x-scheme-handler/stremio) odpre okno Dodatki v Safeer Media; vnos se v meniju ne kaze.
sed "s/^Icon=.*/Icon=$ID/" "$ROOT/packaging/safeer-os-stremio.desktop" > "$PREFIX/share/applications/$ID.Stremio.desktop"
# Safeer Player (Medijski center v svojem oknu, `safeer-os --predvajalnik`) je v meniju svoj program s svojo ikono.
# Ime z ID-jem spredaj: Flatpak izvozi samo vnose in ikone, ki se zacnejo z ID-jem programa.
sed "s/^Icon=.*/Icon=$ID.Player/" "$ROOT/packaging/safeer-player.desktop" > "$PREFIX/share/applications/$ID.Player.desktop"
install -Dm644 "$ROOT/assets/os/predvajalnik.svg" "$PREFIX/share/icons/hicolor/scalable/apps/$ID.Player.svg"
# Vsako okno Safeer OS ima v pultu in docku svoj vnos in ikono (safeer_os.OKNA_V_PULTU; lastnik, 16. 10. 2026: Splet in
# Sporocila sta imela na docku isto ikono). Vnosi se v meniju ne kazejo (NoDisplay), razred okna je safeer-os.<okno>.
for okno in splet sporocila zapiski nastavitve; do
    sed "s/^Icon=.*/Icon=$ID.$okno/" "$ROOT/packaging/safeer-os-$okno.desktop" > "$PREFIX/share/applications/$ID.$okno.desktop"
    install -Dm644 "$ROOT/assets/os/$okno.svg" "$PREFIX/share/icons/hicolor/scalable/apps/$ID.$okno.svg"
done
# Safeer Control v istem procesu (okno razreda safeer-control): .deb ima vnos safeer-control.desktop iz tovora Controla,
# Flatpak (in AppImage) pa ga odstrani - brez vnosa z ID-jem bi pult okno Controla pripisal Safeer OS (ikona Safeer OS).
if [ "$ID" != "safeer-os" ]; then
    sed -e "s/^Icon=.*/Icon=$ID.Control/" -e "s/^StartupNotify=.*/NoDisplay=true/" \
        "$ROOT/packaging/safeer-control.desktop" > "$PREFIX/share/applications/$ID.Control.desktop"
    install -Dm644 "$ROOT/assets/link/control.svg" "$PREFIX/share/icons/hicolor/scalable/apps/$ID.Control.svg"
fi
sed "s|safeer-os.desktop|$ID.desktop|" "$ROOT/io.github.memelandfaner.SafeerOS.metainfo.xml" > "$PREFIX/share/metainfo/io.github.memelandfaner.SafeerOS.metainfo.xml"
install -Dm644 "$ROOT/assets/os/znak.svg" "$PREFIX/share/icons/hicolor/scalable/apps/$ID.svg"
install -m644 "$ROOT/assets/icon.png" "$PREFIX/share/pixmaps/$ID.png"
for icon in "$ROOT/packaging/icons/hicolor"/*/apps/safeer-browser.png; do
    size=$(basename "$(dirname "$(dirname "$icon")")")
    install -Dm644 "$icon" "$PREFIX/share/icons/hicolor/$size/apps/$ID.png"
done
