"""Popravki po tretjem neodvisnem pregledu izdaje 1.0.128 (19. 10. 2026) in okolje procesa med tekom.

- safeer-cinnamon: dock najde tudi programe Flatpak, namescene samo za uporabnika (~/.local/share/flatpak/exports);
  pgrep/pkill Planka in delovne povrsine samo za procese tega uporabnika.
- Prazen XDG_CONFIG_HOME / XDG_CACHE_HOME / XDG_DATA_HOME / XDG_RUNTIME_DIR velja kot nenastavljen (specifikacija XDG):
  prej je dal relativno pot - nastavitve bi sle v trenutno mapo.
- Okolja procesa ne spreminjamo, ko v njem ze tecejo niti (setenv med getenv druge niti je v glibc nedefiniran):
  vgradnja Controla v Safeer OS (zastavica v core/en_proces), ponovni zagon Controla (execve z lastnim okoljem).
Vsak preizkus brez svojega popravka pade.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKRIPTA = os.path.join(KOREN, "packaging", "tema-cinnamon", "safeer-cinnamon")
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)


class DockFlatpakUporabnika(unittest.TestCase):
    def _najdi(self, dom: str, koren: str, ime: str) -> subprocess.CompletedProcess:
        with open(SKRIPTA, encoding="utf-8") as f:
            funkcija = re.search(r"^najdi_program\(\) \{.*?^\}", f.read(), re.S | re.M).group(0)
        okolje = {k: v for k, v in os.environ.items() if k != "XDG_DATA_HOME"}
        okolje.update(HOME=dom, KOREN=koren)
        return subprocess.run(["bash", "-c", funkcija + '\nnajdi_program "$1"', "bash", ime], env=okolje,
                              capture_output=True, text=True, timeout=10)

    def test_program_flatpak_uporabnika(self):
        tmp = tempfile.mkdtemp()
        try:
            mapa = os.path.join(tmp, "dom", ".local", "share", "flatpak", "exports", "share", "applications")
            os.makedirs(mapa)
            pot = os.path.join(mapa, "org.gimp.GIMP.desktop")
            open(pot, "w").close()
            izid = self._najdi(os.path.join(tmp, "dom"), os.path.join(tmp, "koren"), "org.gimp.GIMP")
            self.assertEqual((izid.returncode, izid.stdout.strip()), (0, pot), izid.stderr)
            self.assertEqual(self._najdi(os.path.join(tmp, "dom"), os.path.join(tmp, "koren"), "ni.Ga").returncode, 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_procesi_samo_tega_uporabnika(self):
        """Ob vec prijavljenih uporabnikih se tuj Plank ne steje za nasega in se ga ne poskusa ustaviti."""
        with open(SKRIPTA, encoding="utf-8") as f:
            vrstice = [v.strip() for v in f if re.search(r"\b(pgrep|pkill)\b", v) and not v.lstrip().startswith("#")]
        self.assertTrue(vrstice)
        for v in vrstice:
            self.assertIn('-u "$(id -u)"', v, v)


class PraznaSpremenljivkaXdg(unittest.TestCase):
    def test_prazna_je_kot_nenastavljena(self):
        from core import os_jbl, predvajalnik_moznosti, zvok_na_zvocnik
        prazno = {"XDG_CONFIG_HOME": "", "XDG_CACHE_HOME": "", "XDG_DATA_HOME": ""}
        with mock.patch.dict(os.environ, prazno):
            for pot in (os_jbl.mapa(), predvajalnik_moznosti._pot(), zvok_na_zvocnik._pot_zakasnitev()):
                self.assertTrue(os.path.isabs(pot), pot)
                self.assertTrue(pot.startswith(os.path.expanduser("~/.config")), pot)

    def test_nikjer_oblika_s_privzeto_vrednostjo(self):
        """os.environ.get("XDG_..._HOME", privzeto) vrne "" za prazno spremenljivko; prav je `get(...) or privzeto`."""
        vzorec = re.compile(r"""(environ\.get|getenv)\(\s*['"]XDG_\w+_(HOME|DIR)['"]\s*,""")
        najdeno = []
        poti = [os.path.join(KOREN, ime) for ime in os.listdir(KOREN) if ime.endswith(".py")]
        for koren, _mape, datoteke in os.walk(os.path.join(KOREN, "core")):
            poti += [os.path.join(koren, d) for d in datoteke if d.endswith(".py")]
        for pot in poti:
            with open(pot, encoding="utf-8") as f:
                for st, vrstica in enumerate(f, 1):
                    if vzorec.search(vrstica):
                        najdeno.append("%s:%d" % (os.path.relpath(pot, KOREN), st))
        self.assertEqual(najdeno, [])


class OkoljeProcesaMedTekom(unittest.TestCase):
    def test_vgradnja_controla_brez_okoljske_spremenljivke(self):
        from core import en_proces
        with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
            izvor = f.read()
        self.assertNotIn('os.environ["SAFEER_CONTROL_VGRAJEN"]', izvor)
        self.assertIn("en_proces.vgradi_control()", izvor)
        with mock.patch.object(en_proces, "_control_bo_vgrajen", False):
            self.assertFalse(en_proces.control_bo_vgrajen())
            en_proces.vgradi_control()
            self.assertTrue(en_proces.control_bo_vgrajen())

    def test_ponovni_zagon_controla_ne_spremeni_okolja(self):
        import safeer_control
        lazna = mock.MagicMock()
        prej = dict(os.environ)
        with mock.patch.object(safeer_control, "VGRAJEN", False), \
                mock.patch.object(safeer_control.os, "execve") as execve, \
                mock.patch.object(safeer_control.os, "execv") as execv:
            safeer_control.SafeerControl._znova_zazeni(lazna)
        self.assertEqual(dict(os.environ), prej)
        execv.assert_not_called()
        program, argv, okolje = execve.call_args[0]
        self.assertEqual(okolje.get("SAFEER_CONTROL_ODPRI"), "1")
        self.assertIn("--ozadje", argv)


class SpremenljivkeQt(unittest.TestCase):
    """Lupina Qt v procesu Safeer OS (okno aplikacije) nastane, ko niti ze tecejo: okolje samo zamenja vrednosti."""

    def test_rezervacije_pred_nitmi_in_brez_njih_za_programe(self):
        from core import okolje_procesa, zasebni_webkit
        brez = {k: v for k, v in os.environ.items() if k not in okolje_procesa.QT}
        with mock.patch.dict(os.environ, brez, clear=True):
            okolje_procesa.pred_nitmi()
            for ime in okolje_procesa.QT:
                self.assertEqual(os.environ[ime], "")
            otrok = zasebni_webkit.okolje_za_zunanje()
            self.assertFalse(set(okolje_procesa.QT) & set(otrok), "prazne rezervacije ne gredo programom")
        with mock.patch.dict(os.environ, {"QT_QPA_PLATFORM": "wayland"}):
            okolje_procesa.pred_nitmi()
            self.assertEqual(os.environ["QT_QPA_PLATFORM"], "wayland", "uporabnikova vrednost ostane")
            self.assertEqual(zasebni_webkit.okolje_za_zunanje()["QT_QPA_PLATFORM"], "wayland")

    def test_safeer_os_rezervira_pred_gtk(self):
        with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
            izvor = f.read()
        self.assertLess(izvor.index("\nokolje_procesa.pred_nitmi()"), izvor.index("\nimport gi"))

    def test_pripravi_samo_zamenja(self):
        """os_lupina.pripravi (pozno, EGL): po rezervacijah se v okolju ne doda in ne izbrise nobena spremenljivka."""
        from core import okolje_procesa, os_lupina
        okolje = {"XDG_CURRENT_DESKTOP": "X-Cinnamon", "DESKTOP_SESSION": "cinnamon", "QT_QPA_PLATFORMTHEME": ""}
        with mock.patch.dict(os.environ, okolje):
            okolje_procesa.pred_nitmi()
            kljuci, opazeno = set(os.environ), []
            pravi = os.environ.__class__.__setitem__

            class LazniQApplication:
                def __init__(self, _argv):
                    opazeno.append(set(os.environ) == kljuci)
                    opazeno.append((os.environ["XDG_CURRENT_DESKTOP"], os.environ["QT_XCB_GL_INTEGRATION"]))

                @staticmethod
                def instance():
                    return None

                def __getattr__(self, _ime):
                    return lambda *a, **k: None
            with mock.patch.object(os_lupina, "_qt_app", None), mock.patch.object(os_lupina, "zelena", return_value=True), \
                    mock.patch.dict(sys.modules, _lazni_pyside(LazniQApplication)):
                self.assertTrue(os_lupina.pripravi(["safeer-os"], pozno=True))
            self.assertEqual(opazeno, [True, ("", "xcb_egl")])
            self.assertEqual(set(os.environ), kljuci)
            self.assertEqual((os.environ["XDG_CURRENT_DESKTOP"], os.environ["QT_XCB_GL_INTEGRATION"]), ("X-Cinnamon", ""))
            del pravi


class DomacaStranSpleta(unittest.TestCase):
    """Most »safeer« (Splet v Safeer OS in Safeer Browser) zaupa samo nasi zacetni strani file://<koren>/ui/splet.html."""

    def test_tuj_streznik_z_isto_potjo_ni_domaca_stran(self):
        from core.os_splet import je_domaca_stran
        koren = "/usr/lib/safeer-os"
        for tuj in ("https://napadalec.example/usr/lib/safeer-os/ui/splet.html",
                    "http://napadalec.example/usr/lib/safeer-os/ui/splet.html?x#y",
                    "file://napadalec.example/usr/lib/safeer-os/ui/splet.html",
                    "safeer-x:///usr/lib/safeer-os/ui/splet.html", "/usr/lib/safeer-os/ui/splet.html",
                    "file:///usr/lib/safeer-os/ui/druga.html"):
            self.assertFalse(je_domaca_stran(tuj, koren), tuj)
        for nasa in ("file:///usr/lib/safeer-os/ui/splet.html", "file:///usr/lib/safeer-os/ui/splet.html?jezik=sl",
                     "FILE://localhost/usr/lib/safeer-os/ui/splet.html"):
            self.assertTrue(je_domaca_stran(nasa, koren), nasa)


class PoverilniceMedijskihStreznikov(unittest.TestCase):
    """Jellyfin/Emby/Plex/Kodi: zeton ali geslo ne gre za preusmeritvijo na drug streznik (pregled 19. 10. 2026)."""

    def test_preusmeritev_na_drug_streznik_brez_poverilnic(self):
        import http.server
        import threading
        from core import media_servers
        prejeto = []

        class Cilj(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                prejeto.append({k.lower(): v for k, v in self.headers.items()})
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")
        cilj = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Cilj)

        class Izvor(Cilj):
            def do_GET(self):
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1:%d/prijava" % cilj.server_address[1])
                self.send_header("Content-Length", "0")
                self.end_headers()
        izvor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Izvor)
        for s in (cilj, izvor):
            threading.Thread(target=s.serve_forever, daemon=True).start()
        try:
            media_servers._request("http://127.0.0.1:%d/Users" % izvor.server_address[1],
                                   headers={"Authorization": "MediaBrowser Token=\"SKRIVNO\"", "X-Emby-Token": "SKRIVNO"})
        finally:
            cilj.shutdown()
            izvor.shutdown()
        self.assertEqual(len(prejeto), 1)
        self.assertNotIn("authorization", prejeto[0])
        self.assertNotIn("x-emby-token", prejeto[0])

    def test_https_na_http_zavrnjeno(self):
        import urllib.request
        from core import media_servers
        z = urllib.request.Request("https://jf.example/Users", headers={"Authorization": "x"})
        with self.assertRaises(ValueError):
            media_servers._HTTPSOnlyRedirect().redirect_request(z, None, 302, "Found", {}, "http://192.168.1.5/Users")
        nova = media_servers._HTTPSOnlyRedirect().redirect_request(z, None, 302, "Found", {}, "https://jf.example/web/")
        self.assertEqual(nova.headers.get("Authorization"), "x", "isti streznik obdrzi prijavo")


class ShranjenNaslovAgenta(unittest.TestCase):
    def test_star_http_naslov_pokaze_razlog(self):
        from core.agent import nastavitve
        mapa = tempfile.mkdtemp()
        try:
            with mock.patch.object(nastavitve, "MAPA", mapa):
                nastavitve._pisi("naslov", "http://moj-streznik.example:8080")
                st = nastavitve.stanje()
            self.assertEqual((st["naslov"], st["neveljaven_naslov"], st["napaka_naslova"]),
                             ("", "http://moj-streznik.example:8080", "http"))
        finally:
            shutil.rmtree(mapa, ignore_errors=True)

    def test_ipv4_v_ipv6_ni_domace_omrezje(self):
        from core.agent import nastavitve
        from core import media_servers, os_vgrajeni_viri
        self.assertFalse(nastavitve.domace_omrezje("::ffff:8.8.8.8"))
        self.assertFalse(os_vgrajeni_viri.je_zasebni_gostitelj("::ffff:8.8.8.8"))
        self.assertFalse(media_servers.je_domace_omrezje("::ffff:8.8.8.8"))
        self.assertTrue(nastavitve.domace_omrezje("::ffff:192.168.1.5"))


class RootZAbsolutnimiPotmi(unittest.TestCase):
    """pkexec poisce program po PATH klicatelja (~/.local/bin pred /usr/bin): kot root samo absolutne poti."""

    def test_ukaz_zavrne_relativen_program(self):
        from core import root_ukaz
        with self.assertRaises(ValueError):
            root_ukaz.ukaz("install", "x")
        with mock.patch.object(root_ukaz, "v_flatpaku", lambda: False):
            self.assertEqual(root_ukaz.ukaz(root_ukaz.INSTALL, "x"), ["/usr/bin/pkexec", "/usr/bin/install", "x"])
        with mock.patch.object(root_ukaz, "v_flatpaku", lambda: True):
            self.assertEqual(root_ukaz.ukaz(root_ukaz.SH)[0], "/app/host-bin/pkexec")

    def test_nikjer_pkexec_po_imenu(self):
        vzorec = re.compile(r"""\[\s*["']pkexec["']\s*,\s*["'](?!/)""")
        najdeno = []
        poti = [os.path.join(KOREN, ime) for ime in os.listdir(KOREN) if ime.endswith(".py")]
        for koren, _mape, datoteke in os.walk(os.path.join(KOREN, "core")):
            poti += [os.path.join(koren, d) for d in datoteke if d.endswith(".py")]
        for pot in poti:
            with open(pot, encoding="utf-8") as f:
                for st, vrstica in enumerate(f, 1):
                    if vzorec.search(vrstica):
                        najdeno.append("%s:%d" % (os.path.relpath(pot, KOREN), st))
        self.assertEqual(najdeno, [])
        with open(SKRIPTA, encoding="utf-8") as f:
            besedilo = f.read()
        self.assertNotRegex(besedilo, r'(?<![/\w])pkexec "\$POMOCNIK"')

    def test_ovoj_flatpak_klice_absolutni_pkexec(self):
        mapa = tempfile.mkdtemp()
        try:
            subprocess.run(["bash", os.path.join(KOREN, "packaging", "flatpak_host_wrappers.sh"), mapa], check=True,
                           capture_output=True, timeout=30)
            with open(os.path.join(mapa, "pkexec"), encoding="utf-8") as f:
                self.assertIn('/usr/bin/pkexec "$@"', f.read())
        finally:
            shutil.rmtree(mapa, ignore_errors=True)


class NastavitveLinka(unittest.TestCase):
    def test_datoteka_z_zetoni_nikoli_berljiva_drugim(self):
        from core import link_hub
        mapa = tempfile.mkdtemp()
        stara = os.umask(0o022)
        try:
            pot = os.path.join(mapa, "safeer-control", "link.json")
            n = link_hub.Nastavitve(pot)
            vidno = []
            pravi_dump = link_hub.json.dump

            def dump(podatki, d, **k):
                vidno.append(os.stat(pot + ".tmp").st_mode & 0o777)     # pravice med zapisom zetona
                return pravi_dump(podatki, d, **k)
            n.podatki = {"control_token": "skrivno"}
            with mock.patch.object(link_hub.json, "dump", dump):
                n.shrani()
            self.assertEqual(vidno, [0o600])
            self.assertEqual(os.stat(pot).st_mode & 0o777, 0o600)
            self.assertEqual(os.stat(os.path.dirname(pot)).st_mode & 0o777, 0o700)
            with mock.patch.object(link_hub.json, "dump", side_effect=OSError("disk")):
                n.shrani()
            self.assertFalse(os.path.exists(pot + ".tmp"), "ob napaki zacasna datoteka z zetonom ne ostane")
        finally:
            os.umask(stara)
            shutil.rmtree(mapa, ignore_errors=True)


class PrijavaSPodpisom(unittest.TestCase):
    def test_samo_tls_s_pripetim_odtisom(self):
        from core import link_hub
        with mock.patch.object(link_hub, "_zahteva", side_effect=AssertionError("ne sme poslati")):
            self.assertEqual(link_hub.vzemi_vstopnico_s_podpisom("ws://192.168.1.5:8443", "n-1", "ab" * 32), (None, 0))
            self.assertEqual(link_hub.vzemi_vstopnico_s_podpisom("wss://192.168.1.5:8443", "n-1", ""), (None, 0))
            self.assertIsNone(link_hub.seja_s_podpisom("ws://192.168.1.5:8443", "n-1", "ab" * 32))

    def test_podpise_pripeti_odtis_ne_tistega_s_streznika(self):
        from core import link_hub
        odgovori = [(200, {"nonce": "n1", "fp": "cd" * 32})]
        with mock.patch.object(link_hub, "_zahteva", side_effect=lambda *a, **k: odgovori.pop(0)), \
                mock.patch.object(link_hub.link_krog, "podpisi", return_value="podpis") as podpisi:
            self.assertIsNone(link_hub.vzemi_vstopnico_s_podpisom("wss://192.168.1.5:8443", "n-1", "ab" * 32)[0])
        podpisi.assert_not_called()       # odtis s streznika se ne ujema s pripetim: nic se ne podpise


class PrenosiIzvrsljivih(unittest.TestCase):
    def test_samo_https_tudi_ob_preusmeritvi(self):
        import urllib.error
        import urllib.request
        from core import https_prenos
        with self.assertRaises(ValueError):
            https_prenos.odpri("http://github.com/x")
        z = urllib.request.Request("https://github.com/o/r/releases/download/v1/rqbit")
        with self.assertRaises(urllib.error.HTTPError):
            https_prenos.SamoHttps().redirect_request(z, None, 302, "Found", {}, "http://10.0.0.1/rqbit")
        self.assertIsNotNone(https_prenos.SamoHttps().redirect_request(z, None, 302, "Found", {},
                                                                       "https://objects.githubusercontent.com/x"))

    def test_privzeti_prenosi_uporabljajo_https_prenos(self):
        import inspect
        from core import https_prenos, os_jbl, os_torrent
        self.assertIs(inspect.signature(os_jbl.prenesi_potrdilo).parameters["odpri"].default, https_prenos.odpri)
        self.assertIs(inspect.signature(os_torrent.prenesi_program).parameters["odpri"].default, https_prenos.odpri)
        with open(os.path.join(KOREN, "core", "os_govor.py"), encoding="utf-8") as f:
            self.assertIn("https_prenos.odpri(url", f.read())


class ProcesiInLupina(unittest.TestCase):
    def test_sway_exec_brez_deljenja_ob_vejici(self):
        """Ime datoteke z vejico ali podpicjem ne sme postati ukaz za sway; v lupini sh mora ostati en argument."""
        from core import link_sway
        argv = ["mpv", "/tmp/film.mkv,exit", "a;reload", "it's"]
        vrstica = link_sway._za_sway(argv)
        brez_narekovajev = re.sub(r"'[^']*'", "", vrstica)
        self.assertNotRegex(brez_narekovajev, "[,;]", "vejica ali podpicje zunaj narekovajev")
        izid = subprocess.run(["sh", "-c", "for a in " + vrstica + "; do printf '%s\\n' \"$a\"; done"],
                              capture_output=True, text=True, timeout=10)
        self.assertEqual(izid.stdout.splitlines(), argv)

    def test_spremenljivke_zagona_prevzete_pred_nitmi(self):
        from core import okolje_procesa
        with mock.patch.dict(os.environ, {"NOTIFY_SOCKET": "/run/x.sock", "SAFEER_OBNOVA": "1"}), \
                mock.patch.object(okolje_procesa, "_prevzeto", {}):
            okolje_procesa.pred_nitmi()
            self.assertNotIn("NOTIFY_SOCKET", os.environ)
            kljuci = set(os.environ)
            self.assertEqual(okolje_procesa.prevzemi("NOTIFY_SOCKET"), "/run/x.sock")
            self.assertEqual(okolje_procesa.prevzemi("SAFEER_OBNOVA"), "1")
            self.assertEqual(okolje_procesa.prevzemi("SAFEER_LUPINA_VTIC"), "")
            self.assertEqual(set(os.environ), kljuci, "po pred_nitmi() se okolje ne spreminja")

    def test_varni_nacin_brez_okoljske_spremenljivke(self):
        from core import os_okna
        with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
            self.assertNotIn("os.environ[os_okna.IZKLOP]", f.read())
        with mock.patch.object(os_okna, "_izklopljeno", False):
            self.assertFalse(os_okna.izklopljen() and not os.environ.get(os_okna.IZKLOP))
            os_okna.izklopi()
            self.assertTrue(os_okna.izklopljen())
            self.assertIsNone(os_okna._pridobi())

    def test_skripte_paketa(self):
        """prerm: uporabnikova koda brez rootovega terminala; odstranitev: samo lastni procesi; zaganjalnika: pot ni
        vstavljena v kodo Pythona; uinput: samo aktivna seja (uaccess), ne skupina input."""
        def beri(*pot):
            with open(os.path.join(KOREN, *pot), encoding="utf-8") as f:
                return f.read()
        prerm = beri("build_os_deb.sh")
        self.assertEqual(prerm.count("timeout 60 runuser"), 0)
        self.assertEqual(prerm.count("timeout 60 setsid runuser"), 2)
        self.assertNotRegex(beri("uninstall.sh"), r"pkill -f safeer")
        for zaganjalnik in ("safeer-os-launcher", "safeer-control-launcher"):
            self.assertNotIn("'$APP_DIR'", beri("packaging", zaganjalnik), zaganjalnik)
        self.assertFalse(os.path.exists(os.path.join(KOREN, "packaging", "99-safeer-uinput.rules")))
        pravilo = [v for v in beri("packaging", "60-safeer-uinput.rules").splitlines() if v and not v.startswith("#")]
        self.assertEqual(len(pravilo), 1)
        self.assertIn('TAG+="uaccess"', pravilo[0])
        self.assertNotIn("GROUP", pravilo[0])

    def test_vticnica_lupine_brez_umask(self):
        with open(os.path.join(KOREN, "core", "lupina_streznik.py"), encoding="utf-8") as f:
            self.assertNotIn("os.umask(", f.read())


def _lazni_pyside(qapp):
    """Najmanjsi PySide6 za os_lupina.pripravi (brez Qt): QCoreApplication, QGuiApplication, Qt, QApplication."""
    import types
    qtcore, qtgui, qtwidgets, paket = (types.ModuleType(i) for i in
                                       ("PySide6.QtCore", "PySide6.QtGui", "PySide6.QtWidgets", "PySide6"))

    class _Atr:
        def __getattr__(self, _ime):
            return self
    qtcore.QCoreApplication = types.SimpleNamespace(setAttribute=lambda *a: None)
    qtcore.Qt = _Atr()
    qtgui.QGuiApplication = types.SimpleNamespace(setHighDpiScaleFactorRoundingPolicy=lambda *a: None)
    qtwidgets.QApplication = qapp
    return {"PySide6": paket, "PySide6.QtCore": qtcore, "PySide6.QtGui": qtgui, "PySide6.QtWidgets": qtwidgets}


if __name__ == "__main__":
    unittest.main()
