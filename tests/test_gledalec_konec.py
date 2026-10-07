"""Okno z zaslonom druge naprave: ko ga uporabnik zapre, naprava to izve.

V živo, 7. 10. 2026: po zaprtju okna »Odpri tukaj« na računalniku je tablica zaslon delila naprej (storitev deljenja
je ostala v ospredju) in igra je igrala naprej - računalnik ob zaprtju okna napravi ni sporočil ničesar.
Zdaj Control pošlje ukaz `apps.close` s `stream: true` - »tega zaslona ne gledam več«. Ali je sejo odprl »Odpri tukaj«
(in je treba aplikacijo umakniti z zaslona), ve naprava iz svojega zapisa seje; računalnik tega ne trdi, ker bi njegov
zapis lahko zastaral (drugi neodvisni pregled, 7. 10. 2026). Kadar deljenje konča naprava sama, Control ne pošilja ničesar.
"""
import os
import unittest
from unittest import mock

import safeer_control

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Parametri(unittest.TestCase):
    def test_komu_in_kaj(self):
        f = safeer_control.parametri_konca_gledanja
        self.assertIsNone(f(""))                                                 # nikogar ne gledamo
        self.assertEqual(f("n-1"), {"stream": True})


class Konec(unittest.TestCase):
    def _lazna(self, gledani="n-1"):
        lazna = mock.MagicMock()
        lazna.link.gledani_zaslon = gledani
        lazna.link.gledani_zaslon_id = "d1"
        return lazna

    def test_poslje_apps_close_in_pozabi_gledanje(self):
        lazna = self._lazna()
        with mock.patch.object(safeer_control.threading, "Thread") as nit:
            safeer_control.SafeerControl._konec_gledanja(lazna)
        nit.assert_called_once()
        nit.call_args.kwargs["target"]()                                         # delo niti
        lazna.link.ukaz_pocakaj.assert_called_once_with("n-1", "apps.close", {"stream": True}, cas=5.0)
        self.assertEqual(lazna.link.gledani_zaslon, "")                          # klikov ne posiljamo vec tja
        self.assertEqual(lazna.link.gledani_zaslon_id, "")

    def test_brez_gledanja_ali_povezave_nic(self):
        lazna = self._lazna(gledani="")
        with mock.patch.object(safeer_control.threading, "Thread") as nit:
            safeer_control.SafeerControl._konec_gledanja(lazna)
        nit.assert_not_called()
        lazna = mock.MagicMock()
        lazna.link = None
        with mock.patch.object(safeer_control.threading, "Thread") as nit:
            safeer_control.SafeerControl._konec_gledanja(lazna)
        nit.assert_not_called()

    def test_okno_loci_uporabnika_od_konca_z_druge_strani(self):
        with open(os.path.join(KOREN, "safeer_control.py"), encoding="utf-8") as f:
            s = f.read()
        odpri = s[s.index("    def _odpri_gledalca(self, url: str)"):s.index("    def _zapri_gledalca(self)")]
        # Uporabnik zapre okno: self.gledalec je se to okno. _zapri_gledalca (konec z druge strani) ga prej odstrani.
        self.assertIn("uporabnik = self.gledalec is okno", odpri)
        self.assertIn("if uporabnik:\n                    self._konec_gledanja()", odpri)
        zapri = s[s.index("    def _zapri_gledalca(self)"):s.index("    def _vnos_iz_gledalca(")]
        self.assertLess(zapri.index("self.gledalec = None"), zapri.index("okno.destroy()"))

    def test_racunalnik_ne_trdi_kaj_je_odprl(self):
        # Zapis »odprl sem aplikacijo X na napravi N« v Controlu ni vezan na sejo deljenja in zastara: soglasje na
        # napravi ni bilo dano, cilj je racunalnik z drugim gledalcem ... Poznejse deljenje, ki ga je naprava zacela
        # sama, bi ob zaprtju okna dobilo `app` - naprava bi sla na domaci zaslon pod prsti, racunalnik bi zaprl
        # program. Zato Control takega zapisa nima; odloca naprava.
        with open(os.path.join(KOREN, "safeer_control.py"), encoding="utf-8") as f:
            s = f.read()
        self.assertNotIn("_odpri_tukaj", s)
        konec = s[s.index("    def _konec_gledanja(self)"):s.index("    def _zapri_gledalca(self)")]
        self.assertIn("parametri_konca_gledanja(cilj)", konec)


if __name__ == "__main__":
    unittest.main()
