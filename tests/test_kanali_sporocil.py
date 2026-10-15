"""Vgrajeni kanali Sporocil (core/os_kanali_sporocil.py, core/os_splet.SpletnaAplikacija) zivo v WebKitGTK 6.0 (Xvfb),
brez omrezja in brez prijav: vsebina je lokalni HTML z naslovom https (posrednik na zaprta vrata - nic ne gre ven).

Lastnik, 15. 10. 2026: kanali se nalozijo ob zagonu, tecejo v realnem casu (skrit pogled se ne dusi), izklopljen kanal
se ne nalozi in se ob izklopu sprosti, znacka in obvestilo v < 1 s, klik na obvestilo odpre kanal."""
import os
import tempfile
import time
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DOM = tempfile.mkdtemp(prefix="safeer-kanali-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_DOM, ".config")
os.environ["XDG_CACHE_HOME"] = os.path.join(_DOM, ".cache")

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gdk, Gio, GLib, Gtk, WebKit  # noqa: E402

Gtk.init()

from core import config as _config  # noqa: E402
from core import os_kanali_sporocil, spletni_klepeti  # noqa: E402
from core.sporocila import vklop  # noqa: E402

IZVOR = "https://klepet.primer.invalid/"
TIKI = """<!doctype html><title>Klepet</title><script>
var n = 0; setInterval(function () { n++; document.title = "tiki " + n; }, 1000);
</script>"""


def _cakaj(pogoj, cas=8.0):
    kontekst = GLib.MainContext.default()
    rok = time.monotonic() + cas
    while time.monotonic() < rok:
        if pogoj():
            return True
        if not kontekst.iteration(False):
            time.sleep(0.005)
    return pogoj()


def _vsi(gradnik):
    otrok = gradnik.get_first_child()
    while otrok is not None:
        yield otrok
        yield from _vsi(otrok)
        otrok = otrok.get_next_sibling()


def _js(pogled, koda):
    pogled.evaluate_javascript(koda, -1, None, None, None, None, None)


class _Obvestila:
    def __init__(self):
        self.poslana = []

    def poslji(self, naslov, besedilo, ident, privzeto=None, **_k):
        self.poslana.append((naslov, besedilo, ident, privzeto))
        return ident


class Kanali(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.makedirs(_config.CONFIG_DIR, exist_ok=True)
        c = _config.ConfigManager()
        # Brez omrezja: zaprt posrednik (vrata 9); brez EasyList (pretvorba seznama bi preizkus le upocasnila).
        c.set("doh_enabled", False)
        c.set("secure_proxy_mode", "custom")
        c.set("secure_proxy_url", "http://127.0.0.1:9")
        c.set("easylist_enabled", False)
        c.set("dovoljenja_strani", {"klepet.primer.invalid": {"obvestila": "dovoli"}})
        from core.os_splet import VdelaniSplet
        cls.splet = VdelaniSplet(Gtk, Gdk, Gio, GLib, WebKit, KOREN, lambda: "sl", None, prvi_zavihek=False)
        cls.vklop_pot = os.path.join(_DOM, "vklop.json")

    def setUp(self):
        from unittest import mock
        p = mock.patch.object(vklop, "PRIVZETA_POT", os.path.join(_DOM, "sporocila.sqlite3"))
        p.start()
        self.addCleanup(p.stop)
        vklop.nastavi_sporocila(True)
        self.dogodki, self.odprti = [], []
        self.obvestila = _Obvestila()
        self.splet.config.set(spletni_klepeti.Kanali.KLJUC, [])
        self.k = os_kanali_sporocil.KanaliSporocil(
            Gtk, GLib, Gio, lambda: self.splet, self.splet.config, lambda: "sl",
            lambda vrsta, podatki: self.dogodki.append((time.monotonic(), vrsta, podatki)), self.odprti.append,
            obvestila=self.obvestila)
        self.addCleanup(self.k.ustavi_vse)

    def _lasten(self, ime, vklopljen=True):
        k = self.k.kanali.dodaj(url=IZVOR + ime, ime_kanala=ime)
        if not vklopljen:
            self.k.kanali.vklopi(k["id"], False)
        return k["id"]

    def test_zagon_nalozi_vklopljene_zaporedoma(self):
        a, b, c = self._lasten("a"), self._lasten("b", vklopljen=False), self._lasten("c")
        self.k.zazeni_vse()
        self.assertEqual(self.k.zivi, {}, "nalaganje gre v prosti cas glavne zanke (namizje je ze izrisano)")
        self.assertTrue(_cakaj(lambda: set(self.k.zivi) == {a, c}))
        self.assertNotIn(b, self.k.zivi, "izklopljen kanal se ne nalozi")
        self.assertLessEqual(len(self.k._nalaga), os_kanali_sporocil.HKRATI_OB_ZAGONU)
        # vklop ga takoj nalozi, izklop ga sprosti (pogled unicen, ne le skrit)
        self.k.vklopi(b, True)
        self.assertIn(b, self.k.zivi)
        pogled = self.k.zivi[a].aplikacija.pogled
        self.k.vklopi(a, False)
        self.assertNotIn(a, self.k.zivi)
        self.assertTrue(getattr(pogled, "_safeer_zaprt", False), "pogled je unicen")
        self.assertNotIn(pogled, self.splet.aplikacije)
        # izklopljena Sporocila: nic se ne nalozi
        self.k.ustavi_vse()
        vklop.nastavi_sporocila(False)
        self.k.zazeni_vse()
        _cakaj(lambda: False, 0.3)
        self.assertEqual(self.k.zivi, {})
        self.assertEqual(self.k.neprebrano_skupaj(), 0)
        with self.assertRaises(ValueError):
            self.k.dodaj(url=IZVOR + "x")

    def test_znacka_in_obvestilo_v_manj_kot_sekundi(self):
        kid = self._lasten("ana")
        self.k.zazeni_vse()
        self.assertTrue(_cakaj(lambda: kid in self.k.zivi))
        pogled = self.k.zivi[kid].aplikacija.pogled
        pogled.load_html("<!doctype html><title>Klepet</title>", IZVOR + "ana")
        self.assertTrue(_cakaj(lambda: pogled.get_title() == "Klepet"))
        self.dogodki.clear()
        zacetek = time.monotonic()
        _js(pogled, 'document.title = "(4) Klepet";')
        self.assertTrue(_cakaj(lambda: any(v == "kanaliSporocil" for _t, v, _p in self.dogodki), 2))
        cas = next(t for t, v, _p in self.dogodki if v == "kanaliSporocil") - zacetek
        self.assertLess(cas, 1.0, "znacka se posodobi v < 1 s (izmerjeno %.3f s)" % cas)
        self.assertEqual(self.k.kanali.najdi(kid)["neprebrano"], 4, "zadnje stevilo je shranjeno (znacka ob zagonu)")
        self.assertEqual(self.k.neprebrano_skupaj(), 4)
        _js(pogled, 'new Notification("Ana", {body: "Zivjo"});')
        self.assertTrue(_cakaj(lambda: self.obvestila.poslana, 3))
        naslov, besedilo, ident, klik = self.obvestila.poslana[0]
        # ime kanala (»ana«) je ze v naslovu obvestila - ni podvojeno; drugace »kanal · naslov«
        self.assertEqual((naslov, besedilo, ident), ("Ana", "Zivjo", "safeer-kanal-" + kid))
        klik()
        self.assertEqual(self.odprti, [kid], "klik na obvestilo odpre Sporocila na kanalu")
        # izklopljen kanal ne obvesca in ne steje
        self.k.vklopi(kid, False)
        self.assertEqual(self.k.neprebrano_skupaj(), 0)

    def test_mesto_nad_stranjo_in_preklop_brez_ponovnega_nalaganja(self):
        a, b = self._lasten("a"), self._lasten("b")
        okno = Gtk.Window()
        okno.set_default_size(900, 600)
        stran = WebKit.WebView()
        prekrivanje = Gtk.Overlay()
        prekrivanje.set_child(stran)
        okno.set_child(prekrivanje)
        okno.present()
        self.addCleanup(okno.destroy)
        self.assertTrue(_cakaj(lambda: okno.get_width() > 0))
        r = {"x": 200, "y": 60, "w": 650, "h": 500, "vw": 900, "vh": 600, "dpr": 1}
        self.assertEqual(self.k.pokazi(stran, prekrivanje, a, r), {"ok": True, "vgrajeno": True})
        plast = self.k.plasti[id(stran)]
        s = plast["sklad"]
        self.assertTrue(s.get_visible())
        self.assertEqual((s.get_margin_start(), s.get_margin_top(), s.get_margin_end(), s.get_margin_bottom()), (200, 60, 50, 40))
        self.assertFalse(s.get_hexpand() or s.get_vexpand(), "sklad ne sme razsiriti prekrivanja")
        self.assertIs(s.get_visible_child(), self.k.zivi[a].gradnik)
        nalaganja = []
        self.k.zivi[a].aplikacija.pogled.connect("load-changed", lambda p, d: nalaganja.append((time.monotonic(), d.value_nick)))
        # prvo nalaganje najprej konca (brez omrezja: neuspeh in nato stran z napako omrezja - sicer tekma):
        # 1,5 s brez dogodkov nalaganja
        self.assertTrue(_cakaj(lambda: self.k.zivi[a].nalozen and not self.k.zivi[a].aplikacija.pogled.is_loading()
                               and (not nalaganja or time.monotonic() - nalaganja[-1][0] > 1.5), 15))
        nalaganja.clear()
        self.k.pokazi(stran, prekrivanje, b, r)
        self.assertIs(s.get_visible_child(), self.k.zivi[b].gradnik)
        self.k.pokazi(stran, prekrivanje, a, dict(r, w=500))
        self.assertEqual(s.get_margin_end(), 200)
        _cakaj(lambda: False, 0.5)
        self.assertEqual(nalaganja, [], "preklop med kanali kanala ne nalozi znova")
        self.k.skrij(stran)
        self.assertFalse(s.get_visible())
        self.assertIn(a, self.k.zivi, "skrit kanal tece naprej")
        self.assertEqual(self.k.pokazi(stran, prekrivanje, "ni-ga", r)["ok"], False)

    def test_podatki_kanalov_so_zasciteni(self):
        self._lasten("a")
        self.k.kanali.dodaj(katalog="telegram")
        self.assertEqual(self.k.zasciteni(), {"primer.invalid", "telegram.org"})

    def test_brisanje_spleta_ne_izbrise_kanala(self):
        """»Izbrisi vse« in brisanje ob izhodu ne pobriseta prijave in shrambe dodanega kanala; »Izbrisi podatke
        kanala« jih (lastnik, 15. 10. 2026: kanali se ob zagonu nalozijo brez ponovne prijave)."""
        kid = self._lasten("shramba")
        self.k.zazeni_vse()
        self.assertTrue(_cakaj(lambda: kid in self.k.zivi))
        self.splet.zasciteni_podatki = self.k.zasciteni
        kanal = self.k.zivi[kid].aplikacija.pogled
        tuj = self.splet.nov_zavihek()
        self.addCleanup(self.splet.zapri_zavihek, tuj)
        shrani = "<!doctype html><title>x</title><script>localStorage.setItem('k','v');document.title='ok'</script>"
        kanal.load_html(shrani, IZVOR + "shramba")
        tuj.load_html(shrani, "https://tuja.drugo.invalid/")
        self.assertTrue(_cakaj(lambda: kanal.get_title() == "ok" and tuj.get_title() == "ok"))

        def imena():
            izid = {}
            self.splet.podatki().fetch(WebKit.WebsiteDataTypes.LOCAL_STORAGE, None,
                                       lambda m, r, *_: izid.setdefault("v", {z.get_name() for z in m.fetch_finish(r)}),
                                       None)
            _cakaj(lambda: "v" in izid, 5)
            return izid.get("v", set())
        _cakaj(lambda: {"primer.invalid", "drugo.invalid"} <= imena(), 5)
        self.assertTrue({"primer.invalid", "drugo.invalid"} <= imena(), imena())
        konec = []
        self.splet.izbrisi(["piskotki"], 0, lambda: konec.append(1))
        self.assertTrue(_cakaj(lambda: konec, 5))
        self.assertEqual(imena() & {"primer.invalid", "drugo.invalid"}, {"primer.invalid"},
                         "tuja stran je izbrisana, kanal ostane")
        self.k.izbrisi_podatke(kid)
        self.assertTrue(_cakaj(lambda: "primer.invalid" not in imena(), 5), "»Izbrisi podatke kanala« ga izbrise")

    def test_brisanje_po_obdobju_posteno_pove_kanale(self):
        """Casovno obdobje WebKit brise brez izbire strani: vmesnik pove, da se izbrisejo tudi kanali; pri »Vse« pove,
        da ostanejo. Brez kanalov opombe ni (pregled 15. 10. 2026)."""
        from core.os_splet import besedila
        self.splet.config.set("brisi_vrste", ["piskotki"])
        self.splet.config.set("brisi_obdobje", "ura")
        self.splet.zasciteni_podatki = lambda: set()
        self.addCleanup(lambda: setattr(self.splet, "zasciteni_podatki", lambda: set()))
        d = self.splet._izbrisi_podatke()
        self.addCleanup(d.destroy)
        self.assertFalse(d._opomba_kanalov.get_visible(), "brez kanalov ni opombe")
        d.destroy()
        self._lasten("opomba")
        self.splet.zasciteni_podatki = self.k.zasciteni
        d = self.splet._izbrisi_podatke()
        self.addCleanup(d.destroy)
        o = d._opomba_kanalov
        self.assertTrue(o.get_visible())
        self.assertEqual(o.get_text(), besedila("sl")["bp_kanali_obdobje"])
        izbira = [g for g in _vsi(d) if isinstance(g, Gtk.ComboBoxText)][0]
        izbira.set_active_id("vse")
        self.assertEqual(o.get_text(), besedila("sl")["bp_kanali_ostanejo"])
        for c in [g for g in _vsi(d) if isinstance(g, Gtk.CheckButton)]:
            c.set_active(False)
        self.assertFalse(o.get_visible(), "brez piskotkov in predpomnilnika kanali niso prizadeti")

    def test_skrit_kanal_tece_v_realnem_casu(self):
        """Stran v skritem kanalu (pogled ni v nobenem oknu) s setInterval 1 s naredi v 60 s ~60 tikov. Izmerjeno
        15. 10. 2026 v Xvfb: z dusenjem WebKita 33, brez (os_splet.izklopi_dusenje) 60."""
        kid = self._lasten("tiki")
        self.k.zazeni_vse()
        self.assertTrue(_cakaj(lambda: kid in self.k.zivi))
        pogled = self.k.zivi[kid].aplikacija.pogled
        self.assertIsNone(self.k.zivi[kid].gradnik.get_parent(), "kanal ni prikazan")
        pogled.load_html(TIKI, IZVOR + "tiki")
        self.assertTrue(_cakaj(lambda: (pogled.get_title() or "").startswith("tiki")))
        _cakaj(lambda: False, 60.0)
        tiki = int((pogled.get_title() or "tiki 0").split()[-1])
        self.assertGreaterEqual(tiki, 57, "skrit kanal se ne sme dusiti (tikov v 60 s: %d)" % tiki)


if __name__ == "__main__":
    unittest.main()
