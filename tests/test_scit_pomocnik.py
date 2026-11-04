"""Scit (DNS) prek root pomocnika (tedenski pregled 4. 11. 2026, S15).

Prejsnje pravilo polkit je VSAKEMU programu skrbnika dovolilo poljuben DNS (org.freedesktop.resolve1.*) brez gesla.
Zdaj: pomocnik /usr/lib/safeer-os/scit-dns s fiksnimi dejanji in naslovom 127.0.0.1 na vratih Scita, lastno dejanje
polkit si.safeer.os.scit, pravilo samo zanj; postinst staro pravilo zamenja. Brez popravka ti preizkusi padejo
(pomocnika, dejanja in os_scit.pomocnik ni)."""
import importlib.machinery
import importlib.util
import os
import re
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

KOREN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOREN))

from core import os_scit, root_ukaz  # noqa: E402

POMOCNIK_VIR = KOREN / "packaging" / "scit-dns"
POLICY = KOREN / "packaging" / "si.safeer.os.scit.policy"
DEB = KOREN / "build_os_deb.sh"


def _pomocnik_modul():
    nalagalnik = importlib.machinery.SourceFileLoader("scit_dns_pomocnik", str(POMOCNIK_VIR))
    spec = importlib.util.spec_from_loader("scit_dns_pomocnik", nalagalnik)
    modul = importlib.util.module_from_spec(spec)
    nalagalnik.exec_module(modul)
    return modul


class Pomocnik(unittest.TestCase):
    def setUp(self):
        self.p = _pomocnik_modul()
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        for ime in ("eth0", "wlp2s0", "enx00e04c680001"):
            os.mkdir(os.path.join(self.mapa.name, ime))
        self.p.SISTEM_NET = self.mapa.name
        self.klici = []
        self.p._zazeni = self._lazno

    def _lazno(self, ukaz):
        self.klici.append(list(ukaz))
        if ukaz[:2] == [self.p.NMCLI, "-g"] and ukaz[2] == "IP4.DNS,IP6.DNS":
            return 0, "192.168.1.1 | 127.0.0.1\n-x\nfe80::1\\:2\n0.0.0.0\n192.168.1.1\n"
        if ukaz[:2] == [self.p.NMCLI, "-g"]:
            return 0, "lan\n-h\n~.\n"
        if ukaz[:2] == [self.p.RESOLVECTL, "domain"] and len(ukaz) == 3:
            return 0, "Link 2 (eth0):\n"
        return 0, ""

    def test_shebang_in_absolutne_poti(self):
        besedilo = POMOCNIK_VIR.read_text(encoding="utf-8")
        self.assertTrue(besedilo.startswith("#!/usr/bin/python3 -I\n"), "brez PYTHONPATH in mape klicatelja")
        self.assertEqual(self.p.RESOLVECTL, "/usr/bin/resolvectl")
        self.assertEqual(self.p.NMCLI, "/usr/bin/nmcli")
        self.assertNotIn("shell=True", besedilo)
        self.assertEqual(self.p.VRATA, os_scit.VRATA)
        self.assertEqual(self.p.NASLOV, os_scit.NASLOV)

    def test_zavrne_nedovoljene_argumente(self):
        for slabi in ([], ["usmeri"], ["usmeri", "eth0"], ["usmeri", "eth0", "53"], ["usmeri", "eth0", "1.1.1.1"],
                      ["usmeri", "eth0", "1.1.1.1:53"], ["usmeri", "eth0", "5354", "8.8.8.8"],
                      ["usmeri", "eth0", "05354"], ["usmeri", "eth0", "+5354"], ["usmeri", "eth0", "5358"],
                      ["usmeri", "-h", "5354"], ["usmeri", "../eth0", "5354"], ["usmeri", "eth9", "5354"],
                      ["usmeri", "eth0/..", "5354"], ["usmeri", "a" * 16, "5354"], ["usmeri", "eth 0", "5354"],
                      ["povrni"], ["povrni", "/etc"], ["povrni", "eth0", "8.8.8.8"], ["domene", "eth0", "evil.com"],
                      ["dovoli", "/tmp/pravilo.rules"], ["revert", "eth0"], ["dns", "eth0", "8.8.8.8"],
                      ["--help"], ["usmeri", "eth0\n", "5354"]):
            self.assertIsNone(self.p.razcleni(slabi), slabi)
            self.klici.clear()
            self.assertEqual(self.p.main(slabi), 2, slabi)
            self.assertEqual(self.klici, [], "nic se ne zazene: %r" % slabi)

    def test_sprejme_samo_fiksna_dejanja(self):
        self.assertEqual(self.p.razcleni(["usmeri", "eth0", "5354"]), ("usmeri", ("eth0", 5354)))
        self.assertEqual(self.p.razcleni(["usmeri", "wlp2s0", "5357"]), ("usmeri", ("wlp2s0", 5357)))
        self.assertEqual(self.p.razcleni(["povrni", "enx00e04c680001"]), ("povrni", ("enx00e04c680001",)))
        self.assertEqual(self.p.razcleni(["domene", "eth0"]), ("domene", ("eth0",)))
        self.assertEqual(self.p.razcleni(["dovoli"]), ("dovoli", ()))

    def test_brez_roota_nic(self):
        with mock.patch.object(self.p.os, "geteuid", return_value=1000):
            self.assertEqual(self.p.main(["povrni", "eth0"]), 2)
        self.assertEqual(self.klici, [])

    def test_usmeri_samo_na_scit_in_streznike_networkmanagerja(self):
        self.assertEqual(self.p.usmeri("eth0", 5354), 0)
        nastavitve = [k for k in self.klici if k[0] == self.p.RESOLVECTL]
        self.assertEqual(nastavitve, [[self.p.RESOLVECTL, "dns", "eth0", "127.0.0.1:5354"],
                                      [self.p.RESOLVECTL, "dns", "eth0", "127.0.0.1:5354", "192.168.1.1", "fe80::1:2"]])

    def test_usmeri_zavrne_vrata_brez_scita_klicatelja(self):
        with mock.patch.object(self.p.os, "geteuid", return_value=0), \
                mock.patch.dict(self.p.os.environ, {"PKEXEC_UID": "1000"}), \
                mock.patch.object(self.p, "poslusa", return_value=False):
            self.assertEqual(self.p.main(["usmeri", "eth0", "5354"]), 3)
        self.assertEqual(self.klici, [])
        with mock.patch.object(self.p.os, "geteuid", return_value=0), \
                mock.patch.dict(self.p.os.environ, {"PKEXEC_UID": "abc"}):
            self.assertEqual(self.p.main(["usmeri", "eth0", "5354"]), 3)
        self.assertEqual(self.klici, [])

    def test_poslusa_bere_proc_net_udp(self):
        if not os.path.exists(self.p.PROC_UDP):
            self.skipTest("ni /proc/net/udp")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as u:
            u.bind(("127.0.0.1", 0))
            vrata = u.getsockname()[1]
            self.assertTrue(self.p.poslusa(vrata, os.getuid()))
            self.assertFalse(self.p.poslusa(vrata, os.getuid() + 1), "vticnica drugega uporabnika ne velja")
        self.assertFalse(self.p.poslusa(vrata, os.getuid()), "zaprta vticnica")

    def test_povrni_in_domene(self):
        self.assertEqual(self.p.povrni("eth0"), 0)
        nastavitve = [k for k in self.klici if k[0] == self.p.RESOLVECTL and len(k) > 3]
        self.assertEqual(nastavitve, [[self.p.RESOLVECTL, "dns", "eth0", "192.168.1.1", "fe80::1:2"],
                                      [self.p.RESOLVECTL, "domain", "eth0", "lan", "~."]],
                         "domena »-h« iz DHCP ni zastavica za resolvectl")

    def test_povrni_brez_streznikov_revert(self):
        self.p._zazeni = lambda u: (self.klici.append(list(u)) or (0, ""))
        self.assertEqual(self.p.povrni("eth0"), 0)
        self.assertIn([self.p.RESOLVECTL, "revert", "eth0"], self.klici)

    def test_dovoli_zapise_ozko_pravilo(self):
        pot = os.path.join(self.mapa.name, "rules.d", "49-safeer-os-scit.rules")
        os.makedirs(os.path.dirname(pot))
        with open(pot, "w", encoding="utf-8") as f:
            f.write(os_scit.PRAVILO)                       # staro pravilo se povozi
        self.assertEqual(self.p.dovoli(pot), 0)
        with open(pot, encoding="utf-8") as f:
            self.assertEqual(f.read(), self.p.PRAVILO)
        self.assertEqual(stat.S_IMODE(os.stat(pot).st_mode), 0o644)
        self.assertEqual(os.listdir(os.path.dirname(pot)), ["49-safeer-os-scit.rules"], "brez zacasnih datotek")
        self.assertEqual(self.p.PRAVILO_POT, os_scit.PRAVILO_POT, "isto ime: dovoli zamenja staro pravilo")


class PraviloInDejanje(unittest.TestCase):
    def test_pravilo_samo_za_nase_dejanje(self):
        pravilo = _pomocnik_modul().PRAVILO
        self.assertNotIn("resolve1", pravilo)
        self.assertNotIn("NetworkManager.", pravilo)
        self.assertEqual(re.findall(r'action\.id == "([^"]+)"', pravilo), ["si.safeer.os.scit"])
        for pogoj in ("subject.local", "subject.active", 'subject.isInGroup("sudo")'):
            self.assertIn(pogoj, pravilo)

    def test_policy(self):
        akcije = ET.parse(POLICY).getroot().findall("action")
        self.assertEqual([a.get("id") for a in akcije], [os_scit.AKCIJA_POMOCNIKA])
        a = akcije[0]
        self.assertEqual(a.find("annotate[@key='org.freedesktop.policykit.exec.path']").text, os_scit.POMOCNIK)
        privzeto = {e.tag: e.text for e in a.find("defaults")}
        self.assertEqual(privzeto, {"allow_any": "auth_admin", "allow_inactive": "auth_admin",
                                    "allow_active": "auth_admin_keep"})
        jeziki = {e.get("{http://www.w3.org/XML/1998/namespace}lang") for e in a.findall("description")}
        self.assertEqual(jeziki, {None, "sl", "de", "es", "fr", "it"})

    def test_deb_namesti_pomocnika_in_dejanje(self):
        besedilo = DEB.read_text(encoding="utf-8")
        self.assertIn('install -D -m 755 "$DIR/packaging/scit-dns" "$BUILD_ROOT%s"' % os_scit.POMOCNIK, besedilo)
        self.assertIn('"$DIR/packaging/si.safeer.os.scit.policy" "$BUILD_ROOT/usr/share/polkit-1/actions/'
                      'si.safeer.os.scit.policy"', besedilo)
        self.assertIn('"$BUILD_ROOT%s"' % os_scit.POMOCNIK, besedilo.split("find \"$BUILD_ROOT\" -type d")[-1],
                      "pomocnik je izvrsljiv po poenotenju pravic")


def _odsek(skripta: str, zacetek: str) -> str:
    """Nas odsek iz skripte vzdrzevalca v build_os_deb.sh (od komentarja do prvega »fi« na zacetku vrstice)."""
    besedilo = DEB.read_text(encoding="utf-8")
    telo = besedilo.split("cat << 'EOF2' > \"$BUILD_ROOT/DEBIAN/%s\"" % skripta, 1)[1].split("\nEOF2\n", 1)[0]
    odsek = telo[telo.index(zacetek):]
    return odsek[:odsek.index("\nfi\n") + 4]


@unittest.skipUnless(shutil.which("dash") or shutil.which("sh"), "ni lupine")
class SkripteVzdrzevalca(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        self.pravilo = os.path.join(self.d.name, "49-safeer-os-scit.rules")
        self.dnevnik = os.path.join(self.d.name, "dnevnik")
        self.lupina = shutil.which("dash") or shutil.which("sh")

    def _pomocnik(self, koda: int) -> str:
        pot = os.path.join(self.d.name, "scit-dns")
        with open(pot, "w", encoding="utf-8") as f:
            f.write("#!/bin/sh\necho \"$*\" >> %s\nexit %d\n" % (self.dnevnik, koda))
        os.chmod(pot, 0o755)
        return pot

    def _tek(self, skripta, zacetek, argument, koda_pomocnika=0):
        telo = _odsek(skripta, zacetek).replace("/etc/polkit-1/rules.d/49-safeer-os-scit.rules", self.pravilo)
        telo = telo.replace(os_scit.POMOCNIK, self._pomocnik(koda_pomocnika))
        r = subprocess.run([self.lupina, "-eu", "-c", telo, "skripta", argument], capture_output=True, text=True,
                           timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        try:
            with open(self.dnevnik, encoding="utf-8") as f:
                return f.read().split()
        except OSError:
            return []

    def _staro(self):
        with open(self.pravilo, "w", encoding="utf-8") as f:
            f.write(os_scit.PRAVILO)

    def test_postinst_zamenja_staro_pravilo(self):
        self._staro()
        self.assertEqual(self._tek("postinst", "# Scit (S15", "configure"), ["dovoli"])

    def test_postinst_odstrani_staro_ce_pomocnik_ne_uspe(self):
        self._staro()
        self._tek("postinst", "# Scit (S15", "configure", koda_pomocnika=1)
        self.assertFalse(os.path.exists(self.pravilo))

    def test_postinst_ne_tika_ozkega_ali_brez_pravila(self):
        self.assertEqual(self._tek("postinst", "# Scit (S15", "configure"), [])
        with open(self.pravilo, "w", encoding="utf-8") as f:
            f.write(_pomocnik_modul().PRAVILO)
        self.assertEqual(self._tek("postinst", "# Scit (S15", "configure"), [])
        self.assertTrue(os.path.exists(self.pravilo))

    def test_postrm_purge(self):
        self._staro()
        self._tek("postrm", "# Pravilo polkit Scita", "remove")
        self.assertTrue(os.path.exists(self.pravilo), "remove pusti nastavitev")
        self._tek("postrm", "# Pravilo polkit Scita", "purge")
        self.assertFalse(os.path.exists(self.pravilo))


class OsScitPrekPomocnika(unittest.TestCase):
    """Safeer OS v .deb ne klice resolvectl za nastavitve sam, ampak pkexec + pomocnik z absolutno potjo."""

    def setUp(self):
        self.klici = []
        zamenjave = {"pomocnik": lambda: True, "pot_pomocnika": lambda: os_scit.POMOCNIK, "_zazeni": self._lazno}
        self.stare = {k: getattr(os_scit, k) for k in zamenjave}
        for k, v in zamenjave.items():
            setattr(os_scit, k, v)
        self.addCleanup(lambda: [setattr(os_scit, k, v) for k, v in self.stare.items()])
        p = mock.patch.object(root_ukaz, "v_flatpaku", lambda: False)
        p.start()
        self.addCleanup(p.stop)
        w = mock.patch.object(os_scit.shutil, "which",
                              lambda ime, **k: ime if os.path.isabs(ime) else "/usr/bin/" + ime)
        w.start()
        self.addCleanup(w.stop)
        self.pkcheck = 1

    def _lazno(self, ukaz, cas=8.0):
        self.klici.append(list(ukaz))
        if ukaz[0] == "pkcheck":
            return self.pkcheck, ""
        if ukaz[:2] == ["resolvectl", "domain"]:
            return 0, "Link 2 (eth0):\n"
        return 0, ""

    def test_usmeri_povrni_domene(self):
        self.assertEqual(os_scit.usmeri("eth0", 5354, ["192.168.1.1"]), "")
        self.assertTrue(os_scit.povrni("eth0"))
        os_scit.uredi_domene("eth0")
        pk = "/usr/bin/pkexec"
        self.assertEqual([k for k in self.klici if k[0] != "resolvectl" or len(k) > 3],
                         [[pk, os_scit.POMOCNIK, "usmeri", "eth0", "5354"], [pk, os_scit.POMOCNIK, "povrni", "eth0"],
                          [pk, os_scit.POMOCNIK, "domene", "eth0"]])

    def test_dovoljenje_samo_za_nase_dejanje(self):
        self.pkcheck = 0
        self.assertTrue(os_scit.pravilo_namesceno())
        self.assertEqual(self.klici, [["pkcheck", "--action-id", "si.safeer.os.scit", "--process", str(os.getpid())]])

    def test_namesti_pravilo_pomocnik_brez_vhoda(self):
        with mock.patch.object(os_scit, "_zazeni_z_vhodom", side_effect=AssertionError("nic po vhodu")):
            self.assertTrue(os_scit.namesti_pravilo())
        self.assertEqual(self.klici[-1], ["/usr/bin/pkexec", os_scit.POMOCNIK, "dovoli"])


class IzbiraPoti(unittest.TestCase):
    def test_pomocnik_samo_rootov_in_ne_v_flatpaku(self):
        with tempfile.TemporaryDirectory() as d:
            pot = os.path.join(d, "scit-dns")
            with open(pot, "w", encoding="utf-8") as f:
                f.write("#!/bin/sh\n")
            os.chmod(pot, 0o755)
            with mock.patch.object(os_scit, "POMOCNIK", pot), mock.patch.object(os_scit, "v_flatpaku", lambda: False):
                # Datoteka uporabnika ni pomocnik; kot root tudi ne: zacasna mapa (/tmp) je zapisljiva za vse.
                self.assertFalse(os_scit.pomocnik(), "datoteka uporabnika ali mapa, zapisljiva za druge")
            with mock.patch.object(os_scit, "POMOCNIK", os.path.join(d, "ni")), \
                    mock.patch.object(os_scit, "v_flatpaku", lambda: False):
                self.assertFalse(os_scit.pomocnik())
        with mock.patch.object(os_scit, "v_flatpaku", lambda: True), \
                mock.patch.object(os_scit, "_pomocnik_gostitelja", lambda: False):
            self.assertFalse(os_scit.pomocnik(), "Flatpak brez pomocnika na gostitelju")
        with mock.patch.object(os_scit, "v_flatpaku", lambda: True), \
                mock.patch.object(os_scit, "_pomocnik_gostitelja", lambda: True):
            self.assertEqual(os_scit.pot_pomocnika(), os_scit.POMOCNIK_GOSTITELJA, "Flatpak: pomocnik na gostitelju")


class PomocnikGostitelja(unittest.TestCase):
    """Pregled 4. 11. 2026: Flatpak in AppImage sta namescala siroko pravilo za resolve1 (vsak program skrbnika sme
    poljuben DNS brez gesla). Zdaj gre isti pomocnik enkrat z geslom na gostitelja, root preveri SHA-256 kopije."""

    def setUp(self):
        os_scit._gostitelj_pomocnik = None
        self.addCleanup(setattr, os_scit, "_gostitelj_pomocnik", None)

    def test_vsota_pomocnika_je_vsota_datoteke(self):
        import hashlib
        self.assertEqual(os_scit.SHA_POMOCNIKA, hashlib.sha256(POMOCNIK_VIR.read_bytes()).hexdigest(),
                         "po spremembi packaging/scit-dns posodobi core/os_scit.SHA_POMOCNIKA")
        self.assertEqual(Path(os_scit.VIR_POMOCNIKA).resolve(), POMOCNIK_VIR.resolve())
        self.assertIn('install -m 644 "$ROOT/packaging/scit-dns" "$LIB/packaging/scit-dns"',
                      (KOREN / "packaging" / "install_os_payload.sh").read_text(encoding="utf-8"))

    def _namesti(self, flatpak):
        klici = []

        def z_vhodom(ukaz, vhod, cas=8.0):
            klici.append((list(ukaz), vhod))
            return 0, ""
        with mock.patch.object(os_scit, "v_flatpaku", lambda: flatpak), \
                mock.patch.object(root_ukaz, "v_flatpaku", lambda: flatpak), \
                mock.patch.object(root_ukaz, "na_voljo", lambda: True), \
                mock.patch.object(os_scit, "POMOCNIK", "/ni/te/poti/scit-dns"), \
                mock.patch.object(os_scit, "_zazeni", lambda ukaz, cas=8.0: (1, "")), \
                mock.patch.object(os_scit, "_zazeni_z_vhodom", z_vhodom):
            self.assertTrue(os_scit.namesti_pravilo())
        return klici

    def test_namestitev_na_gostitelja_po_vhodu_s_preverbo(self):
        for flatpak in (False, True):
            klici = self._namesti(flatpak)
            pkexec = "/app/host-bin/pkexec" if flatpak else "/usr/bin/pkexec"
            self.assertEqual(len(klici), 1)
            ukaz, vhod = klici[0]
            self.assertEqual(ukaz, [pkexec, "/bin/sh", "-c", os_scit.NAMESTI_POMOCNIKA_KOT_ROOT, "safeer-scit",
                                    os_scit.SHA_POMOCNIKA])
            self.assertEqual(vhod, POMOCNIK_VIR.read_text(encoding="utf-8"), "vsebina pomocnika po vhodu")
            self.assertNotIn("resolve1", vhod.split("PRAVILO_GOSTITELJA = ")[1].split('"""')[1])
            self.assertNotIn(os_scit.PRAVILO, vhod)
            self.assertNotIn(os_scit.PRAVILO, ukaz, "sirokega pravila ne namescamo vec")

    def test_pokvarjen_tovor_se_ne_namesti(self):
        with mock.patch.object(os_scit, "SHA_POMOCNIKA", "0" * 64), \
                mock.patch.object(os_scit, "POMOCNIK", "/ni/te/poti/scit-dns"), \
                mock.patch.object(os_scit, "v_flatpaku", lambda: False), \
                mock.patch.object(os_scit, "_zazeni_z_vhodom", side_effect=AssertionError("nic rootu")):
            self.assertFalse(os_scit.namesti_pravilo())

    def test_root_skripta_zavrne_napacno_vsoto(self):
        """Ob napacni vsoti root skripta konca (koda 3), preden kaj namesti. Tece kot uporabnik: nic ne zapise."""
        if os.getuid() == 0:
            self.skipTest("kot root bi skripta ob pravi vsoti namescala")
        r = subprocess.run(["/bin/sh", "-c", os_scit.NAMESTI_POMOCNIKA_KOT_ROOT, "safeer-scit", "0" * 64],
                           input=POMOCNIK_VIR.read_bytes(), capture_output=True, timeout=30)
        self.assertEqual(r.returncode, 3, r.stderr)

    def test_staro_siroko_pravilo_ne_velja(self):
        with tempfile.TemporaryDirectory() as d:
            pot = os.path.join(d, "49-safeer-os-scit.rules")
            with open(pot, "w", encoding="utf-8") as f:
                f.write(os_scit.PRAVILO)
            for flatpak in (False, True):
                with mock.patch.object(os_scit, "PRAVILO_POT", pot), \
                        mock.patch.object(os_scit, "v_flatpaku", lambda f=flatpak: f), \
                        mock.patch.object(os_scit, "POMOCNIK", "/ni/te/poti/scit-dns"), \
                        mock.patch.object(os_scit, "_pomocnik_gostitelja", lambda: False), \
                        mock.patch.object(os_scit, "_zazeni", side_effect=AssertionError("brez pkcheck")):
                    self.assertFalse(os_scit.pravilo_namesceno())

    def test_dovoljenje_za_pomocnika_gostitelja(self):
        klici = []

        def zazeni(ukaz, cas=8.0):
            klici.append(list(ukaz))
            return 0, ""
        with mock.patch.object(os_scit, "pot_pomocnika", lambda: os_scit.POMOCNIK_GOSTITELJA), \
                mock.patch.object(os_scit, "_zazeni", zazeni), \
                mock.patch.object(os_scit.shutil, "which", lambda ime, **k: "/usr/bin/" + ime):
            with mock.patch.object(os_scit, "v_flatpaku", lambda: False):
                self.assertTrue(os_scit.pravilo_namesceno())
            with mock.patch.object(os_scit, "v_flatpaku", lambda: True):
                self.assertTrue(os_scit.pravilo_namesceno())
        self.assertEqual(klici, [
            ["pkcheck", "--action-id", "org.freedesktop.policykit.exec", "--detail", "program",
             os_scit.POMOCNIK_GOSTITELJA, "--process", str(os.getpid())],
            ["flatpak-spawn", "--host", "/bin/sh", "-c",
             'exec pkcheck --action-id "$0" --detail program "$1" --process $$', "org.freedesktop.policykit.exec",
             os_scit.POMOCNIK_GOSTITELJA]])

    @staticmethod
    def _izpis_gostitelja(datoteka=(0, 0o100755), predniki=None, vsota=None):
        """Izpis _PREVERI_GOSTITELJA: »uid nacin(hex)« za program in vse prednike do /, nato sha256sum."""
        predniki = predniki or {}
        vrstice = ["%d %x" % datoteka]
        for p in os_scit._predniki(os_scit.POMOCNIK_GOSTITELJA):
            vrstice.append("%d %x" % predniki.get(p, (0, 0o40755)))
        vrstice.append("%s  %s" % (vsota or os_scit.SHA_POMOCNIKA, os_scit.POMOCNIK_GOSTITELJA))
        return "\n".join(vrstice) + "\n"

    def test_preverba_na_gostitelju_v_flatpaku(self):
        i = self._izpis_gostitelja
        primeri = (("ok", (0, i()), "ok"), ("star", (0, i(vsota="1" * 64)), "star"),
                   ("uporabnik", (0, i(datoteka=(1000, 0o100755))), "star"),
                   ("povezava", (0, i(datoteka=(0, 0o120777))), "star"),
                   ("mapa", (0, i(predniki={"/usr/local/lib/safeer-os": (0, 0o40777)})), "nevaren"),
                   # Pregled 4. 11. 2026 (NIZKA): predniki do / - prej se jih ni preverjalo.
                   ("prednik", (0, i(predniki={"/usr/local": (0, 0o42775)})), "nevaren"),
                   ("prednik_uporabnika", (0, i(predniki={"/usr": (1000, 0o40755)})), "nevaren"),
                   ("prednik_povezava", (0, i(predniki={"/usr/local/lib": (0, 0o120777)})), "nevaren"),
                   ("ni", (7, ""), "ni"))
        for primer, izid, pricakovano in primeri:
            os_scit._gostitelj_pomocnik = None
            klici = []
            with mock.patch.object(os_scit, "v_flatpaku", lambda: True), \
                    mock.patch.object(os_scit, "_zazeni", lambda ukaz, cas=8.0, z=izid: (klici.append(ukaz), z)[1]):
                self.assertEqual(os_scit._stanje_gostitelja(), pricakovano, primer)
                os_scit._gostitelj_pomocnik = None
                self.assertEqual(os_scit._pomocnik_gostitelja(), pricakovano == "ok", primer)
            self.assertEqual(klici[0][-6:], [os_scit.POMOCNIK_GOSTITELJA, "/usr/local/lib/safeer-os", "/usr/local/lib",
                                             "/usr/local", "/usr", "/"], "vsi predniki do /")

    def test_predniki_brez_flatpaka(self):
        """AppImage: isti pomocnik, preverba z lstat - mapa nad /usr/local/lib/safeer-os, zapisljiva za skupino, ne
        velja (pomocnika bi zamenjal njen clan); simbolni povezavi ne sledimo."""
        def lazni_lstat(nacini):
            def lstat(pot):
                if pot not in nacini:
                    raise FileNotFoundError(pot)
                return os.stat_result((nacini[pot], 0, 0, 1, 0, 0, 0, 0, 0, 0))
            return lstat
        vse = {p: 0o40755 for p in os_scit._predniki(os_scit.POMOCNIK_GOSTITELJA)}
        vse[os_scit.POMOCNIK_GOSTITELJA] = 0o100755
        with mock.patch.object(os_scit.os, "lstat", lazni_lstat(vse)), \
                mock.patch.object(os_scit.os, "access", lambda p, m: True):
            self.assertTrue(os_scit._rootova_pot(os_scit.POMOCNIK_GOSTITELJA))
        for pot, nacin in (("/usr/local", 0o42775), ("/usr", 0o40757), ("/usr/local/lib", 0o120777),
                           (os_scit.POMOCNIK_GOSTITELJA, 0o120777)):
            with mock.patch.object(os_scit.os, "lstat", lazni_lstat(dict(vse, **{pot: nacin}))), \
                    mock.patch.object(os_scit.os, "access", lambda p, m: True):
                self.assertFalse(os_scit._rootova_pot(os_scit.POMOCNIK_GOSTITELJA), pot)
                os_scit._gostitelj_pomocnik = None
                with mock.patch.object(os_scit, "v_flatpaku", lambda: False), \
                        mock.patch.object(os_scit.os.path, "lexists", lambda p: True):
                    self.assertIn(os_scit._stanje_gostitelja(), ("nevaren", "star"), pot)


class Shramba(dict):
    def get(self, k, d=None):
        return dict.get(self, k, d)

    def set(self, k, v):
        self[k] = v


class StaroSirokoPravilo(unittest.TestCase):
    """Neodvisni pregled 4. 11. 2026 (SREDNJA): Flatpak/AppImage z ze vklopljenim Scitom je obdrzal staro siroko
    pravilo (vsak program skrbnika sme brez gesla poljuben DNS), dokler uporabnik Scita ni vklopil znova - tiho."""

    def setUp(self):
        os_scit._gostitelj_pomocnik = os_scit._siroko = None
        self.addCleanup(setattr, os_scit, "_gostitelj_pomocnik", None)
        self.addCleanup(setattr, os_scit, "_siroko", None)

    def test_pkcheck_za_resolve1_samo_brez_pomocnika(self):
        klici = []

        def zazeni(ukaz, cas=8.0):
            klici.append(list(ukaz))
            return 0, ""
        with mock.patch.object(os_scit, "pot_pomocnika", lambda: None), \
                mock.patch.object(os_scit, "_zazeni", zazeni), \
                mock.patch.object(os_scit.shutil, "which", lambda ime, **k: "/usr/bin/" + ime):
            with mock.patch.object(os_scit, "v_flatpaku", lambda: False):
                self.assertTrue(os_scit.siroko_pravilo_velja())
            os_scit._siroko = None
            with mock.patch.object(os_scit, "v_flatpaku", lambda: True):
                self.assertTrue(os_scit.siroko_pravilo_velja())
        self.assertEqual(klici, [
            ["pkcheck", "--action-id", "org.freedesktop.resolve1.set-dns-servers", "--process", str(os.getpid())],
            ["flatpak-spawn", "--host", "/bin/sh", "-c", 'exec pkcheck --action-id "$0" --process $$',
             "org.freedesktop.resolve1.set-dns-servers"]])
        os_scit._siroko = None
        with mock.patch.object(os_scit, "pot_pomocnika", lambda: os_scit.POMOCNIK_GOSTITELJA), \
                mock.patch.object(os_scit, "_zazeni", side_effect=AssertionError("pomocnik je: brez pkcheck")):
            self.assertFalse(os_scit.siroko_pravilo_velja())
        os_scit._siroko = None
        with mock.patch.object(os_scit, "pot_pomocnika", lambda: None), \
                mock.patch.object(os_scit, "v_flatpaku", lambda: True), \
                mock.patch.object(os_scit, "_zazeni", lambda ukaz, cas=8.0: (1, "")):
            self.assertFalse(os_scit.siroko_pravilo_velja(), "pkcheck zahteva geslo: sirokega pravila ni")

    def _scit(self, d):
        return os_scit.Scit(Shramba(scit=True), mapa=d)

    def test_ponudba_enkrat_opozorilo_ostane(self):
        namestitve = []
        stanje = {"siroko": True}

        def namesti():
            namestitve.append(1)
            stanje["siroko"] = False
            return True
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(os_scit, "siroko_pravilo_velja", lambda: stanje["siroko"]), \
                mock.patch.object(os_scit, "pot_pomocnika", lambda: None), \
                mock.patch.object(os_scit, "_stanje_gostitelja", lambda: "ni"), \
                mock.patch.object(os_scit, "razlog_nemoznosti", lambda: ""), \
                mock.patch.object(os_scit, "pravilo_namesceno", lambda: False), \
                mock.patch.object(os_scit, "namesti_pravilo", namesti):
            sc = self._scit(d)
            sc.napaka = "pravilo"
            st = sc.stanje()
            self.assertEqual((st["dovoljenje"], st["dovoljenjePonudi"], st["napaka"]), ("siroko", True, "siroko"))
            self.assertEqual(sc.stanje_pulta(preveri=False)["napaka"], "siroko", "pult ne sme biti miren")
            from core import pladenj_sni
            self.assertEqual(pladenj_sni.vrsta_scita(sc.stanje_pulta(preveri=False)), "napaka")
            # »Ne zdaj«: ponudba se ne ponovi, opozorilo ostane; nic ne namesti.
            st = sc.posodobi_dovoljenje(False)
            self.assertEqual((st["dovoljenje"], st["dovoljenjePonudi"], st["napaka"]), ("siroko", False, "siroko"))
            self.assertEqual(namestitve, [])
            # Gumb v oknu Scita: namesti pomocnika (ta odstrani staro pravilo), Scit se zazene.
            with mock.patch.object(sc, "_zazeni", lambda: True) as _:
                st = sc.posodobi_dovoljenje(True)
            self.assertEqual(namestitve, [1])
            self.assertEqual((st["dovoljenje"], st["dovoljenjePonudi"]), ("", False))
            self.assertNotEqual(st["napaka"], "siroko")

    def test_zavrnjeno_geslo_ostane_opozorilo(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(os_scit, "siroko_pravilo_velja", lambda: True), \
                mock.patch.object(os_scit, "pot_pomocnika", lambda: None), \
                mock.patch.object(os_scit, "razlog_nemoznosti", lambda: ""), \
                mock.patch.object(os_scit, "pravilo_namesceno", lambda: False), \
                mock.patch.object(os_scit, "namesti_pravilo", lambda: False):
            sc = self._scit(d)
            st = sc.posodobi_dovoljenje(True)
            self.assertEqual((st["dovoljenje"], st["napaka"]), ("siroko", "siroko"))

    def test_star_pomocnik_ponudi_posodobitev_ne_napake_pravilo(self):
        """Pregled 4. 11. 2026 (NIZKA): pomocnik na gostitelju se ni posodabljal - ob drugi SHA_POMOCNIKA je Scit
        javil »pravilo«. Zdaj ponudi posodobitev pomocnika; namestitev starega zamenja (mv -f)."""
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(os_scit, "siroko_pravilo_velja", lambda: False), \
                mock.patch.object(os_scit, "pot_pomocnika", lambda: None), \
                mock.patch.object(os_scit, "_stanje_gostitelja", lambda: "star"), \
                mock.patch.object(os_scit, "razlog_nemoznosti", lambda: ""), \
                mock.patch.object(os_scit, "pravilo_namesceno", lambda: False):
            sc = self._scit(d)
            sc.napaka = "pravilo"
            st = sc.stanje()
            self.assertEqual((st["dovoljenje"], st["dovoljenjePonudi"], st["napaka"]),
                             ("pomocnik", True, "pomocnik_star"))
        self.assertIn('mv -f "$cilj/.scit-dns.novo" "$cilj/scit-dns"', os_scit.NAMESTI_POMOCNIKA_KOT_ROOT)

    def test_proces_scit_pozna_nove_metode(self):
        from core import scit_odjemalec, scit_proces
        for m in ("popravi", "posodobi_dovoljenje"):
            self.assertIn(m, scit_proces.METODE)
            self.assertTrue(callable(getattr(scit_odjemalec.ScitOdjemalec, m, None)), m)
        os_vir = (KOREN / "safeer_os.py").read_text(encoding="utf-8")
        self.assertIn('"scitDovoljenje": lambda: self._po_scitu(self.scit.posodobi_dovoljenje(', os_vir)
        js = (KOREN / "assets" / "os" / "os.js").read_text(encoding="utf-8")
        self.assertIn('klic("scitDovoljenje"', js)
        besedila = (KOREN / "assets" / "os" / "besedila.js").read_text(encoding="utf-8")
        for k in ("scitNapaka_siroko", "scitNapaka_pomocnik_star", "scitDovoljenjePosodobi", "scitDovoljenjeNeZdaj"):
            self.assertEqual(besedila.count(k + ":"), 6, k)


class PomocnikNaGostiteljuPravilo(unittest.TestCase):
    def setUp(self):
        self.p = _pomocnik_modul()
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)

    def test_pravilo_gostitelja_samo_za_ta_program(self):
        pravilo = self.p.PRAVILO_GOSTITELJA
        self.assertNotIn("resolve1", pravilo)
        self.assertEqual(re.findall(r'action\.id == "([^"]+)"', pravilo), ["org.freedesktop.policykit.exec"])
        self.assertEqual(re.findall(r'action\.lookup\("program"\) == "([^"]+)"', pravilo), [os_scit.POMOCNIK_GOSTITELJA])
        for pogoj in ("subject.local", "subject.active", 'subject.isInGroup("sudo")'):
            self.assertIn(pogoj, pravilo)
        self.assertEqual(self.p.POT_GOSTITELJA, os_scit.POMOCNIK_GOSTITELJA)

    def test_dovoli_na_gostitelju_zamenja_siroko(self):
        rules = os.path.join(self.mapa.name, "rules.d")
        os.makedirs(rules)
        staro = os.path.join(rules, "49-safeer-os-scit.rules")
        with open(staro, "w", encoding="utf-8") as f:
            f.write(os_scit.PRAVILO)
        self.p.JAZ = self.p.POT_GOSTITELJA
        self.p.PRAVILO_GOSTITELJA_POT = os.path.join(rules, "49-safeer-os-scit-gostitelj.rules")
        with mock.patch.object(self.p, "PRAVILO_POT", staro):
            self.assertEqual(self.p.dovoli(), 0)
        self.assertEqual(os.listdir(rules), ["49-safeer-os-scit-gostitelj.rules"], "siroko pravilo odstranjeno")
        with open(self.p.PRAVILO_GOSTITELJA_POT, encoding="utf-8") as f:
            self.assertEqual(f.read(), self.p.PRAVILO_GOSTITELJA)

    def test_dovoli_ne_odstrani_ozkega_pravila_paketa(self):
        pot = os.path.join(self.mapa.name, "49-safeer-os-scit.rules")
        with open(pot, "w", encoding="utf-8") as f:
            f.write(self.p.PRAVILO)
        self.p.odstrani_siroko(pot)
        self.assertTrue(os.path.exists(pot))

    def test_usmeri_brez_rezerve_koda_4(self):
        mapa = tempfile.mkdtemp(dir=self.mapa.name)
        os.mkdir(os.path.join(mapa, "eth0"))
        self.p.SISTEM_NET = mapa

        def lazno(ukaz):
            if ukaz[:2] == [self.p.NMCLI, "-g"]:
                return 0, "192.168.1.1\n"
            if ukaz[0] == self.p.RESOLVECTL and len(ukaz) > 4:
                return 1, ""                       # drugi korak (Scit + rezerva) pade
            return 0, ""
        self.p._zazeni = lazno
        self.assertEqual(self.p.usmeri("eth0", 5354), 4)


if __name__ == "__main__":
    unittest.main()
