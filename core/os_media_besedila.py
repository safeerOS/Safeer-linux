"""Besedila domačega GTK predvajalnika in dialogov Safeer Media v jezikih vmesnika Safeer OS.

Stran (assets/os/besedila.js) ima svoje prevode; tu so samo napisi, ki jih riše GTK (okno
predvajalnika, izbirniki map in datotek), da okno ne ostane slovensko v angleškem vmesniku.
"""

from __future__ import annotations

JEZIKI = ("sl", "en", "de", "es", "fr", "it")

BESEDILA: dict[str, dict[str, str]] = {
    "sl": {
        "poslji": "Pošlji na napravo", "poslano": "Poslano na {ime} – tam potrdi s Sprejmi.", "poslano_odpri": "Poslano na {ime} – tam odpri Safeer OS in potrdi s Sprejmi (obvestilo tam ni vidno).", "poslji_napaka": "{ime} ne odgovarja.", "poslji_stara": "{ime} tega še ne zna – tam posodobi Safeer OS.", "poslji_ni": "V Safeer Linku ni druge naprave.", "poslji_ni_deljeno": "Tega ni mogoče poslati (datoteka ni v deljeni mapi).", "poslji_izklopljeno": "{ime} ne sprejema predvajanja z drugih naprav.",
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
        "poslji": "Send to device", "poslano": "Sent to {ime} – confirm there with Accept.", "poslano_odpri": "Sent to {ime} – open Safeer OS on that device and confirm with Accept (a notification is not visible there).", "poslji_napaka": "{ime} is not answering.", "poslji_stara": "{ime} does not know this yet – update Safeer OS there.", "poslji_ni": "No other device in Safeer Link.", "poslji_ni_deljeno": "This cannot be sent (the file is not in a shared folder).", "poslji_izklopljeno": "{ime} does not accept playback from other devices.",
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
        "poslji": "An Gerät senden", "poslano": "An {ime} gesendet – dort mit Annehmen bestätigen.", "poslano_odpri": "An {ime} gesendet – öffne dort Safeer OS und bestätige mit Annehmen (eine Benachrichtigung ist dort nicht sichtbar).", "poslji_napaka": "{ime} antwortet nicht.", "poslji_stara": "{ime} kennt das noch nicht – dort Safeer OS aktualisieren.", "poslji_ni": "Kein anderes Gerät im Safeer Link.", "poslji_ni_deljeno": "Das kann nicht gesendet werden (Datei nicht in einem freigegebenen Ordner).", "poslji_izklopljeno": "{ime} nimmt keine Wiedergabe von anderen Geräten an.",
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
        "poslji": "Enviar a un dispositivo", "poslano": "Enviado a {ime} – confirma allí con Aceptar.", "poslano_odpri": "Enviado a {ime} – abre Safeer OS en ese dispositivo y confirma con Aceptar (allí no se ve ninguna notificación).", "poslji_napaka": "{ime} no responde.", "poslji_stara": "{ime} aún no sabe hacerlo – actualiza Safeer OS allí.", "poslji_ni": "No hay otro dispositivo en Safeer Link.", "poslji_ni_deljeno": "No se puede enviar (el archivo no está en una carpeta compartida).", "poslji_izklopljeno": "{ime} no acepta reproducción desde otros dispositivos.",
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
        "poslji": "Envoyer à un appareil", "poslano": "Envoyé à {ime} – confirme là-bas avec Accepter.", "poslano_odpri": "Envoyé à {ime} – ouvre Safeer OS sur cet appareil et confirme avec Accepter (aucune notification n'y est visible).", "poslji_napaka": "{ime} ne répond pas.", "poslji_stara": "{ime} ne sait pas encore le faire – mets à jour Safeer OS là-bas.", "poslji_ni": "Aucun autre appareil dans Safeer Link.", "poslji_ni_deljeno": "Impossible à envoyer (le fichier n'est pas dans un dossier partagé).", "poslji_izklopljeno": "{ime} n'accepte pas la lecture depuis d'autres appareils.",
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
        "poslji": "Invia a un dispositivo", "poslano": "Inviato a {ime} – conferma lì con Accetta.", "poslano_odpri": "Inviato a {ime} – apri Safeer OS su quel dispositivo e conferma con Accetta (lì nessuna notifica è visibile).", "poslji_napaka": "{ime} non risponde.", "poslji_stara": "{ime} non lo sa ancora fare – aggiorna Safeer OS lì.", "poslji_ni": "Nessun altro dispositivo in Safeer Link.", "poslji_ni_deljeno": "Non si può inviare (il file non è in una cartella condivisa).", "poslji_izklopljeno": "{ime} non accetta la riproduzione da altri dispositivi.",
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
