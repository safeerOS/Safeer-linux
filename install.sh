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
# SAFEER_BRSKALNIK_GTK3=1: zastareli GTK3 brskalnik (safeer_mint.py, WebKit2GTK 4.1) do umika.
if [ "${SAFEER_BRSKALNIK_GTK3:-0}" = 1 ]; then
    PAKETI="python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1 gir1.2-soup-3.0 gir1.2-glib-2.0"
else
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
chmod +x "$DIR/safeer_mint.py"
chmod +x "$DIR/safeer-mint.sh"
chmod +x "$DIR/safeer-browser.desktop"

# 2. Install executable into ~/.local/bin so user can run 'safeer' from anywhere
mkdir -p "$BIN_DIR"
ln -sf "$DIR/safeer-mint.sh" "$BIN_DIR/safeer"
ln -sf "$DIR/safeer-mint.sh" "$BIN_DIR/safeer-browser"

# Ensure ~/.local/bin is in PATH for current session if not already
export PATH="$BIN_DIR:$PATH"

# 3. Install App Icon to standard hicolor directory with proper scaling
if [[ -f "$DIR/assets/icon.png" ]]; then
    python3 -c "
import os
from PIL import Image
src = '$DIR/assets/icon.png'
base = '$ICON_BASE'
sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32)]
try:
    img = Image.open(src)
    for w, h in sizes:
        target_dir = os.path.join(base, f'{w}x{h}', 'apps')
        os.makedirs(target_dir, exist_ok=True)
        out_path = os.path.join(target_dir, 'safeer-browser.png')
        img.resize((w, h), Image.Resampling.LANCZOS).save(out_path, 'PNG')
except Exception:
    pass
" 2>/dev/null || {
        for size in 256x256 128x128 64x64 48x48 32x32; do
            mkdir -p "$ICON_BASE/$size/apps"
            cp "$DIR/assets/icon.png" "$ICON_BASE/$size/apps/safeer-browser.png"
        done
    }
    mkdir -p "$HOME/.local/share/pixmaps"
    cp "$DIR/assets/icon.png" "$HOME/.local/share/pixmaps/safeer-browser.png"
fi

# 4. Install .desktop file to application menu
mkdir -p "$DESKTOP_DIR"
# GTK4 brskalnik: vnos iz paketov (StartupWMClass = ID aplikacije, brez »Novo okno« - en primerek); GTK3 ima svojega.
if [ "${SAFEER_BRSKALNIK_GTK3:-0}" = 1 ]; then
    sed -e "s|Exec=safeer-browser|Exec=$BIN_DIR/safeer-browser|g" \
        "$DIR/safeer-browser.desktop" > "$DESKTOP_DIR/safeer-browser.desktop"
else
    sed -e "s|^Exec=safeer |Exec=$BIN_DIR/safeer-browser |" \
        "$DIR/packaging/safeer-browser.desktop" > "$DESKTOP_DIR/safeer-browser.desktop"
fi
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
