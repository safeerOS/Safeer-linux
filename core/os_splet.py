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

from core import adblock, drm, odlozisce_varuh, os_stabilnost, ozadje_strani, safeer_drm, splet_prenosi, splet_temno
from core.config import ConfigManager, SEARCH_ENGINES, normalize_web_url
from core.doh_proxy import get_doh_proxy, nastavitve_posrednika
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
for _j, _b in splet_prenosi.BESEDILA.items():   # prenosi: skupaj s Safeer Browserjem
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


#: Strani, ki jih Skia kompozitor WebKita 2.54 ne zmore (24ur.com: 28 elementov z backdrop-filter -> 2^n izrisov,
#: ~100 MB/s in 100 % CPU, meritev 13. 10. 2026). Velja SAMO, ce je Skia kompozitor vklopljen (glej nastavi_kompozitor);
#: s TextureMapperjem (privzeto v Spletu) te strani tecejo normalno, s pospesevanjem. Uceni seznam (VdelaniSplet.
#: _proces_pomnilnik) velja vedno.
BREZ_POSPESEVANJA = ("24ur.com",)

#: Konfiguracijski kljuc razlicice izrisa: ob prehodu na TextureMapper (2) se pozabi uceni seznam iz casa Skie.
KOMPOZITOR_RAZLICICA = 2


def nastavi_kompozitor(WebKit2, nastavitve, skia: bool = False) -> bool:
    """Izbere kompozitor WebKita 2.54: Skia (UseSkiaForComposition) ali TextureMapper.

    Skia kompozitor naredi za n elementov z backdrop-filter 2^n izrisov podrevesa (WebKit SkiaCompositingLayer::
    paintBackdrop; poroceno gorvodno 13. 10. 2026): stran z 20+ takimi elementi ustavi izris, porabi 100 % jedra in
    pomnilnik raste do OOM. TextureMapper na 10 straneh ni pocasnejsi (hladno LCP -16 %, toplo load -11 %, FCP enak;
    zameglitev ozadja, filtri in 3D enaki na 1,6/255). Vrne True, ce WebKit to stikalo pozna (2.54+)."""
    try:
        seznam = WebKit2.Settings.get_all_features()
        for i in range(seznam.get_length()):
            f = seznam.get(i)
            if f.get_identifier() == "UseSkiaForComposition":
                nastavitve.set_feature_enabled(f, bool(skia))
                return True
    except Exception:  # noqa: BLE001 - starejsi WebKit brez API funkcij
        pass
    return False


def gostitelj_strani(naslov: str) -> str:
    try:
        return (urllib.parse.urlsplit(naslov).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def brez_pospesevanja(naslov: str, ucene=(), skia: bool = True) -> bool:
    """Ali naj se ta stran izrise brez strojnega pospesevanja (domena ali njena poddomena na seznamu).
    Staticni seznam velja le pri Skia kompozitorju (skia=True), uceni seznam vedno."""
    g = gostitelj_strani(naslov)
    if not g:
        return False
    domene = (tuple(BREZ_POSPESEVANJA) if skia else ()) + tuple(ucene or ())
    return any(g == d or g.endswith("." + d) for d in domene)


def ucene_brez_pospesevanja(config) -> list:
    """Uceni seznam domen brez strojnega izrisa (skupen Spletu in brskalniku Safeer: isti ConfigManager). Ob novi
    razlicici kompozitorja se seznam pozabi (domene iz casa Skie TextureMapperju ne skodijo)."""
    try:
        if config.get("splet_kompozitor_v", 0) != KOMPOZITOR_RAZLICICA:
            config.set("splet_brez_pospesevanja", [])
            config.set("splet_kompozitor_v", KOMPOZITOR_RAZLICICA)
        v = config.get("splet_brez_pospesevanja", [])
    except Exception:  # noqa: BLE001
        return []
    return [str(x) for x in v] if isinstance(v, list) else []


def nauci_po_padcu(WebKit2, razlog, naslov: str, ucene, skia: bool, varuh_pred_s: float):
    """Proces strani je presegel mejo pomnilnika (WebKit) ali ga je pred manj kot 5 s ustavil varuh (splet_varuh):
    vrne nov uceni seznam z domeno te strani (zadnjih 50) ali None, ce se nimamo cesa nauciti."""
    R = getattr(WebKit2, "WebProcessTerminationReason", None)
    pomn = razlog == getattr(R, "EXCEEDED_MEMORY_LIMIT", object())
    varuh = razlog == getattr(R, "CRASHED", object()) and varuh_pred_s < 5
    if not (pomn or varuh):
        return None
    g = gostitelj_strani(naslov or "")
    if not g or brez_pospesevanja("https://" + g, ucene, skia):
        return None
    return (list(ucene) + [g])[-50:]


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


def _gostitelj(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _js_vrednost(rezultat):
    """Vrednost sporocila skripte: WebKit 6.0 da JSC.Value, WebKit2 4.1 JavascriptResult."""
    return rezultat.get_js_value() if hasattr(rezultat, "get_js_value") else rezultat


def registriraj_most(upravitelj, ime: str, svet=None) -> None:
    """register_script_message_handler za WebKit 6.0 (ime, svet) in 4.1 (ime / _in_world)."""
    try:
        upravitelj.register_script_message_handler(ime, svet)
        return
    except TypeError:
        pass
    if svet:
        upravitelj.register_script_message_handler_in_world(ime, svet)
    else:
        upravitelj.register_script_message_handler(ime)


def _unici_pogled(pogled) -> None:
    """Zaprt zavihek: GTK4 nima destroy(), try_close() strani ne ustavi (preizkus 14. 10.: stran je po zaprtju
    zavihka se posiljala sporocila, zvok bi tekel naprej). run_dispose() pogled sprosti takoj, kot destroy() v GTK3."""
    os_stabilnost.oznaci_zaprt(pogled)
    try:
        pogled.stop_loading()
        pogled.run_dispose()
    except Exception:  # noqa: BLE001
        pass


def _ocisti(skatla) -> None:
    """GTK4: odstrani vse otroke gradnika (ListBox, Box)."""
    otrok = skatla.get_first_child()
    while otrok is not None:
        naslednji = otrok.get_next_sibling()
        skatla.remove(otrok)
        otrok = naslednji


def _kratka_pot(pot: str) -> str:
    """Pot za uporabnika: domaca mapa kot ~ (krajse in brez uporabniskega imena na posnetkih zaslona)."""
    dom = os.path.expanduser("~")
    return "~" + pot[len(dom):] if pot == dom or pot.startswith(dom + os.sep) else pot


def _robovi(gradnik, rob: int):
    for stran in ("set_margin_start", "set_margin_end", "set_margin_top", "set_margin_bottom"):
        getattr(gradnik, stran)(rob)
    return gradnik


class _Tipka:
    """Tipka iz GTK4 EventControllerKey z enakima poljema kot Gdk.EventKey v GTK3 (keyval, state)."""
    __slots__ = ("keyval", "state")

    def __init__(self, keyval, state):
        self.keyval, self.state = keyval, state

    def get_keyval(self):
        return True, self.keyval

    def get_state(self):
        return True, self.state


class _Klik:
    """Klik iz GTK4 GestureClick z enakimi polji kot Gdk.EventButton v GTK3 (button, x, y)."""
    __slots__ = ("button", "x", "y")

    def __init__(self, button, x, y):
        self.button, self.x, self.y = button, x, y


class VdelaniSplet:
    """GTK4 gradnik z zavihki (WebKitGTK 6.0); namenoma ni okno in zato ne more zapustiti Safeer OS.

    Prehod na GTK4 (lastnik, 14. 10. 2026): na X11 GTK3 nima EGL, zato je WebKit vsak okvir kopiral prek procesorja
    v vmesnik in Xorg (24ur ~40 % jedra); GTK4 sliko pokaze z EGL brez kopije. Lupina Safeer OS je v QML (kot na
    Windows), Splet in vsebine ostanejo na nasem WebKitGTK - v istem procesu (Qt vrti zanko GLib)."""

    def __init__(self, Gtk, Gdk, Gio, GLib, WebKit2, koren: str, jezik, stanje_povezave,
                 odpri_zapisek=None, stars=None, stremio_dodatek=None):
        # WebKit2 je tu modul WebKit (API 6.0); ime parametra ostane zaradi skupnih pomoznih funkcij.
        self.Gtk, self.Gdk, self.Gio, self.GLib, self.WebKit2 = Gtk, Gdk, Gio, GLib, WebKit2
        from gi.repository import Pango
        self.Pango = Pango
        self.koren, self.jezik = koren, jezik
        self.stanje_povezave, self.odpri_zapisek = stanje_povezave, odpri_zapisek
        self.stars = stars
        #: Gumb »Install« dodatka Stremio (povezava stremio://...): Safeer Player pokaze dodatek in vprasa (kot Android).
        self.stremio_dodatek = stremio_dodatek
        self.config = ConfigManager()
        ucene_brez_pospesevanja(self.config)   # ob novi razlicici kompozitorja pozabi stari uceni seznam
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
            vrh = self.gradnik.get_root()
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
        # WebKitGTK 6.0: podatki, piskotki, posrednik in prenosi so na NetworkSession (ista mapa kot prej: obstojece
        # prijave, zgodovina shrambe in piskotki ostanejo). Peskovnik je v 6.0 vedno vklopljen (ni vec izklopa).
        from core import pomnilnik
        try:
            self.seja = WebKit2.NetworkSession.new(mapa, os.path.join(mapa, "cache"))
            piskotki = self.seja.get_cookie_manager()
            piskotki.set_persistent_storage(os.path.join(self.config.config_dir, "cookies.sqlite"),
                                            WebKit2.CookiePersistentStorage.SQLITE)
            piskotki.set_accept_policy(WebKit2.CookieAcceptPolicy.NO_THIRD_PARTY)
        except Exception as napaka:
            print("[Safeer OS Splet] shramba:", napaka)
            self.seja = WebKit2.NetworkSession.get_default()
        try:
            self.kontekst = pomnilnik.kontekst(WebKit2, pomnilnik.meja_sprostitve_mb(), ubij_mb=pomnilnik.meja_strani_mb())
        except Exception as napaka:
            print("[Safeer OS Splet] kontekst:", napaka)
            self.kontekst = WebKit2.WebContext.get_default()
        # Varuh: proces strani, ki ga WebKitova meja ne ujame (puscanje DMA-BUF), ustavimo sami (core/splet_varuh.py).
        self._varuh_ubil = -1e9
        self.GLib.timeout_add_seconds(5, self._varuh_tik)
        try:
            self.kontekst.set_cache_model(WebKit2.CacheModel.WEB_BROWSER)
        except Exception:
            pass
        self._nastavi_omrezje()
        self.seja.connect("download-started", self._prenos_zacet)
        self._omeji_predpomnilnik()

    def podatki(self):
        """WebsiteDataManager Spleta (6.0: na seji)."""
        return self.seja.get_website_data_manager()

    def _nastavi_omrezje(self) -> None:
        W = self.WebKit2
        izjeme = ["localhost", "127.0.0.0/8", "::1", "10.0.0.0/8", "192.168.0.0/16", "172.16.0.0/12", ".local"]
        try:
            nacin = self.config.get("secure_proxy_mode", "disabled")
            if nacin == "custom" and self.config.get("secure_proxy_url", "").strip():
                p = W.NetworkProxySettings.new(self.config.get("secure_proxy_url").strip(), izjeme)
                self.seja.set_proxy_settings(W.NetworkProxyMode.CUSTOM, p)
                return
            if self.config.get("doh_enabled", True) and self.config.get("doh_provider", "cloudflare") != "disabled":
                doh = get_doh_proxy(provider=self.config.get("doh_provider", "cloudflare"),
                                    custom_url=self.config.get("custom_doh_url", "https://1.1.1.1/dns-query"), enabled=True,
                                    lokalno=bool(self.config.get("doh_lokalno_omrezje", False)))
                if doh and doh.actual_port > 0:
                    p = nastavitve_posrednika(W, doh.actual_port, izjeme)
                    self.seja.set_proxy_settings(W.NetworkProxyMode.CUSTOM, p)
                    return
            self.seja.set_proxy_settings(W.NetworkProxyMode.DEFAULT, None)
        except Exception as napaka:
            print("[Safeer OS Splet] DoH/proxy:", napaka)

    def _zgradi(self) -> None:
        Gtk = self.Gtk
        self.gradnik = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.gradnik.set_name("safeer-splet")
        self.vrstica_zavihkov = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.vrstica_zavihkov.set_name("splet-zavihki")
        self.skatla_zavihkov = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.skatla_zavihkov.set_margin_start(10)
        self.vrstica_zavihkov.append(self.skatla_zavihkov)
        self.nov_gumb = self._gumb("+", lambda *_: self.nov_zavihek(), "new-tab")
        self.vrstica_zavihkov.append(self.nov_gumb)
        presledek = Gtk.Box(); presledek.set_hexpand(True)
        self.vrstica_zavihkov.append(presledek)
        self.povezava = Gtk.Label(label="")
        self.povezava.set_name("splet-povezava")
        self.povezava.set_margin_end(18)
        self.vrstica_zavihkov.append(self.povezava)
        self.gradnik.append(self.vrstica_zavihkov)

        orodja = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        orodja.set_name("splet-orodja")
        self.nazaj = self._gumb("←", lambda *_: self.trenutni() and self.trenutni().go_back(), "nav")
        self.naprej = self._gumb("→", lambda *_: self.trenutni() and self.trenutni().go_forward(), "nav")
        self.osvezi = self._gumb("↻", lambda *_: self._osvezi_trenutni(), "nav")
        self.domov = self._gumb("⌂", lambda *_: self.odpri_domov(), "nav")
        for g, namig in ((self.nazaj, "nazaj"), (self.naprej, "naprej"), (self.osvezi, "osvezi"), (self.domov, "domov")):
            g.set_tooltip_text(self._t(namig)); orodja.append(g)
        naslov = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        naslov.set_name("splet-naslov")
        naslov.set_hexpand(True)
        naslov.set_margin_start(4); naslov.set_margin_end(4)
        self.kljucavnica = (Gtk.Image.new_from_icon_name("channel-secure-symbolic")
                            if self._ima_ikono("channel-secure-symbolic") else Gtk.Label(label="🔒"))
        self.kljucavnica.set_margin_start(8); self.kljucavnica.set_margin_end(8)
        self.vnos = Gtk.Entry()
        self.vnos.set_name("splet-vnos")
        self.vnos.set_hexpand(True)
        self.vnos.set_placeholder_text(self._t("naslov"))
        self.vnos.connect("activate", self._vnesi_naslov)
        self._tipke(self.vnos, lambda e: self.tipka(e))
        self.zvezdica = self._gumb("☆", lambda *_: self.dodaj_trenutno(), "address-action")
        self.zvezdica.set_margin_end(5)
        naslov.append(self.kljucavnica)
        naslov.append(self.vnos)
        naslov.append(self.zvezdica)
        orodja.append(naslov)
        self.gumb_prenosov = self._gumb("⬇", self._pokazi_prenose, "nav")
        self.gumb_prenosov.set_visible(False)
        orodja.append(self.gumb_prenosov)
        self.scit = self._gumb("♢", lambda *_: None, "nav")
        self.scit.set_tooltip_text(self._t("scit"))
        orodja.append(self.scit)
        meni = Gtk.MenuButton()
        meni.set_icon_name("open-menu-symbolic")
        meni.set_name("splet-meni")
        meni.set_tooltip_text(self._t("meni"))
        self._meni_gumb = meni
        self._namesti_dejanja()
        # Meni se zgradi ob odprtju (vnos »Vsili temno na tej strani« je odvisen od trenutne strani).
        meni.set_create_popup_func(lambda g, *_: g.set_menu_model(self._meni()))
        orodja.append(meni)
        self.gradnik.append(orodja)
        self.orodja = orodja

        self.najdi_vrstica = Gtk.SearchBar()
        self.najdi_vnos = Gtk.SearchEntry()
        self.najdi_vnos.set_placeholder_text(self._t("isci"))
        self.najdi_vnos.connect("search-changed", self._najdi)
        self.najdi_vrstica.set_child(self.najdi_vnos)
        self.najdi_vrstica.connect_entry(self.najdi_vnos)
        self.gradnik.append(self.najdi_vrstica)
        self.sklad = Gtk.Stack()
        self.sklad.set_transition_type(Gtk.StackTransitionType.NONE)
        self.sklad.set_vexpand(True); self.sklad.set_hexpand(True)
        self.gradnik.append(self.sklad)
        self._css()
        self.osvezi_povezavo()

    # ---------------------------------------------------------------- GTK4 pomocniki
    def _ima_ikono(self, ime: str) -> bool:
        try:
            return self.Gtk.IconTheme.get_for_display(self.Gdk.Display.get_default()).has_icon(ime)
        except Exception:
            return False

    def _tipke(self, gradnik, obdelaj) -> None:
        """GTK4 nadomestek za key-press-event: obdelaj(e) dobi predmet z .keyval in .state (kot Gdk.EventKey)."""
        k = self.Gtk.EventControllerKey()
        k.set_propagation_phase(self.Gtk.PropagationPhase.CAPTURE)
        k.connect("key-pressed", lambda _k, keyval, _koda, stanje:
                  bool(obdelaj(_Tipka(keyval, stanje))))
        gradnik.add_controller(k)

    def _klik(self, gradnik, obdelaj, gumb: int = 0) -> None:
        """GTK4 nadomestek za button-press-event: obdelaj(gumb, x, y, gradnik). Gradnik pride iz krmilnika, zato ga
        obdelaj ne sme hraniti v zaprtju (krmilnik je last gradnika - krog bi gradnik ohranil zivega)."""
        k = self.Gtk.GestureClick()
        k.set_button(gumb)
        k.connect("pressed", lambda g, _n, x, y: obdelaj(g.get_current_button(), x, y, g.get_widget()))
        gradnik.add_controller(k)

    def _namesti_dejanja(self) -> None:
        """Dejanja menija Spleta (Gio.SimpleActionGroup »splet«) za Gio.Menu v PopoverMenu."""
        skupina = self.Gio.SimpleActionGroup()
        dejanja = {
            "nov": lambda: self.nov_zavihek(), "zaznamki": lambda: self._seznam("zaznamki"),
            "zgodovina": lambda: self._seznam("zgodovina"), "uvozi": lambda: self._uvozi(),
            "predpomnilnik": lambda: self._predpomnilnik(), "prenosi": lambda: self._pokazi_prenose(),
            "najdi": lambda: self._pokazi_najdi(), "povecaj": lambda: self._povecava(.1),
            "pomanjsaj": lambda: self._povecava(-.1), "nastavitve": lambda: self._nastavitve(),
            "zapisek": lambda: self._v_zapisek(), "temno": lambda: self._temno_preklopi_stran(),
        }
        for ime, dejanje in dejanja.items():
            d = self.Gio.SimpleAction.new(ime, None)
            d.connect("activate", lambda *_a, f=dejanje: f())
            skupina.add_action(d)
        self.gradnik.insert_action_group("splet", skupina)

    def _css(self) -> None:
        # Barve namizja Safeer OS (delovna.css): ozadje #0b1424, kartice #101a2b/#16233a, poudarek #8ac7ff - Splet je del
        # celotne teme (lastnik, 11. 10. 2026), ne zelen kot samostojni Safeer Browser.
        css = """
        #safeer-splet { background: #0b1424; color: #eaf2ff; }
        #splet-zavihki { background: #0b1424; min-height: 52px; }
        .splet-tab { background: #101a2b; color: #c3d4ea; border: 1px solid rgba(211,229,255,.14);
          border-bottom: 0; border-radius: 12px 12px 0 0; padding: 8px 12px; margin-top: 8px; min-width: 180px; }
        .splet-tab-aktiven { background: #16233a; color: #eaf2ff; border-color: rgba(138,199,255,.55);
          border-top: 2px solid #8ac7ff; }
        .splet-tab button, .new-tab, .nav, .address-action, #splet-meni > button { background: transparent; color: #eaf2ff;
          border: 0; box-shadow: none; text-shadow: none; }
        .new-tab { font-size: 24px; padding: 5px 10px; }
        #splet-povezava { color: #e3ecf7; border: 1px solid rgba(138,199,255,.55); border-radius: 14px;
          padding: 5px 14px; margin-top: 8px; margin-bottom: 8px; background: rgba(138,199,255,.08); }
        #splet-orodja { background: #0b1424; padding: 6px 14px 8px; }
        .nav { font-size: 20px; padding: 6px 9px; border-radius: 10px; color: #e2eaf6; }
        .nav image, .address-action image, #splet-meni image { color: #e2eaf6; -gtk-icon-size: 20px; }
        .nav:hover, .address-action:hover, #splet-meni > button:hover { background: rgba(104,168,229,.20); }
        #splet-naslov { background: #101a2b; border: 2px solid rgba(138,199,255,.55); border-radius: 20px; padding: 2px 6px; }
        #splet-vnos { background: transparent; color: #eaf2ff; border: 0; box-shadow: none; outline: none;
          font-size: 16px; padding: 10px 4px; }
        #splet-vnos selection { background: #2b5b8c; }
        popover.menu contents { background: #101a2b; color: #eaf2ff; border: 1px solid rgba(211,229,255,.23); }
        popover.menu modelbutton:hover { background: rgba(104,168,229,.20); }
        """
        ponudnik = self.Gtk.CssProvider()
        try:
            ponudnik.load_from_string(css)
        except AttributeError:  # GTK < 4.12
            ponudnik.load_from_data(css, -1)
        self.Gtk.StyleContext.add_provider_for_display(self.Gdk.Display.get_default(), ponudnik,
                                                        self.Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._css_ponudnik = ponudnik

    def _gumb(self, napis, dejanje, razred):
        # Sistemske simbolne ikone (enake oblike kot na Windows), sicer besedilo.
        ikone = {"←": "go-previous-symbolic", "→": "go-next-symbolic", "↻": "view-refresh-symbolic",
                 "⌂": "go-home-symbolic", "☆": "non-starred-symbolic", "♢": "security-high-symbolic",
                 "+": "list-add-symbolic"}
        if napis in ikone and self._ima_ikono(ikone[napis]):
            g = self.Gtk.Button.new_from_icon_name(ikone[napis])
        else:
            g = self.Gtk.Button(label=napis)
        g.set_has_frame(False)
        g.add_css_class(razred)
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
            # Prijave, Cloudflare in banke brez Dark Readerja (kot slog CSS v brskalniku; pregled 14. 10. 2026).
            return splet_temno.namesti(self.WebKit2, upravitelj, os.path.join(self.koren, "core"), self._temno_nacin(),
                                       self._namizje_temno(), self._temno_izjeme(), adblock.AUTH_SCRIPT_EXCLUSIONS)
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
        meni = self.Gio.Menu()
        vnosi = [("nov", "nov"), ("zaznamki", "zaznamki"), ("zgodovina", "zgodovina"), ("uvozi", "uvozi"),
                 ("predpomnilnik", "predpomnilnik"), ("prenosi", "prenosi"), ("najdi", "najdi"),
                 ("povecaj", "povecaj"), ("pomanjsaj", "pomanjsaj"), ("nastavitve", "nastavitve"), ("zapisek", "zapisek")]
        vnosi = [(self._t(k), d) for k, d in vnosi]
        p = self.trenutni()
        g = splet_temno.gostitelj(p.get_uri() if p else "")
        if g and splet_temno.dejaven(self._temno_nacin(), self._namizje_temno()):
            jezik = str(self.jezik() if callable(self.jezik) else self.jezik or "sl")
            kljuc = "na_strani_vklopi" if g in self._temno_izjeme() else "na_strani_izklopi"
            vnosi.insert(-2, (splet_temno.besedilo(jezik, kljuc), "temno"))
        for napis, dejanje in vnosi:
            meni.append(napis, "splet." + dejanje)
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
        # WebKitGTK 6.0: kontekst (procesi strani, meja pomnilnika) in omrezna seja (podatki, piskotki) sta locena.
        pogled = W.WebView(web_context=self.kontekst, network_session=self.seja)
        # Padec spletnega procesa (sesutje strani, pomanjkanje pomnilnika): zavihek se nalozi znova, kot v brskalniku.
        pogled.connect("web-process-terminated", self._proces_pomnilnik)   # pred obnovo (ta caka 400 ms)
        os_stabilnost.obnovi_ob_padcu(W, self.GLib, pogled, "safeer-os", "splet", ob_odpovedi=self._proces_koncan)
        upravitelj = pogled.get_user_content_manager()
        registriraj_most(upravitelj, "safeer")
        # Sibka referenca (glej drm.prikljuci): sicer zaprt zavihek nikoli ne sprosti svojega WebView.
        ref = weakref.ref(pogled)
        upravitelj.connect("script-message-received::safeer",
                           lambda _u, r: ref() is not None and self._sporocilo(ref(), r))
        # Stevec scita v locenem svetu: stran v glavnem svetu tega rokovalnika ne doseze.
        registriraj_most(upravitelj, adblock.STEVEC_MOST, adblock.STEVEC_SVET)
        upravitelj.connect("script-message-received::" + adblock.STEVEC_MOST, lambda _u, r: self._stevec(r))
        odlozisce_varuh.dodaj(W, upravitelj)   # tudi na prijavnih straneh: nicesar ne spreminja, le varuje odlozisce
        # Widevine (Netflix, Disney+ ...): stran se odpre v namescenem brskalniku z Widevine (core/drm.py).
        if getattr(self, "_drm", None) is None:
            self._drm = drm.Preusmeritev()
        drm.prikljuci(W, pogled, self._drm, lambda: str(self.jezik() if callable(self.jezik) else self.jezik or "sl"),
                      vdelaj=self._drm_vdelaj)
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
        nastavi_kompozitor(W, nastavitve, self._skia())
        nastavitve.set_hardware_acceleration_policy(getattr(self, "_naslednja_politika", None)
                                                    or politika_pospesevanja(W, self.config.get("hardware_acceleration", "on_demand")))
        # Vsaka nastavitev posebej: WebKitGTK 6.0 je nekatere odstranil (npr. html5_database, dns_prefetching).
        # Predpomnilnik strani (bfcache): "Nazaj" brez ponovnega nalaganja. Meritev 13. 10. 2026 (testni PC, 4 strani):
        # nazaj ~0,3-0,4 s namesto ~1,2 s, RAM spletnih procesov +50 MB (~7 %); ob pomanjkanju ga WebKit sprosti sam.
        for ime, vrednost in (("enable_javascript", True), ("enable_javascript_markup", True),
                              ("javascript_can_open_windows_automatically", False), ("enable_html5_local_storage", True),
                              ("enable_html5_database", False),
                              ("enable_dns_prefetching", False), ("enable_page_cache", True),
                              ("enable_encrypted_media", True)):
            nastavi = getattr(nastavitve, "set_" + ime, None)
            if nastavi is not None:
                try:
                    nastavi(vrednost)
                except Exception:  # noqa: BLE001
                    pass
        # Temno pod našo začetno stranjo, belo pod spletom - belo mora biti nastavljeno, preden dokument strani nastane.
        ozadje_strani.prikljuci(self.Gdk, W, pogled, os.path.join(self.koren, "ui"), TEMNO_OZADJE)
        pogled.connect("decide-policy", self._politika)
        self._tipke(pogled, lambda e: self.tipka(e))
        self._klik(pogled, lambda gumb, x, y, p: self._miska(p, _Klik(gumb, x, y)))
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
        vrstica.add_css_class("splet-tab")
        ikona = self.Gtk.Label(label="🌐")
        naslov_lbl = self.Gtk.Label(label=self._t("nov")); naslov_lbl.set_ellipsize(self.Pango.EllipsizeMode.END)
        naslov_lbl.set_xalign(0); naslov_lbl.set_hexpand(True)
        zapri = self._gumb("×", lambda *_: self.zapri_zavihek(pogled), "tab-close")
        vrstica.append(ikona); vrstica.append(naslov_lbl); vrstica.append(zapri)
        # GTK4: ni EventBox; klik na zavihek ujame GestureClick na sami vrstici (gumb × ostane svoj).
        dogodek = vrstica
        self._klik(vrstica, lambda *_: self.izberi(pogled), 1)
        self.skatla_zavihkov.append(vrstica)
        pogled.set_vexpand(True); pogled.set_hexpand(True)
        self.sklad.add_named(pogled, "splet-%d" % self._stevec)
        zavihek = {"pogled": pogled, "dogodek": dogodek, "vrstica": vrstica, "naslov": naslov_lbl, "ikona": ikona}
        self.zavihki.append(zavihek)
        self.izberi(pogled)
        self.odpri(naslov, pogled)
        return pogled

    def zapri_zavihek(self, pogled):
        if len(self.zavihki) == 1:
            self.odpri_domov(); return
        z = next((x for x in self.zavihki if x["pogled"] is pogled), None)
        if z is None: return
        self._zapomni_zaprt(pogled)
        indeks = self.zavihki.index(z); self.zavihki.remove(z)
        self._drm_konec(z)
        self.skatla_zavihkov.remove(z["dogodek"]); self.sklad.remove(pogled)
        try:
            _unici_pogled(pogled)
        except Exception:  # noqa: BLE001
            pass
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
                           bool(stanje & Gdk.ModifierType.SHIFT_MASK), bool(stanje & Gdk.ModifierType.ALT_MASK))
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
        d, obmocje = self._dialog(self._t(kaj), 720, 560)
        iskanje = Gtk.SearchEntry(); iskanje.set_margin_start(12); iskanje.set_margin_end(12)
        zvezki = Gtk.Notebook(); zvezki.set_vexpand(True)
        seznami = {}
        for kljuc in ("zaznamki", "zgodovina"):
            okvir = Gtk.ScrolledWindow(); okvir.set_vexpand(True)
            sez = Gtk.ListBox(); sez.set_activate_on_single_click(True)
            sez.connect("row-activated", lambda _s, vrstica: (self.nov_zavihek(vrstica.naslov), d.destroy()))
            okvir.set_child(sez); zvezki.append_page(okvir, Gtk.Label(label=self._t(kljuc))); seznami[kljuc] = sez
        def napolni(*_):
            niz = iskanje.get_text()
            viri = {"zaznamki": [{"title": p.get("title", ""), "url": p.get("url", "")} for p in self.config.get_portals()],
                    "zgodovina": zgodovina.nalozi(os.path.join(self.config.config_dir, "history.json"))}
            for kljuc, sez in seznami.items():
                _ocisti(sez)
                zadetki = [z for z in zgodovina.isci(viri[kljuc], niz) if z.get("url")][:300]
                for z in zadetki:
                    vrstica = Gtk.ListBoxRow(); vrstica.naslov = z["url"]
                    skatla = _robovi(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2), 8)
                    a = Gtk.Label(label=z.get("title") or z["url"], xalign=0); a.set_ellipsize(self.Pango.EllipsizeMode.END)
                    b = Gtk.Label(label=(z.get("time", "") + "  " + z["url"]).strip(), xalign=0)
                    b.set_ellipsize(self.Pango.EllipsizeMode.END)
                    b.add_css_class("dim-label")
                    skatla.append(a); skatla.append(b)
                    vrstica.set_child(skatla); sez.append(vrstica)
                if not zadetki:
                    sez.append(_robovi(Gtk.Label(label=self._t("prazno")), 16))
        iskanje.connect("search-changed", napolni)
        iskanje.set_margin_top(6); iskanje.set_margin_bottom(6)
        obmocje.append(iskanje); obmocje.append(zvezki)
        napolni()
        d.present()
        zvezki.set_current_page(0 if kaj == "zaznamki" else 1)
        iskanje.grab_focus()

    def _dialog(self, naslov: str, sirina: int = 480, visina: int = -1, gumbi=None):
        """GTK4 dialog (Gtk.Dialog je opuscen): okno nad Spletom z obmocjem in vrstico gumbov.

        gumbi: [(napis, odgovor)]; ob kliku se poklice d.odgovor(odgovor) (privzeto zapre okno). Vrne (okno, obmocje)."""
        Gtk = self.Gtk
        d = Gtk.Window(title=naslov, modal=True)
        stars = self._okno_za_dialog()
        if stars is not None:
            try:
                d.set_transient_for(stars)
            except Exception:  # noqa: BLE001
                pass
        d.set_default_size(sirina, visina)
        d.set_destroy_with_parent(True)
        glavna = _robovi(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8), 12)
        obmocje = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        obmocje.set_vexpand(True)
        glavna.append(obmocje)
        vrstica = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        vrstica.set_halign(Gtk.Align.END)
        glavna.append(vrstica)
        d.odgovor = lambda _o: d.destroy()
        for napis, odgovor in (gumbi or [(self._t("zapri"), Gtk.ResponseType.CLOSE)]):
            g = Gtk.Button(label=napis)
            g.connect("clicked", lambda _g, o=odgovor: d.odgovor(o))
            vrstica.append(g)
        d.set_child(glavna)
        k = Gtk.EventControllerKey()
        k.connect("key-pressed", lambda _k, keyval, *_: (keyval == self.Gdk.KEY_Escape and (d.destroy() or True)))
        d.add_controller(k)
        return d, obmocje

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
        d, obmocje = self._dialog(self._t("uvozi").rstrip(" …"))
        if viri or zavihki:
            obmocje.append(Gtk.Label(label=self._t("uvoz_zaznamki", n=dodanih, od=", ".join(viri) or "-"),
                                     xalign=0, margin_top=12))
        else:
            obmocje.append(_robovi(Gtk.Label(label=self._t("uvoz_brez")), 16))
        for ime, naslovi in zavihki.items():
            gumb = Gtk.Button(label=self._t("uvoz_zavihki", n=len(naslovi), ime=ime))
            gumb.connect("clicked", lambda _g, n=naslovi: ([self.nov_zavihek(x) for x in n], d.destroy()))
            obmocje.append(gumb)
        d.present()
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
            self.podatki().clear(
                W.WebsiteDataTypes.DISK_CACHE | W.WebsiteDataTypes.MEMORY_CACHE, 0, None,
                (lambda *_: ob_koncu()) if ob_koncu else None, None)
        except Exception as napaka:  # noqa: BLE001
            print("[Safeer OS Splet] predpomnilnik:", napaka)

    def _predpomnilnik(self) -> None:
        """Upravitelj predpomnilnika: velikost, ciscenje predpomnilnika (prijave ostanejo), podatki po straneh, meja."""
        Gtk, W = self.Gtk, self.WebKit2
        upr = self.podatki()
        d, obmocje = self._dialog(self._t("predpomnilnik"), 640, 560)
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
        obmocje.append(napis); obmocje.append(pocisti)
        obmocje.append(samodejno)
        obmocje.append(Gtk.Label(label=self._t("pp_strani"), xalign=0, margin_top=8))
        iskanje = Gtk.SearchEntry(); iskanje.set_placeholder_text(self._t("pp_iskanje"))
        obmocje.append(iskanje)
        okvir = Gtk.ScrolledWindow(); okvir.set_vexpand(True)
        seznam = Gtk.ListBox(); okvir.set_child(seznam); obmocje.append(okvir)
        vrste = W.WebsiteDataTypes.ALL if hasattr(W.WebsiteDataTypes, "ALL") else (
            W.WebsiteDataTypes.COOKIES | W.WebsiteDataTypes.LOCAL_STORAGE | W.WebsiteDataTypes.INDEXEDDB_DATABASES
            | W.WebsiteDataTypes.DISK_CACHE)
        podatki = []
        def izrisi(*_):
            _ocisti(seznam)
            niz = iskanje.get_text().strip().lower()
            for wd in sorted(podatki, key=lambda x: x.get_name() or ""):
                ime = wd.get_name() or ""
                if niz and niz not in ime.lower():
                    continue
                vrstica = _robovi(Gtk.Box(spacing=8), 6)
                oznaka = Gtk.Label(label=ime, xalign=0); oznaka.set_hexpand(True)
                vrstica.append(oznaka)
                gumb = Gtk.Button(label=self._t("pp_odstrani"))
                def odstrani(_g, wd=wd):
                    upr.remove(vrste, [wd], None, lambda *_: (podatki.remove(wd), izrisi(), osvezi_napis()), None)
                gumb.connect("clicked", odstrani)
                vrstica.append(gumb)
                seznam.append(vrstica)
        def prejeto(m, rezultat, *_):
            try:
                podatki[:] = list(m.fetch_finish(rezultat) or [])
            except Exception as napaka:  # noqa: BLE001
                print("[Safeer OS Splet] podatki strani:", napaka)
            izrisi()
        upr.fetch(vrste, None, prejeto, None)
        iskanje.connect("search-changed", izrisi)
        d.present()

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
                _unici_pogled(z["pogled"])
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
            upr = self.podatki()
            upr.clear(self.WebKit2.WebsiteDataTypes.MEMORY_CACHE, 0, None, None, None)
            return True
        except Exception:  # noqa: BLE001 - starejsi WebKit brez tega: ostane sprostitev po minuti
            return False

    def izberi(self, pogled):
        self.aktivni = pogled; self.sklad.set_visible_child(pogled)
        z = self._zavihek(pogled)
        if z is not None and z.get("drm") is not None:
            self.sklad.set_visible_child(z["drm"].gradnik)
        for z in self.zavihki:
            if z["pogled"] is pogled:
                z["vrstica"].add_css_class("splet-tab-aktiven")
            else:
                z["vrstica"].remove_css_class("splet-tab-aktiven")
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
            # Stran s seznama puscanja: nov pogled z drugim izrisom - sele za Scitom in BankGuardom.
            if self._zamenjaj_za_pospesevanje(pogled, naslov):
                odlocitev.ignore(); return True
            odlocitev.use(); return True
        except Exception:
            odlocitev.ignore(); return True

    def _novo_okno(self, _pogled, dejanje):
        # WebKitGTK 6.0 zahteva, da je vrnjen pogled »related-view« izvornega; nas zavihek ima svoje nastavitve in
        # skripte, zato stran odpremo v novem zavihku in WebKitu ne vrnemo pogleda (window.open ostane brez opener).
        try: naslov = dejanje.get_request().get_uri() or ""
        except Exception: naslov = ""
        if naslov:
            self.nov_zavihek(naslov)
        return None

    def _ucene_brez_pospesevanja(self) -> list:
        return ucene_brez_pospesevanja(self.config)

    def _skia(self) -> bool:
        """Skia kompozitor samo, ce ga uporabnik izrecno vklopi (splet_skia_kompozitor); privzeto TextureMapper."""
        return bool(self.config.get("splet_skia_kompozitor", False))

    def _zelena_politika(self, naslov: str):
        W = self.WebKit2
        if brez_pospesevanja(naslov, self._ucene_brez_pospesevanja(), self._skia()):
            return W.HardwareAccelerationPolicy.NEVER
        return politika_pospesevanja(W, self.config.get("hardware_acceleration", "on_demand"))

    def _zamenjaj_za_pospesevanje(self, pogled, naslov: str) -> bool:
        """Stran potrebuje drugacen strojni izris kot ta zavihek (seznam puscanja): WebKit 2.54 pogleda, ki mu izris
        zamenjamo med zivljenjem, ne izrise vec (crno okno, preverjeno 13. 10. 2026), zato zavihek na istem mestu
        zamenjamo z novim pogledom, ki ima pravi izris ze ob nastanku, in vanj nalozimo stran. True = zamenjano."""
        try:
            zelena = self._zelena_politika(naslov)
            if pogled.get_settings().get_hardware_acceleration_policy() == zelena:
                return False
        except Exception:  # noqa: BLE001
            return False
        star = next((x for x in self.zavihki if x["pogled"] is pogled), None)
        if star is None:
            return False
        indeks = self.zavihki.index(star)
        self._naslednja_politika = zelena
        try:
            nov = self.nov_zavihek(naslov)
        finally:
            self._naslednja_politika = None
        z = next((x for x in self.zavihki if x["pogled"] is nov), None)
        if z is not None:
            self.zavihki.remove(z); self.zavihki.insert(indeks, z)
            try:
                prej = self.zavihki[indeks - 1]["dogodek"] if indeks > 0 else None
                self.skatla_zavihkov.reorder_child_after(z["dogodek"], prej)
            except Exception:  # noqa: BLE001
                pass
        if star in self.zavihki:
            self.zavihki.remove(star)
            try:
                self.skatla_zavihkov.remove(star["dogodek"]); self.sklad.remove(pogled); _unici_pogled(pogled)
            except Exception:  # noqa: BLE001
                pass
        self.izberi(nov)
        return True

    def _varuh_tik(self) -> bool:
        try:
            from core import pomnilnik, splet_varuh
            # 3/4 meje WebKita: pri puscanju DMA-BUF WebKit proces sprazni in spet napolni (meritev: 0,4 -> 2,8 GB v
            # krogih po ~30 s, brez ustavitve), zato varuh ukrepa nizje, ko je to ze zanesljivo puscanje.
            pid = splet_varuh.preglej(pomnilnik.meja_strani_mb() * 3 // 4, os.getpid(), bool(os.environ.get("FLATPAK_ID")))
            if pid is not None:
                self._varuh_ubil = time.monotonic()
                os_stabilnost.zapisi("safeer-os", "spletni proces nad mejo pomnilnika ustavljen (varuh)")
        except Exception as napaka:  # noqa: BLE001 - varuh ne sme podreti Spleta
            print("[Safeer OS Splet] varuh:", napaka)
        return True

    def _proces_pomnilnik(self, pogled, razlog) -> None:
        """Stran je presegla mejo pomnilnika (ustavil jo je WebKit ali nas varuh): njeno domeno si zapomnimo (brez
        strojnega izrisa), da jo os_stabilnost nalozi znova ze brez puscanja."""
        ucene = nauci_po_padcu(self.WebKit2, razlog, pogled.get_uri() or "", self._ucene_brez_pospesevanja(),
                               self._skia(), time.monotonic() - getattr(self, "_varuh_ubil", -1e9))
        if ucene is None:
            return
        try:
            self.config.set("splet_brez_pospesevanja", ucene)
        except Exception:  # noqa: BLE001
            pass
        uri = pogled.get_uri() or ""
        # Namesto ponovnega nalaganja istega pogleda (os_stabilnost) nov zavihek z izrisom brez pospesevanja.
        self.GLib.idle_add(lambda: (self._zamenjaj_za_pospesevanje(pogled, uri), False)[1])

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
        pogled.evaluate_javascript("window.safeerSpletInit(%s);" % json.dumps(stanje, ensure_ascii=True), -1,
                                   None, None, None, None, None)
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
        z = self._zavihek(pogled)
        if z is not None and z.get("drm") is not None:
            # Uporabnik je sel drugam (Nazaj, nov naslov, Domov): zasciten video se konca, zavihek spet kaze Splet.
            if _gostitelj(pogled.get_uri() or "") != _gostitelj(z["drm"].url):
                self._drm_konec(z)
        if pogled is self.trenutni(): self._osvezi_orodja()

    # ------------------------------------------------------------------ Safeer DRM (Widevine) v zavihku
    def _zavihek(self, pogled):
        return next((x for x in self.zavihki if x["pogled"] is pogled), None)

    def _osvezi_trenutni(self) -> None:
        z = self._zavihek(self.trenutni())
        if z is not None and z.get("drm") is not None:
            z["drm"].ukaz("reload")
        elif self.trenutni():
            self.trenutni().reload()

    def _drm_vdelaj(self, pogled, url: str) -> bool:
        """Stran je zaprosila za Widevine: ista stran v Safeer DRM, vstavljenem v ta zavihek."""
        z = self._zavihek(pogled)
        if z is None or not url.startswith("https://"):
            return False
        if z.get("drm") is not None and _gostitelj(z["drm"].url) == _gostitelj(url):
            return True                           # stran vprasa veckrat zapored
        if not safeer_drm.Gostitelj.na_voljo():
            if z.get("drm_prenos"):
                return True
            z["drm_prenos"] = True
            # Prvic: paket se prenese (enkrat). Do takrat stran ostane, potem se zavihek sam preklopi.
            self._drm_obvestilo(pogled, "pripravljam")
            def koncano(uspeh: bool, z=z, url=url):
                def v_gui():
                    z["drm_prenos"] = False
                    if z in self.zavihki and (z["pogled"].get_uri() or "") == url:
                        if not (uspeh and self._drm_vdelaj(z["pogled"], url)):
                            self._drm.odpri(url)  # rezerva: brskalnik z Widevine
                    return False
                self.GLib.idle_add(v_gui)
            safeer_drm.prenesi_v_ozadju(koncano)
            return True
        gost = safeer_drm.Gostitelj(self.Gtk, self.Gdk, self.GLib, ob_celozaslonu=self._drm_celozaslonsko,
                                    ob_koncu=lambda z=z: self._drm_konec(z))
        self._tipke(gost.gradnik, lambda e, gost=gost: self.tipka(e) or gost.tipka(e))
        self.sklad.add_named(gost.gradnik, "drm-%d" % id(gost))
        z["drm"] = gost
        if pogled is self.trenutni():
            self.sklad.set_visible_child(gost.gradnik)
        if not gost.zacni(url, storitev=safeer_drm.je_storitev(url)):
            self._drm_konec(z)
            return False
        try:
            pogled.set_is_muted(True)            # stran v Spletu (brez Widevine) naj ne igra zraven
        except Exception:  # noqa: BLE001 - starejsi WebKitGTK
            pass
        return True

    def koncaj_drm(self) -> None:
        """Zaprtje okna (Safeer Browser): konca Safeer DRM v vseh zavihkih. Preizkus 14. 10. na testnem PC: brez tega
        je okno izginilo, proces safeer-drm na gostitelju (flatpak-spawn --watch-bus) pa je ostal in drzal Flatpak."""
        for z in list(self.zavihki):
            try:
                self._drm_konec(z)
            except Exception as e:  # noqa: BLE001 - zaprtje mora uspeti
                print("[Splet] DRM konec:", e, flush=True)

    def _drm_konec(self, z) -> None:
        gost = z.get("drm") if z else None
        if gost is None:
            return
        z["drm"] = None
        self._drm_celozaslonsko(False)
        gost.unici()
        try:
            self.sklad.remove(gost.gradnik)
        except Exception:  # noqa: BLE001
            pass
        try:
            z["pogled"].set_is_muted(False)
        except Exception:  # noqa: BLE001
            pass
        if z["pogled"] is self.trenutni():
            self.sklad.set_visible_child(z["pogled"])

    def _drm_celozaslonsko(self, vklopi: bool) -> None:
        okno = self.gradnik.get_root()
        for g in (self.vrstica_zavihkov, getattr(self, "orodja", None)):
            if g is not None:
                g.set_visible(not vklopi)
        if okno is not None and hasattr(okno, "fullscreen"):
            (okno.fullscreen if vklopi else okno.unfullscreen)()

    def _drm_obvestilo(self, pogled, kljuc: str) -> None:
        besedila = {"sl": "Pripravljam predvajalnik zaščitenih vsebin (enkrat) …",
                    "en": "Preparing the protected video player (one time) …"}
        jezik = str(self.jezik() if callable(self.jezik) else self.jezik or "sl")[:2]
        koda = drm.OBVESTILO.replace("__BESEDILO__", json.dumps(besedila.get(jezik, besedila["en"])))
        try:
            pogled.evaluate_javascript(koda, -1, None, None, None, None, None)
        except Exception:  # noqa: BLE001
            pass

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
            vrednost = _js_vrednost(rezultat).to_json(0)
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
            s = adblock.preveri_stevec(json.loads(_js_vrednost(rezultat).to_json(0)))
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
        Gtk = self.Gtk
        R = Gtk.ResponseType
        d, obmocje = self._dialog(self._t("dodaj"), gumbi=[(self._t("preklici"), R.CANCEL), (self._t("shrani"), R.OK)])
        mreza = _robovi(Gtk.Grid(column_spacing=10, row_spacing=8), 4)
        ime, url = Gtk.Entry(), Gtk.Entry(); url.set_text("https://"); url.set_hexpand(True)
        mreza.attach(Gtk.Label(label=self._t("ime"), xalign=0), 0, 0, 1, 1); mreza.attach(ime, 1, 0, 1, 1)
        mreza.attach(Gtk.Label(label=self._t("url"), xalign=0), 0, 1, 1, 1); mreza.attach(url, 1, 1, 1, 1)
        obmocje.append(mreza)

        def odgovor(o):
            if o == R.OK:
                naslov = normalize_web_url(url.get_text())
                if naslov:
                    self.config.add_portal(ime.get_text().strip() or urllib.parse.urlparse(naslov).hostname, naslov)
                    # Znova dodana bliznjica ni vec med odstranjenimi.
                    self.config.set("splet_skrite_bliznjice", [k for k in (self.config.get("splet_skrite_bliznjice", []) or [])
                                                               if k != kljuc_bliznjice(naslov)])
            d.destroy()
            p = self.trenutni()
            if p and je_domaca_stran(p.get_uri() or "", self.koren): p.reload()
        d.odgovor = odgovor
        d.present()

    def dodaj_trenutno(self):
        p = self.trenutni(); uri = p.get_uri() if p else ""
        if not uri or je_domaca_stran(uri, self.koren): return
        self.config.add_portal(p.get_title() or urllib.parse.urlparse(uri).hostname or uri, uri)
        if self._ima_ikono("starred-symbolic"):
            self.zvezdica.set_icon_name("starred-symbolic")
        else:
            self.zvezdica.set_label("★")

    def osvezi_povezavo(self):
        if self.stanje_povezave is None:   # samostojni Safeer Browser (safeer_brskalnik.py): brez oznake Linka
            self.povezava.set_visible(False)
            return False
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
        pogled.evaluate_javascript(skripta, -1, "safeer-bankguard", None, None, self._bank_signali, (pogled, uri))

    def _bank_signali(self, pogled, rezultat, podatki):
        pogled0, uri = podatki
        try: signali = json.loads(_js_vrednost(pogled.evaluate_javascript_finish(rezultat)).to_json(0) or "null")
        except Exception: return
        if pogled0.get_uri() != uri: return
        sodba = adblock.fake_bank_page_verdict(uri, signali)
        if sodba is not None: self._opozorilo_bank(pogled0, uri, sodba, True)

    def _vprasaj(self, naslov: str, opis: str, gumbi, ob_odgovoru=None) -> None:
        """GTK4 Gtk.AlertDialog (asinhrono; GTK3 MessageDialog.run je odstranjen). ob_odgovoru(indeks gumba ali -1)."""
        d = self.Gtk.AlertDialog()
        d.set_message(naslov)
        if opis:
            d.set_detail(opis)
        d.set_buttons(list(gumbi))
        d.set_modal(True)
        d.set_cancel_button(0)

        def koncano(dialog, rezultat, *_):
            try:
                i = dialog.choose_finish(rezultat)
            except Exception:  # noqa: BLE001 - zaprto brez izbire
                i = -1
            if ob_odgovoru is not None:
                ob_odgovoru(i)
        d.choose(self._okno_za_dialog(), None, koncano, None)

    def _opozorilo_bank(self, pogled, uri, sodba, nalozen=False):
        gumbi = [self._t("nazaj")] + ([sodba.official_domain] if sodba.official_domain else [])

        def odgovor(i):
            if i == 1 and sodba.official_domain: pogled.load_uri("https://" + sodba.official_domain + "/")
            elif nalozen: pogled.go_back() if pogled.can_go_back() else pogled.load_uri(self.domaci_uri())
        self._vprasaj("Safeer Shield · BankGuard", adblock.fake_bank_warning_text(sodba, self.jezik()), gumbi, odgovor)

    def _opozorilo(self, naslov, opis):
        self._vprasaj(naslov, opis, [self._t("zapri")])

    def _dovoljenje(self, _pogled, zahteva):
        pravilo = self.config.get("permissions_policy", "ask")
        if pravilo == "allow":
            zahteva.allow(); return True
        if pravilo == "deny":
            zahteva.deny(); return True
        # Zahteva ostane odprta, dokler uporabnik ne odgovori (WebKit to dovoli, ce signal vrne True).
        self._vprasaj(self._t("dovoljenje"), "", [self._t("zavrni"), self._t("dovoli")],
                      lambda i: zahteva.allow() if i == 1 else zahteva.deny())
        return True

    # ---------------------------------------------------------------- prenosi (core/splet_prenosi.py)
    def _prenos_zacet(self, _kontekst, prenos):
        """14. 10. 2026: prej ~/Downloads (na slovenskem namizju je »Prejemi«), ime iz naslova, prepis obstojece
        datoteke in programi brez potrditve. Zdaj kot Safeer Browser: mapa XDG, ime iz glave, (1), potrditev programa."""
        prenos.connect("decide-destination", self._prenos_cilj)

    def _prenos_cilj(self, prenos, predlagano):
        uri = ""
        try:
            uri = prenos.get_request().get_uri() or ""
        except Exception:  # noqa: BLE001
            pass
        ime = splet_prenosi.ime_prenosa(predlagano, uri)
        mapa = splet_prenosi.mapa_prenosov(self.GLib)
        self._pospravi_zavihek_prenosa(prenos)
        if not splet_prenosi.je_izvrsljiv_prenos(ime):
            self._prenos_v(prenos, splet_prenosi.edinstvena_pot(mapa, ime))
            return True
        # Program ali namestitveni paket: stran ga ne sme podtakniti ob obisku. Prenos caka na odgovor (WebKit:
        # cilj se lahko nastavi kasneje, ce signal vrne True).
        def odgovor(i):
            if i == 1:
                self._prenos_v(prenos, splet_prenosi.edinstvena_pot(mapa, ime))
            else:
                prenos.cancel()
        self._vprasaj(self._t("pr_program"), self._t("pr_program_opis").format(ime=ime, mapa=_kratka_pot(mapa)),
                      [self._t("pr_preklici"), self._t("pr_prenesi")], odgovor)
        return True

    def _pospravi_zavihek_prenosa(self, prenos):
        """Povezava na datoteko iz drugega programa ali target=_blank odpre zavihek, ki ostane prazen (preizkus
        14. 10.: »Nov zavihek« za namesti.sh). Zavihek brez lastne strani zapremo, kot safeer_mint.py."""
        try:
            pogled = prenos.get_web_view()
        except Exception:  # noqa: BLE001
            pogled = None
        if pogled is None or len(self.zavihki) < 2:
            return
        if not any(z["pogled"] is pogled for z in self.zavihki):
            return
        try:
            prazen = pogled.get_back_forward_list().get_current_item() is None
        except Exception:  # noqa: BLE001
            prazen = False
        if prazen:
            self.GLib.idle_add(lambda: self.zapri_zavihek(pogled) and False)

    def _prenos_v(self, prenos, pot):
        je6 = hasattr(self.WebKit2, "NetworkSession")   # WebKitGTK 6.0: cilj je pot (4.1: URI)
        prenos.set_destination(pot if je6 else self.GLib.filename_to_uri(pot, None))
        zapis = splet_prenosi.nov_zapis(pot)
        zapis["prenos"] = prenos
        self.prenosi.insert(0, zapis)
        del self.prenosi[50:]

        def napredek(*_):
            zapis["napredek"] = prenos.get_estimated_progress()
            self._osvezi_prenose()

        def konec(*_):
            if zapis["stanje"] == "tece":
                zapis["stanje"], zapis["napredek"] = "koncan", 1.0
            zapis.pop("prenos", None)
            self._osvezi_prenose()

        def napaka(_p, err):
            preklic = getattr(self.WebKit2, "DownloadError", None)
            zapis["stanje"] = ("preklican" if preklic is not None and getattr(err, "code", None)
                               == int(preklic.CANCELLED_BY_USER) else "napaka")
            self._osvezi_prenose()
        prenos.connect("notify::estimated-progress", napredek)
        prenos.connect("failed", napaka)
        prenos.connect("finished", konec)
        self._osvezi_prenose()

    def _osvezi_prenose(self):
        """Gumb prenosov v orodni vrstici: viden samo, ko so prenosi; med prenosom kaze odstotek."""
        g = getattr(self, "gumb_prenosov", None)
        if g is None:
            return
        tecejo = [z for z in self.prenosi if z["stanje"] == "tece"]
        g.set_visible(bool(self.prenosi))
        if tecejo:
            pct = int(min(float(z.get("napredek") or 0) for z in tecejo) * 100)
            g.set_label("⬇ %d %%" % pct)
        else:
            g.set_label("⬇")
        g.set_tooltip_text(self._t("prenosi"))
        okno = getattr(self, "_okno_prenosov", None)
        if okno is not None:
            self._napolni_prenose()

    def _pokazi_prenose(self, *_):
        if getattr(self, "_okno_prenosov", None) is not None:
            self._okno_prenosov.present(); return
        Gtk = self.Gtk
        d, obmocje = self._dialog(self._t("prenosi"), 560, 420, gumbi=[(self._t("pr_zapri"), Gtk.ResponseType.CLOSE)])
        glava = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        mapa = Gtk.Button(label=self._t("pr_mapa"))
        mapa.connect("clicked", lambda *_: self._odpri_datoteko(splet_prenosi.mapa_prenosov(self.GLib)))
        glava.append(mapa)
        obmocje.append(glava)
        drsnik = Gtk.ScrolledWindow(vexpand=True)
        self._seznam_prenosov = Gtk.ListBox()
        self._seznam_prenosov.set_selection_mode(Gtk.SelectionMode.NONE)
        drsnik.set_child(self._seznam_prenosov)
        obmocje.append(drsnik)
        self._okno_prenosov = d
        d.connect("destroy", lambda *_: setattr(self, "_okno_prenosov", None))
        self._napolni_prenose()
        d.present()

    def _napolni_prenose(self):
        Gtk, sez = self.Gtk, getattr(self, "_seznam_prenosov", None)
        if sez is None:
            return
        while sez.get_first_child() is not None:
            sez.remove(sez.get_first_child())
        if not self.prenosi:
            sez.append(Gtk.Label(label=self._t("pr_ni"), margin_top=20))
            return
        for z in self.prenosi:
            vrstica = _robovi(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10), 6)
            opis = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)
            ime = Gtk.Label(label=z["ime"], xalign=0)
            ime.set_ellipsize(3)  # Pango.EllipsizeMode.END
            opis.append(ime)
            stanje = Gtk.Label(label=z["cas"] + " · " + splet_prenosi.opis_stanja(z, self._t), xalign=0)
            stanje.add_css_class("dim-label")
            opis.append(stanje)
            vrstica.append(opis)
            if z["stanje"] == "tece" and z.get("prenos") is not None:
                g = Gtk.Button(label=self._t("pr_preklici"))
                g.connect("clicked", lambda _g, p=z["prenos"]: p.cancel())
                vrstica.append(g)
            elif z["stanje"] == "koncan" and os.path.exists(z["pot"]):
                g = Gtk.Button(label=self._t("pr_odpri"))
                g.connect("clicked", lambda _g, p=z["pot"]: self._odpri_datoteko(p))
                vrstica.append(g)
            sez.append(vrstica)

    def _odpri_datoteko(self, pot):
        """Gtk.FileLauncher (GTK 4.10+): v Flatpaku gre prek portala, zunaj prek privzetega programa."""
        try:
            self.Gtk.FileLauncher.new(self.Gio.File.new_for_path(pot)).launch(self._okno_za_dialog(), None, None, None)
        except Exception as napaka:  # noqa: BLE001
            print("[Splet] odpri prenos:", napaka, flush=True)

    def _pokazi_najdi(self): self.najdi_vrstica.set_search_mode(True); self.najdi_vnos.grab_focus()
    def _najdi(self, vnos):
        if self.trenutni(): self.trenutni().get_find_controller().search(vnos.get_text(), 0, 1000)
    def _povecava(self, korak):
        if self.trenutni(): self.trenutni().set_zoom_level(max(.5, min(3.0, self.trenutni().get_zoom_level() + korak)))
    def _nastavitve(self, *_):
        Gtk = self.Gtk
        R = Gtk.ResponseType
        d, obmocje = self._dialog(self._t("nastavitve"), gumbi=[(self._t("preklici"), R.CANCEL), (self._t("shrani"), R.OK)])
        mreza = _robovi(Gtk.Grid(column_spacing=12, row_spacing=12), 6)
        motor = Gtk.ComboBoxText()
        for kljuc, podatki in SEARCH_ENGINES.items(): motor.append(kljuc, podatki["name"])
        motor.set_active_id(self.config.get("search_engine", "duckduckgo"))
        oglasi = Gtk.CheckButton(label=self._t("adblock")); oglasi.set_active(self.config.get("adblock_enabled", True))
        doh = Gtk.CheckButton(label=self._t("doh")); doh.set_active(self.config.get("doh_enabled", True))
        strojno = Gtk.CheckButton(label=self._t("strojno"))
        strojno.set_active(self.config.get("hardware_acceleration", "on_demand") != "never")
        mreza.attach(Gtk.Label(label=self._t("iskalnik"), xalign=0), 0, 0, 1, 1); mreza.attach(motor, 1, 0, 1, 1)
        mreza.attach(oglasi, 0, 1, 2, 1); mreza.attach(doh, 0, 2, 2, 1); mreza.attach(strojno, 0, 3, 2, 1)
        jezik = str(self.jezik() if callable(self.jezik) else self.jezik or "sl")
        temno = Gtk.ComboBoxText()
        for n in splet_temno.NACINI: temno.append(n, splet_temno.besedilo(jezik, n))
        temno.set_active_id(self._temno_nacin())
        mreza.attach(Gtk.Label(label=splet_temno.besedilo(jezik, "nastavitev"), xalign=0), 0, 4, 1, 1)
        mreza.attach(temno, 1, 4, 1, 1)
        obmocje.append(mreza)

        def odgovor(o):
            if o == R.OK:
                self.config.set("search_engine", motor.get_active_id() or "duckduckgo")
                self.config.set("adblock_enabled", oglasi.get_active())
                self.config.set("doh_enabled", doh.get_active())
                self.config.set("hardware_acceleration", "on_demand" if strojno.get_active() else "never")
                if (temno.get_active_id() or splet_temno.PRIVZETO) != self._temno_nacin():
                    self.config.set("temno_nacin", temno.get_active_id() or splet_temno.PRIVZETO)
                    self._temno_osvezi(znova_nalozi=self.trenutni())
                politika = politika_pospesevanja(self.WebKit2, self.config.get("hardware_acceleration"))
                for z in self.zavihki:
                    if not brez_pospesevanja(z["pogled"].get_uri() or "", self._ucene_brez_pospesevanja(), self._skia()):
                        z["pogled"].get_settings().set_hardware_acceleration_policy(politika)
                self._nastavi_omrezje()
            d.destroy()
        d.odgovor = odgovor
        d.present()

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
