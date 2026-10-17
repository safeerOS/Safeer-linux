"""Deskriptorji dolgotrajnega procesa se ne kopicijo (Safeer OS, 17. 10. 2026: SIGTRAP po 11,5 h, meja 1024).

Merjeno na zivem procesu: dohodne povezave naprav na Hub (8990) so po eni zahtevi ostale odprte (keep-alive brez
roka), nove pa so prihajale ~1,3 na minuto. Preizkusi stejejo /proc/self/fd pred in po N povezavah na streznike na
127.0.0.1 - stevilo se ne sme povecevati.
"""
import http.client
import http.server
import os
import socket
import sys
import threading
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

from core import os_deskriptorji  # noqa: E402


def _fd() -> int:
    return len(os.listdir("/proc/self/fd"))


def _pocakaj(pogoj, rok: float = 5.0) -> bool:
    konec = time.monotonic() + rok
    while time.monotonic() < konec:
        if pogoj():
            return True
        time.sleep(0.02)
    return pogoj()


@unittest.skipUnless(os.path.isdir("/proc/self/fd"), "potrebuje /proc")
class HubProstePovezave(unittest.TestCase):
    """Naprava odpira nove povezave in starih ne zapre: Hub jih ne omejuje po stevilu (lastnik 17. 10. 2026), ampak
    zapre vsako, ki po roku ne poslje nove zahteve."""

    def _streznik(self, rok_s: float = 30.0):
        from core import link_hub_streznik

        class Obravnava(link_hub_streznik._Obravnava):
            ROK_CAKANJA_ZAHTEVE_S = rok_s

            def do_GET(self):
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()

        class Streznik(http.server.ThreadingHTTPServer):
            daemon_threads = True

        s = Streznik(("127.0.0.1", 0), Obravnava)
        s.proste = os_deskriptorji.ProsteZveze()
        threading.Thread(target=s.serve_forever, daemon=True).start()
        self.addCleanup(s.server_close)
        self.addCleanup(s.shutdown)
        return s

    def test_proste_povezave_se_zaprejo_po_roku_brez_omejitve_stevila(self):
        s = self._streznik(rok_s=0.5)
        pred = _fd()
        odjemalci = []
        for _ in range(30):
            c = http.client.HTTPConnection(*s.server_address, timeout=5)
            c.request("GET", "/x")
            r = c.getresponse()
            r.read()
            self.assertEqual(r.status, 204)         # vseh 30 dela - naprave ne omejujemo
            odjemalci.append(c)            # povezava ostane odprta, kot pri napravi, ki je ne zapre
        self.assertEqual(s.proste.zaprtih, 0)
        # Po roku streznik vse tihe povezave zapre: ostanejo samo odjemalceve.
        self.assertTrue(_pocakaj(lambda: s.proste.cakajocih() == 0, rok=5.0))
        self.assertTrue(_pocakaj(lambda: _fd() <= pred + 30 + 2, rok=5.0), (_fd(), pred))
        for c in odjemalci:
            c.close()
        self.assertTrue(_pocakaj(lambda: _fd() <= pred + 1), (_fd(), pred))

    def test_zahteva_na_ohranjeni_povezavi_dela(self):
        s = self._streznik()
        c = http.client.HTTPConnection(*s.server_address, timeout=5)
        for _ in range(10):
            c.request("GET", "/x")
            r = c.getresponse()
            r.read()
            self.assertEqual(r.status, 204)
        self.assertEqual(s.proste.zaprtih, 0)
        c.close()

    def test_tiha_povezava_po_roku_ne_drzi_deskriptorja(self):
        s = self._streznik(rok_s=0.3)
        pred = _fd()
        for _ in range(20):
            v = socket.create_connection(s.server_address, timeout=5)
            v.close()
            v = socket.create_connection(s.server_address, timeout=5)   # odprta, brez zahteve
            self.addCleanup(v.close)
        self.assertTrue(_pocakaj(lambda: _fd() <= pred + 20 + 1, rok=5.0), (_fd(), pred))

    def test_utihnjena_sredi_zahteve_ne_drzi_niti(self):
        """Telefon poslje vrstico zahteve (ali glave in del telesa) in izgubi Wi-Fi: nit se po roku sprosti."""
        from core import link_hub_streznik
        s = self._streznik(rok_s=0.3)
        s.rok_po_rokovanju = None          # kot pravi Hub (link_tls.RokovanjeVNiti)
        koncane = []

        class Obravnava(s.RequestHandlerClass):
            ROK_BRANJA_S = 0.3

            def do_POST(self):
                self._telo()
                koncane.append(1)
                self.send_response(204)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def finish(self):
                koncane.append(0)
                super().finish()
        s.RequestHandlerClass = Obravnava
        self.assertTrue(issubclass(Obravnava, link_hub_streznik._Obravnava))
        v1 = socket.create_connection(s.server_address, timeout=5)
        v1.sendall(b"GET /x HTTP/1.1\r\nHost: a\r\n")                 # glave brez konca
        v2 = socket.create_connection(s.server_address, timeout=5)
        v2.sendall(b"POST /x HTTP/1.1\r\nHost: a\r\nContent-Length: 100\r\n\r\n{\"a\"")   # telo brez konca
        self.addCleanup(v1.close)
        self.addCleanup(v2.close)
        self.assertTrue(_pocakaj(lambda: koncane.count(0) >= 2, rok=5.0), koncane)

    def test_streznik_huba_ima_omejitev(self):
        from core import link_hub_streznik
        s = link_hub_streznik._Streznik(("127.0.0.1", 0), link_hub_streznik._Obravnava)
        try:
            self.assertIsInstance(s.proste, os_deskriptorji.ProsteZveze)
            self.assertIsNone(s.proste.najvec)
            self.assertLessEqual(link_hub_streznik._Obravnava.ROK_CAKANJA_ZAHTEVE_S, 10.0)
        finally:
            s.server_close()


@unittest.skipUnless(os.path.isdir("/proc/self/fd"), "potrebuje /proc")
class RokCakanjaZahteve(unittest.TestCase):
    """Lokalni strezniki (pretok, torrent, posrednik, DLNA, zvok na zvocnik): povezava brez zahteve se zapre."""

    def _streznik(self, obravnava):
        s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), obravnava)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        self.addCleanup(s.server_close)
        self.addCleanup(s.shutdown)
        return s

    def test_brez_zahteve_se_zapre_tok_pa_ne(self):
        class Obravnava(os_deskriptorji.RokCakanjaZahteve, http.server.BaseHTTPRequestHandler):
            ROK_CAKANJA_ZAHTEVE_S = 0.3
            protocol_version = "HTTP/1.1"

            def log_message(self, *_a):
                pass

            def do_GET(self):
                time.sleep(0.8)            # "pavza predvajalnika": dlje od roka cakanja na zahtevo
                self.send_response(200)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"ok")

        s = self._streznik(Obravnava)
        pred = _fd()
        for _ in range(25):
            v = socket.create_connection(s.server_address, timeout=5)
            v.close()
            v = socket.create_connection(s.server_address, timeout=5)
            self.addCleanup(v.close)
        self.assertTrue(_pocakaj(lambda: _fd() <= pred + 25 + 1), (_fd(), pred))
        c = http.client.HTTPConnection(*s.server_address, timeout=5)
        c.request("GET", "/")
        self.assertEqual(c.getresponse().read(), b"ok")
        c.close()

    def test_utihnjen_po_vrstici_zahteve_se_zapre(self):
        koncane = []

        class Obravnava(os_deskriptorji.RokCakanjaZahteve, http.server.BaseHTTPRequestHandler):
            ROK_CAKANJA_ZAHTEVE_S = 0.3
            protocol_version = "HTTP/1.1"

            def log_message(self, *_a):
                pass

            def finish(self):
                koncane.append(1)
                super().finish()

        s = self._streznik(Obravnava)
        v = socket.create_connection(s.server_address, timeout=5)
        self.addCleanup(v.close)
        v.sendall(b"GET / HTTP/1.1\r\nHost: a\r\n")      # glave brez prazne vrstice
        self.assertTrue(_pocakaj(lambda: koncane, rok=5.0))

    def test_strezniki_uporabljajo_rok(self):
        from core import link_pretok, link_sprotno, os_torrent
        for razred in (link_pretok._Obravnava, link_sprotno._Posrednik, os_torrent._Obravnava):
            self.assertTrue(issubclass(razred, os_deskriptorji.RokCakanjaZahteve), razred)
        for ime in ("dlna_zvocniki.py", "zvok_na_zvocnik.py"):
            vir = open(os.path.join(KOREN, "core", ime), encoding="utf-8").read()
            self.assertIn("(os_deskriptorji.RokCakanjaZahteve, BaseHTTPRequestHandler)", vir)


@unittest.skipUnless(os.path.isdir("/proc/self/fd"), "potrebuje /proc")
class Straza(unittest.TestCase):
    def test_razclenitev_in_opozorilo(self):
        poslusa = socket.socket()
        poslusa.bind(("127.0.0.1", 0))
        poslusa.listen(1)
        odjemalec = socket.create_connection(poslusa.getsockname())
        sprejet, _ = poslusa.accept()
        try:
            r = os_deskriptorji.razclenitev()
            self.assertGreaterEqual(r["vrste"].get("socket", 0), 3)
            self.assertGreaterEqual(r["tcp"].get("LISTEN", 0), 1)
            self.assertGreaterEqual(r["tcp"].get("ESTAB v:%d" % poslusa.getsockname()[1], 0), 1)
            vrstice = []
            s = os_deskriptorji.Straza(vrstice.append, prag=1, korak=1000)
            self.assertIsNotNone(s.preglej())
            self.assertIsNone(s.preglej())          # brez nove rasti ni novega opozorila
            self.assertEqual(len(vrstice), 1)
            self.assertIn("socket=", vrstice[0])
            self.assertNotIn("127.0.0.1", vrstice[0])     # brez naslovov
        finally:
            for v in (odjemalec, sprejet, poslusa):
                v.close()

    def test_vkljuci_zazene_strazo(self):
        vir = open(os.path.join(KOREN, "core", "os_stabilnost.py"), encoding="utf-8").read()
        telo = vir[vir.index("def vkljuci("):]
        self.assertIn("os_deskriptorji.Straza(", telo[:telo.index("\ndef ")])


if __name__ == "__main__":
    unittest.main()


class _ImapStreznik:
    """Najmanjsi streznik IMAP na 127.0.0.1 (brez TLS): NOOP vrne NO - povezava je za odjemalca mrtva."""

    def __init__(self):
        self.s = socket.socket()
        self.s.bind(("127.0.0.1", 0))
        self.s.listen(32)
        self.vrata = self.s.getsockname()[1]
        threading.Thread(target=self._sprejemaj, daemon=True).start()

    def _sprejemaj(self):
        while True:
            try:
                c, _ = self.s.accept()
            except OSError:
                return
            threading.Thread(target=self._en, args=(c,), daemon=True).start()

    @staticmethod
    def _en(c):
        with c, c.makefile("rb") as f:
            c.sendall(b"* OK pripravljen\r\n")
            for vrstica in f:
                deli = vrstica.split()
                if len(deli) < 2:
                    return
                oznaka, ukaz = deli[0], deli[1].upper()
                if ukaz == b"CAPABILITY":
                    c.sendall(b"* CAPABILITY IMAP4rev1 AUTH=PLAIN\r\n" + oznaka + b" OK koncano\r\n")
                elif ukaz == b"SELECT" or ukaz == b"EXAMINE":
                    c.sendall(b"* 1 EXISTS\r\n" + oznaka + b" OK [READ-WRITE]\r\n")
                elif ukaz == b"NOOP":
                    c.sendall(oznaka + b" NO mrtva\r\n")
                elif ukaz == b"LOGOUT":
                    c.sendall(b"* BYE\r\n" + oznaka + b" OK koncano\r\n")
                    return
                else:
                    c.sendall(oznaka + b" OK koncano\r\n")

    def zapri(self):
        self.s.close()


@unittest.skipUnless(os.path.isdir("/proc/self/fd"), "potrebuje /proc")
class SporocilaImap(unittest.TestCase):
    def setUp(self):
        import imaplib
        from unittest import mock
        from core.sporocila import email
        self.streznik = _ImapStreznik()
        self.addCleanup(self.streznik.zapri)

        class BrezTls(imaplib.IMAP4):
            def __init__(self, host, port, ssl_context=None, timeout=None):
                super().__init__(host, port, timeout=timeout)

        p = mock.patch.object(email.imaplib, "IMAP4_SSL", BrezTls)
        p.start()
        self.addCleanup(p.stop)
        self.email = email

    def _racun(self, vnos=None):
        return self.email.EmailAdapter("k", "lastnik@primer.test", "127.0.0.1", "127.0.0.1",
                                       imap_vrata=self.streznik.vrata, geslo="" if vnos else "x", vnos_gesla=vnos)

    def test_mrtva_povezava_se_zapre_pred_novo(self):
        racun = self._racun()
        racun.povezi()
        pred = _fd()
        for _ in range(20):
            racun.povezi()                  # NOOP vrne NO: stara se zapre, odpre se nova
        self.assertTrue(_pocakaj(lambda: _fd() <= pred + 1), (_fd(), pred))
        self.email._zapri_imap(racun._imap)

    def test_napaka_gesla_ne_pusti_povezave(self):
        def vnos():
            raise RuntimeError("uporabnik je preklical")

        racun = self._racun(vnos=vnos)
        napake = []
        try:
            racun._locena_povezava()        # prvi klic: zbirka gesel (D-Bus) odpre svojo, trajno povezavo
        except RuntimeError as e:
            napake.append(e)
        pred = _fd()
        for _ in range(20):
            try:
                racun._locena_povezava()
            except RuntimeError as e:
                napake.append(e)            # klicatelj napako hrani (z njo sled in lokalne spremenljivke)
        self.assertTrue(_pocakaj(lambda: _fd() <= pred + 1), (_fd(), pred))


@unittest.skipUnless(os.path.isdir("/proc/self/fd"), "potrebuje /proc")
class DrugiViri(unittest.TestCase):
    def test_ffmpeg_cev_zaprta_in_proces_pocakan(self):
        import subprocess
        from core import zvok_na_zvocnik
        pred = _fd()
        for _ in range(15):
            p = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"],
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            zvok_na_zvocnik._koncaj(p)
            self.assertIsNotNone(p.returncode)          # pocakan: ni zombija
            self.assertTrue(p.stdout.closed)
        self.assertLessEqual(_fd(), pred + 1)

    def test_scit_zasedena_vrata_brez_puscanja(self):
        from unittest import mock
        from core import os_scit
        zasedena = socket.socket()
        zasedena.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        zasedena.bind(("127.0.0.1", 0))
        zasedena.listen(1)
        self.addCleanup(zasedena.close)
        vrata = zasedena.getsockname()[1]
        with mock.patch.object(os_scit, "VRATA", [vrata] * 10), mock.patch.object(os_scit, "NASLOV", "127.0.0.1"):
            scit = os_scit.Razresevalnik.__new__(os_scit.Razresevalnik)
            scit._tece = False
            pred = _fd()
            self.assertEqual(os_scit.Razresevalnik.zazeni(scit), 0)     # UDP se veze, TCP ne: obe se zapreta
            self.assertEqual(_fd(), pred)

    def test_krajevni_naslov_brez_puscanja(self):
        from unittest import mock
        from core import link_datoteke
        pred = _fd()
        with mock.patch.object(socket.socket, "connect", side_effect=OSError("ni poti")):
            napake = [link_datoteke.naslov_do_huba("https://127.0.0.1:8990") for _ in range(20)]
        self.assertEqual(set(napake), {"127.0.0.1"})
        self.assertLessEqual(_fd(), pred)
