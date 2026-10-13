"""Vdelani Safeer Browser za razdelek Splet v Safeer OS.

Varnostna pravila niso podvojena: uporablja iste nastavitve, filtre, skripte,
BankGuard in podpisan vir grozenj kot ``safeer_mint.py``.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.parse
import weakref
from html import escape as _escape_html
from pathlib import Path

from core import adblock, drm, odlozisce_varuh, os_stabilnost, ozadje_strani, splet_temno
from core.config import ConfigManager, SEARCH_ENGINES, normalize_web_url
from core.doh_proxy import get_doh_proxy
from core.filter_lists import FILTER_ID


JEZIKI = ("sl", "en", "de", "es", "fr", "it")
BESEDILA = {
    "sl": {"nov": "Nov zavihek", "naslov": "Išči ali vnesi spletni naslov …", "nazaj": "Nazaj",
           "naprej": "Naprej", "osvezi": "Osveži", "domov": "Domov", "povezan": "Povezano",
           "nepovezan": "Ni povezano", "scit": "Safeer Ščit", "meni": "Meni", "prenosi": "Prenosi",
           "najdi": "Najdi na strani", "povecaj": "Povečaj", "pomanjsaj": "Pomanjšaj",
           "nastavitve": "Nastavitve brskalnika", "zapisek": "V zapisek …", "dodaj": "Dodaj bližnjico",
           "ime": "Ime", "url": "Naslov", "preklici": "Prekliči", "shrani": "Shrani",
           "blokirano": "Blokiranih oglasov in groženj: {count}", "isci": "Najdi …"},
    "en": {"nov": "New tab", "naslov": "Search or enter a web address …", "nazaj": "Back",
           "naprej": "Forward", "osvezi": "Reload", "domov": "Home", "povezan": "Connected",
           "nepovezan": "Not connected", "scit": "Safeer Shield", "meni": "Menu", "prenosi": "Downloads",
           "najdi": "Find on page", "povecaj": "Zoom in", "pomanjsaj": "Zoom out",
           "nastavitve": "Browser settings", "zapisek": "Add to note …", "dodaj": "Add shortcut",
           "ime": "Name", "url": "Address", "preklici": "Cancel", "shrani": "Save",
           "blokirano": "Blocked ads and threats: {count}", "isci": "Find …"},
    "de": {"nov": "Neuer Tab", "naslov": "Suchen oder Webadresse eingeben …", "nazaj": "Zurück",
           "naprej": "Vor", "osvezi": "Neu laden", "domov": "Startseite", "povezan": "Verbunden",
           "nepovezan": "Nicht verbunden", "scit": "Safeer-Schutz", "meni": "Menü", "prenosi": "Downloads",
           "najdi": "Auf Seite suchen", "povecaj": "Vergrößern", "pomanjsaj": "Verkleinern",
           "nastavitve": "Browser-Einstellungen", "zapisek": "Zu Notiz hinzufügen …", "dodaj": "Verknüpfung hinzufügen",
           "ime": "Name", "url": "Adresse", "preklici": "Abbrechen", "shrani": "Speichern",
           "blokirano": "Blockierte Werbung und Bedrohungen: {count}", "isci": "Suchen …"},
    "es": {"nov": "Nueva pestaña", "naslov": "Busca o escribe una dirección web …", "nazaj": "Atrás",
           "naprej": "Adelante", "osvezi": "Recargar", "domov": "Inicio", "povezan": "Conectado",
           "nepovezan": "Sin conexión", "scit": "Escudo Safeer", "meni": "Menú", "prenosi": "Descargas",
           "najdi": "Buscar en la página", "povecaj": "Ampliar", "pomanjsaj": "Reducir",
           "nastavitve": "Ajustes del navegador", "zapisek": "Añadir a una nota …", "dodaj": "Añadir acceso",
           "ime": "Nombre", "url": "Dirección", "preklici": "Cancelar", "shrani": "Guardar",
           "blokirano": "Anuncios y amenazas bloqueados: {count}", "isci": "Buscar …"},
    "fr": {"nov": "Nouvel onglet", "naslov": "Rechercher ou saisir une adresse web …", "nazaj": "Retour",
           "naprej": "Suivant", "osvezi": "Actualiser", "domov": "Accueil", "povezan": "Connecté",
           "nepovezan": "Non connecté", "scit": "Bouclier Safeer", "meni": "Menu", "prenosi": "Téléchargements",
           "najdi": "Rechercher dans la page", "povecaj": "Agrandir", "pomanjsaj": "Réduire",
           "nastavitve": "Paramètres du navigateur", "zapisek": "Ajouter à une note …", "dodaj": "Ajouter un raccourci",
           "ime": "Nom", "url": "Adresse", "preklici": "Annuler", "shrani": "Enregistrer",
           "blokirano": "Publicités et menaces bloquées : {count}", "isci": "Rechercher …"},
    "it": {"nov": "Nuova scheda", "naslov": "Cerca o inserisci un indirizzo web …", "nazaj": "Indietro",
           "naprej": "Avanti", "osvezi": "Ricarica", "domov": "Pagina iniziale", "povezan": "Connesso",
           "nepovezan": "Non connesso", "scit": "Scudo Safeer", "meni": "Menu", "prenosi": "Download",
           "najdi": "Trova nella pagina", "povecaj": "Ingrandisci", "pomanjsaj": "Riduci",
           "nastavitve": "Impostazioni del browser", "zapisek": "Aggiungi a una nota …", "dodaj": "Aggiungi scorciatoia",
           "ime": "Nome", "url": "Indirizzo", "preklici": "Annulla", "shrani": "Salva",
           "blokirano": "Annunci e minacce bloccati: {count}", "isci": "Trova …"},
}

# Ko se proces strani sesuje ali preseze mejo pomnilnika (web-process-terminated).
_PROCES = {
    "sl": ("Stran se je zaprla", "Ta stran je porabila preveč pomnilnika ali se je sesula, zato jo je Safeer ustavil, da računalnik ostane odziven.", "Naloži znova"),
    "en": ("The page stopped", "This page used too much memory or crashed, so Safeer stopped it to keep your computer responsive.", "Reload"),
    "de": ("Die Seite wurde beendet", "Diese Seite hat zu viel Speicher verbraucht oder ist abgestürzt. Safeer hat sie beendet, damit der Computer reaktionsfähig bleibt.", "Neu laden"),
    "es": ("La página se detuvo", "Esta página usó demasiada memoria o falló, así que Safeer la detuvo para que el ordenador siga respondiendo.", "Recargar"),
    "fr": ("La page s'est arrêtée", "Cette page a utilisé trop de mémoire ou a planté ; Safeer l'a arrêtée pour que l'ordinateur reste réactif.", "Recharger"),
    "it": ("La pagina si è interrotta", "Questa pagina ha usato troppa memoria o si è bloccata, quindi Safeer l'ha fermata per mantenere reattivo il computer.", "Ricarica"),
}

# Skupna dodatna besedila so zapisana posebej, da zgornji slovar ostane berljiv.
_DODATNA = {
    "sl": ("Spletna stran zahteva posebno dovoljenje.", "Zavrni", "Dovoli", "Iskalnik", "Blokiraj oglase in sledilce", "Šifriran DNS (DoH)"),
    "en": ("The website requests a special permission.", "Deny", "Allow", "Search engine", "Block ads and trackers", "Encrypted DNS (DoH)"),
    "de": ("Die Website fordert eine besondere Berechtigung an.", "Ablehnen", "Zulassen", "Suchmaschine", "Werbung und Tracker blockieren", "Verschlüsseltes DNS (DoH)"),
    "es": ("El sitio web solicita un permiso especial.", "Denegar", "Permitir", "Buscador", "Bloquear anuncios y rastreadores", "DNS cifrado (DoH)"),
    "fr": ("Le site demande une autorisation spéciale.", "Refuser", "Autoriser", "Moteur de recherche", "Bloquer les publicités et traqueurs", "DNS chiffré (DoH)"),
    "it": ("Il sito richiede un'autorizzazione speciale.", "Nega", "Consenti", "Motore di ricerca", "Blocca annunci e tracker", "DNS crittografato (DoH)"),
}
for _jezik, _vrednosti in _DODATNA.items():
    BESEDILA[_jezik].update(dict(zip(("dovoljenje", "zavrni", "dovoli", "iskalnik", "adblock", "doh"), _vrednosti)))
for _jezik, _vrednosti in _PROCES.items():
    BESEDILA[_jezik].update(dict(zip(("proces_naslov", "proces_besedilo", "proces_znova"), _vrednosti)))


#: Ozadje pogleda pod našimi stranmi (pod spletnimi je belo, glej core/ozadje_strani.py).
TEMNO_OZADJE = "#0b1424"


def peskovnik_dela(zazeni=None, kje=None, obstaja=None, okolje=None) -> bool:
    """Ali se WebKitov peskovnik (bubblewrap) na tem sistemu lahko zažene?

    Kjer jedro ne dovoli uporabniških imenskih prostorov (zabojniki, nekatera utrjena jedra), WebKit ob prvem
    pogledu s peskovnikom ubije CEL proces (»Failed to fully launch dbus-proxy«) - v Safeer OS bi klik na Splet
    podrl lupino. Zato to preverimo prej, v ločenem procesu. V Flatpaku WebKit uporabi flatpak-spawn, z
    WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS=1 pa peskovnika sploh ne zažene: tam ni česa preverjati.
    """
    zazeni, kje = zazeni or subprocess.run, kje or shutil.which
    obstaja, okolje = obstaja or os.path.exists, os.environ if okolje is None else okolje
    if obstaja("/.flatpak-info") or okolje.get("WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS") == "1":
        return True
    bwrap = kje("bwrap")
    if not bwrap or not kje("xdg-dbus-proxy"):
        return False
    try:
        # WebKit v peskovniku priklopi tudi /proc in /dev (za xdg-dbus-proxy in spletni proces). Stresni preizkus
        # 12. 10. 2026: v zabojniku je goli --unshare-all uspel, »--proc /proc« pa ne (»Can't mount proc«) - WebKit je
        # nato ob vsakem odprtju Spleta podrl Safeer OS (SIGTRAP). Zato preverimo isto, kar potrebuje WebKit.
        return zazeni([bwrap, "--unshare-all", "--die-with-parent", "--ro-bind", "/", "/", "--proc", "/proc",
                       "--dev", "/dev", "true"], stdin=subprocess.DEVNULL,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8).returncode == 0
    except Exception:
        return False


def omrezni_procesi(starsevski: int | None = None) -> set:
    """PID-i omreznih procesov WebKita, ki so neposredni otroci tega procesa."""
    starsevski = os.getpid() if starsevski is None else starsevski
    izid = set()
    try:
        imena = os.listdir("/proc")
    except OSError:
        return izid
    for ime in imena:
        if not ime.isdigit():
            continue
        try:
            with open("/proc/%s/stat" % ime, encoding="utf-8", errors="replace") as f:
                stat = f.read()
        except OSError:
            continue
        glava, _, rep_ = stat.rpartition(")")
        if "WebKitNetworkPr" not in glava:
            continue
        try:
            if int(rep_.split()[1]) == starsevski:
                izid.add(int(ime))
        except (IndexError, ValueError):
            continue
    return izid


def odprte_datoteke(pid: int) -> set:
    """Poti datotek, ki jih ima proces odprte (/proc/<pid>/fd); prazno, ce ni dostopa."""
    izid = set()
    mapa = "/proc/%d/fd" % pid
    try:
        imena = os.listdir(mapa)
    except OSError:
        return izid
    for ime in imena:
        try:
            izid.add(os.path.realpath(os.readlink(os.path.join(mapa, ime))))
        except OSError:
            continue
    return izid


def pss_mb(pid: int) -> float:
    """PSS procesa v MiB iz /proc/<pid>/smaps_rollup; 0, ce ni dostopa."""
    try:
        with open("/proc/%d/smaps_rollup" % pid, encoding="ascii", errors="replace") as f:
            for vrstica in f:
                if vrstica.startswith("Pss:"):
                    return int(vrstica.split()[1]) / 1024.0
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


def omrezni_procesi_shrambe(piskotki: str, starsevski: int | None = None) -> list:
    """Omrezni procesi WebKita (otroci tega procesa), ki imajo odprto dano shrambo piskotkov.

    Tako locimo omrezni proces enega programa od drugih v istem procesu (namizje, Control)."""
    cilj = os.path.realpath(piskotki)
    return sorted(pid for pid in omrezni_procesi(starsevski) if cilj in odprte_datoteke(pid))


# Zaznamki, zgodovina in uvoz (12. 10. 2026: Splet naj bo enostavna zamenjava za drug brskalnik)
for _j, _b in {
    "sl": {"strojno": "Strojno pospeševanje (izklopi, če se strani prikazujejo napačno)", "zaznamki": "Zaznamki", "zgodovina": "Zgodovina", "uvozi": "Uvozi iz drugega brskalnika …",
           "uvoz_zaznamki": "Zaznamkov dodanih: {n} (iz: {od}).", "uvoz_brez": "Drugega brskalnika s podatki ni bilo mogoče najti.",
           "uvoz_zavihki": "Odpri {n} zavihkov iz brskalnika {ime}", "zapri": "Zapri", "prazno": "Ni zadetkov."},
    "en": {"strojno": "Hardware acceleration (turn off if pages display incorrectly)", "zaznamki": "Bookmarks", "zgodovina": "History", "uvozi": "Import from another browser …",
           "uvoz_zaznamki": "Bookmarks added: {n} (from: {od}).", "uvoz_brez": "No other browser with data was found.",
           "uvoz_zavihki": "Open {n} tabs from {ime}", "zapri": "Close", "prazno": "No results."},
    "de": {"strojno": "Hardwarebeschleunigung (ausschalten, wenn Seiten falsch angezeigt werden)", "zaznamki": "Lesezeichen", "zgodovina": "Verlauf", "uvozi": "Aus anderem Browser importieren …",
           "uvoz_zaznamki": "Lesezeichen hinzugefügt: {n} (aus: {od}).", "uvoz_brez": "Kein anderer Browser mit Daten gefunden.",
           "uvoz_zavihki": "{n} Tabs aus {ime} öffnen", "zapri": "Schließen", "prazno": "Keine Treffer."},
    "es": {"strojno": "Aceleración por hardware (desactívala si las páginas se ven mal)", "zaznamki": "Marcadores", "zgodovina": "Historial", "uvozi": "Importar de otro navegador …",
           "uvoz_zaznamki": "Marcadores añadidos: {n} (de: {od}).", "uvoz_brez": "No se encontró otro navegador con datos.",
           "uvoz_zavihki": "Abrir {n} pestañas de {ime}", "zapri": "Cerrar", "prazno": "Sin resultados."},
    "fr": {"strojno": "Accélération matérielle (désactivez-la si les pages s'affichent mal)", "zaznamki": "Favoris", "zgodovina": "Historique", "uvozi": "Importer d'un autre navigateur …",
           "uvoz_zaznamki": "Favoris ajoutés : {n} (de : {od}).", "uvoz_brez": "Aucun autre navigateur avec des données.",
           "uvoz_zavihki": "Ouvrir {n} onglets de {ime}", "zapri": "Fermer", "prazno": "Aucun résultat."},
    "it": {"strojno": "Accelerazione hardware (disattivala se le pagine si vedono male)", "zaznamki": "Segnalibri", "zgodovina": "Cronologia", "uvozi": "Importa da un altro browser …",
           "uvoz_zaznamki": "Segnalibri aggiunti: {n} (da: {od}).", "uvoz_brez": "Nessun altro browser con dati trovato.",
           "uvoz_zavihki": "Apri {n} schede da {ime}", "zapri": "Chiudi", "prazno": "Nessun risultato."},
}.items():
    BESEDILA.setdefault(_j, {}).update(_b)


for _j, _b in {'sl': {'predpomnilnik': 'Upravitelj predpomnilnika', 'pp_disk': 'Predpomnilnik na disku: {mb} MB', 'pp_pocisti': 'Počisti predpomnilnik (prijave ostanejo)', 'pp_strani': 'Shranjeni podatki strani', 'pp_odstrani': 'Odstrani', 'pp_meja': 'Samodejno počisti predpomnilnik nad {mb} MB', 'pp_iskanje': 'Išči stran …', 'pp_vrste': 'piškotki, shramba, predpomnilnik'}, 'en': {'predpomnilnik': 'Cache manager', 'pp_disk': 'Disk cache: {mb} MB', 'pp_pocisti': 'Clear cache (keeps sign-ins)', 'pp_strani': 'Stored site data', 'pp_odstrani': 'Remove', 'pp_meja': 'Automatically clear cache above {mb} MB', 'pp_iskanje': 'Search site …', 'pp_vrste': 'cookies, storage, cache'}, 'de': {'predpomnilnik': 'Cache-Verwaltung', 'pp_disk': 'Festplatten-Cache: {mb} MB', 'pp_pocisti': 'Cache leeren (Anmeldungen bleiben)', 'pp_strani': 'Gespeicherte Website-Daten', 'pp_odstrani': 'Entfernen', 'pp_meja': 'Cache über {mb} MB automatisch leeren', 'pp_iskanje': 'Website suchen …', 'pp_vrste': 'Cookies, Speicher, Cache'}, 'es': {'predpomnilnik': 'Gestor de caché', 'pp_disk': 'Caché en disco: {mb} MB', 'pp_pocisti': 'Vaciar caché (se mantienen las sesiones)', 'pp_strani': 'Datos guardados de sitios', 'pp_odstrani': 'Eliminar', 'pp_meja': 'Vaciar la caché automáticamente por encima de {mb} MB', 'pp_iskanje': 'Buscar sitio …', 'pp_vrste': 'cookies, almacenamiento, caché'}, 'fr': {'predpomnilnik': 'Gestionnaire de cache', 'pp_disk': 'Cache disque : {mb} Mo', 'pp_pocisti': 'Vider le cache (les connexions restent)', 'pp_strani': 'Données de sites enregistrées', 'pp_odstrani': 'Supprimer', 'pp_meja': 'Vider automatiquement le cache au-delà de {mb} Mo', 'pp_iskanje': 'Rechercher un site …', 'pp_vrste': 'cookies, stockage, cache'}, 'it': {'predpomnilnik': 'Gestione cache', 'pp_disk': 'Cache su disco: {mb} MB', 'pp_pocisti': 'Svuota cache (gli accessi restano)', 'pp_strani': 'Dati dei siti salvati', 'pp_odstrani': 'Rimuovi', 'pp_meja': 'Svuota automaticamente la cache oltre {mb} MB', 'pp_iskanje': 'Cerca sito …', 'pp_vrste': 'cookie, archiviazione, cache'}}.items():
    BESEDILA.setdefault(_j, {}).update(_b)



def velikost_mape_mb(pot: str) -> int:
    """Velikost mape v MiB (datoteke, brez sledenja povezavam)."""
    skupaj = 0
    for koren, _mape, datoteke in os.walk(pot):
        for ime in datoteke:
            try:
                skupaj += os.lstat(os.path.join(koren, ime)).st_size
            except OSError:
                pass
    return skupaj // (1024 * 1024)


def politika_pospesevanja(WebKit2, nastavitev):
    """Strojno pospesevanje je privzeto vklopljeno (ALWAYS); uporabnik ga lahko izklopi ("never").
    "on_demand" je v WebKitGTK 2.4x opuscen - obravnavamo ga kot vklopljeno."""
    return WebKit2.HardwareAccelerationPolicy.NEVER if nastavitev == "never" else WebKit2.HardwareAccelerationPolicy.ALWAYS


def blizjica(tipka: str, ctrl: bool = False, shift: bool = False, alt: bool = False) -> str | None:
    """Bliznjice kot v obicajnih brskalnikih (Chrome, Firefox, Opera): ime dejanja ali None."""
    t = (tipka or "").lower()
    if ctrl and not alt:
        if t == "t":
            return "obnovi-zaprt" if shift else "nov"
        if t == "w" or t == "f4":
            return "zapri"
        if t in ("tab", "iso_left_tab"):
            return "prejsnji" if shift or t == "iso_left_tab" else "naslednji"
        if t in ("page_down", "next"):
            return "naslednji"
        if t in ("page_up", "prior"):
            return "prejsnji"
        if t in ("l", "k", "e") and not shift:
            return "naslov"
        if t == "r" or t == "f5":
            return "osvezi-brez" if shift or t == "f5" else "osvezi"
        if t == "f" and not shift:
            return "najdi"
        if t == "d" and not shift:
            return "zaznamek"
        if t == "h" and not shift:
            return "zgodovina"
        if t == "o" and shift:
            return "zaznamki"
        if t in ("plus", "equal", "kp_add"):
            return "povecaj"
        if t in ("minus", "kp_subtract"):
            return "pomanjsaj"
        if t in ("0", "kp_0"):
            return "povecava-0"
        if t in ("1", "2", "3", "4", "5", "6", "7", "8") and not shift:
            return "zavihek-" + t
        if t == "9" and not shift:
            return "zavihek-zadnji"
        return None
    if alt and not ctrl:
        if t == "left":
            return "nazaj"
        if t == "right":
            return "naprej"
        if t == "home":
            return "domov"
        if t == "d":
            return "naslov"
        return None
    if not ctrl and not alt:
        if t == "f5":
            return "osvezi"
        if t == "f6":
            return "naslov"
        if t == "f3":
            return "najdi"
    return None


def stran_procesa_koncana(naslov: str, besedilo: str, gumb: str, uri: str) -> str:
    """Preprosta stran (brez skript strani): razlaga in gumb, ki stran nalozi znova."""
    e = _escape_html
    return ("<!doctype html><meta charset=utf-8><meta name=color-scheme content='light dark'>"
            "<body style='font:16px system-ui,sans-serif;max-width:36em;margin:15vh auto;padding:0 1em;line-height:1.5'>"
            f"<h1 style='font-size:1.4em'>{e(naslov)}</h1><p>{e(besedilo)}</p>"
            f"<p><a href=\"{e(uri, quote=True)}\" style='display:inline-block;padding:.5em 1.2em;border-radius:6px;"
            f"background:#2a6df4;color:#fff;text-decoration:none'>{e(gumb)}</a></p></body>")


def besedila(jezik: str) -> dict:
    """Besedila razdelka Splet; neznani jezik varno pade na anglescino."""
    return BESEDILA.get(str(jezik or "")[:2].lower(), BESEDILA["en"])


def razcleni_sporocilo(vrednost) -> dict | None:
    """Sprejme samo dejanji zacetne strani in njune pricakovane argumente."""
    if isinstance(vrednost, str):
        try:
            vrednost = json.loads(vrednost)
        except (TypeError, ValueError):
            return None
    if not isinstance(vrednost, dict):
        return None
    dejanje = vrednost.get("action")
    if dejanje == "navigate":
        naslov = normalize_web_url(str(vrednost.get("url") or ""))
        return {"action": dejanje, "url": naslov} if naslov else None
    if dejanje == "open_sidebar" and vrednost.get("service") == "add_portal":
        return {"action": dejanje, "service": "add_portal"}
    # Odstranitev bliznjice z zacetne strani (tudi vgrajene) in obnova privzetih: nic ni vsiljeno.
    if dejanje == "remove_portal":
        naslov = normalize_web_url(str(vrednost.get("url") or ""))
        return {"action": dejanje, "url": naslov} if naslov else None
    if dejanje == "reset_portals":
        return {"action": dejanje}
    # increment_ads/increment_threats ne gresta vec skozi glavni rokovalnik (stran bi napihnila stevec):
    # steje jih samo kozmeticna skripta v locenem svetu prek adblock.preveri_stevec (glej _stevec).
    return None


def kljuc_bliznjice(naslov: str) -> str:
    """Kljuc bliznjice (enak kot v ui/splet.js): naslov brez sheme, www. in koncne posevnice, z malimi crkami."""
    import re
    return re.sub(r"^https?://(www\.)?", "", str(naslov or "").strip(), flags=re.I).rstrip("/").lower()


def je_domaca_stran(naslov: str, koren: str) -> bool:
    try:
        return os.path.realpath(urllib.parse.unquote(urllib.parse.urlparse(naslov).path)) == \
            os.path.realpath(os.path.join(koren, "ui", "splet.html"))
    except Exception:
        return False


class VdelaniSplet:
    """GTK gradnik z zavihki; namenoma ni okno in zato ne more zapustiti Safeer OS."""

    def __init__(self, Gtk, Gdk, Gio, GLib, WebKit2, koren: str, jezik, stanje_povezave,
                 odpri_zapisek=None, stars=None, stremio_dodatek=None):
        self.Gtk, self.Gdk, self.Gio, self.GLib, self.WebKit2 = Gtk, Gdk, Gio, GLib, WebKit2
        self.koren, self.jezik = koren, jezik
        self.stanje_povezave, self.odpri_zapisek = stanje_povezave, odpri_zapisek
        self.stars = stars
        #: Gumb »Install« dodatka Stremio (povezava stremio://...): Safeer Player pokaze dodatek in vprasa (kot Android).
        self.stremio_dodatek = stremio_dodatek
        self.config = ConfigManager()
        #: »Vsili temno« (core/splet_temno.py): skripta Dark Reader vsakega pogleda, da jo ob spremembi zamenjamo.
        self._temno_skripte = weakref.WeakKeyDictionary()
        try:
            Gtk.Settings.get_default().connect("notify::gtk-application-prefer-dark-theme", lambda *_: self._temno_osvezi())
        except Exception:
            pass
        self.zavihki, self.aktivni, self._stevec = [], None, 0
        self.filter, self.filter_store, self.filter_agent = None, None, None
        self.prenosi = []
        self._threat_service = None
        self._ustvari_kontekst()
        self._zgradi()
        self._zazeni_zascito()
        self.nov_zavihek()
        self.GLib.timeout_add_seconds(5, self.osvezi_povezavo)


    def _okno_za_dialog(self):
        """Okno, nad katerim se odpre dialog: tisto, v katerem je Splet ZDAJ (na delovni povrsini je to svoje okno
        »Splet«, ne okno delovne povrsine, ki je bilo podano ob ustvarjanju). Modalni dialog nad napacnim oknom je ostal
        skrit ZA celozaslonskim Spletom in zaklenil vnos vanj - Splet je bil videti zamrznjen (lastnik, 12. 10. 2026)."""
        try:
            vrh = self.gradnik.get_toplevel()
            if isinstance(vrh, self.Gtk.Window) and vrh.get_visible():
                return vrh
        except Exception:
            pass
        return self.stars
    def _t(self, kljuc: str, **vrednosti) -> str:
        niz = besedila(self.jezik()).get(kljuc, kljuc)
        return niz.format(**vrednosti) if vrednosti else niz

    def _ustvari_kontekst(self) -> None:
        WebKit2 = self.WebKit2
        mapa = os.path.join(self.config.config_dir, "web-data")
        os.makedirs(mapa, exist_ok=True)
        try:
            upravitelj = WebKit2.WebsiteDataManager(
                base_data_directory=mapa, base_cache_directory=os.path.join(mapa, "cache"),
                disk_cache_directory=os.path.join(mapa, "cache"),
                indexeddb_directory=os.path.join(mapa, "indexeddb"),
                local_storage_directory=os.path.join(mapa, "localstorage"),
                websql_directory=os.path.join(mapa, "websql"))
            from core import pomnilnik
            self.kontekst = pomnilnik.kontekst(WebKit2, 350, website_data_manager=upravitelj,
                                               ubij_mb=pomnilnik.meja_strani_mb())
            self.kontekst.set_sandbox_enabled(True)
            piskotki = upravitelj.get_cookie_manager()
            piskotki.set_persistent_storage(os.path.join(self.config.config_dir, "cookies.sqlite"),
                                            WebKit2.CookiePersistentStorage.SQLITE)
            piskotki.set_accept_policy(WebKit2.CookieAcceptPolicy.NO_THIRD_PARTY)
        except Exception as napaka:
            print("[Safeer OS Splet] shramba:", napaka)
            self.kontekst = WebKit2.WebContext.get_default()
            self.kontekst.set_sandbox_enabled(True)
        try:
            self.kontekst.set_cache_model(WebKit2.CacheModel.WEB_BROWSER)
        except Exception:
            pass
        self._nastavi_omrezje()
        self.kontekst.connect("download-started", self._prenos_zacet)
        self._omeji_predpomnilnik()

    def _nastavi_omrezje(self) -> None:
        W = self.WebKit2
        izjeme = ["localhost", "127.0.0.0/8", "::1", "10.0.0.0/8", "192.168.0.0/16", "172.16.0.0/12", ".local"]
        try:
            nacin = self.config.get("secure_proxy_mode", "disabled")
            if nacin == "custom" and self.config.get("secure_proxy_url", "").strip():
                p = W.NetworkProxySettings.new(self.config.get("secure_proxy_url").strip(), izjeme)
                self.kontekst.set_network_proxy_settings(W.NetworkProxyMode.CUSTOM, p)
                return
            if self.config.get("doh_enabled", True) and self.config.get("doh_provider", "cloudflare") != "disabled":
                doh = get_doh_proxy(provider=self.config.get("doh_provider", "cloudflare"),
                                    custom_url=self.config.get("custom_doh_url", "https://1.1.1.1/dns-query"), enabled=True,
                                    lokalno=bool(self.config.get("doh_lokalno_omrezje", False)))
                if doh and doh.actual_port > 0:
                    p = W.NetworkProxySettings.new("http://127.0.0.1:%d" % doh.actual_port, izjeme)
                    self.kontekst.set_network_proxy_settings(W.NetworkProxyMode.CUSTOM, p)
                    return
            self.kontekst.set_network_proxy_settings(W.NetworkProxyMode.DEFAULT, None)
        except Exception as napaka:
            print("[Safeer OS Splet] DoH/proxy:", napaka)

    def _zgradi(self) -> None:
        Gtk = self.Gtk
        self.gradnik = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.gradnik.set_name("safeer-splet")
        self.vrstica_zavihkov = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.vrstica_zavihkov.set_name("splet-zavihki")
        self.skatla_zavihkov = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.vrstica_zavihkov.pack_start(self.skatla_zavihkov, False, False, 10)
        self.nov_gumb = self._gumb("+", lambda *_: self.nov_zavihek(), "new-tab")
        self.vrstica_zavihkov.pack_start(self.nov_gumb, False, False, 0)
        self.povezava = Gtk.Label(label="")
        self.povezava.set_name("splet-povezava")
        self.vrstica_zavihkov.pack_end(self.povezava, False, False, 18)
        self.gradnik.pack_start(self.vrstica_zavihkov, False, False, 0)

        orodja = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        orodja.set_name("splet-orodja")
        self.nazaj = self._gumb("←", lambda *_: self.trenutni() and self.trenutni().go_back(), "nav")
        self.naprej = self._gumb("→", lambda *_: self.trenutni() and self.trenutni().go_forward(), "nav")
        self.osvezi = self._gumb("↻", lambda *_: self.trenutni() and self.trenutni().reload(), "nav")
        self.domov = self._gumb("⌂", lambda *_: self.odpri_domov(), "nav")
        for g, namig in ((self.nazaj, "nazaj"), (self.naprej, "naprej"), (self.osvezi, "osvezi"), (self.domov, "domov")):
            g.set_tooltip_text(self._t(namig)); orodja.pack_start(g, False, False, 0)
        naslov = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        naslov.set_name("splet-naslov")
        self.kljucavnica = (Gtk.Image.new_from_icon_name("channel-secure-symbolic", Gtk.IconSize.MENU)
                            if Gtk.IconTheme.get_default().has_icon("channel-secure-symbolic") else Gtk.Label(label="🔒"))
        self.vnos = Gtk.Entry()
        self.vnos.set_name("splet-vnos")
        self.vnos.set_placeholder_text(self._t("naslov"))
        self.vnos.connect("activate", self._vnesi_naslov)
        self.vnos.connect("key-press-event", lambda _v, e: self.tipka(e))
        self.zvezdica = self._gumb("☆", lambda *_: self.dodaj_trenutno(), "address-action")
        naslov.pack_start(self.kljucavnica, False, False, 8)
        naslov.pack_start(self.vnos, True, True, 0)
        naslov.pack_end(self.zvezdica, False, False, 5)
        orodja.pack_start(naslov, True, True, 4)
        self.scit = self._gumb("♢", lambda *_: None, "nav")
        self.scit.set_tooltip_text(self._t("scit"))
        orodja.pack_start(self.scit, False, False, 0)
        meni = Gtk.MenuButton()
        meni.set_image(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.LARGE_TOOLBAR))
        meni.set_name("splet-meni")
        meni.set_tooltip_text(self._t("meni"))
        meni.set_popup(self._meni())
        orodja.pack_end(meni, False, False, 0)
        self.gradnik.pack_start(orodja, False, False, 0)

        self.najdi_vrstica = Gtk.SearchBar()
        self.najdi_vnos = Gtk.SearchEntry()
        self.najdi_vnos.set_placeholder_text(self._t("isci"))
        self.najdi_vnos.connect("search-changed", self._najdi)
        self.najdi_vrstica.add(self.najdi_vnos)
        self.gradnik.pack_start(self.najdi_vrstica, False, False, 0)
        self.sklad = Gtk.Stack()
        self.sklad.set_transition_type(Gtk.StackTransitionType.NONE)
        self.gradnik.pack_start(self.sklad, True, True, 0)
        self._css()
        self.osvezi_povezavo()

    def _css(self) -> None:
        # Barve namizja Safeer OS (delovna.css): ozadje #0b1424, kartice #101a2b/#16233a, poudarek #8ac7ff - Splet je del
        # celotne teme (lastnik, 11. 10. 2026), ne zelen kot samostojni Safeer Browser.
        css = b"""
        #safeer-splet { background: #0b1424; color: #eaf2ff; }
        #splet-zavihki { background: #0b1424; min-height: 52px; }
        .splet-tab { background: #101a2b; color: #c3d4ea; border: 1px solid rgba(211,229,255,.14);
          border-bottom: 0; border-radius: 12px 12px 0 0; padding: 8px 12px; margin-top: 8px; min-width: 180px; }
        .splet-tab-aktiven { background: #16233a; color: #eaf2ff; border-color: rgba(138,199,255,.55);
          border-top: 2px solid #8ac7ff; }
        .splet-tab button, .new-tab, .nav, .address-action, #splet-meni { background: transparent; color: #eaf2ff;
          border: 0; box-shadow: none; text-shadow: none; }
        .new-tab { font-size: 24px; padding: 5px 10px; }
        #splet-povezava { color: #e3ecf7; border: 1px solid rgba(138,199,255,.55); border-radius: 14px;
          padding: 5px 14px; margin-top: 8px; margin-bottom: 8px; background: rgba(138,199,255,.08); }
        #splet-orodja { background: #0b1424; padding: 6px 14px 8px; }
        .nav { font-size: 20px; padding: 6px 9px; border-radius: 10px; color: #e2eaf6; }
        .nav image, .address-action image, #splet-meni image { color: #e2eaf6; }
        .nav:hover, .address-action:hover, #splet-meni:hover { background: rgba(104,168,229,.20); }
        #splet-naslov { background: #101a2b; border: 2px solid rgba(138,199,255,.55); border-radius: 20px; padding: 2px 6px; }
        #splet-vnos { background: transparent; color: #eaf2ff; border: 0; box-shadow: none; font-size: 16px; padding: 10px 4px; }
        #splet-vnos selection { background: #2b5b8c; }
        menu { background: #101a2b; color: #eaf2ff; border: 1px solid rgba(211,229,255,.23); }
        menuitem:hover { background: rgba(104,168,229,.20); }
        """
        ponudnik = self.Gtk.CssProvider()
        ponudnik.load_from_data(css)
        self.Gtk.StyleContext.add_provider_for_screen(self.Gdk.Screen.get_default(), ponudnik,
                                                       self.Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._css_ponudnik = ponudnik

    def _gumb(self, napis, dejanje, razred):
        # Sistemske simbolne ikone (enake oblike kot na Windows), sicer besedilo.
        ikone = {"←": "go-previous-symbolic", "→": "go-next-symbolic", "↻": "view-refresh-symbolic",
                 "⌂": "go-home-symbolic", "☆": "non-starred-symbolic", "♢": "security-high-symbolic",
                 "+": "list-add-symbolic"}
        if napis in ikone and self.Gtk.IconTheme.get_default().has_icon(ikone[napis]):
            g = self.Gtk.Button()
            g.set_image(self.Gtk.Image.new_from_icon_name(ikone[napis], self.Gtk.IconSize.LARGE_TOOLBAR))
            g.set_always_show_image(True)
        else:
            g = self.Gtk.Button(label=napis)
        g.set_relief(self.Gtk.ReliefStyle.NONE)
        g.get_style_context().add_class(razred)
        g.connect("clicked", dejanje)
        return g

    # ---------------------------------------------------------------- vsili temno
    def _temno_nacin(self) -> str:
        n = str(self.config.get("temno_nacin", splet_temno.PRIVZETO) or splet_temno.PRIVZETO)
        return n if n in splet_temno.NACINI else splet_temno.PRIVZETO

    def _namizje_temno(self) -> bool:
        try:
            return bool(self.Gtk.Settings.get_default().props.gtk_application_prefer_dark_theme)
        except Exception:
            return False

    def _temno_izjeme(self) -> list:
        izjeme = self.config.get("temno_izjeme", []) or []
        return [str(x) for x in izjeme] if isinstance(izjeme, list) else []

    def _temno_namesti(self, upravitelj):
        try:
            return splet_temno.namesti(self.WebKit2, upravitelj, os.path.join(self.koren, "core"), self._temno_nacin(),
                                       self._namizje_temno(), self._temno_izjeme())
        except Exception as napaka:
            print("[Safeer OS Splet] vsili temno:", napaka)
            return None

    def _temno_osvezi(self, znova_nalozi=None) -> None:
        """Skripto zamenja v vseh zavihkih; znova_nalozi: pogled, ki ga naj takoj osvezi (sprememba se vidi)."""
        for z in list(getattr(self, "zavihki", []) or []):
            pogled = z.get("pogled")
            if pogled is None:
                continue
            upravitelj = pogled.get_user_content_manager()
            splet_temno.odstrani(upravitelj, self._temno_skripte.get(pogled))
            self._temno_skripte[pogled] = self._temno_namesti(upravitelj)
        if znova_nalozi is not None:
            try:
                znova_nalozi.reload()
            except Exception:
                pass

    def _temno_preklopi_stran(self, *_):
        p = self.trenutni()
        g = splet_temno.gostitelj(p.get_uri() if p else "")
        if not g:
            return
        izjeme = self._temno_izjeme()
        izjeme = [x for x in izjeme if x != g] if g in izjeme else izjeme + [g]
        self.config.set("temno_izjeme", izjeme)
        self._temno_osvezi(znova_nalozi=p)

    def _meni(self):
        meni = self.Gtk.Menu()
        vnosi = [
            (self._t("nov"), lambda *_: self.nov_zavihek()),
            (self._t("zaznamki"), lambda *_: self._seznam("zaznamki")),
            (self._t("zgodovina"), lambda *_: self._seznam("zgodovina")),
            (self._t("uvozi"), self._uvozi),
            (self._t("predpomnilnik"), lambda *_: self._predpomnilnik()),
            (self._t("prenosi"), self._pokazi_prenose),
            (self._t("najdi"), lambda *_: self._pokazi_najdi()),
            (self._t("povecaj"), lambda *_: self._povecava(.1)),
            (self._t("pomanjsaj"), lambda *_: self._povecava(-.1)),
            (self._t("nastavitve"), self._nastavitve),
            (self._t("zapisek"), self._v_zapisek),
        ]
        p = self.trenutni()
        g = splet_temno.gostitelj(p.get_uri() if p else "")
        if g and splet_temno.dejaven(self._temno_nacin(), self._namizje_temno()):
            jezik = str(self.jezik() if callable(self.jezik) else self.jezik or "sl")
            kljuc = "na_strani_vklopi" if g in self._temno_izjeme() else "na_strani_izklopi"
            vnosi.insert(-2, (splet_temno.besedilo(jezik, kljuc), self._temno_preklopi_stran))
        for napis, dejanje in vnosi:
            v = self.Gtk.MenuItem(label=napis); v.connect("activate", dejanje); meni.append(v)
        meni.show_all()
        return meni

    def _zazeni_zascito(self) -> None:
        try:
            from core.threat_intel import default_data_dir, skupna
            self._threat_service = skupna(default_data_dir("safeer-mint"))   # ista kot v Scitu
            adblock.register_threat_matcher(self._threat_service.match)
        except Exception as napaka:
            print("[Safeer OS Splet] vir grozenj:", napaka)
        if not self.config.get("easylist_enabled", True):
            return
        try:
            from core.filter_lists import FilterListAgent
            from core.threat_intel import default_data_dir
            mapa = default_data_dir("safeer-mint").parent / "filter-lists"
            self._filter_mapa = mapa / "compiled"
            # Seznam, ki je ze preveden (oznaka list.sha256 = sha shranjenega seznama), WebKit nalozi iz shrambe; Python
            # ga ne bere in ne pretvarja (meritev 11. 10. 2026: pretvorba je procesu pustila ~170 MiB).
            oznaka = self._filter_mapa / "list.sha256"
            preveden = ""
            try:
                preveden = oznaka.read_text("utf-8").strip()
            except OSError:
                pass
            self.filter_agent = FilterListAgent(mapa, on_rules=lambda p, v: self.GLib.idle_add(self._namesti_filter, p, v),
                                                 never_block_domains=adblock.real_bank_domains())
            from core.webkit_filters import VERZIJA_PRETVORNIKA
            if preveden and preveden == "%s:%s" % (self.filter_agent.saved_sha256(), VERZIJA_PRETVORNIKA):
                self.filter_agent.skip_saved = True
                self._nalozi_preveden_filter()
            self.filter_agent.start()
        except Exception as napaka:
            print("[Safeer OS Splet] EasyList:", napaka)

    def _nalozi_preveden_filter(self) -> None:
        def nalozen(shramba, rezultat, *_a):
            try:
                self.filter = shramba.load_finish(rezultat)
                for z in self.zavihki:
                    self._uporabi_filter(z["pogled"])
            except Exception as napaka:
                # Shramba je pokvarjena ali je ni: naslednjic seznam pretvorimo znova.
                print("[Safeer OS Splet] preveden filter:", napaka)
                try:
                    (self._filter_mapa / "list.sha256").unlink()
                except OSError:
                    pass
        try:
            self._filter_mapa.mkdir(parents=True, exist_ok=True)
            if self.filter_store is None:
                self.filter_store = self.WebKit2.UserContentFilterStore.new(str(self._filter_mapa))
            self.filter_store.load(FILTER_ID, None, nalozen)
        except Exception as napaka:
            print("[Safeer OS Splet] preveden filter:", napaka)

    def _namesti_filter(self, pravila, _vir):
        try:
            self._filter_mapa.mkdir(parents=True, exist_ok=True)
            if self.filter_store is None:
                self.filter_store = self.WebKit2.UserContentFilterStore.new(str(self._filter_mapa))
            sha = hashlib.sha256(pravila.encode("utf-8")).hexdigest()
            podatki = self.GLib.Bytes.new(pravila.encode("utf-8"))
            self.filter_store.save(FILTER_ID, podatki, None, self._filter_koncan, sha)
        except Exception as napaka:
            print("[Safeer OS Splet] filter:", napaka)
        return False

    def _filter_koncan(self, shramba, rezultat, sha):
        try:
            self.filter = shramba.save_finish(rezultat)
            (self._filter_mapa / "compiled.sha256").write_text(sha, "utf-8")
            from core.filter_lists import pocisti_zacasne_filtre
            pocisti_zacasne_filtre(str(self._filter_mapa))
            if self.filter_agent is not None and self.filter_agent.list_sha256:
                from core.webkit_filters import VERZIJA_PRETVORNIKA
                (self._filter_mapa / "list.sha256").write_text("%s:%s" % (self.filter_agent.list_sha256, VERZIJA_PRETVORNIKA), "utf-8")
            for z in self.zavihki:
                self._uporabi_filter(z["pogled"])
        except Exception as napaka:
            print("[Safeer OS Splet] prevajanje filtra:", napaka)

    def _uporabi_filter(self, pogled):
        if self.filter is not None:
            try:
                pogled.get_user_content_manager().remove_filter_by_id(FILTER_ID)
                pogled.get_user_content_manager().add_filter(self.filter)
            except Exception:
                pass

    def _skripta(self, upravitelj, koda, cas=None, dovoljeni=None, izloceni=None):
        if not koda:
            return
        upravitelj.add_script(self.WebKit2.UserScript(
            koda, self.WebKit2.UserContentInjectedFrames.ALL_FRAMES,
            cas or self.WebKit2.UserScriptInjectionTime.START, dovoljeni, izloceni))

    def _nov_pogled(self):
        W = self.WebKit2
        pogled = W.WebView.new_with_context(self.kontekst)
        # Padec spletnega procesa (sesutje strani, pomanjkanje pomnilnika): zavihek se nalozi znova, kot v brskalniku.
        os_stabilnost.obnovi_ob_padcu(W, self.GLib, pogled, "safeer-os", "splet", ob_odpovedi=self._proces_koncan)
        upravitelj = pogled.get_user_content_manager()
        upravitelj.register_script_message_handler("safeer")
        # Sibka referenca (glej drm.prikljuci): sicer zaprt zavihek nikoli ne sprosti svojega WebView.
        ref = weakref.ref(pogled)
        upravitelj.connect("script-message-received::safeer",
                           lambda _u, r: ref() is not None and self._sporocilo(ref(), r))
        # Stevec scita v locenem svetu: stran v glavnem svetu tega rokovalnika ne doseze.
        upravitelj.register_script_message_handler_in_world(adblock.STEVEC_MOST, adblock.STEVEC_SVET)
        upravitelj.connect("script-message-received::" + adblock.STEVEC_MOST, lambda _u, r: self._stevec(r))
        odlozisce_varuh.dodaj(W, upravitelj)   # tudi na prijavnih straneh: nicesar ne spreminja, le varuje odlozisce
        # Widevine (Netflix, Disney+ ...): stran se odpre v namescenem brskalniku z Widevine (core/drm.py).
        if getattr(self, "_drm", None) is None:
            self._drm = drm.Preusmeritev()
        drm.prikljuci(W, pogled, self._drm, lambda: str(self.jezik() if callable(self.jezik) else self.jezik or "sl"))
        izvzemi = adblock.AUTH_SCRIPT_EXCLUSIONS
        if self.config.get("gpc_dnt_enabled", True): self._skripta(upravitelj, adblock.GPC_AND_DNT_SCRIPT, izloceni=izvzemi)
        self._skripta(upravitelj, adblock.YOUTUBE_ADBLOCK_SCRIPT, dovoljeni=["*://*.youtube.com/*", "*://youtube.com/*"], izloceni=izvzemi)
        self._skripta(upravitelj, adblock.YOUTUBE_KEEP_WATCHING_SCRIPT, dovoljeni=["*://*.youtube.com/*", "*://youtube.com/*"], izloceni=izvzemi)
        if self.config.get("adguard_protection_enabled", True): self._skripta(upravitelj, adblock.ADGUARD_PROTECTION_SCRIPT, izloceni=izvzemi)
        # Kozmeticna skripta (cist DOM) v locenem svetu: lahko skrije oglase in posilja stevec, stran je ne vidi.
        upravitelj.add_script(W.UserScript.new_for_world(
            adblock.GENERIC_COSMETIC_SCRIPT, W.UserContentInjectedFrames.ALL_FRAMES,
            W.UserScriptInjectionTime.END, adblock.STEVEC_SVET, None, izvzemi))
        self._skripta(upravitelj, adblock.ANTI_CLICKJACKING_SCRIPT, W.UserScriptInjectionTime.END, izloceni=izvzemi + ["file://*"])
        self._skripta(upravitelj, adblock.TAB_THROTTLER_SCRIPT, izloceni=izvzemi)
        self._temno_skripte[pogled] = self._temno_namesti(upravitelj)
        nastavitve = pogled.get_settings()
        nastavitve.set_hardware_acceleration_policy(politika_pospesevanja(W, self.config.get("hardware_acceleration", "on_demand")))
        nastavitve.set_enable_javascript(True)
        nastavitve.set_enable_javascript_markup(True)
        nastavitve.set_javascript_can_open_windows_automatically(False)
        nastavitve.set_enable_html5_local_storage(True)
        nastavitve.set_enable_html5_database(False)
        try:
            nastavitve.set_enable_hyperlink_auditing(False); nastavitve.set_enable_dns_prefetching(False)
            nastavitve.set_enable_page_cache(False); nastavitve.set_enable_encrypted_media(True)
        except Exception:
            pass
        # Temno pod našo začetno stranjo, belo pod spletom - belo mora biti nastavljeno, preden dokument strani nastane.
        ozadje_strani.prikljuci(self.Gdk, W, pogled, os.path.join(self.koren, "ui"), TEMNO_OZADJE)
        pogled.connect("decide-policy", self._politika)
        pogled.connect("key-press-event", lambda _p, e: self.tipka(e))
        pogled.connect("button-press-event", self._miska)
        pogled.connect("create", lambda p, a: self._novo_okno(p, a))
        pogled.connect("load-changed", self._nalozen)
        pogled.connect("notify::title", self._naslov_spremenjen)
        pogled.connect("notify::uri", self._uri_spremenjen)
        pogled.connect("permission-request", self._dovoljenje)
        self._uporabi_filter(pogled)
        return pogled

    def _proces_koncan(self, pogled, _razlog: str = "") -> None:
        """os_stabilnost strani ne nalozi vec znova (ponovno prekoracen pomnilnik, prevec padcev): namesto bele
        strani razlaga z gumbom za ponovno nalaganje."""
        uri = pogled.get_uri() or ""
        if not uri.startswith(("http://", "https://")):
            return
        pogled.load_alternate_html(stran_procesa_koncana(self._t("proces_naslov"), self._t("proces_besedilo"),
                                                         self._t("proces_znova"), uri), uri, None)

    def nov_zavihek(self, naslov: str = ""):
        self._stevec += 1
        pogled = self._nov_pogled()
        vrstica = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=6)
        vrstica.get_style_context().add_class("splet-tab")
        ikona = self.Gtk.Label(label="🌐")
        naslov_lbl = self.Gtk.Label(label=self._t("nov")); naslov_lbl.set_ellipsize(3); naslov_lbl.set_xalign(0)
        zapri = self._gumb("×", lambda *_: self.zapri_zavihek(pogled), "tab-close")
        vrstica.pack_start(ikona, False, False, 0); vrstica.pack_start(naslov_lbl, True, True, 0); vrstica.pack_end(zapri, False, False, 0)
        dogodek = self.Gtk.EventBox(); dogodek.add(vrstica); dogodek.connect("button-press-event", lambda _w, _e: (self.izberi(pogled), True)[1])
        self.skatla_zavihkov.pack_start(dogodek, False, False, 0)
        self.sklad.add_named(pogled, "splet-%d" % self._stevec)
        zavihek = {"pogled": pogled, "dogodek": dogodek, "vrstica": vrstica, "naslov": naslov_lbl, "ikona": ikona}
        self.zavihki.append(zavihek)
        dogodek.show_all(); pogled.show_all(); self.izberi(pogled)
        self.odpri(naslov, pogled)
        return pogled

    def zapri_zavihek(self, pogled):
        if len(self.zavihki) == 1:
            self.odpri_domov(); return
        z = next((x for x in self.zavihki if x["pogled"] is pogled), None)
        if z is None: return
        self._zapomni_zaprt(pogled)
        indeks = self.zavihki.index(z); self.zavihki.remove(z)
        self.skatla_zavihkov.remove(z["dogodek"]); self.sklad.remove(pogled); pogled.destroy()
        self.izberi(self.zavihki[max(0, indeks - 1)]["pogled"])

    def _zapomni_zaprt(self, pogled) -> None:
        """Naslov zaprtega zavihka za Ctrl+Shift+T (najvec 20)."""
        try:
            naslov = pogled.get_uri() or ""
        except Exception:  # noqa: BLE001
            naslov = ""
        if naslov.startswith(("http://", "https://")):
            zaprti = getattr(self, "_zaprti", [])
            zaprti.append(naslov)
            self._zaprti = zaprti[-20:]

    def tipka(self, dogodek) -> bool:
        """Bliznjice brskalnika; vrne True, ce je tipka porabljena."""
        Gdk = self.Gdk
        stanje = dogodek.state
        dejanje = blizjica(Gdk.keyval_name(dogodek.keyval) or "", bool(stanje & Gdk.ModifierType.CONTROL_MASK),
                           bool(stanje & Gdk.ModifierType.SHIFT_MASK), bool(stanje & Gdk.ModifierType.MOD1_MASK))
        return self.izvedi(dejanje) if dejanje else False

    def izvedi(self, dejanje: str) -> bool:
        p = self.trenutni()
        if dejanje == "nov":
            self.nov_zavihek(); self.vnos.grab_focus()
        elif dejanje == "zapri":
            if p is not None:
                self.zapri_zavihek(p)
        elif dejanje == "obnovi-zaprt":
            zaprti = getattr(self, "_zaprti", [])
            if not zaprti:
                return True
            self.nov_zavihek(zaprti.pop())
        elif dejanje in ("naslednji", "prejsnji") or dejanje.startswith("zavihek-"):
            if not self.zavihki:
                return True
            if dejanje == "zavihek-zadnji":
                i = len(self.zavihki) - 1
            elif dejanje.startswith("zavihek-"):
                i = int(dejanje.rsplit("-", 1)[1]) - 1
                if i >= len(self.zavihki):
                    return True
            else:
                tren = next((k for k, z in enumerate(self.zavihki) if z["pogled"] is p), 0)
                i = (tren + (1 if dejanje == "naslednji" else -1)) % len(self.zavihki)
            self.izberi(self.zavihki[i]["pogled"])
        elif dejanje == "naslov":
            self.vnos.grab_focus(); self.vnos.select_region(0, -1)
        elif dejanje == "osvezi" and p is not None:
            p.reload()
        elif dejanje == "osvezi-brez" and p is not None:
            p.reload_bypass_cache()
        elif dejanje == "najdi":
            self._pokazi_najdi()
        elif dejanje == "zaznamek":
            self.dodaj_trenutno()
        elif dejanje in ("zgodovina", "zaznamki"):
            self._seznam(dejanje)
        elif dejanje == "povecaj":
            self._povecava(.1)
        elif dejanje == "pomanjsaj":
            self._povecava(-.1)
        elif dejanje == "povecava-0" and p is not None:
            p.set_zoom_level(1.0)
        elif dejanje == "nazaj" and p is not None:
            p.go_back()
        elif dejanje == "naprej" and p is not None:
            p.go_forward()
        elif dejanje == "domov":
            self.odpri_domov()
        else:
            return False
        return True

    def _seznam(self, kaj: str = "zaznamki") -> None:
        """Zaznamki (Ctrl+Shift+O) in zgodovina (Ctrl+H) z iskanjem; klik odpre stran v novem zavihku."""
        from core import zgodovina
        Gtk = self.Gtk
        d = Gtk.Dialog(title=self._t(kaj), transient_for=self._okno_za_dialog(), modal=True)
        d.set_default_size(720, 560)
        d.add_button(self._t("zapri"), Gtk.ResponseType.CLOSE)
        iskanje = Gtk.SearchEntry(); iskanje.set_margin_start(12); iskanje.set_margin_end(12)
        zvezki = Gtk.Notebook()
        seznami = {}
        for kljuc in ("zaznamki", "zgodovina"):
            okvir = Gtk.ScrolledWindow(); okvir.set_vexpand(True)
            sez = Gtk.ListBox(); sez.set_activate_on_single_click(True)
            sez.connect("row-activated", lambda _s, vrstica: (self.nov_zavihek(vrstica.naslov), d.destroy()))
            okvir.add(sez); zvezki.append_page(okvir, Gtk.Label(label=self._t(kljuc))); seznami[kljuc] = sez
        def napolni(*_):
            niz = iskanje.get_text()
            viri = {"zaznamki": [{"title": p.get("title", ""), "url": p.get("url", "")} for p in self.config.get_portals()],
                    "zgodovina": zgodovina.nalozi(os.path.join(self.config.config_dir, "history.json"))}
            for kljuc, sez in seznami.items():
                for v in sez.get_children():
                    v.destroy()
                zadetki = [z for z in zgodovina.isci(viri[kljuc], niz) if z.get("url")][:300]
                for z in zadetki:
                    vrstica = Gtk.ListBoxRow(); vrstica.naslov = z["url"]
                    skatla = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, margin=8)
                    a = Gtk.Label(label=z.get("title") or z["url"], xalign=0); a.set_ellipsize(3)
                    b = Gtk.Label(label=(z.get("time", "") + "  " + z["url"]).strip(), xalign=0); b.set_ellipsize(3)
                    b.get_style_context().add_class("dim-label")
                    skatla.pack_start(a, False, False, 0); skatla.pack_start(b, False, False, 0)
                    vrstica.add(skatla); sez.add(vrstica)
                if not zadetki:
                    sez.add(Gtk.Label(label=self._t("prazno"), margin=16))
                sez.show_all()
        iskanje.connect("search-changed", napolni)
        obmocje = d.get_content_area(); obmocje.set_spacing(8)
        obmocje.pack_start(iskanje, False, False, 6); obmocje.pack_start(zvezki, True, True, 0)
        napolni()
        d.show_all()
        zvezki.set_current_page(0 if kaj == "zaznamki" else 1)
        iskanje.grab_focus()
        d.connect("response", lambda *_: d.destroy())

    def _uvozi(self, *_):
        """Zaznamki in odprti zavihki iz drugih brskalnikov na tem racunalniku (samo branje njihovih datotek)."""
        from core import uvoz_zavihkov
        Gtk = self.Gtk
        try:
            from core.bookmarks_importer import auto_import_all_profiles
            zaznamki, viri = auto_import_all_profiles()
            dodanih, _ = self.config.import_bookmarks_items(zaznamki)
        except Exception as napaka:  # noqa: BLE001
            print("[Safeer OS Splet] uvoz zaznamkov:", napaka)
            dodanih, viri = 0, {}
        zavihki = uvoz_zavihkov.odprti_zavihki()
        d = Gtk.Dialog(title=self._t("uvozi").rstrip(" …"), transient_for=self._okno_za_dialog(), modal=True)
        d.add_button(self._t("zapri"), Gtk.ResponseType.CLOSE)
        obmocje = d.get_content_area(); obmocje.set_spacing(10); obmocje.set_margin_start(16); obmocje.set_margin_end(16)
        if viri or zavihki:
            obmocje.pack_start(Gtk.Label(label=self._t("uvoz_zaznamki", n=dodanih, od=", ".join(viri) or "-"),
                                         xalign=0, margin_top=12), False, False, 0)
        else:
            obmocje.pack_start(Gtk.Label(label=self._t("uvoz_brez"), margin=16), False, False, 0)
        for ime, naslovi in zavihki.items():
            gumb = Gtk.Button(label=self._t("uvoz_zavihki", n=len(naslovi), ime=ime))
            gumb.connect("clicked", lambda _g, n=naslovi: ([self.nov_zavihek(x) for x in n], d.destroy()))
            obmocje.pack_start(gumb, False, False, 0)
        d.connect("response", lambda *_: d.destroy())
        d.show_all()
        for z in self.zavihki:          # zacetna stran pokaze nove bliznjice
            if je_domaca_stran(z["pogled"].get_uri() or "", self.koren):
                self._poslji_stanje(z["pogled"], prenesi=False)

    def _mapa_predpomnilnika(self) -> str:
        return os.path.join(self.config.config_dir, "web-data", "cache")

    def _omeji_predpomnilnik(self) -> None:
        """Ob zagonu: predpomnilnik na disku nad mejo (privzeto 500 MB) se pocisti; prijave in shramba strani ostanejo."""
        meja = int(self.config.get("splet_predpomnilnik_meja_mb", 500) or 0)
        if meja <= 0:
            return
        def preveri():
            if velikost_mape_mb(self._mapa_predpomnilnika()) > meja:
                self.GLib.idle_add(lambda: (self._pocisti_predpomnilnik(), False)[1])
        import threading
        threading.Thread(target=preveri, daemon=True, name="splet-predpomnilnik").start()

    def _pocisti_predpomnilnik(self, ob_koncu=None) -> None:
        W = self.WebKit2
        try:
            self.kontekst.get_website_data_manager().clear(
                W.WebsiteDataTypes.DISK_CACHE | W.WebsiteDataTypes.MEMORY_CACHE, 0, None,
                (lambda *_: ob_koncu()) if ob_koncu else None, None)
        except Exception as napaka:  # noqa: BLE001
            print("[Safeer OS Splet] predpomnilnik:", napaka)

    def _predpomnilnik(self) -> None:
        """Upravitelj predpomnilnika: velikost, ciscenje predpomnilnika (prijave ostanejo), podatki po straneh, meja."""
        Gtk, W = self.Gtk, self.WebKit2
        upr = self.kontekst.get_website_data_manager()
        d = Gtk.Dialog(title=self._t("predpomnilnik"), transient_for=self._okno_za_dialog(), modal=True)
        d.set_default_size(640, 560)
        d.add_button(self._t("zapri"), Gtk.ResponseType.CLOSE)
        obmocje = d.get_content_area(); obmocje.set_spacing(8)
        for stran in ("set_margin_start", "set_margin_end", "set_margin_top"):
            getattr(obmocje, stran)(12)
        napis = Gtk.Label(xalign=0)
        def osvezi_napis():
            napis.set_text(self._t("pp_disk", mb=velikost_mape_mb(self._mapa_predpomnilnika())))
        osvezi_napis()
        pocisti = Gtk.Button(label=self._t("pp_pocisti"))
        pocisti.connect("clicked", lambda *_: self._pocisti_predpomnilnik(lambda: self.GLib.timeout_add(500, lambda: (osvezi_napis(), False)[1])))
        meja_mb = int(self.config.get("splet_predpomnilnik_meja_mb", 500) or 500)
        samodejno = Gtk.CheckButton(label=self._t("pp_meja", mb=meja_mb))
        samodejno.set_active(int(self.config.get("splet_predpomnilnik_meja_mb", 500) or 0) > 0)
        samodejno.connect("toggled", lambda g: self.config.set("splet_predpomnilnik_meja_mb", meja_mb if g.get_active() else 0))
        obmocje.pack_start(napis, False, False, 0); obmocje.pack_start(pocisti, False, False, 0)
        obmocje.pack_start(samodejno, False, False, 0)
        obmocje.pack_start(Gtk.Label(label=self._t("pp_strani"), xalign=0, margin_top=8), False, False, 0)
        iskanje = Gtk.SearchEntry(); iskanje.set_placeholder_text(self._t("pp_iskanje"))
        obmocje.pack_start(iskanje, False, False, 0)
        okvir = Gtk.ScrolledWindow(); okvir.set_vexpand(True)
        seznam = Gtk.ListBox(); okvir.add(seznam); obmocje.pack_start(okvir, True, True, 0)
        vrste = W.WebsiteDataTypes.ALL if hasattr(W.WebsiteDataTypes, "ALL") else (
            W.WebsiteDataTypes.COOKIES | W.WebsiteDataTypes.LOCAL_STORAGE | W.WebsiteDataTypes.INDEXEDDB_DATABASES
            | W.WebsiteDataTypes.DISK_CACHE)
        podatki = []
        def izrisi(*_):
            for v in seznam.get_children():
                v.destroy()
            niz = iskanje.get_text().strip().lower()
            for wd in sorted(podatki, key=lambda x: x.get_name() or ""):
                ime = wd.get_name() or ""
                if niz and niz not in ime.lower():
                    continue
                vrstica = Gtk.Box(spacing=8, margin=6)
                vrstica.pack_start(Gtk.Label(label=ime, xalign=0), True, True, 0)
                gumb = Gtk.Button(label=self._t("pp_odstrani"))
                def odstrani(_g, wd=wd):
                    upr.remove(vrste, [wd], None, lambda *_: (podatki.remove(wd), izrisi(), osvezi_napis()), None)
                gumb.connect("clicked", odstrani)
                vrstica.pack_end(gumb, False, False, 0)
                seznam.add(vrstica)
            seznam.show_all()
        def prejeto(m, rezultat, *_):
            try:
                podatki[:] = list(m.fetch_finish(rezultat) or [])
            except Exception as napaka:  # noqa: BLE001
                print("[Safeer OS Splet] podatki strani:", napaka)
            izrisi()
        upr.fetch(vrste, None, prejeto, None)
        iskanje.connect("search-changed", izrisi)
        d.connect("response", lambda *_: d.destroy())
        d.show_all()

    def _miska(self, pogled, dogodek) -> bool:
        """Stranska gumba miske (nazaj/naprej), kot v drugih brskalnikih."""
        if dogodek.button == 8:
            pogled.go_back(); return True
        if dogodek.button == 9:
            pogled.go_forward(); return True
        return False

    def sprosti_zavihke(self) -> None:
        """Zapre vse zavihke (spletni proces se konca in vrne pomnilnik); naslednji odpri() naredi nov zavihek.
        Objekt in kontekst ostaneta - ponovno ustvarjanje celega Spleta bi pustilo staro (casovnik, kontekst)."""
        for z in list(self.zavihki):
            try:
                self.skatla_zavihkov.remove(z["dogodek"]); self.sklad.remove(z["pogled"])
                z["pogled"].destroy(); z["dogodek"].destroy()
            except Exception:  # noqa: BLE001
                pass
        self.zavihki = []
        self.aktivni = None
        self.koncaj_omrezni_proces()

    def koncaj_omrezni_proces(self) -> bool:
        """Konca omrezni proces Spleta, ko Splet nima zavihkov; ob naslednjem zavihku WebKit zazene novega.

        12. 10. 2026: libsoup 3.4.4-5ubuntu0.9 (in upstream) pri vsaki povezavi prek posrednika (nas DoH) pusti
        SoupConnection - omrezni proces je rasel ~6 MiB/min (krog147/libsoup-prispevek). Do popravka v distribucijah
        tako pomnilnik vrnemo ob vsaki sprostitvi Spleta; DNS ostane sifriran. Proces Spleta prepoznamo po tem, da ima
        odprto shrambo piskotkov Spleta (zanesljivo, ne glede na cas zagona; namizje in Control je nimata)."""
        konec = False
        for pid in omrezni_procesi_shrambe(os.path.join(self.config.config_dir, "cookies.sqlite")):
            try:
                os.kill(pid, 15)
                konec = True
            except OSError:
                pass
        return konec

    def ob_zaklepu(self, meja_mb: float = 300.0) -> bool:
        """Zaslon zaklenjen: zavihki ostanejo, sprostimo predpomnilnik; prevelik omrezni proces (libsoup pusca prek
        DoH posrednika) obnovimo, ce se nobena stran ne nalaga. Vrne True, ce je bil omrezni proces obnovljen."""
        self.sprazni_predpomnilnik()
        try:
            if any(z["pogled"].is_loading() for z in self.zavihki):
                return False
        except Exception:  # noqa: BLE001
            return False
        obnovljen = False
        for pid in omrezni_procesi_shrambe(os.path.join(self.config.config_dir, "cookies.sqlite")):
            if pss_mb(pid) >= meja_mb:
                try:
                    os.kill(pid, 15)
                    obnovljen = True
                except OSError:
                    pass
        return obnovljen

    def sprazni_predpomnilnik(self) -> bool:
        """Ob skritju Spleta: spletni procesi izpraznejo pomnilniski predpomnilnik (dekodirane slike, skripte, CSS).
        Zavihki in strani ostanejo - ob ponovnem odprtju so tam, kjer jih je uporabnik pustil; strani se le
        ponovno izrisejo iz predpomnilnika na disku (stresni preizkus 12. 10. 2026: pri pogosti rabi se Splet nikoli
        ni bil 60 s skrit, zato se njegov proces ni nikoli zmanjsal)."""
        try:
            upr = self.kontekst.get_website_data_manager()
            upr.clear(self.WebKit2.WebsiteDataTypes.MEMORY_CACHE, 0, None, None, None)
            return True
        except Exception:  # noqa: BLE001 - starejsi WebKit brez tega: ostane sprostitev po minuti
            return False

    def izberi(self, pogled):
        self.aktivni = pogled; self.sklad.set_visible_child(pogled)
        for z in self.zavihki:
            slog = z["vrstica"].get_style_context()
            if z["pogled"] is pogled:
                slog.add_class("splet-tab-aktiven")
            else:
                slog.remove_class("splet-tab-aktiven")
        self._osvezi_orodja()

    def trenutni(self):
        return self.aktivni

    def domaci_uri(self) -> str:
        return self.GLib.filename_to_uri(os.path.join(self.koren, "ui", "splet.html"), None)

    def odpri_domov(self):
        if self.trenutni(): self.trenutni().load_uri(self.domaci_uri())

    def odpri(self, naslov: str = "", pogled=None):
        pogled = pogled or self.trenutni()
        if pogled is None:
            if self.zavihki:
                return False
            self.nov_zavihek(naslov)        # po sprosti_zavihke(): prvi zavihek na novo
            return True
        if not naslov: pogled.load_uri(self.domaci_uri()); return True
        normalen = normalize_web_url(naslov)
        if not normalen: return False
        pogled.load_uri(normalen); return True

    def odpri_povezavo(self, naslov: str) -> bool:
        """Povezava od drugod (sporočilo): strani, ki jo ima uporabnik odprto, ne zamenja. V zavihku z našo začetno
        stranjo se odpre tam, sicer v novem zavihku."""
        normalen = normalize_web_url(naslov)
        if not normalen: return False
        pogled = self.trenutni()
        if pogled is not None and ozadje_strani.nasa_stran(pogled.get_uri() or "", os.path.join(self.koren, "ui")):
            pogled.load_uri(normalen); return True
        self.nov_zavihek(normalen); return True

    def _vnesi_naslov(self, vnos):
        besedilo = vnos.get_text().strip()
        naslov = normalize_web_url(besedilo)
        if not naslov:
            motor = self.config.get("search_engine", "duckduckgo")
            naslov = SEARCH_ENGINES.get(motor, SEARCH_ENGINES["duckduckgo"])["url"] + urllib.parse.quote_plus(besedilo)
        self.odpri(naslov)

    def _politika(self, pogled, odlocitev, vrsta):
        W = self.WebKit2
        if vrsta not in (W.PolicyDecisionType.NAVIGATION_ACTION, W.PolicyDecisionType.NEW_WINDOW_ACTION): return False
        try:
            dejanje = odlocitev.get_navigation_action(); zahteva = dejanje.get_request(); naslov = zahteva.get_uri() or ""
            if naslov.lower().startswith("stremio://"):
                # Stran sama ne doda nicesar: dodatek se doda sele, ko uporabnik v Safeer Playerju pritisne Poveži.
                odlocitev.ignore()
                if self.stremio_dodatek is not None:
                    self.GLib.idle_add(lambda: self.stremio_dodatek(naslov) and False)
                return True
            if vrsta == W.PolicyDecisionType.NEW_WINDOW_ACTION:
                odlocitev.ignore(); self.nov_zavihek(naslov); return True
            # Srednji klik ali Ctrl+klik na povezavo: nov zavihek (kot v drugih brskalnikih).
            if (dejanje.get_navigation_type() == W.NavigationType.LINK_CLICKED and naslov.startswith(("http://", "https://"))
                    and (dejanje.get_mouse_button() == 2 or dejanje.get_modifiers() & int(self.Gdk.ModifierType.CONTROL_MASK))):
                odlocitev.ignore(); self.nov_zavihek(naslov); return True
            if naslov.startswith(("file://", "about:blank")):
                odlocitev.use(); return True
            if not naslov.startswith(("http://", "https://")):
                odlocitev.ignore(); return True
            grozi = adblock.is_threat_domain(naslov)      # enkrat na navigacijo (prej dvakrat)
            if not grozi and self.config.get("adblock_enabled", True) and adblock.is_ad_domain(naslov):
                self.config.increment_ads_blocked(); odlocitev.ignore(); self._osvezi_scit(); return True
            if grozi:
                self.config.increment_threats_blocked(); odlocitev.ignore(); self._opozorilo("Safeer Shield", naslov); self._osvezi_scit(); return True
            sodba = adblock.fake_bank_verdict(naslov)
            if sodba is not None:
                odlocitev.ignore(); self._opozorilo_bank(pogled, naslov, sodba); return True
            if self.config.get("tracking_protection_enabled", True) and zahteva.get_http_method() == "GET":
                cist = adblock.strip_tracking_parameters(naslov)
                if cist != naslov: odlocitev.ignore(); pogled.load_uri(cist); return True
            odlocitev.use(); return True
        except Exception:
            odlocitev.ignore(); return True

    def _novo_okno(self, _pogled, dejanje):
        try: naslov = dejanje.get_request().get_uri() or ""
        except Exception: naslov = ""
        return self.nov_zavihek(naslov)

    def _nalozen(self, pogled, dogodek):
        if dogodek != self.WebKit2.LoadEvent.FINISHED: return
        naslov = pogled.get_uri() or ""
        if je_domaca_stran(naslov, self.koren):
            self._poslji_stanje(pogled)
        else:
            self._preveri_bank_stran(pogled, naslov)
            from core import zgodovina
            zgodovina.dodaj(os.path.join(self.config.config_dir, "history.json"), naslov, pogled.get_title() or "")
        self._osvezi_orodja()

    def _poslji_stanje(self, pogled, prenesi=True):
        """Zacetna stran Splet: jezik, iskalnik in bliznjice z ikonami (manjkajoce se prenesejo v ozadju)."""
        from core import ikone_strani
        portali, manjkajo = ikone_strani.z_ikonami(self.config.get_home_portals())
        # Kdor je kdaj imel lastne bliznjice, mu vgrajenih ne vracamo, ko svoje odstrani (nic ni vsiljeno).
        if portali and not self.config.get("splet_brez_privzetih", False): self.config.set("splet_brez_privzetih", True)
        stanje = {"language": self.jezik(), "engine": self.config.get("search_engine", "duckduckgo"), "portals": portali,
                  "hidden": list(self.config.get("splet_skrite_bliznjice", []) or []),
                  "no_defaults": bool(self.config.get("splet_brez_privzetih", False))}
        pogled.run_javascript("window.safeerSpletInit(%s);" % json.dumps(stanje, ensure_ascii=True), None, None, None)
        if prenesi and manjkajo and not getattr(self, "_ikone_tecejo", False):
            self._ikone_tecejo = True
            import threading

            def delo():
                for url in manjkajo[:40]:
                    ikona = ikone_strani.ikona_strani(url)
                    if ikona:
                        ikone_strani.shrani(url, ikona)
                self.GLib.idle_add(konec)

            def konec():
                self._ikone_tecejo = False
                for z in list(self.zavihki):
                    if je_domaca_stran(z["pogled"].get_uri() or "", self.koren):
                        self._poslji_stanje(z["pogled"], prenesi=False)
                return False

            threading.Thread(target=delo, name="safeer-ikone", daemon=True).start()

    def _naslov_spremenjen(self, pogled, _lastnost):
        z = next((x for x in self.zavihki if x["pogled"] is pogled), None)
        if z:
            z["naslov"].set_text(self._t("nov") if je_domaca_stran(pogled.get_uri() or "", self.koren) else (pogled.get_title() or self._t("nov")))

    def _uri_spremenjen(self, pogled, _lastnost):
        if pogled is self.trenutni(): self._osvezi_orodja()

    def _osvezi_orodja(self):
        pogled = self.trenutni()
        if not pogled: return
        uri = pogled.get_uri() or ""
        domaca = je_domaca_stran(uri, self.koren)
        self.vnos.set_text("" if domaca else uri)
        self.nazaj.set_sensitive(pogled.can_go_back()); self.naprej.set_sensitive(pogled.can_go_forward())
        self.kljucavnica.set_opacity(1.0 if uri.startswith("https://") else 0.0)
        self._osvezi_scit()

    def _sporocilo(self, pogled, rezultat):
        try:
            vrednost = rezultat.get_js_value().to_json(0)
            sporocilo = razcleni_sporocilo(vrednost)
        except Exception: sporocilo = None
        if not sporocilo:
            return
        if sporocilo["action"] == "increment_ads":
            self.config.increment_ads_blocked(sporocilo["count"]); self._osvezi_scit(); return
        if sporocilo["action"] == "increment_threats":
            self.config.increment_threats_blocked(sporocilo["count"]); self._osvezi_scit(); return
        # Navigacija in odpiranje dialoga sta zaupni dejanji in veljata le za naso zacetno stran.
        if not je_domaca_stran(pogled.get_uri() or "", self.koren):
            return
        if sporocilo["action"] == "navigate": self.odpri(sporocilo["url"], pogled)
        elif sporocilo["action"] == "open_sidebar": self._dodaj_portal()
        elif sporocilo["action"] == "remove_portal":
            # Lastno bliznjico izbrisemo, vgrajeno si zapomnimo kot odstranjeno (stran je ne pokaze vec).
            self.config.delete_portal(sporocilo["url"])
            for p in list(self.config.get_portals()):
                if kljuc_bliznjice(p.get("url")) == kljuc_bliznjice(sporocilo["url"]): self.config.delete_portal(p.get("id"))
            skrite = [k for k in (self.config.get("splet_skrite_bliznjice", []) or []) if k != kljuc_bliznjice(sporocilo["url"])]
            self.config.set("splet_skrite_bliznjice", skrite + [kljuc_bliznjice(sporocilo["url"])])
        elif sporocilo["action"] == "reset_portals":
            self.config.set("splet_skrite_bliznjice", []); self.config.set("splet_brez_privzetih", False)
            self._poslji_stanje(pogled, prenesi=False)

    def _stevec(self, rezultat):
        """Stevec scita iz kozmeticne skripte (loceni svet). Samo increment; stevilo omejeno."""
        try:
            s = adblock.preveri_stevec(json.loads(rezultat.get_js_value().to_json(0)))
        except Exception:
            s = None
        if not s:
            return
        if s["action"] == "increment_ads":
            self.config.increment_ads_blocked(s["count"])
        else:
            self.config.increment_threats_blocked(s["count"])
        self._osvezi_scit()

    def _dodaj_portal(self, *_):
        d = self.Gtk.Dialog(title=self._t("dodaj"), transient_for=self._okno_za_dialog(), flags=self.Gtk.DialogFlags.MODAL)
        d.add_button(self._t("preklici"), self.Gtk.ResponseType.CANCEL); d.add_button(self._t("shrani"), self.Gtk.ResponseType.OK)
        mreza = self.Gtk.Grid(column_spacing=10, row_spacing=8, margin=16)
        ime, url = self.Gtk.Entry(), self.Gtk.Entry(); url.set_text("https://")
        mreza.attach(self.Gtk.Label(label=self._t("ime"), xalign=0), 0, 0, 1, 1); mreza.attach(ime, 1, 0, 1, 1)
        mreza.attach(self.Gtk.Label(label=self._t("url"), xalign=0), 0, 1, 1, 1); mreza.attach(url, 1, 1, 1, 1)
        d.get_content_area().add(mreza); d.show_all()
        if d.run() == self.Gtk.ResponseType.OK:
            naslov = normalize_web_url(url.get_text())
            if naslov:
                self.config.add_portal(ime.get_text().strip() or urllib.parse.urlparse(naslov).hostname, naslov)
                # Znova dodana bliznjica ni vec med odstranjenimi.
                self.config.set("splet_skrite_bliznjice", [k for k in (self.config.get("splet_skrite_bliznjice", []) or []) if k != kljuc_bliznjice(naslov)])
        d.destroy()
        p = self.trenutni()
        if p and je_domaca_stran(p.get_uri() or "", self.koren): p.reload()

    def dodaj_trenutno(self):
        p = self.trenutni(); uri = p.get_uri() if p else ""
        if not uri or je_domaca_stran(uri, self.koren): return
        self.config.add_portal(p.get_title() or urllib.parse.urlparse(uri).hostname or uri, uri)
        if self.Gtk.IconTheme.get_default().has_icon("starred-symbolic"):
            self.zvezdica.set_image(self.Gtk.Image.new_from_icon_name("starred-symbolic", self.Gtk.IconSize.BUTTON))
        else:
            self.zvezdica.set_label("★")

    def osvezi_povezavo(self):
        try: ok = (self.stanje_povezave() or {}).get("stanje") == "povezan"
        except Exception: ok = False
        self.povezava.set_text(("● " if ok else "○ ") + self._t("povezan" if ok else "nepovezan"))
        return True

    def _osvezi_scit(self):
        pass  # stevca ni vec; namig gumba ostane "scit"

    def _preveri_bank_stran(self, pogled, uri):
        if not uri.startswith(("http://", "https://")) or adblock.is_real_bank_host(uri): return
        skripta = adblock.bank_guard_page_script()
        if not skripta: return
        pogled.run_javascript_in_world(skripta, "safeer-bankguard", None, self._bank_signali, (pogled, uri))

    def _bank_signali(self, pogled, rezultat, podatki):
        pogled0, uri = podatki
        try: signali = json.loads(pogled.run_javascript_in_world_finish(rezultat).get_js_value().to_json(0) or "null")
        except Exception: return
        if pogled0.get_uri() != uri: return
        sodba = adblock.fake_bank_page_verdict(uri, signali)
        if sodba is not None: self._opozorilo_bank(pogled0, uri, sodba, True)

    def _opozorilo_bank(self, pogled, uri, sodba, nalozen=False):
        d = self.Gtk.MessageDialog(transient_for=self._okno_za_dialog(), flags=0, message_type=self.Gtk.MessageType.WARNING,
                                   buttons=self.Gtk.ButtonsType.NONE, text="Safeer Shield · BankGuard")
        d.format_secondary_text(adblock.fake_bank_warning_text(sodba, self.jezik()))
        d.add_button(self._t("nazaj"), 1)
        if sodba.official_domain: d.add_button(sodba.official_domain, 2)
        odgovor = d.run(); d.destroy()
        if odgovor == 2: pogled.load_uri("https://" + sodba.official_domain + "/")
        elif nalozen: pogled.go_back() if pogled.can_go_back() else pogled.load_uri(self.domaci_uri())

    def _opozorilo(self, naslov, opis):
        d = self.Gtk.MessageDialog(transient_for=self._okno_za_dialog(), flags=0, message_type=self.Gtk.MessageType.WARNING,
                                   buttons=self.Gtk.ButtonsType.CLOSE, text=naslov)
        d.format_secondary_text(opis); d.run(); d.destroy()

    def _dovoljenje(self, _pogled, zahteva):
        pravilo = self.config.get("permissions_policy", "ask")
        if pravilo == "allow":
            zahteva.allow(); return True
        if pravilo == "deny":
            zahteva.deny(); return True
        d = self.Gtk.MessageDialog(transient_for=self._okno_za_dialog(), flags=self.Gtk.DialogFlags.MODAL,
                                   message_type=self.Gtk.MessageType.QUESTION,
                                   buttons=self.Gtk.ButtonsType.NONE, text=self._t("dovoljenje"))
        d.add_button(self._t("zavrni"), self.Gtk.ResponseType.NO)
        d.add_button(self._t("dovoli"), self.Gtk.ResponseType.YES)
        odgovor = d.run(); d.destroy()
        zahteva.allow() if odgovor == self.Gtk.ResponseType.YES else zahteva.deny()
        return True

    def _prenos_zacet(self, _kontekst, prenos):
        ime = os.path.basename(urllib.parse.urlparse(prenos.get_request().get_uri()).path) or "prenos"
        cilj = os.path.join(os.path.expanduser("~/Downloads"), ime)
        os.makedirs(os.path.dirname(cilj), exist_ok=True)
        prenos.set_destination(self.GLib.filename_to_uri(cilj, None)); self.prenosi.append(cilj)

    def _pokazi_prenose(self, *_): self._opozorilo(self._t("prenosi"), "\n".join(self.prenosi[-10:]) or "—")
    def _pokazi_najdi(self): self.najdi_vrstica.set_search_mode(True); self.najdi_vnos.grab_focus()
    def _najdi(self, vnos):
        if self.trenutni(): self.trenutni().get_find_controller().search(vnos.get_text(), 0, 1000)
    def _povecava(self, korak):
        if self.trenutni(): self.trenutni().set_zoom_level(max(.5, min(3.0, self.trenutni().get_zoom_level() + korak)))
    def _nastavitve(self, *_):
        d = self.Gtk.Dialog(title=self._t("nastavitve"), transient_for=self._okno_za_dialog(), flags=self.Gtk.DialogFlags.MODAL)
        d.add_button(self._t("preklici"), self.Gtk.ResponseType.CANCEL)
        d.add_button(self._t("shrani"), self.Gtk.ResponseType.OK)
        mreza = self.Gtk.Grid(column_spacing=12, row_spacing=12, margin=18)
        motor = self.Gtk.ComboBoxText()
        for kljuc, podatki in SEARCH_ENGINES.items(): motor.append(kljuc, podatki["name"])
        motor.set_active_id(self.config.get("search_engine", "duckduckgo"))
        oglasi = self.Gtk.CheckButton(label=self._t("adblock")); oglasi.set_active(self.config.get("adblock_enabled", True))
        doh = self.Gtk.CheckButton(label=self._t("doh")); doh.set_active(self.config.get("doh_enabled", True))
        strojno = self.Gtk.CheckButton(label=self._t("strojno"))
        strojno.set_active(self.config.get("hardware_acceleration", "on_demand") != "never")
        mreza.attach(self.Gtk.Label(label=self._t("iskalnik"), xalign=0), 0, 0, 1, 1); mreza.attach(motor, 1, 0, 1, 1)
        mreza.attach(oglasi, 0, 1, 2, 1); mreza.attach(doh, 0, 2, 2, 1); mreza.attach(strojno, 0, 3, 2, 1)
        jezik = str(self.jezik() if callable(self.jezik) else self.jezik or "sl")
        temno = self.Gtk.ComboBoxText()
        for n in splet_temno.NACINI: temno.append(n, splet_temno.besedilo(jezik, n))
        temno.set_active_id(self._temno_nacin())
        mreza.attach(self.Gtk.Label(label=splet_temno.besedilo(jezik, "nastavitev"), xalign=0), 0, 4, 1, 1)
        mreza.attach(temno, 1, 4, 1, 1)
        d.get_content_area().add(mreza); d.show_all()
        if d.run() == self.Gtk.ResponseType.OK:
            self.config.set("search_engine", motor.get_active_id() or "duckduckgo")
            self.config.set("adblock_enabled", oglasi.get_active())
            self.config.set("doh_enabled", doh.get_active())
            self.config.set("hardware_acceleration", "on_demand" if strojno.get_active() else "never")
            if (temno.get_active_id() or splet_temno.PRIVZETO) != self._temno_nacin():
                self.config.set("temno_nacin", temno.get_active_id() or splet_temno.PRIVZETO)
                self._temno_osvezi(znova_nalozi=self.trenutni())
            politika = politika_pospesevanja(self.WebKit2, self.config.get("hardware_acceleration"))
            for z in self.zavihki:
                z["pogled"].get_settings().set_hardware_acceleration_policy(politika)
            self._nastavi_omrezje()
        d.destroy()
    def _v_zapisek(self, *_):
        p = self.trenutni()
        if self.odpri_zapisek and p: self.odpri_zapisek(p.get_title() or self._t("nov"), p.get_uri() or "")

    def koncaj(self):
        if self.filter_agent: self.filter_agent.stop()
        # Vir groženj je skupen za ves proces (threat_intel.skupna: tudi Scit) - ne ustavljamo ga tu.
        try:
            get_doh_proxy(enabled=False)
        except Exception:
            pass
