"""Kodi, TVHeadend, AzuraCast, Funkwhale, DLNA, Stremio dodatki in Jellyfin/Emby v Medijskem centru (brez interneta;
Jellyfin je lazni streznik na 127.0.0.1)."""
import http.server
import json
import re
import threading
import urllib.parse
from unittest import mock

from core import media_servers as m

SRV = {"id": "s1", "ime": "Doma", "uporabnik": "kodi"}


def _odgovori(tabela):
    def fake(url, headers=None, body=None, raw=None):
        for kljuc, vrednost in tabela.items():
            if kljuc in url and (not callable(vrednost)):
                return vrednost if isinstance(vrednost, bytes) else json.dumps(vrednost).encode()
            if kljuc in url and callable(vrednost):
                return vrednost(url, body, raw)
        raise OSError("ni odgovora za " + url)
    return fake


def test_http_samo_v_domacem_omrezju():
    assert m.dovoljen_naslov("http://192.168.0.5:8080/jsonrpc")
    assert m.dovoljen_naslov("http://kodi.local:8080/")
    assert m.dovoljen_naslov("https://primer.si/")
    assert not m.dovoljen_naslov("http://8.8.8.8/")


def test_kodi_knjiznica_brez_dodatkov():
    def rpc(url, body, raw):
        metoda = body["method"]
        if metoda == "VideoLibrary.GetMovies":
            return json.dumps({"result": {"movies": [{"movieid": 1, "label": "Film", "file": "/filmi/a b.mkv"}]}}).encode()
        if metoda == "VideoLibrary.GetEpisodes":
            return json.dumps({"result": {}}).encode()
        if metoda == "AudioLibrary.GetSongs":
            return json.dumps({"result": {"songs": [{"songid": 2, "label": "Pesem", "file": "/g/p.mp3",
                                                     "artist": ["A"], "genre": ["Rock"]}]}}).encode()
        if metoda == "Addons.GetAddons":
            return json.dumps({"result": {"addons": [{"addonid": "plugin.video.arte", "name": "ARTE"}]}}).encode()
        return json.dumps({"result": "ok"}).encode()
    with mock.patch.object(m, "_request", _odgovori({"/jsonrpc": rpc})):
        izid = m.catalog("kodi", "http://192.168.0.5:8080", SRV, "geslo")
    film = next(x for x in izid if x["vrsta"] == "film")
    assert film["url"].startswith("http://kodi:geslo@192.168.0.5:8080/vfs/")
    assert urllib.parse.unquote(film["url"].split("/vfs/")[1]) == "/filmi/a b.mkv"
    assert any(x["vrsta"] == "glasba" and x["zanri"] == "Rock" for x in izid)
    # Dodatkov Kodija ne kazemo: tecejo samo v Kodiju, Safeer jih ne more poganjati.
    assert not any(str(x["url"]).startswith("kodi-dodatek:") or x.get("skupina") == "Kodi dodatki" for x in izid)


def test_tvheadend_kanali_so_tv_v_zivo():
    kanali = {"entries": [{"uuid": "abc", "name": "SLO 1", "number": 1, "enabled": True},
                          {"uuid": "x", "name": "Izklopljen", "enabled": False}]}
    with mock.patch.object(m, "_request", _odgovori({"/api/channel/grid": kanali})):
        izid = m.catalog("tvheadend", "http://192.168.0.9:9981", SRV, "")
    assert [x["naslov"] for x in izid] == ["SLO 1"]
    assert izid[0]["vrsta"] == "tv-v-zivo" and "/stream/channel/abc" in izid[0]["url"]


def test_stremio_dodatek_katalog_in_tokovi():
    manifest = {"id": "a", "name": "Dodatek", "catalogs": [{"type": "movie", "id": "top", "extra": [{"name": "search"}]}]}
    tabela = {"/manifest.json": manifest,
              "/catalog/movie/top.json": {"metas": [{"id": "tt1", "name": "Film", "poster": "https://p/1.jpg"}]},
              "/stream/movie/tt1.json": {"streams": [{"infoHash": "abc"}, {"url": "https://cdn.primer/film.mp4", "name": "HD"}]},
              "/stream/movie/tt2.json": {"streams": [{"infoHash": "abc"}]}}
    with mock.patch.object(m, "_request", _odgovori(tabela)):
        izid = m.catalog("stremio", "https://dodatek.primer/manifest.json", SRV, "")
        assert izid[0]["url"] == "stremio:https://dodatek.primer|movie|tt1"
        tokovi = m.stremio_tokovi("https://dodatek.primer", "movie", "tt1")
        assert [t["url"] for t in tokovi if t.get("url")] == ["https://cdn.primer/film.mp4"]
        assert all(t.get("torrent") for t in m.stremio_tokovi("https://dodatek.primer", "movie", "tt2"))


def test_stremio_glasba_radio_tv_gredo_v_svoj_razdelek_in_iskanje_najde_vse():
    """Glasbeni dodatek v Glasbo, radijski v Radio, TV v zivo v TV; iskanje najde tudi kataloge brez lastnega iskanja."""
    manifest = {"id": "a", "name": "Mediji", "catalogs": [
        {"type": "music", "id": "albumi"}, {"type": "radio", "id": "postaje"}, {"type": "tv", "id": "kanali"},
        {"type": "movie", "id": "top"}, {"type": "anime", "id": "novo"}]}
    tabela = {"/manifest.json": manifest,
              "/catalog/music/albumi.json": {"metas": [{"id": "st:alb1", "name": "Jesenski album"}]},
              "/catalog/radio/postaje.json": {"metas": [{"id": "st:r1", "name": "Radio Preizkus"}]},
              "/catalog/tv/kanali.json": {"metas": [{"id": "st:tv1", "name": "Šport TV 1"}, {"id": "st:tv2", "name": "Kino"}]},
              "/catalog/movie/top.json": {"metas": [{"id": "tt1", "name": "Sport film"}]},
              "/catalog/anime/novo.json": {"metas": [{"id": "k1", "name": "Anime"}]},
              "/stream/music/st:alb1.json": {"streams": []},
              "/meta/music/": {"meta": {"id": "st:alb1", "videos": [{"id": "st:alb1:1", "title": "Listje"}]}},
              "/stream/music/st:alb1:1.json": {"streams": [{"url": "https://cdn.primer/listje.mp3", "name": "MP3"}]}}
    with mock.patch.object(m, "_request", _odgovori(tabela)):
        vrste = {x["naslov"]: x["vrsta"] for x in m.catalog("stremio", "https://dodatek.primer/manifest.json", SRV, "")}
        assert vrste == {"Jesenski album": "glasba", "Radio Preizkus": "radio", "Šport TV 1": "tv-v-zivo", "Kino": "tv-v-zivo",
                         "Sport film": "film", "Anime": "video"}
        # Iskanje "sport": TV katalog nima lastnega iskanja - preiscemo ga po imenu (brez naglasov); film brez iskanja ne.
        najdeno = [x["naslov"] for x in m.catalog("stremio", "https://dodatek.primer/manifest.json", SRV, "", "sport")]
        assert najdeno == ["Šport TV 1"]
        # Album nima toka sam: tok da njegov prvi posnetek.
        assert [t["url"] for t in m.stremio_tokovi("https://dodatek.primer", "music", "st:alb1")] == ["https://cdn.primer/listje.mp3"]
        assert m.stremio_vrsta("podcast") == "glasba" and m.stremio_vrsta("events") == "tv-v-zivo" and m.stremio_vrsta("") == "video"


def test_dlna_imenik():
    opis = (b'<root xmlns="urn:schemas-upnp-org:device-1-0"><device><friendlyName>Gerbera</friendlyName>'
            b'<serviceList><service><serviceType>urn:schemas-upnp-org:service:ContentDirectory:1</serviceType>'
            b'<controlURL>/upnp/control/cds</controlURL></service></serviceList></device></root>')
    didl_koren = ('<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/"><container id="1"/></DIDL-Lite>')
    didl_mapa = ('<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" xmlns:dc="http://purl.org/dc/elements/1.1/" '
                 'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/"><item id="9"><dc:title>Pesem</dc:title>'
                 '<upnp:class>object.item.audioItem.musicTrack</upnp:class><upnp:genre>Jazz</upnp:genre>'
                 '<res>http://192.168.0.7:49152/content/media/9.mp3</res></item></DIDL-Lite>')

    def soap(url, body, raw):
        didl = didl_koren if b"<ObjectID>0</ObjectID>" in raw else didl_mapa
        ovoj = ('<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body><u:BrowseResponse '
                'xmlns:u="urn:schemas-upnp-org:service:ContentDirectory:1"><Result>%s</Result></u:BrowseResponse>'
                '</s:Body></s:Envelope>') % didl.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return ovoj.encode()
    with mock.patch.object(m, "_request", _odgovori({"/opis.xml": opis, "/upnp/control/cds": soap})):
        izid = m.catalog("dlna", "http://192.168.0.7:49152/opis.xml", SRV, "")
    assert izid and izid[0]["naslov"] == "Pesem" and izid[0]["vrsta"] == "glasba" and izid[0]["zanri"] == "Jazz"


def test_tv_v_zivo_rtv_programi_in_logotipi(monkeypatch):
    """Lastnik 14. 10. 2026: RTV SLO v zivo je odprl stran 404, kanali so bili brez ikon."""
    from core import ikone_strani, zakoniti_viri as zv
    monkeypatch.setattr(ikone_strani, "iz_predpomnilnika", lambda url: "data:image/png;base64,AA" if "dw.com" in url else "")
    monkeypatch.setattr(zv, "_LOGOTIPI_V_TEKU", {"https://www.rtvslo.si/", "https://www.france24.com/",
                                                   "https://www.aljazeera.com/", "https://www.trtworld.com/",
                                                   "https://www.cbsnews.com/", "https://www.arirang.com/",
                                                   "https://www.tagesschau.de/", "https://www.redbull.com/"})
    kanali = {k["id"]: k for k in zv.tv_v_zivo("SI")}
    assert kanali["tv:tvs1"]["stran"] == "https://365.rtvslo.si/programi/tvs1"
    assert not any("/v-zivo" in str(k.get("stran", "")) for k in kanali.values())
    assert kanali["tv:dw-en"]["slika"].startswith("data:image/")
    assert "tv:tvs1" not in {k["id"] for k in zv.tv_v_zivo("DE")}


# --------------------------------------------------------------- Jellyfin 12 (stara prijava privzeto izklopljena)

def _jellyfin_streznik(razlicica: int):
    """Lazni Jellyfin na 127.0.0.1 po pravilih AuthorizationContext.cs: 12 sprejme samo glavo
    `Authorization: MediaBrowser … Token=` in parameter `ApiKey` (api_key in X-Emby-Token sta stara prijava,
    EnableLegacyAuthorization=false) ter nima /Users/{id}/Items; 10.8 ima samo /Users/{id}/Items in sprejme vse."""
    zahteve = []

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _zeton(self, q):
            najdeno = re.search(r'^MediaBrowser .*Token="([^"]*)"', self.headers.get("Authorization") or "")
            zeton = (najdeno.group(1) if najdeno else "") or (q.get("ApiKey") or [""])[0]
            if razlicica < 12:
                zeton = zeton or self.headers.get("X-Emby-Token") or (q.get("api_key") or [""])[0]
            return zeton

        def _poslji(self, koda, telo=b"", vrsta="application/json"):
            self.send_response(koda)
            self.send_header("Content-Type", vrsta)
            self.send_header("Content-Length", str(len(telo)))
            self.end_headers()
            self.wfile.write(telo)

        def do_POST(self):
            d = urllib.parse.urlsplit(self.path)
            telo = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
            zahteve.append(("POST", d.path, dict(self.headers)))
            auth = self.headers.get("Authorization") or ""
            if d.path == "/Users/AuthenticateByName" and auth.startswith("MediaBrowser ") and 'DeviceId="' in auth \
                    and telo == {"Username": "ana", "Pw": "geslo"}:
                return self._poslji(200, json.dumps({"AccessToken": "ZETON", "User": {"Id": "u1"}}).encode())
            self._poslji(401)

        def do_GET(self):
            d = urllib.parse.urlsplit(self.path)
            q = urllib.parse.parse_qs(d.query)
            zahteve.append(("GET", self.path, dict(self.headers)))
            pot_items = (d.path == "/Items") if razlicica >= 12 else (d.path == "/Users/u1/Items")
            if not pot_items and d.path in ("/Items", "/Users/u1/Items"):
                return self._poslji(404)
            if self._zeton(q) != "ZETON":
                return self._poslji(401)
            if pot_items:
                if d.path == "/Items" and q.get("userId") != ["u1"]:
                    return self._poslji(400)
                return self._poslji(200, json.dumps({"Items": [{"Id": "a1", "Type": "Audio", "Name": "Pesem"}]}).encode())
            if d.path == "/Audio/a1/stream":
                return self._poslji(200, b"ID3", "audio/mpeg")
            self._poslji(404)

    streznik = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=streznik.serve_forever, daemon=True).start()
    return streznik, "http://127.0.0.1:%d" % streznik.server_address[1], zahteve


def test_jellyfin_12_prijava_knjiznica_in_tok_brez_stare_prijave():
    streznik, base, zahteve = _jellyfin_streznik(12)
    try:
        assert m.authenticate("jellyfin", base, "ana", "geslo") == {"token": "ZETON", "user_id": "u1"}
        vrstice = m.catalog("jellyfin", base, {"id": "s1", "ime": "JF", "user_id": "u1"}, "ZETON")
        assert [v["naslov"] for v in vrstice] == ["Pesem"]
        tok = vrstice[0]["url"]
        assert "ApiKey=ZETON" in tok and "api_key" not in tok and "ApiKey=ZETON" in vrstice[0]["slika"]
        # GStreamer in WebKit glav ne dodata: tok mora delati samo z naslovom.
        assert m.tok_odgovarja(tok)
        # Brez stare prijave (Jellyfin 12 jo privzeto zavrne) in brez odstranjene poti /Users/{id}/Items.
        for _, pot, glave in zahteve:
            assert "X-Emby-Token" not in glave and "api_key=" not in pot and not pot.startswith("/Users/u1/Items")
        # Ob predvajanju shranjenega naslova (brez prijave) se doda ApiKey, ne api_key.
        cist = "%s/Audio/a1/stream?static=true" % base
        assert m.s_prijavo(cist, {"ponudnik": "jellyfin", "url": base}, "ZETON") == cist + "&ApiKey=ZETON"
        assert m.tok_odgovarja(m.s_prijavo(cist, {"ponudnik": "jellyfin", "url": base}, "ZETON"))
        assert not m.tok_odgovarja(cist + "&api_key=ZETON")
    finally:
        streznik.shutdown()


def test_jellyfin_10_8_brez_poti_items_se_vrne_na_users_items():
    streznik, base, zahteve = _jellyfin_streznik(10)
    try:
        vrstice = m.catalog("jellyfin", base, {"id": "s1", "ime": "JF", "user_id": "u1"}, "ZETON")
        assert [v["naslov"] for v in vrstice] == ["Pesem"]
        assert m.tok_odgovarja(vrstice[0]["url"])
        assert [p.split("?")[0] for _, p, _ in zahteve if p.split("?")[0].endswith("Items")] == ["/Items", "/Users/u1/Items"]
    finally:
        streznik.shutdown()


def test_emby_ostane_pri_api_key_in_x_emby_token():
    videno = []

    def fake(url, headers=None, body=None, raw=None):
        videno.append((url, headers))
        return json.dumps({"Items": [{"Id": "v1", "Type": "Movie", "Name": "Film"}]}).encode()
    with mock.patch.object(m, "_request", fake):
        vrstice = m.catalog("emby", "https://emby.test", {"id": "s1", "ime": "E", "user_id": "u1"}, "Z")
    assert "/Users/u1/Items" in videno[0][0] and videno[0][1]["X-Emby-Token"] == "Z"
    assert 'Token="Z"' in videno[0][1]["Authorization"]
    assert "api_key=Z" in vrstice[0]["url"]
    assert m.s_prijavo("https://emby.test/Videos/v1/stream?static=true", {"ponudnik": "emby", "url": "https://emby.test"},
                       "Z").endswith("&api_key=Z")


def test_device_id_ni_skupen_in_ne_razkrije_machine_id():
    glava = m._glava_mediabrowser("Z")
    assert glava.startswith('MediaBrowser Client="Safeer OS", Device="') and glava.endswith('Token="Z"')
    did = re.search(r'DeviceId="([^"]+)"', glava).group(1)
    try:
        with open("/etc/machine-id") as f:
            mid = f.read().strip()
    except OSError:
        mid = ""
    if mid:
        assert did.startswith("safeer-") and did != "safeer-os" and mid not in glava
