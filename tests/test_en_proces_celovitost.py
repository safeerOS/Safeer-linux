"""Celovitost: Safeer OS, Control, Splet in delovna povrsina kot en proces (pregled celovitosti 15. 10. 2026).

»Vse je en proces, vsi nasi dodatki delujejo kot del namiznega okolja« (lastnik). Preizkusi pokrivajo predajo
delovne povrsine tekocemu procesu, skupno pripravo namizja, vgrajeni Control (okno, pladenj, posodobitve, samozagon),
ukaze z naprav v istem procesu in Splet namesto privzetega brskalnika.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

from core import en_proces

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


class _Pocisti(unittest.TestCase):
    def tearDown(self):
        en_proces.nastavi_os(None)
        en_proces.nastavi_control(None)


class DelovnaPredaja(_Pocisti):
    """1: `safeer-os --delovna`, ko Safeer OS ze tece, preda dejanje »delovna« (prej tihi konec brez namizja)."""

    def _main(self, predano: bool):
        import safeer_os as so
        app = mock.MagicMock()
        with mock.patch.object(so, "SafeerOS", return_value=app), \
                mock.patch.object(so, "_predaj_ce_oddaljen", return_value=predano) as predaj, \
                mock.patch.object(so, "os_stabilnost"), mock.patch.object(so, "popravi_po_sesutju", return_value=False), \
                mock.patch.object(so, "os_programi"), mock.patch.object(so, "GLib"), \
                mock.patch.object(sys, "argv", ["safeer-os", "--delovna"]):
            izid = so.main()
        return izid, app, predaj

    def test_tekocemu_preda_dejanje(self):
        izid, app, predaj = self._main(True)
        self.assertEqual(izid, 0)
        predaj.assert_called_once_with(app, "delovna")
        app.run.assert_not_called()

    def test_brez_tekocega_zazene(self):
        _izid, app, predaj = self._main(False)
        predaj.assert_called_once_with(app, "delovna")
        app.run.assert_called_once()


class VklopDelovne(_Pocisti):
    """1-2: delovna povrsina v procesu, ki ze tece; ista priprava namizja kot ob zagonu (_ob_namizju)."""

    def setUp(self):
        import safeer_os as so
        self.so = so

    def _lazna(self):
        lazna = mock.MagicMock()
        lazna.okno_delovna = None
        lazna.lupina = None
        lazna.namizje = False
        lazna.posnetek = ""
        return lazna

    def test_iz_safeer_playerja(self):
        lazna = self._lazna()
        self.assertTrue(self.so.SafeerOS._vklopi_delovno(lazna))
        lazna._ustvari_delovno.assert_called_once_with()
        lazna._ob_namizju.assert_called_once_with()
        self.assertTrue(lazna.delovna)

    def test_okno_aplikacije_postane_delovna_povrsina(self):
        lazna = self._lazna()
        lupina = mock.Mock(spec=self.so.os_lupina.Namizje)
        lupina.v_oknu = True
        lazna.lupina = lupina
        self.assertTrue(self.so.SafeerOS._vklopi_delovno(lazna))
        lupina.zapri.assert_called_once_with()
        self.assertIsNone(lupina._ob_koncu)            # zaprtje okna ne konca Safeer OS
        lazna._ustvari_delovno.assert_called_once_with()

    def test_ze_ima_delovno(self):
        lazna = self._lazna()
        lazna.okno_delovna = mock.Mock()
        self.assertFalse(self.so.SafeerOS._vklopi_delovno(lazna))
        lazna._ustvari_delovno.assert_not_called()

    def test_ob_namizju_enkrat_z_vsem(self):
        lazna = self._lazna()
        lazna._namizje_pripravljeno = False
        lazna._prvic = True
        with mock.patch.object(self.so, "GLib") as glib, mock.patch.object(self.so, "uredi_samozagon_ob_zagonu") as sz:
            self.so.SafeerOS._ob_namizju(lazna)
            self.so.SafeerOS._ob_namizju(lazna)
            klici = glib.timeout_add_seconds.call_args_list
            # kuverta, Control, prijavno okno in (15. 10. 2026) kanali Sporocil po izrisu namizja
            self.assertEqual(len(klici), 4)
            for k in klici:
                k.args[1]()
        lazna.scit.zacni_ce_vklopljen.assert_called_once_with()
        sz.assert_called_once_with(lazna.shramba)
        lazna._vgradi_control.assert_called_once_with()      # Control v istem procesu tudi ob poznejsem vklopu
        lazna._zacni_kuverto.assert_called_once_with()
        lazna._prijavno_okno_ob_prijavi.assert_called_once_with()

    def test_izklop_konca_samo_proces_z_delovno(self):
        lazna = self._lazna()
        lazna.delovna = True
        with mock.patch.object(self.so, "GLib") as glib:
            self.assertFalse(self.so.SafeerOS._izklopi_delovno(lazna))      # samo Safeer Player: nic
            lazna.okno_delovna = mock.Mock()
            self.assertTrue(self.so.SafeerOS._izklopi_delovno(lazna))
            glib.idle_add.call_args.args[0]()
        lazna._koncaj.assert_called_once_with()


class OdpriControl(_Pocisti):
    """4: vgrajeni Control pokaze okno neposredno - brez novega procesa safeer-control."""

    def test_vgrajen(self):
        import safeer_os as so
        c = mock.Mock()
        en_proces.nastavi_control(c)
        lazna = mock.MagicMock()
        with mock.patch.object(so.subprocess, "Popen") as popen:
            self.assertTrue(so.SafeerOS._odpri_control(lazna))
        c.pokazi_okno.assert_called_once_with()
        popen.assert_not_called()

    def test_se_ne_tece_vgradi(self):
        import safeer_os as so
        c = mock.Mock()
        lazna = mock.MagicMock()
        lazna._vgradi_control.side_effect = lambda: (en_proces.nastavi_control(c), True)[1]
        with mock.patch.object(so.subprocess, "Popen") as popen:
            self.assertTrue(so.SafeerOS._odpri_control(lazna))
        c.pokazi_okno.assert_called_once_with()
        popen.assert_not_called()

    def test_locen_control(self):
        import safeer_os as so
        lazna = mock.MagicMock()
        lazna._vgradi_control.return_value = False            # Control tece kot locen proces
        with mock.patch.object(so.subprocess, "Popen") as popen, \
                mock.patch.object(so, "_ukaz_controla", return_value=["safeer-control"]):
            self.assertTrue(so.SafeerOS._odpri_control(lazna))
        popen.assert_called_once()

    def test_meni_poslje_dejanje_okno(self):
        vir = beri("safeer_control.py")
        self.assertIn('Gio.SimpleAction.new("okno", None)', vir)
        tekoci = vir[vir.index("def _pokazi_tekocega"):]
        self.assertLess(tekoci.index('("okno", [], {})'), tekoci.index('"org.freedesktop.Application", "Activate"'))


class NapraveVProcesu(_Pocisti):
    """5: magnet, iskanje in medij z naprave v krogu gredo v Safeer OS istega procesa, brez zagona safeer-os."""

    def _klic(self, fn, *argumenti):
        from core import link_daljinec
        app = mock.Mock()
        en_proces.nastavi_os(app)
        with mock.patch("gi.repository.GLib.idle_add", side_effect=lambda f: f()), \
                mock.patch.object(link_daljinec, "_safeer_os") as program, \
                mock.patch("subprocess.Popen") as popen:
            izid = getattr(link_daljinec, fn)(*argumenti)
        program.assert_not_called()
        popen.assert_not_called()
        self.assertTrue(izid["ok"], izid)
        dejanje, vrednost = app.activate_action.call_args.args
        return dejanje, vrednost.get_string()

    def test_magnet(self):
        uri = "magnet:?xt=urn:btih:" + "a" * 40 + "&dn=Sintel"
        dejanje, vrednost = self._klic("odpri_magnet", uri)
        self.assertEqual(dejanje, "magnet")
        self.assertTrue(vrednost.startswith("naprava:magnet:?xt=urn:btih:"))

    def test_iskanje(self):
        self.assertEqual(self._klic("isci_na_racunalniku", "  zaslon  "), ("isci", "zaslon"))

    def test_medij(self):
        import json
        dejanje, vrednost = self._klic("odpri_medij", {"title": "Sintel", "kind": "film"})
        self.assertEqual(dejanje, "medij")
        self.assertEqual(json.loads(vrednost)["title"], "Sintel")


class SpletVProcesu(_Pocisti):
    """6-7: Splet istega procesa namesto privzetega brskalnika; proces se konca z zadnjim oknom."""

    def test_splet_na_namizju_brez_delovne(self):
        vir = beri("safeer_os.py")
        f = vir[vir.index("    def _splet_na_namizju("):vir.index("    def _spremljaj_zaklep(")]
        self.assertIn("if not self._peskovnik_na_voljo():", f)
        self.assertNotIn("not _ima_delovno(self) or", f)

    def test_skritje_zadnjega_okna_konca(self):
        import safeer_os as so
        lazna = mock.MagicMock()
        lazna.okno = lazna.okno_delovna = lazna.lupina = None
        lazna._sprosti_splet_id = 0
        lazna.get_windows.return_value = []
        with mock.patch.object(so, "GLib") as glib, mock.patch.object(so, "pomnilnik"):
            self.assertTrue(so.SafeerOS._skrij_splet_na_namizju(lazna))
            glib.idle_add.call_args.args[0]()
        lazna._koncaj.assert_called_once_with()

    def test_skritje_ob_delovni_ne_konca(self):
        import safeer_os as so
        lazna = mock.MagicMock()
        lazna.okno = None
        lazna._sprosti_splet_id = 0
        with mock.patch.object(so, "GLib") as glib, mock.patch.object(so, "pomnilnik"):
            so.SafeerOS._skrij_splet_na_namizju(lazna)
        glib.idle_add.assert_not_called()

    def test_control_odpre_v_spletu(self):
        import safeer_control as sc
        app = mock.Mock()
        app._splet.return_value = True
        en_proces.nastavi_os(app)
        c = mock.MagicMock()
        c._je_s_huba.return_value = False
        with mock.patch.object(sc, "VGRAJEN", True), mock.patch.object(sc, "Gio") as gio:
            sc.SafeerControl.odpri_naslov(c, "https://example.org/")
        app._splet.assert_called_once_with("https://example.org/", True)
        gio.AppInfo.launch_default_for_uri.assert_not_called()

    def test_samostojni_control_v_privzetem_brskalniku(self):
        import safeer_control as sc
        c = mock.MagicMock()
        c._je_s_huba.return_value = False
        with mock.patch.object(sc, "VGRAJEN", False), mock.patch.object(sc, "Gio") as gio:
            sc.SafeerControl.odpri_naslov(c, "https://example.org/")
        gio.AppInfo.launch_default_for_uri.assert_called_once()


class VgrajeniControl(_Pocisti):
    """3, 8, 9: pladenj vgrajenega Controla brez »Zaženi ob prijavi«, »Posodobi« in »Končaj«; brez druge preverbe."""

    def _postavke(self, vgrajen: bool) -> list:
        import safeer_control as sc
        from core import pladenj_sni
        app = mock.MagicMock()
        app.nastavitve.get.return_value = None
        app.stanje_locenega.return_value = None
        app.posodobitve_izid = {"nove": [{"ime": "safeer-os"}]}
        with mock.patch.object(sc, "VGRAJEN", vgrajen), mock.patch.object(pladenj_sni, "Pladenj") as sni, \
                mock.patch.object(sc.os_posodobitve, "opis", return_value="Safeer OS 9"):
            p = sc.Pladenj(app)
        return p, sni.call_args.args[3]

    def test_pladenj_vgrajen(self):
        p, postavke = self._postavke(True)
        for postavka in (p.samozagon, p.koncaj, p.posodobi):
            self.assertNotIn(postavka, postavke)
        self.assertIn(p.odpri, postavke)
        self.assertFalse(p.posodobi.get_visible())

    def test_pladenj_samostojen(self):
        p, postavke = self._postavke(False)
        for postavka in (p.samozagon, p.koncaj, p.posodobi):
            self.assertIn(postavka, postavke)

    def test_vgrajen_ne_preverja_posodobitev(self):
        import safeer_control as sc
        app = mock.MagicMock()
        app.ozadje, app._prva_aktivacija = True, True
        with mock.patch.object(sc, "VGRAJEN", True), mock.patch.object(sc, "Pladenj"), \
                mock.patch.object(sc, "GLib") as glib:
            sc.SafeerControl.do_activate(app)
        self.assertNotIn(app._posodobitve_preveri, [k.args[1] for k in glib.timeout_add_seconds.call_args_list])

    def test_samozagon_ob_delovni_povrsini_se_konca(self):
        import safeer_control as sc
        with mock.patch.object(en_proces, "delovna_safeer_cinnamon", return_value=True), \
                mock.patch.object(sc.os_stabilnost, "zakleni_primerek") as zaklep, \
                mock.patch.object(sys, "argv", ["safeer-control", "--ozadje"]), \
                mock.patch.dict(os.environ, {"SAFEER_CONTROL_IZ_OS": ""}):
            self.assertEqual(sc.main(), 0)
        zaklep.assert_not_called()          # pred zaklepom: vgradnja v Safeer OS ga ne sme videti

    def test_samozagon_iz_safeer_os_ostane(self):
        import safeer_control as sc
        with mock.patch.object(en_proces, "delovna_safeer_cinnamon", return_value=True), \
                mock.patch.object(sc.os_stabilnost, "zakleni_primerek", return_value=None) as zaklep, \
                mock.patch.object(sys, "argv", ["safeer-control", "--ozadje"]), \
                mock.patch.dict(os.environ, {"SAFEER_CONTROL_IZ_OS": "1"}):
            self.assertEqual(sc.main(), 0)    # zaklep zaseden: tiho, a sele po preverbi zaklepa
        zaklep.assert_called_once()


class Samozagoni(_Pocisti):
    """3, 10: ob delovni povrsini Safeer Cinnamon gresta samozagona v shranjeno kopijo (zagoni/), skriti vnos ostane."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        k = self.tmp.name
        for pot in ("safeer-cinnamon/zagoni", "autostart"):
            os.makedirs(os.path.join(k, pot))
        open(os.path.join(k, "safeer-cinnamon", "vklopljeno"), "w").close()
        with open(os.path.join(k, "autostart", "safeer-cinnamon.desktop"), "w") as f:
            f.write("[Desktop Entry]\nExec=safeer-cinnamon --seja\n")
        self.skrit = "[Desktop Entry]\nType=Application\nName=x\nHidden=true\nX-GNOME-Autostart-enabled=false\n"
        for ime in ("safeer-os.desktop", "safeer-control.desktop"):
            with open(os.path.join(k, "autostart", ime), "w") as f:
                f.write(self.skrit)
            open(os.path.join(k, "safeer-cinnamon", "zagoni", ime + ".ni"), "w").close()
        p = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": k, "FLATPAK_ID": ""})
        p.start()
        self.addCleanup(p.stop)

    def _skrit_ostane(self, ime):
        with open(os.path.join(self.tmp.name, "autostart", ime)) as f:
            self.assertEqual(f.read(), self.skrit)

    def test_zaznava(self):
        self.assertTrue(en_proces.delovna_safeer_cinnamon())
        os.remove(os.path.join(self.tmp.name, "autostart", "safeer-cinnamon.desktop"))     # postavitev videz/dock
        self.assertFalse(en_proces.delovna_safeer_cinnamon())

    def test_safeer_os(self):
        import safeer_os as so
        zagoni = os.path.join(self.tmp.name, "safeer-cinnamon", "zagoni")
        with mock.patch.object(so, "SAMOZAGON", os.path.join(self.tmp.name, "autostart", "safeer-os.desktop")):
            self.assertTrue(so.je_samozagon())            # zazene ga seja safeer-cinnamon
            self.assertTrue(so.nastavi_samozagon(True))
            self._skrit_ostane("safeer-os.desktop")
            with open(os.path.join(zagoni, "safeer-os.desktop")) as f:
                self.assertIn("X-GNOME-Autostart-enabled=true", f.read())
            self.assertFalse(os.path.exists(os.path.join(zagoni, "safeer-os.desktop.ni")))

    def test_safeer_control(self):
        import safeer_control as sc
        zagoni = os.path.join(self.tmp.name, "safeer-cinnamon", "zagoni")
        with mock.patch.object(sc, "SAMOZAGON_POT", os.path.join(self.tmp.name, "autostart", "safeer-control.desktop")):
            sc.Samozagon.nastavi(True)
            self._skrit_ostane("safeer-control.desktop")
            self.assertTrue(sc.Samozagon.je_vklopljen())
            self.assertFalse(os.path.exists(os.path.join(zagoni, "safeer-control.desktop.ni")))
            sc.Samozagon.nastavi(False)
            self._skrit_ostane("safeer-control.desktop")
            self.assertFalse(os.path.exists(os.path.join(zagoni, "safeer-control.desktop")))
            self.assertTrue(os.path.exists(os.path.join(zagoni, "safeer-control.desktop.ni")))   # izklop ga odstrani

    def test_nastavitve_skrijejo_stikali(self):
        vir, js = beri("safeer_os.py"), beri("assets", "os", "os.js")
        self.assertIn('"safeerCinnamon": _safeer_cinnamon_vklopljen(),', vir)
        self.assertIn('"samozagonNamizje": delovna_safeer_cinnamon(),', vir)
        self.assertIn('$("stikaloCelozaslonsko").hidden = !!(S.zacetek && S.zacetek.safeerCinnamon);', js)
        self.assertIn('$("stikaloSamozagon").hidden = !!(S.zacetek && S.zacetek.samozagonNamizje);', js)


if __name__ == "__main__":
    unittest.main()
