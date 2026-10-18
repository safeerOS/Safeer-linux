"""safeer://procesi - the browser's own task manager page.

One row per tab from the monitor's last sample: CPU share, resident memory, threads, state
(active / playing sound / sleeping / why it may not sleep) and two actions that go back to the
browser as links on the same scheme (`?spi=<id>` puts a tab to sleep, `?zapri=<id>` closes it).
Embedded web apps (chats beside the browser, Sporocila) are listed too, without actions.

Since 1.0.127 (GTK4 Splet, core/splet_spanje.py) the action links carry a one-time key (`&k=`): the
browser acts only on a key it handed out, so an old history entry or a reload never repeats an
action. Colours come from assets/os/tokens.css (one source for all Safeer pages). The page refreshes
itself every three seconds with location.replace (no history entries), but only while it is visible
and nothing on it has keyboard focus - a meta refresh used to throw the focus away every three seconds.
It is rendered from plain data, so it is testable without GTK.

Since 1.0.127 (Safeer OS 0.4.85, lastnik 18. 10. 2026) the page covers the whole program, not only tabs: every
tab and embedded app, the main process (in Safeer OS: shell, Control, Splet and player in one process), the WebKit
network and other web processes, sub-processes (rqbit, ffmpeg ...) and the on-demand services of
core/storitve_na_zahtevo.py (running / stopped, last use, when they stop). Next to the current value each
process shows the average and the peak of the last hour from core/poraba_zgodovina.py (one cheap sample every 30 s).
"""
import functools
import html
import os
import secrets
import urllib.parse

REFRESH_SECONDS = 3
PAGE_URI = "safeer://procesi"

_TEXT = {
    "sl": {
        "title": "Procesi",
        "intro": "Vsak zavihek teče v svojem procesu. Safeer meri vsaki dve sekundi; težek zavihek v ozadju brez zvoka po minuti zaspi.",
        "tab": "Zavihek", "cpu": "CPU", "memory": "Pomnilnik", "threads": "Niti", "state": "Stanje", "actions": "Dejanja",
        "active": "aktiven", "audio": "zvok", "sleeping": "spi", "hot": "nad proračunom", "hog": "dolgo nad proračunom",
        "sleep": "Uspavaj", "close": "Zapri", "total": "Skupaj", "no_process": "—",
        "limit": "Meja pomnilnika na zavihek: {limit} MB · proračun CPU: {cpu} % enega jedra",
        "rule": "Zavihek v ozadju, ki ga {min} min ne uporabljaš, zaspi in sprosti pomnilnik; ko se vrneš, se naloži znova na istem mestu. Nikoli ne zaspi zavihek, ki predvaja zvok ali video, ima urejen ali poslan obrazec, prenos, kamero, mikrofon ali deljenje zaslona.",
        "app": "vdelana aplikacija", "media": "predvajanje", "form": "urejen obrazec", "post": "poslan obrazec",
        "download": "prenos", "capture": "kamera, mikrofon ali zaslon", "linked": "povezano okno",
    },
    "en": {
        "title": "Processes",
        "intro": "Every tab runs in its own process. Safeer samples every two seconds; a heavy background tab without sound is put to sleep after a minute.",
        "tab": "Tab", "cpu": "CPU", "memory": "Memory", "threads": "Threads", "state": "State", "actions": "Actions",
        "active": "active", "audio": "sound", "sleeping": "sleeping", "hot": "over budget", "hog": "over budget for long",
        "sleep": "Sleep", "close": "Close", "total": "Total", "no_process": "—",
        "limit": "Memory limit per tab: {limit} MB · CPU budget: {cpu} % of one core",
        "rule": "A background tab you have not used for {min} min goes to sleep and frees its memory; when you come back it loads again at the same place. A tab never sleeps while it plays sound or video, or has an edited or submitted form, a download, the camera, the microphone or screen sharing.",
        "app": "embedded app", "media": "playing", "form": "form being edited", "post": "submitted form",
        "download": "download", "capture": "camera, microphone or screen", "linked": "linked window",
    },
    "de": {
        "title": "Prozesse",
        "intro": "Jeder Tab läuft in einem eigenen Prozess. Safeer misst alle zwei Sekunden; ein schwerer Hintergrund-Tab ohne Ton wird nach einer Minute schlafen gelegt.",
        "tab": "Tab", "cpu": "CPU", "memory": "Speicher", "threads": "Threads", "state": "Status", "actions": "Aktionen",
        "active": "aktiv", "audio": "Ton", "sleeping": "schläft", "hot": "über dem Budget", "hog": "lange über dem Budget",
        "sleep": "Schlafen legen", "close": "Schließen", "total": "Gesamt", "no_process": "—",
        "limit": "Speichergrenze pro Tab: {limit} MB · CPU-Budget: {cpu} % eines Kerns",
        "rule": "Ein Hintergrund-Tab, den du {min} Min. nicht benutzt hast, schläft ein und gibt seinen Speicher frei; wenn du zurückkehrst, lädt er an derselben Stelle neu. Ein Tab schläft nie, solange er Ton oder Video abspielt oder ein bearbeitetes oder gesendetes Formular, einen Download, die Kamera, das Mikrofon oder eine Bildschirmfreigabe hat.",
        "app": "eingebettete App", "media": "Wiedergabe", "form": "Formular in Bearbeitung", "post": "gesendetes Formular",
        "download": "Download", "capture": "Kamera, Mikrofon oder Bildschirm", "linked": "verknüpftes Fenster",
    },
    "es": {
        "title": "Procesos",
        "intro": "Cada pestaña se ejecuta en su propio proceso. Safeer mide cada dos segundos; una pestaña pesada en segundo plano y sin sonido se duerme al cabo de un minuto.",
        "tab": "Pestaña", "cpu": "CPU", "memory": "Memoria", "threads": "Hilos", "state": "Estado", "actions": "Acciones",
        "active": "activa", "audio": "sonido", "sleeping": "dormida", "hot": "por encima del límite", "hog": "mucho tiempo por encima del límite",
        "sleep": "Dormir", "close": "Cerrar", "total": "Total", "no_process": "—",
        "limit": "Límite de memoria por pestaña: {limit} MB · límite de CPU: {cpu} % de un núcleo",
        "rule": "Una pestaña en segundo plano que no usas desde hace {min} min se duerme y libera su memoria; cuando vuelves, se carga de nuevo en el mismo lugar. Una pestaña nunca se duerme mientras reproduce sonido o vídeo, o tiene un formulario editado o enviado, una descarga, la cámara, el micrófono o la pantalla compartida.",
        "app": "aplicación integrada", "media": "reproducción", "form": "formulario en edición", "post": "formulario enviado",
        "download": "descarga", "capture": "cámara, micrófono o pantalla", "linked": "ventana vinculada",
    },
    "fr": {
        "title": "Processus",
        "intro": "Chaque onglet tourne dans son propre processus. Safeer mesure toutes les deux secondes ; un onglet lourd en arrière-plan sans son est mis en veille au bout d’une minute.",
        "tab": "Onglet", "cpu": "CPU", "memory": "Mémoire", "threads": "Threads", "state": "État", "actions": "Actions",
        "active": "actif", "audio": "son", "sleeping": "en veille", "hot": "au-delà du budget", "hog": "longtemps au-delà du budget",
        "sleep": "Mettre en veille", "close": "Fermer", "total": "Total", "no_process": "—",
        "limit": "Limite de mémoire par onglet : {limit} Mo · budget CPU : {cpu} % d’un cœur",
        "rule": "Un onglet en arrière-plan que vous n’avez pas utilisé depuis {min} min se met en veille et libère sa mémoire ; à votre retour, il se recharge au même endroit. Un onglet ne se met jamais en veille tant qu’il lit du son ou une vidéo, ou qu’il a un formulaire modifié ou envoyé, un téléchargement, la caméra, le micro ou un partage d’écran.",
        "app": "application intégrée", "media": "lecture", "form": "formulaire en cours", "post": "formulaire envoyé",
        "download": "téléchargement", "capture": "caméra, micro ou écran", "linked": "fenêtre liée",
    },
    "it": {
        "title": "Processi",
        "intro": "Ogni scheda gira in un proprio processo. Safeer misura ogni due secondi; una scheda pesante in background senza audio viene sospesa dopo un minuto.",
        "tab": "Scheda", "cpu": "CPU", "memory": "Memoria", "threads": "Thread", "state": "Stato", "actions": "Azioni",
        "active": "attiva", "audio": "audio", "sleeping": "sospesa", "hot": "oltre il budget", "hog": "a lungo oltre il budget",
        "sleep": "Sospendi", "close": "Chiudi", "total": "Totale", "no_process": "—",
        "limit": "Limite di memoria per scheda: {limit} MB · budget CPU: {cpu} % di un core",
        "rule": "Una scheda in background che non usi da {min} min viene sospesa e libera la memoria; quando torni, si ricarica nello stesso punto. Una scheda non viene mai sospesa mentre riproduce audio o video, o ha un modulo modificato o inviato, un download, la fotocamera, il microfono o la condivisione dello schermo.",
        "app": "app integrata", "media": "riproduzione", "form": "modulo in compilazione", "post": "modulo inviato",
        "download": "download", "capture": "fotocamera, microfono o schermo", "linked": "finestra collegata",
    },
}

#: Razlogi, zakaj zavihek ne sme zaspati (core/splet_spanje.razlogi_zascite), v vrstnem redu prikaza.
REASONS = ("media", "form", "post", "download", "capture", "linked")

#: Besedila za celoten program, zgodovino in storitve (1.0.127). Dodana v _TEXT spodaj, da ima vsak jezik vse kljuce.
_DODATNO = {
    "sl": {
        "now": "zdaj", "avg": "povprečje", "peak": "vrh",
        "history": "Povprečje in vrh veljata za zadnjo uro (vzorec vsakih {s} s, tudi ko stran ni odprta).",
        "history_wait": "Zgodovina se zbira: prvi vzorec čez največ {s} s.",
        "system": "{app}: vsi procesi", "process": "Proces", "what": "Kaj je",
        "main_os": "Safeer OS – lupina, Control, Splet in predvajalnik", "main_app": "{app}",
        "kind_glavni": "glavni proces", "kind_spletni": "spletni proces", "kind_omrezni": "omrežni proces (piškotki, prenosi)",
        "kind_peskovnik": "peskovnik spletnih procesov", "kind_drugo": "podproces", "kind_zavihki": "spletni procesi zavihkov in vdelanih aplikacij (podrobno zgoraj)",
        "web_other": "drugo okno, vdelan pogled ali vnaprej pripravljen proces", "web_tab": "zavihek: {t}",
        "sandbox_n": "{n} procesov", "of_service": "storitev: {s}", "total_all": "Skupaj {app}",
        "services": "Storitve", "service": "Storitev", "status": "Stanje", "last_use": "Zadnja raba", "stops": "Ustavi se",
        "running": "teče", "stopped": "ustavljena", "off": "izklopljena", "not_started": "ni zagnana", "periodic": "občasno",
        "never_used": "v tem zagonu še ne", "ago_s": "pred {n} s", "ago_min": "pred {n} min", "ago_h": "pred {n} h",
        "idle_stop": "po {n} min mirovanja", "always": "nikoli – {why}", "every_h": "teče vsake {n} h",
        "why_varuje": "varuje računalnik", "why_dosegljivost": "druge naprave morajo računalnik najti",
        "why_obvestila": "sporočila in obvestila takoj", "why_takoj": "prvo iskanje brez čakanja",
        "services_rule": "Storitev, ki je ne uporabljaš, se zažene šele, ko jo potrebuješ, in se po mirovanju ustavi sama. Kar te varuje ali mora biti dosegljivo z drugih naprav, teče vedno.",
        "svc_scit": "Ščit (zaščita DNS)", "svc_link": "Safeer Link (sprejem drugih naprav)", "svc_varuh": "Varuh pomnilnika",
        "svc_posodobitve": "Posodobitve", "svc_sporocila": "Sporočila", "svc_iskalnik": "Indeks iskanja datotek",
        "svc_torrent": "Torrent (rqbit)", "svc_torrent_naprave": "Torrent za druge naprave (rqbit)",
        "svc_teamwork": "Teamwork (skupno urejanje)", "svc_twitch": "Twitch (lokalni posrednik)", "svc_doh": "Šifriran DNS za Splet (DoH)",
        "svc_ciscenje_gledanja": "Čiščenje filmov, ki jih nihče ne gleda", "svc_ciscenje_prenosov": "Čiščenje prenosov za naprave",
    },
    "en": {
        "now": "now", "avg": "average", "peak": "peak",
        "history": "Average and peak cover the last hour (one sample every {s} s, also while this page is closed).",
        "history_wait": "Collecting history: the first sample comes within {s} s.",
        "system": "{app}: all processes", "process": "Process", "what": "What it is",
        "main_os": "Safeer OS – shell, Control, Splet and player", "main_app": "{app}",
        "kind_glavni": "main process", "kind_spletni": "web process", "kind_omrezni": "network process (cookies, downloads)",
        "kind_peskovnik": "web process sandbox", "kind_drugo": "sub-process", "kind_zavihki": "web processes of tabs and embedded apps (details above)",
        "web_other": "another window, an embedded view or a prepared spare process", "web_tab": "tab: {t}",
        "sandbox_n": "{n} processes", "of_service": "service: {s}", "total_all": "{app} total",
        "services": "Services", "service": "Service", "status": "State", "last_use": "Last used", "stops": "Stops",
        "running": "running", "stopped": "stopped", "off": "off", "not_started": "not started", "periodic": "periodic",
        "never_used": "not yet since start", "ago_s": "{n} s ago", "ago_min": "{n} min ago", "ago_h": "{n} h ago",
        "idle_stop": "after {n} min idle", "always": "never – {why}", "every_h": "runs every {n} h",
        "why_varuje": "it protects the computer", "why_dosegljivost": "other devices must find the computer",
        "why_obvestila": "messages and notifications right away", "why_takoj": "first search without waiting",
        "services_rule": "A service you do not use starts only when you need it and stops by itself when idle. What protects you or must be reachable from your other devices always runs.",
        "svc_scit": "Shield (DNS protection)", "svc_link": "Safeer Link (other devices reach this one)", "svc_varuh": "Memory guard",
        "svc_posodobitve": "Updates", "svc_sporocila": "Messages", "svc_iskalnik": "File search index",
        "svc_torrent": "Torrent (rqbit)", "svc_torrent_naprave": "Torrent for other devices (rqbit)",
        "svc_teamwork": "Teamwork (editing together)", "svc_twitch": "Twitch (local relay)", "svc_doh": "Encrypted DNS for Splet (DoH)",
        "svc_ciscenje_gledanja": "Clean-up of films nobody watches", "svc_ciscenje_prenosov": "Clean-up of downloads for devices",
    },
    "de": {
        "now": "jetzt", "avg": "Mittel", "peak": "Spitze",
        "history": "Mittel und Spitze gelten für die letzte Stunde (eine Messung alle {s} s, auch wenn diese Seite geschlossen ist).",
        "history_wait": "Verlauf wird gesammelt: die erste Messung kommt in höchstens {s} s.",
        "system": "{app}: alle Prozesse", "process": "Prozess", "what": "Was es ist",
        "main_os": "Safeer OS – Oberfläche, Control, Splet und Player", "main_app": "{app}",
        "kind_glavni": "Hauptprozess", "kind_spletni": "Webprozess", "kind_omrezni": "Netzwerkprozess (Cookies, Downloads)",
        "kind_peskovnik": "Sandbox der Webprozesse", "kind_drugo": "Unterprozess", "kind_zavihki": "Webprozesse der Tabs und eingebetteten Apps (Details oben)",
        "web_other": "anderes Fenster, eingebettete Ansicht oder vorbereiteter Reserveprozess", "web_tab": "Tab: {t}",
        "sandbox_n": "{n} Prozesse", "of_service": "Dienst: {s}", "total_all": "{app} gesamt",
        "services": "Dienste", "service": "Dienst", "status": "Status", "last_use": "Zuletzt benutzt", "stops": "Stoppt",
        "running": "läuft", "stopped": "gestoppt", "off": "aus", "not_started": "nicht gestartet", "periodic": "regelmäßig",
        "never_used": "seit dem Start noch nicht", "ago_s": "vor {n} s", "ago_min": "vor {n} Min.", "ago_h": "vor {n} Std.",
        "idle_stop": "nach {n} Min. Leerlauf", "always": "nie – {why}", "every_h": "läuft alle {n} Std.",
        "why_varuje": "schützt den Computer", "why_dosegljivost": "andere Geräte müssen den Computer finden",
        "why_obvestila": "Nachrichten und Benachrichtigungen sofort", "why_takoj": "erste Suche ohne Warten",
        "services_rule": "Ein Dienst, den du nicht benutzt, startet erst, wenn du ihn brauchst, und stoppt im Leerlauf von selbst. Was dich schützt oder von deinen anderen Geräten erreichbar sein muss, läuft immer.",
        "svc_scit": "Schild (DNS-Schutz)", "svc_link": "Safeer Link (andere Geräte erreichen diesen)", "svc_varuh": "Speicherwächter",
        "svc_posodobitve": "Aktualisierungen", "svc_sporocila": "Nachrichten", "svc_iskalnik": "Dateisuchindex",
        "svc_torrent": "Torrent (rqbit)", "svc_torrent_naprave": "Torrent für andere Geräte (rqbit)",
        "svc_teamwork": "Teamwork (gemeinsam bearbeiten)", "svc_twitch": "Twitch (lokales Relais)", "svc_doh": "Verschlüsseltes DNS für Splet (DoH)",
        "svc_ciscenje_gledanja": "Aufräumen von Filmen, die niemand ansieht", "svc_ciscenje_prenosov": "Aufräumen von Downloads für Geräte",
    },
    "es": {
        "now": "ahora", "avg": "media", "peak": "pico",
        "history": "La media y el pico corresponden a la última hora (una muestra cada {s} s, también con esta página cerrada).",
        "history_wait": "Recogiendo historial: la primera muestra llega en {s} s como máximo.",
        "system": "{app}: todos los procesos", "process": "Proceso", "what": "Qué es",
        "main_os": "Safeer OS – escritorio, Control, Splet y reproductor", "main_app": "{app}",
        "kind_glavni": "proceso principal", "kind_spletni": "proceso web", "kind_omrezni": "proceso de red (cookies, descargas)",
        "kind_peskovnik": "aislamiento de los procesos web", "kind_drugo": "subproceso", "kind_zavihki": "procesos web de pestañas y aplicaciones integradas (detalle arriba)",
        "web_other": "otra ventana, una vista integrada o un proceso de reserva preparado", "web_tab": "pestaña: {t}",
        "sandbox_n": "{n} procesos", "of_service": "servicio: {s}", "total_all": "Total de {app}",
        "services": "Servicios", "service": "Servicio", "status": "Estado", "last_use": "Último uso", "stops": "Se detiene",
        "running": "en marcha", "stopped": "detenido", "off": "desactivado", "not_started": "no iniciado", "periodic": "periódico",
        "never_used": "aún no desde el inicio", "ago_s": "hace {n} s", "ago_min": "hace {n} min", "ago_h": "hace {n} h",
        "idle_stop": "tras {n} min sin uso", "always": "nunca – {why}", "every_h": "se ejecuta cada {n} h",
        "why_varuje": "protege el ordenador", "why_dosegljivost": "los otros dispositivos deben encontrar el ordenador",
        "why_obvestila": "mensajes y avisos al momento", "why_takoj": "primera búsqueda sin esperas",
        "services_rule": "Un servicio que no usas solo se inicia cuando lo necesitas y se detiene solo cuando no se usa. Lo que te protege o debe ser accesible desde tus otros dispositivos funciona siempre.",
        "svc_scit": "Escudo (protección DNS)", "svc_link": "Safeer Link (otros dispositivos llegan a este)", "svc_varuh": "Guardián de memoria",
        "svc_posodobitve": "Actualizaciones", "svc_sporocila": "Mensajes", "svc_iskalnik": "Índice de búsqueda de archivos",
        "svc_torrent": "Torrent (rqbit)", "svc_torrent_naprave": "Torrent para otros dispositivos (rqbit)",
        "svc_teamwork": "Teamwork (edición conjunta)", "svc_twitch": "Twitch (relé local)", "svc_doh": "DNS cifrado para Splet (DoH)",
        "svc_ciscenje_gledanja": "Limpieza de películas que nadie ve", "svc_ciscenje_prenosov": "Limpieza de descargas para dispositivos",
    },
    "fr": {
        "now": "maintenant", "avg": "moyenne", "peak": "pic",
        "history": "La moyenne et le pic portent sur la dernière heure (une mesure toutes les {s} s, même page fermée).",
        "history_wait": "Historique en cours de collecte : première mesure dans {s} s au plus.",
        "system": "{app} : tous les processus", "process": "Processus", "what": "Rôle",
        "main_os": "Safeer OS – bureau, Control, Splet et lecteur", "main_app": "{app}",
        "kind_glavni": "processus principal", "kind_spletni": "processus web", "kind_omrezni": "processus réseau (cookies, téléchargements)",
        "kind_peskovnik": "bac à sable des processus web", "kind_drugo": "sous-processus", "kind_zavihki": "processus web des onglets et applications intégrées (détail ci-dessus)",
        "web_other": "autre fenêtre, vue intégrée ou processus de réserve préparé", "web_tab": "onglet : {t}",
        "sandbox_n": "{n} processus", "of_service": "service : {s}", "total_all": "Total {app}",
        "services": "Services", "service": "Service", "status": "État", "last_use": "Dernière utilisation", "stops": "S’arrête",
        "running": "en marche", "stopped": "arrêté", "off": "désactivé", "not_started": "non démarré", "periodic": "périodique",
        "never_used": "pas encore depuis le démarrage", "ago_s": "il y a {n} s", "ago_min": "il y a {n} min", "ago_h": "il y a {n} h",
        "idle_stop": "après {n} min d’inactivité", "always": "jamais – {why}", "every_h": "s’exécute toutes les {n} h",
        "why_varuje": "il protège l’ordinateur", "why_dosegljivost": "vos autres appareils doivent trouver l’ordinateur",
        "why_obvestila": "messages et notifications immédiats", "why_takoj": "première recherche sans attente",
        "services_rule": "Un service que vous n’utilisez pas ne démarre que lorsque vous en avez besoin et s’arrête de lui-même quand il est inactif. Ce qui vous protège ou doit être joignable depuis vos autres appareils tourne toujours.",
        "svc_scit": "Bouclier (protection DNS)", "svc_link": "Safeer Link (vos autres appareils le joignent)", "svc_varuh": "Gardien de mémoire",
        "svc_posodobitve": "Mises à jour", "svc_sporocila": "Messages", "svc_iskalnik": "Index de recherche de fichiers",
        "svc_torrent": "Torrent (rqbit)", "svc_torrent_naprave": "Torrent pour les autres appareils (rqbit)",
        "svc_teamwork": "Teamwork (édition à plusieurs)", "svc_twitch": "Twitch (relais local)", "svc_doh": "DNS chiffré pour Splet (DoH)",
        "svc_ciscenje_gledanja": "Nettoyage des films que personne ne regarde", "svc_ciscenje_prenosov": "Nettoyage des téléchargements pour les appareils",
    },
    "it": {
        "now": "ora", "avg": "media", "peak": "picco",
        "history": "Media e picco riguardano l’ultima ora (un campione ogni {s} s, anche a pagina chiusa).",
        "history_wait": "Raccolta della cronologia: il primo campione arriva entro {s} s.",
        "system": "{app}: tutti i processi", "process": "Processo", "what": "Che cos’è",
        "main_os": "Safeer OS – desktop, Control, Splet e lettore", "main_app": "{app}",
        "kind_glavni": "processo principale", "kind_spletni": "processo web", "kind_omrezni": "processo di rete (cookie, download)",
        "kind_peskovnik": "sandbox dei processi web", "kind_drugo": "sottoprocesso", "kind_zavihki": "processi web di schede e app integrate (dettagli sopra)",
        "web_other": "altra finestra, vista integrata o processo di riserva preparato", "web_tab": "scheda: {t}",
        "sandbox_n": "{n} processi", "of_service": "servizio: {s}", "total_all": "Totale {app}",
        "services": "Servizi", "service": "Servizio", "status": "Stato", "last_use": "Ultimo uso", "stops": "Si ferma",
        "running": "attivo", "stopped": "fermato", "off": "disattivato", "not_started": "non avviato", "periodic": "periodico",
        "never_used": "non ancora dall’avvio", "ago_s": "{n} s fa", "ago_min": "{n} min fa", "ago_h": "{n} h fa",
        "idle_stop": "dopo {n} min di inattività", "always": "mai – {why}", "every_h": "gira ogni {n} h",
        "why_varuje": "protegge il computer", "why_dosegljivost": "gli altri dispositivi devono trovare il computer",
        "why_obvestila": "messaggi e notifiche subito", "why_takoj": "prima ricerca senza attesa",
        "services_rule": "Un servizio che non usi si avvia solo quando ti serve e si ferma da solo quando resta inattivo. Ciò che ti protegge o deve essere raggiungibile dagli altri tuoi dispositivi è sempre attivo.",
        "svc_scit": "Scudo (protezione DNS)", "svc_link": "Safeer Link (gli altri dispositivi lo raggiungono)", "svc_varuh": "Guardiano della memoria",
        "svc_posodobitve": "Aggiornamenti", "svc_sporocila": "Messaggi", "svc_iskalnik": "Indice di ricerca dei file",
        "svc_torrent": "Torrent (rqbit)", "svc_torrent_naprave": "Torrent per altri dispositivi (rqbit)",
        "svc_teamwork": "Teamwork (modifica insieme)", "svc_twitch": "Twitch (inoltro locale)", "svc_doh": "DNS cifrato per Splet (DoH)",
        "svc_ciscenje_gledanja": "Pulizia dei film che nessuno guarda", "svc_ciscenje_prenosov": "Pulizia dei download per i dispositivi",
    },
}
for _jezik, _besedila in _DODATNO.items():
    _TEXT[_jezik].update(_besedila)

#: Vrstni red vrst procesov v tabeli programa (core/poraba_zgodovina).
KINDS = ("glavni", "omrezni", "zavihki", "spletni", "drugo", "peskovnik")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@functools.lru_cache(maxsize=1)
def _tokens() -> str:
    """Barve iz enega vira (assets/os/tokens.css), kot predogled datotek in Splet; prebrane enkrat (stran se osvezi
    vsake 3 s)."""
    try:
        with open(os.path.join(_ROOT, "assets", "os", "tokens.css"), encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


def _fmt_mb(mb, lang):
    if mb >= 1024:
        text = f"{mb / 1024:.2f} GB"
        return text if lang == "en" else text.replace(".", ",")     # decimalna vejica v vseh jezikih razen en
    return f"{mb} MB"


def _action(kind, tab_id, key):
    link = f"{PAGE_URI}?{kind}={urllib.parse.quote(tab_id, safe='')}"
    return link + (f"&k={urllib.parse.quote(key, safe='')}" if key else "")


def _pct(cpu):
    return "—" if cpu is None else f"{int(round(cpu * 100))} %"


def _mem(mb, lang):
    return "—" if mb is None else _fmt_mb(int(mb), lang)


def _ago(seconds, tx):
    if seconds is None:
        return tx["never_used"]
    seconds = int(seconds)
    if seconds < 60:
        return tx["ago_s"].format(n=seconds)
    if seconds < 3600:
        return tx["ago_min"].format(n=seconds // 60)
    return tx["ago_h"].format(n=seconds // 3600)


def _usage_cells(row, lang, measured=True):
    """Six cells: CPU now/average/peak, memory now/average/peak (average and peak of the last hour)."""
    if not measured:
        return "<td>—</td>" * 6
    return (f"<td>{_pct(row.get('cpu'))}</td><td class=\"h\">{_pct(row.get('avg_cpu'))}</td>"
            f"<td class=\"h\">{_pct(row.get('peak_cpu'))}</td><td>{_mem(row.get('rss_mb'), lang)}</td>"
            f"<td class=\"h\">{_mem(row.get('avg_mb'), lang)}</td><td class=\"h\">{_mem(row.get('peak_mb'), lang)}</td>")


def _usage_head(tx, first, tail):
    """Two header rows: first column, CPU and memory groups (now / average / peak), then `tail` columns."""
    rest = "".join(f'<th scope="col" rowspan="2">{t}</th>' for t in tail)
    sub = "".join(f'<th scope="col">{tx[k]}</th>' for k in ("now", "avg", "peak"))
    return (f'<thead><tr><th scope="col" rowspan="2">{first}</th><th scope="colgroup" colspan="3">{tx["cpu"]}</th>'
            f'<th scope="colgroup" colspan="3">{tx["memory"]}</th>{rest}</tr><tr>{sub}{sub}</tr></thead>')


def _scroll(label):
    """Ovoj tabele, ki se v ozkem oknu drsi vodoravno: dosegljiv s tipkovnico (Tab, nato puscice), z imenom za bralnik."""
    return f'<div class="tabela" tabindex="0" role="region" aria-label="{html.escape(label)}">'


def _sum(values):
    values = [v for v in values if v is not None]
    return sum(values) if values else None


def _system_table(system, tx, lang, app):
    """Every process of the program: main, network, web processes, sub-processes (rqbit, ffmpeg ...) and the WebKit
    sandbox as one line; the last line is the whole program."""
    order = {k: i for i, k in enumerate(KINDS)}
    body = []
    for row in sorted(system, key=lambda r: (order.get(r.get("kind"), 9), -(r.get("rss_mb") or 0))):
        kind = row.get("kind") or "drugo"
        if kind == "glavni":
            name = tx["main_os"] if app == "Safeer OS" else tx["main_app"].format(app=app or "Safeer")
        elif kind == "peskovnik":
            name = "bwrap, xdg-dbus-proxy"
        elif kind == "zavihki":
            name = "WebKitWebProcess"
        else:
            name = str(row.get("name") or "")
        what = [tx["kind_" + kind] if ("kind_" + kind) in tx else tx["kind_drugo"]]
        if kind in ("peskovnik", "zavihki"):
            what.append(tx["sandbox_n"].format(n=int(row.get("count") or 0)))
        if row.get("tab"):
            what.append(tx["web_tab"].format(t=row["tab"]))
        elif kind == "spletni":
            what.append(tx["web_other"])
        if row.get("service"):
            what.append(tx["of_service"].format(s=tx.get("svc_" + row["service"], row["service"])))
        pid = f' <span class="pid">{int(row["pid"])}</span>' if row.get("pid") else ""
        body.append(f'<tr><td class="t">{html.escape(name)}{pid}</td>{_usage_cells(row, lang)}'
                    f'<td>{int(row.get("threads") or 0)}</td><td>{html.escape(" · ".join(what))}</td></tr>')
    total = {"cpu": _sum(r.get("cpu") for r in system), "rss_mb": _sum(r.get("rss_mb") for r in system),
             "avg_cpu": _sum(r.get("avg_cpu") for r in system), "avg_mb": _sum(r.get("avg_mb") for r in system),
             "peak_cpu": None, "peak_mb": None}
    threads = sum(int(r.get("threads") or 0) for r in system)
    body.append(f'<tr class="total"><td class="t">{html.escape(tx["total_all"].format(app=app or "Safeer"))}</td>'
                f'{_usage_cells(total, lang)}<td>{threads}</td><td></td></tr>')
    naslov = html.escape(tx["system"].format(app=app or "Safeer"))
    return (f'<h2>{naslov}</h2>{_scroll(naslov)}<table>'
            f'{_usage_head(tx, tx["process"], (tx["threads"], tx["what"]))}<tbody>{"".join(body)}</tbody></table></div>')


def _services_table(services, tx):
    body = []
    for svc in services:
        name = tx.get("svc_" + str(svc.get("ime")), str(svc.get("ime") or ""))
        if svc.get("opravilo"):
            state = tx["running"] if svc.get("tece") else tx["periodic"]
            last = _ago(svc.get("zadnje_s"), tx)
            stops = tx["every_h"].format(n=max(1, int(round(float(svc.get("razmik_s") or 0) / 3600))))
        else:
            if svc.get("tece"):
                state = tx["running"]
            elif svc.get("vrsta") == "vedno":
                state = tx["off"]          # izklopil jo je uporabnik (Scit) ali ni nastavljena (Link brez naprav)
            else:
                state = tx["stopped"] if svc.get("ustavitev") else tx["not_started"]
            last = _ago(svc.get("zadnja_raba_s"), tx)
            if svc.get("vrsta") == "vedno" and svc.get("zadnja_raba_s") is None:
                last = "—"             # tece ves cas (Scit, Link): »se ne« bi zavajalo
            if svc.get("vrsta") == "vedno":
                why = tx.get("why_" + str(svc.get("razlog") or ""), "")
                stops = tx["always"].format(why=why) if why else "—"
            else:
                stops = tx["idle_stop"].format(n=max(1, int(round(float(svc.get("mirovanje_s") or 0) / 60))))
        klass = ' class="off"' if state in (tx["stopped"], tx["not_started"], tx["periodic"], tx["off"]) else ""
        body.append(f'<tr{klass}><td class="t">{html.escape(name)}</td><td>{html.escape(state)}</td>'
                    f'<td>{html.escape(last)}</td><td>{html.escape(stops)}</td></tr>')
    return (f'<h2>{tx["services"]}</h2><p class="rule">{html.escape(tx["services_rule"])}</p>{_scroll(tx["services"])}<table>'
            f'<thead><tr><th scope="col">{tx["service"]}</th><th scope="col">{tx["status"]}</th>'
            f'<th scope="col">{tx["last_use"]}</th><th scope="col">{tx["stops"]}</th></tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def render(rows, lang="sl", limit_mb=0, cpu_budget=0.0, key="", sleep_minutes=0, system=None, services=None,
           app="", sample_s=0, history_ready=True):
    """`rows`: list of dicts with id, title, cpu, rss_mb, threads, active, audio, sleeping, verdict and optionally
    pid (a process shared by two rows counts once in the total), app (embedded app: no actions), reasons
    (keys of REASONS: why the tab may not sleep now) and avg_cpu, peak_cpu, avg_mb, peak_mb (last hour).
    `key`: one-time key for the action links. `system`: every process of the program (core/poraba_zgodovina kinds,
    name, pid, threads, cpu, rss_mb and the last-hour values; tab: title of the tab it serves; service: on-demand
    service it belongs to; count: processes in a sandbox line). `services`: core/storitve_na_zahtevo.stanje() plus
    housekeeping jobs ({"ime", "opravilo": True, "razmik_s", "zadnje_s", "tece"}). `app`: program name."""
    tx = _TEXT.get(lang, _TEXT["en"])
    body = []
    total_cpu = 0.0
    total_mb = 0
    counted = set()
    for row in sorted(rows, key=lambda r: (-(r.get("cpu") or 0.0), -(r.get("rss_mb") or 0))):
        tab_id = str(row.get("id", ""))
        cpu = float(row.get("cpu") or 0.0)
        mb = int(row.get("rss_mb") or 0)
        pid = row.get("pid") or 0
        if not pid or pid not in counted:
            total_cpu += cpu
            total_mb += mb
            if pid:
                counted.add(pid)
        sleeping = bool(row.get("sleeping"))
        app_row = bool(row.get("app"))
        reasons = [r for r in REASONS if r in (row.get("reasons") or ())]
        states = []
        if app_row:
            states.append(tx["app"])
        if row.get("active"):
            states.append(tx["active"])
        if row.get("audio"):
            states.append(tx["audio"])
        if sleeping:
            states.append(tx["sleeping"])
        states += [tx[r] for r in reasons if not (r == "media" and row.get("audio"))]
        verdict = row.get("verdict")
        if verdict in ("hot", "hog"):
            states.append(tx[verdict])
        klass = " class=\"hot\"" if verdict in ("hot", "hog") else ""
        measured = bool(not sleeping and (pid or mb or cpu))
        cells = _usage_cells(dict(row, cpu=cpu, rss_mb=mb), lang, measured)
        threads = str(row.get("threads") or 0) if measured else tx["no_process"]
        actions = []
        if not app_row:
            if not sleeping and not row.get("active") and not row.get("audio") and not reasons:
                actions.append(f'<a href="{html.escape(_action("spi", tab_id, key))}">{tx["sleep"]}</a>')
            actions.append(f'<a href="{html.escape(_action("zapri", tab_id, key))}" class="close">{tx["close"]}</a>')
        body.append(
            f"<tr{klass}><td class=\"t\">{html.escape(str(row.get('title') or ''))}</td>"
            f"{cells}<td>{threads}</td>"
            f"<td>{html.escape(', '.join(states))}</td><td>{' · '.join(actions)}</td></tr>"
        )
    body.append(
        f"<tr class=\"total\"><td class=\"t\">{tx['total']}</td><td>{int(round(total_cpu * 100))} %</td><td></td><td></td>"
        f"<td>{_fmt_mb(total_mb, lang)}</td><td></td><td></td><td></td><td></td><td></td></tr>"
    )
    limit_line = tx["limit"].format(limit=limit_mb, cpu=int(round(cpu_budget * 100))) if limit_mb else ""
    rule = f"<p class=\"rule\">{html.escape(tx['rule'].format(min=int(sleep_minutes)))}</p>" if sleep_minutes > 0 else ""
    history = ""
    if sample_s:
        history = f"<p class=\"rule\">{html.escape(tx['history' if history_ready else 'history_wait'].format(s=int(sample_s)))}</p>"
    sections = ""
    if system:
        sections += _system_table(system, tx, lang, app)
    if services:
        sections += _services_table(services, tx)
    nonce = secrets.token_urlsafe(12)
    return f"""<!doctype html>
<html lang="{html.escape(lang)}"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-{nonce}'; form-action 'none'; frame-ancestors 'none'; base-uri 'none'">
<meta name="color-scheme" content="dark">
<title>Safeer · {tx['title']}</title>
<style>
{_tokens()}
  body {{ font-family: system-ui, sans-serif; background: var(--ozadje); color: var(--besedilo); margin: 0; padding: 32px; }}
  h1 {{ font-size: 22px; margin: 0 0 6px; }}
  h2 {{ font-size: 17px; margin: 30px 0 8px; }}
  p {{ color: var(--medlo); margin: 0 0 18px; max-width: 70ch; }}
  p.rule {{ color: var(--tise); font-size: 13px; }}
  .tabela {{ overflow-x: auto; max-width: 1180px; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--tanka); white-space: nowrap; }}
  td.t {{ white-space: normal; max-width: 40ch; overflow: hidden; text-overflow: ellipsis; }}
  td.h {{ color: var(--medlo); }}
  th {{ color: var(--medlo); font-weight: 600; font-size: 13px; }}
  th[scope="colgroup"] {{ text-align: center; border-bottom: 1px solid var(--rob); }}
  .pid {{ color: var(--tise); font-size: 12px; }}
  tr.hot td {{ color: var(--opozorilo); }}
  tr.off td {{ color: var(--tise); }}
  tr.total td {{ color: var(--medlo); font-weight: 600; border-top: 2px solid var(--rob); }}
  a {{ color: var(--zelena); text-decoration: none; border-radius: 4px; }} a.close {{ color: var(--rdeca); }}
  a:hover {{ text-decoration: underline; }}
  a:focus-visible, .tabela:focus-visible {{ outline: 2px solid var(--fokus); outline-offset: 2px; }}
  .limit {{ color: var(--tise); font-size: 12px; margin-top: 14px; }}
</style></head><body>
<h1>🛡️ Safeer · {tx['title']}</h1>
<p>{tx['intro']}</p>
{rule}
{history}
{_scroll(tx['title'])}<table>{_usage_head(tx, tx['tab'], (tx['threads'], tx['state'], tx['actions']))}
<tbody>{''.join(body)}</tbody></table></div>
<div class="limit">{html.escape(limit_line)}</div>
{sections}
<script nonce="{nonce}">
setInterval(function () {{
  var a = document.activeElement;
  if (document.hidden || (a && a !== document.body && a !== document.documentElement)) return;
  location.replace("{PAGE_URI}");
}}, {REFRESH_SECONDS * 1000});
</script>
</body></html>"""


def parse_action(uri):
    """Return ('spi'|'zapri', tab_id) for an action link, else (None, None)."""
    try:
        parsed = urllib.parse.urlparse(uri)
    except ValueError:
        return None, None
    if parsed.scheme != "safeer" or parsed.netloc != "procesi":
        return None, None
    query = urllib.parse.parse_qs(parsed.query)
    for key in ("spi", "zapri"):
        values = query.get(key)
        if values and values[0]:
            return key, values[0][:64]
    return None, None


def action_key(uri):
    """The one-time key (`k`) of an action link, or an empty string."""
    try:
        values = urllib.parse.parse_qs(urllib.parse.urlparse(uri).query).get("k")
    except ValueError:
        return ""
    return values[0][:64] if values else ""
