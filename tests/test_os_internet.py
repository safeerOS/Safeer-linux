"""Safeer OS: plosca »Internet prek telefona« (Omrezne povezave) in njen most do Safeer Controla.

Stran sme nastaviti samo nacin, telefon, pot in sistemski posrednik; zaradi prikaza stanja Controla ne
zaganjamo. Besedila morajo obstajati za vse, kar plosca sestavi iz kode (nacini, dovoljenja, poti, razlogi).
"""
import json
import os
import re
import unittest
from unittest import mock

from core import link_internet

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


def _besedila():
    """jezik -> {kljuc: besedilo} iz vrstic, ki jih doda outputs/krog102/linux102_besedila.py."""
    izid = {}
    for jezik, telo in re.findall(r"/\*internet102\*/Object\.assign\(BESEDILA_OS\.(\w+), (\{.*\})\);", _beri("assets", "os", "besedila.js")):
        izid[jezik] = json.loads(telo)
    return izid


class Most(unittest.TestCase):
    def setUp(self):
        import safeer_os
        self.os = safeer_os

    def test_nastavitve_gredo_precisceno_v_control(self):
        klici = []

        def control(metoda, *argumenti):
            klici.append((metoda,) + argumenti)
            return {"ok": True, "nacin": "izpad"}

        with mock.patch.object(self.os, "_control_naprave", side_effect=control):
            izid = self.os.internet_prek_telefona("nastavi", {"nacin": "izpad", "naprava": "n-" + "a" * 200, "sistemski": True,
                                                              "pot": 7, "vrata": 22, "stari_ponudniki": True, "ukaz": "rm"})
        self.assertEqual(izid, {"ok": True, "nacin": "izpad"})
        self.assertEqual(len(klici), 1)
        self.assertEqual(klici[0][:2], ("Internet", "nastavi"))
        poslano = json.loads(klici[0][2])
        self.assertEqual(sorted(poslano), ["nacin", "naprava", "sistemski"])
        self.assertEqual(poslano["nacin"], "izpad")
        self.assertIs(poslano["sistemski"], True)
        self.assertEqual(len(poslano["naprava"]), 96, "predolg id se odreze")

    def test_sistemski_mora_biti_logicna_vrednost(self):
        with mock.patch.object(self.os, "_control_naprave", return_value={"ok": True}) as control:
            self.os.internet_prek_telefona("nastavi", {"sistemski": "da"})
        self.assertEqual(json.loads(control.call_args[0][2]), {})

    def test_stanje_ne_zazene_controla(self):
        with mock.patch.object(self.os.Gio, "bus_get_sync", return_value=object()), \
                mock.patch.object(self.os, "_control_na_vodilu", return_value=False), \
                mock.patch.object(self.os, "_control_naprave", side_effect=AssertionError("Control se ne sme zagnati")):
            self.assertEqual(self.os.internet_prek_telefona("stanje", {"vprasaj": True}, zazeni=False),
                             {"ok": False, "koda": "ni_controla"})

    def test_stanje_ko_control_tece(self):
        with mock.patch.object(self.os.Gio, "bus_get_sync", return_value=object()), \
                mock.patch.object(self.os, "_control_na_vodilu", return_value=True), \
                mock.patch.object(self.os, "_control_naprave", return_value={"ok": True, "nacin": "vedno"}) as control:
            self.assertEqual(self.os.internet_prek_telefona("stanje", {"vprasaj": 1}, zazeni=False)["nacin"], "vedno")
        self.assertEqual(control.call_args[0], ("Internet", "stanje", '{"vprasaj": true}'))

    def test_neznan_ukaz_ne_gre_naprej(self):
        with mock.patch.object(self.os, "_control_naprave", side_effect=AssertionError("ne sme do Controla")):
            self.assertEqual(self.os.internet_prek_telefona("okolje"), {"ok": False, "koda": "napacna_zahteva"})
            self.assertEqual(self.os.internet_prek_telefona("izbrisi", {"x": 1})["koda"], "napacna_zahteva")

    def test_metode_mosta_so_prijavljene(self):
        os_py = _beri("safeer_os.py")
        js = _beri("assets", "os", "os.js")
        for metoda in ("internetStanje", "internetNastavi", "internetPreizkus"):
            self.assertIn('"%s": lambda' % metoda, os_py, metoda)
            self.assertIn('klic("%s"' % metoda, js, metoda)
        self.assertIn('"internetStanje": lambda: internet_prek_telefona("stanje", {"vprasaj": bool(a[0]) if a else False}, zazeni=False)',
                      os_py, "prikaz stanja ne sme zaganjati Controla")


class Plosca(unittest.TestCase):
    def test_plosca_je_v_omreznih_povezavah(self):
        html = _beri("assets", "os", "index.html")
        omrezje = html.split('id="r-omrezje"', 1)[1].split("</section>", 1)[0]
        for oznaka in ("blokInternet", "internetNacin", "internetNamig", "internetVrstice", "internetStikala",
                       "gumbInternetPreizkus", "internetIzid"):
            self.assertIn('id="%s"' % oznaka, omrezje, oznaka)
        js = _beri("assets", "os", "os.js")
        self.assertIn('if (razdelek === "omrezje") { nalozOmrezje(false); nalozInternet(false); internetZanka(); }', js)

    def test_besedila_za_vse_kar_plosca_sestavi(self):
        b = _besedila()
        self.assertEqual(sorted(b), ["de", "en", "es", "fr", "it", "sl"])
        js = _beri("assets", "os", "os.js")
        sestavljeni = (["intNacin_" + n for n in ("izklopljeno", "izpad", "vedno")]
                       + ["intNacinPod_" + n for n in ("izklopljeno", "izpad", "vedno")]
                       + ["intDov_" + d for d in ("allowed", "pending", "denied", "not_trusted", "disabled", "caka", "stari")]
                       + ["intZdaj_" + z for z in ("telefon", "doma", "brez", "ne")]
                       + ["intPot_" + p for p in ("cellular", "wifi", "ethernet", "vpn", "other")])
        for jezik, slovar in b.items():
            self.assertEqual(sorted(slovar), sorted(b["sl"]), jezik)
            for kljuc in sestavljeni:
                self.assertTrue(slovar.get(kljuc), "%s: %s" % (jezik, kljuc))
            for kljuc, besedilo in slovar.items():
                self.assertEqual(sorted(re.findall(r"\{[a-z]+\}", besedilo)), sorted(re.findall(r"\{[a-z]+\}", b["sl"][kljuc])),
                                 "%s: %s ima druge spremenljivke" % (jezik, kljuc))
        # Vsak dobesedni kljuc »int...« v kodi obstaja.
        for kljuc in set(re.findall(r'\bt\("(int[A-Za-z_]+)"\s*[,)]', js)):
            self.assertTrue(kljuc in b["sl"], kljuc)

    def test_razlogi_ponudnika_imajo_besedilo(self):
        """Razlog, ki ga lahko vrne preizkus (telefon ali Control), mora uporabniku nekaj povedati - ne kode."""
        sl = _besedila()["sl"]
        uporabniku = ("disabled", "permission_required", "denied", "not_trusted", "no_path", "mobile_off", "no_mobile",
                      "roaming", "limit", "busy", "dns_failed", "connect_failed", "timeout", "link", "old_provider")
        for razlog in uporabniku:
            self.assertIn(razlog, link_internet.RAZLOGI)
            self.assertTrue("intRazlog_" + razlog in sl, razlog)
        for koda in ("ni_telefona", "ni_controla", "stari_control", "napaka"):
            self.assertTrue("intRazlog_" + koda in sl, koda)
        js = _beri("assets", "os", "os.js")
        self.assertIn('t(k) === k ? t("intRazlog_napaka") : t(k)', js, "neznan razlog dobi splosno besedilo, ne kode")


if __name__ == "__main__":
    unittest.main()
