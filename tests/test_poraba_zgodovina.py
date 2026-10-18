"""Zgodovina porabe za safeer://procesi (core/poraba_zgodovina.py): povprecje in vrh zadnje ure iz krozega medpomnilnika,
drevo procesov in vrste (glavni, spletni, omrezni, peskovnik, drugo) - s ponarejenim /proc in na pravem procesu."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

from core import poraba_zgodovina as pz


class LazenProc:
    def __init__(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-proc-")

    def proces(self, pid, ime, tiki=0, niti=1, rss_strani=0, otroci=(), zombi=False):
        d = os.path.join(self.mapa, str(pid))
        os.makedirs(os.path.join(d, "task", str(pid)), exist_ok=True)
        polja = ["Z" if zombi else "S"] + ["0"] * 10 + [str(tiki), "0"] + ["0"] * 4 + [str(niti)] + ["0"] * 10
        with open(os.path.join(d, "stat"), "w") as f:
            f.write("%d (%s) %s\n" % (pid, ime, " ".join(polja)))
        with open(os.path.join(d, "statm"), "w") as f:
            f.write("100 %d 0 0 0 0 0\n" % rss_strani)
        with open(os.path.join(d, "task", str(pid), "children"), "w") as f:
            f.write(" ".join(str(o) for o in otroci))

    def odstrani(self, pid):
        shutil.rmtree(os.path.join(self.mapa, str(pid)), ignore_errors=True)

    def pocisti(self):
        shutil.rmtree(self.mapa, ignore_errors=True)


class Zgodovina(unittest.TestCase):
    def setUp(self):
        self.p = LazenProc()

    def tearDown(self):
        self.p.pocisti()

    def test_drevo_vrste_in_povprecje_ter_vrh(self):
        strani_mb = 1024 // pz.PAGE_KB
        self.p.proces(10, "python3", tiki=0, niti=30, rss_strani=300 * strani_mb, otroci=(11, 12))
        self.p.proces(11, "WebKitNetworkPr", tiki=0, rss_strani=20 * strani_mb)
        self.p.proces(12, "bwrap", otroci=(13,))
        self.p.proces(13, "WebKitWebProces", tiki=0, niti=20, rss_strani=200 * strani_mb)
        z = pz.Zgodovina(koren=10, proc=self.p.mapa)
        self.assertFalse(z.ima_vzorce())
        self.assertEqual(z.vzorci(zdaj=1000.0), 4)
        self.assertIsNone(z.povzetek(10, zdaj=1000.0)["cpu_povp"])      # en vzorec: CPU se ni znan
        # 30 s pozneje: glavni porabi 3 s CPU (10 %), spletni 15 s (50 %) in zraste na 400 MB.
        self.p.proces(10, "python3", tiki=3 * pz.CLK_TCK, niti=30, rss_strani=300 * strani_mb, otroci=(11, 12))
        self.p.proces(13, "WebKitWebProces", tiki=15 * pz.CLK_TCK, niti=20, rss_strani=400 * strani_mb)
        z.vzorci(zdaj=1030.0)
        # se 30 s: spletni miruje
        self.p.proces(13, "WebKitWebProces", tiki=15 * pz.CLK_TCK, niti=20, rss_strani=300 * strani_mb)
        z.vzorci(zdaj=1060.0)
        vrste = {d["pid"]: d["vrsta"] for d in z.procesi()}
        self.assertEqual(vrste, {10: pz.GLAVNI, 11: pz.OMREZNI, 12: pz.PESKOVNIK, 13: pz.SPLETNI})
        s = z.povzetek(13, zdaj=1060.0)
        self.assertAlmostEqual(s["cpu_povp"], 0.25)
        self.assertAlmostEqual(s["cpu_vrh"], 0.5)
        self.assertAlmostEqual(s["cpu_zadnji"], 0.0)
        self.assertEqual((s["rss_povp_mb"], s["rss_vrh_mb"]), (300, 400))
        self.assertAlmostEqual(z.povzetek(10, zdaj=1060.0)["cpu_vrh"], 0.1)
        # Okno ene ure: vzorci, starejsi od ure, ne stejejo.
        self.assertEqual(z.povzetek(13, zdaj=1000.0 + 3600 + 31)["vzorcev"], 1)

    def test_konec_procesa_zombi_in_ponovna_raba_pid(self):
        self.p.proces(10, "python3", otroci=(11, 12))
        self.p.proces(11, "rqbit", tiki=100)
        self.p.proces(12, "ffmpeg", zombi=True)
        z = pz.Zgodovina(koren=10, proc=self.p.mapa)
        z.vzorci(zdaj=0.0)
        self.assertEqual(sorted(d["pid"] for d in z.procesi()), [10, 11])   # zombi ne steje
        self.p.proces(11, "WebKitWebProces", tiki=5)                         # isti PID, drug program
        z.vzorci(zdaj=30.0)
        self.assertEqual(z.povzetek(11, zdaj=30.0)["vzorcev"], 1)            # zgodovina rqbita ne velja zanj
        self.p.odstrani(11)
        z.vzorci(zdaj=60.0)
        self.assertIsNone(z.povzetek(11, zdaj=60.0))

    def test_krozni_medpomnilnik(self):
        self.p.proces(10, "python3")
        z = pz.Zgodovina(koren=10, proc=self.p.mapa, vzorcev=5)
        for i in range(12):
            z.vzorci(zdaj=float(i))
        self.assertEqual(z.povzetek(10, zdaj=11.0)["vzorcev"], 5)


@unittest.skipUnless(sys.platform.startswith("linux"), "/proc")
class PravProces(unittest.TestCase):
    def test_otrok_tega_procesa_in_cena_vzorca(self):
        otrok = subprocess.Popen([sys.executable, "-c", "import time\nx = bytearray(40 << 20)\nk = time.time() + 1.5\n"
                                  "while time.time() < k: pass\ntime.sleep(30)"])
        try:
            z = pz.Zgodovina()
            z.vzorci()
            time.sleep(1.0)
            z.vzorci()
            p = z.povzetek(otrok.pid)
            self.assertIsNotNone(p)
            self.assertGreater(p["cpu_vrh"], 0.3)          # otrok racuna
            self.assertGreaterEqual(p["rss_vrh_mb"], 40)
            self.assertIn(otrok.pid, [d["pid"] for d in z.procesi()])
            self.assertLess(z.zadnji_s, 0.05)
            t = pz.trenutno(otrok.pid, None)
            self.assertIsNone(t["cpu"])
            t2 = pz.trenutno(otrok.pid, t["branje"])
            self.assertIsNotNone(t2["cpu"])
        finally:
            otrok.kill()
            otrok.wait()


if __name__ == "__main__":
    unittest.main()
