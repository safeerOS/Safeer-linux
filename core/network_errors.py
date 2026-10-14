"""Bounded recovery for interrupted search connections, with TLS validation intact."""
import html
import urllib.parse
from gi.repository import Gio, GLib, GObject
import gi

# Skupno za Safeer Browser GTK3 (WebKit2 4.1) in Splet / Safeer Browser GTK4 (WebKit 6.0) - 14. 10. 2026.
if gi.get_required_version("Gtk") == "4.0":
    gi.require_version('WebKit', '6.0')
    from gi.repository import WebKit as WebKit2
else:
    gi.require_version('WebKit2', '4.1')
    from gi.repository import WebKit2

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


def can_retry_search(uri, method, error, attempted):
    # Only idempotent search GETs, never forms, account callbacks or certificates.
    parsed = urllib.parse.urlsplit(uri)
    return (not attempted and method == 'GET' and parsed.scheme == 'https'
            and parsed.hostname in ('duckduckgo.com', 'www.duckduckgo.com', 'html.duckduckgo.com', 'lite.duckduckgo.com')
            and parsed.path in ('', '/', '/html/', '/lite/')
            and bool(urllib.parse.parse_qs(parsed.query).get('q'))
            and any(error.matches(Gio.tls_error_quark(), code)
                    for code in (Gio.TlsError.EOF, Gio.TlsError.HANDSHAKE, Gio.TlsError.NOT_TLS)))


def error_html(uri, method, certificate=False, jezik="sl"):
    jezik = (jezik or "sl")[:2] if (jezik or "sl")[:2] in BESEDILA else "en"
    t_cert, t_ni, m_cert, m_ni, t_znova, t_nazaj = BESEDILA[jezik]
    host = html.escape(urllib.parse.urlsplit(uri).hostname or '')
    target = html.escape(uri, quote=True)
    title = t_cert if certificate else t_ni
    message = m_cert if certificate else m_ni
    retry = f'<a href="{target}">{t_znova}</a>' if method == 'GET' and not certificate else ''
    return f'''<!doctype html><html lang="{jezik}"><meta name="viewport" content="width=device-width,initial-scale=1">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
    <title>{title} — Safeer</title><style>html{{color-scheme:dark}}body{{background:#0c1420;color:#eef4fa;font:18px system-ui;max-width:620px;margin:12vh auto;padding:28px;line-height:1.6}}h1{{font-size:28px}}p{{color:#bdcadd}}a{{display:inline-block;padding:12px 22px;background:#85cd3e;color:#102006;border-radius:10px;text-decoration:none;font-weight:600}}</style>
    <h1>{title}</h1><p>{host}</p><p>{message}</p>{retry}<p>{t_nazaj}</p></html>'''


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
        self.retried = set()
        self.error_document = False
        self.pending = None
        self.generation = 0
        view._safeer_load_failed = False
        # WebKitGTK 6.0 nima resource-load-started: glavna zahteva je tam vedno GET (gumb »Poskusi znova« = nov GET).
        if _ima_vire(view):
            view.connect('resource-load-started', self.resource_started)
        view.connect('load-changed', self.load_changed)
        view.connect('load-failed', self.load_failed)
        view.connect('load-failed-with-tls-errors', self.certificate_failed)
        view.connect('destroy', self.destroyed)

    def resource_started(self, view, resource, request):
        if resource == view.get_main_resource():
            self.requests = {request.get_uri(): request.get_http_method()}

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

    def show_error(self, uri, certificate=False):
        self.view._safeer_load_failed = True
        self.error_document = True
        jezik = self.jezik() if callable(self.jezik) else (self.jezik or "sl")
        self.view.load_alternate_html(error_html(uri, self.requests.get(uri, 'GET' if self._brez_virov() else None),
                                                 certificate, jezik), uri, None)

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
        metoda = self.requests.get(uri, 'GET' if self._brez_virov() else None)
        if can_retry_search(uri, metoda, error, uri in self.retried):
            self.retried.add(uri)
            generation = self.generation
            def retry():
                self.pending = None
                # A failed provisional navigation may restore the previous URI.
                # Guard against a newer navigation, rather than comparing that URI.
                if self.generation == generation:
                    view.load_uri(uri)
                return False
            self.pending = GLib.timeout_add(400, retry)
            return True
        certificate = error.matches(Gio.tls_error_quark(), Gio.TlsError.BAD_CERTIFICATE)
        self.show_error(uri, certificate)
        return True
