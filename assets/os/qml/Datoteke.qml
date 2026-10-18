// Panel Datoteke: Nedavno, Najvecje datoteke, Koš, mape, pogoni (z »Izvrzi«); seznam z odpiranjem, »Pokaži v mapi«,
// kopiranjem, prilepljanjem, novo mapo ali datoteko (tudi iz predloge), preimenovanjem, Lastnostmi, Košem in Razveljavi
// (Ctrl+Z) - ista dejanja in besedila kot Datoteke na delovni povrsini WebKit (delovna.js). Datoteke se vlecejo v druge
// programe (seznam naslovov datotek) in iz njih (kopija v mapo). Seznam se osvezi sam, ko se mapa spremeni zunaj.
// Priljubljeno (skupni zapis Safeer OS, Ctrl+D), izbira vec datotek (Ctrl/Shift+klik, Ctrl+A, Shift+puscice) z dejanji
// za vse izbrane in predogled s preslednico (Predogled.qml).
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
    property string kljucNaprave: ""     // Global Link (datotekeNaprave -> kljuc) za predvajanje z naprave
    property var pot: []                 // [{id, ime}] mape naprave od korena navzdol
    property var lokalniViri: []
    property var mapeNamizja: []
    property var nosilci: []
    property string stanje: ""           // "", "napaka", "neDeli"
    // Metode mostu, ki jih ima Safeer OS na Linuxu (najvecje datoteke, prostor, predloge, izvrzi, razveljavi …).
    readonly property bool linux: koren.platforma === "linux"
    property var prostor: ({})
    property var predloge: []
    property var odlozisce: ({ poti: [], rezi: false, ime: "" })
    property var razveljavitve: []       // zapisi za razveljaviDatoteke (zadnjih 20), kot RZ v delovna.js
    property var slicice: ({})           // pot -> naslov slicice (sliciceDatotek)
    property var vlecem: []              // poti, ki jih uporabnik vlece iz tega seznama
    // Izbira vec datotek (kot v Nemu in na delovni povrsini): Ctrl+klik doda/odvzame, Shift+klik in Shift+puscice
    // izberejo obseg od sidra, Ctrl+A vse, Ctrl+preslednica doda/odvzame vrstico s fokusom, Escape pusti eno.
    property var izbrane: ({})           // kljuc vnosa -> true
    property int sidro: -1
    readonly property int steviloIzbranih: Object.keys(izbrane).length
    readonly property var prikazani: elementi.filter(function (e) {
        return !filter || e.ime.toLowerCase().indexOf(filter.toLowerCase()) >= 0
    })

    function kljucVnosa(e) { return e ? String(e.pot || e.id || e.ime || "") : "" }
    function jeIzbran(e) { return !!izbrane[kljucVnosa(e)] }
    function izbraniVnosi() { var z = izbrane; return prikazani.filter(function (e) { return !!z[panel.kljucVnosa(e)] }) }
    function izberiSamo(i) { var e = prikazani[i], z = {}; if (e) z[kljucVnosa(e)] = true; izbrane = z; sidro = e ? i : -1 }
    function preklopiIzbor(i) {
        var e = prikazani[i]
        if (!e) return
        var z = {}, k = kljucVnosa(e)
        for (var x in izbrane) z[x] = true
        if (z[k]) delete z[k]; else z[k] = true
        izbrane = z; sidro = i
    }
    function izberiObseg(i) {
        if (i < 0 || i >= prikazani.length) return
        var a = sidro >= 0 && sidro < prikazani.length ? sidro : i, z = {}
        for (var j = Math.min(a, i); j <= Math.max(a, i); j++) z[kljucVnosa(prikazani[j])] = true
        izbrane = z
        if (sidro < 0) sidro = i
    }
    function izberiVse() { var z = {}; prikazani.forEach(function (e) { z[panel.kljucVnosa(e)] = true }); izbrane = z }
    function pocistiIzbor() { izbrane = ({}); sidro = -1 }
    // Dejanje na vrstici e velja za vse izbrane, ce je e med njimi; sicer samo za e (kot v Nemu).
    function zaDejanje(e) {
        var v = izbraniVnosi()
        return e && !jeIzbran(e) ? [e] : (v.length ? v : (e ? [e] : []))
    }
    function zacni(mape) {
        mapeNamizja = mape || []
        sestaviVire()
        osveziNosilce()
        if (linux) {
            preveriProstor()
            koren.klic("predlogeDatotek", [], function (p) { panel.predloge = (p || []).slice(0, 12) })
        }
        odpri({ vrsta: "nedavno", pot: "" })
    }
    function sestaviVire() {
        var v = [{ oznaka: koren.t("nedavno"), vir: { vrsta: "nedavno", pot: "" } }]
        // Priljubljeno: datoteke in mape, ki si jih je uporabnik izbral (skupaj z delovno povrsino WebKit).
        if (linux) v.push({ oznaka: koren.t("priljubljeno"), vir: { vrsta: "priljubljeno", pot: "@priljubljeno" } })
        // Najvecje datoteke (za skupni prostor): kot »Največje datoteke« na delovni povrsini.
        if (linux) v.push({ oznaka: koren.t("najvecje"), vir: { vrsta: "najvecje", pot: "@najvecje" } })
        v.push({ oznaka: koren.t("smeti"), vir: { vrsta: "smeti", pot: "smeti" } })
        v.push({ naslov: koren.t("mape") })
        mapeNamizja.forEach(function (m) { v.push({ oznaka: koren.t(m.vrsta) !== m.vrsta ? koren.t(m.vrsta) : m.ime, vir: { vrsta: "lokalno", pot: m.pot } }) })
        v.push({ naslov: koren.t("naprave") })
        nosilci.forEach(function (x) {
            v.push({ oznaka: x.ime + (x.ime === x.pot.replace("\\", "") ? "" : " (" + x.pot.replace("\\", "") + ")"), vir: { vrsta: "lokalno", pot: x.pot }, pogon: x })
        })
        lokalniViri = v
        if (!naprava) viri = v
    }
    function osveziNosilce() {
        koren.klic("nosilci", [], function (n) {
            var novi = (n || []).filter(function (x) { return x && x.pot })
            if (JSON.stringify(novi.map(function (x) { return x.pot })) === JSON.stringify(panel.nosilci.map(function (x) { return x.pot }))
                && panel.lokalniViri.length) return
            panel.nosilci = novi; panel.sestaviVire()
        })
    }
    // USB kljuci in diski pridejo in gredo: Safeer OS ob priklopu ali odklopu poslje dogodek »nosilci« (Namizje.qml).
    function izvrzi(n) {
        koren.klic("izvrziNosilec", [n.pot], function (r) {
            if (r && r.ok) {
                koren.obvesti(koren.t("izvrzeno", { ime: n.ime }))
                if (panel.vir.vrsta === "lokalno" && String(panel.vir.pot).indexOf(n.pot) === 0) panel.odpri({ vrsta: "nedavno", pot: "" })
            } else koren.obvesti(r && r.napaka === "zaseden" ? koren.t("izvrziZaseden", { ime: n.ime }) : koren.t("niUspelo"))
            panel.osveziNosilce()
        }, function () { koren.obvesti(koren.t("niUspelo")) })
    }
    // Malo prostora na disku: Datoteke same ponudijo Najvecje datoteke (od tam »Shrani na drugo napravo …«).
    function preveriProstor() {
        if (!linux) return
        koren.klic("prostorDiska", [], function (p) { panel.prostor = p || {} })
    }

    function fokus() { seznam.forceActiveFocus() }
    // Mapa tega racunalnika (npr. iz iskanja): najprej nazaj na »Ta racunalnik«, ce so bile odprte datoteke naprave.
    function odpriLokalno(pot) {
        naprava = ""; imeNaprave = ""; panel.pot = []; streznik = null; viri = lokalniViri
        odpri({ vrsta: "lokalno", pot: pot })
    }
    function odpri(v) {
        // Nova mapa: meni, ki se se odpira (caka na odgovore mostu), ali odprt meni ne sme delati na prejsnji izbiri.
        zahtevaMenija++; meni.close(); meniVec.close()
        vir = v; filter = ""; poljeFilter.text = ""; pocistiIzbor(); seznam.currentIndex = seznam.activeFocus ? 0 : -1; nalozi(false)
    }
    function izberiNapravo(id, ime) {
        naprava = id; imeNaprave = ime; pot = []; streznik = null; kljucNaprave = ""
        if (!id) { viri = lokalniViri; odpri({ vrsta: "nedavno", pot: "" }); return }
        viri = [{ naslov: koren.t("mapeNaprave") }]
        odpri({ vrsta: "naprava", pot: "" })
    }
    function vrstaOddaljenega(t) {
        return t === "audio" ? "zvok" : t === "video" ? "video" : t === "image" ? "slika" : ""
    }
    function vnosNaprave(d) {
        var mapa = d.type === "folder" || d.vrsta === "folder" || d.vrsta === "mapa"
        var ime = d.name || d.ime || ""
        return { ime: ime, id: d.id || "", mapa: mapa, velikost: d.size || d.velikost || 0,
                 spremenjeno: d.mtime || d.modified || d.spremenjeno || 0,
                 vrsta: mapa ? "mapa" : (d.vrsta || vrstaOddaljenega(d.type)), pot: d.id || "", izvirnik: d }
    }
    function jeLokalniPogled() { return vir.vrsta === "lokalno" || vir.vrsta === "nedavno" || vir.vrsta === "najvecje" || vir.vrsta === "priljubljeno" }
    // Priljubljene iz skupnega zapisa: Safeer OS poslje samo tiste, ki so na svoji poti (lastnik, 15. 10. 2026:
    // »nimamo nedelujocih ikon ali datotek«) - v Smeteh ali na odklopljenem disku so skrite in se vrnejo same.
    function seznamPriljubljenih() {
        return (koren.priljubljeno.datoteke || []).map(function (d) {
            return { ime: d.ime, pot: d.pot, mapa: !!d.mapa, vrsta: d.mapa ? "mapa" : (d.vrsta || ""), velikost: d.velikost || 0,
                     spremenjeno: d.spremenjeno || 0 }
        })
    }
    Connections {
        target: koren
        function onPriljubljenoChanged() {
            if (panel.vir.vrsta !== "priljubljeno") return
            panel.elementi = panel.seznamPriljubljenih()
            var z = {}, prej = panel.izbrane
            panel.elementi.forEach(function (e) { var k = panel.kljucVnosa(e); if (prej[k]) z[k] = true })
            panel.izbrane = z
        }
    }
    function nalozi(tiho) {
        var st = ++zahteva
        if (!tiho) elementi = []
        var konec = function (r) {
            if (st !== zahteva) return
            if (vir.vrsta === "lokalno") { elementi = (r && r.elementi) || []; stars = (r && r.stars) || "" }
            else if (vir.vrsta === "smeti") { elementi = (r && r.elementi) || []; stars = "" }
            else { elementi = r || []; stars = "" }
            // Izbira ostane za vnose, ki so se v seznamu (osvezitev po spremembi zunaj).
            var z = {}, prej = izbrane
            elementi.forEach(function (e) { var k = panel.kljucVnosa(e); if (prej[k]) z[k] = true })
            izbrane = z
            naloziSlicice()
        }
        stanje = ""
        if (vir.vrsta === "naprava") {
            koren.klic("datotekeNaprave", [naprava, vir.pot], function (r) {
                if (st !== zahteva) return
                if (!r || !r.ok) { stanje = "napaka"; elementi = []; return }
                if (!r.shared) { stanje = "neDeli"; elementi = []; return }
                if (r.server) streznik = r.server
                if (r.kljuc) kljucNaprave = r.kljuc
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
        if (vir.vrsta === "priljubljeno") {
            // Sveze iz Safeer OS (kar je medtem izginilo ali se vrnilo, npr. USB disk); do odgovora zadnje znano.
            koren.klic("spremljajMapo", [""])
            konec(seznamPriljubljenih())
            if (linux) koren.klic("priljubljenoSeznam", [], function (p) { if (st === zahteva) koren.nastaviPriljubljeno(p) })
            return
        }
        if (vir.vrsta === "lokalno") { koren.klic("mapa", [vir.pot], konec); koren.klic("spremljajMapo", [vir.pot]) }
        else if (vir.vrsta === "smeti") koren.klic("smeti", [], konec)
        else if (vir.vrsta === "najvecje") koren.klic("najvecjeDatoteke", [], konec, function () { if (st === zahteva) { elementi = []; stanje = "napaka" } })
        else koren.klic("nedavne", [], konec)
        // Linux spremlja tudi Nedavno in Smeti (kot pogledVira v delovna.js); Najvecje ni pogled, ki bi se spreminjal.
        if (linux && vir.vrsta !== "lokalno") koren.klic("spremljajMapo", [pogledVira()])
    }
    function pogledVira() {
        return vir.vrsta === "lokalno" ? vir.pot : vir.vrsta === "nedavno" ? "@nedavno" : vir.vrsta === "smeti" ? "@smeti" : ""
    }
    // Slicice slik in videov (iz predpomnilnika namizja ali pomanjsane sproti), kot na delovni povrsini.
    function naloziSlicice() {
        if (!linux || !jeLokalniPogled()) return
        var manjka = elementi.filter(function (e) { return !e.mapa && (e.vrsta === "slika" || e.vrsta === "video") && !(e.pot in panel.slicice) })
                             .slice(0, 60).map(function (e) { return e.pot })
        if (!manjka.length) return
        koren.klic("sliciceDatotek", [manjka], function (r) {
            var s = {}
            for (var k in panel.slicice) s[k] = panel.slicice[k]
            manjka.forEach(function (p) { s[p] = (r && r[p]) || "" })
            panel.slicice = s
        })
    }
    function odpriElement(e) {
        if (vir.vrsta === "smeti") return
        if (vir.vrsta === "naprava") {
            if (e.mapa) { pot = pot.concat([{ id: e.id, ime: e.ime }]); odpri({ vrsta: "naprava", pot: e.id }); return }
            // Glasba ali video z naprave: predvaja se sproti, brez prenosa (kot na delovni povrsini; core/link_pretok).
            if (linux && streznik && (e.vrsta === "zvok" || e.vrsta === "video")) { predvajajZNaprave(e); return }
            // Najbolj gladko: datoteka pride sem in jo odpre program tega racunalnika (fotografije, video, urejanje).
            // Ce prenos ni mogoc, jo odpre program naprave prek oddaljenega namizja (lastnik, 13. 10. 2026).
            if (streznik && streznik.base_url) odpriTukaj(e)
            else odpriSProgramomNaprave(e)
            return
        }
        if (e.mapa) { odpri({ vrsta: "lokalno", pot: e.pot }); return }
        odpriDatotekoTegaRacunalnika(e)
    }
    function odpriDatotekoTegaRacunalnika(e) {
        // Glasba in video tega racunalnika se predvajajo v Medijskem centru (mali predvajalnik na namizju).
        if (linux && (e.vrsta === "zvok" || e.vrsta === "video")) {
            koren.klic("odpriLokalniMedij", [e.pot], function (ok) {
                if (ok) koren.osveziMedij()
                else koren.klic("odpriDatoteko", [e.pot], function (ok2) { if (!ok2) koren.obvesti(koren.t("niUspelo")) })
            })
            return
        }
        koren.klic("odpriDatoteko", [e.pot], function (ok) { if (ok === false) koren.obvesti(koren.t("niUspelo")) })
    }
    function predvajajZNaprave(e) {
        var predvajljivi = elementi.filter(function (x) { return !x.mapa && (x.vrsta === "zvok" || x.vrsta === "video") })
        koren.klic("predvajajZNaprave", [streznik, kljucNaprave, predvajljivi.map(function (x) { return x.izvirnik || {} }),
                                         predvajljivi.indexOf(e), imeNaprave, naprava], function (ok) {
            if (!ok) koren.obvesti(koren.t("niUspelo")); else koren.osveziMedij()
        }, function () { koren.obvesti(koren.t("niUspelo")) })
    }
    // »Nadaljuj tukaj«: datoteka z druge naprave se shrani sem (prenese se samo, kar se je spremenilo - core/link_nadaljuj)
    // in odpre; izid pove, koliko je slo po omrezju in kako se je odprla (Teamwork). Besedila kot nadaljujTukaj v delovna.js.
    property var nadaljujeTece: ({})
    function odpriTukaj(e) {
        var kljuc = naprava + "\n" + e.id
        if (nadaljujeTece[kljuc]) return
        var t_ = nadaljujeTece; t_[kljuc] = true; nadaljujeTece = t_
        koren.obvesti(koren.t("nadaljujPrenasam", { ime: e.ime, naprava: imeNaprave }))
        // 5. argument (imena map do datoteke) uporabi Linux za mesto delovne kopije; Windows ga prezre.
        var mape = pot.map(function (p) { return p.ime }), ime = imeNaprave
        koren.klic("prenesiDatotekoNaprave", [naprava, e.id, e.ime, streznik, mape], function (r) {
            var t2 = panel.nadaljujeTece; delete t2[kljuc]; panel.nadaljujeTece = t2
            if (!r || !r.ok) {
                var k = "nadaljujNapaka_" + ((r && r.koda) || ""), s = koren.t(k)
                koren.obvesti(s === k ? koren.t("nadaljujNapaka") : s); return
            }
            koren.obvesti(panel.besediloNadaljuj(r, ime))
        }, function () { var t3 = panel.nadaljujeTece; delete t3[kljuc]; panel.nadaljujeTece = t3; koren.obvesti(koren.t("nadaljujNapaka")) })
    }
    function besediloNadaljuj(r, ime) {
        var b = ""
        if (r.velikost !== undefined || r.preneseno !== undefined) {
            b = r.delta ? koren.t("nadaljujIzid", { preneseno: koren.velikost(r.preneseno) || "0 B", velikost: koren.velikost(r.velikost) || "0 B",
                                                    odstotek: r.velikost ? Math.floor(100 * (r.iz_lokalnih || 0) / r.velikost) : 100 })
                        : koren.t("nadaljujIzidPolno", { preneseno: koren.velikost(r.preneseno) || "0 B" })
        }
        var d = []
        if (b) d.push(b)
        if (r.izvirnik) d.push(koren.t("nadaljujIzvirnik"))
        if (r.prejsnja_v_smeteh) d.push(koren.t("nadaljujSmeti"))
        if (r.odprto && r.nacin === "podprt" && r.program) d.push(koren.t("nadaljujPodprt", { program: r.program, naprava: ime }))
        if (r.odprto && r.nacin === "pretok") d.push(koren.t("nadaljujPretok", { naprava: ime }))
        if (r.teamwork && r.teamwork.drugi && r.teamwork.drugi.length)
            d.push(koren.t("nadaljujTeamwork", { drugi: r.teamwork.drugi.map(function (x) { return x === "@tukaj" ? ime : x }).join(", ") }))
        if (r.odprto === false && r.pot) d.push(koren.t("nadaljujNiOdprto", { pot: koren.kratkaPot(r.pot) }))
        return d.join(" ") || koren.t("odprtoNaNapravi", { naprava: ime })
    }
    function odpriSProgramomNaprave(e) {
        // Prek oddaljenega namizja: naprava datoteko odpre na svojem LOCENEM zaslonu - njen uporabnik tega ne opazi.
        koren.obvesti(koren.t("odpiramZ", { ime: e.ime, naprava: imeNaprave }))
        koren.klic("odpriDatotekoTukaj", [naprava, e.id], function (r) {
            if (!(r && r.ok)) koren.obvesti(r && r.koda === "ni_locenega_zaslona" ? koren.t("niLocenega") : ((r && r.message) || koren.t("niUspelo")))
        })
    }

    // ---------------------------------------------------------------- razveljavi (kot RZ v delovna.js)
    // Zapis dejanja (premik, kopija, Koš, preimenovanje, novo) sestavimo iz odgovora Safeer OS; razveljavitev nicesar ne
    // prepise in ne izbrise trajno (kopije in ustvarjeno gredo v Smeti). Vrne funkcijo za gumb »Razveljavi« v obvestilu.
    function zapomni(zapis) {
        if (!linux || !zapis || !((zapis.pari && zapis.pari.length) || (zapis.idji && zapis.idji.length))) return null
        var r = razveljavitve.slice(); r.push(zapis); if (r.length > 20) r.shift(); razveljavitve = r
        return function () { panel.razveljavi(zapis) }
    }
    function obvestiZRazveljavi(besedilo, nazaj) { koren.obvesti(besedilo, nazaj ? koren.t("razveljavi") : "", nazaj) }
    function razveljavi(zapis) {
        zapis = zapis || razveljavitve[razveljavitve.length - 1]
        if (!zapis) { koren.obvesti(koren.t("nicZaRazveljaviti")); return }
        razveljavitve = razveljavitve.filter(function (x) { return x !== zapis })
        koren.klic("razveljaviDatoteke", [zapis], function (r) {
            r = r || {}
            var n = r.narejeno || 0, ne = (r.napake || []).length
            koren.obvesti(n && !ne ? koren.t("razveljavljeno") : n ? koren.t("delnoUspelo", { ok: n, ne: ne }) : koren.t("razveljavitevNiUspela"))
            panel.nalozi(true)
        }, function () { koren.obvesti(koren.t("razveljavitevNiUspela")) })
    }

    // ---------------------------------------------------------------- odlozisce, prilepi, spust
    function steviloElementov(n) {
        if (koren.jezik === "sl") {
            var m = n % 100
            return n + " " + (m === 1 ? "element" : m === 2 ? "elementa" : (m === 3 || m === 4) ? "elementi" : "elementov")
        }
        return koren.t(n === 1 ? "elem1" : "elemN", { n: n })
    }
    function vOdlozisce(e, rezi) { if (e) vOdloziscePoti(zaDejanje(e), rezi) }
    function vOdloziscePoti(v, rezi) {
        if (vir.vrsta === "naprava" || vir.vrsta === "smeti") return
        v = (v || []).filter(function (x) { return x && x.pot })
        if (!v.length) return
        var ime = v.length === 1 ? v[0].ime : steviloElementov(v.length)
        odlozisce = { poti: v.map(function (x) { return x.pot }), rezi: !!rezi, ime: ime }
        koren.obvesti(koren.t(rezi ? "izrezano" : "kopirano", { ime: ime }))
    }
    function kamNovo() { return vir.vrsta === "lokalno" && vir.pot ? vir.pot : (koren.dom || "~") }
    function prilepi(vMapo) {
        if (!odlozisce.poti.length) return
        var cilj = vMapo || kamNovo(), rezi = odlozisce.rezi, ime = odlozisce.ime, poti = odlozisce.poti
        koren.obvesti(koren.t(rezi ? "premikam" : "kopiram"))
        koren.klic("prilepiDatoteke", [poti, cilj, rezi], function (r) {
            r = r || {}
            var narejeno = r.narejeno || [], napake = r.napake || []
            if (narejeno.length) {
                var nazaj = zapomni({ vrsta: rezi ? "premik" : "kopija", pari: r.pari || [] })
                if (napake.length) obvestiZRazveljavi(koren.t("delnoUspelo", { ok: narejeno.length, ne: napake.length }), nazaj)
                else obvestiZRazveljavi(koren.t(rezi ? "premaknjeno" : "prilepljeno",
                                                { ime: narejeno.length === 1 ? String(narejeno[0]).split("/").pop() : ime }), nazaj)
                if (rezi) panel.odlozisce = { poti: [], rezi: false, ime: "" }
            } else {
                var koda = r.napaka || ((napake[0] || {}).napaka) || ""
                if (r.ok && !koda) koren.obvesti(koren.t("premaknjeno", { ime: ime }))
                else koren.obvesti(koren.t("prilepiNapaka_" + koda) !== "prilepiNapaka_" + koda ? koren.t("prilepiNapaka_" + koda) : koren.t("niUspelo"))
            }
            panel.nalozi(true)
        }, function () { koren.obvesti(koren.t("niUspelo")) })
    }
    // Spust v mapo: vlecenje iz tega seznama datoteke PREMAKNE (s Ctrl kopira), datoteke iz drugega programa (Nemo,
    // brskalnik) se KOPIRAJO - kot na delovni povrsini. Ne v mapo, kjer ze so, in ne mape vase.
    function smiselne(poti, cilj) {
        return poti.filter(function (p) { return p && p !== cilj && p.replace(/\/[^/]*$/, "") !== cilj && cilj.indexOf(p + "/") !== 0 })
    }
    function potiSpusta(drop) {
        return (drop.urls || []).map(function (u) { return Most.datotekaPot(String(u)) }).filter(function (p) { return !!p })
    }
    function spusti(drop, cilj) {
        var nase = vlecem.length > 0
        var poti = smiselne(nase ? vlecem : potiSpusta(drop), cilj)
        var premakni = nase && !Most.ctrl()
        vlecem = []
        if (!poti.length) return false
        drop.accept(premakni ? Qt.MoveAction : Qt.CopyAction)
        koren.obvesti(koren.t(premakni ? "premikam" : "kopiram"))
        koren.klic("prilepiDatoteke", [poti, cilj, premakni], function (r) {
            r = r || {}
            var narejeno = r.narejeno || [], napake = r.napake || []
            var nazaj = zapomni({ vrsta: premakni ? "premik" : "kopija", pari: r.pari || [] })
            if (narejeno.length && !napake.length) {
                obvestiZRazveljavi(koren.t(premakni ? "premaknjenoV" : "kopiranoV", { mapa: cilj.replace(/\/$/, "").split("/").pop() || "/",
                    ime: narejeno.length === 1 ? String(narejeno[0]).split("/").pop() : steviloElementov(narejeno.length) }), nazaj)
            } else if (narejeno.length) obvestiZRazveljavi(koren.t("delnoUspelo", { ok: narejeno.length, ne: napake.length }), nazaj)
            else {
                var koda = r.napaka || ((napake[0] || {}).napaka) || ""
                koren.obvesti(koren.t("prilepiNapaka_" + koda) !== "prilepiNapaka_" + koda ? koren.t("prilepiNapaka_" + koda) : koren.t("niUspelo"))
            }
            panel.nalozi(true)
        }, function () { koren.obvesti(koren.t("niUspelo")) })
        return true
    }
    function lahkoSpusti(drag, cilj) {
        if (!linux || !cilj) return false
        if (vlecem.length) return smiselne(vlecem, cilj).length > 0
        return drag.hasUrls
    }

    function vKos(e) {
        var v = zaDejanje(e).filter(function (x) { return x.pot })
        if (v.length > 1) { vKosVec(v); return }
        if (!e || !e.pot) return
        koren.klic("vSmeti", [e.pot], function (r) {
            if (!r || !r.ok) { koren.obvesti(koren.t("niUspelo")); return }
            panel.nalozi(true)
            var nazaj = panel.zapomni({ vrsta: "smeti", idji: r.id ? [r.id] : [] })
            // Brez Razveljavi na Linuxu: obnova iz Smeti (kot doslej na Windows).
            if (!nazaj && r.id) nazaj = function () { koren.klic("obnoviIzSmeti", [r.id], function () { panel.nalozi(true) }) }
            panel.obvestiZRazveljavi(koren.t("vKosPoslano", { ime: e.ime }), nazaj)
        })
    }
    // Vec v Smeti z enim dejanjem: en zapis za Razveljavi (Ctrl+Z vrne vse) - core/os_datoteke.v_smeti_vec.
    function vKosVec(v) {
        var v0 = vir
        koren.klic("vSmetiVec", [v.map(function (x) { return x.pot })], function (r) {
            r = r || {}
            var ok = (r.narejeno || []).length, ne = (r.napake || []).length
            // Uporabnik je medtem morda ze v drugi mapi: tam izbire ne pocistimo.
            if (panel.vir === v0) { panel.pocistiIzbor(); panel.nalozi(true) }
            if (r.napaka === "prevec") { koren.obvesti(koren.t("prevecNaenkrat", { najvec: r.najvec || 500 })); return }
            if (!ok) { koren.obvesti(koren.t("niUspelo")); return }
            var nazaj = panel.zapomni({ vrsta: "smeti", idji: r.idji || [] })
            panel.obvestiZRazveljavi(ne ? koren.t("delnoUspelo", { ok: ok, ne: ne }) : koren.t("vSmetiVecOk", { ime: panel.steviloElementov(ok) }), nazaj)
        }, function () { koren.obvesti(koren.t("niUspelo")) })
    }
    function obnoviVec(v) {
        var ostane = v.length, ok = 0, v0 = vir
        v.forEach(function (x) {
            koren.klic("obnoviIzSmeti", [x.id], function (r) {
                if (r && r.ok) ok++
                if (--ostane === 0) {
                    if (panel.vir === v0) { panel.pocistiIzbor(); panel.nalozi(true) }
                    koren.obvesti(ok === v.length ? koren.t("obnovljenoN", { ime: panel.steviloElementov(ok) }) : koren.t("delnoUspelo", { ok: ok, ne: v.length - ok }))
                }
            }, function () { if (--ostane === 0) { panel.nalozi(true); koren.obvesti(koren.t("niUspelo")) } })
        })
    }
    // Ctrl+D ali meni: v priljubljene (ali iz njih) - za vse izbrane naenkrat; ce so ze vsi priljubljeni, jih odstrani.
    function preklopiPriljubljene(e) { preklopiPriljubljeneVec(zaDejanje(e)) }
    function preklopiPriljubljeneVec(v) {
        v = (v || []).filter(function (x) { return x && x.pot })
        if (!linux || !v.length || vir.vrsta === "naprava" || vir.vrsta === "smeti") return
        if (v.length === 1) { koren.preklopiPriljubljeno("datoteka", { pot: v[0].pot, ime: v[0].ime, mapa: !!v[0].mapa }, v[0].ime); return }
        // En klic za vse (ena sprememba, en dogodek): prej je N vzporednih klicev lahko odgovore vrnilo v drugem vrstnem redu.
        var vsi = v.every(function (x) { return koren.jePriljubljenaPot(x.pot) })
        koren.klic("priljubljenoPreklopi", ["datoteke", v.map(function (x) { return { pot: x.pot, ime: x.ime, mapa: !!x.mapa } }), !vsi], function (p) {
            koren.nastaviPriljubljeno(p)
            koren.obvesti(koren.t(vsi ? "odstranjenoPriljubljeno" : "dodanoPriljubljeno", { ime: panel.steviloElementov(v.length) }))
        }, function () { koren.obvesti(koren.t("niUspelo")) })
    }
    // Preslednica ali »Predogled«: datoteke tega racunalnika v tem pogledu (puscici levo/desno se premikata po njih).
    function predogledZa(e) {
        if (!e || e.mapa || !e.pot || !linux || !jeLokalniPogled()) return false
        var d = prikazani.filter(function (x) { return !x.mapa && x.pot })
        predogled.odpri(d, Math.max(0, d.indexOf(e)))
        return true
    }
    // Vlecenje: vse izbrane, ce uporabnik vlece izbrano vrstico, sicer samo to (standardni seznam naslovov datotek).
    function potiZaVlecenje(e) {
        return (jeIzbran(e) && steviloIzbranih > 1 ? izbraniVnosi() : [e])
            .filter(function (x) { return x && x.pot }).map(function (x) { return x.pot })
    }
    function naslovi(e) { return potiZaVlecenje(e).map(function (p) { return Most ? Most.datotekaUrl(p) : "" }).join("\r\n") + "\r\n" }
    // Desni klik ali tipka Meni: meni vec izbranih, ce je vrstica med njimi, sicer meni vrstice. Pred menijem Safeer OS
    // pove, ali je kaksna naprava za posiljanje in v katere oblike se izbrano da pretvoriti - vnos, ki ne bi deloval,
    // se ne pokaze (lastnik, 15. 10. 2026: »nimamo nedelujocih ikon«).
    property var napraveZaPos: []
    readonly property int vMeniju: 3     // toliko naprav meni pokaze neposredno (»Poslji na »Tablica««)
    // Vnos »Poslji na »<naprava>««: i-ta naprava iz napraveZaPos; brez nje vnosa ni (nic nedelujocega v meniju).
    component VnosPoslji: MeniVnos {
        property int i: 0
        property bool vidno: false
        property var paket: null          // vnos datoteke {ime, pot} ali {ime, poti}
        readonly property var cilj: panel.napraveZaPos.length > i ? panel.napraveZaPos[i] : null
        text: cilj ? koren.t("posljiNa", { naprava: cilj.ime }) : ""
        visible: vidno && !!cilj && !!paket
        onTriggered: if (cilj && paket) panel.posljiNapravi(cilj, paket)
    }
    property var ciljiPretvorbe: []
    property bool tvMozna: false         // »Pretvori za televizor«: Control + ffmpeg ali naprava, ki zna (pretvorbaZaTvMozna)
    property bool shrambaMozna: false    // »Shrani na napravo«: naprava v Linku, ki shrani (isti odgovor, »shramba«)
    function meniVrstice(e, kje, x, y) {
        var vec = !!e && jeIzbran(e) && steviloIzbranih > 1
        var vsi_ = (vec ? izbraniVnosi() : (e ? [e] : [])).filter(function (d) { return d && d.pot })
        var dat = vsi_.filter(function (d) { return !d.mapa })
        var ostane = 1, cilji = null, st = ++zahtevaMenija
        var pokazi = function () {
            if (--ostane || st !== panel.zahtevaMenija) return
            panel.ciljiPretvorbe = cilji || []
            if (vec) { meniVec.pokazi(kje, x, y); return }
            meni.e = e
            if (kje) meni.popup(kje, x, y); else meni.popup()
        }
        napraveZaPos = []; ciljiPretvorbe = []; tvMozna = false; shrambaMozna = false
        if (linux && jeLokalniPogled() && vsi_.length) {
            ostane++
            koren.klic("pretvorbaZaTvMozna", [], function (r) {
                if (st === panel.zahtevaMenija) { panel.tvMozna = !!(r && r.ok); panel.shrambaMozna = !!(r && r.shramba) }
                pokazi()
            }, pokazi)
        }
        if (jeLokalniPogled() && vsi_.length) {
            // Datoteke in mape (mapa gre cela); zadnja uporabljena naprava je prva (safeer_os.naprave_za_posiljanje).
            ostane++
            koren.klic("napraveZaPosiljanje", [], function (n) {
                if (st === panel.zahtevaMenija) panel.napraveZaPos = (n || []).filter(function (x) { return x && x.id })
                pokazi()
            }, pokazi)
        }
        if (jeLokalniPogled() && dat.length) {
            if (dat.length <= 50) dat.forEach(function (d) {
                ostane++
                koren.klic("pretvorbaMoznosti", [d.pot], function (m) {
                    var c = m && m.orodje ? (m.cilji || []) : []
                    cilji = cilji === null ? c.slice() : cilji.filter(function (x) { return c.indexOf(x) >= 0 })
                    pokazi()
                }, function () { cilji = []; pokazi() })
            })
        }
        pokazi()
    }
    property int zahtevaMenija: 0
    function izprazniSmeti() {
        // Linux: trajni izbris potrdi sistemsko okno Safeer OS (stran ga ne more preskociti) - brez drugega vprasanja tu.
        if (linux) {
            koren.klic("izprazniSmeti", [], function (r) {
                if (r && r.potrjeno) koren.obvesti(koren.t("smetiIzpraznjene"))
                panel.nalozi(true)
            }, function () { koren.obvesti(koren.t("niUspelo")) })
            return
        }
        potrdi.open()
    }
    function novo(o) {
        o.kam = o.kam || kamNovo()
        oknoNovo.odpri(o)
    }
    // Meni vrstice i (kot tipka Meni na izbrani vrstici); uporabljajo ga tudi preizkusi.
    function meniZa(i) {
        seznam.currentIndex = i; seznam.forceActiveFocus()
        var e = prikazani[i] || null
        if (e && !jeIzbran(e)) izberiSamo(i)
        if (e) meniVrstice(e, seznam.currentItem, 40, seznam.currentItem ? seznam.currentItem.height : 0)
    }
    function meniPraznega() { meniOzadja.popup(seznam, 40, 30) }
    function meniPogonaZa(n) { meniPogona.n = n; meniPogona.popup(viriSeznam, 20, viriSeznam.height / 2) }
    function lastnostiZa(pot) { lastnosti.pokazi(pot) }
    function prazno() {
        if (stanje === "napaka") return vir.vrsta === "najvecje" ? koren.t("niUspelo") : koren.t("niOdgovorila")
        if (stanje === "neDeli") return koren.t("neDeli")
        return vir.vrsta === "smeti" ? koren.t("kosPrazen") : vir.vrsta === "nedavno" ? koren.t("niNedavnih")
             : vir.vrsta === "priljubljeno" ? koren.t("niPriljubljenih")
             : vir.vrsta === "najvecje" ? koren.t("niVelikih") : koren.t("prazno")
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
                id: izbiraNaprave
                Layout.fillWidth: true; zmoznost: "datoteke"; naprave: koren.naprave
                onIzbrana: function (id, ime) { panel.izberiNapravo(id, ime) }
            }
            ListView {
                id: viriSeznam
                objectName: "viriDatotek"
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.topMargin: 6
                clip: true; model: panel.viri; boundsBehavior: Flickable.StopAtBounds
                // Tipkovnica in daljinec TV (puscice): gor/dol preskoci naslove skupin, Enter ali preslednica odpre vir,
                // tipka Meni (Shift+F10) na pogonu ponudi »Izvrzi«.
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
                Keys.onPressed: function (d) {
                    var m = panel.viri[currentIndex]
                    if (m && m.pogon && m.pogon.naprava && (d.key === Qt.Key_Menu || (d.key === Qt.Key_F10 && (d.modifiers & Qt.ShiftModifier)))) {
                        meniPogona.n = m.pogon; meniPogona.popup(currentItem, 20, currentItem ? currentItem.height : 0); d.accepted = true
                    }
                }
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
                        color: spust.containsDrag ? koren.poudarekA(0.3) : izbran ? koren.poudarekA(0.18) : (mv.containsMouse ? koren.prekriv(0.08) : "transparent")
                        border.width: (viriSeznam.activeFocus && index === viriSeznam.currentIndex) || spust.containsDrag ? 2 : 0
                        border.color: koren.paleta.fokus
                        Accessible.role: Accessible.ListItem; Accessible.name: modelData.oznaka || ""
                        Behavior on color { enabled: koren.gibanje; ColorAnimation { duration: 120 } }
                        Text { text: modelData.oznaka || ""; color: parent.izbran ? Qt.lighter(koren.paleta.poudarek, 1.35) : koren.paleta.besedilo; font.pixelSize: koren.px(13); elide: Text.ElideRight
                               width: parent.width - 16; x: 10; anchors.verticalCenter: parent.verticalCenter }
                        // Spust na mapo ali pogon v stranski vrstici (kot ciljSpusta na delovni povrsini).
                        DropArea {
                            id: spust; anchors.fill: parent
                            enabled: !!modelData.vir && modelData.vir.vrsta === "lokalno"
                            onEntered: function (d) { if (!panel.lahkoSpusti(d, modelData.vir.pot)) d.accepted = false }
                            onDropped: function (d) { panel.spusti(d, modelData.vir.pot) }
                        }
                        MouseArea { id: mv; anchors.fill: parent; hoverEnabled: true; cursorShape: Qt.PointingHandCursor
                                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                                    onClicked: function (m) {
                                        viriSeznam.currentIndex = index
                                        if (m.button === Qt.RightButton) {
                                            if (modelData.pogon && modelData.pogon.naprava) { meniPogona.n = modelData.pogon; meniPogona.popup() }
                                            return
                                        }
                                        viriSeznam.izberiVir(index)
                                    } }
                        ToolTip.visible: mv.containsMouse && !!modelData.pogon && !!modelData.pogon.velikost
                        ToolTip.delay: 600
                        ToolTip.text: modelData.pogon && modelData.pogon.velikost
                            ? koren.t("prostoNa", { prosto: koren.velikost(modelData.pogon.prosto) || "0", skupaj: koren.velikost(modelData.pogon.velikost) }) : ""
                    }
                }
            }
        }
        Rectangle { Layout.fillHeight: true; width: 1; color: koren.prekriv(0.08) }
        // ---------------- vsebina
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 8
            // Malo prostora na disku (prostorDiska): opozorilo z bliznjico na Najvecje datoteke.
            Rectangle {
                objectName: "opozoriloProstora"
                visible: panel.linux && !!panel.prostor.malo && panel.naprava === ""
                Layout.fillWidth: true; implicitHeight: vrsticaProstora.implicitHeight + 12; radius: 10
                color: "transparent"; border.color: koren.paleta.opozorilo || koren.paleta.poudarek
                Accessible.role: Accessible.AlertMessage; Accessible.name: napisProstora.text
                Rectangle { anchors.fill: parent; radius: 10; color: koren.paleta.opozorilo || koren.paleta.poudarek; opacity: 0.14 }
                ColumnLayout {
                    id: vrsticaProstora; anchors.fill: parent; anchors.margins: 6; anchors.leftMargin: 10; spacing: 6
                    Text { id: napisProstora; Layout.fillWidth: true; wrapMode: Text.WordWrap; color: koren.paleta.besedilo; font.pixelSize: koren.px(12)
                           text: koren.t("maloProstora", { prosto: koren.velikost(panel.prostor.prosto) || "0 B" }) }
                    Gumb { Layout.alignment: Qt.AlignRight; besedilo: koren.t("pokaziNajvecje"); visible: panel.vir.vrsta !== "najvecje"
                           onKlik: panel.odpri({ vrsta: "najvecje", pot: "@najvecje" }) }
                }
            }
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
                        : panel.vir.vrsta === "lokalno" ? koren.kratkaPot(panel.vir.pot) : panel.vir.vrsta === "smeti" ? koren.t("smeti")
                        : panel.vir.vrsta === "najvecje" ? koren.t("najvecje") : panel.vir.vrsta === "priljubljeno" ? koren.t("priljubljeno")
                        : koren.t("nedavno")
                }
                Text {
                    objectName: "steviloIzbranih"
                    visible: panel.steviloIzbranih > 1
                    text: koren.t("izbranoN", { n: panel.steviloIzbranih }); color: koren.paleta.poudarek; font.pixelSize: koren.px(12)
                    Accessible.role: Accessible.StaticText; Accessible.name: text
                }
                Gumb { besedilo: koren.t("izprazni"); visible: panel.vir.vrsta === "smeti" && panel.elementi.length > 0; onKlik: panel.izprazniSmeti() }
                // Nova mapa ali datoteka (prazna, besedilo, dokument … ali predloga): meni kot »Novo« na delovni povrsini.
                Gumb { id: gumbNovo; objectName: "gumbNovo"; besedilo: "+ " + koren.t("novo"); visible: panel.vir.vrsta === "lokalno" && panel.linux
                       onKlik: meniNovo.popup(gumbNovo, 0, gumbNovo.height + 4) }
                Gumb { besedilo: "+ " + koren.t("novaMapa"); visible: panel.vir.vrsta === "lokalno" && !panel.linux
                       onKlik: koren.klic("novaMapa", [panel.vir.pot, koren.t("novaMapa")], function (r) {
                           if (r && r.ok) { panel.nalozi(true); panel.novo({ nacin: "preimenuj", ime: r.ime, pot: r.pot, mapa: true }) } else koren.obvesti(koren.t("niUspelo")) }) }
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
                objectName: "seznamDatotek"
                Layout.fillWidth: true; Layout.fillHeight: true
                // Tipkovnica (AGENTS: dostopnost): puscice, Enter odpre, Delete v Smeti, F2 preimenuj, Alt+Enter Lastnosti,
                // Ctrl+C/X/V kopiraj, izrezi, prilepi, Ctrl+Z razveljavi, tipka Meni/Shift+F10, preslednica predogled,
                // Ctrl+D priljubljeno, Shift+puscice/Home/End obseg, Ctrl+A vse, Ctrl+preslednica izbira, Escape ena.
                activeFocusOnTab: true; keyNavigationEnabled: true; currentIndex: -1
                Accessible.role: Accessible.List; Accessible.name: koren.t("datoteke")
                onCountChanged: if (currentIndex >= count) currentIndex = count - 1
                function izbran() { return currentIndex >= 0 && currentIndex < panel.prikazani.length ? panel.prikazani[currentIndex] : null }
                onActiveFocusChanged: if (activeFocus && currentIndex < 0 && count > 0) { currentIndex = 0; if (!panel.steviloIzbranih) panel.izberiSamo(0) }
                Keys.onReturnPressed: function (d) {
                    var e = izbran()
                    if (e && (d.modifiers & Qt.AltModifier) && panel.linux && panel.jeLokalniPogled()) lastnosti.pokazi(e.pot)
                    else if (e) panel.odpriElement(e)
                }
                Keys.onEnterPressed: { var e = izbran(); if (e) panel.odpriElement(e) }
                Keys.onLeftPressed: viriSeznam.forceActiveFocus()
                Keys.onDeletePressed: { var e = izbran(); if (e && panel.jeLokalniPogled()) panel.vKos(e) }
                Keys.onPressed: function (d) {
                    var e = izbran(), ctrl = d.modifiers & Qt.ControlModifier, shift = d.modifiers & Qt.ShiftModifier
                    var premik = d.key === Qt.Key_Down ? 1 : d.key === Qt.Key_Up ? -1 : d.key === Qt.Key_Home ? -count : d.key === Qt.Key_End ? count : 0
                    if (premik && !(d.modifiers & Qt.AltModifier)) {
                        if (count === 0) return
                        if (shift && panel.sidro < 0) panel.sidro = Math.max(0, currentIndex)
                        var n = Math.max(0, Math.min(count - 1, currentIndex + premik))
                        currentIndex = n; positionViewAtIndex(n, ListView.Contain)
                        if (shift) panel.izberiObseg(n); else if (!ctrl) panel.izberiSamo(n)   // Ctrl+puscica: fokus brez izbire
                        d.accepted = true; return
                    }
                    if (ctrl && d.key === Qt.Key_A) { panel.izberiVse(); d.accepted = true; return }
                    if (ctrl && d.key === Qt.Key_Space && currentIndex >= 0) { panel.preklopiIzbor(currentIndex); d.accepted = true; return }
                    if (d.key === Qt.Key_Escape && panel.steviloIzbranih > 1) { panel.izberiSamo(currentIndex); d.accepted = true; return }
                    if (d.key === Qt.Key_Space && !d.modifiers && e) { if (panel.predogledZa(e)) d.accepted = true; return }
                    if (ctrl && d.key === Qt.Key_D && e && panel.linux) { panel.preklopiPriljubljene(e); d.accepted = true; return }
                    if (ctrl && d.key === Qt.Key_Z && panel.linux) { panel.razveljavi(null); d.accepted = true; return }
                    if (ctrl && d.key === Qt.Key_V && panel.linux && panel.vir.vrsta === "lokalno") { panel.prilepi(null); d.accepted = true; return }
                    if ((d.key === Qt.Key_Menu || (d.key === Qt.Key_F10 && (d.modifiers & Qt.ShiftModifier))) && !e) {
                        meniOzadja.popup(seznam, 40, 30); d.accepted = true; return
                    }
                    if (!e) return
                    if (ctrl && (d.key === Qt.Key_C || d.key === Qt.Key_X) && panel.linux && panel.jeLokalniPogled()) { panel.vOdlozisce(e, d.key === Qt.Key_X); d.accepted = true }
                    else if (d.key === Qt.Key_F2 && panel.jeLokalniPogled()) { panel.novo({ nacin: "preimenuj", pot: e.pot, ime: e.ime, mapa: e.mapa }); d.accepted = true }
                    else if (d.key === Qt.Key_Menu || (d.key === Qt.Key_F10 && (d.modifiers & Qt.ShiftModifier))) {
                        var it = currentItem
                        panel.meniVrstice(e, it, 40, it ? it.height : 0); d.accepted = true
                    }
                }
                // Ozka plosca (aplikacija v manjsem oknu, 14. 10. 2026: pri 1080 px ime ni bilo vidno): stolpca
                // Spremenjeno in Velikost se umakneta imenu.
                readonly property bool ozko: width < 360
                readonly property bool zeloOzko: width < 260
                readonly property real stolpci: (zeloOzko ? 0 : koren.px(80)) + (ozko ? 0 : koren.px(110))
                clip: true; model: panel.prikazani; boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                // Desni klik na prazen del seznama: Prilepi, Razveljavi, Novo, Osvezi (meniNovo v delovna.js).
                MouseArea {
                    objectName: "ozadjeSeznama"
                    parent: seznam; anchors.fill: parent; z: -1
                    acceptedButtons: Qt.RightButton
                    onClicked: function (m) { meniOzadja.popup() }
                }
                // Spust v odprto mapo (iz drugega programa ali iz tega seznama).
                DropArea {
                    id: spustSeznam
                    parent: seznam; anchors.fill: parent; z: -2
                    enabled: panel.vir.vrsta === "lokalno"
                    onEntered: function (d) { if (!panel.lahkoSpusti(d, panel.vir.pot)) d.accepted = false }
                    onDropped: function (d) { panel.spusti(d, panel.vir.pot) }
                }
                Rectangle { parent: seznam; anchors.fill: parent; z: 5; visible: spustSeznam.containsDrag; color: "transparent"
                            radius: 10; border.width: 2; border.color: koren.paleta.fokus }
                header: Row {
                    height: 26; spacing: 0
                    Text { text: koren.t("ime"); color: Qt.darker(koren.paleta.medlo, 1.15); font.pixelSize: koren.px(11); width: seznam.width - seznam.stolpci }
                    Text { text: koren.t("velikost"); color: Qt.darker(koren.paleta.medlo, 1.15); font.pixelSize: koren.px(11); width: koren.px(80); visible: !seznam.zeloOzko }
                    Text { text: koren.t("spremenjeno"); color: Qt.darker(koren.paleta.medlo, 1.15); font.pixelSize: koren.px(11); width: koren.px(110); visible: !seznam.ozko }
                }
                delegate: Rectangle {
                    id: vrstica
                    width: seznam.width; height: koren.px(34); radius: 8
                    readonly property bool izrezana: panel.odlozisce.rezi && panel.odlozisce.poti.indexOf(modelData.pot) >= 0
                    readonly property bool oznacena: !!panel.izbrane[panel.kljucVnosa(modelData)]
                    color: spustMapa.containsDrag ? koren.poudarekA(0.3) : oznacena ? koren.poudarekA(seznam.activeFocus ? 0.22 : 0.14)
                         : md.containsMouse ? koren.prekriv(0.08) : "transparent"
                    border.width: index === seznam.currentIndex && seznam.activeFocus ? 2 : 0; border.color: koren.paleta.fokus
                    opacity: izrezana ? 0.55 : 1
                    // V Priljubljenem ni stolpca z mapo: kje je datoteka, pove namig.
                    ToolTip.visible: md.containsMouse && panel.vir.vrsta === "priljubljeno"; ToolTip.delay: 600
                    ToolTip.text: panel.vir.vrsta === "priljubljeno" ? koren.kratkaPot(modelData.pot) : ""
                    Accessible.role: Accessible.ListItem; Accessible.selectable: true; Accessible.selected: oznacena
                    Accessible.name: modelData.ime
                    Behavior on color { enabled: koren.gibanje; ColorAnimation { duration: 100 } }
                    Row {
                        anchors.verticalCenter: parent.verticalCenter; x: 6; spacing: 0
                        Row {
                            width: seznam.width - seznam.stolpci - 6; spacing: 8
                            Rectangle {
                                width: koren.px(22); height: koren.px(22); radius: 6; anchors.verticalCenter: parent.verticalCenter
                                color: koren.barvaVrste(modelData.mapa ? "mapa" : modelData.vrsta)
                                Text { anchors.centerIn: parent; color: koren.prekriv(1); font.pixelSize: koren.px(10); font.bold: true
                                       visible: slicica.status !== Image.Ready
                                       text: modelData.mapa ? "▣" : (modelData.ime.split(".").pop() || "?").slice(0, 3).toUpperCase() }
                                Image {
                                    id: slicica; anchors.fill: parent; fillMode: Image.PreserveAspectCrop; asynchronous: true
                                    sourceSize: Qt.size(48, 48); source: panel.slicice[modelData.pot] || ""
                                }
                            }
                            Text { text: modelData.ime
                                   color: koren.paleta.besedilo; font.pixelSize: koren.px(13); elide: Text.ElideRight
                                   width: parent.width - koren.px(22) - 10; anchors.verticalCenter: parent.verticalCenter }
                        }
                        Text { text: modelData.mapa ? "" : koren.velikost(modelData.velikost); color: koren.paleta.medlo; font.pixelSize: koren.px(12); width: koren.px(80)
                               visible: !seznam.zeloOzko; anchors.verticalCenter: parent.verticalCenter }
                        Text { text: koren.cas(modelData.spremenjeno || modelData.izbrisano); color: koren.paleta.medlo; font.pixelSize: koren.px(12); width: koren.px(110)
                               visible: !seznam.ozko; anchors.verticalCenter: parent.verticalCenter }
                    }
                    // Vlecenje v drug program (Nemo, brskalnik, posta): samo standardni seznam naslovov datotek - ciljni
                    // program kopira (s Shift premakne). Kot zacniVlecenje na delovni povrsini; mi ne brisemo nicesar.
                    Item {
                        id: vlecen
                        width: 1; height: 1
                        Drag.dragType: Drag.Automatic
                        Drag.supportedActions: Qt.CopyAction | Qt.MoveAction
                        Drag.proposedAction: Qt.CopyAction
                        Drag.mimeData: ({ "text/uri-list": panel.naslovi(modelData) })
                        Drag.active: md.drag.active && panel.linux && panel.jeLokalniPogled() && !!modelData.pot
                        Drag.onDragStarted: panel.vlecem = panel.potiZaVlecenje(modelData)
                        Drag.onDragFinished: function (dejanje) {
                            panel.vlecem = []; vlecen.x = 0; vlecen.y = 0
                            if (dejanje === Qt.MoveAction) panel.nalozi(true)
                        }
                    }
                    // Spust na mapo v seznamu = v to mapo.
                    DropArea {
                        id: spustMapa; anchors.fill: parent
                        enabled: !!modelData.mapa && panel.vir.vrsta === "lokalno"
                        onEntered: function (d) { if (!panel.lahkoSpusti(d, modelData.pot)) d.accepted = false }
                        onDropped: function (d) { panel.spusti(d, modelData.pot) }
                    }
                    MouseArea {
                        id: md; anchors.fill: parent; hoverEnabled: true; acceptedButtons: Qt.LeftButton | Qt.RightButton
                        drag.target: panel.linux && panel.jeLokalniPogled() ? vlecen : null
                        drag.threshold: 12
                        onDoubleClicked: panel.odpriElement(modelData)
                        onClicked: function (m) {
                            seznam.currentIndex = index; seznam.forceActiveFocus()
                            if (m.button === Qt.RightButton) {
                                if (!panel.jeIzbran(modelData)) panel.izberiSamo(index)
                                panel.meniVrstice(modelData, null)
                                return
                            }
                            if (m.modifiers & Qt.ShiftModifier) panel.izberiObseg(index)
                            else if (m.modifiers & Qt.ControlModifier) panel.preklopiIzbor(index)
                            else panel.izberiSamo(index)
                        }
                    }
                }
                Text {
                    // Daljse besedilo (npr. namig v Priljubljeno) se prelomi znotraj seznama, ne gre cez rob
                    // (posnetek s testnega PC 15. 10. 2026).
                    anchors.centerIn: parent; visible: seznam.count === 0
                    width: Math.max(0, parent.width - koren.px(32))
                    wrapMode: Text.Wrap; horizontalAlignment: Text.AlignHCenter
                    text: panel.prazno(); color: koren.paleta.medlo; font.pixelSize: koren.px(13)
                }
            }
        }
    }

    // Meni v slogu namizja (kot meni ozadja v Namizje.qml), ne sivi privzeti meni Qt. Vrstni red kot meniDatoteke v delovna.js.
    Meni {
        id: meni
        objectName: "meniDatoteke"
        property var e: null
        readonly property bool lok: panel.jeLokalniPogled() && !!meni.e
        readonly property bool datoteka: meni.lok && !!meni.e && !meni.e.mapa
        MeniVnos { text: koren.t("odpri"); visible: panel.vir.vrsta !== "smeti"; onTriggered: panel.odpriElement(meni.e) }
        MeniVnos { text: koren.t("predogled"); objectName: "vnosPredogled"; visible: meni.datoteka && panel.linux; onTriggered: panel.predogledZa(meni.e) }
        MeniVnos { text: koren.t("nadaljujTukaj"); objectName: "vnosNadaljuj"
                   visible: panel.vir.vrsta === "naprava" && !!meni.e && !meni.e.mapa && !!panel.streznik && !!panel.streznik.base_url
                   onTriggered: panel.odpriTukaj(meni.e) }
        MeniVnos { text: koren.t("odpriSProgramom", { naprava: panel.imeNaprave })
                   visible: panel.vir.vrsta === "naprava" && !!meni.e && !meni.e.mapa
                   onTriggered: panel.odpriSProgramomNaprave(meni.e) }
        // Kot Datoteke na prejsnji delovni povrsini (delovna.js): Odpri z … in Poslji na napravo … (14. 10. 2026).
        MeniVnos { text: koren.t("odpriZ"); visible: meni.datoteka; onTriggered: izbirnik.odpriZ(meni.e) }
        MeniVnos { text: koren.t("pokazi"); visible: meni.lok; onTriggered: koren.klic("pokaziVMapi", [meni.e.pot]) }
        // Priljubljeno (Ctrl+D).
        MeniVnos { text: koren.t(meni.e && koren.jePriljubljenaPot(meni.e.pot) ? "odstraniPriljubljeno" : "dodajPriljubljeno"); objectName: "vnosPriljubljeno"
                   visible: panel.linux && !!meni.e && !!meni.e.pot && meni.lok
                   onTriggered: panel.preklopiPriljubljene(meni.e) }
        MeniCrta { visible: meni.lok && panel.linux }
        MeniVnos { text: koren.t("kopiraj"); visible: meni.lok && panel.linux; onTriggered: panel.vOdlozisce(meni.e, false) }
        MeniVnos { text: koren.t("izrezi"); visible: meni.lok && panel.linux; onTriggered: panel.vOdlozisce(meni.e, true) }
        MeniVnos { text: koren.t(meni.e && meni.e.mapa ? "prilepiV" : "prilepi"); objectName: "vnosPrilepi"
                   visible: meni.lok && panel.linux && panel.odlozisce.poti.length > 0 && (panel.vir.vrsta === "lokalno" || !!(meni.e && meni.e.mapa))
                   onTriggered: panel.prilepi(meni.e && meni.e.mapa ? meni.e.pot : null) }
        MeniVnos { text: koren.t("preimenuj"); visible: meni.lok; onTriggered: panel.novo({ nacin: "preimenuj", pot: meni.e.pot, ime: meni.e.ime, mapa: meni.e.mapa }) }
        MeniVnos { text: koren.t("vKos"); visible: meni.lok; onTriggered: panel.vKos(meni.e) }
        MeniVnos { text: koren.t("lastnosti"); objectName: "vnosLastnosti"; visible: meni.lok && panel.linux; onTriggered: lastnosti.pokazi(meni.e.pot) }
        // »Poslji na »Tablica««: prve naprave neposredno (en klik, zadnja uporabljena prva), pri vec se izbira (18. 10. 2026).
        VnosPoslji { i: 0; objectName: "vnosPoslji"; vidno: meni.lok; paket: meni.e }
        VnosPoslji { i: 1; objectName: "vnosPoslji1"; vidno: meni.lok; paket: meni.e }
        VnosPoslji { i: 2; objectName: "vnosPoslji2"; vidno: meni.lok; paket: meni.e }
        MeniVnos { text: koren.t("posljiNaNapravo"); objectName: "vnosPosljiIzbira"; visible: meni.lok && panel.napraveZaPos.length > panel.vMeniju
                   onTriggered: izbirnik.poslji(meni.e) }
        MeniVnos { text: koren.t("shraniNaNapravo"); objectName: "vnosShrani"; visible: meni.datoteka && panel.linux && panel.shrambaMozna; onTriggered: shrani.zacni(meni.e) }
        MeniVnos { text: koren.t("pretvoriV"); objectName: "vnosPretvori"; visible: meni.datoteka && panel.ciljiPretvorbe.length > 0; onTriggered: izbirnik.pretvori(meni.e) }
        // Krog solidarnosti (Safeer Control): video ali vsi videi v mapi za televizor na napravi z najboljsim kodirnikom.
        // Samo, ko pretvorba ta trenutek deluje (Control + ffmpeg ali naprava, ki zna) - sicer bi vnos koncal z napako.
        MeniVnos { text: koren.t("pretvori"); objectName: "vnosPretvoriTv"; visible: meni.datoteka && panel.linux && meni.e.vrsta === "video" && panel.tvMozna
                   onTriggered: pretvoriTv.zacni(meni.e, false) }
        MeniVnos { text: koren.t("pretvoriMapo"); objectName: "vnosPretvoriMapo"; visible: meni.lok && panel.linux && !!(meni.e && meni.e.mapa) && panel.tvMozna
                   onTriggered: pretvoriTv.zacni(meni.e, true) }
        MeniVnos { text: koren.t("obnovi"); visible: panel.vir.vrsta === "smeti"
                   onTriggered: koren.klic("obnoviIzSmeti", [meni.e.id], function (r) {
                       if (r && r.ok) { panel.nalozi(true); koren.obvesti(koren.t("obnovljeno", { ime: meni.e.ime })) } else koren.obvesti(koren.t("niUspelo")) }) }
        MeniVnos { text: koren.t("izprazniSmeti"); visible: panel.vir.vrsta === "smeti"; onTriggered: panel.izprazniSmeti() }
    }
    // Vec izbranih (meniVec v delovna.js): samo dejanja, ki jih Safeer OS zna za vec datotek naenkrat.
    Meni {
        id: meniVec
        objectName: "meniVec"
        property var v: []
        readonly property bool lok: panel.linux && panel.jeLokalniPogled()
        readonly property var dat: meniVec.v.filter(function (x) { return !x.mapa })
        readonly property string n: panel.steviloElementov(meniVec.v.length)
        // Vse izbrano (tudi mape) za »Poslji na …«.
        readonly property var paket: meniVec.v.length ? { poti: meniVec.v.map(function (x) { return x.pot }), ime: meniVec.n } : null
        readonly property bool vsiPriljubljeni: meniVec.v.length > 0 && meniVec.v.every(function (x) { return koren.jePriljubljenaPot(x.pot) })
        function pokazi(kje, x, y) {
            v = panel.izbraniVnosi()
            if (kje) popup(kje, x, y); else popup()
        }
        MeniVnos { text: koren.t("izbranoN", { n: meniVec.v.length }); enabled: false }
        MeniCrta {}
        MeniVnos { text: koren.t("kopirajN", { n: meniVec.n }); objectName: "vnosKopirajVec"; visible: meniVec.lok; onTriggered: panel.vOdloziscePoti(meniVec.v, false) }
        MeniVnos { text: koren.t("izreziN", { n: meniVec.n }); visible: meniVec.lok; onTriggered: panel.vOdloziscePoti(meniVec.v, true) }
        MeniVnos { text: koren.t("prilepi"); visible: meniVec.lok && panel.vir.vrsta === "lokalno" && panel.odlozisce.poti.length > 0; onTriggered: panel.prilepi(null) }
        MeniVnos { text: koren.t("vSmetiN", { n: meniVec.n }); objectName: "vnosSmetiVec"; visible: meniVec.lok; onTriggered: panel.vKosVec(meniVec.v) }
        MeniVnos { text: koren.t(meniVec.vsiPriljubljeni ? "odstraniPriljubljeno" : "dodajPriljubljeno"); objectName: "vnosPriljubljenoVec"
                   visible: meniVec.lok; onTriggered: panel.preklopiPriljubljeneVec(meniVec.v) }
        VnosPoslji { i: 0; objectName: "vnosPosljiVec"; vidno: meniVec.lok; paket: meniVec.paket }
        VnosPoslji { i: 1; objectName: "vnosPosljiVec1"; vidno: meniVec.lok; paket: meniVec.paket }
        VnosPoslji { i: 2; objectName: "vnosPosljiVec2"; vidno: meniVec.lok; paket: meniVec.paket }
        MeniVnos { text: koren.t("posljiNaNapravo"); objectName: "vnosPosljiVecIzbira"
                   visible: meniVec.lok && meniVec.v.length > 0 && panel.napraveZaPos.length > panel.vMeniju
                   onTriggered: izbirnik.posljiVec(meniVec.v) }
        MeniVnos { text: koren.t("pretvoriV"); objectName: "vnosPretvoriVec"; visible: meniVec.lok && meniVec.dat.length > 1 && meniVec.dat.length === meniVec.v.length && panel.ciljiPretvorbe.length > 0
                   onTriggered: izbirnik.pretvoriVec(meniVec.dat) }
        // Krog solidarnosti: vsi izbrani videi (in videi v izbranih mapah) za televizor - naprave si delo razdelijo.
        MeniVnos { text: koren.t("pretvori"); objectName: "vnosPretvoriTvVec"
                   visible: meniVec.lok && panel.tvMozna && meniVec.v.every(function (x) { return x.mapa || x.vrsta === "video" })
                   onTriggered: pretvoriTv.zacni({ ime: meniVec.n }, true, meniVec.v.map(function (x) { return x.pot })) }
        MeniVnos { text: koren.t("obnoviN", { n: meniVec.n }); visible: panel.vir.vrsta === "smeti"; onTriggered: panel.obnoviVec(meniVec.v) }
        MeniCrta {}
        MeniVnos { text: koren.t("pocistiIzbiro"); onTriggered: panel.izberiSamo(seznam.currentIndex) }
    }
    Predogled {
        id: predogled
        onOdpriDatoteko: function (e) { panel.odpriElement(e) }
    }
    // Pogon (USB kljuc, zunanji disk): Odpri in varno Izvrzi (izvrziNosilec).
    Meni {
        id: meniPogona
        objectName: "meniPogona"
        property var n: null
        MeniVnos { text: koren.t("odpri"); onTriggered: panel.odpri({ vrsta: "lokalno", pot: meniPogona.n.pot }) }
        MeniVnos { text: koren.t("izvrzi"); objectName: "vnosIzvrzi"; enabled: panel.linux; onTriggered: panel.izvrzi(meniPogona.n) }
    }
    // Nova mapa, vrste datotek in predloge (postavkeNovo v delovna.js).
    Meni {
        id: meniNovo
        objectName: "meniNovo"
        MeniVnos { text: koren.t("novaMapa"); onTriggered: panel.novo({ nacin: "mapa" }) }
        MeniCrta {}
        MeniVnos { text: koren.t("vPrazna"); onTriggered: panel.novo({ nacin: "datoteka", vrsta: "prazna" }) }
        MeniVnos { text: koren.t("vBesedilo"); onTriggered: panel.novo({ nacin: "datoteka", vrsta: "besedilo" }) }
        MeniVnos { text: koren.t("vDokument"); onTriggered: panel.novo({ nacin: "datoteka", vrsta: "dokument" }) }
        MeniVnos { text: koren.t("vPreglednica"); onTriggered: panel.novo({ nacin: "datoteka", vrsta: "preglednica" }) }
        MeniVnos { text: koren.t("vPredstavitev"); onTriggered: panel.novo({ nacin: "datoteka", vrsta: "predstavitev" }) }
        Instantiator {
            model: panel.predloge
            delegate: MeniVnos { required property var modelData
                                 text: koren.t("vPredloga", { ime: modelData.ime })
                                 onTriggered: panel.novo({ nacin: "datoteka", vrsta: "predloga", predloga: modelData.pot, ime: modelData.ime }) }
            onObjectAdded: function (i, o) { meniNovo.insertItem(7 + i, o) }
            onObjectRemoved: function (i, o) { meniNovo.removeItem(o) }
        }
    }
    // Prazen del seznama (ali tipka Meni brez izbire).
    Meni {
        id: meniOzadja
        objectName: "meniOzadja"
        MeniVnos { text: koren.t("prilepi"); visible: panel.linux && panel.vir.vrsta === "lokalno" && panel.odlozisce.poti.length > 0; onTriggered: panel.prilepi(null) }
        MeniVnos { text: koren.t("razveljavi"); objectName: "vnosRazveljavi"; visible: panel.razveljavitve.length > 0; onTriggered: panel.razveljavi(null) }
        MeniVnos { text: koren.t("novo"); visible: panel.linux && panel.vir.vrsta === "lokalno"; onTriggered: meniNovo.popup() }
        MeniVnos { text: koren.t("izprazniSmeti"); visible: panel.vir.vrsta === "smeti" && panel.elementi.length > 0; onTriggered: panel.izprazniSmeti() }
        MeniVnos { text: koren.t("osvezi"); onTriggered: panel.nalozi(true) }
    }

    NovoIme {
        id: oknoNovo
        predloge: panel.predloge
        onKoncano: function (r, o) {
            var nova = r.pot || "", ime = nova.split("/").pop()
            if (o.nacin !== "preimenuj") panel.obvestiZRazveljavi(koren.t("ustvarjeno", { ime: ime }), panel.zapomni({ vrsta: "novo", pari: [["", nova]] }))
            else if (nova && nova !== o.pot) panel.obvestiZRazveljavi(koren.t("preimenovano", { ime: ime }), panel.zapomni({ vrsta: "preimenovanje", pari: [[o.pot, nova]] }))
            // Pokazemo mapo, kjer je nastalo (ce je bilo ustvarjeno drugje kot v odprti mapi).
            var mapa = nova.replace(/\/[^/]*$/, "") || "/"
            if (o.nacin !== "preimenuj" && !(panel.vir.vrsta === "lokalno" && panel.vir.pot === mapa)) panel.odpriLokalno(mapa)
            else panel.nalozi(true)
        }
    }
    Lastnosti { id: lastnosti }
    ShraniNaNapravo { id: shrani; onIzbrisano: { panel.nalozi(true); panel.preveriProstor() } }
    PretvoriZaTv { id: pretvoriTv; onSpremenjeno: panel.nalozi(true) }

    // Izbira programa (Odpri z …) ali naprave (Poslji na napravo …) za eno datoteko.
    Okno {
        id: izbirnik
        property string naslov: ""
        property var moznosti: []        // [{ ime, opis, ob }]
        property var drug: null          // »Drug program …« (vsi programi, ki sprejmejo datoteko)
        property bool vedno: false       // »Vedno s tem programom« (privzeti program za to vrsto v vsem namizju)
        width: 400
        function pokazi(n, m) { naslov = n; moznosti = m; drug = null; vedno = false; vednoPolje.checked = false; open() }
        // Kot odpriZ v delovna.js: programi, prijavljeni za to vrsto (privzeti prvi), »Drug program …« pokaze vse, kljukica
        // nastavi izbrani program za privzetega - v vsem namizju, ne samo v Safeer OS.
        function odpriZ(e) {
            koren.klic("programiZaDatoteko", [e.pot], function (r) {
                if (!r || !r.ok) { koren.obvesti(koren.t("niUspelo")); return }
                var izberi = function (x) {
                    return function () {
                        koren.klic("odpriZ", [[e.pot], x.id, izbirnik.vedno && vednoPolje.checked], function (o) {
                            if (!(o && o.ok)) koren.obvesti(koren.t("niUspelo"))
                            else if (o.privzet) koren.obvesti(koren.t("odslejZ", { ime: x.ime }))
                        })
                    }
                }
                var v = function (seznam) {
                    return seznam.map(function (x) { return { ime: x.ime, opis: x.privzet ? koren.t("privzetProgram") : "", ob: izberi(x) } })
                }
                pokazi(koren.t("odpriZ") + " · " + e.ime, v(r.programi || []))
                izbirnik.vedno = panel.linux && !!r.vrsta
                if (panel.linux) izbirnik.drug = function () {
                    var privzeti = (r.programi || []).filter(function (x) { return x.privzet })[0]
                    koren.klic("programiZaOdpiranje", [], function (vsi) {
                        izbirnik.drug = null
                        izbirnik.moznosti = v((vsi || []).map(function (x) {
                            return { id: String(x.id), ime: String(x.ime || x.id), privzet: !!privzeti && privzeti.id === x.id }
                        }))
                    }, function () { koren.obvesti(koren.t("niUspelo")) })
                }
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
        // Pretvori v … za vec datotek: oblike, ki jih znajo vse izbrane (pretvorbaMoznosti), vsaka v svojo novo datoteko.
        function pretvoriVec(v) {
            var ostane = v.length, cilji = null, brezOrodja = "", skupina = ""
            var ORODJA = { slika: "ImageMagick", zvok: "ffmpeg", besedilo: "LibreOffice", preglednica: "LibreOffice", predstavitev: "LibreOffice" }
            v.forEach(function (e) {
                koren.klic("pretvorbaMoznosti", [e.pot], function (m) {
                    m = m || {}
                    if (m.cilji && m.cilji.length && !m.orodje) brezOrodja = ORODJA[m.skupina] || "?"
                    var c = (m.cilji || [])
                    cilji = cilji === null ? c.slice() : cilji.filter(function (x) { return c.indexOf(x) >= 0 })
                    if (--ostane) return
                    if (brezOrodja) { koren.obvesti(koren.t("ptdNiOrodja", { orodje: brezOrodja })); return }
                    if (!cilji.length) { koren.obvesti(koren.t("ptdVecNiSkupne")); return }
                    izbirnik.pokazi(koren.t("pretvoriV") + " · " + panel.steviloElementov(v.length), cilji.map(function (c) {
                        return { ime: c.toUpperCase(), opis: "", ob: function () {
                            koren.obvesti(koren.t("ptdPretvarjam", { ime: panel.steviloElementov(v.length), cilj: c.toUpperCase() }))
                            v.forEach(function (e2) {
                                koren.klic("pretvoriDatoteko", [e2.pot, c], function (r) {
                                    if (!r || !r.ok) { koren.obvesti(koren.t("ptdNapaka")); return }
                                    pretvarjanje.dodaj(r.id)
                                }, function () { koren.obvesti(koren.t("ptdNapaka")) })
                            })
                        } }
                    }))
                }, function () { if (--ostane === 0) koren.obvesti(koren.t("ptdNapaka")) })
            })
        }
        function posljiVec(v) {
            koren.klic("napraveZaPosiljanje", [], function (n) {
                n = (n || []).filter(function (x) { return x && x.id })
                if (!n.length) { koren.obvesti(koren.t("posNiNaprav")); return }
                var paket = { poti: v.map(function (x) { return x.pot }), ime: panel.steviloElementov(v.length) }
                pokazi(koren.t("posljiNaNapravo") + " · " + paket.ime, n.map(function (x) {
                    return { ime: x.ime, opis: "", ob: function () { panel.posljiNapravi(x, paket) } }
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
            Text { visible: !izbirnik.moznosti.length; text: koren.t("niProgramaZaVrsto"); color: koren.paleta.medlo; font.pixelSize: koren.px(12) }
            Gumb { objectName: "drugProgram"; visible: !!izbirnik.drug; besedilo: koren.t("drugProgram"); onKlik: izbirnik.drug() }
            CheckBox {
                id: vednoPolje
                visible: izbirnik.vedno
                text: koren.t("vednoSTem"); font.pixelSize: koren.px(12)
                indicator: Rectangle {
                    implicitWidth: 18; implicitHeight: 18; y: (vednoPolje.height - height) / 2; radius: 4
                    color: vednoPolje.checked ? koren.paleta.poudarek : "transparent"
                    border.width: vednoPolje.activeFocus ? 2 : 1; border.color: vednoPolje.activeFocus ? koren.paleta.fokus : koren.crta(0.4)
                    Text { anchors.centerIn: parent; text: "✓"; visible: vednoPolje.checked; color: koren.paleta.poudarekTemna; font.pixelSize: koren.px(12); font.bold: true }
                }
                contentItem: Text { text: vednoPolje.text; leftPadding: vednoPolje.indicator.width + 8; color: koren.paleta.besedilo
                                    font: vednoPolje.font; verticalAlignment: Text.AlignVCenter }
            }
            Gumb { Layout.alignment: Qt.AlignRight; besedilo: koren.t("zapri"); onKlik: izbirnik.close() }
        }
    }

    // Datoteko odda Safeer Control (kot »Poslji datoteko« v njem); tu spremljamo napredek do konca.
    function posljiNapravi(naprava, e) {
        koren.obvesti(koren.t("posPosiljam", { naprava: naprava.ime, ime: e.ime }))
        koren.klic("posljiNapravi", [naprava.id, e.poti || [e.pot]], function (r) {
            if (!r || !r.ok) { koren.obvesti(koren.t("posNapaka", { naprava: naprava.ime })); return }
            if (r.stanje === "posiljam" || r.stanje === "caka") posiljanje.dodaj(r.id, naprava, e.ime)
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
                // Naprave ni: posiljka pocaka in nadaljuje sama (core/link_posiljanje) - povemo enkrat.
                if (r.stanje === "caka" && !o.caka) { o.caka = true; koren.obvesti(koren.t("posCaka", { naprava: o.naprava.ime })) }
                if (r.stanje === "posiljam" || r.stanje === "caka") return
                posiljanje.koncaj(id)
                koren.obvesti(r.stanje === "poslano" ? koren.t("posPoslano", { naprava: o.naprava.ime, ime: o.ime })
                                                     : koren.t("posNapaka", { naprava: o.naprava.ime }))
            })
        })
    }

    // Windows: Koš izprazni sele po tem vprasanju (na Linuxu vprasa sistemsko okno Safeer OS).
    Okno {
        id: potrdi
        width: 400
        ColumnLayout {
            anchors.fill: parent; spacing: 14
            Text { text: koren.t("izprazniVpr"); color: koren.paleta.besedilo; font.pixelSize: koren.px(14); wrapMode: Text.WordWrap; Layout.fillWidth: true }
            RowLayout { Layout.alignment: Qt.AlignRight; spacing: 8
                Gumb { besedilo: koren.t("preklici"); onKlik: potrdi.close() }
                Gumb { besedilo: koren.t("izprazni"); poudarjen: true
                       onKlik: { koren.klic("izprazniSmeti", [], function () { panel.nalozi(true) }); potrdi.close() } } }
        }
    }
    // Zadetek »naprava« v iskanju na namizju: pokaze to napravo v tej plosci.
    function pokaziNapravo(id) { return izbiraNaprave.izberiId(id) }
}
