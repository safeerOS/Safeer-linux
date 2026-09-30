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
         "$ROOT/usr/share/cinnamon-background-properties" "$ROOT/usr/share/doc/safeer-cinnamon"
cp -a "$T/Safeer-Cinnamon" "$T/Safeer-Cinnamon-Kontrast" "$ROOT/usr/share/themes/"
# Obrobe oken prevzame od Mint-Y (tako kot vse Mintove teme, tudi Mint-Y-Dark-Blue), GTK 2 od Mint-Y-Dark-Blue.
ln -s /usr/share/themes/Mint-Y/metacity-1 "$ROOT/usr/share/themes/Safeer-Cinnamon/metacity-1"
ln -s /usr/share/themes/Mint-Y-Dark-Blue/gtk-2.0 "$ROOT/usr/share/themes/Safeer-Cinnamon/gtk-2.0"
install -m 755 "$T/safeer-cinnamon" "$ROOT/usr/bin/safeer-cinnamon"
install -m 644 "$T/plank/dock.theme" "$ROOT/usr/share/safeer-cinnamon/plank/dock.theme"
install -m 644 "$T/ozadje/safeer-gore-3840x2160.png" "$T/ozadje/safeer-gore-16-9.svg" "$ROOT/usr/share/backgrounds/safeer/"
install -m 644 "$T/safeer-cinnamon-ozadje.xml" "$ROOT/usr/share/cinnamon-background-properties/safeer-cinnamon.xml"
install -m 644 "$T/safeer-cinnamon-vklopi.desktop" "$ROOT/usr/share/applications/safeer-cinnamon.desktop"
install -m 644 "$T/safeer-cinnamon-izklopi.desktop" "$ROOT/usr/share/applications/safeer-cinnamon-izklopi.desktop"
install -m 644 "$T/COPYING" "$ROOT/usr/share/doc/safeer-cinnamon/copyright"

cat > "$ROOT/DEBIAN/control" <<EOF2
Package: safeer-cinnamon
Version: ${VERSION}
Section: x11
Priority: optional
Architecture: all
Depends: mint-themes, libglib2.0-bin
Recommends: cinnamon, plank, papirus-icon-theme, dconf-cli
Maintainer: Safeer <info@safeer.si>
Homepage: https://safeer.si/os/
Description: Safeer Cinnamon - a calm blue desktop look for Linux Mint
 A semi-transparent dark blue theme for Cinnamon, GTK 3/4 and window borders
 (derived from CBlue, built on Mint-Y-Dark-Blue), a mountain-and-lake Safeer
 wallpaper and a matching Plank dock. Nothing changes until you choose
 "Safeer Cinnamon" in the menu; "Restore previous look" puts everything back.
 Options: safeer-cinnamon --kontrast (opaque, stronger borders) and
 --vecji-tekst (125 % text).
EOF2
chmod 644 "$ROOT/DEBIAN/control"
# Ob odstranitvi paketa: uporabnikove nastavitve ostanejo njegove; tema, ki je ni vec,
# bi Cinnamon zamenjal s privzeto, zato uporabnika opozorimo, kako vrniti prejsnji videz.
cat > "$ROOT/DEBIAN/prerm" <<'EOF2'
#!/bin/sh
set -e
if [ "$1" = "remove" ]; then
    echo "Safeer Cinnamon: pred odstranitvijo zazenite 'safeer-cinnamon --izklopi' kot vas uporabnik,"
    echo "da se vrne vas prejsnji videz (sicer Cinnamon sam preklopi na privzeto temo)."
fi
exit 0
EOF2
chmod 755 "$ROOT/DEBIAN/prerm"
find "$ROOT" -type d -exec chmod 755 {} +
find "$ROOT/usr/share" -type f -exec chmod 644 {} +

dpkg-deb --root-owner-group --build "$ROOT" "$DIR/$DEB_PACKAGE"
echo "OK: $DEB_PACKAGE"
