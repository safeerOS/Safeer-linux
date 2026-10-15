// Meni namizja (desni klik, tipka Meni ali Shift+F10): ozadje iz palete, podmeniji z MeniVnos.
import QtQuick
import QtQuick.Controls.Basic

Menu {
    background: Rectangle { implicitWidth: 240; radius: 12; color: koren.paleta.vnos; border.color: koren.crta(0.14) }
    delegate: MeniVnos {}
}
