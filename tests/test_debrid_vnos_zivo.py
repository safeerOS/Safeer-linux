"""Okno »Debrid storitve« skozi PRAVO stran (assets/os/index.html?predvajalnik=1, os.js) v WebKitGTK 6.0 (Xvfb) in
PRAVI most core/debrid.most: klic strani gre v Python (delovna nit, kot os_katalog.izvedi), odgovor nazaj v stran.

Lastnik 25. 10. 2026: kljuc TorBox in indeksator Usenet (NZBFinder) na prenosniku kot na TV, s preverbo ob vnosu.
Vrstica pove stanje kljuca (Android d1fdecc): »ključ velja ✓«, »ključ ne velja – vpiši znova« (401 med uporabo) ali
»ključ še ni preverjen« (izpad ob vpisu); nepreverjen se po odprtju okna preveri in vrstica osvezi NA MESTU (polje, ki ga
uporabnik tipka, ostane). Vzorec iz navodil se zavrne brez klica storitve.
Preizkus tipka kljuc (Enter), med preverbo sta polje in gumb zaklenjena, izid je v vrstici stanja (role=status), fokus
se vrne v polje, kljuc ne ostane v strani. Kljuci so izmisljeni; zbirka skrivnosti je v pomnilniku.
Storitve so privzeto ponaredki; SAFEER_ZIVO_KLJUCI=1 vprasa PRAVI TorBox (izmisljen kljuc mora biti zavrnjen).
Grokov pregled 40, S7 (lastnik 26. 10. 2026: »Nevarnost zaklepa računa je prioriteta«): izmisljen kljuc v zivem nacinu
NIKOLI ne gre Real-Debridu, AllDebridu ali indeksatorju - RD ob ugibanju kljucev zapre naslov IP (error 22) in z njim
pravi racun lastnika na istem IP, indeksatorji stejejo neuspele prijave. Preizkusi teh storitev se v zivem nacinu
preskocijo PRED vpisom (prej sele po klicu), varovalo v setUp ustavi vsak drug klic. TorBox naslova IP ne omejuje.
Zagon (nas WebKit): ./tools/nas_webkit.sh xvfb-run -a python3 -m pytest -q tests/test_debrid_vnos_zivo.py"""
import json
import os
import threading
import time
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    import gi

    gi.require_version("Gtk", "4.0")
    gi.require_version("WebKit", "6.0")
    from gi.repository import GLib, Gtk, WebKit  # noqa: E402
except (ImportError, ValueError) as _napaka:  # pragma: no cover - okolje brez GTK4/WebKit 6.0
    raise unittest.SkipTest("WebKitGTK 6.0 ni na voljo: %s" % _napaka)

from core import debrid, debrid_pravila as P  # noqa: E402

ZIVO = os.environ.get("SAFEER_ZIVO_KLJUCI") == "1"
KLJUC_TB = "7c1e9a4b-2f6d-4e8a-b3c5-9d0f1a2e6b74"     # izmisljen (prejsnji je bil vzorec - P.je_vzorec_kljuca)
KLJUC_RD = "R7mK2pX9vL4qT8wN3zB6cH1jF5dS0gY2aE7uI4oP9kM3nV8bQ6xZ"
KLJUC_AD = "aB3dE5gH7jK9mN1pQ3sT"
KLJUC_IX = "0123456789abcdef0123456789abcdef"

#: Most strani: mediaDebrid gre v vrsto, ki jo preizkus izvede v Pythonu; ostalo vrne null (kot prazen katalog).
MOST = """window.__zahteve = []; window.__odg = {}; window.__n = 0; window.__napake = []; window.addEventListener("error", function (e) { window.__napake.push(String(e.message) + " @" + e.lineno); });
window.SafeerOS = { klic: function (m, a) {
  if (m !== "mediaDebrid") return Promise.resolve(null);
  var id = ++window.__n;
  return new Promise(function (r) { window.__odg[id] = r; window.__zahteve.push({ id: id, a: a }); });
} };"""


def _cakaj(pogoj, cas=15.0):
    kontekst, rok = GLib.MainContext.default(), time.monotonic() + cas
    while time.monotonic() < rok:
        if pogoj():
            return True
        if not kontekst.iteration(False):
            time.sleep(0.01)
    return pogoj()


class _Zbirka:
    def __init__(self):
        self.z: dict = {}

    def skrij(self, s):
        k = "zbirka:%d" % (len(self.z) + 1000)
        self.z[k] = s
        return k

    def razkrij(self, k):
        return self.z[k]

    def pozabi(self, k):
        self.z.pop(k, None)


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon (Xvfb)")
class DebridVnos(unittest.TestCase):
    def setUp(self):
        self.zbirka = _Zbirka()
        nast = {"d": {}}
        self.d = debrid.Debrid(lambda: nast["d"], lambda x: nast.__setitem__("d", json.loads(json.dumps(x))),
                               self.zbirka.skrij, self.zbirka.razkrij, self.zbirka.pozabi)
        self.nast = nast
        if ZIVO:
            # Grokov pregled 40, S7: v zivem nacinu gre izmisljen kljuc samo TorBoxu - vse drugo je napaka preizkusa.
            pravi_klic = debrid.klic

            def varovalo(naslov, *a, **k):
                if not str(naslov).startswith("https://api.torbox.app/"):
                    raise AssertionError("zivi nacin: izmisljen kljuc samo TorBoxu, ne " + str(naslov).split("?")[0])
                return pravi_klic(naslov, *a, **k)
            for ime, nadomestek in (("klic", varovalo),
                                    ("indeksator_preveri", mock.Mock(side_effect=AssertionError("zivi nacin: brez indeksatorja"))),
                                    ("usenet_isci", mock.Mock(side_effect=AssertionError("zivi nacin: brez indeksatorja")))):
                zamenjava = mock.patch.object(debrid, ime, nadomestek)
                zamenjava.start()
                self.addCleanup(zamenjava.stop)
        upr = WebKit.UserContentManager()
        upr.add_script(WebKit.UserScript.new(MOST, WebKit.UserContentInjectedFrames.TOP_FRAME,
                                             WebKit.UserScriptInjectionTime.START, None, None))
        okno = Gtk.Window()
        okno.set_default_size(1280, 900)
        self.pogled = WebKit.WebView(user_content_manager=upr)
        okno.set_child(self.pogled)
        okno.present()
        self.addCleanup(okno.destroy)
        self.pogled.load_uri("file://" + os.path.join(KOREN, "assets", "os", "index.html") + "?predvajalnik=1&jezik=sl")
        # Stran je povezala dogodke (poveziDogodke), ko so gumbi kategorij Medijskega centra narisani.
        self.assertTrue(_cakaj(lambda: self._js("!!document.querySelector('#mediaNavKategorije [data-kategorija]')")))
        self._odpri()
        self._streži()
        self.assertTrue(_cakaj(lambda: self._js("!!document.querySelector('#debridSeznam [data-id=\"torbox\"] input')")))
        self.assertTrue(self._js("document.getElementById('slojDebrid').classList.contains('viden')"))

    def _odpri(self):
        """Odpre okno, kot ga odpre izbira »Nastavitve debrida …« ob zvrsteh (zaprto okno najprej zapre)."""
        self._js("(function () { document.getElementById('slojDebrid').classList.remove('viden');"
                 " var s = document.getElementById('mediaDebrid'); s.add(new Option('x', 'nastavitve'));"
                 " s.value = 'nastavitve'; s.dispatchEvent(new Event('change')); return 1; })()")

    def _js(self, koda):
        izid = {}

        def konec(p, r, *_):
            try:
                izid["v"] = json.loads(p.evaluate_javascript_finish(r).to_string() or "null")
            except GLib.Error as e:  # pragma: no cover - napaka skripte pove preizkus
                izid["v"] = "napaka: %s" % e.message
        self.pogled.evaluate_javascript("JSON.stringify((%s)) || \"null\"" % koda, -1, None, None, None, konec, None)
        _cakaj(lambda: "v" in izid, 10)
        return izid.get("v")

    def _streži(self, cas=20.0):
        """Izvede cakajoce klice mediaDebrid v pravem mostu (delovna nit) in odgovor vrne strani."""
        konec = time.monotonic() + cas
        while time.monotonic() < konec:
            if not self._postrezi_cakajoce():
                return
            _cakaj(lambda: False, 0.1)

    def _postrezi_cakajoce(self) -> list:
        """En krog: klici, ki ta trenutek cakajo (brez tistih, ki jih stran poslje po odgovoru). Vrne njihove ukaze."""
        zahteve = self._js("window.__zahteve.splice(0)") or []
        for z in zahteve:
            izid = {}
            nit = threading.Thread(target=lambda a=z["a"]: izid.__setitem__("v", debrid.most(self.d, list(a))))
            nit.start()
            _cakaj(lambda: not nit.is_alive(), 20)
            self._js("(window.__odg[%d](%s), 1)" % (z["id"], json.dumps(izid.get("v"))))
        return [z["a"] for z in zahteve]

    def _vpisi(self, vrstica, vrednosti):
        """Vpise vrednosti v polja vrstice in pritisne Enter v zadnjem (kot uporabnik s tipkovnico)."""
        return self._js("""(function () {
          var p = document.querySelectorAll('#debridSeznam [data-id="%s"] input'), v = %s;
          for (var i = 0; i < v.length; i++) { p[i].focus(); p[i].value = v[i]; }
          p[v.length - 1].dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
          var g = document.querySelector('#debridSeznam [data-id="%s"] button');
          return { zaklenjeno: p[v.length - 1].disabled && g.disabled, zaseden: g.getAttribute('aria-busy'),
                   stanje: document.getElementById('debridStanjeVnosa').textContent,
                   vloga: document.getElementById('debridStanjeVnosa').getAttribute('role') };
        })()""" % (vrstica, json.dumps(vrednosti), vrstica))

    def _klikni(self, vrstica, besedilo):
        """Klik gumba z [besedilo] v vrstici (kot uporabnik)."""
        return self._js("""(function () {
          var g = Array.prototype.filter.call(document.querySelectorAll('#debridSeznam [data-id="%s"] button'),
                                              function (b) { return b.textContent === %s; })[0];
          if (!g) return 0; g.click(); return 1; })()""" % (vrstica, json.dumps(besedilo)))

    def _po(self, vrstica):
        return self._js("""(function () {
          var a = document.activeElement, v = document.querySelector('#debridSeznam [data-id="%s"]');
          return { stanje: document.getElementById('debridStanjeVnosa').textContent, opis: v.querySelector('small').textContent,
                   fokus_v_vrstici: v.contains(a), fokus_vrsta: a && a.type, vrednosti: Array.prototype.map.call(v.querySelectorAll('input'), function (p) { return p.value; }),
                   gumbi: Array.prototype.map.call(v.querySelectorAll('button'), function (b) { return [b.textContent, b.getAttribute('aria-label'), b.disabled]; }),
                   html: document.body.innerHTML };
        })()""" % vrstica)

    def _minuta(self):
        """Grokov pregled 40, S8: isti kljuc gre storitvi najvec enkrat na minuto - preizkus premakne zadnji klic nazaj."""
        for k in list(self.d._rocna):
            self.d._rocna[k] -= P.ROCNA_PREVERBA_S + 1

    def _brez_pravih(self, storitev: str):
        """Grokov pregled 40, S7: zivi nacin izmisljenega kljuca ne poslje [storitev] - preskok PRED vpisom."""
        if ZIVO:
            self.skipTest("zivi nacin: izmisljen kljuc ne gre storitvi %s (zaklep racuna ali IP)" % storitev)

    def test_torbox_zavrnjen_veljaven_in_odstranjen(self):
        pred = self._vpisi("torbox", [KLJUC_TB])
        self.assertEqual((pred["zaklenjeno"], pred["zaseden"], pred["stanje"], pred["vloga"]),
                         (True, "true", "Preverjam ključ …", "status"))
        preveri = mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_NEVELJAVEN, None))
        with (mock.MagicMock() if ZIVO else preveri):
            self._streži()
        po = self._po("torbox")
        self.assertTrue(po["stanje"].startswith("TorBox je ta ključ zavrnil – ni shranjen."), po["stanje"])
        self.assertIn("torbox.app", po["stanje"])
        self.assertEqual(self.zbirka.z, {})
        self.assertTrue(po["fokus_v_vrstici"])
        self.assertNotIn(KLJUC_TB, po["html"] + json.dumps(po["vrednosti"]))
        if ZIVO:
            return                                  # pravi TorBox: izmisljen kljuc je zavrnjen - dovolj
        self._minuta()                              # isti kljuc znova sele cez minuto (S8)
        with mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_VELJAVEN, P.TORBOX_PRO)):
            self._vpisi("torbox", [KLJUC_TB])
            self._streži()
        po = self._po("torbox")
        self.assertEqual(po["stanje"], "Ključ TorBox je veljaven in shranjen (šifriran) · paket Pro.")
        self.assertEqual(po["opis"], "ključ velja ✓ · paket Pro")
        self.assertEqual(list(self.zbirka.z.values()), [KLJUC_TB])
        self.assertNotIn(KLJUC_TB, po["html"])
        self.assertEqual(po["gumbi"][1][:2], ["Odstrani ključ", "Odstrani ključ – TorBox"])
        self._js("(document.querySelectorAll('#debridSeznam [data-id=\"torbox\"] button')[1].click(), 1)")
        self._streži()
        po = self._po("torbox")
        self.assertEqual(po["stanje"], "Ključ TorBox je odstranjen s tega računalnika.")
        self.assertEqual((self.zbirka.z, len(po["gumbi"])), ({}, 1))
        self.assertTrue(po["fokus_v_vrstici"])

    def test_nzbfinder_zavrnjen_naslov_ostane(self):
        self._brez_pravih("nzbfinder.ws")
        pred = self._vpisi("usenet", ["https://nzbfinder.ws", KLJUC_IX])
        self.assertEqual((pred["zaklenjeno"], pred["stanje"]), (True, "Preverjam ključ …"))
        with mock.patch.object(debrid, "indeksator_preveri", return_value=P.PREVERBA_NEVELJAVEN):
            self._streži()
        po = self._po("usenet")
        self.assertEqual(po["stanje"], "Indeksator je ključ zavrnil – ni shranjen. Preveri ga na strani profila indeksatorja.")
        self.assertEqual(po["vrednosti"], ["https://nzbfinder.ws", ""])      # naslova ni treba tipkati znova
        self.assertEqual(po["fokus_vrsta"], "password")
        self.assertIn("nzbfinder.ws/profile", po["opis"])
        self.assertEqual(self.zbirka.z, {})
        self.assertNotIn(KLJUC_IX, po["html"])

    def test_vzorec_zavrnjen_brez_klica_storitve(self):
        """Lastnik 25. 10. 2026: vzorec »XXXXXXXX-XXXX-…« iz navodil se je shranil kot »ključ vpisan ✓«."""
        self._vpisi("torbox", ["XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"])
        with mock.patch.object(debrid, "klic", side_effect=AssertionError("vzorec ne gre do storitve")) as k:
            self._streži()
        po = self._po("torbox")
        self.assertEqual(k.call_count, 0)
        self.assertEqual(po["stanje"], "To ni ključ TorBox – prilepi svoj ključ s strani torbox.app → Settings → API, "
                                       "brez presledkov (vzorec iz navodil ni ključ).")
        self.assertEqual((self.zbirka.z, po["vrednosti"]), ({}, [""]))

    def test_vrstica_nepreverjen_in_ne_velja(self):
        """Izpad ob vpisu: »še ni preverjen« (prej »vpisan ✓«); 401 med uporabo: »ne velja – vpiši znova«."""
        self._brez_pravih("TorBox (izpad ni mogoc)")
        self._vpisi("torbox", [KLJUC_TB])
        with mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_NI_ODGOVORA, None)):
            self._streži()
        po = self._po("torbox")
        self.assertEqual(po["opis"], "ključ še ni preverjen")
        self.assertTrue(po["stanje"].startswith("Ključ TorBox je shranjen (šifriran), a ga TorBox zdaj ni mogel potrditi"))
        with mock.patch.object(debrid, "torbox_tok", return_value=debrid.Izid(napaka=P.NAPAKA_KLJUC, ponudnik=P.TORBOX)):
            self.d.tok("b" * 40)                           # predvajanje: TorBox kljuc zavrne (401)
        self._odpri()
        with mock.patch.object(debrid, "torbox_preveri", side_effect=AssertionError("ne velja se ne preverja znova")):
            self._streži()
        po = self._po("torbox")
        self.assertEqual(po["opis"], "ključ ne velja – Safeer ga ne uporablja; vpiši novega ali pritisni »Preveri«")
        self.assertNotIn(KLJUC_TB, po["html"])
        # Lastnik 26. 10. 2026 (zaklep racuna): zavrnjen kljuc se znova preveri SAMO ob gumbu »Preveri«.
        self.assertIn(["Preveri", "Preveri – TorBox", False], po["gumbi"])
        self._minuta()
        self._klikni("torbox", "Preveri")
        with mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_VELJAVEN, P.TORBOX_PRO)) as tb:
            self.assertEqual(self._postrezi_cakajoce(), [["preveri", "torbox"]])
        self.assertEqual(tb.call_count, 1)
        _cakaj(lambda: False, 0.2)
        po = self._po("torbox")
        self.assertEqual((po["opis"], po["stanje"]), ("ključ velja ✓ · paket Pro", "TorBox: ključ velja ✓"))
        self.assertNotIn("Preveri", [g[0] for g in po["gumbi"]])

    def test_zaklenjen_racun_vrstica_pove_kaj_narediti(self):
        """Lastnik 26. 10. 2026: RD 14 »account locked« - kljuc shranjen, vrstica pove »odkleni na real-debrid.com«,
        Safeer RD ne klice do »Preveri«."""
        self._brez_pravih("Real-Debrid")
        self._vpisi("realdebrid", [KLJUC_RD])
        with mock.patch.object(debrid, "klic", return_value=debrid.Odgovor(403, '{"error": "account_locked", "error_code": 14}')):
            self._streži()
        po = self._po("realdebrid")
        self.assertTrue(po["opis"].startswith("Real-Debrid je račun zaklenil ali ne dovoli tega naslova IP – odkleni ga na "
                                              "real-debrid.com"), po["opis"])
        self.assertEqual(po["stanje"], po["opis"])
        self.assertIn(["Preveri", "Preveri – Real-Debrid", False], po["gumbi"])
        self.assertNotIn(KLJUC_RD, po["html"])
        # Grokov pregled 40, S8: takoj po vpisu »Preveri« ne gre k RD - vrstica pove, koliko je treba pocakati.
        self._klikni("realdebrid", "Preveri")
        with mock.patch.object(debrid, "klic", side_effect=AssertionError("isti kljuc najvec 1 na minuto")):
            self.assertEqual(self._postrezi_cakajoce(), [["preveri", "realdebrid"]])
        _cakaj(lambda: False, 0.2)
        po = self._po("realdebrid")
        self.assertTrue(po["stanje"].startswith("Ta ključ je bil preverjen pred manj kot minuto – počakaj še "), po["stanje"])
        self.assertTrue(po["opis"].startswith("Real-Debrid je račun zaklenil"), po["opis"])
        # Grokov pregled 40, S2: RD ne odgovori (503) - »zaklenjen« ostane in vrstica to pove (prej »še ni preverjen«).
        self._minuta()
        self._klikni("realdebrid", "Preveri")
        with mock.patch.object(debrid, "klic", return_value=debrid.Odgovor(503, "")) as k:
            self.assertEqual(self._postrezi_cakajoce(), [["preveri", "realdebrid"]])
        self.assertEqual(k.call_count, 1)
        _cakaj(lambda: False, 0.2)
        po = self._po("realdebrid")
        self.assertTrue(po["stanje"].startswith("Real-Debrid se ni odzval (ni povezave, omejitev zahtev ali napaka storitve), "
                                                "zato stanje ostaja – Real-Debrid je račun zaklenil"), po["stanje"])
        self.assertTrue(po["opis"].startswith("Real-Debrid je račun zaklenil"), po["opis"])
        self.assertEqual(self.d.stanje_kljuca(P.REAL_DEBRID), P.STANJE_ZAKLENJEN)
        self._minuta()
        self._klikni("realdebrid", "Preveri")
        with mock.patch.object(debrid, "klic", return_value=debrid.Odgovor(200, '{"id": 7, "username": "u"}')) as k:
            self.assertEqual(self._postrezi_cakajoce(), [["preveri", "realdebrid"]])
        self.assertEqual(k.call_count, 1)
        _cakaj(lambda: False, 0.2)
        self.assertEqual(self._po("realdebrid")["opis"], "ključ velja ✓")

    def test_nepreverjen_preverjen_po_odprtju_vrstica_na_mestu(self):
        """Kljuc iz prejsnje razlicice (brez stanja): okno ga preveri; vrstica se osvezi, polje drugega kljuca ostane."""
        self.d.nastavi_kljuc(P.TORBOX, KLJUC_TB)
        self.d.nastavi_indeksator("https://nzbfinder.ws", KLJUC_IX)
        self._odpri()
        self.assertEqual(self._postrezi_cakajoce(), [[]])
        self.assertEqual(self._po("torbox")["opis"], "ključ še ni preverjen")
        self.assertTrue(_cakaj(lambda: self._js("window.__zahteve.length") == 1, 5))
        # Uporabnik medtem tipka kljuc Real-Debrid: osvezitev vrstic ga ne sme pobrisati.
        self._js("(function () { var p = document.querySelector('#debridSeznam [data-id=\"realdebrid\"] input');"
                 " p.focus(); p.value = 'tipkam'; return 1; })()")
        with mock.patch.object(debrid, "torbox_preveri", return_value=(P.PREVERBA_VELJAVEN, P.TORBOX_PRO)) as tb, \
                mock.patch.object(debrid, "indeksator_preveri", return_value=P.PREVERBA_NEVELJAVEN) as ix:
            self.assertEqual(self._postrezi_cakajoce(), [["preveri"]])
        self.assertEqual((tb.call_count, ix.call_count), (1, 1))
        _cakaj(lambda: False, 0.2)
        self.assertEqual(self._po("torbox")["opis"], "ključ velja ✓ · paket Pro")
        self.assertEqual(self._po("usenet")["opis"], "Indeksator: nzbfinder.ws · ključ ne velja – Safeer ga ne uporablja; vpiši novega ali pritisni »Preveri«")
        rd = self._po("realdebrid")
        self.assertEqual((rd["vrednosti"], rd["fokus_v_vrstici"]), (["tipkam"], True))
        self.assertEqual(self._js("window.__zahteve.length"), 0)

    def test_real_debrid_in_alldebrid_preverjena(self):
        """Prej sta se RD in AD shranila brez preverbe (»Ključ … je shranjen«), tudi zavrnjen kljuc."""
        self._brez_pravih("Real-Debrid in AllDebrid")
        self._vpisi("realdebrid", [KLJUC_RD])
        with mock.patch.object(debrid, "klic", return_value=debrid.Odgovor(401, '{"error": "bad_token", "error_code": 8}')):
            self._streži()
        po = self._po("realdebrid")
        self.assertEqual(po["stanje"], "Real-Debrid je ta ključ zavrnil – ni shranjen. Preveri ga na real-debrid.com/apitoken.")
        self.assertEqual(self.zbirka.z, {})
        self._vpisi("alldebrid", [KLJUC_AD])
        with mock.patch.object(debrid, "klic",
                               return_value=debrid.Odgovor(200, '{"status": "error", "error": {"code": "AUTH_BAD_APIKEY"}}')):
            self._streži()
        self.assertEqual(self._po("alldebrid")["stanje"],
                         "AllDebrid je ta ključ zavrnil – ni shranjen. Preveri ga na alldebrid.com/apikeys.")
        self.assertEqual(self.zbirka.z, {})
        self._minuta()
        with mock.patch.object(debrid, "klic", return_value=debrid.Odgovor(200, '{"id": 1, "username": "u", "email": "e@primer.test"}')):
            self._vpisi("realdebrid", [KLJUC_RD])
            self._streži()
        po = self._po("realdebrid")
        self.assertEqual((po["stanje"], po["opis"]), ("Ključ Real-Debrid je veljaven in shranjen (šifriran).", "ključ velja ✓"))
        for skrito in (KLJUC_RD, "e@primer.test"):
            self.assertNotIn(skrito, po["html"])


if __name__ == "__main__":
    unittest.main()
