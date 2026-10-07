"""Okno z zaslonom druge naprave: ko ga uporabnik zapre, naprava to izve.

V živo, 7. 10. 2026: po zaprtju okna »Odpri tukaj« na računalniku je tablica zaslon delila naprej (storitev deljenja
je ostala v ospredju) in igra je igrala naprej - računalnik ob zaprtju okna napravi ni sporočil ničesar.
Zdaj Control pošlje ukaz `apps.close` s `stream: true` - »tega zaslona ne gledam več«. Ali je sejo odprl »Odpri tukaj«
(in je treba aplikacijo umakniti z zaslona), ve naprava iz svojega zapisa seje; računalnik tega ne trdi, ker bi njegov
zapis lahko zastaral (drugi neodvisni pregled, 7. 10. 2026). Kadar deljenje konča naprava sama, Control ne pošilja ničesar.

Okno gledalca je eno samo, zato si Control zapomni, katero napravo kaže (tretji neodvisni pregled, 7. 10. 2026): ko ga
zamenja deljenje druge naprave, prejšnja izve, da je ne gledamo več; dotiki in zaprtje okna veljajo za napravo, ki jo
okno res kaže.
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

    def test_katerim_napravam(self):
        # Obicajno je naprava, ki jo okno kaze, ista kot tista, ki jo Link steje za gledano. Razlicni sta, ce se strani
        # novega deljenja ni dalo odpreti: takrat nehata obe (okno se zapira, nobene ne gledamo vec).
        f = safeer_control.naprave_konca_gledanja
        self.assertEqual(f("n-1", "n-1"), ["n-1"])
        self.assertEqual(f("n-1", "n-2"), ["n-1", "n-2"])
        self.assertEqual(f("", "n-2"), ["n-2"])
        self.assertEqual(f("n-1", ""), ["n-1"])
        self.assertEqual(f("", ""), [])
        self.assertEqual(f(None, None), [])


class Konec(unittest.TestCase):
    def _lazna(self, gledani="n-1", prikazana=None):
        lazna = mock.MagicMock()
        lazna.link.gledani_zaslon = gledani
        lazna.link.gledani_zaslon_id = "d1"
        lazna._gledalec_naprava = gledani if prikazana is None else prikazana
        lazna._povej_konec_gledanja = lambda cilji, pocakaj=0.0: safeer_control.SafeerControl._povej_konec_gledanja(
            lazna, cilji, pocakaj)
        return lazna

    def _niti(self, nit):
        """Pozene delo vseh niti, ki bi jih koda zagnala."""
        for klic in nit.call_args_list:
            klic.kwargs["target"]()

    def test_poslje_apps_close_in_pozabi_gledanje(self):
        lazna = self._lazna()
        with mock.patch.object(safeer_control.threading, "Thread") as nit:
            safeer_control.SafeerControl._konec_gledanja(lazna)
        nit.assert_called_once()
        self._niti(nit)
        lazna.link.ukaz_pocakaj.assert_called_once_with("n-1", "apps.close", {"stream": True}, cas=5.0)
        self.assertEqual(lazna.link.gledani_zaslon, "")                          # klikov ne posiljamo vec tja
        self.assertEqual(lazna.link.gledani_zaslon_id, "")
        self.assertEqual(lazna._gledalec_naprava, "")

    def test_brez_gledanja_ali_povezave_nic(self):
        lazna = self._lazna(gledani="")
        with mock.patch.object(safeer_control.threading, "Thread") as nit:
            safeer_control.SafeerControl._konec_gledanja(lazna)
        nit.assert_not_called()
        lazna = mock.MagicMock()
        lazna.link = None
        lazna._gledalec_naprava = "n-1"
        with mock.patch.object(safeer_control.threading, "Thread") as nit:
            safeer_control.SafeerControl._konec_gledanja(lazna)
        nit.assert_not_called()

    def test_zaprtje_pove_napravi_ki_jo_okno_kaze(self):
        # Gledamo A, deljenje je zacela B, strani za B pa ni bilo mogoce odpreti: okno se kaze A. Prej je zaprtje okna
        # dobila samo B, A je delila naprej.
        lazna = self._lazna(gledani="n-B", prikazana="n-A")
        with mock.patch.object(safeer_control.threading, "Thread") as nit:
            safeer_control.SafeerControl._konec_gledanja(lazna)
        self._niti(nit)
        self.assertEqual([k.args[0] for k in lazna.link.ukaz_pocakaj.call_args_list], ["n-A", "n-B"])
        for k in lazna.link.ukaz_pocakaj.call_args_list:
            self.assertEqual(k.args[1:], ("apps.close", {"stream": True}))
        self.assertEqual((lazna.link.gledani_zaslon, lazna._gledalec_naprava), ("", ""))

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
        konec = s[s.index("    def _povej_konec_gledanja(self"):s.index("    def _zapri_gledalca(self)")]
        self.assertIn("parametri_konca_gledanja(cilj)", konec)


class Zamenjava(unittest.TestCase):
    """Okno je eno samo: ko pokaze drugo napravo, prejsnja izve, da je ne gledamo vec."""

    def _lazna(self, gledani, prikazana):
        lazna = mock.MagicMock()
        lazna.link.gledani_zaslon = gledani
        lazna._gledalec_naprava = prikazana
        lazna._povej_konec_gledanja = lambda cilji, pocakaj=0.0: safeer_control.SafeerControl._povej_konec_gledanja(
            lazna, cilji, pocakaj)
        return lazna

    def test_prejsnja_naprava_neha_deliti(self):
        lazna = self._lazna(gledani="n-B", prikazana="n-A")
        with mock.patch.object(safeer_control.threading, "Thread") as nit:
            safeer_control.SafeerControl._odpri_gledalca(lazna, "https://127.0.0.1:8990/zaslon")
        lazna.gledalec.get_child.return_value.load_uri.assert_called_once_with("https://127.0.0.1:8990/zaslon")
        self.assertEqual(lazna._gledalec_naprava, "n-B")
        for klic in nit.call_args_list:
            klic.kwargs["target"]()
        lazna.link.ukaz_pocakaj.assert_called_once_with("n-A", "apps.close", {"stream": True}, cas=5.0)

    def test_ista_naprava_ali_prvo_odpiranje_ne_posilja(self):
        for prikazana in ("n-B", ""):
            lazna = self._lazna(gledani="n-B", prikazana=prikazana)
            with mock.patch.object(safeer_control.threading, "Thread") as nit:
                safeer_control.SafeerControl._odpri_gledalca(lazna, "https://127.0.0.1:8990/zaslon")
            nit.assert_not_called()
            self.assertEqual(lazna._gledalec_naprava, "n-B")

    def test_konec_z_druge_strani_pozabi_napravo(self):
        lazna = self._lazna(gledani="", prikazana="n-A")
        safeer_control.SafeerControl._zapri_gledalca(lazna)
        self.assertEqual(lazna._gledalec_naprava, "")
        self.assertIsNone(lazna.gledalec)

    def test_dotiki_gredo_samo_napravi_ki_jo_okno_kaze(self):
        def vnos(lazna):
            rezultat = mock.MagicMock()
            rezultat.get_js_value.return_value.to_string.return_value = '{"d": "input.tap", "p": {"x": 0.5, "y": 0.5}}'
            safeer_control.SafeerControl._vnos_iz_gledalca(lazna, None, rezultat)
        lazna = self._lazna(gledani="n-A", prikazana="n-A")
        vnos(lazna)
        lazna.link.poslji_vnos.assert_called_once_with("input.tap", {"x": 0.5, "y": 0.5})
        # Link ze steje B za gledano, okno pa se kaze A: dotik na sliki A ne sme iti B.
        lazna = self._lazna(gledani="n-B", prikazana="n-A")
        vnos(lazna)
        lazna.link.poslji_vnos.assert_not_called()

    def test_izhod_iz_controla_pove_napravi_pred_zaprtjem_povezave(self):
        with open(os.path.join(KOREN, "safeer_control.py"), encoding="utf-8") as f:
            s = f.read()
        izhod = s[s.index("    def koncaj_brez_izhoda(self)"):s.index("                self.link.povezava.zapri()")]
        self.assertIn("self._konec_gledanja(pocakaj=1.0)", izhod)
        # Delo steče v niti, glavna nit nanjo pocaka najvec toliko, kot je receno.
        lazna = self._lazna(gledani="n-A", prikazana="n-A")
        with mock.patch.object(safeer_control.threading, "Thread") as nit:
            safeer_control.SafeerControl._konec_gledanja(lazna, pocakaj=1.0)
        nit.return_value.start.assert_called_once_with()
        nit.return_value.join.assert_called_once()
        self.assertLessEqual(nit.return_value.join.call_args.args[0], 1.0)


if __name__ == "__main__":
    unittest.main()
