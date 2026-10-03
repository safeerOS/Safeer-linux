"""Igre v oblaku (core/os_oblak_igre.py): ponudniki, zdruzljivost, namestitev samo iz uradnega vira in samo na zahtevo."""
import os
import sys
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)
from core import os_oblak_igre as O  # noqa: E402

GFN = O.PONUDNIKI[0]
MINT = {"ram_mb": 11734, "jedra": 8, "arhitektura": "x86_64", "flatpak": True,
        "os": {"NAME": "Linux Mint", "ID": "linuxmint", "VERSION_ID": "22.3", "UBUNTU_CODENAME": "noble"}}


class Tek:
    def __init__(self, namescen=False, napaka_pri=None):
        self.klici, self.namescen, self.napaka_pri = [], namescen, napaka_pri

    def __call__(self, ukaz, cas):
        self.klici.append(ukaz)
        if ukaz[1] == "info":
            return (0 if self.namescen else 1), ""
        if self.napaka_pri == ukaz[1]:
            return 1, "error: No space left on device" if ukaz[1] == "install" else "error: ni omrezja"
        if ukaz[1] == "install":
            self.namescen = True
        return 0, ""


class TestOznaka(unittest.TestCase):
    def test_program_ponudnika_dobi_oznako_oblaka(self):
        self.assertEqual(O.oblak_za("com.nvidia.geforcenow.desktop"), {"ponudnik": "NVIDIA"})
        self.assertEqual(O.oblak_za("com.nvidia.geforcenow"), {"ponudnik": "NVIDIA"})
        self.assertIsNone(O.oblak_za("steam.desktop"))
        self.assertIsNone(O.oblak_za(""))

    def test_vsak_ponudnik_ima_uradni_vir_https(self):
        for p in O.PONUDNIKI:
            self.assertTrue(p["flatpak"]["repo"].startswith("https://"), p["id"])
            self.assertTrue(p["stran"].startswith("https://"), p["id"])
            self.assertEqual(p["flatpak"]["aplikacija"], p["id"])


class TestZdruzljivost(unittest.TestCase):
    def test_mint_na_osnovi_podprtega_ubuntuja_je_poskusi(self):
        z = O.zdruzljivost(GFN, MINT)
        self.assertEqual(z["stanje"], "poskusi")
        self.assertEqual(z["razlogi"], [{"koda": "osnova", "sistem": "Linux Mint", "osnova": "Ubuntu 24.04"}])

    def test_uradno_podprt_ubuntu(self):
        s = dict(MINT, os={"NAME": "Ubuntu", "ID": "ubuntu", "VERSION_ID": "24.04", "UBUNTU_CODENAME": "noble"})
        self.assertEqual(O.zdruzljivost(GFN, s), {"stanje": "zdruzljivo", "razlogi": []})
        s["os"]["VERSION_ID"] = "22.04"
        s["os"]["UBUNTU_CODENAME"] = "jammy"
        self.assertEqual(O.zdruzljivost(GFN, s)["stanje"], "poskusi")

    def test_premalo_pomnilnika_jeder_in_brez_flatpaka(self):
        z = O.zdruzljivost(GFN, dict(MINT, ram_mb=2000, jedra=1, flatpak=False, arhitektura="aarch64"))
        self.assertEqual(z["stanje"], "ne")
        self.assertEqual([r["koda"] for r in z["razlogi"]], ["arhitektura", "ram", "jedra", "flatpak"])

    def test_stiri_gb_pomnilnika_zadosca(self):
        # Racunalnik s »4 GB« ima ~3,8 GiB uporabnega pomnilnika: to ni razlog za zavrnitev.
        self.assertNotEqual(O.zdruzljivost(GFN, dict(MINT, ram_mb=3800))["stanje"], "ne")

    def test_neznan_sistem(self):
        z = O.zdruzljivost(GFN, dict(MINT, os={"NAME": "Fedora Linux", "ID": "fedora", "VERSION_ID": "42"}))
        self.assertEqual((z["stanje"], z["razlogi"][0]["koda"]), ("poskusi", "sistem"))


class TestNamestitev(unittest.TestCase):
    def test_namesti_iz_uradnega_vira_za_uporabnika(self):
        t = Tek()
        r = O.namesti("com.nvidia.geforcenow", t, MINT)
        self.assertEqual(r, {"ok": True, "id": "com.nvidia.geforcenow", "vnos": "com.nvidia.geforcenow.desktop"})
        self.assertEqual(t.klici, [
            ["flatpak", "remote-add", "--user", "--if-not-exists", "GeForceNOW",
             "https://international.download.nvidia.com/GFNLinux/flatpak/geforcenow.flatpakrepo"],
            ["flatpak", "install", "--user", "--noninteractive", "-y", "GeForceNOW", "com.nvidia.geforcenow"]])
        self.assertTrue(O.stanje(t, MINT)[0]["namescen"])

    def test_neznan_ponudnik_ne_zazene_nicesar(self):
        t = Tek()
        for id_ in ("org.zlonamerno.App", "", "com.nvidia.geforcenow; rm -rf ~", None):
            self.assertEqual(O.namesti(id_, t, MINT), {"ok": False, "napaka": "ni_ponudnika"})
        self.assertEqual(t.klici, [])

    def test_nezdruzljiv_racunalnik_ne_namesca(self):
        t = Tek()
        r = O.namesti("com.nvidia.geforcenow", t, dict(MINT, ram_mb=1500))
        self.assertEqual((r["ok"], r["napaka"], r["razlogi"][0]["koda"]), (False, "ni_zdruzljivo", "ram"))
        self.assertEqual(t.klici, [])

    def test_napake_namestitve(self):
        self.assertEqual(O.namesti("com.nvidia.geforcenow", Tek(napaka_pri="remote-add"), MINT)["napaka"], "vir")
        self.assertEqual(O.namesti("com.nvidia.geforcenow", Tek(napaka_pri="install"), MINT)["napaka"], "prostor")

    def test_stanje_za_stran(self):
        s = O.stanje(Tek(), MINT)
        self.assertEqual((s[0]["id"], s[0]["ime"], s[0]["ponudnik"], s[0]["namescen"], s[0]["zdruzljivost"]["stanje"]),
                         ("com.nvidia.geforcenow", "GeForce NOW", "NVIDIA", False, "poskusi"))


if __name__ == "__main__":
    unittest.main()
