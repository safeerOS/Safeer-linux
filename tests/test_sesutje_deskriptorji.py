"""Sesutje ob odpiranju Sporocil (lastnik, 16. 10. 2026, 20:12, safeer-os 0.4.84 .deb, --delovna po 14 h).

Jedrni odtis: SIGTRAP v g_log iz libwebkitgtk-6.0 pod webkit_web_view_load_uri - sporocilo na tem mestu je
g_error("Failed to create memfd: %s"): WebKit ob zagonu novega spletnega procesa ni dobil deskriptorja (EMFILE).
Mehka meja odprtih datotek je bila 1024; Hub Linka (vrata 8990, HTTP/1.1 keep-alive brez roka) je drzal odprte vse
povezave naprav (novi proces: 41 povezav z dveh naprav po 16 minutah, skupaj 204 deskriptorji). stderr je sel v
/dev/null (safeer-cinnamon), zato besedilo napake ni bilo nikjer zapisano.

Preizkusi: (1) mehka meja se dvigne, (2) Hub zapre povezavo, ki ne poslje zahteve, (3) zaganjalnik pise stderr v
sled.log z omejeno velikostjo.
"""
import http.server
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)


class OmejitevDatotek(unittest.TestCase):
    def test_mehka_meja_se_dvigne(self):
        koda = (
            "import resource, sys; sys.path.insert(0, %r)\n"
            "m, t = resource.getrlimit(resource.RLIMIT_NOFILE)\n"
            "resource.setrlimit(resource.RLIMIT_NOFILE, (min(1024, t), t))\n"
            "from core import os_stabilnost as s\n"
            "nova = s.dvigni_omejitev_datotek()\n"
            "m2, t2 = resource.getrlimit(resource.RLIMIT_NOFILE)\n"
            "cilj = s.NAJVEC_DATOTEK if t == resource.RLIM_INFINITY else min(t, s.NAJVEC_DATOTEK)\n"
            "assert m2 == nova == cilj and t2 == t, (m2, nova, cilj, t2, t)\n"
            "print('ok')\n" % KOREN)
        izid = subprocess.run([sys.executable, "-c", koda], capture_output=True, text=True, timeout=60)
        self.assertEqual(izid.stdout.strip(), "ok", izid.stderr)

    def test_vkljuci_dvigne_mejo(self):
        from core import os_stabilnost
        vir = open(os.path.join(KOREN, "core", "os_stabilnost.py"), encoding="utf-8").read()
        telo = vir[vir.index("def vkljuci("):]
        self.assertLess(telo.index("dvigni_omejitev_datotek()"), telo.index("faulthandler.enable"))
        self.assertGreaterEqual(os_stabilnost.NAJVEC_DATOTEK, 8192)


class HubKeepAlive(unittest.TestCase):
    def test_tiha_povezava_se_zapre(self):
        from core import link_hub_streznik

        class Obravnava(link_hub_streznik._Obravnava):
            ROK_CAKANJA_ZAHTEVE_S = 0.4

        streznik = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Obravnava)
        streznik.daemon_threads = True
        nit = threading.Thread(target=streznik.serve_forever, daemon=True)
        nit.start()
        try:
            s = socket.create_connection(streznik.server_address, timeout=5)
            zacetek = time.monotonic()
            try:
                podatki = s.recv(1024)          # streznik ne odgovori nicesar, samo zapre
            except ConnectionResetError:
                podatki = b""
            self.assertEqual(podatki, b"")
            self.assertLess(time.monotonic() - zacetek, 4.0)
            s.close()
        finally:
            streznik.shutdown()
            streznik.server_close()

    def test_rok_samo_za_cakanje_na_zahtevo(self):
        from core import link_hub_streznik
        self.assertEqual(link_hub_streznik._Obravnava.ROK_CAKANJA_ZAHTEVE_S, 10.0)   # lastnik 17. 10. 2026
        vir = open(os.path.join(KOREN, "core", "link_hub_streznik.py"), encoding="utf-8").read()
        telo = vir[vir.index("    def parse_request(self) -> bool:"):]
        telo = telo[:telo.index("\n    def ", 10)]
        self.assertIn('getattr(self.server, "rok_po_rokovanju", None)', telo)


class ZaganjalnikSled(unittest.TestCase):
    def _drevo(self, mapa: str, program: str) -> str:
        os.makedirs(os.path.join(mapa, "bin"))
        os.makedirs(os.path.join(mapa, "lib", "safeer-os", "core"))
        zaganjalnik = os.path.join(mapa, "bin", "safeer-os")
        shutil.copy(os.path.join(KOREN, "packaging", "safeer-os-launcher"), zaganjalnik)
        os.chmod(zaganjalnik, os.stat(zaganjalnik).st_mode | stat.S_IXUSR)
        # --delovna tece pod varuhom procesov (18. 10. 2026); brez Namizje.qml varuh lupine ne zazene.
        shutil.copy(os.path.join(KOREN, "core", "varuh_procesov.py"), os.path.join(mapa, "lib", "safeer-os", "core"))
        with open(os.path.join(mapa, "lib", "safeer-os", "safeer_os.py"), "w", encoding="utf-8") as f:
            f.write(program)
        return zaganjalnik

    def _zazeni(self, mapa: str, nacin: str):
        predpomnilnik = os.path.join(mapa, "cache")
        os.makedirs(os.path.join(predpomnilnik, "safeer-os"))
        sled = os.path.join(predpomnilnik, "safeer-os", "sled.log")
        with open(sled, "w", encoding="utf-8") as f:
            f.write("stara vrstica\n" * 40000)            # ~560 KB, vec kot meja
        izvajanje = os.path.join(mapa, "run")
        os.makedirs(izvajanje, mode=0o700)
        okolje = dict(os.environ, XDG_CACHE_HOME=predpomnilnik, XDG_RUNTIME_DIR=izvajanje, HOME=mapa,
                      PYTHON=sys.executable, SAFEER_OS_BREZ_FLATPAKA="1")
        for ime in ("SAFEER_OS_BREZ_NADZORA", "SAFEER_LUPINA_VTIC", "NOTIFY_SOCKET"):
            okolje.pop(ime, None)
        izid = subprocess.run([os.path.join(mapa, "bin", "safeer-os"), nacin], env=okolje, stdin=subprocess.DEVNULL,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual(izid.returncode, 0, izid.stderr)
        self.assertEqual(izid.stderr, b"")                    # ni terminala: vse je v sled.log
        with open(sled, encoding="utf-8") as f:
            return f.read(), os.path.getsize(sled)

    def test_stderr_v_sled_z_omejitvijo(self):
        """Zaganjalnik sam (okno, predvajalnik, zagon iz menija): sled obreze ob zagonu in vanjo pise stderr."""
        with tempfile.TemporaryDirectory() as mapa:
            self._drevo(mapa, "import sys\nsys.stderr.write('WebKit: Failed to create memfd\\n')\n")
            besedilo, velikost = self._zazeni(mapa, "--okno")
            self.assertIn("WebKit: Failed to create memfd", besedilo)
            self.assertTrue(besedilo.startswith("... (starejsi zapisi so odrezani)"))
            self.assertLessEqual(velikost, 262144)

    def test_delovna_stderr_v_sled_prek_varuha(self):
        """--delovna (ob prijavi) gre pod varuha procesov: stderr Safeer OS je v sled.log, ne v /dev/null. Sled obreze
        Safeer OS sam ob zagonu (core/os_stabilnost.vkljuci), zato je tu lazni program ne."""
        with tempfile.TemporaryDirectory() as mapa:
            self._drevo(mapa, "import sys\nsys.stderr.write('WebKit: Failed to create memfd\\n')\n")
            besedilo, _velikost = self._zazeni(mapa, "--delovna")
            self.assertTrue(besedilo.startswith("stara vrstica\n"), "varuh dopisuje, ne prepise")
            self.assertTrue(besedilo.endswith("WebKit: Failed to create memfd\n"))
            with open(os.path.join(mapa, "cache", "safeer-os", "dnevnik.log"), encoding="utf-8") as f:
                self.assertIn("Safeer OS se je koncal (0)", f.read())

if __name__ == "__main__":
    unittest.main()
