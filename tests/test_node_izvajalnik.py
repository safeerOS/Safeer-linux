"""Node.js 22 LTS v paketu safeer-os (lastnik: nacin »deb«): pripet arhiv, preverjena SHA-256, zasebna predpona, brez
trka s sistemskim node (packaging/node_vendor.py, core/node_izvajalnik.py)."""
import hashlib
import io
import os
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

KOREN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOREN))
sys.path.insert(0, str(KOREN / "packaging"))

import node_vendor as nv  # noqa: E402
from core import node_izvajalnik as ni  # noqa: E402


def _arhiv(pot: Path, clani: dict, povezave: dict = None) -> str:
    """tar.xz s clani {ime: vsebina}; vrne SHA-256."""
    with tarfile.open(pot, "w:xz") as t:
        for ime, vsebina in clani.items():
            info = tarfile.TarInfo(ime)
            info.size = len(vsebina)
            info.mode = 0o755
            t.addfile(info, io.BytesIO(vsebina))
        for ime, cilj in (povezave or {}).items():
            info = tarfile.TarInfo(ime)
            info.type = tarfile.SYMTYPE
            info.linkname = cilj
            t.addfile(info)
    return hashlib.sha256(pot.read_bytes()).hexdigest()


class Pripeto(unittest.TestCase):
    def test_razlicica_22_lts_in_vir(self):
        self.assertRegex(nv.RAZLICICA, r"^22\.\d+\.\d+$")
        self.assertRegex(nv.SHA256, r"^[0-9a-f]{64}$")
        self.assertEqual(nv.URL, "https://nodejs.org/dist/v%s/node-v%s-linux-x64.tar.xz" % (nv.RAZLICICA, nv.RAZLICICA))
        self.assertEqual({v[0] for v in nv.CLANI.values()}, {"bin/node", "LICENSE"})

    def test_razpakira_samo_node_in_licenco(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            a = d / "node.tar.xz"
            sha = _arhiv(a, {nv.IME + "/bin/node": b"#!/bin/sh\n", nv.IME + "/LICENSE": b"MIT\n",
                             nv.IME + "/bin/npm": b"x", nv.IME + "/../../ven": b"x", "/etc/passwd": b"x"})
            nv.razpakiraj(str(a), str(d / "cilj"), sha=sha)
            self.assertEqual(sorted(str(p.relative_to(d / "cilj")) for p in (d / "cilj").rglob("*") if p.is_file()),
                             ["LICENSE", "RAZLICICA", "bin/node"])
            self.assertEqual(stat.S_IMODE((d / "cilj" / "bin" / "node").stat().st_mode), 0o755)
            self.assertEqual((d / "cilj" / "RAZLICICA").read_text().strip(), nv.RAZLICICA)
            self.assertFalse((d / "ven").exists())

    def test_napacna_sha_ali_povezava_ustavi_gradnjo(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            a = d / "node.tar.xz"
            sha = _arhiv(a, {nv.IME + "/LICENSE": b"MIT\n"}, {nv.IME + "/bin/node": "/bin/sh"})
            with self.assertRaises(SystemExit):
                nv.razpakiraj(str(a), str(d / "c1"), sha="0" * 64)
            with self.assertRaises(SystemExit):        # simbolna povezava namesto programa
                nv.razpakiraj(str(a), str(d / "c2"), sha=sha)
            # Prenos z napacno SHA-256 ne pusti datoteke v predpomnilniku.
            with self.assertRaises(SystemExit):
                nv.prenesi(str(d / "predpomnilnik"), url=a.as_uri(), sha="0" * 64)
            self.assertEqual(list((d / "predpomnilnik").iterdir()), [])
            pot = nv.prenesi(str(d / "predpomnilnik"), url=a.as_uri(), sha=sha)
            self.assertEqual(hashlib.sha256(Path(pot).read_bytes()).hexdigest(), sha)

    def test_pravi_arhiv_ce_je_v_predpomnilniku(self):
        """Pravi Node.js (CI in lokalna gradnja ga imata v build/cache/node): razpakiran, oskubljen in zagnan."""
        arhiv = KOREN / "build" / "cache" / "node" / (nv.IME + ".tar.xz")
        if not arhiv.is_file():
            self.skipTest("arhiva Node.js ni v build/cache/node")
        with tempfile.TemporaryDirectory() as d:
            nv.razpakiraj(str(arhiv), d)
            nv.oskubi(d)
            nv.preveri(d)
            self.assertIn("Node.js", (Path(d) / "LICENSE").read_text(encoding="utf-8", errors="replace")[:200])


class Izvajalnik(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.lib = Path(self._d.name) / "usr" / "lib"
        node = self.lib / "safeer-os" / "node" / "bin" / "node"
        node.parent.mkdir(parents=True)
        node.write_text("#!/bin/sh\necho v22.23.3\n")
        node.chmod(0o755)
        (self.lib / "safeer-control").mkdir()
        ni._razlicice.clear()

    def tearDown(self):
        self._d.cleanup()
        ni._razlicice.clear()

    def test_nas_node_tudi_za_control(self):
        pricakovano = str(self.lib / "safeer-os" / "node" / "bin" / "node")
        self.assertEqual(ni.pot(str(self.lib / "safeer-os")), pricakovano)
        self.assertEqual(ni.pot(str(self.lib / "safeer-control")), pricakovano)
        self.assertEqual(ni.ukaz(["-e", "1"], str(self.lib / "safeer-os")), [pricakovano, "-e", "1"])

    def test_sistemski_samo_dovolj_nov(self):
        brez = str(Path(self._d.name) / "brez")
        star = Path(self._d.name) / "bin18" / "node"
        star.parent.mkdir()
        star.write_text("#!/bin/sh\necho v18.19.1\n")
        star.chmod(0o755)
        with mock.patch.dict(os.environ, {"PATH": str(star.parent)}):
            self.assertIsNone(ni.pot(brez))
            self.assertIsNone(ni.pot(brez, sistemski=False))
        nov = Path(self._d.name) / "bin24" / "node"
        nov.parent.mkdir()
        nov.write_text("#!/bin/sh\necho v24.11.0\n")
        nov.chmod(0o755)
        with mock.patch.dict(os.environ, {"PATH": str(nov.parent)}):
            self.assertEqual(ni.pot(brez), str(nov))

    def test_okolje_brez_tujih_nastavitev_in_zasebnih_poti(self):
        koren = str(self.lib / "safeer-os")
        with mock.patch.dict(os.environ, {"NODE_OPTIONS": "--require /tmp/tuje.js", "NODE_PATH": "/x",
                                          "GI_TYPELIB_PATH": "/usr/lib/safeer-os/webkit/lib/girepository-1.0",
                                          "PATH": "/usr/bin:/bin", "NODE_EXTRA_CA_CERTS": "/etc/ca.pem"}):
            o = ni.okolje(koren=koren)
        self.assertNotIn("NODE_OPTIONS", o)
        self.assertNotIn("NODE_PATH", o)
        self.assertNotIn("GI_TYPELIB_PATH", o)
        self.assertEqual(o["NODE_EXTRA_CA_CERTS"], "/etc/ca.pem")   # zaupanje sistema ostane
        self.assertEqual(o["PATH"].split(os.pathsep)[0], str(self.lib / "safeer-os" / "node" / "bin"))
        r = subprocess.run(ni.ukaz([], koren), capture_output=True, text=True, env=o, timeout=30)
        self.assertEqual(r.stdout.strip(), "v22.23.3")


class Paket(unittest.TestCase):
    def test_build_os_deb(self):
        b = (KOREN / "build_os_deb.sh").read_text(encoding="utf-8")
        self.assertIn('python3 "$DIR/packaging/node_vendor.py" "$BUILD_ROOT/usr/lib/safeer-os/node"', b)
        self.assertIn("usr/share/doc/safeer-os/nodejs/LICENSE", b)
        self.assertIn("${NODE_ODVISNOSTI}", b)
        self.assertNotRegex(b, r"usr/bin/node\b")
        self.assertRegex(b, r'if \[ -n "\$WEBKIT_TAR" \] (\|\| \[[^]]*\] )*\|\| \[ "\$NODE" = 1 \]; then ARCH="amd64"')
        for tovor in ("install_os_payload.sh", "install_control_payload.sh"):
            self.assertRegex((KOREN / "packaging" / tovor).read_text(), r"for modul in [^\n]*\bnode_izvajalnik\b")

    def test_preizkusi_gradnje_brez_prenosa(self):
        for ime in ("test_delovna.py", "test_od_vklopa.py"):
            besedilo = (KOREN / "tests" / ime).read_text(encoding="utf-8")
            self.assertTrue(re.search(r'SAFEER_DEB_BREZ_NODE="1"', besedilo), ime)


if __name__ == "__main__":
    unittest.main()
