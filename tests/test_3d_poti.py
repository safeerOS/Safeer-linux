"""3D do konca (lastnik 10. 11. 2026: »3D ne sme prikazovati«): poti mimo tok_izbira.zdruzi_dvojnike - Usenet (samodejno,
samo Usenet, TorBox Usenet) in filter vira Usenet v mrezi - izlocijo 3D z ISTO funkcijo tok_izbira.je_3d; naslov s samo
3D izdajami ni na voljo. Brez omrezja: indeksator in dodatki so nadomestki."""
import tempfile
import unittest
from unittest import mock

from core import debrid, filter_vira_pravila as F, media_servers, os_media, tok_izbira  # noqa: F401
from core import usenet_pravila as U

GB = 1073741824
Z3D = U.Zadetek("Film.2010.1080p.3D.HSBS.BluRay.x264", "https://ix.primer/getnzb/a", 4 * GB)
ZNAVADEN = U.Zadetek("Film.2010.1080p.BluRay.x264", "https://ix.primer/getnzb/b", 4 * GB)


def _sifriraj(s):
    return "enc:" + s[::-1]


def _desifriraj(s):
    return s[4:][::-1] if s.startswith("enc:") else ""


class Lastni:
    def na_voljo(self):
        return True


def _debrid():
    shramba = {"d": {}}
    d = debrid.Debrid(lambda: shramba["d"], lambda x: shramba.__setitem__("d", x), _sifriraj, _desifriraj)
    d.lastni_usenet = Lastni()
    d.nastavi_indeksator("https://ix.primer", "0123456789abcdef0123456789abcdef")
    return d


class Usenet(unittest.TestCase):
    def test_usenet_isci_brez_3d(self):
        d = _debrid()
        with mock.patch.object(debrid, "usenet_isci", return_value=[Z3D, ZNAVADEN]):
            tokovi = d.usenet_isci("tt0000001")
        self.assertEqual([t["naslov"] for t in tokovi], [ZNAVADEN.naslov])

    def test_samo_3d_je_nic_izdaj(self):
        d = _debrid()
        with mock.patch.object(debrid, "usenet_iskanje", return_value=debrid.IzidIskanja([Z3D])):
            tokovi, izid = d.usenet_iskanje_tokov("tt0000001")
        self.assertEqual(tokovi, [])                     # odgovoril je, a predvajljive izdaje ni (ne None)
        self.assertEqual(F.razlog_iskanja(len(tokovi), izid.meja), F.RazlogIskanja.NI_IZDAJ)

    def test_samo_usenet_ne_predvaja_3d(self):
        with tempfile.TemporaryDirectory() as td:
            c = os_media.MediaCenter(td, roots=[], secret_encryptor=_sifriraj, secret_decryptor=_desifriraj)
            c.debrid.lastni_usenet = Lastni()
            c.debrid.nastavi_indeksator("https://ix.primer", "0123456789abcdef0123456789abcdef")
            c.debrid.nastavi_izbiro("usenet")
            c.usenet_filter.spi = lambda s: None
            item = {"id": "s:1", "naslov": "Film", "vrsta": "film", "url": "stremio:https://d.primer|movie|tt0000001"}
            c._dynamic_items[item["id"]] = item
            with mock.patch.object(debrid, "usenet_iskanje", return_value=debrid.IzidIskanja([Z3D])), \
                    mock.patch.object(c.debrid, "usenet_tok", side_effect=AssertionError("3D se ne predvaja")):
                r = c.resolve(item["id"])
            self.assertEqual(r["napaka_koda"], "usenet_ni_izdaj")


class FilterMreze(unittest.TestCase):
    Z = tok_izbira.Zmoznosti()
    P = F.Pogoji(F.VIR_USENET, najvec_gb=15.0)

    def test_samo_3d_ni_na_voljo(self):
        izidi = F.Izidi(F.Izid.NA_VOLJO, F.Odgovor([F.Izdaja(Z3D.naslov, 4.0)]))
        self.assertEqual(F.izid(izidi, self.P, self.Z), F.Izid.NI)
        self.assertEqual(F.pot(F.Izdaja(Z3D.naslov, 4.0), self.Z), F.Pot.NE)

    def test_znacka_ne_iz_3d(self):
        izdaje = [F.Izdaja("Film.2010.2160p.3D.HSBS.x265", 9.0), F.Izdaja(ZNAVADEN.naslov, 4.0)]
        self.assertEqual(F.oznaka(izdaje, self.P, self.Z).napis, "Full HD")


class RazpolozljivostDodatkov(unittest.TestCase):
    """Dodatki gredo skozi zdruzi_dvojnike (popravek 3D): naslov s samo 3D tokovi ni »na voljo«, z navadnim je."""

    def _na_voljo(self, tokovi):
        with tempfile.TemporaryDirectory() as td:
            c = os_media.MediaCenter(td, roots=[], secret_encryptor=_sifriraj, secret_decryptor=_desifriraj)
            c._stremio_strezniki = lambda: []
            with mock.patch.object(media_servers, "stremio_tokovi", return_value=list(tokovi)):
                return c._na_voljo("https://d.primer", "movie", "tt0000001")

    def test_samo_3d_ni_na_voljo(self):
        tok3d = {"url": "https://cdn.primer/f.mkv", "opis": "Film.2010.1080p.3D.HSBS", "vir": "D"}
        navaden = {"url": "https://cdn.primer/g.mkv", "opis": "Film.2010.1080p", "vir": "D"}
        self.assertIs(self._na_voljo([tok3d]), False)
        self.assertIs(self._na_voljo([tok3d, navaden]), True)


if __name__ == "__main__":
    unittest.main()
