# shellcheck shell=bash
# Ali je PREDPONA (/usr/lib/safeer-webkit) WebKit namescenega Safeerja - takrat je lokalna gradnja (zgradi.sh,
# nadaljuj.sh) ne sme izbrisati (rm -rf). Izpise razlog ali nic.
#
# Tedenski pregled 4. 11. 2026 (S16): od vgrajenega WebKita (packaging/webkit-deb/vgradi_v_program.sh) mapa ni datoteka
# nobenega paketa - postinst programa jo napolni iz /usr/lib/<program>/webkit-vgrajen -, zato je `dpkg -S` ne najde vec
# in gradnja bi namesceni Safeer pustila brez WebKita. Zato se: odtis namescene gradnje in stanje paketov Safeer.
predpona_namescena() {
    local predpona="$1" paket stanje razlog=""
    if command -v dpkg >/dev/null 2>&1 && paket="$(dpkg -S "$predpona" 2>/dev/null)"; then
        razlog="pripada paketu ${paket%%: *}"
    elif [ -e "$predpona/share/webkitgtk-safeer/odtis" ]; then
        razlog="ima odtis namescene gradnje ($predpona/share/webkitgtk-safeer/odtis)"
    fi
    if [ -z "$razlog" ] && command -v dpkg-query >/dev/null 2>&1; then
        for paket in safeer-os safeer-os-app safeer-browser safeer-webkit; do
            stanje="$(dpkg-query -W -f '${db:Status-Status}' "$paket" 2>/dev/null || true)"
            case "$stanje" in
                ""|not-installed|config-files) ;;
                *) razlog="paket $paket je namescen ($stanje) in uporablja to mapo"; break ;;
            esac
        done
    fi
    printf '%s' "$razlog"
}
