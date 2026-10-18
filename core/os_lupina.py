"""Lupina Safeer OS v Qt Quick (QML) na Linuxu - isto namizje kot na Windows (assets/os/qml).

Lastnik, 14. 10. 2026: »QML za sistemski vmesnik, HTML/WebKitGTK za spletne aplikacije in vsebine brskalnika«. Lupina
(namizje) je QML, Splet in vsebine ostanejo GTK4 + nas WebKitGTK - v ISTEM procesu. Zanko vrti GTK (g_application_run):
Qt na Linuxu uporablja razpecevalnik GLib, zato njegove casovnike, dogodke in izris QML obdela ista zanka (PoC na
testnem PC in v zabojniku 14. 10.: casovniki Qt in QML tecejo med Gtk.Application.run).

Most: QML poklice Most.klic(metoda, argumenti_json) z istimi imeni kot spletna stran delovne povrsine; klic gre v
SafeerOS._obdelaj_klic (glavna nit GLib), odgovor pride kot signal Most.odgovor. Klicatelj je QmlPogled, zato
_odgovori/_dogodek vedo, da gre odgovor lupini in ne strani WebKit.

Vklop: SAFEER_LUPINA=qml (privzeto, ce je PySide6 na voljo) ali html (prejsnja delovna povrsina v WebKitu).
"""

from __future__ import annotations

import contextlib
import hashlib
import itertools
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Optional

KOREN = Path(__file__).resolve().parents[1]
QML = KOREN / "assets" / "os" / "qml" / "Namizje.qml"
#: PySide6, ki ga prinese paket .deb (Mint 22 ga v svojih paketih nima; build_os_deb.sh -> packaging/pyside6_vendor.py).
#: V Flatpaku je v /app, iz izvorne mape ga najde Python sam.
#: AppImage ga ima izven usr/ (SAFEER_PYSIDE6), da ga linuxdeploy ne razreseva (packaging/build_os_appimage.sh).
for VENDOR in (KOREN / "vendor", Path(os.environ.get("SAFEER_PYSIDE6") or "/nic")):
    if VENDOR.is_dir() and str(VENDOR) not in sys.path:
        sys.path.insert(0, str(VENDOR))

#: Ozadja Safeer (paket safeer-cinnamon jih namesti v /usr/share/backgrounds/safeer; enaka kot na Windows).
OZADJA = (("jezero", "Gore in jezero", "Mountains and lake", "safeer-jezero.jpg"),
          ("gore", "Gore", "Mountains", "safeer-gore-3840x2160.png"),
          ("aurora", "Aurora", "Aurora", "safeer-aurora.jpg"),
          ("zora", "Zora", "Dawn", "safeer-zora.jpg"),
          ("globina", "Globina", "Depth", "safeer-globina.jpg"))
MAPE_OZADIJ = ("/run/host/usr/share/backgrounds/safeer", "/usr/share/backgrounds/safeer",
               str(KOREN / "packaging" / "tema-cinnamon" / "ozadje"))
#: Imena ozadij v drugih jezikih namizja (sl in en sta v OZADJA).
IMENA_OZADIJ = {
    "de": {"jezero": "Berge und See", "gore": "Berge", "aurora": "Polarlicht", "zora": "Morgenröte", "globina": "Tiefe"},
    "es": {"jezero": "Montañas y lago", "gore": "Montañas", "aurora": "Aurora", "zora": "Alba", "globina": "Profundidad"},
    "fr": {"jezero": "Montagnes et lac", "gore": "Montagnes", "aurora": "Aurore", "zora": "Aube", "globina": "Profondeur"},
    "it": {"jezero": "Montagne e lago", "gore": "Montagne", "aurora": "Aurora", "zora": "Alba", "globina": "Profondità"},
}
PRIVZETI_VIDEZ = {"zameglitev": 1.0, "prosojnost": 0.55}
SLIKE = (".jpg", ".jpeg", ".png", ".webp", ".bmp")

_qt_app = None


def zelena() -> bool:
    """Ali naj bo namizje QML: SAFEER_LUPINA=html vrne prejsnjo delovno povrsino; brez PySide6 tudi."""
    if os.environ.get("SAFEER_LUPINA", "qml").strip().lower() == "html":
        return False
    import importlib.util
    return importlib.util.find_spec("PySide6") is not None and QML.is_file()


_NAMIZJE_SPREMENLJIVKE = ("XDG_CURRENT_DESKTOP", "DESKTOP_SESSION", "GNOME_DESKTOP_SESSION_ID", "KDE_FULL_SESSION")
_GTK_TEME_QT = ("", "gtk3", "gtk2", "gnome")


@contextlib.contextmanager
def brez_gtk_teme_qt():
    """Qt v tem procesu ne sme naloziti GTK3 (modul teme libqgtk3): v istem procesu tece GTK4 in obe knjiznici
    registrirata iste tipe GObject (GtkWidget ...), lupina se ne izrise (testni PC 15. 10. 2026, zagon iz seje Cinnamon:
    »cannot register existing type 'GtkWidget'«, vidno samo ozadje). Qt temo GTK3 izbere po XDG_CURRENT_DESKTOP
    (GNOME, Cinnamon, Unity ...), zato med ustvarjanjem QApplication: tema xdgdesktopportal (portal, brez GTK), namizne
    spremenljivke pa zacasno skrite in nato vrnjene - programi, ki jih Safeer OS zazene, jih potrebujejo."""
    if os.environ.get("QT_QPA_PLATFORMTHEME", "").strip().lower() in _GTK_TEME_QT:
        os.environ["QT_QPA_PLATFORMTHEME"] = "xdgdesktopportal"
    shranjeno = {k: os.environ.pop(k) for k in _NAMIZJE_SPREMENLJIVKE if k in os.environ}
    try:
        yield
    finally:
        os.environ.update(shranjeno)


def pripravi(argv: list, pozno: bool = False) -> bool:
    """QGuiApplication pred GTK (en na proces). Zanko potem vrti Gtk.Application.run.

    pozno=True: GTK v tem procesu ze ima okna (npr. Safeer Player, nato `--okno`). Qt potem z GLX ne dobi konteksta
    (testni PC 14. 10. 2026: »QGLXContext: Failed to create dummy context« in sesutje), zato EGL kot GTK4."""
    global _qt_app
    if _qt_app is not None:
        return True
    if not zelena():
        return False
    nastavljen_egl = pozno and "QT_XCB_GL_INTEGRATION" not in os.environ
    if nastavljen_egl:
        os.environ["QT_XCB_GL_INTEGRATION"] = "xcb_egl"
    try:
        from PySide6.QtCore import QCoreApplication, Qt
        from PySide6.QtGui import QGuiApplication
        from PySide6.QtWidgets import QApplication   # QApplication (ne QGuiApplication): QSystemTrayIcon (kuverta)
        os.environ.setdefault("QT_QPA_PLATFORM", platforma_qt())
        # HiDPI: delno merilo zaslona (125, 150, 175 %) Qt uporabi natancno, brez zaokrozanja na 1x/2x - enako kot GTK4.
        # Izmerjeno 18. 10. 2026, brezglavi sway z merilom 1,5: okno ima devicePixelRatio 1,5 (PassThrough), z Round 2,0
        # (sestavljalnik bi sliko pomanjsal - mehko besedilo). QScreen.devicePixelRatio tam kaze 2,0 (celo merilo izhoda).
        if QApplication.instance() is None:
            QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
        with brez_gtk_teme_qt():
            _qt_app = QApplication.instance() or QApplication(list(argv) or ["safeer-os"])
        _qt_app.setQuitOnLastWindowClosed(False)     # zivljenje procesa vodi Gtk.Application
        _qt_app.setApplicationName("Safeer OS")
        _qt_app.setDesktopFileName("io.github.memelandfaner.SafeerOS")
        if nastavljen_egl:
            os.environ.pop("QT_XCB_GL_INTEGRATION", None)   # programi, ki jih Safeer OS zazene, naj izberejo sami
        return True
    except Exception as e:  # noqa: BLE001 - brez Qt: prejsnja delovna povrsina
        print("[SafeerOS lupina] Qt ni na voljo:", e, flush=True)
        _qt_app = None
        return False


def dejavna() -> bool:
    return _qt_app is not None


def platforma_qt(okolje: Optional[dict] = None) -> str:
    """Vticnik Qt za to sejo (QT_QPA_PLATFORM, ce ga uporabnik ni dolocil sam).

    X11 (Mint): xcb - Qt naj ne ugiba Waylanda, ki ga seja nima. Wayland: najprej wayland (nativno, delno merilo in vec
    monitorjev pravilno), xcb samo kot rezerva prek XWaylanda. Prej je odlocal le XDG_SESSION_TYPE: sway, zagnan iz
    konzole, ga nima, zato je Qt sel prek XWaylanda, GTK pa nativno - dve razlicni merili v istem procesu."""
    from core import seja_prikaza
    return "wayland;xcb" if seja_prikaza.je_wayland(okolje) else "xcb"


def nativno_x11() -> bool:
    """Ali okna Qt tega procesa tecejo prek X11 (samo tam imajo winId() X okna za lastnosti EWMH)."""
    try:
        from PySide6.QtGui import QGuiApplication
        return QGuiApplication.platformName() == "xcb"
    except Exception:  # noqa: BLE001
        return False


def zaslon_za_okno():
    """QScreen, na katerem naj se odpre novo okno: X11 - kjer je kazalec miske (tam uporabnik dela, vec monitorjev),
    sicer primarni. Wayland: primarni samo za velikost, mesto izbere sestavljalnik (GNOME: monitor s kazalcem)."""
    from PySide6.QtGui import QCursor, QGuiApplication
    if nativno_x11():
        zaslon = QGuiApplication.screenAt(QCursor.pos())
        if zaslon is not None:
            return zaslon
    return QGuiApplication.primaryScreen()


def dostopnost_sistema(Gio=None, Gtk=None) -> dict:
    """Velikost besedila, kontrast in animacije sistema za namizje QML, kjer ni Safeer Cinnamon (GNOME na Ubuntu …).

    GNOME: Nastavitve > Dostopnost (Vecje besedilo = text-scaling-factor 1,25, Visok kontrast, Animacije). Animacije iz
    Gtk.Settings: isti vir, iz katerega WebKitGTK spletnim stranem nastavi prefers-reduced-motion - namizje QML in strani
    se tako ujemata. Manjkajoca shema ali GTK: privzeto (100 %, brez kontrasta, animacije vklopljene)."""
    izid = {"tekstOdstotek": 100, "kontrast": False, "gibanje": True}
    try:
        if Gio is None:
            from gi.repository import Gio
        vir = Gio.SettingsSchemaSource.get_default()
        if vir is not None and vir.lookup("org.gnome.desktop.interface", True) is not None:
            izid["tekstOdstotek"] = int(round(Gio.Settings.new("org.gnome.desktop.interface")
                                              .get_double("text-scaling-factor") * 100))
        shema = vir.lookup("org.gnome.desktop.a11y.interface", True) if vir is not None else None
        if shema is not None and shema.has_key("high-contrast"):
            izid["kontrast"] = Gio.Settings.new("org.gnome.desktop.a11y.interface").get_boolean("high-contrast")
    except Exception as e:  # noqa: BLE001
        print("[SafeerOS lupina] dostopnost:", e, flush=True)
    try:
        if Gtk is None and "gi.repository.Gtk" in sys.modules:
            Gtk = sys.modules["gi.repository.Gtk"]
        nastavitve = Gtk.Settings.get_default() if Gtk is not None else None
        if nastavitve is not None:
            izid["gibanje"] = bool(nastavitve.get_property("gtk-enable-animations"))
    except Exception as e:  # noqa: BLE001
        print("[SafeerOS lupina] animacije:", e, flush=True)
    return izid


# ---------------------------------------------------------------------------------------- videz (ozadje, plosce)
def _pot_ozadja_safeer(kljuc: str) -> str:
    ime = next((o[3] for o in OZADJA if o[0] == kljuc), "")
    for mapa in MAPE_OZADIJ:
        pot = os.path.join(mapa, ime)
        if ime and os.path.isfile(pot):
            return pot
    return ""


def _preveri_videz(sprememba: dict) -> dict:
    izid: dict = {}
    oz = sprememba.get("ozadje")
    if isinstance(oz, str):
        if oz.startswith("safeer:") and any(o[0] == oz[7:] for o in OZADJA):
            izid["ozadje"] = oz
        elif os.path.isabs(oz) and oz.lower().endswith(SLIKE) and os.path.isfile(oz):
            izid["ozadje"] = oz
    for k, lo, hi in (("zameglitev", 0.0, 1.0), ("prosojnost", 0.2, 0.9)):
        x = sprememba.get(k)
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            izid[k] = round(max(lo, min(hi, float(x))), 3)
    # Iskanje po spletu v privzetem brskalniku namesto plosce na namizju (stikalo delovne povrsine, 15. 10. 2026 tudi QML).
    if isinstance(sprememba.get("spletVBrskalniku"), bool):
        izid["spletVBrskalniku"] = sprememba["spletVBrskalniku"]
    return izid


def videz(shramba) -> dict:
    v = dict(PRIVZETI_VIDEZ)
    shranjeno = shramba.get("namizje_videz", None)
    if isinstance(shranjeno, dict):
        v.update(_preveri_videz(shranjeno))
    return v


def nastavi_videz(shramba, sprememba: dict, nastavi_ozadje_sistema: Optional[Callable[[str], None]] = None) -> dict:
    """Shrani zameglitev/prosojnost; ozadje je na Linuxu ozadje sistema (Cinnamon), zato ga nastavimo tam - enako
    vidijo namizje, zaklenjen zaslon in Splet."""
    if not isinstance(sprememba, dict):
        return videz(shramba)
    if sprememba.get("privzeto"):
        shramba.set("namizje_videz", {})
        sprememba = {"ozadje": "safeer:jezero"}
    preverjeno = _preveri_videz(sprememba)
    oz = preverjeno.pop("ozadje", "")
    trenutni = videz(shramba)
    trenutni.update(preverjeno)
    trenutni.pop("ozadje", None)
    shramba.set("namizje_videz", trenutni)
    if oz and nastavi_ozadje_sistema is not None:
        pot = _pot_ozadja_safeer(oz[7:]) if oz.startswith("safeer:") else oz
        if pot:
            nastavi_ozadje_sistema(pot)
    return trenutni


GSETTINGS_OZADJE = ("org.cinnamon.desktop.background", "picture-uri")
#: GNOME (Ubuntu 24.04): ozadje za svetli in temni slog - nastavimo oba, da izbira velja v obeh.
GSETTINGS_OZADJE_GNOME = (("org.gnome.desktop.background", "picture-uri"), ("org.gnome.desktop.background", "picture-uri-dark"))


def uri_ozadja(pot: str) -> str:
    """URI slike, kot ga vidi racunalnik: v Flatpaku je /run/host/usr/... na gostitelju /usr/..."""
    from urllib.parse import quote
    from core import gostitelj
    return "file://" + quote(gostitelj.na_gostitelju(pot), safe="/")


def nastavi_ozadje_sistema(pot: str, zazeni: Optional[Callable[[list], Any]] = None) -> bool:
    """Ozadje Cinnamona (vidijo ga namizje, zaklenjen zaslon in Splet).

    Flatpak: shema org.cinnamon.desktop.background ni v runtimu GNOME (lookup() vrne None), zato pisemo z ovojem
    gsettings v /app/host-bin, ki tece na gostitelju - tako kot branje (os_sistem.ozadje_namizja). Prej izbira
    ozadja v Flatpaku ni naredila nicesar (pregled 14. 10. 2026). Paket .deb: Gio.Settings + sync(), da takojsnje
    branje (videz po spremembi) ze vidi novo vrednost."""
    uri = uri_ozadja(pot)
    from core import seja_prikaza
    # GNOME: org.gnome.desktop.background (oba sloga); sicer Cinnamon. Prej je izbira ozadja na GNOME ni naredila nic.
    kljuci = GSETTINGS_OZADJE_GNOME if seja_prikaza.namizje() == "gnome" else (GSETTINGS_OZADJE,)
    try:
        from core import gostitelj
        if gostitelj.v_flatpaku():
            import shutil
            import subprocess
            ukaz = "/app/host-bin/gsettings" if os.path.exists("/app/host-bin/gsettings") else shutil.which("gsettings")
            if not ukaz:
                return False
            ok = True
            for shema, kljuc in kljuci:
                argv = [ukaz, "set", shema, kljuc, uri]
                ok = (bool(zazeni(argv)) if zazeni is not None
                      else subprocess.run(argv, capture_output=True, timeout=5).returncode == 0) and ok
            return ok
        from gi.repository import Gio
        vir = Gio.SettingsSchemaSource.get_default()
        if vir is None or any(vir.lookup(shema, True) is None for shema, _k in kljuci):
            return False
        for shema, kljuc in kljuci:
            Gio.Settings.new(shema).set_string(kljuc, uri)
        Gio.Settings.sync()
        return True
    except Exception as e:  # noqa: BLE001
        print("[SafeerOS lupina] ozadje:", e, flush=True)
        return False


def _url(pot: str) -> str:
    from PySide6.QtCore import QUrl
    return QUrl.fromLocalFile(pot).toString() if pot else ""


# ---------------------------------------------------------------------------------------- paleta (en vir: tokens.css)
TOKENI = KOREN / "assets" / "os" / "tokens.css"


def _barva_css(vrednost: str) -> Optional[tuple]:
    """#rgb, #rrggbb ali rgb(a)(r, g, b[, a]) -> (r, g, b, a) z r, g, b 0-255 in a 0-1; drugo (sence, var()) -> None."""
    import re
    v = vrednost.strip().lower()
    m = re.fullmatch(r"#([0-9a-f]{3}|[0-9a-f]{6})", v)
    if m:
        h = m.group(1)
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    m = re.fullmatch(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*([\d.]+)\s*)?\)", v)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)), float(m.group(4)) if m.group(4) else 1.0)
    return None


def tokeni(kontrast: bool = False, pot: Path = TOKENI) -> dict:
    """Barve iz tokens.css: blok :root, ob kontrastu prepisan z blokom ».kontrast« (isti kot na straneh WebKit)."""
    import re
    try:
        css = re.sub(r"/\*.*?\*/", "", pot.read_text(encoding="utf-8"), flags=re.S)
    except OSError:
        return {}
    izid: dict = {}
    for izbirnik, telo in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
        izbirniki = [x.strip() for x in izbirnik.split(",")]
        if ":root" in izbirniki or (kontrast and ".kontrast" in izbirniki):
            for ime, vrednost in re.findall(r"--([\w-]+)\s*:\s*([^;]+);", telo):
                b = _barva_css(vrednost)
                if b is not None:
                    izid[ime] = b
    return izid


def _qml_barva(b: tuple) -> str:
    """QML: #rrggbb ali #aarrggbb (prosojnost spredaj)."""
    r, g, m, a = b
    return ("#%02x%02x%02x" % (r, g, m)) if a >= 1 else ("#%02x%02x%02x%02x" % (round(a * 255), r, g, m))


def _rgb(b: tuple) -> list:
    return [round(b[0] / 255, 4), round(b[1] / 255, 4), round(b[2] / 255, 4)]


VRSTE_DATOTEK = ("mapa", "slika", "video", "zvok", "dokument", "splet", "arhiv", "program", "naprava")


def paleta(kontrast: bool = False, merilo: float = 1.0, pot: Path = TOKENI) -> dict:
    """Paleta za Namizje.qml iz tokens.css - iste barve kot Nastavitve, Medijski center, Splet in delovna povrsina.
    Prej je imelo namizje QML svojo zeleno (#54d6a5), vmesnik pa modro (pregled celovitosti 15. 10. 2026)."""
    t = tokeni(kontrast, pot)
    if not t:
        return {}
    b = lambda ime: _qml_barva(t[ime])  # noqa: E731
    return {
        "poudarek": b("zelena"), "poudarekTemna": b("zelena-temna"), "besedilo": b("besedilo"), "medlo": b("medlo"),
        "tise": b("tise"), "vnos": b("media-meni"), "ozadje": b("ozadje"), "ozadje2": b("ozadje-2"),
        "ok": b("ok"), "rdeca": b("rdeca"), "opozorilo": b("opozorilo"), "fokus": b("fokus"),
        "karticaRgb": _rgb(t["kartica"]), "poudarekRgb": _rgb(t["zelena"]), "prekrivRgb": _rgb(t["prekriv"]),
        "robRgb": _rgb(t["rob"]), "robA": t["rob"][3],
        "vrste": {v: b("vrsta-" + v) for v in VRSTE_DATOTEK if "vrsta-" + v in t},
        "kontrast": bool(kontrast), "merilo": round(max(1.0, min(2.0, float(merilo or 1.0))), 3),
    }


def merilo_besedila(odstotek, razmerje_zaslona: float = 1.0) -> float:
    """Velikost besedila sistema (Cinnamon text-scaling-factor) za namizje QML. QML pise v pikslih (font.pixelSize), ki
    jih povecava pisave sistema ne doseze. Ce je Qt povecavo ze uporabil za ves zaslon (razmerje pik iz Xft.dpi),
    je ne podvojimo."""
    try:
        skala = float(odstotek) / 100.0
    except (TypeError, ValueError):
        return 1.0
    if skala <= 1.0:
        return 1.0
    if razmerje_zaslona > 1.0 and abs(razmerje_zaslona - skala) < 0.05:
        return 1.0
    return min(2.0, skala)


def videz_za_qml(shramba, ozadje_sistema: str, jezik: str = "sl", paleta: Optional[dict] = None) -> dict:
    v = videz(shramba)
    ozadja, izbira = [], ""
    for kljuc, sl, en, _ime in OZADJA:
        pot = _pot_ozadja_safeer(kljuc)
        if pot:
            ime = sl if jezik == "sl" else IMENA_OZADIJ.get(jezik, {}).get(kljuc, en)
            ozadja.append({"kljuc": "safeer:" + kljuc, "ime": ime, "url": _url(pot)})
            if ozadje_sistema and os.path.basename(pot) == os.path.basename(ozadje_sistema):
                izbira = "safeer:" + kljuc
    izid = {"izbira": izbira or ozadje_sistema, "ozadje": _url(ozadje_sistema), "zameglitev": v["zameglitev"],
            "prosojnost": v["prosojnost"], "spletVBrskalniku": bool(v.get("spletVBrskalniku")), "ozadja": ozadja, "windows": "",
            "lastna": "" if izbira else ozadje_sistema}
    if paleta:
        izid["paleta"] = paleta
    return izid


def _mapa_ikon() -> Path:
    mapa = Path(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")) / "safeer-os" / "ikone-namizja"
    mapa.mkdir(parents=True, exist_ok=True)
    return mapa


def ikona_v_url(ikona: str) -> str:
    """Ikona programa za QML Image: data:image;base64 -> datoteka v predpomnilniku, pot -> file:// URL."""
    import base64
    if not ikona:
        return ""
    if ikona.startswith("data:image/") and ";base64," in ikona:
        glava, podatki = ikona.split(";base64,", 1)
        koncnica = "svg" if "svg" in glava else ("png" if "png" in glava else "jpg")
        pot = _mapa_ikon() / (hashlib.sha1(podatki.encode("ascii", "ignore")).hexdigest()[:20] + "." + koncnica)
        if not pot.exists():
            try:
                pot.write_bytes(base64.b64decode(podatki))
            except (OSError, ValueError):
                return ""
        return _url(str(pot))
    if ikona.startswith("/"):
        return _url(ikona)
    return ikona


def naprave_za_izbiro(vse: list, s_programi: list, z_datotekami: list) -> list:
    """Druge naprave v Safeer Linku za izbiro na namizju (ista oblika kot na Windows): ena vrstica na napravo; racunalnik
    je v Linku lahko dvakrat (Safeer OS in njegov Control, id »…-control«)."""
    programi = {n["id"] for n in s_programi}
    datoteke = {n["id"] for n in z_datotekami}
    po_kljucu: dict = {}
    for n in vse:
        id_n = str(n.get("id") or "")
        if n.get("ta") or not id_n or (id_n not in programi and id_n not in datoteke):
            continue
        kljuc = id_n[:-len("-control")] if id_n.endswith("-control") else id_n
        v = po_kljucu.setdefault(kljuc, {"kljuc": kljuc, "ime": "", "platforma": "", "programi": "", "datoteke": ""})
        if not v["ime"] or not id_n.endswith("-control"):
            v["ime"] = str(n.get("ime") or id_n)
            v["platforma"] = str(n.get("platforma") or "")
        if id_n in programi and (not v["programi"] or not id_n.endswith("-control")):
            v["programi"] = id_n
        if id_n in datoteke and (not v["datoteke"] or id_n.endswith("-control")):
            v["datoteke"] = id_n
    return sorted(po_kljucu.values(), key=lambda v: v["ime"].lower())


def robovi_delovnega_obmocja(zaslon, delovno) -> dict:
    """Odmiki vsebine od robov zaslona, ki jih zasedajo pulti: {robZgoraj, robSpodaj, robLevo, robDesno} (piksli)."""
    def r(x):   # QRect ali (x, y, sirina, visina)
        return (x.x(), x.y(), x.width(), x.height()) if hasattr(x, "x") else tuple(x)
    zx, zy, zs, zv = r(zaslon)
    dx, dy, ds, dv = r(delovno)
    if ds <= 0 or dv <= 0:
        return {"robZgoraj": 0, "robSpodaj": 0, "robLevo": 0, "robDesno": 0}
    return {"robZgoraj": max(0, dy - zy), "robLevo": max(0, dx - zx),
            "robSpodaj": max(0, (zy + zv) - (dy + dv)), "robDesno": max(0, (zx + zs) - (dx + ds))}


def najmanjsa_velikost(sirina: int, visina: int) -> tuple:
    """Minimum okna aplikacije: 960 x 620, a nikoli vec od delovnega obmocja. HiDPI zmanjsa logicni zaslon: 1366x768
    pri 125 % je 1093x614, 1920x1080 pri 200 % je 960x540 (izmerjeno 18. 10. 2026, sway z merilom 2: logicni izhod
    960x540) - minimum 620 bi okno potisnil cez spodnji rob zaslona."""
    return (max(1, min(960, int(sirina))), max(1, min(620, int(visina))))


def velikost_okna(sirina: int, visina: int) -> tuple:
    """Velikost okna aplikacije iz delovnega obmocja: 90 %, najvec 1440 x 900, najmanj minimum okna."""
    ms, mv = najmanjsa_velikost(sirina, visina)
    return (max(ms, min(1440, int(sirina * 0.9))), max(mv, min(900, int(visina * 0.9))))


# ---------------------------------------------------------------------------------------- most in okno
def _ustvari_razrede():
    from PySide6.QtCore import QObject, QSize, QUrl, Qt, Signal, Slot
    from PySide6.QtQuick import QQuickView

    class Most(QObject):
        """QML -> Python: klic vrne id, odgovor pride kot signal (iz katerekoli niti; Qt ga dostavi v glavno nit)."""
        odgovor = Signal(int, bool, str)
        dogodek = Signal(str, str)

        def __init__(self, lupina) -> None:
            super().__init__()
            self._lupina = lupina
            self._stevec = itertools.count(1)

        @Slot(str, str, result=int)
        def klic(self, metoda: str, argumenti: str) -> int:
            klic_id = next(self._stevec)
            try:
                a = json.loads(argumenti or "[]")
            except ValueError:
                a = []
            self._lupina.klic(klic_id, metoda, a if isinstance(a, list) else [])
            return klic_id

        @Slot(str, result=str)
        def datotekaUrl(self, pot: str) -> str:  # noqa: N802 - ime za QML
            return QUrl.fromLocalFile(pot).toString() if pot else ""

        @Slot(str, result=str)
        def datotekaPot(self, naslov: str) -> str:  # noqa: N802 - ime za QML
            """Spust iz drugega programa: file:// -> pot (drugi naslovi, npr. https, niso datoteke tega racunalnika)."""
            u = QUrl(naslov or "")
            return u.toLocalFile() if u.isLocalFile() else ""

        @Slot(result=bool)
        def ctrl(self) -> bool:
            """Ali je med spustom drzana tipka Ctrl (vlecenje znotraj Datotek: kopija namesto premika)."""
            from PySide6.QtGui import QGuiApplication
            return bool(QGuiApplication.queryKeyboardModifiers() & Qt.KeyboardModifier.ControlModifier)

    class Okno(QQuickView):
        def __init__(self, v_oknu: bool = False) -> None:
            super().__init__()
            if v_oknu:
                # Aplikacija Safeer OS (GNOME, KDE …): isto namizje v navadnem oknu z robom in gumbom v pultu.
                self.setTitle("Safeer OS")
                self.setMinimumSize(QSize(960, 620))
            else:
                self.setTitle("Safeer OS namizje")
                self.setFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnBottomHint)
            self.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
            self.setColor(Qt.GlobalColor.black)

    return Most, Okno


class QmlPogled:
    """Klicatelj za SafeerOS._obdelaj_klic (namesto pogleda WebKit): odgovori in dogodki gredo v QML."""

    def __init__(self, most) -> None:
        self._most = most

    def qml_odgovor(self, klic_id: int, ok: bool, podatki: Any) -> None:
        self._most.odgovor.emit(int(klic_id), bool(ok), json.dumps(podatki, ensure_ascii=False, default=str))

    def qml_dogodek(self, vrsta: str, podatki: Any) -> None:
        self._most.dogodek.emit(str(vrsta), json.dumps(podatki, ensure_ascii=False, default=str))

    # Del API pogleda WebKit, ki ga _obdelaj_klic kdaj uporabi (okno klica, naslov)
    def get_uri(self) -> str:
        return "qml:namizje"

    def get_root(self):
        return None


class Namizje:
    """Namizje QML na Linuxu: cez cel zaslon, pod vsemi okni (X11 _NET_WM_WINDOW_TYPE_DESKTOP), brez gumba v pultu.

    v_oknu=True: aplikacija Safeer OS (`safeer-os --okno` na GNOME, KDE …) pokaze ISTO namizje v navadnem oknu -
    ena koda za namizno okolje in aplikacijo, vsaka novost je takoj v obeh (lastnik, 14. 10. 2026). Zaprtje okna
    poklice ob_koncu (kot zaprtje starega glavnega okna)."""

    def __init__(self, safeer_os, ob_koncu: Optional[Callable[[], None]] = None, v_oknu: bool = False) -> None:
        from PySide6.QtCore import QUrl
        Most, Okno = _ustvari_razrede()
        self.os = safeer_os
        self.v_oknu = bool(v_oknu)
        self.most = Most(self)
        self.pogled = QmlPogled(self.most)
        self.okno = Okno(self.v_oknu)
        self.okno.rootContext().setContextProperty("Most", self.most)
        # Zmanjsano gibanje ze ob prvem izrisu (vstop panelov), ne sele po odgovoru »zacetek«.
        self.okno.rootContext().setContextProperty("Gibanje", bool(dostopnost_sistema()["gibanje"]))
        self.okno.setSource(QUrl.fromLocalFile(str(QML)))
        for napaka in self.okno.errors():
            print("[SafeerOS lupina]", napaka.toString(), flush=True)
        if self.okno.status() == self.okno.Status.Error:
            # Oba nacina imata rezervo: aplikacija v oknu staro okno index.html, namizje (--delovna) delovno
            # povrsino WebKit (delovna.html). Brez tega crno okno brez okvirja cez cel zaslon (pregled 14. 10.).
            raise RuntimeError("namizje QML se ni naložilo")
        self._ob_koncu = ob_koncu
        self._spremljaj_temo()
        if self.v_oknu:
            # Zaprtje okna = okno postane nevidno. Signala closing PySide6 6.11 ne dostavi (QQuickCloseEvent* se ne
            # pretvori), prepis event() v Pythonu pa je na testnem PC zaklenil glavno nit (crno okno) - 14. 10. 2026.
            self._prikazano = False
            self.okno.visibleChanged.connect(self._vidnost)
            return
        from PySide6.QtGui import QGuiApplication
        # Primarni zaslon se lahko zamenja (prenosnik na TV prek HDMI: eDP ugasne, HDMI postane primarni). Prej je
        # bila povezana samo geometrija ZACETNEGA zaslona, zato je namizje ostalo v velikosti prenosnika (18. 10. 2026).
        aplikacija = QGuiApplication.instance()
        aplikacija.primaryScreenChanged.connect(lambda *_: self._zaslon_spremenjen())
        aplikacija.screenAdded.connect(lambda *_: self._zaslon_spremenjen())
        aplikacija.screenRemoved.connect(lambda *_: self._zaslon_spremenjen())
        self._spremljaj_zaslon(QGuiApplication.primaryScreen())

    # ------------------------------------------------------------------ klici
    def klic(self, klic_id: int, metoda: str, a: list) -> None:
        from gi.repository import GLib

        def na_glavni() -> bool:
            try:
                if not self._lastna(klic_id, metoda, a):
                    self.os._obdelaj_klic(self.pogled, klic_id, metoda, a)
            except Exception as e:  # noqa: BLE001
                print("[SafeerOS lupina]", metoda, e, flush=True)
                self.pogled.qml_odgovor(klic_id, False, str(e))
            return False
        # Klic je ze v glavni niti (zanka GLib), a QML naj se najprej vrne - kot pri spletni strani.
        GLib.idle_add(na_glavni)

    def _odgovor_v_ozadju(self, klic_id: int, delo: Callable[[], Any]) -> None:
        def nit() -> None:
            try:
                self.pogled.qml_odgovor(klic_id, True, delo())
            except Exception as e:  # noqa: BLE001
                self.pogled.qml_odgovor(klic_id, False, str(e))
        threading.Thread(target=nit, daemon=True, name="safeer-lupina").start()

    def _lastna(self, klic_id: int, metoda: str, a: list) -> bool:
        """Metode, ki jih ima samo namizje QML (oblika podatkov kot na Windows). Ostale gredo SafeerOS."""
        import safeer_os as so
        odg = self.pogled.qml_odgovor
        if metoda == "programiNamizja":
            seznam = self.os._seznam_programov() or []
            odg(klic_id, True, [dict(p, ikona=ikona_v_url(str(p.get("ikona") or ""))) for p in seznam])
        elif metoda == "programiNapraveNamizja":
            def delo():
                r = so.programi_naprave(str(a[0]) if a else "") or {}
                if isinstance(r, dict):
                    r = dict(r, programi=[dict(p, ikona=ikona_v_url(str(p.get("ikona") or "")))
                                          for p in r.get("programi") or []])
                return r
            self._odgovor_v_ozadju(klic_id, delo)
        elif metoda == "napraveNamizja":
            self._odgovor_v_ozadju(klic_id, lambda: naprave_za_izbiro(
                so.vse_naprave(), so.naprave_s_programi(), so.naprave_z_datotekami()))
        elif metoda == "oddaljeniZaslon":
            # Gumb »Oddaljeno« v Programih (isti QML kot na Windows): na Linuxu odpre zaslon naprave Safeer Control
            # (upravljaj_racunalnik, kot »Upravljaj« na delovni povrsini). Prej je klic koncal z neznano metodo (15. 10. 2026).
            self._odgovor_v_ozadju(klic_id, lambda: so.upravljaj_racunalnik(str(a[0]) if a else ""))
        elif metoda == "videzNamizja":
            odg(klic_id, True, self.videz())
        elif metoda == "nastaviVidezNamizja":
            sprememba = a[0] if a and isinstance(a[0], dict) else {}
            if isinstance(sprememba.get("sporocila"), bool):
                # Sporocila v celoti (Prilagodi namizje): isti vklop kot v Nastavitvah Safeer OS (core/sporocila/vklop.py).
                self.os._nastavi_sporocila(sprememba["sporocila"])
            nastavi_videz(self.os.shramba, sprememba, self._nastavi_ozadje_sistema)
            v = self.videz()
            odg(klic_id, True, v)
            self.dogodek("videz", v)
        elif metoda == "zacetek":
            z = dict(self.os._zacetek())
            v = self.videz(str(z.get("jezik") or "sl"))
            from core import os_dock
            z.update({"ozadje": v["ozadje"], "videz": v, "platforma": "linux", "vOknu": self.v_oknu,
                      "dock": os_dock.je_namescen()})
            odg(klic_id, True, z)
        else:
            return False
        return True

    def _nastavi_ozadje_sistema(self, pot: str) -> None:
        nastavi_ozadje_sistema(pot)

    def videz(self, jezik: str = "") -> dict:
        """Ozadje in plosce (Prilagodi namizje) + paleta iz tokens.css + kontrast in velikost besedila sistema
        (videz_cinnamon, isto kot stikali delovne povrsine). Prej je QML dobil samo ozadje (pregled 15. 10. 2026)."""
        from core import os_sistem
        import safeer_os as so
        try:
            sistem = dict(so.videz_cinnamon())
        except Exception as e:  # noqa: BLE001 - brez Cinnamona: privzeti videz
            print("[SafeerOS lupina] videz sistema:", e, flush=True)
            sistem = {}
        dostopnost = dostopnost_sistema()
        if not sistem.get("naVoljo"):
            # Brez Safeer Cinnamon (GNOME na Ubuntu 24.04, KDE …): velikost besedila in kontrast iz dostopnosti sistema.
            # Prej je namizje QML tam ostalo pri 100 % in brez kontrasta, ceprav je uporabnik oboje vklopil.
            sistem = dict(sistem, kontrast=dostopnost["kontrast"], tekstOdstotek=dostopnost["tekstOdstotek"])
        razmerje = 1.0
        if nativno_x11():
            # Samo X11: tam Qt merilo zaslona izpelje iz Xft.dpi, ki ze vsebuje povecavo besedila (ne podvojimo).
            # Na Waylandu je razmerje merilo monitorja (npr. 1,25) in z velikostjo besedila nima zveze.
            try:
                from PySide6.QtGui import QGuiApplication
                razmerje = float(QGuiApplication.primaryScreen().devicePixelRatio())
            except Exception:  # noqa: BLE001
                razmerje = 1.0
        kontrast = bool(sistem.get("kontrast"))
        p = paleta(kontrast, merilo_besedila(sistem.get("tekstOdstotek") or 100, razmerje))
        v = videz_za_qml(self.os.shramba, os_sistem.ozadje_namizja() or "", jezik or so._jezik(), p)
        # cinnamon: velikost besedila in kontrast se nastavita v sistemu (videzCinnamonNastavi, kot na delovni povrsini).
        # gibanje: animacije sistema (zmanjsano gibanje) - QML jih brez tega ne bi upostevalo (AGENTS.md, dostopnost).
        v.update({"kontrast": kontrast, "tekstOdstotek": int(sistem.get("tekstOdstotek") or 100),
                  "cinnamon": bool(sistem.get("naVoljo")), "gibanje": dostopnost["gibanje"]})
        from core.sporocila import vklop
        v["sporocila"] = vklop.sporocila_vklopljena()
        return v

    def _spremljaj_temo(self) -> None:
        """Tema (Kontrast) in velikost besedila se spremenita v Nastavitvah ali ukazu safeer-cinnamon: namizje QML
        dobi novo paleto takoj (dogodek »videz«). Delovna povrsina WebKit ima isto v safeer_os._ustvari_delovno."""
        self._nastavitve_sistema = []
        try:
            from gi.repository import Gio
            vir = Gio.SettingsSchemaSource.get_default()
            for shema, kljuc in (("org.cinnamon.theme", "name"), ("org.cinnamon.desktop.interface", "text-scaling-factor"),
                                 ("org.gnome.desktop.interface", "text-scaling-factor"),
                                 ("org.gnome.desktop.a11y.interface", "high-contrast"),
                                 # Ozadje, izbrano v Nastavitvah GNOME (Videz), takoj tudi na namizju QML.
                                 ("org.gnome.desktop.background", "picture-uri"),
                                 ("org.gnome.desktop.background", "picture-uri-dark")):
                s = vir.lookup(shema, True) if vir is not None else None
                if s is None or not s.has_key(kljuc):
                    continue
                n = Gio.Settings.new(shema)
                n.connect("changed::" + kljuc, lambda *_a: self.dogodek("videz", self.videz()))
                self._nastavitve_sistema.append(n)     # drzimo referenco, sicer signal utihne
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS lupina] tema:", e, flush=True)
        try:
            from gi.repository import Gtk
            nastavitve = Gtk.Settings.get_default()
            if nastavitve is not None:
                # Zmanjsano gibanje vklopljeno med delom: namizje QML takoj brez animacij (kot strani WebKit).
                nastavitve.connect("notify::gtk-enable-animations", lambda *_a: self.dogodek("videz", self.videz()))
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS lupina] animacije:", e, flush=True)

    def _zaslon_spremenjen(self) -> None:
        """Locljivost ali zaslon se je spremenil: namizje cez nov zaslon in dock Plank na novo (Plank sprememb
        locljivosti ne sledi). Isto kot _prestavi_delovno za delovno povrsino WebKit; rob docka preberemo znova,
        ko se dock ustali."""
        from PySide6.QtCore import QTimer
        self.postavi()
        # Sprememba locljivosti sprozi vec signalov zapored: dock postavimo enkrat, ko se zaslon umiri.
        if getattr(self, "_casovnik_docka", None) is None:
            self._casovnik_docka = QTimer()
            self._casovnik_docka.setSingleShot(True)
            self._casovnik_docka.setInterval(1500)
            self._casovnik_docka.timeout.connect(self._postavi_dock)
        self._casovnik_docka.start()

    def _postavi_dock(self) -> None:
        import shutil
        self.postavi()          # ko se zaslon umiri, geometrijo preberemo se enkrat (RandR posle vec sprememb zapored)
        import subprocess
        from PySide6.QtCore import QTimer
        if shutil.which("safeer-cinnamon"):
            try:
                from core import zasebni_webkit     # Plank in Cinnamon brez nasih zasebnih poti v okolju
                subprocess.Popen(["safeer-cinnamon", "--dock"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, start_new_session=True, env=zasebni_webkit.okolje_za_zunanje())
            except OSError as e:
                print("[SafeerOS lupina] dock:", e, flush=True)
        if hasattr(self, "_dock_rob"):
            del self._dock_rob
        QTimer.singleShot(4000, self._robovi)

    def dogodek(self, vrsta: str, podatki: Any = None) -> None:
        self.pogled.qml_dogodek(vrsta, podatki)

    # ------------------------------------------------------------------ polozaj: pod vsemi okni
    def postavi(self) -> None:
        from PySide6.QtGui import QGuiApplication
        if self.v_oknu:
            return
        zaslon = QGuiApplication.primaryScreen()
        if zaslon is None:
            return
        self._spremljaj_zaslon(zaslon)
        self.okno.setGeometry(zaslon.geometry())
        self._robovi()

    def _spremljaj_zaslon(self, zaslon) -> None:
        """Signale geometrije poveze na trenutni primarni zaslon (enkrat na zaslon); ob zamenjavi zaslona na novega."""
        if zaslon is None or getattr(self, "_spremljan_zaslon", None) is zaslon:
            return
        self._spremljan_zaslon = zaslon
        zaslon.geometryChanged.connect(lambda *_: self._zaslon_spremenjen() if self._spremljan_zaslon is zaslon else None)
        zaslon.availableGeometryChanged.connect(lambda *_: self._robovi() if self._spremljan_zaslon is zaslon else None)

    def _robovi(self) -> None:
        """Pult Linux Minta (in drugi pulti z rezervacijo prostora) prekriva namizje, ki je cez ves zaslon: vsebina se
        umakne za njihov prostor (delovno obmocje). Lastnik 14. 10. 2026: pasica Minta je prekrivala iskanje."""
        from PySide6.QtGui import QGuiApplication
        koren = self.okno.rootObject() if hasattr(self.okno, "rootObject") else None
        if koren is None:
            return
        z = QGuiApplication.primaryScreen()
        robovi = robovi_delovnega_obmocja(z.geometry(), z.availableGeometry())
        if not hasattr(self, "_dock_rob"):
            try:
                from core import os_dock
                self._dock_rob = os_dock.rob_docka()
            except Exception:  # noqa: BLE001
                self._dock_rob = ("", 0)
        stran, piksli = self._dock_rob
        kljuc = {"left": "robLevo", "right": "robDesno", "top": "robZgoraj", "bottom": "robSpodaj"}.get(stran)
        if kljuc:
            robovi[kljuc] = max(robovi[kljuc], piksli)
        for ime, vrednost in robovi.items():
            koren.setProperty(ime, vrednost)

    def pokazi(self) -> None:
        if self.v_oknu:
            self._pokazi_okno()
            return
        self.okno.create()
        self._x11_namizje(int(self.okno.winId()))
        self.postavi()
        self.okno.show()

    def _pokazi_okno(self) -> None:
        """Okno aplikacije: 90 % delovnega obmocja (najvec 1440 x 900, kot staro glavno okno), na sredini."""
        from PySide6.QtCore import QSize
        zaslon = zaslon_za_okno()
        g = zaslon.availableGeometry()
        sirina, visina = velikost_okna(g.width(), g.height())
        self.okno.setMinimumSize(QSize(*najmanjsa_velikost(g.width(), g.height())))
        self.okno.resize(sirina, visina)
        if nativno_x11():
            # Vec monitorjev: okno na monitorju s kazalcem (zaslon_za_okno). Wayland mesta odjemalcu ne dovoli -
            # okno postavi sestavljalnik sam (GNOME: monitor s kazalcem/fokusom).
            self.okno.setScreen(zaslon)
            self.okno.setPosition(g.x() + (g.width() - sirina) // 2, g.y() + (g.height() - visina) // 2)
        self.okno.create()
        try:
            from core import x11
            p = x11.povezava() if nativno_x11() else None
            if p is not None and int(self.okno.winId()):
                p.nastavi_razred(int(self.okno.winId()), "safeer-os", "Safeer OS")   # skupina v pultu, StartupWMClass
                p.poslji()
        except Exception as e:  # noqa: BLE001 - Wayland: Qt da razred iz setDesktopFileName
            print("[SafeerOS lupina] X11:", e, flush=True)
        self.okno.show()

    def _vidnost(self, vidno: bool) -> None:
        if vidno:
            self._prikazano = True
        elif self._prikazano and self._ob_koncu:
            self._ob_koncu()

    def dvigni(self) -> None:
        """Ponovni zagon aplikacije iz menija: obstojece okno spredaj (ne drugega), tudi ce je pomanjsano."""
        from PySide6.QtCore import Qt
        if self.okno.windowStates() & Qt.WindowState.WindowMinimized:
            self.okno.showNormal()
        self.okno.show()
        self.okno.raise_()
        self.okno.requestActivate()

    def _x11_namizje(self, xid: int) -> None:
        """_NET_WM_WINDOW_TYPE_DESKTOP pred prikazom: upravitelj oken ga ne pokaze v pultu in ga drzi spodaj."""
        try:
            from core import x11
            p = x11.povezava() if nativno_x11() else None
            if p is None or not xid:
                return
            p.nastavi_stevila(xid, "_NET_WM_WINDOW_TYPE", p.atom("ATOM"), [p.atom("_NET_WM_WINDOW_TYPE_DESKTOP")])
            p.nastavi_razred(xid, "safeer-cinnamon", "Safeer Cinnamon")
            p.poslji()
        except Exception as e:  # noqa: BLE001 - Wayland ali brez X: Qt zastavica WindowStaysOnBottomHint ostane
            print("[SafeerOS lupina] X11:", e, flush=True)

    def zapri(self) -> None:
        self.okno.close()


class Kuverta:
    """Kuverta s stevilom neprebranih v pultu (QSystemTrayIcon - StatusNotifierItem, ki ga Cinnamon pokaze prek
    xapp-sn-watcherja). Nadomesca XApp.StatusIcon, ki ga v procesu GTK4 ni mogoce naloziti."""

    def __init__(self, ob_kliku: Callable[[], None]) -> None:
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QSystemTrayIcon
        self._QIcon = QIcon
        self._ikona = QSystemTrayIcon()
        self._ikona.activated.connect(lambda razlog: ob_kliku() if razlog in (
            QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick) else None)

    def nastavi(self, pot_png: str, opis: str) -> None:
        self._ikona.setIcon(self._QIcon(pot_png))
        self._ikona.setToolTip(opis)
        self._ikona.show()

    def zapri(self) -> None:
        """Izklop Sporocil: ikona izgine iz pulta (enako kot pladenj_sni.Kuverta.zapri)."""
        self._ikona.hide()
