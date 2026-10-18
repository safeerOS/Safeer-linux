#!/usr/bin/env bash
# Lupina QML Safeer OS (PySide6 iz paketa .deb) na X11 tece prek vticnika Qt xcb. Ce mu manjka sistemska knjiznica
# (libxcb-*, libxkbcommon-x11 ...), Qt okna sploh ne odpre (»Could not load the Qt platform plugin "xcb"«). Preverimo
# v najmanjsi namestitvi (CI: vsebnik ubuntu:24.04 in slike Linux Minta, apt --no-install-recommends), da ldd vticnika
# in integracij GL ne najde nobene manjkajoce knjiznice - odvisnosti paketa (build_os_deb.sh, Depends) so popolne.
#   preveri_qxcb.sh [MAPA_VENDOR]      privzeto /usr/lib/safeer-os/vendor
set -euo pipefail
QT="${1:-/usr/lib/safeer-os/vendor}/PySide6/Qt"
shopt -s nullglob
vticniki=("$QT/plugins/platforms/libqxcb.so" "$QT"/plugins/xcbglintegrations/*.so)
napaka=0
for so in "${vticniki[@]}"; do
    if [ ! -f "$so" ]; then
        echo "NAPAKA: ni vticnika $so"
        napaka=1
        continue
    fi
    izpis="$(ldd "$so" 2>&1)" || { echo "NAPAKA: ldd $so"; echo "$izpis"; napaka=1; continue; }
    manjka="$(printf '%s\n' "$izpis" | grep -F 'not found' || true)"
    if [ -n "$manjka" ]; then
        echo "NAPAKA: $so potrebuje knjiznice, ki jih paket ne namesti:"
        printf '%s\n' "$manjka"
        napaka=1
    else
        echo "v redu: ${so#"$QT"/} ($(printf '%s\n' "$izpis" | grep -c '=> /') knjiznic)"
    fi
done
[ "${#vticniki[@]}" -ge 2 ] || { echo "NAPAKA: ni integracij GL za xcb v $QT/plugins/xcbglintegrations"; napaka=1; }
exit "$napaka"
