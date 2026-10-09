"""Safeer OS brez Safeer Control (paket deb): namestitev Controla v programu, enkratna kartica, stanje 'rc'.

Paket safeer-os Control od 0.4.76 le priporoca: dvoklik v Mintu (Captain, GDebi) bere samo Depends, safeer-control pa
ni v nobenem skladiscu, zato se safeer-os 0.4.75 z dvoklikom ni dal namestiti. Safeer OS dela brez Controla (brez
Linka in naprav) in ga na klik uporabnika namesti sam - po isti podpisani poti kot posodobitve (core/os_posodobitve).
"""
import os
import re
import shutil
import subprocess
import tempfile
import threading
import unittest
from unittest import mock

from core import os_posodobitve as op
from core import os_programi

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MANIFEST = {
    "android": {},
    "linux": {"safeer-os": {"razlicica": "0.4.80", "deb": {"url": "https://safeer.si/os/safeer-os_0.4.80_all.deb", "sha256": "a" * 64, "velikost": 1},
                            "tema_namescena_deb": {"url": "https://safeer.si/os/safeer-os-tema_0.4.80_all.deb", "sha256": "b" * 64, "velikost": 1}},
              "safeer-control": {"razlicica": "2.1.80", "deb": {"url": "https://safeer.si/os/safeer-control_2.1.80_all.deb",
                                                                "sha256": "c" * 64, "velikost": 545430}}},
    "stran": "https://safeer.si/os/",
}


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class NamestiControl(unittest.TestCase):
    def setUp(self):
        import safeer_os
        self.os_ = safeer_os
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.prenosi = []
        self.namestitve = []
        self.zagoni = []
        for cilj, kaj in ((safeer_os, {"_ukaz_controla": mock.DEFAULT, "_zazeni_control_po_namestitvi": mock.DEFAULT}),
                          (op, {"nacin_namestitve": mock.DEFAULT, "prenesi_manifest": mock.DEFAULT, "namescena_razlicica": mock.DEFAULT,
                                "prenesi": mock.DEFAULT, "namesti_linux": mock.DEFAULT})):
            p = mock.patch.multiple(cilj, **kaj)
            self.m = dict(getattr(self, "m", {}), **p.start())
            self.addCleanup(p.stop)
        p = mock.patch.object(safeer_os.GLib, "get_user_cache_dir", return_value=self.tmp.name)
        p.start()
        self.addCleanup(p.stop)
        self.m["_ukaz_controla"].return_value = None
        self.m["nacin_namestitve"].return_value = "deb"
        self.m["namescena_razlicica"].return_value = ""          # paketa safeer-control ni (ali je 'rc')
        self.m["prenesi_manifest"].return_value = MANIFEST
        self.m["prenesi"].side_effect = self._prenesi
        self.m["namesti_linux"].side_effect = self._namesti
        self.m["_zazeni_control_po_namestitvi"].side_effect = lambda: self.zagoni.append(1) or True
        self.izid_apt = subprocess.CompletedProcess(["pkexec"], 0, "", "")

    def _prenesi(self, url, cilj, sha256, velikost=0, napredek=None, prekini=None, agent=""):
        self.prenosi.append((url, cilj, sha256, velikost, agent))
        napredek(velikost // 2, velikost)
        os.makedirs(os.path.dirname(cilj), exist_ok=True)       # kot pravi prenesi
        with open(cilj, "wb") as f:
            f.write(b"deb")
        return cilj

    def _namesti(self, nacin, poti):
        self.namestitve.append((nacin, list(poti), [os.path.exists(p) for p in poti]))
        return self.izid_apt

    def _lazna(self):
        lazna = mock.MagicMock()
        lazna.posodabljanje = op.Posodabljanje()
        lazna.namescanje_controla = op.Posodabljanje()
        lazna.posodobitve = {"izid": {"nove": []}, "cas": 1.0, "napaka": ""}
        return lazna

    def _namesti_control(self, lazna=None):
        lazna = lazna or self._lazna()
        izid = self.os_.SafeerOS._namesti_control(lazna)
        if lazna.namescanje_controla.nit is not None:
            lazna.namescanje_controla.nit.join(10)
            self.assertFalse(lazna.namescanje_controla.tece())
        return izid, lazna, self.os_.SafeerOS._namesti_control_stanje(lazna)

    def test_uspeh(self):
        izid, lazna, st = self._namesti_control()
        self.assertEqual(izid, {"ok": True})
        self.assertEqual((st["faza"], st["koda"], st["odstotek"], st["tece"]), ("koncano", "", 100, False))
        # Podpisan seznam (prenesi_manifest preveri podpis Ed25519 in svezino) in SHA-256 iz njega - nic mimo tega.
        self.m["prenesi_manifest"].assert_called_once_with()
        deb = MANIFEST["linux"]["safeer-control"]["deb"]
        self.assertEqual(len(self.prenosi), 1)
        url, cilj, sha256, velikost, agent = self.prenosi[0]
        self.assertEqual((url, sha256, velikost), (deb["url"], deb["sha256"], deb["velikost"]))
        self.assertEqual(os.path.dirname(cilj), os.path.join(self.tmp.name, "safeer-os", "posodobitve"))
        self.assertTrue(agent.startswith("SafeerOS/"))
        # En sam paket (ne paket videza ne posodobitev Safeer OS), prek pkexec apt-get (namesti_linux 'deb').
        self.assertEqual(self.namestitve, [("deb", [cilj], [True])])
        self.assertFalse(os.path.exists(cilj))                    # po namestitvi pospravljeno
        self.assertEqual(self.zagoni, [1])                        # Control zagnan takoj: Link dela brez odjave
        self.assertIsNone(lazna.posodobitve["izid"])              # naslednja preverba posodobitev vidi Control

    def test_sha256_se_ne_ujema(self):
        self.m["prenesi"].side_effect = ValueError("SHA-256 se ne ujema")
        izid, lazna, st = self._namesti_control()
        self.assertEqual(izid, {"ok": True})
        self.assertEqual((st["faza"], st["koda"]), ("napaka", "sha256"))
        self.assertEqual(self.namestitve, [])                     # nepreverjen paket nikoli ne pride do apt-get
        self.assertEqual(self.zagoni, [])

    def test_zaklenjen_dpkg(self):
        """Mintov Upravitelj posodobitev ravno namesca: apt-get ne dobi zaklepa -> prijazno »poskusi cez minuto«."""
        for stderr in ("E: Could not get lock /var/lib/dpkg/lock-frontend. It is held by process 4242 (mintUpdate)\n"
                       "E: Unable to acquire the dpkg frontend lock (/var/lib/dpkg/lock-frontend), is another process using it?",
                       # pkexec ohrani LANG: apt v slovenscini, pot zaklepa pa ostane ista.
                       "E: Zaklepa /var/lib/dpkg/lock-frontend ni bilo mogoce dobiti."):
            with self.subTest(stderr=stderr[:30]):
                self.namestitve.clear()
                self.izid_apt = subprocess.CompletedProcess(["pkexec"], 100, "", stderr)
                izid, lazna, st = self._namesti_control()
                self.assertEqual((st["faza"], st["koda"]), ("napaka", "zaklenjeno"))
                self.assertEqual(len(self.namestitve), 1)
                self.assertEqual(self.zagoni, [])
        besedila = _beri("assets", "os", "besedila.js")
        self.assertIn('"ctrlNapaka_zaklenjeno": "Posodobitve sistema so v teku, poskusi čez minuto."', besedila)

    def test_preklicano_geslo_in_druge_napake_apt(self):
        self.izid_apt = subprocess.CompletedProcess(["pkexec"], 126, "", "")
        self.assertEqual(self._namesti_control()[2]["koda"], "preklicano")
        self.izid_apt = subprocess.CompletedProcess(["pkexec"], 100, "", "E: Unmet dependencies.")
        st = self._namesti_control()[2]
        self.assertEqual((st["koda"], st["podrobnosti"]), ("apt", "E: Unmet dependencies."))

    def test_napake_pred_prenosom(self):
        self.m["prenesi_manifest"].side_effect = op.NapakaPodpisa("podpis seznama različic ni veljaven")
        self.assertEqual(self._namesti_control()[2]["koda"], "podpis")
        self.m["prenesi_manifest"].side_effect = op.NapakaSvezine("seznam razlicic je pretekel")
        self.assertEqual(self._namesti_control()[2]["koda"], "podpis")
        self.m["prenesi_manifest"].side_effect = OSError("Network is unreachable")
        self.assertEqual(self._namesti_control()[2]["koda"], "omrezje")
        # Seznam brez veljavnega paketa deb (brez SHA-256): nic se ne prenese.
        self.m["prenesi_manifest"].side_effect = None
        slab = {"android": {}, "linux": {"safeer-control": {"razlicica": "2.1.80", "deb": {"url": "https://safeer.si/x.deb", "sha256": ""}}}}
        self.m["prenesi_manifest"].return_value = slab
        self.assertEqual(self._namesti_control()[2]["koda"], "ni_paketa")
        self.assertEqual((self.prenosi, self.namestitve, self.zagoni), ([], [], []))

    def test_ne_deb_ze_namescen_in_hkratno(self):
        for nacin in ("flatpak", "appimage", "neznano"):
            with self.subTest(nacin=nacin):
                self.m["nacin_namestitve"].return_value = nacin
                izid, lazna, st = self._namesti_control()
                self.assertEqual(izid, {"ok": False, "koda": "rocno", "stran": "https://safeer.si/control/"})
        self.m["nacin_namestitve"].return_value = "deb"
        self.m["_ukaz_controla"].return_value = ["/usr/bin/safeer-control"]
        self.assertEqual(self._namesti_control()[0], {"ok": False, "koda": "ze_namescen"})
        self.m["_ukaz_controla"].return_value = None
        # Paket je namescen ('ii'), le ukaza ni na poti: nic ne prenasamo in ne namescamo (nikoli cez novejsega).
        with mock.patch.object(op, "namescena_razlicica", return_value="2.1.99") as dpkg:
            self.assertEqual(self._namesti_control()[0], {"ok": False, "koda": "ze_namescen"})
            dpkg.assert_called_once_with("safeer-control")
        # Dva apt-get hkrati ne: med posodobitvijo (ali drugo namestitvijo) se namestitev ne zacne.
        lazna = self._lazna()
        konec = threading.Event()
        lazna.posodabljanje.zacni(lambda p: konec.wait(5))
        try:
            self.assertEqual(self.os_.SafeerOS._namesti_control(lazna), {"ok": False, "koda": "tece"})
        finally:
            konec.set()
            lazna.posodabljanje.nit.join(5)
        self.assertEqual((self.m["prenesi_manifest"].call_count, self.prenosi, self.namestitve), (0, [], []))

    def test_posodobitev_pocaka_namestitev_controla(self):
        lazna = self._lazna()
        lazna._posodobitve_stanje.return_value = {"nove": [{"kljuc": "safeer-os", "datoteka": {"url": "https://x/a.deb"}}],
                                                  "nacin": "deb", "stran": ""}
        konec = threading.Event()
        lazna.namescanje_controla.zacni(lambda p: konec.wait(5))
        try:
            self.assertEqual(self.os_.SafeerOS._posodobi(lazna), {"ok": False, "koda": "tece"})
        finally:
            konec.set()
            lazna.namescanje_controla.nit.join(5)

    def test_posodobitev_ob_kliku_znova_preveri_namescene_pakete(self):
        """Izid tihe preverbe je star do 6 ur. Paket videza in Control, odstranjena po preverbi, ob kliku »Posodobi«
        ne gresta v apt-get (paket videza bi ob naslednji prijavi spet preklopil namizje v Safeer OS)."""
        izid = op.preveri("linux", {"safeer-os": "0.4.75", "safeer-control": "2.1.73"}, MANIFEST, nacin="deb", tema=True)
        self.assertEqual([("tema" in n, n["kljuc"]) for n in izid["nove"]], [(True, "safeer-os"), (False, "safeer-control")])
        for namesceni, pricakovano in (
                ({"safeer-os": "0.4.75"}, ["safeer-os_0.4.80_all.deb"]),
                ({"safeer-os": "0.4.75", "safeer-os-tema": "0.4.75", "safeer-control": "2.1.73"},
                 ["safeer-os_0.4.80_all.deb", "safeer-os-tema_0.4.80_all.deb", "safeer-control_2.1.80_all.deb"])):
            with self.subTest(namesceni=sorted(namesceni)):
                self.namestitve.clear()
                self.m["namescena_razlicica"].side_effect = lambda paket: namesceni.get(paket, "")
                lazna = self._lazna()
                lazna._posodobitve_stanje.return_value = {"nove": izid["nove"], "nacin": "deb", "stran": MANIFEST["stran"]}
                self.assertEqual(self.os_.SafeerOS._posodobi(lazna), {"ok": True})
                lazna.posodabljanje.nit.join(10)
                self.assertEqual(lazna.posodabljanje.faza, "koncano")
                self.assertEqual(len(self.namestitve), 1)
                nacin, poti, _ = self.namestitve[0]
                self.assertEqual((nacin, [os.path.basename(p) for p in poti]), ("deb", pricakovano))
        self.assertEqual(lazna.posodabljanje.sporocilo, "Safeer OS 0.4.80, Safeer Control 2.1.80")
        # Nic vec za namestiti (Safeer OS je medtem ze posodobljen): nic ne prenasamo, izid se zavrze.
        self.namestitve.clear()
        self.m["namescena_razlicica"].side_effect = lambda paket: {"safeer-os": "0.4.80"}.get(paket, "")
        lazna = self._lazna()
        lazna._posodobitve_stanje.return_value = {"nove": izid["nove"], "nacin": "deb", "stran": MANIFEST["stran"]}
        self.assertEqual(self.os_.SafeerOS._posodobi(lazna), {"ok": False, "koda": "ni_novih"})
        self.assertIsNone(lazna.posodobitve["izid"])
        self.assertEqual(self.namestitve, [])

    def test_koda_napake_apt(self):
        k = self.os_.koda_napake_apt
        self.assertEqual(k(subprocess.CompletedProcess([], 126, "", "")), "preklicano")
        self.assertEqual(k(subprocess.CompletedProcess([], 127, "", "Error executing command as another user")), "preklicano")
        self.assertEqual(k(subprocess.CompletedProcess([], 100, "", "E: Unable to lock the administration directory (/var/lib/dpkg/), "
                                                                  "is another process using it?")), "zaklenjeno")
        self.assertEqual(k(subprocess.CompletedProcess([], 100, "", "E: Could not get lock /var/lib/apt/lists/lock")), "zaklenjeno")
        self.assertEqual(k(subprocess.CompletedProcess([], 100, "", "E: Sub-process /usr/bin/dpkg returned an error code (1)")), "apt")
        self.assertEqual(k(subprocess.CompletedProcess([], 1, None, None)), "apt")


class KarticaControl(unittest.TestCase):
    """Enkratna kartica »Namesti Safeer Control« na Domov: ko jo uporabnik zapre, se ne vrne (tudi po ponovnem zagonu)."""

    def test_spomin(self):
        import safeer_os
        with tempfile.TemporaryDirectory() as tmp:
            pot = os.path.join(tmp, "os.json")
            lazna = mock.MagicMock()
            lazna.shramba = os_programi.Shramba(pot)
            self.assertTrue(safeer_os.SafeerOS._kartica_control(lazna))
            self.assertTrue(safeer_os.SafeerOS._kartica_control(lazna, False))
            self.assertFalse(os.path.exists(pot))                         # samo branje nicesar ne zapise
            self.assertFalse(safeer_os.SafeerOS._kartica_control(lazna, True))
            self.assertFalse(safeer_os.SafeerOS._kartica_control(lazna))
            lazna.shramba = os_programi.Shramba(pot)                       # nov zagon Safeer OS
            self.assertFalse(safeer_os.SafeerOS._kartica_control(lazna))

    def test_vmesnik(self):
        py = _beri("safeer_os.py")
        js = _beri("assets", "os", "os.js")
        html = _beri("assets", "os", "index.html")
        for kljuc in ('"namestiControl": self._namesti_control', '"namestitevControla": self._namesti_control_stanje',
                      '"karticaControl": lambda: self._kartica_control(bool(a[0]) if a else False)',
                      '"karticaControl": self._kartica_control()',
                      '"namesti_control": not control and os_posodobitve.nacin_namestitve() == "deb"'):
            self.assertIn(kljuc, py)
        for kljuc in ('klic("namestiControl")', 'klic("karticaControl", [true])', 'S.zacetek.karticaControl',
                      '$("gumbNamestiControl").hidden = !namesti;'):
            self.assertIn(kljuc, js)
        for oznaka in ('id="gumbNamestiControl" hidden', 'id="domNamestiControl" hidden', 'id="domNamestiControlZapri"'):
            self.assertIn(oznaka, html)
        # Vsaka koda napake, ki jo vrne Safeer OS, ima besedilo v vseh sestih jezikih.
        besedila = _beri("assets", "os", "besedila.js")
        for koda in ("zaklenjeno", "preklicano", "sha256", "podpis", "omrezje", "ni_paketa", "prekinjeno", "apt", "napaka"):
            self.assertEqual(besedila.count('"ctrlNapaka_%s":' % koda), 6, koda)
            self.assertIn('"%s"' % koda, py + '"napaka"', koda)
        # Nikoli samodejno: namestitev zacne samo klik (gumb v Napravah ali na kartici).
        self.assertEqual(js.count('klic("namestiControl")'), 1)
        self.assertIn('$("gumbNamestiControl").addEventListener("click", namestiControl);', js)
        self.assertIn('$("domNamestiControlGumb").addEventListener("click", namestiControl);', js)
        self.assertEqual(re.findall(r"(?<!function )\bnamestiControl\(", js), [])


@unittest.skipUnless(shutil.which("node"), "node ni namescen")
class GumbStran(unittest.TestCase):
    """Napake, ki jih ponovni poskus ne popravi (podpis, ni_paketa, apt): poleg »Poskusi znova« na kartici in v
    Napravah se gumb, ki odpre safeer.si/control - besedilo napake jo omenja, uporabnik pa naj ima kaj klikniti."""

    def test_gumb_stran_ob_napakah_brez_ponovnega_poskusa(self):
        js = _beri("assets", "os", "os.js")
        blok = js[js.index("  S.namestitevControla = { stanje: null, zanka: 0 };"):js.index("  // Naprave v Linku s preimenovanjem")]
        koda = r"""
var assert = require("assert");
function El() { this.hidden = true; this.disabled = false; this.textContent = ""; var r = {};
  this.classList = { toggle: function (x, v) { if (v) r[x] = 1; else delete r[x]; } }; }
var vozli = {};
["napraveNamestitev", "gumbNamestiControl", "gumbNamestiControlBesedilo", "gumbNamestiControlStran", "domNamestiControlGumb",
 "domNamestiControlBesedilo", "domNamestiControlStran", "domNamestiControlPod", "domNamestiControl"].forEach(function (id) { vozli[id] = new El(); });
function $(id) { return vozli[id]; }
function t(k) { return k; }
var klici = [];
function klic(m, a) { klici.push([m, a]); return Promise.resolve(true); }
function obvesti() {}
function osveziPovezavo() {}
var S = {};
""" + blok + r"""
vozli.gumbNamestiControl.hidden = false;
["podpis", "ni_paketa", "apt"].forEach(function (koda) {
  narisiNamestitevControla({ faza: "napaka", koda: koda, tece: false, stran: "https://safeer.si/control/" });
  assert.strictEqual(vozli.gumbNamestiControlStran.hidden, false, koda);
  assert.strictEqual(vozli.domNamestiControlStran.hidden, false, koda);
  assert.strictEqual(vozli.gumbNamestiControlBesedilo.textContent, "ctrlPoskusiZnova", koda);
});
["zaklenjeno", "preklicano", "omrezje", "sha256", "prekinjeno"].forEach(function (koda) {
  narisiNamestitevControla({ faza: "napaka", koda: koda, tece: false });
  assert.strictEqual(vozli.gumbNamestiControlStran.hidden, true, koda);
  assert.strictEqual(vozli.domNamestiControlStran.hidden, true, koda);
});
narisiNamestitevControla({ faza: "napaka", koda: "apt", tece: false, stran: "https://safeer.si/control/" });
narisiNamestitevControla({ faza: "prenos", tece: true, odstotek: 0 });          // »Poskusi znova«: gumb strani izgine
assert.strictEqual(vozli.domNamestiControlStran.hidden, true);
narisiNamestitevControla({ faza: "napaka", koda: "podpis", tece: false, stran: "https://safeer.si/control/" });
odpriStranControl();
assert.deepStrictEqual(klici, [["splet", ["https://safeer.si/control/"]]]);
// Naprave brez gumba »Namesti« (Control je medtem tu): tudi gumba strani ni.
vozli.gumbNamestiControl.hidden = true;
narisiNamestitevControla({ faza: "napaka", koda: "apt", tece: false });
assert.strictEqual(vozli.gumbNamestiControlStran.hidden, true);
"""
        subprocess.run(["node", "-e", koda], check=True, timeout=60)

    def test_vmesnik_in_stanje(self):
        import safeer_os
        html = _beri("assets", "os", "index.html")
        js = _beri("assets", "os", "os.js")
        for oznaka in ('id="gumbNamestiControlStran" hidden', 'id="domNamestiControlStran" hidden'):
            self.assertIn(oznaka, html)
        for kljuc in ('$("gumbNamestiControlStran").addEventListener("click", odpriStranControl);',
                      '$("domNamestiControlStran").addEventListener("click", odpriStranControl);'):
            self.assertIn(kljuc, js)
        self.assertEqual(_beri("assets", "os", "besedila.js").count('"ctrlOdpriStran":'), 6)
        lazna = mock.MagicMock()
        lazna.namescanje_controla = op.Posodabljanje()
        self.assertEqual(safeer_os.SafeerOS._namesti_control_stanje(lazna)["stran"], "https://safeer.si/control/")


class PosodobitveRazlicice(unittest.TestCase):
    """Odstranjen Control z ostanki nastavitev ('rc') ni namescen: posodobitev ga ne sme tiho vrniti."""

    def test_rc_ne_steje(self):
        import safeer_os
        lazna = mock.MagicMock()
        for izpis, pricakovano in (("install ok installed|2.1.73\n", {"safeer-os": safeer_os.RAZLICICA, "safeer-control": "2.1.73"}),
                                   ("deinstall ok config-files|2.1.73\n", {"safeer-os": safeer_os.RAZLICICA}),
                                   ("", {"safeer-os": safeer_os.RAZLICICA})):
            with self.subTest(izpis=izpis), \
                    mock.patch.object(op, "nacin_namestitve", return_value="deb"), \
                    mock.patch.object(op.subprocess, "run", return_value=mock.Mock(stdout=izpis)) as zagon:
                self.assertEqual(safeer_os.SafeerOS._posodobitve_razlicice(lazna), pricakovano)
                self.assertEqual(zagon.call_args[0][0][-1], "safeer-control")
        with mock.patch.object(op, "nacin_namestitve", return_value="flatpak"), \
                mock.patch.object(op.subprocess, "run", side_effect=AssertionError("dpkg ni potreben")):
            self.assertEqual(safeer_os.SafeerOS._posodobitve_razlicice(lazna), {"safeer-os": safeer_os.RAZLICICA})


class StanjePovezave(unittest.TestCase):
    def test_namesti_control_samo_deb_brez_controla(self):
        import safeer_os
        for ukaz, nacin, pricakovano in ((None, "deb", True), (None, "flatpak", False), (None, "neznano", False),
                                         (["/usr/bin/safeer-control"], "deb", False)):
            with self.subTest(ukaz=ukaz, nacin=nacin), \
                    mock.patch.object(safeer_os, "_ukaz_controla", return_value=ukaz), \
                    mock.patch.object(safeer_os, "_podatki_controla", return_value={}), \
                    mock.patch.object(safeer_os, "hubi_v_omrezju", return_value=[]), \
                    mock.patch.object(op, "nacin_namestitve", return_value=nacin):
                p = safeer_os.stanje_povezave()
                self.assertEqual((p["control"], p["namesti_control"]), (bool(ukaz), pricakovano))


if __name__ == "__main__":
    unittest.main()
