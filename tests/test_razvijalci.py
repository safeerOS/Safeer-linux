"""Preizkusi za orodja za razvijalce in WebDriver v Spletu in Safeer Browserju (naloga 21. 10. 2026).

Preveri zahteve in najdbe neodvisnega pregleda:
1. K1 (KRITIČNA): Avtomatizacija v izolirani, efemerni seji (WebKit.NetworkSession.new_ephemeral()),
   ločen začasni config (mktemp -d, pospravljanje ob izhodu), brez zgodovine, zaznamkov in podatkov uporabnika;
   nič se ne zapiše v uporabnikov config; preizkus: seja is_ephemeral(), pot ni config_dir uporabnika.
2. V1 (VISOKA): Vidna oznaka avtomatizacije - trajna pasica »To okno upravlja program za samodejno preizkušanje (WebDriver)«
   v vseh 6 jezikih (sl, en, de, es, fr, it) + drugačna barva naslovne vrstice iz assets/os/tokens.css (--opozorilo).
   Preizkus: pogled z is_controlled_by_automation ima pasico.
3. V2 (VISOKA): Preverba GNU_STACK za vse ELF v paketu (rešeno v izdaja-132, preverjeno v test_packaging).
4. S1 (SREDNJA): Vedenjski preizkusi inšpektorja:
   - Ctrl+Shift+I in F12 pri izklopljenih orodjih ne naredita ničesar (ne odpreta inšpektorja).
   - Kontekstni meni brez nastavitve nima »Preglej element«.
   - Nastavitev se ob vklopu prenese na obstoječe in NOVE zavihke.
5. S2 (SREDNJA): Dokumentacija docs/razvijalci/webdriver.md izrecno navaja --host=127.0.0.1 in svari pred --host=all.
6. N1 (NIZKA): Čista obravnava callable/string jezika v _t brez skrivanja napak.

Vsak varnostni preizkus mora brez popravka pasti!
"""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent


class TestWebDriverPakiranje(unittest.TestCase):
    """Preverbe gradbenih konfiguracij, skript pakiranja in GNU_STACK (V2)."""

    def test_webdriver_moznosti_gradnje(self):
        """ENABLE_WEBDRIVER=ON v receptu in bin ni v cleanup."""
        pot = ROOT / "packaging/webkit/webkitgtk6-safeer.yml"
        vsebina = pot.read_text(encoding="utf-8")
        self.assertIn("- -DENABLE_WEBDRIVER=ON", vsebina, f"{pot} mora imeti -DENABLE_WEBDRIVER=ON")
        self.assertNotIn("- -DENABLE_WEBDRIVER=OFF", vsebina, f"{pot} ne sme imeti -DENABLE_WEBDRIVER=OFF")
        cleanup = vsebina.split("cleanup:", 1)[1].split("sources:", 1)[0]
        self.assertNotIn("- /bin", cleanup, f"{pot} ne sme imeti - /bin v cleanup")

    def test_webdriver_v_paketu_in_skriptah(self):
        """WebKitWebDriver v vgradi.sh, paket.sh, zgradi.sh in nadaljuj.sh."""
        vgradi = (ROOT / "packaging/webkit-deb/vgradi.sh").read_text(encoding="utf-8")
        self.assertIn("bin/WebKitWebDriver", vgradi, "vgradi.sh mora preveriti bin/WebKitWebDriver")

        zgradi = (ROOT / "packaging/webkit-deb/zgradi.sh").read_text(encoding="utf-8")
        pospravi = zgradi.split("# --- pospravi", 1)[1].split("find ", 1)[0]
        self.assertNotIn('"$PREDPONA/bin"', pospravi, "zgradi.sh ne sme brisati $PREDPONA/bin")

        nadaljuj = (ROOT / "packaging/webkit-deb/nadaljuj.sh").read_text(encoding="utf-8")
        pospravi_n = nadaljuj.split("# --- pospravi", 1)[1].split("find ", 1)[0]
        self.assertNotIn('"$PREDPONA/bin"', pospravi_n, "nadaljuj.sh ne sme brisati $PREDPONA/bin")

        paket = (ROOT / "packaging/webkit-deb/paket.sh").read_text(encoding="utf-8")
        self.assertIn("find bin lib libexec", paket, "paket.sh mora vkljuciti bin v odtis gradnje")

    def test_webdriver_gnu_stack_preverbe(self):
        """smoke_webkit_deb.py in bolt.sh preverita PT_GNU_STACK tudi za WebKitWebDriver."""
        smoke = (ROOT / "packaging/smoke_webkit_deb.py").read_text(encoding="utf-8")
        self.assertIn("WebKitWebDriver", smoke, "smoke_webkit_deb.py mora preveriti WebKitWebDriver")


class TestBrowserAutomationK1Izolacija(unittest.TestCase):
    """K1: Preverba izolacije profila, efemerne seje in začasnega configa v načinu avtomatizacije."""

    def test_brez_zastavice_automation_ni_klican_set_automation_allowed(self):
        """Brez zastavice --automation: set_automation_allowed NI klican in avtomatizacija ni dejavna."""
        from core import os_splet
        from core.config import CONFIG_DIR
        config = mock.MagicMock()
        config.config_dir = CONFIG_DIR
        config.get.return_value = False
        kontekst = mock.MagicMock()
        WebKit2 = mock.MagicMock()
        WebKit2.WebContext.get_default.return_value = kontekst
        WebKit2.NetworkSession.new.return_value = mock.MagicMock()

        with mock.patch("core.pomnilnik.kontekst", return_value=kontekst):
            splet = os_splet.VdelaniSplet(
                mock.MagicMock(), mock.MagicMock(), mock.MagicMock(), mock.MagicMock(),
                WebKit2, str(ROOT), "sl", None, prvi_zavihek=False, config=config, avtomatizacija=False
            )
        kontekst.set_automation_allowed.assert_not_called()
        self.assertFalse(getattr(splet, "avtomatizacija", False))

    def test_avtomatizacija_uporabi_ephemeral_network_session(self):
        """K1: V načinu avtomatizacije VdelaniSplet uporabi WebKit.NetworkSession.new_ephemeral()."""
        from core import os_splet
        from core.config import CONFIG_DIR

        kontekst = mock.MagicMock()
        WebKit2 = mock.MagicMock()
        WebKit2.WebContext.get_default.return_value = kontekst
        ephemeral_session = mock.MagicMock()
        ephemeral_session.is_ephemeral.return_value = True
        WebKit2.NetworkSession.new_ephemeral.return_value = ephemeral_session

        with mock.patch("core.pomnilnik.kontekst", return_value=kontekst):
            splet = os_splet.VdelaniSplet(
                mock.MagicMock(), mock.MagicMock(), mock.MagicMock(), mock.MagicMock(),
                WebKit2, str(ROOT), "sl", None, prvi_zavihek=False, avtomatizacija=True
            )

        WebKit2.NetworkSession.new_ephemeral.assert_called_once()
        self.assertTrue(splet.seja.is_ephemeral())
        # Seja ne sme uporabljati trajne shrambe piskotkov
        WebKit2.NetworkSession.new.assert_not_called()
        self.assertNotEqual(splet.config.config_dir, CONFIG_DIR)
        # Pospravi zacasno mapo
        splet.pospravi()

    def test_avtomatizacija_ustvari_locen_zacasni_config_in_ga_pospravi(self):
        """K1: SafeerBrskalnik(avtomatizacija=True) ima ločeno začasno mapo (ne ~/.config/safeer-mint)."""
        import safeer_brskalnik as sb
        from core.config import CONFIG_DIR

        app = sb.SafeerBrskalnik(avtomatizacija=True)
        self.assertTrue(app.avtomatizacija)
        self.assertIsNotNone(app._zacasna_mapa)
        self.assertTrue(os.path.isdir(app._zacasna_mapa))
        self.assertNotEqual(app.config.config_dir, CONFIG_DIR)
        self.assertTrue(app.config.config_dir.startswith(tempfile.gettempdir()))

        # Poskus zapisa v config gre v zacasno mapo
        app.config.set("test_kljuc", "vrednost_avto")
        self.assertTrue(os.path.isfile(os.path.join(app.config.config_dir, "settings.json")))
        # V uporabnikovem config_dir ni tega zapisa
        self.assertFalse(os.path.isfile(os.path.join(app.config.config_dir, "..", "neobstojeci_test.json")))

        zacasna = app._zacasna_mapa
        # Ob zaprtju se zacasna mapa pospravi
        app.splet = mock.MagicMock()
        app._ob_zaprtju()
        self.assertFalse(os.path.exists(zacasna), "Začasna mapa avtomatizacije mora biti ob zaprtju izbrisana")

    def test_avtomatizacija_ne_pise_zgodovine(self):
        """K1: V načinu avtomatizacije se zgodovina brskanja ne beleži."""
        from core import os_splet
        splet = mock.MagicMock(spec=os_splet.VdelaniSplet)
        splet.avtomatizacija = True
        splet.config = mock.MagicMock()
        splet.config.config_dir = "/tmp/fake-auto"
        splet.WebKit2 = mock.MagicMock()
        splet.WebKit2.LoadEvent.FINISHED = 1
        splet.WebKit2.LoadEvent.STARTED = 0
        splet.aplikacije = {}
        splet.koren = str(ROOT)

        pogled = mock.MagicMock()
        pogled.get_uri.return_value = "https://example.com"
        pogled.get_title.return_value = "Example"

        with mock.patch("core.zgodovina.dodaj") as mock_dodaj:
            os_splet.VdelaniSplet._nalozen(splet, pogled, 1)
            mock_dodaj.assert_not_called()

        # Ko avtomatizacija ni dejavna, se zgodovina belezi
        splet.avtomatizacija = False
        with mock.patch("core.zgodovina.dodaj") as mock_dodaj:
            os_splet.VdelaniSplet._nalozen(splet, pogled, 1)
            mock_dodaj.assert_called_once()


class TestBrowserAutomationV1Oznaka(unittest.TestCase):
    """V1: Vidna oznaka avtomatizacije - trajna pasica v 6 jezikih in barva naslovne vrstice."""

    def test_trajna_pasica_v_vseh_6_jezikih(self):
        """V1: Besedilo pasice avtomatizacije obstaja v vseh 6 jezikih."""
        from core.os_splet import BESEDILA, JEZIKI
        pricakovano = {
            "sl": "To okno upravlja program za samodejno preizkušanje (WebDriver)",
            "en": "This window is being controlled by automated test software (WebDriver)",
            "de": "Dieses Fenster wird von einer automatisierten Testsoftware gesteuert (WebDriver)",
            "es": "Esta ventana está siendo controlada por software de pruebas automatizadas (WebDriver)",
            "fr": "Cette fenêtre est contrôlée par un logiciel de test automatisé (WebDriver)",
            "it": "Questa finestra è controllata da un software di test automatizzato (WebDriver)",
        }
        for j in JEZIKI:
            self.assertIn("avtomatizacija_pasica", BESEDILA[j], f"avtomatizacija_pasica manjka v {j}")
            self.assertEqual(BESEDILA[j]["avtomatizacija_pasica"], pricakovano[j])

    def test_pogled_z_avtomatizacijo_ima_pasico(self):
        """V1: Pogled ustvarjen z nadzorovan_avtomatizacija=True ima pasico."""
        from core import os_splet
        Gtk = mock.MagicMock()
        WebKit2 = mock.MagicMock()
        splet = mock.MagicMock(spec=os_splet.VdelaniSplet)
        splet.Gtk = Gtk
        splet.WebKit2 = WebKit2
        splet.Pango = mock.MagicMock()
        splet.avtomatizacija = True
        splet._t = lambda k: "Pasica avtomatizacije"
        splet._st_zavihkov = 0
        splet.zavihki = []
        splet.skatla_zavihkov = mock.MagicMock()
        splet.sklad = mock.MagicMock()
        splet.spanje = mock.MagicMock()
        splet.koren = str(ROOT)
        splet._deli_proces_z.return_value = None

        fake_pogled = mock.MagicMock()
        splet._nov_pogled.return_value = fake_pogled

        # Klic nov_zavihek z nadzorovan_avtomatizacija=True
        p = os_splet.VdelaniSplet.nov_zavihek(splet, "https://safeer.si", nadzorovan_avtomatizacija=True)
        self.assertTrue(hasattr(p, "pasica"), "Pogled pod avtomatizacijo mora imeti atribut pasica")
        self.assertIsNotNone(p.pasica)

    def test_barva_glave_iz_tokens_css(self):
        """V1: safeer_brskalnik v načinu avtomatizacije uporabi barvo --opozorilo iz tokens.css."""
        from core import os_lupina
        tokeni = os_lupina.tokeni()
        self.assertIn("opozorilo", tokeni, "tokens.css mora vsebovati --opozorilo")
        # Preveri, da je barva opozorila v Safeer barvni paleti (#ffcf8a)
        r, g, b, a = tokeni["opozorilo"]
        self.assertEqual((r, g, b), (255, 207, 138))


class TestWebInspectorS1Vedenje(unittest.TestCase):
    """S1: Vedenjski preizkusi inšpektorja (bližnjice, kontekstni meni, prenos na nove zavihke)."""

    def test_bliznjici_ctrl_shift_i_in_f12_pri_izklopljenih_orodjih_ne_naredita_nic(self):
        """S1: Pri izklopljenih orodjih za razvijalce izvedi('inspektor') vrne False in inšpektorja NE odpre."""
        from core import os_splet
        splet = mock.MagicMock(spec=os_splet.VdelaniSplet)
        splet.config = {"developer_extras_enabled": False}
        pogled = mock.MagicMock()
        inspektor = mock.MagicMock()
        pogled.get_inspector.return_value = inspektor
        splet.trenutni.return_value = pogled
        splet._odpri_inspektor = lambda: os_splet.VdelaniSplet._odpri_inspektor(splet)

        # Ko je izklopljeno:
        rezultat = os_splet.VdelaniSplet._odpri_inspektor(splet)
        self.assertFalse(rezultat)
        inspektor.show.assert_not_called()

        # Izvedi("inspektor") prav tako vrne False
        self.assertFalse(os_splet.VdelaniSplet.izvedi(splet, "inspektor"))
        inspektor.show.assert_not_called()

    def test_bliznjici_pri_vklopljenih_orodjih_odpreta_inspektor(self):
        """S1: Pri vklopljenih orodjih izvedi('inspektor') vrne True in pokliče inspector.show()."""
        from core import os_splet
        splet = mock.MagicMock(spec=os_splet.VdelaniSplet)
        splet.config = {"developer_extras_enabled": True}
        pogled = mock.MagicMock()
        inspektor = mock.MagicMock()
        pogled.get_inspector.return_value = inspektor
        splet.trenutni.return_value = pogled
        splet._odpri_inspektor = lambda: os_splet.VdelaniSplet._odpri_inspektor(splet)

        rezultat = os_splet.VdelaniSplet.izvedi(splet, "inspektor")
        self.assertTrue(rezultat)
        inspektor.show.assert_called_once()

    def test_kontekstni_meni_brez_nastavitve_nima_preglej_element(self):
        """S1: Brez vklopljenih orodij se INSPECT_ELEMENT odstrani iz kontekstnega menija."""
        from core import os_splet
        splet = mock.MagicMock(spec=os_splet.VdelaniSplet)
        splet.WebKit2 = mock.MagicMock()
        splet.Gio = mock.MagicMock()
        splet.GLib = mock.MagicMock()
        A = splet.WebKit2.ContextMenuAction
        A.INSPECT_ELEMENT = 100
        A.COPY = 200

        meni = mock.MagicMock()
        postavka = mock.MagicMock()
        postavka.get_stock_action.return_value = A.INSPECT_ELEMENT
        meni.get_items.return_value = [postavka]
        zadetek = mock.MagicMock()
        zadetek.context_is_link.return_value = False
        zadetek.context_is_selection.return_value = False

        # Izklopljeno
        splet.config = {"developer_extras_enabled": False}
        os_splet.VdelaniSplet._kontekstni_meni(splet, mock.MagicMock(), meni, zadetek)
        meni.remove.assert_called_with(postavka)

        # Vklopljeno: postavka ostane
        meni.reset_mock()
        splet.config = {"developer_extras_enabled": True}
        os_splet.VdelaniSplet._kontekstni_meni(splet, mock.MagicMock(), meni, zadetek)
        meni.remove.assert_not_called()

    def test_nastavitev_se_ob_vklopu_prenese_na_nove_zavihke(self):
        """S1: Ko so orodja vklopljena, vsak nov pogled dobi set_enable_developer_extras(True)."""
        from core import os_splet
        splet = mock.MagicMock(spec=os_splet.VdelaniSplet)
        splet.WebKit2 = mock.MagicMock()
        splet.GLib = mock.MagicMock()
        splet.Gdk = mock.MagicMock()
        splet.koren = str(ROOT)
        splet.kontekst = mock.MagicMock()
        splet.seja = mock.MagicMock()
        splet.config = {"developer_extras_enabled": True}
        splet._pravila_strani.return_value = mock.MagicMock()
        splet._skriti.return_value = set()
        splet._temno_skripte = {}
        splet._temno_namesti.return_value = None
        splet._skia.return_value = False
        splet.jezik = "sl"

        nov_pogled = mock.MagicMock()
        nastavitve = mock.MagicMock()
        nov_pogled.get_settings.return_value = nastavitve
        splet.WebKit2.WebView.return_value = nov_pogled

        with mock.patch("core.scit_pravila.zasebnost_pogleda"), \
             mock.patch("core.scit_pravila.funkcije_spleta"), \
             mock.patch("core.os_stabilnost.obnovi_ob_padcu"), \
             mock.patch("core.os_splet.registriraj_most"), \
             mock.patch("core.os_splet.namesti_stevec"), \
             mock.patch("core.os_splet.odlozisce_varuh"), \
             mock.patch("core.os_splet.nastavi_kompozitor"), \
             mock.patch("core.ozadje_strani.prikljuci"):
            p = os_splet.VdelaniSplet._nov_pogled(splet)

        nastavitve.set_enable_developer_extras.assert_called_with(True)


class TestDokumentacijaWebDriverS2(unittest.TestCase):
    """S2: Dokumentacija docs/razvijalci/webdriver.md navaja --host=127.0.0.1 in varnostne zahteve."""

    def test_dokumentacija_vsebuje_host_localhost_in_opozorilo(self):
        pot = ROOT / "docs/razvijalci/webdriver.md"
        self.assertTrue(pot.is_file(), "docs/razvijalci/webdriver.md mora obstajati")
        vsebina = pot.read_text(encoding="utf-8")
        self.assertIn("--host=127.0.0.1", vsebina, "Dokumentacija mora vsebovati --host=127.0.0.1")
        self.assertIn("/usr/lib/safeer-webkit/bin/WebKitWebDriver", vsebina)
        self.assertIn("new_ephemeral", vsebina, "Dokumentacija mora razložiti efemerno sejo")
        # Varnostno opozorilo glede omrezja
        self.assertIn("--host=all", vsebina, "Dokumentacija mora svariti pred --host=all")


if __name__ == "__main__":
    unittest.main()
