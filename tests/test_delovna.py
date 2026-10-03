"""Delovna povrsina Safeer Cinnamon (assets/os/delovna.*) in tema (packaging/tema-cinnamon).

Varovala iz izkusenj: (1) koda ne sme naslavljati id-ja, ki ga ni v HTML (StreamNexus, SAFEER-ZNANJE §19);
(2) stran klice samo metode mostu, ki jih Safeer OS res ima - nic izmisljenega; (3) paket teme
vsebuje, kar zahteva skripta, in ukaz safeer-cinnamon vrne nastavitve tocno take, kot so bile.
"""
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OS = os.path.join(KOREN, "assets", "os")
TEMA = os.path.join(KOREN, "packaging", "tema-cinnamon")


def beri(*pot):
    with open(os.path.join(KOREN, *pot), encoding="utf-8") as f:
        return f.read()


class TestDelovnaStran(unittest.TestCase):
    def setUp(self):
        self.html = beri("assets", "os", "delovna.html")
        self.js = beri("assets", "os", "delovna.js")

    def test_vsi_idji_obstajajo(self):
        idji = set(re.findall(r'id="([^"]+)"', self.html))
        klicani = set(re.findall(r'\$\("([A-Za-z0-9_-]+)"\)', self.js))
        klicani |= set(re.findall(r'getElementById\("([A-Za-z0-9_-]+)"\)', self.js))
        manjka = sorted(klicani - idji)
        self.assertEqual(manjka, [], "delovna.js naslavlja id-je, ki jih ni v delovna.html: %s" % manjka)

    def test_samo_obstojece_metode_mostu(self):
        py = beri("safeer_os.py")
        metode = set(re.findall(r'klic\("([A-Za-z]+)"', self.js))
        self.assertTrue(metode, "ni najdenih klicev mostu")
        manjka = sorted(m for m in metode if '"%s":' % m not in py)
        self.assertEqual(manjka, [], "delovna.js klice metode, ki jih safeer_os.py nima: %s" % manjka)

    def test_brez_demonstracijskih_podatkov(self):
        # Demo podatki so samo v tests/fixtures/delovna_mock.js (za preizkus postavitve), nikoli v strani.
        for ime in ("delovna.html", "delovna.js", "delovna.css"):
            vsebina = beri("assets", "os", ime).lower()
            self.assertNotIn("(demo)", vsebina, ime)
            self.assertNotIn("delovna_mock", vsebina, ime)

    def test_ascii_identifikatorji(self):
        # Nevidne tuje crke v imenih funkcij (npr. cirilicni "е") zlomijo klic brez opozorila.
        for vrstica in self.js.splitlines():
            koda = re.sub(r'"(?:\\.|[^"\\])*"', '""', vrstica.split("//")[0])
            self.assertIsNone(re.search(r"[^\x00-\x7f]", koda), vrstica.strip()[:80])

    def test_programi_tega_racunalnika_in_priljubljeni(self):
        # Matej, 3. 10. 2026: v Programih ni bilo tega racunalnika, zavihek Priljubljeni pa je bil skrit, dokler je
        # bil prazen (zato ga uporabnik ni nasel), in »V brskalniku« je bil nastet med napravami.
        js = self.js
        self.assertIn('klic("programi")', js)
        self.assertIn('naprava: "ta", imeNaprave: p.oblak ? oznakaOblaka(String(p.oblak)) : t("taRacunalnik")', js)
        self.assertIn('ta.value = "ta"', js, "Ta racunalnik mora biti v izbiri naprav")
        self.assertNotIn('w.value = "splet"', js, "spletne bliznjice niso naprava")
        self.assertNotIn('k === "priljubljeni" && !N.priljubljeniPrg.length) return;', js,
                         "zavihek Priljubljeni mora biti viden tudi prazen")
        self.assertLess(js.index('"priljubljeni", "vse"'), js.index('"pisarna", "ustvarjanje"'))
        self.assertIn("niPriljubljenihPrg", js)
        self.assertEqual(js.count("niPriljubljenihPrg:"), 2, "navodilo mora biti v obeh jezikih")
        # Zvezdica na ploscici doda program z enim klikom in ne sprozi zagona.
        self.assertIn("e.stopPropagation(); preklopiPriljubljen(p);", js)
        # Program tega racunalnika se zazene takoj (brez menija) in v iskanju ni podvojen.
        self.assertIn("if (p.lokalni) { zazeniLokalni(p); return; }", js)
        self.assertIn("return !p.lokalni && (p.ime", js)
        self.assertIn(".program .zvezda.je", beri("assets", "os", "delovna.css"))

    def test_igre_v_oblaku_so_ponudba_ne_namestitev(self):
        # Ponudnik iger v oblaku je med Igrami kot ploscica; namesti se samo na uporabnikov klik v meniju ploscice.
        js = self.js
        self.assertIn('klic("igreOblak")', js)
        self.assertEqual(js.count('klic("igreOblakNamesti"'), 1)
        self.assertIn("function namestiOblak(o)", js)
        namesti = js[js.index("function namestiOblak(o)"):js.index("function meniPrograma(p, x, y)")]
        self.assertIn('klic("igreOblakNamesti", [o.id])', namesti)
        # Namestitev sprozi samo postavka menija - ne nalaganje strani in ne klik na ploscico.
        self.assertEqual(js.count("namestiOblak(o)"), 2, "definicija in ena sama postavka menija")
        self.assertIn('if (p.ponudnikOblaka) { meniOblaka(p, r.left + 12, r.bottom - 6); return; }', js)
        self.assertIn("function oznakaOblaka(ponudnik)", js)

    def test_enter_v_iskanju_odpre_program(self):
        """Na namizju Enter odpre program, ki se ujema (kot meni Start); splet je Shift+Enter. Hiter Enter pocaka na
        programe (I.poEnter), da ne odpre spleta samo zato, ker zadetki se niso prisli."""
        js, html = beri("assets", "os", "delovna.js"), beri("assets", "os", "delovna.html")
        for niz in ("function ocenaPrograma(p, ql)", "I.poEnter = true", 'e.key === "Enter" && e.shiftKey',
                    'izberiZadetek(programi.length ? { vrsta: "program", p: programi[0] } : { vrsta: "splet", q: q })',
                    'if (I.zadetki[pi]._v.vrsta === "program") { I.izbran = pi; break; }'):
            self.assertIn(niz, js)
        self.assertIn("Shift+Enter splet", js)
        self.assertIn("Shift+Enter web", js)
        self.assertIn("Shift+Enter splet", html)
        self.assertNotIn("Enter = splet", js + html)

    def test_most_nima_podvojenih_metod(self):
        # V slovarju metod mostu je bil "splet" zapisan dvakrat (zadnji tiho prepise prvega). Ista metoda na dveh
        # mestih pomeni, da se popravek na enem ne prime - zato vsak slovar v safeer_os.py pregledamo.
        import ast
        drevo = ast.parse(beri("safeer_os.py"))
        podvojeni = []
        for vozel in ast.walk(drevo):
            if isinstance(vozel, ast.Dict):
                kljuci = [k.value for k in vozel.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
                podvojeni += sorted({k for k in kljuci if kljuci.count(k) > 1})
        self.assertEqual(podvojeni, [])

    def test_stran_je_v_paketu(self):
        self.assertIn('cp -a "$ROOT/assets/os"', beri("packaging", "install_os_payload.sh"))


class TestTemaCinnamon(unittest.TestCase):
    def test_datoteke_teme(self):
        for pot in ("Safeer-Cinnamon/index.theme", "Safeer-Cinnamon/cinnamon/cinnamon.css",
                    "Safeer-Cinnamon/cinnamon/theme.json", "Safeer-Cinnamon/gtk-3.0/gtk.css",
                    "Safeer-Cinnamon/gtk-4.0/gtk.css", "Safeer-Cinnamon-Kontrast/cinnamon/cinnamon.css",
                    "Safeer-Cinnamon-Kontrast/gtk-3.0/gtk.css", "Safeer-Cinnamon-Kontrast/gtk-4.0/gtk.css",
                    "Safeer-Cinnamon/cinnamon/sredstva/stikalo-vklopljeno.svg", "Safeer-Cinnamon/cinnamon/sredstva/polje-izbrano.svg",
                    "plank/dock.theme", "ozadje/safeer-gore-3840x2160.png", "ozadje/safeer-gore-16-9.svg",
                    "COPYING", "safeer-cinnamon", "izbira"):
            self.assertTrue(os.path.isfile(os.path.join(TEMA, pot)), pot)
        # Temna razlicica je ista datoteka (tema je samo temna): GTK jo izbere, ko program zahteva temno.
        for tema in ("Safeer-Cinnamon", "Safeer-Cinnamon-Kontrast"):
            for gtk in ("gtk-3.0", "gtk-4.0"):
                self.assertEqual(beri("packaging", "tema-cinnamon", tema, gtk, "gtk.css"),
                                 beri("packaging", "tema-cinnamon", tema, gtk, "gtk-dark.css"), "%s/%s" % (tema, gtk))

    def test_licenca_navaja_izvor(self):
        c = beri("packaging", "tema-cinnamon", "COPYING")
        for niz in ("GPL-3.0", "CBlue", "Bundy01", "cloweling", "Mint-Y"):
            self.assertIn(niz, c)

    def test_uvozi_obstojeco_osnovo(self):
        css = beri("packaging", "tema-cinnamon", "Safeer-Cinnamon", "cinnamon", "cinnamon.css")
        self.assertIn('@import url("/usr/share/themes/Mint-Y-Dark-Blue/cinnamon/cinnamon.css")', css)
        for gtk in ("gtk-3.0", "gtk-4.0"):
            self.assertIn("Mint-Y-Dark-Blue/%s/gtk.css" % gtk, beri("packaging", "tema-cinnamon", "Safeer-Cinnamon", gtk, "gtk.css"))
            # Kontrast je Safeer Cinnamon z dopolnitvami, ne locena tema.
            self.assertIn('@import url("/usr/share/themes/Safeer-Cinnamon/%s/gtk.css")' % gtk,
                          beri("packaging", "tema-cinnamon", "Safeer-Cinnamon-Kontrast", gtk, "gtk.css"))

    def test_gtk3_brez_focus_visible(self):
        # GTK 3 ne pozna :focus-visible; neznana psevdo-razred bi razveljavil celo pravilo.
        self.assertNotIn(":focus-visible", beri("packaging", "tema-cinnamon", "Safeer-Cinnamon", "gtk-3.0", "gtk.css"))

    def test_slike_lupine_obstajajo(self):
        # Slika, ki je ni, v lupini pusti prazno stikalo ali polje (brez napake).
        for tema in ("Safeer-Cinnamon", "Safeer-Cinnamon-Kontrast"):
            css = beri("packaging", "tema-cinnamon", tema, "cinnamon", "cinnamon.css")
            for slika in re.findall(r'url\("(sredstva/[^"]+)"\)', css):
                self.assertTrue(os.path.isfile(os.path.join(TEMA, tema, "cinnamon", slika)), slika)

    def test_obrobe_oken_v_paleti(self):
        # Obrobe oken rise Mint-Y (metacity), barve pa vzame iz teme GTK po teh imenih - brez njih ostanejo Mintove.
        css = beri("packaging", "tema-cinnamon", "Safeer-Cinnamon", "gtk-3.0", "gtk.css")
        for ime in ("wm_bg", "wm_title", "wm_border", "wm_icon_bg", "wm_icon_close_bg", "wm_button_hover_bg", "selected_bg_color"):
            self.assertRegex(css, r"@define-color %s #[0-9a-f]{6};" % ime)

    # ------------------------------------------------------------------ ukaz safeer-cinnamon v laznem okolju
    APPLETI = ("['panel1:left:0:menu@cinnamon.org:0', 'panel1:left:2:grouped-window-list@cinnamon.org:2', "
               "'panel1:right:5:calendar@cinnamon.org:13']")
    ZACETNO = ("org.cinnamon.desktop.interface gtk-theme 'Mint-Y-Dark-Aqua'\n"
               "org.cinnamon.desktop.interface icon-theme 'Mint-Y-Aqua'\n"
               "org.cinnamon.desktop.interface text-scaling-factor 1.0\n"
               "org.cinnamon.desktop.wm.preferences theme 'Mint-Y'\n"
               "org.cinnamon.theme name 'Mint-Y-Dark-Aqua'\n"
               "org.cinnamon.desktop.background picture-uri 'file:///home/u/moje.jpg'\n"
               "org.cinnamon.desktop.background picture-options 'zoom'\n"
               "org.cinnamon.desktop.background.slideshow slideshow-enabled true\n"
               "org.cinnamon panels-enabled ['1:0:bottom']\n"
               "org.cinnamon enabled-applets " + APPLETI + "\n"
               "org.gnome.desktop.interface color-scheme 'default'\n")
    DOCK = "/net/launchpad/plank/docks/dock1/"

    def _okolje(self, tmp):
        """Lazni gsettings/dconf/plank ... in zacasni koren sistema (SAFEER_CINNAMON_KOREN), da je izid enak na vsakem
        racunalniku. Vrne slovar: env, db (gsettings), dconf, dom, koren, mapa (nastavitve ukaza), spices."""
        bin_, dom, koren = os.path.join(tmp, "bin"), os.path.join(tmp, "dom"), os.path.join(tmp, "koren")
        db, dconf = os.path.join(tmp, "db"), os.path.join(tmp, "dconf.json")
        os.makedirs(bin_)
        os.makedirs(os.path.join(dom, ".config", "autostart"))
        with open(db, "w") as f:
            f.write(self.ZACETNO)
        lazno = {
            "gsettings": '#!/usr/bin/env bash\nDB="%s"\ncase "$1" in\n list-keys) grep "^$2 " "$DB" | awk \'{print $2}\';;\n'
                         ' get) grep "^$2 $3 " "$DB" | cut -d" " -f3-;;\n set) grep -v "^$2 $3 " "$DB" > "$DB.t"; '
                         'echo "$2 $3 $4" >> "$DB.t"; mv "$DB.t" "$DB";;\nesac\n' % db,
            # dconf z zapisom v datoteko: write/read/dump/load/reset kot pravi (dovolj za nastavitve docka).
            "dconf": '#!/usr/bin/env python3\nimport json, os, sys\nDB = %r\n'
                     'd = json.load(open(DB)) if os.path.exists(DB) else {}\nu, a = sys.argv[1], sys.argv[2:]\n'
                     'if u == "write": d[a[0]] = a[1]\nelif u == "read": print(d.get(a[0], ""))\n'
                     'elif u == "reset": d = {k: v for k, v in d.items() if not k.startswith(a[-1])}\n'
                     'elif u == "dump":\n    print("[/]")\n    for k, v in sorted(d.items()):\n'
                     '        if k.startswith(a[0]): print("%%s=%%s" %% (k[len(a[0]):], v))\n'
                     'elif u == "load":\n    for v in sys.stdin:\n'
                     '        if "=" in v and not v.startswith("["):\n'
                     '            k, x = v.rstrip("\\n").split("=", 1)\n            d[a[0] + k] = x\n'
                     'json.dump(d, open(DB, "w"))\n' % dconf,
            "pgrep": "#!/bin/sh\nexit 1\n", "pkill": "#!/bin/sh\nexit 0\n", "setsid": "#!/bin/sh\nexit 0\n",
            "safeer-os": "#!/bin/sh\nexit 0\n", "plank": "#!/bin/sh\nexit 0\n", "xev": "#!/bin/sh\nexit 0\n",
            "notify-send": "#!/bin/sh\nexit 0\n", "sleep": "#!/bin/sh\nexit 0\n",
            "xrandr": "#!/bin/sh\necho \"Screen 0: minimum 320 x 200, current 1920 x 1080, maximum 16384 x 16384\"\n",
        }
        for ime, vsebina in lazno.items():
            p = os.path.join(bin_, ime)
            with open(p, "w") as f:
                f.write(vsebina)
            os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)
        # Koren sistema: ozadja, tema docka, tema Kontrast za GTK, ikone Papirus in nekaj programov.
        os.makedirs(os.path.join(koren, "usr", "share", "backgrounds", "safeer"))
        for ime in ("safeer-aurora.jpg", "safeer-zora.jpg"):
            shutil.copyfile(os.path.join(TEMA, "ozadje", ime), os.path.join(koren, "usr", "share", "backgrounds", "safeer", ime))
        os.makedirs(os.path.join(koren, "usr", "share", "safeer-cinnamon", "plank"))
        shutil.copyfile(os.path.join(TEMA, "plank", "dock.theme"), os.path.join(koren, "usr", "share", "safeer-cinnamon", "plank", "dock.theme"))
        os.makedirs(os.path.join(koren, "usr", "share", "themes", "Safeer-Cinnamon-Kontrast", "gtk-3.0"))
        os.makedirs(os.path.join(koren, "usr", "share", "icons", "Papirus-Dark"))
        apps = os.path.join(koren, "usr", "share", "applications")
        os.makedirs(apps)
        for ime in ("nemo", "firefox", "safeer-os", "org.gnome.Terminal"):
            with open(os.path.join(apps, ime + ".desktop"), "w") as f:
                f.write("[Desktop Entry]\nName=%s\nExec=%s\n" % (ime, ime))
        # Uporabnik je imel pred vklopom svoj nabor v Planku, zagon Safeer OS ob prijavi in starejso temo Safeer OS.
        star = os.path.join(dom, ".config", "plank", "dock1", "launchers")
        os.makedirs(star)
        with open(os.path.join(star, "star.dockitem"), "w") as f:
            f.write("[PlankDockItemPreferences]\nLauncher=file:///usr/share/applications/x.desktop\n")
        for ime, vsebina in (("safeer-os.desktop", "[Desktop Entry]\nName=Safeer OS\nExec=safeer-os\n"),
                             ("safeer-tema.desktop", "[Desktop Entry]\nName=Safeer OS Tema\nExec=safeer-uveljavi-temo\n")):
            with open(os.path.join(dom, ".config", "autostart", ime), "w") as f:
                f.write(vsebina)
        # Seznam oken na pultu ima pripete programe (nastavitve appleta, ki jih Cinnamon ob odstranitvi appleta izbrise).
        spices = os.path.join(dom, ".config", "cinnamon", "spices", "grouped-window-list@cinnamon.org")
        os.makedirs(spices)
        with open(os.path.join(spices, "2.json"), "w") as f:
            f.write('{"pinned-apps": {"type": "generic", "value": ["nemo.desktop", "firefox.desktop"]}}')
        env = dict(os.environ, PATH=bin_ + os.pathsep + os.environ.get("PATH", ""), HOME=dom, XDG_CONFIG_HOME="",
                   XDG_DATA_HOME="", SAFEER_CINNAMON_BREZ_SISTEMA="1", SAFEER_CINNAMON_KOREN=koren)
        return {"env": env, "db": db, "dconf": dconf, "dom": dom, "koren": koren, "spices": os.path.join(spices, "2.json"),
                "mapa": os.path.join(dom, ".config", "safeer-cinnamon"), "avto": os.path.join(dom, ".config", "autostart"),
                "launcherji": star}

    def _ukaz(self, o, *argumenti):
        return subprocess.run(["bash", os.path.join(TEMA, "safeer-cinnamon"), *argumenti], env=o["env"], check=True,
                              capture_output=True, text=True).stdout

    @staticmethod
    def _vrednost(o, shema, kljuc):
        with open(o["db"]) as f:
            for vrstica in f:
                if vrstica.startswith("%s %s " % (shema, kljuc)):
                    return vrstica.split(" ", 2)[2].strip()
        return None

    @staticmethod
    def _dconf(o, kljuc):
        import json
        if not os.path.exists(o["dconf"]):
            return None
        with open(o["dconf"]) as f:
            return json.load(f).get(TestTemaCinnamon.DOCK + kljuc)

    def _kot_na_zacetku(self, o):
        with open(o["db"]) as f:
            self.assertEqual(sorted(f.read().splitlines()), sorted(self.ZACETNO.splitlines()))
        self.assertEqual(os.listdir(o["launcherji"]), ["star.dockitem"])
        self.assertEqual(sorted(os.listdir(o["avto"])), ["safeer-os.desktop", "safeer-tema.desktop"])
        with open(os.path.join(o["avto"], "safeer-os.desktop")) as f:
            self.assertEqual(f.read(), "[Desktop Entry]\nName=Safeer OS\nExec=safeer-os\n")
        with open(o["spices"]) as f:
            self.assertIn("firefox.desktop", f.read())
        # Ostane samo spomin na zadnje ozadje (za naslednji vklop).
        self.assertEqual(os.listdir(o["mapa"]), ["zadnje-ozadje"])

    def test_videz_pusti_pult_in_seznam_oken(self):
        """Privzeta postavitev (ukaz brez moznosti): tema, ikone in ozadje - pult, appleti, dock in zagoni ostanejo."""
        tmp = tempfile.mkdtemp()
        try:
            o = self._okolje(tmp)
            self._ukaz(o)
            self.assertEqual(self._vrednost(o, "org.cinnamon.theme", "name"), "'Safeer-Cinnamon'")
            self.assertEqual(self._vrednost(o, "org.cinnamon.desktop.interface", "gtk-theme"), "'Safeer-Cinnamon'")
            self.assertEqual(self._vrednost(o, "org.cinnamon.desktop.interface", "icon-theme"), "'Papirus-Dark'")
            self.assertEqual(self._vrednost(o, "org.cinnamon", "panels-enabled"), "['1:0:bottom']")
            self.assertEqual(self._vrednost(o, "org.cinnamon", "enabled-applets"), self.APPLETI)
            self.assertIn("safeer-aurora.jpg", self._vrednost(o, "org.cinnamon.desktop.background", "picture-uri"))
            # Diaprojekcija bi ozadje takoj zamenjala.
            self.assertEqual(self._vrednost(o, "org.cinnamon.desktop.background.slideshow", "slideshow-enabled"), "false")
            self.assertEqual(sorted(os.listdir(o["avto"])), ["safeer-os.desktop", "safeer-tema.desktop"])
            with open(os.path.join(o["avto"], "safeer-os.desktop")) as f:
                self.assertNotIn("Hidden=true", f.read())
            self.assertEqual(os.listdir(o["launcherji"]), ["star.dockitem"])
            self.assertIn("postavitev:   videz", self._ukaz(o, "--stanje"))
            # Uporabnik izbere drugo ozadje; po izklopu in ponovnem vklopu ga dobi nazaj (ne spet Aurore).
            self._ukaz(o, "--ozadje", "zora")
            self.assertIn("postavitev:   videz", self._ukaz(o, "--stanje"))
            self._ukaz(o, "--izklopi")
            self._kot_na_zacetku(o)
            self._ukaz(o)
            self.assertIn("safeer-zora.jpg", self._vrednost(o, "org.cinnamon.desktop.background", "picture-uri"))
            # "Moje ozadje" ostane na izbiro tudi po vklopu.
            self._ukaz(o, "--ozadje", "prejsnje")
            self.assertEqual(self._vrednost(o, "org.cinnamon.desktop.background", "picture-uri"), "'file:///home/u/moje.jpg'")
            self.assertEqual(self._vrednost(o, "org.cinnamon.desktop.background.slideshow", "slideshow-enabled"), "true")
            self._ukaz(o, "--izklopi")
            self._kot_na_zacetku(o)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_dock_en_sam_seznam_oken(self):
        """Postavitev dock: pult gre na vrh, seznam oken z njega v dock (pripeti programi postanejo zacetni nabor);
        zamenjava postavitve in izklop vrneta pult, applet in njegove nastavitve."""
        tmp = tempfile.mkdtemp()
        try:
            o = self._okolje(tmp)
            self._ukaz(o, "--profil", "dock")
            self.assertEqual(self._vrednost(o, "org.cinnamon", "panels-enabled"), "['1:0:top']")
            appleti = self._vrednost(o, "org.cinnamon", "enabled-applets")
            self.assertNotIn("window-list", appleti)
            self.assertIn("menu@cinnamon.org", appleti)
            self.assertIn("calendar@cinnamon.org", appleti)
            # Nabor docka: programi, ki jih je imel uporabnik pripete na pultu, in Safeer OS; Plankov stari nabor caka.
            self.assertEqual(sorted(os.listdir(o["launcherji"])), ["firefox.dockitem", "nemo.dockitem", "safeer-os.dockitem"])
            self.assertEqual(self._dconf(o, "dock-items"), "['nemo.dockitem', 'firefox.dockitem', 'safeer-os.dockitem']")
            self.assertEqual(self._dconf(o, "pinned-only"), "false")
            self.assertEqual(self._dconf(o, "theme"), "'Safeer-Cinnamon'")
            # Velikost ikon in skrivanje po zaslonu (lazni zaslon 1920 x 1080): 44 px, vedno viden.
            self.assertEqual(self._dconf(o, "icon-size"), "44")
            self.assertEqual(self._dconf(o, "hide-mode"), "'none'")
            # Dock se ob prijavi zazene prek safeer-cinnamon --dock (pocaka na ustaljen zaslon), ne neposredno.
            with open(os.path.join(o["avto"], "safeer-cinnamon-dock.desktop")) as f:
                self.assertIn("Exec=safeer-cinnamon --dock", f.read())
            self.assertFalse(os.path.exists(os.path.join(o["avto"], "safeer-cinnamon.desktop")), "delovna povrsina ni del postavitve dock")
            with open(os.path.join(o["avto"], "safeer-os.desktop")) as f:
                self.assertNotIn("Hidden=true", f.read())
            self.assertIn("postavitev:   dock", self._ukaz(o, "--stanje"))
            # Vecje besedilo poveca tudi ikone docka; kar uporabnik nastavi sam, ostane.
            self._ukaz(o, "--vecji-tekst", "150")
            self.assertEqual(self._vrednost(o, "org.cinnamon.desktop.interface", "text-scaling-factor"), "1.5")
            self.assertEqual(self._dconf(o, "icon-size"), "44", "lazni pgrep: dock ne tece, zato se ne prilagaja")
            self._ukaz(o, "--obicajen-tekst")
            self.assertEqual(self._vrednost(o, "org.cinnamon.desktop.interface", "text-scaling-factor"), "1.0")
            # Cinnamon ob odstranitvi appleta izbrise njegove nastavitve; uporabnik si dock prilagodi.
            os.remove(o["spices"])
            subprocess.run(["dconf", "write", self.DOCK + "icon-size", "52"], env=o["env"], check=True)
            os.remove(os.path.join(o["launcherji"], "firefox.dockitem"))          # uporabnik Firefox povlece iz docka
            # Nazaj na "samo videz": pult dol, seznam oken s pripetimi programi nazaj, dock ugasnjen, a zapomnjen.
            self._ukaz(o, "--profil", "videz")
            self.assertEqual(self._vrednost(o, "org.cinnamon", "panels-enabled"), "['1:0:bottom']")
            self.assertEqual(self._vrednost(o, "org.cinnamon", "enabled-applets"), self.APPLETI)
            with open(o["spices"]) as f:
                self.assertIn("firefox.desktop", f.read())
            self.assertFalse(os.path.exists(os.path.join(o["avto"], "safeer-cinnamon-dock.desktop")))
            self.assertEqual(os.listdir(o["launcherji"]), ["star.dockitem"])
            self.assertTrue(os.path.isdir(os.path.join(o["mapa"], "dock-nas", "launchers")))
            # Spet dock: tak, kot ga je uporabnik pustil (52 px ostane njegovih, Firefoxa mu ne vsilimo nazaj).
            self._ukaz(o, "--profil", "dock")
            self.assertEqual(sorted(os.listdir(o["launcherji"])), ["nemo.dockitem", "safeer-os.dockitem"])
            self.assertEqual(self._dconf(o, "icon-size"), "52")
            with open(os.path.join(o["mapa"], "dock-nastavljeno")) as f:
                self.assertIn("ikone=uporabnik", f.read())
            self.assertNotIn("window-list", self._vrednost(o, "org.cinnamon", "enabled-applets"))
            self._ukaz(o, "--izklopi")
            self._kot_na_zacetku(o)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_delovna_in_izklop_vrneta_nastavitve(self):
        """Postavitev delovna: dock + delovna povrsina Safeer OS; po --izklopi so nastavitve in zagoni kot prej."""
        tmp = tempfile.mkdtemp()
        try:
            o = self._okolje(tmp)
            self._ukaz(o, "--profil", "delovna", "--ozadje", "ohrani")
            self.assertEqual(self._vrednost(o, "org.cinnamon.theme", "name"), "'Safeer-Cinnamon'")
            self.assertEqual(self._vrednost(o, "org.cinnamon", "panels-enabled"), "['1:0:top']")
            self.assertNotIn("window-list", self._vrednost(o, "org.cinnamon", "enabled-applets"))
            self.assertEqual(self._vrednost(o, "org.cinnamon.desktop.background", "picture-uri"), "'file:///home/u/moje.jpg'",
                             "ozadje 'ohrani' pusti uporabnikovo")
            # Samozagon Safeer OS (cel zaslon) in starejsa tema Safeer OS bi se tepla z delovno povrsino.
            for ime in ("safeer-os.desktop", "safeer-tema.desktop"):
                with open(os.path.join(o["avto"], ime)) as f:
                    self.assertIn("Hidden=true", f.read())
            with open(os.path.join(o["avto"], "safeer-cinnamon.desktop")) as f:
                self.assertIn("Exec=safeer-cinnamon --seja", f.read())
            with open(os.path.join(o["avto"], "safeer-cinnamon-dock.desktop")) as f:
                self.assertIn("Exec=safeer-cinnamon --dock", f.read())
            self.assertIn("postavitev:   delovna", self._ukaz(o, "--stanje"))
            # Kontrast zamenja lupino IN programe (GTK); zamenjava postavitve ga ohrani.
            self._ukaz(o, "--kontrast")
            self.assertEqual(self._vrednost(o, "org.cinnamon.theme", "name"), "'Safeer-Cinnamon-Kontrast'")
            self.assertEqual(self._vrednost(o, "org.cinnamon.desktop.interface", "gtk-theme"), "'Safeer-Cinnamon-Kontrast'")
            self._ukaz(o, "--profil", "dock")
            self.assertEqual(self._vrednost(o, "org.cinnamon.theme", "name"), "'Safeer-Cinnamon-Kontrast'")
            self.assertFalse(os.path.exists(os.path.join(o["avto"], "safeer-cinnamon.desktop")))
            with open(os.path.join(o["avto"], "safeer-os.desktop")) as f:
                self.assertNotIn("Hidden=true", f.read())
            self._ukaz(o, "--prosojno")
            self.assertEqual(self._vrednost(o, "org.cinnamon.desktop.interface", "gtk-theme"), "'Safeer-Cinnamon'")
            self._ukaz(o, "--profil", "delovna")
            self._ukaz(o, "--vecji-tekst")
            self.assertEqual(self._vrednost(o, "org.cinnamon.desktop.interface", "text-scaling-factor"), "1.25")
            self._ukaz(o, "--izklopi")
            self._kot_na_zacetku(o)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_nadgradnja_z_razlicice_1_1(self):
        """Vklop z razlicico 1.1 (brez zapisane postavitve, seznam oken se na pultu): prva prijava po nadgradnji umakne
        seznam oken, velikost ikon docka pusti uporabniku, "samo videz" in izklop pa vrneta pult dol."""
        tmp = tempfile.mkdtemp()
        try:
            o = self._okolje(tmp)
            os.makedirs(o["mapa"])
            with open(os.path.join(o["mapa"], "prej.txt"), "w") as f:
                f.write("".join("%s:%s=%s\n" % tuple(v.split(" ", 2)) for v in self.ZACETNO.splitlines()
                                if "enabled-applets" not in v))
            for ime in ("vklopljeno", "dock-nabor", "plank-prej.ini"):
                open(os.path.join(o["mapa"], ime), "w").close()
            shutil.copytree(o["launcherji"], os.path.join(o["mapa"], "plank-launcherji-prej"))
            # Dock iz 1.1: uporabnikov nabor (tu samo Nemo); na pultu ima pripeta Nemo in Firefox.
            os.remove(os.path.join(o["launcherji"], "star.dockitem"))
            with open(os.path.join(o["launcherji"], "nemo.dockitem"), "w") as f:
                f.write("[PlankDockItemPreferences]\nLauncher=file://%s/usr/share/applications/nemo.desktop\n" % o["koren"])
            subprocess.run(["dconf", "write", self.DOCK + "dock-items", "['nemo.dockitem']"], env=o["env"], check=True)
            for ime in ("safeer-cinnamon-dock.desktop", "safeer-cinnamon.desktop"):
                with open(os.path.join(o["avto"], ime), "w") as f:
                    f.write("[Desktop Entry]\nType=Application\nName=Safeer Cinnamon\n")
            for nastavitev in (("org.cinnamon.theme", "name", "'Safeer-Cinnamon'"), ("org.cinnamon", "panels-enabled", "['1:0:top']")):
                subprocess.run(["gsettings", "set", *nastavitev], env=o["env"], check=True)
            subprocess.run(["dconf", "write", self.DOCK + "icon-size", "48"], env=o["env"], check=True)
            self.assertIn("postavitev:   delovna", self._ukaz(o, "--stanje"))
            subprocess.run(["bash", os.path.join(TEMA, "safeer-cinnamon"), "--dock"], env=o["env"], capture_output=True)
            with open(os.path.join(o["mapa"], "profil")) as f:
                self.assertEqual(f.read().strip(), "delovna")
            self.assertNotIn("window-list", self._vrednost(o, "org.cinnamon", "enabled-applets"))
            self.assertEqual(self._dconf(o, "icon-size"), "48", "dock iz 1.1 obdrzi uporabnikovo velikost")
            # Programi, pripeti na pultu, gredo s seznamom oken v dock - brez podvajanja tistih, ki so ze tam.
            self.assertEqual(sorted(os.listdir(o["launcherji"])), ["firefox.dockitem", "nemo.dockitem"])
            self.assertEqual(self._dconf(o, "dock-items"), "['nemo.dockitem', 'firefox.dockitem']")
            # Uporabnik Firefox odstrani iz docka; ponovna prijava ga ne vsili nazaj.
            os.remove(os.path.join(o["launcherji"], "firefox.dockitem"))
            subprocess.run(["bash", os.path.join(TEMA, "safeer-cinnamon"), "--dock"], env=o["env"], capture_output=True)
            self.assertEqual(os.listdir(o["launcherji"]), ["nemo.dockitem"])
            self._ukaz(o, "--profil", "videz")
            self.assertEqual(self._vrednost(o, "org.cinnamon", "panels-enabled"), "['1:0:bottom']")
            self.assertEqual(self._vrednost(o, "org.cinnamon", "enabled-applets"), self.APPLETI)
            self.assertEqual(sorted(os.listdir(o["avto"])), ["safeer-os.desktop", "safeer-tema.desktop"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_napacna_postavitev_nicesar_ne_spremeni(self):
        tmp = tempfile.mkdtemp()
        try:
            o = self._okolje(tmp)
            r = subprocess.run(["bash", os.path.join(TEMA, "safeer-cinnamon"), "--profil", "karkoli"], env=o["env"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            with open(o["db"]) as f:
                self.assertEqual(f.read(), self.ZACETNO)
            self.assertFalse(os.path.exists(os.path.join(o["mapa"], "vklopljeno")))
            pomoc = self._ukaz(o, "--help")
            for niz in ("--izberi", "--profil", "videz", "dock", "delovna", "--izklopi", "--kontrast"):
                self.assertIn(niz, pomoc)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_okno_z_izbiro(self):
        """Vnos v meniju odpre okno z izbiro (nic se ne spremeni, dokler uporabnik ne potrdi); oba jezika sta popolna."""
        import ast
        self.assertIn("Exec=safeer-cinnamon --izberi", beri("packaging", "tema-cinnamon", "safeer-cinnamon-vklopi.desktop"))
        vir = beri("packaging", "tema-cinnamon", "izbira")
        drevo = ast.parse(vir)
        besedila = next(ast.literal_eval(v.value) for v in drevo.body
                        if isinstance(v, ast.Assign) and getattr(v.targets[0], "id", "") == "BESEDILA")
        self.assertEqual(sorted(besedila["sl"]), sorted(besedila["en"]))
        for profil in ("videz", "dock", "delovna"):
            self.assertIn(profil, besedila["sl"])
            self.assertIn(profil + "_opis", besedila["sl"])
        # Okno samo nicesar ne nastavlja: poklice ukaz (ena pot za meni, terminal in Safeer OS).
        self.assertNotIn("Gio.Settings.new(shema).set", vir)
        self.assertIn('"--profil", profil, "--ozadje", ozadje', vir)

    @unittest.skipUnless(os.path.isdir("/usr/share/themes/Mint-Y-Dark-Blue"), "ni Linux Mint")
    def test_povezave_na_mint_obstajajo(self):
        # Mint-Y-Dark-Blue nima metacity-1 (Mint za obrobe vseh tem uporablja Mint-Y); povezava v prazno
        # bi pokvarila obrobe oken.
        skripta = beri("build_cinnamon_tema_deb.sh")
        cilji = re.findall(r"ln -s (/\S+) ", skripta)
        self.assertTrue(cilji)
        for c in cilji:
            self.assertTrue(os.path.isdir(c), c)
        self.assertTrue(os.path.isfile("/usr/share/themes/Mint-Y/metacity-1/metacity-theme-3.xml"))

    @unittest.skipUnless(shutil.which("dpkg-deb"), "dpkg-deb ni namescen")
    def test_paket(self):
        r = subprocess.run(["bash", os.path.join(KOREN, "build_cinnamon_tema_deb.sh")], cwd=KOREN,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(os.path.join(KOREN, "packaging", "VERSION_CINNAMON")) as f:
            deb = os.path.join(KOREN, "safeer-cinnamon_%s_all.deb" % f.read().strip())
        try:
            vsebina = subprocess.run(["dpkg-deb", "-c", deb], capture_output=True, text=True).stdout
            for pot in ("./usr/bin/safeer-cinnamon", "./usr/lib/safeer-cinnamon/izbira",
                        "./usr/share/themes/Safeer-Cinnamon/cinnamon/cinnamon.css",
                        "./usr/share/themes/Safeer-Cinnamon/cinnamon/prebarvano.css",
                        "./usr/share/themes/Safeer-Cinnamon/cinnamon/sredstva/stikalo-vklopljeno.svg",
                        "./usr/share/themes/Safeer-Cinnamon/gtk-3.0/prebarvano.css",
                        "./usr/share/themes/Safeer-Cinnamon-Kontrast/gtk-3.0/gtk.css",
                        "./usr/share/themes/Safeer-Cinnamon-Kontrast/gtk-4.0/gtk.css",
                        "./usr/share/safeer-cinnamon/plank/dock.theme", "./usr/share/backgrounds/safeer/safeer-gore-3840x2160.png",
                        "./usr/share/doc/safeer-cinnamon/copyright"):
                self.assertIn(pot, vsebina)
            for tema in ("Safeer-Cinnamon", "Safeer-Cinnamon-Kontrast"):
                self.assertIn("./usr/share/themes/%s/metacity-1 -> /usr/share/themes/Mint-Y/metacity-1" % tema, vsebina)
            polja = subprocess.run(["dpkg-deb", "-f", deb, "Depends", "Recommends"], capture_output=True, text=True).stdout
            odvisnosti = polja.split("Recommends:")[0]
            # GDebi priporocenih paketov ne namesti: dock in okno z izbiro morata delovati tudi tako.
            for paket in ("plank", "dconf-cli", "python3-gi", "gir1.2-gtk-3.0", "mint-themes"):
                self.assertIn(paket, odvisnosti)
            self.assertNotIn("papirus", odvisnosti, "200 MB ikon ostane priporocilo (tema ima nadomestne)")
            prerm = subprocess.run(["dpkg-deb", "-I", deb, "prerm"], capture_output=True, text=True).stdout
            self.assertIn("safeer-cinnamon --izklopi", prerm)
            self.assertIn('[ "$1" = "remove" ]', prerm)
        finally:
            os.remove(deb)


if __name__ == "__main__":
    unittest.main()
