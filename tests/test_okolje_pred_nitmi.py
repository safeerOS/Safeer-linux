"""Okolje procesa se po zagonu niti ne spreminja (AGENTS.md, Okolje procesa; 19. 10. 2026).

- Peskovnik WebKita (core/peskovnik_userns.py): IZKLOP se v okolje DODA, ko bwrap ne dela (Ubuntu 24.04+ brez profila
  AppArmor). Prej v main(), ko je `import gi` ze zagnal niti; zdaj pred_nitmi() pred `import gi`, main() le prebere stanje.
- SAFEER_CONTROL_ODPRI: prej os.environ.pop ob uvozu safeer_control - v procesu Safeer OS (vgrajen Control) so niti ze
  tekle. Zdaj okolje_procesa.PREVZETE (prevzame jo Safeer OS pred nitmi).
- safeerctl: naslov vodila seje samo ob prvem klicu (pred `import gi`), ne ob vsakem klicu Controla.
Vsak preizkus brez svojega popravka pade.
"""
import io
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

KOREN = Path(__file__).resolve().parents[1]
if str(KOREN) not in sys.path:
    sys.path.insert(0, str(KOREN))

from core import okolje_procesa  # noqa: E402
from core import peskovnik_userns as p  # noqa: E402

VSTOPI = ("safeer_os.py", "safeer_control.py", "safeer_brskalnik.py")


class PeskovnikPredNitmi(unittest.TestCase):
    def test_vstopne_tocke_pred_import_gi(self):
        for ime in VSTOPI:
            vir = (KOREN / ime).read_text(encoding="utf-8")
            klic = vir.index("    peskovnik_userns.pred_nitmi()")
            self.assertLess(klic, vir.index("\nimport gi"), ime)
            # Samo zagon programa, ne uvoz (preizkusi, vgrajen Control v procesu Safeer OS, kjer niti ze tecejo).
            pred = vir[:klic].rstrip().rsplit("\nif ", 1)[1]
            self.assertTrue(pred.startswith('__name__ == "__main__":'), ime)
            telo = vir[vir.index("\ndef main("):]
            self.assertNotIn("peskovnik_userns.pripravi(", telo, ime)
            self.assertIn("peskovnik_userns.ob_zagonu()", telo, ime)

    def _bwrap(self, mapa: Path, koda: int) -> str:
        pot = mapa / ("bwrap-%d" % koda)
        pot.write_text("#!/bin/sh\nexit %d\n" % koda)
        pot.chmod(pot.stat().st_mode | stat.S_IXUSR)
        return str(pot)

    def test_pred_nitmi_enkrat_main_okolja_ne_spremeni(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(p, "_ob_zagonu", None):
            d = Path(d)
            (d / "omejitev").write_text("1\n")
            (d / "oznaka").write_text("unconfined\n")
            k = {"pot_omejitve": str(d / "omejitev"), "poti_oznake": (str(d / "oznaka"),)}
            okolje = {}
            stanje = p.pred_nitmi(okolje, bwrap=self._bwrap(d, 1), **k)
            self.assertTrue(stanje["izklopljen"])
            self.assertEqual(okolje, {p.IZKLOP: "1"}, "pred nitmi: izklop, nikoli prazna vrednost")
            # Drug klic (npr. Control v istem procesu): brez nove preverbe in brez spremembe okolja.
            drugo = {}
            self.assertTrue(p.pred_nitmi(drugo, bwrap=self._bwrap(d, 0), **k)["izklopljen"])
            self.assertEqual(drugo, {})
            # main(): isto stanje, okolje procesa ostane, kot je; zapis gre v izpis (sled.log).
            prej = dict(os.environ)
            izpis = io.StringIO()
            with redirect_stdout(izpis):
                self.assertTrue(p.ob_zagonu()["izklopljen"])
            self.assertEqual(dict(os.environ), prej)
            self.assertIn("brez peskovnika", izpis.getvalue())

    def test_brez_pred_nitmi_preveri_ob_zagonu(self):
        """Varovalka: vstop, ki pred_nitmi() ni poklical, peskovnik preveri v main() (kot prej) - WebKit brez
        delujocega bwrap na Ubuntu 24.04+ bi sicer ob prvi strani koncal ves proces."""
        stanje = {"omejeno": True, "oznaka": "unconfined", "deluje": False, "izklopljen": True}
        with mock.patch.object(p, "_ob_zagonu", None), \
                mock.patch.object(p, "pripravi", return_value=stanje) as pripravi, redirect_stdout(io.StringIO()):
            self.assertTrue(p.ob_zagonu()["izklopljen"])
            self.assertTrue(p.ob_zagonu()["izklopljen"])
        pripravi.assert_called_once()

    def test_main_ne_klice_pripravi(self):
        """main() (Safeer OS, Control, brskalnik) z laznim stanjem: pripravi() ni poklican, pojasnilo ostane."""
        import safeer_os as so
        app = mock.MagicMock()
        with mock.patch.object(p, "pripravi") as pripravi, \
                mock.patch.object(p, "_ob_zagonu", {"omejeno": True, "oznaka": "unconfined", "deluje": False,
                                                    "izklopljen": True}), \
                mock.patch.object(p, "pojasni_kasneje") as pojasni, \
                mock.patch.object(so, "SafeerOS", return_value=app), \
                mock.patch.object(so, "_predaj_ce_oddaljen", return_value=True), \
                mock.patch.object(so, "os_stabilnost"), mock.patch.object(so, "popravi_po_sesutju", return_value=False), \
                mock.patch.object(so, "os_programi"), mock.patch.object(so, "GLib"), \
                mock.patch.object(sys, "argv", ["safeer-os", "--delovna"]), redirect_stdout(io.StringIO()):
            self.assertEqual(so.main(), 0)
        pripravi.assert_not_called()
        pojasni.assert_called_once()


class OdpriControlPrevzeto(unittest.TestCase):
    def test_v_prevzetih(self):
        with mock.patch.dict(os.environ, {"SAFEER_CONTROL_ODPRI": "1"}), \
                mock.patch.object(okolje_procesa, "_prevzeto", {}):
            okolje_procesa.pred_nitmi()
            self.assertNotIn("SAFEER_CONTROL_ODPRI", os.environ)
            kljuci = set(os.environ)
            self.assertEqual(okolje_procesa.prevzemi("SAFEER_CONTROL_ODPRI"), "1")
            self.assertEqual(set(os.environ), kljuci)
        vir = (KOREN / "safeer_control.py").read_text(encoding="utf-8")
        self.assertNotIn('os.environ.pop("SAFEER_CONTROL_ODPRI")', vir)
        self.assertIn('okolje_procesa.prevzemi("SAFEER_CONTROL_ODPRI")', vir)

    def test_vgrajen_control_okolja_ne_spremeni(self):
        """Kot v procesu Safeer OS: pred_nitmi(), vgradnja, GTK (niti), nato uvoz safeer_control - okolje enako, okno
        se vseeno odpre (zastavica prevzeta), peskovnika Control ne preverja drugic."""
        koda = (
            "import os, sys; sys.path.insert(0, %r)\n"
            "from core import okolje_procesa, en_proces, peskovnik_userns\n"
            "okolje_procesa.pred_nitmi(); en_proces.vgradi_control()\n"
            "klici = []\n"
            "peskovnik_userns.pripravi = lambda *a, **k: klici.append(1) or {}\n"
            "import gi; gi.require_version('Gtk', '4.0'); from gi.repository import Gtk\n"
            "kljuci = set(os.environ)\n"
            "import safeer_control\n"
            "print(set(os.environ) == kljuci, safeer_control._ODPRI_OB_ZAGONU, len(klici))\n" % str(KOREN))
        okolje = dict(os.environ, SAFEER_CONTROL_ODPRI="1")
        izid = subprocess.run([sys.executable, "-c", koda], capture_output=True, text=True, timeout=120, env=okolje)
        self.assertEqual(izid.stdout.strip().splitlines()[-1:], ["True True 0"], izid.stderr[-800:])


class SafeerctlVodilo(unittest.TestCase):
    def test_naslov_vodila_samo_ob_prvem_klicu(self):
        import safeerctl
        with mock.patch.object(safeerctl, "_VODILO", {"nastavljeno": False}, create=True), \
                mock.patch.object(safeerctl, "nastavi_vodilo_seje") as nastavi, \
                mock.patch.dict(sys.modules, {"gi": None}):       # brez gi: klic konca z Napaka
            for _ in range(2):
                with self.assertRaises(safeerctl.Napaka):
                    safeerctl.klic_controla("Seznam")
        self.assertEqual(nastavi.call_count, 1)


if __name__ == "__main__":
    unittest.main()
