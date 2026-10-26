"""Lasten pogon Usenet, korak 1 (25. 10. 2026): odjemalec NNTP prek TLS proti laznemu strezniku na 127.0.0.1.

Potrdila ustvari openssl v zacasni mapi (CA, potrdilo za 127.0.0.1 in potrdilo za napacno ime); odjemalec CA zaupa samo
prek izrecnega konteksta v preizkusu. Poverilnice in message-id so izmisljeni. Vsak preizkus streznik ustavi in
povezave zapre (addCleanup); niti streznika so demonske z roki 0,2 s.
"""
import logging
import os
import shutil
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import unittest
import warnings
import zlib
from unittest import mock

from core import usenet_nntp as N, usenet_yenc as Y

UPORABNIK = "preizkus-uporabnik-7f3a"
GESLO = "preizkus-geslo-Qx9"
ID_OK = "clanek-1.AbC@primer.invalid"
ID_PIKA = "pika.Zz@primer.invalid"
ID_NI = "ni-ga.Yy@primer.invalid"
ID_PREKINI = "prekini.Ww@primer.invalid"
ID_ROK = "rok.Vv@primer.invalid"
VSI_ID = (ID_OK, ID_PIKA, ID_NI, ID_PREKINI, ID_ROK)

PODATKI = bytes(range(256)) * 20
CLANKI = {
    ID_OK: Y.kodiraj(PODATKI, "film.mkv"),
    # vrstica s piko na zacetku (kodirnik je ne ubeza): streznik jo podvoji, odjemalec mora podvojitev odstraniti
    ID_PIKA: b"=ybegin line=128 size=3 name=p\r\n.//\r\n=yend size=3 crc32=%08x\r\n" % zlib.crc32(bytes([4, 5, 5])),
}

CA_CNF = """[req]
distinguished_name = dn
prompt = no
x509_extensions = v3_ca
[dn]
CN = Safeer preizkus CA
[v3_ca]
basicConstraints = critical,CA:TRUE
keyUsage = critical,keyCertSign,cRLSign
subjectKeyIdentifier = hash
"""
LIST_CNF = """[req]
distinguished_name = dn
prompt = no
[dn]
CN = lazni-nntp
"""
LIST_EXT = """subjectAltName = %s
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature
extendedKeyUsage = serverAuth
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid
"""


def _openssl(mapa, *argumenti):
    subprocess.run(["openssl", *argumenti], cwd=mapa, check=True, capture_output=True, timeout=60)


def ustvari_potrdila(mapa):
    for ime, vsebina in (("ca.cnf", CA_CNF), ("list.cnf", LIST_CNF), ("prav.ext", LIST_EXT % "IP:127.0.0.1"),
                         ("napacno.ext", LIST_EXT % "DNS:napacno.invalid")):
        with open(os.path.join(mapa, ime), "w") as f:
            f.write(vsebina)
    ec = ("-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes")
    _openssl(mapa, "req", "-x509", "-config", "ca.cnf", *ec, "-keyout", "ca.key", "-out", "ca.pem", "-days", "2")
    for n, ime in enumerate(("prav", "napacno"), 2):
        _openssl(mapa, "req", "-new", "-config", "list.cnf", *ec, "-keyout", ime + ".key", "-out", ime + ".csr")
        _openssl(mapa, "x509", "-req", "-in", ime + ".csr", "-CA", "ca.pem", "-CAkey", "ca.key", "-set_serial", str(n),
                 "-days", "2", "-extfile", ime + ".ext", "-out", ime + ".pem")


def _nntp(telo):
    vrstice = telo.split(b"\r\n")[:-1]
    return b"".join((b"." + v if v.startswith(b".") else v) + b"\r\n" for v in vrstice) + b".\r\n"


class LazniStreznik:
    """Streznik NNTP prek TLS z vnaprej znanimi clanki; vedenje po message-id (430, prekinitev, brez odgovora)."""

    def __init__(self, mapa, potrdilo="prav", pozdrav="200 lazni streznik pripravljen", zapri_po_zahtevi=False,
                 zamuda_gesla=0.0, napacno="481 Authentication failed", meja=None,
                 odgovor_meja="502 Too many connections", gesla_ne_odgovori=False, zamuda_body=0.0):
        self.kontekst = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.kontekst.load_cert_chain(os.path.join(mapa, potrdilo + ".pem"), os.path.join(mapa, potrdilo + ".key"))
        self.pozdrav = pozdrav
        self.zapri_po_zahtevi = zapri_po_zahtevi
        self.zamuda_gesla = zamuda_gesla  # odgovor na PASS pocasi: brez vrat bazena bi vse niti hkrati poslale geslo
        self.napacno = napacno
        self.meja = meja  # najvec hkrati prijavljenih sej (meja povezav racuna)
        self.odgovor_meja = odgovor_meja
        self.gesla_ne_odgovori = gesla_ne_odgovori  # po PASS zapre brez odgovora
        self.zamuda_body = zamuda_body
        self.prijavljenih = 0
        self.ustavi_dogodek = threading.Event()
        self.zaklep = threading.Lock()
        self.sprejete = self.hkrati = self.najvec_hkrati = 0
        self.ukazi = []
        self.vticnik = socket.create_server(("127.0.0.1", 0))
        self.vticnik.settimeout(0.2)
        self.vrata = self.vticnik.getsockname()[1]
        self.niti = [threading.Thread(target=self._sprejemaj, daemon=True)]
        self.niti[0].start()

    def ustavi(self):
        self.ustavi_dogodek.set()
        self.vticnik.close()
        for t in list(self.niti):
            t.join(3)

    def _sprejemaj(self):
        while not self.ustavi_dogodek.is_set():
            try:
                s, _ = self.vticnik.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with self.zaklep:
                self.sprejete += 1
            t = threading.Thread(target=self._obdelaj, args=(s,), daemon=True)
            self.niti.append(t)
            t.start()

    def _vrstica(self, s, buf):
        while b"\r\n" not in buf:
            if self.ustavi_dogodek.is_set():
                return None, buf
            try:
                kos = s.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                return None, buf
            if not kos:
                return None, buf
            buf += kos
        v, _, buf = buf.partition(b"\r\n")
        return v.decode("latin-1"), buf

    def _obdelaj(self, surov):
        prijavljen_seja = False
        with self.zaklep:
            self.hkrati += 1
            self.najvec_hkrati = max(self.najvec_hkrati, self.hkrati)
        try:
            surov.settimeout(5)
            try:
                s = self.kontekst.wrap_socket(surov, server_side=True)
            except (ssl.SSLError, OSError):
                return
            s.settimeout(0.2)
            s.sendall(self.pozdrav.encode() + b"\r\n")
            if not self.pozdrav.startswith("20"):
                return
            buf, uporabnik, prijavljen = b"", None, False
            while True:
                vrstica, buf = self._vrstica(s, buf)
                if vrstica is None:
                    return
                with self.zaklep:
                    self.ukazi.append(vrstica)
                ukaz, _, arg = vrstica.partition(" ")
                if ukaz == "AUTHINFO" and arg.startswith("USER "):
                    uporabnik = arg[5:]
                    s.sendall(b"381 PASS required\r\n")
                elif ukaz == "AUTHINFO" and arg.startswith("PASS "):
                    if self.zamuda_gesla:
                        time.sleep(self.zamuda_gesla)
                    if self.gesla_ne_odgovori:
                        return
                    prijavljen = uporabnik == UPORABNIK and arg[5:] == GESLO
                    if prijavljen:
                        with self.zaklep:
                            if self.meja is not None and self.prijavljenih >= self.meja:
                                prijavljen = False
                            else:
                                self.prijavljenih += 1
                        if not prijavljen:
                            s.sendall(self.odgovor_meja.encode() + b"\r\n")
                            return
                        s.sendall(b"281 Authentication accepted\r\n")
                        prijavljen_seja = True
                    else:
                        s.sendall(self.napacno.encode() + b"\r\n")
                elif ukaz in ("BODY", "STAT"):
                    mid = arg.strip("<>")
                    if not prijavljen:
                        s.sendall(b"480 Authentication required\r\n")
                    elif mid == ID_ROK:
                        self.ustavi_dogodek.wait(10)
                        return
                    elif mid == ID_PREKINI:
                        s.sendall(b"222 0 <%s> body\r\n" % mid.encode() + _nntp(CLANKI[ID_OK])[:3000])
                        return
                    elif mid in CLANKI:
                        if self.zamuda_body:
                            time.sleep(self.zamuda_body)
                        if ukaz == "STAT":
                            s.sendall(b"223 0 <%s>\r\n" % mid.encode())
                        else:
                            s.sendall(b"222 0 <%s> body\r\n" % mid.encode() + _nntp(CLANKI[mid]))
                    else:
                        # streznik ponovi message-id - odjemalec besedila odgovora ne sme prenesti v izjemo ali dnevnik
                        s.sendall(b"430 No such article <%s>\r\n" % mid.encode())
                    if self.zapri_po_zahtevi:
                        return
                elif ukaz == "QUIT":
                    s.sendall(b"205 Bye\r\n")
                    return
                else:
                    s.sendall(b"500 What?\r\n")
        finally:
            with self.zaklep:
                self.hkrati -= 1
                if prijavljen_seja:
                    self.prijavljenih -= 1
            surov.close()


class Zajem(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.besedila = []

    def emit(self, zapis):
        self.besedila.append(zapis.getMessage())


@unittest.skipUnless(shutil.which("openssl"), "brez openssl ni potrdil za lazni streznik")
class Nntp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._mapa = tempfile.TemporaryDirectory()
        ustvari_potrdila(cls._mapa.name)
        cls.ca = os.path.join(cls._mapa.name, "ca.pem")

    @classmethod
    def tearDownClass(cls):
        cls._mapa.cleanup()

    def setUp(self):
        self.zajem = Zajem()
        logging.getLogger("safeer.usenet").addHandler(self.zajem)
        logging.getLogger("safeer.usenet").setLevel(logging.DEBUG)
        self.addCleanup(logging.getLogger("safeer.usenet").removeHandler, self.zajem)
        N._ZAVRNJENI.clear()  # zapah racuna velja za ves proces - vsak preizkus zacne brez njega
        self.addCleanup(N._ZAVRNJENI.clear)

    def kontekst(self):
        return ssl.create_default_context(cafile=self.ca)

    def streznik(self, **k):
        s = LazniStreznik(self._mapa.name, **k)
        self.addCleanup(s.ustavi)
        return s

    def bazen(self, s, **k):
        nastavitve = dict(uporabnik=UPORABNIK, geslo=GESLO, kontekst=self.kontekst(), rok_povezave=5.0, rok=5.0)
        nastavitve.update(k)
        b = N.Bazen("127.0.0.1", s.vrata, **nastavitve)
        self.addCleanup(b.zapri)
        return b

    def napaka(self, fn):
        with self.assertRaises(N.NapakaNntp) as e:
            fn()
        return e.exception

    def brez_skrivnosti(self, *besedila):
        vse = " ".join(list(besedila) + self.zajem.besedila)
        for skrivno in (UPORABNIK, GESLO) + VSI_ID + ("napacno-geslo",):
            self.assertNotIn(skrivno, vse)

    def test_prijava_telo_in_pika(self):
        s = self.streznik()
        b = self.bazen(s, povezav=2)
        telo = b.telo(ID_OK)
        self.assertEqual(telo, CLANKI[ID_OK])
        self.assertEqual(Y.dekodiraj(telo).podatki, PODATKI)
        self.assertEqual(Y.dekodiraj(b.telo("<%s>" % ID_PIKA)).podatki, bytes([4, 5, 5]))
        self.assertEqual(s.sprejete, 1, "druga zahteva gre po isti povezavi")
        self.assertEqual([u for u in s.ukazi if u.startswith("AUTHINFO")],
                         ["AUTHINFO USER " + UPORABNIK, "AUTHINFO PASS " + GESLO])
        self.brez_skrivnosti(repr(b))

    def test_napacno_geslo(self):
        s = self.streznik()
        b = self.bazen(s, geslo="napacno-geslo")
        e = self.napaka(lambda: b.telo(ID_OK))
        self.assertEqual(e.izid, N.PRIJAVA)
        e2 = self.napaka(lambda: b.telo(ID_OK))
        self.assertEqual(e2.izid, N.PRIJAVA)
        self.assertEqual(s.sprejete, 1, "napacnega gesla ne ponavljamo")
        self.brez_skrivnosti(str(e), repr(e), str(e2), repr(b))

    def test_430_povezava_ostane(self):
        s = self.streznik()
        b = self.bazen(s)
        e = self.napaka(lambda: b.telo(ID_NI))
        self.assertEqual((e.izid, e.koda), (N.NI_CLANKA, 430))
        self.assertFalse(b.stat(ID_NI))
        self.assertTrue(b.stat(ID_OK))
        self.assertEqual(b.telo(ID_OK), CLANKI[ID_OK])
        self.assertEqual(s.sprejete, 1)
        self.brez_skrivnosti(str(e), repr(e))

    def test_prekinitev_sredi_body(self):
        s = self.streznik()
        b = self.bazen(s)
        e = self.napaka(lambda: b.telo(ID_PREKINI))
        self.assertEqual(e.izid, N.OMREZJE)
        self.assertEqual(sum(1 for u in s.ukazi if u.startswith("BODY")), 2, "enkrat znova po novi povezavi")
        self.assertEqual(b.telo(ID_OK), CLANKI[ID_OK])
        self.assertEqual(s.sprejete, 3)
        self.brez_skrivnosti(str(e), repr(e))

    def test_stara_povezava_se_zamenja(self):
        s = self.streznik(zapri_po_zahtevi=True)
        b = self.bazen(s)
        self.assertEqual(b.telo(ID_OK), CLANKI[ID_OK])
        time.sleep(0.1)
        self.assertEqual(b.telo(ID_OK), CLANKI[ID_OK])
        self.assertEqual(s.sprejete, 2)

    def test_dve_mrtvi_prosti_povezavi_drugic_sveza(self):
        # Grok 37 C1: po premoru so mrtve vse proste povezave - drugi poskus mora biti nova povezava, ne druga stara.
        s = self.streznik(zapri_po_zahtevi=True, zamuda_body=0.3)
        b = self.bazen(s, povezav=2)
        self.assertEqual(self._hkrati(b, 2, 1), ["ok", "ok"])
        self.assertEqual((s.sprejete, len(b._proste)), (2, 2), "dve prosti povezavi, streznik je zaprl obe")
        time.sleep(0.1)
        self.assertEqual(b.telo(ID_OK), CLANKI[ID_OK])
        self.assertEqual(s.sprejete, 3, "ena stara (mrtva), nato sveza")
        self.assertEqual(len(b._proste), 1, "starejsa prosta je sla stran skupaj z mrtvo")

    def test_nedejavna_prosta_se_zapre(self):
        s = self.streznik()
        b = self.bazen(s)
        with mock.patch.object(N, "PROSTA_NAJDLJE_S", 0.1):
            self.assertEqual(b.telo(ID_OK), CLANKI[ID_OK])
            time.sleep(0.3)
            self.assertEqual(b.telo(ID_OK), CLANKI[ID_OK])
        self.assertEqual(s.sprejete, 2, "nedejavna prosta povezava se ne uporabi")
        self.assertIn("QUIT", s.ukazi, "zaprta vljudno (ponudnik sprosti mesto)")

    def test_rok_zahteve(self):
        s = self.streznik()
        b = self.bazen(s, rok=0.6)
        zacetek = time.monotonic()
        e = self.napaka(lambda: b.telo(ID_ROK))
        trajanje = time.monotonic() - zacetek
        self.assertEqual(e.izid, N.ROK)
        self.assertLess(trajanje, 3.0)
        self.brez_skrivnosti(str(e), repr(e))

    def test_rok_povezave_brez_tls(self):
        tih = socket.create_server(("127.0.0.1", 0))  # sprejme TCP (zaledje), na TLS nikoli ne odgovori
        self.addCleanup(tih.close)
        b = N.Bazen("127.0.0.1", tih.getsockname()[1], kontekst=self.kontekst(), rok_povezave=0.5, rok=0.5)
        self.addCleanup(b.zapri)
        zacetek = time.monotonic()
        self.assertEqual(self.napaka(lambda: b.telo(ID_OK)).izid, N.ROK)
        self.assertLess(time.monotonic() - zacetek, 3.0)

    def _zapri_med(self, b, cakaj=0.4):
        izid, t = [], None

        def delo():
            try:
                b.telo(ID_OK)
                izid.append("ok")
            except N.NapakaNntp as e:
                izid.append(e.izid)
        t = threading.Thread(target=delo)
        t.start()
        time.sleep(cakaj)
        zacetek = time.monotonic()
        b.zapri()
        t.join(8)
        self.assertFalse(t.is_alive())
        return izid, time.monotonic() - zacetek

    def test_zapiranje_prekine_rokovanje_tls(self):
        # Grok 37 C3: streznik sprejme TCP in na TLS ne odgovori - zapri() mora koncati rokovanje takoj, ne po roku.
        tih = socket.create_server(("127.0.0.1", 0))
        self.addCleanup(tih.close)
        b = N.Bazen("127.0.0.1", tih.getsockname()[1], kontekst=self.kontekst(), rok_povezave=10.0, rok=10.0)
        self.addCleanup(b.zapri)
        izid, trajanje = self._zapri_med(b)
        self.assertEqual(izid, [N.ZAPRTO])
        self.assertLess(trajanje, 2.0, "zapiranje ne caka na rok rokovanja (10 s)")

    def test_zapiranje_prekine_tcp_connect(self):
        # Polna vrsta sprejema (backlog 0, nihce ne sprejema): SYN ostane brez odgovora, connect caka.
        poln = socket.create_server(("127.0.0.1", 0), backlog=0)
        self.addCleanup(poln.close)
        vrata = poln.getsockname()[1]
        for _ in range(4):
            c = socket.socket()
            c.setblocking(False)
            self.addCleanup(c.close)
            try:
                c.connect(("127.0.0.1", vrata))
            except BlockingIOError:
                pass
        time.sleep(0.2)
        b = N.Bazen("127.0.0.1", vrata, kontekst=self.kontekst(), rok_povezave=10.0, rok=10.0)
        self.addCleanup(b.zapri)
        izid, trajanje = self._zapri_med(b)
        self.assertEqual(izid, [N.ZAPRTO])
        self.assertLess(trajanje, 2.0, "zapiranje ne caka na rok connect (10 s)")

    def test_napacno_ime_v_potrdilu(self):
        s = self.streznik(potrdilo="napacno")
        e = self.napaka(lambda: self.bazen(s).telo(ID_OK))
        self.assertEqual(e.izid, N.POTRDILO)
        self.assertEqual(s.ukazi, [], "poverilnice ne gredo k strezniku z napacnim potrdilom")
        self.brez_skrivnosti(str(e), repr(e))

    def test_potrdilo_brez_zaupanja(self):
        s = self.streznik()
        b = N.Bazen("127.0.0.1", s.vrata, uporabnik=UPORABNIK, geslo=GESLO, rok_povezave=5.0)  # sistemski CA
        self.addCleanup(b.zapri)
        self.assertEqual(self.napaka(lambda: b.telo(ID_OK)).izid, N.POTRDILO)
        self.assertEqual(s.ukazi, [])

    def test_nevaren_kontekst_zavrnjen(self):
        k = ssl.create_default_context()
        k.check_hostname = False
        with self.assertRaises(ValueError):
            N.Bazen("127.0.0.1", 1, kontekst=k)
        k.verify_mode = ssl.CERT_NONE
        with self.assertRaises(ValueError):
            N.Bazen("127.0.0.1", 1, kontekst=k)
        k = ssl.create_default_context()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            k.minimum_version = ssl.TLSVersion.TLSv1
        N.Bazen("127.0.0.1", 1, kontekst=k)
        self.assertGreaterEqual(k.minimum_version, ssl.TLSVersion.TLSv1_2)
        self.assertGreaterEqual(N.varen_kontekst().minimum_version, ssl.TLSVersion.TLSv1_2)

    def test_neveljaven_id_ne_gre_k_strezniku(self):
        s = self.streznik()
        b = self.bazen(s)
        for mid in ("a@primer.invalid>\r\nQUIT", "ima presledek@x", ""):
            with self.assertRaises(ValueError) as e:
                b.telo(mid)
            self.assertNotIn("QUIT", str(e.exception))
        self.assertEqual(s.sprejete, 0)

    def test_poverilnica_s_crlf(self):
        with self.assertRaises(ValueError) as e:
            N.Bazen("127.0.0.1", 1, uporabnik="x\r\nAUTHINFO", kontekst=self.kontekst())
        self.assertNotIn("AUTHINFO", str(e.exception))

    def test_zaseden_pozdrav_zmanjsa_bazen(self):
        s = self.streznik(pozdrav="502 Too many connections")
        b = self.bazen(s, povezav=3)
        zacetek = time.monotonic()
        self.assertEqual(self.napaka(lambda: b.telo(ID_OK)).izid, N.ZASEDEN)
        self.assertEqual(b.najvec, 1, "nobena druga povezava ni sprejeta: bazen na 1")
        self.assertEqual(self.napaka(lambda: b.telo(ID_OK)).izid, N.ZASEDEN)
        self.assertLess(time.monotonic() - zacetek, 2.0, "premor 60 s je daljsi od roka: brez cakanja")
        self.assertEqual(s.sprejete, 1, "med premorom nobene nove povezave (ni ponavljanja v zanki)")

    # ------------------------------------------------------------ zaklep racuna (Grok 35 Y2, 37 C2; lastnik 26. 10.)

    def _hkrati(self, b, niti=8, zahtev=1, mid=ID_OK):
        izidi, ovira = [], threading.Barrier(niti)

        def delo():
            ovira.wait(5)
            for _ in range(zahtev):
                try:
                    b.telo(mid)
                    izidi.append("ok")
                except N.NapakaNntp as e:
                    izidi.append(e.izid)
        t = [threading.Thread(target=delo) for _ in range(niti)]
        for x in t:
            x.start()
        for x in t:
            x.join(30)
        return izidi

    def _gesel(self, s):
        return sum(1 for u in s.ukazi if u.startswith("AUTHINFO PASS"))

    def test_osem_niti_napacno_geslo_en_poskus(self):
        # Brez vrat bazena (sonda) bi vseh 8 niti hkrati odprlo svojo povezavo in poslalo napacno geslo.
        s = self.streznik(zamuda_gesla=0.3)
        b = self.bazen(s, geslo="napacno-geslo", povezav=8)
        izidi = self._hkrati(b, 8, 3)
        self.assertEqual(izidi, [N.PRIJAVA] * 24)
        self.assertEqual(self._gesel(s), 1, "napacno geslo pride do streznika enkrat")
        self.assertEqual(s.sprejete, 1)
        self.brez_skrivnosti(repr(b))

    def test_zapah_velja_za_racun(self):
        s = self.streznik()
        b = self.bazen(s, geslo="napacno-geslo")
        self.assertEqual(self.napaka(lambda: b.telo(ID_OK)).izid, N.PRIJAVA)
        self.addCleanup(N.dovoli_prijavo_znova, "127.0.0.1", UPORABNIK, "napacno-geslo")
        b2 = self.bazen(s, geslo="napacno-geslo")
        self.assertEqual(self.napaka(lambda: b2.telo(ID_OK)).izid, N.PRIJAVA)
        self.assertEqual((s.sprejete, self._gesel(s)), (1, 1), "nov bazen z istim geslom ne poskusi znova")
        self.assertTrue(N.prijava_zavrnjena("127.0.0.1", UPORABNIK, "napacno-geslo"))
        self.assertEqual(self.bazen(s).telo(ID_OK), CLANKI[ID_OK], "drugo geslo (uporabnik ga je spremenil) gre")
        N.dovoli_prijavo_znova("127.0.0.1", UPORABNIK, "napacno-geslo")  # uporabnik je geslo vpisal znova
        self.assertEqual(self.napaka(lambda: self.bazen(s, geslo="napacno-geslo").telo(ID_OK)).izid, N.PRIJAVA)
        self.assertEqual(self._gesel(s), 3)

    def test_481_za_to_povezavo_je_prijava(self):
        s = self.streznik(napacno="481 Authentication failed for this connection")
        b = self.bazen(s, geslo="napacno-geslo-2", povezav=3)
        self.addCleanup(N.dovoli_prijavo_znova, "127.0.0.1", UPORABNIK, "napacno-geslo-2")
        for _ in range(3):
            self.assertEqual(self.napaka(lambda: b.telo(ID_OK)).izid, N.PRIJAVA)
        self.assertEqual(self._gesel(s), 1)
        self.assertEqual(b.najvec, 3, "zavrnjena prijava ne krci bazena")

    def test_meja_povezav_po_uspeli_prijavi(self):
        # Ponudnik: prevec povezav javi kot napako prijave (480/481) - po uspeli prijavi je to ZASEDEN, ne zapah.
        s = self.streznik(meja=2, odgovor_meja="481 Authentication failed", zamuda_gesla=0.05)
        b = self.bazen(s, povezav=6)
        izidi = self._hkrati(b, 6, 3)
        self.assertEqual(izidi, ["ok"] * 18)
        self.assertEqual(b.najvec, 2, "bazen na sprejete povezave")
        self.assertLessEqual(self._gesel(s), 6, "vsaka povezava najvec ena prijava - brez zanke")
        self.assertLessEqual(s.najvec_hkrati, 6)

    def test_prijava_brez_odgovora_drugic_zapah(self):
        s = self.streznik(gesla_ne_odgovori=True)
        b = self.bazen(s, geslo="ne-odgovori", rok=1.0)
        self.addCleanup(N.dovoli_prijavo_znova, "127.0.0.1", UPORABNIK, "ne-odgovori")
        with mock.patch.object(N, "PREMOR_BREZ_ODPRTIH_S", 0.2):
            self.assertEqual(self.napaka(lambda: b.telo(ID_OK)).izid, N.PRIJAVA)
        self.assertEqual(self._gesel(s), 2, "prvic premor, drugic zapah - nikoli vec")
        self.assertEqual(self.napaka(lambda: b.telo(ID_OK)).izid, N.PRIJAVA)
        self.assertEqual(self._gesel(s), 2)

    def test_nastavi_najvec(self):
        s = self.streznik()
        b = self.bazen(s, povezav=8)
        b.nastavi_najvec(2)
        self.assertEqual(self._hkrati(b, 6, 2), ["ok"] * 12)
        self.assertLessEqual(s.najvec_hkrati, 2)
        self.assertEqual(b.najvec, 2)

    def test_vzporedno_najvec_povezav(self):
        s = self.streznik()
        b = self.bazen(s, povezav=3)
        izidi, napake = [], []

        def delo():
            try:
                izidi.append(b.telo(ID_OK))
            except Exception as e:  # noqa: BLE001
                napake.append(e)
        niti = [threading.Thread(target=delo) for _ in range(12)]
        for t in niti:
            t.start()
        for t in niti:
            t.join(20)
        self.assertEqual(napake, [])
        self.assertEqual(izidi, [CLANKI[ID_OK]] * 12)
        self.assertLessEqual(s.najvec_hkrati, 3)
        self.assertLessEqual(s.sprejete, 3)

    def test_meje_bazena(self):
        k = self.kontekst()
        self.assertEqual(N.Bazen("h", kontekst=k).najvec, N.PRIVZETO_POVEZAV)
        self.assertEqual(N.Bazen("h", povezav=0, kontekst=k).najvec, 1)
        self.assertEqual(N.Bazen("h", povezav=500, kontekst=k).najvec, N.NAJVEC_POVEZAV)
        self.assertEqual((N.PRIVZETO_POVEZAV, N.NAJVEC_POVEZAV, N.VRATA), (8, 50, 563))

    def test_telo_vecje_od_meje(self):
        s = self.streznik()
        b = self.bazen(s)
        with mock.patch.object(N, "NAJVEC_TELO_BAJTOV", 1000):
            self.assertEqual(self.napaka(lambda: b.telo(ID_OK)).izid, N.NAPAKA_PROTOKOLA)

    def test_zapiranje_prekine_zahtevo_v_teku(self):
        s = self.streznik()
        b = self.bazen(s, rok=20.0)
        izid = []

        def delo():
            try:
                b.telo(ID_ROK)
            except N.NapakaNntp as e:
                izid.append(e.izid)
        t = threading.Thread(target=delo)
        t.start()
        for _ in range(100):
            if any(u.startswith("BODY") for u in s.ukazi):
                break
            time.sleep(0.02)
        zacetek = time.monotonic()
        b.zapri()
        t.join(5)
        self.assertFalse(t.is_alive())
        self.assertLess(time.monotonic() - zacetek, 2.0, "zapiranje ne caka na rok zahteve")
        self.assertEqual(izid, [N.ZAPRTO])
        self.assertEqual(s.sprejete, 1, "po zaprtju nobene nove povezave")

    def test_zaprt_bazen(self):
        s = self.streznik()
        b = self.bazen(s)
        b.telo(ID_OK)
        b.zapri()
        self.assertEqual(self.napaka(lambda: b.telo(ID_OK)).izid, N.ZAPRTO)


if __name__ == "__main__":
    unittest.main()
