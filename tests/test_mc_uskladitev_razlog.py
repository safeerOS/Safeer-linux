"""Prazen Medijski center pove, zakaj ni kljucev z drugih naprav (polje »uskladitev« iz core/debrid.most; izmerjeno
10. 11. 2026: naprave s kljuci niso bile v ozjem krogu, vmesnik pa je molcal). Prave funkcije iz assets/os/os.js v node,
odgovor jedra je lazen (klic), brez omrezja. Besedila razloga (6 jezikov) da jedro, vmesnik doda napis v 6 jezikih."""
import json
import os
import re
import shutil
import subprocess
import unittest

from core import uskladitev_kljucev_pravila as P

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JEZIKI = ("sl", "en", "de", "es", "fr", "it")


def _funkcija(js, ime):
    return "function %s(" % ime + js.split("  function %s(" % ime, 1)[1].split("\n  }\n", 1)[0] + "\n  }\n"


OKOLJE = r"""
function El() { this.hidden = false; this.textContent = ""; this.atr = {}; }
El.prototype.setAttribute = function (k, v) { this.atr[k] = String(v); };
var elementi = {}, klici = [], odziv = null, risanDebrid = 0;
function $(id) { return elementi[id] || (elementi[id] = new El()); }
var jezik = "sl";
function t(k, z) { var b = (BESEDILA_OS[jezik] && BESEDILA_OS[jezik][k]); if (b == null) b = BESEDILA_OS.en[k]; if (b == null) b = k;
  if (z) Object.keys(z).forEach(function (x) { b = b.split("{" + x + "}").join(z[x]); }); return b; }
function klic(ime, a) { klici.push([ime, a]); return Promise.resolve(odziv); }
function narisiDebrid() { risanDebrid++; }
var debridStanje = null, debridNalagam = false, debridPrazno = 0;
"""


class RazlogVPraznemStanju(unittest.TestCase):
    def setUp(self):
        if not shutil.which("node"):
            raise unittest.SkipTest("node ni namescen")
        pot = os.path.join(KOREN, "assets", "os")
        with open(os.path.join(pot, "os.js"), encoding="utf-8") as f:
            js = f.read()
        with open(os.path.join(pot, "besedila.js"), encoding="utf-8") as f:
            self.besedila = f.read()
        self.koda = (self.besedila + OKOLJE
                     + _funkcija(js, "razlogUskladitve") + "var uskladitevCas = 0;\n"
                     + re.search(r"  var PRAZNA_USKLADITEV = .*\n", js).group(0)
                     + _funkcija(js, "narisiRazlogUskladitve"))
        self.js = js

    def _pozeni(self, skripta):
        izid = subprocess.run(["node", "-"], input=self.koda + skripta, capture_output=True, text=True, timeout=30)
        self.assertEqual(izid.returncode, 0, izid.stderr)
        return json.loads(izid.stdout.strip().splitlines()[-1])

    def _stanje(self, koda, **dodatno):
        _k, besedilo = P.razlog_brez_kljucev(*{P.RAZLOG_NI_NAPRAV: (0, 0, 0, ""), P.RAZLOG_NEDOSEGLJIVE: (1, 0, 0, ""),
                                               P.RAZLOG_BREZ_KLJUCEV: (1, 1, 0, P.IZID_SPREJETO),
                                               P.RAZLOG_CAKA: (1, 0, 0, P.IZID_CAKA),
                                               P.RAZLOG_V_REDU: (1, 1, 2, P.IZID_SPREJETO)}[koda])
        s = {"storitve": [{"id": "torbox", "ime": "TorBox", "kljuc": False}], "usenet_lastni": False,
             "uskladitev": {"koda": koda, "besedilo": besedilo}}
        s.update(dodatno)
        return s

    def test_pokaze_razlog_v_jeziku_vmesnika(self):
        for j in JEZIKI:
            stanje = self._stanje(P.RAZLOG_NI_NAPRAV)
            r = self._pozeni("jezik = %s; debridStanje = %s; uskladitevCas = Date.now(); narisiRazlogUskladitve();"
                             "console.log(JSON.stringify([$('katPraznoUskladitev').hidden, $('katPraznoUskladitev').textContent,"
                             " $('mediaPraznoUskladitev').hidden, $('mediaPraznoUskladitev').textContent]));"
                             % (json.dumps(j), json.dumps(stanje)))
            self.assertIs(r[0], False, j)
            self.assertEqual(r[2:], r[:2], j)                                      # isto v obeh praznih stanjih
            self.assertIn(P.BESEDILA_RAZLOGA[P.RAZLOG_NI_NAPRAV][j], r[1], j)
            self.assertNotIn("{razlog}", r[1], j)                                  # brez nadomestkov
            self.assertNotIn("katUskladitevKljucev", r[1], j)                      # napis obstaja v jeziku

    def test_vsaka_koda_razen_v_redu(self):
        for koda in P.RAZLOGI:
            r = self._pozeni("debridStanje = %s; uskladitevCas = Date.now(); narisiRazlogUskladitve();"
                             "console.log(JSON.stringify([$('katPraznoUskladitev').hidden, $('katPraznoUskladitev').textContent]));"
                             % json.dumps(self._stanje(koda)))
            if koda == P.RAZLOG_V_REDU:
                self.assertEqual(r, [True, ""], koda)
            else:
                self.assertEqual(r[0], False, koda)
                self.assertIn(P.BESEDILA_RAZLOGA[koda]["sl"], r[1], koda)

    def test_z_lastnim_kljucem_ali_brez_polja_ni_vrstice(self):
        for stanje in (self._stanje(P.RAZLOG_NI_NAPRAV, storitve=[{"id": "torbox", "ime": "TorBox", "kljuc": True}]),
                       self._stanje(P.RAZLOG_NI_NAPRAV, usenet_lastni=True),
                       self._stanje(P.RAZLOG_NI_NAPRAV, usenet={"gostitelj": "ix.primer"}),
                       {"storitve": []},                                          # Windows / brez storitve: polja ni
                       {"storitve": [], "uskladitev": {"koda": "ni_naprav_v_krogu", "besedilo": "<b>"}}):
            r = self._pozeni("debridStanje = %s; uskladitevCas = Date.now(); narisiRazlogUskladitve();"
                             "console.log(JSON.stringify([$('katPraznoUskladitev').hidden, $('katPraznoUskladitev').textContent]));"
                             % json.dumps(stanje))
            self.assertEqual(r, [True, ""], stanje)

    def test_brez_stanja_ga_nalozi_enkrat_in_narise(self):
        r = self._pozeni(
            "odziv = %s; narisiRazlogUskladitve(); narisiRazlogUskladitve();"
            "setTimeout(function () { console.log(JSON.stringify([klici, $('katPraznoUskladitev').hidden,"
            " $('katPraznoUskladitev').textContent])); }, 0);" % json.dumps(self._stanje(P.RAZLOG_NEDOSEGLJIVE)))
        self.assertEqual(r[0], [["mediaDebrid", []]])                              # en klic, ne zanka
        self.assertIs(r[1], False)
        self.assertIn(P.BESEDILA_RAZLOGA[P.RAZLOG_NEDOSEGLJIVE]["sl"], r[2])

    def test_napis_v_vseh_jezikih_in_prazno_stanje_ga_klice(self):
        for j in JEZIKI:
            m = re.search(r'Object\.assign\(BESEDILA_OS\.%s, \{"katUskladitevKljucev": "([^"]+)"' % j, self.besedila)
            self.assertTrue(m, j)
            self.assertIn("{razlog}", m.group(1))
        # Vsa prazna stanja Medijskega centra poklicejo izris razloga (katalog, knjiznica zavihka, Domov).
        self.assertIn("narisiRazlogUskladitve();", _funkcija(self.js, "narisiPrazenKatalog"))
        self.assertIn('if (!prazno.hidden) narisiRazlogUskladitve();', _funkcija(self.js, "narisiMediaDomov"))
        self.assertIn('$("mediaPrazno").hidden = samoViri || prikaz.length !== 0 || imaKatalog;\n'
                      '    if (!$("mediaPrazno").hidden) narisiRazlogUskladitve();', self.js)
        with open(os.path.join(KOREN, "assets", "os", "index.html"), encoding="utf-8") as f:
            html = f.read()
        self.assertRegex(html, r'id="katPrazno"[^>]*>.*id="katPraznoUskladitev"[^>]*hidden')
        blok = html.split('id="mediaPrazno"', 1)[1].split("\n            </div>", 1)[0]
        self.assertIn('id="mediaPraznoUskladitev" role="status" hidden', blok)
        with open(os.path.join(KOREN, "assets", "os", "katalog.css"), encoding="utf-8") as f:
            css = f.read()
        self.assertIn(".kat-prazno p.kat-prazno-uskladitev { font-size: 14px; color: var(--opozorilo); }", css)
        with open(os.path.join(KOREN, "assets", "os", "os.css"), encoding="utf-8") as f:
            self.assertIn("#r-media .media-prazno span.media-prazno-uskladitev { font-size: 14px; color: var(--opozorilo); }",
                          f.read())


if __name__ == "__main__":
    unittest.main()
