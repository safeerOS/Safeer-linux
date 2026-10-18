"""Register storitev na zahtevo in ena ura procesa (core/storitve_na_zahtevo.py, lastnik 18. 10. 2026)."""
import threading
import time
import unittest

from core import storitve_na_zahtevo as snz


class _Lazna:
    """Storitev: tece / ustavi / zaposlena kot pri pravih (rqbit, Teamwork)."""

    def __init__(self):
        self.tece = True
        self.zaposlena = False
        self.ustavljena = threading.Event()

    def ustavi(self):
        self.tece = False
        self.ustavljena.set()


class Register(unittest.TestCase):
    def setUp(self):
        snz._za_preizkus()

    def tearDown(self):
        snz._za_preizkus()

    def _registriraj(self, ime="torrent", mirovanje=600.0):
        s = _Lazna()
        snz.registriraj(ime, snz.NA_ZAHTEVO, mirovanje, tece=lambda: s.tece, ustavi=s.ustavi,
                        zaposlena=lambda: s.zaposlena, pidi=lambda: [1234])
        return s

    def test_ustavi_sele_po_roku_mirovanja(self):
        s = self._registriraj()
        zdaj = 1_000_000.0
        snz.rabi("torrent", zdaj)
        snz.tik(zdaj=zdaj + 599)
        self.assertFalse(s.ustavljena.wait(0.2))
        snz.tik(zdaj=zdaj + 600)
        self.assertTrue(s.ustavljena.wait(2))
        self.assertTrue(_cakaj(lambda: snz.storitev("torrent").ustavitev == 1))

    def test_raba_in_delo_podaljsata(self):
        s = self._registriraj()
        zdaj = 1_000_000.0
        snz.rabi("torrent", zdaj)
        snz.rabi("torrent", zdaj + 500)              # nova raba: rok steje od nje
        snz.tik(zdaj=zdaj + 700)
        self.assertFalse(s.ustavljena.wait(0.2))
        s.zaposlena = True                           # prenos tece: ne ustavi in rok steje od konca dela
        snz.tik(zdaj=zdaj + 5000)
        self.assertFalse(s.ustavljena.wait(0.2))
        s.zaposlena = False
        snz.tik(zdaj=zdaj + 5000 + 599)
        self.assertFalse(s.ustavljena.wait(0.2))
        snz.tik(zdaj=zdaj + 5000 + 600)
        self.assertTrue(s.ustavljena.wait(2))

    def test_brez_javljene_rabe_rok_od_prvega_pregleda(self):
        s = self._registriraj()
        snz.tik(zdaj=2_000_000.0)                    # tece, a rabe ni javila: ne ustavi takoj
        self.assertFalse(s.ustavljena.wait(0.2))
        snz.tik(zdaj=2_000_000.0 + 600)
        self.assertTrue(s.ustavljena.wait(2))

    def test_vedno_in_ustavljena_se_ne_ustavita(self):
        vedno = threading.Event()
        snz.registriraj("scit", snz.VEDNO, 1.0, tece=lambda: True, ustavi=vedno.set, razlog=snz.VARUJE)
        s = self._registriraj()
        s.tece = False
        snz.tik(zdaj=time.time() + 10 ** 6)
        self.assertFalse(vedno.wait(0.2))
        self.assertFalse(s.ustavljena.is_set())

    def test_stanje_za_stran(self):
        self._registriraj()
        snz.registriraj("scit", snz.VEDNO, tece=lambda: False, razlog=snz.VARUJE)
        snz.registriraj("teamwork", snz.NA_ZAHTEVO, 60, tece=lambda: False)
        zdaj = time.time()
        snz.rabi("torrent", zdaj - 125)
        st = snz.stanje(zdaj)
        self.assertEqual([d["ime"] for d in st], ["torrent", "scit", "teamwork"])   # najprej tiste, ki tecejo
        self.assertEqual(st[0]["pidi"], [1234])
        self.assertAlmostEqual(st[0]["zadnja_raba_s"], 125, delta=1)
        self.assertIsNone(st[2]["zadnja_raba_s"])
        self.assertEqual(st[1]["razlog"], snz.VARUJE)

    def test_ponovna_registracija_obdrzi_rabo(self):
        self._registriraj()
        snz.rabi("torrent", 123.0)
        snz.registriraj("torrent", snz.NA_ZAHTEVO, 600, tece=lambda: False)
        self.assertEqual(snz.storitev("torrent").zadnja_raba, 123.0)

    def test_napaka_v_klicu_ne_podre_ure(self):
        def pade():
            raise RuntimeError("x")
        snz.registriraj("x", snz.NA_ZAHTEVO, 1, tece=pade, ustavi=pade, zaposlena=pade)
        snz.registriraj("y", snz.NA_ZAHTEVO, 1, tece=lambda: True, ustavi=pade, zaposlena=pade)
        snz.ob_tiku(pade)
        snz.tik(zdaj=time.time() + 10)               # zaposlena pade -> pri dvomu ne ustavi
        self.assertEqual(snz.storitev("y").ustavitev, 0)


class Opravila(unittest.TestCase):
    def setUp(self):
        snz._za_preizkus()

    def tearDown(self):
        snz._za_preizkus()

    def test_opravilo_na_vrsti_v_kratki_niti_in_ne_dvakrat_hkrati(self):
        tece = threading.Event()
        spusti = threading.Event()
        teki = []

        def delo():
            teki.append(threading.current_thread().name)
            tece.set()
            spusti.wait(5)
        snz.opravilo("ciscenje", delo, razmik_s=3600, zamik_s=100)
        snz.ustavi_uro()                             # ura (nit) ne sme teci med preizkusom
        zdaj = time.monotonic()
        snz.tik(zdaj_mono=zdaj + 50)
        self.assertFalse(tece.wait(0.2))             # pred zamikom ne
        snz.tik(zdaj_mono=zdaj + 101)
        self.assertTrue(tece.wait(2))
        snz.tik(zdaj_mono=zdaj + 101 + 3600)         # se tece: ne zacne drugega
        spusti.set()
        self.assertTrue(_cakaj(lambda: not snz.opravila()[0]["tece"]))
        self.assertEqual(teki, ["safeer-opravilo"])
        self.assertGreater(snz.opravila()[0]["zadnje"], 0)

    def test_opravilo_brez_ure_zazene_eno_nit_glib_jo_zamenja(self):
        snz.opravilo("a", lambda: None, 3600, 10)
        snz.opravilo("b", lambda: None, 3600, 10)
        niti = [t for t in threading.enumerate() if t.name == "safeer-storitve"]
        self.assertEqual(len(niti), 1)               # dve opravili, ena ura
        glib = _LazenGLib()
        snz.zacni(glib, "Safeer OS")
        self.assertEqual(snz.ime_procesa(), "Safeer OS")
        self.assertEqual(glib.razmik, snz.TIK_S)
        self.assertTrue(_cakaj(lambda: not niti[0].is_alive(), 3 * snz.TIK_S))
        snz.zacni(glib, "Safeer Control")            # drugi klic: ura in ime ostaneta
        self.assertEqual((glib.stevilo, snz.ime_procesa()), (1, "Safeer OS"))


class _LazenGLib:
    def __init__(self):
        self.stevilo = 0
        self.razmik = 0

    def timeout_add_seconds(self, razmik, fn):
        self.stevilo += 1
        self.razmik = razmik
        self.fn = fn
        return 7

    def source_remove(self, _ident):
        return True


def _cakaj(pogoj, rok=5.0):
    konec = time.monotonic() + rok
    while time.monotonic() < konec:
        if pogoj():
            return True
        time.sleep(0.02)
    return pogoj()


if __name__ == "__main__":
    unittest.main()
