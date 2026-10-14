"""Zascita pred sledenjem v stopnjah (kot Firefox: obicajna, stroga, po meri) in izjeme po straneh.

Lastnik, 14. 10. 2026: »nasi brskalniki morajo nuditi vse moznosti kot najnovejsi Firefox; vrednote Firefoxa so nam
blizu«. Skupno Spletu (Safeer OS) in Safeer Browserju; nastavitve so v istem ConfigManager kot doslej, zato stare
nastavitve (adblock_enabled ...) ostanejo veljavne in stopnja se iz njih izracuna.
"""
from __future__ import annotations

import urllib.parse

#: Kar vsaka stopnja vklopi. Kljuci so obstojece nastavitve brskalnika (+ dve novi za strogo).
RAVNI = {
    "obicajna": {"adblock_enabled": True, "easylist_enabled": True, "adguard_protection_enabled": True,
                 "tracking_protection_enabled": True, "gpc_dnt_enabled": True,
                 "zascita_itp": False, "zascita_brez_webrtc": False},
    "stroga": {"adblock_enabled": True, "easylist_enabled": True, "adguard_protection_enabled": True,
               "tracking_protection_enabled": True, "gpc_dnt_enabled": True,
               "zascita_itp": True, "zascita_brez_webrtc": True},
}
PRIVZETO = RAVNI["obicajna"]
KLJUCI = tuple(PRIVZETO)


def nastavitve(config) -> dict:
    return {k: bool(config.get(k, PRIVZETO[k])) for k in KLJUCI}


def raven(config) -> str:
    """»obicajna«, »stroga« ali »po_meri« (uporabnik je posamezne nastavitve spremenil sam)."""
    zdaj = nastavitve(config)
    for ime, vrednosti in RAVNI.items():
        if zdaj == vrednosti:
            return ime
    return "po_meri"


def nastavi_raven(config, ime: str) -> None:
    for k, v in RAVNI.get(ime, PRIVZETO).items():
        if bool(config.get(k, PRIVZETO[k])) != v:
            config.set(k, v)


def gostitelj(uri: str) -> str:
    try:
        return (urllib.parse.urlsplit(uri or "").hostname or "").rstrip(".").lower()
    except ValueError:
        return ""


def izjeme(config) -> list:
    v = config.get("zascita_izjeme", []) or []
    return [str(x) for x in v if isinstance(x, str) and x][:500]


def je_izjema(config, uri: str) -> bool:
    """Stran, kjer je uporabnik izklopil blokiranje oglasov in sledilcev (gostitelj ali njegova poddomena)."""
    h = gostitelj(uri)
    return bool(h) and any(h == g or h.endswith("." + g) for g in izjeme(config))


def preklopi_izjemo(config, uri: str) -> bool:
    """Vklopi ali izklopi zascito za gostitelja strani. Vrne True, ce je zascita zdaj VKLOPLJENA."""
    h = gostitelj(uri)
    if not h:
        return True
    seznam = izjeme(config)
    if je_izjema(config, uri):
        seznam = [g for g in seznam if not (h == g or h.endswith("." + g))]
        config.set("zascita_izjeme", seznam)
        return True
    config.set("zascita_izjeme", (seznam + [h])[-500:])
    return False


def vzorci_izjem(config) -> list:
    """Vzorci za izlocitev uporabniskih skript (WebKit UserScript): *://gost/* in *://*.gost/*."""
    izid = []
    for g in izjeme(config):
        izid += ["*://%s/*" % g, "*://*.%s/*" % g]
    return izid


BESEDILA = {
    "sl": {"zas_naslov": "Zaščita pred sledenjem", "zas_obicajna": "Običajna",
           "zas_obicajna_opis": "Blokira oglase, sledilce, piškotke tretjih oseb in sledilne parametre. Strani delujejo kot običajno.",
           "zas_stroga": "Stroga",
           "zas_stroga_opis": "Še močnejša: WebKit omeji sledilne strani in stran ne izve tvojega lokalnega naslova IP (WebRTC). Videoklici v brskalniku in nekatere strani morda ne bodo delovali.",
           "zas_po_meri": "Po meri", "zas_oglasi": "Oglasi in sledilci", "zas_easylist": "Seznam EasyList",
           "zas_adguard": "Napredna zaščita AdGuard", "zas_parametri": "Odstrani sledilne parametre iz povezav",
           "zas_gpc": "Pošlji »Ne sledi« (GPC)", "zas_itp": "Pametna zaščita pred sledenjem (WebKit ITP)",
           "zas_webrtc": "Skrij lokalni naslov IP (izklopi WebRTC)",
           "zas_na_strani": "Zaščita na {stran}", "zas_vklopljena": "Vklopljena", "zas_izklopljena": "Izklopljena za to stran",
           "zas_blokirano": "Blokiranih oglasov in sledilcev: {n}", "zas_nastavitve": "Nastavitve zaščite …",
           "zas_ni_podatkov": "Safeer ne zbira podatkov o tebi: brez telemetrije, brez računa, brez oglasnega profila."},
    "en": {"zas_naslov": "Tracking protection", "zas_obicajna": "Standard",
           "zas_obicajna_opis": "Blocks ads, trackers, third-party cookies and tracking parameters. Pages work as usual.",
           "zas_stroga": "Strict",
           "zas_stroga_opis": "Stronger: WebKit limits tracking sites and pages can't learn your local IP address (WebRTC). Video calls in the browser and some pages may not work.",
           "zas_po_meri": "Custom", "zas_oglasi": "Ads and trackers", "zas_easylist": "EasyList",
           "zas_adguard": "AdGuard advanced protection", "zas_parametri": "Remove tracking parameters from links",
           "zas_gpc": "Send “Do Not Track” (GPC)", "zas_itp": "Intelligent tracking prevention (WebKit ITP)",
           "zas_webrtc": "Hide local IP address (turn off WebRTC)",
           "zas_na_strani": "Protection on {stran}", "zas_vklopljena": "On", "zas_izklopljena": "Off for this site",
           "zas_blokirano": "Blocked ads and trackers: {n}", "zas_nastavitve": "Protection settings …",
           "zas_ni_podatkov": "Safeer collects no data about you: no telemetry, no account, no ad profile."},
    "de": {"zas_naslov": "Schutz vor Aktivitätenverfolgung", "zas_obicajna": "Standard",
           "zas_obicajna_opis": "Blockiert Werbung, Tracker, Drittanbieter-Cookies und Tracking-Parameter. Seiten funktionieren wie gewohnt.",
           "zas_stroga": "Streng",
           "zas_stroga_opis": "Stärker: WebKit schränkt Tracking-Seiten ein und Seiten erfahren deine lokale IP-Adresse nicht (WebRTC). Videoanrufe im Browser und manche Seiten funktionieren eventuell nicht.",
           "zas_po_meri": "Benutzerdefiniert", "zas_oglasi": "Werbung und Tracker", "zas_easylist": "EasyList",
           "zas_adguard": "Erweiterter AdGuard-Schutz", "zas_parametri": "Tracking-Parameter aus Links entfernen",
           "zas_gpc": "„Nicht verfolgen“ senden (GPC)", "zas_itp": "Intelligenter Tracking-Schutz (WebKit ITP)",
           "zas_webrtc": "Lokale IP-Adresse verbergen (WebRTC aus)",
           "zas_na_strani": "Schutz auf {stran}", "zas_vklopljena": "An", "zas_izklopljena": "Aus für diese Seite",
           "zas_blokirano": "Blockierte Werbung und Tracker: {n}", "zas_nastavitve": "Schutzeinstellungen …",
           "zas_ni_podatkov": "Safeer sammelt keine Daten über dich: keine Telemetrie, kein Konto, kein Werbeprofil."},
    "es": {"zas_naslov": "Protección contra rastreo", "zas_obicajna": "Estándar",
           "zas_obicajna_opis": "Bloquea anuncios, rastreadores, cookies de terceros y parámetros de rastreo. Las páginas funcionan como siempre.",
           "zas_stroga": "Estricta",
           "zas_stroga_opis": "Más fuerte: WebKit limita los sitios de rastreo y las páginas no conocen tu IP local (WebRTC). Las videollamadas en el navegador y algunas páginas pueden no funcionar.",
           "zas_po_meri": "Personalizada", "zas_oglasi": "Anuncios y rastreadores", "zas_easylist": "EasyList",
           "zas_adguard": "Protección avanzada de AdGuard", "zas_parametri": "Quitar parámetros de rastreo de los enlaces",
           "zas_gpc": "Enviar «No rastrear» (GPC)", "zas_itp": "Prevención inteligente de rastreo (WebKit ITP)",
           "zas_webrtc": "Ocultar la IP local (desactivar WebRTC)",
           "zas_na_strani": "Protección en {stran}", "zas_vklopljena": "Activada", "zas_izklopljena": "Desactivada en este sitio",
           "zas_blokirano": "Anuncios y rastreadores bloqueados: {n}", "zas_nastavitve": "Ajustes de protección …",
           "zas_ni_podatkov": "Safeer no recoge datos sobre ti: sin telemetría, sin cuenta, sin perfil publicitario."},
    "fr": {"zas_naslov": "Protection contre le pistage", "zas_obicajna": "Standard",
           "zas_obicajna_opis": "Bloque publicités, traqueurs, cookies tiers et paramètres de pistage. Les pages fonctionnent normalement.",
           "zas_stroga": "Stricte",
           "zas_stroga_opis": "Plus forte : WebKit limite les sites de pistage et les pages ne connaissent pas votre IP locale (WebRTC). Les appels vidéo dans le navigateur et certaines pages peuvent ne pas fonctionner.",
           "zas_po_meri": "Personnalisée", "zas_oglasi": "Publicités et traqueurs", "zas_easylist": "EasyList",
           "zas_adguard": "Protection avancée AdGuard", "zas_parametri": "Retirer les paramètres de pistage des liens",
           "zas_gpc": "Envoyer « Ne pas me pister » (GPC)", "zas_itp": "Prévention intelligente du pistage (WebKit ITP)",
           "zas_webrtc": "Masquer l’IP locale (désactiver WebRTC)",
           "zas_na_strani": "Protection sur {stran}", "zas_vklopljena": "Activée", "zas_izklopljena": "Désactivée pour ce site",
           "zas_blokirano": "Publicités et traqueurs bloqués : {n}", "zas_nastavitve": "Réglages de protection …",
           "zas_ni_podatkov": "Safeer ne collecte aucune donnée sur vous : pas de télémétrie, pas de compte, pas de profil publicitaire."},
    "it": {"zas_naslov": "Protezione antitracciamento", "zas_obicajna": "Normale",
           "zas_obicajna_opis": "Blocca pubblicità, tracker, cookie di terze parti e parametri di tracciamento. Le pagine funzionano come sempre.",
           "zas_stroga": "Restrittiva",
           "zas_stroga_opis": "Più forte: WebKit limita i siti traccianti e le pagine non conoscono il tuo IP locale (WebRTC). Videochiamate nel browser e alcune pagine potrebbero non funzionare.",
           "zas_po_meri": "Personalizzata", "zas_oglasi": "Pubblicità e tracker", "zas_easylist": "EasyList",
           "zas_adguard": "Protezione avanzata AdGuard", "zas_parametri": "Rimuovi i parametri di tracciamento dai link",
           "zas_gpc": "Invia «Non tracciare» (GPC)", "zas_itp": "Prevenzione intelligente del tracciamento (WebKit ITP)",
           "zas_webrtc": "Nascondi l’IP locale (disattiva WebRTC)",
           "zas_na_strani": "Protezione su {stran}", "zas_vklopljena": "Attiva", "zas_izklopljena": "Disattivata per questo sito",
           "zas_blokirano": "Pubblicità e tracker bloccati: {n}", "zas_nastavitve": "Impostazioni di protezione …",
           "zas_ni_podatkov": "Safeer non raccoglie dati su di te: nessuna telemetria, nessun account, nessun profilo pubblicitario."},
}
