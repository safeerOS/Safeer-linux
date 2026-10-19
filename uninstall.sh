#!/usr/bin/env bash
# ==============================================================================
# Safeer Browser — Linux Mint & Ubuntu Clean Uninstaller
# Removes CLI binaries, desktop shortcuts, application menu entries, and icons
# ==============================================================================
set -e

BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_BASE="$HOME/.local/share/icons/hicolor"
# Poti, kamor pise brskalnik iz izvorne kode (safeer_brskalnik.py) ali je pisal umaknjeni GTK3 brskalnik (pregled 16. 10. 2026):
#  - profil (nastavitve, zaznamki, prijave, web-data, dnevnik): core/config.py CONFIG_DIR - skupen obema;
#  - privzeti mapi WebKita po prgname: GTK4 »io.github.memelandfaner.SafeerBrowser« (safeer_brskalnik.py:
#    GLib.set_prgname(APP_ID)), GTK3 »safeer-browser«, pred tem ime skripte;
#  - seznami filtrov in groženj: core/threat_intel.default_data_dir("safeer-mint") (skupni s Safeer OS).
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/safeer-mint"
CACHE_HOME="${XDG_CACHE_HOME:-$HOME/.cache}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
APP_ID="io.github.memelandfaner.SafeerBrowser"
CACHE_DIRS=("$CACHE_HOME/$APP_ID" "$CACHE_HOME/safeer_brskalnik.py" "$CACHE_HOME/safeer-browser"
            "$CACHE_HOME/safeer_mint.py" "$CONFIG_DIR/web-data/cache")
# Podatki strani (piskotki, shramba, licence DRM) in preneseni seznami: samo z --purge.
PURGE_DIRS=("$CONFIG_DIR" "$DATA_HOME/$APP_ID" "$DATA_HOME/safeer_brskalnik.py" "$DATA_HOME/safeer-browser"
            "$DATA_HOME/safeer_mint.py" "$DATA_HOME/safeer-mint")

echo "=========================================================="
echo "🗑️ ODSTRANJEVANJE: Safeer Browser iz Linux sistema"
echo "=========================================================="

# 1. Zaustavi morebitne tekoče procese
echo "1. Ustavljanje morebitnih aktivnih procesov Safeer..."
# Samo procesi tega uporabnika iz te mape (klon), ne Safeer Browser iz paketa ali drug program s tem imenom v ukazu.
DIR_VZOREC="$(cd "$(dirname "$0")" && pwd | sed 's/[][\.*^$+?(){}|]/\\&/g')"
pkill -u "$(id -u)" -f "$DIR_VZOREC/(safeer_brskalnik\.py|safeer-mint\.sh)" 2>/dev/null || true

# 2. Odstrani zaganjalne povezave (CLI)
echo "2. Odstranjevanje povezav v $BIN_DIR..."
rm -f "$BIN_DIR/safeer" "$BIN_DIR/safeer-browser"

# 3. Odstrani .desktop datoteko iz menija aplikacij
echo "3. Odstranjevanje menijske bližnjice..."
rm -f "$DESKTOP_DIR/safeer-browser.desktop"

# 4. Odstrani bližnjice z namizja
echo "4. Odstranjevanje bližnjic z namizja..."
for d in "$HOME/Namizje" "$HOME/Desktop"; do
    if [[ -d "$d" ]]; then
        rm -f "$d/safeer-browser.desktop" "$d/Safeer-Browser.desktop" 2>/dev/null || true
    fi
done

# 5. Odstrani ikone
echo "5. Odstranjevanje namenske ikone..."
rm -f "$HOME/.local/share/pixmaps/safeer-browser.png"
for size in 512x512 256x256 128x128 64x64 48x48 32x32 24x24 16x16; do
    rm -f "$ICON_BASE/$size/apps/safeer-browser.png" 2>/dev/null || true
done
rm -f "$ICON_BASE/scalable/apps/safeer-browser.svg" 2>/dev/null || true

# 6. Počisti začasne predpomnilnike in zastarele sockete
echo "6. Čiščenje predpomnilnika in začasnih socketov..."
rm -rf "${CACHE_DIRS[@]}"
rm -f "$CONFIG_DIR/safeer.sock" "$CONFIG_DIR/safeer.lock" 2>/dev/null || true

# Če je podana zastavica --purge, odstrani tudi uporabniške nastavitve, zaznamke in podatke strani.
# Profil ~/.config/safeer-mint in seznami v ~/.local/share/safeer-mint so skupni s paketom safeer-browser, Safeer OS
# in Flatpakom: ce je kateri od njih namescen, jih ne brisemo (bili bi izgubljeni tudi tam).
if [[ "$1" == "--purge" ]]; then
    DRUGI=""
    for paket in safeer-browser safeer-os; do
        dpkg -s "$paket" >/dev/null 2>&1 && DRUGI="$DRUGI $paket"
    done
    if command -v flatpak >/dev/null 2>&1 && flatpak info io.github.memelandfaner.SafeerBrowser >/dev/null 2>&1; then
        DRUGI="$DRUGI Flatpak"
    fi
    if [[ -n "$DRUGI" ]]; then
        echo "⚠️ --purge: profil ($CONFIG_DIR) uporablja tudi:$DRUGI - ostane nespremenjen."
        echo "   Ce ga zelite vseeno odstraniti, najprej odstranite te namestitve."
    else
        echo "⚠️ --purge: Odstranjevanje uporabniškega profila in podatkov strani..."
        for d in "${PURGE_DIRS[@]}"; do
            echo "   $d"
        done
        rm -rf "${PURGE_DIRS[@]}"
    fi
fi

# 7. Posodobi sistemske baze namizja in ikon
echo "7. Posodabljanje predpomnilnika ikon in namiznih povezav..."
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
gtk-update-icon-cache -f -t "$ICON_BASE" 2>/dev/null || true

echo "✅ Safeer Browser je bil uspešno odstranjen iz sistema!"
echo "=========================================================="
