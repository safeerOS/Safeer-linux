"""Police na Domov (Samodejni seznami, Nazadnje dodano): uporabnik jih skrije za stalno, skrite se ne naložijo."""
from pathlib import Path

from core.os_katalog import Katalog

KOREN = Path(__file__).resolve().parent.parent
OS_JS = (KOREN / "assets" / "os" / "os.js").read_text(encoding="utf-8")
BESEDILA = (KOREN / "assets" / "os" / "besedila.js").read_text(encoding="utf-8")


def _regex():
    return Katalog._SKRITO


def test_kljuci_polic_so_veljavni():
    r = _regex()
    assert r.match("polica:samodejni") and r.match("polica:nazadnje")
    assert r.match("kat:glasba") and r.match("vir:mape")
    assert not r.match("polica:") and not r.match("neki:samodejni")


def test_skrita_polica_se_ne_nalozi_in_ne_narise():
    assert 'jeSkrito("polica:samodejni")' in OS_JS
    assert 'jeSkrito("polica:" + p.id)' in OS_JS
    tel = OS_JS.split("function naloziSamodejne", 1)[1].split("function", 1)[0]
    assert 'jeSkrito("polica:samodejni")' in tel and "S.samodejni = []" in tel


def test_gumb_skrij_in_prilagodi_v_vseh_jezikih():
    assert "gumbSkrijPolico" in OS_JS and 'skupina("policaPrilagodi"' in OS_JS
    for jezik in ("sl", "en", "de", "es", "fr", "it"):
        assert f'BESEDILA_OS.{jezik}, {{"policaSkrij"' in BESEDILA


import unittest  # noqa: E402


class VsakaPolica(unittest.TestCase):
    """Lastnik 18. 10. 2026: ob »Vse« na vsaki polici Domov (tudi odkrivanje) je »Skrij«; v Prilagodi meni jih vklopi nazaj."""

    def setUp(self):
        import pathlib
        self.js = (pathlib.Path(__file__).resolve().parents[1] / "assets" / "os" / "os.js").read_text(encoding="utf-8")

    def test_skrij_na_vsaki_polici(self):
        self.assertIn('vrhPolice.appendChild(gumbSkrijPolico("polica:" + p.id, naslov));', self.js)
        self.assertIn('vrh.appendChild(gumbSkrijPolico("polica:" + p.id, naslov));', self.js)
        self.assertIn('!jeSkrito("polica:" + p.id); });', self.js)

    def test_prilagodi_vsebuje_vse_police(self):
        self.assertIn('Object.keys(POLICE_NASLOVI).forEach(function (id) {', self.js)


class SkritoSeNeNalozi(unittest.TestCase):
    """Lastnik 18. 10. 2026: skrita polica se ne nalozi in ne narise (pomnilnik), izbira je trajna, vklop v Prilagodi meni.
    Do tega popravka je jedro skrito polico (npr. Nazadnje dodano) vseeno bralo iz knjiznice in kataloga."""

    def setUp(self):
        import tempfile
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.dogodki = []
        self.k = self._katalog()

    def _katalog(self):
        k = Katalog(str(Path(self.mapa.name) / "media"), dogodek=lambda v, p: self.dogodki.append((v, p)),
                    v_glavni=lambda delo: delo(), predvajaj=lambda *a: True, vdelano=lambda u: True,
                    youtube=lambda u, n: True, youtube_ukaz=lambda u: True)
        k.klici = []
        for ime in ("nadaljuj", "nazadnje", "glasba", "najvec", "priljubljene"):
            setattr(k, "_polica_" + ime, (lambda i: lambda z, o: k.klici.append(i) or [])(ime))
        return k

    def test_skrita_polica_domov_se_ne_bere(self):
        self.k.izvedi("mediaPolice", ["domov", ""])
        self.assertIn("nazadnje", self.k.klici)
        self.k.klici.clear()
        self.k.izvedi("mediaSkrij", ["polica:nazadnje", True])
        self.k.izvedi("mediaPolice", ["domov", ""])
        self.assertNotIn("nazadnje", self.k.klici)
        self.assertIn("najvec", self.k.klici)
        # Trajno: nov zagon (nov Katalog na isti mapi) ve, kaj je skrito.
        drugi = self._katalog()
        self.assertEqual(drugi.izvedi("mediaSkrito", []), ["polica:nazadnje"])
        drugi.izvedi("mediaPolice", ["glasba", ""])
        self.assertNotIn("nazadnje", drugi.klici)
        # Spet vklopljena (Prilagodi meni) se nalozi.
        drugi.izvedi("mediaSkrij", ["polica:nazadnje", False])
        drugi.izvedi("mediaPolice", ["domov", ""])
        self.assertIn("nazadnje", drugi.klici)

    def test_skrita_polica_odkrivanja_in_skrit_zavihek_se_ne_nalozita(self):
        nalozeni = []
        vsi = ("odkrij_filmi", "odkrij_serije", "odkrij_glasba", "odkrij_youtube", "odkrij_spotify", "odkrij_twitch",
               "odkrij_radio")

        def viri(_drzava):
            return {ime: (lambda i: lambda: nalozeni.append(i) or [{"id": i, "naslov": i, "vrsta": "radio"}])(ime)
                    for ime in vsi}
        self.k._odkrij_viri = viri
        self.k._je_zaseben_opis = lambda: (lambda _d: False)
        self.k.ODKRIVANJE_CAKAJ_S = 2.0
        self.k.izvedi("mediaOdkrivanje", ["", []])
        self.assertEqual(sorted(nalozeni), sorted(vsi))
        self.assertIn("odkrij_radio", self.k._odkr["vir"])
        nalozeni.clear()
        self.k._odkr["vir"].clear()
        self.k.izvedi("mediaSkrij", ["polica:odkrij_radio", True])
        self.k.izvedi("mediaSkrij", ["kat:twitch", True])
        self.k.izvedi("mediaOdkrivanje", ["", []])
        self.assertNotIn("odkrij_radio", nalozeni)
        self.assertNotIn("odkrij_twitch", nalozeni)
        self.assertNotIn("odkrij_radio", self.k._odkr["vir"])
        # Osvezitev v ozadju skrite police je ne vrne v pomnilnik.
        self.k._odkrij_zapisi("odkrij_radio", [{"id": "x", "naslov": "x", "vrsta": "radio"}], True)
        self.assertNotIn("odkrij_radio", self.k._odkr["vir"])

    def test_stran_ob_spremembi_nalozi_police_znova(self):
        tel = OS_JS.split("function osveziPoliceSkrite", 1)[1].split("\n  }\n", 1)[0]
        self.assertIn("if (POL.nalozeno) naloziPolice();", tel)
        self.assertIn('if (S.mediaFilter === "domov") naloziOdkrivanje();', tel)
