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
import sys
import tempfile
import threading
import time
import unittest
import warnings
import zlib
from unittest import mock

from core import usenet_nntp as N, usenet_yenc as Y

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPORABNIK = "preizkus-uporabnik-7f3a"
GESLO = "preizkus-geslo-Qx9"
ID_OK = "clanek-1.AbC@primer.invalid"
ID_PIKA = "pika.Zz@primer.invalid"
ID_NI = "ni-ga.Yy@primer.invalid"
ID_PREKINI = "prekini.Ww@primer.invalid"
ID_ROK = "rok.Vv@primer.invalid"
ID_VELIK = "velik.Uu@primer.invalid"
ID_502 = "omejen.Ss@primer.invalid"
VSI_ID = (ID_OK, ID_PIKA, ID_NI, ID_PREKINI, ID_ROK, ID_VELIK, ID_502)

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
                 odgovor_meja="502 Too many connections", gesla_ne_odgovori=False, zamuda_body=0.0, po_kosih=0.0,
                 drug_id=False, ostanek=b""):
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
        self.po_kosih = po_kosih  # telo po 64 KiB z zamikom (hkratna branja vec povezav)
        self.drug_id = drug_id  # 222 z message-id drugega clanka
        self.ostanek = ostanek  # bajti za koncem bloka (brez cevovoda jih ne sme biti)
        self.prijavljenih = 0
        self.geslo = GESLO  # geslo racuna pri ponudniku (zamenjaj_geslo: lastnik ga zamenja med sejo)
        self.rod = 0  # pozabi_seje: prijavljene seje starejsega rodu dobijo pri BODY/STAT 480 (preklop zaledja)
        self.seje = set()
        self.ustavi_dogodek = threading.Event()
        self.zaklep = threading.Lock()
        self.sprejete = self.hkrati = self.najvec_hkrati = 0
        self.ukazi = []
        self.vticnik = socket.create_server(("127.0.0.1", 0))
        self.vticnik.settimeout(0.2)
        self.vrata = self.vticnik.getsockname()[1]
        self.niti = [threading.Thread(target=self._sprejemaj, daemon=True)]
        self.niti[0].start()

    def zamenjaj_geslo(self, novo, zapri_seje=False):
        """Geslo zamenjano pri ponudniku: nove prijave s starim so zavrnjene; obstojece seje ostanejo zive ali jih
        ponudnik zapre."""
        with self.zaklep:
            self.geslo = novo
            seje = list(self.seje)
        for x in seje if zapri_seje else ():
            try:
                socket.socket.shutdown(x, socket.SHUT_RDWR)
            except OSError:
                pass

    def pozabi_seje(self):
        with self.zaklep:
            self.rod += 1

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
        prijavljen_seja, s = False, None
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
            with self.zaklep:
                self.seje.add(s)
            s.sendall(self.pozdrav.encode() + b"\r\n")
            if not self.pozdrav.startswith("20"):
                return
            buf, uporabnik, prijavljen, rod = b"", None, False, self.rod
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
                    prijavljen = uporabnik == UPORABNIK and arg[5:] == self.geslo
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
                        prijavljen_seja, rod = True, self.rod
                    else:
                        s.sendall(self.napacno.encode() + b"\r\n")
                elif ukaz in ("BODY", "STAT"):
                    mid = arg.strip("<>")
                    if not prijavljen or rod != self.rod:
                        s.sendall(b"480 Authentication required\r\n")
                    elif mid == ID_502:
                        s.sendall(b"502 Access restricted\r\n")
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
                        elif self.po_kosih:
                            vse = b"222 0 <%s> body\r\n" % mid.encode() + _nntp(CLANKI[mid])
                            for i in range(0, len(vse), 65536):
                                s.sendall(vse[i:i + 65536])
                                time.sleep(self.po_kosih)
                        else:
                            vrnjen = b"drug.Tt@primer.invalid" if self.drug_id else mid.encode()
                            s.sendall(b"222 0 <%s> body\r\n" % vrnjen + _nntp(CLANKI[mid]) + self.ostanek)
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
                self.seje.discard(s)
            if s is not None:
                s.close()  # seje drzijo SSLSocket - brez tega se vticnik ne zapre ob koncu seje
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
        N._NEZNANE.clear()
        self.addCleanup(N._ZAVRNJENI.clear)
        self.addCleanup(N._NEZNANE.clear)
        # Trajni zapah (Grok 43 C2) vsak preizkus v svoji zacasni datoteki - nikoli v pravi mapi stanja.
        mapa = tempfile.mkdtemp(prefix="usenet-zapah-")
        self.addCleanup(shutil.rmtree, mapa, True)
        self.zapah = os.path.join(mapa, "usenet-zapah")
        self.addCleanup(setattr, N, "_POT_ZAPAHA", N._POT_ZAPAHA)
        N.nastavi_shrambo_zapaha(self.zapah)

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

    def _nov_proces(self, s, geslo):
        """Nov proces (ponovni zagon, sesutje, posodobitev) z istimi poverilnicami: izid prve zahteve."""
        koda = ("import ssl, sys\nsys.path.insert(0, sys.argv[1])\nfrom core import usenet_nntp as N\n"
                "getattr(N, 'nastavi_shrambo_zapaha', lambda p: None)(sys.argv[2])\n"
                "b = N.Bazen('127.0.0.1', int(sys.argv[3]), uporabnik=sys.argv[4], geslo=sys.argv[5], rok_povezave=5.0,"
                " rok=5.0, kontekst=ssl.create_default_context(cafile=sys.argv[6]))\n"
                "try:\n    b.telo(sys.argv[7])\n    print('ok')\nexcept N.NapakaNntp as e:\n    print(e.izid)\n")
        r = subprocess.run([sys.executable, "-I", "-c", koda, KOREN, self.zapah, str(s.vrata), UPORABNIK, geslo,
                            self.ca, ID_OK], capture_output=True, text=True, timeout=60,
                           # Windows: OpenSSL brez SYSTEMROOT ne ustvari konteksta (SSLError 0xa080024, 26. 10. 2026)
                           env={k: v for k, v in (("PATH", os.environ.get("PATH", "")),
                                                  ("SYSTEMROOT", os.environ.get("SYSTEMROOT"))) if v is not None})
        self.assertEqual(r.returncode, 0, r.stderr[-2000:])
        return r.stdout.strip()

    def test_zapah_prezivi_nov_proces(self):
        # Grok 43 C2: zapah je bil samo v pomnilniku procesa - po ponovnem zagonu, sesutju ali posodobitvi je nov proces
        # znova poslal napacno geslo. Zdaj je trajen (odtis, nikoli geslo): nov proces ne poslje AUTHINFO.
        s = self.streznik()
        self.assertEqual(self.napaka(lambda: self.bazen(s, geslo="napacno-geslo-z").telo(ID_OK)).izid, N.PRIJAVA)
        self.assertEqual(self._gesel(s), 1)
        self.assertEqual(self._nov_proces(s, "napacno-geslo-z"), N.PRIJAVA)
        self.assertEqual((s.sprejete, self._gesel(s)), (1, 1), "nov proces: brez povezave in brez AUTHINFO")
        with open(self.zapah, encoding="ascii") as f:
            vsebina = f.read()
        for zasebno in ("napacno-geslo-z", UPORABNIK, "127.0.0.1"):
            self.assertNotIn(zasebno, vsebina)
        if os.name == "posix":  # Windows nima nacina POSIX (st_mode 0o666); dostop ureja ACL profila uporabnika
            self.assertEqual(os.stat(self.zapah).st_mode & 0o777, 0o600)
        self.assertEqual(self._nov_proces(s, GESLO), "ok", "drugo geslo (uporabnik ga je popravil) gre")
        self.assertEqual(self._gesel(s), 2)
        # Odklene ga samo uporabnikov »Preveri« (ali nov vpis poverilnic): en nov poskus, nato spet trajen zapah.
        b = self.bazen(s, geslo="napacno-geslo-z")
        self.assertEqual(self.napaka(b.preveri).izid, N.PRIJAVA)
        self.assertEqual(self._gesel(s), 2, "preveri() brez odklepa ne poskusi")
        self.assertEqual(self.napaka(lambda: b.preveri(odkleni=True)).izid, N.PRIJAVA)
        self.assertEqual(self._gesel(s), 3, "uporabnikov »Preveri«: en nov poskus")
        self.assertEqual(self._nov_proces(s, "napacno-geslo-z"), N.PRIJAVA)
        self.assertEqual(self._gesel(s), 3, "po novi zavrnitvi spet trajen zapah")
        N.dovoli_prijavo_znova("127.0.0.1", UPORABNIK, "napacno-geslo-z")  # nov vpis poverilnic
        self.assertEqual(self._nov_proces(s, "napacno-geslo-z"), N.PRIJAVA)
        self.assertEqual(self._gesel(s), 4, "po novem vpisu en poskus")

    def test_zapah_pokvarjena_datoteka(self):
        with open(self.zapah, "w", encoding="ascii") as f:
            f.write("safeer-usenet-zapah 1\nni zapis\n" + "zz" * 70 + "\n")
        self.assertFalse(N.prijava_zavrnjena("127.0.0.1", UPORABNIK, GESLO))
        N.nastavi_shrambo_zapaha(None)  # brez mape stanja: samo v pomnilniku, brez napake
        s = self.streznik()
        self.assertEqual(self.napaka(lambda: self.bazen(s, geslo="napacno-geslo-p").telo(ID_OK)).izid, N.PRIJAVA)
        self.assertTrue(N.prijava_zavrnjena("127.0.0.1", UPORABNIK, "napacno-geslo-p"))

    def test_zapah_ustavi_vse_bazene_racuna(self):
        # Grok 43 C3: zapah se je v bazenu prebral samo ob nastanku - drug ziv bazen istega racuna je nadaljeval na
        # starih sejah in odpiral nove. Zdaj zavrnjena prijava ustavi vse povezave racuna.
        s = self.streznik()
        b1 = self.bazen(s, povezav=2)
        self.assertEqual(b1.telo(ID_OK), CLANKI[ID_OK])
        s.zamenjaj_geslo("geslo-zamenjano-pri-ponudniku")
        b2 = self.bazen(s)
        self.assertEqual(self.napaka(b2.preveri).izid, N.PRIJAVA)
        pred = (s.sprejete, self._gesel(s))
        self.assertEqual(self.napaka(lambda: b1.telo(ID_OK)).izid, N.PRIJAVA, "zapah ustavi tudi drug bazen racuna")
        self.assertEqual((s.sprejete, self._gesel(s)), pred, "brez nove povezave in gesla")
        self.assertEqual(len(b1._proste), 0, "seje drugega bazena zaprte")

    def test_zapah_po_ponudniku_ne_po_imenu_streznika(self):
        # Grok 43 C3: news.x, eu.news.x in news.x. so isti racun - vsako ime je prej dobilo svoj poskus z napacnim
        # geslom.
        o = N._odtis_racuna("news.primer.invalid", UPORABNIK, "napacno")
        self.assertEqual(o, N._odtis_racuna("EU.News.Primer.Invalid.", UPORABNIK, "napacno"))
        self.assertNotEqual(o, N._odtis_racuna("news.drugi.invalid", UPORABNIK, "napacno"))
        self.assertIs(N._vrata_prijave("news.primer.invalid", UPORABNIK),
                      N._vrata_prijave("ssl.primer.invalid", UPORABNIK))
        N._ZAVRNJENI.add(o)
        self.assertTrue(N.prijava_zavrnjena("ssl.primer.invalid", UPORABNIK, "napacno"))
        self.assertFalse(N.prijava_zavrnjena("ssl.primer.invalid", UPORABNIK, "drugo"))

    def test_480_pri_body_ne_zaklene_pravega_gesla(self):
        # Grok 43 C4: streznik je seje pozabil (preklop zaledja) in pri BODY vrne 480 - prej zapah racuna s pravilnim
        # geslom do ponovnega vpisa. Zdaj gre samo ta povezava stran, nova prijava (pravo geslo) uspe.
        s = self.streznik(zamuda_body=0.1)
        b = self.bazen(s, povezav=4)
        self.assertEqual(self._hkrati(b, 4, 1), ["ok"] * 4)
        s.pozabi_seje()  # vse seje hkrati (vec kot NAPAK_UKAZA_ZAPORED): bazen se ne sme ustaviti
        self.assertEqual(self._hkrati(b, 4, 2), ["ok"] * 8)
        self.assertFalse(N.prijava_zavrnjena("127.0.0.1", UPORABNIK, GESLO))
        self.assertFalse(os.path.exists(self.zapah), "brez trajnega zapaha")

    def test_502_pri_enem_clanku_ne_ustavi_bazena(self):
        # Grok 43 C4: 502 pri enem clanku (omejena skupina) je ustavil ves bazen. Zdaj samo ta zahteva; zaporedni 502
        # (racun brez pravic) bazen ustavijo brez novih prijav v zanki.
        s = self.streznik()
        b = self.bazen(s)
        self.assertEqual(self.napaka(lambda: b.telo(ID_502)).izid, N.DOSTOP)
        self.assertEqual(b.telo(ID_OK), CLANKI[ID_OK])
        self.assertEqual(s.sprejete, 1, "ista povezava ostane")
        for _ in range(N.NAPAK_UKAZA_ZAPORED):
            self.assertEqual(self.napaka(lambda: b.telo(ID_502)).izid, N.DOSTOP)
        self.assertEqual(self.napaka(lambda: b.telo(ID_OK)).izid, N.DOSTOP, "zaporedni 502: bazen ustavljen")
        self.assertEqual((s.sprejete, self._gesel(s)), (1, 1), "brez novih povezav in prijav")

    def test_pozdrav_481_ne_zaklene_racuna(self):
        # Grok 43 C4: 48x v pozdravu (geslo ni bilo poslano) je prej postavil zapah racuna.
        s = self.streznik(pozdrav="481 Authentication required")
        self.assertEqual(self.napaka(lambda: self.bazen(s).telo(ID_OK)).izid, N.PRIJAVA)
        self.assertEqual(self._gesel(s), 0)
        self.assertFalse(N.prijava_zavrnjena("127.0.0.1", UPORABNIK, GESLO), "geslo ni bilo poslano: brez zapaha")

    def test_481_za_to_povezavo_je_prijava(self):
        s = self.streznik(napacno="481 Authentication failed for this connection")
        b = self.bazen(s, geslo="napacno-geslo-2", povezav=3)
        self.addCleanup(N.dovoli_prijavo_znova, "127.0.0.1", UPORABNIK, "napacno-geslo-2")
        for _ in range(3):
            self.assertEqual(self.napaka(lambda: b.telo(ID_OK)).izid, N.PRIJAVA)
        self.assertEqual(self._gesel(s), 1)
        self.assertEqual(b.najvec, 3, "zavrnjena prijava ne krci bazena")

    def test_meja_povezav_po_uspeli_prijavi(self):
        # Ponudnik javi mejo povezav pri AUTHINFO z jasnim besedilom (481 + »too many connections«): ZASEDEN, ne zapah.
        s = self.streznik(meja=2, odgovor_meja="481 Too many connections", zamuda_gesla=0.05)
        b = self.bazen(s, povezav=6)
        izidi = self._hkrati(b, 6, 3)
        self.assertEqual(izidi, ["ok"] * 18)
        self.assertEqual(b.najvec, 2, "bazen na sprejete povezave")
        self.assertLessEqual(self._gesel(s), 6, "vsaka povezava najvec ena prijava - brez zanke")
        self.assertLessEqual(s.najvec_hkrati, 6)

    def test_menjava_gesla_med_sejo_ena_napacna_prijava(self):
        # Grok 43 C1: lastnik zamenja geslo pri ponudniku, stare seje ostanejo zive. Prej je bil »481 Authentication
        # failed« po uspeli prijavi meja povezav: vsaka nova povezava je poslala staro geslo (4 hkrati, nato ena na
        # 10 min).
        s = self.streznik(zamuda_body=0.3, zamuda_gesla=0.05)
        b = self.bazen(s, povezav=6)
        self.assertEqual(self._hkrati(b, 2, 1), ["ok", "ok"])
        pred = self._gesel(s)
        s.zamenjaj_geslo("geslo-zamenjano-pri-ponudniku")
        with mock.patch.object(N, "RAST_BAZENA_S", 0.2), mock.patch.object(N, "PREMOR_OD_S", 0.1):
            izidi = self._hkrati(b, 6, 3)
        self.assertEqual(self._gesel(s) - pred, 1, "staro geslo gre k strezniku enkrat")
        self.assertIn(N.PRIJAVA, izidi)
        self.assertTrue(N.prijava_zavrnjena("127.0.0.1", UPORABNIK, GESLO))
        self.assertEqual(self.napaka(lambda: b.telo(ID_OK)).izid, N.PRIJAVA)
        self.assertEqual(self._gesel(s) - pred, 1)

    def test_menjava_gesla_ponudnik_zapre_seje(self):
        # Ponudnik ob menjavi gesla zapre seje: vse niti hkrati dobijo mrtvo povezavo in odprejo svezo - geslo pa gre
        # skozi vrata prijave ena naenkrat, zato staro geslo do streznika enkrat.
        s = self.streznik(zamuda_gesla=0.05)
        b = self.bazen(s, povezav=8)
        self.assertEqual(self._hkrati(b, 8, 1), ["ok"] * 8)
        pred = self._gesel(s)
        s.zamenjaj_geslo("geslo-zamenjano-pri-ponudniku", zapri_seje=True)
        time.sleep(0.1)
        izidi = self._hkrati(b, 8, 3)
        self.assertEqual(self._gesel(s) - pred, 1, "staro geslo gre k strezniku enkrat")
        self.assertIn(N.PRIJAVA, izidi)
        self.assertNotIn("ok", izidi)

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

    def test_proracun_teles(self):
        # Grok 37 C7 / 35 Y3: 6 hkratnih clankov po ~1,25 MiB v proracunu 3 MiB. Merimo vsoto medpomnilnikov vseh
        # povezav ob vsakem branju: brez proracuna ~7 MiB, s proracunom osnove (3 x 0,5) + rast (1,25) + statusne
        # vrstice.
        CLANKI[ID_VELIK] = Y.kodiraj(bytes(range(256)) * 4800, "velik.mkv")
        self.addCleanup(CLANKI.pop, ID_VELIK)
        s = self.streznik(po_kosih=0.01)
        vrh = [0]
        izvirno = N.Povezava._beri

        def beri(povezava, konec):
            izvirno(povezava, konec)
            vrh[0] = max(vrh[0], sum(len(x._medpomnilnik) for x in list(b._v_rabi)))
        with mock.patch.object(N, "NAJVEC_TELO_BAJTOV", 1536 * 1024), \
                mock.patch.object(N, "OSNOVA_TELESA", 512 * 1024), mock.patch.object(N.Povezava, "_beri", beri):
            b = self.bazen(s, povezav=6, rok=20.0, proracun_bajtov=3 * 1024 * 1024)
            izidi = self._hkrati(b, 6, 1, ID_VELIK)
        self.assertEqual(izidi, ["ok"] * 6, "brez zastoja (prej: zasezanje po delih je zaklenilo do roka)")
        self.assertLessEqual(b.proracun.najvec_zasedeno, 3 * 1024 * 1024)
        self.assertLessEqual(vrh[0], 3 * 1024 * 1024 + 6 * 256 * 1024, "vsota medpomnilnikov v proracunu")
        self.assertEqual(b.proracun.zasedeno, 0, "vse sproscen")
        self.assertGreater(s.najvec_hkrati, 1)

    def test_proracun_rok(self):
        with mock.patch.object(N, "NAJVEC_TELO_BAJTOV", 1024 * 1024), \
                mock.patch.object(N, "OSNOVA_TELESA", 512 * 1024):
            p = N.Proracun(0)  # najmanj ena osnova in rast
            self.assertTrue(p.zasezi(time.monotonic() + 1))
            zacetek = time.monotonic()
            self.assertFalse(p.zasezi(time.monotonic() + 0.2), "druga osnova ni prostora do roka")
            self.assertLess(time.monotonic() - zacetek, 1.0)
            self.assertTrue(p.rasti(time.monotonic() + 0.1))
            self.assertFalse(p.rasti(time.monotonic() + 0.1), "en zeton rasti")
            p.sprosti(True)
            self.assertEqual(p.zasedeno, 0)
            self.assertTrue(p.zasezi(time.monotonic() + 0.1))

    def test_dolga_vrstica_v_enem_branju(self):
        self.assertEqual(N.NAJVEC_VRSTICA_BAJTOV, 4096)
        s = self.streznik(pozdrav="200 " + "x" * 9000)
        self.assertEqual(self.napaka(lambda: self.bazen(s).telo(ID_OK)).izid, N.NAPAKA_PROTOKOLA)

    def test_napacen_gostitelj_ali_vrata(self):
        # Grok 37 C8: prej OverflowError/UnicodeError/ValueError mimo NapakaNntp; poverilnica v gostitelju ne gre v DNS.
        k = self.kontekst()
        for g, v in (("uporabnik:" + GESLO + "@news.primer.invalid", 563), ("", 563), ("a b", 563), ("x" * 254, 563),
                     ("news.primer.invalid", 0), ("news.primer.invalid", 70000), ("a" * 64 + ".invalid", 563)):
            with self.assertRaises(ValueError) as e:
                N.Bazen(g, v, kontekst=k)
            self.assertNotIn(GESLO, str(e.exception))
        N.Bazen("::1", 563, kontekst=k)
        N.Bazen("news.primer.invalid", 443, kontekst=k)

    def test_dnevnik_brez_gostitelja(self):
        s = self.streznik()
        self.napaka(lambda: self.bazen(s, geslo="napacno-geslo-d").telo(ID_OK))
        self.assertTrue(self.zajem.besedila)
        self.assertFalse([b for b in self.zajem.besedila if "127.0.0.1" in b], "ponudnik je zaseben podatek")

    def test_odgovor_za_drug_clanek(self):
        s = self.streznik(drug_id=True)
        b = self.bazen(s)
        self.assertEqual(self.napaka(lambda: b.telo(ID_OK)).izid, N.NAPAKA_PROTOKOLA)
        self.assertEqual(s.sprejete, 1, "brez ponovitve (napaka protokola na sveži povezavi)")
        self.assertEqual(len(b._proste), 0, "neusklajena povezava ne gre v bazen")

    def test_ostanek_za_koncem_zapre_povezavo(self):
        s = self.streznik(ostanek=b"223 0 <x@primer.invalid>\r\n")
        b = self.bazen(s)
        self.assertEqual(b.telo(ID_OK), CLANKI[ID_OK])
        self.assertEqual(len(b._proste), 0, "povezava z ostankom ne gre v bazen")
        self.assertEqual(b.telo(ID_OK), CLANKI[ID_OK])
        self.assertEqual(s.sprejete, 2)

    def test_preveri_vedno_sveza(self):
        s = self.streznik()
        b = self.bazen(s)
        b.telo(ID_OK)
        b.preveri()
        self.assertEqual(s.sprejete, 2, "»Preizkusi povezavo« ne gre po stari prosti povezavi")

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
