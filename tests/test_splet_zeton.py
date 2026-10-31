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
