"""safeerctl - Safeer Link iz ukazne vrstice (safeerctl.py): ukazi z laznim Safeer Controlom, izhodne kode, --json."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)
import safeerctl  # noqa: E402
from core import link_zmoznosti  # noqa: E402

NAPRAVE = [
    {"id": "n-tv", "ime": "Dnevna soba", "platforma": "tv", "vrsta": "screen", "zmoznosti": ["url", "media", "text", "file", "files", "remote"]},
    {"id": "n-tel", "ime": "Telefon v predsobi", "platforma": "phone", "vrsta": "screen", "zmoznosti": ["text", "file", "nekaj.novega"]},
    {"id": "n-pc-control", "ime": "Safeer Control (pisarna)", "platforma": "windows", "vrsta": "control", "zmoznosti": ["apps", "remote"]},
    {"id": "n-jaz-control", "ime": "Safeer Control (doma)", "platforma": "linux", "vrsta": "control", "zmoznosti": ["file"], "ta": True},
]


class Control:
    """Lazni Safeer Control: belezi klice in odgovarja kot vmesnik Naprave."""

    def __init__(self):
        self.klici = []
        self.odgovori = {}
        self.stanja = []

    def __call__(self, metoda, *a):
        self.klici.append((metoda,) + a)
        if metoda == "Seznam":
            return {"ok": True, "naprave": NAPRAVE}
        if metoda == "PosljiStanje" and self.stanja:
            return self.stanja.pop(0)
        return self.odgovori.get(metoda, {"ok": False, "koda": "napaka"})


class Osnova(unittest.TestCase):
    def setUp(self):
        self.c = Control()
        self.izpisi, self.napake = [], []
        p = mock.patch.dict(os.environ, {"SAFEER_OS_JEZIK": "sl"})
        p.start()
        self.addCleanup(p.stop)

    def zazeni(self, *argumenti):
        return safeerctl.main(list(argumenti), klic=self.c, izpis=self.izpisi.append, napaka=self.napake.append)

    def json(self):
        return json.loads(self.izpisi[-1])


class Naprave(Osnova):
    def test_seznam(self):
        self.assertEqual(self.zazeni("devices"), 0)
        vrstice = self.izpisi[0].split("\n")
        self.assertEqual(vrstice[0].split(), ["NAPRAVA", "VRSTA", "ID"])
        self.assertIn("Dnevna soba", vrstice[1])
        self.assertTrue(vrstice[1].rstrip().endswith("n-tv"))
        self.assertIn("(ta računalnik)", vrstice[4])

    def test_seznam_json(self):
        self.assertEqual(self.zazeni("devices", "--json"), 0)
        d = self.json()
        self.assertEqual([x["id"] for x in d["devices"]], [n["id"] for n in NAPRAVE])
        self.assertEqual(d["devices"][0], {"id": "n-tv", "name": "Dnevna soba", "platform": "tv", "kind": "screen",
                                           "capabilities": ["url", "text", "file", "files", "remote", "media"], "this": False})
        self.assertTrue(d["devices"][3]["this"])

    def test_brez_naprav(self):
        self.c = lambda *a: {"ok": True, "naprave": []}
        self.assertEqual(self.zazeni("devices"), 0)
        self.assertEqual(self.izpisi, ["V Safeer Linku ni naprav."])

    def test_iskanje_naprave(self):
        n = safeerctl.najdi_napravo
        self.assertEqual(n(NAPRAVE, "n-tel")["id"], "n-tel")
        self.assertEqual(n(NAPRAVE, "dnevna soba")["id"], "n-tv")
        self.assertEqual(n(NAPRAVE, "DNEVNA")["id"], "n-tv")
        self.assertEqual(n(NAPRAVE, "pisarna")["id"], "n-pc-control")
        with self.assertRaises(safeerctl.Napaka) as e:
            n(NAPRAVE, "safeer control")
        self.assertEqual((e.exception.koda, e.exception.izhod), ("vec_naprav", 1))
        with self.assertRaises(safeerctl.Napaka) as e:
            n(NAPRAVE, "kuhinja")
        self.assertEqual(e.exception.koda, "ni_naprave")
        with self.assertRaises(safeerctl.Napaka):
            n(NAPRAVE, "")

    def test_brez_sumnikov(self):
        naprave = [{"id": "a", "ime": "Čitalnica"}, {"id": "b", "ime": "Šola"}]
        self.assertEqual(safeerctl.najdi_napravo(naprave, "citalnica")["id"], "a")
        self.assertEqual(safeerctl.najdi_napravo(naprave, "sol")["id"], "b")


class Zmoznosti(Osnova):
    def test_opisi_v_jeziku_in_neznana_na_koncu(self):
        self.assertEqual(self.zazeni("capabilities", "telefon"), 0)
        vrstice = [v.split(None, 1) for v in self.izpisi[0].split("\n")]
        self.assertEqual(vrstice[0], ["text", "sprejme besedilo"])
        self.assertEqual(vrstice[1], ["file", "sprejme datoteko"])
        self.assertEqual(vrstice[2], ["nekaj.novega", "nekaj.novega"], "neznana zmoznost novejse naprave ostane vidna")

    def test_json(self):
        self.assertEqual(self.zazeni("capabilities", "n-tel", "--json"), 0)
        d = self.json()
        self.assertEqual(d["capabilities"][0], {"name": "text", "description": "receives text", "known": True})
        self.assertEqual(d["capabilities"][2], {"name": "nekaj.novega", "description": "nekaj.novega", "known": False})

    def test_neznana_naprava_v_json(self):
        self.assertEqual(self.zazeni("capabilities", "kuhinja", "--json"), 1)
        self.assertEqual(self.json()["code"], "ni_naprave")
        self.assertFalse(self.json()["ok"])
        self.assertEqual(self.napake, [], "pri --json gre napaka na izhod kot JSON")


class Podatki(Osnova):
    ANDROID = {"hostname": "Telefon X", "sistem": "Android 14", "cpu": {"jedra": 8, "model": "Octa A55"},
               "ram": {"skupaj": 3912749056, "prosto": 2066227200}, "disk": {"skupaj": 117772910592, "prosto": 94713135104},
               "gpu": {"model": "OpenGL ES 3.2", "kodirniki": []}, "baterija": {"raven": 92, "polni": True},
               "pomoc": {"lahko": False, "razlog": "baterija"}}

    def test_android(self):
        self.c.odgovori["Ukaz"] = {"ok": True, "data": self.ANDROID}
        self.assertEqual(self.zazeni("info", "telefon"), 0)
        self.assertEqual(self.c.klici[-1], ("Ukaz", "n-tel", "host.info", "{}"))
        vrstice = dict(v.split(None, 1) for v in self.izpisi[0].split("\n") if not v.startswith("sme"))
        self.assertEqual(vrstice["sistem"], "Android 14 · Telefon X")
        self.assertEqual(vrstice["procesor"], "Octa A55 · 8 jeder")
        self.assertEqual(vrstice["pomnilnik"], "1,9 GiB prosto / 3,6 GiB")
        self.assertEqual(vrstice["baterija"], "92 % (se polni)")
        self.assertIn("sme pomagati  ne (baterija)", self.izpisi[0])

    def test_linux_brez_baterije_in_json(self):
        self.c.odgovori["Ukaz"] = {"ok": True, "data": {"hostname": "pc", "cpu": {"jedra": 4, "obremenitev": 0.5}, "gpu": "Intel UHD"}}
        self.assertEqual(self.zazeni("info", "dnevna"), 0)
        self.assertIn("4 jeder · obremenitev 0.5", self.izpisi[0])
        self.assertIn("Intel UHD", self.izpisi[0])
        self.assertNotIn("baterija", self.izpisi[0])
        self.assertEqual(self.zazeni("info", "dnevna", "--json"), 0)
        self.assertEqual(self.json()["info"]["hostname"], "pc")

    def test_resources_je_drugo_ime_za_info(self):
        self.c.odgovori["Ukaz"] = {"ok": True, "data": self.ANDROID}
        self.assertEqual(self.zazeni("resources", "telefon", "--json"), 0)
        self.assertEqual(self.c.klici[-1], ("Ukaz", "n-tel", "host.info", "{}"))
        self.assertEqual(self.json()["info"]["cpu"]["jedra"], 8)

    def test_naprava_ne_odgovori(self):
        self.c.odgovori["Ukaz"] = {"ok": False, "koda": "cas"}
        self.assertEqual(self.zazeni("info", "telefon"), 1)
        self.assertEqual(self.napake, ["Naprava ni odgovorila."])


class Programi(Osnova):
    def setUp(self):
        super().setUp()
        self.c.odgovori["Aplikacije"] = {"ok": True, "items": [{"id": "vlc.desktop", "name": "VLC"}, {"id": "calc", "name": "Računalo"},
                                                               {"id": "calc2", "name": "Računalo za davke"}]}
        self.c.odgovori["Zazeni"] = {"ok": True}

    def test_seznam(self):
        self.assertEqual(self.zazeni("apps", "pisarna"), 0)
        self.assertEqual([v.split()[-1] for v in self.izpisi[0].split("\n")], ["calc", "calc2", "vlc.desktop"])

    def test_zagon_po_imenu_in_idju(self):
        self.assertEqual(self.zazeni("run", "vlc", "--on", "pisarna"), 0)
        self.assertEqual(self.c.klici[-1], ("Zazeni", "n-pc-control", "vlc.desktop"))
        self.assertEqual(self.izpisi[-1], "Zagnano na napravi Safeer Control (pisarna): VLC")
        self.assertEqual(self.zazeni("run", "racunalo", "--on", "pisarna"), 0, "natancno ime zmaga pred delnim")
        self.assertEqual(self.c.klici[-1][2], "calc")
        self.assertEqual(self.zazeni("run", "calc2", "--on", "pisarna", "--json"), 0)
        self.assertEqual(self.json()["app"]["id"], "calc2")

    def test_dvoumno_in_neznano(self):
        self.assertEqual(self.zazeni("run", "racun", "--on", "pisarna"), 1)
        self.assertIn("ustreza več programom", self.napake[-1])
        self.assertEqual(self.zazeni("run", "gimp", "--on", "pisarna"), 1)
        self.assertEqual(self.napake[-1], "Programa »gimp« na napravi ni.")
        self.assertFalse([k for k in self.c.klici if k[0] == "Zazeni"])

    def test_naprava_zavrne(self):
        self.c.odgovori["Zazeni"] = {"ok": False, "message": "Program se ni zagnal."}
        self.assertEqual(self.zazeni("run", "vlc", "--on", "pisarna"), 1)
        self.assertEqual(self.napake[-1], "Ni uspelo: Program se ni zagnal.")


class Posiljanje(Osnova):
    def test_datoteke_do_konca(self):
        self.c.odgovori["Poslji"] = {"ok": True, "id": "p1", "stanje": "posiljam", "ime": "a.txt", "odstotek": 0, "datotek": 2}
        self.c.stanja = [{"ok": True, "id": "p1", "stanje": "posiljam", "ime": "b.txt", "odstotek": 60, "datotek": 2},
                         {"ok": True, "id": "p1", "stanje": "poslano", "ime": "b.txt", "odstotek": 100, "datotek": 2, "poslanih": 2, "mape": 1}]
        vmes = []
        a = safeerctl.razclenjevalnik().parse_args(["send", "a.txt", "~/b.txt", "--to", "dnevna"])
        self.assertEqual(safeerctl.ukaz_send(a, self.c, self.izpisi.append, napredek=vmes.append, spi=lambda s: None), 0)
        metoda, naprava, poti = self.c.klici[1]
        self.assertEqual((metoda, naprava), ("Poslji", "n-tv"))
        self.assertEqual(json.loads(poti), [os.path.abspath("a.txt"), os.path.expanduser("~/b.txt")])
        self.assertEqual(vmes, ["Pošiljam napravi Dnevna soba: a.txt … 0 %", "Pošiljam napravi Dnevna soba: b.txt … 60 %"])
        self.assertEqual(self.izpisi, ["Poslano napravi Dnevna soba: 2 (mape niso poslane)"])

    def test_napaka_med_posiljanjem(self):
        self.c.odgovori["Poslji"] = {"ok": True, "id": "p1", "stanje": "posiljam", "ime": "a.txt"}
        self.c.stanja = [{"ok": True, "stanje": "napaka", "koda": "naprava_ni_povezana", "sporocilo": "Ciljna naprava ni povezana."}]
        with mock.patch.object(safeerctl.time, "sleep", lambda s: None):
            self.assertEqual(self.zazeni("send", "a.txt", "--to", "dnevna", "--json"), 1)
        self.assertEqual((self.json()["ok"], self.json()["code"]), (False, "naprava_ni_povezana"))

    def test_zavrnjeno_takoj_in_json_uspeh(self):
        self.c.odgovori["Poslji"] = {"ok": False, "koda": "samo_mape"}
        self.assertEqual(self.zazeni("send", "/tmp", "--to", "dnevna"), 1)
        self.assertEqual(self.napake[-1], "Ni uspelo: samo_mape")
        self.c.odgovori["Poslji"] = {"ok": True, "id": "p", "stanje": "poslano", "datotek": 1, "poslanih": 1, "mape": 0}
        self.assertEqual(self.zazeni("send", "a.txt", "--to", "n-tv", "--json"), 0)
        self.assertEqual(self.json(), {"ok": True, "id": "n-tv", "name": "Dnevna soba", "files": 1, "sent": 1, "skipped_folders": 0})

    def test_naprava_brez_zmoznosti(self):
        self.assertEqual(self.zazeni("send", "a.txt", "--to", "pisarna"), 1)
        self.assertIn("manjka zmožnost »file«", self.napake[-1])
        self.assertFalse([k for k in self.c.klici if k[0] == "Poslji"], "naprave, ki datotek ne sprejme, ne nadlegujemo")

    def test_besedilo(self):
        self.c.odgovori["Besedilo"] = {"ok": True}
        self.assertEqual(self.zazeni("text", "https://safeer.si", "--to", "telefon"), 0)
        self.assertEqual(self.c.klici[-1], ("Besedilo", "n-tel", "https://safeer.si"))
        self.assertEqual(self.izpisi[-1], "Besedilo je poslano napravi Telefon v predsobi.")
        self.assertEqual(self.zazeni("text", "x", "--to", "pisarna"), 1, "brez zmoznosti text")

    def test_preimenovanje(self):
        self.c.odgovori["Preimenuj"] = {"ok": True, "ime": "Spalnica"}
        self.assertEqual(self.zazeni("rename", "dnevna", "Spalnica"), 0)
        self.assertEqual(self.c.klici[-1], ("Preimenuj", "n-tv", "Spalnica"))
        self.assertEqual(self.izpisi[-1], "Naprava se zdaj imenuje »Spalnica«.")
        self.c.odgovori["Preimenuj"] = {"ok": False, "koda": "hub_ni_znan"}
        self.assertEqual(self.zazeni("rename", "dnevna", "X"), 1)


class Raba(Osnova):
    def test_brez_ukaza_in_napacen_ukaz(self):
        with mock.patch.object(sys, "stdout"), mock.patch.object(sys, "stderr"):
            self.assertEqual(self.zazeni(), 2)
            self.assertEqual(self.zazeni("neznano"), 2)
            self.assertEqual(self.zazeni("send", "a.txt"), 2, "manjka --to")
            self.assertEqual(self.zazeni("--help"), 0)

    def test_json_pred_ukazom_ali_za_njim(self):
        self.assertEqual(self.zazeni("--json", "devices"), 0)
        pred = self.json()
        self.assertEqual(self.zazeni("devices", "--json"), 0)
        self.assertEqual(pred, self.json())
        self.assertEqual(len(pred["devices"]), len(NAPRAVE))
        # Tudi napaka je pri --json pred ukazom JSON na izhodu.
        self.assertEqual(self.zazeni("--json", "capabilities", "kuhinja"), 1)
        self.assertEqual(self.json()["code"], "ni_naprave")
        self.assertEqual(self.napake, [])

    def test_razlicica(self):
        self.assertEqual(self.zazeni("--version"), 0)
        with open(os.path.join(KOREN, "packaging", "VERSION_CONTROL")) as f:
            self.assertEqual(self.izpisi, ["safeerctl " + f.read().strip()])

    def test_control_ne_tece(self):
        def brez(*_a):
            raise safeerctl.Napaka(safeerctl.t("ni_controla"), safeerctl.IZHOD_CONTROL, "ni_controla")
        self.c = brez
        self.assertEqual(self.zazeni("devices"), 3)
        self.assertIn("Safeer Control ne teče", self.napake[-1])
        self.assertEqual(self.zazeni("devices", "--json"), 3)
        self.assertEqual(self.json(), {"ok": False, "error": safeerctl.t("ni_controla"), "code": "ni_controla"})

    def test_vodilo_seje_brez_spremenljivke(self):
        # SSH-seja ali cron: naslova vodila ni v okolju, pod systemd pa je vedno na /run/user/UID/bus.
        okolje = {"XDG_RUNTIME_DIR": "/run/user/1234"}
        safeerctl.nastavi_vodilo_seje(okolje, obstaja=lambda p: p == "/run/user/1234/bus")
        self.assertEqual(okolje["DBUS_SESSION_BUS_ADDRESS"], "unix:path=/run/user/1234/bus")
        okolje = {}
        with mock.patch.object(os, "getuid", return_value=77):
            safeerctl.nastavi_vodilo_seje(okolje, obstaja=lambda p: p == "/run/user/77/bus")
        self.assertEqual(okolje["DBUS_SESSION_BUS_ADDRESS"], "unix:path=/run/user/77/bus")
        # Nastavljenega naslova ne prepise; brez vticnice ne izmisli nicesar.
        okolje = {"DBUS_SESSION_BUS_ADDRESS": "unix:path=/moje"}
        safeerctl.nastavi_vodilo_seje(okolje, obstaja=lambda p: True)
        self.assertEqual(okolje["DBUS_SESSION_BUS_ADDRESS"], "unix:path=/moje")
        okolje = {}
        safeerctl.nastavi_vodilo_seje(okolje, obstaja=lambda p: False)
        self.assertNotIn("DBUS_SESSION_BUS_ADDRESS", okolje)

    def test_anglescina(self):
        with mock.patch.dict(os.environ, {"SAFEER_OS_JEZIK": "en"}):
            self.assertEqual(self.zazeni("devices"), 0)
            self.assertEqual(self.izpisi[-1].split("\n")[0].split(), ["DEVICE", "TYPE", "ID"])
            self.assertIn("(this computer)", self.izpisi[-1])
            self.assertEqual(safeerctl.velikost(1536 * 1024 * 1024), "1.5 GiB")
        self.assertEqual(safeerctl.velikost(1536 * 1024 * 1024), "1,5 GiB")
        self.assertEqual(safeerctl.velikost(12), "12 B")
        self.assertEqual(safeerctl.velikost(None), "?")
        self.assertEqual(set(safeerctl.BESEDILA["sl"]), set(safeerctl.BESEDILA["en"]), "isti kljuci v obeh jezikih")


class RegisterZmoznosti(unittest.TestCase):
    """Imena zmoznosti so del protokola: kar koda oglasa, mora biti v registru (core/link_zmoznosti.py)."""

    def test_vse_oglasene_zmoznosti_so_v_registru(self):
        import re
        oglasene = set()
        for pot in ("core/link_hub.py", "core/safeer_link.py"):
            with open(os.path.join(KOREN, pot), encoding="utf-8") as f:
                vir = f.read()
            for blok in re.findall(r'zmoznosti = \[([^\]]*)\]', vir) + re.findall(r'\+ \(\[("[a-z.]+")\] if', vir) + \
                    re.findall(r'dodatne_zmoznosti=\(\[("[a-z.]+")\]', vir) + re.findall(r'zmoznosti\.append\(("[a-z.]+")\)', vir):
                oglasene.update(re.findall(r'"([a-z.]+)"', blok))
        self.assertGreaterEqual(len(oglasene), 9, oglasene)
        self.assertEqual(sorted(oglasene - set(link_zmoznosti.ZMOZNOSTI)), [])

    def test_opis_in_vrstni_red(self):
        self.assertEqual(link_zmoznosti.opis("file"), "sprejme datoteko")
        self.assertEqual(link_zmoznosti.opis("file", "en"), "receives a file")
        self.assertEqual(link_zmoznosti.opis("prihodnost"), "prihodnost")
        self.assertEqual(link_zmoznosti.znane(["zzz", "file", "aaa", "url"]), ["url", "file", "aaa", "zzz"])
        self.assertEqual(link_zmoznosti.znane(None), [])
        for ime, (sl, en) in link_zmoznosti.ZMOZNOSTI.items():
            self.assertTrue(sl and en, ime)


class Tovor(unittest.TestCase):
    def test_namescen_safeerctl_tece_brez_izvorne_mape(self):
        with tempfile.TemporaryDirectory() as mapa:
            prefix = os.path.join(mapa, "usr")
            subprocess.run(["bash", os.path.join(KOREN, "packaging", "install_control_payload.sh"), prefix], check=True, capture_output=True)
            ukaz = os.path.join(prefix, "bin", "safeerctl")
            self.assertTrue(os.access(ukaz, os.X_OK))
            r = subprocess.run([ukaz, "--version"], capture_output=True, text=True, cwd=mapa, env={"PATH": os.environ["PATH"], "HOME": mapa})
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(r.stdout.startswith("safeerctl 2."), r.stdout)
            # Prek simbolne povezave (npr. ~/bin) najde isti tovor.
            povezava = os.path.join(mapa, "safeerctl")
            os.symlink(ukaz, povezava)
            r = subprocess.run([povezava, "--version"], capture_output=True, text=True, cwd=mapa, env={"PATH": os.environ["PATH"], "HOME": mapa})
            self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
