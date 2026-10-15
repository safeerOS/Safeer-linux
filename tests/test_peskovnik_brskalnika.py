"""Safeer Browser v Flatpaku brez izhoda iz peskovnika (lastnik, 15. 10. 2026, izdaja 1.0.127).

Preizkus pade, ce manifest brskalnika spet dobi dostop do gostitelja (org.freedesktop.Flatpak, cel dom, host-os,
ovoje /app/host-bin) ali ce koda, ki jo brskalnik doseze, v peskovniku spet zazene kaj na gostitelju. Safeer OS
(lupina namizja) dostop obdrzi - zanj ta preizkus ne velja.
"""
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

KOREN = Path(__file__).resolve().parents[1]
MANIFEST = KOREN / "io.github.memelandfaner.SafeerBrowser.yml"

#: Dovoljenja, ki pomenijo izhod iz peskovnika ali dostop do (skoraj) vsega.
PREPOVEDANA = re.compile(
    r"^--(talk-name=org\.freedesktop\.Flatpak|own-name=org\.freedesktop\.Flatpak|"
    r"filesystem=(home|host|host-os|host-etc|~|/|/var|/usr|/etc|xdg-config|xdg-data|xdg-cache|/var/lib/flatpak|"
    r"/var/lib/snapd/desktop|~/\.local|~/\.config|~/\.var)(/?:(ro|rw|create))?$|"
    r"socket=session-bus|socket=system-bus|device=all|allow=devel|talk-name=org\.freedesktop\.systemd1)")

#: Edina dovoljena dovoljenja z utemeljitvijo v manifestu; novo dovoljenje mora biti dodano tu (zavestno).
DOVOLJENA = {
    "--socket=wayland", "--socket=fallback-x11", "--share=ipc", "--device=dri", "--share=network",
    "--socket=pulseaudio", "--env=GTK_USE_PORTAL=1",
    "--filesystem=xdg-download",
    "--filesystem=xdg-config/safeer-mint:create",
    "--filesystem=xdg-config/mimeapps.list:ro",
    "--filesystem=~/.mozilla/firefox:ro", "--filesystem=~/snap/firefox/common/.mozilla/firefox:ro",
    "--filesystem=xdg-config/google-chrome:ro", "--filesystem=xdg-config/chromium:ro",
    "--filesystem=~/snap/chromium/common/chromium:ro", "--filesystem=xdg-config/BraveSoftware:ro",
    "--filesystem=xdg-config/microsoft-edge:ro", "--filesystem=xdg-config/vivaldi:ro", "--filesystem=xdg-config/opera:ro",
}


def dovoljenja(besedilo: str) -> list:
    blok = besedilo.split("\nfinish-args:\n", 1)[1].split("\nmodules:\n", 1)[0]
    return re.findall(r"^  - (\S+)\s*$", blok, re.M)


class Manifest(unittest.TestCase):
    def test_brez_izhoda_iz_peskovnika(self):
        d = dovoljenja(MANIFEST.read_text(encoding="utf-8"))
        self.assertTrue(d)
        prepovedana = [x for x in d if PREPOVEDANA.match(x)]
        self.assertEqual(prepovedana, [], "brskalnik ne sme imeti dostopa do gostitelja")
        self.assertEqual(sorted(set(d) - DOVOLJENA), [], "novo dovoljenje: utemelji ga v manifestu in dodaj v DOVOLJENA")
        for x in d:
            if x.startswith("--filesystem=") and x != "--filesystem=xdg-download" and \
                    x != "--filesystem=xdg-config/safeer-mint:create":
                self.assertTrue(x.endswith(":ro"), x)

    def test_prepovedana_se_zaznajo(self):
        """Varovalo samo: vzorec res ujame, kar je bilo v manifestu do 1.0.126."""
        for x in ("--talk-name=org.freedesktop.Flatpak", "--filesystem=home", "--filesystem=host-os:ro",
                  "--filesystem=host", "--filesystem=/var/lib/flatpak:ro", "--filesystem=xdg-config"):
            self.assertTrue(PREPOVEDANA.match(x), x)

    def test_brez_ovojev_gostitelja(self):
        besedilo = MANIFEST.read_text(encoding="utf-8")
        self.assertNotIn("flatpak_host_wrappers", besedilo)
        self.assertNotIn("host-bin", besedilo)
        self.assertNotIn("org.freedesktop.Flatpak", "\n".join(dovoljenja(besedilo)))

    def test_zypak_za_webkitom(self):
        """zypak je modul za WebKitom in libsoup (predpomnilnik WebKita ostane) in je pripet na commit."""
        besedilo = MANIFEST.read_text(encoding="utf-8")
        moduli = re.findall(r"^  - (?:name: )?(\S+)$", besedilo.split("\nmodules:\n", 1)[1], re.M)
        self.assertEqual(moduli[:4], ["packaging/webkit/webkitgtk6-safeer.yml",
                                      "packaging/webkit/webkitgtk6-safeer-typelib.yml",
                                      "packaging/libsoup/libsoup3-safeer.yml", "zypak"])
        self.assertRegex(besedilo, r"url: https://github\.com/refi64/zypak\n\s+tag: v[\d.]+\n\s+commit: [0-9a-f]{40}\n")
        self.assertNotIn("base: org.electronjs.Electron2.BaseApp", besedilo)

    def test_safeer_os_obdrzi_dostop(self):
        os_ = (KOREN / "io.github.memelandfaner.SafeerOS.yml").read_text(encoding="utf-8")
        self.assertIn("--talk-name=org.freedesktop.Flatpak", os_)


class Koda(unittest.TestCase):
    """Brskalnik v peskovniku: brez flatpak-spawn --host, brez host gio, vse prek portala."""

    def _info(self, d: str, flatpak: bool) -> str:
        pot = os.path.join(d, "flatpak-info")
        with open(pot, "w", encoding="utf-8") as f:
            f.write("[Application]\nname=io.github.memelandfaner.SafeerBrowser\n\n[Session Bus Policy]\n"
                    + ("org.freedesktop.Flatpak=talk\n" if flatpak else "org.freedesktop.portal.Foo=talk\n"))
        return pot

    def test_sme_na_gostitelja_iz_flatpak_info(self):
        from core import gostitelj
        with tempfile.TemporaryDirectory() as d:
            self.assertTrue(gostitelj.sme_na_gostitelja(self._info(d, True)))
            self.assertFalse(gostitelj.sme_na_gostitelja(self._info(d, False)))
        self.assertFalse(gostitelj.sme_na_gostitelja("/ni/datoteke"))

    def test_portal_openuri_klic(self):
        """odpri_prek_portala poklice org.freedesktop.portal.OpenURI.OpenURI(parent, uri, {ask}) na seji D-Bus."""
        from core import gostitelj
        klici = []

        class Vodilo:
            def call(self, ime, pot, vmesnik, metoda, parametri, *ostalo):
                klici.append((ime, pot, vmesnik, metoda, parametri.unpack()))
        self.assertTrue(gostitelj.odpri_prek_portala("https://www.netflix.com/", True, vodilo=Vodilo()))
        self.assertEqual(klici, [("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
                                  "org.freedesktop.portal.OpenURI", "OpenURI",
                                  ("", "https://www.netflix.com/", {"ask": True}))])

    def test_rezervni_brskalnik_widevine_gre_portalu(self):
        from core import drm
        zagnano, portal = [], []
        p = drm.Preusmeritev(najdi=lambda: ("Brave", ["brave-browser"]), zazeni=zagnano.append,
                             peskovnik=lambda: True, portal=lambda url, vprasaj: portal.append((url, vprasaj)) or True)
        self.assertEqual(p.odpri("https://www.netflix.com/title/1"), ("portal", ""))
        self.assertEqual(zagnano, [])
        self.assertEqual(portal, [("https://www.netflix.com/title/1", True)])

    def test_zunanji_program_brez_gostitelja(self):
        """Splet: v peskovniku ne isce programa na gostitelju (os_odpri_z/gio) in ne uporabi os_dock (flatpak-spawn)."""
        vir = (KOREN / "core" / "os_splet.py").read_text(encoding="utf-8")
        i = vir.index("def _zunanji_program(")
        telo = vir[i:vir.index("def _kontekstni_meni", i)]
        self.assertIn("if _gost.v_peskovniku():", telo)
        self.assertLess(telo.index("if _gost.v_peskovniku():"), telo.index("os_odpri_z.program_za_shemo"))
        self.assertIn('os.environ.get("FLATPAK_ID") and _gost.sme_na_gostitelja()', telo)
        self.assertIn("self.Gtk.UriLauncher.new(uri).launch(", telo)
        self.assertIn("vir.launch_finish(izid)", telo)

    def test_privzeti_brskalnik_brez_gostitelja(self):
        from core import default_browser as d
        vir = (KOREN / "core" / "default_browser.py").read_text(encoding="utf-8")
        self.assertNotIn("flatpak-spawn", vir)
        self.assertNotIn("xdg-settings", vir.split("def set_default_browser", 1)[1].split("if os.environ.get(\"APPIMAGE\")")[0])
        with tempfile.TemporaryDirectory() as m:
            Path(m, "mimeapps.list").write_text("[Default Applications]\nx-scheme-handler/http=a.desktop;\n"
                                                "x-scheme-handler/https=a.desktop\n", encoding="utf-8")
            self.assertTrue(d.privzeti_v_flatpaku("a.desktop", mapa=m, okolje={}))
            self.assertFalse(d.privzeti_v_flatpaku("b.desktop", mapa=m, okolje={}))
            # Datoteka namizja ima prednost (specifikacija mime-apps).
            Path(m, "x-cinnamon-mimeapps.list").write_text("[Default Applications]\nx-scheme-handler/http=b.desktop\n",
                                                           encoding="utf-8")
            self.assertFalse(d.privzeti_v_flatpaku("a.desktop", mapa=m, okolje={"XDG_CURRENT_DESKTOP": "X-Cinnamon"}))
        with tempfile.TemporaryDirectory() as m:
            self.assertFalse(d.privzeti_v_flatpaku("a.desktop", mapa=m, okolje={}))   # ni datoteke: ne vemo
        with mock.patch.dict(os.environ, {"FLATPAK_ID": "io.github.memelandfaner.SafeerBrowser",
                                          "XDG_CURRENT_DESKTOP": "X-Cinnamon"}), \
                mock.patch.object(d, "is_default_browser", return_value=False):
            ok, sporocila = d.set_default_browser(str(KOREN), "sl")
        self.assertFalse(ok)
        self.assertEqual(sporocila, [d.NAVODILA["sl"]["cinnamon"]])

    def test_navodila_v_vseh_jezikih(self):
        from core import default_browser as d
        self.assertEqual(set(d.NAVODILA), {"sl", "en", "de", "es", "fr", "it"})
        for jezik, besedila in d.NAVODILA.items():
            self.assertEqual(set(besedila), {"cinnamon", "gnome", "kde", "xfce", "mate", "drugo"}, jezik)
            for b in besedila.values():
                self.assertIn("Safeer Browser", b)
        self.assertEqual(d.namizje({"XDG_CURRENT_DESKTOP": "X-Cinnamon"}), "cinnamon")
        self.assertEqual(d.namizje({"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}), "gnome")
        self.assertEqual(d.namizje({}), "drugo")

    def test_besedila_portala_v_vseh_jezikih(self):
        from core.i18n import TRANSLATIONS
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            for kljuc in ("external_app_portal_title", "external_app_portal_body", "external_app_portal_missing_body"):
                self.assertIn("{scheme}", TRANSLATIONS[jezik][kljuc], (jezik, kljuc))
            self.assertIn("{site}", TRANSLATIONS[jezik]["external_app_portal_body"])

    def test_zaganjalnik_in_vstop_brez_host_bin(self):
        for pot in ("packaging/safeer-launcher", "safeer_brskalnik.py"):
            vir = (KOREN / pot).read_text(encoding="utf-8")
            self.assertNotIn('PATH="/app/host-bin', vir, pot)
            self.assertNotIn('"/app/host-bin:"', vir, pot)

    def test_mapa_nastavitev_skupna_z_deb(self):
        """CONFIG_DIR iz SAFEER_MINT_CONFIG_DIR (Flatpak: ~/.config/safeer-mint racunalnika), sicer XDG_CONFIG_HOME."""
        import subprocess
        import sys
        with tempfile.TemporaryDirectory() as d:
            koda = "from core.config import CONFIG_DIR; print(CONFIG_DIR)"
            izhod = subprocess.check_output([sys.executable, "-c", koda], cwd=KOREN, text=True,
                                            env={**os.environ, "SAFEER_MINT_CONFIG_DIR": d + "/skupna",
                                                 "XDG_CONFIG_HOME": d + "/peskovnik"}).strip()
            self.assertEqual(izhod, d + "/skupna")


if __name__ == "__main__":
    unittest.main()
