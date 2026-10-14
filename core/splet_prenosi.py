"""Prenosi v Spletu in Safeer Browserju: ena koda za GTK3 (safeer_mint.py) in GTK4 (core/os_splet.py).

14. 10. 2026: Splet je prenose shranjeval v ~/Downloads (na slovenskem namizju je mapa »Prejemi«), z imenom iz naslova
(ne iz glave strezika), brez potrditve za programe in brez napredka. Pravila prenosov iz safeer_mint.py so zdaj tu.
"""
from __future__ import annotations

import os
import time
import urllib.parse

#: Programi in namestitveni paketi: teh brskalnik nikoli ne prenese brez uporabnikove potrditve.
IZVRSLJIVE_KONCNICE = (".deb", ".rpm", ".apk", ".appimage", ".flatpak", ".flatpakref", ".snap", ".exe",
                       ".msi", ".msix", ".bat", ".cmd", ".ps1", ".dmg", ".pkg", ".jar", ".run", ".sh",
                       ".desktop", ".bin")

BESEDILA = {
    "sl": {"prenosi": "Prenosi", "pr_ni": "Ni prenosov.", "pr_tece": "Prenašam … {pct} %", "pr_koncan": "Končano",
           "pr_napaka": "Prenos ni uspel", "pr_preklican": "Preklicano", "pr_odpri": "Odpri", "pr_mapa": "Odpri mapo",
           "pr_preklici": "Prekliči", "pr_program": "Prenesem program?",
           "pr_program_opis": "»{ime}« je program ali namestitveni paket. Prenesi ga le, če mu zaupaš.\nMapa: {mapa}",
           "pr_prenesi": "Prenesi", "pr_zapri": "Zapri"},
    "en": {"prenosi": "Downloads", "pr_ni": "No downloads.", "pr_tece": "Downloading … {pct} %", "pr_koncan": "Done",
           "pr_napaka": "Download failed", "pr_preklican": "Cancelled", "pr_odpri": "Open", "pr_mapa": "Open folder",
           "pr_preklici": "Cancel", "pr_program": "Download a program?",
           "pr_program_opis": "“{ime}” is a program or an installer. Download it only if you trust it.\nFolder: {mapa}",
           "pr_prenesi": "Download", "pr_zapri": "Close"},
    "de": {"prenosi": "Downloads", "pr_ni": "Keine Downloads.", "pr_tece": "Wird heruntergeladen … {pct} %",
           "pr_koncan": "Fertig", "pr_napaka": "Download fehlgeschlagen", "pr_preklican": "Abgebrochen",
           "pr_odpri": "Öffnen", "pr_mapa": "Ordner öffnen", "pr_preklici": "Abbrechen",
           "pr_program": "Programm herunterladen?",
           "pr_program_opis": "„{ime}“ ist ein Programm oder Installationspaket. Lade es nur herunter, wenn du ihm vertraust.\nOrdner: {mapa}",
           "pr_prenesi": "Herunterladen", "pr_zapri": "Schließen"},
    "es": {"prenosi": "Descargas", "pr_ni": "No hay descargas.", "pr_tece": "Descargando … {pct} %",
           "pr_koncan": "Completado", "pr_napaka": "La descarga falló", "pr_preklican": "Cancelado",
           "pr_odpri": "Abrir", "pr_mapa": "Abrir carpeta", "pr_preklici": "Cancelar",
           "pr_program": "¿Descargar un programa?",
           "pr_program_opis": "«{ime}» es un programa o instalador. Descárgalo solo si confías en él.\nCarpeta: {mapa}",
           "pr_prenesi": "Descargar", "pr_zapri": "Cerrar"},
    "fr": {"prenosi": "Téléchargements", "pr_ni": "Aucun téléchargement.", "pr_tece": "Téléchargement … {pct} %",
           "pr_koncan": "Terminé", "pr_napaka": "Échec du téléchargement", "pr_preklican": "Annulé",
           "pr_odpri": "Ouvrir", "pr_mapa": "Ouvrir le dossier", "pr_preklici": "Annuler",
           "pr_program": "Télécharger un programme ?",
           "pr_program_opis": "« {ime} » est un programme ou un installateur. Ne le téléchargez que si vous lui faites confiance.\nDossier : {mapa}",
           "pr_prenesi": "Télécharger", "pr_zapri": "Fermer"},
    "it": {"prenosi": "Download", "pr_ni": "Nessun download.", "pr_tece": "Download in corso … {pct} %",
           "pr_koncan": "Completato", "pr_napaka": "Download non riuscito", "pr_preklican": "Annullato",
           "pr_odpri": "Apri", "pr_mapa": "Apri cartella", "pr_preklici": "Annulla",
           "pr_program": "Scaricare un programma?",
           "pr_program_opis": "«{ime}» è un programma o un pacchetto di installazione. Scaricalo solo se ti fidi.\nCartella: {mapa}",
           "pr_prenesi": "Scarica", "pr_zapri": "Chiudi"},
}


def je_izvrsljiv_prenos(ime: str) -> bool:
    """Ali je prenesena datoteka program ali namestitveni paket (po koncnici imena)."""
    return str(ime or "").strip().lower().rstrip(". ").endswith(IZVRSLJIVE_KONCNICE)


def varno_ime_datoteke(ime: str, privzeto: str = "prenos_datoteke") -> str:
    """Iz imena, ki ga predlaga streznik, naredi ime, ki ne more zapustiti mape.

    Streznik predlaga ime v glavi Content-Disposition in mu ne gre zaupati: lahko
    vsebuje poti (`../../.bashrc`), absolutno pot (`/etc/cron.d/x`) ali obrnjene
    posevnice. Vzamemo samo zadnji del poti in zavrzemo vse, kar ni ime datoteke.
    """
    if not ime:
        return privzeto
    ocisceno = ime.replace("\\", "/").replace("\x00", "")
    ocisceno = ocisceno.split("/")[-1].strip()
    # Nadzorni znaki v imenu datoteke nimajo kaj poceti.
    ocisceno = "".join(z for z in ocisceno if ord(z) >= 32)
    if ocisceno in ("", ".", ".."):
        return privzeto
    # Dolga imena nekatere datotecne sisteme zlomijo (meja je 255 bajtov).
    if len(ocisceno.encode("utf-8")) > 200:
        koren, konec = os.path.splitext(ocisceno)
        konec = konec[:20]
        while len((koren + konec).encode("utf-8")) > 200 and koren:
            koren = koren[:-1]
        ocisceno = (koren + konec) or privzeto
    return ocisceno


def ime_prenosa(predlagano: str, uri: str) -> str:
    """Ime iz predloga WebKita (glava Content-Disposition), sicer iz naslova; vedno razvozlano in varno."""
    ime = predlagano or os.path.basename(urllib.parse.urlparse(uri or "").path)
    return varno_ime_datoteke(urllib.parse.unquote(ime or ""))


def mapa_prenosov(GLib=None) -> str:
    """Sistemska mapa za prenose (XDG: na slovenskem namizju »Prejemi«), sicer Prenosi/Downloads v domu."""
    d = None
    if GLib is not None:
        try:
            d = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_DOWNLOAD)
        except Exception:  # noqa: BLE001
            d = None
    if d and os.path.isdir(d):
        return d
    for ime in ("Prenosi", "Downloads"):
        p = os.path.expanduser("~/" + ime)
        if os.path.isdir(p):
            return p
    p = os.path.expanduser("~/Prenosi")
    os.makedirs(p, exist_ok=True)
    return p


def edinstvena_pot(mapa: str, ime: str) -> str:
    """Pot v mapi, ki se ne obstaja (Datoteka (1).tar.gz); ime nikoli ne nese poti."""
    ime = varno_ime_datoteke(ime)
    osnova, konec = os.path.splitext(ime)
    if osnova.lower().endswith(".tar"):
        osnova, konec2 = os.path.splitext(osnova)
        konec = konec2 + konec
    cilj = os.path.join(mapa, ime)
    n = 1
    while os.path.lexists(cilj):
        cilj = os.path.join(mapa, f"{osnova} ({n}){konec}")
        n += 1
    return cilj


def nov_zapis(pot: str) -> dict:
    return {"ime": os.path.basename(pot), "pot": pot, "napredek": 0.0, "stanje": "tece",
            "cas": time.strftime("%H:%M")}


def opis_stanja(zapis: dict, t) -> str:
    """Besedilo stanja za vrstico v seznamu prenosov (t: kljuc -> prevod)."""
    s = zapis.get("stanje")
    if s == "tece":
        return t("pr_tece").format(pct=int(float(zapis.get("napredek") or 0) * 100))
    return t({"koncan": "pr_koncan", "preklican": "pr_preklican"}.get(s, "pr_napaka"))
