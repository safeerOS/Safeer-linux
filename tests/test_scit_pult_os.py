"""Safeer Scit v pultu delovne povrsine (safeer_os.py): zacne se z namizjem kot kuverta, klik odpre nastavitve Scita,
preklop gre skozi Scit.nastavi (obstojece vprasanje za geslo) v svoji niti, stikalo v Nastavitvah takoj osvezi pult.
Lastnik, 17. 10. 2026. Ikona in meni sama: tests/test_pladenj_sni.py."""
import os
import sys
import threading
import unittest
from types import SimpleNamespace
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

import safeer_os  # noqa: E402



_NIT = threading.Thread


def _zazeni_in_pocakaj(target, name) -> None:
    n = _NIT(target=target, name=name, daemon=True)
    n.start()
    n.join(5)


def _vir() -> str:
    with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
        return f.read()


class ScitVPultu(unittest.TestCase):
    def test_zacne_se_z_namizjem(self):
        vir = _vir()
        telo = vir[vir.index("    def _ob_namizju(self)"):vir.index("    def _izklopi_delovno(self)")]
        self.assertIn("self._zacni_scit_pult()", telo)
        self.assertIn("self._zacni_kuverto()", telo)

    def test_stikalo_v_nastavitvah_osvezi_pult(self):
        self.assertIn('"scitVklop": lambda: self._po_scitu(self.scit.nastavi(', _vir())

    def _jaz(self, **dodatno):
        jaz = SimpleNamespace(scit_pult=None, _scit_pult_zaposlen=False, SCIT_PULT_OSVEZI_S=15,
                              _dogodek=lambda vrsta, podatki: None, **dodatno)
        for ime in ("_zacni_scit_pult", "_osvezi_scit_pult", "_preklopi_scit_iz_pulta", "_po_scitu"):
            setattr(jaz, ime, getattr(safeer_os.SafeerOS, ime).__get__(jaz))
        return jaz

    def test_klik_odpre_nastavitve_scita_preklop_v_niti(self):
        odprto, ustvarjeni = [], []
        stanje = {"vklop": True, "tece": True, "mozno": True, "napaka": "", "blokiranih": 3}
        scit = mock.MagicMock()
        scit.stanje_pulta.return_value = stanje
        scit.razlog_svez.return_value = False       # prva preverba resolved: v niti (systemctl)
        niti = []
        scit.nastavi.side_effect = lambda v: (niti.append(threading.current_thread().name), dict(stanje, vklop=v))[1]
        jaz = self._jaz(scit=scit, _odpri_razdelek=odprto.append)

        class LazniPult:
            def __init__(self, besedila, ob_nastavitvah, ob_preklopu, mapa, barve=None):
                self.barve = barve
                self.besedila, self.ob_nastavitvah, self.ob_preklopu = besedila, ob_nastavitvah, ob_preklopu
                self.stanja = []
                ustvarjeni.append(self)

            def osvezi(self, s, zaposlen=""):
                self.stanja.append(s)

        idle = lambda fn, *a: fn(*a)  # noqa: E731
        with mock.patch("core.pladenj_sni.ScitPult", LazniPult), \
                mock.patch.object(safeer_os.GLib, "idle_add", side_effect=idle), \
                mock.patch.object(safeer_os.GLib, "timeout_add_seconds") as casovnik, \
                mock.patch.object(safeer_os, "_jezik", return_value="de"), \
                mock.patch.object(safeer_os.threading, "Thread") as nit:
            # Prava nit, a pocakamo nanjo (idle_add je zgoraj takojsen): preizkus ostane zaporeden.
            nit.side_effect = lambda target, name, daemon: SimpleNamespace(start=lambda: _zazeni_in_pocakaj(target, name))
            jaz._zacni_scit_pult()
            jaz._zacni_scit_pult()                           # drugic nic: ena ikona na proces
            self.assertEqual(len(ustvarjeni), 1)
            pult = ustvarjeni[0]
            self.assertEqual(pult.besedila["naslov"], "Safeer Schild")
            self.assertEqual(pult.barve["ok"][:3], (127, 224, 182))      # barve iz assets/os/tokens.css
            self.assertEqual(pult.stanja, [stanje])
            casovnik.assert_called_once()
            pult.ob_nastavitvah()
            self.assertEqual(odprto, ["scit"])                  # okno Safeer Scit (lastnik, 18. 10. 2026)
            pult.ob_preklopu(False)
            scit.nastavi.assert_called_once_with(False)
            self.assertEqual(niti, ["safeer-scit-preklop"])  # pkexec (geslo) ne blokira glavne niti
            self.assertFalse(jaz._scit_pult_zaposlen)
            self.assertFalse(pult.stanja[-1]["vklop"])
            # Stikalo v Nastavitvah: pult dobi isto stanje takoj.
            self.assertEqual(jaz._po_scitu({"vklop": True}), {"vklop": True})
            self.assertEqual(pult.stanja[-1], {"vklop": True})

    def test_osvezitev_brez_niti_ko_je_razlog_svez(self):
        """Redna osvezitev (vsakih 15 s): hitro stanje pulta na glavni niti, brez nove niti in brez polnega stanja
        (systemctl, pkcheck - meritev 19. 10. 2026)."""
        scit = mock.MagicMock()
        scit.razlog_svez.return_value = True
        scit.stanje_pulta.return_value = {"vklop": True, "tece": True, "mozno": True, "napaka": "", "blokiranih": 7}
        pult = mock.MagicMock()
        jaz = self._jaz(scit=scit)
        jaz.scit_pult = pult
        with mock.patch.object(safeer_os.threading, "Thread", side_effect=AssertionError("brez niti")):
            jaz._osvezi_scit_pult()
        pult.osvezi.assert_called_once_with(scit.stanje_pulta.return_value)
        scit.stanje_pulta.assert_called_once_with(preveri=False)    # glavna nit: nikoli podproces
        scit.stanje.assert_not_called()

    def test_brez_vodila_brez_ikone(self):
        jaz = self._jaz(scit=mock.MagicMock())
        with mock.patch("core.pladenj_sni.ScitPult", side_effect=RuntimeError("ni vodila")), \
                mock.patch.object(safeer_os.GLib, "timeout_add_seconds") as casovnik:
            jaz._zacni_scit_pult()
        self.assertIsNone(jaz.scit_pult)
        casovnik.assert_not_called()


if __name__ == "__main__":
    unittest.main()
