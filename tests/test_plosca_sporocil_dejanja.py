"""Plosca sporocil v pultu: dejanja v vrstici (lastnik, 17. 10. 2026: »uporabnik mora ze tu imeti moznost, da oznaci
sporocilo za prebrano in ga po zelji izbrise ali oznaci kot pomembno«). Isti klic kot okno Sporocila, samo dejanja,
ki jih kanal zmore, vsa besedila v sestih jezikih."""
import os
import re
import shutil
import subprocess

import pytest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(KOREN, "assets", "os", "sporocila-plosca.js")
HTML = os.path.join(KOREN, "assets", "os", "sporocila-plosca.html")


def _beri(pot):
    with open(pot, encoding="utf-8") as f:
        return f.read()


def test_dejanja_prek_istega_klica_kot_okno():
    js = _beri(JS)
    assert '"sporocilaDejanje"' in js
    for d in ('"prebrano"', '"neprebrano"', '"zvezdica"', '"brez_zvezdice"', '"izbrisi"'):
        assert d in js, d
    # gumb samo, ce ga kanal zmore
    assert "kanal || {}).dejanja" in js


def test_imena_dejanj_ustrezajo_kanalu_email():
    with open(os.path.join(KOREN, "core", "sporocila", "email.py"), encoding="utf-8") as f:
        email = f.read()
    for d in ("prebrano", "neprebrano", "zvezdica", "brez_zvezdice", "izbrisi"):
        assert '"%s"' % d in email


def test_besedila_v_vseh_jezikih():
    js = _beri(JS)
    for jezik in ("sl", "en", "de", "es", "fr", "it"):
        blok = re.search(r"\n    %s: \{(.*?)\}" % jezik, js, re.S).group(1)
        for k in ("prebrano", "neprebrano", "zvezdica", "brezZvezdice", "izbrisi", "izbrisano", "razveljavi", "napaka"):
            assert re.search(r"\b%s: \"" % k, blok), (jezik, k)


def test_obvestilo_za_razveljavi_v_html():
    assert 'id="obvestilo"' in _beri(HTML)


@pytest.mark.skipif(not shutil.which("node"), reason="node ni namescen")
def test_sintaksa():
    subprocess.run(["node", "--check", JS], check=True)
