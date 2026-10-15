"""Vticniki strežnika Jellyfin (core/jellyfin_vticniki.py) in most Medijskega centra (core/os_katalog.py).

Brez interneta: lazni Jellyfin na 127.0.0.1 po uradnem opisu OpenAPI (10.10.7, 10.11.6, 12.2.0): /System/Info/Public,
/Users/Me, /Plugins (+ Enable/Disable/DELETE z razlicico), /Packages, /Repositories, /Packages/Installed/{name},
/System/Restart. Ponovni zagon strežnik res ustavi (vtičnica se zapre) in ga zažene znova na istih vratih; 10.11+ med
zagonom odgovarja 503 (opis OpenAPI 10.11 to navaja pri vseh poteh)."""
import http.server
import json
import tempfile
import threading
import time
import unittest
import urllib.parse
from pathlib import Path

from core import jellyfin_vticniki as JV
from core import os_katalog as K
from core import os_media

ADMIN, NAVADEN = "ZETON-ADMIN", "ZETON-NAVADEN"
G_FANART = "170a157fac6c437aabddca9c25cebd39"
G_SUBS = "4b9ed42f518548b598036ff2989014c4"
G_TRAKT = "4fe3201ed6ae4f2e8917e12bda571281"
G_TRETJI = "11111111222233334444555555555555"
URADNI = "https://repo.jellyfin.org/files/plugin/manifest.json"
TRETJI = "https://plugins.tretja-oseba.example/manifest.json"


class LazniJellyfin:
    """Stanje strežnika ostane med ponovnimi zagoni (kot na disku); HTTP strežnik se ob zagonu res ustavi."""

    def __init__(self, razlicica: str = "10.11.6"):
        self.razlicica = razlicica
        stari = "Superceded" if razlicica.startswith("10.10") else "Superseded"
        self.vticniki = [
            {"Name": "Trakt", "Version": "32.0.0.0", "Id": G_TRAKT, "CanUninstall": True, "HasImage": False, "Status": stari,
             "Description": "stara razlicica"},
            {"Name": "Trakt", "Version": "33.0.0.0", "Id": G_TRAKT, "CanUninstall": True, "HasImage": False, "Status": "Active",
             "Description": "Record your watched media with Trakt."},
            {"Name": "TMDb", "Version": "10.11.6.0", "Id": "b8715ed16c4745289ad3f72deb539cd4", "CanUninstall": False,
             "HasImage": False, "Status": "Active", "Description": "vgrajen"},
        ]
        self.paketi = [
            {"name": "Fanart", "guid": "170a157f-ac6c-437a-abdd-ca9c25cebd39", "category": "MoviesAndShows", "owner": "jellyfin",
             "overview": "Scrape poster images", "description": "", "imageUrl": "https://x.example/fanart.png",
             "versions": [{"version": "14.0.0.0", "targetAbi": "10.10.0.0", "repositoryName": "Jellyfin Stable", "repositoryUrl": URADNI},
                          {"version": "15.0.0.0", "targetAbi": "10.11.0.0", "repositoryName": "Jellyfin Stable", "repositoryUrl": URADNI}]},
            {"name": "Open Subtitles", "guid": "4b9ed42f-5185-48b5-9803-6ff2989014c4", "category": "Subtitles", "owner": "jellyfin",
             "overview": "Download subtitles", "versions": [{"version": "25.0.0.0", "repositoryName": "Jellyfin Stable", "repositoryUrl": URADNI}]},
            {"name": "Trakt", "guid": "4fe3201e-d6ae-4f2e-8917-e12bda571281", "category": "General", "owner": "jellyfin",
             "overview": "Trakt", "versions": [{"version": "34.0.0.0", "repositoryName": "Jellyfin Stable", "repositoryUrl": URADNI}]},
            {"name": "NextPVR", "guid": "9574ac10-bf23-49bc-949f-924f23cfa48f", "category": "LiveTV", "owner": "jellyfin",
             "overview": "Live TV", "versions": [{"version": "15.0.0.0", "repositoryName": "Jellyfin Stable", "repositoryUrl": URADNI}]},
            {"name": "Tuji Kanal", "guid": "11111111-2222-3333-4444-555555555555", "category": "Channels", "owner": "nekdo",
             "overview": "kanal tretje osebe", "versions": [{"version": "1.2.0.0", "repositoryName": "Tretja", "repositoryUrl": TRETJI}]},
            # Strežnik je izlocil vse nezdruzljive razlicice: paket brez razlicic se ne da namestiti.
            {"name": "Prazen", "guid": "22222222-2222-3333-4444-555555555555", "category": "General", "versions": []},
        ]
        self.repozitoriji = [{"Name": "Jellyfin Stable", "Url": URADNI, "Enabled": True},
                             {"Name": "Tretja", "Url": TRETJI, "Enabled": True}]
        self.zahteve = []
        self.zaganja = False
        self.zagonov = 0
        self.streznik = None
        self.vrata = 0
        self._zazeni()

    # --------------------------------------------------------------- HTTP
    def _rocaj(self):
        laz = self

        class H(http.server.BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _poslji(self, koda, telo=None):
                podatki = json.dumps(telo).encode() if telo is not None else b""
                self.send_response(koda)
                if podatki:
                    self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(podatki)))
                self.end_headers()
                self.wfile.write(podatki)

            def _zeton(self):
                auth = self.headers.get("Authorization") or ""
                return auth.split('Token="', 1)[1].split('"', 1)[0] if 'Token="' in auth else ""

            def _obdelaj(self, metoda):
                d = urllib.parse.urlsplit(self.path)
                q = urllib.parse.parse_qs(d.query)
                laz.zahteve.append((metoda, d.path, q))
                if laz.zaganja:
                    return self._poslji(503)
                if d.path == "/System/Info/Public" and metoda == "GET":
                    return self._poslji(200, {"ServerName": "Domaci", "Version": laz.razlicica, "Id": "abc", "ProductName": "Jellyfin Server"})
                zeton = self._zeton()
                if zeton not in (ADMIN, NAVADEN):
                    return self._poslji(401)
                if d.path == "/Users/Me":
                    return self._poslji(200, {"Id": "u1", "Name": "ana", "Policy": {"IsAdministrator": zeton == ADMIN}})
                if zeton != ADMIN:
                    return self._poslji(403)       # RequiresElevation
                return laz._skrbnik(self, metoda, d.path, q)

            def do_GET(self):
                self._obdelaj("GET")

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length") or 0))
                self._obdelaj("POST")

            def do_DELETE(self):
                self._obdelaj("DELETE")
        return H

    def _skrbnik(self, h, metoda, pot, q):
        deli = pot.strip("/").split("/")
        if pot == "/Plugins" and metoda == "GET":
            return h._poslji(200, self.vticniki)
        if pot == "/Packages" and metoda == "GET":
            return h._poslji(200, self.paketi)
        if pot == "/Repositories" and metoda == "GET":
            return h._poslji(200, self.repozitoriji)
        if pot == "/System/Restart" and metoda == "POST":
            threading.Thread(target=self._ponovni_zagon, daemon=True).start()
            return h._poslji(204)
        if deli[0] == "Plugins" and len(deli) == 4 and metoda == "POST" and deli[3] in ("Enable", "Disable"):
            v = next((v for v in self.vticniki if v["Id"] == deli[1] and v["Version"] == deli[2]), None)
            if v is None:
                return h._poslji(404)
            v["Status"] = "Restart" if deli[3] == "Enable" else "Disabled"
            return h._poslji(204)
        if deli[0] == "Plugins" and len(deli) == 3 and metoda == "DELETE":
            v = next((v for v in self.vticniki if v["Id"] == deli[1] and v["Version"] == deli[2]), None)
            if v is None or not v["CanUninstall"]:
                return h._poslji(404)
            v["Status"] = "Deleted"
            return h._poslji(204)
        if deli[:2] == ["Packages", "Installed"] and len(deli) == 3 and metoda == "POST":
            ime = urllib.parse.unquote(deli[2])
            guid = (q.get("assemblyGuid") or [""])[0].replace("-", "")
            repo = (q.get("repositoryUrl") or [""])[0]
            paket = next((p for p in self.paketi if p["name"] == ime and p["guid"].replace("-", "") == guid and p["versions"]
                          and (not repo or any(v["repositoryUrl"] == repo for v in p["versions"]))), None)
            if paket is None or "version" in q:
                return h._poslji(404)
            najnovejsa = max(paket["versions"], key=lambda v: tuple(int(x) for x in v["version"].split(".")))
            self.vticniki.append({"Name": ime, "Version": najnovejsa["version"], "Id": guid, "CanUninstall": True,
                                  "HasImage": False, "Status": "Restart", "Description": paket.get("overview", "")})
            return h._poslji(204)
        return h._poslji(404)

    # --------------------------------------------------------------- zagon
    def _zazeni(self):
        self.streznik = http.server.ThreadingHTTPServer(("127.0.0.1", self.vrata), self._rocaj())
        self.vrata = self.streznik.server_address[1]
        threading.Thread(target=self.streznik.serve_forever, daemon=True).start()

    def _ponovni_zagon(self):
        time.sleep(0.2)
        self.streznik.shutdown()
        self.streznik.server_close()          # vtičnica zaprta: odjemalec dobi »connection refused«
        time.sleep(0.4)
        self.vticniki = [dict(v, Status="Active") for v in self.vticniki
                         if v["Status"] not in ("Deleted", "Superceded", "Superseded")]
        self.zaganja = self.razlicica >= "10.11"
        self._zazeni()
        self.zagonov += 1
        if self.zaganja:
            time.sleep(0.4)                   # 10.11+: strežnik ze poslusa, a do konca zagona vrne 503
            self.zaganja = False

    @property
    def base(self):
        return "http://127.0.0.1:%d" % self.vrata

    def ustavi(self):
        self.streznik.shutdown()
        self.streznik.server_close()


def _hitro(s):
    time.sleep(min(s, 0.05))


class VticnikiTests(unittest.TestCase):
    def setUp(self):
        self.jf = LazniJellyfin("10.11.6")
        self.addCleanup(self.jf.ustavi)

    def test_stanje_skrbnika_namesceni_katalog_repozitoriji(self):
        s = JV.stanje(self.jf.base, ADMIN)
        self.assertTrue(s["ok"] and s["skrbnik"])
        self.assertEqual(s["streznik"], {"ime": "Domaci", "razlicica": "10.11.6"})
        # Stara (Superseded) razlicica Trakta se ne pokaze; vgrajen TMDb nima Odstrani.
        self.assertEqual([(v["ime"], v["razlicica"], v["stanje"]) for v in s["namesceni"]],
                         [("TMDb", "10.11.6.0", "Active"), ("Trakt", "33.0.0.0", "Active")])
        tmdb = s["namesceni"][0]
        self.assertFalse(tmdb["lahko_odstrani"])
        self.assertTrue(tmdb["lahko_preklopi"] and tmdb["vklopljen"])
        katalog = {p["ime"]: p for p in s["katalog"]}
        self.assertNotIn("Prazen", katalog)                       # brez zdruzljive razlicice
        self.assertEqual(katalog["Fanart"]["razlicica"], "15.0.0.0")
        self.assertTrue(katalog["Fanart"]["uradni"] and katalog["Fanart"]["priporocen"])
        self.assertEqual(katalog["Fanart"]["repozitorij"], "Jellyfin Stable")
        self.assertFalse(katalog["Tuji Kanal"]["uradni"])          # tretja oseba, a samo ker jo je skrbnik dodal
        self.assertEqual(katalog["Open Subtitles"]["safeer_zna"], "jfZnaPodnapisi")
        self.assertFalse(katalog["Open Subtitles"]["priporocen"])
        self.assertTrue(katalog["NextPVR"]["ni_v_safeerju"])
        self.assertTrue(katalog["Trakt"]["namescen"] and katalog["Trakt"]["posodobitev"])
        self.assertEqual(katalog["Trakt"]["namescena_razlicica"], "33.0.0.0")
        self.assertEqual({r["url"]: r["uradni"] for r in s["repozitoriji"]}, {URADNI: True, TRETJI: False})
        prip = {p["ime"]: p for p in s["priporoceno"]}
        self.assertTrue(prip["Fanart"]["v_katalogu"] and not prip["Fanart"]["safeer_zna"])
        self.assertTrue(prip["Open Subtitles"]["safeer_zna"])
        self.assertFalse(prip["Cover Art Archive"]["v_katalogu"])   # ga ni v katalogu tega strežnika
        self.assertFalse(s["potreben_zagon"])

    def test_ne_skrbnik_samo_branje_brez_skrbniskih_klicev(self):
        s = JV.stanje(self.jf.base, NAVADEN)
        self.assertTrue(s["ok"])
        self.assertFalse(s["skrbnik"])
        self.assertEqual((s["namesceni"], s["katalog"], s["repozitoriji"]), ([], [], []))
        self.assertTrue(s["priporoceno"])                          # priporocila samo za branje (brez paketov)
        self.assertTrue(all(p["paket"] is None for p in s["priporoceno"]))
        poti = [p for _, p, _ in self.jf.zahteve]
        self.assertNotIn("/Plugins", poti)
        self.assertNotIn("/Packages", poti)
        with self.assertRaises(JV.NapakaJellyfin) as n:
            JV.preklopi(self.jf.base, NAVADEN, G_TRAKT, "33.0.0.0", False)
        self.assertEqual(n.exception.koda, "skrbnik")

    def test_potekla_prijava(self):
        with self.assertRaises(JV.NapakaJellyfin) as n:
            JV.stanje(self.jf.base, "STAR-ZETON")
        self.assertEqual(n.exception.koda, "prijava")

    def test_izklop_vklop_odstrani_namesti_in_ponovni_zagon(self):
        self.assertEqual(JV.preklopi(self.jf.base, ADMIN, G_TRAKT, "33.0.0.0", False), {"ok": True, "potreben_zagon": True})
        s = JV.stanje(self.jf.base, ADMIN)
        trakt = next(v for v in s["namesceni"] if v["ime"] == "Trakt")
        self.assertEqual(trakt["stanje"], "Disabled")
        self.assertFalse(trakt["vklopljen"])
        JV.preklopi(self.jf.base, ADMIN, G_TRAKT, "33.0.0.0", True)
        self.assertIn(("POST", "/Plugins/%s/33.0.0.0/Enable" % G_TRAKT), [(m, p) for m, p, _ in self.jf.zahteve])
        # Namestitev: brez `version` (strežnik izbere najnovejso zdruzljivo), z znanim repozitorijem.
        JV.namesti(self.jf.base, ADMIN, "Fanart", "170a157f-ac6c-437a-abdd-ca9c25cebd39", URADNI)
        zadnja = [z for z in self.jf.zahteve if z[1].startswith("/Packages/Installed/")][-1]
        self.assertEqual(zadnja[2]["assemblyGuid"], [G_FANART])
        self.assertEqual(zadnja[2]["repositoryUrl"], [URADNI])
        self.assertNotIn("version", zadnja[2])
        JV.odstrani(self.jf.base, ADMIN, G_TRAKT, "33.0.0.0")
        s = JV.stanje(self.jf.base, ADMIN)
        self.assertTrue(s["potreben_zagon"])
        po_imenu = {v["ime"]: v for v in s["namesceni"]}
        self.assertEqual(po_imenu["Fanart"]["stanje"], "Restart")
        self.assertEqual(po_imenu["Trakt"]["stanje"], "Deleted")
        self.assertFalse(po_imenu["Trakt"]["lahko_odstrani"])

        faze = []
        izid = JV.ponovni_zagon(self.jf.base, ADMIN, lambda f, s_: faze.append(f), spi=_hitro, rok=20)
        self.assertTrue(izid["ok"], izid)
        self.assertEqual(self.jf.zagonov, 1)
        self.assertEqual(faze[0], "ustavljam")
        self.assertEqual(faze[-1], "pripravljen")
        self.assertIn("zaganjam", faze)
        s = JV.stanje(self.jf.base, ADMIN)
        self.assertEqual({v["ime"]: v["stanje"] for v in s["namesceni"]}, {"Fanart": "Active", "TMDb": "Active"})
        self.assertFalse(s["potreben_zagon"])

    def test_tuj_repozitorij_samo_ce_je_na_strezniku(self):
        with self.assertRaises(JV.NapakaJellyfin) as n:
            JV.namesti(self.jf.base, ADMIN, "Fanart", "170a157f-ac6c-437a-abdd-ca9c25cebd39", "https://zlonamerno.example/m.json")
        self.assertEqual(n.exception.koda, "neveljavno")
        self.assertFalse([z for z in self.jf.zahteve if z[1].startswith("/Packages/Installed/")])
        JV.namesti(self.jf.base, ADMIN, "Tuji Kanal", "11111111-2222-3333-4444-555555555555", TRETJI)
        self.assertIn(G_TRETJI, [v["Id"] for v in self.jf.vticniki])

    def test_neveljavni_vnosi_ne_pridejo_do_streznika(self):
        for ident, razl in (("../System/Restart", "1.0"), (G_TRAKT, "1.0/../../x"), ("", "1.0"), (G_TRAKT, "")):
            with self.assertRaises(JV.NapakaJellyfin):
                JV.preklopi(self.jf.base, ADMIN, ident, razl, True)
            with self.assertRaises(JV.NapakaJellyfin):
                JV.odstrani(self.jf.base, ADMIN, ident, razl)
        with self.assertRaises(JV.NapakaJellyfin):
            JV.namesti(self.jf.base, ADMIN, "Fanart\r\nX: y", G_FANART)
        self.assertFalse([z for z in self.jf.zahteve if z[0] != "GET"])

    def test_http_samo_v_domacem_omrezju(self):
        with self.assertRaises(JV.NapakaJellyfin) as n:
            JV.stanje("http://8.8.8.8:8096", ADMIN)
        self.assertEqual(n.exception.koda, "neveljavno")


class RazlicicaTests(unittest.TestCase):
    def test_10_10_superceded_in_zagon_brez_503(self):
        jf = LazniJellyfin("10.10.7")
        self.addCleanup(jf.ustavi)
        s = JV.stanje(jf.base, ADMIN)
        self.assertEqual([v["razlicica"] for v in s["namesceni"] if v["ime"] == "Trakt"], ["33.0.0.0"])
        JV.preklopi(jf.base, ADMIN, G_TRAKT, "33.0.0.0", False)
        self.assertTrue(JV.ponovni_zagon(jf.base, ADMIN, spi=_hitro, rok=20)["ok"])
        self.assertEqual(jf.zagonov, 1)

    def test_503_med_zagonom_ni_pripravljen(self):
        jf = LazniJellyfin("10.11.6")
        self.addCleanup(jf.ustavi)
        jf.zaganja = True
        self.assertFalse(JV.odgovarja(jf.base))
        with self.assertRaises(JV.NapakaJellyfin) as n:
            JV.stanje(jf.base, ADMIN)
        self.assertEqual(n.exception.koda, "zaganja")
        jf.zaganja = False
        self.assertTrue(JV.odgovarja(jf.base))

    def test_odstranitev_na_starem_strezniku_brez_poti_z_razlicico(self):
        jf = LazniJellyfin("10.11.6")
        self.addCleanup(jf.ustavi)
        stara = jf._skrbnik

        def brez_razlicice(h, metoda, pot, q):
            deli = pot.strip("/").split("/")
            if metoda == "DELETE" and len(deli) == 3:
                return h._poslji(404)
            if metoda == "DELETE" and len(deli) == 2:
                v = next(v for v in jf.vticniki if v["Id"] == deli[1] and v["Status"] == "Active")
                v["Status"] = "Deleted"
                return h._poslji(204)
            return stara(h, metoda, pot, q)
        jf._skrbnik = brez_razlicice
        JV.odstrani(jf.base, ADMIN, G_TRAKT, "33.0.0.0")
        self.assertEqual([p for m, p, _ in jf.zahteve if m == "DELETE"],
                         ["/Plugins/%s/33.0.0.0" % G_TRAKT, "/Plugins/%s" % G_TRAKT])

    def test_streznik_ne_odgovarja(self):
        jf = LazniJellyfin("10.11.6")
        jf.ustavi()
        # Zagon brez strežnika: ze POST /System/Restart ne uspe.
        with self.assertRaises(JV.NapakaJellyfin):
            JV.ponovni_zagon(jf.base, ADMIN, spi=_hitro, rok=1)

    def test_rok_ponovnega_zagona(self):
        jf = LazniJellyfin("10.11.6")
        self.addCleanup(jf.ustavi)
        jf._ponovni_zagon = lambda: (time.sleep(0.1), jf.streznik.shutdown(), jf.streznik.server_close())
        cas = [0.0]

        def ura():
            cas[0] += 0.5
            return cas[0]
        izid = JV.ponovni_zagon(jf.base, ADMIN, spi=_hitro, ura=ura, rok_ustavitve=3, rok=8)
        self.assertEqual(izid["napaka"], "cas")


class MostTests(unittest.TestCase):
    """Most Medijskega centra: zeton iz zbirke skrivnosti (tu lazne), oznaka »vticniki« samo za Jellyfin."""

    def setUp(self):
        self.jf = LazniJellyfin("10.11.6")
        self.addCleanup(self.jf.ustavi)
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        koren = Path(self.mapa.name)
        strezniki = [{"id": "streznik-aaaaaaaaaaaaaaaa", "ponudnik": "jellyfin", "ime": "JF", "url": self.jf.base,
                      "uporabnik": "ana", "user_id": "u1", "secret_enc": "enc:" + ADMIN},
                     {"id": "streznik-bbbbbbbbbbbbbbbb", "ponudnik": "emby", "ime": "E", "url": "https://emby.test",
                      "uporabnik": "ana", "secret_enc": "enc:x"}]
        (koren / "media.json").write_text(json.dumps({"viri": [], "osebni_strezniki": strezniki}), encoding="utf-8")
        self.dogodki = []
        self.k = K.Katalog(self.mapa.name, dogodek=lambda v, p: self.dogodki.append((v, p)), v_glavni=lambda d: d(),
                           predvajaj=lambda *a: True, vdelano=lambda u: True, youtube=lambda u, n: True,
                           youtube_ukaz=lambda u: True)
        self.k._mc = os_media.MediaCenter(self.mapa.name, roots=[], secret_encryptor=lambda s: "enc:" + s,
                                          secret_decryptor=lambda s: s[4:])

    def test_viri_oznacijo_samo_jellyfin(self):
        viri = {v["id"]: v for v in self.k.izvedi("mediaViri", [])}
        self.assertTrue(viri["streznik-aaaaaaaaaaaaaaaa"]["vticniki"])
        self.assertNotIn("vticniki", viri["streznik-bbbbbbbbbbbbbbbb"])
        self.assertNotIn("secret_enc", viri["streznik-aaaaaaaaaaaaaaaa"])

    def test_most_vticniki_in_zagon(self):
        s = self.k.izvedi("mediaJellyfinVticniki", ["streznik-aaaaaaaaaaaaaaaa"])
        self.assertTrue(s["ok"] and s["skrbnik"])
        self.assertNotIn(ADMIN, json.dumps(s))                       # zeton ne gre na stran
        self.assertEqual(self.k.izvedi("mediaJellyfinVticniki", ["streznik-bbbbbbbbbbbbbbbb"]),
                         {"ok": False, "napaka": "neveljavno"})       # Emby nima tega vmesnika
        self.assertEqual(self.k.izvedi("mediaJellyfinVticnik", ["streznik-aaaaaaaaaaaaaaaa", "zazeni", G_TRAKT, "33.0.0.0"]),
                         {"ok": False, "napaka": "neveljavno"})
        self.assertTrue(self.k.izvedi("mediaJellyfinVticnik", ["streznik-aaaaaaaaaaaaaaaa", "izklopi", G_TRAKT, "33.0.0.0"])["ok"])
        self.assertTrue(self.k.izvedi("mediaJellyfinNamesti", ["streznik-aaaaaaaaaaaaaaaa", "Fanart",
                                                               "170a157f-ac6c-437a-abdd-ca9c25cebd39", URADNI])["ok"])
        self.k.mc._server_cache["streznik-aaaaaaaaaaaaaaaa:"] = (time.time(), [{"id": "x"}])
        jv_zagon = JV.ponovni_zagon
        try:
            JV.ponovni_zagon = lambda b, z, napredek=None, **_: jv_zagon(b, z, napredek, spi=_hitro, rok=20)
            izid = self.k.izvedi("mediaJellyfinZagon", ["streznik-aaaaaaaaaaaaaaaa"])
        finally:
            JV.ponovni_zagon = jv_zagon
        self.assertTrue(izid["ok"], izid)
        faze = [p["faza"] for v, p in self.dogodki if v == "mediaJellyfinZagon"]
        self.assertEqual((faze[0], faze[-1]), ("ustavljam", "pripravljen"))
        self.assertTrue(all(p["streznik"] == "streznik-aaaaaaaaaaaaaaaa" for v, p in self.dogodki if v == "mediaJellyfinZagon"))
        # Po zagonu se knjiznica strežnika prebere znova (novi kanali, metapodatki).
        self.assertNotIn("streznik-aaaaaaaaaaaaaaaa:", self.k.mc._server_cache)

    def test_zaklenjena_zbirka_skrivnosti(self):
        def zaklenjena(_s):
            raise RuntimeError("Zbirka skrivnosti ni na voljo.")
        self.k.mc._secret_decryptor = zaklenjena
        self.assertEqual(self.k.izvedi("mediaJellyfinVticniki", ["streznik-aaaaaaaaaaaaaaaa"]),
                         {"ok": False, "napaka": "skrivnost"})


class PriporocenoTests(unittest.TestCase):
    def test_priporoceno_so_samo_podatki_in_veljavni_guidi(self):
        for p in JV.PRIPOROCENO:
            self.assertTrue(JV.cist_guid(p["guid"]), p)
            self.assertTrue(set(p) <= {"guid", "ime", "razlog", "safeer_zna"}, p)
        besedila = (Path(__file__).resolve().parent.parent / "assets" / "os" / "besedila.js").read_text(encoding="utf-8")
        for p in JV.PRIPOROCENO:
            self.assertEqual(besedila.count('"%s":' % p["razlog"]), 6, p["razlog"])     # vseh 6 jezikov
        # Kar Safeer ze zna, je oznaceno: podnapisi s spleta (core/podnapisi_splet.py) in TVHeadend (media_servers).
        zna = {p["ime"] for p in JV.PRIPOROCENO if p.get("safeer_zna")}
        self.assertTrue({"Open Subtitles", "TVHeadend"} <= zna)
        from core import media_servers, podnapisi_splet
        self.assertIn("opensubtitles", podnapisi_splet.NASLOV)
        self.assertIn("tvheadend", media_servers.PONUDNIKI)

    def test_uradni_repozitorij(self):
        self.assertTrue(JV.je_uradni(URADNI))
        self.assertTrue(JV.je_uradni("https://nyc1.mirror.jellyfin.org/files/plugin/manifest.json"))
        self.assertFalse(JV.je_uradni(TRETJI))
        self.assertFalse(JV.je_uradni("https://jellyfin.org.zlo.example/m.json"))
        self.assertFalse(JV.je_uradni("https://notjellyfin.org/m.json"))


class StranTests(unittest.TestCase):
    """Stran: vsak klic mostu iz ploscice obstaja v Katalog.METODE, barve so iz tokens.css."""
    KOREN = Path(__file__).resolve().parent.parent / "assets" / "os"

    def test_klici_mostu_obstajajo(self):
        js = (self.KOREN / "os.js").read_text(encoding="utf-8")
        import re
        klici = set(re.findall(r'"(mediaJellyfin[A-Za-z]*)"', js))
        self.assertEqual(klici, {"mediaJellyfinVticniki", "mediaJellyfinVticnik", "mediaJellyfinNamesti", "mediaJellyfinZagon"})
        self.assertTrue(klici <= set(K.Katalog.METODE))
        # Gumb se pokaze samo, ce most to zna (oznaka »vticniki« iz Katalog._viri).
        self.assertIn('source.ponudnik === "jellyfin" && source.vticniki', js)
        html = (self.KOREN / "index.html").read_text(encoding="utf-8")
        for ident in ("slojJellyfin", "jfVsebina", "jfZagonGumb", "jfSporocilo", "jfZapri", "jfOsvezi"):
            self.assertIn('id="%s"' % ident, html)

    def test_barve_samo_iz_tokens(self):
        import re
        css = (self.KOREN / "katalog.css").read_text(encoding="utf-8")
        blok = css[css.index("/* Vticniki strežnika Jellyfin"):]
        self.assertFalse(re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", blok), blok)


if __name__ == "__main__":
    unittest.main()
