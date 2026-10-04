"""Iskalni kljuc: ista pravila v Pythonu in v vmesniku (tabela posebnih crk je na treh mestih, tu jih primerjamo)."""
import json
import re
from pathlib import Path

from core import iskalni_kljuc, os_datoteke, os_iskalnik, os_zapiski

KOREN = Path(__file__).resolve().parents[1]


def test_kljuc_brez_sumnikov_in_naglasov():
    assert iskalni_kljuc.kljuc("Ščit ŽIVJO") == "scit zivjo"
    assert iskalni_kljuc.kljuc("Đorđe Łódź Søren Straße Æsop Œuvre") == "dorde lodz soren strasse aesop oeuvre"
    assert iskalni_kljuc.kljuc("café RÉSUMÉ") == "cafe resume"
    assert iskalni_kljuc.kljuc("navaden ascii 123") == "navaden ascii 123"
    assert iskalni_kljuc.kljuc("") == ""


def test_en_kljuc_za_datoteke_zapiske_in_iskalnik():
    assert os_datoteke.kljuc_imena is iskalni_kljuc.kljuc
    assert os_iskalnik.kljuc is iskalni_kljuc.kljuc
    assert os_zapiski.kljuc_iskanja is iskalni_kljuc.kljuc


def test_vmesnik_ima_isto_tabelo_posebnih_crk():
    for ime in ("delovna.js", "iskanje.js"):
        js = (KOREN / "assets" / "os" / ime).read_text(encoding="utf-8")
        tabela = re.search(r"var POSEBNE_CRKE = \{([^}]*)\};", js)
        assert tabela, ime
        pari = {json.loads('"%s"' % crka): zamenjava
                for crka, zamenjava in re.findall(r'"(\\u[0-9a-f]{4})": "([a-z]+)"', tabela.group(1))}
        assert pari == iskalni_kljuc.POSEBNE_CRKE, ime
        # Razred znakov v zamenjavi mora nasteti iste crke.
        razred = re.search(r"\.replace\(/\[((?:\\u[0-9a-f]{4})+)\]/g, function \(z\) \{ return POSEBNE_CRKE\[z\]; \}\)", js)
        assert razred, ime
        crke = {json.loads('"%s"' % c) for c in re.findall(r"\\u[0-9a-f]{4}", razred.group(1))}
        assert crke == set(iskalni_kljuc.POSEBNE_CRKE), ime
