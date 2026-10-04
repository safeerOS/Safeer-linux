#!/bin/bash
# Samodejni preizkus Scita na pravem systemd-resolved + NetworkManager (glej README.md). Brez interneta:
# vsa imena pozna »usmerjevalnik« (preizkus.example = blokirani oglasi, nevarno.example = blokirana lazna stran,
# dovoljeno.example, nas.lan).
set -u
cd "$(dirname "$0")"
L=./lab.sh
napake=0
ok()    { printf '  ok      %s\n' "$1"; }
slabo() { printf '  NAPAKA  %s\n          dobljeno: »%s«, pricakovano: »%s«\n' "$1" "$2" "$3"; napake=$((napake + 1)); }
je()    { if [[ "$2" =~ $3 ]]; then ok "$1"; else slabo "$1" "$2" "$3"; fi; }      # je OPIS DEJANSKO VZOREC
dns()      { docker exec scit-odj resolvectl dns eth0 | sed 's/^[^:]*: *//'; }
domene()   { docker exec scit-odj resolvectl domain eth0 | sed 's/^[^:]*: *//'; }
trenutni() { docker exec scit-odj resolvectl status eth0 | sed -n 's/^ *Current DNS Server: *//p'; }
ime()      { docker exec scit-odj bash -c 'timeout 12 getent ahostsv4 "$1" | head -1 | cut -d" " -f1' _ "$1"; }
sveze()    { docker exec scit-odj resolvectl flush-caches; }
u()        { $L u "$*" >/dev/null; }
polje()    { $L u stanje | python3 -c 'import json,sys; print(json.dumps(json.loads(sys.stdin.read())["izid"].get(sys.argv[1])))' "$1"; }
BLOK=oglasi.preizkus.example      # usmerjevalnik bi odgovoril 172.31.95.66
PROSTO=www.dovoljeno.example      # 172.31.95.67
NM='^172\.31\.95\.2$'
NAS='^127\.0\.0\.1:535[4-7] 172\.31\.95\.2$'

echo "== postavljam okolje"
$L gor >/dev/null
je "NetworkManager je vmesniku dal streznik usmerjevalnika" "$(dns)" "$NM"
je "iskalna domena iz DHCP" "$(domene)" '^lan$'
je "programi sprasujejo systemd-resolved" "$(docker exec scit-odj grep -c '^nameserver 127.0.0.53' /etc/resolv.conf)" '^1$'
$L gonilnik >/dev/null

echo "== vklop"
u vklop
je "nas razresevalnik je prvi, usmerjevalnik rezerva" "$(dns)" "$NAS"
je "iskalna domena ostane" "$(domene)" '^lan$'
je "blokirana domena se ne razresi" "$(ime $BLOK)" '^$'
je "resolved res sprasuje nas (ne rezerve)" "$(trenutni)" '^127\.0\.0\.1:535[4-7]$'
je "dovoljeno ime se razresi" "$(ime $PROSTO)" '^172\.31\.95\.67$'
je "kratko domace ime (iskalna domena) dela" "$(ime nas)" '^172\.31\.95\.77$'
je "stevec blokiranih" "$(polje blokiranih)" '^[1-9]'
je "Docker ipd. imajo v resolv.conf uporaben streznik" "$(docker exec scit-odj grep -c '^nameserver 172.31.95.2' /run/systemd/resolve/resolv.conf)" '^1$'

echo "== izjema in premor"
u dovoli $BLOK
je "dovoljena domena se razresi takoj" "$(ime $BLOK)" '^172\.31\.95\.66$'
je "njena poddomena tudi" "$(ime cdn.$BLOK)" '^172\.31\.95\.66$'
je "druge blokirane ostanejo blokirane" "$(ime drugo.preizkus.example)" '^$'
u blokiraj $BLOK
je "»Blokiraj spet« velja takoj" "$(ime $BLOK)" '^$'
u premor 15
je "med premorom oglasi in sledilci niso blokirani" "$(ime $BLOK)" '^172\.31\.95\.66$'
je "nevarna stran ostane blokirana tudi med premorom" "$(ime prijava.nevarno.example)" '^$'
u premor 0
je "»Nadaljuj zdaj« velja takoj" "$(ime $BLOK)" '^$'
u premor 0.05
sleep 5
je "premor se konca sam" "$(ime $BLOK)" '^$'

echo "== izklop"
u izklop
je "vmesnik ima spet streznik NetworkManagerja" "$(dns)" "$NM"
je "iskalna domena ostane" "$(domene)" '^lan$'
sveze
je "imena se razresujejo" "$(ime $PROSTO)" '^172\.31\.95\.67$'
je "kratko domace ime dela" "$(ime nas)" '^172\.31\.95\.77$'
je "nic vec ni blokirano" "$(ime $BLOK)" '^172\.31\.95\.66$'

echo "== izhod iz Safeer OS z vklopljenim Scitom"
u vklop
je "vklopljen" "$(dns)" "$NAS"
u koncaj
je "po izhodu ima vmesnik streznik NetworkManagerja" "$(dns)" "$NM"
sveze
je "imena se razresujejo" "$(ime $PROSTO)" '^172\.31\.95\.67$'

echo "== nov zagon (Scit je v nastavitvah vklopljen)"
$L gonilnik >/dev/null
u zagon
je "Scit se ob zagonu vklopi sam" "$(dns)" "$NAS"
je "in blokira" "$(ime $BLOK)" '^$'

echo "== sesutje (brez pospravljanja)"
u izhod
sleep 1
sveze
je "DNS dela naprej prek rezerve" "$(ime $PROSTO)" '^172\.31\.95\.67$'
$L gonilnik >/dev/null
u zagon
je "po ponovnem zagonu spet blokira" "$(ime $BLOK)" '^$'
je "resolved spet sprasuje nas" "$(trenutni)" '^127\.0\.0\.1:535[4-7]$'

echo "== menjava omrezja (NetworkManager poslje svoje streznike)"
docker exec scit-odj bash -c 'nmcli con down lab >/dev/null; nmcli con up lab >/dev/null'
sleep 8
je "straza v nekaj sekundah vrne nas razresevalnik" "$(dns)" "$NAS"
je "in blokira" "$(ime $BLOK)" '^$'

echo "== ostanki starejsih razlicic"
u izhod
docker exec scit-odj bash -c 'resolvectl domain eth0 "~."'
$L gonilnik >/dev/null
u zagon
je "usmerjevalna domena »~.« stare razlicice je zamenjana z iskalno" "$(domene)" '^lan$'
u izklop
u izhod
docker exec scit-odj resolvectl revert eth0
je "(stari izklop pusti vmesnik brez streznikov)" "$(dns)" '^$'
$L gonilnik >/dev/null
u zagon
je "izklopljen Scit ob zagonu vrne streznik NetworkManagerja" "$(dns)" "$NM"
je "in iskalno domeno" "$(domene)" '^lan$'
sveze
je "imena se razresujejo" "$(ime $PROSTO)" '^172\.31\.95\.67$'

echo "== racunalnik z lastnim streznikom DNS (programi ne sprasujejo systemd-resolved)"
u izhod
docker exec scit-odj bash -c 'rm /etc/resolv.conf; printf "search lan\n" > /etc/resolv.conf'
$L gonilnik >/dev/null
je "Scit pove, zakaj ni na voljo" "$(polje razlog)" '^"lastni_dns"$'
u vklop
je "vklop zavrne" "$(polje napaka)" '^"lastni_dns"$'
je "in se DNS ne dotakne" "$(dns)" "$NM"
docker exec scit-odj bash -c 'rm /etc/resolv.conf; ln -s ../run/systemd/resolve/stub-resolv.conf /etc/resolv.conf'

echo
if [ "$napake" -eq 0 ]; then echo "VSE V REDU"; else echo "NAPAK: $napake"; fi
[ "${PUSTI:-0}" = 1 ] || $L dol >/dev/null
exit "$napake"
