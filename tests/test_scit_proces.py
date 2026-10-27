"""Scit v svojem procesu (core/scit_proces.py, core/scit_odjemalec.py) - 1.0.129, odpornost 20. 10. 2026.

Na testnem PC je zamrznjen Safeer OS ustavil Scit za ~22 s (resolved je presel na usmerjevalnik, oglasi so sli skozi).
Preizkusi: vrata, ki jih drzi varuh, ostanejo odprta, ko proces Scit umre - poizvedba pocaka in jo odgovori nov proces;
vticnica scit.sock sprejme samo dovoljene metode; odjemalec ob nedosegljivem procesu vrne zadnje stanje.
"""
import json
import os
import random
import signal
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import os_scit, scit_odjemalec, scit_proces  # noqa: E402


def poizvedba(ime: str) -> bytes:
    return struct.pack(">HHHHHH", random.getrandbits(16), 0x0100, 1, 0, 0, 0) + b"".join(
        bytes([len(d)]) + d.encode() for d in ime.split(".")) + b"\0" + struct.pack(">HH", 1, 1)


def vprasaj(vrata: int, ime: str, rok: float) -> int:
    """rcode odgovora ali -1 (ni odgovora v roku)."""
    q = poizvedba(ime)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(rok)
        s.sendto(q, ("127.0.0.1", vrata))
        try:
            while True:
                o = s.recv(4096)
                if o[:2] == q[:2]:
                    return o[3] & 0x0F
        except OSError:
            return -1


#: Otrok: razresevalnik na podedovanih vticnicah (kot core/scit_proces), blokira *.oglas.test.
OTROK = r"""
import os, sys, time
sys.path.insert(0, %(koren)r)
from core import os_scit, scit_proces
os_scit.VRATA = (%(vrata)d,)
u, t = scit_proces.podedovane_vticnice(os.environ["SAFEER_SCIT_FDS"])
os_scit.uporabi_podedovane(u, t)
r = os_scit.Razresevalnik(lambda ime: "oglasi" if ime.endswith("oglas.test") else None, lambda: [])
assert r.zazeni() == %(vrata)d
print("pripravljen", flush=True)
time.sleep(120)
"""


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux: vticnice podeduje proces pod varuhom")
class PodedovanaVrata(unittest.TestCase):
    def setUp(self):
        self.u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.u.bind(("127.0.0.1", 0))
        self.vrata = self.u.getsockname()[1]
        self.t = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.t.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.t.bind(("127.0.0.1", self.vrata))
        self.t.listen(16)
        self.otroci = []

    def tearDown(self):
        for p in self.otroci:
            if p.poll() is None:
                p.kill()
            p.wait(5)
            p.stdout.close()
        self.u.close()
        self.t.close()

    def _otrok(self):
        fds = (self.u.fileno(), self.t.fileno())
        okolje = dict(os.environ, SAFEER_SCIT_FDS="%d,%d" % fds)
        p = subprocess.Popen([sys.executable, "-c", OTROK % {"koren": KOREN, "vrata": self.vrata}], env=okolje,
                             pass_fds=fds, stdout=subprocess.PIPE, text=True)
        self.otroci.append(p)
        self.assertEqual(p.stdout.readline().strip(), "pripravljen")
        return p

    def test_sesutje_procesa_ne_zapre_vrat(self):
        prvi = self._otrok()
        self.assertEqual(vprasaj(self.vrata, "x.oglas.test", 2.0), 3)        # NXDOMAIN: blokirano
        os.kill(prvi.pid, signal.SIGKILL)
        prvi.wait(5)
        # Med ponovnim zagonom: poizvedba ne dobi »vrata zaprta« (resolved bi presel na usmerjevalnik), ampak caka.
        izid = []
        nit = threading.Thread(target=lambda: izid.append(vprasaj(self.vrata, "y.oglas.test", 15.0)))
        nit.start()
        time.sleep(0.5)
        self._otrok()
        nit.join(20)
        self.assertEqual(izid, [3], "poizvedba med ponovnim zagonom mora dobiti odgovor novega procesa")

    def test_tuje_vticnice_zavrne(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as drug:
            drug.bind(("127.0.0.1", 0))
            fd_u = os.dup(drug.fileno())
            fd_t = os.dup(self.t.fileno())
            # Vrata niso na seznamu Scita: proces odpre svoje, tujih ne uporabi.
            self.assertIsNone(scit_proces.podedovane_vticnice("%d,%d" % (fd_u, fd_t)))
        self.assertIsNone(scit_proces.podedovane_vticnice("ni,stevilka"))


class Omejitev(unittest.TestCase):
    def test_cez_mejo_zavrze_in_tece_naprej(self):
        sprosti = threading.Event()

        def blokiraj(ime):
            if ime.startswith("pocasi"):
                sprosti.wait(10)
            return "oglasi"
        r = os_scit.Razresevalnik(blokiraj, lambda: [])
        r.NAJVEC_HKRATI = 2
        r._proste = threading.BoundedSemaphore(2)
        with mock.patch.object(os_scit, "VRATA", (0,)), mock.patch.object(os_scit, "NASLOV", "127.0.0.1"):
            u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            u.bind(("127.0.0.1", 0))
            t = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            t.bind(u.getsockname())
            t.listen(4)
            vrata = u.getsockname()[1]
            r._zacni(u, t, vrata)
        try:
            for i in range(5):
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.sendto(poizvedba("pocasi%d.test" % i), ("127.0.0.1", vrata))
            konec = time.monotonic() + 5
            while r.zavrzenih < 3 and time.monotonic() < konec:
                time.sleep(0.05)
            self.assertEqual(r.zavrzenih, 3)
            sprosti.set()
            while r.blokiranih < 2 and time.monotonic() < konec + 5:   # pocasni poizvedbi sprostita mesti
                time.sleep(0.02)
            time.sleep(0.1)
            self.assertEqual(vprasaj(vrata, "hitro.test", 3.0), 3)       # po sprostitvi spet odgovarja
        finally:
            sprosti.set()
            r.ustavi()


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux")
class NasicenjeTcp(unittest.TestCase):
    """Neodvisni pregled 1.0.129: 300 praznih povezav TCP je zasedlo vsa mesta - oglasi brez odgovora (mimo filtra),
    kanarcek brez odgovora (varuh bi Scit zamenjeval do obupa). Zdaj ima TCP svojo mejo in kratek rok za glavo."""

    def setUp(self):
        self.r = os_scit.Razresevalnik(lambda ime: "oglasi" if ime.endswith("oglas.test") else None, lambda: [])
        self.u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.u.bind(("127.0.0.1", 0))
        self.t = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.t.bind(self.u.getsockname())
        self.t.listen(512)
        self.vrata = self.u.getsockname()[1]
        self.r._zacni(self.u, self.t, self.vrata)
        self.odprte = []

    def tearDown(self):
        for s in self.odprte:
            s.close()
        self.r.ustavi()

    def test_prazne_povezave_tcp_ne_utisajo_udp(self):
        for _ in range(300):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            try:
                s.connect(("127.0.0.1", self.vrata))
            except OSError:
                s.close()
                continue
            self.odprte.append(s)
        time.sleep(0.5)
        self.assertEqual(vprasaj(self.vrata, "a.oglas.test", 2.0), 3)
        self.assertTrue(os_scit._odgovori_kanarcku(self.vrata, 1.0))

    def test_kanarcek_mimo_polne_vrste_in_brez_stetja(self):
        while self.r._proste.acquire(blocking=False):      # vsa mesta UDP zasedena
            pass
        try:
            self.assertTrue(os_scit._odgovori_kanarcku(self.vrata, 1.0))
            self.assertEqual(self.r.poizvedb, 0)           # utrip vsako sekundo ne napihne statistike
        finally:
            for _ in range(self.r.NAJVEC_HKRATI):
                self.r._proste.release()


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux: posix_spawn")
class VarhovaPot(unittest.TestCase):
    """Pot, po kateri vrata res pridejo do Scita: varuh_procesov.Otrok (posix_spawn DUP2) in VrataScita."""

    def test_otrok_dobi_vticnici_kot_3_in_4(self):
        from core import varuh_procesov as vp
        u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        u.bind(("127.0.0.1", 0))
        t = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        t.bind(u.getsockname())
        izhod = tempfile.TemporaryFile()
        try:
            koda = "import socket; print([socket.socket(fileno=f).getsockname()[1] for f in (3, 4)])"
            o = vp.Otrok([sys.executable, "-c", koda], dict(os.environ), izhod.fileno(), 0, (u.fileno(), t.fileno()))
            self.assertEqual(o.wait(20), 0)
            izhod.seek(0)
            self.assertEqual(izhod.read().decode().strip(), str([u.getsockname()[1]] * 2))
        finally:
            u.close()
            t.close()
            izhod.close()

    def test_po_obupu_vrata_znova_odpre(self):
        from core import varuh_procesov as vp
        odprte = []

        def odpri():
            u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            t = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            odprte.append((u, t))
            return (u, t)
        vrata = vp.VrataScita(KOREN, sys.executable, odpri=odpri)
        p = vp.Proces("safeer-scit", ["/bin/true"], {}, zamrznitev_s=8, zagon_s=45, storitev=True,
                      ob_obupu=vrata.ob_obupu, pred_zagonom=vrata.pred_zagonom, obup_premor_s=300)
        try:
            p.pred_zagonom(p)
            self.assertEqual(p.okolje["SAFEER_SCIT_FDS"], "3,4")
            with mock.patch("subprocess.run") as run:
                p.ob_obupu(p)
            self.assertIn("--pospravi", run.call_args[0][0])
            self.assertTrue(odprte[0][0]._closed and odprte[0][1]._closed)     # resolved takoj na usmerjevalnik
            self.assertNotIn("SAFEER_SCIT_FDS", p.okolje)
            p.pred_zagonom(p)                              # »Zazeni znova« ali nov poskus po premoru
            self.assertEqual(len(odprte), 2)
            self.assertEqual(p.podedovani, (odprte[1][0].fileno(), odprte[1][1].fileno()))
            self.assertEqual(p.okolje["SAFEER_SCIT_FDS"], "3,4")
        finally:
            for u, t in odprte:
                u.close()
                t.close()

    def test_obup_scita_ni_trajen(self):
        from core import varuh_procesov as vp
        ura = [1000.0]
        p = vp.Proces("safeer-scit", ["/bin/true"], {}, zamrznitev_s=8, zagon_s=45, storitev=True, obup_premor_s=300)
        v = vp.Varuh([p], tempfile.mkdtemp(), ura=lambda: ura[0], dnevnik=lambda _b: None)
        try:
            for _ in range(vp.NAJVEC_NAPAK):
                v._napaka(p, "preizkus")
            self.assertTrue(p.obupal)
            with mock.patch.object(v, "_zazeni") as zazeni, mock.patch.object(vp, "zaslon_na_voljo", lambda *_a: True):
                ura[0] += 299
                v.korak()
                zazeni.assert_not_called()
                ura[0] += 2
                v.korak()
                zazeni.assert_called_once_with(p)
            self.assertFalse(p.obupal)
        finally:
            v.pospravi()

    def test_podedovane_ne_zapre_tujih_opisnikov(self):
        """Po obupu varuh fd 3/4 ni vec dal, na 3 pa je bila vticnica obvestil: prej jo je ovil, fd 4 ni obstajal, in
        ob pospravljanju je zaprl tujo vticnico - READY in utrip nista vec prisla do varuha."""
        import gc
        obvestila = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        r, w = os.pipe()
        os.close(w)                                        # neveljaven opisnik
        try:
            self.assertIsNone(scit_proces.podedovane_vticnice("%d,%d" % (obvestila.fileno(), w)))
            gc.collect()
            os.fstat(obvestila.fileno())                   # se odprta
            self.assertIsNone(scit_proces.podedovane_vticnice("%d,%d" % (r, r)))
            os.fstat(r)
        finally:
            obvestila.close()
            os.close(r)


class LaznScit:
    def __init__(self):
        self.klici = []

    def stanje(self):
        return {"vklop": True, "naprej": "quad9", "naprejPoMeri": "", "nesifrirano": True, "twitchOglasi": False}

    def stanje_pulta(self):
        return {"vklop": True, "blokiranih": 7}

    def nastavi(self, vklop):
        self.klici.append(("nastavi", vklop))
        return {"vklop": vklop}

    def nastavi_naprej(self, izbira, po_meri):
        self.klici.append(("naprej", izbira, po_meri))
        return dict(self.stanje(), naprej=izbira)

    def dovoli(self, domena, dovoli):
        return {}

    def premor(self, minut):
        self.klici.append(("premor", minut))
        return {"premor": minut}

    def nastavi_twitch(self, vklop):
        return {"twitchOglasi": vklop}


class Shramba:
    def __init__(self):
        self.podatki = {"scit": False}
        self.osvezeno = 0

    def get(self, k, privzeto=None):
        return self.podatki.get(k, privzeto)

    def osvezi(self):
        self.osvezeno += 1


@unittest.skipUnless(hasattr(socket, "AF_UNIX") and hasattr(socket, "SO_PEERCRED"), "vticnica UNIX")
class Vticnica(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.pot = os.path.join(self.mapa, "scit.sock")
        self.scit = LaznScit()
        self.streznik = scit_proces.Streznik(self.scit, self.pot)
        threading.Thread(target=self.streznik.tek, daemon=True).start()

    def tearDown(self):
        self.streznik.vtic.close()
        os_scit.zunanje_nesifrirano = None

    def test_pravice_vticnice(self):
        self.assertEqual(os.stat(self.pot).st_mode & 0o777, 0o600)

    def test_odjemalec_klice_metode(self):
        shramba = Shramba()
        o = scit_odjemalec.ScitOdjemalec(shramba, self.pot)
        self.assertTrue(o.stanje()["vklop"])
        self.assertEqual(o.naprej(), ("quad9", ""))
        self.assertFalse(o.twitch_brez_oglasov())
        self.assertTrue(os_scit.nesifrirano_v_procesu())          # Splet vidi stanje Scita iz drugega procesa
        self.assertEqual(o.nastavi(True)["vklop"], True)
        self.assertEqual(shramba.osvezeno, 1)                      # kljuce, ki jih je zapisal Scit, prevzame
        o.premor(True)                                             # bool ni stevilo minut
        self.assertEqual(self.scit.klici[-1], ("premor", 0))
        self.assertEqual(o.stanje_pulta()["blokiranih"], 7)
        self.assertEqual(o.stanje_pulta(preveri=False)["blokiranih"], 7)   # glavna nit: brez klica
        self.assertFalse(o.razlog_svez())

    def test_samo_dovoljene_metode(self):
        def poslji(besedilo):
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                s.connect(self.pot)
                s.sendall(besedilo + b"\n")
                return json.loads(s.makefile("rb").readline())
        self.assertEqual(poslji(b'{"m": "koncaj"}'), {"napaka": "zahteva"})
        self.assertEqual(poslji(b'{"m": "__class__"}'), {"napaka": "zahteva"})
        self.assertEqual(poslji(b"ni json"), {"napaka": "zahteva"})
        self.assertEqual(poslji(b'{"m": "nastavi", "a": {"rm": 1}}'), {"napaka": "argumenti"})
        self.assertEqual(poslji(b'{"m": "nastavi", "a": [1]}'), {"napaka": "zahteva"})
        self.assertEqual(poslji(b'{"m": "stanje_pulta"}'), {"ok": {"vklop": True, "blokiranih": 7}})

    def test_tuj_uporabnik_ne_dobi_odgovora(self):
        tuj = os.getuid() + 1
        with mock.patch.object(scit_proces.os, "getuid", lambda: tuj):
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(5)
                s.connect(self.pot)
                try:
                    s.sendall(b'{"m": "stanje"}\n')
                    odgovor = s.recv(100)
                except (ConnectionResetError, BrokenPipeError):   # streznik zapre brez branja zahteve (CI 27. 10.: EPIPE)
                    odgovor = b""
                self.assertEqual(odgovor, b"")


class OdjemalecBrezProcesa(unittest.TestCase):
    def tearDown(self):
        os_scit.zunanje_nesifrirano = None

    def test_mrtev_proces_ni_prikazan_kot_zascita(self):
        """Proces Scit ne odgovori (ponovni zagon ali obup varuha): stanje NE sme kazati »deluje« (pregled 1.0.129)."""
        shramba = Shramba()
        shramba.podatki.update(scit=True, scit_naprej="mullvad")
        o = scit_odjemalec.ScitOdjemalec(shramba, os.path.join(tempfile.mkdtemp(), "ni.sock"))
        o._stanje = {"vklop": True, "tece": True, "napaka": "", "blokiranih": 3, "nesifrirano": True}
        o._cas = time.monotonic()
        for s in (o.stanje(), o.stanje_pulta(), o.nastavi(False), o.stanje_pulta(preveri=False)):
            self.assertFalse(s["tece"])
            self.assertEqual(s["napaka"], "proces")
            self.assertTrue(s["vklop"])                   # uporabnikova nastavitev ostane
        self.assertFalse(os_scit.nesifrirano_v_procesu())
        o.koncaj()                                        # konec Safeer OS Scita ne ustavi
        from core import pladenj_sni
        self.assertEqual(pladenj_sni.vrsta_scita(o.stanje_pulta(preveri=False)), "napaka")

    def test_nesifrirano_samo_iz_svezega_stanja(self):
        o = scit_odjemalec.ScitOdjemalec(Shramba(), os.path.join(tempfile.mkdtemp(), "ni.sock"))
        o._stanje = {"nesifrirano": True}
        o._cas = time.monotonic()
        self.assertTrue(os_scit.nesifrirano_v_procesu())
        o._cas = time.monotonic() - 3600                  # DoH je medtem spet delal: staro stanje ne velja
        self.assertFalse(os_scit.nesifrirano_v_procesu())


class StanjePulta(unittest.TestCase):
    def test_hitro_stanje_ima_nesifrirano_in_vrata(self):
        scit = os_scit.Scit(Shramba(), mapa=tempfile.mkdtemp())
        scit._razlog = (time.monotonic(), "")
        s = scit.stanje_pulta(preveri=False)
        self.assertIn("nesifrirano", s)
        self.assertIn("vrata", s)

    def test_splet_dobi_vrata_scita_takoj(self):
        """Splet v Safeer OS ne sme prvega imena filtrirati sam (svoji seznami v pomnilniku), ko Scit tece drugje."""
        from core import doh_proxy
        o = scit_odjemalec.ScitOdjemalec(Shramba(), os.path.join(tempfile.mkdtemp(), "ni.sock"))
        try:
            with mock.patch.object(doh_proxy, "_scit_vrata", (0.0, 0)):
                o._stanje_iz({"tece": True, "vrata": 5355})
                self.assertEqual(doh_proxy.sistemski_scit_vrata(), 5355)
        finally:
            os_scit.zunanje_nesifrirano = None

if __name__ == "__main__":
    unittest.main()


def test_proces_scita_nastavi_nas_webkit_pred_vsem():
    """Pomocnik (pregled 1.0.129): proces Scit je tekel brez zasebni_webkit.nastavi - DoH naprej je odpovedal brez
    gir1.2-soup-3.0 (imena nesifrirano usmerjevalniku) ali tekel na sistemskem libsoup. Klic mora biti pred vticnicami
    in uvozom gi."""
    from unittest import mock
    from core import scit_proces, zasebni_webkit

    class Prvi(Exception):
        pass
    with mock.patch.object(zasebni_webkit, "nastavi", side_effect=Prvi) as nastavi, \
            mock.patch.object(scit_proces, "podedovane_vticnice", side_effect=AssertionError("vticnice pred WebKitom")):
        try:
            scit_proces.main([])
        except Prvi:
            pass
    nastavi.assert_called_once_with(scit_proces.KOREN_PROGRAMA)
    assert os.path.isfile(os.path.join(scit_proces.KOREN_PROGRAMA, "core", "scit_proces.py"))
