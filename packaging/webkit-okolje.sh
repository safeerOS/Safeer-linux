# shellcheck shell=sh
# Okolje WebKitGTK za Safeer OS v Flatpaku (vir: packaging/safeer-os-launcher).
#
# WebKitGTK 2.54 (GNOME 50) z izrisovalnikom DMA-BUF na starejsih grafikah Intel (gen 4-7.5, gonilnik Mesa crocus)
# pusca pomnilnik: meritev 13. 10. 2026 na testnem racunalniku (Haswell HD 4600, Mesa 26.2.2, X11): spletni proces
# na 24ur.com +90 MB/s do OOM; z WEBKIT_DISABLE_DMABUF_RENDERER=1 stabilno ~230 MB. Na sistemskem WebKitu 2.52
# (Mesa 25.2) puscanja ni. Uporabnikova izrecna nastavitev (tudi =0) ima vedno prednost.
safeer_webkit_okolje() {
    [ -n "${WEBKIT_DISABLE_DMABUF_RENDERER+x}" ] && return 0
    koren="${SAFEER_SYS_KOREN:-/sys}"
    for naprava in "$koren"/class/drm/card[0-9]*/device; do
        [ "$(cat "$naprava/vendor" 2>/dev/null)" = "0x8086" ] || continue
        case "$(tr 'A-F' 'a-f' < "$naprava/device" 2>/dev/null)" in
            0x01??|0x04??|0x0a??|0x0b??|0x0c??|0x0d??|0x0f??|0x29??|0x2a??|0x2e??|0x0042|0x0046)
                export WEBKIT_DISABLE_DMABUF_RENDERER=1
                return 0 ;;
        esac
    done
    return 0
}
