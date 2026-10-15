// »Prilagodi dock …« (core/os_dock.py, Plank): vrstni red s puscicama gor/dol (tudi z daljincem - brez vlecenja),
// odstrani, dodaj program, vec nastavitev docka. Isto kot urediDock v delovna.js (lastnik, 11. 10. 2026: dodajanje,
// odstranjevanje in razvrscanje v docku mora biti enostavno). Escape v izbiri programa vrne na seznam.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts

Okno {
    id: okno
    objectName: "urediDock"
    width: Math.min(460, parent ? parent.width - 24 : 460)
    closePolicy: Popup.CloseOnPressOutside
    property var programiPC: []          // programi tega racunalnika (za »Dodaj program«), z ikonami
    property bool plank: false
    property var dock: []                // [{id, ime, ikona, dockitem}]
    property bool izbiram: false
    property string niz: ""
    readonly property var ids: dock.map(function (x) { return x.id })
    readonly property var zaDodati: programiPC.filter(function (p) {
        return ids.indexOf(p.id) < 0 && (!niz || p.ime.toLowerCase().indexOf(niz.toLowerCase()) >= 0)
    }).sort(function (a, b) { return a.ime.localeCompare(b.ime) })

    function odpri(programi) {
        programiPC = programi || []; izbiram = false; niz = ""
        nalozi(function () { okno.open(); Qt.callLater(function () { seznam.forceActiveFocus() }) })
    }
    function nalozi(potem) {
        koren.klic("dock", [], function (r) {
            okno.plank = !!(r && r.plank); okno.dock = (r && r.programi) || []
            if (potem) potem()
        }, function () { okno.plank = false; if (potem) potem() })
    }
    function ikona(x) {
        if (x.ikona) return x.ikona
        var p = programiPC.filter(function (q) { return q.id === x.id })[0]
        return p ? (p.ikona || "") : ""
    }
    function premakni(i, smer) {
        var j = i + smer
        if (j < 0 || j >= dock.length) return
        var d = dock.slice(), x = d[i]; d[i] = d[j]; d[j] = x
        dock = d
        seznam.currentIndex = j
        koren.klic("dockRazvrsti", [d.map(function (y) { return y.dockitem })], function (r) {
            if (!r || r.ok === false) koren.obvesti(koren.t("niUspelo"))
            okno.nalozi(null)
        }, function () { koren.obvesti(koren.t("niUspelo")); okno.nalozi(null) })
    }
    function preklopi(id, ime, dodaj, potem) {
        koren.klic(dodaj ? "dockDodaj" : "dockOdstrani", [id], function (r) {
            if (!r || r.ok === false) { koren.obvesti(koren.t("niUspelo")); return }
            koren.obvesti(koren.t(dodaj ? "dockDodano" : "dockOdstranjeno", { ime: ime }))
            okno.nalozi(potem)
        }, function () { koren.obvesti(koren.t("niUspelo")) })
    }

    contentItem: ColumnLayout {
        spacing: 10
        Keys.onEscapePressed: function (d) { if (okno.izbiram) { okno.izbiram = false; seznam.forceActiveFocus() } else okno.close(); d.accepted = true }
        Text { text: okno.izbiram ? koren.t("dockDodajProgram") : koren.t("dockNaslov"); color: koren.paleta.besedilo
               font.pixelSize: koren.px(15); font.bold: true }
        Text { visible: !okno.plank; text: koren.t("dockBrezPlanka"); Layout.fillWidth: true; wrapMode: Text.WordWrap
               color: koren.paleta.besedilo; font.pixelSize: koren.px(13) }
        Text { visible: okno.plank && !okno.izbiram; text: koren.t("dockOpis"); Layout.fillWidth: true; wrapMode: Text.WordWrap
               color: koren.paleta.medlo; font.pixelSize: koren.px(12) }
        TextField {
            id: polje
            visible: okno.plank && okno.izbiram; Layout.fillWidth: true
            placeholderText: koren.t("dockIsci"); placeholderTextColor: koren.paleta.medlo; color: koren.paleta.besedilo; font.pixelSize: koren.px(13)
            background: Rectangle { radius: 8; color: koren.prekriv(0.08); border.color: polje.activeFocus ? koren.paleta.fokus : koren.crta(0.2) }
            onTextChanged: okno.niz = text
            Keys.onDownPressed: izbira.forceActiveFocus()
            Keys.onEscapePressed: function (d) { okno.izbiram = false; seznam.forceActiveFocus(); d.accepted = true }
        }
        // Programi v docku po vrsti: ↑ ↓ ✕ (z miško ali tipkovnico: puscice izberejo vrstico, Alt+puscica premakne, Delete odstrani).
        ListView {
            id: seznam
            objectName: "seznamDocka"
            visible: okno.plank && !okno.izbiram
            Layout.fillWidth: true; Layout.preferredHeight: Math.min(Math.max(contentHeight, koren.px(40)), koren.px(380)); clip: true; spacing: 2
            model: okno.dock; activeFocusOnTab: true; keyNavigationEnabled: true
            Accessible.role: Accessible.List; Accessible.name: koren.t("dockNaslov")
            Keys.onPressed: function (d) {
                if ((d.modifiers & Qt.AltModifier) && (d.key === Qt.Key_Up || d.key === Qt.Key_Down)) {
                    okno.premakni(currentIndex, d.key === Qt.Key_Up ? -1 : 1); d.accepted = true
                } else if (d.key === Qt.Key_Delete && okno.dock[currentIndex]) {
                    var x = okno.dock[currentIndex]; okno.preklopi(x.id, x.ime, false, null); d.accepted = true
                }
            }
            Text { anchors.centerIn: parent; visible: seznam.count === 0; text: koren.t("dockPrazen"); color: koren.paleta.medlo; font.pixelSize: koren.px(13) }
            delegate: Rectangle {
                id: vrstica
                required property var modelData
                required property int index
                width: seznam.width; height: koren.px(40); radius: 10
                color: seznam.activeFocus && index === seznam.currentIndex ? koren.poudarekA(0.2) : koren.prekriv(0.05)
                border.width: seznam.activeFocus && index === seznam.currentIndex ? 2 : 0; border.color: koren.paleta.fokus
                Accessible.role: Accessible.ListItem; Accessible.name: modelData.ime
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 6; spacing: 8
                    Image { source: okno.ikona(vrstica.modelData); sourceSize: Qt.size(48, 48); Layout.preferredWidth: 24; Layout.preferredHeight: 24 }
                    Text { Layout.fillWidth: true; text: vrstica.modelData.ime; color: koren.paleta.besedilo; font.pixelSize: koren.px(13); elide: Text.ElideRight }
                    Gumb { besedilo: "↑"; enabled: vrstica.index > 0; Accessible.name: koren.t("dockGor"); onKlik: okno.premakni(vrstica.index, -1) }
                    Gumb { besedilo: "↓"; enabled: vrstica.index < okno.dock.length - 1; Accessible.name: koren.t("dockDol"); onKlik: okno.premakni(vrstica.index, 1) }
                    Gumb { besedilo: "✕"; Accessible.name: koren.t("dockOdstrani"); onKlik: okno.preklopi(vrstica.modelData.id, vrstica.modelData.ime, false, null) }
                }
            }
        }
        ListView {
            id: izbira
            objectName: "izbiraDocka"
            visible: okno.plank && okno.izbiram
            Layout.fillWidth: true; Layout.preferredHeight: koren.px(360); clip: true; spacing: 2
            model: okno.zaDodati; activeFocusOnTab: true; keyNavigationEnabled: true
            Accessible.role: Accessible.List; Accessible.name: koren.t("dockDodajProgram")
            function dodaj(p) { okno.preklopi(p.id, p.ime, true, function () { okno.izbiram = false; seznam.forceActiveFocus() }) }
            Keys.onReturnPressed: if (okno.zaDodati[currentIndex]) dodaj(okno.zaDodati[currentIndex])
            Keys.onEnterPressed: if (okno.zaDodati[currentIndex]) dodaj(okno.zaDodati[currentIndex])
            Keys.onUpPressed: if (currentIndex <= 0) polje.forceActiveFocus(); else decrementCurrentIndex()
            delegate: Rectangle {
                id: moznost
                required property var modelData
                required property int index
                width: izbira.width; height: koren.px(38); radius: 10
                color: (izbira.activeFocus && index === izbira.currentIndex) || mi.containsMouse ? koren.poudarekA(0.2) : koren.prekriv(0.05)
                Accessible.role: Accessible.Button; Accessible.name: modelData.ime
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: 10; anchors.rightMargin: 12; spacing: 8
                    Image { source: moznost.modelData.ikona || ""; sourceSize: Qt.size(48, 48); Layout.preferredWidth: 24; Layout.preferredHeight: 24 }
                    Text { Layout.fillWidth: true; text: moznost.modelData.ime; color: koren.paleta.besedilo; font.pixelSize: koren.px(13); elide: Text.ElideRight }
                    Text { text: "+"; color: koren.paleta.poudarek; font.pixelSize: koren.px(16); font.bold: true }
                }
                MouseArea { id: mi; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor; onClicked: izbira.dodaj(moznost.modelData) }
            }
        }
        Flow {
            Layout.fillWidth: true; spacing: 8; layoutDirection: Qt.RightToLeft
            Gumb { besedilo: koren.t("zapri"); onKlik: okno.close() }
            Gumb { visible: okno.plank && !okno.izbiram; besedilo: koren.t("dockVecNastavitev")
                   onKlik: { okno.close(); koren.klic("nastavitveDocka", []) } }
            Gumb { objectName: "dockDodajProgram"; visible: okno.plank && !okno.izbiram; besedilo: koren.t("dockDodajProgram"); poudarjen: true
                   onKlik: { okno.izbiram = true; polje.text = ""; polje.forceActiveFocus() } }
            Gumb { visible: okno.izbiram; besedilo: koren.t("preklici"); onKlik: { okno.izbiram = false; seznam.forceActiveFocus() } }
        }
    }
}
