"""Zasciten video (Widevine) v Safeer Browserju in Spletu Safeer OS.

WebKitGTK komponente Widevine ne zna naloziti, Google pa jo dovoli le brskalnikom s pogodbo (Chrome, Brave, Edge ...).
Lastnik, 11. 10. 2026: stran, ki zahteva Widevine (Netflix, Disney+, Max ...), se samodejno odpre v namescenem
brskalniku, ki ga ima (npr. Brave); vse ostalo ostane v Safeerju. Komponente ne vgrajujemo in ne prenasamo.

Zaznava: skripta na strani ovije navigator.requestMediaKeySystemAccess - ko stran zaprosi za Widevine ali PlayReady,
o tem obvesti Safeer (rokovalnik »safeerDrm«). Safeer ne izve nicesar drugega o strani.
"""
import os
import shutil
import subprocess
import time
import urllib.parse
from typing import Callable, List, Optional, Tuple

MOST = "safeerDrm"

SKRIPTA = r"""
(function () {
  try {
    var n = navigator, izvirna = n.requestMediaKeySystemAccess;
    if (!izvirna || n.__safeerDrm) return;
    n.__safeerDrm = true;
    n.requestMediaKeySystemAccess = function (sistem) {
      try {
        if (/widevine|playready/i.test(String(sistem || "")) && window.webkit && window.webkit.messageHandlers &&
            window.webkit.messageHandlers.safeerDrm) {
          window.webkit.messageHandlers.safeerDrm.postMessage(String(sistem));
        }
      } catch (e) {}
      return izvirna.apply(this, arguments);
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
})(%s);
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


def prikljuci(WebKit2, pogled, preusmeritev: Preusmeritev, jezik: Callable[[], str]) -> None:
    """Skripta in rokovalnik na pogledu WebKit: ob zahtevi za Widevine stran odpre v brskalniku z Widevine."""
    upravitelj = pogled.get_user_content_manager()
    upravitelj.register_script_message_handler(MOST)

    def ob_sporocilu(_u, _r):
        url = pogled.get_uri() or ""
        izid, ime = preusmeritev.odpri(url)
        if izid in ("odprto", "ni"):
            import json
            koda = OBVESTILO % json.dumps(besedilo_obvestila(izid, ime, jezik() or "sl"))
            try:
                pogled.evaluate_javascript(koda, -1, None, None, None, None, None)
            except Exception:  # noqa: BLE001 - starejsi WebKitGTK
                try:
                    pogled.run_javascript(koda, None, None, None)
                except Exception:  # noqa: BLE001
                    pass
    upravitelj.connect("script-message-received::" + MOST, ob_sporocilu)
    upravitelj.add_script(WebKit2.UserScript(SKRIPTA, WebKit2.UserContentInjectedFrames.ALL_FRAMES,
                                             WebKit2.UserScriptInjectionTime.START, None, None))
