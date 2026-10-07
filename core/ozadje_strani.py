"""Barva ozadja pogleda WebKit glede na stran.

WebKit ozadje pogleda nariše pod stranjo, ki svojega ozadja ne določi. Safeer pogledom nastavi temno ozadje, da se
ob odpiranju ne zabliska belo. Stran brez svojega ozadja (navaden HTML, besedilna datoteka, WebKitova stran »strani
ni mogoče naložiti«) je bila zato temna s črnim besedilom - neberljiva. Pravilo: temno samo pod našimi stranmi
(mapa ui, prazen pogled in strani, ki jih program riše sam - pove jih s pravilom `nasa`), pod vsem drugim belo, kot
privzame vsak brskalnik.

Kdaj: WebKit izrecno barvo pogleda vzame za osnovo strani; ko dokument izbere temno barvno shemo (`color-scheme: dark`
brez svojega ozadja), osnovo sam zamenja s temno - naša poznejša nastavitev pa to povozi. Izmerjeno 7. 10. 2026 na
WebKitGTK 2.52.6: belo, nastavljeno ob LoadEvent.COMMITTED, je tako stran naredilo belo z belim besedilom; belo,
nastavljeno ob odločanju o navigaciji ali ob LoadEvent.STARTED, ne. Zato belo nastavimo zgodaj, barvo, ki jo pogled že
ima, pa si zapomnimo in je ne nastavljamo znova.
"""
import os
import urllib.parse

BELO = "#ffffff"


def nasa_stran(naslov, mapa_ui) -> bool:
    """Prazen pogled ali datoteka iz naše mape ui (začetna stran, tipkovnica)."""
    n = str(naslov or "")
    if n in ("", "about:blank"):
        return True
    if not n.startswith("file://"):
        return False
    try:
        pot = os.path.realpath(urllib.parse.unquote(urllib.parse.urlsplit(n).path))
        mapa = os.path.realpath(str(mapa_ui))
    except Exception:
        return False
    return pot == mapa or pot.startswith(mapa + os.sep)


def _je_nasa(naslov, mapa_ui, nasa=None) -> bool:
    """Naša stran po osnovnem pravilu ([nasa_stran]) ali po pravilu programa: `nasa(naslov) -> bool` za strani, ki jih
    program riše sam, a niso datoteke iz mape ui (Safeer Browser: notranje strani na shemi safeer://)."""
    if nasa_stran(naslov, mapa_ui):
        return True
    if nasa is None:
        return False
    try:
        return bool(nasa(str(naslov or "")))
    except Exception:
        return False


def barva(naslov, mapa_ui, temna: str, nasa=None) -> str:
    return temna if _je_nasa(naslov, mapa_ui, nasa) else BELO


#: Atribut pogleda z barvo, ki smo mu jo nazadnje nastavili.
ZAPIS = "_safeer_ozadje"


def _nastavi(Gdk, pogled, b: str) -> bool:
    """Pogledu nastavi barvo ozadja, če je še nima. Vrne True, če jo je nastavil."""
    if getattr(pogled, ZAPIS, None) == b:
        return False
    rgba = Gdk.RGBA()
    rgba.parse(b)
    pogled.set_background_color(rgba)
    setattr(pogled, ZAPIS, b)
    return True


def pred_nalaganjem(Gdk, pogled, cilj, mapa_ui, temna: str, nasa=None) -> str:
    """Pred nalaganjem strani [cilj] (odločanje o navigaciji, LoadEvent.STARTED): za spletno stran belo, preden njen
    dokument nastane. Za našo stran tu ne naredi ničesar - temno pride, ko je prikazana ([uskladi]): navigacija se
    lahko še prekliče, spletna stran brez ozadja, ki je še na zaslonu, pa bi medtem potemnela. Vrne nastavljeno barvo."""
    try:
        if _je_nasa(cilj, mapa_ui, nasa):
            return ""
        _nastavi(Gdk, pogled, BELO)
        return BELO
    except Exception:
        return ""


def uskladi(Gdk, pogled, mapa_ui, temna: str, nasa=None) -> str:
    """Ob LoadEvent.COMMITTED: temno pod našo stranjo. Pod spletno stranjo je belo nastavil že [pred_nalaganjem]; če
    ni tekel, ga nastavi zdaj (zasilna pot - za stran s temno shemo prepozno, za navadno stran dovolj). Vrne barvo."""
    try:
        b = barva(pogled.get_uri(), mapa_ui, temna, nasa)
        _nastavi(Gdk, pogled, b)
        return b
    except Exception:
        return ""


def prikljuci(Gdk, WebKit2, pogled, mapa_ui, temna: str, nasa=None) -> None:
    """Pogledu nastavi začetno temno ozadje (brez belega bliska pod našo začetno stranjo) in ga odslej usklajuje s
    stranjo. Kliči PRED priklopom drugih poslušalcev `decide-policy`: naš mora priti na vrsto prvi, odločitve pa ne
    sprejme (vrne False). `nasa(naslov) -> bool`: dodatne strani, ki jih program riše sam (glej [_je_nasa])."""
    try:
        _nastavi(Gdk, pogled, temna)
    except Exception:
        pass

    def politika(p, odlocitev, vrsta):
        if vrsta == WebKit2.PolicyDecisionType.NAVIGATION_ACTION:
            try:
                cilj = odlocitev.get_navigation_action().get_request().get_uri() or ""
            except Exception:
                cilj = ""
            if cilj:
                pred_nalaganjem(Gdk, p, cilj, mapa_ui, temna, nasa)
        return False

    def nalaganje(p, dogodek):
        if dogodek == WebKit2.LoadEvent.STARTED:
            try:
                cilj = p.get_uri() or ""
            except Exception:
                return
            if cilj:
                pred_nalaganjem(Gdk, p, cilj, mapa_ui, temna, nasa)
        elif dogodek == WebKit2.LoadEvent.COMMITTED:
            uskladi(Gdk, p, mapa_ui, temna, nasa)

    pogled.connect("decide-policy", politika)
    pogled.connect("load-changed", nalaganje)
