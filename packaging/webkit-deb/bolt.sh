#!/usr/bin/env bash
# ==============================================================================
# BOLT (post-link optimizacija, LLVM 22) za nas WebKitGTK v paketih .deb - v gradnji izdaje vklopljen (lastnik,
# 18. 10. 2026; CI: posel webkit-deb, SAFEER_WEBKIT_BOLT=1). Ce noben poskus ne uspe, pade gradnja (nikoli tiho brez BOLT).
#
#   bolt.sh PREDPONA DELO      klice ga zgradi.sh s SAFEER_WEBKIT_BOLT=1, po namestitvi in pred strip (BOLT potrebuje
#                              simbole in staticne relokacije: knjiznici sta povezani z -Wl,--emit-relocs)
#
# BOLT po PGO in ThinLTO na novo razporedi kodo knjiznic po profilu izvajanja (vroce funkcije in bloki skupaj, hladni
# deli loceno): manj zgresitev predpomnilnika ukazov in iTLB. Meritev na testnem PC (Speedometer, JetStream, MotionMark,
# hladni zagon, RAM) s paketi z BOLT sledi gradnji.
#
#   0. SAFEER_BOLT_PREDBOLT=ARHIV.tar.zst: stanje pred BOLT (namescena predpona s simboli in relokacijami, zapis CMake
#      in stevci build.ninja za gradnja.txt) se shrani v arhiv; CI ga shrani v predpomnilnik tudi, ce BOLT pade, in
#      naslednji tek nadaljuje tu (nadaljuj.sh, nekaj minut) namesto 2 h 25 min prevajanja (lastnik, 19. 10. 2026).
#   1. bolt-22 namesti odvisnosti.sh iz apt.llvm.org, pripet na LLVM_PAKET (ista gradnja kot clang-22, lld-22); tu
#      preverba razlicice (dpkg in llvm-bolt --version).
#   2. llvm-bolt -instrument (izvirnika ostaneta v DELO/izvirnik). JavaScriptCore brez rocno pisanega zbirnika
#      interpreterjev LLInt/IPInt (simboli med llintPCRangeStart in llintPCRangeEnd): JSC naslove teh oznak racuna sam
#      (g_opcodeMap) in preverja, ali je PC v tem obsegu; BOLT ga ne sme premikati (CI 39185371479, 19. 10. 2026: 34x
#      »failed to patch entries in llint_op_*«, instrumentirani proces se je 2 s po zagonu ustavil s SIGABRT).
#   3. isti ucni tek kot PGO (ucni_tek.sh bolt: Speedometer 3.1, pgo_trening.py prek bolt_trening.py): vsak proces
#      (glavni, spletni, omrezni) ob normalnem izhodu zapise svoj profil (--instrumentation-file-append-pid).
#      Ce ucni tek pade, ga ena ponovitev pod gdb izpise s skladom klicev (DELO/diagnoza.txt).
#   4. merge-fdata in llvm-bolt z moznostmi za deljene knjiznice (preverjeno z LLVM 22.1.8 18. 10. 2026 na preizkusni
#      knjiznici: instrumentacija prek DT_INIT/DT_FINI, dve instrumentirani knjiznici v enem procesu, strip po BOLT).
#   5. preverba: isti tek z optimiziranimi knjiznicami mora dati veljaven rezultat Speedometra.
# Poskusi (SAFEER_BOLT_POSKUSI, locilo »;«): najprej obe knjiznici, nato samo libwebkitgtk, nato samo JavaScriptCore -
# vsak z izvirnima knjiznicama; knjiznica brez BOLT je v povzetku oznacena (»... brez BOLT«).
# Povzetek (DELO/povzetek.txt) zgradi.sh doda v gradnja.txt (vrstica »bolt: ...«).
# ==============================================================================
set -euo pipefail
KOREN="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PREDPONA="${1:?Uporaba: bolt.sh PREDPONA DELO}"
DELO="${2:?Uporaba: bolt.sh PREDPONA DELO}"
LLVM=/usr/lib/llvm-22/bin
# Ucni tek (preizkus lahko poda svojega z istimi argumenti: PREDPONA MAPA bolt|preveri).
TEK="${SAFEER_BOLT_TEK:-$KOREN/packaging/webkit-deb/ucni_tek.sh}"
# Ime profila -> knjiznica (simbolna povezava v PREDPONA/lib, ki jo nalozi WebKit).
declare -A KNJIZNICA=([webkit]=libwebkitgtk-6.0.so.4 [jsc]=libjavascriptcoregtk-6.0.so.1)
VSE="webkit jsc"
# Moznosti za deljene knjiznice (llvm-bolt --help-hidden, LLVM 22.1.8). --icf=safe: ne zdruzi funkcij, katerih naslov
# se primerja (WebKit). --use-old-text: nova koda v prostor stare, ce gre (manjsa knjiznica), sicer opozorilo.
# NIKOLI --use-gnu-stack: BOLT je nov segment zapisal namesto PT_GNU_STACK, knjiznici 1.0.127 ga nimata in glibc je vsem
# procesom z WebKitom (namizje, brskalnik, spletni proces) naredil izvrsljiv sklad (raziskava 19. 10. 2026; glibc 2.41+ take
# knjiznice sploh ne nalozi). Brez te moznosti PT_GNU_STACK ostane (tudi po llvm-strip), koda in hitrost sta enaki.
MOZNOSTI=(--reorder-blocks=ext-tsp --reorder-functions=cdsort --split-functions --split-all-cold --split-eh
          --icf=safe --use-old-text --dyno-stats)
LLVM_PAKET="$(sed -n 's/^LLVM_PAKET="\(.*\)"$/\1/p' "$KOREN/packaging/webkit-deb/odvisnosti.sh")"
LLVM_RAZLICICA="$(sed -n 's/^LLVM_RAZLICICA="\(.*\)"$/\1/p' "$KOREN/packaging/webkit-deb/odvisnosti.sh")"
[ -n "$LLVM_PAKET" ] && [ -n "$LLVM_RAZLICICA" ] || { echo "bolt.sh: LLVM_PAKET ni v odvisnosti.sh" >&2; exit 1; }

# Regularni izrazi funkcij za --skip-funcs (BOLT jih primerja s celim imenom, lokalna imajo pripono /N): vse oznake
# v obsegu llintPCRangeStart..llintPCRangeEnd in vedno vse predpone interpreterjev JSC (IPInt preveri ob zagonu, da je
# vsak rocaj tocno na bazi + opcode * 256 B, RELEASE_ASSERT -> CRASH() = abort() brez sporocila na Linuxu, WebKit
# r238478; premaknjen ali instrumentiran rocaj = SIGABRT v JSC::initialize, kot v CI 39185371479). Brez obsega
# (libwebkitgtk) prazno. awk prebere ves izhod (brez SIGPIPE).
llint_preskoci() {
    "$LLVM/llvm-nm" --defined-only --numeric-sort "$1" | awk '
        $3 == "llintPCRangeStart" { v = 1 }
        v && NF >= 3 {
            n = $3; r = ""
            if (match(n, /^[A-Za-z][A-Za-z0-9]*_/)) r = substr(n, 1, RLENGTH) ".*"
            else if (n ~ /^[A-Za-z][A-Za-z0-9]*$/) r = n "(/[0-9]+)?"
            if (r != "" && !(r in s)) { s[r] = 1; printf "%s%s", (k++ ? "," : ""), r }
        }
        $3 == "llintPCRangeEnd" { v = 0 }
        END { if (k) printf ",llint_.*,ipint_.*,mint_.*,uint_.*,wasm_.*,vmEntry.*" }'
}

# Ena ponovitev padlega ucnega teka pod gdb: sklad klicev in ukaz, kjer se je proces ustavil (samo prvic).
diagnoza() {
    [ ! -e "$DELO/diagnoza.txt" ] || return 0
    if ! command -v gdb >/dev/null 2>&1; then echo "ni gdb" > "$DELO/diagnoza.txt"; return 0; fi
    echo "bolt.sh: ucni tek je padel - ponovitev pod gdb" >&2
    local sp="$KOREN/build/pgo/speedometer" srv=""
    if [ -d "$sp" ]; then
        python3 -m http.server 8123 --bind 127.0.0.1 --directory "$sp" >/dev/null 2>&1 &
        srv=$!
        sleep 2
    fi
    env GI_TYPELIB_PATH="$PREDPONA/lib/girepository-1.0" WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1 \
        timeout 900 xvfb-run -a -s "-screen 0 1920x1080x24" dbus-run-session -- \
        gdb -q -batch -ex 'set pagination off' -ex 'set print thread-events off' \
            -ex 'handle SIGUSR1 SIGUSR2 SIGPIPE SIG32 SIG33 SIG34 SIG35 nostop noprint pass' \
            -ex run -ex 'bt 60' -ex 'info sharedlibrary' -ex 'x/8i $pc' -ex 'thread apply all bt 12' \
            --args python3 "$KOREN/packaging/webkit-deb/bolt_trening.py" \
            "http://127.0.0.1:8123/?startAutomatically&iterationCount=1" 2 \
        2>&1 | tail -n 400 | tee "$DELO/diagnoza.txt" || true
    [ -z "$srv" ] || kill "$srv" 2>/dev/null || true
}

# --- en poskus (notranji klic: SAFEER_BOLT_POSKUS="webkit jsc" ...); knjiznice v PREDPONA so izvirne ----------------
if [ -n "${SAFEER_BOLT_POSKUS:-}" ]; then
    rm -rf "$DELO/fdata" "$DELO/preveri" "$DELO/povzetek.txt"
    mkdir -p "$DELO/fdata"
    # --- 2. instrumentacija -------------------------------------------------------------------------------------------
    for ime in $SAFEER_BOLT_POSKUS; do
        pot="$(readlink -f "$PREDPONA/lib/${KNJIZNICA[$ime]}")"
        izvirnik="$DELO/izvirnik/$(basename "$pot")"
        preskoci="$(llint_preskoci "$izvirnik")"
        echo "bolt.sh: $ime --skip-funcs: ${preskoci:-(nic)}"
        "$LLVM/llvm-bolt" "$izvirnik" -o "$pot" -instrument \
            --instrumentation-file="$DELO/fdata/$ime" --instrumentation-file-append-pid ${preskoci:+"--skip-funcs=$preskoci"}
    done
    # --- 3. ucni tek --------------------------------------------------------------------------------------------------
    if ! bash "$TEK" "$PREDPONA" "$DELO/fdata" bolt; then
        diagnoza
        exit 1
    fi
    ls -l "$DELO/fdata"
    # Profil zapise proces, ki konca normalno (DT_FINI): glavni in spletni proces (Speedometer). Omrezni proces ob izhodu
    # glavnega profila ne zapise (CI 39213507046: webkit 9 MB glavni + 112 MB spletni, omrezni nic ali 0 B; prej
    # zahtevani 3 profili so zavrnili veljaven ucni tek). Zahteva: vsaj 2 neprazna profila, najvecji (spletni proces)
    # vsaj 32 MiB - brez njega profila najpomembnejsega procesa ni. Prazne datoteke ne gredo v merge-fdata.
    find "$DELO/fdata" -name '*.fdata' -size 0 -delete
    for ime in $SAFEER_BOLT_POSKUS; do
        n="$(find "$DELO/fdata" -name "$ime.*.fdata" -size +0 | wc -l)"
        [ "$n" -ge "${SAFEER_BOLT_NAJMANJ_PROFILOV:-2}" ] || { echo "bolt.sh: $ime ima samo $n profilov" >&2; exit 1; }
        najvecji="$(find "$DELO/fdata" -name "$ime.*.fdata" -printf '%s\n' | sort -n | tail -n 1)"
        [ "${najvecji:-0}" -ge $(( ${SAFEER_BOLT_NAJVECJI_PROFIL_MIB:-32} * 1048576 )) ] \
            || { echo "bolt.sh: $ime: najvecji profil ${najvecji:-0} B - profila spletnega procesa ni" >&2; exit 1; }
    done
    # --- 4. optimizacija ----------------------------------------------------------------------------------------------
    POVZETEK="bolt: da (llvm-bolt $LLVM_RAZLICICA, bolt-22 $LLVM_PAKET, ucni tek Speedometer 3.1)"
    for ime in $VSE; do
        pot="$(readlink -f "$PREDPONA/lib/${KNJIZNICA[$ime]}")"
        izvirnik="$DELO/izvirnik/$(basename "$pot")"
        case " $SAFEER_BOLT_POSKUS " in
            *" $ime "*) ;;
            *) POVZETEK="$POVZETEK; $(basename "$pot") brez BOLT"; continue ;;
        esac
        preskoci="$(llint_preskoci "$izvirnik")"
        # --use-old-text zahteva, da BOLT obdela VSE funkcije: z izpuscenim zbirnikom LLInt/IPInt (JavaScriptCore) pade
        # (CI 39223720608: »BOLT-ERROR: cannot ignore non-empty function llint_entry/1(*2) in current mode«). Zato
        # --use-old-text samo za knjiznico brez izpuscenih funkcij (libwebkitgtk: 188 -> 144,5 MB).
        moznosti=()
        for m in "${MOZNOSTI[@]}"; do
            if [ -n "$preskoci" ] && [ "$m" = --use-old-text ]; then continue; fi
            moznosti+=("$m")
        done
        "$LLVM/merge-fdata" "$DELO/fdata/$ime".*.fdata > "$DELO/$ime.fdata"
        "$LLVM/llvm-bolt" "$izvirnik" -o "$pot" --data="$DELO/$ime.fdata" "${moznosti[@]}" \
            ${preskoci:+"--skip-funcs=$preskoci"} 2>&1 | tee "$DELO/$ime.log"
        grep -E 'BOLT-INFO: [0-9]+ out of [0-9]+ functions in the binary' "$DELO/$ime.log" || true
        # Varovalo: knjiznica mora imeti PT_GNU_STACK z RW (brez X), sicer bi bil sklad vseh procesov izvrsljiv.
        sklad="$("$LLVM/llvm-readelf" -lW "$pot" | awk '$1 == "GNU_STACK" {print $7}')"
        if [ "$sklad" != RW ]; then
            echo "bolt.sh: $(basename "$pot") nima PT_GNU_STACK RW (${sklad:-ga ni}) - knjiznica ni uporabna" >&2
            exit 1
        fi
        POVZETEK="$POVZETEK; $(basename "$pot") $(stat -c %s "$izvirnik") -> $(stat -c %s "$pot") B,"
        POVZETEK="$POVZETEK $(find "$DELO/fdata" -name "$ime.*.fdata" | wc -l) profilov"
    done
    # --- 5. preverba z optimiziranimi knjiznicami -----------------------------------------------------------------------
    bash "$TEK" "$PREDPONA" "$DELO/preveri" preveri
    echo "$POVZETEK" | tee "$DELO/povzetek.txt"
    exit 0
fi

# --- 1. orodja (odvisnosti.sh namesti bolt-22 iz apt.llvm.org v LLVM_PAKET, isto gradnjo kot clang-22) --------------
for orodje in llvm-bolt merge-fdata llvm-readelf llvm-nm; do
    [ -x "$LLVM/$orodje" ] || { echo "NAPAKA: ni $LLVM/$orodje - najprej packaging/webkit-deb/odvisnosti.sh (bolt-22 $LLVM_PAKET)" >&2; exit 1; }
done
if command -v dpkg-query >/dev/null 2>&1 && dpkg-query -W bolt-22 >/dev/null 2>&1; then
    [ "$(dpkg-query -W -f '${Version}' bolt-22)" = "$LLVM_PAKET" ] \
        || { echo "NAPAKA: bolt-22 ni $LLVM_PAKET ($(dpkg-query -W -f '${Version}' bolt-22))" >&2; exit 1; }
fi
"$LLVM/llvm-bolt" --version | grep -E "LLVM version ${LLVM_RAZLICICA//./\\.}( |$)" >/dev/null \
    || { echo "NAPAKA: llvm-bolt ni LLVM $LLVM_RAZLICICA" >&2; exit 1; }

# --- 0. stanje pred BOLT za nadaljevanje (ne ustavi BOLT, ce ne gre: npr. poln disk) -------------------------------
GRADNJA="$(dirname "$DELO")/webkit"   # mapa gradnje WebKita v zgradi.sh (DELO zgradi.sh/webkit)
ARHIV="${SAFEER_BOLT_PREDBOLT:-}"
if [ -n "$ARHIV" ] && [ ! -f "$ARHIV" ] && [ -f "$GRADNJA/CMakeCache.txt" ]; then
    Z="$(dirname "$DELO")/predbolt"
    if rm -rf "$Z" && mkdir -p "$Z" "$(dirname "$ARHIV")" \
        && grep -E '^(CMAKE_BUILD_TYPE|CMAKE_CXX_COMPILER|CMAKE_INSTALL_PREFIX|LTO_MODE|ENABLE_LLVM_PROFILE_GENERATION|USE_PGO_PROFILE):' \
            "$GRADNJA/CMakeCache.txt" > "$Z/cmake.txt" \
        && for z in -fuse-ld=lld -flto=thin -fprofile-generate -fprofile-use --emit-relocs; do
               echo "build.ninja $z: $(grep -c -e "$z" "$GRADNJA/build.ninja" || true)"; done > "$Z/stevci.txt" \
        && tar -C / -I 'zstd -3 -T0' -cf "$ARHIV.del" "${PREDPONA#/}" "${Z#/}" \
        && zstd -q -t "$ARHIV.del" && mv "$ARHIV.del" "$ARHIV"; then
        ls -l "$ARHIV"
    else
        echo "::warning::bolt.sh: stanja pred BOLT ni bilo mogoce shraniti ($ARHIV)"
        rm -f "$ARHIV.del"
    fi
fi

# --- izvirnika (s simboli in relokacijami) ostaneta v DELO/izvirnik; vsak poskus zacne z njima ---------------------
rm -rf "$DELO"
mkdir -p "$DELO/izvirnik"
for ime in $VSE; do
    pot="$(readlink -f "$PREDPONA/lib/${KNJIZNICA[$ime]}")"
    [ -f "$pot" ] || { echo "bolt.sh: ni $PREDPONA/lib/${KNJIZNICA[$ime]}" >&2; exit 1; }
    # Brez staticnih relokacij BOLT ne more premikati funkcij (samo -Wl,--emit-relocs, zgradi.sh s SAFEER_WEBKIT_BOLT=1).
    # grep brez -q prebere ves izhod: -q bi zaprl cev, readelf bi dobil SIGPIPE in pipefail bi javil napacno napako.
    "$LLVM/llvm-readelf" -S "$pot" | grep '\.rela\.text' >/dev/null \
        || { echo "bolt.sh: $pot nima .rela.text - povezava brez -Wl,--emit-relocs" >&2; exit 1; }
    cp -p "$pot" "$DELO/izvirnik/$(basename "$pot")"
done
obnovi() { for f in "$DELO"/izvirnik/*; do cp -p "$f" "$PREDPONA/lib/$(basename "$f")"; done; }

IFS=';' read -r -a POSKUSI <<< "${SAFEER_BOLT_POSKUSI:-webkit jsc;webkit;jsc}"
for poskus in "${POSKUSI[@]}"; do
    obnovi
    echo "=== bolt.sh: poskus $poskus ==="
    if SAFEER_BOLT_POSKUS="$poskus" bash "${BASH_SOURCE[0]}" "$PREDPONA" "$DELO"; then
        cat "$DELO/povzetek.txt"
        exit 0
    fi
    echo "::warning::bolt.sh: BOLT ($poskus) ni uspel"
done
obnovi
[ ! -f "$DELO/diagnoza.txt" ] || { echo "--- diagnoza (gdb) ---"; cat "$DELO/diagnoza.txt"; }
echo "bolt.sh: noben poskus BOLT ni uspel" >&2
exit 1
