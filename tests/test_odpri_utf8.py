"""Besedilne datoteke v core/ se odpirajo z encoding="utf-8" (odprta tocka neodvisnega pregleda 2).

Brez encoding Python vzame kodiranje okolja (na Windows cp1252, v okolju z LANG=C pred PEP 538 ASCII). Izmerjeno
20. 10. 2026: /proc/<pid>/comm je ime procesa v bajtih, ki ga jedro odreze na 15 bajtov tudi sredi znaka UTF-8 -
os_dock.plank_tece je ob takem procesu koncal z UnicodeDecodeError (lovil je samo OSError). Datoteke, ki so samo za flock
ali za izhod podprocesa, so odprte binarno.
"""
import ast
import ctypes
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

KOREN = Path(__file__).resolve().parents[1]
#: Nacin iz spremenljivke, ki je vedno binaren (link_deljenje: "ab" ali "wb" za nadaljevanje prenosa).
IZJEME = {("core/link_deljenje.py", "nacin")}


def _odpiranja_brez_kodiranja():
    izid = []
    for pot in sorted((KOREN / "core").rglob("*.py")):
        rel = pot.relative_to(KOREN).as_posix()
        for n in ast.walk(ast.parse(pot.read_text(encoding="utf-8"))):
            if not isinstance(n, ast.Call):
                continue
            f = n.func
            if isinstance(f, ast.Name) and f.id == "open":
                pass
            elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and \
                    (f.value.id, f.attr) in (("io", "open"), ("os", "fdopen"), ("codecs", "open")):
                pass
            else:
                continue
            if any(k.arg == "encoding" for k in n.keywords):
                continue
            nacin = n.args[1] if len(n.args) > 1 else next((k.value for k in n.keywords if k.arg == "mode"), None)
            if nacin is None:
                besedilo = "r"
            elif isinstance(nacin, ast.Constant) and isinstance(nacin.value, str):
                besedilo = nacin.value
            elif isinstance(nacin, ast.Name) and (rel, nacin.id) in IZJEME:
                continue
            else:
                besedilo = "?"
            if "b" not in besedilo:
                izid.append("%s:%d" % (rel, n.lineno))
    return izid


class KodiranjeBesedilnihDatotek(unittest.TestCase):
    def test_vsa_besedilna_odpiranja_z_encoding(self):
        self.assertEqual(_odpiranja_brez_kodiranja(), [])


@unittest.skipUnless(sys.platform.startswith("linux") and os.path.isdir("/proc/self"), "samo Linux")
class ImeProcesaSredZnaka(unittest.TestCase):
    def test_plank_tece_ne_pade(self):
        koda = ("import ctypes, time; ctypes.CDLL(None).prctl(15, ('ž' * 8).encode('utf-8')); "
                "time.sleep(30)")
        otrok = subprocess.Popen([sys.executable, "-c", koda])
        self.addCleanup(otrok.wait)
        self.addCleanup(otrok.kill)
        meja = time.monotonic() + 5
        comm = b""
        while time.monotonic() < meja:
            try:
                with open("/proc/%d/comm" % otrok.pid, "rb") as f:
                    comm = f.read()
            except OSError:
                break
            if comm.startswith(b"\xc5"):
                break
            time.sleep(0.05)
        if not comm.startswith(b"\xc5\xbe"):
            self.skipTest("prctl(PR_SET_NAME) tu ne dela")
        from core import os_dock
        prej = os_dock._v_flatpaku
        os_dock._v_flatpaku = lambda: False
        self.addCleanup(setattr, os_dock, "_v_flatpaku", prej)
        os_dock._zadnji_plank["pid"] = otrok.pid          # tudi pot z zadnjim znanim PID
        self.assertIsInstance(os_dock.plank_tece(), bool)


if __name__ == "__main__":
    unittest.main()
