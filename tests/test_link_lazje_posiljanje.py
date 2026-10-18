"""Lazje posiljanje datotek med napravami (lastnik, 18. 10. 2026).

  - core/link_posiljanje: posiljka pocaka na napravo, ki je ni, in nadaljuje pri isti datoteki; preklic; zadnja naprava
    prva v menijih; besedila obvestila za posiljanje iz Nema;
  - core/link_prejem: ozji krog brez vprasanja, sirsi krog z vprasanjem (Sprejmi velja za vso posiljko), eno obvestilo
    na posiljatelja z »Odpri« / »Pokazi v mapi«, napake samo v dnevnik;
  - core/link_nemo: dejanja »Poslji na …« v Nemu (vrstni red po imenu datoteke, samo nase datoteke);
  - mapa prenosov po XDG (»Prejemi« na slovenskem Mintu) tudi za prejem v Linku;
  - stran Linka: spust datotek na napravo.
"""
import os
import tempfile
import time
import unittest
from unittest import mock

from core import link_deljenje, link_nemo, link_posiljanje, link_prejem, splet_prenosi

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _pocakaj(pogoj, cas=5.0):
    konec = time.monotonic() + cas
    while time.monotonic() < konec:
        if pogoj():
            return True
        time.sleep(0.01)
    return False


class _Nastavitve:
    def __init__(self):
        self.podatki = {}
        self.shranjeno = 0

    def get(self, k, privzeto=None):
        return self.podatki.get(k, privzeto)

    def shrani(self):
        self.shranjeno += 1


class Nadaljevanje(unittest.TestCase):
    """Naprava odide sredi posiljanja: posiljka caka in nadaljuje pri isti datoteki, ko je naprava spet v Linku."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        for ime, vrednost in (("PREVERI_S", 0.02), ("RAZMIKI_S", (0.0,))):
            p = mock.patch.object(link_posiljanje, ime, vrednost)
            p.start()
            self.addCleanup(p.stop)
        self.tu = False
        self.klici = []
        self.izidi = []
        self.spremembe = []
        self.zadnje = []

    def _datoteka(self, ime, velikost=10):
        pot = os.path.join(self.tmp.name, ime)
        with open(pot, "wb") as f:
            f.write(b"x" * velikost)
        return pot

    def _poslji(self, naprava, pot, napredek):
        self.klici.append(os.path.basename(pot))
        napredek(100)
        return self.izidi.pop(0) if self.izidi else (True, {})

    def _p(self, **kw):
        return link_posiljanje.Posiljanje(self._poslji, lambda i: "Tablica", dosegljiva=lambda i: self.tu,
                                          ob_spremembi=self.spremembe.append, zabelezi=self.zadnje.append, **kw)

    def test_caka_in_nadaljuje_pri_isti_datoteki(self):
        p = self._p()
        ni = (False, {"koda": "naprava_ni_povezana", "sporocilo": "Ciljna naprava ni povezana.", "zasedenaOd": ""})
        self.izidi = [(True, {}), ni]
        a, b, c = self._datoteka("a.txt"), self._datoteka("b.txt"), self._datoteka("c.txt")
        r = p.zacni("tab", [a, b, c], obvesti=True)
        self.assertEqual(self.zadnje, ["tab"], "zadnja naprava zabelezena ob zacetku")
        self.assertTrue(_pocakaj(lambda: p.stanje(r["id"])["stanje"] == "caka"))
        s = p.stanje(r["id"])
        self.assertEqual((s["poslanih"], s["ime"], s["koda"], s["obvesti"]), (1, "b.txt", "naprava_ni_povezana", True))
        time.sleep(0.1)
        self.assertEqual(self.klici, ["a.txt", "b.txt"], "dokler naprave ni, ne poskusa")
        self.tu = True
        p.zbudi("tab")
        self.assertTrue(_pocakaj(lambda: p.stanje(r["id"])["stanje"] == "poslano"))
        self.assertEqual(self.klici, ["a.txt", "b.txt", "b.txt", "c.txt"], "nadaljuje pri b.txt, a.txt ne znova")
        self.assertEqual(p.stanje(r["id"])["koda"], "")
        stanja = [x["stanje"] for x in self.spremembe]
        self.assertIn("caka", stanja)
        self.assertEqual(stanja[-1], "poslano")

    def test_koncna_napaka_ne_caka(self):
        p = self._p()
        self.izidi = [(False, {"koda": "ni_prostora", "sporocilo": "Ni dovolj prostora."})]
        r = p.zacni("tab", [self._datoteka("a.txt")])
        self.assertTrue(_pocakaj(lambda: p.stanje(r["id"])["stanje"] == "napaka"))
        self.assertEqual(p.stanje(r["id"])["koda"], "ni_prostora")

    def test_preklic_cakajoce(self):
        p = self._p()
        self.izidi = [(False, {"koda": "naprava_ni_povezana"})]
        r = p.zacni("tab", [self._datoteka("a.txt")])
        self.assertTrue(_pocakaj(lambda: p.stanje(r["id"])["stanje"] == "caka"))
        self.assertTrue(p.preklici(r["id"])["ok"])
        self.assertTrue(_pocakaj(lambda: p.stanje(r["id"])["stanje"] == "napaka"))
        self.assertEqual(p.stanje(r["id"])["koda"], "preklicano")
        self.assertEqual(p.preklici("ni-ga"), {"ok": False, "koda": "ni_posiljke"})

    def test_izbrisana_datoteka_ne_caka(self):
        p = self._p()
        a = self._datoteka("a.txt")
        self.izidi = [(False, {"koda": "posiljanje_ni_uspelo"})]

        def poslji(naprava, pot, napredek):
            os.remove(pot)
            return self.izidi.pop(0)
        p._poslji = poslji
        r = p.zacni("tab", [a])
        self.assertTrue(_pocakaj(lambda: p.stanje(r["id"])["stanje"] == "napaka"))
        self.assertEqual(p.stanje(r["id"])["koda"], "ni_datoteke")

    def test_rok_cakanja(self):
        ura = [0.0]
        p = self._p(ura=lambda: ura[0])
        self.izidi = [(False, {"koda": "naprava_ni_povezana"})]
        r = p.zacni("tab", [self._datoteka("a.txt")])
        self.assertTrue(_pocakaj(lambda: p.stanje(r["id"])["stanje"] == "caka"))
        ura[0] = link_posiljanje.CAKA_NAJVEC_S + 1
        self.assertTrue(_pocakaj(lambda: p.stanje(r["id"])["stanje"] == "napaka"))
        self.assertEqual(p.stanje(r["id"])["koda"], "naprava_ni_povezana")


class ZadnjaNaprava(unittest.TestCase):
    def test_zadnja_prva_potem_po_imenu(self):
        n = _Nastavitve()
        link_posiljanje.zabelezi_zadnjo(n, "tel", zdaj=100.0)
        link_posiljanje.zabelezi_zadnjo(n, "tab", zdaj=200.0)
        self.assertEqual(n.shranjeno, 2)
        naprave = [{"id": i, "ime": ime, "zadnjic": link_posiljanje.zadnjic(n, i)}
                   for i, ime in (("tv", "Televizor"), ("tel", "Telefon"), ("tab", "Tablica"), ("pc", "Prenosnik"))]
        self.assertEqual([x["id"] for x in link_posiljanje.razvrsti(naprave)], ["tab", "tel", "pc", "tv"])
        self.assertEqual(link_posiljanje.zadnjic(n, "neznana"), 0.0)

    def test_meja_zapisov(self):
        n = _Nastavitve()
        for i in range(link_posiljanje.NAJVEC_ZADNJIH + 5):
            link_posiljanje.zabelezi_zadnjo(n, "n%d" % i, zdaj=float(i))
        zapis = n.podatki[link_posiljanje.KLJUC_ZADNJE]
        self.assertEqual(len(zapis), link_posiljanje.NAJVEC_ZADNJIH)
        self.assertNotIn("n0", zapis, "najstarejse izpadejo")

    def test_besedila_obvestila_v_vseh_jezikih(self):
        kljuci = set(link_posiljanje.BESEDILA_OBVESTIL["sl"])
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            self.assertEqual(set(link_posiljanje.BESEDILA_OBVESTIL[jezik]), kljuci, jezik)
        naslov, telo = link_posiljanje.obvestilo("sl", {"stanje": "caka", "naprava": "Tablica", "datotek": 3})
        self.assertEqual(naslov, "Čakam na napravo Tablica")
        self.assertTrue(telo.startswith("Datotek: 3"))
        self.assertEqual(link_posiljanje.obvestilo("en", {"stanje": "poslano", "naprava": "TV", "datotek": 1, "ime": "a.mp4"}),
                         ("Sent to TV", "a.mp4"))


class Prejem(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.object(link_prejem, "OBVESTILO_RAZMIK_S", 0.0)
        p.start()
        self.addCleanup(p.stop)
        self.ozji = {"tel"}
        self.obvestila = {}
        self.umaknjena = []
        self.odprto, self.pokazano = [], []
        self.ura = [0.0]
        self.neuspeh = set()
        self.p = link_prejem.Prejem(
            prevzemi=self._prevzemi, obvesti=self._obvesti, brez_vprasanja=lambda i, z: (z or i) in self.ozji,
            odpri=self.odprto.append, pokazi=self.pokazano.append, jezik=lambda: "sl",
            umakni=self.umaknjena.append, v_ozadju=lambda f: f(), ura=lambda: self.ura[0])

    def _prevzemi(self, t):
        if t["name"] in self.neuspeh:
            return None, "ni prostora"
        mapa = os.path.join(self.tmp.name, "Prejemi", t.get("dir") or "")
        return os.path.join(mapa, t["name"]), ""

    def _obvesti(self, ident, naslov, besedilo, gumbi=None, privzeto=None, prioriteta="normal"):
        self.obvestila[ident] = {"naslov": naslov, "besedilo": besedilo, "gumbi": {k: (n, f) for k, n, f in gumbi or []},
                                 "privzeto": privzeto}

    def _eno(self, predpona):
        izbrana = [o for i, o in self.obvestila.items() if i.startswith("safeer-" + predpona)]
        self.assertEqual(len(izbrana), 1, self.obvestila)
        return izbrana[0]

    @staticmethod
    def _t(ime, velikost=1000, mapa=""):
        t = {"name": ime, "path": "/cast/file/x?k=y", "size": velikost, "sha256": "0" * 64}
        if mapa:
            t["dir"] = mapa
        return t

    def test_ozji_krog_brez_vprasanja_eno_obvestilo(self):
        self.assertEqual(self.p.prispela("tel", "Telefon", self._t("a.jpg")), "prenos")
        o = self._eno("prejem")
        self.assertEqual(o["naslov"], "Prejeto od Telefon")
        pot = os.path.join(self.tmp.name, "Prejemi", "a.jpg")
        self.assertEqual(o["besedilo"], "a.jpg je v mapi " + os.path.dirname(pot))
        self.assertEqual([n for n, _f in o["gumbi"].values()], ["Odpri", "Pokaži v mapi"])
        o["gumbi"]["odpri"][1]()
        o["gumbi"]["pokazi"][1]()
        self.assertEqual((self.odprto, self.pokazano), ([pot], [pot]))
        self.p.prispela("tel", "Telefon", self._t("b.jpg"))
        o = self._eno("prejem")
        self.assertTrue(o["besedilo"].startswith("Prejetih datotek: 2"), o["besedilo"])
        self.assertNotIn("~", o["besedilo"], "polna pot, nikoli ~")

    def test_poslana_mapa_odpri_mapo(self):
        for ime in ("1.jpg", "2.jpg"):
            self.p.prispela("tel", "Telefon", self._t(ime, mapa="Pocitnice/Dan 1"))
        o = self._eno("prejem")
        vrh = os.path.join(self.tmp.name, "Prejemi", "Pocitnice")
        self.assertEqual(o["besedilo"], "Prejetih datotek: 2 · mapa " + vrh)
        self.assertEqual(o["gumbi"]["odpri"][0], "Odpri mapo")
        o["gumbi"]["odpri"][1]()
        self.assertEqual(self.odprto, [vrh])

    def test_sirsi_krog_vprasa_in_sprejmi_velja_za_posiljko(self):
        self.assertEqual(self.p.prispela("tuj", "Telefon gosta", self._t("a.pdf", 2_500_000)), "vprasano")
        self.assertEqual(self.p.prispela("tuj", "Telefon gosta", self._t("b.pdf", 500_000)), "vprasano")
        o = self._eno("ponudba")
        self.assertEqual(o["naslov"], "Telefon gosta ti pošilja datoteke")
        self.assertIn("Datotek: 2 (3 MB)", o["besedilo"])
        self.assertNotIn("prejem", "".join(self.obvestila), "nic se ni prevzelo")
        o["gumbi"]["sprejmi"][1]()
        self.assertTrue(self.umaknjena[0].startswith("safeer-ponudba-"))
        self.assertTrue(self._eno("prejem")["besedilo"].startswith("Prejetih datotek: 2"))
        # Ista posiljka (mapa) se nadaljuje: brez novega vprasanja.
        self.ura[0] += 30
        self.assertEqual(self.p.prispela("tuj", "Telefon gosta", self._t("c.pdf")), "prenos")
        # Nova posiljka po casu odgovora: spet vprasamo.
        self.ura[0] += link_prejem.ODGOVOR_VELJA_S + 1
        self.assertEqual(self.p.prispela("tuj", "Telefon gosta", self._t("d.pdf")), "vprasano")

    def test_zavrni(self):
        self.p.prispela("tuj", "Gost", self._t("a.pdf"))
        self.assertEqual(self._eno("ponudba")["gumbi"]["zavrni"][1](), 1)
        self.assertEqual(self.p.prispela("tuj", "Gost", self._t("b.pdf")), "zavrnjeno")
        self.assertFalse([i for i in self.obvestila if i.startswith("safeer-prejem")])
        self.assertEqual(self.p.odgovori("tuj", True), 0, "odgovor velja enkrat")

    def test_napaka_samo_v_dnevnik(self):
        self.neuspeh.add("a.jpg")
        self.assertEqual(self.p.prispela("tel", "Telefon", self._t("a.jpg")), "prenos")
        self.assertEqual(self.obvestila, {}, "brez okna ali obvestila z napako")

    def test_mapa_s_tisoc_datotekami_ne_zasuje_obvestil(self):
        poslana = []
        self._obvesti_prej = self._obvesti
        self.p._obvesti = lambda ident, *a, **k: (poslana.append(a[1]), self._obvesti_prej(ident, *a, **k))
        with mock.patch.object(link_prejem, "OBVESTILO_RAZMIK_S", 0.3):
            for i in range(200):
                self.p.prispela("tel", "Telefon", self._t("%d.jpg" % i, mapa="Mapa"))
            self.assertLess(len(poslana), 5, "zdruzena obvestila")
            self.assertTrue(_pocakaj(lambda: poslana and poslana[-1].startswith("Prejetih datotek: 200"), 2.0),
                            "zadnje stanje pride z zamikom")

    def test_besedila_v_vseh_jezikih(self):
        kljuci = set(link_prejem.BESEDILA["sl"])
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            self.assertEqual(set(link_prejem.BESEDILA[jezik]), kljuci, jezik)
        self.assertEqual(link_prejem.velikost(2_500_000, "en"), "2.5 MB")
        self.assertEqual(link_prejem.velikost(2_500_000, "sl"), "2,5 MB")


class Nemo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.mapa = os.path.join(self.tmp.name, "actions")

    def test_eno_dejanje_na_napravo_v_vrstnem_redu(self):
        naprave = [{"id": "n-aaaaaaaaaaaaaaaa", "ime": "Tablica"}, {"id": "n-bbbbbbbbbbbbbbbb.tv", "ime": "TV_100%"}]
        self.assertTrue(link_nemo.zapisi(naprave, self.mapa, nemo=True))
        self.assertEqual(sorted(os.listdir(self.mapa)), ["safeer-poslji-01.nemo_action", "safeer-poslji-02.nemo_action"])
        with open(os.path.join(self.mapa, "safeer-poslji-01.nemo_action"), encoding="utf-8") as f:
            prva = f.read()
        self.assertIn("Name[sl]=Pošlji na »Tablica«\n", prva)
        self.assertIn("Exec=safeerctl send --notify --to n-aaaaaaaaaaaaaaaa %F\n", prva)
        self.assertIn("Selection=notnone\n", prva)
        self.assertIn("Extensions=any;\n", prva)
        self.assertIn("Conditions=dbus io.github.memelandfaner.SafeerControl;\n", prva)
        self.assertIn("Dependencies=safeerctl;\n", prva)
        with open(os.path.join(self.mapa, "safeer-poslji-02.nemo_action"), encoding="utf-8") as f:
            self.assertIn("Name[sl]=Pošlji na »TV__100%%«\n", f.read(), "% in _ v imenu ubezana")
        self.assertFalse(link_nemo.zapisi(naprave, self.mapa, nemo=True), "brez spremembe se nic ne pise")

    def test_odstrani_samo_svoje_in_zavrne_nevarne_oznake(self):
        os.makedirs(self.mapa)
        tuja = os.path.join(self.mapa, "moje.nemo_action")
        open(tuja, "w").close()
        link_nemo.zapisi([{"id": "a", "ime": "A"}, {"id": "b", "ime": "B"}], self.mapa, nemo=True)
        link_nemo.zapisi([{"id": "x; rm -rf /", "ime": "Zlo"}, {"id": "-x", "ime": "Stikalo"}, {"id": "b", "ime": "B"}],
                         self.mapa, nemo=True)
        self.assertEqual(sorted(os.listdir(self.mapa)), ["moje.nemo_action", "safeer-poslji-01.nemo_action"])
        link_nemo.zapisi([{"id": "b", "ime": "B"}], self.mapa, nemo=False)
        self.assertEqual(os.listdir(self.mapa), ["moje.nemo_action"], "brez Nema nasih dejanj ni, tuja ostanejo")

    def test_najvec(self):
        link_nemo.zapisi([{"id": "n%d" % i, "ime": str(i)} for i in range(20)], self.mapa, nemo=True)
        self.assertEqual(len(os.listdir(self.mapa)), link_nemo.NAJVEC)


class MapaPrenosov(unittest.TestCase):
    def test_xdg_prejemi(self):
        with tempfile.TemporaryDirectory() as dom:
            os.makedirs(os.path.join(dom, ".config"))
            os.makedirs(os.path.join(dom, "Prejemi"))
            with open(os.path.join(dom, ".config", "user-dirs.dirs"), "w", encoding="utf-8") as f:
                f.write('# xdg\nXDG_DESKTOP_DIR="$HOME/Namizje"\nXDG_DOWNLOAD_DIR="$HOME/Prejemi"\n')
            with mock.patch.dict(os.environ, {"HOME": dom, "XDG_CONFIG_HOME": ""}):
                self.assertEqual(link_deljenje.mapa_prenosov(), os.path.join(dom, "Prejemi"))
                self.assertEqual(splet_prenosi.mapa_xdg_prenosov(), os.path.join(dom, "Prejemi"))


class StranLinka(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(KOREN, "assets", "link", "link.js"), encoding="utf-8") as f:
            self.js = f.read()
        with open(os.path.join(KOREN, "core", "safeer_link.py"), encoding="utf-8") as f:
            self.py = f.read()

    def test_spust_na_napravo(self):
        self.assertIn("most.posljiSpuscene(n.id)", self.js)
        self.assertIn('"posljiSpuscene": lambda: self._poslji_spuscene(*argumenti[:1])', self.py)
        self.assertIn("posljiSpuscene: function (id)", self.py)
        # Samo kjer GTK pove poti (GTK4): brez tega vrstica spusta ne sprejme.
        self.assertIn("window.__safeerLinkSpust = ", self.py)
        self.assertIn("var znaSpust = !!(most && most.znaSpust", self.js)

    def test_ni_vec_okna_za_vsako_prejeto_datoteko(self):
        self.assertNotIn("def _obvesti(self", self.py, "modalno okno »V redu« za vsako prejeto datoteko je umaknjeno")
        self.assertIn("self.prejem_datotek().prispela(", self.py)


if __name__ == "__main__":
    unittest.main()
