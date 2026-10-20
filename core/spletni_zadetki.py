"""Sprotni zadetki spleta v lupi namizja (lastnik, 20. 10. 2026: »bilo bi dobro, da bi ze sproti pokazalo top
rezultate iskanja«).

Strani rezultatov ne strgamo z urllib: DuckDuckGo html po dveh hitrih zahtevah z istega naslova vrne 202 (zavrne
robota, izmerjeno 20. 10. 2026), Google brez brskalnika pokaze soglasje. Zato stran rezultatov iskalnika, ki ga je
uporabnik izbral (Splet: search_engine), nalozi skrit pogled WebKit v ISTI seji kot Splet (piskotki, soglasje, DoH
posrednik, Scit), kot bi jo uporabnik sam - in iz nje v locenem svetu JavaScripta prebere prve zadetke (brez oglasov).
Izmerjeno na prenosniku lastnika: Google, DuckDuckGo, Bing - 5 zadetkov v 1,2-1,8 s, slike izklopljene.

En pogled, ena zahteva naenkrat (novejsa prekine starejso), predpomnilnik 10 min, po minuti brez iskanja se pogled
zapre (spletni proces vrne pomnilnik). Naslovi so samo http(s); naslov in odlomek sta besedilo (nikoli HTML).
"""
from __future__ import annotations

import json
import time
import urllib.parse
from typing import Callable, Dict, List, Optional, Tuple

#: Najvec zadetkov v lupi.
NAJVEC = 3
#: Rok za celo iskanje (s): pozneje lupa ostane brez sprotnih zadetkov (Enter vseeno odpre iskanje).
ROK_S = 6.0
#: Po nalaganju se zadetki lahko pojavijo sele z JavaScriptom strani (DuckDuckGo): toliko poskusov po 250 ms.
POSKUSOV = 12
#: Pogled se zapre po toliko sekundah brez iskanja.
ZAPRI_PO_S = 60
PREDPOMNILNIK_S = 600
PREDPOMNILNIK_NAJVEC = 40
SVET = "safeer-zadetki"

#: Iskalniki (core/config.SEARCH_ENGINES in safeer_os.ISKALNIKI) -> ime za izvlecni skript.
MOTORJI = (("google.", "google"), ("duckduckgo.", "duckduckgo"), ("bing.", "bing"), ("brave.", "brave"),
           ("ecosia.", "ecosia"), ("startpage.", "startpage"))

# Izbirniki iz dejanskih strani (20. 10. 2026). textContent, ne innerText: skrit pogled strani ne izrise.
IZVLECI_JS = r"""
(function (motor) {
  var izid = [], videno = {};
  function besedilo(e) { return e ? String(e.textContent || "").replace(/\s+/g, " ").trim() : ""; }
  function dodaj(a, naslov, odlomek, prikaz) {
    if (!a || !a.href || izid.length >= 8) return;
    var u = String(a.href);
    if (!/^https?:\/\//i.test(u) || videno[u]) return;
    var t = besedilo(naslov);
    if (!t) return;
    videno[u] = 1;
    izid.push({ t: t.slice(0, 200), u: u.slice(0, 2000), s: besedilo(odlomek).slice(0, 300), p: besedilo(prikaz).slice(0, 200) });
  }
  function vsi(sel, kor) { Array.prototype.forEach.call(document.querySelectorAll(sel), kor); }
  if (motor === "google") {
    vsi("#rso a h3, #search a h3", function (h) {
      var a = h.closest("a");
      if (!a || a.closest("#tads, #bottomads, [data-text-ad], [aria-label='Ads'], [aria-label='Oglasi']")) return;
      var blok = a.closest(".MjjYud, .g, [data-hveid]");
      dodaj(a, h, blok && blok.querySelector(".VwiC3b, [data-sncf], [style*='-webkit-line-clamp']"), blok && blok.querySelector("cite"));
    });
  } else if (motor === "duckduckgo") {
    vsi("article[data-testid='result']", function (r) {
      if (r.closest("[data-testid='ad']") || r.querySelector("[data-testid='ad-badge']")) return;
      var a = r.querySelector("a[data-testid='result-title-a']");
      dodaj(a, a, r.querySelector("[data-result='snippet']"), null);
    });
  } else if (motor === "bing") {
    vsi("#b_results > li.b_algo", function (r) { var a = r.querySelector("h2 a"); dodaj(a, a, r.querySelector(".b_caption p, p"), r.querySelector("cite")); });
  } else if (motor === "brave") {
    vsi("#results .snippet[data-type='web']", function (r) { var a = r.querySelector("a"); dodaj(a, r.querySelector(".title") || a, r.querySelector(".snippet-description, .generic-snippet"), r.querySelector("cite, .netloc")); });
  } else if (motor === "ecosia") {
    vsi("[data-test-id='mainline-result-web']", function (r) {
      var a = r.querySelector("a[data-test-id='result-link']") || r.querySelector("a");
      dodaj(a, r.querySelector("[data-test-id='result-title']") || a, r.querySelector("[data-test-id='web-result-description']"), null);
    });
  } else if (motor === "startpage") {
    vsi(".w-gl .result, .result", function (r) { var a = r.querySelector("a.result-title, a.result-link"); dodaj(a, r.querySelector("h2, .wgl-title") || a, r.querySelector("p.description"), null); });
  }
  return JSON.stringify(izid);
})(%s)
"""


def motor_za(url: str) -> str:
    """Ime iskalnika iz naslova strani rezultatov ('' = neznan: brez sprotnih zadetkov)."""
    gost = (urllib.parse.urlsplit(url).hostname or "").lower()
    for del_, ime in MOTORJI:
        if del_ in gost:
            return ime
    return ""


def gostitelj(url: str, prikaz: str = "") -> str:
    """Kaj pokazemo pod naslovom: ime strani. Google in Bing dajo povezavo prek sebe (/goto, /ck/a), pravo stran
    pove prikazani naslov (cite: »https://vreme.arso.gov.si › napoved«)."""
    for kandidat in (prikaz.split(" ")[0] if prikaz else "", url):
        k = kandidat.strip()
        if not k:
            continue
        if "://" not in k:
            k = "https://" + k
        g = (urllib.parse.urlsplit(k).hostname or "").lower()
        if g and "." in g and not g.startswith(("google.", "www.google.", "www.bing.", "bing.")):
            return g[4:] if g.startswith("www.") else g
    return ""


def ocisti(surovo, najvec: int = NAJVEC) -> List[dict]:
    """Zadetki iz strani (podatki tuje strani!) -> varen seznam {naslov, url, stran, odlomek}."""
    izid: List[dict] = []
    if not isinstance(surovo, list):
        return izid
    videno = set()
    for z in surovo:
        if not isinstance(z, dict):
            continue
        u, t = str(z.get("u") or ""), " ".join(str(z.get("t") or "").split())
        deli = urllib.parse.urlsplit(u)
        if deli.scheme not in ("http", "https") or not deli.hostname or not t or len(u) > 2000 or u in videno:
            continue
        videno.add(u)
        izid.append({"naslov": t[:200], "url": u, "stran": gostitelj(u, str(z.get("p") or "")),
                     "odlomek": " ".join(str(z.get("s") or "").split())[:300]})
        if len(izid) >= najvec:
            break
    return izid


def isti_niz(zahtevan: str, stran: str) -> bool:
    """Ali je stran v pogledu za iskani niz (parameter q, kjer ga imata oba; sicer ne vemo - True)."""
    def q(url: str) -> Optional[str]:
        try:
            v = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("q")
        except Exception:  # noqa: BLE001
            return None
        return " ".join(v[0].split()).lower() if v else None
    a, b = q(zahtevan), q(stran)
    return a is None or b is None or a == b


class PredogledIskanja:
    """Skrit pogled WebKit, ki nalozi stran rezultatov in vrne prve zadetke (glej opis modula)."""

    def __init__(self, Gtk, WebKit, GLib, seja=None, kontekst=None, zdaj: Callable[[], float] = time.monotonic,
                 pripravi: Optional[Callable] = None, pozabi: Optional[Callable] = None):
        """pripravi/pozabi: Splet (os_splet.VdelaniSplet.pripravi_skriti_pogled) da pogledu iste zascite kot zavihku
        in ve, da pogled zivi (omreznega procesa takrat ne konca)."""
        self.Gtk, self.WebKit, self.GLib = Gtk, WebKit, GLib
        self.seja, self.kontekst = seja, kontekst
        self._pripravi, self._pozabi = pripravi, pozabi
        self.zdaj = zdaj
        self.pogled = None
        self.okno = None
        self._povratni: Optional[Callable[[List[dict]], None]] = None
        self._url = ""
        self._rod = 0
        self._rok = 0
        self._zapri = 0
        self._shramba: Dict[str, Tuple[float, List[dict]]] = {}

    # ------------------------------------------------------------------ javno
    def isci(self, url: str, povratni: Callable[[List[dict]], None], motor: str = "") -> None:
        """motor: ime izvlecnega pravila (privzeto iz naslova; preizkusi z lokalnim streznikom ga podajo)."""
        motor = motor or motor_za(url)
        if not motor:
            povratni([])
            return
        v = self._shramba.get(url)
        if v and self.zdaj() - v[0] < PREDPOMNILNIK_S:
            povratni(list(v[1]))
            return
        self._koncaj([])                 # starejse iskanje dobi prazen odgovor, lupa ga tako ali tako zavrze
        self._rod += 1
        self._url, self._motor, self._povratni = url, motor, povratni
        pogled = self._pogled()
        rod = self._rod
        self._rok = self.GLib.timeout_add(int(ROK_S * 1000), lambda: (self._rok_potekel(rod), False)[1])
        self._odlozi_zapiranje()
        pogled.load_uri(url)

    def zapri(self) -> None:
        self._koncaj([])
        if self._zapri:
            self.GLib.source_remove(self._zapri)
            self._zapri = 0
        p, o = self.pogled, self.okno
        self.pogled = self.okno = None
        if p is not None and self._pozabi is not None:
            try:
                self._pozabi(p)
            except Exception:  # noqa: BLE001
                pass
        try:
            if o is not None:
                o.set_child(None)              # najprej iz okna, sicer GTK ob dispose opozori (Gtk-CRITICAL)
            if p is not None:
                p.stop_loading()
                p.run_dispose()
            if o is not None:
                o.destroy()
        except Exception:  # noqa: BLE001
            pass
        return False

    # ------------------------------------------------------------------ notranje
    def _pogled(self):
        if self.pogled is not None:
            return self.pogled
        W = self.WebKit
        lastnosti = {}
        if self.seja is not None:
            lastnosti["network_session"] = self.seja
        if self.kontekst is not None:
            lastnosti["web_context"] = self.kontekst
        p = W.WebView(**lastnosti)
        n = p.get_settings()
        for ime, vrednost in (("auto_load_images", False), ("enable_media", False),
                              ("media_playback_requires_user_gesture", True), ("enable_webaudio", False),
                              ("enable_webgl", False), ("enable_webrtc", False), ("enable_html5_database", False),
                              ("javascript_can_open_windows_automatically", False)):
            nastavi = getattr(n, "set_" + ime, None)
            if nastavi is not None:
                try:
                    nastavi(vrednost)
                except Exception:  # noqa: BLE001
                    pass
        p.connect("load-changed", self._nalozeno)
        p.connect("load-failed", self._napaka)
        p.connect("create", lambda *_a: None)             # stran ne odpre novih oken
        p.connect("permission-request", lambda _p, z: (z.deny(), True)[1])
        if self._pripravi is not None:
            self._pripravi(p)                              # Scit: EasyList, sledilci, GPC/DNT, zasebnost
        # Okno se nikoli ne prikaze: pogled potrebuje starsa, da WebKit nalaga in izvaja skripte.
        self.okno = self.Gtk.Window()
        self.okno.set_child(p)
        self.pogled = p
        return p

    def _odlozi_zapiranje(self) -> None:
        if self._zapri:
            self.GLib.source_remove(self._zapri)
        self._zapri = self.GLib.timeout_add_seconds(ZAPRI_PO_S, self._zapri_ob_mirovanju)

    def _zapri_ob_mirovanju(self) -> bool:
        self._zapri = 0
        self.zapri()
        return False

    def _nalozeno(self, pogled, dogodek) -> None:
        # Webmaster pregled pomocnika 1.0.129: ob novem nizu WebKit prekine staro nalaganje in TAKOJ javi FINISHED
        # (tudi po load-failed CANCELLED) - takrat je v pogledu se stran PREJSNJEGA niza in njeni zadetki bi se
        # pokazali (in 10 min ostali v predpomnilniku) pod novim nizom. Beremo sele po COMMITTED nalaganja tega iskanja.
        # OpenAI pregled 1.0.129 (E): zakasnjen COMMITTED prejsnjega niza ne sme potrditi novega iskanja.
        # Ponovni pregled F: potrdi samo nalaganje, ki se je ZACELO po tem iskanju (STARTED za tem rodom) - tudi stran
        # brez parametra q (preusmeritev, soglasje) prejsnjega niza ga ne more potrditi.
        if dogodek == self.WebKit.LoadEvent.STARTED:
            self._zacet = self._rod
        elif dogodek == self.WebKit.LoadEvent.COMMITTED:
            if getattr(self, "_zacet", 0) == self._rod and \
                    isti_niz(self._url, (pogled.get_uri() if pogled is not None else "") or ""):
                self._potrjen = self._rod
        elif dogodek == self.WebKit.LoadEvent.FINISHED and self._povratni is not None \
                and getattr(self, "_potrjen", 0) == self._rod:
            self._preberi(self._rod, 0)

    def _napaka(self, _p, _d, uri, napaka) -> bool:
        # Prekinjeno starejse nalaganje (nova crka) javi napako s SVOJIM naslovom - ne sme koncati novejsega iskanja.
        if self._povratni is not None and uri == self._url and not napaka.matches(
                self.WebKit.network_error_quark(), self.WebKit.NetworkError.CANCELLED):
            self._koncaj([])
        return True

    def _preberi(self, rod: int, poskus: int) -> None:
        if rod != self._rod or self.pogled is None:
            return
        js = IZVLECI_JS % json.dumps(self._motor)

        def konec(pogled, rezultat):
            if rod != self._rod:
                return
            try:
                surovo = json.loads(pogled.evaluate_javascript_finish(rezultat).to_string())
            except Exception:  # noqa: BLE001
                surovo = []
            zadetki = ocisti(surovo)
            if not isti_niz(self._url, pogled.get_uri() or ""):
                zadetki = []                               # v pogledu je stran drugega niza: ne kazi in ne shrani
            if zadetki or poskus >= POSKUSOV:
                self._shrani(self._url, zadetki)
                self._koncaj(zadetki)
            else:
                self.GLib.timeout_add(250, lambda: (self._preberi(rod, poskus + 1), False)[1])
        try:
            self.pogled.evaluate_javascript(js, -1, SVET, None, None, konec)
        except Exception:  # noqa: BLE001
            self._koncaj([])

    def _shrani(self, url: str, zadetki: List[dict]) -> None:
        if not zadetki:
            return
        if len(self._shramba) >= PREDPOMNILNIK_NAJVEC:
            for k in sorted(self._shramba, key=lambda k: self._shramba[k][0])[:PREDPOMNILNIK_NAJVEC // 4]:
                del self._shramba[k]
        self._shramba[url] = (self.zdaj(), list(zadetki))

    def _rok_potekel(self, rod: int) -> None:
        if rod == self._rod:
            self._rok = 0
            self._koncaj([])
            if self.pogled is not None:
                self.pogled.stop_loading()

    def _koncaj(self, zadetki: List[dict]) -> None:
        povratni, self._povratni = self._povratni, None
        if self._rok:
            self.GLib.source_remove(self._rok)
            self._rok = 0
        if povratni is not None:
            try:
                povratni(zadetki)
            except Exception as e:  # noqa: BLE001
                print("[Lupa] sprotni zadetki:", e, flush=True)
