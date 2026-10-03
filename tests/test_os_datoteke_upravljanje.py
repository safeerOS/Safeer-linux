"""Upravljanje datotek v Safeer OS (core/os_datoteke.py): kopiraj/premakni, Smeti z obnovitvijo, nosilci, lastnosti, slicice."""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)
from core import os_datoteke as D  # noqa: E402


class Osnova(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="safeer-dat-")
        self.staro = {k: os.environ.get(k) for k in ("XDG_DATA_HOME", "XDG_CACHE_HOME")}
        os.environ["XDG_DATA_HOME"] = os.path.join(self.tmp, "share")
        os.environ["XDG_CACHE_HOME"] = os.path.join(self.tmp, "cache")
        self.a, self.b = os.path.join(self.tmp, "a"), os.path.join(self.tmp, "b")
        os.makedirs(self.a)
        os.makedirs(self.b)

    def tearDown(self):
        for k, v in self.staro.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def pisi(self, pot, vsebina="x"):
        os.makedirs(os.path.dirname(pot), exist_ok=True)
        with open(pot, "w", encoding="utf-8") as f:
            f.write(vsebina)
        return pot


class TestPrilepi(Osnova):
    def test_kopija_ne_prepise_obstojecega(self):
        vir = self.pisi(os.path.join(self.a, "pismo.txt"), "novo")
        self.pisi(os.path.join(self.b, "pismo.txt"), "staro")
        r = D.prilepi([vir], self.b)
        self.assertTrue(r["ok"])
        self.assertEqual(r["narejeno"], [os.path.join(self.b, "pismo (2).txt")])
        with open(os.path.join(self.b, "pismo.txt")) as f:
            self.assertEqual(f.read(), "staro")
        self.assertTrue(os.path.exists(vir), "kopiranje izvirnika ne odstrani")

    def test_premik_mape_z_vsebino(self):
        self.pisi(os.path.join(self.a, "album", "01.txt"), "ena")
        r = D.prilepi([os.path.join(self.a, "album")], self.b, premakni=True)
        self.assertEqual(r["narejeno"], [os.path.join(self.b, "album")])
        self.assertFalse(os.path.exists(os.path.join(self.a, "album")))
        self.assertTrue(os.path.isfile(os.path.join(self.b, "album", "01.txt")))

    def test_mape_ne_kopira_vase(self):
        self.pisi(os.path.join(self.a, "x.txt"))
        pod = os.path.join(self.a, "pod")
        os.makedirs(pod)
        r = D.prilepi([self.a], pod)
        self.assertEqual(r["napake"], [{"pot": self.a, "napaka": "vase"}])
        self.assertEqual(os.listdir(pod), [])
        self.assertEqual(D.prilepi([self.a], self.a)["napake"][0]["napaka"], "vase")

    def test_premik_v_isto_mapo_ne_naredi_nic(self):
        vir = self.pisi(os.path.join(self.a, "x.txt"))
        r = D.prilepi([vir], self.a, premakni=True)
        self.assertTrue(r["ok"])
        self.assertEqual((r["narejeno"], r["napake"], os.listdir(self.a)), ([], [], ["x.txt"]))

    def test_domace_mape_in_korena_se_ne_dotakne(self):
        r = D.prilepi(["/", os.path.expanduser("~")], self.b, premakni=True)
        self.assertEqual([n["napaka"] for n in r["napake"]], ["ni_dovoljeno", "ni_dovoljeno"])
        self.assertEqual(os.listdir(self.b), [])

    def test_manjkajoc_vir_in_cilj(self):
        self.assertEqual(D.prilepi([os.path.join(self.a, "ni.txt")], self.b)["napake"][0]["napaka"], "ni_datoteke")
        self.assertEqual(D.prilepi([self.a], os.path.join(self.tmp, "ni-mape"))["napaka"], "ni_mape")
        self.assertEqual(D.prilepi([], self.b)["napaka"], "ni_datoteke")

    def test_simbolne_povezave_ne_sledi(self):
        cilj = self.pisi(os.path.join(self.a, "cilj.txt"), "tajno")
        os.symlink(cilj, os.path.join(self.a, "povezava"))
        r = D.prilepi([os.path.join(self.a, "povezava")], self.b)
        self.assertTrue(os.path.islink(r["narejeno"][0]))


class TestSmeti(Osnova):
    def test_v_smeti_seznam_obnovi(self):
        from core import link_urejanje
        pot = self.pisi(os.path.join(self.a, "racun.pdf"), "pdf")
        link_urejanje._v_smeti_rocno(pot)
        s = D.smeti()
        self.assertEqual(s["skupaj"], 1)
        e = s["elementi"][0]
        self.assertEqual((e["ime"], e["izvirna"], e["mapa"]), ("racun.pdf", pot, False))
        self.assertGreater(e["izbrisano"], time.time() - 120)
        # Medtem je na istem mestu nastala druga datoteka: obnovljena dobi novo ime, nic se ne prepise.
        self.pisi(pot, "druga")
        r = D.obnovi_iz_smeti(e["id"])
        self.assertTrue(r["ok"])
        self.assertEqual(r["pot"], os.path.join(self.a, "racun (2).pdf"))
        with open(pot) as f:
            self.assertEqual(f.read(), "druga")
        self.assertEqual(D.smeti()["skupaj"], 0)
        self.assertEqual(os.listdir(os.path.join(D._mapa_smeti(), "info")), [])

    def test_obnovi_ustvari_manjkajoco_mapo(self):
        from core import link_urejanje
        pot = self.pisi(os.path.join(self.a, "globoko", "zapis.txt"))
        link_urejanje._v_smeti_rocno(pot)
        shutil.rmtree(os.path.join(self.a, "globoko"))
        r = D.obnovi_iz_smeti(D.smeti()["elementi"][0]["id"])
        self.assertEqual(r, {"ok": True, "pot": pot})

    def test_id_ne_sme_iz_smeti(self):
        self.pisi(os.path.join(self.tmp, "zunaj.txt"))
        for id_ in ("../zunaj.txt", "../../zunaj.txt", "/etc/passwd", "", ".."):
            self.assertEqual(D.obnovi_iz_smeti(id_)["ok"], False, id_)

    def test_izprazni(self):
        from core import link_urejanje
        link_urejanje._v_smeti_rocno(self.pisi(os.path.join(self.a, "1.txt")))
        self.pisi(os.path.join(self.a, "mapa", "2.txt"))
        link_urejanje._v_smeti_rocno(os.path.join(self.a, "mapa"))
        self.assertEqual(D.izprazni_smeti(), {"ok": True, "izbrisano": 2})
        self.assertEqual(D.smeti()["skupaj"], 0)


class TestNosilci(unittest.TestCase):
    IZPIS = json.dumps({"blockdevices": [
        {"name": "nvme0n1", "path": "/dev/nvme0n1", "label": None, "size": 500107862016, "type": "disk", "rm": False, "hotplug": False,
         "mountpoint": None, "children": [
             {"name": "nvme0n1p1", "path": "/dev/nvme0n1p1", "label": None, "size": 536870912, "type": "part", "rm": False, "hotplug": False, "mountpoint": "/boot/efi"},
             {"name": "nvme0n1p2", "path": "/dev/nvme0n1p2", "label": None, "size": 499569942528, "type": "part", "rm": False, "hotplug": False, "mountpoint": "/"}]},
        {"name": "sda", "path": "/dev/sda", "label": None, "size": 31001149440, "type": "disk", "rm": True, "hotplug": True, "mountpoint": None,
         "children": [{"name": "sda1", "path": "/dev/sda1", "label": "KLJUC", "size": 31000100864, "type": "part", "rm": True, "hotplug": True,
                       "mountpoint": "/media/janez/KLJUC"}]},
        {"name": "sdb", "path": "/dev/sdb", "label": None, "size": 1000204886016, "type": "disk", "rm": False, "hotplug": False, "mountpoint": None,
         "children": [{"name": "sdb1", "path": "/dev/sdb1", "label": "Arhiv", "size": 1000203837440, "type": "part", "rm": False, "hotplug": False,
                       "mountpoint": "/mnt/arhiv"},
                      {"name": "sdb2", "path": "/dev/sdb2", "label": None, "size": 1024, "type": "part", "rm": False, "hotplug": False, "mountpoint": "[SWAP]"}]},
        {"name": "loop3", "path": "/dev/loop3", "label": None, "size": 4096, "type": "loop", "rm": False, "hotplug": False, "mountpoint": "/snap/core/1"}]})

    def test_samo_uporabnikovi_nosilci(self):
        n = D._nosilci_lsblk(self.IZPIS, "janez")
        self.assertEqual([(x["ime"], x["pot"], x["odstranljiv"]) for x in n],
                         [("KLJUC", "/media/janez/KLJUC", True), ("Arhiv", "/mnt/arhiv", False)])
        self.assertEqual(n[0]["naprava"], "/dev/sda1")

    def test_pokvarjen_izpis(self):
        self.assertEqual(D._nosilci_lsblk("ni json", "janez"), [])

    def test_izvrzi_samo_nosilec_s_seznama(self):
        self.assertEqual(D.izvrzi("/")["ok"], False)
        self.assertEqual(D.izvrzi(os.path.expanduser("~"))["ok"], False)


class TestLastnostiInSlicice(Osnova):
    def test_lastnosti(self):
        pot = self.pisi(os.path.join(self.a, "zapis.txt"), "12345")
        l = D.lastnosti(pot)
        self.assertEqual((l["ok"], l["ime"], l["velikost"], l["mapa"], l["mime"]), (True, "zapis.txt", 5, False, "text/plain"))
        self.assertTrue(l["pravice"].startswith("-rw"))
        m = D.lastnosti(self.a)
        self.assertEqual((m["mapa"], m["vsebuje"], m["velikost"]), (True, 1, 5))
        self.assertEqual(D.lastnosti(os.path.join(self.a, "ni"))["ok"], False)

    def test_slicica_slike(self):
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("ni Pillow")
        pot = os.path.join(self.a, "foto.png")
        Image.new("RGBA", (1200, 800), (200, 30, 30, 128)).save(pot)
        s = D.slicica(pot)
        self.assertTrue(s.startswith(os.path.join(self.tmp, "cache", "safeer-os", "slicice")), s)
        with Image.open(s) as i:
            self.assertEqual(max(i.size), D.SLICICA_VELIKOST)
        self.assertEqual(D.slicica(pot), s, "drugic iz predpomnilnika")
        self.assertEqual(D.slicice([pot, os.path.join(self.a, "ni.png")]), {pot: s})

    def test_slicica_ni_za_besedilo_in_pokvarjeno(self):
        self.assertEqual(D.slicica(self.pisi(os.path.join(self.a, "a.txt"))), "")
        self.assertEqual(D.slicica(self.pisi(os.path.join(self.a, "pokvarjena.jpg"), "ni slika")), "")
        self.assertEqual(os.listdir(self.a).count("pokvarjena.jpg"), 1)


class TestVelikaMapa(Osnova):
    def test_mapa_z_vec_kot_600_vnosi(self):
        for i in range(700):
            open(os.path.join(self.a, "d%04d.txt" % i), "w").close()
        r = D.preglej(self.a)
        self.assertEqual((r["skupaj"], len(r["elementi"])), (700, 700))


if __name__ == "__main__":
    unittest.main()
