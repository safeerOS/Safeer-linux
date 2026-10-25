"""Izbris sporocil Safeer Chat (lastnik 23. 10. 2026, OBVEZNO): pri meni, na vseh mojih napravah (chat.delete,
zdruzljivo z Androidom - SporocilaPravila.kt, naloga 116, pregled D4/D5) in cel pogovor. Brez omrezja in brez Linka."""
import json
import tempfile
import time
import uuid
from pathlib import Path
from unittest import mock

import pytest

from core import os_sporocila
from core.os_sporocila import KANAL_LINKA, SporocilaOS
from core.sporocila import izbris_linka as I
from core.sporocila.safeer_chat import preveri_tovor

UUID1 = "0f8fad5b-d9cb-469f-a165-70867728950e"
UUID2 = "7c9e6679-7425-40de-944b-e07fc1f90ae7"


@pytest.fixture
def sp():
    with tempfile.TemporaryDirectory() as d:
        s = SporocilaOS(Path(d) / "s.sqlite3", zazeni=False)
        yield s
        s.zapri()


def _ids(s, pogovor="fon1"):
    return [m["id"] for m in s.pogovor(KANAL_LINKA, pogovor, oznaci=False)]


# ---------------------------------------------------------------------------- ciste odlocitve (kot Android)

def test_pravila_kot_android():
    assert I.ZMOZNOST_IZBRIS == "chat.delete" and I.BESEDILO_IZBRISA == "\U0001F5D1"
    assert I.skupni_id("chat:ven:" + UUID1, "ven") == UUID1
    assert I.skupni_id("chat:ven:" + uuid.uuid4().hex, "ven") is None, "star krajevni id: izbrisa drugje ni"
    assert I.skupni_id("chat:" + UUID1, "noter") is None
    assert I.prejeti_id(UUID1) == "chat:" + UUID1
    assert I.zahteva_velja("noter", "fon1", "fon1")
    assert not I.zahteva_velja("ven", "fon1", "fon1"), "nasih lastnih ne brise tuja zahteva"
    assert not I.zahteva_velja("noter", "fon1", "tv1"), "tuja naprava ne brise sporocil drugih"
    assert not I.zahteva_velja("noter", "fon1", "")
    assert I.sme_zapisati_vnaprej("fon1", UUID1) and not I.sme_zapisati_vnaprej("fon1", "klepet-x")
    assert not I.sme_zapisati_vnaprej("", UUID1)
    zdaj = 1_000_000.0
    assert I.vnaprej_velja(zdaj + 10, zdaj) and not I.vnaprej_velja(zdaj - 1, zdaj)
    assert not I.vnaprej_velja(zdaj + I.VNAPREJ_VELJA_S + 5, zdaj), "ura prestavljena nazaj"
    assert I.izid_brisanja("accepted", zdaj, zdaj) == I.KONCANO == I.izid_brisanja("queued", zdaj, zdaj)
    assert I.izid_brisanja("ni_naprave", zdaj, zdaj) == I.OPUSTI == I.izid_brisanja("isti_naprava", zdaj, zdaj)
    assert I.izid_brisanja("ni_povezave", zdaj, zdaj) == I.PONOVI == I.izid_brisanja("ne_zna", zdaj, zdaj)
    assert I.izid_brisanja("potek", zdaj - I.BRISANJE_NAJDLJE_S - 1, zdaj) == I.OPUSTI
    assert I.izbris_na_drugi([]) == I.NA_DRUGI_NEZNANO
    assert I.izbris_na_drugi([["url"], ["chat", "chat.delete"]]) == I.NA_DRUGI_DA
    assert I.izbris_na_drugi([["chat"]]) == I.NA_DRUGI_NE


def test_tovor_nosi_zahtevo_za_izbris():
    assert preveri_tovor({"text": I.BESEDILO_IZBRISA, "delete": UUID1})["delete"] == UUID1
    assert "delete" not in preveri_tovor({"text": "zivjo"})


# ---------------------------------------------------------------------------- pri meni in pogovor

def test_izbrisi_pri_meni_in_ponovna_dostava_ga_ne_obudi(sp):
    assert sp.prejmi_klepet("fon1", "Telefon", "prvo", sid=UUID1)
    assert sp.prejmi_klepet("fon1", "Telefon", "drugo", sid=UUID2)
    izid = sp.izbrisi_sporocilo(KANAL_LINKA, "fon1", "chat:" + UUID2)
    assert izid["izbris"] == "" and [m["id"] for m in izid["sporocila"]] == ["chat:" + UUID1]
    p = sp.seznam()["skupine"][0]["pogovori"][0]
    assert p["zadnje_sporocilo"] == "prvo" and p["neprebrano"] == 1, "izbrisano neprebrano se ne steje"
    assert not sp.prejmi_klepet("fon1", "Telefon", "drugo", sid=UUID2), "sredisce je dostavilo znova iz vrste"
    assert _ids(sp) == ["chat:" + UUID1]


def test_izbris_samo_v_safeer_linku(sp):
    with pytest.raises(ValueError):
        sp.izbrisi_sporocilo("e1", "ana@example.test", "uid:1")
    with pytest.raises(ValueError):
        sp.izbrisi_sporocilo(KANAL_LINKA, "fon1", "chat:ni-ga")


def test_izbris_pogovora_novo_sporocilo_ga_vrne(sp):
    sp.prejmi_klepet("fon1", "Telefon", "prvo", sid=UUID1)
    k = next(k for k in sp.seznam()["kanali"] if k["id"] == KANAL_LINKA)
    assert "izbrisi_pogovor" in k["dejanja"] and "izbrisi" not in k["dejanja"], "brez Kosa (ne »V Koš«)"
    izid = sp.dejanje([[KANAL_LINKA, "fon1"]], "izbrisi_pogovor")
    assert izid["napake"] == [] and izid["skupine"] == []
    assert not sp.prejmi_klepet("fon1", "Telefon", "prvo", sid=UUID1), "staro sporocilo ga ne vrne"
    assert sp.seznam()["skupine"] == []
    assert sp.prejmi_klepet("fon1", "Telefon", "novo", sid=UUID2)
    assert [p["id"] for p in sp.seznam()["skupine"][0]["pogovori"]] == ["fon1"]
    assert _ids(sp) == ["chat:" + UUID2]


# ---------------------------------------------------------------------------- na vseh mojih napravah

def _poslano(sp, skupni=UUID1, stanje="accepted"):
    sp.poslji_klepet = lambda n, b, c: {"stanje": stanje, "id": skupni}
    return sp.poslji(KANAL_LINKA, "fon1", "Ob desetih")


def test_poslano_dobi_skupni_id_od_controla(sp):
    assert _poslano(sp)["id"] == "chat:ven:" + UUID1
    sp.poslji_klepet = lambda n, b, c: "queued"                  # starejsi Control: samo stanje
    assert not I.skupni_id(sp.poslji(KANAL_LINKA, "fon1", "x")["id"], "ven")


def test_izbrisi_na_vseh_poslje_zahtevo(sp):
    _poslano(sp)
    poslano = []
    sp.izbrisi_klepet = lambda n, i: poslano.append((n, i)) or "accepted"
    izid = sp.izbrisi_sporocilo(KANAL_LINKA, "fon1", "chat:ven:" + UUID1, na_vseh=True)
    assert izid["izbris"] == "koncano" and poslano == [("fon1", UUID1)]
    assert _ids(sp) == [] and not os_sporocila.cakajo_brisanja(sp.storitev.pot)


def test_izbris_brez_povezave_pocaka_in_odide_ob_povezavi(sp):
    _poslano(sp)
    sp.izbrisi_klepet = lambda n, i: "ni_povezave"
    assert sp.izbrisi_sporocilo(KANAL_LINKA, "fon1", "chat:ven:" + UUID1, na_vseh=True)["izbris"] == "caka"
    assert os_sporocila.cakajo_brisanja(sp.storitev.pot)
    sp.izbrisi_klepet = lambda n, i: "ne_zna"                    # naprava je tu, izbrisa se ne javi: se caka
    assert sp.poslji_cakajoca_brisanja() == 0 and os_sporocila.cakajo_brisanja(sp.storitev.pot)
    sp.izbrisi_klepet = lambda n, i: "queued"
    assert sp.poslji_cakajoca_brisanja() == 1
    assert not os_sporocila.cakajo_brisanja(sp.storitev.pot)


def test_izbris_na_vseh_samo_za_lastno_s_skupnim_id(sp):
    sp.prejmi_klepet("fon1", "Telefon", "prejeto", sid=UUID1)
    with pytest.raises(ValueError):
        sp.izbrisi_sporocilo(KANAL_LINKA, "fon1", "chat:" + UUID1, na_vseh=True)
    assert _ids(sp) == ["chat:" + UUID1], "nic ni izbrisano"


def test_prestar_izbris_se_opusti(sp):
    _poslano(sp)
    sp.izbrisi_klepet = lambda n, i: "ni_povezave"
    sp.izbrisi_sporocilo(KANAL_LINKA, "fon1", "chat:ven:" + UUID1, na_vseh=True)
    with mock.patch.object(os_sporocila.time, "time", return_value=time.time() + I.BRISANJE_NAJDLJE_S + 60):
        sp.poslji_cakajoca_brisanja()
    assert not os_sporocila.cakajo_brisanja(sp.storitev.pot)


# ---------------------------------------------------------------------------- zahteva z druge naprave

def test_zahteva_izbrise_samo_sporocilo_posiljatelja(sp):
    sp.prejmi_klepet("fon1", "Telefon", "od telefona", sid=UUID1)
    sp.prejmi_klepet("tv1", "TV", "od televizorja", sid=UUID2)
    assert not sp.prejmi_izbris("tv1", UUID1), "TV ne brise sporocila telefona"
    assert not sp.prejmi_izbris("fon1", UUID2), "telefon ne brise sporocila televizorja"
    assert sp.prejmi_izbris("fon1", UUID1)
    assert _ids(sp, "fon1") == [] and _ids(sp, "tv1") == ["chat:" + UUID2]
    assert not sp.prejmi_izbris("fon1", UUID1), "ze izbrisano: prezremo"


def test_zahteva_ne_brise_nasih_poslanih(sp):
    _poslano(sp)
    assert not sp.prejmi_izbris("fon1", UUID1)
    assert _ids(sp) == ["chat:ven:" + UUID1]


def test_zahteva_pred_izvirnikom(sp):
    """Pregled D4: sredisce je zahtevo dostavilo pred sporocilom - izvirnik se ob prihodu ne shrani."""
    assert not sp.prejmi_izbris("fon1", UUID1)
    assert not sp.prejmi_klepet("fon1", "Telefon", "izbrisano vnaprej", sid=UUID1)
    assert _ids(sp, "fon1") == []
    assert not sp.prejmi_izbris("fon1", "klepet-ni-uuid") and not sp.storitev.db.execute(
        "SELECT 1 FROM klepet_vnaprej WHERE id=?", ("chat:klepet-ni-uuid",)).fetchone()


def test_zapisov_vnaprej_najvec_500(sp):
    for _ in range(I.VNAPREJ_NAJVEC + 20):
        sp.prejmi_izbris("fon1", str(uuid.uuid4()))
    assert sp.storitev.db.execute("SELECT COUNT(*) FROM klepet_vnaprej").fetchone()[0] == I.VNAPREJ_NAJVEC


# ---------------------------------------------------------------------------- Safeer Link (Control)

class _Povezava:
    tece = True

    def __init__(self):
        self.poslano = []

    def poslji(self, s):
        self.poslano.append(s)
        return True


def _link():
    from core.safeer_link import SafeerLink
    link = SafeerLink.__new__(SafeerLink)
    link.povezava = _Povezava()
    link._klepet_cakajoci = {}
    link.naprave = []
    link.naprave_vse = []
    return link


def test_link_zahteva_za_izbris_kot_android():
    link = _link()
    link.naprave_vse = [{"id": "n-1-os", "naprava": "n-1", "zmoznosti": ["chat", "chat.delete"]}]
    assert link.poslji_izbris("n-1", UUID1, cakaj=0.01) == "potek"            # sredisce v testu ne potrdi
    z = link.povezava.poslano[-1]
    assert z["type"] == "chat.send" and z["target"] == "n-1" and I.je_uuid(z["id"])
    assert z["payload"]["delete"] == UUID1 and z["payload"]["text"] == I.BESEDILO_IZBRISA


def test_link_naprava_brez_zmoznosti_ne_dobi_zahteve():
    link = _link()
    link.naprave_vse = [{"id": "n-2-control", "naprava": "n-2", "zmoznosti": ["chat"]}]
    assert link.poslji_izbris("n-2", UUID1) == "ne_zna"
    assert link.povezava.poslano == [], "starejsa naprava bi zahtevo pokazala kot sporocilo s kosem"


def test_link_skupni_id_je_id_sporocila():
    link = _link()
    link.poslji_klepet("n-1", "zivjo", "2026-10-25T07:00:00+00:00", cakaj=0.01, ident=UUID1)
    assert link.povezava.poslano[-1]["id"] == UUID1 and "delete" not in link.povezava.poslano[-1]["payload"]


def test_control_javi_chat_delete():
    besedilo = Path(__file__).resolve().parent.parent.joinpath("core", "safeer_link.py").read_text(encoding="utf-8")
    assert '["chat", "chat.delete"] if self.control' in besedilo


def test_control_vrne_skupni_id_in_izbrise():
    besedilo = Path(__file__).resolve().parent.parent.joinpath("safeer_control.py").read_text(encoding="utf-8")
    assert '<method name="KlepetIzbrisi">' in besedilo and '"id": ident' in besedilo


def test_besedila_v_vseh_jezikih():
    js = Path(__file__).resolve().parent.parent.joinpath("assets", "os", "besedila.js").read_text(encoding="utf-8")
    kljuci = ("sporIzbrisiPriMeni", "sporIzbrisiNaVseh", "sporIzbrisiPotrdi", "sporIzbrisano", "sporIzbrisanoNaVseh",
              "sporIzbrisanoCaka", "dejanjeIzbrisiPogovor", "dejanjePogovorIzbrisan")
    for jezik in ("sl", "en", "de", "es", "fr", "it"):
        vrstica = next(v for v in js.splitlines() if v.startswith("Object.assign(BESEDILA_OS.%s, {\"sporIzbrisiPriMeni\"" % jezik))
        slovar = json.loads(vrstica[vrstica.index("{"):vrstica.rindex("}") + 1])
        assert set(kljuci) <= set(slovar), jezik
