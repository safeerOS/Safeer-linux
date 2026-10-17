import subprocess
import sys
import time
import unittest
import urllib.request
from unittest import mock

from core import zvok_na_zvocnik as zz


class LazniZvocnik:
    def __init__(self, udn="uuid:jbl", ime="JBL BAR 300", stanje="STOPPED", uri=""):
        self.udn, self.ime, self.model, self.proizvajalec, self.naslov = udn, ime, "BAR 300", "Harman", "127.0.0.1"
        self._stanje, self._uri = stanje, uri
        self.klici = []

    def stanje(self):
        return self._stanje

    def polozaj(self):
        return {"TrackURI": self._uri}

    def predvajaj(self, url, naslov="", izvajalec="", mime=""):
        self.klici.append(("predvajaj", url, mime))
        self._stanje, self._uri = "PLAYING", url

    def ustavi(self):
        self.klici.append(("ustavi",))
        self._stanje = "STOPPED"


class LazniPactl:
    def __init__(self):
        self.klici = []
        self.sinks = "1\talsa_output.pci\tPipeWire\n"

    def __call__(self, *a, cas=4.0):
        self.klici.append(a)
        out = ""
        if a[:1] == ("get-default-sink",):
            out = "alsa_output.pci\n"
        elif a[:3] == ("list", "short", "sinks"):
            out = self.sinks
        elif a[:3] == ("list", "short", "sink-inputs"):
            out = "7\t1\t2\tPipeWire\n"
        elif a[:1] == ("load-module",):
            self.sinks += "2\tsafeer_zvocnik\tPipeWire\n"
            out = "42\n"
        return subprocess.CompletedProcess(a, 0, out, "")


def _zvocniki(zvocnik, pactl):
    z = zz.Zvocniki(najdi=lambda cas: [zvocnik], pactl=pactl, ffmpeg=sys.executable,
                    lan_naslov=lambda ip: "127.0.0.1")
    z.televizorji = lambda: set()
    z.osvezi(pocakaj=True)
    return z


class ZvokNaZvocnikTest(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(zz, "ukaz_toka", lambda vir, ffmpeg="": [sys.executable, "-c",
                              "import sys; sys.stdout.buffer.write(b'ID3' + b'x' * 5000)"])
        p.start()
        self.addCleanup(p.stop)
        m = mock.patch.object(zz.shutil, "which", lambda x: "/usr/bin/" + x)
        m.start()
        self.addCleanup(m.stop)

    def test_seznam_in_predvajanje_toka(self):
        jbl, pactl = LazniZvocnik(), LazniPactl()
        z = _zvocniki(jbl, pactl)
        self.assertEqual([s["id"] for s in z.seznam()], ["dlna:uuid:jbl"])
        r = z.zacni("dlna:uuid:jbl")
        self.assertTrue(r["ok"], r)
        url = jbl.klici[0][1]
        self.assertEqual(jbl.klici[0][2], "audio/mpeg")
        self.assertIn(("set-default-sink", "safeer_zvocnik"), pactl.klici)
        self.assertIn(("move-sink-input", "7", "safeer_zvocnik"), pactl.klici)
        with urllib.request.urlopen(url, timeout=5) as odg:
            self.assertEqual(odg.headers["Content-Type"], "audio/mpeg")
            self.assertTrue(odg.read().startswith(b"ID3"))
        # tuja pot: 404
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(url.rsplit("/", 2)[0] + "/drugo/safeer.mp3", timeout=5)
        self.assertEqual(z.opis()["naprava"], "dlna:uuid:jbl")
        self.assertTrue(z.ustavi())
        self.assertIn(("ustavi",), jbl.klici)
        self.assertIn(("set-default-sink", "alsa_output.pci"), pactl.klici)
        self.assertIn(("unload-module", "42"), pactl.klici)
        self.assertEqual(z.opis()["naprava"], "")

    def test_tv_vir_brez_potrditve_ne_preklopi(self):
        jbl, pactl = LazniZvocnik(stanje="PLAYING", uri="TV"), LazniPactl()
        z = _zvocniki(jbl, pactl)
        r = z.zacni("dlna:uuid:jbl")
        self.assertFalse(r["ok"])
        self.assertEqual(r["vir"], "TV")
        self.assertEqual(jbl.klici, [])
        self.assertNotIn(("set-default-sink", "safeer_zvocnik"), pactl.klici)
        r = z.zacni("dlna:uuid:jbl", potrdi=True)
        self.assertTrue(r["ok"])
        z.ustavi()

    def test_straza_vrne_zvok_ko_zvocnik_preklopi_vir(self):
        jbl, pactl = LazniZvocnik(), LazniPactl()
        z = _zvocniki(jbl, pactl)
        with mock.patch.object(zz, "ZACETNI_ZAMIK_S", 0.0), mock.patch.object(zz, "PREVERI_S", 0.05), \
                mock.patch.object(zz, "ODHOD_PREVERI_S", 0.05), mock.patch.object(zz, "TV_OKNO_S", 0.3):
            self.assertTrue(z.zacni("dlna:uuid:jbl")["ok"])
            jbl._stanje, jbl._uri = "PLAYING", "TV"      # uporabnik na daljincu izbere TV
            for _ in range(100):
                if not z.opis()["naprava"]:
                    break
                time.sleep(0.05)
        self.assertEqual(z.opis()["naprava"], "")
        self.assertIn(("set-default-sink", "alsa_output.pci"), pactl.klici)
        self.assertNotIn(("ustavi",), jbl.klici)       # zvocniku ne vzamemo vira, ki ga je izbral

    def test_nov_tok_po_preklopu_gre_na_zvocnik(self):
        """Safeer DRM (Spotify) odpre ob novi skladbi nov tok; WirePlumber ga pripne na zapomnjen izhod racunalnika."""

        class Pactl(LazniPactl):
            def __init__(self):
                super().__init__()
                self.tokovi = {"7": "1"}          # id toka -> indeks izhoda

            def __call__(self, *a, cas=4.0):
                if a[:3] == ("list", "short", "sink-inputs"):
                    self.klici.append(a)
                    out = "".join("%s\t%s\t3\tPipeWire\n" % (k, v) for k, v in sorted(self.tokovi.items()))
                    return subprocess.CompletedProcess(a, 0, out, "")
                if a[:1] == ("move-sink-input",):
                    self.tokovi[a[1]] = "2" if a[2] == zz.IZHOD else "1"
                return super().__call__(*a, cas=cas)

        jbl, pactl = LazniZvocnik(), Pactl()
        z = _zvocniki(jbl, pactl)
        with mock.patch.object(zz, "NOVI_TOKOVI_S", 0.02), mock.patch.object(zz, "ZACETNI_ZAMIK_S", 30.0):
            self.assertTrue(z.zacni("dlna:uuid:jbl")["ok"])
            self.assertEqual(pactl.tokovi["7"], "2")
            pactl.tokovi["9"] = "1"                 # nova skladba v Safeer DRM: nov tok na zvocnikih racunalnika
            for _ in range(200):
                if pactl.tokovi["9"] == "2":
                    break
                time.sleep(0.01)
            self.assertEqual(pactl.tokovi["9"], "2")
            premikov = len([k for k in pactl.klici if k[:1] == ("move-sink-input",)])
            time.sleep(0.1)                         # tok, ki ze gre na zvocnik, ne premikamo znova
            self.assertEqual(premikov, len([k for k in pactl.klici if k[:1] == ("move-sink-input",)]))
            z.ustavi()
            self.assertEqual(pactl.tokovi, {"7": "1", "9": "1"})
            pactl.tokovi["11"] = "1"                # po koncu seje nicesar vec ne premikamo na zvocnik
            time.sleep(0.1)
            self.assertEqual(pactl.tokovi["11"], "1")

    def test_neznan_zvocnik(self):
        z = _zvocniki(LazniZvocnik(), LazniPactl())
        self.assertEqual(z.zacni("dlna:drug")["napaka"], "ni_zvocnika")


if __name__ == "__main__":
    unittest.main()


class _Tok:
    url = "http://127.0.0.1:1/zeton/safeer.mp3"
    prvi_bajt = 0.0

    def ustavi(self):
        pass


class SamodejniPreklopTvTest(unittest.TestCase):
    """HDMI-CEC ob vklopu televizorja preklopi zvocnik na TV: to ni uporabnikova izbira (lastnik, 17. 10. 2026)."""

    def _straza(self, dogodki, konec=120.0, tv_ob_zacetku=()):
        """Straza na lazni uri; `dogodki`: {cas_s: funkcija(jbl, tv)} - kaj se zgodi ob kateri sekundi."""
        jbl, pactl = LazniZvocnik(stanje="PLAYING", uri=_Tok.url), LazniPactl()
        z = zz.Zvocniki(najdi=lambda cas: [], pactl=pactl, ffmpeg=sys.executable, lan_naslov=lambda ip: "127.0.0.1")
        tv = set(tv_ob_zacetku)
        z.televizorji = lambda: set(tv)
        ura = [0.0]
        z.ura = lambda: ura[0]
        cakajoci = sorted(dogodki.items())

        def spi(s):
            ura[0] += s
            while cakajoci and cakajoci[0][0] <= ura[0]:
                cakajoci.pop(0)[1](jbl, tv)
            if ura[0] > konec:
                z._seja += 1          # varovalka: straza se mora koncati sama
        z.spi = spi
        z._seja, z._zvocnik, z._id, z._tok, z._prejsnji = 1, jbl, "dlna:uuid:jbl", _Tok(), "alsa_output.pci"
        z.stanje = "tece"             # meritev zakasnitve tu ni predmet testa
        z._strazi(1)
        return z, jbl, ura[0]

    @staticmethod
    def _tv_vir(jbl, _tv):
        jbl._stanje, jbl._uri = "PLAYING", "TV"

    @staticmethod
    def _tv_zbujen(_jbl, tv):
        tv.add("tv-dnevna")

    def test_samodejen_preklop_ob_zbujenju_tv_se_nadaljuje(self):
        # TV se zbudi (v Linku) ob 20 s, CEC preklopi zvocnik ob 22 s; uporabnik kasneje izbere drug izhod.
        z, jbl, _ = self._straza({20: self._tv_zbujen, 22: self._tv_vir}, konec=80.0)
        self.assertEqual([k[0] for k in jbl.klici], ["predvajaj"])
        self.assertEqual(jbl.klici[0][1], _Tok.url)          # isti tok, brez nove seje
        self.assertEqual(z.opis()["naprava"], "dlna:uuid:jbl")
        self.assertEqual(jbl._uri, _Tok.url)

    def test_tv_se_v_linku_pojavi_sele_po_preklopu(self):
        z, jbl, _ = self._straza({22: self._tv_vir, 35: self._tv_zbujen}, konec=80.0)
        self.assertEqual([k[0] for k in jbl.klici], ["predvajaj"])
        self.assertEqual(z.opis()["naprava"], "dlna:uuid:jbl")

    def test_brez_dogodka_tv_uporabnik_zmaga(self):
        z, jbl, cas = self._straza({22: self._tv_vir})
        self.assertEqual(jbl.klici, [])                      # zvocniku ne vzamemo vira, ki ga je izbral
        self.assertEqual(z.opis()["naprava"], "")
        self.assertLess(cas, 22 + zz.TV_OKNO_S + 10)

    def test_tv_ze_v_linku_ob_zacetku_ni_dogodek(self):
        z, jbl, _ = self._straza({22: self._tv_vir}, tv_ob_zacetku={"tv-dnevna"})
        # televizor, ki je bil v Linku ze ob zacetku seje, se ni zbudil - preklop je uporabnikov
        self.assertEqual(jbl.klici, [])
        self.assertEqual(z.opis()["naprava"], "")

    def test_star_dogodek_tv_ni_samodejen(self):
        z, jbl, _ = self._straza({15: self._tv_zbujen, 15 + zz.TV_OKNO_S + 10: self._tv_vir})
        self.assertEqual(jbl.klici, [])
        self.assertEqual(z.opis()["naprava"], "")

    def test_dvakrat_zapored_tv_zmaga_uporabnik(self):
        # CEC preklopi, vzamemo nazaj; uporabnik nato sam spet izbere TV -> konec, brez zanke.
        z, jbl, cas = self._straza({20: self._tv_zbujen, 22: self._tv_vir, 40: self._tv_vir})
        self.assertEqual([k[0] for k in jbl.klici], ["predvajaj"])
        self.assertEqual(z.opis()["naprava"], "")
        self.assertIn(("set-default-sink", "alsa_output.pci"), z._pactl.klici)
        self.assertLess(cas, 60)
