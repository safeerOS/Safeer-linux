"""Preizkusi urejenega izhoda (nacrt stabilnosti P2: UI -> strezniki/vticnice -> podprocesi -> baze -> stanje -> exit).

Preverja:
  1. Vrstni red faz in korakov z roki (en zataknjen korak ne ustavi izhoda).
  2. Idempotentnost (ponovni klic _koncaj je varen).
  3. K1: Scit DNS se izvede do konca (brez roka).
  4. K2: GTK/GLib/predvajalnik v FAZA_UI na glavni niti.
  5. K3: Podprocesi vsak v svoji niti vzporedno, ob izhodu otroci.pospravi_vse.
  6. P2: Obnova.json samo pod varuhom in brez 'zgodovina' v brisi_ob_izhodu.
  7. P3: Idempotentnost Control.koncaj in en vir signala.
  8. P4: Zgodnji signal nastavi zastavico, brez praznega stanja, koda 128+signal.
  9. M4: Exception se ujame, SystemExit/KeyboardInterrupt se dvigneta.
  10. M5: povezi_signale uporablja samo GLib.unix_signal_add.
  11. SIGTERM v vsaki fazi zagona (pred oknom, med nalaganjem, po zagonu) za
      Safeer Browser, Safeer Control in Safeer OS: proces konca v roku,
      brez ostankov (vtic, zaklepi, zacasne datoteke), stanje zapisano pod varuhom.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

from core import urejen_izhod, nova_razlicica, varuh_procesov  # noqa: E402


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

    def test_k1_scit_koncaj_brez_roka_do_konca(self):
        # K1: Povrnitev DNS Scita se mora izvesti do konca na niti z join BREZ roka
        dogodki = []

        def dolg_scit():
            time.sleep(3.0)     # dlje od roka navadnega koraka (2 s)
            dogodki.append("scit_koncan")

        ok = urejen_izhod.izvedi_korak(
            urejen_izhod.FAZA_STREZNIKI,
            "scit",
            dolg_scit,
            rok_s=urejen_izhod.ROK_SCITA_S,
            na_niti=True,
        )
        self.assertTrue(ok)
        self.assertEqual(dogodki, ["scit_koncan"])

    def test_k2_gtk_glib_v_faza_ui_na_glavni_niti(self):
        # K2: Preveri, da dejanja v FAZA_UI tecejo na glavni niti (na_niti=False)
        niti = []

        def ui_dejanje():
            niti.append(threading.current_thread() is threading.main_thread())

        ok = urejen_izhod.izvedi_korak(
            urejen_izhod.FAZA_UI,
            "ui_dejanje",
            ui_dejanje,
            rok_s=1.0,
            na_niti=False,
        )
        self.assertTrue(ok)
        self.assertEqual(niti, [True])

    def test_k3_podprocesi_vzporedno_in_pospravi_vse(self):
        # K3: Podprocesi vsak v svoji niti hkrati; ce en spi 3 s, se drugi_zaslon vseeno poklice
        klicani = []

        def pocasen_zvok():
            time.sleep(1.0)
            klicani.append("zvok")

        def hiter_drugi_zaslon():
            klicani.append("drugi_zaslon")

        koraki = [
            ("zvok", pocasen_zvok),
            ("drugi_zaslon", hiter_drugi_zaslon),
        ]
        ok = urejen_izhod.izvedi_vzporedno(urejen_izhod.FAZA_PODPROCESI, koraki, rok_s=0.2)
        self.assertFalse(ok)
        self.assertIn("drugi_zaslon", klicani)

    def test_p2_obnova_samo_pod_varuhom_in_brez_zgodovine(self):
        # P2: varuh_procesov.pod_varuhom() mora biti False brez NOTIFY_SOCKET
        self.assertFalse(varuh_procesov.pod_varuhom())

    def test_p3_control_koncaj_idempotentnost(self):
        # P3: Control.koncaj takoj vrne, ce _izhod_v_teku / _koncano
        class FakeControl:
            def __init__(self):
                self._koncano = False
                self._izhod_v_teku = True
                self.klici = 0

            def koncaj_brez_izhoda(self):
                self.klici += 1

            def koncaj(self):
                if getattr(self, "_koncano", False) or getattr(self, "_izhod_v_teku", False):
                    return
                self.koncaj_brez_izhoda()

        c = FakeControl()
        c.koncaj()
        self.assertEqual(c.klici, 0)

    def test_p4_zgodnji_signal_nastavi_zastavico_in_izhodna_koda(self):
        # P4: Zgodnji signal nastavi zastavico, preveri_zgodnji_signal izstopi s kodo 128+signal
        urejen_izhod._zgodnji_signal["signal"] = signal.SIGTERM
        with self.assertRaises(SystemExit) as cm:
            urejen_izhod.preveri_zgodnji_signal()
        self.assertEqual(cm.exception.code, 128 + signal.SIGTERM)
        urejen_izhod._zgodnji_signal["signal"] = None

    def test_p4_drugi_uvoz_ne_prepise_glib_signalov(self):
        # Izmerjeno 22. 10. (strace): safeer_os uvozen drugic je znova poklical namesti_zgodnje_signale in Python
        # signal.signal prepisal GLib vire -> SIGTERM po zagonu ni nic naredil. Ko je koncaj ze povezan, se ne sme klicati.
        stari = dict(urejen_izhod._aktivni_program)
        klici = []
        orig = signal.signal
        try:
            urejen_izhod._aktivni_program["koncaj"] = lambda: None
            signal.signal = lambda *a: klici.append(a)
            urejen_izhod.namesti_zgodnje_signale("preizkus")
        finally:
            signal.signal = orig
            urejen_izhod._aktivni_program.clear()
            urejen_izhod._aktivni_program.update(stari)
        self.assertEqual(klici, [])

    def test_m4_izvedi_korak_lovi_exception_dvigne_systemexit(self):
        # M4: Exception se ujame (vrne False), SystemExit se dvigne
        def z_napako():
            raise ValueError("testna napaka")

        def z_izhodom():
            sys.exit(42)

        self.assertFalse(urejen_izhod.izvedi_korak(urejen_izhod.FAZA_BAZE, "napaka", z_napako, rok_s=1.0))
        with self.assertRaises(SystemExit):
            urejen_izhod.izvedi_korak(urejen_izhod.FAZA_EXIT, "izhod", z_izhodom, rok_s=1.0)

    def test_m5_povezi_signale_samo_glib(self):
        # M5: povezi_signale ne registrira vec Python signal.signal rokovalnikov
        prvotni = signal.getsignal(signal.SIGTERM)
        urejen_izhod.povezi_signale(lambda: None, ime_programa="test")
        po = signal.getsignal(signal.SIGTERM)
        self.assertEqual(prvotni, po)


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
        self.env["NOTIFY_SOCKET"] = os.path.join(self.td_run.name, "varuh.sock")

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
                env["NOTIFY_SOCKET"] = os.path.join(td_run, "varuh.sock")
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

                pot_obnova = os.path.join(td_run, "safeer-browser", "obnova.json")
                if faza == "pred_oknom":
                    # P4: zgodnji signal zakljuci s kodo 128+sig ali -sig, brez stanja
                    self.assertIn(p.returncode, (128 + signal.SIGTERM, -signal.SIGTERM),
                                  f"Napacna izhodna koda v fazi {faza}: {p.returncode}")
                    self.assertFalse(os.path.isfile(pot_obnova), f"Zgodnji signal ne sme pisati stanja brez vsebine v fazi {faza}")
                else:
                    self.assertEqual(p.returncode, 0, f"Napacna izhodna koda v fazi {faza}: {p.returncode}")
                    # Stanje zapisano v obnova.json pod varuhom
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
                env["NOTIFY_SOCKET"] = os.path.join(td_run, "varuh.sock")
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

                pot_obnova = os.path.join(td_run, "safeer-control", "obnova.json")
                if faza == "pred_oknom":
                    self.assertIn(p.returncode, (128 + signal.SIGTERM, -signal.SIGTERM),
                                  f"Napacna izhodna koda v fazi {faza}: {p.returncode}")
                    self.assertFalse(os.path.isfile(pot_obnova), f"Zgodnji signal ne sme pisati stanja brez vsebine v fazi {faza}")
                else:
                    self.assertEqual(p.returncode, 0, f"Napacna izhodna koda v fazi {faza}: {p.returncode}")
                    self.assertTrue(os.path.isfile(pot_obnova), f"Manjka obnova.json v fazi {faza}")

                ostanki = _preveri_brez_ostankov(td_conf, td_run)
                self.assertEqual(ostanki, [], f"Ostanki datotek v fazi {faza}: {ostanki}")

    def test_safeer_control_aktivacija_po_koncaju_ne_dela_nic(self):
        """Signal med nalaganjem: koncaj() tece pred do_activate; aktivacija ne sme brisati stanja ne zagnati Linka."""
        koda = (
            "import sys, unittest.mock as m\n"
            "import safeer_control as c\n"
            "for polje in ('_koncano', '_izhod_v_teku'):\n"
            "    lazni = m.Mock(spec=['ozadje', '_prva_aktivacija', 'link', '_pripravi_link', 'pokazi_okno', polje])\n"
            "    lazni.ozadje = True; lazni._prva_aktivacija = True\n"
            "    setattr(lazni, polje, True)\n"
            "    c.SafeerControl.do_activate(lazni)\n"
            "    assert lazni._prva_aktivacija is True, polje\n"
            "    lazni._pripravi_link.assert_not_called(); lazni.pokazi_okno.assert_not_called()\n"
        )
        env = dict(self.env)
        env.pop("NOTIFY_SOCKET", None)
        r = subprocess.run([sys.executable, "-c", koda], cwd=KOREN, env=env, capture_output=True, text=True, timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr[-800:])

    def test_safeer_os_sigterm_v_vseh_fazah(self):
        for faza, zamik in [("pred_oknom", 0.25), ("med_nalaganjem", 1.1), ("po_zagonu", 2.2)]:
            with self.subTest(faza=faza), tempfile.TemporaryDirectory() as td_conf, tempfile.TemporaryDirectory() as td_run:
                env = dict(self.env)
                env["XDG_CONFIG_HOME"] = td_conf
                env["XDG_RUNTIME_DIR"] = td_run
                env["SAFEER_NOVA_RAZLICICA_MAPA"] = td_run
                env["NOTIFY_SOCKET"] = os.path.join(td_run, "varuh.sock")
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

                pot_obnova = os.path.join(td_run, "safeer-os", "obnova.json")
                if faza == "pred_oknom":
                    self.assertIn(p.returncode, (128 + signal.SIGTERM, -signal.SIGTERM),
                                  f"Napacna izhodna koda v fazi {faza}: {p.returncode}")
                    self.assertFalse(os.path.isfile(pot_obnova), f"Zgodnji signal ne sme pisati stanja brez vsebine v fazi {faza}")
                else:
                    self.assertEqual(p.returncode, 0, f"Napacna izhodna koda v fazi {faza}: {p.returncode}")
                    self.assertTrue(os.path.isfile(pot_obnova), f"Manjka obnova.json v fazi {faza}")

                ostanki = _preveri_brez_ostankov(td_conf, td_run)
                self.assertEqual(ostanki, [], f"Ostanki datotek v fazi {faza}: {ostanki}")

    def test_p2_brez_varuha_ne_pise_obnova(self):
        # P2: Brez varuha se obnova.json ne zapise
        with tempfile.TemporaryDirectory() as td_conf, tempfile.TemporaryDirectory() as td_run:
            env = dict(self.env)
            env["XDG_CONFIG_HOME"] = td_conf
            env["XDG_RUNTIME_DIR"] = td_run
            env["SAFEER_NOVA_RAZLICICA_MAPA"] = td_run
            env.pop("NOTIFY_SOCKET", None)
            p = subprocess.Popen(
                [sys.executable, os.path.join(KOREN, "safeer_control.py"), "--ozadje"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(1.5)
            p.send_signal(signal.SIGTERM)
            p.wait(timeout=5.0)
            self.assertEqual(p.returncode, 0)
            pot_obnova = os.path.join(td_run, "safeer-control", "obnova.json")
            self.assertFalse(os.path.isfile(pot_obnova), "Brez varuha se obnova.json ne sme zapisati")


if __name__ == "__main__":
    unittest.main()
