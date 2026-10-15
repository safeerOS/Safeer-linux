// Nova mapa, nova datoteka (prazna, besedilo, dokument, preglednica, predstavitev ali predloga iz mape Predloge) in
// preimenovanje - isto okno kot na delovni povrsini WebKit (delovna.js odpriOknoNovo): ime, vrsta, »Kje« s »Spremeni …«,
// napaka pod poljem. Pri preimenovanju je oznaceno ime brez koncnice (kot Nemo).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Okno {
    id: okno
    objectName: "oknoNovo"
    width: Math.min(460, parent ? parent.width - 24 : 460)
    // {nacin: "preimenuj"|"mapa"|"datoteka", kam, pot, ime, mapa, vrsta, predloga}
    property var nastavitve: ({})
    property var predloge: []
    property string kam: ""
    property string napaka: ""
    property bool dela: false
    signal koncano(var r, var nastavitve)
    readonly property bool preimenuj: nastavitve.nacin === "preimenuj"
    // Iste vrste kot VRSTE_NOVIH v delovna.js (core/os_datoteke.NOVE_VRSTE): [vrsta, kljuc menija, privzeto ime].
    readonly property var vrste: [["prazna", "vPrazna", "privzetoDatoteka"], ["besedilo", "vBesedilo", "privzetoDatoteka"],
                                  ["dokument", "vDokument", "privzetoDokument"], ["preglednica", "vPreglednica", "privzetoPreglednica"],
                                  ["predstavitev", "vPredstavitev", "privzetoPredstavitev"]]
    readonly property var moznosti: vrste.map(function (v) { return { vrednost: v[0], ime: koren.t(v[1]).replace(/ …$/, "") } })
        .concat(predloge.map(function (p) { return { vrednost: "predloga:" + p.pot, ime: koren.t("vPredloga", { ime: p.ime }).replace(/ …$/, "") } }))

    function odpri(o) {
        nastavitve = o; napaka = ""; dela = false; kam = o.kam || ""
        var ime = o.nacin === "preimenuj" ? o.ime : o.nacin === "mapa" ? koren.t("privzetoMapa")
            : o.vrsta === "predloga" ? o.ime
            : koren.t((vrste.filter(function (v) { return v[0] === o.vrsta })[0] || vrste[0])[2])
        polje.text = ime
        var izbrana = o.vrsta === "predloga" ? "predloga:" + o.predloga : (o.vrsta || "prazna")
        vrsta.currentIndex = Math.max(0, moznosti.map(function (m) { return m.vrednost }).indexOf(izbrana))
        open()
        polje.forceActiveFocus()
        var konec = o.nacin === "preimenuj" && !o.mapa && ime.lastIndexOf(".") > 0 ? ime.lastIndexOf(".") : ime.length
        polje.select(0, konec)
    }
    function kje(pot) {
        var dom = (koren.dom || "").replace(/\/$/, "")
        if (!pot || pot === "~" || pot.replace(/\/$/, "") === dom) return koren.t("domov")
        if (dom && pot.indexOf(dom + "/") === 0) return koren.t("domov") + " › " + pot.slice(dom.length + 1).split("/").join(" › ")
        return pot
    }
    function napakaBesedilo(koda) {
        return koren.t(({ obstaja: "nObstaja", napacno_ime: "nIme", ni_dovoljenja: "nDovoljenje", ni_dovoljeno: "nDovoljenje",
                          ni_mape: "nMapa" })[koda] || "nSplosno")
    }
    function potrdi() {
        if (dela) return
        var o = nastavitve, ime = polje.text.trim(), metoda, args
        if (o.nacin === "preimenuj") { metoda = "preimenujDatoteko"; args = [o.pot, ime] }
        else if (o.nacin === "mapa") { metoda = "novaMapa"; args = [kam, ime] }
        else {
            var v = (moznosti[vrsta.currentIndex] || moznosti[0]).vrednost
            metoda = "novaDatoteka"
            args = v.indexOf("predloga:") === 0 ? [kam, ime, "prazna", v.slice(9)] : [kam, ime, v, ""]
        }
        dela = true
        koren.klic(metoda, args, function (r) {
            dela = false
            if (!r || !r.ok) { napaka = napakaBesedilo(r && r.napaka); polje.forceActiveFocus(); return }
            close()
            okno.koncano(r, o)
        }, function () { dela = false; napaka = koren.t("nSplosno") })
    }

    ColumnLayout {
        anchors.fill: parent; spacing: 10
        Text {
            Layout.fillWidth: true; elide: Text.ElideRight
            text: koren.t(okno.preimenuj ? "oknoPreimenuj" : okno.nastavitve.nacin === "mapa" ? "oknoMapa" : "oknoDatoteka")
            color: koren.paleta.besedilo; font.pixelSize: koren.px(15); font.bold: true
        }
        Text { text: koren.t("novoIme"); color: koren.paleta.medlo; font.pixelSize: koren.px(11) }
        TextField {
            id: polje
            objectName: "novoIme"
            Layout.fillWidth: true; color: koren.paleta.besedilo; font.pixelSize: koren.px(14)
            selectByMouse: true
            Accessible.name: koren.t("novoIme")
            background: Rectangle { radius: 8; color: koren.prekriv(0.08); border.color: polje.activeFocus ? koren.paleta.fokus : koren.crta(0.2) }
            Keys.onReturnPressed: okno.potrdi()
            Keys.onEnterPressed: okno.potrdi()
            onTextChanged: okno.napaka = ""
        }
        Text { visible: okno.nastavitve.nacin === "datoteka"; text: koren.t("novoVrsta"); color: koren.paleta.medlo; font.pixelSize: koren.px(11) }
        ComboBox {
            id: vrsta
            objectName: "novoVrsta"
            visible: okno.nastavitve.nacin === "datoteka"
            Layout.fillWidth: true; implicitHeight: koren.px(32)
            model: okno.moznosti; textRole: "ime"; font.pixelSize: koren.px(13)
            Accessible.name: koren.t("novoVrsta")
            background: Rectangle { radius: 8; color: vrsta.hovered ? koren.prekriv(0.14) : koren.prekriv(0.08)
                                    border.width: vrsta.activeFocus ? 2 : 1; border.color: vrsta.activeFocus ? koren.paleta.fokus : koren.crta(0.2) }
            contentItem: Text { leftPadding: 10; text: vrsta.displayText; color: koren.paleta.besedilo; font: vrsta.font
                                verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight }
            indicator: Text { text: "▾"; color: koren.paleta.medlo; x: vrsta.width - 22; anchors.verticalCenter: parent.verticalCenter }
            delegate: ItemDelegate {
                width: vrsta.width; highlighted: vrsta.highlightedIndex === index
                contentItem: Text { text: modelData.ime; color: koren.paleta.besedilo; font.pixelSize: koren.px(13); elide: Text.ElideRight }
                background: Rectangle { radius: 8; color: parent.highlighted ? koren.poudarekA(0.22) : "transparent" }
            }
            popup.background: Rectangle { radius: 12; color: koren.paleta.vnos; border.color: koren.crta(0.14) }
        }
        Text { visible: !okno.preimenuj; text: koren.t("novoKje"); color: koren.paleta.medlo; font.pixelSize: koren.px(11) }
        RowLayout {
            visible: !okno.preimenuj; Layout.fillWidth: true; spacing: 8
            Text { Layout.fillWidth: true; text: okno.kje(okno.kam); color: koren.paleta.besedilo; font.pixelSize: koren.px(13); elide: Text.ElideLeft }
            Gumb {
                objectName: "novoSpremeni"
                besedilo: koren.t("novoSpremeni")
                // Sistemsko okno za izbiro mape (izberiMapo, isto kot na delovni povrsini).
                onKlik: koren.klic("izberiMapo", [okno.kam || "~", koren.t("izberiMapoNaslov"), koren.t("preklici"), koren.t("izberi")],
                                   function (p) { if (p) okno.kam = p; polje.forceActiveFocus() })
            }
        }
        Text {
            objectName: "novoNapaka"
            visible: okno.napaka !== ""; text: okno.napaka; Layout.fillWidth: true; wrapMode: Text.WordWrap
            color: koren.paleta.rdeca || koren.paleta.besedilo; font.pixelSize: koren.px(12)
            Accessible.role: Accessible.AlertMessage; Accessible.name: text
        }
        RowLayout {
            Layout.alignment: Qt.AlignRight; spacing: 8
            Gumb { besedilo: koren.t("preklici"); onKlik: okno.close() }
            Gumb { objectName: "novoPotrdi"; besedilo: koren.t(okno.preimenuj ? "preimenuj" : "ustvari"); poudarjen: true
                   enabled: !okno.dela && polje.text.trim() !== ""; onKlik: okno.potrdi() }
        }
    }
}
