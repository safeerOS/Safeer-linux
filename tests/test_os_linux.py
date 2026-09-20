"""Safeer OS za racunalnik (preobleka cez Linux Mint): programi, sistem, datoteke in stran - brez zaslona."""
import os
import re
import tempfile
import unittest
from unittest import mock

import json

from core import os_datoteke, os_jbl, os_omrezje, os_programi, os_sistem, os_zvok

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


def _pisi(pot, vsebina):
    with open(pot, "w", encoding="utf-8") as f:
        f.write(vsebina)


def _vnos(mapa, ime, vsebina):
    with open(os.path.join(mapa, ime), "w", encoding="utf-8") as f:
        f.write("[Desktop Entry]\nType=Application\n" + vsebina)


class Programi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.mapa = os.path.join(self.tmp.name, "applications")
        os.makedirs(self.mapa)
        _vnos(self.mapa, "firefox.desktop", "Name=Firefox\nName[sl]=Firefox\nComment=Browse\nExec=firefox %u\nIcon=firefox\nCategories=Network;WebBrowser;\n")
        _vnos(self.mapa, "cinnamon-settings-themes.desktop", "Name=Themes\nExec=cinnamon-settings themes\nIcon=themes\nCategories=Settings;DesktopSettings;\nOnlyShowIn=X-Cinnamon;\n")
        _vnos(self.mapa, "kde-only.desktop", "Name=KDE stvar\nExec=kstvar\nOnlyShowIn=KDE;\n")
        _vnos(self.mapa, "skrit.desktop", "Name=Skrit\nExec=skrit\nNoDisplay=true\n")
        _vnos(self.mapa, "htop.desktop", "Name=htop\nExec=htop\nTerminal=true\n")
        _vnos(self.mapa, "ni-namescen.desktop", "Name=Manjka\nExec=manjka\nTryExec=ta-program-ne-obstaja-123\n")
        _vnos(self.mapa, "igra.desktop", "Name=Sah\nExec=sah\nCategories=Game;BoardGame;Settings;\n")
        _vnos(self.mapa, "safeer-os.desktop", "Name=Safeer OS\nExec=safeer-os\n")
        self.shramba = os_programi.Shramba(os.path.join(self.tmp.name, "os.json"))
        self.p = os_programi.Programi(self.shramba, mape=[self.mapa], namizja=["X-Cinnamon"])

    def tearDown(self):
        self.tmp.cleanup()

    def test_seznam_kot_meni(self):
        ids = {e["id"]: e for e in self.p.seznam()}
        self.assertEqual(set(ids), {"firefox.desktop", "cinnamon-settings-themes.desktop", "igra.desktop"})
        self.assertEqual(ids["firefox.desktop"]["skupina"], "splet")
        self.assertEqual(ids["cinnamon-settings-themes.desktop"]["skupina"], "sistem")
        self.assertEqual(ids["igra.desktop"]["skupina"], "igre", "igra ostane igra, tudi z nastavitvami")

    def test_zagon_samo_s_seznama(self):
        zagnani = []
        self.assertTrue(self.p.zazeni("firefox.desktop", lambda pot: zagnani.append(pot) or True))
        self.assertEqual(zagnani, [os.path.join(self.mapa, "firefox.desktop")])
        for slab in ("../firefox.desktop", "/usr/share/applications/firefox.desktop", "skrit.desktop", "firefox", ""):
            self.assertFalse(self.p.zazeni(slab, lambda pot: True), slab)
        self.assertEqual(self.shramba.get("uporaba")["firefox.desktop"]["n"], 1)
        self.assertEqual([e for e in self.p.seznam() if e["id"] == "firefox.desktop"][0]["uporaba"], 1)

    def test_skrij_z_domacega(self):
        oznaka = self.p.seznam()[0]["id"]
        self.p.skrij_domov(oznaka)
        self.assertTrue(next(x for x in self.p.seznam() if x["id"] == oznaka)["skrit"])
        self.p.pripni(oznaka, True)             # pripenjanje skritje razveljavi
        z = next(x for x in self.p.seznam() if x["id"] == oznaka)
        self.assertEqual((z["pripet"], z["skrit"]), (True, False))
        self.assertEqual(self.p.skrij_domov("../zlo.desktop"), [])

    def test_pripenjanje_se_shrani(self):
        self.p.pripni("firefox.desktop", True)
        self.p.pripni("ne-obstaja.desktop", True)
        self.assertEqual(os_programi.Shramba(self.shramba.pot).get("pripeti"), ["firefox.desktop"])
        self.p.pripni("firefox.desktop", False)
        self.assertEqual(os_programi.Shramba(self.shramba.pot).get("pripeti"), [])


class Sistem(unittest.TestCase):
    def test_baterija(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(os_sistem.baterija(d))
            os.makedirs(os.path.join(d, "BAT1"))
            _pisi(os.path.join(d, "BAT1", "capacity"), "87\n")
            _pisi(os.path.join(d, "BAT1", "status"), "Charging\n")
            self.assertEqual(os_sistem.baterija(d), {"odstotek": 87, "polni": True, "polna": False})

    def test_nmcli_ubezi(self):
        self.assertEqual(os_sistem._razdeli("wifi:connected:Moj\\:dom"), ["wifi", "connected", "Moj:dom"])

    def test_zvok_iz_pactl(self):
        izpisi = {"get-sink-volume": "Volume: front-left: 29491 /  45% / -20.81 dB,   front-right: 29491 /  45%",
                  "get-sink-mute": "Mute: no"}

        def zazeni(ukaz, cas=4.0):
            return izpisi.get(ukaz[1]) if ukaz[0] == "pactl" else None
        with mock.patch.object(os_sistem, "_zazeni", zazeni):
            self.assertEqual(os_sistem.zvok(), {"glasnost": 45, "utisan": False})

    def test_samo_znani_ukazi(self):
        pognani = []
        with mock.patch.object(os_sistem, "_v_ozadju", lambda u: pognani.append(u) or True), \
                mock.patch.object(os_sistem.shutil, "which", lambda x: "/usr/bin/" + x):
            self.assertTrue(os_sistem.odpri_nastavitve("themes"))
            self.assertTrue(os_sistem.odpri_nastavitve("posodobitve"))
            self.assertFalse(os_sistem.odpri_nastavitve("themes; rm -rf ~"))
            self.assertFalse(os_sistem.odpri_nastavitve("--help"))
            self.assertTrue(os_sistem.napajanje("zakleni"))
            self.assertFalse(os_sistem.napajanje("rm"))
        self.assertEqual(pognani, [["cinnamon-settings", "themes"], ["mintupdate"],
                                   ["cinnamon-screensaver-command", "--lock"]])


class Omrezje(unittest.TestCase):
    IZPISI = {
        ("-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device"):
            "enp1s0:ethernet:connected:Žična povezava 1\nwlp2s0:wifi:disconnected:\ndocker0:bridge:connected (externally):docker0\n"
            "enp9:ethernet:unmanaged:\n",
        ("radio", "wifi"): "enabled\n",
        ("-t", "-f", "NAME,TYPE,DEVICE,ACTIVE", "connection", "show"):
            "Žična povezava 1:802-3-ethernet:enp1s0:yes\nDom\\: zgoraj:802-11-wireless::no\ndocker0:bridge:docker0:yes\n",
    }

    def _nmcli(self, argumenti, cas=6.0):
        self.klici.append(argumenti)
        if argumenti[:3] == ["-t", "-f", "IN-USE,SSID,SIGNAL,SECURITY"]:
            return 0, "*:Dom\\: zgoraj:40:WPA2\n:Dom\\: zgoraj:80:WPA2\n:Kavarna:55:--\n::30:WPA2\n:Sosed:70:WPA2\n", ""
        if argumenti[:3] == ["device", "wifi", "connect"]:
            return (0, "", "") if argumenti[-1] == "pravo" else (4, "", "Error: Secrets were required, but not provided.")
        return 0, self.IZPISI.get(tuple(argumenti), ""), ""

    def setUp(self):
        self.klici = []
        self.popravek = mock.patch.object(os_omrezje, "_nmcli", self._nmcli)
        self.popravek.start()

    def tearDown(self):
        self.popravek.stop()

    def test_stanje(self):
        st = os_omrezje.stanje()
        self.assertEqual([n["vrsta"] for n in st["naprave"]], ["ethernet", "wifi"], "brez mostov in neupravljanih")
        self.assertTrue(st["wifi_vklopljen"])
        imena = [o["ime"] for o in st["omrezja"]]
        self.assertEqual(imena, ["Dom: zgoraj", "Sosed", "Kavarna"], "povezano najprej, nato po signalu; brez skritih")
        dom = st["omrezja"][0]
        self.assertTrue(dom["povezano"] and dom["shranjeno"] and dom["zasciteno"])
        self.assertFalse(st["omrezja"][2]["zasciteno"])
        self.assertEqual([p["ime"] for p in st["shranjene"]], ["Žična povezava 1", "Dom: zgoraj"])

    def test_povezi_in_pozabi(self):
        self.assertEqual(os_omrezje.povezi("Sosed", "narobe"), {"ok": False, "napaka": "geslo"})
        self.assertEqual(os_omrezje.povezi("Sosed", "pravo"), {"ok": True, "napaka": ""})
        self.assertIn(["device", "wifi", "connect", "Sosed", "password", "pravo"], self.klici)
        self.assertFalse(os_omrezje.pozabi("docker0"), "samo wifi/ethernet s seznama")
        self.assertFalse(os_omrezje.pozabi("--help"))
        self.assertTrue(os_omrezje.pozabi("Dom: zgoraj"))
        self.assertIn(["connection", "delete", "id", "Dom: zgoraj"], self.klici)


class Datoteke(unittest.TestCase):
    def test_mape_pregled_iskanje(self):
        with tempfile.TemporaryDirectory() as dom:
            os.makedirs(os.path.join(dom, ".config"))
            os.makedirs(os.path.join(dom, "Dokumenti", "Projekti"))
            os.makedirs(os.path.join(dom, ".skrito"))
            _pisi(os.path.join(dom, "Dokumenti", "porocilo.odt"), "x")
            _pisi(os.path.join(dom, ".skrito", "porocilo-skrito.odt"), "x")
            with open(os.path.join(dom, ".config", "user-dirs.dirs"), "w") as f:
                f.write('XDG_DOCUMENTS_DIR="$HOME/Dokumenti"\nXDG_MUSIC_DIR="$HOME/Glasba"\n')
            with mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": os.path.join(dom, ".config")}):
                mape = os_datoteke.uporabniske_mape(dom)
            self.assertEqual([m["vrsta"] for m in mape], ["HOME", "DOCUMENTS"])
            r = os_datoteke.preglej(os.path.join(dom, "Dokumenti"))
            self.assertEqual([(e["ime"], e["mapa"], e["vrsta"]) for e in r["elementi"]],
                             [("Projekti", True, "mapa"), ("porocilo.odt", False, "dokument")])
            self.assertEqual(os_datoteke.preglej(os.path.join(dom, "ni"))["napaka"], "ni_mape")
            self.assertEqual([z["ime"] for z in os_datoteke.isci("POROC", dom)], ["porocilo.odt"])
            self.assertEqual(os_datoteke.isci("p", dom), [])


def _vol(p):
    return {"front-left": {"value_percent": "%d%%" % p}, "front-right": {"value_percent": "%d%%" % p}}


IZHODI = [
    {"index": 51, "name": "alsa_output.hdmi3", "description": "Tiger Lake HDMI 3", "mute": False, "volume": _vol(100),
     "active_port": "[Out] HDMI3", "ports": [{"name": "[Out] HDMI3", "description": "HDMI / DisplayPort 3 Output",
                                              "type": "HDMI", "availability": "not available"}],
     "properties": {"device.product.name": "Tiger Lake-LP"}},
    {"index": 54, "name": "alsa_output.speaker", "description": "Tiger Lake Speaker", "mute": False, "volume": _vol(40),
     "active_port": "[Out] Speaker", "ports": [{"name": "[Out] Speaker", "description": "Speaker", "type": "Speaker",
                                                "availability": "unknown"}],
     "properties": {"device.product.name": "Tiger Lake-LP"}},
    {"index": 1325, "name": "bluez_output.4C.1", "description": "JBL BAR 300", "mute": False, "volume": _vol(27),
     "properties": {"device.bus": "bluetooth"}},
    {"index": 1400, "name": "safeer_link_zvok", "description": "TV (Safeer Link)", "mute": False, "volume": _vol(100),
     "properties": {}},
]
VHODI = [
    {"index": 1, "name": "bluez_output.4C.1.monitor", "properties": {"device.class": "monitor"}, "volume": _vol(100)},
    {"index": 56, "name": "alsa_input.mic", "description": "Digital Microphone", "mute": True, "volume": _vol(80),
     "active_port": "[In] Mic1", "ports": [{"name": "[In] Mic1", "description": "Digital Microphone", "type": "Mic"}],
     "properties": {"device.product.name": "Tiger Lake-LP"}},
]
TOKOVI = [
    {"index": 1268, "sink": 1325, "corked": True, "mute": False, "volume": {"mono": {"value_percent": "100%"}},
     "properties": {"application.name": "Safeer Browser", "application.process.binary": "WebKitWebProcess", "media.name": "error"}},
    {"index": 1301, "sink": 1325, "corked": False, "mute": False, "volume": _vol(70),
     "properties": {"application.name": "Safeer Browser", "application.process.binary": "WebKitWebProcess", "media.name": "YouTube"}},
    {"index": 1302, "sink": 54, "corked": False, "mute": False, "volume": _vol(50),
     "properties": {"application.name": "Rhythmbox", "application.process.binary": "rhythmbox", "media.name": "Pesem"}},
]


class Zvok(unittest.TestCase):
    def setUp(self):
        self.klici = []

        def pactl(argumenti, cas=4.0):
            self.klici.append(list(argumenti))
            if argumenti == ["get-default-sink"]:
                return 0, "bluez_output.4C.1\n"
            if argumenti == ["get-default-source"]:
                return 0, "alsa_input.mic\n"
            if argumenti[:2] == ["-f", "json"]:
                return 0, json.dumps({"sinks": IZHODI, "sources": VHODI, "sink-inputs": TOKOVI}[argumenti[3]])
            return 0, ""
        self.popravek = mock.patch.object(os_zvok, "_pactl", pactl)
        self.popravek.start()
        self.addCleanup(self.popravek.stop)

    def test_izhodi_vhodi_programi(self):
        izhodi = os_zvok.izhodi()
        # HDMI brez zaslona in navidezni izhod Linka nista na seznamu; privzeti je prvi.
        self.assertEqual([i["id"] for i in izhodi], ["bluez_output.4C.1", "alsa_output.speaker"])
        self.assertEqual((izhodi[0]["ime"], izhodi[0]["vrsta"], izhodi[0]["glasnost"]), ("JBL BAR 300", "bluetooth", 27))
        self.assertEqual((izhodi[1]["ime"], izhodi[1]["podnapis"], izhodi[1]["vrsta"]), ("Speaker", "Tiger Lake-LP", "zvocniki"))
        vhodi = os_zvok.vhodi()
        self.assertEqual([(v["id"], v["utisan"], v["vrsta"]) for v in vhodi], [("alsa_input.mic", True, "mikrofon")])
        programi = os_zvok.programi()
        self.assertEqual([p["ime"] for p in programi], ["Rhythmbox", "Safeer Browser"])
        brskalnik = programi[1]
        self.assertEqual((brskalnik["tokovi"], brskalnik["predvaja"], brskalnik["naslov"], brskalnik["izhod"]),
                         ([1268, 1301], True, "YouTube", "bluez_output.4C.1"))

    def test_dejanja_samo_za_znane(self):
        self.assertTrue(os_zvok.nastavi_izhod("alsa_output.speaker"))
        self.assertIn(["set-default-sink", "alsa_output.speaker"], self.klici)
        self.assertIn(["move-sink-input", "1302", "alsa_output.speaker"], self.klici)
        self.assertFalse(os_zvok.nastavi_izhod("; rm -rf ~"))
        self.assertFalse(os_zvok.nastavi_vhod("bluez_output.4C.1.monitor"))
        self.assertTrue(os_zvok.glasnost_programa("WebKitWebProcess|Safeer Browser", 180))
        self.assertIn(["set-sink-input-volume", "1301", "150%"], self.klici)
        self.assertTrue(os_zvok.premakni_program("rhythmbox|Rhythmbox", "bluez_output.4C.1"))
        self.assertFalse(os_zvok.premakni_program("rhythmbox|Rhythmbox", "neznan"))

    def test_naprave_linka(self):
        with tempfile.TemporaryDirectory() as mapa:
            os.makedirs(os.path.join(mapa, "safeer-link"))
            _pisi(os.path.join(mapa, "safeer-link", "stanje.json"), json.dumps({
                "povezan": True, "zvok": {"naprava": "tv-1", "ime": "Philips", "stanje": "tece"},
                "naprave": [{"id": "tv-1", "ime": "Philips", "zmoznosti": ["url", "audio"]},
                            {"id": "tel", "ime": "Telefon", "zmoznosti": ["url"]}]}))
            with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": mapa}):
                l = os_zvok.link_naprave()
                self.assertEqual([n["id"] for n in l["naprave"]], ["tv-1"])
                self.assertEqual(l["zvok"]["stanje"], "tece")
                _pisi(os.path.join(mapa, "safeer-link", "stanje.json"), json.dumps({"povezan": False, "naprave": [
                    {"id": "tv-1", "ime": "Philips", "zmoznosti": ["audio"]}]}))
                self.assertEqual(os_zvok.link_naprave()["naprave"], [])
            with mock.patch.dict(os.environ, {"XDG_RUNTIME_DIR": os.path.join(mapa, "ni")}):
                self.assertEqual(os_zvok.link_naprave()["naprave"], [])


class Jbl(unittest.TestCase):
    AVAHI = ('+;enp1s0;IPv4;JBL\\032BAR\\032300;_jbl-product._tcp;local\n'
             '=;enp1s0;IPv4;JBL\\032BAR\\032300;_jbl-product._tcp;local;audiocast_3ab7.local;192.168.1.50;59152;'
             '"bootid=x" "security=https 3.0" "MAC=00:1B:44:11:3A:B7" "uuid=uuid:FF"\n'
             '=;enp1s0;IPv6;JBL\\032BAR\\032300;_jbl-product._tcp;local;audiocast_3ab7.local;fe80::1;59152;"MAC=00:1B:44:11:3A:B7"\n')

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.tmp.name})
        p.start()
        self.addCleanup(p.stop)

    def test_najdi_in_prepoznaj_izhod(self):
        r = mock.Mock(stdout=self.AVAHI)
        with mock.patch.object(os_jbl.shutil, "which", lambda x: "/usr/bin/" + x), \
                mock.patch.object(os_jbl.subprocess, "run", lambda *a, **k: r):
            self.assertEqual(os_jbl.najdi(), [{"ime": "JBL BAR 300", "naslov": "192.168.1.50", "mac": "00:1B:44:11:3A:B7"}])
        self.assertFalse(os_jbl.je_vrstica("bluez_output.00_1B_44_11_3A_B8.1"))     # izklopljeno
        os_jbl._shrani({"vklop": True, "bt": "00:1B:44:11:3A:B8", "naslov": "192.168.1.50", "ime": "JBL BAR 300"})
        self.assertTrue(os_jbl.je_vrstica("bluez_output.00_1B_44_11_3A_B8.1"))
        self.assertFalse(os_jbl.je_vrstica("bluez_output.00_11_22_33_44_55.1"))
        self.assertFalse(os_jbl.je_vrstica("alsa_output.speaker"))

    def test_potrdilo_samo_z_ujemajocim_odtisom(self):
        class Odgovor:
            def __init__(self, b): self.b = b
            def read(self): return self.b
            def __enter__(self): return self
            def __exit__(self, *a): return False
        self.assertFalse(os_jbl.prenesi_potrdilo(lambda url, timeout: Odgovor(b"ponaredek")))
        self.assertFalse(os.path.exists(os.path.join(os_jbl.mapa(), "Cert.pem")))
        self.assertFalse(os_jbl.ima_potrdilo())
        # brez potrdila ni ukazov, tudi ce je dodatek oznacen kot vklopljen
        os_jbl._shrani({"vklop": True, "naslov": "192.168.1.50"})
        with mock.patch.object(os_jbl, "_zahteva", side_effect=AssertionError("ne sme klicati")):
            self.assertFalse(os_jbl.preklopi("tv"))
        self.assertFalse(os_jbl.preklopi("reboot"))
        with self.assertRaises(ValueError):
            os_jbl._zahteva("192.168.0.1/../x", "getStatusEx")


class Stran(unittest.TestCase):
    def test_elementi_in_prevodi(self):
        html = _beri("assets", "os", "index.html")
        js = _beri("assets", "os", "os.js")
        for oznaka in set(re.findall(r'\$\("([\w]+)"\)', js)):
            self.assertIn('id="%s"' % oznaka, html, oznaka)
        besedila = _beri("assets", "os", "besedila.js")
        bloki = re.split(r"\n  (sl|en|de|es|fr|it): \{", besedila)[1:]
        jeziki = dict(zip(bloki[0::2], bloki[1::2]))
        self.assertEqual(sorted(jeziki), ["de", "en", "es", "fr", "it", "sl"])
        kljuci = {j: set(re.findall(r'(?:^|[\s{,])"?([\w-]+)"?:\s*"', v)) for j, v in jeziki.items()}
        for j in jeziki:
            self.assertEqual(kljuci[j], kljuci["sl"], j)
        rabljeni = set(re.findall(r'data-t="([\w-]+)"', html)) | set(re.findall(r'\bt\("([\w-]+)"\s*[,)]', js))
        self.assertFalse(rabljeni - kljuci["sl"], rabljeni - kljuci["sl"])
        # Vsak modul in orodje iz os_sistem ima besedilo.
        for m in os_sistem.MODULI:
            self.assertIn("m_" + m, kljuci["sl"])
        for o in os_sistem.ORODJA:
            self.assertIn("o_" + o, kljuci["sl"])

    def test_most_metode(self):
        js = _beri("assets", "os", "os.js")
        py = _beri("safeer_os.py")
        for metoda in set(re.findall(r'klic\("(\w+)"', js)):
            self.assertIn('"%s":' % metoda, py, metoda)

    def test_povezovanje_brez_vsiljevanja(self):
        py = _beri("safeer_os.py")
        js = _beri("assets", "os", "os.js")
        # Ob zagonu ni prijavnega okna; Naprave povedo, ali je v omrezju Safeer Link.
        self.assertNotIn('GLib.timeout_add(1200, lambda: (self._prijava(), False)[1])', py)
        self.assertIn('izid["hubi"] = hubi_v_omrezju()', py)
        self.assertIn('t("novOpisHub", { ime: hubi[0].ime })', js)
        self.assertIn('id="napraveNamig"', _beri("assets", "os", "index.html"))
        link = _beri("assets", "link", "link.js")
        self.assertIn('prijava.ponovno = setTimeout', link)

    def test_scit_v_nastavitvah(self):
        html = _beri("assets", "os", "index.html")
        js = _beri("assets", "os", "os.js")
        py = _beri("safeer_os.py")
        self.assertIn('id="blokScit"', html)
        self.assertIn('stikalo("scitStikalo", "scit"', js)
        self.assertIn('klic("scitVklop", [v])', js)
        for k in ('"scit": self.scit.stanje', '"scitVklop"', "self.scit.zacni_ce_vklopljen()", "self.scit.koncaj()"):
            self.assertIn(k, py, k)
        besedila = _beri("assets", "os", "besedila.js")
        for k in ("scitNapaka_pravilo", "scitNapaka_ni_resolved", "scitNapaka_vrata", "scitNapaka_ni_omrezja"):
            self.assertIn(k + ":", besedila)
        for k in ("oglasi", "groznje", "prevare", "malware", "phishing", "botnet"):
            self.assertIn("scitKat_%s:" % k, besedila)

    def test_zvok_desni_klik_in_nastavitev(self):
        vrstica = _beri("assets", "os", "vrstica.js")
        js = _beri("assets", "os", "os.js")
        self.assertIn('$("sZvok").addEventListener("contextmenu"', vrstica)
        self.assertIn('klic("domov", ["zvok"])', vrstica)
        self.assertIn('if (n.modul === "sound") { pojdi("zvok"); return; }', js)
        besedila = _beri("assets", "os", "besedila.js")
        for vrsta in ("zvocniki", "slusalke", "hdmi", "bluetooth", "usb", "mikrofon"):
            self.assertIn("tip_%s:" % vrsta, besedila)


if __name__ == "__main__":
    unittest.main()


class PreimenovanjeNaprav(unittest.TestCase):
    """Ime naprave hrani sredisce in ga vidijo vse naprave: Safeer OS ga spremeni prek Controla (D-Bus Preimenuj)."""

    def test_preimenovanje_naprav(self):
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(koren, "safeer_os.py"), encoding="utf-8") as f:
            os_py = f.read()
        self.assertIn('"vseNaprave": vse_naprave', os_py)
        self.assertIn('"preimenujNapravo"', os_py)
        self.assertIn('_control_naprave("Preimenuj"', os_py)
        with open(os.path.join(koren, "safeer_control.py"), encoding="utf-8") as f:
            control = f.read()
        self.assertIn('<method name="Preimenuj">', control)
        self.assertIn('link_deljenje.preimenuj_napravo(', control)
        self.assertIn('"ta": n.get("id", "") == link._id()', control)
        with open(os.path.join(koren, "assets", "os", "os.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn('klic("preimenujNapravo", [id, ime])', js)
        self.assertIn('klic("vseNaprave")', js)
        with open(os.path.join(koren, "assets", "os", "index.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertIn('id="seznamNaprav"', html)
        with open(os.path.join(koren, "assets", "os", "besedila.js"), encoding="utf-8") as f:
            b = f.read()
        for kljuc in ("seznamNaprav", "preimenuj:", "shraniIme", "vnesiIme", "preimenovano", "napPreimenovanje", "preimenujNamig", "plat_tv", "plat_web"):
            self.assertEqual(b.count(kljuc + ("" if kljuc.endswith(":") else ":")), 6, kljuc)
