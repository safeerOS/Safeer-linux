#!/bin/bash
# Preizkusno okolje za Scit: »usmerjevalnik« (dnsmasq: DHCP + DNS z dnevnikom poizvedb) in »racunalnik«
# (systemd + systemd-resolved + NetworkManager, kot namizni Linux Mint 22). Oba sta vsebnika Docker v svojem
# omrezju; omrezja gostitelja se nic ne dotakne. Navodila: README.md.
#   lab.sh zgradi        zgradi sliki (enkrat)
#   lab.sh gor           postavi omrezje in oba vsebnika; NetworkManager dobi naslov, DNS in domeno »lan« po DHCP
#   lab.sh dol           vse odstrani
#   lab.sh gonilnik      (znova) zazene gonilnik Scita v »racunalniku« - kot nov zagon Safeer OS
#   lab.sh u UKAZ        ukaz gonilniku: vklop, izklop, zagon, koncaj, dovoli IME, blokiraj IME, premor N, stanje, izhod
#   lab.sh dns           kaj ima systemd-resolved za eth0 + kaj berejo programi (resolv.conf)
#   lab.sh q IME         razresi ime kot navaden program (getent) in pove, ali je poizvedba prisla do usmerjevalnika
#   lab.sh preizkus      cel samodejni preizkus (preizkus.sh)
set -u
LAB="$(cd "$(dirname "$0")" && pwd)"
KODA="${KODA:-$(cd "$LAB/../.." && pwd)}"
case "${1:-}" in
  zgradi)
    docker build -q -t safeer-scit-lab -f "$LAB/Dockerfile" "$LAB" && docker build -q -t safeer-scit-usm -f "$LAB/Dockerfile.usm" "$LAB" ;;
  gor)
    docker network inspect scit95 >/dev/null 2>&1 || docker network create --subnet 172.31.95.0/24 --gateway 172.31.95.1 scit95 >/dev/null
    docker rm -f scit-usm scit-odj >/dev/null 2>&1
    # Docker v omrezjih po meri posreduje DNS streznikom gostitelja; ce jih gostitelj nima, pomaga --dns.
    docker run -d --name scit-usm --hostname usmerjevalnik --network scit95 --ip 172.31.95.2 --cap-add NET_ADMIN --cap-add NET_RAW \
      --dns "${DNS1:-1.1.1.1}" --dns "${DNS2:-9.9.9.9}" safeer-scit-usm \
      dnsmasq -k --log-queries --log-dhcp --log-facility=/var/log/dnsmasq.log \
        --dhcp-range=172.31.95.50,172.31.95.99,255.255.255.0,1h --dhcp-option=3,172.31.95.1 --dhcp-option=6,172.31.95.2 \
        --domain=lan --dhcp-authoritative --no-hosts --cache-size=0 --address=/nas.lan/172.31.95.77 \
        --address=/preizkus.example/172.31.95.66 --address=/dovoljeno.example/172.31.95.67 \
        --address=/nevarno.example/172.31.95.68 >/dev/null
    docker run -d --name scit-odj --hostname scit-odj --privileged --cgroupns=private --tmpfs /run --tmpfs /run/lock --tmpfs /tmp \
      --network scit95 --ip 172.31.95.10 -v "$KODA":/repo:ro -e PRAVI_SEZNAMI="${PRAVI_SEZNAMI:-0}" safeer-scit-lab >/dev/null
    sleep 6
    # /etc/resolv.conf kot na namizju: posrednik systemd-resolved (Docker tja priklopi svojo datoteko).
    docker exec scit-odj bash -c 'umount /etc/resolv.conf 2>/dev/null; rm -f /etc/resolv.conf; ln -s ../run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
      systemctl is-system-running --wait >/dev/null 2>&1; systemctl restart systemd-resolved NetworkManager; sleep 3
      nmcli con add type ethernet ifname eth0 con-name lab ipv4.method auto ipv6.method disabled autoconnect yes >/dev/null
      nmcli con up lab >/dev/null; sleep 2; nmcli -t -f DEVICE,TYPE,STATE,CONNECTION device | head -1'
    # Gonilnik tece kot root (polkit ga pusti brez pravila); znak »pravilo je namesceno« zato nastavimo rocno.
    docker exec scit-odj bash -c 'mkdir -p /var/tmp/scit-podatki /root/.config/safeer-os && echo lab > /root/.config/safeer-os/scit-pravilo'
    ;;
  dol)
    docker rm -f scit-usm scit-odj >/dev/null 2>&1; docker network rm scit95 >/dev/null 2>&1; echo odstranjeno ;;
  gonilnik)
    docker exec -e PRAVI_SEZNAMI="${PRAVI_SEZNAMI:-0}" scit-odj bash -c '[ -f /tmp/gonilnik.pid ] && kill "$(cat /tmp/gonilnik.pid)" 2>/dev/null
      rm -f /tmp/scit.cmd; : > /tmp/scit.log
      (setsid nohup python3 /repo/tools/scit_lab/lab_scit.py /repo >/tmp/gonilnik.log 2>&1 & echo $! > /tmp/gonilnik.pid)
      for i in $(seq 1 40); do [ -s /tmp/scit.log ] && break; sleep 0.25; done; tail -1 /tmp/scit.log; tail -3 /tmp/gonilnik.log' ;;
  u)
    shift
    docker exec scit-odj bash -c 'n=$(wc -l < /tmp/scit.log); echo "$1" > /tmp/scit.cmd
      for i in $(seq 1 100); do [ "$(wc -l < /tmp/scit.log)" -gt "$n" ] && break; sleep 0.3; done; tail -1 /tmp/scit.log' _ "$*" ;;
  dns)
    docker exec scit-odj bash -c 'resolvectl status eth0 2>&1 | grep -vE "^$"; echo "--- /etc/resolv.conf (programi):"; grep -v "^#" /etc/resolv.conf | grep -v "^$"
      echo "--- /run/systemd/resolve/resolv.conf (Docker ipd.):"; grep -v "^#" /run/systemd/resolve/resolv.conf | grep -v "^$"' ;;
  q)
    docker exec scit-usm sh -c ': > /var/log/dnsmasq.log'
    docker exec scit-odj bash -c 'z=$(date +%s%N); r=$(timeout 12 getent ahostsv4 "$1" | head -1); echo "$1 -> ${r:-NI ODGOVORA} ($(( ($(date +%s%N)-z)/1000000 )) ms)"' _ "$2"
    docker exec scit-usm sh -c 'echo "   do usmerjevalnika: $(grep -c "query\[A\] $1" /var/log/dnsmasq.log)"' _ "$2" ;;
  preizkus)
    exec bash "$LAB/preizkus.sh" ;;
  *) sed -n '2,13p' "$0" ;;
esac
