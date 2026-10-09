"""Safeer Player: Medijski center v svojem oknu (safeer_os.py --predvajalnik).

Lastnik, 9. 10. 2026 (posnetek z Linux Minta, tema Safeer Cinnamon): gumb »Odpri Medijski center« na delovni povrsini je
odprl celo lupino Safeer OS. Pricakoval je Medijski center v nasem programu Safeer Player - svoje okno, svoja ikona v
pultu, brez stranske vrstice Safeer OS - z isto kodo (stran assets/os, most, predvajalnik, katalog, Safeer Link) v
istem procesu. Glavno okno Safeer OS in njegov Medijski center ostaneta, kot sta bila.
"""
import configparser
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from core import os_katalog, os_programi

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class _Lupina(unittest.TestCase):
    def setUp(self):
        import safeer_os
        self.os_ = safeer_os
        self.SafeerOS = safeer_os.SafeerOS


class Usmerjanje(_Lupina):
    """Delovna povrsina klice »odpriRazdelek«: Medijski center gre v Safeer Player, vse drugo kot prej."""

    def test_kateri_razdelki_so_medijski_center(self):
        f = self.os_.razdelek_predvajalnika
        self.assertEqual(f("media"), "")
        self.assertEqual(f("mediji:jazz"), "jazz")
        self.assertEqual(f("mediji:  Pink Floyd "), "Pink Floyd")
        self.assertEqual(f("mediji:"), "")
        for drugo in ("", None, "domov", "naprave", "nastavitve", "nastavitve#blokScit", "zapisek:42", "splet",
                      "sporocila", "zapiski", "medijix", "Media"):
            self.assertIsNone(f(drugo), drugo)

    def _lazna(self, okno=True):
        lazna = mock.MagicMock()
        lazna.okno = mock.MagicMock() if okno else None
        return lazna

    def test_media_odpre_safeer_player_ne_glavnega_okna(self):
        for razdelek, iskanje in (("media", ""), ("mediji:jazz", "jazz")):
            for okno in (True, False):
                lazna = self._lazna(okno)
                with mock.patch.object(self.os_, "GLib") as glib:
                    self.SafeerOS._odpri_razdelek(lazna, razdelek)
                lazna._odpri_predvajalnik.assert_called_once_with(iskanje)
                lazna._ustvari_okno.assert_not_called()
                lazna._domov.assert_not_called()
                glib.timeout_add.assert_not_called()

    def test_drugi_razdelki_ostanejo_v_glavnem_oknu(self):
        for razdelek in ("naprave", "nastavitve#blokScit", "zapisek:42", "sporocila", "splet"):
            lazna = self._lazna(okno=True)
            self.SafeerOS._odpri_razdelek(lazna, razdelek)
            lazna._domov.assert_called_once_with(razdelek)
            lazna._odpri_predvajalnik.assert_not_called()
            lazna = self._lazna(okno=False)
            with mock.patch.object(self.os_, "GLib") as glib:
                self.assertTrue(self.SafeerOS._odpri_razdelek(lazna, razdelek))
            lazna._ustvari_okno.assert_called_once_with()
            glib.timeout_add.assert_called_once()
            lazna._odpri_predvajalnik.assert_not_called()

    def test_delovna_povrsina_klice_isto_metodo(self):
        """Gumb in iskanje na delovni povrsini ostaneta pri »odpriRazdelek« - usmeri jih safeer_os.py, zato se tudi
        starejsa stran (ali drug klicatelj) z »media« znajde v Safeer Playerju."""
        js = beri("assets", "os", "delovna.js")
        self.assertIn('$("gumbMedijskiCenter").addEventListener("click", function () { klic("odpriRazdelek", ["media"])', js)
        self.assertIn('else if (v.vrsta === "mediji") klic("odpriRazdelek", ["mediji:" + v.q]);', js)
        self.assertIn('pod = t(v.cilj === "media" ? "odprePredvajalnik" : "odpreSafeerOs");', js)
        self.assertEqual(js.count('odprePredvajalnik: "'), 2, "napis v obeh jezikih delovne povrsine")
        self.assertIn('"odpriRazdelek": lambda: self._odpri_razdelek(', beri("safeer_os.py"))


class Zastavica(_Lupina):
    """`safeer-os --predvajalnik` (meni »Safeer Player«): v tekocem Safeer OS odpre okno, sicer zazene Safeer Player."""

    def test_branje_zastavice(self):
        f = self.os_.zagon_predvajalnika
        for da in (["--predvajalnik"], ["--player"], ["--okno", "--predvajalnik"], ["--predvajalnik", "--posnetek", "x.png"]):
            self.assertTrue(f(da), da)
        for ne in ([], None, ["--okno"], ["--delovna"], ["--predvajaj", "/tmp/film.mkv"], ["--predvajalnik=1"], ["predvajalnik"]):
            self.assertFalse(f(ne), ne)
        self.assertNotIn("--predvajaj", self.os_.ZASTAVICE_PREDVAJALNIKA, "--predvajaj <datoteka> ostane, kar je bil")

    def _main(self, argv, predaja=False, **kwargs):
        """main() brez zaslona in brez sledi v uporabnikovem profilu: zagon programa je lazen."""
        with mock.patch.object(self.os_.sys, "argv", ["safeer_os.py"] + argv), \
                mock.patch.object(self.os_, "_predaj_tekocemu", **({"side_effect": predaja} if isinstance(predaja, Exception)
                                                                  else {"return_value": predaja})) as predaj, \
                mock.patch.object(self.os_, "SafeerOS") as razred, \
                mock.patch.object(self.os_, "os_stabilnost") as stabilnost, \
                mock.patch.object(self.os_, "popravi_po_sesutju", return_value=False), \
                mock.patch.object(self.os_.os_programi, "Shramba"), \
                mock.patch.object(self.os_.GLib, "timeout_add_seconds"), \
                mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": tempfile.gettempdir() + "/ni-safeer-cinnamon"}):
            stabilnost.naj_bo_varni_nacin.return_value = False
            razred.return_value.run.return_value = 0
            koda = self.os_.main()
        return koda, predaj, razred, stabilnost

    def test_tekoci_safeer_os_odpre_okno_in_proces_konca(self):
        for zastavica in ("--predvajalnik", "--player"):
            koda, predaj, razred, stabilnost = self._main([zastavica], predaja=True)
            self.assertEqual(koda, 0)
            predaj.assert_called_once_with("predvajalnik", "")
            razred.assert_not_called()
            # Brez popravkov po sesutju in sledi: to sodi samo k pravemu zagonu.
            stabilnost.vkljuci.assert_not_called()

    def test_brez_tekocega_se_zazene_safeer_player_v_oknu(self):
        for predaja in (False, OSError("ni seje D-Bus")):
            koda, predaj, razred, _ = self._main(["--predvajalnik"], predaja=predaja)
            self.assertEqual(koda, 0)
            razred.assert_called_once()
            argumenti = razred.call_args.kwargs
            self.assertTrue(argumenti["predvajalnik"])
            self.assertTrue(argumenti["v_oknu"], "Safeer OS iz menija se v tem procesu odpre kot okno, ne kot namizje")
            self.assertFalse(argumenti["delovna"])
            razred.return_value.run.assert_called_once()

    def test_posnetek_ne_preda_tekocemu(self):
        koda, predaj, razred, _ = self._main(["--predvajalnik", "--posnetek", "/tmp/ni.png"], predaja=True)
        predaj.assert_not_called()
        self.assertEqual(razred.call_args.kwargs["posnetek"], "/tmp/ni.png")
        self.assertTrue(razred.call_args.kwargs["predvajalnik"])

    def test_brez_zastavice_je_zagon_kot_prej(self):
        koda, predaj, razred, _ = self._main(["--okno"])
        predaj.assert_not_called()
        self.assertFalse(razred.call_args.kwargs["predvajalnik"])
        self.assertTrue(razred.call_args.kwargs["v_oknu"])
        koda, predaj, razred, _ = self._main([])
        self.assertFalse(razred.call_args.kwargs["predvajalnik"])
        self.assertFalse(razred.call_args.kwargs["v_oknu"], "brez zastavic ostane celozaslonski Safeer OS")

    def test_predvajaj_in_magnet_se_vedno_predata(self):
        """Predaja tekocemu je zdaj ena funkcija za vse tri zastavice; --predvajaj in --magnet morata ostati enaka."""
        with tempfile.NamedTemporaryFile(suffix=".mp3") as d:
            koda, predaj, razred, _ = self._main(["--predvajaj", d.name], predaja=True)
            self.assertEqual(koda, 0)
            predaj.assert_called_once_with("predvajaj", os.path.realpath(d.name))
        magnet = "magnet:?xt=urn:btih:" + "a" * 40
        koda, predaj, _, _ = self._main(["--magnet", magnet], predaja=True)
        predaj.assert_called_once_with("magnet", magnet)
        koda, predaj, _, _ = self._main(["--magnet-naprava", magnet], predaja=True)
        predaj.assert_called_once_with("magnet", "naprava:" + magnet)

    def test_dejanje_v_tekocem_procesu(self):
        """Drugi zagon se z delujocim Safeer OS pogovori po D-Bus (org.gtk.Actions) - dejanje »predvajalnik« obstaja."""
        vir = beri("safeer_os.py")
        self.assertIn('Gio.SimpleAction.new("predvajalnik", GLib.VariantType.new("s"))', vir)
        self.assertIn('lambda _a, v: self._odpri_predvajalnik(v.get_string() if v else "")', vir)
        vodilo = mock.MagicMock()
        vodilo.call_sync.return_value.unpack.return_value = (True,)
        with mock.patch.object(self.os_.Gio, "bus_get_sync", return_value=vodilo):
            self.assertTrue(self.os_._predaj_tekocemu("predvajalnik", ""))
        klic = vodilo.call_sync.call_args_list[-1].args
        self.assertEqual(klic[:4], (self.os_.APP_ID, "/io/github/memelandfaner/SafeerOS", "org.gtk.Actions", "Activate"))
        self.assertEqual(klic[4].unpack(), ("predvajalnik", [""], {}))
        vodilo.call_sync.reset_mock()
        vodilo.call_sync.return_value.unpack.return_value = (False,)
        with mock.patch.object(self.os_.Gio, "bus_get_sync", return_value=vodilo):
            self.assertFalse(self.os_._predaj_tekocemu("predvajalnik", ""))
        self.assertEqual(vodilo.call_sync.call_count, 1, "ce Safeer OS ne tece, se dejanje ne posilja")


class Zagon(_Lupina):
    """Prva aktivacija procesa: --predvajalnik odpre samo Safeer Player, sicer je vse kot prej."""

    def _odpri(self, **polja):
        lazni = mock.Mock()
        lazni.delovna, lazni.okno, lazni.okno_delovna, lazni.namizje = False, None, None, False
        lazni._cakajoca_datoteka, lazni._cakajoca_ponudba = "", None
        lazni._prvic, lazni.posnetek, lazni._zacni_s_predvajalnikom = True, "", False
        for ime, vrednost in polja.items():
            setattr(lazni, ime, vrednost)
        with mock.patch.object(self.os_, "GLib"), mock.patch.object(self.os_, "Gio"), \
                mock.patch.object(self.os_, "uredi_samozagon_ob_zagonu"), mock.patch.object(self.os_, "skrij_mintov_pult"):
            self.SafeerOS.do_activate(lazni)
        return lazni

    def test_zagon_s_predvajalnikom(self):
        lazni = self._odpri(_zacni_s_predvajalnikom=True)
        lazni._odpri_predvajalnik.assert_called_once_with()
        lazni._ustvari_okno.assert_not_called()
        lazni._ustvari_vrstico.assert_not_called()
        lazni._povezi_koncanje.assert_called_once_with()          # odjava (SIGTERM) pospravi tudi za Safeer Playerjem
        lazni.scit.zacni_ce_vklopljen.assert_not_called()         # Scit in zagon ob prijavi sodita k lupini
        self.assertFalse(lazni._zacni_s_predvajalnikom, "naslednja aktivacija (meni Safeer OS) odpre glavno okno")

    def test_glavno_okno_kot_prej(self):
        lazni = self._odpri()
        lazni._ustvari_okno.assert_called_once_with()
        lazni._odpri_predvajalnik.assert_not_called()
        lazni.scit.zacni_ce_vklopljen.assert_called_once_with()
        lazni = self._odpri(okno=mock.Mock())
        lazni._domov.assert_called_once_with()
        lazni._odpri_predvajalnik.assert_not_called()

    def test_delovna_povrsina_kot_prej(self):
        lazni = self._odpri(delovna=True, _zacni_s_predvajalnikom=True)
        lazni._ustvari_delovno.assert_called_once_with()
        lazni._odpri_predvajalnik.assert_not_called()

    def test_koncanje_se_poveze_enkrat(self):
        lazni = mock.Mock(spec=["add_action", "_koncaj"])
        with mock.patch.object(self.os_, "GLib") as glib, mock.patch.object(self.os_, "Gio"):
            self.SafeerOS._povezi_koncanje(lazni)
            self.SafeerOS._povezi_koncanje(lazni)
        self.assertEqual(lazni.add_action.call_count, 1)
        self.assertEqual(sorted(k.args[1] for k in glib.unix_signal_add.call_args_list), [1, 2, 15])


class Okno(_Lupina):
    """Okno Safeer Player: odpiranje, zapiranje in okna, ki jih odpre."""

    def test_okno_je_svoje_v_pultu(self):
        vir = beri("safeer_os.py")
        telo = vir[vir.index("def _ustvari_predvajalnik"):vir.index("def _ikona_predvajalnika")]
        self.assertIn('Gtk.ApplicationWindow(application=self, title="Safeer Player")', telo)
        self.assertIn("okno.set_wmclass(*WMCLASS_PREDVAJALNIKA)", telo)
        self.assertIn('("predvajalnik", "1")', telo)
        self.assertIn('okno.connect("delete-event", self._zapri_predvajalnik)', telo)
        self.assertEqual(self.os_.WMCLASS_PREDVAJALNIKA, ("safeer-player", "Safeer Player"))
        # Glavno okno ostane, kot je bilo: ista stran, isto ime za upravitelja oken.
        glavno = vir[vir.index("def _ustvari_okno"):vir.index("def _ustvari_vrstico")]
        self.assertIn('self._nov_pogled("index.html" + ("?namizje=1" if self.namizje else ""))', glavno)
        self.assertIn('okno.set_wmclass("safeer-os", "Safeer OS")', glavno)
        self.assertTrue(os.path.isfile(os.path.join(KOREN, "assets", "os", "predvajalnik.svg")))
        # Okno z videom (domaci predvajalnik) je v pultu v skupini Safeer Player.
        video = vir[vir.index('okno = Gtk.Window(title="Safeer Player")'):vir.index('okno.get_style_context().add_class("safeer-player")')]
        self.assertIn("okno.set_wmclass(*WMCLASS_PREDVAJALNIKA)", video)

    def test_prvo_odprtje_ustvari_okno_z_iskanjem(self):
        lazna = mock.MagicMock()
        lazna.okno_predvajalnik = None
        self.assertTrue(self.SafeerOS._odpri_predvajalnik(lazna, " jazz "))
        lazna._ustvari_predvajalnik.assert_called_once_with("jazz")
        lazna._js.assert_not_called()

    def test_odprto_okno_pride_v_ospredje_z_iskanjem_samo_v_svoji_strani(self):
        lazna = mock.MagicMock()
        with mock.patch.object(self.os_, "Gtk") as gtk, mock.patch.object(self.os_, "GLib"):
            gtk.get_current_event_time.return_value = 1234
            self.SafeerOS._odpri_predvajalnik(lazna, "Pink Floyd")
        lazna._ustvari_predvajalnik.assert_not_called()
        lazna.okno_predvajalnik.deiconify.assert_called_once_with()
        lazna.okno_predvajalnik.present_with_time.assert_called_once_with(1234)
        koda, pogled = lazna._js.call_args.args
        self.assertIs(pogled, lazna.pogled_predvajalnik, "glavno okno ne sme dobiti ukaza za Safeer Player")
        self.assertIn(json.dumps("mediji:Pink Floyd"), koda)
        lazna = mock.MagicMock()
        with mock.patch.object(self.os_, "Gtk"), mock.patch.object(self.os_, "GLib"):
            self.SafeerOS._odpri_predvajalnik(lazna, "")
        lazna._js.assert_not_called()
        lazna.okno_predvajalnik.present_with_time.assert_called_once()

    def test_zapiranje(self):
        for delovna, glavno in ((True, None), (None, True), (True, True)):
            lazna = mock.MagicMock()
            lazna.okno_delovna = mock.Mock() if delovna else None
            lazna.okno = mock.Mock() if glavno else None
            okno = mock.Mock()
            self.assertTrue(self.SafeerOS._zapri_predvajalnik(lazna, okno, None))
            okno.hide.assert_called_once_with()        # predvajanje in vrsta skladb tecejo naprej
            lazna._koncaj.assert_not_called()
        lazna = mock.MagicMock()
        lazna.okno_delovna = lazna.okno = None
        okno = mock.Mock()
        self.assertTrue(self.SafeerOS._zapri_predvajalnik(lazna, okno, None))
        lazna._koncaj.assert_called_once_with()         # samostojni Safeer Player se zapre kot vsak predvajalnik
        okno.hide.assert_not_called()

    def test_sistemska_okna_nad_safeer_playerjem(self):
        lazna = mock.MagicMock()
        self.assertIs(self.SafeerOS._okno_klica(lazna, lazna.pogled_predvajalnik), lazna.okno_predvajalnik)
        self.assertIsNone(self.SafeerOS._okno_klica(lazna, lazna.pogled))
        self.assertIsNone(self.SafeerOS._okno_klica(lazna, None))
        lazna.pogled_predvajalnik = None
        self.assertIsNone(self.SafeerOS._okno_klica(lazna, None))


class Most(_Lupina):
    """Ista stran je lahko odprta dvakrat (glavno okno in Safeer Player); most mora vedeti, kdo klice."""

    def _lazna(self):
        lazna = mock.MagicMock()
        lazna.pogled, lazna.pogled_predvajalnik = mock.Mock(name="glavni"), mock.Mock(name="predvajalnik")
        lazna._okno_klica = lambda p: self.SafeerOS._okno_klica(lazna, p)
        lazna._katalog_most.return_value.pozna.side_effect = lambda m: m in os_katalog.Katalog.METODE
        lazna._katalog_pogled = None
        lazna.SPREMINJAJO_DATOTEKE = self.SafeerOS.SPREMINJAJO_DATOTEKE
        return lazna

    def _klic(self, lazna, pogled, metoda, argumenti=()):
        rezultat = mock.Mock()
        rezultat.get_js_value.return_value.to_string.return_value = json.dumps({"id": 7, "m": metoda, "a": list(argumenti)})
        self.SafeerOS._na_sporocilo(lazna, pogled, rezultat)

    def test_razdelek_velja_samo_za_glavno_okno(self):
        lazna = self._lazna()
        self._klic(lazna, lazna.pogled, "razdelek", ["media"])
        lazna._razdelek.assert_called_once_with("media")
        lazna = self._lazna()
        self._klic(lazna, lazna.pogled_predvajalnik, "razdelek", ["media"])
        lazna._razdelek.assert_not_called()       # sicer bi Safeer Player skril Splet v glavnem oknu
        lazna._odgovori.assert_called_once_with(lazna.pogled_predvajalnik, 7, True, True)

    def test_izbira_datotek_nad_oknom_klica(self):
        for metoda, ime in (("lokalniMediji", "_medijski_dodaj_datoteke"), ("medijskaMapa", "_medijski_dodaj_mapo"),
                            ("medijskiTok", "_medijski_dodaj_tok")):
            lazna = self._lazna()
            self._klic(lazna, lazna.pogled_predvajalnik, metoda)
            getattr(lazna, ime).assert_called_once_with(lazna.okno_predvajalnik)
            lazna = self._lazna()
            self._klic(lazna, lazna.pogled, metoda)
            getattr(lazna, ime).assert_called_once_with(None)        # glavno okno: kot prej
        lazna = self._lazna()
        self._klic(lazna, lazna.pogled_predvajalnik, "magnetIzDatoteke", [True])
        lazna._magnet_iz_datoteke.assert_called_once_with(True, lazna.okno_predvajalnik)

    def test_lastnik_vrste_skladb(self):
        lazna = self._lazna()
        koncano = threading.Event()
        lazna._katalog_most.return_value.izvedi.side_effect = lambda *a: koncano.set() or {"ok": True}
        self._klic(lazna, lazna.pogled_predvajalnik, "mediaPredvajaj", ["id-1"])
        self.assertTrue(koncano.wait(5))
        self.assertIs(lazna._katalog_pogled, lazna.pogled_predvajalnik)
        self._klic(lazna, lazna.pogled, "mediaSeznami")              # branje kataloga lastnika ne zamenja
        self.assertIs(lazna._katalog_pogled, lazna.pogled_predvajalnik)

    def _dogodek(self, lazna, vrsta):
        with mock.patch.object(self.os_.GLib, "idle_add", side_effect=lambda f: f()):
            self.SafeerOS._dogodek(lazna, vrsta, {"id": "x"})
        return lazna._js.call_args.args[1]

    def test_dogodki_vrste_gredo_samo_lastniku(self):
        lazna = mock.MagicMock()
        glavni, predvajalnik, delovna = mock.Mock(), mock.Mock(), mock.Mock()
        lazna.pogledi = [glavni, delovna, predvajalnik]
        lazna.DOGODKI_VRSTE = self.SafeerOS.DOGODKI_VRSTE
        lazna._katalog_pogled = predvajalnik
        for vrsta in ("mediaKonec", "mediaVrstaUkaz", "mediaYt", "mediaYtZaprt", "mediaYtNapaka"):
            self.assertIs(self._dogodek(lazna, vrsta), predvajalnik, vrsta)
        for vrsta in ("predvajalnik", "medijskaKnjiznica", "mediaKatalogOsvezen", "pojdi", "fokus", "magnet"):
            self.assertIsNone(self._dogodek(lazna, vrsta), vrsta)        # vsem stranem, kot prej
        lazna._katalog_pogled = None
        self.assertIsNone(self._dogodek(lazna, "mediaKonec"))
        lazna._katalog_pogled = mock.Mock()                              # pogleda ni vec
        self.assertIsNone(self._dogodek(lazna, "mediaKonec"))

    def test_splet_brez_glavnega_okna_v_privzetem_brskalniku(self):
        for okno in (None, mock.Mock(**{"get_visible.return_value": False})):
            lazna = mock.MagicMock()
            lazna.okno = okno
            lazna._odpri_v_brskalniku.return_value = True
            self.assertTrue(self.SafeerOS._splet(lazna, "https://365.rtvslo.si/"))
            lazna._odpri_v_brskalniku.assert_called_once_with("https://365.rtvslo.si/")
            lazna._pokazi_spletni_nacin.assert_not_called()
            lazna._odpri_v_brskalniku.reset_mock()
            self.assertFalse(self.SafeerOS._splet(lazna, ""))
            self.assertFalse(self.SafeerOS._splet(lazna, "javascript:alert(1)"))
            lazna._odpri_v_brskalniku.assert_not_called()
        lazna = mock.MagicMock()
        lazna.okno.is_active.return_value = False
        self.SafeerOS._splet(lazna, "https://example.org/")
        lazna.okno.present.assert_called_once_with()                  # glavno okno z vgrajenim Spletom pride naprej
        lazna._spletni.odpri.assert_called_once_with("https://example.org/")
        lazna._odpri_v_brskalniku.assert_not_called()


class Stran(unittest.TestCase):
    """index.html?predvajalnik=1: ista stran, samo Medijski center, brez lupine Safeer OS."""

    def setUp(self):
        self.js = beri("assets", "os", "os.js")
        self.css = beri("assets", "os", "os.css")

    def test_nacin_iz_naslova(self):
        self.assertIn("var PREDVAJALNIK = /[?&]predvajalnik=1(&|$)/.test(location.search);", self.js)
        self.assertIn('document.body.classList.add("predvajalnik");', self.js)
        self.assertIn('window.safeerOsPojdi(niz ? "mediji:" + niz : "media");', self.js)
        # Jezik iz naslova: Medijski center se pokaze takoj, katalog se nalozi enkrat.
        self.assertIn("if (jezikStrani && BESEDILA_OS[jezikStrani]) jezik = jezikStrani;", self.js)
        self.assertIn('("jezik", _jezik())', beri("safeer_os.py"))

    def test_lupina_je_skrita(self):
        for izbirnik in ("body.predvajalnik #stranska", "body.predvajalnik #vrh", "body.predvajalnik #noga",
                         "body.predvajalnik .rocaj-vrstice", "body.predvajalnik .razdelek:not(#r-media)"):
            self.assertIn(izbirnik, self.css)
        self.assertIn("body.predvajalnik #aplikacija { display: flex; }", self.css)
        # Zapomnjena skrcena/skrita vrstica glavnega okna (localStorage) ne sme v Safeer Player in obratno.
        self.assertIn("if (!gumb || PREDVAJALNIK) return;", self.js)
        self.assertIn("  if (!PREDVAJALNIK) {\n    try { if (localStorage.getItem(\"safeer_vrstica_skrcena\")", self.js)

    def test_drugi_razdelki_gredo_v_glavno_okno(self):
        self.assertIn('if (PREDVAJALNIK && razdelek !== "media") {\n'
                      '      // Drugi razdelki niso del Safeer Playerja: odpre jih glavno okno Safeer OS (enako kot z delovne povrsine).\n'
                      '      klic("odpriRazdelek", [razdelek]).catch(function () {});', self.js)
        self.assertIn('if (PREDVAJALNIK && kam !== "media" && kam.indexOf("mediji:") !== 0) return;', self.js)

    def test_dogodki_glavnega_okna_ne_vplivajo(self):
        dogodki = self.js[self.js.index("window.safeerOsDogodek = function (vrsta, podatki) {"):]
        self.assertIn('if (vrsta === "magnet" && !PREDVAJALNIK) odpriMagnet(', dogodki)
        self.assertLess(dogodki.index("if (PREDVAJALNIK) return;"), dogodki.index('if (vrsta === "pojdi") window.safeerOsPojdi(podatki);'))
        self.assertLess(dogodki.index("if (PREDVAJALNIK) return;"), dogodki.index('if (vrsta === "fokus") {'))
        # Predvajanje (stanje, knjiznica, katalog) dobi tudi Safeer Player - te so pred izhodom.
        for vrsta in ('katDogodek(vrsta, podatki);', 'if (vrsta === "predvajalnik") osveziPredvajalnik(podatki);',
                      'if (vrsta === "medijskaKnjiznica") naloziMedije();'):
            self.assertLess(dogodki.index(vrsta), dogodki.index("if (PREDVAJALNIK) return;"), vrsta)
        self.assertIn("if (!PREDVAJALNIK)      // cakajoci magnet", self.js)

    def test_tipkovnica_in_splet(self):
        self.assertIn('else if (!PREDVAJALNIK) pojdi("domov");', self.js)
        self.assertIn('var polje = PREDVAJALNIK ? $("mediaIskanje") : iskanje;', self.js)
        splet = self.js[self.js.index("function odpriVSpletu("):self.js.index("function odpriSplet(")]
        self.assertIn('return klic("odpriVBrskalniku", [naslov])', splet)
        self.assertIn('"odpriVBrskalniku": lambda: self._odpri_v_brskalniku(', beri("safeer_os.py"))

    def test_splet_iz_safeer_playerja_v_privzetem_brskalniku(self):
        """Ista funkcija strani: v glavnem oknu vgrajeni Splet (kot prej), v Safeer Playerju privzeti brskalnik."""
        if not shutil.which("node"):
            self.skipTest("ni node")
        splet = self.js[self.js.index("  var brezPeskovnikaOb = 0;"):self.js.index("  function odpriSplet(naslov, ime)")]
        koda = r"""
var assert = require("assert");
var klici = [], obvestila = [], izidi = {}, PREDVAJALNIK = false;
function t(k) { return k; }
function obvesti(b) { obvestila.push(b); }
function klic(m, a) { klici.push([m, a]); return m in izidi ? Promise.resolve(izidi[m]) : Promise.resolve(true); }
""" + splet + r"""
(async function () {
  assert.strictEqual(await odpriVSpletu("https://365.rtvslo.si/"), true);
  assert.deepStrictEqual(klici.pop(), ["splet", ["https://365.rtvslo.si/"]]);
  PREDVAJALNIK = true;
  assert.strictEqual(await odpriVSpletu("https://365.rtvslo.si/"), true);
  assert.deepStrictEqual(klici.pop(), ["odpriVBrskalniku", ["https://365.rtvslo.si/"]]);
  assert.deepStrictEqual(klici, []);
  izidi.odpriVBrskalniku = false;
  assert.strictEqual(await odpriVSpletu("https://365.rtvslo.si/"), false);
  assert.deepStrictEqual(obvestila, ["niUspelo"]);
})().catch(function (e) { console.error(e); process.exit(1); });
"""
        subprocess.run(["node", "-e", koda], check=True, timeout=60)

    def test_skladnja(self):
        if not shutil.which("node"):
            self.skipTest("ni node")
        for ime in ("os.js", "delovna.js"):
            subprocess.run(["node", "--check", os.path.join(KOREN, "assets", "os", ime)], check=True)


class Paket(unittest.TestCase):
    """Vnos »Safeer Player« v meniju (Linux Mint): v paketu safeer-os, veljaven, z ujemajocim WM_CLASS."""

    def _namesti(self, mapa, *id_):
        prefix = Path(mapa) / "usr"
        subprocess.run(["bash", os.path.join(KOREN, "packaging", "install_os_payload.sh"), str(prefix), *id_],
                       check=True, capture_output=True)
        return prefix

    def _vnos(self, pot):
        razclen = configparser.RawConfigParser(strict=True)
        razclen.optionxform = str
        razclen.read(pot, encoding="utf-8")
        return razclen["Desktop Entry"]

    def test_vnos_v_meniju(self):
        import safeer_os
        with tempfile.TemporaryDirectory() as mapa:
            prefix = self._namesti(mapa)
            pot = prefix / "share/applications/safeer-os.Player.desktop"
            self.assertTrue(pot.is_file())
            if shutil.which("desktop-file-validate"):
                subprocess.run(["desktop-file-validate", str(pot)], check=True)
            v = self._vnos(pot)
            self.assertEqual(v["Name"], "Safeer Player")
            self.assertEqual(v["Name[sl]"], "Safeer Player")
            self.assertEqual(v["Exec"].split(), ["safeer-os", "--predvajalnik"])
            self.assertEqual(v["StartupWMClass"], safeer_os.WMCLASS_PREDVAJALNIKA[0])
            self.assertEqual(v["Categories"], "AudioVideo;Player;")
            self.assertNotEqual(v.get("NoDisplay", "false"), "true")
            self.assertEqual(v["Icon"], "safeer-os.Player")
            self.assertTrue((prefix / "share/icons/hicolor/scalable/apps/safeer-os.Player.svg").is_file())
            # Glavni vnos Safeer OS ostane, kot je bil.
            glavni = self._vnos(prefix / "share/applications/safeer-os.desktop")
            self.assertEqual((glavni["Exec"], glavni["StartupWMClass"]), ("safeer-os --okno", "safeer-os"))
            self.assertTrue((prefix / "lib/safeer-os/assets/os/predvajalnik.svg").is_file())

    def test_flatpak_izvozi_samo_imena_z_id(self):
        app_id = "io.github.memelandfaner.SafeerOS"
        with tempfile.TemporaryDirectory() as mapa:
            prefix = self._namesti(mapa, app_id)
            vnosi = sorted(p.name for p in (prefix / "share/applications").iterdir())
            self.assertIn(app_id + ".Player.desktop", vnosi)
            for ime in vnosi:
                self.assertTrue(ime.startswith(app_id), ime)
            ikone = [p.name for p in (prefix / "share/icons").rglob("*.svg")]
            self.assertIn(app_id + ".Player.svg", ikone)
            for ime in ikone:
                self.assertTrue(ime.startswith(app_id), ime)
            self.assertEqual(self._vnos(prefix / "share/applications" / (app_id + ".Player.desktop"))["Icon"],
                             app_id + ".Player")

    def test_deb_pot_do_ukaza(self):
        deb = beri("build_os_deb.sh")
        self.assertIn('"$BUILD_ROOT/usr/share/applications/safeer-os.Player.desktop"', deb)
        self.assertIn("desktop-file-validate /usr/share/applications/safeer-os.Player.desktop",
                      beri(".github", "workflows", "linux-packages.yml"))

    def test_safeer_os_ne_ponuja_sebe(self):
        """Safeer Player je Medijski center Safeer OS: med Programi in viri Medijskega centra ga ni (kot Safeer OS)."""
        with tempfile.TemporaryDirectory() as mapa:
            aplikacije = os.path.join(mapa, "applications")
            os.makedirs(aplikacije)
            shutil.copy(os.path.join(KOREN, "packaging", "safeer-player.desktop"),
                        os.path.join(aplikacije, "safeer-os.Player.desktop"))
            shutil.copy(os.path.join(KOREN, "packaging", "safeer-player.desktop"),
                        os.path.join(aplikacije, "io.github.memelandfaner.SafeerOS.Player.desktop"))
            with open(os.path.join(aplikacije, "vlc.desktop"), "w", encoding="utf-8") as f:
                f.write("[Desktop Entry]\nType=Application\nName=VLC\nExec=vlc\nCategories=AudioVideo;Player;\n")
            programi = os_programi.Programi(os_programi.Shramba(os.path.join(mapa, "os.json")), mape=[aplikacije],
                                            namizja=["X-Cinnamon"])
            self.assertEqual([p["id"] for p in programi.seznam()], ["vlc.desktop"])


if __name__ == "__main__":
    unittest.main()
