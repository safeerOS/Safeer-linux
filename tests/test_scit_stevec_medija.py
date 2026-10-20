"""Stevec Scita (blokirani oglasi) je stel premalo (odprta tocka pregleda 1.0.128).

1. Medijski center (YouTube v vgradnem predvajalniku, safeer_os._ustvari_medijski_pogled) ima isto skripto
   YOUTUBE_ADBLOCK_SCRIPT kot Splet. Ta tece v glavnem svetu in odstranjene oglase javi z dogodkom DOM; bere ga samo
   rele z mostom v locenem svetu (core/os_splet.namesti_stevec). Medijski pogled releja in mostu ni imel - stetje se je
   izgubilo.
2. Stevec v settings.json stejeta Safeer OS in Safeer Browser: povecanje iz stare kopije v pomnilniku je prepisalo
   povecanja drugega procesa (zdruzevanje po kljucih vzame nas kljuc v celoti).

Brez GTK 4 in WebKita: metode SafeerOS in namesti_stevec se preberejo iz vira (ast), WebKit je lazen.
"""
import ast
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from core import adblock, config

KOREN = Path(__file__).resolve().parents[1]


def _funkcije(pot, *imena, razred=None):
    drevo = ast.parse((KOREN / pot).read_text(encoding="utf-8"))
    telo = drevo.body
    if razred:
        telo = next(n for n in telo if isinstance(n, ast.ClassDef) and n.name == razred).body
    izid = [n for n in telo if isinstance(n, ast.FunctionDef) and n.name in imena]
    assert {n.name for n in izid} == set(imena), set(imena) - {n.name for n in izid}
    return izid


def _izvedi(funkcije, imenski):
    exec(compile(ast.Module(body=funkcije, type_ignores=[]), "vir", "exec"), imenski)  # noqa: S102 - koda repozitorija
    return imenski


class _Upravitelj:
    """Lazni WebKit.UserContentManager: zapomni si mostove (ime, svet), povezave signalov in skripte."""

    def __init__(self):
        self.mostovi, self.signali, self.skripte = [], {}, []

    def register_script_message_handler(self, ime, svet=None):
        self.mostovi.append((ime, svet))

    def connect(self, signal, klic):
        self.signali[signal] = klic

    def add_script(self, skripta):
        self.skripte.append(skripta)


class _JS:
    def __init__(self, vrednost):
        self.vrednost = vrednost

    def to_json(self, _zamik):
        return json.dumps(self.vrednost)


class _Profil(unittest.TestCase):
    def setUp(self):
        mapa = tempfile.TemporaryDirectory()
        self.addCleanup(mapa.cleanup)
        self.pot = Path(mapa.name) / "settings.json"
        for ime, vrednost in (("CONFIG_DIR", mapa.name), ("CONFIG_FILE", str(self.pot))):
            p = mock.patch.object(config, ime, vrednost)
            p.start()
            self.addCleanup(p.stop)

    def na_disku(self, kljuc):
        return json.loads(self.pot.read_text(encoding="utf-8")).get(kljuc)


class StevecDvehProcesov(_Profil):
    def test_povecanja_obeh_procesov_ostanejo(self):
        safeer_os = config.ConfigManager()
        brskalnik = config.ConfigManager()        # odprt prej: v pomnilniku ima se 0
        safeer_os.increment_ads_blocked(3)
        brskalnik.increment_ads_blocked(2)
        safeer_os.increment_threats_blocked(1)
        brskalnik.increment_threats_blocked(4)
        self.assertEqual(self.na_disku("total_ads_blocked"), 5)
        self.assertEqual(self.na_disku("total_threats_blocked"), 5)
        self.assertEqual(brskalnik.get("total_ads_blocked"), 5)

    def test_neveljavno_stevilo_ne_spremeni(self):
        c = config.ConfigManager()
        c.increment_ads_blocked(2)
        c.increment_ads_blocked(0)
        c.increment_ads_blocked("x")
        self.assertEqual(self.na_disku("total_ads_blocked"), 2)

    def test_pokvarjena_vrednost_na_disku(self):
        c = config.ConfigManager()
        c.set("total_ads_blocked", 1)
        besedilo = json.loads(self.pot.read_text(encoding="utf-8"))
        besedilo["total_ads_blocked"] = "ni stevilo"
        self.pot.write_text(json.dumps(besedilo), encoding="utf-8")
        c.increment_ads_blocked(2)
        self.assertEqual(self.na_disku("total_ads_blocked"), 2)


class MedijskiPogledSteje(_Profil):
    def setUp(self):
        super().setUp()
        # Pravi namesti_stevec in registriraj_most iz core/os_splet.py (modul sam potrebuje libsoup).
        os_splet = types.ModuleType("core.os_splet")
        imena = _izvedi(_funkcije("core/os_splet.py", "registriraj_most", "namesti_stevec"), {"adblock": adblock})
        for ime in ("registriraj_most", "namesti_stevec"):
            setattr(os_splet, ime, imena[ime])
        p = mock.patch.dict(sys.modules, {"core.os_splet": os_splet})
        p.start()
        self.addCleanup(p.stop)
        self.upravitelj = _Upravitelj()
        WebKit2 = mock.MagicMock()
        WebKit2.UserContentManager.return_value = self.upravitelj
        WebKit2.UserScript.new_for_world = lambda vir, *a: ("svet", vir, a)
        imenski = _izvedi(_funkcije("safeer_os.py", "_ustvari_medijski_pogled", "_stevec_medija", razred="SafeerOS"),
                          {"WebKit2": WebKit2, "Gtk": mock.MagicMock(), "json": json,
                           "namesti_most_skladbe": mock.MagicMock(), "odlozisce_varuh": mock.MagicMock(),
                           "os_medijska_plast": mock.MagicMock()})
        self.config = config.ConfigManager()
        L = type("Lazni", (), {"_ustvari_medijski_pogled": imenski["_ustvari_medijski_pogled"],
                               "_stevec_medija": imenski["_stevec_medija"]})
        self.os = L()
        for ime in ("_dogodek", "_na_stanje_skladbe", "_medijski_odlocitev", "_sledilci_v_pogled", "_medijski_nalozen",
                    "_mb", "_medijska_plast_nazaj", "_medijska_plast_css", "_vgrajeno_filter"):
            setattr(self.os, ime, mock.MagicMock())
        self.os._medijski_pogled = None
        self.os._peskovnik_na_voljo = lambda: True
        self.os._config_spleta = lambda: self.config

    def test_most_in_rele_v_locenem_svetu(self):
        self.assertTrue(self.os._ustvari_medijski_pogled())
        self.assertIn((adblock.STEVEC_MOST, adblock.STEVEC_SVET), self.upravitelj.mostovi)
        self.assertNotIn((adblock.STEVEC_MOST, None), self.upravitelj.mostovi)
        rele = [s for s in self.upravitelj.skripte if isinstance(s, tuple) and s[1] == adblock.STEVEC_RELE_SCRIPT]
        self.assertEqual(len(rele), 1)
        self.assertIn(adblock.STEVEC_SVET, rele[0][2])

    def test_sporocilo_releja_poveca_stevec_spleta(self):
        self.os._ustvari_medijski_pogled()
        klic = self.upravitelj.signali["script-message-received::" + adblock.STEVEC_MOST]
        klic(self.upravitelj, _JS({"action": "increment_ads", "count": 3}))
        klic(self.upravitelj, _JS({"action": "increment_ads", "count": 1000}))     # meja preveri_stevec: 100
        klic(self.upravitelj, _JS({"action": "navigate", "url": "https://x"}))     # ni stevec: nic
        klic(self.upravitelj, _JS("ni slovar"))
        self.assertEqual(self.na_disku("total_ads_blocked"), 103)


if __name__ == "__main__":
    unittest.main()
