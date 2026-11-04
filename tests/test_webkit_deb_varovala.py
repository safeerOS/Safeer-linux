"""Lokalna gradnja nasega WebKita ne izbrise WebKita namescenega Safeerja (S16) in root razpakira samo preverjen arhiv
(N5) - tedenski pregled 4. 11. 2026."""
import io
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WD = os.path.join(KOREN, "packaging", "webkit-deb")


def _varovalo(predpona, dpkg_query_stanje=None):
    """Pozene predpona_namescena z laznima dpkg in dpkg-query v PATH (pravih paketov sistema ne vprasamo)."""
    with tempfile.TemporaryDirectory() as bin_:
        with open(os.path.join(bin_, "dpkg"), "w") as f:
            f.write("#!/bin/sh\nexit 1\n")              # dpkg -S: mapa ni datoteka nobenega paketa
        with open(os.path.join(bin_, "dpkg-query"), "w") as f:
            f.write("#!/bin/sh\n" + ('[ "$4" = safeer-os ] && { printf %%s %s; exit 0; }\n' % dpkg_query_stanje
                                     if dpkg_query_stanje else "") + "exit 1\n")
        for ime in ("dpkg", "dpkg-query"):
            os.chmod(os.path.join(bin_, ime), 0o755)
        izid = subprocess.run(["/bin/bash", "-c", '. "$1"; predpona_namescena "$2"', "_",
                               os.path.join(WD, "varovalo_predpone.sh"), predpona],
                              capture_output=True, text=True, timeout=30, env={"PATH": bin_ + ":/usr/bin:/bin"})
        return izid.stdout


def _arhiv(clani):
    b = io.BytesIO()
    with tarfile.open(fileobj=b, mode="w") as t:
        for ime, vrsta, cilj in clani:
            i = tarfile.TarInfo(ime)
            i.type = vrsta
            if cilj is not None:
                i.linkname = cilj
            podatki = b"x" if vrsta == tarfile.REGTYPE else b""
            i.size = len(podatki)
            t.addfile(i, io.BytesIO(podatki))
    return b.getvalue()


def _preveri(podatki):
    return subprocess.run([sys.executable, os.path.join(WD, "preveri_arhiv.py"), "usr/lib/safeer-webkit", "src/build/predbolt"],
                          input=podatki, capture_output=True, timeout=30).returncode


R, D, S, H = tarfile.REGTYPE, tarfile.DIRTYPE, tarfile.SYMTYPE, tarfile.LNKTYPE
DOBRO = [("usr/lib/safeer-webkit", D, None), ("usr/lib/safeer-webkit/lib/libwebkitgtk-6.0.so.4", R, None),
         ("usr/lib/safeer-webkit/lib/libwebkitgtk-6.0.so", S, "libwebkitgtk-6.0.so.4"),
         ("usr/lib/safeer-webkit/lib/kopija", H, "usr/lib/safeer-webkit/lib/libwebkitgtk-6.0.so.4"),
         ("src/build/predbolt/cmake.txt", R, None)]


class VarovaloPredpone(unittest.TestCase):
    def test_odtis_namescene_gradnje(self):
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "share", "webkitgtk-safeer"))
            self.assertEqual(_varovalo(d), "")
            open(os.path.join(d, "share", "webkitgtk-safeer", "odtis"), "w").close()
            self.assertIn("odtis", _varovalo(d))

    def test_namescen_paket_safeer(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIn("safeer-os", _varovalo(d, "installed"))
            self.assertIn("safeer-os", _varovalo(d, "half-configured"))
            self.assertEqual(_varovalo(d, "config-files"), "")

    def test_skripti_uporabita_varovalo_pred_brisanjem(self):
        for ime in ("zgradi.sh", "nadaljuj.sh"):
            with self.subTest(ime), open(os.path.join(WD, ime), encoding="utf-8") as f:
                s = f.read()
            self.assertLess(s.index('predpona_namescena "$PREDPONA"'), s.index('rm -rf "$PREDPONA"'))
        with open(os.path.join(WD, "nadaljuj.sh"), encoding="utf-8") as f:
            s = f.read()
        self.assertLess(s.index("preveri_arhiv.py"), s.index('rm -rf "$PREDPONA" "$Z"'))
        self.assertLess(s.index('rm -rf "$PREDPONA" "$Z"'), s.index("tar -C / "))


class PreveriArhiv(unittest.TestCase):
    def test_dober_arhiv(self):
        self.assertEqual(_preveri(_arhiv(DOBRO)), 0)

    def test_nevarni_clani(self):
        for clan in [("/etc/cron.d/x", R, None), ("usr/lib/safeer-webkit/../../../etc/x", R, None),
                     ("etc/passwd", R, None), ("usr/lib/safeer-webkit-drugo/x", R, None),
                     ("usr/lib/safeer-webkit/lib/ven", S, "../../../../etc/shadow"),
                     ("usr/lib/safeer-webkit/lib/abs", S, "/etc/shadow"),
                     ("usr/lib/safeer-webkit/lib/trda", H, "etc/shadow"),
                     ("usr/lib/safeer-webkit/naprava", tarfile.CHRTYPE, None),
                     ("usr/lib/safeer-webkit/fifo", tarfile.FIFOTYPE, None)]:
            with self.subTest(clan[0]):
                self.assertEqual(_preveri(_arhiv(DOBRO + [clan])), 1)

    def test_prazen_ali_pokvarjen(self):
        self.assertEqual(_preveri(b""), 1)
        self.assertEqual(_preveri(b"ni arhiv" * 100), 1)


if __name__ == "__main__":
    unittest.main()
