# --- Safeer WebKit, vgrajen v paket (packaging/webkit-deb/vgradi_v_program.sh; lastnik, 20. 10. 2026) ----------------
# Vsak program Safeer (safeer-os = namizno okolje, safeer-os-app = aplikacija, safeer-browser) nosi nas WebKitGTK v
# /usr/lib/@PROGRAM@/webkit-vgrajen in ga namesti v skupno mapo /usr/lib/safeer-webkit (predpona, prevedena v knjiznice).
# Ce je ista gradnja (enak odtis) ze namescena - npr. od namizja -, je ne namesti ponovno: datoteke vira samo poveze
# (trda povezava) z ze namescenimi, da na disku ni druge kopije. Starejse ne namesti cez novejso.
if [ "${1:-}" = "configure" ] && [ -f /usr/lib/@PROGRAM@/webkit-vgrajen/share/webkitgtk-safeer/odtis ]; then
    wk_vir=/usr/lib/@PROGRAM@/webkit-vgrajen
    wk_cilj=/usr/lib/safeer-webkit
    wk_podatki=share/webkitgtk-safeer
    if [ -f "$wk_cilj/$wk_podatki/odtis" ] && cmp -s "$wk_vir/$wk_podatki/odtis" "$wk_cilj/$wk_podatki/odtis"; then
        echo "Safeer WebKit je ze namescen (ista gradnja): ne namescam ga ponovno."
        # Enake datoteke vira -> trde povezave na namescene (vsebina ostane ista, dpkg --verify je zadovoljen).
        ( cd "$wk_vir" && find . -type f ) | while IFS= read -r wk_f; do
            if [ -f "$wk_cilj/$wk_f" ] && [ ! "$wk_vir/$wk_f" -ef "$wk_cilj/$wk_f" ] && cmp -s "$wk_vir/$wk_f" "$wk_cilj/$wk_f"; then
                ln -f "$wk_cilj/$wk_f" "$wk_vir/$wk_f" 2>/dev/null || true
            fi
        done
    elif [ -f "$wk_cilj/$wk_podatki/razlicica" ] && [ -f "$wk_vir/$wk_podatki/razlicica" ] \
         && dpkg --compare-versions "$(cat "$wk_cilj/$wk_podatki/razlicica")" gt "$(cat "$wk_vir/$wk_podatki/razlicica")"; then
        echo "Safeer WebKit: namescen je novejsi ($(cat "$wk_cilj/$wk_podatki/razlicica")), ostane."
    else
        wk_novo="$wk_cilj.novo.$$"
        rm -rf "$wk_novo"
        # Trde povezave: brez druge kopije na disku; ce /usr/lib ni en datotecni sistem, kopija.
        cp -al "$wk_vir" "$wk_novo" 2>/dev/null || { rm -rf "$wk_novo"; cp -a "$wk_vir" "$wk_novo"; }
        if [ -e "$wk_cilj" ]; then
            # Tekoci programi obdrzijo stare knjiznice v pomnilniku (izbrisane datoteke ostanejo preslikane);
            # Safeer OS in Control ob novem odtisu zazeneta znova (core/nova_razlicica.py).
            wk_staro="$wk_cilj.staro.$$"
            rm -rf "$wk_staro"
            mv "$wk_cilj" "$wk_staro"
            mv "$wk_novo" "$wk_cilj"
            rm -rf "$wk_staro"
        else
            mv "$wk_novo" "$wk_cilj"
        fi
        echo "Safeer WebKit $(cat "$wk_cilj/$wk_podatki/razlicica" 2>/dev/null || true) je namescen v $wk_cilj."
    fi
fi
# --- konec Safeer WebKit -------------------------------------------------------------------------------------------
