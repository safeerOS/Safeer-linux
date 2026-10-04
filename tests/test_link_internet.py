"""Safeer Internet Gateway, odjemalec (core/link_internet.py): tokovi, nadzor pretoka, konci, napake.

Brez laznih vticnic: krajevni strezniki TCP, referencni ponudnik (tests/pomoc_internet.py) in »zica« z
izhodnima vrstama, ki imata meji pravega sredisca. Najpomembnejsa trditev: tudi kadar program bere
pocasi ali povezava stoji, promet NIKOLI ne preseze 64 okvirjev / 512 KiB v vrsti - pravo sredisce bi
takrat napravo odklopilo iz Linka.
"""
import hashlib
import os
import socket
import threading
import time
import unittest

from core import link_internet as li

import pomoc_internet as pi


def _tunel(odjemalec, vrata, pot=li.POT_MOBILNA, okna=None, cas=5.0, host="127.0.0.1"):
    a, b = socket.socketpair()
    tok, razlog = odjemalec.odpri("tel", host, vrata, b, pot, cas=cas, okna=okna)
    if tok is None:
        a.close()
        b.close()
        return None, None, razlog
    tok.zazeni()
    return a, tok, ""


def _pocakaj(pogoj, rok=5.0):
    konec = time.monotonic() + rok
    while time.monotonic() < konec:
        if pogoj():
            return True
        time.sleep(0.02)
    return pogoj()


class Osnova(unittest.TestCase):
    def setUp(self):
        self.strezniki = []
        self.zice = []

    def tearDown(self):
        for s in self.strezniki:
            s.zapri()
        for z in self.zice:
            z.zapri()

    def streznik(self, obravnava):
        s = pi.Streznik(obravnava)
        self.strezniki.append(s)
        return s

    def povezi(self, zamik=0.0, **kw):
        odjemalec, ponudnik, zica = pi.povezi(zamik, **kw)
        self.zice.append(zica)
        self.assertIsNotNone(odjemalec.vprasaj("tel", 2.0) if kw.get("protokol", 2) >= 2 else {})
        return odjemalec, ponudnik, zica


class Tok(Osnova):
    def test_odmev_v_obe_smeri(self):
        s = self.streznik(pi.odmev)
        odjemalec, ponudnik, zica = self.povezi()
        a, tok, razlog = _tunel(odjemalec, s.vrata)
        self.assertEqual(razlog, "")
        self.assertEqual(tok.vrsta_poti, "cellular")
        a.settimeout(5)
        for sporocilo in (b"zdravo", b"x" * 5000, b"se enkrat"):
            a.sendall(sporocilo)
            prejeto = b""
            while len(prejeto) < len(sporocilo):
                prejeto += a.recv(65536)
            self.assertEqual(prejeto, sporocilo)
        a.close()
        self.assertTrue(tok.pocakaj(5))
        self.assertTrue(_pocakaj(lambda: not ponudnik.tokovi), "ponudnik mora tok zapreti")
        self.assertEqual(odjemalec.stevilo_tokov(), 0)
        self.assertEqual(ponudnik.zahtevane_poti, ["mobile"])

    def test_streznik_spregovori_prvi(self):
        """Pozdrav streznika (SSH, SMTP) mora priti do programa, ceprav program se nic ne poslje."""
        def pozdrav(c):
            c.sendall(b"220 pozdravljen\r\n")
            c.recv(100)
        s = self.streznik(pozdrav)
        odjemalec, _p, _z = self.povezi()
        a, _tok, _ = _tunel(odjemalec, s.vrata)
        a.settimeout(5)
        self.assertEqual(a.recv(100), b"220 pozdravljen\r\n")
        a.close()

    def test_pol_zaprtje_programa_ne_izgubi_odgovora(self):
        """Program poslje zahtevo in zapre svojo smer; odgovor, ki pride po tem, mora dobiti cel."""
        def po_koncu(c):
            zahteva = pi.preberi_vse(c)
            c.sendall(b"prejel " + str(len(zahteva)).encode() + b" bajtov")
        s = self.streznik(po_koncu)
        odjemalec, ponudnik, _z = self.povezi()
        a, tok, _ = _tunel(odjemalec, s.vrata)
        a.sendall(b"a" * 70000)
        a.shutdown(socket.SHUT_WR)
        self.assertEqual(pi.preberi_vse(a, 10), b"prejel 70000 bajtov")
        a.close()
        self.assertTrue(tok.pocakaj(5))
        self.assertTrue(_pocakaj(lambda: not ponudnik.tokovi))

    def test_velik_prenos_dol_je_cel(self):
        podatki = os.urandom(6 * 1024 * 1024)
        s = self.streznik(lambda c: c.sendall(podatki))
        odjemalec, _p, zica = self.povezi()
        a, tok, _ = _tunel(odjemalec, s.vrata)
        prejeto = pi.preberi_vse(a, 60)
        self.assertEqual(hashlib.sha256(prejeto).hexdigest(), hashlib.sha256(podatki).hexdigest())
        self.assertFalse(zica.prekoraceno, "vrsta sredisca: %d okvirjev, %d B" % (zica.dol.najvec_okvirjev, zica.dol.najvec_bajtov))
        self.assertEqual(tok.dol, len(podatki))

    def test_velik_prenos_gor_je_cel(self):
        podatki = os.urandom(3 * 1024 * 1024)
        prejeto = {}

        def sprejmi(c):
            prejeto["vse"] = pi.preberi_vse(c, 60)
            c.sendall(b"ok")
        s = self.streznik(sprejmi)
        odjemalec, _p, zica = self.povezi()
        a, _tok, _ = _tunel(odjemalec, s.vrata)
        a.sendall(podatki)
        a.shutdown(socket.SHUT_WR)
        self.assertEqual(pi.preberi_vse(a, 60), b"ok")
        self.assertEqual(hashlib.sha256(prejeto["vse"]).hexdigest(), hashlib.sha256(podatki).hexdigest())
        self.assertFalse(zica.prekoraceno)

    def test_vec_tokov_hkrati(self):
        s = self.streznik(pi.odmev)
        odjemalec, _p, zica = self.povezi()
        napake = []

        def en(i):
            try:
                a, _tok, razlog = _tunel(odjemalec, s.vrata)
                if a is None:
                    napake.append(razlog)
                    return
                podatki = bytes([i]) * (200 * 1024 + i)
                prejeto = bytearray()

                def beri():
                    a.settimeout(30)
                    while len(prejeto) < len(podatki):
                        kos = a.recv(65536)
                        if not kos:
                            break
                        prejeto.extend(kos)
                bralec = threading.Thread(target=beri)
                bralec.start()
                a.sendall(podatki)
                bralec.join(30)
                if bytes(prejeto) != podatki:
                    napake.append("tok %d: %d/%d" % (i, len(prejeto), len(podatki)))
                a.close()
            except Exception as e:  # noqa: BLE001
                napake.append(repr(e))
        niti = [threading.Thread(target=en, args=(i,)) for i in range(12)]
        for n in niti:
            n.start()
        for n in niti:
            n.join(60)
        self.assertEqual(napake, [])
        self.assertFalse(zica.prekoraceno, "%d okvirjev, %d B" % (zica.dol.najvec_okvirjev, zica.dol.najvec_bajtov))
        self.assertTrue(_pocakaj(lambda: odjemalec.stevilo_tokov() == 0))


class NadzorPretoka(Osnova):
    def test_program_ne_bere_vrsta_sredisca_ostane_pod_mejo(self):
        """Streznik posilja hitro, program ne bere: ponudnik se mora ustaviti pri oknu, ne polniti vrste."""
        podatki = os.urandom(4 * 1024 * 1024)
        s = self.streznik(lambda c: c.sendall(podatki))
        odjemalec, ponudnik, zica = self.povezi()
        a, tok, _ = _tunel(odjemalec, s.vrata)
        time.sleep(1.5)                       # program se ne bere
        self.assertFalse(zica.prekoraceno)
        ptok = next(iter(ponudnik.tokovi.values()))
        self.assertLessEqual(ptok.poslano - ptok.potrjeno, li.OKNO_TOKA + li.NAJVEC_KOS)
        self.assertLess(ptok.poslano, len(podatki), "ponudnik je poslal vse, ceprav program ne bere")
        prejeto = pi.preberi_vse(a, 60)       # zdaj program bere: vse mora priti in nic se ne sme izgubiti
        self.assertEqual(hashlib.sha256(prejeto).hexdigest(), hashlib.sha256(podatki).hexdigest())
        self.assertFalse(zica.prekoraceno)
        self.assertFalse(tok.koncan, "program svoje smeri se ni zaprl: tok mora ostati odprt")
        a.close()
        self.assertTrue(tok.pocakaj(5))

    def test_povezava_stoji_vrsta_ostane_pod_mejo(self):
        """Pot do odjemalca za hip obstane (pocasna naprava): v vrsti sme ostati najvec proracun."""
        podatki = os.urandom(2 * 1024 * 1024)
        s = self.streznik(lambda c: c.sendall(podatki))
        odjemalec, _p, zica = self.povezi()
        zica.dol.ustavljena = True
        prejeto = {}

        def odpri_in_beri():
            a, _tok, razlog = _tunel(odjemalec, s.vrata, cas=10)
            prejeto["vse"] = pi.preberi_vse(a, 60) if a is not None else razlog
        nit = threading.Thread(target=odpri_in_beri)
        nit.start()
        time.sleep(1.0)
        zica.dol.ustavljena = False
        nit.join(60)
        self.assertEqual(len(prejeto["vse"]), len(podatki))
        self.assertFalse(zica.prekoraceno, "%d okvirjev, %d B" % (zica.dol.najvec_okvirjev, zica.dol.najvec_bajtov))
        self.assertLessEqual(zica.dol.najvec_okvirjev, li.NAJVEC_OKVIRJEV + 4)

    def test_majhni_kosi_ne_presezejo_okvirjev(self):
        """Veliko drobnih kosov (tipkanje, igra): stevec okvirjev ustavi posiljatelja pred mejo sredisca."""
        def drobi(c):
            for _ in range(600):
                c.sendall(b"x" * 10)
                time.sleep(0.0005)
        s = self.streznik(drobi)
        odjemalec, _p, zica = self.povezi(zamik=0.002)
        a, _tok, _ = _tunel(odjemalec, s.vrata)
        prejeto = pi.preberi_vse(a, 60)
        self.assertEqual(len(prejeto), 6000)
        self.assertFalse(zica.prekoraceno)
        self.assertLessEqual(zica.dol.najvec_okvirjev, li.NAJVEC_OKVIRJEV + 4)

    def test_potrditev_ni_vec_kot_kosov(self):
        """Prejemnik ne sme poslati vec potrditev, kot je dobil kosov (sicer bi potrditve polnile vrsto)."""
        podatki = os.urandom(1024 * 1024)
        s = self.streznik(lambda c: c.sendall(podatki))
        odjemalec, _p, zica = self.povezi()
        a, _tok, _ = _tunel(odjemalec, s.vrata)
        self.assertEqual(len(pi.preberi_vse(a, 60)), len(podatki))
        self.assertLessEqual(zica.gor.po_vrsti.get("internet.window", 0), zica.dol.po_vrsti.get("internet.data", 0))

    def test_proracun_caka_in_se_sprosti(self):
        p = li.Proracun(bajtov=100, okvirjev=2)
        self.assertTrue(p.zakupi(60, lambda: False))
        self.assertTrue(p.zakupi(30, lambda: False))
        izid = []
        nit = threading.Thread(target=lambda: izid.append(p.zakupi(10, lambda: False)))
        nit.start()
        time.sleep(0.2)
        self.assertEqual(izid, [], "tretji okvir mora cakati (meja okvirjev)")
        p.sprosti(60)
        nit.join(2)
        self.assertEqual(izid, [True])
        self.assertFalse(p.zakupi(90, lambda: True), "preklic med cakanjem")
        self.assertEqual((p.bajtov, p.okvirjev), (40, 2))


class Napake(Osnova):
    def test_dovoljenje_caka(self):
        s = self.streznik(pi.odmev)
        odjemalec, ponudnik, _z = self.povezi(dovoljenje="pending")
        self.assertEqual(odjemalec.znano_stanje("tel")["permission"], "pending")
        a, _tok, razlog = _tunel(odjemalec, s.vrata)
        self.assertIsNone(a)
        self.assertEqual(razlog, "permission_required")
        self.assertEqual(odjemalec.stevilo_tokov(), 0)
        ponudnik.dovoljenje = "allowed"
        a, _tok, razlog = _tunel(odjemalec, s.vrata)
        self.assertEqual(razlog, "")
        a.close()

    def test_cilj_se_ne_odzove(self):
        prost = socket.socket()
        prost.bind(("127.0.0.1", 0))
        vrata = prost.getsockname()[1]
        prost.close()
        odjemalec, _p, _z = self.povezi()
        a, _tok, razlog = _tunel(odjemalec, vrata)
        self.assertIsNone(a)
        self.assertEqual(razlog, "connect_failed")

    def test_ponudnik_molci(self):
        odjemalec, ponudnik, _z = self.povezi()
        ponudnik.molci = True
        zacetek = time.monotonic()
        a, _tok, razlog = _tunel(odjemalec, 1, cas=0.6)
        self.assertIsNone(a)
        self.assertEqual(razlog, "timeout")
        self.assertLess(time.monotonic() - zacetek, 3)
        self.assertEqual(odjemalec.stevilo_tokov(), 0)

    def test_sredisce_zavrne_ker_naprave_ni(self):
        """Zavrnitev sredisca (internet.ack rejected) mora odpiranje koncati takoj, ne po izteku roka."""
        poslano = []

        def oddaj(s):
            poslano.append(s)
            if s["type"] == "internet.open":
                threading.Thread(target=lambda: odjemalec.obdelaj(
                    {"type": "internet.ack", "ref_id": s["id"], "status": "rejected", "error_code": "ni_naprave"})).start()
            return True
        odjemalec = li.InternetPrekLinka(oddaj)
        a, b = socket.socketpair()
        zacetek = time.monotonic()
        tok, razlog = odjemalec.odpri("tel", "example.org", 443, b, cas=10)
        self.assertIsNone(tok)
        self.assertEqual(razlog, "link")
        self.assertLess(time.monotonic() - zacetek, 2)
        self.assertEqual([s["type"] for s in poslano], ["internet.open"], "ponudniku, ki ga ni, ne posiljamo internet.close")
        a.close()

    def test_link_pade_tokovi_se_koncajo(self):
        s = self.streznik(pi.odmev)
        odjemalec, _p, _z = self.povezi()
        a, tok, _ = _tunel(odjemalec, s.vrata)
        odjemalec.povezava_izgubljena()
        self.assertTrue(tok.pocakaj(3))
        a.settimeout(3)
        self.assertEqual(a.recv(10), b"")
        self.assertEqual(odjemalec.protokol("tel"), 0)

    def test_ponudnik_zapre_program_dobi_kar_je_ze_prislo(self):
        def poslji_in_zapri(c):
            c.sendall(b"zadnje besede")
        s = self.streznik(poslji_in_zapri)
        odjemalec, _p, _z = self.povezi()
        a, tok, _ = _tunel(odjemalec, s.vrata)
        self.assertEqual(pi.preberi_vse(a, 5), b"zadnje besede")
        a.close()
        self.assertTrue(tok.pocakaj(5))

    def test_tuja_naprava_ne_more_v_tok(self):
        s = self.streznik(lambda c: time.sleep(0.5))
        odjemalec, _p, _z = self.povezi()
        a, tok, _ = _tunel(odjemalec, s.vrata)
        odjemalec.obdelaj({"type": "internet.data", "sender": "vsiljivec", "stream_id": tok.id, "data": "aGFoYQ=="})
        odjemalec.obdelaj({"type": "internet.close", "sender": "vsiljivec", "stream_id": tok.id})
        a.settimeout(0.3)
        with self.assertRaises(socket.timeout):
            a.recv(10)
        self.assertFalse(tok.koncan)
        a.close()

    def test_pokvarjeni_podatki_koncajo_tok(self):
        s = self.streznik(lambda c: time.sleep(1))
        odjemalec, _p, _z = self.povezi()
        a, tok, _ = _tunel(odjemalec, s.vrata)
        odjemalec.obdelaj({"type": "internet.data", "sender": "tel", "stream_id": tok.id, "data": "ni base64 !!"})
        self.assertTrue(tok.pocakaj(3))
        self.assertEqual(tok.razlog, "data")
        a.close()

    def test_izgubljen_kos_konca_tok_namesto_da_ga_pokvari(self):
        """Povezava med srediscema se sredi prenosa obnovi in en kos se izgubi. Program ne sme dobiti toka z
        luknjo (pokvarjena datoteka brez napake): tok se konca, kar je ze prislo pred luknjo, je pravilno."""
        podatki = os.urandom(600 * 1024)
        s = self.streznik(lambda c: c.sendall(podatki))
        odjemalec, ponudnik, zica = self.povezi()
        kosi = {"n": 0}

        def izgubi(sporocilo):
            if sporocilo.get("type") != "internet.data":
                return False
            kosi["n"] += 1
            return kosi["n"] == 5
        zica.dol.izgubi = izgubi
        a, tok, _ = _tunel(odjemalec, s.vrata)
        prejeto = pi.preberi_vse(a, 20)
        self.assertTrue(tok.pocakaj(5))
        self.assertEqual(tok.razlog, "gap")
        self.assertLess(len(prejeto), len(podatki))
        self.assertEqual(prejeto, podatki[:len(prejeto)], "pred luknjo mora biti tok nepokvarjen")
        self.assertLessEqual(len(prejeto), 4 * li.NAJVEC_KOS, "nic za luknjo ne sme do programa")
        self.assertTrue(_pocakaj(lambda: not ponudnik.tokovi), "ponudnik mora izvedeti, da je tok koncan")
        a.close()

    def test_izgubljen_kos_proti_strezniku(self):
        prejeto = {}

        def sprejmi(c):
            prejeto["vse"] = pi.preberi_vse(c, 20)
        s = self.streznik(sprejmi)
        odjemalec, ponudnik, zica = self.povezi()
        kosi = {"n": 0}

        def izgubi(sporocilo):
            if sporocilo.get("type") != "internet.data":
                return False
            kosi["n"] += 1
            return kosi["n"] == 3
        zica.gor.izgubi = izgubi
        a, tok, _ = _tunel(odjemalec, s.vrata)
        podatki = os.urandom(300 * 1024)
        try:
            a.sendall(podatki)
        except OSError:
            pass
        self.assertTrue(tok.pocakaj(8))
        self.assertTrue(_pocakaj(lambda: "vse" in prejeto))
        dobil = prejeto["vse"]
        self.assertLessEqual(len(dobil), 2 * li.NAJVEC_KOS, "nic za luknjo ne sme do streznika")
        self.assertEqual(dobil, podatki[:len(dobil)], "streznik dobi samo nepokvarjeni zacetek")
        a.close()

    def test_meja_tokov(self):
        odjemalec = li.InternetPrekLinka(lambda s: True)
        pari = []
        for _ in range(li.NAJVEC_TOKOV):
            a, b = socket.socketpair()
            pari.append((a, b))
            odjemalec._tokovi["s%d" % len(pari)] = li.Tok(odjemalec, "s%d" % len(pari), "tel", "h", 1, b, True)
        a, b = socket.socketpair()
        tok, razlog = odjemalec.odpri("tel", "h", 1, b, cas=0.1)
        self.assertIsNone(tok)
        self.assertEqual(razlog, "busy_local")
        for x, y in pari + [(a, b)]:
            x.close()
            y.close()


class Okrevanje(Osnova):
    """Ponovni zagon ene strani, izguba Linka, izgubljena potrditev: tok se ne sme obesiti ali drzati proracuna."""

    def setUp(self):
        super().setUp()
        self._prej = (li.PONOVI_POTRDITEV_S, li.PONOVI_NAJVEC_S)
        li.PONOVI_POTRDITEV_S, li.PONOVI_NAJVEC_S = 0.3, 1.0

    def tearDown(self):
        li.PONOVI_POTRDITEV_S, li.PONOVI_NAJVEC_S = self._prej
        super().tearDown()

    @staticmethod
    def _lije(c):
        """Streznik, ki posilja, dokler kdo bere."""
        kos = b"z" * 65536
        while True:
            c.sendall(kos)

    def test_ponovni_zagon_odjemalca_sprosti_proracun(self):
        """Control se znova zazene sredi prenosov. Stari tokovi na telefonu drzijo proracun naprave; nov
        odjemalec mora kljub temu takoj delati - ponudnik stare tokove zapre ob novi dobi."""
        s = self.streznik(self._lije)
        odjemalec, ponudnik, zica = self.povezi()
        stari = [_tunel(odjemalec, s.vrata) for _ in range(4)]          # programi ne berejo: okna se napolnijo
        self.assertTrue(all(t[1] is not None for t in stari))
        self.assertTrue(_pocakaj(lambda: ponudnik._proracun("pc").bajtov >= li.PRORACUN_NAPRAVE - li.NAJVEC_KOS, 5.0),
                        "proracun naprave bi moral biti poln")
        # »Ponovni zagon«: nov odjemalec na isti zici, stari izgine brez slovesa.
        novi = li.InternetPrekLinka(zica.gor.poslji)
        zica.dol.prejemnik = novi.obdelaj
        self.assertNotEqual(novi._doba, odjemalec._doba)
        odmev = self.streznik(pi.odmev)
        self.assertIsNotNone(novi.vprasaj("tel", 2.0))
        self.assertTrue(_pocakaj(lambda: not ponudnik.tokovi, 3.0), "stari tokovi bi morali biti zaprti ob novi dobi")
        # Zapre jih nova doba; kos, ki je bil se na poti, pa lahko nov odjemalec zavrne tudi sam (»gone«).
        self.assertEqual(len(ponudnik.zaprti), 4)
        self.assertLessEqual(set(ponudnik.zaprti.values()), {"restart", "peer_closed"})
        self.assertEqual(ponudnik._proracun("pc").bajtov, 0)
        a, tok, razlog = _tunel(novi, odmev.vrata)
        self.assertEqual(razlog, "")
        a.settimeout(5)
        a.sendall(b"spet dela")
        self.assertEqual(a.recv(100), b"spet dela")
        tok.prekini("local")
        for stara_vticnica, t, _r in stari:
            t.prekini("local", obvesti=False)
            stara_vticnica.close()
        a.close()

    def test_izguba_linka_zamenja_dobo(self):
        s = self.streznik(pi.odmev)
        odjemalec, ponudnik, zica = self.povezi()
        a, tok, _ = _tunel(odjemalec, s.vrata)
        prej = odjemalec._doba
        odjemalec.povezava_izgubljena()
        self.assertTrue(tok.koncan)
        self.assertEqual(tok.razlog, "link")
        self.assertNotEqual(odjemalec._doba, prej)
        self.assertEqual(len(ponudnik.tokovi), 1, "ponudnik za izgubo se ne ve")
        self.assertIsNotNone(odjemalec.vprasaj("tel", 2.0))
        self.assertTrue(_pocakaj(lambda: not ponudnik.tokovi, 3.0))
        self.assertEqual(list(ponudnik.zaprti.values()), ["restart"])
        a.close()

    def test_izgubljena_potrditev_ne_ustavi_toka(self):
        """Potrditve se na poti izgubijo (sredisce je zamenjalo pot). Brez ponovitve bi prenos obstal pri
        polnem oknu; tih tok potrditev ponovi in prenos se konca."""
        vsebina = os.urandom(900 * 1024)

        def poslji(c):
            c.sendall(vsebina)

        s = self.streznik(poslji)
        odjemalec, ponudnik, zica = self.povezi()
        izgubljenih = []

        def izgubi(sporocilo):
            # Vsako potrditev izgubimo, razen ponovitev (te pridejo po premoru, ko je tok tih).
            if sporocilo.get("type") == "internet.window" and len(izgubljenih) < 6:
                izgubljenih.append(sporocilo.get("bytes"))
                return True
            return False

        zica.gor.izgubi = izgubi
        a, tok, razlog = _tunel(odjemalec, s.vrata)
        self.assertEqual(razlog, "")
        prejeto = pi.preberi_vse(a, 20.0)
        self.assertEqual(len(izgubljenih), 6)
        self.assertEqual(hashlib.sha256(prejeto).hexdigest(), hashlib.sha256(vsebina).hexdigest())
        self.assertFalse(zica.prekoraceno)
        a.close()

    def test_kos_za_neznan_tok_dobi_gone_enkrat(self):
        odjemalec, ponudnik, zica = self.povezi()
        videna = []
        zica.gor.prejemnik = lambda s: videna.append(s) or ponudnik.obdelaj(s)
        kos = {"type": "internet.data", "sender": "tel", "stream_id": "s" + "ab" * 10, "off": 0, "data": "QUJD"}
        odjemalec.obdelaj(dict(kos))
        odjemalec.obdelaj(dict(kos, off=3))
        odjemalec.obdelaj({"type": "internet.window", "sender": "tel", "stream_id": "s" + "ab" * 10, "bytes": 5})
        self.assertTrue(_pocakaj(lambda: any(s.get("type") == "internet.close" for s in videna), 2.0))
        time.sleep(0.2)
        zaprtja = [s for s in videna if s.get("type") == "internet.close"]
        self.assertEqual(len(zaprtja), 1, "za isti tok odgovorimo samo enkrat")
        self.assertEqual(zaprtja[0]["reason"], "gone")
        self.assertEqual(zaprtja[0]["stream_id"], "s" + "ab" * 10)
        self.assertEqual(zaprtja[0]["target"], "tel")

    def test_po_nasem_zaprtju_poznih_kosov_ne_zavracamo_znova(self):
        """Tok smo zaprli sami (internet.close je ze sel); kosi, ki so bili takrat na poti, niso »neznan tok«."""
        s = self.streznik(pi.odmev)
        odjemalec, ponudnik, zica = self.povezi()
        a, tok, _ = _tunel(odjemalec, s.vrata)
        tok.prekini("local")
        pred = zica.gor.po_vrsti.get("internet.close", 0)
        odjemalec.obdelaj({"type": "internet.data", "sender": "tel", "stream_id": tok.id, "off": 0, "data": "QUJD"})
        time.sleep(0.2)
        self.assertEqual(zica.gor.po_vrsti.get("internet.close", 0), pred)
        a.close()

    def test_ponudnik_toka_ne_pozna_vec(self):
        """Telefon se je znova zagnal: toka ne pozna. Tih tok to izve ob ponovitvi potrditve in se konca,
        namesto da program caka do izteka nedejavnosti."""
        s = self.streznik(pi.odmev)
        odjemalec, ponudnik, zica = self.povezi()
        a, tok, _ = _tunel(odjemalec, s.vrata)
        a.settimeout(5)
        a.sendall(b"ena")
        self.assertEqual(a.recv(10), b"ena")
        with ponudnik.zaklep:                       # »ponovni zagon« ponudnika: tokov ni vec, slovesa ni bilo
            ponudnik.tokovi.clear()
            ponudnik.nedavni.clear()
        self.assertTrue(tok.pocakaj(4.0), "tok bi se moral koncati, ko ponudnik pove, da ga ne pozna")
        self.assertEqual(tok.razlog, "gone")
        self.assertEqual(a.recv(10), b"")
        a.close()

    def test_tih_tok_ne_posilja_potrditev_v_nedogled(self):
        """Ponovitve se redcijo (0,3 s, 0,6 s, 1 s ...): tiha povezava ne sme postati stalen promet."""
        s = self.streznik(pi.odmev)
        odjemalec, ponudnik, zica = self.povezi()
        a, tok, _ = _tunel(odjemalec, s.vrata)
        time.sleep(2.6)
        ponovitev = zica.gor.po_vrsti.get("internet.window", 0)
        self.assertGreaterEqual(ponovitev, 2)
        self.assertLessEqual(ponovitev, 4, "0,3 + 0,6 + 1 + 1 s -> najvec stiri ponovitve v 2,6 s")
        self.assertFalse(tok.koncan)
        tok.prekini("local")
        a.close()


class StariPonudnik(Osnova):
    """Safeer OS do 0.5.46 (protokol 1): brez internet.status, brez oken, konec = internet.close."""

    def test_na_vprasanje_ne_odgovori(self):
        odjemalec, _p, _z = pi.povezi(protokol=1)
        self.assertIsNone(odjemalec.vprasaj("tel", 0.4))
        self.assertEqual(odjemalec.protokol("tel"), 0)

    def test_tok_brez_oken_dela(self):
        s = self.streznik(lambda c: c.sendall(b"odgovor " + c.recv(100)))
        odjemalec, _p, zica = pi.povezi(protokol=1)
        self.zice.append(zica)
        a, tok, razlog = _tunel(odjemalec, s.vrata, okna=False)
        self.assertEqual(razlog, "")
        a.sendall(b"vprasanje")
        self.assertEqual(pi.preberi_vse(a, 5), b"odgovor vprasanje")
        self.assertEqual(zica.gor.po_vrsti.get("internet.window", 0), 0)
        self.assertEqual(zica.gor.po_vrsti.get("internet.eof", 0), 0)
        self.assertTrue(tok.pocakaj(5))

    def test_izklopljen_prehod(self):
        odjemalec, _p, zica = pi.povezi(protokol=1, vklopljen=False)
        self.zice.append(zica)
        a, _tok, razlog = _tunel(odjemalec, 80, okna=False)
        self.assertIsNone(a)
        self.assertEqual(razlog, "disabled")

    def test_razlogi_starega_ponudnika(self):
        self.assertEqual(li.razlog_iz("rejected"), "disabled")
        self.assertEqual(li.razlog_iz("private_destination"), "private_destination")
        self.assertEqual(li.razlog_iz("Unable to resolve host \"x\": No address associated with hostname"), "dns_failed")
        self.assertEqual(li.razlog_iz("failed to connect to /1.2.3.4 (port 9) after 10000ms"), "connect_failed")
        self.assertEqual(li.razlog_iz("connect timed out"), "timeout")
        self.assertEqual(li.razlog_iz("no_path"), "no_path")
        self.assertEqual(li.razlog_iz("limit"), "limit")


if __name__ == "__main__":
    unittest.main()
