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

    def test_desni_stolpec_samo_med_predvajanjem(self):
        self.assertIn("#r-media:not(.predvaja) .media-desni { display: none; }", self.css)
        self.assertIn("#r-media .media-postavitev { grid-template-columns: minmax(0, 1fr); gap: 24px; }", self.css)
        telo = self.js.split("function uskladiDesniStolpec() {", 1)[1].split("\n  }", 1)[0]
        # Isto pravilo kot spodnja vrstica predvajalnika: premor steje, ustavljeno ne; ali skladba iz kataloga.
        self.assertIn('var domaci = !!(p && p.naslov && p.stanje !== "ustavljeno");', telo)
        self.assertIn("kat.aktivni && kat.aktivni.zvok", telo)
        self.assertIn('r.classList.toggle("predvaja", domaci || izKataloga);', telo)
        for klic in ("function prikaziMediaBar() {\n    var p = S.mediaPredvajalnik;\n    uskladiDesniStolpec();",
                     "    if (!pl) return;\n    uskladiDesniStolpec();"):
            self.assertIn(klic, self.js)

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
