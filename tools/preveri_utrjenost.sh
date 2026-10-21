#!/usr/bin/env bash
# Preverba utrjenosti nasega WebKita in libsoup (AGENTS.md, »Utrjena gradnja«; lastnik 21. 10. 2026). En skript za
# posle webkit-deb, flatpak in flatpak-brskalnik (naloga 40), da pravila niso v treh kopijah.
#
#   tools/preveri_utrjenost.sh KOREN [PODMAPA ...]
#
# KOREN je predpona nasega WebKita: v paketu .deb <razpakirano>/usr/lib/safeer-webkit, v Flatpaku mapa files/ namescene
# aplikacije (/app). Pet glavnih datotek (libwebkitgtk, libjavascriptcoregtk, libsoup, WebKitWebProcess,
# WebKitNetworkProcess): BIND_NOW, GNU_RELRO, GNU_STACK RW, PIE/DYN, CET (IBT in SHSTK), zascita sklada in _FORTIFY
# (razen libexec). Ostale datoteke ELF pod KOREN (ali samo pod PODMAPA, npr. v Flatpaku lib/webkitgtk-6.0, kjer so v /app
# tudi programi drugih projektov): BIND_NOW (razen vgrajenih knjiznic Ubuntuja), GNU_RELRO, GNU_STACK RW.
# Izhod 1 ob prvi napaki (::error::), 2 ob napacni uporabi.
#
# Izhod orodij se najprej shrani v spremenljivko: `nm -D velika.so | grep -q` pod pipefail (privzeto v GitHub Actions)
# lahko pade s SIGPIPE, ko grep konca prej kot nm - lazna napaka.
set -euo pipefail

KOREN="${1:?Uporaba: tools/preveri_utrjenost.sh KOREN [PODMAPA ...]}"
shift
[ -d "$KOREN" ] || { echo "::error::preveri_utrjenost: ni mape $KOREN" >&2; exit 2; }
for orodje in readelf nm file; do
    command -v "$orodje" >/dev/null || { echo "::error::preveri_utrjenost: manjka $orodje (binutils, file)" >&2; exit 2; }
done

napaka() { echo "::error::$1"; exit 1; }

skupno() {   # BIND_NOW (ce $2 = da), GNU_RELRO, GNU_STACK RW (brez E)
    local f="$1" bind="$2" glave dinamicni sklad
    glave="$(readelf -lW "$f")"
    dinamicni="$(readelf -dW "$f")"
    if [ "$bind" = da ]; then
        grep -qE 'BIND_NOW|FLAGS_1.*NOW' <<< "$dinamicni" || napaka "$f brez BIND_NOW"
    fi
    grep -q GNU_RELRO <<< "$glave" || napaka "$f brez GNU_RELRO"
    sklad="$(grep GNU_STACK <<< "$glave" || true)"
    grep -q ' RW ' <<< "$sklad" || napaka "$f nima GNU_STACK RW"
}

GLAVNE=(lib/libwebkitgtk-6.0.so.4 lib/libjavascriptcoregtk-6.0.so.1 lib/libsoup-3.0.so.0
        libexec/webkitgtk-6.0/WebKitWebProcess libexec/webkitgtk-6.0/WebKitNetworkProcess)
for rel in "${GLAVNE[@]}"; do
    [ -e "$KOREN/$rel" ] || napaka "$KOREN/$rel manjka"
    f="$(readlink -f "$KOREN/$rel")"
    skupno "$f" da
    glava="$(readelf -hW "$f")"
    grep -q 'Type:.*DYN' <<< "$glava" || napaka "$f ni PIE/DYN"
    # CET je od naloge 40 napaka: CI 39589540802 (gradnja z BOLT) je izmeril IBT in SHSTK v vseh petih datotekah.
    opombe="$(readelf -nW "$f")"
    grep -qE 'x86 feature:.*IBT' <<< "$opombe" && grep -qE 'x86 feature:.*SHSTK' <<< "$opombe" \
        || napaka "$f brez CET (IBT, SHSTK)"
    simboli="$(nm -D "$f")"
    chk="$(grep -cE ' U __[a-z0-9_]+_chk(@|$)' <<< "$simboli" || true)"
    # Pomozna procesa (libexec) sta le majhen main(), ki klice knjiznico: brez lokalnih polj -fstack-protector-strong
    # nima kaj zascititi (CI 39589540802: WebKitWebProcess brez __stack_chk_fail, knjiznice _chk=11/6/4).
    case "$rel" in
        libexec/*) ;;
        *)  grep -q ' U __stack_chk_fail' <<< "$simboli" || napaka "$f brez zascite sklada"
            [ "$chk" -ge 1 ] || napaka "$f brez _FORTIFY_SOURCE" ;;
    esac
    echo "utrjeno: $f _chk=$chk CET=IBT,SHSTK"
done

# Ostale datoteke ELF (vgrajene knjiznice, dav1ddec, vticnik spletnega procesa ...): pregled 1.0.132 - preverba samo 5
# datotek je spregledala libgstdav1d.so brez BIND_NOW.
mape=()
if [ "$#" -eq 0 ]; then
    mape=("$KOREN")
else
    for p in "$@"; do mape+=("$KOREN/$p"); done
fi
stevilo=0
for mapa in "${mape[@]}"; do
    [ -d "$mapa" ] || napaka "$mapa manjka"
    while IFS= read -r -d '' f; do
        vrsta="$(file -b "$f")"
        case "$vrsta" in ELF*) ;; *) continue ;; esac
        # Vgrajene knjiznice Ubuntuja (packaging/webkit-deb/vgradi.sh) so nespremenjeni binarni paketi distribucije -
        # Ubuntujev libjxl0.7 nima BIND_NOW (izmerjeno 21. 10.); zanje veljata RELRO in GNU_STACK.
        case "$(basename "$f")" in
            libicu*|libjxl*|libhwy*|libjpeg*|libxml2*|libxslt*|libexslt*) skupno "$f" ne ;;
            *) skupno "$f" da ;;
        esac
        stevilo=$((stevilo + 1))
    done < <(find "${mapa}" -type f -print0)
done
echo "utrjeno: ${#GLAVNE[@]} glavnih in $stevilo datotek ELF pod ${mape[*]}"
