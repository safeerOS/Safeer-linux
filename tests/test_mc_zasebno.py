"""Kategorija »Zasebno« v Medijskem centru (lastnik, 17. 10. 2026).

Vsebina zasebnih dodatkov (manifest behaviorHints.adult) se pokaze samo, ce uporabnik vklopi »Zasebno«, in samo v svoji
kategoriji. Privzeto izklopljeno: zasebne vsebine ni v katalogu, iskanju, predlogih, na policah, med viri in v tokovih.
Preizkus brez omrezja (katalogi in manifesti dodatkov so nadomesceni).
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import media_servers, os_katalog, os_media

JAVNI = "https://javni.primer"
ZASEBNI = "https://zasebni.primer"
NEZNAN = "https://neznan.primer"
STREZNIKI = [
    {"id": "streznik-javni", "vrsta": "streznik", "ponudnik": "stremio", "ime": "Javni dodatek", "url": JAVNI},
    # Zapis brez oznake »zaseben« (dodan pred to izdajo): odloci manifest.
    {"id": "streznik-zasebni", "vrsta": "streznik", "ponudnik": "stremio", "ime": "Zasebni dodatek", "url": ZASEBNI},
]
MANIFESTI = {JAVNI: {"id": "javni", "name": "Javni"},
             ZASEBNI: {"id": "zasebni", "name": "Zasebni", "behaviorHints": {"adult": True}}}


def _vrstica(koren, ime, ident, naslov, vrsta="film"):
    return {"id": "stremio:%s:movie:%s" % (ime, ident), "naslov": naslov, "vrsta": vrsta,
            "url": "stremio:%s|movie|%s" % (koren, ident), "imdb_id": ident if ident.startswith("tt") else "",
            "vir": ime, "stremio": {"koren": koren, "tip": "movie", "id": ident}, "slika": "", "opis": "", "leto": 0}


VRSTICE = {
    JAVNI: [_vrstica(JAVNI, "Javni dodatek", "tt0000001", "Javni film"),
            _vrstica(JAVNI, "Javni dodatek", "tt0000002", "Skupni film")],
    # Isti film (isti IMDb) tudi v zasebnem dodatku: na javni kartici zasebna razlicica izpade.
    ZASEBNI: [_vrstica(ZASEBNI, "Zasebni dodatek", "zz-1", "Zasebni naslov"),
              _vrstica(ZASEBNI, "Zasebni dodatek", "tt0000002", "Skupni film")],
}


def _katalog_dodatka(_ponudnik, url, _streznik, _skrivnost, query=""):
    vrstice = VRSTICE.get(media_servers._stremio_koren(url), [])
    return [dict(v) for v in vrstice if not query or media_servers.ujema_iskanje(v, query)]


def _manifest(url, sveze=False):
    koren = media_servers._stremio_koren(url)
    if koren not in MANIFESTI:
        raise OSError("ni omrezja")
    return MANIFESTI[koren]


class _BrezVirov:
    def get(self, *a, **k):
        return []


class Osnova(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        (Path(self.mapa.name) / "media.json").write_text(json.dumps({"viri": [], "osebni_strezniki": STREZNIKI}),
                                                         encoding="utf-8")
        for ime, nadomestek in (("catalog", _katalog_dodatka), ("stremio_manifest", _manifest)):
            p = mock.patch.object(media_servers, ime, nadomestek)
            p.start()
            self.addCleanup(p.stop)
        self.mc = self.nov_mc()

    def nov_mc(self):
        mc = os_media.MediaCenter(self.mapa.name, roots=[], secret_decryptor=lambda v: "")
        mc._zakoniti_viri = _BrezVirov()
        mc._cinemeta_items = lambda *a, **k: []
        return mc

    @staticmethod
    def naslovi(rezultat):
        return sorted(x["naslov"] for x in rezultat["vnosi"])

    @staticmethod
    def vsi_naslovi_tokov(rezultat):
        return [r.get("url") for x in rezultat["vnosi"] for r in ([x] + list(x.get("razlicice") or []))]


class Zasebno(Osnova):
    def test_privzeto_izklopljeno_nikjer(self):
        self.assertFalse(self.mc.zasebno)
        for vrsta in ("vse", "film"):
            izid = self.mc.catalog("", vrsta)
            self.assertEqual(self.naslovi(izid), ["Javni film", "Skupni film"])
            self.assertFalse(any(ZASEBNI in str(u) for u in self.vsi_naslovi_tokov(izid)))
        # Iskanje
        self.assertEqual(self.naslovi(self.mc.catalog("zasebni", "vse")), [])
        self.assertEqual(self.naslovi(self.mc.catalog("skupni", "vse")), ["Skupni film"])
        self.assertFalse(any(ZASEBNI in str(u) for u in self.vsi_naslovi_tokov(self.mc.catalog("skupni", "vse"))))
        # Kategorija Zasebno je prazna, dokler ni vklopljena
        self.assertEqual(self.mc.catalog("", "zasebno")["vnosi"], [])
        self.assertEqual(self.mc.catalog_hitro("", "zasebno")["vnosi"], [])
        # Viri (filter »Viri« in nastavitve) in tokovi
        self.assertEqual([v["id"] for v in self.mc.vidni_viri()], ["streznik-javni"])
        self.assertEqual([s["id"] for s in self.mc._stremio_strezniki()], ["streznik-javni"])

    def test_vklopljeno_samo_v_svoji_kategoriji(self):
        self.mc.zasebno = True
        self.assertEqual(self.naslovi(self.mc.catalog("", "zasebno")), ["Skupni film", "Zasebni naslov"])
        self.assertEqual(self.naslovi(self.mc.catalog("zasebni", "zasebno")), ["Zasebni naslov"])
        # Ne pomesano med ostale kategorije in iskanje
        self.assertEqual(self.naslovi(self.mc.catalog("", "film")), ["Javni film", "Skupni film"])
        self.assertFalse(any(ZASEBNI in str(u) for u in self.vsi_naslovi_tokov(self.mc.catalog("", "vse"))))
        self.assertEqual(self.naslovi(self.mc.catalog("zasebni", "vse")), [])
        self.assertEqual(sorted(v["id"] for v in self.mc.vidni_viri()), ["streznik-javni", "streznik-zasebni"])

    def test_predpomnilnik_in_predlogi(self):
        """Pogled, shranjen pred to izdajo (z zasebno vsebino), se ne pokaze; predlogi iskanja je nikoli ne ponudijo."""
        self.mc.zasebno = True
        zasebni = self.mc.catalog_hitro("", "zasebno")
        self.assertTrue(zasebni["vnosi"])
        star = {"vnosi": [_vrstica(ZASEBNI, "Zasebni dodatek", "zz-1", "Zasebni naslov"),
                          _vrstica(JAVNI, "Javni dodatek", "tt0000001", "Javni film")], "skupaj": 2}
        self.mc._zapomni_katalog(self.mc.kljuc_kataloga("", "film"), star)
        self.assertEqual(self.naslovi(self.mc.catalog_hitro("", "film")), ["Javni film"])
        self.assertEqual(self.mc.isci_v_predpomnilniku("zasebni"), [])
        self.assertEqual([x["naslov"] for x in self.mc.isci_v_predpomnilniku("javni")], ["Javni film"])
        # Izklop: shranjeni pogledi kategorije Zasebno izginejo
        self.mc.zasebno = False
        self.mc.pozabi_zasebno_v_predpomnilniku()
        kljuci = list(self.mc._nalozi_predpomnilnik()["katalog"])
        self.assertFalse(any(json.loads(k)[2] == "zasebno" for k in kljuci))
        self.assertEqual(self.mc.catalog_hitro("", "zasebno")["vnosi"], [])

    def test_tokovi_izklopljenega_ne_vprasajo_zasebnega(self):
        vprasani = []
        with mock.patch.object(media_servers, "stremio_tokovi", lambda k, t, i: vprasani.append(k) or []):
            self.mc._stremio_tokovi_vseh(JAVNI, "movie", "tt0000002")
            self.assertEqual(vprasani, [JAVNI])
            vprasani.clear()
            self.mc._stremio_tokovi_vseh(ZASEBNI, "movie", "zz-1")
            self.assertEqual(vprasani, [JAVNI])
            vprasani.clear()
            self.mc.zasebno = True
            self.mc._stremio_tokovi_vseh(JAVNI, "movie", "tt0000002")
            self.assertEqual(sorted(vprasani), [JAVNI, ZASEBNI])

    def test_neznan_dodatek_velja_kot_zaseben(self):
        """Manifesta ni bilo mogoce prebrati: dodatek velja kot zaseben (kot pri Linku) in ga ne sprasujemo ob vsakem klicu."""
        streznik = {"id": "streznik-neznan", "ponudnik": "stremio", "ime": "Neznan", "url": NEZNAN}
        klici = []
        with mock.patch.object(media_servers, "stremio_manifest", lambda u, sveze=False: klici.append(u) or _manifest(u)):
            self.assertTrue(self.mc.zaseben_streznik(streznik))
            self.assertTrue(self.mc.zaseben_streznik(streznik))
        self.assertEqual(len(klici), 1)
        self.assertFalse(self.mc.zaseben_streznik({"ponudnik": "jellyfin", "url": NEZNAN}))


class Most(Osnova):
    """core/os_katalog.py: stikalo v nastavitvah Medijskega centra, viri, police."""

    def setUp(self):
        super().setUp()
        self.k = os_katalog.Katalog(self.mapa.name, dogodek=lambda *a: None, v_glavni=lambda f: f(),
                                    predvajaj=lambda *a: True, vdelano=lambda *a: True, youtube=lambda *a: True,
                                    youtube_ukaz=lambda *a: True)
        self.k._mc = self.mc

    def test_stikalo_in_viri(self):
        self.assertEqual(self.k.izvedi("mediaZasebno", []), {"vklopljeno": False, "skriti": 1})
        self.assertEqual([v["id"] for v in self.k.izvedi("mediaViri", [])], ["streznik-javni"])
        self.assertEqual(self.k.izvedi("mediaZasebno", [True]), {"vklopljeno": True, "skriti": 1})
        self.assertTrue(json.loads((Path(self.mapa.name) / "nastavitve.json").read_text())["media_zasebno"])
        self.assertEqual(len(self.k.izvedi("mediaViri", [])), 2)
        # Nov zagon prebere nastavitev
        k2 = os_katalog.Katalog(self.mapa.name, dogodek=lambda *a: None, v_glavni=lambda f: f(),
                                predvajaj=lambda *a: True, vdelano=lambda *a: True, youtube=lambda *a: True,
                                youtube_ukaz=lambda *a: True)
        with mock.patch.object(os_media.MediaCenter, "_default_roots", staticmethod(lambda: [])):
            self.assertTrue(k2.mc.zasebno)
        self.assertEqual(self.k.izvedi("mediaZasebno", [False])["vklopljeno"], False)
        self.assertFalse(self.mc.zasebno)

    def test_police_brez_zasebnega(self):
        je = self.k._je_zaseben_opis()
        self.assertTrue(je({"id": "stremio:streznik-zasebni:movie:zz-1", "naslov": "x"}))
        self.assertTrue(je({"id": "abc", "vir": "Zasebni dodatek"}))
        self.assertFalse(je({"id": "stremio:streznik-javni:movie:tt0000001", "vir": "Javni dodatek"}))
        # Zasebno ne gre med priljubljene
        self.assertFalse(self.k.izvedi("mediaPriljubljena", ["tmdb:film:1", True,
                                                             {"id": "stremio:streznik-zasebni:movie:zz-1", "naslov": "x"}]))


if __name__ == "__main__":
    unittest.main()


class Kartice(Osnova):
    def test_javna_kartica_z_zasebno_glavno_razlicico_ostane(self):
        """Film TMDB, ki ga ponujata javni in zasebni dodatek (zasebni je bil glavna razlicica): ostane javni dodatek."""
        kartica = {"id": "x", "naslov": "Film", "url": "stremio:%s|movie|tt9" % ZASEBNI,
                   "stremio": {"koren": ZASEBNI, "tip": "movie", "id": "tt9"}, "vir": "Zasebni dodatek",
                   "razlicice": [{"url": "stremio:%s|movie|tt9" % ZASEBNI, "vir": "Zasebni dodatek"},
                                 {"url": "stremio:%s|movie|tt9" % JAVNI, "vir": "Javni dodatek"},
                                 {"url": "https://vgradni.primer/tt9", "vir": "Splet"}]}
        samo_zasebna = {"id": "y", "naslov": "Z", "url": "stremio:%s|movie|zz" % ZASEBNI,
                        "stremio": {"koren": ZASEBNI, "tip": "movie", "id": "zz"},
                        "razlicice": [{"url": "stremio:%s|movie|zz" % ZASEBNI}]}
        izid = self.mc.brez_zasebnih([kartica, samo_zasebna])
        self.assertEqual(len(izid), 1)
        self.assertEqual(izid[0]["stremio"]["koren"], JAVNI)
        self.assertEqual(izid[0]["vir"], "Javni dodatek")
        self.assertEqual(izid[0]["stevilo_razlicic"], 2)
        self.assertFalse(self.mc.je_zaseben_vnos(izid[0]))


class Hitrost(Osnova):
    def test_branje_manifesta_ne_zadrzi_drugih_dodatkov(self):
        """Zasebnost dodatka, ki je se ne poznamo, se prebere v niti njegovega streznika, ne pred vsemi."""
        import time as _cas

        def pocasen(url, sveze=False):
            if media_servers._stremio_koren(url) == NEZNAN:
                _cas.sleep(1.5)
                raise OSError("rok")
            return _manifest(url)
        strezniki = STREZNIKI + [{"id": "streznik-neznan", "vrsta": "streznik", "ponudnik": "stremio", "ime": "Neznan",
                                  "url": NEZNAN}]
        self.mc._load = lambda: {"viri": [], "osebni_strezniki": strezniki}
        self.mc.STREZNIKI_ROK_S = 0.5
        with mock.patch.object(media_servers, "stremio_manifest", pocasen):
            t0 = _cas.monotonic()
            naslovi = sorted(x["naslov"] for x in self.mc._personal_items(""))
            self.assertLess(_cas.monotonic() - t0, 1.2)
        self.assertEqual(naslovi, ["Javni film", "Skupni film"])


class TestDodatekZaOdrasleBrezOznake(unittest.TestCase):
    """Preizkus 17. 10. 2026: JAV Nexus se v manifestu ne oznaci z behaviorHints.adult, njegovi filmi so bili v Filmih.
    Ime, opis in imena katalogov dodatka zato tudi stejejo; naslovi filmov ne."""

    def test_manifest_brez_oznake(self):
        from core import media_servers as ms
        jav = {"id": "community.discovery.ftv", "name": "JAV Nexus", "behaviorHints": {"configurable": True},
               "description": "Japanese adult films (JAV) for viewers 18+.",
               "catalogs": [{"type": "movie", "name": "JAV Top Rated"}]}
        self.assertTrue(ms.stremio_je_zaseben(jav))
        self.assertTrue(ms.stremio_je_zaseben({"name": "Cool", "catalogs": [{"name": "XXX Latest"}]}))
        for javni in ({"name": "Cinemeta", "description": "The official addon for movie and series catalogs"},
                      {"name": "Anime Kitsu", "catalogs": [{"name": "Kitsu Trending"}]},
                      {"name": "Adult Swim Shows"}, {"name": "Javelin TV"}, {"name": "Sex Education fan club"}):
            self.assertFalse(ms.stremio_je_zaseben(javni), javni)

    def test_star_zapis_ni_zaseben_a_ime_pove(self):
        from core import os_media
        import tempfile
        mc = os_media.MediaCenter(tempfile.mkdtemp())
        self.assertTrue(mc._stremio_zaseben_znano({"ponudnik": "stremio", "ime": "JAV Nexus", "zaseben": False,
                                                    "url": "https://app.jnexus.site/manifest.json"}))
        self.assertFalse(mc._stremio_zaseben_znano({"ponudnik": "stremio", "ime": "HdHub", "zaseben": False,
                                                     "url": "https://hdhub.example/manifest.json"}))
