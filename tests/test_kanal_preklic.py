"""Vgrajeni kanal, ki se ni v uporabi (lastnik, 15. 10. 2026, testni PC): »Dodaj kanal › Gmail« je kanal dodal takoj in
odprl prijavo Googla v Sporocilih - ce si je uporabnik premislil, ni bilo izhoda (ne Preklici ne Zapri), kanal je
ostal na seznamu. Zdaj: kanal »caka«, dokler prijava ni koncana; »Preklici dodajanje« (tudi Esc / Nazaj) ga odstrani
in vrne uporabnika tja, kjer je bil; »Odstrani kanal« je v orodni vrstici z eno potrditvijo; carovnik ima Zapri in
Preklici vedno na zaslonu. Brez GTK in brez omrezja (nadomestki)."""
import json
import os
import re
import tempfile
import unittest
from unittest import mock

from core import os_kanali_sporocil, spletni_klepeti as sk

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class _Shramba(dict):
    def set(self, k, v):
        self[k] = json.loads(json.dumps(v))


class _Aplikacija:
    def __init__(self, uri):
        self._uri = uri

    def uri(self):
        return self._uri


class Caka(unittest.TestCase):
    def test_nov_kanal_caka_do_potrditve_stari_ne(self):
        s = _Shramba()
        s[sk.Kanali.KLJUC] = [{"id": "star", "katalog": "telegram", "ime": "Telegram",
                               "url": "https://web.telegram.org/a/", "vklopljen": True}]
        k = sk.Kanali(s)
        self.assertFalse(k.najdi("star")["caka"])           # kanali izpred te razlicice so v uporabi
        nov = k.dodaj(katalog="gmail")
        self.assertTrue(nov["caka"] and k.najdi("gmail")["caka"])
        self.assertTrue(k.potrdi("gmail"))
        self.assertFalse(k.najdi("gmail")["caka"])
        self.assertFalse(k.potrdi("gmail"))                # brez ponovnega zapisa

    def test_ista_stran(self):
        self.assertTrue(sk.ista_stran("https://mail.google.com/mail/u/0/#inbox", "https://mail.google.com/mail/"))
        self.assertFalse(sk.ista_stran("https://accounts.google.com/v3/signin/identifier", "https://mail.google.com/mail/"))
        self.assertFalse(sk.ista_stran("http://mail.google.com/mail/", "https://mail.google.com/mail/"))
        self.assertFalse(sk.ista_stran("", "https://mail.google.com/mail/"))
        self.assertFalse(sk.ista_stran("about:blank", "https://mail.google.com/mail/"))


class Preklic(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.okolje = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.d.name})
        self.okolje.start()
        self.dogodki = []
        self.k = os_kanali_sporocil.KanaliSporocil(
            None, None, None, lambda: None, _Shramba(), lambda: "sl",
            lambda ime, podatki: self.dogodki.append((ime, podatki)), lambda kid: None, obvestila=object())
        self.k._ustvari = lambda kanal: None              # brez WebKita: zivi kanal po potrebi nastavi preizkus
        self.k.kanali.dodaj(katalog="gmail")

    def tearDown(self):
        self.okolje.stop()
        self.d.cleanup()

    def _zivi(self, uri):
        z = os_kanali_sporocil._Kanal(self.k.kanali.najdi("gmail"))
        z.aplikacija = _Aplikacija(uri)
        self.k.zivi["gmail"] = z

    def test_preklic_odstrani_kanal_ki_caka_brez_brisanja_podatkov(self):
        with mock.patch.object(self.k, "_izbrisi_podatke_strani") as brisi:
            seznam = self.k.preklici("gmail")
        self.assertEqual(seznam, [])
        brisi.assert_not_called()                          # seja je skupna s Spletom: prijava tam ostane

    def test_kanala_v_uporabi_preklic_ne_odstrani(self):
        self.k.kanali.potrdi("gmail")
        with self.assertRaises(ValueError):
            self.k.preklici("gmail")
        self.assertIsNotNone(self.k.kanali.najdi("gmail"))

    def test_odhod_s_prijave_ostane_v_cakanju_odhod_s_strani_kanala_potrdi(self):
        self._zivi("https://accounts.google.com/v3/signin/identifier")
        pogled = mock.Mock()
        plast = self.k.plasti[id(pogled)] = {"sklad": mock.Mock(), "kanal": "gmail"}
        self.k.skrij(pogled)
        self.assertTrue(self.k.kanali.najdi("gmail")["caka"])     # prijava ni koncana: »Preklici« ostane
        self.k.zivi["gmail"].aplikacija = _Aplikacija("https://mail.google.com/mail/u/0/#inbox")
        plast["kanal"] = "gmail"
        self.k.skrij(pogled)
        self.assertFalse(self.k.kanali.najdi("gmail")["caka"])
        self.assertIn("kanaliSporocil", [d[0] for d in self.dogodki])

    def test_esc_in_nazaj_samo_dokler_caka(self):
        self.assertTrue(self.k._tipka("gmail", 0xff1b))           # Esc
        self.assertTrue(self.k._tipka("gmail", 0x1008ff26))       # Nazaj (daljinec)
        self.assertEqual(self.dogodki[-1], ("kanalPreklici", "gmail"))
        self.assertFalse(self.k._tipka("gmail", 0x61))            # »a« gre v stran
        self.k.kanali.potrdi("gmail")
        n = len(self.dogodki)
        self.assertFalse(self.k._tipka("gmail", 0xff1b))          # kanal v uporabi: Esc dobi stran kanala
        self.assertEqual(len(self.dogodki), n)


class Vmesnik(unittest.TestCase):
    def test_orodna_vrstica_in_carovnik(self):
        html = _beri("assets", "os", "index.html")
        self.assertIn('id="vgrajenKanalPreklici" data-t="kanalPrekliciDodajanje"', html)
        self.assertIn('id="vgrajenKanalOdstrani" data-naslov="odstraniKanal"', html)
        self.assertIn('<button type="button" class="gumb-ikona" id="kanalZapri" data-naslov="zapri">', html)
        css = _beri("assets", "os", "os.css")
        self.assertRegex(css, r"\.kanal-carovnik-glava \{ position:sticky; top:-20px;")
        self.assertRegex(css, r"#obrazecKanal > \.gumbi \{ position:sticky; bottom:-20px;")
        js = _beri("assets", "os", "os.js")
        self.assertIn('$("vgrajenKanalPreklici").hidden = !k.caka;', js)
        self.assertIn('if (vrsta === "kanalPreklici") vkPrekliciDodajanje(String(podatki || ""));', js)
        self.assertIn('klicKanala("kanalPreklici", [k.id])', js)
        self.assertIn('VK.prej = { razdelek: S.razdelek, kanal: VK.aktivni };', js)
        self.assertIn('klicKanala("kanalOdstrani", [k.id, false])', js)
        py = _beri("safeer_os.py")
        self.assertIn('"kanalPreklici": lambda: self._kanali_klic("preklici"', py)

    def test_besedila_v_vseh_jezikih(self):
        js = _beri("assets", "os", "besedila.js")
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            m = re.search(r'Object\.assign\(BESEDILA_OS\.%s, \{"kanalPrekliciDodajanje": "[^"]+", "kanalPrekliciNamig": '
                          r'"[^"]+", "kanalDodajanjePreklicano": "[^"]*\{ime\}[^"]*"\}\);' % jezik, js)
            self.assertIsNotNone(m, jezik)


if __name__ == "__main__":
    unittest.main()
