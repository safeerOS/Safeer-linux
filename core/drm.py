"""Zasciten video (Widevine) v Safeer Browserju in Spletu Safeer OS.

WebKitGTK komponente Widevine ne zna naloziti, Google pa jo dovoli le brskalnikom s pogodbo (Chrome, Brave, Edge ...).
Lastnik, 11. 10. 2026: stran, ki zahteva Widevine (Netflix, Disney+, Max ...), se samodejno odpre v namescenem
brskalniku, ki ga ima (npr. Brave); vse ostalo ostane v Safeerju. Komponente ne vgrajujemo in ne prenasamo.

Zaznava: skripta na strani ovije navigator.requestMediaKeySystemAccess - ko stran zaprosi za Widevine ali PlayReady,
o tem obvesti Safeer (rokovalnik »safeerDrm«). Safeer ne izve nicesar drugega o strani.
"""
import weakref
import os
import shutil
import subprocess
import time
import urllib.parse
from typing import Callable, List, Optional, Tuple


def _izvedi_js(pogled, koda: str) -> None:
    """JavaScript v strani: WebKitGTK 6.0 (GTK4) ima samo evaluate_javascript, starejsi 4.1 run_javascript."""
    if hasattr(pogled, "evaluate_javascript"):
        pogled.evaluate_javascript(koda, -1, None, None, None, None, None)
    else:
        pogled.run_javascript(koda, None, None, None)


MOST = "safeerDrm"

SKRIPTA = r"""
(function () {
  try {
    var n = navigator;
    if (n.__safeerDrm) return;
    n.__safeerDrm = true;
    var izvirna = n.requestMediaKeySystemAccess;
    function javi(sistem) {
      try {
        if (/widevine|playready|com\.apple\.fps|fairplay|^safeer:/i.test(String(sistem || "")) && window.webkit && window.webkit.messageHandlers &&
            window.webkit.messageHandlers.safeerDrm) {
          window.webkit.messageHandlers.safeerDrm.postMessage(String(sistem));
        }
      } catch (e) {}
    }
    // WebKitGTK na namizju EME pogosto sploh nima (funkcija ne obstaja): stran bi brez klica le javila »brskalnik ni
    // podprt«. Zato jo ponudimo - ob klicu Safeer stran odpre drugje, stran pa dobi obicajno zavrnitev.
    // Brez EME v WebKitGTK manjkajo tudi razredi: nekateri predvajalniki (Vimeo) po tem sklepajo, da DRM ni, in
    // requestMediaKeySystemAccess sploh ne poklicejo. Prazni razredi jih pripeljejo do klica (in s tem do Safeer DRM).
    if (!izvirna) {
      try {
        var Ni = function () { throw new TypeError("Illegal constructor"); };
        ["MediaKeys", "MediaKeySession", "MediaKeySystemAccess", "MediaKeyMessageEvent", "MediaEncryptedEvent"]
          .forEach(function (ime) { if (typeof window[ime] === "undefined") window[ime] = Ni; });
        var P = window.HTMLMediaElement && HTMLMediaElement.prototype;
        if (P && !("setMediaKeys" in P)) {
          P.setMediaKeys = function () { return Promise.reject(new DOMException("Not supported", "NotSupportedError")); };
          Object.defineProperty(P, "mediaKeys", { get: function () { return null; }, configurable: true });
        }
      } catch (e) {}
    }
    // WebKitGTK se strani predstavi kot Safari: predvajalniki (Vimeo) zato izberejo FairPlay prek starega
    // WebKitMediaKeys. Tega v WebKitGTK ni - prazen razred javi zahtevo za zascito, stran pa dobi »ni podprto«.
    if (typeof window.WebKitMediaKeys === "undefined") {
      try {
        var Wmk = function (sistem) { javi(sistem || "com.apple.fps"); throw new DOMException("Not supported", "NotSupportedError"); };
        Wmk.isTypeSupported = function (sistem) { window.__safeerEmeKlici = (window.__safeerEmeKlici || 0) + 1; javi(sistem); return false; };
        window.WebKitMediaKeys = Wmk;
      } catch (e) {}
    }
    // Splosna zaznava (tudi ce predvajalnik EME sploh ne poklice, npr. Vimeo z zapomnjeno odlocitvijo): video, ki naj
    // bi tekel (ni ustavljen, ima vir), pa 6 s nima niti ene slike, ali video z napako zapisa/dekodiranja. Tak video
    // v WebKitGTK ne bo stekel (zasciten ali zapis brez dekoderja) - Safeer DRM (Chromium) ga predvaja.
    {
      var zastoj = new WeakMap();
      setInterval(function () {
        try {
          var m = document.querySelectorAll("video");
          for (var i = 0; i < m.length; i++) {
            var v = m[i];
            if (v.error && (v.error.code === 3 || v.error.code === 4)) { javi("safeer:zapis"); return; }
            var tece = !v.paused && !v.ended && (v.currentSrc || v.src) && v.readyState < 2;
            var k = tece ? (zastoj.get(v) || 0) + 1 : 0;
            zastoj.set(v, k);
            if (k >= 3) { javi("safeer:zastoj"); zastoj.set(v, -1000); return; }
          }
        } catch (e) {}
      }, 2000);
    }
    n.requestMediaKeySystemAccess = function (sistem) {
      window.__safeerEmeKlici = (window.__safeerEmeKlici || 0) + 1;
      javi(sistem);
      if (izvirna) return izvirna.apply(this, arguments);
      return Promise.reject(new DOMException("Key system not supported", "NotSupportedError"));
    };
  } catch (e) {}
})();
"""

# Obvestilo na strani (brez dostopa do strani: samo pasica, ki izgine).
OBVESTILO = r"""
(function (besedilo) {
  try {
    var d = document.createElement("div");
    d.textContent = besedilo;
    d.setAttribute("role", "status");
    d.style.cssText = "position:fixed;left:50%;top:18px;transform:translateX(-50%);z-index:2147483647;" +
      "background:#101a2b;color:#eaf2ff;border:1px solid #8ac7ff;border-radius:12px;padding:12px 18px;" +
      "font:15px system-ui,sans-serif;box-shadow:0 10px 30px rgba(0,0,0,.45);max-width:80vw";
    (document.body || document.documentElement).appendChild(d);
    setTimeout(function () { d.remove(); }, 9000);
  } catch (e) {}
})(__BESEDILO__);
"""

# Brskalniki z Widevine po vrsti: najprej zasebni (Brave), nato drugi Chromium. Flatpak tudi.
_KANDIDATI: List[Tuple[str, List[str]]] = [
    ("Brave", ["brave-browser"]), ("Brave", ["brave"]),
    ("Google Chrome", ["google-chrome-stable"]), ("Google Chrome", ["google-chrome"]),
    ("Chromium", ["chromium"]), ("Chromium", ["chromium-browser"]),
    ("Microsoft Edge", ["microsoft-edge"]), ("Vivaldi", ["vivaldi"]), ("Opera", ["opera"]),
]
_FLATPAK = [("Brave", "com.brave.Browser"), ("Google Chrome", "com.google.Chrome"),
            ("Chromium", "org.chromium.Chromium"), ("Microsoft Edge", "com.microsoft.Edge")]


def najdi_brskalnik(which=shutil.which, flatpak_ima: Optional[Callable[[str], bool]] = None) -> Optional[Tuple[str, List[str]]]:
    """(ime, ukaz) prvega namescenega brskalnika z Widevine, ali None."""
    for ime, ukaz in _KANDIDATI:
        if which(ukaz[0]):
            return ime, ukaz
    if flatpak_ima is None:
        def flatpak_ima(app: str) -> bool:
            for koren in (os.path.expanduser("~/.local/share/flatpak/app"), "/var/lib/flatpak/app"):
                if os.path.isdir(os.path.join(koren, app)):
                    return True
            return False
    if which("flatpak"):
        for ime, app in _FLATPAK:
            if flatpak_ima(app):
                return ime, ["flatpak", "run", app]
    return None


def primeren_naslov(url: str) -> bool:
    try:
        d = urllib.parse.urlsplit(str(url or ""))
    except ValueError:
        return False
    return d.scheme == "https" and bool(d.hostname)


class Preusmeritev:
    """Ena preusmeritev na stran (stran za Widevine pogosto vprasa veckrat zapored)."""

    def __init__(self, najdi=najdi_brskalnik, zazeni=None, ura=time.monotonic):
        self._najdi, self._ura = najdi, ura
        self._zazeni = zazeni or (lambda ukaz: subprocess.Popen(ukaz, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                                                 stdin=subprocess.DEVNULL, start_new_session=True))
        self._zadnje: dict = {}

    def odpri(self, url: str) -> Tuple[str, str]:
        """Vrne (izid, ime brskalnika): izid »odprto«, »ze« (ta stran je bila pravkar odprta), »ni« (ni brskalnika)
        ali »neveljavno«."""
        if not primeren_naslov(url):
            return "neveljavno", ""
        gostitelj = urllib.parse.urlsplit(url).hostname or ""
        zdaj = self._ura()
        if zdaj - self._zadnje.get(gostitelj, -1e9) < 30:
            return "ze", ""
        najden = self._najdi()
        if not najden:
            self._zadnje[gostitelj] = zdaj
            return "ni", ""
        ime, ukaz = najden
        try:
            self._zazeni(ukaz + [url])
        except OSError:
            return "ni", ""
        self._zadnje[gostitelj] = zdaj
        return "odprto", ime


def besedilo_obvestila(izid: str, ime: str, jezik: str = "sl") -> str:
    sl = jezik.startswith("sl")
    if izid == "odprto":
        return ("Ta stran potrebuje Widevine (zaščiten video), zato je odprta v brskalniku %s." if sl else
                "This page needs Widevine (protected video), so it was opened in %s.") % ime
    return ("Ta stran potrebuje Widevine (zaščiten video). Namesti brskalnik, ki ga podpira (npr. Brave)." if sl else
            "This page needs Widevine (protected video). Install a browser that supports it (e.g. Brave).")


def _vsebina(rezultat) -> str:
    """Besedilo sporocila skripte (WebKit2 4.1 JavascriptResult ali JSC.Value)."""
    try:
        vrednost = rezultat.get_js_value() if hasattr(rezultat, "get_js_value") else rezultat
        return str(vrednost.to_string() or "")
    except Exception:  # noqa: BLE001
        return ""


def prikljuci(WebKit2, pogled, preusmeritev: Preusmeritev, jezik: Callable[[], str],
              vdelaj: Optional[Callable[[object, str], bool]] = None) -> None:
    """Skripta in rokovalnik na pogledu WebKit: ob zahtevi za Widevine stran predvaja Safeer DRM v istem zavihku
    (vdelaj, Splet Safeer OS); ce tega ni ali ne gre, jo odpre v namescenem brskalniku z Widevine."""
    upravitelj = pogled.get_user_content_manager()
    try:
        upravitelj.register_script_message_handler(MOST, None)   # WebKitGTK 6.0 (GTK4): (ime, svet)
    except TypeError:
        upravitelj.register_script_message_handler(MOST)         # WebKit2GTK 4.1 (Safeer Browser, GTK3)
    # Sibka referenca: rokovalnik zivi na upravitelju vsebine, ki ga drzi pogled. Mocna referenca bi naredila krog
    # med C in Pythonom, ki ga zbiralnik ne vidi - zaprt zavihek (WebView) se ne bi nikoli sprostil (12. 10. 2026:
    # 30 zaprtih zavihkov = 30 zivih WebView, +68 MiB).
    ref = weakref.ref(pogled)

    def ob_sporocilu(_u, _r):
        pogled = ref()
        if pogled is None:
            return
        url = pogled.get_uri() or ""
        if vdelaj is not None:
            try:
                if vdelaj(pogled, url):
                    return
            except Exception as e:  # noqa: BLE001 - rezerva: drug brskalnik
                print("[SafeerDRM] vdelava:", e, flush=True)
        if _vsebina(_r).startswith("safeer:"):
            return      # samo sum (zastoj videa): drugega brskalnika zaradi tega ne odpiramo
        izid, ime = preusmeritev.odpri(url)
        if izid in ("odprto", "ni"):
            import json
            koda = OBVESTILO.replace("__BESEDILO__", json.dumps(besedilo_obvestila(izid, ime, jezik() or "sl")))
            try:
                pogled.evaluate_javascript(koda, -1, None, None, None, None, None)
            except Exception:  # noqa: BLE001 - starejsi WebKitGTK
                try:
                    _izvedi_js(pogled, koda)
                except Exception:  # noqa: BLE001
                    pass
    upravitelj.connect("script-message-received::" + MOST, ob_sporocilu)
    upravitelj.add_script(WebKit2.UserScript(SKRIPTA, WebKit2.UserContentInjectedFrames.ALL_FRAMES,
                                             WebKit2.UserScriptInjectionTime.START, None, None))
