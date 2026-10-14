// Namizje Safeer OS za Windows in Linux (Qt Quick). Ista dela kot na Linuxu: iskanje, Medijski center, datoteke, programi,
// Safeer Link. Podatki pridejo iz Pythona prek »Most« (iste metode kot spletna stran na Linuxu).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Shapes
import "../izhod.js" as Izhod
import "../besedila-namizja.js" as Besedila

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
            if (vrsta === "datoteke" && p && p.pot === datoteke.vir.pot) datoteke.nalozi(true)
            if (vrsta === "videz" && p) koren.uporabiVidez(p)
            if (vrsta === "iskanjeOdDrugod" && p && p.q) { polje.text = p.q; polje.forceActiveFocus() }
            if (vrsta === "predvajalnik" && p) koren.medij = p
            if (vrsta === "medijskaKnjiznica") koren.osveziMedij()
        }
    }
    property string jezik: "sl"
    // Barve iz assets/os/tokens.css (en vir z vmesnikom, Spletom, delovno povrsino in Controlom): paleto poslje
    // core/os_lupina.paleta ob »zacetek« in dogodku »videz«. Spodaj je le rezerva do prvega odgovora (iste vrednosti,
    // preverja tests/test_namizje_celota.py), da prvi izris ni v drugih barvah.
    property var paleta: ({ poudarek: "#8ac7ff", poudarekTemna: "#0b1424", besedilo: "#eaf2ff", medlo: "#afbed4",
                            tise: "#93a9c4", vnos: "#121d2d", ozadje: "#0b1424", ozadje2: "#152a3d", fokus: "#9dceff",
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
    Steklo {
        id: iskanje
        zamegljeno: zamegljeno
        width: Math.min(640, koren.width * 0.46); height: 54
        anchors.horizontalCenter: parent.horizontalCenter
        y: koren.robZgoraj + 18
        polmer: 27
        TextField {
            id: polje
            anchors.fill: parent; anchors.leftMargin: 52; anchors.rightMargin: 18
            placeholderText: koren.t("isci")
            placeholderTextColor: koren.paleta.medlo
            color: koren.paleta.besedilo; font.pixelSize: koren.px(16)
            background: Item {}
            onTextChanged: casovnikIskanja.restart()
            Keys.onReturnPressed: zadetki.izberi(zadetki.trenutni)
            Keys.onDownPressed: { zadetki.premaknjen = true; zadetki.trenutni = Math.min(zadetki.trenutni + 1, zadetkiModel.count - 1) }
            Keys.onUpPressed: { zadetki.premaknjen = true; zadetki.trenutni = Math.max(zadetki.trenutni - 1, 0) }
            Keys.onEscapePressed: koren.zapriVrhnje()
        }
        Lupa { x: 20; anchors.verticalCenter: parent.verticalCenter }
    }
    Timer { id: casovnikIskanja; interval: 180; onTriggered: zadetki.isci(polje.text) }
    // Escape zapre, kar je zgoraj (kot Nazaj na daljincu TV): Prilagodi namizje, sicer zadetke iskanja. Meniji in okna
    // (Popup, Menu) se zaprejo sami (CloseOnEscape), zato bliznjica takrat ne velja. Puscice in Tab: vsak del namizja
    // (iskanje, Medijski center, viri in seznam Datotek, kategorije in mreza Programov, gumbi) ima fokus in tipke.
    function zapriVrhnje() {
        if (prilagodi.visible) { prilagodi.zapri(); return true }
        if (polje.text !== "") { polje.text = ""; polje.forceActiveFocus(); return true }
        return false
    }
    Shortcut {
        sequences: [StandardKey.Cancel, "Back"]
        enabled: (prilagodi.visible || polje.text !== "") && !izhodi.visible && !meniNamizja.visible
        onActivated: koren.zapriVrhnje()
    }
    ListModel { id: zadetkiModel; objectName: "zadetkiModel" }
    Steklo {
        id: zadetki
        objectName: "zadetki"
        zamegljeno: zamegljeno
        z: 10
        property int trenutni: 0
        property int zahteva: 0
        visible: polje.text.length > 0 && zadetkiModel.count > 0
        width: iskanje.width; x: iskanje.x; y: iskanje.y + iskanje.height + 8
        height: Math.min(420, seznamZadetkov.contentHeight + 16)
        barva: koren.plosca(Math.min(0.95, koren.prosojnostPlosc + 0.27))
        // Ucenje lupe (core/os_lupa.py, isti zapis kot prejsnja delovna povrsina): kar je uporabnik za tak niz ze
        // izbral, je prvo. Izbire [niz, kljuc, cas, prvi]; novejse stejejo vec (polovica po 30 dneh), enak niz dvojno.
        property var izbire: []
        property string zadnjiNiz: ""
        property bool premaknjen: false
        function nizUcenja(q) {
            var n = String(q || "").toLowerCase()
            // Iste posebne crke kot iskanje.js / delovna.js: skupen zapis ucenja (core/os_lupa.py).
            var POSEBNE = { "\u0111": "d", "\u0142": "l", "\u00f8": "o", "\u00df": "ss", "\u00e6": "ae", "\u0153": "oe", "\u0131": "i" }
            n = n.replace(/[\u0111\u0142\u00f8\u00df\u00e6\u0153\u0131]/g, function (z) { return POSEBNE[z] })
            if (n.normalize) n = n.normalize("NFD").replace(/[\u0300-\u036f]/g, "")
            return n.replace(/\s+/g, " ").trim()
        }
        function kljucZadetka(z) { return z.vrsta === "splet" ? "splet" : (z.vrsta === "mapa" ? "datoteka" : z.vrsta) + ":" + z.kljuc }
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
        function poUcenju() {
            var k = []
            for (var i = 0; i < zadetkiModel.count; i++) k.push(kljucZadetka(zadetkiModel.get(i)))
            var naj = najMesto(k)
            if (naj > 0) zadetkiModel.move(naj, 0, 1)
            if (!premaknjen) trenutni = 0       // izbire, ki jo je uporabnik ze premaknil, ne ponastavimo
        }
        function isci(q) {
            zadetkiModel.clear(); trenutni = 0
            q = (q || "").trim(); zadnjiNiz = q; premaknjen = false; if (!q) return
            var st = ++zahteva, ql = q.toLowerCase()
            programi.vsi.filter(function (p) { return p.ime.toLowerCase().indexOf(ql) >= 0 }).slice(0, 5)
                .forEach(function (p) { zadetkiModel.append({ vrsta: "program", ime: p.ime, opis: koren.t("programi"), kljuc: p.id, ikona: p.ikona || "" }) })
            zadetkiModel.append({ vrsta: "splet", ime: koren.t("splet") + ": " + q, opis: "", kljuc: q, ikona: "" })
            poUcenju()
            koren.klic("isciDatoteke", [q, 8], function (r) {
                if (st !== zahteva) return
                ;(r || []).forEach(function (d) {
                    // Pred zadetek »Splet« (ki je po ucenju lahko prvi), sicer na konec (pregled 14. 10.).
                    var sp = -1
                    for (var i = 0; i < zadetkiModel.count; i++) if (zadetkiModel.get(i).vrsta === "splet") { sp = i; break }
                    zadetkiModel.insert(sp > 0 ? sp : zadetkiModel.count, { vrsta: d.mapa ? "mapa" : "datoteka", ime: d.ime, opis: koren.kratkaPot(d.pot), kljuc: d.pot, ikona: "" })
                })
                poUcenju()
            })
        }
        function izberi(i) {
            if (i < 0 || i >= zadetkiModel.count) return
            var z = zadetkiModel.get(i)
            var ql = nizUcenja(zadnjiNiz), k = kljucZadetka(z)
            if (ql && k) {
                izbire.push([ql, k, Math.round(Date.now() / 1000), i === 0])
                if (izbire.length > 500) izbire.shift()
                koren.klic("lupaZapomni", [ql, k, i === 0])
            }
            if (z.vrsta === "program") koren.klic("zazeni", [z.kljuc], function (ok) { if (!ok) koren.obvesti(koren.t("niUspelo")) })
            else if (z.vrsta === "datoteka") koren.klic("odpriDatoteko", [z.kljuc])
            else if (z.vrsta === "mapa") datoteke.odpriLokalno(z.kljuc)   // mapa se odpre v Datotekah (tega racunalnika)
            else koren.klic("spletNaNamizju", [z.kljuc])
            polje.text = ""
        }
        ListView {
            id: seznamZadetkov
            anchors.fill: parent; anchors.margins: 8
            model: zadetkiModel; clip: true; interactive: contentHeight > height
            delegate: Rectangle {
                width: seznamZadetkov.width; height: koren.px(46); radius: 10
                color: index === zadetki.trenutni ? koren.prekriv(0.12) : (mz.containsMouse ? koren.prekriv(0.06) : "transparent")
                Row {
                    anchors.verticalCenter: parent.verticalCenter; x: 10; spacing: 12
                    Image { source: model.ikona; width: 26; height: 26; visible: model.ikona !== ""; sourceSize: Qt.size(52, 52) }
                    Text { text: model.vrsta === "splet" ? "🌐" : model.vrsta === "mapa" ? "📁" : "📄"; visible: model.ikona === ""; font.pixelSize: koren.px(20); width: 26 }
                    Column {
                        Text { text: model.ime; color: koren.paleta.besedilo; font.pixelSize: koren.px(14); elide: Text.ElideRight; width: seznamZadetkov.width - 70 }
                        Text { text: model.opis; color: koren.paleta.medlo; font.pixelSize: koren.px(11); elide: Text.ElideMiddle; width: seznamZadetkov.width - 70; visible: text !== "" }
                    }
                }
                MouseArea { id: mz; anchors.fill: parent; hoverEnabled: true; onClicked: zadetki.izberi(index) }
            }
        }
    }

    // Safeer Link pod iskanjem
    property int napravVLinku: 0
    Rectangle {
        id: linkGumb
        anchors.horizontalCenter: parent.horizontalCenter
        y: iskanje.y + iskanje.height + 10
        visible: !zadetki.visible
        height: koren.px(26); width: linkVrstica.width + 22; radius: height / 2
        color: ml.containsMouse || activeFocus ? koren.prekriv(0.16) : koren.plosca(koren.prosojnostPlosc)
        border.width: activeFocus ? 2 : 1
        border.color: activeFocus ? koren.paleta.fokus : koren.crta(0.12)
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: koren.t("linkNaslov")
        Keys.onReturnPressed: koren.klic("odpriRazdelek", ["naprave"])
        Keys.onEnterPressed: koren.klic("odpriRazdelek", ["naprave"])
        Keys.onSpacePressed: koren.klic("odpriRazdelek", ["naprave"])
        Behavior on color { ColorAnimation { duration: 150 } }
        Row {
            id: linkVrstica; anchors.centerIn: parent; spacing: 7
            Rectangle { width: 7; height: 7; radius: 4; color: koren.napravVLinku > 0 ? koren.paleta.poudarek : koren.paleta.medlo; anchors.verticalCenter: parent.verticalCenter }
            Text { text: koren.t("link") + (koren.napravVLinku > 0 ? " · " + koren.steviloNaprav(koren.napravVLinku) : ""); color: koren.paleta.besedilo; font.pixelSize: koren.px(12) }
        }
        MouseArea { id: ml; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: koren.klic("odpriRazdelek", ["naprave"]) }
    }

    // Domaca mapa kot »~« (kot upravitelji datotek): krajse in brez uporabniskega imena na posnetkih zaslona (14. 10. 2026).
    property string dom: ""
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
    readonly property real vrhPanelov: Math.max(robZgoraj + 104, linkGumb.y + linkGumb.height - 2)
    // Medijski center: kaj se predvaja (lastnik, 14. 10. 2026: med glasbo je pripomocek kazal »Ni predvajanja«). Isto stanje
    // kot delovna.js in Medijski center (predvajalnikStanje: domaci predvajalnik ali skladba s seznama v vgradnem predvajalniku
    // YouTuba), osvezevanje 1 s med predvajanjem, sicer 3 s; dogodek »predvajalnik« osvezi takoj.
    property var medij: ({})
    readonly property bool medijIgra: !!medij.naslov && medij.stanje !== "ustavljeno"
    function osveziMedij() { koren.klic("predvajalnikStanje", [], function (p) { koren.medij = p || {} }) }
    function medijUkaz(u) { koren.klic("predvajalnikUkaz", [u], function () { koren.osveziMedij() }) }
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
        zvocnik: "M4 9v6h4l5 4V5L8 9z M16 9a4 4 0 0 1 0 6 M18.5 6.5a8 8 0 0 1 0 11", kljukica: "M5 12.5l4.5 4.5L19 7.5" })
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
                width: parent.width; spacing: 8
                Text { text: koren.t("medijski"); color: koren.paleta.besedilo; font.pixelSize: koren.px(16); font.bold: true; Layout.fillWidth: true
                       elide: Text.ElideRight }
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
                Gumb { besedilo: koren.t("odpriMedijski"); onKlik: koren.klic("odpriRazdelek", ["media"]) }
            }
            RowLayout {
                width: parent.width; spacing: 14
                Item {
                    id: ovitek
                    Layout.preferredWidth: 54; Layout.preferredHeight: 54
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
                    spacing: 6; visible: koren.medijIgra
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
                }
            }
            // Polozaj samo, ce ga predvajalnik pozna (ne tok v zivo, ne vgradni predvajalnik YouTuba) - brez laznega drsnika.
            Rectangle {
                objectName: "medijNapredek"
                visible: koren.medijIgra && Number(koren.medij.trajanje) > 0
                width: parent.width; height: 4; radius: 2; color: koren.prekriv(0.12)
                Accessible.role: Accessible.ProgressBar
                Accessible.name: Math.floor((koren.medij.pozicija || 0) / 60) + ":" + ("0" + Math.floor((koren.medij.pozicija || 0) % 60)).slice(-2)
                Rectangle {
                    height: parent.height; radius: 2; color: koren.paleta.poudarek
                    width: parent.width * Math.min(1, Math.max(0, (koren.medij.pozicija || 0) / (koren.medij.trajanje || 1)))
                }
            }
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
        })
        programi.nalozi()
        koren.klic("lupaUcenje", [], function (p) { zadetki.izbire = (p && p.izbire) || [] })
        osveziLink()
    }
    // Safeer Link se ob zagonu sele poveze: stevilo naprav osvezimo na 20 s.
    property var naprave: []
    function osveziLink() {
        koren.klic("napraveNamizja", [], function (n) { koren.naprave = n || []; koren.napravVLinku = koren.naprave.length })
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
    Menu {
        id: meniNamizja
        background: Rectangle { implicitWidth: 230; radius: 12; color: koren.paleta.vnos; border.color: koren.crta(0.14) }
        MenuItem {
            text: koren.t("prilagodi")
            contentItem: Text { text: parent.text; color: koren.paleta.besedilo; font.pixelSize: koren.px(13); leftPadding: 6 }
            background: Rectangle { radius: 8; color: parent.highlighted ? koren.poudarekA(0.22) : "transparent" }
            onTriggered: prilagodi.odpri()
        }
        MenuItem {
            text: koren.t("temaSistema")
            contentItem: Text { text: parent.text; color: koren.paleta.besedilo; font.pixelSize: koren.px(13); leftPadding: 6 }
            background: Rectangle { radius: 8; color: parent.highlighted ? koren.poudarekA(0.22) : "transparent" }
            onTriggered: koren.klic("odpriRazdelek", ["nastavitve"])
        }
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
