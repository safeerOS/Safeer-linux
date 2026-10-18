// Namizje Safeer OS za Windows in Linux (Qt Quick). Ista dela kot na Linuxu: iskanje, Medijski center, datoteke, programi,
// Safeer Link. Podatki pridejo iz Pythona prek »Most« (iste metode kot spletna stran na Linuxu).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Shapes
import "../izhod.js" as Izhod
import "../besedila-namizja.js" as Besedila
import "../iskanje.js" as Iskanje

Item {
    id: koren
    width: 1440; height: 860

    // ------------------------------------------------------------------ most in besedila
    property var cakajo: ({})
    function klic(metoda, argumenti, ok, napaka) {
        var id = Most.klic(metoda, JSON.stringify(argumenti || []))
        cakajo[id] = { ok: ok, napaka: napaka }
    }
    Connections {
        target: Most
        function onOdgovor(id, uspeh, podatki) {
            var c = koren.cakajo[id]; if (!c) return
            delete koren.cakajo[id]
            var v = null
            try { v = JSON.parse(podatki) } catch (e) {}
            if (uspeh && c.ok) c.ok(v)
            else if (!uspeh && c.napaka) c.napaka(v)
        }
        function onDogodek(vrsta, podatki) {
            var p = null
            try { p = JSON.parse(podatki) } catch (e) {}
            if (vrsta === "datoteke" && p && p.pot && p.pot === datoteke.pogledVira()) datoteke.nalozi(true)
            if (vrsta === "nosilci") datoteke.osveziNosilce()
            if (vrsta === "govor" && p) govor.dogodek(p)
            if (vrsta === "videz" && p) koren.uporabiVidez(p)
            if (vrsta === "jezik" && p && p.jezik) koren.nastaviJezik(p.jezik)   // izbira v vodniku ob prvem zagonu
            if (vrsta === "iskanjeOdDrugod" && p && p.q) { polje.text = p.q; polje.forceActiveFocus() }
            if (vrsta === "predvajalnik" && p) koren.medij = p
            if (vrsta === "medijskaKnjiznica") koren.osveziMedij()
            if (vrsta === "prilagodi") prilagodi.odpri()   // Nastavitve Safeer OS -> Namizje -> Prilagodi namizje
            if (vrsta === "programi") programi.osveziTiho()   // program namescen ali odstranjen
            if (vrsta === "priljubljeno" && p) koren.nastaviPriljubljeno(p)   // tudi sprememba na delovni povrsini WebKit
            if (vrsta === "pokaziNaNamizju" && p) koren.pokaziNaNamizju(p)
            if (vrsta === "sporocilaStevilo" && p) koren.sporocilNeprebranih = Math.max(0, Number(p.n) || 0)
            // Tiha preverba posodobitev (safeer_os._posodobitve_tiho): opomba pod iskanjem, kot na Domov aplikacije.
            if (vrsta === "posodobitev" && p) koren.posodobitev = (p.nove || []).length ? String(p.opis || "") : ""
        }
    }
    property string jezik: "sl"
    // Barve iz assets/os/tokens.css (en vir z vmesnikom, Spletom, delovno povrsino in Controlom): paleto poslje
    // core/os_lupina.paleta ob »zacetek« in dogodku »videz«. Spodaj je le rezerva do prvega odgovora (iste vrednosti,
    // preverja tests/test_namizje_celota.py), da prvi izris ni v drugih barvah.
    property var paleta: ({ poudarek: "#8ac7ff", poudarekTemna: "#0b1424", besedilo: "#eaf2ff", medlo: "#afbed4",
                            tise: "#93a9c4", vnos: "#121d2d", ozadje: "#0b1424", ozadje2: "#152a3d", fokus: "#9dceff",
                            opozorilo: "#ffcf8a", rdeca: "#ff6b6b",
                            karticaRgb: [0.0627, 0.102, 0.1686], poudarekRgb: [0.5412, 0.7804, 1], prekrivRgb: [1, 1, 1],
                            robRgb: [0.8275, 0.898, 1], robA: 0.23, vrste: ({}), kontrast: false, merilo: 1 })
    property real zameglitev: 1.0
    property real prosojnost: 0.55
    // Kontrast (tema sistema »Kontrast«): plosce skoraj neprosojne in brez zameglitve, robovi mocnejsi - kot
    // »Manj prosojnosti« na delovni povrsini WebKit.
    readonly property bool kontrast: !!paleta.kontrast
    readonly property real prosojnostPlosc: kontrast ? Math.max(0.94, prosojnost) : prosojnost
    readonly property real zameglitevPlosc: kontrast ? 0 : zameglitev
    // Velikost besedila sistema (Cinnamon); QML pise v pikslih, zato jih pomnozimo sami.
    readonly property real merilo: Math.max(1, Math.min(2, Number(paleta.merilo) || 1))
    function px(n) { return Math.round(n * merilo) }
    property var videz: ({})
    function plosca(a) { var c = paleta.karticaRgb; return Qt.rgba(c[0], c[1], c[2], a) }
    function poudarekA(a) { var c = paleta.poudarekRgb; return Qt.rgba(c[0], c[1], c[2], a) }
    function prekriv(a) { var c = paleta.prekrivRgb || [1, 1, 1]; return Qt.rgba(c[0], c[1], c[2], a) }
    function crta(a) { var c = paleta.robRgb || [1, 1, 1]; return Qt.rgba(c[0], c[1], c[2], kontrast ? Math.max(0.45, a * 2.5) : a) }
    function barvaVrste(v) { var b = paleta.vrste || {}; return b[v] || b.program || paleta.tise }
    function uporabiVidez(v) {
        if (!v) return
        // Dogodek »videz« lahko prinese samo del (npr. le kontrast in velikost besedila): ostalo ostane.
        var z = {}
        for (var k in koren.videz) z[k] = koren.videz[k]
        for (var k2 in v) z[k2] = v[k2]
        koren.videz = z
        if (v.paleta) koren.paleta = v.paleta
        if (v.ozadje !== undefined) koren.ozadjeUrl = v.ozadje || ""
        if (v.zameglitev !== undefined) koren.zameglitev = v.zameglitev
        if (v.prosojnost !== undefined) koren.prosojnost = v.prosojnost
    }
    // Besedila: assets/os/besedila-namizja.js - isti slovar kot delovna povrsina WebKit (sl, en, de, es, fr, it).
    readonly property var besedila: Besedila.BESEDILA_NAMIZJA
    function nastaviJezik(j) { koren.jezik = besedila[j] ? j : "en" }
    // Windows: Koš namesto Smeti in »Ta PC« (kljuci win_…); namizje QML ima pri nekaterih sporocilih manj zamenjav (qml_…).
    property string platforma: "windows"
    function t(k, vr) {
        var d = besedila[jezik] || besedila.en, en = besedila.en
        var s = (platforma === "windows" && (d["win_" + k] || en["win_" + k])) || d["qml_" + k] || d[k] || en["qml_" + k] || en[k] || k
        if (vr) for (var x in vr) s = s.split("{" + x + "}").join(vr[x])
        return s
    }
    function velikost(b) {
        if (!b) return ""
        var e = ["B", "KB", "MB", "GB", "TB"], i = 0
        while (b >= 1024 && i < 4) { b /= 1024; i++ }
        var st = i ? b.toFixed(b < 10 ? 1 : 0) : String(b)
        return (jezik === "en" ? st : st.replace(".", ",")) + " " + e[i]     // decimalna vejica kot delovna.js
    }
    function cas(s) {
        if (!s) return ""
        var d = new Date(s * 1000), z = new Date()
        if (d.toDateString() === z.toDateString()) return Qt.formatTime(d, "hh:mm")
        if (jezik === "sl") return Qt.formatDate(d, "d. M. yyyy")
        // Drugi jeziki: kratek datum po krajevnih navadah (isti jeziki kot LOKALE v delovna.js).
        var l = ({ en: "en_GB", de: "de_DE", es: "es_ES", fr: "fr_FR", it: "it_IT" })[jezik] || "en_GB"
        return d.toLocaleDateString(Qt.locale(l), Locale.ShortFormat)
    }
    function obvesti(besedilo, dejanje, ob) { obvestilo.pokazi(besedilo, dejanje, ob) }
    // Razdelek Datoteke ali Programi z drugega mesta (okno Zapiski, Nastavitve …): plosca na namizju dobi fokus, Datoteke
    // pri mapi. Prej se je odprlo staro glavno okno Safeer OS (popis 3.1, safeer_os._pokazi_na_namizju, 18. 10. 2026).
    function pokaziNaNamizju(p) {
        if (p.razdelek === "datoteke") { if (p.pot) datoteke.odpriLokalno(p.pot); datoteke.fokus() }
        else if (p.razdelek === "programi") programi.fokus()
    }
    // »{n} naprav«: slovenscina ima ednino, dvojino in mnozino (isto pravilo kot delovna.js).
    function steviloNaprav(n) {
        var m = n % 100
        if (jezik !== "sl") return t(n === 1 ? "naprav1" : "napravN", { n: n })
        return m === 1 ? t("naprav1") : m === 2 ? t("naprav2") : (m === 3 || m === 4) ? t("naprav34", { n: n }) : t("napravN", { n: n })
    }

    // ------------------------------------------------------------------ ozadje
    property string ozadjeUrl: ""
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            GradientStop { position: 0; color: koren.paleta.ozadje }
            GradientStop { position: 1; color: koren.paleta.ozadje2 }
        }
    }
    Image {
        id: ozadje
        anchors.fill: parent
        source: koren.ozadjeUrl
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: false
        sourceSize.width: 1920
        opacity: status === Image.Ready ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: 600 } }
    }
    MultiEffect {
        id: zamegljeno
        anchors.fill: ozadje
        source: ozadje
        blurEnabled: true
        blur: koren.zameglitevPlosc
        Behavior on blur { NumberAnimation { duration: 200 } }
        blurMax: 64
        saturation: 0.15
        brightness: -0.08
        // Vidna mora biti (sicer se ne izrise v teksturo); skrijejo jo panelni ShaderEffectSource (hideSource).
    }

    // ------------------------------------------------------------------ iskanje (zgoraj na sredini)
    // Ista lupa kot na delovni povrsini WebKit (delovna.js isci, pregled enakosti 15. 10. 2026): splet, programi in
    // nastavitve sistema, Safeer OS, naprave v Linku, datoteke, zapiski, mediji (knjiznica, katalog iz predpomnilnika,
    // »Poisci v Medijskem centru«) in »Prikazi na …« (npr. »film na tv«). Iskanje z glasom (core/os_govor.py) na tem
    // racunalniku. Enter odpre oznaceno (program pred spletom, nauceno najprej), Shift+Enter vedno splet.
    Steklo {
        id: iskanje
        zamegljeno: zamegljeno
        width: Math.min(640, koren.width * 0.46); height: 54
        anchors.horizontalCenter: parent.horizontalCenter
        y: koren.robZgoraj + 18
        polmer: 27
        TextField {
            id: polje
            objectName: "iskalnoPolje"
            anchors.fill: parent; anchors.leftMargin: 52; anchors.rightMargin: mikrofon.visible ? 56 : 18
            placeholderText: govor.stanje === "poslusam" ? koren.t("govorPoslusam") : govor.stanje === "prepoznavam" ? koren.t("govorPrepoznavam") : koren.t("isci")
            placeholderTextColor: koren.paleta.medlo
            color: koren.paleta.besedilo; font.pixelSize: koren.px(16)
            background: Item {}
            Accessible.name: koren.t("isci")
            onTextChanged: casovnikIskanja.restart()
            Keys.onReturnPressed: function (d) {
                if (d.modifiers & Qt.ShiftModifier) { if (polje.text.trim()) zadetki.izberiVnos({ vrsta: "splet", kljuc: polje.text.trim() }) }
                else zadetki.enter()
            }
            Keys.onEnterPressed: zadetki.enter()
            Keys.onDownPressed: { zadetki.premaknjen = true; zadetki.trenutni = Math.min(zadetki.trenutni + 1, zadetkiModel.count - 1) }
            Keys.onUpPressed: { zadetki.premaknjen = true; zadetki.trenutni = Math.max(zadetki.trenutni - 1, 0) }
            Keys.onEscapePressed: koren.zapriVrhnje()
        }
        Lupa { x: 20; anchors.verticalCenter: parent.verticalCenter }
        // Mikrofon: prvi pritisk ponudi prenos prepoznave (ce je se ni), sicer poslusa; med poslusanjem konca govor.
        GumbIkona {
            id: mikrofon
            objectName: "gumbMikrofon"
            visible: koren.platforma === "linux"
            anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter
            width: 36; height: 36; velikostIkone: 19
            pot: "M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3z M5 11a7 7 0 0 0 14 0 M12 18v3"
            ime: koren.t("mikrofonNaslov")
            vklopljen: govor.poslusa()
            onKlik: govor.klik()
        }
    }
    Timer { id: casovnikIskanja; interval: 180; onTriggered: zadetki.isci(polje.text) }
    // Escape zapre, kar je zgoraj (kot Nazaj na daljincu TV): Prilagodi namizje, sicer zadetke iskanja. Meniji in okna
    // (Popup, Menu) se zaprejo sami (CloseOnEscape), zato bliznjica takrat ne velja. Puscice in Tab: vsak del namizja
    // (iskanje, Medijski center, viri in seznam Datotek, kategorije in mreza Programov, gumbi) ima fokus in tipke.
    function zapriVrhnje() {
        if (prilagodi.visible) { prilagodi.zapri(); return true }
        // Govor: Escape preklice poslusanje (kot na delovni povrsini) in zapre plosco govora.
        if (govor.plosca !== "" || govor.poslusa()) { if (govor.poslusa()) koren.klic("govorPreklici", []); govor.plosca = ""; return true }
        if (polje.text !== "") { polje.text = ""; polje.forceActiveFocus(); return true }
        return false
    }
    Shortcut {
        sequences: [StandardKey.Cancel, "Back"]
        enabled: (prilagodi.visible || polje.text !== "" || govor.plosca !== "" || govor.poslusa()) && !izhodi.visible && !meniNamizja.visible
        onActivated: koren.zapriVrhnje()
    }
    // Ctrl+K (kot na delovni povrsini): v iskanje od koderkoli na namizju.
    Shortcut { sequence: "Ctrl+K"; onActivated: { polje.forceActiveFocus(); polje.selectAll() } }

    // ------------------------------------------------------------------ iskanje z glasom (core/os_govor.py)
    // Kot delovna.js (mikrofonKlik, govorDogodek): prepoznava na tem racunalniku, nic ne gre na splet; prepoznano
    // besedilo gre v polje in se isce kot natipkano - nic se ne odpre samo od sebe.
    QtObject {
        id: govor
        objectName: "govor"
        property string stanje: ""       // "", "poslusam", "prepoznavam", "namescam"
        property string plosca: ""       // "", "ponudba", "prenos", "poslusam"
        property int mb: 0
        property int odstotek: 0
        property string delno: ""
        property var ravni: []
        function poslusa() { return stanje === "poslusam" || stanje === "prepoznavam" }
        function klik() {
            if (stanje === "poslusam") { koren.klic("govorUstavi", []); return }
            if (stanje === "prepoznavam" || stanje === "namescam") return
            koren.klic("govorStanje", [], function (s) {
                if (!s || !s.podprto) koren.obvesti(koren.t("govorNiPodprto"))
                else if (s.namescam) { govor.odstotek = 0; govor.plosca = "prenos"; govor.stanje = "namescam" }
                else if (!s.namesceno) { govor.mb = Math.max(1, Math.round((s.prenos || 0) / 1e6)); govor.plosca = "ponudba" }
                else govor.poslusaj()
            }, function () { koren.obvesti(koren.t("govorNiPodprto")) })
        }
        function poslusaj() {
            koren.klic("govorPoslusaj", [], function (ok) { if (!ok) koren.obvesti(koren.t("govorNapaka")) },
                       function () { koren.obvesti(koren.t("govorNapaka")) })
        }
        function namesti() {
            koren.klic("govorNamesti", [], function (ok) {
                if (ok) { govor.odstotek = 0; govor.plosca = "prenos"; govor.stanje = "namescam" }
                else { govor.plosca = ""; koren.obvesti(koren.t("govorNiPodprto")) }
            })
        }
        function dogodek(d) {
            var v = d.vrsta
            if (v === "raven") { var r = ravni.slice(-33); r.push(d.r || 0); ravni = r; return }
            if (v === "delno") { if (poslusa()) delno = d.besedilo || ""; return }
            if (v === "poslusam") { ravni = []; delno = ""; plosca = "poslusam"; polje.text = ""; polje.forceActiveFocus() }
            else if (v === "prepoznavam") { plosca = "poslusam"; if (!delno) delno = koren.t("govorPrepoznavam") }
            else if (v !== "namescam" && plosca === "poslusam") plosca = ""
            stanje = (v === "poslusam" || v === "prepoznavam" || v === "namescam") ? v : ""
            if (v === "namescam") { odstotek = d.odstotek || 0; plosca = "prenos" }
            else if (v === "namesceno") { plosca = ""; poslusaj() }
            else if (v === "besedilo") {
                if (d.besedilo) { polje.text = d.besedilo; polje.forceActiveFocus(); casovnikIskanja.stop(); zadetki.isci(d.besedilo) }
                else koren.obvesti(koren.t("govorTisina"))
            }
            else if (v === "tisina") koren.obvesti(koren.t("govorTisina"))
            else if (v === "napaka") {
                plosca = ""
                if (d.razlog !== "preklicano") koren.obvesti(koren.t(d.razlog === "mikrofon" ? "govorMikrofon" : d.razlog === "prenos" ? "govorPrenosNapaka" : "govorNapaka"))
            }
        }
    }
    Steklo {
        id: govorPlosca
        objectName: "govorPlosca"
        zamegljeno: zamegljeno
        z: 11
        visible: govor.plosca !== ""
        width: iskanje.width; x: iskanje.x; y: iskanje.y + iskanje.height + 8
        height: govorVsebina.implicitHeight + 32
        // Skoraj neprosojno: zadetki lezijo cez plosce Datoteke in Programi, njihovo besedilo (opozorilo o prostoru,
        // kategorije) se je pri 0,82 videlo skozi (posnetek 1440 x 900, 15. 10. 2026).
        barva: koren.plosca(Math.max(0.96, koren.prosojnostPlosc))
        ColumnLayout {
            id: govorVsebina
            anchors.fill: parent; anchors.margins: 16; spacing: 10
            Text { visible: govor.plosca === "ponudba"; text: koren.t("govorNamestiNaslov"); color: koren.paleta.besedilo; font.pixelSize: koren.px(15); font.bold: true }
            Text { visible: govor.plosca === "ponudba"; text: koren.t("govorNamestiOpis", { mb: govor.mb }); Layout.fillWidth: true; wrapMode: Text.WordWrap
                   color: koren.paleta.medlo; font.pixelSize: koren.px(13) }
            Text { visible: govor.plosca === "prenos"; text: koren.t("govorPrenasam", { o: govor.odstotek }); color: koren.paleta.besedilo; font.pixelSize: koren.px(13) }
            Rectangle {
                visible: govor.plosca === "prenos"; Layout.fillWidth: true; height: 6; radius: 3; color: koren.prekriv(0.12)
                Accessible.role: Accessible.ProgressBar; Accessible.name: govor.odstotek + " %"
                Rectangle { height: parent.height; radius: 3; color: koren.paleta.poudarek; width: parent.width * Math.min(1, govor.odstotek / 100) }
            }
            // Valovi glasnosti: tisina so pike, govor stolpci (kot govorValovi na delovni povrsini).
            RowLayout {
                visible: govor.plosca === "poslusam"; Layout.fillWidth: true; spacing: 10
                GumbIkona { pot: "M6 6l12 12 M18 6L6 18"; ime: koren.t("govorPreklici"); onKlik: koren.klic("govorPreklici", []) }
                Row {
                    Layout.fillWidth: true; spacing: 3; height: 26
                    Repeater {
                        model: 34
                        delegate: Rectangle {
                            required property int index
                            readonly property real r: govor.ravni[govor.ravni.length - 34 + index] || 0
                            width: 3; radius: 1.5; anchors.verticalCenter: parent.verticalCenter
                            height: r < 0.28 ? 3 : Math.round(3 + (r - 0.28) / 0.72 * 22)
                            color: govor.stanje === "prepoznavam" ? koren.paleta.medlo : koren.paleta.poudarek
                        }
                    }
                }
                GumbIkona { pot: "M7 7h10v10H7z"; polnilo: true; poudarjen: true; ime: koren.t("govorKoncaj"); onKlik: koren.klic("govorUstavi", []) }
            }
            Text { visible: govor.plosca === "poslusam" && govor.delno !== ""; text: govor.delno; Layout.fillWidth: true; wrapMode: Text.WordWrap
                   color: koren.paleta.besedilo; font.pixelSize: koren.px(14) }
            RowLayout {
                visible: govor.plosca === "ponudba" || govor.plosca === "prenos"; Layout.alignment: Qt.AlignRight; spacing: 8
                Gumb { visible: govor.plosca === "ponudba"; besedilo: koren.t("govorNeZdaj"); onKlik: govor.plosca = "" }
                Gumb { id: gumbPrenesiGovor; objectName: "govorPrenesi"; visible: govor.plosca === "ponudba"; besedilo: koren.t("govorPrenesi"); poudarjen: true
                       onKlik: govor.namesti() }
                Gumb { visible: govor.plosca === "prenos"; besedilo: koren.t("govorPrekini"); onKlik: koren.klic("govorPrekliciNamestitev", []) }
            }
        }
        onVisibleChanged: if (visible && govor.plosca === "ponudba") gumbPrenesiGovor.forceActiveFocus()
    }

    ListModel { id: zadetkiModel; objectName: "zadetkiModel" }
    Steklo {
        id: zadetki
        objectName: "zadetki"
        zamegljeno: zamegljeno
        z: 10
        property int trenutni: 0
        property int zahteva: 0
        property int caka: 0
        property bool poEnter: false
        visible: polje.text.length > 0 && zadetkiModel.count > 0 && govor.plosca === ""
        width: iskanje.width; x: iskanje.x; y: iskanje.y + iskanje.height + 8
        height: Math.min(Math.max(220, koren.height - y - koren.robSpodaj - 40), seznamZadetkov.contentHeight + 16)
        // Skoraj neprosojno: zadetki lezijo cez plosce Datoteke in Programi, njihovo besedilo (opozorilo o prostoru,
        // kategorije) se je pri 0,82 videlo skozi (posnetek 1440 x 900, 15. 10. 2026).
        barva: koren.plosca(Math.max(0.96, koren.prosojnostPlosc))
        // Ucenje lupe (core/os_lupa.py, isti zapis kot prejsnja delovna povrsina): kar je uporabnik za tak niz ze
        // izbral, je oznaceno. Izbire [niz, kljuc, cas, prvi]; novejse stejejo vec (polovica po 30 dneh), enak niz dvojno.
        property var izbire: []
        property string zadnjiNiz: ""
        property bool premaknjen: false
        property var cilj: null             // »Prikazi na …«: {q, vrste} ali null
        property var napraveCilja: []
        property string privzetiKljuc: ""
        onTrenutniChanged: if (trenutni >= 0 && trenutni < zadetkiModel.count) seznamZadetkov.positionViewAtIndex(trenutni, ListView.Contain)
        function nizUcenja(q) { return Iskanje.SafeerIskanje.brezNaglasa(q).replace(/\s+/g, " ").trim() }
        function kljucZadetka(z) {
            if (z.vrsta === "splet" || z.vrsta === "mediji") return z.vrsta
            return (z.vrsta === "mapa" ? "datoteka" : z.vrsta) + ":" + z.kljuc
        }
        function ocene(ql) {
            var o = {}, zdaj = Date.now() / 1000
            izbire.forEach(function (x) {
                var niz = x[0], enak = niz === ql
                if (!enak && !(niz.length >= 2 && (niz.indexOf(ql) === 0 || ql.indexOf(niz) === 0))) return
                o[x[1]] = (o[x[1]] || 0) + Math.pow(0.5, Math.max(0, zdaj - x[2]) / (30 * 86400)) * (enak ? 2 : 1)
            })
            return o
        }
        function najMesto(kljuci) {          // mesto naucenega zadetka ali -1
            var o = ocene(nizUcenja(zadnjiNiz)), naj = -1, najO = 0
            for (var i = 0; i < kljuci.length; i++) {
                var v = o[kljuci[i]] || 0
                if (v > najO) { najO = v; naj = i }
            }
            return najO >= 0.5 ? naj : -1
        }
        // Besede brez locil; kratka beseda (1-2 crki) se mora ujemati z zacetkom besede, daljsa kjerkoli, sklon (vsaj
        // 5 crk) brez zadnjih dveh crk - ista pravila kot besedeIskanja/ujemaZadetek v delovna.js.
        function besede(q) { return Iskanje.SafeerIskanje.brezNaglasa(q).replace(/[^0-9a-zÀ-ɏͰ-ϿЀ-ӿ]+/g, " ").trim().split(" ").filter(function (b) { return !!b }) }
        function ujema(besedilo, bs) {
            var k = " " + Iskanje.SafeerIskanje.brezNaglasa(besedilo).replace(/[^0-9a-zÀ-ɏͰ-ϿЀ-ӿ]+/g, " ")
            return bs.length > 0 && bs.every(function (b) {
                if (k.indexOf(b.length < 3 ? " " + b : b) >= 0) return true
                return b.length >= 5 && k.indexOf(" " + b.slice(0, Math.max(4, b.length - 2))) >= 0
            })
        }
        function ocenaPrograma(p, ql) {
            var ime = Iskanje.SafeerIskanje.brezNaglasa(p.ime)
            if (ime.indexOf(ql) === 0) return 3
            if (ime.indexOf(" " + ql) >= 0 || ime.indexOf("-" + ql) >= 0) return 2
            return ime.indexOf(ql) >= 0 ? 1 : 0
        }
        // Razdelki Safeer OS: [cilj za odpriRazdelek, kljuc imena, kljucne besede brez sumnikov] (SAFEER_CILJI).
        readonly property var safeerCilji: [
            ["media", "ciljMedia", "medijski center filmi serije glasba radio tv televizija video katalog media centre movies series music"],
            ["naprave", "ciljNaprave", "safeer link naprave telefon televizor tablica povezi qr koda devices phone tablet pair"],
            ["nastavitve#blokScit", "ciljScit", "scit zascita dns oglasi sledilci blokiranje premor dovoli shield ads trackers protection block"],
            ["nastavitve", "ciljNastavitve", "nastavitve safeer os posodobitve samozagon celozaslonsko settings updates"],
            ["zapiski", "ciljZapiski", "zapiski belezke opombe notes"],
            ["sporocila", "ciljSporocila", "sporocila posta klepet messages mail chat"],
            ["splet", "ciljSplet", "splet brskalnik zaznamki web browser"]]
        readonly property var besedeNaprav: ({ tv: "tv televizor televizija television", phone: "telefon mobitel phone", tablet: "tablica tablet",
                                              windows: "windows racunalnik computer pc", linux: "linux racunalnik computer pc", mac: "mac racunalnik computer" })
        // »Prikazi na …« (glas ali tipkanje; sl, en, de, es, pt, fr, it): cilj na koncu niza (ciljMedija v delovna.js).
        readonly property var pc: ["windows", "linux", "mac"]
        readonly property var ciljiMedija: [
            [/ (na|v) (tv|televiziji|televizorju|televizor|televizijo)$/, ["tv"]], [/ na (racunalniku|racunalnik|pc|prenosniku)$/, pc],
            [/ na (tablici|tablico|tablica)$/, ["tablet"]], [/ na (telefonu|telefon|mobitelu|mobitel)$/, ["phone"]],
            [/ on (the |my )?(tv|television|telly)$/, ["tv"]], [/ on (the |my |this )?(computer|pc|laptop)$/, pc],
            [/ on (the |my )?tablet$/, ["tablet"]], [/ on (the |my )?(phone|mobile)$/, ["phone"]],
            [/ (auf|im) (dem |meinem )?(fernseher|tv|fernsehen)$/, ["tv"]], [/ auf (dem |meinem )?(computer|pc|rechner|laptop)$/, pc],
            [/ auf (dem |meinem )?tablet$/, ["tablet"]], [/ auf (dem |meinem )?(handy|telefon|smartphone)$/, ["phone"]],
            [/ en (la |mi )?(tele|television|tv)$/, ["tv"]], [/ en (el |mi )?(ordenador|computador|computadora|pc|portatil)$/, pc],
            [/ en (la |mi )?tableta$/, ["tablet"]], [/ en (el |mi )?(movil|telefono|celular)$/, ["phone"]],
            [/ n(a|o) (tv|televisao|televisor)$/, ["tv"]], [/ no (computador|pc|portatil)$/, pc],
            [/ no tablet$/, ["tablet"]], [/ no (telemovel|celular|telefone)$/, ["phone"]],
            [/ sur (la |ma )?(tele|television|tv)$/, ["tv"]], [/ sur (lordinateur|mon ordinateur|le pc|mon pc)$/, pc],
            [/ sur (la |ma )?tablette$/, ["tablet"]], [/ sur (le |mon )?(telephone|portable|mobile)$/, ["phone"]],
            [/ (sulla|in) (tv|televisione)$/, ["tv"]], [/ sul (computer|pc)$/, pc],
            [/ sul tablet$/, ["tablet"]], [/ sul (telefono|cellulare)$/, ["phone"]]]
        readonly property var glagoliPrikaza: ["prikazi", "pokazi", "predvajaj", "odpri", "zavrti", "show", "play", "open", "put", "zeige", "spiele",
                                               "offne", "muestra", "reproduce", "pon", "abre", "mostra", "reproduz", "toca", "passa",
                                               "montre", "joue", "ouvre", "lance", "riproduci", "apri", "metti"]
        function ciljMedija(q) {
            var bs = String(q || "").trim().split(/\s+/).filter(function (b) { return !!b })
            var ocisti = function (b) { return Iskanje.SafeerIskanje.brezNaglasa(b).replace(/[^0-9a-zÀ-ɏ]+/g, "") }
            var k = " " + bs.map(ocisti).join(" ")
            for (var i = 0; i < ciljiMedija.length; i++) {
                var m = k.match(ciljiMedija[i][0])
                if (!m) continue
                var ostanek = bs.slice(0, bs.length - m[0].trim().split(" ").length)
                if (ostanek.length && glagoliPrikaza.indexOf(ocisti(ostanek[0])) >= 0) ostanek = ostanek.slice(1)
                return { q: ostanek.join(" "), vrste: ciljiMedija[i][1] }
            }
            return null
        }
        property var deli: ({})
        function isci(q) {
            q = (q || "").trim(); zadnjiNiz = q; premaknjen = false; poEnter = false
            var st = ++zahteva
            deli = {}; caka = 0
            if (!q) { zadetkiModel.clear(); return }
            var c = ciljMedija(q)
            cilj = c && c.q ? c : null
            if (cilj) q = cilj.q
            var bs = besede(q), ql = Iskanje.SafeerIskanje.brezNaglasa(q), o = ocene(nizUcenja(q)), linux = koren.platforma === "linux"
            // Programi in orodja za nastavitve sistema (Cinnamon, Mint) - vsaka skupina do 5 zadetkov.
            var vsi = programi.vsi.filter(function (p) {
                return !p.skrit && zadetki.ujema(p.ime + " " + (p.splosno || "") + " " + (p.kljucne || []).join(" "), bs)
            }).sort(function (a, b) {
                return ((o["program:" + b.id] || 0) - (o["program:" + a.id] || 0)) || (ocenaPrograma(b, ql) - ocenaPrograma(a, ql)) || ((b.uporaba || 0) - (a.uporaba || 0))
            })
            var d = {
                programi: vsi.filter(function (p) { return !p.nastavitev }).slice(0, 5),
                nastavitve: vsi.filter(function (p) { return p.nastavitev }).slice(0, 5),
                // Izklopljena Sporocila (Prilagodi): razdelka ni med zadetki.
                safeer: q.length >= 2 && linux ? safeerCilji.filter(function (x) { return (koren.videz.sporocila !== false || x[0] !== "sporocila") && zadetki.ujema(koren.t(x[1]) + " " + x[2], bs) }).slice(0, 4) : [],
                naprave: q.length >= 2 ? koren.naprave.filter(function (n) {
                    return zadetki.ujema(n.ime, bs) || zadetki.ujema(n.ime + " " + (besedeNaprav[n.platforma] || n.platforma || ""), bs)
                }).slice(0, 4) : [],
                datoteke: [], zapiski: [], mediji: [], katalog: [], naCilj: []
            }
            deli = d
            function pocakaj(metoda, args, kam, obdelaj) {
                caka++
                koren.klic(metoda, args, function (r) {
                    if (st !== zahteva) return
                    var dd = zadetki.deli; dd[kam] = obdelaj(r || []); zadetki.deli = dd; zadetki.caka--; zadetki.sestavi()
                }, function () { if (st !== zahteva) return; zadetki.caka--; zadetki.sestavi() })
            }
            if (q.length >= 2) pocakaj("isciDatoteke", [q, 6], "datoteke", function (r) { return r.slice(0, 6) })
            if (linux && q.length >= 2) {
                pocakaj("zapiskiSeznam", [q], "zapiski", function (r) { return r.slice(0, 4) })
                pocakaj("knjiznicaMedijev", ["", q, 0], "mediji", function (r) { return r.slice(0, 5) })
            }
            // Katalog Medijskega centra samo iz predpomnilnika na disku - med tipkanjem se virov po omrezju ne sprasuje.
            if (linux && q.length >= 3) pocakaj("mediaIsciPredpomnilnik", [q], "katalog", function (r) {
                var poNaslovu = r.filter(function (x) { return zadetki.ujema((x.naslov || "") + " " + (x.izvajalec || ""), bs) })
                return (poNaslovu.length ? poNaslovu : r).slice(0, 5)
            })
            if (cilj) pocakaj("napraveZaMedij", [], "naCilj", function (r) {
                var izbor = r.filter(function (n) { return zadetki.cilj && zadetki.cilj.vrste.indexOf(n.platforma) >= 0 })
                if (zadetki.cilj && zadetki.cilj.vrste === zadetki.pc) izbor.unshift({ id: "", ime: koren.t("taRacunalnik"), platforma: "linux" })
                return izbor
            })
            sestavi()
        }
        // Zadetki v skupinah (vrstni red kot na delovni povrsini); vsak vnos ima skupino za naslov razdelka.
        function sestavi() {
            var d = deli, q = cilj ? cilj.q : zadnjiNiz, v = [], izbrani = zadetkiModel.count && premaknjen ? kljucZadetka(zadetkiModel.get(trenutni)) : ""
            if (cilj && caka === 0) {
                if (d.naCilj.length) d.naCilj.forEach(function (n) {
                    v.push({ vrsta: "naCilj", skupina: koren.t("skPrikaziNa"), ime: koren.t("prikaziNaVrsta", { kaj: q, ime: n.ime }), opis: "", kljuc: n.id, ikona: "",
                             podatki: JSON.stringify({ n: n, naslov: q, izberi: d.naCilj.length > 1 }) })
                })
                else v.push({ vrsta: "naCilj", skupina: koren.t("skPrikaziNa"), ime: koren.t("niNapraveCilja"), opis: "", kljuc: "", ikona: "", podatki: "{}" })
            }
            v.push({ vrsta: "splet", skupina: koren.t("skSplet"), ime: koren.t("isciVSpletu", { q: q }), opis: koren.t("odpreVBrskalniku"), kljuc: q, ikona: "", podatki: "{}" })
            d.programi.forEach(function (p) { v.push({ vrsta: "program", skupina: koren.t("skProgrami"), ime: p.ime, opis: p.opis || "", kljuc: p.id, ikona: p.ikona || "", podatki: "{}" }) })
            d.nastavitve.forEach(function (p) { v.push({ vrsta: "program", skupina: koren.t("skNastavitve"), ime: p.ime, opis: p.opis || "", kljuc: p.id, ikona: p.ikona || "", podatki: "{}" }) })
            d.safeer.forEach(function (x) { v.push({ vrsta: "safeer", skupina: koren.t("skSafeer"), ime: koren.t(x[1]), opis: koren.t(x[0] === "media" ? "odprePredvajalnik" : "odpreSafeerOs"),
                                                     kljuc: x[0], ikona: "", podatki: "{}" }) })
            var bs = besede(q)
            d.naprave.forEach(function (n) {
                v.push({ vrsta: "naprava", skupina: koren.t("skNaprave"), ime: n.ime, opis: koren.t(n.datoteke ? "napravaDatoteke" : "napravaProgrami") + " · Safeer Link",
                         kljuc: n.kljuc || n.datoteke || n.programi, ikona: "", podatki: JSON.stringify({ n: n, poImenu: zadetki.ujema(n.ime, bs) }) })
            })
            d.datoteke.forEach(function (x) { v.push({ vrsta: x.mapa ? "mapa" : "datoteka", skupina: koren.t("skDatoteke"), ime: x.ime, opis: koren.kratkaPot(x.pot), kljuc: x.pot, ikona: "",
                                                       podatki: JSON.stringify({ vrsta: x.vrsta || "" }) }) })
            d.zapiski.forEach(function (z) { v.push({ vrsta: "zapisek", skupina: koren.t("skZapiski"), ime: z.naslov || "", opis: z.odlomek || "", kljuc: z.id, ikona: "", podatki: "{}" }) })
            d.mediji.forEach(function (m) { v.push({ vrsta: "medij", skupina: koren.t("skMediji"), ime: m.naslov || m.ime || m.pot, opis: koren.kratkaPot(m.pot || ""), kljuc: m.pot, ikona: "", podatki: "{}" }) })
            d.katalog.forEach(function (k) { v.push({ vrsta: "katalog", skupina: koren.t("skMediji"), ime: k.naslov || "", opis: k.izvajalec || koren.t("skMediji"), kljuc: k.id,
                                                      ikona: k.slika && /^https:\/\//.test(k.slika) ? k.slika : "", podatki: JSON.stringify({ k: k }) }) })
            if (q.length >= 2 && koren.platforma === "linux")
                v.push({ vrsta: "mediji", skupina: koren.t("skMediji"), ime: koren.t("isciVMedijih", { q: q }), opis: koren.t("odpreMedijski"), kljuc: q, ikona: "", podatki: "{}" })
            zadetkiModel.clear()
            v.forEach(function (x) { zadetkiModel.append(x) })
            var i = -1
            if (izbrani) for (var j = 0; j < v.length; j++) if (kljucZadetka(v[j]) === izbrani) { i = j; break }
            trenutni = i >= 0 ? i : privzeti(v, q)
            privzetiKljuc = v[trenutni] ? kljucZadetka(v[trenutni]) : ""
            if (poEnter && caka === 0) { poEnter = false; enter() }
        }
        // Kateri zadetek odpre Enter, ce uporabnik ni izbral sam (privzetiZadetek v delovna.js): nauceno, spletni naslov
        // -> splet, »Prikazi na«, program, ime datoteke/medija/zapiska, ki se z nizom zacne, Safeer OS, naprava po imenu.
        function privzeti(v, q) {
            var naj = najMesto(v.map(kljucZadetka))
            if (naj >= 0) return naj
            var I = Iskanje.SafeerIskanje
            if (q && I.jeNaslov(q)) { for (var s = 0; s < v.length; s++) if (v[s].vrsta === "splet") return s }
            var RANG = { naCilj: 4, program: 3, safeer: 2, naprava: 1 }, prvi = 0, rang = 0
            for (var i = 0; i < v.length; i++) {
                var x = v[i], r = RANG[x.vrsta] || 0
                if (x.vrsta === "naprava" && !JSON.parse(x.podatki).poImenu) r = 0
                if (x.vrsta === "datoteka" || x.vrsta === "mapa" || x.vrsta === "medij" || x.vrsta === "zapisek") {
                    var ime = x.ime, brez = ime.replace(/\.[^.\s]{1,8}$/, "")
                    var o = Math.max(I.oceni(ime, q), I.oceni(brez, q))
                    if (o >= 70 || ((x.vrsta === "datoteka" || x.vrsta === "mapa") && I.jePotAliKoncnica(q) && o > 0)) r = 2.5
                }
                if (r > rang) { rang = r; prvi = i }
            }
            return prvi
        }
        // Enter pred prihodom vseh zadetkov: odlocimo, ko pridejo (najvec 1,5 s), kot na delovni povrsini.
        function enter() {
            var q = polje.text.trim()
            if (!q) return
            if (!premaknjen && (casovnikIskanja.running || q !== zadnjiNiz || caka > 0)) {
                if (q !== zadnjiNiz) { casovnikIskanja.stop(); isci(q) }
                poEnter = true; enterCasovnik.restart(); return
            }
            var z = zadetkiModel.count ? zadetkiModel.get(trenutni) : null
            if (z && z.vrsta === "naCilj" && JSON.parse(z.podatki).izberi && !premaknjen) { koren.obvesti(koren.t("izberiNapravo")); return }
            if (z) izberi(trenutni); else izberiVnos({ vrsta: "splet", kljuc: q })
        }
        Timer { id: enterCasovnik; interval: 1500; onTriggered: if (zadetki.poEnter) { zadetki.poEnter = false; zadetki.enter() } }
        function izberi(i) {
            if (i < 0 || i >= zadetkiModel.count) return
            var z = zadetkiModel.get(i)
            izberiVnos({ vrsta: z.vrsta, kljuc: z.kljuc, ime: z.ime, podatki: z.podatki }, i)
        }
        function izberiVnos(z, i) {
            var ql = nizUcenja(zadnjiNiz), k = kljucZadetka(z)
            if (ql && k) {
                var prvi = k === privzetiKljuc
                izbire.push([ql, k, Math.round(Date.now() / 1000), prvi])
                if (izbire.length > 500) izbire.shift()
                koren.klic("lupaZapomni", [ql, k, prvi])
            }
            var p = z.podatki ? JSON.parse(z.podatki) : {}
            if (z.vrsta === "program") koren.klic("zazeni", [z.kljuc], function (ok) { if (!ok) koren.obvesti(koren.t("niUspelo")) })
            else if (z.vrsta === "datoteka") datoteke.odpriDatotekoTegaRacunalnika({ pot: z.kljuc, ime: z.ime, mapa: false, vrsta: p.vrsta || "" })
            else if (z.vrsta === "mapa") datoteke.odpriLokalno(z.kljuc)   // mapa se odpre v Datotekah (tega racunalnika)
            else if (z.vrsta === "safeer") koren.klic("odpriRazdelek", [z.kljuc])
            else if (z.vrsta === "zapisek") koren.klic("odpriRazdelek", ["zapisek:" + z.kljuc])
            else if (z.vrsta === "naprava") {
                if (p.n.datoteke) datoteke.pokaziNapravo(p.n.datoteke)
                else programi.pokaziNapravo(p.n.programi)
            }
            else if (z.vrsta === "mediji") koren.klic("odpriRazdelek", ["mediji:" + z.kljuc])
            else if (z.vrsta === "medij") koren.klic("odpriLokalniMedij", [z.kljuc], function (ok) { if (ok) koren.osveziMedij(); else koren.obvesti(koren.t("niUspelo")) })
            else if (z.vrsta === "katalog" && cilj) { prikaziKatalogNa(p.k); return }
            else if (z.vrsta === "katalog") odpriIzKataloga(p.k)
            else if (z.vrsta === "naCilj") prikaziNa(p.n, p.k, p.naslov)
            else odpriSplet(z.kljuc)
            polje.text = ""
        }
        // Spletni zadetek: rezultati v plosci na namizju (isti vgrajeni brskalnik kot Splet); brez nje privzeti brskalnik.
        function odpriSplet(q) {
            if (koren.videz.spletVBrskalniku) {
                koren.klic("odpriVBrskalniku", [q], function (ok) { if (ok === false) koren.klic("iskanjeSplet", [q]) }, function () { koren.klic("iskanjeSplet", [q]) })
                return
            }
            koren.klic("spletNaNamizju", [q], function (ok) {
                if (ok === false) koren.klic("odpriVBrskalniku", [q], function (ok2) { if (ok2 === false) koren.klic("iskanjeSplet", [q]) },
                                             function () { koren.klic("iskanjeSplet", [q]) })
            }, function () { koren.klic("odpriVBrskalniku", [q], null, function () { koren.klic("iskanjeSplet", [q]) }) })
        }
        // Vsebina iz kataloga: glasba, radio in TV se predvajajo takoj; film ali serija se odpre v Safeer Playerju.
        function odpriIzKataloga(k) {
            if (k.vrsta === "film" || k.vrsta === "serija" || k.vrsta === "video") { koren.klic("odpriRazdelek", ["mediji:" + (k.naslov || "")]); return }
            koren.klic("mediaPredvajaj", [k.id], function (izid) {
                if (!izid || izid.napaka_koda || izid.napaka) koren.obvesti(koren.t("niUspelo")); else koren.osveziMedij()
            }, function () { koren.obvesti(koren.t("niUspelo")) })
        }
        // »Prikazi na …«: naslov (ali vnos kataloga) odpre Medijski center izbrane naprave (Link media.open); ta racunalnik
        // (id "") ga odpre tukaj.
        function prikaziNa(n, k, naslov) {
            if (!n) { koren.obvesti(koren.t("niNapraveCilja")); return }
            var kaj = k ? k.naslov : naslov
            if (!n.id) { if (k) odpriIzKataloga(k); else koren.klic("odpriRazdelek", ["mediji:" + kaj]); return }
            var m = { title: kaj, kind: k ? (k.vrsta || "") : "", year: k && k.leto ? Number(k.leto) || null : null }
            koren.klic("odpriMedijNa", [n.id, JSON.stringify(m)], function (izid) {
                var koda = izid && (izid.koda || izid.code)
                if (izid && izid.ok) koren.obvesti(koren.t("prikazanoNa", { ime: n.ime, kaj: kaj }))
                else if (koda === "neznano_dejanje" || koda === "stari_control") koren.obvesti(koren.t("napravaNeZna", { ime: n.ime }))
                else koren.obvesti(koren.t("niUspelo"))
            }, function () { koren.obvesti(koren.t("niUspelo")) })
        }
        function prikaziKatalogNa(k) {
            var n = deli.naCilj || []
            if (n.length === 1) { prikaziNa(n[0], k, k.naslov); polje.text = ""; return }
            if (!n.length) { koren.obvesti(koren.t("niNapraveCilja")); return }
            zadetkiModel.clear()
            n.forEach(function (x) {
                zadetkiModel.append({ vrsta: "naCilj", skupina: koren.t("izberiNapravo"), ime: koren.t("prikaziNaVrsta", { kaj: k.naslov, ime: x.ime }), opis: "",
                                      kljuc: x.id, ikona: "", podatki: JSON.stringify({ n: x, k: k, naslov: k.naslov }) })
            })
            trenutni = 0; premaknjen = true
            polje.forceActiveFocus()
        }
        ListView {
            id: seznamZadetkov
            objectName: "seznamZadetkov"
            anchors.fill: parent; anchors.margins: 8
            model: zadetkiModel; clip: true; interactive: contentHeight > height
            Accessible.role: Accessible.List; Accessible.name: koren.t("isci")
            section.property: "skupina"
            section.delegate: Text {
                required property string section
                text: section.toUpperCase(); leftPadding: 10; topPadding: 8; bottomPadding: 2
                color: Qt.darker(koren.paleta.medlo, 1.15); font.pixelSize: koren.px(10); font.letterSpacing: 1
            }
            delegate: Rectangle {
                width: seznamZadetkov.width; height: koren.px(model.opis ? 46 : 38); radius: 10
                color: index === zadetki.trenutni ? koren.prekriv(0.12) : (mz.containsMouse ? koren.prekriv(0.06) : "transparent")
                Accessible.role: Accessible.ListItem; Accessible.name: model.ime
                Row {
                    anchors.verticalCenter: parent.verticalCenter; x: 10; spacing: 12
                    Image { source: model.ikona; width: 26; height: 26; visible: model.ikona !== ""; sourceSize: Qt.size(52, 52) }
                    Text { text: model.vrsta === "splet" ? "🌐" : model.vrsta === "mapa" ? "📁" : model.vrsta === "zapisek" ? "📝"
                               : (model.vrsta === "medij" || model.vrsta === "katalog" || model.vrsta === "mediji") ? "🎵"
                               : (model.vrsta === "naprava" || model.vrsta === "naCilj") ? "📺" : model.vrsta === "safeer" ? "✦"
                               : model.vrsta === "program" ? "▣" : "📄"
                           visible: model.ikona === ""; font.pixelSize: koren.px(18); width: 26; color: koren.paleta.medlo }
                    Column {
                        anchors.verticalCenter: parent.verticalCenter
                        Text { text: model.ime; color: koren.paleta.besedilo; font.pixelSize: koren.px(14); elide: Text.ElideRight; width: seznamZadetkov.width - 70 }
                        Text { text: model.opis; color: koren.paleta.medlo; font.pixelSize: koren.px(11); elide: Text.ElideMiddle; width: seznamZadetkov.width - 70; visible: text !== "" }
                    }
                }
                MouseArea { id: mz; anchors.fill: parent; hoverEnabled: true; onClicked: zadetki.izberi(index)
                            onContainsMouseChanged: if (containsMouse) { zadetki.trenutni = index; zadetki.premaknjen = true } }
            }
        }
    }

    // Pod iskanjem: Safeer Link, Sporocila (neprebrana, isto stevilo kot kuverta v pultu) in opomba o posodobitvi - vstopi,
    // ki jih je imel Domov aplikacije Safeer OS (popis 3.1, 18. 10. 2026).
    property int napravVLinku: 0
    property int sporocilNeprebranih: 0
    property string posodobitev: ""      // opis nove razlicice (dogodek »posodobitev«) ali ""
    function osveziSporocila() { if (platforma === "linux" && videz.sporocila !== false) klic("sporocilaNeprebrana", []) }
    // Varnostno osvezevanje (spremembo sicer javi dogodek »sporocilaStevilo«; brez ikone v pultu ga ni ob vsaki spremembi).
    Timer { interval: 60000; repeat: true; running: koren.platforma === "linux" && koren.videz.sporocila !== false
            onTriggered: koren.osveziSporocila() }
    Row {
        id: vrsticaCipov
        objectName: "vrsticaCipov"
        anchors.horizontalCenter: parent.horizontalCenter
        y: iskanje.y + iskanje.height + 10
        visible: !zadetki.visible
        spacing: 8
        Rectangle {
            id: linkGumb
            height: koren.px(26); width: linkVrstica.width + 22; radius: height / 2
            color: ml.containsMouse || activeFocus ? koren.prekriv(0.16) : koren.plosca(koren.prosojnostPlosc)
            border.width: activeFocus ? 2 : 1
            border.color: activeFocus ? koren.paleta.fokus : koren.crta(0.12)
            activeFocusOnTab: true
            Accessible.role: Accessible.Button
            Accessible.name: koren.t("linkNaslov")
            Keys.onReturnPressed: koren.linkKlik()
            Keys.onEnterPressed: koren.linkKlik()
            Keys.onSpacePressed: koren.linkKlik()
            Behavior on color { ColorAnimation { duration: 150 } }
            Row {
                id: linkVrstica; anchors.centerIn: parent; spacing: 7
                Rectangle { width: 7; height: 7; radius: 4; color: koren.napravVLinku > 0 ? koren.paleta.poudarek : koren.paleta.medlo; anchors.verticalCenter: parent.verticalCenter }
                Text { objectName: "linkBesedilo"
                       text: koren.linkNepovezan() ? koren.t("linkPovezi")
                           : koren.t("link") + (koren.napravVLinku > 0 ? " · " + koren.steviloNaprav(koren.napravVLinku) : "")
                       color: koren.paleta.besedilo; font.pixelSize: koren.px(12) }
            }
            MouseArea { id: ml; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: koren.linkKlik() }
        }
        Cip {
            id: sporocilaGumb
            objectName: "gumbSporocila"
            visible: koren.platforma === "linux" && koren.videz.sporocila !== false
            besedilo: koren.t("sporocilaGumb")
            stevilo: koren.sporocilNeprebranih
            ime: koren.sporocilNeprebranih > 0 ? koren.t("sporocilaNeprebrana", { n: koren.sporocilNeprebranih }) : koren.t("sporocilaGumb")
            onKlik: koren.klic("odpriRazdelek", ["sporocila"])
        }
        Cip {
            id: posodobitevGumb
            objectName: "gumbPosodobitev"
            visible: koren.posodobitev !== "" && koren.platforma === "linux"
            poudarjen: true
            besedilo: koren.t("posodobitevNaVoljo", { opis: koren.posodobitev })
            ime: besedilo + " · " + koren.t("posodobitevOdpri")
            onKlik: koren.klic("odpriRazdelek", ["nastavitve#blokPosodobitve"])
        }
    }

    // Domaca mapa kot »~« (kot upravitelji datotek): krajse in brez uporabniskega imena na posnetkih zaslona (14. 10. 2026).
    property string dom: ""
    // Priljubljene datoteke, mape in programi, kategorije programov, razvrscanje in pogled Programov: en zapis v Safeer OS
    // (core/priljubljeno.py) za to namizje in delovno povrsino WebKit; sprememba pride kot dogodek »priljubljeno«.
    property var priljubljeno: ({ datoteke: [], programi: [], kategorije: ({}), nastavitve: ({}), izSkupine: ({}), kategorijeProgramov: [] })
    // Odgovori mostu tecejo v vec nitih: odgovor starejse spremembe lahko pride za dogodkom novejse. Stanje starejsega
    // rodu (core/priljubljeno.py »rod«) se ne uporabi - sicer bi namizje pokazalo, kar ni vec res (pregled 15. 10. 2026).
    function nastaviPriljubljeno(p) {
        if (!p || Array.isArray(p) || typeof p !== "object") return
        if (typeof p.rod === "number" && typeof priljubljeno.rod === "number" && p.rod < priljubljeno.rod) return
        priljubljeno = p
    }
    function naloziPriljubljeno() {
        if (platforma !== "linux") return
        klic("priljubljenoSeznam", [], function (p) { koren.nastaviPriljubljeno(p) })
    }
    function jePriljubljenaPot(pot) { return (priljubljeno.datoteke || []).some(function (d) { return d.pot === pot }) }
    function jePriljubljenProgram(kljuc) { return (priljubljeno.programi || []).indexOf(kljuc) >= 0 }
    // vrsta "datoteka" (podatek {pot, ime, mapa}) ali "program" (kljuc); vkljuci: true/false ali undefined (preklopi).
    function preklopiPriljubljeno(vrsta, podatek, ime, vkljuci) {
        var a = [vrsta, podatek]
        if (vkljuci === true || vkljuci === false) a.push(vkljuci)
        var bilo = vrsta === "program" ? jePriljubljenProgram(podatek) : jePriljubljenaPot(podatek.pot)
        klic("priljubljenoPreklopi", a, function (p) {
            if (!p) return
            koren.nastaviPriljubljeno(p)
            // Iz tega odgovora (ne iz koren.priljubljeno - ta je lahko ze novejsi ali odgovor ni bil uporabljen).
            var je = vrsta === "program" ? (p.programi || []).indexOf(podatek) >= 0
                                         : (p.datoteke || []).some(function (d) { return d.pot === podatek.pot })
            if (ime && je !== bilo) obvesti(t(je ? "dodanoPriljubljeno" : "odstranjenoPriljubljeno", { ime: ime }))
        }, function () { obvesti(t("niUspelo")) })
    }
    function kratkaPot(p) {
        p = p || ""
        if (!dom) return p
        return p === dom ? "~" : (p.indexOf(dom + "/") === 0 ? "~" + p.slice(dom.length) : p)
    }

    // Aplikacija v oknu (GNOME, KDE …): desnega klika na ozadje nihce ne isce - Nastavitve in Prilagodi kot gumb.
    property bool vOknu: false
    Rectangle {
        id: gumbNastavitve
        objectName: "gumbNastavitve"
        visible: koren.vOknu
        anchors.right: parent.right; anchors.rightMargin: koren.rob
        anchors.verticalCenter: iskanje.verticalCenter
        width: 40; height: 40; radius: 20
        color: mn.containsMouse || activeFocus ? koren.prekriv(0.16) : koren.plosca(koren.prosojnostPlosc)
        border.width: activeFocus ? 2 : 1
        border.color: activeFocus ? koren.paleta.fokus : koren.crta(0.12)
        Accessible.role: Accessible.Button
        Accessible.name: koren.t("nastavitve")
        activeFocusOnTab: true
        Keys.onReturnPressed: meniNamizja.popup(gumbNastavitve, 0, height + 6)
        Keys.onSpacePressed: meniNamizja.popup(gumbNastavitve, 0, height + 6)
        Text { anchors.centerIn: parent; text: "\u2699"; color: koren.paleta.besedilo; font.pixelSize: koren.px(20) }
        MouseArea { id: mn; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                    onClicked: meniNamizja.popup(gumbNastavitve, 0, gumbNastavitve.height + 6) }
        ToolTip.visible: mn.containsMouse; ToolTip.text: koren.t("nastavitve"); ToolTip.delay: 500
    }

    // ------------------------------------------------------------------ paneli
    readonly property real rob: 30
    // Prostor pultov (Linux Mint zgoraj ali spodaj): nastavi os_lupina iz delovnega obmocja zaslona (14. 10. 2026).
    property real robZgoraj: 0
    property real robSpodaj: 0
    property real robLevo: 0
    property real robDesno: 0
    // Paneli pod gumbom Safeer Link (ta zraste z vecjim besedilom sistema)
    readonly property real vrhPanelov: Math.max(robZgoraj + 104, vrsticaCipov.y + vrsticaCipov.height - 2)
    // Medijski center: kaj se predvaja (lastnik, 14. 10. 2026: med glasbo je pripomocek kazal »Ni predvajanja«). Isto stanje
    // kot delovna.js in Medijski center (predvajalnikStanje: domaci predvajalnik ali skladba s seznama v vgradnem predvajalniku
    // YouTuba), osvezevanje 1 s med predvajanjem, sicer 3 s; dogodek »predvajalnik« osvezi takoj.
    property var medij: ({})
    readonly property bool medijIgra: !!medij.naslov && medij.stanje !== "ustavljeno"
    function osveziMedij() { koren.klic("predvajalnikStanje", [], function (p) { koren.medij = p || {} }) }
    function medijUkaz(u, v) { koren.klic("predvajalnikUkaz", v === undefined ? [u] : [u, v], function () { koren.osveziMedij() }) }
    // Premik po posnetku samo, ce ga predvajalnik res zna (kot drsnik vrstice »Predvaja se« v Medijskem centru): ne prenos v
    // zivo, ne Spotify (njegov trak vodi stran v Safeer DRM). Prej je bil napredek na namizju le prikaz (popis 3.1, 18. 10. 2026).
    // Ukaze skok, ustavi in predvajaj <n> pozna most na Linuxu (safeer_os._medijski_ukaz); drugje gumbov ni.
    readonly property bool medijLinux: medijIgra && platforma === "linux"
    readonly property bool medijPremik: medijLinux && Number(medij.trajanje) > 0 && !medij.zivo && !medij.spotify
                                        && medij.vrsta !== "tv" && medij.vrsta !== "radio"
    function casMedija(s) {
        s = Math.max(0, Math.floor(Number(s) || 0))
        var h = Math.floor(s / 3600), m = Math.floor(s % 3600 / 60), x = ("0" + s % 60).slice(-2)
        return h ? h + ":" + ("0" + m).slice(-2) + ":" + x : m + ":" + x
    }
    // Klik na ovitek: video ali vgradni predvajalnik spet v oknu; kar okna nima (glasba), odpre Medijski center.
    function odpriPredvajanje() {
        koren.klic("predvajalnikUkaz", ["odpri"], function (ok) { if (ok !== true) koren.klic("odpriRazdelek", ["media"]) },
                   function () { koren.klic("odpriRazdelek", ["media"]) })
    }
    // Glasnost privzetega izhoda (isti pactl/wpctl kot vrstica Medijskega centra in hitre nastavitve): beremo ob odprtju.
    property var zvokSistema: null
    function naloziGlasnost() { koren.klic("zvokGlasnost", [], function (z) { koren.zvokSistema = z || null }) }
    Timer { interval: koren.medij.stanje === "predvaja" ? 1000 : 3000; running: true; repeat: true; triggeredOnStart: true
            onTriggered: koren.osveziMedij() }
    function opisMedija() {
        var p = koren.medij
        if (!koren.medijIgra) return koren.t("medijOpis")
        var deli = [p.stanje === "napaka" ? koren.t("napakaPredvajanja") : p.stanje === "premor" ? koren.t("vPremoru")
                    : (p.vrsta === "tv" || p.vrsta === "radio") ? koren.t("vZivo") : koren.t("predvaja")]
        if (p.izvajalec) deli.push(p.izvajalec)
        if (p.izvor) deli.push(p.izvor)
        var izh = koren.izhodZ ? Izhod.SafeerIzhod.aktivna(koren.izhodZ) : null
        if (izh && izh.vrsta !== "racunalnik") deli.push(koren.t("predvajaNa", { ime: izh.ime }))
        return deli.join(" · ")
    }
    // Kam gre zvok (izhod.js, isto kot »Predvajaj na …« v Medijskem centru): ob predvajanju vsakih 15 s za znak na gumbu.
    property var izhodZ: null
    function naloziIzhode() { koren.klic("zvok", [], function (z) { koren.izhodZ = z || {}; izhodi.narisi() }) }
    Timer { interval: 15000; running: koren.medijIgra && !izhodi.visible; repeat: true; triggeredOnStart: true; onTriggered: koren.naloziIzhode() }
    function pozneje(ms, fn) {
        var c = Qt.createQmlObject("import QtQuick; Timer { repeat: false }", koren)
        c.interval = ms
        c.triggered.connect(function () { fn(); c.destroy() })
        c.start()
    }
    readonly property var ikone: ({
        prejsnja: "M6 5v14 M19 5 9 12l10 7z", naslednja: "M18 5v14 M5 5l10 7-10 7z",
        predvajaj: "M7 4.5v15l12.5-7.5z", premor: "M6.5 5h3.2v14H6.5z M14.3 5h3.2v14h-3.2z",
        oddajaj: "M3 8V6a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-5 M3 12a8 8 0 0 1 8 8 M3 16a4 4 0 0 1 4 4 M3 20h.01",
        ponovno: "M20 12a8 8 0 1 1-2.3-5.7 M20 4v5h-5",
        racunalnik: "M3 4h18v13H3z M3 14h18 M9 21h6", naprava: "M3 4h18v12H3z M8 20h8 M12 16v4",
        zvocnik: "M4 9v6h4l5 4V5L8 9z M16 9a4 4 0 0 1 0 6 M18.5 6.5a8 8 0 0 1 0 11", kljukica: "M5 12.5l4.5 4.5L19 7.5",
        utisan: "M4 9v6h4l5 4V5L8 9z M16 9l5 6 M21 9l-5 6", ustavi: "M6.5 6.5h11v11h-11z", odpri: "M14 4h6v6 M20 4l-9 9 M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5", vrsta: "M4 6h16 M4 12h16 M4 18h10 M18 16v5l3-2.5z" })
    Steklo {
        id: medijski
        objectName: "medijski"
        zamegljeno: zamegljeno
        x: koren.robLevo + koren.rob; y: koren.vrhPanelov
        width: (koren.width - koren.robLevo - koren.robDesno - 3 * koren.rob) * 0.44; height: Math.max(150, medijVsebina.implicitHeight + 36)
        Column {
            id: medijVsebina
            anchors.fill: parent; anchors.margins: 18; spacing: 10
            RowLayout {
                width: parent.width; spacing: 6
                Text { text: koren.t("medijski"); color: koren.paleta.besedilo; font.pixelSize: koren.px(16); font.bold: true; Layout.fillWidth: true
                       elide: Text.ElideRight }
                // Cakalna vrsta domacega predvajalnika (skladbe in videi iz Datotek ali knjiznice): izbira z misko ali tipkami.
                GumbIkona {
                    id: gumbVrsta
                    objectName: "medijVrsta"
                    visible: koren.medijLinux && (koren.medij.skupaj || 0) > 1 && (koren.medij.vrstaSeznam || []).length > 0
                    pot: koren.ikone.vrsta; width: 30; height: 30; velikostIkone: 17
                    ime: koren.t("cakalnaVrsta")
                    Accessible.role: Accessible.ButtonMenu
                    onKlik: vrstaPopup.visible ? vrstaPopup.close() : vrstaPopup.open()
                }
                GumbIkona {
                    id: gumbGlasnost
                    objectName: "medijGlasnost"
                    visible: koren.medijLinux
                    pot: koren.zvokSistema && koren.zvokSistema.utisan ? koren.ikone.utisan : koren.ikone.zvocnik
                    width: 30; height: 30; velikostIkone: 17
                    ime: koren.t("glasnost")
                    Accessible.role: Accessible.ButtonMenu
                    onKlik: glasnostPopup.visible ? glasnostPopup.close() : glasnostPopup.open()
                }
                GumbIkona {
                    id: gumbIzhod
                    objectName: "medijIzhod"
                    readonly property var aktivna: koren.izhodZ ? Izhod.SafeerIzhod.aktivna(koren.izhodZ) : null
                    pot: koren.ikone.oddajaj; width: 30; height: 30; velikostIkone: 17
                    vklopljen: !!aktivna && aktivna.vrsta !== "racunalnik"
                    ime: vklopljen ? koren.t("predvajaNa", { ime: aktivna.ime }) : koren.t("predvajajNa")
                    Accessible.role: Accessible.ButtonMenu
                    onKlik: izhodi.visible ? izhodi.close() : izhodi.open()
                }
                // Ozka plosca (okno 960 px, zaslon 1024 px): gumb z napisom postane ikona, naslov ostane berljiv (posnetek 18. 10. 2026).
                Gumb { visible: medijski.width >= koren.px(470); besedilo: koren.t("odpriMedijski"); onKlik: koren.klic("odpriRazdelek", ["media"]) }
                GumbIkona {
                    objectName: "medijOdpriIkona"
                    visible: medijski.width < koren.px(470)
                    pot: koren.ikone.odpri; width: 30; height: 30; velikostIkone: 16; ime: koren.t("odpriMedijski")
                    onKlik: koren.klic("odpriRazdelek", ["media"])
                }
            }
            RowLayout {
                width: parent.width; spacing: 14
                Item {
                    id: ovitek
                    objectName: "medijOvitek"
                    Layout.preferredWidth: 54; Layout.preferredHeight: 54
                    // Med predvajanjem je ovitek gumb: pokaze, kar se predvaja (video v oknu ali Medijski center).
                    activeFocusOnTab: koren.medijLinux
                    Accessible.role: Accessible.Button
                    Accessible.name: koren.t("odpriPredvajanje")
                    Accessible.onPressAction: if (koren.medijLinux) koren.odpriPredvajanje()
                    Keys.onReturnPressed: if (koren.medijLinux) koren.odpriPredvajanje()
                    Keys.onEnterPressed: if (koren.medijLinux) koren.odpriPredvajanje()
                    Keys.onSpacePressed: if (koren.medijLinux) koren.odpriPredvajanje()
                    Rectangle {
                        anchors.fill: parent; radius: 12
                        gradient: Gradient { GradientStop { position: 0; color: koren.paleta.poudarek } GradientStop { position: 1; color: koren.paleta.vnos } }
                        Text { anchors.centerIn: parent; text: "♫"; color: koren.paleta.besedilo; font.pixelSize: koren.px(24) }
                    }
                    // Naslovnica iz kataloga (ce jo predvajalnik pozna), z zaobljenimi robovi kot znak.
                    Image {
                        id: slikaOvitka
                        objectName: "medijSlika"
                        anchors.fill: parent; visible: false; layer.enabled: true
                        source: koren.medijIgra && koren.medij.slika ? koren.medij.slika : ""
                        fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize: Qt.size(108, 108)
                    }
                    Shape {
                        objectName: "medijSlikaUcinek"
                        anchors.fill: parent
                        visible: slikaOvitka.status === Image.Ready
                        ShapePath {
                            strokeColor: "transparent"; fillItem: slikaOvitka
                            PathRectangle { width: 54; height: 54; radius: 12 }
                        }
                    }
                    Rectangle {
                        anchors.fill: parent; radius: 12; color: "transparent"
                        border.width: ovitek.activeFocus ? 2 : 0; border.color: koren.paleta.fokus
                    }
                    MouseArea { anchors.fill: parent; enabled: koren.medijLinux; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: koren.odpriPredvajanje()
                                ToolTip.visible: containsMouse; ToolTip.text: koren.t("odpriPredvajanje"); ToolTip.delay: 500 }
                }
                Column {
                    Layout.fillWidth: true; spacing: 4
                    Text {
                        objectName: "medijNaslov"
                        width: parent.width; elide: Text.ElideRight
                        text: koren.medijIgra ? koren.medij.naslov : koren.t("niPredvajanja")
                        color: koren.paleta.besedilo; font.pixelSize: koren.px(15); font.bold: true
                    }
                    Text {
                        objectName: "medijOpis"
                        width: parent.width; elide: Text.ElideRight
                        text: koren.opisMedija()
                        color: koren.paleta.medlo; font.pixelSize: koren.px(12)
                    }
                }
                Row {
                    spacing: 4; visible: koren.medijIgra
                    GumbIkona {
                        objectName: "medijPrejsnja"
                        pot: koren.ikone.prejsnja; polnilo: true; ime: koren.t("prejsnja")
                        anchors.verticalCenter: parent.verticalCenter
                        enabled: !!koren.medij.vrstaStrani || koren.medij.indeks > 0
                        onKlik: koren.medijUkaz("prejsnja")
                    }
                    GumbIkona {
                        objectName: "medijPremor"
                        width: 42; height: 42; velikostIkone: 18; poudarjen: true; polnilo: true
                        pot: koren.medij.stanje === "predvaja" ? koren.ikone.premor : koren.ikone.predvajaj
                        ime: koren.medij.stanje === "predvaja" ? koren.t("premor") : koren.t("nadaljuj")
                        onKlik: koren.medijUkaz("premor")
                    }
                    GumbIkona {
                        objectName: "medijNaslednja"
                        pot: koren.ikone.naslednja; polnilo: true; ime: koren.t("naslednja")
                        anchors.verticalCenter: parent.verticalCenter
                        enabled: !!koren.medij.vrstaStrani || koren.medij.indeks < (koren.medij.skupaj || 0) - 1
                        onKlik: koren.medijUkaz("naslednja")
                    }
                    GumbIkona {
                        objectName: "medijUstavi"
                        visible: koren.platforma === "linux"
                        pot: koren.ikone.ustavi; polnilo: true; ime: koren.t("ustaviMedij"); velikostIkone: 15
                        anchors.verticalCenter: parent.verticalCenter
                        onKlik: koren.medijUkaz("ustavi")
                    }
                }
            }
            // Polozaj samo, ce ga predvajalnik pozna (ne tok v zivo, ne vgradni predvajalnik YouTuba) - brez laznega drsnika.
            // Premik: miska (klik ali vlecenje) ali puscici levo/desno po 10 s; casa sta levo in desno kot v Medijskem centru.
            RowLayout {
                objectName: "medijNapredek"
                visible: koren.medijIgra && Number(koren.medij.trajanje) > 0
                width: parent.width; spacing: 8
                Text { objectName: "medijCas"; text: koren.casMedija(drsnikMedija.pressed ? drsnikMedija.value : koren.medij.pozicija)
                       color: koren.paleta.medlo; font.pixelSize: koren.px(11); font.family: "monospace" }
                Slider {
                    id: drsnikMedija
                    objectName: "medijDrsnik"
                    Layout.fillWidth: true; implicitHeight: 18
                    from: 0; to: Math.max(1, Number(koren.medij.trajanje) || 1); stepSize: 10
                    enabled: koren.medijPremik; focusPolicy: Qt.StrongFocus
                    Accessible.name: koren.t("polozajPredvajanja") + " " + koren.casMedija(value) + " / " + koren.casMedija(to)
                    Binding on value { value: Number(koren.medij.pozicija) || 0; when: !drsnikMedija.pressed; restoreMode: Binding.RestoreNone }
                    // Tipkovnica premakne takoj, miska ob spustu (med vlecenjem tece cas naprej, drsnik ne skace).
                    onMoved: if (!pressed) koren.medijUkaz("skok", value)
                    onPressedChanged: if (!pressed && enabled) koren.medijUkaz("skok", value)
                    background: Rectangle {
                        x: drsnikMedija.leftPadding; y: drsnikMedija.topPadding + drsnikMedija.availableHeight / 2 - height / 2
                        width: drsnikMedija.availableWidth; height: 4; radius: 2; color: koren.prekriv(0.12)
                        Rectangle { width: drsnikMedija.visualPosition * parent.width; height: parent.height; radius: 2; color: koren.paleta.poudarek }
                    }
                    handle: Rectangle {
                        x: drsnikMedija.leftPadding + drsnikMedija.visualPosition * (drsnikMedija.availableWidth - width)
                        y: drsnikMedija.topPadding + drsnikMedija.availableHeight / 2 - height / 2
                        width: 12; height: 12; radius: 6; color: koren.paleta.besedilo
                        border.width: drsnikMedija.activeFocus ? 2 : 0; border.color: koren.paleta.fokus
                        visible: drsnikMedija.enabled && (drsnikMedija.hovered || drsnikMedija.pressed || drsnikMedija.activeFocus)
                    }
                }
                Text { objectName: "medijTrajanje"; text: koren.casMedija(koren.medij.trajanje)
                       color: koren.paleta.medlo; font.pixelSize: koren.px(11); font.family: "monospace" }
            }
        }
    }

    // Cakalna vrsta domacega predvajalnika (isti seznam kot plosca »Cakalna vrsta« v Medijskem centru): okno okoli
    // trenutne skladbe; Enter, preslednica ali klik predvaja izbrano. Escape ali klik drugam zapre.
    Popup {
        id: vrstaPopup
        objectName: "vrstaPopup"
        parent: gumbVrsta
        x: gumbVrsta.width - width; y: gumbVrsta.height + 8
        width: 330; padding: 12
        modal: false; focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
        readonly property int zacetek: koren.medij.zacetniIndeks || 0
        function izberi(i) { if (i >= 0) koren.medijUkaz("predvajaj", zacetek + i) }
        onOpened: {
            seznamVrste.currentIndex = Math.max(0, Math.min((koren.medij.indeks || 0) - zacetek, seznamVrste.count - 1))
            seznamVrste.positionViewAtIndex(seznamVrste.currentIndex, ListView.Contain)
            seznamVrste.forceActiveFocus()
        }
        onClosed: gumbVrsta.forceActiveFocus()
        background: Rectangle { radius: 14; color: koren.paleta.vnos; border.color: koren.crta(0.14) }
        contentItem: Column {
            spacing: 8
            RowLayout {
                width: parent.width
                Text { text: koren.t("cakalnaVrsta"); color: koren.paleta.besedilo; font.pixelSize: koren.px(15); font.bold: true; Layout.fillWidth: true }
                Text { text: String(koren.medij.skupaj || 0); color: koren.paleta.medlo; font.pixelSize: koren.px(12) }
            }
            ListView {
                id: seznamVrste
                objectName: "seznamVrste"
                width: parent.width; height: Math.min(contentHeight, 300)
                model: koren.medij.vrstaSeznam || []; clip: true; spacing: 2
                keyNavigationEnabled: true; activeFocusOnTab: true
                Accessible.role: Accessible.List; Accessible.name: koren.t("cakalnaVrsta")
                Keys.onReturnPressed: vrstaPopup.izberi(currentIndex)
                Keys.onEnterPressed: vrstaPopup.izberi(currentIndex)
                Keys.onSpacePressed: vrstaPopup.izberi(currentIndex)
                delegate: Rectangle {
                    id: vrsticaVrste
                    required property var modelData
                    required property int index
                    readonly property bool zdaj: vrstaPopup.zacetek + index === koren.medij.indeks
                    readonly property bool izbran: seznamVrste.activeFocus && index === seznamVrste.currentIndex
                    readonly property string pod: modelData.vrsta === "tv" || modelData.vrsta === "radio" ? koren.t("vZivo")
                                                  : (modelData.izvor || koren.t("medijTaRacunalnik"))
                    width: seznamVrste.width; height: 44; radius: 10
                    color: zdaj ? koren.poudarekA(0.22) : (izbran || mv.containsMouse) ? koren.prekriv(0.10) : "transparent"
                    border.width: izbran ? 2 : 0; border.color: koren.paleta.poudarek
                    Accessible.role: Accessible.ListItem
                    Accessible.name: modelData.naslov + ", " + pod
                    Accessible.selected: zdaj
                    Text {
                        x: 10; width: 26; anchors.verticalCenter: parent.verticalCenter; horizontalAlignment: Text.AlignHCenter
                        text: vrsticaVrste.zdaj ? "♫" : String(vrstaPopup.zacetek + vrsticaVrste.index + 1)
                        color: vrsticaVrste.zdaj ? koren.paleta.poudarek : koren.paleta.medlo; font.pixelSize: koren.px(12)
                    }
                    Column {
                        x: 44; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 54; spacing: 2
                        Text { text: vrsticaVrste.modelData.naslov || ""; width: parent.width; elide: Text.ElideRight
                               color: koren.paleta.besedilo; font.pixelSize: koren.px(13); font.bold: vrsticaVrste.zdaj }
                        Text { text: vrsticaVrste.pod; width: parent.width; elide: Text.ElideRight; color: koren.paleta.medlo; font.pixelSize: koren.px(11) }
                    }
                    MouseArea { id: mv; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: { seznamVrste.currentIndex = vrsticaVrste.index; vrstaPopup.izberi(vrsticaVrste.index) } }
                }
            }
        }
    }

    // Glasnost privzetega izhoda in utisaj (kot drsnik v vrstici Medijskega centra): drsnik s puscicami po 5 %.
    Popup {
        id: glasnostPopup
        objectName: "glasnostPopup"
        parent: gumbGlasnost
        x: gumbGlasnost.width - width; y: gumbGlasnost.height + 8
        width: 280; padding: 12
        modal: false; focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
        onOpened: { koren.naloziGlasnost(); drsnikGlasnosti.forceActiveFocus() }
        onClosed: gumbGlasnost.forceActiveFocus()
        background: Rectangle { radius: 14; color: koren.paleta.vnos; border.color: koren.crta(0.14) }
        Timer { id: casovnikGlasnosti; interval: 120
                onTriggered: koren.klic("glasnost", [Math.round(drsnikGlasnosti.value)], function () { koren.naloziGlasnost() }) }
        contentItem: RowLayout {
            spacing: 8
            GumbIkona {
                objectName: "glasnostUtisaj"
                readonly property bool utisan: !!(koren.zvokSistema && koren.zvokSistema.utisan)
                pot: utisan ? koren.ikone.utisan : koren.ikone.zvocnik; vklopljen: utisan
                width: 30; height: 30; velikostIkone: 17
                ime: koren.t(utisan ? "vklopiZvok" : "utisaj")
                onKlik: koren.klic("utisaj", [], function () { koren.naloziGlasnost() })
            }
            Slider {
                id: drsnikGlasnosti
                objectName: "drsnikGlasnosti"
                Layout.fillWidth: true; implicitHeight: 22
                from: 0; to: 100; stepSize: 5
                enabled: !!koren.zvokSistema
                Accessible.name: koren.t("glasnost") + " " + Math.round(value) + " %"
                Binding on value { value: koren.zvokSistema ? Math.min(100, Number(koren.zvokSistema.glasnost) || 0) : 0
                                   when: !drsnikGlasnosti.pressed && !casovnikGlasnosti.running; restoreMode: Binding.RestoreNone }
                onMoved: casovnikGlasnosti.restart()
                background: Rectangle {
                    x: drsnikGlasnosti.leftPadding; y: drsnikGlasnosti.topPadding + drsnikGlasnosti.availableHeight / 2 - height / 2
                    width: drsnikGlasnosti.availableWidth; height: 4; radius: 2; color: koren.prekriv(0.12)
                    Rectangle { width: drsnikGlasnosti.visualPosition * parent.width; height: parent.height; radius: 2; color: koren.paleta.poudarek }
                }
                handle: Rectangle {
                    x: drsnikGlasnosti.leftPadding + drsnikGlasnosti.visualPosition * (drsnikGlasnosti.availableWidth - width)
                    y: drsnikGlasnosti.topPadding + drsnikGlasnosti.availableHeight / 2 - height / 2
                    width: 14; height: 14; radius: 7; color: koren.paleta.besedilo
                    border.width: drsnikGlasnosti.activeFocus ? 2 : 0; border.color: koren.paleta.fokus
                }
            }
            Text { objectName: "glasnostOdstotek"; text: Math.round(drsnikGlasnosti.value) + " %"; color: koren.paleta.medlo; font.pixelSize: koren.px(12)
                   Layout.preferredWidth: koren.px(40); horizontalAlignment: Text.AlignRight }
        }
    }

    // »Predvajaj na …«: ta racunalnik, naprave v Safeer Linku in zvocniki v omrezju (izhod.js). Escape ali klik drugam zapre;
    // puscici gor/dol, Enter ali preslednica izbere.
    Popup {
        id: izhodi
        objectName: "izhodiPopup"
        parent: gumbIzhod
        x: gumbIzhod.width - width; y: gumbIzhod.height + 8
        width: 330; padding: 12
        modal: false; focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
        property var st: Izhod.SafeerIzhod.novoStanje()
        property var moznosti: []
        property string stanjeBesedilo: ""
        property bool isce: false           // izhod.js pise v st (navaden objekt): vezave berejo to lastnost
        function gost() {
            return { klic: function (m, a, ok, napaka) { koren.klic(m, a, ok, napaka) },
                     obvesti: function (k, z) { koren.obvesti(koren.t(k, z)) },
                     osvezi: function () { koren.naloziIzhode() }, narisi: function () { izhodi.narisi() },
                     pozneje: function (ms, fn) { koren.pozneje(ms, fn) } }
        }
        function narisi() {
            var z = koren.izhodZ, i = seznamIzhodov.currentIndex
            moznosti = z ? Izhod.SafeerIzhod.moznosti(z) : []
            seznamIzhodov.currentIndex = Math.max(0, Math.min(i, moznosti.length - 1))
            isce = !!st.isce
            stanjeBesedilo = !z ? koren.t("izhodNalagam") : st.isce ? koren.t("zvokIscem")
                           : Izhod.SafeerIzhod.imaDruge(z) ? "" : koren.t("zvokNiIzhodov")
        }
        function opis(m) {
            if (st.caka && st.caka === m.id && !m.aktiven) return koren.t("zvokPovezujem")
            var pod = m.vrsta === "racunalnik" ? m.pod : m.vrsta === "zvocnik" ? koren.t("zvokZvocnik") + (m.model ? " · " + m.model : "") : "Safeer Link"
            if (m.aktiven && m.stanje) return koren.t(m.stanje === "tece" ? "zvokPredvaja" : "zvokPovezujem") + " · " + pod
            if (st.potrdi[m.id]) return koren.t("zvokZvocnikPreklopi", { vir: st.potrdi[m.id] })
            return pod
        }
        function izberi(i) { if (i >= 0 && i < moznosti.length) Izhod.SafeerIzhod.izberi(st, moznosti[i], koren.izhodZ, gost()) }
        onOpened: {
            narisi()
            for (var i = 0; i < moznosti.length; i++) if (moznosti[i].aktiven) seznamIzhodov.currentIndex = i
            seznamIzhodov.forceActiveFocus()
            koren.klic("zvok", [], function (z) {
                koren.izhodZ = z || {}; izhodi.narisi()
                if (!((koren.izhodZ.link || {}).zvocniki || []).length && !izhodi.st.isce) Izhod.SafeerIzhod.isci(izhodi.st, izhodi.gost())
            })
        }
        onClosed: gumbIzhod.forceActiveFocus()
        Timer { interval: 3000; running: izhodi.visible; repeat: true; onTriggered: koren.naloziIzhode() }
        background: Rectangle { radius: 14; color: koren.paleta.vnos; border.color: koren.crta(0.14) }
        contentItem: Column {
            spacing: 8
            RowLayout {
                width: parent.width
                Text { text: koren.t("predvajajNaNaslov"); color: koren.paleta.besedilo; font.pixelSize: koren.px(15); font.bold: true; Layout.fillWidth: true }
                GumbIkona {
                    objectName: "izhodIsci"
                    pot: koren.ikone.ponovno; width: 30; height: 30; velikostIkone: 16; ime: koren.t("zvokIsci")
                    enabled: !izhodi.isce
                    onKlik: Izhod.SafeerIzhod.isci(izhodi.st, izhodi.gost())
                }
            }
            ListView {
                id: seznamIzhodov
                objectName: "seznamIzhodov"
                width: parent.width; height: Math.min(contentHeight, 300)
                model: izhodi.moznosti; clip: true; spacing: 2
                keyNavigationEnabled: true; activeFocusOnTab: true
                Accessible.role: Accessible.List; Accessible.name: koren.t("predvajajNaNaslov")
                Keys.onReturnPressed: izhodi.izberi(currentIndex)
                Keys.onEnterPressed: izhodi.izberi(currentIndex)
                Keys.onSpacePressed: izhodi.izberi(currentIndex)
                delegate: Rectangle {
                    id: vrsticaIzhoda
                    required property var modelData
                    required property int index
                    readonly property bool izbran: seznamIzhodov.activeFocus && index === seznamIzhodov.currentIndex
                    readonly property string ime: modelData.vrsta === "racunalnik" ? koren.t("taRacunalnik") : modelData.ime
                    readonly property string pod: izhodi.opis(modelData)
                    width: seznamIzhodov.width; height: 50; radius: 10
                    color: modelData.aktiven ? koren.poudarekA(0.22) : (izbran || mi.containsMouse) ? koren.prekriv(0.10) : "transparent"
                    border.width: izbran ? 2 : 0; border.color: koren.paleta.poudarek
                    Accessible.role: Accessible.RadioButton
                    Accessible.name: ime + (pod ? ", " + pod : "")
                    Accessible.checked: !!modelData.aktiven
                    Shape {
                        x: 12; anchors.verticalCenter: parent.verticalCenter; width: 24; height: 24; scale: 0.9
                        ShapePath {
                            strokeColor: vrsticaIzhoda.modelData.aktiven ? koren.paleta.poudarek : koren.paleta.medlo; strokeWidth: 1.8
                            fillColor: "transparent"; capStyle: ShapePath.RoundCap; joinStyle: ShapePath.RoundJoin
                            PathSvg { path: koren.ikone[vrsticaIzhoda.modelData.vrsta] || "" }
                        }
                    }
                    Column {
                        x: 48; anchors.verticalCenter: parent.verticalCenter; width: parent.width - 48 - 36; spacing: 2
                        Text { text: vrsticaIzhoda.ime; color: koren.paleta.besedilo; font.pixelSize: koren.px(13); font.bold: true; width: parent.width; elide: Text.ElideRight }
                        Text { text: vrsticaIzhoda.pod; visible: text !== ""; color: koren.paleta.medlo; font.pixelSize: koren.px(11); width: parent.width; elide: Text.ElideRight }
                    }
                    Shape {
                        visible: !!vrsticaIzhoda.modelData.aktiven
                        anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter; width: 24; height: 24; scale: 0.8
                        ShapePath { strokeColor: koren.paleta.poudarek; strokeWidth: 2; fillColor: "transparent"; capStyle: ShapePath.RoundCap
                                    PathSvg { path: koren.ikone.kljukica } }
                    }
                    MouseArea { id: mi; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: { seznamIzhodov.currentIndex = vrsticaIzhoda.index; izhodi.izberi(vrsticaIzhoda.index) } }
                }
            }
            Text {
                objectName: "izhodStanje"
                width: parent.width; wrapMode: Text.WordWrap; visible: text !== ""
                text: izhodi.stanjeBesedilo; color: koren.paleta.medlo; font.pixelSize: koren.px(12)
                Accessible.role: Accessible.StaticText
            }
        }
    }

    Datoteke {
        id: datoteke
        zamegljeno: zamegljeno
        x: medijski.x; y: medijski.y + medijski.height + koren.rob * 0.6
        width: medijski.width; height: koren.height - koren.robSpodaj - y - koren.rob
    }

    Programi {
        id: programi
        zamegljeno: zamegljeno
        x: medijski.x + medijski.width + koren.rob; y: koren.vrhPanelov
        width: koren.width - koren.robDesno - x - koren.rob; height: koren.height - koren.robSpodaj - y - koren.rob
    }

    // vstop: paneli prihajajo drug za drugim
    Component.onCompleted: {
        var paneli = [medijski, datoteke, programi]
        for (var i = 0; i < paneli.length; i++) { paneli[i].opacity = 0; paneli[i].scale = 0.97 }
        vstop.start()
        koren.klic("zacetek", [], function (z) {
            z = z || {}
            koren.nastaviJezik(z.jezik)
            if (z.platforma) koren.platforma = z.platforma
            koren.vOknu = !!z.vOknu
            koren.dom = (z.mape && z.mape[0] && z.mape[0].pot) || ""
            koren.ozadjeUrl = z.ozadje || ""
            if (z.videz) koren.uporabiVidez(z.videz)
            datoteke.zacni(z.mape || [])
            // Spletne aplikacije (shranjene v Safeer OS) in mapa Prenosi (GitHub v »Namesti programe …«).
            programi.spletne = Array.isArray(z.spletne) ? z.spletne : []
            programi.mapaPrenosov = ((z.mape || []).filter(function (m) { return m.vrsta === "DOWNLOAD" })[0] || {}).pot || ""
            if (koren.platforma === "linux") koren.klic("povezava", [], function (p) { koren.linkStanje = p || null })
            koren.naloziPriljubljeno()
            programi.naloziOblak()
            koren.osveziSporocila()
        })
        programi.nalozi()
        koren.klic("lupaUcenje", [], function (p) { zadetki.izbire = (p && p.izbire) || [] })
        osveziLink()
    }
    // Safeer Link se ob zagonu sele poveze: stevilo naprav osvezimo na 20 s.
    property var naprave: []
    // Stanje povezave (povezava -> safeer_os.stanje_povezave): nepovezan racunalnik s Safeer Controlom dobi »Poveži se v
    // Safeer Link« in klik odpre prijavno okno Controla (kot gumb Link na delovni povrsini); sicer razdelek Naprave.
    property var linkStanje: null
    function linkNepovezan() { return !!linkStanje && !!linkStanje.control && linkStanje.stanje !== "povezan" }
    function linkKlik() {
        if (linkNepovezan()) koren.klic("prijava", [], function (ok) { if (ok === false) koren.obvesti(koren.t("brezControla")); koren.pozneje(8000, koren.osveziLink) })
        else koren.klic("odpriRazdelek", ["naprave"])
    }
    function osveziLink() {
        koren.klic("napraveNamizja", [], function (n) { koren.naprave = n || []; koren.napravVLinku = koren.naprave.length })
        if (platforma === "linux") koren.klic("povezava", [], function (p) { koren.linkStanje = p || null })
    }
    Timer { interval: 20000; running: true; repeat: true; onTriggered: koren.osveziLink() }
    SequentialAnimation {
        id: vstop
        PauseAnimation { duration: 120 }
        ParallelAnimation {
            NumberAnimation { target: medijski; property: "opacity"; to: 1; duration: 380; easing.type: Easing.OutCubic }
            NumberAnimation { target: medijski; property: "scale"; to: 1; duration: 380; easing.type: Easing.OutCubic }
            SequentialAnimation {
                PauseAnimation { duration: 90 }
                ParallelAnimation {
                    NumberAnimation { target: datoteke; property: "opacity"; to: 1; duration: 380; easing.type: Easing.OutCubic }
                    NumberAnimation { target: datoteke; property: "scale"; to: 1; duration: 380; easing.type: Easing.OutCubic }
                }
            }
            SequentialAnimation {
                PauseAnimation { duration: 180 }
                ParallelAnimation {
                    NumberAnimation { target: programi; property: "opacity"; to: 1; duration: 380; easing.type: Easing.OutCubic }
                    NumberAnimation { target: programi; property: "scale"; to: 1; duration: 380; easing.type: Easing.OutCubic }
                }
            }
        }
    }

    // ------------------------------------------------------------------ prilagodi namizje (desni klik na ozadje)
    MouseArea {
        anchors.fill: parent
        z: -1
        acceptedButtons: Qt.RightButton
        onClicked: function (m) { meniNamizja.popup() }
    }
    // Kot meni plosc na delovni povrsini: Prilagodi namizje, Prilagodi dock … (Plank), tema sistema.
    Meni {
        id: meniNamizja
        objectName: "meniNamizja"
        MeniVnos { text: koren.t("prilagodi"); onTriggered: prilagodi.odpri() }
        MeniVnos { text: koren.t("prilagodiDock"); visible: koren.platforma === "linux"; onTriggered: programi.urediDock() }
        MeniVnos { text: koren.t("temaSistema"); onTriggered: koren.klic("odpriRazdelek", ["nastavitve"]) }
    }
    Prilagodi { id: prilagodi; objectName: "prilagodi"; z: 30; anchors.fill: parent }

    // ------------------------------------------------------------------ obvestilo spodaj (z dejanjem, npr. Razveljavi)
    Rectangle {
        id: obvestilo
        z: 20
        property var ob: null
        anchors.horizontalCenter: parent.horizontalCenter
        y: koren.height - koren.robSpodaj - 70
        height: 40; radius: 20; width: vrsticaObv.width + 30
        color: koren.plosca(0.94); border.color: koren.crta(0.14)
        opacity: 0; visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 200 } }
        function pokazi(b, dejanje, ob) {
            napisObv.text = b; gumbObv.besedilo = dejanje || ""; obvestilo.ob = ob || null
            opacity = 1; skrijObv.restart()
        }
        Row {
            id: vrsticaObv; anchors.centerIn: parent; spacing: 14
            Text { id: napisObv; color: koren.paleta.besedilo; font.pixelSize: koren.px(13); anchors.verticalCenter: parent.verticalCenter }
            Gumb { id: gumbObv; visible: besedilo !== ""; onKlik: { if (obvestilo.ob) obvestilo.ob(); obvestilo.opacity = 0 } }
        }
        Timer { id: skrijObv; interval: 6000; onTriggered: obvestilo.opacity = 0 }
    }
}
