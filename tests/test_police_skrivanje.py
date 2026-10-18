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
