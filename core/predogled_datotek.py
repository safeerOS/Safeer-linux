"""Predogled datotek brez GTK: kaj je datoteka, ali je nevarna in kaj pokazati (PDF, slika, besedilo, varen HTML).

Skupen za Sporocila (priponke) in za vsak drug del Safeer OS, ki hoce pokazati datoteko, ne da bi uporabnik zapustil
Safeer (namizje QML, Datoteke). Okno, ki to pokaze, je core/os_predogled.py (GTK4 + WebKitGTK 6.0, isti proces).

Kako (izmerjeno 15. 10. 2026, WebKitGTK 2.52.6, Xvfb):
* PDF pokaze WebKit sam (vgrajeni PDF.js, »webkit-pdfjs-viewer://«): stran nalozena v 1,6 s skupaj z zagonom spletnega
  procesa, iskanje, povecava in tiskanje brez dodatnih programov. PDF.js potrebuje JavaScript - zato tece v svojem
  pogledu brez mostu, brez omrezja in brez piskotkov (os_predogled.py). Isti WebKit je v Flatpaku (nasa gradnja,
  packaging/webkit) in na gostitelju (libwebkitgtk-6.0), zato ni razlike med njima (zivo preverjeno v Flatpaku 0.4.84,
  WebKitGTK 2.54.1: PDF.js prebere vse strani priponke). Poppler (pdftoppm, v svojem procesu) naredi samo slicico prve
  strani za cip priponke in Datoteke (core/os_datoteke.slika_prve_strani).
* DOC/DOCX/ODT/XLS(X)/ODS/PPT(X)/ODP/RTF: LibreOffice brez okna v PDF (txt->pdf 1,9 s ob prvem zagonu) in potem kot
  PDF. V Flatpaku LibreOffice tece na racunalniku prek /app/host-bin/soffice (core/os_pretvorba_datotek.orodje),
  datoteka je zato v ~/.cache racunalnika. Brez LibreOffice: besedilo iz DOCX/ODF/PPTX/XLSX (zip + XML), sicer jasno
  sporocilo in gumb »Odpri v programu« - nikoli prazno okno.
* Slike, besedilo, CSV, HTML in posredovana pisma (.eml): stran brez JavaScripta; HTML je preciscen (brez skript,
  okvirjev, obrazcev, oddaljenih slik), dodatno ga varujeta CSP in pogled brez omrezja.
* Programi in dokumenti z makri: brez predogleda, z opozorilom kot v Gmailu; odpreti jih je mogoce samo po potrditvi.
"""
from __future__ import annotations

import csv
import hashlib
import html as _html
import io
import os
import re
import shutil
import threading
import time
import zipfile
from html.parser import HTMLParser
from typing import Callable, Dict, Optional
from xml.etree import ElementTree

from core import splet_prenosi

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
#: Predpomnilnik priponk in pretvorb: v domu racunalnika (ne v peskovniku Flatpaka), da ga vidi LibreOffice na
#: racunalniku in program, s katerim uporabnik datoteko odpre.
NAJVEC_PREDPOMNILNIK = 400 * 1024 * 1024
STAROST_PREDPOMNILNIK_S = 7 * 24 * 3600
NAJVEC_BESEDILO = 2 * 1024 * 1024
NAJVEC_VRSTIC_TABELE = 2000
CAS_PRETVORBE_S = 90

SLIKE = (".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".gif", ".webp", ".bmp", ".svg", ".avif", ".ico")
DOKUMENTI = (".doc", ".docx", ".docm", ".dot", ".dotx", ".odt", ".ott", ".rtf", ".xls", ".xlsx", ".xlsm", ".ods",
             ".ots", ".ppt", ".pptx", ".pptm", ".pps", ".ppsx", ".odp", ".otp", ".odg", ".wpd", ".pages")
BESEDILA = (".txt", ".log", ".md", ".json", ".xml", ".ini", ".conf", ".cfg", ".yaml", ".yml", ".ics", ".vcf", ".diff",
            ".patch", ".srt", ".vtt", ".asc", ".pem")
TABELE = (".csv", ".tsv")
HTML = (".html", ".htm", ".xhtml")
POSTA = (".eml",)

#: Programi, skripte in vse, kar se ob dvojnem kliku zazene - kot seznam, ki ga Gmail ne dovoli odpreti.
NEVARNE_KONCNICE = tuple(sorted(set(splet_prenosi.IZVRSLJIVE_KONCNICE) | {
    ".com", ".scr", ".pif", ".cpl", ".msc", ".msp", ".mst", ".hta", ".js", ".jse", ".vbs", ".vbe", ".wsf", ".wsh",
    ".ws", ".lnk", ".reg", ".inf", ".scf", ".gadget", ".application", ".appref-ms", ".psm1", ".py", ".pyw", ".pl",
    ".rb", ".php", ".jar", ".jnlp", ".command", ".action", ".workflow", ".csh", ".ksh", ".zsh", ".bash", ".elf",
    ".so", ".ko", ".xpi", ".crx", ".iso", ".img", ".vhd", ".vhdx", ".library-ms", ".settingcontent-ms", ".url",
    ".docm", ".dotm", ".xlsm", ".xltm", ".xlam", ".pptm", ".potm", ".ppam", ".ppsm", ".sldm", ".xll", ".xla"}))
NEVARNI_TIPI = {"application/x-msdownload", "application/x-ms-dos-executable", "application/x-executable",
                "application/x-sharedlib", "application/x-sh", "application/x-shellscript", "application/x-desktop",
                "application/java-archive", "application/x-java-archive", "application/vnd.microsoft.portable-executable",
                "application/x-msi", "application/x-ms-installer", "application/vnd.ms-word.document.macroenabled.12",
                "application/vnd.ms-excel.sheet.macroenabled.12", "application/vnd.ms-powerpoint.presentation.macroenabled.12",
                "application/x-appimage", "application/vnd.debian.binary-package", "application/x-rpm",
                "application/javascript", "text/javascript", "application/x-python-code", "text/x-python"}
#: Dokument z makri: predogled (LibreOffice pretvorbe makrov ne zaganja) je dovoljen, odpiranje v programu pa ne brez
#: potrditve.
MAKRO_KONCNICE = (".docm", ".dotm", ".xlsm", ".xltm", ".pptm", ".potm", ".ppsm", ".sldm")

BESEDILA_PREDOGLEDA = {
    "sl": {"slike_vrstica": "Slike so skrite zaradi zasebnosti", "slike_prikazi": "Prikaži slike", "slike_vedno": "Vedno prikaži od {od}", "prenesi": "Prenesi", "odpri": "Odpri v programu", "mapa": "Pokaži v mapi", "zapri": "Zapri",
           "pripravljam": "Pripravljam predogled …", "nevarno_naslov": "Ta datoteka je lahko nevarna",
           "nevarno": "»{ime}« je program, skripta ali dokument z makri. Take datoteke lahko škodijo računalniku, zato jih Safeer ne prikaže. Odpri jo samo, če pošiljatelju zaupaš in jo pričakuješ.",
           "brez_naslov": "Predogled ni na voljo", "brez": "Te vrste datoteke ({vrsta}) Safeer ne zna prikazati. Prenesi jo ali jo odpri v programu.",
           "brez_lo": "Za predogled dokumentov Office in ODF namesti LibreOffice (Upravitelj programov). Do takrat lahko dokument odpreš v programu.",
           "napaka": "Datoteke ni bilo mogoče prebrati.", "ni_povezave": "Priponke ni bilo mogoče prenesti. Preveri povezavo in poskusi znova.", "brez_oblike": "Predogled brez oblikovanja – za popoln predogled namesti LibreOffice.",
           "slike_skrite": "Slike s spleta so zaradi zasebnosti skrite (pošiljatelj ne izve, da si pismo odprl).",
           "od": "Od", "za": "Za", "datum": "Datum", "zadeva": "Zadeva", "priponke": "Priponke",
           "skrajsano": "Prikazan je samo začetek datoteke.", "shranjeno": "Shranjeno v Prejemi: {ime}"},
    "en": {"slike_vrstica": "Images are hidden for your privacy", "slike_prikazi": "Show images", "slike_vedno": "Always show from {od}", "prenesi": "Download", "odpri": "Open in app", "mapa": "Show in folder", "zapri": "Close",
           "pripravljam": "Preparing preview …", "nevarno_naslov": "This file may be dangerous",
           "nevarno": "“{ime}” is a program, a script or a document with macros. Files like this can harm your computer, so Safeer does not show them. Open it only if you trust the sender and expect it.",
           "brez_naslov": "No preview available", "brez": "Safeer cannot show this kind of file ({vrsta}). Download it or open it in an app.",
           "brez_lo": "To preview Office and ODF documents, install LibreOffice (Software Manager). Until then you can open the document in an app.",
           "napaka": "The file could not be read.", "ni_povezave": "The attachment could not be downloaded. Check the connection and try again.", "brez_oblike": "Preview without formatting – install LibreOffice for a full preview.",
           "slike_skrite": "Images from the web are hidden for your privacy (the sender does not learn that you opened the email).",
           "od": "From", "za": "To", "datum": "Date", "zadeva": "Subject", "priponke": "Attachments",
           "skrajsano": "Only the beginning of the file is shown.", "shranjeno": "Saved to Downloads: {ime}"},
    "de": {"slike_vrstica": "Bilder sind zum Schutz der Privatsphäre ausgeblendet", "slike_prikazi": "Bilder anzeigen", "slike_vedno": "Immer anzeigen von {od}", "prenesi": "Herunterladen", "odpri": "In App öffnen", "mapa": "Im Ordner zeigen", "zapri": "Schließen",
           "pripravljam": "Vorschau wird vorbereitet …", "nevarno_naslov": "Diese Datei kann gefährlich sein",
           "nevarno": "„{ime}“ ist ein Programm, ein Skript oder ein Dokument mit Makros. Solche Dateien können deinem Computer schaden, daher zeigt Safeer sie nicht an. Öffne sie nur, wenn du dem Absender vertraust und sie erwartest.",
           "brez_naslov": "Keine Vorschau verfügbar", "brez": "Safeer kann diese Dateiart ({vrsta}) nicht anzeigen. Lade sie herunter oder öffne sie in einer App.",
           "brez_lo": "Für die Vorschau von Office- und ODF-Dokumenten installiere LibreOffice (Anwendungsverwaltung). Bis dahin kannst du das Dokument in einer App öffnen.",
           "napaka": "Die Datei konnte nicht gelesen werden.", "ni_povezave": "Der Anhang konnte nicht heruntergeladen werden. Prüfe die Verbindung und versuche es erneut.", "brez_oblike": "Vorschau ohne Formatierung – installiere LibreOffice für die vollständige Vorschau.",
           "slike_skrite": "Bilder aus dem Web sind zum Schutz deiner Privatsphäre ausgeblendet (der Absender erfährt nicht, dass du die E-Mail geöffnet hast).",
           "od": "Von", "za": "An", "datum": "Datum", "zadeva": "Betreff", "priponke": "Anhänge",
           "skrajsano": "Nur der Anfang der Datei wird angezeigt.", "shranjeno": "In Downloads gespeichert: {ime}"},
    "es": {"slike_vrstica": "Las imágenes están ocultas por privacidad", "slike_prikazi": "Mostrar imágenes", "slike_vedno": "Mostrar siempre de {od}", "prenesi": "Descargar", "odpri": "Abrir en una app", "mapa": "Mostrar en carpeta", "zapri": "Cerrar",
           "pripravljam": "Preparando la vista previa …", "nevarno_naslov": "Este archivo puede ser peligroso",
           "nevarno": "«{ime}» es un programa, un script o un documento con macros. Estos archivos pueden dañar tu ordenador, por eso Safeer no los muestra. Ábrelo solo si confías en el remitente y lo esperabas.",
           "brez_naslov": "Vista previa no disponible", "brez": "Safeer no puede mostrar este tipo de archivo ({vrsta}). Descárgalo o ábrelo en una app.",
           "brez_lo": "Para ver documentos de Office y ODF, instala LibreOffice (Gestor de software). Mientras tanto puedes abrir el documento en una app.",
           "napaka": "No se pudo leer el archivo.", "ni_povezave": "No se pudo descargar el adjunto. Comprueba la conexión e inténtalo de nuevo.", "brez_oblike": "Vista previa sin formato: instala LibreOffice para una vista previa completa.",
           "slike_skrite": "Las imágenes de la web están ocultas por tu privacidad (el remitente no sabe que abriste el correo).",
           "od": "De", "za": "Para", "datum": "Fecha", "zadeva": "Asunto", "priponke": "Adjuntos",
           "skrajsano": "Solo se muestra el principio del archivo.", "shranjeno": "Guardado en Descargas: {ime}"},
    "fr": {"slike_vrstica": "Les images sont masquées pour votre confidentialité", "slike_prikazi": "Afficher les images", "slike_vedno": "Toujours afficher de {od}", "prenesi": "Télécharger", "odpri": "Ouvrir dans une app", "mapa": "Afficher dans le dossier", "zapri": "Fermer",
           "pripravljam": "Préparation de l’aperçu …", "nevarno_naslov": "Ce fichier peut être dangereux",
           "nevarno": "« {ime} » est un programme, un script ou un document avec des macros. Ces fichiers peuvent nuire à votre ordinateur, Safeer ne les affiche donc pas. Ouvrez-le seulement si vous faites confiance à l’expéditeur et l’attendiez.",
           "brez_naslov": "Aperçu indisponible", "brez": "Safeer ne peut pas afficher ce type de fichier ({vrsta}). Téléchargez-le ou ouvrez-le dans une app.",
           "brez_lo": "Pour prévisualiser les documents Office et ODF, installez LibreOffice (Gestionnaire de logiciels). En attendant, vous pouvez ouvrir le document dans une app.",
           "napaka": "Le fichier n’a pas pu être lu.", "ni_povezave": "La pièce jointe n’a pas pu être téléchargée. Vérifiez la connexion et réessayez.", "brez_oblike": "Aperçu sans mise en forme – installez LibreOffice pour un aperçu complet.",
           "slike_skrite": "Les images du web sont masquées pour votre confidentialité (l’expéditeur ne sait pas que vous avez ouvert le message).",
           "od": "De", "za": "À", "datum": "Date", "zadeva": "Objet", "priponke": "Pièces jointes",
           "skrajsano": "Seul le début du fichier est affiché.", "shranjeno": "Enregistré dans Téléchargements : {ime}"},
    "it": {"slike_vrstica": "Le immagini sono nascoste per la privacy", "slike_prikazi": "Mostra immagini", "slike_vedno": "Mostra sempre da {od}", "prenesi": "Scarica", "odpri": "Apri in un'app", "mapa": "Mostra nella cartella", "zapri": "Chiudi",
           "pripravljam": "Preparazione dell'anteprima …", "nevarno_naslov": "Questo file può essere pericoloso",
           "nevarno": "«{ime}» è un programma, uno script o un documento con macro. Questi file possono danneggiare il computer, perciò Safeer non li mostra. Aprilo solo se ti fidi del mittente e te lo aspettavi.",
           "brez_naslov": "Anteprima non disponibile", "brez": "Safeer non può mostrare questo tipo di file ({vrsta}). Scaricalo o aprilo in un'app.",
           "brez_lo": "Per l'anteprima dei documenti Office e ODF installa LibreOffice (Gestore applicazioni). Nel frattempo puoi aprire il documento in un'app.",
           "napaka": "Impossibile leggere il file.", "ni_povezave": "Impossibile scaricare l'allegato. Controlla la connessione e riprova.", "brez_oblike": "Anteprima senza formattazione: installa LibreOffice per un'anteprima completa.",
           "slike_skrite": "Le immagini dal web sono nascoste per la tua privacy (il mittente non sa che hai aperto il messaggio).",
           "od": "Da", "za": "A", "datum": "Data", "zadeva": "Oggetto", "priponke": "Allegati",
           "skrajsano": "Viene mostrato solo l'inizio del file.", "shranjeno": "Salvato in Download: {ime}"},
}


def besedilo(kljuc: str, jezik: str = "sl", **zamenjave) -> str:
    b = (BESEDILA_PREDOGLEDA.get(jezik) or BESEDILA_PREDOGLEDA["en"]).get(kljuc) or BESEDILA_PREDOGLEDA["en"].get(kljuc, kljuc)
    for k, v in zamenjave.items():
        b = b.replace("{" + k + "}", str(v))
    return b


# ---------------------------------------------------------------------------------------------- vrsta in varnost
def _koncnica(ime: str) -> str:
    return os.path.splitext(str(ime or "").strip().lower().rstrip(". "))[1]


def je_nevarna(ime: str, tip: str = "") -> bool:
    """Program, skripta, namestitveni paket ali dokument z makri (tudi »racun.pdf.exe«)."""
    ime = str(ime or "").strip().lower().rstrip(". ")
    return ime.endswith(NEVARNE_KONCNICE) or str(tip or "").split(";")[0].strip().lower() in NEVARNI_TIPI


def vrsta_predogleda(ime: str, tip: str = "") -> str:
    """»slika«, »pdf«, »dokument«, »besedilo«, »tabela«, »html«, »posta«, »nevarno« ali "" (ni predogleda)."""
    k = _koncnica(ime)
    tip = str(tip or "").split(";")[0].strip().lower()
    if je_nevarna(ime, tip) and k not in MAKRO_KONCNICE:
        return "nevarno"
    if k == ".pdf" or tip == "application/pdf":
        return "pdf"
    if k in SLIKE or (tip.startswith("image/") and tip not in ("image/tiff", "image/heic", "image/heif")):
        return "slika"
    if k in DOKUMENTI or tip in ("application/msword", "application/rtf", "text/rtf") or \
            tip.startswith(("application/vnd.openxmlformats-officedocument", "application/vnd.oasis.opendocument",
                            "application/vnd.ms-excel", "application/vnd.ms-powerpoint", "application/vnd.ms-word")):
        return "dokument"
    if k in TABELE or tip in ("text/csv", "text/tab-separated-values"):
        return "tabela"
    if k in HTML or tip in ("text/html", "application/xhtml+xml"):
        return "html"
    if k in POSTA or tip == "message/rfc822":
        return "posta"
    if k in BESEDILA or tip.startswith("text/") or tip in ("application/json", "application/xml"):
        return "besedilo"
    return ""


# ---------------------------------------------------------------------------------------------- predpomnilnik
def mapa_predpomnilnika() -> str:
    """Pretvorbe krajevnih datotek (Datoteke, namizje): $XDG_CACHE_HOME/safeer-os/predogled (zasebna, 0700).
    Priponke sporocil imajo svoj predpomnilnik s kljucem sporocila (core/sporocila/predpomnilnik.py)."""
    pot = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.join(os.path.expanduser("~"), ".cache"),
                       "safeer-os", "predogled")
    os.makedirs(pot, mode=0o700, exist_ok=True)
    try:
        os.chmod(pot, 0o700)
    except OSError:
        pass
    return pot


def pot_v_predpomnilniku(kljuc: str, ime: str) -> str:
    """Pot za datoteko s kljucem (kanal, sporocilo, del): <predpomnilnik>/<zgostitev>/<varno ime>. Ime ostane
    pravo (program, s katerim se odpre, ga pokaze), mapa pa ne more uiti iz predpomnilnika."""
    zgostitev = hashlib.sha256(str(kljuc).encode("utf-8")).hexdigest()[:24]
    mapa = os.path.join(mapa_predpomnilnika(), zgostitev)
    os.makedirs(mapa, mode=0o700, exist_ok=True)
    return os.path.join(mapa, varno_ime(ime))


def varno_ime(ime: str, privzeto: str = "priponka") -> str:
    """Ime brez poti, nadzornih znakov in imen, ki jih datotecni sistem ne mara (CON, NUL na FAT/NTFS kljucih)."""
    ime = splet_prenosi.varno_ime_datoteke(str(ime or ""), privzeto)
    ime = "".join(z for z in ime if z not in '<>:"|?*' and not (0x7F <= ord(z) <= 0x9F) and z not in "\u202e\u202d\u200e\u200f")
    ime = ime.strip().strip(".") or privzeto
    if os.path.splitext(ime)[0].upper() in {"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "LPT1", "LPT2"}:
        ime = "_" + ime
    return ime


def pocisti_predpomnilnik(najvec: int = NAJVEC_PREDPOMNILNIK, starost: float = STAROST_PREDPOMNILNIK_S,
                          zdaj: Optional[float] = None) -> int:
    """Izbrise datoteke, starejse od tedna, in najstarejse, dokler je vse skupaj vec kot `najvec`. Vrne izbrisanih."""
    zdaj = time.time() if zdaj is None else zdaj
    koren = mapa_predpomnilnika()
    datoteke = []
    for mapa, _, imena in os.walk(koren):
        for ime in imena:
            pot = os.path.join(mapa, ime)
            try:
                st = os.lstat(pot)
            except OSError:
                continue
            datoteke.append((st.st_mtime, st.st_size, pot))
    datoteke.sort()
    skupaj = sum(d[1] for d in datoteke)
    izbrisanih = 0
    for cas, velikost, pot in datoteke:
        if zdaj - cas <= starost and skupaj <= najvec:
            continue
        try:
            os.remove(pot)
            izbrisanih += 1
            skupaj -= velikost
        except OSError:
            pass
    for mapa, podmape, imena in os.walk(koren, topdown=False):
        if mapa != koren and not podmape and not imena:
            try:
                os.rmdir(mapa)
            except OSError:
                pass
    return izbrisanih


# ---------------------------------------------------------------------------------------------- varen HTML
_PREPOVEDANO_Z_VSEBINO = {"script", "iframe", "frame", "frameset", "object", "embed", "applet", "template", "noembed",
                          "title", "portal", "xml", "noframes"}
_PREPOVEDANO = {"base", "meta", "link", "param", "source", "track", "audio", "video", "form", "input", "button",
                "select", "option", "textarea", "html", "head", "body", "!doctype"}
_URL_ATRIBUTI = {"href", "src", "background", "poster", "action", "formaction", "xlink:href", "lowsrc", "dynsrc",
                 "longdesc", "cite", "data", "codebase", "usemap", "manifest", "srcset", "ping", "srcdoc"}
_PRAZNI = {"area", "br", "col", "hr", "img", "wbr"}
_CSS_URL = re.compile(r"url\s*\(\s*(['\"]?)(.*?)\1\s*\)", re.I | re.S)


class _Cistilnik(HTMLParser):
    def __init__(self, cid: Dict[str, str], oddaljene: Optional[Dict[str, str]] = None):
        super().__init__(convert_charrefs=True)
        self.cid = {k.strip("<>").lower(): v for k, v in (cid or {}).items()}
        self.oddaljene = oddaljene                  # {url: file://} slike, ki jih je prenesla zascita Safeer
        self.oddaljeni: list = []                   # vsi oddaljeni naslovi slik (za prenos)
        self.izhod: list = []
        self.preskoci = 0
        self.skrite_slike = 0

    def _url_slike(self, v: str) -> str:
        v = v.strip()
        nizko = v.lower()
        if nizko.startswith("cid:"):
            return self.cid.get(v[4:].strip("<>").lower(), "")
        if nizko.startswith("data:image/") and not nizko.startswith("data:image/svg"):
            return v
        if nizko.startswith(("http:", "https:", "//")):
            url = ("https:" + v) if v.startswith("//") else v
            if url not in self.oddaljeni:
                self.oddaljeni.append(url)
            if self.oddaljene is not None:
                return self.oddaljene.get(url, "")    # blokirano (sledilec, 1x1, domace omrezje): ni slike
            self.skrite_slike += 1
        return ""

    @staticmethod
    def _piksel(atributi) -> bool:
        """Sledilni piksel po atributih: sirina ali visina 0-2 tocke ali skrita slika."""
        a = {str(k or "").lower(): str(v or "") for k, v in atributi}
        for kljuc in ("width", "height"):
            m = re.match(r"\s*(\d+)(px)?\s*$", a.get(kljuc, ""))
            if m and int(m.group(1)) <= 2:
                return True
        slog = a.get("style", "").replace(" ", "").lower()
        return bool(re.search(r"(^|;)(width|height):[0-2](px)?(;|$)|display:none|visibility:hidden", slog))

    def _css(self, css: str) -> str:
        css = re.sub(r"(?i)@import[^;]*;?", "", css)
        css = re.sub(r"(?i)expression\s*\(|behavior\s*:|-moz-binding", "x-", css)

        def url(m) -> str:
            novo = self._url_slike(m.group(2))
            return "url(%s)" % ('"' + novo.replace('"', "%22") + '"' if novo else "about:blank")
        return _CSS_URL.sub(url, css)

    def handle_starttag(self, oznaka, atributi, prazna=False):
        oznaka = oznaka.lower()
        if oznaka == "img" and not self.preskoci and self._piksel(atributi):
            return                                      # sledilni piksel se ne steje med skrite slike
        if self.preskoci:
            if oznaka in _PREPOVEDANO_Z_VSEBINO:
                self.preskoci += 1
            return
        if oznaka in _PREPOVEDANO_Z_VSEBINO:
            if not prazna:
                self.preskoci = 1
            return
        if oznaka in _PREPOVEDANO or not re.fullmatch(r"[a-z][a-z0-9:-]{0,30}", oznaka):
            return
        deli = ["<" + oznaka]
        for ime, vrednost in atributi:
            ime = str(ime or "").lower()
            vrednost = "" if vrednost is None else str(vrednost)
            if not re.fullmatch(r"[a-z_:][a-z0-9_:.-]{0,40}", ime) or ime.startswith("on") or ime == "http-equiv":
                continue
            if ime in _URL_ATRIBUTI:
                if ime == "href" and oznaka in ("a", "area"):
                    if not re.match(r"(?i)^\s*(https?:|mailto:|#)", vrednost):
                        continue
                elif ime in ("src", "background") and oznaka in ("img", "td", "table", "body", "image"):
                    vrednost = self._url_slike(vrednost)
                    if not vrednost:
                        continue
                else:
                    continue
            if ime == "style":
                vrednost = self._css(vrednost)
            deli.append(' %s="%s"' % (ime, _html.escape(vrednost, quote=True)))
        if oznaka == "a":
            deli.append(' rel="noreferrer noopener"')
        self.izhod.append("".join(deli) + (" />" if prazna and oznaka in _PRAZNI else ">"))

    def handle_startendtag(self, oznaka, atributi):
        self.handle_starttag(oznaka, atributi, prazna=True)

    def handle_endtag(self, oznaka):
        oznaka = oznaka.lower()
        if self.preskoci:
            if oznaka in _PREPOVEDANO_Z_VSEBINO:
                self.preskoci -= 1
            return
        if oznaka in _PREPOVEDANO or oznaka in _PRAZNI or oznaka in _PREPOVEDANO_Z_VSEBINO:
            return
        if re.fullmatch(r"[a-z][a-z0-9:-]{0,30}", oznaka):
            self.izhod.append("</%s>" % oznaka)

    def handle_data(self, podatki):
        if self.preskoci:
            return
        if self.lasttag == "style":
            self.izhod.append(self._css(podatki).replace("</", "<\\/"))
        else:
            self.izhod.append(_html.escape(podatki, quote=False))

    def handle_comment(self, _):
        pass

    def handle_decl(self, _):
        pass

    def handle_pi(self, _):
        pass


def _cisti(vsebina: str, cid, oddaljene):
    c = _Cistilnik(cid or {}, oddaljene)
    try:
        c.feed(str(vsebina or ""))
        c.close()
    except Exception:  # noqa: BLE001 - pokvarjen HTML: kar je preciscenega do tu
        pass
    return c


def varen_html(vsebina: str, cid: Optional[Dict[str, str]] = None, oddaljene: Optional[Dict[str, str]] = None) -> tuple:
    """Preciscen HTML (brez skript, okvirjev, obrazcev, dogodkov, oddaljenih virov). cid: {Content-ID: naslov slike}
    za slike v vrstici; oddaljene: {url: file://} slike, ki jih je prenesla zascita Safeer (None = oddaljene skrite).
    Vrne (html, stevilo skritih oddaljenih slik)."""
    c = _cisti(vsebina, cid, oddaljene)
    return "".join(c.izhod), c.skrite_slike


def oddaljene_slike(vsebina: str) -> list:
    """Naslovi oddaljenih slik v HTML (brez sledilnih pikslov po atributih), v vrstnem redu."""
    return list(_cisti(vsebina, {}, None).oddaljeni)


#: Brez skript, okvirjev, obrazcev in omrezja; slike samo iz datotek predpomnilnika in data:. Velja tudi brez JS.
CSP = ("default-src 'none'; img-src file: data:; style-src 'unsafe-inline'; font-src data:; "
       "form-action 'none'; frame-src 'none'; base-uri 'none'")


def _zetoni() -> str:
    try:
        with open(os.path.join(KOREN, "assets", "os", "tokens.css"), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def stran(telo: str, jezik: str = "sl", svetla: bool = False) -> str:
    """Cela stran predogleda. svetla: HTML pisma in dokumenti so pisani za belo podlago (kot v Gmailu)."""
    slog = _zetoni() + """
body { margin:0; font: 15px/1.5 system-ui, sans-serif; background: var(--kartica-polna); color: var(--besedilo); }
.okvir { max-width: 1100px; margin: 0 auto; padding: 24px; overflow-wrap: anywhere; }
/* Pismo »Prikazi izvirnik«: slike in tabele posiljatelja ne smejo biti sirse od okna (testni PC 15. 10. 2026: slika v
   vrstici v polni locljivosti je segala daleč cez okno). Kot v Gmailu: pomanjsaj na sirino, razmerje ostane. */
.okvir img, .okvir video { max-width: 100% !important; height: auto !important; }
.okvir table { max-width: 100% !important; }
.sporocilo { display:flex; flex-direction:column; align-items:center; justify-content:center; min-height:80vh;
  text-align:center; gap:10px; padding:24px; }
.sporocilo h1 { font-size: 20px; margin: 0; } .sporocilo p { color: var(--medlo); max-width: 560px; margin: 0; }
.nevarno h1 { color: var(--opozorilo); }
.opomba { color: var(--medlo); font-size: 13px; border-bottom: 1px solid var(--tanka); padding: 8px 24px; margin: 0; }
pre { white-space: pre-wrap; overflow-wrap: anywhere; font: 13px/1.5 ui-monospace, monospace; margin: 0; }
.slika { display:flex; align-items:center; justify-content:center; min-height:100vh; }
.slika img { max-width: 100%; max-height: 100vh; object-fit: contain; }
table.tabela { border-collapse: collapse; font-size: 13px; }
table.tabela td { border: 1px solid var(--tanka); padding: 4px 8px; vertical-align: top; }
table.tabela tr:first-child td { font-weight: 600; background: var(--kartica-poudarek); }
dl.glava { display:grid; grid-template-columns: max-content 1fr; gap: 4px 14px; margin: 0 0 16px; }
dl.glava dt { color: var(--medlo); } dl.glava dd { margin: 0; }
.vrtavka { width: 28px; height: 28px; border-radius: 50%; border: 3px solid var(--tanka); border-top-color: var(--zelena);
  animation: vrti 1s linear infinite; }
@keyframes vrti { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .vrtavka { animation: none; } }
"""
    if svetla:
        slog += "body.svetla { background: var(--media-logotip-podlaga); color: var(--zelena-temna); }\n" \
                "body.svetla .opomba { background: var(--kartica-polna); color: var(--medlo); }\n"
    return ('<!DOCTYPE html><html lang="%s"><head><meta charset="utf-8">'
            '<meta http-equiv="Content-Security-Policy" content="%s">'
            '<meta name="color-scheme" content="%s"><style>%s</style></head><body%s>%s</body></html>'
            % (_html.escape(jezik), CSP, "light" if svetla else "dark", slog, ' class="svetla"' if svetla else "", telo))


def stran_sporocila(naslov: str, opis: str, jezik: str = "sl", nevarno: bool = False, nalaganje: bool = False) -> str:
    vrtavka = '<div class="vrtavka" role="progressbar" aria-busy="true"></div>' if nalaganje else ""
    return stran('<div class="sporocilo%s">%s<h1>%s</h1><p>%s</p></div>' % (
        " nevarno" if nevarno else "", vrtavka, _html.escape(naslov), _html.escape(opis)), jezik)


# ---------------------------------------------------------------------------------------------- besedilo iz dokumentov
def _beri_zip(z: zipfile.ZipFile, ime: str, najvec: int = 50 * 1024 * 1024) -> bytes:
    info = z.getinfo(ime)
    if info.file_size > najvec:
        raise ValueError("prevelik del")
    with z.open(info) as f:
        return f.read(najvec + 1)[:najvec]


def _lokalno(oznaka: str) -> str:
    return oznaka.rsplit("}", 1)[-1]


def _besedilo_el(el) -> str:
    """Besedilo odstavka v vrstnem redu: DOCX (w:t, w:tab, w:br), PPTX (a:t, a:br), ODF (besedilo, text:s/tab/line-break)."""
    deli: list = []

    def obisci(e) -> None:
        ime = _lokalno(e.tag)
        if ime == "tab":
            deli.append("\t")
        elif ime in ("br", "cr", "line-break"):
            deli.append("\n")
        elif ime == "s":
            try:
                deli.append(" " * max(1, min(200, int(e.get("{urn:oasis:names:tc:opendocument:xmlns:text:1.0}c", "1")))))
            except ValueError:
                deli.append(" ")
        elif ime not in ("instrText", "delText", "annotation", "pPr", "rPr"):
            if e.text:
                deli.append(e.text)
            for otrok in e:
                obisci(otrok)
                if otrok.tail:
                    deli.append(otrok.tail)
    obisci(el)
    return "".join(deli)


def _odstavki_xml(xml: bytes, odstavki=("p", "h")) -> list:
    try:
        koren = ElementTree.fromstring(xml)
    except ElementTree.ParseError:
        return []
    return [_besedilo_el(el) for el in koren.iter() if _lokalno(el.tag) in odstavki]


def besedilo_dokumenta(pot: str) -> str:
    """Golo besedilo iz DOCX, PPTX, XLSX in ODF (zip + XML), brez dodatnih knjiznic. "" ce ne gre."""
    k = _koncnica(pot)
    try:
        with zipfile.ZipFile(pot) as z:
            imena = z.namelist()
            if k in (".docx", ".docm", ".dotx"):
                deli = [n for n in ("word/document.xml",) if n in imena]
                return "\n".join(o for d in deli for o in _odstavki_xml(_beri_zip(z, d)))
            if k in (".pptx", ".pptm", ".ppsx"):
                prosojnice = sorted((n for n in imena if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                                    key=lambda n: int(re.search(r"(\d+)", n.rsplit("/", 1)[1]).group(1)))
                bloki = []
                for i, n in enumerate(prosojnice, 1):
                    vrstice = [o for o in _odstavki_xml(_beri_zip(z, n)) if o.strip()]
                    bloki.append("— %d —\n%s" % (i, "\n".join(vrstice)))
                return "\n\n".join(bloki)
            if k in (".xlsx", ".xlsm"):
                skupni = []
                if "xl/sharedStrings.xml" in imena:
                    koren = ElementTree.fromstring(_beri_zip(z, "xl/sharedStrings.xml"))
                    skupni = ["".join(si.itertext()) for si in koren if _lokalno(si.tag) == "si"]
                bloki = []
                for n in sorted(x for x in imena if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", x)):
                    koren = ElementTree.fromstring(_beri_zip(z, n))
                    vrstice = []
                    for vrsta in koren.iter():
                        if _lokalno(vrsta.tag) != "row":
                            continue
                        celice = []
                        for c in vrsta:
                            if _lokalno(c.tag) != "c":
                                continue
                            v = next((x.text or "" for x in c.iter() if _lokalno(x.tag) in ("v", "t")), "")
                            if c.get("t") == "s" and v.isdigit() and int(v) < len(skupni):
                                v = skupni[int(v)]
                            celice.append(v)
                        vrstice.append("\t".join(celice))
                        if len(vrstice) >= NAJVEC_VRSTIC_TABELE:
                            break
                    bloki.append("\n".join(vrstice))
                return "\n\n".join(bloki)
            if "content.xml" in imena:                 # ODT, ODS, ODP
                return "\n".join(_odstavki_xml(_beri_zip(z, "content.xml")))
    except (zipfile.BadZipFile, KeyError, ValueError, OSError, ElementTree.ParseError, RuntimeError):
        return ""
    if k == ".rtf":
        try:
            with open(pot, "rb") as f:
                rtf = f.read(NAJVEC_BESEDILO).decode("latin-1")
        except OSError:
            return ""
        rtf = re.sub(r"\\'([0-9a-fA-F]{2})", lambda m: bytes([int(m.group(1), 16)]).decode("cp1250", "replace"), rtf)
        rtf = re.sub(r"\\par[d]?\b ?", "\n", rtf)
        rtf = re.sub(r"\{\\\*[^{}]*\}|\\[a-zA-Z]+-?\d* ?|[{}]", "", rtf)
        return rtf.strip()
    return ""


# ---------------------------------------------------------------------------------------------- pretvorba v PDF
_zaklep_lo = threading.Lock()


def v_pdf(pot: str, najdi: Callable[[str], Optional[str]] = shutil.which, cas: float = CAS_PRETVORBE_S,
          cilj_mapa: str = "") -> tuple:
    """Dokument -> PDF z LibreOffice brez okna (v Flatpaku na racunalniku). Vrne (pot_pdf, "") ali ("", koda):
    »ni_orodja«, »prepocasi«, »ni_uspelo«. Rezultat ostane v predpomnilniku (isti dokument se ne pretvarja znova):
    v `cilj_mapa` (vnos priponke), sicer v mapi pretvorb, oboje s kljucem velikosti in casa spremembe."""
    from core import os_pretvorba_datotek as pretvorba
    try:
        st = os.stat(pot)
    except OSError:
        return "", "ni_uspelo"
    kljuc = hashlib.sha256(("%s\0%d\0%d" % (os.path.realpath(pot), st.st_size, int(st.st_mtime))).encode()).hexdigest()[:24]
    if cilj_mapa:
        # Vnos priponke: kljuc po vsebini (cas spremembe se ob vsaki uporabi osvezi za LRU in ne sme sprozit pretvorbe).
        zg = hashlib.sha256()
        with open(pot, "rb") as f:
            for kos in iter(lambda: f.read(1024 * 1024), b""):
                zg.update(kos)
        cilj = os.path.join(cilj_mapa, "predogled-%s.pdf" % zg.hexdigest()[:16])
    else:
        cilj = os.path.join(mapa_predpomnilnika(), "pdf-" + kljuc, os.path.splitext(varno_ime(os.path.basename(pot)))[0] + ".pdf")
    if os.path.isfile(cilj) and os.path.getsize(cilj) > 0:
        return cilj, ""
    soffice = pretvorba.orodje("besedilo", najdi)
    if not soffice:
        return "", "ni_orodja"
    import subprocess
    with _zaklep_lo:                                    # en profil LibreOffice: ena pretvorba naenkrat
        try:
            zacasna = pretvorba._zacasna_mapa()
        except OSError:
            return "", "ni_uspelo"
        try:
            profil = os.path.join(os.path.dirname(mapa_predpomnilnika()), "lo-profil")
            ukaz = [soffice, "--headless", "--norestore", "--nolockcheck", "--nodefault", "--nofirststartwizard",
                    "-env:UserInstallation=file://" + profil, "--convert-to", "pdf", "--outdir", zacasna, pot]
            try:
                koda = pretvorba._zazeni_s_koncem(ukaz, cas)
            except subprocess.TimeoutExpired:
                return "", "prepocasi"
            except OSError:
                return "", "ni_orodja"
            narejeno = next((os.path.join(zacasna, f) for f in os.listdir(zacasna) if f.lower().endswith(".pdf")), "")
            if koda != 0 or not narejeno or os.path.getsize(narejeno) == 0:
                return "", "ni_uspelo"
            os.makedirs(os.path.dirname(cilj), mode=0o700, exist_ok=True)
            shutil.move(narejeno, cilj)
            os.chmod(cilj, 0o600)
            return cilj, ""
        finally:
            shutil.rmtree(zacasna, ignore_errors=True)


# ---------------------------------------------------------------------------------------------- priprava predogleda
def _uri(pot: str) -> str:
    from urllib.parse import quote
    return "file://" + quote(os.path.abspath(pot))


def _beri_besedilo(pot: str) -> tuple:
    with open(pot, "rb") as f:
        surovo = f.read(NAJVEC_BESEDILO + 1)
    skrajsano = len(surovo) > NAJVEC_BESEDILO
    surovo = surovo[:NAJVEC_BESEDILO]
    for nabor in ("utf-8-sig", "cp1250", "latin-1"):
        try:
            return surovo.decode(nabor), skrajsano
        except UnicodeDecodeError:
            continue
    return surovo.decode("utf-8", "replace"), skrajsano


def _tabela(besedilo_: str, locilo: str) -> str:
    vrstice = []
    try:
        bralnik = csv.reader(io.StringIO(besedilo_), delimiter=locilo)
        for i, vrsta in enumerate(bralnik):
            if i >= NAJVEC_VRSTIC_TABELE:
                break
            vrstice.append("<tr>%s</tr>" % "".join("<td>%s</td>" % _html.escape(c) for c in vrsta[:60]))
    except csv.Error:
        return "<pre>%s</pre>" % _html.escape(besedilo_)
    return '<table class="tabela">%s</table>' % "".join(vrstice)


def _posta(pot: str, jezik: str) -> str:
    """Posredovano pismo (.eml): glava, HTML (slike v vrstici iz pisma samega) ali besedilo in seznam priponk."""
    from email import message_from_binary_file, policy
    from core.sporocila.email import _glava, telo_pisma
    import base64
    with open(pot, "rb") as f:
        msg = message_from_binary_file(f, policy=policy.default)
    glava = "".join("<dt>%s</dt><dd>%s</dd>" % (_html.escape(besedilo(k, jezik)), _html.escape(_glava(msg.get(h, ""))))
                    for k, h in (("od", "From"), ("za", "To"), ("datum", "Date"), ("zadeva", "Subject")) if msg.get(h))
    cid, html_del, priponke = {}, None, []
    for d in msg.walk():
        if d.is_multipart():
            continue
        tip = d.get_content_type()
        ime = d.get_filename()
        if d.get("Content-ID") and tip.startswith("image/") and tip != "image/svg+xml":
            vsebina = d.get_payload(decode=True) or b""
            if len(vsebina) <= 5 * 1024 * 1024:
                cid[str(d["Content-ID"]).strip("<> ")] = "data:%s;base64,%s" % (tip, base64.b64encode(vsebina).decode())
            continue
        if ime or d.get_content_disposition() == "attachment":
            priponke.append(_glava(ime or "priponka"))
        elif tip == "text/html" and html_del is None:
            html_del = d
    opomba = ""
    if html_del is not None:
        try:
            surovo = str(html_del.get_content())
        except Exception:  # noqa: BLE001
            surovo = (html_del.get_payload(decode=True) or b"").decode("utf-8", "replace")
        telo, skrite = varen_html(surovo, cid)
        if skrite:
            opomba = '<p class="opomba">%s</p>' % _html.escape(besedilo("slike_skrite", jezik))
    else:
        telo = "<pre>%s</pre>" % _html.escape(telo_pisma(msg))
    seznam = ""
    if priponke:
        seznam = "<dt>%s</dt><dd>%s</dd>" % (_html.escape(besedilo("priponke", jezik)),
                                            ", ".join(_html.escape(p) for p in priponke))
    return '%s<div class="okvir"><dl class="glava">%s%s</dl>%s</div>' % (opomba, glava, seznam, telo)


def pripravi(pot: str, ime: str = "", tip: str = "", jezik: str = "sl",
             najdi: Callable[[str], Optional[str]] = shutil.which, mapa_pretvorbe: str = "") -> dict:
    """Kaj pokazati za datoteko. Vrne {"nacin": "pdf", "pot"} (PDF.js) ali {"nacin": "html", "html", "osnova"}
    (stran brez JavaScripta) in vedno »vrsta«; nikoli prazne strani. mapa_pretvorbe: kam shraniti PDF pretvorbe
    (vnos priponke v predpomnilniku Sporocil)."""
    ime = ime or os.path.basename(pot)
    vrsta = vrsta_predogleda(ime, tip)
    osnova = _uri(os.path.dirname(os.path.abspath(pot))) + "/"

    def html(telo: str, svetla: bool = False) -> dict:
        return {"nacin": "html", "vrsta": vrsta, "html": stran(telo, jezik, svetla), "osnova": osnova}

    def sporocilo(naslov_k: str, opis: str, nevarno: bool = False) -> dict:
        return {"nacin": "html", "vrsta": vrsta, "osnova": osnova,
                "html": stran_sporocila(besedilo(naslov_k, jezik), opis, jezik, nevarno=nevarno)}

    if vrsta == "nevarno":
        return sporocilo("nevarno_naslov", besedilo("nevarno", jezik, ime=ime), nevarno=True)
    if not os.path.isfile(pot):
        return sporocilo("brez_naslov", besedilo("napaka", jezik))
    try:
        if vrsta == "pdf":
            return {"nacin": "pdf", "vrsta": vrsta, "pot": pot}
        if vrsta == "slika":
            return html('<div class="slika"><img src="%s" alt="%s"></div>' % (_html.escape(_uri(pot)), _html.escape(ime)))
        if vrsta == "dokument":
            pdf, koda = v_pdf(pot, najdi, cilj_mapa=mapa_pretvorbe)
            if pdf:
                return {"nacin": "pdf", "vrsta": vrsta, "pot": pdf, "pretvorjeno": True}
            golo = besedilo_dokumenta(pot)
            if golo.strip():
                return html('<p class="opomba">%s</p><div class="okvir"><pre>%s</pre></div>' % (
                    _html.escape(besedilo("brez_oblike", jezik)), _html.escape(golo)))
            return sporocilo("brez_naslov", besedilo("brez_lo" if koda == "ni_orodja" else "napaka", jezik))
        if vrsta in ("besedilo", "tabela", "html"):
            vsebina, skrajsano = _beri_besedilo(pot)
            opomba = '<p class="opomba">%s</p>' % _html.escape(besedilo("skrajsano", jezik)) if skrajsano else ""
            if vrsta == "html":
                telo, skrite = varen_html(vsebina)
                if skrite:
                    opomba += '<p class="opomba">%s</p>' % _html.escape(besedilo("slike_skrite", jezik))
                return html(opomba + '<div class="okvir">%s</div>' % telo, svetla=True)
            if vrsta == "tabela":
                locilo = "\t" if _koncnica(ime) == ".tsv" or "\t" in vsebina[:2000] and "," not in vsebina[:2000] else (
                    ";" if vsebina[:2000].count(";") > vsebina[:2000].count(",") else ",")
                return html(opomba + '<div class="okvir">%s</div>' % _tabela(vsebina, locilo))
            return html(opomba + '<div class="okvir"><pre>%s</pre></div>' % _html.escape(vsebina))
        if vrsta == "posta":
            return html(_posta(pot, jezik), svetla=True)
    except Exception:  # noqa: BLE001 - pokvarjena datoteka: jasno sporocilo, ne prazno okno
        return sporocilo("brez_naslov", besedilo("napaka", jezik))
    return sporocilo("brez_naslov", besedilo("brez", jezik, vrsta=(_koncnica(ime).lstrip(".").upper() or tip or "?")))


def html_pisma(vsebina: str, cid: Dict[str, str], jezik: str = "sl", oddaljene: Optional[Dict[str, str]] = None) -> tuple:
    """HTML telo e-pisma kot v Gmailu: preciscen, slike v vrstici (cid:) iz predpomnilnika; oddaljene skrite ali iz
    zascite Safeer (oddaljene). Vrne (stran, skritih) - vrstico »Prikazi slike« pokaze okno predogleda (GTK, ne
    stran: besedilo pisma je ne more ponarediti)."""
    telo, skrite = varen_html(vsebina, cid, oddaljene)
    return stran('<div class="okvir">%s</div>' % telo, jezik, svetla=True), skrite
