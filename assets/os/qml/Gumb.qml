// Gumb z napisom: miska, tipkovnica (Tab, Enter, preslednica), viden fokus in dostopno ime - kot GumbIkona.
import QtQuick

Rectangle {
    id: gumb
    property string besedilo: ""
    property bool poudarjen: false
    signal klik()
    // Velikost prek implicit*: postavitve (RowLayout) jo upostevajo tudi, ko se pisava kasneje poveca.
    implicitHeight: koren.px(30); implicitWidth: napis.implicitWidth + 26; radius: height / 2
    opacity: enabled ? 1 : 0.4
    color: poudarjen ? (m.containsMouse || activeFocus ? Qt.lighter(koren.paleta.poudarek, 1.12) : koren.paleta.poudarek)
                     : (m.pressed ? koren.prekriv(0.22) : m.containsMouse ? koren.prekriv(0.16) : koren.prekriv(0.08))
    border.width: activeFocus ? 2 : 1
    border.color: activeFocus ? (poudarjen ? koren.paleta.besedilo : koren.paleta.fokus) : poudarjen ? "transparent" : koren.crta(0.14)
    scale: m.pressed ? 0.96 : 1
    Behavior on color { enabled: koren.gibanje; ColorAnimation { duration: 140 } }
    Behavior on scale { enabled: koren.gibanje; NumberAnimation { duration: 90 } }
    activeFocusOnTab: enabled && visible
    Accessible.role: Accessible.Button
    Accessible.name: besedilo
    Accessible.onPressAction: if (gumb.enabled) gumb.klik()
    Keys.onReturnPressed: if (gumb.enabled) gumb.klik()
    Keys.onEnterPressed: if (gumb.enabled) gumb.klik()
    Keys.onSpacePressed: if (gumb.enabled) gumb.klik()
    Text {
        id: napis; anchors.centerIn: parent; text: gumb.besedilo
        color: gumb.poudarjen ? koren.paleta.poudarekTemna : koren.paleta.besedilo; font.pixelSize: koren.px(12); font.bold: gumb.poudarjen
    }
    MouseArea { id: m; anchors.fill: parent; hoverEnabled: true; enabled: gumb.enabled; cursorShape: Qt.PointingHandCursor; onClicked: gumb.klik() }
}
