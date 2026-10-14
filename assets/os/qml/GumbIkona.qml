// Okrogel gumb z ikono (pot SVG 24 x 24, iste poti kot os.js): tipkovnica (Tab, Enter, preslednica), viden fokus,
// dostopno ime in namig. Za prejsnja / predvajaj / naslednja in »Predvajaj na …« na namizju.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Shapes

Rectangle {
    id: g
    property string pot: ""
    property string ime: ""
    property bool poudarjen: false      // glavni gumb (predvajaj / premor)
    property bool polnilo: false        // ikona s polnilom (predvajaj, premor, prejsnja, naslednja)
    property bool vklopljen: false      // npr. zvok gre na drugo napravo
    property real velikostIkone: 18
    signal klik()
    width: 34; height: 34; radius: width / 2
    opacity: enabled ? 1 : 0.4
    readonly property color barvaIkone: poudarjen ? koren.paleta.poudarekTemna : vklopljen ? koren.paleta.poudarek : koren.paleta.besedilo
    color: poudarjen ? (m.containsMouse ? Qt.lighter(koren.paleta.poudarek, 1.12) : koren.paleta.poudarek)
                     : vklopljen ? koren.poudarekA(0.22)
                     : (m.pressed ? Qt.rgba(1, 1, 1, 0.22) : m.containsMouse ? Qt.rgba(1, 1, 1, 0.14) : "transparent")
    border.width: activeFocus ? 2 : 0
    border.color: poudarjen ? koren.paleta.besedilo : koren.paleta.poudarek
    scale: m.pressed ? 0.94 : 1
    Behavior on color { ColorAnimation { duration: 140 } }
    Behavior on scale { NumberAnimation { duration: 90 } }
    activeFocusOnTab: enabled
    Accessible.role: Accessible.Button
    Accessible.name: ime
    Accessible.onPressAction: if (g.enabled) g.klik()
    Keys.onReturnPressed: if (g.enabled) g.klik()
    Keys.onEnterPressed: if (g.enabled) g.klik()
    Keys.onSpacePressed: if (g.enabled) g.klik()
    Shape {
        anchors.centerIn: parent
        width: 24; height: 24
        scale: g.velikostIkone / 24
        ShapePath {
            strokeColor: g.barvaIkone; strokeWidth: g.polnilo ? 1.2 : 1.8
            fillColor: g.polnilo ? g.barvaIkone : "transparent"
            capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
            PathSvg { path: g.pot }
        }
    }
    MouseArea { id: m; anchors.fill: parent; hoverEnabled: true; enabled: g.enabled; cursorShape: Qt.PointingHandCursor; onClicked: g.klik() }
    ToolTip.visible: m.containsMouse && g.ime !== ""; ToolTip.text: g.ime; ToolTip.delay: 500
}
