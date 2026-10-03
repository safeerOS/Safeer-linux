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
        # Lastnik, 3. 10. 2026: v Programih ni bilo tega racunalnika, zavihek Priljubljeni pa je bil skrit, dokler je
        # bil prazen (zato ga uporabnik ni nasel), in »V brskalniku« je bil nastet med napravami.
        js = self.js
        self.assertIn('klic("programi")', js)
        self.assertIn('naprava: "ta", imeNaprave: t("taRacunalnik")', js)
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

    def test_stran_je_v_paketu(self):
        self.assertIn('cp -a "$ROOT/assets/os"', beri("packaging", "install_os_payload.sh"))


class TestTemaCinnamon(unittest.TestCase):
    def test_datoteke_teme(self):
        for pot in ("Safeer-Cinnamon/index.theme", "Safeer-Cinnamon/cinnamon/cinnamon.css",
                    "Safeer-Cinnamon/cinnamon/theme.json", "Safeer-Cinnamon/gtk-3.0/gtk.css",
                    "Safeer-Cinnamon/gtk-4.0/gtk.css", "Safeer-Cinnamon-Kontrast/cinnamon/cinnamon.css",
                    "plank/dock.theme", "ozadje/safeer-gore-3840x2160.png", "ozadje/safeer-gore-16-9.svg",
                    "COPYING", "safeer-cinnamon"):
            self.assertTrue(os.path.isfile(os.path.join(TEMA, pot)), pot)

    def test_licenca_navaja_izvor(self):
        c = beri("packaging", "tema-cinnamon", "COPYING")
        for niz in ("GPL-3.0", "CBlue", "Bundy01", "cloweling", "Mint-Y"):
            self.assertIn(niz, c)

    def test_uvozi_obstojeco_osnovo(self):
        css = beri("packaging", "tema-cinnamon", "Safeer-Cinnamon", "cinnamon", "cinnamon.css")
        self.assertIn('@import url("/usr/share/themes/Mint-Y-Dark-Blue/cinnamon/cinnamon.css")', css)
        for gtk in ("gtk-3.0", "gtk-4.0"):
            self.assertIn("Mint-Y-Dark-Blue/%s/gtk.css" % gtk, beri("packaging", "tema-cinnamon", "Safeer-Cinnamon", gtk, "gtk.css"))

    def test_gtk3_brez_focus_visible(self):
        # GTK 3 ne pozna :focus-visible; neznana psevdo-razred bi razveljavil celo pravilo.
        self.assertNotIn(":focus-visible", beri("packaging", "tema-cinnamon", "Safeer-Cinnamon", "gtk-3.0", "gtk.css"))

    def test_vklop_izklop_vrne_nastavitve(self):
        """safeer-cinnamon z laznimi gsettings/dconf: po --izklopi so vse nastavitve in zagoni kot prej."""
        tmp = tempfile.mkdtemp()
        try:
            bin_ = os.path.join(tmp, "bin")
            dom = os.path.join(tmp, "dom")
            os.makedirs(bin_)
            os.makedirs(os.path.join(dom, ".config", "autostart"))
            db = os.path.join(tmp, "db")
            zacetno = ("org.cinnamon.desktop.interface gtk-theme 'Mint-Y-Dark-Aqua'\n"
                       "org.cinnamon.desktop.interface icon-theme 'Mint-Y-Aqua'\n"
                       "org.cinnamon.desktop.interface text-scaling-factor 1.0\n"
                       "org.cinnamon.desktop.wm.preferences theme 'Mint-Y'\n"
                       "org.cinnamon.theme name 'Mint-Y-Dark-Aqua'\n"
                       "org.cinnamon panels-enabled ['1:0:bottom']\n"
                       "org.gnome.desktop.interface color-scheme 'default'\n")
            with open(db, "w") as f:
                f.write(zacetno)
            lazno = {
                "gsettings": '#!/usr/bin/env bash\nDB="%s"\ncase "$1" in\n list-keys) grep "^$2 " "$DB" | awk \'{print $2}\';;\n'
                             ' get) grep "^$2 $3 " "$DB" | cut -d" " -f3-;;\n set) grep -v "^$2 $3 " "$DB" > "$DB.t"; '
                             'echo "$2 $3 $4" >> "$DB.t"; mv "$DB.t" "$DB";;\nesac\n' % db,
                "dconf": "#!/bin/sh\nexit 0\n", "pgrep": "#!/bin/sh\nexit 1\n", "pkill": "#!/bin/sh\nexit 0\n",
                "setsid": "#!/bin/sh\nexit 0\n", "safeer-os": "#!/bin/sh\nexit 0\n", "plank": "#!/bin/sh\nexit 0\n",
                "xrandr": "#!/bin/sh\necho \"Screen 0: current 1920 x 1080\"\n", "sleep": "#!/bin/sh\nexit 0\n",
            }
            for ime, vsebina in lazno.items():
                p = os.path.join(bin_, ime)
                with open(p, "w") as f:
                    f.write(vsebina)
                os.chmod(p, os.stat(p).st_mode | stat.S_IEXEC)
            apps = os.path.join(dom, ".local", "share", "applications")
            os.makedirs(apps)
            with open(os.path.join(apps, "org.gnome.Terminal.desktop"), "w") as f:
                f.write("[Desktop Entry]\nName=Safeer OS\nExec=safeer-os\n")
            star = os.path.join(dom, ".config", "plank", "dock1", "launchers")
            os.makedirs(star)
            with open(os.path.join(star, "star.dockitem"), "w") as f:
                f.write("[PlankDockItemPreferences]\nLauncher=file:///usr/share/applications/x.desktop\n")
            zagon = os.path.join(dom, ".config", "autostart", "safeer-os.desktop")
            with open(zagon, "w") as f:
                f.write("[Desktop Entry]\nName=Safeer OS\nExec=safeer-os\n")
            # Starejsa namestitev teme Safeer OS ob prijavi vsili temo Safeer-OS: med vklopom mora biti izklopljena.
            tema_zagon = os.path.join(dom, ".config", "autostart", "safeer-tema.desktop")
            with open(tema_zagon, "w") as f:
                f.write("[Desktop Entry]\nName=Safeer OS Tema\nExec=safeer-uveljavi-temo\n")
            env = dict(os.environ, PATH=bin_ + os.pathsep + os.environ.get("PATH", ""), HOME=dom,
                       XDG_CONFIG_HOME="", XDG_DATA_HOME="")
            skripta = os.path.join(TEMA, "safeer-cinnamon")
            subprocess.run(["bash", skripta], env=env, check=True, capture_output=True)
            with open(db) as f:
                vmes = f.read()
            self.assertIn("org.cinnamon.theme name 'Safeer-Cinnamon'", vmes)
            self.assertIn("['1:0:top']", vmes)
            with open(zagon) as f:
                self.assertIn("Hidden=true", f.read())
            # Zacetni nabor docka: Plankove privzete (tu: en star launcher) zamenja nas nabor, izklop jih vrne.
            launcherji = os.path.join(dom, ".config", "plank", "dock1", "launchers")
            self.assertTrue(os.path.isfile(os.path.join(launcherji, "org.gnome.Terminal.dockitem")))
            self.assertFalse(os.path.exists(os.path.join(launcherji, "star.dockitem")))
            # Dock se ob prijavi zazene prek safeer-cinnamon --dock (pocaka na ustaljen zaslon), ne neposredno.
            with open(os.path.join(dom, ".config", "autostart", "safeer-cinnamon-dock.desktop")) as f:
                self.assertIn("Exec=safeer-cinnamon --dock", f.read())
            with open(tema_zagon) as f:
                self.assertIn("Hidden=true", f.read())
            subprocess.run(["bash", skripta, "--vecji-tekst"], env=env, check=True, capture_output=True)
            subprocess.run(["bash", skripta, "--izklopi"], env=env, check=True, capture_output=True)
            with open(db) as f:
                self.assertEqual(sorted(f.read().splitlines()), sorted(zacetno.splitlines()))
            with open(zagon) as f:
                self.assertEqual(f.read(), "[Desktop Entry]\nName=Safeer OS\nExec=safeer-os\n")
            with open(tema_zagon) as f:
                self.assertEqual(f.read(), "[Desktop Entry]\nName=Safeer OS Tema\nExec=safeer-uveljavi-temo\n")
            self.assertEqual(os.listdir(star), ["star.dockitem"])
            self.assertEqual(sorted(os.listdir(os.path.join(dom, ".config", "autostart"))),
                             ["safeer-os.desktop", "safeer-tema.desktop"])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    @unittest.skipUnless(os.path.isdir("/usr/share/themes/Mint-Y-Dark-Blue"), "ni Linux Mint")
    def test_povezave_na_mint_obstajajo(self):
        # Mint-Y-Dark-Blue nima metacity-1 (Mint za obrobe vseh tem uporablja Mint-Y); povezava v prazno
        # bi pokvarila obrobe oken.
        skripta = beri("build_cinnamon_tema_deb.sh")
        cilji = re.findall(r"^ln -s (\S+) ", skripta, flags=re.M)
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
        vsebina = subprocess.run(["dpkg-deb", "-c", deb], capture_output=True, text=True).stdout
        for pot in ("./usr/bin/safeer-cinnamon", "./usr/share/themes/Safeer-Cinnamon/cinnamon/cinnamon.css",
                    "./usr/share/safeer-cinnamon/plank/dock.theme", "./usr/share/backgrounds/safeer/safeer-gore-3840x2160.png",
                    "./usr/share/doc/safeer-cinnamon/copyright"):
            self.assertIn(pot, vsebina)
        os.remove(deb)


if __name__ == "__main__":
    unittest.main()
