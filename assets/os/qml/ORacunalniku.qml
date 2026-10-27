// O tem racunalniku v Datotekah (lastnik, 27. 10. 2026: »enostavno omogociti uporabniku kot del namiznega okolja, kjer
// pregleduje datoteke«): diski z zasedenostjo, velikost podmap trenutne mape, strojna in programska oprema.
// Vse prebere core/sistem_podatki.py iz /proc, /sys, /etc in statvfs - brez root, brez omrezja; podatka, ki ga sistem
// ne pove, ne pokazemo (ni izmisljenih vrednosti). Velikost map steje nit mostu z rokom; nov klic ali Preklici jo ustavi.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Item {
    id: plosca
    objectName: "oRacunalniku"
    // Datoteke.qml: odpri mapo (disk ali podmapo) v seznamu datotek.
    signal odpriMapo(string pot)
    property var p: ({})
    property string stanje: ""           // "", "berem", "ok", "napaka"
    property string mapa: ""             // mapa, v kateri stejemo podmape
    property var mape: ({})              // odgovor velikostiMap
    property string stanjeMap: ""        // "", "stejem", "ok", "napaka"
    property int zahteva: 0
    property int zahtevaMap: 0
    readonly property bool stejem: stanjeMap === "stejem"

    function nalozi() {
        var st = ++zahteva
        if (stanje !== "ok") stanje = "berem"
        koren.klic("sistemPodatki", [], function (r) {
            if (st !== zahteva) return
            if (r && typeof r === "object") { plosca.p = r; plosca.stanje = "ok" } else plosca.stanje = "napaka"
        }, function () { if (st === plosca.zahteva) plosca.stanje = "napaka" })
    }
    function prestej(pot) {
        if (pot) mapa = pot
        if (!mapa) mapa = koren.dom || "~"
        var st = ++zahtevaMap
        stanjeMap = "stejem"; mape = ({})
        koren.klic("velikostiMap", [mapa], function (r) {
            if (st !== plosca.zahtevaMap) return
            plosca.mape = r || {}
            plosca.stanjeMap = r && r.ok ? "ok" : "napaka"
        }, function () { if (st === plosca.zahtevaMap) plosca.stanjeMap = "napaka" })
    }
    function preklici() {
        if (!stejem) return
        ++zahtevaMap
        stanjeMap = "ok"; mape = ({ ok: true, mape: [], popolno: false, preklicano: true })
        koren.klic("velikostiMapPreklici", [])
    }
    function fokus() { (gumbStej.visible ? gumbStej : gumbOsvezi).forceActiveFocus() }

    // ---------------------------------------------------------------- besedila vrstic (ciste funkcije, preizkus jih klice)
    function delez(d) { return d && d.velikost > 0 ? Math.max(0, Math.min(1, 1 - (d.prosto || 0) / d.velikost)) : 0 }
    function imeDiska(d) {
        if (d.sistem) return koren.t("racSistemskiDisk")
        return d.oznaka || d.model || (d.pot && d.pot !== "/" ? String(d.pot).split("/").pop() : "") || String(d.naprava || "").replace(/^\/dev\//, "")
    }
    function opisDiska(d) {
        if (!d.priklopljen) return koren.t("racNiPriklopljen", { skupaj: koren.velikost(d.velikost) || "0 B" })
        var deli = [koren.t("prostoNa", { prosto: koren.velikost(d.prosto) || "0 B", skupaj: koren.velikost(d.velikost) || "0 B" }),
                    koren.t("racZasedeno", { odstotek: Math.round(delez(d) * 100) })]
        if (d.datotecni_sistem) deli.push(d.datotecni_sistem)
        if (d.pot && d.pot !== "/") deli.push(koren.kratkaPot(d.pot))
        return deli.join(" · ")
    }
    function casDelovanja(s) {
        s = Math.max(0, Math.floor(s || 0))
        var ure = Math.floor(s / 3600)
        return ure >= 24 ? koren.t("racDni", { d: Math.floor(ure / 24), h: ure % 24 })
            : ure >= 1 ? koren.t("racUr", { h: ure, m: Math.floor(s % 3600 / 60) }) : koren.t("racMin", { m: Math.floor(s / 60) })
    }
    function zasloni() {
        var z = (p.zasloni || []).map(function (x) {
            return [x.prikljucek, x.locljivost, x.vgrajen ? koren.t("racVgrajen") : ""].filter(function (v) { return !!v }).join(" · ")
        })
        if (z.length) return z
        // Brez /sys/class/drm (Flatpak, virtualni stroj): kar ve Qt o zaslonih tega namizja.
        return (Qt.application.screens || []).map(function (s) {
            var r = s.devicePixelRatio || 1
            return (s.name ? s.name + " · " : "") + Math.round(s.width * r) + " × " + Math.round(s.height * r)
        })
    }
    // [[oznaka, vrednost, delez ali -1]] - prazne vrednosti izpustimo (sistem tega ne pove).
    function strojna() {
        var v = [], ram = p.pomnilnik || {}
        if (p.racunalnik) v.push([koren.t("racRacunalnik"), p.racunalnik, -1])
        var niti = p.jeder || 0, jedra = p.fizicnih_jeder || 0
        var jedraOpis = jedra && niti && jedra !== niti ? koren.t("racJedra", { jedra: jedra, niti: niti }) : niti ? koren.t("racNiti", { niti: niti }) : ""
        if (p.procesor || jedraOpis) v.push([koren.t("racProcesor"), [p.procesor, jedraOpis].filter(function (x) { return !!x }).join(" · "), -1])
        if (ram.skupaj) {
            var zasedeno = Math.max(0, ram.skupaj - (ram.na_voljo || 0))
            v.push([koren.t("racPomnilnik"), koren.t("racPomnilnikVr", { zasedeno: koren.velikost(zasedeno) || "0 B", skupaj: koren.velikost(ram.skupaj) })
                    + (ram.izmenjalni ? " · " + koren.t("racIzmenjalni", { velikost: koren.velikost(ram.izmenjalni) }) : ""), zasedeno / ram.skupaj])
        }
        ;(p.graficne || []).forEach(function (g) { v.push([koren.t("racGraficna"), g, -1]) })
        ;(p.naprave || []).forEach(function (n) {
            var vrsta = ({ ssd: koren.t("racVrsta_ssd"), nvme: koren.t("racVrsta_nvme"), hdd: koren.t("racVrsta_hdd"),
                           usb: koren.t("racVrsta_usb"), mmc: koren.t("racVrsta_mmc") })[n.vrsta] || ""
            v.push([koren.t("racShramba"), [n.model || String(n.naprava || "").replace(/^\/dev\//, ""), koren.velikost(n.velikost),
                                             vrsta, n.odstranljiv ? koren.t("racOdstranljiv") : ""]
                    .filter(function (x) { return !!x }).join(" · "), -1])
        })
        ;(p.baterije || []).forEach(function (b) {
            var st = ({ polni: koren.t("racBat_polni"), prazni: koren.t("racBat_prazni"), polna: koren.t("racBat_polna"),
                        ne_polni: koren.t("racBat_ne_polni") })[b.stanje] || ""
            v.push([koren.t("racBaterija"), [b.napolnjenost >= 0 ? b.napolnjenost + " %" : "", st,
                                              b.zdravje >= 0 ? koren.t("racZdravje", { odstotek: b.zdravje }) : "", b.model]
                    .filter(function (x) { return !!x }).join(" · "), b.napolnjenost >= 0 ? b.napolnjenost / 100 : -1])
        })
        zasloni().forEach(function (z) { v.push([koren.t("racZaslon"), z, -1]) })
        return v
    }
    function programska() {
        var v = []
        if (p.safeer) v.push([koren.t("racSafeer"), p.safeer, -1])
        if (p.sistem) v.push([koren.t("racSistem"), p.sistem, -1])
        if (p.osnova) v.push([koren.t("racOsnova"), p.osnova, -1])
        if (p.jedro) v.push([koren.t("racJedro"), p.jedro, -1])
        var nam = [p.namizje, p.seja].filter(function (x) { return !!x }).join(" · ")
        if (nam) v.push([koren.t("racNamizje"), nam, -1])
        if (p.arhitektura) v.push([koren.t("racArhitektura"), p.arhitektura, -1])
        if (p.cas_delovanja_s) v.push([koren.t("racCas"), casDelovanja(p.cas_delovanja_s), -1])
        var k = (p.komponente || []).map(function (x) { return x.ime + " " + x.razlicica })
        if (k.length) v.push([koren.t("racKomponente"), k.join(" · "), -1])
        return v
    }
    function opisMape(m) {
        var vel = koren.velikost(m.velikost) || "0 B"
        return m.popolno ? vel : koren.t("racVsaj", { velikost: vel })
    }

    // Vrstica z napisom, vrednostjo in (neobvezno) trakom zasedenosti.
    component Vrstica: ColumnLayout {
        id: vrstica
        property string oznaka: ""
        property string vrednost: ""
        property real delez: -1
        property bool opozorilo: false
        Layout.fillWidth: true; spacing: 3
        Accessible.role: Accessible.StaticText; Accessible.name: oznaka + ": " + vrednost
        RowLayout {
            Layout.fillWidth: true; spacing: 12
            Text { text: oznaka; color: koren.paleta.medlo; font.pixelSize: koren.px(12); Layout.preferredWidth: koren.px(130); elide: Text.ElideRight
                   Layout.alignment: Qt.AlignTop }
            Text { text: vrednost; color: koren.paleta.besedilo; font.pixelSize: koren.px(12); Layout.fillWidth: true; wrapMode: Text.Wrap }
        }
        Trak { visible: vrstica.delez >= 0; delez: Math.max(0, vrstica.delez); opozorilo: vrstica.opozorilo; Layout.leftMargin: koren.px(142) }
    }
    component Trak: Rectangle {
        property real delez: 0
        property bool opozorilo: false
        Layout.fillWidth: true; implicitHeight: koren.px(6); radius: height / 2; color: koren.prekriv(0.1)
        Rectangle {
            width: parent.width * Math.max(0, Math.min(1, parent.delez)); height: parent.height; radius: parent.radius
            color: parent.opozorilo ? (koren.paleta.opozorilo || koren.paleta.poudarek) : koren.paleta.poudarek
            Behavior on width { enabled: koren.gibanje; NumberAnimation { duration: 220 } }
        }
    }
    component Naslov: Text {
        Layout.fillWidth: true; Layout.topMargin: koren.px(10)
        color: Qt.darker(koren.paleta.medlo, 1.15); font.pixelSize: koren.px(10); font.letterSpacing: 1
        Accessible.role: Accessible.Heading; Accessible.name: text
    }

    Flickable {
        id: drsnik
        anchors.fill: parent
        contentWidth: width; contentHeight: vsebina.implicitHeight + koren.px(16)
        clip: true; boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: drsnik.contentHeight > drsnik.height ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff }
        ColumnLayout {
            id: vsebina
            width: drsnik.width - koren.px(14); spacing: 8
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                Text { Layout.fillWidth: true; text: koren.t("racNaslov"); color: koren.paleta.besedilo; font.pixelSize: koren.px(15); font.bold: true
                       Accessible.role: Accessible.Heading; Accessible.name: text }
                Gumb { id: gumbOsvezi; objectName: "racOsvezi"; besedilo: koren.t("osvezi"); onKlik: plosca.nalozi() }
            }
            Text { Layout.fillWidth: true; wrapMode: Text.Wrap; text: koren.t("racZasebno"); color: koren.paleta.medlo; font.pixelSize: koren.px(11) }
            Text { visible: plosca.stanje === "berem"; text: koren.t("nalagam"); color: koren.paleta.medlo; font.pixelSize: koren.px(12) }
            Text { objectName: "racNapaka"; visible: plosca.stanje === "napaka"; text: koren.t("racNapaka"); color: koren.paleta.opozorilo || koren.paleta.besedilo
                   font.pixelSize: koren.px(12); Layout.fillWidth: true; wrapMode: Text.Wrap }

            // ---------------- diski
            Naslov { text: koren.t("racDiski").toUpperCase(); visible: plosca.stanje === "ok" }
            Text { visible: plosca.stanje === "ok" && !(plosca.p.diski || []).length; text: koren.t("racNiDiskov"); color: koren.paleta.medlo; font.pixelSize: koren.px(12) }
            Repeater {
                objectName: "racDiskiSeznam"
                model: plosca.stanje === "ok" ? (plosca.p.diski || []) : []
                delegate: Rectangle {
                    id: vrsticaDiska
                    required property var modelData
                    readonly property bool odpre: !!modelData.priklopljen && !!modelData.pot
                    Layout.fillWidth: true; implicitHeight: stolpec.implicitHeight + koren.px(14); radius: 10
                    color: md.containsMouse && odpre ? koren.prekriv(0.08) : koren.prekriv(0.04)
                    border.width: activeFocus ? 2 : 0; border.color: koren.paleta.fokus
                    activeFocusOnTab: odpre
                    Accessible.role: Accessible.Button
                    Accessible.name: plosca.imeDiska(modelData) + ", " + plosca.opisDiska(modelData)
                    Accessible.onPressAction: if (odpre) plosca.odpriMapo(modelData.pot)
                    Keys.onReturnPressed: if (odpre) plosca.odpriMapo(modelData.pot)
                    Keys.onSpacePressed: if (odpre) plosca.odpriMapo(modelData.pot)
                    ColumnLayout {
                        id: stolpec
                        anchors.left: parent.left; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                        anchors.leftMargin: 12; anchors.rightMargin: 12; spacing: 4
                        RowLayout {
                            Layout.fillWidth: true; spacing: 8
                            Text { text: plosca.imeDiska(vrsticaDiska.modelData); color: koren.paleta.besedilo; font.pixelSize: koren.px(13); font.bold: true
                                   elide: Text.ElideRight; Layout.fillWidth: true }
                            Text { visible: !!vrsticaDiska.modelData.malo_prostora; text: koren.t("racMalo")
                                   color: koren.paleta.opozorilo || koren.paleta.poudarek; font.pixelSize: koren.px(11) }
                        }
                        Text { text: plosca.opisDiska(vrsticaDiska.modelData); color: koren.paleta.medlo; font.pixelSize: koren.px(11)
                               Layout.fillWidth: true; wrapMode: Text.Wrap }
                        Trak { visible: !!vrsticaDiska.modelData.priklopljen; delez: plosca.delez(vrsticaDiska.modelData)
                               opozorilo: !!vrsticaDiska.modelData.malo_prostora }
                    }
                    MouseArea { id: md; anchors.fill: parent; hoverEnabled: true; enabled: vrsticaDiska.odpre; cursorShape: Qt.PointingHandCursor
                                onClicked: plosca.odpriMapo(vrsticaDiska.modelData.pot) }
                }
            }

            // ---------------- velikost map (podmape mape, iz katere je uporabnik prisel)
            Naslov { text: koren.t("racMape").toUpperCase() }
            RowLayout {
                Layout.fillWidth: true; spacing: 8
                Text { Layout.fillWidth: true; elide: Text.ElideLeft; color: koren.paleta.besedilo; font.pixelSize: koren.px(12)
                       text: koren.t("racMapeV", { mapa: koren.kratkaPot(plosca.mapa || koren.dom || "~") }) }
                Gumb { id: gumbStej; objectName: "racPrestej"; visible: !plosca.stejem; besedilo: koren.t("racPrestej"); onKlik: plosca.prestej("") }
                Gumb { objectName: "racPreklici"; visible: plosca.stejem; besedilo: koren.t("preklici"); onKlik: plosca.preklici() }
            }
            Text { objectName: "racStanjeMap"; Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: koren.px(11)
                   color: plosca.stanjeMap === "napaka" ? (koren.paleta.opozorilo || koren.paleta.besedilo) : koren.paleta.medlo
                   visible: text !== ""
                   text: plosca.stejem ? koren.t("racStejem")
                       : plosca.stanjeMap === "napaka" ? koren.t("racMapaNapaka")
                       : plosca.stanjeMap !== "ok" ? ""
                       : plosca.mape.preklicano ? koren.t("racPreklicano")
                       : !(plosca.mape.mape || []).length ? koren.t("racNiMap")
                       : !plosca.mape.popolno ? koren.t("racDelno") : "" }
            Repeater {
                objectName: "racMapeSeznam"
                model: plosca.stanjeMap === "ok" ? (plosca.mape.mape || []) : []
                delegate: Rectangle {
                    id: vrsticaMape
                    required property var modelData
                    required property int index
                    readonly property real najvec: Math.max(1, ((plosca.mape.mape || [])[0] || {}).velikost || 1)
                    Layout.fillWidth: true; implicitHeight: stolpecMape.implicitHeight + koren.px(10); radius: 8
                    color: mm.containsMouse ? koren.prekriv(0.08) : "transparent"
                    border.width: activeFocus ? 2 : 0; border.color: koren.paleta.fokus
                    activeFocusOnTab: true
                    Accessible.role: Accessible.Button; Accessible.name: modelData.ime + ", " + plosca.opisMape(modelData)
                    Accessible.onPressAction: plosca.odpriMapo(modelData.pot)
                    Keys.onReturnPressed: plosca.odpriMapo(modelData.pot)
                    Keys.onSpacePressed: plosca.odpriMapo(modelData.pot)
                    ColumnLayout {
                        id: stolpecMape
                        anchors.left: parent.left; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                        anchors.leftMargin: 10; anchors.rightMargin: 10; spacing: 3
                        RowLayout {
                            Layout.fillWidth: true
                            Text { text: vrsticaMape.modelData.ime; color: koren.paleta.besedilo; font.pixelSize: koren.px(12); elide: Text.ElideMiddle; Layout.fillWidth: true }
                            Text { text: plosca.opisMape(vrsticaMape.modelData); color: koren.paleta.medlo; font.pixelSize: koren.px(12) }
                        }
                        Trak { delez: vrsticaMape.modelData.velikost / vrsticaMape.najvec }
                    }
                    MouseArea { id: mm; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                onClicked: plosca.odpriMapo(vrsticaMape.modelData.pot) }
                }
            }
            Text { visible: plosca.stanjeMap === "ok" && (plosca.mape.datoteke_tu || 0) > 0; color: koren.paleta.medlo; font.pixelSize: koren.px(11)
                   text: koren.t("racDatotekTu", { velikost: koren.velikost(plosca.mape.datoteke_tu) }) }

            // ---------------- strojna in programska oprema
            Naslov { text: koren.t("racStrojna").toUpperCase(); visible: plosca.stanje === "ok" }
            Repeater {
                objectName: "racStrojnaSeznam"
                model: plosca.stanje === "ok" ? plosca.strojna() : []
                delegate: Vrstica { required property var modelData; oznaka: modelData[0]; vrednost: modelData[1]; delez: modelData[2] }
            }
            Naslov { text: koren.t("racProgramska").toUpperCase(); visible: plosca.stanje === "ok" }
            Repeater {
                objectName: "racProgramskaSeznam"
                model: plosca.stanje === "ok" ? plosca.programska() : []
                delegate: Vrstica { required property var modelData; oznaka: modelData[0]; vrednost: modelData[1]; delez: modelData[2] }
            }
        }
    }
}
