#!/usr/bin/env bash
# Smoke preizkus namescenega paketa safeer-player: okno Safeer Player se res odpre in po odprtju ne pade.
# Tece pod xvfb-run in dbus-run-session (CI, linux-packages.yml). safeer_os.py nima vidne zastavice --preveri za
# Player, zato je enakovredno: iscemo vidno okno razreda safeer-os.Player (StartupWMClass v safeer-player.desktop).
# Uporaba: bash packaging/smoke_player.sh [DNEVNIK]
set -euo pipefail
CAS="${SAFEER_SMOKE_CAS:-180}"
DNEVNIK="${1:-player-smoke.log}"
# setsid: Player dobi svojo skupino procesov, da na koncu ustavimo tudi podprocese (WebKit, Control v istem procesu).
setsid safeer-player >"$DNEVNIK" 2>&1 &
PID=$!
pospravi() { kill -TERM -- "-$PID" 2>/dev/null || true; sleep 2; kill -KILL -- "-$PID" 2>/dev/null || true; }
trap pospravi EXIT
OKNO=""
for _ in $(seq "$CAS"); do
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "::error::safeer-player se je koncal, preden se je odprlo okno"; cat "$DNEVNIK"; exit 1
    fi
    # Razred ali ime primerka: GTK in Qt ga na X11 zapiseta razlicno, oba sta lahko safeer-os.Player.
    OKNO="$(xdotool search --onlyvisible --class '^safeer-os\.Player$' 2>/dev/null | head -n1 || true)"
    [ -n "$OKNO" ] || OKNO="$(xdotool search --onlyvisible --classname '^safeer-os\.Player$' 2>/dev/null | head -n1 || true)"
    [ -z "$OKNO" ] || break
    sleep 1
done
if [ -z "$OKNO" ]; then
    echo "::error::okno Safeer Player (safeer-os.Player) se ni odprlo v ${CAS} s"; cat "$DNEVNIK"; exit 1
fi
echo "okno Safeer Player: $OKNO »$(xdotool getwindowname "$OKNO" 2>/dev/null || true)«"
# Okno, ki se takoj zapre (napaka pri nalaganju Medijskega centra), ni uspeh.
sleep 5
kill -0 "$PID" 2>/dev/null || { echo "::error::safeer-player je po odprtju okna padel"; cat "$DNEVNIK"; exit 1; }
echo "Safeer Player OK"
