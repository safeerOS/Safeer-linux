"""core/shramba_json: atomski zapis in zdruzevanje kljucev med procesi (os.json Safeer OS in Scit, 20. 10. 2026).

Pred popravkom je vsak proces ob zapisu zapisal celo svojo kopijo os.json - sprememba drugega procesa (npr. Scit v
svojem procesu nastavi scit_naprej) se je tiho izgubila.
"""
import json
import multiprocessing
import os
import stat
import tempfile
import time
import unittest

from core import shramba_json


def _otrok_nastavi(pot, kljuc, vrednost, ponovitev):
    s = shramba_json.Shramba(pot)
    for i in range(ponovitev):
        s.set(kljuc, "%s-%d" % (vrednost, i))


class TestShrambaJson(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.pot = os.path.join(self.mapa, "os.json")

    def test_drug_proces_ne_povozi_kljuca(self):
        a = shramba_json.Shramba(self.pot)
        b = shramba_json.Shramba(self.pot)
        a.set("scit", True)
        b.set("tema", "temna")           # b ne pozna kljuca "scit" - prej ga je zbrisal
        with open(self.pot, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"scit": True, "tema": "temna"})
        self.assertEqual(b.get("scit"), True)   # b je kljuc drugega procesa prevzel

    def test_brisanje_kljuca_se_ohrani(self):
        a = shramba_json.Shramba(self.pot)
        a.set("x", 1)
        a.set("y", 2)
        b = shramba_json.Shramba(self.pot)
        del a.podatki["x"]
        a.shrani()
        b.set("z", 3)
        self.assertEqual(shramba_json.preberi_slovar(self.pot), {"y": 2, "z": 3})

    def test_vec_procesov_hkrati(self):
        ctx = multiprocessing.get_context("spawn")
        otroci = [ctx.Process(target=_otrok_nastavi, args=(self.pot, "k%d" % i, "v", 25)) for i in range(4)]
        for p in otroci:
            p.start()
        for p in otroci:
            p.join(60)
            self.assertEqual(p.exitcode, 0)
        self.assertEqual(shramba_json.preberi_slovar(self.pot), {"k%d" % i: "v-24" for i in range(4)})
        self.assertEqual([n for n in os.listdir(self.mapa) if n.endswith(".tmp")], [])

    def test_pravice_0600(self):
        shramba_json.Shramba(self.pot).set("a", 1)
        self.assertEqual(stat.S_IMODE(os.stat(self.pot).st_mode), 0o600)

    def test_pokvarjena_datoteka_se_umakne_ne_prepise(self):
        with open(self.pot, "w", encoding="utf-8") as f:
            f.write('{"scit": tr')
        s = shramba_json.Shramba(self.pot)
        self.assertEqual(s.podatki, {})
        umaknjene = [n for n in os.listdir(self.mapa) if n.startswith("os.json.pokvarjen-")]
        self.assertEqual(len(umaknjene), 1)
        with open(os.path.join(self.mapa, umaknjene[0]), encoding="utf-8") as f:
            self.assertEqual(f.read(), '{"scit": tr')

    def test_osvezi_prevzame_tuje_ohrani_svoje(self):
        a = shramba_json.Shramba(self.pot)
        a.set("x", 1)
        b = shramba_json.Shramba(self.pot)
        a.set("x", 2)
        b.podatki["y"] = "lokalno"       # se ni shranjeno
        b.osvezi()
        self.assertEqual(b.get("x"), 2)
        self.assertEqual(b.get("y"), "lokalno")

    def test_hkraten_set_dveh_niti_se_ne_izgubi(self):
        """Neodvisni pregled 1.0.129: nit A je nastavila kljuc med zapisom niti B; B je po zapisu prevzela staro
        vrednost z diska in A-jeva se ni zapisala nikoli."""
        import threading
        from unittest import mock
        s = shramba_json.Shramba(self.pot)
        s.set("b", "staro")
        v_zapisu, nadaljuj = threading.Event(), threading.Event()
        pravi = shramba_json.zapisi_atomsko

        def pocasen(*a, **k):
            if threading.current_thread().name == "B":
                v_zapisu.set()
                nadaljuj.wait(5)
            return pravi(*a, **k)
        with mock.patch.object(shramba_json, "zapisi_atomsko", pocasen):
            s.podatki["a"] = 1
            b = threading.Thread(target=s.shrani, name="B")
            b.start()
            self.assertTrue(v_zapisu.wait(5))
            a = threading.Thread(target=s.set, args=("b", "novo"), name="A")
            a.start()
            time.sleep(0.2)
            nadaljuj.set()
            b.join(5)
            a.join(5)
        self.assertEqual(shramba_json.preberi_slovar(self.pot), {"a": 1, "b": "novo"})
        self.assertEqual(s.get("b"), "novo")

    def test_napaka_zapisa_ne_pusti_zacasne(self):
        with self.assertRaises(TypeError):
            shramba_json.zapisi_atomsko(self.pot, {"a": object()})
        self.assertEqual(os.listdir(self.mapa), [])


    def _drzi_zaklep_v_drugem_procesu(self):
        """flock je po odprtem opisu datoteke: drug opis v istem procesu se obnasa kot drug proces."""
        import fcntl
        fd = os.open(self.pot + ".lock", os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        self.addCleanup(os.close, fd)
        return fd

    def test_zaseden_zaklep_ne_pise_in_ponovi(self):
        """Pregled 4. 11. 2026: po roku 2 s je zaklep popustil in Shramba je vseeno pisala - zapis drugega procesa,
        ki je drzal zaklep, je bil povozen. Brez zaklepa nic na disk; ko se sprosti, se zapis ponovi sam."""
        import fcntl
        from unittest import mock
        s = shramba_json.Shramba(self.pot)
        s.set("a", 1)
        fd = self._drzi_zaklep_v_drugem_procesu()
        pravi = shramba_json.zaklep
        with mock.patch.object(shramba_json, "zaklep", lambda pot, rok=2.0: pravi(pot, rok=0.05)), \
                mock.patch.object(shramba_json.Shramba, "ZAMIK_PONOVITVE", 0.1, create=True):
            s.podatki["b"] = 2
            self.assertFalse(s.shrani())
            self.assertEqual(shramba_json.preberi_slovar(self.pot), {"a": 1})   # nic zapisano brez zaklepa
            self.assertEqual(s.get("b"), 2)                                       # sprememba ostane v pomnilniku
            fcntl.flock(fd, fcntl.LOCK_UN)
            meja = time.monotonic() + 5
            while shramba_json.preberi_slovar(self.pot) != {"a": 1, "b": 2} and time.monotonic() < meja:
                time.sleep(0.05)
        self.assertEqual(shramba_json.preberi_slovar(self.pot), {"a": 1, "b": 2})

    def test_zaklep_ob_oserror_ne_pise(self):
        from unittest import mock
        s = shramba_json.Shramba(self.pot)
        s.set("a", 1)
        with mock.patch.object(shramba_json.fcntl, "flock", side_effect=OSError("ENOLCK")), \
                mock.patch.object(shramba_json.Shramba, "_ponovi_kasneje", lambda self: None, create=True):
            s.podatki["b"] = 2
            self.assertFalse(s.shrani())
        self.assertEqual(shramba_json.preberi_slovar(self.pot), {"a": 1})
        self.assertTrue(s.shrani())                 # ob naslednjem zapisu gre sprememba na disk
        self.assertEqual(shramba_json.preberi_slovar(self.pot), {"a": 1, "b": 2})

    def test_datotecni_sistem_brez_flock_vseeno_shrani(self):
        """ENOLCK/EOPNOTSUPP (NFS brez lockd): zaklepa med procesi ne bo nikoli - prej je bil vsak zapis odlozen in
        nastavitve se niso shranile nikoli (CodeRabbit, 4. 11. 2026). Zdaj velja samo zaklep niti."""
        import errno
        from unittest import mock
        for koda in (errno.ENOLCK, errno.EOPNOTSUPP):
            with self.subTest(errno.errorcode[koda]):
                s = shramba_json.Shramba(self.pot)
                s.set("k", koda)
                with mock.patch.object(shramba_json.fcntl, "flock", side_effect=OSError(koda, os.strerror(koda))), \
                        mock.patch.object(shramba_json.Shramba, "_ponovi_kasneje", lambda self: None, create=True):
                    s.podatki["k"] = -koda
                    self.assertTrue(s.shrani())
                self.assertEqual(shramba_json.preberi_slovar(self.pot)["k"], -koda)

    def test_config_stevec_ne_izgubi_povecanja_ob_zasedenem_zaklepu(self):
        import fcntl
        from unittest import mock
        from core.config import ConfigManager
        cfg = ConfigManager(config_dir=self.mapa)
        self.pot = cfg.config_file
        zacetek = cfg.get("total_ads_blocked", 0) or 0
        fd = self._drzi_zaklep_v_drugem_procesu()
        pravi = shramba_json.zaklep
        with mock.patch.object(shramba_json, "zaklep", lambda pot, rok=2.0: pravi(pot, rok=0.05)), \
                mock.patch.object(ConfigManager, "_ponovi_kasneje", lambda self: None, create=True):
            cfg.increment_ads_blocked(3)
            self.assertEqual((shramba_json.preberi_slovar(self.pot) or {}).get("total_ads_blocked", 0) or 0,
                             zacetek)
        fcntl.flock(fd, fcntl.LOCK_UN)
        cfg.increment_ads_blocked(2)
        self.assertEqual(shramba_json.preberi_slovar(self.pot)["total_ads_blocked"], zacetek + 5)

    def _cakanje_ne_drzi_zaklepa_niti(self, zapisi):
        """Pregled 4. 11. 2026: ponovitev zapisa (nit v ozadju) je med cakanjem na flock drzala globalni ZAKLEP_NITI
        - vsak set() druge shrambe na glavni niti je zamrznil do 2 s. Zdaj ZAKLEP_NITI med cakanjem ostane prost."""
        import threading
        fd = self._drzi_zaklep_v_drugem_procesu()
        caka = threading.Thread(target=zapisi, name="ponovitev", daemon=True)
        caka.start()
        time.sleep(0.3)                       # nit zdaj caka na flock (rok 2 s)
        self.assertTrue(caka.is_alive())
        zacetek = time.monotonic()
        dobil = shramba_json.ZAKLEP_NITI.acquire(timeout=0.5)
        if dobil:
            shramba_json.ZAKLEP_NITI.release()
        druga = shramba_json.Shramba(os.path.join(self.mapa, "druga.json"))
        druga.set("x", 1)                     # druga datoteka: ne sme cakati na tuj flock
        trajalo = time.monotonic() - zacetek
        import fcntl
        fcntl.flock(fd, fcntl.LOCK_UN)
        caka.join(5)
        self.assertTrue(dobil, "ZAKLEP_NITI je drzala nit, ki caka na flock")
        self.assertLess(trajalo, 1.0)
        self.assertEqual(shramba_json.preberi_slovar(os.path.join(self.mapa, "druga.json")), {"x": 1})

    def test_ponovitev_shrambe_ne_drzi_zaklepa_niti_med_cakanjem(self):
        s = shramba_json.Shramba(self.pot)
        s.podatki["a"] = 1
        self._cakanje_ne_drzi_zaklepa_niti(s._ponovi)

    def test_ponovitev_nastavitev_ne_drzi_zaklepa_niti_med_cakanjem(self):
        from unittest import mock
        from core.config import ConfigManager
        cfg = ConfigManager(config_dir=self.mapa)
        self.pot = cfg.config_file
        cfg.settings["virtual_keyboard_enabled"] = True
        with mock.patch.object(ConfigManager, "_ponovi_kasneje", lambda self: None, create=True):
            self._cakanje_ne_drzi_zaklepa_niti(cfg._ponovi)


if __name__ == "__main__":
    unittest.main()
