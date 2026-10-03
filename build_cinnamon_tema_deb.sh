#!/usr/bin/env bash
# ==============================================================================
# Safeer Cinnamon — .deb: modra polprosojna tema za Linux Mint Cinnamon (po CBlue),
# ozadje Safeer, tema za dock Plank in ukaz safeer-cinnamon (vklop/izklop/kontrast/tekst).
# Loceno od safeer-os-tema: ta paket ne zazene Safeer OS in ne spremeni nicesar, dokler
# uporabnik ne izbere "Safeer Cinnamon" v meniju (ali pozene safeer-cinnamon).
# ==============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(cat "$DIR/packaging/VERSION_CINNAMON")"
DEB_PACKAGE="safeer-cinnamon_${VERSION}_all.deb"
ROOT="$DIR/build/deb-cinnamon"
T="$DIR/packaging/tema-cinnamon"

rm -rf "$ROOT"
mkdir -p "$ROOT/DEBIAN" "$ROOT/usr/share/themes" "$ROOT/usr/bin" "$ROOT/usr/share/applications" \
         "$ROOT/usr/share/safeer-cinnamon/plank" "$ROOT/usr/share/backgrounds/safeer" \
         "$ROOT/usr/share/cinnamon-background-properties" "$ROOT/usr/share/doc/safeer-cinnamon" \
         "$ROOT/usr/share/plymouth/themes/safeer" "$ROOT/usr/lib/safeer-cinnamon" "$ROOT/usr/share/polkit-1/actions"
cp -a "$T/Safeer-Cinnamon" "$T/Safeer-Cinnamon-Kontrast" "$ROOT/usr/share/themes/"
# Obrobe oken prevzame od Mint-Y (tako kot vse Mintove teme, tudi Mint-Y-Dark-Blue), GTK 2 od Mint-Y-Dark-Blue.
ln -s /usr/share/themes/Mint-Y/metacity-1 "$ROOT/usr/share/themes/Safeer-Cinnamon/metacity-1"
ln -s /usr/share/themes/Mint-Y-Dark-Blue/gtk-2.0 "$ROOT/usr/share/themes/Safeer-Cinnamon/gtk-2.0"
install -m 755 "$T/safeer-cinnamon" "$ROOT/usr/bin/safeer-cinnamon"
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

cat > "$ROOT/DEBIAN/control" <<EOF2
Package: safeer-cinnamon
Version: ${VERSION}
Section: x11
Priority: optional
Architecture: all
Depends: mint-themes, libglib2.0-bin
Recommends: cinnamon, plank, papirus-icon-theme, dconf-cli, safeer-os
Suggests: plymouth, slick-greeter
Maintainer: Safeer <info@safeer.si>
Homepage: https://safeer.si/os/
Description: Safeer Cinnamon - a calm blue desktop look for Linux Mint
 A semi-transparent dark blue theme for Cinnamon, GTK 3/4 and window borders
 (derived from CBlue, built on Mint-Y-Dark-Blue), a mountain-and-lake Safeer
 wallpaper and a matching Plank dock. Nothing changes until you choose
 "Safeer Cinnamon" in the menu; "Restore previous look" puts everything back.
 Options: safeer-cinnamon --kontrast (opaque, stronger borders),
 --vecji-tekst (125 % text) and --od-vklopa (the Safeer look on the boot
 and login screen too; asks for the administrator password and
 --od-vklopa-izklopi restores what was there before).
EOF2
chmod 644 "$ROOT/DEBIAN/control"
# Ob odstranitvi paketa: uporabnikove nastavitve ostanejo njegove; tema, ki je ni vec,
# bi Cinnamon zamenjal s privzeto, zato uporabnika opozorimo, kako vrniti prejsnji videz.
cat > "$ROOT/DEBIAN/prerm" <<'EOF2'
#!/bin/sh
set -e
if [ "$1" = "remove" ]; then
    # Zagonski in prijavni zaslon sta sistemska: vrnemo ju, preden izginejo datoteke teme.
    if [ -x /usr/lib/safeer-cinnamon/od-vklopa ]; then /usr/lib/safeer-cinnamon/od-vklopa izklopi || true; fi
    echo "Safeer Cinnamon: pred odstranitvijo zazenite 'safeer-cinnamon --izklopi' kot vas uporabnik,"
    echo "da se vrne vas prejsnji videz (sicer Cinnamon sam preklopi na privzeto temo)."
fi
exit 0
EOF2
chmod 755 "$ROOT/DEBIAN/prerm"
cat > "$ROOT/DEBIAN/postrm" <<'EOF2'
#!/bin/sh
set -e
if [ "$1" = "purge" ]; then rm -rf /var/lib/safeer-cinnamon; fi
exit 0
EOF2
chmod 755 "$ROOT/DEBIAN/postrm"
find "$ROOT" -type d -exec chmod 755 {} +
find "$ROOT/usr/share" -type f -exec chmod 644 {} +

dpkg-deb --root-owner-group --build "$ROOT" "$DIR/$DEB_PACKAGE"
echo "OK: $DEB_PACKAGE"
