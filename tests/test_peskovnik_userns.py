"""Peskovnik WebKita na Ubuntu 24.04+ (omejeni uporabniski imenski prostori): profil AppArmor v paketu .deb in zaznava
v programu (core/peskovnik_userns.py). Brez tega WebKit ob prvi strani konca ves proces z g_error."""
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KOREN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOREN))

from core import peskovnik_userns as p  # noqa: E402

PROFILI = {"safeer-os": "/usr/bin/safeer-os", "safeer-control": "/usr/bin/safeer-control",
           "safeer-browser": "/usr/bin/safeer"}


def _program(mapa: Path, ime: str, telo: str) -> str:
    pot = mapa / ime
    pot.write_text("#!/bin/sh\n" + telo + "\n")
    pot.chmod(pot.stat().st_mode | stat.S_IXUSR)
    return str(pot)


class Zaznava(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.d = Path(self._d.name)
        self.omejitev = self.d / "omejitev"
        self.oznaka = self.d / "oznaka"
        self.dober = _program(self.d, "bwrap-dober", "exit 0")
        self.slab = _program(self.d, "bwrap-slab", "echo 'bwrap: setting up uid map: Permission denied' >&2; exit 1")

    def tearDown(self):
        self._d.cleanup()

    def _preveri(self, omejeno: str, oznaka: str, bwrap: str, okolje=None):
        self.omejitev.write_text(omejeno + "\n")
        self.oznaka.write_text(oznaka + "\n")
        okolje = {} if okolje is None else okolje
        return p.pripravi(okolje, pot_omejitve=str(self.omejitev), poti_oznake=(str(self.oznaka),), bwrap=bwrap), okolje

    def test_mint_brez_omejitve(self):
        stanje, okolje = self._preveri("0", "unconfined", self.slab)
        self.assertTrue(stanje["deluje"])
        self.assertFalse(stanje["izklopljen"])
        self.assertNotIn(p.IZKLOP, okolje)

    def test_ubuntu_z_nasim_profilom_brez_poskusa(self):
        # Profil velja: poskusa ni (slab bwrap bi sicer pokazal napako).
        stanje, okolje = self._preveri("1", "safeer-os (unconfined)", self.slab)
        self.assertTrue(stanje["deluje"])
        self.assertNotIn(p.IZKLOP, okolje)

    def test_ubuntu_brez_profila_a_bwrap_deluje(self):
        # Npr. setuid bwrap ali skrbnikov profil za /usr/bin/bwrap.
        stanje, okolje = self._preveri("1", "unconfined", self.dober)
        self.assertTrue(stanje["deluje"])
        self.assertNotIn(p.IZKLOP, okolje)

    def test_ubuntu_brez_profila_izklopi_peskovnik_namesto_sesutja(self):
        stanje, okolje = self._preveri("1", "unconfined", self.slab)
        self.assertFalse(stanje["deluje"])
        self.assertTrue(stanje["izklopljen"])
        self.assertEqual(okolje[p.IZKLOP], "1")

    def test_flatpak_in_ze_izklopljen(self):
        stanje, _ = self._preveri("1", "unconfined", self.slab, {"FLATPAK_ID": "io.github.memelandfaner.SafeerOS"})
        self.assertTrue(stanje["deluje"])
        stanje, _ = self._preveri("1", "unconfined", self.slab, {p.IZKLOP: "1"})
        self.assertFalse(stanje["izklopljen"])

    def test_brez_datotek_jedra(self):
        self.assertFalse(p.omejeno(str(self.d / "ni")))
        self.assertEqual(p.oznaka((str(self.d / "ni"),)), "")

    def test_poskus_je_isti_kot_webkitov(self):
        # Source/WTF/wtf/glib/Sandbox.cpp: isInsideUnsupportedContainer()
        self.assertEqual(p.POSKUS, ("--ro-bind", "/", "/", "--proc", "/proc", "--dev", "/dev", "--unshare-all", "true"))

    def test_pojasnilo_v_vseh_jezikih_in_enkrat(self):
        self.assertEqual(set(p.BESEDILA), {"sl", "en", "de", "es", "fr", "it"})
        for jezik, b in p.BESEDILA.items():
            self.assertEqual(set(b), {"naslov", "besedilo", "brez_profila"}, jezik)
        etc = self.d / "apparmor.d"
        etc.mkdir()
        (etc / "safeer-os").write_text("x")
        naslov, besedilo = p.besedilo("sl", "Safeer OS", "safeer-os", str(etc))
        self.assertIn("sudo apparmor_parser -r /etc/apparmor.d/safeer-os", besedilo)
        _n, brez = p.besedilo("fr", "Safeer OS", "safeer-os", str(self.d / "ni"))
        self.assertNotIn("apparmor_parser", brez)
        self.assertIn("Flatpak", brez)
        self.assertEqual(p.besedilo("xx", "A", "safeer-os", str(etc))[0], p.BESEDILA["en"]["naslov"])
        poslano = []
        self.assertTrue(p.pojasni_enkrat(str(self.d / "nast"), lambda: poslano.append(1)))
        self.assertFalse(p.pojasni_enkrat(str(self.d / "nast"), lambda: poslano.append(1)))
        self.assertEqual(poslano, [1])

    def test_vstopne_tocke_pred_aplikacijo(self):
        for ime, razred in (("safeer_os.py", "SafeerOS("), ("safeer_control.py", "SafeerControl(ozadje"),
                            ("safeer_brskalnik.py", "SafeerBrskalnik()")):
            vir = (KOREN / ime).read_text(encoding="utf-8")
            telo = vir[vir.index("\ndef main("):]
            self.assertLess(telo.index("peskovnik_userns.pripravi()"), telo.index(razred), ime)
            self.assertIn("peskovnik_userns.pojasni_kasneje(", telo, ime)


class ProfiliAppArmor(unittest.TestCase):
    def test_profili(self):
        for ime, pot in PROFILI.items():
            besedilo = (KOREN / "packaging" / "apparmor" / ime).read_text(encoding="ascii")
            self.assertIn("abi <abi/4.0>,", besedilo)
            self.assertRegex(besedilo, r"(?m)^profile %s %s flags=\(unconfined\) \{$" % (re.escape(ime), re.escape(pot)))
            self.assertRegex(besedilo, r"(?m)^  userns,$")
            self.assertIn("include if exists <local/%s>" % ime, besedilo)

    @unittest.skipUnless(shutil.which("apparmor_parser") or os.environ.get("SAFEER_APPARMOR_PARSER"),
                         "ni apparmor_parser")
    def test_profili_se_prevedejo(self):
        parser = os.environ.get("SAFEER_APPARMOR_PARSER") or shutil.which("apparmor_parser")
        dodatno = os.environ.get("SAFEER_APPARMOR_ARGUMENTI", "").split()
        for ime in PROFILI:
            r = subprocess.run([parser, *dodatno, "-Q", "-K", "-T", "-S",
                                str(KOREN / "packaging" / "apparmor" / ime)], capture_output=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr.decode(errors="replace"))
            self.assertGreater(len(r.stdout), 500, ime)

    def test_namesti_v_paket_kot_conffile(self):
        with tempfile.TemporaryDirectory() as d:
            for _ in range(2):    # dvakrat: conffiles brez podvojenih vrstic
                subprocess.run(["bash", str(KOREN / "packaging" / "apparmor" / "namesti.sh"), d, "safeer-os",
                                "safeer-control"], check=True)
            self.assertEqual(Path(d, "DEBIAN", "conffiles").read_text().splitlines(),
                             ["/etc/apparmor.d/safeer-os", "/etc/apparmor.d/safeer-control"])
            self.assertEqual(stat.S_IMODE(os.stat(Path(d, "etc", "apparmor.d", "safeer-os")).st_mode), 0o644)

    def _skripte(self, builder):
        text = (KOREN / builder).read_text()
        return dict(re.findall(r"cat << 'EOF2?' > \"\$BUILD_ROOT/DEBIAN/(postinst|prerm|postrm)\"\n(.*?)\nEOF2?\n",
                               text, re.S))

    def test_postinst_nalozi_postrm_odstrani(self):
        for builder, profili in (("build_os_deb.sh", ["safeer-os", "safeer-control"]),
                                 ("build_deb.sh", ["safeer-browser"])):
            besedilo = (KOREN / builder).read_text()
            self.assertIn('packaging/apparmor/namesti.sh" "$BUILD_ROOT" ' + " ".join(profili), besedilo)
            skripte = self._skripte(builder)
            with tempfile.TemporaryDirectory() as d:
                d = Path(d)
                (d / "sys").mkdir()
                (d / "etc").mkdir()
                for ime in profili:
                    (d / "etc" / ime).write_text("x")
                dnevnik = d / "klici"
                kos = d / "bin"
                kos.mkdir()
                _program(kos, "apparmor_parser", 'echo "$*" >> %s' % dnevnik)

                def tek(ime, dejanje, sys_pot):
                    telo = skripte[ime].replace("/sys/kernel/security/apparmor", sys_pot)
                    telo = telo.replace("/etc/apparmor.d/", str(d / "etc") + "/")
                    telo = telo.replace("/usr/bin/", "/nonexistent/").replace("/usr/sbin/", "/nonexistent/")
                    telo = telo.replace("/usr/lib/", "/nonexistent/lib/")
                    subprocess.run(["sh", "-c", telo, ime, dejanje], check=True, env={"PATH": str(kos) + ":/bin"},
                                   capture_output=True)
                    vsebina = dnevnik.read_text().splitlines() if dnevnik.exists() else []
                    dnevnik.unlink(missing_ok=True)
                    return vsebina

                self.assertEqual(tek("postinst", "configure", str(d / "sys")),
                                 ["-r -T -W %s/%s" % (d / "etc", ime) for ime in profili], builder)
                self.assertEqual(tek("postinst", "configure", str(d / "ni-apparmorja")), [], builder)
                self.assertEqual(tek("postrm", "remove", str(d / "sys")),
                                 ["-R %s/%s" % (d / "etc", ime) for ime in profili], builder)
                self.assertEqual(tek("postrm", "upgrade", str(d / "sys")), [], builder)


if __name__ == "__main__":
    unittest.main()
