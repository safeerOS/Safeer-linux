// Panel Programi: vsi programi menija Start z ikonami, iskanje, skupine; klik zazene program. Kot na delovni povrsini
// WebKit (delovna.js): tudi shranjene spletne aplikacije, igre v oblaku (igreOblak) z namestitvijo iz uradnega vira,
// »Namesti programe …« (ponudniki, viri, GitHub) in »Prilagodi dock …« (vrstni red, dodaj, odstrani).
// Priljubljeni (skupni zapis Safeer OS, core/priljubljeno.py): vrstica na vrhu v uporabnikovem vrstnem redu (vleci ali
// Alt+puscica), kategorija »★ Priljubljeni«, Ctrl+D; razvrscanje po imenu ali uporabi, pogled mreza/seznam in
// prestavitev programa v drugo kategorijo - vse zapomnjeno in isto kot na delovni povrsini.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Steklo {
    id: panel
    property var vsi: []
    property string skupina: ""          // "" = vse, "priljubljeni" ali kategorija
    property string niz: ""
    // Na Linuxu Safeer OS pozna se igre v oblaku in ponudnike programov (metode mostu, ki jih Windows nima).
    readonly property bool linux: koren.platforma === "linux"
    readonly property var pril: koren.priljubljeno || ({})
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
    // Kljuc programa kot kljucPrograma v delovna.js (naprava + ":" + id): priljubljeni in kategorije so skupni.
    function kljuc(p) {
        if (!p) return ""
        return p.url ? "splet:" + p.id : p.ponudnikOblaka ? "oblak:" + p.id : (naprava || "ta") + ":" + p.id
    }
    readonly property var poKljucih: {
        var m = {}
        seznam.forEach(function (p) { m[panel.kljuc(p)] = p })
        return m
    }
    // Kategorija: uporabnikova izbira, sicer iz skupine programa (isti katalog kot delovna povrsina, IZ_SKUPINE).
    function kategorijaP(p) {
        var k = (pril.kategorije || {})[kljuc(p)]
        if (k) return k
        return (pril.izSkupine || {})[p.skupina] || p.skupina || "drugo"
    }
    readonly property var skupine: {
        var s = {}, red = pril.kategorijeProgramov || []
        seznam.forEach(function (p) { s[panel.kategorijaP(p)] = true })
        return Object.keys(s).sort(function (a, b) {
            var x = red.indexOf(a), y = red.indexOf(b)
            x = x < 0 ? 99 : x; y = y < 0 ? 99 : y
            return x !== y ? x - y : a.localeCompare(b)
        })
    }
    // Priljubljeni te naprave v uporabnikovem vrstnem redu (priljubljeni drugih naprav so v zapisu, a tu jih ni).
    readonly property var priljubljeni: (pril.programi || []).filter(function (k) { return !!poKljucih[k] }).map(function (k) { return poKljucih[k] })
    function jePriljubljen(p) { return koren.jePriljubljenProgram(kljuc(p)) }
    // Razvrscanje in pogled: na Linuxu v skupnem zapisu (zapomnjeno, isto na delovni povrsini), drugje do zaprtja.
    property string razvrstiTu: ""
    property string pogledTu: ""
    readonly property string razvrsti: razvrstiTu || (pril.nastavitve || {}).programiRazvrsti || "ime"
    readonly property bool seznamPogled: (pogledTu || (pril.nastavitve || {}).programiPogled || "mreza") === "seznam"
    property bool zastarelo: false       // uporaba se je spremenila, ko je bil seznam po imenu
    function nastavi(kljuc_, vrednost) {
        if (!linux) { if (kljuc_ === "programiRazvrsti") razvrstiTu = vrednost; else pogledTu = vrednost; return }
        koren.klic("priljubljenoNastavi", [kljuc_, vrednost], function (p) { koren.nastaviPriljubljeno(p) })
    }
    function nastaviRazvrsti(v) { nastavi("programiRazvrsti", v); if (zastarelo && v !== "ime") nalozi() }
    function ujema(p) { return !niz || String(p.ime).toLowerCase().indexOf(niz.toLowerCase()) >= 0 }
    readonly property var prikazani: {
        if (skupina === "priljubljeni") return priljubljeni.filter(ujema)
        var r = seznam.filter(function (p) { return (!skupina || panel.kategorijaP(p) === skupina) && panel.ujema(p) })
        var po = razvrsti
        return r.sort(function (a, b) {
            if (po === "nazadnje" && (b.zadnjic || 0) !== (a.zadnjic || 0)) return (b.zadnjic || 0) - (a.zadnjic || 0)
            if (po === "najveckrat" && (b.uporaba || 0) !== (a.uporaba || 0)) return (b.uporaba || 0) - (a.uporaba || 0)
            var c = String(a.ime).toLowerCase().localeCompare(String(b.ime).toLowerCase())
            // Enaka imena (dva »Terminal«): vedno isti vrstni red, ne da ploscici ob vsakem osvezevanju zamenjata mesti.
            return c !== 0 ? c : (panel.kljuc(a) < panel.kljuc(b) ? -1 : panel.kljuc(a) > panel.kljuc(b) ? 1 : 0)
        })
    }
    property string naprava: ""          // "" = ta racunalnik
    property string imeNaprave: ""
    property string stanje: ""           // "", "nalagam", "napaka", "prazno"
    property int zahteva: 0
    function nalozi() {
        var st = ++zahteva
        panel.vsi = []; zastarelo = false
        if (skupina !== "priljubljeni") panel.skupina = ""
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
    // Program namescen ali odstranjen (dogodek »programi«, Safeer OS spremlja mape z zaganjalniki): seznam se osvezi
    // brez praznjenja, izbrana kategorija in iskanje ostaneta; priljubljeni odstranjenega se skrijejo, ob ponovni
    // namestitvi vrnejo na svoje mesto (prej se odprta plosca ni osvezila do ponovnega odprtja).
    function osveziTiho() {
        if (naprava) return
        var st = ++zahteva
        koren.klic("programiNamizja", [], function (s) { if (st === zahteva) { panel.vsi = s || []; panel.stanje = ""; panel.zastarelo = false } })
    }
    // Igre v oblaku (igreOblak) - na Linuxu; klice se tudi ob »zacetek«, ko namizje izve platformo.
    function naloziOblak() { if (linux) koren.klic("igreOblak", [], function (o) { panel.oblak = o || [] }) }
    function zazeni(p) {
        if (p.ponudnikOblaka) { meniOblaka.pokazi(p.ponudnikOblaka); return }
        if (p.url) { koren.klic("splet", [p.url]); return }
        if (!naprava) {
            koren.klic("zazeni", [p.id], function (ok) { if (!ok) koren.obvesti(koren.t("niUspelo")); else panel.zabeleziZagon(p) })
            return
        }
        // Program naprave se odpre TUKAJ (naprava ga zazene in pretaka sliko), kot v Safeer OS.
        koren.obvesti(koren.t("odpiramZ", { ime: p.ime, naprava: imeNaprave }))
        koren.klic("odpriTukaj", [naprava, p.id], function (r) {
            if (!(r === true || (r && r.ok))) koren.obvesti(r && r.koda === "ni_locenega_zaslona" ? koren.t("niLocenega") : ((r && r.message) || koren.t("niUspelo")))
        })
    }
    // Zagon zabelezi Safeer OS (os_programi.zabelezi); tu samo osvezimo prikaz razvrscanja po uporabi.
    function zabeleziZagon(p) {
        if (razvrsti === "ime") { zastarelo = true; return }
        var zdaj = Date.now() / 1000
        vsi = vsi.map(function (x) { return x.id === p.id ? Object.assign({}, x, { uporaba: (x.uporaba || 0) + 1, zadnjic: zdaj }) : x })
    }
    // Imena skupin v jeziku vmesnika (prej samo slovensko - tudi v angleskem Safeer OS in na Windows).
    function imeSkupine(s) {
        if (s === "priljubljeni") return koren.t("kPriljubljeni")
        var k = "sk_" + s, b = koren.t(k)
        return b !== k ? b : (s.charAt(0).toUpperCase() + s.slice(1))
    }
    function preklopiPriljubljen(p) {
        if (!linux || !p || !p.id) return
        koren.preklopiPriljubljeno("program", kljuc(p), p.ime)
    }
    // Vrstni red priljubljenih: vleci v vrstici ali Alt+puscica. Priljubljeni drugih naprav ostanejo na svojih mestih.
    ListModel { id: modelPril }
    property bool vlecemPril: false
    onPriljubljeniChanged: if (!vlecemPril) sinhronizirajPril()
    function sinhronizirajPril() {
        var k = priljubljeni.map(function (p) { return panel.kljuc(p) })
        var enako = k.length === modelPril.count
        for (var i = 0; enako && i < k.length; i++) enako = modelPril.get(i).kljuc === k[i]
        if (enako) return
        modelPril.clear()
        k.forEach(function (x) { modelPril.append({ kljuc: x }) })
    }
    function vrstniRedPril() { var k = []; for (var i = 0; i < modelPril.count; i++) k.push(modelPril.get(i).kljuc); return k }
    function premakniPriljubljen(od, kam) {
        if (od === kam || od < 0 || kam < 0 || od >= modelPril.count || kam >= modelPril.count) return false
        modelPril.move(od, kam, 1)
        shraniVrstniRed()
        return true
    }
    function shraniVrstniRed() {
        // Samo kljuci, ki so v zapisu: program, odstranjen med vlecenjem, ne sme zamakniti ostalih.
        var zapis = pril.programi || []
        var k = vrstniRedPril().filter(function (x) { return zapis.indexOf(x) >= 0 }), vidni = {}, j = 0
        k.forEach(function (x) { vidni[x] = true })
        var polno = zapis.map(function (x) { return vidni[x] ? k[j++] : x })
        if (JSON.stringify(polno) === JSON.stringify(pril.programi || [])) return
        // Takoj vidno (tudi v kategoriji Priljubljeni); Safeer OS potrdi in poslje obema namizjema.
        var z = {}
        for (var x in pril) z[x] = pril[x]
        z.programi = polno
        koren.priljubljeno = z
        koren.klic("priljubljenoVrstniRed", ["programi", polno], function (p) { koren.nastaviPriljubljeno(p) })
    }
    function prestaviVKategorijo(p, k) {
        koren.klic("priljubljenoKategorija", [kljuc(p), k], function (r) { koren.nastaviPriljubljeno(r) }, function () { koren.obvesti(koren.t("niUspelo")) })
    }
    function meniZa(p, kje, x, y) {
        if (!p) return
        if (p.ponudnikOblaka) meniOblaka.pokazi(p.ponudnikOblaka)
        else meniPrograma.pokazi(p, kje, x, y)
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
            // Spletna aplikacija (kot »Dodaj« na Domov aplikacije Safeer OS): ime in naslov, odpre se v Spletu (popis 3.1).
            GumbIkona {
                objectName: "gumbDodajSpletno"
                visible: panel.linux && panel.naprava === ""
                pot: "M12 5v14 M5 12h14"; ime: koren.t("spletnaDodaj"); velikostIkone: 17
                onKlik: dodajSpletno.odpri()
            }
            Rectangle {
                Layout.fillWidth: true; height: 34; radius: 17
                color: koren.prekriv(0.07); border.color: koren.crta(0.12)
                Lupa { x: 12; anchors.verticalCenter: parent.verticalCenter; scale: 0.8 }
                TextField {
                    id: poljeProgramov
                    objectName: "poljeProgramov"
                    anchors.fill: parent; anchors.leftMargin: 36; anchors.rightMargin: 12
                    placeholderText: koren.t("isciProg"); placeholderTextColor: koren.paleta.medlo; color: koren.paleta.besedilo; font.pixelSize: koren.px(13)
                    background: Item {}
                    onTextChanged: panel.niz = text
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true; spacing: 8
            Flow {
                Layout.fillWidth: true; spacing: 6
                Repeater {
                    model: [""].concat(panel.linux && panel.priljubljeni.length ? ["priljubljeni"] : []).concat(panel.skupine)
                    delegate: Rectangle {
                        height: koren.px(26); width: n.implicitWidth + 22; radius: height / 2
                        color: panel.skupina === modelData ? koren.paleta.poudarek : (ms.containsMouse || activeFocus ? koren.prekriv(0.14) : koren.prekriv(0.07))
                        border.width: activeFocus ? 2 : 0; border.color: koren.paleta.fokus
                        activeFocusOnTab: true
                        Accessible.role: Accessible.RadioButton; Accessible.name: n.text; Accessible.checked: panel.skupina === modelData
                        Keys.onReturnPressed: panel.skupina = modelData
                        Keys.onEnterPressed: panel.skupina = modelData
                        Keys.onSpacePressed: panel.skupina = modelData
                        Behavior on color { enabled: koren.gibanje; ColorAnimation { duration: 140 } }
                        Text {
                            id: n; anchors.centerIn: parent; font.pixelSize: koren.px(12)
                            text: modelData === "" ? koren.t("vse") : panel.imeSkupine(modelData)
                            color: panel.skupina === modelData ? koren.paleta.poudarekTemna : koren.paleta.besedilo
                        }
                        MouseArea { id: ms; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: panel.skupina = modelData }
                    }
                }
            }
            // Razvrsti: po imenu ali po uporabi (Safeer OS steje zagone programov tega racunalnika).
            Gumb {
                id: gumbRazvrsti
                objectName: "gumbRazvrsti"
                // Samo kjer Safeer OS steje zagone (Linux): brez podatkov o uporabi bi bila izbira prazna obljuba.
                visible: panel.linux && panel.naprava === "" && panel.skupina !== "priljubljeni"
                besedilo: koren.t("razvrstiPo", { k: koren.t(panel.razvrsti === "nazadnje" ? "razvrstiNazadnje"
                                                              : panel.razvrsti === "najveckrat" ? "razvrstiNajveckrat" : "razvrstiIme") }) + "  ▾"
                onKlik: meniRazvrsti.popup(gumbRazvrsti, 0, gumbRazvrsti.height + 4)
            }
            GumbIkona {
                objectName: "gumbPogled"
                pot: panel.seznamPogled ? "M4 4h7v7H4z M13 4h7v7h-7z M4 13h7v7H4z M13 13h7v7h-7z" : "M4 6h16 M4 12h16 M4 18h16"
                ime: koren.t("pogledSeznam"); velikostIkone: 16
                onKlik: panel.nastavi("programiPogled", panel.seznamPogled ? "mreza" : "seznam")
            }
        }
        // Priljubljeni: vrstica na vrhu (kategorija Vse, brez iskanja) v uporabnikovem vrstnem redu.
        ColumnLayout {
            Layout.fillWidth: true; spacing: 4
            visible: panel.linux && panel.skupina === "" && panel.niz === "" && modelPril.count > 0
            RowLayout {
                Layout.fillWidth: true
                Text { text: koren.t("kPriljubljeni"); color: koren.paleta.besedilo; font.pixelSize: koren.px(12); font.bold: true }
                Text { Layout.fillWidth: true; text: koren.t("priljubljeniNamig"); color: Qt.darker(koren.paleta.medlo, 1.1)
                       font.pixelSize: koren.px(11); elide: Text.ElideRight; horizontalAlignment: Text.AlignRight }
            }
            ListView {
                id: vrstaPril
                objectName: "vrstaPriljubljenih"
                Layout.fillWidth: true; Layout.preferredHeight: koren.px(84)
                orientation: ListView.Horizontal; spacing: 6; clip: true
                model: modelPril; boundsBehavior: Flickable.StopAtBounds
                activeFocusOnTab: true; keyNavigationEnabled: true; currentIndex: -1
                Accessible.role: Accessible.List; Accessible.name: koren.t("kPriljubljeni")
                onActiveFocusChanged: if (activeFocus && currentIndex < 0 && count > 0) currentIndex = 0
                function trenutni() { return currentIndex >= 0 && currentIndex < modelPril.count ? panel.poKljucih[modelPril.get(currentIndex).kljuc] : null }
                Keys.onPressed: function (d) {
                    var p = trenutni()
                    if ((d.modifiers & Qt.AltModifier) && (d.key === Qt.Key_Left || d.key === Qt.Key_Right)) {
                        var kam = currentIndex + (d.key === Qt.Key_Left ? -1 : 1)
                        if (panel.premakniPriljubljen(currentIndex, kam)) currentIndex = kam
                        d.accepted = true
                    } else if (p && (d.key === Qt.Key_Return || d.key === Qt.Key_Enter || d.key === Qt.Key_Space)) { panel.zazeni(p); d.accepted = true }
                    else if (p && (d.modifiers & Qt.ControlModifier) && d.key === Qt.Key_D) { panel.preklopiPriljubljen(p); d.accepted = true }
                    else if (p && (d.key === Qt.Key_Menu || (d.key === Qt.Key_F10 && (d.modifiers & Qt.ShiftModifier)))) {
                        panel.meniZa(p, currentItem, 20, currentItem ? currentItem.height : 0); d.accepted = true
                    }
                }
                delegate: DropArea {
                    id: celica
                    width: koren.px(96); height: vrstaPril.height
                    readonly property int vi: index
                    readonly property var p: panel.poKljucih[model.kljuc] || ({ ime: "", id: "" })
                    keys: ["safeer/priljubljen-program"]
                    onEntered: function (d) {
                        if (d.source && d.source.vi !== undefined && d.source.vi !== celica.vi) modelPril.move(d.source.vi, celica.vi, 1)
                    }
                    Rectangle {
                        id: ploscicaP
                        width: celica.width - 4; height: celica.height - 4
                        anchors.horizontalCenter: parent.horizontalCenter; anchors.verticalCenter: parent.verticalCenter
                        radius: 12
                        readonly property bool izbran: vrstaPril.activeFocus && celica.vi === vrstaPril.currentIndex
                        color: mpp.drag.active ? koren.poudarekA(0.25) : mpp.containsMouse || izbran ? koren.prekriv(0.13) : "transparent"   // mirujoca ploscica prosojna (lastnik 18. 10.)
                        border.width: izbran ? 2 : (mpp.containsMouse ? 1 : 0); border.color: izbran ? koren.paleta.fokus : koren.crta(0.08)
                        Accessible.role: Accessible.ListItem; Accessible.name: celica.p.ime
                        Drag.active: mpp.drag.active; Drag.source: celica; Drag.keys: ["safeer/priljubljen-program"]
                        Drag.hotSpot.x: width / 2; Drag.hotSpot.y: height / 2
                        states: State {
                            when: mpp.drag.active
                            ParentChange { target: ploscicaP; parent: vrstaPril }
                            AnchorChanges { target: ploscicaP; anchors.horizontalCenter: undefined; anchors.verticalCenter: undefined }
                        }
                        Image {
                            id: ikonaP; source: celica.p.ikona || ""; width: 32; height: 32; sourceSize: Qt.size(64, 64)
                            anchors.horizontalCenter: parent.horizontalCenter; y: 10; smooth: true; asynchronous: true
                        }
                        Rectangle {
                            visible: ikonaP.status !== Image.Ready; anchors.fill: ikonaP; radius: 8
                            color: koren.barvaVrste(celica.p.ponudnikOblaka ? "program" : celica.p.url ? "splet" : "program")
                            Text { anchors.centerIn: parent; text: (String(celica.p.ime || "?").trim().charAt(0) || "?").toUpperCase()
                                   color: koren.prekriv(1); font.pixelSize: koren.px(15); font.bold: true }
                        }
                        Text {
                            anchors.top: ikonaP.bottom; anchors.topMargin: 6; anchors.horizontalCenter: parent.horizontalCenter
                            width: parent.width - 10; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
                            text: celica.p.ime; color: koren.paleta.besedilo; font.pixelSize: koren.px(11)
                        }
                        MouseArea {
                            id: mpp; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            drag.target: ploscicaP; drag.axis: Drag.XAxis; drag.threshold: 10
                            property var redPrej: []
                            onPressed: function (m) { if (m.button === Qt.LeftButton) { panel.vlecemPril = true; redPrej = panel.vrstniRedPril() } }
                            onReleased: function (m) {
                                if (m.button !== Qt.LeftButton) return
                                ploscicaP.Drag.drop()
                                panel.vlecemPril = false
                                if (JSON.stringify(redPrej) !== JSON.stringify(panel.vrstniRedPril())) panel.shraniVrstniRed()
                                panel.sinhronizirajPril()     // program namescen/odstranjen med vlecenjem
                            }
                            onCanceled: { panel.vlecemPril = false; panel.sinhronizirajPril() }
                            onClicked: function (m) {
                                vrstaPril.currentIndex = celica.vi
                                if (m.button === Qt.RightButton) panel.meniZa(celica.p, null)
                                else panel.zazeni(celica.p)
                            }
                        }
                    }
                }
            }
        }
        GridView {
            id: mreza
            objectName: "mrezaProgramov"
            Layout.fillWidth: true; Layout.fillHeight: true
            clip: true
            readonly property int stolpcev: panel.seznamPogled ? 1 : Math.max(3, Math.floor(width / 128))
            cellWidth: width / stolpcev; cellHeight: panel.seznamPogled ? koren.px(44) : 112 + koren.px(14) - 14
            model: panel.prikazani
            // Tipkovnica in daljinec TV: puscice premikajo izbiro, Enter/preslednica zazene, tipka Meni odpre meni,
            // Ctrl+D priljubljen, v kategoriji Priljubljeni Alt+puscica premakne program.
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
                if ((d.modifiers & Qt.AltModifier) && panel.skupina === "priljubljeni" && panel.niz === ""
                        && (d.key === Qt.Key_Left || d.key === Qt.Key_Right || d.key === Qt.Key_Up || d.key === Qt.Key_Down)) {
                    var smer = d.key === Qt.Key_Left ? -1 : d.key === Qt.Key_Right ? 1 : d.key === Qt.Key_Up ? -stolpcev : stolpcev
                    var kam = currentIndex + smer
                    if (panel.premakniPriljubljen(currentIndex, kam)) currentIndex = kam
                    d.accepted = true
                    return
                }
                if (p && (d.modifiers & Qt.ControlModifier) && d.key === Qt.Key_D) { panel.preklopiPriljubljen(p); d.accepted = true; return }
                if (p && (d.key === Qt.Key_Menu || (d.key === Qt.Key_F10 && (d.modifiers & Qt.ShiftModifier)))) {
                    panel.meniZa(p, currentItem, 40, currentItem ? currentItem.height : 0)
                    d.accepted = true
                }
            }
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            add: Transition { enabled: koren.gibanje; NumberAnimation { property: "opacity"; from: 0; to: 1; duration: 200 } }
            Text {
                anchors.centerIn: parent; width: parent.width - 40; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
                visible: panel.stanje !== "" && panel.stanje !== "nalagam" || (panel.stanje === "nalagam" && mreza.count === 0)
                         || (panel.stanje === "" && mreza.count === 0 && panel.skupina === "priljubljeni")
                text: panel.stanje === "nalagam" ? koren.t("nalagam") : panel.stanje === "napaka" ? koren.t("niOdgovorila")
                    : panel.skupina === "priljubljeni" ? koren.t("niPriljubljenihPrg") : koren.t("brezProgramov")
                color: koren.paleta.medlo; font.pixelSize: koren.px(13)
            }
            delegate: Item {
                width: mreza.cellWidth; height: mreza.cellHeight
                readonly property bool vrsta: panel.seznamPogled
                Rectangle {
                    id: ploscica
                    anchors.fill: parent; anchors.margins: vrsta ? 2 : 5; radius: vrsta ? 10 : 14
                    readonly property bool izbran: mreza.activeFocus && index === mreza.currentIndex
                    readonly property bool priljubljen: panel.linux && panel.jePriljubljen(modelData)
                    color: mp.containsMouse || izbran ? koren.prekriv(0.13) : "transparent"   // mirujoca ploscica prosojna (lastnik 18. 10.)
                    border.width: izbran ? 2 : (mp.containsMouse ? 1 : 0)
                    border.color: izbran ? koren.paleta.fokus : mp.containsMouse ? koren.poudarekA(0.55) : koren.crta(0.08)
                    Accessible.role: Accessible.ListItem; Accessible.name: modelData.ime + (priljubljen ? ", " + koren.t("kPriljubljeni") : "")
                    scale: vrsta ? 1 : (mp.pressed ? 0.95 : (mp.containsMouse ? 1.04 : 1))
                    Behavior on scale { enabled: koren.gibanje; NumberAnimation { duration: 140; easing.type: Easing.OutCubic } }
                    Behavior on color { enabled: koren.gibanje; ColorAnimation { duration: 140 } }
                    Image {
                        id: slika
                        source: modelData.ikona || ""
                        width: vrsta ? 28 : 40; height: width; sourceSize: Qt.size(64, 64)
                        x: vrsta ? 10 : (parent.width - width) / 2; y: vrsta ? (parent.height - height) / 2 : 16
                        smooth: true; asynchronous: true
                    }
                    // Brez ikone (igra v oblaku, spletna aplikacija): crka namesto izmisljenega logotipa (kot delovna povrsina).
                    Rectangle {
                        visible: slika.status !== Image.Ready
                        anchors.fill: slika; radius: vrsta ? 7 : 10; color: koren.barvaVrste(modelData.ponudnikOblaka ? "program" : modelData.url ? "splet" : "program")
                        Text { anchors.centerIn: parent; text: (String(modelData.ime || "?").trim().charAt(0) || "?").toUpperCase()
                               color: koren.prekriv(1); font.pixelSize: koren.px(vrsta ? 14 : 18); font.bold: true }
                    }
                    Text {
                        id: imeP
                        x: vrsta ? slika.x + slika.width + 12 : 6
                        y: vrsta ? (parent.height - height) / 2 : slika.y + slika.height + 10
                        width: vrsta ? parent.width - x - kategorijaT.width - 40 : parent.width - 12
                        horizontalAlignment: vrsta ? Text.AlignLeft : Text.AlignHCenter
                        text: modelData.ime; color: koren.paleta.besedilo; font.pixelSize: koren.px(vrsta ? 13 : 12); elide: Text.ElideRight
                    }
                    Text {
                        id: kategorijaT
                        visible: vrsta
                        anchors.right: parent.right; anchors.rightMargin: 34; anchors.verticalCenter: parent.verticalCenter
                        text: vrsta ? (modelData.ponudnikOblaka ? "☁ " + modelData.ponudnikOblaka.ponudnik : panel.imeSkupine(panel.kategorijaP(modelData))) : ""
                        color: koren.paleta.medlo; font.pixelSize: koren.px(11)
                    }
                    Text {
                        visible: !vrsta && !!modelData.ponudnikOblaka
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
                            else { mreza.currentIndex = index; panel.meniZa(modelData, null) }
                        }
                    }
                    // Zvezdica: priljubljen (polna) ali dodaj (obris ob miski) - kot ☆/★ na delovni povrsini.
                    Text {
                        objectName: "zvezdica"
                        visible: panel.linux && !modelData.ponudnikOblaka && (ploscica.priljubljen || mp.containsMouse || mz.containsMouse || ploscica.izbran)
                        text: ploscica.priljubljen ? "★" : "☆"
                        color: ploscica.priljubljen ? koren.paleta.poudarek : koren.paleta.medlo; font.pixelSize: koren.px(15)
                        anchors.right: parent.right; anchors.rightMargin: 8
                        anchors.top: vrsta ? undefined : parent.top; anchors.topMargin: 5
                        anchors.verticalCenter: vrsta ? parent.verticalCenter : undefined
                        // Bralnik zaslona: zvezdica je gumb z imenom dejanja (tipkovnica: Ctrl+D na izbranem programu).
                        Accessible.role: Accessible.Button
                        Accessible.name: koren.t(ploscica.priljubljen ? "odstraniPriljubljeno" : "dodajPriljubljeno")
                        Accessible.onPressAction: panel.preklopiPriljubljen(modelData)
                        MouseArea { id: mz; anchors.fill: parent; anchors.margins: -6; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: panel.preklopiPriljubljen(modelData) }
                    }
                }
            }
        }
    }

    Meni {
        id: meniRazvrsti
        objectName: "meniRazvrsti"
        MeniVnos { text: (panel.razvrsti === "ime" ? "✓  " : "     ") + koren.t("razvrstiIme"); onTriggered: panel.nastaviRazvrsti("ime") }
        MeniVnos { text: (panel.razvrsti === "nazadnje" ? "✓  " : "     ") + koren.t("razvrstiNazadnje"); objectName: "vnosRazvrstiNazadnje"
                   onTriggered: panel.nastaviRazvrsti("nazadnje") }
        MeniVnos { text: (panel.razvrsti === "najveckrat" ? "✓  " : "     ") + koren.t("razvrstiNajveckrat"); onTriggered: panel.nastaviRazvrsti("najveckrat") }
    }

    // Desni klik na program: Odpri, priljubljen, kategorija; za programe tega racunalnika se Dodaj v dock / Odstrani iz
    // docka in Prilagodi dock … (kot prejsnja delovna povrsina; tam je »Prilagodi dock …« v meniju plosc).
    Meni {
        id: meniPrograma
        objectName: "meniPrograma"
        property var p: null
        property bool plank: false
        property bool vDocku: false
        function pokazi(p, kje, x, y) {
            meniPrograma.p = p
            var odpri = function () { if (kje) meniPrograma.popup(kje, x, y); else meniPrograma.popup() }
            // Podmeni Kategorija je samo tam, kjer Safeer OS hrani kategorije (Linux) - drugje bi bil prazen.
            for (var i = 0; i < meniPrograma.count; i++) {
                var it = meniPrograma.itemAt(i)
                if (it && it.subMenu === podmeniKategorija) it.visible = panel.linux
            }
            if (panel.naprava) { meniPrograma.plank = false; odpri(); return }
            koren.klic("dock", [], function (d) {
                meniPrograma.plank = !!(d && d.plank)
                meniPrograma.vDocku = !!(d && (d.programi || []).some(function (x) { return x.id === p.id }))
                odpri()
            }, function () { meniPrograma.plank = false; odpri() })
        }
        MeniVnos { text: koren.t("odpri"); onTriggered: panel.zazeni(meniPrograma.p) }
        MeniVnos { text: koren.t(meniPrograma.p && panel.jePriljubljen(meniPrograma.p) ? "odstraniPriljubljeno" : "dodajPriljubljeno")
                   objectName: "vnosPriljubljenProgram"; visible: panel.linux && !!meniPrograma.p
                   onTriggered: panel.preklopiPriljubljen(meniPrograma.p) }
        MeniVnos { text: koren.t(meniPrograma.vDocku ? "dockOdstrani" : "dockDodaj"); visible: meniPrograma.plank && !!meniPrograma.p && !meniPrograma.p.url && !meniPrograma.p.ponudnikOblaka
                   onTriggered: {
                       var p = meniPrograma.p, dodaj = !meniPrograma.vDocku
                       koren.klic(dodaj ? "dockDodaj" : "dockOdstrani", [p.id], function (r) {
                           if (!r || r.ok === false) koren.obvesti(koren.t("niUspelo"))
                           else koren.obvesti(koren.t(dodaj ? "dockDodano" : "dockOdstranjeno", { ime: p.ime }))
                       }, function () { koren.obvesti(koren.t("niUspelo")) })
                   } }
        MeniVnos { text: koren.t("spletnaOdstrani"); objectName: "vnosOdstraniSpletno"; visible: panel.linux && !!meniPrograma.p && !!meniPrograma.p.url
                   onTriggered: panel.odstraniSpletno(meniPrograma.p) }
        // Kategorija: program prestavi uporabnik (isti zapis kot na delovni povrsini WebKit).
        Meni {
            id: podmeniKategorija
            objectName: "podmeniKategorija"
            title: meniPrograma.p ? koren.t("kategorija", { k: panel.imeSkupine(panel.kategorijaP(meniPrograma.p)) }) : ""
            Instantiator {
                model: panel.linux ? (panel.pril.kategorijeProgramov || []) : []
                delegate: MeniVnos {
                    required property string modelData
                    text: (meniPrograma.p && panel.kategorijaP(meniPrograma.p) === modelData ? "✓  " : "     ") + panel.imeSkupine(modelData)
                    onTriggered: panel.prestaviVKategorijo(meniPrograma.p, modelData)
                }
                onObjectAdded: function (i, o) { podmeniKategorija.insertItem(i, o) }
                onObjectRemoved: function (i, o) { podmeniKategorija.removeItem(o) }
            }
        }
        MeniCrta { visible: meniPrograma.plank && panel.linux }
        MeniVnos { text: koren.t("prilagodiDock"); objectName: "vnosPrilagodiDock"; visible: meniPrograma.plank && panel.linux
                   onTriggered: panel.urediDock() }
    }
    // Igra v oblaku, ki se ni namescena: kaj je, ali bo delovala, in namestitev iz ponudnikovega uradnega vira (samo na klik).
    Meni {
        id: meniOblaka
        objectName: "meniOblaka"
        sirina: koren.px(380)
        property var o: ({})
        readonly property var zdr: o.zdruzljivost || {}
        function razlog() {
            var r = (meniOblaka.zdr.razlogi || [])[0]
            if (!r) return ""
            var k = "oblakRazlog_" + r.koda, b = koren.t(k, r)
            return b === k ? "" : b
        }
        function pokazi(o) { meniOblaka.o = o; meniOblaka.popup() }
        MeniVnos { text: koren.t("oblakOpis", { ponudnik: meniOblaka.o.ponudnik || "" }); enabled: false; prelomi: true }
        MeniVnos { text: meniOblaka.zdr.stanje === "zdruzljivo" ? koren.t("oblakZdruzljivo")
                       : koren.t(meniOblaka.zdr.stanje === "ne" ? "oblakNe" : "oblakPoskusi", { razlog: meniOblaka.razlog() }); enabled: false; prelomi: true }
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
    function fokus() { poljeProgramov.forceActiveFocus() }
    // Odstranitev spletne aplikacije z »Razveljavi« (prejsnji seznam gre nazaj, isti vrstni red).
    function odstraniSpletno(p) {
        var prej = panel.spletne.slice()
        koren.klic("spletnaOdstrani", [p.url], function (r) {
            if (!r || !r.ok) { koren.obvesti(koren.t("niUspelo")); return }
            panel.spletne = r.spletne || []
            koren.obvesti(koren.t("spletnaOdstranjena", { ime: p.ime }), koren.t("razveljavi"), function () {
                koren.klic("shraniSpletne", [prej], function (s) { if (Array.isArray(s)) panel.spletne = s })
            })
        }, function () { koren.obvesti(koren.t("niUspelo")) })
    }
    DodajSpletno {
        id: dodajSpletno
        onDodano: function (r) { panel.spletne = r.spletne || []; panel.skupina = "splet"; koren.obvesti(koren.t("spletnaDodana", { ime: r.ime })) }
    }
    // Zadetek »naprava« v iskanju na namizju: pokaze to napravo v tej plosci.
    function pokaziNapravo(id) { return izbiraNaprave.izberiId(id) }
}
