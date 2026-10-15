"""Prijava osebnih streznikov (zeton, geslo) nikoli v seznamih, policah in na drugih napravah (pregled 14. 10. 2026:
»Shrani kot seznam« je pisal `api_key` Jellyfina in `u/t/s` Navidroma v seznami.json, lists.get pa jih je dal napravam
v Linku). Naslov se shrani brez prijave, Medijski center jo doda ob predvajanju s streznika."""
import hashlib
import json
import tempfile
import threading
import time
import unittest
import urllib.parse
from pathlib import Path
from unittest import mock

from core import link_seznami, media_servers, os_katalog as K, os_knjiznica as KN, os_media, os_police, viri_sink
from core import zakoniti_viri as ZV

JF = "streznik-aaaaaaaaaaaaaaaa"
ND = "streznik-bbbbbbbbbbbbbbbb"
STREZNIKI = [
    {"id": JF, "ponudnik": "jellyfin", "ime": "JF", "url": "https://jf.test:8920", "uporabnik": "ana", "secret_enc": "enc:ZETON-JF"},
    {"id": ND, "ponudnik": "navidrome", "ime": "ND", "url": "https://nd.test", "uporabnik": "ana", "secret_enc": "enc:geslo-nd"},
    {"id": "streznik-cccccccccccccccc", "ponudnik": "kodi", "ime": "Kodi", "url": "http://192.168.1.5:8080",
     "uporabnik": "kodi", "secret_enc": "enc:kodi-geslo"},
]
# Jellyfin 12 sprejme le `ApiKey` (api_key je stara prijava, privzeto izklopljena); starejsi shranjeni naslovi imajo api_key.
JF_TOK = "https://jf.test:8920/Audio/abc/stream?static=true&ApiKey=ZETON-JF"
JF_SLIKA = "https://jf.test:8920/Items/abc/Images/Primary?maxHeight=240&ApiKey=ZETON-JF"
JF_TOK_STAR = "https://jf.test:8920/Audio/abc/stream?static=true&api_key=ZETON-JF"
JF_SLIKA_STAR = "https://jf.test:8920/Items/abc/Images/Primary?maxHeight=240&api_key=ZETON-JF"
ND_TOK = "https://nd.test/rest/stream.view?u=ana&t=0123abcd&s=sol1&v=1.16.1&c=SafeerOS&f=json&id=7"
SKRIVNO = ("ZETON-JF", "t=0123abcd", "s=sol1", "u=ana", "geslo")


def _brez_skrivnosti(test, besedilo):
    for s in SKRIVNO:
        test.assertNotIn(s, besedilo)


class CistiNaslovi(unittest.TestCase):
    def test_brez_prijave(self):
        self.assertEqual(viri_sink.brez_prijave(JF_TOK), "https://jf.test:8920/Audio/abc/stream?static=true")
        self.assertEqual(viri_sink.brez_prijave(JF_TOK_STAR), "https://jf.test:8920/Audio/abc/stream?static=true")
        self.assertEqual(viri_sink.brez_prijave(ND_TOK), "https://nd.test/rest/stream.view?v=1.16.1&c=SafeerOS&f=json&id=7")
        self.assertEqual(viri_sink.brez_prijave("https://plex.test/library/parts/1/file.mp3?X-Plex-Token=abc"),
                         "https://plex.test/library/parts/1/file.mp3")
        self.assertEqual(viri_sink.brez_prijave("https://fw.test/api/v1/listen/x/?token=abc&upload=1"),
                         "https://fw.test/api/v1/listen/x/?upload=1")
        self.assertEqual(viri_sink.brez_prijave("http://kodi:p%40ss@192.168.1.5:8080/vfs/a.mp3"), "http://192.168.1.5:8080/vfs/a.mp3")
        self.assertEqual(viri_sink.brez_prijave("https://x.test/a?ACCESS_TOKEN=1&b=2"), "https://x.test/a?b=2")
        # Kratka imena Subsonic (t, s, u, p) samo na poti Subsonic: drugje (cas v posnetku) ostanejo.
        for ostane in ("https://www.youtube.com/watch?v=abc&t=30", "https://cdn.test/p.mp3?s=1&u=2", "file:///m/a.mp3", ""):
            self.assertEqual(viri_sink.brez_prijave(ostane), ostane)
            self.assertFalse(viri_sink.ima_prijavo(ostane))
        self.assertTrue(viri_sink.ima_prijavo(JF_TOK) and viri_sink.ima_prijavo(ND_TOK))
        cista = viri_sink.cista_skladba({"naslov": "N", "url": JF_TOK, "slika": JF_SLIKA})
        self.assertEqual((cista["prijava"], cista["url"]), (True, "https://jf.test:8920/Audio/abc/stream?static=true"))
        self.assertNotIn("prijava", viri_sink.cista_skladba({"naslov": "N", "url": "https://radio.test/tok.mp3"}))

    def test_prijava_ob_predvajanju_samo_za_svoj_streznik(self):
        cist = viri_sink.brez_prijave(ND_TOK)
        url = media_servers.s_prijavo(cist, STREZNIKI[1], "geslo-nd")
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))
        self.assertEqual((q["u"], q["id"], q["v"]), ("ana", "7", "1.16.1"))
        self.assertEqual(q["t"], hashlib.md5(("geslo-nd" + q["s"]).encode()).hexdigest())
        self.assertEqual(media_servers.s_prijavo(viri_sink.brez_prijave(JF_TOK), STREZNIKI[0], "ZETON-JF"), JF_TOK)
        self.assertEqual(media_servers.s_prijavo("http://192.168.1.5:8080/vfs/a.mp3", STREZNIKI[2], "kodi-geslo"),
                         "http://kodi:kodi-geslo@192.168.1.5:8080/vfs/a.mp3")
        # Drug gostitelj, drugacna vrata ali protokol: prijava ne gre nikamor drugam.
        for tuj in ("https://zlobni.test/Audio/abc/stream", "https://jf.test/Audio/abc/stream", "http://jf.test:8920/x"):
            self.assertEqual(media_servers.s_prijavo(tuj, STREZNIKI[0], "ZETON-JF"), tuj)
        self.assertEqual(media_servers.streznik_iz_id("server:%s:abc" % JF), JF)
        self.assertEqual(media_servers.streznik_iz_id("navidrome:%s:7" % ND), ND)
        self.assertEqual(media_servers.streznik_iz_id("tmdb:film:1"), "")


class SezamiMedijskegaCentra(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.koren = Path(self.mapa.name)
        (self.koren / "media.json").write_text(json.dumps({"viri": [], "osebni_strezniki": STREZNIKI}), encoding="utf-8")
        self.mc = self._mc()

    def _mc(self):
        return os_media.MediaCenter(str(self.koren), roots=[], secret_encryptor=lambda s: "enc:" + s,
                                    secret_decryptor=lambda e: e[4:])

    def _disk(self):
        return (self.koren / "seznami.json").read_text(encoding="utf-8")

    def test_shrani_kot_seznam_brez_prijave_in_predvajanje_s_prijavo(self):
        izid = self.mc.shrani_seznam("Moj", [
            {"naslov": "Pesem", "izvajalec": "I", "slika": JF_SLIKA, "sekund": 200, "url": JF_TOK, "streznik": JF},
            {"naslov": "Druga", "izvajalec": "I", "slika": "", "sekund": 100, "url": ND_TOK},
            {"naslov": "Radio", "izvajalec": "", "slika": "", "sekund": 0, "url": "https://radio.test/tok.mp3"}])
        self.assertTrue(izid["ok"])
        _brez_skrivnosti(self, self._disk())
        shranjen = json.loads(self._disk())[0]["skladbe"]
        self.assertEqual((shranjen[0]["streznik"], shranjen[0]["prijava"], shranjen[1]["prijava"]), (JF, True, True))
        self.assertNotIn("prijava", shranjen[2])
        # Druga naprava v Linku: ne iz Medijskega centra ne iz Safeer Controla (bere datoteko sam).
        _brez_skrivnosti(self, json.dumps(self.mc.seznami_izvoz({"ime": "Moj"})))
        _brez_skrivnosti(self, json.dumps(link_seznami.izvoz({"ime": "Moj"}, str(self.koren))))
        # Na tej napravi: prikaz in predvajanje s prijavo (iz zbirke skrivnosti).
        vnosi = self.mc.seznam("Moj")["vnosi"]
        self.assertEqual((vnosi[0]["url"], vnosi[0]["slika"]), (JF_TOK, JF_SLIKA))
        self.assertEqual(self.mc.seznami()[0]["slika"], JF_SLIKA)
        nd = self.mc.resolve(vnosi[1]["id"])
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(nd["url"]).query))
        self.assertEqual(q["t"], hashlib.md5(("geslo-nd" + q["s"]).encode()).hexdigest())
        self.assertEqual(self.mc.resolve(vnosi[2]["id"])["url"], "https://radio.test/tok.mp3")
        _brez_skrivnosti(self, self._disk())

    def test_dodaj_na_seznam_iz_kataloga(self):
        ident = "server:%s:abc" % JF
        self.mc._dynamic_items[ident] = {"id": ident, "naslov": "Pesem", "izvajalec": "I", "vrsta": "glasba", "url": JF_TOK,
                                         "slika": JF_SLIKA}
        self.assertTrue(self.mc.dodaj_na_seznam("Moj", ident)["ok"])
        _brez_skrivnosti(self, self._disk())
        self.assertEqual(json.loads(self._disk())[0]["skladbe"][0]["streznik"], JF)
        vnos = self.mc.seznam("Moj")["vnosi"][0]
        self.assertTrue(self.mc.dodaj_na_seznam("Drugi", vnos["id"])["ok"])       # s seznama na seznam: prijava ostane zunaj
        _brez_skrivnosti(self, self._disk())
        self.assertEqual(self.mc.seznam("Drugi")["vnosi"][0]["url"], JF_TOK)

    def test_enkratna_selitev_starih_seznamov_in_obrambni_izvoz(self):
        star = [{"ime": "Star", "vir": "", "cas": 1, "skladbe": [{"naslov": "Pesem", "url": JF_TOK_STAR, "slika": JF_SLIKA_STAR},
                                                              {"naslov": "Druga", "url": ND_TOK}]}]
        (self.koren / "seznami.json").write_text(json.dumps(star), encoding="utf-8")
        # Safeer Control odgovarja tudi, ce Safeer OS datoteke se ni ocistil.
        _brez_skrivnosti(self, json.dumps(link_seznami.izvoz({"ime": "Star"}, str(self.koren))))
        self.assertEqual(link_seznami.izvoz({"ime": "Star"}, str(self.koren))["skladbe"][0]["url"],
                         "https://jf.test:8920/Audio/abc/stream?static=true")
        mc = self._mc()
        self.assertEqual(mc.seznami()[0]["stevilo"], 2)
        _brez_skrivnosti(self, self._disk())
        # Predvajanje dela tudi po selitvi - z novim parametrom ApiKey (Jellyfin 12), ne s starim api_key.
        self.assertEqual(mc.seznam("Star")["vnosi"][0]["url"], JF_TOK)

    def test_prevzem_z_druge_naprave_brez_prijave(self):
        self.mc._seznami_pisi([{"ime": "Tuj", "vir": "", "cas": 5, "skladbe": [{"naslov": "X", "url": ND_TOK}]}])
        _brez_skrivnosti(self, self._disk())


class Police(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.koren = Path(self.mapa.name)

    def _disk(self):
        return "".join(p.read_text(encoding="utf-8") for p in self.koren.glob("*.json"))

    def test_predvajanja_in_priljubljene_brez_prijave(self):
        p = os_police.Police(self.koren)
        p.zapomni("id:server:%s:abc" % JF, {"id": "server:%s:abc" % JF, "naslov": "Pesem", "vrsta": "glasba", "url": JF_TOK,
                                           "slika": JF_SLIKA})
        p.stej("id:navidrome:%s:7" % ND, {"id": "navidrome:%s:7" % ND, "naslov": "Druga", "vrsta": "glasba", "url": ND_TOK})
        p.nastavi_priljubljeno("id:x", True, {"naslov": "X", "vrsta": "glasba", "url": ND_TOK})
        _brez_skrivnosti(self, self._disk())
        self.assertEqual(p.opis("id:server:%s:abc" % JF)["url"], "https://jf.test:8920/Audio/abc/stream?static=true")

    def test_enkratna_selitev(self):
        (self.koren / "predvajanja.json").write_text(json.dumps(
            {"id:a": {"n": 3, "t": 1, "m": {"id": "a", "naslov": "A", "vrsta": "glasba", "url": JF_TOK, "slika": JF_SLIKA}},
             "id:b": {"n": 1, "t": 2, "m": {"id": "b", "naslov": "B", "vrsta": "radio", "url": "https://radio.test/t"}}}),
            encoding="utf-8")
        (self.koren / "priljubljene.json").write_text(json.dumps(
            {"v": [{"k": "id:c", "t": 1, "m": {"naslov": "C", "vrsta": "glasba", "url": ND_TOK}}]}), encoding="utf-8")
        p = os_police.Police(self.koren)
        self.assertEqual(p.predvajanja()["id:a"]["n"], 3)
        self.assertEqual(p.predvajanja()["id:b"]["m"]["url"], "https://radio.test/t")
        self.assertEqual(len(p.priljubljene()), 1)
        _brez_skrivnosti(self, self._disk())


class MostKataloga(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.koren = Path(self.mapa.name) / "media"
        self.koren.mkdir()
        (self.koren / "media.json").write_text(json.dumps({"viri": [], "osebni_strezniki": STREZNIKI}), encoding="utf-8")
        self.predvajano = []
        self.k = K.Katalog(str(self.koren), dogodek=lambda v, p: None, v_glavni=lambda delo: delo(),
                           predvajaj=lambda *a: self.predvajano.append(a) or True, vdelano=lambda u: True,
                           youtube=lambda u, n: True, youtube_ukaz=lambda u: True,
                           lokalna=KN.Knjiznica(Path(self.mapa.name) / "m.sqlite3"))
        self.k._mc = os_media.MediaCenter(str(self.koren), roots=[], secret_encryptor=lambda s: "enc:" + s,
                                          secret_decryptor=lambda e: e[4:])

    def test_samodejni_shrani_hrani_streznik_ne_prijave_in_ne_povozi_bogatejsega_vnosa(self):
        ident = "server:%s:abc" % JF
        bogat = {"id": ident, "naslov": "Pesem", "izvajalec": "I", "vrsta": "glasba", "url": JF_TOK, "slika": JF_SLIKA,
                 "glave": {"Referer": "https://jf.test:8920/"}}
        self.k.mc._dynamic_items[ident] = bogat
        self.k._samodejni.update(cas=time.time(), seznami=[{"id": "sam:odkrij", "vrsta": "odkrij", "ime": "", "skladbe": [
            {"id": ident, "naslov": "Pesem", "izvajalec": "I", "slika": JF_SLIKA, "url": JF_TOK, "pot": "", "sekund": 200}]}])
        vnosi = self.k.izvedi("mediaSamodejniSeznam", ["sam:odkrij"])["vnosi"]
        self.assertEqual(vnosi[0]["id"], ident)
        self.assertIs(self.k.mc._dynamic_items[ident], bogat)                  # glave in referer ostanejo
        self.assertTrue(self.k.izvedi("mediaSamodejniShrani", ["sam:odkrij", "Odkrij"])["ok"])
        disk = (self.koren / "seznami.json").read_text(encoding="utf-8")
        _brez_skrivnosti(self, disk)
        self.assertEqual(json.loads(disk)[0]["skladbe"][0]["streznik"], JF)

    def test_polica_skladbe_s_streznika_zaigra_s_prijavo(self):
        ident = "navidrome:%s:7" % ND
        self.k.police.stej("id:" + ident, {"id": ident, "naslov": "Druga", "vrsta": "glasba", "url": ND_TOK})
        _brez_skrivnosti(self, (self.koren / "predvajanja.json").read_text(encoding="utf-8"))
        self.k.mc.catalog = lambda *a, **k: {"vnosi": []}            # brez omrezja: vnosa ni vec v katalogu
        with mock.patch.object(K, "nacin_predvajanja", return_value="neposredno"):
            self.k.izvedi("mediaPolicaPredvajaj", ["id:" + ident])
        self.assertTrue(self.predvajano)
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.predvajano[-1][0]).query))
        self.assertEqual(q["t"], hashlib.md5(("geslo-nd" + q["s"]).encode()).hexdigest())

    def test_nastavitve_brez_izgubljenih_sprememb_med_nitmi(self):
        kljuci = ["vir:v%d" % i for i in range(24)]
        niti = [threading.Thread(target=self.k.izvedi, args=("mediaSkrij", [k, True])) for k in kljuci]
        niti.append(threading.Thread(target=self.k.izvedi, args=("mediaWatchCountry", ["DE"])))
        for n in niti:
            n.start()
        for n in niti:
            n.join()
        self.assertEqual(sorted(self.k.izvedi("mediaSkrito", [])), sorted(kljuci))
        self.assertEqual(self.k._drzava(), "DE")
        self.assertEqual([p.name for p in self.koren.glob("*.tmp")], [])


class LogotipiTv(unittest.TestCase):
    def setUp(self):
        self.addCleanup(ZV._LOGOTIPI_V_TEKU.clear)
        self.addCleanup(ZV._LOGOTIPI_NEUSPELI.clear)
        ZV._LOGOTIPI_V_TEKU.clear()
        ZV._LOGOTIPI_NEUSPELI.clear()

    def test_neuspel_logotip_ni_vec_v_teku_in_ne_zavira_znova(self):
        from core import ikone_strani
        klici = []

        def pocasna(stran):
            klici.append(stran)
            time.sleep(0.05)
            return None
        with mock.patch.object(ikone_strani, "iz_predpomnilnika", return_value=""), \
                mock.patch.object(ikone_strani, "ikona_strani", side_effect=pocasna):
            ZV.pripravi_logotipe(cas=2.0)
            prvic = len(klici)
            self.assertGreater(prvic, 0)
            self.assertEqual(ZV._LOGOTIPI_V_TEKU, set())          # spodleteli ni vec »v teku«
            zacetek = time.monotonic()
            ZV.pripravi_logotipe(cas=2.0)                          # nedavno spodleteli: brez cakanja in brez novih klicev
            self.assertLess(time.monotonic() - zacetek, 0.04)
            self.assertEqual(len(klici), prvic)
            # Po LOGOTIP_ZNOVA_S poskusimo znova.
            for k in list(ZV._LOGOTIPI_NEUSPELI):
                ZV._LOGOTIPI_NEUSPELI[k] -= ZV.LOGOTIP_ZNOVA_S + 1
            ZV.pripravi_logotipe(cas=2.0)
            self.assertEqual(len(klici), 2 * prvic)
        self.assertEqual(ZV.LOGOTIP_ZNOVA_S, 600.0)


class GStreamerBrezPrijaveVGlavah(unittest.TestCase):
    def test_souphttpsrc_ne_dobi_glav_piskotkov_ali_gesla(self):
        """GStreamer-SA-2026-0080: souphttpsrc pred 1.28.7 ob preusmeritvi na drug izvor poslje naprej extra-headers,
        piskotke in user-id/user-pw. Runtime 50 ima GStreamer 1.26.11, zato prijava gre samo v naslov (ApiKey, u/t/s,
        uporabnik@): nov naslov iz Location je nima, libsoup pa prijavo iz naslova uporabi le za ta izvor
        (soup-auth-manager.c jo po uporabi odstrani). Teh lastnosti ne nastavljamo nikjer."""
        import re
        koren = Path(__file__).resolve().parent.parent
        datoteke = list((koren / "core").rglob("*.py")) + list(koren.glob("*.py"))
        vzorec = re.compile(r"[\"'](user-id|user-pw|proxy-id|proxy-pw|cookies)[\"']")
        najdeno = [str(p.relative_to(koren)) for p in datoteke if vzorec.search(p.read_text(encoding="utf-8", errors="replace"))]
        self.assertEqual(najdeno, [])
        # extra-headers samo za javne glave toka (Referer ...), ki jih zahteva dodatek - 15. 10. 2026: brez glave Referer
        # streznik toka vrne 429. V njih nikoli prijave ali piskotkov (te bi sle ob preusmeritvi naprej).
        vzorec = re.compile(r"[\"']extra-headers[\"']")
        najdeno = [str(p.relative_to(koren)) for p in datoteke if vzorec.search(p.read_text(encoding="utf-8", errors="replace"))]
        self.assertEqual(najdeno, ["core/os_predvajalnik.py"])
        from core import os_predvajalnik
        self.assertFalse({"authorization", "cookie", "proxy-authorization"} & os_predvajalnik._DOVOLJENE_GLAVE)
        self.assertEqual(os_predvajalnik.cisti_glave({"Authorization": "Bearer x", "Cookie": "a=b", "Referer": "https://r/"}),
                         (("Referer", "https://r/"),))


if __name__ == "__main__":
    unittest.main()
