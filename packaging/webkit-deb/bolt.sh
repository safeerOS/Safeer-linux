#!/usr/bin/env bash
# ==============================================================================
# BOLT (post-link optimizacija, LLVM 22) za nas WebKitGTK v paketih .deb - v gradnji izdaje vklopljen (lastnik,
# 18. 10. 2026; CI: posel webkit-deb, SAFEER_WEBKIT_BOLT=1). Ce katerikoli korak pade, pade gradnja (nikoli tiho brez BOLT).
#
#   bolt.sh PREDPONA DELO      klice ga zgradi.sh s SAFEER_WEBKIT_BOLT=1, po namestitvi in pred strip (BOLT potrebuje
#                              simbole in staticne relokacije: knjiznici sta povezani z -Wl,--emit-relocs)
#
# BOLT po PGO in ThinLTO na novo razporedi kodo knjiznic po profilu izvajanja (vroce funkcije in bloki skupaj, hladni
# deli loceno): manj zgresitev predpomnilnika ukazov in iTLB. Meritev na testnem PC (Speedometer, JetStream, MotionMark,
# hladni zagon, RAM) s paketi z BOLT sledi gradnji.
#
#   1. bolt-22 namesti odvisnosti.sh iz apt.llvm.org, pripet na LLVM_PAKET (ista gradnja kot clang-22, lld-22); tu
#      preverba razlicice (dpkg in llvm-bolt --version).
#   2. llvm-bolt -instrument za libwebkitgtk-6.0 in libjavascriptcoregtk-6.0 (izvirnika ostaneta v DELO/izvirnik).
#   3. isti ucni tek kot PGO (ucni_tek.sh bolt: Speedometer 3.1, pgo_trening.py prek bolt_trening.py): vsak proces
#      (glavni, spletni, omrezni) ob normalnem izhodu zapise svoj profil (--instrumentation-file-append-pid).
#   4. merge-fdata in llvm-bolt z moznostmi za deljene knjiznice (preverjeno z LLVM 22.1.8 18. 10. 2026 na preizkusni
#      knjiznici: instrumentacija prek DT_INIT/DT_FINI, dve instrumentirani knjiznici v enem procesu, strip po BOLT).
#   5. preverba: isti tek z optimiziranima knjiznicama mora dati veljaven rezultat Speedometra.
# Povzetek (DELO/povzetek.txt) zgradi.sh doda v gradnja.txt (vrstica »bolt: ...«).
# ==============================================================================
set -euo pipefail
KOREN="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PREDPONA="${1:?Uporaba: bolt.sh PREDPONA DELO}"
DELO="${2:?Uporaba: bolt.sh PREDPONA DELO}"
LLVM=/usr/lib/llvm-22/bin
# Ucni tek (preizkus lahko poda svojega z istimi argumenti: PREDPONA MAPA bolt|preveri).
TEK="${SAFEER_BOLT_TEK:-$KOREN/packaging/webkit-deb/ucni_tek.sh}"
# Ime profila : knjiznica (simbolna povezava v PREDPONA/lib, ki jo nalozi WebKit).
KNJIZNICE=("webkit:libwebkitgtk-6.0.so.4" "jsc:libjavascriptcoregtk-6.0.so.1")
# Moznosti za deljene knjiznice (llvm-bolt --help-hidden, LLVM 22.1.8). --icf=safe: ne zdruzi funkcij, katerih naslov
# se primerja (WebKit). --use-old-text: nova koda v prostor stare, ce gre (manjsa knjiznica), sicer opozorilo.
MOZNOSTI=(--reorder-blocks=ext-tsp --reorder-functions=cdsort --split-functions --split-all-cold --split-eh
          --icf=safe --use-gnu-stack --use-old-text --dyno-stats)

LLVM_PAKET="$(sed -n 's/^LLVM_PAKET="\(.*\)"$/\1/p' "$KOREN/packaging/webkit-deb/odvisnosti.sh")"
LLVM_RAZLICICA="$(sed -n 's/^LLVM_RAZLICICA="\(.*\)"$/\1/p' "$KOREN/packaging/webkit-deb/odvisnosti.sh")"
[ -n "$LLVM_PAKET" ] && [ -n "$LLVM_RAZLICICA" ] || { echo "bolt.sh: LLVM_PAKET ni v odvisnosti.sh" >&2; exit 1; }

# --- 1. orodja (odvisnosti.sh namesti bolt-22 iz apt.llvm.org v LLVM_PAKET, isto gradnjo kot clang-22) --------------
for orodje in llvm-bolt merge-fdata llvm-readelf; do
    [ -x "$LLVM/$orodje" ] || { echo "NAPAKA: ni $LLVM/$orodje - najprej packaging/webkit-deb/odvisnosti.sh (bolt-22 $LLVM_PAKET)" >&2; exit 1; }
done
if command -v dpkg-query >/dev/null 2>&1 && dpkg-query -W bolt-22 >/dev/null 2>&1; then
    [ "$(dpkg-query -W -f '${Version}' bolt-22)" = "$LLVM_PAKET" ] \
        || { echo "NAPAKA: bolt-22 ni $LLVM_PAKET ($(dpkg-query -W -f '${Version}' bolt-22))" >&2; exit 1; }
fi
"$LLVM/llvm-bolt" --version | grep -E "LLVM version ${LLVM_RAZLICICA//./\\.}( |$)" >/dev/null \
    || { echo "NAPAKA: llvm-bolt ni LLVM $LLVM_RAZLICICA" >&2; exit 1; }

rm -rf "$DELO"
mkdir -p "$DELO/izvirnik" "$DELO/fdata"

# --- 2. instrumentacija -----------------------------------------------------------------------------------------------
for par in "${KNJIZNICE[@]}"; do
    ime="${par%%:*}"
    pot="$(readlink -f "$PREDPONA/lib/${par#*:}")"
    [ -f "$pot" ] || { echo "bolt.sh: ni $PREDPONA/lib/${par#*:}" >&2; exit 1; }
    # Brez staticnih relokacij BOLT ne more premikati funkcij (samo -Wl,--emit-relocs, zgradi.sh s SAFEER_WEBKIT_BOLT=1).
    # grep brez -q prebere ves izhod: -q bi zaprl cev, readelf bi dobil SIGPIPE in pipefail bi javil napacno napako.
    "$LLVM/llvm-readelf" -S "$pot" | grep '\.rela\.text' >/dev/null \
        || { echo "bolt.sh: $pot nima .rela.text - povezava brez -Wl,--emit-relocs" >&2; exit 1; }
    cp -p "$pot" "$DELO/izvirnik/$(basename "$pot")"
    "$LLVM/llvm-bolt" "$DELO/izvirnik/$(basename "$pot")" -o "$pot" -instrument \
        --instrumentation-file="$DELO/fdata/$ime" --instrumentation-file-append-pid
done

# --- 3. ucni tek ------------------------------------------------------------------------------------------------------
bash "$TEK" "$PREDPONA" "$DELO/fdata" bolt
ls -l "$DELO/fdata"
# Glavni, omrezni in spletni proces nalozijo obe knjiznici: manj kot 3 profili pomeni, da spletni proces ni koncal
# normalno (npr. SIGKILL) in profila najpomembnejsega procesa ni.
for par in "${KNJIZNICE[@]}"; do
    ime="${par%%:*}"
    n="$(find "$DELO/fdata" -name "$ime.*.fdata" -size +0 | wc -l)"
    [ "$n" -ge "${SAFEER_BOLT_NAJMANJ_PROFILOV:-3}" ] || { echo "bolt.sh: $ime ima samo $n profilov" >&2; exit 1; }
done

# --- 4. optimizacija --------------------------------------------------------------------------------------------------
POVZETEK="bolt: da (llvm-bolt $LLVM_RAZLICICA, bolt-22 $LLVM_PAKET, ucni tek Speedometer 3.1)"
for par in "${KNJIZNICE[@]}"; do
    ime="${par%%:*}"
    pot="$(readlink -f "$PREDPONA/lib/${par#*:}")"
    izvirnik="$DELO/izvirnik/$(basename "$pot")"
    "$LLVM/merge-fdata" "$DELO/fdata/$ime".*.fdata > "$DELO/$ime.fdata"
    "$LLVM/llvm-bolt" "$izvirnik" -o "$pot" --data="$DELO/$ime.fdata" "${MOZNOSTI[@]}" 2>&1 | tee "$DELO/$ime.log"
    grep -E 'BOLT-INFO: [0-9]+ out of [0-9]+ functions in the binary' "$DELO/$ime.log" || true
    POVZETEK="$POVZETEK; $(basename "$pot") $(stat -c %s "$izvirnik") -> $(stat -c %s "$pot") B,"
    POVZETEK="$POVZETEK $(find "$DELO/fdata" -name "$ime.*.fdata" | wc -l) profilov"
done

# --- 5. preverba z optimiziranima knjiznicama ---------------------------------------------------------------------------
bash "$TEK" "$PREDPONA" "$DELO/preveri" preveri
echo "$POVZETEK" | tee "$DELO/povzetek.txt"
