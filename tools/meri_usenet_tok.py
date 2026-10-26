"""Meritev prometa lastnega pogona Usenet (korak 2): koliko gre z »Useneta« za 60 s ogleda.

Cela pot kot pri predvajanju: lazni streznik NNTP prek TLS (tests/test_usenet_nntp.LazniStreznik, clanki yEnc po
700 KiB, generirani sproti) -> usenet_nntp.Bazen -> usenet_bralnik.pripravi/Bralnik -> usenet_streznik (HTTP Range na
127.0.0.1) -> model predvajalnika: odprtje (glava 1 MiB, indeks na koncu 64 KiB, vsak s svojo zahtevo Range), nato EN
dolg GET od zacetka (ali od skoka), ki ga predvajalnik bere s hitrostjo ogleda + 20 s vnaprej (mpv --cache-secs=20).
Cas je simuliran (bajti ne zavisijo od ure), zato tek traja nekaj sekund.

»Pogledano« kot v prototipu 25. 10. 2026: kar je predvajalnik prebral (60 s + 20 s vnaprej + odprtje); prototip
(NzbDAV): 167-344 MiB pri ~50 MiB pogledanega = 3,4-6,9x. Cilj: najvec ~1,5x.

Zagon (iz korena repozitorija):  python tools/meri_usenet_tok.py
"""
import json
import os
import ssl
import sys
import tempfile
import time
import urllib.request
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:0] = [KOREN, os.path.join(KOREN, "tests")]

import test_usenet_nntp as TN  # noqa: E402
import usenet_gradnja as G  # noqa: E402
from core import usenet_bralnik as B, usenet_nntp as N, usenet_nzb as NZ, usenet_streznik as S  # noqa: E402

MiB = 1024 * 1024
#: (opis, velikost filma, Mbit/s, RAR: None ali (razlicica, velikost zvezka), skok) - velikosti in hitrosti kot filmi
#: CC v prototipu (Sintel 550 MiB 5,2; Tears of Steel 704 MiB 8,1; Big Buck Bunny 642 MiB 8,5).
TEKI = (("Sintel-podoben mkv, gola datoteka", 550 * MiB, 5.2, None, 0.0),
        ("Tears of Steel-podoben, RAR5 store 50 MiB zvezki", 704 * MiB, 8.1, (5, 50 * MiB), 0.0),
        ("Big Buck Bunny-podoben, RAR4 store 50 MiB zvezki, ogled od 50 %", 642 * MiB, 8.5, (4, 50 * MiB), 0.5))


def predvajalnik(url: str, velikost: int, mbit: float, od: int, sekund: float = 60.0, vnaprej_s: float = 20.0) -> int:
    """Model mpv prek HTTP: odprtje z dvema zahtevama Range, nato en GET od [od]; vrne prebrane bajte."""
    prebrano = 0
    for a, b in ((0, MiB - 1), (velikost - 2 * MiB, velikost - 2 * MiB + 65535)):
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Range": "bytes=%d-%d" % (a, b)}), timeout=60) as r:
            prebrano += len(r.read())
    na_s = mbit * 1e6 / 8
    cilj = min(velikost - od, int(na_s * (sekund + vnaprej_s)))
    with urllib.request.urlopen(urllib.request.Request(url, headers={"Range": "bytes=%d-" % od}), timeout=60) as r:
        while prebrano < cilj + MiB + 65536:
            kos = r.read(min(256 * 1024, cilj + MiB + 65536 - prebrano))
            if not kos:
                break
            prebrano += len(kos)
    return prebrano


def tek(mapa: str, opis: str, velikost: int, mbit: float, rar, skok: float, profil: str = "namizje") -> dict:
    film = G.Leno(velikost, 7)
    o = G.Objava()
    if rar:
        for i, z in enumerate(G.zvezki_leno(rar[0], "Film.mkv", film, rar[1])):
            o.dodaj("Film.part%02d.rar" % (i + 1), z)
    else:
        o.dodaj("Film.mkv", film)
    o.poslano = 0
    N._ZAVRNJENI.clear()
    if hasattr(N, "nastavi_shrambo_zapaha"):
        N.nastavi_shrambo_zapaha(os.path.join(mapa, "zapah"))
    with mock.patch.object(TN, "CLANKI", o):
        srv = TN.LazniStreznik(mapa)
        bazen = N.Bazen("127.0.0.1", srv.vrata, uporabnik=TN.UPORABNIK, geslo=TN.GESLO, povezav=8,
                        kontekst=ssl.create_default_context(cafile=os.path.join(mapa, "ca.pem")), rok=30.0)
        try:
            t0 = time.perf_counter()
            vir, priprava = B.pripravi(NZ.razcleni(o.nzb()), bazen.telo)
            t_prip = time.perf_counter() - t0
            br = B.Bralnik(bazen.telo, vir, B.PROFILI[profil])
            s = S.Streznik(br)
            pogledano = predvajalnik(s.url, vir.velikost, mbit, int(vir.velikost * skok))
            G.pocakaj_mir(br)
            postrezeno = br.postrezeno
            s.zapri()
            time.sleep(0.5)
            po_zaprtju = o.poslano
            time.sleep(1.0)
            z_omrezja = o.poslano
        finally:
            bazen.zapri()
            srv.ustavi()
    return {"opis": opis, "profil": profil, "film_mib": round(velikost / MiB), "mbit_s": mbit,
            "pogledano_mib": round(pogledano / MiB, 1), "postrezeno_http_mib": round(postrezeno / MiB, 1),
            "z_omrezja_mib": round(z_omrezja / MiB, 1), "od_tega_priprava_mib": round(priprava / MiB, 1),
            "razmerje": round(z_omrezja / pogledano, 2), "po_zaprtju_mib": round((z_omrezja - po_zaprtju) / MiB, 2),
            "priprava_s": round(t_prip, 2)}


def main() -> None:
    with tempfile.TemporaryDirectory() as mapa:
        TN.ustvari_potrdila(mapa)
        izidi = [tek(mapa, *t) for t in TEKI]
        izidi.append(tek(mapa, TEKI[0][0] + " (profil TV)", *TEKI[0][1:], profil="tv"))
    for i in izidi:
        print(json.dumps(i, ensure_ascii=False))


if __name__ == "__main__":
    main()
