"""Sporocila, testni PC 15. 10. 2026 (Safeer OS 0.4.84 Flatpak):

1. »PDF nima predogleda«: cip PDF priponke je imel samo ikono (slicice so bile samo za slike), v Flatpaku pa ni bilo
   pdftoppm. Zdaj prva stran PDF kot slicica (kot Gmail), pdftoppm tece loceno s casovno mejo.
2. Novo pismo brez znacke in obvestila: pismo samemu sebi je slo med »poslano« (samo v mapo Poslano, brez znacke),
   osvezitev odprtega pogovora v ozadju je novo pismo takoj oznacila kot prebrano, obvestila namizja za e-posto ni bilo.

Brez omrezja in brez pravih racunov: lokalni nadomestni streznik IMAP (tests/lazni_imap.py, 127.0.0.1).
"""
import imaplib
import os
import re
import shutil
import socket
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import pytest

from core import os_datoteke, os_sporocila
from core.sporocila import imap_sprotno
from core.sporocila.email import EmailAdapter
from core.sporocila.model import Kanal, Sporocilo
from core.sporocila.storitev import StoritevSporocil
from lazni_imap import LazniImap, pismo

KOREN = Path(__file__).resolve().parent.parent
JAZ = "jaz@example.test"


def _pdf() -> bytes:
    """Najmanjsi veljaven PDF z eno stranjo in besedilom."""
    vsebina = b"BT /F1 24 Tf 20 250 Td (Safeer) Tj ET"
    deli = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 300] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            b"<< /Length %d >>\nstream\n" % len(vsebina) + vsebina + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    t, odmiki = b"%PDF-1.4\n", []
    for i, d in enumerate(deli, 1):
        odmiki.append(len(t))
        t += b"%d 0 obj\n" % i + d + b"\nendobj\n"
    x = len(t)
    t += b"xref\n0 %d\n0000000000 65535 f \n" % (len(deli) + 1) + b"".join(b"%010d 00000 n \n" % o for o in odmiki)
    return t + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(deli) + 1, x)


# ============================================================ 1. slicica prve strani PDF
class _Adapter:
    vrsta = "email"
    zmore = {"poslji", "priloge"}

    def __init__(self, vsebina: bytes):
        self.vsebina, self.klici, self.oznaceno = vsebina, 0, []

    def prenesi_priponko(self, sid, p, pisi, napredek=None):
        self.klici += 1
        pisi(self.vsebina)
        return len(self.vsebina)

    def oznaci_prebrano(self, pogovor_id):
        self.oznaceno.append(pogovor_id)


class SlicicaPdf(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        koren = Path(self.d.name)
        self.okolje = mock.patch.dict(os.environ, {"HOME": str(koren), "XDG_CACHE_HOME": str(koren / ".cache"),
                                                   "XDG_CONFIG_HOME": str(koren / ".config")})
        self.okolje.start()
        self.os = os_sporocila.SporocilaOS(koren / "sp.db", zazeni=False)
        self.adapter = _Adapter(_pdf())
        st = self.os.storitev
        st.registriraj(Kanal("k", "email", "Posta"), self.adapter, {"naslov": JAZ})
        with st.db:
            st._shrani_sporocilo("k", Sporocilo("uid:9", "ana@example.test", "noter", "", "2026-10-15T20:16:05+00:00", [
                {"ime": "Ponudba.pdf", "tip": "application/pdf", "velikost": 900, "del": "2", "kodiranje": "base64"},
                {"ime": "Velik.pdf", "tip": "application/pdf", "velikost": os_sporocila.MEJA_SLICICE_PDF + 1, "del": "3"},
                {"ime": "racun.pdf.exe", "tip": "application/octet-stream", "velikost": 900, "del": "4"},
            ], "prejeto"))

    def tearDown(self):
        self.os.storitev.zapri()
        self.okolje.stop()
        self.d.cleanup()

    @unittest.skipUnless(shutil.which("pdftoppm"), "brez pdftoppm")
    def test_prva_stran_kot_slicica_iz_predpomnilnika(self):
        pot = self.os.priponka_slicica("k", "uid:9", "2")
        self.assertTrue(pot.endswith("slicica-pdf.png"), pot)
        with open(pot, "rb") as f:
            self.assertEqual(f.read(8), b"\x89PNG\r\n\x1a\n")
        self.assertEqual(os.stat(pot).st_mode & 0o777, 0o600)       # stran zasebnega dokumenta vidi samo uporabnik
        self.assertEqual(self.os.priponka_slicica("k", "uid:9", "2"), pot)
        self.assertEqual(self.adapter.klici, 1)                      # drugic brez omrezja in brez pdftoppm

    def test_brez_pdftoppm_ni_slicice_in_ni_prenosa(self):
        with mock.patch("core.os_sporocila.shutil.which", return_value=None):
            self.assertEqual(self.os.priponka_slicica("k", "uid:9", "2"), "")
        self.assertEqual(self.adapter.klici, 0)                      # PDF-ja samo zaradi slicice ne prenasamo

    def test_prevelik_in_nevaren_brez_slicice(self):
        self.assertEqual(self.os.priponka_slicica("k", "uid:9", "3"), "")
        self.assertEqual(self.os.priponka_slicica("k", "uid:9", "4"), "")
        self.assertEqual(self.adapter.klici, 0)

    def test_pokvarjen_pdf_pdftoppm_pade_brez_pokvarjene_slicice(self):
        orodja = Path(self.d.name) / "bin"
        orodja.mkdir()
        orodje = orodja / "pdftoppm"
        # Kot pdftoppm, ki na pokvarjenem PDF-ju napise pol slike in pade.
        orodje.write_text('#!/bin/sh\nfor a; do z="$a"; done\nprintf "\\211PNG pol" > "$z.png"\nexit 1\n')
        orodje.chmod(0o755)
        najdi = lambda ime: str(orodje) if ime == "pdftoppm" else None  # noqa: E731
        with mock.patch("core.os_sporocila.shutil.which", najdi), mock.patch("core.os_datoteke.shutil.which", najdi), \
                mock.patch.object(os_datoteke.slika_prve_strani, "__defaults__", (1200, najdi, 15)):
            self.assertEqual(self.os.priponka_slicica("k", "uid:9", "2"), "")
        vnos = self.os.mapa_vnosa("k", "uid:9", "2")
        self.assertEqual([f for f in os.listdir(vnos) if f.endswith(".png") or ".png." in f or f.startswith("slicica")], [])

    def test_obvisel_pdftoppm_prekine_casovna_meja(self):
        orodja = Path(self.d.name) / "bin"
        orodja.mkdir()
        orodje = orodja / "pdftoppm"
        orodje.write_text("#!/bin/sh\nexec sleep 30\n")
        orodje.chmod(0o755)
        pdf = Path(self.d.name) / "a.pdf"
        pdf.write_bytes(_pdf())
        t0 = time.monotonic()
        ok = os_datoteke.slika_prve_strani(str(pdf), str(Path(self.d.name) / "a.png"), 160,
                                           najdi=lambda _i: str(orodje), cas=0.5)
        self.assertFalse(ok)
        self.assertLess(time.monotonic() - t0, 5)
        self.assertFalse((Path(self.d.name) / "a.png").exists())


def test_cip_pdf_zahteva_slicico():
    """os.js: cip PDF priponke zahteva slicico (iste meje kot Python) in jo pokaze od vrha strani."""
    js = (KOREN / "assets" / "os" / "os.js").read_text(encoding="utf-8")
    assert 'var pdf = a.predogled === "pdf" && !a.nevarna && a.velikost <= 25 * 1024 * 1024;' in js
    assert 'var slika = pdf || (a.predogled === "slika"' in js
    assert os_sporocila.MEJA_SLICICE_PDF == 25 * 1024 * 1024
    css = (KOREN / "assets" / "os" / "os.css").read_text(encoding="utf-8")
    assert ".priponka.s-stranjo .priponka-ikona img { object-position:top;" in css


def test_flatpak_ima_pdftoppm_in_deb_poppler():
    """Runtime GNOME 50 nima popplerja: modul v manifestu (samo pdftoppm), deb zahteva poppler-utils. Brez PyYAML
    (posel deb-appimage ga nima): besedilo manifesta."""
    m = (KOREN / "io.github.memelandfaner.SafeerOS.yml").read_text(encoding="utf-8")
    assert "  - name: poppler-pdftoppm\n" in m
    assert m.index("  - name: poppler-pdftoppm\n") < m.index("  - name: safeer-os\n")
    modul = m.split("  - name: poppler-pdftoppm\n", 1)[1].split("\n  - name: ", 1)[0]
    assert re.search(r"url: https://poppler\.freedesktop\.org/poppler-[\d.]+\.tar\.xz\n\s+sha256: [0-9a-f]{64}", modul)
    assert "-DENABLE_LIBCURL=OFF" in modul and "- /bin/pdftotext" in modul and "- /bin/pdftoppm" not in modul
    assert "poppler-utils" in (KOREN / "build_os_deb.sh").read_text(encoding="utf-8").split("Depends:", 1)[1].split("\n", 1)[0]


# ============================================================ 2. novo pismo: samemu sebi, znacka, obvestilo
def _imap_brez_tls(host, port=993, ssl_context=None, timeout=None):
    return imaplib.IMAP4(host, port, timeout=timeout)


def _idle_brez_tls(gostitelj, vrata, kontekst=None):
    return imap_sprotno.PovezavaIdle(socket.create_connection((gostitelj, vrata), timeout=5))


@pytest.fixture
def lokalno():
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


def _kanal(st, srv, kid="e1"):
    a = EmailAdapter(kid, JAZ, "127.0.0.1", "127.0.0.1", srv.vrata, 465, geslo="skrivno")
    st.registriraj(Kanal(kid, "email", "Posta", "nepovezan"), a, {"naslov": JAZ})
    return a


def _vrstica(st, besedilo, kid="e1"):
    return st.db.execute("SELECT * FROM sporocila WHERE kanal_id=? AND besedilo=?", (kid, besedilo)).fetchone()


def test_pismo_samemu_sebi_je_v_prejetem_neprebrano_z_obvestilom(lokalno, baza):
    """Gmail in Outlook pismo samemu sebi pokazeta v Prejetem; ce je na strezniku neprebrano, ga stejeta."""
    srv = LazniImap()
    srv.nabiralnik.dodaj(pismo(mid="star", telo="Staro pismo"), prebrano=True)
    st = StoritevSporocil(baza)
    nova = []
    st.ob_novih = lambda kid, n: nova.extend((kid, p.id, s.id) for p, _o, s in n)
    try:
        _kanal(st, srv)
        st.zazeni_kanal("e1")
        assert _cakaj(lambda: _vrstica(st, "Staro pismo") is not None)
        assert nova == []                                      # prvi uvoz predala: stara pisma niso »nova«
        assert _cakaj(lambda: st._delavci["e1"].stevci["idle"] >= 1)
        uid = srv.nabiralnik.dodaj(pismo(od="Jaz <%s>" % JAZ, komu=JAZ, mid="sebi", telo="Opomnik sebi"))
        assert _cakaj(lambda: _vrstica(st, "Opomnik sebi") is not None, 3.0), "IDLE: pismo ni prispelo"
        r = _vrstica(st, "Opomnik sebi")
        assert (r["smer"], r["stanje"], r["pogovor_id"]) == ("noter", "prejeto", JAZ)
        assert _cakaj(lambda: st.neprebrano_po_kanalih().get("e1") == 1)
        p = st.db.execute("SELECT neprebrano FROM pogovori WHERE kanal_id='e1' AND id=?", (JAZ,)).fetchone()
        assert p["neprebrano"] == 1
        assert st.zadnje_smeri()[("e1", JAZ)] == "noter"       # v Prejetem, ne samo v mapi Poslano
        assert _cakaj(lambda: ("e1", JAZ, "uid:%d" % uid) in nova)
        assert len(nova) == 1
    finally:
        st.zapri(); srv.ustavi()


def test_pismo_sebi_ze_prebrano_na_strezniku_je_novo_a_ne_neprebrano(lokalno, baza):
    """Ce ga streznik shrani kot \\Seen, je pismo vseeno prispelo (obvestilo »novo«), znacka pa ne laze."""
    srv = LazniImap()
    srv.nabiralnik.dodaj(pismo(mid="star", telo="Staro"), prebrano=True)
    st = StoritevSporocil(baza)
    nova = []
    st.ob_novih = lambda kid, n: nova.extend(s.id for _p, _o, s in n)
    try:
        _kanal(st, srv)
        st.zazeni_kanal("e1")
        assert _cakaj(lambda: st._delavci["e1"].stevci["idle"] >= 1 and _vrstica(st, "Staro") is not None)
        uid = srv.nabiralnik.dodaj(pismo(od=JAZ, komu="Jaz <%s>" % JAZ.upper(), mid="s2", telo="Ze prebrano"),
                                   prebrano=True)
        assert _cakaj(lambda: _vrstica(st, "Ze prebrano") is not None, 3.0)
        r = _vrstica(st, "Ze prebrano")
        assert (r["smer"], r["stanje"]) == ("noter", "prebrano")
        assert _cakaj(lambda: "uid:%d" % uid in nova)
        assert st.neprebrano_po_kanalih().get("e1") == 0
    finally:
        st.zapri(); srv.ustavi()


def test_lastna_kopija_pisma_drugemu_ostane_poslano(lokalno, baza):
    """From = jaz, To = nekdo drug (npr. Bcc sebi): uporabnik je pisal drugemu - »poslano« v niti z njim, brez obvestila."""
    srv = LazniImap()
    srv.nabiralnik.dodaj(pismo(mid="star", telo="Staro"), prebrano=True)
    st = StoritevSporocil(baza)
    nova = []
    st.ob_novih = lambda kid, n: nova.extend(n)
    try:
        _kanal(st, srv)
        st.zazeni_kanal("e1")
        assert _cakaj(lambda: st._delavci["e1"].stevci["idle"] >= 1 and _vrstica(st, "Staro") is not None)
        srv.nabiralnik.dodaj(pismo(od=JAZ, komu="Ana <ana@example.test>", mid="bcc", telo="Kopija zame"))
        assert _cakaj(lambda: _vrstica(st, "Kopija zame") is not None, 3.0)
        r = _vrstica(st, "Kopija zame")
        assert (r["smer"], r["stanje"], r["pogovor_id"]) == ("ven", "poslano", "ana@example.test")
        time.sleep(0.2)
        assert nova == []
    finally:
        st.zapri(); srv.ustavi()


def test_obvestilo_ime_in_zadeva_ne_ob_izklopljenih():
    with tempfile.TemporaryDirectory() as d:
        okolje = mock.patch.dict(os.environ, {"HOME": d, "XDG_CONFIG_HOME": os.path.join(d, ".config"),
                                              "XDG_CACHE_HOME": os.path.join(d, ".cache")})
        okolje.start()
        try:
            sp = os_sporocila.SporocilaOS(Path(d) / "sp.db", zazeni=False)
            poslano = []
            sp.obvesti_novo = lambda *a: poslano.append(a)
            from core.sporocila.model import Pogovor
            oseba = sp.storitev._oseba("email", "ana@example.test", "Ana Novak")
            p = Pogovor("ana@example.test", "k", "ana@example.test", "Ponudba")
            s1 = Sporocilo("uid:5", "ana@example.test", "noter", "Prvo  besedilo\nv dveh vrsticah", "2026-10-15T20:00:00+00:00")
            s2 = Sporocilo("uid:6", "ana@example.test", "noter", "Drugo", "2026-10-15T20:01:00+00:00")
            sp._ob_novih("k", [(p, oseba, s1), (p, oseba, s2)])
            assert poslano == [("k", "ana@example.test", "Ana Novak (2)", "Ponudba - Drugo")]
            poslano.clear()
            with mock.patch("core.os_sporocila._vklop.izklopljeni_kanali", return_value={"k"}):
                sp._ob_novih("k", [(p, oseba, s1)])
            with mock.patch("core.os_sporocila._vklop.sporocila_vklopljena", return_value=False):
                sp._ob_novih("k", [(p, oseba, s1)])
            assert poslano == []
            sp.storitev.zapri()
        finally:
            okolje.stop()


def test_osvezitev_v_ozadju_ne_oznaci_prebranega():
    """Odprt pogovor, okno v ozadju: novo pismo ostane neprebrano (znacka); ko uporabnik pogleda, se oznaci."""
    with tempfile.TemporaryDirectory() as d:
        okolje = mock.patch.dict(os.environ, {"HOME": d, "XDG_CONFIG_HOME": os.path.join(d, ".config"),
                                              "XDG_CACHE_HOME": os.path.join(d, ".cache")})
        okolje.start()
        try:
            sp = os_sporocila.SporocilaOS(Path(d) / "sp.db", zazeni=False)
            a = _Adapter(b"")
            st = sp.storitev
            st.registriraj(Kanal("k", "email", "Posta"), a, {"naslov": JAZ})
            with st.db:
                st._shrani_sporocilo("k", Sporocilo("uid:3", "ana@example.test", "noter", "Novo", "2026-10-15T20:00:00+00:00"))
                st.db.execute("INSERT INTO pogovori(id,kanal_id,oseba_id,zadeva,zadnje_sporocilo,neprebrano,cas,identiteta) "
                              "VALUES('ana@example.test','k','o1','Z','Novo',1,'2026-10-15T20:00:00+00:00','ana@example.test')")
            assert [s["besedilo"] for s in sp.pogovor("k", "ana@example.test", False)] == ["Novo"]
            stanje = lambda: st.db.execute("SELECT stanje FROM sporocila WHERE id='uid:3'").fetchone()[0]  # noqa: E731
            assert stanje() == "prejeto"
            assert st.db.execute("SELECT neprebrano FROM pogovori").fetchone()[0] == 1
            sp.pogovor("k", "ana@example.test")                 # uporabnik pogleda (privzeto oznaci)
            assert stanje() == "prebrano"
            assert _cakaj(lambda: a.oznaceno == ["ana@example.test"], 2.0)
            st.zapri()
        finally:
            okolje.stop()


def test_os_js_oznaci_samo_ko_uporabnik_vidi():
    js = (KOREN / "assets" / "os" / "os.js").read_text(encoding="utf-8")
    assert 'klic("sporocilaPogovor", [pogovor.kanal_id, pogovor.id, !!odpiranje || uporabnikVidi()])' in js
    assert 'document.visibilityState !== "hidden"' in js and "document.hasFocus()" in js
    py = (KOREN / "safeer_os.py").read_text(encoding="utf-8")
    assert '"sporocilaPogovor": lambda: self.sporocila.pogovor(str(a[0]), str(a[1]), a[2] is not False' in py
    assert "self.sporocila.obvesti_novo = self._obvesti_novo_pismo" in py
