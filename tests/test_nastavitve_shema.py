"""Shema settings.json (core/nastavitve_shema.py + core/config.ConfigManager; nacrt stabilnosti P2, naloga 43).

Napacen tip ali obseg -> privzeto v pomnilniku in zapis v dnevnik (ne sesutje); na disku ostane uporabnikova vrednost;
neznana polja ostanejo; stara razlicica -> selitev z varnostno kopijo settings.json.v<N>.bak."""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import config, nastavitve_shema  # noqa: E402


class Shema(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="nastavitve-")
        self.addCleanup(shutil.rmtree, self.d, ignore_errors=True)
        self.pot = os.path.join(self.d, "settings.json")

    def zapisi(self, vsebina):
        with open(self.pot, "w", encoding="utf-8") as f:
            f.write(vsebina if isinstance(vsebina, str) else json.dumps(vsebina))

    def disk(self):
        with open(self.pot, encoding="utf-8") as f:
            return json.load(f)

    def nalozi(self):
        izpis = io.StringIO()
        with contextlib.redirect_stdout(izpis):
            c = config.ConfigManager(config_dir=self.d)
        return c, izpis.getvalue()

    # ------------------------------------------------------------------ pokvarjeno in prazno
    def test_pokvarjen_json(self):
        self.zapisi('{"language": "sl", ')
        c, _ = self.nalozi()
        self.assertEqual(c.get("search_engine"), "duckduckgo")
        self.assertTrue(any(i.startswith("settings.json.pokvarjen-") for i in os.listdir(self.d)), os.listdir(self.d))
        self.assertEqual(self.disk()["schema_version"], nastavitve_shema.SCHEMA_VERSION)

    def test_prazna_datoteka_in_ne_slovar(self):
        for vsebina in ("", "[]", "null"):
            with self.subTest(vsebina=vsebina):
                for i in os.listdir(self.d):
                    os.unlink(os.path.join(self.d, i))
                self.zapisi(vsebina)
                c, _ = self.nalozi()
                self.assertTrue(c.get("adblock_enabled"))
                self.assertIsInstance(self.disk(), dict)

    # ------------------------------------------------------------------ tipi in obsegi
    def test_napacni_tipi_privzeto_in_dnevnik(self):
        prej = {"schema_version": nastavitve_shema.SCHEMA_VERSION, "splet_predpomnilnik_meja_mb": "veliko",
                "sidebar_width": True, "doh_enabled": "da", "tab_freeze_after_s": -5, "temno_nacin": "rdece",
                "hardware_acceleration": "turbo", "language": "sl", "default_bookmarks_removed": True,
                "dns_scit_selitev": True, "custom_portals": ["x", {"id": "a", "title": "A", "url": "https://a.si"}]}
        self.zapisi(prej)
        c, izpis = self.nalozi()
        self.assertEqual(c.get("sidebar_width"), config.DEFAULT_SETTINGS["sidebar_width"])
        self.assertIs(c.get("doh_enabled"), True)
        self.assertEqual(c.get("tab_freeze_after_s"), config.DEFAULT_SETTINGS["tab_freeze_after_s"])
        self.assertEqual(c.get("hardware_acceleration"), "on_demand")
        # Kljuc brez privzete vrednosti v DEFAULT_SETTINGS izgine: velja privzeta vrednost v kodi (os_splet: 500).
        self.assertNotIn("splet_predpomnilnik_meja_mb", c.settings)
        self.assertEqual(int(c.get("splet_predpomnilnik_meja_mb", 500) or 0), 500)
        self.assertNotIn("temno_nacin", c.settings)
        self.assertEqual([p["id"] for p in c.get("custom_portals")], ["a"])
        self.assertEqual(c.get("language"), "sl")
        self.assertIn("[Config] Nastavitve z napacnim tipom ali obsegom", izpis)
        self.assertIn("sidebar_width", izpis)
        self.assertNotIn("veliko", izpis, "vrednosti (lahko osebne) ne gredo v dnevnik")
        # Na disku nic izbrisano ali prepisano, tudi po zapisu drugega kljuca.
        self.assertEqual(self.disk()["splet_predpomnilnik_meja_mb"], "veliko")
        c.set("search_engine", "brave")
        disk = self.disk()
        self.assertEqual(disk["search_engine"], "brave")
        for k in ("splet_predpomnilnik_meja_mb", "sidebar_width", "doh_enabled", "temno_nacin", "custom_portals"):
            self.assertEqual(disk[k], prej[k], k)
        self.assertEqual(c.get("sidebar_width"), config.DEFAULT_SETTINGS["sidebar_width"], "zapis ne vrne napacne")

    def test_selitve_tecejo_kljub_napacnemu_elementu(self):
        """Prej: niz v custom_portals -> p.get(...) vrze -> vse selitve izpadejo (hydrahd ostane)."""
        self.zapisi({"default_bookmarks_removed": True, "dns_scit_selitev": True,
                     "custom_portals": ["x", {"id": "f", "title": "Filmi", "url": "https://hydrahd.ws/x"}]})
        c, _ = self.nalozi()
        self.assertEqual([p["url"] for p in c.get("custom_portals")], ["https://365.rtvslo.si"])
        self.assertEqual(c.get("custom_portals")[0]["title"], "RTV 365")

    def test_neznano_polje_ostane(self):
        self.zapisi({"schema_version": nastavitve_shema.SCHEMA_VERSION, "prihodnja_nastavitev": {"a": [1, 2]},
                     "default_bookmarks_removed": True, "dns_scit_selitev": True})
        c, _ = self.nalozi()
        self.assertEqual(c.get("prihodnja_nastavitev"), {"a": [1, 2]})
        c.set("theme", "mint")
        self.assertEqual(self.disk()["prihodnja_nastavitev"], {"a": [1, 2]})

    # ------------------------------------------------------------------ razlicica in selitev
    def test_stara_razlicica_selitev_in_kopija(self):
        prej = {"language": "de", "custom_css": "body{}", "neznano": 7, "default_bookmarks_removed": True,
                "dns_scit_selitev": True}
        self.zapisi(prej)
        with open(self.pot, "rb") as f:
            izvirnik = f.read()
        c, _ = self.nalozi()
        kopija = self.pot + ".v0.bak"
        self.assertTrue(os.path.isfile(kopija))
        with open(kopija, "rb") as f:
            self.assertEqual(f.read(), izvirnik, "kopija je bajt za bajtom stara datoteka")
        self.assertEqual(os.stat(kopija).st_mode & 0o777, 0o600)
        disk = self.disk()
        self.assertEqual(disk["schema_version"], nastavitve_shema.SCHEMA_VERSION)
        for k, v in prej.items():
            self.assertEqual(disk[k], v, k)
        self.assertEqual(c.get("language"), "de")
        # Drugi zagon: brez nove selitve, kopija ostane prva.
        self.zapisi(dict(disk, language="fr"))
        self.nalozi()
        with open(kopija, "rb") as f:
            self.assertEqual(f.read(), izvirnik)
        self.assertFalse(os.path.exists(self.pot + ".v1.bak"))

    def test_novejsa_razlicica_se_ne_zniza(self):
        prihodnja = nastavitve_shema.SCHEMA_VERSION + 1
        self.zapisi({"schema_version": prihodnja, "language": "it", "default_bookmarks_removed": True,
                     "dns_scit_selitev": True})
        c, _ = self.nalozi()
        self.assertEqual(c.get("schema_version"), prihodnja)
        c.set("theme", "mint")
        self.assertEqual(self.disk()["schema_version"], prihodnja)
        self.assertFalse(any(i.endswith(".bak") for i in os.listdir(self.d)))

    def test_nova_datoteka_ima_razlicico(self):
        self.nalozi()
        self.assertEqual(self.disk()["schema_version"], nastavitve_shema.SCHEMA_VERSION)

    def test_shema_pokrije_privzete(self):
        for k, v in config.DEFAULT_SETTINGS.items():
            with self.subTest(k=k):
                self.assertIn(k, nastavitve_shema.SHEMA)
                self.assertTrue(nastavitve_shema.SHEMA[k].ustreza(v))
        self.assertEqual(sorted(nastavitve_shema.SELITVE), list(range(1, nastavitve_shema.SCHEMA_VERSION + 1)))

    def test_bool_ni_stevilo(self):
        self.assertFalse(nastavitve_shema.SHEMA["sidebar_width"].ustreza(True))
        self.assertFalse(nastavitve_shema.SHEMA["doh_enabled"].ustreza(1))

    # ------------------------------------------------------------------ bralci brez ConfigManager
    def test_preberi_kljuc(self):
        self.assertEqual(nastavitve_shema.preberi_kljuc("ui_language", "x", self.pot), "x")
        self.assertFalse(os.path.exists(self.pot), "branje ne ustvari datoteke")
        self.zapisi({"ui_language": 5, "search_engine": "brave"})
        self.assertIsNone(nastavitve_shema.preberi_kljuc("ui_language", None, self.pot))
        self.assertEqual(nastavitve_shema.preberi_kljuc("search_engine", "duckduckgo", self.pot), "brave")
        self.zapisi("{pokvarjeno")
        self.assertEqual(nastavitve_shema.preberi_kljuc("search_engine", "duckduckgo", self.pot), "duckduckgo")

    def test_bralci_prek_sheme(self):
        def beri(pot):
            with open(os.path.join(KOREN, pot), encoding="utf-8") as f:
                return f.read()
        os_ = beri("safeer_os.py")
        self.assertIn('preberi_kljuc("ui_language", None, BRSKALNIK_NASTAVITVE)', os_)
        self.assertIn('preberi_kljuc("search_engine", "duckduckgo", BRSKALNIK_NASTAVITVE)', os_)
        self.assertIn('preberi_kljuc("ui_language", None, pot)', beri("safeer_control.py"))
        self.assertIn(" nastavitve_shema", beri("packaging/install_control_payload.sh"))
        self.assertIn(" nastavitve_shema ", beri("packaging/install_os_payload.sh"))
        # Varuh ostane brez uvozov core (najmanjsi proces, izmerjeno 18. 10. 2026) - a napacen tip ga ne podre.
        self.assertNotIn("nastavitve_shema", beri("core/varuh_procesov.py"))

    def test_varuh_napacen_tip(self):
        from core import varuh_procesov
        mapa = os.path.join(self.d, "safeer-mint")
        os.makedirs(mapa)
        with open(os.path.join(mapa, "settings.json"), "w") as f:
            json.dump({"ui_language": 5}, f)
        self.assertEqual(varuh_procesov.jezik({"XDG_CONFIG_HOME": self.d, "LANG": "sl_SI.UTF-8"}), "sl")


if __name__ == "__main__":
    unittest.main()
