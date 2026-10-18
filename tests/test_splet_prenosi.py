"""Prenosi v Spletu (GTK4) in Safeer Browserju: skupna pravila v core/splet_prenosi.py (14. 10. 2026)."""
import os
import tempfile

from core import splet_prenosi as sp

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_ime_iz_glave_ne_iz_naslova():
    assert sp.ime_prenosa("Porocilo%20Q3.pdf", "https://x.si/prenesi?id=5") == "Porocilo Q3.pdf"
    assert sp.ime_prenosa("", "https://x.si/mapa/navodila.odt") == "navodila.odt"
    assert sp.ime_prenosa("../../.bashrc", "") == ".bashrc"
    assert sp.ime_prenosa("", "https://x.si/") == "prenos_datoteke"


def test_programi_potrebujejo_potrditev():
    for ime in ("setup.exe", "paket.DEB", "igra.AppImage", "x.sh.", "a.flatpakref"):
        assert sp.je_izvrsljiv_prenos(ime), ime
    for ime in ("slika.png", "dokument.pdf", "arhiv.tar.gz"):
        assert not sp.je_izvrsljiv_prenos(ime), ime


def test_obstojeca_datoteka_ni_prepisana():
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "a.tar.gz"), "w").close()
        assert sp.edinstvena_pot(d, "a.tar.gz") == os.path.join(d, "a (1).tar.gz")
        assert sp.edinstvena_pot(d, "../b.txt") == os.path.join(d, "b.txt")


def test_mapa_xdg():
    class G:
        class UserDirectory:
            DIRECTORY_DOWNLOAD = 2

        @staticmethod
        def get_user_special_dir(_):
            return tempfile.gettempdir()
    assert sp.mapa_prenosov(G) == tempfile.gettempdir()


def test_besedila_v_vseh_jezikih():
    kljuci = set(sp.BESEDILA["sl"])
    for j in ("en", "de", "es", "fr", "it"):
        assert set(sp.BESEDILA[j]) == kljuci, j
    for j, b in sp.BESEDILA.items():
        assert "{ime}" in b["pr_program_opis"] and "{mapa}" in b["pr_program_opis"], j


def test_splet_in_brskalnik_uporabljata_isto_kodo():
    splet = open(os.path.join(KOREN, "core", "os_splet.py"), encoding="utf-8").read()
    assert "splet_prenosi.edinstvena_pot" in splet and "splet_prenosi.je_izvrsljiv_prenos" in splet
    assert 'expanduser("~/Downloads")' not in splet


def test_splet_ima_zunanje_programe_in_okna_z_opener():
    """14. 10. 2026: mailto:/magnet:/claude:// so bili v Spletu tiho prezrti, window.open brez opener (prijave)."""
    splet = open(os.path.join(KOREN, "core", "os_splet.py"), encoding="utf-8").read()
    assert "external_apps.external_scheme(naslov)" in splet and "UriLauncher" in splet
    assert "related_view=povezan" in splet and 'nov.connect("close"' in splet
