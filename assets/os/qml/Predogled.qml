// Predogled datoteke v Datotekah (preslednica ali »Predogled«, kot Quick Look): slika, zacetek besedila ali kode
// (najvec 200 KB, binarno ne - core/os_datoteke.predogled), prva stran PDF, ce je na racunalniku orodje zanjo, in za
// glasbo in video »Predvajaj« po isti poti kot dvojni klik (Medijski center). Puscici levo/desno: prejsnja in
// naslednja datoteka v pogledu; Enter odpre s privzetim programom; preslednica ali Escape zapre.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Okno {
    id: okno
    objectName: "predogled"
    parent: Overlay.overlay
    width: Math.min(koren.px(1000), (parent ? parent.width : 1000) - 80)
    height: Math.min(koren.px(760), (parent ? parent.height : 760) - 80)
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    property var seznam: []
    property int i: 0
    readonly property var e: seznam[i] || null
    property var r: ({})                 // odgovor predogledDatoteke
    property bool nalagam: false
    property int zahteva: 0
    readonly property string nacin: r && r.ok ? String(r.nacin || "podatki") : ""
    signal odpriDatoteko(var e)

    function odpri(s, k) {
        seznam = s || []
        if (!seznam.length) return
        i = Math.max(0, Math.min(k || 0, seznam.length - 1))
        nalozi()
        open()
        vsebina.forceActiveFocus()
    }
    function premakni(smer) {
        if (seznam.length < 2) return
        i = (i + smer + seznam.length) % seznam.length
        nalozi()
    }
    function nalozi() {
        var st = ++zahteva
        r = ({}); nalagam = true; besedilo.contentY = 0; besedilo.contentX = 0
        if (!e) return
        koren.klic("predogledDatoteke", [e.pot], function (x) {
            if (st !== okno.zahteva) return
            okno.nalagam = false; okno.r = x || { ok: false }
        }, function () { if (st === okno.zahteva) { okno.nalagam = false; okno.r = { ok: false } } })
    }
    function potrdi() { var x = e; close(); if (x) odpriDatoteko(x) }
    function razlog() {
        if (!r || r.ok === false) return koren.t("predogledNapaka")
        if (r.prevelika) return koren.t("predogledPrevelika")
        if (r.binarno) return koren.t("predogledBinarno")
        if (r.brezOrodja) return koren.t("predogledPdfNi")
        return ""
    }
    function pomakni(dy) { besedilo.contentY = Math.max(0, Math.min(besedilo.contentHeight - besedilo.height, besedilo.contentY + dy)) }

    Item {
        id: vsebina
        anchors.fill: parent
        focus: true
        Accessible.role: Accessible.Dialog
        Accessible.name: koren.t("predogled") + (okno.e ? ": " + okno.e.ime : "")
        Keys.onPressed: function (d) {
            if (d.key === Qt.Key_Escape || d.key === Qt.Key_Space) { okno.close(); d.accepted = true }
            else if (d.key === Qt.Key_Return || d.key === Qt.Key_Enter) { okno.potrdi(); d.accepted = true }
            else if (d.key === Qt.Key_Left) { okno.premakni(-1); d.accepted = true }
            else if (d.key === Qt.Key_Right) { okno.premakni(1); d.accepted = true }
            else if (d.key === Qt.Key_Down) { okno.pomakni(koren.px(40)); d.accepted = true }
            else if (d.key === Qt.Key_Up) { okno.pomakni(-koren.px(40)); d.accepted = true }
            else if (d.key === Qt.Key_PageDown) { okno.pomakni(besedilo.height * 0.9); d.accepted = true }
            else if (d.key === Qt.Key_PageUp) { okno.pomakni(-besedilo.height * 0.9); d.accepted = true }
        }

        ColumnLayout {
            anchors.fill: parent; spacing: 10
            RowLayout {
                Layout.fillWidth: true; spacing: 10
                Text {
                    objectName: "predogledIme"
                    Layout.fillWidth: true; elide: Text.ElideMiddle
                    text: okno.e ? okno.e.ime : ""; color: koren.paleta.besedilo; font.pixelSize: koren.px(16); font.bold: true
                }
                Text {
                    visible: okno.seznam.length > 1
                    text: (okno.i + 1) + " / " + okno.seznam.length; color: koren.paleta.medlo; font.pixelSize: koren.px(12)
                }
            }
            Text {
                Layout.fillWidth: true; elide: Text.ElideLeft
                color: koren.paleta.medlo; font.pixelSize: koren.px(12)
                text: okno.e ? [koren.velikost(okno.r.velikost !== undefined ? okno.r.velikost : okno.e.velikost), koren.cas(okno.r.spremenjeno || okno.e.spremenjeno),
                                koren.kratkaPot(String(okno.e.pot).replace(/\/[^/]*$/, ""))].filter(function (x) { return !!x }).join("  ·  ") : ""
            }
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true
                radius: 12; color: koren.plosca(0.6); border.color: koren.crta(0.10); clip: true
                // Slika ali prva stran PDF: pomanjsana v okno (dekodirana najvec do 2400 px).
                Image {
                    id: slika
                    objectName: "predogledSlika"
                    anchors.fill: parent; anchors.margins: 8
                    visible: okno.nacin === "slika" || okno.nacin === "pdf"
                    fillMode: Image.PreserveAspectFit; asynchronous: true; smooth: true; autoTransform: true
                    sourceSize: Qt.size(2400, 2400)
                    source: !visible ? "" : Most.datotekaUrl(okno.nacin === "pdf" ? String(okno.r.slika || "") : String(okno.r.pot || ""))
                    Accessible.role: Accessible.Graphic; Accessible.name: okno.e ? okno.e.ime : ""
                }
                Flickable {
                    id: besedilo
                    objectName: "predogledBesedilo"
                    anchors.fill: parent; anchors.margins: 10
                    visible: okno.nacin === "besedilo"
                    contentWidth: Math.max(width, tekst.paintedWidth); contentHeight: tekst.paintedHeight
                    boundsBehavior: Flickable.StopAtBounds; clip: true
                    ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                    ScrollBar.horizontal: ScrollBar { policy: ScrollBar.AsNeeded }
                    TextEdit {
                        id: tekst
                        objectName: "predogledTekst"
                        readOnly: true; selectByMouse: true; activeFocusOnPress: false
                        textFormat: TextEdit.PlainText
                        text: besedilo.visible ? String(okno.r.besedilo || "") : ""
                        color: koren.paleta.besedilo; selectionColor: koren.poudarekA(0.4); selectedTextColor: koren.paleta.besedilo
                        font.family: "monospace"; font.pixelSize: koren.px(12)
                    }
                }
                // Glasba, video, druge datoteke in razlogi (prevelika, binarna, brez orodja za PDF).
                ColumnLayout {
                    anchors.centerIn: parent; width: parent.width - 40; spacing: 14
                    visible: !okno.nalagam && (okno.nacin === "medij" || okno.nacin === "podatki" || okno.nacin === "" || slika.status === Image.Error)
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        width: koren.px(84); height: koren.px(84); radius: 20
                        color: koren.barvaVrste(okno.e ? okno.e.vrsta : "")
                        Text { anchors.centerIn: parent; color: koren.prekriv(1); font.pixelSize: koren.px(22); font.bold: true
                               text: okno.e ? (String(okno.e.ime).split(".").pop() || "?").slice(0, 4).toUpperCase() : "" }
                    }
                    Text {
                        objectName: "predogledRazlog"
                        Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
                        visible: text !== ""
                        text: slika.status === Image.Error ? koren.t("predogledNapaka") : okno.razlog()
                        color: koren.paleta.medlo; font.pixelSize: koren.px(13)
                    }
                }
                Text {
                    anchors.centerIn: parent; visible: okno.nalagam
                    text: koren.t("nalagam"); color: koren.paleta.medlo; font.pixelSize: koren.px(13)
                }
            }
            Text {
                objectName: "predogledOdrezano"
                Layout.fillWidth: true; visible: okno.nacin === "besedilo" && !!okno.r.odrezano; wrapMode: Text.WordWrap
                text: visible ? koren.t("predogledZacetek", { velikost: koren.velikost(okno.r.prebrano || 0),
                                                             skupaj: koren.velikost(okno.r.velikost) }) : ""
                color: koren.paleta.opozorilo || koren.paleta.medlo; font.pixelSize: koren.px(12)
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                Text { Layout.fillWidth: true; text: koren.t(okno.seznam.length > 1 ? "predogledNamig" : "predogledNamigEna"); color: Qt.darker(koren.paleta.medlo, 1.1)
                       font.pixelSize: koren.px(11); elide: Text.ElideRight }
                Gumb { objectName: "predogledPredvajaj"; visible: okno.nacin === "medij"; poudarjen: true; besedilo: koren.t("predvajaj"); onKlik: okno.potrdi() }
                Gumb { objectName: "predogledOdpri"; visible: okno.nacin !== "medij"; poudarjen: true; besedilo: koren.t("odpri"); onKlik: okno.potrdi() }
                Gumb { besedilo: koren.t("zapri"); onKlik: okno.close() }
            }
        }
    }
}
