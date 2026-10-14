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

from core import (adblock, dovoljenja_strani, drm, odlozisce_varuh, os_stabilnost, ozadje_strani, pojavna_okna,
                  safeer_drm, splet_prenosi, splet_temno, zascita)
from core.config import ConfigManager, SEARCH_ENGINES, normalize_web_url
from core import external_apps
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
# 14. 10. 2026: funkcije, ki jih je imel le Safeer Browser GTK3 (najdi naprej/nazaj, tiskanje, celozaslonsko, utisaj ...).
_BRSKALNIK = {
    "sl": {"natisni": "Natisni …", "utisaj": "Utišaj zavihek", "zvok": "Vklopi zvok zavihka", "zadetki": "{n} zadetkov",
           "ni_zadetkov": "Ni zadetkov", "celozaslonsko": "Celozaslonski način", "odstrani": "Odstrani",
           "zaznamek_odstrani": "Odstrani zaznamek", "povecava_vrni": "Vrni velikost na 100 %",
           "najdi_naprej": "Naslednji zadetek", "najdi_nazaj": "Prejšnji zadetek",
           "kon_povezava": "Odpri povezavo v novem zavihku", "kon_slika": "Odpri sliko v novem zavihku"},
    "en": {"natisni": "Print …", "utisaj": "Mute tab", "zvok": "Unmute tab", "zadetki": "{n} matches",
           "ni_zadetkov": "No matches", "celozaslonsko": "Full screen", "odstrani": "Remove",
           "zaznamek_odstrani": "Remove bookmark", "povecava_vrni": "Reset zoom to 100 %",
           "najdi_naprej": "Next match", "najdi_nazaj": "Previous match",
           "kon_povezava": "Open link in new tab", "kon_slika": "Open image in new tab"},
    "de": {"natisni": "Drucken …", "utisaj": "Tab stummschalten", "zvok": "Ton des Tabs einschalten",
           "zadetki": "{n} Treffer", "ni_zadetkov": "Keine Treffer", "celozaslonsko": "Vollbild",
           "odstrani": "Entfernen", "zaznamek_odstrani": "Lesezeichen entfernen",
           "povecava_vrni": "Zoom auf 100 % zurücksetzen", "najdi_naprej": "Nächster Treffer",
           "najdi_nazaj": "Vorheriger Treffer", "kon_povezava": "Link in neuem Tab öffnen",
           "kon_slika": "Bild in neuem Tab öffnen"},
    "es": {"natisni": "Imprimir …", "utisaj": "Silenciar pestaña", "zvok": "Activar sonido de la pestaña",
           "zadetki": "{n} coincidencias", "ni_zadetkov": "Sin coincidencias", "celozaslonsko": "Pantalla completa",
           "odstrani": "Quitar", "zaznamek_odstrani": "Quitar marcador", "povecava_vrni": "Restablecer zoom al 100 %",
           "najdi_naprej": "Siguiente coincidencia", "najdi_nazaj": "Coincidencia anterior",
           "kon_povezava": "Abrir enlace en una pestaña nueva", "kon_slika": "Abrir imagen en una pestaña nueva"},
    "fr": {"natisni": "Imprimer …", "utisaj": "Couper le son de l’onglet", "zvok": "Rétablir le son de l’onglet",
           "zadetki": "{n} résultats", "ni_zadetkov": "Aucun résultat", "celozaslonsko": "Plein écran",
           "odstrani": "Supprimer", "zaznamek_odstrani": "Supprimer le marque-page",
           "povecava_vrni": "Réinitialiser le zoom à 100 %", "najdi_naprej": "Résultat suivant",
           "najdi_nazaj": "Résultat précédent", "kon_povezava": "Ouvrir le lien dans un nouvel onglet",
           "kon_slika": "Ouvrir l’image dans un nouvel onglet"},
    "it": {"natisni": "Stampa …", "utisaj": "Silenzia scheda", "zvok": "Riattiva audio scheda",
           "zadetki": "{n} risultati", "ni_zadetkov": "Nessun risultato", "celozaslonsko": "Schermo intero",
           "odstrani": "Rimuovi", "zaznamek_odstrani": "Rimuovi segnalibro", "povecava_vrni": "Ripristina zoom al 100 %",
           "najdi_naprej": "Risultato successivo", "najdi_nazaj": "Risultato precedente",
           "kon_povezava": "Apri link in una nuova scheda", "kon_slika": "Apri immagine in una nuova scheda"},
}
_NASTAVITVE = {
    "sl": {"nas_splosno": "Splošno", "nas_zasebnost": "Zasebnost in varnost", "nas_dovoljenja": "Nastavitve spletnih mest …",
           "nas_brisi": "Izbriši podatke brskanja …", "nas_mapa": "Mapa za prenose: {mapa}",
           "nas_vprasaj_kam": "Vedno vprašaj, kam shraniti datoteko",
           "nas_programi": "Programi in namestitveni paketi se prenesejo šele po tvoji potrditvi."},
    "en": {"nas_splosno": "General", "nas_zasebnost": "Privacy & security", "nas_dovoljenja": "Site settings …",
           "nas_brisi": "Clear browsing data …", "nas_mapa": "Download folder: {mapa}",
           "nas_vprasaj_kam": "Always ask where to save files",
           "nas_programi": "Programs and installers are downloaded only after you confirm."},
    "de": {"nas_splosno": "Allgemein", "nas_zasebnost": "Datenschutz & Sicherheit", "nas_dovoljenja": "Website-Einstellungen …",
           "nas_brisi": "Browserdaten löschen …", "nas_mapa": "Download-Ordner: {mapa}",
           "nas_vprasaj_kam": "Immer fragen, wo Dateien gespeichert werden",
           "nas_programi": "Programme und Installationspakete werden erst nach deiner Bestätigung heruntergeladen."},
    "es": {"nas_splosno": "General", "nas_zasebnost": "Privacidad y seguridad", "nas_dovoljenja": "Ajustes de sitios …",
           "nas_brisi": "Borrar datos de navegación …", "nas_mapa": "Carpeta de descargas: {mapa}",
           "nas_vprasaj_kam": "Preguntar siempre dónde guardar los archivos",
           "nas_programi": "Los programas e instaladores solo se descargan tras tu confirmación."},
    "fr": {"nas_splosno": "Général", "nas_zasebnost": "Vie privée et sécurité", "nas_dovoljenja": "Paramètres des sites …",
           "nas_brisi": "Effacer les données de navigation …", "nas_mapa": "Dossier de téléchargement : {mapa}",
           "nas_vprasaj_kam": "Toujours demander où enregistrer les fichiers",
           "nas_programi": "Les programmes et installateurs ne sont téléchargés qu’après votre confirmation."},
    "it": {"nas_splosno": "Generale", "nas_zasebnost": "Privacy e sicurezza", "nas_dovoljenja": "Impostazioni dei siti …",
           "nas_brisi": "Cancella dati di navigazione …", "nas_mapa": "Cartella download: {mapa}",
           "nas_vprasaj_kam": "Chiedi sempre dove salvare i file",
           "nas_programi": "Programmi e pacchetti di installazione vengono scaricati solo dopo la tua conferma."},
}
_BRISANJE = {
    "sl": {"bp_naslov": "Izbriši podatke brskanja", "bp_obdobje": "Časovno obdobje", "bp_ura": "Zadnja ura",
           "bp_dan": "Zadnjih 24 ur", "bp_teden": "Zadnji teden", "bp_vse": "Vse", "bp_zgodovina": "Zgodovina brskanja",
           "bp_piskotki": "Piškotki in podatki strani (odjava s strani)", "bp_predpomnilnik": "Predpomnilnik (slike in datoteke)",
           "bp_prenosi": "Seznam prenosov (datoteke ostanejo)", "bp_dovoljenja": "Nastavitve spletnih mest",
           "bp_izbrisi": "Izbriši", "bp_ob_izhodu": "Izbranih podatkov ob zaprtju ne shranjuj (izbriši ob izhodu)",
           "bp_koncano": "Izbrisano."},
    "en": {"bp_naslov": "Clear browsing data", "bp_obdobje": "Time range", "bp_ura": "Last hour", "bp_dan": "Last 24 hours",
           "bp_teden": "Last week", "bp_vse": "Everything", "bp_zgodovina": "Browsing history",
           "bp_piskotki": "Cookies and site data (signs you out)", "bp_predpomnilnik": "Cache (images and files)",
           "bp_prenosi": "Download list (files stay)", "bp_dovoljenja": "Site settings", "bp_izbrisi": "Clear",
           "bp_ob_izhodu": "Delete the selected data when closing", "bp_koncano": "Cleared."},
    "de": {"bp_naslov": "Browserdaten löschen", "bp_obdobje": "Zeitraum", "bp_ura": "Letzte Stunde", "bp_dan": "Letzte 24 Stunden",
           "bp_teden": "Letzte Woche", "bp_vse": "Alles", "bp_zgodovina": "Verlauf",
           "bp_piskotki": "Cookies und Website-Daten (meldet dich ab)", "bp_predpomnilnik": "Cache (Bilder und Dateien)",
           "bp_prenosi": "Download-Liste (Dateien bleiben)", "bp_dovoljenja": "Website-Einstellungen", "bp_izbrisi": "Löschen",
           "bp_ob_izhodu": "Ausgewählte Daten beim Schließen löschen", "bp_koncano": "Gelöscht."},
    "es": {"bp_naslov": "Borrar datos de navegación", "bp_obdobje": "Intervalo", "bp_ura": "Última hora",
           "bp_dan": "Últimas 24 horas", "bp_teden": "Última semana", "bp_vse": "Todo", "bp_zgodovina": "Historial",
           "bp_piskotki": "Cookies y datos de sitios (cierra sesiones)", "bp_predpomnilnik": "Caché (imágenes y archivos)",
           "bp_prenosi": "Lista de descargas (los archivos se quedan)", "bp_dovoljenja": "Ajustes de sitios",
           "bp_izbrisi": "Borrar", "bp_ob_izhodu": "Borrar los datos seleccionados al cerrar", "bp_koncano": "Borrado."},
    "fr": {"bp_naslov": "Effacer les données de navigation", "bp_obdobje": "Période", "bp_ura": "Dernière heure",
           "bp_dan": "Dernières 24 heures", "bp_teden": "Dernière semaine", "bp_vse": "Tout", "bp_zgodovina": "Historique",
           "bp_piskotki": "Cookies et données de sites (vous déconnecte)", "bp_predpomnilnik": "Cache (images et fichiers)",
           "bp_prenosi": "Liste des téléchargements (les fichiers restent)", "bp_dovoljenja": "Paramètres des sites",
           "bp_izbrisi": "Effacer", "bp_ob_izhodu": "Effacer les données sélectionnées à la fermeture", "bp_koncano": "Effacé."},
    "it": {"bp_naslov": "Cancella dati di navigazione", "bp_obdobje": "Intervallo", "bp_ura": "Ultima ora",
           "bp_dan": "Ultime 24 ore", "bp_teden": "Ultima settimana", "bp_vse": "Tutto", "bp_zgodovina": "Cronologia",
           "bp_piskotki": "Cookie e dati dei siti (esce dagli account)", "bp_predpomnilnik": "Cache (immagini e file)",
           "bp_prenosi": "Elenco download (i file restano)", "bp_dovoljenja": "Impostazioni dei siti", "bp_izbrisi": "Cancella",
           "bp_ob_izhodu": "Cancella i dati selezionati alla chiusura", "bp_koncano": "Cancellato."},
}
for _j, _b in (list(_BRISANJE.items()) + list(splet_prenosi.BESEDILA.items()) + list(pojavna_okna.BESEDILA.items()) + list(_BRSKALNIK.items())
               + list(zascita.BESEDILA.items()) + list(_NASTAVITVE.items()) + list(dovoljenja_strani.BESEDILA.items()) + list(drm.BESEDILA.items())):   # skupaj s Safeer Browserjem
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
        if t == "g":
            return "najdi-nazaj" if shift else "najdi-naprej"
        if t == "p" and not shift:
            return "natisni"
        if t == "delete" and shift:
            return "izbrisi"
        if t == "m" and not shift:
            return "utisaj"
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
            return "najdi-nazaj" if shift else "najdi-naprej"
        if t == "f11":
            return "celozaslonsko"
    return None


def stevilo_zadetkov(n: int, jezik: str) -> str:
    """»1 zadetek, 2 zadetka, 3 zadetki, 5 zadetkov« (slovenska dvojina in mnozina; preizkus 14. 10.: »2 zadetkov«)."""
    j = (jezik or "en")[:2]
    if j == "sl":
        o = n % 100
        oblika = "zadetek" if o == 1 else "zadetka" if o == 2 else "zadetki" if o in (3, 4) else "zadetkov"
        return "%d %s" % (n, oblika)
    edn = {"en": "match", "de": "Treffer", "es": "coincidencia", "fr": "résultat", "it": "risultato"}
    mn = {"en": "matches", "de": "Treffer", "es": "coincidencias", "fr": "résultats", "it": "risultati"}
    return "%d %s" % (n, (edn if n == 1 else mn).get(j, "matches" if n != 1 else "match"))


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


def _izvor(url: str) -> str:
    """shema://gostitelj[:vrata] (izvor strani) ali ''."""
    try:
        d = urllib.parse.urlsplit(url or "")
    except ValueError:
        return ""
    return (d.scheme + "://" + d.netloc).lower() if d.scheme and d.netloc else ""


def pocisti_vse_ob_izhodu(spleti, GLib, cas: float = 5.0) -> bool:
    """Konec Safeer OS: za vsak Splet (okno in namizje) konca Safeer DRM in izvede »Izbrisi ob izhodu«, nato caka na
    WebKit (asinhrono brisanje) najvec `cas` sekund, kot Safeer Browser ob zaprtju okna. Prej je Safeer OS ob izhodu
    klical le koncaj() - nastavitev ni brisala nicesar, proces safeer-drm je ostal (pregled 14. 10. 2026).
    Vrne True, ce se je brisanje koncalo pravocasno."""
    spleti = [s for s in spleti if s is not None]
    for s in spleti:
        try:
            s.koncaj_drm()
        except Exception as e:  # noqa: BLE001 - izhod mora uspeti
            print("[Splet] DRM ob izhodu:", e, flush=True)
    ostane = {"n": len(spleti)}

    def konec():
        ostane["n"] -= 1
    for s in spleti:
        try:
            s.pocisti_ob_izhodu(konec)
        except Exception as e:  # noqa: BLE001
            print("[Splet] brisanje ob izhodu:", e, flush=True)
            konec()
    kontekst = GLib.MainContext.default()
    rok = time.monotonic() + cas
    while ostane["n"] > 0 and time.monotonic() < rok:
        if not kontekst.iteration(False):
            time.sleep(0.01)
    return ostane["n"] <= 0


def lokalni_naslov(naslov: str) -> str:
    """file:// na obstojeco navadno datoteko (HTML, PDF, slika ... iz »Odpri z«, ukazne vrstice, privzetega brskalnika
    ali naslovne vrstice) ali ''. normalize_web_url pozna le http(s), zato lokalna datoteka prej ni odprla nicesar
    (pregled 14. 10. 2026). Mapo ali neobstojeco pot zavrnemo."""
    n = (naslov or "").strip()
    if not n.lower().startswith("file://"):
        return ""
    try:
        d = urllib.parse.urlsplit(n)
        if d.netloc not in ("", "localhost"):
            return ""
        pot = urllib.parse.unquote(d.path)
    except ValueError:
        return ""
    return n if pot and os.path.isfile(pot) else ""


def je_vdelana_vsebina(naslov: str, stran: str) -> bool:
    """Navigacija, ki je del strani in ne pomeni nove strani: about:srcdoc (okvir s srcdoc), data: (okvir; glavni okvir
    WebKit zavrne sam, preverjeno 14. 10. 2026 v WebKitGTK 6.0) in blob: istega izvora kot stran (prenos z atributom
    download, izvoz) ali vgrajenega pdf.js (»Shrani«). Prej je Splet vse to prezrl (pregled 14. 10. 2026)."""
    n = (naslov or "").strip()
    nl = n.lower()
    if nl == "about:srcdoc" or nl.startswith("data:"):
        return True
    if nl.startswith("blob:"):
        if nl.startswith("blob:webkit-pdfjs-viewer://"):
            return True
        izvor = _izvor(n[5:])
        return izvor.startswith(("https://", "http://")) and izvor == _izvor(stran)
    return False


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
            if self.config.get("zascita_itp", False):
                self.seja.set_itp_enabled(True)      # stroga zascita (core/zascita.py)
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
        Gtk, Gdk = self.Gtk, self.Gdk
        self.gradnik = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.gradnik.set_name("safeer-splet")
        self.vrstica_zavihkov = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.vrstica_zavihkov.set_name("splet-zavihki")
        self.skatla_zavihkov = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.skatla_zavihkov.set_margin_start(10)
        # Zavihki v drsniku: veliko zavihkov ne razsiri okna cez zaslon (preizkus 14. 10.: okno ni slo vec na zaslon);
        # ko jih je prevec, se vrstica drsi (kolesce, Ctrl+Tab), kot v Firefoxu.
        self.drsnik_zavihkov = Gtk.ScrolledWindow()
        self.drsnik_zavihkov.set_policy(Gtk.PolicyType.EXTERNAL, Gtk.PolicyType.NEVER)
        self.drsnik_zavihkov.set_propagate_natural_width(True)
        self.drsnik_zavihkov.set_child(self.skatla_zavihkov)
        self.vrstica_zavihkov.append(self.drsnik_zavihkov)
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
        self.gumb_povecave = Gtk.Button(label="100 %")
        self.gumb_povecave.set_has_frame(False)
        self.gumb_povecave.add_css_class("address-action")
        self.gumb_povecave.set_tooltip_text(self._t("povecava_vrni"))
        self.gumb_povecave.connect("clicked", lambda *_: self.izvedi("povecava-0"))
        self.gumb_povecave.set_visible(False)
        naslov.append(self.kljucavnica)
        naslov.append(self.vnos)
        naslov.append(self.gumb_povecave)
        naslov.append(self.zvezdica)
        orodja.append(naslov)
        self.gumb_prenosov = self._gumb("⬇", self._pokazi_prenose, "nav")
        self.gumb_prenosov.set_visible(False)
        orodja.append(self.gumb_prenosov)
        self.scit = self._gumb("♢", lambda *_: self._pokazi_scit(), "nav")
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
        # Enter: naslednji, Shift+Enter: prejsnji, Esc: zapri (kot v Firefoxu); stevec zadetkov.
        self.najdi_vnos.connect("activate", lambda *_: self.izvedi("najdi-naprej"))
        k = Gtk.EventControllerKey()
        k.connect("key-pressed", lambda _k, kv, _c, st: bool(
            Gdk.keyval_name(kv) in ("Return", "KP_Enter") and st & Gdk.ModifierType.SHIFT_MASK
            and self.izvedi("najdi-nazaj")))
        self.najdi_vnos.add_controller(k)
        self.najdi_vnos.connect("previous-match", lambda *_: self.izvedi("najdi-nazaj"))
        self.najdi_vnos.connect("next-match", lambda *_: self.izvedi("najdi-naprej"))
        self.najdi_vnos.connect("stop-search", lambda *_: (self.najdi_vrstica.set_search_mode(False),
                                                          self.trenutni() and self.trenutni().get_find_controller().search_finish()))
        najdi_vrsta = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        najdi_vrsta.append(self.najdi_vnos)
        for ikona, dejanje, namig in (("go-up-symbolic", "najdi-nazaj", "najdi_nazaj"),
                                      ("go-down-symbolic", "najdi-naprej", "najdi_naprej")):
            g = Gtk.Button.new_from_icon_name(ikona); g.set_has_frame(False); g.set_tooltip_text(self._t(namig))
            g.connect("clicked", lambda _g, d=dejanje: self.izvedi(d))
            najdi_vrsta.append(g)
        self.najdi_stevec = Gtk.Label(label="")
        self.najdi_stevec.set_name("splet-najdi-stevec")   # svetlo na temni vrstici (preizkus 14. 10.: neviden)
        najdi_vrsta.append(self.najdi_stevec)
        self.najdi_vrstica.set_child(najdi_vrsta)
        self.najdi_vrstica.connect_entry(self.najdi_vnos)
        self.gradnik.append(self.najdi_vrstica)
        # Blokirano pojavno okno: vrstica nad stranjo (kot v drugih brskalnikih), nic se ne izgubi brez vednosti.
        self.pojavna = Gtk.Revealer()
        vrsta = _robovi(Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8), 4)
        vrsta.set_name("splet-pojavna")
        self.pojavna_napis = Gtk.Label(xalign=0, hexpand=True)
        self.pojavna_napis.set_ellipsize(self.Pango.EllipsizeMode.MIDDLE)
        self.pojavna_odpri = Gtk.Button(label=self._t("po_odpri"))
        self.pojavna_vedno = Gtk.Button()
        skrij = Gtk.Button.new_from_icon_name("window-close-symbolic")
        skrij.set_has_frame(False)
        skrij.connect("clicked", lambda *_: self._vrstica_skrij())
        for g in (self.pojavna_napis, self.pojavna_odpri, self.pojavna_vedno, skrij):
            vrsta.append(g)
        self.pojavna_odpri.connect("clicked", lambda *_: self._vrstica_klik(False))
        self.pojavna_vedno.connect("clicked", lambda *_: self._vrstica_klik(True))
        self.pojavna.set_child(vrsta)
        self._pojavno = None
        self._drm_ponudba = None      # (pogled, url): vrstica ponuja Safeer DRM (isto mesto kot pojavna okna)
        self.gradnik.append(self.pojavna)
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
            "natisni": lambda: self.izvedi("natisni"), "celozaslonsko": lambda: self.izvedi("celozaslonsko"),
            "izbrisi": lambda: self._izbrisi_podatke(), "dovoljenja": lambda: self._dovoljenja_strani(),
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
        #safeer-splet searchbar > revealer > box { background: #0b1424; border-bottom: 1px solid rgba(211,229,255,.14); }
        #safeer-splet searchbar entry { background: #101a2b; color: #eaf2ff; border: 1px solid rgba(138,199,255,.45); }
        #safeer-splet searchbar button { background: transparent; color: #e2eaf6; border: 0; box-shadow: none; }
        #splet-najdi-stevec { color: #b0bdc4; margin-left: 6px; }
        #safeer-brskalnik { background: #0b1424; }
        #splet-pojavna { background: #16233a; color: #eaf2ff; border-bottom: 1px solid rgba(138,199,255,.35); }
        #splet-pojavna button { background: rgba(138,199,255,.12); color: #eaf2ff; border: 1px solid rgba(138,199,255,.35);
          box-shadow: none; }
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
                 ("povecaj", "povecaj"), ("pomanjsaj", "pomanjsaj"), ("natisni", "natisni"),
                 ("celozaslonsko", "celozaslonsko"), ("nas_brisi", "izbrisi"), ("nas_dovoljenja", "dovoljenja"),
                 ("nastavitve", "nastavitve"), ("zapisek", "zapisek")]
        if not self.odpri_zapisek:
            vnosi = [v for v in vnosi if v[1] != "zapisek"]   # samostojni brskalnik nima zapiskov: brez praznega vnosa
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
        self._filter_za(pogled, pogled.get_uri() or "")

    def _filter_za(self, pogled, naslov: str) -> None:
        """Seznam EasyList na zavihku: vklopljen, razen ce ga je uporabnik izklopil (stopnja po meri) ali stran izvzel
        (»Zascita na tej strani: izklopljena«). Upravitelj vsebine je za vsak zavihek svoj, zato velja le zanj."""
        upravitelj = pogled.get_user_content_manager()
        try:
            upravitelj.remove_filter_by_id(FILTER_ID)
            if (self.filter is not None and self.config.get("easylist_enabled", True)
                    and not zascita.je_izjema(self.config, naslov)):
                upravitelj.add_filter(self.filter)
        except Exception:  # noqa: BLE001
            pass

    def _skripta(self, upravitelj, koda, cas=None, dovoljeni=None, izloceni=None):
        if not koda:
            return
        upravitelj.add_script(self.WebKit2.UserScript(
            koda, self.WebKit2.UserContentInjectedFrames.ALL_FRAMES,
            cas or self.WebKit2.UserScriptInjectionTime.START, dovoljeni, izloceni))

    def _nov_pogled(self, povezan=None):
        W = self.WebKit2
        # WebKitGTK 6.0: kontekst (procesi strani, meja pomnilnika) in omrezna seja (podatki, piskotki) sta locena.
        # povezan: okno, ki ga odpre stran (window.open, prijava z Googlom/Microsoftom): WebKit zahteva »related-view«,
        # ki deli proces in sejo z izvorom; upravitelj vsebine in nastavitve sta svoja (preverjeno 14. 10. 2026), zato
        # spodaj dobi iste skripte in nastavitve kot vsak zavihek.
        pogled = (W.WebView(related_view=povezan) if povezan is not None
                  else W.WebView(web_context=self.kontekst, network_session=self.seja,
                                 website_policies=self._pravila_strani()))
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
        # Safeer DRM sele po kliku v vrstici (_drm_ponudi) in ne, ce je stran v nastavitvah zavrnjena.
        drm.prikljuci(W, pogled, self._drm, lambda: str(self.jezik() if callable(self.jezik) else self.jezik or "sl"),
                      vdelaj=self._drm_vdelaj, ponudi=self._drm_ponudi,
                      dovoljeno=lambda url: dovoljenja_strani.odlocitev(self.config, url, ["drm"]))
        izvzemi = adblock.AUTH_SCRIPT_EXCLUSIONS
        # Strani, kjer je uporabnik izklopil zascito: brez skript za oglase (ostanejo varnostne in GPC).
        izvzemi_oglase = izvzemi + zascita.vzorci_izjem(self.config)
        if self.config.get("gpc_dnt_enabled", True): self._skripta(upravitelj, adblock.GPC_AND_DNT_SCRIPT, izloceni=izvzemi)
        if self.config.get("adblock_enabled", True):
            self._skripta(upravitelj, adblock.YOUTUBE_ADBLOCK_SCRIPT, dovoljeni=["*://*.youtube.com/*", "*://youtube.com/*"], izloceni=izvzemi_oglase)
        self._skripta(upravitelj, adblock.YOUTUBE_KEEP_WATCHING_SCRIPT, dovoljeni=["*://*.youtube.com/*", "*://youtube.com/*"], izloceni=izvzemi)
        if self.config.get("adguard_protection_enabled", True): self._skripta(upravitelj, adblock.ADGUARD_PROTECTION_SCRIPT, izloceni=izvzemi_oglase)
        # Kozmeticna skripta (cist DOM) v locenem svetu: lahko skrije oglase in posilja stevec, stran je ne vidi.
        upravitelj.add_script(W.UserScript.new_for_world(
            adblock.GENERIC_COSMETIC_SCRIPT, W.UserContentInjectedFrames.ALL_FRAMES,
            W.UserScriptInjectionTime.END, adblock.STEVEC_SVET, None, izvzemi_oglase))
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
                              ("enable_encrypted_media", True),
                              # Stroga zascita: stran ne izve lokalnega naslova IP prek WebRTC.
                              ("enable_webrtc", not self.config.get("zascita_brez_webrtc", False))):
            nastavi = getattr(nastavitve, "set_" + ime, None)
            if nastavi is not None:
                try:
                    nastavi(vrednost)
                except Exception:  # noqa: BLE001
                    pass
        # Temno pod našo začetno stranjo, belo pod spletom - belo mora biti nastavljeno, preden dokument strani nastane.
        ozadje_strani.prikljuci(self.Gdk, W, pogled, os.path.join(self.koren, "ui"), TEMNO_OZADJE)
        pogled.connect("decide-policy", self._politika)
        # Napaka omrezja ali potrdila: nasa stran v jeziku vmesnika (prej WebKitova v anglescini; kot Safeer Browser).
        from core.network_errors import NetworkErrorHandler
        pogled._safeer_napake = NetworkErrorHandler(pogled, lambda: str(self.jezik() if callable(self.jezik) else self.jezik or "sl"))
        fc = pogled.get_find_controller()
        fc.connect("counted-matches", lambda f, n: pogled is self.trenutni() and self._najdi_stevec(f, n))
        fc.connect("failed-to-find-text", lambda f: pogled is self.trenutni() and self._najdi_stevec(f, 0))
        self._tipke(pogled, lambda e: self.tipka(e))
        self._klik(pogled, lambda gumb, x, y, p: self._miska(p, _Klik(gumb, x, y)))
        pogled.connect("create", lambda p, a: self._novo_okno(p, a))
        pogled.connect("context-menu", self._kontekstni_meni)
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

    def nov_zavihek(self, naslov: str = "", povezan=None, lokalno: bool = False):
        self._stevec += 1
        pogled = self._nov_pogled(povezan)
        vrstica = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=6)
        vrstica.add_css_class("splet-tab")
        ikona = self.Gtk.Label(label="🌐")
        naslov_lbl = self.Gtk.Label(label=self._t("nov")); naslov_lbl.set_ellipsize(self.Pango.EllipsizeMode.END)
        naslov_lbl.set_xalign(0); naslov_lbl.set_hexpand(True)
        zapri = self._gumb("×", lambda *_: self.zapri_zavihek(pogled), "tab-close")
        zvok = self.Gtk.Button.new_from_icon_name("audio-volume-high-symbolic")
        zvok.set_has_frame(False); zvok.add_css_class("tab-close"); zvok.set_visible(False)
        zvok.connect("clicked", lambda *_: (pogled.set_is_muted(not pogled.get_is_muted()), self._osvezi_zvok(pogled)))
        vrstica.append(ikona); vrstica.append(naslov_lbl); vrstica.append(zvok); vrstica.append(zapri)
        # GTK4: ni EventBox; klik na zavihek ujame GestureClick na sami vrstici (gumb × ostane svoj).
        dogodek = vrstica
        self._klik(vrstica, lambda *_: self.izberi(pogled), 1)
        self.skatla_zavihkov.append(vrstica)
        pogled.set_vexpand(True); pogled.set_hexpand(True)
        self.sklad.add_named(pogled, "splet-%d" % self._stevec)
        zavihek = {"pogled": pogled, "dogodek": dogodek, "vrstica": vrstica, "naslov": naslov_lbl, "ikona": ikona,
                   "zvok": zvok}
        pogled.connect("notify::is-playing-audio", lambda p, _l: self._osvezi_zvok(p))
        pogled.connect("notify::is-muted", lambda p, _l: self._osvezi_zvok(p))
        pogled.connect("notify::zoom-level", lambda p, _l: p is self.trenutni() and self._osvezi_povecavo())
        self.zavihki.append(zavihek)
        self.izberi(pogled)
        if povezan is None:
            self.odpri(naslov, pogled, lokalno)      # okno strani nalozi WebKit sam (zahteva iz window.open)
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
            p.set_zoom_level(1.0); self._osvezi_povecavo()
        elif dejanje in ("najdi-naprej", "najdi-nazaj"):
            if not self.najdi_vrstica.get_search_mode() or not self.najdi_vnos.get_text():
                self._pokazi_najdi()
            elif p is not None:
                fc = p.get_find_controller()
                fc.search_next() if dejanje == "najdi-naprej" else fc.search_previous()
        elif dejanje == "natisni" and p is not None:
            try:
                self.WebKit2.PrintOperation.new(p).run_dialog(self._okno_za_dialog())
            except Exception as napaka:  # noqa: BLE001
                print("[Splet] tiskanje:", napaka, flush=True)
        elif dejanje == "celozaslonsko":
            okno = self._okno_za_dialog()
            if okno is not None:
                okno.unfullscreen() if okno.is_fullscreen() else okno.fullscreen()
        elif dejanje == "izbrisi":
            self._izbrisi_podatke()
        elif dejanje == "utisaj" and p is not None:
            p.set_is_muted(not p.get_is_muted()); self._osvezi_zvok(p)
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
            viri = {"zaznamki": [{"title": p.get("title", ""), "url": p.get("url", ""), "id": p.get("id", "")}
                                 for p in self.config.get_portals()],
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
                    vrsta = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
                    skatla.set_hexpand(True); vrsta.append(skatla)
                    # × odstrani zaznamek ali stran iz zgodovine (prej ni bilo mogoce; 14. 10. 2026).
                    proc = Gtk.Button.new_from_icon_name("window-close-symbolic")
                    proc.set_has_frame(False); proc.set_valign(Gtk.Align.CENTER)
                    proc.set_tooltip_text(self._t("odstrani"))
                    proc.connect("clicked", lambda _g, k=kljuc, zz=z: (self._odstrani_iz(k, zz), napolni()))
                    vrsta.append(proc)
                    vrstica.set_child(vrsta); sez.append(vrstica)
                if not zadetki:
                    sez.append(_robovi(Gtk.Label(label=self._t("prazno")), 16))
        iskanje.connect("search-changed", napolni)
        iskanje.set_margin_top(6); iskanje.set_margin_bottom(6)
        obmocje.append(iskanje); obmocje.append(zvezki)
        napolni()
        d.present()
        zvezki.set_current_page(0 if kaj == "zaznamki" else 1)
        iskanje.grab_focus()

    def _odstrani_iz(self, kaj: str, zapis: dict) -> None:
        from core import zgodovina
        if kaj == "zaznamki":
            if zapis.get("id"):
                self.config.delete_portal(zapis["id"])
        else:
            zgodovina.odstrani(os.path.join(self.config.config_dir, "history.json"), zapis.get("url", ""))
        self._osvezi_zvezdico()

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
        if getattr(self, "_pojavno", None) and self._pojavno[2] is not pogled:
            self._pojavno = None; self.pojavna.set_reveal_child(False)   # vrstica velja za zavihek, kjer je nastala
        if getattr(self, "_drm_ponudba", None) and self._drm_ponudba[0] is not pogled:
            self._drm_ponudba = None; self.pojavna.set_reveal_child(False)
        z = self._zavihek(pogled)
        if z is not None and z.get("drm") is not None:
            self.sklad.set_visible_child(z["drm"].gradnik)
        elif z is not None and z.get("drm_ponudba") and getattr(self, "pojavna", None) is not None:
            self._drm_ponudi(pogled, *z["drm_ponudba"])     # ponudba, ki je nastala v ozadju
        for z in self.zavihki:
            if z["pogled"] is pogled:
                z["vrstica"].add_css_class("splet-tab-aktiven")
            else:
                z["vrstica"].remove_css_class("splet-tab-aktiven")
        z = self._zavihek(pogled)
        if z is not None and getattr(self, "drsnik_zavihkov", None) is not None:
            self.GLib.idle_add(lambda v=z["vrstica"]: self._v_vidno(v) or False)
        self._osvezi_orodja()

    def _v_vidno(self, vrstica) -> None:
        """Izbrani zavihek v vidnem delu drsne vrstice zavihkov."""
        try:
            ok, meje = vrstica.compute_bounds(self.skatla_zavihkov)
            if not ok:
                return
            prilagodi = self.drsnik_zavihkov.get_hadjustment()
            x, sirina = meje.get_x(), meje.get_width()
            if x < prilagodi.get_value():
                prilagodi.set_value(x)
            elif x + sirina > prilagodi.get_value() + prilagodi.get_page_size():
                prilagodi.set_value(x + sirina - prilagodi.get_page_size())
        except Exception:  # noqa: BLE001
            pass

    def trenutni(self):
        return self.aktivni

    def domaci_uri(self) -> str:
        return self.GLib.filename_to_uri(os.path.join(self.koren, "ui", "splet.html"), None)

    def odpri_domov(self):
        if self.trenutni(): self.trenutni().load_uri(self.domaci_uri())

    def odpri(self, naslov: str = "", pogled=None, lokalno: bool = False):
        """lokalno=True: tudi datoteka z diska (file://) - samo za naslove od uporabnika (naslovna vrstica, »Odpri z«,
        ukazna vrstica), nikoli iz sporocil strani ali drugih naprav."""
        pogled = pogled or self.trenutni()
        if pogled is None:
            if self.zavihki:
                return False
            if lokalno and lokalni_naslov(naslov):
                self.nov_zavihek(naslov, lokalno=True); return True
            self.nov_zavihek(naslov)        # po sprosti_zavihke(): prvi zavihek na novo
            return True
        if not naslov: pogled.load_uri(self.domaci_uri()); return True
        normalen = (lokalni_naslov(naslov) if lokalno else "") or normalize_web_url(naslov)
        if not normalen: return False
        pogled.load_uri(normalen); return True

    def odpri_povezavo(self, naslov: str, lokalno: bool = False) -> bool:
        """Povezava od drugod (sporočilo): strani, ki jo ima uporabnik odprto, ne zamenja. V zavihku z našo začetno
        stranjo se odpre tam, sicer v novem zavihku. lokalno=True (samo Safeer Browser: datoteka iz »Odpri z« ali
        privzetega brskalnika): tudi file:// na obstojeco datoteko."""
        normalen = (lokalni_naslov(naslov) if lokalno else "") or normalize_web_url(naslov)
        if not normalen: return False
        pogled = self.trenutni()
        if pogled is not None and ozadje_strani.nasa_stran(pogled.get_uri() or "", os.path.join(self.koren, "ui")):
            pogled.load_uri(normalen); return True
        if lokalno:
            self.nov_zavihek(normalen, lokalno=True); return True
        self.nov_zavihek(normalen); return True

    def _vnesi_naslov(self, vnos):
        besedilo = vnos.get_text().strip()
        naslov = lokalni_naslov(besedilo) or normalize_web_url(besedilo)
        if not naslov:
            motor = self.config.get("search_engine", "duckduckgo")
            naslov = SEARCH_ENGINES.get(motor, SEARCH_ENGINES["duckduckgo"])["url"] + urllib.parse.quote_plus(besedilo)
        self.odpri(naslov, lokalno=True)        # uporabnik je naslov vpisal sam

    def _politika(self, pogled, odlocitev, vrsta):
        W = self.WebKit2
        if vrsta == W.PolicyDecisionType.RESPONSE:
            return self._odziv(pogled, odlocitev)
        if vrsta not in (W.PolicyDecisionType.NAVIGATION_ACTION, W.PolicyDecisionType.NEW_WINDOW_ACTION): return False
        try:
            dejanje = odlocitev.get_navigation_action(); zahteva = dejanje.get_request(); naslov = zahteva.get_uri() or ""
            if naslov.lower().startswith("stremio://"):
                # Stran sama ne doda nicesar: dodatek se doda sele, ko uporabnik v Safeer Playerju pritisne Poveži.
                odlocitev.ignore()
                if self.stremio_dodatek is not None:
                    self.GLib.idle_add(lambda: self.stremio_dodatek(naslov) and False)
                return True
            nov_okno = vrsta == W.PolicyDecisionType.NEW_WINDOW_ACTION
            shema = external_apps.external_scheme(naslov)
            if shema:
                # mailto:, tel:, magnet:, zoommtg:, claude:// po prijavi ...: program na racunalniku, po potrditvi
                # (prej tiho prezrto; 14. 10. 2026 kot safeer_mint.py open_external_app_link).
                odlocitev.ignore()
                try:
                    kretnja = bool(dejanje.is_user_gesture())
                except Exception:  # noqa: BLE001
                    kretnja = dejanje.get_navigation_type() == W.NavigationType.LINK_CLICKED
                self.GLib.idle_add(lambda: self._zunanji_program(naslov, shema, pogled.get_uri() or "", kretnja) and False)
                return True
            # Srednji klik ali Ctrl+klik na povezavo: nov zavihek (kot v drugih brskalnikih).
            if (dejanje.get_navigation_type() == W.NavigationType.LINK_CLICKED and naslov.startswith(("http://", "https://"))
                    and (dejanje.get_mouse_button() == 2 or dejanje.get_modifiers() & int(self.Gdk.ModifierType.CONTROL_MASK))):
                odlocitev.ignore(); self.nov_zavihek(naslov); return True
            if naslov.startswith(("file://", "about:blank")):
                odlocitev.use(); return True     # about:blank: okno za prijavo se pogosto odpre prazno
            if je_vdelana_vsebina(naslov, pogled.get_uri() or ""):
                # NAVIGATION_ACTION velja tudi za okvirje (iframe): srcdoc, data: in blob: istega izvora (prenos z
                # atributom download, »Shrani« v pdf.js) so del strani. Glavni okvir na data: WebKit zavrne sam.
                odlocitev.use(); return True
            if not naslov.startswith(("http://", "https://")):
                odlocitev.ignore(); return True
            grozi = adblock.is_threat_domain(naslov)      # enkrat na navigacijo (prej dvakrat)
            izjema = zascita.je_izjema(self.config, naslov)
            if not grozi and not izjema and self.config.get("adblock_enabled", True) and adblock.is_ad_domain(naslov):
                self.config.increment_ads_blocked(); odlocitev.ignore(); self._osvezi_scit(); return True
            if grozi:
                self.config.increment_threats_blocked(); odlocitev.ignore(); self._opozorilo("Safeer Shield", naslov); self._osvezi_scit(); return True
            sodba = adblock.fake_bank_verdict(naslov)
            if sodba is not None:
                odlocitev.ignore(); self._opozorilo_bank(pogled, naslov, sodba); return True
            if nov_okno:
                prava = dejanje.get_navigation_type() == W.NavigationType.LINK_CLICKED
                if self.config.get("popup_blokiraj", True) and not pojavna_okna.dovoli(
                        pogled.get_uri() or "", naslov, prava, self.config.get("popup_dovoljeni", []) or []):
                    odlocitev.ignore(); self._pojavno_blokirano(pogled, naslov); return True
                odlocitev.use(); return True     # zavihek naredi signal "create" (_novo_okno)
            # Prazno okno (window.open("") in nato location = ...): prvi pravi naslov gre skozi pravila pojavnih oken
            # z odpiralcem kot izvorom (pregled 14. 10. 2026: tako se je odprl oglas mimo blokade).
            z = self._zavihek(pogled)
            if z is not None and z.get("pojavno_prazno") is not None:
                izvor, prava, odpiralec = z.pop("pojavno_prazno")
                if self.config.get("popup_blokiraj", True) and not pojavna_okna.dovoli(
                        izvor, naslov, prava, self.config.get("popup_dovoljeni", []) or []):
                    odlocitev.ignore()
                    self.GLib.idle_add(lambda: self._pojavno_prazno_blokirano(pogled, odpiralec(), naslov) and False)
                    return True
            # Samo klik na povezavo (kot safeer_mint.py): decide-policy velja tudi za okvirje, load_uri pa bi z naslovom
            # okvirja (vdelan predvajalnik z utm_) zamenjal ves zavihek; preusmeritev in obrazec (POST) ostaneta.
            if (not izjema and self.config.get("tracking_protection_enabled", True)
                    and dejanje.get_navigation_type() == W.NavigationType.LINK_CLICKED and not dejanje.is_redirect()
                    and zahteva.get_http_method() == "GET"):
                cist = adblock.strip_tracking_parameters(naslov)
                if cist != naslov:
                    odlocitev.ignore()
                    self.GLib.idle_add(lambda: pogled.load_uri(cist) and False)
                    return True
            # Zamenjava pogleda za strojni izris (seznam puscanja) je v _odziv: tam WebKit pove, ali gre za glavni okvir.
            odlocitev.use(); return True
        except Exception:
            odlocitev.ignore(); return True

    def _novo_okno(self, pogled, dejanje):
        """Okno, ki ga odpre stran (target=_blank, window.open): zavihek s povezanim pogledom. Prej je bil zavihek brez
        opener, zato prijava v oknu (Google, Microsoft, Apple, placila) ni mogla vrniti rezultata strani, ki jo je
        odprla (14. 10. 2026, kot safeer_mint.py new_tab(related_view)). Stran okno zapre z window.close()."""
        # window.open ne gre skozi decide-policy NEW_WINDOW_ACTION (to je le za target=_blank; preizkus 14. 10.: okno na
        # tujo stran se je odprlo), zato ista pravila tudi tu.
        try:
            naslov = dejanje.get_request().get_uri() or ""
            prava = dejanje.get_navigation_type() == self.WebKit2.NavigationType.LINK_CLICKED
        except Exception:  # noqa: BLE001
            naslov, prava = "", False
        if naslov.lower().startswith(("http://", "https://")):
            if adblock.is_threat_domain(naslov):
                self.config.increment_threats_blocked(); self._osvezi_scit(); return None
            if self.config.get("adblock_enabled", True) and adblock.is_ad_domain(naslov):
                self.config.increment_ads_blocked(); self._osvezi_scit(); return None
            if self.config.get("popup_blokiraj", True) and not pojavna_okna.dovoli(
                    pogled.get_uri() or "", naslov, prava, self.config.get("popup_dovoljeni", []) or []):
                self._pojavno_blokirano(pogled, naslov); return None
        nov = self.nov_zavihek(povezan=pogled)
        ref = weakref.ref(nov)
        izvor = weakref.ref(pogled)
        if not naslov.lower().startswith(("http://", "https://")):
            # Prazno okno: pravila pojavnih oken veljajo za prvo pravo stran, ki jo vanj nalozi odpiralec (_politika).
            z = self._zavihek(nov)
            if z is not None:
                z["pojavno_prazno"] = (pogled.get_uri() or "", prava, izvor)

        def zapri(*_):
            # Okno za prijavo se zapre samo: uporabnik se vrne na stran, ki ga je odprla (preizkus 14. 10.: izbran je
            # bil sosednji zavihek). Zapremo izven signala "close": pogleda ne unicujemo v njegovem rokovalniku.
            def zdaj():
                if ref() is not None:
                    self.zapri_zavihek(ref())
                if izvor() is not None and any(z["pogled"] is izvor() for z in self.zavihki):
                    self.izberi(izvor())
                return False
            self.GLib.idle_add(zdaj)
        nov.connect("close", zapri)
        return nov

    def _pojavno_prazno_blokirano(self, pogled, odpiralec, naslov: str) -> None:
        """Prazno okno je hotelo na stran, ki je pravila pojavnih oken ne dovolijo: zavihek zapremo, odpiralec dobi
        vrstico »Blokirano pojavno okno · Odpri · Vedno dovoli« kot pri vsakem drugem."""
        if any(z["pogled"] is pogled for z in self.zavihki) and len(self.zavihki) > 1:
            self.zapri_zavihek(pogled)
        if odpiralec is not None and any(z["pogled"] is odpiralec for z in self.zavihki):
            self.izberi(odpiralec)
            self._pojavno_blokirano(odpiralec, naslov)

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

    def _odziv(self, pogled, odlocitev) -> bool:
        """Odgovor strezenika (RESPONSE): samo tu WebKit pove, ali je to glavni okvir. Stran s seznama puscanja dobi
        nov pogled z drugim izrisom - samo glavni okvir in GET (prej je okvir zamenjal ves zavihek, POST je postal GET).
        Zamenjava gre izven rokovalnika (pogleda ne unicujemo med njegovim signalom)."""
        try:
            if not odlocitev.is_main_frame_main_resource():
                return False
            zahteva = odlocitev.get_request()
            if (zahteva.get_http_method() or "GET").upper() != "GET":
                return False
            odgovor = odlocitev.get_response()
            naslov = (odgovor.get_uri() if odgovor is not None else "") or zahteva.get_uri() or ""
            if not naslov.startswith(("http://", "https://")) or not self._potrebuje_zamenjavo(pogled, naslov):
                return False
        except Exception:  # noqa: BLE001 - privzeto ravnanje WebKita
            return False
        odlocitev.ignore()
        self.GLib.idle_add(lambda: self._zamenjaj_za_pospesevanje(pogled, naslov) and False)
        return True

    def _potrebuje_zamenjavo(self, pogled, naslov: str) -> bool:
        try:
            return pogled.get_settings().get_hardware_acceleration_policy() != self._zelena_politika(naslov)
        except Exception:  # noqa: BLE001
            return False

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
        return self._zamenjaj_pogled(pogled, naslov, zelena)

    def _zamenjaj_pogled(self, pogled, naslov: str, politika=None) -> bool:
        """Zavihek na istem mestu dobi nov pogled (nove skripte, izris, izjeme zascite) z isto stranjo."""
        star = next((x for x in self.zavihki if x["pogled"] is pogled), None)
        if star is None:
            return False
        indeks = self.zavihki.index(star)
        self._naslednja_politika = politika
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
        if dogodek == self.WebKit2.LoadEvent.STARTED:
            self._filter_za(pogled, pogled.get_uri() or "")    # izjema zascite velja ze za prvo zahtevo strani
            return
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
        if z is not None and z.get("drm_ponudba") and _gostitelj(pogled.get_uri() or "") != _gostitelj(z["drm_ponudba"][0]):
            z.pop("drm_ponudba", None)         # ponudba velja za stran, kjer je nastala
            if getattr(self, "_drm_ponudba", None) and self._drm_ponudba[0] is pogled:
                self._drm_ponudba = None; self.pojavna.set_reveal_child(False)
                self.pojavna_odpri.set_label(self._t("po_odpri"))
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

    def _drm_ponudi(self, pogled, url: str, sum_: bool = False) -> None:
        """Stran ima (morda) zasciten video: vrstica nad stranjo z gumbom »Predvajaj v Safeer DRM«. Brez klika se nic
        ne prenese in ne zazene (pregled 14. 10. 2026: prej je zastoj videa, napaka zapisa ali oglas v okvirju sam
        prenesel ~120 MB in zagnal Chromium na gostitelju)."""
        z = self._zavihek(pogled)
        if z is None or not url.startswith("https://") or z.get("drm") is not None or z.get("drm_prenos"):
            return
        prej = z.get("drm_ponudba")
        if prej and _gostitelj(prej[0]) == _gostitelj(url) and not prej[1]:
            sum_ = False                       # prava zahteva strani ima prednost pred sumom
        z["drm_ponudba"] = (url, sum_)
        if pogled is not self.trenutni():
            return                             # pokaze se, ko uporabnik izbere zavihek (izberi)
        self._pojavno = None
        self._drm_ponudba = (pogled, url)
        self.pojavna_napis.set_text(self._t("drm_sum" if sum_ else "drm_zahteva").format(
            stran=dovoljenja_strani.gostitelj(url) or url))
        self.pojavna_odpri.set_label(self._t("drm_predvajaj"))
        self.pojavna_vedno.set_visible(False)
        self.pojavna.set_reveal_child(True)

    def _drm_klik(self) -> None:
        """Uporabnik je kliknil »Predvajaj v Safeer DRM«: nastavitev strani »zavrni« velja, »vprasaj« vprasa."""
        pogled, url = self._drm_ponudba
        self._drm_ponudba = None
        self.pojavna.set_reveal_child(False)
        self.pojavna_odpri.set_label(self._t("po_odpri"))
        z = self._zavihek(pogled)
        if z is None:
            return
        z.pop("drm_ponudba", None)
        zdaj = pogled.get_uri() or ""
        if _gostitelj(zdaj) != _gostitelj(url):
            return                             # zavihek je medtem na drugi strani
        odl = dovoljenja_strani.odlocitev(self.config, zdaj, ["drm"])
        if odl == "zavrni":
            return

        def zazeni():
            if z in self.zavihki and _gostitelj(pogled.get_uri() or "") == _gostitelj(zdaj):
                if not self._drm_vdelaj(pogled, pogled.get_uri() or zdaj):
                    self._drm.odpri(pogled.get_uri() or zdaj)      # rezerva: namesceni brskalnik z Widevine
        if odl == "dovoli":
            zazeni(); return

        def odgovor(i):
            if i in (0, 1):
                dovoljenja_strani.zapomni(self.config, zdaj, ["drm"], "dovoli" if i == 1 else "zavrni")
            if i == 1:
                zazeni()
        self._vprasaj(self._t("dv_zahteva").format(stran=dovoljenja_strani.gostitelj(zdaj), kaj=self._t("dv_drm").lower()),
                      "", [self._t("zavrni"), self._t("dovoli")], odgovor)

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
        self._osvezi_zvezdico()
        self._osvezi_povecavo()

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

    def _zaznamek_za(self, uri: str):
        return next((p for p in self.config.get_portals() if p.get("url") == uri), None) if uri else None

    def dodaj_trenutno(self):
        """Zvezdica: doda zaznamek, ce ga stran se nima, sicer ga odstrani (kot Firefox; prej se je dodal vsakic znova)."""
        p = self.trenutni(); uri = p.get_uri() if p else ""
        if not uri or je_domaca_stran(uri, self.koren): return
        obstojeci = self._zaznamek_za(uri)
        if obstojeci is not None and obstojeci.get("id"):
            self.config.delete_portal(obstojeci["id"])
        else:
            self.config.add_portal(p.get_title() or urllib.parse.urlparse(uri).hostname or uri, uri)
        self._osvezi_zvezdico()

    def _osvezi_zvezdico(self):
        p = self.trenutni(); uri = p.get_uri() if p else ""
        ima = self._zaznamek_za(uri) is not None
        ikona = "starred-symbolic" if ima else "non-starred-symbolic"
        if self._ima_ikono(ikona):
            self.zvezdica.set_icon_name(ikona)
        else:
            self.zvezdica.set_label("★" if ima else "☆")
        self.zvezdica.set_tooltip_text(self._t("zaznamek_odstrani") if ima else self._t("dodaj"))

    def osvezi_povezavo(self):
        if self.stanje_povezave is None:   # samostojni Safeer Browser (safeer_brskalnik.py): brez oznake Linka
            self.povezava.set_visible(False)
            return False
        try: ok = (self.stanje_povezave() or {}).get("stanje") == "povezan"
        except Exception: ok = False
        self.povezava.set_text(("● " if ok else "○ ") + self._t("povezan" if ok else "nepovezan"))
        return True

    def _osvezi_scit(self):
        """Scit v orodni vrstici: izklopljena zascita na tej strani je vidna (kot Firefox)."""
        p = self.trenutni()
        izjema = p is not None and zascita.je_izjema(self.config, p.get_uri() or "")
        ikona = "security-low-symbolic" if izjema else "security-high-symbolic"
        try:
            if self._ima_ikono(ikona):
                self.scit.set_icon_name(ikona)
        except Exception:  # noqa: BLE001
            pass

    def _pokazi_scit(self):
        """Klik na scit: zascita na tej strani (vklop/izklop), stevec blokiranega, nastavitve zascite."""
        Gtk = self.Gtk
        p = self.trenutni()
        uri = p.get_uri() if p is not None else ""
        gost = zascita.gostitelj(uri) if (uri or "").startswith(("http://", "https://")) else ""
        pop = Gtk.Popover()
        pop.set_parent(self.scit)
        skatla = _robovi(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10), 12)
        skatla.set_size_request(320, -1)
        if gost:
            vrsta = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            napis = Gtk.Label(label=self._t("zas_na_strani").format(stran=gost), xalign=0, hexpand=True, wrap=True)
            stikalo = Gtk.Switch(active=not zascita.je_izjema(self.config, uri), valign=Gtk.Align.CENTER)
            vrsta.append(napis); vrsta.append(stikalo)
            skatla.append(vrsta)
            stanje = Gtk.Label(xalign=0); stanje.add_css_class("dim-label")
            stanje.set_text(self._t("zas_vklopljena") if stikalo.get_active() else self._t("zas_izklopljena"))
            skatla.append(stanje)

            def ob_stikalu(s, _l):
                if s.get_active() == (not zascita.je_izjema(self.config, uri)):
                    return
                vklop = zascita.preklopi_izjemo(self.config, uri)
                stanje.set_text(self._t("zas_vklopljena") if vklop else self._t("zas_izklopljena"))
                pop.popdown()
                self._zamenjaj_pogled(p, uri)       # skripte in seznam strani na novo, brez/z zascito
                self._osvezi_scit()
            stikalo.connect("notify::active", ob_stikalu)
        skatla.append(Gtk.Label(label=self._t("zas_blokirano").format(
            n=int(self.config.get("total_ads_blocked", 0) or 0) + int(self.config.get("total_threats_blocked", 0) or 0)),
            xalign=0))
        g = Gtk.Button(label=self._t("zas_nastavitve"))
        g.connect("clicked", lambda *_: (pop.popdown(), self._nastavitve()))
        skatla.append(g)
        opis = Gtk.Label(label=self._t("zas_ni_podatkov"), xalign=0, wrap=True); opis.add_css_class("dim-label")
        opis.set_max_width_chars(40)
        skatla.append(opis)
        pop.set_child(skatla)
        pop.connect("closed", lambda *_: self.GLib.idle_add(lambda: pop.unparent() or False))
        pop.popup()

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

    def _pravila_strani(self):
        """Samodejno predvajanje (nastavitve spletnih mest): WebKit ga sprejme le ob nastanku pogleda."""
        W = self.WebKit2
        try:
            nacin = {"dovoli": W.AutoplayPolicy.ALLOW, "brez_zvoka": W.AutoplayPolicy.ALLOW_WITHOUT_SOUND,
                     "blokiraj": W.AutoplayPolicy.DENY}[dovoljenja_strani.samodejno_predvajanje(self.config)]
            return W.WebsitePolicies(autoplay=nacin)
        except Exception:  # noqa: BLE001
            return None

    def _dovoljenje(self, pogled, zahteva):
        """Dovoljenja po straneh (core/dovoljenja_strani.py): zapomnjena odlocitev ali privzeto za vrsto, sicer vprasanje,
        ki se zapomni (kot Firefox). Prej ena nastavitev za vse strani in brez spomina."""
        uri = pogled.get_uri() or ""
        vrste = dovoljenja_strani.vrste_zahteve(zahteva, self.WebKit2)
        odl = dovoljenja_strani.odlocitev(self.config, uri, vrste)
        if odl == "dovoli":
            zahteva.allow(); return True
        if odl == "zavrni":
            zahteva.deny(); return True
        kaj = ", ".join(self._t("dv_" + v).lower() for v in vrste) or self._t("dovoljenje")
        stran = dovoljenja_strani.gostitelj(uri) or self._t("dovoljenje")

        def odgovor(i):
            if i == 1:
                zahteva.allow()
            else:
                zahteva.deny()
            if i in (0, 1):
                dovoljenja_strani.zapomni(self.config, uri, vrste, "dovoli" if i == 1 else "zavrni")
        # Zahteva ostane odprta, dokler uporabnik ne odgovori (WebKit to dovoli, ce signal vrne True).
        self._vprasaj(self._t("dv_zahteva").format(stran=stran, kaj=kaj), "", [self._t("zavrni"), self._t("dovoli")], odgovor)
        return True

    OBDOBJA = (("ura", 3600), ("dan", 86400), ("teden", 7 * 86400), ("vse", 0))
    VRSTE_BRISANJA = ("zgodovina", "piskotki", "predpomnilnik", "prenosi", "dovoljenja")

    def izbrisi(self, vrste, sekund: int = 0, ob_koncu=None) -> None:
        """Izbrise izbrane podatke brskanja za zadnjih `sekund` (0 = vse). Piskotki in predpomnilnik: WebKit asinhrono."""
        import datetime
        from core import zgodovina
        vrste = set(vrste)
        if "zgodovina" in vrste:
            od = datetime.datetime.now() - datetime.timedelta(seconds=sekund) if sekund else None
            zgodovina.pocisti(os.path.join(self.config.config_dir, "history.json"), od)
        if "prenosi" in vrste:
            self.prenosi[:] = [z for z in self.prenosi if z.get("stanje") == "tece"]
            self._osvezi_prenose()
        if "dovoljenja" in vrste:
            for k in ("dovoljenja_strani", "popup_dovoljeni", "external_app_permissions"):
                self.config.set(k, {} if k != "popup_dovoljeni" else [])
        W = self.WebKit2
        tipi = 0
        if "piskotki" in vrste:
            for ime in ("COOKIES", "LOCAL_STORAGE", "SESSION_STORAGE", "INDEXEDDB_DATABASES", "OFFLINE_APPLICATION_CACHE",
                        "SERVICE_WORKER_REGISTRATIONS", "DOM_CACHE", "HSTS_CACHE", "ITP"):
                tipi |= int(getattr(W.WebsiteDataTypes, ime, 0) or 0)
        if "predpomnilnik" in vrste:
            for ime in ("DISK_CACHE", "MEMORY_CACHE"):
                tipi |= int(getattr(W.WebsiteDataTypes, ime, 0) or 0)
        if not tipi:
            ob_koncu and ob_koncu()
            return
        try:
            upravitelj = self.seja.get_website_data_manager()
            upravitelj.clear(W.WebsiteDataTypes(tipi), sekund * 1_000_000, None,
                             lambda m, r, *_: (m.clear_finish(r), ob_koncu and ob_koncu()), None)
        except Exception as napaka:  # noqa: BLE001
            print("[Splet] brisanje podatkov:", napaka, flush=True)
            ob_koncu and ob_koncu()

    def pocisti_ob_izhodu(self, ob_koncu=None) -> None:
        """Brisanje ob izhodu (kot Firefox): brskalnik ob zaprtju okna, Splet ob koncu Safeer OS."""
        vrste = [v for v in (self.config.get("brisi_ob_izhodu", []) or []) if v in self.VRSTE_BRISANJA]
        if vrste:
            self.izbrisi(vrste, 0, ob_koncu)
        elif ob_koncu:
            ob_koncu()

    def _izbrisi_podatke(self, *_):
        Gtk = self.Gtk
        R = Gtk.ResponseType
        d, obmocje = self._dialog(self._t("bp_naslov"), 520, -1,
                                  gumbi=[(self._t("preklici"), R.CANCEL), (self._t("bp_izbrisi"), R.OK)])
        vsebina = _robovi(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8), 6)
        vrsta = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        vrsta.append(Gtk.Label(label=self._t("bp_obdobje"), xalign=0, hexpand=True))
        obdobje = Gtk.ComboBoxText()
        for k, _s in self.OBDOBJA:
            obdobje.append(k, self._t("bp_" + k))
        obdobje.set_active_id(str(self.config.get("brisi_obdobje", "ura")) if self.config.get("brisi_obdobje", "ura") in
                              [k for k, _ in self.OBDOBJA] else "ura")
        vrsta.append(obdobje); vsebina.append(vrsta)
        izbrane = set(self.config.get("brisi_vrste", ["zgodovina", "predpomnilnik"]) or [])
        stikala = {}
        for v in self.VRSTE_BRISANJA:
            c = Gtk.CheckButton(label=self._t("bp_" + v)); c.set_active(v in izbrane)
            stikala[v] = c; vsebina.append(c)
        ob_izhodu = Gtk.CheckButton(label=self._t("bp_ob_izhodu"))
        ob_izhodu.set_active(bool(self.config.get("brisi_ob_izhodu", [])))
        ob_izhodu.set_margin_top(8)
        vsebina.append(ob_izhodu)
        obmocje.append(vsebina)

        def odgovor(o):
            izbrane = [v for v, c in stikala.items() if c.get_active()]
            if o == R.OK:
                self.config.set("brisi_vrste", izbrane)
                self.config.set("brisi_obdobje", obdobje.get_active_id() or "ura")
                self.config.set("brisi_ob_izhodu", izbrane if ob_izhodu.get_active() else [])
                sekund = dict(self.OBDOBJA).get(obdobje.get_active_id() or "ura", 3600)
                self.izbrisi(izbrane, sekund, lambda: self._opozorilo(self._t("bp_naslov"), self._t("bp_koncano")))
            d.destroy()
        d.odgovor = odgovor
        d.present()

    def _dovoljenja_strani(self, *_):
        """Nastavitve spletnih mest: privzeto za vsako vrsto, strani z lastno nastavitvijo, samodejno predvajanje,
        pojavna okna, zunanji programi in strani brez zascite - vse na enem mestu, vse se da preklicati."""
        Gtk = self.Gtk
        d, obmocje = self._dialog(self._t("dv_naslov"), 640, 640)
        okvir = Gtk.ScrolledWindow(vexpand=True); okvir.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        vsebina = _robovi(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10), 12)
        okvir.set_child(vsebina); obmocje.append(okvir)

        def naslov(t):
            l = Gtk.Label(label=t, xalign=0); l.add_css_class("heading"); l.set_margin_top(8); vsebina.append(l)

        def izbira(moznosti, trenutna, ob):
            c = Gtk.ComboBoxText()
            for k, besedilo in moznosti:
                c.append(k, besedilo)
            c.set_active_id(trenutna)
            c.connect("changed", lambda c: ob(c.get_active_id()))
            return c

        odl = [(o, self._t("dv_" + o)) for o in dovoljenja_strani.ODLOCITVE]
        naslov(self._t("dv_privzeto"))
        mreza = Gtk.Grid(column_spacing=12, row_spacing=6)
        for i, v in enumerate(dovoljenja_strani.VRSTE):
            mreza.attach(Gtk.Label(label=self._t("dv_" + v), xalign=0, hexpand=True), 0, i, 1, 1)
            mreza.attach(izbira(odl, dovoljenja_strani.privzeto(self.config, v),
                                lambda o, v=v: dovoljenja_strani.nastavi_privzeto(self.config, v, o)), 1, i, 1, 1)
        vsebina.append(mreza)
        naslov(self._t("dv_samodejno"))
        vsebina.append(izbira([(o, self._t("dv_sp_" + o)) for o in dovoljenja_strani.SAMODEJNO],
                              dovoljenja_strani.samodejno_predvajanje(self.config),
                              lambda o: self.config.set("samodejno_predvajanje", o)))
        opis = Gtk.Label(label=self._t("dv_novi"), xalign=0); opis.add_css_class("dim-label"); vsebina.append(opis)

        naslov(self._t("dv_strani"))
        strani = dovoljenja_strani.seznam(self.config)
        if not strani:
            l = Gtk.Label(label=self._t("dv_ni_strani"), xalign=0); l.add_css_class("dim-label"); vsebina.append(l)
        for gost, dov in strani:
            vrsta = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            besedilo = gost + " — " + ", ".join("%s: %s" % (self._t("dv_" + k), self._t("dv_" + o)) for k, o in dov.items())
            l = Gtk.Label(label=besedilo, xalign=0, hexpand=True, wrap=True); vrsta.append(l)
            g = Gtk.Button(label=self._t("dv_pozabi"))
            g.connect("clicked", lambda _g, gost=gost, vrsta=vrsta: (dovoljenja_strani.pozabi_stran(self.config, gost),
                                                                    vsebina.remove(vrsta)))
            vrsta.append(g); vsebina.append(vrsta)

        def seznam_kljuca(naslov_k, kljuc, ob_odstrani):
            vrednost = self.config.get(kljuc, []) or []
            elementi = list(vrednost.keys()) if isinstance(vrednost, dict) else [str(x) for x in vrednost]
            if not elementi:
                return
            naslov(self._t(naslov_k))
            for el in elementi:
                vrsta = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                vrsta.append(Gtk.Label(label=el, xalign=0, hexpand=True))
                g = Gtk.Button(label=self._t("dv_odstrani"))
                g.connect("clicked", lambda _g, el=el, vrsta=vrsta: (ob_odstrani(el), vsebina.remove(vrsta)))
                vrsta.append(g); vsebina.append(vrsta)

        def odstrani_iz(kljuc):
            def f(el):
                v = self.config.get(kljuc, []) or []
                if isinstance(v, dict):
                    v = {k: x for k, x in v.items() if k != el}
                else:
                    v = [x for x in v if x != el]
                self.config.set(kljuc, v)
            return f
        seznam_kljuca("dv_pojavna", "popup_dovoljeni", odstrani_iz("popup_dovoljeni"))
        seznam_kljuca("dv_programi", "external_app_permissions", odstrani_iz("external_app_permissions"))
        seznam_kljuca("dv_zascita", "zascita_izjeme", odstrani_iz("zascita_izjeme"))
        d.present()

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
        vprasaj_kam = bool(self.config.get("always_ask_download_dir", False))
        if not splet_prenosi.je_izvrsljiv_prenos(ime):
            if vprasaj_kam:
                self._prenos_kam(prenos, mapa, ime)
            else:
                self._prenos_v(prenos, splet_prenosi.edinstvena_pot(mapa, ime))
            return True
        # Program ali namestitveni paket: stran ga ne sme podtakniti ob obisku. Prenos caka na odgovor (WebKit:
        # cilj se lahko nastavi kasneje, ce signal vrne True).
        def odgovor(i):
            if i == 1 and vprasaj_kam:
                self._prenos_kam(prenos, mapa, ime)
            elif i == 1:
                self._prenos_v(prenos, splet_prenosi.edinstvena_pot(mapa, ime))
            else:
                prenos.cancel()
        self._vprasaj(self._t("pr_program"), self._t("pr_program_opis").format(ime=ime, mapa=_kratka_pot(mapa)),
                      [self._t("pr_preklici"), self._t("pr_prenesi")], odgovor)
        return True

    def _ti(self, kljuc: str) -> str:
        """Besedila, ki so ze prevedena za Safeer Browser (core/i18n.py), v jeziku Spleta."""
        from core.i18n import TRANSLATIONS
        j = str(self.jezik() if callable(self.jezik) else self.jezik or "en")[:2]
        return TRANSLATIONS.get(j, {}).get(kljuc) or TRANSLATIONS.get("en", {}).get(kljuc) or kljuc

    def _zunanji_program(self, uri: str, shema: str, stran: str, kretnja: bool = True) -> None:
        """Povezava, ki pripada programu na racunalniku: vprasanje (stran ne sme odpirati programov brez vednosti),
        zapomni si »vedno« za stran in program, nato Gtk.UriLauncher (v Flatpaku portal, zunaj privzeti program).

        Najprej vrata vprasanj (eno hkrati, tiho po »Ne«), sele nato iskanje programa - v niti in z zapomnjenim
        izidom: gio mime / flatpak-spawn traja do 6 s in je prej tekel v niti GTK ob vsakem klicu, zato je stran, ki
        v zanki odpira mailto:, zamrznila vmesnik (pregled 14. 10. 2026)."""
        gostitelj = external_apps.site_of(stran)
        dovoljen = external_apps.is_allowed(self.config.get("external_app_permissions", {}), gostitelj, shema)
        if not hasattr(self, "_vrata_programov"):
            self._vrata_programov = external_apps.ExternalLinkGate()
        if not dovoljen and not self._vrata_programov.may_ask(gostitelj, shema):
            return
        if not hasattr(self, "_programi_shem"):
            self._programi_shem, self._iscem_sheme = {}, set()
        zapis = self._programi_shem.get(shema)
        # Najden program velja 10 min, »ni programa« 30 s (uporabnik ga medtem lahko namesti).
        if zapis is not None and time.monotonic() - zapis[0] < (600 if zapis[1] else 30):
            self._zunanji_program_nadaljuj(uri, shema, gostitelj, kretnja, zapis[1])
            return
        if shema in self._iscem_sheme:
            return                       # iskanje ze tece: nove zahteve iste sheme ne cakajo v vrsti
        self._iscem_sheme.add(shema)
        import threading

        def isci():
            try:
                from core import os_odpri_z
                program = os_odpri_z.program_za_shemo(shema)      # tudi v Flatpaku: program gostitelja
            except Exception as napaka:  # noqa: BLE001
                print("[Splet] program za", shema, napaka, flush=True)
                program = None

            def v_gui():
                self._iscem_sheme.discard(shema)
                self._programi_shem[shema] = (time.monotonic(), program)
                self._zunanji_program_nadaljuj(uri, shema, gostitelj, kretnja, program)
                return False
            self.GLib.idle_add(v_gui)
        threading.Thread(target=isci, name="safeer-program-sheme", daemon=True).start()

    def _zunanji_program_nadaljuj(self, uri: str, shema: str, gostitelj: str, kretnja: bool, program) -> None:
        if program is None:
            if kretnja:   # strani, ki le preverjajo, ali je program namescen (brez klika), ne dobijo obvestila
                self._ni_programa(gostitelj, shema)
            return
        if program["oznaka"].lower().startswith(("safeer", "io.github.memelandfaner")):
            return        # povezava bi vodila nazaj v Safeer
        ime = program["ime"]

        def odpri():
            try:
                if os.environ.get("FLATPAK_ID"):
                    # Program racunalnika neposredno (portal bi uporabnika vprasal se enkrat, katerega programa).
                    from core import os_dock
                    subprocess.Popen(os_dock._gostitelj(["gio", "open", uri]), stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                else:
                    self.Gtk.UriLauncher.new(uri).launch(self._okno_za_dialog(), None, None, None)
            except Exception as napaka:  # noqa: BLE001
                print("[Splet] zunanji program:", napaka, flush=True)
                self._ni_programa(gostitelj, shema)

        dovoljenja = self.config.get("external_app_permissions", {})
        if external_apps.is_allowed(dovoljenja, gostitelj, shema):
            odpri(); return
        if not hasattr(self, "_vrata_programov"):
            self._vrata_programov = external_apps.ExternalLinkGate()
        vrata = self._vrata_programov
        if not vrata.may_ask(gostitelj, shema):
            return
        vrata.asking()
        gumbi = [self._t("preklici"), self._ti("external_app_open")]
        if gostitelj:
            gumbi.append(self._ti("external_app_remember").format(site=gostitelj))

        def odgovor(i):
            vrata.answered(gostitelj, shema, i in (1, 2))
            if i == 2:
                self.config.set("external_app_permissions", external_apps.remember(
                    self.config.get("external_app_permissions", {}), gostitelj, shema))
            if i in (1, 2):
                odpri()
        self._vprasaj(self._ti("external_app_title").format(app=ime),
                      self._ti("external_app_body").format(site=gostitelj or self._ti("external_app_this_page"),
                                                           app=ime, scheme=shema), gumbi, odgovor)

    def _ni_programa(self, gostitelj: str, shema: str) -> None:
        kljuc = (gostitelj, shema)
        if not hasattr(self, "_ni_programa_pokazano"):
            self._ni_programa_pokazano = set()
        if kljuc in self._ni_programa_pokazano:
            return
        self._ni_programa_pokazano.add(kljuc)
        self._opozorilo(self._ti("external_app_missing_title"), self._ti("external_app_missing_body").format(scheme=shema))

    def _kontekstni_meni(self, _pogled, meni, zadetek, *_):
        """Meni desnega klika kot v Firefoxu (lastnik 14. 10. 2026: »Kopiraj« na povezavi ni kopiral nicesar - prav je
        »Kopiraj povezavo«): na povezavi brez izbranega besedila ni praznega »Kopiraj«, »Odpri v novem oknu« odpre
        nov zavihek (Splet nima oken), brez »Preglej element«."""
        W = self.WebKit2
        A = W.ContextMenuAction
        if getattr(self, "_dejanje_zavihek", None) is None:
            self._dejanje_zavihek = self.Gio.SimpleAction.new("splet-nov-zavihek", self.GLib.VariantType.new("s"))
            self._dejanje_zavihek.connect("activate", lambda _a, v: self.nov_zavihek(v.get_string()))
        povezava = zadetek.context_is_link()
        izbor = zadetek.context_is_selection()
        for postavka in list(meni.get_items()):
            dejanje = postavka.get_stock_action()
            if dejanje == A.COPY and povezava and not izbor:
                meni.remove(postavka)
            elif dejanje == A.INSPECT_ELEMENT:
                meni.remove(postavka)
            elif dejanje in (A.OPEN_LINK_IN_NEW_WINDOW, A.OPEN_IMAGE_IN_NEW_WINDOW, A.OPEN_VIDEO_IN_NEW_WINDOW,
                             A.OPEN_AUDIO_IN_NEW_WINDOW, A.OPEN_FRAME_IN_NEW_WINDOW):
                naslov = (zadetek.get_link_uri() if dejanje == A.OPEN_LINK_IN_NEW_WINDOW else
                          zadetek.get_image_uri() if dejanje == A.OPEN_IMAGE_IN_NEW_WINDOW else
                          zadetek.get_media_uri()) or ""
                if not naslov.startswith(("http://", "https://")):
                    continue
                kljuc = "kon_slika" if dejanje == A.OPEN_IMAGE_IN_NEW_WINDOW else "kon_povezava"
                nova = W.ContextMenuItem.new_from_gaction(self._dejanje_zavihek, self._t(kljuc),
                                                          self.GLib.Variant.new_string(naslov))
                i = list(meni.get_items()).index(postavka)
                meni.remove(postavka)
                meni.insert(nova, i)
        return False

    def _vrstica_skrij(self) -> None:
        """× v vrstici: ponudba Safeer DRM za to stran se ne vrne vec (dokler stran znova ne zaprosi)."""
        if getattr(self, "_drm_ponudba", None):
            z = self._zavihek(self._drm_ponudba[0])
            if z is not None:
                z.pop("drm_ponudba", None)
            self._drm_ponudba = None
        self.pojavna.set_reveal_child(False)

    def _vrstica_klik(self, vedno: bool) -> None:
        if getattr(self, "_drm_ponudba", None):
            self._drm_klik()
        else:
            self._pojavno_odpri(vedno)

    def _pojavno_blokirano(self, pogled, naslov: str) -> None:
        self._drm_ponudba = None
        self.pojavna_odpri.set_label(self._t("po_odpri"))
        self._pojavno = (pogled.get_uri() or "", naslov, pogled)
        stran = pojavna_okna.osnova(pojavna_okna.gostitelj(self._pojavno[0]))
        self.pojavna_napis.set_text(self._t("po_blokirano").format(cilj=pojavna_okna.gostitelj(naslov) or naslov))
        self.pojavna_vedno.set_label(self._t("po_vedno").format(stran=stran))
        self.pojavna_vedno.set_visible(bool(stran))
        self.pojavna.set_reveal_child(True)

    def _pojavno_odpri(self, vedno: bool) -> None:
        if not self._pojavno:
            return
        izvor, naslov, _p = self._pojavno
        self._pojavno = None
        self.pojavna.set_reveal_child(False)
        if vedno:
            self.config.set("popup_dovoljeni", pojavna_okna.zapomni(self.config.get("popup_dovoljeni", []), izvor))
        self.nov_zavihek(naslov)

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

    def _prenos_kam(self, prenos, mapa: str, ime: str) -> None:
        """Nastavitev »Vedno vprasaj, kam shraniti«: Gtk.FileDialog (v Flatpaku prek portala); preklic = brez prenosa."""
        try:
            dialog = self.Gtk.FileDialog()
            dialog.set_initial_folder(self.Gio.File.new_for_path(mapa))
            dialog.set_initial_name(ime)

            def koncano(dlg, rezultat, *_):
                try:
                    datoteka = dlg.save_finish(rezultat)
                except Exception:  # noqa: BLE001 - preklicano
                    datoteka = None
                pot = datoteka.get_path() if datoteka is not None else None
                if pot:
                    self._prenos_v(prenos, pot, prepisi=True)
                else:
                    prenos.cancel()
            dialog.save(self._okno_za_dialog(), None, koncano, None)
        except Exception as napaka:  # noqa: BLE001 - brez FileDialog: v mapo Prenosi
            print("[Splet] izbira mape prenosa:", napaka, flush=True)
            self._prenos_v(prenos, splet_prenosi.edinstvena_pot(mapa, ime))

    def _prenos_v(self, prenos, pot, prepisi: bool = False):
        je6 = hasattr(self.WebKit2, "NetworkSession")   # WebKitGTK 6.0: cilj je pot (4.1: URI)
        if prepisi:      # uporabnik je v izbirniku sam potrdil prepis obstojece datoteke
            prenos.set_allow_overwrite(True)
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
        p = self.trenutni()
        if not p:
            return
        fc = p.get_find_controller()
        niz = vnos.get_text()
        if not niz:
            fc.search_finish(); self.najdi_stevec.set_text(""); return
        W = self.WebKit2
        moznosti = int(W.FindOptions.CASE_INSENSITIVE) | int(W.FindOptions.WRAP_AROUND)
        fc.search(niz, moznosti, 1000)
        fc.count_matches(niz, moznosti, 1000)

    def _najdi_stevec(self, _fc, n):
        self.najdi_stevec.set_text(stevilo_zadetkov(n, str(self.jezik() if callable(self.jezik) else self.jezik or "en"))
                                   if n else self._t("ni_zadetkov"))
    def _povecava(self, korak):
        if self.trenutni(): self.trenutni().set_zoom_level(max(.5, min(3.0, self.trenutni().get_zoom_level() + korak)))
        self._osvezi_povecavo()

    def _osvezi_povecavo(self):
        """Gumb »110 %« v naslovni vrstici, ko stran ni v izvirni velikosti (kot Firefox); klik vrne na 100 %."""
        p = self.trenutni()
        raven = p.get_zoom_level() if p is not None else 1.0
        g = getattr(self, "gumb_povecave", None)
        if g is not None:
            g.set_label("%d %%" % round(raven * 100))
            g.set_visible(abs(raven - 1.0) > 0.01)

    def _osvezi_zvok(self, pogled):
        """Zavihek, ki predvaja zvok, ima zvocnik; klik nanj utisa ali vrne zvok (kot Firefox)."""
        z = self._zavihek(pogled)
        if z is None or z.get("zvok") is None:
            return
        igra = bool(pogled.get_property("is-playing-audio"))
        utisan = bool(pogled.get_is_muted())
        z["zvok"].set_visible(igra or utisan)
        z["zvok"].set_icon_name("audio-volume-muted-symbolic" if utisan else "audio-volume-high-symbolic")
        z["zvok"].set_tooltip_text(self._t("zvok" if utisan else "utisaj"))
    def _nastavitve(self, *_):
        """Nastavitve brskalnika po skupinah kot Firefox (lastnik 14. 10. 2026): Splosno, Zasebnost in varnost, Prenosi."""
        Gtk = self.Gtk
        R = Gtk.ResponseType
        d, obmocje = self._dialog(self._t("nastavitve"), 640, 620, gumbi=[(self._t("preklici"), R.CANCEL), (self._t("shrani"), R.OK)])
        zvezki = Gtk.Notebook(); zvezki.set_vexpand(True)

        def stran(naslov):
            okvir = Gtk.ScrolledWindow(); okvir.set_vexpand(True)
            okvir.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            m = _robovi(Gtk.Grid(column_spacing=12, row_spacing=10), 12)
            okvir.set_child(m)
            zvezki.append_page(okvir, Gtk.Label(label=naslov))
            return m

        def napis(besedilo, krepko=False, opis=False):
            l = Gtk.Label(label=besedilo, xalign=0, wrap=True)
            l.set_max_width_chars(60)
            if krepko:
                l.add_css_class("heading")
            if opis:
                l.add_css_class("dim-label")
            return l

        # ---- Splosno
        splosno = stran(self._t("nas_splosno"))
        motor = Gtk.ComboBoxText()
        for kljuc, podatki in SEARCH_ENGINES.items(): motor.append(kljuc, podatki["name"])
        motor.set_active_id(self.config.get("search_engine", "duckduckgo"))
        jezik = str(self.jezik() if callable(self.jezik) else self.jezik or "sl")
        temno = Gtk.ComboBoxText()
        for n in splet_temno.NACINI: temno.append(n, splet_temno.besedilo(jezik, n))
        temno.set_active_id(self._temno_nacin())
        strojno = Gtk.CheckButton(label=self._t("strojno"))
        strojno.set_active(self.config.get("hardware_acceleration", "on_demand") != "never")
        splosno.attach(napis(self._t("iskalnik")), 0, 0, 1, 1); splosno.attach(motor, 1, 0, 1, 1)
        splosno.attach(napis(splet_temno.besedilo(jezik, "nastavitev")), 0, 1, 1, 1); splosno.attach(temno, 1, 1, 1, 1)
        splosno.attach(strojno, 0, 2, 2, 1)
        privzeti = getattr(self, "privzeti", None)     # samo samostojni Safeer Browser (safeer_brskalnik.py)
        if privzeti is not None and not privzeti[0]():
            gumb_privzeti = Gtk.Button(label=privzeti[2]()[4])

            def ob_privzeti(g):
                ok, napake = privzeti[1]()
                g.set_label(privzeti[2]()[3] if ok else "; ".join(napake)[:120]); g.set_sensitive(not ok)
            gumb_privzeti.connect("clicked", ob_privzeti)
            splosno.attach(gumb_privzeti, 0, 3, 2, 1)

        # ---- Zasebnost in varnost
        zas = stran(self._t("nas_zasebnost"))
        vrsta = 0
        zas.attach(napis(self._t("zas_naslov"), krepko=True), 0, vrsta, 2, 1); vrsta += 1
        zdaj = zascita.raven(self.config)
        gumbi_ravni = {}
        skupina = None
        for ime, opis in (("obicajna", "zas_obicajna_opis"), ("stroga", "zas_stroga_opis"), ("po_meri", "")):
            g = Gtk.CheckButton(label=self._t("zas_" + ime))
            if skupina is not None:
                g.set_group(skupina)
            skupina = skupina or g
            g.set_active(ime == zdaj)
            gumbi_ravni[ime] = g
            zas.attach(g, 0, vrsta, 2, 1); vrsta += 1
            if opis:
                o = napis(self._t(opis), opis=True); o.set_margin_start(28)
                zas.attach(o, 0, vrsta, 2, 1); vrsta += 1
        po_meri = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6); po_meri.set_margin_start(28)
        stikala = {}
        for kljuc, besedilo in (("adblock_enabled", "zas_oglasi"), ("easylist_enabled", "zas_easylist"),
                                ("adguard_protection_enabled", "zas_adguard"), ("tracking_protection_enabled", "zas_parametri"),
                                ("gpc_dnt_enabled", "zas_gpc"), ("zascita_itp", "zas_itp"), ("zascita_brez_webrtc", "zas_webrtc")):
            c = Gtk.CheckButton(label=self._t(besedilo)); c.set_active(zascita.nastavitve(self.config)[kljuc])
            stikala[kljuc] = c; po_meri.append(c)
        po_meri.set_visible(zdaj == "po_meri")
        gumbi_ravni["po_meri"].connect("toggled", lambda g: po_meri.set_visible(g.get_active()))
        zas.attach(po_meri, 0, vrsta, 2, 1); vrsta += 1
        pojavna = Gtk.CheckButton(label=self._t("po_nastavitev")); pojavna.set_active(self.config.get("popup_blokiraj", True))
        zas.attach(pojavna, 0, vrsta, 2, 1); vrsta += 1
        # Izbira DNS (lastnik 14. 10. 2026: »ne pozabi na moznost menjave DNS«) - isti ponudniki kot Safeer Browser.
        doh = Gtk.ComboBoxText()
        for kljuc in ("quad9", "adguard", "cloudflare", "google", "custom", "disabled"):
            doh.append(kljuc, self._ti("doh_" + kljuc))
        izbran_dns = self.config.get("doh_provider", "cloudflare") if self.config.get("doh_enabled", True) else "disabled"
        doh.set_active_id(izbran_dns if izbran_dns in ("quad9", "adguard", "cloudflare", "google", "custom") else "disabled")
        lasten = Gtk.Entry(placeholder_text="https://dns.example/dns-query")
        lasten.set_text(self.config.get("custom_doh_url", "") or "")
        lasten.set_visible(doh.get_active_id() == "custom")
        doh.connect("changed", lambda c: lasten.set_visible(c.get_active_id() == "custom"))
        zas.attach(napis(self._t("doh"), krepko=True), 0, vrsta, 2, 1); vrsta += 1
        zas.attach(doh, 0, vrsta, 2, 1); vrsta += 1
        zas.attach(lasten, 0, vrsta, 2, 1); vrsta += 1
        for kljuc, dejanje in (("nas_dovoljenja", lambda *_: (d.destroy(), self._dovoljenja_strani())),
                               ("nas_brisi", lambda *_: (d.destroy(), self._izbrisi_podatke()))):
            g = Gtk.Button(label=self._t(kljuc)); g.set_halign(Gtk.Align.START); g.connect("clicked", dejanje)
            zas.attach(g, 0, vrsta, 2, 1); vrsta += 1
        zas.attach(napis(self._t("zas_ni_podatkov"), opis=True), 0, vrsta, 2, 1); vrsta += 1

        # ---- Prenosi
        pren = stran(self._t("prenosi"))
        pren.attach(napis(self._t("nas_mapa").format(mapa=_kratka_pot(splet_prenosi.mapa_prenosov(self.GLib)))), 0, 0, 2, 1)
        vprasaj = Gtk.CheckButton(label=self._t("nas_vprasaj_kam"))
        vprasaj.set_active(bool(self.config.get("always_ask_download_dir", False)))
        pren.attach(vprasaj, 0, 1, 2, 1)
        pren.attach(napis(self._t("nas_programi"), opis=True), 0, 2, 2, 1)

        obmocje.append(zvezki)

        def odgovor(o):
            if o == R.OK:
                self.config.set("search_engine", motor.get_active_id() or "duckduckgo")
                izbrana = next((ime for ime, g in gumbi_ravni.items() if g.get_active()), "obicajna")
                if izbrana == "po_meri":
                    for kljuc, c in stikala.items():
                        self.config.set(kljuc, c.get_active())
                else:
                    zascita.nastavi_raven(self.config, izbrana)
                dns = doh.get_active_id() or "cloudflare"
                url = lasten.get_text().strip()
                if dns == "custom" and not (url.startswith("https://") and len(url) > 12 and " " not in url):
                    dns = self.config.get("doh_provider", "cloudflare")      # neveljaven naslov: ostane prejsnji
                    dns = "cloudflare" if dns in ("custom", "disabled") else dns
                elif dns == "custom":
                    self.config.set("custom_doh_url", url)
                self.config.set("doh_enabled", dns != "disabled")
                self.config.set("doh_provider", dns)
                self.config.set("popup_blokiraj", pojavna.get_active())
                self.config.set("always_ask_download_dir", vprasaj.get_active())
                self.config.set("hardware_acceleration", "on_demand" if strojno.get_active() else "never")
                if (temno.get_active_id() or splet_temno.PRIVZETO) != self._temno_nacin():
                    self.config.set("temno_nacin", temno.get_active_id() or splet_temno.PRIVZETO)
                    self._temno_osvezi(znova_nalozi=self.trenutni())
                politika = politika_pospesevanja(self.WebKit2, self.config.get("hardware_acceleration"))
                for z in self.zavihki:
                    if not brez_pospesevanja(z["pogled"].get_uri() or "", self._ucene_brez_pospesevanja(), self._skia()):
                        z["pogled"].get_settings().set_hardware_acceleration_policy(politika)
                self._uporabi_zascito()
                self._nastavi_omrezje()
            d.destroy()
        d.odgovor = odgovor
        d.present()

    def _uporabi_zascito(self) -> None:
        """Stopnja zascite takoj: ITP na seji, WebRTC in seznam EasyList na vseh zavihkih; skripte (AdGuard, GPC) dobijo
        nove strani - trenutni zavihek se zato nalozi znova."""
        try:
            self.seja.set_itp_enabled(bool(self.config.get("zascita_itp", False)))
        except Exception:  # noqa: BLE001
            pass
        brez = bool(self.config.get("zascita_brez_webrtc", False))
        for z in self.zavihki:
            nast = z["pogled"].get_settings()
            if hasattr(nast, "set_enable_webrtc"):
                nast.set_enable_webrtc(not brez)
            self._filter_za(z["pogled"], z["pogled"].get_uri() or "")
        p = self.trenutni()
        if p is not None and (p.get_uri() or "").startswith(("http://", "https://")):
            self._zamenjaj_pogled(p, p.get_uri())

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
