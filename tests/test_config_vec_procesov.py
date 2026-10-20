"""settings.json si delijo Safeer OS, Safeer Browser (.deb in Flatpak) - vsak proces ima svojo kopijo nastavitev.

Stresni preizkus 20. 10. 2026: zapis enega procesa je prepisal spremembe drugega (npr. zaprtje brskalnika je vrnilo
izbiro DNS, ki jo je uporabnik medtem spremenil v Safeer OS), prekinjen zapis je pustil napol zapisano datoteko, ta pa
je ob naslednjem zagonu pomenila privzete nastavitve cez uporabnikove."""
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from core import config

KOREN = Path(__file__).resolve().parents[1]


class Profil(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self.mapa.cleanup)
        self.pot = Path(self.mapa.name) / "settings.json"
        for ime, vrednost in (("CONFIG_DIR", self.mapa.name), ("CONFIG_FILE", str(self.pot))):
            p = patch.object(config, ime, vrednost)
            p.start()
            self.addCleanup(p.stop)

    def disk(self):
        return json.loads(self.pot.read_text(encoding="utf-8"))


class ZapisNePrekrijeDrugegaProcesa(Profil):
    def test_kljuc_drugega_procesa_ostane(self):
        os_ = config.ConfigManager()            # Safeer OS
        brskalnik = config.ConfigManager()      # Safeer Browser, odprt prej
        os_.set("doh_provider", "quad9")        # uporabnik spremeni DNS v Safeer OS
        brskalnik.set("splet_seja", ["https://safeer.si/"])   # brskalnik se zapre in shrani zavihke
        d = self.disk()
        self.assertEqual(d["doh_provider"], "quad9")
        self.assertEqual(d["splet_seja"], ["https://safeer.si/"])
        # brskalnik ima zdaj tudi v pomnilniku izbiro, ki jo je naredil drug proces
        self.assertEqual(brskalnik.get("doh_provider"), "quad9")

    def test_spremenjen_gnezden_slovar_in_save_settings(self):
        a = config.ConfigManager()
        b = config.ConfigManager()
        a.set("language", "de")
        b.settings.setdefault("user_script_values", {})["s1"] = {"x": "1"}
        b.save_settings()
        d = self.disk()
        self.assertEqual(d["language"], "de")
        self.assertEqual(d["user_script_values"]["s1"], {"x": "1"})

    def test_privzeta_vrednost_ne_prekrije_izbire_drugega(self):
        self.pot.write_text(json.dumps({"default_bookmarks_removed": True, "dns_scit_selitev": True}),
                            encoding="utf-8")
        a = config.ConfigManager()             # nalozi brez kljuca force_dark_mode (privzeta vrednost)
        b = config.ConfigManager()
        b.set("force_dark_mode", not config.DEFAULT_SETTINGS.get("force_dark_mode", True))
        a.set("language", "fr")
        self.assertEqual(self.disk()["force_dark_mode"], not config.DEFAULT_SETTINGS.get("force_dark_mode", True))

    def test_hkraten_zapis_dveh_procesov(self):
        """Dva prava procesa vsak po 40 zapisov svojega kljuca: na koncu sta oba kljuca in datoteka je cel JSON."""
        self.pot.write_text("{}", encoding="utf-8")
        skript = textwrap.dedent(f"""
            import sys
            sys.path.insert(0, {str(KOREN)!r})
            from core import config
            config.CONFIG_DIR, config.CONFIG_FILE = {self.mapa.name!r}, {str(self.pot)!r}
            c = config.ConfigManager()
            for i in range(40):
                c.set(sys.argv[1], i)
        """)
        procesa = [subprocess.Popen([sys.executable, "-c", skript, k]) for k in ("stevec_a", "stevec_b")]
        for p in procesa:
            self.assertEqual(p.wait(timeout=60), 0)
        d = self.disk()
        self.assertEqual((d["stevec_a"], d["stevec_b"]), (39, 39))


class ZapisJeAtomski(Profil):
    def test_prekinjen_zapis_pusti_staro_datoteko(self):
        c = config.ConfigManager()
        c.set("language", "it")
        pred = self.pot.read_bytes()

        def napol(podatki, f, **_k):
            f.write('{"language": "x"')
            raise OSError("disk poln")
        with patch.object(config.json, "dump", side_effect=napol):
            self.assertFalse(c.set("language", "es"))
        self.assertEqual(self.pot.read_bytes(), pred)
        self.assertEqual(sorted(p.name for p in Path(self.mapa.name).iterdir()
                                if p.name.startswith(".settings.json.")), [])

    def test_pokvarjena_datoteka_ni_prepisana_s_privzetimi(self):
        self.pot.write_text('{"language": "de", "custom_portals": [', encoding="utf-8")
        c = config.ConfigManager()
        shranjene = [p for p in Path(self.mapa.name).iterdir() if p.name.startswith("settings.json.pokvarjen-")]
        self.assertEqual(len(shranjene), 1)
        self.assertEqual(shranjene[0].read_text(encoding="utf-8"), '{"language": "de", "custom_portals": [')
        self.assertEqual(c.get("language"), config.DEFAULT_SETTINGS.get("language"))
        self.assertIsInstance(self.disk(), dict)

    def test_datoteka_samo_za_lastnika(self):
        config.ConfigManager().set("language", "sl")
        self.assertEqual(os.stat(self.pot).st_mode & 0o077, 0)


if __name__ == "__main__":
    unittest.main()
