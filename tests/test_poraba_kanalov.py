"""Poraba kanalov Sporocil (gumb »Info«, lastnik 15. 10. 2026): branje lazni /proc, povprecja, vsota, pripis procesov
kanalom (sonda za spletne kanale, drevo procesov za programe) in porocilo. core/poraba_kanalov.py,
core/os_poraba_kanalov.py."""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from core import os_poraba_kanalov as op
from core import poraba_kanalov as p


class LazniProc:
    """Mapa v obliki /proc: <pid>/stat, comm, smaps_rollup."""

    def __init__(self):
        self.koren = tempfile.mkdtemp(prefix="safeer-proc-")

    def proces(self, pid, stars, ime, pss_kib, tiki=0, utime=None):
        d = os.path.join(self.koren, str(pid))
        os.makedirs(d, exist_ok=True)
        ut = tiki if utime is None else utime
        st = tiki - ut
        polja = ["S", str(stars)] + ["0"] * 9 + [str(ut), str(st)] + ["0"] * 10
        with open(os.path.join(d, "stat"), "w") as f:
            f.write("%d (%s) %s\n" % (pid, ime, " ".join(polja)))
        with open(os.path.join(d, "comm"), "w") as f:
            f.write(ime + "\n")
        with open(os.path.join(d, "smaps_rollup"), "w") as f:
            f.write("00400000-ffffffff ---p 00000000 00:00 0 [rollup]\nRss: %d kB\nPss: %d kB\n" % (pss_kib * 2, pss_kib))

    def odstrani(self, pid):
        shutil.rmtree(os.path.join(self.koren, str(pid)), ignore_errors=True)

    def proc(self, flatpak=False):
        pr = p.Proc(self.koren)
        pr.hz = 100
        pr.flatpak = flatpak
        return pr


class Branje(unittest.TestCase):
    def setUp(self):
        self.l = LazniProc()
        self.addCleanup(shutil.rmtree, self.l.koren, True)

    def test_drevo_pss_tiki_in_koren_programa(self):
        self.l.proces(1, 0, "systemd", 1)
        self.l.proces(100, 1, "signal", 200 * 1024, 500)
        self.l.proces(101, 100, "signal", 50 * 1024, 30)     # okno pripada podprocesu z istim imenom
        self.l.proces(102, 101, "signal-render", 80 * 1024, 70)
        self.l.proces(200, 1, "drugo", 999)
        pr = self.l.proc()
        self.assertEqual(sorted(pr.drevo(100)), [100, 101, 102])
        self.assertEqual(pr.koren_programa(101), 100)
        self.assertEqual(pr.pss_kib(102), 80 * 1024)
        self.assertEqual(pr.tiki(100), 500)
        self.assertEqual(pr.drevo(999), [], "proces, ki ga ni")
        self.assertFalse(pr.zivi(999))

    def test_brez_smaps_rollup_vmrss(self):
        self.l.proces(5, 1, "x", 10)
        os.remove(os.path.join(self.l.koren, "5", "smaps_rollup"))
        with open(os.path.join(self.l.koren, "5", "status"), "w") as f:
            f.write("Name:\tx\nVmRSS:\t   2048 kB\n")
        self.assertEqual(self.l.proc().pss_kib(5), 2048)

    def test_cpu_odstotek(self):
        self.assertEqual(p.cpu_odstotek(100, 400, 30.0, 100), 10.0)       # 3 s procesorja v 30 s = 10 % jedra
        self.assertIsNone(p.cpu_odstotek(400, 100, 30.0, 100), "stevec se zmanjsa: drug proces")
        self.assertIsNone(p.cpu_odstotek(0, 1, 0, 100))

    def test_povprecje_ure_in_od_zagona(self):
        z = p.Zgodovina(okno_s=3600)
        z.dodaj("k", 0.0, 100.0, 2.0)
        z.dodaj("k", 30.0, 200.0, None)            # procesor tega vzorca ni znan: ne steje v povprecje
        z.dodaj("k", 4000.0, 300.0, 4.0)           # prva dva sta zdaj starejsa od ure
        s = z.povzetek("k", zdaj=4000.0)
        self.assertEqual((s["mem_ura"], s["cpu_ura"], s["vzorcev"]), (300.0, 4.0, 1))
        self.assertEqual((s["mem_zagon"], s["cpu_zagon"]), (200.0, 3.0))
        self.assertIsNone(z.povzetek("ni", zdaj=1.0)["mem_ura"])

    def test_vsota_in_delna_vsota(self):
        v = [{"mem_ura": 100.0, "disk": 10, "vklopljen": True, "ni_merljivo": []},
             {"mem_ura": None, "disk": 5, "vklopljen": True, "ni_merljivo": ["mem_ura"]},
             {"mem_ura": None, "disk": 7, "vklopljen": False, "ni_merljivo": ["mem_ura"]}]
        s = p.sestej(v, ("mem_ura", "disk"))
        self.assertEqual((s["mem_ura"], s["disk"]), (100.0, 22))
        self.assertTrue(s["mem_ura_delno"], "vklopljen kanal brez meritve: vsota je spodnja meja")
        self.assertFalse(s["disk_delno"])

    def test_velikost_mape(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        os.makedirs(os.path.join(d, "a", "b"))
        for pot, n in (("x", 10), ("a/y", 20), ("a/b/z", 30)):
            with open(os.path.join(d, pot), "wb") as f:
                f.write(b"0" * n)
        os.symlink("/etc/passwd", os.path.join(d, "povezava"))
        self.assertEqual(p.velikost_mape(d), 60, "povezave ne steje")
        self.assertEqual(p.velikost_mape(os.path.join(d, "ni")), 0)


class _GLib:
    PRIORITY_LOW = 300

    def __init__(self):
        self.casovniki = []

    def timeout_add_seconds(self, s, f, *a, **k):
        self.casovniki.append((s * 1000, f, a))
        return len(self.casovniki)

    def timeout_add(self, ms, f, *a, **k):
        self.casovniki.append((ms, f, a))
        return len(self.casovniki)

    def idle_add(self, f, *a, **k):
        self.casovniki.append((0, f, a))
        return len(self.casovniki)

    def source_remove(self, _i):
        pass

    def pozeni(self):
        while self.casovniki:
            _ms, f, a = self.casovniki.pop(0)
            f(*a)


class _Pogled:
    def __init__(self, uri, ob_sondi):
        self.uri, self.ob_sondi, self.sond = uri, ob_sondi, 0

    def get_uri(self):
        return self.uri

    def connect(self, *_a):
        return 1

    def evaluate_javascript(self, koda, _d, svet, *_a):
        assert svet == op.SONDA_SVET, "sonda tece v locenem svetu (stran je ne vidi)"
        assert "performance.now" in koda
        self.sond += 1
        self.ob_sondi()


class _Z:
    def __init__(self, aplikacija=None, program=None, pid=0):
        self.aplikacija, self.program, self.pid = aplikacija, program, pid


class _Kanali:
    def __init__(self, seznam):
        self._s = seznam
        self.zivi = {}
        self.kanali = self

    def seznam(self):
        return self._s

    def jedro(self):
        return None


class Poraba(unittest.TestCase):
    def setUp(self):
        self.l = LazniProc()
        self.addCleanup(shutil.rmtree, self.l.koren, True)
        self.l.proces(10, 1, "python3", 100 * 1024, 1000)               # Safeer OS
        self.l.proces(11, 10, "WebKitNetworkPr", 40 * 1024, 50)
        self.l.proces(12, 10, "WebKitWebProces", 150 * 1024, 200)       # kanal A
        self.l.proces(13, 10, "WebKitWebProces", 250 * 1024, 300)       # kanal B
        self.l.proces(14, 10, "WebKitWebProces", 30 * 1024, 10)         # servisni delavec
        self.l.proces(20, 1, "viber", 300 * 1024, 400)                  # program (ni otrok Safeer OS)
        self.l.proces(21, 20, "QtWebEngineProc", 100 * 1024, 100)
        self.kanali = _Kanali([
            {"id": "a", "ime": "Telegram", "katalog": "telegram", "url": "https://web.telegram.org/", "vklopljen": True},
            {"id": "b", "ime": "WhatsApp", "katalog": "whatsapp", "url": "https://web.whatsapp.com/", "vklopljen": True},
            {"id": "v", "ime": "Viber", "katalog": "viber", "url": "", "vklopljen": True},
            {"id": "x", "ime": "Discord", "katalog": "discord", "url": "https://discord.com/app", "vklopljen": False}])
        self.glib = _GLib()

        class _Api:
            @staticmethod
            def seznam_kanalov():
                return [{"id": "e", "ime": "Posta", "vrsta": "email", "vklopljen": True}]

            @staticmethod
            def velikost_kanalov():
                return {"e": 4096}
        self.poraba = op.PorabaKanalov(self.glib, self.kanali, lambda: _Api, proc=self.l.proc(), koren_pid=10)

    def _sonda_kanala(self, kid, pid_kanala, uri):
        """Pogled, ki med sondo »porabi« procesor v procesu pid_kanala (kot pravi WebKit)."""
        def ob_sondi():
            t = self.l.proc().tiki(pid_kanala)
            self.l.proces(pid_kanala, 10, "WebKitWebProces", 150 * 1024 if pid_kanala == 12 else 250 * 1024, t + 25)

        class _A:
            pogled = _Pogled(uri, ob_sondi)
        return _Z(aplikacija=_A())

    def test_sonda_najde_proces_kanala(self):
        self.kanali.zivi["a"] = self._sonda_kanala("a", 12, "https://web.telegram.org/k/")
        self.kanali.zivi["b"] = self._sonda_kanala("b", 13, "https://web.whatsapp.com/")
        self.poraba.sonda("a")
        self.poraba.sonda("b")
        self.glib.pozeni()
        self.assertEqual(self.poraba.pid_spleta["a"], (12, "telegram.org"))
        self.assertEqual(self.poraba.pid_spleta["b"], (13, "whatsapp.com"))

    def test_sonda_brez_jasnega_izida_ne_ugiba(self):
        def ob_sondi():                          # dva procesa porabita enako: ni jasno, kateri je kanalov
            for pid in (12, 13):
                self.l.proces(pid, 10, "WebKitWebProces", 1, self.l.proc().tiki(pid) + 25)

        class _A:
            pogled = _Pogled("https://web.telegram.org/", ob_sondi)
        self.kanali.zivi["a"] = _Z(aplikacija=_A())
        self.poraba.sonda("a")
        self.glib.pozeni()
        self.assertNotIn("a", self.poraba.pid_spleta)
        self.assertEqual(_A.pogled.sond, op.SONDA_POSKUSOV, "poskusi znova, nato odneha")

    def test_sonda_pod_obremenitvijo(self):
        """18. 10. 2026: pod obremenitvijo je zanka sonde dobila le del jedra (+6 tikov), sosednji proces, ki se je
        nalagal, pa je imel med sondo manj kot v ozadju. Kanal je jasno prevladal - sonda ga mora najti; sum (+2)
        pa ne sme odlociti."""
        for dodatek, najde in ((6, True), (2, False)):
            with self.subTest(dodatek=dodatek):
                self.setUp()

                def ob_sondi(d=dodatek):
                    self.l.proces(12, 10, "WebKitWebProces", 1, self.l.proc().tiki(12) + d)

                class _A:
                    pogled = _Pogled("https://web.telegram.org/", ob_sondi)
                self.kanali.zivi["a"] = _Z(aplikacija=_A())
                self.poraba.sonda("a")
                self.glib.pozeni()
                self.assertEqual("a" in self.poraba.pid_spleta, najde)

    def test_vzorci_porocilo_in_vsota(self):
        self.kanali.zivi["a"] = self._sonda_kanala("a", 12, "https://web.telegram.org/")
        self.kanali.zivi["b"] = self._sonda_kanala("b", 13, "https://web.whatsapp.com/")
        self.kanali.zivi["v"] = _Z(program={"ukaz": ["viber"]}, pid=20)
        self.poraba.pid_spleta = {"a": (12, "telegram.org"), "b": (13, "whatsapp.com")}
        ura = [1000.0]
        with mock.patch.object(op.time, "monotonic", lambda: ura[0]):
            self.assertTrue(self.poraba._vzorci())
            ura[0] = 1030.0
            # v 30 s: kanal A 3 s procesorja (300 tikov), program 60 tikov
            self.l.proces(12, 10, "WebKitWebProces", 150 * 1024, 200 + 300)
            self.l.proces(20, 1, "viber", 300 * 1024, 400 + 60)
            self.assertTrue(self.poraba._vzorci())
        s = self.poraba.zgodovina.povzetek("a", zdaj=1030.0)
        self.assertEqual((s["mem_ura"], s["cpu_ura"], s["vzorcev"]), (150.0, 10.0, 2))
        self.assertEqual(self.poraba.zgodovina.povzetek("v", zdaj=1030.0)["mem_ura"], 400.0, "drevo programa")
        self.assertEqual(self.poraba.zgodovina.povzetek("v", zdaj=1030.0)["cpu_ura"], 2.0)
        self.assertEqual(self.poraba.vzorcev, 2)
        izid = []
        self.poraba._disk = {"cas": op.time.monotonic(), "splet": {"telegram.org": 2048, "whatsapp.com": 0}, "api": {"e": 4096}}
        self.poraba.porocilo(izid.append)
        r = izid[0]
        vrstice = {v["id"]: v for v in r["kanali"]}
        self.assertEqual(vrstice["a"]["mem_trenutno"], 150.0)
        self.assertEqual(vrstice["a"]["disk"], 2048)
        self.assertEqual(vrstice["v"]["mem_trenutno"], 400.0)
        self.assertIn("disk", vrstice["v"]["ni_merljivo"], "podatki programa: ni merljivo")
        self.assertFalse(vrstice["x"]["vklopljen"])
        self.assertIsNone(vrstice["x"]["mem_trenutno"])
        self.assertEqual(vrstice["e"]["razlog"], "safeer", "kanal API: vkljuceno v Safeer OS, ne izmisljena stevilka")
        self.assertIsNone(vrstice["e"]["mem_trenutno"])
        self.assertEqual(vrstice["e"]["disk"], 4096)
        self.assertEqual(r["skupaj"]["mem_trenutno"], 150.0 + 250.0 + 400.0)
        self.assertTrue(r["skupaj"]["mem_trenutno_delno"], "kanal API ni vstet - vmesnik pove")
        self.assertEqual(r["skupaj"]["disk"], 2048 + 4096)
        self.assertEqual(r["skupno"]["drugi"]["mem_trenutno"], 30.0, "servisni delavec ni pripisan kanalu")
        self.assertEqual(r["skupno"]["omrezje"]["mem_trenutno"], 40.0)
        self.assertEqual(r["skupno"]["safeer"]["mem_trenutno"], 100.0)
        self.assertIsNotNone(r["cena_ms"])

    def test_deljen_proces_razdeljen(self):
        self.kanali.zivi["a"] = _Z(aplikacija=object())
        self.kanali.zivi["b"] = _Z(aplikacija=object())
        self.poraba.pid_spleta = {"a": (12, "telegram.org"), "b": (12, "telegram.org")}
        m = self.poraba._vse_meritve({})
        self.assertEqual((m["a"]["mem"], m["b"]["mem"]), (75.0, 75.0))
        self.assertTrue(m["a"]["deljeno"])

    def test_mrtev_proces_sprozi_novo_sondo(self):
        self.kanali.zivi["a"] = self._sonda_kanala("a", 12, "https://web.telegram.org/")
        self.poraba.pid_spleta = {"a": (99, "telegram.org")}
        m = self.poraba._vse_meritve({})
        self.assertEqual(m["a"]["razlog"], "sonda")
        self.assertNotIn("a", self.poraba.pid_spleta)
        self.glib.pozeni()
        self.assertEqual(self.poraba.pid_spleta["a"][0], 12)

    def test_vzorcenje_samo_z_zivimi_kanali(self):
        self.poraba.uskladi()
        self.assertEqual(self.glib.casovniki, [], "brez kanalov se ne meri nic")
        self.kanali.zivi["a"] = _Z(aplikacija=object())
        self.poraba.uskladi()
        self.assertEqual(self.glib.casovniki[0][0], p.VZOREC_S * 1000)
        self.kanali.zivi.clear()
        self.assertFalse(self.poraba._vzorci(), "zadnji kanal izklopljen: casovnik se ustavi")


class Flatpak(unittest.TestCase):
    """Zivi preizkus 15. 10. 2026 (Flatpak Safeer OS, WhatsApp): sonda ni nasla procesa kanala. Pravo drevo s testnega PC
    (pid ppid comm v nasem imenskem prostoru procesov): spletni procesi niso potomci Safeer OS - zazene jih
    flatpak-spawn --sandbox, njihov bwrap je otrok pid 1 (bwrap nasega peskovnika). Lazni /proc je to drevo."""

    def setUp(self):
        self.l = LazniProc()
        self.addCleanup(shutil.rmtree, self.l.koren, True)
        for pid, stars, ime in ((1, 0, "bwrap"), (168, 2, "flatpak-spawn"), (177, 1, "bwrap"), (242, 2, "flatpak-spawn"),
                                (249, 1, "bwrap"), (269, 2, "flatpak-spawn"), (274, 1, "bwrap"), (364, 2, "flatpak-spawn"),
                                (379, 1, "bwrap")):
            self.l.proces(pid, stars, ime, 1)
        self.l.proces(2, 1, "python3", 200 * 1024, 100)                  # Safeer OS
        self.l.proces(151, 2, "WebKitNetworkPr", 30 * 1024, 5)
        self.l.proces(178, 177, "WebKitWebProces", 180 * 1024, 300)      # kanal
        self.l.proces(250, 249, "WebKitWebProces", 20 * 1024, 3)
        self.l.proces(275, 274, "WebKitWebProces", 20 * 1024, 3)
        self.l.proces(380, 379, "WebKitWebProces", 20 * 1024, 3)
        self.kanali = _Kanali([{"id": "w", "ime": "WhatsApp", "katalog": "whatsapp",
                                "url": "https://web.whatsapp.com/", "vklopljen": True}])
        self.glib = _GLib()
        self.poraba = op.PorabaKanalov(self.glib, self.kanali, lambda: None, proc=self.l.proc(flatpak=True), koren_pid=2)

    def _kanal(self, pid):
        def ob_sondi():
            self.l.proces(pid, 177, "WebKitWebProces", 180 * 1024, self.l.proc().tiki(pid) + 25)

        class _A:
            pogled = _Pogled("https://web.whatsapp.com/", ob_sondi)
        return _Z(aplikacija=_A())

    def test_procesi_v_podpeskovniku_so_nasi(self):
        pr = self.l.proc(flatpak=True)
        self.assertEqual(pr.nasi(2, "WebKitWebProces"), ([], [178, 250, 275, 380]))
        self.assertEqual(pr.nasi(2, "WebKitNetworkPr"), ([151], []))
        # Zunaj Flatpaka bi veriga do pid 1 pomenila tuj program: pravilo velja samo tam.
        self.assertEqual(self.l.proc(flatpak=False).nasi(2, "WebKitWebProces"), ([], []))

    def test_tuji_procesi_niso_nasi(self):
        # Zunaj Flatpaka: drug program z WebKitom (veriga do pid 1) ni nas; nasi so potomci.
        self.l.proces(50, 1, "epiphany", 1)
        self.l.proces(51, 50, "WebKitWebProces", 1)
        self.l.proces(60, 2, "bwrap", 1)
        self.l.proces(61, 60, "WebKitWebProces", 1)
        for pid in (177, 178, 249, 250, 274, 275, 379, 380):
            self.l.odstrani(pid)
        self.assertEqual(self.l.proc(flatpak=False).nasi(2, "WebKitWebProces"), ([61], []))

    def test_sonda_najde_kanal_v_podpeskovniku(self):
        self.kanali.zivi["w"] = self._kanal(178)
        self.poraba.sonda("w")
        self.glib.pozeni()
        self.assertEqual(self.poraba.pid_spleta["w"][0], 178)
        r = []
        self.poraba._disk["cas"] = op.time.monotonic()
        self.poraba.porocilo(r.append)
        self.assertEqual(r[0]["kanali"][0]["mem_trenutno"], 180.0)
        self.assertEqual(r[0]["skupno"]["drugi"]["procesov"], 3, "ostali spletni procesi v vrstici drugih procesov")

    def test_brez_smaps_priblizek_rss(self):
        # Proces v drugem uporabniskem imenskem prostoru: smaps_rollup ni berljiv (ptrace), status je.
        os.remove(os.path.join(self.l.koren, "178", "smaps_rollup"))
        with open(os.path.join(self.l.koren, "178", "status"), "w") as f:
            f.write("Name:\tWebKitWebProces\nVmRSS:\t 409600 kB\n")
        self.kanali.zivi["w"] = _Z(aplikacija=object())
        self.poraba.pid_spleta = {"w": (178, "whatsapp.com")}
        m = self.poraba._vse_meritve({})
        self.assertEqual(m["w"]["mem"], 400.0)
        self.assertTrue(m["w"]["priblizek"], "vmesnik pokaze »≈« in namig")

    def test_neuspela_sonda_se_ponovi(self):
        for pid in (178, 250, 275, 380):
            self.l.odstrani(pid)       # spletni proces se ni zagnan (kanal se nalaga ob zagonu)
        self.kanali.zivi["w"] = self._kanal(178)
        with mock.patch("builtins.print") as izpis:
            self.poraba.sonda("w")
            self.glib.casovniki.pop(0)[1]()          # prva sonda: ni kandidatov
        self.assertNotIn("w", self.poraba.pid_spleta)
        self.assertIn("brez kandidatov", str(izpis.call_args))
        self.assertEqual(self.glib.casovniki[0][0], 2000, "znova cez 2 s")
        self.l.proces(178, 177, "WebKitWebProces", 180 * 1024, 300)   # proces je medtem nastal
        self.glib.pozeni()
        self.assertEqual(self.poraba.pid_spleta["w"][0], 178)

    def test_odprto_okno_sprozi_sondo(self):
        self.kanali.zivi["w"] = self._kanal(178)
        self.poraba._poskusi["w"] = op.SONDA_POSKUSOV           # hitri poskusi so ze porabljeni
        self.poraba.ob_prikazu("w")
        self.glib.pozeni()
        self.assertEqual(self.poraba.pid_spleta["w"][0], 178)

    def test_vzorec_ponovi_sondo_s_premorom(self):
        self.kanali.zivi["w"] = self._kanal(178)
        ura = [1000.0]
        with mock.patch.object(op.time, "monotonic", lambda: ura[0]):
            self.poraba._zadnja_sonda["w"] = 990.0
            self.poraba._vse_meritve({})
            self.assertEqual(self.glib.casovniki, [], "premor: ne prej kot 60 s po zadnji sondi")
            ura[0] = 1051.0
            self.poraba._vse_meritve({})
            self.glib.pozeni()
        self.assertEqual(self.poraba.pid_spleta["w"][0], 178)


if __name__ == "__main__":
    unittest.main()
