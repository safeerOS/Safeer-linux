// »Pretvori za televizor …« (krog solidarnosti, Safeer Control): video pretvori naprava v Safeer Linku z najboljsim
// strojnim kodirnikom (H.264, 1080p); izvirnik ostane, uporabnik izbere, ali rezultat prenese sem ali ga pusti na
// napravi. Za mapo si vse videe razdelijo naprave, ki lahko pomagajo (sorazmerni delez). Isti potek in besedila kot
// pretvoriVideo / pretvoriMapo v delovna.js (pretvoriVideo -> pretvorbaStanje, pretvoriVec -> pretvorbaSkupina).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Okno {
    id: okno
    objectName: "pretvoriZaTv"
    width: Math.min(500, parent ? parent.width - 24 : 500)
    closePolicy: Popup.CloseOnEscape
    property bool mapa: false
    property string id_: ""
    property string naslov: ""
    property string besedilo: ""
    property string naprave: ""
    property string vprasanje: ""
    property bool izbira: false          // Prenesi sem / Pusti na napravi
    property var zadnji: ({})
    signal spremenjeno()
    function zacni(e, jeMapa) {
        mapa = !!jeMapa; id_ = ""; izbira = false; vprasanje = ""; naprave = ""
        naslov = mapa ? koren.t("prvSkNaslov") : koren.t("pretvori").replace(/\s…$/, "")
        besedilo = koren.t("prvIscem", { ime: e.ime })
        open(); zapri.forceActiveFocus()
        koren.klic(mapa ? "pretvoriVec" : "pretvoriVideo", [mapa ? [e.pot] : e.pot], function (r) {
            if (!r || !r.ok) { okno.napaka(r); return }
            okno.id_ = r.id; okno.pokazi(r)
        }, function () { okno.napaka(null) })
    }
    function koncaj(s) { besedilo = s; vprasanje = ""; izbira = false; casovnik.stop(); Qt.callLater(function () { zapri.forceActiveFocus() }) }
    function napaka(r) {
        var k = (r && (r.napaka || r.koda)) || "napaka"
        if (mapa) koncaj(k === "ni_videov" ? koren.t("prvSkNiVidea") : k === "ni_naprave" ? koren.t("prvNiNaprave") : koren.t("prvNapaka", { koda: k }))
        else koncaj(k === "ni_naprave" ? koren.t("prvNiNaprave") : k === "ne_zna_dekodirati" ? koren.t("prvNeZna") : koren.t("prvNapaka", { koda: k }))
    }
    function pokazi(r) { zadnji = r; if (mapa) pokaziSkupino(r); else pokaziEno(r) }
    function pokaziEno(r) {
        // Samo mapa (ime datoteke je ze v besedilu): "Download/Safeer Shramba/x.mp4" -> "Prenosi › Safeer Shramba".
        var kje = String(r.kje || "").replace(/\/[^\/]*$/, "").replace(/^Download(\/|$)/, koren.t("shrPrenosi") + "$1").replace(/\//g, " › ")
        var z = { ime: r.ime, naprava: r.naprava || "", kje: kje, izhod: r.izhod || "", velikost: koren.velikost(r.izhod_velikost || 0), odst: r.odstotek || 0 }
        var st = r.stanje
        if (st === "isceno") besedilo = koren.t("prvIscem", z)
        else if (st === "prenasam") besedilo = koren.t("prvPrenasam", z)
        else if (st === "pretvarjam") besedilo = koren.t("prvPretvarjam", z)
        else if (st === "pretvarjam_tu") besedilo = koren.t("prvPretvarjamTu", z)
        else if (st === "shranjujem") besedilo = koren.t("prvShranjujem", z)
        else if (st === "prenasam_nazaj") { besedilo = koren.t("prvNazaj", z); izbira = false; vprasanje = "" }
        else if (st === "na_racunalniku") { koncaj(koren.t("prvNaRacunalniku", z)); spremenjeno(); return }
        else if (st === "pusceno") { koncaj(koren.t("prvPusceno", z)); return }
        else if (st === "koncano") {
            naslov = koren.t("prvKoncanoNaslov")
            if (r.napaka) { koncaj(r.napaka === "naprava_ne_deli" ? koren.t("prvNeDeli", z) : koren.t("prvKoncano", z) + " " + koren.t("prvNapaka", { koda: r.napaka })); return }
            besedilo = koren.t("prvKoncano", z); vprasanje = koren.t("prvVprasaj"); izbira = true
            Qt.callLater(function () { prenesi.forceActiveFocus() }); return
        }
        else if (st === "napaka") { napaka(r); return }
        casovnik.restart()
    }
    function pokaziSkupino(r) {
        var z = { opr: r.uspesno || 0, vseh: r.skupaj || 0 }
        // Kdo koliko opravi (sorazmerni delez) in kaj kdo ta trenutek dela.
        var dela = {}, imena = {}, vrstice = []
        ;(r.opravila || []).forEach(function (o) {
            if (o.naprava && ["prenasam", "pretvarjam", "shranjujem"].indexOf(o.stanje) >= 0) dela[o.naprava] = o.ime + " " + (o.odstotek || 0) + " %"
        })
        Object.keys(r.po_napravah || {}).forEach(function (k) { imena[k] = 1 })
        Object.keys(dela).forEach(function (k) { imena[k] = 1 })
        Object.keys(imena).forEach(function (k) {
            vrstice.push(k + ": " + ((r.po_napravah || {})[k] || 0) + (dela[k] ? " · " + koren.t("prvSkDela") + " " + dela[k] : ""))
        })
        naprave = vrstice.join("\n")
        if (r.nazaj === "prenasam") { besedilo = koren.t("prvSkNazaj"); izbira = false; vprasanje = "" }
        else if (r.nazaj === "koncano") {
            var n = (r.opravila || []).filter(function (o) { return o.stanje === "na_racunalniku" }).length
            koncaj(koren.t("prvSkNaRacunalniku", { n: n })); spremenjeno(); return
        }
        else if (r.koncano) {
            var tekst = koren.t("prvSkKoncano", z)
            if (r.napake) {
                var prva = (r.opravila || []).filter(function (o) { return o.stanje === "napaka" })[0] || {}
                tekst += " " + koren.t("prvSkNapake", { n: r.napake, koda: prva.napaka || "" })
            }
            if (!r.uspesno) { koncaj(tekst); return }
            if ((r.opravila || []).some(function (o) { return o.stanje === "pusceno" })) { koncaj(tekst + " " + koren.t("prvSkPusceno")); return }
            besedilo = tekst; vprasanje = koren.t("prvSkVprasaj"); izbira = true
            Qt.callLater(function () { prenesi.forceActiveFocus() }); return
        }
        else besedilo = koren.t("prvSkPoteka", z)
        casovnik.restart()
    }
    onClosed: casovnik.stop()
    Timer {
        id: casovnik; interval: 1500
        onTriggered: koren.klic(okno.mapa ? "pretvorbaSkupina" : "pretvorbaStanje", [okno.id_], function (r) {
            if (r && r.ok) okno.pokazi(r); else okno.napaka(r)
        }, function () { okno.napaka(null) })
    }
    ColumnLayout {
        anchors.fill: parent; spacing: 10
        Text { text: okno.naslov; color: koren.paleta.besedilo; font.pixelSize: koren.px(15); font.bold: true; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Text { objectName: "prvBesedilo"; text: okno.besedilo; color: koren.paleta.besedilo; font.pixelSize: koren.px(13); Layout.fillWidth: true; wrapMode: Text.WordWrap
               Accessible.role: Accessible.StaticText; Accessible.name: text }
        Text { visible: okno.naprave !== ""; text: okno.naprave; color: koren.paleta.medlo; font.pixelSize: koren.px(12); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Text { visible: okno.vprasanje !== ""; text: okno.vprasanje; color: koren.paleta.besedilo; font.pixelSize: koren.px(13); font.bold: true
               Layout.fillWidth: true; wrapMode: Text.WordWrap }
        RowLayout {
            Layout.alignment: Qt.AlignRight; spacing: 8
            Gumb {
                visible: okno.izbira; besedilo: koren.t(okno.mapa ? "prvSkPusti" : "prvPusti")
                onKlik: koren.klic(okno.mapa ? "pretvorbaPustiSkupino" : "pretvorbaPusti", [okno.id_], function (x) { okno.pokazi(x && x.ok ? x : okno.zadnji) },
                                   function () { okno.napaka(null) })
            }
            Gumb {
                id: prenesi; visible: okno.izbira; besedilo: koren.t(okno.mapa ? "prvSkPrenesi" : "prvPrenesi"); poudarjen: true
                onKlik: {
                    okno.izbira = false; okno.vprasanje = ""
                    koren.klic(okno.mapa ? "pretvorbaPrenesiSkupino" : "pretvorbaPrenesi", [okno.id_], function (x) {
                        if (!x || !x.ok) { okno.napaka(x); return }
                        okno.pokazi(x)
                    }, function () { okno.napaka(null) })
                }
            }
            Gumb { id: zapri; visible: !okno.izbira; besedilo: koren.t("shrZapri"); onKlik: okno.close() }
        }
    }
}
