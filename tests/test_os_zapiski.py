"""Zapiski in skupna stranska vrstica Safeer OS."""

import os
import re
import tempfile

from core.os_zapiski import Zapiski


KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_zapisek_shrani_in_prebere():
    with tempfile.TemporaryDirectory() as mapa:
        zapiski = Zapiski(os.path.join(mapa, "zapiski.json"))
        povzetek = zapiski.shrani("", "Načrt", "Poglej [@poročilo](safeer:datoteka:/tmp/porocilo.pdf).")
        zapisek = zapiski.dobi(povzetek["id"])

        assert zapisek["naslov"] == "Načrt"
        assert zapisek["besedilo"].startswith("Poglej")
        assert zapisek["omembe"] == [{
            "ime": "poročilo", "cilj": "safeer:datoteka:/tmp/porocilo.pdf", "vrsta": "datoteka"
        }]
        assert zapiski.zadnji() == povzetek["id"]


def test_zapiski_iskanje_po_naslovu_in_besedilu():
    with tempfile.TemporaryDirectory() as mapa:
        zapiski = Zapiski(os.path.join(mapa, "zapiski.json"))
        prvi = zapiski.shrani("", "Nakup", "mleko in kruh")
        drugi = zapiski.shrani("", "Sestanek", "Dogovor o projektu Orion")

        assert [z["id"] for z in zapiski.seznam("NAKUP")] == [prvi["id"]]
        assert [z["id"] for z in zapiski.seznam("orion")] == [drugi["id"]]


def test_zapisek_izbrisi():
    with tempfile.TemporaryDirectory() as mapa:
        zapiski = Zapiski(os.path.join(mapa, "zapiski.json"))
        ident = zapiski.shrani("", "Začasno", "")['id']

        assert zapiski.izbrisi(ident) is True
        assert zapiski.izbrisi(ident) is False
        assert zapiski.dobi(ident) is None
        assert zapiski.seznam() == []


def test_stranska_vrstica_ima_windowsov_vrstni_red():
    with open(os.path.join(KOREN, "assets", "os", "index.html"), encoding="utf-8") as datoteka:
        html = datoteka.read()
    meni = re.search(r'<nav id="meni">(.*?)</nav>', html, re.DOTALL).group(1)

    assert re.findall(r'data-razdelek="([^"]+)"', meni) == [
        "domov", "media", "naprave", "sporocila", "programi", "datoteke", "splet", "zapiski", "nastavitve"
    ]
