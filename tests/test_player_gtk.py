"""GTK Safeer Player (core/os_player_gtk.py) na istem mostu kot spletni Medijski center.

Okno dobi lazen most, ki zapise klice in odgovori kot Safeer OS; preverimo, da okno klice prave metode mostu in iz
odgovorov narise, kar pokaze stran (kartice z imeni, prazno stanje, predvajalni trak, cakalna vrsta).
"""
import os
import unittest

try:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk
    IMA_ZASLON = Gtk.init_check()[0]
except Exception:  # noqa: BLE001
    IMA_ZASLON = False

from core import os_most_nativni


class LazenMost(os_most_nativni.NativniPogled):
    def __init__(self, odgovori):
        self.klici = []
        self.odgovori = odgovori
        super().__init__(self._poslji)

    def _poslji(self, pogled, id_, metoda, a):
        self.klici.append((metoda, a))
        odgovor = self.odgovori.get(metoda)
        pogled.odgovor(id_, True, odgovor(a) if callable(odgovor) else odgovor)


KNJIZNICA = [{"pot": "/m/a.ogg", "ime": "ACDC - Whole Lotta Rosie", "vrsta": "glasba", "pozicija": 0, "trajanje": 0,
              "naVoljo": True},
             {"pot": "/m/film.mkv", "ime": "Film", "vrsta": "filmi", "pozicija": 600, "trajanje": 5400, "naVoljo": True},
             {"pot": "/m/manjka.ogg", "ime": "Manjka", "vrsta": "glasba", "naVoljo": False}]


def _besedila(w):
    """Vsa besedila oznak v gradniku (rekurzivno)."""
    izid = []
    if isinstance(w, Gtk.Label):
        izid.append(w.get_text())
    if isinstance(w, Gtk.Container):
        for o in w.get_children():
            izid += _besedila(o)
    return izid


@unittest.skipUnless(IMA_ZASLON, "ni zaslona (xvfb-run)")
class OknoNaMostu(unittest.TestCase):
    def _okno(self, knjiznica=KNJIZNICA, **odgovori):
        from core import os_player_gtk
        privzeto = {"knjiznicaMedijev": knjiznica, "dvdPogoni": [], "medijskeMape": [{"pot": "/m", "stevilo": 3,
                    "naVoljo": True}], "tokoviMedijev": [], "predvajalnikStanje": {"stanje": "ustavljeno", "naslov": ""},
                    "odpriLokalniMedij": True}
        privzeto.update(odgovori)
        most = LazenMost(privzeto)
        okno = os_player_gtk.SafeerPlayerOkno(most=most)
        okno.t = __import__("core.os_besedila", fromlist=["Prevajalnik"]).Prevajalnik("sl")
        return okno, most

    def test_knjiznica_po_mostu_in_imena_na_karticah(self):
        okno, most = self._okno()
        metode = [m for m, _ in most.klici]
        for m in ("dvdPogoni", "medijskeMape", "tokoviMedijev", "predvajalnikStanje", "knjiznicaMedijev"):
            self.assertIn(m, metode)
        self.assertIn(("knjiznicaMedijev", ["vse", "", 0]), most.klici)
        besedila = _besedila(okno.mreza)
        self.assertIn("ACDC - Whole Lotta Rosie", besedila, "ime iz polja »ime« (prej »Neznano«)")
        self.assertIn("Nadaljuj · 10:00", besedila)
        self.assertTrue(any("Datoteka ni dosegljiva" in b for b in besedila))
        self.assertFalse(okno.prazno.get_visible())
        okno.destroy()

    def test_prazna_knjiznica_in_filter(self):
        okno, most = self._okno(knjiznica=[])
        okno.show_all()
        self.assertTrue(okno.prazno.get_visible(), "prazno stanje, ko ni vsebin")
        okno.izberi_filter("glasba")
        self.assertIn(("knjiznicaMedijev", ["glasba", "", 0]), most.klici)
        okno.izberi_filter("radio")
        self.assertFalse(okno.blok_knjiznice.get_visible(), "TV in radio nimata knjiznice datotek")
        okno.destroy()

    def test_odpri_in_predvajalnik(self):
        okno, most = self._okno()
        okno.odpri_vnos(KNJIZNICA[0], KNJIZNICA)
        self.assertIn(("odpriLokalniMedij", ["/m/a.ogg"]), most.klici)
        okno.osvezi_predvajalnik({"stanje": "predvaja", "naslov": "ACDC", "vrsta": "glasba", "indeks": 0,
                                  "zacetniIndeks": 0, "skupaj": 2, "pozicija": 65, "trajanje": 300,
                                  "vrstaSeznam": [{"naslov": "ACDC", "vrsta": "glasba"}, {"naslov": "Druga", "vrsta": "glasba"}]})
        self.assertTrue(okno.trak.get_visible())
        self.assertEqual(okno.trak_cas.get_text(), "1:05")
        self.assertEqual(okno.trak_trajanje.get_text(), "5:00")
        self.assertEqual(okno.trak_premor.get_label(), "Ⅱ")
        self.assertFalse(okno.trak_prejsnja.get_sensitive())
        self.assertTrue(okno.trak_naslednja.get_sensitive())
        self.assertIn("Druga", _besedila(okno.vrsta))
        okno.ukaz("predvajaj", 1)
        self.assertIn(("predvajalnikUkaz", ["predvajaj", 1]), most.klici)
        # Dogodek mostu »predvajalnik« osvezi okno kot stran.
        okno.most.dogodek("predvajalnik", {"stanje": "ustavljeno", "naslov": "ACDC", "vrsta": "glasba"})
        self.assertFalse(okno.trak.get_visible())
        okno.destroy()

    def test_zivi_tok_brez_drsnika(self):
        okno, _most = self._okno()
        okno.osvezi_predvajalnik({"stanje": "predvaja", "naslov": "Val 202", "vrsta": "radio", "indeks": 0, "skupaj": 1})
        self.assertEqual(okno.trak_cas.get_text(), "V živo")
        self.assertFalse(okno.trak_napredek.get_visible())
        self.assertFalse(okno.gumb_odpri_video.get_visible(), "radio nima okna videa")
        okno.destroy()


class SlogGtk(unittest.TestCase):
    """Slog GTK Safeer Playerja: GTK 3 zavrne cel slog ob eni neznani vrednosti (11. 10. 2026: font-weight 750 in
    letter-spacing - okno se ni odprlo). Razred ne sme biti »safeer-player« (to je slog okna videa v safeer_os.py)."""

    @unittest.skipUnless(IMA_ZASLON, "ni zaslona (xvfb-run)")
    def test_slog_se_nalozi(self):
        from core import os_player_gtk
        Gtk.CssProvider().load_from_data(os_player_gtk.CSS)
        self.assertNotIn(b".safeer-player", os_player_gtk.CSS)

    def test_ikone_iz_strani(self):
        from core import os_player_gtk_ikone as ik
        ikone = ik.preberi()
        for ime in ("glasba", "video", "radio", "slika", "mapa", "x", "ponovno", "plus", "programi"):
            self.assertIn(ime, ikone)
        self.assertIn('stroke-width="1.8"', ik.svg("glasba"))


if __name__ == "__main__":
    unittest.main()
