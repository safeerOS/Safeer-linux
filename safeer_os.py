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
  safeer_os.py --posnetek P    izrise stran, shrani posnetek v P (PNG) in konca (preverjanje)

Prvi zagon: ce racunalnik se ni v Safeer Linku in uporabnik ni izbral »Nadaljuj brez povezave
naprav«, Safeer OS odpre prijavno okno Safeer Control (QR / 6-mestna koda / brez povezave).
Naprave lahko uporabnik kadarkoli poveze v razdelku Naprave.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Optional

KOREN = os.path.dirname(os.path.abspath(__file__))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, Gio, GLib, Gtk, WebKit2  # noqa: E402

from core import (os_datoteke, os_knjiznica, os_okna, os_omrezje, os_programi, os_scit, os_sistem,  # noqa: E402
                  os_media_besedila, os_mediji, os_predvajalnik, os_sporocila, os_spletne, os_stabilnost, os_torrent,
                  os_zapiski, os_zvok)

# Preklop vhoda zvocne vrstice JBL je samo interni poskus: uradni paket modula ne vsebuje
# (packaging/install_os_payload.sh), zato ga uvozimo le, ce je prisoten (zagon iz repozitorija).
# Uradna pot za zvocnike v omrezju je splosni DLNA.
try:
    from core import os_jbl  # noqa: E402
except ImportError:
    os_jbl = None


def _jbl_vrstica(ime: str) -> bool:
    return os_jbl is not None and os_jbl.je_vrstica(ime)

APP_ID = "io.github.memelandfaner.SafeerOS"


def _razlicica() -> str:
    try:
        with open(os.path.join(KOREN, "packaging", "VERSION_OS"), encoding="utf-8") as d:
            return d.read().strip()
    except Exception:
        return "0.4.7"


RAZLICICA = _razlicica()
CONTROL_NASTAVITVE = os.path.expanduser("~/.config/safeer-control/link.json")
BRSKALNIK_NASTAVITVE = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                                    "safeer-mint", "settings.json")
ZAPISKI_POT = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                           "safeer-os", "zapiski.json")
ISKALNIKI = {"google": "https://www.google.com/search?q=", "duckduckgo": "https://duckduckgo.com/?q=",
             "brave": "https://search.brave.com/search?q=", "startpage": "https://www.startpage.com/do/search?q=",
             "bing": "https://www.bing.com/search?q=", "ecosia": "https://www.ecosia.org/search?q="}

MOST_JS = r"""
(function () {
  var cakajo = {}, stevec = 0;
  window.__safeerOsOdgovor = function (id, ok, podatki) {
    var c = cakajo[id]; if (!c) return; delete cakajo[id];
    if (ok) c.res(podatki); else c.rej(podatki);
  };
  window.SafeerOS = {
    klic: function (metoda, argumenti) {
      return new Promise(function (res, rej) {
        var id = ++stevec; cakajo[id] = { res: res, rej: rej };
        try {
          window.webkit.messageHandlers.safeerOs.postMessage(JSON.stringify({ id: id, m: metoda, a: argumenti || [] }));
        } catch (e) { delete cakajo[id]; rej(String(e)); }
      });
    }
  };
})();
"""


def _jezik() -> str:
    """Jezik vmesnika: nastavitev Safeer Browserja, sicer jezik seje; podprti sl/en/de/es/fr/it."""
    posnetek = (os.environ.get("SAFEER_OS_JEZIK") or "")[:2].lower()   # samo za razvoj/posnetke
    if posnetek in ("sl", "en", "de", "es", "fr", "it"):
        return posnetek
    try:
        with open(BRSKALNIK_NASTAVITVE, encoding="utf-8") as f:
            v = (json.load(f) or {}).get("ui_language")
        if v:
            return str(v)[:2]
    except Exception:
        pass
    lang = (os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or "en")[:2].lower()
    return lang if lang in ("sl", "en", "de", "es", "fr", "it") else "en"


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


def _iskalnik() -> str:
    try:
        with open(BRSKALNIK_NASTAVITVE, encoding="utf-8") as f:
            ime = (json.load(f) or {}).get("search_engine") or "duckduckgo"
    except Exception:
        ime = "duckduckgo"
    return ISKALNIKI.get(ime, ISKALNIKI["duckduckgo"])


def _podatki_controla() -> dict:
    try:
        with open(CONTROL_NASTAVITVE, encoding="utf-8") as f:
            p = json.load(f) or {}
        return p if isinstance(p, dict) else {}
    except Exception:
        return {}


_hubi_cache: dict = {"cas": 0.0, "hubi": []}


def hubi_v_omrezju(cas: float = 1.5) -> list:
    """Safeer Linki (sredisca), ki se oglasajo v domacem omrezju (mDNS): [{"ime", "naslov"}]. Rezultat velja
    10 s, da Naprave ne iscejo ob vsakem izrisu. Brez knjiznice zeroconf je seznam prazen."""
    if time.time() - _hubi_cache["cas"] < 10:
        return list(_hubi_cache["hubi"])
    try:
        from core import link_hub
        hubi = [{"ime": h.get("ime") or h["naslov"], "naslov": h["naslov"]} for h in link_hub.poisci_hube_mdns(cas)]
    except Exception:
        hubi = []
    _hubi_cache.update(cas=time.time(), hubi=hubi)
    return list(hubi)


def stanje_povezave() -> dict:
    """Ali je racunalnik (Safeer Control) v Safeer Linku: povezan / brez (izbral) / nov.

    Povezava nezaupanega racunalnika velja samo do konca prijave (core/link_seja.py): ob novi
    prijavi je stanje spet »nov« in Safeer OS pokaze prijavno okno."""
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
    izid = {"stanje": stanje, "control": bool(_ukaz_controla()), "zaupana": link_seja.zaupana(p), "hubi": []}
    if stanje != "povezan":
        # Nepovezan racunalnik: Naprave povedo, ali je v omrezju Safeer Link (in kateri), ali ga ni.
        izid["hubi"] = hubi_v_omrezju()
    return izid


CONTROL_ID = "io.github.memelandfaner.SafeerControl"
CONTROL_POT = "/io/github/memelandfaner/SafeerControl"


def nastavi_zaupanje(zaupaj: bool) -> bool:
    """»Zaupaj temu racunalniku«: tekoci Safeer Control dobi odlocitev prek D-Bus (drzi nastavitve v
    pomnilniku in bi jih sicer prepisal); ce ne tece, jo zapisemo v njegove nastavitve sami."""
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


def _control_na_vodilu(vodilo) -> bool:
    return vodilo.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus", "NameHasOwner",
                            GLib.Variant("(s)", (CONTROL_ID,)), GLib.VariantType("(b)"),
                            Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]


def _zagotovi_control(vodilo) -> bool:
    """Control tece (na vodilu) - ce ne, ga zazenemo v ozadju (pladenj) in pocakamo, da se javi."""
    if _control_na_vodilu(vodilo):
        return True
    ukaz = _ukaz_controla()
    if not ukaz:
        return False
    subprocess.Popen(ukaz + ["--ozadje"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    for _ in range(40):
        time.sleep(0.25)
        if _control_na_vodilu(vodilo):
            time.sleep(0.5)
            return True
    return False


def control_dejanje(ime: str, parameter: Optional["GLib.Variant"] = None) -> bool:
    """Dejanje v Safeer Controlu (prijava, nova-naprava, odjava). Ce Control ne tece, ga zazenemo v ozadju
    (pladenj) in pocakamo, da se javi na vodilu. Klicati v ozadju (ne na glavni niti)."""
    try:
        vodilo = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        if not _zagotovi_control(vodilo):
            return False
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
    return stanje


def zvok_na_zvocnik(id_zvocnika: str, potrdi: bool = False) -> dict:
    """Zvok racunalnika na zvocnik v omrezju; tekoco sejo na napravo v Linku najprej koncamo."""
    if os_zvok.link_naprave()["zvok"]["naprava"]:
        control_dejanje("zvok-ustavi")
    return zvocniki().zacni(str(id_zvocnika or ""), bool(potrdi))


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
        podpis = "(" + "s" * len(argumenti) + ")"
        r = vodilo.call_sync(CONTROL_ID, CONTROL_POT + "/naprave", CONTROL_ID + ".Naprave", metoda,
                             GLib.Variant(podpis, tuple(argumenti)) if argumenti else None,
                             GLib.VariantType("(s)"), Gio.DBusCallFlags.NONE, 60000, None)
        izid = json.loads(r.unpack()[0])
        return izid if isinstance(izid, dict) else {"ok": False}
    except Exception as e:  # noqa: BLE001
        print("[SafeerOS] naprave:", metoda, e)
        return {"ok": False, "koda": "napaka", "message": str(e)}


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


def naprave_s_programi() -> list:
    """Naprave v Safeer Linku, ki znajo nasteti in zagnati programe (zmoznost apps ali remote); brez tega
    racunalnika (njegovi programi so ze v meniju)."""
    izid = _control_naprave("Seznam")
    naprave = []
    for n in izid.get("naprave") or []:
        z = n.get("zmoznosti") or []
        # Preskoci samo ta racunalnik. Prej je bila izpuscena vsaka naprava vrste "control", zato Linux ni
        # videl programov racunalnika z Windows (ta se v Link prijavi kot Safeer Control).
        if n.get("ta") or n.get("platforma") == "linux" and socket.gethostname() in n.get("ime", ""):
            continue
        if "apps" in z or "remote" in z:
            naprave.append({"id": n["id"], "ime": n.get("ime", ""), "platforma": n.get("platforma", ""),
                            "vrsta": n.get("vrsta", "")})
    return naprave


def vse_naprave() -> list:
    """Vse naprave v Safeer Linku (tudi ta racunalnik) za stran Naprave: id, ime, platforma, vrsta, ta."""
    izid = _control_naprave("Seznam")
    return [{"id": n.get("id", ""), "ime": n.get("ime", ""), "platforma": n.get("platforma", ""),
             "vrsta": n.get("vrsta", ""), "ta": bool(n.get("ta"))} for n in izid.get("naprave") or [] if n.get("id")]


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
        if nastavi:
            subprocess.run(["xdg-mime", "default", vnos, "x-scheme-handler/magnet"], timeout=10, check=False,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        r = subprocess.run(["xdg-mime", "query", "default", "x-scheme-handler/magnet"], timeout=10,
                           capture_output=True, text=True)
        return r.stdout.strip() == vnos
    except Exception:
        return False


def naprave_z_datotekami() -> list:
    """Druge naprave v Linku, ki delijo datoteke (zmoznost "files"): za Safeer Media -> Naprave."""
    izid = _control_naprave("Seznam")
    return [{"id": n.get("id", ""), "ime": n.get("ime", ""), "platforma": n.get("platforma", ""),
             "vrsta": n.get("vrsta", "")}
            for n in izid.get("naprave") or [] if n.get("id") and not n.get("ta") and "files" in (n.get("zmoznosti") or [])]


def datoteke_naprave(id_naprave: str, mapa: str = "") -> dict:
    """Mapa druge naprave (files.list prek Controla): vnosi, streznik za tok in kljuc naprave iz kroga."""
    return _control_naprave("Datoteke", str(id_naprave or ""), str(mapa or ""))


def preimenuj_napravo(id_naprave: str, ime: str) -> dict:
    """Novo ime naprave (tudi tega racunalnika) za vse naprave v Linku; hrani ga sredisce."""
    return _control_naprave("Preimenuj", str(id_naprave or ""), str(ime or ""))


def upravljaj_racunalnik(id_naprave: str) -> dict:
    """Safeer Control pridobi dovoljenje in odpre oddaljeni zaslon izbranega racunalnika."""
    return _control_naprave("Upravljaj", str(id_naprave or ""))


def programi_naprave(id_naprave: str) -> dict:
    """Programi ene naprave v obliki, kot jo ima stran (ikone kot data URL)."""
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
    return {"ok": True, "programi": programi, "deli": bool(izid.get("enabled", True))}


def zazeni_na_napravi(id_naprave: str, app: str) -> dict:
    """Program zazene na sami napravi in ohrani njeno sporocilo ob napaki."""
    return _control_naprave("Zazeni", str(id_naprave or ""), str(app or ""))


def odpri_tukaj(id_naprave: str, app: str) -> dict:
    """Napravo prosi za zagon programa in pretakanje zaslona na ta racunalnik."""
    return _control_naprave("OdpriTukaj", str(id_naprave or ""), str(app or ""))


SAMOZAGON = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                         "autostart", "safeer-os.desktop")


def _ukaz_os() -> str:
    from shutil import which
    if which("safeer-os"):
        return "safeer-os"
    return '"%s" "%s"' % (sys.executable, os.path.join(KOREN, "safeer_os.py"))


def je_samozagon() -> bool:
    """Ali se Safeer OS zazene ob prijavi v racunalnik (~/.config/autostart, vidno tudi v Mintovih
    »Zagonskih programih«, kjer ga uporabnik lahko izklopi)."""
    try:
        with open(SAMOZAGON, encoding="utf-8") as f:
            vsebina = f.read()
    except OSError:
        return False
    return "X-GNOME-Autostart-enabled=false" not in vsebina and "Hidden=true" not in vsebina


def nastavi_samozagon(vklop: bool) -> bool:
    """Vklop zapise vnos; izklop ga pusti z X-GNOME-Autostart-enabled=false (preglasi tudi sistemski
    vnos iz paketa, ko bo Safeer OS namescen kot .deb)."""
    vnos = ("[Desktop Entry]\nType=Application\nName=Safeer OS\n"
            "Comment=Safeer OS ob prijavi v racunalnik\nComment[sl]=Safeer OS ob prijavi v računalnik\n"
            "Exec=%s\nIcon=%s\nTerminal=false\nX-GNOME-Autostart-enabled=%s\nX-GNOME-Autostart-Delay=2\n"
            % (_ukaz_os(), os.path.join(KOREN, "assets", "os", "znak.svg"), "true" if vklop else "false"))
    try:
        os.makedirs(os.path.dirname(SAMOZAGON), exist_ok=True)
        with open(SAMOZAGON + ".tmp", "w", encoding="utf-8") as f:
            f.write(vnos)
        os.replace(SAMOZAGON + ".tmp", SAMOZAGON)
        return True
    except OSError:
        return False


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


def _ukaz_controla() -> Optional[list]:
    from shutil import which
    pot = which("safeer-control")
    if pot:
        return [pot]
    skripta = os.path.join(KOREN, "safeer_control.py")
    if os.path.isfile(skripta):
        return [sys.executable, skripta]
    return None


class SafeerOS(Gtk.Application):
    def __init__(self, v_oknu: bool = False, posnetek: str = "", namizje: bool = False) -> None:
        zastavice = Gio.ApplicationFlags.NON_UNIQUE if posnetek else Gio.ApplicationFlags.FLAGS_NONE
        super().__init__(application_id=APP_ID, flags=zastavice)
        self.v_oknu = v_oknu
        self.posnetek = posnetek
        self.shramba = os_programi.Shramba()
        self.programi = os_programi.Programi(self.shramba)
        self.zapiski = os_zapiski.Zapiski(ZAPISKI_POT)
        self.sporocila = os_sporocila.SporocilaOS()
        # Safeer Chat gre po Linku, ki ga drzi Safeer Control (D-Bus).
        self.sporocila.poslji_klepet = lambda n, b, c: _control_naprave("Klepet", n, b, c).get("stanje") \
            or _control_naprave_koda("Klepet")
        self.sporocila.naprave_klepeta = lambda: _control_naprave("KlepetNaprave").get("naprave") or []
        #: Scit: filtriranje DNS za ves racunalnik; ce je bil vklopljen, tece od zagona naprej.
        self.scit = os_scit.Scit(self.shramba)
        self.okno: Optional[Gtk.ApplicationWindow] = None
        self.pogled: Optional[WebKit2.WebView] = None
        self._ikone: dict = {}
        self._prvic = True
        #: Namizni nacin: Safeer OS je namizje (spodaj, programi nad njim) s svojo vrstico namesto
        #: Mintovega pulta. Sicer navadno okno (--okno, posnetki).
        # --namizje (paket safeer-os-tema, ob prijavi) vedno zazene namizje; --okno (program v oknu) nikoli.
        self.namizje = not v_oknu and not posnetek and (namizje or bool(self.shramba.get("celozaslonsko", True)))
        self.vrstica: Optional[Gtk.Window] = None
        self.pogledi: list = []
        self._okna_zamik = 0
        self._zaslon_zamik = 0
        self._koncano = False
        self._posnetek_nacrtovan = False
        # Safeer Media ima največ en lahek spletni pogled, ki se med vsebinami ponovno uporabi.
        self._medijski_okno = None
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
        self._glavna_postavitev = None
        self._spletni_nacin = False
        self._medijski_napis = None
        self._medijski_sklad = None
        self._medijski_vrsta = None
        self._medijski_premor = None
        self._medijski_drsnik = None
        self._medijski_cas = None
        self._medijski_vlecem = False
        self._medijski_css = None
        self._knjiznica_medijev = None
        self._medijski_tik_zacet = False
        self._medijsko_osvezevanje = False
        self._zadnji_medijski_napredek = None
        #: Magnet povezava, ki caka, da se stran nalozi (zagon z --magnet ali dejanje, ko okna se ni).
        self._cakajoci_magnet = ""
        magnet = Gio.SimpleAction.new("magnet", GLib.VariantType.new("s"))
        magnet.connect("activate", lambda _a, v: self._odpri_magnet(v.get_string() if v else ""))
        self.add_action(magnet)

    # ------------------------------------------------------------------ okno
    def do_activate(self) -> None:
        if self.okno is not None:
            self._domov()
            return
        self._ustvari_okno()
        if self.namizje:
            self._ustvari_vrstico()
            if VARNI_NACIN:
                # Po ponovljenih sesutjih pusti Mintov pult viden: uporabnik ima vedno pot ven.
                print("[SafeerOS] varni način: Mintov pult ostane viden")
            else:
                skrij_mintov_pult(self.shramba)
        koncaj = Gio.SimpleAction.new("koncaj", None)
        koncaj.connect("activate", lambda *a: self._koncaj())
        self.add_action(koncaj)
        for signal in (15, 1, 2):     # SIGTERM (odjava), SIGHUP, SIGINT: Mintov pult vrnemo
            GLib.unix_signal_add(GLib.PRIORITY_HIGH, signal, lambda *a: (self._koncaj(), False)[1])
        if self._prvic and not self.posnetek:
            self._prvic = False
            self.scit.zacni_ce_vklopljen()
            if self.shramba.get("samozagon") is None:
                # Kdor odpre Safeer OS, ga dobi tudi ob naslednji prijavi; izklop je v Nastavitvah,
                # v »Nazaj v Linux Mint« in v Mintovih Zagonskih programih.
                self.shramba.set("samozagon", nastavi_samozagon(True))
            # Brez prijavnega okna ob zagonu: Safeer OS dela takoj, naprave uporabnik poveze v Napravah,
            # kadar hoce (tam vidi, ali je v omrezju Safeer Link, in dobi navodila, ce ga ni).

    def _nov_pogled(self, stran: str) -> WebKit2.WebView:
        """WebKit z mostom do tega procesa; odgovori gredo nazaj v isti pogled."""
        upravitelj = WebKit2.UserContentManager()
        upravitelj.register_script_message_handler("safeerOs")
        upravitelj.add_script(WebKit2.UserScript(
            MOST_JS, WebKit2.UserContentInjectedFrames.TOP_FRAME,
            WebKit2.UserScriptInjectionTime.START, None, None))
        pogled = WebKit2.WebView.new_with_user_content_manager(upravitelj)
        upravitelj.connect("script-message-received::safeerOs", lambda _u, r: self._na_sporocilo(pogled, r))
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
        pogled.connect("context-menu", lambda *a: True)   # brez »Reload / Inspect« v preobleki
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

    def _zaslon(self):
        try:
            d = Gdk.Display.get_default()
            return d.get_primary_monitor() or d.get_monitor(0)
        except Exception:
            return None

    def _ustvari_okno(self) -> None:
        pogled = self._nov_pogled("index.html" + ("?namizje=1" if self.namizje else ""))
        okno = Gtk.ApplicationWindow(application=self, title="Safeer OS")
        okno.set_wmclass("safeer-os", "Safeer OS")
        okno.set_icon_name("safeer-browser")
        zaslon = self._zaslon()
        if self.posnetek and _velikost_okna(os.environ.get("SAFEER_OS_OKNO", "")):
            sirina, visina = _velikost_okna(os.environ["SAFEER_OS_OKNO"])
            okno.set_default_size(sirina, visina)
        elif self.posnetek:
            okno.set_decorated(False)
            okno.fullscreen()
        elif not self.namizje:
            g = zaslon.get_workarea() if zaslon else None
            okno.set_default_size(min(1440, int(g.width * 0.9)) if g else 1280,
                                  min(900, int(g.height * 0.9)) if g else 800)
            okno.set_position(Gtk.WindowPosition.CENTER)
        else:
            # Namizje: okno je ozadje - vedno pod programi, ni ga v preklopniku oken in ga »Pokaži
            # namizje« ne pomanjsa. Spodaj pusti prostor za Safeerjevo vrstico.
            g = zaslon.get_geometry() if zaslon else None
            okno.set_type_hint(Gdk.WindowTypeHint.DESKTOP)
            okno.set_decorated(False)
            okno.set_skip_taskbar_hint(True)
            okno.set_skip_pager_hint(True)
            if g is not None:
                okno.move(g.x, g.y)
                okno.set_default_size(g.width, g.height - VISINA_VRSTICE)
                okno.set_size_request(g.width, g.height - VISINA_VRSTICE)
        postavitev = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        postavitev.pack_start(pogled, True, True, 0)
        okno.add(postavitev)
        okno.connect("key-press-event", self._na_tipko)
        okno.connect("focus-in-event", lambda *a: (self._dogodek("fokus", None), False)[1])
        okno.connect("destroy", lambda *a: self._koncaj())
        self.okno, self.pogled, self._glavna_postavitev = okno, pogled, postavitev
        okno.show_all()
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
        vrstica.set_wmclass("safeer-os-vrstica", "Safeer OS")
        vrstica.set_type_hint(Gdk.WindowTypeHint.DOCK)
        vrstica.set_decorated(False)
        vrstica.set_skip_taskbar_hint(True)
        vrstica.set_skip_pager_hint(True)
        vrstica.stick()
        vrstica.set_keep_above(True)
        if g is not None:
            vrstica.move(g.x, g.y + g.height - VISINA_VRSTICE)
            vrstica.set_size_request(g.width, VISINA_VRSTICE)
        vrstica.add(self._nov_pogled("vrstica.html"))
        vrstica.connect("realize", lambda w: GLib.timeout_add(200, lambda: (self._rezerviraj(w, g), False)[1]))
        self.add_window(vrstica)
        vrstica.show_all()
        self.vrstica = vrstica
        self._spremljaj_okna()
        self._spremljaj_zaslone()

    def _spremljaj_zaslone(self) -> None:
        """Zaslon se med delom lahko zamenja: zaprt pokrov, priklopljen televizor, druga
        locljivost. Vrstica in namizje morata za njim - sicer ostaneta v velikosti zaslona,
        ki ga ni vec (20. 9. 2026: pokrov zaprt, slika sla na televizor 3840x2160, vrstica
        pa je ostala siroka 1920 in na starem mestu)."""
        try:
            zaslon = Gdk.Screen.get_default()
            if zaslon is None:
                return
            zaslon.connect("monitors-changed", lambda *a: self._zaslon_spremenjen())
            zaslon.connect("size-changed", lambda *a: self._zaslon_spremenjen())
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] spremljanja zaslonov ni:", e)

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
            self.vrstica.move(g.x, g.y + g.height - VISINA_VRSTICE)
            self.vrstica.set_size_request(g.width, VISINA_VRSTICE)
            self.vrstica.resize(g.width, VISINA_VRSTICE)
            # Rezervacija spodnjega roba je vezana na velikost zaslona, zato gre znova tudi ta.
            self._rezerviraj(self.vrstica, g)
        if self.namizje and self.okno is not None:
            self.okno.move(g.x, g.y)
            self.okno.set_size_request(g.width, g.height - VISINA_VRSTICE)
            self.okno.resize(g.width, g.height - VISINA_VRSTICE)
        print("[SafeerOS] zaslon %dx%d: vrstica in namizje prilagojena" % (g.width, g.height))
        return False

    def _rezerviraj(self, vrstica, g) -> None:
        """Rezervira spodnji rob zaslona za vrstico (xprop; GTK 3 tega sam ne zna)."""
        try:
            gi.require_version("GdkX11", "3.0")
            from gi.repository import GdkX11  # noqa: F401
            xid = vrstica.get_window().get_xid()
            m = vrstica.get_scale_factor() or 1
            zaslon_h = Gdk.Screen.get_default().get_height() * m
            spodaj = (zaslon_h - (g.y + g.height) * m) + VISINA_VRSTICE * m
            x0, x1 = g.x * m, (g.x + g.width) * m - 1
            vrednost = "0,0,0,%d,0,0,0,0,0,0,%d,%d" % (spodaj, x0, x1)
            subprocess.run(["xprop", "-id", str(xid), "-f", "_NET_WM_STRUT_PARTIAL", "32cccccccccccc",
                            "-set", "_NET_WM_STRUT_PARTIAL", vrednost], timeout=4)
            subprocess.run(["xprop", "-id", str(xid), "-f", "_NET_WM_STRUT", "32cccc",
                            "-set", "_NET_WM_STRUT", "0,0,0,%d" % spodaj], timeout=4)
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
            cas = Gtk.get_current_event_time() or int(GLib.get_monotonic_time() / 1000)
            os_okna.pomanjsaj_vse(self._nasi_xid(), cas)
        if self.okno is not None:
            self.okno.deiconify()
            self.okno.present()
        self._dogodek("fokus", None)
        if razdelek:
            self._dogodek("pojdi", razdelek)
        return True

    def _koncaj(self) -> None:
        """Konec Safeer OS (izhod, odjava, »Nazaj v Linux Mint«): Mintov pult se vrne."""
        if self._koncano:
            return
        self._koncano = True
        self._pocisti_medijski_pogled()
        self._ustavi_neposredni_medij()
        if self._medijski_predvajalnik is not None:
            self._medijski_predvajalnik.zapri()
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
            if self._spletni is not None:
                self._spletni.koncaj()
        except Exception:
            pass
        self.quit()

    def _na_politiko(self, _pogled, odlocitev, vrsta) -> bool:
        """Pogled sme prikazati samo stran Safeer OS (most ne sme k tuji strani)."""
        try:
            if vrsta not in (WebKit2.PolicyDecisionType.NAVIGATION_ACTION,
                             WebKit2.PolicyDecisionType.NEW_WINDOW_ACTION):
                return False
            naslov = odlocitev.get_navigation_action().get_request().get_uri() or ""
            if naslov.startswith(self._koren_strani + "/"):
                return False
            odlocitev.ignore()
            if naslov.startswith(("http://", "https://")):
                self._splet(naslov)
            return True
        except Exception:
            odlocitev.ignore()
            return True

    def _na_tipko(self, _okno, dogodek) -> bool:
        # F11: namizni nacin / okno (obicajna bliznjica, deluje tudi, ko se kaj zatakne).
        if dogodek.keyval == Gdk.KEY_F11 and not self.posnetek:
            self._celozaslonsko(not self.namizje)
            return True
        return False

    def _celozaslonsko(self, vklop: bool) -> bool:
        """Namizni nacin vklopi/izklopi; Safeer OS se zazene znova v izbranem nacinu."""
        self.shramba.set("celozaslonsko", bool(vklop))
        if bool(vklop) == self.namizje or self.v_oknu:
            return vklop

        def znova():
            if self.namizje:
                vrni_mintov_pult(self.shramba)
            os.execv(sys.executable, [sys.executable, os.path.abspath(__file__)])
        GLib.timeout_add(200, lambda: (znova(), False)[1])
        return vklop

    def _periodicno(self) -> bool:
        if self.okno is None:
            return False
        if self.okno.is_active() or (self.vrstica is not None):
            threading.Thread(target=lambda: self._dogodek("stanje", os_sistem.stanje()), daemon=True).start()
        return True

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
            self.pogled.evaluate_javascript("innerWidth + 'x' + innerHeight + ' @' + devicePixelRatio", -1, None, None, None,
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
        # Zajemi celo okno: levi WebKit je v spletnem nacinu samo stranska vrstica.
        if self.okno is not None and self.okno.get_window() is not None:
            try:
                w, h = self.okno.get_allocated_width(), self.okno.get_allocated_height()
                slika = Gdk.pixbuf_get_from_window(self.okno.get_window(), 0, 0, w, h)
                if slika is not None:
                    slika.savev(self.posnetek, "png", [], [])
                    print("posnetek:", self.posnetek)
                    self.quit()
                    return False
            except Exception as e:  # noqa: BLE001
                print("posnetek okna ni uspel, poskus pogleda:", e)
        def konec(pogled, rezultat):
            try:
                povrsina = pogled.get_snapshot_finish(rezultat)
                povrsina.write_to_png(self.posnetek)
                print("posnetek:", self.posnetek)
            except Exception as e:  # noqa: BLE001
                print("posnetek ni uspel:", e)
            self.quit()
        self.pogled.get_snapshot(WebKit2.SnapshotRegion.VISIBLE, WebKit2.SnapshotOptions.NONE, None, konec)
        return False

    # ------------------------------------------------------------------ most
    def _js(self, koda: str, pogled=None) -> None:
        for p in ([pogled] if pogled is not None else list(self.pogledi)):
            try:
                p.run_javascript(koda, None, None, None)
            except Exception:
                pass

    def _odgovori(self, pogled, id_, ok: bool, podatki) -> None:
        def naredi():
            self._js("window.__safeerOsOdgovor(%d, %s, %s);" % (
                int(id_), "true" if ok else "false", json.dumps(podatki, ensure_ascii=True)), pogled)
            return False
        GLib.idle_add(naredi)

    def _dogodek(self, vrsta: str, podatki) -> None:
        def naredi():
            self._js("window.safeerOsDogodek && window.safeerOsDogodek(%s, %s);" % (
                json.dumps(vrsta), json.dumps(podatki, ensure_ascii=True)))
            return False
        GLib.idle_add(naredi)

    def _na_sporocilo(self, pogled, rezultat) -> None:
        try:
            s = json.loads(rezultat.get_js_value().to_string())
            id_, metoda, a = int(s.get("id", 0)), str(s.get("m", "")), list(s.get("a") or [])
        except Exception:
            return
        # Na glavni niti (Gtk, ikone, okna):
        glavna = {
            "zacetek": self._zacetek,
            "programi": lambda: self.programi.seznam(self._ikona),
            "zazeni": lambda: self.programi.zazeni(str(a[0]) if a else "", self._zazeni_vnos),
            "pripni": lambda: self.programi.pripni(str(a[0]), bool(a[1]) if len(a) > 1 else True),
            "skrijDomov": lambda: self.programi.skrij_domov(str(a[0]), bool(a[1]) if len(a) > 1 else True),
            "nedavnePozabi": lambda: self._nedavne_pozabi(str(a[0]) if a else ""),
            "nedavnePocisti": self._nedavne_pocisti,
            "nedavne": self._nedavne,
            "odprtaOkna": self._odprta_okna,
            "aktivirajOkno": lambda: self._okno_dejanje(a[0] if a else 0, "aktiviraj"),
            "zapriOkno": lambda: self._okno_dejanje(a[0] if a else 0, "zapri"),
            "namizje": self._namizje,
            "celozaslonsko": lambda: self._celozaslonsko(bool(a[0]) if a else True),
            "control": lambda: self._odpri_control(),
            "prijava": lambda: self._prijava(),
            "domov": lambda: self._domov(str(a[0]) if a else ""),
            "preklopiOkno": lambda: self._okno_dejanje(a[0] if a else 0, "preklopi"),
            "shraniSpletne": lambda: self._shrani_spletne(a[0] if a else []),
            "splet": lambda: self._splet(str(a[0]) if a else ""),
            "medij": lambda: self._medij(str(a[0]) if a else ""),
            "lokalniMediji": self._medijski_dodaj_datoteke,
            "medijskaMapa": self._medijski_dodaj_mapo,
            "osveziMedijskeMape": self._medijski_osvezi_mape,
            "medijskiTok": self._medijski_dodaj_tok,
            "dodajMedijskiTok": lambda: self._shrani_medijski_tok(
                str(a[0]) if a else "", str(a[1]) if len(a) > 1 else "",
                str(a[2]) if len(a) > 2 else ""),
            "odpriMedijskiTok": lambda: self._odpri_medijski_tok(str(a[0]) if a else ""),
            "odpriLokalniMedij": lambda: self._odpri_lokalni_medij(str(a[0]) if a else ""),
            "cakajociMagnet": self._vzemi_cakajoci_magnet,
            "kopiraj": lambda: self._kopiraj(str(a[0]) if a else ""),
            "magnetPredvajaj": lambda: self._predvajaj_magnet(int(a[0]) if a else -1, int(a[1]) if len(a) > 1 else -1,
                                                             str(a[2]) if len(a) > 2 else ""),
            "magnetIzDatoteke": lambda: self._magnet_iz_datoteke(bool(a[0]) if a else False),
            "predvajajZNaprave": lambda: self._predvajaj_z_naprave(
                a[0] if a and isinstance(a[0], dict) else {}, str(a[1]) if len(a) > 1 else "",
                a[2] if len(a) > 2 and isinstance(a[2], list) else [], int(a[3]) if len(a) > 3 else 0,
                str(a[4]) if len(a) > 4 else ""),
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
            "zapiskiSeznam": lambda: self.zapiski.seznam(str(a[0]) if a else ""),
            "zapisekDobi": lambda: self.zapiski.dobi(str(a[0]) if a else ""),
            "zapisekShrani": lambda: self.zapiski.shrani(
                str(a[0]) if a else "", str(a[1]) if len(a) > 1 else "",
                str(a[2]) if len(a) > 2 else "",
                bool(a[3]) if len(a) > 3 and a[3] is not None else None),
            "zapisekIzbrisi": lambda: self.zapiski.izbrisi(str(a[0]) if a else ""),
            "sporocilaSeznam": lambda: self.sporocila.seznam(str(a[0]) if a else ""),
            "samozagon": lambda: self._samozagon(bool(a[0])) if a else je_samozagon(),
            "nazajVMint": lambda: self._nazaj_v_mint(bool(a[0]) if a else False),
            "razdelek": lambda: self._razdelek(str(a[0]) if a else "domov"),
            "splet": lambda: self._splet(str(a[0]) if a else ""),
            "iskanjeSplet": lambda: self._splet(_iskalnik() + GLib.uri_escape_string(str(a[0] if a else ""), None, False)),
        }
        # V ozadju (ukazi, ki lahko trajajo):
        ozadje = {
            "stanje": os_sistem.stanje,
            "glasnost": lambda: os_sistem.nastavi_glasnost(int(a[0])),
            "utisaj": os_sistem.preklopi_utisaj,
            "svetlost": lambda: os_sistem.nastavi_svetlost(int(a[0])),
            "nocna": lambda: os_sistem.nastavi_nocno_luc(bool(a[0])),
            "wifi": lambda: os_sistem.nastavi_wifi(bool(a[0])),
            "nastavitve": lambda: os_sistem.odpri_nastavitve(str(a[0]) if a else ""),
            "napajanje": lambda: os_sistem.napajanje(str(a[0]) if a else ""),
            "mapa": lambda: os_datoteke.preglej(str(a[0]) if a else "~"),
            "isciDatoteke": lambda: os_datoteke.isci(str(a[0]) if a else ""),
            "odpriDatoteko": lambda: os_datoteke.odpri(str(a[0]) if a else ""),
            "pokaziVMapi": lambda: os_datoteke.pokazi_v_mapi(str(a[0]) if a else ""),
            "medijskeMape": lambda: self._medijska_knjiznica().mape_podrobno(),
            "odstraniMedijskoMapo": lambda: self._odstrani_medijsko_mapo(str(a[0]) if a else ""),
            "tokoviMedijev": lambda: self._medijska_knjiznica().tokovi(),
            "odstraniMedijskiTok": lambda: self._odstrani_medijski_tok(str(a[0]) if a else ""),
            "knjiznicaMedijev": lambda: self._medijska_knjiznica().seznam(
                str(a[0]) if a else "", str(a[1]) if len(a) > 1 else "", 120,
                int(a[2]) if len(a) > 2 else 0),
            "odstraniLokalniMedij": lambda: self._odstrani_lokalni_medij(str(a[0]) if a else ""),
            "povezava": stanje_povezave,
            "zaupanje": lambda: nastavi_zaupanje(bool(a[0]) if a else False),
            "novaNaprava": lambda: control_dejanje("nova-naprava"),
            "odjava": lambda: control_dejanje("odjava"),
            "omrezje": lambda: os_omrezje.stanje(bool(a[0]) if a else False),
            "omrezjePovezi": lambda: os_omrezje.povezi(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            "omrezjeOdklopi": lambda: os_omrezje.odklopi(str(a[0]) if a else ""),
            "omrezjeAktiviraj": lambda: os_omrezje.aktiviraj(str(a[0]) if a else ""),
            "omrezjePozabi": lambda: os_omrezje.pozabi(str(a[0]) if a else ""),
            "zvok": zvok_stanje,
            "zvokNaZvocnik": lambda: zvok_na_zvocnik(str(a[0]) if a else "", bool(a[1]) if len(a) > 1 else False),
            "zvokUstaviZvocnik": lambda: zvocniki().ustavi(),
            "zvokIsciZvocnike": lambda: zvocniki().osvezi() or True,
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
            "magnetDodaj": lambda: _magnet_klic(lambda: {"id": os_torrent.torrenti().dodaj(
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
            "datotekeNaprave": lambda: datoteke_naprave(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            "preimenujNapravo": lambda: preimenuj_napravo(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            "upravljajRacunalnik": lambda: upravljaj_racunalnik(str(a[0]) if a else ""),
            "programiNaprave": lambda: programi_naprave(str(a[0]) if a else ""),
            "zazeniNaNapravi": lambda: zazeni_na_napravi(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            "odpriTukaj": lambda: odpri_tukaj(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            "zvokUstavi": zvok_ustavi,
            "jbl": lambda: os_jbl.stanje(True) if os_jbl else {"na_voljo": False},
            "jblVklop": lambda: os_jbl.vklopi(bool(a[0]) if a else False) if os_jbl else {"na_voljo": False},
            "scit": self.scit.stanje,
            "scitVklop": lambda: self.scit.nastavi(bool(a[0]) if a else False),
            "sporocilaDodaj": lambda: self.sporocila.dodaj_kanal(a[0] if a and isinstance(a[0], dict) else {}),
            "sporocilaPoslji": lambda: self.sporocila.poslji(str(a[0]), str(a[1]), str(a[2])),
            "sporocilaSinhroniziraj": self.sporocila.sinhroniziraj,
            "sporocilaIsci": lambda: self.sporocila.isci(str(a[0]) if a else ""),
            "sporocilaPogovor": lambda: self.sporocila.pogovor(str(a[0]), str(a[1])),
            "sporocilaSkrivnost": lambda: self.sporocila.nastavi_skrivnost(str(a[0]), str(a[1])),
            "sporocilaOdstrani": lambda: self.sporocila.odstrani_kanal(str(a[0])),
            "sporocilaStreznik": lambda: self.sporocila.privzeta_streznika(str(a[0]) if a else ""),
            "sporocilaNaprave": self.sporocila.naprave_za_klepet,
            "sporocilaZacni": lambda: self.sporocila.zacni_klepet(str(a[0]), str(a[1]) if len(a) > 1 else ""),
        }
        if metoda in glavna:
            try:
                self._odgovori(pogled, id_, True, glavna[metoda]())
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS]", metoda, e)
                self._odgovori(pogled, id_, False, str(e))
        elif metoda in ozadje:
            def delo():
                try:
                    self._odgovori(pogled, id_, True, ozadje[metoda]())
                except Exception as e:  # noqa: BLE001
                    print("[SafeerOS]", metoda, e)
                    self._odgovori(pogled, id_, False, str(e))
            threading.Thread(target=delo, daemon=True).start()
        else:
            self._odgovori(pogled, id_, False, "neznano")

    # ------------------------------------------------------------------ dejanja
    def _zacetek(self) -> dict:
        ozadje = os_sistem.ozadje_namizja()
        shranjene_spletne = self.shramba.get("spletne", None)
        if isinstance(shranjene_spletne, list):
            ciste_spletne = os_spletne.pocisti(shranjene_spletne)
            if ciste_spletne != shranjene_spletne:
                self.shramba.set("spletne", ciste_spletne)
            shranjene_spletne = ciste_spletne
        return {
            "jezik": _jezik(),
            "ime": GLib.get_real_name() if GLib.get_real_name() not in ("", "Unknown") else GLib.get_user_name(),
            "racunalnik": socket.gethostname(),
            "ozadje": ("file://" + GLib.uri_escape_string(ozadje, "/", False)) if ozadje else "",
            "razpolozljivo": os_sistem.razpolozljivo(),
            "mape": os_datoteke.uporabniske_mape(),
            "celozaslonsko": bool(self.shramba.get("celozaslonsko", True)) and not self.v_oknu,
            "namizje": self.namizje,
            "spletne": shranjene_spletne,
            "razlicica": RAZLICICA,
            "sistem": _ime_sistema(),
            "samozagon": je_samozagon(),
            "povezava": stanje_povezave(),
        }

    def _samozagon(self, vklop: bool) -> bool:
        ok = nastavi_samozagon(vklop)
        if ok:
            self.shramba.set("samozagon", bool(vklop))
        return je_samozagon()

    def _nazaj_v_mint(self, za_stalno: bool) -> bool:
        """Zapre Safeer OS; pod njim je obicajno namizje Linux Mint. »Za stalno« izklopi tudi zagon ob
        prijavi. Nazaj se uporabnik vrne iz menija (Safeer OS)."""
        if za_stalno:
            self._samozagon(False)
        GLib.timeout_add(250, lambda: (self._koncaj(), False)[1])
        return True

    def _shrani_spletne(self, seznam) -> list:
        """Spletne aplikacije: ime, HTTP(S) naslov in neobvezna vrsta medija, največ 24."""
        cisti = os_spletne.pocisti(seznam)
        self.shramba.set("spletne", cisti)
        return cisti

    def _ikona(self, ime: str) -> str:
        if ime not in self._ikone:
            pot = os_programi.pot_ikone(ime)
            self._ikone[ime] = ("file://" + GLib.uri_escape_string(pot, "/", False)) if pot else ""
        return self._ikone[ime]

    def _zazeni_vnos(self, pot: str) -> bool:
        info = Gio.DesktopAppInfo.new_from_filename(pot)
        if info is None:
            return False
        kontekst = Gdk.Display.get_default().get_app_launch_context()
        kontekst.set_timestamp(Gtk.get_current_event_time() or Gdk.CURRENT_TIME)
        return bool(info.launch([], kontekst))

    def _nedavne(self) -> list:
        izhod = []
        try:
            for e in Gtk.RecentManager.get_default().get_items():
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
            return bool(Gtk.RecentManager.get_default().remove_item(GLib.filename_to_uri(pot, None)))
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] nedavne pozabi:", e)
            return False

    def _nedavne_pocisti(self) -> bool:
        try:
            Gtk.RecentManager.get_default().purge_items()
            return True
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] nedavne pocisti:", e)
            return False

    # --- odprta okna (libwnck prek core/os_okna.py: samo X11, samo glavna nit, brez ponovnega
    # osvezevanja seznama oken v zanki - to je povzrocilo sesutje)
    def _nasi_xid(self) -> set:
        """Okni Safeer OS (domaci zaslon, vrstica) v seznamu programov ne smeta biti."""
        nasi = set()
        for w in (self.okno, self.vrstica):
            try:
                if w is not None and w.get_window() is not None:
                    nasi.add(w.get_window().get_xid())
            except Exception:  # noqa: BLE001
                pass
        return nasi

    def _odprta_okna(self) -> list:
        return os_okna.seznam(self._nasi_xid(), os_programi.MAPA_IKON)

    def _okno_dejanje(self, xid, dejanje: str) -> bool:
        cas = Gtk.get_current_event_time() or int(GLib.get_monotonic_time() / 1000)
        return os_okna.dejanje(xid, dejanje, cas)

    def _namizje(self) -> bool:
        """Umakne Safeer OS in pokaze Mintovo namizje (vrne se s klikom v meniju ali na plosci)."""
        if self.okno is not None:
            self.okno.iconify()
        return True

    def _splet(self, naslov: str) -> bool:
        """Odpre naslov v zavihku znotraj glavnega okna; brez procesa ali dodatnega okna."""
        if naslov and not naslov.startswith(("http://", "https://")):
            return False
        self._pokazi_spletni_nacin()
        return self._spletni.odpri(naslov) if naslov else True

    def _ustvari_spletni(self) -> None:
        if self._spletni is not None:
            return
        from core.os_splet import VdelaniSplet
        self._spletni = VdelaniSplet(Gtk, Gdk, Gio, GLib, WebKit2, KOREN, _jezik, stanje_povezave,
                                     self._splet_v_zapisek, self.okno)
        self._glavna_postavitev.pack_start(self._spletni.gradnik, True, True, 0)
        self._spletni.gradnik.set_no_show_all(True)
        self._spletni.gradnik.hide()

    def _pokazi_spletni_nacin(self) -> bool:
        """Najprej izmeri #stranska, sele nato doda nacin-splet in zozi HTML lupino."""
        self._ustvari_spletni()
        self._spletni_nacin = True
        koda = (
            "(function(){var s=document.getElementById('stranska'),b=document.body;"
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
            self.pogled.set_hexpand(False)
            # Lupina je v Box zapakirana z expand=True; v nacinu Splet mora ostati le stranska vrstica.
            self._glavna_postavitev.set_child_packing(self.pogled, False, False, 0, Gtk.PackType.START)
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
            self._spletni.gradnik.set_no_show_all(False)
            self._spletni.gradnik.show_all()

        self.pogled.evaluate_javascript(koda, -1, None, None, None, izmerjeno)
        return True

    def _uskladi_sirino_spleta(self, *_):
        if not self._spletni_nacin or self._spletni is None or self.okno is None:
            return False
        skupaj = self.okno.get_allocated_width()
        stranska = int(getattr(self, "_sirina_stranske", 300) or 300)
        self._spletni.gradnik.set_size_request(max(360, skupaj - stranska), -1)
        if not getattr(self, "_splet_povezan_resize", False):
            self._splet_povezan_resize = True
            self.okno.connect("size-allocate", lambda *a: GLib.idle_add(self._uskladi_sirino_spleta))
        return False

    def _skrij_spletni_nacin(self, razdelek: str = "domov") -> bool:
        self._spletni_nacin = False
        if self._spletni is not None:
            self._spletni.gradnik.hide()
            self._spletni.gradnik.set_no_show_all(True)
        self.pogled.set_size_request(-1, -1)
        self.pogled.set_hexpand(True)
        if self._spletni is not None:
            self._spletni.gradnik.set_size_request(-1, -1)
        self._glavna_postavitev.set_child_packing(self.pogled, True, True, 0, Gtk.PackType.START)
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
                             ime: str = "", zacetek: int = 0, seznam=None, zacni: int = 0) -> bool:
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
                self._medijski_predvajalnik.v_glavni = lambda f: GLib.idle_add(f)
                if not self._medijski_tik_zacet:
                    self._medijski_tik_zacet = True
                    GLib.timeout_add_seconds(1, self._medijski_tik)
            if self._medijski_predvajalnik_okno is None:
                okno = Gtk.Window(title="Safeer Player")
                okno.get_style_context().add_class("safeer-player")
                if self._medijski_css is None:
                    try:
                        css = Gtk.CssProvider()
                        css.load_from_data(b"""
                            window.safeer-player { background: #0c1821; color: #f0f4f3; }
                            window.safeer-player label { color: #dbeee9; }
                            window.safeer-player label.safeer-player-title { font-size: 18px; font-weight: 700; }
                            window.safeer-player label.safeer-player-queue { color: #b0bdc4; }
                            window.safeer-player label.safeer-player-note { font-size: 96px; color: #54d6a5; }
                            window.safeer-player button { background: #1a3339; color: #edfff7;
                                border: 1px solid #3a6f65; border-radius: 10px; padding: 8px 13px; }
                            window.safeer-player button:hover { background: #275248; border-color: #54d6a5; }
                            window.safeer-player scale highlight { background: #54d6a5; }
                            window.safeer-player scale slider { background: #54d6a5;
                                min-width: 14px; min-height: 14px; }
                        """)
                        Gtk.StyleContext.add_provider_for_screen(
                            Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
                        self._medijski_css = css
                    except Exception as e:  # noqa: BLE001
                        print("[SafeerOS] slog predvajalnika:", e)
                # Na velikih zaslonih 960x620 deluje kot sličica; okno naj zavzame približno dve tretjini.
                zaslon = self._zaslon()
                g = zaslon.get_workarea() if zaslon else None
                okno.set_default_size(max(960, int(g.width * 0.62)) if g else 960,
                                      max(620, int(g.height * 0.7)) if g else 620)
                okno.set_transient_for(self.okno)
                okno.set_position(Gtk.WindowPosition.CENTER_ON_PARENT)
                okno.connect("delete-event", lambda *a: (self._ustavi_neposredni_medij(), True)[1])
                okno.connect("key-press-event", self._medijska_tipka)
                postavitev = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
                postavitev.set_border_width(16)
                # Glasba nima slike: namesto črnega polja pokažemo znak in naslov (sklad preklopi ob osvežitvi).
                self._medijski_sklad = Gtk.Stack()
                self._medijski_sklad.set_vexpand(True)
                self._medijski_sklad.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
                zvok = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6, valign=Gtk.Align.CENTER)
                znak = Gtk.Label(label="♫")
                znak.get_style_context().add_class("safeer-player-note")
                self._medijski_zvok_naslov = Gtk.Label()
                self._medijski_zvok_naslov.get_style_context().add_class("safeer-player-title")
                self._medijski_zvok_naslov.set_line_wrap(True)
                self._medijski_zvok_naslov.set_justify(Gtk.Justification.CENTER)
                zvok.pack_start(znak, False, False, 0)
                zvok.pack_start(self._medijski_zvok_naslov, False, False, 0)
                self._medijski_sklad.add_named(zvok, "zvok")
                ponor = Gst.ElementFactory.make("gtksink", "safeer-media-video")
                if ponor is not None:
                    self._medijski_predvajalnik.element.set_property("video-sink", ponor)
                    slika = Gtk.EventBox()
                    slika.add(ponor.get_property("widget"))
                    # Dvojni klik na sliko preklopi cel zaslon (kot v VLC in mpv).
                    slika.connect("button-press-event", lambda _w, d: d.type == Gdk.EventType._2BUTTON_PRESS and
                                  self._medijski_cel_zaslon(okno))
                    self._medijski_sklad.add_named(slika, "slika")
                postavitev.pack_start(self._medijski_sklad, True, True, 0)
                self._medijski_napis = Gtk.Label(xalign=0)
                self._medijski_napis.get_style_context().add_class("safeer-player-title")
                postavitev.pack_start(self._medijski_napis, False, False, 0)
                premik = Gtk.Box(spacing=10)
                self._medijski_drsnik = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1, 1)
                self._medijski_drsnik.set_draw_value(False)
                self._medijski_drsnik.set_hexpand(True)
                self._medijski_drsnik.set_tooltip_text(self._mb("premik"))
                self._medijski_drsnik.connect("change-value", self._medijski_premik)
                self._medijski_drsnik.connect("button-press-event", self._medijski_zacni_premik)
                self._medijski_drsnik.connect_after("button-release-event", self._medijski_spusti_premik)
                premik.pack_start(self._medijski_drsnik, True, True, 0)
                self._medijski_cas = Gtk.Label(label="0:00 / 0:00")
                premik.pack_start(self._medijski_cas, False, False, 0)
                postavitev.pack_start(premik, False, False, 0)
                gumbi = Gtk.Box(spacing=8)
                for napis_gumba, dejanje in (("＋ " + self._mb("dodaj_datoteke"), self._medijski_dodaj_datoteke),
                                              ("⏮ " + self._mb("prejsnja"), lambda: self._medijski_ukaz("prejsnja")),
                                              ("⏭ " + self._mb("naslednja"), lambda: self._medijski_ukaz("naslednja"))):
                    gumb = Gtk.Button(label=napis_gumba)
                    gumb.connect("clicked", lambda _g, ukaz=dejanje: ukaz())
                    gumbi.pack_start(gumb, False, False, 0)
                self._medijski_premor = Gtk.Button(label="⏸ " + self._mb("premor"))
                self._medijski_premor.connect("clicked", lambda _g: self._medijski_ukaz("premor"))
                gumbi.pack_start(self._medijski_premor, False, False, 0)
                # Podnapisi (kot v VLC): izklop, vgrajeni tokovi in datoteke ob videu; tipka V jih preklaplja.
                self._medijski_podnapisi = Gtk.Button(label="💬 " + self._mb("podnapisi"))
                self._medijski_podnapisi.set_no_show_all(True)
                self._medijski_podnapisi.connect("clicked", self._medijski_meni_podnapisov)
                gumbi.pack_end(self._medijski_podnapisi, False, False, 0)
                celozaslonsko = Gtk.Button(label="⛶ " + self._mb("cel_zaslon"))
                celozaslonsko.connect("clicked", lambda _g: okno.unfullscreen() if okno.get_window() and
                                     okno.get_window().get_state() & Gdk.WindowState.FULLSCREEN else okno.fullscreen())
                gumbi.pack_end(celozaslonsko, False, False, 0)
                postavitev.pack_start(gumbi, False, False, 0)
                self._medijski_vrsta = Gtk.Label(xalign=0)
                self._medijski_vrsta.get_style_context().add_class("safeer-player-queue")
                self._medijski_vrsta.set_line_wrap(True)
                postavitev.pack_start(self._medijski_vrsta, False, False, 0)
                okno.add(postavitev)
                self.add_window(okno)
                self._medijski_predvajalnik_okno = okno
            if seznam:
                uspesno = self._medijski_predvajalnik.zamenjaj_vrsto(seznam, zacni)
            else:
                self._medijski_predvajalnik.dodaj(naslov, predvajaj=True, vrsta=vrsta,
                                                  naslov=ime, zacetek=zacetek)
                uspesno = self._medijski_predvajalnik.stanje != "napaka"
            if prikazi:
                self._medijski_predvajalnik_okno.show_all()
                self._medijski_predvajalnik_okno.present()
            else:
                self._medijski_predvajalnik_okno.hide()
            return uspesno
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] neposredni medij:", e)
            self._ustavi_neposredni_medij()
            # Lokalni varni tok (127.0.0.1/m/<skrivnost>) ni spletna stran: ne v brskalnik in ne v zgodovino.
            return self._splet(naslov) if vrsta == "medij" and naslov.startswith(("http://", "https://")) \
                and not naslov.startswith("http://127.0.0.1:") else False

    def _ustavi_neposredni_medij(self) -> None:
        if self._medijski_predvajalnik is not None:
            try:
                self._shrani_medijski_napredek()
                self._medijski_predvajalnik.ustavi()
                self._dogodek("medijskaKnjiznica", None)
            except Exception:
                pass
        if self._medijski_predvajalnik_okno is not None:
            self._medijski_predvajalnik_okno.hide()

    def _osvezi_medijski_predvajalnik(self) -> None:
        servis = self._medijski_predvajalnik
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
        if getattr(self, "_medijski_podnapisi", None) is not None:
            self._medijski_podnapisi.set_visible(bool(podatki.get("podnapisi")) and podatki.get("vrsta") == "video")
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
        servis = self._medijski_predvajalnik
        if servis is None:
            return
        stanje = servis.podnapisi()
        meni = Gtk.Menu()
        skupina = None
        for kljuc, napis in [("izklop", self._mb("podnapisi_izklop"))] + \
                [(m["kljuc"], self._ime_podnapisa(m)) for m in stanje["moznosti"]]:
            postavka = Gtk.RadioMenuItem.new_with_label_from_widget(skupina, napis)
            skupina = skupina or postavka
            postavka.set_active(kljuc == stanje["izbran"])
            postavka.connect("activate", lambda p, k=kljuc: p.get_active() and servis.izberi_podnapise(k))
            meni.append(postavka)
        meni.show_all()
        meni.attach_to_widget(gumb, None)
        meni.popup_at_widget(gumb, Gdk.Gravity.NORTH_WEST, Gdk.Gravity.SOUTH_WEST, None)

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
        return servis.izberi_podnapise(kljuci[(i + 1) % len(kljuci)])

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
        if okno.get_window() and okno.get_window().get_state() & Gdk.WindowState.FULLSCREEN:
            okno.unfullscreen()
        else:
            okno.fullscreen()
        return True

    def _medijska_tipka(self, okno, dogodek) -> bool:
        tipka = Gdk.keyval_name(dogodek.keyval)
        servis = self._medijski_predvajalnik
        if servis is not None and servis.je_dvd():
            # Meni DVD: puščice in Enter premikajo izbiro (v filmu jih disk prezre), M odpre meni diska.
            ukaz = {"Up": "gor", "Down": "dol", "Return": "potrdi", "KP_Enter": "potrdi", "m": "meni", "M": "meni"}.get(tipka or "")
            if ukaz:
                return servis.navigacija(ukaz)
            if tipka in ("Left", "Right"):
                servis.navigacija("levo" if tipka == "Left" else "desno")
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
        if tipka == "Escape" and okno.get_window() and okno.get_window().get_state() & Gdk.WindowState.FULLSCREEN:
            okno.unfullscreen()
            return True
        return False

    def _osvezi_medijski_sklad(self) -> None:
        """Slika za video, glasbeni znak za zvok. Dokler playbin ne pozna tokov, odloči vrsta vnosa."""
        servis = self._medijski_predvajalnik
        if servis is None or self._medijski_sklad is None:
            return
        self._medijski_zvok_naslov.set_text(servis.trenutna.naslov if servis.trenutna else "")
        try:
            ok, pozicija = servis.element.query_position(servis.gst.Format.TIME)
            znano = bool(ok and pozicija > 0)
            ima_sliko = int(servis.element.get_property("n-video") or 0) > 0
        except Exception:  # noqa: BLE001
            znano, ima_sliko = False, False
        if not znano:
            ima_sliko = bool(servis.trenutna and servis.trenutna.vrsta in ("video", "tv"))
        cilj = "slika" if ima_sliko and self._medijski_sklad.get_child_by_name("slika") else "zvok"
        if self._medijski_sklad.get_visible_child_name() != cilj:
            self._medijski_sklad.set_visible_child_name(cilj)

    def _medijski_tik(self) -> bool:
        if self._koncano:
            return False
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
        pot = self._pot_lokalnega_videa(uri)
        if pot:
            self._medijska_knjiznica().ponastavi_napredek(pot)
            self._zadnji_medijski_napredek = None
            self._dogodek("medijskaKnjiznica", None)

    def _medijski_podatki(self) -> dict:
        return self._medijski_predvajalnik.podatki() if self._medijski_predvajalnik else {
            "stanje": "ustavljeno", "naslov": "", "vrsta": "", "indeks": -1,
            "zacetniIndeks": 0, "skupaj": 0, "vrstaSeznam": [], "pozicija": 0, "trajanje": 0, "napaka": ""}

    def _medijski_ukaz(self, ukaz: str, vrednost=None) -> bool:
        servis = self._medijski_predvajalnik
        if not servis:
            return False
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
            self._medijski_predvajalnik_okno.show_all()
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

    def _medijska_knjiznica(self):
        if self._knjiznica_medijev is None:
            self._knjiznica_medijev = os_knjiznica.Knjiznica()
        return self._knjiznica_medijev

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

    def _predvajaj_z_naprave(self, streznik: dict, kljuc: str, vnosi: list, zacni: int = 0, izvor: str = "") -> bool:
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
                                                  podnapisi=tuple(podnapisi)))
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
        self._cakajoci_magnet = {"uri": uri, "samodejno": samodejno}
        if self.okno is None:
            self.activate()
            return            # stran ga prevzame ob nalaganju (cakajociMagnet)
        self.okno.present()
        self._dogodek("magnet", {"uri": uri, "samodejno": samodejno})

    @staticmethod
    def _kopiraj(besedilo: str) -> bool:
        """Besedilo v odložišče (npr. magnet povezava za deljenje z drugimi)."""
        odlozisce = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        odlozisce.set_text(besedilo[:8192], -1)
        odlozisce.store()
        return True

    def _vzemi_cakajoci_magnet(self) -> dict:
        cakajoci, self._cakajoci_magnet = self._cakajoci_magnet, ""
        return cakajoci or {}

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
        ok = self._predvajaj_neposredno(url, vrsta="video" if video else "medij", prikazi=video,
                                        ime=skladba.naslov, seznam=[skladba], zacni=0)
        return {"ok": bool(ok)}

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

    def _magnet_iz_datoteke(self, mapa: bool) -> bool:
        """Uporabnik izbere svojo datoteko ali mapo; iz nje nastane magnet, ki ga lahko pošlje ali deli."""
        izbirnik = Gtk.FileChooserNative.new(
            self._mb("izberi_mapo") if mapa else self._mb("deli_datoteko"), self.okno,
            Gtk.FileChooserAction.SELECT_FOLDER if mapa else Gtk.FileChooserAction.OPEN, None, None)
        izbirnik.set_current_folder(GLib.get_home_dir())
        if izbirnik.run() != Gtk.ResponseType.ACCEPT:
            return False
        pot = izbirnik.get_filename() or ""

        def delo() -> None:
            izid = _magnet_klic(lambda: {"uri": os_torrent.torrenti().deli_datoteko(pot),
                                         "ime": os.path.basename(pot)})
            self._dogodek("magnetDeljen", izid)
        threading.Thread(target=delo, name="safeer-magnet-deli", daemon=True).start()
        return True

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

    def _medijski_dodaj_datoteke(self) -> None:
        dialog = Gtk.FileChooserDialog(title=self._mb("dodaj_datoteke"), transient_for=self._medijski_predvajalnik_okno or self.okno,
                                       action=Gtk.FileChooserAction.OPEN)
        dialog.add_buttons(self._mb("preklici"), Gtk.ResponseType.CANCEL, self._mb("dodaj"), Gtk.ResponseType.OK)
        dialog.set_current_folder(GLib.get_home_dir())   # ne mapa programa (~/.local/lib/safeer-os)
        dialog.set_select_multiple(True)
        try:
            if dialog.run() == Gtk.ResponseType.OK:
                poti = dialog.get_filenames()[:500]
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
        finally:
            dialog.destroy()

    def _medijski_dodaj_mapo(self) -> bool:
        dialog = Gtk.FileChooserDialog(title=self._mb("dodaj_mapo"), transient_for=self.okno,
                                       action=Gtk.FileChooserAction.SELECT_FOLDER)
        dialog.add_buttons(self._mb("preklici"), Gtk.ResponseType.CANCEL, self._mb("dodaj"), Gtk.ResponseType.OK)
        dialog.set_current_folder(GLib.get_home_dir())   # ne mapa programa (~/.local/lib/safeer-os)
        try:
            if dialog.run() != Gtk.ResponseType.OK:
                return False
            mapa = dialog.get_filename()
        finally:
            dialog.destroy()
        knjiznica = self._medijska_knjiznica()

        def uvozi():
            try:
                knjiznica.dodaj_mapo(mapa)
                self._dogodek("medijskaKnjiznica", None)
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS] medijska mapa:", e)
                self._dogodek("medijskaNapaka", "")
        threading.Thread(target=uvozi, daemon=True).start()
        return True

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

    def _medijski_dodaj_tok(self) -> bool:
        """Uporabnikov neposredni tok shrani in predvaja v GStreamerju."""
        dialog = Gtk.Dialog(title="Dodaj TV ali radijski tok", transient_for=self.okno, flags=Gtk.DialogFlags.MODAL)
        dialog.add_buttons("Prekliči", Gtk.ResponseType.CANCEL, "Shrani in predvajaj", Gtk.ResponseType.OK)
        polja = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        polja.set_border_width(12)
        ime = Gtk.Entry()
        ime.set_placeholder_text("Ime postaje")
        polja.pack_start(ime, False, False, 0)
        vrsta = Gtk.ComboBoxText()
        vrsta.append("tv", "TV v živo")
        vrsta.append("radio", "Radio")
        vrsta.set_active_id("tv")
        polja.pack_start(vrsta, False, False, 0)
        vnos = Gtk.Entry()
        vnos.set_placeholder_text("https://primer.si/kanal.m3u8")
        vnos.set_width_chars(55)
        polja.pack_start(vnos, False, False, 0)
        dialog.get_content_area().pack_start(polja, False, False, 0)
        dialog.show_all()
        try:
            if dialog.run() != Gtk.ResponseType.OK:
                return False
            naslov = vnos.get_text().strip()
            ime_postaje = ime.get_text().strip()
            vrsta_toka = vrsta.get_active_id()
            return self._shrani_medijski_tok(ime_postaje, naslov, vrsta_toka)
        except ValueError:
            return False
        finally:
            dialog.destroy()

    def _shrani_medijski_tok(self, ime: str, url: str, vrsta: str) -> bool:
        os_predvajalnik.medij(url, vrsta)
        self._medijska_knjiznica().dodaj_tok(ime, url, vrsta)
        self._dogodek("medijskaKnjiznica", None)
        if not self._odpri_medijski_tok(url):
            self._dogodek("medijskaNapaka", "")
        return True

    def _odpri_lahki_medijski_pogled(self, naslov: str) -> bool:
        """En WebKit brez JavaScripta; če ni medija, enkrat poskusi z JavaScriptom."""
        self._ustavi_neposredni_medij()
        if self._medijski_pogled is None:
            # Tuje strani v lastnem, zacasnem kontekstu s peskovnikom: nic piskotkov/podatkov Safeer OS in
            # locen spletni proces, ki ga ob izhodu z vsebine izpraznemo.
            kontekst = WebKit2.WebContext.new_ephemeral()
            try:
                kontekst.set_sandbox_enabled(True)
            except Exception:
                pass
            kontekst.set_cache_model(WebKit2.CacheModel.DOCUMENT_VIEWER)
            pogled = WebKit2.WebView.new_with_context(kontekst)
            nastavitve = pogled.get_settings()
            # Skripte strani izklopimo (markup), API skripte ostanejo - z njimi preverimo, ali je na strani video.
            nastavitve.set_property("enable-javascript-markup", False)
            nastavitve.set_property("enable-webgl", False)
            pogled.connect("load-changed", self._medijski_nalozen)
            okno = Gtk.ApplicationWindow(application=self, title="Medijski center")
            okno.set_default_size(1100, 700)
            okno.set_transient_for(self.okno)
            okno.add(pogled)
            okno.connect("delete-event", lambda *a: (self._pocisti_medijski_pogled(), True)[1])
            self._medijski_pogled, self._medijski_okno = pogled, okno
        self._medijski_rod += 1
        self._medijski_naslov = naslov
        self._medijski_js = False
        self._medijski_pogled.get_settings().set_property("enable-javascript-markup", False)
        self._medijski_pogled.load_uri(naslov)
        self._medijski_okno.show_all()
        self._medijski_okno.present()
        return True

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
        self._medijski_rod += 1
        self._medijski_naslov = ""
        self._medijski_js = False
        if self._medijski_pogled is None:
            return
        try:
            self._medijski_pogled.load_uri("about:blank")
            self._medijski_pogled.get_settings().set_property("enable-javascript-markup", False)
            upravitelj = self._medijski_pogled.get_context().get_website_data_manager()
            vrste = WebKit2.WebsiteDataTypes.MEMORY_CACHE | WebKit2.WebsiteDataTypes.DISK_CACHE
            upravitelj.clear(vrste, 0, None, None, None)
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] čiščenje medijskega pogleda:", e)
        if self._medijski_okno is not None:
            self._medijski_okno.hide()

    def _prijava(self) -> bool:
        """Prijavno okno Safeer Linka (QR / koda / brez povezave) - zanj skrbi Safeer Control; okno je nad
        Safeer OS in se po prijavi samo zapre."""
        threading.Thread(target=lambda: control_dejanje("prijava") or self._odpri_control(), daemon=True).start()
        return True

    def _odpri_control(self) -> bool:
        """Safeer Control: prijavno okno (QR / koda) ali seznam naprav, ce je racunalnik ze povezan."""
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
            vodilo = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            tece = vodilo.call_sync("org.freedesktop.DBus", "/org/freedesktop/DBus", "org.freedesktop.DBus",
                                    "NameHasOwner", GLib.Variant("(s)", (APP_ID,)), GLib.VariantType("(b)"),
                                    Gio.DBusCallFlags.NONE, 2000, None).unpack()[0]
            if tece:
                vodilo.call_sync(APP_ID, "/" + APP_ID.replace(".", "/"), "org.gtk.Actions", "Activate",
                                 GLib.Variant("(sava{sv})", ("magnet", [GLib.Variant("s", magnet)], {})),
                                 None, Gio.DBusCallFlags.NONE, 5000, None)
                return 0
        except Exception as e:  # noqa: BLE001 - Safeer OS ne tece: zazenemo ga z magnetom
            print("[SafeerOS] magnet:", e)
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
    if os_stabilnost.naj_bo_varni_nacin("safeer-os") and not os.environ.get(os_okna.IZKLOP):
        # Vec sesutij v kratkem casu: tokrat brez seznama oken (libwnck) in brez skrivanja Mintovega
        # pulta, da je Safeer OS vsaj uporaben in da ima uporabnik pot nazaj v Mint.
        os.environ[os_okna.IZKLOP] = "1"
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
    app = SafeerOS(v_oknu="--okno" in sys.argv[1:] or bool(magnet), posnetek=posnetek, namizje="--namizje" in sys.argv[1:])
    app._cakajoci_magnet = magnet
    # Ce program tece brez tezav, zgodovina sesutij ni vec pomembna (sicer bi varni nacin ostal za vedno).
    GLib.timeout_add_seconds(120, lambda: (os_stabilnost.pozabi_sesutja("safeer-os"), False)[1])
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
