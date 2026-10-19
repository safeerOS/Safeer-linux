// Vnos menija v slogu namizja (Datoteke, Programi, iskanje): barve iz palete, onemogocen vnos je medel, skrit vnos ne
// zaseda prostora. Prej je imela vsaka plosca svojo kopijo (pregled enakosti z delovno povrsino, 15. 10. 2026).
import QtQuick
import QtQuick.Controls.Basic

MenuItem {
    id: vnos
    property bool prelomi: false        // opis (npr. kje igra tece) se prelomi namesto »…«
    height: visible ? implicitHeight : 0
    contentItem: Text {
        text: vnos.text; color: vnos.enabled ? koren.paleta.besedilo : koren.paleta.medlo
        font.pixelSize: koren.px(13); leftPadding: 6; rightPadding: vnos.checkable ? koren.px(22) : 0
        elide: vnos.prelomi ? Text.ElideNone : Text.ElideRight; wrapMode: vnos.prelomi ? Text.WordWrap : Text.NoWrap
    }
    // Vnos z izbiro (npr. »Zlozena iskalna lupa«): kljukica desno v barvi palete. Privzeti indikator sloga Basic je bil
    // temno siv na temnem meniju in pod prvimi crkami besedila - stanje se ni videlo (pregled 19. 10. 2026).
    indicator: Text {
        visible: vnos.checkable && vnos.checked; text: "✓"; color: koren.paleta.poudarek; font.pixelSize: koren.px(14)
        x: vnos.width - width - 10; anchors.verticalCenter: parent ? parent.verticalCenter : undefined
    }
    arrow: Text {
        visible: !!vnos.subMenu; text: "›"; color: koren.paleta.medlo; font.pixelSize: koren.px(15)
        x: vnos.width - width - 10; anchors.verticalCenter: parent ? parent.verticalCenter : undefined
    }
    background: Rectangle { radius: 8; color: vnos.highlighted && vnos.enabled ? koren.poudarekA(0.22) : "transparent" }
}
