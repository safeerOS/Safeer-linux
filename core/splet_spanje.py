"""Spanje zavihkov v ozadju, stran safeer://procesi in (v 1.0.129 izklopljena) obnova omreznega procesa za Splet
(GTK4, WebKitGTK 6.0).

Prenos iz brskalnika GTK3 (safeer_mint.py, umaknjen 18. 10. 2026), da uporabniki 1.0.127 teh funkcij ne izgubijo.
Splet (core/os_splet.VdelaniSplet) to uporablja v Safeer OS in v Safeer Browser; modul je vezan z nekaj vrsticami.

Meritve v WebKitGTK 6.0 (2.52.6, Xvfb, 18. 10. 2026), na katerih stoji koda:
* Vsak zavihek ima svoj spletni proces. terminate_web_process() ga konca (razlog TERMINATED_BY_API); stran s 400 MiB
  PSS je sprostila 403 MiB. Po koncu pogled nima vec naslova ne naslova strani (get_uri() == ""), seznam
  nazaj/naprej ostane. reload() zazene nov proces, nalozi isti naslov in sam vrne polozaj drsenja (2345 px -> 2345 px).
* reload() strani, ki je rezultat obrazca POST, obrazec POSLJE ZNOVA (strezniku sta prisla dva POST). Zato tak
  zavihek nikoli ne zaspi.
* Povezan pogled (okno, ki ga odpre stran - prijava z Googlom) deli proces z odpiralcem: konec enega je izbrisal
  oba. Zato zavihek s povezanim oknom ne zaspi.
* Zavihek v ozadju (Gtk.Stack) ima document.visibilityState == "hidden" in WebKit sam duši njegove casovnike, zato
  koraka »zamrzni« (skripta, ki je v GTK3 ponarejala skrito stran) ni vec.
* WebKit 6.0 ne pove, kateri proces je od katerega pogleda; procese menja ob prehodu na drugo spletisce (PSON),
  drzi stare za »Nazaj« in enega vnaprej pripravljenega - par »nov proces = zavihek, ki se je zacel nalagati« (GTK3)
  tu ni zanesljiv. Proces pogleda zato poiscemo s sondo: 40 ms racunanja v pogledu (locen svet skript), proces,
  katerega cas CPU zraste, je njegov.
* WebKit 6.0 nima API-ja za konec omreznega procesa (NetworkSession/WebContext: preverjeno z introspekcijo), zato ga je
  recikliranje koncalo s SIGTERM kot GTK3 (proces z odprto shrambo piskotkov Spleta). Piskotki seje (brez roka) so
  samo v pomnilniku omreznega procesa - pred koncem jih preberemo in vrnemo. V 1.0.129 je recikliranje IZKLOPLJENO
  (RECIKLIRANJE_OMREZNEGA = False): spletni procesi, ki jih WebKit hrani za nove zavihke, ostanejo povezani s koncanim
  omreznim procesom in prvo nalaganje odpove (napaka lupe 20. 10. 2026, AGENTS.md).
"""
from __future__ import annotations

import json
import os
import secrets
import signal
import time
import urllib.parse
import weakref

from core import poraba_zgodovina, pomnilnik, processes_page, storitve_na_zahtevo, tab_lifecycle
from core.tab_monitor import CLK_TCK, TabMonitor, web_processes_under

SHEMA = "safeer"
PROCESI = processes_page.PAGE_URI
#: Vpisi v naslovno vrstico, ki odprejo stran procesov (»procesi« kot v GTK3).
VPISI_PROCESOV = ("safeer://procesi", "procesi", "safeer://processes")
#: Locen svet skript: stran ga ne vidi in ne more ponarediti njegovih sporocil.
SVET = "safeer-spanje"
MOST = "safeerSpanje"
SONDA_MS = 40
_SONDA_JS = "(function(){var k=performance.now()+%d;while(performance.now()<k){}return 1;})()" % SONDA_MS
#: Vsi Spleti v procesu (Safeer OS ima dva: okno in plosca na namizju): stran procesov enega pozna naslove zavihkov
#: drugega (njihovi spletni procesi niso »neznani«).
_PRIMERKI: "weakref.WeakSet" = weakref.WeakSet()
#: Ena sonda naenkrat v vsem procesu (Safeer OS ima dva Spleta v istem procesu); cas zacetka, 0 = nobena. Odgovor, ki
#: ga ni v 3 s (pogled se je medtem zaprl), zaklepa ne drzi vec.
_SONDA = {"tece": 0.0}

#: Stanje zavihka iz vseh okvirjev (tudi tujih iframe): urejen obrazec (vpis uporabnika, ki se ni poslan ali izbrisan)
#: in predvajanje (video brez zvoka WebKit ne javi kot is-playing-audio). Vsak okvir poslje svoje stanje ob spremembi.
SKRIPTA_STANJA = r"""
(function () {
  "use strict";
  if (window.__safeerSpanje) return;
  window.__safeerSpanje = true;
  var h = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.safeerSpanje;
  if (!h) return;
  var okvir = Math.random().toString(36).slice(2, 12), polja = [], mediji = [], zadnje = "", cakam = 0, preveri = 0;
  function cilj(e) { var p = e.composedPath ? e.composedPath() : []; return p.length ? p[0] : e.target; }
  function urejeno(el) {
    try {
      if (!el.isConnected) return false;
      if (el.isContentEditable) return (el.textContent || "").trim() !== "";
      var t = (el.type || "").toLowerCase();
      if (t === "checkbox" || t === "radio") return el.checked !== el.defaultChecked;
      if (el.tagName === "SELECT") {
        for (var i = 0; i < el.options.length; i++) if (el.options[i].selected !== el.options[i].defaultSelected) return true;
        return false;
      }
      return typeof el.value === "string" && el.value !== el.defaultValue;
    } catch (x) { return false; }
  }
  function igra() {
    var vsi = Array.prototype.slice.call(document.querySelectorAll("video, audio")).concat(mediji);
    for (var i = 0; i < vsi.length; i++) {
      var m = vsi[i];
      if (m.isConnected && !m.paused && !m.ended) return true;
    }
    return false;
  }
  function poslji(konec) {
    var s = konec ? {f: okvir, u: false, m: false, konec: true} : {f: okvir, u: polja.some(urejeno), m: igra()};
    var k = JSON.stringify(s);
    if (k === zadnje) return;
    zadnje = k;
    try { h.postMessage(s); } catch (x) {}
    // Stran polje po posiljanju izprazni sama (brez dogodka input): dokler je urejeno, preverimo vsakih 5 s.
    clearTimeout(preveri);
    if (s.u || s.m) preveri = setTimeout(function () { poslji(false); }, 5000);
  }
  function kasneje() { if (!cakam) cakam = setTimeout(function () { cakam = 0; poslji(false); }, 400); }
  function vpis(e) {
    if (!e.isTrusted) return;
    var el = cilj(e);
    if (el && (el.isContentEditable || "value" in el) && polja.indexOf(el) < 0) {
      polja.push(el);
      if (polja.length > 50) polja.shift();
    }
    kasneje();
  }
  document.addEventListener("input", vpis, true);
  document.addEventListener("change", vpis, true);
  document.addEventListener("submit", kasneje, true);
  ["play", "playing", "pause", "ended", "emptied"].forEach(function (t) {
    document.addEventListener(t, function (e) {
      var el = cilj(e);
      if (el instanceof HTMLMediaElement && mediji.indexOf(el) < 0) {
        mediji.push(el);
        if (mediji.length > 20) mediji.shift();
      }
      kasneje();
    }, true);
  });
  window.addEventListener("pagehide", function () { poslji(true); }, true);
  window.addEventListener("pageshow", function (e) { if (e.persisted) { zadnje = ""; poslji(false); } }, true);
})();
"""


def je_notranja(naslov: str) -> bool:
    """Nasa stran na shemi safeer:// (ozadje_strani: temna podlaga, brez belega bliska ob osvezitvi)."""
    return str(naslov or "").startswith("safeer://procesi")


def naslov_menija(jezik) -> str:
    """»Procesi« v meniju Spleta: isto besedilo kot naslov strani (processes_page, vseh sest jezikov)."""
    j = str((jezik() if callable(jezik) else jezik) or "en")[:2]
    return processes_page._TEXT.get(j, processes_page._TEXT["en"])["title"]


def naslov_pogleda(pogled) -> str:
    """Naslov zavihka - tudi uspanega: pogled po koncu procesa nima naslova (meritev zgoraj), zato ga hranimo sami.
    Za sejo ob zaprtju okna in Ctrl+Shift+T (brez tega bi se uspani zavihki izgubili)."""
    try:
        spi = getattr(pogled, "_safeer_spi_uri", "")
        return (spi if isinstance(spi, str) and spi else pogled.get_uri()) or ""
    except Exception:  # noqa: BLE001
        return ""


def razlogi_zascite(stanje: dict) -> list:
    """Zakaj zavihek ne sme zaspati (kljuci processes_page.REASONS); prazno = sme. `stanje` so podatki zavihka iz
    SpanjeZavihkov._stanje (brez GTK, zato preizkusljivo)."""
    razlogi = []
    if stanje.get("media"):
        razlogi.append("media")
    if stanje.get("form"):
        razlogi.append("form")
    if stanje.get("post"):
        razlogi.append("post")
    if stanje.get("download"):
        razlogi.append("download")
    if stanje.get("capture"):
        razlogi.append("capture")
    if stanje.get("linked"):
        razlogi.append("linked")
    return razlogi


def sme_spati(stanje: dict) -> bool:
    """Varnostna pravila (lastnik, 18. 10. 2026): nikoli viden ali aktiven zavihek, zvok ali video, prenos, urejen ali
    poslan obrazec, kamera/mikrofon/zaslon, povezano okno, vdelana aplikacija, nalaganje, vprasanje ali Safeer DRM;
    samo spletna stran ali nasa zacetna stran (ne nasa stran procesov, ne prazen zavihek)."""
    if (stanje.get("active") or stanje.get("visible") or stanje.get("audio") or stanje.get("sleeping")
            or stanje.get("app") or stanje.get("loading") or stanje.get("busy")):
        return False
    if razlogi_zascite(stanje):
        return False
    uri = str(stanje.get("uri") or "")
    return uri.startswith(("http://", "https://", "file://"))


def proces_iz_sonde(pred: dict, po: dict, najmanj: int = 3):
    """PID, katerega cas CPU je med sondo zrasel (vsaj `najmanj` tikov) in jasno bolj kot pri drugih (vsaj 3-krat);
    0, ce sonda ni enoznacna (druga stran je ravno takrat racunala) - takrat poskusimo znova."""
    rast = sorted(((po[p] - pred[p], p) for p in po if p in pred), reverse=True)
    if not rast or rast[0][0] < najmanj:
        return 0
    if len(rast) > 1 and rast[1][0] * 3 > rast[0][0]:
        return 0
    return rast[0][1]


def _tiki(pid: int) -> int:
    try:
        with open("/proc/%d/stat" % pid, "rb") as f:
            polja = f.read().rsplit(b")", 1)[1].split()
        return int(polja[11]) + int(polja[12])
    except (OSError, IndexError, ValueError):
        return -1


def _tiki_vseh() -> dict:
    izid = {}
    for pid in web_processes_under(os.getpid()):
        t = _tiki(pid)
        if t >= 0:
            izid[pid] = t
    return izid



#: Recikliranje omreznega procesa med mirovanjem. IZKLOPLJENO v 1.0.129 (ponovni pregled OpenAI F, 21. 10. 2026):
#: Safeer OS ima dva Spleta z isto shrambo piskotkov - varuh enega bi lahko koncal omrezni proces drugega, aktivnega,
#: in ob napaki branja piskotkov bi se vseeno koncal. AGENTS.md (napake 1.0.129): omreznega procesa WebKit nikoli ne
#: koncaj od zunaj, dokler zivijo spletni procesi. Z nasim libsoup ne raste; s sistemskim (AppImage) do 1.0.130, ko bo
#: tudi AppImage nosil nas libsoup, pomnilnik raste namesto odjav. Logika ostane preizkusena (preizkusi jo vklopijo).
RECIKLIRANJE_OMREZNEGA = False


def _sme_koncati_omrezni(s) -> bool:
    """Ali se omrezni proces Spleta sme koncati (recikliranje): samo s sistemskim libsoup, ki pusca, in ko na njem ne
    tecejo vdelane aplikacije (klepeti v realnem casu) ne skriti pogledi sprotnih zadetkov lupe. Z nasim libsoup proces
    ne raste, konec pa pokvari prvo nalaganje v odprtih zavihkih (WebKitErrorDomain 300 - lupa 20. 10. 2026)."""
    if not RECIKLIRANJE_OMREZNEGA or s.aplikacije:
        return False
    skriti = getattr(s, "_skriti", None)
    if skriti is not None and len(skriti()):
        return False
    from core.os_splet import libsoup_brez_puscanja
    return not libsoup_brez_puscanja()

class SpanjeZavihkov:
    """Spanje zavihkov, stran procesov in (izklopljena v 1.0.129) obnova omreznega procesa za en VdelaniSplet."""

    def __init__(self, splet) -> None:
        self._splet = weakref.ref(splet)
        self.GLib = splet.GLib
        self.W = splet.WebKit2
        # Proracun kot v GTK3: tezek zavihek je nad ~1 GB ali nad 70 % jedra; dolgo nad njim po minuti.
        self.nadzor = TabMonitor(cpu_budget=0.7, show_after=15.0, patience=60.0,
                                 memory_budget_mb=max(512, min(1024, pomnilnik.meja_strani_mb() // 4)))
        self._stevec = 0
        self._kljuc = secrets.token_urlsafe(16)
        self._okno_neaktivno_od = None
        self._recikliranje = False
        self._css_namescen = False
        #: Zadnje branje (cas, tiki) procesov programa za trenutni CPU na strani procesov (glej sistem()).
        self._branja: dict = {}
        _PRIMERKI.add(self)
        # Zgodovina porabe (povprecje in vrh zadnje ure) tece na uri registra storitev: v Safeer OS jo je ze zagnal
        # safeer_os.py, v Safeer Browser jo zazene prvi Splet (glavna zanka GLib, brez lastne niti).
        poraba_zgodovina.skupna()
        storitve_na_zahtevo.zacni(self.GLib)
        self._registriraj_shemo(splet.kontekst)
        self.GLib.timeout_add_seconds(2, self._tik_nadzor)
        # Ena ura za vse zavihke (kot GTK3): neaktivni zavihki, pomanjkanje pomnilnika, omrezni proces.
        self.GLib.timeout_add_seconds(15, self._tik_zivljenja)

    # ------------------------------------------------------------------ shema safeer://
    def _registriraj_shemo(self, kontekst) -> None:
        """safeer://procesi samo za nas: shema je lokalna in izolirana - spletna stran je ne more odpreti, vdelati
        (iframe, img), prebrati (fetch), nanjo preusmeriti ali je odpreti v oknu (izmerjeno 18. 10. 2026: 0 klicev
        obdelovalca od 6 poskusov strani; brez oznak 4 od 5). Oznake »no_access« namenoma ni: stran dobi neprozoren
        izvor in ne more vec niti na svoje povezave (izmerjeno). Dejanja zahtevajo se enkratni kljuc (_obdelaj_zahtevo)."""
        try:
            kontekst.register_uri_scheme(SHEMA, self._obdelaj_zahtevo)
            varnost = kontekst.get_security_manager()
            varnost.register_uri_scheme_as_local(SHEMA)
            varnost.register_uri_scheme_as_display_isolated(SHEMA)
        except Exception as napaka:  # noqa: BLE001 - brez sheme ostane vse drugo
            print("[Splet] shema safeer:// ni registrirana:", napaka, flush=True)

    def _obdelaj_zahtevo(self, zahteva) -> None:
        uri = zahteva.get_uri() or ""
        s = self._splet()
        try:
            pogled = zahteva.get_web_view()
        except Exception:  # noqa: BLE001
            pogled = None
        if s is None or not je_notranja(uri) or pogled is None or s._zavihek(pogled) is None:
            # Samo zavihki Spleta (ne vdelane aplikacije) in samo stran procesov.
            self._napaka(zahteva)
            return
        skriti = set()
        dejanje, cilj = processes_page.parse_action(uri)
        if dejanje and cilj and secrets.compare_digest(processes_page.action_key(uri), self._kljuc):
            self._kljuc = secrets.token_urlsafe(16)     # enkraten: »Nazaj« ali osvezitev dejanja ne ponovi
            z = self._zavihek_po_id(cilj)
            if z is not None and dejanje == "spi":
                self.uspavaj(z, "safeer://procesi")
            elif z is not None and dejanje == "zapri":
                skriti.add(cilj)
                ref = weakref.ref(z["pogled"])
                self.GLib.idle_add(lambda: (ref() is not None and s._zavihek(ref()) is not None
                                            and s.zapri_zavihek(ref()), False)[1])
        podatki = self.stran_procesov(skriti).encode("utf-8")
        try:
            tok = s.Gio.MemoryInputStream.new_from_bytes(self.GLib.Bytes.new(podatki))
            zahteva.finish(tok, len(podatki), "text/html")
        except Exception as napaka:  # noqa: BLE001
            print("[Splet] safeer://procesi:", napaka, flush=True)
            self._napaka(zahteva)

    def _napaka(self, zahteva) -> None:
        try:
            zahteva.finish_error(self.GLib.Error.new_literal(self.GLib.quark_from_string("safeer"), "ni na voljo", 404))
        except Exception:  # noqa: BLE001
            pass

    def politika(self, pogled, odlocitev, vrsta) -> bool:
        """Klice VdelaniSplet._politika na zacetku. Vrne True, ce je odlocitev ze sprejeta.

        * POST v glavnem okvirju si zapomnimo: reload() take strani po spanju bi obrazec poslal znova (izmerjeno).
        * safeer://procesi: samo uporabnik (naslovna vrstica, meni) ali nasa stran sama; spletna stran nikoli (WebKit
          jo ze ustavi zaradi lokalne sheme - to je druga plast)."""
        W = self.W
        if vrsta != W.PolicyDecisionType.NAVIGATION_ACTION and vrsta != W.PolicyDecisionType.NEW_WINDOW_ACTION:
            return False
        try:
            dejanje = odlocitev.get_navigation_action()
            zahteva = dejanje.get_request()
            naslov = zahteva.get_uri() or ""
        except Exception:  # noqa: BLE001
            return False
        s = self._splet()
        z = s._zavihek(pogled) if s is not None else None
        if vrsta == W.PolicyDecisionType.NAVIGATION_ACTION and z is not None and "spanje" in z:
            try:
                if (zahteva.get_http_method() or "").upper() == "POST":
                    z["spanje"]["post_cakajoc"] = naslov
            except Exception:  # noqa: BLE001
                pass
        if not naslov.startswith(SHEMA + ":"):
            return False
        # »Nazaj«/»Naprej« in osvezitev smeta na stran procesov: dejanje brez svezega kljuca le pokaze seznam.
        zgodovina = dejanje.get_navigation_type() in (W.NavigationType.BACK_FORWARD, W.NavigationType.RELOAD)
        dovoli = (vrsta == W.PolicyDecisionType.NAVIGATION_ACTION and z is not None and je_notranja(naslov)
                  and (getattr(pogled, "_safeer_notranja", "") == naslov or je_notranja(pogled.get_uri() or "")
                       or zgodovina))
        if getattr(pogled, "_safeer_notranja", "") == naslov:
            pogled._safeer_notranja = ""
        if dovoli:
            odlocitev.use()
        else:
            odlocitev.ignore()
        return True

    def odpri_procese(self, vpis: str = PROCESI, nov: bool = False) -> bool:
        """Uporabnik je vpisal »procesi« (ali safeer://procesi) ali izbral Procesi v meniju. True, ce je vpis nas."""
        if str(vpis or "").strip().lower() not in VPISI_PROCESOV:
            return False
        s = self._splet()
        if s is None:
            return False
        pogled = s.trenutni()
        if nov or pogled is None:
            pogled = s.nov_zavihek()
        pogled._safeer_notranja = PROCESI
        pogled.load_uri(PROCESI)
        return True

    # ------------------------------------------------------------------ zavihki
    def _zavihek_po_id(self, ident: str):
        s = self._splet()
        if s is None:
            return None
        return next((z for z in s.zavihki if z.get("spanje", {}).get("id") == ident), None)

    def nov(self, z: dict, povezan=None) -> None:
        """Klice VdelaniSplet.nov_zavihek, preden se zavihek prvic nalozi."""
        s = self._splet()
        self._stevec += 1
        st = {"id": "z%d" % self._stevec, "neaktiven_od": None, "spi": False, "okvirji": {}, "post": False,
              "post_cakajoc": "", "preusmerjen": False, "povezani": [], "sonda_po": 0.0, "sonde": 0}
        z["spanje"] = st
        pogled = z["pogled"]
        if povezan is not None and s is not None:
            # Okno strani (window.open) deli proces z odpiralcem: dokler sta oba odprta, ne zaspi nobeden.
            st["povezani"].append(weakref.ref(povezan))
            oz = s._zavihek(povezan)
            if oz is not None and "spanje" in oz:
                oz["spanje"]["povezani"].append(weakref.ref(pogled))
        try:
            from core.os_splet import registriraj_most
            upravitelj = pogled.get_user_content_manager()
            registriraj_most(upravitelj, MOST, SVET)
            upravitelj.add_script(self.W.UserScript.new_for_world(
                SKRIPTA_STANJA, self.W.UserContentInjectedFrames.ALL_FRAMES, self.W.UserScriptInjectionTime.START,
                SVET, None, None))
            ref = weakref.ref(pogled)
            upravitelj.connect("script-message-received::" + MOST,
                               lambda _u, vrednost: ref() is not None and self._sporocilo(ref(), vrednost))
        except Exception as napaka:  # noqa: BLE001 - brez skripte zavihek pac nikoli ne zaspi zaradi obrazca
            st["brez_skripte"] = True
            print("[Splet] stanje zavihka:", napaka, flush=True)
        pogled.connect("load-changed", self._nalaganje)
        # Po notify::title in ::favicon Spleta (povezana prej): uspan zavihek obdrzi svoj naslov in ikono.
        pogled.connect("notify::title", lambda p, _l: self._obdrzi_oznako(p))
        pogled.connect("notify::favicon", lambda p, _l: self._obdrzi_oznako(p))
        self._namesti_css(s)

    def _namesti_css(self, s) -> None:
        if self._css_namescen or s is None:
            return
        self._css_namescen = True
        try:
            css = s.Gtk.CssProvider()
            pravilo = ".splet-tab-spi { opacity: 0.6; }"
            if hasattr(css, "load_from_string"):
                css.load_from_string(pravilo)          # GTK 4.12+
            else:
                css.load_from_data(pravilo, -1)
            s.Gtk.StyleContext.add_provider_for_display(s.Gdk.Display.get_default(), css,
                                                        s.Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        except Exception:  # noqa: BLE001 - brez sloga ostaneta opis in namig
            pass

    def _sporocilo(self, pogled, vrednost) -> None:
        s = self._splet()
        z = s._zavihek(pogled) if s is not None else None
        if z is None or "spanje" not in z:
            return
        try:
            podatki = json.loads(vrednost.to_json(0) or "null")
        except Exception:  # noqa: BLE001
            return
        if not isinstance(podatki, dict) or not isinstance(podatki.get("f"), str):
            return
        okvirji = z["spanje"]["okvirji"]
        if podatki.get("konec") or not (podatki.get("u") or podatki.get("m")):
            okvirji.pop(podatki["f"], None)
        elif len(okvirji) < 64 or podatki["f"] in okvirji:
            okvirji[podatki["f"]] = (bool(podatki.get("u")), bool(podatki.get("m")))

    def _nalaganje(self, pogled, dogodek) -> None:
        s = self._splet()
        z = s._zavihek(pogled) if s is not None else None
        if z is None or "spanje" not in z:
            return
        st = z["spanje"]
        W = self.W
        if dogodek == W.LoadEvent.STARTED:
            st["preusmerjen"] = False
        elif dogodek == W.LoadEvent.REDIRECTED:
            st["preusmerjen"] = True      # POST -> 303 -> GET: koncna stran je GET, ponovno nalaganje je varno
        elif dogodek == W.LoadEvent.COMMITTED:
            uri = pogled.get_uri() or ""
            st["post"] = bool(st["post_cakajoc"]) and st["post_cakajoc"] == uri and not st["preusmerjen"]
            st["post_cakajoc"] = ""
            st["okvirji"] = {}            # nov dokument: stanje starih okvirjev ne velja vec
            # Nov dokument je lahko v drugem procesu (PSON): proces poiscemo znova, ko se stran nalozi.
            self.nadzor.forget(st["id"])
            st["sonde"] = 0
            st["sonda_po"] = time.monotonic() + 2.0
        elif dogodek == W.LoadEvent.FINISHED:
            st["sonda_po"] = max(st["sonda_po"], time.monotonic() + 1.0)

    def izbran(self, pogled) -> None:
        """Klice VdelaniSplet.izberi: izbrani zavihek ni vec neaktiven (in se zbudi), prejsnji postane neaktiven."""
        s = self._splet()
        if s is None:
            return
        zdaj = time.monotonic()
        for z in s.zavihki:
            st = z.get("spanje")
            if st is None:
                continue
            if z["pogled"] is pogled:
                st["neaktiven_od"] = None
                if st["spi"]:
                    self.zbudi(z)
            elif st["neaktiven_od"] is None:
                st["neaktiven_od"] = zdaj

    def _stanje(self, z: dict) -> dict:
        """Podatki za odlocitev (sme_spati, razlogi_zascite, tab_lifecycle) iz pogleda in Spleta."""
        s = self._splet()
        p = z["pogled"]
        st = z["spanje"]
        W = self.W
        stanje = {"id": st["id"], "sleeping": st["spi"], "inactive_since": st["neaktiven_od"],
                  "active": s is not None and p is s.aktivni, "post": st["post"],
                  "busy": bool(z.get("drm") is not None or z.get("drm_ponudba") or z.get("vprasanja")
                               or z.get("pojavno_prazno") is not None or st.get("brez_skripte")),
                  "rss_mb": getattr(getattr(self, "vzorci", {}).get(st["id"]), "rss_mb", 0)}
        if st["spi"]:
            stanje["uri"] = getattr(p, "_safeer_spi_uri", "")
            return stanje
        try:
            stanje["uri"] = p.get_uri() or ""
            stanje["visible"] = bool(p.get_mapped())
            stanje["loading"] = bool(p.is_loading())
            stanje["audio"] = bool(p.is_playing_audio())
            brez = W.MediaCaptureState.NONE
            stanje["capture"] = any(x != brez for x in (p.get_camera_capture_state(), p.get_microphone_capture_state(),
                                                         p.get_display_capture_state()))
        except Exception:  # noqa: BLE001 - zaprt pogled: nikoli ne spi
            stanje["busy"] = True
        stanje["form"] = any(u for u, _m in st["okvirji"].values())
        stanje["media"] = any(m for _u, m in st["okvirji"].values())
        stanje["download"] = any(zp.get("stanje") == "tece" and _pogled_prenosa(zp.get("prenos")) is p
                                 for zp in (s.prenosi if s is not None else []))
        stanje["linked"] = s is not None and any(r() is not None and s._zavihek(r()) is not None for r in st["povezani"])
        return stanje

    def uspavaj(self, z: dict, razlog: str = "") -> bool:
        """Konca spletni proces zavihka; zavihek ostane in se ob izbiri nalozi znova na istem mestu."""
        if "spanje" not in z or not sme_spati(self._stanje(z)):
            return False
        p = z["pogled"]
        st = z["spanje"]
        uri = p.get_uri() or ""
        try:
            naslov = p.get_title() or z["naslov"].get_text()
        except Exception:  # noqa: BLE001
            naslov = uri
        try:
            ikona = p.get_favicon()
        except Exception:  # noqa: BLE001
            ikona = None
        st.update(spi=True, naslov=naslov, ikona=ikona)
        p._safeer_spi_uri = uri
        try:
            p.terminate_web_process()
        except Exception as napaka:  # noqa: BLE001
            st["spi"] = False
            p._safeer_spi_uri = ""
            print("[Splet] zavihka ni bilo mogoce uspavati:", napaka, flush=True)
            return False
        self.nadzor.forget(st["id"])
        self._oznaci(z, True)
        print("[Splet] zavihek uspavan (%s)" % razlog, flush=True)
        return True

    def zbudi(self, z: dict) -> None:
        st = z["spanje"]
        p = z["pogled"]
        uri = getattr(p, "_safeer_spi_uri", "")
        st["spi"] = False
        p._safeer_spi_uri = ""
        self._oznaci(z, False)
        try:
            if p.get_back_forward_list().get_current_item() is not None:
                p.reload()          # isti vnos zgodovine: WebKit vrne tudi polozaj drsenja (izmerjeno)
            elif uri:
                p.load_uri(uri)
        except Exception as napaka:  # noqa: BLE001
            print("[Splet] zbujanje zavihka:", napaka, flush=True)

    def _oznaci(self, z: dict, spi: bool) -> None:
        st = z["spanje"]
        try:
            from core.i18n import TRANSLATIONS
            s = self._splet()
            jezik = str((s.jezik() if callable(s.jezik) else s.jezik) or "en")[:2] if s is not None else "en"
            opis = TRANSLATIONS.get(jezik, TRANSLATIONS["en"]).get("tab_sleeping") or TRANSLATIONS["en"]["tab_sleeping"]
            if spi:
                z["vrstica"].add_css_class("splet-tab-spi")
                z["naslov"].set_text(st.get("naslov") or "")
                z["vrstica"].set_tooltip_text("%s\n%s" % (st.get("naslov") or "", opis))
            else:
                z["vrstica"].remove_css_class("splet-tab-spi")
                z["vrstica"].set_tooltip_text(z["naslov"].get_text())
            # Bralnik zaslona (dostopnost): zavihek spi in kaj naredi klik.
            z["vrstica"].update_property([s.Gtk.AccessibleProperty.DESCRIPTION], [opis if spi else ""])
        except Exception:  # noqa: BLE001
            pass

    def _obdrzi_oznako(self, pogled) -> None:
        s = self._splet()
        z = s._zavihek(pogled) if s is not None else None
        if z is None or not z.get("spanje", {}).get("spi"):
            return
        st = z["spanje"]
        try:
            if z["naslov"].get_text() != (st.get("naslov") or ""):
                self._oznaci(z, True)
            if st.get("ikona") is not None:
                z["ikona"].set_from_paintable(st["ikona"])
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ meritve in ura
    def _pogledi(self, s) -> list:
        """(id, pogled, zavihek ali None) za vse zavihke in vdelane aplikacije."""
        izid = [(z["spanje"]["id"], z["pogled"], z) for z in s.zavihki if "spanje" in z]
        for pogled in list(s.aplikacije):
            ident = getattr(pogled, "_safeer_spanje_id", None)
            if ident is None:
                self._stevec += 1
                ident = pogled._safeer_spanje_id = "a%d" % self._stevec
            izid.append((ident, pogled, None))
        return izid

    def _tik_nadzor(self) -> bool:
        s = self._splet()
        if s is None or getattr(s, "_koncan", False):
            return False
        try:
            self._nadzor(s)
        except Exception as napaka:  # noqa: BLE001 - ura ne sme nikoli obstati
            print("[Splet] nadzor zavihkov:", napaka, flush=True)
        return True

    def _nadzor(self, s) -> None:
        pogledi = self._pogledi(s)
        if not pogledi:
            return
        vrstice = []
        for ident, p, z in pogledi:
            if z is not None and z["spanje"]["spi"]:
                continue
            try:
                zvok = bool(p.is_playing_audio())
            except Exception:  # noqa: BLE001
                zvok = False
            vrstice.append((ident, None, p is s.aktivni, zvok))
        self.vzorci = self.nadzor.sample(vrstice)
        if s.config.get("sleep_heavy_background_tabs", True):
            for ident, _p, z in pogledi:
                v = self.vzorci.get(ident)
                if z is not None and v is not None and v.verdict == "hog" and not v.active:
                    self.uspavaj(z, "dolgo nad proracunom: %s" % _opis(v))
        self._sondiraj(s, pogledi)

    def _sondiraj(self, s, pogledi) -> None:
        """Poisce proces enega pogleda brez znanega procesa. Ne v pogledu, ki je na zaslonu (40 ms racunanja bi lahko
        zatresli drsenje) - ta pride na vrsto, ko gre v ozadje."""
        zdaj = time.monotonic()
        if zdaj - _SONDA["tece"] < 3.0:
            return
        for ident, p, z in pogledi:
            st = z["spanje"] if z is not None else p.__dict__.setdefault("_safeer_sonda", {"sonda_po": 0.0, "sonde": 0})
            if (z is not None and st["spi"]) or self.nadzor.pid_of(ident) or st["sonde"] >= 3 or st["sonda_po"] > zdaj:
                continue
            try:
                if p.is_loading() or not (p.get_uri() or "") or p.get_mapped():
                    continue
            except Exception:  # noqa: BLE001
                continue
            st["sonde"] += 1
            st["sonda_po"] = zdaj + 5.0
            self._sonda(ident, p)
            return

    def _sonda(self, ident: str, pogled) -> None:
        _SONDA["tece"] = time.monotonic()
        pred = _tiki_vseh()

        def konec(p, rezultat, *_):
            _SONDA["tece"] = 0.0
            try:
                p.evaluate_javascript_finish(rezultat)
            except Exception:  # noqa: BLE001 - stran je medtem odsla ali se zaprla
                return
            pid = proces_iz_sonde(pred, _tiki_vseh(), najmanj=max(2, SONDA_MS * CLK_TCK // 1000 - 1))
            if pid:
                self.nadzor.pair(ident, pid)
        try:
            pogled.evaluate_javascript(_SONDA_JS, -1, SVET, None, None, konec, None)
        except Exception:  # noqa: BLE001
            _SONDA["tece"] = 0.0

    def _tik_zivljenja(self) -> bool:
        s = self._splet()
        if s is None or getattr(s, "_koncan", False):
            return False
        try:
            zdaj = time.monotonic()
            self._neaktivni(s, zdaj)
            self._pritisk(s)
            self._omrezni(s, zdaj)
        except Exception as napaka:  # noqa: BLE001 - ura ne sme nikoli obstati
            print("[Splet] zivljenje zavihkov:", napaka, flush=True)
        return True

    def _neaktivni(self, s, zdaj: float) -> None:
        """Tih zavihek, ki ga uporabnik dolgo ne uporablja, zaspi (tab_discard_after_s, privzeto 10 min, kot GTK3).
        Korak »zamrzni« je izklopljen: WebKit skrito stran dusi sam (meritev v glavi modula)."""
        zavrzi_po = max(0.0, float(s.config.get("tab_discard_after_s", 600) or 0))
        if zavrzi_po <= 0:
            return
        for z in list(s.zavihki):
            if "spanje" not in z or z["spanje"]["spi"]:
                continue
            stanje = self._stanje(z)
            dejanje = tab_lifecycle.dejanje_zavihka(
                neaktiven_od=stanje["inactive_since"], zdaj=zdaj, aktiven=stanje["active"],
                zvok=bool(stanje.get("audio")), zasciten=not sme_spati(stanje), zamrznjen=False,
                zamrzni_po=0, zavrzi_po=zavrzi_po)
            if dejanje == "zavrzi":
                self.uspavaj(z, "neaktiven %d s" % int(zdaj - stanje["inactive_since"]))

    def _pritisk(self, s) -> None:
        """Pod 10 % razpolozljivega pomnilnika zaspijo najstarejsi neaktivni zavihki do manjkajocega (kot GTK3)."""
        try:
            with open("/proc/meminfo", encoding="ascii") as f:
                razpolozljivo, skupaj = tab_lifecycle.pomnilnik(f.read())
        except OSError:
            return
        if skupaj <= 0 or razpolozljivo / skupaj >= 0.10:
            return
        stanja = []
        for z in s.zavihki:
            if "spanje" in z and not z["spanje"]["spi"]:
                stanje = self._stanje(z)
                stanje["protected"] = not sme_spati(stanje)
                stanja.append(stanje)
        for kandidat in tab_lifecycle.izberi_za_sprostitev(stanja, int(skupaj * 0.10 - razpolozljivo)):
            z = self._zavihek_po_id(kandidat["id"])
            if z is not None:
                self.uspavaj(z, "MemAvailable pod 10 %")

    def _omrezni(self, s, zdaj: float) -> bool:
        """Varnostna mreza (libsoup je zdaj popravljen proti puscanju CONNECT): prevelik omrezni proces bi obnovili
        samo, ko okna 5 min nihce ne uporablja in se nic ne prenasa, nalaga ali predvaja (pravila iz GTK3). V 1.0.129
        izklopljeno (_sme_koncati_omrezni -> RECIKLIRANJE_OMREZNEGA)."""
        meja = float(s.config.get("network_process_limit_mb", 300) or 0)
        if meja <= 0 or self._recikliranje:
            return False
        try:
            okno = s.gradnik.get_root()
            aktivno = okno is not None and okno.get_visible() and okno.is_active()
        except Exception:  # noqa: BLE001
            aktivno = True
        if aktivno:
            self._okno_neaktivno_od = None
            return False
        if self._okno_neaktivno_od is None:
            self._okno_neaktivno_od = zdaj
            return False
        if not _sme_koncati_omrezni(s):
            return False
        prenosi = any(zp.get("stanje") == "tece" for zp in s.prenosi)
        nalaganje = zvok = False
        for z in s.zavihki:
            if "spanje" not in z or z["spanje"]["spi"]:
                continue
            try:
                nalaganje = nalaganje or bool(z["pogled"].is_loading())
                zvok = zvok or bool(z["pogled"].is_playing_audio()) or any(m for _u, m in z["spanje"]["okvirji"].values())
            except Exception:  # noqa: BLE001
                return False
        from core.os_splet import omrezni_procesi_shrambe, pss_mb
        for pid in omrezni_procesi_shrambe(os.path.join(s.config.config_dir, "cookies.sqlite")):
            velikost = pss_mb(pid)
            if pomnilnik.recikliraj_omrezni(okno_aktivno=False, neaktivno_s=zdaj - self._okno_neaktivno_od,
                                            prenosi=prenosi, nalaganje=nalaganje, zvok=zvok,
                                            pss_mb=velikost, meja_mb=meja):
                self.recikliraj_omrezni(pid, velikost)
                return True
        return False

    def recikliraj_omrezni(self, pid: int, velikost: float = 0.0, ob_koncu=None) -> None:
        """Konca omrezni proces Spleta; piskotke seje (brez roka, samo v pomnilniku procesa) prej prebere in jih po
        zagonu novega procesa vrne - uporabnik ostane prijavljen. ob_koncu(stevilo_vrnjenih) za preizkuse."""
        s = self._splet()
        if s is None:
            return
        self._recikliranje = True
        upr = s.seja.get_cookie_manager()

        def vrni(seje, rok):
            if os.path.exists("/proc/%d" % pid) and time.monotonic() < rok:
                return True       # WebKit mora najprej opaziti konec procesa, sicer gre piskotek v stari proces
            for c in seje:
                try:
                    upr.add_cookie(c, None, None, None)
                except Exception:  # noqa: BLE001
                    pass
            self._recikliranje = False
            if ob_koncu is not None:
                ob_koncu(len(seje))
            return False

        def ob_piskotkih(_u, rezultat, *_):
            try:
                vsi = upr.get_all_cookies_finish(rezultat) or []
            except Exception:  # noqa: BLE001
                vsi = []
            seje = [c for c in vsi if c.get_expires() is None]
            # Ponovni pregled OpenAI 1.0.129 (C): med branjem piskotkov je lupa lahko odprla skrit pogled ali se je
            # zagnala vdelana aplikacija - pred koncem procesa vse pogoje preverimo znova.
            if not _sme_koncati_omrezni(s):
                self._recikliranje = False
                return
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                self._recikliranje = False
                return
            print("[Splet] omrezni proces (%.0f MiB) obnovljen med mirovanjem okna; piskotkov seje: %d"
                  % (velikost, len(seje)), flush=True)
            rok = time.monotonic() + 5.0
            self.GLib.timeout_add(200, lambda: vrni(seje, rok))
        try:
            upr.get_all_cookies(None, ob_piskotkih, None)
        except Exception:  # noqa: BLE001 - starejsi WebKit brez get_all_cookies: konec kot v GTK3
            ob_piskotkih(None, None)

    # ------------------------------------------------------------------ stran procesov
    def vrstice(self, skriti=()) -> list:
        s = self._splet()
        if s is None:
            return []
        vzorci = getattr(self, "vzorci", {})
        zgodovina = poraba_zgodovina.skupna()
        izid = []
        for ident, p, z in self._pogledi(s):
            if ident in skriti:
                continue
            v = vzorci.get(ident)
            pid = self.nadzor.pid_of(ident)
            if z is None:
                aplikacija = s.aplikacije.get(p)
                naslov = (p.get_title() or "") if p is not None else ""
                if not naslov and aplikacija is not None:
                    naslov = urllib.parse.urlsplit(getattr(aplikacija, "naslov", "") or "").hostname or ""
                stanje = {"app": True}
            else:
                stanje = self._stanje(z)
                naslov = z["spanje"].get("naslov") if z["spanje"]["spi"] else (p.get_title() or stanje.get("uri") or "")
            vrstica = {
                "id": ident, "title": naslov, "pid": pid if v is not None and v.pid else 0,
                "cpu": v.cpu if v else 0.0, "rss_mb": v.rss_mb if v else 0, "threads": v.threads if v else 0,
                "active": bool(stanje.get("active")), "audio": bool(stanje.get("audio")),
                "sleeping": bool(stanje.get("sleeping")), "verdict": v.verdict if v else "calm",
                "app": bool(stanje.get("app")), "reasons": razlogi_zascite(stanje),
            }
            ura = _zadnja_ura(zgodovina, vrstica["pid"])
            ura.pop("cpu_zadnji", None)        # zavihek ima trenutni CPU iz nadzora (vsaki 2 s)
            vrstica.update(ura)
            izid.append(vrstica)
        return izid

    def _naslovi_drugih(self) -> dict:
        """PID -> naslov zavihka iz drugih Spletov v procesu (Safeer OS: okno in plosca na namizju)."""
        izid = {}
        for drugi in list(_PRIMERKI):
            if drugi is self:
                continue
            s = drugi._splet()
            if s is None:
                continue
            for z in list(s.zavihki):
                st = z.get("spanje")
                pid = drugi.nadzor.pid_of(st["id"]) if st else 0
                if pid:
                    try:
                        izid[pid] = z["pogled"].get_title() or z["pogled"].get_uri() or ""
                    except Exception:  # noqa: BLE001
                        pass
        return izid

    def sistem(self, vrstice: list) -> list:
        """Vsi procesi programa za stran: glavni, omrezni, spletni (zavihki tega okna v eni vrstici, podrobno so zgoraj),
        podprocesi (rqbit, ffmpeg - s storitvijo, ki ji pripadajo) in peskovnik WebKita v eni vrstici. Trenutni CPU je
        od prejsnje osvezitve strani (3 s), ob prvem odprtju zadnji interval zgodovine."""
        zgodovina = poraba_zgodovina.skupna()
        koren = zgodovina.koren
        zavihki = {r["pid"] for r in vrstice if r.get("pid")}
        drugi = self._naslovi_drugih()
        storitve = {}
        for st in storitve_na_zahtevo.stanje():
            for pid in st.get("pidi") or ():
                storitve[pid] = st["ime"]
        skupine: dict = {}
        izid = []
        branja = {}
        for pid in [koren] + poraba_zgodovina.potomci(koren):
            b = poraba_zgodovina.trenutno(pid, self._branja.get(pid))
            if b is None:
                continue
            branja[pid] = b["branje"]
            zadnja = _zadnja_ura(zgodovina, pid)
            cpu = b["cpu"] if b["cpu"] is not None else zadnja.pop("cpu_zadnji", None)
            zadnja.pop("cpu_zadnji", None)
            vrsta = poraba_zgodovina.vrsta(b["ime"], pid, koren)
            vrstica = dict(zadnja, pid=pid, name=b["ime"], kind=vrsta, cpu=cpu, rss_mb=b["rss_mb"], threads=b["niti"])
            if vrsta == poraba_zgodovina.SPLETNI and pid in zavihki:
                vrstica["kind"] = "zavihki"
            if vrstica["kind"] in ("zavihki", poraba_zgodovina.PESKOVNIK):
                sk = skupine.setdefault(vrstica["kind"], {"kind": vrstica["kind"], "count": 0, "threads": 0,
                                                          "cpu": None, "rss_mb": 0, "avg_cpu": None, "avg_mb": None})
                sk["count"] += 1
                sk["threads"] += vrstica["threads"]
                sk["rss_mb"] += vrstica["rss_mb"]
                for k in ("cpu", "avg_cpu", "avg_mb"):
                    if vrstica.get(k) is not None:
                        sk[k] = (sk[k] or 0) + vrstica[k]
                continue
            if pid in drugi:
                vrstica["tab"] = drugi[pid]
            if pid in storitve:
                vrstica["service"] = storitve[pid]
            izid.append(vrstica)
        self._branja = branja
        return izid + list(skupine.values())

    def stran_procesov(self, skriti=()) -> str:
        s = self._splet()
        jezik = str((s.jezik() if callable(s.jezik) else s.jezik) or "en")[:2] if s is not None else "en"
        minute = 0
        if s is not None:
            try:
                minute = max(0, int(float(s.config.get("tab_discard_after_s", 600) or 0) // 60))
            except (TypeError, ValueError):
                minute = 0
        vrstice = self.vrstice(skriti)
        try:
            sistem = self.sistem(vrstice)
        except Exception as napaka:  # noqa: BLE001 - zavihki se pokazejo tudi brez tabele programa
            print("[Splet] procesi programa:", napaka, flush=True)
            sistem = []
        storitve = storitve_na_zahtevo.stanje()
        zdaj = time.time()
        storitve += [{"ime": o["ime"], "opravilo": True, "razmik_s": o["razmik_s"], "tece": o["tece"],
                      "zadnje_s": (zdaj - o["zadnje"]) if o["zadnje"] else None}
                     for o in storitve_na_zahtevo.opravila()]
        return processes_page.render(vrstice, jezik, pomnilnik.meja_strani_mb(), self.nadzor.cpu_budget,
                                     key=self._kljuc, sleep_minutes=minute, system=sistem, services=storitve,
                                     app=storitve_na_zahtevo.ime_procesa() or "Safeer Browser",
                                     sample_s=storitve_na_zahtevo.TIK_S,
                                     history_ready=poraba_zgodovina.skupna().ima_vzorce())


def _zadnja_ura(zgodovina, pid: int) -> dict:
    """Povprecje in vrh zadnje ure za vrstico strani (kljuci processes_page) ali prazno brez zgodovine."""
    p = zgodovina.povzetek(pid) if pid else None
    if p is None:
        return {}
    return {"avg_cpu": p["cpu_povp"], "peak_cpu": p["cpu_vrh"], "avg_mb": p["rss_povp_mb"], "peak_mb": p["rss_vrh_mb"],
            "cpu_zadnji": p["cpu_zadnji"]}


def _pogled_prenosa(prenos):
    try:
        return prenos.get_web_view() if prenos is not None else None
    except Exception:  # noqa: BLE001
        return None


def _opis(v) -> str:
    from core.tab_monitor import describe
    return describe(v)
