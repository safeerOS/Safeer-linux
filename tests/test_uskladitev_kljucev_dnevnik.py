"""Usklajevanje kljucev: dnevnik na Linuxu in razlog za vmesnik (izmerjeno 10. 11. 2026 na testnem PC).

Logger safeer.kljuci_sinh na Linuxu ni pisal nikamor (dnevnik.log je imel samo varuha, journal nic), Medijski center pa
je bil prazen brez razlage - naprave s kljuci niso bile v ozjem krogu. Preizkus:
- sporocila gredo v dnevnik programa (os_stabilnost.zapisi, ~/.cache/<program>/dnevnik.log), z isto mejo velikosti;
- v datoteki ni vrednosti kljuca (tudi ne kosa >= 8 znakov) in ne celega ID naprave;
- razlog_brez_kljucev za vsako kodo, besedila v 6 jezikih, Uskladitev.razlog() steje samo ozji krog TE naprave.
Brez spremembe os.environ: mapa dnevnika je zamenjana z mktemp -d (mock na os_stabilnost._mapa).
"""
import logging
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import debrid, os_stabilnost  # noqa: E402
from core import uskladitev_kljucev as U  # noqa: E402
from core import uskladitev_kljucev_pravila as P  # noqa: E402
from tests.test_uskladitev_kljucev import Mreza, Vir, pocakaj  # noqa: E402

#: Lazen kljuc: v dnevniku ga ne sme biti, tudi ne po delih.
LAZNI_KLJUC = "tbx_9f3K2LmQ8vR7wZ1yX4cB6nP0qS5tU"
PC = "pc-0123456789abcdef"
TEL = "tel-fedcba9876543210"
TUJ = "tuj-aaaabbbbccccdddd"
JEZIKI = ("sl", "en", "de", "es", "fr", "it")


def _kosi(niz: str, dolzina: int = 8):
    return {niz[i:i + dolzina] for i in range(len(niz) - dolzina + 1)}


class _Dnevnik(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-kljuci-dnevnik-")
        self.addCleanup(shutil.rmtree, self.mapa, True)

        def mapa(ime):
            pot = os.path.join(self.mapa, ime)
            os.makedirs(pot, exist_ok=True)
            return pot
        p = mock.patch.object(os_stabilnost, "_mapa", mapa)
        p.start()
        self.addCleanup(p.stop)
        self.logger = logging.getLogger("safeer.kljuci_sinh")
        prej_raven, prej = self.logger.level, list(self.logger.handlers)

        def obnovi():
            self.logger.handlers[:] = prej
            self.logger.setLevel(prej_raven)
        self.addCleanup(obnovi)
        self.logger.handlers[:] = [h for h in prej if not isinstance(h, getattr(os_stabilnost, "VDnevnik", ()))]
        self.logger.setLevel(logging.NOTSET)
        self.pot = os.path.join(self.mapa, "safeer-test", "dnevnik.log")

    def beri(self) -> str:
        try:
            with open(self.pot, encoding="utf-8") as d:
                return d.read()
        except FileNotFoundError:
            return ""


class Dnevnik(_Dnevnik):
    def test_sporocilo_pride_v_datoteko(self):
        h = os_stabilnost.v_dnevnik("safeer-test", "safeer.kljuci_sinh")
        self.assertIs(os_stabilnost.v_dnevnik("safeer-test", "safeer.kljuci_sinh"), h, "en zapisovalec, tudi ob drugem klicu")
        U._log.info("uskladitev: zapisov %d, naprav %d", 3, 1)
        U._log.debug("podrobnost, ki je ne zelimo")
        vsebina = self.beri()
        self.assertIn("INFO safeer.kljuci_sinh: uskladitev: zapisov 3, naprav 1", vsebina)
        self.assertNotIn("podrobnost", vsebina)

    def test_sled_izjeme_ne_gre_v_dnevnik(self):
        os_stabilnost.v_dnevnik("safeer-test", "safeer.kljuci_sinh")
        try:
            raise ValueError(LAZNI_KLJUC)
        except ValueError as e:
            U._log.info("pripravi: %s", type(e).__name__, exc_info=True)
        vsebina = self.beri()
        self.assertIn("pripravi: ValueError", vsebina)
        self.assertFalse(_kosi(LAZNI_KLJUC) & _kosi(vsebina), "kos kljuca iz sledi izjeme je v dnevniku")

    def test_omejena_velikost(self):
        os_stabilnost.v_dnevnik("safeer-test", "safeer.kljuci_sinh")
        for i in range(4000):
            U._log.info("uskladitev %05d: %s", i, "x" * 150)
        velikost = os.path.getsize(self.pot)
        self.assertLessEqual(velikost, os_stabilnost.NAJVECJI_DNEVNIK + 400)
        self.assertIn("uskladitev 03999", self.beri(), "zadnji zapis ostane")
        self.assertIn("starejsi zapisi so odrezani", self.beri())


class Storitev(_Dnevnik):
    """Dve napravi v istem procesu (kot tests/test_uskladitev_kljucev.py), dnevnik v zacasni mapi."""

    def setUp(self):
        super().setUp()
        os_stabilnost.v_dnevnik("safeer-test", "safeer.kljuci_sinh")
        self.m = Mreza()
        self.ura = [1_000_000]

    def naprava(self, ident):
        vir = Vir()
        u = U.Uskladitev(U.Shramba(os.path.join(self.mapa, ident + ".json")), vir, self.m.link(ident),
                         ura=lambda: self.ura[0])
        self.m.naprave[ident] = u
        return u, vir

    def krog(self, a, b):
        self.m.krog.setdefault(a, set()).add(b)
        self.m.krog.setdefault(b, set()).add(a)

    def test_v_dnevniku_ni_kljuca_ne_celega_id(self):
        pc, vir_pc = self.naprava(PC)
        tel, vir_tel = self.naprava(TEL)
        self.naprava(TUJ)
        self.krog(PC, TEL)
        vir_pc.vrednosti["debrid:torbox"] = LAZNI_KLJUC
        self.assertEqual(pc.uskladi_zdaj(), 1)
        self.assertTrue(pocakaj(lambda: vir_tel.vrednosti.get("debrid:torbox") == LAZNI_KLJUC))
        # Naprava zunaj kroga poslje kljuc: zavrnjeno, v dnevnik gre samo kratek ID in razlog.
        pc.prejmi(TUJ, TUJ, {"v": 1, "items": [{"k": "debrid:torbox", "c": 5, "i": TUJ, "d": False,
                                                "v": LAZNI_KLJUC}]}, zascita=TUJ)
        pc.prejmi(TEL, TEL, {"items": []}, zascita="")
        vsebina = self.beri()
        self.assertTrue(vsebina, "dnevnik je prazen")
        self.assertFalse(_kosi(LAZNI_KLJUC) & _kosi(vsebina), "kos kljuca (>= 8 znakov) je v dnevniku")
        for ident in (PC, TEL, TUJ):
            self.assertNotIn(ident, vsebina, "cel ID naprave v dnevniku")
        self.assertIn("izmenjava z %s: sprejeto" % P.kratek_id(TEL), vsebina)
        self.assertIn("prejem od %s: zavrnjeno (ni_krog), zapisov 1" % P.kratek_id(TUJ), vsebina)
        self.assertIn("prejem od %s: zavrnjeno (zascita)" % P.kratek_id(TEL), vsebina)

    def test_razlog_po_stanju(self):
        pc, vir_pc = self.naprava(PC)
        self.assertEqual(pc.razlog()["koda"], P.RAZLOG_NI_NAPRAV)
        tel, vir_tel = self.naprava(TEL)
        self.krog(PC, TEL)
        self.assertEqual(pc.razlog()["koda"], P.RAZLOG_NEDOSEGLJIVE, "se ni izmenjave")
        # Telefon ne odgovori (ni povezan): nedosegljive.
        with mock.patch.object(type(pc.link), "ukaz", return_value={}):
            pc.uskladi_zdaj()
        self.assertEqual(pc.razlog()["koda"], P.RAZLOG_NEDOSEGLJIVE)
        # Telefon odgovori, a nima kljucev.
        pc.uskladi_zdaj()
        self.assertEqual(pc.razlog()["koda"], P.RAZLOG_BREZ_KLJUCEV)
        # Telefon ima kljuc: v redu.
        vir_tel.vrednosti["debrid:torbox"] = LAZNI_KLJUC
        self.ura[0] += 10
        pc.uskladi_zdaj()
        self.assertTrue(pocakaj(lambda: pc.razlog()["koda"] == P.RAZLOG_V_REDU))
        r = pc.razlog()
        self.assertEqual(set(r["besedilo"]), set(JEZIKI))
        self.assertNotIn(LAZNI_KLJUC, repr(r))
        # Telefon, ki je prej odgovarjal, zdaj ne odgovori: zadnji izid velja, ne stari »sprejeto«.
        with mock.patch.object(type(pc.link), "ukaz", return_value={}):
            pc.uskladi_zdaj()
        self.assertEqual(pc.razlog()["koda"], P.RAZLOG_NEDOSEGLJIVE)
        # Izklopljeno: razloga ni.
        pc.nastavi_vklopljeno(False)
        self.assertIsNone(pc.razlog())

    def test_caka_potrditev(self):
        pc, _ = self.naprava(PC)
        self.naprava(TEL)
        self.krog(PC, TEL)
        with mock.patch.object(type(pc.link), "ukaz", return_value={"ok": True, "data": {"accepted": False,
                                                                                          "pending": True}}):
            pc.uskladi_zdaj()
        self.assertEqual(pc.razlog()["koda"], P.RAZLOG_CAKA)

    def test_naprava_zunaj_kroga_ne_spremeni_razloga(self):
        """Razlog ne razkrije naprav zunaj kroga: tuja naprava, ki poslje kljuce, ga ne spremeni."""
        pc, _ = self.naprava(PC)
        self.naprava(TUJ)
        self.assertEqual(pc.razlog()["koda"], P.RAZLOG_NI_NAPRAV)
        pc.prejmi(TUJ, TUJ, {"v": 1, "items": [{"k": "debrid:torbox", "c": 5, "i": TUJ, "d": False, "v": "X"}]},
                  zascita=TUJ)
        self.assertEqual(pc.razlog()["koda"], P.RAZLOG_NI_NAPRAV)
        # Telefon v krogu se ni odgovoril; tuja naprava z »uspesno izmenjavo« tega ne sme spremeniti v »v redu«.
        self.naprava(TEL)
        self.krog(PC, TEL)
        prej = pc.razlog()
        pc._zabelezi_izid(TUJ, P.IZID_SPREJETO, 5)       # tudi ce bi kdaj zabelezili izid, ga razlog ne steje
        self.assertEqual(pc.razlog(), prej)
        self.assertEqual(prej["koda"], P.RAZLOG_NEDOSEGLJIVE)

    def test_most_vmesnika_ima_razlog(self):
        pc, _ = self.naprava(PC)
        dbr = mock.Mock()
        dbr.stanje.return_value = {"storitve": []}
        U.nastavi(pc)
        self.addCleanup(U.nastavi, None)
        odgovor = debrid.most(dbr, [])
        self.assertEqual(odgovor["uskladitev"]["koda"], P.RAZLOG_NI_NAPRAV)
        self.assertEqual(set(odgovor["uskladitev"]["besedilo"]), set(JEZIKI))
        U.nastavi(None)
        self.assertNotIn("uskladitev", debrid.most(dbr, []), "brez storitve v procesu polja ni")


class Razlog(unittest.TestCase):
    def test_vsaka_koda(self):
        primeri = {
            P.RAZLOG_NI_NAPRAV: (0, 0, 0, ""),
            P.RAZLOG_CAKA: (1, 0, 0, P.IZID_CAKA),
            P.RAZLOG_NEDOSEGLJIVE: (2, 0, 0, P.IZID_NEDOSEGLJIVO),
            P.RAZLOG_BREZ_KLJUCEV: (1, 1, 0, P.IZID_SPREJETO),
            P.RAZLOG_V_REDU: (1, 1, 3, P.IZID_SPREJETO),
        }
        self.assertEqual(set(primeri), set(P.RAZLOGI))
        for koda, vhod in primeri.items():
            dobljena, besedila = P.razlog_brez_kljucev(*vhod)
            self.assertEqual(dobljena, koda, vhod)
            self.assertEqual(set(besedila), set(JEZIKI), koda)
            for jezik, b in besedila.items():
                self.assertTrue(b.strip(), (koda, jezik))
        # Brez naprav v krogu ni pomembno nic drugega.
        self.assertEqual(P.razlog_brez_kljucev(0, 3, 9, P.IZID_CAKA)[0], P.RAZLOG_NI_NAPRAV)

    def test_besedila_razlicna(self):
        for jezik in JEZIKI:
            besedila = [P.BESEDILA_RAZLOGA[k][jezik] for k in P.RAZLOGI]
            self.assertEqual(len(set(besedila)), len(besedila), jezik)

    def test_kratek_id(self):
        self.assertEqual(P.kratek_id(PC), "pc…cdef")
        self.assertEqual(P.kratek_id("kratek"), "…")
        self.assertEqual(P.kratek_id(""), "…")


if __name__ == "__main__":
    unittest.main()
