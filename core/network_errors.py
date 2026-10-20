"""Bounded recovery for interrupted search connections, with TLS validation intact."""
import html
import urllib.parse
from gi.repository import Gio, GLib, GObject
import gi

# Splet in Safeer Browser: GTK4 in WebKit 6.0 (GTK3 umaknjen 18. 10. 2026). WebKit2 4.1 samo, ce je proces ze izbral
# GTK 3. Prej je bil WebKit2 4.1 privzet, ce Gtk se ni bil izbran: samostojni uvoz (tests/test_network_errors.py v svojem
# procesu) je padel z »Namespace WebKit2 not available«, ker CI namesti samo gir1.2-webkit-6.0 (19. 10. 2026).
if gi.get_required_version("Gtk") == "3.0":
    gi.require_version('WebKit2', '4.1')
    from gi.repository import WebKit2
else:
    gi.require_version('WebKit', '6.0')
    from gi.repository import WebKit as WebKit2

BESEDILA = {
    "sl": ("Varne povezave ni mogoče potrditi", "Strani trenutno ni mogoče odpreti",
           "Spletno mesto je poslalo neveljavno potrdilo. Povezava je ostala blokirana.",
           "Povezava s spletnim mestom se je prekinila. Preverite povezavo in poskusite znova.",
           "Poskusi znova", "Za vrnitev uporabite gumb Nazaj ali Domov v brskalniku."),
    "en": ("The secure connection could not be verified", "This page can't be opened right now",
           "The website sent an invalid certificate. The connection stayed blocked.",
           "The connection to the website was interrupted. Check your connection and try again.",
           "Try again", "Use the Back or Home button in the browser to go back."),
    "de": ("Die sichere Verbindung konnte nicht bestätigt werden", "Die Seite kann gerade nicht geöffnet werden",
           "Die Website hat ein ungültiges Zertifikat gesendet. Die Verbindung bleibt blockiert.",
           "Die Verbindung zur Website wurde unterbrochen. Prüfe die Verbindung und versuche es erneut.",
           "Erneut versuchen", "Mit Zurück oder Startseite im Browser kommst du zurück."),
    "es": ("No se pudo verificar la conexión segura", "Ahora no se puede abrir la página",
           "El sitio envió un certificado no válido. La conexión sigue bloqueada.",
           "Se interrumpió la conexión con el sitio. Comprueba la conexión e inténtalo de nuevo.",
           "Reintentar", "Usa Atrás o Inicio en el navegador para volver."),
    "fr": ("La connexion sécurisée n’a pas pu être vérifiée", "Impossible d’ouvrir la page pour le moment",
           "Le site a envoyé un certificat non valide. La connexion reste bloquée.",
           "La connexion au site a été interrompue. Vérifiez la connexion et réessayez.",
           "Réessayer", "Utilisez Retour ou Accueil dans le navigateur pour revenir."),
    "it": ("Impossibile verificare la connessione sicura", "Al momento la pagina non si può aprire",
           "Il sito ha inviato un certificato non valido. La connessione resta bloccata.",
           "La connessione al sito si è interrotta. Controlla la connessione e riprova.",
           "Riprova", "Usa Indietro o Home nel browser per tornare."),
}


#: Prehodne napake povezave (lastnik, 20. 10. 2026: Google iskanje v Spletu je enkrat pokazalo »Strani trenutno ni
#: mogoce odpreti«, ponovni poskus je delal - prej se je samodejno ponovilo samo iskanje DuckDuckGo). Brez napak
#: potrdil: te nikoli ne ponavljamo.
PREHODNE_TLS = ("EOF", "HANDSHAKE", "NOT_TLS")
PREHODNE_IO = ("CONNECTION_CLOSED", "BROKEN_PIPE", "PARTIAL_INPUT", "TIMED_OUT", "CONNECTION_REFUSED",
               "HOST_UNREACHABLE", "NETWORK_UNREACHABLE", "PROXY_FAILED", "NOT_CONNECTED")
#: Notranja napaka WebKita (WebCore::internalError): domena in koda, kot ju WebKitGTK 2.54 da v load-failed.
DOMENA_NOTRANJE, KODA_NOTRANJE = "WebKitErrorDomain", 300
#: Zamiki samodejnih ponovitev (s): DoH posrednik ali Scit po kratkem izpadu (omrezje, prebujenje) potrebuje do ~1 s.
ZAMIKI_PONOVITVE = (0.4, 1.5)


def je_prehodna(error) -> bool:
    """Napaka povezave, ki jo ponovni poskus lahko odpravi (prekinjena povezava, posrednik, rok)."""
    for imena, domena, enum in ((PREHODNE_TLS, Gio.tls_error_quark(), Gio.TlsError),
                                (PREHODNE_IO, Gio.io_error_quark(), Gio.IOErrorEnum)):
        for ime in imena:
            koda = getattr(enum, ime, None)
            if koda is not None and error.matches(domena, koda):
                return True
    if error.matches(Gio.resolver_error_quark(), Gio.ResolverError.TEMPORARY_FAILURE):
        return True
    # »WebKit encountered an internal error« (WebLoaderStrategy::internallyFailedLoadTimerFired): spletni proces
    # zahteve ni mogel predati omreznemu procesu, ker se je ta ravno koncal - zahteva ni sla nikamor, ponovitev gre
    # novemu omreznemu procesu (izmerjeno 20. 10. 2026 na prenosniku lastnika: Google iz lupe -> ta napaka, takoj
    # zatem stran dela).
    if error.matches(GLib.quark_from_string(DOMENA_NOTRANJE), KODA_NOTRANJE):
        return True
    return error.matches(WebKit2.network_error_quark(), WebKit2.NetworkError.TRANSPORT)


def can_retry_search(uri, method, error, attempted):
    """Samodejna ponovitev glavne navigacije: samo GET (nikoli obrazci), http(s), prehodna napaka povezave in
    najvec len(ZAMIKI_PONOVITVE)-krat za isti naslov. Ponovitev je nov GET istega naslova - zahteva ni prispela do
    strani ali odgovor ni prisel, zato je za GET varna."""
    if isinstance(attempted, bool):
        attempted = 1 if attempted else 0
    parsed = urllib.parse.urlsplit(uri)
    return (attempted < len(ZAMIKI_PONOVITVE) and method == 'GET' and parsed.scheme in ('https', 'http')
            and bool(parsed.hostname) and je_prehodna(error))


def opis_napake(error) -> str:
    """Kratka tehnicna oznaka napake za stran in dnevnik (brez naslova strani)."""
    try:
        return "%s %d" % (GLib.quark_to_string(error.domain) if isinstance(error.domain, int) else error.domain,
                          error.code)
    except Exception:  # noqa: BLE001
        return ""


def error_html(uri, method, certificate=False, jezik="sl", koda=""):
    jezik = (jezik or "sl")[:2] if (jezik or "sl")[:2] in BESEDILA else "en"
    t_cert, t_ni, m_cert, m_ni, t_znova, t_nazaj = BESEDILA[jezik]
    host = html.escape(urllib.parse.urlsplit(uri).hostname or '')
    target = html.escape(uri, quote=True)
    title = t_cert if certificate else t_ni
    message = m_cert if certificate else m_ni
    retry = f'<a href="{target}">{t_znova}</a>' if method == 'GET' and not certificate else ''
    oznaka = f'<p class="k">{html.escape(koda)}</p>' if koda else ''
    return f'''<!doctype html><html lang="{jezik}"><meta name="viewport" content="width=device-width,initial-scale=1">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
    <title>{title} — Safeer</title><style>html{{color-scheme:dark}}body{{background:#0c1420;color:#eef4fa;font:18px system-ui;max-width:620px;margin:12vh auto;padding:28px;line-height:1.6}}h1{{font-size:28px}}p{{color:#bdcadd}}a{{display:inline-block;padding:12px 22px;background:#85cd3e;color:#102006;border-radius:10px;text-decoration:none;font-weight:600}}.k{{font-size:13px;color:#7f8ea3}}</style>
    <h1>{title}</h1><p>{host}</p><p>{message}</p>{retry}<p>{t_nazaj}</p>{oznaka}</html>'''


def _ima_vire(view):
    """WebKit2 4.1 javi glavno zahtevo (in njeno metodo); WebKitGTK 6.0 ne. Lazni pogled v preizkusih: kot 4.1."""
    if not isinstance(view, GObject.Object):
        return True
    try:
        return bool(GObject.signal_lookup('resource-load-started', type(view)))
    except (TypeError, AttributeError):
        # Starejsi PyGObject (Ubuntu 22.04) za tip brez GType vrze AttributeError, novejsi TypeError (CI 14. 10. 2026).
        return True


class NetworkErrorHandler:
    def __init__(self, view, jezik=None):
        self.view = view
        self.jezik = jezik          # klicljivo ali niz; Splet: jezik vmesnika
        self.requests = {}
        self.retried = {}           # naslov -> stevilo samodejnih ponovitev
        self.error_document = False
        self.pending = None
        self.generation = 0
        view._safeer_load_failed = False
        # WebKitGTK 6.0 nima resource-load-started: glavna zahteva je tam vedno GET (gumb »Poskusi znova« = nov GET).
        if _ima_vire(view):
            view.connect('resource-load-started', self.resource_started)
        else:
            # 6.0: metodo glavne navigacije izvemo iz odlocitve (POST obrazca se ne sme ponoviti kot GET).
            view.connect('decide-policy', self.decide_policy)
        view.connect('load-changed', self.load_changed)
        view.connect('load-failed', self.load_failed)
        view.connect('load-failed-with-tls-errors', self.certificate_failed)
        view.connect('destroy', self.destroyed)

    def resource_started(self, view, resource, request):
        if resource == view.get_main_resource():
            self.requests = {request.get_uri(): request.get_http_method()}

    def decide_policy(self, view, decision, kind):
        try:
            if kind == WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
                zahteva = decision.get_navigation_action().get_request()
                self.requests = {zahteva.get_uri(): zahteva.get_http_method() or 'GET'}
        except Exception:  # noqa: BLE001
            pass
        return False

    def load_changed(self, view, event):
        if event == WebKit2.LoadEvent.STARTED:
            self.generation += 1
        if event == WebKit2.LoadEvent.COMMITTED:
            if self.error_document:
                self.error_document = False
            else:
                view._safeer_load_failed = False
                self.retried.clear()

    def destroyed(self, *args):
        self.cancel_pending()

    def cancel_pending(self):
        self.generation += 1
        if self.pending:
            GLib.source_remove(self.pending)
            self.pending = None

    def _metoda(self, uri):
        """Metoda glavne zahteve (resource-load-started ali, kjer ga ni, decide-policy). Naslov napake je lahko ze
        preusmerjen (Google iskanje 302): preusmerjen GET ostane GET, POST ne velja za GET. Brez podatka v WebKitu
        brez resource-load-started GET kot prej."""
        if uri in self.requests:
            return self.requests[uri]
        if self.requests:
            return 'GET' if list(self.requests.values()) == ['GET'] else None
        return 'GET' if self._brez_virov() else None

    def show_error(self, uri, certificate=False, koda=""):
        self.view._safeer_load_failed = True
        self.error_document = True
        jezik = self.jezik() if callable(self.jezik) else (self.jezik or "sl")
        self.view.load_alternate_html(error_html(uri, self._metoda(uri), certificate, jezik, koda), uri, None)

    def _brez_virov(self):
        return not _ima_vire(self.view)

    def certificate_failed(self, view, uri, certificate, flags):
        self.show_error(uri, True)
        return True

    def load_failed(self, view, event, uri, error):
        if getattr(view, "_safeer_crashed", False):
            return True
        if error.matches(WebKit2.network_error_quark(), WebKit2.NetworkError.CANCELLED):
            return False
        if error.matches(WebKit2.policy_error_quark(), WebKit2.PolicyError.FRAME_LOAD_INTERRUPTED_BY_POLICY_CHANGE):
            return False
        metoda = self._metoda(uri)
        poskusov = self.retried.get(uri, 0)
        koda = opis_napake(error)
        # Dnevnik (sled.log): samo ime gostitelja, brez poti in poizvedbe (zasebnost).
        print("[Splet] napaka nalaganja %s: %s (%s), ponovitev %d" % (urllib.parse.urlsplit(uri).hostname or "?", koda,
              getattr(error, "message", ""), poskusov), flush=True)
        if can_retry_search(uri, metoda, error, poskusov):
            self.retried[uri] = poskusov + 1
            generation = self.generation
            def retry():
                self.pending = None
                # A failed provisional navigation may restore the previous URI.
                # Guard against a newer navigation, rather than comparing that URI.
                if self.generation == generation:
                    view.load_uri(uri)
                return False
            self.pending = GLib.timeout_add(int(ZAMIKI_PONOVITVE[poskusov] * 1000), retry)
            return True
        certificate = error.matches(Gio.tls_error_quark(), Gio.TlsError.BAD_CERTIFICATE)
        self.show_error(uri, certificate, koda)
        return True
