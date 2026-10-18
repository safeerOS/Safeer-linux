#!/bin/bash
# Tece v vsebniku Linux Minta (glej preizkus.sh). Paketi so v /paketi (samo za branje); ce so v /prejsnji paketi zadnje
# objavljene izdaje, se najprej namestijo ti in novi cez nje (posodobitev).
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8
# Dnevniki in posnetek v svoji zacasni mapi (ne v fiksnih /tmp/...): ob ponovnem zagonu v istem vsebniku ali ob
# deljenem /tmp ne preberemo starega dnevnika ali posnetka.
ZACASNO="$(mktemp -d)"
trap 'rm -rf "$ZACASNO"' EXIT

grep -rqs "packages.linuxmint.com" /etc/apt/sources.list /etc/apt/sources.list.d/ || { echo "NAPAKA: to ni Linux Mint (ni Mintovih skladisc)"; exit 1; }
echo "== Linux Mint: $(grep -rhs "packages.linuxmint.com" /etc/apt/sources.list.d/ | head -1 | awk '{print $3}')"

paket() { local p; p="$(ls /paketi/$1 2>/dev/null | head -1)"; [ -f "$p" ] || { echo "NAPAKA: manjka paket $1" >&2; exit 1; }; echo "$p"; }
razlicica() { dpkg-deb -f "$1" Version; }
# Od 15. 10. 2026 sta paketa amd64 (nas WebKitGTK in libsoup v /usr/lib/<paket>/webkit, packaging/webkit-deb).
BRSKALNIK="$(paket 'safeer-browser_*_amd64.deb')"
# Od 12. 10. 2026 je Safeer OS en paket: Safeer Control in Safeer Cinnamon sta v njem (glej build_os_deb.sh).
OS="$(paket 'safeer-os_*_amd64.deb')"
VSEBNIK_OS="$(dpkg-deb -c "$OS" | awk '{print $6}' | sed -n 's|^\./||p')"
razlicica_v() { dpkg-deb -f "$OS" Provides | tr ',' '\n' | sed -n "s/^ *$1 (= \(.*\))\$/\1/p"; }

echo "== 1. namestitev (odvisnosti razresi apt iz skladisc Minta in Ubuntuja)"
apt-get update -q >/dev/null
# Orodja preizkusa - niso odvisnosti paketov.
apt-get install -y -q --no-install-recommends xvfb xauth dbus-x11 desktop-file-utils >/dev/null
# Priporocenih paketov ne namescamo: pri uporabniku so ze tam (namizje Cinnamon), tu bi jih bilo vec sto.
useradd -m preizkus
# Posnetek pise uporabnik preizkus (mktemp -d je root z 0700).
POSNETEK_MAPA="$ZACASNO/posnetek"
install -d -m 0700 -o preizkus "$POSNETEK_MAPA"
chmod 0711 "$ZACASNO"
POSNETEK="$POSNETEK_MAPA/safeer-os.png"
# Prejsnja izdaja ima pakete _all (do 1.0.127) ali _amd64 (z nasim WebKitom): posodobitev all -> amd64 je pot vseh
# obstojecih uporabnikov.
if ls /prejsnji/safeer-*.deb >/dev/null 2>&1; then
  echo "   najprej prejsnja izdaja: $(cd /prejsnji && echo safeer-*.deb)"
  # Paketa, ki ju je nadomestil safeer-os, morata ob posodobitvi »izginiti« (Replaces): to se zgodi samo, ce ima
  # novi paket VSE njune datoteke. Sicer bi ostala namescena in lastnika polovice datotek.
  # (Brez cevi printf | grep -q: s pipefail grep -q zapre cev, printf dobi SIGPIPE in najdena datoteka velja za manjkajoco.)
  for star in /prejsnji/safeer-control_*_all.deb /prejsnji/safeer-cinnamon_*_all.deb; do
    [ -f "$star" ] || continue
    manjka="$(dpkg-deb -c "$star" | grep -v '^d' | awk '{print $6}' | sed 's|^\./||' | while read -r d; do
      grep -qxF -- "$d" <<<"$VSEBNIK_OS" || echo "$d"; done)"
    [ -z "$manjka" ] || { echo "$manjka" | head -20; echo "NAPAKA: safeer-os nima vseh datotek paketa $(basename "$star")"; exit 1; }
  done
  apt-get install -y -q --no-install-recommends /prejsnji/safeer-*.deb >"$ZACASNO/prejsnja.log" 2>&1 \
    || { tail -40 "$ZACASNO/prejsnja.log"; echo "NAPAKA: namestitev prejsnje izdaje"; exit 1; }
  # Najslabsi primer za posodobitev: programi so ze tekli kot root in v mapah programov pustili svojo bajtno kodo.
  xvfb-run -a safeer --version >/dev/null
  xvfb-run -a safeer-control --version >/dev/null
  xvfb-run -a safeer-os --version >/dev/null
  # Uporabnik ima Safeer Cinnamon vklopljen: posodobitev mu videza ne sme izklopiti (stari paket ne sme dobiti
  # `prerm remove`, zato safeer-os nima Conflicts/Breaks, samo Replaces).
  su preizkus -c 'mkdir -p ~/.config/safeer-cinnamon && touch ~/.config/safeer-cinnamon/vklopljeno'
  echo "   nato posodobitev z ukazom, s katerim jo namesti Safeer OS (apt-get install --allow-downgrades)"
fi
# --reinstall: tudi kadar ima prejsnja izdaja isto stevilko (veja pred novo stevilko razlicice), se namestijo novi paketi.
apt-get install -y -q --allow-downgrades --reinstall --no-install-recommends "$BRSKALNIK" "$OS" >"$ZACASNO/namestitev.log" 2>&1 \
  || { tail -40 "$ZACASNO/namestitev.log"; echo "NAPAKA: namestitev"; exit 1; }
for p in safeer-browser safeer-os; do
  dpkg-query -W -f '${Package} ${Version} ${db:Status-Abbrev}\n' "$p" | tee /dev/stderr | grep -q " ii " || { echo "NAPAKA: $p ni namescen"; exit 1; }
done
for p in safeer-control safeer-cinnamon; do
  if dpkg-query -W -f '${db:Status-Abbrev}\n' "$p" 2>/dev/null | grep -q "^ii"; then
    echo "NAPAKA: stari paket $p je po posodobitvi se namescen (safeer-os bi ga moral nadomestiti)"; exit 1
  fi
done
if ls /prejsnji/safeer-cinnamon_*_all.deb >/dev/null 2>&1; then
  [ -f /home/preizkus/.config/safeer-cinnamon/vklopljeno ] || { echo "NAPAKA: posodobitev je izklopila Safeer Cinnamon"; exit 1; }
  rm -f /home/preizkus/.config/safeer-cinnamon/vklopljeno
fi
# Uporabnik v /usr/lib ne more pisati: brez bajtne kode, prevedene ob namestitvi, Python ob vsakem zagonu prevaja znova.
for mapa in /usr/lib/safeer-browser /usr/lib/safeer-control /usr/lib/safeer-os; do
  [ "$(find "$mapa" -name '*.pyc' | wc -l)" -ge "$(find "$mapa" -name '*.py' | wc -l)" ] \
    || { echo "NAPAKA: $mapa nima bajtne kode za vse module (postinst je ni prevedel)"; exit 1; }
done

for p in safeer-browser safeer-os; do
  [ "$(dpkg-query -W -f '${Architecture}' "$p")" = amd64 ] || { echo "NAPAKA: $p ni amd64 (ni nasega WebKita)"; exit 1; }
done

echo "== 1a. nas WebKitGTK in libsoup (navaden uporabnik, peskovnik bubblewrap)"
# Brez sistemskega WebKitGTK 6.0 (paketa ga ne zahtevata) in nato z njim: paketa morata teci na svojem.
webkit_preizkus() {
  for koren in /usr/lib/safeer-browser /usr/lib/safeer-os /usr/lib/safeer-control; do
    su preizkus -c "cd ~ && dbus-run-session -- xvfb-run -a timeout 120 python3 /smoke_webkit_deb.py $koren" >"$ZACASNO/webkit.log" 2>&1 \
      || { tail -40 "$ZACASNO/webkit.log"; echo "NAPAKA: nas WebKit v $koren ($1)"; exit 1; }
    grep -E '^(knjiznice|libsoup|peskovnik|gstreamer|stran AV1|::notice::dav1d|PASS)' "$ZACASNO/webkit.log"
  done
}
# Prejsnja izdaja je zahtevala gir1.2-webkit-6.0; po posodobitvi ga noben paket ne potrebuje vec in ga autoremove vzame.
apt-get autoremove -y -q >"$ZACASNO/autoremove.log" 2>&1 || { tail -20 "$ZACASNO/autoremove.log"; echo "NAPAKA: autoremove"; exit 1; }
if dpkg-query -W -f '${db:Status-Abbrev}\n' libwebkitgtk-6.0-4 2>/dev/null | grep -q '^ii'; then
  echo "   (sistemski WebKitGTK 6.0 ostaja namescen: $(apt-cache rdepends --installed libwebkitgtk-6.0-4 | tail -n +3 | tr '\n' ' '))"
fi
webkit_preizkus "brez sistemskega WebKitGTK"
apt-get install -y -q --no-install-recommends gir1.2-webkit-6.0 gir1.2-soup-3.0 >/dev/null
webkit_preizkus "s sistemskim WebKitGTK $(dpkg-query -W -f '${Version}' libwebkitgtk-6.0-4)"

echo "== 1b. odvisnosti, brez katerih Safeer Link ne najde naprav"
/usr/bin/python3 -c "import zeroconf, qrcode, cryptography" || { echo "NAPAKA: manjka python3-zeroconf/qrcode/cryptography"; exit 1; }

echo "== 1c. Node.js v paketu (nacin deb): tece kot uporabnik, ne trci s sistemskim node"
NODE=/usr/lib/safeer-os/node/bin/node
NASA="$(su preizkus -c "$NODE --version")" || { echo "NAPAKA: nas Node.js se ne zazene"; exit 1; }
echo "   nas Node.js: $NASA"
[ ! -e /usr/bin/node ] || { echo "NAPAKA: /usr/bin/node obstaja, ceprav nodejs ni namescen (paket ga ne sme prinesti)"; exit 1; }
apt-get install -y -q --no-install-recommends nodejs >"$ZACASNO/nodejs.log" 2>&1 \
  || { tail -20 "$ZACASNO/nodejs.log"; echo "NAPAKA: namestitev sistemskega nodejs ob safeer-os"; exit 1; }
case "$(dpkg -S /usr/bin/node 2>/dev/null)" in nodejs:*) ;; *) echo "NAPAKA: /usr/bin/node ni iz paketa nodejs"; exit 1 ;; esac
echo "   sistemski node: $(/usr/bin/node --version) (paket nodejs)"
[ "$(su preizkus -c "$NODE --version")" = "$NASA" ] || { echo "NAPAKA: sistemski nodejs je spremenil nas Node.js"; exit 1; }
su preizkus -c "python3 -c \"import sys; sys.path.insert(0, '/usr/lib/safeer-os'); from core import node_izvajalnik as n; assert n.pot() == '$NODE', n.pot()\"" \
  || { echo "NAPAKA: programi Safeer OS ne najdejo nasega Node.js"; exit 1; }
apt-get purge -y -q nodejs >/dev/null 2>&1 || true

echo "== 1d. profili AppArmor (Ubuntu 24.04+: peskovnik WebKita) se prevedejo z apparmor_parser Minta"
AA="$ZACASNO/apparmor"
mkdir -p "$AA/koren"
( cd "$AA" && apt-get download apparmor >/dev/null 2>&1 ) || { echo "NAPAKA: paketa apparmor ni mogoce prenesti"; exit 1; }
dpkg-deb -x "$AA"/apparmor_*.deb "$AA/koren"
PARSER=""
for p in "$AA/koren/sbin/apparmor_parser" "$AA/koren/usr/sbin/apparmor_parser"; do if [ -x "$p" ]; then PARSER="$p"; break; fi; done
[ -n "$PARSER" ] || { echo "NAPAKA: v paketu apparmor ni apparmor_parser"; exit 1; }
for profil in safeer-os safeer-control safeer-browser; do
  [ -f "/etc/apparmor.d/$profil" ] || { echo "NAPAKA: ni profila /etc/apparmor.d/$profil"; exit 1; }
  "$PARSER" --config-file="$AA/koren/etc/apparmor/parser.conf" --base="$AA/koren/etc/apparmor.d" -I "$AA/koren/etc/apparmor.d" \
    -Q -K -T -S "/etc/apparmor.d/$profil" >/dev/null 2>"$AA/napaka" \
    || { cat "$AA/napaka"; echo "NAPAKA: profil $profil se ne prevede"; exit 1; }
  echo "   $profil: v redu"
done

echo "== 1e. vticnik Qt xcb lupine QML najde vse knjiznice (paket brez priporocenih)"
bash /preveri_qxcb.sh /usr/lib/safeer-os/vendor || { echo "NAPAKA: PySide6 xcb potrebuje knjiznico, ki je paket ne namesti"; exit 1; }

echo "== 2. razlicice programov"
xvfb-run -a safeer --version | tee /dev/stderr | grep -Fxq "Safeer Browser $(razlicica "$BRSKALNIK")"
xvfb-run -a safeer-control --version | tee /dev/stderr | grep -Fxq "Safeer Control $(razlicica_v safeer-control)"
safeerctl --version | tee /dev/stderr | grep -Fxq "safeerctl $(razlicica_v safeer-control)"
xvfb-run -a safeer-os --version | tee /dev/stderr | grep -Fxq "Safeer OS $(razlicica "$OS")"

echo "== 3. zaganjalniki v meniju"
desktop-file-validate /usr/share/applications/safeer-browser.desktop /usr/share/applications/safeer-control.desktop \
  /usr/share/applications/safeer-os.desktop /usr/share/applications/safeer-os.Magnet.desktop \
  /usr/share/applications/safeer-os.Player.desktop

echo "== 4. Safeer OS se zazene in izrise stran (navaden uporabnik, WebKit s peskovnikom)"
# Linux Mint dovoli uporabniske imenske prostore (/etc/sysctl.d/20-apparmor-mint.conf), Ubuntu jih omejuje. Nastavitev
# je v jedru gostitelja, zato je tu ne spreminjamo - povemo pa, ce ni taka kot na Mintu (peskovnik se potem ne zazene).
if [ "$(cat /proc/sys/kernel/apparmor_restrict_unprivileged_userns 2>/dev/null || echo 0)" = "1" ]; then
  echo "OPOZORILO: gostitelj omejuje uporabniske imenske prostore, Linux Mint jih ne."
  echo "           Na gostitelju: sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0"
fi
# Brez upravljalnika oken cel zaslon ne velja (okno ostane 200 x 200), zato velikost okna povemo sami.
su preizkus -c 'cd ~ && SAFEER_OS_OKNO=1280x800 dbus-run-session -- xvfb-run -a -s "-screen 0 1280x800x24" timeout 120 safeer-os --posnetek '"$POSNETEK" >"$ZACASNO/zagon.log" 2>&1 \
  || { tail -30 "$ZACASNO/zagon.log"; echo "NAPAKA: Safeer OS se ni zagnal"; exit 1; }
python3 - "$POSNETEK" <<'PY'
import struct, sys
with open(sys.argv[1], "rb") as f:
    d = f.read()
assert d[:8] == b"\x89PNG\r\n\x1a\n", "posnetek ni PNG"
sirina, visina = struct.unpack(">II", d[16:24])
print("posnetek: %d x %d, %d kB" % (sirina, visina, len(d) // 1024))
# Prazna (enobarvna) stran bi bila le nekaj kB.
assert sirina >= 800 and visina >= 500 and len(d) > 20_000, "stran se ni izrisala"
PY
if grep -q "Traceback" "$ZACASNO/zagon.log"; then tail -30 "$ZACASNO/zagon.log"; echo "NAPAKA: izjema ob zagonu"; exit 1; fi

echo "== 5. ukaza videza delujeta"
bash -n /usr/bin/safeer-cinnamon
test -f /usr/share/themes/Safeer-Cinnamon/cinnamon/cinnamon.css
safeer-cinnamon --help >/dev/null

echo "== 6. odstranitev ne pusti nicesar"
# safeer-os-tema (staro celozaslonsko namizje) ni vec v izdaji; ce ga je namestila prejsnja izdaja, gre tudi on.
dpkg-query -W -f '${db:Status-Abbrev}\n' safeer-os-tema 2>/dev/null | grep -q "^ii" && TEMA_STARA=safeer-os-tema || TEMA_STARA=""
apt-get remove -y -q $TEMA_STARA safeer-os safeer-browser >"$ZACASNO/odstranitev.log" 2>&1 \
  || { tail -30 "$ZACASNO/odstranitev.log"; echo "NAPAKA: odstranitev"; exit 1; }
for ostanek in /usr/lib/safeer-os /usr/lib/safeer-control /usr/lib/safeer-browser /usr/lib/safeer-cinnamon \
               /usr/bin/safeer /usr/bin/safeer-os /usr/bin/safeer-control /usr/bin/safeerctl /usr/bin/safeer-cinnamon \
               /usr/share/themes/Safeer-Cinnamon /usr/share/applications/safeer-os.desktop; do
  [ ! -e "$ostanek" ] || { echo "NAPAKA: po odstranitvi je ostalo $ostanek"; find "$ostanek" | head -5; exit 1; }
done
dpkg-query -W -f '${db:Status-Abbrev}\n' libwebkitgtk-6.0-4 | grep -q '^ii' || { echo "NAPAKA: odstranitev je vzela sistemski WebKitGTK"; exit 1; }
echo "== USPEH: namestitev, zagon in odstranitev na Linux Mintu"
