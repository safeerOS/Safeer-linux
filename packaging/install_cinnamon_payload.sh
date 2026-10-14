#!/usr/bin/env bash
# Safeer Cinnamon payload: the desktop look and the Safeer workspace for Linux Mint Cinnamon (derived from CBlue),
# Safeer wallpapers, the Plank dock theme, the layout chooser, the safeer-cinnamon command and the boot/login look.
# Since 12. 10. 2026 it ships inside the single safeer-os package (build_os_deb.sh): one download, one install,
# one update. Installing changes nothing until the user opens "Safeer Cinnamon" in the menu and picks a layout.
#
#   install_cinnamon_payload.sh DESTINATION_ROOT        (files go to DESTINATION_ROOT/usr/...)
set -euo pipefail
KOREN="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="${1:?Usage: install_cinnamon_payload.sh DESTINATION_ROOT}"
T="$KOREN/packaging/tema-cinnamon"

mkdir -p "$ROOT/usr/share/themes" "$ROOT/usr/bin" "$ROOT/usr/share/applications" \
         "$ROOT/usr/share/safeer-cinnamon/plank" "$ROOT/usr/share/backgrounds/safeer" \
         "$ROOT/usr/share/cinnamon-background-properties" "$ROOT/usr/share/doc/safeer-cinnamon" \
         "$ROOT/usr/share/plymouth/themes/safeer" "$ROOT/usr/lib/safeer-cinnamon" "$ROOT/usr/share/polkit-1/actions"
cp -a "$T/Safeer-Cinnamon" "$T/Safeer-Cinnamon-Kontrast" "$ROOT/usr/share/themes/"
# Applet Safeer Miska (miska v pultu: nastavitve in baterija brezzicne miske), dodan ob vklopu postavitve.
mkdir -p "$ROOT/usr/share/cinnamon/applets"
cp -a "$T/appleti/miska@safeer.si" "$ROOT/usr/share/cinnamon/applets/"
chmod 644 "$ROOT/usr/share/cinnamon/applets/miska@safeer.si/"*
# Obrobe oken rise Mint-Y (kot pri vseh Mintovih temah): barve vzame iz nase teme GTK (wm_bg, wm_title,
# selected_bg_color ...), zato so v paleti Safeer. GTK 2 prevzamemo od Mint-Y-Dark-Blue.
for tema in Safeer-Cinnamon Safeer-Cinnamon-Kontrast; do
    ln -s /usr/share/themes/Mint-Y/metacity-1 "$ROOT/usr/share/themes/$tema/metacity-1"
    ln -s /usr/share/themes/Mint-Y-Dark-Blue/gtk-2.0 "$ROOT/usr/share/themes/$tema/gtk-2.0"
done
install -m 755 "$T/safeer-cinnamon" "$ROOT/usr/bin/safeer-cinnamon"
install -m 755 "$T/izbira" "$ROOT/usr/lib/safeer-cinnamon/izbira"
install -m 644 "$T/plank/dock.theme" "$ROOT/usr/share/safeer-cinnamon/plank/dock.theme"
install -m 644 "$T"/ozadje/*.jpg "$T/ozadje/safeer-gore-3840x2160.png" "$T/ozadje/safeer-gore-16-9.svg" "$ROOT/usr/share/backgrounds/safeer/"
install -m 644 "$T/safeer-cinnamon-ozadje.xml" "$ROOT/usr/share/cinnamon-background-properties/safeer-cinnamon.xml"
install -m 644 "$T/safeer-cinnamon-vklopi.desktop" "$ROOT/usr/share/applications/safeer-cinnamon.desktop"
install -m 644 "$T/safeer-cinnamon-izklopi.desktop" "$ROOT/usr/share/applications/safeer-cinnamon-izklopi.desktop"
install -m 644 "$T/COPYING" "$ROOT/usr/share/doc/safeer-cinnamon/copyright"
# Safeer od vklopa: zagonski zaslon (Plymouth) in pomocnik, ki ga in prijavni zaslon vklopi sele na uporabnikovo
# zahtevo (safeer-cinnamon --od-vklopa, skrbnisko geslo prek pkexec). Namestitev paketa sama ne spremeni nicesar.
install -m 644 "$T"/plymouth/safeer/* "$ROOT/usr/share/plymouth/themes/safeer/"
install -m 755 "$T/od-vklopa" "$ROOT/usr/lib/safeer-cinnamon/od-vklopa"
install -m 644 "$T/si.safeer.cinnamon.od-vklopa.policy" "$ROOT/usr/share/polkit-1/actions/si.safeer.cinnamon.od-vklopa.policy"
install -m 644 "$T/safeer-cinnamon-od-vklopa.desktop" "$ROOT/usr/share/applications/safeer-cinnamon-od-vklopa.desktop"
install -m 644 "$T/safeer-cinnamon-od-vklopa-izklopi.desktop" "$ROOT/usr/share/applications/safeer-cinnamon-od-vklopa-izklopi.desktop"
find "$ROOT/usr/share/themes/Safeer-Cinnamon" "$ROOT/usr/share/themes/Safeer-Cinnamon-Kontrast" \
     "$ROOT/usr/share/safeer-cinnamon" "$ROOT/usr/share/backgrounds/safeer" "$ROOT/usr/share/plymouth/themes/safeer" \
     -type f -exec chmod 644 {} +
