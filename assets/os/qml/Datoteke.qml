// Panel Datoteke: Nedavno, Koš, mape, pogoni; seznam z odpiranjem, »Pokaži v mapi«, preimenovanjem in Košem
// (z Razveljavi). Seznam se osvezi sam, ko se mapa spremeni zunaj Safeer OS.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Steklo {
    id: panel
    property var vir: ({ vrsta: "nedavno", pot: "" })
    property var elementi: []
    property var viri: []
    property string filter: ""
    property string stars: ""
    property int zahteva: 0
    // Naprava v Safeer Linku ("" = ta racunalnik): njene mape in datoteke (files.list prek Safeer Controla).
    property string naprava: ""
    property string imeNaprave: ""
    property var streznik: null
    property var pot: []                 // [{id, ime}] mape naprave od korena navzdol
    property var lokalniViri: []
    property string stanje: ""           // "", "napaka", "neDeli"
    readonly property var prikazani: elementi.filter(function (e) {
        return !filter || e.ime.toLowerCase().indexOf(filter.toLowerCase()) >= 0
    })

    function zacni(mape) {
        var v = [{ oznaka: koren.t("nedavno"), vir: { vrsta: "nedavno", pot: "" } },
                 { oznaka: koren.t("smeti"), vir: { vrsta: "smeti", pot: "smeti" } },
                 { naslov: koren.t("mape") }]
        mape.forEach(function (m) { v.push({ oznaka: koren.t(m.vrsta) !== m.vrsta ? koren.t(m.vrsta) : m.ime, vir: { vrsta: "lokalno", pot: m.pot } }) })
        v.push({ naslov: koren.t("naprave") })
        panel.viri = v; panel.lokalniViri = v
        koren.klic("nosilci", [], function (n) {
            var z = panel.lokalniViri.slice()
            ;(n || []).forEach(function (x) { z.push({ oznaka: x.ime + (x.ime === x.pot.replace("\\", "") ? "" : " (" + x.pot.replace("\\", "") + ")"), vir: { vrsta: "lokalno", pot: x.pot }, pogon: x }) })
            panel.lokalniViri = z
            if (!panel.naprava) panel.viri = z
        })
        odpri({ vrsta: "nedavno", pot: "" })
    }
    // Mapa tega racunalnika (npr. iz iskanja): najprej nazaj na »Ta racunalnik«, ce so bile odprte datoteke naprave.
    function odpriLokalno(pot) {
        naprava = ""; imeNaprave = ""; panel.pot = []; streznik = null; viri = lokalniViri
        odpri({ vrsta: "lokalno", pot: pot })
    }
    function odpri(v) { vir = v; filter = ""; poljeFilter.text = ""; seznam.currentIndex = seznam.activeFocus ? 0 : -1; nalozi(false) }
    function izberiNapravo(id, ime) {
        naprava = id; imeNaprave = ime; pot = []; streznik = null
        if (!id) { viri = lokalniViri; odpri({ vrsta: "nedavno", pot: "" }); return }
        viri = [{ naslov: koren.t("mapeNaprave") }]
        odpri({ vrsta: "naprava", pot: "" })
    }
    function vnosNaprave(d) {
        var mapa = d.type === "folder" || d.vrsta === "folder" || d.vrsta === "mapa"
        var ime = d.name || d.ime || ""
        return { ime: ime, id: d.id || "", mapa: mapa, velikost: d.size || d.velikost || 0,
                 spremenjeno: d.mtime || d.spremenjeno || 0, vrsta: mapa ? "mapa" : (d.vrsta || ""), pot: d.id || "" }
    }
    function nalozi(tiho) {
        var st = ++zahteva
        if (!tiho) elementi = []
        var konec = function (r) {
            if (st !== zahteva) return
            if (vir.vrsta === "lokalno") { elementi = (r && r.elementi) || []; stars = (r && r.stars) || "" }
            else if (vir.vrsta === "smeti") { elementi = (r && r.elementi) || []; stars = "" }
            else { elementi = r || []; stars = "" }
        }
        stanje = ""
        if (vir.vrsta === "naprava") {
            koren.klic("datotekeNaprave", [naprava, vir.pot], function (r) {
                if (st !== zahteva) return
                if (!r || !r.ok) { stanje = "napaka"; elementi = []; return }
                if (!r.shared) { stanje = "neDeli"; elementi = []; return }
                if (r.server) streznik = r.server
                var vnosi = (r.items || []).map(panel.vnosNaprave)
                vnosi.sort(function (a, b) { return a.mapa !== b.mapa ? (a.mapa ? -1 : 1) : a.ime.toLowerCase().localeCompare(b.ime.toLowerCase()) })
                elementi = vnosi
                if (vir.pot === "") {   // koren naprave: mape tudi v stranski vrstici
                    viri = [{ naslov: koren.t("mapeNaprave") }].concat(vnosi.filter(function (e) { return e.mapa })
                        .map(function (e) { return { oznaka: e.ime, vir: { vrsta: "naprava", pot: e.id }, ime: e.ime } }))
                }
            }, function () { if (st === zahteva) { stanje = "napaka"; elementi = [] } })
            return
        }
        if (vir.vrsta === "lokalno") { koren.klic("mapa", [vir.pot], konec); koren.klic("spremljajMapo", [vir.pot]) }
        else if (vir.vrsta === "smeti") koren.klic("smeti", [], konec)
        else koren.klic("nedavne", [], konec)
    }
    function odpriElement(e) {
        if (vir.vrsta === "smeti") return
        if (vir.vrsta === "naprava") {
            if (e.mapa) { pot = pot.concat([{ id: e.id, ime: e.ime }]); odpri({ vrsta: "naprava", pot: e.id }); return }
            // Najbolj gladko: datoteka pride sem in jo odpre program tega racunalnika (fotografije, video, urejanje).
            // Ce prenos ni mogoc, jo odpre program naprave prek oddaljenega namizja (lastnik, 13. 10. 2026).
            if (streznik && streznik.base_url) odpriTukaj(e)
            else odpriSProgramomNaprave(e)
            return
        }
        if (e.mapa) odpri({ vrsta: "lokalno", pot: e.pot })
        else koren.klic("odpriDatoteko", [e.pot])
    }
    function odpriTukaj(e) {
        koren.obvesti(koren.t("prenasam", { ime: e.ime }))
        // 5. argument (imena map do datoteke) uporabi Linux za mesto delovne kopije; Windows ga prezre.
        var mape = pot.map(function (p) { return p.ime })
        koren.klic("prenesiDatotekoNaprave", [naprava, e.id, e.ime, streznik, mape], function (r) {
            if (!r || !r.ok) { koren.obvesti(koren.t("niUspelo")); return }
            // Teamwork (Linux): kako se je odprla in kdo jo se ureja.
            var b = []
            if (r.nacin === "podprt" && r.program) b.push(koren.t("odprtoV", { program: r.program, naprava: imeNaprave }))
            if (r.nacin === "pretok" && r.odprto) b.push(koren.t("odprtoNaNapravi", { naprava: imeNaprave }))
            if (r.teamwork && r.teamwork.drugi && r.teamwork.drugi.length)
                b.push(koren.t("teamworkTudi", { drugi: r.teamwork.drugi.map(function (x) { return x === "@tukaj" ? imeNaprave : x }).join(", ") }))
            if (b.length) koren.obvesti(b.join(" "))
        })
    }
    function odpriSProgramomNaprave(e) {
        // Prek oddaljenega namizja: naprava datoteko odpre na svojem LOCENEM zaslonu - njen uporabnik tega ne opazi.
        koren.obvesti(koren.t("odpiramZ", { ime: e.ime, naprava: imeNaprave }))
        koren.klic("odpriDatotekoTukaj", [naprava, e.id], function (r) {
            if (!(r && r.ok)) koren.obvesti(r && r.koda === "ni_locenega_zaslona" ? koren.t("niLocenega") : ((r && r.message) || koren.t("niUspelo")))
        })
    }
    function vKos(e) {
        koren.klic("vSmeti", [e.pot], function (r) {
            if (!r || !r.ok) { koren.obvesti(koren.t("niUspelo")); return }
            panel.nalozi(true)
            koren.obvesti(koren.t("vKosPoslano", { ime: e.ime }), r.id ? koren.t("razveljavi") : "",
                          function () { koren.klic("obnoviIzSmeti", [r.id], function () { panel.nalozi(true) }) })
        })
    }
    function prazno() {
        if (stanje === "napaka") return koren.t("niOdgovorila")
        if (stanje === "neDeli") return koren.t("neDeli")
        return vir.vrsta === "smeti" ? koren.t("kosPrazen") : vir.vrsta === "nedavno" ? koren.t("niNedavnih") : koren.t("prazno")
    }

    RowLayout {
        anchors.fill: parent; anchors.margins: 14; spacing: 12
        // ---------------- viri
        // Naslov in izbira naprave nad seznamom virov (ne glava ListViewa: ta se ob vecjem besedilu sistema
        // odreze na vrhu - posnetek pri 150 %, 15. 10. 2026).
        ColumnLayout {
            Layout.fillWidth: false; Layout.fillHeight: true; spacing: 8
            Layout.preferredWidth: Math.min(koren.px(170), panel.width * 0.34); Layout.maximumWidth: Layout.preferredWidth
            Text { text: koren.t("datoteke"); color: koren.paleta.besedilo; font.pixelSize: koren.px(16); font.bold: true; leftPadding: 4 }
            IzbiraNaprave {
                Layout.fillWidth: true; zmoznost: "datoteke"; naprave: koren.naprave
                onIzbrana: function (id, ime) { panel.izberiNapravo(id, ime) }
            }
            ListView {
                id: viriSeznam
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.topMargin: 6
                clip: true; model: panel.viri; boundsBehavior: Flickable.StopAtBounds
                // Tipkovnica in daljinec TV (puscice): gor/dol preskoci naslove skupin, Enter ali preslednica odpre vir.
                activeFocusOnTab: true; currentIndex: -1
                Accessible.role: Accessible.List; Accessible.name: koren.t("mape")
                function izberiVir(i) {
                    var m = panel.viri[i]
                    if (!m || !m.vir) return
                    if (m.vir.vrsta === "naprava") panel.pot = [{ id: m.vir.pot, ime: m.ime }]
                    panel.odpri(m.vir)
                }
                function premakni(smer) {
                    for (var i = currentIndex + smer; i >= 0 && i < panel.viri.length; i += smer)
                        if (!panel.viri[i].naslov) { currentIndex = i; positionViewAtIndex(i, ListView.Contain); return }
                }
                onActiveFocusChanged: if (activeFocus && currentIndex < 0) premakni(1)
                Keys.onDownPressed: premakni(1)
                Keys.onUpPressed: premakni(-1)
                Keys.onReturnPressed: izberiVir(currentIndex)
                Keys.onEnterPressed: izberiVir(currentIndex)
                Keys.onSpacePressed: izberiVir(currentIndex)
                Keys.onRightPressed: seznam.forceActiveFocus()
                delegate: Item {
                    width: viriSeznam.width; height: koren.px(modelData.naslov ? 30 : 32)
                    Text {
                        visible: !!modelData.naslov; text: (modelData.naslov || "").toUpperCase()
                        color: Qt.darker(koren.paleta.medlo, 1.15); font.pixelSize: koren.px(10); font.letterSpacing: 1; anchors.bottom: parent.bottom; anchors.bottomMargin: 6; x: 6
                    }
                    Rectangle {
                        visible: !modelData.naslov
                        anchors.fill: parent; anchors.margins: 1; radius: 9
                        readonly property bool izbran: !!modelData.vir && panel.vir.vrsta === modelData.vir.vrsta && panel.vir.pot === modelData.vir.pot
                        color: izbran ? koren.poudarekA(0.18) : (mv.containsMouse ? koren.prekriv(0.08) : "transparent")
                        border.width: viriSeznam.activeFocus && index === viriSeznam.currentIndex ? 2 : 0
                        border.color: koren.paleta.fokus
                        Accessible.role: Accessible.ListItem; Accessible.name: modelData.oznaka || ""
                        Behavior on color { ColorAnimation { duration: 120 } }
                        Text { text: modelData.oznaka || ""; color: parent.izbran ? Qt.lighter(koren.paleta.poudarek, 1.35) : koren.paleta.besedilo; font.pixelSize: koren.px(13); elide: Text.ElideRight
                               width: parent.width - 16; x: 10; anchors.verticalCenter: parent.verticalCenter }
                        MouseArea { id: mv; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: { viriSeznam.currentIndex = index; viriSeznam.izberiVir(index) } }
                    }
                }
            }
        }
        Rectangle { Layout.fillHeight: true; width: 1; color: koren.prekriv(0.08) }
        // ---------------- vsebina
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 8
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                Gumb { besedilo: "↑"; visible: panel.stars !== "" || (panel.vir.vrsta === "naprava" && panel.pot.length > 0)
                       onKlik: {
                           if (panel.vir.vrsta === "naprava") {
                               var p = panel.pot.slice(0, -1); panel.pot = p
                               panel.odpri({ vrsta: "naprava", pot: p.length ? p[p.length - 1].id : "" })
                           } else panel.odpri({ vrsta: "lokalno", pot: panel.stars })
                       } }
                Text {
                    Layout.fillWidth: true; color: koren.paleta.besedilo; font.pixelSize: koren.px(12); elide: Text.ElideLeft
                    text: panel.vir.vrsta === "naprava" ? [panel.imeNaprave].concat(panel.pot.map(function (x) { return x.ime })).join("  ›  ")
                        : panel.vir.vrsta === "lokalno" ? koren.kratkaPot(panel.vir.pot) : panel.vir.vrsta === "smeti" ? koren.t("smeti") : koren.t("nedavno")
                }
                Gumb { besedilo: koren.t("izprazni"); visible: panel.vir.vrsta === "smeti" && panel.elementi.length > 0; onKlik: potrdi.open() }
                Gumb { besedilo: "+ " + koren.t("novaMapa"); visible: panel.vir.vrsta === "lokalno"
                       onKlik: koren.klic("novaMapa", [panel.vir.pot, koren.t("novaMapa")], function (r) {
                           if (r && r.ok) { panel.nalozi(true); preimenovanje.zacni({ ime: r.ime, pot: r.pot }) } else koren.obvesti(koren.t("niUspelo")) }) }
                Rectangle {
                    width: Math.min(170, Math.max(96, seznam.width * 0.34)); height: 30; radius: 15; color: koren.prekriv(0.07); border.color: koren.crta(0.12)
                    TextField {
                        id: poljeFilter
                        anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 10
                        placeholderText: koren.t("filter"); placeholderTextColor: koren.paleta.medlo; color: koren.paleta.besedilo; font.pixelSize: koren.px(12)
                        background: Item {}
                        onTextChanged: panel.filter = text
                    }
                }
            }
            ListView {
                id: seznam
                Layout.fillWidth: true; Layout.fillHeight: true
                // Tipkovnica (AGENTS: dostopnost): puscice, Enter odpre, Delete v Smeti, F2 preimenuj, tipka Meni/Shift+F10.
                activeFocusOnTab: true; keyNavigationEnabled: true; currentIndex: -1
                Accessible.role: Accessible.List; Accessible.name: koren.t("datoteke")
                onCountChanged: if (currentIndex >= count) currentIndex = count - 1
                function izbran() { return currentIndex >= 0 && currentIndex < panel.prikazani.length ? panel.prikazani[currentIndex] : null }
                onActiveFocusChanged: if (activeFocus && currentIndex < 0 && count > 0) currentIndex = 0
                Keys.onReturnPressed: { var e = izbran(); if (e) panel.odpriElement(e) }
                Keys.onEnterPressed: { var e = izbran(); if (e) panel.odpriElement(e) }
                Keys.onLeftPressed: viriSeznam.forceActiveFocus()
                Keys.onDeletePressed: { var e = izbran(); if (e && (panel.vir.vrsta === "lokalno" || panel.vir.vrsta === "nedavno")) panel.vKos(e) }
                Keys.onPressed: function (d) {
                    var e = izbran()
                    if (!e) return
                    if (d.key === Qt.Key_F2 && panel.vir.vrsta === "lokalno") { preimenovanje.zacni(e); d.accepted = true }
                    else if (d.key === Qt.Key_Menu || (d.key === Qt.Key_F10 && (d.modifiers & Qt.ShiftModifier))) {
                        meni.e = e; var it = currentItem
                        meni.popup(it, 40, it ? it.height : 0); d.accepted = true
                    }
                }
                // Ozka plosca (aplikacija v manjsem oknu, 14. 10. 2026: pri 1080 px ime ni bilo vidno): stolpca
                // Spremenjeno in Velikost se umakneta imenu.
                readonly property bool ozko: width < 360
                readonly property bool zeloOzko: width < 260
                readonly property real stolpci: (zeloOzko ? 0 : koren.px(80)) + (ozko ? 0 : koren.px(110))
                clip: true; model: panel.prikazani; boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                header: Row {
                    height: 26; spacing: 0
                    Text { text: koren.t("ime"); color: Qt.darker(koren.paleta.medlo, 1.15); font.pixelSize: koren.px(11); width: seznam.width - seznam.stolpci }
                    Text { text: koren.t("velikost"); color: Qt.darker(koren.paleta.medlo, 1.15); font.pixelSize: koren.px(11); width: koren.px(80); visible: !seznam.zeloOzko }
                    Text { text: koren.t("spremenjeno"); color: Qt.darker(koren.paleta.medlo, 1.15); font.pixelSize: koren.px(11); width: koren.px(110); visible: !seznam.ozko }
                }
                delegate: Rectangle {
                    width: seznam.width; height: koren.px(34); radius: 8
                    color: index === seznam.currentIndex && seznam.activeFocus ? koren.poudarekA(0.2)
                         : md.containsMouse ? koren.prekriv(0.08) : "transparent"
                    Accessible.role: Accessible.ListItem; Accessible.name: modelData.ime
                    Behavior on color { ColorAnimation { duration: 100 } }
                    Row {
                        anchors.verticalCenter: parent.verticalCenter; x: 6; spacing: 0
                        Row {
                            width: seznam.width - seznam.stolpci - 6; spacing: 8
                            Rectangle {
                                width: koren.px(22); height: koren.px(22); radius: 6; anchors.verticalCenter: parent.verticalCenter
                                color: koren.barvaVrste(modelData.mapa ? "mapa" : modelData.vrsta)
                                Text { anchors.centerIn: parent; color: koren.prekriv(1); font.pixelSize: koren.px(10); font.bold: true
                                       text: modelData.mapa ? "▣" : (modelData.ime.split(".").pop() || "?").slice(0, 3).toUpperCase() }
                            }
                            Text { text: modelData.ime; color: koren.paleta.besedilo; font.pixelSize: koren.px(13); elide: Text.ElideRight
                                   width: parent.width - koren.px(22) - 10; anchors.verticalCenter: parent.verticalCenter }
                        }
                        Text { text: modelData.mapa ? "" : koren.velikost(modelData.velikost); color: koren.paleta.medlo; font.pixelSize: koren.px(12); width: koren.px(80); visible: !seznam.zeloOzko
                               anchors.verticalCenter: parent.verticalCenter }
                        Text { text: koren.cas(modelData.spremenjeno || modelData.izbrisano); color: koren.paleta.medlo; font.pixelSize: koren.px(12); width: koren.px(110); visible: !seznam.ozko
                               anchors.verticalCenter: parent.verticalCenter }
                    }
                    MouseArea {
                        id: md; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
                        onDoubleClicked: panel.odpriElement(modelData)
                        onClicked: function (m) {
                            seznam.currentIndex = index; seznam.forceActiveFocus()
                            if (m.button === Qt.RightButton) { meni.e = modelData; meni.popup() }
                        }
                    }
                }
                Text {
                    anchors.centerIn: parent; visible: seznam.count === 0
                    text: panel.prazno(); color: koren.paleta.medlo; font.pixelSize: koren.px(13)
                }
            }
        }
    }

    // Meni v slogu namizja (kot meni ozadja v Namizje.qml), ne sivi privzeti meni Qt.
    component MeniVnos: MenuItem {
        contentItem: Text { text: parent.text; color: koren.paleta.besedilo; font.pixelSize: koren.px(13); leftPadding: 6 }
        background: Rectangle { radius: 8; color: parent.highlighted ? koren.poudarekA(0.22) : "transparent" }
    }
    Menu {
        id: meni
        background: Rectangle { implicitWidth: 230; radius: 12; color: koren.paleta.vnos; border.color: koren.crta(0.14) }
        property var e: null
        MeniVnos { text: koren.t("odpri"); visible: panel.vir.vrsta !== "smeti"; height: visible ? implicitHeight : 0; onTriggered: panel.odpriElement(meni.e) }
        MeniVnos { text: koren.t("odpriSProgramom", { naprava: panel.imeNaprave })
                   visible: panel.vir.vrsta === "naprava" && !!meni.e && !meni.e.mapa; height: visible ? implicitHeight : 0
                   onTriggered: panel.odpriSProgramomNaprave(meni.e) }
        // Kot Datoteke na prejsnji delovni povrsini (delovna.js): Odpri z … in Poslji na napravo … (14. 10. 2026).
        MeniVnos { text: koren.t("odpriZ"); visible: panel.lokalnaDatoteka(meni.e); height: visible ? implicitHeight : 0
                   onTriggered: izbirnik.odpriZ(meni.e) }
        MeniVnos { text: koren.t("posljiNaNapravo"); visible: panel.lokalnaDatoteka(meni.e); height: visible ? implicitHeight : 0
                   onTriggered: izbirnik.poslji(meni.e) }
        MeniVnos { text: koren.t("pretvoriV"); visible: panel.lokalnaDatoteka(meni.e); height: visible ? implicitHeight : 0
                   onTriggered: izbirnik.pretvori(meni.e) }
        MeniVnos { text: koren.t("pokazi"); visible: panel.vir.vrsta === "lokalno" || panel.vir.vrsta === "nedavno"; height: visible ? implicitHeight : 0; onTriggered: koren.klic("pokaziVMapi", [meni.e.pot]) }
        MeniVnos { text: koren.t("preimenuj"); visible: panel.vir.vrsta === "lokalno"; height: visible ? implicitHeight : 0; onTriggered: preimenovanje.zacni(meni.e) }
        MeniVnos { text: koren.t("vKos"); visible: panel.vir.vrsta === "lokalno" || panel.vir.vrsta === "nedavno"; height: visible ? implicitHeight : 0; onTriggered: panel.vKos(meni.e) }
        MeniVnos { text: koren.t("obnovi"); visible: panel.vir.vrsta === "smeti"; height: visible ? implicitHeight : 0
                   onTriggered: koren.klic("obnoviIzSmeti", [meni.e.id], function (r) { if (r && r.ok) panel.nalozi(true); else koren.obvesti(koren.t("niUspelo")) }) }
    }

    Popup {
        id: preimenovanje
        property var e: null
        anchors.centerIn: parent; modal: true; focus: true; padding: 18; width: 380
        background: Rectangle { radius: 16; color: koren.paleta.vnos; border.color: koren.crta(0.14) }
        function zacni(e) { preimenovanje.e = e; novoIme.text = e.ime; open(); novoIme.forceActiveFocus(); novoIme.selectAll() }
        function shrani() {
            koren.klic("preimenujDatoteko", [preimenovanje.e.pot, novoIme.text], function (r) {
                if (r && r.ok) panel.nalozi(true); else koren.obvesti(koren.t("niUspelo"))
            })
            close()
        }
        ColumnLayout {
            anchors.fill: parent; spacing: 12
            Text { text: koren.t("preimenuj"); color: koren.paleta.besedilo; font.pixelSize: koren.px(15); font.bold: true }
            TextField { id: novoIme; Layout.fillWidth: true; color: koren.paleta.besedilo; font.pixelSize: koren.px(14)
                        background: Rectangle { radius: 8; color: koren.prekriv(0.08); border.color: koren.paleta.poudarek }
                        Keys.onReturnPressed: preimenovanje.shrani() }
            RowLayout { Layout.alignment: Qt.AlignRight; spacing: 8
                Gumb { besedilo: koren.t("preklici"); onKlik: preimenovanje.close() }
                Gumb { besedilo: koren.t("shrani"); poudarjen: true; onKlik: preimenovanje.shrani() } }
        }
    }

    function lokalnaDatoteka(e) { return !!e && !e.mapa && (vir.vrsta === "lokalno" || vir.vrsta === "nedavno") }

    // Izbira programa (Odpri z …) ali naprave (Poslji na napravo …) za eno datoteko.
    Popup {
        id: izbirnik
        property string naslov: ""
        property var moznosti: []        // [{ ime, opis, ob }]
        anchors.centerIn: parent; modal: true; focus: true; padding: 18; width: 400
        background: Rectangle { radius: 16; color: koren.paleta.vnos; border.color: koren.crta(0.14) }
        function pokazi(n, m) { naslov = n; moznosti = m; open() }
        function odpriZ(e) {
            koren.klic("programiZaDatoteko", [e.pot], function (r) {
                var p = (r && r.ok && r.programi) || []
                if (!p.length) { koren.obvesti(koren.t("niUspelo")); return }
                pokazi(koren.t("odpriZ") + " · " + e.ime, p.map(function (x) {
                    return { ime: x.ime, opis: x.privzet ? koren.t("privzetProgram") : "",
                             ob: function () { koren.klic("odpriZ", [[e.pot], x.id, false], function (o) { if (!(o && o.ok)) koren.obvesti(koren.t("niUspelo")) }) } }
                }))
            })
        }
        // Pretvori v … (core/os_pretvorba_datotek.py): nova datoteka ob izvirniku, izvirnik ostane.
        function pretvori(e) {
            var ORODJA = { slika: "ImageMagick", zvok: "ffmpeg", besedilo: "LibreOffice", preglednica: "LibreOffice", predstavitev: "LibreOffice" }
            koren.klic("pretvorbaMoznosti", [e.pot], function (m) {
                if (!m || !m.cilji || !m.cilji.length) { koren.obvesti(koren.t("ptdNiMogoce")); return }
                if (!m.orodje) { koren.obvesti(koren.t("ptdNiOrodja", { orodje: ORODJA[m.skupina] || "?" })); return }
                pokazi(koren.t("pretvoriV") + " · " + e.ime, m.cilji.map(function (c) {
                    return { ime: c.toUpperCase(), opis: "", ob: function () {
                        koren.obvesti(koren.t("ptdPretvarjam", { ime: e.ime, cilj: c.toUpperCase() }))
                        koren.klic("pretvoriDatoteko", [e.pot, c], function (r) {
                            if (!r || !r.ok) { koren.obvesti(koren.t("ptdNapaka")); return }
                            pretvarjanje.dodaj(r.id)
                        }, function () { koren.obvesti(koren.t("ptdNapaka")) })
                    } }
                }))
            })
        }
        function poslji(e) {
            koren.klic("napraveZaPosiljanje", [], function (n) {
                n = (n || []).filter(function (x) { return x && x.id })
                if (!n.length) { koren.obvesti(koren.t("posNiNaprav")); return }
                pokazi(koren.t("posljiNaNapravo") + " · " + e.ime, n.map(function (x) {
                    return { ime: x.ime, opis: "", ob: function () { panel.posljiNapravi(x, e) } }
                }))
            })
        }
        ColumnLayout {
            anchors.fill: parent; spacing: 10
            Text { text: izbirnik.naslov; color: koren.paleta.besedilo; font.pixelSize: koren.px(15); font.bold: true; elide: Text.ElideMiddle; Layout.fillWidth: true }
            Repeater {
                model: izbirnik.moznosti
                delegate: Rectangle {
                    Layout.fillWidth: true; height: 40; radius: 10
                    color: mi.containsMouse || activeFocus ? koren.poudarekA(0.2) : koren.prekriv(0.05)
                    border.width: activeFocus ? 2 : 0; border.color: koren.paleta.fokus
                    activeFocusOnTab: true
                    Keys.onEnterPressed: { izbirnik.close(); modelData.ob() }
                    Keys.onSpacePressed: { izbirnik.close(); modelData.ob() }
                    Accessible.role: Accessible.Button; Accessible.name: modelData.ime
                    Keys.onReturnPressed: { izbirnik.close(); modelData.ob() }
                    Row { anchors.verticalCenter: parent.verticalCenter; x: 12; spacing: 10
                        Text { text: modelData.ime; color: koren.paleta.besedilo; font.pixelSize: koren.px(13) }
                        Text { text: modelData.opis; color: koren.paleta.medlo; font.pixelSize: koren.px(11); visible: text !== "" } }
                    MouseArea { id: mi; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: { izbirnik.close(); modelData.ob() } }
                }
            }
            Gumb { Layout.alignment: Qt.AlignRight; besedilo: koren.t("zapri"); onKlik: izbirnik.close() }
        }
    }

    // Datoteko odda Safeer Control (kot »Poslji datoteko« v njem); tu spremljamo napredek do konca.
    function posljiNapravi(naprava, e) {
        koren.obvesti(koren.t("posPosiljam", { naprava: naprava.ime, ime: e.ime }))
        koren.klic("posljiNapravi", [naprava.id, [e.pot]], function (r) {
            if (!r || !r.ok) { koren.obvesti(koren.t("posNapaka", { naprava: naprava.ime })); return }
            if (r.stanje === "posiljam") posiljanje.dodaj(r.id, naprava, e.ime)
            else koren.obvesti(koren.t("posPoslano", { naprava: naprava.ime, ime: e.ime }))
        }, function () { koren.obvesti(koren.t("posNapaka", { naprava: naprava.ime })) })
    }
    // Vec pretvorb in posiljanj hkrati: vsako opravilo ima svoj zapis (pregled 14. 10.: en id je prejsnjega prepisal).
    Timer {
        id: pretvarjanje
        property var dela: ({})        // id -> stevilo napak
        interval: 700; repeat: true
        function dodaj(id) { var d = dela; d[id] = 0; dela = d; start() }
        function koncaj(id) { var d = dela; delete d[id]; dela = d; if (!Object.keys(d).length) stop() }
        onTriggered: Object.keys(dela).forEach(function (id) {
            koren.klic("pretvorbaDatotekeStanje", [id], function (r) {
                if (!(id in pretvarjanje.dela)) return
                if (!r || !r.ok || r.stanje === "napaka") {
                    if (r && r.ok === false && ++pretvarjanje.dela[id] <= 3) return
                    pretvarjanje.koncaj(id); koren.obvesti(koren.t("ptdNapaka")); return
                }
                if (r.stanje !== "koncano") return
                pretvarjanje.koncaj(id)
                if (panel.vir.vrsta === "lokalno") panel.nalozi(true)
                var pot = r.pot_izhoda || ""
                koren.obvesti(koren.t("ptdKoncano", { izhod: String(r.izhod || "").split("/").pop() }),
                              pot ? koren.t("pokazi") : "", pot ? function () { koren.klic("pokaziVMapi", [pot]) } : null)
            })
        })
    }
    Timer {
        id: posiljanje
        property var dela: ({})        // id -> { naprava, ime, napak }
        interval: 800; repeat: true
        function dodaj(id, naprava, ime) { var d = dela; d[id] = { naprava: naprava, ime: ime, napak: 0 }; dela = d; start() }
        function koncaj(id) { var d = dela; delete d[id]; dela = d; if (!Object.keys(d).length) stop() }
        onTriggered: Object.keys(dela).forEach(function (id) {
            koren.klic("posljiStanje", [id], function (r) {
                var o = posiljanje.dela[id]
                if (!o) return
                if (!r || !r.ok) { if (++o.napak > 5) { posiljanje.koncaj(id); koren.obvesti(koren.t("posNapaka", { naprava: o.naprava.ime })) } return }
                if (r.stanje === "posiljam") return
                posiljanje.koncaj(id)
                koren.obvesti(r.stanje === "poslano" ? koren.t("posPoslano", { naprava: o.naprava.ime, ime: o.ime })
                                                     : koren.t("posNapaka", { naprava: o.naprava.ime }))
            })
        })
    }


    Popup {
        id: potrdi
        anchors.centerIn: parent; modal: true; focus: true; padding: 18; width: 400
        background: Rectangle { radius: 16; color: koren.paleta.vnos; border.color: koren.crta(0.14) }
        ColumnLayout {
            anchors.fill: parent; spacing: 14
            Text { text: koren.t("izprazniVpr"); color: koren.paleta.besedilo; font.pixelSize: koren.px(14); wrapMode: Text.WordWrap; Layout.fillWidth: true }
            RowLayout { Layout.alignment: Qt.AlignRight; spacing: 8
                Gumb { besedilo: koren.t("preklici"); onKlik: potrdi.close() }
                Gumb { besedilo: koren.t("izprazni"); poudarjen: true
                       onKlik: { koren.klic("izprazniSmeti", [], function () { panel.nalozi(true) }); potrdi.close() } } }
        }
    }
}
