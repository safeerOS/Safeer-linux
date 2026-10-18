#!/usr/bin/env bash
# ==============================================================================
# Safeer Browser — Linux Mint & Ubuntu One-Click Installer
# Full XDG integration: App menu, Desktop shortcut, Icons, and 'safeer' CLI
# ==============================================================================
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_BASE="$HOME/.local/share/icons/hicolor"

echo "=========================================================="
echo "🛡️ NAMEŠČANJE: Safeer Browser za Linux Mint"
echo "=========================================================="

# Preveri potrebne sistemske pakete. Privzeto (od 16. 10. 2026) install.sh zazene GTK4 brskalnik safeer_brskalnik.py
# (GTK4, WebKitGTK 6.0), zato velja isti seznam kot Depends GTK4 paketa v build_deb.sh (test
# tests/test_install_odvisnosti.py); kodeki GStreamer so v seznamu, ker brez njih video na straneh ne dela.
echo "Zahteva: Linux Mint 22 / Ubuntu 24.04 ali novejši (GTK4, WebKitGTK 6.0)."
PAKETI="python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-webkit-6.0 gir1.2-soup-3.0 gir1.2-glib-2.0 gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad gstreamer1.0-libav gstreamer1.0-gl"
# WebKitGTK 6.0 je v arhivu sele od Linux Mint 22 / Ubuntu 24.04: na starejsem sistemu ga apt ne najde, zato to
# povemo jasno, namesto da apt install pade z »Unable to locate package«.
if ! dpkg -s gir1.2-webkit-6.0 >/dev/null 2>&1 && command -v apt-cache >/dev/null 2>&1 \
        && ! apt-cache policy gir1.2-webkit-6.0 2>/dev/null | grep -q "Candidate: [0-9]"; then
    echo "❌ Safeer Browser potrebuje WebKitGTK 6.0 (gir1.2-webkit-6.0), ki ga ima Linux Mint 22 / Ubuntu 24.04 ali novejši."
    echo "   Apt ga na tem sistemu ne najde (po sveži namestitvi najprej: sudo apt update)."
    echo "   Na starejšem sistemu: nadgradite ga ali namestite Flatpak (io.github.memelandfaner.SafeerBrowser)."
    exit 1
fi
MISSING_PKGS=()
for pkg in $PAKETI; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
        MISSING_PKGS+=("$pkg")
    fi
done

if [ ${#MISSING_PKGS[@]} -ne 0 ]; then
    echo "⚠️  OPOZORILO: Manjkajo naslednji sistemski paketi:"
    echo "   ${MISSING_PKGS[*]}"
    if [ -t 0 ]; then
        read -p "Ali želite samodejno namestiti manjkajoče pakete z 'sudo apt install'? [D/n]: " -r REPLY
        if [[ "$REPLY" =~ ^[DdYy]?$ ]]; then
            sudo apt update && sudo apt install -y "${MISSING_PKGS[@]}"
        else
            echo "Namestitev nadaljujem brez paketov (za delovanje jih namestite naknadno)."
        fi
    else
        echo "   Za polno delovanje jih namestite z ukazom:"
        echo "   sudo apt update && sudo apt install -y ${MISSING_PKGS[*]}"
    fi
    echo "----------------------------------------------------------"
fi

# 1. Ensure execute permissions
chmod +x "$DIR/safeer-mint.sh"

# 2. Install executable into ~/.local/bin so user can run 'safeer' from anywhere
mkdir -p "$BIN_DIR"
ln -sf "$DIR/safeer-mint.sh" "$BIN_DIR/safeer"
ln -sf "$DIR/safeer-mint.sh" "$BIN_DIR/safeer-browser"

# Ensure ~/.local/bin is in PATH for current session if not already
export PATH="$BIN_DIR:$PATH"

# 3. Install App Icon: Safeer Browser's own icon (globe with "S", assets/brskalnik.svg), not the Safeer OS shield.
# PNG sizes come pre-rendered from packaging/icons/hicolor (tools/izrisi_ikone.py).
if [[ -d "$DIR/packaging/icons/hicolor" ]]; then
    for icon in "$DIR/packaging/icons/hicolor"/*/apps/safeer-browser.png; do
        [[ -f "$icon" ]] || continue
        size="$(basename "$(dirname "$(dirname "$icon")")")"
        mkdir -p "$ICON_BASE/$size/apps"
        cp "$icon" "$ICON_BASE/$size/apps/safeer-browser.png"
    done
    mkdir -p "$HOME/.local/share/pixmaps"
    cp "$DIR/packaging/icons/hicolor/256x256/apps/safeer-browser.png" "$HOME/.local/share/pixmaps/safeer-browser.png"
fi
if [[ -f "$DIR/assets/brskalnik.svg" ]]; then
    mkdir -p "$ICON_BASE/scalable/apps"
    cp "$DIR/assets/brskalnik.svg" "$ICON_BASE/scalable/apps/safeer-browser.svg"
fi

# 4. Install .desktop file to application menu
mkdir -p "$DESKTOP_DIR"
# Vnos iz paketov (StartupWMClass = ID aplikacije, brez »Novo okno« - en primerek).
sed -e "s|^Exec=safeer |Exec=$BIN_DIR/safeer-browser |" \
    "$DIR/packaging/safeer-browser.desktop" > "$DESKTOP_DIR/safeer-browser.desktop"
chmod +x "$DESKTOP_DIR/safeer-browser.desktop"

# 5. Create Desktop shortcut if Desktop or Namizje exists
for d in "$HOME/Namizje" "$HOME/Desktop"; do
    if [[ -d "$d" ]]; then
        cp "$DESKTOP_DIR/safeer-browser.desktop" "$d/safeer-browser.desktop"
        chmod +x "$d/safeer-browser.desktop"
        gio set "$d/safeer-browser.desktop" metadata::trusted true 2>/dev/null || true
    fi
done

# 6. Update desktop and icon caches
update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
gtk-update-icon-cache -f -t "$ICON_BASE" 2>/dev/null || true

echo "✅ Safeer Browser je bil uspešno nameščen!"
echo "   - Ukaz v terminalu: 'safeer' ali 'safeer-browser [URL]'"
echo "   - Bližnjica na namizju: Safeer Browser"
echo "   - Linux Mint Meni: Internet -> Safeer Browser"
echo "   - Zagon z enim klikom: $DIR/safeer-mint.sh"
echo "=========================================================="
