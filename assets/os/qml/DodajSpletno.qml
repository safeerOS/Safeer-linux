// Dodaj spletno aplikacijo (kot »Dodaj« na Domov aplikacije Safeer OS): ime in naslov; preverjanje, »ze dodana« in
// najvec 24 so v core/os_spletne.py (most spletnaDodaj). Napaka pod poljem, Escape ali Preklici zapre (popis 3.1, 18. 10. 2026).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Okno {
    id: okno
    objectName: "oknoSpletna"
    property string napaka: ""
    property bool dela: false
    signal dodano(var r)

    function odpri() {
        ime.text = ""; naslov.text = ""; napaka = ""; dela = false
        open()
        naslov.forceActiveFocus()
    }
    function potrdi() {
        if (dela || naslov.text.trim() === "") return
        dela = true
        koren.klic("spletnaDodaj", [ime.text.trim(), naslov.text.trim()], function (r) {
            dela = false
            if (!r || !r.ok) {
                napaka = koren.t(({ ze: "spletnaZeDodana", polno: "spletnaPolno" })[r && r.napaka] || "spletnaNapacenNaslov", { n: (r && r.meja) || "" })
                naslov.forceActiveFocus(); naslov.selectAll()
                return
            }
            close()
            okno.dodano(r)
        }, function () { dela = false; napaka = koren.t("niUspelo") })
    }

    ColumnLayout {
        anchors.fill: parent; spacing: 10
        Text { Layout.fillWidth: true; text: koren.t("spletnaDodaj"); color: koren.paleta.besedilo; font.pixelSize: koren.px(15); font.bold: true }
        TextField {
            id: naslov
            objectName: "spletnaNaslov"
            Layout.fillWidth: true; color: koren.paleta.besedilo; font.pixelSize: koren.px(14); selectByMouse: true
            placeholderText: koren.t("spletnaNaslov"); placeholderTextColor: koren.paleta.medlo
            inputMethodHints: Qt.ImhUrlCharactersOnly | Qt.ImhNoAutoUppercase
            Accessible.name: koren.t("spletnaNaslov")
            background: Rectangle { radius: 8; color: koren.prekriv(0.08); border.color: naslov.activeFocus ? koren.paleta.fokus : koren.crta(0.2) }
            Keys.onReturnPressed: okno.potrdi()
            Keys.onEnterPressed: okno.potrdi()
            onTextChanged: okno.napaka = ""
        }
        TextField {
            id: ime
            objectName: "spletnaIme"
            Layout.fillWidth: true; color: koren.paleta.besedilo; font.pixelSize: koren.px(14); selectByMouse: true
            maximumLength: 40
            placeholderText: koren.t("spletnaIme"); placeholderTextColor: koren.paleta.medlo
            Accessible.name: koren.t("spletnaIme")
            background: Rectangle { radius: 8; color: koren.prekriv(0.08); border.color: ime.activeFocus ? koren.paleta.fokus : koren.crta(0.2) }
            Keys.onReturnPressed: okno.potrdi()
            Keys.onEnterPressed: okno.potrdi()
        }
        Text {
            objectName: "spletnaNapaka"
            visible: okno.napaka !== ""; text: okno.napaka; Layout.fillWidth: true; wrapMode: Text.WordWrap
            color: koren.paleta.rdeca || koren.paleta.besedilo; font.pixelSize: koren.px(12)
            Accessible.role: Accessible.AlertMessage; Accessible.name: text
        }
        RowLayout {
            Layout.alignment: Qt.AlignRight; spacing: 8
            Gumb { besedilo: koren.t("preklici"); onKlik: okno.close() }
            Gumb { objectName: "spletnaPotrdi"; besedilo: koren.t("dodaj"); poudarjen: true
                   enabled: !okno.dela && naslov.text.trim() !== ""; onKlik: okno.potrdi() }
        }
    }
}
