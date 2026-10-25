"""Beta kanal (lastnik, 18. 10. 2026, cilj 3.8: »Beta kanal za navdusence, manjse in pogostejse izdaje«).

Preverja: urejanje razlicic (beta < koncna, tudi tako kot dpkg), kanal v nastavitvah (privzeto stabilno), locen podpisan
beta seznam (drug kontekst - ne velja kot stabilni, tudi za ze namescene odjemalce), stabilni kanal predizdaj ne vidi
nikoli, izklop bete nicesar ne zamenja navzdol, orodje tools/beta_seznam.py, check_version za beto, posel CI beta-izdaja
(samo osnutek predizdaje) in stikalo v Nastavitvah (6 jezikov, tipkovnica).
"""
import base64
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

KOREN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOREN))
sys.path.insert(0, str(KOREN / "tools"))
from core import os_posodobitve as op  # noqa: E402
from test_os_posodobitve import MANIFEST, _Streznik, _svez_manifest  # noqa: E402

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
except Exception:  # pragma: no cover - CI in razvoj imata python3-cryptography
    Ed25519PrivateKey = None

import beta_seznam  # noqa: E402

DEB = {"url": "https://github.com/safeerOS/Safeer-linux/releases/download/v1.0.128-beta.1/safeer-os_0.4.86-beta.1_amd64.deb",
       "sha256": "1" * 64, "velikost": 10}
FLATPAK = {"url": "https://github.com/safeerOS/Safeer-linux/releases/download/v1.0.128-beta.1/Safeer-OS-0.4.86-beta.1-x86_64.flatpak",
           "sha256": "2" * 64, "velikost": 10}
APPIMAGE = {"url": "https://github.com/safeerOS/Safeer-linux/releases/download/v1.0.128-beta.1/Safeer-OS-0.4.86-beta.1-x86_64.AppImage",
            "sha256": "3" * 64, "velikost": 10}


def _beta(razlicica="0.4.86-beta.1", izdano="2026-10-18T00:00:00Z", potece="2030-01-01T00:00:00Z"):
    return {"kanal": "beta", "oznaka": "v1.0.128-beta.1", "izdano": izdano, "potece": potece,
            "linux": {"safeer-os": {"razlicica": razlicica, "deb": DEB, "flatpak": FLATPAK, "appimage": APPIMAGE},
                      "novo": {"sl": "Beta novost.", "en": "Beta news."}},
            "stran": "https://github.com/safeerOS/Safeer-linux/releases/tag/v1.0.128-beta.1"}


def _stabilni(razlicica="0.4.85"):
    m = copy.deepcopy(MANIFEST)
    m["linux"]["safeer-os"]["razlicica"] = razlicica
    m["linux"]["novo"] = {"sl": "Stabilna novost.", "en": "Stable news."}
    return m


class UrejanjeRazlicic(unittest.TestCase):
    VRSTA = ["0.4.85", "0.4.86-beta.1", "0.4.86-beta.2", "0.4.86-beta.10", "0.4.86-rc.1", "0.4.86", "0.4.87-beta.1", "0.4.87"]

    def test_beta_pred_koncno(self):
        for i, a in enumerate(self.VRSTA):
            for b in self.VRSTA[i + 1:]:
                self.assertTrue(op.novejsa(b, a), (b, a))
                self.assertFalse(op.novejsa(a, b), (a, b))
        # Uporabnik bete dobi koncno izdajo: 0.4.86 > 0.4.86-beta.2 (prej so stele samo stevilke: (0,4,86,2) > (0,4,86)).
        self.assertTrue(op.novejsa("0.4.86", "0.4.86-beta.2"))

    def test_oblika_deb_in_oznake_sta_enaki(self):
        """Control bere razlicico iz dpkg (0.4.86~beta.1), program in oznaka pisejo 0.4.86-beta.1 - isto."""
        self.assertEqual(op.kljuc_razlicice("0.4.86~beta.1"), op.kljuc_razlicice("0.4.86-beta.1"))
        self.assertEqual(op.kljuc_razlicice("v1.0.128-beta.1"), op.kljuc_razlicice("1.0.128-beta.1"))
        self.assertFalse(op.novejsa("0.4.86~beta.1", "0.4.86-beta.1"))
        self.assertTrue(op.je_predizdaja("0.4.86~beta.1") and op.je_predizdaja("1.0.128-beta.3"))
        for v in ("0.4.86", "1.0.127", "", None, "ni razlicica", "0.4.86-1"):
            self.assertFalse(op.je_predizdaja(v), v)

    def test_stare_razlicice_kot_prej(self):
        self.assertTrue(op.novejsa("1.0.18", "1.0.9"))
        self.assertTrue(op.novejsa("0.4.23", ""))
        self.assertFalse(op.novejsa("", "0.4.22"))
        self.assertFalse(op.novejsa("ni razlicica", "0.0.1"))
        self.assertFalse(op.novejsa("1.0", "1.0.0"))   # enako (prej (1,0) < (1,0,0))

    @unittest.skipUnless(shutil.which("dpkg"), "brez dpkg")
    def test_enako_kot_dpkg(self):
        """Isti vrstni red kot apt: Version paketa .deb je iz packaging/deb_razlicica.sh (0.4.86-beta.1 -> 0.4.86~beta.1)."""
        def deb(v):
            return subprocess.run(["bash", str(KOREN / "packaging/deb_razlicica.sh"), v], capture_output=True,
                                  text=True, check=True).stdout.strip()
        self.assertEqual([deb(v) for v in ("1.0.127", "0.4.86-beta.2", "2.1.83-rc.1")], ["1.0.127", "0.4.86~beta.2", "2.1.83~rc.1"])
        for i, a in enumerate(self.VRSTA):
            for b in self.VRSTA[i + 1:]:
                r = subprocess.run(["dpkg", "--compare-versions", deb(a), "lt", deb(b)])
                self.assertEqual(r.returncode, 0, (deb(a), deb(b)))
        # Brez tilde bi dpkg beto uredil ZA koncno - zato packaging/deb_razlicica.sh.
        self.assertEqual(subprocess.run(["dpkg", "--compare-versions", "0.4.86-beta.2", "gt", "0.4.86"]).returncode, 0)

    def test_paketa_deb_uporabita_obliko_dpkg(self):
        for skripta, polja in (("build_deb.sh", ["Version: ${DEB_VERSION}"]),
                               ("build_os_deb.sh", ["Version: ${DEB_VERSION}", "safeer-control (= ${DEB_CONTROL_VERSION})",
                                                    "safeer-cinnamon (= ${DEB_CINNAMON_VERSION})",
                                                    "Conflicts: safeer-control (<< ${DEB_CONTROL_VERSION}~)"])):
            besedilo = (KOREN / skripta).read_text(encoding="utf-8")
            self.assertIn('packaging/deb_razlicica.sh" "$VERSION")"', besedilo)
            for p in polja:
                self.assertIn(p, besedilo, skripta)
            # Ime datoteke ostane z »-beta.N« (enako kot oznaka in imena v CI).
            self.assertIn('DEB_PACKAGE="${PKG_NAME}_${VERSION}_${ARCH}.deb"', besedilo)
        mint = (KOREN / "tools/mint_namestitev/v_vsebniku.sh").read_text(encoding="utf-8")
        self.assertIn('razlicica() { dpkg-deb -f "$1" Version | v_program; }', mint)
        r = subprocess.run(["bash", "-c", re.search(r"^v_program\(\) .*$", mint, re.M).group(0) +
                            '\nprintf "0.4.86~beta.1\\n1.0.127\\n" | v_program'], capture_output=True, text=True, check=True)
        self.assertEqual(r.stdout.split(), ["0.4.86-beta.1", "1.0.127"])


class Kanal(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.pot = os.path.join(self.mapa, "safeer-os", "posodobitve.json")
        p = mock.patch.dict(os.environ, {"SAFEER_POSODOBITVE_STANJE": self.pot})
        p.start()
        self.addCleanup(p.stop)
        self.addCleanup(shutil.rmtree, self.mapa, True)

    def test_privzeto_stabilno(self):
        self.assertEqual(op.izbrani_kanal(), "stabilno")
        os.makedirs(os.path.dirname(self.pot), exist_ok=True)
        with open(self.pot + "x", "w") as f:
            f.write("ni json")
        self.assertEqual(op.izbrani_kanal(self.pot + "x"), "stabilno")

    def test_vklop_in_izklop(self):
        self.assertEqual(op.nastavi_kanal("beta"), "beta")
        self.assertEqual(op.izbrani_kanal(), "beta")
        self.assertEqual(op.nastavi_kanal("stabilno"), "stabilno")
        with self.assertRaises(ValueError):
            op.nastavi_kanal("nocni")
        self.assertEqual(op.izbrani_kanal(), "stabilno")

    def test_anti_rollback_in_kanal_v_isti_datoteki_ne_brisata_drug_drugega(self):
        op.nastavi_kanal("beta")
        op._shrani_izdano(self.pot, "2026-10-18T00:00:00Z")
        op._shrani_izdano(self.pot, "2026-10-17T00:00:00Z", "izdano_beta")
        self.assertEqual(op.izbrani_kanal(), "beta")
        op.nastavi_kanal("stabilno")
        self.assertEqual((op._zadnje_izdano(self.pot), op._zadnje_izdano(self.pot, "izdano_beta")),
                         ("2026-10-18T00:00:00Z", "2026-10-17T00:00:00Z"))
        # Datoteka starejse razlicice ({"izdano": ...}) se bere naprej.
        with open(self.pot, "w") as f:
            json.dump({"izdano": "2026-09-01T00:00:00Z"}, f)
        self.assertEqual((op._zadnje_izdano(self.pot), op.izbrani_kanal()), ("2026-09-01T00:00:00Z", "stabilno"))


class Preveri(unittest.TestCase):
    def test_stabilni_kanal_bete_ne_vidi(self):
        i = op.preveri("linux", {"safeer-os": "0.4.85"}, _stabilni("0.4.85"), nacin="deb", kanal="stabilno", beta_manifest=_beta())
        self.assertEqual((i["nove"], i["kanal"], i["na_beti"]), ([], "stabilno", False))
        # Predizdaja, ki bi pomotoma zasla v stabilni seznam, se stabilnemu kanalu ne ponudi.
        i = op.preveri("linux", {"safeer-os": "0.4.85"}, _stabilni("0.4.86-beta.1"), nacin="deb")
        self.assertEqual(i["nove"], [])
        # Brez podanega kanala in s podanim seznamom (preizkusi, Windows) je kanal stabilni.
        self.assertEqual(op.preveri("linux", {"safeer-os": "0.4.85"}, _stabilni(), nacin="deb")["kanal"], "stabilno")

    def test_beta_kanal_ponudi_novejso(self):
        i = op.preveri("linux", {"safeer-os": "0.4.85"}, _stabilni("0.4.85"), nacin="deb", kanal="beta", beta_manifest=_beta())
        n = i["nove"][0]
        self.assertEqual((n["razlicica"], n["beta"], n["datoteka"]), ("0.4.86-beta.1", True, DEB))
        self.assertEqual((i["novo"]["sl"], i["stran"]), ("Beta novost.", _beta()["stran"]))
        self.assertEqual(op.opis(i), "Safeer OS 0.4.86-beta.1")
        for nacin, datoteka in (("flatpak", FLATPAK), ("appimage", APPIMAGE)):
            self.assertEqual(op.preveri("linux", {"safeer-os": "0.4.85"}, _stabilni(), nacin=nacin, kanal="beta",
                                        beta_manifest=_beta())["nove"][0]["datoteka"], datoteka)
        hibrid = op.preveri("linux", {"safeer-os": "0.4.85"}, _stabilni(), nacin="flatpak+deb", kanal="beta",
                            beta_manifest=_beta())["nove"][0]
        self.assertEqual((hibrid["datoteka"], hibrid["deb"]), (FLATPAK, DEB))

    def test_beta_kanal_vzame_stabilno_ce_je_novejsa_ali_enaka(self):
        s = _stabilni("0.4.86")
        i = op.preveri("linux", {"safeer-os": "0.4.86-beta.1"}, s, nacin="deb", kanal="beta", beta_manifest=_beta())
        n = i["nove"][0]
        self.assertEqual((n["razlicica"], n["beta"], n["datoteka"]["url"]), ("0.4.86", False, s["linux"]["safeer-os"]["deb"]["url"]))
        self.assertEqual(i["novo"]["sl"], "Stabilna novost.")
        enaka = _beta("0.4.85")
        n = op.preveri("linux", {"safeer-os": "0.4.84"}, _stabilni("0.4.85"), nacin="deb", kanal="beta", beta_manifest=enaka)["nove"][0]
        self.assertFalse(n["beta"])

    def test_izklop_bete_ne_zamenja_navzdol(self):
        """Na beti 0.4.86-beta.2, kanal stabilno: stabilna 0.4.85 se NE ponudi; 0.4.86 se ponudi (posodobitev)."""
        i = op.preveri("linux", {"safeer-os": "0.4.86-beta.2"}, _stabilni("0.4.85"), nacin="deb", kanal="stabilno")
        self.assertEqual((i["nove"], i["na_beti"], i["flatpak_preklop"]), ([], True, None))
        i = op.preveri("linux", {"safeer-os": "0.4.86~beta.2"}, _stabilni("0.4.86"), nacin="deb", kanal="stabilno")
        self.assertEqual(i["nove"][0]["razlicica"], "0.4.86")
        # Namestitev .deb nikoli z --allow-downgrades (apt starejse ne namesti).
        self.assertNotIn("allow-downgrades", Path(op.__file__).read_text(encoding="utf-8").replace("Brez --allow-downgrades", ""))

    def test_brez_beta_seznama_ostane_stabilni(self):
        def prenesi(url="", kanal="stabilno", **_k):
            if kanal == "beta":
                raise op.NapakaPodpisa("podpis seznama različic ni veljaven")
            return _stabilni("0.4.86")
        with mock.patch.object(op, "prenesi_manifest", side_effect=prenesi):
            i = op.preveri("linux", {"safeer-os": "0.4.85"}, nacin="deb", kanal="beta")
        self.assertEqual((i["nove"][0]["razlicica"], i["kanal"]), ("0.4.86", "beta"))
        self.assertIn("podpis", i["beta_napaka"])

    def test_kanal_iz_nastavitve(self):
        mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, mapa, True)
        klici = []

        def prenesi(url="", kanal="stabilno", **_k):
            klici.append(kanal)
            return _beta() if kanal == "beta" else _stabilni("0.4.85")
        with mock.patch.dict(os.environ, {"SAFEER_POSODOBITVE_STANJE": os.path.join(mapa, "p.json")}), \
                mock.patch.object(op, "prenesi_manifest", side_effect=prenesi):
            self.assertEqual(op.preveri("linux", {"safeer-os": "0.4.85"}, nacin="deb")["nove"], [])
            self.assertEqual(klici, ["stabilno"])        # privzeto: beta seznama sploh ne prenese
            op.nastavi_kanal("beta")
            self.assertEqual(op.preveri("linux", {"safeer-os": "0.4.85"}, nacin="deb")["nove"][0]["razlicica"], "0.4.86-beta.1")
            self.assertEqual(klici, ["stabilno", "stabilno", "beta"])


@unittest.skipIf(Ed25519PrivateKey is None, "brez python3-cryptography")
class BetaSeznamPodpis(unittest.TestCase):
    def setUp(self):
        self.k = Ed25519PrivateKey.generate()
        javni = self.k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.kljuci = {"preizkus": base64.b64encode(javni).decode("ascii")}
        self.mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.mapa, True)
        os.makedirs(os.path.join(self.mapa, "os"))
        self.st = _Streznik(self.mapa)
        self.addCleanup(self.st.ustavi)
        for p in (mock.patch.object(op, "_LOKALNI_HTTP", True),
                  mock.patch.dict(os.environ, {"SAFEER_POSODOBITVE_STANJE": os.path.join(self.mapa, "stanje.json")})):
            p.start()
            self.addCleanup(p.stop)

    def _objavi(self, ime, m, kontekst):
        podatki = json.dumps(m, ensure_ascii=False, indent=1).encode("utf-8") + b"\n"
        sig = self.k.sign(kontekst + podatki)
        with open(os.path.join(self.mapa, "os", ime), "wb") as f:
            f.write(podatki)
        with open(os.path.join(self.mapa, "os", ime + ".sig"), "wb") as f:
            f.write(json.dumps([{"alg": "ed25519", "key_id": "preizkus", "sig": base64.b64encode(sig).decode()}]).encode())
        return self.st.url("/os/" + ime)

    def test_beta_seznam_z_beta_kontekstom(self):
        url = self._objavi("razlicice-beta.json", _beta(), op.KONTEKST_BETA)
        m = op.prenesi_manifest(url, kljuci=self.kljuci, kanal="beta")
        self.assertEqual(m["linux"]["safeer-os"]["razlicica"], "0.4.86-beta.1")

    def test_beta_seznam_ni_nikoli_stabilni(self):
        """Kdor obvlada streznik (ne kljuca), pristnega beta seznama ne more podtakniti kot razlicice.json: podpis z
        beta kontekstom ne velja s stabilnim (tudi za ze namescene odjemalce, ki polja "kanal" ne poznajo)."""
        b = _beta()
        b["android"] = {}   # tudi z obliko stabilnega seznama
        url = self._objavi("razlicice.json", b, op.KONTEKST_BETA)
        with self.assertRaises(op.NapakaPodpisa):
            op.prenesi_manifest(url, kljuci=self.kljuci)
        # in obratno: stabilni podpis ne velja kot beta
        url = self._objavi("razlicice-beta.json", _beta(), op.KONTEKST)
        with self.assertRaises(op.NapakaPodpisa):
            op.prenesi_manifest(url, kljuci=self.kljuci, kanal="beta")

    def test_oznaka_kanala_v_seznamu(self):
        brez = _beta()
        del brez["kanal"]
        url = self._objavi("razlicice-beta.json", brez, op.KONTEKST_BETA)
        with self.assertRaises(ValueError):
            op.prenesi_manifest(url, kljuci=self.kljuci, kanal="beta")
        s = _svez_manifest()
        s["kanal"] = "beta"
        url = self._objavi("razlicice.json", s, op.KONTEKST)
        with self.assertRaises(ValueError):
            op.prenesi_manifest(url, kljuci=self.kljuci)

    def test_locen_anti_rollback(self):
        """Novejsi beta seznam ne zavrne stabilnega z zgodnejsim 'izdano' (in obratno); starejsi beta pa se zavrne."""
        op.prenesi_manifest(self._objavi("razlicice-beta.json", _beta(izdano="2026-10-18T00:00:00Z"), op.KONTEKST_BETA),
                            kljuci=self.kljuci, kanal="beta")
        op.prenesi_manifest(self._objavi("razlicice.json", _svez_manifest("2026-10-01T00:00:00Z"), op.KONTEKST), kljuci=self.kljuci)
        with self.assertRaises(op.NapakaSvezine):
            op.prenesi_manifest(self._objavi("razlicice-beta.json", _beta(izdano="2026-10-10T00:00:00Z"), op.KONTEKST_BETA),
                                kljuci=self.kljuci, kanal="beta")
        with self.assertRaises(op.NapakaSvezine):
            op.prenesi_manifest(self._objavi("razlicice-beta.json", _beta(potece="2026-01-01T00:00:00Z", izdano="2025-12-01T00:00:00Z"),
                                             op.KONTEKST_BETA), kljuci=self.kljuci, kanal="beta")

    def test_privzeti_naslov_beta(self):
        self.assertEqual(op.MANIFEST_BETA, os.environ.get("SAFEER_MANIFEST_BETA_URL") or "https://safeer.si/os/razlicice-beta.json")
        self.assertTrue(op.dovoljen_naslov("https://safeer.si/os/razlicice-beta.json"))


@unittest.skipIf(Ed25519PrivateKey is None, "brez python3-cryptography")
class OrodjeBetaSeznam(unittest.TestCase):
    OZNAKA = "v1.0.128-beta.1"
    PAKETI = ("safeer-os_0.4.86-beta.1_amd64.deb", "Safeer-OS-0.4.86-beta.1-x86_64.flatpak",
              "Safeer-OS-0.4.86-beta.1-x86_64.AppImage", "safeer-browser_1.0.128-beta.1_amd64.deb",
              "Safeer-Browser-1.0.128-beta.1-x86_64.flatpak", "Safeer-Browser-1.0.128-beta.1-x86_64.AppImage",
              "safeer-os-app_0.4.86-beta.1_amd64.deb")

    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.mapa, True)
        vsote = []
        for i, ime in enumerate(self.PAKETI):
            vsebina = os.urandom(1000 + i)
            with open(os.path.join(self.mapa, ime), "wb") as f:
                f.write(vsebina)
            vsote.append("%s  %s\n" % (hashlib.sha256(vsebina).hexdigest(), ime))
        with open(os.path.join(self.mapa, "SHA256SUMS"), "w") as f:
            f.writelines(vsote)
        self.k = Ed25519PrivateKey.generate()
        javni = self.k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.kljuci = {"preizkus": base64.b64encode(javni).decode("ascii")}

    def test_seznam_sprejme_program(self):
        zdaj = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)
        s = beta_seznam.zgradi_seznam(self.OZNAKA, self.mapa, zdaj, novo={"sl": "Novo.", "en": "New.", "de": ""})
        self.assertEqual((s["kanal"], s["izdano"], s["potece"]), ("beta", "2026-10-18T12:00:00Z", "2026-11-17T12:00:00Z"))
        self.assertEqual(s["linux"]["novo"], {"sl": "Novo.", "en": "New."})
        os_p = s["linux"]["safeer-os"]
        self.assertEqual(os_p["razlicica"], "0.4.86-beta.1")
        self.assertEqual(os_p["deb"]["url"], "https://github.com/safeerOS/Safeer-linux/releases/download/v1.0.128-beta.1/"
                                            "safeer-os_0.4.86-beta.1_amd64.deb")
        with open(os.path.join(self.mapa, self.PAKETI[0]), "rb") as f:
            self.assertEqual(os_p["deb"]["sha256"], hashlib.sha256(f.read()).hexdigest())
        podatki, podpis = beta_seznam.podpisi(s, self.k, "preizkus")
        op.preveri_podpis(podatki, podpis, self.kljuci, op.KONTEKST_BETA)
        with self.assertRaises(op.NapakaPodpisa):
            op.preveri_podpis(podatki, podpis, self.kljuci)        # ni stabilni seznam
        m = json.loads(podatki)
        op.preveri_svezino(m, "", zdaj)
        i = op.preveri("linux", {"safeer-os": "0.4.85"}, _stabilni("0.4.85"), nacin="deb", kanal="beta", beta_manifest=m)
        self.assertEqual((i["nove"][0]["razlicica"], i["nove"][0]["datoteka"]), ("0.4.86-beta.1", os_p["deb"]))
        # WebKit je od 20. 10. 2026 vgrajen (ni "webkit_deb"); aplikacija Safeer OS ima svoj paket "deb_app".
        self.assertNotIn("webkit_deb", os_p)
        self.assertNotIn("webkit_deb", s["linux"]["safeer-browser"])
        self.assertNotIn("webkit", i["nove"][0])
        self.assertEqual(os_p["deb_app"]["url"].rsplit("/", 1)[1], "safeer-os-app_0.4.86-beta.1_amd64.deb")

    def test_zavrne_neskladje(self):
        zdaj = datetime(2026, 10, 18, tzinfo=timezone.utc)
        with self.assertRaises(beta_seznam.Napaka):
            beta_seznam.zgradi_seznam("v1.0.128", self.mapa, zdaj)            # ni beta oznaka
        with open(os.path.join(self.mapa, self.PAKETI[2]), "ab") as f:
            f.write(b"x")                                                     # paket ni tisti iz SHA256SUMS
        with self.assertRaises(beta_seznam.Napaka) as e:
            beta_seznam.zgradi_seznam(self.OZNAKA, self.mapa, zdaj)
        self.assertIn("SHA-256", str(e.exception))
        os.remove(os.path.join(self.mapa, self.PAKETI[2]))
        with self.assertRaises(beta_seznam.Napaka):
            beta_seznam.zgradi_seznam(self.OZNAKA, self.mapa, zdaj)           # manjka paket
        with self.assertRaises(beta_seznam.Napaka):
            beta_seznam.zgradi_seznam("v1.0.128-beta.2", self.mapa, zdaj)     # Safeer OS ni iste bete

    def test_preveri_objavo_na_githubu(self):
        s = beta_seznam.zgradi_seznam(self.OZNAKA, self.mapa, datetime(2026, 10, 18, tzinfo=timezone.utc))
        sredstva = [{"name": ime, "size": os.path.getsize(os.path.join(self.mapa, ime))} for ime in self.PAKETI]

        class Odgovor:
            def __init__(self, d):
                self.d = json.dumps(d).encode()

            def read(self):
                return self.d

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False
        objavljena = {"draft": False, "prerelease": True, "assets": sredstva}
        beta_seznam.preveri_na_githubu(self.OZNAKA, s, odpri=lambda url, timeout: Odgovor(objavljena))
        for slabo in ({"draft": True}, {"prerelease": False}, {"assets": sredstva[1:]},
                      {"assets": [dict(sredstva[0], size=1)] + sredstva[1:]}):
            with self.assertRaises(beta_seznam.Napaka, msg=slabo):
                beta_seznam.preveri_na_githubu(self.OZNAKA, s, odpri=lambda url, timeout: Odgovor(dict(objavljena, **slabo)))

        def ni(url, timeout):
            raise OSError("HTTP 404")
        with self.assertRaises(beta_seznam.Napaka):
            beta_seznam.preveri_na_githubu(self.OZNAKA, s, odpri=ni)

    def test_main_samo_s_kljucem_ki_mu_program_zaupa(self):
        kljuc = os.path.join(self.mapa, "kljuc.pem")
        with open(kljuc, "wb") as f:
            f.write(self.k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                         serialization.NoEncryption()))
        izhod = os.path.join(self.mapa, "izhod")
        argv = ["--oznaka", self.OZNAKA, "--mapa", self.mapa, "--kljuc", kljuc, "--izhod", izhod, "--brez-githuba",
                "--key-id", "preizkus"]
        with mock.patch("sys.stderr"):
            self.assertEqual(beta_seznam.main(argv), 1)                       # tuj kljuc: nic se ne zapise
        self.assertFalse(os.path.exists(izhod))
        with mock.patch.dict(op.KLJUCI, self.kljuci, clear=True), mock.patch("sys.stdout"):
            self.assertEqual(beta_seznam.main(argv), 0)
        with open(os.path.join(izhod, "razlicice-beta.json"), "rb") as f:
            podatki = f.read()
        with open(os.path.join(izhod, "razlicice-beta.json.sig"), "rb") as f:
            op.preveri_podpis(podatki, f.read(), self.kljuci, op.KONTEKST_BETA)
        # Surovo seme (32 bajtov, tudi base64) je enakovredno PEM.
        seme = self.k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
        with open(kljuc, "wb") as f:
            f.write(base64.b64encode(seme) + b"\n")
        self.assertEqual(beta_seznam.nalozi_kljuc(kljuc).public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw), base64.b64decode(self.kljuci["preizkus"]))


class PreverbaRazlicicZaBeto(unittest.TestCase):
    """packaging/check_version.py: beta ima isti -beta.N povsod; README ostane na stabilni; oznaka = v + VERSION."""
    DATOTEKE = ("packaging/check_version.py", "packaging/VERSION", "packaging/VERSION_OS", "packaging/VERSION_CONTROL",
                "README.md", "PACKAGING.md", "io.github.memelandfaner.SafeerBrowser.metainfo.xml",
                "io.github.memelandfaner.SafeerOS.metainfo.xml")

    def _pozeni(self, v, v_os, v_control, oznaka=None):
        with tempfile.TemporaryDirectory() as d:
            koren = Path(d)
            for rel in self.DATOTEKE:
                (koren / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(KOREN / rel, koren / rel)
            stari = {ime: (KOREN / "packaging" / ime).read_text().strip() for ime in ("VERSION", "VERSION_OS", "VERSION_CONTROL")}
            for ime, nova in (("VERSION", v), ("VERSION_OS", v_os), ("VERSION_CONTROL", v_control)):
                (koren / "packaging" / ime).write_text(nova + "\n")
            for xml, staro, novo in (("io.github.memelandfaner.SafeerBrowser.metainfo.xml", stari["VERSION"], v),
                                     ("io.github.memelandfaner.SafeerOS.metainfo.xml", stari["VERSION_OS"], v_os)):
                p = koren / xml
                t = p.read_text(encoding="utf-8").replace('<release version="%s"' % staro, '<release version="%s"' % novo, 1)
                p.write_text(t.replace("Safeer Control " + stari["VERSION_CONTROL"], "Safeer Control " + v_control), encoding="utf-8")
            okolje = {k: x for k, x in os.environ.items() if not k.startswith("GITHUB_REF")}
            if oznaka:
                okolje.update(GITHUB_REF_TYPE="tag", GITHUB_REF_NAME=oznaka)
            return subprocess.run([sys.executable, str(koren / "packaging/check_version.py")], capture_output=True,
                                  text=True, env=okolje)

    def test_beta_izdaja(self):
        r = self._pozeni("1.0.128-beta.1", "0.4.86-beta.1", "2.1.83-beta.1", "v1.0.128-beta.1")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("| beta", r.stdout)
        self.assertNotEqual(self._pozeni("1.0.128-beta.1", "0.4.86-beta.1", "2.1.83-beta.1", "v1.0.128-beta.2").returncode, 0)

    def test_neskladna_beta_zavrnjena(self):
        for v, v_os, v_c in (("1.0.128-beta.1", "0.4.86", "2.1.83-beta.1"),          # OS bi bil »stabilen«
                             ("1.0.128-beta.1", "0.4.86-beta.2", "2.1.83-beta.1"),   # drug N
                             ("1.0.128", "0.4.86-beta.1", "2.1.83"),
                             ("1.0.128-rc.1", "0.4.86-rc.1", "2.1.83-rc.1")):         # samo -beta.N
            r = self._pozeni(v, v_os, v_c)
            self.assertNotEqual(r.returncode, 0, (v, v_os, v_c))

    def test_stabilna_kot_prej(self):
        stare = [(KOREN / "packaging" / i).read_text().strip() for i in ("VERSION", "VERSION_OS", "VERSION_CONTROL")]
        r = self._pozeni(*stare)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        # Veja v razvoju je lahko beta (1.0.132-beta.1 za zivo meritev, 21. 10. 2026): README ostane na zadnji stabilni.
        if "-beta." in stare[0]:
            self.assertIn("| beta", r.stdout)
        else:
            self.assertNotIn("beta", r.stdout)


class PoselBetaIzdaja(unittest.TestCase):
    POTEK = KOREN / ".github/workflows/linux-packages.yml"

    def setUp(self):
        try:
            import yaml
        except ImportError:
            self.skipTest("python3-yaml ni namescen")
        self.wf = yaml.safe_load(self.POTEK.read_text(encoding="utf-8"))
        self.posli = self.wf["jobs"]

    def _korak(self, posel, ime):
        for k in self.posli[posel]["steps"]:
            if k.get("name") == ime:
                return k["run"]
        self.fail("ni koraka %s / %s" % (posel, ime))

    def test_beta_oznaka_samo_v_osnutek_predizdaje(self):
        stabilna, beta = self.posli["release"], self.posli["beta-izdaja"]
        self.assertEqual(stabilna["if"], "startsWith(github.ref, 'refs/tags/v') && !contains(github.ref_name, '-beta.')")
        self.assertEqual(beta["if"], "startsWith(github.ref, 'refs/tags/v') && contains(github.ref_name, '-beta.')")
        # Obe izdaji: brez gradnje ob oznaki, paketi zelenega teka istega commita z istimi posli (tools/ci_izdaja.py).
        self.assertNotIn("needs", beta)
        self.assertNotIn("needs", stabilna)
        for posel in (beta, stabilna):
            self.assertIn("python3 tools/ci_izdaja.py najdi", json.dumps(posel))
        sys.path.insert(0, str(KOREN / "tools"))
        import ci_izdaja
        self.assertIn("mint", ci_izdaja.POSLI_IZDAJE)
        besedilo = json.dumps(beta)
        self.assertIn("--draft --prerelease --verify-tag", besedilo)
        ukazi_gh = [v.strip() for k in beta["steps"] for v in (k.get("run") or "").splitlines() if "gh " in v]
        for objava in ("release edit", "--draft=false", "--latest", "-X PATCH", "--method PATCH"):
            self.assertFalse([v for v in ukazi_gh if objava in v], objava)
        self.assertNotIn("--prerelease", json.dumps(stabilna))
        # Preizkus nadgradnje vzame zadnjo objavljeno STABILNO (predizdaje niso »latest«).
        nadgradnja = self._korak("mint", "Packages of the last published release (for the upgrade test)")
        self.assertIn("select((.draft or .prerelease) | not)", nadgradnja)
        self.assertIn("releases/latest", nadgradnja)

    def test_oblika_oznake(self):
        skripta = self._korak("beta-izdaja", "Beta tag shape (vX.Y.Z-beta.N)")
        for oznaka, ok in (("v1.0.128-beta.1", True), ("v1.0.128-beta.12", True), ("v1.0.128-beta", False),
                           ("v1.0.128-beta.1x", False), ("v1.0-beta.1", False)):
            r = subprocess.run(["bash", "-e", "-c", skripta], env=dict(os.environ, TAG=oznaka), capture_output=True, text=True)
            self.assertEqual(r.returncode == 0, ok, (oznaka, r.stdout + r.stderr))

    GH = r'''#!/usr/bin/env python3
import json, os, sys
d = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
st = json.load(open(os.path.join(d, "stanje.json")))
a = sys.argv[1:]
with open(os.path.join(d, "klici.txt"), "a") as f:
    f.write(" ".join(a) + "\n")
if a[:2] == ["release", "view"]:
    r = st.get("izdaja")
    if r is None:
        sys.exit("release not found")
    if "--json" in a:
        print("true" if r[a[a.index("--json") + 1]] else "false")
    sys.exit(0)
if a[:2] == ["release", "create"]:
    st["izdaja"] = {"isDraft": "--draft" in a, "isPrerelease": "--prerelease" in a}
    json.dump(st, open(os.path.join(d, "stanje.json"), "w"))
    sys.exit(0)
if a[:2] == ["release", "upload"]:
    sys.exit(0)
sys.exit("neznan ukaz: %s" % a)
'''

    def test_pripne_samo_v_osnutek_predizdaje(self):
        skripta = self._korak("beta-izdaja", "Attach packages to the beta pre-release draft")
        primeri = [  # (obstojeca izdaja, koda, ustvari, nalozi)
            (None, 0, True, True),
            ({"isDraft": True, "isPrerelease": True}, 0, False, True),
            ({"isDraft": True, "isPrerelease": False}, 1, False, False),     # nikoli v stabilno izdajo
            ({"isDraft": False, "isPrerelease": True}, 0, False, False),     # objavljena: datoteke ostanejo
        ]
        for izdaja, koda, ustvari, nalozi in primeri:
            with self.subTest(izdaja=izdaja), tempfile.TemporaryDirectory() as d:
                gh = Path(d) / "bin" / "gh"
                gh.parent.mkdir()
                gh.write_text(self.GH)
                gh.chmod(0o755)
                (Path(d) / "stanje.json").write_text(json.dumps({"izdaja": izdaja}))
                # Pakete in SHA256SUMS pripravi korak pred tem (tools/ci_izdaja.py preveri) iz zelenega teka.
                (Path(d) / "release").mkdir()
                (Path(d) / "release" / "safeer-os_0.4.86-beta.1_amd64.deb").write_text("x")
                (Path(d) / "release" / "SHA256SUMS").write_text("%s  safeer-os_0.4.86-beta.1_amd64.deb\n" % ("0" * 64))
                r = subprocess.run(["bash", "-e", "-c", skripta], cwd=d, capture_output=True, text=True,
                                   env=dict(os.environ, PATH=str(gh.parent) + os.pathsep + os.environ["PATH"],
                                            TAG="v1.0.128-beta.1", GH_TOKEN="x", GH_REPO="lastnik/repo", TEK="123"))
                self.assertEqual(r.returncode, koda, r.stdout + r.stderr)
                klici = (Path(d) / "klici.txt").read_text()
                self.assertEqual("release create" in klici, ustvari, klici)
                self.assertEqual("release upload" in klici, nalozi, klici)
                if ustvari:
                    self.assertIn("--draft --prerelease --verify-tag", klici)
                    self.assertEqual(json.loads((Path(d) / "stanje.json").read_text())["izdaja"],
                                     {"isDraft": True, "isPrerelease": True})
                if nalozi:
                    self.assertIn("SHA256SUMS", " ".join(os.listdir(Path(d) / "release")))


class StikaloVNastavitvah(unittest.TestCase):
    def setUp(self):
        self.html = (KOREN / "assets/os/index.html").read_text(encoding="utf-8")
        self.js = (KOREN / "assets/os/os.js").read_text(encoding="utf-8")
        self.besedila = (KOREN / "assets/os/besedila.js").read_text(encoding="utf-8")
        self.py = (KOREN / "safeer_os.py").read_text(encoding="utf-8")

    def test_stikalo_privzeto_izklopljeno_in_dostopno(self):
        m = re.search(r'<button class="stikalo" id="stikaloBeta"[^>]*>', self.html)
        self.assertIsNotNone(m)
        # <button> (tipkovnica: Tab, Enter, preslednica), vloga stikala, privzeto izklopljeno; videz iz razreda stikalo.
        self.assertIn('role="switch"', m.group(0))
        self.assertIn('aria-checked="false"', m.group(0))
        self.assertNotIn("style=", m.group(0))
        odsek = self.html.split('<h2 data-t="posodobitve"></h2>', 1)[1].split('<div id="nastavitveDelov">', 1)[0]
        self.assertIn('id="stikaloBeta"', odsek)
        self.assertIn('$("stikaloBeta").addEventListener("click", preklopiBeto);', self.js)
        self.assertIn('klic("posodobitveKanal", [nov ? "beta" : "stabilno"])', self.js)
        self.assertIn('"posodobitveKanal": lambda: self._posodobitve_kanal(', self.py)

    def test_besedila_v_vseh_jezikih(self):
        for kljuc in ("betaKanal", "betaKanalPod", "posodobitevNaBetiPod", "posodobitevNajnovejsaBetaPod"):
            self.assertEqual(len(re.findall(r"\b%s: \"[^\"]{4,}\"" % kljuc, self.besedila)), 6, kljuc)
        for kljuc in ("betaKanal", "betaKanalPod", "posodobitevNaBetiPod", "posodobitevNajnovejsaBetaPod"):
            self.assertIn(kljuc, self.html + self.js)

    def test_js_je_veljaven(self):
        if not shutil.which("node"):
            self.skipTest("brez node")
        for f in ("assets/os/os.js", "assets/os/besedila.js"):
            subprocess.run(["node", "-e", "new Function(require('fs').readFileSync(process.argv[1],'utf8'))",
                            str(KOREN / f)], check=True)


class MostSafeerOS(unittest.TestCase):
    """_posodobitve_stanje in _posodobitve_kanal na laznem objektu (brez okna GTK)."""

    def setUp(self):
        import safeer_os
        self.so = safeer_os
        self.mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.mapa, True)
        p = mock.patch.dict(os.environ, {"SAFEER_POSODOBITVE_STANJE": os.path.join(self.mapa, "p.json")})
        p.start()
        self.addCleanup(p.stop)

        class Lazni:
            posodobitve = {"izid": None, "cas": 0.0, "napaka": ""}
            posodabljanje = op.Posodabljanje()

            def _posodobitve_razlicice(self):
                return {"safeer-os": "0.4.85"}

            def _flatpak_ponudba(self, izid):
                return None
        self.lazni = Lazni()

    def test_preklop_kanala_preveri_takoj(self):
        klici = []

        def preveri(platforma, razlicice, kanal=None, **_k):
            klici.append(kanal)
            return {"nove": [], "nacin": "deb", "stran": op.STRAN, "kanal": kanal}
        S = self.so.SafeerOS
        with mock.patch.object(op, "preveri", side_effect=preveri):
            st = S._posodobitve_stanje(self.lazni)
            self.assertEqual((st["kanal"], klici), ("stabilno", ["stabilno"]))
            S._posodobitve_stanje(self.lazni)
            self.assertEqual(klici, ["stabilno"])                     # izid velja 6 ur
            self.assertEqual(S._posodobitve_kanal(self.lazni, "beta"), {"ok": True, "kanal": "beta"})
            st = S._posodobitve_stanje(self.lazni)
            self.assertEqual((st["kanal"], klici), ("beta", ["stabilno", "beta"]))
            op.nastavi_kanal("stabilno")                              # sprememba od drugod (npr. datoteka)
            S._posodobitve_stanje(self.lazni)
            self.assertEqual(klici, ["stabilno", "beta", "stabilno"])
            self.assertEqual(S._posodobitve_kanal(self.lazni, "nocni")["ok"], False)
        self.assertEqual(op.izbrani_kanal(), "stabilno")
        self.assertIn("na_beti", st)


class ScitNiOdvisenOdKanala(unittest.TestCase):
    def test_pravila_scita_svoj_vir(self):
        """Pravila Scita so svoj podpisan vir (intel.safeer.si, core/signed_feed); beta kanal jih ne spreminja."""
        for ime in ("core/scit_pravila.py", "core/threat_intel.py", "core/signed_feed.py"):
            besedilo = (KOREN / ime).read_text(encoding="utf-8")
            self.assertNotIn("os_posodobitve", besedilo, ime)
            self.assertNotIn("razlicice-beta", besedilo, ime)
        self.assertNotEqual(op.KONTEKST_BETA, op.KONTEKST)
        from core import signed_feed
        self.assertNotIn(op.KONTEKST_BETA, (signed_feed.MANIFEST_CONTEXT, signed_feed.BUNDLE_CONTEXT))


if __name__ == "__main__":
    unittest.main()
