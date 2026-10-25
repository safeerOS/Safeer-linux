"""Sporocila v realnem casu (lastnik, 15. 10. 2026): IMAP IDLE, dolga poizvedba Matrix/Telegram, oznake v obe
smeri (CONDSTORE), UIDVALIDITY, odhodna vrsta, iskanje FTS5, vklop/izklop kanala.

Samo lokalni nadomestni strezniki (tests/lazni_imap.py, http.server na 127.0.0.1) - brez interneta, brez pravih
racunov in gesel."""
import imaplib
import json
import socket
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit

import pytest

from core.sporocila import imap_sprotno, sprotno
from core.sporocila.email import EmailAdapter
from core.sporocila.matrix import MatrixAdapter
from core.sporocila.model import Kanal, Pogovor, Sporocilo
from core.sporocila.storitev import StoritevSporocil
from core.sporocila.telegram_bot import TelegramBotAdapter
from lazni_imap import LazniImap, pismo


# ============================================================ pomocniki
def _imap_brez_tls(host, port=993, ssl_context=None, timeout=None):
    return imaplib.IMAP4(host, port, timeout=timeout)


def _idle_brez_tls(gostitelj, vrata, kontekst=None):
    return imap_sprotno.PovezavaIdle(socket.create_connection((gostitelj, vrata), timeout=5))


@pytest.fixture
def lokalno():
    """Adapter in povezava IDLE gresta na lokalni streznik brez TLS (samo v preizkusu)."""
    with mock.patch.object(imaplib, "IMAP4_SSL", _imap_brez_tls), \
         mock.patch.object(imap_sprotno.PovezavaIdle, "odpri", staticmethod(_idle_brez_tls)):
        yield


@pytest.fixture
def baza():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d) / "sporocila.db"


def _cakaj(pogoj, najvec=5.0):
    konec = time.monotonic() + najvec
    while time.monotonic() < konec:
        if pogoj():
            return True
        time.sleep(0.01)
    return pogoj()


def _email_kanal(st, streznik, kid="e1"):
    a = EmailAdapter(kid, "jaz@example.test", "127.0.0.1", "127.0.0.1", streznik.vrata, 465, geslo="skrivno")
    st.registriraj(Kanal(kid, "email", "Posta", "nepovezan"), a, {"naslov": "jaz@example.test"})
    return a


def _besedila(st, kid="e1"):
    return [r[0] for r in st.db.execute("SELECT besedilo FROM sporocila WHERE kanal_id=? ORDER BY rowid", (kid,))]


def _neprebrano(st, kid="e1"):
    return sum(int(r[0]) for r in st.db.execute("SELECT neprebrano FROM pogovori WHERE kanal_id=?", (kid,)))


class _Dogodki:
    def __init__(self):
        self.cas = []
        self.ev = threading.Event()

    def __call__(self):
        self.cas.append(time.monotonic())
        self.ev.set()


# ============================================================ IMAP IDLE
def test_idle_novo_pismo_v_manj_kot_2_s(lokalno, baza):
    srv = LazniImap()
    srv.nabiralnik.dodaj(pismo(mid="a1", telo="Prvo pismo"))
    st = StoritevSporocil(baza)
    try:
        _email_kanal(st, srv)
        st.zazeni_kanal("e1")
        assert _cakaj(lambda: "Prvo pismo" in _besedila(st))
        assert st.delavci() == {"e1": "imap"}
        assert _cakaj(lambda: st._delavci["e1"].stevci["idle"] >= 1)
        zamude = []
        for i in range(5):
            dogodki = _Dogodki()
            st.ob_sinhronizaciji = dogodki
            t0 = time.monotonic()
            srv.nabiralnik.dodaj(pismo(mid="n%d" % i, telo="Novo %d" % i))
            assert _cakaj(lambda: "Novo %d" % i in _besedila(st), 2.0), "pismo ni prispelo v 2 s"
            assert dogodki.ev.wait(1.0)
            zamude.append(dogodki.cas[0] - t0)
        print("\nIMAP IDLE zamuda (s): najvec %.3f, povprecje %.3f" % (max(zamude), sum(zamude) / len(zamude)))
        assert max(zamude) < 2.0
        # Brez novic nit spi: v 1 s ni nobene sinhronizacije (ni vrtenja zanke).
        prej = st._delavci["e1"].stevci["sinhronizacij"]
        time.sleep(1.0)
        assert st._delavci["e1"].stevci["sinhronizacij"] == prej
    finally:
        st.zapri(); srv.ustavi()


def test_idle_prekinjena_povezava_se_obnovi(lokalno, baza):
    srv = LazniImap()
    st = StoritevSporocil(baza)
    try:
        _email_kanal(st, srv)
        st.zazeni_kanal("e1")
        d = st._delavci["e1"]
        assert _cakaj(lambda: d.stevci["idle"] >= 1)
        srv.nabiralnik.prekini_vse()                  # izguba omrezja
        srv.nabiralnik.dodaj(pismo(mid="p1", telo="Po prekinitvi"))
        assert _cakaj(lambda: "Po prekinitvi" in _besedila(st), 5.0)
        assert d.stevci["povezav"] >= 2
        assert _cakaj(lambda: st.kanali()[0].stanje == "povezan")
    finally:
        st.zapri(); srv.ustavi()


def test_ponovna_povezava_ob_spremembi_omrezja(lokalno, baza):
    srv = LazniImap()
    st = StoritevSporocil(baza)
    try:
        _email_kanal(st, srv)
        st.zazeni_kanal("e1")
        d = st._delavci["e1"]
        assert _cakaj(lambda: d.stevci["idle"] >= 1)
        st.ob_spremembi_omrezja()                     # Gio.NetworkMonitor »network-changed« ali prebujenje
        assert _cakaj(lambda: d.stevci["povezav"] >= 2 and d.stevci["idle"] >= 2, 3.0)
    finally:
        st.zapri(); srv.ustavi()


def test_uidvalidity_spremenjen_predpomnilnik_na_novo(lokalno, baza):
    srv = LazniImap()
    for i in range(5):
        srv.nabiralnik.dodaj(pismo(mid="s%d" % i, telo="Staro %d" % i))
    st = StoritevSporocil(baza)
    try:
        a = _email_kanal(st, srv)
        st.sinhroniziraj("e1")
        assert len(_besedila(st)) == 5 and a.zadnji_uid == 5 and a.uidvalidity == 1001
        # Streznik mapo obnovi: ostaneta 2 pisma z UID 1 in 2, novo pismo dobi UID 3 (< zadnji_uid 5).
        with srv.nabiralnik.zaklep:
            srv.nabiralnik.pisma = srv.nabiralnik.pisma[:2]
        srv.nabiralnik.ponastavi_uidvalidity()
        srv.nabiralnik.dodaj(pismo(mid="nov", telo="Novo po obnovi"))
        a.zapri()
        st.sinhroniziraj("e1")
        assert a.uidvalidity == 1002
        assert sorted(_besedila(st)) == ["Novo po obnovi", "Staro 0", "Staro 1"]
        ids = sorted(r[0] for r in st.db.execute("SELECT id FROM sporocila"))
        assert ids == ["uid:1", "uid:2", "uid:3"]
        assert json.loads(st.db.execute("SELECT podatki FROM kanal_stanje").fetchone()[0])["uidvalidity"] == 1002
    finally:
        st.zapri(); srv.ustavi()


@pytest.mark.parametrize("condstore", [True, False])
def test_oznake_v_obe_smeri_in_pravo_stevilo_neprebranih(lokalno, baza, condstore):
    srv = LazniImap(condstore=condstore)
    uidi = [srv.nabiralnik.dodaj(pismo(mid="o%d" % i, telo="Pismo %d" % i)) for i in range(3)]
    st = StoritevSporocil(baza)
    try:
        a = _email_kanal(st, srv)
        st.zazeni_kanal("e1")
        assert _cakaj(lambda: _neprebrano(st) == 3)
        assert _cakaj(lambda: st._delavci["e1"].stevci["idle"] >= 1)
        # Prebrano na telefonu (drug odjemalec): IDLE javi FETCH, stevilo pade brez ponovnega prenosa pisem.
        t0 = time.monotonic()
        srv.nabiralnik.nastavi_prebrano(uidi[0], True)
        assert _cakaj(lambda: _neprebrano(st) == 2, 2.0)
        print("\noznaka z druge naprave (condstore=%s): %.3f s" % (condstore, time.monotonic() - t0))
        srv.nabiralnik.nastavi_prebrano(uidi[0], False)  # spet neprebrano
        assert _cakaj(lambda: _neprebrano(st) == 3, 2.0)
        for _ in range(3):                               # vec sinhronizacij ne napihne stevila (prej sestevek)
            st.sinhroniziraj("e1")
        assert _neprebrano(st) == 3
        if condstore:
            assert a.modseq >= srv.nabiralnik.modseq - 1
            assert any("CHANGEDSINCE" in u for u in srv.nabiralnik.ukazi)
        else:
            assert not any("CHANGEDSINCE" in u for u in srv.nabiralnik.ukazi)
        # Prebrano tukaj: oznaka gre na streznik.
        st.oznaci_prebrano("e1", "ana@example.test")
        assert _neprebrano(st) == 0
        assert _cakaj(lambda: all("\\Seen" in p["zastavice"] for p in srv.nabiralnik.pisma), 3.0)
    finally:
        st.zapri(); srv.ustavi()


def test_streznik_brez_idle_poizveduje(lokalno, baza):
    srv = LazniImap(idle=False)
    st = StoritevSporocil(baza)
    try:
        with mock.patch.object(imap_sprotno, "POIZVEDBA_BREZ_IDLE_S", 0.3):
            _email_kanal(st, srv)
            st.zazeni_kanal("e1")
            assert _cakaj(lambda: st._delavci["e1"].ima_idle is False)
            srv.nabiralnik.dodaj(pismo(mid="x", telo="Brez IDLE"))
            assert _cakaj(lambda: "Brez IDLE" in _besedila(st), 2.0)
    finally:
        st.zapri(); srv.ustavi()


def test_vklop_izklop_kanala_zapre_povezave(lokalno, baza):
    srv = LazniImap()
    st = StoritevSporocil(baza)
    try:
        _email_kanal(st, srv, "e1")
        _email_kanal(st, srv, "e2")
        st.zazeni()
        assert _cakaj(lambda: st.delavci() == {"e1": "imap", "e2": "imap"})
        assert _cakaj(lambda: len(srv.nabiralnik.odjemalci) == 4)      # vsak racun: IDLE + glavna povezava
        st.ustavi_kanal("e1")
        assert st.delavci() == {"e2": "imap"}
        assert _cakaj(lambda: len(srv.nabiralnik.odjemalci) == 2, 3.0)
        st.zazeni()                                   # izklopljenega kanala zazeni() ne vklopi
        assert set(st.delavci()) == {"e2"}
        st.zazeni_kanal("e1")
        assert _cakaj(lambda: set(st.delavci()) == {"e1", "e2"})
        st.ustavi()                                   # Sporocila izklopljena v celoti
        assert st.delavci() == {}
        assert _cakaj(lambda: len(srv.nabiralnik.odjemalci) == 0, 3.0)
        assert not [t for t in threading.enumerate() if t.name == "safeer-imap-idle" and t.is_alive()]
    finally:
        st.zapri(); srv.ustavi()


def test_dolgo_pismo_celotno_besedilo_enkrat(lokalno, baza):
    srv = LazniImap()
    dolgo = ("Vrstica besedila %05d.\n" * 6000) % tuple(range(6000))        # ~140 KB
    srv.nabiralnik.dodaj(pismo(mid="d", telo=dolgo))
    st = StoritevSporocil(baza)
    try:
        _email_kanal(st, srv)
        st.sinhroniziraj("e1")
        prirezano = _besedila(st)[0]
        assert len(prirezano) < len(dolgo.strip())
        assert st.dopolni_besedila("e1", ["uid:1"]) == 1
        assert _besedila(st)[0].rstrip().endswith("05999.")
        n = len(srv.nabiralnik.ukazi)
        assert st.dopolni_besedila("e1", ["uid:1"]) == 0 and len(srv.nabiralnik.ukazi) == n   # samo enkrat
        st.sinhroniziraj("e1")
        assert _besedila(st)[0].rstrip().endswith("05999.")          # sinhronizacija ga ne prireze nazaj
    finally:
        st.zapri(); srv.ustavi()


# ============================================================ Matrix in Telegram: dolga poizvedba
class LazniHttp(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, obravnava):
        self.pogoj = threading.Condition()
        self.dogodki, self.zahteve, self.poslano, self.napake, self.napake_posiljanja = [], [], {}, [], []
        self.nalozeno = []
        self.obravnava = obravnava
        super().__init__(("127.0.0.1", 0), _HttpObravnava)
        threading.Thread(target=self.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        self.url = "http://127.0.0.1:%d" % self.server_address[1]

    def dodaj(self, dogodek):
        with self.pogoj:
            self.dogodki.append(dogodek)
            self.pogoj.notify_all()

    def ustavi(self):
        with self.pogoj:
            self.pogoj.notify_all()
        self.shutdown(); self.server_close()


class _HttpObravnava(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _odgovori(self, koda, telo):
        b = json.dumps(telo).encode()
        self.send_response(koda)
        self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b)))
        self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        self.server.obravnava(self, "GET", b"")

    def do_POST(self):
        self.server.obravnava(self, "POST", self.rfile.read(int(self.headers.get("Content-Length") or 0)))

    do_PUT = do_POST


def _matrix_obravnava(h, metoda, telo):
    srv = h.server
    deli = urlsplit(h.path)
    q = {k: v[0] for k, v in parse_qs(deli.query).items()}
    srv.zahteve.append((metoda, deli.path, q))
    if srv.napake:
        return h._odgovori(srv.napake.pop(0), {"errcode": "M_UNKNOWN"})
    if deli.path.endswith("/_matrix/media/v3/upload"):
        with srv.pogoj:
            srv.nalozeno.append((q.get("filename"), len(telo)))
        return h._odgovori(200, {"content_uri": "mxc://lokalno/d%d" % len(srv.nalozeno)})
    if "/state/m.room.encryption" in deli.path or "/media/" in deli.path:
        return h._odgovori(404, {"errcode": "M_NOT_FOUND"})       # nesifrirana soba; meja nalaganja privzeta
    if deli.path.endswith("/account/whoami"):
        return h._odgovori(200, {"user_id": "@jaz:lokalno"})
    if "/send/m.room.message/" in deli.path:
        txn = deli.path.rsplit("/", 1)[-1]
        if srv.napake_posiljanja:
            # Streznik dogodek objavi, odgovor pa se izgubi (502): odjemalec ne ve, ali je sporocilo odslo.
            with srv.pogoj:
                srv.poslano.setdefault(txn, json.loads(telo)["body"])
            return h._odgovori(srv.napake_posiljanja.pop(0), {"errcode": "M_UNKNOWN"})
        with srv.pogoj:
            if txn not in srv.poslano:               # isti txn = isti dogodek (idempotentno kot Synapse)
                vsebina = json.loads(telo)
                srv.poslano[txn] = vsebina["body"] if vsebina.get("msgtype") == "m.text" else ("datoteka", vsebina["body"])
        return h._odgovori(200, {"event_id": "$" + txn})
    if deli.path.endswith("/sync"):
        od = int(q.get("since") or 0)
        cakaj = int(q.get("timeout") or 0) / 1000
        with srv.pogoj:
            if od >= len(srv.dogodki) and cakaj:
                srv.pogoj.wait_for(lambda: len(srv.dogodki) > od, timeout=cakaj)
            novi = srv.dogodki[od:]
            n = len(srv.dogodki)
        clani = [{"type": "m.room.member", "state_key": u, "content": {"membership": "join", "displayname": i}}
                 for u, i in (("@ana:lokalno", "Ana"), ("@jaz:lokalno", "Jaz"))]
        return h._odgovori(200, {"next_batch": str(n), "rooms": {"join": {"!soba:lokalno": {
            "state": {"events": clani if not od else []}, "timeline": {"events": novi}}}}})
    return h._odgovori(404, {})


def _matrix_dogodek(i, besedilo):
    return {"type": "m.room.message", "event_id": "$m%d" % i, "sender": "@ana:lokalno",
            "origin_server_ts": int(time.time() * 1000), "content": {"msgtype": "m.text", "body": besedilo}}


def test_matrix_dolga_poizvedba_pod_2_s(baza):
    srv = LazniHttp(_matrix_obravnava)
    srv.dodaj(_matrix_dogodek(0, "Prvo"))
    st = StoritevSporocil(baza)
    try:
        a = MatrixAdapter("m1", srv.url, "ZETON-PREIZKUS")
        st.registriraj(Kanal("m1", "matrix", "Matrix", "nepovezan"), a, {"streznik": srv.url})
        st.zazeni_kanal("m1")
        assert st.delavci() == {"m1": "dolga"}
        assert _cakaj(lambda: "Prvo" in _besedila(st, "m1"))
        assert _cakaj(lambda: any(q.get("timeout") == "30000" for _m, p, q in srv.zahteve if p.endswith("/sync")))
        zamude = []
        for i in range(1, 6):
            dogodki = _Dogodki(); st.ob_sinhronizaciji = dogodki
            time.sleep(0.2)                              # zahteva caka na strezniku
            t0 = time.monotonic()
            srv.dodaj(_matrix_dogodek(i, "Sporocilo %d" % i))
            assert _cakaj(lambda: "Sporocilo %d" % i in _besedila(st, "m1"), 2.0)
            assert dogodki.ev.wait(1.0)
            zamude.append(dogodki.cas[0] - t0)
        print("\nMatrix dolgi /sync zamuda (s): najvec %.3f, povprecje %.3f" % (max(zamude), sum(zamude) / len(zamude)))
        assert max(zamude) < 2.0
        # Med cakanjem ni vrtenja: v 1 s najvec ena nova zahteva /sync.
        n = len(srv.zahteve); time.sleep(1.0)
        assert len(srv.zahteve) - n <= 1
        # Izklop kanala prekine tekoco dolgo zahtevo takoj (ne caka 30 s), nit se konca.
        nit = st._delavci["m1"]._nit
        t0 = time.monotonic()
        st.ustavi_kanal("m1")
        assert time.monotonic() - t0 < 1.5 and not nit.is_alive()
        assert st.delavci() == {}
        st.zazeni_kanal("m1")                            # ponovni vklop dela
        srv.dodaj(_matrix_dogodek(9, "Po vklopu"))
        assert _cakaj(lambda: "Po vklopu" in _besedila(st, "m1"), 3.0)
    finally:
        st.zapri(); srv.ustavi()


def test_matrix_napaka_streznika_zamik_in_nadaljevanje(baza):
    srv = LazniHttp(_matrix_obravnava)
    st = StoritevSporocil(baza)
    try:
        a = MatrixAdapter("m1", srv.url, "ZETON-PREIZKUS")
        st.registriraj(Kanal("m1", "matrix", "Matrix", "nepovezan"), a, {})
        srv.napake = [502, 502]
        st.zazeni_kanal("m1")
        srv.dodaj(_matrix_dogodek(0, "Po napaki"))
        assert _cakaj(lambda: "Po napaki" in _besedila(st, "m1"), 6.0)
        assert st._delavci["m1"].stevci["napak"] >= 1
    finally:
        st.zapri(); srv.ustavi()


def _telegram_obravnava(h, metoda, telo):
    srv = h.server
    podatki = json.loads(telo or b"{}")
    pot = urlsplit(h.path).path
    srv.zahteve.append((metoda, pot.rsplit("/", 1)[-1], podatki))
    if pot.endswith("/getMe"):
        return h._odgovori(200, {"ok": True, "result": {"id": 99, "username": "preizkus_bot"}})
    if pot.endswith("/getUpdates"):
        od = int(podatki.get("offset") or 0)
        with srv.pogoj:
            if not [d for d in srv.dogodki if d["update_id"] >= od] and podatki.get("timeout"):
                srv.pogoj.wait_for(lambda: any(d["update_id"] >= od for d in srv.dogodki), timeout=podatki["timeout"])
            novi = [d for d in srv.dogodki if d["update_id"] >= od]
        return h._odgovori(200, {"ok": True, "result": novi})
    return h._odgovori(404, {"ok": False})


def test_telegram_dolga_poizvedba_pod_2_s(baza):
    srv = LazniHttp(_telegram_obravnava)
    st = StoritevSporocil(baza)
    try:
        a = TelegramBotAdapter("t1", "123:ZETON-PREIZKUS")
        a.API = srv.url
        st.registriraj(Kanal("t1", "telegram_bot", "Telegram", "nepovezan"), a, {})
        st.zazeni_kanal("t1")
        assert _cakaj(lambda: any(p == "getUpdates" and d.get("timeout") == 25 for _m, p, d in srv.zahteve))
        time.sleep(0.2)
        t0 = time.monotonic()
        srv.dodaj({"update_id": 7, "message": {"message_id": 1, "date": int(time.time()), "text": "Zivjo bot",
                                               "chat": {"id": 5, "type": "private"}, "from": {"id": 5, "first_name": "Ana"}}})
        assert _cakaj(lambda: "Zivjo bot" in _besedila(st, "t1"), 2.0)
        print("\nTelegram dolgi getUpdates zamuda: %.3f s" % (time.monotonic() - t0))
        t0 = time.monotonic()
        st.ustavi()                                      # Sporocila izklopljena: tudi dolga zahteva se zapre takoj
        assert time.monotonic() - t0 < 1.5 and st.delavci() == {}
    finally:
        st.zapri(); srv.ustavi()


# ============================================================ odhodna vrsta
def test_odhodna_vrsta_enkrat_in_v_vrstnem_redu(baza):
    srv = LazniHttp(_matrix_obravnava)
    st = StoritevSporocil(baza)
    try:
        a = MatrixAdapter("m1", srv.url, "ZETON-PREIZKUS")
        st.registriraj(Kanal("m1", "matrix", "Matrix", "nepovezan"), a, {})
        st.sinhroniziraj("m1")
        pravi = a.streznik
        a.streznik = "http://127.0.0.1:9"                 # streznik ni dosegljiv (zavrnjena povezava)
        poslana = [st.poslji("m1", "!soba:lokalno", "Vrsta %d" % i) for i in range(3)]
        assert [s.stanje for s in poslana] == ["caka"] * 3
        assert [s.besedilo for s in st.sporocila("m1", "!soba:lokalno") if s.stanje == "caka"] == ["Vrsta 0", "Vrsta 1", "Vrsta 2"]
        assert len(st.cakajoca("m1")) == 3
        # Preklic drugega sporocila.
        assert st.preklici_cakajoce("m1", poslana[1].id)
        assert not st.preklici_cakajoce("m1", poslana[1].id)
        # Povezava se vrne, prvi poskus se konca z 502 (streznik je morda ze objavil): ponovitev z istim txn.
        a.streznik = pravi
        srv.napake_posiljanja = [502]
        st.sinhroniziraj("m1")                            # uspesna sinhronizacija izprazni vrsto
        st.sinhroniziraj("m1")
        assert list(srv.poslano.values()) == ["Vrsta 0", "Vrsta 2"]      # vsako enkrat, v vrstnem redu, brez preklicanega
        txn = [p.rsplit("/", 1)[-1] for m, p, q in srv.zahteve if "/send/" in p]
        assert len(txn) == 3 and txn[0] == txn[1] != txn[2]   # ponovitev po 502 z istim txn - streznik ne podvoji
        assert st.cakajoca("m1") == []
        stanja = [(s.besedilo, s.stanje) for s in st.sporocila("m1", "!soba:lokalno") if s.smer == "ven"]
        assert stanja == [("Vrsta 0", "poslano"), ("Vrsta 2", "poslano")]
    finally:
        st.zapri(); srv.ustavi()


def test_odhodna_vrsta_zavrnjeno_takoj_in_po_ponovnem_zagonu(baza):
    srv = LazniHttp(_matrix_obravnava)
    try:
        st = StoritevSporocil(baza)
        a = MatrixAdapter("m1", srv.url, "ZETON-PREIZKUS")
        st.registriraj(Kanal("m1", "matrix", "Matrix", "nepovezan"), a, {})
        srv.napake = [403]
        with pytest.raises(Exception):
            st.poslji("m1", "!soba:lokalno", "Zavrnjeno")    # prijava/pravice: ni vrste, uporabnik izve takoj
        assert st.cakajoca("m1") == []
        a.streznik = "http://127.0.0.1:9"
        s = st.poslji("m1", "!soba:lokalno", "Po zagonu")
        # Program se je koncal sredi posiljanja: ob zagonu se sporocilo vrne v vrsto z istim txn.
        st.db.execute("UPDATE odhodni SET stanje='posiljam', poskus=?", (time.time(),)); st.db.commit()
        drugi = StoritevSporocil(baza)                    # drug primerek (Safeer Link) med posiljanjem ga ne vzame
        assert drugi.cakajoca("m1")[0]["stanje"] == "posiljam"
        drugi.zapri()
        st.db.execute("UPDATE odhodni SET poskus=?", (time.time() - 3600,)); st.db.commit()
        idem = st.cakajoca("m1")[0]["idem"]
        st.zapri()
        st = StoritevSporocil(baza)
        a = MatrixAdapter("m1", srv.url, "ZETON-PREIZKUS")
        st.registriraj(Kanal("m1", "matrix", "Matrix", "nepovezan"), a, {})
        assert st.cakajoca("m1")[0]["stanje"] == "caka" and st.cakajoca("m1")[0]["idem"] == idem
        assert st.poslji_cakajoce("m1") == 1
        assert srv.poslano == {idem: "Po zagonu"}
        assert s.id not in [x.id for x in st.sporocila("m1", "!soba:lokalno")]
        st.zapri()
    finally:
        srv.ustavi()


def test_eposta_vrsta_isti_message_id_ob_ponovitvi(baza):
    smtp = mock.MagicMock()
    poslano = []
    stevec = {"n": 0}

    def tovarna(*_a, **_k):
        stevec["n"] += 1
        if stevec["n"] == 1:
            raise ConnectionRefusedError("ni omrezja")
        return smtp
    smtp.send_message.side_effect = lambda msg: poslano.append(str(msg["Message-ID"]))
    st = StoritevSporocil(baza)
    try:
        a = EmailAdapter("e1", "jaz@example.test", "imap.example.test", "smtp.example.test", geslo="skrivno")
        st.registriraj(Kanal("e1", "email", "Posta", "povezan"), a, {})
        with mock.patch("core.sporocila.email.smtplib.SMTP_SSL", side_effect=tovarna):
            s = st.poslji("e1", "ana@example.test", "Zivjo")
            assert s.stanje == "caka"
            idem = st.cakajoca("e1")[0]["idem"]
            assert st.poslji_cakajoce("e1") == 1
        assert poslano == [idem]
        assert [x.stanje for x in st.sporocila("e1", "ana@example.test")] == ["poslano"]
    finally:
        st.zapri()


# ============================================================ iskanje FTS5, predpomnilnik
def _napolni(st, n, kanal="k1"):
    st.registriraj(Kanal(kanal, "email", "Posta", "povezan"), mock.Mock(vrsta="email"), {})
    with st._zaklep, st.db:
        st.db.execute("INSERT OR IGNORE INTO pogovori(id,kanal_id,oseba_id,zadeva,zadnje_sporocilo,neprebrano,cas,identiteta) "
                      "VALUES('p1',?,'o1','Kosilo','',0,'','')", (kanal,))
        for i in range(n):
            st._shrani_sporocilo(kanal, Sporocilo("s%d" % i, "p1", "noter", "Sporocilo %d o vremenu in kavi" % i,
                                                  "2026-10-%02dT10:00:00+00:00" % (1 + i % 14)))


def test_fts_sprozilci_iskanje_in_nadomestek(baza):
    st = StoritevSporocil(baza)
    try:
        assert st.fts
        _napolni(st, 3)
        st._shrani_sporocilo("k1", Sporocilo("x", "p1", "noter", "Čaj s prijateljico", "2026-10-15T10:00:00+00:00"))
        st.db.commit()
        assert [z["id"] for z in st.isci_sporocila("caj")] == ["x"]        # brez razlike c/č
        assert [z["id"] for z in st.isci_sporocila("prijat")] == ["x"]     # zacetek besede
        assert st.isci_sporocila("kosilo")                                  # zadeva pogovora
        # Znotraj osebe: neposreden pregled njenih sporocil in pot prek indeksa dasta enak izid.
        from core.sporocila import storitev as modul
        assert [z["id"] for z in st.isci_sporocila("ČAJ prij", oseba_id="o1")] == ["x"]
        with mock.patch.object(modul, "PREGLED_NAJVEC", 0):
            assert [z["id"] for z in st.isci_sporocila("ČAJ prij", oseba_id="o1")] == ["x"]
        assert st.isci_sporocila("caj", oseba_id="drug") == []
        assert "Čaj" in st.isci_sporocila("caj", oseba_id="o1")[0]["izsek"]
        # Sprememba besedila (posodobitev obdrzi vrstico) in brisanje sledita indeksu.
        with st.db:
            st._shrani_sporocilo("k1", Sporocilo("x", "p1", "noter", "Kava z bratom", "2026-10-15T10:00:00+00:00"))
        assert st.isci_sporocila("caj") == [] and [z["id"] for z in st.isci_sporocila("bratom")] == ["x"]
        assert st.db.execute("SELECT COUNT(*) FROM sporocila_fts").fetchone()[0] == 4
        st.odstrani_kanal("k1")
        assert st.db.execute("SELECT COUNT(*) FROM sporocila_fts").fetchone()[0] == 0
        # Brez FTS5: LIKE (podniz).
        _napolni(st, 2, "k2")
        st.fts = False
        assert len(st.isci_sporocila("remen")) == 2
    finally:
        st.zapri()


def test_fts_obstojeca_baza_se_indeksira(baza):
    st = StoritevSporocil(baza)
    _napolni(st, 5)
    st.db.execute("DROP TABLE sporocila_fts"); st.db.commit()
    st.zapri()
    st = StoritevSporocil(baza)
    try:
        assert len(st.isci_sporocila("vremenu")) == 5
    finally:
        st.zapri()


def test_ciscenje_predpomnilnika(baza):
    st = StoritevSporocil(baza)
    try:
        _napolni(st, 2)
        with st.db:
            st._shrani_sporocilo("k1", Sporocilo("star", "p1", "noter", "Zelo staro", "2020-01-01T00:00:00+00:00"))
            st._shrani_sporocilo("k1", Sporocilo("caka:1", "p1", "ven", "Neposlano", "2020-01-01T00:00:00+00:00", [], "caka"))
        assert st.pocisti_predpomnilnik(dni=365) == 1
        ids = {r[0] for r in st.db.execute("SELECT id FROM sporocila")}
        assert "star" not in ids and "caka:1" in ids
        assert st.isci_sporocila("staro") == []
        # Omejitev velikosti: brise najstarejsa, dokler baza ni pod mejo.
        _napolni(st, 3000, "k2")
        assert st.pocisti_predpomnilnik(dni=36500, najvec_mb=0.05) > 0
        assert "caka:1" in {r[0] for r in st.db.execute("SELECT id FROM sporocila")}
    finally:
        st.zapri()


def test_neprebrano_po_kanalih_ostane_ob_zagonu(baza):
    st = StoritevSporocil(baza)
    a = mock.Mock(vrsta="chatwoot", spec=["vrsta", "povezi", "pogovori", "sporocila", "poslji", "oznaci_prebrano"])
    a.pogovori.return_value = [Pogovor("c1", "w1", "o1", "", "Zivjo", 4, "2026-10-15T10:00:00+00:00")]
    a.sporocila.return_value = []
    st.registriraj(Kanal("w1", "chatwoot", "Klepet", "nepovezan"), a, {})
    st.sinhroniziraj("w1")
    st.nastavi_neprebrano_kanala("splet-klepet", 2)
    st.zapri()
    st = StoritevSporocil(baza)                        # ponovni zagon: brez povezave, brez adapterjev
    try:
        assert st.neprebrano_po_kanalih() == {"w1": 4, "splet-klepet": 2}
        assert st.neprebrano_skupaj() == 6
    finally:
        st.zapri()


def test_odstranjen_kanal_med_sinhronizacijo_ne_vrne_vrstic(baza):
    st = StoritevSporocil(baza)
    try:
        a = mock.Mock(vrsta="chatwoot", spec=["vrsta", "povezi", "pogovori", "sporocila", "poslji", "oznaci_prebrano"])

        def pogovori():
            st.adapterji.pop("w1", None)               # uporabnik kanal odstrani, medtem ko streznik odgovarja
            return [Pogovor("c1", "w1", "o1", "", "Zivjo", 1, "")]
        a.pogovori.side_effect = pogovori
        a.sporocila.return_value = [Sporocilo("1", "c1", "noter", "Zivjo", "")]
        st.registriraj(Kanal("w1", "chatwoot", "Klepet", "nepovezan"), a, {})
        st.sinhroniziraj("w1")
        assert st.db.execute("SELECT COUNT(*) FROM sporocila").fetchone()[0] == 0
    finally:
        st.zapri()


def test_izbira_niti_po_vrsti_kanala():
    st = mock.Mock()
    assert sprotno.ustvari(st, "k", EmailAdapter("k", "a@b.si", "imap", "smtp")).vrsta == "imap"
    m = MatrixAdapter("k", "https://x.test")
    assert sprotno.ustvari(st, "k", m).vrsta == "dolga" and m.dolgo_cakanje_s == 30
    t = TelegramBotAdapter("k", "1:2")
    assert sprotno.ustvari(st, "k", t).vrsta == "dolga" and t.dolgo_cakanje_s == 25
    assert sprotno.ustvari(st, "k", mock.Mock(vrsta="chatwoot"), 30).interval == 30


# ============================================================ most do vmesnika
def test_most_cakajoce_sporocilo_in_preklic(baza):
    from core.os_sporocila import SporocilaOS
    s = SporocilaOS(baza, zazeni=False)
    try:
        a = MatrixAdapter("m1", "http://127.0.0.1:9", "ZETON-PREIZKUS")     # streznik ni dosegljiv
        a._preverjen = True
        s.storitev.registriraj(Kanal("m1", "matrix", "Matrix", "povezan"), a, {})
        r = s.poslji("m1", "!soba:lokalno", "Brez povezave")
        assert r["caka"] is True and r["stanje"] == "caka"
        assert s.neprebrano_skupaj() == 0
        assert s.preklici("m1", "!soba:lokalno", r["id"]) == []
        with pytest.raises(ValueError):
            s.preklici("m1", "!soba:lokalno", r["id"])
    finally:
        s.zapri()


def test_vmesnik_dogodek_ura_preklic_v_vseh_jezikih():
    koren = Path(__file__).resolve().parent.parent
    os_py = (koren / "safeer_os.py").read_text("utf-8")
    assert '"sporocilaPreklici"' in os_py and "neprebrano_skupaj()" in os_py
    assert '_dogodek("sporocila", {})' in os_py
    js = (koren / "assets/os/os.js").read_text("utf-8")
    assert 'vrsta === "sporocila"' in js and "sporocilaPreklici" in js and 's.stanje === "caka"' in js
    # V obdelavi dogodkov (window.safeerOsDogodek): »if (EN_RAZDELEK) return;« je tudi drugje (Zasloni, prostorSosednji).
    dogodek = js[js.index("window.safeerOsDogodek = function"):]
    assert dogodek.index('if (vrsta === "sporocila") sporocilaSpremenjena();') < dogodek.index("if (EN_RAZDELEK) return;")
    assert 'vrsta !== "sporocila"' in (koren / "assets/os/sporocila-plosca.js").read_text("utf-8")
    besedila = (koren / "assets/os/besedila.js").read_text("utf-8")
    for kljuc in ("sporCaka:", "sporNiPoslano:", "sporPreklici:", "sporPreklicano:", "sporCakaObvestilo:"):
        assert besedila.count(kljuc) == 6, kljuc


def test_znacka_eposte_enaka_strezniku_ne_samo_predpomnilniku(lokalno, baza):
    """INBOX s 250 neprebranimi: predpomnilnik ima zadnjih 200, znacka kanala pa pravo stevilo (STATUS UNSEEN)."""
    srv = LazniImap()
    for i in range(250):
        srv.nabiralnik.dodaj(pismo(od="O%d <o%d@example.test>" % (i, i), mid="z%d" % i, telo="Pismo %d" % i))
    st = StoritevSporocil(baza)
    try:
        _email_kanal(st, srv)
        st.zazeni_kanal("e1")
        assert _cakaj(lambda: st.neprebrano_po_kanalih().get("e1") == 250)
        assert _neprebrano(st) == 200                       # seznam pogovorov: iz predpomnilnika
        assert any(u.startswith("STATUS INBOX") for u in srv.nabiralnik.ukazi)
        assert _cakaj(lambda: st._delavci["e1"].stevci["idle"] >= 1)
        srv.nabiralnik.nastavi_prebrano(1, True)            # najstarejse pismo, ki ga v predpomnilniku ni
        assert _cakaj(lambda: st.neprebrano_po_kanalih().get("e1") == 249, 2.0)
        srv.nabiralnik.dodaj(pismo(mid="novo", telo="Novo"))
        assert _cakaj(lambda: st.neprebrano_po_kanalih().get("e1") == 250, 2.0)
        st.oznaci_prebrano("e1", "o249@example.test")       # prebrano tukaj: znacka takoj, streznik potrdi
        assert st.neprebrano_po_kanalih()["e1"] == 249
        assert _cakaj(lambda: st.neprebrano_skupaj() == 249, 3.0)
    finally:
        st.zapri(); srv.ustavi()


def test_odhodna_vrsta_s_prilogo(baza, tmp_path):
    """Sporocilo s prilogo brez povezave: v pogovoru takoj s prilogo (lokalno), ob vrnitvi povezave enkrat poslano."""
    datoteka = tmp_path / "porocilo.pdf"
    datoteka.write_bytes(b"%PDF-1.4 preizkus" * 100)
    srv = LazniHttp(_matrix_obravnava)
    st = StoritevSporocil(baza)
    try:
        a = MatrixAdapter("m1", srv.url, "ZETON-PREIZKUS")
        st.registriraj(Kanal("m1", "matrix", "Matrix", "nepovezan"), a, {})
        st.sinhroniziraj("m1")
        pravi, a.streznik = a.streznik, "http://127.0.0.1:9"
        s = st.poslji("m1", "!soba:lokalno", "Priloga", [{"pot": str(datoteka)}])
        assert s.stanje == "caka"
        caka = [x for x in st.sporocila("m1", "!soba:lokalno") if x.stanje == "caka"][0]
        assert caka.priponke[0]["ime"] == "porocilo.pdf" and caka.priponke[0]["lokalno"] == str(datoteka)
        assert json.loads(st.cakajoca("m1")[0]["priponke"]) == [{"pot": str(datoteka)}]
        a.streznik = pravi
        st.sinhroniziraj("m1")
        assert srv.nalozeno == [("porocilo.pdf", 1700)]
        assert sorted(map(str, srv.poslano.values())) == sorted(["Priloga", str(("datoteka", "porocilo.pdf"))])
        assert st.cakajoca("m1") == []
        # Priloga, ki je pred vrnitvijo povezave izginila: sporocilo je »ni poslano«, vrsta ni zablokirana.
        a.streznik = "http://127.0.0.1:9"
        izgubljena = tmp_path / "izgubljena.txt"; izgubljena.write_text("x")
        st.poslji("m1", "!soba:lokalno", "", [{"pot": str(izgubljena)}])
        st.poslji("m1", "!soba:lokalno", "Za njo")
        izgubljena.unlink()
        a.streznik = pravi
        st.sinhroniziraj("m1")
        assert st.cakajoca("m1") == []
        stanja = {(x.besedilo, x.stanje) for x in st.sporocila("m1", "!soba:lokalno") if x.smer == "ven"}
        assert ("", "napaka") in stanja and ("Za njo", "poslano") in stanja and ("Priloga", "poslano") in stanja
    finally:
        st.zapri(); srv.ustavi()


def test_dolgo_pismo_s_priponko_prenese_samo_del_z_besedilom(lokalno, baza):
    """Celotno besedilo po delih (BODYSTRUCTURE): 1 MB priponke pred besedilom se ne prenasa znova."""
    import base64
    besedilo = ("Dolga vrstica %05d.\r\n" * 5000) % tuple(range(5000))
    priponka = base64.encodebytes(b"\0" * 750000).replace(b"\n", b"\r\n")
    surovo = (b"From: Ana <ana@example.test>\r\nTo: jaz@example.test\r\nSubject: Dolgo\r\n"
              b"Date: Thu, 15 Oct 2026 10:00:00 +0000\r\nMessage-ID: <dolgo@example.test>\r\nMIME-Version: 1.0\r\n"
              b'Content-Type: multipart/mixed; boundary="MEJA"\r\n\r\n'
              b'--MEJA\r\nContent-Type: application/octet-stream\r\nContent-Transfer-Encoding: base64\r\n'
              b'Content-Disposition: attachment; filename="velika.bin"\r\n\r\n' + priponka + b"\r\n"
              b"--MEJA\r\nContent-Type: text/plain; charset=utf-8\r\n\r\n" + besedilo.encode() + b"\r\n--MEJA--\r\n")
    srv = LazniImap()
    srv.nabiralnik.dodaj(surovo)
    st = StoritevSporocil(baza)
    try:
        _email_kanal(st, srv)
        st.sinhroniziraj("e1")
        assert _besedila(st)[0].startswith("Dolga vrstica 00000.") and not _besedila(st)[0].rstrip().endswith("04999.")
        n = len(srv.nabiralnik.ukazi)
        assert st.dopolni_besedila("e1", ["uid:1"]) == 1
        assert _besedila(st)[0].rstrip().endswith("04999.")
        novi = srv.nabiralnik.ukazi[n:]
        assert any("BODY.PEEK[2]" in u for u in novi)
        assert not any("BODY.PEEK[1]" in u or "BODY.PEEK[]" in u for u in novi)   # priponke ne prenasamo
    finally:
        st.zapri(); srv.ustavi()
