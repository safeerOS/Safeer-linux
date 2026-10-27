"""Razsirjeni katalog storitev Sporocil (core/katalog_storitev.py, core/ferdium_katalog/) in splosna pravila za stevilo
neprebranih iz naslova (core/spletni_klepeti.neprebrano). Samo podatki iz ferdium-recipes (MIT), brez kode receptov
(ROADMAP.md: »brez receptov za posamezne strani«). Brez GTK in brez omrezja."""
import base64
import importlib
import json
import os
import re
import shutil
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAPA = os.path.join(KOREN, "core", "ferdium_katalog")

from core import spletni_klepeti  # noqa: E402


def _ks():
    # Uvoz v preizkusu (ne na vrhu): brez modula pade vsak preizkus posebej, ne zbiranje datoteke.
    return importlib.import_module("core.katalog_storitev")


class _Shramba(dict):
    def set(self, kljuc, vrednost):
        self[kljuc] = vrednost


class Podatki(unittest.TestCase):
    def test_datoteka_in_licenca(self):
        with open(os.path.join(MAPA, "katalog-sporocila.json"), encoding="utf-8") as f:
            k = json.load(f)
        with open(os.path.join(MAPA, "LICENSE"), encoding="utf-8") as f:
            licenca = f.read()
        self.assertIn("MIT License", licenca)
        self.assertIn("Copyright (c) 2022 Ferdium Contributors", licenca)
        self.assertEqual(k["vir"]["licenca"], "MIT")
        self.assertIn(k["vir"]["licenca_besedilo"], licenca)
        self.assertRegex(k["vir"]["commit"], r"^[0-9a-f]{40}$")
        for v in k["katalog"]:
            self.assertEqual(list(v)[:5], ["id", "ime", "vrsta", "splet", "prenos"], v["id"])
            self.assertEqual(v["vir"]["licenca"], "MIT", v["id"])
            self.assertEqual(v["vir"]["commit"], k["vir"]["commit"], v["id"])
            self.assertTrue(v["vir"]["povezava"].endswith("/tree/%s/recipes/%s" % (k["vir"]["commit"], v["id"])))

    def test_brez_kode_receptov(self):
        with open(os.path.join(MAPA, "katalog-sporocila.json"), encoding="utf-8") as f:
            besedilo = f.read()
        for koda in ("setBadge", "module.exports", "Ferdium.loop", "injectCSS", "<script"):
            self.assertNotIn(koda, besedilo)

    def test_nalozi_preverjene_vnose(self):
        ks = _ks()
        vnosi = ks.nalozi()
        self.assertGreaterEqual(len(vnosi), 80)
        self.assertEqual(len({v["id"] for v in vnosi}), len(vnosi))
        for v in vnosi:
            self.assertIn(v["vrsta"], ks.VRSTE)
            self.assertEqual(spletni_klepeti.preveri_naslov(v["splet"]), v["splet"])
            self.assertFalse(v["izmerjeno"])
            if v["ikona_svg"]:
                self.assertEqual(ks.varna_svg.ocisti(v["ikona_svg"]), v["ikona_svg"])
        ai = {v["id"] for v in vnosi if v["vrsta"] == ks.AI}
        self.assertTrue({"chatgpt", "claude-ai", "google-gemini", "perplexity", "mistral"} <= ai, ai)

    def test_izmerjeni_katalog_ostane_vir_resnice(self):
        ks = _ks()
        izmerjeni = {k["id"] for k in spletni_klepeti.KATALOG}
        for v in ks.dodatni():
            self.assertNotIn(v["id"], izmerjeni)
        # Carovnik (za_vmesnik) kaze samo izmerjeni katalog - kdaj pokazati neizmerjene, odloci lastnik.
        self.assertEqual([v["id"] for v in spletni_klepeti.za_vmesnik("sl")], [k["id"] for k in spletni_klepeti.KATALOG])
        self.assertIs(spletni_klepeti.po_id("telegram"), next(k for k in spletni_klepeti.KATALOG if k["id"] == "telegram"))
        povezani = {v["obstojeci"] for v in ks.nalozi() if v["obstojeci"]}
        self.assertTrue({"telegram", "gmail", "google-messages"} <= povezani, povezani)


class Uporaba(unittest.TestCase):
    def test_kanal_iz_razsirjenega_kataloga(self):
        _ks()
        vnos = spletni_klepeti.po_id("claude-ai")
        self.assertIsNotNone(vnos)
        self.assertEqual(vnos["vrsta"], "ai")
        self.assertTrue(spletni_klepeti.vdelljiv(vnos))
        kanali = spletni_klepeti.Kanali(_Shramba())
        k = kanali.dodaj(katalog="claude-ai")
        self.assertEqual((k["id"], k["url"], k["caka"]), ("claude-ai", vnos["splet"], True))
        self.assertEqual(kanali.seznam()[0]["katalog"], "claude-ai")
        with self.assertRaises(ValueError):
            kanali.dodaj(katalog="ni-takega-recepta")

    def test_ikona_kot_data_url(self):
        ks = _ks()
        for kid in ("telegram", "chatgpt"):
            url = ks.ikona(kid)
            self.assertTrue(url.startswith("data:image/svg+xml;base64,"), kid)
            svg = base64.b64decode(url.split(",", 1)[1]).decode("utf-8")
            self.assertTrue(svg.startswith("<svg"), kid)
        self.assertEqual(ks.ikona(""), "")
        self.assertEqual(ks.ikona("ni-takega"), "")

    def test_katalog_carovnika_ima_ikone_brez_omrezja(self):
        ks = _ks()
        from core import ikone_strani, os_kanali_sporocil
        mapa = tempfile.mkdtemp(prefix="safeer-ikone-")
        prej, ikone_strani.MAPA = ikone_strani.MAPA, mapa
        prenos = ikone_strani.ikona_strani
        ikone_strani.ikona_strani = lambda *_a, **_k: self.fail("katalog ne sme klicati strani")
        try:
            ks_ = os_kanali_sporocil.KanaliSporocil(None, None, None, lambda: None, _Shramba(), lambda: "sl",
                                                    lambda *_a: None, lambda *_a: None, obvestila=object())
            po_id = {v["id"]: v for v in ks_.katalog()}
        finally:
            ikone_strani.MAPA, ikone_strani.ikona_strani = prej, prenos
            shutil.rmtree(mapa, ignore_errors=True)
        self.assertEqual(po_id["telegram"]["ikona"], ks.ikona("telegram"))
        self.assertTrue(po_id["gmail"]["ikona"].startswith("data:image/svg+xml;base64,"))

    def test_pokvarjena_ali_manjkajoca_datoteka(self):
        ks = _ks()
        self.assertEqual(ks.nalozi(os.path.join(tempfile.gettempdir(), "ni-kataloga-%d.json" % os.getpid())), [])
        with open(os.path.join(MAPA, "katalog-sporocila.json"), encoding="utf-8") as f:
            k = json.load(f)
        zlo = '<svg xmlns="http://www.w3.org/2000/svg" onload="x()"><script>x()</script></svg>'
        k["katalog"] = [dict(k["katalog"][0], id="a", ikona_svg=zlo),
                        dict(k["katalog"][0], id="b", splet="javascript:alert(1)"),
                        dict(k["katalog"][0], id="c", vrsta="drugo"),
                        dict(k["katalog"][0], id="d", vir={"licenca": "GPL-3.0"}),
                        dict(k["katalog"][0], id="../e"),
                        dict(k["katalog"][0], id="f", obstojeci="")]
        with tempfile.TemporaryDirectory() as d:
            pot = os.path.join(d, "k.json")
            with open(pot, "w", encoding="utf-8") as f:
                json.dump(k, f)
            vnosi = {v["id"]: v for v in ks.nalozi(pot)}
            self.assertEqual(set(vnosi), {"a", "f"})
            self.assertEqual(vnosi["a"]["ikona_svg"], "")          # ikona, ki ni ze ociscena, se zavrne
            with open(pot, "w", encoding="utf-8") as f:
                f.write("{ni json")
            self.assertEqual(ks.nalozi(pot), [])
            with open(pot, "w", encoding="utf-8") as f:
                json.dump(dict(k, vir=dict(k["vir"], licenca="GPL-3.0")), f)
            self.assertEqual(ks.nalozi(pot), [])

    def test_v_tovoru(self):
        for skripta in ("install_os_payload.sh", "install_control_payload.sh"):
            with open(os.path.join(KOREN, "packaging", skripta), encoding="utf-8") as f:
                s = f.read()
            moduli = set(re.search(r"for modul in (.*?); do", s, re.S).group(1).replace("\\\n", " ").split())
            self.assertTrue({"katalog_storitev", "varna_svg"} <= moduli, skripta)
            self.assertIn('"$ROOT"/core/ferdium_katalog/katalog-sporocila.json "$ROOT"/core/ferdium_katalog/LICENSE', s)


class Neprebrano(unittest.TestCase):
    """Splosna pravila (brez znanja o storitvi), oblike iz naslovov, ki jih berejo recepti ferdium-recipes:
    freshrss (trdi presledek v stevilu), reddit-chat »(*)«, rocketchat oklepaj brez stevila."""

    def test_tisocice(self):
        n = spletni_klepeti.neprebrano
        self.assertEqual(n("(1 234) Novice"), 1234)
        self.assertEqual(n("(1\u00a0234) FreshRSS"), 1234)
        self.assertEqual(n("[1.234] Element"), 1234)
        self.assertEqual(n("(12,345) Posta"), 9999)
        self.assertEqual(n("Prejeto (1 234) - ime@primer - Posta"), 1234)
        self.assertEqual(n("Inbox (2\u202f500) | Posta"), 2500)

    def test_oklepaj_z_oznako(self):
        n = spletni_klepeti.neprebrano
        self.assertEqual(n("(•) Rocket.Chat"), 1)
        self.assertEqual(n("(*) Klepet"), 1)
        self.assertEqual(n("[!] Kanal"), 1)

    def test_obstojeca_pravila_ostanejo(self):
        n = spletni_klepeti.neprebrano
        self.assertEqual(n("Srečanje (2026) - Teams"), 0)
        self.assertEqual(n("(123456) X"), 0)
        self.assertEqual(n("(99999) X"), 9999)
        self.assertEqual(n("Klepet | (3)"), 0)
        self.assertEqual(n("(1,5) Ocena"), 0)
        self.assertEqual(n("Cena (1.99) - Trgovina"), 0)


if __name__ == "__main__":
    unittest.main()
