"""Besedila domačega GTK predvajalnika in dialogov Safeer Media v jezikih vmesnika Safeer OS.

Stran (assets/os/besedila.js) ima svoje prevode; tu so samo napisi, ki jih riše GTK (okno
predvajalnika, izbirniki map in datotek), da okno ne ostane slovensko v angleškem vmesniku.
"""

from __future__ import annotations

JEZIKI = ("sl", "en", "de", "es", "fr", "it")

BESEDILA: dict[str, dict[str, str]] = {
    "sl": {
        "dvd": "Diska ni mogoče prebrati. Zaščitenih diskov (CSS) Safeer ne odklepa.",
        "podnapisi": "Podnapisi", "podnapisi_izklop": "Izklopljeno", "podnapisi_vgrajeni": "Vgrajeni", "podnapisi_v_videu": "Podnapisi v videu",
        "deli_datoteko": "Izberi datoteko za deljenje", "izberi_mapo": "Izberi mapo za deljenje",
        "premik": "Premik po posnetku", "dodaj_datoteke": "Dodaj datoteke", "prejsnja": "Prejšnja",
        "naslednja": "Naslednja", "premor": "Premor", "nadaljuj": "Nadaljuj", "cel_zaslon": "Cel zaslon",
        "cakalna_vrsta": "Naslednje", "nic": "Nič se ne predvaja", "v_zivo": "V živo",
        "dodaj_mapo": "Dodaj medijsko mapo", "preklici": "Prekliči", "dodaj": "Dodaj",
        "tok": "Tok ni dosegljiv. Preveri naslov in povezavo.", "datoteka": "Datoteke ni mogoče prebrati.",
        "format": "Tega zapisa ni mogoče predvajati.",
        "zascita": "Posnetek je zaščiten (DRM) in ga Safeer ne predvaja.",
        "zacetek": "Predvajanja ni bilo mogoče začeti.", "splosno": "Predvajanje se je ustavilo zaradi napake.",
    },
    "en": {
        "dvd": "The disc can't be read. Safeer doesn't unlock protected (CSS) discs.",
        "podnapisi": "Subtitles", "podnapisi_izklop": "Off", "podnapisi_vgrajeni": "Built-in", "podnapisi_v_videu": "Subtitles in the video",
        "deli_datoteko": "Choose a file to share", "izberi_mapo": "Choose a folder to share",
        "premik": "Seek", "dodaj_datoteke": "Add files", "prejsnja": "Previous", "naslednja": "Next",
        "premor": "Pause", "nadaljuj": "Resume", "cel_zaslon": "Full screen", "cakalna_vrsta": "Up next",
        "nic": "Nothing playing", "v_zivo": "Live", "dodaj_mapo": "Add media folder", "preklici": "Cancel",
        "dodaj": "Add", "tok": "Stream unreachable. Check the address and connection.",
        "datoteka": "The file can't be read.", "format": "This format can't be played.",
        "zascita": "This recording is DRM-protected and Safeer doesn't play it.",
        "zacetek": "Playback couldn't start.", "splosno": "Playback stopped because of an error.",
    },
    "de": {
        "dvd": "Die Disc kann nicht gelesen werden. Geschützte Discs (CSS) entsperrt Safeer nicht.",
        "podnapisi": "Untertitel", "podnapisi_izklop": "Aus", "podnapisi_vgrajeni": "Eingebettet", "podnapisi_v_videu": "Untertitel im Video",
        "deli_datoteko": "Datei zum Teilen wählen", "izberi_mapo": "Ordner zum Teilen wählen",
        "premik": "Spulen", "dodaj_datoteke": "Dateien hinzufügen", "prejsnja": "Zurück", "naslednja": "Weiter",
        "premor": "Pause", "nadaljuj": "Fortsetzen", "cel_zaslon": "Vollbild", "cakalna_vrsta": "Als Nächstes",
        "nic": "Keine Wiedergabe", "v_zivo": "Live", "dodaj_mapo": "Medienordner hinzufügen",
        "preklici": "Abbrechen", "dodaj": "Hinzufügen",
        "tok": "Stream nicht erreichbar. Adresse und Verbindung prüfen.",
        "datoteka": "Die Datei kann nicht gelesen werden.", "format": "Dieses Format kann nicht abgespielt werden.",
        "zascita": "Die Aufnahme ist DRM-geschützt; Safeer spielt sie nicht ab.",
        "zacetek": "Die Wiedergabe konnte nicht starten.", "splosno": "Die Wiedergabe wurde wegen eines Fehlers beendet.",
    },
    "es": {
        "dvd": "No se puede leer el disco. Safeer no desbloquea discos protegidos (CSS).",
        "podnapisi": "Subtítulos", "podnapisi_izklop": "Desactivados", "podnapisi_vgrajeni": "Integrados", "podnapisi_v_videu": "Subtítulos del vídeo",
        "deli_datoteko": "Elige un archivo para compartir", "izberi_mapo": "Elige una carpeta para compartir",
        "premik": "Buscar", "dodaj_datoteke": "Añadir archivos", "prejsnja": "Anterior", "naslednja": "Siguiente",
        "premor": "Pausa", "nadaljuj": "Reanudar", "cel_zaslon": "Pantalla completa", "cakalna_vrsta": "A continuación",
        "nic": "No se reproduce nada", "v_zivo": "En directo", "dodaj_mapo": "Añadir carpeta multimedia",
        "preklici": "Cancelar", "dodaj": "Añadir",
        "tok": "No se puede acceder a la emisión. Revisa la dirección y la conexión.",
        "datoteka": "No se puede leer el archivo.", "format": "Este formato no se puede reproducir.",
        "zascita": "La grabación está protegida con DRM y Safeer no la reproduce.",
        "zacetek": "No se pudo iniciar la reproducción.", "splosno": "La reproducción se detuvo por un error.",
    },
    "fr": {
        "dvd": "Impossible de lire le disque. Safeer ne déverrouille pas les disques protégés (CSS).",
        "podnapisi": "Sous-titres", "podnapisi_izklop": "Désactivés", "podnapisi_vgrajeni": "Intégrés", "podnapisi_v_videu": "Sous-titres de la vidéo",
        "deli_datoteko": "Choisir un fichier à partager", "izberi_mapo": "Choisir un dossier à partager",
        "premik": "Avancer", "dodaj_datoteke": "Ajouter des fichiers", "prejsnja": "Précédent", "naslednja": "Suivant",
        "premor": "Pause", "nadaljuj": "Reprendre", "cel_zaslon": "Plein écran", "cakalna_vrsta": "À suivre",
        "nic": "Aucune lecture", "v_zivo": "En direct", "dodaj_mapo": "Ajouter un dossier multimédia",
        "preklici": "Annuler", "dodaj": "Ajouter",
        "tok": "Flux inaccessible. Vérifiez l'adresse et la connexion.",
        "datoteka": "Impossible de lire le fichier.", "format": "Ce format ne peut pas être lu.",
        "zascita": "L'enregistrement est protégé par DRM ; Safeer ne le lit pas.",
        "zacetek": "La lecture n'a pas pu démarrer.", "splosno": "La lecture s'est arrêtée à cause d'une erreur.",
    },
    "it": {
        "dvd": "Impossibile leggere il disco. Safeer non sblocca i dischi protetti (CSS).",
        "podnapisi": "Sottotitoli", "podnapisi_izklop": "Disattivati", "podnapisi_vgrajeni": "Integrati", "podnapisi_v_videu": "Sottotitoli nel video",
        "deli_datoteko": "Scegli un file da condividere", "izberi_mapo": "Scegli una cartella da condividere",
        "premik": "Scorri", "dodaj_datoteke": "Aggiungi file", "prejsnja": "Precedente", "naslednja": "Successivo",
        "premor": "Pausa", "nadaljuj": "Riprendi", "cel_zaslon": "Schermo intero", "cakalna_vrsta": "A seguire",
        "nic": "Nessuna riproduzione", "v_zivo": "In diretta", "dodaj_mapo": "Aggiungi cartella multimediale",
        "preklici": "Annulla", "dodaj": "Aggiungi",
        "tok": "Flusso non raggiungibile. Controlla l'indirizzo e la connessione.",
        "datoteka": "Impossibile leggere il file.", "format": "Questo formato non può essere riprodotto.",
        "zascita": "La registrazione è protetta da DRM e Safeer non la riproduce.",
        "zacetek": "Impossibile avviare la riproduzione.", "splosno": "La riproduzione si è interrotta per un errore.",
    },
}


def besedilo(kljuc: str, jezik: str = "en") -> str:
    """Napis v jeziku vmesnika; neznan jezik ali ključ pade na angleščino (in nato na ključ)."""
    jezik = (jezik or "en")[:2].lower()
    return BESEDILA.get(jezik, BESEDILA["en"]).get(kljuc) or BESEDILA["en"].get(kljuc, kljuc)
