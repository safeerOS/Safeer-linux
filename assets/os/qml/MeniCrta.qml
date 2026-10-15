// Locilo v meniju namizja (kot »—« v menijih delovne povrsine).
import QtQuick
import QtQuick.Controls.Basic

MenuSeparator {
    height: visible ? implicitHeight : 0
    topPadding: 4; bottomPadding: 4
    contentItem: Rectangle { implicitHeight: 1; color: koren.crta(0.14) }
}
