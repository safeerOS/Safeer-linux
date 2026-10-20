# --- Safeer WebKit, vgrajen v paket (packaging/webkit-deb/vgradi_v_program.sh) ---------------------------------------
# /usr/lib/safeer-webkit ni datoteka nobenega paketa: odstrani ga zadnji program Safeer, ki ga uporablja. Ne ob
# posodobitvi in ne, ce je namescen se kateri (tudi napol) ali star paket safeer-webkit (do 1.0.128), ki mapo ima v lasti.
if [ "${1:-}" = "remove" ] || [ "${1:-}" = "purge" ]; then
    wk_ostane=""
    for wk_p in safeer-os safeer-os-app safeer-browser safeer-webkit; do
        # Sebe ne steje: med postrm je ta paket se »napol namescen« (H).
        [ "$wk_p" = "@PROGRAM@" ] && continue
        # Druga crka stanja: i namescen, U razpakiran, F napol nastavljen, H napol namescen, W/t sprozilci.
        case "$(dpkg-query -W -f='${db:Status-Abbrev}' "$wk_p" 2>/dev/null || true)" in
            ?[iUFHWt]*) wk_ostane="$wk_p" ;;
        esac
    done
    if [ -z "$wk_ostane" ] && [ -d /usr/lib/safeer-webkit ]; then
        rm -rf /usr/lib/safeer-webkit
        echo "Safeer WebKit odstranjen (noben program Safeer ga ne uporablja vec)."
    fi
fi
# --- konec Safeer WebKit -------------------------------------------------------------------------------------------
