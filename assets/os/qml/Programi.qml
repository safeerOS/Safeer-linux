// Panel Programi: vsi programi menija Start z ikonami, iskanje, skupine; klik zazene program. Kot na delovni povrsini
// WebKit (delovna.js): tudi shranjene spletne aplikacije, igre v oblaku (igreOblak) z namestitvijo iz uradnega vira,
// »Namesti programe …« (ponudniki, viri, GitHub) in »Prilagodi dock …« (vrstni red, dodaj, odstrani).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Steklo {
    id: panel
    property var vsi: []
    property string skupina: ""
    property string niz: ""
    readonly property var skupine: {
        var s = {}
        seznam.forEach(function (p) { if (p.skupina) s[p.skupina] = true })
        return Object.keys(s).sort()
    }
    // Na Linuxu Safeer OS pozna se igre v oblaku in ponudnike programov (metode mostu, ki jih Windows nima).
    readonly property bool linux: koren.platforma === "linux"
    property var oblak: []               // igreOblak: ponudniki iger v oblaku (nenamesceni so med programi)
    property var spletne: []             // spletne aplikacije, ki jih je uporabnik shranil (zacetek -> spletne)
    property string mapaPrenosov: ""
    // Ta racunalnik: programi + spletne aplikacije + nenamescene igre v oblaku (sestaviPrograme v delovna.js).
    readonly property var seznam: naprava ? vsi : vsi.concat(spletne.filter(function (s) { return s && s.url }).map(function (s, i) {
            return { id: "splet:" + i, ime: s.ime || s.url, skupina: "splet", url: s.url,
                     ikona: s.ikona && /^(data:image\/|https:)/.test(s.ikona) ? s.ikona : "" }
        })).concat(oblak.filter(function (o) { return o && o.id && !o.namescen }).map(function (o) {
            return { id: "oblak:" + o.id, ime: o.ime, skupina: "igre", ikona: "", ponudnikOblaka: o }
        }))
    readonly property var prikazani: seznam.filter(function (p) {
        return (!skupina || p.skupina === skupina) && (!niz || p.ime.toLowerCase().indexOf(niz.toLowerCase()) >= 0)
    })
    property string naprava: ""          // "" = ta racunalnik
    property string imeNaprave: ""
    property string stanje: ""           // "", "nalagam", "napaka", "prazno"
    property int zahteva: 0
    function nalozi() {
        var st = ++zahteva
        panel.vsi = []; panel.skupina = ""
        if (!naprava) {
            stanje = "nalagam"
            koren.klic("programiNamizja", [], function (s) { if (st !== zahteva) return; panel.vsi = s || []; stanje = "" })
            naloziOblak()
            return
        }
        stanje = "nalagam"
        koren.klic("programiNapraveNamizja", [naprava], function (r) {
            if (st !== zahteva) return
            if (!r || !r.ok) { stanje = "napaka"; return }
            panel.vsi = r.programi || []; stanje = panel.vsi.length ? "" : "prazno"
        }, function () { if (st === zahteva) stanje = "napaka" })
    }
    // Igre v oblaku (igreOblak) - na Linuxu; klice se tudi ob »zacetek«, ko namizje izve platformo.
    function naloziOblak() { if (linux) koren.klic("igreOblak", [], function (o) { panel.oblak = o || [] }) }
    function zazeni(p) {
        if (p.ponudnikOblaka) { meniOblaka.pokazi(p.ponudnikOblaka); return }
        if (p.url) { koren.klic("splet", [p.url]); return }
        if (!naprava) {
            koren.klic("zazeni", [p.id], function (ok) { if (!ok) koren.obvesti(koren.t("niUspelo")) })
            return
        }
        // Program naprave se odpre TUKAJ (naprava ga zazene in pretaka sliko), kot v Safeer OS.
        koren.obvesti(koren.t("odpiramZ", { ime: p.ime, naprava: imeNaprave }))
        koren.klic("odpriTukaj", [naprava, p.id], function (r) {
            if (!(r === true || (r && r.ok))) koren.obvesti(r && r.koda === "ni_locenega_zaslona" ? koren.t("niLocenega") : ((r && r.message) || koren.t("niUspelo")))
        })
    }
    // Imena skupin v jeziku vmesnika (prej samo slovensko - tudi v angleskem Safeer OS in na Windows).
    function imeSkupine(s) {
        var k = "sk_" + s, b = koren.t(k)
        return b !== k ? b : (s.charAt(0).toUpperCase() + s.slice(1))
    }

    ColumnLayout {
        anchors.fill: parent; anchors.margins: 18; spacing: 12
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            Text { text: koren.t("programi"); color: koren.paleta.besedilo; font.pixelSize: koren.px(16); font.bold: true }
            IzbiraNaprave {
                id: izbiraNaprave
                zmoznost: "programi"; naprave: koren.naprave
                onIzbrana: function (id, ime) { panel.naprava = id; panel.imeNaprave = ime; panel.nalozi() }
            }
            Gumb {
                // Ves loceni zaslon naprave tukaj (oddaljeno namizje) - tudi prek Global Linka.
                besedilo: koren.t("oddaljeno"); visible: panel.naprava !== ""
                onKlik: koren.klic("oddaljeniZaslon", [panel.naprava, panel.imeNaprave, "apps"], function (r) {
                    if (r && r.ok === false) koren.obvesti(r.message || koren.t("niUspelo")) })
            }
            // Od kod namescam programe (ponudniki, viri, GitHub) - kot gumb ob iskanju na delovni povrsini.
            GumbIkona {
                id: gumbNamesti
                objectName: "gumbNamesti"
                visible: panel.linux && panel.naprava === ""
                pot: "M12 4v11 M7 10l5 5 5-5 M5 20h14"; ime: koren.t("ppGumb"); velikostIkone: 17
                onKlik: panel.odpriPonudnike("")
            }
            Rectangle {
                Layout.fillWidth: true; height: 34; radius: 17
                color: koren.prekriv(0.07); border.color: koren.crta(0.12)
                Lupa { x: 12; anchors.verticalCenter: parent.verticalCenter; scale: 0.8 }
                TextField {
                    anchors.fill: parent; anchors.leftMargin: 36; anchors.rightMargin: 12
                    placeholderText: koren.t("isciProg"); placeholderTextColor: koren.paleta.medlo; color: koren.paleta.besedilo; font.pixelSize: koren.px(13)
                    background: Item {}
                    onTextChanged: panel.niz = text
                }
            }
        }
        Flow {
            Layout.fillWidth: true; spacing: 6
            Repeater {
                model: [""].concat(panel.skupine)
                delegate: Rectangle {
                    height: koren.px(26); width: n.implicitWidth + 22; radius: height / 2
                    color: panel.skupina === modelData ? koren.paleta.poudarek : (ms.containsMouse || activeFocus ? koren.prekriv(0.14) : koren.prekriv(0.07))
                    border.width: activeFocus ? 2 : 0; border.color: koren.paleta.fokus
                    activeFocusOnTab: true
                    Accessible.role: Accessible.RadioButton; Accessible.name: n.text; Accessible.checked: panel.skupina === modelData
                    Keys.onReturnPressed: panel.skupina = modelData
                    Keys.onEnterPressed: panel.skupina = modelData
                    Keys.onSpacePressed: panel.skupina = modelData
                    Behavior on color { ColorAnimation { duration: 140 } }
                    Text {
                        id: n; anchors.centerIn: parent; font.pixelSize: koren.px(12)
                        text: modelData === "" ? koren.t("vse")
                              : panel.imeSkupine(modelData)
                        color: panel.skupina === modelData ? koren.paleta.poudarekTemna : koren.paleta.besedilo
                    }
                    MouseArea { id: ms; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: panel.skupina = modelData }
                }
            }
        }
        GridView {
            id: mreza
            Layout.fillWidth: true; Layout.fillHeight: true
            clip: true
            readonly property int stolpcev: Math.max(3, Math.floor(width / 128))
            cellWidth: width / stolpcev; cellHeight: 112 + koren.px(14) - 14
            model: panel.prikazani
            // Tipkovnica in daljinec TV: puscice premikajo izbiro, Enter/preslednica zazene, tipka Meni odpre meni.
            activeFocusOnTab: true; keyNavigationEnabled: true; currentIndex: -1
            Accessible.role: Accessible.List; Accessible.name: koren.t("programi")
            onActiveFocusChanged: if (activeFocus && currentIndex < 0 && count > 0) currentIndex = 0
            onCountChanged: if (currentIndex >= count) currentIndex = count - 1
            function trenutni() { return currentIndex >= 0 && currentIndex < panel.prikazani.length ? panel.prikazani[currentIndex] : null }
            Keys.onReturnPressed: { var p = trenutni(); if (p) panel.zazeni(p) }
            Keys.onEnterPressed: { var p = trenutni(); if (p) panel.zazeni(p) }
            Keys.onSpacePressed: { var p = trenutni(); if (p) panel.zazeni(p) }
            Keys.onPressed: function (d) {
                var p = trenutni()
                if (p && !panel.naprava && (d.key === Qt.Key_Menu || (d.key === Qt.Key_F10 && (d.modifiers & Qt.ShiftModifier)))) {
                    if (p.ponudnikOblaka) meniOblaka.pokazi(p.ponudnikOblaka); else meniPrograma.pokazi(p)
                    d.accepted = true
                }
            }
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            add: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 200 } }
            Text {
                anchors.centerIn: parent; visible: panel.stanje !== "" && panel.stanje !== "nalagam" || (panel.stanje === "nalagam" && mreza.count === 0)
                text: panel.stanje === "nalagam" ? koren.t("nalagam") : panel.stanje === "napaka" ? koren.t("niOdgovorila") : koren.t("brezProgramov")
                color: koren.paleta.medlo; font.pixelSize: koren.px(13)
            }
            delegate: Item {
                width: mreza.cellWidth; height: mreza.cellHeight
                Rectangle {
                    id: ploscica
                    anchors.fill: parent; anchors.margins: 5; radius: 14
                    readonly property bool izbran: mreza.activeFocus && index === mreza.currentIndex
                    color: mp.containsMouse || izbran ? koren.prekriv(0.13) : koren.prekriv(0.05)
                    border.width: izbran ? 2 : 1
                    border.color: izbran ? koren.paleta.fokus : mp.containsMouse ? koren.poudarekA(0.55) : koren.crta(0.08)
                    Accessible.role: Accessible.ListItem; Accessible.name: modelData.ime
                    scale: mp.pressed ? 0.95 : (mp.containsMouse ? 1.04 : 1)
                    Behavior on scale { NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                    Behavior on color { ColorAnimation { duration: 140 } }
                    Image {
                        id: slika
                        source: modelData.ikona || ""
                        width: 40; height: 40; sourceSize: Qt.size(64, 64)
                        anchors.horizontalCenter: parent.horizontalCenter; y: 16
                        smooth: true; asynchronous: true
                    }
                    // Brez ikone (igra v oblaku, spletna aplikacija): crka namesto izmisljenega logotipa (kot delovna povrsina).
                    Rectangle {
                        visible: slika.status !== Image.Ready
                        anchors.fill: slika; radius: 10; color: koren.barvaVrste(modelData.ponudnikOblaka ? "program" : modelData.url ? "splet" : "program")
                        Text { anchors.centerIn: parent; text: (String(modelData.ime || "?").trim().charAt(0) || "?").toUpperCase()
                               color: koren.prekriv(1); font.pixelSize: koren.px(18); font.bold: true }
                    }
                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter; anchors.top: slika.bottom; anchors.topMargin: 10
                        width: parent.width - 12; horizontalAlignment: Text.AlignHCenter
                        text: modelData.ime; color: koren.paleta.besedilo; font.pixelSize: koren.px(12); elide: Text.ElideRight
                    }
                    Text {
                        visible: !!modelData.ponudnikOblaka
                        anchors.horizontalCenter: parent.horizontalCenter; anchors.bottom: parent.bottom; anchors.bottomMargin: 6
                        width: parent.width - 12; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
                        text: modelData.ponudnikOblaka ? "☁ " + koren.t("oblak") + " · " + modelData.ponudnikOblaka.ponudnik : ""
                        color: koren.paleta.medlo; font.pixelSize: koren.px(10)
                    }
                    MouseArea {
                        id: mp; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                        onClicked: function (m) {
                            if (m.button === Qt.LeftButton) panel.zazeni(modelData)
                            else if (modelData.ponudnikOblaka) meniOblaka.pokazi(modelData.ponudnikOblaka)
                            else if (!panel.naprava) meniPrograma.pokazi(modelData)
                        }
                    }
                }
            }
        }
    }

    // Desni klik na program tega racunalnika: Odpri, Dodaj v dock / Odstrani iz docka, Prilagodi dock … (kot prejsnja
    // delovna povrsina; tam je »Prilagodi dock …« v meniju plosc).
    Meni {
        id: meniPrograma
        objectName: "meniPrograma"
        property var p: null
        property bool plank: false
        property bool vDocku: false
        function pokazi(p) {
            meniPrograma.p = p
            koren.klic("dock", [], function (d) {
                meniPrograma.plank = !!(d && d.plank)
                meniPrograma.vDocku = !!(d && (d.programi || []).some(function (x) { return x.id === p.id }))
                meniPrograma.popup()
            }, function () { meniPrograma.plank = false; meniPrograma.popup() })
        }
        MeniVnos { text: koren.t("odpri"); onTriggered: panel.zazeni(meniPrograma.p) }
        MeniVnos { text: koren.t(meniPrograma.vDocku ? "dockOdstrani" : "dockDodaj"); visible: meniPrograma.plank && !!meniPrograma.p && !meniPrograma.p.url && !meniPrograma.p.ponudnikOblaka
                   onTriggered: {
                       var p = meniPrograma.p, dodaj = !meniPrograma.vDocku
                       koren.klic(dodaj ? "dockDodaj" : "dockOdstrani", [p.id], function (r) {
                           if (!r || r.ok === false) koren.obvesti(koren.t("niUspelo"))
                           else koren.obvesti(koren.t(dodaj ? "dockDodano" : "dockOdstranjeno", { ime: p.ime }))
                       }, function () { koren.obvesti(koren.t("niUspelo")) })
                   } }
        MeniCrta { visible: meniPrograma.plank && panel.linux }
        MeniVnos { text: koren.t("prilagodiDock"); objectName: "vnosPrilagodiDock"; visible: meniPrograma.plank && panel.linux
                   onTriggered: panel.urediDock() }
    }
    // Igra v oblaku, ki se ni namescena: kaj je, ali bo delovala, in namestitev iz ponudnikovega uradnega vira (samo na klik).
    Meni {
        id: meniOblaka
        objectName: "meniOblaka"
        property var o: ({})
        readonly property var zdr: o.zdruzljivost || {}
        function razlog() {
            var r = (meniOblaka.zdr.razlogi || [])[0]
            if (!r) return ""
            var k = "oblakRazlog_" + r.koda, b = koren.t(k, r)
            return b === k ? "" : b
        }
        function pokazi(o) { meniOblaka.o = o; meniOblaka.popup() }
        MeniVnos { text: koren.t("oblakOpis", { ponudnik: meniOblaka.o.ponudnik || "" }); enabled: false }
        MeniVnos { text: meniOblaka.zdr.stanje === "zdruzljivo" ? koren.t("oblakZdruzljivo")
                       : koren.t(meniOblaka.zdr.stanje === "ne" ? "oblakNe" : "oblakPoskusi", { razlog: meniOblaka.razlog() }); enabled: false }
        MeniCrta {}
        MeniVnos { text: koren.t("oblakNamesti", { ponudnik: meniOblaka.o.ponudnik || "" }); enabled: meniOblaka.zdr.stanje !== "ne"
                   onTriggered: panel.namestiOblak(meniOblaka.o) }
        MeniVnos { text: koren.t("oblakVec"); onTriggered: koren.klic("splet", [meniOblaka.o.stran]) }
    }
    property bool namescam: false
    function namestiOblak(o) {
        if (namescam) { koren.obvesti(koren.t("oblakZeNamescam")); return }
        namescam = true
        koren.obvesti(koren.t("oblakNamescam", { ime: o.ime, ponudnik: o.ponudnik }))
        koren.klic("igreOblakNamesti", [o.id], function (r) {
            panel.namescam = false
            if (r && r.ok) { koren.obvesti(koren.t("oblakNamesceno", { ime: o.ime })); panel.nalozi(); panel.skupina = "igre" }
            else {
                var k = "oblakNapaka_" + (r && r.napaka)
                koren.obvesti(koren.t(k) !== k ? koren.t(k) : koren.t("niUspelo"))
            }
        }, function () { panel.namescam = false; koren.obvesti(koren.t("niUspelo")) })
    }
    function urediDock() { dock.odpri(vsi) }
    function odpriPonudnike(zavihek) { ponudniki.odpri(mapaPrenosov); if (zavihek) ponudniki.izberiZavihek(zavihek) }
    UrediDock { id: dock }
    PonudnikiProgramov { id: ponudniki; onNamesceno: panel.nalozi() }
    // Zadetek »naprava« v iskanju na namizju: pokaze to napravo v tej plosci.
    function pokaziNapravo(id) { return izbiraNaprave.izberiId(id) }
}
