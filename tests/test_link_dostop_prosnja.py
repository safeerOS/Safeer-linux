"""Prosnja za dostop, ki jo odobri uporabnik NA tem racunalniku (core/link_dostop).

Lastnik, 14. 10. 2026: naprava iz Safeer Linka (npr. telefon druzinskega clana) dostop do racunalnika lahko prosi, dobi
pa ga samo, ce ga uporabnik odobri tukaj - zascita pred napadalcem. Preverjeno: prosnja nastane samo za clana kroga in
samo za eno manjkajoco zmoznost, ime je iz kroga (ne iz sporocila), omejitve pogostosti, 24-urna zavrnitev prezivi
ponovni zagon, Dovoli doda samo eno crko, stara oblika zavrnitve ostane (dodani sta le novi polji) in polje
»zavrnjeno« v dostop.json je varno pri hkratnem pisanju vec programov.
"""
import json
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

import pytest

from core import link_dostop

pytestmark = pytest.mark.pravi_dostop

JAZ = "n-cccccccccccccccc"
A = "n-aaaaaaaaaaaaaaaa"        # telefon druzinskega clana (v krogu)
B = "n-bbbbbbbbbbbbbbbb"        # naprava, ki je krog ne pozna
DRUGI = ["n-%016x" % (0x1000 + i) for i in range(7)]
KLJUCI = {"KJAZ": JAZ, "KA": A, "KB": B}
KLJUCI.update({"K%d" % i: j for i, j in enumerate(DRUGI)})
ZDAJ = float(int(__import__("time").time()))  # zdaj: odprte prosnje se pocistijo po pravi uri


class _Krog:
    def __init__(self, clani=()):
        import threading
        self._zaklep = threading.RLock()
        self.clani = {c["id"]: c for c in clani}

    def _veljaven(self, c):
        return True

    def clan_za_id(self, device_id):
        return self.clani.get(device_id)


CLANI = ({"id": A + "-os", "kljuc": "KA", "ime": "Safeer OS na telefonu", "dodano": 2_000_000_000.0},
         {"id": A, "kljuc": "KA", "ime": "Druzinski\u2028 telefon  \u202e", "dodano": 2_000_000_000.0},
         {"id": JAZ, "kljuc": "KJAZ", "ime": "Ta racunalnik", "dodano": 2_000_000_000.0}) + tuple(
    {"id": j, "kljuc": "K%d" % i, "ime": "Naprava %d" % i, "dodano": 2_000_000_000.0} for i, j in enumerate(DRUGI))


_ZASCITENO = object()


def _vprasaj(naprava, zahteva, zascita=_ZASCITENO, **k):
    """Zavrnitev ZASCITENEGA sporocila (privzeto: jedro iz preverjenega kljuca je jedro naprave)."""
    if zascita is _ZASCITENO:
        zascita = naprava[:link_dostop.DOLZINA_JEDRA] if link_dostop.je_id_iz_kljuca(naprava) else None
    return link_dostop.prosnja_ob_zavrnitvi(naprava, zahteva, zascita=zascita, **k)


class _Osnova(unittest.TestCase):
    clani = CLANI

    def setUp(self):
        self._mapa = tempfile.TemporaryDirectory()
        self.addCleanup(self._mapa.cleanup)
        link_dostop._za_preizkus(os.path.join(self._mapa.name, "dostop.json"))
        self.addCleanup(lambda: link_dostop._za_preizkus(None))
        for ime, vrednost in (("_lastni_kljuc", lambda: "KJAZ"), ("_id_iz_kljuca", lambda k: KLJUCI[k]),
                              ("_krog", lambda: _Krog(self.clani))):
            p = mock.patch.object(link_dostop, ime, vrednost)
            p.start()
            self.addCleanup(p.stop)
        self.pokazano, self.umaknjeno = [], []
        self._javi_prikaz()

    def _javi_prikaz(self):
        link_dostop.nastavi_prikaz(self.pokazano.append, self.umaknjeno.append)

    def _zapis(self):
        with open(link_dostop._pot(), encoding="utf-8") as d:
            return json.load(d)


class NastanekProsnje(_Osnova):
    def test_clan_kroga_brez_zmoznosti_sprozi_obvestilo(self):
        izid = _vprasaj(A + "-os", link_dostop.zahteva_dejanja("files.list"), zdaj=ZDAJ)
        self.assertEqual(izid, ("pending", "d"))
        self.assertEqual(len(self.pokazano), 1)
        p = self.pokazano[0]
        self.assertEqual((p["jedro"], p["zmoznost"], p["cas"]), (A, "d", ZDAJ))
        self.assertEqual(link_dostop.odprte_prosnje()[0]["jedro"], A)
        self.assertEqual(link_dostop.zmoznosti(A), set())               # prosnja sama ne odpre nicesar

    def test_ime_iz_kroga_precisceno_in_omejeno(self):
        _vprasaj(A, "p", zdaj=ZDAJ)
        self.assertEqual(self.pokazano[0]["ime"], "Druzinski telefon")       # vnos naprave same, brez nadzornih znakov
        self.assertEqual(link_dostop.cisto_ime("x" * 200 + "\n"), "x" * 60)
        self.assertEqual(link_dostop.cisto_ime("a\nb\tc\u202ed"), "a b c d")

    def test_neznana_naprava_ne_sprozi_obvestila(self):
        self.assertEqual(_vprasaj(B, "d", zdaj=ZDAJ), ("none", "d"))
        self.assertEqual(_vprasaj("stara-oznaka", "d", zdaj=ZDAJ), ("none", "d"))
        self.assertEqual(_vprasaj("", "d", zdaj=ZDAJ), ("none", "d"))
        self.assertEqual(self.pokazano, [])

    def test_dejanje_ki_zahteva_vse_ali_nic_ne_sprozi_obvestila(self):
        for dejanje in ("novo.dejanje", "", "sync.data"):
            zahteva = link_dostop.zahteva_dejanja(dejanje)
            self.assertEqual(_vprasaj(A, zahteva, zdaj=ZDAJ), ("none", zahteva))
        self.assertEqual(_vprasaj(A, "", zdaj=ZDAJ), ("none", ""))
        self.assertEqual(_vprasaj(A, "x", zdaj=ZDAJ), ("none", "x"))
        self.assertEqual(self.pokazano, [])

    def test_ta_racunalnik_in_naprava_z_zmoznostjo_ne_sprozita_obvestila(self):
        self.assertEqual(_vprasaj(JAZ + "-control", "d", zascita=JAZ, zdaj=ZDAJ)[0], "none")
        link_dostop.nastavi(A, "d")
        self.assertEqual(_vprasaj(A, "d", zdaj=ZDAJ)[0], "none")
        self.assertEqual(self.pokazano, [])

    def test_brez_programa_z_obvestili_ni_prosnje(self):
        link_dostop.nastavi_prikaz(None)
        self.assertEqual(_vprasaj(A, "d", zdaj=ZDAJ), ("none", "d"))
        self.assertEqual(link_dostop.odprte_prosnje(), [])

    def test_samo_zasciteno_sporocilo_sprozi_obvestilo(self):
        """Oznako posiljatelja nezascitenega sporocila vpise sredisce: ponaredek bi uporabniku pokazal »druzinski clan
        prosi za dostop«. Zato nezasciteno - tudi od naprave, ki zascite se nikoli ni uporabila - dobi "none"."""
        self.assertFalse(link_dostop.zna_zascito(A))
        for naprava in (A, A + "-os"):
            self.assertEqual(link_dostop.prosnja_ob_zavrnitvi(naprava, "d", zdaj=ZDAJ), ("none", "d"))
            self.assertEqual(link_dostop.prosnja_ob_zavrnitvi(naprava, "d", zascita=None, zdaj=ZDAJ), ("none", "d"))
            self.assertEqual(link_dostop.prosnja_ob_zavrnitvi(naprava, "d", zascita="", zdaj=ZDAJ), ("none", "d"))
        link_dostop.zabelezi_zascito(A)
        self.assertEqual(link_dostop.prosnja_ob_zavrnitvi(A + "-os", "d", zdaj=ZDAJ), ("none", "d"))
        self.assertEqual(self.pokazano, [])
        # Zasciteno: velja preverjen kljuc, ne oznaka.
        self.assertEqual(_vprasaj(B, "d", zascita=A, zdaj=ZDAJ), ("pending", "d"))
        self.assertEqual(self.pokazano[0]["jedro"], A)
        self.assertEqual(_vprasaj(A, "p", zascita="karkoli", zdaj=ZDAJ), ("none", "p"))     # ni jedro

    def test_napaka_prikaza_ni_prosnja(self):
        link_dostop.nastavi_prikaz(mock.Mock(side_effect=RuntimeError("ni obvestil")))
        self.assertEqual(_vprasaj(A, "d", zdaj=ZDAJ), ("none", "d"))
        self.assertEqual(link_dostop.odprte_prosnje(), [])


class Omejitve(_Osnova):
    def test_ista_prosnja_najvec_enkrat_na_deset_minut(self):
        self.assertEqual(_vprasaj(A, "d", zdaj=ZDAJ)[0], "pending")
        for zamik in (1, 60, 599):
            self.assertEqual(_vprasaj(A, "d", zdaj=ZDAJ + zamik)[0], "pending")
        self.assertEqual(len(self.pokazano), 1)
        self.assertEqual(_vprasaj(A, "p", zdaj=ZDAJ + 5)[0], "pending")   # druga zmoznost
        self.assertEqual(len(self.pokazano), 2)
        self.assertEqual(_vprasaj(A, "d", zdaj=ZDAJ + 601)[0], "pending")
        self.assertEqual(len(self.pokazano), 3)                         # po desetih minutah se enkrat

    def test_vse_odprte_prosnje_ostanejo(self):
        """Lastnik, 18. 10. 2026: prej najvec 5 odprtih (najstarejse so izpadle, preden jih je uporabnik videl). Zdaj
        ostanejo vse - prosnjo sprozi samo clan kroga, najvec eno na crko - in izpadejo po 24 urah."""
        for i, j in enumerate(DRUGI[:6]):
            self.assertEqual(_vprasaj(j, "d", zdaj=ZDAJ + i)[0], "pending")
        odprte = [p["jedro"] for p in link_dostop.odprte_prosnje()]
        self.assertEqual(odprte, DRUGI[:6])
        self.assertEqual(self.umaknjeno, [])
        self.assertEqual(_vprasaj(DRUGI[0], "d", zdaj=ZDAJ + 10)[0], "pending")
        # Dostop se se vedno podeli samo s klikom uporabnika na tem racunalniku.
        self.assertEqual(link_dostop.zmoznosti(DRUGI[0]), set())
        self.assertTrue(link_dostop.odobri_prosnjo(DRUGI[0], "d"))
        self.assertEqual(link_dostop.zmoznosti(DRUGI[0]), {"d"})
        # Po 24 urah neodgovorjena prosnja izpade.
        self.assertEqual(_vprasaj(DRUGI[1], "p", zdaj=ZDAJ + link_dostop.ZAVRNITEV_VELJA_S + 10)[0], "pending")
        self.assertNotIn(DRUGI[2], [p["jedro"] for p in link_dostop.odprte_prosnje()])


class Zavrnitev(_Osnova):
    def test_zavrni_utisa_za_24_ur_in_prezivi_ponovni_zagon(self):
        _vprasaj(A, "d", zdaj=ZDAJ)
        self.assertTrue(link_dostop.zavrni_prosnjo(A, "d", zdaj=ZDAJ + 5))
        self.assertEqual(link_dostop.odprte_prosnje(), [])
        self.assertEqual(_vprasaj(A, "d", zdaj=ZDAJ + 700), ("declined", "d"))
        self.assertEqual(self._zapis()["zavrnjeno"], {A + "|d": ZDAJ + 5})
        pot = link_dostop._pot()
        link_dostop._za_preizkus(pot)                                   # nov zagon programa
        self._javi_prikaz()
        self.assertEqual(_vprasaj(A, "d", zdaj=ZDAJ + 3600), ("declined", "d"))
        self.assertEqual(_vprasaj(A, "p", zdaj=ZDAJ + 3600)[0], "pending")  # druga crka
        self.assertEqual(len(self.pokazano), 2)
        self.assertEqual(_vprasaj(A, "d", zdaj=ZDAJ + 5 + 86400)[0], "pending")

    def test_zavrnitev_v_pomnilniku_velja_tudi_ce_jo_starejsi_program_izbrise(self):
        link_dostop.zavrni_prosnjo(A, "d", zdaj=ZDAJ)
        pot = link_dostop._pot()
        with open(pot, "w", encoding="utf-8") as d:                     # starejsi program polja ne pozna
            json.dump({"v": 1, "podedovano_ob": 1.0, "naprave": {}}, d)
        os.utime(pot, (1, 1))
        self.assertEqual(_vprasaj(A, "d", zdaj=ZDAJ + 60)[0], "declined")

    def test_napacne_oblike_ne_zapisemo(self):
        for jedro, crka in (("karkoli", "d"), (A + "-os", "d"), (A, "*"), (A, "dd"), (A, "d*"), (A, "dpvzd"), ("", "")):
            self.assertFalse(link_dostop.zavrni_prosnjo(jedro, crka, zdaj=ZDAJ))
        self.assertFalse(os.path.exists(link_dostop._pot()) and "zavrnjeno" in self._zapis())

    def test_pokvarjeni_vnosi_zavrnjeno_se_prezrejo(self):
        pot = link_dostop._pot()
        with open(pot, "w", encoding="utf-8") as d:
            json.dump({"v": 1, "podedovano_ob": 1.0, "naprave": {},
                       "zavrnjeno": {A + "|d": "jutri", "x|d": ZDAJ, A + "|q": ZDAJ, A + "|p": True}}, d)
        self.assertEqual(_vprasaj(A, "d", zdaj=ZDAJ)[0], "pending")
        self.assertEqual(_vprasaj(A, "p", zdaj=ZDAJ)[0], "pending")


class Dovoli(_Osnova):
    def test_dovoli_doda_samo_zaprosen_crko(self):
        link_dostop.nastavi(A, "v")
        _vprasaj(A + "-os", "d", zdaj=ZDAJ)
        self.assertTrue(link_dostop.odobri_prosnjo(A, "d"))
        self.assertEqual(link_dostop.zmoznosti(A), {"v", "d"})
        self.assertEqual(self._zapis()["naprave"], {A: "dv"})
        self.assertEqual(link_dostop.odprte_prosnje(), [])
        self.assertFalse(link_dostop.odobri_prosnjo(A, "d"))            # enkrat; ni vec odprta

    def test_brez_odprte_prosnje_ni_odobritve(self):
        self.assertFalse(link_dostop.odobri_prosnjo(A, "d"))
        self.assertFalse(link_dostop.odobri_prosnjo(A, "*"))
        self.assertFalse(link_dostop.odobri_prosnjo("karkoli", "d"))
        _vprasaj(A, "d", zdaj=ZDAJ)
        self.assertFalse(link_dostop.odobri_prosnjo(A, "p"))            # druga zmoznost ni bila zaprosena
        self.assertEqual(link_dostop.zmoznosti(A), set())

    def test_dovoli_po_zavrnitvi_izbrise_zavrnitev(self):
        link_dostop.zavrni_prosnjo(A, "p", zdaj=ZDAJ - 90000)          # stara, potekla
        _vprasaj(A, "p")
        self.assertTrue(link_dostop.odobri_prosnjo(A, "p"))
        self.assertNotIn(A + "|p", self._zapis().get("zavrnjeno", {}))

    def test_dovoli_ki_ga_ni_mogoce_zapisati_pusti_prosnjo_odprto(self):
        _vprasaj(A, "d", zdaj=ZDAJ)
        with mock.patch.object(link_dostop, "_na_disk", side_effect=OSError(28, "No space left on device")):
            self.assertFalse(link_dostop.odobri_prosnjo(A, "d"))
        self.assertEqual(len(link_dostop.odprte_prosnje()), 1)
        self.assertTrue(link_dostop.odobri_prosnjo(A, "d"))


class OblikaOdgovora(unittest.TestCase):
    def test_stara_polja_ostanejo_novi_sta_dodani(self):
        for dejanje in ("files.list", "files.search", "apps.list", "apps.running", "play.state", "screen.start"):
            stara = link_dostop.zavrnitev(dejanje)
            nova = link_dostop.z_prosnjo(stara, "pending", "d")
            self.assertEqual({k: v for k, v in nova.items() if k not in ("access_request", "capability", "data")},
                             {k: v for k, v in stara.items() if k != "data"}, dejanje)
            self.assertEqual((nova["access_request"], nova["capability"]), ("pending", "d"))
            if "data" in stara:
                self.assertEqual({k: v for k, v in nova["data"].items() if k not in ("access_request", "capability")},
                                 stara["data"])
                self.assertEqual((nova["data"]["access_request"], nova["data"]["capability"]), ("pending", "d"))
            self.assertNotIn("access_request", link_dostop.zavrnitev(dejanje))     # izvirnik ostane nespremenjen
        f = link_dostop.z_prosnjo(link_dostop.zavrnitev("files.list"), "none", "d")
        self.assertEqual((f["ok"], f["data"]["shared"], f["data"]["reason"], f["data"]["items"]), (True, False, "access", []))


def _safeer_link_brez_gtk():
    """core.safeer_link brez GTK3 (v tem okolju ga ni): gi zamenjamo le za cas uvoza. Kjer GTK3 je, pravi modul."""
    try:
        from core import safeer_link
        return safeer_link
    except (ImportError, ValueError):
        pass
    import core
    shranjeno = {k: sys.modules.get(k) for k in ("gi", "gi.repository")}
    gi = types.ModuleType("gi")
    gi.require_version = lambda *a, **k: None
    gi.get_required_version = lambda *a, **k: None      # core/safeer_link izbere GTK3/GTK4 po njej (brez izbire GTK4)
    rep = types.ModuleType("gi.repository")
    for ime in ("Gdk", "Gtk", "WebKit2", "WebKit", "GLib", "Gio"):
        setattr(rep, ime, mock.MagicMock(name=ime))
    rep.Gtk.get_major_version.return_value = 4
    gi.repository = rep
    sys.modules["gi"], sys.modules["gi.repository"] = gi, rep
    modul = None
    try:
        sys.modules.pop("core.safeer_link", None)
        import importlib
        modul = importlib.import_module("core.safeer_link")
    finally:
        for k, v in shranjeno.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
        sys.modules.pop("core.safeer_link", None)       # drugi preizkusi ne dobijo modula z nadomestnim gi
        if modul is not None and getattr(core, "safeer_link", None) is modul:
            delattr(core, "safeer_link")
    return modul


class RacunalnikVprasa(_Osnova):
    """Sprejem na racunalniku (core/safeer_link): zavrnitev ostane, kot je bila; uporabnik dobi prosnjo."""

    def setUp(self):
        super().setUp()
        self.safeer_link = _safeer_link_brez_gtk()
        self.link = self.safeer_link.SafeerLink.__new__(self.safeer_link.SafeerLink)
        self.odzivi = []
        self.link._odziv = lambda vrsta, podatki: self.odzivi.append((vrsta, podatki))
        self.poslano = []
        self.link.povezava = mock.Mock()
        self.link.povezava.poslji = lambda s: self.poslano.append(s) or True
        self.link.control = True
        self.link.gledani_zaslon = ""
        self.link.gledani_zaslon_id = ""
        self.link._v_ozadju = mock.Mock()
        self.link.naprave = [{"id": A + "-os", "ime": "Telefon"}]
        self.link.naprave_vse = []
        p = mock.patch.object(self.safeer_link.GLib, "idle_add")
        self.idle_add = p.start()
        self.addCleanup(p.stop)

    def _ukaz(self, od, dejanje, zasciteno=True, parametri=None, **dodatno):
        """Ukaz od naprave; privzeto zasciten (kot ga oznaci core/link_hub: _zascita = jedro preverjenega kljuca)."""
        self.poslano.clear()
        s = {"id": "u1", "type": "control.command", "sender": od,
             "payload": {"action": dejanje, "params": dict(parametri or {})}}
        if zasciteno:
            s["_zascita"] = od[:link_dostop.DOLZINA_JEDRA]
        s.update(dodatno)
        self.link._na_sporocilo_huba(s)
        return self.poslano[-1]["payload"] if self.poslano else None

    def test_seznam_datotek_stara_oblika_in_prosnja(self):
        o = self._ukaz(A + "-os", "files.list", sender_name="Ponarejeno\nime")
        self.idle_add.assert_not_called()
        self.assertEqual((o["ok"], o["message"], o["action"]), (True, "Naprava datotek ne deli", "files.list"))
        self.assertEqual(o["data"]["items"], [])
        self.assertEqual((o["data"]["shared"], o["data"]["reason"], o["data"]["folder"]), (False, "access", ""))
        self.assertEqual((o["access_request"], o["capability"]), ("pending", "d"))
        self.assertEqual((o["data"]["access_request"], o["data"]["capability"]), ("pending", "d"))
        self.assertEqual(len(self.pokazano), 1)
        self.assertEqual(self.pokazano[0]["ime"], "Druzinski telefon")       # iz kroga, ne iz sporocila

    def test_kratka_zavrnitev_ohrani_kodo(self):
        o = self._ukaz(A, "apps.launch")
        self.assertEqual((o["ok"], o["code"]), (False, "ni_dovoljeno"))
        self.assertEqual((o["access_request"], o["capability"]), ("pending", "p"))
        self.assertNotIn("data", o)

    def test_neznana_naprava_in_neznano_dejanje(self):
        o = self._ukaz(B, "files.list")
        self.assertEqual((o["access_request"], o["data"]["access_request"], o["data"]["shared"]), ("none", "none", False))
        o = self._ukaz(A, "novo.dejanje")
        self.assertEqual((o["access_request"], o["capability"], o["code"]), ("none", "*", "ni_dovoljeno"))
        self.assertEqual(self.pokazano, [])

    def test_nezasciten_ukaz_ne_vprasa(self):
        """Nezasciten ukaz (starejsa naprava brez zascite ali ponaredek z oznako druzinskega clana): stara zavrnitev,
        "none" in brez obvestila."""
        o = self._ukaz(A + "-os", "files.list", zasciteno=False)
        self.assertEqual((o["ok"], o["data"]["shared"], o["data"]["reason"]), (True, False, "access"))
        self.assertEqual((o["access_request"], o["capability"]), ("none", "d"))
        self.assertEqual((o["data"]["access_request"], o["data"]["capability"]), ("none", "d"))
        o = self._ukaz(A, "apps.launch", zasciteno=False)
        self.assertEqual((o["code"], o["access_request"], o["capability"]), ("ni_dovoljeno", "none", "p"))
        self.assertEqual(self.pokazano, [])
        self.assertEqual(link_dostop.odprte_prosnje(), [])

    def test_zahteva_v_ozadju_ne_odpre_obvestila(self):
        """Lastnik, 15. 10. 2026: telefon v ozadju predpomni seznam programov (apps.list) - uporabnik ni nic zahteval,
        zato obvestila ni. Polje obvestilo samo prepreci; dostopa nikoli ne odpre."""
        o = self._ukaz(A, "apps.list", parametri={"background": True})
        self.assertEqual((o["ok"], o["data"]["enabled"], o["data"]["reason"]), (True, False, "access"))
        self.assertEqual((o["access_request"], o["capability"]), ("none", "p"))
        self.assertEqual(self.pokazano, [])
        self.assertEqual(link_dostop.odprte_prosnje(), [])
        self.assertEqual(link_dostop.zmoznosti(A), set())
        # Samo pravi True; "true", 1 ... so navadna zahteva.
        o = self._ukaz(A, "apps.list", parametri={"background": "true"})
        self.assertEqual(o["access_request"], "pending")
        self.assertEqual(len(self.pokazano), 1)
        # Prosnja ze caka (uporabnik je odprl programe): zahteva v ozadju izve, da caka, novega obvestila ni.
        o = self._ukaz(A, "apps.list", parametri={"background": True})
        self.assertEqual(o["access_request"], "pending")
        self.assertEqual(len(self.pokazano), 1)
        link_dostop.zavrni_prosnjo(A, "p")
        self.assertEqual(self._ukaz(A, "apps.list", parametri={"background": True})["access_request"], "declined")
        self.assertEqual(link_dostop.zmoznosti(A), set())

    def test_v_ozadju_jedro(self):
        self.assertEqual(_vprasaj(A, "p", zdaj=ZDAJ, v_ozadju=True), ("none", "p"))
        self.assertEqual((self.pokazano, link_dostop.odprte_prosnje()), ([], []))
        self.assertEqual(_vprasaj(A, "p", zdaj=ZDAJ), ("pending", "p"))     # uporabnik sam: obvestilo
        self.assertEqual(len(self.pokazano), 1)

    def test_po_zavrnitvi_declined(self):
        self._ukaz(A, "files.list")
        link_dostop.zavrni_prosnjo(A, "d")
        self.assertEqual(self._ukaz(A, "files.list")["access_request"], "declined")

    def test_dovoli_iz_obvestila_osvezi_seznam_in_odpre_samo_to(self):
        self._ukaz(A, "files.list")
        self.assertTrue(self.link.odobri_prosnjo_dostopa(A, "d"))
        self.assertEqual(link_dostop.zmoznosti(A), {"d"})
        self.assertEqual(self.link.naprave[0]["dostop"], "d")
        self.assertIn("naprave", [v for v, _ in self.odzivi])
        dostop = [p for v, p in self.odzivi if v == "dostop"]
        self.assertEqual([(p["id"], p["ok"], p["dostop"]) for p in dostop], [(A, True, "d"), (A + "-os", True, "d")])
        self.idle_add.reset_mock()
        self._ukaz(A, "files.list")
        self.idle_add.assert_called_once()                              # zdaj se izvede
        self.assertEqual(self.poslano, [])
        self.assertFalse(self.link.odobri_prosnjo_dostopa(A, "p"))      # nic drugega

    def test_stran_zavrnjena_s_prosnjo(self):
        self.link._na_sporocilo_huba({"id": "c1", "type": "cast.url", "sender": A, "_zascita": A,
                                      "payload": {"url": "https://primer.si/"}})
        ack = self.poslano[-1]
        self.assertEqual((ack["type"], ack["status"], ack["access_request"], ack["capability"]),
                         ("cast.ack", "rejected", "pending", "v"))
        self.assertEqual([(p["jedro"], p["zmoznost"]) for p in self.pokazano], [(A, "v")])

    def test_nezascitena_stran_ne_vprasa(self):
        self.link._na_sporocilo_huba({"id": "c1", "type": "cast.url", "sender": A,
                                      "payload": {"url": "https://primer.si/"}})
        ack = self.poslano[-1]
        self.assertEqual((ack["status"], ack["access_request"], ack["capability"]), ("rejected", "none", "v"))
        self.assertEqual(self.pokazano, [])

    def test_zaslon_druge_naprave_ne_vprasa(self):
        """share.screen nikoli ne pride zasciten (ni v link_e2e.ZASCITENI_TIPI; sredisce zasciten share.screen zavrze),
        zato zanj prosnje ni - zaslon naprava zaprosi z zascitenim ukazom screen.start."""
        from core import link_e2e
        self.assertNotIn("share.screen", link_e2e.ZASCITENI_TIPI)
        for dodatno in ({}, {"_zascita": A}):
            sporocilo = {"type": "share.screen", "sender": A,
                         "payload": {"action": "start", "id": "z1", "path": "/x", "fp": "ab"}}
            sporocilo.update(dodatno)
            self.link._na_sporocilo_huba(sporocilo)
        self.assertEqual(self.link.gledani_zaslon, "")
        self.assertEqual(self.pokazano, [])
        o = self._ukaz(A, "screen.start")
        self.assertEqual((o["access_request"], o["capability"]), ("pending", "z"))

    def test_odgovor_druge_naprave_prenese_stanje_prosnje(self):
        f = self.safeer_link._prosnja_iz_odgovora
        self.assertEqual(f({"ok": False, "access_request": "pending", "capability": "p"}),
                         {"access_request": "pending", "capability": "p"})
        self.assertEqual(f({"ok": True, "data": {"access_request": "declined", "capability": "d"}}),
                         {"access_request": "declined", "capability": "d"})
        self.assertEqual(f({"ok": False, "access_request": "<b>karkoli</b>"}), {})
        self.assertEqual(f({"ok": False}), {})
        self.assertEqual(f({"access_request": "pending", "capability": "xx"})["capability"], "")


class Obvestilo(unittest.TestCase):
    """Namizno obvestilo in dejanji aplikacije Control (Gio nadomescen - GTK3 tu ni)."""

    def _gio(self):
        Gio, GLib = mock.MagicMock(), mock.MagicMock()
        GLib.Variant.side_effect = lambda tip, v: ("V", tip, v)
        return Gio, GLib

    def test_obvestilo_z_gumboma_in_klikom_na_seznam_naprav(self):
        Gio, GLib = self._gio()
        app = mock.Mock()
        ident = link_dostop.poslji_obvestilo(app, Gio, GLib, {"jedro": A, "ime": "Druzinski\ntelefon", "zmoznost": "d"}, "sl")
        self.assertEqual(ident, "safeer-dostop-" + A)                  # eno obvestilo na napravo
        Gio.Notification.new.assert_called_once_with("Safeer Link")
        o = Gio.Notification.new.return_value
        o.set_body.assert_called_once_with("Druzinski telefon prosi za dostop: datoteke na tem računalniku.")
        o.set_default_action.assert_called_once_with("app.dostop-naprave")
        # Varna izbira prva (pregled 18. 10. 2026), klik na obvestilo odpre seznam naprav - nikoli ne odobri.
        self.assertEqual([c.args for c in o.add_button_with_target.call_args_list],
                         [("Zavrni", "app.dostop-zavrni", ("V", "s", A + "|d")),
                          ("Dovoli", "app.dostop-dovoli", ("V", "s", A + "|d"))])
        app.send_notification.assert_called_once_with(ident, o)

    def test_anglesko_in_neznan_jezik(self):
        p = {"jedro": A, "ime": "Phone", "zmoznost": "z"}
        self.assertEqual(link_dostop.telo_obvestila(p, "en"), "Phone is asking for access: screen and control on this computer.")
        self.assertEqual(link_dostop.telo_obvestila(p, "xx"), link_dostop.telo_obvestila(p, "en"))
        for jezik, b in link_dostop.BESEDILA_OBVESTILA.items():
            self.assertEqual(set(b), set(link_dostop.BESEDILA_OBVESTILA["en"]), jezik)

    def test_dejanja_sprejmejo_samo_pravo_obliko(self):
        Gio, GLib = self._gio()
        dejanja = {}

        def nova(ime, tip):
            d = mock.Mock()
            d.connect.side_effect = lambda _sig, fn: dejanja.__setitem__(ime, fn)
            return d
        Gio.SimpleAction.new.side_effect = nova
        app = mock.Mock()
        dovoli, zavrni, odpri = mock.Mock(), mock.Mock(), mock.Mock()
        link_dostop.registriraj_dejanja(app, Gio, GLib, dovoli, zavrni, odpri)
        self.assertEqual(set(dejanja), {"dostop-dovoli", "dostop-zavrni", "dostop-naprave"})
        self.assertEqual(app.add_action.call_count, 3)
        for slab in ("", "karkoli", A + "|*", A + "-os|d", A + "|dd", A + "|dx", A + "|", None):
            dejanja["dostop-dovoli"](None, slab)
        dovoli.assert_not_called()
        dejanja["dostop-dovoli"](None, mock.Mock(get_string=lambda: A + "|p"))
        dovoli.assert_called_once_with(A, "p")
        app.withdraw_notification.assert_called_once_with("safeer-dostop-" + A)
        dejanja["dostop-zavrni"](None, A + "|d")
        zavrni.assert_called_once_with(A, "d")
        dejanja["dostop-naprave"](None, None)
        odpri.assert_called_once_with()
        dovoli.assert_called_once()                                     # klik na obvestilo nikoli ne odobri


class VecProgramovZavrnjeno(_Osnova):
    """Polje »zavrnjeno« pise isti zapis kot dovoljenja: ista pravila (zaklep, primerjava pred zamenjavo, neznana
    polja ostanejo)."""

    def test_neznana_polja_ostanejo_ob_pisanju(self):
        link_dostop.nastavi(A, "d")
        pot = link_dostop._pot()
        zapis = self._zapis()
        zapis["novo_polje"] = {"x": 1}
        with open(pot + ".drug", "w", encoding="utf-8") as d:
            json.dump(zapis, d)
        os.replace(pot + ".drug", pot)
        link_dostop.zavrni_prosnjo(A, "p", zdaj=ZDAJ)
        link_dostop.nastavi(DRUGI[0], "v")
        link_dostop.zabelezi_zascito(A)
        zapis = self._zapis()
        self.assertEqual(zapis["novo_polje"], {"x": 1})
        self.assertEqual(zapis["zavrnjeno"], {A + "|p": ZDAJ})
        self.assertEqual(zapis["naprave"], {A: "d", DRUGI[0]: "v"})

    def test_zavrnitev_ne_povozi_spremembe_drugega_programa_tik_pred_zamenjavo(self):
        link_dostop.nastavi(A, "dpvz")
        pot = link_dostop._pot()
        pravi_fsync = os.fsync
        klici = []

        def fsync(rocaj):
            pravi_fsync(rocaj)
            if not klici:
                klici.append(1)
                with open(pot, encoding="utf-8") as d:
                    zapis = json.load(d)
                zapis["naprave"][A] = ""                                # drug program: odvzem dostopa
                zapis["zavrnjeno"] = {DRUGI[1] + "|d": ZDAJ}             # ... in svoja zavrnitev
                with open(pot + ".drug", "w", encoding="utf-8") as d:
                    json.dump(zapis, d)
                os.replace(pot + ".drug", pot)
        with mock.patch.object(link_dostop.os, "fsync", fsync):
            self.assertTrue(link_dostop.zavrni_prosnjo(A, "p", zdaj=ZDAJ + 1))
        self.assertEqual(klici, [1])
        zapis = self._zapis()
        self.assertEqual(zapis["naprave"][A], "")
        self.assertEqual(zapis["zavrnjeno"], {DRUGI[1] + "|d": ZDAJ, A + "|p": ZDAJ + 1})
        self.assertEqual(sorted(os.listdir(os.path.dirname(pot))), ["dostop.json", "dostop.json.lock"])

    def test_dva_programa_hkrati_ne_izgubita_zavrnitev_ne_dovoljenj(self):
        """Pravi drug proces 100-krat spremeni dostop, ta proces medtem 100-krat zabelezi zavrnitev: na koncu so v
        zapisu vse spremembe obeh."""
        import subprocess
        import time
        pot = link_dostop._pot()
        link_dostop.nastavi(A, "d")
        koda = (
            "import sys\n"
            "from core import link_dostop\n"
            "link_dostop._za_preizkus(sys.argv[1])\n"
            "link_dostop.je_ta_naprava = lambda i: False\n"
            "link_dostop.jedro = lambda i: i[:18]\n"
            "link_dostop._lastni_kljuc = lambda: None\n"
            "def _brez_kroga():\n"
            "    raise RuntimeError('preizkus ne bere pravega kroga')\n"
            "link_dostop._krog = _brez_kroga\n"
            "for i in range(100):\n"
            "    link_dostop.nastavi('n-%016x' % (0x3000 + i), 'dp')\n")
        koren = os.path.dirname(os.path.dirname(os.path.abspath(link_dostop.__file__)))
        proces = subprocess.Popen([sys.executable, "-c", koda, pot], cwd=koren)
        try:
            rok = time.time() + 30
            while time.time() < rok and proces.poll() is None:
                try:
                    with open(pot, encoding="utf-8") as d:
                        if "n-%016x" % 0x3000 in json.load(d).get("naprave", {}):
                            break
                except (OSError, ValueError):
                    pass
                time.sleep(0.005)
            for i in range(100):
                link_dostop.zavrni_prosnjo("n-%016x" % (0x4000 + i), "d", zdaj=ZDAJ + i)
            self.assertEqual(proces.wait(timeout=60), 0)
        finally:
            if proces.poll() is None:
                proces.kill()
        zapis = self._zapis()
        self.assertEqual(sorted(zapis["naprave"]), sorted([A] + ["n-%016x" % (0x3000 + i) for i in range(100)]))
        self.assertEqual(sorted(zapis["zavrnjeno"]), sorted("n-%016x|d" % (0x4000 + i) for i in range(100)))
        self.assertEqual(sorted(os.listdir(os.path.dirname(pot))), ["dostop.json", "dostop.json.lock"])


class Zdruzevanje(_Osnova):
    """Ena naprava = eno obvestilo (lastnik, 15. 10. 2026: telefon je hkrati zaprosil za predvajalnik, zaslon in
    programe; racunalnik je pokazal tri obvestila zapored)."""

    def _javi_prikaz(self):
        self.razporejeno = []
        self.prikaz = link_dostop.ZdruzenPrikaz(
            self.pokazano.append, self.umaknjeno.append, lambda s, klic: self.razporejeno.append((s, klic)))
        link_dostop.nastavi_prikaz(self.prikaz.pokazi, self.prikaz.umakni)

    def _izvedi(self):
        cakajo, self.razporejeno = self.razporejeno, []
        for _s, klic in cakajo:
            klic()

    def test_tri_hkratne_prosnje_eno_obvestilo(self):
        for crka in "vzp":
            self.assertEqual(_vprasaj(A + "-os", crka, zdaj=ZDAJ + 0.1)[0], "pending")
        self.assertEqual([s for s, _ in self.razporejeno], [link_dostop.ZDRUZI_S])   # en odlozen prikaz
        self.assertEqual(self.pokazano, [])
        self._izvedi()
        self.assertEqual(len(self.pokazano), 1)
        p = self.pokazano[0]
        self.assertEqual((p["jedro"], p["zmoznosti"], p["ime"]), (A, "vzp", "Druzinski telefon"))
        self.assertEqual(link_dostop.telo_obvestila(p, "sl"),
                         "Druzinski telefon prosi za dostop: predvajalnik, zaslon in upravljanje, programi na tem računalniku.")
        self.assertEqual(link_dostop.telo_obvestila(p, "en"),
                         "Druzinski telefon is asking for access: player, screen and control, apps on this computer.")
        self.assertEqual(link_dostop.zmoznosti(A), set())               # prosnje same ne odprejo nicesar

    def test_poznejsa_prosnja_iste_naprave_zamenja_obvestilo(self):
        _vprasaj(A, "v", zdaj=ZDAJ)
        self._izvedi()
        _vprasaj(A, "d", zdaj=ZDAJ + 30)
        self._izvedi()
        self.assertEqual([p["zmoznosti"] for p in self.pokazano], ["v", "vd"])
        Gio, GLib = mock.MagicMock(), mock.MagicMock()
        GLib.Variant.side_effect = lambda tip, v: ("V", tip, v)
        app = mock.Mock()
        idji = {link_dostop.poslji_obvestilo(app, Gio, GLib, p, "sl") for p in self.pokazano}
        self.assertEqual(idji, {"safeer-dostop-" + A})                  # isti id: namizje ga zamenja
        gumbi = [c.args for c in Gio.Notification.new.return_value.add_button_with_target.call_args_list[-2:]]
        # Varna izbira prva (pregled 18. 10. 2026: privzeta izbira na daljincu je varna).
        self.assertEqual(gumbi, [("Zavrni", "app.dostop-zavrni", ("V", "s", A + "|vd")),
                                 ("Dovoli", "app.dostop-dovoli", ("V", "s", A + "|vd"))])

    def test_razlicni_napravi_dve_obvestili(self):
        _vprasaj(A, "v", zdaj=ZDAJ)
        _vprasaj(DRUGI[0], "v", zdaj=ZDAJ)
        _vprasaj(A, "z", zdaj=ZDAJ)
        self._izvedi()
        self.assertEqual(sorted((p["jedro"], p["zmoznosti"]) for p in self.pokazano), sorted([(A, "vz"), (DRUGI[0], "v")]))

    def test_dovoli_odobri_vse_nastete_z_enim_zapisom(self):
        for crka in "vzp":
            _vprasaj(A, crka, zdaj=ZDAJ)
        self._izvedi()
        pravi = link_dostop._na_disk
        with mock.patch.object(link_dostop, "_na_disk", side_effect=pravi) as zapis:
            self.assertTrue(link_dostop.odobri_prosnjo(A, "vzp"))
        self.assertEqual(zapis.call_count, 1)
        self.assertEqual(link_dostop.zmoznosti(A), {"v", "z", "p"})
        self.assertEqual(self._zapis()["naprave"], {A: "pvz"})
        self.assertEqual(link_dostop.odprte_prosnje(), [])
        self.assertIn(A, self.umaknjeno)                                # obvestilo se umakne
        self.assertFalse(link_dostop.odobri_prosnjo(A, "vzp"))         # enkrat
        self.assertEqual(_vprasaj(A, "z", zdaj=ZDAJ)[0], "none")         # zdaj ima dostop

    def test_dovoli_samo_nasteto_in_samo_odprto(self):
        for crka in "vz":
            _vprasaj(A, crka, zdaj=ZDAJ)
        self.assertTrue(link_dostop.odobri_prosnjo(A, "vzd"))           # d ni bil zaprosen: ne odpre se
        self.assertEqual(link_dostop.zmoznosti(A), {"v", "z"})
        self.assertFalse(link_dostop.odobri_prosnjo(A, "d"))
        self.assertFalse(link_dostop.odobri_prosnjo(A, "dpvz*"))
        self.assertEqual(link_dostop.zmoznosti(A), {"v", "z"})

    def test_dovoli_delno_pusti_ostalo_v_obvestilu(self):
        for crka in "vzp":
            _vprasaj(A, crka, zdaj=ZDAJ)
        self._izvedi()
        self.pokazano.clear()
        self.assertTrue(link_dostop.odobri_prosnjo(A, "vz"))            # obvestilo je bilo pokazano pred »p«
        self.assertEqual(link_dostop.zmoznosti(A), {"v", "z"})
        self._izvedi()
        self.assertEqual([p["zmoznosti"] for p in self.pokazano], ["p"])

    def test_zavrni_zavrne_vse_nastete_za_24_ur(self):
        for crka in "vzp":
            _vprasaj(A, crka, zdaj=ZDAJ)
        self.assertTrue(link_dostop.zavrni_prosnjo(A, "vzp", zdaj=ZDAJ + 1))
        self.assertEqual(link_dostop.odprte_prosnje(), [])
        self.assertEqual(self._zapis()["zavrnjeno"], {A + "|v": ZDAJ + 1, A + "|z": ZDAJ + 1, A + "|p": ZDAJ + 1})
        self.assertIn(A, self.umaknjeno)
        for crka in "vzp":
            self.assertEqual(_vprasaj(A, crka, zdaj=ZDAJ + 3600), ("declined", crka))
        self.assertEqual(_vprasaj(A, "d", zdaj=ZDAJ + 3600)[0], "pending")   # nenasteta crka ni zavrnjena
        self.assertEqual(_vprasaj(A, "z", zdaj=ZDAJ + 2 + 86400)[0], "pending")
        self.assertEqual(link_dostop.zmoznosti(A), set())

    def test_ob_prikazu_sveze_stanje(self):
        """Kar je bilo med cakanjem odobreno ali zavrnjeno, se ne pokaze; ce ni nic vec odprto, se obvestilo umakne."""
        _vprasaj(A, "v", zdaj=ZDAJ)
        _vprasaj(A, "z", zdaj=ZDAJ)
        link_dostop.zavrni_prosnjo(A, "z", zdaj=ZDAJ)
        self._izvedi()
        self.assertEqual([p["zmoznosti"] for p in self.pokazano], ["v"])
        _vprasaj(DRUGI[0], "d", zdaj=ZDAJ)
        link_dostop.odobri_prosnjo(DRUGI[0], "d")
        self.pokazano.clear()
        self._izvedi()
        self.assertEqual(self.pokazano, [])
        self.assertIn(DRUGI[0], self.umaknjeno)

    def test_neuspel_prikaz_zapre_prosnje_naprave(self):
        _vprasaj(A, "v", zdaj=ZDAJ)
        self.prikaz._pokazi = mock.Mock(side_effect=RuntimeError("ni obvestil"))
        self._izvedi()
        self.assertEqual(link_dostop.odprte_prosnje(), [])
        self.assertEqual(_vprasaj(A, "v", zdaj=ZDAJ + 5)[0], "none")      # naprava ne caka zaman
        self.assertFalse(link_dostop.odobri_prosnjo(A, "v"))

    def test_varnost_ostane(self):
        # Nezasciteno in neznana naprava: ni prosnje, ni obvestila.
        self.assertEqual(link_dostop.prosnja_ob_zavrnitvi(A, "v", zdaj=ZDAJ), ("none", "v"))
        self.assertEqual(_vprasaj(B, "v", zdaj=ZDAJ), ("none", "v"))
        self.assertEqual(self.razporejeno, [])
        # Ime iz kroga, ne iz sporocila; vse odprte ostanejo tudi pri zdruzevanju (ena prosnja na crko in napravo).
        for i, j in enumerate(DRUGI[:3]):
            for crka in "vz":
                _vprasaj(j, crka, zdaj=ZDAJ + i)
                _vprasaj(j, crka, zdaj=ZDAJ + i + 0.5)                   # ponovitev ne doda nove
        self.assertEqual(sorted(p["jedro"] + p["zmoznost"] for p in link_dostop.odprte_prosnje()),
                         sorted(j + c for j in DRUGI[:3] for c in "vz"))
        self._izvedi()
        self.assertEqual(sorted((p["jedro"], p["zmoznosti"]) for p in self.pokazano),
                         sorted([(DRUGI[0], "vz"), (DRUGI[1], "vz"), (DRUGI[2], "vz")]))
        self.assertTrue(all(p["ime"].startswith("Naprava ") for p in self.pokazano))
        # Brez klika nic: zapis dovoljenj je prazen.
        self.assertEqual(link_dostop.zmoznosti(DRUGI[1]), set())

    def test_dejanje_gumba_nosi_vse_crke(self):
        Gio, GLib = mock.MagicMock(), mock.MagicMock()
        dejanja = {}

        def nova(ime, tip):
            d = mock.Mock()
            d.connect.side_effect = lambda _sig, fn: dejanja.__setitem__(ime, fn)
            return d
        Gio.SimpleAction.new.side_effect = nova
        app = mock.Mock()
        link_dostop.registriraj_dejanja(app, Gio, GLib, link_dostop.odobri_prosnjo, link_dostop.zavrni_prosnjo, mock.Mock())
        for crka in "vzp":
            _vprasaj(A, crka, zdaj=ZDAJ)
        _vprasaj(DRUGI[0], "d", zdaj=ZDAJ)
        dejanja["dostop-dovoli"](None, A + "|vzp")
        self.assertEqual(link_dostop.zmoznosti(A), {"v", "z", "p"})
        dejanja["dostop-zavrni"](None, DRUGI[0] + "|d")
        self.assertEqual(_vprasaj(DRUGI[0], "d", zdaj=ZDAJ + 60)[0], "declined")
        self.assertEqual(link_dostop.zmoznosti(DRUGI[0]), set())


if __name__ == "__main__":
    unittest.main()


class Skrcitev(_Osnova):
    """Obvestilo s prosnjo ne ostane ure na zaslonu (lastnik, 17. 10. 2026: na testnem PC je stalo od polnoci): po
    SKRCI_PO_S gre z zaslona, prosnja ostane veljavna, stevec na ikoni Link jo kaze, nic se ne odobri ali zavrne samo."""

    def _javi_prikaz(self):
        self.razporejeno, self.skrceno = [], []
        self.prikaz = link_dostop.ZdruzenPrikaz(
            self.pokazano.append, self.umaknjeno.append, lambda s, klic: self.razporejeno.append((s, klic)),
            skrci=self.skrceno.append)
        link_dostop.nastavi_prikaz(self.prikaz.pokazi, self.prikaz.umakni)

    def _izvedi(self):
        cakajo, self.razporejeno = self.razporejeno, []
        for _s, klic in cakajo:
            klic()

    def test_po_desetih_sekundah_skrci_prosnja_ostane(self):
        _vprasaj(A, "v", zdaj=ZDAJ)
        self._izvedi()                                                  # prikaz po ZDRUZI_S
        self.assertEqual(len(self.pokazano), 1)
        self.assertEqual([s for s, _ in self.razporejeno], [link_dostop.SKRCI_PO_S])
        self.assertEqual(link_dostop.SKRCI_PO_S, 10.0)
        self._izvedi()                                                  # 10 s pozneje
        self.assertEqual(self.skrceno, [A])
        self.assertEqual(self.umaknjeno, [])                            # prosnja ni umaknjena
        self.assertEqual([p["jedro"] for p in link_dostop.odprte_prosnje()], [A])
        self.assertEqual(link_dostop.zmoznosti(A), set())               # nic odobreno
        self.assertEqual(self._zapis().get("zavrnjeno", {}), {})        # nic zavrnjeno
        self.assertEqual(link_dostop.stevilo_cakajocih(), 1)
        # Klik na stevec: obvestilo znova, z enakimi gumbi, in se spet skrci.
        self.assertEqual(self.prikaz.pokazi_znova(), 1)
        self.assertEqual(len(self.pokazano), 2)
        self._izvedi()
        self.assertEqual(self.skrceno, [A, A])
        self.assertTrue(link_dostop.odobri_prosnjo(A, "v"))             # odgovor uporabnika velja tudi po skrcitvi
        self.assertEqual(link_dostop.stevilo_cakajocih(), 0)

    def test_novo_obvestilo_iste_naprave_ima_svoj_rok(self):
        _vprasaj(A, "v", zdaj=ZDAJ)
        self._izvedi()
        prvi_rok = self.razporejeno
        self.razporejeno = []
        _vprasaj(A, "d", zdaj=ZDAJ + 30)
        self._izvedi()                                                  # novo obvestilo (vd)
        for _s, klic in prvi_rok:
            klic()                                                      # rok prvega obvestila ne skrci novega
        self.assertEqual(self.skrceno, [])
        self._izvedi()
        self.assertEqual(self.skrceno, [A])

    def test_odgovorjena_se_ne_skrci(self):
        _vprasaj(A, "v", zdaj=ZDAJ)
        self._izvedi()
        link_dostop.zavrni_prosnjo(A, "v", zdaj=ZDAJ + 1)
        self._izvedi()
        self.assertEqual(self.skrceno, [])

    def test_obvestilo_ni_kriticno(self):
        _vprasaj(A, "v", zdaj=ZDAJ)
        self._izvedi()
        Gio, GLib = mock.MagicMock(), mock.MagicMock()
        link_dostop.poslji_obvestilo(mock.Mock(), Gio, GLib, self.pokazano[0], "sl")
        Gio.Notification.new.return_value.set_priority.assert_called_once_with(Gio.NotificationPriority.NORMAL)

    def test_besedilo_stevca(self):
        self.assertEqual([link_dostop.besedilo_stevca("sl", n) for n in (1, 2, 3, 5, 101)],
                         ["1 zahteva za dostop", "2 zahtevi za dostop", "3 zahteve za dostop", "5 zahtev za dostop",
                          "101 zahteva za dostop"])
        self.assertEqual(link_dostop.besedilo_stevca("en", 2), "2 access requests")
        for jezik in ("de", "es", "fr", "it"):
            self.assertIn("1", link_dostop.besedilo_stevca(jezik, 1))
        self.assertEqual(link_dostop.besedilo_stevca("xx", 1), "1 access request")
