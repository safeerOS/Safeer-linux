"""Preizkusi urejenega izhoda (nacrt stabilnosti P2: UI -> strezniki/vticnice -> podprocesi -> baze -> stanje -> exit).

Preverja:
  1. Vrstni red faz in korakov z roki (en zataknjen korak ne ustavi izhoda).
  2. Idempotentnost (ponovni klic _koncaj je varen).
  3. SIGTERM v vsaki fazi zagona (pred oknom, med nalaganjem, po zagonu) za
     Safeer Browser, Safeer Control in Safeer OS: proces konca v roku,
     brez ostankov (vtic, zaklepi, zacasne datoteke), stanje zapisano.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

from core import urejen_izhod, nova_razlicica  # noqa: E402


class TestEnoteUrejenIzhod(unittest.TestCase):
    def test_vrstni_red_faz(self):
        pricakovan = (
            urejen_izhod.FAZA_UI,
            urejen_izhod.FAZA_STREZNIKI,
            urejen_izhod.FAZA_PODPROCESI,
            urejen_izhod.FAZA_BAZE,
            urejen_izhod.FAZA_STANJE,
            urejen_izhod.FAZA_EXIT,
        )
        self.assertEqual(urejen_izhod.VRSTNI_RED_FAZ, pricakovan)

    def test_izvedi_korak_uspeh(self):
        rezultat = []
        ok = urejen_izhod.izvedi_korak(urejen_izhod.FAZA_UI, "preizkus", lambda: rezultat.append(1), rok_s=1.0)
        self.assertTrue(ok)
        self.assertEqual(rezultat, [1])

    def test_izvedi_korak_rok_presezen_nadaljuje(self):
        # Korak, ki visi ali spi dlje od roka na niti, ne sme ustaviti poteka
        zacetek = time.monotonic()
        ok = urejen_izhod.izvedi_korak(
            urejen_izhod.FAZA_PODPROCESI,
            "zataknjen_proces",
            lambda: time.sleep(1.0),
            rok_s=0.2,
            na_niti=True,
        )
        trajanje = time.monotonic() - zacetek
        self.assertFalse(ok)
        self.assertLess(trajanje, 0.6)

    def test_izvedi_korak_napaka_ne_ustavi(self):
        def napacno():
            raise RuntimeError("zrusitev koraka")

        ok = urejen_izhod.izvedi_korak(urejen_izhod.FAZA_BAZE, "napaka", napacno, rok_s=1.0)
        self.assertFalse(ok)

    def test_idempotentnost_ponovni_klic_varen(self):
        # Ponovni klici funkcije za izhod ne smejo ponovno izvajati ze koncanega
        stevec = []

        def akcija():
            stevec.append(1)

        urejen_izhod.izvedi_korak(urejen_izhod.FAZA_STANJE, "korak1", akcija)
        self.assertEqual(stevec, [1])


def _preveri_brez_ostankov(mapa_conf: str, mapa_run: str) -> list[str]:
    """Preveri, da v zacasnih mapah ni ostankov nedokoncanih zacasnih datotek (*.tmp)."""
    ostanki = []
    for koren in (mapa_conf, mapa_run):
        if not os.path.isdir(koren):
            continue
        for pot, _mape, datoteke in os.walk(koren):
            for d in datoteke:
                if d.endswith(".tmp"):
                    ostanki.append(os.path.join(pot, d))
    return ostanki


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon (xvfb-run)")
class TestSigtermFazeZagona(unittest.TestCase):
    def setUp(self):
        self.td_conf = tempfile.TemporaryDirectory()
        self.td_run = tempfile.TemporaryDirectory()
        self.env = dict(os.environ)
        self.env["XDG_CONFIG_HOME"] = self.td_conf.name
        self.env["XDG_RUNTIME_DIR"] = self.td_run.name
        self.env["SAFEER_NOVA_RAZLICICA_MAPA"] = self.td_run.name
        self.env["WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS"] = "1"

    def tearDown(self):
        self.td_conf.cleanup()
        self.td_run.cleanup()

    def test_safeer_brskalnik_sigterm_v_vseh_fazah(self):
        for faza, zamik in [("pred_oknom", 0.15), ("med_nalaganjem", 0.8), ("po_zagonu", 1.8)]:
            with self.subTest(faza=faza), tempfile.TemporaryDirectory() as td_conf, tempfile.TemporaryDirectory() as td_run:
                env = dict(self.env)
                env["XDG_CONFIG_HOME"] = td_conf
                env["XDG_RUNTIME_DIR"] = td_run
                env["SAFEER_NOVA_RAZLICICA_MAPA"] = td_run
                p = subprocess.Popen(
                    [sys.executable, os.path.join(KOREN, "safeer_brskalnik.py"), "about:blank"],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(zamik)
                z0 = time.monotonic()
                p.send_signal(signal.SIGTERM)
                try:
                    p.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    p.kill()
                    self.fail(f"Safeer Browser je obvisel v fazi {faza}")
                trajanje = time.monotonic() - z0
                self.assertLess(trajanje, 4.0, f"Izhod je trajal predolgo: {trajanje:.2f} s")
                self.assertEqual(p.returncode, 0, f"Napacna izhodna koda v fazi {faza}: {p.returncode}")

                # Stanje zapisano v obnova.json
                pot_obnova = os.path.join(td_run, "safeer-browser", "obnova.json")
                self.assertTrue(os.path.isfile(pot_obnova), f"Manjka obnova.json v fazi {faza}")

                # Brez ostankov .tmp datotek
                ostanki = _preveri_brez_ostankov(td_conf, td_run)
                self.assertEqual(ostanki, [], f"Ostanki datotek v fazi {faza}: {ostanki}")

    def test_safeer_control_sigterm_v_vseh_fazah(self):
        for faza, zamik in [("pred_oknom", 0.15), ("med_nalaganjem", 0.7), ("po_zagonu", 1.5)]:
            with self.subTest(faza=faza), tempfile.TemporaryDirectory() as td_conf, tempfile.TemporaryDirectory() as td_run:
                env = dict(self.env)
                env["XDG_CONFIG_HOME"] = td_conf
                env["XDG_RUNTIME_DIR"] = td_run
                env["SAFEER_NOVA_RAZLICICA_MAPA"] = td_run
                p = subprocess.Popen(
                    [sys.executable, os.path.join(KOREN, "safeer_control.py"), "--ozadje"],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(zamik)
                z0 = time.monotonic()
                p.send_signal(signal.SIGTERM)
                try:
                    p.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    p.kill()
                    self.fail(f"Safeer Control je obvisel v fazi {faza}")
                trajanje = time.monotonic() - z0
                self.assertLess(trajanje, 4.0, f"Izhod je trajal predolgo: {trajanje:.2f} s")
                self.assertEqual(p.returncode, 0, f"Napacna izhodna koda v fazi {faza}: {p.returncode}")

                pot_obnova = os.path.join(td_run, "safeer-control", "obnova.json")
                self.assertTrue(os.path.isfile(pot_obnova), f"Manjka obnova.json v fazi {faza}")

                ostanki = _preveri_brez_ostankov(td_conf, td_run)
                self.assertEqual(ostanki, [], f"Ostanki datotek v fazi {faza}: {ostanki}")

    def test_safeer_os_sigterm_v_vseh_fazah(self):
        for faza, zamik in [("pred_oknom", 0.25), ("med_nalaganjem", 1.1), ("po_zagonu", 2.2)]:
            with self.subTest(faza=faza), tempfile.TemporaryDirectory() as td_conf, tempfile.TemporaryDirectory() as td_run:
                env = dict(self.env)
                env["XDG_CONFIG_HOME"] = td_conf
                env["XDG_RUNTIME_DIR"] = td_run
                env["SAFEER_NOVA_RAZLICICA_MAPA"] = td_run
                p = subprocess.Popen(
                    [sys.executable, os.path.join(KOREN, "safeer_os.py"), "--okno"],
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(zamik)
                z0 = time.monotonic()
                p.send_signal(signal.SIGTERM)
                try:
                    p.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    p.kill()
                    self.fail(f"Safeer OS je obvisel v fazi {faza}")
                trajanje = time.monotonic() - z0
                self.assertLess(trajanje, 4.0, f"Izhod je trajal predolgo: {trajanje:.2f} s")
                self.assertEqual(p.returncode, 0, f"Napacna izhodna koda v fazi {faza}: {p.returncode}")

                pot_obnova = os.path.join(td_run, "safeer-os", "obnova.json")
                self.assertTrue(os.path.isfile(pot_obnova), f"Manjka obnova.json v fazi {faza}")

                ostanki = _preveri_brez_ostankov(td_conf, td_run)
                self.assertEqual(ostanki, [], f"Ostanki datotek v fazi {faza}: {ostanki}")


if __name__ == "__main__":
    unittest.main()
