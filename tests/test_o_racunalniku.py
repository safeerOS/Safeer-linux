"""O tem racunalniku v Datotekah (lastnik, 27. 10. 2026: »enostavno omogociti uporabniku kot del namiznega okolja, kjer
pregleduje datoteke«): diski iz /proc/self/mounts (brez navideznih in omreznih), naprave za shranjevanje, jedra,
baterija, graficna, zasloni, osnova sistema, razlicice komponent, velikost map (rok, preklic, simbolne povezave) in
namizje QML (offscreen, lazni SafeerOS). Vse ciste funkcije nad besedilom - brez /sys in /proc tega racunalnika."""
import json
import os
import re
import sys
import tempfile
import types
import unittest

import test_qml_enakost as tq

from core import sistem_podatki as sp

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# /proc/self/mounts prenosnika z Ubuntujem (posneto po vzorcu, imena naprav in poti izmisljena).
MOUNTS = r"""sysfs /sys sysfs rw,nosuid,nodev,noexec,relatime 0 0
proc /proc proc rw,nosuid,nodev,noexec,relatime 0 0
udev /dev devtmpfs rw,nosuid,relatime 0 0
tmpfs /run tmpfs rw,nosuid,nodev,noexec,relatime 0 0
/dev/nvme0n1p2 / ext4 rw,relatime,errors=remount-ro 0 0
/dev/nvme0n1p2 /var/snap/firefox/common/host-hunspell ext4 ro,relatime 0 0
/dev/loop3 /snap/firefox/4848 squashfs ro,nodev,relatime 0 0
/dev/nvme0n1p1 /boot/efi vfat rw,relatime 0 0
tmpfs /run/user/1000 tmpfs rw,nosuid,nodev,relatime 0 0
gvfsd-fuse /run/user/1000/gvfs fuse.gvfsd-fuse rw,nosuid,nodev,relatime 0 0
/dev/sda1 /run/media/ana/Moj\040disk exfat rw,nosuid,nodev,relatime 0 0
/dev/sdb1 /mnt/varnost ext4 rw,relatime 0 0
/dev/sdb1 /home/ana/varnost ext4 rw,relatime 0 0
streznik:/izvoz /mnt/nfs nfs4 rw,relatime 0 0
//nas/deljeno /mnt/nas cifs rw,relatime 0 0
overlay /var/lib/docker/overlay2/x/merged overlay rw,relatime 0 0
/dev/zram0 /var/zram ext4 rw 0 0
/dev/sdc1 /media/ana/USB fuseblk rw,nosuid,nodev,relatime 0 0
"""

LSBLK = json.dumps({"blockdevices": [
    {"name": "nvme0n1", "path": "/dev/nvme0n1", "size": 512110190592, "type": "disk", "rm": False, "hotplug": False,
     "model": "Samsung SSD 980 PRO 500GB ", "rota": False, "tran": "nvme"},
    {"name": "sda", "path": "/dev/sda", "size": 2000398934016, "type": "disk", "rm": False, "hotplug": True,
     "model": "WD Elements", "rota": True, "tran": "usb"},
    {"name": "sdb", "path": "/dev/sdb", "size": 1000204886016, "type": "disk", "rm": False, "hotplug": False,
     "model": "ST1000DM010", "rota": True, "tran": "sata"},
    {"name": "sdd", "path": "/dev/sdd", "size": 256060514304, "type": "disk", "rm": False, "hotplug": False,
     "model": "Crucial", "rota": False, "tran": "sata"},
    {"name": "mmcblk0", "path": "/dev/mmcblk0", "size": 63864569856, "type": "disk", "rm": False, "hotplug": False,
     "model": None, "rota": False, "tran": None},
    {"name": "loop3", "path": "/dev/loop3", "size": 268435456, "type": "loop"},
    {"name": "zram0", "path": "/dev/zram0", "size": 8e9, "type": "disk"},
    {"name": "sr0", "path": "/dev/sr0", "size": 0, "type": "rom"},
]})

CPUINFO_HT = "".join("processor\t: %d\nphysical id\t: 0\ncore id\t\t: %d\nmodel name\t: Intel(R) Core(TM) i7\n\n" % (i, i % 4)
                     for i in range(8))
CPUINFO_DVA = "".join("processor\t: %d\nphysical id\t: %d\ncore id\t\t: %d\n\n" % (i, i // 4, i % 4) for i in range(8))
CPUINFO_ARM = "processor\t: 0\nBogoMIPS\t: 108.00\n\nprocessor\t: 1\nBogoMIPS\t: 108.00\n"

BAT = """POWER_SUPPLY_NAME=BAT0
POWER_SUPPLY_TYPE=Battery
POWER_SUPPLY_STATUS=Discharging
POWER_SUPPLY_PRESENT=1
POWER_SUPPLY_ENERGY_FULL_DESIGN=57000000
POWER_SUPPLY_ENERGY_FULL=45600000
POWER_SUPPLY_CAPACITY=73
POWER_SUPPLY_MANUFACTURER=SMP
POWER_SUPPLY_MODEL_NAME=5B10W13930
"""


class Priklopi(unittest.TestCase):
    def test_samo_pravi_lokalni_datotecni_sistemi(self):
        p = sp.priklopi_iz_mounts(MOUNTS)
        tocke = sorted(t for _, t, _ in p)
        # Brez /sys, /proc, /run, /boot, snap (squashfs, loop), gvfs, nfs, cifs, overlay, zram; bind sdb1 samo enkrat.
        self.assertEqual(tocke, ["/", "/media/ana/USB", "/mnt/varnost", "/run/media/ana/Moj disk"])
        self.assertIn(("/dev/nvme0n1p2", "/", "ext4"), p)

    def test_osmiska_koda_presledka(self):
        self.assertEqual(sp._odkodiraj_priklop(r"/media/a\040b\134c"), "/media/a b\\c")

    def test_omrezni_se_ne_merijo(self):
        # statvfs na odklopljenem strezniku NFS lahko visi: omreznih tock sploh ne vprasamo.
        vprasano = []

        def statvfs(t):
            vprasano.append(t)
            return (100e9, 40e9)
        sp.dopolni_iz_priklopov([], MOUNTS, statvfs, "/home/ana")
        self.assertFalse([t for t in vprasano if t.startswith(("/mnt/nfs", "/mnt/nas", "/proc", "/sys", "/run/user"))], vprasano)

    def test_dopolni_lsblk_brez_udev(self):
        # Virtualni racunalnik (27. 10. 2026): lsblk ne pove FSTYPE, seznam iz lsblk je prazen - priklopi ga dopolnijo.
        velikosti = {"/": (100e9, 3e9), "/mnt/varnost": (1000e9, 600e9), "/media/ana/USB": (32e9, 30e9),
                     "/run/media/ana/Moj disk": (0, 0)}
        d = sp.dopolni_iz_priklopov([], MOUNTS, lambda t: velikosti.get(t), "/home/ana")
        self.assertEqual([x["pot"] for x in d], ["/", "/mnt/varnost", "/media/ana/USB"])   # sistem prvi, nato po velikosti
        sistem = d[0]
        self.assertTrue(sistem["sistem"] and sistem["priklopljen"] and sistem["malo_prostora"])
        self.assertEqual((sistem["velikost"], sistem["prosto"], sistem["datotecni_sistem"]), (100e9, 3e9, "ext4"))
        self.assertFalse(d[1]["malo_prostora"])
        self.assertTrue(d[2]["odstranljiv"])
        for k in ("naprava", "oznaka", "model", "datotecni_sistem", "velikost", "prosto", "pot", "priklopljen", "odstranljiv",
                  "sistem", "dom", "malo_prostora"):
            self.assertIn(k, sistem)

    def test_znanih_iz_lsblk_ne_podvoji(self):
        iz_lsblk = [{"naprava": "/dev/nvme0n1p2", "pot": "/", "velikost": 1, "prosto": 1, "priklopljen": True, "sistem": True}]
        d = sp.dopolni_iz_priklopov(iz_lsblk, MOUNTS, lambda t: (10e9, 5e9))
        self.assertEqual([x["pot"] for x in d].count("/"), 1)
        self.assertIs(d[0], iz_lsblk[0])

    def test_prazno_in_pokvarjeno(self):
        self.assertEqual(sp.priklopi_iz_mounts(""), [])
        self.assertEqual(sp.priklopi_iz_mounts("nesmisel\n\n/dev/sda1\n"), [])
        self.assertEqual(sp.dopolni_iz_priklopov([], MOUNTS, lambda t: None), [])


class Strojna(unittest.TestCase):
    def test_naprave_iz_lsblk(self):
        n = sp.naprave_iz_lsblk(LSBLK)
        po = {x["naprava"]: x for x in n}
        self.assertEqual(set(po), {"/dev/nvme0n1", "/dev/sda", "/dev/sdb", "/dev/sdd", "/dev/mmcblk0"})   # brez loop, zram, rom
        self.assertEqual(po["/dev/nvme0n1"]["vrsta"], "nvme")
        self.assertEqual(po["/dev/nvme0n1"]["model"], "Samsung SSD 980 PRO 500GB")
        self.assertEqual((po["/dev/sda"]["vrsta"], po["/dev/sda"]["odstranljiv"]), ("usb", True))
        self.assertEqual(po["/dev/sdb"]["vrsta"], "hdd")
        self.assertEqual(po["/dev/sdd"]["vrsta"], "ssd")
        self.assertEqual(po["/dev/mmcblk0"]["vrsta"], "mmc")
        self.assertEqual(n[-1]["naprava"], "/dev/sda")            # odstranljivi na koncu
        self.assertEqual(sp.naprave_iz_lsblk(""), [])
        self.assertEqual(sp.naprave_iz_lsblk("{ni json"), [])

    def test_jedra(self):
        self.assertEqual(sp.jedra_iz_cpuinfo(CPUINFO_HT), 4)       # 8 niti, 4 jedra
        self.assertEqual(sp.jedra_iz_cpuinfo(CPUINFO_DVA), 8)      # dva procesorja po 4 jedra
        self.assertEqual(sp.jedra_iz_cpuinfo(CPUINFO_ARM), 0)      # ne pove - ne ugibamo
        self.assertEqual(sp.jedra_iz_cpuinfo(""), 0)

    def test_baterija(self):
        b = sp.baterija_iz_uevent(BAT)
        self.assertEqual(b, {"ime": "BAT0", "model": "SMP 5B10W13930", "napolnjenost": 73, "stanje": "prazni", "zdravje": 80})
        polni = sp.baterija_iz_uevent(BAT.replace("Discharging", "Charging").replace("ENERGY", "CHARGE"))
        self.assertEqual((polni["stanje"], polni["zdravje"]), ("polni", 80))
        brez = sp.baterija_iz_uevent("POWER_SUPPLY_TYPE=Battery\nPOWER_SUPPLY_STATUS=Unknown\n")
        self.assertEqual((brez["napolnjenost"], brez["zdravje"], brez["stanje"]), (-1, -1, ""))
        self.assertIsNone(sp.baterija_iz_uevent("POWER_SUPPLY_TYPE=Mains\nPOWER_SUPPLY_ONLINE=1\n"))
        self.assertIsNone(sp.baterija_iz_uevent(BAT + "POWER_SUPPLY_SCOPE=Device\n"))     # miska
        self.assertIsNone(sp.baterija_iz_uevent(BAT.replace("PRESENT=1", "PRESENT=0")))
        self.assertIsNone(sp.baterija_iz_uevent(""))

    def test_baterije_iz_imenika(self):
        with tempfile.TemporaryDirectory() as d:
            for ime, vsebina in (("BAT0", BAT), ("AC", "POWER_SUPPLY_TYPE=Mains\n")):
                os.makedirs(os.path.join(d, ime))
                with open(os.path.join(d, ime, "uevent"), "w") as f:
                    f.write(vsebina)
            self.assertEqual([b["ime"] for b in sp.baterije(d)], ["BAT0"])
        self.assertEqual(sp.baterije("/ni/tega/imenika"), [])

    def test_graficna_in_zaslon(self):
        self.assertEqual(sp.graficna_iz_uevent("DRIVER=i915\nPCI_ID=8086:A7A0\n"), "i915 (8086:a7a0)")
        self.assertEqual(sp.graficna_iz_uevent("DRIVER=virtio-pci\n"), "virtio-pci")
        self.assertEqual(sp.graficna_iz_uevent(""), "")
        self.assertEqual(sp.zaslon_iz_drm("card1-eDP-1", "connected\n", "1920x1200\n1600x1200\n"),
                         {"prikljucek": "eDP-1", "locljivost": "1920x1200", "vgrajen": True})
        self.assertEqual(sp.zaslon_iz_drm("card0-HDMI-A-1", "connected", "")["locljivost"], "")
        self.assertFalse(sp.zaslon_iz_drm("card0-HDMI-A-1", "connected", "3840x2160")["vgrajen"])
        self.assertIsNone(sp.zaslon_iz_drm("card0-DP-2", "disconnected", "1920x1080"))

    def test_zasloni_iz_imenika(self):
        with tempfile.TemporaryDirectory() as d:
            for ime, stanje in (("card1-eDP-1", "connected"), ("card1-DP-1", "disconnected")):
                os.makedirs(os.path.join(d, ime))
                with open(os.path.join(d, ime, "status"), "w") as f:
                    f.write(stanje + "\n")
                with open(os.path.join(d, ime, "modes"), "w") as f:
                    f.write("2560x1600\n")
            self.assertEqual([z["prikljucek"] for z in sp.zasloni(d)], ["eDP-1"])
        self.assertEqual(sp.zasloni("/ni/tega/imenika"), [])


class Programska(unittest.TestCase):
    def test_osnova(self):
        ubuntu = 'NAME="Linux Mint"\nID=linuxmint\nID_LIKE="ubuntu debian"\nUBUNTU_CODENAME=noble\n'
        self.assertEqual(sp.osnova_iz_release(ubuntu), "ubuntu debian (noble)")
        self.assertEqual(sp.osnova_iz_release('ID=debian\nVERSION_CODENAME=trixie\nDEBIAN_CODENAME=trixie\n'), "")
        self.assertEqual(sp.osnova_iz_release("ID=fedora\n"), "")
        self.assertEqual(sp.osnova_iz_release(""), "")

    def test_komponente_samo_ze_nalozene(self):
        class Gtk:
            def get_major_version(self):
                return 4

            def get_minor_version(self):
                return 14

            def get_micro_version(self):
                return 2

        class Pokvarjen:
            def get_major_version(self):
                raise RuntimeError("ni simbola")

        qt = types.SimpleNamespace(qVersion=lambda: "6.8.2")
        gst = types.SimpleNamespace(version=lambda: (1, 24, 2, 0))
        k = dict(sp.komponente_iz_modulov({"PySide6.QtCore": qt, "gi.repository.Gtk": Gtk(), "gi.repository.Gst": gst,
                                           "gi.repository.WebKit": Pokvarjen()}))
        self.assertEqual(k["Qt"], "6.8.2")
        self.assertEqual(k["GTK"], "4.14.2")
        self.assertEqual(k["GStreamer"], "1.24.2")
        self.assertNotIn("WebKitGTK", k)               # pokvarjen modul: vrstice ni, napake tudi ne
        self.assertNotIn("libsoup", k)                 # ni nalozen - ne uvozimo ga zaradi prikaza
        self.assertEqual(list(dict(sp.komponente_iz_modulov({}))), ["Python"])

    def test_podatki_brez_omrezja_in_root(self):
        # Ves modul: brez omreznih knjiznic, brez sudo/pkexec (zasebnost: Safeer ne posilja telemetrije).
        vir = open(os.path.join(KOREN, "core", "sistem_podatki.py"), encoding="utf-8").read()
        for prepovedano in ("import socket", "urllib", "requests", "http.client", "pkexec", "sudo "):
            self.assertNotIn(prepovedano, vir)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux")
    def test_podatki_tega_racunalnika(self):
        p = sp.podatki("0.0.0")
        self.assertEqual(p["safeer"], "0.0.0")
        for k in ("sistem", "jedro", "procesor", "jeder", "pomnilnik", "diski", "naprave", "baterije", "zasloni", "komponente",
                  "osnova", "fizicnih_jeder", "arhitektura"):
            self.assertIn(k, p)
        self.assertEqual(p["komponente"][0]["ime"], "Python")
        json.dumps(p)                                   # gre cez most kot JSON


class VelikostMap(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.d, ignore_errors=True))

    def _datoteka(self, pot, bajtov):
        os.makedirs(os.path.dirname(pot), exist_ok=True)
        with open(pot, "wb") as f:
            f.write(os.urandom(bajtov))

    def test_velikosti_in_vrstni_red(self):
        self._datoteka(os.path.join(self.d, "velika", "a.bin"), 400_000)
        self._datoteka(os.path.join(self.d, "velika", "pod", "b.bin"), 300_000)
        self._datoteka(os.path.join(self.d, "mala", "c.txt"), 5_000)
        os.makedirs(os.path.join(self.d, "prazna"))
        self._datoteka(os.path.join(self.d, "tu.bin"), 50_000)
        # Simbolna povezava na veliko mapo se ne steje (sicer bi se velika stela dvakrat).
        os.symlink(os.path.join(self.d, "velika"), os.path.join(self.d, "povezava"))
        os.symlink(os.path.join(self.d, "velika"), os.path.join(self.d, "mala", "nazaj"))
        # Trda povezava: isti bloki samo enkrat (kot du).
        os.link(os.path.join(self.d, "velika", "a.bin"), os.path.join(self.d, "velika", "pod", "a2.bin"))
        r = sp.velikosti_map(self.d)
        self.assertTrue(r["ok"] and r["popolno"] and not r["preklicano"])
        self.assertEqual([m["ime"] for m in r["mape"]], ["velika", "mala", "prazna"])
        velika = r["mape"][0]
        self.assertGreaterEqual(velika["velikost"], 700_000)
        self.assertLess(velika["velikost"], 1_000_000)          # a.bin in a2.bin samo enkrat
        self.assertEqual(velika["datotek"], 3)
        self.assertLess(r["mape"][1]["velikost"], 100_000)       # povezava »nazaj« ne steje velike
        self.assertEqual(r["mape"][2]["velikost"], 0)
        self.assertTrue(all(m["popolno"] for m in r["mape"]))
        self.assertGreaterEqual(r["datoteke_tu"], 50_000)
        self.assertEqual(r["vseh_map"], 3)
        self.assertEqual(r["mape"][0]["pot"], os.path.join(os.path.realpath(self.d), "velika"))
        self.assertEqual(len(sp.velikosti_map(self.d, koliko=1)["mape"]), 1)

    def test_rok_ustavi_in_vrne_delni_izid(self):
        mapa = os.path.join(self.d, "veliko")
        os.makedirs(mapa)
        for i in range(1200):
            open(os.path.join(mapa, "%d.txt" % i), "w").close()
        casi = iter([0.0] + [100.0] * 10)       # zacetek, nato je rok ze mimo
        r = sp.velikosti_map(self.d, rok=6.0, ura=lambda: next(casi))
        self.assertTrue(r["ok"])
        self.assertFalse(r["popolno"] or r["preklicano"])
        self.assertFalse(r["mape"][0]["popolno"])
        r = sp.velikosti_map(self.d, najvec=600)
        self.assertFalse(r["popolno"])
        self.assertTrue(sp.velikosti_map(self.d)["popolno"])

    def test_preklic(self):
        mapa = os.path.join(self.d, "veliko")
        os.makedirs(mapa)
        for i in range(1200):
            open(os.path.join(mapa, "%d.txt" % i), "w").close()
        klici = []

        def ura():
            klici.append(1)
            if len(klici) == 2:                 # med stetjem: uporabnik pritisne Preklici (ali zacne novo stetje)
                sp.preklici_velikosti_map()
            return 0.0
        r = sp.velikosti_map(self.d, ura=ura)
        self.assertTrue(r["ok"] and r["preklicano"])
        self.assertFalse(r["popolno"])

    def test_napaka(self):
        r = sp.velikosti_map(os.path.join(self.d, "ni"))
        self.assertFalse(r["ok"])
        self.assertEqual(r["mape"], [])
        with open(os.path.join(self.d, "f"), "w"):
            pass
        self.assertFalse(sp.velikosti_map(os.path.join(self.d, "f"))["ok"])


class MostInBesedila(unittest.TestCase):
    def test_metode_mostu_v_niti(self):
        vir = open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8").read()
        ozadje = vir[vir.index("ozadje = {"):]
        for m in ('"sistemPodatki": lambda: sistem_podatki.podatki(RAZLICICA)', '"velikostiMap": lambda: sistem_podatki.velikosti_map(',
                  '"velikostiMapPreklici": sistem_podatki.preklici_velikosti_map'):
            self.assertIn(m, ozadje)

    def test_besedila_v_vseh_sestih_jezikih(self):
        js = open(os.path.join(KOREN, "assets", "os", "besedila-namizja.js"), encoding="utf-8").read()
        qml = open(os.path.join(KOREN, "assets", "os", "qml", "ORacunalniku.qml"), encoding="utf-8").read()
        kljuci = set(re.findall(r'koren\.t\("(rac\w+)"', qml)) | {"racNaslov", "racVelikostMap"}
        self.assertGreater(len(kljuci), 40)
        for k in sorted(kljuci):
            self.assertEqual(len(re.findall(r"^    %s: " % k, js, re.M)), 6, k)

    def test_vmesnik_v_datotekah(self):
        dat = open(os.path.join(KOREN, "assets", "os", "qml", "Datoteke.qml"), encoding="utf-8").read()
        self.assertIn('vir: { vrsta: "racunalnik", pot: "@racunalnik" }', dat)
        self.assertIn('objectName: "gumbVelikostMap"', dat)
        self.assertIn("ORacunalniku {", dat)


class ORacunalnikuQml(tq.NamizjeQml):
    """O tem racunalniku v namizju QML (offscreen): vnos v stranski vrstici, diski, strojna in programska oprema,
    »Velikost map« iz mape in preklic stetja ob odhodu."""

    def setUp(self):
        super().setUp()
        D = self.DOM
        self.odgovori["sistemPodatki"] = {
            "safeer": "0.4.91", "sistem": "Ubuntu 24.04.1 LTS", "osnova": "debian", "jedro": "6.8.0-45-generic",
            "namizje": "Safeer", "seja": "wayland", "arhitektura": "x86_64", "cas_delovanja_s": 93784,
            "procesor": "Intel(R) Core(TM) i7-1165G7", "jeder": 8, "fizicnih_jeder": 4,
            "pomnilnik": {"skupaj": 16e9, "na_voljo": 6e9, "izmenjalni": 2e9}, "graficne": ["Intel Iris Xe"],
            "racunalnik": "LENOVO ThinkPad X1", "komponente": [{"ime": "Python", "razlicica": "3.12.3"}, {"ime": "Qt", "razlicica": "6.8.2"}],
            "naprave": [{"naprava": "/dev/nvme0n1", "model": "Samsung SSD 980", "velikost": 512e9, "vrsta": "nvme", "odstranljiv": False}],
            "baterije": [{"ime": "BAT0", "model": "SMP", "napolnjenost": 73, "stanje": "prazni", "zdravje": 80}],
            "zasloni": [{"prikljucek": "eDP-1", "locljivost": "1920x1200", "vgrajen": True}],
            "diski": [{"naprava": "/dev/nvme0n1p2", "oznaka": "", "model": "", "datotecni_sistem": "ext4", "velikost": 500e9,
                       "prosto": 12e9, "pot": "/", "priklopljen": True, "odstranljiv": False, "sistem": True, "malo_prostora": True},
                      {"naprava": "/dev/sda1", "oznaka": "Varnost", "model": "", "datotecni_sistem": "exfat", "velikost": 2e12,
                       "prosto": 1.5e12, "pot": "/media/u/Varnost", "priklopljen": True, "odstranljiv": True, "sistem": False,
                       "malo_prostora": False}]}
        self.odgovori["velikostiMap"] = {
            "ok": True, "pot": D + "/Dokumenti", "datoteke_tu": 4096, "vseh_map": 2, "popolno": False, "preklicano": False,
            "mape": [{"ime": "Projekti", "pot": D + "/Dokumenti/Projekti", "velikost": 3e9, "datotek": 10, "popolno": True},
                     {"ime": "Arhiv", "pot": D + "/Dokumenti/Arhiv", "velikost": 1e9, "datotek": 5, "popolno": False}]}

    def test_o_tem_racunalniku(self):
        self._namizje()
        self.assertTrue(self._pocakaj(lambda: any((v.get("vir") or {}).get("vrsta") == "racunalnik"
                                                  for v in self._js("datoteke.lokalniViri"))))
        self._js('datoteke.odpri({ vrsta: "racunalnik", pot: "@racunalnik" })')
        self.assertTrue(self._klicano("sistemPodatki", []))
        o = self._obj("oRacunalniku")
        self.assertTrue(self._pocakaj(lambda: o.property("stanje") == "ok"))
        self.assertTrue(o.property("visible"))
        self.assertFalse(self._obj("seznamDatotek").property("visible"))
        self.assertTrue(self._pocakaj(lambda: self._obj("racDiskiSeznam").property("count") == 2))
        self.assertEqual(self._js("imeDiska(p.diski[0])", o), "Sistemski disk")
        self.assertIn("98 % zasedeno", self._js("opisDiska(p.diski[0])", o))
        self.assertEqual(self._js("imeDiska(p.diski[1])", o), "Varnost")
        strojna = {v[0]: v[1] for v in self._js("strojna()", o)}
        self.assertEqual(strojna["Procesor"], "Intel(R) Core(TM) i7-1165G7 · jedra: 4 · niti: 8")
        self.assertTrue(strojna["Pomnilnik"].startswith(self._js("koren.velikost(10e9)") + " "), strojna["Pomnilnik"])
        self.assertIn("73 %", strojna["Baterija"])
        self.assertIn("eDP-1 · 1920x1200", strojna["Zaslon"])
        self.assertIn("Samsung SSD 980", strojna["Shramba"])
        programska = {v[0]: v[1] for v in self._js("programska()", o)}
        self.assertEqual(programska["Različica Safeer OS"], "0.4.91")
        self.assertEqual(programska["Čas delovanja"], self._js('koren.t("racDni", { d: 1, h: 2 })'))
        self.assertIn("Qt 6.8.2", programska["Komponente"])
        self.assertTrue(self._pocakaj(lambda: self._obj("racStrojnaSeznam").property("count") == len(strojna)))
        # Klik na disk odpre njegovo mapo v Datotekah.
        self._js('odpriMapo("/media/u/Varnost")', o)
        self.assertEqual(self._js("datoteke.vir.vrsta"), "lokalno")
        self.assertTrue(self._klicano("mapa", ["/media/u/Varnost"]))

    def test_velikost_map_iz_mape_in_preklic(self):
        self._namizje()
        D = self.DOM
        self._js('datoteke.odpriLokalno("%s/Dokumenti")' % D)
        self.assertTrue(self._pocakaj(lambda: self._js("datoteke.prikazani.length") == 4))
        # Ozka plosca: gumba ni (pot mape ostane berljiva), »Velikost map« je v meniju mape.
        gumb = self._obj("gumbVelikostMap")
        self.assertFalse(gumb.property("visible"))
        self._js("datoteke.meniZa(0)")
        vnos = self._obj("vnosVelikostMap")
        self.assertTrue(self._pocakaj(lambda: self._obj("meniDatoteke").property("visible") and vnos.property("visible")))
        vnos.triggered.emit()
        self.assertTrue(self._klicano("velikostiMap", [D + "/Dokumenti/Projekti"]))
        self.assertEqual(self._js("datoteke.vir.vrsta"), "racunalnik")
        # Siroka plosca (velik zaslon): gumb v vrstici orodij mape.
        self._js('datoteke.odpriLokalno("%s/Dokumenti")' % D)
        self.koren.setProperty("width", 2560)
        self.koren.setProperty("height", 1440)
        self.assertTrue(self._pocakaj(lambda: gumb.property("visible")))
        gumb.klik.emit()
        self.assertTrue(self._klicano("velikostiMap", [D + "/Dokumenti"]))
        o = self._obj("oRacunalniku")
        self.assertTrue(self._pocakaj(lambda: o.property("stanjeMap") == "ok"))
        self.assertTrue(self._pocakaj(lambda: self._obj("racMapeSeznam").property("count") == 2))
        self.assertEqual(self._obj("racStanjeMap").property("text"), self._js('koren.t("racDelno")'))
        self.assertEqual(self._js("opisMape(mape.mape[1])", o), self._js('koren.t("racVsaj", { velikost: koren.velikost(1e9) })'))
        # Stetje tece (odgovor se ni prisel) in uporabnik gre drugam: stetje se ustavi.
        self._js('stanjeMap = "stejem"', o)
        self._js('datoteke.odpri({ vrsta: "nedavno", pot: "" })')
        self.assertTrue(self._klicano("velikostiMapPreklici", []))
        self.assertFalse(o.property("visible"))

    def test_napaka_mostu(self):
        self.odgovori["sistemPodatki"] = None
        self._namizje()
        self._js('datoteke.odpri({ vrsta: "racunalnik", pot: "@racunalnik" })')
        o = self._obj("oRacunalniku")
        self.assertTrue(self._pocakaj(lambda: o.property("stanje") == "napaka"))
        self.assertTrue(self._obj("racNapaka").property("visible"))


# Preizkusi namizja iz test_qml_enakost tecejo tam; tu samo O tem racunalniku.
for _ime in dir(tq.NamizjeQml):
    if _ime.startswith("test_"):
        setattr(ORacunalnikuQml, _ime, None)

if __name__ == "__main__":
    unittest.main()
