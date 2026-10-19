"""Varnostni pregled datotek in pretvorbe v Safeer Linku (19. 10. 2026): preizkus za vsako ugotovitev.

Vsak preizkus brez popravka pade (preverjeno z zacasno umaknjenim popravkom). Strezniki tecejo samo na zanki
(127.0.0.1), vse zacasne mape in strezniki se po preizkusu pospravijo.

1. Ime pretvorjenega videa z druge naprave (video.status -> name) ne pise zunaj mape izvirnika in ne da programa.
2. files.open ne zazene programa ali zaganjalnika; preimenovanje datoteke ne naredi za program.
3. Streznik datotek: skupni rok za glave (slowloris), meja povezav pred glavami, samo domace omrezje, obramba.
4. Napake napravi brez poti in besedila izjem (samo v krajevni dnevnik).
5. Slicice slik: najvec dve hkrati in brez dekodiranja ogromnih slik.
6. /live/ in /m/ preverita zmoznost predvajalnika pri vsaki zahtevi.
7. Windows: atribut Skrito/Sistemsko skrije datoteko kot pika na Linuxu.
"""
import io
import json
import os
import shutil
import socket
import ssl
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_daljinec, link_datoteke, link_pretvorba, link_teamwork, zasebni_webkit  # noqa: E402
from dostop_za_preizkus import setUpModule, tearDownModule  # noqa: E402,F401 - naprave v teh preizkusih so v ozjem krogu

POT_LASTNIKA = "/home/lastnik/Dokumenti/tajno.odt"


class _SamoZanka(link_datoteke._Streznik):
    """Streznik datotek v preizkusu poslusa samo na zanki (ne na vseh vmesnikih)."""

    def __init__(self, naslov, *a, **k):
        super().__init__(("127.0.0.1", naslov[1]), *a, **k)


class _Obravnava:
    """Namesto BaseHTTPRequestHandler: kaj streznik odgovori, brez omrezja."""

    def __init__(self, glave=None, command="GET", telo=b""):
        self.headers = dict(glave or {})
        self.command = command
        self.koda = None
        self.glave = {}
        self.wfile = io.BytesIO()
        self.rfile = io.BytesIO(telo)
        self.connection = None
        self.close_connection = False

    def send_response(self, koda, *_a):
        if self.koda is None:
            self.koda = koda

    def send_header(self, ime, vrednost):
        self.glave[ime] = vrednost

    def end_headers(self):
        pass


def _pocakaj(pogoj, rok=5.0):
    konec = time.monotonic() + rok
    while time.monotonic() < konec:
        if pogoj():
            return True
        time.sleep(0.02)
    return pogoj()


# ---------------------------------------------------------------------------------------------------------- 1
class ImePretvorjenegaVidea(unittest.TestCase):
    """Ime z druge naprave (`video.status` -> name) je bilo brez ciscenja pot za os.path.join: absolutna pot ali ../
    je ob »prenesi nazaj« pisala vsebino naprave kamorkoli (~/.bash_aliases, ~/.config/autostart/*.desktop)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="safeer-pregled-pretvorba-")
        self.mapa = os.path.join(self.tmp, "Videi")
        self.zunaj = os.path.join(self.tmp, "zunaj")
        os.makedirs(self.mapa)
        os.makedirs(self.zunaj)
        self.pot = os.path.join(self.mapa, "film.mkv")
        with open(self.pot, "wb") as f:
            f.write(b"\x1aE\xdf\xa3" + b"v" * 4000)
        self.zapisano = []

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _pretvorba(self, ime_naprave):
        class _Streznik:
            odtis = "a" * 64

            def zazeni(self):
                pass

            def osnova(self, naslov):
                return "https://127.0.0.1:9"

            def dodaj_datoteko_toka(self, pot):
                return "/m/skrivnost/film.mkv"

            def zeton_za(self, naprava):
                return "zeton"

        class _Datoteke:
            streznik = _Streznik()

        def vprasaj(naprava, dejanje, p):
            if dejanje == "host.info":
                return {"ok": True, "data": {"disk": {"prosto": 50 * 2 ** 30, "skupaj": 0}, "cpu": {"jedra": 8},
                                             "gpu": {"strojno": True, "kodirniki": [{"vrsta": "avc", "sirina": 1920}]},
                                             "pomoc": {"lahko": True}}}
            if dejanje == "video.transcode":
                return {"ok": True, "data": {"id": "op1"}}
            if dejanje == "video.status":
                return {"ok": True, "data": {"state": "koncano", "percent": 100, "name": ime_naprave,
                                             "file_id": "media:shramba:7", "size": 11}}
            if dejanje == "files.list":
                return {"ok": True, "data": {"shared": True, "items": [{"id": "media:shramba:7"}],
                                             "server": {"base_url": "https://127.0.0.1:9", "fp": "a" * 64, "token": "z"}}}
            return {"ok": False}

        def prenesi(streznik, oznaka, cilj, o):
            self.zapisano.append(cilj)
            with open(cilj, "wb") as f:
                f.write(b"[Desktop Entry]\nExec=sh -c zlo\n")

        naprave = [{"id": "tv", "ime": "TV", "zmoznosti": ["files"], "platforma": "tv"}]
        return link_pretvorba.Pretvorba(lambda: naprave, vprasaj, _Datoteke(), cakaj=0.02, prenesi=prenesi,
                                        sonda=lambda pot: None, ffmpeg="")

    def _pretvori_in_prenesi(self, ime_naprave):
        p = self._pretvorba(ime_naprave)
        o = p.zacni(self.pot)
        self.assertTrue(_pocakaj(lambda: p.stanje(o["id"])["stanje"] in ("koncano", "napaka")))
        r = p.stanje(o["id"])
        self.assertEqual(r["stanje"], "koncano", r)
        izhod = r["izhod"]
        p.prenesi(o["id"])
        self.assertTrue(_pocakaj(lambda: p.stanje(o["id"])["stanje"] != "prenasam_nazaj"))
        return izhod, p.stanje(o["id"])

    def test_absolutna_pot_naprave_ostane_v_mapi_izvirnika(self):
        tarca = os.path.join(self.zunaj, "zlo.desktop")
        izhod, r = self._pretvori_in_prenesi(tarca)
        self.assertNotIn("/", izhod)
        self.assertTrue(izhod.endswith(".mp4"), izhod)
        self.assertFalse(os.path.lexists(tarca), "datoteka z druge naprave je pristala zunaj mape izvirnika")
        self.assertEqual(r["stanje"], "na_racunalniku", r)
        self.assertEqual(os.path.dirname(r["lokalno"]), os.path.realpath(self.mapa))
        self.assertEqual(os.listdir(self.zunaj), [])

    def test_relativna_pot_in_skrito_ime(self):
        izhod, r = self._pretvori_in_prenesi("../zunaj/.bash_aliases")
        self.assertEqual(izhod, "bash_aliases.mp4")
        self.assertEqual(os.listdir(self.zunaj), [])
        self.assertEqual(r["lokalno"], os.path.join(os.path.realpath(self.mapa), "bash_aliases.mp4"))

    def test_zapis_na_disk_ne_zaupa_imenu_opravila(self):
        """Tudi ce bi ime prislo mimo video.status (drugo opravilo, stara razlicica), pisanje ostane v mapi."""
        p = self._pretvorba("x")
        o = link_pretvorba.Opravilo(self.pot)
        o.stanje, o.cilj, o.oznaka = "koncano", "tv", "media:shramba:7"
        o.izhod_ime = os.path.join(self.zunaj, "autostart.desktop")
        p._nazaj(o)
        self.assertEqual(os.listdir(self.zunaj), [])
        self.assertEqual(os.path.dirname(o.lokalno), os.path.realpath(self.mapa))
        self.assertTrue(o.lokalno.endswith(".mp4"))

    def test_prosta_pot_ne_sprejme_poti(self):
        for ime in (os.path.join(self.zunaj, "x.mp4"), "../x.mp4", "a/b.mp4", "..", ""):
            with self.assertRaises(ValueError, msg=ime):
                link_pretvorba.prosta_pot(self.mapa, ime)
        self.assertEqual(link_pretvorba.prosta_pot(self.mapa, "film-1080p.mp4"), os.path.join(self.mapa, "film-1080p.mp4"))

    def test_zacasna_datoteka_ne_sledi_simbolni_povezavi(self):
        """Prenos nazaj je pisal v <cilj>.part z open(..., "wb"): obstojeca simbolna povezava s tem imenom je
        preusmerila vsebino naprave v poljubno datoteko uporabnika."""
        tarca = os.path.join(self.zunaj, "bashrc")
        with open(tarca, "wb") as f:
            f.write(b"IZVIRNIK")
        cilj = os.path.join(self.mapa, "film-1080p.mp4")
        os.symlink(tarca, cilj + ".part")
        vsebina = b"pretvorjeni video" * 100

        class _Odgovor:
            status = 200

            def __init__(self):
                self._b = io.BytesIO(vsebina)

            def getheader(self, ime, privzeto=None):
                return str(len(vsebina)) if ime.lower() == "content-length" else privzeto

            def read(self, n=-1):
                return self._b.read(n)

        class _Https:
            def __init__(self, *_a, **_k):
                pass

            def request(self, *_a, **_k):
                pass

            def getresponse(self):
                return _Odgovor()

            def close(self):
                pass

        from core import link_tls
        o = link_pretvorba.Opravilo(self.pot)
        with mock.patch.object(link_tls, "_PripetaHttps", _Https):
            link_pretvorba.prenesi_z_naprave({"base_url": "https://127.0.0.1:9", "fp": "a" * 64, "token": "z"},
                                             "media:shramba:7", cilj, o)
        with open(tarca, "rb") as f:
            self.assertEqual(f.read(), b"IZVIRNIK", "vsebina naprave je prepisala datoteko zunaj mape")
        self.assertFalse(os.path.islink(cilj))
        with open(cilj, "rb") as f:
            self.assertEqual(f.read(), vsebina)


# ---------------------------------------------------------------------------------------------------------- 2
class OdpiranjeNaDaljavo(unittest.TestCase):
    """files.open je odprl s privzetim programom karkoli v deljeni mapi: naprava z zmoznostjo "d" je datoteko
    preimenovala v .exe/.desktop (ali poslala) in jo odprla - z Wine ali Javo je to zagon programa."""

    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-pregled-odpri-")
        self._pisi("film.mp4", b"\x00\x00\x00\x18ftypmp42" + b"v" * 100)
        self._pisi("film_ntfs.mp4", b"\x00\x00\x00\x18ftypmp42" + b"v" * 100, 0o755)   # NTFS/exFAT: vse je +x
        self._pisi("zagon.desktop", b"[Desktop Entry]\nType=Application\nExec=sh -c zlo\n")
        self._pisi("namesti.exe", b"MZ\x90\x00")
        self._pisi("skripta.sh", b"#!/bin/sh\necho zlo\n")
        self._pisi("Program.AppImage", b"\x7fELF\x02\x01")
        self._pisi("brez_koncnice", b"\x7fELF\x02\x01\x01")
        self._pisi("preoblecen.mp4", b"MZ\x90\x00 program s koncnico videa")
        self._pisi("izvrsljiva", b"echo zlo\n", 0o755)
        self._pisi("zaganjalnik_brez_koncnice", b"\xef\xbb\xbf\n[Desktop Entry]\nExec=zlo\n")
        os.makedirs(os.path.join(self.mapa, "Mapa"))
        self.d = link_datoteke.Datoteke([self.mapa], tls_mapa=os.path.join(self.mapa, ".tls"))
        self.odprto = []
        popravek = mock.patch.object(zasebni_webkit, "odpri_privzeto", lambda pot: self.odprto.append(pot) or True)
        popravek.start()
        self.addCleanup(popravek.stop)

    def tearDown(self):
        self.d.ustavi()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def _pisi(self, ime, vsebina, nacin=0o644):
        pot = os.path.join(self.mapa, ime)
        with open(pot, "wb") as f:
            f.write(vsebina)
        os.chmod(pot, nacin)

    def _odpri(self, ime, dejanje="files.open", programi=None):
        izidi = []
        link_daljinec.izvedi_control(dejanje, {"id": "share:0:" + ime}, lambda u: None, izidi.append,
                                     datoteke=self.d, programi=programi)
        return izidi[-1]

    NEVARNE = ("zagon.desktop", "namesti.exe", "skripta.sh", "Program.AppImage", "brez_koncnice", "preoblecen.mp4",
               "izvrsljiva", "zaganjalnik_brez_koncnice")

    def test_files_open_ne_zazene_programa(self):
        for ime in self.NEVARNE:
            r = self._odpri(ime)
            self.assertEqual((r["ok"], r.get("code")), (False, "nevarna_datoteka"), ime)
        self.assertEqual(self.odprto, [], "privzeti program je dobil program ali zaganjalnik")
        for ime in self.NEVARNE:
            self.assertFalse(self.d.odpri("share:0:" + ime), ime)      # tudi neposredni klic Datoteke.odpri
        self.assertEqual(self.odprto, [])

    def test_navadne_datoteke_in_mape_se_odprejo(self):
        """Video z diska NTFS/exFAT (izvrsljiv bit pri vsaki datoteki) se odpre kot prej."""
        for ime in ("film.mp4", "film_ntfs.mp4", "Mapa"):
            r = self._odpri(ime)
            self.assertTrue(r["ok"], (ime, r))
        self.assertEqual([os.path.basename(p) for p in self.odprto], ["film.mp4", "film_ntfs.mp4", "Mapa"])

    def test_locen_zaslon_ne_zazene_programa(self):
        class _Drugi:
            def __init__(self):
                self.zagnano = []

            def zazeni_program(self, argv, opis=None):
                self.zagnano.append(argv)
                return True

        class _Programi:
            vklopljeno = True

            def __init__(self, drugi):
                self.drugi = drugi

        drugi = _Drugi()
        r = self._odpri("zagon.desktop", "files.open_locen", _Programi(drugi))
        self.assertEqual((r["ok"], r.get("code")), (False, "nevarna_datoteka"))
        self.assertEqual(drugi.zagnano, [])
        self.assertTrue(self._odpri("film.mp4", "files.open_locen", _Programi(drugi))["ok"])
        self.assertEqual(len(drugi.zagnano), 1)

    def test_preimenovanje_ne_naredi_programa(self):
        s = self.d.streznik
        for novo in ("film.exe", "film.desktop", "film.mp4.sh", "film.AppImage", "film.jar", "film.py", "film.EXE."):
            koda, odgovor = s.uredi("share:0:film.mp4", {"op": "rename", "name": novo})
            self.assertEqual((koda, odgovor.get("napaka")), (403, "nevarna_vrsta"), novo)
        self.assertTrue(os.path.isfile(os.path.join(self.mapa, "film.mp4")))
        # Navadno preimenovanje in program z ISTO koncnico ostaneta dovoljena.
        self.assertEqual(s.uredi("share:0:film.mp4", {"op": "rename", "name": "film-2.mp4"})[0], 200)
        self.assertEqual(s.uredi("share:0:skripta.sh", {"op": "rename", "name": "skripta-stara.sh"})[0], 200)
        self.assertEqual(s.uredi("share:0:Mapa", {"op": "rename", "name": "Mapa.d"})[0], 200)


# ---------------------------------------------------------------------------------------------------------- 3
class StreznikDatotekObramba(unittest.TestCase):
    """Streznik datotek je poslusal na 0.0.0.0 brez obrambe (core/link_obramba), brez preverbe domacega omrezja in s
    120 s na posamezen recv: kdor je poslal en bajt na nekaj sekund, je drzal nit in deskriptor za vedno."""

    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-pregled-streznik-")
        self.d = link_datoteke.Datoteke([self.mapa], tls_mapa=os.path.join(self.mapa, ".tls"))
        self.vticniki = []

    def tearDown(self):
        for v in self.vticniki:
            try:
                v.close()
            except OSError:
                pass
        self.d.ustavi()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def _zazeni(self):
        with mock.patch.object(link_datoteke, "_Streznik", _SamoZanka):
            self.d.streznik.zazeni()
        return self.d.streznik._streznik

    def _povezi(self, tls=True):
        v = socket.create_connection(("127.0.0.1", self.d.streznik.vrata), timeout=5)
        if tls:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            v = ctx.wrap_socket(v)
        self.vticniki.append(v)
        return v

    @staticmethod
    def _zaprta(v, rok):
        v.settimeout(rok)
        try:
            return v.recv(1) == b""
        except (socket.timeout, TimeoutError):
            return False
        except OSError:
            return True

    def test_glave_imajo_skupni_rok(self):
        with mock.patch.object(link_datoteke, "ROK_GLAV_S", 1.0, create=True):
            self._zazeni()
        v = self._povezi()
        v.sendall(b"GET /d/share:0:x HTTP/1.1\r\nHost: x\r\n")
        zacetek = time.monotonic()
        zaprta = None
        while time.monotonic() - zacetek < 6.0:
            try:
                v.sendall(b"X")                 # en bajt glave na cetrt sekunde: rok na recv se ne izteče nikoli
            except OSError:
                zaprta = time.monotonic() - zacetek
                break
            if self._zaprta(v, 0.25):
                zaprta = time.monotonic() - zacetek
                break
        self.assertIsNotNone(zaprta, "povezava brez celih glav je ostala odprta (slowloris)")
        self.assertLess(zaprta, 4.0)

    def test_meja_povezav_pred_glavami_na_vir(self):
        with mock.patch.object(link_datoteke, "NAJVEC_PRED_GLAVAMI_NA_VIR", 3, create=True):
            self._zazeni()
        tihe = []
        for _ in range(5):
            tihe.append(self._povezi(tls=False))     # TCP brez rokovanja TLS: tiha povezava
            time.sleep(0.1)
        time.sleep(0.3)
        self.assertEqual([self._zaprta(v, 0.3) for v in tihe], [True, True, False, False, False],
                         "nad mejo mora izpasti najstarejsa tiha povezava istega vira")

    def test_samo_domace_omrezje(self):
        s = self._zazeni()
        primeri = [("127.0.0.1", True), ("192.168.1.20", True), ("10.1.2.3", True), ("172.20.0.4", True),
                   ("169.254.3.4", True), ("fe80::1", True), ("fd12::5", True), ("::ffff:192.168.1.2", True),
                   ("8.8.8.8", False), ("203.0.113.7", False), ("100.64.0.1", False), ("172.32.0.1", False),
                   ("::ffff:8.8.8.8", False), ("2001:db8::1", False), ("", False)]
        for vir, dovoljen in primeri:
            lazni = socket.socket()
            try:
                self.assertEqual(s.verify_request(lazni, (vir, 5555)), dovoljen, vir)
            finally:
                s.shutdown_request(lazni)

    def test_obramba_zapre_vir_ki_ne_zna_tls(self):
        s = self._zazeni()
        neuspelo = getattr(s, "ob_neuspelem_rokovanju", lambda naslov: None)
        for _ in range(40):                        # pregledovalnik vrat: 40 neuspelih rokovanj v minuti
            neuspelo(("192.168.77.5", 4000))
        lazni = socket.socket()
        try:
            self.assertFalse(s.verify_request(lazni, ("192.168.77.5", 4001)), "obramba vira ni zaprla")
        finally:
            s.shutdown_request(lazni)
        lazni = socket.socket()
        try:
            self.assertTrue(s.verify_request(lazni, ("192.168.77.6", 4001)), "druga naprava v omrezju ostane")
        finally:
            s.shutdown_request(lazni)

    def test_prava_zahteva_dela_in_nit_cuvaja_se_konca(self):
        s = self._zazeni()
        with open(os.path.join(self.mapa, "a.txt"), "wb") as f:
            f.write(b"vsebina")
        zeton = self.d.streznik.zeton_za("tv-1")
        v = self._povezi()
        v.sendall(b"GET /d/share:0:a.txt HTTP/1.1\r\nHost: x\r\nX-Safeer-Token: " + zeton.encode() + b"\r\n\r\n")
        odgovor = b""
        while b"vsebina" not in odgovor:
            kos = v.recv(4096)
            if not kos:
                break
            odgovor += kos
        self.assertTrue(odgovor.startswith(b"HTTP/1.1 200"), odgovor[:40])
        self.assertTrue(odgovor.endswith(b"vsebina"))
        nit = s.cuvaj._nit
        self.d.ustavi()
        self.assertTrue(_pocakaj(lambda: not nit.is_alive(), 3.0), "nit cuvaja je ostala po ustavitvi")


# ---------------------------------------------------------------------------------------------------------- 4
class NapakeBrezPodrobnosti(unittest.TestCase):
    """Napaka je drugi napravi vrnila besedilo izjeme (»Ukaz ni uspel: [Errno 2] ... /home/<uporabnik>/...«,
    "razlog": str(e)) - s potjo in uporabniskim imenom tega racunalnika."""

    def _brez_poti(self, besedilo):
        self.assertNotIn("/home/lastnik", json.dumps(besedilo, ensure_ascii=False))
        self.assertNotIn("tajno", json.dumps(besedilo, ensure_ascii=False))

    def _control(self, dejanje, **k):
        izidi = []
        link_daljinec.izvedi_control(dejanje, {}, lambda u: None, izidi.append, **k)
        self.assertTrue(_pocakaj(lambda: bool(izidi)))
        return izidi[-1]

    def test_ukaz_controla(self):
        class _Datoteke:
            def seznam(self, *_a):
                raise RuntimeError(POT_LASTNIKA)

        r = self._control("files.list", datoteke=_Datoteke())
        self._brez_poti(r)
        self.assertEqual((r["ok"], r.get("code")), (False, "napaka"))

        class _Manjka:
            def seznam(self, *_a):
                raise FileNotFoundError(2, "No such file or directory", POT_LASTNIKA)

        r = self._control("files.list", datoteke=_Manjka())
        self._brez_poti(r)
        self.assertEqual((r["ok"], r.get("code")), (False, "ni_mape"))

        class _Predvajanje:
            def stanje(self, *_a):
                raise OSError(13, "Permission denied", POT_LASTNIKA)

        self._brez_poti(self._control("play.state", predvajanje=_Predvajanje()))

    def test_ukaz_brskalnika(self):
        class _Brskalnik:
            def get_active_webview(self):
                return None

            def load_homepage(self):
                raise OSError(2, "No such file or directory", POT_LASTNIKA)

        izidi = []
        link_daljinec.izvedi(_Brskalnik(), "key", {"key": "home"}, lambda u: None, izidi.append)
        self._brez_poti(izidi[-1])
        self.assertFalse(izidi[-1]["ok"])

    def test_glasnost(self):
        with mock.patch.object(link_daljinec.shutil, "which", lambda ime: "/usr/bin/" + ime), \
                mock.patch.object(link_daljinec, "_pactl", side_effect=OSError(2, "No such file", POT_LASTNIKA)):
            r = link_daljinec._glasnost({"direction": "up"})
        self._brez_poti(r)
        self.assertFalse(r["ok"])

    def test_popravek_na_strezniku(self):
        tmp = tempfile.mkdtemp(prefix="safeer-pregled-popravek-")
        self.addCleanup(shutil.rmtree, tmp, True)

        class _Teamwork:
            def _mapa_zacasnih(self):
                return tmp

            def popravek(self, *_a):
                raise RuntimeError("ni mogoce zapisati " + POT_LASTNIKA)

        o = _Obravnava(command="POST", telo=b"p" * 10)
        link_datoteke._sprejmi_popravek(o, _Teamwork(), "B", "share:0:a.odt", 10)
        self.assertEqual(o.koda, 500)
        self._brez_poti(o.wfile.getvalue().decode())
        self.assertEqual(json.loads(o.wfile.getvalue())["koda"], "napaka")

    def test_teamwork_napaka_diska(self):
        tmp = tempfile.mkdtemp(prefix="safeer-pregled-tw-")
        self.addCleanup(shutil.rmtree, tmp, True)
        izvirnik = os.path.join(tmp, "a.odt")
        with open(izvirnik, "wb") as f:
            f.write(b"a" * 1000)
        telo = os.path.join(tmp, "telo")
        with open(telo, "wb") as f:
            f.write(b"x")
        a = link_teamwork.Teamwork(razresi=lambda o: izvirnik if o == "share:0:a.odt" else "", ime_naprave=lambda i: i,
                                   obvesti=lambda k, p: None, ukaz=None, okna=lambda: [], mapa=os.path.join(tmp, "tw"),
                                   procesi=None, zdaj=lambda: 1000.0)
        self.assertTrue(a.prijava("B", {"id": "share:0:a.odt", "odprto": True})["ok"])
        with mock.patch.object(link_teamwork, "uporabi_popravek",
                               side_effect=OSError(13, "Permission denied", POT_LASTNIKA)):
            koda, odgovor = a.popravek("B", "share:0:a.odt", telo)
        self.assertEqual(koda, 500)
        self._brez_poti(odgovor)
        self.assertEqual(odgovor.get("razlog"), "EACCES")


# ---------------------------------------------------------------------------------------------------------- 5
class _LaznaSlika:
    """Namesto PIL slike: velikost iz glave, dekodiranje (thumbnail) zabelezi in lahko pocaka."""
    hkrati = 0
    najvec_hkrati = 0
    dekodirane = 0
    zaklep = threading.Lock()
    cakaj = None

    def __init__(self, velikost, po_draft=None):
        self.size = velikost
        self._po_draft = po_draft
        self.mode = "RGB"

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False

    def draft(self, *_a):
        if self._po_draft:
            self.size = self._po_draft

    def thumbnail(self, *_a):
        cls = type(self)
        with cls.zaklep:
            cls.hkrati += 1
            cls.dekodirane += 1
            cls.najvec_hkrati = max(cls.najvec_hkrati, cls.hkrati)
        try:
            if cls.cakaj is not None:
                cls.cakaj.wait(5)
        finally:
            with cls.zaklep:
                cls.hkrati -= 1

    def save(self, izhod, *_a, **_k):
        izhod.write(b"\xff\xd8slicica")


class SliciceSlik(unittest.TestCase):
    """Slicice slik so se delale brez meje hkratnosti in do ~179 MP (meja Pillowa): vzporedne zahteve so izcrpale
    pomnilnik procesa."""

    def setUp(self):
        _LaznaSlika.hkrati = _LaznaSlika.najvec_hkrati = _LaznaSlika.dekodirane = 0
        _LaznaSlika.cakaj = None
        self.velikost = (4000, 3000)
        self.po_draft = None
        popravki = [mock.patch("PIL.Image.open", lambda pot: _LaznaSlika(self.velikost, self.po_draft)),
                    mock.patch("PIL.ImageOps.exif_transpose", lambda im: im)]
        for p in popravki:
            p.start()
            self.addCleanup(p.stop)

    def test_najvec_dve_hkrati(self):
        _LaznaSlika.cakaj = threading.Event()
        niti = [threading.Thread(target=link_datoteke._slicica_slike, args=("/x/%d.png" % i, 512)) for i in range(6)]
        for n in niti:
            n.start()
        time.sleep(0.5)
        hkrati = _LaznaSlika.najvec_hkrati
        _LaznaSlika.cakaj.set()
        for n in niti:
            n.join(10)
        self.assertLessEqual(hkrati, 2, "slike so se dekodirale vse hkrati")
        self.assertEqual(_LaznaSlika.dekodirane, 6, "vse slicice so na koncu narejene")

    def test_ogromna_slika_se_ne_dekodira(self):
        self.velikost = (10000, 6000)                # 60 MP PNG: ~240 MB RGBA samo za eno slicico
        self.assertIsNone(link_datoteke._slicica_slike("/x/ogromna.png", 512))
        self.assertEqual(_LaznaSlika.dekodirane, 0)

    def test_fotografija_telefona_200_mp_z_draft(self):
        """JPEG se z draft dekodira pomanjsan (1/8): 200 MP fotografija ostane s slicico."""
        self.velikost, self.po_draft = (16320, 12240), (2040, 1530)
        self.assertTrue(link_datoteke._slicica_slike("/x/foto.jpg", 512))


# ---------------------------------------------------------------------------------------------------------- 6
class ZmoznostTokov(unittest.TestCase):
    """/live/ in /m/ sta preverila samo zeton: tok je po odvzemu zmoznosti predvajalnika ("v") deloval se do
    izteka zetona (12 h od zadnje rabe)."""

    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-pregled-tokovi-")
        self.d = link_datoteke.Datoteke([], tls_mapa=os.path.join(self.mapa, "tls"))
        self.s = self.d.streznik
        self.zeton = self.s.zeton_za("tv-1")
        self.odvzeto = set()
        self.s.sme = lambda naprava, zmoznost: zmoznost not in self.odvzeto

    def tearDown(self):
        self.d.ustavi()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_live_po_odvzemu_predvajalnika(self):
        postrezeno = []

        class _Sprotno:
            def postrezi(self, obravnava, id_, samo_glava):
                postrezeno.append(id_)
                obravnava.send_response(200)

        self.s.sprotno = _Sprotno()
        o = _Obravnava({"X-Safeer-Token": self.zeton})
        link_datoteke.postrezi_pot(o, self.s, "/live/abc/index.m3u8", False)
        self.assertEqual((o.koda, postrezeno), (200, ["abc"]))
        self.odvzeto.add("v")
        o = _Obravnava({"X-Safeer-Token": self.zeton})
        link_datoteke.postrezi_pot(o, self.s, "/live/abc/index.m3u8", False)
        self.assertEqual(o.koda, 401, "sprotni tok je deloval po odvzemu predvajalnika")
        self.assertEqual(postrezeno, ["abc"])

    def test_tok_torrenta_po_odvzemu_predvajalnika(self):
        class _Torrenti:
            def zazeni(self):
                pass

            def preberi(self, uri):
                return {"hash": "b" * 40, "datoteke": [{"i": 0, "ime": "Film/film.mkv", "velikost": 900, "vrsta": "video"}]}

            def dodaj(self, uri, izbrane):
                return 7

            def tok(self, tid, i):
                return "http://127.0.0.1:1/t/film.mkv"     # nihce ne poslusa: odgovora brez 401 ni

            def podnapisi_za(self, tid, i):
                return []

        with mock.patch.object(link_datoteke, "_Streznik", _SamoZanka):
            r = self.d.tok_torrenta("magnet:?xt=urn:btih:" + "b" * 40, "tv-1", torrenti=_Torrenti(),
                                    zmogljivost=lambda m, v: "", mape_stanja=[self.mapa])
        skrivnost = r["path"].split("/")[2]
        self.odvzeto.add("v")
        o = _Obravnava({"X-Safeer-Token": r["server"]["token"]})
        link_datoteke.postrezi_pot(o, self.s, "/m/%s/film.mkv" % skrivnost, False)
        self.assertEqual(o.koda, 401, "tok torrenta je deloval po odvzemu predvajalnika")

    def test_tok_ki_ga_da_racunalnik_sam_ostane(self):
        """Pretvorba in shramba: izvirnik je napravi dal ta racunalnik - zmoznost predvajalnika ni potrebna."""
        pot = os.path.join(self.mapa, "film.mkv")
        with open(pot, "wb") as f:
            f.write(b"izvirnik")
        poti = self.s.dodaj_datoteko_toka(pot)
        self.odvzeto.add("v")
        o = _Obravnava({"X-Safeer-Token": self.zeton})
        link_datoteke.postrezi_pot(o, self.s, poti, False)
        self.assertEqual((o.koda, o.wfile.getvalue()), (200, b"izvirnik"))


# ---------------------------------------------------------------------------------------------------------- 7
class SkriteDatotekeWindows(unittest.TestCase):
    """Na Windows skrite in sistemske datoteke nimajo pike (AppData, pagefile.sys): seznam in oznake so jih dajali."""

    SKRITO, SISTEMSKO = 0x2, 0x4

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="safeer-pregled-windows-")
        self.dom = os.path.join(self.tmp, "Uporabnik")
        os.makedirs(os.path.join(self.dom, "AppData", "Roaming"))
        for ime in ("AppData/Roaming/gesla.db", "skrita.mp4", "pagefile.sys", "film.mp4"):
            with open(os.path.join(self.dom, ime), "wb") as f:
                f.write(b"x")
        self.atributi = {"AppData": self.SKRITO, "skrita.mp4": self.SKRITO, "pagefile.sys": self.SKRITO | self.SISTEMSKO}
        for p in (mock.patch.object(link_datoteke, "_IMA_ATRIBUTE", True, create=True),
                  mock.patch.object(link_datoteke, "_atributi", lambda pot: self.atributi.get(os.path.basename(pot), 0),
                                    create=True)):
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_deljena_mapa(self):
        m = link_datoteke.DeljeneMape([self.dom])
        self.assertEqual([v["name"] for v in m.seznam("share:0:")], ["film.mp4"])
        for rel in ("AppData", "AppData/Roaming/gesla.db", "skrita.mp4", "pagefile.sys"):
            self.assertIsNone(m.razresi("share:0:" + rel), rel)
        self.assertIsNotNone(m.razresi("share:0:film.mp4"))

    def test_ves_disk(self):
        m = link_datoteke.DeljeneMape([], ves_disk=True)
        imena = [v["name"] for v in m.seznam("disk:" + self.dom)]
        self.assertEqual(imena, ["film.mp4"])
        self.assertIsNone(m.razresi("disk:" + os.path.join(self.dom, "AppData", "Roaming", "gesla.db")))
        self.assertIsNotNone(m.razresi("disk:" + os.path.join(self.dom, "film.mp4")))

    def test_izrecno_deljena_skrita_mapa_ostane_dosegljiva(self):
        """Uporabnik je sam delil mapo z atributom Skrito: to je njegova odlocitev, vsebina je dosegljiva."""
        self.atributi["Uporabnik"] = self.SKRITO
        m = link_datoteke.DeljeneMape([self.dom])
        self.assertIsNotNone(m.razresi("share:0:film.mp4"))
        self.assertIsNone(m.razresi("share:0:skrita.mp4"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
