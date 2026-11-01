import pytest
import json
from unittest.mock import MagicMock
from core.os_splet import VdelaniSplet, ZETON_MOSTU

class MockJSValue:
    def __init__(self, val):
        self.val = val
    def to_json(self, indent):
        return json.dumps(self.val)

class MockPogled:
    def get_uri(self):
        return "file:///tmp/koren/ui/splet.html"

class MockSplet:
    def __init__(self):
        self.koren = "/tmp/koren"
        self.odpri_klici = []
    
    def odpri(self, url, pogled):
        self.odpri_klici.append(url)
        
    _sporocilo = VdelaniSplet._sporocilo

def test_splet_zeton_zavrne_napacnega():
    splet = MockSplet()
    pogled = MockPogled()
    
    # Brez zetona
    sporocilo = MockJSValue({"action": "navigate", "url": "https://example.com"})
    splet._sporocilo(pogled, sporocilo)
    assert len(splet.odpri_klici) == 0, "Sporocilo brez zetona bi moralo biti zavrnjeno"
    
    # Napacen zeton
    sporocilo = MockJSValue({"action": "navigate", "url": "https://example.com", "t": "napacen_zeton"})
    splet._sporocilo(pogled, sporocilo)
    assert len(splet.odpri_klici) == 0, "Sporocilo z napacnim zetonom bi moralo biti zavrnjeno"
    
    # Pravilen zeton
    sporocilo = MockJSValue({"action": "navigate", "url": "https://example.com", "t": ZETON_MOSTU})
    splet._sporocilo(pogled, sporocilo)
    assert len(splet.odpri_klici) == 1, "Sporocilo s pravim zetonom bi moralo biti sprejeto"
    assert splet.odpri_klici[0] == "https://example.com"


def test_splet_zeton_niz_iz_poslji():
    """SafeerSplet.poslji poslje JSON.stringify(sporocilo) - niz, ne predmet (pregled 1. 11. 2026)."""
    splet = MockSplet()
    sporocilo = MockJSValue(json.dumps({"action": "navigate", "url": "https://example.com", "t": ZETON_MOSTU}))
    splet._sporocilo(MockPogled(), sporocilo)
    assert splet.odpri_klici == ["https://example.com"]
    napacen = MockJSValue(json.dumps({"action": "navigate", "url": "https://example.com", "t": "x"}))
    splet._sporocilo(MockPogled(), napacen)
    assert splet.odpri_klici == ["https://example.com"]


# --- Pregled 1. 11. 2026: most z zetonom samo za mapo vmesnika ---

from core.os_splet import je_uri_vmesnika, razcleni_sporocilo, vzorci_mostu


class _PogledZ:
    def __init__(self, uri):
        self.uri = uri

    def get_uri(self):
        return self.uri


@pytest.mark.parametrize("uri", [
    "file:///tmp/drugo.html",
    "https://example.com",
    "https://example.com/tmp/koren/ui/splet.html",
    "file:///tmp/koren/uix/splet.html",
    "file:///tmp/koren/ui/../drugo.html",
])
def test_splet_zeton_zavrne_tujo_stran(uri):
    """Pravi zeton, a stran ni iz mape vmesnika: sporocilo mora biti zavrnjeno."""
    splet = MockSplet()
    sporocilo = MockJSValue(json.dumps({"action": "navigate", "url": "https://example.com", "t": ZETON_MOSTU}))
    splet._sporocilo(_PogledZ(uri), sporocilo)
    assert splet.odpri_klici == []


def test_vzorci_mostu_samo_mapa_vmesnika(tmp_path):
    koren = tmp_path / "s presledkom"
    (koren / "ui").mkdir(parents=True)
    vzorci = vzorci_mostu(str(koren))
    assert "file:///*" not in vzorci
    assert vzorci and all(v.endswith("/ui/*") for v in vzorci)
    assert all("%20" in v and " " not in v for v in vzorci)
    uri = (koren / "ui" / "splet.html").as_uri()
    assert je_uri_vmesnika(uri, str(koren))
    assert not je_uri_vmesnika((koren / "drugo.html").as_uri(), str(koren))
    assert not je_uri_vmesnika((koren / "ui").as_uri(), str(koren))   # brez koncne posevnice ni predpona
    assert not je_uri_vmesnika("", str(koren))


def test_razcleni_sporocilo_dict_in_niz():
    pricakovano = {"action": "navigate", "url": "https://example.com"}
    assert razcleni_sporocilo({"action": "navigate", "url": "https://example.com"}) == pricakovano
    assert razcleni_sporocilo(json.dumps({"action": "navigate", "url": "https://example.com"})) == pricakovano
    assert razcleni_sporocilo(b'{"action": "reset_portals"}') == {"action": "reset_portals"}
    for slabo in ("", "ni json", "[1, 2]", "null", None, 5, b"\xff"):
        assert razcleni_sporocilo(slabo) is None


def test_zeton_ne_gre_naprej(monkeypatch):
    """Kljuc t se po preverjanju odstrani, preden gre sporocilo naprej."""
    import core.os_splet as os_splet
    prejeto = []
    izvirni = os_splet.razcleni_sporocilo
    monkeypatch.setattr(os_splet, "razcleni_sporocilo", lambda v: prejeto.append(dict(v)) or izvirni(v))
    splet = MockSplet()
    splet._sporocilo(MockPogled(), MockJSValue({"action": "navigate", "url": "https://example.com", "t": ZETON_MOSTU}))
    assert prejeto and "t" not in prejeto[0]
