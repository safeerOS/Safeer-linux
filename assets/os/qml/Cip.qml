// Cip pod iskanjem na namizju (Sporocila, posodobitev) - isti videz kot gumb Safeer Link: miska, tipkovnica (Tab, Enter,
// preslednica), viden fokus in dostopno ime; neobvezna znacka s stevilom (popis 3.1, 18. 10. 2026).
import QtQuick

Rectangle {
    id: cip
    property string besedilo: ""
    property string ime: besedilo       // dostopno ime (npr. s stevilom neprebranih)
    property int stevilo: 0             // znacka; 0 = brez znacke
    property bool poudarjen: false
    signal klik()
    height: koren.px(26); width: vsebina.width + 22; radius: height / 2
    color: poudarjen ? (m.containsMouse || activeFocus ? Qt.lighter(koren.paleta.poudarek, 1.12) : koren.paleta.poudarek)
                     : (m.containsMouse || activeFocus ? koren.prekriv(0.16) : koren.plosca(koren.prosojnostPlosc))
    border.width: activeFocus ? 2 : 1
    border.color: activeFocus ? (poudarjen ? koren.paleta.besedilo : koren.paleta.fokus) : poudarjen ? "transparent" : koren.crta(0.12)
    activeFocusOnTab: visible
    Accessible.role: Accessible.Button
    Accessible.name: ime
    Accessible.onPressAction: cip.klik()
    Keys.onReturnPressed: cip.klik()
    Keys.onEnterPressed: cip.klik()
    Keys.onSpacePressed: cip.klik()
    Behavior on color { ColorAnimation { duration: 150 } }
    Row {
        id: vsebina; anchors.centerIn: parent; spacing: 7
        Text {
            text: cip.besedilo; anchors.verticalCenter: parent.verticalCenter
            color: cip.poudarjen ? koren.paleta.poudarekTemna : koren.paleta.besedilo
            font.pixelSize: koren.px(12); font.bold: cip.poudarjen
        }
        Rectangle {
            objectName: "znacka"
            visible: cip.stevilo > 0
            height: koren.px(17); width: Math.max(height, stevka.implicitWidth + 10); radius: height / 2
            anchors.verticalCenter: parent.verticalCenter
            color: koren.paleta.poudarek
            Text {
                id: stevka; anchors.centerIn: parent
                text: cip.stevilo > 99 ? "99+" : String(cip.stevilo)
                color: koren.paleta.poudarekTemna; font.pixelSize: koren.px(11); font.bold: true
            }
        }
    }
    MouseArea { id: m; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: cip.klik() }
}
