#!/bin/bash
# Tece v vsebniku Linux Minta (glej preizkus.sh). Paketi so v /paketi (samo za branje); ce so v /prejsnji paketi zadnje
# objavljene izdaje, se najprej namestijo ti in novi cez nje (posodobitev).
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8

grep -rqs "packages.linuxmint.com" /etc/apt/sources.list /etc/apt/sources.list.d/ || { echo "NAPAKA: to ni Linux Mint (ni Mintovih skladisc)"; exit 1; }
echo "== Linux Mint: $(grep -rhs "packages.linuxmint.com" /etc/apt/sources.list.d/ | head -1 | awk '{print $3}')"

paket() { local p; p="$(ls /paketi/$1 2>/dev/null | head -1)"; [ -f "$p" ] || { echo "NAPAKA: manjka paket $1" >&2; exit 1; }; echo "$p"; }
razlicica() { dpkg-deb -f "$1" Version; }
BRSKALNIK="$(paket 'safeer-browser_*_all.deb')"
CONTROL="$(paket 'safeer-control_*_all.deb')"
OS="$(paket 'safeer-os_*_all.deb')"
TEMA="$(paket 'safeer-os-tema_*_all.deb')"
CINNAMON="$(paket 'safeer-cinnamon_*_all.deb')"

# Safeer OS izrise stran kot navaden uporabnik (WebKit s peskovnikom) in shrani posnetek; prazna stran ali izjema = napaka.
preveri_zagon() {
  local posnetek="$1" dnevnik="$2"
  rm -f "$posnetek"
  # Brez upravljalnika oken cel zaslon ne velja (okno ostane 200 x 200), zato velikost okna povemo sami.
  su preizkus -c "cd ~ && SAFEER_OS_OKNO=1280x800 dbus-run-session -- xvfb-run -a -s '-screen 0 1280x800x24' timeout 120 safeer-os --posnetek $posnetek" >"$dnevnik" 2>&1 \
    || { tail -30 "$dnevnik"; echo "NAPAKA: Safeer OS se ni zagnal"; exit 1; }
  python3 - "$posnetek" <<'PY'
import struct, sys
d = open(sys.argv[1], "rb").read()
assert d[:8] == b"\x89PNG\r\n\x1a\n", "posnetek ni PNG"
sirina, visina = struct.unpack(">II", d[16:24])
print("posnetek: %d x %d, %d kB" % (sirina, visina, len(d) // 1024))
# Prazna (enobarvna) stran bi bila le nekaj kB.
assert sirina >= 800 and visina >= 500 and len(d) > 20_000, "stran se ni izrisala"
PY
  if grep -q "Traceback" "$dnevnik"; then tail -30 "$dnevnik"; echo "NAPAKA: izjema ob zagonu"; exit 1; fi
}
# Linux Mint dovoli uporabniske imenske prostore (/etc/sysctl.d/20-apparmor-mint.conf), Ubuntu jih omejuje. Nastavitev
# je v jedru gostitelja, zato je tu ne spreminjamo - povemo pa, ce ni taka kot na Mintu (peskovnik se potem ne zazene).
if [ "$(cat /proc/sys/kernel/apparmor_restrict_unprivileged_userns 2>/dev/null || echo 0)" = "1" ]; then
  echo "OPOZORILO: gostitelj omejuje uporabniske imenske prostore, Linux Mint jih ne."
  echo "           Na gostitelju: sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0"
fi

echo "== 0. dvoklik (Captain/GDebi) in Safeer OS sam, na cistem sistemu"
apt-get update -q >/dev/null
# Orodja preizkusa - niso odvisnosti paketov. python3-apt: z njim paket ob dvokliku preverita Captain in GDebi.
apt-get install -y -q --no-install-recommends xvfb xauth dbus-x11 desktop-file-utils python3-apt >/dev/null
# Captain in GDebi bereta samo Depends/Pre-Depends: vsaka odvisnost mora biti v skladiscih Minta in Ubuntuja, sicer je
# gumb Namesti siv (tako je padel safeer-os 0.4.75 z odvisnostjo od safeer-control, ki ni v nobenem skladiscu).
python3 /dvojni_klik.py "$BRSKALNIK" "$CONTROL" "$OS" "$CINNAMON" || { echo "NAPAKA: paketa ni mogoce namestiti z dvoklikom"; exit 1; }
# Safeer OS SAM, brez Safeer Control: pot uporabnika, ki dvoklikne samo safeer-os. Control je le priporocen; apt
# priporocenega paketa, ki ga ni v skladiscih, ne zahteva (na suho, s priporocenimi).
apt-get install -s -q "$OS" >/tmp/os-sam-suho.log 2>&1 || { tail -30 /tmp/os-sam-suho.log; echo "NAPAKA: apt zavrne safeer-os brez safeer-control"; exit 1; }
if grep -q "^Inst safeer-control" /tmp/os-sam-suho.log; then echo "NAPAKA: safeer-control ne bi smel priti zraven"; exit 1; fi
apt-get install -y -q --no-install-recommends "$OS" >/tmp/os-sam.log 2>&1 || { tail -40 /tmp/os-sam.log; echo "NAPAKA: namestitev safeer-os brez safeer-control"; exit 1; }
[ ! -e /usr/bin/safeer-control ] || { echo "NAPAKA: safeer-control je namescen - to ni preizkus brez njega"; exit 1; }
xvfb-run -a safeer-os --version | tee /dev/stderr | grep -Fxq "Safeer OS $(razlicica "$OS")"
useradd -m preizkus
preveri_zagon /tmp/safeer-os-sam.png /tmp/zagon-sam.log
# Paket videza je odvisen od safeer-os: z dvoklikom gre sele, ko je Safeer OS namescen (tako ga opise tudi stran).
python3 /dvojni_klik.py "$TEMA" || { echo "NAPAKA: safeer-os-tema ni mogoce namestiti z dvoklikom po Safeer OS"; exit 1; }
apt-get purge -y -q safeer-os >/tmp/os-sam-odstranitev.log 2>&1 || { tail -30 /tmp/os-sam-odstranitev.log; echo "NAPAKA: odstranitev safeer-os"; exit 1; }
[ ! -e /usr/lib/safeer-os ] && [ ! -e /usr/bin/safeer-os ] || { echo "NAPAKA: po odstranitvi safeer-os je ostal"; exit 1; }

echo "== 1. namestitev (odvisnosti razresi apt iz skladisc Minta in Ubuntuja)"
# Priporocenih paketov ne namescamo: pri uporabniku so ze tam (namizje Cinnamon), tu bi jih bilo vec sto.
if ls /prejsnji/safeer-*_all.deb >/dev/null 2>&1; then
  echo "   najprej prejsnja izdaja: $(cd /prejsnji && echo safeer-*_all.deb)"
  apt-get install -y -q --no-install-recommends /prejsnji/safeer-*_all.deb >/tmp/prejsnja.log 2>&1 \
    || { tail -40 /tmp/prejsnja.log; echo "NAPAKA: namestitev prejsnje izdaje"; exit 1; }
  # Najslabsi primer za posodobitev: programi so ze tekli kot root in v mapah programov pustili svojo bajtno kodo.
  xvfb-run -a safeer --version >/dev/null
  xvfb-run -a safeer-control --version >/dev/null
  xvfb-run -a safeer-os --version >/dev/null
  echo "   nato posodobitev z apt-get install (Safeer OS: pkexec apt-get install -y, brez --allow-downgrades)"
fi
# --reinstall: tudi kadar ima prejsnja izdaja isto stevilko (veja pred novo stevilko razlicice), se namestijo novi paketi.
apt-get install -y -q --allow-downgrades --reinstall --no-install-recommends "$BRSKALNIK" "$CONTROL" "$OS" "$TEMA" "$CINNAMON" >/tmp/namestitev.log 2>&1 \
  || { tail -40 /tmp/namestitev.log; echo "NAPAKA: namestitev"; exit 1; }
for p in safeer-browser safeer-control safeer-os safeer-os-tema safeer-cinnamon; do
  dpkg-query -W -f '${Package} ${Version} ${db:Status-Abbrev}\n' "$p" | tee /dev/stderr | grep -q " ii " || { echo "NAPAKA: $p ni namescen"; exit 1; }
done
# Uporabnik v /usr/lib ne more pisati: brez bajtne kode, prevedene ob namestitvi, Python ob vsakem zagonu prevaja znova.
for mapa in /usr/lib/safeer-browser /usr/lib/safeer-control /usr/lib/safeer-os; do
  [ "$(find "$mapa" -name '*.pyc' | wc -l)" -ge "$(find "$mapa" -name '*.py' | wc -l)" ] \
    || { echo "NAPAKA: $mapa nima bajtne kode za vse module (postinst je ni prevedel)"; exit 1; }
done

echo "== 2. razlicice programov"
xvfb-run -a safeer --version | tee /dev/stderr | grep -Fxq "Safeer Browser $(razlicica "$BRSKALNIK")"
xvfb-run -a safeer-control --version | tee /dev/stderr | grep -Fxq "Safeer Control $(razlicica "$CONTROL")"
safeerctl --version | tee /dev/stderr | grep -Fxq "safeerctl $(razlicica "$CONTROL")"
xvfb-run -a safeer-os --version | tee /dev/stderr | grep -Fxq "Safeer OS $(razlicica "$OS")"

echo "== 3. zaganjalniki v meniju"
desktop-file-validate /usr/share/applications/safeer-browser.desktop /usr/share/applications/safeer-control.desktop \
  /usr/share/applications/safeer-os.desktop /usr/share/applications/safeer-os.Magnet.desktop

echo "== 4. Safeer OS se zazene in izrise stran (navaden uporabnik, WebKit s peskovnikom)"
preveri_zagon /tmp/safeer-os.png /tmp/zagon.log

echo "== 5. ukaza videza delujeta"
bash -n /usr/bin/safeer-os-tema
bash -n /usr/bin/safeer-cinnamon
test -f /usr/share/themes/Safeer-OS/gtk-3.0/gtk.css
test -f /usr/share/themes/Safeer-Cinnamon/cinnamon/cinnamon.css

echo "== 6. odstranitev ne pusti nicesar"
apt-get remove -y -q safeer-os-tema safeer-cinnamon safeer-os safeer-control safeer-browser >/tmp/odstranitev.log 2>&1 \
  || { tail -30 /tmp/odstranitev.log; echo "NAPAKA: odstranitev"; exit 1; }
for ostanek in /usr/lib/safeer-os /usr/lib/safeer-control /usr/lib/safeer-browser /usr/lib/safeer-cinnamon \
               /usr/bin/safeer /usr/bin/safeer-os /usr/bin/safeer-control /usr/bin/safeerctl /usr/bin/safeer-cinnamon \
               /usr/share/themes/Safeer-OS /usr/share/themes/Safeer-Cinnamon /usr/share/applications/safeer-os.desktop; do
  [ ! -e "$ostanek" ] || { echo "NAPAKA: po odstranitvi je ostalo $ostanek"; find "$ostanek" | head -5; exit 1; }
done
echo "== USPEH: namestitev, zagon in odstranitev na Linux Mintu"
