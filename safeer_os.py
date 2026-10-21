#!/usr/bin/env python3
"""Safeer OS za racunalnik - preobleka cez Linux Mint.

Isti Safeer OS kot na televizorju, le za racunalnik: celozaslonski domaci zaslon z levim menijem
(Domov, Medijski center, Naprave, Programi, Datoteke, Splet, Zapiski, Nastavitve), ki pokaze VSE, kar je ze na racunalniku -
programe iz menija, uporabnikove mape, nastavitve Minta - in doda Safeerjeve reci (Safeer Link,
spletne aplikacije, iskanje po vsem hkrati).

Pod njim ostane Linux Mint: programi se odpirajo v svojih oknih, nastavitve so Mintove
(cinnamon-settings, Upravitelj posodobitev ...), zato Safeer OS nicesar ne podvaja in nicesar
ne pokvari. Ko ga uporabnik zapre, je tam njegovo obicajno namizje.

Zagon:
  safeer_os.py                 celozaslonsko (privzeto)
  safeer_os.py --okno          v oknu (za preizkus ob drugem delu)
  safeer_os.py --predvajalnik  Safeer Player: samo Medijski center v svojem oknu (tudi --player)
  safeer_os.py --posnetek P    izrise stran, shrani posnetek v P (PNG) in konca (preverjanje)
  safeer_os.py --nazaj-na-cinnamon  obicajno namizje Cinnamon: brez zagona ob prijavi, vrne pult in dock (tudi --back-to-cinnamon)

Prvi zagon: ce racunalnik se ni v Safeer Linku in uporabnik ni izbral »Nadaljuj brez povezave
naprav«, Safeer OS odpre prijavno okno Safeer Control (QR / 6-mestna koda / brez povezave).
Naprave lahko uporabnik kadarkoli poveze v razdelku Naprave.
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
import socket
import subprocess
import weakref
import sys
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Optional

KOREN = os.path.dirname(os.path.abspath(__file__))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

# Manj RAM-a: najvec dve areni malloc (pred nitmi GTK/WebKit/GStreamer) - core/pomnilnik.py.
# Paket .deb: nas WebKitGTK in libsoup iz /usr/lib/<paket>/webkit namesto sistemskih (pred `import gi`).
from core import zasebni_webkit  # noqa: E402
zasebni_webkit.nastavi(KOREN)
# Se ena nit: mesta za spremenljivke, ki jih bo lupina Qt v tem procesu zacasno zamenjala (core/okolje_procesa.py).
from core import okolje_procesa  # noqa: E402
okolje_procesa.pred_nitmi()
if __name__ == "__main__":
    # Ubuntu 24.04+ brez nasega profila AppArmor: ce bwrap ne more teci, WebKitov peskovnik izklopi (spremenljivka v
    # okolju) - tu, pred prvo nitjo; v main() so niti ze tekle (core/okolje_procesa.py). Uvoz modula okolja ne spremeni.
    from core import peskovnik_userns  # noqa: E402
    peskovnik_userns.pred_nitmi()
from core import video_dekoderji  # noqa: E402
video_dekoderji.programsko()     # VA-API je pri YouTubu odpovedoval (18. 10. 2026), glej modul
from core import pomnilnik  # noqa: E402
pomnilnik.omeji_arene(2)
# Profil naprave: niti slikanja Skia za spletne procese - okolje pred prvo nitjo (core/profil_naprave.py), samo kot
# glavni program (ob uvozu v drug proces, npr. lupino, niti ze tecejo - AGENTS.md, core/okolje_procesa.py).
from core import profil_naprave  # noqa: E402
if __name__ == "__main__":
    profil_naprave.okolje_pred_nitmi()

import gi  # noqa: E402

# GTK4 + WebKitGTK 6.0 (lastnik, 14. 10. 2026): na X11 GTK3 nima EGL, zato je WebKit vsak okvir kopiral prek procesorja.
gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("WebKit", "6.0")
from gi.repository import Gdk, Gio, GLib, Gtk  # noqa: E402
# Ime WebKit2 ostane: skupne pomozne funkcije (pomnilnik, os_stabilnost, odlozisce_varuh) dobijo modul kot parameter.
from gi.repository import WebKit as WebKit2  # noqa: E402
zasebni_webkit.preveri_nas_webkit(WebKit2)
try:   # X11: delovno obmocje zaslona (GdkX11.X11Monitor.get_workarea) in cas streznika; na Waylandu ga ni
    gi.require_version("GdkX11", "4.0")
    from gi.repository import GdkX11  # noqa: E402
except (ValueError, ImportError):
    GdkX11 = None

from core import (os_datoteke, os_govor, os_katalog, os_knjiznica, os_lupa, os_oblak_igre, os_okna, os_omrezje, os_programi, os_scit, os_sistem,  # noqa: E402
                  os_media_besedila, os_mediji, os_posodobitve, os_predvajalnik, os_sporocila, os_spletne, os_stabilnost,
                  os_torrent, os_torrent_tok, os_zapiski, os_zvok, knjiznica_kroga, os_ponudniki_programov, os_github_programi)
from core import budnost, gostitelj, odlozisce_varuh, os_iskalnik, os_odpri_z, os_pretvorba_datotek  # noqa: E402
from core import peskovnik_userns  # noqa: E402
from core import nova_razlicica  # noqa: E402
from core import media_servers  # noqa: E402
from core import os_dock  # noqa: E402
from core import priljubljeno  # noqa: E402
from core import os_lupina  # noqa: E402
from core import os_medijska_plast  # noqa: E402
from core import os_vgrajeni_viri  # noqa: E402
from core import x11  # noqa: E402
from core import seja_prikaza  # noqa: E402
from core.sporocila import vklop as sporocila_vklop  # noqa: E402
pomnilnik.tlak_omrezja(WebKit2, 160)   # pred prvim pogledom: omrezni procesi WebKita z mejo pomnilnika
# Globalni model predpomnilnika po profilu PRED prvim lastnim WebContext (strani Safeer OS, Splet): WebProcessCache ga
# prebere ob nastanku konteksta - varcni profil brez predpomnilnika procesov (core/profil_naprave.py).
profil_naprave.nastavi_model(WebKit2)
from core import en_proces  # noqa: E402
# Lupina namizja v svojem procesu pod varuhom (lastnik, 18. 10. 2026: moznost B) - core/lupina_streznik.py.
from core import lupina_streznik, varuh_procesov  # noqa: E402

# Preklop vhoda zvocne vrstice JBL je samo interni poskus: uradni paket modula ne vsebuje
# (packaging/install_os_payload.sh), zato ga uvozimo le, ce je prisoten (zagon iz repozitorija).
# Uradna pot za zvocnike v omrezju je splosni DLNA.
try:
    from core import os_jbl  # noqa: E402
except ImportError:
    os_jbl = None


def privzeti_brskalnik() -> str:
    """Ime privzetega brskalnika sistema (za https), npr. "Opera"; prazno, ce ga ni."""
    try:
        app = Gio.AppInfo.get_default_for_uri_scheme("https")
        return app.get_display_name() if app is not None else ""
    except Exception:  # noqa: BLE001
        return ""

MODULI_NASTAVITEV = ("", "themes", "backgrounds", "fonts", "display", "windows", "panel", "nightlight", "desktop",
                     "effects", "keyboard", "mouse", "sound", "power", "screensaver", "accessibility")


#: Moduli Cinnamona -> plosce Nastavitev GNOME 46 (Ubuntu 24.04; imena iz gnome-<plosca>-panel.desktop, preverjeno
#: 18. 10. 2026). Prej je GNOME vedno odprl prvo stran - npr. »Ozadje« ni odprlo Videza.
PLOSCE_GNOME = {"themes": "background", "backgrounds": "background", "display": "display", "nightlight": "display",
                "keyboard": "keyboard", "mouse": "mouse", "sound": "sound", "power": "power",
                "accessibility": "universal-access", "panel": "ubuntu", "desktop": "ubuntu", "windows": "multitasking",
                "screensaver": "privacy"}


def sistemske_nastavitve(modul: str = "") -> bool:
    """Odpre sistemske nastavitve namizja (Cinnamon; brez njega GNOME/Xfce/MATE). Samo znani moduli."""
    # Samo sistemske mape, ne PATH: Nastavitve (uporabniki, datum ...) lahko vprasajo za geslo (core/root_ukaz.py).
    from core.root_ukaz import sistemski_program as which, sistemski_ukaz
    if modul not in MODULI_NASTAVITEV:
        return False
    # Flatpak ima ovoj za vsako orodje (/app/host-bin), tudi ce ga gostitelj nima - zato odloci namizje seje.
    from core import seja_prikaza as seja
    gnome = seja.namizje() == "gnome"
    if which("cinnamon-settings") and not gnome:
        ukaz = ["cinnamon-settings"] + ([modul] if modul else [])
    elif which("gnome-control-center"):
        ukaz = ["gnome-control-center"] + ([PLOSCE_GNOME[modul]] if modul in PLOSCE_GNOME else [])
    else:
        ukaz = next(([u] for u in ("gnome-control-center", "xfce4-settings-manager", "mate-control-center")
                     if which(u)), None)
        if ukaz is None:
            return False
    ukaz = sistemski_ukaz(ukaz)
    if ukaz is None:
        return False
    try:
        subprocess.Popen(ukaz, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True, env=zasebni_webkit.okolje_za_zunanje())
        return True
    except OSError:
        return False

def dvojni_esc(prejsnji_ms, zdaj_ms, okno_ms: int = 600) -> bool:
    """Ali je bil Esc pritisnjen dvakrat zapored v okno_ms (casi dogodkov GDK v ms)."""
    if prejsnji_ms is None or not zdaj_ms:
        return False
    return 0 <= zdaj_ms - prejsnji_ms <= okno_ms


def _jbl_vrstica(ime: str) -> bool:
    return os_jbl is not None and os_jbl.je_vrstica(ime)

APP_ID = "io.github.memelandfaner.SafeerOS"


def _razlicica() -> str:
    try:
        with open(os.path.join(KOREN, "packaging", "VERSION_OS"), encoding="utf-8") as d:
            return d.read().strip()
    except Exception:
        return "0.4.28"


RAZLICICA = _razlicica()
#: Argumenti zagona, preden jih main() prilagodi: nova razlicica ohrani nacin (core/nova_razlicica.nacin_zagona).
_ZACETNI_ARGV = list(sys.argv)
# Najvec znakov, ki jih stran sme dati v odlozisce z enim klicem (sporocilo, povezava).
NAJVEC_KOPIJE = 1_000_000
CONTROL_NASTAVITVE = os.path.expanduser("~/.config/safeer-control/link.json")
#: Nastavitve Controla (pladenj: predvajanje_za_naprave, deljene mape ...), loceno od podatkov Linka v link.json.
CONTROL_NASTAVITVE_PLADNJA = os.path.expanduser("~/.config/safeer-control/control.json")
BRSKALNIK_NASTAVITVE = os.path.join((os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")),
                                    "safeer-mint", "settings.json")
ZAPISKI_POT = os.path.join((os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")),
                           "safeer-os", "zapiski.json")
ISKALNIKI = {"google": "https://www.google.com/search?q=", "duckduckgo": "https://duckduckgo.com/?q=",
             "brave": "https://search.brave.com/search?q=", "startpage": "https://www.startpage.com/do/search?q=",
             "bing": "https://www.bing.com/search?q=", "ecosia": "https://www.ecosia.org/search?q="}

#: Zeton mostu safeerOs (lastni vgrajeni viri, 15. 10. 2026). WebKit da window.webkit.messageHandlers VSEM okvirjem
#: strani, tudi tujim iframom (vgrajen vir, peskovnik komponente) - rokovalnik pa ne pove, iz katerega okvirja je
#: sporocilo. Zeton je samo v zaprtju MOST_JS, ki ga dobi le glavni okvir (TOP_FRAME); _na_sporocilo zavrne vsako
#: sporocilo brez njega. Nov ob vsakem zagonu procesa, nikoli na disku ali v dnevniku.
ZETON_MOSTU = secrets.token_urlsafe(32)

MOST_JS = r"""
(function () {
  var cakajo = {}, stevec = 0, zeton = "__ZETON__";
  window.__safeerOsOdgovor = function (id, ok, podatki) {
    var c = cakajo[id]; if (!c) return; delete cakajo[id];
    if (ok) c.res(podatki); else c.rej(podatki);
  };
  window.SafeerOS = {
    klic: function (metoda, argumenti) {
      return new Promise(function (res, rej) {
        var id = ++stevec; cakajo[id] = { res: res, rej: rej };
        try {
          window.webkit.messageHandlers.safeerOs.postMessage(JSON.stringify({ id: id, m: metoda, a: argumenti || [], t: zeton }));
        } catch (e) { delete cakajo[id]; rej(String(e)); }
      });
    }
  };
})();
""".replace("__ZETON__", ZETON_MOSTU)


def zeton_velja(sporocilo: dict) -> bool:
    """Sporocilo mostu safeerOs je iz glavnega okvirja strani Safeer OS (MOST_JS), ne iz vgrajenega okvirja."""
    return isinstance(sporocilo, dict) and hmac.compare_digest(str(sporocilo.get("t") or ""), ZETON_MOSTU)


def _jezik() -> str:
    """Jezik vmesnika: nastavitev Safeer Browserja, sicer jezik seje; podprti sl/en/de/es/fr/it."""
    posnetek = (os.environ.get("SAFEER_OS_JEZIK") or "")[:2].lower()   # samo za razvoj/posnetke
    if posnetek in ("sl", "en", "de", "es", "fr", "it"):
        return posnetek
    # Prek sheme nastavitev (core/nastavitve_shema.preberi_kljuc, naloga 43): napacen tip (npr. stevilo) ne velja za jezik.
    from core.nastavitve_shema import preberi_kljuc
    v = preberi_kljuc("ui_language", None, BRSKALNIK_NASTAVITVE)
    if v:
        return str(v)[:2]
    # Jezik seje po vrstnem redu gettexta - enako kot Safeer Control. Prej samo LC_MESSAGES/LANG: v seji z
    # LANGUAGE=sl in LANG=en_US je bil Safeer OS angleski, Control pa slovenski.
    for kljuc in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        vrednost = os.environ.get(kljuc, "")
        if vrednost:
            lang = vrednost.split(":")[0].replace("-", "_").split(".")[0].split("_")[0].strip().lower()[:2]
            return lang if lang in ("sl", "en", "de", "es", "fr", "it") else "en"
    return "en"


def _opis_prilog(poti) -> list:
    """Priloge za cipe pod vnosom sporocila: samo obstojece datoteke (ne mape), z imenom in velikostjo."""
    izid = []
    for pot in list(poti or [])[:50]:
        pot = os.path.realpath(os.path.expanduser(str(pot or "")))
        if os.path.isfile(pot):
            izid.append({"pot": pot, "ime": os.path.basename(pot), "velikost": os.path.getsize(pot)})
    return izid


def _posrednik_slik(url: str) -> str:
    """Posrednik za slike s spleta v pismih - isti, kot ga uporablja Splet: Safeerjev lasten posrednik
    (secure_proxy_mode »custom«), sicer sistemske nastavitve namizja (Gio.ProxyResolver: rocno, PAC, okolje).
    "" = neposredno. Ce posrednika ni mogoce ugotoviti, vrne neuporabnega - slike se ne nalozijo (nikoli mimo)."""
    try:
        from core.config import ConfigManager
        nastavitve = ConfigManager()
        lasten = str(nastavitve.get("secure_proxy_url", "") or "").strip()
        if nastavitve.get("secure_proxy_mode", "disabled") == "custom" and lasten:
            return lasten
    except Exception:  # noqa: BLE001
        return "neznan://"
    try:
        seznam = Gio.ProxyResolver.get_default().lookup(url, None) or []
    except Exception:  # noqa: BLE001
        return "neznan://"
    prvi = str(seznam[0]) if seznam else "direct://"
    return "" if prvi.startswith("direct://") else prvi


def _razresevalnik_slik(nastavitve=None):
    """Razresevanje imen slik s spleta v pismih: ce je v Safeerju vklopljen sifriran DNS (doh_enabled + ponudnik),
    prek istega ponudnika DoH kot Splet (core/doh_proxy.DoHResolver) - sicer bi ponudnik interneta videl, katere
    strežnike pismo klice. Ce DoH ime ne razresi, slike ni (brez vrnitve na sistemski DNS). Brez DoH: sistemski DNS."""
    try:
        if nastavitve is None:
            from core.config import ConfigManager
            nastavitve = ConfigManager()
        vklopljen = bool(nastavitve.get("doh_enabled", True)) and nastavitve.get("doh_provider", "scit") != "disabled"
    except Exception:  # noqa: BLE001
        vklopljen = True                                     # nastavitev ni mogoce prebrati: raje sifrirano
        nastavitve = None
    if not vklopljen:
        return socket.getaddrinfo
    from core import doh_proxy
    ponudnik = nastavitve.get("doh_provider", "scit") if nastavitve is not None else "scit"
    lasten = nastavitve.get("custom_doh_url", "") if nastavitve is not None else ""
    razresevalnik = doh_proxy._global_resolver         # isti (in isti predpomnilnik) kot Splet, ce ze tece
    if razresevalnik is None:
        razresevalnik = doh_proxy.DoHResolver(ponudnik, lasten)
        # Scit: isti streznik naprej kot Splet in Scit (en vir, doh_proxy.naprej_iz)
        razresevalnik.naprej, razresevalnik.naprej_po_meri = doh_proxy.naprej_iz(nastavitve)
    else:
        razresevalnik.set_provider(ponudnik, lasten)

    def razresi(ime, _vrata=None):
        try:
            ip = razresevalnik.resolve(str(ime))
        except Exception:  # noqa: BLE001
            ip = None
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 0))] if ip else []
    return razresi


def _velikost_napis(b: int) -> str:
    """»2,4 MB« za podnaslov okna predogleda (enake enote kot stran)."""
    if b <= 0:
        return ""
    enote, v = ["B", "kB", "MB", "GB"], float(b)
    i = 0
    while v >= 1024 and i < len(enote) - 1:
        v /= 1024
        i += 1
    return ("%d %s" % (v, enote[i])) if i == 0 or v >= 10 else ("%.1f %s" % (v, enote[i])).replace(".", ",")


def _ime_sistema() -> str:
    """Ime sistema iz /etc/os-release (npr. »Linux Mint 22.3«) - kar je res namesceno."""
    try:
        with open("/etc/os-release", encoding="utf-8") as f:
            for vrstica in f:
                if vrstica.startswith("PRETTY_NAME="):
                    return vrstica.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return "Linux"


IMENA_ISKALNIKOV = {"google": "Google", "duckduckgo": "DuckDuckGo", "brave": "Brave", "startpage": "Startpage",
                    "bing": "Bing", "ecosia": "Ecosia"}


def _kljuc_iskalnika() -> str:
    from core.nastavitve_shema import preberi_kljuc
    ime = preberi_kljuc("search_engine", "duckduckgo", BRSKALNIK_NASTAVITVE) or "duckduckgo"
    return ime if ime in ISKALNIKI else "duckduckgo"


def _iskalnik() -> str:
    return ISKALNIKI[_kljuc_iskalnika()]


def _podatki_controla() -> dict:
    try:
        with open(CONTROL_NASTAVITVE, encoding="utf-8") as f:
            p = json.load(f) or {}
        return p if isinstance(p, dict) else {}
    except Exception:
        return {}


_hubi_cache: dict = {"cas": 0.0, "hubi": []}


_hubi_isce = threading.Lock()


def hubi_v_omrezju(cas: float = 1.5, cakaj: bool = True) -> list:
    """Safeer Linki (sredisca), ki se oglasajo v domacem omrezju (mDNS): [{"ime", "naslov"}]. Rezultat velja
    10 s, da Naprave ne iscejo ob vsakem izrisu. Brez knjiznice zeroconf je seznam prazen.

    Iskanje traja `cas` sekund. Glavna nit GTK ne sme cakati (cakaj=False): dobi zadnji znani seznam, iskanje pa
    tece v ozadju (prej je zacetek namizja ob vsakem nalaganju zamrznil za 1,5 s)."""
    if time.time() - _hubi_cache["cas"] < 10:
        return list(_hubi_cache["hubi"])
    if not cakaj:
        if _hubi_isce.acquire(blocking=False):
            def isci_hube() -> None:
                try:
                    _poisci_hube(cas)
                finally:
                    _hubi_isce.release()
            threading.Thread(target=isci_hube, name="safeer-hubi-mdns", daemon=True).start()
        return list(_hubi_cache["hubi"])
    return _poisci_hube(cas)


def _poisci_hube(cas: float) -> list:
    try:
        from core import link_hub
        hubi = [{"ime": h.get("ime") or h["naslov"], "naslov": h["naslov"]} for h in link_hub.poisci_hube_mdns(cas)]
    except Exception:
        hubi = []
    _hubi_cache.update(cas=time.time(), hubi=hubi)
    return list(hubi)


def _stanje_povezave_spleta() -> dict:
    """Za oznako »povezan« v Spletu (casovnik na glavni niti GTK): brez iskanja Hubov."""
    return stanje_povezave("brez")


def stanje_povezave(hubi: str = "cakaj") -> dict:
    """Ali je racunalnik (Safeer Control) v Safeer Linku: povezan / brez (izbral) / nov.

    Povezava nezaupanega racunalnika velja samo do konca prijave (core/link_seja.py): ob novi
    prijavi je stanje spet »nov« in Safeer OS pokaze prijavno okno.

    hubi: "cakaj" (delovna nit: poisce Hube v omrezju), "ozadje" (glavna nit: zadnji znani, iskanje v ozadju) ali
    "brez" (oznaka povezave v Spletu vsakih 5 s: Hubov ne potrebuje)."""
    from core import link_seja
    p = _podatki_controla()
    seja = link_seja.trenutna_seja()
    povezan = link_seja.povezava_velja(p, seja)
    if not povezan and link_seja.zaupana(p):
        try:
            from core import link_hub, link_krog
            povezan = bool(link_krog.lahko_s_podpisom(link_hub.id_naprave() + "-control"))
        except Exception:
            pass
    if povezan:
        stanje = "povezan"
    elif link_seja.brez_v_seji(p, seja):
        stanje = "brez"
    else:
        stanje = "nov"
    izid = {"stanje": stanje, "control": bool(_ukaz_controla()), "zaupana": link_seja.zaupana(p), "hubi": [],
            "predajanje": bool(_nastavitve_pladnja().get("predvajanje_za_naprave", True))}
    if stanje != "povezan" and hubi != "brez":
        # Nepovezan racunalnik: Naprave povedo, ali je v omrezju Safeer Link (in kateri), ali ga ni.
        izid["hubi"] = hubi_v_omrezju(cakaj=hubi != "ozadje")
    return izid


CONTROL_ID = "io.github.memelandfaner.SafeerControl"
CONTROL_POT = "/io/github/memelandfaner/SafeerControl"
#: D-Bus tega procesa za Safeer Control: kaj domaci predvajalnik predvaja (core/link_predvajanje.py).
PREDVAJANJE_POT = "/io/github/memelandfaner/SafeerOS/predvajanje"


def nastavi_zaupanje(zaupaj: bool) -> bool:
    """»Zaupaj temu racunalniku«: tekoci Safeer Control dobi odlocitev prek D-Bus (drzi nastavitve v
    pomnilniku in bi jih sicer prepisal); ce ne tece, jo zapisemo v njegove nastavitve sami."""
    c = en_proces.control_app()
    if c is not None:   # Control tece v tem procesu (core/en_proces.py)
        en_proces.na_glavni(lambda: c.activate_action("zaupanje", GLib.Variant("b", bool(zaupaj))))
        return True
    try:
        vodilo = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        ima = vodilo.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                               "NameHasOwner", GLib.Variant("(s)", (CONTROL_ID,)), GLib.VariantType("(b)"),
                               Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]
        if ima:
            vodilo.call_sync(CONTROL_ID, CONTROL_POT, "org.gtk.Actions", "Activate",
                             GLib.Variant("(sava{sv})", ("zaupanje", [GLib.Variant("b", bool(zaupaj))], {})),
                             None, Gio.DBusCallFlags.NONE, 3000, None)
            return True
    except Exception as e:  # noqa: BLE001 - starejsi Control brez dejanja: zapisemo sami
        print("[SafeerOS] zaupanje prek Controla:", e)
    from core import link_seja
    p = _podatki_controla()
    p["zaupana"] = bool(zaupaj)
    p["seja_prijave"] = link_seja.trenutna_seja()
    try:
        os.makedirs(os.path.dirname(CONTROL_NASTAVITVE), exist_ok=True)
        zacasna = CONTROL_NASTAVITVE + ".tmp"
        with open(zacasna, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
        os.chmod(zacasna, 0o600)
        os.replace(zacasna, CONTROL_NASTAVITVE)
        return True
    except Exception:
        return False


def _nastavitve_pladnja() -> dict:
    try:
        with open(CONTROL_NASTAVITVE_PLADNJA, encoding="utf-8") as f:
            p = json.load(f) or {}
        return p if isinstance(p, dict) else {}
    except Exception:
        return {}


def nastavi_predajanje(deli: bool) -> bool:
    """»Predvajanje za druge naprave« (poleg Zaupaj): tekoci Control dobi vrednost prek D-Bus (drzi nastavitve v
    pomnilniku in uskladi pladenj), sicer jo zapisemo v control.json sami - kot nastavi_zaupanje."""
    c = en_proces.control_app()
    if c is not None:
        en_proces.na_glavni(lambda: c.activate_action("predvajanje-za-naprave", GLib.Variant("b", bool(deli))))
        return bool(deli)
    try:
        vodilo = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        if _control_na_vodilu(vodilo):
            vodilo.call_sync(CONTROL_ID, CONTROL_POT, "org.gtk.Actions", "Activate",
                             GLib.Variant("(sava{sv})", ("predvajanje-za-naprave", [GLib.Variant("b", bool(deli))], {})),
                             None, Gio.DBusCallFlags.NONE, 3000, None)
            return bool(deli)
    except Exception as e:  # noqa: BLE001 - starejsi Control brez dejanja: zapisemo sami
        print("[SafeerOS] predvajanje za naprave prek Controla:", e)
    p = _nastavitve_pladnja()
    p["predvajanje_za_naprave"] = bool(deli)
    try:
        os.makedirs(os.path.dirname(CONTROL_NASTAVITVE_PLADNJA), exist_ok=True)
        zacasna = CONTROL_NASTAVITVE_PLADNJA + ".tmp"
        with open(zacasna, "w", encoding="utf-8") as f:
            json.dump(p, f, ensure_ascii=False, indent=2)
        os.chmod(zacasna, 0o600)
        os.replace(zacasna, CONTROL_NASTAVITVE_PLADNJA)
        return bool(deli)
    except Exception:
        return not deli


def _control_na_vodilu(vodilo) -> bool:
    if en_proces.control_app() is not None:
        return True
    return _control_na_vodilu_dbus(vodilo)


def _control_na_vodilu_dbus(vodilo) -> bool:
    return vodilo.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "NameHasOwner",
                            GLib.Variant("(s)", (CONTROL_ID,)), GLib.VariantType("(b)"),
                            Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]


#: Control zaganja ena nit naenkrat. Brez tega sta ga ob zagonu Safeer OS dve niti zagnali dvakrat v 120 ms, drugi
#: zagon pa tekocemu primerku odpre okno (izmerjeno 4. 10. 2026).
_ZAGON_CONTROLA = threading.Lock()


def _zagotovi_control(vodilo) -> bool:
    """Control tece (v tem procesu ali na vodilu) - ce ne, ga Safeer OS vgradi v svoj proces (core/en_proces.py);
    sele ce to ni mogoce, ga zazenemo kot locen proces v ozadju (pladenj) in pocakamo, da se javi."""
    if _control_na_vodilu(vodilo):
        return True
    with _ZAGON_CONTROLA:
        if _control_na_vodilu(vodilo):      # medtem ga je zagnala druga nit
            return True
        aplikacija = en_proces.os_app()
        if aplikacija is not None and en_proces.na_glavni(aplikacija._vgradi_control, cas=20.0, privzeto=False):
            return True
        ukaz = _ukaz_controla()
        if not ukaz:
            return False
        # SAFEER_CONTROL_IZ_OS: `--ozadje` se ob delovni povrsini Safeer Cinnamon sicer konca takoj (samozagon, glej
        # safeer_control.main) - tu ga je zahteval Safeer OS sam, ker vgradnja ni bila mogoca.
        subprocess.Popen(ukaz + ["--ozadje"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                         env=dict(os.environ, SAFEER_CONTROL_IZ_OS="1"))
        for _ in range(40):
            time.sleep(0.25)
            if _control_na_vodilu(vodilo):
                time.sleep(0.5)
                return True
        return False


#: Nastavitve Controla, ki so bile samo v njegovem pladnju: kljuc v Nastavitvah Safeer OS -> (postavka pladnja,
#: stanje, nastavi). Prek postavke pladnja, kadar je pladenj: ostane uskladena in sprememba gre po isti poti.
_NASTAVITVE_CONTROLA = {
    "programi": ("programi", lambda c: bool(c.programi.vklopljeno), lambda c, v: c.nastavi_programe(v)),
    "vesDisk": ("ves_disk", lambda c: bool(c.datoteke.mape.ves_disk), lambda c, v: c.nastavi_ves_disk(v)),
    "zaslon": ("zaslon", lambda c: bool(c.zaslon.vklopljeno), lambda c, v: c.nastavi_zaslon(v)),
    "predajanje": ("predvajanje", lambda c: bool(c.nastavitve.get("predvajanje_za_naprave", True)),
                   lambda c, v: c.nastavi_predvajanje_za_naprave(v)),
    "samozagon": ("samozagon", lambda c: bool(sys.modules["safeer_control"].Samozagon.je_vklopljen()),
                  lambda c, v: c.nastavi_samozagon(v)),
}


def nastavitve_controla() -> Optional[dict]:
    """Stanje nastavitev Controla, ki tece v tem procesu (core/en_proces.py); None, ce ne tece tu."""
    c = en_proces.control_app()
    if c is None:
        return None
    try:
        izid = {k: stanje(c) for k, (_p, stanje, _n) in _NASTAVITVE_CONTROLA.items()}
        if en_proces.delovna_safeer_cinnamon():
            # Namizje (seja safeer-cinnamon) zazene Control v tem procesu; lastni samozagon Controla je skrit,
            # ker bi ob prijavi tekel drugi proces (pregled celovitosti 15. 10. 2026).
            izid.pop("samozagon", None)
        return izid
    except Exception as e:  # noqa: BLE001
        print("[SafeerOS] nastavitve Controla:", e)
        return None


def nastavi_control(kljuc: str, vrednost: bool) -> Optional[bool]:
    """Spremeni nastavitev Controla (glavna nit); vrne stanje, kot je obveljalo, ali None."""
    c = en_proces.control_app()
    zapis = _NASTAVITVE_CONTROLA.get(kljuc)
    if c is None or zapis is None or (kljuc == "samozagon" and en_proces.delovna_safeer_cinnamon()):
        return None
    ime_postavke, stanje, nastavi = zapis
    postavka = getattr(getattr(c, "pladenj", None), ime_postavke, None)
    if postavka is not None:
        postavka.set_active(bool(vrednost))         # toggled -> isti klic kot klik v pladnju
    else:
        nastavi(c, bool(vrednost))
    return stanje(c)


def control_dejanje(ime: str, parameter: Optional["GLib.Variant"] = None) -> bool:
    """Dejanje v Safeer Controlu (prijava, nova-naprava, odjava). Ce Control ne tece, ga zazenemo v ozadju
    (pladenj) in pocakamo, da se javi na vodilu. Klicati v ozadju (ne na glavni niti)."""
    try:
        vodilo = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        if not _zagotovi_control(vodilo):
            return False
        c = en_proces.control_app()
        if c is not None:
            en_proces.na_glavni(lambda: c.activate_action(ime, parameter))
            return True
        vodilo.call_sync(CONTROL_ID, CONTROL_POT, "org.gtk.Actions", "Activate",
                         GLib.Variant("(sava{sv})", (ime, [parameter] if parameter is not None else [], {})),
                         None, Gio.DBusCallFlags.NONE, 5000, None)
        return True
    except Exception as e:  # noqa: BLE001
        print("[SafeerOS] Control:", ime, e)
        return False


def zvok_na_napravo(id_naprave: str) -> bool:
    """»Predvajaj na«: Safeer Control preusmeri zvok racunalnika na napravo v Linku (core/link_zvok.py).

    Ce je racunalnik doslej igral na zvocno vrstico JBL po Bluetoothu in gre zvok zdaj na televizor, ki
    ima to vrstico na HDMI eARC, vrstico preklopimo na vhod TV (dodatek JBL, core/os_jbl.py)."""
    id_naprave = str(id_naprave or "")
    naprava = next((n for n in os_zvok.link_naprave()["naprave"] if n["id"] == id_naprave), None)
    if naprava is None:
        return False
    if _ZVOCNIKI is not None and _ZVOCNIKI.opis()["naprava"]:
        _ZVOCNIKI.ustavi()
    prej = os_zvok._privzeto()[0]
    ok = control_dejanje("zvok-na-napravo", GLib.Variant("s", id_naprave))
    if ok and naprava.get("platforma") == "tv" and _jbl_vrstica(prej):
        os_jbl.preklopi("tv")
    return ok


def zvok_ustavi() -> bool:
    """Zvok nazaj na racunalnik; ce je spet na vrstici JBL po Bluetoothu, jo preklopimo na Bluetooth."""
    ok = control_dejanje("zvok-ustavi")
    for _ in range(30):
        if not os_zvok.link_naprave()["zvok"]["naprava"]:
            break
        time.sleep(0.1)
    if ok and _jbl_vrstica(os_zvok._privzeto()[0]):
        os_jbl.preklopi("bluetooth")
    return ok


# ---------------------------------------------------------------------- zvocniki v omrezju (DLNA)
_ZVOCNIKI = None


def zvocniki():
    """Zvocniki v omrezju (core/zvok_na_zvocnik.py); ustvarimo ob prvi rabi, iskanje tece v ozadju."""
    global _ZVOCNIKI
    if _ZVOCNIKI is None:
        from core import zvok_na_zvocnik
        _ZVOCNIKI = zvok_na_zvocnik.Zvocniki()
        import atexit
        atexit.register(lambda: _ZVOCNIKI.ustavi())
    return _ZVOCNIKI


def zvok_stanje() -> dict:
    stanje = os_zvok.stanje()
    try:
        z = zvocniki()
        stanje["link"]["zvocniki"] = z.seznam()
        stanje["link"]["zvocnik"] = z.opis()
    except Exception as e:  # noqa: BLE001
        print("[SafeerOS] zvocniki:", e)
    stanje["moznosti"] = os_zvok.moznosti_izhoda(stanje)
    return stanje


def zvok_na_zvocnik(id_zvocnika: str, potrdi: bool = False) -> dict:
    """Zvok racunalnika na zvocnik v omrezju; tekoco sejo na napravo v Linku najprej koncamo."""
    if os_zvok.link_naprave()["zvok"]["naprava"]:
        control_dejanje("zvok-ustavi")
    return zvocniki().zacni(str(id_zvocnika or ""), bool(potrdi))


def zvok_izberi_izhod(m: dict, potrdi: bool = False):
    """Izbira v »Predvajaj na …« okna predvajalnika videa (GTK) - ista dejanja kot izberi() v assets/os/izhod.js."""
    vrsta, id_ = str(m.get("vrsta") or ""), str(m.get("id") or "")
    if vrsta == "racunalnik":
        return zvocniki().ustavi() if _ZVOCNIKI is not None and _ZVOCNIKI.opis()["naprava"] else zvok_ustavi()
    if vrsta == "naprava":
        return zvok_na_napravo(id_)
    if vrsta == "zvocnik":
        return zvok_na_zvocnik(id_, potrdi)
    return False


def zvok_izhod(ime: str) -> bool:
    """Izbran izhod racunalnika. Ce zvok ta trenutek tece na napravo v Linku, ga Control najprej vrne
    (in navidezni izhod pospravi), sele nato nastavimo uporabnikovo izbiro - sicer bi jo prepisal."""
    if _ZVOCNIKI is not None and _ZVOCNIKI.opis()["naprava"]:
        _ZVOCNIKI.ustavi()
    if os_zvok.link_naprave()["zvok"]["naprava"]:
        control_dejanje("zvok-ustavi")
        for _ in range(30):
            if not os_zvok.link_naprave()["zvok"]["naprava"]:
                break
            time.sleep(0.1)
    ok = os_zvok.nastavi_izhod(ime)
    if ok and _jbl_vrstica(ime):
        os_jbl.preklopi("bluetooth")
    return ok


# ---------------------------------------------------------------------- programi z drugih naprav (prek Controla)
def _control_naprave(metoda: str, *argumenti: str) -> dict:
    """Klic vmesnika Naprave v Safeer Controlu (D-Bus); Control zazenemo, ce ne tece. V ozadju."""
    try:
        vodilo = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        if not _zagotovi_control(vodilo):
            return {"ok": False, "koda": "ni_controla"}
        c = en_proces.control_app()
        if c is not None:   # v istem procesu: neposredno (ta funkcija tece v ozadju, kot prej klic D-Bus)
            izid = c._naprave_metoda(metoda, [str(x) for x in argumenti])
            return izid if isinstance(izid, dict) else {"ok": False}
        podpis = "(" + "s" * len(argumenti) + ")"
        r = vodilo.call_sync(CONTROL_ID, CONTROL_POT + "/naprave", CONTROL_ID + ".Naprave", metoda,
                             GLib.Variant(podpis, tuple(argumenti)) if argumenti else None,
                             GLib.VariantType("(s)"), Gio.DBusCallFlags.NONE, 60000, None)
        izid = json.loads(r.unpack()[0])
        return izid if isinstance(izid, dict) else {"ok": False}
    except Exception as e:  # noqa: BLE001
        print("[SafeerOS] naprave:", metoda, e)
        if "UnknownMethod" in str(e) or "No such method" in str(e):
            # Tece starejsi Safeer Control (posodobljen paket, a se nezagnan znova): metode se nima.
            return {"ok": False, "koda": "stari_control"}
        return {"ok": False, "koda": "napaka", "message": str(e)}


def internet_prek_telefona(ukaz: str, parametri: Optional[dict] = None, zazeni: bool = True) -> dict:
    """Internet prek telefona v Safeer Linku: nastavitve in stanje ima Safeer Control (D-Bus Naprave.Internet).

    `zazeni=False`: samo, ce Control ze tece - zaradi prikaza stanja ga ne zaganjamo. Parametre precistimo tu:
    stran sme nastaviti samo nacin, telefon, pot, sistemski posrednik in pomoc ob gneci."""
    if not zazeni:
        try:
            if not _control_na_vodilu(Gio.bus_get_sync(Gio.BusType.SESSION, None)):
                return {"ok": False, "koda": "ni_controla"}
        except Exception:  # noqa: BLE001
            return {"ok": False, "koda": "ni_controla"}
    p = parametri if isinstance(parametri, dict) else {}
    cisto: dict = {}
    if ukaz == "stanje":
        cisto["vprasaj"] = bool(p.get("vprasaj"))
    elif ukaz == "nastavi":
        for kljuc in ("nacin", "naprava", "pot", "gneca"):
            if isinstance(p.get(kljuc), str):
                cisto[kljuc] = p[kljuc][:96]
        if isinstance(p.get("sistemski"), bool):
            cisto["sistemski"] = p["sistemski"]
    elif ukaz != "preizkus":
        return {"ok": False, "koda": "napacna_zahteva"}
    return _control_naprave("Internet", ukaz, json.dumps(cisto))


def _seznami_z_naprav(uskladi: Callable[[Callable[[dict], Optional[dict]]], bool]) -> bool:
    """Seznami predvajanja z drugih naprav v Safeer Linku (core/seznami_sink.py). Naprave vprasa Safeer Control
    (`lists.get`, samo branje); `uskladi` je MediaCenter.seznami_uskladi. Klic iz delovne niti. Vrne True, ce se je
    tukaj kaj spremenilo. Controla zaradi seznamov ne zaganjamo: ce ne tece, naprav v Linku tako ali tako ni."""
    try:
        if not _control_na_vodilu(Gio.bus_get_sync(Gio.BusType.SESSION, None)):
            return False
    except Exception:  # noqa: BLE001
        return False
    spremenjeno = False
    for n in (_control_naprave("Seznam").get("naprave") or [])[:32]:
        zmoznosti = n.get("zmoznosti") or []
        # Samo naprave, ki same povedo, da znajo sezname ("lists"): starejsa razlicica dejanja ne pozna.
        if n.get("ta") or not n.get("id") or "remote" not in zmoznosti or "lists" not in zmoznosti:
            continue

        def vprasaj(parametri: dict, _id: str = str(n["id"])) -> Optional[dict]:
            r = _control_naprave("Ukaz", _id, "lists.get", json.dumps(parametri or {}))
            return r.get("data") if r.get("ok") and isinstance(r.get("data"), dict) else None
        try:
            if uskladi(vprasaj):
                spremenjeno = True
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] seznami z naprave:", e, flush=True)
    return spremenjeno


def _knjiznica() -> "knjiznica_kroga.Knjiznica":
    """Polica »Na tvojih napravah« v Medijskem centru: naprave v Linku vprasa Safeer Control (Controla zaradi police
    ne zaganjamo: ce ne tece, naprav v Linku ni - prenosi motorja Safeer OS na tem racunalniku so na polici vseeno)."""
    def naprave() -> list:
        try:
            if not _control_na_vodilu(Gio.bus_get_sync(Gio.BusType.SESSION, None)):
                return []
        except Exception:  # noqa: BLE001
            return []
        return _control_naprave("Seznam").get("naprave") or []

    def ukaz(id_naprave: str, dejanje: str, parametri: dict, _cas: float) -> dict:
        return _control_naprave("Ukaz", id_naprave, dejanje, json.dumps(parametri or {}))
    return knjiznica_kroga.Knjiznica(naprave, ukaz)


def _control_naprave_koda(_metoda: str) -> str:
    """Control ni odgovoril s stanjem (ne tece ali stara razlicica brez klepeta)."""
    return "ni_controla"


_ANDROID_SKUPINE = (
    ("igre", ("game", "games", "unity", "rovio", "supercell", "king.", "gameloft", "ea.", "minecraft", "roblox")),
    ("splet", ("browser", "chrome", "firefox", "safeer", "youtube", "netflix", "spotify", "tv", "video", "music", "radio")),
    ("pisarna", ("docs", "office", "sheets", "calendar", "mail", "notes", "keep", "drive", "pdf")),
    ("predstavnost", ("photo", "gallery", "camera", "media", "player", "vlc", "kodi", "plex")),
    ("sistem", ("settings", "android.", "google.android", "launcher", "samsung.", "philips", "tv.settings")),
)


def _skupina_paketa(paket: str) -> str:
    p = str(paket or "").lower()
    for skupina, kljuci in _ANDROID_SKUPINE:
        if any(k in p for k in kljuci):
            return skupina
    return "drugo"


def naprave_s_programi(izid: Optional[dict] = None) -> list:
    """Naprave v Safeer Linku, ki znajo nasteti in zagnati programe (zmoznost apps ali remote); brez tega
    racunalnika (njegovi programi so ze v meniju). izid: ze prebran seznam (Control "Seznam"), sicer ga vprasa."""
    izid = _control_naprave("Seznam") if izid is None else izid
    naprave = []
    for n in izid.get("naprave") or []:
        z = n.get("zmoznosti") or []
        # Preskoci samo ta racunalnik. Prej je bila izpuscena vsaka naprava vrste "control", zato Linux ni
        # videl programov racunalnika z Windows (ta se v Link prijavi kot Safeer Control).
        if n.get("ta") or n.get("platforma") == "linux" and socket.gethostname() in n.get("ime", ""):
            continue
        # Samo ozji krog zaupanja (lastnik, 17. 10. 2026): naprave izven njega za ogled programov ne vidimo.
        if ("apps" in z or "remote" in z) and n.get("ozji"):
            naprave.append({"id": n["id"], "ime": n.get("ime", ""), "platforma": n.get("platforma", ""),
                            "vrsta": n.get("vrsta", "")})
    return naprave


def vse_naprave(izid: Optional[dict] = None) -> list:
    """Vse naprave v Safeer Linku (tudi ta racunalnik) za stran Naprave: id, ime, platforma, vrsta, ta."""
    izid = _control_naprave("Seznam") if izid is None else izid
    return [{"id": n.get("id", ""), "ime": n.get("ime", ""), "platforma": n.get("platforma", ""),
             "vrsta": n.get("vrsta", ""), "ta": bool(n.get("ta")), "ozji": bool(n.get("ozji") or n.get("ta"))}
            for n in izid.get("naprave") or [] if n.get("id")]


def _magnet_klic(delo) -> dict:
    """Klic motorja za magnet: napaka gre strani kot kratka koda (prevede jo stran)."""
    try:
        izid = delo()
        return dict(izid, ok=True) if isinstance(izid, dict) else {"ok": bool(izid)}
    except os_torrent.NapakaTorrenta as e:
        return {"ok": False, "koda": str(e)}
    except Exception as e:  # noqa: BLE001
        print("[SafeerOS] magnet:", e)
        return {"ok": False, "koda": "napaka"}


def _magnet_dodaj(uri: str, izbrane: list, potrjene: list) -> int:
    """Uporabnik je torrent dodal sam (Magnet povezave): ostane, dokler ga sam ne odstrani - tudi ce je prej nastal
    kot prenos zaradi gledanja v Medijskem centru (tega po 48 urah brez predvajanja odstranimo sami)."""
    tid = os_torrent.torrenti().dodaj(uri, izbrane, potrjene)
    m = os_torrent.razcleni_magnet(uri)
    if m is not None:
        os_torrent_tok.obdrzi(m["hash"])
    return tid


def naprave_za_magnet() -> list:
    """Naprave v Linku, ki znajo odpreti magnet (zmoznost "magnet"): tja lahko pošljemo povezavo."""
    izid = _control_naprave("Seznam")
    return [{"id": n.get("id", ""), "ime": n.get("ime", ""), "platforma": n.get("platforma", "")}
            for n in izid.get("naprave") or [] if n.get("id") and not n.get("ta") and "magnet" in (n.get("zmoznosti") or [])]


def magnet_privzeto(nastavi: Optional[bool] = None) -> bool:
    """Ali magnet povezave odpira Safeer OS (xdg-mime); z nastavi=True ga naredi za privzetega."""
    # Ime vnosa je odvisno od namestitve (install_os_payload.sh: <ID>.Magnet.desktop; ID je "safeer-os" ali APP_ID).
    mape = [os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")] + \
        (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
    vnos = next((ime for ime in ("safeer-os.Magnet.desktop", APP_ID + ".Magnet.desktop")
                 for m in mape if os.path.isfile(os.path.join(m, "applications", ime))), "")
    if not vnos:
        return False
    try:
        return _privzeti_za_shemo("magnet", vnos if nastavi else "") == vnos
    except Exception:
        return False


def _privzeti_za_shemo(shema: str, nastavi: str = "") -> str:
    """Privzeti program (vnos .desktop) za povezave sheme; z `nastavi` ga prej nastavi. V procesu (GIO - isto kot
    xdg-mime na Cinnamonu, ki klice gio mime), xdg-mime ostane rezerva in pot v Flatpaku in AppImage. Meritev
    19. 10. 2026 v commitu: xdg-mime je lupinska skripta, ki zazene se gio (vsak zagon Safeer OS za stremio)."""
    from core import os_odpri_z
    vrsta = "x-scheme-handler/" + shema
    if nastavi and not os_odpri_z.nastavi_v_procesu(vrsta, nastavi):
        subprocess.run(["xdg-mime", "default", nastavi, vrsta], timeout=10, check=False,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    v_procesu = os_odpri_z.programi_v_procesu(vrsta)
    if v_procesu is not None:
        return v_procesu[0]
    r = subprocess.run(["xdg-mime", "query", "default", vrsta], timeout=10, capture_output=True, text=True)
    return r.stdout.strip()


def stremio_privzeto() -> str:
    """Povezave »Install« (stremio://) odpira Safeer OS, ce jih ne odpira se nihce (npr. aplikacija Stremio): tako
    gumb na strani z dodatki deluje tudi v drugem brskalniku. Obstojece izbire ne spremenimo. Vrne privzeti vnos."""
    mape = [os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")] + \
        (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
    vnos = next((ime for ime in ("safeer-os.Stremio.desktop", APP_ID + ".Stremio.desktop")
                 for m in mape if os.path.isfile(os.path.join(m, "applications", ime))), "")
    try:
        zdaj = _privzeti_za_shemo("stremio")
        if not zdaj and vnos:
            _privzeti_za_shemo("stremio", vnos)
            return vnos
        return zdaj
    except Exception:
        return ""


def naprave_z_datotekami(izid: Optional[dict] = None) -> list:
    """Druge naprave v Linku, ki delijo datoteke (zmoznost "files"): za Safeer Media -> Naprave."""
    izid = _control_naprave("Seznam") if izid is None else izid
    return [{"id": n.get("id", ""), "ime": n.get("ime", ""), "platforma": n.get("platforma", ""),
             "vrsta": n.get("vrsta", "")}
            for n in izid.get("naprave") or [] if n.get("id") and not n.get("ta") and n.get("ozji")
            and "files" in (n.get("zmoznosti") or [])]


def naprave_za_posiljanje() -> list:
    """Druge naprave v Linku, ki sprejmejo datoteko (zmoznost "file"): cilji za »Poslji na napravo« v Datotekah.
    Zadnja naprava, ki ji je uporabnik poslal, je prva (lastnik, 18. 10. 2026: en klik)."""
    from core import link_posiljanje
    izid = _control_naprave("Seznam")
    return [{"id": n.get("id", ""), "ime": n.get("ime", ""), "platforma": n.get("platforma", ""),
             "vrsta": n.get("vrsta", "")}
            for n in link_posiljanje.razvrsti([n for n in izid.get("naprave") or [] if n.get("id") and not n.get("ta")
                                               and "file" in (n.get("zmoznosti") or [])])]


def pretvorba_za_tv_mozna(najdi=None) -> dict:
    """»Pretvori za televizor« dela, ce tece Safeer Control in video pretvori ta racunalnik (ffmpeg, rezerva v
    core/link_pretvorba._lokalno) ali naprava v Linku, ki pretvorbo zna (ne namizna, z datotekami - kot
    razvrsti_naprave). Brez tega vnos ne bi deloval (lastnik, 15. 10. 2026: »nimamo nedelujocih ikon«).
    "shramba": »Shrani na napravo« dela samo z enako napravo (core/link_shramba: ne namizna, z datotekami) - brez
    rezerve na tem racunalniku, zato ffmpeg tu ne steje."""
    namizne = ("linux", "windows", "macos")     # core/link_pretvorba.NAMIZNE (modul je v paketu Controla, ne OS)
    izid = _control_naprave("Seznam")
    if not izid.get("ok"):
        return {"ok": False, "shramba": False, "koda": izid.get("koda") or "ni_controla"}
    naprave = [n for n in izid.get("naprave") or [] if not n.get("ta") and "files" in (n.get("zmoznosti") or [])
               and n.get("platforma") not in namizne]
    import shutil
    lokalno = bool((najdi or shutil.which)("ffmpeg"))
    return {"ok": lokalno or bool(naprave), "lokalno": lokalno, "naprave": len(naprave), "shramba": bool(naprave)}


def datoteke_naprave(id_naprave: str, mapa: str = "") -> dict:
    """Mapa druge naprave (files.list prek Controla): vnosi, streznik za tok in kljuc naprave iz kroga. Samo naprave
    v ozjem krogu zaupanja (lastnik, 17. 10. 2026)."""
    if not _v_ozjem_krogu(str(id_naprave or "")):
        return {"ok": False, "koda": "ni_ozji_krog", "items": []}
    return _control_naprave("Datoteke", str(id_naprave or ""), str(mapa or ""))


def nadaljuj_tukaj(streznik: dict, kljuc: str, oznaka: str, id_naprave: str, ime_naprave: str, pot_imen: list,
                   zaganjalnik=None) -> dict:
    """»Nadaljuj tukaj«: datoteko z druge naprave shrani sem s prenosom samo spremenjenih kosov (core/link_nadaljuj) in
    jo odpre. V ozadju (omrezje in disk). Vrne meritve za stran (preneseno, iz_lokalnih, cas ...) in kako se je odprla.

    Teamwork (core/link_teamwork): delovno kopijo spremlja Safeer Control - shranitve gredo napravi lastnika, nove
    razlicice pridejo sem, kdo jo se ureja, pove obvestilo. Program: isti kot pri lastniku, ce je tu namescen; sicer
    program, ki format podpira; ce ga ni, se datoteka odpre na napravi lastnika in tu se pokaze njen zaslon."""
    from core import link_nadaljuj, link_teamwork
    moje_ime = ""
    if link_nadaljuj.IME_MAPE in [str(x) for x in pot_imen]:
        # Datoteka, ki se vraca (A -> B -> A): ime tega racunalnika v Linku pove, kje je izvirnik.
        moje_ime = next((str(n.get("ime") or "") for n in _control_naprave("Seznam").get("naprave") or [] if n.get("ta")), "")
    izid = link_nadaljuj.nadaljuj_tukaj(streznik, kljuc, oznaka, id_naprave, ime_naprave, pot_imen, moje_ime=moje_ime,
                                        odpri=lambda _p: True)
    if not izid.get("ok"):
        return izid
    pot = str(izid.get("pot") or "")
    program_lastnika = ""
    if not izid.get("izvirnik"):
        tw = _control_naprave("Teamwork", json.dumps({
            "naprava": str(id_naprave), "ime_naprave": str(ime_naprave), "oznaka": str(oznaka),
            "pot_imen": [str(x) for x in pot_imen], "pot": pot, "streznik": streznik if isinstance(streznik, dict) else {}}))
        program_lastnika = str(tw.get("program") or "")
        izid["teamwork"] = {"podprto": bool(tw.get("podprto")), "drugi": [str(x) for x in tw.get("drugi") or []]}
    from core import os_odpri_z
    izbira = link_teamwork.izberi_program(pot, program_lastnika, os_odpri_z.programi_za)
    izid["nacin"], izid["program"] = izbira["nacin"], izbira["ime"]
    izid["odprto"] = False
    if izbira["nacin"] in ("isti", "podprt"):
        izid["odprto"] = bool(os_odpri_z.odpri_z([pot], izbira["program"], zaganjalnik=zaganjalnik).get("ok"))
        if not izid["odprto"]:
            from core import os_datoteke
            izid["odprto"] = bool(os_datoteke.odpri(pot))
    elif not izid.get("izvirnik"):
        # Tu ni programa za ta format: datoteka se odpre na napravi lastnika (na locenem zaslonu, ce ga ima) in tu se
        # pokaze njen zaslon - urejas na njej.
        r = _control_naprave("Ukaz", str(id_naprave), "files.open_locen", json.dumps({"id": str(oznaka)}))
        if not r.get("ok"):
            r = _control_naprave("Ukaz", str(id_naprave), "files.open", json.dumps({"id": str(oznaka)}))
        if r.get("ok"):
            izid["odprto"] = bool(upravljaj_racunalnik(str(id_naprave)).get("ok"))
    return izid


def prenesi_datoteko_naprave(id_naprave: str, oznaka: str, ime: str, streznik: dict, mape: list,
                             zaganjalnik=None) -> dict:
    """Lupina QML (Datoteke, ista kot na Windows): datoteka z druge naprave pride sem in se odpre - to je »Nadaljuj
    tukaj« s Teamworkom (prenos samo sprememb, shranitve gredo nazaj, isti/podprt program ali zaslon naprave).
    Kljuc za Global Link in ime naprave poiscemo tu; QML jih nima."""
    kljuc = ""
    try:
        from core import link_krog
        kljuc = str((link_krog.krog().clan_za_id(str(id_naprave)) or {}).get("kljuc") or "")
    except Exception:  # noqa: BLE001 - doma gre brez kljuca
        kljuc = ""
    ime_naprave = next((str(n.get("ime") or "") for n in _control_naprave("Seznam").get("naprave") or []
                        if n.get("id") == id_naprave), "") or str(id_naprave)
    pot_imen = [str(x) for x in (mape or []) if str(x or "").strip()][:31] + [str(ime or "")]
    return nadaljuj_tukaj(streznik if isinstance(streznik, dict) else {}, kljuc, str(oznaka), str(id_naprave),
                          ime_naprave, pot_imen, zaganjalnik)


def odpri_na_napravi_tukaj(id_naprave: str, oznaka: str) -> dict:
    """Lupina QML: datoteko odpre program naprave (na locenem zaslonu, ce ga ima) in tu se pokaze njen zaslon."""
    r = _control_naprave("Ukaz", str(id_naprave), "files.open_locen", json.dumps({"id": str(oznaka)}))
    if not r.get("ok"):
        if r.get("koda") != "ni_locenega_zaslona":
            return {"ok": False, "koda": str(r.get("koda") or ""), "message": str(r.get("message") or "")}
        r = _control_naprave("Ukaz", str(id_naprave), "files.open", json.dumps({"id": str(oznaka)}))
        if not r.get("ok"):
            return {"ok": False, "koda": str(r.get("koda") or ""), "message": str(r.get("message") or "")}
    return upravljaj_racunalnik(str(id_naprave))


def preimenuj_napravo(id_naprave: str, ime: str) -> dict:
    """Novo ime naprave (tudi tega racunalnika) za vse naprave v Linku; hrani ga sredisce."""
    return _control_naprave("Preimenuj", str(id_naprave or ""), str(ime or ""))


def _v_ozjem_krogu(id_naprave: str) -> bool:
    """Ali je naprava v ozjem krogu zaupanja tega racunalnika (polje »ozji« iz Controla)."""
    izid = _control_naprave("Seznam")
    return any(n.get("id") == id_naprave and n.get("ozji") for n in izid.get("naprave") or [])


def upravljaj_racunalnik(id_naprave: str) -> dict:
    """Safeer Control pridobi dovoljenje in odpre oddaljeni zaslon izbranega racunalnika - samo v ozjem krogu."""
    if not _v_ozjem_krogu(str(id_naprave or "")):
        return {"ok": False, "koda": "ni_ozji_krog"}
    return _control_naprave("Upravljaj", str(id_naprave or ""))


def programi_naprave(id_naprave: str) -> dict:
    """Programi ene naprave v obliki, kot jo ima stran (ikone kot data URL). Samo ozji krog zaupanja."""
    if not _v_ozjem_krogu(str(id_naprave or "")):
        return {"ok": False, "koda": "ni_ozji_krog", "programi": []}
    izid = _control_naprave("Aplikacije", str(id_naprave or ""))
    if not izid.get("ok"):
        return {"ok": False, "koda": izid.get("koda", ""), "programi": []}
    programi = []
    for e in izid.get("items") or []:
        if not isinstance(e, dict) or not e.get("id"):
            continue
        ikona = str(e.get("icon") or "")
        if not ikona and e.get("icon_png"):
            ikona = "data:image/png;base64," + str(e["icon_png"])
        if ikona and not ikona.startswith("data:image/"):
            ikona = ""
        programi.append({"id": str(e["id"]), "ime": str(e.get("name") or e["id"]), "opis": str(e.get("comment") or ""),
                         "skupina": str(e.get("group") or _skupina_paketa(e["id"])), "ikona": ikona,
                         "naprava": str(id_naprave)})
    return {"ok": True, "programi": programi, "deli": bool(izid.get("enabled", True)),
            "access_request": str(izid.get("access_request") or "")}


def zazeni_na_napravi(id_naprave: str, app: str) -> dict:
    """Program zazene na sami napravi in ohrani njeno sporocilo ob napaki."""
    return _control_naprave("Zazeni", str(id_naprave or ""), str(app or ""))


def naprave_za_medij() -> list:
    """Naprave v Linku, na katerih lahko lupa »prikaze« film ali glasbo (media.open): vse z daljincem razen te."""
    izid = _control_naprave("Seznam")
    return [{"id": n.get("id"), "ime": n.get("ime") or n.get("id"), "platforma": n.get("platforma") or ""}
            for n in (izid.get("naprave") or []) if n.get("id") and not n.get("ta") and "remote" in (n.get("zmoznosti") or [])]


def odpri_medij_na(id_naprave: str, medij: str) -> dict:
    """»Prikazi na TV«: naslov odpre Medijski center izbrane naprave (Link media.open prek Controla)."""
    try:
        m = json.loads(medij or "{}")
    except ValueError:
        return {"ok": False, "koda": "prazno"}
    return _control_naprave("Ukaz", str(id_naprave or ""), "media.open", json.dumps(m if isinstance(m, dict) else {}))


def odpri_tukaj(id_naprave: str, app: str) -> dict:
    """Napravo prosi za zagon programa in pretakanje zaslona na ta racunalnik."""
    return _control_naprave("OdpriTukaj", str(id_naprave or ""), str(app or ""))


#: »Safeer od vklopa« (zagonski in prijavni zaslon v videzu Safeer) je del paketa safeer-cinnamon: pomocnik s
#: skrbniskimi pravicami si zapomni prejsnje stanje v /var/lib in ga ob izklopu vrne.
OD_VKLOPA_POMOCNIK = "/usr/lib/safeer-cinnamon/od-vklopa"
OD_VKLOPA_STANJE = "/var/lib/safeer-cinnamon/od-vklopa.json"


def od_vklopa_stanje() -> dict:
    """Ali je »Safeer od vklopa« na voljo (namescen paket s pomocnikom) in ali je vklopljen."""
    return {"na_voljo": os.access(OD_VKLOPA_POMOCNIK, os.X_OK) and bool(_ukaz_safeer_cinnamon()),
            "vklopljeno": os.path.exists(OD_VKLOPA_STANJE)}


def od_vklopa(vklop: bool) -> dict:
    """Vklop ali izklop prek ukaza safeer-cinnamon: ta vprasa za skrbnisko geslo (pkexec) in uporabniku sam
    sporoci izid. Vrne stanje, kakrsno je po tem res (brez gesla ostane, kot je bilo)."""
    ok = False
    if od_vklopa_stanje()["na_voljo"]:
        try:
            r = subprocess.run(_ukaz_safeer_cinnamon() + ["--od-vklopa" if vklop else "--od-vklopa-izklopi"],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=900)
            ok = r.returncode == 0
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] od vklopa:", e)
    return dict(od_vklopa_stanje(), ok=ok)


def videz_cinnamon() -> dict:
    """Videz Safeer Cinnamon za delovno povrsino: ali je vklopljen ter ali veljata kontrast (brez prosojnosti) in
    vecje besedilo. Stikali delovne povrsine upravljata ISTO nastavitev kot ukaz safeer-cinnamon (tema lupine in
    programov, velikost besedila sistema) - prej je imela delovna povrsina svoji, ki se s sistemom nista ujemali."""
    from shutil import which
    mapa = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "safeer-cinnamon")
    stanje = {"naVoljo": bool(which("safeer-cinnamon")) and os.path.exists(os.path.join(mapa, "vklopljeno")),
              "kontrast": False, "vecjiTekst": False}
    if not stanje["naVoljo"]:
        return stanje
    try:
        vir = Gio.SettingsSchemaSource.get_default()
        if vir is not None and vir.lookup("org.cinnamon.theme", True) is not None:
            stanje["kontrast"] = "Kontrast" in Gio.Settings.new("org.cinnamon.theme").get_string("name")
        if vir is not None and vir.lookup("org.cinnamon.desktop.interface", True) is not None:
            povecava = Gio.Settings.new("org.cinnamon.desktop.interface").get_double("text-scaling-factor")
            stanje["vecjiTekst"] = povecava >= 1.15
            stanje["tekstOdstotek"] = int(round(povecava * 100))
    except Exception as e:  # noqa: BLE001
        print("[SafeerOS] videz:", e)
    return stanje


def videz_cinnamon_nastavi(kaj: str, vklop) -> dict:
    """Stikalo delovne povrsine: kaj = "kontrast" | "tekst". Pri besedilu je vklop lahko odstotek (100, 125, 150, 175,
    200 - 200 % za ogled od dalec, npr. TV s kavca). Vrne stanje, kakrsno je po tem res."""
    dodatno: list = []
    if kaj == "tekst" and not isinstance(vklop, bool) and str(vklop).isdigit() and int(vklop) in (100, 125, 150, 160, 175, 200):
        ukaz = "--obicajen-tekst" if int(vklop) == 100 else "--vecji-tekst"
        dodatno = [] if int(vklop) == 100 else [str(int(vklop))]
    else:
        ukaz = {("kontrast", True): "--kontrast", ("kontrast", False): "--prosojno",
                ("tekst", True): "--vecji-tekst", ("tekst", False): "--obicajen-tekst"}.get((kaj, bool(vklop)))
    if ukaz and videz_cinnamon()["naVoljo"]:
        try:
            subprocess.run(["safeer-cinnamon", ukaz, *dodatno], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, timeout=30)
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] videz:", e)
    return videz_cinnamon()


SAMOZAGON = os.path.join((os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")),
                         "autostart", "safeer-os.desktop")


def _ukaz_os() -> str:
    from shutil import which
    if which("safeer-os"):
        return "safeer-os"
    return okolje_procesa.python_niz(os.path.join(KOREN, "safeer_os.py"))


def _mapa_nastavitev() -> str:
    return en_proces.mapa_nastavitev_racunalnika()


def _safeer_cinnamon_vklopljen() -> bool:
    """Safeer Cinnamon je vklopljen (katerakoli postavitev): Safeer OS iz menija se odpre kot okno (main)."""
    return os.path.isfile(os.path.join(_mapa_nastavitev(), "safeer-cinnamon", "vklopljeno"))


def delovna_safeer_cinnamon() -> bool:
    return en_proces.delovna_safeer_cinnamon()


def _pot_samozagona() -> str:
    """Kam pisemo vnos zagona ob prijavi: ob delovni povrsini Safeer Cinnamon v shranjeno kopijo, ki jo izklop Safeer
    Cinnamon vrne (zagoni_vrni) - zapis v autostart bi prepisal skriti vnos in ob prijavi bi se Safeer OS zagnal
    dvakrat (pregled celovitosti 15. 10. 2026)."""
    if delovna_safeer_cinnamon():
        return os.path.join(_mapa_nastavitev(), "safeer-cinnamon", "zagoni", "safeer-os.desktop")
    return SAMOZAGON


def _vnos_vklopljen(pot: str) -> bool:
    try:
        with open(pot, encoding="utf-8") as f:
            vsebina = f.read()
    except OSError:
        return False
    return "X-GNOME-Autostart-enabled=false" not in vsebina and "Hidden=true" not in vsebina


def je_samozagon() -> bool:
    """Ali se Safeer OS zazene ob prijavi v racunalnik (~/.config/autostart, vidno tudi v Mintovih
    »Zagonskih programih«, kjer ga uporabnik lahko izklopi). Ob delovni povrsini Safeer Cinnamon vedno da: zazene ga
    seja safeer-cinnamon (izklop je »Nazaj v Linux Mint« → »Ne zaganjaj več ob prijavi«)."""
    return delovna_safeer_cinnamon() or _vnos_vklopljen(SAMOZAGON)


def nastavi_samozagon(vklop: bool) -> bool:
    """Vklop zapise vnos; izklop ga pusti z X-GNOME-Autostart-enabled=false (preglasi tudi sistemski
    vnos iz paketa, ko bo Safeer OS namescen kot .deb). Ob delovni povrsini Safeer Cinnamon gre zapis v kopijo, ki
    jo vrne izklop Safeer Cinnamon (_pot_samozagona)."""
    pot = _pot_samozagona()
    vnos = ("[Desktop Entry]\nType=Application\nName=Safeer OS\n"
            "Comment=Safeer OS ob prijavi v racunalnik\nComment[sl]=Safeer OS ob prijavi v računalnik\n"
            "Exec=%s\nIcon=%s\nTerminal=false\nX-GNOME-Autostart-enabled=%s\nX-GNOME-Autostart-Delay=2\n"
            % (_ukaz_os(), os.path.join(KOREN, "assets", "os", "znak.svg"), "true" if vklop else "false"))
    try:
        os.makedirs(os.path.dirname(pot), exist_ok=True)
        with open(pot + ".tmp", "w", encoding="utf-8") as f:
            f.write(vnos)
        os.replace(pot + ".tmp", pot)
        if pot != SAMOZAGON:
            try:   # oznaka »vnosa ni bilo«: izklop Safeer Cinnamon naj zdaj vrne ta vnos, ne izbrise ga
                os.remove(pot + ".ni")
            except FileNotFoundError:
                pass
        return True
    except OSError:
        return False


def uredi_samozagon_ob_zagonu(shramba) -> bool:
    """Safeer OS se ob prijavi zazene samo, ce je uporabnik to SAM vklopil v Nastavitvah (»Zaženi ob prijavi v
    računalnik«). Do razlicice 0.4.64 si je program zagon ob prijavi ob prvem odprtju vklopil sam.

    Enkratna selitev: kjer je vklopljen, uporabnik pa ga ni izbral s stikalom (zapisa `samozagon_izbral` se ni), ga
    izklopimo - vnos ostane, izklopljen. Potem velja samo stikalo. Vrne True, ce je bil ob tem izklopljen."""
    if shramba.get("samozagon_izbral") is not None:
        return False
    izklopljen = False
    if _vnos_vklopljen(_pot_samozagona()):
        izklopljen = nastavi_samozagon(False)
        if not izklopljen:
            return False                # vnosa ni bilo mogoce zapisati: poskusimo ob naslednjem zagonu
    shramba.set("samozagon", False)
    shramba.set("samozagon_izbral", False)
    return izklopljen


# ---------------------------------------------------------------------- Mintov pult
#: Visina Safeerjeve vrstice spodaj (tocke GDK). Programi se z najvecjim oknom ustavijo nad njo.
VISINA_VRSTICE = 64
#: Mintov pult ne izbrisemo (Cinnamon bi takoj vprasal »Nimate dodanih pultov«), ampak ga samodejno
#: skrijemo in mu nastavimo zelo dolg zamik prikaza - ostane, a se ne pokaze.
_PULT_KLJUCI = ("panels-autohide", "panels-show-delay")
SKRIT_ZAMIK_MS = 86_400_000
#: Varni nacin (ponovljena sesutja): brez seznama oken in brez skrivanja Mintovega pulta.
VARNI_NACIN = False


def _gsettings(*argumenti) -> Optional[str]:
    try:
        r = subprocess.run(["gsettings"] + list(argumenti), capture_output=True, text=True, timeout=4)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def _seznam(vrednost: Optional[str]) -> list:
    """GVariant 'as' (npr. "['1:0:bottom']" ali "@as []") v Pythonov seznam nizov."""
    import ast
    v = (vrednost or "").strip()
    if v.startswith("@as"):
        v = v[3:].strip()
    try:
        s = ast.literal_eval(v)
        return [str(x) for x in s] if isinstance(s, (list, tuple)) else []
    except Exception:
        return []


def _gv(seznam: list) -> str:
    return "[" + ", ".join("'%s'" % x.replace("'", "") for x in seznam) + "]"


def skrij_mintov_pult(shramba) -> None:
    """V namiznem nacinu je spodaj Safeerjeva vrstica, zato se Mintov pult ne kaze. Prvotne vrednosti
    si zapomnimo v os.json (samo, ce jih ze nismo), da jih »Nazaj v Linux Mint« - ali naslednji
    zagon po sesutju - vrne."""
    idji = [p.split(":")[0] for p in _seznam(_gsettings("get", "org.cinnamon", "panels-enabled"))]
    if not idji:
        return
    if not shramba.get("mintov_pult"):
        shramba.set("mintov_pult", {k: _gsettings("get", "org.cinnamon", k) for k in _PULT_KLJUCI})
    _gsettings("set", "org.cinnamon", "panels-autohide", _gv(["%s:true" % i for i in idji]))
    _gsettings("set", "org.cinnamon", "panels-show-delay", _gv(["%s:%d" % (i, SKRIT_ZAMIK_MS) for i in idji]))


def vrni_mintov_pult(shramba) -> None:
    """Vrne Mintov pult na vrednosti pred skrivanjem. Klic je idempotenten: ce ni nicesar shranjenega,
    ne naredi nicesar, zato ga sme poklicati vsak (konec, --vrni-mint, zaganjalnik po sesutju)."""
    prej = shramba.get("mintov_pult")
    if not isinstance(prej, dict):
        return
    ok = True
    for kljuc in _PULT_KLJUCI:
        if prej.get(kljuc) is not None and _gsettings("set", "org.cinnamon", kljuc, prej[kljuc]) is None:
            ok = False
    if ok:
        shramba.set("mintov_pult", None)


def pult_je_skrit(shramba) -> bool:
    """Ali je v shrambi zapis, da Safeer OS trenutno skriva Mintov pult (= prejsnji zagon se ni koncal)."""
    return isinstance(shramba.get("mintov_pult"), dict)


def popravi_po_sesutju(shramba) -> bool:
    """Ce je prejsnji zagon pustil Mintov pult skrit (sesutje, OOM, izklop), ga najprej vrnemo.

    Brez tega je uporabnik po sesutju Safeer OS ostal pred namizjem brez pulta in brez menija - tocno
    to se je zgodilo 20. 9. 2026. Mint pod masko mora ostati varnostna mreza, ne talec.
    """
    if not pult_je_skrit(shramba):
        return False
    vrni_mintov_pult(shramba)
    return True


# ---------------------------------------------------------------------- vodnik ob prvem zagonu
def oznaci_vodnik(shramba) -> bool:
    """Vodnik ob prvem zagonu (jezik, racuni, Scit, Link) se pokaze samo novi namestitvi: shramba os.json je ob
    zagonu prazna. Kdor Safeer OS ze uporablja (shramba ima karkoli), ga ob posodobitvi ne dobi vsiljenega (lastnik,
    17. 10. 2026). Klic mora biti pred prvim zapisom v shrambo (uredi_samozagon_ob_zagonu pise ob vsakem zagonu).
    Vrne True, ce naj se vodnik pokaze; znova ga uporabnik odpre v Nastavitvah."""
    if shramba.get("vodnik") is None:
        shramba.set("vodnik", "caka" if not getattr(shramba, "podatki", None) else "ni_potreben")
    return shramba.get("vodnik") == "caka"


# ---------------------------------------------------------------------- nazaj na Cinnamon
def _profil_safeer_cinnamon() -> str:
    """Postavitev Safeer Cinnamon (videz | dock | delovna) ali "", ce ni vklopljen."""
    mapa = os.path.join(_mapa_nastavitev(), "safeer-cinnamon")
    if not os.path.isfile(os.path.join(mapa, "vklopljeno")):
        return ""
    try:
        with open(os.path.join(mapa, "profil"), encoding="utf-8") as f:
            profil = f.read().strip()
    except OSError:
        profil = ""
    return profil if profil in ("videz", "dock", "delovna") else "videz"


def _ukaz_safeer_cinnamon() -> list:
    """safeer-cinnamon z absolutno potjo (/usr/bin), ne po PATH: --od-vklopa in --izklopi vprasata za skrbnisko geslo
    (pkexec) - podtaknjen safeer-cinnamon v ~/.local/bin bi ga dobil (koncni neodvisni pregled, 19. 10. 2026)."""
    from core import root_ukaz
    pot = root_ukaz.sistemski_program("safeer-cinnamon")
    return [pot] if pot else []


def nazaj_na_cinnamon(shramba, pocakaj: bool = True) -> dict:
    """Pot nazaj na obicajno namizje Cinnamon (lastnik, 17. 10. 2026), brez roota in brez odstranjevanja paketov:
    Safeer OS se ne zazene vec ob prijavi, Mintov pult se vrne in safeer-cinnamon --izklopi vrne temo, pult, dock,
    ozadje in zagone iz shranjenega prejsnjega stanja. Ce je vklopljen »Safeer od vklopa« (zagonski in prijavni zaslon),
    ga --izklopi vrne tudi - sistem vpraša za skrbnisko geslo (pkexec; lastnik, 17. 10. 2026: »Da«). Brez gesla ostaneta.

    Prejsnjo postavitev si zapomnimo, da jo Safeer OS iz menija ponudi vrniti (vrni_safeer_os). pocakaj=False:
    safeer-cinnamon tece loceno, ker --izklopi konca tudi proces z delovno povrsino (to je lahko klicatelj)."""
    profil = _profil_safeer_cinnamon()
    if shramba.get("nazaj_na_cinnamon") is None or profil:
        shramba.set("nazaj_na_cinnamon", {"profil": profil})
    nastavi_samozagon(False)                 # pred --izklopi: ob delovni povrsini gre zapis v kopijo, ki jo izklop vrne
    shramba.set("samozagon", False)
    shramba.set("samozagon_izbral", True)
    vrni_mintov_pult(shramba)
    ukaz = _ukaz_safeer_cinnamon()
    if ukaz and profil:
        okolje = dict(os.environ)   # brez SAFEER_CINNAMON_BREZ_SISTEMA: --izklopi vrne tudi »Safeer od vklopa« (geslo)
        try:
            if pocakaj:
                subprocess.run(ukaz + ["--izklopi"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, env=okolje, timeout=120)
            else:
                subprocess.Popen(ukaz + ["--izklopi"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, env=okolje, start_new_session=True)
        except Exception as e:  # noqa: BLE001 - samozagon in pult sta ze vrnjena
            print("[SafeerOS] safeer-cinnamon --izklopi:", e)
    return {"profil": profil, "safeerCinnamon": bool(ukaz and profil)}


def ukaz_nazaj_na_cinnamon() -> int:
    """`safeer-os --nazaj-na-cinnamon` iz terminala, tudi ce namizje ne dela. Ce Safeer OS tece, to naredi on (ena
    shramba: njegov zapis bi sicer prepisal nas) in se konca; ce ne odgovori, to naredimo tu."""
    try:
        if _predaj_tekocemu("nazaj-na-cinnamon", ""):
            print("Safeer OS vraca namizje Cinnamon in se zapira.")
            return 0
    except Exception as e:  # noqa: BLE001 - ni seje D-Bus ali Safeer OS ne odgovori
        print("[SafeerOS] nazaj na Cinnamon:", e)
    izid = nazaj_na_cinnamon(os_programi.Shramba())
    print("Namizje Cinnamon je vrnjeno; Safeer OS se ne zazene vec ob prijavi." if izid["safeerCinnamon"] else
          "Safeer OS se ne zazene vec ob prijavi; Mintov pult je viden.")
    print("Nazaj na Safeer OS: odpri Safeer OS iz menija.")
    return 0


def vrni_safeer_os(shramba, da: bool) -> bool:
    """Safeer OS iz menija po »Nazaj na Cinnamon«: da = spet ob prijavi (in prejsnja postavitev Safeer Cinnamon),
    ne = samo ta zagon. Vprasanje se pokaze enkrat; True, ce je bilo kaj vrnjeno."""
    prej = shramba.get("nazaj_na_cinnamon")
    shramba.set("nazaj_na_cinnamon", None)
    if not da:
        return False
    nastavi_samozagon(True)
    shramba.set("samozagon", True)
    shramba.set("samozagon_izbral", True)
    profil = prej.get("profil") if isinstance(prej, dict) else ""
    ukaz = _ukaz_safeer_cinnamon()
    if ukaz and profil in ("videz", "dock", "delovna"):
        try:     # delovna: safeer-cinnamon zazene `safeer-os --delovna`, ki se preda temu procesu
            subprocess.Popen(ukaz + ["--profil", profil], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] safeer-cinnamon --profil:", e)
    return True


def _ukaz_controla() -> Optional[list]:
    from shutil import which
    pot = which("safeer-control")
    if pot:
        return [pot]
    skripta = os.path.join(KOREN, "safeer_control.py")
    if os.path.isfile(skripta):
        return okolje_procesa.python_ukaz() + [skripta]
    return None


#: Po negativnem izidu preverbe peskovnika jo ponovimo šele čez toliko sekund (glej SafeerOS._peskovnik_na_voljo).
PESKOVNIK_PONOVNO_S = 30.0


#: Ukazna zastavica za okno Safeer Player (Medijski center v svojem oknu); --predvajaj <datoteka> je nekaj drugega.
#: Plosca Splet na namizju: (naslov, »Odpri v brskalniku«, »Zapri (Esc)«).
BESEDILA_SPLETA_NA_NAMIZJU = {
    "sl": ("Splet", "Odpri v brskalniku", "Zapri (Esc)"),
    "en": ("Web", "Open in browser", "Close (Esc)"),
    "de": ("Web", "Im Browser öffnen", "Schließen (Esc)"),
    "es": ("Web", "Abrir en el navegador", "Cerrar (Esc)"),
    "fr": ("Web", "Ouvrir dans le navigateur", "Fermer (Échap)"),
    "it": ("Web", "Apri nel browser", "Chiudi (Esc)"),
}

ZASTAVICE_PREDVAJALNIKA = ("--predvajalnik", "--player")
#: Ime okna Safeer Player za upravitelja oken (WM_CLASS): po njem ga pult zdruzi z vnosom »Safeer Player«
#: (StartupWMClass v packaging/safeer-player.desktop) in ne z glavnim oknom Safeer OS. Ime je ID vnosa v paketu
#: (safeer-os.Player.desktop), ne »safeer-player«: tako je imenovan lastnikov lokalni prototip
#: (~/.local/share/applications/safeer-player.desktop) in Cinnamon bi okno lahko pripel k njemu.
WMCLASS_PREDVAJALNIKA = ("safeer-os.Player", "Safeer Player")


def _monitor_v_tocki(zasloni, povezava):
    """Gdk.Monitor pod kazalcem miske (X11; povezava = core/x11.povezava()). Geometrija GDK je v logicnih tockah,
    kazalec X v pikah - delimo z merilom monitorja (HiDPI). None brez X11 ali kazalca."""
    if povezava is None or zasloni is None:
        return None
    tocka = povezava.kazalec()
    if tocka is None:
        return None
    for i in range(zasloni.get_n_items()):
        m = zasloni.get_item(i)
        g, merilo = m.get_geometry(), max(1, int(m.get_scale_factor() or 1))
        x, y = tocka[0] / merilo, tocka[1] / merilo
        if g.x <= x < g.x + g.width and g.y <= y < g.y + g.height:
            return m
    return None


def _cas_dogodka(okno=None) -> int:
    """Cas za present_with_time in dejanja oken. GTK4 nima vec »trenutnega dogodka« (Gtk.get_current_event_time), zato
    cas streznika X za dano okno ali katerokoli nase realizirano okno (GdkX11): ta je vedno novejsi od zadnjega klika
    v oknu v ospredju, zato upravljalnik oken (Muffin) okno res pokaze, namesto da ga le oznaci z »zahteva pozornost«.
    Rezerva: milisekunde od zagona - 32-bitno, zato po 49,7 dneh zacne znova (sicer OverflowError)."""
    try:
        if GdkX11 is not None:
            okna = ([okno] if okno is not None else []) + list(Gtk.Window.list_toplevels())
            for o in okna:
                povrsina = o.get_surface() if o is not None and o.get_realized() else None
                if isinstance(povrsina, GdkX11.X11Surface):
                    return GdkX11.x11_get_server_time(povrsina) & 0xFFFFFFFF
    except (ImportError, ValueError, TypeError, AttributeError):
        pass
    return int(GLib.get_monotonic_time() / 1000) & 0xFFFFFFFF


def _v_ospredje(okno) -> None:
    """Okno pokaze in ga da v ospredje s casom uporabe (glej _cas_dogodka). Okno, ki ga je uporabnik zaprl (skrili smo
    ga), GTK ob ponovnem prikazu ne oznaci s casom - Muffin ga potem le oznaci z »zahteva pozornost«."""
    okno.set_visible(True)
    cas = _cas_dogodka(okno)
    povrsina = x11.povrsina_x11(okno)
    if povrsina is not None:
        povrsina.set_user_time(cas)
    okno.present_with_time(cas)


class _Tipka:
    """Tipka iz GTK4 EventControllerKey s polji kot Gdk.EventKey v GTK3 (keyval, state, time)."""
    __slots__ = ("keyval", "state", "time")

    def __init__(self, keyval, state, cas):
        self.keyval, self.state, self.time = keyval, state, cas


def _tipke(gradnik, obdelaj, zajem: bool = False):
    """GTK4 nadomestek za key-press-event: obdelaj(gradnik, dogodek) dobi predmet s .keyval, .state in .time.
    zajem=True: tipko dobimo pred otroki (kot GTK3 okno, ki je tipko videlo pred gradnikom v fokusu)."""
    k = Gtk.EventControllerKey()
    if zajem:
        k.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
    k.connect("key-pressed", lambda kr, keyval, _koda, stanje:
              bool(obdelaj(gradnik, _Tipka(keyval, stanje, kr.get_current_event_time()))))
    gradnik.add_controller(k)
    return k


def _robovi_gradnika(gradnik, rob: int):
    """GTK4 nima set_border_width: rob okoli gradnika."""
    for stran in ("set_margin_start", "set_margin_end", "set_margin_top", "set_margin_bottom"):
        getattr(gradnik, stran)(rob)
    return gradnik


def _css(besedilo) -> "Gtk.CssProvider":
    """Slog za ves zaslon (GTK4: load_from_string, add_provider_for_display)."""
    if isinstance(besedilo, bytes):
        besedilo = besedilo.decode("utf-8")
    ponudnik = Gtk.CssProvider()
    try:
        ponudnik.load_from_string(besedilo)
    except AttributeError:  # GTK < 4.12
        ponudnik.load_from_data(besedilo, -1)
    Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), ponudnik,
                                              Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
    return ponudnik


_PROZORNO_CSS = None


def _prozorno_okno(okno) -> None:
    """Okno brez lastnega ozadja (GTK3: vizual RGBA + app_paintable). GTK4 na X11 s sestavljalnikom risbo okna z
    alfa kanalom pokaze sam - dovolj je prozorno ozadje v slogu."""
    global _PROZORNO_CSS
    if _PROZORNO_CSS is None:
        _PROZORNO_CSS = _css("window.safeer-prozorno { background: transparent; box-shadow: none; }")
    okno.add_css_class("safeer-prozorno")


#: Razred oken Safeer OS za pult (WM_CLASS res_class) - enak StartupWMClass v packaging/safeer-os.desktop.
RAZRED_SAFEER_OS = "safeer-os"

#: Vsako okno Safeer OS ima v pultu in docku svoj vnos (.desktop), svoj razred in svojo ikono. Lastnik, 16. 10. 2026:
#: »na stranskem docku imata Sporocila in Splet enako ikono - uporabnik se zmede«; do 0.4.84 so imela vsa okna razred
#: »safeer-os« in ikono Safeer OS. vloga -> pripona; razred okna (res_name = res_class = StartupWMClass) je
#: »safeer-os.<pripona>«, vnos in ikona v paketu »<ID>.<pripona>« (.deb: safeer-os.splet, Flatpak:
#: io.github.memelandfaner.SafeerOS.splet - Flatpak izvozi samo imena z ID-jem spredaj). Male crke: Plank (bamf)
#: razred okna spremeni v male crke in ga isce med imeni vnosov. Slika ikone je assets/os/<pripona>.svg.
#: Safeer Player ima svoj vnos ze od prej (WMCLASS_PREDVAJALNIKA, packaging/safeer-player.desktop).
OKNA_V_PULTU = ("splet", "sporocila", "zapiski", "nastavitve", "scit")
#: Pod varuhom: stanje za obnovo po sesutju (zavihki, okna, predvajanje) se posname toliko sekund po spremembi.
POSNETEK_STANJA_S = 10
#: Okna, ki sodijo k drugemu programu: Medijski center (stran vira) in njegov dialog sta del Safeer Playerja.
_OKNA_PREDVAJALNIKA = ("Medijski", "Dialog")


def _ime_ikone(imena, slika: str = "") -> str:
    """Prvo ime iz `imena`, ki ga ima tema ikon (ikona iz paketa: .deb »safeer-os…«, Flatpak »<ID>…«). Brez namescenega
    paketa (izvorna mapa) ikona iz assets/os pod imenom `slika`; brez zaslona prvo ime."""
    try:
        tema = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
        for ime in imena:
            if tema.has_icon(ime):
                return ime
        if slika:
            mapa = os.path.join(KOREN, "assets", "os")
            if mapa not in (tema.get_search_path() or []):
                tema.add_search_path(mapa)
            if tema.has_icon(slika):
                return slika
    except Exception:  # noqa: BLE001 - brez zaslona: ime iz paketa .deb
        pass
    return imena[0]


def _ikona_safeer_os(pripona: str = "") -> str:
    """Ime ikone okna Safeer OS (pripona: ».splet« …), kot jo je namestil paket: .deb »safeer-os«, Flatpak ID programa.
    Prej so imela okna ikono »safeer-browser«, ki je brez Safeer Browserja ni (pregled celovitosti 15. 10. 2026)."""
    return _ime_ikone(("safeer-os" + pripona, APP_ID + pripona), pripona.lstrip("."))


def razred_in_ikona(vloga: str = ""):
    """(res_name, res_class, pripona ikone) za okno z vlogo: »« glavno okno, »splet«, »sporocila«, »zapiski«,
    »nastavitve« (velikost crk ni pomembna) ali okno Safeer Playerja. Neznana vloga dobi razred Safeer OS."""
    if vloga in _OKNA_PREDVAJALNIKA:
        return WMCLASS_PREDVAJALNIKA + (".Player",)
    pripona = vloga.lower()
    if pripona in OKNA_V_PULTU:
        razred = RAZRED_SAFEER_OS + "." + pripona
        return razred, razred, "." + pripona
    return RAZRED_SAFEER_OS, RAZRED_SAFEER_OS, ""


def _razred_okna(okno, vloga: str = "") -> None:
    """Razred okna (WM_CLASS, po njem pult in dock okno povezeta z vnosom .desktop) in ikona okna (_NET_WM_ICON - Plank
    jo pokaze tudi, ce vnosa ne najde) po vlogi okna (glej OKNA_V_PULTU)."""
    ime, razred, pripona = razred_in_ikona(vloga)
    x11.nastavi_razred(okno, ime, razred)
    if pripona == ".Player":
        okno.set_icon_name(_ime_ikone(("safeer-os.Player", APP_ID + ".Player"), "predvajalnik"))
    else:
        okno.set_icon_name(_ikona_safeer_os(pripona))


def _registriraj_most(upravitelj, ime: str) -> None:
    """register_script_message_handler za WebKit 6.0 (ime, svet) in 4.1 (ime)."""
    try:
        upravitelj.register_script_message_handler(ime, None)
    except TypeError:
        upravitelj.register_script_message_handler(ime)


def namesti_most_skladbe(upravitelj, ob_sporocilu) -> None:
    """Most skladbe v lahkem medijskem pogledu: rokovalnik samo v svetu os_katalog.SVET_SKLADBE, rele tega sveta samo
    v glavnem okvirju strani posnetka (pregled 18. 10. 2026: rokovalnik v glavnem svetu je bil dosegljiv vsakemu
    okvirju, WebKitGTK pa sporocilu okvirja ne doda). SKRIPT_SKLADBE ostane v glavnem svetu (API predvajalnika)."""
    strani = list(os_katalog.STRANI_SKRIPTA_SKLADBE)
    upravitelj.register_script_message_handler("safeerSkladba", os_katalog.SVET_SKLADBE)
    upravitelj.connect("script-message-received::safeerSkladba", ob_sporocilu)
    upravitelj.add_script(WebKit2.UserScript.new_for_world(
        os_katalog.RELE_SKLADBE, WebKit2.UserContentInjectedFrames.TOP_FRAME, WebKit2.UserScriptInjectionTime.START,
        os_katalog.SVET_SKLADBE, strani, None))
    upravitelj.add_script(WebKit2.UserScript(
        os_katalog.SKRIPT_SKLADBE, WebKit2.UserContentInjectedFrames.TOP_FRAME,
        WebKit2.UserScriptInjectionTime.END, strani, None))


def zagon_predvajalnika(argumenti) -> bool:
    """Ali ukazna vrstica zahteva okno Safeer Player (meni »Safeer Player«, `safeer-os --predvajalnik`)."""
    return any(a in ZASTAVICE_PREDVAJALNIKA for a in (argumenti or ()))


BESEDILA_KUVERTE = {
    "sl": ("Sporočila", "Sporočila: {n} neprebranih"), "en": ("Messages", "Messages: {n} unread"),
    "de": ("Nachrichten", "Nachrichten: {n} ungelesen"), "es": ("Mensajes", "Mensajes: {n} sin leer"),
    "fr": ("Messages", "Messages : {n} non lus"), "it": ("Messaggi", "Messaggi: {n} non letti"),
}


def ikona_kuverte(n: int, mapa: str, velikost: int = 48) -> str:
    """Ikona kuverte za pult: bela kuverta (vidna na temnem pultu), pri neprebranih modra znacka s stevilom (9+).
    Narise jo cairo (brez tujih slik); vrne pot do PNG v predpomnilniku (ena datoteka na stevilo)."""
    import cairo
    oznaka = "" if n <= 0 else ("9+" if n > 9 else str(n))
    os.makedirs(mapa, exist_ok=True)
    pot = os.path.join(mapa, "kuverta-%s.png" % (oznaka.replace("+", "p") or "0"))
    if os.path.isfile(pot):
        return pot
    v = float(velikost)
    p = cairo.ImageSurface(cairo.FORMAT_ARGB32, velikost, velikost)
    c = cairo.Context(p)
    c.set_line_width(v * 0.07)
    c.set_line_join(cairo.LINE_JOIN_ROUND)
    c.set_source_rgba(0.92, 0.95, 1.0, 1.0)
    x0, y0, x1, y1 = v * 0.10, v * 0.26, v * 0.80, v * 0.80
    c.rectangle(x0, y0, x1 - x0, y1 - y0)
    c.stroke()
    c.move_to(x0, y0)
    c.line_to((x0 + x1) / 2, (y0 + y1) / 2 + v * 0.02)
    c.line_to(x1, y0)
    c.stroke()
    if oznaka:
        r = v * 0.24
        cx, cy = v - r - 1, r + 1
        c.arc(cx, cy, r, 0, 6.2832)
        c.set_source_rgba(0.23, 0.55, 0.94, 1.0)
        c.fill()
        c.set_source_rgba(1, 1, 1, 1)
        c.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        c.set_font_size(v * (0.30 if len(oznaka) > 1 else 0.36))
        e = c.text_extents(oznaka)
        c.move_to(cx - e.width / 2 - e.x_bearing, cy - e.height / 2 - e.y_bearing)
        c.show_text(oznaka)
    zacasna = pot + ".tmp"
    p.write_to_png(zacasna)
    os.replace(zacasna, pot)
    return pot


#: Razdelki, ki se na delovni povrsini odprejo vsak v svojem oknu (ne cela stara lupina Safeer OS).
#: Safeer Scit (lastnik, 18. 10. 2026) je svoj program kot Sporocila: svoj vnos v meniju, okno, ikona v pultu in docku.
RAZDELKI_V_SVOJEM_OKNU = ("zapiski", "sporocila", "nastavitve", "scit")
#: Podstrani Nastavitev (ploscici Omrezje in Zvok): na namizju se pokazeta v oknu Nastavitve. Prej je klik nanju v oknu
#: Nastavitve odprl staro glavno okno Safeer OS (popis 3.1, 18. 10. 2026 - glej docs/NAMIZJE-POPIS.md).
PODSTRANI_NASTAVITEV = ("omrezje", "zvok")
#: Razdelka, ki sta na namizju plosci (Datoteke, Programi): pokazeta se tam, ne v oknu.
RAZDELKI_NAMIZJA = ("datoteke", "programi")
_NASLOVI_RAZDELKOV = {
    "sl": {"zapiski": "Zapiski", "sporocila": "Sporočila", "nastavitve": "Nastavitve Safeer OS", "scit": "Safeer Ščit"},
    "en": {"zapiski": "Notes", "sporocila": "Messages", "nastavitve": "Safeer OS settings", "scit": "Safeer Shield"},
    "de": {"zapiski": "Notizen", "sporocila": "Nachrichten", "nastavitve": "Safeer OS Einstellungen", "scit": "Safeer Schild"},
    "es": {"zapiski": "Notas", "sporocila": "Mensajes", "nastavitve": "Ajustes de Safeer OS", "scit": "Safeer Escudo"},
    "fr": {"zapiski": "Notes", "sporocila": "Messages", "nastavitve": "Réglages de Safeer OS", "scit": "Safeer Bouclier"},
    "it": {"zapiski": "Note", "sporocila": "Messaggi", "nastavitve": "Impostazioni di Safeer OS", "scit": "Safeer Scudo"},
}


def _naslov_razdelka(ime: str) -> str:
    return _NASLOVI_RAZDELKOV.get(_jezik(), _NASLOVI_RAZDELKOV["en"]).get(ime, "Safeer OS")


def razdelek_predvajalnika(razdelek: str) -> Optional[str]:
    """Ali delovna povrsina z »odpriRazdelek« zahteva Medijski center - ta se odpre v oknu Safeer Player, ne v glavnem
    oknu Safeer OS. Vrne iskani niz ('' brez iskanja) za »media« in »mediji:<niz>«, za druge razdelke None (ti gredo
    v glavno okno kot prej)."""
    razdelek = str(razdelek or "")
    if razdelek == "media":
        return ""
    if razdelek.startswith("mediji:"):
        return razdelek[len("mediji:"):].strip()
    return None


def _podatki_zagona() -> dict:
    """Podatki platforme za predajo tekocemu procesu: oznaka zagona iz menija (DESKTOP_STARTUP_ID). GtkApplication jo
    uporabi pri present(), zato okno pride v ospredje in vrtavka ob kazalcu se ustavi."""
    oznaka = os.environ.get("DESKTOP_STARTUP_ID", "")
    return {"desktop-startup-id": GLib.Variant("s", oznaka)} if oznaka else {}


def _predaj_tekocemu(dejanje: str, vrednost: str) -> bool:
    """Ce Safeer OS ze tece (delovna povrsina, okno), mu preda dejanje (org.gtk.Actions) in vrne True; sicer False in
    klicatelj zazene nov primerek. Napako vodila (ni seje D-Bus) dobi klicatelj kot izjemo."""
    vodilo = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    tece = vodilo.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                            "NameHasOwner", GLib.Variant("(s)", (APP_ID,)), GLib.VariantType("(b)"),
                            Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]
    if tece:
        vodilo.call_sync(APP_ID, "/" + APP_ID.replace(".", "/"), "org.gtk.Actions", "Activate",
                         GLib.Variant("(sava{sv})", (dejanje, [GLib.Variant("s", vrednost)], _podatki_zagona())),
                         None, Gio.DBusCallFlags.NONE, 5000, None)
    return bool(tece)


def _predaj_ce_oddaljen(app, dejanje: str, vrednost=None) -> bool:
    """Atomarna predaja: app se prijavi na vodilo; ce ime ze ima drug proces (tudi tak, ki je zacel hkrati - dvojni
    klik, zasedeni Safeer OS), mu preda dejanje in vrne True. Navadna aktivacija bi namen izgubila: primarni proces bi
    odprl glavno okno. Napako vodila dobi klicatelj kot izjemo."""
    app.register(None)
    if not app.get_is_remote():
        return False
    app.activate_action(dejanje, vrednost)
    povezava = app.get_dbus_connection()
    if povezava is not None:
        povezava.flush_sync(None)     # sporocilo mora oditi, preden se ta proces konca
    return True


def datoteka_nedavnih(okolje=None, dom: str = "") -> str:
    """Seznam nedavnih datotek racunalnika. V Flatpaku GTK bere ~/.var/app/<id>/data/recently-used.xbel, ki je prazen
    (testni PC 14. 10. 2026: Nedavno je bilo vedno prazno); programi racunalnika pisejo v ~/.local/share. Prazno = privzeto."""
    okolje = os.environ if okolje is None else okolje
    if not okolje.get("FLATPAK_ID"):
        return ""
    return os.path.join(dom or os.path.expanduser("~"), ".local", "share", "recently-used.xbel")


_NEDAVNI = None


def _nedavni():
    """Gtk.RecentManager nad seznamom racunalnika (glej datoteka_nedavnih)."""
    global _NEDAVNI
    if _NEDAVNI is None:
        pot = datoteka_nedavnih()
        try:
            _NEDAVNI = Gtk.RecentManager(filename=pot) if pot else Gtk.RecentManager.get_default()
        except Exception:  # noqa: BLE001
            _NEDAVNI = Gtk.RecentManager.get_default()
    return _NEDAVNI


def _ima_delovno(app) -> bool:
    """Delovna povrsina tece: okno WebKit (delovna.html) ali namizje QML (core/os_lupina.Namizje) - ali na Waylandu
    njene storitve brez okna (_delovna_v_ozadju: zaprtje zadnjega okna proces pusti zivega, kot ob delovni povrsini)."""
    return getattr(app, "okno_delovna", None) is not None or \
        isinstance(getattr(app, "lupina", None), os_lupina.Namizje) or getattr(app, "_delovna_v_ozadju", False) is True


class SafeerOS(Gtk.Application):
    def __init__(self, v_oknu: bool = False, posnetek: str = "", namizje: bool = False,
                 delovna: bool = False, predvajalnik: bool = False) -> None:
        zastavice = Gio.ApplicationFlags.NON_UNIQUE if posnetek else Gio.ApplicationFlags.FLAGS_NONE
        super().__init__(application_id=APP_ID, flags=zastavice)
        self.v_oknu = v_oknu
        self.posnetek = posnetek
        self.shramba = os_programi.Shramba()
        # Pred prvim zapisom v shrambo: prazna shramba = nova namestitev (oznaci_vodnik).
        self._vodnik = not posnetek and oznaci_vodnik(self.shramba)
        self.programi = os_programi.Programi(self.shramba)
        self.zapiski = os_zapiski.Zapiski(ZAPISKI_POT)
        self.lupa = os_lupa.Ucenje()
        self.govor = os_govor.Govor()
        self.sporocila = os_sporocila.SporocilaOS()
        # Predpomnilnika: priponke Sporocil (LRU do 500 MB, core/sporocila/predpomnilnik.py) in pretvorbe krajevnih
        # datotek za predogled (starejse od tedna in prek 400 MB).
        def _pocisti_predpomnilnika() -> None:
            from core import predogled_datotek
            from core.sporocila import predpomnilnik
            predpomnilnik.pocisti()
            predogled_datotek.pocisti_predpomnilnik()
        threading.Thread(target=_pocisti_predpomnilnika, name="safeer-priponke-ciscenje", daemon=True).start()
        # Safeer Chat gre po Linku, ki ga drzi Safeer Control (D-Bus).
        self.sporocila.poslji_klepet = lambda n, b, c: _control_naprave("Klepet", n, b, c).get("stanje") \
            or _control_naprave_koda("Klepet")
        self.sporocila.naprave_klepeta = lambda: _control_naprave("KlepetNaprave").get("naprave") or []
        # Novo sporocilo, oznake, stanje kanala: odprte strani (razdelek Sporocila, plosca) se osvezijo takoj (niti
        # kanalov v realnem casu - lastnik, 15. 10. 2026), ne sele ob 30-sekundnem osvezevanju strani.
        os_sporocila.ob_spremembi(lambda: GLib.idle_add(lambda: (self._dogodek("sporocila", {}), False)[1]))
        # Novo e-pismo: obvestilo namizja (kot Gmail in Outlook), klik odpre ta pogovor (lastnik, 15. 10. 2026: pismo
        # je prislo brez znacke in brez obvestila).
        self.sporocila.obvesti_novo = self._obvesti_novo_pismo
        #: Scit: filtriranje DNS za ves racunalnik; ce je bil vklopljen, tece od zagona naprej. Pod varuhom tece v
        #: svojem procesu (core/scit_proces.py, 1.0.129): zamrznitev ali sesutje tega procesa ga ne ustavi vec.
        vtic_scita = okolje_procesa.prevzemi("SAFEER_SCIT_VTIC")
        if vtic_scita:
            from core import scit_odjemalec
            self.scit = scit_odjemalec.ScitOdjemalec(self.shramba, vtic_scita)
        else:
            self.scit = os_scit.Scit(self.shramba)
        self._en_vir_naprej()
        # Posodobitve s safeer.si: zadnja preverba (izid, cas) in tekoce posodabljanje (prenos + namestitev v niti).
        self.posodobitve: dict = {"izid": None, "cas": 0.0, "napaka": ""}
        self.posodabljanje = os_posodobitve.Posodabljanje()
        GLib.timeout_add_seconds(90, self._posodobitve_tiho)
        #: Nova razlicica po namestitvi (core/nova_razlicica.py): spremljanje, cakanje, ponovni zagon ob koncu run().
        self._nova_spremljevalec = None
        self._nova_spremljevalec_webkit = None
        self._nova_cakanje = None
        self._nova_razlicica = ""
        self._ponovni_zagon = False
        #: Posodobitev je zagnal uporabnik v Safeer OS: nova razlicica ne caka na njegovo nedejavnost.
        self._posodobil_sam = False
        # Prenosi zaradi gledanja (film iz torrenta v Medijskem centru), ki jih 48 ur nihce ni predvajal, se odstranijo sami.
        os_torrent_tok.zazeni_ciscenje()
        self.okno: Optional[Gtk.ApplicationWindow] = None
        self.pogled: Optional[WebKit2.WebView] = None
        #: Datoteke, ki jih uporabnik pravkar vlece v okno iz drugega programa (glej _na_vlecene_podatke).
        self._vleceno_kontekst = None
        self._vlecene_poti: list = []
        #: Med predvajanjem racunalnik ne zaspi sam (glej _budnost_predvajanja).
        self._budnost = budnost.Budnost("Safeer OS")
        # Indeks imen datotek za iskanje: zgradi se v ozadju kmalu po zagonu, da je ze prvo iskanje takojsnje.
        if not posnetek:
            GLib.timeout_add_seconds(12, lambda: (os_iskalnik.indeks().zgradi_v_ozadju(), False)[1])
        #: Naslovi datotek, ki jih uporabnik vlece IZ Datotek (pravo vlecenje namizja, glej _zacni_vlecenje).
        self._lastno_vlecenje: list = []
        self._lastno_ni_uspelo = False
        self._ikone: dict = {}
        self._prvic = True
        #: Namizni nacin: Safeer OS je namizje (spodaj, programi nad njim) s svojo vrstico namesto
        #: Mintovega pulta. Sicer navadno okno (--okno, posnetki).
        # --namizje (paket safeer-os-tema, ob prijavi) vedno zazene namizje; --okno (program v oknu) nikoli.
        self.namizje = not v_oknu and not posnetek and not delovna and (
            namizje or bool(self.shramba.get("celozaslonsko", True)))
        #: Safeer Cinnamon (paket safeer-cinnamon): delovna povrsina (iskanje, datoteke, predvajalnik,
        #: programi naprav) kot ozadje pod okni; Mintov pult in dock ostaneta. Glavno okno Safeer OS se
        #: odpre sele, ko ga uporabnik zazene (navadno okno).
        self.delovna = bool(delovna) and not posnetek
        if self.delovna:
            self.v_oknu = True
        self.okno_delovna: Optional[Gtk.Window] = None
        self.pogled_delovna = None
        #: Namizje QML (core/os_lupina.py); takrat okno_delovna ostane None, pogled_delovna je QmlPogled.
        self.lupina = None
        self._robovi_delovne = None
        #: Safeer Player: Medijski center v svojem oknu (gumb »Odpri Medijski center« na delovni povrsini, meni
        #: »Safeer Player«). Ista stran in isti most v tem procesu - predvajanje, mini predvajalnik in Safeer Link so skupni.
        self.okno_predvajalnik: Optional[Gtk.ApplicationWindow] = None
        #: Okna razdelkov na delovni povrsini (ime -> (okno, pogled)), glej _odpri_okno_razdelka.
        self.okna_razdelkov: dict = {}
        self.pogled_predvajalnik = None
        #: Zagon s --predvajalnik: prva aktivacija odpre samo Safeer Player (glavno okno sele naslednja, meni Safeer OS).
        self._zacni_s_predvajalnikom = bool(predvajalnik)
        #: Pogled, ki je nazadnje zacel predvajanje iz kataloga: vrsto skladb vodi samo on (glej _dogodek).
        self._katalog_pogled = None
        #: Pogled, ki je nazadnje zahteval predvajanje (KLICI_PREDVAJANJA): okno z videom in lahki medijski pogled sta
        #: nad njegovim oknom (glej _stars_medija). None: zahteva brez strani (D-Bus, druga naprava).
        self._medijski_klicatelj = None
        #: Pogled, ki je odprl lahki medijski pogled: ce strani brez videa ni mogoce predvajati, gre tja nazaj.
        self._lahki_klicatelj = None
        self.vrstica: Optional[Gtk.Window] = None
        self.pogledi: list = []
        self._okna_zamik = 0
        self._zaslon_zamik = 0
        self._koncano = False
        self._posnetek_nacrtovan = False
        # Safeer Media ima največ en lahek spletni pogled, ki se med vsebinami ponovno uporabi.
        self._medijska_plast = None       # vgrajeni spletni predvajalnik v oknu Medijskega centra (os_medijska_plast)
        self._medijski_pogled = None
        self._medijski_naslov = ""
        self._medijski_js = False
        self._medijski_rod = 0
        self._medijski_predvajalnik = None
        self._medijski_gst = None
        self._medijski_predvajalnik_okno = None
        # Splet je del istega okna. Ustvarimo ga sele ob prvem obisku in ga med razdelki samo skrijemo,
        # zato zavihki, prijave in zgodovina ostanejo zivi.
        self._spletni = None
        #: Splet na delovni povrsini (iskanje z zgornjim poljem): isti vgrajeni brskalnik v plosci nad namizjem.
        self._spletni_namizje = None
        self._plosca_spleta = None
        self._prekrivanje_delovne = None
        self._peskovnik_dela = None   # None = še ni preverjeno (core.os_splet.peskovnik_dela)
        #: Pogledi z odprtim lastnim vgrajenim virom (okvirji http(s) dovoljeni, filter EasyList) in tisti v celem zaslonu.
        self._vgrajeni_pogledi = weakref.WeakSet()
        self._vgrajeni_cel_zaslon = weakref.WeakSet()
        self._peskovnik_preverjen = 0.0   # kdaj (time.monotonic) je bil nazadnje preverjen
        self._glavna_postavitev = None
        self._spletni_nacin = False
        self._medijski_napis = None
        self._medijski_sklad = None
        self._medijski_vrsta = None
        self._medijski_zvok = None        # gumb Zvok (zvocni posnetek, zamik, izenacevalnik)
        self._medijski_osd = None         # kratko besedilo v kotu slike
        self._medijski_osd_cas = 0
        self._medijska_okenca = []        # odprta okenca z nastavitvami (tipke gredo njim)
        self._medijski_premor = None
        self._medijski_drsnik = None
        self._medijski_cas = None
        self._medijski_vlecem = False
        self._medijski_css = None
        self._knjiznica_medijev = None
        #: Katalog Medijskega centra (filmi, serije, glasba, radio, TV, seznami predvajanja): isto jedro kot na Windows.
        self._katalog = None
        self._mpris = None                  # core/os_mpris.Mpris; False = ni uspelo (ne poskusamo znova)
        self._medijski_tik_zacet = False
        self._medijsko_osvezevanje = False
        self._zadnji_medijski_napredek = None
        #: Magnet povezava, ki caka, da se stran nalozi (zagon z --magnet ali dejanje, ko okna se ni).
        self._cakajoci_magnet = ""
        #: Dodatek Stremio (povezava »Install«), ki caka, da se stran Safeer Playerja nalozi (cakajociStremio).
        self._cakajoci_stremio = ""
        magnet = Gio.SimpleAction.new("magnet", GLib.VariantType.new("s"))
        magnet.connect("activate", lambda _a, v: self._odpri_magnet(v.get_string() if v else ""))
        self.add_action(magnet)
        #: Datoteka, ki caka na okno (zagon `safeer-os --predvajaj <pot>`, ko Safeer OS se ne tece).
        self._cakajoca_datoteka = ""
        predvajaj = Gio.SimpleAction.new("predvajaj", GLib.VariantType.new("s"))
        predvajaj.connect("activate", lambda _a, v: self._predvajaj_datoteko(v.get_string() if v else ""))
        self.add_action(predvajaj)
        #: "Poslji na napravo": sprejeta ponudba druge naprave (Control jo preda po Sprejmi), ki caka na okno.
        self._cakajoca_ponudba = None
        ponudba = Gio.SimpleAction.new("ponudba", GLib.VariantType.new("s"))
        ponudba.connect("activate", lambda _a, v: self._predvajaj_ponudbo(v.get_string() if v else ""))
        self.add_action(ponudba)
        #: `safeer-os --predvajalnik`, ko Safeer OS ze tece: okno Safeer Player v tem procesu (parameter: iskani niz).
        predvajalnik_okno = Gio.SimpleAction.new("predvajalnik", GLib.VariantType.new("s"))
        predvajalnik_okno.connect("activate", lambda _a, v: self._odpri_predvajalnik(v.get_string() if v else ""))
        self.add_action(predvajalnik_okno)
        #: `safeer-os --medij-naprava <json>` (»prikazi na racunalniku« z druge naprave, media.open): Safeer Player.
        medij = Gio.SimpleAction.new("medij", GLib.VariantType.new("s"))
        medij.connect("activate", lambda _a, v: self._odpri_medij_od_drugod(v.get_string() if v else ""))
        self.add_action(medij)
        #: `safeer-os --isci-naprava <niz>` (glas s telefona, core/link_daljinec.py search.query): niz v iskalno lupo.
        isci = Gio.SimpleAction.new("isci", GLib.VariantType.new("s"))
        isci.connect("activate", lambda _a, v: self._isci_od_drugod(v.get_string() if v else ""))
        self.add_action(isci)
        # Odpri spletni naslov v Spletu na delovni povrsini (drugi programi, Safeer Link, preizkus na testnem PC):
        # gdbus call ... org.gtk.Actions.Activate splet "[<'https://...'>]" {}. Samo http(s), nic drugega.
        splet_akcija = Gio.SimpleAction.new("splet", GLib.VariantType.new("s"))
        splet_akcija.connect("activate", lambda _a, v: self._splet_od_drugod(v.get_string() if v else ""))
        self.add_action(splet_akcija)
        #: `safeer-os --stremio <naslov>` (gumb »Install« na strani z dodatki, x-scheme-handler/stremio): Safeer Player.
        stremio = Gio.SimpleAction.new("stremio", GLib.VariantType.new("s"))
        stremio.connect("activate", lambda _a, v: self._odpri_stremio_dodatek(v.get_string() if v else ""))
        self.add_action(stremio)
        #: `safeer-os --razdelek splet|sporocila|zapiski|nastavitve` (vnos okna v docku, glej OKNA_V_PULTU): okno razdelka.
        razdelek = Gio.SimpleAction.new("razdelek", GLib.VariantType.new("s"))
        razdelek.connect("activate", lambda _a, v: self._razdelek_od_drugod(v.get_string() if v else ""))
        self.add_action(razdelek)
        #: `safeer-os --delovna` (safeer-cinnamon), ko Safeer OS ze tece brez delovne povrsine (glej _vklopi_delovno).
        delovna_povrsina = Gio.SimpleAction.new("delovna", None)
        delovna_povrsina.connect("activate", lambda *_a: self._vklopi_delovno())
        self.add_action(delovna_povrsina)
        #: `safeer-cinnamon` ob izklopu postavitve delovna: konec procesa, ki ima delovno povrsino (kot SIGTERM). Proces
        #: ima lahko drugo ime (Safeer Player, okno iz menija, ki mu je bila delovna povrsina predana), zato pkill po
        #: »--delovna« ni dovolj. Brez delovne povrsine (samo Safeer Player) se ne zgodi nic.
        delovna_konec = Gio.SimpleAction.new("delovna-izklopi", None)
        delovna_konec.connect("activate", lambda *_a: self._izklopi_delovno())
        self.add_action(delovna_konec)
        #: `safeer-os --nazaj-na-cinnamon`, ko Safeer OS tece: naredi ga ta proces (ena shramba), nato se konca.
        cinnamon = Gio.SimpleAction.new("nazaj-na-cinnamon", GLib.VariantType.new("s"))   # _predaj_tekocemu poslje niz
        cinnamon.connect("activate", lambda *_a: self._nazaj_v_mint(True))
        self.add_action(cinnamon)

    def _razdelek_od_drugod(self, razdelek: str) -> None:
        """Dejanje »razdelek« (vnos okna v docku ali meniju): samo okna iz OKNA_V_PULTU, nic drugega iz ukazne vrstice."""
        if razdelek in OKNA_V_PULTU:
            self._odpri_razdelek(razdelek)

    def do_startup(self) -> None:
        Gtk.Application.do_startup(self)
        x11._knjiznica()    # rokovalnik napak X po GDK in v glavni niti (glej core/x11.py)
        gostitelj.dodaj_ikone_gostitelja(Gtk)
        # Safeer DRM je od 1.0.127 v paketu (nic se ne prenasa); v ozadju pospravimo samo nekoc preneseno kopijo.
        if not self.posnetek:
            from core import safeer_drm
            safeer_drm.pospravi_staro_v_ozadju()
        # Spletne strani (prefers-color-scheme) sledijo temi namizja, tudi ob preklopu med delom.
        try:
            from core import os_tema_namizja
            self._tema_namizja = os_tema_namizja.sledi(Gtk, Gio, GLib)
        except Exception as e:  # noqa: BLE001 - brez tega strani ostanejo le svetle
            print("[SafeerOS] tema namizja:", e)
        pomnilnik.obrezuj_periodicno(GLib)
        # Storitve na zahtevo, hisna opravila in zgodovina porabe za safeer://procesi (ena ura na glavni zanki).
        from core import storitve_na_zahtevo
        storitve_na_zahtevo.vezi_safeer_os(self, GLib)
        # `safeer-os --okno` iz menija, ko Safeer OS ze tece (npr. kot Safeer Player): drugi zagon to sporoci
        # primerku, ki tece, pred aktivacijo - sicer bi se odprlo staro okno namesto namizja QML (pregled 14. 10. 2026).
        okno_qml = Gio.SimpleAction.new("okno-qml", None)
        okno_qml.connect("activate", lambda *_a: setattr(self, "_qml_okno", True))
        self.add_action(okno_qml)
        self._izvozi_predvajanje()
        en_proces.nastavi_os(self, klic=self._predvajanje_neposredno)
        self._spremljaj_zaklep()
        if not self.posnetek:
            self._spremljaj_novo_razlicico()
            # Ponovni zagon nove razlicice: zavihki Spleta in predvajanje iz stare (po aktivaciji, ko so okna).
            GLib.timeout_add_seconds(3, self._obnovi_po_novi_razlicici)
        threading.Thread(target=stremio_privzeto, name="safeer-stremio-privzeto", daemon=True).start()
        if self.namizje and not self.posnetek:
            # Namizje tece ves dan: Control (Safeer Link, naprave, pladenj) naj tece z njim, v istem procesu, kot je
            # prej tekel locen proces v ozadju. Z zamikom, da namizje ni pocasnejse ob prijavi. Delovna povrsina
            # (--delovna ali predana pozneje) to naredi v _ob_namizju.
            GLib.timeout_add_seconds(3, lambda: (self._vgradi_control(), False)[1])

    def do_shutdown(self) -> None:
        # Vsak konec procesa (tudi zadnje okno zaprto brez close-request): Scit vrne DNS, rqbit se ustavi, pult se vrne.
        try:
            self._koncaj()
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] konec:", e)
        c = en_proces.control_app()
        if c is not None:
            try:   # kot SIGTERM samostojnega Controla: pospravi Link, deljene mape, lociti zaslon, navidezni zvok
                c.koncaj_brez_izhoda()
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] Control ob izhodu:", e)
        Gtk.Application.do_shutdown(self)

    # ------------------------------------------------------------------ Control v istem procesu (core/en_proces.py)
    def _vgradi_control(self) -> bool:
        """Safeer Control zazene v tem procesu (glavna nit). False: ze tece drug proces Control, Control ni v paketu
        ali ga uporabnik zeli locenega (SAFEER_LOCEN_CONTROL=1) - takrat ostane stara pot (locen proces, D-Bus)."""
        if en_proces.control_app() is not None:
            return True
        if os.environ.get("SAFEER_LOCEN_CONTROL") == "1" or self.posnetek:
            return False
        if not os.path.isfile(os.path.join(KOREN, "safeer_control.py")):
            return False
        try:
            vodilo = self.get_dbus_connection() or Gio.bus_get_sync(Gio.BusType.SESSION, None)
            if _control_na_vodilu_dbus(vodilo):
                return False                      # Control ze tece kot locen proces: ga ne podvajamo
            zaklep = os_stabilnost.zakleni_primerek("safeer-control")
            if zaklep is None:
                return False                      # locen Control se ravno zaganja
            # Control kot Gio.Application (safeer_control._OSNOVA) - zastavica v procesu, ne okoljska spremenljivka:
            # tu ze tecejo niti, setenv bi bil nevaren (core/en_proces.vgradi_control).
            en_proces.vgradi_control()
            import safeer_control
            safeer_control._ZAKLEP_PRIMERKA = zaklep
            safeer_control.VGRAJEN = True
            c = safeer_control.SafeerControl(ozadje=True)
            if not c.register(None) or c.get_is_remote():
                return False
            en_proces.nastavi_control(c)
            c.activate()                          # prva aktivacija v ozadju: Link, pladenj, preverba posodobitev
            print("[SafeerOS] Safeer Control tece v procesu Safeer OS (en proces).", flush=True)
            return True
        except Exception as e:  # noqa: BLE001 - ce ne gre, ostane locen proces
            print("[SafeerOS] vgradnja Controla:", e, flush=True)
            return False

    def _predvajanje_neposredno(self, metoda: str, argumenti: list) -> dict:
        """Isti vmesnik kot D-Bus Predvajanje, za Control v istem procesu (brez D-Bus samemu sebi)."""
        if metoda == "OdstraniPrenos":
            ok = bool(knjiznica_kroga.odstrani_lokalnega(str(argumenti[0]) if argumenti else ""))
            if ok:
                GLib.idle_add(lambda: (self._dogodek("mediaKnjiznicaSpremenjena", None), False)[1])
            return {"ok": ok}
        fn = {"Stanje": self._predvajanje_za_control, "Premor": self._predvajanje_premor}.get(metoda)
        if fn is None:
            return {"ok": False, "message": "neznana metoda"}
        return en_proces.na_glavni(fn, cas=3.0, privzeto={"ok": False, "message": "cas"})

    # ------------------------------------------------------------------ D-Bus za Safeer Control: kaj predvajam
    VMESNIK_PREDVAJANJE = """
    <node><interface name="io.github.memelandfaner.SafeerOS.Predvajanje">
      <method name="Stanje"><arg type="s" name="json" direction="out"/></method>
      <method name="Premor"><arg type="s" name="json" direction="out"/></method>
      <method name="OdstraniPrenos"><arg type="s" name="hash" direction="in"/><arg type="s" name="json" direction="out"/></method>
    </interface></node>"""

    def _izvozi_predvajanje(self) -> None:
        """»Nadaljuj z druge naprave«: Safeer Control (locen proces) prek tega vmesnika izve, kaj domaci predvajalnik
        predvaja in pri kateri sekundi (ukaz `play.state` s telefona ali televizorja), in ga na izrecno zeljo
        uporabnika na cilju ustavi (`play.stop`, samo pavza). Nic samodejnega in nic ne gre ven brez vprasanja
        naprave v krogu zaupanja; datoteko dobi naprava le, ce je v mapi, ki jo Control deli."""
        try:
            vodilo = self.get_dbus_connection() or Gio.bus_get_sync(Gio.BusType.SESSION, None)
            info = Gio.DBusNodeInfo.new_for_xml(self.VMESNIK_PREDVAJANJE)
            vodilo.register_object(PREDVAJANJE_POT, info.interfaces[0], self._klic_predvajanje, None, None)
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] D-Bus Predvajanje:", e)

    def _klic_predvajanje(self, _vodilo, _posiljatelj, _pot, _vmesnik, metoda, _parametri, klic) -> None:
        # Tece na glavni niti (GStreamer je v tem procesu): klici so kratki, nic ne caka na omrezje.
        if metoda == "OdstraniPrenos":
            # Naprava v krogu je s police »Na tvojih napravah« odstranila film, ki ga hrani motor Safeer OS (Control
            # zahtevo posreduje sem). Odstranitev govori z motorjem, zato v ozadju; odgovor, ko konca.
            hash_ = str(_parametri.unpack()[0]) if _parametri is not None else ""

            def odstrani() -> None:
                try:
                    ok = bool(knjiznica_kroga.odstrani_lokalnega(hash_))
                except Exception as e:  # noqa: BLE001
                    print("[SafeerOS] odstranitev prenosa:", e, flush=True)
                    ok = False
                klic.return_value(GLib.Variant("(s)", (json.dumps({"ok": ok}),)))
                if ok:
                    GLib.idle_add(lambda: (self._dogodek("mediaKnjiznicaSpremenjena", None), False)[1])
            threading.Thread(target=odstrani, name="safeer-odstrani-prenos", daemon=True).start()
            return
        try:
            if metoda == "Stanje":
                izid = self._predvajanje_za_control()
            elif metoda == "Premor":
                izid = self._predvajanje_premor()
            else:
                izid = {"ok": False, "message": "neznana metoda"}
        except Exception as e:  # noqa: BLE001
            izid = {"ok": False, "message": str(e)}
        klic.return_value(GLib.Variant("(s)", (json.dumps(izid, ensure_ascii=True),)))

    def _predvajanje_za_control(self) -> dict:
        """Kaj igra (ali je v premoru) in kje: uri, naslov, vrsta, sekunde; datoteka z druge naprave v Linku ima
        se id te naprave in svojo oznako tam (cilj si zeton pri njej dobi sam, kot pri Datotekah)."""
        servis = self._medijski_predvajalnik
        if servis is None or servis.trenutna is None or servis.stanje not in ("predvaja", "premor"):
            return {"ok": True, "stanje": "ustavljeno"}
        vnos = self._katalog.vnos_predvajanega(servis.trenutna.uri) if self._katalog is not None else None
        if vnos and vnos.get("zaseben"):
            # Vsebina zasebnega dodatka (kategorija »Zasebno«): drugim napravam v Linku ne povemo, kaj igra.
            return {"ok": True, "stanje": "ustavljeno"}
        p = servis.podatki()
        t = servis.trenutna
        return {"ok": True, "stanje": p["stanje"], "uri": t.uri, "naslov": p["naslov"], "vrsta": p["vrsta"],
                "pozicija": p["pozicija"], "trajanje": p["trajanje"], "izvor": p.get("izvor", ""),
                "naprava": t.naprava, "oznaka": t.oznaka, "izvirnik": t.izvirnik}

    def _predvajanje_premor(self) -> dict:
        """`play.stop` z naprave, ki je predvajanje prevzela: tu samo premor (nic se ne izgubi, mesto se shrani)."""
        servis = self._medijski_predvajalnik
        if servis is None or servis.stanje != "predvaja":
            return {"ok": True, "stopped": False}
        return {"ok": True, "stopped": bool(self._medijski_ukaz("premor"))}

    # ------------------------------------------------------------------ okno
    def do_activate(self) -> None:
        if self.delovna and not _ima_delovno(self):
            if seja_prikaza.je_wayland():
                # Safeer Cinnamon ob prijavi na Waylandu (Cinnamon na Waylandu, poskusno v Mintu 22): delovne povrsine
                # pod okni ni mogoce narediti, okno cez ves zaslon bi prekrilo programe. Storitve (Scit, Link, kuverta)
                # tecejo, okno Safeer OS odpre meni (naslednja aktivacija - QML v oknu).
                self._delovna_v_ozadju = True
                self._qml_okno = True
                self.hold()
            else:
                # Prvi zagon z --delovna: samo delovna povrsina (glavno okno ob naslednji aktivaciji).
                self._ustvari_delovno()
            self._ob_namizju()
            self._prvic = False
            self._povezi_koncanje()
            return
        if self._zacni_s_predvajalnikom:
            # Zagon s --predvajalnik (meni »Safeer Player«, Safeer OS se ne tece): samo okno Safeer Player. Glavno okno
            # odpre naslednja aktivacija (meni »Safeer OS«); Scit in zagon ob prijavi sodita k lupini, zato ju tu ne.
            self._zacni_s_predvajalnikom = False
            self._odpri_predvajalnik()
            self._povezi_koncanje()
            return
        if isinstance(self.lupina, os_lupina.Namizje) and self.lupina.v_oknu:
            self.lupina.dvigni()
            return
        if self.okno is None and self.lupina is None and self._ustvari_qml_okno():
            return
        if self.okno is not None:
            self._domov()
            return
        self._ustvari_okno()
        if self._cakajoca_datoteka or self._cakajoca_ponudba:
            GLib.timeout_add(1500, self._predvajaj_cakajoco)
        if self.namizje:
            self._ustvari_vrstico()
            if VARNI_NACIN:
                # Po ponovljenih sesutjih pusti Mintov pult viden: uporabnik ima vedno pot ven.
                print("[SafeerOS] varni način: Mintov pult ostane viden")
            else:
                skrij_mintov_pult(self.shramba)
        self._povezi_koncanje()
        if self._prvic and not self.posnetek:
            self._prvic = False
            self.scit.zacni_ce_vklopljen()
            # Zagona ob prijavi program NE vklopi sam (prej ga je ob prvem odprtju): vklopi ga samo uporabnik s
            # stikalom v Nastavitvah. Kjer ga je vklopila starejsa razlicica, ga tu enkrat izklopimo.
            uredi_samozagon_ob_zagonu(self.shramba)
            # Brez prijavnega okna ob zagonu: Safeer OS dela takoj, naprave uporabnik poveze v Napravah,
            # kadar hoce (tam vidi, ali je v omrezju Safeer Link, in dobi navodila, ce ga ni).

    #: `safeer-os --okno` iz menija (GNOME, KDE …) brez datoteke, ponudbe ali predvajalnika: main() nastavi True.
    _qml_okno = False
    #: --delovna na Waylandu: storitve brez okna delovne povrsine (do_activate).
    _delovna_v_ozadju = False

    def _ustvari_qml_okno(self) -> bool:
        """Aplikacija Safeer OS v oknu = isto namizje QML kot namizno okolje (lastnik, 14. 10. 2026: brez dvojnega dela;
        Datoteke z drugih naprav in Teamwork, Lupa, Programi naprav so tako tudi v aplikaciji). Razdelki (Nastavitve,
        Zapiski, Sporocila, Splet, Safeer Player) se odprejo v svojih oknih kot na namizju (_ima_delovno). Brez PySide6
        ali s SAFEER_LUPINA=html ostane prejsnje okno index.html (vrne False)."""
        if not self._qml_okno or self.posnetek or self.namizje or (self.delovna and not self._delovna_v_ozadju) or \
                not os_lupina.pripravi(sys.argv[:1], pozno=bool(self.get_windows())):
            return False
        try:
            self.lupina = os_lupina.Namizje(self, ob_koncu=lambda: GLib.idle_add(self._zaprto_qml_okno), v_oknu=True)
        except Exception as e:  # noqa: BLE001 - QML se ni nalozil: staro okno
            print("[SafeerOS] okno QML:", e, flush=True)
            self.lupina = None
            return False
        self.pogled_delovna = self._qml_pogled = self.lupina.pogled
        self.lupina.pokazi()
        self.hold()          # okno QML ni okno Gtk.Application: brez tega bi se proces koncal takoj po zagonu
        self._povezi_koncanje()
        if self._prvic:
            self._prvic = False
            self.scit.zacni_ce_vklopljen()
            uredi_samozagon_ob_zagonu(self.shramba)
        return True

    def _zaprto_qml_okno(self) -> bool:
        """Uporabnik je zaprl okno aplikacije. Ce so odprta se druga okna (Splet, Safeer Player z videom, Zapiski …),
        jih ne zapremo brez opozorila (pregled 14. 10. 2026): Safeer OS se konca, ko izgine zadnje vidno okno."""
        if self.lupina is not None and self.lupina.okno.isVisible():
            return False                      # okno je medtem spet odprto (dvigni)
        if self._delovna_v_ozadju is True:
            return False                      # Wayland, Safeer Cinnamon: storitve (Scit, Link) tecejo naprej, meni okno vrne
        if any(o.get_visible() for o in self.get_windows()):
            GLib.timeout_add_seconds(2, self._zaprto_qml_okno)
            return False
        self._koncaj()
        return False

    def _povezi_koncanje(self) -> None:
        """Dejanje »koncaj« in signali SIGTERM (odjava), SIGHUP, SIGINT: Safeer OS pospravi za sabo (Mintov pult, Scit,
        predvajanje). Enkrat na proces, ne glede na to, katero okno se je odprlo prvo."""
        if getattr(self, "_koncanje_povezano", False):
            return
        self._koncanje_povezano = True
        koncaj = Gio.SimpleAction.new("koncaj", None)
        koncaj.connect("activate", lambda *a: self._koncaj())
        self.add_action(koncaj)
        for signal in (15, 1, 2):     # SIGTERM (odjava), SIGHUP, SIGINT: Mintov pult vrnemo
            GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal, lambda *a: (self._koncaj(), False)[1])

    def _vklopi_delovno(self) -> bool:
        """`safeer-os --delovna` (safeer-cinnamon ob prijavi ali ob vklopu teme), ko Safeer OS ze tece kot Safeer Player
        ali okno iz menija: delovna povrsina se odpre v tem procesu (prej je drugi zagon tiho koncal in tema je ostala
        brez nje do naslednje prijave). Glavno okno odslej ob zapiranju samo skrije (_zapri_glavno). Kjer delovna
        povrsina ze je ali tece celozaslonski Safeer OS (namizje), se ne zgodi nic - kot prej."""
        lupina = getattr(self, "lupina", None)
        okno_aplikacije = isinstance(lupina, os_lupina.Namizje) and lupina.v_oknu
        if (_ima_delovno(self) and not okno_aplikacije) or self.namizje or self.posnetek:
            return False
        if seja_prikaza.je_wayland():
            # Wayland: delovne povrsine pod okni ni (do_activate) - samo storitve; odprto okno ostane, kot je.
            self._delovna_v_ozadju = True
            self._ob_namizju()
            self._povezi_koncanje()
            return True
        if okno_aplikacije:
            # Aplikacija Safeer OS v oknu je isto namizje QML (_ustvari_qml_okno): okno postane delovna povrsina. Prej je
            # odprto okno delovno povrsino blokiralo do naslednje prijave (pregled celovitosti 15. 10. 2026).
            lupina._ob_koncu = None              # zaprtje tega okna ne sme koncati Safeer OS (_zaprto_qml_okno)
            try:
                lupina.zapri()
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] okno aplikacije:", e, flush=True)
            self.lupina = None
            self.pogled_delovna = self._qml_pogled = None
        self.delovna, self.v_oknu = True, True
        self._ustvari_delovno()
        self._ob_namizju()
        self._povezi_koncanje()
        return True

    def _ob_namizju(self) -> None:
        """Kar sodi k delovni povrsini, ne glede na to, ali je nastala ob zagonu (--delovna) ali pozneje v procesu, ki je
        ze tekel kot Safeer Player ali okno (_vklopi_delovno): Scit, zagon ob prijavi, kuverta sporocil v pultu, Control
        v tem procesu (Safeer Link, pladenj) in ponudba povezave. Prej je vse to dobila samo pot ob zagonu (pregled
        celovitosti 15. 10. 2026). Vsak del se zgodi enkrat na proces."""
        if self.posnetek or getattr(self, "_namizje_pripravljeno", False):
            return
        self._namizje_pripravljeno = True
        # Varuh (core/varuh_procesov.py): pripravljen, utrip iz glavne zanke (zamrznitev) in stanje za obnovo po napaki.
        if varuh_procesov.pod_varuhom():
            varuh_procesov.obvesti("READY=1")
            varuh_procesov.utrip_glib(GLib)
            GLib.timeout_add_seconds(POSNETEK_STANJA_S, self._posnemi_stanje)
        if self._prvic:
            # Ce je bilo glavno okno ze odprto, sta Scit in zagon ob prijavi ze urejena.
            self._prvic = False
            # Scit, ki ga je uporabnik vklopil, varuje tudi, kadar Safeer OS tece kot delovna povrsina.
            self.scit.zacni_ce_vklopljen()
            uredi_samozagon_ob_zagonu(self.shramba)
        # Sporocila na namizju: kuverta z neprebranimi v pultu zgoraj desno, klik odpre plosco sporocil.
        GLib.timeout_add_seconds(2, lambda: (self._zacni_kuverto(), False)[1])
        # Safeer Scit poleg kuverte: stanje in stevec v pultu, klik odpre nastavitve Scita (lastnik, 17. 10. 2026).
        GLib.timeout_add_seconds(2, lambda: (self._zacni_scit_pult(), False)[1])
        # Namizje tece ves dan: Control (Safeer Link, naprave, pladenj) tece z njim, v istem procesu. Z zamikom, da
        # namizje ni pocasnejse ob prijavi.
        GLib.timeout_add_seconds(3, lambda: (self._vgradi_control(), False)[1])
        # Safeer Link ob prijavi v namizje: ce racunalnik ni povezan, tiho obvestilo z gumbom »Poveži«
        # (okno ob zagonu je bilo moteče - lastnik, 13. 10. 2026), razen ce je ze povezan ali v tej seji izbral brez.
        GLib.timeout_add_seconds(4, self._prijavno_okno_ob_prijavi)
        # Kanali Sporocil se nalozijo ob zagonu namizja (lastnik, 15. 10. 2026: brez cakanja ob prvem odprtju), a sele
        # ko je namizje izrisano in mirno: po Controlu, z nizko prednostjo, zaporedoma po dva (os_kanali_sporocil).
        GLib.timeout_add_seconds(5, lambda: (GLib.idle_add(self._zacni_kanale, priority=GLib.PRIORITY_LOW), False)[1])
        # Varuh docka: sesuti Plank se vrne (safeer-cinnamon --dock-ozivi), vsakih 30 s - za namizje QML in WebKit.
        GLib.timeout_add_seconds(30, lambda: (self._varuh_docka(), True)[1])

    def _izklopi_delovno(self) -> bool:
        """Dejanje »delovna-izklopi« (safeer-cinnamon ob izklopu): proces z delovno povrsino se konca kot ob SIGTERM."""
        if not (self.delovna and _ima_delovno(self)):
            return False
        GLib.idle_add(lambda: (self._koncaj(), False)[1])
        return True

    def _nov_pogled(self, stran: str) -> WebKit2.WebView:
        """WebKit z mostom do tega procesa; odgovori gredo nazaj v isti pogled."""
        upravitelj = WebKit2.UserContentManager()
        _registriraj_most(upravitelj, "safeerOs")
        # Most samo v glavnem okvirju in samo na straneh file:// (Safeer OS): vgrajeni viri (iframe) ga ne dobijo; tuja
        # stran v glavnem okvirju tudi ne (to sicer prepreci ze _na_politiko, glej os_vgrajeni_viri.tuja_glavna_stran).
        upravitelj.add_script(WebKit2.UserScript(
            MOST_JS, WebKit2.UserContentInjectedFrames.TOP_FRAME,
            WebKit2.UserScriptInjectionTime.START, ["file:///*"], None))
        odlozisce_varuh.dodaj(WebKit2, upravitelj)   # Ctrl+C brez izbora ne sme izprazniti odložišča
        # Strani Safeer OS (namizje, glavno okno) imajo skupen kontekst z mejo pomnilnika spletnega procesa.
        if getattr(self, "_os_kontekst", None) is None:
            self._os_kontekst = pomnilnik.kontekst(WebKit2, 220)
        pogled = WebKit2.WebView(user_content_manager=upravitelj, web_context=self._os_kontekst)
        ref = weakref.ref(pogled)   # sibka: mocna referenca bi zaprtemu oknu pustila zivi WebView (krog C-Python)
        upravitelj.connect("script-message-received::safeerOs",
                           lambda _u, r: ref() is not None and self._na_sporocilo(ref(), r))
        n = pogled.get_settings()
        n.set_property("enable-developer-extras", bool(os.environ.get("SAFEER_OS_RAZVOJ")))
        try:   # razvojni nacin: napake JavaScripta v terminal (preverjanje razdelkov s --posnetek)
            n.set_property("enable-write-console-messages-to-stdout", bool(os.environ.get("SAFEER_OS_RAZVOJ")))
        except Exception:
            pass
        n.set_property("enable-webgl", False)
        try:
            n.set_property("default-font-size", 16)
            n.set_property("minimum-font-size", 0)
        except Exception:
            pass
        barva = Gdk.RGBA()
        barva.parse("#090d15")
        pogled.set_background_color(barva)
        pogled.connect("decide-policy", self._na_politiko)
        # Pojavno okno iz vgrajenega vira (samo ce ga je uporabnik dovolil - sicer ga ustavi ze peskovnik iframa).
        pogled.connect("create", self._vgrajeno_novo_okno)
        # Cel zaslon elementa (video v vgrajenem viru): Escape ga zapusti (WebKit), ne zapre vira (_vgrajeno_tipka).
        pogled.connect("enter-fullscreen", lambda p: (self._vgrajeni_cel_zaslon.add(p), False)[1])
        pogled.connect("leave-fullscreen", lambda p: (self._vgrajeni_cel_zaslon.discard(p), False)[1])
        # Ce spletni proces pade (sesutje, pomanjkanje pomnilnika), se stran nalozi znova - sicer ostane prazno namizje.
        os_stabilnost.obnovi_ob_padcu(WebKit2, GLib, pogled, "safeer-os", stran.split("?", 1)[0])
        pogled.set_hexpand(True)
        pogled.set_vexpand(True)
        pogled.connect("context-menu", lambda *a: True)   # brez »Reload / Inspect« v preobleki
        # Datoteke na delovni povrsini sprejmejo datoteke iz drugih programov, Sporocila (index.html) priloge.
        if stran.startswith(("delovna.html", "index.html")):
            # GTK4: signala drag-data-received ni; DropControllerMotion vlecenja ne prevzame (spust ostane WebKitu).
            vlecenje = Gtk.DropControllerMotion()
            vlecenje.connect("enter", lambda k, *_a: self._na_vlecene_podatke(pogled, k.get_drop()))
            pogled.add_controller(vlecenje)
        # Posnetek mora load-changed priklopiti PRED load_uri. Pri hitrem file:// nalaganju je bil
        # dogodek sicer lahko že mimo in preverjevalni zagon je ostal odprt za vedno.
        if self.posnetek:
            pogled.connect("load-changed", self._za_posnetek)
        # Pot projekta lahko vsebuje presledke ali sumnike. Golo "file://" sestavljanje je takrat
        # pustilo WebKit na praznem crnem zaslonu; GLib izdela pravilen, kodiran datotecni URI.
        self._koren_strani = GLib.filename_to_uri(os.path.join(KOREN, "assets", "os"), None)
        pogled.load_uri(self._koren_strani + "/" + stran)
        self.pogledi.append(pogled)
        return pogled

    # ------------------------------------------------------------------ delovna povrsina (Safeer Cinnamon)
    def _robovi(self) -> dict:
        """Kaj od zaslona zasedajo pult in dock (workarea): stran pusti ta prostor prazen."""
        zaslon = self._zaslon()
        if zaslon is None:
            return {"vrh": 0, "dno": 0, "levo": 0, "desno": 0}
        g, w = zaslon.get_geometry(), self._delovno_obmocje(zaslon)
        return {"vrh": max(0, w.y - g.y), "levo": max(0, w.x - g.x),
                "dno": max(0, (g.y + g.height) - (w.y + w.height)),
                "desno": max(0, (g.x + g.width) - (w.x + w.width))}

    def _ustvari_qml_namizje(self) -> bool:
        """Namizje v QML (kot na Windows); Splet, Safeer Player in razdelki ostanejo okna GTK4 v tem procesu.
        Napaka QML ali Namizje() (npr. brez primarnega zaslona) vrne False: ostane delovna povrsina WebKit
        (delovna.html). Prej je bilo crno okno brez rezerve ali sesutje v zanko ponovnih zagonov (pregled 14. 10.)."""
        lupina = None
        try:
            # Pod varuhom tece QML v procesu lupine (core/lupina_proces.py); tu samo streznik z isto logiko namizja.
            lupina = lupina_streznik.OddaljenaLupina(self) if lupina_streznik.locena() else os_lupina.Namizje(self)
            self.lupina = lupina
            self.pogled_delovna = self._qml_pogled = lupina.pogled
            lupina.pokazi()
        except Exception as e:  # noqa: BLE001 - rezerva: delovna povrsina WebKit
            print("[SafeerOS] namizje QML ni na voljo, delovna povrsina WebKit:", e, flush=True)
            try:
                if lupina is not None:
                    lupina.okno.hide()
            except Exception:  # noqa: BLE001
                pass
            self.lupina = None
            self.pogled_delovna = self._qml_pogled = None
            return False
        self.hold()          # okno QML ni okno Gtk.Application: brez tega bi se proces koncal takoj po zagonu
        self._ob_spremembi_zaslonov(lupina._zaslon_spremenjen)   # tudi dock na novo, ne samo okno namizja
        return True

    def _ustvari_delovno(self) -> None:
        """Okno delovne povrsine: cez cel zaslon, pod vsemi okni (kot namizje); vsebina se umakne pultu
        in docku (robovi iz workarea), zato se nic ne prekriva."""
        robovi = self._robovi()
        self._robovi_delovne = robovi
        # pozno: Safeer OS je ze tekel kot Player ali okno (_vklopi_delovno) - Qt mora dobiti EGL (glej os_lupina.pripravi).
        # Lupina v svojem procesu (varuh, core/lupina_streznik.py): v tem procesu ni Qt, namizje je v procesu lupine.
        if not self.posnetek and (lupina_streznik.locena() or os_lupina.pripravi(
                sys.argv[:1], pozno=bool(self.get_windows()))) and self._ustvari_qml_namizje():
            return
        if lupina_streznik.locena():
            varuh_procesov.obvesti("SAFEER_BREZ_LUPINE=1")   # spodaj delovna povrsina WebKit: varuh ugasne lupino
        pogled = self._nov_pogled("delovna.html?" + "&".join("%s=%d" % kv for kv in sorted(robovi.items())))
        okno = Gtk.ApplicationWindow(application=self, title="Safeer Cinnamon")
        # GTK4 nima set_wmclass, set_type_hint, set_keep_below, move: lastnosti X nastavi core/x11.py.
        x11.nastavi_razred(okno, "safeer-cinnamon", "Safeer Cinnamon")
        okno.set_icon_name(_ikona_safeer_os())
        x11.nastavi_vrsto(okno, "DESKTOP")
        okno.set_decorated(False)
        x11.nastavi_preskoci(okno)
        x11.nastavi_stanje(okno, "BELOW")
        zaslon = self._zaslon()
        g = zaslon.get_geometry() if zaslon else None
        if g is not None:
            x11.premakni(okno, g.x, g.y)
            okno.set_default_size(g.width, g.height)
            okno.set_size_request(g.width, g.height)
        # Prekrivanje: nad namizjem se lahko pokaze plosca Splet (iskanje po spletu iz zgornjega polja).
        prekrivanje = Gtk.Overlay()
        prekrivanje.set_child(pogled)
        okno.set_child(prekrivanje)
        self._prekrivanje_delovne = prekrivanje
        # GTK4: »destroy« pride sele, ko okna nihce vec ne drzi (self.okno ga drzi), zato pospravimo ob zapiranju.
        okno.connect("close-request", lambda *a: (self._koncaj(), False)[1])
        self.okno_delovna, self.pogled_delovna = okno, pogled
        okno.set_visible(True)
        try:
            vir = Gio.SettingsSchemaSource.get_default()
            if vir is not None and vir.lookup("org.cinnamon.desktop.background", True) is not None:
                self._nastavitve_ozadja = Gio.Settings.new("org.cinnamon.desktop.background")
                self._nastavitve_ozadja.connect("changed::picture-uri", self._ozadje_spremenjeno)
            # Kontrast in velikost besedila se lahko spremenita tudi drugje (ukaz, nastavitve Cinnamona): stikali sledita.
            if vir is not None and vir.lookup("org.cinnamon.theme", True) is not None:
                self._nastavitve_teme = Gio.Settings.new("org.cinnamon.theme")
                self._nastavitve_teme.connect("changed::name", lambda *_a: self._dogodek("videz", videz_cinnamon()))
            if vir is not None and vir.lookup("org.cinnamon.desktop.interface", True) is not None:
                self._nastavitve_vmesnika = Gio.Settings.new("org.cinnamon.desktop.interface")
                self._nastavitve_vmesnika.connect("changed::text-scaling-factor",
                                                  lambda *_a: self._dogodek("videz", videz_cinnamon()))
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] ozadje:", e)
        # Pult/dock se lahko pojavita sele po prijavi (Plank): robove preverimo se nekajkrat.
        GLib.timeout_add_seconds(3, self._preveri_robove)
        self._ob_spremembi_zaslonov(self._prestavi_delovno)

    def _preveri_robove(self) -> bool:
        if self.okno_delovna is None:
            return False
        robovi = self._robovi()
        if robovi != self._robovi_delovne:
            self._robovi_delovne = robovi
            self._dogodek("robovi", robovi)
        return True

    def _varuh_docka(self) -> None:
        """Vsakih 30 s: ce je dock vklopljen in Plank ne tece, ga safeer-cinnamon --dock-ozivi zazene znova (najvec 3-krat
        v 10 min). Lastnik, 17. 10. 2026: dock je izginil (Plank se ni vrnil) - »uporabnik ne zeli ostati brez docka«.
        V niti: ukaz pocaka na konec (brez zombijev), glavna nit ne caka. Isti pogoj (dock vklopljen, Plank ne tece)
        najprej preverimo tu, brez podprocesa: prej se je vsakih 30 s zagnala skripta bash (1300 vrstic) s pgrep."""
        if getattr(self, "_varuh_docka_tece", False) or not os_dock.dock_vklopljen() or os_dock.plank_tece():
            return
        self._varuh_docka_tece = True

        def nit() -> None:
            try:
                subprocess.run(os_dock._gostitelj(["safeer-cinnamon", "--dock-ozivi"]), stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
            except (OSError, subprocess.SubprocessError):
                pass
            finally:
                self._varuh_docka_tece = False
        threading.Thread(target=nit, daemon=True, name="safeer-varuh-docka").start()

    def _prestavi_delovno(self) -> None:
        zaslon = self._zaslon()
        if self.okno_delovna is None or zaslon is None:
            return
        g = zaslon.get_geometry()
        x11.premakni(self.okno_delovna, g.x, g.y)
        self.okno_delovna.set_size_request(g.width, g.height)
        self.okno_delovna.set_default_size(g.width, g.height)
        self._preveri_robove()
        # Dock Plank ne sledi spremembi locljivosti: safeer-cinnamon --dock ga postavi na novo (pocaka,
        # da se zaslon ustali). Robove delovne povrsine potem popravi _preveri_robove (vsake 3 s).
        try:
            subprocess.Popen(["safeer-cinnamon", "--dock"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True, env=zasebni_webkit.okolje_za_zunanje())
        except OSError:
            pass

    def _predvajaj_cakajoco(self) -> bool:
        pot, self._cakajoca_datoteka = self._cakajoca_datoteka, ""
        if pot:
            self._predvajaj_datoteko(pot)
        ponudba, self._cakajoca_ponudba = self._cakajoca_ponudba, None
        if ponudba:
            self._predvajaj_ponudbo(ponudba)
        return False

    def _predvajaj_ponudbo(self, besedilo) -> bool:
        """"Poslji na napravo": uporabnik je v obvestilu Controla pritisnil Sprejmi - predvajamo, kar je ponudila druga
        naprava, pri isti sekundi: datoteko izvora prek njenega streznika (zeton za ta racunalnik), datoteko tretje
        naprave z lastnim zetonom (Control: Datoteke z mapo datoteke), spletni tok s svojim naslovom."""
        try:
            p = json.loads(besedilo) if isinstance(besedilo, str) else besedilo
        except Exception:  # noqa: BLE001
            return False
        if not isinstance(p, dict) or not isinstance(p.get("item"), dict):
            return False
        self._medijski_klicatelj = None      # ponudba z druge naprave: okno z videom nad Medijskim centrom (_stars_medija)
        if self.okno is None and self.okno_predvajalnik is None:
            self._cakajoca_ponudba = p
            self._odpri_medijsko_okno()
            GLib.timeout_add(1500, self._predvajaj_cakajoco)
            return True
        from core import link_predvajanje
        item = p["item"]
        naslov = str(item.get("naslov") or "")
        video = bool(item.get("video"))
        zacetek = max(0, int(p.get("position_ms") or 0) // 1000)
        od = str(p.get("od") or "")
        od_ime = str(p.get("od_ime") or od)
        streznik = p.get("server") if isinstance(p.get("server"), dict) else None
        naprava = str(p.get("server_device") or "")
        kljuc = str(p.get("kljuc") or "")
        oznaka = str(item.get("id") or "")
        lokalna = str(p.get("lokalna_pot") or "")
        if lokalna and os.path.isfile(lokalna):
            # Datoteka tega racunalnika (Control jo je prepoznal): z diska, pri isti sekundi.
            return self._predvajaj_neposredno(GLib.filename_to_uri(lokalna, None), vrsta="video" if video else "medij",
                                             prikazi=video, ime=naslov or os_knjiznica.naslov_datoteke(Path(lokalna)), zacetek=zacetek)
        if naprava and streznik is None:
            # Datoteka tretje naprave (telefon, drug racunalnik): svoj zeton dobimo kot pri Datotekah (files.list z mapo).
            r = _control_naprave("Datoteke", naprava, link_predvajanje.mapa_datoteke(oznaka))
            streznik = r.get("server") if r.get("ok") and isinstance(r.get("server"), dict) else None
            kljuc = str(r.get("kljuc") or kljuc)
        if streznik is not None:
            vnos = {"id": oznaka, "name": naslov or oznaka, "type": "video" if video else "audio", "mime": str(item.get("mime") or "")}
            return self._predvajaj_z_naprave(streznik, kljuc, [vnos], 0, izvor=od_ime, naprava=naprava or od, zacetek=zacetek)
        zvok = str(item.get("zvok") or "")
        if zvok.startswith(("http://", "https://")):
            vrsta = "tv" if item.get("kanal") else "radio" if item.get("radio") else "video" if video else "medij"
            return self._predvajaj_neposredno(zvok, vrsta=vrsta, prikazi=video, ime=naslov or zvok, zacetek=zacetek)
        return False

    def _odpri_razdelek(self, razdelek: str) -> bool:
        """Iz delovne povrsine: odpre glavno okno Safeer OS na razdelku (npr. naprave). Medijski center (»media«,
        »mediji:<iskanje>«) se odpre v svojem oknu Safeer Player - uporabnik ob kliku nanj ne pricakuje cele lupine
        Safeer OS (lastnik, 9. 10. 2026)."""
        iskanje = razdelek_predvajalnika(razdelek)
        if iskanje is not None:
            return self._odpri_predvajalnik(iskanje)
        if self.okno is None and _ima_delovno(self):
            # Na delovni povrsini se stara lupina Safeer OS ne odpira vec (lastnik, 12. 10. 2026: »namizno okolje lahko
            # ponudi vec udobja kot aplikacija«): vsak razdelek ima svoje mesto na namizju.
            osnova = "zapiski" if razdelek.startswith("zapisek:") else \
                "sporocila" if razdelek.startswith(("pogovor:", "sporocila:", "kanal:")) else razdelek.split("#", 1)[0]
            if osnova == "sporocila" and not sporocila_vklop.sporocila_vklopljena():
                return False                                 # Sporocila izklopljena: razdelka ni (tudi z Linka)
            if osnova in RAZDELKI_V_SVOJEM_OKNU:
                return self._odpri_okno_razdelka(osnova, razdelek)
            if osnova == "naprave":
                return self._prijava()                       # Safeer Control: prijava ali seznam naprav
            if osnova == "splet":
                return self._splet_na_namizju("", domov=True)
            if osnova in PODSTRANI_NASTAVITEV or osnova == "vodnik":
                # Vodnik ob prvem zagonu: na namizju ga pokaze okno Nastavitve (prej ga uporabnik namizja ni videl).
                return self._odpri_okno_razdelka("nastavitve", razdelek)
            if osnova.split(":", 1)[0] in RAZDELKI_NAMIZJA:
                return self._pokazi_na_namizju(osnova.split(":", 1)[0], razdelek.partition(":")[2])
            if osnova in ("", "domov"):
                lupina = getattr(self, "lupina", None)
                if lupina is not None and getattr(lupina, "v_oknu", False):
                    lupina.dvigni()                     # aplikacija v oknu: domaci zaslon je to okno
                return True                                  # delovna povrsina je domaci zaslon
            # Razdelka, ki ga namizje nima, ni: stare lupine z namizja ne odpremo (cilj 3.1, lastnik 18. 10. 2026:
            # »kdor uporablja namizje Safeer, aplikacije Safeer OS ne potrebuje vec«).
            print("[SafeerOS] razdelek, ki ga namizje nima:", razdelek, flush=True)
            return False
        if self.okno is None:
            self._ustvari_okno()
            if razdelek:
                GLib.timeout_add(1500, lambda: (self._dogodek("pojdi", razdelek), False)[1])
            return True
        return self._domov(razdelek)

    def _pokazi_na_namizju(self, razdelek: str, pot: str = "") -> bool:
        """Datoteke in Programi sta plosci namizja (QML ali delovna povrsina WebKit): razdelek z drugega mesta jih pokaze
        tam (Datoteke pri mapi [pot]). Prej se je odprlo staro glavno okno Safeer OS (popis 3.1, 18. 10. 2026)."""
        lupina = getattr(self, "lupina", None)
        if lupina is not None and getattr(lupina, "v_oknu", False):
            lupina.dvigni()                             # aplikacija v oknu: plosci sta v tem oknu
        pogled = getattr(self, "_qml_pogled", None) or getattr(self, "pogled_delovna", None)
        if pogled is None:
            return False
        self._dogodek("pokaziNaNamizju", {"razdelek": razdelek, "pot": pot}, pogled)
        return True

    # ------------------------------------------------------------------ sporocila na namizju (kuverta in plosca)
    #: Varnostno osvezevanje stevila; sicer se kuverta osvezi ob dogodku (os_sporocila.ob_spremembi: novo sporocilo,
    #: prebran pogovor, koncana sinhronizacija). Periodicno je potrebno samo, ce Control tece kot locen proces.
    KUVERTA_OSVEZI_S = 120

    #: Ikona kuverte v pultu: predmet z metodo nastavi(pot_png, opis); klik nanjo poklice _preklopi_plosco_sporocil().
    #: None: kuverte ni.
    kuverta_pult = None

    def _namesti_kuverto(self):
        """Ikona kuverte v pultu. GTK3 je imel XApp.StatusIcon (Cinnamon) ali Gtk.StatusIcon - obeh v GTK4 ni. Kuverta je
        StatusNotifierItem (core/pladenj_sni.py) - isti sklad kot ikona Controla, brez Qt, zato dela tudi z namizjem
        WebKit. Ikona Qt (QSystemTrayIcon) je samo nadomestek, ce SNI ne gre (ni vodila D-Bus)."""
        if self.kuverta_pult is None:
            ob_kliku = lambda: GLib.idle_add(lambda: (self._preklopi_plosco_sporocil(), False)[1])  # noqa: E731
            try:
                from core import pladenj_sni
                self.kuverta_pult = pladenj_sni.Kuverta(ob_kliku, BESEDILA_KUVERTE.get(_jezik(), BESEDILA_KUVERTE["en"])[0])
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] kuverta (SNI):", e)
                if self.lupina is not None:
                    try:
                        self.kuverta_pult = os_lupina.Kuverta(ob_kliku)
                    except Exception as e2:  # noqa: BLE001
                        print("[SafeerOS] kuverta (Qt):", e2)
        return self.kuverta_pult or False

    def _zacni_kuverto(self) -> None:
        """Kuverta v pultu s stevilom neprebranih sporocil (glej _namesti_kuverto)."""
        if getattr(self, "_kuverta", None) is not None or not sporocila_vklop.sporocila_vklopljena():
            return
        k = self._namesti_kuverto()
        if not k:
            print("[SafeerOS] kuverta v pultu: ni ikone pulta", flush=True)
            return
        self._kuverta, self._kuverta_stevilo = k, -1
        self._osvezi_kuverto()
        os_sporocila.ob_spremembi(lambda: GLib.idle_add(lambda: (self._osvezi_kuverto(), False)[1]))
        GLib.timeout_add_seconds(self.KUVERTA_OSVEZI_S, lambda: (self._osvezi_kuverto(), True)[1])

    def pokazi_sporocila(self) -> None:
        """Klik na obvestilo novega sporocila (core/safeer_link.py): odpre plosco Sporocil, ce ni ze odprta."""
        if not sporocila_vklop.sporocila_vklopljena():
            return

        def zdaj() -> bool:
            okno = getattr(self, "_plosca_sporocil", None)
            if okno is None or not okno.get_visible():
                self._preklopi_plosco_sporocil()
            return False
        GLib.idle_add(zdaj)

    def _osvezi_kuverto(self) -> None:
        if not sporocila_vklop.sporocila_vklopljena():
            return
        # Vgrajeni kanali: zadnje znano stevilo je shranjeno - znacka je pravilna ze ob zagonu, preden se kanal nalozi.
        spletni = self._kanali().neprebrano_skupaj() if self._kanali() is not None else 0

        def delo() -> None:
            try:
                # Zadnje znano stevilo iz baze (pravo ze ob zagonu, preden se kanali povezejo), brez branja nabiralnika.
                n = spletni + int(self.sporocila.neprebrano_skupaj())
            except Exception as e:  # noqa: BLE001 - brez Sporocil kuverta ostane brez stevila
                print("[SafeerOS] kuverta:", e)
                n = 0
            GLib.idle_add(lambda: (self._narisi_kuverto(n), False)[1])
        threading.Thread(target=delo, name="safeer-kuverta", daemon=True).start()

    def _narisi_kuverto(self, n: int) -> None:
        lupina = getattr(self, "_qml_pogled", None)
        if lupina is not None:
            # Gumb Sporocila na namizju QML kaze isto stevilo kot kuverta - tudi kadar ikone v pultu ni (popis 3.1).
            lupina.qml_dogodek("sporocilaStevilo", {"n": int(n)})
        k = getattr(self, "_kuverta", None)
        if k is None or n == self._kuverta_stevilo:
            return
        self._kuverta_stevilo = n
        pot = ikona_kuverte(n, os.path.join(GLib.get_user_cache_dir(), "safeer-os"))
        napis = BESEDILA_KUVERTE.get(_jezik(), BESEDILA_KUVERTE["en"])
        opis = napis[1].format(n=n) if n else napis[0]
        try:
            k.nastavi(pot, opis)
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] kuverta:", e)

    def _preklopi_plosco_sporocil(self) -> None:
        okno = getattr(self, "_plosca_sporocil", None)
        if okno is not None and okno.get_visible():
            self._skrij_plosco_sporocil()
            return
        # Klik na kuverto, ko je plosca odprta: plosca se je ze skrila ob izgubi fokusa - ne odpremo je znova.
        if time.monotonic() - getattr(self, "_plosca_skrita_ob", 0.0) < 0.4:
            return
        if okno is None:
            okno = Gtk.Window(title=BESEDILA_KUVERTE.get(_jezik(), BESEDILA_KUVERTE["en"])[0])
            okno.set_application(self)
            _razred_okna(okno, "Sporocila")
            okno.set_decorated(False)
            x11.nastavi_preskoci(okno, opravilna=True, preklopnik=False)
            x11.nastavi_vrsto(okno, "DIALOG")
            _prozorno_okno(okno)
            pogled = self._nov_pogled("sporocila-plosca.html?jezik=" + _jezik())
            prozorno = Gdk.RGBA()
            prozorno.parse("rgba(0,0,0,0)")
            pogled.set_background_color(prozorno)
            okno.set_child(pogled)
            okno.connect("close-request", lambda *_a: (self._skrij_plosco_sporocil(), True)[1])
            # Klik drugam skrije plosco (kot meni v pultu); GTK4: ni focus-out-event, je lastnost is-active.
            okno.connect("notify::is-active", lambda o, *_a: o.is_active() or
                         GLib.timeout_add(150, self._skrij_ce_ni_fokusa))
            self._plosca_sporocil, self._pogled_plosce = okno, pogled
        else:
            self._js("window.safeerPloscaOsvezi && window.safeerPloscaOsvezi();", self._pogled_plosce)
        zaslon = self._zaslon()
        g = self._delovno_obmocje(zaslon) if zaslon else None
        sirina = 400
        visina = min(660, g.height - 16) if g else 640
        okno.set_default_size(sirina, visina)
        if g:
            x11.premakni(okno, g.x + g.width - sirina - 10, g.y + 8)
        _v_ospredje(okno)
        self._osvezi_kuverto()

    def _skrij_ce_ni_fokusa(self) -> bool:
        okno = getattr(self, "_plosca_sporocil", None)
        if okno is not None and okno.get_visible() and not okno.is_active():
            self._skrij_plosco_sporocil()
        return False

    def _skrij_plosco_sporocil(self) -> bool:
        okno = getattr(self, "_plosca_sporocil", None)
        if okno is not None and okno.get_visible():
            okno.set_visible(False)
            self._plosca_skrita_ob = time.monotonic()
        self._osvezi_kuverto()
        return True

    def _en_vir_naprej(self) -> None:
        """Streznik naprej za »Safeer Scit« ima en vir: Scit (velja za ves racunalnik in za Splet; doh_proxy.naprej_iz).
        Kdor ga je do zdaj izbral samo v Spletu (nastavitve brskalnika), ga obdrzi: ob prvem zagonu ga prevzame Scit."""
        try:
            from core import doh_proxy
            if self.shramba.get("scit_naprej") is None:
                from core.config import ConfigManager
                c = ConfigManager()
                izbira = c.get("scit_naprej")
                if c.get("dns_izbira_uporabnika") and izbira in os_scit.IZBIRE_NAPREJ and izbira != os_scit.PRIVZETI_NAPREJ:
                    self.scit.nastavi_naprej(izbira, str(c.get("scit_naprej_po_meri", "") or ""))
            doh_proxy.nastavi_vir_naprej(self.scit)
        except Exception as e:  # noqa: BLE001 - brez libsoup Splet ni na voljo, Scit dela naprej
            print("[SafeerOS] scit, streznik naprej:", type(e).__name__, e, flush=True)

    # ------------------------------------------------------------------ Safeer Scit v pultu (poleg kuverte)
    #: Stanje in stevec blokiranih v pultu se osvezita na toliko sekund, takoj pa po preklopu iz pulta ali Nastavitev.
    SCIT_PULT_OSVEZI_S = 15
    #: pladenj_sni.ScitPult, ko tece delovna povrsina; None: ikone Scita ni.
    scit_pult = None
    _scit_pult_zaposlen = False

    def _zacni_scit_pult(self) -> None:
        if self.scit_pult is not None:
            return
        try:
            from core import pladenj_sni
            self.scit_pult = pladenj_sni.ScitPult(
                pladenj_sni.BESEDILA_SCITA.get(_jezik(), pladenj_sni.BESEDILA_SCITA["en"]),
                lambda: GLib.idle_add(lambda: (self._odpri_razdelek("scit"), False)[1]),
                self._preklopi_scit_iz_pulta, os.path.join(GLib.get_user_cache_dir(), "safeer-os"),
                barve=os_lupina.tokeni())
        except Exception as e:  # noqa: BLE001 - brez vodila D-Bus ikone Scita ni, Scit dela naprej
            print("[SafeerOS] scit v pultu:", e, flush=True)
            return
        self._osvezi_scit_pult()
        GLib.timeout_add_seconds(self.SCIT_PULT_OSVEZI_S, lambda: (self._osvezi_scit_pult(), True)[1])

    def _osvezi_scit_pult(self, stanje: Optional[dict] = None) -> None:
        """Stanje Scita v pult. Brez podanega stanja vzame hitro stanje pulta (Scit.stanje_pulta: brez podprocesov); v
        ozadju le, ce je na vrsti preverba systemd-resolved (najvec vsakih 5 min). Prej nit in polno stanje vsakih 15 s."""
        if self.scit_pult is None or self._scit_pult_zaposlen:
            return
        if stanje is None and self.scit.razlog_svez():
            stanje = self.scit.stanje_pulta(preveri=False)
        if stanje is not None:
            self.scit_pult.osvezi(stanje)
            return

        def delo() -> None:
            try:
                s = self.scit.stanje_pulta()
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] scit v pultu:", e)
                return
            GLib.idle_add(lambda: (self._osvezi_scit_pult(s), False)[1])
        threading.Thread(target=delo, name="safeer-scit-pult", daemon=True).start()

    def _preklopi_scit_iz_pulta(self, vklop: bool) -> None:
        """Vklopi/Izklopi v meniju pulta: ista pot kot stikalo v Nastavitvah (Scit.nastavi, ob prvem vklopu sistem
        vprasa za geslo), zato v svoji niti."""
        self._scit_pult_zaposlen = True

        def delo() -> None:
            try:
                s = self.scit.nastavi(bool(vklop))
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] scit v pultu:", e)
                s = None

            def konec() -> bool:
                self._scit_pult_zaposlen = False
                self._osvezi_scit_pult(s)
                return False
            GLib.idle_add(konec)
        threading.Thread(target=delo, name="safeer-scit-preklop", daemon=True).start()

    def _po_scitu(self, stanje: dict) -> dict:
        """Scit je spremenjen (Nastavitve, okno Safeer Scit, pult): pult in vse odprte strani pokazejo novo stanje takoj -
        vir je en sam (self.scit), nobeno okno ne kaze starega."""
        GLib.idle_add(lambda: (self._osvezi_scit_pult(stanje), False)[1])
        # Klici mostu za Scit tecejo v svoji niti: dogodek (tudi QML) posljemo iz glavne niti.
        GLib.idle_add(lambda: (self._dogodek("scit", stanje), False)[1])
        return stanje

    def _scit_statistika(self) -> dict:
        """Statistika za okno Safeer Scit: DNS za ves racunalnik, Splet in Sporocila (skupni stevci brskalnika), pravila
        proti sledenju (core/scit_pravila.py: vgrajen ali podpisan seznam)."""
        izid: dict = {"scit": self.scit.stanje()}
        try:
            from core.config import ConfigManager
            c = ConfigManager()
            izid["splet"] = {"oglasi": int(c.get("total_ads_blocked", 0) or 0),
                             "groznje": int(c.get("total_threats_blocked", 0) or 0)}
        except Exception:  # noqa: BLE001
            izid["splet"] = {}
        try:
            from core import scit_pravila
            izid["pravila"] = scit_pravila.skupna(zazeni=False).stanje()
        except Exception:  # noqa: BLE001
            izid["pravila"] = {}
        return izid

    # ------------------------------------------------------------------ okna razdelkov (delovna povrsina)
    def _odpri_okno_razdelka(self, ime: str, cilj: str = "") -> bool:
        """Zapiski, Sporocila ali Nastavitve v svojem oknu (ista stran, index.html?razdelek=<ime>, kot Safeer Player za
        Medijski center) - brez stranske vrstice in glave stare lupine. Odprto okno pride v ospredje in gre na cilj."""
        par = self.okna_razdelkov.get(ime)
        if par is None:
            stran = "index.html?" + urllib.parse.urlencode([("razdelek", ime), ("jezik", _jezik())],
                                                         quote_via=urllib.parse.quote)
            pogled = self._nov_pogled(stran)
            okno = Gtk.ApplicationWindow(application=self, title=_naslov_razdelka(ime))
            _razred_okna(okno, ime)
            # Kanali Sporocil (spletni klepeti, namizni programi) so nad stranjo na mestu vsebine (prekrivanje).
            prekrivanje = self._prekrivanje_kanalov(pogled)
            zaslon = self._zaslon_za_okno()
            g = self._delovno_obmocje(zaslon) if zaslon else None
            sirina, visina = (min(1280, int(g.width * 0.85)) if g else 1200, min(860, int(g.height * 0.85)) if g else 800)
            okno.set_default_size(sirina, visina)
            self._na_sredino(okno, sirina, visina)
            okno.set_child(prekrivanje)
            # Zapiranje okno samo skrije: naslednji klic ga takoj vrne (nezapisano besedilo zapiska ostane).
            okno.connect("close-request", lambda w, *_: (w.set_visible(False), True)[1])
            self.okna_razdelkov[ime] = par = (okno, pogled)
            okno.set_visible(True)
            if cilj and cilj != ime:
                GLib.timeout_add(1500, lambda: (self._js("window.safeerOsPojdi && window.safeerOsPojdi(%s);"
                                                          % json.dumps(cilj), pogled), False)[1])
        else:
            okno, pogled = par
            self._js("window.safeerOsPojdi && window.safeerOsPojdi(%s);" % json.dumps(cilj or ime), pogled)
        _v_ospredje(par[0])
        return True

    # ------------------------------------------------------------------ Safeer Player (Medijski center v svojem oknu)
    def _odpri_predvajalnik(self, iskanje: str = "") -> bool:
        """Safeer Player: Medijski center v svojem oknu, brez stranske vrstice in glave Safeer OS. Stran je ista
        (index.html?predvajalnik=1 pokaze samo razdelek media), most in predvajalnik sta ista kot v glavnem oknu. Ce
        okno ze obstaja (tudi skrito), pride v ospredje; iskani niz gre v iskanje Medijskega centra."""
        iskanje = str(iskanje or "").strip()
        if self.okno_predvajalnik is None:
            self._ustvari_predvajalnik(iskanje)
            return True
        if iskanje:
            self._js("window.safeerOsPojdi && window.safeerOsPojdi(%s);" % json.dumps("mediji:" + iskanje),
                     self.pogled_predvajalnik)
        # Lastnik, 11. 10. 2026: Safeer Player se vedno odpre cez cel zaslon - tudi ko ga odpremo znova ali iscemo.
        self.okno_predvajalnik.maximize()
        # Okno, ki ga je uporabnik zaprl (upravljalnik oken ga je umaknil, mi smo ga skrili), GTK ob ponovnem prikazu
        # ne oznaci s casom - Muffin ga potem le oznaci z »zahteva pozornost« in ostane za drugim oknom (izmerjeno
        # 11. 10. 2026). Zato cas uporabe nastavimo sami, pred prikazom (_v_ospredje).
        _v_ospredje(self.okno_predvajalnik)
        return True

    def _ustvari_predvajalnik(self, iskanje: str = "") -> None:
        # Jezik v naslovu strani: Medijski center se pokaze takoj, brez cakanja na »zacetek« (glej os.js zacni).
        stran = "index.html?" + urllib.parse.urlencode(
            [("predvajalnik", "1"), ("jezik", _jezik())] + ([("iskanje", iskanje)] if iskanje else []),
            quote_via=urllib.parse.quote)
        pogled = self._nov_pogled(stran)
        okno = Gtk.ApplicationWindow(application=self, title="Safeer Player")
        # Svoja skupina in ikona v pultu (ne »Safeer OS«): WM_CLASS se ujema s StartupWMClass vnosa Safeer Player.
        x11.nastavi_razred(okno, *WMCLASS_PREDVAJALNIKA)
        self._ikona_predvajalnika(okno)
        velikost = _velikost_okna(os.environ.get("SAFEER_OS_OKNO", "")) if self.posnetek else None
        if velikost:
            okno.set_default_size(*velikost)
        else:
            zaslon = self._zaslon_za_okno()
            g = self._delovno_obmocje(zaslon) if zaslon else None
            sirina, visina = (min(1440, int(g.width * 0.9)) if g else 1280, min(900, int(g.height * 0.9)) if g else 800)
            okno.set_default_size(sirina, visina)
            if self.posnetek:
                self._na_sredino(okno, sirina, visina)   # sicer je povecano (spodaj); premik bi ga motil
        # Prekrivanje: nad stranjo je lahko vgrajeni spletni predvajalnik (YouTube s seznama, os_medijska_plast).
        okno.set_child(self._prekrivanje_kanalov(pogled))
        # Vgrajen vir: F11 in Escape dobi okno pred tujo stranjo v okvirju (glej _vgrajeno_tipka); najprej plast predvajalnika.
        _tipke(okno, lambda o, e: self._plast_tipka(o, e) or self._vgrajeno_tipka(pogled, e), zajem=True)
        okno.connect("close-request", self._zapri_predvajalnik)
        self.okno_predvajalnik, self.pogled_predvajalnik = okno, pogled
        if not self.posnetek:
            # Lastnik, 11. 10. 2026: Safeer Player se vedno odpre cez cel zaslon (povecano okno, dock in pult ostaneta);
            # nacin za kavc (kavc.js) ga da cez cel zaslon brez pulta.
            okno.maximize()
        okno.set_visible(True)
        if self.posnetek and self.okno is None:
            # Kot pri glavnem oknu: posnetek mora nastati tudi, ce WebKit konca nalaganja ne javi.
            GLib.timeout_add(8000 + int(os.environ.get("SAFEER_OS_POSNETEK_ZAMIK", "0") or 0), self._rezervni_posnetek)

    @staticmethod
    def _ikona_predvajalnika(okno) -> None:
        """Ikona okna Safeer Player iz strani (assets/os/predvajalnik.svg) - je v vsakem paketu, tudi ob zagonu iz
        repozitorija; namescena ikona vnosa (Icon=) ima isto sliko. GTK4 nima set_icon_from_file: mapo strani dodamo
        temi ikon (datoteka predvajalnik.svg v njej je ikona »predvajalnik«)."""
        try:
            tema = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            mapa = os.path.join(KOREN, "assets", "os")
            if mapa not in (tema.get_search_path() or []):
                tema.add_search_path(mapa)
            if not tema.has_icon("predvajalnik"):
                raise LookupError("predvajalnik.svg ni v temi ikon")
            okno.set_icon_name("predvajalnik")
        except Exception as e:  # noqa: BLE001 - brez nalagalnika SVG ostane ikona Safeer
            print("[SafeerOS] ikona predvajalnika:", e)
            okno.set_icon_name(_ikona_safeer_os())

    def _zapri_predvajalnik(self, okno, *_a) -> bool:
        """Zapiranje okna Safeer Player. Ob delovni povrsini ali glavnem oknu se okno samo skrije: predvajanje tece
        naprej (tudi vrsta skladb iz kataloga, ki jo vodi njegova stran), mini predvajalnik ga kaze, naslednji klic
        okno takoj vrne. Samostojni Safeer Player (zagon iz menija brez Safeer OS) se zapre kot vsak predvajalnik."""
        if _ima_delovno(self) or self.okno is not None:
            okno.set_visible(False)
            return True
        if self._plosca_spleta is not None and self._plosca_spleta.get_visible():
            # Splet, odprt iz tega Safeer Playerja (povezava, spletna aplikacija), ostane odprt: predvajanje se ustavi
            # kot ob zaprtju predvajalnika, Safeer OS pa se konca, ko uporabnik zapre se Splet (_skrij_splet_na_namizju).
            okno.set_visible(False)
            self._pocisti_medijski_pogled()
            self._ustavi_neposredni_medij()
            return True
        self._koncaj()
        return True

    def _okno_klica(self, pogled):
        """Sistemska okna (izbira datotek, mape, toka), odprta iz Safeer Playerja, so nad njim, ne nad glavnim oknom.
        Za klice iz glavnega okna None - tam ostane, kot je bilo."""
        if pogled is not None and pogled is self.pogled_predvajalnik:
            return self.okno_predvajalnik
        return None

    @staticmethod
    def _zazeni_orodje(ukaz: list) -> bool:
        """Zazene sistemsko orodje (nastavitve docka, ozadja) loceno od Safeer OS, brez nasih zasebnih poti."""
        try:
            subprocess.Popen(ukaz, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                             env=zasebni_webkit.okolje_za_zunanje())
            return True
        except OSError:
            return False

    def _ozadje_spremenjeno(self, *_a) -> None:
        """Uporabnik je v Cinnamonu izbral novo ozadje: delovna povrsina ga prevzame takoj."""
        ozadje = os_sistem.ozadje_namizja()
        self._dogodek("ozadje", ("file://" + GLib.uri_escape_string(ozadje, "/", False)) if ozadje else "")

    #: Slog plosce Splet na namizju - barve namizja (assets/os/delovna.css).
    CSS_SPLETA_NA_NAMIZJU = b"""
        #splet-namizje { background-color: rgba(14, 23, 39, 0.98); border: 1px solid rgba(215, 234, 255, 0.34);
            border-radius: 16px; box-shadow: 0 24px 60px rgba(0, 0, 0, 0.55); padding: 6px; }
        #splet-namizje-glava { padding: 4px 8px 6px 12px; }
        #splet-namizje-glava label { color: #eaf2ff; font-weight: bold; }
        #splet-namizje-glava button { background-image: none; background-color: rgba(16, 26, 43, 0.8); color: #eaf2ff;
            border: 1px solid rgba(211, 229, 255, 0.23); border-radius: 10px; padding: 4px 12px; box-shadow: none;
            text-shadow: none; }
        #splet-namizje-glava button:hover { background-color: rgba(104, 168, 229, 0.20); border-color: #9dceff; }
    """

    def _spletni_zadetki(self, niz: str, povratni) -> None:
        """Sprotni zadetki spleta v lupi (core/spletni_zadetki.py): stran rezultatov izbranega iskalnika v skritem pogledu
        ISTE seje kot Splet. Brez peskovnika WebKita ali ob izklopu v Prilagodi: prazno."""
        niz = " ".join(str(niz or "").split())[:200]
        if len(niz) < 3 or not self._peskovnik_na_voljo():
            povratni([])
            return
        try:
            self._ustvari_splet_namizja(prvi_zavihek=False)
            if getattr(self, "_predogled_iskanja", None) is None:
                from core.spletni_zadetki import PredogledIskanja
                splet = self._spletni_namizje
                self._predogled_iskanja = PredogledIskanja(Gtk, WebKit2, GLib, splet.seja, splet.kontekst,
                                                           pripravi=splet.pripravi_skriti_pogled,
                                                           pozabi=splet.pozabi_skriti_pogled)
            ime = IMENA_ISKALNIKOV.get(_kljuc_iskalnika(), "")
            # Lupa pove, kateri iskalnik je dobil niz (oznaka pod zadetki, lastnik 20. 10. 2026).
            from core.spletni_zadetki import z_iskalnikom
            self._predogled_iskanja.isci(_iskalnik() + GLib.uri_escape_string(niz, None, False),
                                         lambda r: povratni(z_iskalnikom(r, ime)))
        except Exception as e:  # noqa: BLE001 - lupa brez sprotnih zadetkov dela naprej
            print("[SafeerOS] sprotni zadetki:", e, flush=True)
            povratni([])

    def _splet_na_namizju(self, niz: str, vrh: float = 0, domov: bool = False) -> bool:
        """Iskanje po spletu iz zgornjega polja delovne povrsine: rezultati v plosci na namizju (isti vgrajeni
        brskalnik z vsemi moznostmi kot Splet v Safeer OS: zavihki, naslov, Scit, meni), ne v drugem programu.
        `vrh`: spodnji rob iskalnega polja (CSS px), plosca je tik pod njim. Brez peskovnika: privzeti brskalnik.
        Isto okno Splet dobijo tudi povezave iz Zapiskov, Sporocil, Safeer Playerja in spletnih aplikacij, kadar
        glavnega okna ni (_splet) - tudi brez delovne povrsine (samo Safeer Player): en proces, en Splet."""
        niz = str(niz or "").strip()
        if not niz and not domov:
            return False
        # domov: »Splet« iz iskanja na delovni povrsini brez niza - zacetna stran Spleta (url "" = domaca stran).
        url = "" if not niz else niz if niz.lower().startswith(("http://", "https://")) else \
            _iskalnik() + GLib.uri_escape_string(niz, None, False)
        if not self._peskovnik_na_voljo():
            return self._odpri_v_brskalniku(niz) if niz else False
        self._ustvari_splet_namizja()
        okno = self._plosca_spleta
        zaslon = self._zaslon()
        g = self._delovno_obmocje(zaslon) if zaslon else None
        x0, y0, sirina, visina = (g.x, g.y, g.width, g.height) if g else (0, 0, 1280, 800)
        # Lastnik, 11. 10. 2026: Splet se odpre cez cel zaslon (kot Safeer Player) - pult in dock ostaneta vidna.
        okno.set_default_size(sirina, visina)
        x11.premakni(okno, x0, y0)
        okno.set_visible(True)
        okno.maximize()
        self._spletni_namizje.odpri(url)
        _v_ospredje(okno)
        try:
            self._spletni_namizje.trenutni().grab_focus()
        except Exception:  # noqa: BLE001
            pass
        return True

    def _ustvari_splet_namizja(self, prvi_zavihek: bool = True) -> None:
        """Plosca Splet na namizju (okno ostane skrito, dokler je ne odpre _splet_na_namizju). prvi_zavihek=False: jedro
        za vgrajene kanale Sporocil - brez zavihka (in brez spletnega procesa zanj), dokler uporabnik ne odpre Spleta."""
        if self._plosca_spleta is None:
            from core.os_splet import VdelaniSplet
            _css(self.CSS_SPLETA_NA_NAMIZJU)
            self._spletni_namizje = VdelaniSplet(Gtk, Gdk, Gio, GLib, WebKit2, KOREN, _jezik, _stanje_povezave_spleta,
                                                 self._splet_v_zapisek, self.okno_delovna,
                                                 stremio_dodatek=self._odpri_stremio_dodatek,
                                                 prvi_zavihek=prvi_zavihek, config=self._config_spleta())
            # Povezava iz vgrajenega kanala Sporocil (target=_blank) se odpre v tem Spletu, v novem zavihku.
            self._spletni_namizje.odpri_zunaj = lambda naslov: self._splet(naslov, True)
            self._spletni_namizje.zasciteni_podatki = self._kanali().zasciteni
            plosca = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            plosca.set_name("splet-namizje")
            glava = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            glava.set_name("splet-namizje-glava")
            glava.append(Gtk.Label(label=BESEDILA_SPLETA_NA_NAMIZJU.get(_jezik(), BESEDILA_SPLETA_NA_NAMIZJU["en"])[0]))
            presledek = Gtk.Box()
            presledek.set_hexpand(True)
            glava.append(presledek)
            v_brskalniku = Gtk.Button(label=BESEDILA_SPLETA_NA_NAMIZJU.get(_jezik(), BESEDILA_SPLETA_NA_NAMIZJU["en"])[1])
            v_brskalniku.connect("clicked", lambda *_: self._splet_namizja_v_brskalnik())
            glava.append(v_brskalniku)
            zapri = Gtk.Button(label="✕")
            zapri.set_tooltip_text(BESEDILA_SPLETA_NA_NAMIZJU.get(_jezik(), BESEDILA_SPLETA_NA_NAMIZJU["en"])[2])
            zapri.connect("clicked", lambda *_: self._skrij_splet_na_namizju())
            glava.append(zapri)
            # Za glavo se okno premakne (okno nima okvirja): GTK4 Gtk.WindowHandle namesto EventBox + begin_move_drag.
            okvir_glave = Gtk.WindowHandle()
            okvir_glave.set_child(glava)
            plosca.append(okvir_glave)
            self._spletni_namizje.gradnik.set_vexpand(True)
            plosca.append(self._spletni_namizje.gradnik)
            # Svoje okno brez okvirja (videz plosce namizja): namizje je vedno pod vsemi okni, rezultati pa morajo
            # priti naprej. Za glavo se okno premakne; Esc ali ✕ ga skrije.
            okno = Gtk.Window(title=BESEDILA_SPLETA_NA_NAMIZJU.get(_jezik(), BESEDILA_SPLETA_NA_NAMIZJU["en"])[0])
            _razred_okna(okno, "Splet")
            okno.set_decorated(False)
            okno.set_application(self)
            _prozorno_okno(okno)
            okno.set_child(plosca)
            # Esc: najprej stran (izhod iz celozaslonskega videa ...), sele neporabljen skrije okno (glej
            # _tipka_splet_na_namizju); dvojni Esc ujamemo pred stranjo.
            _tipke(okno, self._dvojni_esc_splet, zajem=True)
            esc = Gtk.ShortcutController()
            esc.add_shortcut(Gtk.Shortcut.new(Gtk.ShortcutTrigger.parse_string("Escape"),
                                              Gtk.CallbackAction.new(lambda *_a: self._skrij_splet_na_namizju())))
            okno.add_controller(esc)
            okno.connect("close-request", lambda *_: (self._skrij_splet_na_namizju(), True)[1])
            self._plosca_spleta = okno

    def _spremljaj_zaklep(self) -> None:
        """Ob zaklepu zaslona (Cinnamon) Splet sprosti pomnilnik; zavihki ostanejo."""
        try:
            vodilo = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            vodilo.signal_subscribe(None, "org.cinnamon.ScreenSaver", "ActiveChanged", "/org/cinnamon/ScreenSaver",
                                    None, Gio.DBusSignalFlags.NONE, self._ob_zaklepu, None)
        except Exception as e:  # noqa: BLE001 - brez seje D-Bus (preizkusi) ni zaklepa
            print("[SafeerOS] zaklep:", e)

    def _ob_zaklepu(self, _vodilo, _posiljatelj, _pot, _vmesnik, _signal, parametri, _podatki) -> None:
        try:
            zaklenjen = bool(parametri.unpack()[0])
        except Exception:  # noqa: BLE001
            return
        if not zaklenjen or self._spletni_namizje is None:
            return
        obnovljen = self._spletni_namizje.ob_zaklepu()
        pomnilnik.obrezuj()
        print("[SafeerOS] zaklep: Splet sprostil predpomnilnik" + (", omrezni proces obnovljen" if obnovljen else ""), flush=True)

    def _skrij_splet_na_namizju(self) -> bool:
        if self._plosca_spleta is None or not self._plosca_spleta.get_visible():
            return False
        self._plosca_spleta.set_visible(False)
        if self._spletni_namizje is not None:
            self._spletni_namizje.zapri_dialoge()      # dialog ne ostane sam nad skritim Spletom
        self._dogodek("spletNaNamizjuZaprt", None, self.pogled_delovna)
        # Takoj: predpomnilnik v pomnilniku spletnih procesov (zavihki ostanejo) in prazne strani Pythona sistemu.
        if self._spletni_namizje is not None:
            self._spletni_namizje.sprazni_predpomnilnik()
        GLib.timeout_add_seconds(2, lambda: (pomnilnik.obrezuj(), False)[1])
        # Skrit Splet drzi spletni proces (~250 MiB): po minuti ga zapremo; naslednje iskanje ga odpre na novo.
        if getattr(self, "_sprosti_splet_id", 0):
            GLib.source_remove(self._sprosti_splet_id)
        self._sprosti_splet_id = GLib.timeout_add_seconds(60, self._sprosti_splet_na_namizju)
        if not _ima_delovno(self) and self.okno is None and not any(o.get_visible() for o in self.get_windows()):
            # Samostojni Safeer Player je ze zaprt (_zapri_predvajalnik), Splet je bil zadnje okno: kot zaprtje
            # zadnjega okna - skrito okno sicer drzi proces brez vsega vidnega.
            GLib.idle_add(lambda: (self._koncaj(), False)[1])
        return True

    def _sprosti_splet_na_namizju(self) -> bool:
        self._sprosti_splet_id = 0
        okno = self._plosca_spleta
        if okno is None or okno.get_visible() or self._spletni_namizje is None:
            return False
        # Okno in Splet ostaneta (en kontekst, en omrezni proces); zaprejo se samo zavihki s spletnim procesom.
        self._spletni_namizje.sprosti_zavihke()
        pomnilnik.obrezuj()
        return False

    def _splet_namizja_v_brskalnik(self) -> None:
        """»Odpri v brskalniku«: trenutna stran gre v privzeti brskalnik, plosca se zapre."""
        try:
            naslov = self._spletni_namizje.trenutni().get_uri() or ""
        except Exception:  # noqa: BLE001
            naslov = ""
        if naslov.startswith(("http://", "https://")) and self._odpri_v_brskalniku(naslov):
            self._skrij_splet_na_namizju()

    def _dvojni_esc_splet(self, _okno, dogodek) -> bool:
        """Esc najprej dobi stran (izhod iz celozaslonskega videa, zapiranje okenca na strani); Esc, ki ga stran ne
        porabi, pride do bliznjice okna (Gtk.ShortcutController v _splet_na_namizju) in sele ta skrije okno Splet.
        Ta funkcija tece PRED stranjo (faza zajema) in ujame samo dvojni Esc."""
        if Gdk.keyval_name(dogodek.keyval) != "Escape":
            return False
        # Dvojni Esc (v 0,6 s) Splet vedno zapre: strani, kot je Google, prvi Esc porabijo zase in brez tega
        # uporabnik Spleta s tipkovnico ne bi mogel zapreti (stresni preizkus 12. 10. 2026).
        cas = int(getattr(dogodek, "time", 0) or 0)
        prejsnji, self._zadnji_esc_splet = getattr(self, "_zadnji_esc_splet", None), cas
        if dvojni_esc(prejsnji, cas):
            self._zadnji_esc_splet = None
            return self._skrij_splet_na_namizju()
        return False

    def _odpri_v_brskalniku(self, niz: str) -> bool:
        """Spletni zadetek iskanja v PRIVZETEM brskalniku (xdg): naslov http(s) ali iskanje z nastavljenim
        iskalnikom brskalnika Safeer."""
        niz = str(niz or "").strip()
        if not niz:
            return False
        url = niz if niz.startswith(("http://", "https://")) else \
            _iskalnik() + GLib.uri_escape_string(niz, None, False)
        from core import varuh_procesov
        for ukaz in (["gio", "open", url], ["xdg-open", url]):
            if shutil.which(ukaz[0]) is not None:
                try:
                    pid = varuh_procesov.zazeni_program(ukaz, zasebni_webkit.okolje_za_zunanje())
                    if pid:
                        return True
                except Exception:
                    pass
        try:
            return bool(Gio.AppInfo.launch_default_for_uri(url, zasebni_webkit.kontekst_za_zunanje(Gio)))
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] brskalnik:", e)
            return False

    def _zaslon(self):
        """Zaslon (Gdk.Monitor) Safeer OS: tisti, na katerem je namizje ali glavno okno; sicer prvi (GTK4 nima vec
        »glavnega« zaslona - na X11 GDK primarni izhod RandR da na prvo mesto)."""
        try:
            d = Gdk.Display.get_default()
            for okno in (self.okno_delovna, self.okno):
                povrsina = okno.get_surface() if okno is not None and okno.get_realized() else None
                if povrsina is not None:
                    m = d.get_monitor_at_surface(povrsina)
                    if m is not None:
                        return m
            zasloni = d.get_monitors()
            return zasloni.get_item(0) if zasloni.get_n_items() else None
        except Exception:
            return None

    def _zaslon_za_okno(self):
        """Zaslon za NOVO okno (razdelki, Safeer Player, dialogi): na X11 monitor s kazalcem miske - tam uporabnik
        dela (vec monitorjev; prej vedno prvi monitor). Brez tega (Wayland: okno postavi sestavljalnik, GNOME na
        monitor s fokusom) kot _zaslon(). Namizje in vrstica ostaneta na _zaslon() (primarni)."""
        try:
            m = _monitor_v_tocki(Gdk.Display.get_default().get_monitors(), x11.povezava())
        except Exception:  # noqa: BLE001
            m = None
        return m if m is not None else self._zaslon()

    @staticmethod
    def _delovno_obmocje(zaslon):
        """Del zaslona brez pulta in docka (GTK3 Gdk.Monitor.get_workarea; v GTK4 samo GdkX11.X11Monitor)."""
        try:
            return zaslon.get_workarea()
        except AttributeError:
            return zaslon.get_geometry()

    @staticmethod
    def _ob_spremembi_zaslonov(ob_spremembi) -> None:
        """GTK4 nima Gdk.Screen (monitors-changed, size-changed): seznam zaslonov (items-changed) in geometrija
        vsakega zaslona (notify::geometry)."""
        try:
            zasloni = Gdk.Display.get_default().get_monitors()

            def povezi(od: int, koliko: int) -> None:
                for i in range(od, od + koliko):
                    m = zasloni.get_item(i)
                    if m is not None:
                        m.connect("notify::geometry", lambda *_a: ob_spremembi())

            povezi(0, zasloni.get_n_items())
            zasloni.connect("items-changed", lambda _s, polozaj, _odstranjeni, dodani:
                            (povezi(polozaj, dodani), ob_spremembi()))
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] spremljanja zaslonov ni:", e)

    def _na_sredino(self, okno, sirina: int, visina: int) -> None:
        """GTK3 set_position(CENTER): GTK4 tega nima, okno postavimo na sredino delovnega obmocja sami."""
        zaslon = self._zaslon_za_okno()
        g = self._delovno_obmocje(zaslon) if zaslon else None
        if g is not None:
            x11.premakni(okno, g.x + max(0, (g.width - sirina) // 2), g.y + max(0, (g.height - visina) // 2))

    def _ustvari_okno(self) -> None:
        pogled = self._nov_pogled("index.html" + ("?namizje=1" if self.namizje else ""))
        okno = Gtk.ApplicationWindow(application=self, title="Safeer OS")
        _razred_okna(okno)
        zaslon = self._zaslon()
        if self.posnetek and _velikost_okna(os.environ.get("SAFEER_OS_OKNO", "")):
            sirina, visina = _velikost_okna(os.environ["SAFEER_OS_OKNO"])
            okno.set_default_size(sirina, visina)
        elif self.posnetek:
            okno.set_decorated(False)
            okno.fullscreen()
        elif not self.namizje:
            g = self._delovno_obmocje(zaslon) if zaslon else None
            sirina, visina = (min(1440, int(g.width * 0.9)) if g else 1280, min(900, int(g.height * 0.9)) if g else 800)
            okno.set_default_size(sirina, visina)
            self._na_sredino(okno, sirina, visina)
        else:
            # Namizje: okno je ozadje - vedno pod programi, ni ga v preklopniku oken in ga »Pokaži
            # namizje« ne pomanjsa. Spodaj pusti prostor za Safeerjevo vrstico.
            g = zaslon.get_geometry() if zaslon else None
            x11.nastavi_vrsto(okno, "DESKTOP")
            okno.set_decorated(False)
            x11.nastavi_preskoci(okno)
            if g is not None:
                x11.premakni(okno, g.x, g.y)
                okno.set_default_size(g.width, g.height - VISINA_VRSTICE)
                okno.set_size_request(g.width, g.height - VISINA_VRSTICE)
        postavitev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        postavitev.append(self._prekrivanje_kanalov(pogled))
        okno.set_child(postavitev)
        # F11 v fazi zajema: deluje tudi, ko ima fokus stran (kot GTK3 key-press-event okna).
        _tipke(okno, self._na_tipko, zajem=True)
        okno.connect("notify::is-active", lambda o, *a: o.is_active() and self._dogodek("fokus", None))
        if self.delovna:
            # Ob delovni povrsini zapiranje glavnega okna samo skrije okno: Scit, predvajanje, prenosi in
            # prijave v Spletu tecejo naprej; »Safeer OS« v meniju ga spet pokaze (do_activate -> _domov).
            okno.connect("close-request", lambda o, *_: (o.set_visible(False), True)[1])
        # GTK4: »destroy« pride sele, ko okna nihce vec ne drzi (self.okno ga drzi), zato pospravimo ob zapiranju.
        okno.connect("close-request", lambda *a: (self._koncaj(), False)[1])
        self.okno, self.pogled, self._glavna_postavitev = okno, pogled, postavitev
        okno.present()
        if self.posnetek:
            # V nekaterih WebKit2GTK/Mesa kombinacijah FINISHED za krajevni file:// pogled ne
            # pride. Preverjanje mora kljub temu narediti posnetek in se koncati, ne viseti.
            GLib.timeout_add(8000 + int(os.environ.get("SAFEER_OS_POSNETEK_ZAMIK", "0") or 0), self._rezervni_posnetek)
        GLib.timeout_add_seconds(10, self._periodicno)

    def _ustvari_vrstico(self) -> None:
        """Safeerjeva vrstica spodaj (namesto Mintovega pulta): Domov, odprti programi, stanje, ura.
        Okno vrste DOCK z rezervacijo prostora (_NET_WM_STRUT), da programi z najvecjim oknom ostanejo nad njo."""
        zaslon = self._zaslon()
        g = zaslon.get_geometry() if zaslon else None
        vrstica = Gtk.Window(title="Safeer OS vrstica")
        x11.nastavi_razred(vrstica, "safeer-os-vrstica", "Safeer OS")
        x11.nastavi_vrsto(vrstica, "DOCK")
        vrstica.set_decorated(False)
        x11.nastavi_preskoci(vrstica)
        x11.nastavi_stanje(vrstica, "STICKY", "ABOVE")
        if g is not None:
            x11.premakni(vrstica, g.x, g.y + g.height - VISINA_VRSTICE)
            vrstica.set_size_request(g.width, VISINA_VRSTICE)
        vrstica.set_child(self._nov_pogled("vrstica.html"))
        vrstica.connect("realize", lambda w: GLib.timeout_add(200, lambda: (self._rezerviraj(w, g), False)[1]))
        self.add_window(vrstica)
        vrstica.set_visible(True)
        self.vrstica = vrstica
        self._spremljaj_okna()
        self._spremljaj_zaslone()

    def _spremljaj_zaslone(self) -> None:
        """Zaslon se med delom lahko zamenja: zaprt pokrov, priklopljen televizor, druga
        locljivost. Vrstica in namizje morata za njim - sicer ostaneta v velikosti zaslona,
        ki ga ni vec (20. 9. 2026: pokrov zaprt, slika sla na televizor 3840x2160, vrstica
        pa je ostala siroka 1920 in na starem mestu)."""
        self._ob_spremembi_zaslonov(self._zaslon_spremenjen)

    def _zaslon_spremenjen(self) -> None:
        # Menjava zaslona sprozi vec dogodkov zapored (ugasne se en izhod, prizge drug):
        # pocakamo pol sekunde, da se umirijo, in se prilagodimo enkrat.
        if self._zaslon_zamik:
            try:
                GLib.source_remove(self._zaslon_zamik)
            except Exception:  # noqa: BLE001
                pass
        self._zaslon_zamik = GLib.timeout_add(500, self._prilagodi_zaslonu)

    def _prilagodi_zaslonu(self) -> bool:
        """Vrstico in namizje postavi na trenutni zaslon in v njegovo velikost."""
        self._zaslon_zamik = 0
        zaslon = self._zaslon()
        g = zaslon.get_geometry() if zaslon else None
        if g is None:
            return False
        if self.vrstica is not None:
            x11.premakni(self.vrstica, g.x, g.y + g.height - VISINA_VRSTICE)
            self.vrstica.set_size_request(g.width, VISINA_VRSTICE)
            self.vrstica.set_default_size(g.width, VISINA_VRSTICE)
            # Rezervacija spodnjega roba je vezana na velikost zaslona, zato gre znova tudi ta.
            self._rezerviraj(self.vrstica, g)
        if self.namizje and self.okno is not None:
            x11.premakni(self.okno, g.x, g.y)
            self.okno.set_size_request(g.width, g.height - VISINA_VRSTICE)
            self.okno.set_default_size(g.width, g.height - VISINA_VRSTICE)
        print("[SafeerOS] zaslon %dx%d: vrstica in namizje prilagojena" % (g.width, g.height))
        return False

    def _rezerviraj(self, vrstica, g) -> None:
        """Rezervira spodnji rob zaslona za vrstico (_NET_WM_STRUT_PARTIAL prek core/x11.py; GTK tega sam ne zna,
        prej xprop)."""
        try:
            if g is None:
                return
            m = vrstica.get_scale_factor() or 1
            zaslon_h = x11.visina_korena()            # visina korenskega okna X je ze v fizicnih pikah
            if not zaslon_h:
                return
            spodaj = (zaslon_h - (g.y + g.height) * m) + VISINA_VRSTICE * m
            x0, x1 = g.x * m, (g.x + g.width) * m - 1
            if not x11.rezerviraj(vrstica, dno=spodaj, dno_od=x0, dno_do=x1):
                print("[SafeerOS] rezervacija vrstice: ni X11")
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] rezervacija vrstice:", e)

    def _spremljaj_okna(self) -> None:
        """Vrstica in Domov vidita odprte programe sproti (odprtje, zaprtje, aktivno okno)."""
        def sprememba():
            # Dogodki pridejo v rafalih (odpiranje okna sprozi vec signalov): zberemo jih v cetrt sekunde.
            if self._okna_zamik:
                return
            def poslji():
                self._okna_zamik = 0
                self._dogodek("okna", self._odprta_okna())
                return False
            self._okna_zamik = GLib.timeout_add(250, poslji)
        os_okna.spremljaj(sprememba)

    def _domov(self, razdelek: str = "") -> bool:
        """Gumb Domov v vrstici (ali ponoven zagon Safeer OS iz menija): programe pomanjsamo, pred nami je
        Safeer OS."""
        if self.namizje:
            os_okna.pomanjsaj_vse(self._nasi_xid(), _cas_dogodka(self.okno))
        if self.okno is not None:
            self.okno.unminimize()
            self.okno.present()
        self._dogodek("fokus", None)
        if razdelek:
            self._dogodek("pojdi", razdelek)
        return True

    def _koncaj(self) -> None:
        """Konec Safeer OS (izhod, odjava, »Nazaj v Linux Mint«): Mintov pult se vrne."""
        if self._koncano:
            return
        if varuh_procesov.pod_varuhom() and not self._ponovni_zagon:
            self._posnemi_stanje()        # varuh (meja pomnilnika) zazene Safeer OS znova s tem stanjem
        self._koncano = True
        try:
            self._budnost.sprosti_vse()
        except Exception:  # noqa: BLE001
            pass
        self._pocisti_medijski_pogled()
        self._ustavi_neposredni_medij()
        if self._medijski_predvajalnik is not None:
            self._medijski_predvajalnik.zapri()
        if self._katalog is not None:
            self._katalog.zapri()
        if self.namizje:
            vrni_mintov_pult(self.shramba)
        try:
            os_torrent.torrenti().ustavi()        # rqbit ne ostane teči brez Safeer OS
        except Exception:
            pass
        # Brez nasega razresevalnika bi racunalnik ostal brez DNS: nastavitev povrnemo.
        try:
            self.scit.koncaj()
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] scit:", e)
        try:
            self.sporocila.zapri()
        except Exception:
            pass
        try:
            if getattr(self, "_kanali_sporocil", None) is not None:
                self._kanali_sporocil.koncaj()   # okna vgrajenih programov nazaj na namizje (programi tecejo naprej)
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] kanali Sporocil ob izhodu:", e)
        try:
            # »Izbrisi ob izhodu« in Safeer DRM za oba Spleta (okno in namizje), s cakanjem na WebKit (najvec 5 s).
            if self._spletni is not None or self._spletni_namizje is not None:
                from core.os_splet import pocisti_vse_ob_izhodu
                pocisti_vse_ob_izhodu([self._spletni, self._spletni_namizje], GLib)
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] Splet ob izhodu:", e)
        try:
            if self._spletni is not None:
                self._spletni.koncaj()
        except Exception:
            pass
        self.quit()

    def _na_vlecene_podatke(self, pogled, kontekst) -> None:
        """Datoteke, ki jih uporabnik vlece v okno iz drugega programa (Nemo, namizje). WebKitGTK strani njihovih poti
        ne pove, GTK pa jih pove nam: ob vstopu vlecenja (Gtk.DropControllerMotion) preberemo seznam datotek iz
        Gdk.Drop. Zapomnimo si jih; stran izve samo, koliko jih je (dogodek vleceneDatoteke), in jih ob spustu prevzame
        z metodo spusceneDatoteke. Novo vlecenje (drug Gdk.Drop) prejsnje pozabi - tudi ce ne prinasa datotek."""
        def javi() -> None:
            self._js("window.safeerOsDogodek && window.safeerOsDogodek(\"vleceneDatoteke\", %s);"
                     % json.dumps({"stevilo": len(self._vlecene_poti)}), pogled)

        def prebrano(spust, poti) -> None:
            # Tudi vlecenje iz programov v drugem procesu (XWayland, Electron) in iz portala dokumentov (Flatpak).
            if poti and spust is self._vleceno_kontekst:
                self._vlecene_poti = poti
            javi()

        try:
            if kontekst is None:
                return
            if kontekst is not self._vleceno_kontekst:
                self._vleceno_kontekst, self._vlecene_poti = kontekst, []
            os_datoteke.preberi_vlecene(kontekst, prebrano)
        except Exception:
            pass

    @staticmethod
    def _vlecenje_na_voljo() -> bool:
        """Vlecenje iz okna lahko sami zacnemo v X11. V Waylandu je za zacetek potreben dogodek miske, ki ga ima
        WebKit, ne mi - tam ostane vlecenje znotraj strani."""
        if os.environ.get("SAFEER_OS_BREZ_VLECENJA"):
            return False
        zaslon = Gdk.Display.get_default()
        return zaslon is not None and not str(zaslon.get_name() or "").startswith("wayland")

    def _zacni_vlecenje(self, pogled, poti) -> bool:
        """Vlecenje datotek iz Datotek kot pravo vlecenje namizja. Vlecenje, ki ga zacne spletna stran, drugim
        programom ne pove pravega: WebKitGTK ob seznamu naslovov vedno ponudi se _NETSCAPE_URL, Nemo pa ta cilj
        postavi pred text/uri-list in iz njega naredi bliznjico (.desktop) namesto kopije. Tu ponudimo samo
        standardni seznam naslovov datotek: Nemo datoteke kopira (s Shift premakne), sprejmejo jih tudi brskalnik,
        posta in terminal. Kopiranje ali premik opravi ciljni program; mi ne brisemo nicesar."""
        naslovi = os_datoteke.naslovi_iz_poti(poti if isinstance(poti, list) else [])
        okno = pogled.get_root() if pogled is not None else None
        if not naslovi or not isinstance(okno, Gtk.Window) or not self._vlecenje_na_voljo():
            return False
        povrsina = okno.get_surface()
        if povrsina is None:
            return False
        self._lastno_vlecenje, self._lastno_ni_uspelo = naslovi, False
        try:
            # GTK4: Gdk.Drag.begin z vsebino text/uri-list (samo seznam naslovov, kot GTK3 add_uri_targets).
            kazalec = Gdk.Display.get_default().get_default_seat().get_pointer()
            vsebina = Gdk.ContentProvider.new_for_bytes(
                "text/uri-list", GLib.Bytes.new(("\r\n".join(naslovi) + "\r\n").encode("utf-8")))
            vlecenje = Gdk.Drag.begin(povrsina, kazalec, vsebina, Gdk.DragAction.COPY | Gdk.DragAction.MOVE, 0, 0)  # odmik od kazalca
        except Exception:
            vlecenje = None
        if vlecenje is None:
            self._lastno_vlecenje = []
            return False
        self._vlecenje_gdk = vlecenje          # referenca: vlecenje mora ziveti do konca
        vlecenje.connect("cancel", lambda v, _razlog: self._na_vlecenje_ni_uspelo(v, pogled))
        vlecenje.connect("dnd-finished", lambda v: self._na_vlecenje_konec(v, pogled))
        try:   # ikona ob kazalcu: vrsta prve datoteke
            prva = os_datoteke.poti_iz_naslovov(naslovi[:1])[0]
            vrsta = "inode/directory" if os.path.isdir(prva) else (Gio.content_type_guess(prva, None)[0] or "")
            slika = Gtk.Image.new_from_gicon(Gio.content_type_get_icon(vrsta) if vrsta
                                             else Gio.ThemedIcon.new("text-x-generic"))
            slika.set_pixel_size(32)
            Gtk.DragIcon.get_for_drag(vlecenje).set_child(slika)
        except Exception:
            pass
        return True

    def _na_vlecenje_ni_uspelo(self, vlecenje, pogled) -> None:
        """Gdk.Drag »cancel«: cilj vlecenja ni sprejel (GTK3 drag-failed); za njim ni vec »dnd-finished«."""
        self._lastno_ni_uspelo = True
        self._na_vlecenje_konec(vlecenje, pogled)

    def _na_vlecenje_konec(self, vlecenje, pogled) -> None:
        if vlecenje is not getattr(self, "_vlecenje_gdk", None):
            return
        self._vlecenje_gdk = None
        sprejeto = bool(self._lastno_vlecenje) and not self._lastno_ni_uspelo
        self._lastno_vlecenje = []
        self._js("window.safeerOsDogodek && window.safeerOsDogodek(\"vlecenjeKoncano\", %s);"
                 % json.dumps({"sprejeto": sprejeto}), pogled)

    def _spuscene_datoteke(self) -> list:
        """Poti datotek, spuscenih iz drugega programa (enkrat: po prevzemu jih pozabimo)."""
        poti, self._vlecene_poti = list(self._vlecene_poti), []
        return poti

    # ------------------------------------------------------------------ priponke in predogled (Sporocila)
    def _predogled(self):
        """Eno okno predogleda za ves Safeer OS (core/os_predogled.py), ustvarjeno ob prvi uporabi."""
        if getattr(self, "_okno_predogleda", None) is None:
            from core import os_predogled
            self._okno_predogleda = os_predogled.OknoPredogleda(
                Gtk, Gdk, GLib, WebKit2, _jezik,
                # Povezava iz PDF ali pisma: kot povezava v sporocilu (Splet v glavnem oknu, sicer privzeti brskalnik).
                odpri_povezavo=lambda u: self._splet(u, True) if self.okno is not None else self._odpri_v_brskalniku(u),
                odpri_v_programu=os_datoteke.odpri, pokazi_v_mapi=os_datoteke.pokazi_v_mapi)
        return self._okno_predogleda

    def _okno_pogleda(self, pogled):
        """Okno, nad katerim se odpre predogled ali izbira datotek: okno strani (WebKit), sicer glavno okno (lupina
        QML nima Gtk okna)."""
        koren = pogled.get_root() if pogled is not None and hasattr(pogled, "get_root") else None
        return koren if isinstance(koren, Gtk.Window) else (self.okno or getattr(self, "okno_delovna", None))

    def _napredek_priponke(self, kanal: str, sid: str, kljuc: str, delez: float) -> None:
        self._dogodek("priponkaNapredek", {"kanal": kanal, "sid": sid, "kljuc": kljuc, "delez": round(float(delez), 3)})

    def _prenesi_priponko(self, kanal: str, sid: str, kljuc: str) -> dict:
        izid = self.sporocila.priponka_prenesi(kanal, sid, kljuc,
                                               napredek=lambda d: self._napredek_priponke(kanal, sid, kljuc, d))
        os_iskalnik.zastarel()                          # nova datoteka v Prejemih: iskanje jo najde
        return izid

    def _predogled_priponke(self, pogled, kanal: str, sid: str, kljuc: str) -> bool:
        from core import predogled_datotek
        _a, _s, p = self.sporocila._najdi_priponko(kanal, sid, kljuc)
        ime, tip = str(p.get("ime") or ""), str(p.get("tip") or "")
        jezik = _jezik()
        vrsta = predogled_datotek.vrsta_predogleda(ime, tip)
        velikost = int(p.get("velikost") or 0)

        def prenesi() -> str:
            izid = self._prenesi_priponko(kanal, sid, kljuc)
            self._dogodek("priponkaShranjena", {"kanal": kanal, "sid": sid, "kljuc": kljuc, "pot": izid["pot"]})
            return izid["pot"]
        okno = self._predogled()
        rod = okno.odpri(ime, self._okno_pogleda(pogled),
                         _velikost_napis(velikost), prenesi, predogled_datotek.je_nevarna(ime, tip))

        def delo() -> None:
            try:
                if vrsta == "nevarno":
                    # Programa ali skripte ne prenesemo niti v predpomnilnik: samo opozorilo (prenos je v glavi okna).
                    izid, pot = predogled_datotek.pripravi("", ime, tip, jezik), ""
                else:
                    pot, _p = self.sporocila.priponka_v_predpomnilnik(
                        kanal, sid, kljuc, napredek=lambda d: self._napredek_priponke(kanal, sid, kljuc, d))
                    # PDF iz LibreOffice ostane ob priponki: drugo odprtje brez ponovne pretvorbe.
                    izid = predogled_datotek.pripravi(pot, ime, tip, jezik,
                                                      mapa_pretvorbe=self.sporocila.mapa_vnosa(kanal, sid, kljuc))
                GLib.idle_add(lambda: (okno.pokazi(rod, izid, pot), False)[1])
            except ValueError as e:
                koda = "ni_povezave" if "povezave" in str(e) else "napaka"
                GLib.idle_add(lambda: (okno.napaka(rod, predogled_datotek.besedilo(koda, jezik)), False)[1])
        threading.Thread(target=delo, name="safeer-predogled-priponke", daemon=True).start()
        return True

    def _predogled_pisma(self, pogled, kanal: str, sid: str, naslov: str = "") -> bool:
        """»Prikazi izvirnik«: HTML pisma kot v Gmailu (slike v vrstici iz pisma, oddaljene skrite, brez skript)."""
        from core import predogled_datotek
        from core.sporocila import predpomnilnik
        jezik = _jezik()
        okno = self._predogled()
        rod = okno.odpri(naslov or kanal, self._okno_pogleda(pogled))

        def je_blokirano(url: str) -> bool:
            # Oddaljene slike: isti seznami oglasov, sledilcev in groženj kot v Spletu - tudi pravila Scita (sledilci in
            # telemetrija; slika v pismu je vedno vir tretje strani).
            from core import adblock, scit_pravila
            return (adblock.is_ad_domain(url) or adblock.is_threat_domain(url)
                    or scit_pravila.trenutna().blokira(url))

        def delo(slike: bool = False) -> None:
            try:
                r = self.sporocila.html_pisma(kanal, sid, jezik, slike=slike, je_blokirano=je_blokirano,
                                              posrednik=_posrednik_slik, razresi=_razresevalnik_slik())
                izid = {"nacin": "html", "html": r["html"],
                        "osnova": GLib.filename_to_uri(predpomnilnik.koren(), None) + "/"}
                vrstica = None if r["prikazane"] else {"skritih": r["skritih"], "posiljatelj": r["posiljatelj"],
                                                       "prikazi": prikazi}
                GLib.idle_add(lambda: (okno.pokazi(rod, izid, "", vrstica), False)[1])
            except ValueError as e:
                koda = "ni_povezave" if "povezave" in str(e) else "napaka"
                GLib.idle_add(lambda: (okno.napaka(rod, predogled_datotek.besedilo(koda, jezik)), False)[1])
            except Exception as e:  # noqa: BLE001 - poln disk, slike, razclenjevanje: okno ne sme obviseti v nalaganju
                print("[SafeerOS] predogled pisma:", type(e).__name__, file=sys.stderr, flush=True)
                GLib.idle_add(lambda: (okno.napaka(rod, predogled_datotek.besedilo("napaka", jezik)), False)[1])

        def prikazi(vedno: bool) -> None:
            """»Prikazi slike« ali »Vedno prikazi od …« (ta izbira ostane po naslovu posiljatelja; preklic v podoknu)."""
            if vedno:
                try:
                    self.sporocila.nastavi_slike_od(self.sporocila.html_posiljatelj(kanal, sid), True)
                    self._dogodek("sporocilaSlikeOd", self.sporocila.slike_od.seznam())
                except ValueError:
                    pass
            threading.Thread(target=delo, args=(True,), name="safeer-predogled-slike", daemon=True).start()
        threading.Thread(target=delo, name="safeer-predogled-pisma", daemon=True).start()
        return True

    def _predogled_datoteke(self, pogled, pot: str) -> bool:
        """Predogled krajevne datoteke (za Datoteke in namizje QML - ista komponenta kot priponke)."""
        pot = os.path.realpath(os.path.expanduser(pot or ""))
        if not os.path.isfile(pot):
            return False
        self._predogled().odpri_datoteko(pot, self._okno_pogleda(pogled))
        return True

    def _na_politiko(self, pogled, odlocitev, vrsta) -> bool:
        """Pogled sme prikazati samo stran Safeer OS (most ne sme k tuji strani). Izjema: okvirji (iframe) odprtega
        lastnega vgrajenega vira - ti gredo skozi Scit (_vgrajeno_dovoli); glavni okvir tudi takrat ostane Safeer OS
        (odgovor tuje strani za glavni okvir zavrnemo, preden se karkoli izrise)."""
        try:
            if vrsta == WebKit2.PolicyDecisionType.RESPONSE:
                if odlocitev.is_main_frame_main_resource() and os_vgrajeni_viri.tuja_glavna_stran(
                        odlocitev.get_request().get_uri() or "", getattr(self, "_koren_strani", "")):
                    odlocitev.ignore()
                    return True
                return False
            if vrsta not in (WebKit2.PolicyDecisionType.NAVIGATION_ACTION,
                             WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION):
                return False
            naslov = odlocitev.get_navigation_action().get_request().get_uri() or ""
            if naslov.startswith(self._koren_strani + "/"):
                return False
            if vrsta == WebKit2.PolicyDecisionType.NAVIGATION_ACTION and self._vgrajeno_odprto(pogled):
                # Navigacije okvirja vgrajenega vira (WebKitGTK ne pove, ali gre za okvir - glavni okvir ustavi
                # odgovor zgoraj); Scit ustavi domene groženj in oglasov.
                if self._vgrajeno_dovoli(naslov):
                    odlocitev.use()
                else:
                    odlocitev.ignore()
                return True
            odlocitev.ignore()
            if naslov.startswith(("http://", "https://")) and not self._vgrajeno_scit_ustavi(naslov):
                self._splet(naslov)
            return True
        except Exception:
            odlocitev.ignore()
            return True

    # ------------------------------------------------------------------ lastni vgrajeni viri (iframe v Medijskem centru)
    def _vgrajeno_odprto(self, pogled) -> bool:
        return pogled is not None and pogled in getattr(self, "_vgrajeni_pogledi", ())

    def _vgrajeno_scit_ustavi(self, naslov: str) -> bool:
        """Scit za vgrajene vire: domene groženj in oglasov (isti seznami kot Splet) se ne nalozijo."""
        if not naslov.lower().startswith(("http://", "https://")):
            return False
        try:
            from core import adblock
            return adblock.is_threat_domain(naslov) or adblock.is_ad_domain(naslov)
        except Exception:  # noqa: BLE001 - seznama ni: ne ugibamo
            return False

    def _vgrajeno_dovoli(self, naslov: str) -> bool:
        return os_vgrajeni_viri.dovoli_okvir(naslov) and not self._vgrajeno_scit_ustavi(naslov)

    def _vgrajeno_aktivno(self, pogled, da: bool) -> bool:
        """Stran pove, da je odprla (ali zaprla) vgrajen vir. Sele tedaj pogled pusti okvirje http(s) in dobi filter
        EasyList (WebKit content blocker velja za vse okvirje strani, kot v Spletu); ob zaprtju filter odstranimo, da
        strani Safeer OS ne tecejo skozenj."""
        if not hasattr(self, "_vgrajeni_pogledi"):
            self._vgrajeni_pogledi = weakref.WeakSet()
        if da:
            self._vgrajeni_pogledi.add(pogled)
            self._vgrajeno_scit_pripravi()
            self._vgrajeno_filter()
            # Sledilci in telemetrija (core/scit_pravila.py) tudi v vgrajenih virih: en poslusalec za vse (nov seznam ->
            # vsi odprti viri), pogled pa filter dobi takoj.
            try:
                self._sledilci_v_pogled(pogled)
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] vgrajeni viri, sledilci:", e, flush=True)
        else:
            self._vgrajeni_pogledi.discard(pogled)
            try:
                from core.filter_lists import FILTER_ID
                from core.scit_pravila import FILTER_ID as SLEDILCI
                pogled.get_user_content_manager().remove_filter_by_id(FILTER_ID)
                pogled.get_user_content_manager().remove_filter_by_id(SLEDILCI)
            except Exception:  # noqa: BLE001
                pass
        return bool(da)

    def _sledilci_v_pogled(self, pogled) -> None:
        """Filter sledilcev (core/scit_pravila.FilterSledilcev) na pogled vgrajenega vira ali predvajalnika Medijskega
        centra. Poslusalec za nov seznam je en sam (brez kopicenja ob vsakem odprtju) in velja za trenutne poglede."""
        from core import scit_pravila
        sledilci = scit_pravila.filter_sledilcev(WebKit2, GLib)
        if sledilci is None:
            return
        if not getattr(self, "_sledilci_prijava", False):
            self._sledilci_prijava = True

            def nov(_f) -> None:
                medijski = getattr(self, "_medijski_pogled", None)
                for p in list(getattr(self, "_vgrajeni_pogledi", ())) + ([medijski] if medijski is not None else []):
                    sledilci.uporabi(p)
            sledilci.ob_novem(nov)
        sledilci.uporabi(pogled)

    def _vgrajeno_scit_pripravi(self) -> None:
        """Vir groženj (podpisan seznam Safeer, isti kot Splet in Scit) za preverjanje okvirjev - enkrat na proces."""
        if getattr(self, "_vgrajeno_scit", False):
            return
        self._vgrajeno_scit = True
        try:
            from core import adblock
            from core.threat_intel import default_data_dir, skupna
            adblock.register_threat_matcher(skupna(default_data_dir("safeer-mint")).match)
        except Exception as e:  # noqa: BLE001 - vgrajeni seznam domen ostane
            print("[SafeerOS] vgrajeni viri, vir groženj:", e, flush=True)

    def _vgrajeno_filter(self, pripravi: bool = True) -> None:
        """EasyList (preveden filter Spleta, ista shramba in id) na poglede z vgrajenim virom. Ce prevedenega se ni
        (Splet se ni tekel), ga enkrat pripravimo iz shranjenega seznama oziroma prenosa, kot Splet - razen ce
        pripravi=False (samo ze preveden filter, brez pretvorbe)."""
        from core.filter_lists import FILTER_ID, FilterListAgent
        from core.threat_intel import default_data_dir

        def uporabi(filter_) -> None:
            self._vgrajeni_filter = filter_
            medijski = getattr(self, "_medijski_pogled", None)
            for p in list(getattr(self, "_vgrajeni_pogledi", ())) + ([medijski] if medijski is not None else []):
                try:
                    upravitelj = p.get_user_content_manager()
                    upravitelj.remove_filter_by_id(FILTER_ID)
                    upravitelj.add_filter(filter_)
                except Exception as e:  # noqa: BLE001
                    print("[SafeerOS] vgrajeni viri, filter:", e, flush=True)
        if getattr(self, "_vgrajeni_filter", None) is not None:
            uporabi(self._vgrajeni_filter)
            return
        if getattr(self, "_vgrajeni_filter_nalagam", False):
            return
        self._vgrajeni_filter_nalagam = True
        mapa = default_data_dir("safeer-mint").parent / "filter-lists"
        try:
            (mapa / "compiled").mkdir(parents=True, exist_ok=True)
            shramba = WebKit2.UserContentFilterStore.new(str(mapa / "compiled"))
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] vgrajeni viri, shramba filtra:", e, flush=True)
            self._vgrajeni_filter_nalagam = False
            return

        def shranjen(st, rezultat, *_a) -> None:
            try:
                uporabi(st.save_finish(rezultat))
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] vgrajeni viri, prevajanje filtra:", e, flush=True)
            self._vgrajeni_filter_nalagam = False

        def pravila(json_pravila, _vir) -> None:
            agent = getattr(self, "_vgrajeni_agent", None)
            if agent is not None:
                agent.stop()                       # en seznam je dovolj; osvezevanje ostane Spletu
            GLib.idle_add(lambda: (shramba.save(FILTER_ID, GLib.Bytes.new(json_pravila.encode("utf-8")), None, shranjen),
                                   False)[1])

        def nalozen(st, rezultat, *_a) -> None:
            try:
                uporabi(st.load_finish(rezultat))
                self._vgrajeni_filter_nalagam = False
            except Exception:  # noqa: BLE001 - se ni preveden: iz shranjenega seznama ali prenosa
                if not pripravi:
                    self._vgrajeni_filter_nalagam = False
                    return
                try:
                    from core import adblock
                    self._vgrajeni_agent = FilterListAgent(mapa, on_rules=pravila, first_delay=0,
                                                           never_block_domains=adblock.real_bank_domains())
                    self._vgrajeni_agent.start()
                except Exception as e:  # noqa: BLE001
                    print("[SafeerOS] vgrajeni viri, EasyList:", e, flush=True)
                    self._vgrajeni_filter_nalagam = False
        shramba.load(FILTER_ID, None, nalozen)

    def _vgrajeno_novo_okno(self, pogled, dejanje):
        """window.open iz vgrajenega vira (peskovnik ga pusti samo z »Dovoli pojavna okna«): okno se odpre v Spletu,
        kjer veljajo Scit in pravila pojavnih oken; v Medijskem centru novega pogleda z mostom ne naredimo."""
        try:
            naslov = dejanje.get_request().get_uri() or ""
        except Exception:  # noqa: BLE001
            naslov = ""
        if (self._vgrajeno_odprto(pogled) and naslov.lower().startswith(("http://", "https://"))
                and not self._vgrajeno_scit_ustavi(naslov)):
            GLib.idle_add(lambda: (self._splet(naslov), False)[1])
        return None

    def _vgrajeno_tipka(self, pogled, dogodek) -> bool:
        """F11 in Escape v oknu z odprtim vgrajenim virom: tipko dobi okno pred okvirjem (fokus je pogosto v tuji strani,
        ki je stran Safeer OS ne slisi). F11 = nacin za kavc (cel zaslon), Escape = nazaj iz vira; cel zaslon elementa
        (video v okvirju) Escape zapusti WebKit sam."""
        if not self._vgrajeno_odprto(pogled):
            return False
        ime = Gdk.keyval_name(dogodek.keyval) or ""
        if ime == "F11":
            self._js("window.SafeerKavc && window.SafeerKavc.nastavi(!window.SafeerKavc.vklopljen());", pogled)
            return True
        if ime == "Escape" and pogled not in self._vgrajeni_cel_zaslon:
            self._js("window.SafeerVgrajeno && window.SafeerVgrajeno.zapriVse();", pogled)
            return True
        return False

    def _na_tipko(self, okno, dogodek) -> bool:
        # Vgrajeni spletni predvajalnik nad Medijskim centrom: Escape (cel zaslon / nazaj) in F11 sta njegova.
        if self._plast_tipka(okno, dogodek):
            return True
        # F11: namizni nacin / okno (obicajna bliznjica, deluje tudi, ko se kaj zatakne).
        if dogodek.keyval == Gdk.KEY_F11 and not self.posnetek:
            self._celozaslonsko(not self.namizje)
            return True
        # Escape iz vgrajenega vira v glavnem oknu (fokus je v tuji strani v okvirju).
        if dogodek.keyval == Gdk.KEY_Escape and self._vgrajeno_odprto(getattr(self, "pogled", None)):
            return self._vgrajeno_tipka(self.pogled, dogodek)
        return False

    def _celozaslonsko(self, vklop: bool) -> bool:
        """Namizni nacin vklopi/izklopi; Safeer OS se zazene znova v izbranem nacinu."""
        self.shramba.set("celozaslonsko", bool(vklop))
        if bool(vklop) == self.namizje or self.v_oknu:
            return vklop

        def znova():
            if self.namizje:
                vrni_mintov_pult(self.shramba)
            py = okolje_procesa.python_ukaz()
            os.execv(py[0], py + [os.path.abspath(__file__)])
        GLib.timeout_add(200, lambda: (znova(), False)[1])
        return vklop

    def _periodicno(self) -> bool:
        if self.okno is None:
            return False
        if self.okno.is_active() or (self.vrstica is not None):
            threading.Thread(target=lambda: self._dogodek("stanje", os_sistem.stanje()), daemon=True).start()
        return True

    # ------------------------------------------------------------------ posodobitve (safeer.si/os/razlicice.json)
    def _posodobitve_razlicice(self) -> dict:
        # Od 12. 10. 2026 je Safeer Control (in Safeer Cinnamon) v paketu safeer-os: ena razlicica, ena posodobitev.
        return {"safeer-os": RAZLICICA}

    def _posodobitve_stanje(self, vsiljeno: bool = False) -> dict:
        """Stanje za vmesnik (v niti): izid zadnje preverbe (najvec 6 ur stare, ali sveze ob [vsiljeno]) + tekoce posodabljanje."""
        s = self.posodobitve
        kanal = os_posodobitve.izbrani_kanal()
        # Drug kanal kot ob zadnji preverbi (stikalo Beta kanal): izid ne velja vec, preverimo takoj, ne sele cez 6 ur.
        if s["izid"] is not None and s["izid"].get("kanal", kanal) != kanal:
            s["izid"] = None
        if vsiljeno or s["izid"] is None or time.time() - s["cas"] > os_posodobitve.PREVERBA_S:
            try:
                s["izid"] = os_posodobitve.preveri("linux", self._posodobitve_razlicice(), kanal=kanal)
                s["cas"], s["napaka"] = time.time(), ""
            except Exception as e:  # noqa: BLE001 - brez omrezja: ostane prejsnji izid
                s["napaka"] = str(e)
                if s["izid"] is None:
                    s["cas"] = time.time() - os_posodobitve.PREVERBA_S + 600   # cez 10 minut znova
        izid = s["izid"] or {"nove": [], "nacin": os_posodobitve.nacin_namestitve(), "stran": os_posodobitve.STRAN}
        return {"nove": izid.get("nove") or [], "opis": os_posodobitve.opis(izid), "nacin": izid.get("nacin"), "novo": izid.get("novo") or {},
                "stran": izid.get("stran"), "nasa": RAZLICICA, "napaka": s["napaka"], "posodabljanje": self.posodabljanje.stanje(),
                "flatpak_preklop": self._flatpak_ponudba(izid), "kanal": kanal,
                "na_beti": os_posodobitve.je_predizdaja(RAZLICICA)}

    def _posodobitve_kanal(self, novi: str) -> dict:
        """Stikalo »Beta kanal« (Nastavitve -> Posodobitve): shrani kanal; vmesnik nato preveri na novo. Nicesar ne
        namesti - tudi izklop bete ne zamenja razlicice navzdol (os_posodobitve.preveri ponudi samo novejse)."""
        try:
            kanal = os_posodobitve.nastavi_kanal(novi)
        except ValueError:
            return {"ok": False, "koda": "neznan_kanal", "kanal": os_posodobitve.izbrani_kanal()}
        self.posodobitve["izid"] = None
        return {"ok": True, "kanal": kanal}

    def _flatpak_ponudba(self, izid: dict):
        """Ponudba »hitrejsi Splet« (lastnik, 12. 10. 2026: Flatpak je glavna pot): samo .deb brez Flatpaka."""
        p = (izid or {}).get("flatpak_preklop")
        if not p:
            return None
        if self.posodobitve.get("flatpak_namescen") is None:
            self.posodobitve["flatpak_namescen"] = os_posodobitve.flatpak_namescen()
        return None if self.posodobitve["flatpak_namescen"] else {"razlicica": p.get("razlicica")}

    def _flatpak_preklop(self) -> dict:
        """Prenese Flatpak Safeer OS (SHA-256 iz manifesta), ga namesti za uporabnika in Safeer OS znova zazene -
        zaganjalnik .deb ga nato preda Flatpaku (WebKit iz runtime GNOME). Brez gesla."""
        st = self._posodobitve_stanje()
        izid = self.posodobitve.get("izid") or {}
        p = izid.get("flatpak_preklop")
        if not p or not st.get("flatpak_preklop"):
            return {"ok": False, "koda": "ni_na_voljo"}
        d = p["datoteka"]

        def delo(stanje: os_posodobitve.Posodabljanje) -> None:
            mapa = os.path.join(GLib.get_user_cache_dir(), "safeer-os", "posodobitve")
            ime = str(d["url"]).rsplit("/", 1)[-1]
            stanje.sporocilo = ime
            pot = os_posodobitve.prenesi(str(d["url"]), os.path.join(mapa, ime), str(d.get("sha256") or ""),
                                         int(d.get("velikost") or 0),
                                         lambda a, b: setattr(stanje, "odstotek", int(a * 100 / b) if b else 0),
                                         lambda: stanje.prekinjeno, agent="SafeerOS/" + RAZLICICA)
            stanje.faza, stanje.odstotek = "namescanje", 100
            r = os_posodobitve.namesti_flatpak(pot)
            if r.returncode != 0:
                stanje.faza, stanje.sporocilo = "napaka", (r.stderr or r.stdout or "").strip()[-300:] or "namestitev ni uspela"
                return
            try:
                os.remove(pot)
            except OSError:
                pass
            self.posodobitve["flatpak_namescen"] = True
            stanje.sporocilo = "Flatpak"
            # Znova zazenemo prek zaganjalnika .deb (preda Flatpaku); najprej koncamo ta proces (en primerek).
            argumenti = ["--delovna"] if self.delovna else []
            # Lupina je tu namerna: nov proces mora zaceti sele, ko se ta konca (en primerek), casovnik GLib pa bi
            # umrl s tem procesom. Besedilo ukaza je stalno, argumenti gredo kot "$@" (neodvisni pregled 19. 10. 2026).
            subprocess.Popen(["sh", "-c", 'sleep 3; exec /usr/bin/safeer-os "$@"', "safeer-os"] + argumenti,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            GLib.timeout_add_seconds(1, lambda: (self._koncaj(), False)[1])
        return {"ok": self.posodabljanje.zacni(delo)}

    def _posodobitve_tiho(self) -> bool:
        """Tiha preverba ob zagonu in nato na 6 ur; novo razlicico sporoci vmesniku (opomba na domacem zaslonu)."""
        def delo() -> None:
            st = self._posodobitve_stanje()
            if st["nove"]:
                self._dogodek("posodobitev", st)
        threading.Thread(target=delo, name="safeer-posodobitve", daemon=True).start()
        GLib.timeout_add_seconds(os_posodobitve.PREVERBA_S, self._posodobitve_tiho)
        return False

    def _posodobi(self) -> dict:
        """Prenese nove pakete (SHA-256) in jih namesti: deb prek pkexec apt-get (geslo), flatpak brez gesla, AppImage se zamenja."""
        st = self._posodobitve_stanje()
        nove = [n for n in st["nove"] if n.get("datoteka")]
        if not nove:
            # Nova razlicica brez paketa za ta nacin (AppImage od 1.0.132): stran s prenosi, ne »ni novih« v zanki.
            return ({"ok": False, "koda": "rocno", "stran": st["stran"]} if st["nove"] else {"ok": False, "koda": "ni_novih"})
        nacin = st["nacin"]
        if nacin not in ("deb", "flatpak", "flatpak+deb", "appimage"):
            return {"ok": False, "koda": "rocno", "stran": st["stran"]}

        def delo(p: os_posodobitve.Posodabljanje) -> None:
            mapa = os.path.join(GLib.get_user_cache_dir(), "safeer-os", "posodobitve")
            datoteke, vsote = [], []       # vsote iz podpisanega seznama: root jih preveri na svoji kopiji
            for n in nove:
                for d in os_posodobitve.datoteke_namestitve(n):
                    vsote.append(str(d.get("sha256") or ""))
                    ime = str(d["url"]).rsplit("/", 1)[-1]
                    p.sporocilo = ime
                    datoteke.append(os_posodobitve.prenesi(str(d["url"]), os.path.join(mapa, ime), str(d.get("sha256") or ""),
                                                           int(d.get("velikost") or 0),
                                                           lambda a, b: setattr(p, "odstotek", int(a * 100 / b) if b else 0),
                                                           lambda: p.prekinjeno, agent="SafeerOS/" + RAZLICICA))
            p.faza, p.odstotek = "namescanje", 100
            r = os_posodobitve.namesti_linux(nacin, datoteke, vsote)
            if r.returncode != 0:
                p.faza, p.sporocilo = "napaka", (r.stderr or r.stdout or "").strip()[-300:] or "namestitev ni uspela"
                return
            self._posodobil_sam = True      # uporabnik je posodobitev zahteval: nova razlicica takoj, ko nic ne tece
            for d in datoteke:
                if nacin != "appimage":
                    try:
                        os.remove(d)
                    except OSError:
                        pass
            self.posodobitve["izid"] = None   # naslednja preverba pove, da smo na najnovejsi
            p.sporocilo = os_posodobitve.opis(st)
        return {"ok": self.posodabljanje.zacni(delo)}

    # ------------------------------------------------------------------ nova razlicica po namestitvi
    # Lastnik 18. 10. 2026: po `apt install` je stari Safeer OS tekel se dneve. core/nova_razlicica.py: spremljanje
    # packaging/VERSION_OS, cakanje na trenutek, ko nic ne tece, shranjeno stanje in zagon nove razlicice.
    def _spremljaj_novo_razlicico(self) -> None:
        if self._nova_spremljevalec is not None or not nova_razlicica.velja(KOREN):
            return
        try:
            self._nova_spremljevalec = nova_razlicica.Spremljevalec(
                Gio, GLib, os.path.join(KOREN, "packaging", "VERSION_OS"), RAZLICICA, self._ob_novi_razlicici)
        except Exception as e:  # noqa: BLE001 - brez spremljanja pride nova razlicica ob naslednjem zagonu
            print("[SafeerOS] nova razlicica, spremljanje:", e, flush=True)
        # Skupni WebKit (paket safeer-webkit, od 19. 10. 2026) lahko posodobi tudi Safeer Browser: Splet bi s staro
        # knjiznico v pomnilniku zaganjal spletne procese nove gradnje. Nov odtis gradnje -> ista pot kot nova razlicica
        # (razlicica iz namescene datoteke: ce se je posodobil tudi Safeer OS, je to nova, sicer ta).
        odtis = zasebni_webkit.pot_odtisa()
        if odtis:
            try:
                self._nova_spremljevalec_webkit = nova_razlicica.Spremljevalec(
                    Gio, GLib, odtis, nova_razlicica.beri(odtis), lambda _odtis: self._ob_novi_razlicici(
                        nova_razlicica.beri(os.path.join(KOREN, "packaging", "VERSION_OS")) or RAZLICICA))
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] nova gradnja WebKita, spremljanje:", e, flush=True)

    def _ob_novi_razlicici(self, nova: str) -> None:
        print("[SafeerOS] namescena je nova razlicica %s (tece %s)" % (nova, RAZLICICA), flush=True)
        self._nova_razlicica = nova
        if self._nova_cakanje is not None or self._koncano:
            return
        self._nova_cakanje = nova_razlicica.Cakanje(
            GLib, self._zaposleno, lambda: nova_razlicica.nedejavnost_s(Gio, GLib),
            lambda: nova_razlicica.zaslon_zaklenjen(Gio, GLib), self._znova_v_novo,
            takoj=lambda: self._posodobil_sam, ob_cakanju=self._obvesti_novo_razlicico)
        self._nova_cakanje.zacni()

    def _obvesti_novo_razlicico(self, _razlog: str) -> None:
        """Enkrat, ko mora nova razlicica pocakati: kaj se bo zgodilo in gumb za takojsen zagon."""
        from core import obvestila
        b = nova_razlicica.besedila(_jezik(), "Safeer OS", self._nova_razlicica)

        def zdaj() -> None:
            if self._nova_cakanje is not None and not self._koncano:
                self._nova_cakanje.zdaj()
        # Pot D-Bus: stevilko obvestila shranimo v stanje za novo razlicico, ki ga ob zagonu zapre (prej je obvestilo z
        # gumbom »Znova zazeni zdaj« ostalo tudi po samodejnem zagonu nove razlicice - stresni preizkus 20. 10. 2026).
        obvestila.poslji(b["naslov"], b["besedilo"], "safeer-nova-razlicica", gumbi=[("zdaj", b["zdaj"], zdaj)], app=self,
                         dbus=True)

    def _zaposleno(self) -> str:
        """Kaj bi ponovni zagon prekinil ("" = nic): predvajanje, klic, prenos, posodobitev, delo Controla."""
        try:
            if self._medijski_podatki().get("stanje") == "predvaja":
                return "predvajanje"
        except Exception:  # noqa: BLE001
            pass
        razlog = nova_razlicica.zaposlenost_pogledov(Gtk, WebKit2)
        if razlog:
            return razlog
        for splet in (self._spletni, self._spletni_namizje):
            if splet is not None and any(z.get("stanje") == "tece" for z in (getattr(splet, "prenosi", None) or [])):
                return "prenos"
        if self.posodabljanje.tece():
            return "posodobitev"
        if budnost.dejavno("pomoc", 60):          # druga naprava bere datoteko ali tok s tega racunalnika
            return "prenos"
        try:
            torrenti = os_torrent.torrenti()
            if torrenti.tece() and getattr(torrenti, "_tokovi", None):
                return "predvajanje"             # film iz torrenta se gleda (prenosi brez gledanja se nadaljujejo sami)
        except Exception:  # noqa: BLE001
            pass
        c = en_proces.control_app()
        if c is not None and hasattr(c, "zaposlenost"):
            try:
                return c.zaposlenost() or ""
            except Exception:  # noqa: BLE001
                return ""
        return ""

    def _stanje_za_obnovo(self, napredek: bool = False) -> dict:
        """Zavihki Spleta, odprta okna Safeer OS in predvajanje (lokalna datoteka, polozaj) - za novo razlicico in za
        ponovni zagon po sesutju ali zamrznitvi (varuh). napredek=True zapise tudi »Nadaljuj z ogledom«."""
        predvajalnik = self.okno_predvajalnik is not None and self.okno_predvajalnik.get_visible()
        stanje = {"iz": RAZLICICA, "pid": os.getpid(),
                  "splet": nova_razlicica.zavihki([self._spletni, self._spletni_namizje]),
                  "okna": [ime for ime, par in self.okna_razdelkov.items() if par[0].get_visible()]
                  + (["predvajalnik"] if predvajalnik else [])}
        servis = self._medijski_predvajalnik
        if servis is not None and servis.trenutna is not None and servis.stanje in ("predvaja", "premor"):
            try:
                if napredek:
                    self._zadnji_medijski_napredek = None
                    self._shrani_medijski_napredek()     # »Nadaljuj z ogledom« ima zadnji polozaj (tudi tokovi)
                pot = nova_razlicica.lokalni_medij(servis.trenutna.uri)
                if pot:
                    p = servis.podatki()
                    stanje["predvajanje"] = {"pot": pot, "naslov": servis.trenutna.naslov,
                                             "vrsta": servis.trenutna.vrsta, "pozicija": int(p.get("pozicija") or 0),
                                             "predvaja": servis.stanje == "predvaja"}
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] stanje, predvajanje:", e, flush=True)
        return stanje

    def _posnemi_stanje(self) -> bool:
        """Vsakih POSNETEK_STANJA_S (samo pod varuhom): stanje za obnovo po sesutju - po njem ni casa za shranjevanje.
        Pise samo ob spremembi (XDG_RUNTIME_DIR, samo v pomnilniku, 0600)."""
        if self._koncano or self._ponovni_zagon:
            return False
        try:
            stanje = self._stanje_za_obnovo()
            besedilo = json.dumps(stanje, sort_keys=True)
            if besedilo != getattr(self, "_zadnji_posnetek_stanja", "") and \
                    nova_razlicica.shrani_stanje("safeer-os", stanje, ime=nova_razlicica.OBNOVA):
                self._zadnji_posnetek_stanja = besedilo
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] posnetek stanja:", e, flush=True)
        return True

    def _znova_v_novo(self) -> None:
        """Shrani zavihke Spleta in predvajanje, nato obicajen izhod (Scit, Link, pult); main() zazene novo razlicico."""
        if self._ponovni_zagon or self._koncano:
            return
        stanje = dict(self._stanje_za_obnovo(napredek=True), v=self._nova_razlicica)
        try:
            from core import obvestila
            stanje["obvestilo"] = obvestila.stevilka("safeer-nova-razlicica")
        except Exception:  # noqa: BLE001
            pass
        nova_razlicica.shrani_stanje("safeer-os", stanje)
        print("[SafeerOS] zaganjam novo razlicico %s (zavihkov: %d, predvajanje: %s)"
              % (self._nova_razlicica, len(stanje["splet"]), "da" if stanje.get("predvajanje") else "ne"), flush=True)
        self._ponovni_zagon = True
        self._koncaj()

    def _obnovi_po_novi_razlicici(self) -> bool:
        """Nova razlicica tece: zavihki Spleta in predvajanje iz stare (core/nova_razlicica.preberi_stanje)."""
        stanje = nova_razlicica.preberi_stanje("safeer-os", RAZLICICA)
        if stanje:
            print("[SafeerOS] nova razlicica %s tece (prej %s): obnovim stanje" % (RAZLICICA, stanje.get("iz")), flush=True)
            if stanje.get("obvestilo"):
                from core import obvestila
                obvestila.zapri_stevilko(stanje.get("obvestilo"))
        elif str(getattr(self, "_obnova_po_napaki", "")).isdigit():
            # Varuh je Safeer OS znova zagnal po sesutju, zamrznitvi ali preveliki porabi pomnilnika (lupina je ostala):
            # stanje, ki ga je posnel prav prejsnji proces (PID), ne kaksno starejse.
            prejsnji, self._obnova_po_napaki = int(self._obnova_po_napaki), ""
            stanje = nova_razlicica.preberi_stanje("safeer-os", ime=nova_razlicica.OBNOVA,
                                                   velja_s=nova_razlicica.OBNOVA_VELJA_S)
            if not stanje or stanje.get("pid") != prejsnji:
                return False
            print("[SafeerOS] ponovni zagon po napaki: obnovim zavihke (%d), okna (%d), predvajanje: %s" % (
                len(stanje.get("splet") or []), len(stanje.get("okna") or []), "da" if stanje.get("predvajanje") else "ne"),
                flush=True)
        else:
            return False
        for ime in stanje.get("okna") or []:
            try:
                if ime == "predvajalnik":
                    self._odpri_predvajalnik()
                elif ime in RAZDELKI_V_SVOJEM_OKNU and (ime != "sporocila" or sporocila_vklop.sporocila_vklopljena()):
                    self._odpri_okno_razdelka(ime)
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] obnova okna:", ime, e, flush=True)
        for naslov in stanje.get("splet") or []:
            try:
                self._splet(str(naslov), True)
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] obnova zavihka:", e, flush=True)
        p = stanje.get("predvajanje") or {}
        pot = nova_razlicica.lokalni_medij(p.get("pot", ""))
        if pot:
            # Predvajanje, ki je teklo (izrecen zagon), se nadaljuje; ustavljeno ostane ustavljeno, na istem mestu.
            self._predvajaj_neposredno(Gio.File.new_for_path(pot).get_uri(), vrsta=str(p.get("vrsta") or "medij"),
                                       prikazi=False, ime=str(p.get("naslov") or ""),
                                       zacetek=int(p.get("pozicija") or 0), v_premoru=not p.get("predvaja"))
        return False

    # ------------------------------------------------------------------ posnetek (preverjanje)
    def _za_posnetek(self, pogled, dogodek) -> None:
        if dogodek != WebKit2.LoadEvent.FINISHED or self._posnetek_nacrtovan:
            return
        self._posnetek_nacrtovan = True
        razdelek = os.environ.get("SAFEER_OS_RAZDELEK", "")
        if razdelek:
            GLib.timeout_add(1500, lambda: (self._js("window.safeerOsPojdi && safeerOsPojdi(%s)" % json.dumps(razdelek)), False)[1])
        # Razvoj: skripta, ki se izvede pred posnetkom (npr. klik na pogovor ali zamenjava imen za predstavitev).
        skripta = os.environ.get("SAFEER_OS_POSNETEK_JS", "")
        if skripta and os.path.isfile(skripta):
            with open(skripta, encoding="utf-8") as d:
                koda = d.read()
            GLib.timeout_add(2200, lambda: (self._js(koda), False)[1])
        zamik = int(os.environ.get("SAFEER_OS_POSNETEK_ZAMIK", "0") or 0)
        def velikost():
            pogled.evaluate_javascript("innerWidth + 'x' + innerHeight + ' @' + devicePixelRatio", -1, None, None, None,
                                       lambda p, r: print("pogled:", p.evaluate_javascript_finish(r).to_string()))
            return False
        GLib.timeout_add(3500 + zamik, velikost)
        GLib.timeout_add(4000 + zamik, self._naredi_posnetek)

    def _rezervni_posnetek(self) -> bool:
        if not self._posnetek_nacrtovan:
            self._posnetek_nacrtovan = True
            return self._naredi_posnetek()
        return False

    def _naredi_posnetek(self) -> bool:
        # Zajemi celo okno: levi WebKit je v spletnem nacinu samo stranska vrstica. Zagon s --predvajalnik nima
        # glavnega okna - takrat zajamemo Safeer Player.
        okno, pogled = (self.okno, self.pogled) if self.okno is not None else (self.okno_predvajalnik, self.pogled_predvajalnik)
        if okno is not None and okno.get_realized():
            try:
                # GTK4: Gdk.pixbuf_get_from_window ni vec - okno izrisemo z njegovim izrisovalnikom v teksturo.
                w, h = okno.get_width(), okno.get_height()
                slikar = Gtk.WidgetPaintable.new(okno)
                posnetek = Gtk.Snapshot()
                slikar.snapshot(posnetek, w, h)
                vozlisce = posnetek.to_node()
                if vozlisce is not None:
                    okno.get_native().get_renderer().render_texture(vozlisce, None).save_to_png(self.posnetek)
                    print("posnetek:", self.posnetek)
                    self.quit()
                    return False
            except Exception as e:  # noqa: BLE001
                print("posnetek okna ni uspel, poskus pogleda:", e)
        def konec(pogled, rezultat):
            try:
                povrsina = pogled.get_snapshot_finish(rezultat)
                # WebKitGTK 6.0: Gdk.Texture; 4.1: cairo.Surface
                (povrsina.save_to_png if hasattr(povrsina, "save_to_png") else povrsina.write_to_png)(self.posnetek)
                print("posnetek:", self.posnetek)
            except Exception as e:  # noqa: BLE001
                print("posnetek ni uspel:", e)
            self.quit()
        pogled.get_snapshot(WebKit2.SnapshotRegion.VISIBLE, WebKit2.SnapshotOptions.NONE, None, konec)
        return False

    # ------------------------------------------------------------------ most
    def _js(self, koda: str, pogled=None) -> None:
        for p in ([pogled] if pogled is not None else list(self.pogledi)):
            if hasattr(p, "qml_odgovor"):
                continue        # lupina QML nima JavaScripta strani; dogodke dobi prek _dogodek
            try:
                if hasattr(p, "evaluate_javascript"):          # WebKitGTK 6.0 (GTK4)
                    p.evaluate_javascript(koda, -1, None, None, None, None, None)
                else:
                    p.run_javascript(koda, None, None, None)
            except Exception:
                pass

    def _odgovori(self, pogled, id_, ok: bool, podatki) -> None:
        if hasattr(pogled, "qml_odgovor"):     # lupina QML: signal Qt je varen iz katerekoli niti
            pogled.qml_odgovor(int(id_), bool(ok), podatki)
            return

        def naredi():
            self._js("window.__safeerOsOdgovor(%d, %s, %s);" % (
                int(id_), "true" if ok else "false", json.dumps(podatki, ensure_ascii=True)), pogled)
            return False
        GLib.idle_add(naredi)

    def _seznam_programov(self) -> list:
        """Programi tega racunalnika za stran. Ob prvem klicu zacne spremljati mape z zaganjalniki: ko se program
        namesti ali odstrani, odprte strani dobijo dogodek »programi« in seznam preberejo znova."""
        if getattr(self, "_nadzor_programov", None) is None:
            self._nadzor_programov = os_programi.NadzorProgramov(self.programi.kandidati, lambda: self._dogodek("programi", None))
            try:
                self._nadzor_programov.zacni()
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] nadzor programov:", e)
        return self.programi.seznam(self._ikona)

    def _spremljaj_mapo(self, pogled, kaj: str) -> bool:
        """Stran pove, kateri pogled Datotek kaze (pot mape, »@nedavno«, »@smeti«; prazno = nobenega). Ko se tam kaj
        spremeni - tudi zaradi drugega programa -, odprte strani dobijo dogodek »datoteke« in seznam preberejo
        znova; ob priklopu ali odklopu nosilca dogodek »nosilci«."""
        nadzor = getattr(self, "_nadzor_map", None)
        if nadzor is None:
            nadzor = self._nadzor_map = os_datoteke.NadzorMap(
                lambda spremenjen: (self._dogodek("datoteke", {"pot": spremenjen}), self._priljubljene_osvezi_v_ozadju()),
                lambda: (self._dogodek("nosilci", None), self._priljubljene_osvezi_v_ozadju()))
            try:
                # Seznam nedavnih vodi GTK in spremembo javi sam (datoteka, odprta ali shranjena v drugem programu).
                _nedavni().connect(
                    "changed", lambda *_a: nadzor.zunanja(os_datoteke.NadzorMap.NEDAVNO))
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] nadzor nedavnih:", e)
        try:
            nadzor.obdrzi({id(p) for p in self.pogledi})
            return nadzor.spremljaj(id(pogled), kaj)
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] nadzor map:", e)
            return False

    #: Dogodki vrste skladb iz kataloga (konec, naslednja/prejsnja, vgradni predvajalnik): vrsto vodi stran.
    DOGODKI_VRSTE = frozenset({"mediaKonec", "mediaVrstaUkaz", "mediaYt", "mediaYtZaprt", "mediaYtNapaka"})

    def _odpri_medij_od_drugod(self, podatki: str) -> None:
        """media.open: Safeer Player pride v ospredje in isce naslov (uporabnik je rekel »prikazi na racunalniku«)."""
        try:
            m = json.loads(podatki or "{}")
        except ValueError:
            return
        naslov = " ".join(str((m or {}).get("title", "") or "").split())[:200]
        if naslov:
            self._odpri_predvajalnik(naslov)

    def _splet_od_drugod(self, url: str) -> None:
        url = str(url or "").strip()
        if url.lower().startswith(("http://", "https://")) and len(url) <= 4096:
            self._splet_na_namizju(url)

    def _isci_od_drugod(self, niz: str) -> None:
        """Niz z druge naprave (telefon kot mikrofon): namizje se pokaze, lupa ga isce - nic se ne odpre samo."""
        niz = " ".join(str(niz or "").split())[:200]
        if not niz or self.pogled_delovna is None:
            return
        os_okna.pokazi_namizje()
        if self.okno_delovna is not None:
            self.okno_delovna.present_with_time(_cas_dogodka(self.okno_delovna))
        elif self.lupina is not None:
            self.lupina.okno.requestActivate()
        self._dogodek("iskanjeOdDrugod", {"q": niz}, self.pogled_delovna)

    def _govor_dogodek(self, vrsta: str, podatki: dict) -> None:
        """Iz niti govora: stanje (poslusam, prepoznavam, besedilo, ...) gre na namizje."""
        self._dogodek("govor", dict(podatki or {}, vrsta=vrsta), self.pogled_delovna)

    def _dogodek(self, vrsta: str, podatki, pogled=None) -> None:
        """Dogodek strani: vsem pogledom ali samo [pogled]. Medijski center je lahko odprt dvakrat (glavno okno in
        Safeer Player): dogodke vrste skladb dobi samo stran, ki je predvajanje zacela, sicer bi ob koncu skladbe vsaka
        zacela svojo naslednjo."""
        if pogled is None:
            lastnik = self._katalog_pogled if vrsta in self.DOGODKI_VRSTE else None
            pogled = lastnik if lastnik is not None and any(p is lastnik for p in self.pogledi) else None

        lupina = getattr(self, "_qml_pogled", None)
        if lupina is not None and (pogled is None or pogled is lupina):
            lupina.qml_dogodek(vrsta, podatki)
            if pogled is lupina:
                return

        def naredi():
            self._js("window.safeerOsDogodek && window.safeerOsDogodek(%s, %s);" % (
                json.dumps(vrsta), json.dumps(podatki, ensure_ascii=True)), pogled)
            return False
        GLib.idle_add(naredi)

    def _na_sporocilo(self, pogled, rezultat) -> None:
        try:
            s = json.loads(rezultat.to_string())          # JSC.Value (WebKitGTK 6.0)
            if not zeton_velja(s):
                # Vgrajen okvir (tuja stran, komponenta) ali tuja stran: brez odgovora, brez izvedbe.
                if not getattr(self, "_most_zavrnjen", False):
                    self._most_zavrnjen = True
                    print("[SafeerOS] most: zavrnjeno sporocilo brez zetona (vgrajen okvir?)", flush=True)
                return
            id_, metoda, a = int(s.get("id", 0)), str(s.get("m", "")), list(s.get("a") or [])
        except Exception:
            return
        self._obdelaj_klic(pogled, id_, metoda, a)

    def _obdelaj_klic(self, pogled, id_: int, metoda: str, a: list) -> None:
        """Klic namizja: iz spletne strani (pogled WebKit) ali iz lupine QML (pogled = os_lupina.QmlPogled).
        Odgovor gre prek _odgovori nazaj istemu klicatelju."""
        # Na glavni niti (Gtk, ikone, okna):
        glavna = {
            # Vgrajeni kanali Sporocil (core/os_kanali_sporocil.py): v GLAVNI niti - ustvarjajo gradnike GTK in poglede
            # WebKit (v niti ozadja je proces padel ali obvisel; zivi preizkus 15. 10. 2026: »Dodaj v Sporocila« ni
            # naredil nicesar). Seznam bere tudi zive kanale (self.zivi), ki jih spreminja samo glavna nit.
            "kanaliSeznam": lambda: self._kanali_klic("seznam"),
            "kanaliKatalog": lambda: self._kanali_klic("katalog"),
            "kanalDodaj": lambda: self._kanali_klic("dodaj", str(a[0]) if a else "", str(a[1]) if len(a) > 1 else "",
                                                    str(a[2]) if len(a) > 2 else "", str(a[3]) if len(a) > 3 else ""),
            "kanalOdstrani": lambda: self._kanali_klic("odstrani", str(a[0]) if a else "", len(a) > 1 and a[1] is True),
            # »Preklici dodajanje«: samo kanal, ki se ni v uporabi (prijava ni koncana); podatki strani ostanejo.
            "kanalPreklici": lambda: self._kanali_klic("preklici", str(a[0]) if a else ""),
            "kanalPreimenuj": lambda: self._kanali_klic("preimenuj", str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            "kanalPremakni": lambda: self._kanali_klic("premakni", str(a[0]) if a else "",
                                                       int(a[1]) if len(a) > 1 and isinstance(a[1], (int, float)) else 1),
            "kanalVklopi": lambda: self._kanali_klic("vklopi", str(a[0]) if a else "", len(a) < 2 or a[1] is True),
            "kanalIzbrisiPodatke": lambda: self._kanali_klic("izbrisi_podatke", str(a[0]) if a else ""),
            "kanalPokazi": lambda: self._kanal_pokazi(pogled, str(a[0]) if a else "",
                                                      a[1] if len(a) > 1 and isinstance(a[1], dict) else {}),
            "kanalPolozaj": lambda: self._kanali() is not None and self._kanali().polozaj(
                pogled, a[0] if a and isinstance(a[0], dict) else {}),
            "kanalSkrij": lambda: self._kanali() is not None and self._kanali().skrij(pogled),
            "kanalUkaz": lambda: self._kanali_klic("ukaz", str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            "zacetek": self._zacetek,
            "zacniVlecenje": lambda: self._zacni_vlecenje(pogled, a[0] if a else []),
            "programi": self._seznam_programov,
            "spremljajMapo": lambda: self._spremljaj_mapo(pogled, str(a[0]) if a else ""),
            "zazeni": lambda: self.programi.zazeni(str(a[0]) if a else "", self._zazeni_vnos),
            "odpriZ": lambda: os_odpri_z.odpri_z(a[0] if a and isinstance(a[0], list) else [], str(a[1]) if len(a) > 1 else "",
                                                 bool(a[2]) if len(a) > 2 else False, self._zazeni_vnos_z),
            "pripni": lambda: self.programi.pripni(str(a[0]), bool(a[1]) if len(a) > 1 else True),
            # Dock (Plank): dodaj, odstrani, razvrsti iz menijev Safeer OS (core/os_dock.py).
            "skrijDomov": lambda: self.programi.skrij_domov(str(a[0]), bool(a[1]) if len(a) > 1 else True),
            "nedavnePozabi": lambda: self._nedavne_pozabi(str(a[0]) if a else ""),
            "nedavnePocisti": self._nedavne_pocisti,
            "nedavne": self._nedavne,
            "odprtaOkna": self._odprta_okna,
            "aktivirajOkno": lambda: self._okno_dejanje(a[0] if a else 0, "aktiviraj"),
            "zapriOkno": lambda: self._okno_dejanje(a[0] if a else 0, "zapri"),
            "namizje": self._namizje,
            "nastavitveDelov": self._nastavitve_delov,
            "nastavitevDela": lambda: self._nastavitev_dela(pogled, str(a[0]) if a else "", a[1] if len(a) > 1 else None),
            "celozaslonsko": lambda: self._celozaslonsko(bool(a[0]) if a else True),
            "control": lambda: self._odpri_control(),
            "prijava": lambda: self._prijava(),
            "domov": lambda: self._domov(str(a[0]) if a else ""),
            "preklopiOkno": lambda: self._okno_dejanje(a[0] if a else 0, "preklopi"),
            "shraniSpletne": lambda: self._shrani_spletne(a[0] if a else []),
            "splet": lambda: self._splet(str(a[0]) if a else "", len(a) > 1 and a[1] is True),
            "spletKonecPrijave": lambda: self._splet_konec_prijave([str(x) for x in (a[0] if a and isinstance(a[0], list) else [])]),
            "odjavaStoritve": lambda: self._odjava_storitve(str(a[0]) if a else ""),
            "medij": lambda: self._medij(str(a[0]) if a else ""),
            "osveziMedijskeMape": self._medijski_osvezi_mape,
            "dodajMedijskiTok": lambda: self._shrani_medijski_tok(
                str(a[0]) if a else "", str(a[1]) if len(a) > 1 else "",
                str(a[2]) if len(a) > 2 else ""),
            "odpriMedijskiTok": lambda: self._odpri_medijski_tok(str(a[0]) if a else ""),
            "odpriLokalniMedij": lambda: self._odpri_lokalni_medij(str(a[0]) if a else ""),
            "cakajociMagnet": self._vzemi_cakajoci_magnet,
            "cakajociStremio": self._vzemi_cakajoci_stremio,
            "kavcCelZaslon": lambda: self._kavc_cel_zaslon(pogled, bool(a[0]) if a else False),
            "vgrajenoAktivno": lambda: self._vgrajeno_aktivno(pogled, bool(a[0]) if a else False),
            "kopiraj": lambda: self._kopiraj(str(a[0]) if a else ""),
            "predvajajZNaprave": lambda: self._predvajaj_z_naprave(
                a[0] if a and isinstance(a[0], dict) else {}, str(a[1]) if len(a) > 1 else "",
                a[2] if len(a) > 2 and isinstance(a[2], list) else [], int(a[3]) if len(a) > 3 else 0,
                str(a[4]) if len(a) > 4 else "", str(a[5]) if len(a) > 5 else ""),
            "predvajalnikStanje": self._medijski_podatki,
            "predvajalnikUkaz": lambda: self._medijski_ukaz(str(a[0]) if a else "", a[1] if len(a) > 1 else None),
            "dvdPogoni": lambda: __import__("core.os_dvd", fromlist=["pogoni"]).pogoni(),
            "dvdPredvajaj": lambda: self._predvajaj_disk(str(a[0]) if a else ""),
            "dvdMeni": lambda: bool(self._medijski_predvajalnik and self._medijski_predvajalnik.navigacija(str(a[0]) if a else "meni")),
            "predvajalnikPodnapisi": lambda: (self._medijski_predvajalnik.podnapisi() if self._medijski_predvajalnik
                                              else {"moznosti": [], "izbran": "izklop"}),
            "predvajalnikIzberiPodnapise": lambda: bool(self._medijski_predvajalnik and
                                                        self._medijski_predvajalnik.izberi_podnapise(str(a[0]) if a else "")),
            "iskanjeSplet": lambda: self._splet(_iskalnik() + GLib.uri_escape_string(str(a[0] if a else ""), None, False)),
            "odpriVBrskalniku": lambda: self._odpri_v_brskalniku(str(a[0]) if a else ""),
            # Lupa: »Odpri safeer.si« nad »Isci v spletu« - naslov po istem pravilu kot naslovna vrstica Spleta.
            "naslovLupe": lambda: __import__("core.config", fromlist=["naslov_za_lupo"]).naslov_za_lupo(
                str(a[0]) if a else ""),
            "privzetiBrskalnik": privzeti_brskalnik,
            "sistemskeNastavitve": lambda: sistemske_nastavitve(str(a[0]) if a else ""),
            "skrijPloscoSporocil": lambda: self._skrij_plosco_sporocil(),
            "spletNaNamizju": lambda: self._splet_na_namizju(str(a[0]) if a else "",
                                                             a[1] if len(a) > 1 and isinstance(a[1], (int, float)) else 0),
            "spletNaNamizjuZapri": self._skrij_splet_na_namizju,
            "odpriRazdelek": lambda: self._odpri_razdelek(str(a[0]) if a else ""),
            "nastavitveDocka": lambda: self._zazeni_orodje(["safeer-cinnamon", "--nastavitve-docka"]),
            "nastavitveOzadja": lambda: sistemske_nastavitve("backgrounds"),
            "lupaUcenje": self.lupa.podatki,
            "lupaZapomni": lambda: self.lupa.zapomni(*(list(a or [])[:3])),
            "lupaPozabi": self.lupa.pozabi,
            # Govor v lupi (core/os_govor.py): prepoznava na tem racunalniku; dogodki gredo strani kot »govor«.
            "govorStanje": self.govor.stanje,
            "govorNamesti": lambda: self.govor.namesti(self._govor_dogodek),
            "govorPrekliciNamestitev": self.govor.preklici_namestitev,
            "govorPoslusaj": lambda: self.govor.poslusaj(os_govor.jezik_govora(_jezik()), self._govor_dogodek),
            "govorUstavi": self.govor.ustavi,
            "govorPreklici": self.govor.preklici,
            "zapiskiSeznam": lambda: self.zapiski.seznam(str(a[0]) if a else ""),
            "zapisekDobi": lambda: self.zapiski.dobi(str(a[0]) if a else ""),
            "zapisekShrani": lambda: self.zapiski.shrani(
                str(a[0]) if a else "", str(a[1]) if len(a) > 1 else "",
                str(a[2]) if len(a) > 2 else "",
                bool(a[3]) if len(a) > 3 and a[3] is not None else None),
            "zapisekIzbrisi": lambda: self.zapiski.izbrisi(str(a[0]) if a else ""),
            "sporocilaSeznam": lambda: self.sporocila.seznam(str(a[0]) if a else ""),
            # Predogled v oknu Safeer OS (core/os_predogled.py): okno takoj, prenos in priprava v ozadju.
            "sporocilaPredogled": lambda: self._predogled_priponke(pogled, *[str(x) for x in (list(a) + ["", "", ""])[:3]]),
            "sporocilaIzvirnik": lambda: self._predogled_pisma(pogled, *[str(x) for x in (list(a) + ["", "", ""])[:3]]),
            # Celo okno predogleda (core/os_predogled.py) za krajevno datoteko; »predogledDatoteke« je podatek za
            # predogled s preslednico v Datotekah (os_datoteke.predogled) - imeni sta locena, da se ne prekrijeta.
            "predogledOkno": lambda: self._predogled_datoteke(pogled, str(a[0]) if a else ""),
            "samozagon": lambda: self._samozagon(bool(a[0])) if a else je_samozagon(),
            "nazajVMint": lambda: self._nazaj_v_mint(bool(a[0]) if a else False),
            "vodnikKoncaj": lambda: self._vodnik_koncaj(),
            "vrniSafeerOs": lambda: vrni_safeer_os(self.shramba, bool(a[0]) if a else False),
            "nastaviJezik": lambda: self._nastavi_jezik(str(a[0]) if a else ""),
            # Razdelek izbira postavitev GLAVNEGA okna (vgrajeni Splet); Safeer Player ima samo Medijski center.
            "razdelek": lambda: self._razdelek(str(a[0]) if a else "domov") if pogled is self.pogled else True,
        }
        # V ozadju (ukazi, ki lahko trajajo):
        ozadje = {
            # Magnet: zagon rqbita in poizvedbe trajajo do minute (prej na glavni niti - namizje je zamrznilo);
            # predvajalnik odpre glavna nit (_predvajaj_magnet).
            "magnetPredvajaj": lambda: self._predvajaj_magnet(int(a[0]) if a else -1, int(a[1]) if len(a) > 1 else -1,
                                                             str(a[2]) if len(a) > 2 else ""),
            # "Nadaljuj z druge naprave" (Control vprasa naprave, do 4 s) in prevzem ponudbe - prej na glavni niti.
            "predajaPoizvedi": lambda: _control_naprave("Predaja"),
            "predajaPrevzemi": lambda: bool(_control_naprave("Prevzemi", str(a[0]) if a else "",
                                                             json.dumps(a[1] if len(a) > 1 and isinstance(a[1], dict) else {}),
                                                             "1" if len(a) > 2 and a[2] else "0").get("ok")),
            # Dock: v Flatpaku vsak klic tece prek flatpak-spawn (pgrep, dconf, kill, plank) - ne na glavni niti (pregled 14. 10.).
            "dock": self._dock_seznam,
            "dockDodaj": lambda: os_dock.dodaj(self.programi.pot(str(a[0]) if a else "") or ""),
            "dockOdstrani": lambda: os_dock.odstrani(str(a[0]) if a else ""),
            "dockRazvrsti": lambda: os_dock.razvrsti([str(x) for x in a[0]] if a and isinstance(a[0], list) else []),
            "posodobitveStanje": lambda: self._posodobitve_stanje(bool(a[0]) if a else False),
            "posodobitveKanal": lambda: self._posodobitve_kanal(str(a[0]) if a else ""),
            "posodobi": self._posodobi,
            "flatpakPreklop": self._flatpak_preklop,
            "stanje": os_sistem.stanje,
            "glasnost": lambda: os_sistem.nastavi_glasnost(int(a[0])),
            "utisaj": os_sistem.preklopi_utisaj,
            "svetlost": lambda: os_sistem.nastavi_svetlost(int(a[0])),
            "nocna": lambda: os_sistem.nastavi_nocno_luc(bool(a[0])),
            "wifi": lambda: os_sistem.nastavi_wifi(bool(a[0])),
            "nastavitve": lambda: os_sistem.odpri_nastavitve(str(a[0]) if a else ""),
            # Safeer Agent (core/agent): Nastavitve -> Safeer Agent in iskalna lupa (lastnik, 19. 10. 2026). V ozadju -
            # preverba dosegljivosti in ukaz agentu cakata na omrezje.
            "agentStanje": lambda: self._agent("stanje"),
            "agentNastavi": lambda: self._agent("naslov", a[0] if a else ""),
            "agentVklop": lambda: self._agent("vklop", a[0] is True if a else True),
            "agentTrajanje": lambda: self._agent("trajanje", a[0] if a else None),
            "agentDosegljivost": lambda: self._agent("dosegljivost"),
            "agentVprasaj": lambda: self._agent("vprasaj", str(a[0]) if a else ""),
            "napajanje": lambda: os_sistem.napajanje(str(a[0]) if a else ""),
            "mapa": lambda: os_datoteke.preglej(str(a[0]) if a else "~"),
            # Iz indeksa v pomnilniku (takoj, po vsej globini); drugi parameter: koliko zadetkov (razdelek Datoteke vec).
            "isciDatoteke": lambda: os_iskalnik.isci(
                str(a[0]) if a else "",
                min(300, max(1, int(a[1]))) if len(a) > 1 and isinstance(a[1], (int, float)) and not isinstance(a[1], bool)
                else os_datoteke.NAJVEC_ZADETKOV),
            "odpriDatoteko": lambda: os_datoteke.odpri(str(a[0]) if a else ""),
            "pokaziVMapi": lambda: os_datoteke.pokazi_v_mapi(str(a[0]) if a else ""),
            "novaMapa": lambda: os_datoteke.ustvari_mapo(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            "novaDatoteka": lambda: os_datoteke.ustvari_datoteko(
                str(a[0]) if a else "", str(a[1]) if len(a) > 1 else "",
                str(a[2]) if len(a) > 2 else "prazna", str(a[3]) if len(a) > 3 else ""),
            "predlogeDatotek": os_datoteke.predloge,
            "preimenujDatoteko": lambda: os_datoteke.preimenuj(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            "vSmeti": lambda: os_datoteke.v_smeti(str(a[0]) if a else ""),
            # Izbira vec datotek v Datotekah: vse v Smeti z enim zapisom za Razveljavi (idji).
            "vSmetiVec": lambda: os_datoteke.v_smeti_vec(a[0] if a and isinstance(a[0], list) else []),
            # Preslednica v Datotekah: slika, zacetek besedila (najvec 200 KB, ne binarno), prva stran PDF, medij.
            "predogledDatoteke": lambda: os_datoteke.predogled(str(a[0]) if a else ""),
            # Priljubljene datoteke, mape in programi (core/priljubljeno.py): en zapis za namizje QML in delovno
            # povrsino; sprememba gre obema kot dogodek »priljubljeno«.
            "priljubljenoSeznam": lambda: self._priljubljeno().stanje(),
            "priljubljenoPreklopi": lambda: self._priljubljeno().preklopi(
                str(a[0]) if a else "", a[1] if len(a) > 1 else None, a[2] if len(a) > 2 and isinstance(a[2], bool) else None),
            "priljubljenoVrstniRed": lambda: self._priljubljeno().vrstni_red(str(a[0]) if a else "", a[1] if len(a) > 1 else None),
            "priljubljenoKategorija": lambda: self._priljubljeno().kategorija(str(a[0]) if a else "", str(a[1]) if len(a) > 1 and a[1] else ""),
            "priljubljenoNastavi": lambda: self._priljubljeno().nastavi(str(a[0]) if a else "", a[1] if len(a) > 1 else None),
            "priljubljenoPreseli": lambda: self._priljubljeno().preseli(a[0] if a and isinstance(a[0], dict) else {}),
            "prostorDiska": lambda: os_datoteke.prostor(),
            "igreOblak": lambda: os_oblak_igre.stanje(),
            "igreOblakNamesti": lambda: os_oblak_igre.namesti(str(a[0]) if a else ""),
            "ponudnikiProgramov": lambda: os_ponudniki_programov.stanje(),
            "ponudnikNamesti": lambda: os_ponudniki_programov.namesti(str(a[0]) if a else ""),
            "ponudnikOdpri": lambda: os_ponudniki_programov.odpri(str(a[0]) if a else ""),
            "ponudnikPodrobnosti": lambda: os_ponudniki_programov.podrobnosti(str(a[0]) if a else ""),
            "viriProgramov": lambda: os_ponudniki_programov.viri(),
            "virPodrobnosti": lambda: os_ponudniki_programov.podrobnosti_vira(str(a[0]) if a else ""),
            "dodajVir": lambda: os_ponudniki_programov.dodaj_vir(str(a[0]) if a else ""),
            "githubIsci": lambda: os_github_programi.isci(str(a[0]) if a else ""),
            "githubIzdaje": lambda: os_github_programi.izdaje(str(a[0]) if a else ""),
            "githubShrani": lambda: os_github_programi.prenosi().zacni(*[str(x) for x in (list(a) + ["", "", "", ""])[:4]]),
            "githubStanje": lambda: os_github_programi.prenosi().stanje(str(a[0]) if a else ""),
            "prilepiDatoteke": lambda: os_datoteke.prilepi(a[0] if a and isinstance(a[0], list) else [], str(a[1]) if len(a) > 1 else "",
                                                           bool(a[2]) if len(a) > 2 else False),
            "spusceneDatoteke": self._spuscene_datoteke,
            "razveljaviDatoteke": lambda: os_datoteke.razveljavi(a[0] if a and isinstance(a[0], dict) else {}),
            "smeti": os_datoteke.smeti,
            "obnoviIzSmeti": lambda: os_datoteke.obnovi_iz_smeti(str(a[0]) if a else ""),
            "nosilci": os_datoteke.nosilci,
            "izvrziNosilec": lambda: os_datoteke.izvrzi(str(a[0]) if a else ""),
            "lastnostiDatoteke": lambda: os_datoteke.lastnosti(str(a[0]) if a else ""),
            "programiZaDatoteko": lambda: os_odpri_z.programi_za(str(a[0]) if a else ""),
            "programiZaOdpiranje": os_odpri_z.vsi_programi,
            "sliciceDatotek": lambda: {pot: GLib.filename_to_uri(s, None) for pot, s in
                                       os_datoteke.slicice(a[0] if a and isinstance(a[0], list) else []).items()},
            "najvecjeDatoteke": lambda: os_datoteke.najvecje(),
            "medijskeMape": lambda: self._medijska_knjiznica().mape_podrobno(),
            "odstraniMedijskoMapo": lambda: self._odstrani_medijsko_mapo(str(a[0]) if a else ""),
            "tokoviMedijev": lambda: self._medijska_knjiznica().tokovi(),
            "odstraniMedijskiTok": lambda: self._odstrani_medijski_tok(str(a[0]) if a else ""),
            "knjiznicaMedijev": lambda: self._medijska_knjiznica().seznam(
                str(a[0]) if a else "", str(a[1]) if len(a) > 1 else "", 120,
                int(a[2]) if len(a) > 2 else 0),
            "odstraniLokalniMedij": lambda: self._odstrani_lokalni_medij(str(a[0]) if a else ""),
            # »brez« (namizje QML): stanje brez iskanja Hubov po mDNS - namizje jih ne kaze (stran Naprave jih).
            "povezava": lambda: stanje_povezave("brez" if a and a[0] == "brez" else "cakaj"),
            "zaupanje": lambda: nastavi_zaupanje(bool(a[0]) if a else False),
            "predajanje": lambda: nastavi_predajanje(bool(a[0]) if a else False),
            "novaNaprava": lambda: control_dejanje("nova-naprava"),
            "odjava": lambda: control_dejanje("odjava"),
            "omrezje": lambda: os_omrezje.stanje(bool(a[0]) if a else False),
            # Internet prek telefona v Safeer Linku (Safeer Control). Stanje Controla ne zaganja; nastavitev in preizkus ga.
            "internetStanje": lambda: internet_prek_telefona("stanje", {"vprasaj": bool(a[0]) if a else False}, zazeni=False),
            "internetNastavi": lambda: internet_prek_telefona("nastavi", a[0] if a and isinstance(a[0], dict) else {}),
            "internetPreizkus": lambda: internet_prek_telefona("preizkus"),
            "omrezjePovezi": lambda: os_omrezje.povezi(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            "omrezjeOdklopi": lambda: os_omrezje.odklopi(str(a[0]) if a else ""),
            "omrezjeAktiviraj": lambda: os_omrezje.aktiviraj(str(a[0]) if a else ""),
            "omrezjePozabi": lambda: os_omrezje.pozabi(str(a[0]) if a else ""),
            "zvok": zvok_stanje,
            "zvokNaZvocnik": lambda: zvok_na_zvocnik(str(a[0]) if a else "", bool(a[1]) if len(a) > 1 else False),
            "zvokUstaviZvocnik": lambda: zvocniki().ustavi(),
            "zvokIsciZvocnike": lambda: zvocniki().osvezi() or True,
            "zvokZakasnitevZvocnika": lambda: zvocniki().nastavi_zakasnitev(str(a[0]) if a else "", a[1] if len(a) > 1 else 0),
            "zvokIzhod": lambda: zvok_izhod(str(a[0]) if a else ""),
            "zvokVhod": lambda: os_zvok.nastavi_vhod(str(a[0]) if a else ""),
            "zvokGlasnostIzhoda": lambda: os_zvok.glasnost_izhoda(str(a[0]), int(a[1])),
            "zvokUtisajIzhod": lambda: os_zvok.utisaj_izhod(str(a[0]), bool(a[1])),
            "zvokGlasnostVhoda": lambda: os_zvok.glasnost_vhoda(str(a[0]), int(a[1])),
            "zvokUtisajVhod": lambda: os_zvok.utisaj_vhod(str(a[0]), bool(a[1])),
            "zvokGlasnostPrograma": lambda: os_zvok.glasnost_programa(str(a[0]), int(a[1])),
            "zvokUtisajProgram": lambda: os_zvok.utisaj_program(str(a[0]), bool(a[1])),
            "zvokPremakniProgram": lambda: os_zvok.premakni_program(str(a[0]), str(a[1])),
            "zvokNaNapravo": lambda: zvok_na_napravo(str(a[0]) if a else ""),
            "napraveSProgrami": naprave_s_programi,
            "vseNaprave": vse_naprave,
            "napraveZDatotekami": naprave_z_datotekami,
            "magnetProgram": lambda: {"na_voljo": os_torrent.program_na_voljo(), "podprto": bool(os_torrent.platforma()),
                                      "mb": round((os_torrent.RQBIT_PAKETI.get(os_torrent.platforma()) or ("", "", 0))[2] / 1e6)},
            "magnetPrenesiProgram": self._magnet_prenesi_program,
            "magnetPreberi": lambda: _magnet_klic(lambda: os_torrent.torrenti().preberi(str(a[0]) if a else "")),
            "magnetDodaj": lambda: _magnet_klic(lambda: {"id": _magnet_dodaj(
                str(a[0]) if a else "", [int(x) for x in (a[1] if len(a) > 1 and isinstance(a[1], list) else [])],
                [int(x) for x in (a[2] if len(a) > 2 and isinstance(a[2], list) else [])])}),
            "magnetSeznam": lambda: os_torrent.torrenti().seznam(),
            "magnetPremor": lambda: os_torrent.torrenti().premor(int(a[0])),
            "magnetNadaljuj": lambda: _magnet_klic(lambda: os_torrent.torrenti().nadaljuj(int(a[0]))),
            "magnetOdstrani": lambda: os_torrent.torrenti().odstrani(int(a[0]), bool(a[1]) if len(a) > 1 else False),
            "magnetDeliNaprej": lambda: os_torrent.torrenti().deli_naprej(str(a[0]), bool(a[1]) if len(a) > 1 else False) or True,
            "magnetPovezava": lambda: _magnet_klic(lambda: {"uri": os_torrent.torrenti().magnet(int(a[0]))}),
            "magnetNaNapravo": lambda: _control_naprave("Magnet", str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            "magnetNaprave": naprave_za_magnet,
            "magnetMapa": lambda: self._odpri_mapo_prenosov(str(a[0]) if a else ""),
            "magnetPrivzeto": lambda: magnet_privzeto(bool(a[0]) if a else None),
            # Skupni prostor: datoteko shrani naprava z najvec prostora; original izbrise sele uporabnik.
            "shraniNaNapravo": lambda: _control_naprave("ShrambaZacni", str(a[0]) if a else ""),
            # Datoteke na izbrano napravo (povleci na napravo, »Poslji na napravo«): odda jih Safeer Control.
            "napraveZaPosiljanje": naprave_za_posiljanje,
            "posljiNapravi": lambda: _control_naprave(
                "Poslji", str(a[0]) if a else "",
                json.dumps([str(x) for x in (a[1] if len(a) > 1 and isinstance(a[1], list) else [])][:200])),
            "posljiStanje": lambda: _control_naprave("PosljiStanje", str(a[0]) if a else ""),
            "shrambaStanje": lambda: _control_naprave("ShrambaStanje", str(a[0]) if a else ""),
            "shrambaIzbrisi": lambda: _control_naprave("ShrambaIzbrisi", str(a[0]) if a else ""),
            "shrambaObdrzi": lambda: _control_naprave("ShrambaObdrzi", str(a[0]) if a else ""),
            # Slika, zvok, dokument: pretvorba na tem racunalniku (ImageMagick, ffmpeg, LibreOffice), brez spleta.
            "pretvorbaMoznosti": lambda: os_pretvorba_datotek.moznosti(str(a[0]) if a else ""),
            "pretvoriDatoteko": lambda: os_pretvorba_datotek.pretvorbe().zacni(str(a[0]) if a else "",
                                                                              str(a[1]) if len(a) > 1 else ""),
            "pretvorbaDatotekeStanje": lambda: os_pretvorba_datotek.pretvorbe().stanje(str(a[0]) if a else ""),
            "pretvoriVideo": lambda: _control_naprave("PretvorbaZacni", str(a[0]) if a else ""),
            # Ali »Pretvori za televizor« ta trenutek deluje (vnos menija se sicer ne pokaze).
            "pretvorbaZaTvMozna": pretvorba_za_tv_mozna,
            "pretvorbaStanje": lambda: _control_naprave("PretvorbaStanje", str(a[0]) if a else ""),
            "pretvorbaPrenesi": lambda: _control_naprave("PretvorbaPrenesi", str(a[0]) if a else ""),
            "pretvorbaPusti": lambda: _control_naprave("PretvorbaPusti", str(a[0]) if a else ""),
            "pretvoriVec": lambda: _control_naprave("PretvorbaZacniVec", json.dumps([str(x) for x in (a[0] if a and isinstance(a[0], list) else a)])),
            "pretvorbaSkupina": lambda: _control_naprave("PretvorbaSkupina", str(a[0]) if a else ""),
            "pretvorbaPrenesiSkupino": lambda: _control_naprave("PretvorbaPrenesiSkupino", str(a[0]) if a else ""),
            "pretvorbaPustiSkupino": lambda: _control_naprave("PretvorbaPustiSkupino", str(a[0]) if a else ""),
            "datotekeNaprave": lambda: datoteke_naprave(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            # Lupina QML (assets/os/qml/Datoteke.qml): datoteka z naprave sem (Teamwork) ali odprta na napravi.
            "prenesiDatotekoNaprave": lambda: prenesi_datoteko_naprave(
                str(a[0]) if a else "", str(a[1]) if len(a) > 1 else "", str(a[2]) if len(a) > 2 else "",
                a[3] if len(a) > 3 and isinstance(a[3], dict) else {},
                a[4] if len(a) > 4 and isinstance(a[4], list) else [], self._zazeni_vnos_z),
            "odpriDatotekoTukaj": lambda: odpri_na_napravi_tukaj(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            # Datoteka z druge naprave: sem se prenese samo, kar se je spremenilo (core/link_nadaljuj), nato se odpre.
            "nadaljujTukaj": lambda: nadaljuj_tukaj(
                a[0] if a and isinstance(a[0], dict) else {}, str(a[1]) if len(a) > 1 else "", str(a[2]) if len(a) > 2 else "",
                str(a[3]) if len(a) > 3 else "", str(a[4]) if len(a) > 4 else "",
                [str(x) for x in (a[5] if len(a) > 5 and isinstance(a[5], list) else [])][:32], self._zazeni_vnos_z),
            "preimenujNapravo": lambda: preimenuj_napravo(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            "upravljajRacunalnik": lambda: upravljaj_racunalnik(str(a[0]) if a else ""),
            "programiNaprave": lambda: programi_naprave(str(a[0]) if a else ""),
            "napraveZaMedij": naprave_za_medij,
            "odpriMedijNa": lambda: odpri_medij_na(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            "zazeniNaNapravi": lambda: zazeni_na_napravi(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            "odpriTukaj": lambda: odpri_tukaj(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            "zvokUstavi": zvok_ustavi,
            "odVklopa": lambda: od_vklopa(bool(a[0])) if a else od_vklopa_stanje(),
            "videzCinnamon": videz_cinnamon,
            "videzCinnamonNastavi": lambda: videz_cinnamon_nastavi(str(a[0]) if a else "", a[1] if len(a) > 1 else False),
            "jbl": lambda: os_jbl.stanje(True) if os_jbl else {"na_voljo": False},
            "jblVklop": lambda: os_jbl.vklopi(bool(a[0]) if a else False) if os_jbl else {"na_voljo": False},
            "scit": self.scit.stanje,
            "scitVklop": lambda: self._po_scitu(self.scit.nastavi(bool(a[0]) if a else False)),
            "scitDovoli": lambda: self._po_scitu(self.scit.dovoli(str(a[0]) if a else "", bool(a[1]) if len(a) > 1 else True)),
            "scitNaprej": lambda: self._po_scitu(self.scit.nastavi_naprej(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else "")),
            "scitTwitch": lambda: self._po_scitu(self.scit.nastavi_twitch(bool(a[0]) if a else True)),
            "scitPremor": lambda: self._po_scitu(self.scit.premor(a[0] if a and isinstance(a[0], (int, float)) and not isinstance(a[0], bool) else 0)),
            "scitStatistika": self._scit_statistika,
            "sporocilaDodaj": lambda: self.sporocila.dodaj_kanal(a[0] if a and isinstance(a[0], dict) else {}),
            "sporocilaPoslji": lambda: self.sporocila.poslji(str(a[0]), str(a[1]), str(a[2]),
                                                             a[3] if len(a) > 3 and isinstance(a[3], list) else None),
            "sporocilaNovo": lambda: self.sporocila.novo(str(a[0]), str(a[1]), str(a[2]), str(a[3]),
                                                         str(a[4]) if len(a) > 4 else "",
                                                         a[5] if len(a) > 5 and isinstance(a[5], list) else None),
            # Priponke (lastnik, 15. 10. 2026: »uporabnik ne sme pogresati Gmaila ali Outlooka«): prenos v Prejemi z
            # napredkom (dogodek priponkaNapredek) in slicice slik. »Odpri v programu« je samo v oknu predogleda, kjer
            # nevarno datoteko odpre sele po potrditvi.
            "sporocilaPrenesiPriponko": lambda: self._prenesi_priponko(*[str(x) for x in (list(a) + ["", "", ""])[:3]]),
            "sporocilaPrenesiVse": lambda: self.sporocila.priponke_prenesi_vse(
                str(a[0]), str(a[1]), napredek=lambda k, d: self._napredek_priponke(str(a[0]), str(a[1]), k, d)),
            "sporocilaSlicicaPriponke": lambda: (lambda pot: GLib.filename_to_uri(pot, None) if pot else "")(
                self.sporocila.priponka_slicica(str(a[0]), str(a[1]), str(a[2]))),
            "opisPrilog": lambda: _opis_prilog(a[0] if a and isinstance(a[0], list) else []),
            # »Vedno prikazi slike od …«: preklic (ali vklop) v podoknu osebe; lokalno, po naslovu posiljatelja.
            "sporocilaSlikeOd": lambda: self.sporocila.nastavi_slike_od(str(a[0]) if a else "", bool(a[1]) if len(a) > 1 else False),
            "sporocilaOsnutki": self.sporocila.uskladi_osnutke,
            "sporocilaShraniOsnutek": lambda: self.sporocila.shrani_osnutek(a[0] if a and isinstance(a[0], dict) else {}),
            "sporocilaOdstraniOsnutek": lambda: self.sporocila.odstrani_osnutek(str(a[0]) if a else ""),
            "sporocilaSinhroniziraj": self.sporocila.sinhroniziraj,
            "sporocilaIsci": lambda: self.sporocila.isci(str(a[0]) if a else ""),
            "sporocilaPogovor": lambda: self.sporocila.pogovor(str(a[0]), str(a[1]), a[2] is not False if len(a) > 2 else True),
            "sporocilaPreklici": lambda: self.sporocila.preklici(str(a[0]), str(a[1]), str(a[2])),
            "sporocilaSkrivnost": lambda: self.sporocila.nastavi_skrivnost(str(a[0]), str(a[1])),
            "sporocilaOdstrani": lambda: self.sporocila.odstrani_kanal(str(a[0])),
            "sporocilaStreznik": lambda: self.sporocila.privzeta_streznika(str(a[0]) if a else ""),
            "sporocilaPonudniki": lambda: self.sporocila.ponudniki(str(a[0]) if a else _jezik()),
            # Vgrajeni kanali Sporocil (spletni klepeti, namizni programi) in vklop - core/os_kanali_sporocil.py.
            "sporocilaVklop": lambda: self._nastavi_sporocila(bool(a[0]) if a else True),
            "sporocilaKanalVklop": lambda: self.sporocila.vklopi_kanal(str(a[0]), bool(a[1]) if len(a) > 1 else True),
            "sporocilaNaprave": self.sporocila.naprave_za_klepet,
            "sporocilaPreimenuj": lambda: self.sporocila.preimenuj_osebo(str(a[0]), str(a[1])),
            "sporocilaZdruzi": lambda: self.sporocila.zdruzi_osebi(str(a[0]), str(a[1])),
            "sporocilaRazdruzi": lambda: self.sporocila.razdruzi_osebo(str(a[0]), a[1]),
            "sporocilaOznake": lambda: self.sporocila.nastavi_oznake(str(a[0]), str(a[1]), a[2] if len(a) > 2 else []),
            # Dejanja v seznamu (arhiv, kos, neprebrano, zvezdica, mapa) za enega ali vec pogovorov; IMAP v tej niti.
            "sporocilaDejanje": lambda: self.sporocila.dejanje(a[0] if a and isinstance(a[0], list) else [],
                                                               str(a[1]) if len(a) > 1 else "", str(a[2]) if len(a) > 2 else ""),
            "sporocilaMapeRacuna": lambda: self.sporocila.mape(str(a[0]) if a else ""),
            "sporocilaOsebe": self.sporocila.osebe,
            "sporocilaIsciPri": lambda: self.sporocila.isci_pri_osebi(
                str(a[0]), str(a[1]), str(a[2]) if len(a) > 2 else "", str(a[3]) if len(a) > 3 else ""),
            "sporocilaZacni": lambda: self.sporocila.zacni_klepet(str(a[0]), str(a[1]) if len(a) > 1 else ""),
        }
        # Na glavni niti, odgovor pride kasneje (GTK4: sistemska okna in odlozisce so samo asinhrona - Dialog.run in
        # Clipboard.wait_for_text sta odstranjena). Funkcija dobi konec(izid) in ga poklice, ko uporabnik odloci.
        asinhrono = {
            "lokalniMediji": lambda konec: self._medijski_dodaj_datoteke(self._okno_klica(pogled), konec),
            "medijskaMapa": lambda konec: self._medijski_dodaj_mapo(self._okno_klica(pogled), konec),
            "medijskiTok": lambda konec: self._medijski_dodaj_tok(self._okno_klica(pogled), konec),
            "odlozisceBesedilo": lambda konec: self._odlozisce_besedilo(konec),
            "magnetIzDatoteke": lambda konec: self._magnet_iz_datoteke(bool(a[0]) if a else False,
                                                                       self._okno_klica(pogled), konec),
            "izberiMapo": lambda konec: self._izberi_mapo(*[str(x) for x in a[:4]], konec=konec),
            # Namizni program kot kanal Sporocil, ki ni v obicajni mapi (AppImage drugje): uporabnik izbere datoteko.
            "kanalIzberiProgram": lambda konec: self._izberi_poti(
                str(a[0]) if a else "", pogled.get_root() if hasattr(pogled, "get_root") else self.okno, "datoteka",
                lambda poti: konec(poti[0] if poti else "")),
            # Plosca »Info« v Sporocilih: poraba kanalov (pomnilnik, procesor, disk); disk prebere WebKit asinhrono.
            "kanaliPoraba": lambda konec: self._kanali().poraba.porocilo(konec),
            # »Prilozi« v Sporocilih: sistemsko okno za vec datotek; stran dobi ime in velikost (cipi pod vnosom).
            "izberiPriloge": lambda konec: self._izberi_poti(
                str(a[0]) if a else "", self._okno_pogleda(pogled), "datoteke",
                lambda poti: konec(_opis_prilog(poti)), potrdi=str(a[1]) if len(a) > 1 else ""),
        }
        if metoda == "izprazniSmeti":
            # Trajni izbris: potrditev v sistemskem oknu na glavni niti (stran je ne more preskociti), brisanje v ozadju.
            def delo_smeti():
                try:
                    # Kar je bilo v Smeteh, je zdaj trajno izbrisano: zapisi priljubljenih zanj gredo. Samo za tisto,
                    # cesar po praznjenju res ni vec v Smeteh (delno praznjenje: ostalo se da se obnoviti).
                    izvirne = {str(e.get("izvirna") or "") for e in os_datoteke.smeti().get("elementi") or []}
                    izid = os_datoteke.izprazni_smeti()
                    try:
                        ostale = {str(e.get("izvirna") or "") for e in os_datoteke.smeti().get("elementi") or []}
                        self._priljubljeno().odstrani_poti(sorted(x for x in izvirne - ostale if x))
                    except Exception as e:  # noqa: BLE001
                        print("[SafeerOS] priljubljene:", e)
                    self._odgovori(pogled, id_, True, dict(izid, potrjeno=True))
                except Exception as e:  # noqa: BLE001
                    print("[SafeerOS] izprazni smeti:", e)
                    self._odgovori(pogled, id_, False, str(e))

            def odlocitev(potrjeno: bool) -> None:
                if not potrjeno:
                    self._odgovori(pogled, id_, True, {"ok": True, "potrjeno": False})
                    return
                threading.Thread(target=delo_smeti, name="safeer-smeti", daemon=True).start()
            self._potrdi_izpraznitev_smeti(odlocitev)
            return
        if metoda in asinhrono:
            poslano = []

            def konec(izid, _p=pogled, _i=id_) -> None:
                if poslano:            # odgovor samo enkrat, tudi ce bi ga pot klicala dvakrat
                    return
                poslano.append(True)
                self._odgovori(_p, _i, True, izid)
            try:
                asinhrono[metoda](konec)
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS]", metoda, e)
                if not poslano:
                    poslano.append(True)
                    self._odgovori(pogled, id_, False, str(e))
            return
        if self._katalog_most().pozna(metoda):
            if metoda == "mediaPredvajaj":
                self._katalog_pogled = pogled     # ta stran zdaj vodi vrsto skladb (glej _dogodek)
            # Katalog Medijskega centra bere omrezje: vedno v ozadju; okno (predvajalnik) klice sam v glavni niti.
            # Katalog vzamemo tu, na glavni niti: _katalog_most() ga ob prvem klicu ustvari in bere zaslon (Gdk) -
            # nit naj ga dobi ze ustvarjenega (naloga 42, vmesnik samo iz glavne niti).
            katalog = self._katalog_most()

            def delo_katalog():
                try:
                    self._odgovori(pogled, id_, True, katalog.izvedi(metoda, a))
                except Exception as e:  # noqa: BLE001
                    print("[SafeerOS]", metoda, e)
                    self._odgovori(pogled, id_, False, str(e))
            threading.Thread(target=delo_katalog, daemon=True).start()
        elif metoda in glavna:
            try:
                self._odgovori(pogled, id_, True, glavna[metoda]())
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS]", metoda, e)
                self._odgovori(pogled, id_, False, str(e))
        elif metoda in ozadje:
            def delo():
                try:
                    izid = ozadje[metoda]()
                    if metoda in self.SPREMINJAJO_DATOTEKE:
                        os_iskalnik.zastarel()      # naslednje iskanje naj indeks datotek obnovi
                        self._priljubljene_sledijo(metoda, a, izid)
                    self._odgovori(pogled, id_, True, izid)
                except Exception as e:  # noqa: BLE001
                    print("[SafeerOS]", metoda, e)
                    self._odgovori(pogled, id_, False, str(e))
            threading.Thread(target=delo, daemon=True).start()
        else:
            self._odgovori(pogled, id_, False, "neznano")

    #: Metode mostu, po katerih je indeks imen datotek (core/os_iskalnik.py) zastarel.
    SPREMINJAJO_DATOTEKE = frozenset({"novaMapa", "novaDatoteka", "preimenujDatoteko", "vSmeti", "vSmetiVec", "prilepiDatoteke",
                                      "obnoviIzSmeti", "razveljaviDatoteke", "nadaljujTukaj",
                                      "prenesiDatotekoNaprave"})

    def _agent(self, kaj: str, vrednost=None):
        """Nastavitve in klic Safeer Agenta (core/agent/nastavitve.py, storitev.vprasaj_tukaj). Sprememba nastavitev gre
        vsem pogledom kot dogodek »agent« (iskalna lupa na namizju pokaze ali skrije vnos agenta)."""
        from core.agent import nastavitve as agent_nastavitve
        from core.agent import storitev as agent_storitev
        if kaj == "stanje":
            return agent_nastavitve.stanje()
        if kaj == "dosegljivost":
            return agent_nastavitve.dosegljivost()
        if kaj == "vprasaj":
            return agent_storitev.vprasaj_tukaj(vrednost)
        izid = {"naslov": agent_nastavitve.nastavi_naslov, "vklop": agent_nastavitve.nastavi_vklop,
                "trajanje": agent_nastavitve.nastavi_trajanje}[kaj](vrednost)
        if izid.get("ok"):
            self._dogodek("agent", {"na_voljo": bool(izid.get("na_voljo"))})
        return izid

    def _priljubljeno(self) -> "priljubljeno.Priljubljeno":
        """Shramba priljubljenih; vsaka sprememba gre obema namizjema (QML in WebKit) kot dogodek »priljubljeno«."""
        return priljubljeno.shramba(lambda stanje: self._dogodek("priljubljeno", stanje))

    def _priljubljene_sledijo(self, metoda: str, a: list, izid) -> None:
        """Preimenovana ali premaknjena datoteka (tudi z Razveljavi) ostane priljubljena na novem mestu."""
        try:
            pari = (priljubljeno.premaknjeno_po_razveljavitvi(a[0] if a else {}, izid) if metoda == "razveljaviDatoteke"
                    else priljubljeno.premaknjeno_po_dejanju(metoda, a, izid))
            if pari:
                self._priljubljeno().premaknjeno(pari)
            # V Smeti, obnova (Obnovi, Razveljavi), premik: vidne priljubljene so se lahko spremenile.
            self._priljubljeno().osvezi()
        except Exception as e:  # noqa: BLE001 - priljubljene ne smejo podreti dejanja z datotekami
            print("[SafeerOS] priljubljene:", e)

    def _priljubljene_osvezi_v_ozadju(self) -> None:
        """Disk priklopljen/odklopljen ali mapa spremenjena zunaj: priljubljene na njem se pokazejo ali skrijejo.
        Zdruzeno: kopiranje 1000 datotek v spremljano mapo da 1000 sprememb - ena osvezitev po 0,7 s, ne 1000 niti."""
        if getattr(self, "_prilj_caka", False):
            return
        self._prilj_caka = True

        def delo():
            self._prilj_caka = False
            try:
                self._priljubljeno().osvezi()
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] priljubljene:", e)

        def zazeni():
            threading.Thread(target=delo, daemon=True, name="safeer-priljubljene").start()
            return False
        GLib.timeout_add(700, zazeni)

    #: Besedila sistemskega okna za trajni izbris (naslov, opis, preklic, potrditev).
    BESEDILA_SMETI = {
        "sl": ("Izpraznim Smeti?", "Elementov v Smeteh: {n}. Izbrisani bodo trajno in jih ne bo več mogoče obnoviti.", "Prekliči", "Izprazni Smeti"),
        "en": ("Empty the Trash?", "Items in the Trash: {n}. They will be deleted permanently and cannot be restored.", "Cancel", "Empty Trash"),
        "de": ("Papierkorb leeren?", "Elemente im Papierkorb: {n}. Sie werden endgültig gelöscht und können nicht wiederhergestellt werden.", "Abbrechen", "Papierkorb leeren"),
        "es": ("¿Vaciar la papelera?", "Elementos en la papelera: {n}. Se eliminarán definitivamente y no se podrán recuperar.", "Cancelar", "Vaciar papelera"),
        "fr": ("Vider la corbeille ?", "Éléments dans la corbeille : {n}. Ils seront supprimés définitivement et ne pourront pas être restaurés.", "Annuler", "Vider la corbeille"),
        "it": ("Svuotare il cestino?", "Elementi nel cestino: {n}. Saranno eliminati definitivamente e non potranno essere ripristinati.", "Annulla", "Svuota cestino"),
    }

    def _potrdi_izpraznitev_smeti(self, odlocitev: Callable[[bool], None]) -> None:
        """Vprasa v sistemskem (GTK) oknu; privzeti gumb je Preklici. Prazne Smeti: nic za vprasati.
        GTK4: Gtk.AlertDialog je asinhron - odlocitev(True/False) pride, ko uporabnik izbere."""
        n = os_datoteke.smeti()["skupaj"]
        if not n:
            odlocitev(False)
            return
        naslov, opis, preklic, potrdi = self.BESEDILA_SMETI.get(_jezik(), self.BESEDILA_SMETI["en"])
        okno = Gtk.AlertDialog()
        okno.set_message(naslov)
        okno.set_detail(opis.format(n=n))
        okno.set_buttons([preklic, potrdi])
        okno.set_cancel_button(0)
        okno.set_default_button(0)
        okno.set_modal(True)

        def izbrano(dialog, izid) -> None:
            try:
                i = dialog.choose_finish(izid)
            except Exception:  # noqa: BLE001 - zaprto brez izbire (Esc)
                i = 0
            odlocitev(i == 1)
        okno.choose(self.get_active_window(), None, izbrano)

    # ------------------------------------------------------------------ dejanja
    def _zacetek(self) -> dict:
        ozadje = os_sistem.ozadje_namizja()
        shranjene_spletne = self.shramba.get("spletne", None)
        if isinstance(shranjene_spletne, list):
            ciste_spletne = os_spletne.pocisti(shranjene_spletne)
            if ciste_spletne != shranjene_spletne:
                self.shramba.set("spletne", ciste_spletne)
            shranjene_spletne = ciste_spletne
        izid = {
            "jezik": _jezik(),
            "ime": GLib.get_real_name() if GLib.get_real_name() not in ("", "Unknown") else GLib.get_user_name(),
            "racunalnik": socket.gethostname(),
            "odVklopa": od_vklopa_stanje(),
            "videz": videz_cinnamon(),
            "vlecenjeDatotek": self._vlecenje_na_voljo(),
            "ozadje": ("file://" + GLib.uri_escape_string(ozadje, "/", False)) if ozadje else "",
            "razpolozljivo": os_sistem.razpolozljivo(_jezik()),
            # Iskalna lupa: vnos »Vprasaj Safeer Agenta« samo, ce ima agent nastavljen in vklopljen model.
            "agent": {"na_voljo": bool(self._agent("stanje").get("na_voljo"))},
            "mape": os_datoteke.uporabniske_mape(),
            "zaznamki": os_datoteke.zaznamki(izpusti=[m["pot"] for m in os_datoteke.uporabniske_mape()]),
            "celozaslonsko": bool(self.shramba.get("celozaslonsko", True)) and not self.v_oknu,
            # Safeer Cinnamon: Safeer OS je vedno v oknu (main), stikalo Celozaslonsko nima ucinka; ob delovni
            # povrsini zagon ob prijavi vodi seja safeer-cinnamon - Nastavitve stikal ne pokazejo (os.js).
            "safeerCinnamon": _safeer_cinnamon_vklopljen(),
            # Wayland: namizja cez cel zaslon ni (main) - stikalo Celozaslonsko bi bilo prazen gumb (os.js ga skrije).
            "wayland": seja_prikaza.je_wayland(),
            "samozagonNamizje": delovna_safeer_cinnamon(),
            "namizje": self.namizje,
            "spletne": shranjene_spletne,
            "razlicica": RAZLICICA,
            "sistem": _ime_sistema(),
            "samozagon": je_samozagon(),
            "povezava": stanje_povezave("ozadje"),
            "sporocila": sporocila_vklop.sporocila_vklopljena(),
        }
        izid.update(self._zacetek_vodnika())
        return izid

    def _zacetek_vodnika(self) -> dict:
        """Vodnik ob prvem zagonu v glavnem oknu; na namizju (QML, delovna povrsina WebKit) ga namizje odpre v oknu
        Nastavitve (odpriRazdelek »vodnik«; okno razdelka in Safeer Player to vesta v os.js); zagon iz menija
        po »Nazaj na Cinnamon«: os.js enkrat vprasa, ali naj se Safeer OS spet zaganja ob prijavi."""
        return {"vodnik": bool(self._vodnik),
                "vrnitev": isinstance(self.shramba.get("nazaj_na_cinnamon"), dict) and not self.delovna}

    # ------------------------------------------------------------------ vgrajeni kanali Sporocil
    def _prekrivanje_kanalov(self, pogled):
        """Gtk.Overlay okoli strani: nad njo so vgrajeni kanali Sporocil na mestu vsebine (os_kanali_sporocil)."""
        prekrivanje = Gtk.Overlay()
        prekrivanje.set_child(pogled)
        if not hasattr(self, "_prekrivanja"):
            self._prekrivanja = {}
        self._prekrivanja[id(pogled)] = prekrivanje
        return prekrivanje

    def _jedro_spleta(self):
        """Vgrajeni Splet, v katerem tecejo spletni kanali (ista seja = ena prijava). Obstojeci (glavno okno ali plosca
        na namizju), sicer plosca na namizju brez okna in brez zavihka. None brez peskovnika WebKit."""
        if self._spletni is not None:
            return self._spletni
        if self._spletni_namizje is None:
            if not self._peskovnik_na_voljo():
                return None
            self._ustvari_splet_namizja(prvi_zavihek=False)
        return self._spletni_namizje

    def _kanali(self):
        """Kanali Sporocil (ustvari se ob prvi rabi); None, ce so Sporocila izklopljena in se niso bili ustvarjeni."""
        k = getattr(self, "_kanali_sporocil", None)
        if k is None:
            from core import os_kanali_sporocil
            k = self._kanali_sporocil = os_kanali_sporocil.KanaliSporocil(
                Gtk, GLib, Gio, self._jedro_spleta, self._config_spleta(), _jezik, self._kanali_dogodek, self._odpri_kanal)
            # Plosca »Info«: poraba kanalov (vzorci vsakih 30 s, samo ko tece vsaj en spletni kanal ali program).
            from core import os_poraba_kanalov
            k.poraba = os_poraba_kanalov.PorabaKanalov(GLib, k, lambda: getattr(self, "sporocila", None))
        return k

    def _config_spleta(self):
        """Ena shramba nastavitev Spleta v procesu (oba Spleta in kanali Sporocil): vsak ConfigManager pise celo
        datoteko, dva primerka bi si prepisovala spremembe (npr. seznam kanalov ali dovoljenja strani)."""
        c = getattr(self, "_nastavitve_spleta", None)
        if c is None:
            from core.config import ConfigManager
            c = self._nastavitve_spleta = ConfigManager()
        return c

    def _kanali_dogodek(self, vrsta: str, podatki) -> None:
        self._dogodek(vrsta, podatki)
        self._osvezi_kuverto()           # znacka se posodobi takoj ob spremembi naslova strani (< 1 s)

    def _kanali_klic(self, metoda: str, *argumenti):
        k = self._kanali()
        try:
            return getattr(k, metoda)(*argumenti)
        except (KeyError, ValueError) as e:
            raise ValueError(str(e.args[0]) if e.args else metoda) from None

    def _kanal_pokazi(self, pogled, kid: str, pravokotnik: dict) -> dict:
        prekrivanje = getattr(self, "_prekrivanja", {}).get(id(pogled))
        if prekrivanje is None:
            return {"ok": False, "razlog": "okno"}
        return self._kanali().pokazi(pogled, prekrivanje, kid, pravokotnik)

    def _obvesti_novo_pismo(self, kanal_id: str, pogovor_id: str, naslov: str, besedilo: str) -> None:
        """Nit kanala -> glavna nit. Ko je okno Safeer OS aktivno, uporabnik pismo vidi v seznamu (znacka, na vrhu
        Prejetega) in obvestila ne dobi - tako kot Gmail v ospredju. Klik na obvestilo odpre pogovor."""
        def pokazi() -> bool:
            if any(o.is_active() for o in Gtk.Window.list_toplevels() if isinstance(o, Gtk.Window)):
                return False
            cilj = "pogovor:%s:%s" % (kanal_id, pogovor_id)

            def odpri() -> None:
                GLib.idle_add(lambda: (self._odpri_razdelek(cilj) if _ima_delovno(self) or self.okno is None
                                       else self._domov(cilj), False)[1])
            from core import obvestila
            obvestila.poslji(naslov or "Safeer OS", besedilo, "safeer-posta-" + kanal_id, privzeto=odpri)
            return False
        GLib.idle_add(pokazi)

    def _odpri_kanal(self, kid: str) -> None:
        """Klik na obvestilo kanala: Sporocila se odprejo na tem kanalu."""
        if sporocila_vklop.sporocila_vklopljena():
            GLib.idle_add(lambda: (self._odpri_razdelek("kanal:" + kid) if _ima_delovno(self) or self.okno is None
                                   else self._domov("kanal:" + kid), False)[1])

    def _zacni_kanale(self) -> bool:
        if sporocila_vklop.sporocila_vklopljena() and not self.posnetek:
            self._kanali().zazeni_vse()
        return False

    def _nastavi_sporocila(self, vklop: bool) -> bool:
        """Moznost Sporocila v celoti (Nastavitve Safeer OS, Prilagodi namizje): izklop ustavi storitev, kanale, kuverto
        in obvestila; razdelka ni nikjer. Vklop vse vrne brez ponovnega zagona; nastavitve kanalov ostanejo."""
        sporocila_vklop.nastavi_sporocila(bool(vklop))
        # Storitev (IMAP, Telegram ...) lahko ob ustavljanju caka na omrezje: tu, v niti klica (most: ozadje). Kanali,
        # kuverta in okna so GTK in WebKit - samo v glavni niti (pregled 15. 10. 2026).
        if vklop:
            self.sporocila.nadaljuj()
        else:
            self.sporocila.ustavi()
        if threading.current_thread() is threading.main_thread():
            self._uskladi_vklop_sporocil(bool(vklop))
        else:
            GLib.idle_add(lambda: (self._uskladi_vklop_sporocil(bool(vklop)), False)[1])
        return bool(vklop)

    def _uskladi_vklop_sporocil(self, vklop: bool) -> None:
        """Del vklopa Sporocil v glavni niti: kanali, kuverta, okno Sporocil, dogodek strani in namizju."""
        if vklop:
            self._zacni_kanale()
            self._zacni_kuverto()
        else:
            k = getattr(self, "_kanali_sporocil", None)
            if k is not None:
                k.ustavi_vse()
            kuverta = getattr(self, "_kuverta", None)
            if kuverta is not None:
                try:
                    kuverta.zapri()
                except Exception as e:  # noqa: BLE001
                    print("[SafeerOS] kuverta:", e)
                self._kuverta = None
                # Ponoven vklop mora narediti novo ikono (pregled 18. 10.: kazalec na zaprto kuverto je ostal).
                self.kuverta_pult = None
            okno = self.okna_razdelkov.get("sporocila")
            if okno is not None:
                okno[0].set_visible(False)
            self._skrij_plosco_sporocil()
        self._dogodek("sporocilaVklop", bool(vklop))
        if self.lupina is not None:
            try:
                self.lupina.dogodek("videz", self.lupina.videz())
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] videz ob vklopu Sporocil:", e)

    def _samozagon(self, vklop: bool) -> bool:
        ok = nastavi_samozagon(vklop)
        if ok:
            self.shramba.set("samozagon", bool(vklop))
            self.shramba.set("samozagon_izbral", True)      # izbira uporabnika: selitev ob zagonu je ne spreminja vec
        return je_samozagon()

    def _vodnik_koncaj(self) -> bool:
        """Vodnik ob prvem zagonu je koncan ali preskocen: ne pokaze se vec sam (Nastavitve ga odprejo znova)."""
        self._vodnik = False
        self.shramba.set("vodnik", "koncan")
        return True

    def _nastavi_jezik(self, jezik: str) -> str:
        """Jezik namizja iz vodnika: ista nastavitev, ki jo bere _jezik() (ui_language Safeer Browserja). Velja takoj
        za vsa odprta okna in lupino QML (dogodek »jezik«)."""
        if jezik in ("sl", "en", "de", "es", "fr", "it"):
            try:
                from core.config import ConfigManager
                ConfigManager().set("ui_language", jezik)
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] jezik:", e)
            self._dogodek("jezik", {"jezik": jezik})
        return _jezik()

    def _nazaj_v_mint(self, za_stalno: bool) -> bool:
        """Zapre Safeer OS; pred uporabnikom je obicajno namizje Linux Mint. Nazaj se vrne iz menija (Safeer OS).

        Ob Safeer Cinnamon (delovna povrsina) samo zaprtje ni bilo dovolj (lastnik, 14. 10. 2026: »uporabnik lahko
        kadarkoli preklopi na Mint namizje«): ikone Nemo so ostale skrite, ob naslednji prijavi pa je Safeer OS zagnal
        safeer-cinnamon --seja ne glede na stikalo. Zato: »Samo tokrat« vrne ikone namizja za to sejo (ob naslednji
        prijavi spet Safeer OS); »Nazaj na Cinnamon« (za_stalno) vrne prejsnji videz Minta - nazaj_na_cinnamon, isto kot
        `safeer-os --nazaj-na-cinnamon`; Safeer OS iz menija ponudi vrnitev."""
        if za_stalno:
            # Loceno od Safeer OS: --izklopi konca tudi delovno povrsino (SIGTERM -> _koncaj pospravi).
            nazaj_na_cinnamon(self.shramba, pocakaj=False)
        elif videz_cinnamon()["naVoljo"]:
            try:
                subprocess.run(["gsettings", "set", "org.nemo.desktop", "show-desktop-icons", "true"],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
                from core import varuh_procesov
                pid = varuh_procesov.zazeni_program(["nemo-desktop"], zasebni_webkit.okolje_za_zunanje())
                if not pid:
                    subprocess.Popen(["nemo-desktop"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, start_new_session=True,
                                     env=zasebni_webkit.okolje_za_zunanje())
            except Exception as e:  # noqa: BLE001 - Safeer OS se zapre v vsakem primeru
                print("[SafeerOS] nazaj v Mint:", e)
        GLib.timeout_add(250, lambda: (self._koncaj(), False)[1])
        return True

    def _shrani_spletne(self, seznam) -> list:
        """Spletne aplikacije: ime, HTTP(S) naslov in neobvezna vrsta medija, največ 24."""
        cisti = os_spletne.pocisti(seznam)
        self.shramba.set("spletne", cisti)
        return cisti

    def _dock_seznam(self) -> dict:
        """Programi v docku po vrsti, z imenom in ikono; »plank« = ali je dock sploh namescen."""
        programi = []
        vnosi = [(e, os_programi.preberi_vnos(e["pot"]) or {}) for e in os_dock.elementi()]
        # Tema ikon (Gtk) samo na glavni niti (gostitelj.ikona_iz_teme); ta metoda tece v ozadju.
        ikone = self._v_glavni_pocakaj(lambda: {v["ikona"]: self._ikona(v["ikona"]) for _e, v in vnosi if v.get("ikona")})
        ikone = ikone if isinstance(ikone, dict) else {}
        for e, v in vnosi:
            ime = v.get("ime") or (e["id"][: -len(".desktop")] if e["id"].endswith(".desktop") else e["id"])
            programi.append({"id": e["id"], "dockitem": e["dockitem"], "ime": ime, "ikona": ikone.get(v.get("ikona"), "")})
        # »plank« = ali je dock, ki ga Safeer OS ureja (Plank na X11 ali priljubljeni GNOME - Ubuntu Dock, tudi Wayland);
        # »Vec nastavitev docka« ima samo Plank (safeer-cinnamon --nastavitve-docka).
        vrsta = os_dock.vrsta_docka()
        return {"ok": True, "plank": bool(vrsta), "vecNastavitev": vrsta == "plank", "programi": programi}

    def _ikona(self, ime: str) -> str:
        if ime not in self._ikone:
            pot = os_programi.pot_ikone(ime)
            self._ikone[ime] = ("file://" + GLib.uri_escape_string(pot, "/", False)) if pot else ""
        return self._ikone[ime]

    def _zazeni_vnos(self, pot: str) -> bool:
        return self._zazeni_vnos_z(pot, [])

    def _zazeni_vnos_z(self, pot: str, datoteke: list) -> bool:
        """Zazene program iz menija, po zelji z datotekami (»Odpri z ...«) - z okoljem namizja, da novo okno pride
        v ospredje."""
        # Flatpak: program tece na racunalniku, ne v peskovniku (core/gostitelj.py).
        if gostitelj.v_flatpaku():
            return gostitelj.zazeni_vnos(pot, datoteke)
        from core import varuh_procesov
        for ukaz in (["gio", "launch", pot] + [str(d) for d in datoteke],
                     ["gtk-launch", os.path.basename(pot)] + [str(d) for d in datoteke]):
            if shutil.which(ukaz[0]) is not None:
                try:
                    pid = varuh_procesov.zazeni_program(ukaz, zasebni_webkit.okolje_za_zunanje())
                    if pid:
                        return True
                except Exception:
                    pass
        info = Gio.DesktopAppInfo.new_from_filename(pot)
        if info is None:
            return False
        kontekst = zasebni_webkit.kontekst_za_zunanje(Gio, Gdk.Display.get_default().get_app_launch_context())
        kontekst.set_timestamp(_cas_dogodka() or Gdk.CURRENT_TIME)
        return bool(info.launch([Gio.File.new_for_path(d) for d in datoteke], kontekst))

    def _nedavne(self) -> list:
        izhod = []
        try:
            for e in _nedavni().get_items():
                if not e.exists() or not e.is_local():
                    continue
                pot = GLib.filename_from_uri(e.get_uri())[0]
                if os.path.isdir(pot):
                    continue
                cas = e.get_modified()          # GTK 3: int (time_t); novejsi: GLib.DateTime
                cas = cas.to_unix() if hasattr(cas, "to_unix") else int(cas or 0)
                try:
                    velikost = os.path.getsize(pot)
                except OSError:
                    velikost = 0
                izhod.append({"ime": e.get_display_name(), "pot": pot, "cas": cas, "spremenjeno": cas,
                              "velikost": velikost, "vrsta": os_datoteke.vrsta_datoteke(pot), "mapa": False})
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] nedavne:", e)
        izhod.sort(key=lambda d: -d["cas"])
        return izhod[:24]

    def _nedavne_pozabi(self, pot: str) -> bool:
        """Ena datoteka iz seznama nedavnih (datoteka sama ostane)."""
        if not pot or not os.path.isabs(pot):
            return False
        try:
            return bool(_nedavni().remove_item(GLib.filename_to_uri(pot, None)))
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] nedavne pozabi:", e)
            return False

    def _nedavne_pocisti(self) -> bool:
        try:
            _nedavni().purge_items()
            return True
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] nedavne pocisti:", e)
            return False

    # --- odprta okna (EWMH prek core/os_okna.py: samo X11, samo glavna nit; libwnck je GTK3 in ga v GTK4 ni)
    def _nasi_xid(self) -> set:
        """Okni Safeer OS (domaci zaslon, vrstica) v seznamu programov ne smeta biti."""
        nasi = set()
        for w in (self.okno, self.vrstica):
            if w is not None and x11.xid(w):
                nasi.add(x11.xid(w))
        return nasi

    def _odprta_okna(self) -> list:
        return os_okna.seznam(self._nasi_xid(), os_programi.MAPA_IKON)

    def _okno_dejanje(self, xid, dejanje: str) -> bool:
        return os_okna.dejanje(xid, dejanje, _cas_dogodka(self.okno))

    def _nastavitve_delov(self) -> dict:
        """Kateri deli Safeerja imajo nastavitve v Nastavitvah Safeer OS: Control (v tem procesu), Splet (WebKitov
        peskovnik dela) in namizje QML (lupina tece)."""
        izid = {"control": nastavitve_controla(), "splet": bool(self._peskovnik_na_voljo()),
                "namizje": self.lupina is not None, "sporocila": sporocila_vklop.sporocila_vklopljena()}
        if izid["namizje"]:
            # Iskalna lupa na namizju QML: zlozena (privzeto) ali vedno razsirjena - core/priljubljeno.py »lupa«. Glavna
            # nit: samo nastavitev, ne stanje() (stat vseh priljubljenih, zaklep, fsync - tests/test_nastavitve_delov.py).
            izid["lupa"] = self._priljubljeno().nastavitev("lupa")
        return izid

    def _nastavitev_dela(self, pogled, kljuc: str, vrednost=None):
        """Klik v skupinah Naprave in Link, Splet in Namizje (Nastavitve Safeer OS)."""
        if kljuc in _NASTAVITVE_CONTROLA:
            return nastavi_control(kljuc, bool(vrednost))
        if kljuc == "sporocila":
            return self._nastavi_sporocila(bool(vrednost))
        if kljuc == "lupa":
            # Stikalo »Zlozena iskalna lupa«: sprememba gre namizju kot dogodek »priljubljeno« (_priljubljeno). Shranjevanje
            # v ozadju, kot vsi klici priljubljeno* (stanje() pregleda priljubljene datoteke, _pisi naredi fsync).
            lupa = "zlozena" if vrednost else "razsirjena"
            threading.Thread(target=lambda: self._priljubljeno().nastavi("lupa", lupa), daemon=True,
                             name="safeer-lupa").start()
            return lupa == "zlozena"
        if kljuc == "mape":
            c = en_proces.control_app()
            if c is None:
                return False
            c.izberi_mape()
            return True
        if kljuc == "splet":
            # Isto okno kot »Nastavitve« v meniju Spleta (ena nastavitev za vse primerke Spleta: ConfigManager).
            # Splet se odpre, da je okno nad njim: v glavnem oknu ali, na delovni povrsini, v plosci na namizju.
            splet = self._spletni or getattr(self, "_spletni_namizje", None)
            if splet is None:
                if self.okno is not None and self.okno.get_visible():
                    self._splet("")
                    splet = self._spletni
                else:
                    self._splet_na_namizju("", domov=True)
                    splet = getattr(self, "_spletni_namizje", None)
            if splet is None:
                return False
            splet._nastavitve()
            return True
        if kljuc == "namizje" and self.lupina is not None:
            # »Prilagodi namizje« je na namizju QML (pod okni): okno z Nastavitvami se umakne, da je vidno.
            okno = pogled.get_root() if hasattr(pogled, "get_root") else None
            if isinstance(okno, Gtk.Window):
                okno.minimize()
            if okno is not self.okno:
                self._namizje()
            self.lupina.dogodek("prilagodi", {})
            return True
        return False

    def _namizje(self) -> bool:
        """Umakne Safeer OS in pokaze Mintovo namizje (vrne se s klikom v meniju ali na plosci)."""
        if self.okno is not None:
            self.okno.minimize()
        return True

    def _splet(self, naslov: str, nov_zavihek: bool = False) -> bool:
        """Odpre naslov v zavihku znotraj glavnega okna; brez procesa ali dodatnega okna.

        Samo http in https (velikost črk v shemi ni pomembna - telefonske tipkovnice pišejo »Https://«). Naslov, ki ga
        brskalnik ne bi odprl, zavrnemo, PREDEN lupino zožimo v način Splet. nov_zavihek: povezava od drugod
        (sporočilo) ne zamenja strani, ki jo ima uporabnik odprto v brskalniku."""
        if naslov:
            from core.config import normalize_web_url
            if not naslov.lower().startswith(("http://", "https://")) or not normalize_web_url(naslov):
                return False
        if self.okno is None or not self.okno.get_visible():
            # Glavnega okna ni ali je skrito (Safeer Cinnamon, Safeer Player, okna Zapiskov in Sporocil): stran odpre
            # Splet v svojem oknu v tem procesu, ne skrita lupina. Prej je sel vsak klic v privzeti brskalnik
            # (pregled celovitosti 15. 10. 2026); ta ostane samo brez peskovnika WebKit (_splet_na_namizju) ali na
            # izrecno zahtevo uporabnika (»Odpri v brskalniku«).
            return bool(naslov) and self._splet_na_namizju(naslov)
        if not self.okno.is_active():
            self.okno.present()
        if not self._pokazi_spletni_nacin():
            return False
        if not naslov:
            return True
        return self._spletni.odpri_povezavo(naslov) if nov_zavihek else self._spletni.odpri(naslov)

    #: Odjava znotraj Safeer OS (lastnik 17. 10. 2026): izbrisemo samo piskotke te storitve v seji Spleta.
    _ODJAVA_DOMENE = {"youtube": ("youtube.com",), "twitch": ("twitch.tv",), "spotify": ("spotify.com",)}

    def _odjava_storitve(self, storitev: str) -> bool:
        domene = self._ODJAVA_DOMENE.get(storitev)
        if not domene:
            return False
        seje = []
        for ime in ("_spletni", "_spletni_namizje"):
            spletni = getattr(self, ime, None)
            seja = getattr(spletni, "seja", None) if spletni is not None else None
            if seja is not None and seja not in seje:
                seje.append(seja)
        if not seje:
            # Splet v tem procesu se ni odprt: baze nihce nima odprte, piskotke te storitve izbrisemo neposredno.
            try:
                import sqlite3
                from core import youtube_racun
                povezava = sqlite3.connect(youtube_racun.pot_piskotkov(), timeout=2)
                try:
                    for d in domene:
                        povezava.execute("DELETE FROM moz_cookies WHERE host = ? OR host LIKE ?", (d, "%." + d))
                    povezava.commit()
                finally:
                    povezava.close()
                return True
            except Exception as e:  # noqa: BLE001
                print("[Safeer OS] odjava:", type(e).__name__, flush=True)
                return False
        for seja in seje:
            upravitelj = seja.get_website_data_manager()

            def ob_branju(u, rezultat, u2=upravitelj):
                try:
                    podatki = u2.fetch_finish(rezultat)
                except Exception:  # noqa: BLE001
                    return
                izbrani = [x for x in podatki if any(x.get_name() == d or x.get_name().endswith("." + d) for d in domene)]
                if izbrani:
                    u2.remove(WebKit2.WebsiteDataTypes.COOKIES, izbrani, None, None, None)
            upravitelj.fetch(WebKit2.WebsiteDataTypes.COOKIES, None, ob_branju, None)
        return True

    def _splet_konec_prijave(self, gostitelji: list) -> bool:
        """Po prijavi v YouTube/Twitch v Spletu (Medijski center jo zazna v piskotkih): zavihki strani za prijavo se
        zaprejo in v ospredje pride Safeer Player - gledanje gre v nas predvajalnik (lastnik 17. 10. 2026: po prijavi
        je Splet ostal odprt na youtube.com). Samo zavihki na danih gostiteljih; drugih zavihkov se ne dotaknemo."""
        gostitelji = [g.lower().strip(".") for g in gostitelji if g and "/" not in g][:6]
        if not gostitelji:
            return False

        def ujema(uri: str) -> bool:
            host = (urllib.parse.urlsplit(uri or "").hostname or "").lower()
            return any(host == g or host.endswith("." + g) for g in gostitelji)
        zaprto = 0
        for ime in ("_spletni_namizje", "_spletni"):
            spletni = getattr(self, ime, None)
            if spletni is None:
                continue
            for z in list(getattr(spletni, "zavihki", [])):
                try:
                    if ujema(z["pogled"].get_uri() or ""):
                        if len(spletni.zavihki) == 1 and ime == "_spletni_namizje":
                            spletni.odpri("")                      # zadnji zavihek: domaca stran, okno skrijemo
                            okno = getattr(self, "_plosca_spleta", None)
                            if okno is not None:
                                okno.set_visible(False)
                        else:
                            spletni.zapri_zavihek(z["pogled"])
                        zaprto += 1
                except Exception:  # noqa: BLE001
                    continue
        okno = getattr(self, "okno_predvajalnik", None)
        if okno is not None:
            okno.present()
        return zaprto > 0

    def _peskovnik_na_voljo(self) -> bool:
        """Ali se WebKitov peskovnik da zagnati (core.os_splet.peskovnik_dela). Brez njega Safeer OS ne ustvari
        NOBENEGA pogleda za tujo vsebino - ne vgrajenega brskalnika ne lahkega medijskega pogleda: WebKit bi ob prvem
        takem pogledu ubil ves Safeer OS.

        Pozitiven izid velja do konca teka. Negativen velja PESKOVNIK_PONOVNO_S sekund: ena prehodna napaka preverbe
        (pod obremenitvijo poteče) ne sme izklopiti Spleta do ponovnega zagona lupine, preverba (teče v glavni niti)
        pa tudi ne ob vsakem kliku."""
        if self._peskovnik_dela:
            return True
        if self._peskovnik_dela is False and time.monotonic() - self._peskovnik_preverjen < PESKOVNIK_PONOVNO_S:
            return False
        from core.os_splet import peskovnik_dela
        self._peskovnik_dela = bool(peskovnik_dela())
        self._peskovnik_preverjen = time.monotonic()
        if not self._peskovnik_dela:
            print("[Safeer OS] peskovnika (bubblewrap) ni mogoče zagnati - vgrajeni brskalnik in spletni "
                  "predvajalnik sta izklopljena")
        return self._peskovnik_dela

    def _ustvari_spletni(self) -> bool:
        """Ustvari vgrajeni brskalnik (ob prvem odpiranju Spleta). False: peskovnika ni mogoče zagnati - brskalnika
        ne ustvarimo (WebKit bi sicer ubil ves Safeer OS), uporabnik dobi pojasnilo."""
        if self._spletni is not None:
            return True
        from core.os_splet import VdelaniSplet
        if not self._peskovnik_na_voljo():
            self._dogodek("spletBrezPeskovnika", True)
            return False
        self._spletni = VdelaniSplet(Gtk, Gdk, Gio, GLib, WebKit2, KOREN, _jezik, _stanje_povezave_spleta,
                                     self._splet_v_zapisek, self.okno,
                                     stremio_dodatek=self._odpri_stremio_dodatek, config=self._config_spleta())
        # Povezava iz vgrajenega kanala Sporocil se odpre v Spletu (nacin Splet glavnega okna), ne v skritem zavihku.
        self._spletni.odpri_zunaj = lambda naslov: self._splet(naslov, True)
        # Podatki dodanih kanalov Sporocil (prijava, shramba) ostanejo pri brisanju Spleta - tudi ko so Sporocila izklopljena.
        self._spletni.zasciteni_podatki = self._kanali().zasciteni
        self._spletni.gradnik.set_hexpand(True)
        self._spletni.gradnik.set_vexpand(True)
        self._spletni.gradnik.set_visible(False)       # GTK4: skrit, dokler uporabnik ne odpre Spleta
        self._glavna_postavitev.append(self._spletni.gradnik)
        return True

    def _pokazi_spletni_nacin(self) -> bool:
        """Najprej izmeri #stranska, sele nato doda nacin-splet in zozi HTML lupino. V nacinu Splet je vrstica vedno
        razsirjena (trak bi bil ozji od gumbov za razdelke): meri se razsirjena, ne trak - prej je skrcena vrstica dala
        rezervnih 375 px, siroka pa 250-300 px (19. 10. 2026)."""
        if not self._ustvari_spletni():
            return False
        self._spletni_nacin = True
        koda = (
            "(function(){var s=document.getElementById('stranska'),b=document.body;"
            "if(!b.classList.contains('nacin-splet'))b.classList.remove('vrstica-skrcena','vrstica-plava');"
            "var w=b.classList.contains('nacin-splet')?Number(b.dataset.stranska||0):"
            "(s?s.getBoundingClientRect().width:0);b.dataset.stranska=String(w);"
            "b.classList.add('nacin-splet');"
            "document.querySelectorAll('#meni button').forEach(function(x){x.classList.toggle('izbran',x.getAttribute('data-razdelek')==='splet');});"
            "return w*(window.devicePixelRatio||1);})()"
        )

        def izmerjeno(pogled, rezultat):
            if not self._spletni_nacin:
                return
            try:
                sirina = round(pogled.evaluate_javascript_finish(rezultat).to_double())
            except Exception:
                sirina = 300
            if sirina < 160:
                sirina = 375
            self.pogled.set_size_request(sirina, -1)
            # Lupina se v Box razteza (hexpand); v nacinu Splet mora ostati le stranska vrstica.
            self.pogled.set_hexpand(False)
            # WebKitWebView kot naravno sirino javi zadnjo dodelitev, zato Box lupine ne bi zozil:
            # brskalniku dodelimo preostanek okna (in ga uskladimo ob vsaki spremembi velikosti okna).
            # JS vrne sirino v fizicnih pikslih (CSS * devicePixelRatio, npr. besedilo 1,5x); GTK hoce logicne.
            try:
                sirina = round(sirina / max(1, int(self.pogled.get_scale_factor() or 1)))
            except Exception:
                pass
            self.pogled.set_size_request(sirina, -1)
            self._sirina_stranske = sirina
            self._uskladi_sirino_spleta()
            self._spletni.gradnik.set_visible(True)
            # Lupina se je zožila, brskalnik je dobil svoj del okna. Brez izrecnega izrisa je ob prvem odpiranju iz
            # drugega razdelka del orodne vrstice brskalnika ostal neizrisan (videli so se ostanki lupine), dokler
            # se ni spremenila velikost okna. Izmerjeno v preizkusni seji brez sestavljalnika, 7. 10. 2026.
            GLib.timeout_add(60, self._izrisi_okno)
            GLib.timeout_add(450, self._izrisi_okno)

        self.pogled.evaluate_javascript(koda, -1, None, None, None, izmerjeno)
        return True

    def _izrisi_okno(self) -> bool:
        if self.okno is not None:
            self.okno.queue_draw()
        return False

    def _uskladi_sirino_spleta(self, *_):
        if not self._spletni_nacin or self._spletni is None or self.okno is None:
            return False
        skupaj = self.okno.get_width()
        stranska = int(getattr(self, "_sirina_stranske", 300) or 300)
        self._spletni.gradnik.set_size_request(max(360, skupaj - stranska), -1)
        povrsina = self.okno.get_surface()
        if povrsina is not None and getattr(self, "_splet_povezan_resize", None) is not povrsina:
            # GTK4 nima signala size-allocate: velikost okna sporoci njegova povrsina (Gdk.Surface width).
            self._splet_povezan_resize = povrsina
            povrsina.connect("notify::width", lambda *a: GLib.idle_add(self._uskladi_sirino_spleta))
        return False

    def _skrij_spletni_nacin(self, razdelek: str = "domov") -> bool:
        self._spletni_nacin = False
        if self._spletni is not None:
            self._spletni.gradnik.set_visible(False)
        self.pogled.set_size_request(-1, -1)
        self.pogled.set_hexpand(True)
        if self._spletni is not None:
            self._spletni.gradnik.set_size_request(-1, -1)
        self._js("document.body.classList.remove('nacin-splet');")
        return True

    def _razdelek(self, razdelek: str) -> bool:
        if razdelek == "splet":
            return self._pokazi_spletni_nacin()
        if self._spletni_nacin:
            self._skrij_spletni_nacin(razdelek)
        return True

    def vrniSplet(self) -> bool:  # noqa: N802 - enako javno ime kot na drugih izdajah Safeer OS
        return self._pokazi_spletni_nacin()

    def _splet_v_zapisek(self, naslov: str, url: str) -> None:
        vsebina = "[%s](%s)" % (naslov.replace("]", ""), url)
        zapisek = self.zapiski.shrani("", naslov, vsebina, None)
        self._skrij_spletni_nacin("zapiski")
        self._js("window.safeerOsPojdi && window.safeerOsPojdi('zapiski');")
        self._dogodek("zapisek", zapisek)

    def _medij(self, naslov: str) -> bool:
        """Safeer Media: neposredni tok, nato lahek WebKit, šele nazadnje brskalnik."""
        nivo = os_mediji.izberi_nivo(naslov)
        if not nivo:
            return False
        if nivo == "neposredno":
            return self._predvajaj_neposredno(naslov)
        return self._odpri_lahki_medijski_pogled(naslov)

    @staticmethod
    def _nalozi_gstreamer():
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst  # noqa: WPS433
        Gst.init(None)
        return Gst

    def _predvajaj_neposredno(self, naslov: str, vrsta: str = "medij", prikazi: bool = True,
                             ime: str = "", zacetek: int = 0, seznam=None, zacni: int = 0,
                             v_premoru: bool = False) -> bool:
        """Neposredni medij doda v čakalno vrsto domačega predvajalnika."""
        self._pocisti_medijski_pogled()
        try:
            self._shrani_medijski_napredek()
            Gst = self._medijski_gst or self._nalozi_gstreamer()
            self._medijski_gst = Gst
            if self._medijski_predvajalnik is None:
                self._medijski_predvajalnik = os_predvajalnik.Predvajalnik(
                    Gst, self._osvezi_medijski_predvajalnik, self._medijski_konec)
                from core import podnapisi as _pn
                self._medijski_predvajalnik.nastavitve_podnapisov = _pn.nalozi_nastavitve()
                self._medijski_predvajalnik.shrani_podnapise = _pn.shrani_nastavitve
                self._medijski_predvajalnik.jezik_sistema = _pn.jezik_sistema()
                self._medijski_predvajalnik.pripravi_podnapis = _pn.pripravi
                # Jezik zvoka in izenacevalnik (kot v Kodiju): shranjena izbira velja od prvega posnetka naprej.
                from core import predvajalnik_moznosti as _pm
                self._medijski_predvajalnik.moznosti = _pm.nalozi()
                self._medijski_predvajalnik.shrani_moznosti = _pm.shrani
                self._medijski_predvajalnik.nastavi_izenacevalnik(self._medijski_predvajalnik.moznosti["izenacevalnik"],
                                                                  shrani=False)
                self._medijski_predvajalnik.v_glavni = lambda f: GLib.idle_add(f)
                self._povezi_zakasnitev_zvocnika()
                self._medijski_predvajalnik.zakasni = lambda ms, f: GLib.timeout_add(ms, f)
                # Naslov, ki se ne odpre z nobeno razlicico: Medijski center ga ne ponuja vec (brez nedelujocih ikon).
                self._medijski_predvajalnik.neuspeh = lambda s: self._katalog is not None and self._katalog.predvajanje_ni_uspelo(s.uri)
                if not self._medijski_tik_zacet:
                    self._medijski_tik_zacet = True
                    GLib.timeout_add_seconds(1, self._medijski_tik)
            if self._medijski_predvajalnik_okno is None:
                self._ustvari_okno_videa(Gst)
            if seznam:
                uspesno = self._medijski_predvajalnik.zamenjaj_vrsto(seznam, zacni)
            else:
                self._medijski_predvajalnik.dodaj(naslov, predvajaj=True, vrsta=vrsta,
                                                  naslov=ime, zacetek=zacetek, v_premoru=v_premoru)
                uspesno = self._medijski_predvajalnik.stanje != "napaka"
            if prikazi:
                self._medijski_predvajalnik_okno.present()
            else:
                self._medijski_predvajalnik_okno.set_visible(False)
            return uspesno
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] neposredni medij:", e)
            self._ustavi_neposredni_medij()
            # Lokalni varni tok (127.0.0.1/m/<skrivnost>) ni spletna stran: ne v brskalnik in ne v zgodovino.
            return self._splet(naslov) if vrsta == "medij" and naslov.startswith(("http://", "https://")) \
                and not naslov.startswith("http://127.0.0.1:") else False

    def _ustvari_okno_videa(self, Gst) -> None:
        """Okno domacega predvajalnika (GStreamer): slika, napis, drsnik, gumbi in cakalna vrsta."""
        okno = Gtk.Window(title="Safeer Player")
        # Okno z videom je del Safeer Playerja: v pultu je v njegovi skupini, z njegovo ikono.
        x11.nastavi_razred(okno, *WMCLASS_PREDVAJALNIKA)
        self._ikona_predvajalnika(okno)
        okno.add_css_class("safeer-player")
        if self._medijski_css is None:
            try:
                self._medijski_css = _css("""
                    window.safeer-player { background: #0b1424; color: #eaf2ff; }
                    window.safeer-player label { color: #eaf2ff; }
                    window.safeer-player label.safeer-player-title { font-size: 18px; font-weight: 700; }
                    window.safeer-player label.safeer-player-queue { color: #afbed4; }
                    window.safeer-player label.safeer-player-note { font-size: 96px; color: #8ac7ff; }
                    window.safeer-player button { background: #16233a; color: #eaf2ff;
                        border: 1px solid rgba(211,229,255,.23); border-radius: 10px; padding: 8px 13px; }
                    window.safeer-player button:hover { background: #243e63; border-color: #8ac7ff; }
                    window.safeer-player scale highlight { background: #8ac7ff; }
                    window.safeer-player scale slider { background: #8ac7ff;
                        min-width: 14px; min-height: 14px; margin: -6px; }
                    window.safeer-player label.safeer-player-osd { background: rgba(11,20,36,.86); color: #eaf2ff;
                        border: 1px solid rgba(211,229,255,.23); border-radius: 10px; padding: 8px 14px;
                        font-size: 16px; font-weight: 700; }
                    window.safeer-player popover > contents { background: #0f1b2e; color: #eaf2ff; }
                    window.safeer-player popover label.safeer-player-heading { color: #afbed4; font-weight: 700; }
                    window.safeer-player popover checkbutton { color: #eaf2ff; padding: 4px 6px; }
                    window.safeer-player popover checkbutton:focus-visible,
                    window.safeer-player popover button:focus-visible { outline: 2px solid #8ac7ff; }
                """)
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] slog predvajalnika:", e)
        # Na velikih zaslonih 960x620 deluje kot sličica; okno naj zavzame približno dve tretjini.
        zaslon = self._zaslon_za_okno()
        g = self._delovno_obmocje(zaslon) if zaslon else None
        okno.set_default_size(max(960, int(g.width * 0.62)) if g else 960,
                              max(620, int(g.height * 0.7)) if g else 620)
        # Brez glavnega okna (predvajanje iz Safeer Playerja) je nad oknom Safeer Player; GTK4 nima
        # set_position(CENTER_ON_PARENT) - prehodno okno postavi upravitelj oken nad starsa.
        okno.set_transient_for(self.okno or self.okno_predvajalnik)
        okno.connect("close-request", lambda *a: (self._ustavi_neposredni_medij(), True)[1])
        _tipke(okno, self._medijska_tipka, zajem=True)    # presledek je premor, tudi ko ima fokus gumb
        postavitev = _robovi_gradnika(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8), 16)
        # Glasba nima slike: namesto črnega polja pokažemo znak in naslov (sklad preklopi ob osvežitvi).
        self._medijski_sklad = Gtk.Stack()
        self._medijski_sklad.set_vexpand(True)
        self._medijski_sklad.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        zvok = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER)
        znak = Gtk.Label(label="♫")
        znak.add_css_class("safeer-player-note")
        self._medijski_zvok_naslov = Gtk.Label()
        self._medijski_zvok_naslov.add_css_class("safeer-player-title")
        self._medijski_zvok_naslov.set_wrap(True)
        self._medijski_zvok_naslov.set_justify(Gtk.Justification.CENTER)
        zvok.append(znak)
        zvok.append(self._medijski_zvok_naslov)
        self._medijski_sklad.add_named(zvok, "zvok")
        # GTK4: gtksink (GTK3) ne gre; gtk4paintablesink (gst-plugins-rs) da Gdk.Paintable za Gtk.Picture. Brez
        # njega playbin izbere autovideosink: video je v svojem oknu, tu ostane napis in upravljanje.
        ponor = Gst.ElementFactory.make("gtk4paintablesink", "safeer-media-video")
        if ponor is not None:
            self._medijski_predvajalnik.element.set_property("video-sink", ponor)
            slika = Gtk.Picture.new_for_paintable(ponor.get_property("paintable"))
            slika.set_hexpand(True)
            slika.set_vexpand(True)
            # Dvojni klik na sliko preklopi cel zaslon (kot v VLC in mpv).
            klik = Gtk.GestureClick()
            klik.connect("pressed", lambda _k, n, _x, _y: n == 2 and self._medijski_cel_zaslon(okno))
            slika.add_controller(klik)
            self._medijski_sklad.add_named(slika, "slika")
        else:
            print("[SafeerOS] gtk4paintablesink ni namescen: video v svojem oknu (autovideosink)", flush=True)
        # OSD (zamik, zvocni posnetek, podnapisi): kratko besedilo v kotu slike, kot v Kodiju in VLC.
        prekrivanje = Gtk.Overlay()
        prekrivanje.set_vexpand(True)
        prekrivanje.set_child(self._medijski_sklad)
        self._medijski_osd = Gtk.Label(halign=Gtk.Align.END, valign=Gtk.Align.START)
        self._medijski_osd.add_css_class("safeer-player-osd")
        self._medijski_osd.set_margin_top(16)
        self._medijski_osd.set_margin_end(16)
        self._medijski_osd.set_can_target(False)
        self._medijski_osd.set_visible(False)
        prekrivanje.add_overlay(self._medijski_osd)
        postavitev.append(prekrivanje)
        self._medijski_napis = Gtk.Label(xalign=0)
        self._medijski_napis.add_css_class("safeer-player-title")
        postavitev.append(self._medijski_napis)
        premik = Gtk.Box(spacing=10)
        self._medijski_drsnik = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 1)
        self._medijski_drsnik.set_draw_value(False)
        self._medijski_drsnik.set_hexpand(True)
        self._medijski_drsnik.set_tooltip_text(self._mb("premik"))
        self._medijski_drsnik.connect("change-value", self._medijski_premik)
        # GTK4: ni button-press/release-event. Surovi dogodki v fazi zajema (EventControllerLegacy) - drsnikova
        # lastna kretnja jih ne prevzame, zato spust vedno pride (GestureClick bi jo drsnik preklical).
        miska = Gtk.EventControllerLegacy()
        miska.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        miska.connect("event", self._medijski_miska_drsnika)
        self._medijski_drsnik.add_controller(miska)
        premik.append(self._medijski_drsnik)
        self._medijski_cas = Gtk.Label(label="0:00 / 0:00")
        premik.append(self._medijski_cas)
        postavitev.append(premik)
        gumbi = Gtk.Box(spacing=8)
        for napis_gumba, dejanje in (("＋ " + self._mb("dodaj_datoteke"), self._medijski_dodaj_datoteke),
                                      ("⏮ " + self._mb("prejsnja"), lambda: self._medijski_ukaz("prejsnja")),
                                      ("⏭ " + self._mb("naslednja"), lambda: self._medijski_ukaz("naslednja"))):
            gumb = Gtk.Button(label=napis_gumba)
            gumb.connect("clicked", lambda _g, ukaz=dejanje: ukaz())
            gumbi.append(gumb)
        self._medijski_premor = Gtk.Button(label="⏸ " + self._mb("premor"))
        self._medijski_premor.connect("clicked", lambda _g: self._medijski_ukaz("premor"))
        gumbi.append(self._medijski_premor)
        presledek = Gtk.Box()
        presledek.set_hexpand(True)
        gumbi.append(presledek)        # GTK3 pack_end: gumbi spodaj desno, v istem vrstnem redu
        celozaslonsko = Gtk.Button(label="⛶ " + self._mb("cel_zaslon"))
        celozaslonsko.connect("clicked", lambda _g: self._medijski_cel_zaslon(okno))
        gumbi.append(celozaslonsko)
        # "Poslji na napravo": kar igra tu, drugi napravi v Linku - tam caka tiho Sprejmi/Zavrni, tu igra naprej.
        poslji = Gtk.Button(label="📤 " + self._mb("poslji"))
        poslji.connect("clicked", self._medijski_poslji_meni)
        gumbi.append(poslji)
        # »Predvajaj na …« (kot v mini predvajalniku): ta racunalnik, naprava v Linku ali zvocnik v omrezju.
        self._medijski_izhod = Gtk.Button(label="🔈 " + self._mb("predvajaj_na"))
        self._medijski_izhod.connect("clicked", self._medijski_meni_izhoda)
        gumbi.append(self._medijski_izhod)
        # Podnapisi (kot v VLC): izklop, vgrajeni tokovi in datoteke ob videu; tipka V jih preklaplja.
        self._medijski_podnapisi = Gtk.Button(label="💬 " + self._mb("podnapisi"))
        self._medijski_podnapisi.set_visible(False)
        self._medijski_podnapisi.connect("clicked", self._medijski_meni_podnapisov)
        self._medijski_podnapisi.set_tooltip_text(self._mb("podnapisi") + " (V) · " + self._mb("zamik_podnapisov") + " (G / H)")
        gumbi.append(self._medijski_podnapisi)
        # Zvok (kot v Kodiju): zvocni posnetek, zamik zvoka in izenacevalnik; tipka Menu na daljincu ga odpre.
        self._medijski_zvok = Gtk.Button(label="🔊 " + self._mb("zvok"))
        self._medijski_zvok.set_visible(False)
        self._medijski_zvok.connect("clicked", self._medijski_meni_zvoka)
        self._medijski_zvok.set_tooltip_text(self._mb("zvocni_posnetek") + " (B) · " + self._mb("zamik_zvoka") + " (J / K)")
        gumbi.append(self._medijski_zvok)
        postavitev.append(gumbi)
        self._medijski_vrsta = Gtk.Label(xalign=0)
        self._medijski_vrsta.add_css_class("safeer-player-queue")
        self._medijski_vrsta.set_wrap(True)
        postavitev.append(self._medijski_vrsta)
        okno.set_child(postavitev)
        self.add_window(okno)
        self._medijski_predvajalnik_okno = okno

    def _medijski_miska_drsnika(self, _kontroler, dogodek) -> bool:
        if dogodek is None:       # GTK ob odprtju okenca (popover) poslje dogodek brez podatkov
            return False
        vrsta = dogodek.get_event_type()
        if vrsta == Gdk.EventType.BUTTON_PRESS:
            self._medijski_zacni_premik(self._medijski_drsnik, dogodek)
        elif vrsta == Gdk.EventType.BUTTON_RELEASE and self._medijski_vlecem:
            # Po privzeti obdelavi spusta (GTK3 connect_after): drsnik ima ze koncno vrednost.
            GLib.idle_add(lambda: (self._medijski_spusti_premik(self._medijski_drsnik, dogodek), False)[1])
        return False

    def _ustavi_neposredni_medij(self) -> None:
        if self._medijski_predvajalnik is not None:
            try:
                self._shrani_medijski_napredek()
                self._medijski_predvajalnik.ustavi()
                self._dogodek("medijskaKnjiznica", None)
            except Exception:
                pass
        if self._medijski_predvajalnik_okno is not None:
            self._medijski_predvajalnik_okno.set_visible(False)

    def _mpris_podatki(self) -> dict:
        """Stanje predvajalnika za sistem: kot za stran, z izvajalcem in sliko iz kataloga, ce ju ta pozna."""
        p = dict(self._medijski_podatki())
        for kljuc in ("izvajalec", "slika"):
            p[kljuc] = p.get(kljuc) or ""
        p["vrstaStrani"] = bool(p.get("vrstaStrani"))
        return p

    def _mpris_osvezi(self) -> None:
        """Sistemu (medijske tipke, slusalke, Cinnamonov zvocni applet) pove, kaj igra domaci predvajalnik."""
        if self._mpris is False:
            return
        try:
            if self._mpris is None:
                from core import os_mpris
                vodilo = self.get_dbus_connection() or Gio.bus_get_sync(Gio.BusType.SESSION, None)
                self._mpris = os_mpris.Mpris(vodilo, self._mpris_podatki, self._medijski_ukaz)
            self._mpris.osvezi()
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] MPRIS:", e, flush=True)
            self._mpris = False

    def _osvezi_medijski_predvajalnik(self) -> None:
        servis = self._medijski_predvajalnik
        if servis is not None:
            self._mpris_osvezi()
        if servis is None or self._medijski_napis is None:
            return
        naslov = servis.trenutna.naslov if servis.trenutna else self._mb("nic")
        if servis.trenutna and servis.trenutna.vrsta in ("tv", "radio"):
            naslov = "● " + self._mb("v_zivo") + " · " + naslov
        self._medijski_napis.set_text(naslov + (" · " + self._mb(servis.napaka)
                                                     if servis.napaka else ""))
        self._medijski_premor.set_label("▶ " + self._mb("nadaljuj") if servis.stanje == "premor" else "⏸ " + self._mb("premor"))
        self._osvezi_medijski_sklad()
        naprej = [v.naslov for v in servis.vrsta[servis.indeks + 1:servis.indeks + 6]]
        self._medijski_vrsta.set_text(self._mb("cakalna_vrsta") + ": " + "  ·  ".join(naprej) if naprej else "")
        podatki = self._medijski_podatki()
        video = podatki.get("vrsta") == "video" or (servis.trenutna is not None and self._medij_ima_sliko())
        if getattr(self, "_medijski_podnapisi", None) is not None:
            # Video ima vedno vsaj »Naloži iz datoteke«, zato je gumb viden ob vsakem videu.
            self._medijski_podnapisi.set_visible(bool(podatki.get("podnapisi")) and podatki.get("vrsta") == "video" or
                                                 bool(video) and servis.trenutna is not None and not servis.je_dvd())
        if getattr(self, "_medijski_zvok", None) is not None:
            self._medijski_zvok.set_visible(servis.trenutna is not None and self._medijske_moznosti_zvoka())
        self._osvezi_medijski_drsnik(podatki)
        self._dogodek("predvajalnik", podatki)

    def _ime_podnapisa(self, m: dict) -> str:
        from core import podnapisi as _pn
        jezik = m.get("jezik") or ""
        ime = _pn.ime_jezika(jezik, _jezik()) if jezik else ""
        if m.get("vgrajeni"):
            return " · ".join(x for x in (ime, self._mb("podnapisi_vgrajeni")) if x) or self._mb("podnapisi_v_videu")
        return " · ".join(x for x in (ime, m.get("oznaka") or "") if x) or str(m.get("ime") or "")

    def _medijski_meni_podnapisov(self, gumb) -> None:
        """Podnapisi (kot v Kodiju): izbira toka, zamik, nalaganje iz datoteke in s spleta - vse s tipkovnico in daljincem."""
        servis = self._medijski_predvajalnik
        if servis is None:
            return
        self._medijsko_okence(gumb, self._medijska_plosca_podnapisov)

    def _medijska_plosca_podnapisov(self, okence) -> "Gtk.Widget":
        servis = self._medijski_predvajalnik
        plosca = self._medijska_plosca()
        stanje = servis.podnapisi()
        moznosti = [("izklop", self._mb("podnapisi_izklop"))] + [(m["kljuc"], self._ime_podnapisa(m)) for m in stanje["moznosti"]]
        plosca.append(self._medijski_naslov_plosce(self._mb("podnapisi")))
        self._medijske_izbire(plosca, moznosti, stanje["izbran"],
                              lambda kljuc: (servis.izberi_podnapise(kljuc),
                                             self._medijski_osd_pokazi(self._mb("podnapisi") + ": " + dict(moznosti).get(kljuc, ""))))
        if not servis.je_dvd():
            plosca.append(self._medijski_zamik_vrstica("podnapisi"))
            datoteka = Gtk.Button(label="📂 " + self._mb("podnapisi_datoteka"))
            datoteka.connect("clicked", lambda _g: (okence.popdown(), self._medijski_podnapisi_iz_datoteke()))
            plosca.append(datoteka)
            if self._medijski_id_podnapisov():
                splet = Gtk.Button(label="🌐 " + self._mb("podnapisi_splet"))
                splet.connect("clicked", lambda _g: self._medijski_podnapisi_splet(okence))
                plosca.append(splet)
        return plosca

    def _medijski_meni_zvoka(self, gumb) -> None:
        if self._medijski_predvajalnik is None:
            return
        self._medijsko_okence(gumb, self._medijska_plosca_zvoka)

    def _medijske_moznosti_zvoka(self) -> bool:
        """Ali ima okence Zvok kaj pokazati (vec zvocnih posnetkov, zamik ob videu ali izenacevalnik)."""
        servis = self._medijski_predvajalnik
        if servis is None or servis.trenutna is None:
            return False
        try:
            vec_zvokov = int(servis.element.get_property("n-audio") or 0) > 1
        except Exception:  # noqa: BLE001
            vec_zvokov = False
        return vec_zvokov or servis.izenacevalnik is not None or self._medij_ima_sliko()

    def _medijska_plosca_zvoka(self, okence) -> "Gtk.Widget":
        from core import predvajalnik_moznosti as _pm
        servis = self._medijski_predvajalnik
        plosca = self._medijska_plosca()
        toki = servis.zvocni_toki(_jezik(), self._mb("zvok_st"))
        if len(toki["moznosti"]) > 1:
            plosca.append(self._medijski_naslov_plosce(self._mb("zvocni_posnetek")))
            imena = {m["kljuc"]: m["ime"] for m in toki["moznosti"]}
            self._medijske_izbire(plosca, [(m["kljuc"], m["ime"]) for m in toki["moznosti"]], toki["izbran"],
                                  lambda i: (servis.izberi_zvok(i), self._medijski_osd_pokazi(
                                      self._mb("zvocni_posnetek") + ": " + imena.get(i, ""))))
        if self._medij_ima_sliko():
            plosca.append(self._medijski_zamik_vrstica("zvok"))
        if servis.izenacevalnik is not None:
            plosca.append(self._medijski_naslov_plosce(self._mb("izenacevalnik")))
            izbire = list(_pm.IZBIRE_IZENACEVALNIKA)
            seznam = Gtk.DropDown.new_from_strings([self._mb("eq_" + i) for i in izbire])
            trenutna = servis.moznosti.get("izenacevalnik", "ravno")
            seznam.set_selected(izbire.index(trenutna) if trenutna in izbire else 0)
            plosca.append(seznam)
            drsniki = self._medijski_drsniki_izenacevalnika()
            drsniki.set_visible(trenutna == _pm.PO_MERI)
            plosca.append(drsniki)

            def izbrano(dd, _p) -> None:
                izbira = izbire[dd.get_selected()] if 0 <= dd.get_selected() < len(izbire) else "ravno"
                servis.nastavi_izenacevalnik(izbira)
                drsniki.set_visible(izbira == _pm.PO_MERI)
                self._medijski_osd_pokazi(self._mb("izenacevalnik") + ": " + self._mb("eq_" + izbira))
            seznam.connect("notify::selected", izbrano)
        return plosca

    def _medijski_drsniki_izenacevalnika(self) -> "Gtk.Widget":
        """Deset navpicnih drsnikov (Po meri): -12..+12 dB, puscici gor/dol premikata izbrani pas za 1 dB."""
        from core import predvajalnik_moznosti as _pm
        servis = self._medijski_predvajalnik
        vrsta = Gtk.Box(spacing=4)
        vrednosti = list(_pm.ojacitve(_pm.PO_MERI, servis.moznosti.get("po_meri")))
        cakam = {"id": 0}

        def shrani() -> bool:
            cakam["id"] = 0
            servis.shrani_moznosti(dict(servis.moznosti))
            return False

        for i, pas in enumerate(_pm.PASOVI):
            stolpec = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            drsnik = Gtk.Scale.new_with_range(Gtk.Orientation.VERTICAL, _pm.NAJMANJ_DB, _pm.NAJVEC_DB, 1)
            drsnik.set_inverted(True)            # gor = glasneje
            drsnik.set_draw_value(False)
            drsnik.set_size_request(-1, 120)
            drsnik.set_value(vrednosti[i])
            drsnik.set_tooltip_text("%s Hz" % pas)
            drsnik.update_property([Gtk.AccessibleProperty.LABEL], ["%s %s Hz" % (self._mb("izenacevalnik"), pas)])

            def premik(d, k=i) -> None:
                vrednosti[k] = round(d.get_value())
                servis.nastavi_izenacevalnik(_pm.PO_MERI, vrednosti, shrani=False)
                if not cakam["id"]:              # na disk sele, ko uporabnik neha premikati
                    cakam["id"] = GLib.timeout_add(600, shrani)
            drsnik.connect("value-changed", premik)
            stolpec.append(drsnik)
            oznaka = Gtk.Label(label=pas)
            oznaka.add_css_class("dim-label")
            stolpec.append(oznaka)
            vrsta.append(stolpec)
        return vrsta

    @staticmethod
    def _medijska_plosca() -> "Gtk.Box":
        plosca = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        return _robovi_gradnika(plosca, 10)

    @staticmethod
    def _medijski_naslov_plosce(besedilo: str) -> "Gtk.Label":
        naslov = Gtk.Label(label=besedilo, xalign=0)
        naslov.add_css_class("safeer-player-heading")
        return naslov

    @staticmethod
    def _medijske_izbire(plosca, moznosti: list, izbran, izberi: Callable) -> None:
        """Izbira ene moznosti (radijski gumbi): puscice in preslednica, kot v vsakem dialogu GTK."""
        prvi = None
        for kljuc, napis in moznosti:
            gumb = Gtk.CheckButton(label=napis)
            if prvi is None:
                prvi = gumb
            else:
                gumb.set_group(prvi)
            gumb.set_active(kljuc == izbran)
            gumb.connect("toggled", lambda g, k=kljuc: g.get_active() and izberi(k))
            plosca.append(gumb)

    def _medijski_zamik_vrstica(self, vrsta: str) -> "Gtk.Widget":
        """»Zamik zvoka  −100 ms  +150 ms  +100 ms  Ponastavi« - gumbi menija premikajo za 100 ms, tipke za 50 ms."""
        from core import predvajalnik_moznosti as _pm
        servis = self._medijski_predvajalnik
        okvir = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        ime = self._mb("zamik_zvoka" if vrsta == "zvok" else "zamik_podnapisov")
        tipke = "J / K" if vrsta == "zvok" else "G / H"
        okvir.append(self._medijski_naslov_plosce("%s (%s)" % (ime, tipke)))
        vrstica = Gtk.Box(spacing=6)
        vrednost = Gtk.Label(label=_pm.besedilo_zamika(servis.zamik_zvoka if vrsta == "zvok" else servis.zamik_podnapisov))
        vrednost.set_width_chars(9)

        def premakni(korak: int) -> None:
            ms = servis.nastavi_zamik(vrsta, 0) if korak == 0 else servis.premakni_zamik(vrsta, korak)
            vrednost.set_text(_pm.besedilo_zamika(ms))
            self._medijski_osd_pokazi("%s: %s" % (ime, _pm.besedilo_zamika(ms)))
        for napis, korak in (("−%d ms" % _pm.KORAK_MENI_MS, -_pm.KORAK_MENI_MS), (None, 0),
                             ("+%d ms" % _pm.KORAK_MENI_MS, _pm.KORAK_MENI_MS)):
            if napis is None:
                vrstica.append(vrednost)
                continue
            gumb = Gtk.Button(label=napis)
            gumb.update_property([Gtk.AccessibleProperty.LABEL], ["%s %s" % (ime, napis)])
            gumb.connect("clicked", lambda _g, k=korak: premakni(k))
            vrstica.append(gumb)
        ponastavi = Gtk.Button(label="↺ " + self._mb("ponastavi"))
        ponastavi.update_property([Gtk.AccessibleProperty.LABEL], ["%s: %s" % (ime, self._mb("ponastavi"))])
        ponastavi.connect("clicked", lambda _g: premakni(0))
        vrstica.append(ponastavi)
        okvir.append(vrstica)
        return okvir

    def _medijsko_okence(self, gumb, zgradi: Callable) -> None:
        """Okence pod gumbom z nastavitvami (Gtk.Popover): vsebino zgradi zgradi(okence); fokus na prvi moznosti,
        da daljinec in tipkovnica takoj delujeta."""
        stari = getattr(gumb, "_safeer_meni", None)
        if stari is not None:
            stari.unparent()
        okence = Gtk.Popover()
        okence.set_parent(gumb)
        okence.set_position(Gtk.PositionType.TOP)
        okence.set_has_arrow(False)
        gumb._safeer_meni = okence
        okence.set_child(zgradi(okence))
        self._medijska_okenca = [o for o in getattr(self, "_medijska_okenca", []) if o is not stari] + [okence]
        okence.popup()
        self._medijski_fokus_okenca(okence)

    @staticmethod
    def _medijski_fokus_okenca(okence) -> None:
        """Fokus na izbrani moznosti (daljinec: puscici takoj premikata izbiro), sicer na prvem gumbu."""
        def isci(g):
            while g is not None:
                if isinstance(g, Gtk.CheckButton) and g.get_active():
                    return g
                najden = isci(g.get_first_child())
                if najden is not None:
                    return najden
                g = g.get_next_sibling()
            return None
        izbran = isci(okence.get_child())
        if izbran is None or not izbran.grab_focus():
            okence.child_focus(Gtk.DirectionType.TAB_FORWARD)

    def _medijsko_okence_odprto(self) -> bool:
        return any(o.get_visible() for o in getattr(self, "_medijska_okenca", []))

    def _medijski_osd_pokazi(self, besedilo: str) -> None:
        """Kratko besedilo v kotu slike za 2 s (zamik, posnetek, podnapisi)."""
        osd = getattr(self, "_medijski_osd", None)
        if osd is None:
            return
        osd.set_text(besedilo)
        osd.set_visible(True)
        if getattr(self, "_medijski_osd_cas", 0):
            GLib.source_remove(self._medijski_osd_cas)

        def skrij() -> bool:
            self._medijski_osd_cas = 0
            osd.set_visible(False)
            return False
        self._medijski_osd_cas = GLib.timeout_add(2000, skrij)

    def _medijski_zamik_tipka(self, vrsta: str, korak: int) -> bool:
        from core import predvajalnik_moznosti as _pm
        servis = self._medijski_predvajalnik
        if servis is None or servis.trenutna is None or not self._medij_ima_sliko():
            return False
        ms = servis.premakni_zamik(vrsta, korak)
        self._medijski_osd_pokazi("%s: %s" % (self._mb("zamik_zvoka" if vrsta == "zvok" else "zamik_podnapisov"),
                                              _pm.besedilo_zamika(ms)))
        return True

    def _medijski_naslednji_zvok(self) -> bool:
        servis = self._medijski_predvajalnik
        if servis is None:
            return False
        i = servis.naslednji_zvok()
        if i < 0:
            return False
        ime = next((m["ime"] for m in servis.zvocni_toki(_jezik(), self._mb("zvok_st"))["moznosti"] if m["kljuc"] == i), "")
        self._medijski_osd_pokazi(self._mb("zvocni_posnetek") + ": " + ime)
        return True

    # ------------------------------------------------------------------ podnapisi iz datoteke in s spleta

    def _medijski_podnapisi_iz_datoteke(self) -> None:
        servis = self._medijski_predvajalnik
        if servis is None or servis.trenutna is None:
            return
        from core import podnapisi as _pn
        video = Gio.File.new_for_uri(servis.trenutna.uri).get_path() if servis.trenutna.uri.startswith("file://") else ""

        def izbrano(poti: list) -> None:
            if not poti or self._medijski_predvajalnik is None or self._medijski_predvajalnik.trenutna is None:
                return
            pot = poti[0]
            try:
                velikost = os.path.getsize(pot)
            except OSError:
                velikost = -1
            if not _pn.je_podnapis(pot) or not 0 < velikost <= _pn.NAJVEC_BAJTOV:
                self._medijski_osd_pokazi(self._mb("podnapisi_neveljavni"))
                return
            koda, oznaka = _pn.jezik(os.path.basename(video) if video else self._medijski_predvajalnik.trenutna.naslov, pot)
            if self._medijski_predvajalnik.dodaj_podnapis(GLib.filename_to_uri(pot, None), os.path.basename(pot), koda, oznaka):
                self._medijski_osd_pokazi(self._mb("podnapisi") + ": " + os.path.basename(pot))
        self._izberi_poti(self._mb("podnapisi_izberi"), self._medijski_predvajalnik_okno or self.okno, "datoteka", izbrano,
                          potrdi=self._mb("odpri"), zacetna=os.path.dirname(video) if video else "",
                          filtri=[(self._mb("podnapisi") + " (SRT, ASS, SSA, VTT)", ["*.srt", "*.ass", "*.ssa", "*.vtt",
                                                                                     "*.SRT", "*.ASS", "*.SSA", "*.VTT"])])

    def _medijski_id_podnapisov(self) -> str:
        """IMDb oznaka trenutnega vnosa kataloga (movie/tt… ali series/tt…:S:E) za spletne podnapise; prazno = ni."""
        servis = self._medijski_predvajalnik
        if servis is None or servis.trenutna is None or self._katalog is None:
            return ""
        vnos = self._katalog.vnos_predvajanega(servis.trenutna.uri) or {}
        return str(vnos.get("podnapisi_id") or "")

    def _medijski_jeziki_podnapisov(self) -> list:
        from core import podnapisi_splet
        servis = self._medijski_predvajalnik
        return podnapisi_splet.jeziki_uporabnika(servis.nastavitve_podnapisov.get("jezik"), servis.jezik_sistema, _jezik())

    def _medijski_podnapisi_splet(self, okence) -> None:
        """Rezultati dodatka OpenSubtitles v istem okencu: uporabnikovi jeziki prvi, izbira prenese in vklopi podnapis."""
        from core import podnapisi_splet
        ident = self._medijski_id_podnapisov()
        if not ident:
            return
        cakaj = self._medijska_plosca()
        cakaj.append(Gtk.Label(label=self._mb("podnapisi_iscem"), xalign=0))
        okence.set_child(cakaj)
        jeziki = self._medijski_jeziki_podnapisov()
        uri = self._medijski_predvajalnik.trenutna.uri

        def delo() -> None:
            try:
                izid, napaka = podnapisi_splet.poisci(ident, jeziki), ""
            except Exception as e:  # noqa: BLE001 - omrezje, JSON: uporabnik vidi razumljivo sporocilo
                print("[SafeerOS] spletni podnapisi:", type(e).__name__, e, flush=True)
                izid, napaka = [], "podnapisi_napaka"
            GLib.idle_add(lambda: (self._medijski_rezultati_podnapisov(okence, uri, izid, napaka), False)[1])
        threading.Thread(target=delo, name="safeer-podnapisi-splet", daemon=True).start()

    def _medijski_rezultati_podnapisov(self, okence, uri: str, rezultati: list, napaka: str) -> None:
        from gi.repository import Pango
        from core import podnapisi as _pn, podnapisi_splet
        servis = self._medijski_predvajalnik
        if servis is None or servis.trenutna is None or servis.trenutna.uri != uri or not okence.get_visible():
            return
        plosca = self._medijska_plosca()
        nazaj = Gtk.Button(label="← " + self._mb("nazaj"))
        nazaj.connect("clicked", lambda _g: (okence.set_child(self._medijska_plosca_podnapisov(okence)),
                                             self._medijski_fokus_okenca(okence)))
        plosca.append(nazaj)
        if napaka or not rezultati:
            plosca.append(Gtk.Label(label=self._mb(napaka or "podnapisi_ni"), xalign=0, wrap=True))
        else:
            seznam = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            for jezik, skupina in podnapisi_splet.skupine(rezultati):
                seznam.append(self._medijski_naslov_plosce(_pn.ime_jezika(jezik, _jezik())))
                for r in skupina:
                    gumb = Gtk.Button(label=" · ".join(x for x in (r["ime"] or r["id"], r["oznaka"]) if x))
                    gumb.get_child().set_ellipsize(Pango.EllipsizeMode.MIDDLE)    # dolga imena izdaj
                    gumb.get_child().set_xalign(0)
                    gumb.connect("clicked", lambda _g, r=r: self._medijski_prenesi_podnapis(okence, uri, r))
                    seznam.append(gumb)
            drsno = Gtk.ScrolledWindow()
            drsno.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
            drsno.set_propagate_natural_height(True)
            drsno.set_max_content_height(420)
            drsno.set_min_content_width(420)
            drsno.set_child(seznam)
            plosca.append(drsno)
        okence.set_child(plosca)
        okence.child_focus(Gtk.DirectionType.TAB_FORWARD)

    def _medijski_prenesi_podnapis(self, okence, uri: str, rezultat: dict) -> None:
        from core import podnapisi as _pn, podnapisi_splet
        self._medijski_osd_pokazi(self._mb("podnapisi_prenasam"))

        def delo() -> None:
            try:
                pot = podnapisi_splet.prenesi(rezultat)
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] prenos podnapisa:", type(e).__name__, e, flush=True)
                pot = ""

            def nared() -> bool:
                servis = self._medijski_predvajalnik
                if not pot:
                    self._medijski_osd_pokazi(self._mb("podnapisi_napaka"))
                elif servis is not None and servis.trenutna is not None and servis.trenutna.uri == uri:
                    ime = _pn.ime_jezika(rezultat["jezik"], _jezik())
                    if servis.dodaj_podnapis(GLib.filename_to_uri(pot, None), rezultat["ime"] or ime,
                                             rezultat["jezik"], " ".join(x for x in ("OpenSubtitles", rezultat["oznaka"]) if x)):
                        okence.popdown()
                        self._medijski_osd_pokazi(self._mb("podnapisi") + ": " + ime)
                return False
            GLib.idle_add(nared)
        threading.Thread(target=delo, name="safeer-podnapis-prenos", daemon=True).start()

    @staticmethod
    def _pokazi_meni(gumb, meni, skupina: str, dejanja: list) -> None:
        """Meni pod gumbom (GTK3 Menu.popup_at_widget): Gio.Menu v Gtk.PopoverMenu z dejanji v skupini `skupina`."""
        dejanja_skupine = Gio.SimpleActionGroup()
        for d in dejanja:
            dejanja_skupine.add_action(d)
        gumb.insert_action_group(skupina, dejanja_skupine)
        stari = getattr(gumb, "_safeer_meni", None)
        if stari is not None:
            stari.unparent()
        okence = Gtk.PopoverMenu.new_from_model(meni)
        okence.set_parent(gumb)
        okence.set_position(Gtk.PositionType.BOTTOM)
        okence.set_has_arrow(False)
        gumb._safeer_meni = okence
        okence.popup()

    def _medijski_poslji_meni(self, gumb) -> None:
        """Meni naprav v Linku (brez te); izbira poslje ponudbo prek Controla (Ponudi) in izid pokaze v napisu."""
        def naprave() -> list:
            r = _control_naprave("Seznam")
            return [n for n in (r.get("naprave") or []) if not n.get("ta") and "remote" in (n.get("zmoznosti") or [])]

        def pokazi(seznam: list) -> bool:
            if not seznam:
                self._medijski_obvestilo(self._mb("poslji_ni"))
                return False
            meni, dejanja = Gio.Menu(), []
            for i, n in enumerate(seznam):
                dejanje = Gio.SimpleAction.new("n%d" % i, None)
                dejanje.connect("activate", lambda *_a, nap=n: self._medijski_poslji(nap))
                dejanja.append(dejanje)
                meni.append(str(n.get("ime") or n.get("id") or ""), "poslji.n%d" % i)
            self._pokazi_meni(gumb, meni, "poslji", dejanja)
            return False
        threading.Thread(target=lambda: GLib.idle_add(pokazi, naprave()), name="safeer-poslji-naprave", daemon=True).start()

    def _medijski_poslji(self, naprava: dict) -> None:
        ime = str(naprava.get("ime") or naprava.get("id") or "")

        def delo() -> None:
            r = _control_naprave("Ponudi", str(naprava.get("id") or ""))
            koda = str(r.get("koda") or "")
            b = (self._mb("poslano_odpri") if r.get("ok") and r.get("prikaz") == "later" else
                 self._mb("poslano") if r.get("ok") else
                 self._mb("poslji_stara") if koda == "stara" else
                 self._mb("poslji_ni_deljeno") if koda == "ni_deljeno" else
                 self._mb("poslji_izklopljeno") if koda == "izklopljeno" else self._mb("poslji_napaka")).replace("{ime}", ime)
            GLib.idle_add(self._medijski_obvestilo, b)
        threading.Thread(target=delo, name="safeer-poslji", daemon=True).start()

    # ------------------------------------------------------------------ »Predvajaj na …« in zakasnitev zvocnika
    def _povezi_zakasnitev_zvocnika(self) -> None:
        """Zvok na zvocniku v omrezju zamuja (medpomnilnik): sliko zamaknemo za njegovo zakasnitev, ob vrnitvi na 0."""
        servis = self._medijski_predvajalnik
        try:
            z = zvocniki()
            z.ob_zakasnitvi = lambda ms: GLib.idle_add(lambda: (servis.nastavi_zakasnitev_izhoda(ms), False)[1])
            servis.nastavi_zakasnitev_izhoda(z.opis()["zakasnitev"])
        except Exception as e:  # noqa: BLE001 - predvajanje gre naprej brez zamika slike
            print("[SafeerOS] zakasnitev zvocnika:", e, flush=True)

    def _medijski_meni_izhoda(self, gumb) -> None:
        """Seznam izhodov preberemo v ozadju (pactl, Link); okence odpremo, ko je znan - vmesnik ne zamrzne."""
        def delo() -> None:
            try:
                z = zvok_stanje()
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] predvajaj na:", e, flush=True)
                z = {}
            if not (z.get("link") or {}).get("zvocniki"):
                zvocniki().osvezi()          # iskanje tece v ozadju; seznam ob naslednjem odprtju
            GLib.idle_add(lambda: (self._medijsko_okence(gumb, lambda ok: self._medijska_plosca_izhoda(ok, gumb, z)),
                                   False)[1])
        threading.Thread(target=delo, name="safeer-predvajaj-na", daemon=True).start()

    def _medijska_plosca_izhoda(self, okence, gumb, z: dict) -> "Gtk.Widget":
        plosca = self._medijska_plosca()
        plosca.append(self._medijski_naslov_plosce(self._mb("predvajaj_na")))
        moznosti = os_zvok.moznosti_izhoda(z)
        potrdi = getattr(self, "_medijski_izhod_potrdi", {})
        self._medijski_izhod_potrdi = potrdi
        izbran = next((m for m in moznosti if m["aktiven"]), moznosti[0])

        def napis(m: dict) -> str:
            if m["vrsta"] == "racunalnik":
                return self._mb("ta_racunalnik") + (" · " + m["pod"] if m.get("pod") else "")
            pod = self._mb("zvocnik_omrezje") if m["vrsta"] == "zvocnik" else "Safeer Link"
            if m.get("aktiven") and m.get("stanje") == "caka":
                pod = self._mb("povezujem")
            return "%s · %s" % (m.get("ime") or "", pod)

        def izberi(kljuc: str) -> None:
            m = next((x for x in moznosti if "%s:%s" % (x["vrsta"], x["id"]) == kljuc), None)
            if m is None or m["aktiven"]:
                return
            okence.popdown()
            soglasje = bool(potrdi.pop(m["id"], None))

            def delo() -> None:
                r = zvok_izberi_izhod(m, soglasje)
                if isinstance(r, dict) and r.get("vir"):
                    potrdi[m["id"]] = r["vir"]      # zvocnik igra drug vir (TV): preklop sele ob drugi izbiri
                    b = os_media_besedila.besedilo("zvok_zaseden", _jezik()).replace("{ime}", m["ime"] or "")
                    b = b.replace("{vir}", str(r["vir"]))
                else:
                    ok = r.get("ok") if isinstance(r, dict) else bool(r)
                    b = (napis(m) if ok else self._mb("poslji_napaka").replace("{ime}", m.get("ime") or ""))
                GLib.idle_add(self._medijski_obvestilo, b)
            threading.Thread(target=delo, name="safeer-predvajaj-na-izberi", daemon=True).start()
        self._medijske_izbire(plosca, [("%s:%s" % (m["vrsta"], m["id"]), napis(m)) for m in moznosti],
                              "%s:%s" % (izbran["vrsta"], izbran["id"]), izberi)
        if izbran["vrsta"] == "zvocnik":
            plosca.append(self._medijski_zamik_zvocnika(izbran))
        isci = Gtk.Button(label="⟳ " + self._mb("isci_zvocnike"))
        isci.connect("clicked", lambda _g: (zvocniki().osvezi(), okence.popdown(),
                                            GLib.timeout_add(3500, lambda: (self._medijski_meni_izhoda(gumb), False)[1])))
        plosca.append(isci)
        return plosca

    def _medijski_zamik_zvocnika(self, m: dict) -> "Gtk.Widget":
        """Drsnik »Zamik zvoka« za aktivni zvocnik (0-8 s, korak 50 ms); shrani se na tej napravi (zvocniki.json)."""
        from core import zvok_na_zvocnik as _zz
        okvir = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        ime = Gtk.Label(xalign=0)
        okvir.append(ime)
        drsnik = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, _zz.MEJA_ZAKASNITVE_MS, _zz.KORAK_ZAKASNITVE_MS)
        drsnik.set_draw_value(False)
        drsnik.set_size_request(280, -1)
        drsnik.set_value(int(m.get("zakasnitev") or 0))
        drsnik.update_property([Gtk.AccessibleProperty.LABEL], [self._mb("zamik_zvoka")])
        opis = lambda: ime.set_text("%s: %d ms" % (self._mb("zamik_zvoka"), _zz.omeji_zakasnitev(drsnik.get_value())))
        opis()
        cas = [0]

        def spremenjeno(_d) -> None:
            opis()
            if cas[0]:
                GLib.source_remove(cas[0])

            def shrani() -> bool:
                cas[0] = 0
                ms = drsnik.get_value()
                threading.Thread(target=lambda: zvocniki().nastavi_zakasnitev(str(m["id"]), ms),
                                 name="safeer-zakasnitev", daemon=True).start()
                return False
            cas[0] = GLib.timeout_add(300, shrani)
        drsnik.connect("value-changed", spremenjeno)
        okvir.append(drsnik)
        opomba = Gtk.Label(label=self._mb("zamik_splet"), xalign=0)
        opomba.set_wrap(True)
        opomba.set_max_width_chars(40)
        opomba.add_css_class("dim-label")
        okvir.append(opomba)
        return okvir

    def _medijski_obvestilo(self, besedilo: str) -> bool:
        """Kratko sporocilo v vrstici cakalne vrste okna predvajalnika (brez oken)."""
        if self._medijski_vrsta is not None:
            self._medijski_vrsta.set_text(besedilo)
            GLib.timeout_add_seconds(6, lambda: (self._osvezi_medijski_predvajalnik(), False)[1])
        return False

    def _medijski_naslednji_podnapisi(self) -> bool:
        """Tipka V: izklop -> prvi -> drugi ... -> izklop (kot v VLC)."""
        servis = self._medijski_predvajalnik
        if servis is None:
            return False
        stanje = servis.podnapisi()
        kljuci = ["izklop"] + [m["kljuc"] for m in stanje["moznosti"]]
        if len(kljuci) < 2:
            return False
        i = kljuci.index(stanje["izbran"]) if stanje["izbran"] in kljuci else 0
        nov = kljuci[(i + 1) % len(kljuci)]
        if not servis.izberi_podnapise(nov):
            return False
        m = next((m for m in stanje["moznosti"] if m["kljuc"] == nov), None)
        self._medijski_osd_pokazi(self._mb("podnapisi") + ": " + (self._ime_podnapisa(m) if m else self._mb("podnapisi_izklop")))
        return True

    @staticmethod
    def _medijski_cas_besedilo(sekunde: float) -> str:
        sekunde = max(0, int(sekunde))
        return f"{sekunde // 60}:{sekunde % 60:02d}"

    def _osvezi_medijski_drsnik(self, podatki: dict) -> None:
        if self._medijski_drsnik is None:
            return
        v_zivo = podatki["vrsta"] in ("tv", "radio")
        dolzina = podatki["trajanje"]
        self._medijski_drsnik.set_sensitive(not v_zivo and dolzina > 0)
        self._medijski_drsnik.set_range(0, max(1, dolzina))
        if not self._medijski_vlecem:
            self._medijski_drsnik.set_value(min(dolzina, podatki["pozicija"]))
        self._medijski_cas.set_text("● V živo" if v_zivo else
                                   self._medijski_cas_besedilo(podatki["pozicija"]) + " / " +
                                   self._medijski_cas_besedilo(dolzina))

    def _medijski_premik(self, _drsnik, _vrsta_premika, vrednost) -> bool:
        if not self._medijski_vlecem:
            self._medijski_ukaz("skok", float(vrednost))
        return False

    def _medijski_zacni_premik(self, _drsnik, _dogodek) -> bool:
        self._medijski_vlecem = True
        return False

    def _medijski_spusti_premik(self, drsnik, _dogodek) -> bool:
        self._medijski_vlecem = False
        self._medijski_ukaz("skok", drsnik.get_value())
        return False

    @staticmethod
    def _mb(kljuc: str) -> str:
        """Napis GTK predvajalnika v jeziku vmesnika."""
        return os_media_besedila.besedilo(kljuc, _jezik())

    def _medijski_cel_zaslon(self, okno) -> bool:
        if okno.is_fullscreen():
            okno.unfullscreen()
        else:
            okno.fullscreen()
        return True

    def _medijska_tipka(self, okno, dogodek) -> bool:
        tipka = Gdk.keyval_name(dogodek.keyval)
        servis = self._medijski_predvajalnik
        if self._medijsko_okence_odprto():
            # Okence z nastavitvami ima svoje tipke (puscice, preslednica, Esc) - ne premikamo posnetka pod njim.
            # Tipka Nazaj na daljincu ga zapre kot Esc.
            if tipka == "Back":
                for o in self._medijska_okenca:
                    o.popdown()
                return True
            return False
        if servis is not None and servis.je_dvd():
            # Meni DVD: puščice in Enter premikajo izbiro (v filmu jih disk prezre), M odpre meni diska.
            ukaz = {"Up": "gor", "Down": "dol", "Return": "potrdi", "KP_Enter": "potrdi", "m": "meni", "M": "meni"}.get(tipka or "")
            if ukaz:
                return servis.navigacija(ukaz)
            if tipka in ("Left", "Right"):
                servis.navigacija("levo" if tipka == "Left" else "desno")
        brez_ctrl = not dogodek.state & (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK)
        if tipka in ("Menu", "AudioCycleTrack") or (tipka in ("b", "B") and brez_ctrl):
            # Menu na daljincu odpre Zvok; B in tipka daljinca za zvocni posnetek ga preklopita (kot v VLC).
            if tipka == "Menu":
                if self._medijski_zvok is not None and self._medijski_zvok.get_visible():
                    self._medijski_meni_zvoka(self._medijski_zvok)
                    return True
                return False
            return self._medijski_naslednji_zvok()
        if tipka in ("j", "J", "k", "K", "g", "G", "h", "H") and brez_ctrl:
            # Zamik za 50 ms kot v VLC: J/K zvok (K = zvok kasneje), G/H podnapisi (H = podnapisi kasneje).
            from core import predvajalnik_moznosti as _pm
            t = tipka.lower()
            return self._medijski_zamik_tipka("zvok" if t in "jk" else "podnapisi",
                                              _pm.KORAK_TIPKA_MS if t in "kh" else -_pm.KORAK_TIPKA_MS)
        if tipka == "Subtitle":
            return self._medijski_naslednji_podnapisi()
        if tipka == "space":
            return self._medijski_ukaz("premor")
        if tipka in ("Left", "Right") and self._medijski_predvajalnik:
            podatki = self._medijski_podatki()
            return self._medijski_ukaz("skok", podatki["pozicija"] + (-10 if tipka == "Left" else 10))
        if tipka and tipka.lower() == "v" and not dogodek.state & Gdk.ModifierType.CONTROL_MASK:
            return self._medijski_naslednji_podnapisi()
        if tipka and (tipka.lower() == "f" or tipka == "F11"):
            return self._medijski_cel_zaslon(okno)
        if tipka and tipka.lower() in ("n", "p") and not dogodek.state & Gdk.ModifierType.CONTROL_MASK:
            return self._medijski_ukaz("naslednja" if tipka.lower() == "n" else "prejsnja")
        if tipka == "Escape" and okno.is_fullscreen():
            okno.unfullscreen()
            return True
        return False

    def _osvezi_medijski_sklad(self) -> None:
        """Slika za video, glasbeni znak za zvok. Dokler playbin ne pozna tokov, odloči vrsta vnosa."""
        servis = self._medijski_predvajalnik
        if servis is None or self._medijski_sklad is None:
            return
        self._medijski_zvok_naslov.set_text(servis.trenutna.naslov if servis.trenutna else "")
        cilj = "slika" if self._medij_ima_sliko() and self._medijski_sklad.get_child_by_name("slika") else "zvok"
        if self._medijski_sklad.get_visible_child_name() != cilj:
            self._medijski_sklad.set_visible_child_name(cilj)

    def _medij_ima_sliko(self) -> bool:
        """Ali ima to, kar predvajamo, sliko. Dokler playbin ne pozna tokov, odloci vrsta vnosa."""
        servis = self._medijski_predvajalnik
        if servis is None:
            return False
        try:
            ok, pozicija = servis.element.query_position(servis.gst.Format.TIME)
            if ok and pozicija > 0:
                return int(servis.element.get_property("n-video") or 0) > 0
        except Exception:  # noqa: BLE001
            pass
        return bool(servis.trenutna and servis.trenutna.vrsta in ("video", "tv"))

    def _budnost_predvajanja(self) -> None:
        """Med predvajanjem racunalnik ne zaspi sam; med videom se tudi ohranjevalnik ne vklopi in zaslon ne ugasne
        (kot v vsakem predvajalniku). Premor, konec in napaka zadrzanje sprostijo. Zaprt pokrov deluje kot vedno."""
        servis = self._medijski_predvajalnik
        zastavice = 0
        if servis is not None and servis.stanje == "predvaja":
            zastavice = budnost.SPANJE | (budnost.ZASLON if self._medij_ima_sliko() else 0)
        try:
            self._budnost.nastavi("predvajanje", zastavice, "Safeer predvaja")
        except Exception:  # noqa: BLE001 - predvajanje ne sme pasti zaradi vodila seje
            pass

    def _medijski_tik(self) -> bool:
        if self._koncano:
            return False
        self._budnost_predvajanja()
        if self._medijski_predvajalnik and self._medijski_predvajalnik.stanje == "premor":
            self._medijski_predvajalnik.poskusi_nadaljevati()     # obnovljen ustavljen: skok na shranjeni polozaj
        if self._medijski_predvajalnik and self._medijski_predvajalnik.stanje == "predvaja":
            self._medijski_predvajalnik.poskusi_nadaljevati()
            podatki = self._medijski_podatki()
            self._shrani_medijski_napredek(podatki)
            self._osvezi_medijski_drsnik(podatki)
            self._osvezi_medijski_sklad()
            self._dogodek("predvajalnik", podatki)
        return True

    @staticmethod
    def _pot_lokalnega_videa(uri: str) -> str:
        if not uri.startswith("file://"):
            return ""
        pot = Gio.File.new_for_uri(uri).get_path() or ""
        return pot if os_knjiznica.vrsta_datoteke(Path(pot)) in ("filmi", "serije") else ""

    def _shrani_medijski_napredek(self, podatki=None) -> None:
        servis = self._medijski_predvajalnik
        if not servis or not servis.trenutna or servis.stanje not in ("predvaja", "premor"):
            return
        pot = self._pot_lokalnega_videa(servis.trenutna.uri)
        if not pot:
            if self._katalog is not None and self._katalog.vnos_predvajanega(servis.trenutna.uri):
                # Film ali epizoda iz kataloga: napredek hrani katalog (naslednjic nadaljuje, kjer je uporabnik ostal).
                podatki = podatki or servis.podatki()
                kljuc = (servis.trenutna.uri, int(podatki["pozicija"]) // 5)
                if kljuc != self._zadnji_medijski_napredek:
                    self._katalog.shrani_napredek(servis.trenutna.uri, podatki["pozicija"], podatki["trajanje"])
                    self._zadnji_medijski_napredek = kljuc
            return
        podatki = podatki or servis.podatki()
        pozicija, trajanje = podatki["pozicija"], podatki["trajanje"]
        if pozicija < 15 or trajanje <= 0:
            return
        kljuc = (pot, int(pozicija) // 5)
        if kljuc != self._zadnji_medijski_napredek:
            self._medijska_knjiznica().shrani_napredek(pot, pozicija, trajanje)
            self._zadnji_medijski_napredek = kljuc

    def _medijski_konec(self, uri: str) -> None:
        if self._katalog is not None:
            self._katalog.konec(uri)      # skladba iz kataloga: stran predvaja naslednjo iz svoje vrste
        pot = self._pot_lokalnega_videa(uri)
        if pot:
            self._medijska_knjiznica().ponastavi_napredek(pot)
            self._zadnji_medijski_napredek = None
            self._dogodek("medijskaKnjiznica", None)

    def _yt_predvajanje(self) -> Optional[dict]:
        """Skladba iz kataloga v vgradnem predvajalniku YouTuba, kadar domaci predvajalnik ne igra (ne premor)."""
        servis = self._medijski_predvajalnik
        if servis is not None and servis.stanje in ("predvaja", "premor"):
            return None
        return self._katalog.yt_podatki() if self._katalog is not None else None

    def _sp_racun(self):
        """Spotify (skrit Safeer DRM), ce ze tece - za pripomocke ga ne zaganjamo (brez ustvarjanja MediaCenter)."""
        mc = getattr(self._katalog, "_mc", None) if self._katalog is not None else None
        return getattr(mc, "_spotify", None) if mc is not None else None

    def _sp_predvajanje(self) -> Optional[dict]:
        """Skladba Spotify, kadar domaci predvajalnik ne igra (ne premor). 18. 10. 2026: med glasbo iz Spotifyja je
        pripomocek na namizju kazal »Ni predvajanja«."""
        servis = self._medijski_predvajalnik
        if servis is not None and servis.stanje in ("predvaja", "premor"):
            return None
        racun = self._sp_racun()
        try:
            p = racun.predvajanje() if racun is not None else {}
        except Exception:  # noqa: BLE001 - pripomocek ne sme pasti zaradi Spotifyja
            p = {}
        if not p.get("naslov"):
            return None
        return {"stanje": "predvaja" if p.get("igra") else "premor", "naslov": str(p.get("naslov") or ""),
                "izvajalec": str(p.get("izvajalec") or ""), "slika": str(p.get("slika") or ""), "vrsta": "glasba",
                "izvor": "Spotify", "indeks": -1, "zacetniIndeks": 0, "skupaj": 0, "vrstaSeznam": [], "pozicija": 0,
                "trajanje": 0, "napaka": "", "vrstaStrani": False, "spotify": True}

    def _medijski_podatki(self) -> dict:
        yt = self._yt_predvajanje()
        if yt is not None:
            # Ista oblika kot domaci predvajalnik (14. 10. 2026: pripomocek na namizju je med skladbo s seznama kazal
            # »Ni predvajanja«). Polozaja vgradni predvajalnik ne javlja: trajanje 0 skrije drsnik. Naslednjo in
            # prejsnjo vodi stran (vrstaStrani), zato ju pripomocki ne onemogocijo.
            return dict(yt, indeks=-1, zacetniIndeks=0, skupaj=0, vrstaSeznam=[], pozicija=0, trajanje=0, napaka="",
                        vrstaStrani=True)
        sp = self._sp_predvajanje()
        if sp is not None:
            return sp
        servis = self._medijski_predvajalnik
        if servis is None:
            return {"stanje": "ustavljeno", "naslov": "", "vrsta": "", "indeks": -1,
                    "zacetniIndeks": 0, "skupaj": 0, "vrstaSeznam": [], "pozicija": 0, "trajanje": 0, "napaka": ""}
        p = servis.podatki()
        # Skladba iz kataloga: naslednjo in prejsnjo vodi stran (vrsta, premesaj), zato sta na voljo tudi pri eni skladbi.
        vnos = (self._katalog.vnos_predvajanega(servis.trenutna.uri) if self._katalog is not None and servis.trenutna
                else None) or {}
        p["vrstaStrani"] = bool(vnos.get("zvok")) and len(servis.vrsta) <= 1 and p.get("vrsta") != "radio"
        # Izvajalec in naslovnica iz kataloga: za pripomocke na namizju in sistem (MPRIS).
        p["izvajalec"] = str(vnos.get("izvajalec") or "")
        p["slika"] = str(vnos.get("slika") or "")
        return p

    def _yt_spremenjeno(self) -> None:
        """Skladba v vgradnem predvajalniku je zacela, se ustavila ali koncala: stranem (Medijski center, namizje) in
        sistemu (MPRIS) povemo novo stanje - sicer bi vrstica ostala pri stari skladbi."""
        self._dogodek("predvajalnik", self._medijski_podatki())
        self._mpris_osvezi()

    def _sp_spremenjeno(self) -> None:
        """Spotify (nit strazarja, core/spotify_racun.py) je zacel, ustavil ali zamenjal skladbo: isto kot _yt_spremenjeno,
        iz glavne niti. Namizje QML zato ne bere stanja vsake 3 s (Namizje.qml osveziMedij)."""
        GLib.idle_add(lambda: (self._yt_spremenjeno(), False)[1])

    def _yt_ukaz(self, ukaz: str, yt: dict) -> bool:
        """Tipke pripomockov in sistema za skladbo v vgradnem predvajalniku YouTuba (glavna nit)."""
        if ukaz == "premor":
            return self._katalog_youtube_ukaz("pauseVideo" if yt["stanje"] == "predvaja" else "playVideo")
        if ukaz in ("naslednja", "prejsnja"):
            self._dogodek("mediaVrstaUkaz", 1 if ukaz == "naslednja" else -1)
            return True
        if ukaz == "ustavi":
            return self._katalog_youtube_ukaz("zapri")        # zapre pogled: yt_zaprt ustavi tudi vrsto strani
        if ukaz == "odpri" and self._medijska_plast is not None:
            return self._pokazi_medijsko_plast()        # klik na mini predvajalnik: video spet v oknu
        return False

    def _medijski_ukaz(self, ukaz: str, vrednost=None) -> bool:
        yt = self._yt_predvajanje()
        if yt is not None:          # katalog jo lahko hkrati konca (nit): podatke beremo enkrat
            return self._yt_ukaz(ukaz, yt)
        if self._sp_predvajanje() is not None:
            # Tipke pripomockov in sistema za Spotify: ukaz gre strani v Safeer DRM (do 5 s), zato v niti, ne na glavni.
            sp_ukaz = {"premor": "premor", "naslednja": "naprej", "prejsnja": "nazaj", "ustavi": "ustavi"}.get(ukaz)
            racun = self._sp_racun()
            if sp_ukaz is None or racun is None:
                return False
            threading.Thread(target=racun.upravljaj, args=(sp_ukaz,), name="safeer-spotify-ukaz", daemon=True).start()
            return True
        servis = self._medijski_predvajalnik
        if not servis:
            return False
        if ukaz in ("naslednja", "prejsnja") and self._katalog is not None and len(servis.vrsta) <= 1 and servis.trenutna \
                and (self._katalog.vnos_predvajanega(servis.trenutna.uri) or {}).get("zvok"):
            # Skladba iz kataloga: vrsto (naslednja, premesaj, ponovi) vodi stran - tipka ali daljinec gre njej.
            self._dogodek("mediaVrstaUkaz", 1 if ukaz == "naslednja" else -1)
            return True
        if ukaz in ("premor", "naslednja", "prejsnja", "ustavi", "predvajaj"):
            self._shrani_medijski_napredek()
            if ukaz in ("naslednja", "prejsnja", "ustavi", "predvajaj"):
                self._dogodek("medijskaKnjiznica", None)
        if ukaz == "premor":
            servis.premor()
        elif ukaz == "naslednja":
            return servis.naslednja()
        elif ukaz == "prejsnja":
            return servis.prejsnja()
        elif ukaz == "ustavi":
            servis.ustavi()
            self._dogodek("medijskaKnjiznica", None)
        elif ukaz == "predvajaj" and type(vrednost) is int:
            return servis.predvajaj(vrednost)
        elif ukaz == "skok" and isinstance(vrednost, (float, int)):
            if not servis.skok(vrednost):
                return False
            pot = self._pot_lokalnega_videa(servis.trenutna.uri) if servis.trenutna else ""
            if pot:
                if vrednost < 15:
                    self._medijska_knjiznica().ponastavi_napredek(pot)
                else:
                    self._medijska_knjiznica().shrani_napredek(pot, vrednost, servis.trajanje())
                self._zadnji_medijski_napredek = None
            return True
        elif ukaz == "odpri" and self._medijski_predvajalnik_okno:
            self._medijski_predvajalnik_okno.present()
        else:
            return False
        return True

    @staticmethod
    def _odpri_mapo_prenosov(pot: str) -> bool:
        """Odpre mapo prenosa (nikoli datoteke - ta bi lahko bila potrjen program) znotraj mape Prenosi/Safeer."""
        koren = os.path.realpath(os_torrent.mapa_prenosov())
        pot = os.path.realpath(pot or koren)
        if not os.path.isdir(pot):
            pot = os.path.dirname(pot)
        if not os.path.isdir(pot) or not (pot == koren or pot.startswith(koren + os.sep)):
            return False
        return os_datoteke.odpri(pot)

    def _predvajaj_disk(self, naprava: str) -> bool:
        """DVD v optičnem pogonu (samo naprave /dev/sr*, ki jih javi core/os_dvd.pogoni)."""
        from core import os_dvd
        if not any(p["naprava"] == naprava and p["vstavljen"] for p in os_dvd.pogoni()):
            return False
        ime = next((p["ime"] for p in os_dvd.pogoni() if p["naprava"] == naprava), "DVD")
        return self._predvajaj_neposredno("dvd://" + naprava, vrsta="video", prikazi=True, ime=ime)

    def _katalog_most(self):
        """Katalog Medijskega centra (core/os_katalog.py); ustvari se ob prvem klicu strani."""
        if self._katalog is None:
            zaslon = self._zaslon()
            g = zaslon.get_geometry() if zaslon else None
            visina = int(min(g.width, g.height) * (zaslon.get_scale_factor() if zaslon else 1)) if g else 1080
            self._katalog = os_katalog.Katalog(
                os.path.join(os_programi.MAPA_NASTAVITEV, "media"), self._dogodek, GLib.idle_add,
                predvajaj=self._katalog_predvajaj, vdelano=self._odpri_lahki_medijski_pogled,
                youtube=self._katalog_youtube, youtube_ukaz=self._katalog_youtube_ukaz,
                jezik=_jezik, visina_zaslona=visina, uskladi_sezname=_seznami_z_naprav, knjiznica=_knjiznica())
            self._katalog.twitch_brez_oglasov = self.scit.twitch_brez_oglasov
            self._katalog.ob_spotify = self._sp_spremenjeno
        return self._katalog

    def _katalog_predvajaj(self, uri: str, vrsta: str, ime: str, zacetek: int, podnapisi: tuple, prikazi: bool,
                           tok: Optional[dict] = None) -> bool:
        """Tok ali datoteka iz kataloga v domacem predvajalniku (video v oknu, zvok brez okna). `tok`: glave, ki jih
        streznik toka zahteva, in druge razlicice ({"glave": {...}, "nadomestni": [(uri, glave), ...]})."""
        tok = tok if isinstance(tok, dict) else {}
        seznam = [os_predvajalnik.Skladba(uri, ime, vrsta, zacetek=max(0, int(zacetek or 0)), podnapisi=podnapisi,
                                          glave=os_predvajalnik.cisti_glave(tok.get("glave")),
                                          nadomestni=os_predvajalnik.cisti_nadomestne(tok.get("nadomestni")))]
        return self._predvajaj_neposredno(uri, vrsta=vrsta, prikazi=prikazi, ime=ime, seznam=seznam, zacni=0)

    def _medijska_knjiznica(self):
        if self._knjiznica_medijev is None:
            self._knjiznica_medijev = os_knjiznica.Knjiznica()
        return self._knjiznica_medijev

    def _predvajaj_datoteko(self, pot: str) -> bool:
        """Video ali glasba z diska (`safeer-os --predvajaj <pot>` iz terminala ali zaganjalnika): iz knjiznice
        z nadaljevanjem, kjer je uporabnik ostal, sicer neposredno v domacem predvajalniku."""
        pot = os.path.realpath(str(pot or ""))
        if not os.path.isfile(pot):
            return False
        self._medijski_klicatelj = None
        if self.okno is None and self.okno_predvajalnik is None:
            self._cakajoca_datoteka = pot
            self._odpri_medijsko_okno()
            GLib.timeout_add(1500, self._predvajaj_cakajoco)
            return True
        if self._odpri_lokalni_medij(pot):
            return True
        vrsta = os_knjiznica.vrsta_datoteke(Path(pot))
        if vrsta not in ("filmi", "serije", "glasba"):
            return False
        return self._predvajaj_neposredno(GLib.filename_to_uri(pot, None), vrsta="video" if vrsta != "glasba" else "medij",
                                         prikazi=vrsta != "glasba", ime=os_knjiznica.naslov_datoteke(Path(pot)))

    def _odpri_lokalni_medij(self, pot: str) -> bool:
        vnos = self._medijska_knjiznica().dobi(pot)
        if not vnos or not os.path.isfile(pot):
            return False
        if vnos["vrsta"] == "slike":
            return os_datoteke.odpri(pot)
        self._medijska_knjiznica().predvajano(pot)
        prikazi = vnos["vrsta"] != "glasba"
        zacetek = vnos["pozicija"] if prikazi and vnos["pozicija"] >= 15 else 0
        seznam, zacni = None, 0
        if vnos["vrsta"] == "glasba":
            album = self._medijska_knjiznica().skladbe_iz_mape(pot)
            seznam = [os_predvajalnik.Skladba(GLib.filename_to_uri(s["pot"], None), s["ime"]) for s in album]
            zacni = next((i for i, s in enumerate(album) if s.get("izbrana")), 0)
        if prikazi:
            # Video z datotekami podnapisov ob njem (ista mapa ali podmapa Subs), kot pri VLC.
            from core import podnapisi as _pn
            podnapisi = tuple((GLib.filename_to_uri(p, None), os.path.basename(p)) + _pn.jezik(pot, p)
                              for p in _pn.podnapisi_mape(pot))
            seznam = [os_predvajalnik.Skladba(GLib.filename_to_uri(pot, None), vnos["ime"], "video",
                                              zacetek=zacetek, podnapisi=podnapisi)]
            zacni = 0
        from core import os_dvd
        if prikazi and os_dvd.je_dvd(pot):
            # DVD (ISO ali VIDEO_TS): GStreamer ga odpre kot disk, z meniji; napredka ne nadaljujemo.
            return self._predvajaj_neposredno(os_dvd.uri(pot), vrsta="video", prikazi=True, ime=vnos["ime"])
        return self._predvajaj_neposredno(GLib.filename_to_uri(pot, None),
                                         vrsta="video" if prikazi else "medij", prikazi=prikazi,
                                         ime=vnos["ime"], zacetek=zacetek, seznam=seznam, zacni=zacni)

    def _predvajaj_z_naprave(self, streznik: dict, kljuc: str, vnosi: list, zacni: int = 0, izvor: str = "",
                             naprava: str = "", zacetek: int = 0) -> bool:
        """Glasba ali video z druge naprave v Linku, sproti in brez prenosa na disk.

        Predvajalnik dobi lokalni naslov 127.0.0.1 (core/link_pretok.py), ta pa bere z naprave po HTTPS s
        pripetim potrdilom in zetonom - doma neposredno, zunaj doma prek Global Linka (kljuc iz kroga).
        Glasba: vse skladbe mape v vrsti (album); video: samo izbrani posnetek, v oknu predvajalnika."""
        from core import link_pretok
        vnosi = [v for v in vnosi if isinstance(v, dict) and v.get("type") in ("audio", "video")]
        if not vnosi:
            return False
        zacni = max(0, min(int(zacni or 0), len(vnosi) - 1))
        izbran = vnosi[zacni]
        zvok = izbran.get("type") == "audio"
        if not zvok:
            vnosi, zacni = [izbran], 0
        elif any(v.get("type") != "audio" for v in vnosi):
            vnosi = [v for v in vnosi if v.get("type") == "audio"]
            zacni = vnosi.index(izbran)
        seznam = []
        for v in vnosi:
            vir = link_pretok.vir_iz_streznika(streznik, str(v.get("id") or ""), kljuc, str(v.get("mime") or ""))
            if vir is None:
                return False
            ime = os.path.splitext(str(v.get("name") or ""))[0] or str(v.get("name") or "")
            podnapisi = []
            for p in (v.get("subtitles") or [])[:24] if not zvok else []:
                if not isinstance(p, dict):
                    continue
                vp = link_pretok.vir_iz_streznika(streznik, str(p.get("id") or ""), kljuc, "text/plain")
                if vp is not None:
                    podnapisi.append((link_pretok.pretok().dodaj(vp), str(p.get("name") or ""),
                                      str(p.get("lang") or ""), str(p.get("label") or "")))
            seznam.append(os_predvajalnik.Skladba(link_pretok.pretok().dodaj(vir), ime,
                                                  "medij" if zvok else "video", izvor=str(izvor or ""),
                                                  zacetek=max(0, int(zacetek or 0)) if v is izbran else 0,
                                                  podnapisi=tuple(podnapisi), naprava=str(naprava or ""),
                                                  oznaka=str(v.get("id") or ""),
                                                  izvirnik=vir.base_url.rstrip("/") + "/d/" + urllib.parse.quote(vir.id_datoteke, safe="")))
        return self._predvajaj_neposredno(seznam[zacni].uri, vrsta="medij" if zvok else "video",
                                         prikazi=not zvok, ime=seznam[zacni].naslov,
                                         seznam=seznam, zacni=zacni)

    # ------------------------------------------------------------------ magnet povezave
    def _odpri_magnet(self, uri: str) -> None:
        """Magnet iz brskalnika ali z druge naprave: Medijski center ga pokaže.

        Samo ukaz z naprave v krogu ("naprava:" iz --magnet-naprava) se začne brati in predvajati sam;
        povezava iz brskalnika ali druge aplikacije se ne dotakne omrežja, dokler uporabnik ne pritisne Odpri."""
        samodejno = uri.startswith("naprava:")
        uri = uri[len("naprava:"):] if samodejno else uri
        if os_torrent.razcleni_magnet(uri) is None:
            return
        magnet = {"uri": uri, "samodejno": samodejno}
        if self._medijski_cilj() == "predvajalnik":
            # Ob delovni povrsini (ali ko je odprt samo Safeer Player) magnet pokaze Safeer Player, ne cele lupine.
            if self.okno_predvajalnik is None:
                self._cakajoci_magnet = dict(magnet, predvajalnik=True)
                self._odpri_predvajalnik()
                return        # stran Safeer Playerja ga prevzame ob nalaganju (cakajociMagnet)
            self._odpri_predvajalnik()
            self._dogodek("magnet", magnet, self.pogled_predvajalnik)
            return
        self._cakajoci_magnet = magnet
        if self.okno is None:
            self.activate()
            return            # stran ga prevzame ob nalaganju (cakajociMagnet)
        self.okno.present()
        self._dogodek("magnet", magnet, self.pogled)     # samo glavnemu oknu: Safeer Player ga ne odpre se enkrat

    @staticmethod
    def _kopiraj(besedilo: str) -> bool:
        """Besedilo v odložišče (magnet povezava, sporočilo ali izbrani del sporočila).

        Prazno besedilo odložišča ne izprazni. Do 0.4.65 je bila meja 8192 znakov (dovolj za povezavo, premalo za dolgo
        e-sporočilo - konec je tiho manjkal)."""
        besedilo = str(besedilo or "")[:NAJVEC_KOPIJE]
        if not besedilo:
            return False
        # GTK4: odlozisce je na zaslonu (Gdk.Clipboard); store_async ga preda upravitelju odlozisca, da ostane po izhodu.
        odlozisce = Gdk.Display.get_default().get_clipboard()
        odlozisce.set(besedilo)
        odlozisce.store_async(GLib.PRIORITY_DEFAULT, None, SafeerOS._odlozisce_shranjeno)
        return True

    @staticmethod
    def _odlozisce_shranjeno(odlozisce, izid) -> None:
        try:
            odlozisce.store_finish(izid)
        except Exception:  # noqa: BLE001 - brez upravitelja odlozisca besedilo ostane, dokler tece Safeer OS
            pass

    def _odpri_stremio_dodatek(self, naslov: str) -> bool:
        """Gumb »Install« dodatka Stremio (stremio://...) iz Spleta, brskalnika ali druge aplikacije: Safeer Player odpre
        okno Dodatki z naslovom dodatka. Doda se sele, ko uporabnik pritisne Poveži (dodatek se tedaj preveri)."""
        url = media_servers.stremio_naslov_dodatka(naslov)
        if not url:
            return False
        if self.okno_predvajalnik is None:
            self._cakajoci_stremio = url
            self._odpri_predvajalnik()
            return True       # stran Safeer Playerja ga prevzame ob nalaganju (cakajociStremio)
        self._odpri_predvajalnik()
        self._dogodek("stremioDodatek", {"url": url}, self.pogled_predvajalnik)
        return True

    def _kavc_cel_zaslon(self, pogled, vklop: bool) -> bool:
        """Nacin za kavc (kavc.js): okno strani, ki ga je vklopila, cez cel zaslon. GTK in ne celozaslonski nacin strani,
        da Escape ostane tipka Nazaj (WebKit bi z njo zapustil cel zaslon)."""
        okno = self.okno_predvajalnik if pogled is not None and pogled is self.pogled_predvajalnik else self.okno
        if okno is None:
            return False
        if vklop:
            okno.fullscreen()
        else:
            okno.unfullscreen()
        return True

    def _vzemi_cakajoci_stremio(self) -> dict:
        url, self._cakajoci_stremio = self._cakajoci_stremio, ""
        return {"url": url} if url else {}

    @staticmethod
    def _odlozisce_besedilo(konec: Callable[[str], None]) -> None:
        """Gumb Prilepi v oknu Dodatki: besedilo iz odlozisca (samo na klik uporabnika, najvec 1024 znakov).
        GTK4 bere odlozisce samo asinhrono: besedilo dobi konec(besedilo)."""
        def prebrano(odlozisce, izid) -> None:
            try:
                besedilo = odlozisce.read_text_finish(izid) or ""
            except Exception:  # noqa: BLE001 - v odloziscu ni besedila
                besedilo = ""
            konec(besedilo.strip()[:1024])
        Gdk.Display.get_default().get_clipboard().read_text_async(None, prebrano)

    def _vzemi_cakajoci_magnet(self, pogled=None) -> dict:
        """Magnet, ki caka na stran (zagon z --magnet ali magnet, preden je bilo okno). Dobi ga samo stran, ki ji je
        namenjen (Safeer Player ali glavno okno), sicer bi ga pokazali obe ali napacna."""
        cakajoci = self._cakajoci_magnet
        if isinstance(cakajoci, str):
            # Zagon `safeer-os --magnet[-naprava]` (main): niz z »naprava:« spredaj, kot pri dejanju »magnet«.
            samodejno = cakajoci.startswith("naprava:")
            cakajoci = {"uri": cakajoci[len("naprava:"):] if samodejno else cakajoci, "samodejno": samodejno} \
                if cakajoci else {}
        if not cakajoci or bool(cakajoci.get("predvajalnik")) != (pogled is not None and pogled is self.pogled_predvajalnik):
            return {}
        self._cakajoci_magnet = ""
        return {"uri": cakajoci["uri"], "samodejno": bool(cakajoci.get("samodejno"))}

    def _predvajaj_magnet(self, tid: int, i: int, ime: str) -> dict:
        """Datoteka torrenta v našem predvajalniku že med prenosom (lokalni tok z geslom na 127.0.0.1)."""
        try:
            url = os_torrent.torrenti().tok(tid, i)
        except os_torrent.NapakaTorrenta as e:
            return {"ok": False, "koda": str(e)}
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] magnet tok:", e)
            return {"ok": False, "koda": "napaka"}
        video = os_torrent.vrsta_datoteke(ime) == "video"
        podnapisi = []
        if video:
            try:
                from core import podnapisi as _pn
                for j, pot_p in os_torrent.torrenti().podnapisi_za(tid, i):
                    podnapisi.append((os_torrent.torrenti().tok(tid, j), os.path.basename(pot_p)) + _pn.jezik(ime, pot_p))
            except Exception as e:  # noqa: BLE001 - podnapisi niso nujni za predvajanje
                print("[SafeerOS] magnet podnapisi:", e)
        skladba = os_predvajalnik.Skladba(url, os.path.splitext(os.path.basename(ime))[0] or ime,
                                          "video" if video else "medij", izvor="Magnet", podnapisi=tuple(podnapisi))
        ok = self._v_glavni_pocakaj(lambda: self._predvajaj_neposredno(
            url, vrsta="video" if video else "medij", prikazi=video, ime=skladba.naslov, seznam=[skladba], zacni=0))
        return {"ok": bool(ok)}

    @staticmethod
    def _v_glavni_pocakaj(delo: Callable[[], Any], cas: float = 12.0) -> Any:
        """Iz niti ozadja: delo z okni (Gtk) izvede glavna nit, nit ozadja pocaka na izid (kot os_katalog)."""
        if threading.current_thread() is threading.main_thread():
            return delo()
        konec, izid = threading.Event(), {}

        def naredi() -> bool:
            try:
                izid["v"] = delo()
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] glavna nit:", e)
            konec.set()
            return False
        GLib.idle_add(naredi)
        konec.wait(cas)
        return izid.get("v", False)

    def _magnet_prenesi_program(self) -> dict:
        """Enkratni prenos odprtokodnega rqbita (preverjen SHA-256); napredek gre na stran."""
        if os_torrent.program_na_voljo():
            return {"ok": True}
        try:
            os_torrent.prenesi_program(lambda n, vse: self._dogodek("magnetProgram", {"n": n, "vse": vse}))
            return {"ok": True}
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] rqbit:", e)
            return {"ok": False, "koda": "prenos_programa"}

    def _magnet_iz_datoteke(self, mapa: bool, stars=None, konec: Optional[Callable[[bool], None]] = None) -> None:
        """Uporabnik izbere svojo datoteko ali mapo; iz nje nastane magnet, ki ga lahko pošlje ali deli.
        konec(True/False): ali je uporabnik izbral (GTK4: izbira je asinhrona)."""
        def izbrano(poti: list) -> None:
            if not poti:
                konec and konec(False)
                return
            pot = poti[0]

            def delo() -> None:
                izid = _magnet_klic(lambda: {"uri": os_torrent.torrenti().deli_datoteko(pot),
                                             "ime": os.path.basename(pot)})
                self._dogodek("magnetDeljen", izid)
            threading.Thread(target=delo, name="safeer-magnet-deli", daemon=True).start()
            konec and konec(True)
        self._izberi_poti(self._mb("izberi_mapo") if mapa else self._mb("deli_datoteko"), stars or self.okno,
                          "mapa" if mapa else "datoteka", izbrano)

    def _izberi_poti(self, naslov: str, stars, nacin: str, konec: Callable[[list], None],
                     potrdi: str = "", zacetna: str = "", filtri: Optional[list] = None) -> None:
        """Sistemsko okno za izbiro (GTK4 Gtk.FileDialog, asinhrono; GTK3 FileChooserDialog.run je odstranjen).
        nacin: »datoteka«, »datoteke« (vec) ali »mapa«. konec(seznam poti) - prazen ob preklicu."""
        izbira = Gtk.FileDialog(title=naslov, modal=True)
        if potrdi:
            izbira.set_accept_label(potrdi)
        zacetna = zacetna if zacetna and os.path.isdir(zacetna) else GLib.get_home_dir()
        izbira.set_initial_folder(Gio.File.new_for_path(zacetna))   # ne mapa programa (~/.local/lib/safeer-os)
        if filtri:
            # [(ime, [vzorci])]: npr. samo podnapisi - prvi filter je privzet
            seznam = Gio.ListStore.new(Gtk.FileFilter)
            for ime, vzorci in filtri:
                f = Gtk.FileFilter()
                f.set_name(ime)
                for v in vzorci:
                    f.add_pattern(v)
                seznam.append(f)
            izbira.set_filters(seznam)

        def izbrano(dialog, izid) -> None:
            try:
                if nacin == "datoteke":
                    model = dialog.open_multiple_finish(izid)
                    datoteke = [model.get_item(i) for i in range(model.get_n_items())] if model is not None else []
                elif nacin == "mapa":
                    datoteke = [dialog.select_folder_finish(izid)]
                else:
                    datoteke = [dialog.open_finish(izid)]
            except GLib.Error:      # preklic (Gtk.DialogError.DISMISSED)
                datoteke = []
            poti = [f.get_path() for f in datoteke if f is not None and f.get_path()]
            konec(poti)
        if nacin == "datoteke":
            izbira.open_multiple(stars, None, izbrano)
        elif nacin == "mapa":
            izbira.select_folder(stars, None, izbrano)
        else:
            izbira.open(stars, None, izbrano)

    def _odstrani_lokalni_medij(self, pot: str) -> bool:
        if not self._medijska_knjiznica().dobi(pot):
            return False
        self._medijska_knjiznica().odstrani(pot)
        self._dogodek("medijskaKnjiznica", None)
        return True

    def _odpri_medijski_tok(self, url: str) -> bool:
        vnos = self._medijska_knjiznica().dobi_tok(url)
        if not vnos:
            return False
        return self._predvajaj_neposredno(vnos["url"], vrsta=vnos["vrsta"],
                                         prikazi=vnos["vrsta"] == "tv", ime=vnos["ime"])

    def _odstrani_medijsko_mapo(self, pot: str) -> bool:
        """Mapo odstrani iz knjižnice (datoteke na disku ostanejo nedotaknjene)."""
        odstranjena = self._medijska_knjiznica().odstrani_mapo(pot) is not None
        if odstranjena:
            self._dogodek("medijskaKnjiznica", None)
        return odstranjena

    def _odstrani_medijski_tok(self, url: str) -> bool:
        odstranjen = self._medijska_knjiznica().odstrani_tok(url)
        if odstranjen:
            self._dogodek("medijskaKnjiznica", None)
        return odstranjen

    def _medijski_dodaj_datoteke(self, stars=None, konec: Optional[Callable] = None) -> None:
        def izbrano(poti: list) -> None:
            try:
                dodaj(poti)
            except Exception as e:  # noqa: BLE001 - stran vseeno dobi odgovor
                print("[SafeerOS] dodajanje medija:", e)
            finally:
                if konec is not None:
                    konec(None)

        def dodaj(poti: list) -> None:
            poti = poti[:500]
            if poti:
                self._medijska_knjiznica().dodaj(poti)
                for pot in poti:
                    vrsta = os_knjiznica.vrsta_datoteke(Path(pot))
                    if not vrsta or vrsta == "slike":
                        continue
                    try:
                        from core import os_dvd
                        uri = os_dvd.uri(pot) if os_dvd.je_dvd(pot) else GLib.filename_to_uri(pot, None)
                        if self._medijski_predvajalnik is None:
                            self._predvajaj_neposredno(uri, prikazi=vrsta != "glasba")
                        else:
                            self._medijski_predvajalnik.dodaj(uri)
                    except ValueError as e:
                        print("[SafeerOS] dodajanje medija:", e)
                self._dogodek("medijskaKnjiznica", None)
        self._izberi_poti(self._mb("dodaj_datoteke"), stars or self._medijski_predvajalnik_okno or self.okno,
                          "datoteke", izbrano, potrdi=self._mb("dodaj"))

    def _izberi_mapo(self, zacetna: str = "", naslov: str = "", preklici: str = "", izberi: str = "",
                     konec: Optional[Callable[[str], None]] = None) -> None:
        """Obicajno okno za izbiro mape (kam ustvariti novo mapo ali datoteko). konec('') ob preklicu.
        Besedila poda stran v jeziku vmesnika (GTK4 Gtk.FileDialog nima napisa za Preklici - ostane sistemski)."""
        stars = self.okno_delovna if (self.okno is None or not self.okno.get_visible()) else self.okno
        self._izberi_poti(naslov or self._mb("izberi_mapo_splosno"), stars, "mapa",
                          lambda poti: konec and konec(poti[0] if poti else ""),
                          potrdi=izberi or self._mb("izberi"), zacetna=os.path.expanduser(zacetna or "~"))

    def _medijski_dodaj_mapo(self, stars=None, konec: Optional[Callable[[bool], None]] = None) -> None:
        def izbrano(poti: list) -> None:
            if not poti:
                konec and konec(False)
                return
            mapa = poti[0]

            def uvozi():
                try:
                    self._medijska_knjiznica().dodaj_mapo(mapa)
                    self._dogodek("medijskaKnjiznica", None)
                except Exception as e:  # noqa: BLE001
                    print("[SafeerOS] medijska mapa:", e)
                    self._dogodek("medijskaNapaka", "")
            threading.Thread(target=uvozi, daemon=True).start()
            konec and konec(True)
        self._izberi_poti(self._mb("dodaj_mapo"), stars or self.okno, "mapa", izbrano, potrdi=self._mb("dodaj"))

    def _medijski_osvezi_mape(self) -> bool:
        if self._medijsko_osvezevanje or not self._medijska_knjiznica().seznam_map():
            return False
        self._medijsko_osvezevanje = True

        def osvezi():
            try:
                self._medijska_knjiznica().osvezi_mape()
                self._dogodek("medijskaKnjiznica", None)
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] osvežitev medijev:", e)
                self._dogodek("medijskaNapaka", "")
            finally:
                self._medijsko_osvezevanje = False
                self._dogodek("medijskoOsvezevanje", False)

        threading.Thread(target=osvezi, daemon=True).start()
        return True

    def _medijski_dodaj_tok(self, stars=None, konec: Optional[Callable[[bool], None]] = None) -> None:
        """Uporabnikov neposredni tok shrani in predvaja v GStreamerju. GTK4: Gtk.Dialog.run je odstranjen - okno z
        gumboma, izid dobi konec(True/False)."""
        dialog = Gtk.Window(title=self._mb("tok_naslov"), modal=True)
        dialog.set_transient_for(stars or self.okno)
        _razred_okna(dialog, "Dialog")
        dialog.set_destroy_with_parent(True)
        polja = _robovi_gradnika(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8), 12)
        ime = Gtk.Entry()
        ime.set_placeholder_text(self._mb("tok_ime"))
        polja.append(ime)
        vrste = (("tv", self._mb("tok_tv")), ("radio", self._mb("tok_radio")))
        vrsta = Gtk.DropDown.new_from_strings([napis for _k, napis in vrste])
        vrsta.set_selected(0)
        polja.append(vrsta)
        vnos = Gtk.Entry()
        vnos.set_placeholder_text(self._mb("tok_primer"))
        vnos.set_width_chars(55)
        polja.append(vnos)
        gumbi = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.END)
        preklici, shrani = Gtk.Button(label=self._mb("preklici")), Gtk.Button(label=self._mb("shrani_predvajaj"))
        gumbi.append(preklici)
        gumbi.append(shrani)
        polja.append(gumbi)
        dialog.set_child(polja)
        koncano = []

        def odgovor(ok: bool) -> None:
            if koncano:
                return
            koncano.append(True)
            izid = False
            if ok:
                try:
                    izbrana = vrsta.get_selected()
                    vrsta_toka = vrste[izbrana][0] if 0 <= izbrana < len(vrste) else "tv"
                    izid = self._shrani_medijski_tok(ime.get_text().strip(), vnos.get_text().strip(), vrsta_toka)
                except Exception as e:  # noqa: BLE001 - okno se mora vedno zapreti, stran dobi odgovor
                    if not isinstance(e, ValueError):
                        print("[SafeerOS] medijski tok:", e)
                    izid = False
            dialog.destroy()
            if konec is not None:
                konec(izid)
        preklici.connect("clicked", lambda *_a: odgovor(False))
        shrani.connect("clicked", lambda *_a: odgovor(True))
        dialog.connect("close-request", lambda *_a: (odgovor(False), True)[1])
        _tipke(dialog, lambda _d, e: Gdk.keyval_name(e.keyval) == "Escape" and (odgovor(False) or True))
        dialog.present()

    def _shrani_medijski_tok(self, ime: str, url: str, vrsta: str) -> bool:
        os_predvajalnik.medij(url, vrsta)
        self._medijska_knjiznica().dodaj_tok(ime, url, vrsta)
        self._dogodek("medijskaKnjiznica", None)
        if not self._odpri_medijski_tok(url):
            self._dogodek("medijskaNapaka", "")
        return True

    def _odpri_lahki_medijski_pogled(self, naslov: str) -> bool:
        """En WebKit brez JavaScripta; če ni medija, enkrat poskusi z JavaScriptom."""
        if not self._ustvari_medijski_pogled():
            return False          # brez peskovnika: kar že igra, igra naprej; uporabnik je dobil pojasnilo
        self._ustavi_neposredni_medij()
        self._zapusti_skladbo_youtube()
        self._medijski_rod += 1
        self._medijski_naslov = naslov
        self._medijski_js = False
        self._medijski_pogled.get_settings().set_property("enable-javascript-markup", False)
        self._medijski_pogled.load_uri(naslov)
        self._pokazi_medijsko_plast(self._mb("medijski_center"))
        return True

    def _ustvari_medijski_pogled(self) -> bool:
        """Lahki pogled za vdelano stran ali vgradni predvajalnik. False: peskovnika ni mogoče zagnati - pogleda ne
        ustvarimo (glej _peskovnik_na_voljo), uporabnik dobi pojasnilo."""
        if self._medijski_pogled is not None:
            return True
        if not self._peskovnik_na_voljo():
            self._dogodek("medijBrezPeskovnika", True)
            return False
        # Tuje strani v lastnem, zacasnem kontekstu s peskovnikom: nic piskotkov/podatkov Safeer OS in
        # locen spletni proces, ki ga ob izhodu z vsebine izpraznemo.
        # WebKitGTK 6.0: zacasni podatki so na seji (NetworkSession.new_ephemeral), peskovnik je vedno vklopljen;
        # svoj WebContext = svoj spletni proces.
        kontekst = WebKit2.WebContext()
        # Brez set_cache_model: model je v WebKitGTK globalen (LegacyGlobalSettings), DOCUMENT_VIEWER bi Spletu vzel
        # back-forward cache (0 strani) in predpomnilnik - model doloca profil naprave (core/profil_naprave.py).
        from core import jeziki_strani
        jeziki_strani.nastavi(kontekst)
        # Edino sporocilo, ki ga ta pogled sme poslati Safeer OS: stanje skladbe v vgradnem predvajalniku
        # (igra, premor, konec, napaka). Mostu Safeer OS (safeerOs) tu ni.
        upravitelj = WebKit2.UserContentManager()
        namesti_most_skladbe(upravitelj, self._na_stanje_skladbe)
        odlozisce_varuh.dodaj(WebKit2, upravitelj)
        # Scit tudi v YouTubu Medijskega centra (vdelan predvajalnik): ista skripta kot v Spletu - oglasi, preskok
        # neprekinljivih, protiblokada (lastnik 17. 10. 2026: »pri oglasih ne sprejemamo kompromisov«).
        from core import adblock
        upravitelj.add_script(WebKit2.UserScript(
            adblock.YOUTUBE_ADBLOCK_SCRIPT, WebKit2.UserContentInjectedFrames.ALL_FRAMES,
            WebKit2.UserScriptInjectionTime.START,
            ["*://*.youtube.com/*", "*://youtube.com/*", "*://*.youtube-nocookie.com/*"], None))
        # Stevec Scita: YouTube skripta tece v glavnem svetu in odstranjene oglase javi z dogodkom DOM; bere ga samo
        # rele z mostom v locenem svetu (core/os_splet.namesti_stevec). Brez njega se je stetje Medijskega centra
        # izgubilo - stevec Scita je stel samo Splet.
        from core.os_splet import namesti_stevec
        namesti_stevec(WebKit2, upravitelj, lambda _u, r: self._stevec_medija(r))
        lastnosti = {"web_context": kontekst, "user_content_manager": upravitelj,
                     "network_session": WebKit2.NetworkSession.new_ephemeral()}
        if hasattr(WebKit2, "WebsitePolicies"):
            # Medijski pogled odpre uporabnik zato, da nekaj predvaja: predvajanje se zacne brez dodatnega klika.
            lastnosti["website_policies"] = WebKit2.WebsitePolicies(autoplay=WebKit2.AutoplayPolicy.ALLOW)
        pogled = WebKit2.WebView(**lastnosti)
        pogled.connect("decide-policy", self._medijski_odlocitev)
        nastavitve = pogled.get_settings()
        # Scit tudi tu (lastnik 18. 10. 2026: »nihce ne sme slediti uporabnikom«): proti prstnim odtisom, sledilci in
        # telemetrija (core/scit_pravila.py) ter EasyList kot v Spletu - za YouTube, RTV 365 in strani virov.
        from core import scit_pravila
        scit_pravila.zasebnost_pogleda(WebKit2, nastavitve)
        self._sledilci_v_pogled(pogled)
        # Skripte strani izklopimo (markup), API skripte ostanejo - z njimi preverimo, ali je na strani video.
        nastavitve.set_property("enable-javascript-markup", False)
        nastavitve.set_property("enable-webgl", False)
        pogled.connect("load-changed", self._medijski_nalozen)
        # Lastnik, 17. 10. 2026: ne svoje okno, ampak plast v oknu Medijskega centra (core/os_medijska_plast.py).
        self._medijska_plast = os_medijska_plast.MedijskaPlast(Gtk, pogled, self._mb, self._medijska_plast_nazaj)
        self._medijska_plast_css()
        self._medijski_pogled = pogled
        # EasyList (isti preveden filter kot Splet) tudi na ta pogled - samo ze preveden: pretvorba seznama v Pythonu bi
        # procesu pustila ~150 MiB (meritev 11. 10. 2026), tega predvajanje skladbe ne sme sproziti.
        self._vgrajeno_filter(pripravi=False)
        return True

    def _stevec_medija(self, rezultat) -> None:
        """Sporocilo releja stevca iz medijskega pogleda: iste meje (adblock.preveri_stevec), isti stevec kot Splet."""
        from core import adblock
        try:
            s = adblock.preveri_stevec(json.loads(rezultat.to_json(0)))
        except Exception:  # noqa: BLE001 - neveljavno sporocilo strani
            s = None
        if not s:
            return
        c = self._config_spleta()
        if s["action"] == "increment_ads":
            c.increment_ads_blocked(s["count"])
        else:
            c.increment_threats_blocked(s["count"])

    def _medijska_plast_css(self) -> None:
        """Barve pasu plasti iz tokens.css (en vir barv), enkrat na proces."""
        if getattr(self, "_plast_css", None) is not None:
            return
        try:
            besedilo = os_medijska_plast.css_pasu(os_lupina.tokeni())
            self._plast_css = _css(besedilo) if besedilo else False
        except Exception as e:  # noqa: BLE001 - brez sloga pas ostane v temi GTK
            print("[SafeerOS] slog medijske plasti:", type(e).__name__, flush=True)
            self._plast_css = False

    def _medijsko_okno_cilj(self):
        """(okno, prekrivanje) Medijskega centra, v katerem se pokaze vgrajeni predvajalnik: okno strani, ki je
        predvajanje zacela (glavno okno ne v namiznem nacinu - tam je ozadje), sicer Safeer Player; ce ga ni, ga odpre."""
        prekrivanja = getattr(self, "_prekrivanja", None) or {}
        pari = [(self.okno_predvajalnik, self.pogled_predvajalnik)]
        if not self.namizje:
            pari.append((self.okno, getattr(self, "pogled", None)))
        klicatelj = getattr(self, "_katalog_pogled", None)
        for okno, pogled in pari:
            if okno is not None and pogled is not None and pogled is klicatelj and okno.get_visible() \
                    and id(pogled) in prekrivanja:
                return okno, prekrivanja[id(pogled)]
        if self.okno_predvajalnik is None or id(self.pogled_predvajalnik) not in prekrivanja:
            self._odpri_predvajalnik()
            prekrivanja = getattr(self, "_prekrivanja", None) or {}
        if self.okno_predvajalnik is None or id(self.pogled_predvajalnik) not in prekrivanja:
            return None, None
        return self.okno_predvajalnik, prekrivanja[id(self.pogled_predvajalnik)]

    def _pokazi_medijsko_plast(self, naslov: Optional[str] = None) -> bool:
        """Plast predvajalnika v oknu Medijskega centra (glej _medijsko_okno_cilj) in okno v ospredje."""
        plast = self._medijska_plast
        if plast is None:
            return False
        okno, prekrivanje = self._medijsko_okno_cilj()
        if okno is None:
            return False
        plast.postavi(okno, prekrivanje)
        plast.pokazi(naslov)
        if okno is self.okno_predvajalnik:
            okno.maximize()                  # Safeer Player je vedno cez cel zaslon (lastnik, 11. 10. 2026)
        _v_ospredje(okno)
        return True

    def _plast_tipka(self, okno, dogodek) -> bool:
        plast = self._medijska_plast
        if plast is None or plast.okno is not okno:
            return False
        return plast.tipka(Gdk.keyval_name(dogodek.keyval) or "")

    def _medijska_plast_nazaj(self) -> None:
        """»Nazaj na Medijski center«: skladba s seznama igra naprej (mini predvajalnik jo pokaze, klik nanj vrne plast);
        vdelana stran brez upravljanja v mini predvajalniku se ustavi - sicer bi igrala nevidno in brez gumba."""
        if getattr(self, "_medijski_skladba", False):
            self._yt_spremenjeno()
        else:
            self._pocisti_medijski_pogled()
        plast = self._medijska_plast
        okno = plast.okno if plast is not None else None
        pogled = self.pogled_predvajalnik if okno is not None and okno is self.okno_predvajalnik else getattr(self, "pogled", None)
        if pogled is not None:
            pogled.grab_focus()

    # -- skladba s seznama predvajanja: vgradni predvajalnik YouTuba v lahkem pogledu (core/os_katalog.py)
    def _katalog_youtube(self, naslov: str, ime: str) -> bool:
        """Vgradni predvajalnik YouTuba (ali, ce vgradnja ni dovoljena, stran posnetka) v lahkem pogledu; stanje skladbe
        javi skript (os_katalog.SKRIPT_SKLADBE)."""
        vgradnja = os_katalog.je_naslov_vgradnje(naslov)
        if not vgradnja and not os_katalog.je_naslov_strani(naslov):
            return False
        if not self._ustvari_medijski_pogled():
            return False          # brez peskovnika (glej _odpri_lahki_medijski_pogled)
        self._ustavi_neposredni_medij()
        self._medijski_rod += 1
        self._medijski_naslov = ""          # brez preverbe »ali je na strani video« (ta velja za tuje strani)
        self._medijski_js = True
        self._medijski_skladba = True
        self._medijski_pogled.get_settings().set_property("enable-javascript-markup", True)
        self._medijska_plast.nastavi_naslov(ime or self._mb("medijski_center"))
        self._yt_prijava_v_medijski_pogled()
        zahteva = WebKit2.URIRequest.new(naslov)
        if vgradnja:
            # YouTube vgradnjo dovoli samo znanemu izvoru; Safeer se predstavi enako kot na Windows.
            zahteva.get_http_headers().append("Referer", os_katalog.IZVOR_VGRADNJE)
        self._medijski_pogled.load_request(zahteva)
        if not getattr(self, "_medijski_skladba_videna", False):
            # Prvic plast pokazemo v oknu Medijskega centra; naslednja skladba je ne vrine nazaj, ce se je uporabnik
            # vrnil v katalog (glasba igra naprej, mini predvajalnik jo pokaze).
            self._pokazi_medijsko_plast()
        self._medijski_skladba_videna = True
        GLib.idle_add(lambda: self._yt_spremenjeno() and False)   # ko katalog zapise skladbo (glej _predvajaj_razresen)
        return True

    def _yt_prijava_v_medijski_pogled(self) -> None:
        """Ce je uporabnik v Spletu prijavljen v YouTube, dobi lahki (sicer zacasni, brez piskotkov) pogled piskotke
        youtube.com - samo te. Brez njih YouTube vgrajen predvajalnik zahteva »Prijavite se in potrdite, da niste
        bot« (testni PC 17. 10. 2026, seznam Favorites)."""
        try:
            from core import youtube_racun
            gi.require_version("Soup", "3.0")
            from gi.repository import Soup
            piskotki = youtube_racun.beri_piskotke(youtube_racun.pot_piskotkov())
            if not youtube_racun.prijavljen(piskotki):
                return
            upravitelj = self._medijski_pogled.get_network_session().get_cookie_manager()
            for ime, vrednost in piskotki.items():
                c = Soup.Cookie.new(ime, vrednost, ".youtube.com", "/", 6 * 3600)
                c.set_secure(True)
                c.set_http_only("APISID" not in ime)          # SAPISID beri skript YouTuba (glava SAPISIDHASH)
                upravitelj.add_cookie(c, None, None, None)
        except Exception as e:  # noqa: BLE001 - brez prijave predvaja kot prej
            print("[Safeer OS] YouTube prijava v predvajalnik:", type(e).__name__, flush=True)

    def _medijski_odlocitev(self, _pogled, odlocitev, vrsta) -> bool:
        """Lahki pogled ne odpira novih oken; med skladbo klik na povezavo ne zapusti predvajalnika."""
        if vrsta == WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION:
            odlocitev.ignore()
            return True
        if vrsta == WebKit2.PolicyDecisionType.NAVIGATION_ACTION and getattr(self, "_medijski_skladba", False):
            try:
                dejanje = odlocitev.get_navigation_action()
                if (dejanje.get_navigation_type() == WebKit2.NavigationType.LINK_CLICKED
                        and not os_katalog.je_naslov_vgradnje(dejanje.get_request().get_uri() or "")
                        and not os_katalog.je_naslov_strani(dejanje.get_request().get_uri() or "")):
                    odlocitev.ignore()
                    return True
            except Exception:  # noqa: BLE001
                pass
        return False

    def _katalog_youtube_ukaz(self, ukaz: str) -> bool:
        if not getattr(self, "_medijski_skladba", False) or self._medijski_pogled is None:
            return False
        if ukaz == "zapri":
            self._pocisti_medijski_pogled()
            return True
        if ukaz not in ("playVideo", "pauseVideo"):
            return False
        self._medijski_pogled.evaluate_javascript("window.safeerUkaz && window.safeerUkaz(%s)" % json.dumps(ukaz),
                                                  -1, None, None, None, None)
        return True

    def _na_stanje_skladbe(self, _upravitelj, rezultat) -> None:
        if not getattr(self, "_medijski_skladba", False) or self._katalog is None:
            return
        try:
            self._katalog.yt_sporocilo(rezultat.to_string())
            self._yt_spremenjeno()
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] stanje skladbe:", e)

    def _zapusti_skladbo_youtube(self) -> None:
        if getattr(self, "_medijski_skladba", False):
            self._medijski_skladba = False
            self._medijski_skladba_videna = False
            if self._katalog is not None:
                self._katalog.yt_zaprt()
                self._yt_spremenjeno()

    def _medijski_nalozen(self, pogled, dogodek) -> None:
        if dogodek != WebKit2.LoadEvent.FINISHED or not self._medijski_naslov:
            return
        rod = self._medijski_rod
        GLib.timeout_add(1800, lambda: self._preveri_medijski_pogled(pogled, rod))

    def _preveri_medijski_pogled(self, pogled, rod: int) -> bool:
        if rod != self._medijski_rod or not self._medijski_naslov:
            return False

        def koncano(p, rezultat):
            if rod != self._medijski_rod:
                return
            najden = False
            try:
                vrednost = p.evaluate_javascript_finish(rezultat)
                najden = bool(vrednost.to_boolean())
            except Exception:
                pass
            if najden:
                return
            if not self._medijski_js:
                self._medijski_js = True
                p.get_settings().set_property("enable-javascript-markup", True)
                p.reload()
            else:
                naslov = self._medijski_naslov
                self._pocisti_medijski_pogled()
                self._splet(naslov)

        pogled.evaluate_javascript(
            "!!document.querySelector('video, audio, source[src], video source, audio source')",
            -1, None, None, None, koncano)
        return False

    def _pocisti_medijski_pogled(self) -> None:
        """Ob izhodu odstrani stran in njen predpomnilnik, pogled pa ohrani za naslednjič."""
        self._zapusti_skladbo_youtube()
        self._medijski_rod += 1
        self._medijski_naslov = ""
        self._medijski_js = False
        if self._medijski_pogled is None:
            return
        try:
            self._medijski_pogled.load_uri("about:blank")
            self._medijski_pogled.get_settings().set_property("enable-javascript-markup", False)
            seja = self._medijski_pogled.get_network_session() if hasattr(self._medijski_pogled, "get_network_session") \
                else None   # WebKitGTK 6.0: podatki so na seji; 4.1: na kontekstu
            upravitelj = (seja or self._medijski_pogled.get_context()).get_website_data_manager()
            vrste = WebKit2.WebsiteDataTypes.MEMORY_CACHE | WebKit2.WebsiteDataTypes.DISK_CACHE
            upravitelj.clear(vrste, 0, None, None, None)
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] čiščenje medijskega pogleda:", e)
        if self._medijska_plast is not None:
            self._medijska_plast.skrij()

    def _prijavno_okno_ob_prijavi(self) -> bool:
        """Ob prijavi v namizje (delovna povrsina) ponudi povezavo v Safeer Link - ne z oknom cez namizje, ampak s tihim
        obvestilom z gumbom »Poveži« (lastnik, 13. 10. 2026: okno takoj ob zagonu ni vsec; prej 12. 10. okno). Ne pokaze ga, ce je racunalnik ze povezan (zaupan racunalnik po ponovnem
        zagonu ali odjavi iz seje; nezaupan v isti seji), ce je uporabnik v tej seji ze izbral »Nadaljuj brez povezave«
        ali ce je bil v tej seji ze pokazan (ponovni zagon delovne povrsine po sesutju ne sme znova vsiljevati okna)."""
        from core import link_seja
        try:
            c = en_proces.control_app()
            link = getattr(c, "link", None) if c is not None else None
            if link is None:
                # Control se vgradi ~3 s po zagonu: pocakamo do ~40 s, nato (locen Control) okno odpre uporabnik sam.
                self._prijava_poskusi = getattr(self, "_prijava_poskusi", 0) + 1
                return self._prijava_poskusi < 10
            podatki = link.nastavitve.podatki
            if link_seja.povezava_velja(podatki) or link._v_krogu() or link_seja.brez_v_seji(podatki):
                return False
            seja = link_seja.trenutna_seja()
            if self.shramba.get("prijavno_okno_seja") == seja:
                return False
            self.shramba.set("prijavno_okno_seja", seja)
        except Exception as e:  # noqa: BLE001 - brez prijavnega okna namizje vseeno deluje
            print("[SafeerOS] prijavno okno ob prijavi:", e, flush=True)
            return False
        self._ponudi_prijavo()
        return False

    _PRIJAVA_OBVESTILO = {
        "sl": ("Safeer Link", "Naprave niso povezane s tem računalnikom.", "Poveži"),
        "en": ("Safeer Link", "Your devices are not connected to this computer.", "Connect"),
        "de": ("Safeer Link", "Deine Geräte sind nicht mit diesem Computer verbunden.", "Verbinden"),
        "es": ("Safeer Link", "Tus dispositivos no están conectados a este ordenador.", "Conectar"),
        "fr": ("Safeer Link", "Vos appareils ne sont pas connectés à cet ordinateur.", "Connecter"),
        "it": ("Safeer Link", "I tuoi dispositivi non sono collegati a questo computer.", "Collega"),
    }

    def _ponudi_prijavo(self) -> None:
        """Obvestilo namizja (brez okna): klik nanj ali na »Poveži« odpre prijavno okno Safeer Linka."""
        naslov, besedilo, gumb = self._PRIJAVA_OBVESTILO.get(_jezik(), self._PRIJAVA_OBVESTILO["en"])
        try:
            if self.lookup_action("prijava-iz-obvestila") is None:
                dejanje = Gio.SimpleAction.new("prijava-iz-obvestila", None)
                dejanje.connect("activate", lambda *_a: self._prijava())
                self.add_action(dejanje)
            obvestilo = Gio.Notification.new(naslov)
            obvestilo.set_body(besedilo)
            obvestilo.set_icon(Gio.ThemedIcon.new("safeer-control"))
            obvestilo.set_priority(Gio.NotificationPriority.LOW)
            obvestilo.set_default_action("app.prijava-iz-obvestila")
            obvestilo.add_button(gumb, "app.prijava-iz-obvestila")
            self.send_notification("safeer-link-prijava", obvestilo)
        except Exception as e:  # noqa: BLE001 - brez obvestila namizje deluje; povezava je v Napravah
            print("[SafeerOS] obvestilo prijave:", e, flush=True)

    def _prijava(self) -> bool:
        """Prijavno okno Safeer Linka (QR / koda / brez povezave) - zanj skrbi Safeer Control; okno je nad
        Safeer OS in se po prijavi samo zapre."""
        threading.Thread(target=lambda: control_dejanje("prijava") or self._odpri_control(), daemon=True).start()
        return True

    def _odpri_control(self) -> bool:
        """Safeer Control: prijavno okno (QR / koda) ali seznam naprav, ce je racunalnik ze povezan.

        Control v tem procesu (core/en_proces.py) pokaze okno neposredno. Prej je vedno zagnal nov proces
        safeer-control, ki je vgrajenemu Controlu poslal Activate - ta ga je prvo minuto po zagonu prezrl (pregled
        celovitosti 15. 10. 2026). Ce Control se ne tece, ga Safeer OS najprej vgradi (en proces); locen proces
        ostane samo, kadar vgradnja ni mogoca."""
        def v_procesu() -> bool:
            c = en_proces.control_app()
            if c is None and self._vgradi_control():
                c = en_proces.control_app()
            if c is None:
                return False
            c.pokazi_okno()
            return True
        try:
            if en_proces.na_glavni(v_procesu, cas=20.0, privzeto=False):
                return True
        except Exception as e:  # noqa: BLE001 - locen proces kot prej
            print("[SafeerOS] Control v procesu:", e, flush=True)
        ukaz = _ukaz_controla()
        if not ukaz:
            return False
        try:
            subprocess.Popen(ukaz, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return True
        except Exception:
            return False


def _velikost_okna(vrednost: str):
    """SAFEER_OS_OKNO kot »1280x800«; ob nerazumljivi vrednosti None (okno naj bo celozaslonsko).

    Napacna spremenljivka okolja ne sme podreti izdelave okna - brez okna Safeer OS samo visi.
    """
    deli = (vrednost or "").lower().split("x")
    if len(deli) != 2:
        return None
    try:
        sirina, visina = int(deli[0]), int(deli[1])
    except ValueError:
        return None
    if sirina < 200 or visina < 200:
        return None
    return sirina, visina


def main() -> int:
    global VARNI_NACIN
    if "--version" in sys.argv[1:]:
        print("Safeer OS", RAZLICICA)
        return 0
    magnet = ""
    zastavica = "--magnet-naprava" if "--magnet-naprava" in sys.argv[1:] else "--magnet"
    if zastavica in sys.argv[1:]:
        # Magnet povezava (brskalnik, druga naprava v Linku): ce Safeer OS ze tece, jo preda njemu
        # (org.gtk.Actions) in konca - brez popravkov po sesutju, ki sodijo samo k pravemu zagonu.
        # --magnet-naprava (samo ukaz z naprave v krogu, core/link_daljinec.py) sme predvajati takoj;
        # --magnet (brskalnik, druge aplikacije) le pokaže povezavo - uporabnik pritisne Odpri.
        i = sys.argv.index(zastavica)
        magnet = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
        if os_torrent.razcleni_magnet(magnet) is None:
            print("To ni veljavna magnet povezava.")
            return 2
        if zastavica == "--magnet-naprava":
            magnet = "naprava:" + magnet
        try:
            if _predaj_tekocemu("magnet", magnet):
                return 0
        except Exception as e:  # noqa: BLE001 - Safeer OS ne tece: zazenemo ga z magnetom
            print("[SafeerOS] magnet:", e)
    if "--medij-naprava" in sys.argv[1:]:
        # media.open z naprave v krogu: preda tekocemu Safeer OS (Safeer Player isce naslov), sicer zazene Safeer Player.
        i = sys.argv.index("--medij-naprava")
        podatki = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
        try:
            if _predaj_tekocemu("medij", podatki):
                return 0
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] medij:", e)
        sys.argv = [sys.argv[0], "--predvajalnik"]       # Safeer OS ni tekel: odpre se Safeer Player
    if "--isci-naprava" in sys.argv[1:]:
        # Glas s telefona (search.query): niz preda tekocemu Safeer OS; ce ne tece, ga zaradi iskanja ne zaganjamo.
        i = sys.argv.index("--isci-naprava")
        niz = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
        try:
            return 0 if _predaj_tekocemu("isci", niz) else 3
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] isci:", e)
            return 3
    stremio_url = ""
    if "--stremio" in sys.argv[1:]:
        # Gumb »Install« na strani z dodatki Stremio (x-scheme-handler/stremio): preda tekocemu Safeer OS, sicer zazene
        # Safeer Player, ki pokaze okno Dodatki. Nic se ne doda brez uporabnika.
        i = sys.argv.index("--stremio")
        stremio_url = media_servers.stremio_naslov_dodatka(sys.argv[i + 1] if i + 1 < len(sys.argv) else "")
        if not stremio_url:
            print("To ni naslov dodatka Stremio.")
            return 2
        try:
            if _predaj_tekocemu("stremio", stremio_url):
                return 0
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] stremio:", e)
        sys.argv = [sys.argv[0], "--predvajalnik"]
    datoteka = ""
    if "--predvajaj" in sys.argv[1:]:
        # Datoteka z diska: ce Safeer OS ze tece, jo preda njemu (org.gtk.Actions) in konca, sicer se zazene
        # kot okno in jo predvaja, ko je okno pripravljeno.
        i = sys.argv.index("--predvajaj")
        datoteka = os.path.realpath(sys.argv[i + 1]) if i + 1 < len(sys.argv) else ""
        if not os.path.isfile(datoteka):
            print("Te datoteke ni.")
            return 2
        try:
            if _predaj_tekocemu("predvajaj", datoteka):
                return 0
        except Exception as e:  # noqa: BLE001 - Safeer OS ne tece: zazenemo ga z datoteko
            print("[SafeerOS] predvajaj:", e)
    predvajalnik = zagon_predvajalnika(sys.argv[1:])
    if predvajalnik and "--posnetek" not in sys.argv[1:]:
        # Safeer Player (meni, zaganjalnik): ce Safeer OS ze tece (delovna povrsina, okno), odpre okno Safeer Player
        # v njem in konca - predvajanje, mini predvajalnik delovne povrsine in Safeer Link ostanejo eni.
        try:
            if _predaj_tekocemu("predvajalnik", ""):
                return 0
        except Exception as e:  # noqa: BLE001 - Safeer OS ne tece: zazenemo ga kot Safeer Player
            print("[SafeerOS] predvajalnik:", e)
    if "--razdelek" in sys.argv[1:]:
        # Vnos okna v docku (Splet, Sporocila …): ce Safeer OS tece, odpre okno razdelka v njem; sicer se zazene kot okno.
        i = sys.argv.index("--razdelek")
        razdelek = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
        try:
            if razdelek in OKNA_V_PULTU and _predaj_tekocemu("razdelek", razdelek):
                return 0
        except Exception as e:  # noqa: BLE001 - Safeer OS ne tece: zazenemo ga v oknu
            print("[SafeerOS] razdelek:", e)
        sys.argv = [sys.argv[0], "--okno"]
    ponudba_json = ""
    if "--ponudba" in sys.argv[1:]:
        # Sprejeta ponudba "Poslji na napravo" (Safeer Control, ko Safeer OS se ne tece).
        i = sys.argv.index("--ponudba")
        ponudba_json = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
    if "--nazaj-na-cinnamon" in sys.argv[1:] or "--back-to-cinnamon" in sys.argv[1:]:
        return ukaz_nazaj_na_cinnamon()
    if "--vrni-mint" in sys.argv[1:] or "--restore-mint" in sys.argv[1:]:
        # Samo povrnitev Mintovega pulta, brez okna in brez WebKita: to poklice zaganjalnik, ko
        # odneha, in uporabnik iz terminala, ce bi Safeer OS kdaj pustil namizje brez pulta.
        shramba = os_programi.Shramba()
        vrnjeno = popravi_po_sesutju(shramba)
        print("Mintov pult je vrnjen." if vrnjeno else "Mintov pult ni bil skrit; nicesar ni bilo treba vrniti.")
        return 0
    # Sled ob sesutju (tudi ob SIGSEGV v knjiznici C) in dnevnik neujetih izjem; brez tega je ob
    # sesutju ostalo samo prazno namizje in nobenega podatka o tem, kaj je teklo.
    os_stabilnost.vkljuci("safeer-os")
    # print() je sel na stdout (/dev/null pri zagonu iz menija): odslej v sled.log, brez skrivnosti.
    os_stabilnost.preusmeri_izpis()
    # Pod varuhom (core/varuh_procesov.py): NOTIFY_SOCKET ne gre naprej programom, ki jih Safeer OS zazene. Ce je lupina v
    # svojem procesu, v tem procesu ni Qt (PySide6 bi brez potrebe nalozil knjiznice Qt - RAM).
    varuh_procesov.pripravi_obvestila()
    if lupina_streznik.locena():
        sys.modules["PySide6"] = None
    # Varuh je Safeer OS znova zagnal po sesutju, zamrznitvi ali preveliki porabi pomnilnika: stanje se obnovi.
    obnova_po_napaki = okolje_procesa.prevzemi("SAFEER_OBNOVA")     # prevzeto pred nitmi (core/okolje_procesa.py)
    if os_stabilnost.naj_bo_varni_nacin("safeer-os") and not os_okna.izklopljen():
        # Vec sesutij v kratkem casu: tokrat brez seznama oken (libwnck) in brez skrivanja Mintovega
        # pulta, da je Safeer OS vsaj uporaben in da ima uporabnik pot nazaj v Mint.
        os_okna.izklopi()          # zastavica v procesu: tu ze tecejo niti, setenv ne (core/okolje_procesa.py)
        VARNI_NACIN = True
        os_stabilnost.zapisi("safeer-os", "varni nacin: seznam oken izklopljen, Mintov pult ostane viden")
        print("[SafeerOS] varni način: seznam odprtih oken je izklopljen (glej ~/.cache/safeer-os/dnevnik.log)")
    if popravi_po_sesutju(os_programi.Shramba()):
        # Prejsnji zagon se ni koncal (sesutje, OOM, izklop): pult je bil se skrit. Vrnemo ga zdaj in
        # ga spodaj po potrebi skrijemo znova - tako je zapis v shrambi vedno resnicen.
        os_stabilnost.zapisi("safeer-os", "prejsnji zagon se ni koncal: Mintov pult vrnjen pred zagonom")
    posnetek = ""
    if "--posnetek" in sys.argv[1:]:
        i = sys.argv.index("--posnetek")
        posnetek = sys.argv[i + 1] if i + 1 < len(sys.argv) else "/tmp/safeer-os.png"
    # Ob vklopljenem Safeer Cinnamon je namizje delovna povrsina: Safeer OS iz menija se odpre kot okno
    # (ne cez cel zaslon in brez skrivanja Mintovega pulta).
    cinnamon = _safeer_cinnamon_vklopljen()
    # Proces, ki ga je zagnal Safeer Player, odpre tudi Safeer OS iz menija v oknu (kot ob --predvajaj).
    v_oknu = "--okno" in sys.argv[1:] or bool(magnet) or bool(datoteka) or bool(ponudba_json) or predvajalnik \
        or (cinnamon and "--namizje" not in sys.argv[1:])
    # Wayland (GNOME na Ubuntu 24.04, KDE, sway): namizja pod okni ni - protokol odjemalcu ne da vrste DESKTOP, okna
    # pod vsemi drugimi ne rezervacije roba za vrstico (izmerjeno 18. 10. 2026, brezglavi sway 1.9: privzeti zagon je
    # odprl okno namizja in »Safeer OS vrstica« kot dve navadni okni med programi, vrstica cez tretjino zaslona).
    # --namizje in privzeti zagon zato odpreta aplikacijo Safeer OS v oknu (isto namizje QML); --delovna (Safeer
    # Cinnamon ob prijavi) samo storitve v ozadju (do_activate).
    wayland_okno = seja_prikaza.je_wayland() and not posnetek and not v_oknu and "--delovna" not in sys.argv[1:]
    if wayland_okno:
        v_oknu = True
    # Ubuntu 24.04+: brez nasega profila AppArmor bwrap ne dobi imenskega prostora in WebKit bi ob prvi strani koncal
    # ves proces (g_error). Peskovnik je izklopljen ze pred nitmi (vrh datoteke), samo ce res ne more teci; tu pojasnilo.
    peskovnik = peskovnik_userns.ob_zagonu()
    app = SafeerOS(v_oknu=v_oknu, posnetek=posnetek, namizje="--namizje" in sys.argv[1:],
                   delovna="--delovna" in sys.argv[1:], predvajalnik=predvajalnik)
    if peskovnik.get("izklopljen") and not posnetek:
        peskovnik_userns.pojasni_kasneje(GLib, os.path.join(GLib.get_user_config_dir(), "safeer-os"), _jezik(),
                                         "Safeer OS", "safeer-os", app)
    app._cakajoci_magnet = magnet
    app._obnova_po_napaki = obnova_po_napaki
    app._qml_okno = ("--okno" in sys.argv[1:] or wayland_okno) and not (magnet or datoteka or ponudba_json
                                                                         or predvajalnik or stremio_url)
    app._cakajoci_stremio = stremio_url
    app._cakajoca_datoteka = datoteka
    if ponudba_json:
        try:
            app._cakajoca_ponudba = json.loads(ponudba_json)
        except Exception:  # noqa: BLE001
            app._cakajoca_ponudba = None
    if app._qml_okno:
        try:
            app.register(None)
            if app.get_is_remote():
                app.activate_action("okno-qml", None)   # primerek, ki tece, naj odpre namizje QML v oknu
        except Exception:  # noqa: BLE001
            pass
    if "--delovna" in sys.argv[1:]:
        # Ze tece primerek Safeer OS (delovna povrsina, Safeer Player ali okno): drugi zagon ob prijavi ali iz
        # safeer-cinnamon mu preda dejanje »delovna« (_vklopi_delovno) - aktivacija bi odprla glavno okno, tihi konec
        # pa je pustil sejo brez delovne povrsine do naslednje prijave (pregled celovitosti 15. 10. 2026).
        try:
            if _predaj_ce_oddaljen(app, "delovna"):
                return 0
        except Exception:  # noqa: BLE001
            pass
    # Ce program tece brez tezav, zgodovina sesutij ni vec pomembna (sicer bi varni nacin ostal za vedno).
    GLib.timeout_add_seconds(120, lambda: (os_stabilnost.pozabi_sesutja("safeer-os"), False)[1])
    # Zbiranje smeti samo na glavni niti (pregled 18. 10. 2026): samodejni gc v delovni niti (DoH, Link, IMAP ...) je
    # sprostil predmet WebKit/GTK zunaj glavne niti - RELEASE_ASSERT(isMainThread) -> SIGTRAP (signal 5, koda 133).
    from core import runtime_safety
    runtime_safety.install_main_thread_gc()
    koda = app.run([sys.argv[0]])
    if getattr(app, "_ponovni_zagon", False) is True:      # samo pravi zahtevek (ne lazni predmet v preizkusih)
        # Nova razlicica (core/nova_razlicica.py): zaganjalnik jo zazene ob kodi 75, sicer exec nove kode.
        return nova_razlicica.znova("SAFEER_OS_NADZOR", os.path.abspath(__file__), _ZACETNI_ARGV[1:])
    return koda


if __name__ == "__main__":
    sys.exit(main())
