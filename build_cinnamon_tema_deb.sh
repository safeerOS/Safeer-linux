#!/usr/bin/env bash
# ==============================================================================
# Safeer Cinnamon — .deb: modra polprosojna tema za Linux Mint Cinnamon (po CBlue),
# ozadja Safeer, tema za dock Plank, okno z izbiro postavitve in ukaz safeer-cinnamon
# (postavitve videz/dock/delovna, izklop, kontrast, tekst).
# Loceno od safeer-os-tema: ta paket ne zazene Safeer OS in ne spremeni nicesar, dokler
# uporabnik v meniju ne odpre "Safeer Cinnamon" in ne pritisne Vklopi.
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

# Odvisnosti: okno z izbiro je v GTK 3 (python3-gi je del vsakega Cinnamona), dock in njegove nastavitve sta
# majhna (Plank ~0,5 MB) in morata delovati tudi, ko paket namesti GDebi, ki priporocenih paketov ne namesti.
# Ikone Papirus (200 MB) ostanejo priporocene: brez njih tema uporabi Mintove modre ikone.
cat > "$ROOT/DEBIAN/control" <<EOF2
Package: safeer-cinnamon
Version: ${VERSION}
Section: x11
Priority: optional
Architecture: all
Depends: mint-themes, libglib2.0-bin, python3, python3-gi, gir1.2-gtk-3.0, plank, dconf-cli
Recommends: cinnamon, papirus-icon-theme, safeer-os
Suggests: plymouth, slick-greeter
Maintainer: Safeer <info@safeer.si>
Homepage: https://safeer.si/os/
Description: Safeer Cinnamon - a calm blue desktop look for Linux Mint
 A semi-transparent dark blue theme for Cinnamon, GTK 3/4 and window borders
 (derived from CBlue, built on Mint-Y-Dark-Blue), Safeer wallpapers and a
 matching Plank dock. Nothing changes until you open "Safeer Cinnamon" in the
 menu and choose how much of it you want: the look only (your panel, windows
 and desktop icons stay where they are), the look with a dock, or the Safeer
 workspace. "Restore previous look" puts everything back.
 Options: safeer-cinnamon --kontrast (opaque, stronger borders, in the shell
 and in programs), --vecji-tekst [125|150] and --od-vklopa (the Safeer look on
 the boot and login screen too; asks for the administrator password and
 --od-vklopa-izklopi restores what was there before).
EOF2
chmod 644 "$ROOT/DEBIAN/control"
# Ob odstranitvi paketa: tema, ki je ni vec, bi Cinnamon zamenjal s privzeto, pult, dock in ozadje pa bi ostali
# spremenjeni. Zato vsakemu uporabniku, ki ima Safeer Cinnamon vklopljen, vrnemo njegov prejsnji videz, dokler
# ukaz in tema se obstajata (prijavljenemu v njegovi seji, ostalim v zacasni seji D-Bus).
cat > "$ROOT/DEBIAN/prerm" <<'EOF2'
#!/bin/sh
set -e
if [ "$1" = "remove" ]; then
    getent passwd | awk -F: '$3 >= 1000 && $3 < 60000 { print $1 ":" $3 ":" $6 }' | while IFS=: read -r ime uid dom; do
        [ -f "$dom/.config/safeer-cinnamon/vklopljeno" ] || continue
        if [ -S "/run/user/$uid/bus" ]; then
            zaslon=":0"
            pid="$(pgrep -u "$uid" -x cinnamon 2>/dev/null | head -n1)" || true
            if [ -n "$pid" ] && [ -r "/proc/$pid/environ" ]; then
                z="$(tr '\0' '\n' < "/proc/$pid/environ" | sed -n 's/^DISPLAY=//p' | head -n1)" || true
                [ -n "$z" ] && zaslon="$z"
            fi
            timeout 60 runuser -u "$ime" -- env HOME="$dom" XDG_RUNTIME_DIR="/run/user/$uid" \
                DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$uid/bus" DISPLAY="$zaslon" \
                SAFEER_CINNAMON_BREZ_SISTEMA=1 /usr/bin/safeer-cinnamon --izklopi >/dev/null 2>&1 || true
        elif command -v dbus-run-session >/dev/null 2>&1; then
            timeout 60 runuser -u "$ime" -- env HOME="$dom" SAFEER_CINNAMON_BREZ_SISTEMA=1 \
                dbus-run-session -- /usr/bin/safeer-cinnamon --izklopi >/dev/null 2>&1 || true
        fi
        if [ -f "$dom/.config/safeer-cinnamon/vklopljeno" ]; then
            echo "Safeer Cinnamon: uporabniku $ime prejsnjega videza ni bilo mogoce vrniti samodejno."
        else
            echo "Safeer Cinnamon: uporabniku $ime je vrnjen prejsnji videz."
        fi
    done
    # Zagonski in prijavni zaslon sta sistemska: vrnemo ju, preden izginejo datoteke teme.
    if [ -x /usr/lib/safeer-cinnamon/od-vklopa ]; then /usr/lib/safeer-cinnamon/od-vklopa izklopi || true; fi
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
