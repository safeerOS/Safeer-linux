"""Lupina namizja v svojem procesu (lastnik, 18. 10. 2026, moznost B): most prek vticnice, streznik v Safeer OS, odjemalec
v lupini in zivi poskusi odpornosti (sesutje Safeer OS -> namizje ostane; sesutje lupine -> Safeer OS tece naprej).

core/lupina_most.py (okvirji), core/lupina_streznik.py (Safeer OS, GLib), core/lupina_proces.py (lupina, Qt),
core/varuh_procesov.py (varuh). Pravila varuha z laznimi otroki so v tests/test_varuh_procesov.py."""
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import lupina_most as lm  # noqa: E402


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class Okvirji(unittest.TestCase):
    def test_vse_vrste_naprej_in_nazaj(self):
        tok = (lm.klic(7, "zacetek", [1, "č"]) + lm.zdravo({"razmerje": 1.25}) + lm.ping(3) + lm.pong(3)
               + lm.odgovor(-5, True, '{"a": "š"}') + lm.dogodek("videz", "[1]") + lm.ukaz({"u": "aktiviraj"}))
        d = lm.Dekoder()
        okvirji = []
        for i in range(0, len(tok), 3):          # po kosih, kot jih lahko vrne vticnica
            okvirji += d.dodaj(tok[i:i + 3])
        izid = [lm.razcleni(v, t) for v, t in okvirji]
        self.assertEqual(izid, [("K", {"k": 7, "m": "zacetek", "a": [1, "č"]}), ("Z", {"razmerje": 1.25}), ("P", 3),
                                ("Q", 3), ("O", (-5, True, '{"a": "š"}')), ("D", ("videz", "[1]")),
                                ("U", {"u": "aktiviraj"})])

    def test_prevelik_okvir(self):
        with self.assertRaises(lm.PrevelikOkvir):
            lm.Dekoder().dodaj((lm.NAJVEC_OKVIR + 1).to_bytes(4, "big") + b"K")

    def test_besedilo_kot_v_enem_procesu(self):
        # QML razclenjuje isto besedilo kot prej iz os_lupina.QmlPogled (json.dumps, ensure_ascii=False, default=str).
        podatki = {"pot": "/dom/čšž", "n": 3, "cas": object()}
        self.assertEqual(lm.besedilo_json(podatki), json.dumps(podatki, ensure_ascii=False, default=str))

    def test_sogovornik_isti_uporabnik(self):
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        self.assertTrue(lm.nas_sogovornik(a))
        self.assertEqual(lm.sogovornik(a)[0], os.getpid())
        a.close()
        b.close()

    def test_mapa_izvajanja_zaprta(self):
        d = tempfile.mkdtemp()
        os.chmod(d, 0o755)
        with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": d}):
            mapa = lm.mapa_izvajanja()
            os.chmod(mapa, 0o755)
            self.assertEqual(lm.mapa_izvajanja(), mapa)
        self.assertEqual(os.stat(mapa).st_mode & 0o777, 0o700)
        shutil.rmtree(d)


class UrlBrezQt(unittest.TestCase):
    def test_enak_kot_qurl(self):
        try:
            from PySide6.QtCore import QUrl
        except ImportError:
            self.skipTest("PySide6 ni na voljo")
        from core import os_lupina
        poti = ["/dom/a/x%sy.jpg" % chr(i) for i in range(32, 127)] + ["/dom/čšž ČŠŽ/é ü€ñß.png", ""]
        with mock.patch.dict(sys.modules, {"PySide6.QtCore": None}):
            brez = [os_lupina._url(p) for p in poti]
        self.assertEqual(brez, [QUrl.fromLocalFile(p).toString() if p else "" for p in poti])


class _LazenOS:
    """Kar streznik lupine od Safeer OS potrebuje: _obdelaj_klic (odgovor prek pogleda, tudi iz niti)."""

    def __init__(self):
        self.klici = []

    def _obdelaj_klic(self, pogled, klic_id, metoda, a):
        self.klici.append((metoda, a))
        if metoda == "vNiti":
            threading.Thread(target=lambda: pogled.qml_odgovor(klic_id, True, {"nit": True})).start()
        elif metoda == "napaka":
            raise RuntimeError("ni slo")
        else:
            pogled.qml_odgovor(klic_id, True, {"metoda": metoda, "a": a})


class Streznik(unittest.TestCase):
    """core/lupina_streznik.OddaljenaLupina v zanki GLib (kot v Safeer OS), odjemalec je navadna vticnica."""

    @classmethod
    def setUpClass(cls):
        try:
            import gi
            gi.require_version("GLib", "2.0")
            gi.require_version("Gtk", "4.0")       # _spremljaj_temo (Safeer OS ima Gtk 4.0)
            from gi.repository import GLib
        except (ImportError, ValueError):
            raise unittest.SkipTest("GLib ni na voljo")
        cls.GLib = GLib

    def setUp(self):
        from core import lupina_streznik
        self.mapa = tempfile.mkdtemp()
        self.os = _LazenOS()
        self.lupina = lupina_streznik.OddaljenaLupina(self.os, os.path.join(self.mapa, "l.sock"))
        self.dek = lm.Dekoder()

    def tearDown(self):
        self.lupina.zapri()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def vrti(self, pogoj, rok=5.0):
        k = self.GLib.MainContext.default()
        konec = time.monotonic() + rok
        while time.monotonic() < konec and not pogoj():
            k.iteration(False)
            time.sleep(0.002)
        return pogoj()

    def povezi(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(self.lupina.pot)
        s.setblocking(False)
        stevec = self.lupina.stevec_povezav
        self.assertTrue(self.vrti(lambda: self.lupina.stevec_povezav > stevec))
        return s

    def prejmi(self, s, n=1, rok=5.0):
        izid = []

        def poskusi():
            try:
                podatki = s.recv(65536)
                if podatki:
                    izid.extend(lm.razcleni(v, t) for v, t in self.dek.dodaj(podatki))
            except BlockingIOError:
                pass
            return len(izid) >= n
        self.vrti(poskusi, rok)
        return izid

    def test_vticnica_0600(self):
        self.assertEqual(os.stat(self.lupina.pot).st_mode & 0o777, 0o600)

    def test_klic_odgovor_ping_dogodek(self):
        s = self.povezi()
        s.sendall(lm.zdravo({"razmerje": 1.5}) + lm.klic(11, "odmev", ["x"]) + lm.ping(4) + lm.klic(12, "vNiti", []))
        izid = self.prejmi(s, 3)
        self.assertIn(("O", (11, True, '{"metoda": "odmev", "a": ["x"]}')), izid)
        self.assertIn(("Q", 4), izid)
        self.assertIn(("O", (12, True, '{"nit": true}')), izid)
        self.assertEqual(self.lupina._razmerje_zaslona(), 1.5)
        # Dogodek iz niti (npr. Link) gre lupini prek glavne zanke.
        threading.Thread(target=lambda: self.lupina.dogodek("sporocilaStevilo", {"n": 2})).start()
        self.assertEqual(self.prejmi(s, 1), [("D", ("sporocilaStevilo", '{"n": 2}'))])
        self.lupina.okno.requestActivate()
        self.assertEqual(self.prejmi(s, 1), [("U", {"u": "aktiviraj"})])
        s.close()

    def test_napaka_metode_je_odgovor_z_napako(self):
        s = self.povezi()
        s.sendall(lm.klic(5, "napaka", []))
        self.assertEqual(self.prejmi(s, 1), [("O", (5, False, '"ni slo"'))])
        s.close()

    def test_nova_lupina_zamenja_staro(self):
        prva = self.povezi()
        druga = self.povezi()
        self.assertTrue(self.vrti(lambda: prva.recv(10) == b"" if self._berljiva(prva) else False))
        druga.sendall(lm.klic(1, "odmev", []))
        self.assertEqual(len(self.prejmi(druga, 1)), 1)
        druga.close()

    @staticmethod
    def _berljiva(s):
        import select
        return bool(select.select([s], [], [], 0)[0])

    def test_zamrznjena_lupina_ne_zamrzne_safeer_os(self):
        """Lupina, ki ne bere (SIGSTOP), ne sme ustaviti glavne zanke Safeer OS: povezava se prekine pri meji."""
        from core import lupina_streznik
        s = self.povezi()
        with mock.patch.object(lupina_streznik, "NAJVEC_IZHOD", 256 * 1024):
            velik = "x" * 65536
            zacetek = time.monotonic()
            for _ in range(200):
                self.lupina.dogodek("velik", velik)
            self.assertLess(time.monotonic() - zacetek, 2.0, "posiljanje ne sme cakati na lupino")
            self.assertTrue(self.vrti(lambda: self.lupina._povezava is None, 2))
        s.close()

    def test_brez_lupine_dogodki_niso_napaka(self):
        self.lupina.dogodek("videz", {"a": 1})        # lupina se se zaganja: dogodek se zavrze, brez izjeme


class Odjemalec(unittest.TestCase):
    """core/lupina_proces.Odjemalec (Qt): vrsta klicev med ponovnim zagonom Safeer OS, napaka nedokoncanih klicev,
    dogodek osStanje za obvestilo na namizju, id-ji z zamikom."""

    @classmethod
    def setUpClass(cls):
        try:
            from PySide6.QtCore import QObject, Signal
            from PySide6.QtWidgets import QApplication
        except ImportError:
            raise unittest.SkipTest("PySide6 ni na voljo")
        # QApplication (ne QCoreApplication): naslednji preizkusi v istem procesu ustvarjajo okna QML.
        os.environ["QT_QPA_PLATFORM"] = os.environ.get("QT_QPA_PLATFORM") or "offscreen"  # rezervacija "" (okolje_procesa)
        cls.app = QApplication.instance() or QApplication(["test"])

        class Most(QObject):
            odgovor = Signal(int, bool, str)
            dogodek = Signal(str, str)
        cls.Most = Most

    def setUp(self):
        from core import lupina_proces
        self.mapa = tempfile.mkdtemp()
        self.pot = os.path.join(self.mapa, "l.sock")
        self.odgovori, self.dogodki = [], []
        most = self.Most()
        most.odgovor.connect(lambda i, ok, b: self.odgovori.append((i, ok, b)))
        most.dogodek.connect(lambda v, p: self.dogodki.append((v, json.loads(p))))
        lazna = mock.Mock()
        lazna.most = most
        lazna.zdravo.return_value = {"pid": 1, "razmerje": 1.0}
        lazna.dogodek.side_effect = lambda v, p: most.dogodek.emit(v, json.dumps(p))
        self.lazna = lazna
        self.most = most
        self.odj = lupina_proces.Odjemalec(lazna, self.pot)
        self.streznik = None

    def tearDown(self):
        if self.odj._casovnik is not None:
            self.odj._casovnik.stop()
        if self.odj.sock is not None:
            self.odj.sock.close()
        if self.streznik is not None:
            self.streznik.close()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def vrti(self, pogoj, rok=5.0):
        konec = time.monotonic() + rok
        while time.monotonic() < konec and not pogoj():
            self.app.processEvents()
            time.sleep(0.005)
        return pogoj()

    def poslusaj(self):
        self.streznik = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.streznik.bind(self.pot)
        self.streznik.listen(2)

    def sprejmi(self):
        self.streznik.settimeout(0.05)
        konec = time.monotonic() + 5
        while time.monotonic() < konec:
            self.app.processEvents()
            try:
                c, _ = self.streznik.accept()
                return c
            except socket.timeout:
                continue
        self.fail("lupina se ni povezala")

    def okvirji(self, c, n, rok=5.0):
        d, izid = lm.Dekoder(), []
        c.settimeout(0.05)
        konec = time.monotonic() + rok
        while time.monotonic() < konec and len(izid) < n:
            self.app.processEvents()
            try:
                izid += [lm.razcleni(v, t) for v, t in d.dodaj(c.recv(65536))]
            except socket.timeout:
                pass
        return izid

    def test_klici_pocakajo_na_safeer_os(self):
        with mock.patch("core.lupina_most.beri_stanje_varuha", return_value={}):
            self.odj.zacni()
            self.odj.klic(1, "zacetek", [])          # ob prijavi: Safeer OS se zaganja
            self.assertFalse(self.odj.povezan())
            self.poslusaj()
            c = self.sprejmi()
            okv = self.okvirji(c, 2)
        self.assertEqual(okv[0][0], "Z")
        self.assertEqual(okv[1][0], "K")
        zica = okv[1][1]["k"]
        self.assertNotEqual(zica, 1, "id na zici ima zamik tega procesa")
        c.sendall(lm.odgovor(zica, True, '{"ok": 1}') + lm.odgovor(zica + 1, True, "1") + lm.dogodek("videz", "{}"))
        self.assertTrue(self.vrti(lambda: self.odgovori and self.dogodki and self.dogodki[-1][0] == "videz"))
        self.assertEqual(self.odgovori, [(1, True, '{"ok": 1}')], "tuj id (stara lupina) se zavrze")
        self.assertEqual(self.dogodki[0], ("osStanje", {"stanje": "", "ponovno": False}))
        c.close()

    def test_sesutje_safeer_os(self):
        stanje = {"procesi": {"safeer-os": {"stanje": "zaganja"}}}
        with mock.patch("core.lupina_most.beri_stanje_varuha", side_effect=lambda *a: stanje):
            self.poslusaj()
            self.odj.zacni()
            c = self.sprejmi()
            self.okvirji(c, 1)
            self.odj.klic(5, "mapa", ["/"])
            self.okvirji(c, 1)
            self.streznik.close()                     # Safeer OS se je sesul med klicem
            os.unlink(self.pot)
            c.close()
            self.assertTrue(self.vrti(lambda: (5, False, '"%s"' % "safeerOsSeZaganja") in self.odgovori))
            self.assertTrue(self.vrti(lambda: ("osStanje", {"stanje": "znova", "ponovno": False}) in self.dogodki))
            stanje["procesi"]["safeer-os"]["stanje"] = "obupal"
            self.assertTrue(self.vrti(lambda: ("osStanje", {"stanje": "obupal", "ponovno": False}) in self.dogodki))
            # Program sistema se zazene tudi brez Safeer OS (lokalno), drugo pocaka.
            with mock.patch("core.lupina_proces.zazeni_lokalno", return_value=True) as z:
                self.odj.klic(6, "zazeni", ["org.x.editor.desktop"])
            z.assert_called_once_with("org.x.editor.desktop")
            self.assertIn((6, True, "null"), self.odgovori)
            self.odj.klic(7, "odpriRazdelek", ["splet"])
            self.poslusaj()
            c = self.sprejmi()
            okv = self.okvirji(c, 2)
            self.assertEqual(okv[1][1]["m"], "odpriRazdelek", "klik med ponovnim zagonom se izvede")
            self.assertTrue(self.vrti(lambda: ("osStanje", {"stanje": "", "ponovno": True}) in self.dogodki))
            c.close()

    def test_star_klic_se_ne_izvede(self):
        from core import lupina_proces
        with mock.patch("core.lupina_most.beri_stanje_varuha", return_value={}), \
                mock.patch.object(lupina_proces, "CAKANJE_KLICA_S", 0.2):
            self.odj.zacni()
            self.odj.klic(9, "vSmeti", [["/tmp/x"]])
            time.sleep(0.3)
            self.assertTrue(self.vrti(lambda: (9, False, '"safeerOsSeZaganja"') in self.odgovori))

    def test_gumb_zazeni_znova_obvesti_varuha(self):
        with mock.patch("core.varuh_procesov.obvesti", return_value=True) as obvesti:
            self.odj.klic(3, "varuhZnova", [])
        obvesti.assert_called_once_with("SAFEER_ZNOVA=1")
        self.assertIn((3, True, "null"), self.odgovori)

    def test_zazeni_lokalno_samo_vnos_desktop(self):
        from core import lupina_proces
        self.assertFalse(lupina_proces.zazeni_lokalno("../../bin/sh"))
        self.assertFalse(lupina_proces.zazeni_lokalno("/usr/bin/xterm"))
        self.assertFalse(lupina_proces.zazeni_lokalno("ni-tega-programa-safeer.desktop"))


class Povezano(unittest.TestCase):
    """Safeer OS ne nalozi Qt, ko je lupina v svojem procesu; lupina ne nalozi Gtk, WebKit ali Gio."""

    def test_safeer_os_brez_qt(self):
        s = _beri("safeer_os.py")
        self.assertIn('sys.modules["PySide6"] = None', s)
        self.assertIn("lupina_streznik.OddaljenaLupina(self) if lupina_streznik.locena() else os_lupina.Namizje(self)", s)
        self.assertIn("(lupina_streznik.locena() or os_lupina.pripravi(", s)

    def test_lupina_brez_gtk(self):
        koda = ("import sys; sys.path.insert(0, %r); import core.lupina_proces as l; "
                "print(' '.join(sorted(m for m in sys.modules if m.split('.')[0] in ('gi', 'safeer_os') "
                "or m in ('hashlib',))))" % KOREN)
        izid = subprocess.run([sys.executable, "-c", koda], capture_output=True, text=True, timeout=60)
        self.assertEqual(izid.stdout.strip(), "", izid.stderr)

    def test_stanje_obnove(self):
        s = _beri("safeer_os.py")
        self.assertIn("nova_razlicica.OBNOVA", s)
        # Prevzeta pred nitmi in ne gre naprej programom (core/okolje_procesa.PREVZETE).
        self.assertIn('okolje_procesa.prevzemi("SAFEER_OBNOVA")', s)
        self.assertIn('stanje.get("pid") != prejsnji', s)
        self.assertIn('"okna": [ime for ime, par in self.okna_razdelkov.items() if par[0].get_visible()]', s)

    def test_besedila_obvestila_v_vseh_jezikih(self):
        js = _beri("assets", "os", "besedila-namizja.js")
        for kljuc in ("osSeZaganja", "osSeZnovaZaganja", "osCakaPomnilnik", "osUstavljen", "osZazeniZnova"):
            self.assertEqual(js.count(kljuc + ":"), 6, kljuc)
        qml = _beri("assets", "os", "qml", "Namizje.qml")
        self.assertIn('vrsta !== "osStanje"', qml)
        self.assertIn("Accessible.role: Accessible.AlertMessage", qml)


def _zivo_mogoce():
    if not os.environ.get("DISPLAY") or not shutil.which("dbus-run-session") or not shutil.which("xwininfo"):
        return False
    try:
        import importlib.util
        return importlib.util.find_spec("PySide6") is not None and importlib.util.find_spec("gi") is not None
    except Exception:  # noqa: BLE001
        return False


@unittest.skipUnless(_zivo_mogoce(), "potreben Xvfb, D-Bus, PySide6 in WebKitGTK")
class Zivo(unittest.TestCase):
    """Pravi varuh, prava lupina in pravi Safeer OS (--delovna) pod Xvfb: sesutje Safeer OS ne podre namizja, sesutje
    lupine ne ustavi Safeer OS."""

    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-locena-")
        o = dict(os.environ)
        for k in ("XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME", "XDG_RUNTIME_DIR"):
            o[k] = os.path.join(self.mapa, k.lower())
            os.makedirs(o[k], mode=0o700)
        os.makedirs(os.path.join(o["XDG_CONFIG_HOME"], "safeer-os"))
        with open(os.path.join(o["XDG_CONFIG_HOME"], "safeer-os", "os.json"), "w") as f:
            json.dump({"vodnik": "ni_potreben"}, f)
        # Kot ob pravem zagonu: brez izbir ozadja Qt/GDK, ki jih nastavijo drugi preizkusi v istem procesu (offscreen).
        for k in ("SAFEER_LUPINA_VTIC", "NOTIFY_SOCKET", "WAYLAND_DISPLAY", "QT_QPA_PLATFORM", "QT_XCB_GL_INTEGRATION",
                  "QT_QPA_PLATFORMTHEME", "GDK_BACKEND", "SAFEER_LUPINA", "SAFEER_OS_BREZ_OKEN", "SAFEER_LOCENA_LUPINA"):
            o.pop(k, None)
        o["XDG_SESSION_TYPE"] = "x11"
        self.o = o
        self.p = subprocess.Popen(["dbus-run-session", "--", sys.executable, os.path.join(KOREN, "core", "varuh_procesov.py"),
                                   "--delovna"], env=o, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def tearDown(self):
        varuh = self.stanje().get("pid")
        if varuh:
            try:
                os.kill(varuh, signal.SIGTERM)
            except OSError:
                pass
        try:
            self.p.wait(30)
        except subprocess.TimeoutExpired:
            self.p.kill()
            self.p.wait(5)
        shutil.rmtree(self.mapa, ignore_errors=True)

    def stanje(self):
        try:
            with open(os.path.join(self.o["XDG_RUNTIME_DIR"], "safeer-os", "varuh.json")) as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def proces(self, ime):
        return (self.stanje().get("procesi") or {}).get(ime) or {}

    def cakaj(self, pogoj, rok):
        konec = time.monotonic() + rok
        while time.monotonic() < konec:
            if pogoj():
                return True
            time.sleep(0.1)
        return False

    def namizje_vidno(self):
        r = subprocess.run(["xwininfo", "-name", "Safeer OS namizje"], capture_output=True, text=True, env=self.o)
        return "IsViewable" in r.stdout

    def test_sesutje_safeer_os_in_lupine(self):
        self.assertTrue(self.cakaj(lambda: self.proces("safeer-os").get("stanje") == "tece"
                                   and self.proces("safeer-lupina").get("stanje") == "tece", 90), self.stanje())
        self.assertTrue(self.cakaj(self.namizje_vidno, 30))
        lupina, os_ = self.proces("safeer-lupina")["pid"], self.proces("safeer-os")["pid"]
        with open("/proc/%d/maps" % lupina) as f:
            preslikave = f.read()
        for knjiznica in ("libgtk-4", "libwebkitgtk", "libgirepository"):
            self.assertNotIn(knjiznica, preslikave, "lupina mora biti brez Gtk, WebKit in gi")
        with open("/proc/%d/maps" % os_) as f:
            self.assertNotIn("libQt6", f.read(), "Safeer OS brez Qt, ko je lupina v svojem procesu")

        os.kill(os_, signal.SIGSEGV)
        vedno_vidno = True
        konec = time.monotonic() + 60
        while time.monotonic() < konec:
            vedno_vidno = vedno_vidno and self.namizje_vidno()
            p = self.proces("safeer-os")
            if p.get("stanje") == "tece" and p.get("pid") != os_:
                break
            time.sleep(0.2)
        self.assertEqual(self.proces("safeer-os").get("stanje"), "tece", self.stanje())
        self.assertTrue(vedno_vidno, "namizje mora ostati, ko pade Safeer OS")
        self.assertEqual(self.proces("safeer-lupina")["pid"], lupina, "lupina ostane ista")

        os_ = self.proces("safeer-os")["pid"]
        os.kill(lupina, signal.SIGSEGV)
        self.assertTrue(self.cakaj(lambda: self.proces("safeer-lupina").get("pid") not in (lupina, 0, None)
                                   and self.proces("safeer-lupina").get("stanje") == "tece", 60), self.stanje())
        self.assertTrue(self.cakaj(self.namizje_vidno, 30))
        self.assertEqual(self.proces("safeer-os")["pid"], os_, "Safeer OS tece naprej")


def _sway_mogoc():
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import wayland_okolje
        import importlib.util
        return wayland_okolje.na_voljo() and importlib.util.find_spec("gi") is not None
    except Exception:  # noqa: BLE001
        return False


@unittest.skipUnless(_sway_mogoc(), "potreben brezglavi sway (tests/wayland_okolje.py)")
class ZivoWayland(unittest.TestCase):
    """Wayland (seja_prikaza): --delovna tam nima namizja pod okni, zato varuh lupine ne zazene - Safeer OS (storitve)
    tece pod varuhom, njegovo sesutje ali zamrznitev varuh popravi enako kot na X11."""

    def test_brez_lupine_safeer_os_pod_varuhom(self):
        import wayland_okolje
        with wayland_okolje.Sway() as sw:
            run = sw.okolje["XDG_RUNTIME_DIR"]
            os.makedirs(os.path.join(sw.okolje["XDG_CONFIG_HOME"], "safeer-os"), exist_ok=True)
            with open(os.path.join(sw.okolje["XDG_CONFIG_HOME"], "safeer-os", "os.json"), "w") as f:
                json.dump({"vodnik": "ni_potreben"}, f)
            p = sw.zazeni([sys.executable, os.path.join(KOREN, "core", "varuh_procesov.py"), "--delovna"])

            def stanje():
                try:
                    with open(os.path.join(run, "safeer-os", "varuh.json")) as f:
                        return json.load(f)
                except (OSError, ValueError):
                    return {}
            konec = time.monotonic() + 90
            while time.monotonic() < konec and ((stanje().get("procesi") or {}).get("safeer-os") or {}).get("stanje") != "tece":
                time.sleep(0.2)
            procesi = stanje().get("procesi") or {}
            try:
                # Scit tece v svojem procesu (1.0.129) tudi na Waylandu; lupine ni.
                self.assertEqual([i for i in procesi if i != "safeer-scit"], ["safeer-os"], "na Waylandu brez locene lupine")
                self.assertEqual(procesi["safeer-os"]["stanje"], "tece", sw.dnevnik())
                stari = procesi["safeer-os"]["pid"]
                os.kill(stari, signal.SIGSEGV)
                konec = time.monotonic() + 60
                while time.monotonic() < konec:
                    s = (stanje().get("procesi") or {}).get("safeer-os") or {}
                    if s.get("stanje") == "tece" and s.get("pid") != stari:
                        break
                    time.sleep(0.2)
                s = (stanje().get("procesi") or {}).get("safeer-os") or {}
                self.assertEqual(s.get("stanje"), "tece")
                self.assertNotEqual(s.get("pid"), stari)
                self.assertEqual(sw.okna(), [], "--delovna na Waylandu ne odpre okna (le storitve)")
            finally:
                p.send_signal(signal.SIGTERM)
                p.wait(30)


if __name__ == "__main__":
    unittest.main()
