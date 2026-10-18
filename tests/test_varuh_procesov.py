"""Varuh procesov (core/varuh_procesov.py): sesutje, zamrznitev, omejitev ponovnih zagonov, pomnilnik, konec seje.

Lastnik, 18. 10. 2026 (moznost B): lupina namizja in Safeer OS tecejo vsak v svojem procesu, varuh je tretji. Tu z
majhnimi pravimi otroki (Python, protokol sd_notify) in kratkimi roki preverimo pravila varuha; zive poskuse z
lupino in Safeer OS ima tests/test_lupina_locena.py."""
import json
import os
import select
import signal
import socket
import sys
import tempfile
import textwrap
import time
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import varuh_procesov as vp  # noqa: E402

OTROK = textwrap.dedent("""
    import os, signal, sys, time
    sys.path.insert(0, %r)
    from core import varuh_procesov as v
    vedenje = os.environ.get("VEDENJE", "zdrav").split(":")
    with open(os.environ["ZAPIS"], "a") as f:
        f.write("%%d %%s %%s\\n" %% (os.getpid(), os.environ.get("SAFEER_OBNOVA", "-"),
                                   "NOTIFY" if "NOTIFY_SOCKET" in os.environ else "-"))
    v.obvesti("READY=1")
    if "NOTIFY_SOCKET" in os.environ:
        sys.exit(9)                    # pripravi_obvestila mora odstraniti NOTIFY_SOCKET iz okolja
    zacetek = time.monotonic()
    while True:
        cas = time.monotonic() - zacetek
        if vedenje[0] == "sesuj" and cas >= float(vedenje[1]):
            os.kill(os.getpid(), signal.SIGKILL)
        if vedenje[0] == "izhod" and cas >= float(vedenje[2]):
            sys.exit(int(vedenje[1]))
        if vedenje[0] == "zamrzni" and cas >= float(vedenje[1]):
            time.sleep(3600)
        if vedenje[0] == "spomin":
            globals().setdefault("balast", bytearray(64 * 1024 * 1024))
        if vedenje[0] == "znova" and os.path.exists(os.environ.get("ZASTAVICA", "/nic")) and not globals().get("poslano"):
            v.obvesti("SAFEER_ZNOVA=1")
            globals()["poslano"] = True
        v.obvesti("WATCHDOG=1")
        time.sleep(0.1)
""" % KOREN)


class _Osnova(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-varuh-")
        self.skripta = os.path.join(self.mapa, "otrok.py")
        with open(self.skripta, "w") as f:
            f.write(OTROK)
        self.zapis = os.path.join(self.mapa, "zapis.txt")
        self.dnevnik = []
        self.obupi = []
        self.varuh = None
        self.meminfo = os.path.join(self.mapa, "meminfo")
        self.nastavi_prosto(8000)

    def tearDown(self):
        if self.varuh is not None:
            self.varuh.ustavi_vse()
            self.varuh.pospravi()
        import shutil
        shutil.rmtree(self.mapa, ignore_errors=True)

    def nastavi_prosto(self, mib):
        with open(self.meminfo, "w") as f:
            f.write("MemTotal:       16000000 kB\nMemAvailable:   %d kB\n" % (mib * 1024))

    def proces(self, ime, vedenje="zdrav", glavni=False, **kw):
        nastavitve = dict(zamrznitev_s=1.5, zagon_s=3, ustavi_s=2, zacetni_zamik_s=0.1)
        nastavitve.update(kw)
        return vp.Proces(ime, [sys.executable, self.skripta],
                         {"VEDENJE": vedenje, "ZAPIS": self.zapis, "ZASTAVICA": os.path.join(self.mapa, "znova")},
                         glavni=glavni, **nastavitve)

    def zazeni(self, *procesi):
        self.varuh = vp.Varuh(list(procesi), self.mapa, ob_obupu=self.obupi.append, dnevnik=self.dnevnik.append,
                              meminfo=self.meminfo, okolje_zaslona={})
        return self.varuh

    def teci(self, pogoj, rok=10.0):
        """Korak varuha, dokler ni pogoj izpolnjen. Vrne (izid pogoja, izhodna koda varuha ali None)."""
        konec = time.monotonic() + rok
        while time.monotonic() < konec:
            koda = self.varuh.korak()
            if koda is not None:
                return pogoj(), koda
            if pogoj():
                return True, None
            select.select([self.varuh.vtic], [], [], 0.05)
        return pogoj(), None

    def zagoni(self):
        try:
            with open(self.zapis) as f:
                return [v.split() for v in f.read().splitlines()]
        except OSError:
            return []


class Obvestila(unittest.TestCase):
    def test_obvesti_poslje_in_odstrani_notify_socket(self):
        mapa = tempfile.mkdtemp()
        pot = os.path.join(mapa, "n.sock")
        s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s.bind(pot)
        s.settimeout(2)
        with mock.patch.dict(os.environ, {"NOTIFY_SOCKET": pot}), \
                mock.patch.dict(vp._obvestila, {"vtic": None, "naslov": None, "prebrano": False, "utrip": 0}):
            self.assertTrue(vp.obvesti("READY=1", "STATUS=x"))
            self.assertNotIn("NOTIFY_SOCKET", os.environ)
            self.assertEqual(s.recv(100), b"READY=1\nSTATUS=x")
        s.close()

    def test_brez_varuha_nic(self):
        with mock.patch.dict(os.environ, {}, clear=False), \
                mock.patch.dict(vp._obvestila, {"vtic": None, "naslov": None, "prebrano": False, "utrip": 0}):
            os.environ.pop("NOTIFY_SOCKET", None)
            self.assertFalse(vp.obvesti("WATCHDOG=1"))
            self.assertFalse(vp.pod_varuhom())


class Pravila(_Osnova):
    def test_sesutje_znova_zazene_samo_tega(self):
        lupina, os_ = self.proces("lupina"), self.proces("os", "sesuj:0.6", glavni=True)
        self.zazeni(lupina, os_)
        ok, _ = self.teci(lambda: lupina.pripravljen and os_.zagonov >= 2 and os_.pripravljen)
        self.assertTrue(ok, self.dnevnik)
        self.assertEqual(lupina.zagonov, 1, "lupina mora ostati ista")
        self.assertTrue(any("signal 9" in v for v in self.dnevnik), self.dnevnik)

    def test_obnova_stanja_brez_zanke(self):
        """Prvi ponovni zagon obnovi stanje prejsnjega procesa (SAFEER_OBNOVA = njegov PID); ce obnovljeni proces pade
        prej kot v OBNOVA_PO_S, je naslednji zagon brez obnove (kriva je lahko obnovljena stran)."""
        os_ = self.proces("os", "sesuj:0.3", glavni=True)
        self.zazeni(os_)
        ok, _ = self.teci(lambda: len(self.zagoni()) >= 3, 15)
        self.assertTrue(ok, self.dnevnik)
        z = self.zagoni()
        self.assertEqual(z[0][1], "-")
        self.assertEqual(z[1][1], z[0][0], "obnova stanja prav prejsnjega procesa")
        self.assertEqual(z[2][1], "-", "obnovljeni je padel takoj: brez obnove")

    def test_zamrznitev_sigabrt_nato_znova(self):
        os_ = self.proces("os", "zamrzni:0.3", glavni=True)
        self.zazeni(os_)
        zacetek = time.monotonic()
        ok, _ = self.teci(lambda: os_.zagonov >= 2, 15)
        self.assertTrue(ok, self.dnevnik)
        self.assertTrue(any("se ne odziva" in v and "SIGABRT" in v for v in self.dnevnik), self.dnevnik)
        self.assertTrue(any("signal 6" in v for v in self.dnevnik), self.dnevnik)
        self.assertLess(time.monotonic() - zacetek, 6)

    def test_ustavljen_proces_takoj_sigkill(self):
        os_ = self.proces("os", glavni=True)
        self.zazeni(os_)
        self.teci(lambda: os_.pripravljen)
        stari = os_.pid
        os.kill(stari, signal.SIGSTOP)
        ok, _ = self.teci(lambda: os_.zagonov >= 2, 10)
        self.assertTrue(ok, self.dnevnik)
        self.assertTrue(any("SIGKILL" in v for v in self.dnevnik), self.dnevnik)
        self.assertFalse(os.path.exists("/proc/%d/status" % stari) and vp.ustavljen(stari))

    def test_po_petih_napakah_odneha_in_pove(self):
        os_ = self.proces("os", "sesuj:0.05", glavni=True)
        lupina = self.proces("lupina")
        self.zazeni(lupina, os_)
        ok, _ = self.teci(lambda: os_.obupal, 30)
        self.assertTrue(ok, self.dnevnik)
        self.assertEqual(os_.zagonov, vp.NAJVEC_NAPAK)
        self.assertEqual(self.obupi, [os_])
        self.teci(lambda: False, 1.0)
        self.assertEqual(os_.zagonov, vp.NAJVEC_NAPAK, "po obupu ni vec zagonov (brez zanke)")
        self.assertTrue(lupina.tece(), "namizje ostane")
        with open(self.varuh.pot_stanja) as f:
            stanje = json.load(f)
        self.assertEqual(stanje["procesi"]["os"]["stanje"], "obupal")
        self.assertEqual(stanje["procesi"]["lupina"]["stanje"], "tece")
        # Zamiki rastejo: 0.1, 0.2, 0.4, 0.8 s
        zamiki = [float(v.split("znova cez ")[1].split(" s")[0]) for v in self.dnevnik if "znova cez" in v]
        self.assertEqual(zamiki, [0.1, 0.2, 0.4, 0.8])

    def test_gumb_zazeni_znova_iz_lupine(self):
        os_ = self.proces("os", "sesuj:0.05", glavni=True)
        lupina = self.proces("lupina", "znova")
        self.zazeni(lupina, os_)
        ok, _ = self.teci(lambda: os_.obupal, 30)
        self.assertTrue(ok)
        os_.okolje["VEDENJE"] = "zdrav"
        open(os.path.join(self.mapa, "znova"), "w").close()      # lupina: gumb »Zazeni znova«
        ok, _ = self.teci(lambda: not os_.obupal and os_.pripravljen, 10)
        self.assertTrue(ok, self.dnevnik)
        self.assertTrue(any("ponoven poskus" in v for v in self.dnevnik))

    def test_tuj_proces_ne_more_zahtevati_ponovnega_poskusa(self):
        os_ = self.proces("os", "sesuj:0.05", glavni=True)
        self.zazeni(os_)
        self.teci(lambda: os_.obupal, 30)
        s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        s.sendto(b"SAFEER_ZNOVA=1", self.varuh.pot_vtic)      # ta proces (preizkus) ni otrok varuha
        s.close()
        self.teci(lambda: False, 0.5)
        self.assertTrue(os_.obupal)

    def test_konec_safeer_os_konca_namizje(self):
        os_ = self.proces("os", "izhod:0:0.5", glavni=True)
        lupina = self.proces("lupina")
        self.zazeni(lupina, os_)
        ok, koda = self.teci(lambda: False, 10)
        self.assertEqual(koda, 0)
        self.varuh.ustavi_vse()
        self.assertFalse(lupina.tece())

    def test_nova_razlicica(self):
        os_ = self.proces("os", "izhod:75:0.5", glavni=True)
        self.zazeni(os_)
        _ok, koda = self.teci(lambda: False, 10)
        self.assertEqual(koda, vp.KODA_ZNOVA)

    def test_lupina_z_izhodom_0_se_vrne(self):
        lupina = self.proces("lupina", "izhod:0:0.3")
        os_ = self.proces("os", glavni=True)
        self.zazeni(lupina, os_)
        ok, koda = self.teci(lambda: lupina.zagonov >= 2, 10)
        self.assertTrue(ok)
        self.assertIsNone(koda)

    def test_caka_na_pomnilnik(self):
        self.nastavi_prosto(100)
        os_ = self.proces("os", glavni=True, prost_mib=300)
        self.zazeni(os_)
        self.teci(lambda: False, 0.5)
        self.assertIsNone(os_.popen)
        self.assertEqual(os_.stanje(), "pomnilnik")
        self.assertEqual(len([v for v in self.dnevnik if "caka na pomnilnik" in v]), 1, "en zapis, ne zanka")
        self.nastavi_prosto(2000)
        ok, _ = self.teci(lambda: os_.pripravljen, 6)
        self.assertTrue(ok)

    def test_meja_pomnilnika_miren_ponovni_zagon(self):
        os_ = self.proces("os", "spomin", glavni=True, meja_mib=40)
        self.zazeni(os_)
        with mock.patch.object(vp, "POMNILNIK_VSAKIH_S", 0.2):
            ok, koda = self.teci(lambda: os_.zagonov >= 2, 15)
        self.assertTrue(ok, self.dnevnik)
        self.assertIsNone(koda, "SIGTERM varuha ni konec seje")
        self.assertTrue(any("meja 40 MiB" in v for v in self.dnevnik))

    def test_brez_zaslona_varuh_konca(self):
        os_ = self.proces("os", "sesuj:0.3", glavni=True)
        self.zazeni(os_)
        self.teci(lambda: os_.pripravljen)
        self.varuh.okolje_zaslona = {"DISPLAY": ":987"}
        _ok, koda = self.teci(lambda: False, 5)
        self.assertEqual(koda, 0)

    def test_oom_score(self):
        os_ = self.proces("os", glavni=True, oom=200)
        self.zazeni(os_)
        self.teci(lambda: os_.pripravljen)
        with open("/proc/%d/oom_score_adj" % os_.pid) as f:
            self.assertEqual(f.read().strip(), "200")

    def test_mapa_in_vticnica_samo_za_uporabnika(self):
        self.zazeni(self.proces("os", glavni=True))
        self.assertEqual(os.stat(self.varuh.pot_vtic).st_mode & 0o777, 0o600)
        self.teci(lambda: os.path.exists(self.varuh.pot_stanja))
        self.assertEqual(os.stat(self.varuh.pot_stanja).st_mode & 0o777, 0o600)


class Pomozne(unittest.TestCase):
    def test_zaslon(self):
        self.assertTrue(vp.zaslon_na_voljo({}))
        self.assertFalse(vp.zaslon_na_voljo({"DISPLAY": ":987"}))
        mapa = tempfile.mkdtemp()
        open(os.path.join(mapa, "wayland-1"), "w").close()
        self.assertTrue(vp.zaslon_na_voljo({"WAYLAND_DISPLAY": "wayland-1", "XDG_RUNTIME_DIR": mapa}))
        self.assertFalse(vp.zaslon_na_voljo({"WAYLAND_DISPLAY": "wayland-2", "XDG_RUNTIME_DIR": mapa}))

    def test_jezik(self):
        self.assertEqual(vp.jezik({"LANG": "sl_SI.UTF-8", "XDG_CONFIG_HOME": "/nic"}), "sl")
        self.assertEqual(vp.jezik({"LANGUAGE": "de:en", "XDG_CONFIG_HOME": "/nic"}), "de")
        self.assertEqual(vp.jezik({"LANG": "ja_JP.UTF-8", "XDG_CONFIG_HOME": "/nic"}), "en")
        for b in vp.BESEDILA.values():
            self.assertEqual(set(b), set(vp.BESEDILA["sl"]))

    def test_na_waylandu_brez_locene_lupine(self):
        with mock.patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-0", "XDG_SESSION_TYPE": "wayland"}):
            self.assertFalse(vp.lupina_mogoca(KOREN))
        with mock.patch.dict(os.environ, {"SAFEER_LOCENA_LUPINA": "0"}):
            self.assertFalse(vp.lupina_mogoca(KOREN))
        with mock.patch.dict(os.environ, {"SAFEER_LUPINA": "html"}):
            self.assertFalse(vp.lupina_mogoca(KOREN))

    def test_sestava_procesov(self):
        mapa = tempfile.mkdtemp()
        with mock.patch.object(vp, "lupina_mogoca", lambda _k: True):
            procesi = vp.sestavi(["--delovna"], KOREN, sys.executable, mapa)
        lupina, os_ = procesi
        self.assertTrue(os_.glavni and not lupina.glavni)
        self.assertEqual(os_.okolje["SAFEER_LUPINA_VTIC"], lupina.okolje["SAFEER_LUPINA_VTIC"])
        self.assertEqual(os_.okolje["SAFEER_OS_NADZOR"], str(os.getpid()))
        self.assertTrue(os_.argv[-1] == "--delovna" and os_.argv[1].endswith("safeer_os.py"))
        self.assertTrue(lupina.argv[1].endswith(os.path.join("core", "lupina_proces.py")))
        self.assertEqual(os_.oom, vp.OOM_OS)
        with mock.patch.object(vp, "lupina_mogoca", lambda _k: False):
            procesi = vp.sestavi(["--delovna"], KOREN, sys.executable, mapa)
        self.assertEqual([p.ime for p in procesi], ["safeer-os"])
        self.assertNotIn("SAFEER_LUPINA_VTIC", procesi[0].okolje)

    def test_varuh_je_majhen(self):
        """Varuh ne uvaza subprocess, json, typing, Gtk ali Qt ob zagonu (izmerjeno: 8,8 MB namesto 15 MB)."""
        import subprocess
        koda = ("import sys; sys.path.insert(0, %r); import core.varuh_procesov as v; v.lupina_mogoca(%r); "
                "print(' '.join(sorted(m for m in ('subprocess', 'json', 'typing', 'gi', 'PySide6', 'hashlib') "
                "if m in sys.modules)))" % (KOREN, KOREN))
        izid = subprocess.run([sys.executable, "-c", koda], capture_output=True, text=True, timeout=30)
        self.assertEqual(izid.stdout.strip(), "", izid.stderr)


class Zaganjalnik(unittest.TestCase):
    def test_delovna_gre_pod_varuha(self):
        with open(os.path.join(KOREN, "packaging", "safeer-os-launcher"), encoding="utf-8") as f:
            s = f.read()
        self.assertIn('exec "$PY" "$APP_DIR/core/varuh_procesov.py" "$@"', s)
        self.assertIn('export SAFEER_ZAGANJALNIK="$PRG"', s)
        # SAFEER_OS_BREZ_NADZORA (razvoj) ostane pred varuhom, Flatpak preusmeritev tudi.
        self.assertLess(s.index("SAFEER_OS_BREZ_NADZORA:-"), s.index("core/varuh_procesov.py"))
        self.assertLess(s.index('exec flatpak run "$FP_ID"'), s.index("core/varuh_procesov.py"))


if __name__ == "__main__":
    unittest.main()
