// Okno namizja nad plosco (Lastnosti, Nova datoteka, Shrani na napravo, Uredi dock …): modalno, Escape ali klik zunaj
// zapre, fokus ostane v oknu (Tab). Isti videz kot meniji namizja; barve iz palete (tokens.css).
import QtQuick
import QtQuick.Controls.Basic

Popup {
    anchors.centerIn: parent
    modal: true; focus: true; padding: 18
    width: Math.min(420, parent ? parent.width - 24 : 420)
    background: Rectangle { radius: 16; color: koren.paleta.vnos; border.color: koren.crta(0.14) }
    Overlay.modal: Rectangle { color: koren.plosca(0.35) }
}
