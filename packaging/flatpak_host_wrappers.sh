#!/usr/bin/env bash
# Safeer OS in a Flatpak: the shell controls the computer with the system's own tools (nmcli, pactl,
# resolvectl, pkexec, gsettings, systemctl ...). They are not inside the sandbox, so /app/host-bin gets
# one wrapper per tool that runs it on the host through flatpak-spawn (--talk-name=org.freedesktop.Flatpak).
# The Python code stays the same: shutil.which() finds the wrapper and subprocess runs it. A tool the
# host does not have fails with a non-zero exit code, exactly as a missing command would.
set -euo pipefail
DEST="${1:?Usage: flatpak_host_wrappers.sh /app/host-bin}"
mkdir -p "$DEST"
TOOLS="nmcli nm-connection-editor resolvectl pkexec pactl pacmd wpctl brightnessctl gsettings gdbus systemctl loginctl
       xdg-open gio xprop xdotool wmctrl sway swaymsg wf-recorder wtype notify-send cinnamon-settings cinnamon-session-quit
       cinnamon-screensaver-command gnome-screenshot nemo pgrep pkill hostnamectl timedatectl xrandr playerctl amixer
       safeer safeer-browser flatpak safeer-cinnamon nemo-desktop"
for tool in $TOOLS; do
    cat > "$DEST/$tool" << 'EOF'
#!/bin/sh
# Runs the host's tool of the same name (Safeer OS Flatpak).
# LC_ALL/LANGUAGE: Python izpis orodij razclenjuje v anglescini (LC_ALL=C) - brez tega gostitelj odgovori v svojem jeziku.
exec flatpak-spawn --host --env=DISPLAY="${DISPLAY:-}" --env=WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-}" \
    ${LC_ALL:+"--env=LC_ALL=$LC_ALL"} ${LANGUAGE:+"--env=LANGUAGE=$LANGUAGE"} "$(basename "$0")" "$@"
EOF
    chmod 755 "$DEST/$tool"
done
