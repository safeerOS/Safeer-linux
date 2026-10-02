"""Logika vdelanega razdelka Splet, ki ne potrebuje zaslona."""

import json
import os

from core.os_splet import BESEDILA, JEZIKI, besedila, je_domaca_stran, razcleni_sporocilo


KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_vseh_sest_jezikov_ima_vsa_besedila():
    assert tuple(BESEDILA) == JEZIKI
    assert all(set(BESEDILA["sl"]) == set(BESEDILA[jezik]) for jezik in JEZIKI)
    assert [BESEDILA[j]["nov"] for j in JEZIKI] == [
        "Nov zavihek", "New tab", "Neuer Tab", "Nueva pestaña", "Nouvel onglet", "Nuova scheda"
    ]
    assert besedila("xx") == BESEDILA["en"]


def test_most_sprejme_samo_navigacijo_http_in_dodajanje_bliznjice():
    assert razcleni_sporocilo({"action": "navigate", "url": "example.com"}) == {
        "action": "navigate", "url": "https://example.com"
    }
    assert razcleni_sporocilo(json.dumps({"action": "open_sidebar", "service": "add_portal"})) == {
        "action": "open_sidebar", "service": "add_portal"
    }
    assert razcleni_sporocilo({"action": "navigate", "url": "file:///etc/passwd"}) is None
    assert razcleni_sporocilo({"action": "open_sidebar", "service": "settings"}) is None
    assert razcleni_sporocilo("ni json") is None
    # Odstranjevanje bliznjic z zacetne strani (tudi vgrajenih) in obnova privzetih.
    assert razcleni_sporocilo({"action": "remove_portal", "url": "https://www.reddit.com"})["action"] == "remove_portal"
    assert razcleni_sporocilo({"action": "remove_portal", "url": "file:///etc/passwd"}) is None
    assert razcleni_sporocilo({"action": "reset_portals"}) == {"action": "reset_portals"}
    from core.os_splet import kljuc_bliznjice
    assert kljuc_bliznjice("https://www.Reddit.com/") == "reddit.com"
    assert kljuc_bliznjice("http://365.rtvslo.si") == "365.rtvslo.si"


def test_domaca_stran_je_samo_skupni_splet_html():
    prava = "file://" + os.path.join(KOREN, "ui", "splet.html")
    assert je_domaca_stran(prava, KOREN)
    assert not je_domaca_stran("file:///tmp/ui/splet.html", KOREN)
    assert not je_domaca_stran("https://example.com/splet.html", KOREN)


def test_safeer_os_ne_zaganja_zunanjega_brskalnika():
    with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as datoteka:
        vir = datoteka.read()
    zacetek = vir.index("    def _splet(")
    konec = vir.index("    def _medij(", zacetek)
    telo = vir[zacetek:konec]
    assert "subprocess.Popen" not in telo
    assert "safeer-browser" not in telo
    assert "self._pokazi_spletni_nacin()" in telo


def test_sirino_stranske_izmeri_pred_razredom_in_uporabi_dataset():
    with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as datoteka:
        vir = datoteka.read()
    zacetek = vir.index("    def _pokazi_spletni_nacin(")
    konec = vir.index("    def _skrij_spletni_nacin(", zacetek)
    telo = vir[zacetek:konec]
    assert telo.index("getBoundingClientRect().width") < telo.index("classList.add('nacin-splet')")
    assert "dataset.stranska||0" in telo
