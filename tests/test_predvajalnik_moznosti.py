"""Nastavitve predvajanja kot v Kodiju (lastnik, 14. 10. 2026): zvocni posnetki, zamik zvoka in podnapisov,
podnapisi iz datoteke in s spleta (OpenSubtitles brez racuna), izenacevalnik.

Brez omrezja in brez zvocne naprave: playbin je lazen, odgovor dodatka OpenSubtitles je posnet
(tests/fixtures/opensubtitles_v3_serija.json, 14. 10. 2026). Zivi preizkus s pravim GStreamerjem 1.24 (dva zvocna
toka, av-offset -> ts-offset zvocnega ponora, text-offset -> subtitle-ts-offset) je opisan v sporocilu commita.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from core import podnapisi as pn
from core import podnapisi_splet as ps
from core import predvajalnik_moznosti as pm
from core.os_predvajalnik import Predvajalnik

VZOREC = Path(__file__).parent / "fixtures" / "opensubtitles_v3_serija.json"


class Oznake:
    def __init__(self, **vrednosti):
        self.v = vrednosti

    def get_string(self, ime):
        return (ime in self.v, self.v.get(ime))


class Element:
    """playbin z dvema zvocnima tokoma (slv AC3 5.1, eng AAC stereo)."""

    def __init__(self):
        self.lastnosti = {"flags": 0x17, "n-text": 0, "current-text": -1, "n-audio": 2, "current-audio": 0}
        self.toki = [Oznake(**{"language-code": "sl", "audio-codec": "AC-3 (ATSC A/52)"}),
                     Oznake(**{"language-code": "en", "audio-codec": "MPEG-4 AAC", "title": "Komentar"})]
        self.kanali = [6, 2]
        self.vodilo = SimpleNamespace(add_signal_watch=lambda: None, remove_signal_watch=lambda: None,
                                      connect=lambda *_: None)

    def get_bus(self):
        return self.vodilo

    def set_state(self, _stanje):
        return "ok"

    def set_property(self, ime, vrednost):
        self.lastnosti[ime] = vrednost

    def get_property(self, ime):
        return self.lastnosti.get(ime)

    def emit(self, signal, i):
        if signal == "get-audio-tags":
            return self.toki[i]
        if signal == "get-audio-pad":
            struktura = SimpleNamespace(get_int=lambda _k, n=self.kanali[i]: (True, n))
            zmoznosti = SimpleNamespace(get_size=lambda: 1, get_structure=lambda _i: struktura)
            return SimpleNamespace(get_current_caps=lambda: zmoznosti)
        return None

    def query_duration(self, _f):
        return True, 600_000_000_000

    def query_position(self, _f):
        return True, 30_000_000_000

    def seek_simple(self, *_a):
        return True


def _predvajalnik():
    element = Element()
    gst = SimpleNamespace(ElementFactory=SimpleNamespace(make=lambda *_: element),
                          State=SimpleNamespace(NULL="null", PLAYING="playing", PAUSED="paused", READY="ready"),
                          StateChangeReturn=SimpleNamespace(FAILURE="failure"),
                          Format=SimpleNamespace(TIME="time"), SECOND=1_000_000_000, CLOCK_TIME_NONE=2**64 - 1,
                          SeekFlags=SimpleNamespace(FLUSH=1, KEY_UNIT=2),
                          MessageType=SimpleNamespace(EOS="eos", ERROR="error", ASYNC_DONE="async_done"))
    p = Predvajalnik(gst)
    p.nit = False
    return p, element


class ImenaZvocnihTokov(unittest.TestCase):
    def test_ime_iz_oznak(self):
        self.assertEqual(pm.ime_zvocnega_toka(0, "slv", "AC-3 (ATSC A/52)", 6), "Slovenščina · AC3 5.1")
        self.assertEqual(pm.ime_zvocnega_toka(1, "en", "MPEG-4 AAC", 2, "Komentar"), "Angleščina · Komentar · AAC Stereo")
        self.assertEqual(pm.ime_zvocnega_toka(0, "de", "E-AC-3", 8, jezik_vmesnika="en"), "German · E-AC3 7.1")
        self.assertEqual(pm.ime_zvocnega_toka(0, "en", "DTS", 6, "English", jezik_vmesnika="en"), "English · DTS 5.1",
                         "naslov, ki ponovi jezik, izpustimo")
        self.assertEqual(pm.ime_zvocnega_toka(2, "", "", 0, privzeto="Zvok {n}"), "Zvok 3")
        self.assertEqual(pm.ime_zvocnega_toka(0, "und", "Opus", 1), "Opus Mono")

    def test_kodeki_in_kanali(self):
        for opis, kratko in (("E-AC-3 audio", "E-AC3"), ("AC-3 (ATSC A/52)", "AC3"), ("MPEG-1 Layer 3 (MP3)", "MP3"),
                             ("Free Lossless Audio Codec (FLAC)", "FLAC"), ("Dolby TrueHD", "TrueHD"), ("", "")):
            self.assertEqual(pm.kratek_kodek(opis), kratko)
        self.assertEqual([pm.opis_kanalov(n) for n in (1, 2, 6, 8, 4, 0)], ["Mono", "Stereo", "5.1", "7.1", "4 ch", ""])

    def test_iso_oznake(self):
        self.assertEqual([pn.iso1(k) for k in ("slv", "eng", "ger", "pob", "slo", "sl", "en-US", "pt_BR", "und", "")],
                         ["sl", "en", "de", "pt", "sk", "sl", "en", "pt", "", ""])


class IzbiraJezikaZvoka(unittest.TestCase):
    def test_izberi_po_jeziku(self):
        self.assertEqual(pm.izberi_po_jeziku(["sl", "en"], ["en"]), 1)
        self.assertEqual(pm.izberi_po_jeziku(["slv", "eng"], ["sl"]), 0)
        self.assertEqual(pm.izberi_po_jeziku(["de", "en"], ["sl", "en"]), 1)
        self.assertEqual(pm.izberi_po_jeziku(["de", "fr"], ["sl"]), -1)
        self.assertEqual(pm.izberi_po_jeziku(["de"], [""]), -1)

    def test_predvajalnik_izbere_zapomnjeni_jezik_po_nalaganju(self):
        p, e = _predvajalnik()
        p.moznosti["zvok_jezik"] = "en"
        p.dodaj("https://example.test/film.mkv", vrsta="video")
        p._sporocilo(None, SimpleNamespace(type="async_done"))
        self.assertEqual(e.lastnosti["current-audio"], 1)
        e.lastnosti["current-audio"] = 0          # uporabnik/datoteka po skoku: ASYNC_DONE ne izbira znova
        p._sporocilo(None, SimpleNamespace(type="async_done"))
        self.assertEqual(e.lastnosti["current-audio"], 0)

    def test_izbira_si_zapomni_jezik_in_imena(self):
        p, e = _predvajalnik()
        shranjeno = []
        p.shrani_moznosti = shranjeno.append
        p.dodaj("https://example.test/film.mkv", vrsta="video")
        toki = p.zvocni_toki("sl", "Zvok {n}")
        self.assertEqual([m["ime"] for m in toki["moznosti"]], ["Slovenščina · AC3 5.1", "Angleščina · Komentar · AAC Stereo"])
        self.assertEqual(p.naslednji_zvok(), 1)
        self.assertEqual(e.lastnosti["current-audio"], 1)
        self.assertEqual(shranjeno[-1]["zvok_jezik"], "en")
        self.assertFalse(p.izberi_zvok(5))

    def test_zamenjava_podnapisov_ohrani_zvok(self):
        p, e = _predvajalnik()
        p.dodaj("https://example.test/film.mkv", vrsta="video")
        p._sporocilo(None, SimpleNamespace(type="async_done"))
        p.izberi_zvok(1)
        p._znova_zazeni(-1)
        e.lastnosti["current-audio"] = 0           # playbin po READY zacne s privzetim tokom
        p._sporocilo(None, SimpleNamespace(type="async_done"))
        self.assertEqual(e.lastnosti["current-audio"], 1)


class Zamik(unittest.TestCase):
    def test_koraki_in_meje(self):
        self.assertEqual(pm.premakni_zamik(0, 50, pm.MEJA_ZVOK_MS), 50)
        self.assertEqual(pm.premakni_zamik(50, -100, pm.MEJA_ZVOK_MS), -50)
        self.assertEqual(pm.premakni_zamik(9_980, 100, pm.MEJA_ZVOK_MS), 10_000)
        self.assertEqual(pm.premakni_zamik(-59_990, -100, pm.MEJA_PODNAPISI_MS), -60_000)
        self.assertEqual(pm.premakni_zamik(33, 0, pm.MEJA_ZVOK_MS), 50, "vrednost ostane na mrezi 50 ms")
        self.assertEqual(pm.premakni_zamik("x", 50, pm.MEJA_ZVOK_MS), 0, "neveljavna vrednost = brez zamika")

    def test_besedilo(self):
        self.assertEqual([pm.besedilo_zamika(v) for v in (0, 150, -50, 1250, -2000)],
                         ["0 ms", "+150 ms", "−50 ms", "+1,25 s", "−2 s"])

    def test_predznak_lastnosti_playbina(self):
        # Zvok kasneje (K) = slika prej: av-offset negativen (playsink da +ts-offset zvocnemu ponoru - izmerjeno).
        self.assertEqual(pm.av_offset_ns(150), -150_000_000)
        self.assertEqual(pm.text_offset_ns(-50), -50_000_000)

    def test_predvajalnik_zamik_velja_za_posnetek(self):
        p, e = _predvajalnik()
        p.dodaj("https://example.test/a.mkv", vrsta="video")
        p.premakni_zamik("zvok", 50)
        p.premakni_zamik("zvok", 100)
        p.premakni_zamik("podnapisi", -50)
        self.assertEqual((p.zamik_zvoka, e.lastnosti["av-offset"]), (150, -150_000_000))
        self.assertEqual((p.zamik_podnapisov, e.lastnosti["text-offset"]), (-50, -50_000_000))
        p.dodaj("https://example.test/b.mkv", predvajaj=True, vrsta="video")
        self.assertEqual((p.zamik_zvoka, p.zamik_podnapisov, e.lastnosti["av-offset"], e.lastnosti["text-offset"]),
                         (0, 0, 0, 0))
        self.assertEqual(p.nastavi_zamik("zvok", 99_999), pm.MEJA_ZVOK_MS)
        self.assertEqual(p.nastavi_zamik("neznano", 50), 0)


class KodiranjePodnapisov(unittest.TestCase):
    def test_zaznava(self):
        self.assertEqual(pn.zaznaj_kodiranje("Čas je za žgance, šef.".encode("cp1250")), "cp1250")
        self.assertEqual(pn.zaznaj_kodiranje("Šola".encode("cp1250")), "cp1250")
        self.assertEqual(pn.zaznaj_kodiranje("čevapčiči".encode("cp1250"), "sl"), "cp1250", "samo č: odloci jezik")
        self.assertEqual(pn.zaznaj_kodiranje("Voilà, très bien".encode("cp1252")), "cp1252")
        self.assertEqual(pn.zaznaj_kodiranje("très".encode("cp1252"), "fr"), "cp1252")
        self.assertEqual(pn.zaznaj_kodiranje("Привет, как дела?".encode("cp1251")), "cp1251")
        self.assertEqual(pn.zaznaj_kodiranje("Čas".encode("utf-8")), "utf-8")
        self.assertEqual(pn.zaznaj_kodiranje("Čas".encode("utf-8-sig")), "utf-8-sig")
        self.assertEqual(pn.zaznaj_kodiranje("Čas".encode("utf-16")), "utf-16")

    def test_pocisti_po_imenu(self):
        srt = "1\r\n00:00:01,000 --> 00:00:02,000\r\nčevapčiči\r\n".encode("cp1250")
        self.assertIn("čevapčiči", pn.pocisti("Film.sl.srt", srt)[1])
        self.assertIn("Grüße, à bientôt", pn.pocisti("x.ass", "Grüße, à bientôt".encode("cp1252"))[1])


class SpletniPodnapisi(unittest.TestCase):
    def test_id_vnosa(self):
        self.assertEqual(ps.id_vnosa({"stremio": {"tip": "series", "id": "tt0903747:1:2"}}), "series/tt0903747:1:2")
        self.assertEqual(ps.id_vnosa({"url": "stremio:https://x|movie|tt0133093"}), "movie/tt0133093")
        self.assertEqual(ps.id_vnosa({"imdb_id": "tt0903747", "sezona": 2, "epizoda": 3, "vrsta": "serija"}),
                         "series/tt0903747:2:3")
        self.assertEqual(ps.id_vnosa({"imdb_id": "tt0133093", "vrsta": "film"}), "movie/tt0133093")
        self.assertEqual(ps.id_vnosa({"imdb_id": "tt0903747", "vrsta": "serija"}), "", "serija brez epizode")
        self.assertEqual(ps.id_vnosa({"stremio": {"tip": "series", "id": "tt0903747"}}), "")
        self.assertEqual(ps.id_vnosa({"naslov": "Domaci posnetek"}), "")
        self.assertEqual(ps.id_vnosa(None), "")

    def test_naslov_iskanja(self):
        self.assertEqual(ps.naslov_iskanja("movie/tt0133093"),
                         "https://opensubtitles-v3.strem.io/subtitles/movie/tt0133093.json")
        self.assertEqual(ps.naslov_iskanja("series/tt0903747:1:1"),
                         "https://opensubtitles-v3.strem.io/subtitles/series/tt0903747:1:1.json")
        for slab in ("", "movie/../x", "tv/tt0133093", "movie/tt0133093?x=1", "movie/tt12"):
            self.assertEqual(ps.naslov_iskanja(slab), "", slab)

    def test_razclenitev_posnetega_odgovora(self):
        izid = ps.razcleni(VZOREC.read_bytes(), ["sl", "en"])
        self.assertEqual([r["jezik"] for r in izid], ["sl", "en", "en", "de", "hr", "mk", "pt", "pt"])
        self.assertTrue(all(r["url"].startswith("https://subs5.strem.io/") for r in izid))
        self.assertEqual(len({r["url"] for r in izid}), len(izid), "brez podvojenih")
        self.assertEqual([r["oznaka"] for r in izid if r["jezik"] == "pt"], ["", "BR"])
        self.assertTrue(izid[0]["ime"].endswith(".srt"))
        self.assertEqual([j for j, _ in ps.skupine(izid)], ["sl", "en", "de", "hr", "mk", "pt"])
        self.assertEqual(ps.razcleni(b"ni json", ["sl"]), [])
        self.assertEqual(ps.razcleni({"subtitles": "x"}), [])

    def test_iskanje_in_prenos_brez_omrezja(self):
        klici = []

        class Odgovor:
            def __init__(self, podatki):
                self.podatki = podatki

            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

            def read(self, n=-1):
                return self.podatki[:n] if n >= 0 else self.podatki

        def odpri(url):
            klici.append(url)
            return Odgovor(VZOREC.read_bytes() if url.endswith(".json") else "1\r\n00:00:01,000 --> 00:00:02,000\r\nHi\r\n".encode())
        izid = ps.poisci("series/tt0903747:1:1", ["sl"], odpri=odpri)
        self.assertEqual(klici, ["https://opensubtitles-v3.strem.io/subtitles/series/tt0903747:1:1.json"])
        with tempfile.TemporaryDirectory() as mapa:
            pot = ps.prenesi(izid[0], mapa, odpri=odpri)
            self.assertTrue(pot.startswith(mapa) and pot.endswith(".sl.srt"))
            self.assertIn("Hi", Path(pot).read_text(encoding="utf-8"))
            ps.prenesi(izid[0], mapa, odpri=odpri)
            self.assertEqual(len(klici), 2, "ze prenesen podnapis beremo iz predpomnilnika")
        with self.assertRaises(ValueError):
            ps.prenesi({"url": "http://x/y.srt"}, "/nikamor")
        self.assertEqual(ps.poisci("neveljavno", odpri=odpri), [])

    def test_jeziki_uporabnika(self):
        self.assertEqual(ps.jeziki_uporabnika("", "sl", "sl"), ["sl", "en"])
        self.assertEqual(ps.jeziki_uporabnika("de", "sl", "en"), ["de", "sl", "en"])

    def test_dodan_podnapis_se_izbere(self):
        p, e = _predvajalnik()
        p.dodaj("https://example.test/film.mkv", vrsta="video")
        with tempfile.NamedTemporaryFile(suffix=".sl.srt") as d:
            uri = Path(d.name).as_uri()
            self.assertTrue(p.dodaj_podnapis(uri, "film.sl.srt", "sl"))
            self.assertTrue(p.dodaj_podnapis(uri, "film.sl.srt", "sl"), "isti podnapis ne dvakrat")
            self.assertEqual(len(p.trenutna.podnapisi), 1)
            self.assertEqual(p.podnapisi()["izbran"], "z:0")
            self.assertEqual(e.lastnosti["suburi"], uri)
        self.assertFalse(p.dodaj_podnapis("ftp://x/y.srt", "y.srt"))


class Izenacevalnik(unittest.TestCase):
    def test_prednastavitve(self):
        self.assertEqual(list(pm.IZBIRE_IZENACEVALNIKA), ["ravno", "bas", "glas", "klasika", "rock", "elektronska", "po_meri"])
        for ime, vrednosti in pm.PREDNASTAVITVE.items():
            self.assertEqual(len(vrednosti), 10, ime)
            self.assertTrue(all(-12 <= v <= 6 for v in vrednosti), ime)
        self.assertEqual(pm.ojacitve("ravno"), [0.0] * 10)
        self.assertEqual(pm.ojacitve("bas")[:3], [6.0, 5.0, 4.0])
        self.assertEqual(pm.ojacitve("neznano"), [0.0] * 10)
        self.assertEqual(pm.ojacitve("po_meri", [30, -30, "x", float("nan")]), [12.0, -12.0] + [0.0] * 8)

    def test_predojacitev_prepreci_pokanje(self):
        self.assertAlmostEqual(pm.predojacitev(pm.ojacitve("ravno")), 1.0)
        self.assertAlmostEqual(pm.predojacitev(pm.ojacitve("bas")), 10 ** (-6 / 20))
        self.assertAlmostEqual(pm.predojacitev(pm.ojacitve("klasika")), 1.0, msg="samo znizanja: brez predojacitve")

    def test_shramba(self):
        with tempfile.TemporaryDirectory() as mapa:
            pot = os.path.join(mapa, "p.json")
            self.assertEqual(pm.nalozi(pot), pm.privzete())
            pm.shrani({"zvok_jezik": "sl", "izenacevalnik": "po_meri", "po_meri": [3] * 10}, pot)
            self.assertEqual(pm.nalozi(pot), {"zvok_jezik": "sl", "izenacevalnik": "po_meri", "po_meri": [3.0] * 10})
            with open(pot, "w") as d:
                json.dump({"izenacevalnik": "<script>", "po_meri": "x", "zvok_jezik": 5}, d)
            self.assertEqual(pm.nalozi(pot), pm.privzete())

    def test_brez_elementa_ni_izenacevalnika(self):
        p, _e = _predvajalnik()        # lazni Gst nima parse_bin_from_description: meni izenacevalnika skrije
        self.assertIsNone(p.izenacevalnik)
        self.assertEqual(p.nastavi_izenacevalnik("bas", shrani=False)[0], 6.0)


class Okno(unittest.TestCase):
    """Okno predvajalnika: tipke, gumbi in besedila (brez zagona GTK)."""

    def test_besedila_v_vseh_jezikih(self):
        from core import os_media_besedila as mb
        for kljuc in ["zvok", "zvocni_posnetek", "zamik_zvoka", "zamik_podnapisov", "izenacevalnik",
                      "podnapisi_datoteka", "podnapisi_splet"] + ["eq_" + i for i in pm.IZBIRE_IZENACEVALNIKA]:
            for jezik in mb.JEZIKI:
                self.assertIn(kljuc, mb.BESEDILA[jezik], (kljuc, jezik))

    def test_tipke_in_moduli(self):
        vir = (Path(__file__).parent.parent / "safeer_os.py").read_text(encoding="utf-8")
        for del_ in ('tipka in ("Menu", "AudioCycleTrack")', '("j", "J", "k", "K", "g", "G", "h", "H")',
                     'tipka == "Subtitle"', "if self._medijsko_okence_odprto():"):
            self.assertIn(del_, vir)
        tovor = (Path(__file__).parent.parent / "packaging" / "install_os_payload.sh").read_text(encoding="utf-8")
        self.assertIn(" predvajalnik_moznosti ", tovor)
        self.assertIn(" podnapisi_splet ", tovor)


if __name__ == "__main__":
    unittest.main()
