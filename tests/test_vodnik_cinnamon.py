"""Vodnik ob prvem zagonu in pot nazaj na Cinnamon (lastnik, 17. 10. 2026): besedila v vseh sestih jezikih in vmesnik.
Logika v safeer_os (zastavica, safeer-os --nazaj-na-cinnamon) je v test_nazaj_na_cinnamon (skupina gtk4)."""
import os
import re
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JEZIKI = ("sl", "en", "de", "es", "fr", "it")


def beri(*pot) -> str:
    with open(os.path.join(KOREN, *pot), encoding="utf-8") as f:
        return f.read()


def bloki_besedil() -> dict:
    """{jezik: besedilo slovarja} iz assets/os/besedila.js.

    Kljuce, ki jih kasnejse vrstice dodajo z Object.assign(BESEDILA_OS.<jezik>, {"kljuc": "..."}) (npr. vrstaNakljucno
    iz Medijskega centra, 18. 10. 2026), pripnemo bloku tistega jezika v istem zapisu kot v slovarju."""
    s = beri("assets", "os", "besedila.js")
    zac = [(m.group(1), m.start()) for m in re.finditer(r"^  (sl|en|de|es|fr|it): \{", s, re.M)]
    konec = re.search(r"^Object\.assign\(", s, re.M)
    meja = konec.start() if konec else len(s)
    bloki = {j: s[z:(zac[i + 1][1] if i + 1 < len(zac) else meja)] for i, (j, z) in enumerate(zac)}
    for m in re.finditer(r"^Object\.assign\(BESEDILA_OS\.(sl|en|de|es|fr|it), \{(.*)\}\);$", s, re.M):
        bloki[m.group(1)] += "\n" + re.sub(r'"(\w+)": "', r'\1: "', m.group(2))
    return bloki


class Prevodi(unittest.TestCase):
    def test_vsi_novi_kljuci_v_vseh_jezikih(self):
        js, html = beri("assets", "os", "os.js"), beri("assets", "os", "index.html")
        kljuci = set(re.findall(r'\bt\("((?:vd|vr)[A-Za-z]+)"', js)) | set(re.findall(r'data-t="((?:vd|vr)[A-Za-z]+)"', html))
        koraki = re.search(r"var KORAKI_VODNIKA = \[([^\]]+)\]", js).group(1)
        for k in re.findall(r'"(\w+)"', koraki):        # t("vd" + k + "Naslov") in t("vd" + k + "Opis")
            kljuci |= {"vd%sNaslov" % k, "vd%sOpis" % k}
        kljuci |= {"vdPreskoci", "vdPozneje", "vdKoncaj", "vdNaprej", "vdKonecUkaz", "nazajVMint", "nazajOpis", "zaStalno"}
        self.assertGreater(len(kljuci), 25)
        bloki = bloki_besedil()
        self.assertEqual(sorted(bloki), sorted(JEZIKI))
        for jezik, blok in bloki.items():
            for k in sorted(kljuci):
                m = re.search(r'\b%s: "((?:[^"\\]|\\.)*)"' % k, blok)
                self.assertIsNotNone(m, "%s manjka v %s" % (k, jezik))
                self.assertTrue(m.group(1).strip(), "%s je prazen v %s" % (k, jezik))
                # Zamenjave ({n}, {m}) morajo biti v vseh jezikih enake.
                sl = re.search(r'\b%s: "((?:[^"\\]|\\.)*)"' % k, bloki["sl"]).group(1)
                self.assertEqual(sorted(re.findall(r"\{\w+\}", m.group(1))), sorted(re.findall(r"\{\w+\}", sl)), (k, jezik))

    def test_potrditev_omeni_ukaz_v_terminalu(self):
        for jezik, blok in bloki_besedil().items():
            self.assertIn("safeer-os --nazaj-na-cinnamon", re.search(r'\bnazajOpis: "([^"]*)"', blok).group(1), jezik)


class Vmesnik(unittest.TestCase):
    def test_vodnik_samo_v_glavnem_oknu(self):
        """Okno razdelka in Safeer Player koncata prej (return), vodnik se odpre samo v glavnem oknu."""
        js = beri("assets", "os", "os.js")
        i_pred = js.index("if (PREDVAJALNIK) return;     // stanje, odprta okna")
        i_razdelek = js.index("if (RAZDELEK) {", js.index('klic("zacetek").then'))
        i_vodnik = js.index("if (z.vodnik) odpriVodnik(); else if (z.vrnitev) odpriVrnitev();")
        self.assertLess(i_razdelek, i_vodnik)
        self.assertLess(i_pred, i_vodnik)

    def test_gumbi_in_sloji(self):
        html = beri("assets", "os", "index.html")
        for ime in ("slojVodnik", "slojVrnitev", "gumbVodnik", "vodnikPreskoci", "vodnikPreskociVse", "vodnikNaprej",
                    "vodnikNazaj", "vrnitevDa", "vrnitevNe", "mintZaStalno"):
            self.assertIn('id="%s"' % ime, html)
        js = beri("assets", "os", "os.js")
        # »Nazaj na Cinnamon« je vedno na voljo, ne samo ob vklopljenem zagonu ob prijavi.
        self.assertNotIn('$("mintZaStalno").hidden', js)
        # Vodnik ne obdeluje gesel: racuni gredo v obstojece prijave, Link v prijavno okno Controla.
        self.assertIn('klic("splet", [YT_PRIJAVA, true]); cakajYtPrijavo();', js)
        self.assertIn('gumb(t("vdSpotify"), spPrijava);', js)
        self.assertIn('klic("prijava")', js)

    def test_lupina_qml_sprejme_jezik(self):
        self.assertIn('vrsta === "jezik"', beri("assets", "os", "qml", "Namizje.qml"))


if __name__ == "__main__":
    unittest.main()


def test_nazaj_na_cinnamon_vrne_tudi_zagonski_zaslon():
    """Lastnik, 17. 10. 2026: »Nazaj na Cinnamon« vrne tudi Safeerjev zagonski in prijavni zaslon (sistem vpraša za
    skrbnisko geslo) - safeer-cinnamon --izklopi zato ne dobi SAFEER_CINNAMON_BREZ_SISTEMA."""
    import re
    with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
        koda = f.read()
    telo = re.search(r"def nazaj_na_cinnamon\(.*?\n(?=def )", koda, re.S).group(0)
    assert 'SAFEER_CINNAMON_BREZ_SISTEMA="1"' not in telo
    assert '"--izklopi"' in telo
