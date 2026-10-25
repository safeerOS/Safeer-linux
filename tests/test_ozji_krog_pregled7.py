"""Sedmi neodvisni pregled (25. 10. 2026): ozji krog in umik naprave - vsak preizkus brez svojega popravka pade.

Pravilo lastnika (25. 10. 2026 10:49): naprava v ozjem krogu z ENO izrecno privolitvijo dobi upravljanje s Safeer Vnos in
domaco mapo; umik iz kroga TAKOJ preklice sejo zaslona, vnos in zetone. O dostopu odloca samo ta naprava; nic iz
dohodnega sporocila ne sme podeliti dostopa (AGENTS.md).
"""
import base64
import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from unittest import mock

import pytest

from core import link_daljinec, link_datoteke, link_dostop, link_krog, link_zaslon
from tests.test_link_dostop import A, B, _Krog, _Osnova
from tests.test_link_dostop_prosnja import CLANI, KLJUCI, _vprasaj

pytestmark = pytest.mark.pravi_dostop


class U8Natancno(_Osnova):
    def test_nastavi_in_dodaj_zmoznost_sta_natancni(self):
        """Ozji krog samo na poti izrecne privolitve: koda, ki doda eno zmoznost, ne podeli upravljanja po pomoti."""
        self.assertTrue(link_dostop.nastavi(B, "p"))
        self.assertEqual(link_dostop.zmoznosti(B), {"p"})
        self.assertTrue(link_dostop.dodaj_zmoznost(B, "v"))
        self.assertEqual(link_dostop.zmoznosti(B), {"p", "v"})
        self.assertFalse(link_dostop.sme_dejanje(B, "input.key"))

    def test_stikalo_okna_je_ozji_krog(self):
        self.assertTrue(link_dostop.nastavi_ozji_krog(B, "p"))
        self.assertEqual(link_dostop.zmoznosti(B), {"p", "d", "z"})
        self.assertTrue(link_dostop.nastavi_ozji_krog(B, ""))
        self.assertEqual(link_dostop.zmoznosti(B), set())

    def test_okno_link_gre_skozi_ozji_krog(self):
        from core import safeer_link
        link = safeer_link.SafeerLink.__new__(safeer_link.SafeerLink)
        link.naprave, link.naprave_vse, link.zaslon = [], None, None
        odzivi = []
        link._odziv = lambda vrsta, podatki: odzivi.append((vrsta, podatki))
        link._nastavi_dostop(B, "v")
        self.assertEqual(link_dostop.zmoznosti(B), {"v", "d", "z"})
        self.assertIn(("dostop", {"id": B, "ok": True, "dostop": "dvz", "jaz": False}), odzivi, "dejanski nabor")


class U4Dedovanje(_Osnova):
    MEJA = link_dostop.MEJA_PODEDOVANJA
    clani = ({"id": "jaz", "kljuc": "KJAZ", "dodano": MEJA - 9000}, {"id": "a", "kljuc": "KA", "dodano": MEJA - 100})

    def test_podedovana_naprava_brez_ozjega_kroga(self):
        self.assertEqual(link_dostop.zmoznosti(A), {"p", "v"})
        self.assertFalse(link_dostop.sme_dejanje(A, "screen.start"))
        self.assertFalse(link_dostop.sme_dejanje(A, "files.list"))

    def test_izginul_zapis_ne_podeduje_znova(self):
        link_dostop.zmoznosti(A)                        # prvi zagon: dedovanje
        self.assertTrue(link_dostop.nastavi(A, ""))     # uporabnik je dostop vzel
        pot = link_dostop._pot()
        os.remove(pot)                                  # npr. rocno ciscenje nastavitev, obnova brez datoteke
        link_dostop._za_preizkus(pot)                   # nov zagon programa
        self.assertEqual(link_dostop.zmoznosti(A), set())
        self.assertTrue(os.path.exists(pot), "nov prazen zapis")

    def test_star_zapis_dobi_oznako_dedovanja(self):
        """Zapis iz razlicice pred oznako: ob branju se oznaka dopise - izginul zapis potem ne podeduje."""
        pot = link_dostop._pot()
        with open(pot, "w", encoding="utf-8") as d:
            json.dump({"v": 1, "podedovano_ob": 1.0, "naprave": {B: "p"}}, d)
        link_dostop._za_preizkus(pot)
        self.assertEqual(link_dostop.zmoznosti(B), {"p"})
        self.assertTrue(os.path.exists(pot + ".podedovano"))
        os.remove(pot)
        link_dostop._za_preizkus(pot)
        self.assertEqual(link_dostop.zmoznosti(A), set())

    def test_zapisa_ni_mogoce_ustvariti_nihce(self):
        with mock.patch.object(link_dostop, "_na_disk", side_effect=OSError(28, "No space left on device")):
            self.assertEqual(link_dostop.zmoznosti(A), set())


class U6BrezPreverbeNikoli(_Osnova):
    def test_odvzem_ne_povozi_spremembe_ki_se_dogaja_ves_cas(self):
        """Drug program pise zapis med vsakim nasim poskusom: odvzem ne uspe (uporabnik vidi napako) - zadnji poskus
        ne pise vec brez preverbe (prej je povozil zapis drugega programa)."""
        link_dostop.nastavi(B, "dz")
        pot = link_dostop._pot()
        pravi = link_dostop._na_disk
        stevec = [0]

        def drug_program_vmes(*a, **k):
            stevec[0] += 1
            with open(pot + ".drug", "w", encoding="utf-8") as d:
                json.dump({"v": 1, "podedovano_ob": 1.0, "naprave": {B: "dz", "n-%016x" % stevec[0]: "p"}}, d)
            os.replace(pot + ".drug", pot)
            return pravi(*a, **k)
        with mock.patch.object(link_dostop, "_na_disk", drug_program_vmes):
            self.assertFalse(link_dostop.nastavi(B, ""))
        self.assertEqual(stevec[0], link_dostop.NAJVEC_POSKUSOV_ZAPISA)
        with open(pot, encoding="utf-8") as d:
            self.assertEqual(json.load(d)["naprave"][B], "dz", "zapis drugega programa ostane")


class U14Zapis(_Osnova):
    def test_zaklep_ne_sledi_simbolni_povezavi(self):
        pot = link_dostop._pot()
        cilj = os.path.join(self._mapa.name, "drugje")
        os.symlink(cilj, pot + ".lock")
        self.assertTrue(link_dostop.nastavi(B, "p"))
        self.assertFalse(os.path.lexists(cilj), "podtaknjena povezava ne ustvari datoteke drugje")

    def test_nova_mapa_samo_za_lastnika(self):
        pot = os.path.join(self._mapa.name, "nova", "dostop.json")
        link_dostop._za_preizkus(pot)
        self.assertTrue(link_dostop.nastavi(B, "p"))
        self.assertEqual(os.stat(os.path.dirname(pot)).st_mode & 0o777, 0o700)

    @unittest.skipUnless(hasattr(os, "O_DIRECTORY"), "fsync mape samo na POSIX")
    def test_fsync_mape_po_zamenjavi(self):
        import stat as st
        mape = []
        pravi = os.fsync

        def fsync(fd):
            if st.S_ISDIR(os.fstat(fd).st_mode):
                mape.append(fd)
            return pravi(fd)
        with mock.patch.object(link_dostop.os, "fsync", fsync):
            self.assertTrue(link_dostop.nastavi(B, ""))
        self.assertTrue(mape, "po os.replace je na disku tudi mapa")


class U12Prosnje(_Osnova):
    clani = CLANI

    def setUp(self):
        super().setUp()
        p = mock.patch.object(link_dostop, "_id_iz_kljuca", lambda k: KLJUCI[k])
        p.start()
        self.addCleanup(p.stop)
        self.pokazano, self.umaknjeno = [], []
        link_dostop.nastavi_prikaz(self.pokazano.append, self.umaknjeno.append)

    def test_odvzem_pobrise_cakajoce_prosnje(self):
        """Prosnja, ki je cakala pred umikom, po umiku ne vrne dostopa s starim »Dovoli«."""
        link_dostop.nastavi(A, "dz")
        self.assertEqual(_vprasaj(A, "v")[0], "pending")
        link_dostop.nastavi(A, "")
        self.assertEqual(link_dostop.odprte_prosnje(), [])
        self.assertIn(A, self.umaknjeno, "obvestilo je umaknjeno")
        self.assertFalse(link_dostop.odobri_prosnjo(A, "v"))
        self.assertEqual(link_dostop.zmoznosti(A), set())


class U13Zeton(unittest.TestCase):
    def test_dejanje_brez_zetona_obvestila_ne_odobri(self):
        """Dejanje »Dovoli« je na vodilu seje dosegljivo vsakemu procesu: brez zetona obvestila ne naredi nicesar."""
        Gio, GLib = mock.MagicMock(), mock.MagicMock()
        dejanja = {}

        def nova(ime, tip):
            d = mock.Mock()
            d.connect.side_effect = lambda _sig, fn: dejanja.__setitem__(ime, fn)
            return d
        Gio.SimpleAction.new.side_effect = nova
        dovoli = mock.Mock()
        link_dostop.registriraj_dejanja(mock.Mock(), Gio, GLib, dovoli, mock.Mock(), mock.Mock())
        dejanja["dostop-dovoli"](None, A + "|dpvz")
        dovoli.assert_not_called()


class U5UmikIzKroga(_Osnova):
    def setUp(self):
        super().setUp()
        self.kljuc = base64.b64encode(b"\x30" + bytes(range(90))).decode("ascii")
        self.jedro = link_krog.id_iz_kljuca(self.kljuc)
        self.k = link_krog.Krog(None)
        for cilj, ime, vrednost in ((link_krog, "_krog", self.k), (link_krog.Krog, "_smo_mi", lambda s, i: False),
                                    (link_dostop, "_krog", lambda: self.k), (link_dostop, "_id_iz_kljuca",
                                                                             link_krog.id_iz_kljuca)):
            p = mock.patch.object(cilj, ime, vrednost)
            p.start()
            self.addCleanup(p.stop)
        self.assertTrue(self.k.dodaj(self.jedro, self.kljuc, "Telefon", "android", "n-0000000000000001",
                                     dodano=time.time() - 60))

    def test_umik_vzame_ozji_krog_in_nova_seznanitev_ga_ne_vrne(self):
        odvzeto = []

        def ob_odvzemu(j):
            odvzeto.append(j)
        link_dostop.ob_odvzemu(ob_odvzemu)
        self.assertTrue(link_dostop.nastavi_ozji_krog(self.jedro, "dpvz"))
        self.assertTrue(self.k.umakni(self.jedro, "n-0000000000000001"))
        self.assertEqual(link_dostop.zmoznosti(self.jedro), set())
        self.assertIn(self.jedro, odvzeto, "seja zaslona, zetoni in Teamwork se koncajo takoj")
        # Ponovna seznanitev z ISTIM kljucem: brez nove privolitve nic.
        self.assertTrue(self.k.dodaj(self.jedro, self.kljuc, "Telefon", "android", "n-0000000000000001"))
        self.assertTrue(self.k.je_clan(self.jedro))
        self.assertEqual(link_dostop.zmoznosti(self.jedro), set())


class _OdjemalecZaslona:
    def __init__(self, blokira_s=0.0):
        self.poslano, self.zaprto = [], threading.Event()
        self._blokira_s = blokira_s

    def sendall(self, podatki):
        if self._blokira_s:
            self.zaprto.wait(self._blokira_s)      # gledalec ne bere: pisanje caka (kot polna vrsta TLS)
        self.poslano.append(bytes(podatki))

    def shutdown(self, _kako):
        self.zaprto.set()

    def close(self):
        self.zaprto.set()


class U2U3Zaslon(_Osnova):
    def _seja(self, naprava, jedro=""):
        z = link_zaslon.Zaslon(vklopljeno=True)
        z._naprava, z._jedro, z._povezan, z._seja_st = naprava, jedro, True, 7
        z.ustavi = mock.Mock()
        return z

    def test_privzeta_preverba_je_link_dostop(self):
        """Zaslon brez nastavljenega `dostop` (vsaka pot, ki ga ustvari) preverja ozji krog - nikoli »dovoli«."""
        link_dostop.nastavi(A, "dz")
        z = self._seja(B)
        self.assertTrue(z.preveri_dostop(), "B nima upravljanja: seja se konca")
        z = self._seja(A)
        self.assertFalse(z.preveri_dostop())
        z.dostop = None
        z._naprava = B
        self.assertTrue(z.preveri_dostop(), "None ni »dovoli«")

    def test_straza_preverja_jedro_preverjenega_kljuca(self):
        """Seja iz zascitenega ukaza velja za jedro kljuca, ne za oznako »sender«."""
        link_dostop.nastavi(A, "dz")
        z = self._seja(A, jedro=B)
        self.assertTrue(z.preveri_dostop())

    def test_ukaz_z_oznako_drugega_jedra_zavrnjen(self):
        from core import safeer_link
        link_dostop.nastavi(A, "dz")
        link_dostop.nastavi(B, "dz")
        link = safeer_link.SafeerLink.__new__(safeer_link.SafeerLink)
        poslano = []
        link.povezava = mock.Mock()
        link.povezava.poslji = lambda s: poslano.append(s) or True
        link.control = True
        with mock.patch.object(safeer_link.GLib, "idle_add") as idle_add:
            link._prejmi_ukaz({"id": "u1", "type": "control.command", "sender": A, "_zascita": B,
                               "payload": {"action": "screen.start", "params": {}}})
            idle_add.assert_not_called()
        self.assertEqual(poslano[0]["payload"].get("code"), "ni_dovoljeno")

    def test_screen_start_veze_sejo_na_jedro(self):
        zaslon = mock.Mock()
        zaslon.na_voljo.return_value = {"dovoljeno": True, "mozno": True}
        zaslon.zacni.return_value = {"screen": "desktop"}
        link_daljinec.izvedi_control("screen.start", {}, lambda u: None, lambda i: None, zaslon=zaslon,
                                     posiljatelj=A, zascita=A)
        self.assertEqual(zaslon.zacni.call_args.kwargs.get("jedro"), A)


class U1Ponovno(_Osnova):
    def test_izvedba_na_glavni_niti_preveri_znova(self):
        """Dovoljenje se preveri na bralni niti; ce ga uporabnik vzame, preden se ukaz izvede, se ne izvede."""
        from core import safeer_link
        link_dostop.nastavi(B, "dz")
        link = safeer_link.SafeerLink.__new__(safeer_link.SafeerLink)
        poslano = []
        link.povezava = mock.Mock()
        link.povezava.poslji = lambda s: poslano.append(s) or True
        link.control = True
        with mock.patch.object(safeer_link.GLib, "idle_add") as idle_add:
            link._prejmi_ukaz({"id": "u1", "type": "control.command", "sender": B,
                               "payload": {"action": "screen.start", "params": {}}})
            izvedi = idle_add.call_args.args[0]
        link_dostop.nastavi(B, "")                       # uporabnik umakne napravo, ukaz caka v vrsti glavne zanke
        with mock.patch.object(link_daljinec, "izvedi_control") as izvedba:
            izvedi()
        izvedba.assert_not_called()
        self.assertEqual(poslano[-1]["payload"].get("code"), "ni_dovoljeno")

    def test_straza_preveri_takoj(self):
        z = link_zaslon.Zaslon(vklopljeno=True)
        z._naprava, z._povezan, z._seja_st = B, True, 3
        z.ustavi = mock.Mock()
        konec = threading.Event()
        with mock.patch.object(link_zaslon, "DOSTOP_PREVERI_S", 5.0):
            nit = threading.Thread(target=z._strazi_dostop, args=(3, konec), daemon=True)
            nit.start()
            nit.join(1.0)
        konec.set()
        self.assertFalse(nit.is_alive(), "prva preverba takoj, ne sele po DOSTOP_PREVERI_S")
        z.ustavi.assert_called_once()

    def test_gledalec_brez_dostopa_ne_dobi_niti_glave(self):
        """Seja caka gledalca; uporabnik medtem umakne napravo: ob povezavi gledalca se seja ne zacne."""
        z = link_zaslon.Zaslon(vklopljeno=True)
        z._naprava, z._seja_st = B, 9
        odjemalec = _OdjemalecZaslona()
        z._sprejmi = lambda posluh, ctx: (odjemalec, None)
        z._profil_seje = mock.Mock(side_effect=AssertionError("seja se je zacela brez dostopa"))
        z.ustavi = mock.Mock()
        z._streci(mock.Mock(), mock.Mock(), ["ffmpeg"], 9)
        z._profil_seje.assert_not_called()
        self.assertTrue(any(b'"dostop"' in p for p in odjemalec.poslano), "gledalec izve, zakaj ne")


class U10Umik(_Osnova):
    def test_umik_ne_caka_na_gledalca_ki_ne_bere(self):
        z = link_zaslon.Zaslon(vklopljeno=True)
        odjemalec = _OdjemalecZaslona(blokira_s=5.0)
        z._naprava, z._povezan, z._seja_st, z._odjemalec = B, True, 4, odjemalec
        zacetek = time.monotonic()
        self.assertTrue(z.preveri_dostop())
        self.assertLess(time.monotonic() - zacetek, 1.0, "klicatelj (glavna nit) ne caka na gledalca")
        self.assertIsNone(z._odjemalec, "seja (in z njo vnos) je ustavljena takoj")
        self.assertTrue(odjemalec.zaprto.wait(link_zaslon.OBVESTILO_ROK_S + 2.0), "povezava se zapre po roku")

    def test_vnos_po_ustavitvi_ne_gre_naprej(self):
        z = link_zaslon.Zaslon(vklopljeno=True)
        dogodki = (b'{"vrsta": "tipka", "tipka": "a"}\n{"vrsta": "tipka", "tipka": "b"}\n', b"")

        class Vticnica:
            def __init__(self):
                self.i = 0

            def recv(self, _n):
                self.i += 1
                return dogodki[min(self.i - 1, 1)]
        vticnica = Vticnica()
        z._odjemalec = vticnica

        def izvedi(_d):
            z._odjemalec = None          # odvzem dostopa med obdelavo prvega dogodka (ustavi)
            return True
        z._vnos = mock.Mock(izvedi=mock.Mock(side_effect=izvedi))
        z._plosek_dogodek = lambda d: False
        z._po_vnosu = mock.Mock()
        z._odpre_tipkovnico = lambda d: False
        z._fokus = lambda: None
        z._beri_vnos(vticnica)
        self.assertEqual(z._vnos.izvedi.call_count, 1, "drugi dogodek iz medpomnilnika ne gre v vnos")


class U15UstaviSamoLastnik(_Osnova):
    def test_screen_stop_tuje_seje_zavrnjen(self):
        link_dostop.nastavi(A, "dz")
        link_dostop.nastavi(B, "dz")
        z = link_zaslon.Zaslon(vklopljeno=True)
        z._naprava = A
        z.ustavi = mock.Mock()
        izidi = []
        link_daljinec.izvedi_control("screen.stop", {"close_apps": True}, lambda u: None, izidi.append, zaslon=z,
                                     posiljatelj=B)
        z.ustavi.assert_not_called()
        self.assertFalse(izidi[-1]["ok"])
        link_daljinec.izvedi_control("screen.stop", {}, lambda u: None, izidi.append, zaslon=z, posiljatelj=A + "-os")
        z.ustavi.assert_called_once()


class U9Tece(_Osnova):
    def test_odvzem_preklice_zetone_vseh_oznak_naprave_in_teamwork(self):
        mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, mapa, True)
        d = link_datoteke.Datoteke([mapa])
        z1, z2, z3 = d.streznik.zeton_za(B + "-os"), d.streznik.zeton_za(B), d.streznik.zeton_za(A)
        d.streznik.umaknjena = lambda n: False
        d.teamwork = mock.Mock()
        d.teamwork.odjavi_napravo.return_value = 1
        d.preklici_napravo(B)
        self.assertFalse(d.streznik.zeton_velja(z1))
        self.assertFalse(d.streznik.zeton_velja(z2))
        self.assertTrue(d.streznik.zeton_velja(z3), "druge naprave ostanejo")
        pripada = d.teamwork.odjavi_napravo.call_args.args[0]
        self.assertTrue(pripada(B + "-control"))
        self.assertFalse(pripada(A))

    def test_tekoci_prenos_se_prekine(self):
        mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, mapa, True)
        pot = os.path.join(mapa, "film.bin")
        with open(pot, "wb") as f:
            f.write(b"x" * (link_datoteke.VELIKOST_KOSA * 8))
        poslano = []
        obravnava = mock.Mock(headers={}, wfile=mock.Mock(write=lambda b: poslano.append(len(b))))
        klici = []
        with mock.patch.object(link_datoteke, "PREVERI_MED_POSILJANJEM_S", 0.0):
            link_datoteke._poslji_datoteko(obravnava, pot, False, se_velja=lambda: klici.append(1) or len(klici) < 2)
        self.assertLess(sum(poslano), link_datoteke.VELIKOST_KOSA * 8, "prenos se konca ob odvzemu")
        self.assertTrue(obravnava.close_connection)

    def test_teamwork_odjavi_napravo(self):
        from core import link_teamwork
        mapa = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, mapa, True)
        tw = link_teamwork.Teamwork(lambda o: "", lambda i: i, mock.Mock(), mock.Mock(), lambda: [], mapa=mapa,
                                    procesi=lambda: set())
        s = link_teamwork._Seja("x", os.path.join(mapa, "a.txt"))
        zdaj = time.time()
        s.udelezenci = {B + "-os": {"ime": "B", "odprto": True, "cas": zdaj}, A: {"ime": "A", "odprto": True, "cas": zdaj}}
        tw._seje["x"] = s
        self.assertEqual(tw.odjavi_napravo(lambda i: i.startswith(B)), 1)
        self.assertEqual(list(s.udelezenci), [A])

    def test_safeer_link_ob_odvzemu_konca_kar_tece(self):
        from core import safeer_link
        link = safeer_link.SafeerLink.__new__(safeer_link.SafeerLink)
        link.zaslon, link.datoteke = mock.Mock(), mock.Mock()
        link._v_ozadju = lambda f: f()
        link_dostop.ob_odvzemu(link._ob_odvzemu_dostopa)
        link_dostop.nastavi(B, "dz")
        with mock.patch.object(safeer_link.GLib, "idle_add"):
            link_dostop.nastavi(B, "")
        link.zaslon.preveri_dostop.assert_called()
        link.datoteke.preklici_napravo.assert_called_with(B)


class U7Okno(unittest.TestCase):
    def test_okno_pokaze_napako_in_dejansko_stanje(self):
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(koren, "assets", "link", "link.js"), encoding="utf-8") as d:
            js = d.read()
        self.assertEqual(js.count('dostopNapaka: "'), 6, "besedilo v vseh 6 jezikih")
        self.assertIn('!podatki.ok ? t("dostopNapaka")', js)


if __name__ == "__main__":
    unittest.main()
