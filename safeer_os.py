#!/usr/bin/env python3
"""Safeer OS za racunalnik - preobleka cez Linux Mint.

Isti Safeer OS kot na televizorju, le za racunalnik: celozaslonski domaci zaslon z levim menijem
(Domov, Programi, Datoteke, Naprave, Nastavitve), ki pokaze VSE, kar je ze na racunalniku -
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
from typing import Optional

KOREN = os.path.dirname(os.path.abspath(__file__))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

import gi  # noqa: E402

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("WebKit2", "4.1")
from gi.repository import Gdk, Gio, GLib, Gtk, WebKit2  # noqa: E402

from core import (os_datoteke, os_jbl, os_okna, os_omrezje, os_programi, os_scit, os_sistem,  # noqa: E402
                  os_stabilnost, os_zvok)

APP_ID = "io.github.memelandfaner.SafeerOS"


def _razlicica() -> str:
    try:
        with open(os.path.join(KOREN, "packaging", "VERSION_OS"), encoding="utf-8") as d:
            return d.read().strip()
    except Exception:
        return "0.4.1"


RAZLICICA = _razlicica()
CONTROL_NASTAVITVE = os.path.expanduser("~/.config/safeer-control/link.json")
BRSKALNIK_NASTAVITVE = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                                    "safeer-mint", "settings.json")
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
    prej = os_zvok._privzeto()[0]
    ok = control_dejanje("zvok-na-napravo", GLib.Variant("s", id_naprave))
    if ok and naprava.get("platforma") == "tv" and os_jbl.je_vrstica(prej):
        os_jbl.preklopi("tv")
    return ok


def zvok_ustavi() -> bool:
    """Zvok nazaj na racunalnik; ce je spet na vrstici JBL po Bluetoothu, jo preklopimo na Bluetooth."""
    ok = control_dejanje("zvok-ustavi")
    for _ in range(30):
        if not os_zvok.link_naprave()["zvok"]["naprava"]:
            break
        time.sleep(0.1)
    if ok and os_jbl.je_vrstica(os_zvok._privzeto()[0]):
        os_jbl.preklopi("bluetooth")
    return ok


def zvok_izhod(ime: str) -> bool:
    """Izbran izhod racunalnika. Ce zvok ta trenutek tece na napravo v Linku, ga Control najprej vrne
    (in navidezni izhod pospravi), sele nato nastavimo uporabnikovo izbiro - sicer bi jo prepisal."""
    if os_zvok.link_naprave()["zvok"]["naprava"]:
        control_dejanje("zvok-ustavi")
        for _ in range(30):
            if not os_zvok.link_naprave()["zvok"]["naprava"]:
                break
            time.sleep(0.1)
    ok = os_zvok.nastavi_izhod(ime)
    if ok and os_jbl.je_vrstica(ime):
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
        if n.get("vrsta") == "control" or n.get("platforma") == "linux" and socket.gethostname() in n.get("ime", ""):
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


def preimenuj_napravo(id_naprave: str, ime: str) -> dict:
    """Novo ime naprave (tudi tega racunalnika) za vse naprave v Linku; hrani ga sredisce."""
    return _control_naprave("Preimenuj", str(id_naprave or ""), str(ime or ""))


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


def zazeni_na_napravi(id_naprave: str, app: str) -> bool:
    return bool(_control_naprave("Zazeni", str(id_naprave or ""), str(app or "")).get("ok"))


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
    def __init__(self, v_oknu: bool = False, posnetek: str = "") -> None:
        zastavice = Gio.ApplicationFlags.NON_UNIQUE if posnetek else Gio.ApplicationFlags.FLAGS_NONE
        super().__init__(application_id=APP_ID, flags=zastavice)
        self.v_oknu = v_oknu
        self.posnetek = posnetek
        self.shramba = os_programi.Shramba()
        self.programi = os_programi.Programi(self.shramba)
        #: Scit: filtriranje DNS za ves racunalnik; ce je bil vklopljen, tece od zagona naprej.
        self.scit = os_scit.Scit(self.shramba)
        self.okno: Optional[Gtk.ApplicationWindow] = None
        self.pogled: Optional[WebKit2.WebView] = None
        self._ikone: dict = {}
        self._prvic = True
        #: Namizni nacin: Safeer OS je namizje (spodaj, programi nad njim) s svojo vrstico namesto
        #: Mintovega pulta. Sicer navadno okno (--okno, posnetki).
        self.namizje = not v_oknu and not posnetek and bool(self.shramba.get("celozaslonsko", True))
        self.vrstica: Optional[Gtk.Window] = None
        self.pogledi: list = []
        self._okna_zamik = 0
        self._koncano = False

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
        self._koren_strani = "file://" + os.path.join(KOREN, "assets", "os")
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
        okno.add(pogled)
        okno.connect("key-press-event", self._na_tipko)
        okno.connect("focus-in-event", lambda *a: (self._dogodek("fokus", None), False)[1])
        okno.connect("destroy", lambda *a: self._koncaj())
        self.okno, self.pogled = okno, pogled
        if self.posnetek:
            pogled.connect("load-changed", self._za_posnetek)
        okno.show_all()
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
        if self.namizje:
            vrni_mintov_pult(self.shramba)
        # Brez nasega razresevalnika bi racunalnik ostal brez DNS: nastavitev povrnemo.
        try:
            self.scit.koncaj()
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS] scit:", e)
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
        if dogodek != WebKit2.LoadEvent.FINISHED:
            return
        razdelek = os.environ.get("SAFEER_OS_RAZDELEK", "")
        if razdelek:
            GLib.timeout_add(1500, lambda: (self._js("window.safeerOsPojdi && safeerOsPojdi(%s)" % json.dumps(razdelek)), False)[1])
        def velikost():
            self.pogled.evaluate_javascript("innerWidth + 'x' + innerHeight + ' @' + devicePixelRatio", -1, None, None, None,
                                            lambda p, r: print("pogled:", p.evaluate_javascript_finish(r).to_string()))
            return False
        GLib.timeout_add(3500, velikost)
        GLib.timeout_add(4000, self._naredi_posnetek)

    def _naredi_posnetek(self) -> bool:
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
            "samozagon": lambda: self._samozagon(bool(a[0])) if a else je_samozagon(),
            "nazajVMint": lambda: self._nazaj_v_mint(bool(a[0]) if a else False),
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
            "splet": lambda: self._splet(str(a[0]) if a else ""),
            "iskanjeSplet": lambda: self._splet(_iskalnik() + GLib.uri_escape_string(str(a[0] if a else ""), None, False)),
            "povezava": stanje_povezave,
            "zaupanje": lambda: nastavi_zaupanje(bool(a[0]) if a else False),
            "novaNaprava": lambda: control_dejanje("nova-naprava"),
            "odjava": lambda: control_dejanje("odjava"),
            "omrezje": lambda: os_omrezje.stanje(bool(a[0]) if a else False),
            "omrezjePovezi": lambda: os_omrezje.povezi(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            "omrezjeOdklopi": lambda: os_omrezje.odklopi(str(a[0]) if a else ""),
            "omrezjeAktiviraj": lambda: os_omrezje.aktiviraj(str(a[0]) if a else ""),
            "omrezjePozabi": lambda: os_omrezje.pozabi(str(a[0]) if a else ""),
            "zvok": os_zvok.stanje,
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
            "preimenujNapravo": lambda: preimenuj_napravo(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            "programiNaprave": lambda: programi_naprave(str(a[0]) if a else ""),
            "zazeniNaNapravi": lambda: zazeni_na_napravi(str(a[0]) if a else "", str(a[1]) if len(a) > 1 else ""),
            "zvokUstavi": zvok_ustavi,
            "jbl": lambda: os_jbl.stanje(True),
            "jblVklop": lambda: os_jbl.vklopi(bool(a[0]) if a else False),
            "scit": self.scit.stanje,
            "scitVklop": lambda: self.scit.nastavi(bool(a[0]) if a else False),
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
        return {
            "jezik": _jezik(),
            "ime": GLib.get_real_name() if GLib.get_real_name() not in ("", "Unknown") else GLib.get_user_name(),
            "racunalnik": socket.gethostname(),
            "ozadje": ("file://" + GLib.uri_escape_string(ozadje, "/", False)) if ozadje else "",
            "razpolozljivo": os_sistem.razpolozljivo(),
            "mape": os_datoteke.uporabniske_mape(),
            "celozaslonsko": bool(self.shramba.get("celozaslonsko", True)) and not self.v_oknu,
            "namizje": self.namizje,
            "spletne": self.shramba.get("spletne", None),
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
        """Spletne aplikacije na domacem zaslonu: samo ime in naslov http(s), najvec 24."""
        cisti = []
        for e in (seznam if isinstance(seznam, list) else [])[:24]:
            if not isinstance(e, dict):
                continue
            ime, url = str(e.get("ime", ""))[:40].strip(), str(e.get("url", ""))[:300].strip()
            if ime and url.startswith(("https://", "http://")):
                cisti.append({"ime": ime, "url": url})
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
        if not naslov.startswith(("http://", "https://")):
            return False
        from shutil import which
        for ukaz in (["safeer-browser", naslov], ["safeer", naslov], ["xdg-open", naslov]):
            if which(ukaz[0]):
                try:
                    subprocess.Popen(ukaz, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                    return True
                except Exception:
                    continue
        return False

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
    app = SafeerOS(v_oknu="--okno" in sys.argv[1:], posnetek=posnetek)
    # Ce program tece brez tezav, zgodovina sesutij ni vec pomembna (sicer bi varni nacin ostal za vedno).
    GLib.timeout_add_seconds(120, lambda: (os_stabilnost.pozabi_sesutja("safeer-os"), False)[1])
    return app.run([sys.argv[0]])


if __name__ == "__main__":
    sys.exit(main())
