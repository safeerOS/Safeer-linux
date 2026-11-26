"""Kljuc abuse.ch se vstavi samo v vgrajeni vir, ne v filter po meri (neodvisni pregled 12. 11. 2026, najdba S1)."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import os_scit  # noqa: E402

KLJUC = "k" * 40


def test_naslov_po_meri_s_kljucem_zavrnjen():
    assert os_scit.napaka_naslova("https://napadalec.example/{KLJUC}/seznam.txt") == "znaki"


def test_osvezi_ne_poslje_kljuca_filtru_po_meri():
    videni = []
    with tempfile.TemporaryDirectory() as m:
        s = os_scit.Seznami(m, prenesi_fn=lambda url, etag, cas=60.0: (videni.append(url), (404, b"", ""))[1],
                            kljuc_fn=lambda: KLJUC)
        s.viri = lambda: [("pm-x", "https://napadalec.example/{KLJUC}/s.txt", "oglasi")]
        s._osvezi()
    ip_url = [u for _o, u in os_scit.VIRI_IP]          # seznama naslovov IPv4 (blokada po IP odgovora) niso filter po meri
    assert [u for u in videni if u not in ip_url] == ["https://napadalec.example/{KLJUC}/s.txt"]
    assert not any(KLJUC in u for u in videni)
