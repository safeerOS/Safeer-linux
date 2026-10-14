"""Pojavna okna (window.open) v Spletu in Safeer Browserju: nezazelena blokira, prijavna in placilna pusti.

Lastnik, 14. 10. 2026: »preprečiti nezaželena pop up okna, pri čemer zaželenih, kot so prijavna okna, ne blokiramo«.

Plasti (od zunaj navznoter):
1. WebKit: okno brez uporabnikovega klika ni nikoli odprto (javascript_can_open_windows_automatically = False).
2. Seznam oglasov in groženj (adblock) - tudi za okna po kliku.
3. Ta modul: okno, ki ga po kliku odpre SKRIPTA (ne prava povezava), je dovoljeno, ce gre na isto stran, na prijavo ali
   placilo (znani ponudniki, poti /login, /oauth ...) ali ce je uporabnik stran ze dovolil. Drugace je blokirano in
   Splet pokaze vrstico »Blokirano pojavno okno · Odpri · Vedno dovoli« - nic se ne izgubi brez vednosti.
Prava povezava (<a target=_blank>) se vedno odpre: to je uporabnikova izbira.
"""
from __future__ import annotations

import urllib.parse

#: Prijave in placila, ki se odpirajo v oknu (OAuth, »Prijava z ...«, 3-D Secure, PayPal).
PRIJAVNI_GOSTITELJI = (
    "accounts.google.com", "accounts.youtube.com", "login.microsoftonline.com", "login.live.com",
    "login.microsoft.com", "appleid.apple.com", "idmsa.apple.com", "facebook.com", "github.com", "gitlab.com",
    "x.com", "twitter.com", "api.twitter.com", "discord.com", "slack.com", "linkedin.com", "auth0.com",
    "okta.com", "onelogin.com", "amazon.com", "steamcommunity.com", "id.twitch.tv", "zoom.us", "dropbox.com",
    "accounts.spotify.com", "auth.openai.com", "accounts.x.ai", "auth.x.ai", "id.atlassian.com",
    "paypal.com", "stripe.com", "checkout.stripe.com", "klarna.com", "adyen.com", "3dsecure.io",
    "challenges.cloudflare.com", "hcaptcha.com", "recaptcha.net", "si-pass.gov.si", "nio.gov.si",
)

#: Poti, ki pomenijo prijavo pri kateremkoli ponudniku (kot adblock.AUTH_SCRIPT_EXCLUSIONS).
PRIJAVNE_POTI = ("/login", "/signin", "/sign-in", "/oauth", "/oauth2", "/auth/", "/authorize", "/sso",
                 "/saml", "/openid", "/connect/authorize", "/consent")

#: Drugi del domene, pod katerim so registrirane strani (co.uk ...): osnova je tedaj zadnjih treh delov.
_DVODELNE = frozenset({"co.uk", "org.uk", "ac.uk", "gov.uk", "com.au", "net.au", "org.au", "co.jp", "ne.jp",
                       "com.br", "com.cn", "com.tr", "co.nz", "co.za", "com.mx", "com.ar", "co.in", "co.kr",
                       "gov.si", "com.hr", "co.rs", "co.at", "or.at"})


def gostitelj(uri: str) -> str:
    try:
        return (urllib.parse.urlsplit(uri or "").hostname or "").rstrip(".").lower()
    except ValueError:
        return ""


def osnova(host: str) -> str:
    """Registrirana domena (priblizek brez celotnega seznama javnih koncnic): mail.google.com -> google.com."""
    deli = [d for d in (host or "").split(".") if d]
    if len(deli) <= 2:
        return ".".join(deli)
    if ".".join(deli[-2:]) in _DVODELNE:
        return ".".join(deli[-3:])
    return ".".join(deli[-2:])


def _pod(host: str, seznam) -> bool:
    return any(host == g or host.endswith("." + g) for g in seznam)


def je_prijava(uri: str) -> bool:
    h = gostitelj(uri)
    if not h:
        return False
    if _pod(h, PRIJAVNI_GOSTITELJI):
        return True
    try:
        pot = (urllib.parse.urlsplit(uri).path or "").lower()
    except ValueError:
        return False
    return any(pot.startswith(p) or ("/" + p.strip("/") + "/") in pot + "/" for p in PRIJAVNE_POTI)


def dovoli(izvor: str, cilj: str, prava_povezava: bool, dovoljeni=()) -> bool:
    """Ali okno, ki ga je uporabnik sprozil s klikom, odpremo. izvor: stran, ki okno odpira; cilj: naslov okna."""
    if prava_povezava:
        return True
    if not cilj.lower().startswith(("http://", "https://")):
        return True        # about:blank: prijava pogosto odpre prazno okno in ga nato preusmeri (ta navigacija gre
                           # skozi Scit kot vsaka druga)
    hi, hc = gostitelj(izvor), gostitelj(cilj)
    if hi and osnova(hi) == osnova(hc):
        return True
    if je_prijava(cilj):
        return True
    return bool(hi) and osnova(hi) in set(dovoljeni or ())


def zapomni(dovoljeni, izvor: str, najvec: int = 300) -> list:
    """Seznam strani, ki smejo odpirati okna (»Vedno dovoli«), z novo stranjo na koncu."""
    o = osnova(gostitelj(izvor))
    seznam = [str(x) for x in (dovoljeni or []) if isinstance(x, str) and x != o]
    if o:
        seznam.append(o)
    return seznam[-najvec:]


BESEDILA = {
    "sl": {"po_blokirano": "Blokirano pojavno okno: {cilj}", "po_odpri": "Odpri", "po_vedno": "Vedno dovoli za {stran}",
           "po_nastavitev": "Blokiraj nezaželena pojavna okna (prijave ostanejo dovoljene)"},
    "en": {"po_blokirano": "Pop-up blocked: {cilj}", "po_odpri": "Open", "po_vedno": "Always allow for {stran}",
           "po_nastavitev": "Block unwanted pop-ups (sign-in windows stay allowed)"},
    "de": {"po_blokirano": "Pop-up blockiert: {cilj}", "po_odpri": "Öffnen", "po_vedno": "Für {stran} immer erlauben",
           "po_nastavitev": "Unerwünschte Pop-ups blockieren (Anmeldefenster bleiben erlaubt)"},
    "es": {"po_blokirano": "Ventana emergente bloqueada: {cilj}", "po_odpri": "Abrir",
           "po_vedno": "Permitir siempre en {stran}",
           "po_nastavitev": "Bloquear ventanas emergentes no deseadas (se permiten las de inicio de sesión)"},
    "fr": {"po_blokirano": "Fenêtre pop-up bloquée : {cilj}", "po_odpri": "Ouvrir",
           "po_vedno": "Toujours autoriser pour {stran}",
           "po_nastavitev": "Bloquer les pop-ups indésirables (les fenêtres de connexion restent autorisées)"},
    "it": {"po_blokirano": "Pop-up bloccato: {cilj}", "po_odpri": "Apri", "po_vedno": "Consenti sempre per {stran}",
           "po_nastavitev": "Blocca i pop-up indesiderati (le finestre di accesso restano consentite)"},
}
