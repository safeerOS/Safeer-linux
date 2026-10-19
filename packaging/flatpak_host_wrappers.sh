#!/usr/bin/env bash
# Safeer OS in a Flatpak: the shell controls the computer with the system's own tools (nmcli, pactl,
# resolvectl, pkexec, gsettings, systemctl ...). They are not inside the sandbox, so /app/host-bin gets
# one wrapper per tool that runs it on the host through flatpak-spawn (--talk-name=org.freedesktop.Flatpak).
# The Python code stays the same: shutil.which() finds the wrapper and subprocess runs it. A tool the
# host does not have fails with a non-zero exit code, exactly as a missing command would.
# 14. 10. 2026: xdg-mime (privzeti programi), udisksctl (izvrzi USB), dpkg-query/apt-cache (ponudniki programov),
# avahi-browse (naprave v omrezju) in dconf (dock) v peskovniku Flatpaka manjkajo - preverjeno na testnem PC.
set -euo pipefail
DEST="${1:?Usage: flatpak_host_wrappers.sh /app/host-bin}"
mkdir -p "$DEST"
TOOLS="nmcli nm-connection-editor resolvectl pkexec pactl pacmd wpctl brightnessctl gsettings gdbus systemctl loginctl
       xdg-open gio xprop xdotool wmctrl sway swaymsg wf-recorder wtype notify-send cinnamon-settings cinnamon-session-quit
       cinnamon-screensaver-command gnome-screenshot gnome-control-center nemo pgrep pkill hostnamectl timedatectl xrandr playerctl amixer
       safeer safeer-browser flatpak safeer-cinnamon nemo-desktop
       xdg-mime udisksctl dpkg-query apt-cache avahi-browse dconf soffice libreoffice magick convert"
for tool in $TOOLS; do
    cat > "$DEST/$tool" << 'EOF'
#!/bin/sh
# Runs the host's tool of the same name (Safeer OS Flatpak).
# LC_ALL/LANGUAGE: Python izpis orodij razclenjuje v anglescini (LC_ALL=C) - brez tega gostitelj odgovori v svojem jeziku.
# Zaslon samo, ce ga peskovnik ima (core/gostitelj.env_zaslona): prazen DISPLAY bi na Waylandu prepisal gostiteljevega.
# Orodje na gostitelju samo iz sistemskih map (core/root_ukaz.SISTEMSKE_MAPE), ne po uporabnikovem PATH (~/.local/bin
# pred /usr/bin): safeer-cinnamon --od-vklopa, Nastavitve, systemctl ... lahko vprasajo za geslo, podtaknjen program bi
# ga dobil (koncni neodvisni pregled, 19. 10. 2026). Orodja ni: koda 127, kot pri manjkajocem ukazu.
exec flatpak-spawn --host ${DISPLAY:+"--env=DISPLAY=$DISPLAY"} ${WAYLAND_DISPLAY:+"--env=WAYLAND_DISPLAY=$WAYLAND_DISPLAY"} \
    ${LC_ALL:+"--env=LC_ALL=$LC_ALL"} ${LANGUAGE:+"--env=LANGUAGE=$LANGUAGE"} \
    /bin/sh -c 'for d in /usr/local/sbin /usr/local/bin /usr/sbin /usr/bin /sbin /bin /snap/bin; do [ -f "$d/$0" ] && [ -x "$d/$0" ] && exec "$d/$0" "$@"; done; echo "$0: ni v sistemskih mapah" >&2; exit 127' "$(basename "$0")" "$@"
EOF
    chmod 755 "$DEST/$tool"
done
# pkexec na gostitelju vedno /usr/bin/pkexec (core/root_ukaz.py).
sed -i 's|^    /bin/sh -c .*$|    /usr/bin/pkexec "$@"|' "$DEST/pkexec"
grep -q '/usr/bin/pkexec "$@"' "$DEST/pkexec"
