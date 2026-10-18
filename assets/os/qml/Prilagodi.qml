// Prilagodi namizje: ozadje (Safeer, Windows ali lastna slika), zameglitev in prekrivnost plosc. Barve so iz tokens.css,
// kontrast in velikost besedila iz sistema. Tipkovnica: ob odprtju je fokus v oknu, Escape (in Nazaj) ga zapre.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Dialogs
import QtQuick.Window

Item {
    id: prilagodi
    visible: opacity > 0
    opacity: 0
    Behavior on opacity { enabled: koren.gibanje; NumberAnimation { duration: 180 } }
    property Item fokusPrej: null
    function urlSlike(p) {     // Windows C:\… -> file:///C:/…, Linux /home/… -> file:///home/…
        p = String(p || "")
        return p.charAt(0) === "/" ? "file://" + encodeURI(p) : "file:///" + encodeURI(p.replace(/\\/g, "/"))
    }
    function odpri() {
        fokusPrej = Window.activeFocusItem
        opacity = 1; prilagodi.forceActiveFocus()
        koren.klic("videzNamizja", [], function (v) { koren.uporabiVidez(v) })
        if (koren.platforma === "linux")
            koren.klic("privzetiBrskalnik", [], function (ime) { prilagodi.napisBrskalnik = ime && typeof ime === "string" ? koren.t("spletVBrskalnikuIme", { ime: ime }) : koren.t("spletVBrskalniku") })
    }
    function zapri() {
        opacity = 0
        if (fokusPrej) fokusPrej.forceActiveFocus()
        fokusPrej = null
    }
    Keys.onEscapePressed: zapri()
    Keys.onBackPressed: zapri()
    Accessible.role: Accessible.Dialog
    Accessible.name: koren.t("prilagodi").replace(" …", "")
    function nastavi(sprememba) { koren.klic("nastaviVidezNamizja", [sprememba], function (v) { koren.uporabiVidez(v) }) }
    // Videz sistema (safeer-cinnamon): po spremembi preberemo videz znova (paleta, kontrast, velikost besedila).
    function sistem(kaj, vrednost) {
        koren.klic("videzCinnamonNastavi", [kaj, vrednost], function () { koren.klic("videzNamizja", [], function (v) { koren.uporabiVidez(v) }) })
    }
    property string napisBrskalnik: koren.t("spletVBrskalniku")

    Rectangle { anchors.fill: parent; color: Qt.rgba(0, 0, 0, 0.35)
        MouseArea { anchors.fill: parent; onClicked: prilagodi.zapri() } }

    Rectangle {
        id: okvir
        // Na nizkih zaslonih (1366 x 768) se vsebina pomika, okno ne seže cez rob.
        width: Math.min(720, parent.width - 80); height: Math.min(vsebina.implicitHeight + 48, parent.height - 32)
        anchors.centerIn: parent
        radius: 22
        color: koren.plosca(0.96); border.color: koren.crta(0.14)
        MouseArea { anchors.fill: parent }        // klik v oknu ga ne zapre
        Flickable {
            anchors.fill: parent; anchors.margins: 24; clip: true
            contentWidth: width; contentHeight: vsebina.implicitHeight; boundsBehavior: Flickable.StopAtBounds
            interactive: contentHeight > height
            ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
        Column {
            id: vsebina
            width: okvir.width - 48; spacing: 16
            Text { text: koren.t("prilagodi").replace(" …", ""); color: koren.paleta.besedilo; font.pixelSize: koren.px(20); font.bold: true }
            Text { text: koren.t("ozadje"); color: koren.paleta.medlo; font.pixelSize: koren.px(13) }
            Flow {
                width: parent.width; spacing: 12
                Repeater {
                    model: (koren.videz.ozadja || []).concat(koren.videz.windows ? [{ kljuc: "windows", ime: koren.t("ozadjeWindows"), url: koren.videz.windows }] : [])
                                                     .concat(koren.videz.lastna ? [{ kljuc: koren.videz.lastna, ime: koren.t("lastnaSlika").replace(" …", ""), url: prilagodi.urlSlike(koren.videz.lastna) }] : [])
                    delegate: Item {
                        width: 152; height: 112
                        property bool izbrano: koren.videz.izbira === modelData.kljuc
                        Rectangle {
                            id: slicica; width: 152; height: 86; radius: 12; clip: true
                            color: koren.paleta.vnos
                            border.width: parent.izbrano || activeFocus ? 3 : 1
                            border.color: activeFocus ? koren.paleta.fokus : parent.izbrano ? koren.paleta.poudarek : (mo.containsMouse ? koren.crta(0.4) : koren.crta(0.14))
                            activeFocusOnTab: true
                            Accessible.role: Accessible.RadioButton; Accessible.name: modelData.ime; Accessible.checked: parent.izbrano
                            Keys.onReturnPressed: prilagodi.nastavi({ ozadje: modelData.kljuc })
                            Keys.onEnterPressed: prilagodi.nastavi({ ozadje: modelData.kljuc })
                            Keys.onSpacePressed: prilagodi.nastavi({ ozadje: modelData.kljuc })
                            Image { anchors.fill: parent; anchors.margins: parent.border.width; source: modelData.url
                                    fillMode: Image.PreserveAspectCrop; asynchronous: true; sourceSize.width: 320 }
                            MouseArea { id: mo; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                        onClicked: prilagodi.nastavi({ ozadje: modelData.kljuc }) }
                        }
                        Text { anchors.top: slicica.bottom; anchors.topMargin: 6; width: 152; elide: Text.ElideRight
                               horizontalAlignment: Text.AlignHCenter; text: modelData.ime; font.pixelSize: koren.px(12)
                               color: parent.izbrano ? koren.paleta.poudarek : koren.paleta.besedilo }
                    }
                }
                Item {
                    width: 152; height: 112
                    Rectangle {
                        width: 152; height: 86; radius: 12; color: "transparent"
                        border.color: activeFocus ? koren.paleta.fokus : ml.containsMouse ? koren.paleta.poudarek : koren.crta(0.22)
                        border.width: activeFocus ? 3 : 1
                        activeFocusOnTab: true
                        Accessible.role: Accessible.Button; Accessible.name: koren.t("lastnaSlika")
                        Keys.onReturnPressed: izbiraSlike.open()
                        Keys.onEnterPressed: izbiraSlike.open()
                        Keys.onSpacePressed: izbiraSlike.open()
                        Text { anchors.centerIn: parent; text: "+"; color: koren.paleta.besedilo; font.pixelSize: koren.px(30) }
                        MouseArea { id: ml; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    onClicked: izbiraSlike.open() }
                    }
                    Text { y: 92; width: 152; horizontalAlignment: Text.AlignHCenter; text: koren.t("lastnaSlika")
                           color: koren.paleta.besedilo; font.pixelSize: koren.px(12) }
                }
            }
            Row {
                spacing: 14; width: parent.width
                Text { text: koren.t("zameglitevNapis"); color: koren.paleta.besedilo; font.pixelSize: koren.px(13); width: 170; anchors.verticalCenter: parent.verticalCenter }
                Slider { id: dZam; width: parent.width - 190; from: 0; to: 1; value: koren.zameglitev
                         Accessible.name: koren.t("zameglitevNapis")
                         onMoved: { koren.zameglitev = value; if (!pressed) shraniTipke.restart() }
                         onPressedChanged: if (!pressed) prilagodi.nastavi({ zameglitev: value }) }
            }
            Row {
                spacing: 14; width: parent.width
                Text { text: koren.t("prosojnostNapis"); color: koren.paleta.besedilo; font.pixelSize: koren.px(13); width: 170; anchors.verticalCenter: parent.verticalCenter }
                Slider { id: dPro; width: parent.width - 190; from: 0.2; to: 0.9; value: koren.prosojnost
                         Accessible.name: koren.t("prosojnostNapis")
                         onMoved: { koren.prosojnost = value; if (!pressed) shraniTipke.restart() }
                         onPressedChanged: if (!pressed) prilagodi.nastavi({ prosojnost: value }) }
            }
            Text { width: parent.width; wrapMode: Text.WordWrap; text: koren.t("temaOpis"); color: koren.paleta.medlo; font.pixelSize: koren.px(12) }
            // Kot meni plosc na delovni povrsini (Linux): velikost besedila in manj prosojnosti za ves sistem (safeer-cinnamon),
            // iskanje po spletu v privzetem brskalniku in sistemske nastavitve namizja (en klik stran - lastnik, 12. 10. 2026).
            Flow {
                visible: koren.platforma === "linux" && !!koren.videz.cinnamon
                width: parent.width; spacing: 8
                Text { text: koren.t("velikostBesedila"); color: koren.paleta.besedilo; font.pixelSize: koren.px(13); height: koren.px(30); verticalAlignment: Text.AlignVCenter; rightPadding: 6 }
                Repeater {
                    model: [100, 125, 150, 175, 200]
                    delegate: Gumb {
                        required property int modelData
                        objectName: "tekst" + modelData
                        besedilo: modelData === 200 ? koren.t("tekst200") : modelData + " %"
                        poudarjen: (koren.videz.tekstOdstotek || 100) === modelData
                        Accessible.role: Accessible.RadioButton; Accessible.checked: poudarjen
                        onKlik: prilagodi.sistem("tekst", modelData)
                    }
                }
            }
            Row {
                spacing: 10; width: parent.width
                visible: koren.platforma === "linux"
                Gumb { objectName: "manjProsojnosti"; visible: !!koren.videz.cinnamon; besedilo: (koren.kontrast ? "✓ " : "") + koren.t("manjProsojnosti")
                       Accessible.role: Accessible.CheckBox; Accessible.checked: koren.kontrast
                       onKlik: prilagodi.sistem("kontrast", !koren.kontrast) }
                Gumb { objectName: "spletVBrskalniku"; besedilo: (koren.videz.spletVBrskalniku ? "✓ " : "") + prilagodi.napisBrskalnik
                       Accessible.role: Accessible.CheckBox; Accessible.checked: !!koren.videz.spletVBrskalniku
                       onKlik: prilagodi.nastavi({ spletVBrskalniku: !koren.videz.spletVBrskalniku }) }
                // Moznost Sporocila v celoti (lastnik, 15. 10. 2026): izklop skrije razdelek povsod in ustavi kanale.
                Gumb { objectName: "sporocilaVklop"; besedilo: (koren.videz.sporocila !== false ? "✓ " : "") + koren.t("sporocilaVklop")
                       Accessible.role: Accessible.CheckBox; Accessible.checked: koren.videz.sporocila !== false
                       onKlik: prilagodi.nastavi({ sporocila: koren.videz.sporocila === false }) }
            }
            Text { visible: koren.platforma === "linux"; text: koren.t("sistemNaslov"); color: koren.paleta.medlo; font.pixelSize: koren.px(13) }
            Flow {
                visible: koren.platforma === "linux"
                width: parent.width; spacing: 8
                Repeater {
                    model: [["themes", "modulTeme"], ["backgrounds", "modulOzadja"], ["fonts", "modulPisave"], ["display", "modulZaslon"],
                            ["windows", "modulOkna"], ["panel", "modulPult"], ["nightlight", "modulNocna"], ["", "modulVse"]]
                    delegate: Gumb {
                        required property var modelData
                        besedilo: koren.t(modelData[1])
                        onKlik: koren.klic("sistemskeNastavitve", [modelData[0]])
                    }
                }
            }
            Row {
                spacing: 10; anchors.right: parent.right
                Gumb { besedilo: koren.t("temaSistema"); onKlik: { prilagodi.zapri(); koren.klic("odpriRazdelek", ["nastavitve"]) } }
                Gumb { besedilo: koren.t("privzeto"); onKlik: prilagodi.nastavi({ privzeto: true }) }
                Gumb { besedilo: koren.t("zapri"); poudarjen: true; onKlik: prilagodi.zapri() }
            }
        }
        }
    }
    // Drsnika s puscicami: shranimo, ko se tipke umirijo (z misko ob spustu).
    Timer { id: shraniTipke; interval: 400; onTriggered: prilagodi.nastavi({ zameglitev: dZam.value, prosojnost: dPro.value }) }
    FileDialog {
        id: izbiraSlike
        nameFilters: [koren.t("vrstaSlika") + " (*.jpg *.jpeg *.png *.webp *.bmp)"]
        onAccepted: {
            // Linux: /home/… ostane, kot je; Windows: C:/… -> C:\… (prej je tudi na Linuxu dobil »\home\…« in ga zavrnil).
            var pot = decodeURIComponent(String(selectedFile).replace(/^file:\/\//, ""))
            if (koren.platforma === "windows") pot = pot.replace(/^\//, "").replace(/\//g, "\\")
            prilagodi.nastavi({ ozadje: pot })
        }
    }
}
