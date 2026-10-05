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
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, Gio, GLib, Gtk, WebKit2  # noqa: E402

from core import link_daljinec, link_datoteke, link_deljenje, link_hub, link_programi, link_sway, link_tls, link_zaslon, link_zvok  # noqa: E402
from core import budnost, os_posodobitve, os_stabilnost  # noqa: E402
from core import link_internet, link_internet_posrednik, sistemski_posrednik  # noqa: E402
from core.link_gledalec import (Gledalec, OKVIR_OBVESTILO, OKVIR_SLIKA,  # noqa: E402
                                izberi_ponor, niz_cevovoda, preslikaj_tipko,
                                preslikaj_tocko)
from core.safeer_link import SafeerLink  # noqa: E402

APP_ID = "io.github.memelandfaner.SafeerControl"
CONTROL_POT = "/io/github/memelandfaner/SafeerControl"
NASTAVITVE_MAPA = os.path.expanduser("~/.config/safeer-control")
#: Safeer OS na tem racunalniku (D-Bus): sprejeta ponudba "Poslji na napravo" gre njemu.
OS_ID = "io.github.memelandfaner.SafeerOS"
SAMOZAGON_POT = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "autostart", "safeer-control.desktop")

# Besedila pladnja v jezikih vmesnika (isti nabor kot Safeer Browser).
BESEDILA = {
    "sl": {"posodobi": "Posodobi: {opis} …", "posodobi_prenasam": "Prenašam {ime} …", "posodobi_namescam": "Nameščam … (vpiši geslo, če te sistem vpraša)", "posodobi_koncano": "Nameščeno: {opis}. Nova različica se zažene ob naslednjem zagonu.", "posodobi_napaka": "Posodobitev ni uspela: {napaka}", "posodobi_naslov": "Posodobitev Safeer", "locen_namesti": "Namesti ločen zaslon za televizor …", "locen_posodobi": "Posodobi wf-recorder za ločen zaslon …", "locen_ni": "Ločen zaslon za televizor: wf-recorder je prestar", "locen_vprasanje": "Za ločen zaslon za televizor Safeer Control potrebuje pakete: {paketi}. Programi, ki jih zaženeš s televizorja, se bodo odprli na svojem zaslonu in ne bodo motili tvojega namizja.\n\nNamestim jih zdaj? Sistem te bo vprašal za geslo.", "locen_uspeh": "Ločen zaslon za televizor je pripravljen.", "locen_napaka": "Namestitev ni uspela. Programi s televizorja se še naprej odpirajo na namizju.", "locen_gumb": "Namesti", "odpri": "Odpri Safeer Control", "samozagon": "Zaženi ob prijavi", "mape": "Mape za televizor …", "programi": "Programi za televizor", "ves_disk": "Ves računalnik za televizor", "zaslon": "Zaslon za televizor", "predvajanje": "Predvajanje za druge naprave", "ponudba_naslov": "Pošlji na napravo", "ponudba": "{naprava} ti pošilja: {kaj}", "sprejmi": "Sprejmi", "zavrni": "Zavrni", "koncaj": "Končaj", "povezan": "Safeer Link: povezan", "ni": "Safeer Link: ni povezave"},
    "en": {"posodobi": "Update: {opis}…", "posodobi_prenasam": "Downloading {ime}…", "posodobi_namescam": "Installing… (enter your password if the system asks)", "posodobi_koncano": "Installed: {opis}. The new version starts with the next launch.", "posodobi_napaka": "The update did not go through: {napaka}", "posodobi_naslov": "Safeer update", "locen_namesti": "Install the separate TV screen…", "locen_posodobi": "Update wf-recorder for the separate TV screen…", "locen_ni": "Separate TV screen: wf-recorder is too old", "locen_vprasanje": "For the separate TV screen Safeer Control needs these packages: {paketi}. Programs you start from the TV will open on their own screen and will not disturb your desktop.\n\nInstall them now? The system will ask for your password.", "locen_uspeh": "The separate TV screen is ready.", "locen_napaka": "Installation failed. Programs from the TV keep opening on your desktop.", "locen_gumb": "Install", "odpri": "Open Safeer Control", "samozagon": "Start at login", "mape": "Folders for the TV…", "programi": "Apps for the TV", "ves_disk": "Whole computer for the TV", "zaslon": "Screen for the TV", "predvajanje": "Playback for other devices", "ponudba_naslov": "Send to device", "ponudba": "{naprava} is sending you: {kaj}", "sprejmi": "Accept", "zavrni": "Decline", "koncaj": "Quit", "povezan": "Safeer Link: connected", "ni": "Safeer Link: not connected"},
    "de": {"posodobi": "Aktualisieren: {opis} …", "posodobi_prenasam": "Lade {ime} herunter …", "posodobi_namescam": "Installiere … (gib dein Passwort ein, wenn das System fragt)", "posodobi_koncano": "Installiert: {opis}. Die neue Version startet beim nächsten Start.", "posodobi_napaka": "Das Update hat nicht geklappt: {napaka}", "posodobi_naslov": "Safeer-Update", "locen_namesti": "Separaten Bildschirm für den Fernseher installieren …", "locen_posodobi": "wf-recorder für den separaten Bildschirm aktualisieren …", "locen_ni": "Separater Bildschirm: wf-recorder ist zu alt", "locen_vprasanje": "Für den separaten Bildschirm braucht Safeer Control diese Pakete: {paketi}. Programme, die du vom Fernseher startest, öffnen sich auf einem eigenen Bildschirm und stören deinen Desktop nicht.\n\nJetzt installieren? Das System fragt nach deinem Passwort.", "locen_uspeh": "Der separate Bildschirm für den Fernseher ist bereit.", "locen_napaka": "Die Installation ist fehlgeschlagen. Programme vom Fernseher öffnen sich weiter auf dem Desktop.", "locen_gumb": "Installieren", "odpri": "Safeer Control öffnen", "samozagon": "Beim Anmelden starten", "mape": "Ordner für den Fernseher …", "programi": "Programme für den Fernseher", "ves_disk": "Ganzer Computer für den Fernseher", "zaslon": "Bildschirm für den Fernseher", "predvajanje": "Wiedergabe für andere Geräte", "ponudba_naslov": "An Gerät senden", "ponudba": "{naprava} sendet dir: {kaj}", "sprejmi": "Annehmen", "zavrni": "Ablehnen", "koncaj": "Beenden", "povezan": "Safeer Link: verbunden", "ni": "Safeer Link: nicht verbunden"},
    "es": {"posodobi": "Actualizar: {opis}…", "posodobi_prenasam": "Descargando {ime}…", "posodobi_namescam": "Instalando… (escribe tu contraseña si el sistema la pide)", "posodobi_koncano": "Instalado: {opis}. La versión nueva arranca con el próximo inicio.", "posodobi_napaka": "La actualización no se completó: {napaka}", "posodobi_naslov": "Actualización de Safeer", "locen_namesti": "Instalar la pantalla separada para el televisor…", "locen_posodobi": "Actualizar wf-recorder para la pantalla separada…", "locen_ni": "Pantalla separada: wf-recorder es demasiado antiguo", "locen_vprasanje": "Para la pantalla separada Safeer Control necesita estos paquetes: {paketi}. Los programas que abras desde el televisor se abrirán en su propia pantalla y no molestarán tu escritorio.\n\n¿Instalarlos ahora? El sistema te pedirá la contraseña.", "locen_uspeh": "La pantalla separada para el televisor está lista.", "locen_napaka": "La instalación ha fallado. Los programas del televisor seguirán abriéndose en el escritorio.", "locen_gumb": "Instalar", "odpri": "Abrir Safeer Control", "samozagon": "Iniciar al iniciar sesión", "mape": "Carpetas para el televisor…", "programi": "Programas para el televisor", "ves_disk": "Todo el ordenador para el televisor", "zaslon": "Pantalla para el televisor", "predvajanje": "Reproducción para otros dispositivos", "ponudba_naslov": "Enviar a un dispositivo", "ponudba": "{naprava} te envía: {kaj}", "sprejmi": "Aceptar", "zavrni": "Rechazar", "koncaj": "Salir", "povezan": "Safeer Link: conectado", "ni": "Safeer Link: sin conexión"},
    "fr": {"posodobi": "Mettre à jour : {opis}…", "posodobi_prenasam": "Téléchargement de {ime}…", "posodobi_namescam": "Installation… (saisis ton mot de passe si le système le demande)", "posodobi_koncano": "Installé : {opis}. La nouvelle version démarre au prochain lancement.", "posodobi_napaka": "La mise à jour n'a pas abouti : {napaka}", "posodobi_naslov": "Mise à jour Safeer", "locen_namesti": "Installer l'écran séparé pour le téléviseur…", "locen_posodobi": "Mettre à jour wf-recorder pour l'écran séparé…", "locen_ni": "Écran séparé : wf-recorder est trop ancien", "locen_vprasanje": "Pour l'écran séparé, Safeer Control a besoin de ces paquets : {paketi}. Les programmes lancés depuis le téléviseur s'ouvriront sur leur propre écran sans déranger ton bureau.\n\nLes installer maintenant ? Le système te demandera ton mot de passe.", "locen_uspeh": "L'écran séparé pour le téléviseur est prêt.", "locen_napaka": "L'installation a échoué. Les programmes du téléviseur continuent de s'ouvrir sur le bureau.", "locen_gumb": "Installer", "odpri": "Ouvrir Safeer Control", "samozagon": "Lancer à la connexion", "mape": "Dossiers pour le téléviseur…", "programi": "Programmes pour le téléviseur", "ves_disk": "Tout l'ordinateur pour le téléviseur", "zaslon": "Écran pour le téléviseur", "predvajanje": "Lecture pour les autres appareils", "ponudba_naslov": "Envoyer à un appareil", "ponudba": "{naprava} t'envoie : {kaj}", "sprejmi": "Accepter", "zavrni": "Refuser", "koncaj": "Quitter", "povezan": "Safeer Link : connecté", "ni": "Safeer Link : non connecté"},
    "it": {"posodobi": "Aggiorna: {opis}…", "posodobi_prenasam": "Scarico {ime}…", "posodobi_namescam": "Installo… (inserisci la password se il sistema la chiede)", "posodobi_koncano": "Installato: {opis}. La nuova versione parte al prossimo avvio.", "posodobi_napaka": "L'aggiornamento non è riuscito: {napaka}", "posodobi_naslov": "Aggiornamento Safeer", "locen_namesti": "Installa lo schermo separato per il televisore…", "locen_posodobi": "Aggiorna wf-recorder per lo schermo separato…", "locen_ni": "Schermo separato: wf-recorder è troppo vecchio", "locen_vprasanje": "Per lo schermo separato Safeer Control ha bisogno di questi pacchetti: {paketi}. I programmi avviati dal televisore si apriranno su un proprio schermo senza disturbare il tuo desktop.\n\nInstallarli ora? Il sistema ti chiederà la password.", "locen_uspeh": "Lo schermo separato per il televisore è pronto.", "locen_napaka": "L'installazione non è riuscita. I programmi dal televisore continuano ad aprirsi sul desktop.", "locen_gumb": "Installa", "odpri": "Apri Safeer Control", "samozagon": "Avvia all’accesso", "mape": "Cartelle per il televisore…", "programi": "Programmi per il televisore", "ves_disk": "Tutto il computer per il televisore", "zaslon": "Schermo per il televisore", "predvajanje": "Riproduzione per gli altri dispositivi", "ponudba_naslov": "Invia a un dispositivo", "ponudba": "{naprava} ti invia: {kaj}", "sprejmi": "Accetta", "zavrni": "Rifiuta", "koncaj": "Esci", "povezan": "Safeer Link: connesso", "ni": "Safeer Link: non connesso"},
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
            # Jezik vmesnika: ce ima uporabnik na tem racunalniku Safeer Browser, govori Control v istem jeziku,
            # sicer v jeziku seje (prej je pladenj brez brskalnika vedno govoril anglesko).
            v = _jezik_brskalnika() or _jezik_sistema()
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


def _jezik_sistema() -> Optional[str]:
    """Jezik seje (LANGUAGE, LC_ALL, LC_MESSAGES, LANG), ce ga Control zna; sicer None."""
    for kljuc in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        vrednost = os.environ.get(kljuc, "")
        if vrednost:
            oznaka = vrednost.split(":")[0].replace("-", "_").split(".")[0].split("_")[0].strip().lower()[:2]
            return oznaka if oznaka in BESEDILA else None
    return None


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
        # »Nadaljuj z druge naprave«: telefon sme vprasati, kaj Safeer OS tu predvaja, in nadaljevati pri isti
        # sekundi. Privzeto vklopljeno (gre samo napravam v krogu zaupanja, datoteke le iz deljenih map).
        self.predvajanje = Gtk.CheckMenuItem(label=besedilo(self.jezik, "predvajanje"))
        self.predvajanje.set_active(bool(app.nastavitve.get("predvajanje_za_naprave", True)))
        self._predvajanje_id = self.predvajanje.connect("toggled", self._preklop_predvajanje)
        # Posodobitev s safeer.si: postavka se pokaze samo, kadar je na voljo novejsa razlicica (preverba na 6 ur).
        self.posodobi = Gtk.MenuItem(label="")
        self.posodobi.connect("activate", lambda *_a: app.posodobi_iz_pladnja())
        # Locen zaslon za televizor: postavka se pokaze samo, kadar kaj manjka ali je prestaro.
        self.locen = Gtk.MenuItem(label="")
        self.locen.connect("activate", lambda *_a: app.namesti_locen_zaslon())
        self.koncaj = Gtk.MenuItem(label=besedilo(self.jezik, "koncaj"))
        self.koncaj.connect("activate", lambda *_a: app.koncaj())
        for m in (self.odpri, self.posodobi, self.mape, self.ves_disk, self.programi, self.zaslon, self.predvajanje, self.locen, Gtk.SeparatorMenuItem(),
                  self.samozagon, Gtk.SeparatorMenuItem(), self.koncaj):
            self.meni.append(m)
        self.meni.show_all()
        self.osvezi_locen()
        self.osvezi_posodobitev()
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

    def _preklop_predvajanje(self, postavka: Gtk.CheckMenuItem) -> None:
        self.app.nastavitve.set("predvajanje_za_naprave", bool(postavka.get_active()))

    def osvezi_posodobitev(self) -> None:
        """Postavka "Posodobi: Safeer Control 2.1.23 …" le, kadar je zadnja preverba nasla novejso razlicico."""
        opis = os_posodobitve.opis(self.app.posodobitve_izid or {})
        if opis:
            self.posodobi.set_label(besedilo(self.jezik, "posodobi").replace("{opis}", opis))
            self.posodobi.show()
        else:
            self.posodobi.hide()

    def osvezi_predvajanje(self) -> None:
        """Postavka v pladnju sledi stikalu v Safeer OS (brez ponovnega prozenja preklopa)."""
        zelim = bool(self.app.nastavitve.get("predvajanje_za_naprave", True))
        if self.predvajanje.get_active() == zelim:
            return
        self.predvajanje.handler_block(self._predvajanje_id)
        try:
            self.predvajanje.set_active(zelim)
        finally:
            self.predvajanje.handler_unblock(self._predvajanje_id)

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


class OddaljeniGledalec(Gtk.Window):
    """GTK3 gledalec H.264, ki tece v istem procesu kot Safeer Control."""

    def __init__(self, control, id_naprave: str, podatki: dict) -> None:
        super().__init__(title="Oddaljeni zaslon - " + str(podatki.get("ime") or "racunalnik"))
        self.control = control
        self.id_naprave = id_naprave
        self.gledalec = None
        self.pipeline = None
        self.appsrc = None
        self.Gst = None
        self.ponor_ime = ""
        self.zaprto = False
        self.prejsnja_tocka = None
        self.sirina_slike = 1920
        self.visina_slike = 1080
        self.set_default_size(1200, 760)

        prekrivnik = Gtk.Overlay()
        self.add(prekrivnik)
        self.dogodki = Gtk.EventBox()
        self.dogodki.set_visible_window(False)
        self.dogodki.set_above_child(True)
        self.dogodki.set_can_focus(True)
        self.dogodki.add_events(
            Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK |
            Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.KEY_PRESS_MASK | Gdk.EventMask.KEY_RELEASE_MASK)
        prekrivnik.add(self.dogodki)

        self.stanje = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.stanje.set_halign(Gtk.Align.CENTER)
        self.stanje.set_valign(Gtk.Align.CENTER)
        self.napis = Gtk.Label(label="Povezujem ...")
        self.napis.set_line_wrap(True)
        self.ponovno = Gtk.Button(label="Povezi znova")
        self.ponovno.set_no_show_all(True)
        self.ponovno.connect("clicked", self._ponovi)
        self.stanje.pack_start(self.napis, False, False, 0)
        self.stanje.pack_start(self.ponovno, False, False, 0)
        prekrivnik.add_overlay(self.stanje)

        celo = Gtk.Button(label="Celozaslonsko")
        celo.set_halign(Gtk.Align.END)
        celo.set_valign(Gtk.Align.START)
        celo.set_margin_top(12)
        celo.set_margin_end(12)
        celo.connect("clicked", self._celo)
        prekrivnik.add_overlay(celo)

        self.dogodki.connect("motion-notify-event", self._premik)
        self.dogodki.connect("leave-notify-event", self._izhod_miske)
        self.dogodki.connect("button-press-event", self._klik, True)
        self.dogodki.connect("button-release-event", self._klik, False)
        self.dogodki.connect("scroll-event", self._kolo)
        self.dogodki.connect("key-press-event", self._tipka, True)
        self.dogodki.connect("key-release-event", self._tipka, False)
        self.connect("delete-event", self._zahteva_zaprtje)
        self.show_all()
        self._zacni(podatki)

    @staticmethod
    def _nalozi_gstreamer():
        # Uvoz je namenoma pozen: Control mora delovati tudi brez GStreamerja.
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst  # noqa: WPS433
        Gst.init(None)
        return Gst

    def _celo(self, *_a) -> None:
        if self.get_window() is not None and self.get_window().get_state() & Gdk.WindowState.FULLSCREEN:
            self.unfullscreen()
        else:
            self.fullscreen()

    def _pokazi_napako(self, sporocilo: str) -> bool:
        if self.zaprto:
            return False
        self.napis.set_text(sporocilo or "Povezava je bila prekinjena.")
        self.ponovno.show()
        self.stanje.show_all()
        return False

    def _zamenjaj_vsebino(self, widget) -> None:
        otrok = self.dogodki.get_child()
        if otrok is not None:
            self.dogodki.remove(otrok)
        self.dogodki.add(widget)
        widget.show()

    def _pripravi_pipeline(self) -> None:
        self.Gst = self._nalozi_gstreamer()
        Gst = self.Gst
        self.ponor_ime = izberi_ponor(lambda ime: Gst.ElementFactory.find(ime) is not None)
        self.pipeline = Gst.parse_launch(niz_cevovoda(self.ponor_ime))
        self.appsrc = self.pipeline.get_by_name("vir")
        ponor = self.pipeline.get_by_name("ponor")
        if self.ponor_ime == "gtksink":
            self._zamenjaj_vsebino(ponor.props.widget)
        else:
            prazno = Gtk.DrawingArea()
            self._zamenjaj_vsebino(prazno)
            if ponor.find_property("handle-events") is not None:
                ponor.set_property("handle-events", True)
            self.napis.set_text("Paket gtksink ni na voljo. Slika je odprta v locenem oknu glimagesink.")
            self.stanje.show_all()
            print("[SafeerControl] gtksink ni na voljo; uporabljam glimagesink v locenem oknu.")
            podloga = ponor.get_static_pad("sink")
            if podloga is not None:
                podloga.add_probe(Gst.PadProbeType.EVENT_UPSTREAM, self._navigacijski_dogodek)
        vodilo = self.pipeline.get_bus()
        vodilo.add_signal_watch()
        vodilo.connect("message::error", self._gst_napaka)
        if self.pipeline.set_state(Gst.State.PLAYING) == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("GStreamer cevovoda ni mogel zagnati.")

    def _gst_napaka(self, _vodilo, sporocilo) -> None:
        napaka, _podrobnosti = sporocilo.parse_error()
        GLib.idle_add(self._pokazi_napako, "GStreamer: " + str(napaka))

    def _zacni(self, podatki: dict) -> None:
        self.napis.set_text("Povezujem ...")
        self.ponovno.hide()
        self.stanje.show_all()
        self.ponovno.hide()
        self._ustavi_pretok()
        try:
            self._pripravi_pipeline()
        except Exception as e:  # noqa: BLE001
            self._pokazi_napako("GStreamer ne more pripraviti slike: " + str(e))
            return

        def delo() -> None:
            gledalec = None
            try:
                gledalec = Gledalec(str(podatki.get("naslov") or ""), podatki.get("seja") or {})
                self.gledalec = gledalec
                glava = gledalec.povezi()
                self.sirina_slike, self.visina_slike = glava.sirina, glava.visina
                GLib.idle_add(self._povezano)
                for vrsta, telo in gledalec.okvirji():
                    if self.zaprto or self.gledalec is not gledalec:
                        break
                    if vrsta == OKVIR_SLIKA:
                        medpomnilnik = self.Gst.Buffer.new_allocate(None, len(telo), None)
                        medpomnilnik.fill(0, telo)
                        appsrc = self.appsrc
                        if appsrc is None or appsrc.emit("push-buffer", medpomnilnik) == self.Gst.FlowReturn.ERROR:
                            raise RuntimeError("Dekoder slike se je ustavil.")
                    elif vrsta == OKVIR_OBVESTILO:
                        obvestilo = json.loads(telo.decode("utf-8"))
                        if obvestilo.get("konec"):
                            raise RuntimeError(str(obvestilo.get("konec")))
            except Exception as e:  # noqa: BLE001
                if not self.zaprto and gledalec is not None and self.gledalec is gledalec:
                    GLib.idle_add(self._pokazi_napako, str(e))

        threading.Thread(target=delo, name="safeer-gledalec", daemon=True).start()

    def _povezano(self) -> bool:
        if self.ponor_ime == "gtksink":
            self.stanje.hide()
        self.dogodki.grab_focus()
        return False

    def _ustavi_pretok(self) -> None:
        # Najprej pozabimo sejo, sele nato jo zapremo: bralna nit se ob zaprtju zbudi z napako in jo pokaze
        # samo, ce je seja se »nasa«. V obratnem vrstnem redu bi ob »Povezi znova« lahko pokazala napako stare seje.
        gledalec, self.gledalec = self.gledalec, None
        if gledalec is not None:
            gledalec.zapri()
        if self.pipeline is not None and self.Gst is not None:
            self.pipeline.set_state(self.Gst.State.NULL)
            self.pipeline = None
            self.appsrc = None

    def _ponovi(self, *_a) -> None:
        self.ponovno.hide()
        self.napis.set_text("Pridobivam novo dovoljenje ...")
        self.stanje.show()

        def delo() -> None:
            try:
                if self.control.link is not None:
                    self.control.link.ukaz_pocakaj(self.id_naprave, "screen.stop", {}, cas=5.0)
                novi = self.control._nova_oddaljena_seja(self.id_naprave)
                if not novi.get("ok"):
                    raise RuntimeError(str(novi.get("message") or "Povezava ni dovoljena."))
                GLib.idle_add(self._zacni, novi)
            except Exception as e:  # noqa: BLE001
                GLib.idle_add(self._pokazi_napako, str(e))

        threading.Thread(target=delo, name="safeer-gledalec-ponovi", daemon=True).start()

    def _poslji(self, dogodek) -> None:
        if dogodek and self.gledalec is not None:
            try:
                self.gledalec.poslji(dogodek)
            except OSError:
                pass

    def _tocka(self, x: float, y: float):
        razpored = self.dogodki.get_allocation()
        return preslikaj_tocko(x, y, razpored.width, razpored.height,
                               self.sirina_slike, self.visina_slike)

    def _premik(self, _widget, dogodek) -> bool:
        # Absolutni polozaj (kot Windows gledalec): oddaljeni kazalec je vedno tam, kamor kaze nas.
        # Relativni premiki so se razlezli (pospesek miske na drugi strani, skok ob vstopu v okno).
        tocka = self._tocka(dogodek.x, dogodek.y)
        if tocka is not None and tocka != self.prejsnja_tocka:
            self._poslji({"vrsta": "tocka", "x": round(tocka[0]), "y": round(tocka[1])})
        self.prejsnja_tocka = tocka
        return True

    def _izhod_miske(self, *_a) -> bool:
        self.prejsnja_tocka = None
        return False

    def _klik(self, _widget, dogodek, dol: bool) -> bool:
        tocka = self._tocka(dogodek.x, dogodek.y)
        if tocka is None:
            return True
        if dol:
            self._poslji({"vrsta": "tocka", "x": round(tocka[0]), "y": round(tocka[1])})
        if dol:
            self.dogodki.grab_focus()
        gumb = {1: "levi", 2: "srednji", 3: "desni"}.get(int(dogodek.button))
        if gumb:
            self._poslji({"vrsta": "gumb", "gumb": gumb, "dol": dol})
        return True

    def _kolo(self, _widget, dogodek) -> bool:
        if self._tocka(dogodek.x, dogodek.y) is None:
            return True
        if dogodek.direction == Gdk.ScrollDirection.SMOOTH:
            _uspeh, _dx, dy = dogodek.get_scroll_deltas()
            if not dy:
                return True
            smer = "dol" if dy > 0 else "gor"
            koliko = min(10, max(1, round(abs(dy)) or 1))
        else:
            smer = "dol" if dogodek.direction in (Gdk.ScrollDirection.DOWN, Gdk.ScrollDirection.RIGHT) else "gor"
            koliko = 1
        self._poslji({"vrsta": "kolesce", "smer": smer, "koliko": koliko})
        return True

    def _tipka(self, _widget, dogodek, dol: bool) -> bool:
        ime = Gdk.keyval_name(dogodek.keyval) or ""
        unicode_vrednost = Gdk.keyval_to_unicode(dogodek.keyval)
        znak = chr(unicode_vrednost) if unicode_vrednost else ""
        bliznjice = {"c": "kopiraj", "v": "prilepi", "x": "izrezi", "z": "razveljavi",
                     "y": "ponovi", "a": "izberi_vse", "s": "shrani", "p": "natisni",
                     "f": "isci", "w": "zapri_okno", "b": "krepko", "i": "lezece", "u": "podcrtano"}
        if dol and dogodek.state & Gdk.ModifierType.CONTROL_MASK and znak.lower() in bliznjice:
            self._poslji({"vrsta": "tipka", "tipka": bliznjice[znak.lower()]})
        else:
            self._poslji(preslikaj_tipko(ime, znak, dol))
        return True

    def _navigacijski_dogodek(self, _podloga, podatek):
        """Vhod lastnega okna glimagesink prevede iz navigacijskih dogodkov."""
        Gst = self.Gst
        dogodek = podatek.get_event()
        struktura = dogodek.get_structure() if dogodek is not None else None
        if struktura is None or struktura.get_name() != "application/x-gst-navigation":
            return Gst.PadProbeReturn.OK
        vrsta = struktura.get_string("event") or ""
        if vrsta == "mouse-move":
            x, y = float(struktura.get_value("pointer_x")), float(struktura.get_value("pointer_y"))
            prej, self.prejsnja_tocka = self.prejsnja_tocka, (x, y)
            if prej is not None:
                self._poslji({"vrsta": "premik", "dx": round(x - prej[0]), "dy": round(y - prej[1])})
        elif vrsta in ("mouse-button-press", "mouse-button-release"):
            gumb = {1: "levi", 2: "srednji", 3: "desni"}.get(int(struktura.get_value("button")))
            if gumb:
                self._poslji({"vrsta": "gumb", "gumb": gumb, "dol": vrsta.endswith("press")})
        elif vrsta == "mouse-scroll":
            dy = float(struktura.get_value("delta_y") or 0)
            if dy:
                self._poslji({"vrsta": "kolesce", "smer": "dol" if dy > 0 else "gor",
                              "koliko": min(10, max(1, round(abs(dy)) or 1))})
        elif vrsta in ("key-press", "key-release"):
            ime = struktura.get_string("key") or ""
            self._poslji(preslikaj_tipko(ime, ime if len(ime) == 1 else "", vrsta == "key-press"))
        return Gst.PadProbeReturn.OK

    def _zahteva_zaprtje(self, *_a) -> bool:
        self.zapri()
        return True

    def zapri(self, sporoci_stop: bool = True) -> None:
        if self.zaprto:
            return
        self.zaprto = True
        self._ustavi_pretok()
        if self.control._oddaljeni_gledalec is self:
            self.control._oddaljeni_gledalec = None
        self.destroy()
        if sporoci_stop:
            threading.Thread(target=self.control._ustavi_oddaljeno_sejo,
                             args=(self.id_naprave,), name="safeer-gledalec-stop", daemon=True).start()


class SafeerControl(Gtk.Application):
    def __init__(self, ozadje: bool = False) -> None:
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.link: Optional[SafeerLink] = None
        self.posodobitve_izid: Optional[dict] = None     # zadnja preverba safeer.si (os_posodobitve.preveri)
        self.posodabljanje = os_posodobitve.Posodabljanje()
        self.nastavitve = Nastavitve(os.path.join(NASTAVITVE_MAPA, "control.json"))
        self.web_context = WebKit2.WebContext.get_default()
        self.gledalec: Optional[Gtk.Window] = None
        self._oddaljeni_gledalec: Optional[OddaljeniGledalec] = None
        # --ozadje: brez okna, z ikono v pladnju; okno se odpre iz pladnja ali ob ponovnem zagonu iz menija.
        self.ozadje = ozadje
        self.pladenj: Optional[Pladenj] = None
        self._prva_aktivacija = True
        # Deljene mape za televizor; seznam poti je v control.json ("deljene_mape").
        mape = self.nastavitve.get("deljene_mape")
        self.datoteke = link_datoteke.Datoteke(mape if isinstance(mape, list) else [],
                                              ves_disk=bool(self.nastavitve.get("ves_disk_za_tv", False)))
        self.datoteke.ob_spremembi = lambda poti: self.nastavitve.set("deljene_mape", poti)
        # Kar racunalnik prenese za naprave (torrent prek magnet.stream) in tega 48 ur nihce ne predvaja, odstrani sam.
        link_datoteke.zazeni_ciscenje()
        # Knjiznica kroga: film, ki ga je Safeer OS na tem racunalniku zaradi gledanja prenesel sam, vidijo in predvajajo
        # tudi naprave (magnet.list); zasebnih naslovov med njimi ni.
        from core import knjiznica_kroga
        self.datoteke.gledanje = knjiznica_kroga.lokalni
        self.datoteke.odstrani_gledanje = self._odstrani_gledanje
        self.datoteke.obdrzi_gledanje = knjiznica_kroga.nastavi_obdrzi
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
        # Safeer OS (stikalo »Predvajanje za druge naprave« poleg Zaupaj): isti kljuc kot postavka v pladnju.
        predvajanje = Gio.SimpleAction.new("predvajanje-za-naprave", GLib.VariantType.new("b"))
        predvajanje.connect("activate", lambda _d, v: self.nastavi_predvajanje_za_naprave(v.get_boolean()))
        self.add_action(predvajanje)
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
        # "Poslji na napravo" z druge naprave: gumba Sprejmi/Zavrni v tihem obvestilu (pravila 28. 9.).
        for ime, klic in (("predaja-sprejmi", self.predaja_sprejmi), ("predaja-zavrni", self.predaja_zavrni)):
            dejanje = Gio.SimpleAction.new(ime, None)
            dejanje.connect("activate", lambda _d, _v, k=klic: k())
            self.add_action(dejanje)
        if self.ozadje:
            self.hold()  # brez okna bi se GApplication koncal; ikona v pladnju ga drzi
        self._izvozi_naprave()
        # Dokler racunalnik posilja datoteko ali tok drugi napravi (ali zanjo sproti pretvarja), ne zaspi sam:
        # sicer bi film na televizorju obstal sredi predvajanja. Zaprt pokrov in rocno spanje delujeta kot vedno.
        self._budnost = budnost.Budnost("Safeer Control")
        GLib.timeout_add_seconds(30, self._budnost_tik)

    def _budnost_tik(self) -> bool:
        try:
            self._budnost.po_dejavnosti("pomoc", "Safeer pretaka na drugo napravo")
        except Exception:  # noqa: BLE001
            pass
        return True

    # ------------------------------------------------------------------ D-Bus za Safeer OS: naprave in njihovi programi
    VMESNIK_NAPRAVE = """
    <node><interface name="io.github.memelandfaner.SafeerControl.Naprave">
      <method name="Seznam"><arg type="s" name="json" direction="out"/></method>
      <method name="Aplikacije"><arg type="s" name="naprava" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="Zazeni"><arg type="s" name="naprava" direction="in"/><arg type="s" name="app" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="OdpriTukaj"><arg type="s" name="naprava" direction="in"/><arg type="s" name="app" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="Preimenuj"><arg type="s" name="naprava" direction="in"/><arg type="s" name="ime" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="Upravljaj"><arg type="s" name="naprava" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="Klepet"><arg type="s" name="naprava" direction="in"/><arg type="s" name="besedilo" direction="in"/><arg type="s" name="cas" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="KlepetNaprave"><arg type="s" name="json" direction="out"/></method>
      <method name="Magnet"><arg type="s" name="naprava" direction="in"/><arg type="s" name="uri" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="ShrambaZacni"><arg type="s" name="pot" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="ShrambaStanje"><arg type="s" name="id" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="ShrambaIzbrisi"><arg type="s" name="id" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="ShrambaObdrzi"><arg type="s" name="id" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="PretvorbaZacni"><arg type="s" name="pot" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="PretvorbaStanje"><arg type="s" name="id" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="PretvorbaPrenesi"><arg type="s" name="id" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="PretvorbaPusti"><arg type="s" name="id" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="PretvorbaZacniVec"><arg type="s" name="poti" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="PretvorbaSkupina"><arg type="s" name="id" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="PretvorbaPrenesiSkupino"><arg type="s" name="id" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="PretvorbaPustiSkupino"><arg type="s" name="id" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="Datoteke"><arg type="s" name="naprava" direction="in"/><arg type="s" name="mapa" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="Ukaz"><arg type="s" name="naprava" direction="in"/><arg type="s" name="dejanje" direction="in"/><arg type="s" name="parametri" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="Predaja"><arg type="s" name="json" direction="out"/></method>
      <method name="Prevzemi"><arg type="s" name="naprava" direction="in"/><arg type="s" name="podatki" direction="in"/><arg type="s" name="ustavi_tam" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="Ponudi"><arg type="s" name="naprava" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="Poslji"><arg type="s" name="naprava" direction="in"/><arg type="s" name="poti" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="PosljiStanje"><arg type="s" name="id" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="Besedilo"><arg type="s" name="naprava" direction="in"/><arg type="s" name="besedilo" direction="in"/><arg type="s" name="json" direction="out"/></method>
      <method name="Internet"><arg type="s" name="ukaz" direction="in"/><arg type="s" name="parametri" direction="in"/><arg type="s" name="json" direction="out"/></method>
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
        if metoda.startswith("Shramba"):
            # Skupni prostor: datoteka tega racunalnika na napravo z najvec prostora (core/link_shramba.py).
            if getattr(self, "shramba", None) is None:
                from core import link_shramba
                self.shramba = link_shramba.Shramba(
                    lambda: [dict(n, ta=n.get("id", "") == link._id()) for n in link.naprave],
                    lambda i, d, p: link.ukaz_pocakaj(i, d, p, cas=20.0),
                    self.datoteke, lambda: link._hub() or "")
            arg = str(a[0]) if a else ""
            if metoda == "ShrambaZacni":
                return self.shramba.zacni(arg)
            if metoda == "ShrambaStanje":
                return self.shramba.stanje(arg)
            if metoda == "ShrambaIzbrisi":
                return self.shramba.izbrisi_original(arg)
            if metoda == "ShrambaObdrzi":
                return self.shramba.obdrzi(arg)
            return {"ok": False, "koda": "neznano"}
        if metoda.startswith("Pretvorba"):
            # Grafika: video pretvori naprava z najboljsim strojnim kodirnikom (core/link_pretvorba.py).
            if getattr(self, "pretvorba", None) is None:
                from core import link_pretvorba
                self.pretvorba = link_pretvorba.Pretvorba(
                    lambda: [dict(n, ta=n.get("id", "") == link._id()) for n in link.naprave],
                    lambda i, d, p: link.ukaz_pocakaj(i, d, p, cas=20.0),
                    self.datoteke, lambda: link._hub() or "")
            arg = str(a[0]) if a else ""
            if metoda == "PretvorbaZacniVec":
                # Seznam poti (datoteke ali mape) kot JSON - zakon solidarnosti, korak 4 (sorazmerni delez).
                try:
                    poti = json.loads(arg) if arg.startswith("[") else [arg]
                except ValueError:
                    poti = []
                return self.pretvorba.zacni_vec([str(x) for x in poti if isinstance(x, str)])
            dejanje = {"PretvorbaZacni": self.pretvorba.zacni, "PretvorbaStanje": self.pretvorba.stanje,
                       "PretvorbaPrenesi": self.pretvorba.prenesi, "PretvorbaPusti": self.pretvorba.pusti,
                       "PretvorbaSkupina": self.pretvorba.stanje_skupine,
                       "PretvorbaPrenesiSkupino": self.pretvorba.prenesi_skupino,
                       "PretvorbaPustiSkupino": self.pretvorba.pusti_skupino}.get(metoda)
            return dejanje(arg) if dejanje else {"ok": False, "koda": "neznano"}
        if metoda == "Preimenuj":
            # Ime hrani sredisce (/cast/devices/rename) in ga vidijo vse naprave; prazno vrne prvotno ime.
            # Zeton za HTTP: zeton seznanitve ali sejni zeton s podpisom (racunalnik kot lastno sredisce prvega nima).
            zeton = link._zeton_http() if (link._hub() and link._odtis()) else None
            if not zeton:
                return {"ok": False, "koda": "hub_ni_znan"}
            ok, novo, n = link_deljenje.preimenuj_napravo(link._hub(), zeton, link._odtis() or "",
                                                          str(a[0]) if a else "", str(a[1]) if len(a) > 1 else "")
            return {"ok": bool(ok), "ime": novo, "koda": "" if ok else n.get("koda", ""),
                    "message": "" if ok else n.get("sporocilo", "")}
        if metoda == "Upravljaj":
            return self.upravljaj_racunalnik(str(a[0]) if a else "")
        if metoda == "Klepet":
            # Safeer Chat iz Sporocil v Safeer OS: poslje napravi v Linku in vrne potrditev sredisca.
            stanje = link.poslji_klepet(str(a[0]), str(a[1]), str(a[2]) if len(a) > 2 else "")
            return {"ok": stanje in ("accepted", "queued"), "stanje": stanje}
        if metoda == "KlepetNaprave":
            return {"ok": True, "naprave": list(link.naprave_klepeta)}
        if metoda == "Magnet":
            # Magnet povezava na drugo napravo v Linku: tam se odpre v predvajalniku (magnet.open).
            from core import os_torrent
            m = os_torrent.razcleni_magnet(str(a[1]) if len(a) > 1 else "")
            if m is None:
                return {"ok": False, "koda": "ni_magnet"}
            return link.ukaz_pocakaj(str(a[0]) if a else "", "magnet.open", {"uri": m["uri"]}, cas=15.0)
        if metoda == "Datoteke":
            # Deljene mape druge naprave (files.list) za Safeer Media: seznam + streznik (naslov, odtis, zeton).
            # Doda kljuc naprave iz kroga: z njim gre tok prek Global Linka, kadar naprave ni v tem omrezju.
            id_naprave = str(a[0]) if a else ""
            r = link.ukaz_pocakaj(id_naprave, "files.list", {"folder": str(a[1]) if len(a) > 1 else ""}, cas=15.0)
            if not r.get("ok"):
                return {"ok": False, "koda": r.get("koda") or "napaka", "message": r.get("message") or ""}
            d = r.get("data") or {}
            try:
                from core import link_krog
                clan = link_krog.krog().clan_za_id(id_naprave) or {}
            except Exception:
                clan = {}
            return {"ok": True, "items": d.get("items") if isinstance(d.get("items"), list) else [],
                    "folder": str(d.get("folder") or ""), "shared": bool(d.get("shared", True)),
                    "reason": str(d.get("reason") or ""),
                    "server": d.get("server") if isinstance(d.get("server"), dict) else None,
                    "kljuc": str(clan.get("kljuc") or "")}
        if metoda == "Ukaz":
            # Poljuben ukaz Linka napravi s cakanjem na odgovor (Safeer OS, diagnostika: host.info, status ...).
            id_naprave = str(a[0]) if a else ""
            dejanje = str(a[1]) if len(a) > 1 else ""
            try:
                parametri = json.loads(str(a[2])) if len(a) > 2 and str(a[2]).strip() else {}
            except Exception:
                return {"ok": False, "koda": "napacna_zahteva", "message": "Parametri niso JSON."}
            if not id_naprave or not dejanje or not isinstance(parametri, dict):
                return {"ok": False, "koda": "napacna_zahteva", "message": "Manjka naprava ali dejanje."}
            if id_naprave == link._id() and dejanje in link_daljinec.DEJANJA_TOK_TORRENTA:
                return self._ukaz_tukaj(dejanje, parametri)
            if id_naprave == link._id() and dejanje == "host.info":
                # Ta racunalnik o sebi (safeerctl info): sredisce bi ukaz samemu sebi zavrnilo (»ista naprava«).
                return {"ok": True, "data": link_daljinec.podatki_hosta()}
            return link.ukaz_pocakaj(id_naprave, dejanje, parametri, cas=20.0)
        if metoda == "Predaja":
            # "Nadaljuj z druge naprave" na tem racunalniku: vse naprave z daljincem vprasa hkrati (play.state, 3 s),
            # vrne tiste, ki kaj igrajo ali so kaj nazadnje gledale (najprej tiste, ki igrajo) - kot Predaja.poizvedi.
            from core import link_predvajanje
            naprave = [n for n in link.naprave if n.get("id") != link._id() and "remote" in (n.get("zmoznosti") or [])]
            izidi: dict = {}

            def vprasaj(n: dict) -> None:
                try:
                    izidi[n["id"]] = link.ukaz_pocakaj(str(n["id"]), "play.state", {}, cas=3.0)
                except Exception as e:  # noqa: BLE001
                    izidi[n["id"]] = {"ok": False, "message": str(e)}
            niti = [threading.Thread(target=vprasaj, args=(n,), daemon=True) for n in naprave]
            for t in niti:
                t.start()
            for t in niti:
                t.join(4.0)
            ponudbe = []
            for n in naprave:
                r = izidi.get(n["id"]) or {}
                d = r.get("data") if r.get("ok") and isinstance(r.get("data"), dict) else None
                if not d or not isinstance(d.get("item"), dict) or not (d.get("playing") or d.get("last")):
                    continue
                if link_predvajanje.ponudba_iz(n["id"], "", d) is None:
                    continue  # tu tega ni mogoce predvajati (datoteka naprave brez streznika, lokalni posrednik ...)
                ponudbe.append({"naprava": {"id": n["id"], "ime": n.get("ime") or n["id"]},
                                "naslov": str(d["item"].get("naslov") or ""), "igra": bool(d.get("playing")) and bool(d.get("is_playing", True)),
                                "nazadnje": bool(d.get("last")), "position_ms": int(d.get("position_ms") or 0),
                                "duration_ms": int(d.get("duration_ms") or 0), "opis": link_predvajanje.opis_ponudbe(
                                    {"item": d["item"], "position_ms": d.get("position_ms") or 0}), "podatki": d})
            ponudbe.sort(key=lambda p: (not p["igra"], p["nazadnje"]))
            return {"ok": True, "ponudbe": ponudbe}
        if metoda == "Prevzemi":
            # Uporabnik je na tem racunalniku izbral ponudbo: predvajamo jo tu (kot sprejeto "Poslji na napravo");
            # izvor igra naprej, razen ce je izbral "nadaljuj tukaj in ustavi tam" (play.stop = premor).
            from core import link_predvajanje
            id_naprave = str(a[0]) if a else ""
            try:
                d = json.loads(str(a[1])) if len(a) > 1 else {}
            except Exception:
                return {"ok": False, "koda": "napacna_zahteva"}
            ime = next((str(n.get("ime") or "") for n in link.naprave if n.get("id") == id_naprave), id_naprave)
            p = link_predvajanje.ponudba_iz(id_naprave, ime, d if isinstance(d, dict) else {})
            if p is None or link.predvajanje is None:
                return {"ok": False, "koda": "ni_vnosa"}
            if len(a) > 2 and str(a[2]).lower() in ("1", "true", "da"):
                try:
                    link.ukaz_pocakaj(id_naprave, "play.stop", {}, cas=5.0)
                except Exception:  # noqa: BLE001
                    pass
            link.predvajanje.cakajoca = p
            GLib.idle_add(self.predaja_sprejmi)
            return {"ok": True}
        if metoda == "Internet":
            # Internet prek telefona (Safeer OS, safeerctl internet): stanje, nastavitve, preizkus.
            try:
                parametri = json.loads(str(a[1])) if len(a) > 1 and str(a[1]).strip() else {}
            except ValueError:
                return {"ok": False, "koda": "napacna_zahteva"}
            if not isinstance(parametri, dict):
                return {"ok": False, "koda": "napacna_zahteva"}
            return self._internet_metoda(str(a[0]) if a else "", parametri)
        if metoda == "Besedilo":
            # Besedilo ali povezava napravi (safeerctl text): isto kot »Poslji besedilo« v Controlu.
            ok, n = link.poslji_besedilo_napravi(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else "")
            return {"ok": True} if ok else {"ok": False, "koda": n.get("koda", ""), "message": n.get("sporocilo", "")}
        if metoda in ("Poslji", "PosljiStanje"):
            # Datoteke iz Datotek Safeer OS na izbrano napravo (povleci na napravo, »Poslji na napravo«).
            if getattr(self, "posiljanje", None) is None:
                from core import link_posiljanje
                self.posiljanje = link_posiljanje.Posiljanje(
                    link.poslji_datoteko_napravi,
                    lambda i: next((str(n.get("ime") or "") for n in link.naprave if n.get("id") == i), ""))
            if metoda == "PosljiStanje":
                return self.posiljanje.stanje(str(a[0]) if a else "")
            try:
                poti = json.loads(str(a[1])) if len(a) > 1 else []
            except ValueError:
                poti = []
            return self.posiljanje.zacni(str(a[0]) if a else "", [str(p) for p in poti] if isinstance(poti, list) else [])
        if metoda == "Ponudi":
            # "Poslji na napravo" s tega racunalnika: kar Safeer OS igra, napravi (zeton streznika datotek za njo);
            # tam caka Sprejmi, tu igra naprej.
            from core import link_predvajanje
            id_naprave = str(a[0]) if a else ""
            if link.predvajanje is None:
                return {"ok": False, "koda": "ni_predvajanja"}
            st = link.predvajanje.stanje(id_naprave, link._hub() or "")
            if not st.get("playing"):
                return {"ok": False, "koda": st.get("reason") or "ni_predvajanja"}
            jaz = next((str(n.get("ime") or "") for n in link.naprave if n.get("id") == link._id()), "")
            parametri = {k: st[k] for k in ("item", "position_ms", "duration_ms", "server", "server_device") if k in st}
            parametri["from"] = jaz
            return link_predvajanje.izid_ponudbe(link.ukaz_pocakaj(id_naprave, "play.offer", parametri, cas=8.0))
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
        if metoda == "OdpriTukaj":
            r = link.ukaz_pocakaj(str(a[0]) if a else "", "apps.launch",
                                  {"app": str(a[1]) if len(a) > 1 else "", "stream": True}, cas=8.0)
            podatki = r.get("data") if isinstance(r.get("data"), dict) else {}
            id_cilja = str(a[0]) if a else ""
            naprava = next((n for n in (getattr(link, "naprave", None) or []) if n.get("id") == id_cilja), {}) or {}
            if r.get("ok") and (naprava.get("platforma") in ("windows", "linux") or naprava.get("vrsta") == "control"):
                # Racunalnik zaslona ne potisne sam (kot telefon ali TV): program se odpre na njegovem
                # namizju, tukaj pa odpremo oddaljeni zaslon tega namizja - z misko in tipkovnico.
                def _pocakaj_in_upravljaj() -> None:
                    time.sleep(1.5)
                    self.upravljaj_racunalnik(id_cilja)
                threading.Thread(target=_pocakaj_in_upravljaj, name="safeer-odpri-tukaj", daemon=True).start()
                return {"ok": True, "tu": True, "koda": "", "message": str(r.get("message") or "")}
            return {"ok": bool(r.get("ok")), "tu": podatki.get("stream") == "pending",
                    "koda": str(r.get("koda") or r.get("code") or ""),
                    "message": str(r.get("message") or "")}
        return {"ok": False, "message": "neznana metoda"}

    @staticmethod
    def _odstrani_gledanje(hash_: str) -> bool:
        """Naprava je s police odstranila film, ki ga je prenesel Safeer OS na tem racunalniku. Motor torrentov je
        njegov: ce Safeer OS tece, film odstrani on (D-Bus); sicer ga odstranimo tukaj - motor zazenemo samo za to in
        ga spet ustavimo."""
        from core import knjiznica_kroga, link_predvajanje, os_torrent
        if link_predvajanje.safeer_os_tece():
            return link_predvajanje.odstrani_prenos_safeer_os(hash_)
        motor = os_torrent.torrenti()
        tekel = motor.tece()
        try:
            return knjiznica_kroga.odstrani_lokalnega(hash_, motor)
        finally:
            if not tekel and motor.tece():
                motor.ustavi()

    def _ukaz_tukaj(self, dejanje: str, parametri: dict) -> dict:
        """Ukaz za prenose (magnet.list / magnet.stream / magnet.remove) temu racunalniku: polica »Na tvojih napravah« v
        Safeer OS vprasa tudi Control na istem racunalniku. Izvedemo ga tukaj - sredisce bi ga zavrnilo (ista naprava)."""
        konec, izid = threading.Event(), {}

        def koncaj(r: dict) -> None:
            izid.update(r if isinstance(r, dict) else {})
            konec.set()
        link = self.link
        link_daljinec.izvedi_control(dejanje, parametri, lambda _naslov: None, koncaj, datoteke=self.datoteke,
                                     posiljatelj=link._id(), hub_url=link._hub() or "")
        # Klic D-Bus Safeer OS caka najvec minuto: tok, ki se pripravlja dlje, stran vprasa znova (koda "cas").
        if not konec.wait(50.0 if dejanje == "magnet.stream" else 20.0):
            return {"ok": False, "message": "Računalnik še pripravlja odgovor.", "koda": "cas", "data": {}}
        return {"ok": bool(izid.get("ok")), "message": str(izid.get("message") or ""), "koda": str(izid.get("code") or ""),
                "data": izid.get("data") if isinstance(izid.get("data"), dict) else {}}

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
            zapri_deljeni_zaslon=self._zapri_gledalca,
            odpri_oddaljeni_zaslon=self.upravljaj_racunalnik,
            odpri_zaslon=self._odpri_gledalca,
        )
        self.link.ob_povezavi = self._na_povezavo
        self.link.ob_brez_povezave = self.odpri_safeer_os
        self.link.ob_seznanitvi = self._po_seznanitvi
        self.link.datoteke = self.datoteke
        self.link.programi = self.programi
        self.link.zaslon = self.zaslon
        self.link.zvok = self.zvok
        # »Nadaljuj z druge naprave«: telefon vprasa (play.state), kaj Safeer OS tu predvaja, in nadaljuje pri isti
        # sekundi. Izklop: "predvajanje_za_naprave" v control.json (meni v pladnju).
        from core import link_predvajanje
        self.link.predvajanje = link_predvajanje.za_control(
            self.datoteke, deli=lambda: bool(self.nastavitve.get("predvajanje_za_naprave", True)))
        self.link.predvajanje.ob_ponudbi = lambda p: GLib.idle_add(self._pokazi_ponudbo, p)
        self.zvok.ob_spremembi = lambda _opis: self.link.zapisi_stanje_za_os() if self.link is not None else None
        self._pripravi_internet()

    # ------------------------------------------------------------------ internet prek telefona (Safeer Internet Gateway)
    internet = None

    #: Obvestili ob preklopu (nacin »ob izpadu«): naslov, besedilo.
    OBVESTILA_INTERNETA = {
        "sl": {"prek_telefona": ("Domači internet ne dela", "Safeer zdaj uporablja mobilni internet naprave {telefon}."),
               "nazaj_doma": ("Domači internet spet dela", "Safeer ne uporablja več mobilnega interneta telefona.")},
        "en": {"prek_telefona": ("Home internet is down", "Safeer now uses the mobile internet of {telefon}."),
               "nazaj_doma": ("Home internet is back", "Safeer no longer uses the phone's mobile internet.")},
        "de": {"prek_telefona": ("Heim-Internet ausgefallen", "Safeer nutzt jetzt das mobile Internet von {telefon}."),
               "nazaj_doma": ("Heim-Internet funktioniert wieder", "Safeer nutzt das mobile Internet des Telefons nicht mehr.")},
        "es": {"prek_telefona": ("Internet de casa no funciona", "Safeer usa ahora el internet móvil de {telefon}."),
               "nazaj_doma": ("Internet de casa vuelve a funcionar", "Safeer ya no usa el internet móvil del teléfono.")},
        "fr": {"prek_telefona": ("Internet de la maison est en panne", "Safeer utilise maintenant l'internet mobile de {telefon}."),
               "nazaj_doma": ("Internet de la maison fonctionne à nouveau", "Safeer n'utilise plus l'internet mobile du téléphone.")},
        "it": {"prek_telefona": ("Internet di casa non funziona", "Safeer ora usa l'internet mobile di {telefon}."),
               "nazaj_doma": ("Internet di casa funziona di nuovo", "Safeer non usa più l'internet mobile del telefono.")},
    }

    def _pripravi_internet(self) -> None:
        """Tokovi skozi telefon v Linku in krajevni posrednik. Privzeto izklopljeno; vklopi uporabnik."""
        link = self.link
        link.internet = link_internet.InternetPrekLinka(
            lambda s: bool(link.povezava is not None and link.povezava.poslji(s)))
        self.internet = link_internet_posrednik.InternetUpravitelj(
            link.internet, lambda: link.naprave_vse, os.path.join(NASTAVITVE_MAPA, "internet.json"),
            sistemski=sistemski_posrednik.SistemskiPosrednik(os.path.join(NASTAVITVE_MAPA, "sistemski-posrednik.json")),
            obvesti=self._obvestilo_interneta)
        link.internet_upravitelj = self.internet
        # Zagon (sistemski posrednik po sesutju, posrednik, sonda) klice gsettings: ne na glavni niti.
        threading.Thread(target=self.internet.zazeni, name="safeer-internet-zagon", daemon=True).start()

    def _obvestilo_interneta(self, koda: str, podatki: dict) -> None:
        import shutil
        if not shutil.which("notify-send"):
            return
        jezik = self.link._jezik() if self.link is not None else "en"
        besedila = self.OBVESTILA_INTERNETA.get(jezik) or self.OBVESTILA_INTERNETA["en"]
        if koda not in besedila:
            return
        naslov, besedilo = besedila[koda]
        try:
            subprocess.Popen(["notify-send", "-a", "Safeer Control", "-i", "safeer-control", naslov,
                              besedilo.format(telefon=str(podatki.get("telefon") or "?"))],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:  # noqa: BLE001
            pass

    def _internet_metoda(self, ukaz: str, p: dict) -> dict:
        """D-Bus `Internet(ukaz, parametri)`: stanje | nastavi | preizkus | okolje."""
        u = self.internet
        if u is None:
            return {"ok": False, "koda": "ni_na_voljo"}
        if ukaz == "stanje":
            return u.stanje(vprasaj=bool(p.get("vprasaj")))
        if ukaz == "nastavi":
            nacin, naprava, pot, sistemski = p.get("nacin"), p.get("naprava"), p.get("pot"), p.get("sistemski")
            if any(x is not None and not isinstance(x, str) for x in (nacin, naprava, pot)) or \
                    (sistemski is not None and not isinstance(sistemski, bool)):
                return {"ok": False, "koda": "napacna_zahteva"}
            return u.nastavi(nacin=nacin, naprava=naprava, sistemski=sistemski, pot=pot)
        if ukaz == "preizkus":
            return u.preizkus(str(p.get("naprava") or ""), str(p.get("pot") or ""), bool(p.get("stari")))
        if ukaz == "okolje":
            return {"ok": True, "okolje": u.okolje(), "tece": u.posrednik.tece}
        return {"ok": False, "koda": "napacna_zahteva"}

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

    def _nova_oddaljena_seja(self, id_naprave: str) -> dict:
        """Zahteva nov enkraten zeton in doda naslov iz seznama naprav."""
        if self.link is None:
            self._pripravi_link()
        naprava = next((n for n in self.link.naprave if n.get("id") == id_naprave), None)
        if naprava is None:
            return {"ok": False, "message": "Naprava ni vec povezana."}
        if not str(naprava.get("naslov") or "").strip():
            # Slika gre neposredno z naprave. Brez njenega naslova (dosegljiva je samo prek Global Linka) je ne
            # prosimo: naprava bi zaman odprla vrata in cakala na nas.
            return {"ok": False, "koda": "ni_naslova",
                    "message": "%s zdaj ni dosegljiv neposredno. Slika zaslona deluje samo v istem omrežju (doma), "
                               "prek Global Linka ne." % str(naprava.get("ime") or id_naprave)}
        odgovor = self.link.ukaz_pocakaj(id_naprave, "screen.start",
                                         {"quality": "srednja", "screen": "desktop"}, cas=15.0)
        if not odgovor.get("ok"):
            # Sporocilo ciljne naprave mora ostati nespremenjeno (tudi zavrnitev dovoljenja).
            return {"ok": False, "message": str(odgovor.get("message") or "Naprava je zahtevo zavrnila."),
                    "koda": str(odgovor.get("koda") or "")}
        try:
            from core.link_gledalec import razcleni_odgovor
            seja = razcleni_odgovor(odgovor)
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "message": str(e)}
        return {"ok": True, "ime": str(naprava.get("ime") or id_naprave),
                "naslov": str(naprava.get("naslov") or ""), "seja": seja}

    def upravljaj_racunalnik(self, id_naprave: str) -> dict:
        """Pripravi sejo in odpre GTK3 gledalec v glavnem procesu Controla."""
        id_naprave = str(id_naprave or "")
        if not id_naprave:
            return {"ok": False, "message": "Naprava ni izbrana."}
        # Metoda se klice iz delovne niti Safeer Linka. GTK spremembe zato prepustimo glavni zanki.
        stari = self._oddaljeni_gledalec
        if stari is not None:
            koncano = threading.Event()

            def zapri_starega() -> bool:
                stari.zapri(sporoci_stop=False)
                koncano.set()
                return False

            GLib.idle_add(zapri_starega)
            koncano.wait(3.0)
            self._ustavi_oddaljeno_sejo(stari.id_naprave)
        zacetna = self._nova_oddaljena_seja(id_naprave)
        if not zacetna.get("ok"):
            return zacetna
        GLib.idle_add(self._odpri_oddaljeni_gledalec, id_naprave, zacetna)
        return {"ok": True}

    def _odpri_oddaljeni_gledalec(self, id_naprave: str, podatki: dict) -> bool:
        try:
            okno = OddaljeniGledalec(self, id_naprave, podatki)
            self._oddaljeni_gledalec = okno
            self.add_window(okno)
            okno.present()
        except Exception as e:  # noqa: BLE001
            print("[SafeerControl] Gledalca ni bilo mogoce odpreti:", e)
            threading.Thread(target=self._ustavi_oddaljeno_sejo, args=(id_naprave,), daemon=True).start()
        return False

    def _ustavi_oddaljeno_sejo(self, id_naprave: str) -> None:
        try:
            if self.link is not None:
                self.link.ukaz_pocakaj(id_naprave, "screen.stop", {}, cas=5.0)
        except Exception as e:  # noqa: BLE001
            print("[SafeerControl] Oddaljene seje ni bilo mogoce ustaviti:", e)

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

    def nastavi_predvajanje_za_naprave(self, deli: bool) -> None:
        """Ali druge naprave smejo vprasati, kaj tu igra, nadaljevati tam in poslati sem (play.state/stop/offer)."""
        self.nastavitve.set("predvajanje_za_naprave", bool(deli))
        if self.pladenj is not None:
            self.pladenj.osvezi_predvajanje()

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
            oddaljeni = self._oddaljeni_gledalec
            if oddaljeni is not None:
                oddaljeni.zapri(sporoci_stop=False)
                self._ustavi_oddaljeno_sejo(oddaljeni.id_naprave)
        except Exception:
            pass
        try:
            if self.link is not None and self.link.povezava is not None:
                self.link.povezava.zapri()
        except Exception:
            pass
        try:
            # Sistemski posrednik namizja se vrne na prejsnje vrednosti, tokovi skozi telefon se zaprejo.
            if self.internet is not None:
                self.internet.ustavi()
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

    # ------------------------------------------------------------------ "Poslji na napravo": ta racunalnik kot cilj
    #: Pasica s ponudbo (majhno okno v kotu zaslona) - ena naenkrat.
    _pasica_ponudbe = None
    PASICA_S = 60

    def _pokazi_ponudbo(self, p: dict) -> bool:
        """Tiha pasica »Tablica ti posilja: Film (pri 12:34)« z gumboma Sprejmi/Zavrni v spodnjem desnem kotu: majhno
        okno brez okvirja, ki ne vzame fokusa in ne odpre nicesar; po minuti se umakne (ponudba velja se 10 minut).
        Lastno okno namesto namiznega obvestila: v Cinnamonu so obvestila lahko izklopljena (display-notifications
        false) in uporabnik ponudbe sploh ne bi videl. Nic se ne predvaja in nic se ne ustavi, dokler ne pritisne Sprejmi."""
        from core import link_predvajanje
        self._umakni_pasico()
        try:
            jezik = self.nastavitve.get("ui_language")
            ime = str(p.get("od_ime") or "")
            if self.link is not None:
                ime = next((str(n.get("ime") or "") for n in self.link.naprave if n.get("id") == p.get("od")), "") or ime
            okno = Gtk.Window(type=Gtk.WindowType.TOPLEVEL, title=besedilo(jezik, "ponudba_naslov"))
            okno.set_decorated(False)
            okno.set_type_hint(Gdk.WindowTypeHint.NOTIFICATION)
            okno.set_keep_above(True)
            okno.set_accept_focus(False)
            okno.set_skip_taskbar_hint(True)
            okno.set_skip_pager_hint(True)
            okno.set_resizable(False)
            okno.set_border_width(14)
            okno.get_style_context().add_class("safeer-pasica")
            css = Gtk.CssProvider()
            css.load_from_data(b"""
                window.safeer-pasica { background: #0f1a26; color: #f0f4f3; border: 1px solid #26364a; border-radius: 12px; }
                window.safeer-pasica label { color: #f0f4f3; }
                window.safeer-pasica button { background: #152129; color: #f0f4f3; border: 1px solid #26364a; border-radius: 10px; padding: 6px 14px; }
                window.safeer-pasica button:hover { border-color: #57d6ad; }
            """)
            Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            skatla = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            napis = Gtk.Label(label=besedilo(jezik, "ponudba").format(naprava=ime or p.get("od", ""), kaj=link_predvajanje.opis_ponudbe(p)))
            napis.set_line_wrap(True)
            napis.set_max_width_chars(44)
            napis.set_xalign(0)
            skatla.pack_start(napis, True, True, 0)
            sprejmi = Gtk.Button(label=besedilo(jezik, "sprejmi"))
            sprejmi.connect("clicked", lambda *_a: (self._umakni_pasico(), self.predaja_sprejmi()))
            zavrni = Gtk.Button(label=besedilo(jezik, "zavrni"))
            zavrni.connect("clicked", lambda *_a: (self._umakni_pasico(), self.predaja_zavrni()))
            skatla.pack_start(sprejmi, False, False, 0)
            skatla.pack_start(zavrni, False, False, 0)
            okno.add(skatla)
            okno.show_all()
            # Spodnji desni kot glavnega zaslona (nad pultom): okno je ze narisano, zato poznamo njegovo velikost.
            try:
                zaslon = Gdk.Display.get_default()
                g = (zaslon.get_primary_monitor() or zaslon.get_monitor(0)).get_workarea()
                sirina, visina = okno.get_size()
                okno.move(g.x + g.width - sirina - 24, g.y + g.height - visina - 24)
            except Exception:  # noqa: BLE001
                pass
            self._pasica_ponudbe = okno
            GLib.timeout_add_seconds(self.PASICA_S, lambda: (self._umakni_pasico(okno), False)[1])
        except Exception as e:  # noqa: BLE001
            print("[SafeerControl] pasica ponudbe:", e)
        return False

    def _umakni_pasico(self, okno=None) -> None:
        o = self._pasica_ponudbe
        if o is None or (okno is not None and okno is not o):
            return
        self._pasica_ponudbe = None
        try:
            o.destroy()
        except Exception:  # noqa: BLE001
            pass

    def predaja_zavrni(self) -> None:
        self._umakni_pasico()
        if self.link is not None and self.link.predvajanje is not None:
            self.link.predvajanje.zavrni_ponudbo()

    def predaja_sprejmi(self) -> None:
        """Sprejmi: ponudbo preda Safeer OS (tece -> dejanje `ponudba` prek D-Bus; sicer ga zazene z njo)."""
        self._umakni_pasico()
        pr = self.link.predvajanje if self.link is not None else None
        p = pr.vzemi_ponudbo() if pr is not None else None
        if p is None:
            return
        try:
            from core import link_krog
            clan = link_krog.krog().clan_za_id(str(p.get("server_device") or p.get("od") or "")) or {}
            p["kljuc"] = str(clan.get("kljuc") or "")
        except Exception:  # noqa: BLE001
            p["kljuc"] = ""
        if p.get("server_device") and p["server_device"] == self.link._id() and self.datoteke is not None:
            # Datoteka tega racunalnika, ki se vraca (telefon jo je igral od tod): Safeer OS jo odpre kar z diska.
            try:
                r = self.datoteke.mape.razresi(str((p.get("item") or {}).get("id") or ""))
                if r is not None and os.path.isfile(r[1]):
                    p["lokalna_pot"] = r[1]
            except Exception:  # noqa: BLE001
                pass
        podatki = json.dumps(p, ensure_ascii=True)
        try:
            vodilo = self.get_dbus_connection() or Gio.bus_get_sync(Gio.BusType.SESSION, None)
            tece = vodilo.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "NameHasOwner",
                                    GLib.Variant("(s)", (OS_ID,)), GLib.VariantType("(b)"), Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]
            if tece:
                vodilo.call_sync(OS_ID, "/" + OS_ID.replace(".", "/"), "org.gtk.Actions", "Activate",
                                 GLib.Variant("(sava{sv})", ("ponudba", [GLib.Variant("s", podatki)], {})),
                                 None, Gio.DBusCallFlags.NONE, 5000, None)
                return
        except Exception as e:  # noqa: BLE001
            print("[SafeerControl] ponudba Safeer OS:", e)
        from core import link_daljinec
        program = link_daljinec._safeer_os()
        if not program:
            print("[SafeerControl] ponudba: Safeer OS ni namescen")
            return
        subprocess.Popen([program, "--ponudba", podatki], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)

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

    # ------------------------------------------------------------------ posodobitve s safeer.si (pladenj)
    def _posodobitve_razlicice(self) -> dict:
        """Kar Control lahko posodobi sam: sebe in - ce je Safeer OS namescen kot paket - tudi njega (isti pkexec apt-get)."""
        r = {"safeer-control": APP_VERSION} if APP_VERSION else {}
        try:
            v = subprocess.run(["dpkg-query", "-W", "-f=${Version}", "safeer-os"], capture_output=True, text=True, timeout=10).stdout.strip()
            if v:
                r["safeer-os"] = v
        except Exception:
            pass
        return r

    def _posodobitve_preveri(self) -> bool:
        """Tiha preverba (2 min po zagonu, nato na 6 ur); izid pokaze postavka v pladnju. Brez omrezja: nic."""
        def delo() -> None:
            try:
                if os_posodobitve.nacin_namestitve() != "deb":
                    return   # Flatpak/AppImage/razvojna kopija: posodobitve vodi Safeer OS ali uporabnik sam
                izid = os_posodobitve.preveri("linux", self._posodobitve_razlicice(), nacin="deb")
            except Exception as e:  # noqa: BLE001
                print("[SafeerControl] posodobitve:", e)
                return
            self.posodobitve_izid = izid
            GLib.idle_add(lambda: (self.pladenj.osvezi_posodobitev() if self.pladenj is not None else None) and False)
        threading.Thread(target=delo, name="safeer-control-posodobitve", daemon=True).start()
        GLib.timeout_add_seconds(os_posodobitve.PREVERBA_S, self._posodobitve_preveri)
        return False

    def posodobi_iz_pladnja(self) -> None:
        """Prenese pakete (SHA-256) in jih namesti prek pkexec apt-get; majhno okno kaze napredek in izid."""
        izid = self.posodobitve_izid or {}
        nove = [n for n in izid.get("nove") or [] if n.get("datoteka")]
        if not nove or self.posodabljanje.tece():
            return
        jezik = self.nastavitve.get("ui_language")
        okno = Gtk.Window(title=besedilo(jezik, "posodobi_naslov"))
        okno.set_default_size(420, 120)
        okno.set_border_width(16)
        okno.set_position(Gtk.WindowPosition.CENTER)
        skatla = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        napis = Gtk.Label(label=besedilo(jezik, "posodobi_prenasam").replace("{ime}", ""), xalign=0)
        napis.set_line_wrap(True)
        vrstica = Gtk.ProgressBar()
        skatla.pack_start(napis, False, False, 0)
        skatla.pack_start(vrstica, False, False, 0)
        okno.add(skatla)
        okno.show_all()

        def delo(p: os_posodobitve.Posodabljanje) -> None:
            mapa = os.path.join(GLib.get_user_cache_dir(), "safeer-control", "posodobitve")
            datoteke = []
            for n in nove:
                for d in ([n["datoteka"]] + ([n["tema"]] if n.get("tema") else [])):
                    ime = str(d["url"]).rsplit("/", 1)[-1]
                    GLib.idle_add(napis.set_text, besedilo(jezik, "posodobi_prenasam").replace("{ime}", ime))
                    datoteke.append(os_posodobitve.prenesi(str(d["url"]), os.path.join(mapa, ime), str(d.get("sha256") or ""),
                                                           int(d.get("velikost") or 0),
                                                           lambda a, b: GLib.idle_add(vrstica.set_fraction, (a / b) if b else 0.0),
                                                           lambda: p.prekinjeno, agent="SafeerControl/" + APP_VERSION))
            p.faza = "namescanje"
            GLib.idle_add(napis.set_text, besedilo(jezik, "posodobi_namescam"))
            GLib.idle_add(vrstica.set_fraction, 1.0)
            r = os_posodobitve.namesti_linux("deb", datoteke)
            if r.returncode != 0:
                raise RuntimeError((r.stderr or r.stdout or "").strip()[-300:] or "apt-get")
            for d in datoteke:
                try:
                    os.remove(d)
                except OSError:
                    pass
            self.posodobitve_izid = None
            GLib.idle_add(lambda: (self.pladenj.osvezi_posodobitev() if self.pladenj is not None else None) and False)
            GLib.idle_add(napis.set_text, besedilo(jezik, "posodobi_koncano").replace("{opis}", os_posodobitve.opis(izid)))

        def po_koncu() -> bool:
            if self.posodabljanje.tece():
                return True
            if self.posodabljanje.faza == "napaka":
                napis.set_text(besedilo(jezik, "posodobi_napaka").replace("{napaka}", self.posodabljanje.sporocilo))
            return False
        self.posodabljanje.zacni(delo)
        GLib.timeout_add(500, po_koncu)

    def do_activate(self) -> None:
        if self.ozadje and self._prva_aktivacija:
            self._prva_aktivacija = False
            if self.link is None:
                self._pripravi_link()
            self.pladenj = Pladenj(self)
            self.link.povezi_v_ozadju()
            GLib.timeout_add_seconds(120, self._posodobitve_preveri)
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

    def _zapri_gledalca(self) -> None:
        """Ob koncu share.screen odstrani zadnjo sliko in zapri samo vgrajeni gledalec."""
        if self.gledalec is None:
            return
        okno = self.gledalec
        self.gledalec = None
        try:
            pogled = okno.get_child()
            if pogled is not None:
                pogled.load_uri("about:blank")
            okno.destroy()
        except Exception as e:  # noqa: BLE001
            print(f"[SafeerControl] Gledalca ni bilo mogoce zapreti: {e}")

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


#: Zaklep enega primerka (drzimo ga do konca programa).
_ZAKLEP_PRIMERKA = None


def _pokazi_tekocega(cakaj_s: float = 8.0) -> bool:
    """Control ze tece: pokaze njegovo okno (org.freedesktop.Application.Activate). Ce se se zaganja, pocaka, da se
    javi na vodilu. Vrne, ali je uspelo."""
    try:
        vodilo = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        konec = time.monotonic() + cakaj_s
        while time.monotonic() < konec:
            ima = vodilo.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "NameHasOwner",
                                   GLib.Variant("(s)", (APP_ID,)), GLib.VariantType("(b)"),
                                   Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]
            if ima:
                vodilo.call_sync(APP_ID, CONTROL_POT, "org.freedesktop.Application", "Activate",
                                 GLib.Variant("(a{sv})", ({},)), None, Gio.DBusCallFlags.NONE, 5000, None)
                return True
            time.sleep(0.25)
    except Exception:  # noqa: BLE001 - brez vodila ali starejsi primerek: nadaljujemo po stari poti
        pass
    return False


def main() -> int:
    global _ZAKLEP_PRIMERKA
    if "--version" in sys.argv[1:]:
        print(f"Safeer Control {APP_VERSION}")
        return 0
    ozadje = "--ozadje" in sys.argv[1:]
    # En primerek. GApplication ob drugem zagonu tekocemu poslje »activate« in ta odpre okno - tudi ce je drugi zagon
    # zahteval ozadje (Safeer OS in samozagon ob prijavi startata hkrati). Poleg tega bi drugi primerek se pred tem
    # pospravil navidezne zvocne izhode tekocega. Zato: zagon v ozadju, ko Control ze tece, se konca tiho; zagon iz
    # menija tekocemu samo pokaze okno.
    _ZAKLEP_PRIMERKA = os_stabilnost.zakleni_primerek("safeer-control")
    if _ZAKLEP_PRIMERKA is None:
        if ozadje or _pokazi_tekocega():
            return 0
    # Sled ob sesutju in dnevnik neujetih izjem (~/.cache/safeer-control/). Control tece ves dan v
    # ozadju; brez tega naprave samo izgubijo racunalnik in nihce ne ve, zakaj.
    os_stabilnost.vkljuci("safeer-control")
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
