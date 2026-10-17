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
