"""Uporabniske skripte (.user.js) v Spletu (Safeer OS) in GTK4 Safeer Browserju - WebKitGTK 6.0.

Prenos iz GTK3 brskalnika (safeer_mint.py, umaknjen 18. 10. 2026), da uporabniki funkcije ne izgubijo. Ena shramba in
eno jedro za vse skripte (lastnik: ne dveh sistemov): shramba je core/uporabniske_skripte.py (ista kot »Moje skripte«
v Medijskem centru), glavo ==UserScript== bere core/userscripts.py. Ta modul jih le vgradi v zavihke in jih pokaze.

- Skripta tece samo na straneh iz svoje glave (@match/@include, @exclude, @run-at, @noframes) - WebKit jo vbrizga s
  seznamom dovoljenih in prepovedanih naslovov, nikoli z »vse« (glej userscripts.VSE_SPLETNE_STRANI): na notranjih
  straneh Safeerja (safeer://, zacetna stran, file://) ne tece nikoli.
- Tece v svojem svetu JavaScripta (SVET): stran je ne vidi, ona pa ne vidi mostu Safeerja (»safeer« v svetu strani)
  ne svetov zascite, temnega nacina, DRM in varuha odlozisca. V svojem svetu ima samo most shrambe GM_setValue (MOST).
- Kar uporabnik doda, je njegova odlocitev in odgovornost (lastnik, 15. in 18. 10. 2026): vsebine ne omejujemo, pred
  dodajanjem pa pove, kaj skripta zmore. Oznaka v naslovni vrstici pove, katere skripte tecejo na trenutni strani.
"""

from __future__ import annotations

import json
import weakref
from typing import Any, Dict, List

from core import uporabniske_skripte, userscripts

#: Svet skript (isti kot v GTK3 brskalniku) in most shrambe v njem.
SVET = "safeer-userscripts"
MOST = uporabniske_skripte.MOST_GM
#: Toliko imen pove namig oznake; ostale skrije »…«.
NAJVEC_IMEN = 5
#: Razred oznake v naslovni vrstici (barve iz assets/os/tokens.css).
RAZRED_ZNAKA = "splet-skripte-znak"

PREDLOGA = """// ==UserScript==
// @name         {ime}
// @match        https://example.com/*
// @run-at       document-end
// @grant        GM_addStyle
// ==/UserScript==

// Safeer: GM_addStyle, GM_getValue, GM_setValue, GM_deleteValue, GM_listValues, GM_log, GM_info.
GM_addStyle('body {{ }}');
"""

BESEDILA: Dict[str, Dict[str, str]] = {
    "sl": {
        "meni": "Uporabniške skripte …", "naslov": "Uporabniške skripte",
        "opis": "Skripte JavaScript (.user.js), ki jih dodaš sam. Tečejo na straneh, ki jih navaja njihova glava "
                "(@match, @include; @exclude strani izvzame), v ločenem svetu, ki ga stran ne vidi. Na notranjih "
                "straneh Safeerja ne tečejo nikoli. Safeer jih ne dostavlja in ne pregleda – odgovornost je tvoja.",
        "mapa": "Skripte so shranjene v mapi: {pot}", "prazno": "Ni dodanih skript.",
        "uvozi": "Uvozi datoteko …", "nova": "Nova skripta …",
        "pot": "Ali vpiši celotno pot do datoteke .js:", "uvozi_pot": "Uvozi s poti",
        "opozorilo": "»{ime}« bo lahko brala in spreminjala strani, ki jih navaja njena glava – tudi prijave in vse, "
                     "kar tam vpišeš. Dodaj jo samo, če ji zaupaš.",
        "potrdi": "Dodaj in vklopi", "preklici": "Prekliči", "uredi": "Uredi", "odstrani": "Odstrani",
        "vklop": "Vklopi skripto {ime}", "strani": "Teče na: {vzorci}", "povsod": "vseh spletnih straneh (http, https)",
        "razen": "Razen: {vzorci}",
        "spotify": "Brez glave ==UserScript==: teče samo v strani Spotify v Medijskem centru. Za spletne strani ji "
                   "dodaj glavo z @match.",
        "tudi_spotify": "Teče tudi v strani Spotify v Medijskem centru.",
        "manjka": "Ne teče: Safeer še nima {kaj}.",
        "ni_vzorca": "Ne teče: glava nima uporabnega @match ali @include (podprta sta http:// in https://).",
        "datoteka": "Datoteka: {pot}",
        "dodana": "»{ime}« je dodana in vklopljena. Velja ob naslednjem nalaganju strani.",
        "dodana_ne": "»{ime}« je dodana, a na spletnih straneh ne teče – razlog je napisan pri skripti.",
        "shranjena": "Skripta je shranjena. Velja ob naslednjem nalaganju strani.",
        "napaka_vrsta": "Podprte so samo datoteke JavaScript (.js).",
        "napaka_velikost": "Skripta je prevelika (največ 256 KB).",
        "napaka_pot": "Na tej poti ni datoteke .js v tvoji domači mapi.",
        "napaka_stevilo": "Skript je že 50 – največ, kar jih Safeer hrani.",
        "napaka": "Skripte ni mogoče shraniti.",
        "znak": "Uporabniške skripte na tej strani: {imena}",
        "urejevalnik": "Koda skripte", "shrani": "Shrani", "izberi": "Izberi skripto JavaScript",
    },
    "en": {
        "meni": "User scripts …", "naslov": "User scripts",
        "opis": "JavaScript scripts (.user.js) that you add yourself. They run on the pages listed in their header "
                "(@match, @include; @exclude leaves pages out), in a separate world the page cannot see. They never "
                "run on Safeer's internal pages. Safeer does not supply or review them – you are responsible.",
        "mapa": "Scripts are stored in the folder: {pot}", "prazno": "No scripts added.",
        "uvozi": "Import file …", "nova": "New script …",
        "pot": "Or type the full path to the .js file:", "uvozi_pot": "Import from path",
        "opozorilo": "“{ime}” will be able to read and change the pages listed in its header – including sign-ins "
                     "and everything you type there. Add it only if you trust it.",
        "potrdi": "Add and enable", "preklici": "Cancel", "uredi": "Edit", "odstrani": "Remove",
        "vklop": "Enable script {ime}", "strani": "Runs on: {vzorci}", "povsod": "all web pages (http, https)",
        "razen": "Except: {vzorci}",
        "spotify": "No ==UserScript== header: runs only in the Spotify page of the Media centre. Add a header with "
                   "@match to run it on web pages.",
        "tudi_spotify": "Also runs in the Spotify page of the Media centre.",
        "manjka": "Does not run: Safeer does not have {kaj} yet.",
        "ni_vzorca": "Does not run: the header has no usable @match or @include (http:// and https:// are supported).",
        "datoteka": "File: {pot}",
        "dodana": "“{ime}” has been added and enabled. It applies the next time a page loads.",
        "dodana_ne": "“{ime}” has been added but does not run on web pages – the reason is shown with the script.",
        "shranjena": "The script has been saved. It applies the next time a page loads.",
        "napaka_vrsta": "Only JavaScript files (.js) are supported.",
        "napaka_velikost": "The script is too large (256 KB at most).",
        "napaka_pot": "There is no .js file at this path in your home folder.",
        "napaka_stevilo": "There are already 50 scripts – the most Safeer keeps.",
        "napaka": "The script could not be saved.",
        "znak": "User scripts on this page: {imena}",
        "urejevalnik": "Script code", "shrani": "Save", "izberi": "Choose a JavaScript script",
    },
    "de": {
        "meni": "Benutzerskripte …", "naslov": "Benutzerskripte",
        "opis": "JavaScript-Skripte (.user.js), die du selbst hinzufügst. Sie laufen auf den Seiten, die ihr Kopf "
                "nennt (@match, @include; @exclude nimmt Seiten aus), in einer eigenen Welt, die die Seite nicht "
                "sieht. Auf internen Seiten von Safeer laufen sie nie. Safeer liefert und prüft sie nicht – die "
                "Verantwortung liegt bei dir.",
        "mapa": "Die Skripte sind in diesem Ordner gespeichert: {pot}", "prazno": "Keine Skripte hinzugefügt.",
        "uvozi": "Datei importieren …", "nova": "Neues Skript …",
        "pot": "Oder gib den vollständigen Pfad zur .js-Datei ein:", "uvozi_pot": "Aus Pfad importieren",
        "opozorilo": "„{ime}“ kann die Seiten lesen und ändern, die sein Kopf nennt – auch Anmeldungen und alles, "
                     "was du dort eingibst. Füge es nur hinzu, wenn du ihm vertraust.",
        "potrdi": "Hinzufügen und aktivieren", "preklici": "Abbrechen", "uredi": "Bearbeiten", "odstrani": "Entfernen",
        "vklop": "Skript {ime} aktivieren", "strani": "Läuft auf: {vzorci}", "povsod": "allen Webseiten (http, https)",
        "razen": "Außer: {vzorci}",
        "spotify": "Kein ==UserScript==-Kopf: läuft nur in der Spotify-Seite des Mediencenters. Füge einen Kopf mit "
                   "@match hinzu, damit es auf Webseiten läuft.",
        "tudi_spotify": "Läuft auch in der Spotify-Seite des Mediencenters.",
        "manjka": "Läuft nicht: Safeer hat {kaj} noch nicht.",
        "ni_vzorca": "Läuft nicht: Der Kopf hat kein verwendbares @match oder @include (unterstützt werden http:// "
                     "und https://).",
        "datoteka": "Datei: {pot}",
        "dodana": "„{ime}“ wurde hinzugefügt und aktiviert. Es gilt beim nächsten Laden einer Seite.",
        "dodana_ne": "„{ime}“ wurde hinzugefügt, läuft aber nicht auf Webseiten – der Grund steht beim Skript.",
        "shranjena": "Das Skript wurde gespeichert. Es gilt beim nächsten Laden einer Seite.",
        "napaka_vrsta": "Nur JavaScript-Dateien (.js) werden unterstützt.",
        "napaka_velikost": "Das Skript ist zu groß (höchstens 256 KB).",
        "napaka_pot": "Unter diesem Pfad gibt es in deinem Home-Ordner keine .js-Datei.",
        "napaka_stevilo": "Es gibt bereits 50 Skripte – mehr speichert Safeer nicht.",
        "napaka": "Das Skript konnte nicht gespeichert werden.",
        "znak": "Benutzerskripte auf dieser Seite: {imena}",
        "urejevalnik": "Code des Skripts", "shrani": "Speichern", "izberi": "JavaScript-Skript auswählen",
    },
    "es": {
        "meni": "Scripts de usuario …", "naslov": "Scripts de usuario",
        "opis": "Scripts JavaScript (.user.js) que añades tú. Se ejecutan en las páginas que indica su cabecera "
                "(@match, @include; @exclude deja páginas fuera), en un mundo aparte que la página no ve. Nunca se "
                "ejecutan en las páginas internas de Safeer. Safeer no los suministra ni los revisa: la "
                "responsabilidad es tuya.",
        "mapa": "Los scripts se guardan en la carpeta: {pot}", "prazno": "No hay scripts añadidos.",
        "uvozi": "Importar archivo …", "nova": "Nuevo script …",
        "pot": "O escribe la ruta completa del archivo .js:", "uvozi_pot": "Importar desde ruta",
        "opozorilo": "«{ime}» podrá leer y cambiar las páginas que indica su cabecera, incluidos los inicios de "
                     "sesión y todo lo que escribas en ellas. Añádelo solo si confías en él.",
        "potrdi": "Añadir y activar", "preklici": "Cancelar", "uredi": "Editar", "odstrani": "Quitar",
        "vklop": "Activar el script {ime}", "strani": "Se ejecuta en: {vzorci}",
        "povsod": "todas las páginas web (http, https)", "razen": "Excepto: {vzorci}",
        "spotify": "Sin cabecera ==UserScript==: solo se ejecuta en la página de Spotify del centro multimedia. "
                   "Añádele una cabecera con @match para usarlo en páginas web.",
        "tudi_spotify": "También se ejecuta en la página de Spotify del centro multimedia.",
        "manjka": "No se ejecuta: Safeer aún no tiene {kaj}.",
        "ni_vzorca": "No se ejecuta: la cabecera no tiene un @match o @include utilizable (se admiten http:// y "
                     "https://).",
        "datoteka": "Archivo: {pot}",
        "dodana": "«{ime}» se ha añadido y activado. Se aplica la próxima vez que se cargue una página.",
        "dodana_ne": "«{ime}» se ha añadido, pero no se ejecuta en páginas web: el motivo aparece junto al script.",
        "shranjena": "El script se ha guardado. Se aplica la próxima vez que se cargue una página.",
        "napaka_vrsta": "Solo se admiten archivos JavaScript (.js).",
        "napaka_velikost": "El script es demasiado grande (máximo 256 KB).",
        "napaka_pot": "No hay ningún archivo .js en esta ruta de tu carpeta personal.",
        "napaka_stevilo": "Ya hay 50 scripts, el máximo que guarda Safeer.",
        "napaka": "No se pudo guardar el script.",
        "znak": "Scripts de usuario en esta página: {imena}",
        "urejevalnik": "Código del script", "shrani": "Guardar", "izberi": "Elige un script JavaScript",
    },
    "fr": {
        "meni": "Scripts utilisateur …", "naslov": "Scripts utilisateur",
        "opis": "Scripts JavaScript (.user.js) que tu ajoutes toi-même. Ils s’exécutent sur les pages indiquées dans "
                "leur en-tête (@match, @include ; @exclude en retire), dans un monde à part que la page ne voit pas. "
                "Ils ne s’exécutent jamais sur les pages internes de Safeer. Safeer ne les fournit ni ne les "
                "vérifie : la responsabilité est la tienne.",
        "mapa": "Les scripts sont enregistrés dans le dossier : {pot}", "prazno": "Aucun script ajouté.",
        "uvozi": "Importer un fichier …", "nova": "Nouveau script …",
        "pot": "Ou saisis le chemin complet du fichier .js :", "uvozi_pot": "Importer depuis le chemin",
        "opozorilo": "« {ime} » pourra lire et modifier les pages indiquées dans son en-tête, y compris les "
                     "connexions et tout ce que tu y saisis. Ne l’ajoute que si tu lui fais confiance.",
        "potrdi": "Ajouter et activer", "preklici": "Annuler", "uredi": "Modifier", "odstrani": "Supprimer",
        "vklop": "Activer le script {ime}", "strani": "S’exécute sur : {vzorci}",
        "povsod": "toutes les pages web (http, https)", "razen": "Sauf : {vzorci}",
        "spotify": "Pas d’en-tête ==UserScript== : s’exécute seulement dans la page Spotify du centre multimédia. "
                   "Ajoute-lui un en-tête avec @match pour l’utiliser sur des pages web.",
        "tudi_spotify": "S’exécute aussi dans la page Spotify du centre multimédia.",
        "manjka": "Ne s’exécute pas : Safeer n’a pas encore {kaj}.",
        "ni_vzorca": "Ne s’exécute pas : l’en-tête n’a pas de @match ou @include utilisable (http:// et https:// "
                     "sont pris en charge).",
        "datoteka": "Fichier : {pot}",
        "dodana": "« {ime} » a été ajouté et activé. Il s’applique au prochain chargement d’une page.",
        "dodana_ne": "« {ime} » a été ajouté mais ne s’exécute pas sur les pages web : la raison est indiquée avec "
                     "le script.",
        "shranjena": "Le script a été enregistré. Il s’applique au prochain chargement d’une page.",
        "napaka_vrsta": "Seuls les fichiers JavaScript (.js) sont pris en charge.",
        "napaka_velikost": "Le script est trop volumineux (256 Ko au maximum).",
        "napaka_pot": "Aucun fichier .js à ce chemin dans ton dossier personnel.",
        "napaka_stevilo": "Il y a déjà 50 scripts, le maximum que Safeer conserve.",
        "napaka": "Le script n’a pas pu être enregistré.",
        "znak": "Scripts utilisateur sur cette page : {imena}",
        "urejevalnik": "Code du script", "shrani": "Enregistrer", "izberi": "Choisir un script JavaScript",
    },
    "it": {
        "meni": "Script utente …", "naslov": "Script utente",
        "opis": "Script JavaScript (.user.js) che aggiungi tu. Girano sulle pagine indicate nella loro intestazione "
                "(@match, @include; @exclude ne esclude alcune), in un mondo separato che la pagina non vede. Non "
                "girano mai sulle pagine interne di Safeer. Safeer non li fornisce né li controlla: la "
                "responsabilità è tua.",
        "mapa": "Gli script sono salvati nella cartella: {pot}", "prazno": "Nessuno script aggiunto.",
        "uvozi": "Importa file …", "nova": "Nuovo script …",
        "pot": "Oppure scrivi il percorso completo del file .js:", "uvozi_pot": "Importa dal percorso",
        "opozorilo": "«{ime}» potrà leggere e modificare le pagine indicate nella sua intestazione, compresi gli "
                     "accessi e tutto ciò che vi scrivi. Aggiungilo solo se ti fidi.",
        "potrdi": "Aggiungi e attiva", "preklici": "Annulla", "uredi": "Modifica", "odstrani": "Rimuovi",
        "vklop": "Attiva lo script {ime}", "strani": "Gira su: {vzorci}", "povsod": "tutte le pagine web (http, https)",
        "razen": "Tranne: {vzorci}",
        "spotify": "Senza intestazione ==UserScript==: gira solo nella pagina di Spotify del centro multimediale. "
                   "Aggiungi un'intestazione con @match per usarlo sulle pagine web.",
        "tudi_spotify": "Gira anche nella pagina di Spotify del centro multimediale.",
        "manjka": "Non gira: Safeer non ha ancora {kaj}.",
        "ni_vzorca": "Non gira: l'intestazione non ha un @match o @include utilizzabile (sono supportati http:// e "
                     "https://).",
        "datoteka": "File: {pot}",
        "dodana": "«{ime}» è stato aggiunto e attivato. Vale dal prossimo caricamento di una pagina.",
        "dodana_ne": "«{ime}» è stato aggiunto ma non gira sulle pagine web: il motivo è indicato accanto allo script.",
        "shranjena": "Lo script è stato salvato. Vale dal prossimo caricamento di una pagina.",
        "napaka_vrsta": "Sono supportati solo file JavaScript (.js).",
        "napaka_velikost": "Lo script è troppo grande (massimo 256 KB).",
        "napaka_pot": "Non c'è nessun file .js in questo percorso della tua cartella personale.",
        "napaka_stevilo": "Ci sono già 50 script, il massimo che Safeer conserva.",
        "napaka": "Impossibile salvare lo script.",
        "znak": "Script utente su questa pagina: {imena}",
        "urejevalnik": "Codice dello script", "shrani": "Salva", "izberi": "Scegli uno script JavaScript",
    },
}

#: Vnos menija Spleta (core/os_splet.BESEDILA, kljuc »skripte«).
MENI = {j: {"skripte": b["meni"]} for j, b in BESEDILA.items()}

#: Kljuc napake shrambe -> besedilo.
NAPAKE = {"vrsta": "napaka_vrsta", "velikost": "napaka_velikost", "pot": "napaka_pot", "ni_datoteke": "napaka_pot",
          "preveliko_stevilo": "napaka_stevilo"}


def besedilo(jezik: str, kljuc: str, **vrednosti) -> str:
    b = BESEDILA.get(str(jezik or "")[:2].lower(), BESEDILA["en"])
    niz = b.get(kljuc) or BESEDILA["en"].get(kljuc, kljuc)
    return niz.format(**vrednosti) if vrednosti else niz


def css(tokeni: dict) -> str:
    """CSS oznake iz assets/os/tokens.css ({ime: (r, g, b, a)}) - oznaka je na temni vrstici Spleta; brez tokenov prazno.
    Okno za upravljanje je v temi GTK (svetla ali temna): tam razreda teme dim-label in warning (kontrast po temi)."""
    def b(ime: str) -> str:
        r, g, m, a = tokeni[ime]
        return "rgba(%d,%d,%d,%.3f)" % (r, g, m, a)
    try:
        return (".%s { background: %s; color: %s; border: 1px solid %s; border-radius: 10px; padding: 1px 8px; "
                "margin: 6px 2px; min-height: 0; font-weight: 600; font-size: 12px; box-shadow: none; }\n"
                ".%s:hover { background: %s; }\n"
                ".%s:focus-visible { outline: 2px solid %s; outline-offset: 1px; }\n"
                % (RAZRED_ZNAKA, b("media-poudarek"), b("zelena"), b("rob"), RAZRED_ZNAKA, b("izbrano"),
                   RAZRED_ZNAKA, b("fokus")))
    except (KeyError, TypeError, ValueError):
        return ""


def opis_skripte(jezik: str, s: Dict[str, Any]) -> str:
    """Kje skripta tece (ali zakaj ne), po resnici - za seznam v Spletu."""
    p = s.get("pripravljeno") or {}
    if s.get("kje") == "spotify":
        return besedilo(jezik, "spotify")
    if p.get("napaka") == "manjkajoca_dovoljenja":
        return besedilo(jezik, "manjka", kaj=", ".join(p.get("manjka") or []))
    if p.get("napaka"):
        return besedilo(jezik, "ni_vzorca")
    dovoljeni = p.get("dovoljeni") or []
    vzorci = (besedilo(jezik, "povsod") if list(dovoljeni) == list(userscripts.VSE_SPLETNE_STRANI)
              else ", ".join(dovoljeni))
    deli = [besedilo(jezik, "strani", vzorci=vzorci)]
    # Izjeme iz glave (@exclude), ne nase notranje (te veljajo za vse skripte in so v opisu okna).
    izjeme = []
    for v in (p.get("glava") or {}).get("excludes") or []:
        w = userscripts.vzorec_v_webkit(v)
        if w is None or w:
            izjeme.append(w or "*://*/*")
    if izjeme:
        deli.append(besedilo(jezik, "razen", vzorci=", ".join(izjeme)))
    if s.get("kje") == "oboje":
        deli.append(besedilo(jezik, "tudi_spotify"))
    return " ".join(deli)


def _gradniki(g):
    """Vsi gradniki pod g (GTK4), po vrsti."""
    o = g.get_first_child()
    while o is not None:
        yield o
        yield from _gradniki(o)
        o = o.get_next_sibling()


def _js_vrednost(rezultat):
    """WebKit 6.0 da JavaScriptCore.Value, 4.1 JavascriptResult."""
    return rezultat.get_js_value() if hasattr(rezultat, "get_js_value") else rezultat


class SpletSkripte:
    """Skripte v zavihkih enega Spleta: vgradnja v upravitelja vsebine, most shrambe, oznaka in okno za upravljanje."""

    def __init__(self, splet) -> None:
        self._splet = weakref.ref(splet)
        self.Gtk, self.GLib, self.WebKit = splet.Gtk, splet.GLib, splet.WebKit2
        self.koren = splet.koren
        self._pripravljene = None          # [(skripta, WebKit.UserScript)] vklopljenih, ki tecejo na spletnih straneh
        self._prenova = 0
        self._okno = None                  # odprto okno za upravljanje (eno hkrati)
        self._d = None
        try:
            uporabniske_skripte.preseli_iz_nastavitev(splet.config)
        except Exception as napaka:  # noqa: BLE001 - selitev se ponovi ob naslednjem zagonu
            print("[Splet] selitev uporabniskih skript:", napaka, flush=True)
        uporabniske_skripte.ob_spremembi(self._sprememba)
        self.znak = self._zgradi_znak()
        self._namesti_css()

    # ------------------------------------------------------------------ pomocniki
    def jezik(self) -> str:
        s = self._splet()
        j = (s.jezik() if callable(s.jezik) else s.jezik) if s is not None else "sl"
        return str(j or "sl")[:2]

    def t(self, kljuc: str, **vrednosti) -> str:
        return besedilo(self.jezik(), kljuc, **vrednosti)

    def _pogledi(self) -> list:
        s = self._splet()
        return [z["pogled"] for z in list(getattr(s, "zavihki", []) or [])] if s is not None else []

    def _namesti_css(self) -> None:
        try:
            from core import os_lupina
            besedilo_css = css(os_lupina.tokeni())
            if not besedilo_css:
                return
            ponudnik = self.Gtk.CssProvider()
            try:
                ponudnik.load_from_string(besedilo_css)
            except AttributeError:  # GTK < 4.12
                ponudnik.load_from_data(besedilo_css, -1)
            s = self._splet()
            self.Gtk.StyleContext.add_provider_for_display(s.Gdk.Display.get_default(), ponudnik,
                                                            self.Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            self._css_ponudnik = ponudnik
        except Exception as napaka:  # noqa: BLE001 - brez sloga oznaka ostane berljiva v temi GTK
            print("[Splet] slog uporabniskih skript:", napaka, flush=True)

    # ------------------------------------------------------------------ vgradnja v zavihke
    def pripravljene(self) -> list:
        """Vklopljene skripte, ki tecejo na spletnih straneh, z enim WebKit.UserScript za vse zavihke."""
        if self._pripravljene is None:
            W = self.WebKit
            izid = []
            for s in uporabniske_skripte.skripte_js(self.koren):
                p = s["pripravljeno"]
                if not s["vklopljena"] or s["kje"] not in ("splet", "oboje") or p.get("napaka"):
                    continue
                try:
                    us = W.UserScript.new_for_world(
                        p["vir"],
                        W.UserContentInjectedFrames.ALL_FRAMES if p["vsi_okvirji"]
                        else W.UserContentInjectedFrames.TOP_FRAME,
                        W.UserScriptInjectionTime.START if p["run_at"] == "document-start"
                        else W.UserScriptInjectionTime.END,
                        SVET, p["dovoljeni"], p["prepovedani"])
                except Exception as napaka:  # noqa: BLE001
                    print("[Splet] skripta %s: %s" % (s["id"], napaka), flush=True)
                    continue
                izid.append((s, us))
            self._pripravljene = izid
        return self._pripravljene

    def namesti(self, pogled) -> None:
        """Skripte v upravitelja vsebine zavihka (ob vsakem novem pogledu in ob vsaki spremembi seznama)."""
        upravitelj = pogled.get_user_content_manager()
        if not getattr(pogled, "_safeer_skripte_most", False):
            pogled._safeer_skripte_most = True
            try:
                try:
                    upravitelj.register_script_message_handler(MOST, SVET)
                except TypeError:           # WebKit 4.1
                    upravitelj.register_script_message_handler_in_world(MOST, SVET)
                upravitelj.connect("script-message-received::" + MOST, self._sporocilo)
            except Exception as napaka:  # noqa: BLE001 - brez mosta skripta tece, le GM_setValue ne shrani
                print("[Splet] most uporabniskih skript:", napaka, flush=True)
            pogled.connect("load-changed", self._nalaganje)
        for us in getattr(pogled, "_safeer_skripte", None) or ():
            try:
                upravitelj.remove_script(us)
            except Exception:  # noqa: BLE001
                pass
        namescene = []
        for s, us in self.pripravljene():
            upravitelj.add_script(us)
            namescene.append(us)
        pogled._safeer_skripte = namescene
        pogled._safeer_skripte_podatki = [s for s, _us in self.pripravljene()]

    def _nalaganje(self, pogled, dogodek) -> None:
        """Ob nastanku dokumenta si zapomni, katere skripte WebKit vbrizga vanj - oznaka pove resnico za ta dokument
        (tudi ce se seznam med tem spremeni ali stran zamenja naslov s pushState)."""
        if dogodek != self.WebKit.LoadEvent.COMMITTED:
            return
        uri = pogled.get_uri() or ""
        pogled._safeer_skripte_tecejo = [s["naslov"] for s in getattr(pogled, "_safeer_skripte_podatki", None) or ()
                                         if userscripts.velja(s["pripravljeno"], uri)]
        s = self._splet()
        if s is not None and pogled is s.trenutni():
            self.osvezi_znak(pogled)

    def tecejo(self, pogled) -> List[str]:
        return list(getattr(pogled, "_safeer_skripte_tecejo", None) or []) if pogled is not None else []

    def osvezi_vse(self, *_a) -> bool:
        """Seznam se je spremenil: nove skripte v vseh zavihkih (veljajo ob naslednjem nalaganju strani)."""
        self._pripravljene = None
        for pogled in self._pogledi():
            try:
                self.namesti(pogled)
            except Exception as napaka:  # noqa: BLE001
                print("[Splet] osvezitev skript:", napaka, flush=True)
        return False

    def _sprememba(self) -> None:
        # Iz katerekoli niti (Medijski center klice shrambo iz mostu): delo v glavni niti GTK.
        self.GLib.idle_add(self.osvezi_vse)

    def _sporocilo(self, _upravitelj, rezultat) -> None:
        """GM_setValue / GM_deleteValue iz sveta skript. Sporocilu ne verjamemo: shramba pise samo v predal vklopljene
        skripte, ki obstaja, in samo vrednosti v mejah (uporabniske_skripte.shrani_vrednost)."""
        try:
            podatki = json.loads(_js_vrednost(rezultat).to_string())
        except Exception:  # noqa: BLE001
            return
        if not isinstance(podatki, dict) or not isinstance(podatki.get("payload"), dict):
            return
        sid, op, tovor = podatki.get("id"), podatki.get("op"), podatki["payload"]
        if op == "set":
            ok = uporabniske_skripte.shrani_vrednost(sid, tovor.get("key"), tovor.get("value"))
        elif op == "delete":
            ok = uporabniske_skripte.izbrisi_vrednost(sid, tovor.get("key"))
        else:
            return
        if ok:
            self._prenovi_kmalu()

    def _prenovi_kmalu(self) -> None:
        """Vrednosti so v skripti posnetek ob vbrizgu (GM_getValue je sinhron): po zapisu nov posnetek za naslednje
        nalaganje strani - en sam za niz zapisov."""
        if self._prenova:
            return

        def zdaj():
            self._prenova = 0
            self.osvezi_vse()
            return False
        self._prenova = self.GLib.timeout_add(400, zdaj)

    # ------------------------------------------------------------------ oznaka v naslovni vrstici
    def _zgradi_znak(self):
        Gtk = self.Gtk
        g = Gtk.Button(label="JS")
        g.set_has_frame(False)
        g.add_css_class(RAZRED_ZNAKA)
        g.set_valign(Gtk.Align.CENTER)
        g.set_visible(False)
        g.connect("clicked", lambda *_: self.pokazi())
        return g

    def osvezi_znak(self, pogled=None) -> None:
        s = self._splet()
        if pogled is None and s is not None:
            pogled = s.trenutni()
        imena = self.tecejo(pogled)
        self.znak.set_visible(bool(imena))
        if not imena:
            return
        self.znak.set_label("JS %d" % len(imena))
        seznam = ", ".join(imena[:NAJVEC_IMEN]) + (" …" if len(imena) > NAJVEC_IMEN else "")
        namig = self.t("znak", imena=seznam)
        self.znak.set_tooltip_text(namig)
        try:
            self.znak.update_property([self.Gtk.AccessibleProperty.LABEL], [namig])
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ okno za upravljanje
    def pokazi(self) -> None:
        """Seznam skript: vklop, urejanje, odstranitev, uvoz iz datoteke ali s poti, nova skripta."""
        s = self._splet()
        if s is None:
            return
        if self._okno is not None:
            self._okno.present()
            return
        Gtk = self.Gtk
        d, obmocje = s._dialog(self.t("naslov"), 700, 620)
        self._okno = d
        trenutni = s.trenutni()
        prej = self._za_naslov(trenutni)

        def napis(besedilo, razred=None, izbirno=False):
            l = Gtk.Label(label=besedilo, xalign=0, wrap=True)
            l.set_wrap_mode(s.Pango.WrapMode.WORD_CHAR)
            l.set_max_width_chars(80)
            l.set_selectable(izbirno)
            if razred:
                l.add_css_class(razred)
            return l

        obmocje.append(napis(self.t("opis")))
        obmocje.append(napis(self.t("mapa", pot=str(uporabniske_skripte.mapa())), "dim-label", True))
        okvir = Gtk.ScrolledWindow()
        okvir.set_vexpand(True)
        okvir.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        seznam = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        okvir.set_child(seznam)
        obmocje.append(okvir)
        sporocilo = napis("")
        sporocilo.set_visible(False)
        obmocje.append(sporocilo)
        potrditev = Gtk.Revealer()
        obmocje.append(potrditev)
        self._d = {"seznam": seznam, "sporocilo": sporocilo, "potrditev": potrditev, "napis": napis}

        gumbi = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        uvozi = Gtk.Button(label=self.t("uvozi"))
        uvozi.connect("clicked", lambda *_: self._izberi_datoteko())
        nova = Gtk.Button(label=self.t("nova"))
        nova.connect("clicked", lambda *_: self.uredi(None))
        gumbi.append(uvozi)
        gumbi.append(nova)
        obmocje.append(gumbi)
        obmocje.append(napis(self.t("pot")))
        vrsta_poti = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        pot = Gtk.Entry()
        pot.set_hexpand(True)
        pot.set_placeholder_text(uporabniske_skripte.primer_poti())      # celotna pot, nikoli »~«
        pot.update_property([Gtk.AccessibleProperty.LABEL], [self.t("pot")])
        po_poti = Gtk.Button(label=self.t("uvozi_pot"))
        vrsta_poti.append(pot)
        vrsta_poti.append(po_poti)
        obmocje.append(vrsta_poti)

        def s_poti(*_):
            besedilo_poti = pot.get_text().strip()
            if not besedilo_poti:
                pot.grab_focus()
                return
            r = uporabniske_skripte.preberi_pot(besedilo_poti)
            if r.get("ok") and uporabniske_skripte.vrsta_iz_imena(r["ime"]) != "js":
                r = {"ok": False, "napaka": "vrsta"}
            if not r.get("ok"):
                self._sporoci(self.t(NAPAKE.get(r.get("napaka"), "napaka")), napaka=True)
                return
            self._ponudi(r["ime"], r["vsebina"])
        po_poti.connect("clicked", s_poti)
        pot.connect("activate", s_poti)

        def zaprto(*_):
            self._okno = None
            self._d = None
            # Sprememba, ki zadeva trenutno stran, se vidi takoj: stran se nalozi znova (kot pri stopnji zascite).
            if trenutni is not None and trenutni in self._pogledi() and self._za_naslov(trenutni) != prej:
                uri = trenutni.get_uri() or ""
                if uri.startswith(("http://", "https://")):
                    trenutni.reload()
        d.connect("destroy", zaprto)
        self._narisi()
        # Prvi fokus na dejanje, ne na izbirno besedilo (to bi se ob odprtju oznacilo v celoti).
        prvo = next((g for g in _gradniki(seznam) if isinstance(g, Gtk.Switch)), uvozi)
        d.set_focus(prvo)
        d.present()

    def _za_naslov(self, pogled) -> list:
        """Skripte (id in koda), ki bi tekle na strani pogleda - za ponovno nalaganje po spremembi ali urejanju.
        Vrednosti GM_setValue niso zraven: zapis strani med odprtim oknom je ne nalozi znova."""
        uri = (pogled.get_uri() or "") if pogled is not None else ""
        return [(s["id"], s["koda"]) for s, _us in self.pripravljene() if userscripts.velja(s["pripravljeno"], uri)]

    def _sporoci(self, besedilo_sporocila: str, napaka: bool = False) -> None:
        d = getattr(self, "_d", None)
        if d:
            d["sporocilo"].set_text(besedilo_sporocila)
            d["sporocilo"].set_visible(bool(besedilo_sporocila))
            (d["sporocilo"].add_css_class if napaka else d["sporocilo"].remove_css_class)("warning")

    def _narisi(self) -> None:
        d = getattr(self, "_d", None)
        if not d:
            return
        Gtk, seznam, napis = self.Gtk, d["seznam"], d["napis"]
        otrok = seznam.get_first_child()
        while otrok is not None:
            naslednji = otrok.get_next_sibling()
            seznam.remove(otrok)
            otrok = naslednji
        skripte = uporabniske_skripte.skripte_js(self.koren)
        if not skripte:
            seznam.append(napis(self.t("prazno"), "dim-label"))
        jezik = self.jezik()
        for s in skripte:
            vrsta = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            vrh = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            ime = Gtk.Label(label=s["naslov"], xalign=0, hexpand=True)
            ime.add_css_class("heading")
            ime.set_ellipsize(self._splet().Pango.EllipsizeMode.END)
            stikalo = Gtk.Switch(active=bool(s["vklopljena"]), valign=Gtk.Align.CENTER)
            stikalo.update_property([Gtk.AccessibleProperty.LABEL], [self.t("vklop", ime=s["naslov"])])
            stikalo.connect("notify::active", lambda g, _p, sid=s["id"]: self._vklopi(sid, g.get_active()))
            uredi = Gtk.Button(label=self.t("uredi"))
            uredi.update_property([Gtk.AccessibleProperty.LABEL], ["%s: %s" % (self.t("uredi"), s["naslov"])])
            uredi.connect("clicked", lambda *_a, sid=s["id"]: self.uredi(sid))
            odstrani = Gtk.Button(label=self.t("odstrani"))
            odstrani.update_property([Gtk.AccessibleProperty.LABEL], ["%s: %s" % (self.t("odstrani"), s["naslov"])])
            odstrani.connect("clicked", lambda *_a, sid=s["id"]: self._odstrani(sid))
            for g in (ime, stikalo, uredi, odstrani):
                vrh.append(g)
            vrsta.append(vrh)
            vrsta.append(napis(opis_skripte(jezik, s), "dim-label", True))
            vrsta.append(napis(self.t("datoteka", pot=s["pot"]), "dim-label", True))
            seznam.append(vrsta)

    def _vklopi(self, sid: str, da: bool) -> None:
        r = uporabniske_skripte.vklopi(sid, da)
        if not r.get("ok"):
            self._sporoci(self.t("napaka"), napaka=True)
        self.osvezi_vse()

    def _odstrani(self, sid: str) -> None:
        uporabniske_skripte.odstrani(sid)
        self.osvezi_vse()
        self._narisi()

    # ------------------------------------------------------------------ dodajanje
    def _izberi_datoteko(self) -> None:
        """Gtk.FileDialog (v Flatpaku prek portala - brskalnik nima dostopa do celega doma)."""
        s = self._splet()
        Gtk, Gio = self.Gtk, s.Gio
        try:
            dialog = Gtk.FileDialog()
            dialog.set_title(self.t("izberi"))
            filtri = Gio.ListStore.new(Gtk.FileFilter)
            f = Gtk.FileFilter()
            f.set_name("JavaScript (.js)")
            f.add_pattern("*.js")
            f.add_mime_type("text/javascript")
            f.add_mime_type("application/javascript")
            filtri.append(f)
            dialog.set_filters(filtri)
            dialog.set_default_filter(f)
        except Exception as napaka:  # noqa: BLE001
            print("[Splet] izbira skripte:", napaka, flush=True)
            return

        def izbrano(dlg, rezultat, *_):
            try:
                datoteka = dlg.open_finish(rezultat)
            except Exception:  # noqa: BLE001 - preklicano
                return
            if datoteka is None:
                return
            try:
                velikost = datoteka.query_info("standard::size", Gio.FileQueryInfoFlags.NONE, None).get_size()
            except Exception:  # noqa: BLE001
                velikost = 0
            if velikost > uporabniske_skripte.NAJVEC_BAJTOV:
                self._sporoci(self.t("napaka_velikost"), napaka=True)
                return
            ime = datoteka.get_basename() or "skripta.js"
            if uporabniske_skripte.vrsta_iz_imena(ime) != "js":
                self._sporoci(self.t("napaka_vrsta"), napaka=True)
                return

            def prebrano(dat, rez, *_a):
                try:
                    ok, vsebina, _etag = dat.load_contents_finish(rez)
                    besedilo_skripte = bytes(vsebina).decode("utf-8") if ok else ""
                except Exception:  # noqa: BLE001
                    besedilo_skripte = ""
                if not besedilo_skripte:
                    self._sporoci(self.t("napaka"), napaka=True)
                    return
                self._ponudi(ime, besedilo_skripte)
            datoteka.load_contents_async(None, prebrano, None)
        dialog.open(getattr(self, "_okno", None) or s._okno_za_dialog(), None, izbrano, None)

    def _ponudi(self, ime: str, vsebina: str) -> None:
        """Opozorilo pred dodajanjem (kaj skripta zmore); sele »Dodaj in vklopi« jo shrani."""
        d = getattr(self, "_d", None)
        if not d:
            return
        Gtk = self.Gtk
        glava = userscripts.razclenii_glavo(vsebina)
        prikaz = glava.get("name") or ime
        okvir = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        okvir.append(d["napis"](self.t("opozorilo", ime=prikaz), "warning"))
        gumbi = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        da = Gtk.Button(label=self.t("potrdi"))
        ne = Gtk.Button(label=self.t("preklici"))
        gumbi.append(da)
        gumbi.append(ne)
        okvir.append(gumbi)
        d["potrditev"].set_child(okvir)
        d["potrditev"].set_reveal_child(True)

        def skrij():
            d["potrditev"].set_reveal_child(False)
            d["potrditev"].set_child(None)

        def dodaj(*_):
            skrij()
            self._dodaj(ime, vsebina, prikaz)
        da.connect("clicked", dodaj)
        ne.connect("clicked", lambda *_: skrij())
        ne.grab_focus()

    def _dodaj(self, ime: str, vsebina: str, prikaz: str) -> None:
        r = uporabniske_skripte.uvozi(ime, vsebina, "js")
        if not r.get("ok"):
            self._sporoci(self.t(NAPAKE.get(r.get("napaka"), "napaka")), napaka=True)
            return
        # Uporabnik je skripto izbral in potrdil opozorilo: vklopi se, ce na spletnih straneh lahko tece.
        if uporabniske_skripte.kje(vsebina) in ("splet", "oboje"):
            uporabniske_skripte.vklopi(r["skripta"]["id"], True)
            self._sporoci(self.t("dodana", ime=prikaz))
        else:
            self._sporoci(self.t("dodana_ne", ime=prikaz), napaka=True)
        self.osvezi_vse()
        self._narisi()

    def uredi(self, sid) -> None:
        """Urejevalnik kode (kot v GTK3 brskalniku): nova skripta iz predloge ali sprememba obstojece."""
        s = self._splet()
        Gtk = self.Gtk
        obstojeca = next((x for x in uporabniske_skripte.skripte_js(self.koren) if x["id"] == sid), None) if sid else None
        d, obmocje = s._dialog(obstojeca["naslov"] if obstojeca else self.t("nova").rstrip(" …"), 720, 560,
                               gumbi=[(self.t("preklici"), Gtk.ResponseType.CANCEL), (self.t("shrani"), Gtk.ResponseType.OK)])
        d.set_transient_for(getattr(self, "_okno", None) or s._okno_za_dialog())
        obmocje.append(Gtk.Label(label=self.t("urejevalnik"), xalign=0))
        okvir = Gtk.ScrolledWindow()
        okvir.set_vexpand(True)
        koda = Gtk.TextView(monospace=True)
        koda.set_wrap_mode(Gtk.WrapMode.NONE)
        koda.update_property([Gtk.AccessibleProperty.LABEL], [self.t("urejevalnik")])
        koda.get_buffer().set_text(obstojeca["koda"] if obstojeca else PREDLOGA.format(ime=self.t("nova").rstrip(" …")))
        okvir.set_child(koda)
        obmocje.append(okvir)
        izid = Gtk.Label(xalign=0, wrap=True)
        izid.add_css_class("warning")
        obmocje.append(izid)

        def odgovor(o):
            if o != Gtk.ResponseType.OK:
                d.destroy()
                return
            b = koda.get_buffer()
            besedilo_kode = b.get_text(b.get_start_iter(), b.get_end_iter(), True)
            if obstojeca:
                r = uporabniske_skripte.posodobi(obstojeca["id"], besedilo_kode)
            else:
                ime = userscripts.razclenii_glavo(besedilo_kode).get("name") or "skripta"
                r = uporabniske_skripte.uvozi(ime, besedilo_kode, "js")
                if r.get("ok") and uporabniske_skripte.kje(besedilo_kode) in ("splet", "oboje"):
                    uporabniske_skripte.vklopi(r["skripta"]["id"], True)
            if not r.get("ok"):
                izid.set_text(self.t(NAPAKE.get(r.get("napaka"), "napaka")))
                return
            d.destroy()
            self.osvezi_vse()
            self._sporoci(self.t("shranjena"))
            self._narisi()
        d.odgovor = odgovor
        d.present()
        koda.grab_focus()
