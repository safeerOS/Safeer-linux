"""Neodvisni pregled 17 (25. 10. 2026) popravkov pregleda 11: vsak preizkus brez svojega popravka pade."""
import json
import os
import shutil
import tempfile
import time
import unittest
from unittest import mock

import pytest

from core import link_datoteke, link_dostop
from tests.test_link_dostop import A, B, _Osnova
from tests.test_pregled11_ozji_krog import _Dom, _Krog

pytestmark = pytest.mark.pravi_dostop

MEJA = link_dostop.MEJA_PODEDOVANJA


class M1MigracijaBrezKroga(_Osnova):
    clani = ({"id": "jaz", "kljuc": "KJAZ", "dodano": MEJA - 9000}, {"id": "a", "kljuc": "KA", "dodano": MEJA - 100})

    def _star_zapis(self, naprave):
        pot = link_dostop._pot()
        with open(pot, "w", encoding="utf-8") as d:
            json.dump({"v": 1, "podedovano_ob": MEJA + 100, "naprave": naprave}, d)
        link_dostop._za_preizkus(pot)
        return pot

    def _na_disku(self, pot):
        with open(pot, encoding="utf-8") as d:
            return json.load(d)["naprave"]

    def test_brez_kljuca_oznaka_ni_zapisana_migracija_se_ponovi(self):
        """Kljuc te naprave (se) ni berljiv: »ne vem« ni »nobena« - brez oznake, v programu brez ozjega kroga."""
        pot = self._star_zapis({A: "dpvz"})
        with mock.patch.object(link_dostop, "_lastni_kljuc", lambda: None):
            self.assertEqual(link_dostop.zmoznosti(A), {"p", "v"})
            self.assertFalse(os.path.exists(pot + ".podedovano"), "oznaka brez migracije")
        with mock.patch.object(link_dostop, "UMIK_PONOVI_S", 0.0):
            self.assertEqual(link_dostop.zmoznosti(A), {"p", "v"})
        self.assertTrue(os.path.exists(pot + ".podedovano"))
        self.assertEqual(self._na_disku(pot)[A], "pv")

    def test_drug_zapis_med_cakanjem_ne_zapise_oznake(self):
        pot = self._star_zapis({A: "dpvz"})
        with mock.patch.object(link_dostop, "_lastni_kljuc", lambda: None):
            self.assertTrue(link_dostop.nastavi(B, "p"))
            self.assertFalse(os.path.exists(pot + ".podedovano"), "vsak zapis je prej zapisal oznako")
            self.assertEqual(link_dostop.zmoznosti(A), {"p", "v"})
        with mock.patch.object(link_dostop, "UMIK_PONOVI_S", 0.0):
            link_dostop.zmoznosti(A)
        self.assertEqual(self._na_disku(pot)[A], "pv")
        self.assertEqual(self._na_disku(pot)[B], "p")

    def test_prazen_krog_z_napravami_ni_nobena(self):
        self.clani = ()
        pot = self._star_zapis({A: "dpvz"})
        self.assertEqual(link_dostop.zmoznosti(A), {"p", "v"})
        self.assertFalse(os.path.exists(pot + ".podedovano"))


class M2Vrnitev(_Krog):
    def test_zastarel_umik_ne_vzame_privolitve_po_vrnitvi(self):
        link_dostop.nastavi_ozji_krog(self.jedro, "dpvz")
        self.k.umakni(self.jedro, "n-0000000000000001")
        ob = self.k.umiki[self.jedro]["umaknjeno"]
        self.assertEqual(link_dostop.zmoznosti(self.jedro), set())
        self.assertTrue(self.k.dodaj(self.jedro, self.kljuc, "Telefon", "android", "n-0000000000000001",
                                     dodano=ob + 1))
        self.assertEqual(link_dostop.zmoznosti(self.jedro), set(), "vrnitev ne vrne starega")
        self.assertTrue(link_dostop.nastavi_ozji_krog(self.jedro, "pv"))       # nova privolitev po vrnitvi
        # Naprava, ki vrnitve se ni videla, poslje star zapis umika - vsaka taka zdruzitev je prej vzela vse.
        self.k.zdruzi({"umiki": {self.jedro: {"umaknjeno": ob, "umaknil": "n-0000000000000001"}}})
        self.assertNotIn(self.jedro, self.k.umiki)
        self.assertEqual(link_dostop.zmoznosti(self.jedro), set("dpvz"))

    def test_vrnitev_iz_drugega_programa_vzame_samo_staro(self):
        """Drug program tega racunalnika (zastarel krog) obdela vrnitev pozneje: privolitev po umiku ostane."""
        ob = time.time() - 5
        self.assertTrue(link_dostop.nastavi_ozji_krog(self.jedro, "pv"))      # dana po umiku
        link_dostop.ob_umiku_iz_kroga(set(), {self.jedro: ob})
        self.assertEqual(link_dostop.zmoznosti(self.jedro), set("dpvz"))
        link_dostop.ob_umiku_iz_kroga(set(), {self.jedro: time.time() + 5})   # dana pred umikom: gre
        self.assertEqual(link_dostop.zmoznosti(self.jedro), set())


class M3VesDiskBrezOzjegaKroga(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        koren = os.path.realpath(tmp.name)
        self.dom = os.path.join(koren, "domovi", "uporabnik")
        self.usb = os.path.join(koren, "media", "usb")
        os.makedirs(os.path.join(self.dom, "Dokumenti"))
        os.makedirs(self.usb)
        for pot in (os.path.join(self.dom, "Dokumenti", "pismo.txt"), os.path.join(self.usb, "film.mp4")):
            with open(pot, "w", encoding="utf-8") as d:
                d.write("x")
        p = mock.patch.dict(os.environ, {"HOME": self.dom})
        p.start()
        self.addCleanup(p.stop)
        self.d = link_datoteke.Datoteke([], tls_mapa=os.path.join(koren, ".tls"), ves_disk=True)
        self.addCleanup(self.d.ustavi)

    def test_tv_vidi_zunanji_disk_domace_mape_ne(self):
        with mock.patch.object(link_datoteke, "_v_ozjem_krogu", lambda n: n == A), \
                mock.patch.object(self.d, "streznik_za", return_value={}):
            koren_b = self.d.seznam("", B)
            self.assertTrue(koren_b["shared"], "»ves disk« za televizor brez ozjega kroga")
            oznake = [v["id"] for v in koren_b["items"]]
            self.assertIn("disk:/", oznake)
            self.assertNotIn("disk:" + self.dom, oznake)
            self.assertIn("film.mp4", [v["name"] for v in self.d.seznam("disk:" + self.usb, B)["items"]])
            for mapa in (self.dom, os.path.dirname(self.dom)):          # tudi mapa domacih map (/home)
                with self.assertRaises(FileNotFoundError):
                    self.d.seznam("disk:" + mapa, B)
            self.assertIn("disk:" + self.dom, [v["id"] for v in self.d.seznam("", A)["items"]])
        s = self.d.streznik
        s.sme, s.umaknjena, s.v_ozjem_krogu = (lambda n, z: True), (lambda n: False), (lambda n: n == A)
        z = s.zeton_za(B)
        self.assertTrue(s.zeton_velja(z, zmoznost="d", oznaka="disk:" + self.usb + "/film.mp4"))
        self.assertFalse(s.zeton_velja(z, zmoznost="d", oznaka="disk:" + self.dom + "/Dokumenti/pismo.txt"))
        os.symlink(os.path.join(self.dom, "Dokumenti"), os.path.join(self.usb, "bliznjica"))
        self.assertFalse(s.zeton_velja(z, zmoznost="d", oznaka="disk:" + self.usb + "/bliznjica/pismo.txt"),
                         "povezava z zunanjega diska v domaco mapo")


class M4PrivolitevPoNeuspelemUmiku(_Krog):
    def setUp(self):
        super().setUp()
        # Privolitev pride, preden se umik ponovi (prej: v 5 s po zadnjem poskusu v poti branja).
        p = mock.patch.object(link_dostop, "UMIK_PONOVI_S", 3600.0)
        p.start()
        self.addCleanup(p.stop)

    def test_nova_privolitev_velja_in_ostane(self):
        link_dostop.nastavi_ozji_krog(self.jedro, "dpvz")
        with mock.patch.object(link_dostop, "_na_disk", side_effect=OSError(28, "No space left on device")):
            self.k.umakni(self.jedro, "n-0000000000000001")
            self.assertEqual(link_dostop.zmoznosti(self.jedro), set())
            # Disk je se poln tudi ob ponovni seznanitvi; uporabnik nato sprosti prostor in da privolitev.
            self.assertTrue(self.k.dodaj(self.jedro, self.kljuc, "Telefon", "android", "n-0000000000000001"))
        self.assertTrue(link_dostop.nastavi_ozji_krog(self.jedro, "p"))
        pricakovano = link_dostop.ozji_krog({"p"})
        self.assertEqual(link_dostop.zmoznosti(self.jedro), pricakovano, "»Shranjeno« mora veljati")
        link_dostop._ponovi_v_ozadju()
        self.assertEqual(link_dostop.zmoznosti(self.jedro), pricakovano, "ponovljen umik je ne izbrise")


class M5UmikBrezBranja(_Krog):
    def test_neberljiv_zapis_umik_caka(self):
        link_dostop.nastavi_ozji_krog(self.jedro, "dpvz")
        pot = link_dostop._pot()
        with mock.patch.object(link_dostop, "_z_diska", return_value=("napaka", {}, set(), 0.0, {})):
            link_dostop._za_preizkus(pot)
            link_dostop.ob_umiku_iz_kroga({self.jedro})
        self.assertEqual(link_dostop.zmoznosti(self.jedro), set(), "branje spet dela: umik velja")
        link_dostop._ponovi_v_ozadju()
        with open(pot, encoding="utf-8") as d:
            self.assertEqual(json.load(d)["naprave"].get(self.jedro, ""), "")

    def test_pot_branja_ne_pise(self):
        link_dostop.nastavi_ozji_krog(self.jedro, "dpvz")
        with mock.patch.object(link_dostop, "_na_disk", side_effect=OSError(28, "No space left on device")):
            link_dostop.ob_umiku_iz_kroga({self.jedro})
        klici = []
        pravi = link_dostop._spremeni
        with mock.patch.object(link_dostop, "UMIK_PONOVI_S", 0.0), \
                mock.patch.object(link_dostop, "_spremeni", lambda *a, **k: klici.append(1) or pravi(*a, **k)):
            for _ in range(3):
                self.assertEqual(link_dostop.zmoznosti(self.jedro), set())
        self.assertEqual(klici, [], "zmoznosti() ne sme pisati (casovnik v svoji niti)")


class M6M8Skrivnosti(unittest.TestCase):
    def setUp(self):
        self.mapa = os.path.realpath(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.mapa, True)

    def _datoteka(self, ime, vsebina):
        pot = os.path.join(self.mapa, ime)
        os.makedirs(os.path.dirname(pot), exist_ok=True)
        with open(pot, "wb") as d:
            d.write(vsebina)
        return pot

    def test_spremljajoce_datoteke_profila_in_kljuci_der(self):
        skrite = {"Default/Cookies-journal": b"\xd9\xd5\x05\xf9\x20\xa1\x63\xd7" + b"\x00" * 50,
                  "Kopija/Cookies-wal": b"\x37\x7f\x06\x82" + b"\x00" * 50,
                  "Profil/Web Data": b"SQLite format 3\x00" + b"\x00" * 50,
                  "Profil/Web Data-shm": b"\x00" * 64,
                  "streznik.key": b"\x30\x82\x04\xbd\x02\x01\x00\x30\x0d\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x01\x01"
                                  + b"\x00" * 40,
                  "naprava.der": b"\x30\x77\x02\x01\x01\x04\x20" + b"\x11" * 40}
        vidne = {"potrdilo.der": b"\x30\x82\x03\x00\x30\x82\x02\xe8\xa0\x03\x02\x01\x02" + b"\x00" * 40,
                 "Recepti/Cookies-journal": b"moj dnevnik piskotov"}
        for ime, vsebina in list(skrite.items()) + list(vidne.items()):
            self._datoteka(ime, vsebina)
        m = link_datoteke.DeljeneMape([self.mapa])
        for ime in skrite:
            self.assertIsNone(m.razresi("share:0:" + ime), ime)
        for ime in vidne:
            self.assertIsNotNone(m.razresi("share:0:" + ime), ime)

    def test_predpomnilnik_ne_vrne_zastarelega_izida(self):
        pot = self._datoteka("nastavitve.txt", b"a" * 64)
        t = time.time_ns()
        os.utime(pot, ns=(t, t))
        link_datoteke._vsebina_spomin.clear()
        self.assertFalse(link_datoteke._vsebina_skrivnost(pot))
        with open(pot, "r+b") as d:             # ista datoteka, ista dolzina, isti cas (FAT, hiter urejevalnik)
            d.write(b"aws_secret_access_key=" + b"x" * 42)
        os.utime(pot, ns=(t, t))
        self.assertTrue(link_datoteke._vsebina_skrivnost(pot))


class M9Zagon(_Dom):
    def test_mapa_ne_postane_mapa_path(self):
        os.makedirs(os.path.join(self.dom, "Dokumenti", "bin"))
        os.makedirs(os.path.join(self.dom, "projekt", "orodja"))
        with mock.patch.dict(os.environ, {"PATH": os.path.join(self.dom, "projekt", "bin") + os.pathsep + "/usr/bin"}):
            koda, _ = self.s.uredi("dom:Dokumenti/bin", {"op": "move", "folder": "dom:projekt"}, naprava=A)
            self.assertEqual(koda, 403, "premik")
            koda, _ = self.s.uredi("dom:projekt/orodja", {"op": "rename", "name": "bin"}, naprava=A)
            self.assertEqual(koda, 403, "preimenovanje")
        self.assertTrue(os.path.isdir(os.path.join(self.dom, "projekt", "orodja")))

    def test_namizje_iz_user_dirs(self):
        os.makedirs(os.path.join(self.dom, ".config"))
        os.makedirs(os.path.join(self.dom, "Schreibtisch"))
        with open(os.path.join(self.dom, ".config", "user-dirs.dirs"), "w", encoding="utf-8") as d:
            d.write('XDG_DESKTOP_DIR="$HOME/Schreibtisch"\n')
        koda, _ = self.s.uredi("dom:Dokumenti/zagon.desktop", {"op": "move", "folder": "dom:Schreibtisch"}, naprava=A)
        self.assertEqual(koda, 403)


class M10PrivolitevPreverjena(_Osnova):
    def test_povozena_privolitev_ni_shranjena(self):
        link_dostop.nastavi(A, "p")
        pot = link_dostop._pot()
        pravi = link_dostop._fsync_mape

        def star_program(mapa):
            pravi(mapa)
            try:
                with open(pot, encoding="utf-8") as d:
                    zapis = json.load(d)
            except (OSError, ValueError):
                return
            if zapis.get("naprave", {}).pop(B, None) is not None:     # starejsi program povozi z zapisom brez B
                with open(pot + ".star", "w", encoding="utf-8") as d:
                    json.dump(zapis, d)
                os.replace(pot + ".star", pot)
        with mock.patch.object(link_dostop, "_fsync_mape", star_program):
            self.assertFalse(link_dostop.nastavi(B, "p"), "»Shranjeno« samo, ce je zapisano")


class DomacaMapaIzrecno(_Osnova):
    """Vodja 25. 10. 2026: zapis d+z iz prejsnje razlicice obdrzi datoteke in upravljanje; domaco mapo dobi sele z
    izrecno, informirano privolitvijo - ob prvem zagonu nove razlicice se ne podeli sama."""

    def _star_zapis(self, naprave):
        pot = link_dostop._pot()
        with open(pot, "w", encoding="utf-8") as d:
            json.dump({"v": 1, "podedovano_ob": MEJA + 100, "naprave": naprave}, d)
        with open(pot + ".podedovano", "w", encoding="utf-8") as d:
            d.write("{}")
        link_dostop._za_preizkus(pot)

    def test_star_zapis_dz_brez_domace_mape(self):
        self._star_zapis({B: "dz"})
        self.assertEqual(link_dostop.zmoznosti(B), {"d", "z"}, "datoteke in upravljanje ostanejo")
        self.assertTrue(link_dostop.v_ozjem_krogu(B))
        self.assertFalse(link_dostop.sme_domaco_mapo(B), "domaca mapa se ne podeli sama")
        self.assertTrue(link_dostop.dovoli_domaco_mapo(B))
        self.assertTrue(link_dostop.sme_domaco_mapo(B))
        self.assertEqual(link_dostop.zmoznosti(B), {"d", "z"})
        link_dostop.nastavi(B, "d")                  # izgubi ozji krog: privolitev za domaco mapo gre z njim
        link_dostop.nastavi(B, "dz")
        self.assertFalse(link_dostop.sme_domaco_mapo(B))

    def test_stikalo_ozjega_kroga_je_privolitev(self):
        self.assertTrue(link_dostop.nastavi_ozji_krog(B, "p"))
        self.assertTrue(link_dostop.sme_domaco_mapo(B))
        link_dostop.nastavi(A, "p")                  # zunaj ozjega kroga domace mape ne da niti gumb
        self.assertFalse(link_dostop.dovoli_domaco_mapo(A))
        self.assertFalse(link_dostop.sme_domaco_mapo(A))

    def test_obvestilo_pove_domaco_mapo(self):
        self._star_zapis({B: "dz"})
        prosnja = {"jedro": B, "ime": "Televizor", "zmoznost": "p"}
        for jezik in ("sl", "en", "de", "es", "fr", "it"):
            self.assertIn(link_dostop.besedilo_obvestila(jezik, "dom"), link_dostop.telo_obvestila(prosnja, jezik))
        self.assertTrue(link_dostop.dovoli_domaco_mapo(B))
        self.assertNotIn(link_dostop.besedilo_obvestila("sl", "dom"), link_dostop.telo_obvestila(prosnja, "sl"))

    def test_seznam_datotek_brez_domace_mape(self):
        self._star_zapis({B: "dz"})
        d = link_datoteke.Datoteke([], tls_mapa=os.path.join(self._mapa.name, ".tls"), dom=True)
        self.addCleanup(d.ustavi)
        with mock.patch.object(d, "streznik_za", return_value={}):
            self.assertNotIn("dom:", [v["id"] for v in d.seznam("", B)["items"]])
            self.assertTrue(link_dostop.dovoli_domaco_mapo(B))
            self.assertIn("dom:", [v["id"] for v in d.seznam("", B)["items"]])


class OknoLinkDomacaMapa(unittest.TestCase):
    def test_gumb_most_in_besedila_v_vseh_jezikih(self):
        from pathlib import Path
        koren = Path(__file__).resolve().parents[1]
        js = (koren / "assets" / "link" / "link.js").read_text(encoding="utf-8")
        self.assertEqual((js.count("dostopDomOpis:"), js.count("dostopDomDovoli:")), (6, 6))
        self.assertIn('id="gumbDostopDom"', (koren / "assets" / "link" / "index.html").read_text(encoding="utf-8"))
        vir = (koren / "core" / "safeer_link.py").read_text(encoding="utf-8")
        self.assertIn('dovoliDomacoMapo: function (id) { poslji("dovoliDomacoMapo", [id]); }', vir)
        # Pregled 29, G12: zapis v ozadju, okno ne zamrzne.
        self.assertIn('"dovoliDomacoMapo": lambda: self._v_ozadju(lambda: self._dovoli_domaco_mapo(*argumenti[:1]))',
                      vir)
        self.assertIn('"dom": bool(link_dostop.sme_domaco_mapo(id_naprave))', vir)


# ---------------------------------------------------------------------------------------------- pregled 29 (Grok)

def _zapis_prejsnje(naprave, oznaka=True):
    """Zapis dostop.json prejsnje razlicice (brez polj dom in dano_ob); `oznaka`: migracija je ze opravljena."""
    pot = link_dostop._pot()
    with open(pot, "w", encoding="utf-8") as d:
        json.dump({"v": 1, "podedovano_ob": MEJA + 100, "naprave": naprave}, d)
    if oznaka:
        with open(pot + ".podedovano", "w", encoding="utf-8") as d:
            d.write("{}")
    link_dostop._za_preizkus(pot)
    return pot


class G1DomacaMapaSamoObVklopu(_Osnova):
    """Pregled 29, G1: domaco mapo je podelila vsaka sprememba stikal (nastavi_ozji_krog je vedno zapisal dom)."""

    def test_sprememba_drugega_stikala_ne_da_domace_mape(self):
        _zapis_prejsnje({B: "dpvz"})
        self.assertFalse(link_dostop.sme_domaco_mapo(B))
        self.assertTrue(link_dostop.nastavi_ozji_krog(B, "dvz"))          # izklop »Programi«
        self.assertEqual(link_dostop.zmoznosti(B), set("dvz"))
        self.assertFalse(link_dostop.sme_domaco_mapo(B), "izklop drugega stikala je dal domaco mapo")
        self.assertTrue(link_dostop.nastavi_ozji_krog(B, "dpvz"))         # vklop »Programi« (ozji krog je ze bil)
        self.assertFalse(link_dostop.sme_domaco_mapo(B))

    def test_izklop_zunaj_ozjega_kroga_ne_da_pravic(self):
        _zapis_prejsnje({B: "pv", A: "dpv"})
        self.assertTrue(link_dostop.nastavi_ozji_krog(B, "v"))            # izklop »Programi«
        self.assertEqual(link_dostop.zmoznosti(B), {"v"}, "izklop je dal upravljanje in mape")
        self.assertFalse(link_dostop.sme_domaco_mapo(B))
        # Okno »d« ne pokaze: izklop »Predvajalnik« ga ne vzame (izbrane mape iz prejsnje razlicice ostanejo).
        self.assertTrue(link_dostop.nastavi_ozji_krog(A, "p"))
        self.assertEqual(link_dostop.zmoznosti(A), {"d", "p"})

    def test_vklop_ozjega_kroga_je_privolitev(self):
        _zapis_prejsnje({B: "pv", A: "dz"})
        self.assertTrue(link_dostop.nastavi_ozji_krog(B, "pvz"))
        self.assertEqual(link_dostop.zmoznosti(B), set("dpvz"))
        self.assertTrue(link_dostop.sme_domaco_mapo(B))
        # d+z iz prejsnje razlicice: izklop in vklop stikala ozjega kroga je izrecna privolitev.
        self.assertFalse(link_dostop.sme_domaco_mapo(A))
        self.assertTrue(link_dostop.nastavi_ozji_krog(A, ""))
        self.assertTrue(link_dostop.nastavi_ozji_krog(A, "z"))
        self.assertTrue(link_dostop.sme_domaco_mapo(A))


class G2IzrecnaMedCakajocoMigracijo(_Osnova):
    """Pregled 29, G2: med cakajoco migracijo je naprava z vsemi stirimi izgubila ozji krog, tudi z izrecno novo
    privolitvijo, okno pa je javilo »Shranjeno«; ko je migracija stekla, je vzela se domaco mapo."""
    clani = ({"id": "jaz", "kljuc": "KJAZ", "dodano": MEJA - 9000}, {"id": "a", "kljuc": "KA", "dodano": MEJA - 100})

    def _na_disku(self, pot):
        with open(pot, encoding="utf-8") as d:
            return json.load(d)["naprave"]

    def test_izrecna_privolitev_velja_in_je_migracija_ne_vzame(self):
        pot = _zapis_prejsnje({A: "dpvz"}, oznaka=False)
        with mock.patch.object(link_dostop, "_lastni_kljuc", lambda: None):      # migracija caka
            self.assertEqual(link_dostop.zmoznosti(A), {"p", "v"})
            self.assertTrue(link_dostop.nastavi_ozji_krog(A, "dpvz"))
            self.assertEqual(link_dostop.zmoznosti(A), set("dpvz"), "»Shranjeno«, a brez upravljanja")
            self.assertTrue(link_dostop.sme_domaco_mapo(A))
        with mock.patch.object(link_dostop, "UMIK_PONOVI_S", 0.0):
            self.assertEqual(link_dostop.zmoznosti(A), set("dpvz"), "migracija je vzela izrecno privolitev")
            self.assertTrue(link_dostop.sme_domaco_mapo(A))
        self.assertEqual(self._na_disku(pot)[A], "dpvz")
        self.assertTrue(os.path.exists(pot + ".podedovano"))

    def test_prazen_krog_z_izrecno_privolitvijo_ne_caka(self):
        self.clani = ()
        pot = _zapis_prejsnje({A: "dpvz"}, oznaka=False)
        self.assertEqual(link_dostop.zmoznosti(A), {"p", "v"})
        self.assertTrue(link_dostop.nastavi_ozji_krog(A, "dpvz"))
        self.assertEqual(link_dostop.zmoznosti(A), set("dpvz"))
        with mock.patch.object(link_dostop, "UMIK_PONOVI_S", 0.0):
            self.assertEqual(link_dostop.zmoznosti(A), set("dpvz"))
        self.assertTrue(os.path.exists(pot + ".podedovano"), "migracija pri praznem krogu caka trajno")

    def test_shranjeno_samo_ce_v_programu_velja(self):
        _zapis_prejsnje({A: "dpvz"}, oznaka=False)
        with mock.patch.object(link_dostop, "_lastni_kljuc", lambda: None), \
                mock.patch.object(link_dostop, "_izrecna", lambda ostalo: set()):
            self.assertFalse(link_dostop.nastavi_ozji_krog(A, "dpvz"), "»Shranjeno«, ceprav v programu ne velja")
