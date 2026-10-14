"""Zascita v stopnjah, izjeme po straneh, dovoljenja po straneh, brisanje podatkov (Firefox, 14. 10. 2026)."""
import os

import gi
gi.require_version("Gtk", "4.0")

from core import dovoljenja_strani as dv
from core import zascita

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class C(dict):
    def set(self, k, v):
        self[k] = v


def test_stopnje_in_po_meri():
    c = C()
    assert zascita.raven(c) == "obicajna"
    zascita.nastavi_raven(c, "stroga")
    assert zascita.raven(c) == "stroga" and c["zascita_itp"] and c["zascita_brez_webrtc"]
    c["gpc_dnt_enabled"] = False
    assert zascita.raven(c) == "po_meri"
    zascita.nastavi_raven(c, "obicajna")
    assert zascita.raven(c) == "obicajna"


def test_izjeme_po_straneh():
    c = C()
    assert zascita.preklopi_izjemo(c, "https://www.primer.si/a") is False
    assert zascita.je_izjema(c, "https://www.primer.si/b") and not zascita.je_izjema(c, "https://primer.si/")
    assert "*://www.primer.si/*" in zascita.vzorci_izjem(c)
    assert zascita.preklopi_izjemo(c, "https://www.primer.si/c") is True and not zascita.izjeme(c)


def test_dovoljenja_zapomnjena_in_privzeta():
    c = C()
    assert dv.odlocitev(c, "https://meet.primer.si/", ["kamera", "mikrofon"]) == "vprasaj"
    dv.zapomni(c, "https://meet.primer.si/", ["kamera", "mikrofon"], "dovoli")
    assert dv.odlocitev(c, "https://meet.primer.si/x", ["kamera"]) == "dovoli"
    assert dv.odlocitev(c, "https://drugo.si/", ["kamera"]) == "vprasaj"
    dv.nastavi_privzeto(c, "lokacija", "zavrni")
    assert dv.odlocitev(c, "https://drugo.si/", ["lokacija"]) == "zavrni"
    c["permissions_policy"] = "allow"
    assert dv.privzeto(c, "obvestila") == "dovoli"         # stara nastavitev ostane veljavna
    dv.pozabi_stran(c, "meet.primer.si")
    assert dv.seznam(c) == []
    assert dv.samodejno_predvajanje(c) == "brez_zvoka"


def test_vrste_zahteve_webkit6():
    gi.require_version("WebKit", "6.0")
    from gi.repository import WebKit
    assert dv.vrste_zahteve(object(), WebKit) == []


def test_besedila():
    for mod in (zascita, dv):
        k = set(mod.BESEDILA["sl"])
        assert all(set(b) == k for b in mod.BESEDILA.values())


def test_splet_ima_nastavitve_firefox():
    s = open(os.path.join(KOREN, "core", "os_splet.py"), encoding="utf-8").read()
    for niz in ("zascita.nastavi_raven", "_pokazi_scit", "_dovoljenja_strani", "def izbrisi(", "pocisti_ob_izhodu",
                "website_policies=self._pravila_strani()", "always_ask_download_dir", "set_itp_enabled"):
        assert niz in s, niz
    b = open(os.path.join(KOREN, "safeer_brskalnik.py"), encoding="utf-8").read()
    assert "pocisti_ob_izhodu" in b
