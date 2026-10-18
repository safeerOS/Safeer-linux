"""Global Link - neposredna pot od zunaj (core/link_neposredno.py) s pravimi vticnicami na 127.0.0.1.

Lazno sredisce je odmev za vhodom (bajti tunela so za vhod neprozorni - skozenj tece TLS Linka), lazni rele je
krajevna cev do istega odmeva. Javni naslovi v oglasih so dokumentacijski (203.0.113.x), preverba javnosti naslova je
v preizkusu zamenjana, kjer povezava dejansko tece na 127.0.0.1.
"""
import base64
import json
import os
import socket
import struct
import tempfile
import threading
import time

import pytest

from core import link_kripto, link_neposredno as ln, link_obramba, link_pot


# ------------------------------------------------------------------ identitete in lazne storitve

class Naprava:
    def __init__(self, mapa: str, ime: str) -> None:
        self.kljuc_pot = os.path.join(mapa, ime + "-kljuc.pem")
        self.potrdilo_pot = os.path.join(mapa, ime + "-potrdilo.pem")
        link_kripto.ustvari_kljuc_in_potrdilo(self.kljuc_pot, self.potrdilo_pot, "preizkus")
        self.kljuc = base64.b64encode(link_kripto.javni_kljuc_der(self.kljuc_pot)).decode("ascii")
        self.id = ln.id_iz_kljuca(self.kljuc)

    def podpisi(self, podatki: bytes) -> bytes:
        return link_kripto.podpisi(self.kljuc_pot, podatki)


@pytest.fixture(scope="module")
def naprave():
    mapa = tempfile.mkdtemp()
    return {"hub": Naprava(mapa, "hub"), "a": Naprava(mapa, "a"), "tujec": Naprava(mapa, "tujec"),
            "drug_hub": Naprava(mapa, "drug")}


class Odmev:
    """Lazni krajevni Hub: vrne vse, kar dobi."""

    def __init__(self) -> None:
        self.s = socket.create_server(("127.0.0.1", 0))
        self.vrata = self.s.getsockname()[1]
        self.povezav = 0
        threading.Thread(target=self._teci, daemon=True).start()

    def _teci(self):
        while True:
            try:
                c, _ = self.s.accept()
            except OSError:
                return
            self.povezav += 1
            threading.Thread(target=self._odmev, args=(c,), daemon=True).start()

    @staticmethod
    def _odmev(c):
        try:
            while True:
                b = c.recv(65536)
                if not b:
                    break
                c.sendall(b)
        except OSError:
            pass
        c.close()

    def zapri(self):
        self.s.close()


class LazniRele:
    """Kot link_rele.LokalniRele(poslusaj=False): `kanal(tcp)` - tu cev do odmeva, z umetnim zamikom vzpostavitve."""

    def __init__(self, cilj_vrata: int, zamik_s: float = 0.0) -> None:
        self.cilj_vrata, self.zamik_s = cilj_vrata, zamik_s
        self.kanalov = 0
        self.zadnja_napaka = ""

    def kanal(self, tcp):
        self.kanalov += 1
        time.sleep(self.zamik_s)
        h = socket.create_connection(("127.0.0.1", self.cilj_vrata))
        for v in (tcp, h):
            v.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)     # kot link_rele.cev (brez_zamika)
        ln._pipe(tcp, h)

    def zapri(self):
        pass


def vhod(naprave, hub_vrata, clani=("a",), **kw):
    hub = naprave["hub"]
    kljuci = {naprave[c].id: naprave[c].kljuc for c in clani}
    return ln.VhodNeposredno(0, lambda: hub_vrata, hub.id, hub.kljuc_pot, hub.potrdilo_pot,
                             lambda cid: kljuci.get(cid), naslov="127.0.0.1", **kw)


def brez_odgovora(s: socket.socket) -> bool:
    """Druga stran ne poslje niti bajta: samo zaprtje (EOF ali RST)."""
    s.settimeout(3)
    try:
        return s.recv(100) == b""
    except ConnectionResetError:
        return True


def krog(sock_vrata, s: socket.socket, sporocilo: bytes = b"safeer") -> bytes:
    s.sendall(sporocilo)
    s.settimeout(8)
    out = b""
    while len(out) < len(sporocilo):
        b = s.recv(65536)
        if not b:
            break
        out += b
    return out


# ------------------------------------------------------------------ nastavitve

def test_nastavitve_privzeto_izklopljeno_in_shranjevanje(tmp_path):
    pot = str(tmp_path / "n.json")
    assert ln.nastavitve(pot) == {"vklopljeno": False, "vrata": ln.PRIVZETA_VRATA}
    assert ln.shrani_nastavitve(True, 50123, pot) == {"vklopljeno": True, "vrata": 50123}
    with pytest.raises(ValueError):
        ln.shrani_nastavitve(True, 80, pot)
    with open(pot, "w") as d:
        json.dump({"vklopljeno": True, "vrata": "x"}, d)
    assert ln.nastavitve(pot)["vrata"] == ln.PRIVZETA_VRATA


def test_okolje_izklopi(tmp_path, monkeypatch):
    pot = str(tmp_path / "n.json")
    ln.shrani_nastavitve(True, None, pot)
    monkeypatch.setenv("SAFEER_NEPOSREDNO", "0")
    assert ln.nastavitve(pot)["vklopljeno"] is False


# ------------------------------------------------------------------ oglas (podpis, rok)

def _vsi_javni(_ip):
    return True


def test_oglas_podpisan_in_preverjen(naprave):
    hub = naprave["hub"]
    zdaj = 1_800_000_000.0
    niz = ln.sestavi_oglas(hub.id, "203.0.113.7", 48990, hub.kljuc, hub.podpisi, preverjeno=zdaj - 60, zdaj=zdaj)
    assert len(niz) <= 512
    o = ln.preveri_oglas(niz, hub.id, hub.kljuc, link_kripto.preveri, zdaj=zdaj, je_javni=_vsi_javni)
    assert o == {"ip": "203.0.113.7", "vrata": 48990, "exp": int(zdaj + ln.TTL_OGLASA_S), "preverjeno": True}
    # nepreverjen
    niz2 = ln.sestavi_oglas(hub.id, "203.0.113.7", 48990, hub.kljuc, hub.podpisi, zdaj=zdaj)
    assert ln.preveri_oglas(niz2, hub.id, hub.kljuc, link_kripto.preveri, zdaj=zdaj, je_javni=_vsi_javni)["preverjeno"] is False


def test_oglas_zavrnjen(naprave):
    hub, drug = naprave["hub"], naprave["drug_hub"]
    zdaj = 1_800_000_000.0
    niz = ln.sestavi_oglas(hub.id, "203.0.113.7", 48990, hub.kljuc, hub.podpisi, zdaj=zdaj)
    pv = link_kripto.preveri
    # kljuc drugega sredisca (relej bi podtaknil svoj oglas)
    assert ln.preveri_oglas(niz, hub.id, drug.kljuc, pv, zdaj=zdaj, je_javni=_vsi_javni) is None
    # drug id
    assert ln.preveri_oglas(niz, drug.id, hub.kljuc, pv, zdaj=zdaj, je_javni=_vsi_javni) is None
    # potekel / predalec v prihodnosti
    assert ln.preveri_oglas(niz, hub.id, hub.kljuc, pv, zdaj=zdaj + ln.TTL_OGLASA_S + 1, je_javni=_vsi_javni) is None
    dolg = ln.sestavi_oglas(hub.id, "203.0.113.7", 48990, hub.kljuc, hub.podpisi, zdaj=zdaj, ttl=ln.NAJDALJSI_TTL_S + 60)
    assert ln.preveri_oglas(dolg, hub.id, hub.kljuc, pv, zdaj=zdaj, je_javni=_vsi_javni) is None
    # spremenjen tovor
    oznaka, t, p = niz.split(".")
    tovor = json.loads(ln._b64u_d(t))
    tovor["ip"] = "203.0.113.99"
    ponarejen = "%s.%s.%s" % (oznaka, ln._b64u(json.dumps(tovor).encode()), p)
    assert ln.preveri_oglas(ponarejen, hub.id, hub.kljuc, pv, zdaj=zdaj, je_javni=_vsi_javni) is None
    # zasebni in dokumentacijski naslovi niso javni (privzeta preverba)
    for ip in ("192.168.1.5", "10.0.0.1", "100.64.1.1", "203.0.113.7"):
        z = ln.sestavi_oglas(hub.id, ip, 48990, hub.kljuc, hub.podpisi, zdaj=zdaj)
        assert ln.preveri_oglas(z, hub.id, hub.kljuc, pv, zdaj=zdaj) is None
    # nizka vrata
    z = ln.sestavi_oglas(hub.id, "203.0.113.7", 80, hub.kljuc, hub.podpisi, zdaj=zdaj)
    assert ln.preveri_oglas(z, hub.id, hub.kljuc, pv, zdaj=zdaj, je_javni=_vsi_javni) is None
    assert ln.preveri_oglas("smeti", hub.id, hub.kljuc, pv, zdaj=zdaj) is None


def test_poisci_oglas_vzame_prvega_veljavnega(naprave):
    hub, drug = naprave["hub"], naprave["drug_hub"]
    zdaj = time.time()
    tuj = ln.sestavi_oglas(hub.id, "203.0.113.8", 48990, drug.kljuc, drug.podpisi, zdaj=zdaj)
    pravi = ln.sestavi_oglas(hub.id, "203.0.113.7", 48991, hub.kljuc, hub.podpisi, zdaj=zdaj)
    odgovor = {"presence": {"device_id": hub.id, "candidate_hints": ["x", tuj, pravi]}}
    import core.link_neposredno as m
    stara = m.je_javni_ipv4
    m.je_javni_ipv4 = _vsi_javni
    try:
        o = ln.poisci_oglas(hub.id, hub.kljuc, prenesi=lambda _h: odgovor)
    finally:
        m.je_javni_ipv4 = stara
    assert o["vrata"] == 48991 and o["niz"] == pravi
    assert ln.poisci_oglas(hub.id, hub.kljuc, prenesi=lambda _h: {"presence": None}) is None


# ------------------------------------------------------------------ STUN

def _stun_odgovor(tid: bytes, ip: str, vrata: int) -> bytes:
    xip = bytes(a ^ b for a, b in zip(socket.inet_aton(ip), struct.pack(">I", 0x2112A442)))
    atr = struct.pack(">HH", 0x0020, 8) + bytes([0, 1]) + struct.pack(">H", vrata ^ 0x2112) + xip
    return struct.pack(">HHI", 0x0101, len(atr), 0x2112A442) + tid + atr


def test_stun_razclenitev_in_lazni_streznik():
    tid = os.urandom(12)
    assert ln.razberi_stun(_stun_odgovor(tid, "203.0.113.7", 50000), tid) == ("203.0.113.7", 50000)
    assert ln.razberi_stun(_stun_odgovor(tid, "203.0.113.7", 50000), os.urandom(12)) is None
    assert ln.razberi_stun(b"\x00" * 10, tid) is None

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))

    def streznik():
        z, kdo = s.recvfrom(2048)
        s.sendto(_stun_odgovor(z[8:20], "203.0.113.7", kdo[1]), kdo)
    threading.Thread(target=streznik, daemon=True).start()
    assert ln.javni_ipv4_stun([("127.0.0.1", s.getsockname()[1])], rok_s=2, je_javni=_vsi_javni) == "203.0.113.7"
    s.close()


def test_stun_brez_odgovora_vrne_prazno():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    t0 = time.monotonic()
    assert ln.javni_ipv4_stun([("127.0.0.1", s.getsockname()[1])], rok_s=0.2, poskusov=2) == ""
    assert time.monotonic() - t0 < 2
    s.close()


# ------------------------------------------------------------------ vhod: overjanje

def test_clan_kroga_pride_skozi_in_bajti_tecejo(naprave):
    odmev = Odmev()
    v = vhod(naprave, odmev.vrata)
    try:
        a, hub = naprave["a"], naprave["hub"]
        t, ms_tcp, ms = ln.odpri_neposredno("127.0.0.1", v.vrata, hub.id, hub.kljuc, a.id, a.podpisi)
        assert ms_tcp >= 0 and ms >= ms_tcp
        assert krog(0, t, b"x" * 200_000) == b"x" * 200_000
        t.close()
        assert v.sprejetih == 1 and odmev.povezav == 1
    finally:
        v.zapri()
        odmev.zapri()


def test_neseznanjena_naprava_ne_dobi_niti_bajta(naprave):
    odmev = Odmev()
    v = vhod(naprave, odmev.vrata)
    try:
        tujec, hub = naprave["tujec"], naprave["hub"]
        with pytest.raises(ln.NapakaNeposredne):
            ln.odpri_neposredno("127.0.0.1", v.vrata, hub.id, hub.kljuc, tujec.id, tujec.podpisi)
        # Surovo: pravilno oblikovan trk tujca -> nic odgovora (ne TLS ne potrdila), samo zaprtje.
        s = socket.create_connection(("127.0.0.1", v.vrata))
        s.sendall(ln.sestavi_trk(hub.id, tujec.id, tujec.podpisi))
        assert brez_odgovora(s)
        s.close()
        assert odmev.povezav == 0
    finally:
        v.zapri()
        odmev.zapri()


def test_pregledovalnik_vrat_ne_dobi_odgovora(naprave):
    odmev = Odmev()
    v = vhod(naprave, odmev.vrata)
    try:
        for poskus in (b"GET / HTTP/1.1\r\nHost: x\r\n\r\n" + b"x" * 64, b"\x16\x03\x01" + os.urandom(200)):
            s = socket.create_connection(("127.0.0.1", v.vrata))
            s.sendall(poskus)
            assert brez_odgovora(s)
            s.close()
        assert odmev.povezav == 0
    finally:
        v.zapri()
        odmev.zapri()


def test_podpis_z_napacnim_kljucem_in_ponovljen_trk(naprave):
    odmev = Odmev()
    v = vhod(naprave, odmev.vrata)
    try:
        a, tujec, hub = naprave["a"], naprave["tujec"], naprave["hub"]
        # id clana, podpis tujca (ukraden id)
        with pytest.raises(ln.NapakaNeposredne):
            ln.odpri_neposredno("127.0.0.1", v.vrata, hub.id, hub.kljuc, a.id, tujec.podpisi)
        # posnet trk clana: drugic se ne odpre nic
        trk = ln.sestavi_trk(hub.id, a.id, a.podpisi)
        for i in range(2):
            s = socket.create_connection(("127.0.0.1", v.vrata))
            s.sendall(trk)
            import ssl
            k = ln._kontekst_odjemalca()
            s.settimeout(3)
            try:
                t = k.wrap_socket(s)
                ok = True
                t.close()
            except (OSError, ssl.SSLError):
                ok = False
                s.close()
            assert ok is (i == 0)
        # star cas
        star = ln.sestavi_trk(hub.id, a.id, a.podpisi, cas=int(time.time()) - ln.OKNO_CASA_S - 5)
        s = socket.create_connection(("127.0.0.1", v.vrata))
        s.sendall(star)
        assert brez_odgovora(s)
        s.close()
        assert odmev.povezav == 0
    finally:
        v.zapri()
        odmev.zapri()


def test_odjemalec_zavrne_sredisce_z_drugim_kljucem(naprave):
    odmev = Odmev()
    v = vhod(naprave, odmev.vrata)
    try:
        a, hub, drug = naprave["a"], naprave["hub"], naprave["drug_hub"]
        # Odjemalec pricakuje kljuc drugega sredisca (v krogu je drug kljuc): TLS uspe, kljuc se ne ujema -> ne.
        with pytest.raises(ln.NapakaNeposredne) as e:
            ln.odpri_neposredno("127.0.0.1", v.vrata, hub.id, drug.kljuc, a.id, a.podpisi)
        assert "kljuc" in str(e.value)
        assert odmev.povezav == 0
    finally:
        v.zapri()
        odmev.zapri()


def test_obramba_zapre_vir_po_ponavljanju(naprave):
    odmev = Odmev()
    ura = [1000.0]
    obramba = link_obramba.Obramba(ura=lambda: ura[0], izvzet=lambda _v: False)
    v = vhod(naprave, odmev.vrata, obramba=obramba)
    try:
        tujec, a, hub = naprave["tujec"], naprave["a"], naprave["hub"]
        for _ in range(25):
            s = socket.create_connection(("127.0.0.1", v.vrata))
            s.sendall(ln.sestavi_trk(hub.id, tujec.id, tujec.podpisi))
            s.settimeout(3)
            try:
                s.recv(10)
            except OSError:
                pass
            s.close()
        assert obramba.zaprt("127.0.0.1")
        # Zaprt vir ne pride skozi niti s pravim kljucem, dokler zapora traja.
        with pytest.raises(ln.NapakaNeposredne):
            ln.odpri_neposredno("127.0.0.1", v.vrata, hub.id, hub.kljuc, a.id, a.podpisi)
        ura[0] += link_obramba.ZAPORA_S + 1
        t, _, _ = ln.odpri_neposredno("127.0.0.1", v.vrata, hub.id, hub.kljuc, a.id, a.podpisi)
        t.close()
    finally:
        v.zapri()
        odmev.zapri()


def test_umaknjen_clan_ne_pride_vec(naprave):
    odmev = Odmev()
    clani = {naprave["a"].id: naprave["a"].kljuc}
    hub, a = naprave["hub"], naprave["a"]
    v = ln.VhodNeposredno(0, lambda: odmev.vrata, hub.id, hub.kljuc_pot, hub.potrdilo_pot, lambda cid: clani.get(cid),
                          naslov="127.0.0.1")
    try:
        t, _, _ = ln.odpri_neposredno("127.0.0.1", v.vrata, hub.id, hub.kljuc, a.id, a.podpisi)
        t.close()
        clani.clear()           # umik iz kroga: naslednja povezava ne gre vec skozi
        with pytest.raises(ln.NapakaNeposredne):
            ln.odpri_neposredno("127.0.0.1", v.vrata, hub.id, hub.kljuc, a.id, a.podpisi)
    finally:
        v.zapri()
        odmev.zapri()


def test_preizkus_steje_kot_preverjanje_samo_z_javnega_naslova(naprave, monkeypatch):
    odmev = Odmev()
    zunanji = []
    v = vhod(naprave, odmev.vrata, ob_zunanji=zunanji.append)
    try:
        a, hub = naprave["a"], naprave["hub"]
        assert ln.preizkusi("127.0.0.1", v.vrata, hub.id, hub.kljuc, a.id, a.podpisi) is not None
        assert zunanji == [] and odmev.povezav == 0     # zanka ni "od zunaj"; preizkus ne odpre Huba
        monkeypatch.setattr(ln, "je_javni_ipv4", lambda ip: ip == "127.0.0.1")
        assert ln.preizkusi("127.0.0.1", v.vrata, hub.id, hub.kljuc, a.id, a.podpisi) is not None
        assert zunanji == ["127.0.0.1"] and odmev.povezav == 0
        tujec = naprave["tujec"]
        assert ln.preizkusi("127.0.0.1", v.vrata, hub.id, hub.kljuc, tujec.id, tujec.podpisi) is None
        assert zunanji == ["127.0.0.1"]
    finally:
        v.zapri()
        odmev.zapri()


def test_tunel_oznaci_krajevna_vrata_za_meritve(naprave):
    """Hub vidi 127.0.0.1 - oznaka vrat pove, da je neposredna pot (link_pot.pot_vticnika)."""
    seen = []

    class Hub(Odmev):
        @staticmethod
        def _odmev(c):
            seen.append(link_pot.pot_vticnika("127.0.0.1", c))
            Odmev._odmev(c)
    hubs = Hub()
    v = vhod(naprave, hubs.vrata)
    try:
        a, hub = naprave["a"], naprave["hub"]
        t, _, _ = ln.odpri_neposredno("127.0.0.1", v.vrata, hub.id, hub.kljuc, a.id, a.podpisi)
        assert krog(0, t) == b"safeer"
        assert seen == ["neposredno"]
        t.close()
    finally:
        v.zapri()
        hubs.zapri()
    assert link_pot.pot_vticnika("127.0.0.1", None) == "rele"
    assert link_pot.pot_naslova("192.168.0.2") == "lan"


# ------------------------------------------------------------------ odjemalec: vrstni red poti in rezerva

def _oglas(ip="127.0.0.1", vrata=0, preverjeno=True):
    return {"ip": ip, "vrata": vrata, "exp": time.time() + 600, "preverjeno": preverjeno, "niz": "sdv1.x.y"}


def _od_zunaj(naprave, oglas, rele, tmp_path=None, omrezje=lambda ip: "omrezje-1"):
    hub, a = naprave["hub"], naprave["a"]
    return ln.LokalniOdZunaj(hub.id, kljuc_huba=hub.kljuc, rele=lambda _c: rele, nas_id=lambda: a.id,
                             podpisi=a.podpisi, poisci=lambda h, k: oglas, omrezje=omrezje,
                             pot_spomina=str(tmp_path / "poti.json") if tmp_path else None)


def _pocakaj(pogoj, rok=3.0):
    konec = time.monotonic() + rok
    while time.monotonic() < konec:
        if pogoj():
            return True
        time.sleep(0.02)
    return pogoj()


def test_neposredno_pred_relejem(naprave, tmp_path):
    odmev = Odmev()
    v = vhod(naprave, odmev.vrata)
    rele = LazniRele(odmev.vrata)
    o = _od_zunaj(naprave, _oglas(vrata=v.vrata), rele, tmp_path)
    try:
        assert _pocakaj(lambda: o.neposredno_na_voljo())
        s = socket.create_connection(("127.0.0.1", o.vrata))
        assert krog(0, s) == b"safeer"
        s.close()
        assert o.zadnja_pot == "neposredno" and rele.kanalov == 0 and v.sprejetih == 1
        assert o.zadnji_ms is not None
        # zapomnjena pot
        spomin = json.load(open(tmp_path / "poti.json"))
        assert spomin[naprave["hub"].id]["pot"] == "neposredno"
    finally:
        o.zapri()
        v.zapri()
        odmev.zapri()


def test_rezerva_rele_hitro_in_premor(naprave):
    odmev = Odmev()
    # Vrata, kjer nihce ne poslusa (vhod ugasnjen / usmerjevalnik ne preusmeri).
    prazna = socket.create_server(("127.0.0.1", 0))
    mrtva = prazna.getsockname()[1]
    prazna.close()
    rele = LazniRele(odmev.vrata)
    o = _od_zunaj(naprave, _oglas(vrata=mrtva), rele)
    try:
        assert _pocakaj(lambda: o.neposredno_na_voljo())
        t0 = time.monotonic()
        s = socket.create_connection(("127.0.0.1", o.vrata))
        assert krog(0, s) == b"safeer"
        prvi = time.monotonic() - t0
        s.close()
        assert o.zadnja_pot == "rele" and rele.kanalov == 1
        assert prvi < ln.ROK_POVEZAVE_S + 0.5
        # Druga povezava neposredne poti ne poskusa (premor): takoj prek releja.
        assert not o.neposredno_na_voljo()
        t0 = time.monotonic()
        s = socket.create_connection(("127.0.0.1", o.vrata))
        assert krog(0, s) == b"safeer"
        assert time.monotonic() - t0 < 0.5
        s.close()
        assert rele.kanalov == 2
    finally:
        o.zapri()
        odmev.zapri()


def test_crna_luknja_ne_zadrzi_dlje_od_roka(naprave):
    """Vrata, ki sprejmejo TCP in molcijo (npr. napacna preusmeritev): po roku rokovanja na rele."""
    odmev = Odmev()
    molk = socket.create_server(("127.0.0.1", 0))
    rele = LazniRele(odmev.vrata)
    o = _od_zunaj(naprave, _oglas(vrata=molk.getsockname()[1]), rele)
    try:
        assert _pocakaj(lambda: o.neposredno_na_voljo())
        t0 = time.monotonic()
        s = socket.create_connection(("127.0.0.1", o.vrata))
        assert krog(0, s) == b"safeer"
        assert time.monotonic() - t0 < ln.ROK_ROKOVANJA_S + 1.0
        s.close()
        assert o.zadnja_pot == "rele"
    finally:
        o.zapri()
        molk.close()
        odmev.zapri()


def test_sprememba_omrezja_izbrise_premor(naprave):
    odmev = Odmev()
    prazna = socket.create_server(("127.0.0.1", 0))
    mrtva = prazna.getsockname()[1]
    prazna.close()
    omrezje = ["mobilno"]
    o = _od_zunaj(naprave, _oglas(vrata=mrtva), LazniRele(odmev.vrata), omrezje=lambda ip: omrezje[0])
    try:
        assert _pocakaj(lambda: o.neposredno_na_voljo())
        s = socket.create_connection(("127.0.0.1", o.vrata))
        krog(0, s)
        s.close()
        assert not o.neposredno_na_voljo()
        omrezje[0] = "wifi-v-kavarni"
        assert o.neposredno_na_voljo()
    finally:
        o.zapri()
        odmev.zapri()


def test_nepreverjen_oglas_najprej_preizkus_v_ozadju(naprave):
    odmev = Odmev()
    v = vhod(naprave, odmev.vrata)
    rele = LazniRele(odmev.vrata)
    o = _od_zunaj(naprave, _oglas(vrata=v.vrata, preverjeno=False), rele)
    try:
        # Preizkus v ozadju (namen 2) uspe -> neposredna pot je nasa preverjena; do takrat pot ni na voljo.
        assert _pocakaj(lambda: o.neposredno_na_voljo())
        assert v.sprejetih >= 1 and odmev.povezav == 0
        s = socket.create_connection(("127.0.0.1", o.vrata))
        assert krog(0, s) == b"safeer"
        s.close()
        assert o.zadnja_pot == "neposredno" and rele.kanalov == 0
    finally:
        o.zapri()
        v.zapri()
        odmev.zapri()


def test_nepreverjen_oglas_ki_ne_dela_ostane_na_releju(naprave):
    odmev = Odmev()
    prazna = socket.create_server(("127.0.0.1", 0))
    mrtva = prazna.getsockname()[1]
    prazna.close()
    rele = LazniRele(odmev.vrata)
    o = _od_zunaj(naprave, _oglas(vrata=mrtva, preverjeno=False), rele)
    try:
        time.sleep(0.5)
        t0 = time.monotonic()
        s = socket.create_connection(("127.0.0.1", o.vrata))
        assert krog(0, s) == b"safeer"
        assert time.monotonic() - t0 < 0.5           # uporabnik ne caka na nepreverjeno pot
        s.close()
        assert o.zadnja_pot == "rele" and not o.neposredno_na_voljo()
    finally:
        o.zapri()
        odmev.zapri()


def test_brez_oglasa_vedno_rele(naprave):
    odmev = Odmev()
    rele = LazniRele(odmev.vrata)
    o = _od_zunaj(naprave, None, rele)
    try:
        s = socket.create_connection(("127.0.0.1", o.vrata))
        assert krog(0, s) == b"safeer"
        s.close()
        assert o.zadnja_pot == "rele" and rele.kanalov == 1
    finally:
        o.zapri()
        odmev.zapri()


def test_vrata_samo_neposredno_brez_releja(naprave):
    odmev = Odmev()
    prazna = socket.create_server(("127.0.0.1", 0))
    mrtva = prazna.getsockname()[1]
    prazna.close()
    rele = LazniRele(odmev.vrata)
    o = _od_zunaj(naprave, _oglas(vrata=mrtva), rele)
    try:
        assert _pocakaj(lambda: o.neposredno_na_voljo())
        s = socket.create_connection(("127.0.0.1", o.vrata_neposredno))
        assert brez_odgovora(s)         # neposredno ni uspelo: zaprto, brez kanala releja
        s.close()
        assert rele.kanalov == 0
    finally:
        o.zapri()
        odmev.zapri()


def test_spomin_po_ponovnem_zagonu(naprave, tmp_path):
    """Zadnja delujoca pot (s podpisanim oglasom) se nalozi ob novem procesu - prva povezava gre takoj neposredno."""
    hub, a = naprave["hub"], naprave["a"]
    odmev = Odmev()
    v = vhod(naprave, odmev.vrata)
    zdaj = time.time()
    niz = ln.sestavi_oglas(hub.id, "127.0.0.1", v.vrata, hub.kljuc, hub.podpisi, zdaj=zdaj)
    with open(tmp_path / "poti.json", "w") as d:
        json.dump({hub.id: {"pot": "neposredno", "ob": int(zdaj), "oglas": niz}}, d)
    import core.link_neposredno as m
    stara = m.je_javni_ipv4
    m.je_javni_ipv4 = lambda ip: True
    rele = LazniRele(odmev.vrata)
    try:
        o = ln.LokalniOdZunaj(hub.id, kljuc_huba=hub.kljuc, rele=lambda _c: rele, nas_id=lambda: a.id,
                              podpisi=a.podpisi, poisci=lambda h, k: None, pot_spomina=str(tmp_path / "poti.json"))
        assert o.neposredno_na_voljo()
        s = socket.create_connection(("127.0.0.1", o.vrata))
        assert krog(0, s) == b"safeer"
        s.close()
        assert o.zadnja_pot == "neposredno" and rele.kanalov == 0
        o.zapri()
    finally:
        m.je_javni_ipv4 = stara
        v.zapri()
        odmev.zapri()


# ------------------------------------------------------------------ sredisce: vhod, javni naslov, oglas

class _LazniVhod:
    def __init__(self, vrata):
        self.vrata_nastavljena = vrata
        self.vrata = vrata
        self.tece = True

    def zapri(self):
        self.tece = False


def test_sredisce_vhod_po_nastavitvi_in_preverjanje(naprave, tmp_path, monkeypatch):
    hub = naprave["hub"]
    n = {"vklopljeno": False, "vrata": 48990}
    vhodi = []

    def tovarna(vrata, hub_vrata, ob_zunanji):
        vhodi.append((_LazniVhod(vrata), ob_zunanji))
        return vhodi[-1][0]
    ura = [1_800_000_000.0]
    h = ln.NeposrednoHuba(lambda: 8990, nastavitve_fn=lambda: dict(n), stun=lambda: "203.0.113.7",
                          vhod_tovarna=tovarna, pot_stanja=str(tmp_path / "stanje.json"), ura=lambda: ura[0])
    monkeypatch.setattr(ln, "je_javni_ipv4", lambda ip: ip.startswith("203.0.113."))
    h.korak()
    assert h.vhod is None and h.namigi(hub.kljuc, hub.podpisi) == []
    n["vklopljeno"] = True
    h.korak()
    assert h.vhod is not None and h.stanje()["tece"] and h.stanje()["javni_naslov"]
    assert not h.preverjeno()
    niz = h.namigi(hub.kljuc, hub.podpisi)[0]
    o = ln.preveri_oglas(niz, hub.id, hub.kljuc, link_kripto.preveri, zdaj=ura[0])
    assert o["ip"] == "203.0.113.7" and o["vrata"] == 48990 and o["preverjeno"] is False
    # Prva overjena povezava od zunaj -> preverjeno; oglas to nosi.
    vhodi[-1][1]("198.51.100.20")
    assert h.preverjeno()
    o = ln.preveri_oglas(h.namigi(hub.kljuc, hub.podpisi)[0], hub.id, hub.kljuc, link_kripto.preveri, zdaj=ura[0])
    assert o["preverjeno"] is True
    assert "203.0.113.7" not in json.dumps(h.stanje())      # vmesnik ne dobi naslova IP
    # Preverba velja PREVERJENO_VELJA_S.
    ura[0] += ln.PREVERJENO_VELJA_S + 1
    assert not h.preverjeno()
    # Druga vrata: vhod znova, preverba ne velja vec.
    vhodi[-1][1]("198.51.100.20")
    n["vrata"] = 48991
    h.korak()
    assert len(vhodi) == 2 and not vhodi[0][0].tece and not h.preverjeno()
    # Izklop zapre vhod in umakne oglas.
    n["vklopljeno"] = False
    h.korak()
    assert h.vhod is None and h.namigi(hub.kljuc, hub.podpisi) == []


def test_sredisce_nov_javni_naslov_ponastavi_preverjanje(naprave, tmp_path, monkeypatch):
    ip = ["203.0.113.7"]
    ura = [1_800_000_000.0]
    vhodi = []
    h = ln.NeposrednoHuba(lambda: 8990, nastavitve_fn=lambda: {"vklopljeno": True, "vrata": 48990},
                          stun=lambda: ip[0],
                          vhod_tovarna=lambda v, hv, oz: vhodi.append(oz) or _LazniVhod(v),
                          pot_stanja=str(tmp_path / "s.json"), ura=lambda: ura[0])
    monkeypatch.setattr(ln, "je_javni_ipv4", lambda x: x.startswith("203.0.113."))
    h.korak()
    vhodi[0]("198.51.100.20")
    assert h.preverjeno()
    ip[0] = "203.0.113.8"
    ura[0] += ln.STUN_VSAKIH_S + 1
    h.korak()
    assert not h.preverjeno()
    # Stanje prezivi ponovni zagon (shranjeno brez nacina, kako je bilo preverjeno).
    vhodi[0]("198.51.100.20")
    h2 = ln.NeposrednoHuba(lambda: 8990, nastavitve_fn=lambda: {"vklopljeno": True, "vrata": 48990},
                           stun=lambda: ip[0], vhod_tovarna=lambda v, hv, oz: _LazniVhod(v),
                           pot_stanja=str(tmp_path / "s.json"), ura=lambda: ura[0])
    h2.korak()
    assert h2.preverjeno()


def test_sredisce_zasedena_vrata(tmp_path):
    def tovarna(vrata, hub_vrata, ob_zunanji):
        raise OSError(98, "Address already in use")
    h = ln.NeposrednoHuba(lambda: 8990, nastavitve_fn=lambda: {"vklopljeno": True, "vrata": 48990},
                          stun=lambda: "", vhod_tovarna=tovarna, pot_stanja=str(tmp_path / "s.json"))
    h.korak()
    assert h.vhod is None and "48990" in h.napaka


def test_agent_objavi_oglas_v_prisotnosti(monkeypatch):
    from core import link_rele, link_krog
    poslano = {}

    class Odg:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b"{}"

    def urlopen(z, timeout=0):
        poslano["telo"] = json.loads(z.data)
        return Odg()
    monkeypatch.setattr(link_rele.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(link_rele, "podpisane_glave", lambda *a, **k: {})
    monkeypatch.setattr(link_krog, "javni_kljuc_b64", lambda: base64.b64encode(b"k" * 91).decode())
    agent = link_rele.AgentHuba(vrata=lambda: 1, vklopljen=lambda: True, krog_json=lambda: {},
                                namigi=lambda: ["sdv1.a.b"])
    agent.objavi()
    assert poslano["telo"]["candidate_hints"] == ["sdv1.a.b"]
    agent = link_rele.AgentHuba(vrata=lambda: 1, vklopljen=lambda: True, krog_json=lambda: {}, namigi=lambda: [])
    agent.objavi()
    assert "candidate_hints" not in poslano["telo"]


# ------------------------------------------------------------------ Hub: boljsa pot zamenja slabso

def test_hub_obdrzi_boljso_pot():
    from core import link_hub_streznik

    class P:
        def __init__(self, pot):
            self.meritev = link_pot.MeritevPoti(pot)
            self.naslov = "127.0.0.1"
            self.podatki = {}
            self.zaprta = False

        def poslji(self, *_a):
            return True

        def zapri(self, *_a):
            self.zaprta = True

    hub = link_hub_streznik.Hub(odtis="x", nas_id="n-0000000000000001")
    hub._je_clan = lambda _i: True
    sid = "n-0000000000000002"
    rele, nep, lan = P("rele"), P("neposredno"), P("lan")
    assert hub.dodaj_soseda(sid, rele, sid)
    assert hub.dodaj_soseda(sid, nep, sid) and rele.zaprta          # neposredno zamenja rele
    assert not hub.dodaj_soseda(sid, P("rele"), sid)                 # rele ne zamenja neposredne
    assert hub.dodaj_soseda(sid, lan, sid) and nep.zaprta           # domace omrezje zamenja neposredno
    assert not hub.dodaj_soseda(sid, P("neposredno"), sid)


def test_tunel_ima_keepalive_mrtva_stran_ne_drzi_mesta(naprave, monkeypatch):
    """Tunel je brez roka (settimeout(None)): mrtvo drugo stran mora zaznati keepalive, sicer tunel za vedno drzi
    niti, deskriptorje in mesto med NAJVEC_TUNELOV. Obe strani tunela (vhod in odjemalec) ga vklopita."""
    from core import link_vticnik
    nastavljeno = []
    izvirna = link_vticnik.ohrani_zivost

    def zabelezi(v, *a, **k):
        izvirna(v, *a, **k)
        nastavljeno.append(v.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE))
    monkeypatch.setattr(link_vticnik, "ohrani_zivost", zabelezi)
    odmev = Odmev()
    v = vhod(naprave, odmev.vrata)
    try:
        a, hub = naprave["a"], naprave["hub"]
        t, _, _ = ln.odpri_neposredno("127.0.0.1", v.vrata, hub.id, hub.kljuc, a.id, a.podpisi)
        assert krog(0, t) == b"safeer"
        assert nastavljeno and all(nastavljeno), nastavljeno
        t.close()
        assert _pocakaj(lambda: v._tunelov == 0), "zaprt tunel sprosti mesto"
    finally:
        v.zapri()
        odmev.zapri()


def _iz_naslova(monkeypatch, naslov: str) -> None:
    """Odjemalec odpira povezave z drugega naslova zanke (127.0.0.x): tako je vir za vhod drug naslov."""
    izvirna = socket.create_connection

    def s_virom(cilj, timeout=None, source_address=None, **kw):
        return izvirna(cilj, timeout, source_address or (naslov, 0), **kw)
    monkeypatch.setattr(ln.socket, "create_connection", s_virom)


def _tihi_trki(stevilo: int, naslov: str = "127.0.0.1", vrata: int = 0) -> list:
    """Pocasen trk (slowloris): povezava odprta, nic poslano - drzi mesto za rokovanje do ROK_VHODA_S."""
    vticnice = []
    for _ in range(stevilo):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.bind((naslov, 0))
        s.connect(("127.0.0.1", vrata))
        vticnice.append(s)
    return vticnice


def test_en_naslov_ne_zasede_vseh_mest_za_rokovanje(naprave, monkeypatch):
    """Pregled 18. 10. 2026: en naslov je s 16 tihimi trki zasedel vsa mesta - clan kroga z drugega naslova ni prisel
    skozi, dokler trki niso potekli (ROK_VHODA_S)."""
    odmev = Odmev()
    v = vhod(naprave, odmev.vrata)
    tihi = []
    try:
        tihi = _tihi_trki(ln.NAJVEC_ROKOVANJ, "127.0.0.1", v.vrata)
        assert _pocakaj(lambda: v._rokovanj == ln.NAJVEC_ROKOVANJ_NA_VIR), v._rokovanj
        _iz_naslova(monkeypatch, "127.0.0.2")
        a, hub = naprave["a"], naprave["hub"]
        t, _, _ = ln.odpri_neposredno("127.0.0.1", v.vrata, hub.id, hub.kljuc, a.id, a.podpisi)
        assert krog(0, t) == b"safeer"
        t.close()
    finally:
        for s in tihi:
            s.close()
        v.zapri()
        odmev.zapri()


def test_mnogo_naslovov_ne_izrine_zaupane_naprave(naprave, monkeypatch):
    """REZERVA_ZAUPANIM mest ostane naslovom, ki so se v zadnjem casu izkazali kot clani kroga."""
    odmev = Odmev()
    v = vhod(naprave, odmev.vrata)
    tihi = []
    try:
        a, hub = naprave["a"], naprave["hub"]
        _iz_naslova(monkeypatch, "127.0.0.9")
        t, _, _ = ln.odpri_neposredno("127.0.0.1", v.vrata, hub.id, hub.kljuc, a.id, a.podpisi)
        t.close()                                  # 127.0.0.9 je zdaj zaupan (obramba.zaupaj)
        assert v.obramba.zaupa("127.0.0.9")
        prosta = ln.NAJVEC_ROKOVANJ - ln.REZERVA_ZAUPANIM
        for i in range(prosta // ln.NAJVEC_ROKOVANJ_NA_VIR + 1):
            tihi += _tihi_trki(ln.NAJVEC_ROKOVANJ_NA_VIR, "127.0.1.%d" % (i + 1), v.vrata)
        assert _pocakaj(lambda: v._rokovanj == prosta), v._rokovanj
        assert not v.obramba.zaupa("127.0.1.1")
        t, _, _ = ln.odpri_neposredno("127.0.0.1", v.vrata, hub.id, hub.kljuc, a.id, a.podpisi)
        assert krog(0, t) == b"safeer"
        t.close()
    finally:
        for s in tihi:
            s.close()
        v.zapri()
        odmev.zapri()
