#!/usr/bin/env python3
"""Safeer Control — namizna aplikacija za upravljanje naprav prek Safeer Linka.

Brez brskalnika: Safeer Control ima Safeer Link vgrajen. Racunalnik se s 6-mestno kodo
poveze v domaci Safeer Link (na televizorju ali telefonu), potem ima uporabnik v tem oknu
daljinec za televizor (glas, tipke, aplikacije) in telefon, deljenje besedila, datotek in
zaslona - vse v domacem omrezju, brez oblaka in brez racuna.

Ista stran kot v brskalniku (assets/link/), isti Link (core/link_hub.py, core/safeer_link.py).
Kar potrebuje brskalnik (posiljanje odprte strani, zaznamki), stran v Controlu skrije.

Svoja identiteta in shramba: ~/.config/safeer-control/link.json. Ce je na tem racunalniku
Safeer Browser ze povezan v Safeer Link, Control tega ne podira - obe aplikaciji sta v Linku
vsaka s svojim imenom.

Datoteke za televizor: uporabnik izbere mape (stran Control ali pladenj), Safeer OS na
televizorju jih pregleduje in predvaja naravnost z racunalnika (core/link_datoteke.py). Brez
izbrane mape televizor ne vidi nic.

Tiho v ozadju: `safeer-control --ozadje` se poveze v Safeer Link brez okna in pusti ikono v
pladnju (Odpri, Zazeni ob prijavi, Koncaj). Ko je racunalnik enkrat seznanjen, se Control ob
prijavi zaganja sam (~/.config/autostart) - uporabnik ne zaganja nicesar; televizor in telefon
ga vidita, kadar je racunalnik prizgan. Zapiranje okna Control le skrije.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import sys
from typing import Optional

KOREN = os.path.dirname(os.path.abspath(__file__))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gio, GLib, Gtk, WebKit2  # noqa: E402

from core import link_datoteke, link_deljenje, link_hub, link_programi, link_sway, link_tls, link_zaslon, link_zvok  # noqa: E402
from core import os_stabilnost  # noqa: E402
from core.safeer_link import SafeerLink  # noqa: E402

APP_ID = "io.github.memelandfaner.SafeerControl"
CONTROL_POT = "/io/github/memelandfaner/SafeerControl"
NASTAVITVE_MAPA = os.path.expanduser("~/.config/safeer-control")
SAMOZAGON_POT = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "autostart", "safeer-control.desktop")

# Besedila pladnja v jezikih vmesnika (isti nabor kot Safeer Browser).
BESEDILA = {
    "sl": {"locen_namesti": "Namesti ločen zaslon za televizor …", "locen_posodobi": "Posodobi wf-recorder za ločen zaslon …", "locen_ni": "Ločen zaslon za televizor: wf-recorder je prestar", "locen_vprasanje": "Za ločen zaslon za televizor Safeer Control potrebuje pakete: {paketi}. Programi, ki jih zaženeš s televizorja, se bodo odprli na svojem zaslonu in ne bodo motili tvojega namizja.\n\nNamestim jih zdaj? Sistem te bo vprašal za geslo.", "locen_uspeh": "Ločen zaslon za televizor je pripravljen.", "locen_napaka": "Namestitev ni uspela. Programi s televizorja se še naprej odpirajo na namizju.", "locen_gumb": "Namesti", "odpri": "Odpri Safeer Control", "samozagon": "Zaženi ob prijavi", "mape": "Mape za televizor …", "programi": "Programi za televizor", "ves_disk": "Ves računalnik za televizor", "zaslon": "Zaslon za televizor", "koncaj": "Končaj", "povezan": "Safeer Link: povezan", "ni": "Safeer Link: ni povezave"},
    "en": {"locen_namesti": "Install the separate TV screen…", "locen_posodobi": "Update wf-recorder for the separate TV screen…", "locen_ni": "Separate TV screen: wf-recorder is too old", "locen_vprasanje": "For the separate TV screen Safeer Control needs these packages: {paketi}. Programs you start from the TV will open on their own screen and will not disturb your desktop.\n\nInstall them now? The system will ask for your password.", "locen_uspeh": "The separate TV screen is ready.", "locen_napaka": "Installation failed. Programs from the TV keep opening on your desktop.", "locen_gumb": "Install", "odpri": "Open Safeer Control", "samozagon": "Start at login", "mape": "Folders for the TV…", "programi": "Apps for the TV", "ves_disk": "Whole computer for the TV", "zaslon": "Screen for the TV", "koncaj": "Quit", "povezan": "Safeer Link: connected", "ni": "Safeer Link: not connected"},
    "de": {"locen_namesti": "Separaten Bildschirm für den Fernseher installieren …", "locen_posodobi": "wf-recorder für den separaten Bildschirm aktualisieren …", "locen_ni": "Separater Bildschirm: wf-recorder ist zu alt", "locen_vprasanje": "Für den separaten Bildschirm braucht Safeer Control diese Pakete: {paketi}. Programme, die du vom Fernseher startest, öffnen sich auf einem eigenen Bildschirm und stören deinen Desktop nicht.\n\nJetzt installieren? Das System fragt nach deinem Passwort.", "locen_uspeh": "Der separate Bildschirm für den Fernseher ist bereit.", "locen_napaka": "Die Installation ist fehlgeschlagen. Programme vom Fernseher öffnen sich weiter auf dem Desktop.", "locen_gumb": "Installieren", "odpri": "Safeer Control öffnen", "samozagon": "Beim Anmelden starten", "mape": "Ordner für den Fernseher …", "programi": "Programme für den Fernseher", "ves_disk": "Ganzer Computer für den Fernseher", "zaslon": "Bildschirm für den Fernseher", "koncaj": "Beenden", "povezan": "Safeer Link: verbunden", "ni": "Safeer Link: nicht verbunden"},
    "es": {"locen_namesti": "Instalar la pantalla separada para el televisor…", "locen_posodobi": "Actualizar wf-recorder para la pantalla separada…", "locen_ni": "Pantalla separada: wf-recorder es demasiado antiguo", "locen_vprasanje": "Para la pantalla separada Safeer Control necesita estos paquetes: {paketi}. Los programas que abras desde el televisor se abrirán en su propia pantalla y no molestarán tu escritorio.\n\n¿Instalarlos ahora? El sistema te pedirá la contraseña.", "locen_uspeh": "La pantalla separada para el televisor está lista.", "locen_napaka": "La instalación ha fallado. Los programas del televisor seguirán abriéndose en el escritorio.", "locen_gumb": "Instalar", "odpri": "Abrir Safeer Control", "samozagon": "Iniciar al iniciar sesión", "mape": "Carpetas para el televisor…", "programi": "Programas para el televisor", "ves_disk": "Todo el ordenador para el televisor", "zaslon": "Pantalla para el televisor", "koncaj": "Salir", "povezan": "Safeer Link: conectado", "ni": "Safeer Link: sin conexión"},
    "fr": {"locen_namesti": "Installer l'écran séparé pour le téléviseur…", "locen_posodobi": "Mettre à jour wf-recorder pour l'écran séparé…", "locen_ni": "Écran séparé : wf-recorder est trop ancien", "locen_vprasanje": "Pour l'écran séparé, Safeer Control a besoin de ces paquets : {paketi}. Les programmes lancés depuis le téléviseur s'ouvriront sur leur propre écran sans déranger ton bureau.\n\nLes installer maintenant ? Le système te demandera ton mot de passe.", "locen_uspeh": "L'écran séparé pour le téléviseur est prêt.", "locen_napaka": "L'installation a échoué. Les programmes du téléviseur continuent de s'ouvrir sur le bureau.", "locen_gumb": "Installer", "odpri": "Ouvrir Safeer Control", "samozagon": "Lancer à la connexion", "mape": "Dossiers pour le téléviseur…", "programi": "Programmes pour le téléviseur", "ves_disk": "Tout l'ordinateur pour le téléviseur", "zaslon": "Écran pour le téléviseur", "koncaj": "Quitter", "povezan": "Safeer Link : connecté", "ni": "Safeer Link : non connecté"},
    "it": {"locen_namesti": "Installa lo schermo separato per il televisore…", "locen_posodobi": "Aggiorna wf-recorder per lo schermo separato…", "locen_ni": "Schermo separato: wf-recorder è troppo vecchio", "locen_vprasanje": "Per lo schermo separato Safeer Control ha bisogno di questi pacchetti: {paketi}. I programmi avviati dal televisore si apriranno su un proprio schermo senza disturbare il tuo desktop.\n\nInstallarli ora? Il sistema ti chiederà la password.", "locen_uspeh": "Lo schermo separato per il televisore è pronto.", "locen_napaka": "L'installazione non è riuscita. I programmi dal televisore continuano ad aprirsi sul desktop.", "locen_gumb": "Installa", "odpri": "Apri Safeer Control", "samozagon": "Avvia all’accesso", "mape": "Cartelle per il televisore…", "programi": "Programmi per il televisore", "ves_disk": "Tutto il computer per il televisore", "zaslon": "Schermo per il televisore", "koncaj": "Esci", "povezan": "Safeer Link: connesso", "ni": "Safeer Link: non connesso"},
}


def besedilo(jezik: Optional[str], kljuc: str) -> str:
    return BESEDILA.get((jezik or "en")[:2], BESEDILA["en"]).get(kljuc, BESEDILA["en"][kljuc])


def razlicica() -> str:
    try:
        with open(os.path.join(KOREN, "packaging", "VERSION_CONTROL"), encoding="utf-8") as d:
            return d.read().strip()
    except Exception:
        return ""


APP_VERSION = razlicica()


class Nastavitve:
    """Majhna shramba nastavitev Controla (jezik ipd.); isti vmesnik, kot ga Link pricakuje od brskalnika."""

    def __init__(self, pot: str) -> None:
        self.pot = pot
        self.podatki: dict = {}
        try:
            with open(pot, "r", encoding="utf-8") as d:
                self.podatki = json.load(d) or {}
        except Exception:
            self.podatki = {}

    def get(self, kljuc: str, privzeto=None):
        v = self.podatki.get(kljuc)
        if v is None and kljuc == "ui_language":
            # Jezik vmesnika: ce ima uporabnik na tem racunalniku Safeer Browser, govori Control v istem jeziku.
            v = _jezik_brskalnika()
        return v if v is not None else privzeto

    def set(self, kljuc: str, vrednost) -> None:
        self.podatki[kljuc] = vrednost
        try:
            os.makedirs(os.path.dirname(self.pot), exist_ok=True)
            zacasna = self.pot + ".tmp"
            with open(zacasna, "w", encoding="utf-8") as d:
                json.dump(self.podatki, d, ensure_ascii=False, indent=2)
            os.chmod(zacasna, 0o600)
            os.replace(zacasna, self.pot)
        except Exception:
            pass

    # Sinhronizacija zaznamkov je stvar brskalnika; Control je nima.
    def get_portals(self) -> list:
        return []

    def import_bookmarks_items(self, _postavke) -> tuple:
        return 0, 0


def _jezik_brskalnika() -> Optional[str]:
    pot = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "safeer-mint", "settings.json")
    try:
        with open(pot, "r", encoding="utf-8") as d:
            v = (json.load(d) or {}).get("ui_language")
        return str(v) if v else None
    except Exception:
        return None


def prevzemi_seznanitev_brskalnika(nastavitve: link_hub.Nastavitve, id_naprave: str, ime: str) -> bool:
    """Ce je Safeer Browser na tem racunalniku ze v Safeer Linku, Control vstopi brez nove kode.

    Brskalnikov zeton (ista datoteka istega uporabnika) Hubu dokaze, da smo isti racunalnik; Hub
    izda Controlu njegov lasten zeton (sorodna naprava, /cast/pair/sibling). Brez brskalnika ali
    s starim Hubom ostane obicajna pot s kodo. Vrne True, ce je seznanitev zdaj prevzeta.
    """
    if nastavitve.get("control_token") and nastavitve.get("hub_fp"):
        return False  # Control je ze seznanjen sam
    pot = os.path.join(link_hub.NASTAVITVE_MAPA, "link.json")
    try:
        with open(pot, "r", encoding="utf-8") as d:
            brskalnik = json.load(d) or {}
    except Exception:
        return False
    kandidati = []
    hub, zeton, odtis = brskalnik.get("hub_url"), brskalnik.get("control_token"), brskalnik.get("hub_fp")
    if hub and zeton and odtis:
        kandidati.append((str(hub), str(zeton), str(odtis)))
    seznanitve = brskalnik.get("seznanitve")
    if isinstance(seznanitve, dict):
        for fp, z in seznanitve.items():
            if isinstance(z, dict) and z.get("token") and z.get("hub_url") and (str(z["hub_url"]), str(z["token"]), str(fp)) not in kandidati:
                kandidati.append((str(z["hub_url"]), str(z["token"]), str(fp)))
    uspelo = False
    seznanitve_controla = nastavitve.get("seznanitve") if isinstance(nastavitve.get("seznanitve"), dict) else {}
    for hub, zeton, odtis in kandidati:
        if not hub.startswith("wss://"):
            continue  # zeton gre samo po TLS
        try:
            koda, odgovor, _ = link_tls.zahteva(link_hub._osnova(hub) + "/cast/pair/sibling",
                                                {"device_id": id_naprave, "name": ime}, zeton, 4.0, pripeti=odtis)
        except Exception:
            continue
        nov = odgovor.get("token") if isinstance(odgovor, dict) else None
        if koda != 200 or not nov:
            continue
        seznanitve_controla[odtis] = {"token": str(nov), "hub_url": hub}
        if not uspelo:
            nastavitve.podatki["hub_url"] = hub
            nastavitve.podatki["control_token"] = str(nov)
            nastavitve.podatki["hub_fp"] = odtis
            uspelo = True
    if uspelo:
        nastavitve.podatki["seznanitve"] = seznanitve_controla
        nastavitve.shrani()
    return uspelo


def identiteta() -> tuple:
    """Control ima v Linku svoje ime in id, da ne trka z brskalnikom na istem racunalniku."""
    ime = link_hub._ime_naprave().split(".")[0]
    return link_hub.id_naprave() + "-control", "Safeer Control (" + ime + ")"


class Samozagon:
    """Zagon ob prijavi: vnos v ~/.config/autostart (XDG), ki pozene `safeer-control --ozadje`."""

    @staticmethod
    def je_vklopljen() -> bool:
        try:
            with open(SAMOZAGON_POT, "r", encoding="utf-8") as d:
                v = d.read()
            return "safeer-control" in v and "X-GNOME-Autostart-enabled=false" not in v and "Hidden=true" not in v
        except Exception:
            return False

    @staticmethod
    def nastavi(vklopljen: bool) -> None:
        try:
            if not vklopljen:
                if os.path.exists(SAMOZAGON_POT):
                    os.remove(SAMOZAGON_POT)
                return
            os.makedirs(os.path.dirname(SAMOZAGON_POT), exist_ok=True)
            ukaz = "safeer-control --ozadje"
            if not shutil_which("safeer-control"):
                ukaz = f'"{sys.executable}" "{os.path.abspath(__file__)}" --ozadje'
            with open(SAMOZAGON_POT, "w", encoding="utf-8") as d:
                d.write("[Desktop Entry]\nType=Application\nName=Safeer Control\n"
                        "Comment=Safeer Link v ozadju (daljinec, deljenje) / Safeer Link in the background\n"
                        f"Exec={ukaz}\nIcon=safeer-control\nTerminal=false\nNoDisplay=true\n"
                        "X-GNOME-Autostart-enabled=true\nX-GNOME-Autostart-Delay=8\n")
        except Exception as e:  # noqa: BLE001
            print(f"[SafeerControl] Samozagona ni bilo mogoče nastaviti: {e}")


def shutil_which(ime: str) -> Optional[str]:
    import shutil
    return shutil.which(ime)


class Pladenj:
    """Ikona v pladnju: XApp.StatusIcon (Linux Mint/Cinnamon), sicer Gtk.StatusIcon."""

    def __init__(self, app: "SafeerControl") -> None:
        self.app = app
        self.jezik = app.nastavitve.get("ui_language")
        self.meni = Gtk.Menu()
        self.odpri = Gtk.MenuItem(label=besedilo(self.jezik, "odpri"))
        self.odpri.connect("activate", lambda *_a: app.pokazi_okno())
        self.samozagon = Gtk.CheckMenuItem(label=besedilo(self.jezik, "samozagon"))
        self.samozagon.set_active(Samozagon.je_vklopljen())
        self._preklop_id = self.samozagon.connect("toggled", self._preklop)
        self.mape = Gtk.MenuItem(label=besedilo(self.jezik, "mape"))
        self.mape.connect("activate", lambda *_a: app.izberi_mape())
        # Programi za televizor: privzeto izklopljeno; uporabnik vklopi tu in kadarkoli izklopi.
        self.programi = Gtk.CheckMenuItem(label=besedilo(self.jezik, "programi"))
        self.programi.set_active(bool(app.programi.vklopljeno))
        self._programi_id = self.programi.connect("toggled", self._preklop_programi)
        # Brskanje po celem racunalniku: privzeto izklopljeno. Vklopljeno pomeni, da televizor
        # vidi domaco mapo in koren diska, ne le izbranih map - zato je locena, zavestna izbira.
        self.ves_disk = Gtk.CheckMenuItem(label=besedilo(self.jezik, "ves_disk"))
        self.ves_disk.set_active(bool(app.datoteke.mape.ves_disk))
        self._ves_disk_id = self.ves_disk.connect("toggled", self._preklop_ves_disk)
        # Zaslon racunalnika na televizorju: privzeto izklopljeno, vklopi ga uporabnik tu.
        self.zaslon = Gtk.CheckMenuItem(label=besedilo(self.jezik, "zaslon"))
        self.zaslon.set_active(bool(app.zaslon.vklopljeno))
        self._zaslon_id = self.zaslon.connect("toggled", self._preklop_zaslon)
        # Locen zaslon za televizor: postavka se pokaze samo, kadar kaj manjka ali je prestaro.
        self.locen = Gtk.MenuItem(label="")
        self.locen.connect("activate", lambda *_a: app.namesti_locen_zaslon())
        self.koncaj = Gtk.MenuItem(label=besedilo(self.jezik, "koncaj"))
        self.koncaj.connect("activate", lambda *_a: app.koncaj())
        for m in (self.odpri, self.mape, self.ves_disk, self.programi, self.zaslon, self.locen, Gtk.SeparatorMenuItem(),
                  self.samozagon, Gtk.SeparatorMenuItem(), self.koncaj):
            self.meni.append(m)
        self.meni.show_all()
        self.osvezi_locen()
        self.ikona = None
        self.xapp = None
        ikona = "safeer-control"
        try:
            if not Gtk.IconTheme.get_default().has_icon(ikona):
                ikona = os.path.join(KOREN, "assets", "icon.png")  # zagon iz izvorne kode brez namescene teme
        except Exception:
            pass
        try:
            gi.require_version("XApp", "1.0")
            from gi.repository import XApp  # noqa: WPS433
            self.xapp = XApp.StatusIcon()
            self.xapp.set_icon_name(ikona)
            self.xapp.set_name("safeer-control")
            self.xapp.set_secondary_menu(self.meni)
            self.xapp.connect("activate", lambda *_a: app.pokazi_okno())
        except Exception:
            self.ikona = Gtk.StatusIcon()
            if os.path.isabs(ikona):
                self.ikona.set_from_file(ikona)
            else:
                self.ikona.set_from_icon_name(ikona)
            self.ikona.set_title("Safeer Control")
            self.ikona.connect("activate", lambda *_a: app.pokazi_okno())
            self.ikona.connect("popup-menu", lambda ikona, gumb, cas: self.meni.popup(None, None, Gtk.StatusIcon.position_menu, ikona, gumb, cas))
        self.stanje(False)

    def stanje(self, povezan: bool) -> None:
        napis = besedilo(self.jezik, "povezan" if povezan else "ni")
        try:
            if self.xapp is not None:
                self.xapp.set_tooltip_text(napis)
            elif self.ikona is not None:
                self.ikona.set_tooltip_text(napis)
        except Exception:
            pass

    def _preklop_programi(self, postavka: Gtk.CheckMenuItem) -> None:
        self.app.nastavi_programe(bool(postavka.get_active()))

    def _preklop_ves_disk(self, postavka: Gtk.CheckMenuItem) -> None:
        self.app.nastavi_ves_disk(bool(postavka.get_active()))

    def _preklop_zaslon(self, postavka: Gtk.CheckMenuItem) -> None:
        self.app.nastavi_zaslon(bool(postavka.get_active()))

    def _preklop(self, element) -> None:
        self.app.nastavi_samozagon(element.get_active())

    def osvezi_locen(self) -> None:
        """Napis in vidnost postavke za locen zaslon po trenutnem stanju racunalnika."""
        s = self.app.stanje_locenega()
        if s is None:
            self.locen.hide()
            return
        if link_sway.paketi_za_namestitev(s) and s.get("orodja"):
            self.locen.set_label(besedilo(self.jezik, "locen_posodobi" if s.get("posodobitev") and not s.get("manjka")
                                          else "locen_namesti"))
            self.locen.set_sensitive(True)
        else:
            self.locen.set_label(besedilo(self.jezik, "locen_ni"))
            self.locen.set_sensitive(False)
        self.locen.show()

    def osvezi_samozagon(self) -> None:
        self.samozagon.handler_block(self._preklop_id)
        self.samozagon.set_active(Samozagon.je_vklopljen())
        self.samozagon.handler_unblock(self._preklop_id)


class SafeerControl(Gtk.Application):
    def __init__(self, ozadje: bool = False) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.link: Optional[SafeerLink] = None
        self.nastavitve = Nastavitve(os.path.join(NASTAVITVE_MAPA, "control.json"))
        self.web_context = WebKit2.WebContext.get_default()
        self.gledalec: Optional[Gtk.Window] = None
        # --ozadje: brez okna, z ikono v pladnju; okno se odpre iz pladnja ali ob ponovnem zagonu iz menija.
        self.ozadje = ozadje
        self.pladenj: Optional[Pladenj] = None
        self._prva_aktivacija = True
        # Deljene mape za televizor; seznam poti je v control.json ("deljene_mape").
        mape = self.nastavitve.get("deljene_mape")
        self.datoteke = link_datoteke.Datoteke(mape if isinstance(mape, list) else [],
                                              ves_disk=bool(self.nastavitve.get("ves_disk_za_tv", False)))
        self.datoteke.ob_spremembi = lambda poti: self.nastavitve.set("deljene_mape", poti)
        # Programi racunalnika za televizor; privzeto izklopljeno ("programi_za_tv" v control.json).
        self.programi = link_programi.Programi(bool(self.nastavitve.get("programi_za_tv", False)))
        self.programi.ob_spremembi = lambda vklopljeno: self.nastavitve.set("programi_za_tv", bool(vklopljeno))
        # Zaslon racunalnika na televizorju; privzeto izklopljeno ("zaslon_za_tv" v control.json).
        self.zaslon = link_zaslon.Zaslon(vklopljeno=bool(self.nastavitve.get("zaslon_za_tv", False)))
        self.zaslon.ob_spremembi = lambda vklopljeno: self.nastavitve.set("zaslon_za_tv", bool(vklopljeno))
        # Locen zaslon za televizor: programi s televizorja tecejo na drugem, nevidnem zaslonu in ne
        # posegajo v uporabnikovega ("locen_zaslon_za_tv" v control.json, privzeto vklopljeno, kjer je mogoce).
        # Navidezni zvocni izhodi, ki jih je pustil prejsnji (ubit ali sesut) Control.
        link_sway.pocisti_zvok()
        self.drugi_zaslon = (link_sway.DrugiZaslon()
                             if self.nastavitve.get("locen_zaslon_za_tv", True) and link_sway.DrugiZaslon.mozno()
                             else None)
        self.programi.drugi = self.drugi_zaslon
        self.zaslon.drugi = self.drugi_zaslon
        # Zvok racunalnika na televizorju ali tablici (Safeer OS: stran Zvok). Navidezni izhod, ki ga je
        # pustil prejsnji (ubit) Control, pospravimo takoj - sicer bi zvok sel v prazno.
        self.zvok = link_zvok.ZvokNaNapravo()
        self.zvok.ustavi()

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        # Safeer OS (stikalo »Zaupaj temu računalniku«) klice to dejanje prek D-Bus (org.gtk.Actions).
        zaupanje = Gio.SimpleAction.new("zaupanje", GLib.VariantType.new("b"))
        zaupanje.connect("activate", self._na_zaupanje)
        self.add_action(zaupanje)
        # Safeer OS: prijavno okno, »Poveži novo napravo« in »Odjavi ta računalnik«.
        for ime, klic in (("prijava", self.prijava_iz_os), ("nova-naprava", self.nova_naprava),
                          ("odjava", self.odjava), ("zvok-ustavi", self.zvok_ustavi)):
            dejanje = Gio.SimpleAction.new(ime, None)
            dejanje.connect("activate", lambda _d, _v, k=klic: k())
            self.add_action(dejanje)
        # Safeer OS: »Predvajaj na« - zvok racunalnika na napravo v Safeer Linku (id naprave).
        zvok = Gio.SimpleAction.new("zvok-na-napravo", GLib.VariantType.new("s"))
        zvok.connect("activate", lambda _d, v: self.zvok_na_napravo(v.get_string()))
        self.add_action(zvok)
        if self.ozadje:
            self.hold()  # brez okna bi se GApplication koncal; ikona v pladnju ga drzi
        self._izvozi_naprave()

    # ------------------------------------------------------------------ D-Bus za Safeer OS: naprave in njihovi programi
    VMESNIK_NAPRAVE = """
    <node><interface name="io.github.memelandfaner.SafeerControl.Naprave">
      <method name="Seznam"><arg type="s" name="json" direction="out"/></method>
      <method name="Aplikacije"><arg type="s" name="naprava" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="Zazeni"><arg type="s" name="naprava" direction="in"/><arg type="s" name="app" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="Preimenuj"><arg type="s" name="naprava" direction="in"/><arg type="s" name="ime" direction="in"/><arg type="s" name="json" direction="out"/></method>
    </interface></node>"""

    def _izvozi_naprave(self) -> None:
        """Safeer OS (locen proces) prek tega vmesnika naste naprave v Linku, njihove programe (apps.list) in
        jih zazene (apps.launch). Klici cakajo na odgovor naprave, zato tecejo v ozadju, ne na glavni niti."""
        try:
            vodilo = self.get_dbus_connection() or Gio.bus_get_sync(Gio.BusType.SESSION, None)
            info = Gio.DBusNodeInfo.new_for_xml(self.VMESNIK_NAPRAVE)
            vodilo.register_object(CONTROL_POT + "/naprave", info.interfaces[0], self._klic_naprave, None, None)
        except Exception as e:  # noqa: BLE001
            print("[SafeerControl] D-Bus Naprave:", e)

    def _klic_naprave(self, _vodilo, _posiljatelj, _pot, _vmesnik, metoda, parametri, klic) -> None:
        argumenti = list(parametri.unpack())

        def delo() -> None:
            try:
                izid = self._naprave_metoda(metoda, argumenti)
            except Exception as e:  # noqa: BLE001
                izid = {"ok": False, "message": str(e)}
            klic.return_value(GLib.Variant("(s)", (json.dumps(izid, ensure_ascii=True),)))
        threading.Thread(target=delo, name="safeer-dbus-naprave", daemon=True).start()

    def _naprave_metoda(self, metoda: str, a: list) -> dict:
        if self.link is None:
            self._pripravi_link()
        link = self.link
        if metoda == "Seznam":
            return {"ok": True, "naprave": [
                {"id": n.get("id", ""), "ime": n.get("ime", ""), "zmoznosti": n.get("zmoznosti") or [],
                 "platforma": n.get("platforma", ""), "vrsta": n.get("vrsta", ""),
                 "ta": n.get("id", "") == link._id()} for n in link.naprave]}
        if metoda == "Preimenuj":
            # Ime hrani sredisce (/cast/devices/rename) in ga vidijo vse naprave; prazno vrne prvotno ime.
            if not (link._hub() and link._zeton() and link._odtis()):
                return {"ok": False, "koda": "hub_ni_znan"}
            ok, novo, n = link_deljenje.preimenuj_napravo(link._hub(), link._zeton() or "", link._odtis() or "",
                                                          str(a[0]) if a else "", str(a[1]) if len(a) > 1 else "")
            return {"ok": bool(ok), "ime": novo, "message": "" if ok else n.get("sporocilo", "")}
        if metoda == "Aplikacije":
            id_naprave = str(a[0]) if a else ""
            # Po kosih (racunalnik daje najvec 60 z ikonami na sporocilo); Android vrne vse naenkrat.
            vsi, od = [], 0
            for _ in range(20):
                r = link.ukaz_pocakaj(id_naprave, "apps.list", {"icons": True, "offset": od, "limit": 60}, cas=20.0)
                if not r.get("ok"):
                    return r
                d = r.get("data") or {}
                kos = d.get("items") if isinstance(d.get("items"), list) else []
                vsi += kos
                skupaj = int(d.get("total") or len(vsi))
                od = int(d.get("offset") or 0) + len(kos)
                if not kos or od >= skupaj:
                    break
            return {"ok": True, "items": vsi, "enabled": bool((r.get("data") or {}).get("enabled", True))}
        if metoda == "Zazeni":
            return link.ukaz_pocakaj(str(a[0]) if a else "", "apps.launch", {"app": str(a[1]) if len(a) > 1 else ""})
        return {"ok": False, "message": "neznana metoda"}

    def _pripravi_link(self) -> None:
        nastavitve_linka = link_hub.Nastavitve(os.path.join(NASTAVITVE_MAPA, "link.json"))
        id_naprave, ime = identiteta()
        try:
            # Racunalniku, ki mu uporabnik ni zaupal, seznanitve brskalnika ne prevzemamo: ob novi prijavi
            # mora biti prijavno okno, ne tiha povezava (core/link_seja.py).
            if nastavitve_linka.get("zaupana") is not False and \
                    prevzemi_seznanitev_brskalnika(nastavitve_linka, id_naprave, ime):
                print("[SafeerControl] Seznanitev prevzeta od Safeer Browserja (brez kode).")
        except Exception as e:  # noqa: BLE001
            print(f"[SafeerControl] Seznanitve brskalnika ni bilo mogoče prevzeti: {e}")
        self.link = SafeerLink(
            None, self.nastavitve,
            trenutna_stran=lambda: {},
            odpri_naslov=self.odpri_naslov,
            koren_programa=KOREN,
            dovoli_potrdilo=self.dovoli_potrdilo,
            nastavitve=nastavitve_linka,
            identiteta=(id_naprave, ime),
            control=True,
            ob_zaprtju=self.ob_zaprtju_okna,
        )
        self.link.ob_povezavi = self._na_povezavo
        self.link.ob_brez_povezave = self.odpri_safeer_os
        self.link.ob_seznanitvi = self._po_seznanitvi
        self.link.datoteke = self.datoteke
        self.link.programi = self.programi
        self.link.zaslon = self.zaslon
        self.link.zvok = self.zvok
        self.zvok.ob_spremembi = lambda _opis: self.link.zapisi_stanje_za_os() if self.link is not None else None

    # ------------------------------------------------------------------ Safeer OS
    _iz_os = False

    def prijava_iz_os(self) -> None:
        """Safeer OS pokaze prijavno okno (QR / koda / brez povezave). Okno je nad Safeer OS; po prijavi
        ali »brez povezave« se zapre in uporabnik je spet v Safeer OS."""
        if self.link is None:
            self._pripravi_link()
        self._iz_os = True
        if self.link.nastavitve.get("brez_povezave"):
            self.link._povezi_naprave()        # prej izbral »brez povezave«: spet prijavno okno
        self.pokazi_okno()
        if self.link.okno is not None:
            self.link.okno.set_keep_above(True)
            self.link.okno.present()

    def nova_naprava(self) -> None:
        """»Poveži novo napravo« iz Safeer OS: okno Control z QR kodo za nov telefon ali tablico."""
        if self.link is None:
            self._pripravi_link()
        koda = "window.safeerLinkOdpri && safeerLinkOdpri('novaNaprava')"
        nalozena = self.link.pogled is not None
        self.link.ob_nalozitvi_js = "" if nalozena else koda
        self.pokazi_okno()
        if nalozena:
            self.link._js(koda)
        if self.link.okno is not None:
            self.link.okno.present()

    def odjava(self) -> None:
        """»Odjavi ta računalnik« iz Safeer OS: sredisce ga pozabi, ob naslednjem odprtju je prijavno okno."""
        if self.link is None:
            self._pripravi_link()
        self.link._v_ozadju(self.link._pozabi_napravo)

    def zvok_na_napravo(self, id_naprave: str) -> None:
        if self.link is None:
            self._pripravi_link()
        self.link._v_ozadju(lambda: self.link.zvok_na_napravo(str(id_naprave or "")))

    def zvok_ustavi(self) -> None:
        if self.link is None:
            self.zvok.ustavi()
            return
        self.link._v_ozadju(self.link.zvok_ustavi)

    def _po_seznanitvi(self) -> None:
        if not self._iz_os:
            return
        self._iz_os = False

        def nazaj():
            if self.link is not None and self.link.okno is not None:
                self.link.okno.set_keep_above(False)
            self.odpri_safeer_os()
            return False
        GLib.timeout_add(2500, nazaj)      # »Prijavljeno« ostane vidno, nato nazaj v Safeer OS

    def _na_zaupanje(self, _dejanje, vrednost) -> None:
        if self.link is None:
            self._pripravi_link()
        self.link.nastavi_zaupanje(bool(vrednost.get_boolean()))

    def nastavi_zaslon(self, vklopljeno: bool) -> None:
        """Televizor sme (ali ne sme vec) videti zaslon tega racunalnika. Izklop takoj konca sejo;
        zmoznost `desktop` se javi ali odpade ob naslednji povezavi."""
        self.zaslon.nastavi(vklopljeno)
        if self.link is not None:
            try:
                self.link.povezi_v_ozadju()
            except Exception:
                pass

    def stanje_locenega(self) -> Optional[dict]:
        """None, kadar je locen zaslon ze pripravljen, izklopljen ali ga ta racunalnik ne zmore
        (brez graficne kartice); sicer kaj manjka (link_sway.stanje_namestitve)."""
        if self.drugi_zaslon is not None or not self.nastavitve.get("locen_zaslon_za_tv", True):
            return None
        s = link_sway.stanje_namestitve()
        if not s.get("graficna") or not (s.get("manjka") or s.get("prestar")):
            return None
        return s

    def namesti_locen_zaslon(self) -> None:
        """Na uporabnikov klik: vprasa, nato namesti ali posodobi pakete (geslo vpise v sistemsko okno)."""
        s = self.stanje_locenega()
        ukaz = link_sway.ukaz_namestitve(s) if s else None
        if not ukaz:
            return
        jezik = self.nastavitve.get("ui_language")
        vprasanje = Gtk.MessageDialog(message_type=Gtk.MessageType.QUESTION, buttons=Gtk.ButtonsType.CANCEL,
                                      text="Safeer Control")
        vprasanje.format_secondary_text(besedilo(jezik, "locen_vprasanje").format(
            paketi=", ".join(link_sway.paketi_za_namestitev(s))))
        vprasanje.add_button(besedilo(jezik, "locen_gumb"), Gtk.ResponseType.OK)
        odgovor = vprasanje.run()
        vprasanje.destroy()
        if odgovor != Gtk.ResponseType.OK:
            return

        def tece() -> None:
            try:
                koda = subprocess.run(ukaz, capture_output=True, timeout=1800).returncode
            except Exception:
                koda = 1
            GLib.idle_add(konec, koda)

        def konec(koda: int) -> bool:
            link_sway.wf_zmoznosti(osvezi=True)
            if koda == 0 and link_sway.DrugiZaslon.mozno():
                self.drugi_zaslon = link_sway.DrugiZaslon()
                self.programi.drugi = self.drugi_zaslon
                self.zaslon.drugi = self.drugi_zaslon
                sporocilo, vrsta = besedilo(jezik, "locen_uspeh"), Gtk.MessageType.INFO
            else:
                sporocilo, vrsta = besedilo(jezik, "locen_napaka"), Gtk.MessageType.WARNING
            okno = Gtk.MessageDialog(message_type=vrsta, buttons=Gtk.ButtonsType.OK, text="Safeer Control")
            okno.format_secondary_text(sporocilo)
            okno.run()
            okno.destroy()
            if self.pladenj is not None:
                self.pladenj.osvezi_locen()
            return False

        import threading
        threading.Thread(target=tece, name="safeer-namestitev", daemon=True).start()

    def nastavi_ves_disk(self, vklopljeno: bool) -> None:
        """Televizor sme (ali ne sme vec) brskati po celem racunalniku, ne le po izbranih mapah.
        Velja takoj; nastavitev se zapomni ("ves_disk_za_tv" v control.json)."""
        self.datoteke.nastavi_ves_disk(vklopljeno)
        self.nastavitve.set("ves_disk_za_tv", bool(vklopljeno))

    def nastavi_programe(self, vklopljeno: bool) -> None:
        """Televizor sme (ali ne sme vec) videti programe tega racunalnika. Sprememba velja takoj:
        ob naslednji povezavi se zmoznost `apps` javi ali odpade."""
        self.programi.nastavi(bool(vklopljeno))
        if self.link is not None:
            try:
                self.link.povezi_v_ozadju()   # zmoznost `apps` se javi (ali odpade) ob novi povezavi
            except Exception:
                pass

    def izberi_mape(self) -> None:
        """Izbira map za televizor iz pladnja (isti pogovor kot na strani Control)."""
        if self.link is None:
            self._pripravi_link()
        self.link.dodaj_deljeno_mapo()

    def _na_povezavo(self, povezan: bool) -> None:
        if self.pladenj is not None:
            GLib.idle_add(lambda: (self.pladenj.stanje(povezan), False)[1])
        # Prvic seznanjen racunalnik: od zdaj naprej se Control zaganja ob prijavi, da ga naprave vidijo.
        if povezan and not self.nastavitve.get("samozagon_nastavljen"):
            self.nastavitve.set("samozagon_nastavljen", True)
            if self.nastavitve.get("samozagon", True):
                Samozagon.nastavi(True)
                if self.pladenj is not None:
                    GLib.idle_add(lambda: (self.pladenj.osvezi_samozagon(), False)[1])

    def nastavi_samozagon(self, vklopljen: bool) -> None:
        self.nastavitve.set("samozagon", bool(vklopljen))
        self.nastavitve.set("samozagon_nastavljen", True)
        Samozagon.nastavi(bool(vklopljen))

    def ob_zaprtju_okna(self) -> None:
        # Z ikono v pladnju zapiranje okna Control samo skrije; Link tece naprej.
        if self.pladenj is None:
            self.quit()

    def koncaj(self) -> None:
        self.koncaj_brez_izhoda()
        self.quit()

    def koncaj_brez_izhoda(self) -> None:
        """Pospravi povezavo, deljene mape in zaslon (ob izhodu in pred zagonom nove razlicice)."""
        try:
            if self.link is not None and self.link.povezava is not None:
                self.link.povezava.zapri()
        except Exception:
            pass
        try:
            self.datoteke.ustavi()
        except Exception:
            pass
        try:
            self.zvok.ustavi()
        except Exception:
            pass
        try:
            self.zaslon.ustavi()
            if self.drugi_zaslon is not None:
                self.drugi_zaslon.ustavi()
        except Exception:
            pass

    def odpri_safeer_os(self) -> None:
        """»Nadaljuj brez povezave naprav« v prijavnem oknu: odpre Safeer OS na tem racunalniku, Control
        gre v pladenj. Dokler Safeer OS za racunalnik ni namescen, to okno to posteno pove."""
        self._iz_os = False
        if self.link is not None and self.link.okno is not None:
            self.link.okno.set_keep_above(False)
        ukaz = None
        pot = shutil_which("safeer-os")
        if pot:
            ukaz = [pot]
        else:
            skripta = os.path.join(KOREN, "safeer_os.py")
            if os.path.isfile(skripta):
                ukaz = [sys.executable, skripta]
        if not ukaz:
            if self.link is not None:
                self.link._odziv("brezPovezave", {"os": False})
            return
        try:
            subprocess.Popen(ukaz, start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:  # noqa: BLE001
            print(f"[SafeerControl] Safeer OS se ni odprl: {e}")
            if self.link is not None:
                self.link._odziv("brezPovezave", {"os": False})
            return
        if self.link is not None and self.link.okno is not None:
            # S pladnjem se okno umakne tja; brez njega (zagon iz menija) ga le pomanjsamo, da ne izgine.
            if getattr(self, "pladenj", None) is not None:
                self.link.okno.hide()
            else:
                self.link.okno.iconify()

    def pokazi_okno(self) -> None:
        if self.link is None:
            self._pripravi_link()
        if self.link.okno is not None:
            self.link.okno.present()
            return
        self.link.pokazi()
        if self.link.okno is not None:
            self.add_window(self.link.okno)

    def do_activate(self) -> None:
        if self.ozadje and self._prva_aktivacija:
            self._prva_aktivacija = False
            if self.link is None:
                self._pripravi_link()
            self.pladenj = Pladenj(self)
            self.link.povezi_v_ozadju()
            if os.environ.pop("SAFEER_CONTROL_ODPRI", "") == "1":
                self.pokazi_okno()
            return
        self._prva_aktivacija = False
        # Program je tekel v ozadju, medtem pa je bil posodobljen: namesto starega okna odpremo novo
        # razlicico (uporabniku ni treba vedeti, da je bilo treba kaj znova zagnati).
        if self._koda_posodobljena() and (self.link is None or self.link.okno is None):
            self._znova_zazeni()
            return
        self.pokazi_okno()

    _ZAGNAN_OB = time.time()
    _DATOTEKE_KODE = ("safeer_control.py", "core/safeer_link.py", "core/link_hub.py",
                      "assets/link/link.js", "assets/link/index.html", "assets/link/daljinec.js")

    def _koda_posodobljena(self) -> bool:
        for ime in self._DATOTEKE_KODE:
            try:
                if os.path.getmtime(os.path.join(KOREN, ime)) > self._ZAGNAN_OB + 1:
                    return True
            except OSError:
                continue
        return False

    def _znova_zazeni(self) -> None:
        print("[SafeerControl] Koda je posodobljena; zaganjam novo razlicico.")
        try:
            self.koncaj_brez_izhoda()
        except Exception:
            pass
        # Pladenj ostane (--ozadje), okno pa se odpre takoj, ker ga je uporabnik pravkar zahteval.
        argv = [a for a in sys.argv if a != "--ozadje"] + ["--ozadje"]
        os.environ["SAFEER_CONTROL_ODPRI"] = "1"
        os.execv(sys.executable, [sys.executable] + argv)

    # ------------------------------------------------------------------
    # Odpiranje naslovov: gledalec zaslona s Huba v svojem oknu, vse drugo v sistemskem brskalniku
    # ------------------------------------------------------------------

    def dovoli_potrdilo(self, pem: str, gostitelj: str) -> None:
        try:
            potrdilo = Gio.TlsCertificate.new_from_pem(pem, -1)
            self.web_context.allow_tls_certificate_for_host(potrdilo, gostitelj)
        except Exception as e:  # noqa: BLE001
            print(f"[SafeerControl] Potrdila Huba ni bilo mogoče dovoliti: {e}")

    def _je_s_huba(self, url: str) -> bool:
        try:
            hub = self.link._hub() if self.link is not None else ""
            if not hub:
                return False
            from urllib.parse import urlparse
            return urlparse(url).hostname == urlparse(link_hub._osnova(hub)).hostname
        except Exception:
            return False

    def odpri_naslov(self, url: str) -> None:
        cist = (url or "").strip()
        if not (cist.startswith("http://") or cist.startswith("https://")):
            return
        if self._je_s_huba(cist):
            self._odpri_gledalca(cist)
            return
        # Prejete strani in povezave odpre brskalnik, ki ga uporabnik ze ima (ce je to Safeer, toliko bolje).
        try:
            Gio.AppInfo.launch_default_for_uri(cist, None)
        except Exception:
            try:
                subprocess.Popen(["xdg-open", cist])
            except Exception as e:  # noqa: BLE001
                print(f"[SafeerControl] Naslova ni bilo mogoče odpreti: {e}")

    # Okno gledalca: dotik, poteg in tipke z miske in tipkovnice gredo na napravo, katere zaslon gledamo
    # (Safeer Vnos na tablici). Slika je v <img id="zaslon"> z object-fit: contain; koordinate
    # preracunamo v delez prave slike, da sirina okna ali crni robovi ne zamaknejo dotika.
    GLEDALEC_VNOS_JS = r"""
(function () {
  function poslji(d, p) {
    try { window.webkit.messageHandlers.safeerVnos.postMessage(JSON.stringify({d: d, p: p})); } catch (e) {}
  }
  function delez(img, x, y) {
    var r = img.getBoundingClientRect();
    var nw = img.naturalWidth || 1, nh = img.naturalHeight || 1;
    var m = Math.min(r.width / nw, r.height / nh);
    var w = nw * m, h = nh * m;
    var ox = r.left + (r.width - w) / 2, oy = r.top + (r.height - h) / 2;
    var fx = (x - ox) / w, fy = (y - oy) / h;
    if (fx < 0 || fy < 0 || fx > 1 || fy > 1) return null;
    return {x: fx, y: fy};
  }
  var zacetek = null, cas = 0, tipkano = "", casovnik = null;
  document.addEventListener("mousedown", function (e) {
    var img = document.getElementById("zaslon");
    if (!img || e.button !== 0) return;
    zacetek = delez(img, e.clientX, e.clientY); cas = Date.now();
    e.preventDefault();
  }, true);
  document.addEventListener("mouseup", function (e) {
    var img = document.getElementById("zaslon");
    if (!img || !zacetek || e.button !== 0) return;
    var konec = delez(img, e.clientX, e.clientY) || zacetek;
    var trajanje = Math.max(60, Math.min(1500, Date.now() - cas));
    if (Math.abs(konec.x - zacetek.x) + Math.abs(konec.y - zacetek.y) > 0.02) {
      poslji("input.swipe", {x1: zacetek.x, y1: zacetek.y, x2: konec.x, y2: konec.y, ms: trajanje});
    } else {
      poslji("input.tap", {x: zacetek.x, y: zacetek.y, ms: trajanje > 450 ? 700 : 60});
    }
    zacetek = null;
  }, true);
  document.addEventListener("wheel", function (e) {
    var img = document.getElementById("zaslon");
    if (!img) return;
    var t = delez(img, e.clientX, e.clientY);
    if (!t) return;
    var dy = e.deltaY > 0 ? -0.25 : 0.25;
    poslji("input.swipe", {x1: t.x, y1: t.y, x2: t.x, y2: Math.max(0, Math.min(1, t.y + dy)), ms: 250});
    e.preventDefault();
  }, {capture: true, passive: false});
  document.addEventListener("contextmenu", function (e) { e.preventDefault(); poslji("input.key", {key: "back"}); }, true);
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" || e.key === "BrowserBack") { poslji("input.key", {key: "back"}); e.preventDefault(); return; }
    if (e.key === "Home") { poslji("input.key", {key: "home"}); e.preventDefault(); return; }
    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      tipkano += e.key; e.preventDefault();
      clearTimeout(casovnik);
      casovnik = setTimeout(function () { if (tipkano) poslji("input.text", {text: tipkano}); tipkano = ""; }, 250);
    }
  }, true);
})();
"""

    def _odpri_gledalca(self, url: str) -> None:
        """Deljen zaslon druge naprave: stran gledalca s Huba v svojem oknu Controla. Ce naprava to
        zna (Safeer Vnos na tablici), jo iz tega okna upravljas z misko in tipkovnico."""
        if self.gledalec is None:
            upravitelj = WebKit2.UserContentManager()
            upravitelj.register_script_message_handler("safeerVnos")
            upravitelj.connect("script-message-received::safeerVnos", self._vnos_iz_gledalca)
            upravitelj.add_script(WebKit2.UserScript(
                self.GLEDALEC_VNOS_JS,
                WebKit2.UserContentInjectedFrames.TOP_FRAME,
                WebKit2.UserScriptInjectionTime.END,
                None, None,
            ))
            pogled = WebKit2.WebView(web_context=self.web_context, user_content_manager=upravitelj)
            nastavitve = pogled.get_settings()
            nastavitve.set_property("enable-developer-extras", False)
            okno = Gtk.Window(title="Safeer Control — zaslon")
            okno.set_default_size(960, 600)
            okno.add(pogled)

            def zaprto(*_a):
                self.gledalec = None
            okno.connect("destroy", zaprto)
            self.add_window(okno)
            self.gledalec = okno
            self._vnos_nastavitve_odprte = False
            okno.show_all()
            if self.link is not None:
                self.link.ob_odzivu_vnosa = self._odziv_vnosa
        pogled = self.gledalec.get_child()
        pogled.load_uri(url)
        self.gledalec.present()

    def _vnos_iz_gledalca(self, _upravitelj, rezultat) -> None:
        """Dotik/tipka iz okna gledalca -> ukaz input.* napravi, katere zaslon gledamo."""
        try:
            sporocilo = json.loads(rezultat.get_js_value().to_string())
            dejanje = str(sporocilo.get("d", ""))
            parametri = sporocilo.get("p") if isinstance(sporocilo.get("p"), dict) else {}
        except Exception:
            return
        if self.link is not None and dejanje.startswith("input."):
            self.link.poslji_vnos(dejanje, parametri)

    def _odziv_vnosa(self, odziv: dict) -> None:
        """Naprava vnosa ne sprejme: v naslovu okna povemo, kaj naj uporabnik naredi (enkrat)."""
        if self.gledalec is None:
            return
        if odziv.get("ok"):
            self.gledalec.set_title("Safeer Control — zaslon")
        elif odziv.get("koda") == "vnos_ni_vklopljen":
            self.gledalec.set_title("Safeer Control — zaslon · na tablici vklopi Safeer Vnos "
                                    "(Dostopnost → Nameščene aplikacije → Safeer Vnos)")
            # Uporabniku ni treba iskati: tablica sama odpre nastavitve, ki jih potrebuje (enkrat na okno).
            if not getattr(self, "_vnos_nastavitve_odprte", False) and self.link is not None:
                self._vnos_nastavitve_odprte = True
                self.link.poslji_vnos("input.enable", {})


def main() -> int:
    if "--version" in sys.argv[1:]:
        print(f"Safeer Control {APP_VERSION}")
        return 0
    # Sled ob sesutju in dnevnik neujetih izjem (~/.cache/safeer-control/). Control tece ves dan v
    # ozadju; brez tega naprave samo izgubijo racunalnik in nihce ne ve, zakaj.
    os_stabilnost.vkljuci("safeer-control")
    ozadje = "--ozadje" in sys.argv[1:]
    argv = [a for a in sys.argv if a != "--ozadje"]
    GLib.set_prgname("safeer-control")
    GLib.set_application_name("Safeer Control")
    app = SafeerControl(ozadje=ozadje)
    # Ob SIGTERM (odjava, posodobitev paketa) pospravimo kot ob Izhodu: sicer bi locen zaslon s
    # programi ostal tece nevidno in brez lastnika - nihce ga ne bi vec videl ne zaprl.
    try:
        import signal as _signal
        for _sig in (_signal.SIGTERM, _signal.SIGINT):
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, _sig, lambda *_a: (app.koncaj(), False)[1])
    except Exception:
        pass
    return app.run(argv)


if __name__ == "__main__":
    sys.exit(main())
