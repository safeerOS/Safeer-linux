#!/usr/bin/env python3
"""Safeer Browser za Linux na GTK4 in WebKitGTK 6.0 (nas WebKit s popravki): Splet (core/os_splet.VdelaniSplet) v
svojem oknu.

Lastnik, 14. 10. 2026: »vsi produkti z najnovejso tehnologijo, ki se dela na nasih napravah« - tudi Safeer Browser.
Splet in brskalnik sta tako ena koda: vsaka izboljsava spletne izkusnje je takoj v obeh . Podatki (prijave, piskotki, zaznamki, zgodovina) so v isti mapi kot prej (ConfigManager).

Uporaba: safeer_brskalnik.py [NASLOV ...]   - drugi zagon odpre naslove v oknu, ki ze tece (en primerek).
"""
from __future__ import annotations

import os
import sys

KOREN = os.path.dirname(os.path.abspath(__file__))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

from core import urejen_izhod  # noqa: E402
urejen_izhod.namesti_zgodnje_signale("safeer-browser")

if os.environ.get("FLATPAK_ID"):
    # Flatpak od 1.0.127 brez dostopa do gostitelja (lastnik, 15. 10. 2026): brez ovojev /app/host-bin in brez celega
    # doma. Nastavitve, prijave in zaznamki ostanejo skupni s paketom .deb: manifest pokaze samo ~/.config/safeer-mint
    # (--filesystem=xdg-config/safeer-mint:create), drugi podatki (predpomnilnik, seznami groženj, Safeer DRM) so v
    # zasebni mapi Flatpaka (~/.var/app/<ID>). Pred uvozom core.config (CONFIG_DIR se doloci ob uvozu).
    _skupna = os.path.join(os.path.expanduser("~"), ".config", "safeer-mint")
    if os.path.isdir(_skupna) and os.access(_skupna, os.W_OK):
        os.environ.setdefault("SAFEER_MINT_CONFIG_DIR", _skupna)

# Paket .deb: nas WebKitGTK in libsoup iz /usr/lib/<paket>/webkit namesto sistemskih (pred `import gi`).
from core import zasebni_webkit  # noqa: E402
zasebni_webkit.nastavi(KOREN)
from core import video_dekoderji  # noqa: E402
video_dekoderji.programsko()     # VA-API je pri YouTubu odpovedoval (18. 10. 2026), glej modul
from core import pomnilnik  # noqa: E402
pomnilnik.omeji_arene(2)
# Profil naprave: niti slikanja Skia za spletne procese - okolje pred prvo nitjo (core/profil_naprave.py), samo kot
# glavni program (ob uvozu v drug proces, npr. lupino, niti ze tecejo - AGENTS.md, core/okolje_procesa.py).
from core import profil_naprave  # noqa: E402
if __name__ == "__main__":
    from core import okolje_procesa  # noqa: E402
    okolje_procesa.pred_nitmi()
if __name__ == "__main__":
    profil_naprave.okolje_pred_nitmi()
if __name__ == "__main__":
    from core import peskovnik_userns  # noqa: E402
    peskovnik_userns.pred_nitmi()

import gi  # noqa: E402
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Pango", "1.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402
from gi.repository import WebKit as WebKit2  # noqa: E402
zasebni_webkit.preveri_nas_webkit(WebKit2)

pomnilnik.tlak_omrezja(WebKit2, 160)   # pred prvim pogledom (kot Safeer OS)
profil_naprave.nastavi_model(WebKit2)  # globalni model predpomnilnika po profilu, pred prvim WebContext

from core import log as safeer_log  # noqa: E402
from core.config import CONFIG_DIR, ConfigManager  # noqa: E402

APP_ID = "io.github.memelandfaner.SafeerBrowser"
JEZIKI = ("sl", "en", "de", "es", "fr", "it")


def razlicica() -> str:
    try:
        with open(os.path.join(KOREN, "packaging", "VERSION"), encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def jezik() -> str:
    """Jezik vmesnika: nastavitev brskalnika (language), sicer jezik seje."""
    v = str(ConfigManager().get("language", "auto") or "auto")[:2].lower()
    if v in JEZIKI:
        return v
    for ime in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        for del_ in (os.environ.get(ime) or "").split(":"):
            k = del_[:2].lower()
            if k in JEZIKI:
                return k
    return "en"


def naslovi_iz_argumentov(argv) -> list:
    """Naslovi in datoteke iz ukazne vrstice (privzeti brskalnik: xdg-open https://...)."""
    izhod = []
    for a in argv:
        if not a or a.startswith("-"):
            continue
        if a.startswith(("http://", "https://", "file://", "about:")):
            izhod.append(a)
        elif os.path.exists(a):
            izhod.append(GLib.filename_to_uri(os.path.abspath(a), None))
    return izhod


def shrani_sejo(config, naslovi, izbran: int = 0) -> None:
    """Odprti zavihki ob zaprtju okna (obnovijo se ob naslednjem zagonu) in zavihek, ki je
    bil izbran (preizkus 14. 10.: po zagonu je bil vedno izbran prvi)."""
    shranjeni = [(i, n) for i, n in enumerate(naslovi) if n.startswith(("http://", "https://"))][:30]
    config.set("splet_seja_izbran", next((k for k, (i, _n) in enumerate(shranjeni) if i == izbran), 0))
    config.set("splet_seja", [n for _i, n in shranjeni])


def shrani_ali_pozabi_sejo(config, naslovi, izbran: int = 0) -> None:
    """»Izbrisi ob izhodu: zgodovina«: odprti zavihki so tudi zgodovina - seje ne shranimo in staro pozabimo (pregled
    14. 10. 2026: prej so se naslovi zavihkov shranili ne glede na to nastavitev)."""
    if "zgodovina" in (config.get("brisi_ob_izhodu", []) or []):
        config.set("splet_seja", [])
        config.set("splet_seja_izbran", 0)
        return
    shrani_sejo(config, naslovi, izbran)


def izbran_v_seji(config, n: int) -> int:
    try:
        i = int(config.get("splet_seja_izbran", 0) or 0)
    except (TypeError, ValueError):
        i = 0
    return i if 0 <= i < n else 0


def nalozi_sejo(config) -> list:
    v = config.get("splet_seja", []) or []
    return [str(n) for n in v if isinstance(n, str) and n.startswith(("http://", "https://"))][:30]


PRIVZETI = {
    "sl": ("Safeer Browser ni tvoj privzeti brskalnik.", "Nastavi kot privzetega", "Ne sprašuj več",
           "Safeer Browser je zdaj tvoj privzeti brskalnik.", "Nastavi Safeer Browser kot privzeti brskalnik"),
    "en": ("Safeer Browser is not your default browser.", "Make default", "Don't ask again",
           "Safeer Browser is now your default browser.", "Make Safeer Browser the default browser"),
    "de": ("Safeer Browser ist nicht dein Standardbrowser.", "Als Standard festlegen", "Nicht mehr fragen",
           "Safeer Browser ist jetzt dein Standardbrowser.", "Safeer Browser als Standardbrowser festlegen"),
    "es": ("Safeer Browser no es tu navegador predeterminado.", "Establecer como predeterminado", "No volver a preguntar",
           "Safeer Browser es ahora tu navegador predeterminado.", "Establecer Safeer Browser como navegador predeterminado"),
    "fr": ("Safeer Browser n’est pas votre navigateur par défaut.", "Définir par défaut", "Ne plus demander",
           "Safeer Browser est maintenant votre navigateur par défaut.", "Définir Safeer Browser comme navigateur par défaut"),
    "it": ("Safeer Browser non è il tuo browser predefinito.", "Imposta come predefinito", "Non chiedere più",
           "Safeer Browser ora è il tuo browser predefinito.", "Imposta Safeer Browser come browser predefinito"),
}


def besedila_privzetega() -> tuple:
    return PRIVZETI.get(jezik(), PRIVZETI["en"])


def nastavi_privzetega() -> tuple:
    """(uspeh, napake) - .deb nastavi sam; Flatpak (brez portala za to) in AppImage povesta, kje v nastavitvah sistema
    se nastavi (core/default_browser.py)."""
    from core.default_browser import set_default_browser
    try:
        return set_default_browser(KOREN, jezik())
    except Exception as e:  # noqa: BLE001 - klik ne sme zapreti okna
        return False, [repr(e)]


def je_privzet() -> bool:
    from core.default_browser import is_default_browser
    try:
        return bool(is_default_browser())
    except Exception:  # noqa: BLE001
        return False


class SafeerBrskalnik(Gtk.Application):
    def __init__(self, avtomatizacija: bool = False) -> None:
        self.avtomatizacija = bool(avtomatizacija)
        flags = Gio.ApplicationFlags.NON_UNIQUE if self.avtomatizacija else Gio.ApplicationFlags.HANDLES_OPEN
        super().__init__(application_id=APP_ID, flags=flags)
        self.okno = None
        self.splet = None
        self._zacasna_mapa = None
        self._koncano = False
        self._izhod_v_teku = False
        if self.avtomatizacija:
            from core.os_splet import pocisti_stare_zacasne_avtomatizacije, ustvari_zacasno_mapo_avtomatizacije
            pocisti_stare_zacasne_avtomatizacije()
            self._zacasna_mapa = ustvari_zacasno_mapo_avtomatizacije()
            self.config = ConfigManager(config_dir=self._zacasna_mapa)
        else:
            self.config = None
        from core import urejen_izhod
        urejen_izhod.povezi_signale(self._koncaj)
        self.add_main_option("automation", 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             "Nacin za avtomatizacijo (WebKitWebDriver)", None)

    # ------------------------------------------------------------------ okno
    def _ustvari(self) -> None:
        from core.os_splet import VdelaniSplet
        okno = Gtk.ApplicationWindow(application=self, title="Safeer Browser")
        okno.set_icon_name("safeer-browser")
        okno.set_default_size(1280, 820)
        try:
            self.splet = VdelaniSplet(Gtk, Gdk, Gio, GLib, WebKit2, KOREN, jezik, None, stars=okno,
                                      config=self.config, avtomatizacija=self.avtomatizacija,
                                      prvi_zavihek=not self.avtomatizacija)
        except Exception as e:
            if self.avtomatizacija:
                sys.stderr.write(f"[Safeer Browser] Napaka avtomatizacije pri zagonu: {e}\n")
                self._pospravi_avtomatizacijo()
                self.quit()
                sys.exit(1)
            raise
        self.splet.privzeti = (je_privzet, nastavi_privzetega, besedila_privzetega)   # gumb v nastavitvah Spleta
        # Safeer DRM je od 1.0.127 v paketu: nekoc preneseno kopijo pospravimo v ozadju (profili s prijavami ostanejo).
        from core import safeer_drm
        safeer_drm.pospravi_staro_v_ozadju()
        skatla = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        skatla.set_name("safeer-brskalnik")      # ozadje kot Splet (brez belega roba okoli vrstice)
        skatla.append(self._vrstica_privzetega())
        # Stranska plosca (spletni klepeti in posta ob strani) iz istega kataloga kot Sporocila v Safeer OS
        # (core/spletni_klepeti.py) - ista seja in zascita kot zavihki (core/stranska_plosca.py).
        from core.stranska_plosca import StranskaPlosca
        vsebina = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        vsebina.set_vexpand(True)
        self.splet.gradnik.set_hexpand(True)
        vsebina.append(self.splet.gradnik)
        self.plosca = StranskaPlosca(Gtk, Gio, self.splet, jezik)
        vsebina.append(self.plosca.gradnik)
        skatla.append(vsebina)
        self.splet.gradnik.set_vexpand(True)
        okno.set_child(skatla)
        self._zavihki_v_naslovno_vrstico(okno)
        k = Gtk.EventControllerKey()
        k.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        k.connect("key-pressed", lambda _k, keyval, _koda, stanje: bool(self.splet.tipka(_Tipka(keyval, stanje))))
        okno.add_controller(k)
        okno.connect("close-request", self._ob_zaprtju)
        self.okno = okno
        if not self.avtomatizacija:
            seja = nalozi_sejo(self.splet.config)
            if seja:
                self.splet.odpri(seja[0])
                for n in seja[1:]:
                    self.splet.nov_zavihek(n)
                self.splet.izberi(self.splet.zavihki[izbran_v_seji(self.splet.config, len(self.splet.zavihki))]["pogled"])

    def _zavihki_v_naslovno_vrstico(self, okno) -> None:
        """Kot sodobni brskalniki: zavihki so v vrhu okna, brez locene naslovne vrstice (lastnik 17. 10. 2026: napis
        »Safeer Browser« v Mintovi naslovni vrstici je segal v prvo vrstico brskalnika). Gumbi okna ostanejo desno."""
        vrstica = getattr(self.splet, "vrstica_zavihkov", None)
        if vrstica is None or vrstica.get_parent() is None:
            return
        try:
            vrstica.get_parent().remove(vrstica)
            vrstica.set_hexpand(True)
            glava = Gtk.HeaderBar()
            glava.set_name("safeer-glava")
            glava.set_show_title_buttons(True)
            glava.set_title_widget(vrstica)
            okno.set_titlebar(glava)
            from core import os_lupina
            tok = os_lupina.tokeni()
            if self.avtomatizacija:
                # V1: drugacna barva naslovne vrstice iz assets/os/tokens.css (--opozorilo: #ffcf8a)
                r, g, b, a = tok.get("opozorilo", (255, 207, 138, 1.0))
                barva_bg = f"rgba({r},{g},{b},{a:.3f})" if a < 1 else f"#{r:02x}{g:02x}{b:02x}"
                barva_btn = "#0b1424"
            else:
                r, g, b, a = tok.get("ozadje", (11, 20, 36, 1.0))
                barva_bg = f"rgba({r},{g},{b},{a:.3f})" if a < 1 else f"#{r:02x}{g:02x}{b:02x}"
                barva_btn = "#eaf2ff"
            css = Gtk.CssProvider()
            slog = (f"#safeer-glava {{ background: {barva_bg}; box-shadow: none; border: 0; min-height: 0;"
                    f" padding: 0 4px 0 0; }} #safeer-glava windowcontrols button {{ color: {barva_btn}; }}")
            css.load_from_data(slog.encode("utf-8"), -1)
            Gtk.StyleContext.add_provider_for_display(okno.get_display(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except Exception as e:  # noqa: BLE001 - brez glave ostane prejsnja postavitev (zavihki pod naslovno vrstico)
            print("[Safeer Browser] zavihki v glavi:", e)
            if vrstica.get_parent() is None:
                self.splet.gradnik.prepend(vrstica)

    def _vrstica_privzetega(self):
        """Kot Firefox: tiha vrstica, ce Safeer ni privzeti brskalnik - nikoli ne prevzame vloge sam (lastnik: brez
        prevzemanja za hrbtom). »Ne sprasuj vec« si zapomni (check_default_browser, ista nastavitev kot GTK3)."""
        if self.avtomatizacija:
            return Gtk.Box()
        besedila = besedila_privzetega()
        rev = Gtk.Revealer()
        vrsta = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        vrsta.set_name("splet-pojavna")
        for stran in ("set_margin_start", "set_margin_end", "set_margin_top", "set_margin_bottom"):
            getattr(vrsta, stran)(4)
        napis = Gtk.Label(label=besedila[0], xalign=0, hexpand=True, wrap=True)   # navodila Flatpaka so daljsa
        nastavi = Gtk.Button(label=besedila[1])
        nikoli = Gtk.Button(label=besedila[2])
        for g in (napis, nastavi, nikoli):
            vrsta.append(g)
        rev.set_child(vrsta)

        def ob_nastavi(*_):
            ok, napake = nastavi_privzetega()
            if ok:
                napis.set_text(besedila[3]); nastavi.set_visible(False); nikoli.set_visible(False)
                GLib.timeout_add_seconds(4, lambda: rev.set_reveal_child(False) or False)
            else:
                napis.set_text("; ".join(napake)[:400])
                nastavi.set_visible(False)      # Flatpak: navodila namesto gumba, ki ne more nic narediti

        def ob_nikoli(*_):
            self.splet.config.set("check_default_browser", False)
            rev.set_reveal_child(False)
        nastavi.connect("clicked", ob_nastavi)
        nikoli.connect("clicked", ob_nikoli)

        def preveri():
            if self.splet.config.get("check_default_browser", True) and not je_privzet():
                rev.set_reveal_child(True)
            return False
        GLib.timeout_add_seconds(3, preveri)     # po prvem izrisu: brez zamude ob zagonu
        return rev

    def _ob_sigterm(self, *_a) -> bool:
        """Ob signalu SIGTERM/SIGINT: urejen izhod po nacrtu stabilnosti P2."""
        self._koncaj()
        return False

    def _ob_zaprtju(self, *_a) -> bool:
        """Ob zaprtju okna: urejen izhod po nacrtu stabilnosti P2."""
        self._koncaj()
        return False

    def _koncaj(self) -> None:
        """Urejen izhod Safeer Browserja (P2: UI -> strezniki -> podprocesi -> baze -> stanje -> exit)."""
        if getattr(self, "_koncano", False) or getattr(self, "_izhod_v_teku", False):
            return
        self._izhod_v_teku = True

        import os
        import time
        from core import urejen_izhod

        # Posnetek seje pred skrivanjem oken
        zavihki_za_sejo = None
        izbran_idx = 0
        try:
            if self.splet is not None and getattr(self.splet, "config", None) is not None:
                tren = self.splet.trenutni()
                zavihki = self.splet.zavihki
                from core.splet_spanje import naslov_pogleda
                zavihki_za_sejo = [naslov_pogleda(z["pogled"]) for z in zavihki]
                izbran_idx = next((i for i, z in enumerate(zavihki) if z["pogled"] is tren), 0)
        except Exception as e:  # noqa: BLE001 - posnetek seje ne sme ustaviti zapiranja
            print("[Safeer Browser] posnetek seje:", e, flush=True)

        # 1. FAZA_UI: skrij okno, pocisti WebKit ob izhodu, pospravi Splet
        def korak_ui():
            if self.okno is not None:
                try:
                    self.okno.set_visible(False)
                except Exception:  # noqa: BLE001, S110 - izhod/pospravljanje: nobena napaka ne sme ustaviti naslednjih korakov
                    pass
            if self.splet is not None:
                if self.splet.config.get("brisi_ob_izhodu", []) and not getattr(self, "_brisanje", False):
                    self._brisanje = True
                    ostane = {"n": 1}

                    def konec():
                        ostane["n"] = 0

                    try:
                        self.splet.pocisti_ob_izhodu(konec)
                        kontekst = GLib.MainContext.default()
                        rok = time.monotonic() + 2.0
                        while ostane["n"] > 0 and time.monotonic() < rok:
                            if not kontekst.iteration(False):
                                time.sleep(0.01)
                    except Exception as e:  # noqa: BLE001 - ciscenje WebKita ne sme blokirati izhoda
                        print("[Safeer Browser] pocisti_ob_izhodu:", e)
                if hasattr(self.splet, "pospravi"):
                    try:
                        self.splet.pospravi()
                    except Exception as e:  # noqa: BLE001 - pospravljanje spleta ne sme blokirati izhoda
                        print("[Safeer Browser] pospravi splet:", e)

        urejen_izhod.izvedi_korak(urejen_izhod.FAZA_UI, "SafeerBrowser:ui", korak_ui, rok_s=2.5)

        # 2. FAZA_STREZNIKI: brskalnik nima zunanjih streznikov
        def korak_strezniki():
            pass

        urejen_izhod.izvedi_korak(urejen_izhod.FAZA_STREZNIKI, "SafeerBrowser:strezniki", korak_strezniki, rok_s=1.0)

        # 3. FAZA_PODPROCESI: Safeer DRM
        def korak_podprocesi():
            if self.splet is not None:
                try:
                    self.splet.koncaj_drm()
                except Exception as e:
                    print("[Safeer Browser] DRM ob izhodu:", e)

        urejen_izhod.izvedi_korak(urejen_izhod.FAZA_PODPROCESI, "SafeerBrowser:drm", korak_podprocesi, rok_s=2.0, na_niti=True)

        # 4. FAZA_BAZE: WebKit baze
        def korak_baze():
            pass

        urejen_izhod.izvedi_korak(urejen_izhod.FAZA_BAZE, "SafeerBrowser:baze", korak_baze, rok_s=1.0)

        # 5. FAZA_STANJE: seja, obnova, zacasna mapa avtomatizacije
        def korak_stanje():
            if not self.avtomatizacija and zavihki_za_sejo is not None and self.splet is not None and self.splet.config is not None:
                try:
                    shrani_ali_pozabi_sejo(self.splet.config, zavihki_za_sejo, izbran_idx)
                except Exception as e:  # noqa: BLE001 - napaka seje ne sme podreti izhoda
                    print("[Safeer Browser] seja:", e, flush=True)
            try:
                from core import nova_razlicica
                nova_razlicica.shrani_stanje("safeer-browser", {"pid": os.getpid(), "zavihki": zavihki_za_sejo or []},
                                             ime=nova_razlicica.OBNOVA)
            except Exception as e:  # noqa: BLE001 - izhod/pospravljanje: nobena napaka ne sme ustaviti naslednjih korakov
                print("[Safeer Browser] stanje obnova:", e)
            if getattr(self, "_zacasna_mapa", None) and os.path.isdir(self._zacasna_mapa):
                from core.os_splet import _je_zacasna_mapa_avtomatizacije
                if _je_zacasna_mapa_avtomatizacije(self._zacasna_mapa):
                    import shutil
                    try:
                        shutil.rmtree(self._zacasna_mapa, ignore_errors=True)
                    except Exception as e:  # noqa: BLE001 - izhod/pospravljanje: nobena napaka ne sme ustaviti naslednjih korakov
                        print("[Safeer Browser] pospravi zacasno ob zaprtju:", e)
                self._zacasna_mapa = None

        urejen_izhod.izvedi_korak(urejen_izhod.FAZA_STANJE, "SafeerBrowser:stanje", korak_stanje, rok_s=2.0)

        # 6. FAZA_EXIT: unici okno in koncaj
        def korak_exit():
            if self.okno is not None:
                try:
                    self.okno.destroy()
                except Exception:  # noqa: BLE001, S110 - izhod/pospravljanje: nobena napaka ne sme ustaviti naslednjih korakov
                    pass
            self.quit()

        urejen_izhod.izvedi_korak(urejen_izhod.FAZA_EXIT, "SafeerBrowser:exit", korak_exit, rok_s=1.0)

        self._koncano = True
        self._izhod_v_teku = False

    def do_activate(self) -> None:
        if self.okno is None:
            self._ustvari()
        self.okno.present()

    def do_open(self, datoteke, _n, _namig) -> None:
        """Naslovi od drugod (privzeti brskalnik, drugi zagon): v oknu, ki tece; strani, ki jo ima uporabnik odprto,
        ne zamenja (VdelaniSplet.odpri_povezavo)."""
        prvic = self.okno is None
        if prvic:
            self._ustvari()
        for i, d in enumerate(datoteke):
            naslov = d.get_uri() or ""
            # Datoteka z diska (»Odpri z«, privzeti brskalnik): file:// je tu uporabnikova izbira (lokalno=True).
            if prvic and i == 0 and not nalozi_sejo(self.splet.config):
                self.splet.odpri(naslov, lokalno=True)
            else:
                self.splet.odpri_povezavo(naslov, lokalno=True)
        self.okno.present()


class _Tipka:
    def __init__(self, keyval, state) -> None:
        self.keyval, self.state = keyval, state


def main() -> int:
    if "--version" in sys.argv[1:]:
        print("Safeer Browser " + razlicica())
        return 0
    if "--set-default" in sys.argv[1:]:
        ok, napake = nastavi_privzetega()
        print(besedila_privzetega()[3] if ok else "; ".join(napake), file=sys.stdout if ok else sys.stderr)
        return 0 if ok else 1
    safeer_log.install(CONFIG_DIR, razlicica())
    # Razred okna na X11 = prgname: brez tega »safeer_brskalnik.py« in pult okna ne poveze z vnosom v meniju
    # (StartupWMClass; izmerjeno v Xvfb ob pregledu paketa 14. 10. 2026).
    GLib.set_prgname(APP_ID)
    # Ubuntu 24.04+ brez nasega profila AppArmor: peskovnik WebKita je izklopljen ze pred nitmi (vrh datoteke), samo ce
    # res ne more teci (sicer g_error); tu le pojasnilo.
    from core import peskovnik_userns
    peskovnik = peskovnik_userns.ob_zagonu()
    avtomatizacija = "--automation" in sys.argv[1:]
    app = SafeerBrskalnik(avtomatizacija=True) if avtomatizacija else SafeerBrskalnik()
    if peskovnik.get("izklopljen"):
        peskovnik_userns.pojasni_kasneje(GLib, CONFIG_DIR, jezik(), "Safeer Browser", "safeer-browser", app)
    argumenti = [sys.argv[0]] + [a for a in naslovi_iz_argumentov(sys.argv[1:]) if a != "--automation"]
    # Zbiranje smeti samo na glavni niti (pregled 18. 10. 2026): samodejni gc v delovni niti (DoH, Link, IMAP ...) je
    # sprostil predmet WebKit/GTK zunaj glavne niti - RELEASE_ASSERT(isMainThread) -> SIGTRAP (signal 5, koda 133).
    from core import runtime_safety
    runtime_safety.install_main_thread_gc()
    return app.run(argumenti)


if __name__ == "__main__":
    sys.exit(main())
