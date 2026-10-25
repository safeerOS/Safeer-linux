"""Zapiranje slojev TLS in zacasnih datotek (nacrt stabilnosti P2, naloga 45) ter ruff samo za novo kodo.

Po ssl.wrap_socket je surova vticnica odklopljena (detach): zapreti je treba ovito. link_gledalec je ob napacnem odtisu
zapiral surovo (nic) - ovita je ostala odprta, dokler je zivela izjema (povezi() jo hrani kot `zadnja`)."""
import os
import shutil
import socket
import ssl
import subprocess
import sys
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)
sys.path.insert(0, os.path.join(KOREN, "tools"))

import ruff_nove_vrstice as rnv  # noqa: E402


def odprte_povezave(vrata: int) -> int:
    """Vticnice TEGA procesa, povezane na streznik preizkusa (oddaljena vrata `vrata`, /proc/self/net/tcp in tcp6).
    Prej je preizkus stel vse deskriptorje procesa: v teku z drugimi preizkusi jih odpira in zapira tudi nit, ki jo je
    pustil prejsnji preizkus (25. 10. 2026: 91 != 90 v teku, sam zelen)."""
    nase = set()
    for fd in os.listdir("/proc/self/fd"):
        try:
            cilj = os.readlink("/proc/self/fd/" + fd)
        except OSError:
            continue
        if cilj.startswith("socket:["):
            nase.add(cilj[len("socket:["):-1])
    n = 0
    for tabela in ("/proc/self/net/tcp", "/proc/self/net/tcp6"):
        try:
            with open(tabela, encoding="ascii") as f:
                next(f, None)
                for vrstica in f:
                    polja = vrstica.split()     # 2: oddaljeni naslov:vrata (hex), 9: inode
                    if len(polja) > 9 and int(polja[2].rsplit(":", 1)[1], 16) == vrata and polja[9] in nase:
                        n += 1
        except OSError:
            continue
    return n


STREZNIK = r"""
import socket, ssl, sys
kljuc, potrdilo, tls = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ctx.load_cert_chain(potrdilo, kljuc)
poslusa = socket.create_server(("127.0.0.1", 0))
print(poslusa.getsockname()[1], flush=True)
povezave = []
while True:
    s, _ = poslusa.accept()
    if tls:
        try:
            s = ctx.wrap_socket(s, server_side=True)
        except (ssl.SSLError, OSError):
            s.close()
            continue
    else:
        s.sendall(b"to ni TLS\r\n")
    povezave.append(s)
"""


class StreznikTls:
    """Lokalni streznik TLS (samopodpisano potrdilo, openssl) v LOCENEM procesu: /proc/self/fd preizkusa steje samo
    odjemalca."""

    def __init__(self, mapa: str, tls: bool = True) -> None:
        kljuc, potrdilo = os.path.join(mapa, "k.pem"), os.path.join(mapa, "c.pem")
        subprocess.run(["openssl", "req", "-x509", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1",
                        "-nodes", "-days", "1", "-subj", "/CN=preizkus", "-keyout", kljuc, "-out", potrdilo],
                       check=True, capture_output=True, timeout=30)
        self.proces = subprocess.Popen([sys.executable, "-c", STREZNIK, kljuc, potrdilo, "1" if tls else "0"],
                                       stdout=subprocess.PIPE, text=True)
        self.vrata = int(self.proces.stdout.readline())

    def ustavi(self) -> None:
        self.proces.kill()
        self.proces.wait(timeout=10)
        self.proces.stdout.close()


@unittest.skipUnless(os.path.isdir("/proc/self/fd") and shutil.which("openssl"), "brez /proc ali openssl")
class Tls(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="tls-")
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)

    def _gledalec(self, vrata: int, fp: str):
        from core import link_gledalec
        g = link_gledalec.Gledalec.__new__(link_gledalec.Gledalec)
        g.seja, g.cas_povezave = {"port": vrata, "fp": fp}, 5.0
        return g, link_gledalec

    def test_gledalec_napacen_odtis_zapre_tls(self):
        streznik = StreznikTls(self.d)
        self.addCleanup(streznik.ustavi)
        g, lg = self._gledalec(streznik.vrata, "0" * 64)
        prej = odprte_povezave(streznik.vrata)
        zadnja = None
        try:
            g._odpri("127.0.0.1", 5.0)
        except lg.NapakaGledalca as e:
            zadnja = e                        # kot povezi(): izjema (in z njo okvir) zivi naprej
        self.assertIsNotNone(zadnja)
        self.assertEqual(odprte_povezave(streznik.vrata), prej, "ovita vticnica TLS je ostala odprta")

    def test_rokovanje_odpove_brez_puscanja(self):
        """Streznik ne govori TLS: ssl zapre deskriptor sam (CPython ssl._create), nic ne ostane."""
        streznik = StreznikTls(self.d, tls=False)
        self.addCleanup(streznik.ustavi)
        g, lg = self._gledalec(streznik.vrata, "0" * 64)
        prej = odprte_povezave(streznik.vrata)
        with self.assertRaises(Exception):
            g._odpri("127.0.0.1", 2.0)
        self.assertEqual(odprte_povezave(streznik.vrata), prej)

    def test_link_tls_neujemanje_in_napaka_po_rokovanju(self):
        from core import link_tls
        streznik = StreznikTls(self.d)
        self.addCleanup(streznik.ustavi)
        for nacin in ("odtis", "napaka"):
            with self.subTest(nacin=nacin):
                prej = odprte_povezave(streznik.vrata)
                s = socket.create_connection(("127.0.0.1", streznik.vrata), 5)
                self.assertEqual(odprte_povezave(streznik.vrata), prej + 1, "stetje ne vidi odprte povezave")
                izvirnik = link_tls.odtis_potrdila
                if nacin == "napaka":
                    link_tls.odtis_potrdila = lambda _der: (_ for _ in ()).throw(OSError("pokvarjeno potrdilo"))
                zadnja = None
                try:
                    link_tls.ovij(s, "127.0.0.1", "f" * 64)
                except (link_tls.NeujemanjeOdtisa, OSError) as e:
                    zadnja = e                    # izjema s sledjo (okvir z vticnico) zivi naprej, kot pri klicatelju
                finally:
                    link_tls.odtis_potrdila = izvirnik
                self.assertIsNotNone(zadnja)
                s.close()
                self.assertEqual(odprte_povezave(streznik.vrata), prej)
                del zadnja


class Zacasne(unittest.TestCase):
    def beri(self, pot):
        with open(os.path.join(KOREN, pot), encoding="utf-8") as f:
            return f.read()

    def test_govor_pise_v_deskriptor(self):
        s = self.beri("core/os_govor.py")
        i = s.index('fd, pot = tempfile.mkstemp(prefix="safeer-govor-"')
        self.assertIn('with os.fdopen(fd, "wb") as datoteka, wave.open(datoteka, "wb") as w:', s[i:i + 600])
        self.assertNotIn("os.close(fd)", s[i:i + 600])

    def test_teamwork_zacasna_mapa_zasebna(self):
        from core import link_teamwork as tw
        d = tempfile.mkdtemp(prefix="tw-")
        self.addCleanup(shutil.rmtree, d, ignore_errors=True)
        os.makedirs(os.path.join(d, "tw", "zacasno"), mode=0o755)
        os.chmod(os.path.join(d, "tw", "zacasno"), 0o755)
        t = tw.Teamwork(razresi=lambda o: "", ime_naprave=lambda i: i, obvesti=lambda *a: None, ukaz=None,
                        okna=lambda: [], mapa=os.path.join(d, "tw"), procesi=None)
        m = t._mapa_zacasnih()
        self.assertEqual(os.stat(m).st_mode & 0o777, 0o700)

    def test_datoteke_streznik_ob_napaki_zapre_vrata(self):
        s = self.beri("core/link_datoteke.py")
        i = s.index("s.socket = ctx.wrap_socket(s.socket, server_side=True, do_handshake_on_connect=False)")
        self.assertIn("s.server_close()", s[i:i + 300])


class Ruff(unittest.TestCase):
    DIFF = (
        "diff --git a/core/a.py b/core/a.py\n--- a/core/a.py\n+++ b/core/a.py\n"
        "@@ -10,0 +11,2 @@ def f():\n+    try:\n+        x()\n"
        "@@ -40 +42 @@\n-    pass\n+    return\n"
        "diff --git a/core/b.py b/core/b.py\nnew file mode 100644\n--- /dev/null\n+++ b/core/b.py\n"
        "@@ -0,0 +1,3 @@\n+a\n+b\n+c\n")

    def test_spremenjene_vrstice(self):
        v = rnv.spremenjene_vrstice(self.DIFF)
        self.assertEqual(v["core/a.py"], {11, 12, 42})
        self.assertEqual(v["core/b.py"], {1, 2, 3})

    def test_samo_nove_najdbe(self):
        v = rnv.spremenjene_vrstice(self.DIFF)
        najdbe = [{"filename": "/r/core/a.py", "location": {"row": 12}, "code": "S110", "message": "try-except-pass"},
                  {"filename": "/r/core/a.py", "location": {"row": 30}, "code": "BLE001", "message": "stara koda"},
                  {"filename": "/r/core/c.py", "location": {"row": 1}, "code": "E722", "message": "nespremenjena"}]
        izid = rnv.nove_najdbe(najdbe, v, "/r")
        self.assertEqual([(n["filename"], n["location"]["row"]) for n in izid], [("core/a.py", 12)])

    def test_nastavitve_in_ci(self):
        with open(os.path.join(KOREN, "ruff.toml"), encoding="utf-8") as f:
            nastavitve = f.read()
        self.assertIn('select = ["S110", "BLE001", "E722"]', nastavitve)
        with open(os.path.join(KOREN, ".github", "workflows", "linux-packages.yml"), encoding="utf-8") as f:
            ci = f.read()
        self.assertIn("python3 tools/ruff_nove_vrstice.py", ci)
        self.assertIn("pip\" install -q ruff==", ci)
        self.assertIn("fetch-depth: 0", ci[ci.index("ruff-nova-koda:"):ci.index("ruff-nova-koda:") + 400])


if __name__ == "__main__":
    unittest.main()
