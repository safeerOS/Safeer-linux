import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

from core import os_player_gtk


class TestPlayerGTK(unittest.TestCase):
    def test_format_cas(self):
        self.assertEqual(os_player_gtk._format_cas(0), "0:00")
        self.assertEqual(os_player_gtk._format_cas(5), "0:05")
        self.assertEqual(os_player_gtk._format_cas(65), "1:05")
        self.assertEqual(os_player_gtk._format_cas(3600), "1:00:00")
        self.assertEqual(os_player_gtk._format_cas(3665), "1:01:05")

    def test_init_window(self):
        # Inicializacija okna SafeerPlayerOkno
        with patch("core.os_knjiznica.Knjiznica.seznam", return_value=[]), \
             patch("core.os_knjiznica.Knjiznica.tokovi", return_value=[]):
            okno = os_player_gtk.SafeerPlayerOkno(iskanje="test")
            self.assertEqual(okno.get_title(), "Safeer Player")
            self.assertEqual(okno.trenutno_iskanje, "test")
            self.assertEqual(okno.sklad.get_visible_child_name(), "knjiznica")
            okno.destroy()

    def test_kategorije_in_iskanje(self):
        with patch("core.os_knjiznica.Knjiznica.seznam", return_value=[
            {"pot": "/tmp/film.mp4", "naslov": "Moj Film", "vrsta": "filmi"},
            {"pot": "/tmp/pesem.mp3", "naslov": "Moja Pesem", "vrsta": "glasba"}
        ]):
            okno = os_player_gtk.SafeerPlayerOkno()
            okno.osvezi_zbirko()
            self.assertFalse(okno.prazno_box.get_visible())
            self.assertTrue(okno.flowbox.get_visible())

            # Izbira kategorije
            okno._ob_izbiri_kategorije(None, "filmi")
            self.assertEqual(okno.izbrana_kategorija, "filmi")
            okno.destroy()

    def test_predvajaj_pot(self):
        with patch("core.os_knjiznica.Knjiznica.seznam", return_value=[]):
            okno = os_player_gtk.SafeerPlayerOkno()
            # Simuliraj predvajanje
            if okno.predvajalnik is not None:
                okno.predvajalnik.zamenjaj_vrsto = MagicMock(return_value=True)
                ok = okno.predvajaj_pot("http://localhost/test.mp4", naslov="Test Video", vrsta="video")
                self.assertTrue(ok)
                self.assertEqual(okno.sklad.get_visible_child_name(), "predvajanje")
                self.assertEqual(okno.bar_naslov.get_text(), "Test Video")
            okno.destroy()

    def test_ob_tipki(self):
        with patch("core.os_knjiznica.Knjiznica.seznam", return_value=[]):
            okno = os_player_gtk.SafeerPlayerOkno()
            okno._ukaz = MagicMock()

            # Simuliraj dogodek preslednice
            dogodek_space = MagicMock()
            dogodek_space.keyval = 32  # space
            dogodek_space.state = 0
            with patch("gi.repository.Gdk.keyval_name", return_value="space"):
                ujeto = okno._ob_tipki(okno, dogodek_space)
                self.assertTrue(ujeto)
                okno._ukaz.assert_called_with("premor")

            # Simuliraj puščico levo
            with patch("gi.repository.Gdk.keyval_name", return_value="Left"):
                ujeto = okno._ob_tipki(okno, dogodek_space)
                self.assertTrue(ujeto)

            okno.destroy()


if __name__ == "__main__":
    unittest.main()
