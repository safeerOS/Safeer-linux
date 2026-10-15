// Lastnosti datoteke ali mape (lastnostiDatoteke, core/os_datoteke.lastnosti) - iste vrstice kot na delovni povrsini
// WebKit: vrsta, velikost, vsebuje, kje, spremenjeno, pravice, povezava. Enter ali Escape zapre.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Okno {
    id: okno
    objectName: "lastnosti"
    width: Math.min(440, parent ? parent.width - 24 : 440)
    property var l: ({})
    readonly property var vrsteZnane: ["mapa", "slika", "video", "zvok", "dokument", "arhiv", "splet", "program"]
    function pokazi(pot) {
        koren.klic("lastnostiDatoteke", [pot], function (r) {
            if (!r || !r.ok) { koren.obvesti(koren.t("niUspelo")); return }
            okno.l = r; okno.open(); zapri.forceActiveFocus()
        }, function () { koren.obvesti(koren.t("niUspelo")) })
    }
    function vrstice() {
        var l = okno.l, v = []
        if (!l || !l.ok) return v
        var vrsta = l.mapa ? "mapa" : (vrsteZnane.indexOf(l.vrsta) >= 0 ? l.vrsta : "drugo")
        v.push([koren.t("lVrsta"), koren.t("en_" + vrsta) + (l.mime && !l.mapa ? " · " + l.mime : "")])
        v.push([koren.t("lVelikost"), koren.velikost(l.velikost) || "0 kB"])
        if (l.mapa) v.push([koren.t("lVsebuje"), koren.t("lElementov", { n: l.vsebuje || 0 })])
        v.push([koren.t("lKje"), koren.kratkaPot(String(l.pot || "").replace(/\/[^/]*$/, "") || "/")])
        if (l.spremenjeno) {
            var lok = ({ sl: "sl_SI", en: "en_GB", de: "de_DE", es: "es_ES", fr: "fr_FR", it: "it_IT" })[koren.jezik] || "en_GB"
            v.push([koren.t("lSpremenjeno"), new Date(l.spremenjeno * 1000).toLocaleString(Qt.locale(lok), Locale.ShortFormat)])
        }
        if (l.pravice) v.push([koren.t("lPravice"), l.pravice + (l.lastnik ? " · " + l.lastnik : "")])
        if (l.povezava !== undefined && l.povezava !== null) v.push([koren.t("lPovezava"), l.povezava])
        return v
    }
    ColumnLayout {
        anchors.fill: parent; spacing: 8
        Text { text: koren.t("lastnosti"); color: koren.paleta.besedilo; font.pixelSize: koren.px(15); font.bold: true }
        Text { objectName: "lastnostiIme"; text: okno.l.ime || ""; Layout.fillWidth: true; wrapMode: Text.WrapAnywhere
               color: koren.paleta.besedilo; font.pixelSize: koren.px(13) }
        GridLayout {
            Layout.fillWidth: true; columns: 2; columnSpacing: 14; rowSpacing: 6
            Repeater {
                // [oznaka, vrednost, oznaka, vrednost …] - dva stolpca
                model: okno.visible ? [].concat.apply([], okno.vrstice()) : []
                delegate: Text {
                    required property var modelData
                    required property int index
                    Layout.row: Math.floor(index / 2); Layout.column: index % 2
                    Layout.fillWidth: index % 2 === 1; Layout.alignment: Qt.AlignTop
                    text: modelData; wrapMode: Text.WrapAnywhere
                    color: index % 2 ? koren.paleta.besedilo : koren.paleta.medlo; font.pixelSize: koren.px(12)
                }
            }
        }
        Gumb {
            id: zapri
            Layout.alignment: Qt.AlignRight; besedilo: koren.t("zapri")
            onKlik: okno.close()
        }
    }
}
