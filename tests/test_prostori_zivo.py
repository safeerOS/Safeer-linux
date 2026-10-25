"""Prostori (Safeer Link Spaces, MVP) skozi PRAVO stran (assets/os/index.html, os.js) in pravi most Safeer OS v WebKitGTK 6.0
(Xvfb): gumb v glavi in Super+Tab (safeer_os._na_tipko) odpreta preklopnik, puscice izbirajo, Enter/klik odpre zaslon
naprave po obstojeci poti Safeer Controla (Upravljaj za racunalnik, OdpriTukaj s CEL_ZASLON za Android), »+« odpre dodajanje
naprave, Esc zapre in vrne fokus. Safeer Control je nadomescen (safeer_os._control_naprave), vse drugo je pravo.

Potrebuje WebKitGTK 6.0 in zaslon, sicer se preskoci (kot drugi *_zivo preizkusi). Z nasim WebKitom:
GI_TYPELIB_PATH=/usr/lib/safeer-webkit/lib/girepository-1.0 LD_LIBRARY_PATH=/usr/lib/safeer-webkit/lib \
xvfb-run -a python3 -m pytest -q tests/test_prostori_zivo.py"""
import json
import os
import tempfile
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DOM = tempfile.mkdtemp(prefix="safeer-prostori-zivo-")
os.environ["XDG_CONFIG_HOME"] = os.path.join(_DOM, ".config")
os.environ["XDG_CACHE_HOME"] = os.path.join(_DOM, ".cache")
os.environ["XDG_DATA_HOME"] = os.path.join(_DOM, ".local", "share")
os.makedirs(os.path.join(_DOM, ".cache"), exist_ok=True)

try:
    import gi  # noqa: E402

    gi.require_version("Gtk", "4.0")
    gi.require_version("Gdk", "4.0")
    gi.require_version("WebKit", "6.0")
    from gi.repository import Gdk, GLib, Gtk  # noqa: E402
except (ImportError, ValueError) as e:  # brez WebKitGTK 6.0 preizkusa ni (prej: ERROR ob zbiranju, pregled 25. 10. 2026)
    raise unittest.SkipTest("potrebuje WebKitGTK 6.0: %s" % e)
if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
    raise unittest.SkipTest("potrebuje zaslon (xvfb-run -a)")

Gtk.init()

import safeer_os as so  # noqa: E402
from tests.test_stranska_vrstica_zivo import RAZPOLOZLJIVO, _cakaj, _Nic  # noqa: E402

PRAVE = ("_nov_pogled", "_na_sporocilo", "_obdelaj_klic", "_odgovori", "_js", "_dogodek", "_na_tipko",
         "_prostori", "_prostor_odpri", "_prostor_slicica", "_prostori_rob", "_iz_gledalca")

ZLO_OKNO = '"><img src=x onerror="window.__xss=2">'
NAPRAVE = [
    {"id": "jaz-control", "ime": "Ta", "zmoznosti": ["desktop"], "platforma": "linux", "ta": True, "ozji": True},
    {"id": "pc-1-control", "ime": "Pisarna", "zmoznosti": ["desktop", "apps"], "platforma": "windows", "vrsta": "control",
     "ozji": True},
    {"id": "t-1-os", "ime": "Tablica", "zmoznosti": ["zaslon.deli", "remote"], "platforma": "tablet", "ozji": True},
    {"id": "tuj", "ime": "Tuj telefon", "zmoznosti": ["zaslon.deli"], "platforma": "phone", "ozji": False},
]


class _Namizja:
    """Nadomestna namizja Cinnamona (core/os_delovni_prostori.Namizja): seznam, preklop in dodajanje se zapisejo."""

    def __init__(self):
        self.seznam_ = []
        self.klici = []

    def seznam(self, izloci=None):
        return [dict(n) for n in self.seznam_]

    def preklopi(self, st):
        self.klici.append(("preklopi", st))
        return {"ok": isinstance(st, int) and any(n["st"] == st for n in self.seznam_), "st": st}

    def dodaj(self):
        self.klici.append(("dodaj",))
        return {"ok": True, "st": len(self.seznam_)}


NAMIZJA = [{"st": 0, "ime": "D1", "trenutno": True, "okna": [{"x": 0.1, "y": 0.1, "w": 0.5, "h": 0.5, "naslov": "Urejevalnik"}]},
           {"st": 1, "ime": "D2", "trenutno": False, "okna": [{"x": 0.2, "y": 0.2, "w": 0.4, "h": 0.4, "naslov": "Terminal"},
                                                              {"x": 0.5, "y": 0.1, "w": 0.4, "h": 0.6, "naslov": ZLO_OKNO}]},
           {"st": 2, "ime": "D3", "trenutno": False, "okna": []}]


class _Shramba(dict):
    zapisi = 0

    def set(self, k, v):
        self.zapisi += 1
        self[k] = v


ZLO = '<img src=x onerror="window.__xss=1">Pisarna'


def _os_razred(jezik):
    imena = {ime: so.SafeerOS.__dict__[ime] for ime in PRAVE}

    class Os:
        posnetek = ""

        def __init__(self):
            self.pogledi, self._os_kontekst, self.razdelki = [], None, []
            # Prej videna naprava, ki je zdaj ni v Linku: ostane na svojem mestu (prva), oznacena »ni povezana«.
            self.shramba = _Shramba(prostori=[{"kljuc": "tv-9", "id": "tv-9-os", "ime": "Kuhinja", "vrsta": "tv",
                                               "nacin": "zaslon", "dodana": 1, "videna": 1}])

        def __getattr__(self, ime):
            return _Nic()

        def _na_politiko(self, *_a):
            return False

        def _zacetek(self):
            return {"jezik": jezik, "sporocila": True, "platforma": "linux", "mape": [], "razlicica": "1.0.133",
                    "razpolozljivo": RAZPOLOZLJIVO, "agent": {"na_voljo": False}, "povezava": {"stanje": "povezan"}}

        def _katalog_most(self):
            class _K:
                @staticmethod
                def pozna(_m):
                    return False
            return _K()
    for ime, f in imena.items():
        setattr(Os, ime, f)
    return Os


class Prostori(unittest.TestCase):
    JEZIK = "sl"
    NI_NASLOVA = "neposredno"

    def setUp(self):
        self.klici = []
        self.odgovori = {}
        self.naprave = [dict(n) for n in NAPRAVE]

        def control(metoda, *a):
            self.klici.append((metoda,) + a)
            if metoda == "Seznam":
                return {"ok": True, "naprave": self.naprave}
            return self.odgovori.get(metoda, {"ok": True})
        p = mock.patch.object(so, "_control_naprave", side_effect=control)
        p.start()
        self.addCleanup(p.stop)
        # Programi naprav (napraveSProgrami): None = prava funkcija nad nadomescenim Controlom, sicer ta seznam.
        self.programi_naprav = None
        izvirnik = so.naprave_s_programi
        p3 = mock.patch.object(so, "naprave_s_programi", side_effect=lambda *a: izvirnik(*a) if self.programi_naprav is None
                               else self.programi_naprav)
        p3.start()
        self.addCleanup(p3.stop)
        self.dejanja = []
        p2 = mock.patch.object(so, "control_dejanje", side_effect=lambda ime, *_a: self.dejanja.append(ime) or True)
        p2.start()
        self.addCleanup(p2.stop)
        # Lokalna namizja (wmctrl) nadomescena: privzeto jih ni (kot Wayland ali brez wmctrl) - MVP vedenje.
        self.namizja = _Namizja()
        p4 = mock.patch.object(so, "_lokalna_namizja", return_value=self.namizja)
        p4.start()
        self.addCleanup(p4.stop)
        p5 = mock.patch.object(so, "_prostori_slicice", so.link_prostori.Slicice())
        p5.start()
        self.addCleanup(p5.stop)
        self.os = _os_razred(self.JEZIK)()
        self.pogled = self.os._nov_pogled("index.html")
        self.os.pogled = self.pogled
        self.okno = Gtk.Window()
        self.okno.set_default_size(1260, 860)
        self.okno.set_child(self.pogled)
        self.okno.present()
        self.addCleanup(self.okno.destroy)
        self.assertTrue(_cakaj(lambda: self._js("!!window.SafeerOS && !!document.getElementById('gumbProstori')") is True, 20))
        self.assertTrue(_cakaj(lambda: self._js("document.getElementById('gumbProstori').title") not in (None, "", "prostoriNamig"), 10))

    def _js(self, koda):
        izid = {}

        def konec(p, r, *_):
            try:
                izid["v"] = json.loads(p.evaluate_javascript_finish(r).to_string() or "null")
            except Exception as e:  # noqa: BLE001
                izid["v"] = "napaka:%s" % e
        self.pogled.evaluate_javascript("JSON.stringify((%s)) || \"null\"" % koda, -1, None, None, None, konec, None)
        _cakaj(lambda: "v" in izid, 5)
        return izid.get("v")

    def tipka(self, kljuc, **mod):
        self._js("document.activeElement.dispatchEvent(new KeyboardEvent('keydown', %s)), 1"
                 % json.dumps(dict({"key": kljuc, "bubbles": True, "cancelable": True}, **mod)))

    def odprto(self):
        return self._js("document.getElementById('slojProstori').classList.contains('viden')")

    def ploscice(self):
        return self._js("Array.prototype.map.call(document.querySelectorAll('#prostoriTrak button.prostor'), "
                        "function (b) { return b.getAttribute('aria-label'); })")

    def fokus(self):
        return self._js("document.activeElement.getAttribute('data-prostor')")

    def pocakaj_naprave(self):
        self.assertTrue(_cakaj(lambda: len(self.ploscice() or []) == 5, 10), self.ploscice())

    def test_gumb_odpre_ploscice_v_stalnem_redu(self):
        g = "document.getElementById('gumbProstori')"
        self.assertEqual(self._js(g + ".getAttribute('aria-label')"), "Prostori – zasloni tvojih naprav (Super+Tab)")
        self.assertEqual(self._js(g + ".getAttribute('aria-expanded')"), "false")
        self._js(g + ".focus(), " + g + ".click(), 1")
        self.assertTrue(self.odprto())
        self.pocakaj_naprave()
        p = self.ploscice()
        self.assertEqual(p[0], "Ta računalnik, Tukaj si")
        self.assertTrue(p[1].startswith("Kuhinja, televizor, Ni povezana"), p[1])     # zapomnjena, na svojem mestu
        self.assertEqual(p[2], "Pisarna, računalnik, Povezana")
        self.assertEqual(p[3], "Tablica, tablica, Povezana")
        self.assertEqual(p[4], "Dodaj, Namizje, napravo ali način")
        self.assertNotIn("Tuj", json.dumps(p, ensure_ascii=False), "izven ozjega kroga ni prostor")
        self.assertEqual(self.fokus(), "0", "gumb odpre na tem racunalniku")
        self.assertEqual(self._js(g + ".getAttribute('aria-expanded')"), "true")
        self.assertEqual(self._js("document.querySelector('#prostoriTrak .prostor.ta').getAttribute('aria-current')"), "true")
        # Zapis ima nove naprave na koncu, zapomnjeno spredaj (stalna mesta).
        self.assertEqual([z["kljuc"] for z in self.os.shramba["prostori"]], ["tv-9", "pc-1", "t-1"])
        # Puscice, Home/End; Esc zapre in vrne fokus gumbu.
        self.tipka("ArrowRight")
        self.assertEqual(self.fokus(), "1")
        self.tipka("ArrowLeft")
        self.tipka("ArrowLeft")
        self.assertEqual(self.fokus(), "4", "iz prvega levo na zadnjega")
        self.tipka("Home")
        self.assertEqual(self.fokus(), "0")
        # Crka med odprtim preklopnikom ne gre v iskanje.
        self.tipka("w")
        self.assertEqual(self._js("document.getElementById('iskanje').value"), "")
        self.tipka("Escape")
        self.assertFalse(self.odprto())
        self.assertEqual(self._js("document.activeElement.id"), "gumbProstori")

    def test_super_tab_iz_gtk(self):
        # Pravi upravljalec tipk okna (faza zajema): Super+Tab odpre in izbere naslednji prostor, vnovic naprej, Shift nazaj.
        self.assertTrue(self.os._na_tipko(self.okno, so._Tipka(Gdk.KEY_Tab, Gdk.ModifierType.SUPER_MASK, 0)))
        self.assertTrue(_cakaj(lambda: self.odprto() is True, 5))
        self.assertTrue(_cakaj(lambda: self.fokus() == "1", 5), self.fokus())
        self.pocakaj_naprave()
        self.os._na_tipko(self.okno, so._Tipka(Gdk.KEY_Tab, Gdk.ModifierType.SUPER_MASK, 0))
        self.assertTrue(_cakaj(lambda: self.fokus() == "2", 5), self.fokus())
        self.os._na_tipko(self.okno, so._Tipka(Gdk.KEY_ISO_Left_Tab, Gdk.ModifierType.SUPER_MASK | Gdk.ModifierType.SHIFT_MASK, 0))
        self.assertTrue(_cakaj(lambda: self.fokus() == "1", 5), self.fokus())
        # Navaden Tab ni bliznjica.
        self.assertFalse(self.os._na_tipko(self.okno, so._Tipka(Gdk.KEY_Tab, 0, 0)))

    def test_enter_odpre_racunalnik(self):
        self._js("document.getElementById('gumbProstori').click(), 1")
        self.pocakaj_naprave()
        self._js("document.querySelector('[data-prostor=\"2\"]').click(), 1")
        # Krog 2: celozaslonsko (ProstorOdpri: "" = oddaljeni zaslon racunalnika, "1" = celo).
        self.assertTrue(_cakaj(lambda: ("ProstorOdpri", "pc-1-control", "", "1") in self.klici, 10), self.klici)
        self.assertTrue(_cakaj(lambda: self.odprto() is False, 5))
        self.assertIn("Pisarna", self._js("document.getElementById('obvestilo').textContent"))

    def test_android_cel_zaslon_s_potrditvijo(self):
        self.odgovori["ProstorOdpri"] = {"ok": True, "tu": True}
        self._js("document.getElementById('gumbProstori').click(), 1")
        self.pocakaj_naprave()
        self._js("document.querySelector('[data-prostor=\"3\"]').focus(), 1")
        self._js("document.activeElement.click(), 1")
        self.assertTrue(_cakaj(lambda: ("ProstorOdpri", "t-1-os", "safeer.cel.zaslon", "1") in self.klici, 10), self.klici)
        self.assertTrue(_cakaj(lambda: self.odprto() is False, 5))
        self.assertEqual(self._js("document.getElementById('obvestilo').textContent"),
                         "Na napravi Tablica potrdi deljenje zaslona – nato se odpre tukaj.")

    def test_napaka_ostane_v_preklopniku(self):
        self.odgovori["ProstorOdpri"] = {"ok": False, "koda": "ni_naslova", "message": "x"}
        self._js("document.getElementById('gumbProstori').click(), 1")
        self.pocakaj_naprave()
        self._js("document.querySelector('[data-prostor=\"2\"]').click(), 1")
        self.assertTrue(_cakaj(lambda: self.NI_NASLOVA in (self._js("document.getElementById('prostoriStanje').textContent") or ""), 10))
        self.assertTrue(self.odprto())

    def test_brez_povezave_ne_klice(self):
        self._js("document.getElementById('gumbProstori').click(), 1")
        self.pocakaj_naprave()
        pred = len(self.klici)
        self._js("document.querySelector('[data-prostor=\"1\"]').click(), 1")
        self.assertEqual(self._js("document.getElementById('prostoriStanje').textContent"),
                         "Naprava Kuhinja zdaj ni povezana. Vklopi jo ali na njej odpri Safeer.")
        _cakaj(lambda: False, 0.3)
        # Odpiranja ni; slicica povezanega racunalnika (krog 2) med odprtim preklopnikom je dovoljena.
        self.assertFalse([k for k in self.klici[pred:] if k[0] != "Seznam" and k[2:3] != ("screen.thumb",)],
                         self.klici[pred:])
        self.assertTrue(self.odprto())

    def test_plus_odpre_dodajanje_naprave(self):
        # Krog 2: »+« odpre meni (namizje, nacini naprav, nova naprava); »Dodaj napravo« je obstojeca pot.
        self._js("document.getElementById('gumbProstori').click(), 1")
        self.pocakaj_naprave()
        self._js("document.querySelector('[data-prostor=\"4\"]').click(), 1")
        self.assertFalse(self._js("document.getElementById('prostoriMeni').hidden"))
        self.assertEqual(self._js("document.querySelector('[data-prostor=\"4\"]').getAttribute('aria-expanded')"), "true")
        self.assertEqual(self._js("document.activeElement.getAttribute('data-meni')"), "zrcaljenje:pc-1-control")
        self.assertEqual(self.dejanja, [])
        self._js("document.querySelector('#prostoriMeni [data-meni=\"dodaj\"]').click(), 1")
        self.assertTrue(_cakaj(lambda: self.dejanja == ["nova-naprava"], 10), self.dejanja)
        self.assertFalse(self.odprto())

    def test_osvezitev_ne_zaganja_controla(self):
        # Sprotna osvezitev odprtega preklopnika (vsakih 5 s) Controla ne zazene; zapomnjene naprave ostanejo.
        pred = len(self.klici)
        with mock.patch.object(so, "_control_na_vodilu", return_value=False):
            izid = self.os._prostori(False)
        self.assertEqual(izid["koda"], "ni_controla")
        self.assertEqual(self.klici[pred:], [])
        self.assertEqual([p["id"] for p in izid["prostori"]], ["tv-9-os"])
        self.assertTrue(self.os._prostori(True)["ok"])
        self.assertIn(("Seznam",), self.klici[pred:])

    def test_stran_ne_odpre_tujega(self):
        # Most: id izven ozjega kroga ali neznan id ne gre do Controla.
        self.assertEqual(self.os._prostor_odpri("tuj"), {"ok": False, "koda": "ni_prostora"})
        self.assertEqual(self.os._prostor_odpri("jaz-control")["koda"], "ni_prostora")
        self.assertFalse([k for k in self.klici if k[0] in ("Upravljaj", "OdpriTukaj", "ProstorOdpri")])
        # Lazen sorodnik izven ozjega kroga (z namizjem) ob pravem v krogu: ukaz gre samo pravemu (pregled 25. 10. 2026).
        self.naprave += [{"id": "lz", "ime": "Lazni", "zmoznosti": ["zaslon.deli"], "platforma": "tablet", "ozji": True},
                         {"id": "lz-control", "ime": "Lazni", "zmoznosti": ["desktop", "apps"], "platforma": "linux",
                          "vrsta": "control", "ozji": False}]
        for id_ in ("lz-control", "lz"):
            self.assertTrue(self.os._prostor_odpri(id_)["ok"])
        self.assertEqual([k for k in self.klici if k[0] in ("Upravljaj", "OdpriTukaj", "ProstorOdpri")],
                         [("ProstorOdpri", "lz", "safeer.cel.zaslon", "1")] * 2)

    def test_ime_z_oznakami_je_besedilo(self):
        self.naprave[1] = dict(self.naprave[1], ime=ZLO)
        self._js("document.getElementById('gumbProstori').click(), 1")
        self.pocakaj_naprave()
        self.assertTrue(self.ploscice()[2].startswith(ZLO + ", "), self.ploscice()[2])
        self.assertEqual(self._js("document.querySelector('[data-prostor=\"2\"] b').textContent"), ZLO)
        self.assertIn(ZLO, self._js("document.querySelector('.prostor-aplikacija').title"))
        self._js("document.querySelector('[data-prostor=\"2\"]').click(), 1")
        self.assertTrue(_cakaj(lambda: ("ProstorOdpri", "pc-1-control", "", "1") in self.klici, 10), self.klici)
        self.assertTrue(_cakaj(lambda: ZLO in (self._js("document.getElementById('obvestilo').textContent") or ""), 5))
        _cakaj(lambda: False, 0.3)
        self.assertEqual(self._js("document.querySelectorAll('#slojProstori img, #obvestilo img').length"), 0)
        self.assertIsNone(self._js("window.__xss"))

    def test_klik_na_ozadje_zapre_in_vrne_fokus(self):
        # Pregled 25. 10. 2026: splosni poslusalec .tancica je sloj skril mimo zapriProstore - aria-expanded je ostal
        # "true", fokus je padel na body.
        g = "document.getElementById('gumbProstori')"
        self._js(g + ".focus(), " + g + ".click(), 1")
        self.pocakaj_naprave()
        self.tipka("ArrowRight")
        self.assertEqual(self.fokus(), "1")
        self._js("document.querySelector('#slojProstori .tancica').click(), 1")
        self.assertFalse(self.odprto())
        self.assertEqual(self._js(g + ".getAttribute('aria-expanded')"), "false")
        self.assertEqual(self._js("document.activeElement.id"), "gumbProstori")

    def test_tab_ostane_v_preklopniku(self):
        self._js("document.getElementById('gumbProstori').click(), 1")
        self.pocakaj_naprave()
        self._js("document.querySelector('[data-prostor=\"2\"]').focus(), 1")
        kje = ("(function (a) { return document.getElementById('slojProstori').contains(a) ? "
               "(a.id || a.getAttribute('data-prostor') || a.className) : 'zunaj:' + a.tagName; })(document.activeElement)")
        pot = []
        for _ in range(4):
            self.tipka("Tab")
            pot.append(self._js(kje))
        # Krog 2: za trakom je se stikalo »zgornji rob« (meni »+« je skrit in ga Tab preskoci).
        self.assertEqual(pot, ["gumb majhen prostor-aplikacija", "prostoriRob", "prostoriZapri", "2"])
        self.tipka("Tab", shiftKey=True)
        self.tipka("Tab", shiftKey=True)
        self.assertEqual(self._js(kje), "prostoriRob")
        self.assertTrue(self.odprto())

    def test_osvezitev_brez_spremembe_ne_pise(self):
        # Pregled 25. 10. 2026: vsaka osvezitev (5 s) je zapisala os.json, ker se je `videna` vedno spremenil.
        self._js("document.getElementById('gumbProstori').click(), 1")
        self.pocakaj_naprave()
        pred, zapis = self.os.shramba.zapisi, json.dumps(self.os.shramba["prostori"])
        for _ in range(3):
            self.assertTrue(self.os._prostori(True)["ok"])
        self.assertEqual(self.os.shramba.zapisi, pred)
        self.assertEqual(json.dumps(self.os.shramba["prostori"]), zapis)
        # Nova naprava je sprememba in se zapise.
        self.naprave.append({"id": "f-1", "ime": "Telefon", "zmoznosti": ["zaslon.deli"], "platforma": "phone", "ozji": True})
        self.os._prostori(True)
        self.assertEqual(self.os.shramba.zapisi, pred + 1)

    def test_ena_aplikacija_pred_nalaganjem_naprav(self):
        # Pregled 25. 10. 2026: seznam naprav s programi se ni bil nalozen, gumb je tiho odprl samo Programe.
        besedilo = self._js("BESEDILA_OS[%s].prostorAplikacijeNi" % json.dumps(self.JEZIK)).replace("{ime}", "Pisarna")
        gumb = "document.querySelector('[data-prostor=\"2\"]').parentNode.querySelector('.prostor-aplikacija')"
        self.programi_naprav = []
        self._js("document.getElementById('gumbProstori').click(), 1")
        self.pocakaj_naprave()
        self._js(gumb + ".click(), 1")
        self.assertFalse(self.odprto())
        self.assertTrue(_cakaj(lambda: self._js("document.getElementById('obvestilo').textContent") == besedilo, 10),
                        self._js("document.getElementById('obvestilo').textContent"))
        self.assertTrue(self._js("document.getElementById('r-programi').classList.contains('viden')"))
        # Ko naprave pridejo: izbere napravo (prej: brez izbire, ker se seznam se ni nalozil).
        self.programi_naprav = None
        self._js("document.getElementById('gumbProstori').click(), 1")
        self.pocakaj_naprave()
        self._js(gumb + ".click(), 1")
        self.assertTrue(_cakaj(lambda: "Pisarna" in (self._js(
            "(document.querySelector('#filtriNaprav button.izbran') || {}).textContent") or ""), 10))


class ProstoriKrog2(Prostori):
    """Krog 2: lokalna namizja v istem preklopniku, slicice racunalnikov v zivo samo med odprtim preklopnikom, meni »+«
    z nacini, Super+Alt+puscica do sosednjega prostora (tudi iz gledalca), zgornji rob, starejsi Control."""

    def setUp(self):
        super().setUp()
        self.namizja.seznam_ = [dict(n) for n in NAMIZJA]

    def pocakaj_naprave(self):
        self.assertTrue(_cakaj(lambda: len(self.ploscice() or []) == 7, 10), self.ploscice())

    def test_gumb_odpre_ploscice_v_stalnem_redu(self):
        self._js("document.getElementById('gumbProstori').click(), 1")
        self.pocakaj_naprave()
        p = self.ploscice()
        self.assertEqual(p[:3], ["Namizje 1, Tukaj si", "Namizje 2, Okna: 2", "Namizje 3, Prazno"])
        self.assertEqual(p[3].split(",")[0], "Kuhinja")
        self.assertEqual(p[6], "Dodaj, Namizje, napravo ali način")
        # Shema oken: pravokotniki na svojem mestu, naslov okna je samo besedilo (title).
        self.assertEqual(self._js("document.querySelectorAll('[data-prostor=\"1\"] .prostor-okno').length"), 2)
        self.assertEqual(self._js("document.querySelector('[data-prostor=\"1\"] .prostor-okno').style.left"), "20%")
        self.assertEqual(self._js("document.querySelectorAll('[data-prostor=\"1\"] .prostor-okno')[1].title"), ZLO_OKNO)
        self.assertIsNone(self._js("window.__xss"))
        self.assertEqual(self._js("document.querySelector('#prostoriTrak .prostor.ta').getAttribute('data-prostor')"), "0")
        self.assertEqual(self._js("document.querySelectorAll('#prostoriTrak .prostor.brez').length"), 1, "samo Kuhinja")

    def test_super_tab_iz_gtk(self):
        self.assertTrue(self.os._na_tipko(self.okno, so._Tipka(Gdk.KEY_Tab, Gdk.ModifierType.SUPER_MASK, 0)))
        self.assertTrue(_cakaj(lambda: self.odprto() is True, 5))
        self.pocakaj_naprave()
        self.assertTrue(_cakaj(lambda: self.fokus() == "1", 5), self.fokus())
        self.tipka("Enter")
        self._js("document.activeElement.click(), 1")
        self.assertTrue(_cakaj(lambda: ("preklopi", 1) in self.namizja.klici, 5), self.namizja.klici)
        self.assertFalse(self.odprto())

    def test_enter_odpre_racunalnik(self):
        self._js("document.getElementById('gumbProstori').click(), 1")
        self.pocakaj_naprave()
        self._js("document.querySelector('[data-prostor=\"4\"]').click(), 1")
        self.assertTrue(_cakaj(lambda: ("ProstorOdpri", "pc-1-control", "", "1") in self.klici, 10), self.klici)

    def test_android_cel_zaslon_s_potrditvijo(self):
        pass

    def test_napaka_ostane_v_preklopniku(self):
        pass

    def test_brez_povezave_ne_klice(self):
        pass

    def test_ime_z_oznakami_je_besedilo(self):
        pass

    def test_klik_na_ozadje_zapre_in_vrne_fokus(self):
        pass

    def test_tab_ostane_v_preklopniku(self):
        pass

    def test_ena_aplikacija_pred_nalaganjem_naprav(self):
        pass

    def test_plus_odpre_dodajanje_naprave(self):
        # Meni: novo namizje, nacini za vsako povezano napravo (namizni samo, ce ga naprava sporoca), nova naprava.
        self.naprave[2] = dict(self.naprave[2], zmoznosti=["zaslon.deli", "remote", so.link_prostori.ZMOZNOST_NAMIZNI])
        self._js("document.getElementById('gumbProstori').click(), 1")
        self.pocakaj_naprave()
        self._js("document.querySelector('[data-prostor=\"6\"]').click(), 1")
        meni = self._js("Array.prototype.map.call(document.querySelectorAll('#prostoriMeni button'), "
                        "function (b) { return b.getAttribute('data-meni') + '=' + b.textContent; })")
        self.assertEqual(meni, ["namizje=Novo namizje", "zrcaljenje:pc-1-control=Zrcaljenje",
                                "aplikacija:pc-1-control=Samo ena aplikacija", "zrcaljenje:t-1-os=Zrcaljenje",
                                "aplikacija:t-1-os=Samo ena aplikacija", "namizni:t-1-os=Namizni način", "dodaj=Dodaj napravo"])
        # Puscice se premikajo po meniju, Esc zapre meni (ne preklopnika) in vrne fokus na »+«.
        self.assertEqual(self._js("document.activeElement.getAttribute('data-meni')"), "namizje")
        self.tipka("ArrowDown")
        self.assertEqual(self._js("document.activeElement.getAttribute('data-meni')"), "zrcaljenje:pc-1-control")
        self.tipka("Escape")
        self.assertTrue(self._js("document.getElementById('prostoriMeni').hidden"))
        self.assertTrue(self.odprto())
        self.assertEqual(self.fokus(), "6")
        self._js("document.activeElement.click(), 1")
        self._js("document.querySelector('#prostoriMeni [data-meni=\"namizni:t-1-os\"]').click(), 1")
        self.assertTrue(_cakaj(lambda: ("ProstorOdpri", "t-1-os", so.link_prostori.PROGRAM_NAMIZNI, "1") in self.klici, 10),
                        self.klici)
        self._js("document.getElementById('gumbProstori').click(), 1")
        self.pocakaj_naprave()
        self._js("document.querySelector('[data-prostor=\"6\"]').click(), 1")
        self._js("document.querySelector('#prostoriMeni [data-meni=\"namizje\"]').click(), 1")
        self.assertTrue(_cakaj(lambda: ("dodaj",) in self.namizja.klici, 5), self.namizja.klici)
        self.assertTrue(_cakaj(lambda: self._js("document.getElementById('obvestilo').textContent") == "Namizje 4", 5))

    def test_nacin_preveri_python(self):
        # Stran ne more izbrati nacina, ki ga naprava ne zna, ali poljubnega programa.
        pred = len(self.klici)
        self.assertEqual(self.os._prostor_odpri("pc-1-control", "namizni")["koda"], "ni_nacina")
        self.assertEqual(self.os._prostor_odpri("t-1-os", "namizni")["koda"], "ni_nacina")
        self.assertEqual(self.os._prostor_odpri("t-1-os", "safeer.cel.zaslon")["koda"], "napacna_zahteva")
        self.assertEqual(self.os._prostor_odpri("t-1-os", "razsirjen")["koda"], "napacna_zahteva")
        self.assertFalse([k for k in self.klici[pred:] if k[0] != "Seznam"], self.klici[pred:])

    def test_starejsi_control_odpre_v_oknu(self):
        self.odgovori["ProstorOdpri"] = {"ok": False, "koda": "stari_control"}
        self.assertTrue(self.os._prostor_odpri("pc-1-control")["ok"])
        self.assertTrue(self.os._prostor_odpri("t-1-os")["ok"])
        self.assertIn(("Upravljaj", "pc-1-control"), self.klici)
        self.assertIn(("OdpriTukaj", "t-1-os", "safeer.cel.zaslon"), self.klici)

    def test_slicice_v_zivo_samo_med_odprtim(self):
        slika = so.link_prostori.PREDPONA_SLICICE + "/9j/4AAQSkZJRg=="
        self.odgovori["Ukaz"] = {"ok": True, "data": {"image": slika, "width": 320, "height": 180}}
        self._js("document.getElementById('gumbProstori').click(), 1")
        self.pocakaj_naprave()
        img = "document.querySelector('[data-prostor=\"4\"] img.prostor-zivo')"
        self.assertTrue(_cakaj(lambda: self._js(img + " && " + img + ".src") == slika, 10), self.klici)
        # Naprava Android (Tablica) in naprava brez povezave nimata slike; Ukaz je sel samo racunalniku.
        self.assertEqual(self._js("document.querySelectorAll('#prostoriTrak img.prostor-zivo').length"), 1)
        ukazi = [k for k in self.klici if k[0] == "Ukaz"]
        self.assertTrue(ukazi)
        self.assertEqual({k[1:3] for k in ukazi}, {("pc-1-control", "screen.thumb")})
        # Most zavrne napravo, ki ni racunalnik v krogu.
        for id_ in ("t-1-os", "tuj", "jaz-control", ""):
            self.assertEqual(self.os._prostor_slicica(id_), {"ok": False, "koda": "ni_prostora"}, id_)
        # Zaprt preklopnik ne sprasuje nikogar vec.
        self.tipka("Escape")
        self.assertFalse(self.odprto())
        _cakaj(lambda: False, 0.5)
        n = len([k for k in self.klici if k[0] == "Ukaz"])
        _cakaj(lambda: False, 3.6)
        self.assertEqual(len([k for k in self.klici if k[0] == "Ukaz"]), n)

    def test_sosednji_prostor(self):
        # Super+Alt+desno iz okna Safeer OS: z namizja 1 na namizje 2 (brez preklopnika).
        alt = Gdk.ModifierType.SUPER_MASK | Gdk.ModifierType.ALT_MASK
        self.assertTrue(self.os._na_tipko(self.okno, so._Tipka(Gdk.KEY_Right, alt, 0)))
        self.assertTrue(_cakaj(lambda: ("preklopi", 1) in self.namizja.klici, 10), self.namizja.klici)
        self.assertFalse(self.odprto())
        # Iz gledalca Pisarne (Super+Alt+desno): naslednji je Tablica; levo: Kuhinja nima povezave -> Namizje 3.
        self.os._iz_gledalca({"sosednji": 1, "od": "pc-1-control"})
        self.assertTrue(_cakaj(lambda: ("ProstorOdpri", "t-1-os", "safeer.cel.zaslon", "1") in self.klici, 10), self.klici)
        self.os._iz_gledalca({"sosednji": -1, "od": "pc-1"})
        self.assertTrue(_cakaj(lambda: ("preklopi", 2) in self.namizja.klici, 10), self.namizja.klici)
        # Iz gledalca Super+Tab: odpre preklopnik.
        self.os._iz_gledalca({"smer": 1, "od": "t-1-os"})
        self.assertTrue(_cakaj(lambda: self.odprto() is True, 5))
        # Shift+Super+Alt in Super brez Alt/Ctrl nista bliznjici (Super+puscica je zlaganje oken Cinnamona).
        self.assertFalse(self.os._na_tipko(self.okno, so._Tipka(Gdk.KEY_Right, Gdk.ModifierType.SUPER_MASK, 0)))
        self.assertFalse(self.os._na_tipko(self.okno, so._Tipka(Gdk.KEY_Left, alt | Gdk.ModifierType.SHIFT_MASK, 0)))

    def test_zgornji_rob(self):
        self.assertFalse(self.os._prostori_rob(None)["rob"])
        self._js("document.dispatchEvent(new MouseEvent('mousemove', {clientX: 300, clientY: 0})), 1")
        _cakaj(lambda: False, 0.7)
        self.assertFalse(self.odprto(), "privzeto izklopljeno")
        self._js("document.getElementById('gumbProstori').click(), 1")
        self.pocakaj_naprave()
        self._js("(function (c) { c.checked = true; c.dispatchEvent(new Event('change')); })(document.getElementById('prostoriRob')), 1")
        self.assertTrue(_cakaj(lambda: self.os.shramba.get("prostori_rob") is True, 5))
        self.tipka("Escape")
        self._js("document.dispatchEvent(new MouseEvent('mousemove', {clientX: 300, clientY: 0})), 1")
        self.assertTrue(_cakaj(lambda: self.odprto() is True, 3))
        self.assertEqual(self.os._prostori_rob("da"), {"ok": True, "rob": True}, "samo bool spremeni nastavitev")


class ProstoriAngleski(Prostori):
    JEZIK = "en"
    NI_NASLOVA = "directly"

    def test_gumb_odpre_ploscice_v_stalnem_redu(self):
        self._js("document.getElementById('gumbProstori').click(), 1")
        self.pocakaj_naprave()
        self.assertEqual(self._js("document.getElementById('prostoriNaslov').textContent"), "Spaces")
        self.assertEqual(self.ploscice()[2], "Pisarna, computer, Connected")

    def test_android_cel_zaslon_s_potrditvijo(self):
        pass

    def test_brez_povezave_ne_klice(self):
        pass


if __name__ == "__main__":
    unittest.main()
