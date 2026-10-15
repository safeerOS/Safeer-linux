// »Shrani na drugo napravo …« (skupni prostor, zakon solidarnosti): datoteko shrani naprava v Safeer Linku z najvec
// prostora; izvirnik izbrise sele uporabnik, ko vidi, kje je preverjena kopija. Isti potek kot shraniNaNapravo v
// delovna.js: shraniNaNapravo -> shrambaStanje (vsakih 1,5 s) -> Obdrzi oboje / Izbrisi izvirnik.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Okno {
    id: okno
    objectName: "shraniNaNapravo"
    width: Math.min(480, parent ? parent.width - 24 : 480)
    closePolicy: Popup.CloseOnEscape
    property string id_: ""
    property string ime: ""
    property string naslov: ""
    property string besedilo: ""
    property string vprasanje: ""
    property bool kopija: false
    property var zamenjave: ({})
    signal izbrisano()
    function zacni(e) {
        id_ = ""; ime = e.ime; kopija = false; vprasanje = ""
        naslov = koren.t("shraniNaNapravo").replace(/\s…$/, "")
        besedilo = koren.t("shrPripravljam", { ime: e.ime })
        open(); zapri.forceActiveFocus()
        koren.klic("shraniNaNapravo", [e.pot], function (r) {
            if (!r || !r.ok) { napaka(r); return }
            okno.id_ = r.id; okno.pokazi(r)
        }, function () { napaka(null) })
    }
    function koncaj(s) { besedilo = s; vprasanje = ""; kopija = false; casovnik.stop(); Qt.callLater(function () { zapri.forceActiveFocus() }) }
    function napaka(r) {
        var k = (r && (r.napaka || r.koda)) || "napaka"
        koncaj(k === "ni_naprave" ? koren.t("shrNiNaprave") : k === "spremenjena" ? koren.t("shrSpremenjena") : koren.t("shrNapaka", { koda: k }))
    }
    function pokazi(r) {
        // Android pove pot kot "Download/Safeer Shramba/ime": uporabnik pozna mapo Prenosi.
        var kje = String(r.kje || "").replace(/^Download\//, koren.t("shrPrenosi") + " › ").replace(/\//g, " › ")
        zamenjave = { ime: r.ime || ime, naprava: r.naprava || "", kje: kje, velikost: koren.velikost(r.velikost),
              odst: r.velikost ? Math.floor(100 * (r.preneseno || 0) / r.velikost) : 0 }
        if (r.stanje === "pripravljam") besedilo = koren.t("shrPripravljam", zamenjave)
        else if (r.stanje === "prenasam") besedilo = koren.t("shrPrenasam", zamenjave)
        else if (r.stanje === "kopija") {
            naslov = koren.t("shrKopijaNaslov"); besedilo = koren.t("shrKopija", zamenjave); vprasanje = koren.t("shrVprasaj", zamenjave)
            kopija = true; obdrzi.forceActiveFocus(); return
        } else if (r.stanje === "napaka") { napaka(r); return }
        casovnik.restart()
    }
    onClosed: casovnik.stop()
    Timer {
        id: casovnik; interval: 1500
        onTriggered: koren.klic("shrambaStanje", [okno.id_], function (r) { if (r && r.ok) okno.pokazi(r); else okno.napaka(r) },
                                function () { okno.napaka(null) })
    }
    ColumnLayout {
        anchors.fill: parent; spacing: 10
        Text { text: okno.naslov; color: koren.paleta.besedilo; font.pixelSize: koren.px(15); font.bold: true; Layout.fillWidth: true; wrapMode: Text.WordWrap }
        Text { objectName: "shrBesedilo"; text: okno.besedilo; color: koren.paleta.besedilo; font.pixelSize: koren.px(13); Layout.fillWidth: true; wrapMode: Text.WordWrap
               Accessible.role: Accessible.StaticText; Accessible.name: text }
        Text { visible: okno.vprasanje !== ""; text: okno.vprasanje; color: koren.paleta.besedilo; font.pixelSize: koren.px(13); font.bold: true
               Layout.fillWidth: true; wrapMode: Text.WordWrap }
        RowLayout {
            Layout.alignment: Qt.AlignRight; spacing: 8
            Gumb {
                id: obdrzi; visible: okno.kopija; besedilo: koren.t("shrObdrzi")
                onKlik: koren.klic("shrambaObdrzi", [okno.id_], function () { okno.koncaj(koren.t("shrObdrzano", okno.zamenjave)) },
                                   function () { okno.napaka(null) })
            }
            Gumb {
                visible: okno.kopija; besedilo: koren.t("shrIzbrisi"); poudarjen: true
                onKlik: koren.klic("shrambaIzbrisi", [okno.id_], function (x) {
                    if (!x || !x.ok) { okno.napaka(x); return }
                    okno.koncaj(koren.t("shrIzbrisano", okno.zamenjave)); okno.izbrisano()
                }, function () { okno.napaka(null) })
            }
            Gumb { id: zapri; visible: !okno.kopija; besedilo: koren.t("shrZapri"); onKlik: okno.close() }
        }
    }
}
