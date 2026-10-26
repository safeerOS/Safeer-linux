"""Preizkusi popravkov G1-G6 iz pregleda 77 (naloga 110) za core/usenet_ponudnik.py.

Samozadostni: modul se nalozi iz datoteke v locen paket z laznima usenet_nntp in skrivnosti, zato preizkusi ne
odpirajo omrezja, ne rabijo sistemske zbirke in ne posegajo v pravi usenet_nntp. Lazni usenet_nntp posnema samo javni
obris, ki ga modul uporablja (zapah po gostitelju+uporabniku+geslu ali po racunu). Vsak preizkus G dobi svezo kopijo
modula, da stanje v pomnilniku (omejitev 1/min, register bazenov) ne tece med preizkusi."""

import hashlib
import importlib.util
import os
import ssl
import sys
import threading
import types
from pathlib import Path

import pytest

_MODUL = Path(__file__).resolve().parents[1] / "core" / "usenet_ponudnik.py"
_PAKET = "_naloga110_usenet"
PRAVO = "pravo-geslo1"
NAPACNO = "napacno-geslo1"
DRUGO = "drugo-geslo1"


class _Streznik:
    """Lazni streznik: steje poslane AUTHINFO PASS in hkrati odprte povezave na racun (brez gesel)."""

    def __init__(self):
        self.gesla = {}
        self.poslan_pass = 0
        self.odprte = 0
        self.najvec_hkrati = 0
        self.ob_prijavi = None

    def odpri(self):
        self.odprte += 1
        self.najvec_hkrati = max(self.najvec_hkrati, self.odprte)

    def zapri(self):
        self.odprte -= 1

    def prijava(self, uporabnik, geslo):
        self.poslan_pass += 1
        if self.ob_prijavi is not None:
            self.ob_prijavi()
        return self.gesla.get(uporabnik) == geslo


def _lazni_nntp(zapah_na_racun=False):
    n = types.ModuleType(_PAKET + ".usenet_nntp")
    n.VRATA, n.PRIVZETO_POVEZAV, n.NAJVEC_POVEZAV = 563, 8, 50
    n.PRIJAVA, n.ZASEDEN, n.DOSTOP = "PRIJAVA", "ZASEDEN", "DOSTOP"
    n.FAZA_POVEZAVA, n.FAZA_PRIJAVA = "povezava", "prijava"
    n.streznik = _Streznik()
    n.zapah = set()
    n.klici_dovoli = 0
    n.bazeni = []

    class NapakaNntp(Exception):
        def __init__(self, izid):
            super().__init__(izid)
            self.izid = izid

    n.NapakaNntp = NapakaNntp

    def _k(g, u, geslo):
        if zapah_na_racun:
            return (str(g).lower(), u)
        return (str(g).lower(), u, hashlib.sha256(str(geslo).encode()).hexdigest())

    def prijava_zavrnjena(g, u, geslo):
        return geslo is not None and _k(g, u, geslo) in n.zapah

    def dovoli_prijavo_znova(g, u, geslo):
        n.klici_dovoli += 1
        n.zapah.discard(_k(g, u, geslo))

    def varna_poverilnica(s):
        return isinstance(s, str) and 0 < len(s) <= 512 and not any(c in s for c in "\r\n\x00")

    def _preveri_gostitelja(g, vrata):
        if not isinstance(g, str) or not g or any(c in g for c in " /@\t\r\n"):
            raise ValueError("neveljaven gostitelj")

    def ponudnik(g):
        return ".".join(str(g).lower().split(".")[-2:])  # racun pri ponudniku: zadnji dve oznaki

    def varen_kontekst(k=None):
        k = ssl.create_default_context() if k is None else k
        if k.verify_mode != ssl.CERT_REQUIRED or not k.check_hostname:
            raise ValueError("kontekst brez preverbe potrdila")
        return k

    class Bazen:
        # Namenoma NE preverja konteksta: pravi Bazen tega morda ne naredi (pregled 77 G3, NEPREVERJENO).
        def __init__(self, gostitelj, vrata, uporabnik, geslo, povezav=8, kontekst=None):
            self.g, self.u, self.kljuc = gostitelj, uporabnik, _k(gostitelj, uporabnik, geslo)
            self.kontekst = kontekst
            self._najvec = min(int(povezav), n.NAJVEC_POVEZAV)
            self._odprte = 0
            self.ustavljen = None
            n.bazeni.append(self)

        def nastavi_najvec(self, povezav):
            self._najvec = min(int(povezav), n.NAJVEC_POVEZAV)

        def zahtevaj(self):
            """Odpre eno povezavo, ce bazen se sme (kot zahteva predvajanja)."""
            if self._odprte >= self._najvec:
                return False
            self._odprte += 1
            n.streznik.odpri()
            return True

        def _pred_prijavo(self):
            if self.kljuc in n.zapah:
                raise NapakaNntp(n.PRIJAVA)

        def _po_prijavi(self, izid):
            if izid == n.PRIJAVA:
                n.zapah.add(self.kljuc)

        def _ustavi(self, razlog, racun=False):
            self.ustavljen = razlog

        def zapri(self):
            while self._odprte:
                self._odprte -= 1
                n.streznik.zapri()

    class Povezava:
        def __init__(self, gostitelj, vrata, uporabnik, geslo, kontekst, pred_prijavo=None, po_prijavi=None):
            self.u, self.geslo = uporabnik, geslo
            self.pred, self.po = pred_prijavo, po_prijavi
            self.faza = None
            self.odprta = False

        def odpri(self):
            self.faza = n.FAZA_POVEZAVA
            n.streznik.odpri()
            self.odprta = True
            self.pred()
            self.faza = n.FAZA_PRIJAVA
            ok = n.streznik.prijava(self.u, self.geslo)
            self.po(None if ok else n.PRIJAVA)
            if not ok:
                raise NapakaNntp(n.PRIJAVA)

        def zapri(self, vljudno=False):
            if self.odprta:
                self.odprta = False
                n.streznik.zapri()

    for ime, v in dict(locals()).items():
        if ime not in ("n", "zapah_na_racun") and not ime.startswith("__"):
            setattr(n, ime, v)
    return n


def _lazne_skrivnosti():
    s = types.ModuleType(_PAKET + ".sporocila.skrivnosti")
    s.zbirka = {}
    s.napaka = False

    def shrani(k, v):
        if s.napaka:
            raise RuntimeError("zbirka zaklenjena")
        s.zbirka[k] = v
        return True

    s.shrani = shrani
    s.preberi = lambda k: s.zbirka.get(k)
    s.pozabi = lambda k: s.zbirka.pop(k, None)
    return s


def _nalozi(monkeypatch, zapah_na_racun=False):
    paket = types.ModuleType(_PAKET)
    paket.__path__ = []
    spor = types.ModuleType(_PAKET + ".sporocila")
    spor.__path__ = []
    nntp, skr = _lazni_nntp(zapah_na_racun), _lazne_skrivnosti()
    paket.usenet_nntp, paket.sporocila, spor.skrivnosti = nntp, spor, skr
    for ime, mod in ((_PAKET, paket), (_PAKET + ".usenet_nntp", nntp), (_PAKET + ".sporocila", spor),
                     (_PAKET + ".sporocila.skrivnosti", skr)):
        monkeypatch.setitem(sys.modules, ime, mod)
    spec = importlib.util.spec_from_file_location(_PAKET + ".usenet_ponudnik", _MODUL)
    m = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, m)
    spec.loader.exec_module(m)
    ura = [1000.0]
    m._ura = lambda: ura[0]
    nntp.streznik.gesla["uporabnik1"] = PRAVO
    return types.SimpleNamespace(m=m, nntp=nntp, skr=skr, ura=ura, srv=nntp.streznik)


@pytest.fixture(params=["zapah_na_geslo", "zapah_na_racun"])
def o2(request, monkeypatch):
    """Obe mozni pomeni zapaha v pravem usenet_nntp (NEPREVERJENO, kateri velja)."""
    return _nalozi(monkeypatch, zapah_na_racun=request.param == "zapah_na_racun")


@pytest.fixture
def o(monkeypatch):
    return _nalozi(monkeypatch)


@pytest.fixture
def pot(tmp_path):
    return str(tmp_path / "usenet.json")


def P(o, **k):
    k.setdefault("gostitelj", "news.example")
    k.setdefault("uporabnik", "uporabnik1")
    return o.m.Ponudnik(**k)


def Q(o, **k):
    return P(o, gostitelj="192.0.2.1", **k)  # drug racun (dokumentacijski naslov), isti uporabnik1


def _v_niti(fn, *a, **k):
    izid = {}

    def tek():
        try:
            izid["v"] = fn(*a, **k)
        except BaseException as e:  # noqa: B036 - prenesemo v glavno nit
            izid["e"] = e

    t = threading.Thread(target=tek)
    t.start()
    t.join(10)
    assert not t.is_alive()
    if "e" in izid:
        raise izid["e"]
    return izid["v"]


def _preveri(o, p, geslo, pot_=None):
    return _v_niti(o.m.preveri_ponudnika, p, geslo, pot_nastavitev=pot_)


def _poskusi_shrani(o, p, geslo, pot_):
    """Vmesnik ob »Shrani«: zavrnjen vpis je pricakovan izid, ne napaka preizkusa."""
    try:
        return o.m.shrani_ponudnika(p, geslo, pot_)
    except o.m.NapakaPonudnika as e:
        return e.razlog


def _zavrni(o, p, pot_):
    o.m.shrani_ponudnika(p, NAPACNO, pot_)
    assert _preveri(o, p, NAPACNO, pot_) == o.m.NE_VELJA
    assert o.srv.poslan_pass == 1


def _napolni(b):
    while b.zahtevaj():
        pass


# ------------------------------------------------------------------ G1

def test_g1a_isto_zavrnjeno_geslo_preveri_zaklenjen_en_pass(o2, pot):
    o, p = o2, P(o2)
    _zavrni(o, p, pot)
    _poskusi_shrani(o, p, NAPACNO, pot)  # isto zavrnjeno geslo znova
    assert _preveri(o, p, NAPACNO, pot) == o.m.ZAKLENJEN
    o.ura[0] += 3600  # tudi po iztekli minuti
    assert _preveri(o, p, NAPACNO, pot) == o.m.ZAKLENJEN
    assert o.srv.poslan_pass == 1


def test_g1b_isto_zavrnjeno_geslo_ustvari_bazen_zaklenjen(o2, pot):
    o, p = o2, P(o2)
    _zavrni(o, p, pot)
    _poskusi_shrani(o, p, NAPACNO, pot)
    with pytest.raises(o.m.NapakaPonudnika) as e:
        o.m.ustvari_bazen(p)
    assert e.value.razlog == o.m.RACUN_ZAKLENJEN
    assert o.srv.poslan_pass == 1


def test_g1_sedem_klikov_shrani_preveri_en_pass(o2, pot):
    o, p = o2, P(o2)
    o.m.shrani_ponudnika(p, NAPACNO, pot)
    izidi = []
    for _ in range(7):
        _poskusi_shrani(o, p, NAPACNO, pot)
        izidi.append(_preveri(o, p, NAPACNO, pot))
    assert izidi == [o.m.NE_VELJA] + [o.m.ZAKLENJEN] * 6
    assert o.srv.poslan_pass == 1


def test_g1_vpis_istega_zavrnjenega_gesla_jasen_razlog_brez_gesla(o2, pot):
    o, p = o2, P(o2)
    _zavrni(o, p, pot)
    klici = o.nntp.klici_dovoli
    with pytest.raises(o.m.NapakaPonudnika) as e:
        o.m.shrani_ponudnika(p, NAPACNO, pot)
    assert e.value.razlog == o.m.GESLO_ZAVRNJENO
    assert NAPACNO not in str(e.value) + repr(e.value) and "uporabnik1" not in str(e.value)
    assert o.nntp.klici_dovoli == klici  # zapah ni bil odklenjen
    assert o.m.GESLO_ZAVRNJENO in o.m.BESEDILA_IZIDOV


def test_g1_drugo_geslo_odklene(o2, pot):
    # Regresija: sprememba gesla mora se vedno odkleniti zapah in dovoliti takojsnjo preverbo.
    o, p = o2, P(o2)
    _zavrni(o, p, pot)
    o.m.shrani_ponudnika(p, PRAVO, pot)
    assert _preveri(o, p, PRAVO, pot) == o.m.VELJA
    assert o.srv.poslan_pass == 2
    o.m.ustvari_bazen(p).zapri()


def test_g1_isto_veljavno_geslo_ne_ponastavi_minute(o, pot):
    p = P(o)
    o.m.shrani_ponudnika(p, PRAVO, pot)
    assert _preveri(o, p, PRAVO, pot) == o.m.VELJA
    o.m.shrani_ponudnika(p, PRAVO, pot)  # npr. sprememba imena prek starega obrazca
    assert _preveri(o, p, PRAVO, pot) == o.m.PREPOGOSTO
    assert o.srv.poslan_pass == 1


def test_g1_posodobi_nastavitve_brez_gesla_ne_odklene(o2, pot):
    o, p = o2, P(o2)
    _zavrni(o, p, pot)
    klici = o.nntp.klici_dovoli
    nov = o.m.posodobi_nastavitve(pot, ime="Doma", najvec_povezav=3)
    assert (nov.ime, nov.najvec_povezav) == ("Doma", 3)
    assert o.m.preberi_ponudnika(pot) == nov
    assert o.nntp.klici_dovoli == klici
    assert o.m.stanje_za_vmesnik(pot)["stanje"] == o.m.NE_VELJA  # izid preverbe ostane
    assert _preveri(o, nov, NAPACNO, pot) == o.m.ZAKLENJEN
    with pytest.raises(o.m.NapakaPonudnika) as e:
        o.m.ustvari_bazen(nov)
    assert e.value.razlog == o.m.RACUN_ZAKLENJEN
    assert o.srv.poslan_pass == 1


def test_g1_posodobi_nastavitve_neveljavno_in_brez_ponudnika(o, pot):
    with pytest.raises(o.m.NapakaPonudnika) as e:
        o.m.posodobi_nastavitve(pot, ime="x")
    assert e.value.razlog == o.m.NI_PONUDNIKA
    o.m.shrani_ponudnika(P(o), PRAVO, pot)
    with pytest.raises(ValueError):
        o.m.posodobi_nastavitve(pot, najvec_povezav=0)
    assert o.m.preberi_ponudnika(pot).najvec_povezav == o.m.PRIVZETO_POVEZAV


def test_g1_pozabi_in_isto_zavrnjeno_geslo_ne_odklene(o, pot):
    p = P(o)
    _zavrni(o, p, pot)
    o.m.pozabi_ponudnika(pot)
    _poskusi_shrani(o, p, NAPACNO, pot)
    o.ura[0] += 3600
    assert _preveri(o, p, NAPACNO, pot) == o.m.ZAKLENJEN
    assert o.srv.poslan_pass == 1


def test_g1_vmesno_drugo_zavrnjeno_geslo_ne_odklene_prvega(o, pot):
    p = P(o)
    _zavrni(o, p, pot)
    o.m.shrani_ponudnika(p, DRUGO, pot)
    assert _preveri(o, p, DRUGO, pot) == o.m.NE_VELJA
    assert o.srv.poslan_pass == 2
    _poskusi_shrani(o, p, NAPACNO, pot)
    o.ura[0] += 3600
    assert _preveri(o, p, NAPACNO, pot) == o.m.ZAKLENJEN
    assert o.srv.poslan_pass == 2


# ------------------------------------------------------------------ G2

GNEZDENO = b"[" * 60000


@pytest.mark.parametrize("vsebina", [GNEZDENO, b'{"verzija": 1, "ponudnik": ' + b"[" * 60000],
                         ids=["gnezden", "gnezden_v_zapisu"])
def test_g2_globoko_gnezden_json(o, pot, vsebina):
    with open(pot, "wb") as f:
        f.write(vsebina)
    assert o.m.preberi_ponudnika(pot) is None
    assert o.m.stanje_za_vmesnik(pot)["vpisan"] is False
    with pytest.raises(o.m.NapakaPonudnika):
        o.m.posodobi_nastavitve(pot, ime="x")
    o.m.pozabi_ponudnika(pot)  # uporabnik pokvarjeno datoteko odstrani
    assert not os.path.exists(pot)
    with open(pot, "wb") as f:
        f.write(vsebina)
    assert o.m.shrani_ponudnika(P(o), PRAVO, pot) is True  # ali jo popravi z novim vpisom
    assert o.m.preberi_ponudnika(pot) == P(o)


# ------------------------------------------------------------------ G3

def _brez_preverbe(nacin):
    k = ssl.create_default_context()
    k.check_hostname = False
    if nacin == "cert_none":
        k.verify_mode = ssl.CERT_NONE
    return k


@pytest.mark.parametrize("nacin", ["cert_none", "brez_imena"])
def test_g3_ustvari_bazen_zavrne_kontekst_brez_preverbe(o, pot, nacin):
    o.m.shrani_ponudnika(P(o), PRAVO, pot)
    with pytest.raises(ValueError):
        o.m.ustvari_bazen(P(o), kontekst=_brez_preverbe(nacin))
    assert o.nntp.bazeni == [] and o.srv.najvec_hkrati == 0 and o.srv.poslan_pass == 0


def test_g3_varen_kontekst_gre_v_bazen(o, pot):
    o.m.shrani_ponudnika(P(o), PRAVO, pot)
    k = ssl.create_default_context()
    b = o.m.ustvari_bazen(P(o), kontekst=k)
    assert b.kontekst is k and b.kontekst.verify_mode == ssl.CERT_REQUIRED
    b.zapri()


# ------------------------------------------------------------------ G4

def test_g4_dva_bazena_ne_presezeta_meje_racuna(o, pot):
    p = P(o, najvec_povezav=3)
    o.m.shrani_ponudnika(p, PRAVO, pot)
    b1 = o.m.ustvari_bazen(p)
    _napolni(b1)
    b2 = o.m.ustvari_bazen(p)
    _napolni(b2)
    assert o.srv.najvec_hkrati == 3
    assert b1 is b2
    b1.zapri()
    b3 = o.m.ustvari_bazen(p)  # zaprt bazen ne zaseda vec racuna
    assert b3 is not b1
    _napolni(b3)
    assert o.srv.odprte == 3
    b3.zapri()


def test_g4_nastavi_najvec_ne_gre_cez_mejo(o, pot):
    p = P(o, najvec_povezav=3)
    o.m.shrani_ponudnika(p, PRAVO, pot)
    b = o.m.ustvari_bazen(p)
    b.nastavi_najvec(40)
    _napolni(b)
    assert o.srv.najvec_hkrati == 3
    b.zapri()


def test_g4_preverba_med_predvajanjem_ne_preseze_meje(o, pot):
    p = P(o, najvec_povezav=3)
    o.m.shrani_ponudnika(p, PRAVO, pot)
    b = o.m.ustvari_bazen(p)
    _napolni(b)
    assert _preveri(o, p, PRAVO, pot) == o.m.V_UPORABI
    assert o.srv.najvec_hkrati == 3 and o.srv.poslan_pass == 0
    b.zapri()
    assert _preveri(o, p, PRAVO, pot) == o.m.VELJA  # minuta ni bila porabljena
    assert o.srv.najvec_hkrati == 3


def test_g4_bazen_med_preverbo_dobi_povezavo_manj(o, pot):
    p = P(o, najvec_povezav=3)
    o.m.shrani_ponudnika(p, PRAVO, pot)
    bazen = []

    def med_prijavo():
        b = o.m.ustvari_bazen(p)
        _napolni(b)
        bazen.append(b)

    o.srv.ob_prijavi = med_prijavo
    assert _preveri(o, p, PRAVO, pot) == o.m.VELJA
    assert o.srv.najvec_hkrati == 3
    o.srv.ob_prijavi = None
    b = bazen[0]
    _napolni(b)  # po preverbi bazen spet sme do polne meje
    assert o.srv.odprte == 3
    b.zapri()


def test_g4_posodobi_nastavitve_zmanjsa_mejo_zivega_bazena(o, pot):
    p = P(o, najvec_povezav=4)
    o.m.shrani_ponudnika(p, PRAVO, pot)
    b = o.m.ustvari_bazen(p)
    o.m.posodobi_nastavitve(pot, najvec_povezav=2)
    _napolni(b)
    assert o.srv.najvec_hkrati == 2
    b.zapri()


# ------------------------------------------------------------------ G5

def test_g5_napaka_zbirke_ne_izgubi_starega_racuna(o, pot):
    p, q = P(o), Q(o)
    o.m.shrani_ponudnika(p, PRAVO, pot)
    o.skr.napaka = True
    with pytest.raises(o.m.NapakaPonudnika) as e:
        o.m.shrani_ponudnika(q, DRUGO, pot)
    assert e.value.razlog == o.m.ZBIRKA_NAPAKA and "zaklenjena" not in str(e.value)
    o.skr.napaka = False
    assert o.m.preberi_ponudnika(pot) == p
    assert o.skr.zbirka == {p.kljuc_gesla: PRAVO}
    o.m.ustvari_bazen(p).zapri()


def test_g5_napaka_zapisa_json_ne_pusti_novega_gesla(o, pot, monkeypatch):
    # Regresija: z novim vrstnim redom (zbirka pred JSON) novo geslo ob napaki diska ne sme ostati v zbirki.
    p, q = P(o), Q(o)
    o.m.shrani_ponudnika(p, PRAVO, pot)
    pravi = o.m._pisi_json

    def pisi(pot_, podatki):
        if "ponudnik" in podatki:
            raise OSError("disk poln")
        return pravi(pot_, podatki)

    monkeypatch.setattr(o.m, "_pisi_json", pisi)
    with pytest.raises(OSError):
        o.m.shrani_ponudnika(q, DRUGO, pot)
    assert o.m.preberi_ponudnika(pot) == p
    assert o.skr.zbirka == {p.kljuc_gesla: PRAVO}


def test_g5_socasen_zapis_izida_ne_povozi_novega_vpisa(o, pot, monkeypatch):
    p, q = P(o), Q(o)
    o.m.shrani_ponudnika(p, PRAVO, pot)
    pravi = o.m._beri_json
    vpis = []

    def beri(pot_):
        d = pravi(pot_)
        if not vpis and threading.current_thread().name == "zapis-izida":
            # Natanko v oknu med branjem in pisanjem izida uporabnik vpise drug racun.
            t = threading.Thread(target=o.m.shrani_ponudnika, args=(q, DRUGO, pot))
            vpis.append(t)
            t.start()
            t.join(1.0)  # s popravkom caka na zaklep; brez njega konca takoj
        return d

    monkeypatch.setattr(o.m, "_beri_json", beri)
    z = threading.Thread(target=o.m._zapisi_preverbo, args=(pot, p, o.m.VELJA), name="zapis-izida")
    z.start()
    z.join(10)
    vpis[0].join(10)
    assert not z.is_alive() and not vpis[0].is_alive()
    assert o.m.preberi_ponudnika(pot) == q
    assert o.skr.zbirka == {q.kljuc_gesla: DRUGO}
    o.m.ustvari_bazen(q).zapri()  # ne NI_GESLA


# ------------------------------------------------------------------ G6

POKVARJENO = [b"{", GNEZDENO, b"x" * (64 * 1024 + 1)]


@pytest.mark.parametrize("vsebina", POKVARJENO, ids=["zacet", "gnezden", "prevelik"])
def test_g6_pozabi_po_pokvarjeni_datoteki(o, pot, vsebina):
    o.m.shrani_ponudnika(P(o), PRAVO, pot)
    with open(pot, "wb") as f:
        f.write(vsebina)
    o.m.pozabi_ponudnika(pot)
    assert o.skr.zbirka == {}
    assert os.listdir(os.path.dirname(pot)) == []


@pytest.mark.parametrize("vsebina", POKVARJENO, ids=["zacet", "gnezden", "prevelik"])
def test_g6_shrani_po_pokvarjeni_datoteki(o, pot, vsebina):
    p, q = P(o), Q(o)
    o.m.shrani_ponudnika(p, PRAVO, pot)
    with open(pot, "wb") as f:
        f.write(vsebina)
    o.m.shrani_ponudnika(q, DRUGO, pot)
    assert o.skr.zbirka == {q.kljuc_gesla: DRUGO}
    o.m.pozabi_ponudnika(pot)
    assert o.skr.zbirka == {}


def test_g6_pozabi_izprazni_pomnilnik(o, pot, monkeypatch):
    monkeypatch.setattr(o.skr, "shrani", lambda k, v: False)  # brez sistemske zbirke: samo pomnilnik
    assert o.m.shrani_ponudnika(P(o), PRAVO, pot) is False
    with open(pot, "wb") as f:
        f.write(b"{")
    o.m.pozabi_ponudnika(pot)
    assert o.m._V_POMNILNIKU == {}


def test_gesla_ni_v_nobeni_datoteki(o, pot):
    # Regresija za lastnikovo pravilo: tudi novi seznam kljucev nima gesla ali uporabnika.
    o.m.shrani_ponudnika(P(o), PRAVO, pot)
    o.m.shrani_ponudnika(Q(o), DRUGO, pot)
    for ime in os.listdir(os.path.dirname(pot)):
        with open(os.path.join(os.path.dirname(pot), ime), "rb") as f:
            vsebina = f.read()
        assert PRAVO.encode() not in vsebina and DRUGO.encode() not in vsebina
        if ime.endswith(".kljuci"):
            assert b"uporabnik1" not in vsebina
            assert oct(os.stat(os.path.join(os.path.dirname(pot), ime)).st_mode & 0o777) == "0o600"
