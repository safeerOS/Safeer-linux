"""Uporabniske skripte v Spletu in GTK4 Safeer Browserju (core/splet_skripte.py) - del brez zaslona.

Ena shramba (core/uporabniske_skripte.py) in eno jedro (core/userscripts.py) za Splet in Medijski center; tu preverimo
pomen vzorcev (enak kot v WebKitu, izmerjeno z WebKitGTK 2.52 18. 10. 2026), notranje strani, shrambo GM_setValue,
selitev skript GTK3 brskalnika in besedila v vseh jezikih. Zivi del je v test_userscripts_splet_zivo.py."""
import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from core import uporabniske_skripte as us
from core import userscripts

KOREN = Path(__file__).resolve().parent.parent


def glava(*vrstice, ime="Preizkus"):
    return "// ==UserScript==\n// @name %s\n%s\n// ==/UserScript==\nwindow.x = 1;\n" % (
        ime, "\n".join("// " + v for v in vrstice))


class PomenVzorcev(unittest.TestCase):
    """userscripts.ujema = WebKitov UserContentURLPattern (tabela iz meritve z WebKitGTK 2.52)."""

    def test_kot_webkit(self):
        primeri = [
            ("*://127.0.0.1/*", "http://127.0.0.1:8080/", True),          # vrata naslova se ne upostevajo
            ("http://127.0.0.1/a*", "http://127.0.0.1:1/a?x=1", True),
            ("http://127.0.0.1/b", "http://127.0.0.1:1/b?q", True),         # poizvedba ni del poti
            ("http://127.0.0.1/a?x=1", "http://127.0.0.1:1/a?x=1", False),
            ("http://127.0.0.1/*x=1*", "http://127.0.0.1:1/z?x=1", False),
            ("*://*.localhost/*", "http://localhost:1/c", True),           # *.domena zajame tudi domeno
            ("http://*.0.0.1/*", "http://127.0.0.1:1/", True),
            ("http://127.0.0.*/*", "http://127.0.0.1:1/", False),          # zvezdica samo spredaj
            ("https://127.0.0.1/*", "http://127.0.0.1:1/", False),
            ("*://*/*", "https://example.com/x", True),
            ("*://*/*", "safeer://procesi", False),                         # »*« je samo http/https
            ("*://*/*", "about:blank", False),
            ("*://*/*", "file:///tmp/x.html", False),
            ("http://127.0.0.1:1/*", "http://127.0.0.1:1/", False),       # vzorec z vrati WebKit ne ujame
        ]
        for vzorec, naslov, pricakovano in primeri:
            with self.subTest(vzorec=vzorec, naslov=naslov):
                self.assertIs(userscripts.ujema(vzorec, naslov), pricakovano)

    def test_vzorec_z_vrati_velja_za_gostitelja(self):
        self.assertEqual(userscripts.vzorec_v_webkit("http://localhost:8080/app/*"), "http://localhost/app/*")
        self.assertEqual(userscripts.vzorec_v_webkit("*://*.example.com:443"), "*://*.example.com/*")

    def test_povsod_je_samo_splet_nikoli_notranje_strani(self):
        p = userscripts.pripravi({"id": "s", "code": glava("@match *://*/*")}, {}, str(KOREN))
        self.assertEqual(p["dovoljeni"], list(userscripts.VSE_SPLETNE_STRANI))      # nikoli None (= vse v WebKitu)
        domaca = (KOREN / "ui" / "splet.html").as_uri()
        for naslov in ("safeer://procesi", "safeer://home", domaca, "about:blank", "file:///etc/passwd"):
            self.assertFalse(userscripts.velja(p, naslov), naslov)
        self.assertTrue(userscripts.velja(p, "https://example.com/"))
        for vzorec in ("@include *", "@match <all_urls>", "@include http*://*/*"):
            self.assertEqual(userscripts.pripravi({"id": "s", "code": glava(vzorec)}, {}, str(KOREN))["dovoljeni"],
                             ["*://*/*"], vzorec)
        # file:// in druge sheme glava ne more izbrati
        self.assertEqual(userscripts.pripravi({"id": "s", "code": glava("@match file:///*")}, {}, str(KOREN))["napaka"],
                         "ni_veljavnega_vzorca")

    def test_izjeme_in_dovoljenja(self):
        p = userscripts.pripravi({"id": "s", "code": glava("@match https://*.example.com/*",
                                                           "@exclude https://example.com/prijava*")}, {}, str(KOREN))
        self.assertTrue(userscripts.velja(p, "https://www.example.com/x"))
        self.assertFalse(userscripts.velja(p, "https://example.com/prijava/1"))
        self.assertFalse(userscripts.velja(p, "https://example.org/"))
        p = userscripts.pripravi({"id": "s", "code": glava("@match *://*/*", "@grant GM_xmlhttpRequest")}, {}, str(KOREN))
        self.assertEqual((p["napaka"], p["manjka"]), ("manjkajoca_dovoljenja", ["GM_xmlhttpRequest"]))
        self.assertFalse(userscripts.velja(p, "https://example.com/"))


class Shramba(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="skripte-splet-")
        self.stari = os.environ.get("SAFEER_SKRIPTE_MAPA")
        os.environ["SAFEER_SKRIPTE_MAPA"] = self.mapa

    def tearDown(self):
        if self.stari is None:
            os.environ.pop("SAFEER_SKRIPTE_MAPA", None)
        else:
            os.environ["SAFEER_SKRIPTE_MAPA"] = self.stari
        shutil.rmtree(self.mapa, ignore_errors=True)

    def dodaj(self, koda, vklop=True, ime="s.js"):
        s = us.uvozi(ime, koda, "js")["skripta"]
        if vklop:
            us.vklopi(s["id"], True)
        return s["id"]

    def test_kje_tece_po_glavi(self):
        brez = self.dodaj("window.spotify = 1;")
        yt = self.dodaj(glava("@match https://www.youtube.com/*", ime="YT"))
        vse = self.dodaj(glava("@match *://*/*", ime="Vse"))
        ne = self.dodaj(glava("@match *://*/*", "@grant GM_xmlhttpRequest", ime="Ne"))
        kje = {s["id"]: s["kje"] for s in us.skripte_js(str(KOREN))}
        self.assertEqual(kje, {brez: "spotify", yt: "splet", vse: "oboje", ne: "ne"})
        self.assertEqual({s["id"]: s.get("kje") for s in us.seznam()}, kje)     # Medijski center pove isto
        naslovi = {s["id"]: s["naslov"] for s in us.skripte_js(str(KOREN))}
        self.assertEqual((naslovi[yt], naslovi[brez]), ("YT", "s.js"))
        for s in us.skripte_js(str(KOREN)):
            self.assertTrue(os.path.isabs(s["pot"]) and "~" not in s["pot"], s["pot"])     # celotna pot

    def test_spotify_dobi_samo_svoje_skripte(self):
        self.dodaj("window.spotify = 1;", ime="star.js")
        self.dodaj(glava("@match https://www.youtube.com/*", ime="YT"), ime="yt.js")
        self.dodaj(glava("@match https://open.spotify.com/*", "@grant GM_addStyle", ime="Sp"), ime="sp.js")
        aktivne = us.aktivne_js()
        self.assertEqual([a["ime"] for a in aktivne], ["star.js", "sp.js"])       # skripta za YouTube ne
        self.assertEqual(aktivne[0]["koda"], "window.spotify = 1;")               # brez glave nespremenjena
        self.assertIn("const GM_addStyle", aktivne[1]["koda"])                    # z glavo dobi svoje funkcije GM_
        self.assertIn("DOMContentLoaded", aktivne[1]["koda"])                     # @run-at document-end

    def test_vrednosti_samo_za_vklopljeno_skripto_v_mejah(self):
        sid = self.dodaj(glava("@match *://*/*", "@grant GM_setValue"))
        izklopljena = self.dodaj(glava("@match *://*/*"), vklop=False)
        self.assertTrue(us.shrani_vrednost(sid, "barva", "modra"))
        self.assertEqual(us.vrednosti(sid), {"barva": "modra"})
        self.assertFalse(us.shrani_vrednost(izklopljena, "x", 1))
        self.assertFalse(us.shrani_vrednost("0" * 12, "x", 1))
        self.assertFalse(us.shrani_vrednost("../kazalo", "x", 1))
        self.assertFalse(us.shrani_vrednost(sid, "", 1))
        self.assertFalse(us.shrani_vrednost(sid, "velika", "x" * (us.NAJVEC_BAJTOV_VREDNOSTI + 1)))
        for i in range(us.NAJVEC_KLJUCEV - 1):
            self.assertTrue(us.shrani_vrednost(sid, "k%d" % i, i))
        self.assertFalse(us.shrani_vrednost(sid, "cez", 1))
        self.assertTrue(us.shrani_vrednost(sid, "k0", 42))                      # obstojeci kljuc se sme prepisati
        pot = Path(self.mapa) / ("%s.vrednosti.json" % sid)
        self.assertEqual(oct(pot.stat().st_mode & 0o777), "0o600")
        self.assertTrue(us.izbrisi_vrednost(sid, "barva"))
        self.assertNotIn("barva", us.vrednosti(sid))
        self.assertIn('"k0": 42', us.pripravi({"id": sid}, us._koda({"id": sid, "vrsta": "js"}))["vir"])
        us.odstrani(sid)
        self.assertFalse(pot.exists())

    def test_poslusalec_spremembe(self):
        klici = []

        class Splet:
            def ob(self):
                klici.append(1)
        splet = Splet()
        us.ob_spremembi(splet.ob)
        sid = self.dodaj(glava("@match *://*/*"))                  # uvoz + vklop
        us.posodobi(sid, glava("@match https://example.com/*"))
        us.odstrani(sid)
        self.assertEqual(len(klici), 4)
        del splet                                                  # sibka referenca: zaprt Splet ne ostane
        self.dodaj("x = 1;")
        self.assertEqual(len(klici), 4)

    def test_selitev_iz_gtk3_brskalnika(self):
        class Nastavitve(dict):
            def set(self, k, v):
                self[k] = v
        c = Nastavitve(user_scripts=[
            {"id": "sample_banner_cleaner", "name": "Primer", "pattern": "*", "code": "console.log(1)", "enabled": True},
            {"id": "script_aa", "name": "Stara\n// @match evil", "pattern": "example.com", "code": "window.a = 1;",
             "enabled": True, "run_at": "start"},
            {"id": "script_bb", "name": "Z glavo", "pattern": "*", "enabled": False,
             "code": glava("@match https://www.example.org/*", "@grant GM_getValue", ime="Z glavo")},
        ], user_script_values={"script_aa": {"stevec": 3}})
        self.assertEqual(us.preseli_iz_nastavitev(c), 2)
        self.assertTrue((Path(self.mapa) / "preseljeno-gtk3").exists())         # oznaka v shrambi, ne v nastavitvah
        self.assertNotIn("user_scripts_preseljene", c)                      # nastavitev ne spremeni
        self.assertEqual(us.preseli_iz_nastavitev(c), 0)                       # samo enkrat v to shrambo
        skripte = {s["naslov"]: s for s in us.skripte_js(str(KOREN))}
        self.assertEqual(sorted(skripte), ["Stara // @match evil", "Z glavo"])  # vzorcna se ne seli
        stara = skripte["Stara // @match evil"]
        self.assertTrue(stara["vklopljena"])
        self.assertEqual(stara["pripravljeno"]["dovoljeni"], ["*://*.example.com/*"])
        self.assertEqual(stara["pripravljeno"]["run_at"], "document-start")
        self.assertEqual(stara["pripravljeno"]["glava"]["matches"], ["example.com"])   # ime ni ubezalo v glavo
        self.assertEqual(us.vrednosti(stara["id"]), {"stevec": 3})
        self.assertFalse(skripte["Z glavo"]["vklopljena"])

    def test_brez_skript_za_selitev_se_shramba_ne_oznaci(self):
        class Nastavitve(dict):
            def set(self, k, v):
                self[k] = v
        prazne = Nastavitve(user_scripts=[{"id": "sample_banner_cleaner", "code": "x", "name": "Primer"}])
        self.assertEqual(us.preseli_iz_nastavitev(prazne), 0)
        self.assertFalse((Path(self.mapa) / "preseljeno-gtk3").exists())
        self.assertEqual(us.preseli_iz_nastavitev(None), 0)


class Vgradnja(unittest.TestCase):
    """Splet: svoj svet, besedila v vseh jezikih, barve iz tokenov, oznaka in vnos menija."""

    def test_svet_je_samo_za_skripte(self):
        from core import adblock, drm, odlozisce_varuh, splet_skripte, splet_temno
        self.assertEqual(splet_skripte.SVET, "safeer-userscripts")
        self.assertNotIn(splet_skripte.SVET, (adblock.STEVEC_SVET, drm.SVET, splet_temno.SVET, odlozisce_varuh.SVET,
                                              None, ""))
        self.assertNotIn(splet_skripte.MOST, ("safeer", adblock.STEVEC_MOST, drm.MOST, "safeerLink"))

    def test_besedila_v_vseh_jezikih_brez_tujih_imen_in_tilde(self):
        from core import splet_skripte
        from core.os_splet import BESEDILA, JEZIKI
        self.assertEqual(tuple(splet_skripte.BESEDILA), JEZIKI)
        kljuci = set(splet_skripte.BESEDILA["sl"])
        for j, b in splet_skripte.BESEDILA.items():
            self.assertEqual(set(b), kljuci, j)
            for k, v in b.items():
                self.assertNotRegex(v, r"(?i)tampermonkey|greasemonkey|violentmonkey", (j, k))
                self.assertNotIn("~", v, (j, k))
                # vsako polje {x} iz slovenscine je tudi v prevodu
                self.assertEqual(set(re.findall(r"\{(\w+)\}", v)),
                                 set(re.findall(r"\{(\w+)\}", splet_skripte.BESEDILA["sl"][k])), (j, k))
            self.assertEqual(BESEDILA[j]["skripte"], b["meni"])       # vnos menija Spleta

    def test_barve_samo_iz_tokenov(self):
        from core import os_lupina, splet_skripte
        css = splet_skripte.css(os_lupina.tokeni())
        self.assertIn("." + splet_skripte.RAZRED_ZNAKA, css)
        self.assertNotRegex(css, r"#[0-9a-fA-F]{3,8}\b")
        self.assertEqual(splet_skripte.css({}), "")
        vir = (KOREN / "core" / "splet_skripte.py").read_text(encoding="utf-8")
        self.assertNotRegex(vir, r"#[0-9a-fA-F]{6}\b")

    def test_os_splet_vgradi_v_zavihke_ne_v_aplikacije(self):
        vir = (KOREN / "core" / "os_splet.py").read_text(encoding="utf-8")
        self.assertIn('if not aplikacija and getattr(self, "skripte", None) is not None:\n'
                      '            self.skripte.namesti(pogled)', vir)
        self.assertIn("self.skripte.osvezi_znak(pogled)", vir)
        self.assertIn('("skripte", "skripte")', vir)
        self.assertIn('"skripte": lambda: self.skripte.pokazi()', vir)
        tovor = (KOREN / "packaging" / "install_os_payload.sh").read_text(encoding="utf-8")
        for modul in ("splet_skripte", "userscripts", "uporabniske_skripte"):
            self.assertRegex(tovor, r"\s%s\s" % modul)

    def test_opis_skripte_po_resnici(self):
        from core import splet_skripte
        p = userscripts.pripravi({"id": "s", "code": glava("@match *://*/*", "@exclude https://bank.example/*")}, {},
                                 str(KOREN))
        opis = splet_skripte.opis_skripte("sl", {"pripravljeno": p, "kje": "oboje"})
        self.assertIn("vseh spletnih straneh", opis)
        self.assertIn("https://bank.example/*", opis)
        self.assertIn("Spotify", opis)
        p = userscripts.pripravi({"id": "s", "code": glava("@match *://*/*", "@grant GM_download")}, {}, str(KOREN))
        self.assertIn("GM_download", splet_skripte.opis_skripte("en", {"pripravljeno": p, "kje": "ne"}))


if __name__ == "__main__":
    unittest.main()
