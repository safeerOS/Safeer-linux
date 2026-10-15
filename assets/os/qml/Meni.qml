// Meni namizja (desni klik, tipka Meni ali Shift+F10): ozadje iz palete, podmeniji z MeniVnos.
import QtQuick
import QtQuick.Controls.Basic

Menu {
    property real sirina: 240           // meni z daljsimi opisi (igra v oblaku) je sirsi
    background: Rectangle { implicitWidth: sirina; radius: 12; color: koren.paleta.vnos; border.color: koren.crta(0.14) }
    delegate: MeniVnos {}
}
