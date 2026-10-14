"""Medijski center - jasen, miren videz (lastnik, 14. 10. 2026: »mora izgledati res profesionalno, uporabniki ne
smejo biti zmedeni«). En glavni gumb Dodaj z menijem, brez podvojenih vstopov, desni stolpec le med predvajanjem,
samodejno nalaganje kataloga namesto gumbov za strani, zvrsti le tam, kjer res filtrirajo. Izris je bil preverjen
z WebKitGTK 6.0 pod xvfb (1280, 1440 in 1920 px, nacin za kavc)."""
import os
import re
import threading
import unittest

from core import os_media

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JEZIKI = ("sl", "en", "de", "es", "fr", "it")


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class Glava(unittest.TestCase):
    def setUp(self):
        self.html = _beri("assets", "os", "index.html")
        self.js = _beri("assets", "os", "os.js")
        self.glava = self.html.split('<div class="media-glava-dejanja">', 1)[1].split('<div class="media-orodna">', 1)[0]

    def test_en_glavni_gumb_dodaj(self):
        self.assertEqual(self.glava.count('class="gumb glavni"'), 1)
        self.assertIn('id="medijiDodajMeniGumb" type="button" aria-haspopup="menu" aria-expanded="false"', self.glava)
        # Ob njem samo dve kompaktni dejanji z namigom in dostopnim imenom (ikona brez besedila).
        self.assertIn('class="media-ikona-gumb" id="medijiPredaja" type="button" data-naslov="mediaPredaja"', self.glava)
        self.assertIn('class="media-ikona-gumb" id="medijiKavc" type="button" aria-pressed="false"', self.glava)
        self.assertIn('if (!el.textContent.trim()) el.setAttribute("aria-label", el.title);', self.js)

    def test_meni_ima_vse_nacine_dodajanja(self):
        meni = self.glava.split('id="medijiDodajMeni" role="menu" hidden>', 1)[1].split("</div>", 1)[0]
        for id_ in ("medijiMapa", "medijiLokalno", "medijiTok", "medijiDodaj", "medijiMagnet", "medijiDodatki"):
            self.assertIn('role="menuitem" type="button" id="%s"' % id_, meni)
        self.assertEqual(meni.count('role="menuitem"'), 6)
        # Tipkovnica: gor/dol, Home/End, Escape zapre samo meni in vrne izbor na gumb.
        for niz in ('e.key === "ArrowDown" || e.key === "ArrowUp"', 'e.key === "Home" || e.key === "End"',
                    'if (e.key === "Escape" && zapriMeniDodaj(true)) { e.preventDefault(); e.stopImmediatePropagation(); }'):
            self.assertIn(niz, self.js)
        self.assertIn('ob("medijiDodatki", "click", function () { zapriMeniDodaj(false); odpriKatViri(); });', self.js)

    def test_brez_podvojenih_vstopov(self):
        # Dodatki Stremio so v oknu »Dodatki in viri« (gumb katPoisciDodatke), ne se enkrat v glavi.
        self.assertNotIn("medijiStremio", self.html + self.js)
        self.assertIn('id="katPoisciDodatke"', self.html)
        # »Dodatki in viri« ni vec v vrstici kataloga - samo v meniju Dodaj.
        self.assertNotIn('id="katDodatki"', self.html)
        self.assertEqual(self.html.count('data-t="katDodatki"'), 2)       # predmet menija in naslov okna

    def test_besedila_v_vseh_jezikih(self):
        bes = _beri("assets", "os", "besedila.js")
        for kljuc in ("mediaDodaj", "mediaDodajMapaOpis", "mediaDodajLokalnoOpis", "mediaDodajTokOpis", "mediaDodajSpletOpis",
                      "mediaDodajMagnetOpis", "mediaDodajDodatkiOpis", "katZvrsti", "katNalagamVec", "katNiNalozeno",
                      "katPoskusiZnova"):
            for j in JEZIKI:
                self.assertIn('BESEDILA_OS.%s, {"mediaDodaj"' % j, bes)
            self.assertEqual(bes.count('"%s":' % kljuc), 6, kljuc)


class Postavitev(unittest.TestCase):
    def setUp(self):
        self.css = _beri("assets", "os", "os.css")
        self.js = _beri("assets", "os", "os.js")

    def test_brez_desnega_stolpca_in_traku_kataloga(self):
        # 14. 10. 2026: kar se predvaja, je v spodnji vrstici (kot v glasbenih aplikacijah); desnega stolpca in traku
        # kataloga ni vec, katalog ima vso sirino.
        html = _beri("assets", "os", "index.html")
        for star in ('id="mediaDesni"', 'class="kat-trak"', 'id="mediaSedajNaslov"', 'id="mediaOdpriOkno"', 'id="mediaBarPremor"'):
            self.assertNotIn(star, html)
        self.assertNotIn("uskladiDesniStolpec", self.js)
        self.assertIn("#r-media .media-postavitev { grid-template-columns: minmax(0, 1fr); gap: 24px; }", self.css)
        # Spodnja vrstica je pod drsnim delom (#vsebina), ne cez njega: vsebine ne prekrije.
        glavno = html.split('<main id="glavno">', 1)[1].split("</main>", 1)[0]
        self.assertLess(glavno.index('<div id="vsebina">'), glavno.index('<div id="mediaPlayerBar"'))
        self.assertNotRegex(self.css.split("Spodnja vrstica »Predvaja se«", 1)[1].split("}", 1)[0], r"position:\s*(fixed|absolute)")

    def test_mirna_podlaga_iz_tem(self):
        self.assertIn("--media-tancica:", self.css.split(":root {", 1)[1].split("}", 1)[0])           # barva je v :root
        self.assertIn("body.v-mediji #ozadje::after, body.predvajalnik #ozadje::after { background: var(--media-tancica); }", self.css)
        self.assertIn('document.body.classList.toggle("v-mediji", razdelek === "media");', self.js)

    def test_eno_prazno_stanje(self):
        html = _beri("assets", "os", "index.html")
        self.assertNotIn("media-hero", html)
        self.assertIn('$("mediaPrazno").hidden = samoViri || prikaz.length !== 0 || imaKatalog;', self.js)
        self.assertIn('<div class="kat-prazno" id="katPrazno" hidden><p class="drobno" id="katPraznoBesedilo"></p><button class="gumb" id="katPraznoDejanje" type="button" hidden></button></div>', html)
        prazno = self.js.split("function narisiPrazenKatalog(skrij) {", 1)[1].split("\n  }\n", 1)[0]
        for niz in ('t("katVsiJeziki")', "izberiZanr(vseZvrsti)", "gumb.onclick = odpriKatViri;"):
            self.assertIn(niz, prazno)

    def test_zmanjsano_gibanje(self):
        kat = _beri("assets", "os", "katalog.css")
        self.assertIn("@media (prefers-reduced-motion: no-preference) { .kat-vrtavka { animation:", kat)
        self.assertIn("@media (prefers-reduced-motion: no-preference) {\n  .media-dodaj-meni:not([hidden])", self.css)


class NeskoncnoDrsenje(unittest.TestCase):
    def setUp(self):
        self.html = _beri("assets", "os", "index.html")
        self.js = _beri("assets", "os", "os.js")

    def test_brez_gumbov_za_strani(self):
        self.assertNotIn("mediaStranjevanje", self.html + self.js)
        self.assertNotIn("narisiStranjevanje", self.js)
        self.assertNotIn('t("katStran"', self.js)
        self.assertIn('<div class="kat-nalaganje" id="katNalaganje" hidden>', self.html)

    def test_naslednja_stran_ob_koncu(self):
        self.assertIn("new IntersectionObserver(function (vnosi) {", self.js)
        self.assertIn("naloziKatalog(true);", self.js)
        nalozi = self.js.split("function naloziKatalog(vec) {", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn("stran = vec ? kat.page + 1 : 1;", nalozi)
        self.assertIn("if (vec) { kat.napakaVec = true; narisiNalaganje(); return; }", nalozi)      # napaka: Poskusi znova
        prevzem = self.js.split("function prevzemiKatalog(response, tiho, stran) {", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn("else if (stran > 1) kat.strani.push({ kljuc: kljuc, vnosi: vnosi });", prevzem)
        # Izbor (D-pad, daljinec) in polozaj na zaslonu ostaneta po izrisu nove strani.
        self.assertIn("var sidro = (tiho || stran > 1) ? katSidro() : null;", prevzem)
        self.assertIn("kartica.focus({ preventScroll: true })", self.js)
        self.assertIn('card.setAttribute("data-id", x.id || "");', self.js)

    def test_tiha_osvezitev_vsake_strani(self):
        self.assertIn("kat.strani.some(function (s) { return s.kljuc === podatki.kljuc; })) prevzemiKatalog(podatki, true);", self.js)


class Zvrsti(unittest.TestCase):
    def test_gumbi_le_kjer_filtrirajo(self):
        js = _beri("assets", "os", "os.js")
        vidni = js.split("function zanriVidni() {", 1)[1].split("\n  }", 1)[0]
        self.assertIn('skupina === "film" || skupina === "serija" ? (kat.zvrsti || !!kat.genre) : !!skupina', vidni)
        self.assertIn('if (response && typeof response.zvrsti === "boolean") kat.zvrsti = response.zvrsti;', js)
        # Serije imajo pri TMDB svoje stevilke zvrsti (10759 akcija in pustolovscina, 10765 ZF in fantazija).
        self.assertIn('["10759", "katZanr_akcija"], ["10765", "katZanr_scifi"]', js)

    def _mc(self, viri):
        mc = os_media.MediaCenter.__new__(os_media.MediaCenter)
        mc._lock = threading.RLock()
        mc._load = lambda: {"viri": viri}
        return mc

    def test_jedro_pove_ali_zvrsti_filtrirajo(self):
        mc = self._mc([])
        for vrsta in ("glasba", "radio", "tv-v-zivo"):
            self.assertTrue(mc.zvrsti_filtrirajo(vrsta), vrsta)
        for vrsta in ("video", "vse", "slike", "film", "serija"):
            self.assertFalse(mc.zvrsti_filtrirajo(vrsta), vrsta)

    def test_filmi_samo_s_ponudnikom_tmdb(self):
        stari = os_media._EMBED_DOMAINS
        try:
            os_media._EMBED_DOMAINS = ("ponudnik.test",)
            mc = self._mc([{"id": "p1", "url": "https://ponudnik.test/"}])
            self.assertTrue(mc.zvrsti_filtrirajo("film"))
            self.assertTrue(mc.zvrsti_filtrirajo("serija"))
            self.assertFalse(mc.zvrsti_filtrirajo("film", ["p1"]))          # uporabnik ga je zacasno izklopil
        finally:
            os_media._EMBED_DOMAINS = stari

    def test_most_doda_zvrsti_v_odgovor(self):
        py = _beri("core", "os_katalog.py")
        self.assertIn('rezultat = dict(rezultat, zvrsti=mc.zvrsti_filtrirajo(self._niz(a, 1, "vse"), izklopljeni))', py)


def _funkcija(js, ime):
    """Besedilo funkcije `ime` iz os.js (do zaprtja na istem zamiku)."""
    return "function %s(" % ime + js.split("  function %s(" % ime, 1)[1].split("\n  }\n", 1)[0] + "\n  }\n"


def _node(koda):
    import json
    import shutil
    import subprocess
    if not shutil.which("node"):
        raise unittest.SkipTest("node ni namescen")
    izid = subprocess.run(["node", "-e", koda], capture_output=True, text=True, check=True).stdout
    return json.loads(izid)


class Domov(unittest.TestCase):
    """Skica Safeer Playerja (lastnik, 14. 10. 2026): Domov je privzeti pogled, junak samo z resnicnimi podatki,
    brez praznih polic, »Vse →« odpre pravi zavihek."""

    def setUp(self):
        self.js = _beri("assets", "os", "os.js")
        self.html = _beri("assets", "os", "index.html")

    def test_domov_je_privzet_in_zapomni_se_zadnji_pogled(self):
        koda = _funkcija(self.js, "zadnjaMedijskaKategorija") + """
        var shramba = {}; var localStorage = { getItem: function (k) { return k in shramba ? shramba[k] : null; } };
        var izid = [zadnjaMedijskaKategorija()];
        shramba["safeer.mediaKategorija"] = "filmi"; izid.push(zadnjaMedijskaKategorija());
        shramba["safeer.mediaKategorija"] = "vse"; izid.push(zadnjaMedijskaKategorija());
        shramba["safeer.mediaKategorija"] = "domov"; izid.push(zadnjaMedijskaKategorija());
        console.log(JSON.stringify(izid));"""
        self.assertEqual(_node(koda), ["domov", "filmi", "domov", "domov"])
        kategorije = self.js.split("var MEDIA_KATEGORIJE = [", 1)[1].split("];", 1)[0]
        self.assertTrue(kategorije.strip().startswith('["domov", "domov"]'))
        self.assertNotIn('"vse"', kategorije)
        # Domov nima kataloga in ne krajevne mreze; izbira se zapomni kot prej (izberiMedijskoKategorijo).
        self.assertIn("slike: \"\", domov: \"\" };", self.js)
        self.assertIn('S.mediaFilter === "tv" || S.mediaFilter === "radio" || S.mediaFilter === "domov"', self.js)

    def test_brez_praznih_polic_in_vse_odpre_zavihek(self):
        telo = _funkcija(self.js, "narisiPolice")
        self.assertIn("c.hidden = !police.length;", telo)
        self.assertIn("izberiZavihekMedijev(zavihek)", telo)
        koda = "var ZAVIHEK_VRSTE = " + self.js.split("var ZAVIHEK_VRSTE = ", 1)[1].split(";\n", 1)[0] + ";\n" + \
            _funkcija(self.js, "zavihekPolice") + """
        console.log(JSON.stringify([
          zavihekPolice({ id: "nadaljuj", vnosi: [{ vrsta: "serija" }, { vrsta: "serija" }, { vrsta: "film" }] }),
          zavihekPolice({ id: "nazadnje", vnosi: [{ vrsta: "filmi" }, { vrsta: "glasba" }, { vrsta: "filmi" }] }),
          zavihekPolice({ id: "glasba", vnosi: [{ vrsta: "film" }] }),
          zavihekPolice({ id: "najvec", vnosi: [{ vrsta: "radio" }] })]));"""
        self.assertEqual(_node(koda), ["serije", "filmi", "glasba", "radio"])
        # Prazno stanje z gumbom Dodaj, ko Domov nima nobene police (sele po odgovoru, da ne utripa).
        domov = _funkcija(self.js, "narisiMediaDomov")
        self.assertIn('var nalozeno = POL.nalozeno === "domov";', domov)
        self.assertIn("prazno.hidden = !nalozeno || ima;", domov)
        self.assertIn('class="media-prazno media-domov-del" id="mediaPrazno" hidden', self.html)

    def test_junak_samo_z_resnicnimi_podatki(self):
        priprava = "var t = function (k, z) { return k + (z ? JSON.stringify(z) : ''); };\n" + \
            "var KAT_FILMSKI_ZANRI = " + self.js.split("var KAT_FILMSKI_ZANRI = ", 1)[1].split(";\n", 1)[0] + ";\n" + \
            "var KAT_SERIJSKI_ZANRI = " + self.js.split("var KAT_SERIJSKI_ZANRI = ", 1)[1].split(";\n", 1)[0] + ";\n" + \
            "var ZAVIHEK_VRSTE = " + self.js.split("var ZAVIHEK_VRSTE = ", 1)[1].split(";\n", 1)[0] + ";\n"
        koda = priprava + "".join(_funkcija(self.js, f) for f in ("imeZvrsti", "trajanjeBesedilo", "podatkiJunaka")) + """
        console.log(JSON.stringify([
          podatkiJunaka({ naslov: "Film 1", vrsta: "film" }),
          podatkiJunaka({ naslov: "Film 2", vrsta: "film", leto: 2016, zanr: 878, vir: "Vir 1", pozicija: 1800, trajanje: 6600,
                          slika: "https://s.test/p.jpg", ozadje: "https://s.test/o.jpg" }),
          podatkiJunaka({ naslov: "Album", vrsta: "glasba", album: true, trajanje: 200, tip: "lokalno", pot: "/m/a.mp3" }),
          podatkiJunaka({ naslov: "Film 3", vrsta: "filmi", trajanje: 5400, tip: "lokalno" })]));"""
        brez, film, album, lokalni = _node(koda)
        # Brez podatkov: samo naslov in vrsta, nobene izmisljene oznake, vira ali slike.
        self.assertEqual(brez["meta"], ["media_filmi"])
        self.assertEqual((brez["vir"], brez["slika"], brez["ozadje"], brez["napredek"]), ("", "", "", 0))
        self.assertEqual(film["meta"], ["2016", 'policaOstane{"n":80}', "katZanr_scifi", "media_filmi"])
        self.assertEqual((film["vir"], film["napredek"], film["ozadje"]), ("Vir 1", 27, "https://s.test/o.jpg"))
        self.assertEqual(album["meta"], ["media_glasba"])                   # dolzina albuma ni dolzina prve skladbe
        self.assertEqual(album["vir"], "mediaTaRacunalnik")
        self.assertEqual(lokalni["meta"], ['domovUre{"h":1,"m":30}', "media_filmi"])
        telo = _funkcija(self.js, "podatkiJunaka") + _funkcija(self.js, "narisiMediaDomov")
        for izmisljeno in ("4K", "HDR", "Dolby", "IMDb", "ocena"):
            self.assertNotIn(izmisljeno, telo)


class Navigacija(unittest.TestCase):
    """Leva navigacija na namizju, vodoravni zavihki v ozkem prostoru; viri so pravi, brez praznih naslovov."""

    def setUp(self):
        self.css = _beri("assets", "os", "os.css")
        self.js = _beri("assets", "os", "os.js")
        self.html = _beri("assets", "os", "index.html")

    def test_ozko_ostanejo_vodoravni_zavihki(self):
        blok = self.css.split("Medijski center na namizju", 1)[1]
        self.assertIn("#r-media { container: mediji / inline-size; }", blok)
        self.assertIn(".media-nav { display: none; }", blok)                   # privzeto (ozko): brez leve navigacije
        siroko = blok.split("@container mediji (min-width: 980px) {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("grid-template-columns: 220px minmax(0, 1fr)", siroko)
        self.assertIn(".media-nav { position: sticky;", siroko)
        self.assertIn("#r-media .media-orodna .media-kategorije { display: none; }", siroko)
        # Iskanje ostane na vrhu vsebine v obeh postavitvah.
        vsebina = self.html.split('<div class="media-vsebina">', 1)[1]
        self.assertTrue(vsebina.lstrip().startswith('<div class="media-orodna">'))
        self.assertIn('id="mediaIskanje"', vsebina.split('<div class="media-postavitev">', 1)[0])

    def test_isti_zavihki_v_obeh_postavitvah(self):
        telo = _funkcija(self.js, "narisiMedije")
        self.assertIn('[[kategorije, "media-kategorija"], [$("mediaNavKategorije"), "media-nav-kategorija"]]', telo)
        self.assertIn('b.setAttribute("role", "tab");', telo)
        self.assertIn('b.setAttribute("aria-selected"', telo)
        self.assertIn('role="tablist" aria-orientation="vertical"', self.html)

    def test_viri_samo_pravi_brez_praznega_naslova(self):
        telo = _funkcija(self.js, "narisiViriNav")
        self.assertIn("ovoj.hidden = !vnosi.length;", telo)
        self.assertIn("if (S.mediaMape.length && ", telo)
        self.assertIn('<div class="media-nav-viri" id="mediaNavViri" hidden>', self.html)
        # Isto pravilo kot core/os_media.vidni_viri: strezniki, viri z vsebino, delujoci predvajalni viri.
        self.assertIn('v.vrsta === "streznik" || (v.stevilo || 0) > 0 || (v.tip === "predvajalni_vir" && !v.napaka)', self.js)
        # Klik na vir uporabi obstojeci zacasni filter virov kataloga (tam ga uporabnik tudi ponastavi).
        izberi = _funkcija(self.js, "izberiVir")
        self.assertIn("kat.izklopljeni[x] = 1", izberi)
        self.assertIn("osveziGumbViri();", izberi)


class SpodnjaVrstica(unittest.TestCase):
    """Vrstica »Predvaja se«: samo med predvajanjem, polozaj samo, ce je znan, isti gumbi za katalog in predvajalnik."""

    def setUp(self):
        self.js = _beri("assets", "os", "os.js")
        self.html = _beri("assets", "os", "index.html")

    def test_skrita_ko_se_nic_ne_predvaja(self):
        self.assertIn('<div id="mediaPlayerBar" class="media-player-bar" role="region" aria-labelledby="mediaBarNaslov" hidden>', self.html)
        koda = """
        var el = {}; function $(id) { return el[id] || (el[id] = { hidden: true, setAttribute: function () {}, focus: function () {} }); }
        var document = { body: { classList: { toggle: function () {} } } };
        var S = { mediaPredvajalnik: null }, kat = { aktivni: null };
        """ + "".join(_funkcija(self.js, f) for f in ("skladbaKataloga", "zapriVrstoPlosco", "uskladiTrak")) + """
        var izid = [];
        $("mediaPlayerBar").hidden = false;
        uskladiTrak(); izid.push($("mediaPlayerBar").hidden);                                  // nic
        S.mediaPredvajalnik = { naslov: "Skladba 1", stanje: "ustavljeno" };
        uskladiTrak(); izid.push($("mediaPlayerBar").hidden);                                  // ustavljeno
        S.mediaPredvajalnik.stanje = "premor"; uskladiTrak(); izid.push($("mediaPlayerBar").hidden);
        S.mediaPredvajalnik.stanje = "ustavljeno"; kat.aktivni = { zvok: true, naslov: "Skladba 2" };
        uskladiTrak(); izid.push($("mediaPlayerBar").hidden);                                  // skladba iz kataloga
        kat.aktivni = { zvok: false }; uskladiTrak(); izid.push($("mediaPlayerBar").hidden);  // video iz kataloga gre v okno
        console.log(JSON.stringify(izid));"""
        self.assertEqual(_node(koda), [True, True, False, False, True])

    def test_polozaj_samo_ce_je_znan(self):
        telo = _funkcija(self.js, "narisiTrak")
        self.assertIn('var polozaj = !(item && item.okno_youtube) && !!p.naslov && p.stanje !== "ustavljeno" && !zivo && Number(p.trajanje) > 0;', telo)
        self.assertIn('$("mediaBarPolozaj").hidden = !polozaj;', telo)
        self.assertIn('<div class="media-player-polozaj" id="mediaBarPolozaj" hidden>', self.html)
        # Glasnost je sistemska in samo, ce jo sistem javi.
        self.assertIn("ovoj.hidden = !z;", _funkcija(self.js, "narisiGlasnostTraku"))

    def test_obstojeci_gumbi_v_vrstici(self):
        vrstica = self.html.split('<div id="mediaPlayerBar"', 1)[1].split("\n    </div>\n", 1)[0]
        for id_ in ("mediaPremesaj", "mediaPrejsnja", "mediaKatPremor", "mediaNaslednja", "mediaPonovi", "mediaZapri",
                    "mediaBarNapredek", "mediaBarGlasnostDrsnik", "mediaBarVrstaGumb", "mediaVrsta"):
            self.assertIn('id="%s"' % id_, vrstica)
        for niz in ('ob("mediaPrejsnja", "click", function () { if (skladbaKataloga()) predvajajIzVrste(-1); else ukaz("prejsnja"); });',
                    'ob("mediaKatPremor", "click", function () { if (skladbaKataloga()) premorKatPredvajanja(); else ukaz("premor"); });',
                    'ob("mediaZapri", "click", function () { if (kat.aktivni) ustaviKatPredvajanje(); else ukaz("ustavi"); });'):
            self.assertIn(niz, self.js)
        # Plosca cakalne vrste: Escape (Nazaj na daljincu) zapre samo njo, izbor se vrne na gumb.
        self.assertIn('if (e.key === "Escape" && zapriVrstoPlosco(true)) { e.preventDefault(); e.stopImmediatePropagation(); }', self.js)


class BesedilaInBarve(unittest.TestCase):
    def test_nova_besedila_v_vseh_jezikih(self):
        bes = _beri("assets", "os", "besedila.js")
        js, html = _beri("assets", "os", "os.js"), _beri("assets", "os", "index.html")
        for kljuc in ("media_domov", "mediaViriNaslov", "mediaPolozaj", "policaGlasba", "domovVse", "domovVseOznaka",
                      "domovUre", "domovMinut", "domovNadaljuj", "domovPredvajaj"):
            self.assertEqual(bes.count('"%s":' % kljuc), 6, kljuc)
            self.assertTrue(kljuc in js or kljuc in html or kljuc == "media_domov", kljuc)

    def test_barve_samo_iz_spremenljivk(self):
        blok = _beri("assets", "os", "os.css").split("Medijski center na namizju", 1)[1]
        self.assertNotRegex(blok, r"rgba?\(|#[0-9a-fA-F]{3,6}\b")

    def test_zmanjsano_gibanje(self):
        blok = _beri("assets", "os", "os.css").split("Medijski center na namizju", 1)[1]
        self.assertIn("@media (prefers-reduced-motion: no-preference) {\n  .media-vrsta-plosca:not([hidden])", blok)


class PrilagojenMeni(unittest.TestCase):
    """Skrij, kar uporabnik ne potrebuje (lastnik, 14. 10. 2026): zavihki in viri se skrijejo samo iz menija."""

    def setUp(self):
        self.js = _beri("assets", "os", "os.js")
        self.html = _beri("assets", "os", "index.html")
        self.kavc = _beri("assets", "os", "kavc.js")

    def test_domov_se_ne_skrije_in_skrito_ni_v_meniju(self):
        koda = "var S = { mediaSkrito: { 'kat:tv': 1, 'kat:domov': 1, 'vir:a': 1 } };\n" + _funkcija(self.js, "jeSkrito") + """
        console.log(JSON.stringify([jeSkrito("kat:tv"), jeSkrito("kat:domov"), jeSkrito("vir:a"), jeSkrito("kat:radio")]));"""
        self.assertEqual(_node(koda), [True, False, True, False])
        mediji = _funkcija(self.js, "narisiMedije")
        self.assertIn('MEDIA_KATEGORIJE.filter(function (k) { return k[0] === S.mediaFilter || !jeSkrito("kat:" + k[0]); })', mediji)
        self.assertIn('poveziMeniNav(b, "kat:" + k[0], t("media_" + k[0]));', mediji)       # vodoravni zavihki in leva navigacija
        viri = _funkcija(self.js, "narisiViriNav")
        self.assertIn('!jeSkrito("vir:mape")', viri)
        self.assertIn('if (jeSkrito("vir:" + v.id)) return;', viri)
        # Zapomnjen skrit zavihek ob odprtju: Domov.
        self.assertIn('if (ob_nalaganju && !prej && jeSkrito("kat:" + S.mediaFilter)) { izberiMedijskoKategorijo("domov");',
                      _funkcija(self.js, "nastaviSkrito"))
        # V jedru, ne v localStorage (skupno glavnemu oknu in Safeer Playerju; drugo okno dobi dogodek).
        self.assertIn('klic("mediaSkrij", [kljuc, !!da])', self.js)
        self.assertIn('if (vrsta === "mediaSkrito") nastaviSkrito(podatki, false);', self.js)
        self.assertNotIn("safeer.mediaSkrito", self.js)

    def test_meni_s_tipkovnico_dotikom_in_ploskom(self):
        povezi = _funkcija(self.js, "poveziMeniNav")
        for niz in ('addEventListener("contextmenu"', 'e.key === "ContextMenu" || (e.shiftKey && e.key === "F10")',
                    'if (e.pointerType === "mouse") return;', "}, 600);"):
            self.assertIn(niz, povezi)
        # Gumb Y na ploscku poslje »contextmenu« izbranemu gumbu (kavc.js).
        self.assertIn('el.dispatchEvent(new MouseEvent("contextmenu"', self.kavc)
        meni = _funkcija(self.js, "odpriMeniNav")
        self.assertIn('if (kljuc !== "kat:domov") postavka("x", t("mediaSkrijIzMenija")', meni)
        self.assertIn('t("mediaPrilagodiMeni")', meni)

    def test_plosca_prilagodi(self):
        self.assertIn('id="mediaNavPrilagodi" type="button" aria-haspopup="dialog" aria-controls="slojPrilagodi"', self.html)
        self.assertIn('<div class="plosca media-mape-plosca prilagodi-plosca" role="dialog" aria-modal="true" aria-labelledby="prilagodiNaslov"', self.html)
        plosca = _funkcija(self.js, "narisiPrilagodi")
        self.assertIn('k[0] !== "domov"', plosca)
        self.assertIn('cb.type = "checkbox"; cb.checked = !jeSkrito(p.kljuc);', plosca)
        self.assertIn('if (e.key === "Escape" && zapriPrilagodi()) { e.preventDefault(); e.stopImmediatePropagation(); }', self.js)
        # Odprto okno ujame izbor puscic (kavc.js: .sloj.viden).
        self.assertIn('.sloj.viden, [role=dialog]:not([hidden])', self.kavc)

    def test_meni_ob_povecavi_kavca(self):
        koda = """
        var window = { innerWidth: 1920, innerHeight: 1080, getComputedStyle: function () { return { zoom: "1.25" }; } };
        var document = { body: {} };
        """ + _funkcija(self.js, "postaviPlavajoce") + """
        var m = { offsetWidth: 240, offsetHeight: 143, style: {} };
        postaviPlavajoce(m, 100, 760, 700); var a = [m.style.left, m.style.top];
        postaviPlavajoce(m, 100, 1060, 1000); a.push(m.style.top);              // pod gumbom ni prostora: nad gumb
        console.log(JSON.stringify(a));"""
        self.assertEqual(_node(koda), ["80px", "608px", "657px"])


class SamodejniSeznamiStran(unittest.TestCase):
    def setUp(self):
        self.js = _beri("assets", "os", "os.js")
        self.html = _beri("assets", "os", "index.html")

    def test_polica_na_domov_in_glasbi_brez_praznih(self):
        self.assertIn('<section class="media-samodejni media-domov-del" id="mediaSamodejni" aria-labelledby="mediaSamodejniNaslov" hidden>', self.html)
        telo = _funkcija(self.js, "narisiSamodejne")
        self.assertIn('var vidno = (S.mediaFilter === "domov" || S.mediaFilter === "glasba") && !String(S.mediaIskanje || "").trim() && seznami.length > 0;', telo)
        self.assertIn("c.hidden = !vidno;", telo)
        self.assertIn('klic("mediaSamodejniSeznami", [])', self.js)
        self.assertIn('if (vrsta === "mediaSamodejniOsvezeni") naloziSamodejne();', self.js)

    def test_predvajanje_skozi_obstojeco_vrsto_brez_mesanja(self):
        telo = _funkcija(self.js, "predvajajSamodejni")
        self.assertIn("kat.vrsta = vnosi.map(function (v) { return v.id; }); kat.vrstaVnosi = vnosi; kat.vrstaMesto = 0;", telo)
        self.assertIn("odpriKatalogVnos(vnosi[0].id);", telo)
        for f in ("predvajajSamodejni", "narisiSamodejne", "kolaz"):
            self.assertNotIn("Math.random", _funkcija(self.js, f))
        self.assertIn('klic("mediaSamodejniShrani", [sz.id, ime])', _funkcija(self.js, "shraniSamodejni"))

    def test_kolaz_samo_iz_pravih_naslovnic(self):
        telo = _funkcija(self.js, "kolaz")
        self.assertIn("var n = slike.length >= 4 ? 4 : slike.length ? 1 : 0;", telo)
        self.assertIn("slike.slice(0, n)", telo)

    def test_besedila_v_vseh_jezikih(self):
        bes = _beri("assets", "os", "besedila.js")
        for kljuc in ("mediaSkrijIzMenija", "mediaPrilagodiMeni", "mediaPrilagodiNaslov", "mediaPrilagodiOpis", "mediaPrilagodiVrste",
                      "mediaSkritoObvestilo", "samNaslov", "samNajvec", "samNazadnje", "samDolgo", "samOdkrij", "samMesanica",
                      "samShrani", "samShranjen", "samPredvajaj"):
            self.assertEqual(bes.count('"%s":' % kljuc), 6, kljuc)
            self.assertTrue(kljuc in self.js or kljuc in self.html, kljuc)


class Kavc(unittest.TestCase):
    def test_gumb_ikona_s_stanjem(self):
        js = _beri("assets", "os", "kavc.js")
        self.assertIn('g.setAttribute("aria-label", besedilo("kavcVklop"));', js)
        self.assertIn('g.title = besedilo(vklop ? "kavcIzklop" : "kavcVklop");', js)
        # Odprt meni ujame izbor puscic kot okno.
        self.assertIn("[role=menu]:not([hidden])", js)
        self.assertTrue(re.search(r"napis: function \(\) \{ napisGumba\(kavc\(\)\); \}", js))


if __name__ == "__main__":
    unittest.main()
