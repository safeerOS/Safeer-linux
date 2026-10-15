"""Namizni programi kot kanali Sporocil (Viber, Signal Desktop; lastnik, 15. 10. 2026) - brez pravih programov:
lazen program (tests/fixtures/lazni_program_okno.py, okno GTK4 z vnosom) v Xvfb.

core/vstavi_okno.py: vstavitev okna (XReparentWindow), sledenje velikosti, skrij/pokazi, fokus tipkovnice ob vstopu
miske (tipke XTest pridejo v program), vrnitev na namizje. core/namizni_programi.py: zaznava namestitve (.desktop s
StartupWMClass, ukaz na poti, AppImage, izbrana pot). core/znacke_programov.py: LauncherEntry, obvestila (D-Bus)."""
import ctypes
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAZNI = os.path.join(KOREN, "tests", "fixtures", "lazni_program_okno.py")

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, GLib, Gtk  # noqa: E402

from core import namizni_programi, vstavi_okno  # noqa: E402

Gtk.init()


def _cakaj(pogoj, cas=8.0):
    kontekst = GLib.MainContext.default()
    rok = time.monotonic() + cas
    while time.monotonic() < rok:
        if pogoj():
            return True
        if not kontekst.iteration(False):
            time.sleep(0.005)
    return pogoj()


def _x11():
    try:
        return vstavi_okno.X11()
    except OSError:
        return None


@unittest.skipUnless(os.environ.get("DISPLAY") and _x11() is not None, "potrebuje X11 (Xvfb)")
class Vstavljanje(unittest.TestCase):
    def setUp(self):
        self.otrok = subprocess.Popen([sys.executable, LAZNI, "6"], stdout=subprocess.PIPE, text=True)
        self.addCleanup(self._koncaj_otroka)
        self.assertEqual(self.otrok.stdout.readline().strip(), "pripravljen")
        self.x = vstavi_okno.X11()
        self.addCleanup(self.x.zapri)

    def _koncaj_otroka(self):
        self.otrok.terminate()
        try:
            self.otrok.wait(5)
        except subprocess.TimeoutExpired:
            self.otrok.kill()

    def test_okno_samo_od_pravega_procesa(self):
        """WM_CLASS si lahko nastavi vsak program: okno se izbere samo, ce _NET_WM_PID pripada programu."""
        self.assertTrue(_cakaj(lambda: self.x.najdi(["safeer-lazni-program"]), 5))
        okno = self.x.najdi(["safeer-lazni-program"])
        self.assertEqual(self.x.pid(okno), self.otrok.pid)
        self.assertEqual(self.x.najdi(["safeer-lazni-program"], sprejmi=lambda pid: False), 0)
        self.assertEqual(self.x.najdi(["safeer-lazni-program"], sprejmi=lambda pid: pid == self.otrok.pid), okno)
        program = {"ukazi": ["viber"], "razredi": ["safeer-lazni-program"]}
        self.assertFalse(namizni_programi.pripada_programu(self.otrok.pid, {"ukaz": ["/opt/viber/Viber"]}, program),
                         "tuj proces (python) z enakim WM_CLASS ni program kanala")
        self.assertTrue(namizni_programi.pripada_programu(self.otrok.pid, {"ukaz": ["/opt/viber/Viber"]}, program,
                                                          [self.otrok.pid]), "proces, ki ga je zagnal Safeer")

    def test_padec_safeer_okno_programa_ostane(self):
        """Safeer OS pade (SIGKILL) z vstavljenim oknom: okno programa se vrne na namizje in ostane (X11 save-set),
        ne izgine skupaj z nasim oknom (pregled 15. 10. 2026)."""
        import signal
        self.assertTrue(_cakaj(lambda: self.x.najdi(["safeer-lazni-program"]), 5))
        tuje = self.x.najdi(["safeer-lazni-program"])
        vstavi = subprocess.Popen([sys.executable, os.path.join(KOREN, "tests", "fixtures", "vstavi_in_padi.py"),
                                   "safeer-lazni-program", KOREN], stdout=subprocess.PIPE, text=True)
        self.addCleanup(lambda: vstavi.poll() is None and vstavi.kill())
        self.assertTrue(vstavi.stdout.readline().startswith("vstavljeno"))
        self.assertNotEqual(self.x.stars(tuje), self.x.koren())
        vstavi.send_signal(signal.SIGKILL)
        vstavi.wait(5)
        self.assertTrue(_cakaj(lambda: self.x.stars(tuje) == self.x.koren(), 3), "okno programa nazaj na namizju")
        self.assertEqual(self.x.stanje_prikaza(tuje), 2, "okno programa je vidno")
        self.assertIsNone(self.otrok.poll(), "program tece naprej")

    def test_vstavi_sledi_skrije_tipke_vrne(self):
        self.assertTrue(_cakaj(lambda: self.x.najdi(["SAFEER-lazni-program"]), 5), "iskanje po razredu brez velikosti crk")
        okno_programa = self.x.najdi(["safeer-lazni-program"])
        self.assertEqual(self.x.naslov(okno_programa), "(6) Lazni program")
        okno = Gtk.Window()
        okno.set_default_size(800, 600)
        skatla = Gtk.Box()
        nas_vnos = Gtk.Entry()          # vnos Safeerja: tipke, ki jih uporabnik tipka v Safeer
        nas_vnos.set_size_request(80, -1)
        skatla.append(nas_vnos)
        mesto = Gtk.DrawingArea()
        mesto.set_hexpand(True)
        mesto.set_vexpand(True)
        skatla.append(mesto)
        okno.set_child(skatla)
        okno.present()
        self.addCleanup(okno.destroy)
        self.assertTrue(_cakaj(lambda: mesto.get_mapped()))
        v = vstavi_okno.VstavljenoOkno(Gtk, GLib, mesto)
        self.addCleanup(v.unici)
        self.assertTrue(v.vstavi(okno_programa))
        nase = vstavi_okno.Mesto(Gtk, mesto).xid_starsa()
        self.assertTrue(_cakaj(lambda: self.x.stars(okno_programa) == nase), "okno programa je v nasem oknu")
        # sledi velikosti gradnika
        okno.set_default_size(700, 500)
        _cakaj(lambda: False, 0.4)
        v.prilagodi()
        r = vstavi_okno.Mesto(Gtk, mesto).pravokotnik()
        a = vstavi_okno._XWindowAttributes()
        self.x.lib.XGetWindowAttributes(self.x.dpy, okno_programa, ctypes.byref(a))
        self.assertEqual((a.x, a.y, a.width, a.height), tuple(r))
        # skrij (drug kanal ali razdelek) in pokazi
        mesto.set_visible(False)
        self.assertTrue(_cakaj(lambda: self.x.stanje_prikaza(okno_programa) == vstavi_okno.IS_UNMAPPED, 2))
        mesto.set_visible(True)
        self.assertTrue(_cakaj(lambda: self.x.stanje_prikaza(okno_programa) == 2, 2))
        # Tipkovnica (pregled 15. 10. 2026): sam prehod miske program NE dobi fokusa (tipke ostanejo v Safeerju); klik v
        # program mu da fokus; klik v Safeer ga vrne.
        xtst = ctypes.cdll.LoadLibrary("libXtst.so.6")
        xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
        xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        xtst.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        self.x.lib.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.x.lib.XKeysymToKeycode.restype = ctypes.c_ubyte
        _o = ctypes.c_ulong()

        def miska(okno_, x, y):
            rx, ry = ctypes.c_int(), ctypes.c_int()
            self.x.lib.XTranslateCoordinates(self.x.dpy, okno_, self.x.koren(), x, y, ctypes.byref(rx), ctypes.byref(ry),
                                             ctypes.byref(_o))
            xtst.XTestFakeMotionEvent(self.x.dpy, -1, rx.value, ry.value, 0)
            self.x.lib.XFlush(self.x.dpy)
            _cakaj(lambda: False, 0.4)

        def klik():
            xtst.XTestFakeButtonEvent(self.x.dpy, 1, 1, 0)
            self.x.lib.XFlush(self.x.dpy)
            _cakaj(lambda: False, 0.12)          # kratek klik (pod 150 ms)
            xtst.XTestFakeButtonEvent(self.x.dpy, 1, 0, 0)
            self.x.lib.XFlush(self.x.dpy)
            _cakaj(lambda: False, 0.4)

        def tipkaj(besedilo):
            for crka in besedilo:
                kc = self.x.lib.XKeysymToKeycode(self.x.dpy, ord(crka))
                xtst.XTestFakeKeyEvent(self.x.dpy, kc, 1, 0)
                xtst.XTestFakeKeyEvent(self.x.dpy, kc, 0, 0)
            self.x.lib.XFlush(self.x.dpy)
            _cakaj(lambda: False, 0.6)
        miska(nase, 10, 10)
        klik()                                    # klik v nas vnos: fokus Safeerju
        nas_vnos.grab_focus()
        self.x.fokus(nase)
        _cakaj(lambda: False, 0.3)
        tipkaj("ab")
        self.assertEqual(nas_vnos.get_text(), "ab")
        miska(okno_programa, 20, 20)              # samo prehod miske: fokus ostane Safeerju
        self.assertFalse(self.x.fokus_v(okno_programa), "prehod miske ne premakne fokusa")
        klik()                                    # klik v program: fokus programu
        self.assertTrue(self.x.fokus_v(okno_programa))
        tipkaj("safeer")
        self.assertEqual(nas_vnos.get_text(), "ab")
        miska(nase, 10, 10)                       # samo izhod miske: program obdrzi fokus (prej ga je izgubil)
        self.assertTrue(self.x.fokus_v(okno_programa), "izhod miske ne vzame fokusa programu")
        klik()                                    # klik v Safeer: fokus nazaj
        self.assertFalse(self.x.fokus_v(okno_programa))
        tipkaj("c")
        self.assertEqual(sorted(nas_vnos.get_text()), ["a", "b", "c"], "tipke spet v Safeerju (klik postavi kazalec)")
        # vrnitev na namizje: okno programa spet otrok korenskega okna, program tece naprej
        v.vrni()
        self.assertTrue(_cakaj(lambda: self.x.stars(okno_programa) == self.x.koren(), 2))
        self.assertIsNone(self.otrok.poll(), "program se ne ustavi")
        self._koncaj_otroka()
        izhod = self.otrok.stdout.read()
        self.assertIn("vnos:safeer", izhod, "tipke so prisle v vstavljeni program")
        self.assertNotIn("safeerc", izhod)


@unittest.skipUnless(os.environ.get("DISPLAY") and _x11() is not None, "potrebuje X11 (Xvfb)")
class KanalProgram(unittest.TestCase):
    """Cela pot: kanal iz kataloga (lazen vnos - samo podatki), zagon ob zagonu namizja, vgradnja v Sporocila,
    stevilo neprebranih iz naslova okna, ob koncu okno nazaj na namizje (program tece naprej)."""

    def test_kanal_program_od_zagona_do_konca(self):
        from unittest import mock
        from core import os_kanali_sporocil, spletni_klepeti
        mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, mapa)
        ovoj = os.path.join(mapa, "lazni-program")
        with open(ovoj, "w") as f:
            f.write("#!/bin/sh\nexec %s %s 3\n" % (sys.executable, LAZNI))
        os.chmod(ovoj, 0o755)
        vnos = {"id": "lazni", "ime": "Lazni program", "vrsta": "klepet", "splet": "", "prenos": "https://primer.invalid/",
                "program": {"vnosi": [], "ukazi": [], "appimage": [], "razredi": ["safeer-lazni-program"], "argumenti": []}}
        self.addCleanup(lambda: subprocess.run(["pkill", "-f", LAZNI]))

        class _S(dict):
            def set(self, k, v):
                self[k] = v
        with mock.patch.object(spletni_klepeti, "KATALOG", spletni_klepeti.KATALOG + [vnos]), \
                mock.patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"}), \
                mock.patch.object(os_kanali_sporocil.KanaliSporocil, "_uskladi_znacke"):
            k = os_kanali_sporocil.KanaliSporocil(Gtk, GLib, Gio, lambda: None, _S(), lambda: "sl", lambda *a: None,
                                                  lambda kid: None)
            self.assertTrue(k.katalog()[-1]["namescen"] is False, "brez izbrane poti program ni namescen")
            seznam = k.dodaj(katalog="lazni", pot=ovoj)
            self.assertEqual((seznam[0]["vrsta"], seznam[0]["namescen"]), ("program", True))
            self.assertTrue(_cakaj(lambda: k.zivi["lazni"].okno.okno, 15), "okno zagnanega programa je najdeno")
            self.assertEqual(k.kanali.najdi("lazni")["neprebrano"], 3, "stevilo iz naslova okna »(3) Lazni program«")
            okno = Gtk.Window()
            okno.set_default_size(800, 600)
            stran = Gtk.Label(label="Sporocila")
            prekrivanje = Gtk.Overlay()
            prekrivanje.set_child(stran)
            okno.set_child(prekrivanje)
            okno.present()
            self.addCleanup(okno.destroy)
            self.assertTrue(_cakaj(lambda: okno.get_mapped()))
            r = {"x": 200, "y": 60, "w": 560, "h": 500, "vw": 800, "vh": 600, "dpr": 1}
            self.assertEqual(k.pokazi(stran, prekrivanje, "lazni", r), {"ok": True, "vgrajeno": True})
            x = vstavi_okno.X11()
            self.addCleanup(x.zapri)
            w = k.zivi["lazni"].okno.okno
            nase = vstavi_okno.Mesto(Gtk, k.zivi["lazni"].gradnik).xid_starsa()
            self.assertTrue(_cakaj(lambda: x.stars(w) == nase, 5), "okno programa je v Sporocilih")
            k.koncaj()
            self.assertTrue(_cakaj(lambda: x.stars(w) == x.koren(), 3), "ob koncu nazaj na namizje")


class Zaznava(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.mapa)
        self.program = {"vnosi": ["primer.desktop"], "ukazi": ["safeer-ni-tega-ukaza"], "appimage": ["primer*.appimage"],
                        "razredi": ["PrimerPC"], "argumenti": ["--ozone-platform=x11"]}

    def _izvrsljiva(self, pot):
        with open(pot, "w") as f:
            f.write("#!/bin/sh\n")
        os.chmod(pot, os.stat(pot).st_mode | stat.S_IXUSR)
        return pot

    def test_nic_namesceno(self):
        self.assertIsNone(namizni_programi.najdi(self.program, mape_vnosov=[self.mapa], mape_appimage=[self.mapa]))

    def test_vnos_z_razredom_okna(self):
        with open(os.path.join(self.mapa, "primer.desktop"), "w") as f:
            f.write("[Desktop Entry]\nType=Application\nName=Primer\nExec=/opt/primer/Primer %U\nStartupWMClass=Primer.PrimerPC\n")
        n = namizni_programi.najdi(self.program, mape_vnosov=[self.mapa], mape_appimage=[])
        self.assertEqual(n["oblika"], "vnos")
        self.assertEqual(n["ukaz"], ["/opt/primer/Primer", "--ozone-platform=x11"])
        self.assertEqual(n["razredi"][0], "Primer.PrimerPC", "StartupWMClass vnosa ima prednost")

    def test_appimage_in_izbrana_pot(self):
        ai = self._izvrsljiva(os.path.join(self.mapa, "Primer-1.2-x86_64.AppImage"))
        n = namizni_programi.najdi(self.program, mape_vnosov=[], mape_appimage=[self.mapa])
        self.assertEqual((n["oblika"], n["ukaz"][0]), ("appimage", ai))
        drugje = self._izvrsljiva(os.path.join(self.mapa, "kar.bin"))
        self.assertEqual(namizni_programi.najdi(self.program, drugje, mape_vnosov=[], mape_appimage=[])["oblika"], "pot")
        os.chmod(ai, 0o644)
        self.assertIsNone(namizni_programi.najdi(self.program, mape_vnosov=[], mape_appimage=[self.mapa]),
                          "neizvrsljiva datoteka ni namestitev")

    def test_katalog_viber_in_signal(self):
        from core import spletni_klepeti
        viber, signal = spletni_klepeti.po_id("viber"), spletni_klepeti.po_id("signal")
        # Testni PC 15. 10. 2026: Viber AppImage ima WM_CLASS »Viber.ViberPC« (ime Viber, razred ViberPC).
        self.assertIn("ViberPC", viber["program"]["razredi"])
        self.assertIn("org.signal.Signal.desktop", signal["program"]["vnosi"])
        self.assertIn("--ozone-platform=x11", signal["program"]["argumenti"], "Electron mora odpreti okno X11")
        self.assertEqual(signal["prenos"], "https://signal.org/download/", "Flatpak je neuraden - uradna stran")

    def test_exec_kode_polj_in_nevarni_ukazi(self):
        f = namizni_programi.ukaz_iz_exec
        self.assertEqual(f("/opt/Signal/signal-desktop --no-sandbox %U"), ["/opt/Signal/signal-desktop", "--no-sandbox"])
        self.assertEqual(f('"/opt/My App/app" --file=%f --name=100%% %i'), ["/opt/My App/app", "--file=", "--name=100%"])
        self.assertEqual(f("/usr/bin/flatpak run --command=signal-desktop org.signal.Signal @@u %U @@"),
                         ["/usr/bin/flatpak", "run", "--command=signal-desktop", "org.signal.Signal", "@@u", "@@"])
        self.assertEqual(f("--help"), [], "prvi argument z »-« bi flatpak-spawn bral kot moznost")
        self.assertEqual(f('"neprekinjeno'), [])
        self.assertEqual(f("%U"), [])
        # zazeni: brez lupine, nevaren prvi argument zavrnjen
        from unittest import mock
        with mock.patch.object(namizni_programi.subprocess, "Popen") as popen:
            self.assertIsNone(namizni_programi.zazeni({"ukaz": ["--env=X=1", "sh"]}))
            self.assertIsNone(namizni_programi.zazeni({"ukaz": []}))
            popen.assert_not_called()
        with mock.patch.object(namizni_programi.gostitelj, "v_flatpaku", lambda: True), \
                mock.patch.object(namizni_programi.shutil, "which", lambda u: "/usr/bin/" + u), \
                mock.patch.object(namizni_programi.subprocess, "Popen") as popen:
            namizni_programi.zazeni({"ukaz": ["/opt/viber/Viber", "--x"]})
            argv = popen.call_args[0][0]
            self.assertEqual(argv[:2], ["flatpak-spawn", "--host"])
            self.assertTrue(argv[2].startswith("--env=DISPLAY="))
            self.assertEqual(argv[3:], [namizni_programi.gostitelj.na_gostitelju("/opt/viber/Viber"), "--x"])
            self.assertNotIn("shell", popen.call_args[1])

    def test_izbrana_pot_absolutna_navadna_izvrsljiva(self):
        ai = self._izvrsljiva(os.path.join(self.mapa, "Viber.AppImage"))
        self.assertTrue(namizni_programi.je_izvrsljiva(ai))
        self.assertFalse(namizni_programi.je_izvrsljiva(os.path.relpath(ai)), "relativna pot")
        self.assertFalse(namizni_programi.je_izvrsljiva(self.mapa), "mapa ni program")
        self.assertFalse(namizni_programi.je_izvrsljiva(""))
        fifo = os.path.join(self.mapa, "cev")
        os.mkfifo(fifo)
        os.chmod(fifo, 0o755)
        self.assertFalse(namizni_programi.je_izvrsljiva(fifo), "posebna datoteka ni program")

    def test_pripada_programu(self):
        f = namizni_programi.pripada_programu
        self.assertFalse(f(os.getpid(), {"ukaz": ["/x"]}, {}), "nikoli nase okno")
        self.assertTrue(f(0, {"ukaz": ["/x"]}, {}), "okno brez PID: preveriti ni mogoce")
        self.assertTrue(f(4194304 + 7, {"ukaz": ["/x"]}, {}), "procesa ne vidimo (drug imenski prostor)")
        kopija = os.path.join(self.mapa, "viber-preizkus")
        shutil.copy(shutil.which("sleep"), kopija)
        p = subprocess.Popen([kopija, "30"])
        self.addCleanup(p.kill)
        tuj = subprocess.Popen(["sleep", "30"])
        self.addCleanup(tuj.kill)
        program = {"ukazi": ["viber"], "razredi": ["ViberPC", "Viber"]}
        self.assertTrue(f(p.pid, {"ukaz": ["/opt/viber/Viber"]}, program), "ime programa v poti procesa")
        self.assertFalse(f(tuj.pid, {"ukaz": ["/opt/viber/Viber"]}, program), "drug program z WM_CLASS Viber")
        lupina = subprocess.Popen(["sh", "-c", "sleep 30 & wait"])
        self.addCleanup(lupina.kill)
        otrok = None
        rok = time.monotonic() + 3
        while otrok is None and time.monotonic() < rok:
            try:
                otrok = int(open("/proc/%d/task/%d/children" % (lupina.pid, lupina.pid)).read().split()[0])
            except (OSError, IndexError, ValueError):
                time.sleep(0.05)
        self.assertIsNotNone(otrok)
        self.addCleanup(lambda: os.kill(otrok, 9))
        self.assertTrue(f(otrok, {"ukaz": ["/opt/viber/Viber"]}, program, [lupina.pid]), "potomec zagnanega procesa")
        self.assertTrue(f(tuj.pid, {"ukaz": ["/usr/bin/flatpak", "run", "com.viber.Viber"]}, program),
                        "program v Flatpaku: PID je iz peskovnika, preverba ni mogoca")

    def test_wayland_ni_vgradnje(self):
        from unittest import mock
        with mock.patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":0"}):
            self.assertFalse(namizni_programi.x11_seja())
        with mock.patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}):
            self.assertTrue(namizni_programi.x11_seja())


class ViriSamoZaVklopljeneProgramce(unittest.TestCase):
    """Opazovalec obvestil (vir 3) tece samo, ko je vklopljen kanal namiznega programa, in samo za njegova imena."""

    def test_opazovalec_samo_z_vklopljenim_programom(self):
        from unittest import mock
        from core import os_kanali_sporocil, spletni_klepeti, znacke_programov

        class _P:
            primerki = []

            def __init__(self, *_a, **k):
                self.imena, self.ustavljen, self.k = None, False, k
                _P.primerki.append(self)

            def nastavi_obvestila(self, imena):
                self.imena = set(imena)

            def ustavi(self):
                self.ustavljen = True

        class _S(dict):
            def set(self, k, v):
                self[k] = v
        k = os_kanali_sporocil.KanaliSporocil(Gtk, GLib, Gio, lambda: None, _S(), lambda: "sl", lambda *a: None,
                                              lambda kid: None)
        z = os_kanali_sporocil._Kanal({"id": "viber", "katalog": "viber"})
        z.program = {"ukaz": ["/opt/viber/Viber"], "razredi": ["ViberPC"]}
        with mock.patch.object(znacke_programov, "Poslusalec", _P):
            k._uskladi_znacke()
            self.assertEqual(_P.primerki, [], "brez kanalov programov ni poslusanja vodila")
            k.zivi["viber"] = z
            k._uskladi_znacke()
            self.assertEqual(len(_P.primerki), 1)
            self.assertIn("Viber", _P.primerki[0].imena)
            self.assertNotIn("/opt/viber/Viber", _P.primerki[0].imena)
            k.zivi["viber"].okno = None
            k._unici("viber")
            self.assertTrue(_P.primerki[0].ustavljen, "zadnji program izklopljen: opazovalec ustavljen")
            self.assertIsNone(k._znacke)
        self.assertEqual(spletni_klepeti.po_id("viber")["ime"], "Viber")


ODDAJNIK = r"""
import sys, time
import gi
from gi.repository import Gio, GLib
sys.path.insert(0, sys.argv[1])
from core import znacke_programov
prejeto = []
p = znacke_programov.Poslusalec(Gio, GLib, ob_znacki=lambda d, n: prejeto.append(["znacka", d, n]),
                                ob_pladnju=lambda i, a: prejeto.append(["pladenj", i, a]),
                                ob_obvestilu=lambda *a: prejeto.append(["obvestilo"] + list(a)))
p.nastavi_obvestila(["Primer"])
prejeto.append(["opazovalec", p.opazovalec is not None])
v = Gio.bus_get_sync(Gio.BusType.SESSION, None)
v.emit_signal(None, "/primer", "com.canonical.Unity.LauncherEntry", "Update",
              GLib.Variant("(sa{sv})", ("application://primer.desktop", {"count": GLib.Variant("x", 5),
                                                                        "count-visible": GLib.Variant("b", True)})))
v.emit_signal(None, "/primer", "com.canonical.Unity.LauncherEntry", "Update",
              GLib.Variant("(sa{sv})", ("application://primer.desktop", {"count": GLib.Variant("x", 9),
                                                                        "count-visible": GLib.Variant("b", False)})))
# Lazni streznik obvestil (kot namizje) in klic Notify, kot ga naredi program
XML = ("<node><interface name='org.freedesktop.Notifications'><method name='Notify'>"
       "<arg type='s' direction='in'/><arg type='u' direction='in'/><arg type='s' direction='in'/>"
       "<arg type='s' direction='in'/><arg type='s' direction='in'/><arg type='as' direction='in'/>"
       "<arg type='a{sv}' direction='in'/><arg type='i' direction='in'/><arg type='u' direction='out'/>"
       "</method></interface></node>")
streznik = Gio.bus_get_sync(Gio.BusType.SESSION, None)
streznik = Gio.DBusConnection.new_for_address_sync(Gio.dbus_address_get_for_bus_sync(Gio.BusType.SESSION, None),
    Gio.DBusConnectionFlags.AUTHENTICATION_CLIENT | Gio.DBusConnectionFlags.MESSAGE_BUS_CONNECTION, None, None)
streznik.register_object("/org/freedesktop/Notifications", Gio.DBusNodeInfo.new_for_xml(XML).interfaces[0],
                         lambda c, s, p, i, m, a, inv: inv.return_value(GLib.Variant("(u)", (1,))), None, None)
streznik.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "RequestName",
                   GLib.Variant("(su)", ("org.freedesktop.Notifications", 0)), None, Gio.DBusCallFlags.NONE, 2000, None)
for app in ("Drugo", "Primer"):     # obvestilo drugega programa: vodilo ga opazovalcu sploh ne poslje
    v.call("org.freedesktop.Notifications", "/org/freedesktop/Notifications", "org.freedesktop.Notifications", "Notify",
           GLib.Variant("(susssasa{sv}i)", (app, 0, "", "Ana", "Zivjo", [], {}, -1)), None,
           Gio.DBusCallFlags.NONE, 2000, None, None, None)
k = GLib.MainContext.default(); rok = time.monotonic() + 2
while time.monotonic() < rok:
    k.iteration(False); time.sleep(0.01)
p.nastavi_obvestila([])            # brez kanalov programov: opazovalec ustavljen
prejeto.append(["ustavljen", p.opazovalec is None])
v.call("org.freedesktop.Notifications", "/org/freedesktop/Notifications", "org.freedesktop.Notifications", "Notify",
       GLib.Variant("(susssasa{sv}i)", ("Primer", 0, "", "Ana", "Drugic", [], {}, -1)), None,
       Gio.DBusCallFlags.NONE, 2000, None, None, None)
k = GLib.MainContext.default(); rok = time.monotonic() + 3
while time.monotonic() < rok:
    k.iteration(False); time.sleep(0.01)
print(json.dumps(prejeto) if False else __import__("json").dumps(prejeto))
"""


@unittest.skipUnless(shutil.which("dbus-run-session"), "potrebuje dbus-run-session")
class Znacke(unittest.TestCase):
    def test_launcher_entry_in_obvestila(self):
        from core import znacke_programov
        self.assertEqual(znacke_programov.desktop_id("application://signal-desktop.desktop"), "signal-desktop.desktop")
        self.assertEqual(znacke_programov.desktop_id("signal"), "")
        self.assertEqual(znacke_programov.stevilo_iz_lastnosti({"count": 3, "count-visible": True}), 3)
        self.assertEqual(znacke_programov.stevilo_iz_lastnosti({"count": 3, "count-visible": False}), 0)
        self.assertEqual(znacke_programov.stevilo_iz_lastnosti({"urgent": True}), 1)
        self.assertIsNone(znacke_programov.stevilo_iz_lastnosti({"progress": 0.5}))
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
            f.write(ODDAJNIK)
        self.addCleanup(os.unlink, f.name)
        r = subprocess.run(["dbus-run-session", "--", sys.executable, f.name, KOREN], capture_output=True, text=True,
                           timeout=30)
        prejeto = json.loads(r.stdout.strip().splitlines()[-1])
        self.assertIn(["znacka", "primer.desktop", 5], prejeto)
        self.assertIn(["znacka", "primer.desktop", 0], prejeto, "count-visible=false pomeni brez znacke")
        self.assertIn(["opazovalec", True], prejeto)
        # Zasebnost: samo app_name izbranega programa - brez povzetka in besedila, brez obvestil drugih programov.
        self.assertEqual([x for x in prejeto if x[0] == "obvestilo"], [["obvestilo", "Primer"]],
                         "vir 3: en klic Notify izbranega programa, po ustavitvi nic")
        self.assertIn(["ustavljen", True], prejeto)
        self.assertNotIn("Ana", r.stdout + r.stderr, "besedilo obvestila se ne izpise")
        self.assertNotIn("Zivjo", r.stdout + r.stderr)

    def test_pravila_opazovalca_najozja(self):
        from core import znacke_programov
        pravila = znacke_programov.pravila_obvestil(["Viber", "ViberPC", "signal-desktop", "x' ,eavesdrop='true", ""])
        self.assertIn("type='method_call',interface='org.freedesktop.Notifications',member='Notify',arg0='Viber'", pravila)
        self.assertIn("type='method_call',interface='org.freedesktop.Notifications',member='Notify',arg0='viber'", pravila)
        self.assertTrue(all("arg0='" in p for p in pravila), "nikoli opazovanje vseh obvestil")
        self.assertFalse(any("eavesdrop" in p for p in pravila), "ime ne sme razsiriti pravila")
        self.assertEqual(znacke_programov.pravila_obvestil([]), [])


if __name__ == "__main__":
    unittest.main()
