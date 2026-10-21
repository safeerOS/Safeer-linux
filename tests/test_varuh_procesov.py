"""Varuh procesov (core/varuh_procesov.py): sesutje, zamrznitev, omejitev ponovnih zagonov, pomnilnik, konec seje.

Lastnik, 18. 10. 2026 (moznost B): lupina namizja in Safeer OS tecejo vsak v svojem procesu, varuh je tretji. Tu z
majhnimi pravimi otroki (Python, protokol sd_notify) in kratkimi roki preverimo pravila varuha; zive poskuse z
lupino in Safeer OS ima tests/test_lupina_locena.py."""
import json
import os
import select
import signal
import socket
import struct
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
        if vedenje[0] == "zazeni" and not globals().get("poslano_zazeni"):
            pid = v.zazeni_program([sys.executable, "-c", "import time; time.sleep(10)"])
            with open(os.environ.get("ZASTAVICA", "/nic"), "w") as f:
                f.write(str(pid or -1))
            globals()["poslano_zazeni"] = True
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

    def test_zanka_spi_do_roka(self):
        """19. 10. 2026: zanka se ne zbuja vec vsakih 0,5 s - spi do najblizjega roka (utrip + meja zamrznitve, SIGKILL,
        ponovni zagon, meritev pomnilnika); obvestila in SIGCHLD jo zbudijo prej."""
        ura = [1000.0]
        lup = self.proces("lupina", zamrznitev_s=20, zagon_s=60)
        os_ = self.proces("os", zamrznitev_s=30, zagon_s=120, glavni=True)
        v = self.zazeni(lup, os_)
        v.ura = lambda: ura[0]
        self.assertEqual(v.do_roka(), 0.0)                       # nihce ne tece: zagon takoj
        v.korak()
        self.assertTrue(lup.tece() and os_.tece())
        self.assertAlmostEqual(v.do_roka(), vp.POMNILNIK_VSAKIH_S)  # meritev pomnilnika je najblizja
        v._zadnja_meritev = ura[0] + 100
        self.assertAlmostEqual(v.do_roka(), vp.NAJVEC_SPANJE_S)     # najdaljse spanje
        with mock.patch.object(vp, "NAJVEC_SPANJE_S", 1000.0):
            self.assertAlmostEqual(v.do_roka(), 60.05, places=2)    # zagon lupine (60 s brez READY)
            lup.pripravljen = os_.pripravljen = True
            lup.zadnji_utrip = ura[0] - 5
            self.assertAlmostEqual(v.do_roka(), 15.05, places=2)    # 20 s brez utripa = zamrznitev
        lup.zadnji_utrip = ura[0] - 19
        self.assertAlmostEqual(v.do_roka(), 1.05, places=2)      # zamrznitev lupine cez 1 s
        lup.zahteva, lup.kill_ob = "zamrznitev", ura[0] + 0.5
        self.assertAlmostEqual(v.do_roka(), 0.5, places=2)       # SIGKILL po SIGABRT
        lup.zahteva, lup.kill_ob = "", 0.0
        lup.zadnji_utrip = ura[0] - 25
        self.assertEqual(v.do_roka(), 0.0)                        # rok je ze potekel

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

    def test_zagon_prek_varuha_oom_in_seja(self):
        """Otrok varuha z oom_score_adj=200 prek varuha zazene program, ki dobi oom=0, loceno sejo in ne umre ob restartu."""
        zastavica = os.path.join(self.mapa, "znova")
        os_ = self.proces("os", "zazeni", glavni=True, oom=200)
        self.zazeni(os_)
        ok, _ = self.teci(lambda: os.path.exists(zastavica), 15)
        self.assertTrue(ok, self.dnevnik)
        with open(zastavica) as f:
            grandchild_pid = int(f.read().strip())
        self.assertGreater(grandchild_pid, 0)
        try:
            # Stars (safeer-os otrok) ima oom_score_adj 200
            with open("/proc/%d/oom_score_adj" % os_.pid) as f:
                self.assertEqual(f.read().strip(), "200")
            # Zagnani program pa ima oom_score_adj 0 (podedovano od varuha)
            with open("/proc/%d/oom_score_adj" % grandchild_pid) as f:
                self.assertEqual(f.read().strip(), "0")
            # Program je v svoji seji (setsid)
            self.assertEqual(os.getsid(grandchild_pid), grandchild_pid)
            # PPID je varuh (zagnan zunaj drevesa safeer-os)
            with open("/proc/%d/stat" % grandchild_pid) as f:
                ppid = int(f.read().split()[3])
                self.assertNotEqual(ppid, os_.pid)
                self.assertEqual(ppid, os.getpid())
            # Ob sesutju Safeer OS program tece naprej
            os.kill(os_.pid, signal.SIGKILL)
            self.teci(lambda: os_.zagonov >= 2, 10)
            self.assertTrue(os.path.exists("/proc/%d" % grandchild_pid))
        finally:
            try:
                os.kill(grandchild_pid, signal.SIGKILL)
            except OSError:
                pass

    def test_zagon_nadomestna_pot_brez_varuha(self):
        """Brez NOTIFY_SOCKET zazeni_program vrne None (klicatelj zazene po starem)."""
        with mock.patch.dict(vp._obvestila, {"vtic": None, "naslov": None, "prebrano": False, "utrip": 0}), \
                mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NOTIFY_SOCKET", None)
            self.assertIsNone(vp.zazeni_program(["ls"]))

    def test_zagon_tuj_proces_zavrnjen(self):
        """Zahteve zunanjega procesa (ki ni otrok varuha) varuh zavrne brez zagona."""
        os_ = self.proces("os", glavni=True)
        self.zazeni(os_)
        self.teci(lambda: os_.pripravljen)
        import array
        c1, c2 = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM | socket.SOCK_CLOEXEC)
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            anc = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", [c2.fileno()]))]
            s.sendmsg([b"SAFEER_ZAZENI=1\n"], anc, 0, self.varuh.pot_vtic)
            s.close()
            c2.close()
            # Poskusi poslati ukaz
            c1.settimeout(0.5)
            telo = json.dumps({"ukaz": ["sleep", "10"]}).encode("utf-8")
            try:
                c1.sendall(struct.pack(">I", len(telo)) + telo)
                odg = c1.recv(4)
                # Ker varuh zavrne proces in zapre povezavo, odg je prazen
                self.assertEqual(odg, b"")
            except (OSError, socket.timeout):
                pass
        finally:
            c1.close()


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
        with mock.patch.object(vp, "lupina_mogoca", lambda _k: True), \
                mock.patch.object(vp, "scit_v_procesu", lambda: False):
            procesi = vp.sestavi(["--delovna"], KOREN, sys.executable, mapa)
        lupina, os_ = procesi
        self.assertTrue(os_.glavni and not lupina.glavni)
        self.assertEqual(os_.okolje["SAFEER_LUPINA_VTIC"], lupina.okolje["SAFEER_LUPINA_VTIC"])
        self.assertEqual(os_.okolje["SAFEER_OS_NADZOR"], str(os.getpid()))
        self.assertTrue(os_.argv[-1] == "--delovna" and os_.argv[1].endswith("safeer_os.py"))
        self.assertTrue(lupina.argv[1].endswith(os.path.join("core", "lupina_proces.py")))
        self.assertEqual(os_.oom, vp.OOM_OS)
        with mock.patch.object(vp, "lupina_mogoca", lambda _k: False), \
                mock.patch.object(vp, "scit_v_procesu", lambda: False):
            procesi = vp.sestavi(["--delovna"], KOREN, sys.executable, mapa)
        self.assertEqual([p.ime for p in procesi], ["safeer-os"])
        self.assertNotIn("SAFEER_LUPINA_VTIC", procesi[0].okolje)

    def test_scit_v_svojem_procesu(self):
        """1.0.129: Scit je prvi proces; varuh drzi vticnici na 127.0.0.1 in ju da otroku kot fd 3 in 4."""
        mapa = tempfile.mkdtemp()
        vticnice = []
        with mock.patch.object(vp, "lupina_mogoca", lambda _k: False), \
                mock.patch.object(vp, "vticnici_scita", lambda: tuple(vticnice)):
            u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            u.bind(("127.0.0.1", 0))
            t = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            t.bind(("127.0.0.1", 0))
            vticnice[:] = [u, t]
            procesi = vp.sestavi(["--delovna"], KOREN, sys.executable, mapa)
            scit, os_ = procesi
            scit.pred_zagonom(scit)                    # vrata odpre tik pred zagonom
        try:
            self.assertEqual(scit.ime, "safeer-scit")
            self.assertTrue(scit.storitev and not scit.glavni and os_.glavni)
            self.assertTrue(scit.argv[1].endswith(os.path.join("core", "scit_proces.py")))
            self.assertEqual(scit.podedovani, (u.fileno(), t.fileno()))
            self.assertEqual(scit.okolje["SAFEER_SCIT_FDS"], "3,4")
            self.assertEqual(scit.obup_premor_s, vp.OBUP_SCIT_PREMOR_S)
            self.assertEqual(scit.okolje["SAFEER_SCIT_VTIC"], os_.okolje["SAFEER_SCIT_VTIC"])
            self.assertEqual(scit.zamrznitev_s, vp.ZAMRZNITEV_SCIT_S)
            self.assertIsNotNone(scit.ob_obupu)
            with mock.patch.dict(os.environ, {"SAFEER_SCIT_PROCES": "0"}), \
                    mock.patch.object(vp, "lupina_mogoca", lambda _k: False):
                self.assertEqual([p.ime for p in vp.sestavi(["--delovna"], KOREN, sys.executable, mapa)], ["safeer-os"])
        finally:
            u.close()
            t.close()

    def test_vticnici_scita(self):
        vticnici = vp.vticnici_scita()
        if vticnici is None:
            self.skipTest("vsa vrata Scita so zasedena")
        u, t = vticnici
        try:
            self.assertEqual(u.getsockname(), t.getsockname())
            self.assertIn(u.getsockname()[1], (5354, 5355, 5356, 5357))
            self.assertTrue(u.fileno() >= 10 and t.fileno() >= 10)
            self.assertFalse(u.get_inheritable() or t.get_inheritable())   # lupina in Safeer OS ju ne dobita
        finally:
            u.close()
            t.close()

    def test_brez_lupine_ne_ustavi_scita(self):
        """SAFEER_BREZ_LUPINE izkljuci lupino, ne Scita (storitev)."""
        mapa = tempfile.mkdtemp()
        scit = vp.Proces("safeer-scit", ["/bin/true"], zamrznitev_s=8, zagon_s=45, storitev=True)
        lupina = vp.Proces("safeer-lupina", ["/bin/true"], zamrznitev_s=20, zagon_s=60)
        os_ = vp.Proces("safeer-os", ["/bin/true"], zamrznitev_s=30, zagon_s=120, glavni=True)
        v = vp.Varuh([scit, lupina, os_], mapa, dnevnik=lambda _b: None)
        try:
            os_.popen = mock.Mock(pid=4242, poll=lambda: None)
            podatki = b"SAFEER_BREZ_LUPINE=1"
            pomozni = [(socket.SOL_SOCKET, socket.SCM_CREDENTIALS, struct.pack("3i", 4242, os.getuid(), os.getgid()))]
            v.vtic.close()
            v.vtic = mock.Mock(recvmsg=mock.Mock(side_effect=[(podatki, pomozni, 0, None), BlockingIOError()]))
            v._beri_obvestila()
            self.assertTrue(lupina.izkljucen)
            self.assertFalse(scit.izkljucen)
        finally:
            v.pospravi()

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
        self.assertIn('exec "$PY" -s "$APP_DIR/core/varuh_procesov.py" "$@"', s)
        self.assertIn('export SAFEER_ZAGANJALNIK="$PRG"', s)
        # SAFEER_OS_BREZ_NADZORA (razvoj) ostane pred varuhom, Flatpak preusmeritev tudi.
        self.assertLess(s.index("SAFEER_OS_BREZ_NADZORA:-"), s.index("core/varuh_procesov.py"))
        self.assertLess(s.index('exec flatpak run "$FP_ID"'), s.index("core/varuh_procesov.py"))


class ObvestiloUporabniku(unittest.TestCase):
    """Obup varuha: Notify po vodilu seje (lazni streznik obvestil na zasebnem vodilu), brez notify-send."""

    def test_notify_po_vodilu_seje(self):
        import shutil
        import threading
        try:
            from gi.repository import Gio, GLib
        except Exception:  # noqa: BLE001
            self.skipTest("potrebuje PyGObject")
        if not (shutil.which("dbus-daemon") and shutil.which("gdbus")):
            self.skipTest("potrebuje dbus-daemon in gdbus")
        import subprocess
        from zasebno_vodilo import ZasebnoVodilo
        vodilo = ZasebnoVodilo()                    # ne Gio.TestDBus: ta spreminja okolje procesa (zasebno_vodilo.py)
        self.addCleanup(vodilo.ustavi)
        streznik = vodilo.povezava(Gio)
        self.addCleanup(streznik.close_sync, None)
        info = Gio.DBusNodeInfo.new_for_xml(
            '<node><interface name="org.freedesktop.Notifications"><method name="Notify">'
            '<arg type="s" direction="in"/><arg type="u" direction="in"/><arg type="s" direction="in"/>'
            '<arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="as" direction="in"/>'
            '<arg type="a{sv}" direction="in"/><arg type="i" direction="in"/><arg type="u" direction="out"/></method>'
            '</interface></node>')
        klici = []

        def klic(_v, _p, _pot, _vm, metoda, parametri, k):
            klici.append((metoda, parametri.unpack()))
            k.return_value(GLib.Variant("(u)", (3,)))
        reg = streznik.register_object("/org/freedesktop/Notifications", info.interfaces[0], klic, None, None)
        self.addCleanup(streznik.unregister_object, reg)
        Gio.bus_own_name_on_connection(streznik, "org.freedesktop.Notifications", Gio.BusNameOwnerFlags.NONE,
                                       None, None)
        izid = []
        # gdbus --session dobi naslov zasebnega vodila v svojem okolju; okolja tega procesa ne spreminjamo (setenv med
        # getenv drugih niti je v glibc nedefiniran).
        pravi_zagon = subprocess.run
        with mock.patch("subprocess.run", lambda ukaz, **k: pravi_zagon(ukaz, env=vodilo.okolje(), **k)):
            # gdbus caka na odgovor, streznik odgovarja v glavni zanki tega procesa: klic v svoji niti.
            nit = threading.Thread(target=lambda: izid.append(vp.obvesti_uporabnika("Naslov", "Opis")), daemon=True)
            nit.start()
            kontekst, konec = GLib.MainContext.default(), time.monotonic() + 15
            while nit.is_alive() and time.monotonic() < konec:
                kontekst.iteration(False) or time.sleep(0.01)
            nit.join(1)
        self.assertEqual(izid, [True])
        self.assertEqual(klici, [("Notify", ("Safeer OS", 0, "safeer-os", "Naslov", "Opis", [], {"urgency": 2}, 0))])

    def test_brez_gdbus_ne_poskusa_drugega_programa(self):
        with mock.patch("shutil.which", lambda _i: None), mock.patch("subprocess.run") as zagon:
            self.assertFalse(vp.obvesti_uporabnika("Naslov", "Opis"))
        zagon.assert_not_called()


if __name__ == "__main__":
    unittest.main()
