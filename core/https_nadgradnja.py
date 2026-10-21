"""Samodejni prehod na https s povratkom (kot Safari 18 »HTTPS-Upgrade«, Chrome »HTTPS Upgrades«, Firefox »HTTPS-First«).

Lastnik 21. 10. 2026: »strani samodejno preide na https, ce ti stran omogoca«. Glavna navigacija na http:// JAVNEGA
gostitelja najprej poskusi https:// istega naslova. Ce https ne uspe (napaka TLS ali potrdila, zavrnjena povezava, rok
ROK_S, preusmeritev nazaj na http), se odpre prvotni http:// brez opozorilne strani (kot Safari), gostitelj pa se za
sejo zapomni, da se poskus ne ponavlja ob vsakem kliku.

Brez poskusa: lokalni naslovi (core/config._lokalni_gostitelj), imena brez pike (»nas«), lokalne domene (LOKALNE_DOMENE),
vrata, ki niso 80 (na drugih vratih https skoraj nikoli ne tece - Chrome jih tudi ne nadgradi), metoda, ki ni GET
(AGENTS.md: POST/PUT se nikoli ne ponovi), in vse, kar ni glavni okvir (iframe in podviri ostanejo nespremenjeni).

WebKitGTK 6.0 (javni API) tega ne zna: v WebKitu je funkcija »HTTPSByDefaultEnabled« s stanjem »testable« in privzeto
izklopljena (Source/WTF/Scripts/Preferences/UnifiedWebPreferences.yaml), nacin pa izbira odjemalec Cocoa prek
WKWebpagePreferences; WebKitWebsitePolicies v GTK ima samo samodejno predvajanje. Zato izvedba tu. Ce bo WebKitGTK
funkcijo izpostavil kot stabilno, se ta modul umakne.

Modul ne uvaza gi: odlocitve so ciste funkcije (preizkus brez WebKita), vezava na pogled dobi WebKit in GLib od klicatelja.
Uporabljata ga Splet (core/os_splet.py) in Safeer Browser za Linux (safeer_brskalnik.py prek VdelaniSplet).
"""
from __future__ import annotations

import ipaddress
import os
import time
import urllib.parse
from typing import Callable, Optional, Set

from core.config import _lokalni_gostitelj

#: Rok za poskus https (s): Safari in Chrome cakata ~3 s, preden prideta na http (Chrome: 3 s »fallback timer«).
ROK_S = 3.0
#: Domene domacega omrezja (RFC 6762 .local, RFC 8375 .home.arpa, ICANN .internal, obicajni .lan): brez poskusa.
LOKALNE_DOMENE = (".local", ".lan", ".home.arpa", ".internal", ".localhost")
#: Rok veljavnosti trajnega zapisa o gostiteljih brez https (30 dni; lastnik 21. 10. 2026).
ROK_DNI = 30
ROK_VELJAVNOSTI_S = 30 * 86400
#: Ime datoteke za trajno hrambo gostiteljev brez https v mapi nastavitev.
DATOTEKA_POVRATKOV = "https_brez.json"


def _gostitelj(uri: str) -> str:
    try:
        return (urllib.parse.urlsplit(uri).hostname or "").lower()
    except ValueError:
        return ""


def je_lokalen(gostitelj: str) -> bool:
    """localhost, naslov IP, ime brez pike ali lokalna domena: http ostane, brez poskusa https."""
    g = (gostitelj or "").lower().rstrip(".")
    if not g or "." not in g or g.endswith(LOKALNE_DOMENE) or _lokalni_gostitelj(f"[{g}]" if ":" in g else g):
        return True
    try:
        ipaddress.ip_address(g)
        return True          # tudi javni IP: potrdila za IP so redka, Chrome IP-jev ne nadgradi - brez poskusa
    except ValueError:
        return False


class Seja:
    """Gostitelji, pri katerih https ni uspel (povratek na http):
    - trajno na disku v config_dir (z rokom 30 dni, atomski zapis),
    - v pomnilniku za cas seje (proces), skupno vsem zavihkom.

    Naslednji obisk takoj na http brez poskusa in brez cakanja (lastnik 21. 10. 2026:
    »ce stran sporoca, da https ne podpira, ga ne iscemo in ne izgubljamo casa«).
    """

    def __init__(self, config_dir: Optional[str] = None) -> None:
        self.config_dir = config_dir
        self.povratki: Set[str] = set()
        self._nalozi_disk()

    def _pot_diska(self) -> Optional[str]:
        if self.config_dir:
            return os.path.join(self.config_dir, DATOTEKA_POVRATKOV)
        return None

    def _nalozi_disk(self) -> None:
        pot = self._pot_diska()
        if not pot or not os.path.exists(pot):
            return
        from core import shramba_json
        podatki = shramba_json.preberi_slovar(pot)
        if not podatki or not isinstance(podatki, dict):
            return
        zdaj = time.time()
        sprememba = False
        ostali = {}
        for gostitelj, ts in podatki.items():
            try:
                ts_f = float(ts)
                if zdaj - ts_f < ROK_VELJAVNOSTI_S:
                    ostali[gostitelj.lower()] = ts_f
                    self.povratki.add(gostitelj.lower())
                else:
                    sprememba = True  # poteklo 30 dni
            except (ValueError, TypeError):
                sprememba = True
        if sprememba:
            try:
                shramba_json.zapisi_atomsko(pot, ostali)
            except OSError:
                pass

    def pocisti(self) -> None:
        """Brisanje podatkov brskanja (zgodovina, piskotki/HSTS): seznam gostiteljev je sled obiskanih strani - izbrise se
        z njimi (v pomnilniku in na disku)."""
        self.povratki.clear()
        pot = self._pot_diska()
        if pot:
            try:
                os.remove(pot)
            except FileNotFoundError:
                pass
            except OSError as napaka:
                print("[Splet] https_brez:", napaka, flush=True)

    def je_brez_https(self, gostitelj: str) -> bool:
        """Ali je gostitelj v povratkih (v pomnilniku ali na disku znotraj 30 dni)."""
        g = (gostitelj or "").lower().strip()
        if not g:
            return False
        if g in self.povratki:
            return True
        pot = self._pot_diska()
        if pot and os.path.exists(pot):
            from core import shramba_json
            podatki = shramba_json.preberi_slovar(pot)
            if podatki and isinstance(podatki, dict) and g in podatki:
                try:
                    if time.time() - float(podatki[g]) < ROK_VELJAVNOSTI_S:
                        self.povratki.add(g)
                        return True
                except (ValueError, TypeError):
                    pass
        return False

    def nadgradnja(self, uri: str, metoda: Optional[str]) -> Optional[str]:
        """https naslov za poskus ali None (ostane, kot je)."""
        if metoda != "GET" or not (uri or "").lower().startswith("http://"):
            return None
        try:
            deli = urllib.parse.urlsplit(uri)
            vrata = deli.port
        except ValueError:
            return None
        gost = (deli.hostname or "").lower()
        if not gost or vrata not in (None, 80) or deli.username or deli.password or "@" in deli.netloc:
            return None
        if je_lokalen(gost) or self.je_brez_https(gost):
            return None
        gostitelj = deli.netloc.rsplit("@", 1)[-1]
        if vrata == 80:
            gostitelj = gostitelj.rsplit(":", 1)[0]          # https na vratih 443, ne na 80
        return urllib.parse.urlunsplit(("https", gostitelj, deli.path, deli.query, deli.fragment))

    def povratek(self, gostitelj: str) -> None:
        """Gostitelj brez https: zapomnimo si ga v seji in trajno na disku z atomskim zapisom."""
        g = (gostitelj or "").lower().strip()
        if not g:
            return
        self.povratki.add(g)
        pot = self._pot_diska()
        if not pot:
            return
        from core import shramba_json
        zdaj = time.time()
        podatki = shramba_json.preberi_slovar(pot) or {}
        if not isinstance(podatki, dict):
            podatki = {}
        ocisceni = {}
        for k, v in podatki.items():
            try:
                if zdaj - float(v) < ROK_VELJAVNOSTI_S:
                    ocisceni[k.lower()] = float(v)
            except (ValueError, TypeError):
                pass
        ocisceni[g] = zdaj
        try:
            shramba_json.zapisi_atomsko(pot, ocisceni)
        except OSError:
            pass


class Poskus:
    """En poskus https na glavnem okvirju: prvotni http, https in gostitelj."""

    def __init__(self, http: str, https: str) -> None:
        self.http, self.https, self.gostitelj = http, https, _gostitelj(https)
        # Gostitelji poskusa: https://a.si lahko preusmeri na https://www.a.si; napaka tam je se vedno napaka poskusa.
        self.gostitelji = {self.gostitelj}


class Pogled:
    """Vezava na en WebKit.WebView: load-changed (glavni okvir), load-failed, load-failed-with-tls-errors.

    Povezati PRED core/network_errors.NetworkErrorHandler (signal ustavimo z True), sicer bi ta pokazal stran napake
    namesto povratka na http. metoda(uri) vrne metodo glavne navigacije (NetworkErrorHandler._metoda) ali None."""

    def __init__(self, pogled, seja: Seja, WebKit, GLib, metoda: Callable[[str], Optional[str]]) -> None:
        self.pogled, self.seja, self.W, self.GLib, self.metoda = pogled, seja, WebKit, GLib, metoda
        self.poskus: Optional[Poskus] = None
        self.ura = 0
        pogled.connect("load-changed", self.load_changed)
        pogled.connect("load-failed", self.load_failed)
        pogled.connect("load-failed-with-tls-errors", self.tls_failed)

    # -- pred nalaganjem (naslovna vrstica, zaznamek, povezava od drugod): zahteva na http sploh ne odide
    def pred_nalaganjem(self, uri: str) -> str:
        https = self.seja.nadgradnja(uri, "GET")
        if https is None:
            return uri
        self._zacni(uri, https)
        return https

    def _zacni(self, http: str, https: str) -> None:
        self._ustavi_uro()
        self.poskus = Poskus(http, https)
        self.ura = self.GLib.timeout_add(int(ROK_S * 1000), self._rok)

    def _ustavi_uro(self) -> None:
        if self.ura:
            self.GLib.source_remove(self.ura)
            self.ura = 0

    def _povratek(self) -> None:
        """https ni uspel: gostitelj v seji na http, nalozi prvotni http (brez opozorilne strani, kot Safari)."""
        poskus, self.poskus = self.poskus, None
        self._ustavi_uro()
        if poskus is None:
            return
        self.seja.povratek(poskus.gostitelj)
        print("[Splet] https ni uspel, povratek na http: %s" % poskus.gostitelj, flush=True)
        self.GLib.idle_add(lambda: self.pogled.load_uri(poskus.http) and False)

    def _rok(self) -> bool:
        self.ura = 0
        if self.poskus is not None:
            self.pogled.stop_loading()
            self._povratek()
        return False

    # -- signali
    def load_changed(self, pogled, dogodek) -> None:
        W = self.W.LoadEvent
        uri = pogled.get_uri() or ""
        if dogodek in (W.STARTED, W.REDIRECTED):
            if self.poskus is not None:
                if uri.lower().startswith("http://") and _gostitelj(uri) in self.poskus.gostitelji:
                    # Streznik https preusmeri nazaj na http istega gostitelja: zanka - ostane http, brez novega poskusa.
                    self.seja.povratek(self.poskus.gostitelj)
                    self.poskus = None
                    self._ustavi_uro()
                    return
                if uri.lower().startswith("https://"):
                    self.poskus.gostitelji.add(_gostitelj(uri))
                    return                           # nas poskus (ali preusmeritev znotraj https) - caka na rezultat
                self.poskus = None                   # uporabnik je medtem odprl drug naslov
                self._ustavi_uro()
            https = self.seja.nadgradnja(uri, self.metoda(uri))
            if https is not None:
                # Povezava, preusmeritev, zgodovina: load-changed velja samo za glavni okvir (iframe se ne nadgradi).
                self._zacni(uri, https)
                self.GLib.idle_add(lambda: pogled.load_uri(https) and False)
        elif dogodek == W.COMMITTED and self.poskus is not None and uri.lower().startswith("https://"):
            self.poskus = None                       # https je uspel
            self._ustavi_uro()

    def load_failed(self, pogled, dogodek, uri, napaka) -> bool:
        if self.poskus is None or not (uri or "").lower().startswith("https://") \
                or _gostitelj(uri) not in self.poskus.gostitelji:
            return False
        try:
            if napaka.matches(self.W.network_error_quark(), self.W.NetworkError.CANCELLED):
                return False                         # nas load_uri ali uporabnik je preklical - ni napaka https
        except Exception:  # noqa: BLE001 - lazna napaka v preizkusu nima matches
            pass
        self._povratek()
        return True

    def tls_failed(self, pogled, uri, potrdilo, napake) -> bool:
        if self.poskus is None or _gostitelj(uri) not in self.poskus.gostitelji:
            return False
        self._povratek()
        return True
