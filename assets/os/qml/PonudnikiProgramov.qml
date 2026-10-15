// »Namesti programe …« (core/os_ponudniki_programov.py, core/os_github_programi.py): uporabnik izbere, od kod namesca
// programe. Trije zavihki kot na delovni povrsini WebKit (delovna.js ponudnikiProgramov): Ponudniki (po abecedi, brez
// priporocila), Viri (Flatpak repozitoriji, PPA - doda svoje) in GitHub (javni repozitoriji in datoteke izdaj, shrani v
// mapo, ki jo izbere sam). Nic se ne namesti brez potrditve, v kateri uporabnik vidi, kaj natanko, od kod, koliko in
// kako se bo posodabljalo (lastnik, 11. 10. 2026).
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Okno {
    id: okno
    objectName: "ponudnikiProgramov"
    width: Math.min(640, parent ? parent.width - 24 : 640)
    height: Math.min(680, parent ? parent.height - 24 : 680)
    property string zavihek: "ponudniki"
    property string mapa: ""             // kam GitHub shrani (privzeto Prenosi)
    signal namesceno()

    function imaKljuc(k) { return koren.t(k) !== k }
    function kljuc(id) { return String(id).replace(/-/g, "_") }
    function stevilo(v) { return koren.jezik === "en" ? String(v || 0) : String(v || 0).replace(".", ",") }
    function odpri(mapaPrenosov) {
        if (!mapa) mapa = mapaPrenosov || koren.dom || "~"
        open(); izberiZavihek("ponudniki")
    }
    function izberiZavihek(k) {
        zavihek = k
        if (k === "ponudniki") ponudniki.osvezi()
        else if (k === "viri") viri.osvezi()
        Qt.callLater(function () { (k === "github" ? ghPolje : k === "viri" ? virPolje : gumbPonudniki).forceActiveFocus() })
    }

    // Vrstica z naslovom, opisom in gumbom (vrsticaZ v delovna.js), pod njo po potrebi okvir za potrditev.
    component Vrstica: ColumnLayout {
        id: vr
        property string naslov: ""
        property string opis: ""
        property string gumb: ""
        property bool gumbOmogocen: true
        // Potrditev: {seznam: [nizi], vrstice: [nizi], potrdi: besedilo} ali null
        property var potrditev: null
        signal klik()
        signal potrjeno()
        signal preklicano()
        Layout.fillWidth: true; spacing: 6
        RowLayout {
            Layout.fillWidth: true; spacing: 10
            ColumnLayout {
                Layout.fillWidth: true; spacing: 2
                Text { text: vr.naslov; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere; color: koren.paleta.besedilo; font.pixelSize: koren.px(13); font.bold: true }
                Text { visible: vr.opis !== ""; text: vr.opis; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: koren.paleta.medlo; font.pixelSize: koren.px(12) }
            }
            Gumb { visible: vr.gumb !== ""; besedilo: vr.gumb; enabled: vr.gumbOmogocen; onKlik: vr.klik() }
        }
        Rectangle {
            visible: !!vr.potrditev
            Layout.fillWidth: true; implicitHeight: potrdiStolpec.implicitHeight + 20; radius: 8
            color: "transparent"; border.color: koren.crta(0.3)
            ColumnLayout {
                id: potrdiStolpec; anchors.fill: parent; anchors.margins: 10; spacing: 4
                Text { visible: !!vr.potrditev && (vr.potrditev.seznam || []).length > 0; text: koren.t("ppKajSe"); color: koren.paleta.besedilo; font.pixelSize: koren.px(12) }
                Repeater {
                    model: vr.potrditev ? (vr.potrditev.seznam || []) : []
                    delegate: Text { required property var modelData; text: "• " + modelData; Layout.fillWidth: true; wrapMode: Text.WordWrap
                                     color: koren.paleta.besedilo; font.pixelSize: koren.px(12); leftPadding: 8 }
                }
                Repeater {
                    model: vr.potrditev ? (vr.potrditev.vrstice || []) : []
                    delegate: Text { required property var modelData; text: modelData; Layout.fillWidth: true; wrapMode: Text.WordWrap
                                     color: koren.paleta.medlo; font.pixelSize: koren.px(12) }
                }
                RowLayout {
                    Layout.alignment: Qt.AlignRight; spacing: 8
                    Gumb { besedilo: koren.t("ppPreklici"); onKlik: vr.preklicano() }
                    Gumb { id: gumbPotrdi; besedilo: vr.potrditev ? vr.potrditev.potrdi : ""; poudarjen: true; onKlik: vr.potrjeno() }
                }
            }
            onVisibleChanged: if (visible) gumbPotrdi.forceActiveFocus()
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: koren.crta(0.08) }
    }
    // Cipi za filter (zvrst repozitorija, sistem datotek izdaje): [[kljuc, besedilo, stevilo]].
    component Cipi: Flow {
        id: cp
        property var moznosti: []
        property string izbrano: ""
        signal izbran(string k)
        Layout.fillWidth: true; spacing: 6
        Repeater {
            model: cp.moznosti
            delegate: Gumb {
                required property var modelData
                besedilo: modelData[1] + (modelData[2] !== undefined ? " · " + modelData[2] : "")
                poudarjen: modelData[0] === cp.izbrano
                Accessible.role: Accessible.RadioButton; Accessible.checked: modelData[0] === cp.izbrano
                onKlik: cp.izbran(modelData[0])
            }
        }
    }

    contentItem: ColumnLayout {
        spacing: 10
        Text { text: koren.t("ppNaslov"); Layout.fillWidth: true; wrapMode: Text.WordWrap; color: koren.paleta.besedilo; font.pixelSize: koren.px(16); font.bold: true }
        Row {
            spacing: 6
            Accessible.role: Accessible.PageTabList
            Gumb { id: gumbPonudniki; objectName: "zavihekPonudniki"; besedilo: koren.t("ppZavihekPonudniki"); poudarjen: okno.zavihek === "ponudniki"
                   Accessible.role: Accessible.PageTab; onKlik: okno.izberiZavihek("ponudniki") }
            Gumb { objectName: "zavihekViri"; besedilo: koren.t("ppZavihekViri"); poudarjen: okno.zavihek === "viri"
                   Accessible.role: Accessible.PageTab; onKlik: okno.izberiZavihek("viri") }
            Gumb { objectName: "zavihekGithub"; besedilo: koren.t("ppZavihekGithub"); poudarjen: okno.zavihek === "github"
                   Accessible.role: Accessible.PageTab; onKlik: okno.izberiZavihek("github") }
        }
        Flickable {
            id: drsnik
            Layout.fillWidth: true; Layout.fillHeight: true; clip: true
            contentWidth: width; contentHeight: vsebina.implicitHeight; boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
            ColumnLayout {
                id: vsebina; width: drsnik.width - 12; spacing: 8

                // ------------------------------------------------ Ponudniki
                ColumnLayout {
                    id: ponudniki
                    visible: okno.zavihek === "ponudniki"; Layout.fillWidth: true; spacing: 6
                    property var vsi: []
                    property bool nalozeno: false
                    property var dela: ({})          // id -> "preverjam" | "namescam"
                    property var potrditve: ({})     // id -> potrditev
                    function ime(p) { return okno.imaKljuc("ppIme_" + okno.kljuc(p.id)) ? koren.t("ppIme_" + okno.kljuc(p.id)) : p.ime }
                    function nastavi(obj, id, v) { var o = {}; for (var k in obj) o[k] = obj[k]; if (v === undefined) delete o[id]; else o[id] = v; return o }
                    function osvezi() {
                        koren.klic("ponudnikiProgramov", [], function (s) {
                            ponudniki.vsi = (s || []).slice().sort(function (a, b) { return ponudniki.ime(a).localeCompare(ponudniki.ime(b)) })
                            ponudniki.nalozeno = true
                        }, function () { ponudniki.vsi = []; ponudniki.nalozeno = true })
                    }
                    function klik(p) {
                        if (p.namescen) { koren.klic("ponudnikOdpri", [p.id]); okno.close(); return }
                        dela = nastavi(dela, p.id, "preverjam")
                        koren.klic("ponudnikPodrobnosti", [p.id], function (d) {
                            ponudniki.dela = ponudniki.nastavi(ponudniki.dela, p.id)
                            if (!d || !d.ok) { koren.obvesti(koren.t("ppNiPodatkov")); ponudniki.osvezi(); return }
                            var seznam, vrstice
                            if (d.vrsta === "snap") {
                                seznam = (d.koraki || []).map(function (k) { return koren.t("ppKorak_" + okno.kljuc(k)) })
                                vrstice = [koren.t("ppVirSnap"), koren.t("ppPosSnap")]
                            } else {
                                seznam = (d.paketi || []).map(function (x) {
                                    return x.ime + (x.razlicica ? " " + x.razlicica : "") + (x.okolje ? " – " + koren.t("ppOkolje") : "")
                                         + (x.prenos_mb ? " (" + okno.stevilo(x.prenos_mb) + " MB)" : "")
                                })
                                vrstice = [d.vrsta === "flatpak" ? koren.t("ppVirFlatpak", { mb: okno.stevilo(d.prenos_mb) })
                                                                 : koren.t("ppVirApt", { vir: d.vir, mb: okno.stevilo(d.prenos_mb) }),
                                           koren.t(d.samodejno ? "ppPosSamo" : "ppPosRocno")]
                            }
                            ponudniki.potrditve = ponudniki.nastavi(ponudniki.potrditve, p.id,
                                { seznam: seznam, vrstice: vrstice, potrdi: d.vrsta === "snap" ? koren.t("ppOmogoci") : koren.t("ppPotrdi") })
                        }, function () { ponudniki.dela = ponudniki.nastavi(ponudniki.dela, p.id); koren.obvesti(koren.t("ppNiPodatkov")) })
                    }
                    function namesti(p) {
                        potrditve = nastavi(potrditve, p.id)
                        dela = nastavi(dela, p.id, "namescam")
                        koren.klic("ponudnikNamesti", [p.id], function (r) {
                            ponudniki.dela = ponudniki.nastavi(ponudniki.dela, p.id)
                            if (r && r.ok) { koren.obvesti(koren.t("ppKoncano", { ime: ponudniki.ime(p) })); okno.namesceno() }
                            else koren.obvesti(r && r.napaka === "preklicano" ? koren.t("ppPreklicano") : koren.t("ppNapaka", { ime: ponudniki.ime(p) }))
                            ponudniki.osvezi()
                        }, function () { ponudniki.dela = ponudniki.nastavi(ponudniki.dela, p.id); koren.obvesti(koren.t("ppNapaka", { ime: ponudniki.ime(p) })) })
                    }
                    Text { text: koren.t("ppUvod"); Layout.fillWidth: true; wrapMode: Text.WordWrap; color: koren.paleta.medlo; font.pixelSize: koren.px(12) }
                    Text { visible: ponudniki.nalozeno && !ponudniki.vsi.length; text: koren.t("ppPrazno"); color: koren.paleta.besedilo; font.pixelSize: koren.px(13) }
                    Repeater {
                        model: ponudniki.vsi
                        delegate: Vrstica {
                            required property var modelData
                            naslov: ponudniki.ime(modelData) + (modelData.namescen ? " · " + koren.t("ppNamesceno") : "")
                            opis: koren.t("ppOpis_" + okno.kljuc(modelData.id)) + (modelData.namestljiv && modelData.vrsta === "apt" ? " (" + koren.t("ppGeslo") + ")" : "")
                            gumb: ponudniki.dela[modelData.id] === "preverjam" ? koren.t("ppPreverjam") : ponudniki.dela[modelData.id] === "namescam" ? koren.t("ppNamescam")
                                : modelData.namescen ? koren.t("ppOdpri") : modelData.vrsta === "snap" ? koren.t("ppOmogoci") : koren.t("ppNamesti")
                            gumbOmogocen: !ponudniki.dela[modelData.id] && !ponudniki.potrditve[modelData.id] && (modelData.namescen || modelData.namestljiv)
                            potrditev: ponudniki.potrditve[modelData.id] || null
                            onKlik: ponudniki.klik(modelData)
                            onPotrjeno: ponudniki.namesti(modelData)
                            onPreklicano: ponudniki.potrditve = ponudniki.nastavi(ponudniki.potrditve, modelData.id)
                        }
                    }
                }

                // ------------------------------------------------ Viri
                ColumnLayout {
                    id: viri
                    visible: okno.zavihek === "viri"; Layout.fillWidth: true; spacing: 6
                    property var vrstice: []         // [[naslov, opis]]
                    property var potrditev: null
                    function osvezi() {
                        koren.klic("viriProgramov", [], function (v) {
                            v = v || {}
                            var r = []
                            ;(v.flatpak || []).forEach(function (x) { r.push([x.ime + " · Flatpak", x.url + " · " + koren.t(x.za === "uporabnik" ? "ppZaUporabnika" : "ppZaSistem")]) })
                            ;(v.ppa || []).forEach(function (x) { r.push([x + " · PPA", koren.t("ppZaSistem")]) })
                            ;(v.apt || []).forEach(function (x) { r.push([String(x.url).replace(/^https?:\/\//, "") + " · " + x.izdaja, koren.t("ppAptVir")]) })
                            viri.vrstice = r
                        }, function () { viri.vrstice = [] })
                    }
                    function preveri() {
                        var niz = virPolje.text.trim()
                        koren.klic("virPodrobnosti", [niz], function (d) {
                            if (!d || !d.ok) { koren.obvesti(koren.t("ppViriNeveljaven")); return }
                            viri.potrditev = { niz: niz, potrdi: koren.t("ppViriDodaj"), vrstice: [d.vrsta === "ppa" ? koren.t("ppViriPpa", { vir: d.vir })
                                : koren.t("ppViriFlatpak", { vir: d.vir, ime: d.ime }), koren.t("ppViriOpozorilo")] }
                        })
                    }
                    function dodaj() {
                        var niz = potrditev.niz
                        potrditev = null
                        koren.klic("dodajVir", [niz], function (r) {
                            if (r && r.ok) { koren.obvesti(koren.t("ppViriDodan")); virPolje.text = ""; viri.osvezi() }
                            else koren.obvesti(r && r.napaka === "preklicano" ? koren.t("ppPreklicano") : koren.t("ppViriNapaka"))
                        }, function () { koren.obvesti(koren.t("ppViriNapaka")) })
                    }
                    Text { text: koren.t("ppViriUvod"); Layout.fillWidth: true; wrapMode: Text.WordWrap; color: koren.paleta.medlo; font.pixelSize: koren.px(12) }
                    Repeater {
                        model: viri.vrstice
                        delegate: Vrstica { required property var modelData; naslov: modelData[0]; opis: modelData[1] }
                    }
                    Text { visible: !viri.vrstice.length; text: koren.t("ppViriPrazno"); color: koren.paleta.besedilo; font.pixelSize: koren.px(13) }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 8
                        TextField {
                            id: virPolje
                            Layout.fillWidth: true; placeholderText: koren.t("ppViriPh"); placeholderTextColor: koren.paleta.medlo
                            color: koren.paleta.besedilo; font.pixelSize: koren.px(13); Accessible.name: koren.t("ppViriPh")
                            background: Rectangle { radius: 8; color: koren.prekriv(0.08); border.color: virPolje.activeFocus ? koren.paleta.fokus : koren.crta(0.2) }
                            Keys.onReturnPressed: viri.preveri()
                        }
                        Gumb { besedilo: koren.t("ppViriDodaj"); poudarjen: true; enabled: !viri.potrditev && virPolje.text.trim() !== ""; onKlik: viri.preveri() }
                    }
                    Vrstica {
                        visible: !!viri.potrditev; potrditev: viri.potrditev
                        onPotrjeno: viri.dodaj(); onPreklicano: viri.potrditev = null
                    }
                }

                // ------------------------------------------------ GitHub
                ColumnLayout {
                    id: github
                    visible: okno.zavihek === "github"; Layout.fillWidth: true; spacing: 6
                    property string stanje: ""        // "", "iscem", "napaka:<kljuc>", "nic"
                    property var repozitoriji: []
                    property string zvrst: "vse"
                    property string repo: ""          // odprte izdaje repozitorija
                    property var izdaje: []
                    property string sistem: ""
                    property var shranjevanje: ({})   // url -> {besedilo, pot, dela}
                    function nastaviShr(url, v) { var o = {}; for (var k in shranjevanje) o[k] = shranjevanje[k]; o[url] = v; shranjevanje = o }
                    function napaka(r) { stanje = "napaka:" + (r && r.napaka === "omejitev" ? "ppGhOmejitev" : "ppGhNapaka") }
                    function isci() {
                        var niz = ghPolje.text.trim(); if (!niz) return
                        zvrst = "vse"; sistem = ""; repo = ""; stanje = "iscem"; repozitoriji = []
                        koren.klic("githubIsci", [niz], function (r) {
                            if (!r || !r.ok) { github.napaka(r); return }
                            github.repozitoriji = r.repozitoriji || []
                            github.stanje = github.repozitoriji.length ? "" : "nic"
                        }, function () { github.napaka(null) })
                    }
                    function odpriIzdaje(repo) {
                        github.repo = repo; stanje = "iscem"; izdaje = []
                        koren.klic("githubIzdaje", [repo], function (r) {
                            if (!r || !r.ok) { github.napaka(r); return }
                            github.izdaje = r.izdaje || []; github.stanje = ""
                            var vse = [].concat.apply([], github.izdaje.map(function (iz) { return iz.datoteke || [] }))
                            if (!github.sistem) github.sistem = vse.some(function (d) { return d.nas }) ? "nas" : "vse"
                        }, function () { github.napaka(null) })
                    }
                    function ustreza(d, k) { return k === "vse" || (k === "nas" ? d.nas : d.sistem === k) }
                    function moznostiZvrsti() {
                        var st = {}
                        repozitoriji.forEach(function (x) { st[x.zvrst] = (st[x.zvrst] || 0) + 1 })
                        return [["vse", koren.t("ppGhVse"), repozitoriji.length]].concat(Object.keys(st).sort(function (a, b) { return st[b] - st[a] })
                            .map(function (k) { return [k, koren.t("ppZvrst_" + k), st[k]] }))
                    }
                    function moznostiSistema() {
                        var vse = [].concat.apply([], izdaje.map(function (iz) { return iz.datoteke || [] }))
                        return [["nas", koren.t("ppGhZaTaKratko")], ["linux", "Linux"], ["windows", "Windows"], ["macos", "macOS"],
                                ["android", "Android"], ["ios", "iOS"], ["drugo", koren.t("ppGhDrugo")], ["vse", koren.t("ppGhVse")]]
                            .map(function (m) { return [m[0], m[1], vse.filter(function (d) { return github.ustreza(d, m[0]) }).length] })
                            .filter(function (m) { return m[2] > 0 || m[0] === "vse" })
                    }
                    // Vrstice izdaj: glava izdaje in njene datoteke za izbrani sistem.
                    function vrsticeIzdaj() {
                        var v = []
                        izdaje.forEach(function (iz) {
                            v.push({ glava: iz.ime + " · " + iz.datum + (iz.predizdaja ? " · " + koren.t("ppGhPredizdaja") : "") })
                            var d = (iz.datoteke || []).filter(function (x) { return github.ustreza(x, github.sistem) })
                            if (!d.length) v.push({ prazno: true })
                            d.forEach(function (x) { v.push({ d: x }) })
                        })
                        return v
                    }
                    function shrani(d) {
                        var s = shranjevanje[d.url]
                        if (s && s.pot) { koren.klic("pokaziVMapi", [s.pot]); return }
                        nastaviShr(d.url, { besedilo: koren.t("ppGhShranjujem"), dela: true })
                        koren.klic("githubShrani", [d.url, d.ime, okno.mapa, d.sha256 || ""], function (z) {
                            if (!z || !z.ok) { github.nastaviShr(d.url, null); koren.obvesti(koren.t(z && z.koda === "mapa" ? "ppGhNiMape" : "ppGhNapaka")); return }
                            ghSpremljaj.dodaj(z.id, d.url)
                        }, function () { github.nastaviShr(d.url, null) })
                    }
                    Text { text: koren.t("ppGhUvod"); Layout.fillWidth: true; wrapMode: Text.WordWrap; color: koren.paleta.medlo; font.pixelSize: koren.px(12) }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 8
                        Text { Layout.fillWidth: true; text: koren.t("ppGhMapa", { pot: koren.kratkaPot(okno.mapa) }); wrapMode: Text.WrapAnywhere
                               color: koren.paleta.besedilo; font.pixelSize: koren.px(12) }
                        Gumb { besedilo: koren.t("ppGhSpremeni")
                               onKlik: koren.klic("izberiMapo", [okno.mapa, koren.t("ppGhIzberiMapo"), koren.t("preklici"), koren.t("izberi")],
                                                  function (p) { if (p) okno.mapa = p }) }
                    }
                    RowLayout {
                        Layout.fillWidth: true; spacing: 8
                        TextField {
                            id: ghPolje
                            objectName: "githubPolje"
                            Layout.fillWidth: true; placeholderText: koren.t("ppGhIsciPh"); placeholderTextColor: koren.paleta.medlo
                            color: koren.paleta.besedilo; font.pixelSize: koren.px(13); Accessible.name: koren.t("ppGhIsciPh")
                            background: Rectangle { radius: 8; color: koren.prekriv(0.08); border.color: ghPolje.activeFocus ? koren.paleta.fokus : koren.crta(0.2) }
                            Keys.onReturnPressed: github.isci()
                            Keys.onEnterPressed: github.isci()
                        }
                        Gumb { besedilo: koren.t("ppGhIsci"); poudarjen: true; onKlik: github.isci() }
                    }
                    Text { visible: github.stanje !== ""; color: koren.paleta.besedilo; font.pixelSize: koren.px(13); Layout.fillWidth: true; wrapMode: Text.WordWrap
                           text: github.stanje === "iscem" ? koren.t("ppGhIscem") : github.stanje === "nic" ? koren.t("ppGhNic")
                               : github.stanje.indexOf("napaka:") === 0 ? koren.t(github.stanje.slice(7)) : "" }
                    // Rezultati iskanja
                    Cipi { visible: !github.repo && github.repozitoriji.length > 0; moznosti: github.moznostiZvrsti(); izbrano: github.zvrst
                           onIzbran: function (k) { github.zvrst = k } }
                    Repeater {
                        model: github.repo ? [] : github.repozitoriji.filter(function (x) { return github.zvrst === "vse" || x.zvrst === github.zvrst })
                        delegate: Vrstica {
                            required property var modelData
                            naslov: modelData.repo
                            opis: [modelData.opis, koren.t("ppZvrst_" + modelData.zvrst), "★ " + modelData.zvezdice,
                                   modelData.licenca === "NOASSERTION" ? koren.t("ppGhDrugaLicenca") : modelData.licenca, modelData.posodobljeno,
                                   modelData.arhiviran ? koren.t("ppGhArhiviran") : ""].filter(function (x) { return !!x }).join(" · ")
                            gumb: koren.t("ppGhIzdaje")
                            onKlik: github.odpriIzdaje(modelData.repo)
                        }
                    }
                    // Izdaje izbranega repozitorija
                    Gumb { visible: github.repo !== ""; besedilo: "← " + koren.t("ppGhNazaj"); onKlik: { github.repo = ""; github.izdaje = []; github.stanje = "" } }
                    Text { visible: github.repo !== ""; text: github.repo; color: koren.paleta.besedilo; font.pixelSize: koren.px(14); font.bold: true }
                    Text { visible: github.repo !== "" && github.stanje === "" && !github.izdaje.length; text: koren.t("ppGhBrezIzdaj")
                           color: koren.paleta.besedilo; font.pixelSize: koren.px(13) }
                    Cipi { visible: github.repo !== "" && github.izdaje.length > 0; moznosti: github.moznostiSistema(); izbrano: github.sistem
                           onIzbran: function (k) { github.sistem = k } }
                    Text { visible: github.repo !== "" && github.izdaje.length > 0 && !github.moznostiSistema().some(function (m) { return m[0] === "nas" })
                           text: koren.t("ppGhNiZaNas"); color: koren.paleta.medlo; font.pixelSize: koren.px(12); Layout.fillWidth: true; wrapMode: Text.WordWrap }
                    Repeater {
                        model: github.repo ? github.vrsticeIzdaj() : []
                        // Brez »required«: modelData je lastnost konteksta in jo vidijo tudi komponente v Loaderju.
                        delegate: Loader {
                            Layout.fillWidth: true
                            sourceComponent: modelData.glava ? glavaIzdaje : modelData.prazno ? brezDatotek : datotekaIzdaje
                            Component { id: glavaIzdaje; Text { text: modelData.glava; topPadding: 8; color: koren.paleta.medlo; font.pixelSize: koren.px(12); font.bold: true } }
                            Component { id: brezDatotek; Text { text: koren.t("ppGhBrezDatotek"); color: koren.paleta.besedilo; font.pixelSize: koren.px(12) } }
                            Component {
                                id: datotekaIzdaje
                                Vrstica {
                                    readonly property var d: modelData.d
                                    readonly property var s: github.shranjevanje[d.url] || null
                                    naslov: d.ime
                                    opis: okno.stevilo(d.mb) + " MB · " + koren.t("ppGhPrenosov", { n: d.prenosi })
                                          + (d.nas ? " · " + koren.t("ppGhZaTa") : d.linux ? " · Linux" : "") + (d.sha256 ? " · SHA-256" : "")
                                    gumb: s ? (s.pot ? koren.t("pokaziVMapi") : s.besedilo) : koren.t("ppGhShrani")
                                    gumbOmogocen: !s || !s.dela
                                    onKlik: github.shrani(d)
                                }
                            }
                        }
                    }
                    Timer {
                        id: ghSpremljaj
                        property var dela: ({})      // id -> url
                        interval: 500; repeat: true
                        function dodaj(id, url) { var d = {}; for (var k in dela) d[k] = dela[k]; d[id] = url; dela = d; start() }
                        function koncaj(id) { var d = {}; for (var k in dela) if (k !== id) d[k] = dela[k]; dela = d; if (!Object.keys(d).length) stop() }
                        onTriggered: Object.keys(dela).forEach(function (id) {
                            var url = ghSpremljaj.dela[id]
                            koren.klic("githubStanje", [id], function (s) {
                                if (!(id in ghSpremljaj.dela)) return
                                if (!s || !s.ok || s.stanje === "napaka") {
                                    ghSpremljaj.koncaj(id); github.nastaviShr(url, null)
                                    koren.obvesti(koren.t(s && s.koda === "kontrolna" ? "ppGhKontrolna" : "ppGhNapaka")); return
                                }
                                if (s.stanje === "koncano") {
                                    ghSpremljaj.koncaj(id); github.nastaviShr(url, { pot: s.pot, dela: false })
                                    koren.obvesti(koren.t(s.preverjeno ? "ppGhShranjenoPreverjeno" : "ppGhShranjeno", { ime: s.ime })); return
                                }
                                github.nastaviShr(url, { dela: true, besedilo: s.skupaj ? Math.round(100 * s.prebrano / s.skupaj) + " %"
                                                                                         : okno.stevilo(Math.round(s.prebrano / 104857.6) / 10) + " MB" })
                            })
                        })
                    }
                }
            }
        }
        Gumb { Layout.alignment: Qt.AlignRight; besedilo: koren.t("shrZapri"); onKlik: okno.close() }
    }
}
