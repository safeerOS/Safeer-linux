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
import urllib.parse
from pathlib import Path

from core import adblock, odlozisce_varuh, ozadje_strani
from core.config import ConfigManager, SEARCH_ENGINES, normalize_web_url
from core.doh_proxy import get_doh_proxy
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


#: Ozadje pogleda pod našimi stranmi (pod spletnimi je belo, glej core/ozadje_strani.py).
TEMNO_OZADJE = "#0a141c"


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
        return zazeni([bwrap, "--unshare-all", "--ro-bind", "/", "/", "true"], stdin=subprocess.DEVNULL,
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8).returncode == 0
    except Exception:
        return False


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
    if dejanje in ("increment_ads", "increment_threats"):
        try:
            stevilo = max(0, min(int(vrednost.get("count", 1)), 100))
        except (TypeError, ValueError):
            return None
        return {"action": dejanje, "count": stevilo}
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


class VdelaniSplet:
    """GTK gradnik z zavihki; namenoma ni okno in zato ne more zapustiti Safeer OS."""

    def __init__(self, Gtk, Gdk, Gio, GLib, WebKit2, koren: str, jezik, stanje_povezave,
                 odpri_zapisek=None, stars=None):
        self.Gtk, self.Gdk, self.Gio, self.GLib, self.WebKit2 = Gtk, Gdk, Gio, GLib, WebKit2
        self.koren, self.jezik = koren, jezik
        self.stanje_povezave, self.odpri_zapisek = stanje_povezave, odpri_zapisek
        self.stars = stars
        self.config = ConfigManager()
        self.zavihki, self.aktivni, self._stevec = [], None, 0
        self.filter, self.filter_store, self.filter_agent = None, None, None
        self.prenosi = []
        self._threat_service = None
        self._ustvari_kontekst()
        self._zgradi()
        self._zazeni_zascito()
        self.nov_zavihek()
        self.GLib.timeout_add_seconds(5, self.osvezi_povezavo)

    def _t(self, kljuc: str, **vrednosti) -> str:
        niz = besedila(self.jezik()).get(kljuc, kljuc)
        return niz.format(**vrednosti) if vrednosti else niz

    def _ustvari_kontekst(self) -> None:
        WebKit2 = self.WebKit2
        mapa = os.path.join(self.config.config_dir, "web-data")
        os.makedirs(mapa, exist_ok=True)
        try:
            upravitelj = WebKit2.WebsiteDataManager(
                base_data_directory=mapa, base_cache_directory=os.path.join(mapa, "cache"),
                disk_cache_directory=os.path.join(mapa, "cache"),
                indexeddb_directory=os.path.join(mapa, "indexeddb"),
                local_storage_directory=os.path.join(mapa, "localstorage"),
                websql_directory=os.path.join(mapa, "websql"))
            self.kontekst = WebKit2.WebContext.new_with_website_data_manager(upravitelj)
            self.kontekst.set_sandbox_enabled(True)
            piskotki = upravitelj.get_cookie_manager()
            piskotki.set_persistent_storage(os.path.join(self.config.config_dir, "cookies.sqlite"),
                                            WebKit2.CookiePersistentStorage.SQLITE)
            piskotki.set_accept_policy(WebKit2.CookieAcceptPolicy.NO_THIRD_PARTY)
        except Exception as napaka:
            print("[Safeer OS Splet] shramba:", napaka)
            self.kontekst = WebKit2.WebContext.get_default()
            self.kontekst.set_sandbox_enabled(True)
        try:
            self.kontekst.set_cache_model(WebKit2.CacheModel.WEB_BROWSER)
        except Exception:
            pass
        self._nastavi_omrezje()
        self.kontekst.connect("download-started", self._prenos_zacet)

    def _nastavi_omrezje(self) -> None:
        W = self.WebKit2
        izjeme = ["localhost", "127.0.0.0/8", "::1", "10.0.0.0/8", "192.168.0.0/16", "172.16.0.0/12", ".local"]
        try:
            nacin = self.config.get("secure_proxy_mode", "disabled")
            if nacin == "custom" and self.config.get("secure_proxy_url", "").strip():
                p = W.NetworkProxySettings.new(self.config.get("secure_proxy_url").strip(), izjeme)
                self.kontekst.set_network_proxy_settings(W.NetworkProxyMode.CUSTOM, p)
                return
            if self.config.get("doh_enabled", True) and self.config.get("doh_provider", "cloudflare") != "disabled":
                doh = get_doh_proxy(provider=self.config.get("doh_provider", "cloudflare"),
                                    custom_url=self.config.get("custom_doh_url", "https://1.1.1.1/dns-query"), enabled=True)
                if doh and doh.actual_port > 0:
                    p = W.NetworkProxySettings.new("http://127.0.0.1:%d" % doh.actual_port, izjeme)
                    self.kontekst.set_network_proxy_settings(W.NetworkProxyMode.CUSTOM, p)
                    return
            self.kontekst.set_network_proxy_settings(W.NetworkProxyMode.DEFAULT, None)
        except Exception as napaka:
            print("[Safeer OS Splet] DoH/proxy:", napaka)

    def _zgradi(self) -> None:
        Gtk = self.Gtk
        self.gradnik = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.gradnik.set_name("safeer-splet")
        self.vrstica_zavihkov = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.vrstica_zavihkov.set_name("splet-zavihki")
        self.skatla_zavihkov = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.vrstica_zavihkov.pack_start(self.skatla_zavihkov, False, False, 10)
        self.nov_gumb = self._gumb("+", lambda *_: self.nov_zavihek(), "new-tab")
        self.vrstica_zavihkov.pack_start(self.nov_gumb, False, False, 0)
        self.povezava = Gtk.Label(label="")
        self.povezava.set_name("splet-povezava")
        self.vrstica_zavihkov.pack_end(self.povezava, False, False, 18)
        self.gradnik.pack_start(self.vrstica_zavihkov, False, False, 0)

        orodja = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        orodja.set_name("splet-orodja")
        self.nazaj = self._gumb("←", lambda *_: self.trenutni() and self.trenutni().go_back(), "nav")
        self.naprej = self._gumb("→", lambda *_: self.trenutni() and self.trenutni().go_forward(), "nav")
        self.osvezi = self._gumb("↻", lambda *_: self.trenutni() and self.trenutni().reload(), "nav")
        self.domov = self._gumb("⌂", lambda *_: self.odpri_domov(), "nav")
        for g, namig in ((self.nazaj, "nazaj"), (self.naprej, "naprej"), (self.osvezi, "osvezi"), (self.domov, "domov")):
            g.set_tooltip_text(self._t(namig)); orodja.pack_start(g, False, False, 0)
        naslov = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        naslov.set_name("splet-naslov")
        self.kljucavnica = (Gtk.Image.new_from_icon_name("channel-secure-symbolic", Gtk.IconSize.MENU)
                            if Gtk.IconTheme.get_default().has_icon("channel-secure-symbolic") else Gtk.Label(label="🔒"))
        self.vnos = Gtk.Entry()
        self.vnos.set_name("splet-vnos")
        self.vnos.set_placeholder_text(self._t("naslov"))
        self.vnos.connect("activate", self._vnesi_naslov)
        self.zvezdica = self._gumb("☆", lambda *_: self.dodaj_trenutno(), "address-action")
        naslov.pack_start(self.kljucavnica, False, False, 8)
        naslov.pack_start(self.vnos, True, True, 0)
        naslov.pack_end(self.zvezdica, False, False, 5)
        orodja.pack_start(naslov, True, True, 4)
        self.scit = self._gumb("♢", lambda *_: None, "nav")
        self.scit.set_tooltip_text(self._t("scit"))
        orodja.pack_start(self.scit, False, False, 0)
        meni = Gtk.MenuButton()
        meni.set_image(Gtk.Image.new_from_icon_name("open-menu-symbolic", Gtk.IconSize.LARGE_TOOLBAR))
        meni.set_name("splet-meni")
        meni.set_tooltip_text(self._t("meni"))
        meni.set_popup(self._meni())
        orodja.pack_end(meni, False, False, 0)
        self.gradnik.pack_start(orodja, False, False, 0)

        self.najdi_vrstica = Gtk.SearchBar()
        self.najdi_vnos = Gtk.SearchEntry()
        self.najdi_vnos.set_placeholder_text(self._t("isci"))
        self.najdi_vnos.connect("search-changed", self._najdi)
        self.najdi_vrstica.add(self.najdi_vnos)
        self.gradnik.pack_start(self.najdi_vrstica, False, False, 0)
        self.sklad = Gtk.Stack()
        self.sklad.set_transition_type(Gtk.StackTransitionType.NONE)
        self.gradnik.pack_start(self.sklad, True, True, 0)
        self._css()
        self.osvezi_povezavo()

    def _css(self) -> None:
        css = b"""
        #safeer-splet { background: #0a141c; color: #f2f7f5; }
        #splet-zavihki { background: #0a141c; min-height: 52px; }
        .splet-tab { background: #0d1a23; color: #c5d3cf; border: 1px solid rgba(181,220,209,.12);
          border-bottom: 0; border-radius: 12px 12px 0 0; padding: 8px 12px; margin-top: 8px; min-width: 180px; }
        .splet-tab-aktiven { background: #13252f; color: #f2f7f5; border-color: rgba(87,214,173,.55);
          border-top: 2px solid #57D6AD; }
        .splet-tab button, .new-tab, .nav, .address-action, #splet-meni { background: transparent; color: #f2f7f5;
          border: 0; box-shadow: none; text-shadow: none; }
        .new-tab { font-size: 24px; padding: 5px 10px; }
        #splet-povezava { color: #e5efec; border: 1px solid rgba(87,214,173,.55); border-radius: 14px;
          padding: 5px 14px; margin-top: 8px; margin-bottom: 8px; background: rgba(87,214,173,.08); }
        #splet-orodja { background: #0a141c; padding: 6px 14px 8px; }
        .nav { font-size: 20px; padding: 6px 9px; border-radius: 10px; color: #e2e8f0; }
        .nav image, .address-action image, #splet-meni image { color: #e2e8f0; }
        .nav:hover, .address-action:hover, #splet-meni:hover { background: #162731; }
        #splet-naslov { background: #0c1820; border: 2px solid rgba(87,214,173,.55); border-radius: 20px; padding: 2px 6px; }
        #splet-vnos { background: transparent; color: #f2f7f5; border: 0; box-shadow: none; font-size: 16px; padding: 10px 4px; }
        #splet-vnos selection { background: #287b67; }
        menu { background: #13222b; color: #f2f7f5; border: 1px solid #32444d; }
        menuitem:hover { background: #26404a; }
        """
        ponudnik = self.Gtk.CssProvider()
        ponudnik.load_from_data(css)
        self.Gtk.StyleContext.add_provider_for_screen(self.Gdk.Screen.get_default(), ponudnik,
                                                       self.Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._css_ponudnik = ponudnik

    def _gumb(self, napis, dejanje, razred):
        # Sistemske simbolne ikone (enake oblike kot na Windows), sicer besedilo.
        ikone = {"←": "go-previous-symbolic", "→": "go-next-symbolic", "↻": "view-refresh-symbolic",
                 "⌂": "go-home-symbolic", "☆": "non-starred-symbolic", "♢": "security-high-symbolic",
                 "+": "list-add-symbolic"}
        if napis in ikone and self.Gtk.IconTheme.get_default().has_icon(ikone[napis]):
            g = self.Gtk.Button()
            g.set_image(self.Gtk.Image.new_from_icon_name(ikone[napis], self.Gtk.IconSize.LARGE_TOOLBAR))
            g.set_always_show_image(True)
        else:
            g = self.Gtk.Button(label=napis)
        g.set_relief(self.Gtk.ReliefStyle.NONE)
        g.get_style_context().add_class(razred)
        g.connect("clicked", dejanje)
        return g

    def _meni(self):
        meni = self.Gtk.Menu()
        vnosi = [
            (self._t("nov"), lambda *_: self.nov_zavihek()),
            (self._t("prenosi"), self._pokazi_prenose),
            (self._t("najdi"), lambda *_: self._pokazi_najdi()),
            (self._t("povecaj"), lambda *_: self._povecava(.1)),
            (self._t("pomanjsaj"), lambda *_: self._povecava(-.1)),
            (self._t("nastavitve"), self._nastavitve),
            (self._t("zapisek"), self._v_zapisek),
        ]
        for napis, dejanje in vnosi:
            v = self.Gtk.MenuItem(label=napis); v.connect("activate", dejanje); meni.append(v)
        meni.show_all()
        return meni

    def _zazeni_zascito(self) -> None:
        try:
            from core.threat_intel import ThreatIntelService, default_data_dir
            self._threat_service = ThreatIntelService(default_data_dir("safeer-mint"))
            adblock.register_threat_matcher(self._threat_service.match)
            self._threat_service.start()
        except Exception as napaka:
            print("[Safeer OS Splet] vir grozenj:", napaka)
        if not self.config.get("easylist_enabled", True):
            return
        try:
            from core.filter_lists import FilterListAgent
            from core.threat_intel import default_data_dir
            mapa = default_data_dir("safeer-mint").parent / "filter-lists"
            self._filter_mapa = mapa / "compiled"
            self.filter_agent = FilterListAgent(mapa, on_rules=lambda p, v: self.GLib.idle_add(self._namesti_filter, p, v),
                                                 never_block_domains=adblock.real_bank_domains())
            self.filter_agent.start()
        except Exception as napaka:
            print("[Safeer OS Splet] EasyList:", napaka)

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
            for z in self.zavihki:
                self._uporabi_filter(z["pogled"])
        except Exception as napaka:
            print("[Safeer OS Splet] prevajanje filtra:", napaka)

    def _uporabi_filter(self, pogled):
        if self.filter is not None:
            try:
                pogled.get_user_content_manager().remove_filter_by_id(FILTER_ID)
                pogled.get_user_content_manager().add_filter(self.filter)
            except Exception:
                pass

    def _skripta(self, upravitelj, koda, cas=None, dovoljeni=None, izloceni=None):
        if not koda:
            return
        upravitelj.add_script(self.WebKit2.UserScript(
            koda, self.WebKit2.UserContentInjectedFrames.ALL_FRAMES,
            cas or self.WebKit2.UserScriptInjectionTime.START, dovoljeni, izloceni))

    def _nov_pogled(self):
        W = self.WebKit2
        pogled = W.WebView.new_with_context(self.kontekst)
        upravitelj = pogled.get_user_content_manager()
        upravitelj.register_script_message_handler("safeer")
        upravitelj.connect("script-message-received::safeer", lambda _u, r: self._sporocilo(pogled, r))
        odlozisce_varuh.dodaj(W, upravitelj)   # tudi na prijavnih straneh: nicesar ne spreminja, le varuje odlozisce
        izvzemi = adblock.AUTH_SCRIPT_EXCLUSIONS
        if self.config.get("gpc_dnt_enabled", True): self._skripta(upravitelj, adblock.GPC_AND_DNT_SCRIPT, izloceni=izvzemi)
        self._skripta(upravitelj, adblock.YOUTUBE_ADBLOCK_SCRIPT, dovoljeni=["*://*.youtube.com/*", "*://youtube.com/*"], izloceni=izvzemi)
        self._skripta(upravitelj, adblock.YOUTUBE_KEEP_WATCHING_SCRIPT, dovoljeni=["*://*.youtube.com/*", "*://youtube.com/*"], izloceni=izvzemi)
        if self.config.get("adguard_protection_enabled", True): self._skripta(upravitelj, adblock.ADGUARD_PROTECTION_SCRIPT, izloceni=izvzemi)
        self._skripta(upravitelj, adblock.GENERIC_COSMETIC_SCRIPT, W.UserScriptInjectionTime.END, izloceni=izvzemi)
        self._skripta(upravitelj, adblock.ANTI_CLICKJACKING_SCRIPT, W.UserScriptInjectionTime.END, izloceni=izvzemi + ["file://*"])
        self._skripta(upravitelj, adblock.TAB_THROTTLER_SCRIPT, izloceni=izvzemi)
        nastavitve = pogled.get_settings()
        nastavitve.set_enable_javascript(True)
        nastavitve.set_enable_javascript_markup(True)
        nastavitve.set_javascript_can_open_windows_automatically(False)
        nastavitve.set_enable_html5_local_storage(True)
        nastavitve.set_enable_html5_database(False)
        try:
            nastavitve.set_enable_hyperlink_auditing(False); nastavitve.set_enable_dns_prefetching(False)
            nastavitve.set_enable_page_cache(False); nastavitve.set_enable_encrypted_media(True)
        except Exception:
            pass
        # Temno pod našo začetno stranjo, belo pod spletom - belo mora biti nastavljeno, preden dokument strani nastane.
        ozadje_strani.prikljuci(self.Gdk, W, pogled, os.path.join(self.koren, "ui"), TEMNO_OZADJE)
        pogled.connect("decide-policy", self._politika)
        pogled.connect("create", lambda p, a: self._novo_okno(p, a))
        pogled.connect("load-changed", self._nalozen)
        pogled.connect("notify::title", self._naslov_spremenjen)
        pogled.connect("notify::uri", self._uri_spremenjen)
        pogled.connect("permission-request", self._dovoljenje)
        self._uporabi_filter(pogled)
        return pogled

    def nov_zavihek(self, naslov: str = ""):
        self._stevec += 1
        pogled = self._nov_pogled()
        vrstica = self.Gtk.Box(orientation=self.Gtk.Orientation.HORIZONTAL, spacing=6)
        vrstica.get_style_context().add_class("splet-tab")
        ikona = self.Gtk.Label(label="🌐")
        naslov_lbl = self.Gtk.Label(label=self._t("nov")); naslov_lbl.set_ellipsize(3); naslov_lbl.set_xalign(0)
        zapri = self._gumb("×", lambda *_: self.zapri_zavihek(pogled), "tab-close")
        vrstica.pack_start(ikona, False, False, 0); vrstica.pack_start(naslov_lbl, True, True, 0); vrstica.pack_end(zapri, False, False, 0)
        dogodek = self.Gtk.EventBox(); dogodek.add(vrstica); dogodek.connect("button-press-event", lambda _w, _e: (self.izberi(pogled), True)[1])
        self.skatla_zavihkov.pack_start(dogodek, False, False, 0)
        self.sklad.add_named(pogled, "splet-%d" % self._stevec)
        zavihek = {"pogled": pogled, "dogodek": dogodek, "vrstica": vrstica, "naslov": naslov_lbl, "ikona": ikona}
        self.zavihki.append(zavihek)
        dogodek.show_all(); pogled.show_all(); self.izberi(pogled)
        self.odpri(naslov, pogled)
        return pogled

    def zapri_zavihek(self, pogled):
        if len(self.zavihki) == 1:
            self.odpri_domov(); return
        z = next((x for x in self.zavihki if x["pogled"] is pogled), None)
        if z is None: return
        indeks = self.zavihki.index(z); self.zavihki.remove(z)
        self.skatla_zavihkov.remove(z["dogodek"]); self.sklad.remove(pogled); pogled.destroy()
        self.izberi(self.zavihki[max(0, indeks - 1)]["pogled"])

    def izberi(self, pogled):
        self.aktivni = pogled; self.sklad.set_visible_child(pogled)
        for z in self.zavihki:
            slog = z["vrstica"].get_style_context()
            if z["pogled"] is pogled:
                slog.add_class("splet-tab-aktiven")
            else:
                slog.remove_class("splet-tab-aktiven")
        self._osvezi_orodja()

    def trenutni(self):
        return self.aktivni

    def domaci_uri(self) -> str:
        return self.GLib.filename_to_uri(os.path.join(self.koren, "ui", "splet.html"), None)

    def odpri_domov(self):
        if self.trenutni(): self.trenutni().load_uri(self.domaci_uri())

    def odpri(self, naslov: str = "", pogled=None):
        pogled = pogled or self.trenutni()
        if pogled is None: return False
        if not naslov: pogled.load_uri(self.domaci_uri()); return True
        normalen = normalize_web_url(naslov)
        if not normalen: return False
        pogled.load_uri(normalen); return True

    def odpri_povezavo(self, naslov: str) -> bool:
        """Povezava od drugod (sporočilo): strani, ki jo ima uporabnik odprto, ne zamenja. V zavihku z našo začetno
        stranjo se odpre tam, sicer v novem zavihku."""
        normalen = normalize_web_url(naslov)
        if not normalen: return False
        pogled = self.trenutni()
        if pogled is not None and ozadje_strani.nasa_stran(pogled.get_uri() or "", os.path.join(self.koren, "ui")):
            pogled.load_uri(normalen); return True
        self.nov_zavihek(normalen); return True

    def _vnesi_naslov(self, vnos):
        besedilo = vnos.get_text().strip()
        naslov = normalize_web_url(besedilo)
        if not naslov:
            motor = self.config.get("search_engine", "duckduckgo")
            naslov = SEARCH_ENGINES.get(motor, SEARCH_ENGINES["duckduckgo"])["url"] + urllib.parse.quote_plus(besedilo)
        self.odpri(naslov)

    def _politika(self, pogled, odlocitev, vrsta):
        W = self.WebKit2
        if vrsta not in (W.PolicyDecisionType.NAVIGATION_ACTION, W.PolicyDecisionType.NEW_WINDOW_ACTION): return False
        try:
            dejanje = odlocitev.get_navigation_action(); zahteva = dejanje.get_request(); naslov = zahteva.get_uri() or ""
            if vrsta == W.PolicyDecisionType.NEW_WINDOW_ACTION:
                odlocitev.ignore(); self.nov_zavihek(naslov); return True
            if naslov.startswith(("file://", "about:blank")):
                odlocitev.use(); return True
            if not naslov.startswith(("http://", "https://")):
                odlocitev.ignore(); return True
            if self.config.get("adblock_enabled", True) and adblock.is_ad_domain(naslov) and not adblock.is_threat_domain(naslov):
                self.config.increment_ads_blocked(); odlocitev.ignore(); self._osvezi_scit(); return True
            if adblock.is_threat_domain(naslov):
                self.config.increment_threats_blocked(); odlocitev.ignore(); self._opozorilo("Safeer Shield", naslov); self._osvezi_scit(); return True
            sodba = adblock.fake_bank_verdict(naslov)
            if sodba is not None:
                odlocitev.ignore(); self._opozorilo_bank(pogled, naslov, sodba); return True
            if self.config.get("tracking_protection_enabled", True) and zahteva.get_http_method() == "GET":
                cist = adblock.strip_tracking_parameters(naslov)
                if cist != naslov: odlocitev.ignore(); pogled.load_uri(cist); return True
            odlocitev.use(); return True
        except Exception:
            odlocitev.ignore(); return True

    def _novo_okno(self, _pogled, dejanje):
        try: naslov = dejanje.get_request().get_uri() or ""
        except Exception: naslov = ""
        return self.nov_zavihek(naslov)

    def _nalozen(self, pogled, dogodek):
        if dogodek != self.WebKit2.LoadEvent.FINISHED: return
        naslov = pogled.get_uri() or ""
        if je_domaca_stran(naslov, self.koren):
            self._poslji_stanje(pogled)
        else:
            self._preveri_bank_stran(pogled, naslov)
        self._osvezi_orodja()

    def _poslji_stanje(self, pogled, prenesi=True):
        """Zacetna stran Splet: jezik, iskalnik in bliznjice z ikonami (manjkajoce se prenesejo v ozadju)."""
        from core import ikone_strani
        portali, manjkajo = ikone_strani.z_ikonami(self.config.get_portals())
        # Kdor je kdaj imel lastne bliznjice, mu vgrajenih ne vracamo, ko svoje odstrani (nic ni vsiljeno).
        if portali and not self.config.get("splet_brez_privzetih", False): self.config.set("splet_brez_privzetih", True)
        stanje = {"language": self.jezik(), "engine": self.config.get("search_engine", "duckduckgo"), "portals": portali,
                  "hidden": list(self.config.get("splet_skrite_bliznjice", []) or []),
                  "no_defaults": bool(self.config.get("splet_brez_privzetih", False))}
        pogled.run_javascript("window.safeerSpletInit(%s);" % json.dumps(stanje, ensure_ascii=True), None, None, None)
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
        if pogled is self.trenutni(): self._osvezi_orodja()

    def _osvezi_orodja(self):
        pogled = self.trenutni()
        if not pogled: return
        uri = pogled.get_uri() or ""
        domaca = je_domaca_stran(uri, self.koren)
        self.vnos.set_text("" if domaca else uri)
        self.nazaj.set_sensitive(pogled.can_go_back()); self.naprej.set_sensitive(pogled.can_go_forward())
        self.kljucavnica.set_opacity(1.0 if uri.startswith("https://") else 0.0)
        self._osvezi_scit()

    def _sporocilo(self, pogled, rezultat):
        try:
            vrednost = rezultat.get_js_value().to_json(0)
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

    def _dodaj_portal(self, *_):
        d = self.Gtk.Dialog(title=self._t("dodaj"), transient_for=self.stars, flags=self.Gtk.DialogFlags.MODAL)
        d.add_button(self._t("preklici"), self.Gtk.ResponseType.CANCEL); d.add_button(self._t("shrani"), self.Gtk.ResponseType.OK)
        mreza = self.Gtk.Grid(column_spacing=10, row_spacing=8, margin=16)
        ime, url = self.Gtk.Entry(), self.Gtk.Entry(); url.set_text("https://")
        mreza.attach(self.Gtk.Label(label=self._t("ime"), xalign=0), 0, 0, 1, 1); mreza.attach(ime, 1, 0, 1, 1)
        mreza.attach(self.Gtk.Label(label=self._t("url"), xalign=0), 0, 1, 1, 1); mreza.attach(url, 1, 1, 1, 1)
        d.get_content_area().add(mreza); d.show_all()
        if d.run() == self.Gtk.ResponseType.OK:
            naslov = normalize_web_url(url.get_text())
            if naslov:
                self.config.add_portal(ime.get_text().strip() or urllib.parse.urlparse(naslov).hostname, naslov)
                # Znova dodana bliznjica ni vec med odstranjenimi.
                self.config.set("splet_skrite_bliznjice", [k for k in (self.config.get("splet_skrite_bliznjice", []) or []) if k != kljuc_bliznjice(naslov)])
        d.destroy()
        p = self.trenutni()
        if p and je_domaca_stran(p.get_uri() or "", self.koren): p.reload()

    def dodaj_trenutno(self):
        p = self.trenutni(); uri = p.get_uri() if p else ""
        if not uri or je_domaca_stran(uri, self.koren): return
        self.config.add_portal(p.get_title() or urllib.parse.urlparse(uri).hostname or uri, uri)
        if self.Gtk.IconTheme.get_default().has_icon("starred-symbolic"):
            self.zvezdica.set_image(self.Gtk.Image.new_from_icon_name("starred-symbolic", self.Gtk.IconSize.BUTTON))
        else:
            self.zvezdica.set_label("★")

    def osvezi_povezavo(self):
        try: ok = (self.stanje_povezave() or {}).get("stanje") == "povezan"
        except Exception: ok = False
        self.povezava.set_text(("● " if ok else "○ ") + self._t("povezan" if ok else "nepovezan"))
        return True

    def _osvezi_scit(self):
        n = int(self.config.get("total_ads_blocked", 0)) + int(self.config.get("total_threats_blocked", 0))
        self.scit.set_tooltip_text(self._t("blokirano", count=n))

    def _preveri_bank_stran(self, pogled, uri):
        if not uri.startswith(("http://", "https://")) or adblock.is_real_bank_host(uri): return
        skripta = adblock.bank_guard_page_script()
        if not skripta: return
        pogled.run_javascript_in_world(skripta, "safeer-bankguard", None, self._bank_signali, (pogled, uri))

    def _bank_signali(self, pogled, rezultat, podatki):
        pogled0, uri = podatki
        try: signali = json.loads(pogled.run_javascript_in_world_finish(rezultat).get_js_value().to_json(0) or "null")
        except Exception: return
        if pogled0.get_uri() != uri: return
        sodba = adblock.fake_bank_page_verdict(uri, signali)
        if sodba is not None: self._opozorilo_bank(pogled0, uri, sodba, True)

    def _opozorilo_bank(self, pogled, uri, sodba, nalozen=False):
        d = self.Gtk.MessageDialog(transient_for=self.stars, flags=0, message_type=self.Gtk.MessageType.WARNING,
                                   buttons=self.Gtk.ButtonsType.NONE, text="Safeer Shield · BankGuard")
        d.format_secondary_text(adblock.fake_bank_warning_text(sodba, self.jezik()))
        d.add_button(self._t("nazaj"), 1)
        if sodba.official_domain: d.add_button(sodba.official_domain, 2)
        odgovor = d.run(); d.destroy()
        if odgovor == 2: pogled.load_uri("https://" + sodba.official_domain + "/")
        elif nalozen: pogled.go_back() if pogled.can_go_back() else pogled.load_uri(self.domaci_uri())

    def _opozorilo(self, naslov, opis):
        d = self.Gtk.MessageDialog(transient_for=self.stars, flags=0, message_type=self.Gtk.MessageType.WARNING,
                                   buttons=self.Gtk.ButtonsType.CLOSE, text=naslov)
        d.format_secondary_text(opis); d.run(); d.destroy()

    def _dovoljenje(self, _pogled, zahteva):
        pravilo = self.config.get("permissions_policy", "ask")
        if pravilo == "allow":
            zahteva.allow(); return True
        if pravilo == "deny":
            zahteva.deny(); return True
        d = self.Gtk.MessageDialog(transient_for=self.stars, flags=self.Gtk.DialogFlags.MODAL,
                                   message_type=self.Gtk.MessageType.QUESTION,
                                   buttons=self.Gtk.ButtonsType.NONE, text=self._t("dovoljenje"))
        d.add_button(self._t("zavrni"), self.Gtk.ResponseType.NO)
        d.add_button(self._t("dovoli"), self.Gtk.ResponseType.YES)
        odgovor = d.run(); d.destroy()
        zahteva.allow() if odgovor == self.Gtk.ResponseType.YES else zahteva.deny()
        return True

    def _prenos_zacet(self, _kontekst, prenos):
        ime = os.path.basename(urllib.parse.urlparse(prenos.get_request().get_uri()).path) or "prenos"
        cilj = os.path.join(os.path.expanduser("~/Downloads"), ime)
        os.makedirs(os.path.dirname(cilj), exist_ok=True)
        prenos.set_destination(self.GLib.filename_to_uri(cilj, None)); self.prenosi.append(cilj)

    def _pokazi_prenose(self, *_): self._opozorilo(self._t("prenosi"), "\n".join(self.prenosi[-10:]) or "—")
    def _pokazi_najdi(self): self.najdi_vrstica.set_search_mode(True); self.najdi_vnos.grab_focus()
    def _najdi(self, vnos):
        if self.trenutni(): self.trenutni().get_find_controller().search(vnos.get_text(), 0, 1000)
    def _povecava(self, korak):
        if self.trenutni(): self.trenutni().set_zoom_level(max(.5, min(3.0, self.trenutni().get_zoom_level() + korak)))
    def _nastavitve(self, *_):
        d = self.Gtk.Dialog(title=self._t("nastavitve"), transient_for=self.stars, flags=self.Gtk.DialogFlags.MODAL)
        d.add_button(self._t("preklici"), self.Gtk.ResponseType.CANCEL)
        d.add_button(self._t("shrani"), self.Gtk.ResponseType.OK)
        mreza = self.Gtk.Grid(column_spacing=12, row_spacing=12, margin=18)
        motor = self.Gtk.ComboBoxText()
        for kljuc, podatki in SEARCH_ENGINES.items(): motor.append(kljuc, podatki["name"])
        motor.set_active_id(self.config.get("search_engine", "duckduckgo"))
        oglasi = self.Gtk.CheckButton(label=self._t("adblock")); oglasi.set_active(self.config.get("adblock_enabled", True))
        doh = self.Gtk.CheckButton(label=self._t("doh")); doh.set_active(self.config.get("doh_enabled", True))
        mreza.attach(self.Gtk.Label(label=self._t("iskalnik"), xalign=0), 0, 0, 1, 1); mreza.attach(motor, 1, 0, 1, 1)
        mreza.attach(oglasi, 0, 1, 2, 1); mreza.attach(doh, 0, 2, 2, 1)
        d.get_content_area().add(mreza); d.show_all()
        if d.run() == self.Gtk.ResponseType.OK:
            self.config.set("search_engine", motor.get_active_id() or "duckduckgo")
            self.config.set("adblock_enabled", oglasi.get_active())
            self.config.set("doh_enabled", doh.get_active())
            self._nastavi_omrezje()
        d.destroy()
    def _v_zapisek(self, *_):
        p = self.trenutni()
        if self.odpri_zapisek and p: self.odpri_zapisek(p.get_title() or self._t("nov"), p.get_uri() or "")

    def koncaj(self):
        if self.filter_agent: self.filter_agent.stop()
        if self._threat_service: self._threat_service.stop()
        try:
            get_doh_proxy(enabled=False)
        except Exception:
            pass
