"""»Odpri z ...« za Datoteke: programi, ki znajo odpreti datoteko, zagon z izbranim in privzeti program.

Vir resnice je namizje samo: `gio info` pove vrsto vsebine, `gio mime VRSTA` privzeti program in programe, ki so se
za to vrsto prijavili (isti seznam kot v Nemu), `gio mime VRSTA PROGRAM` nastavi privzetega (v
~/.config/mimeapps.list), `gio launch VNOS DATOTEKE` zazene program tako, kot ga zazene meni. Safeer OS nima svojega
seznama: kar uporabnik nastavi tu, velja v vsem namizju, in obratno. Iste klice GIO (g_app_info_*, standard::content-type)
naredimo v tem procesu (paket .deb, izvorna koda) - brez dveh podprocesov gio ob vsakem meniju »Odpri z« (meritev
19. 10. 2026 v commitu); ukaz gio ostane rezerva ter pot v Flatpaku in AppImage (zasebni_webkit.gio_v_procesu).

Stran lahko izbere samo program iz menija (vnos .desktop, ki ga meni kaze) in samo obstojece krajevne datoteke; ukaza
ali poti do programa ne poda nikoli.
"""

from __future__ import annotations

import mimetypes
import os
import re
import shutil
import subprocess
from typing import Callable, List, Optional, Tuple

from core import link_programi, os_programi, zasebni_webkit

NAJVEC_PROGRAMOV = 24
NAJVEC_VSEH = 300
NAJVEC_DATOTEK = 200
_POLJE_DATOTEKE = re.compile(r"%[fFuU]")
_OZNAKA = re.compile(r"^[A-Za-z0-9._+@-]{1,180}\.desktop$")
_VRSTA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]{0,126}$")


def _gio(argumenti: List[str], cas: float = 6.0) -> Tuple[int, str]:
    if shutil.which("gio") is None:
        return 127, ""
    okolje = dict(os.environ, LC_ALL="C", LANGUAGE="C")      # izpis razclenjujemo: vedno v anglescini
    try:
        r = subprocess.run(["gio"] + list(argumenti), capture_output=True, text=True, timeout=cas, env=okolje)
        return r.returncode, r.stdout
    except Exception:
        return 1, ""


def _vrsta_v_procesu(pot: str) -> Optional[str]:
    """standard::content-type, kot ga pove `gio info` - iz tega procesa (zasebni_webkit.gio_v_procesu). None: tu ne gre
    (Flatpak, AppImage, napaka) - klicatelj vprasa ukaz gio."""
    Gio = zasebni_webkit.gio_v_procesu()
    if Gio is None:
        return None
    try:
        return Gio.File.new_for_path(pot).query_info("standard::content-type", Gio.FileQueryInfoFlags.NONE,
                                                      None).get_content_type() or ""
    except Exception:  # noqa: BLE001 - GLib.Error: ukaz gio kot rezerva
        return None


def programi_v_procesu(vrsta: str) -> Optional[Tuple[str, List[str]]]:
    """Isto kot `gio mime VRSTA` (privzeti program, priporoceni, nato vsi prijavljeni - g_app_info_get_default_for_type,
    get_recommended_for_type, get_all_for_type) brez podprocesa. Namizni mimeapps.list (XDG_CURRENT_DESKTOP, npr.
    x-cinnamon-mimeapps.list) in programi, ki jih ni vec, so obravnavani kot pri ukazu gio - isti GIO. None: tu ne gre."""
    Gio = zasebni_webkit.gio_v_procesu()
    if Gio is None:
        return None
    try:
        privzeti = Gio.AppInfo.get_default_for_type(vrsta, False)
        vsi = list(Gio.AppInfo.get_recommended_for_type(vrsta)) + list(Gio.AppInfo.get_all_for_type(vrsta))
    except Exception:  # noqa: BLE001
        return None
    oznaka = (privzeti.get_id() or "") if privzeti is not None else ""
    oznaka = oznaka if _OZNAKA.match(oznaka) else ""
    vrstni: List[str] = [oznaka] if oznaka else []
    for app in vsi:
        ime = app.get_id() or ""
        if _OZNAKA.match(ime) and ime not in vrstni:
            vrstni.append(ime)
    return oznaka, vrstni


def nastavi_v_procesu(vrsta: str, oznaka: str) -> Optional[bool]:
    """Kot `gio mime VRSTA PROGRAM` (g_app_info_set_as_default_for_type, ~/.config/mimeapps.list). None: tu ne gre."""
    Gio = zasebni_webkit.gio_v_procesu()
    if Gio is None:
        return None
    try:
        app = Gio.DesktopAppInfo.new(oznaka)
        return bool(app is not None and app.set_as_default_for_type(vrsta))
    except Exception:  # noqa: BLE001
        return None


def _pot(pot) -> str:
    return os.path.abspath(os.path.expanduser(str(pot or "")))


def vrsta_vsebine(pot: str, gio: Callable = _gio) -> str:
    """Vrsta MIME, kot jo doloci namizje (po vsebini in imenu); '' ce je ni mogoce dolociti."""
    if os.path.isdir(pot):
        return "inode/directory"
    gio_vrsta = _vrsta_v_procesu(pot) if gio is _gio else None
    if gio_vrsta is None:
        koda, izpis = gio(["info", "-a", "standard::content-type", pot])
        m = re.search(r"standard::content-type:\s*(\S+)", izpis) if koda == 0 else None
        gio_vrsta = m.group(1) if m else ""
    for vrsta in (gio_vrsta, mimetypes.guess_type(pot)[0] or ""):      # brez gio: po koncnici
        if _VRSTA.match(vrsta):
            return vrsta
    return ""


def razcleni_mime(izpis: str) -> Tuple[str, List[str]]:
    """Iz izpisa `gio mime VRSTA`: (privzeti program, vsi programi - privzeti, priporoceni, nato drugi prijavljeni)."""
    privzeti = ""
    skupine = {"recommended": [], "registered": []}
    trenutna = ""
    for v in izpis.splitlines():
        if v[:1] in ("\t", " "):
            ime = v.strip()
            if trenutna and _OZNAKA.match(ime) and ime not in skupine[trenutna]:
                skupine[trenutna].append(ime)
            continue
        nizka = v.lower()
        trenutna = ""
        ime = v.rsplit(":", 1)[-1].strip() if ":" in v else ""
        if nizka.startswith("default application") or (ime.endswith(".desktop") and not privzeti):
            privzeti = ime if _OZNAKA.match(ime) else ""
        elif nizka.startswith("recommended applications"):
            trenutna = "recommended"
        elif nizka.startswith("registered applications"):
            trenutna = "registered"
        elif v.rstrip().endswith(":"):
            # Izpis v jeziku racunalnika (Flatpak: gio tece na gostitelju prek flatpak-spawn, ki LC_ALL ne prenese -
            # testni PC 14. 10. 2026: »Vpisani programi:«). Vrstni red gio je vedno: vpisani, nato priporoceni.
            trenutna = "registered" if not skupine["registered"] else "recommended"
    vrstni: List[str] = []
    for ime in ([privzeti] if privzeti else []) + skupine["recommended"] + skupine["registered"]:
        if ime not in vrstni:
            vrstni.append(ime)
    return privzeti, vrstni


def _programi_vrste(vrsta: str, gio: Callable) -> Tuple[str, List[str]]:
    """(privzeti, vsi) za vrsto: v procesu, sicer iz izpisa `gio mime VRSTA` (Flatpak, AppImage, preizkusi z laznim gio)."""
    v_procesu = programi_v_procesu(vrsta) if gio is _gio else None
    if v_procesu is not None:
        return v_procesu
    koda, izpis = gio(["mime", vrsta])
    return razcleni_mime(izpis) if koda == 0 else ("", [])


def program_za_shemo(shema: str, gio: Callable = _gio, mape: Optional[List[str]] = None,
                     namizja: Optional[List[str]] = None) -> Optional[dict]:
    """Privzeti program za povezave sheme (mailto, magnet ...): {"oznaka", "ime"} ali None, ce ga ni. V Flatpaku gio
    tece na gostitelju, zato Splet pozna program racunalnika (prej »zunanji program«; 14. 10. 2026)."""
    if not re.match(r"^[a-z][a-z0-9+.-]{0,31}$", str(shema or "")):
        return None
    privzeti, vsi = _programi_vrste("x-scheme-handler/" + shema, gio)
    for oznaka in ([privzeti] if privzeti else []) + vsi:
        vnos = _vnos(oznaka, mape, namizja)
        if vnos:
            return {"oznaka": oznaka, "ime": vnos.get("ime") or oznaka}
    return None


def pot_vnosa(oznaka: str, mape: Optional[List[str]] = None) -> Optional[str]:
    """Datoteka .desktop za oznako programa (ime vnosa brez poti) ali None."""
    oznaka = str(oznaka or "")
    if not _OZNAKA.match(oznaka):
        return None
    for mapa in (mape if mape is not None else link_programi._mape_vnosov()):
        pot = os.path.join(mapa, oznaka)
        if os.path.isfile(pot):
            return pot
    return None


def _vnos(oznaka: str, mape: Optional[List[str]], namizja: Optional[List[str]]) -> Optional[dict]:
    """Vnos, kot ga kaze meni (skriti, terminalski in tisti brez programa odpadejo), ali None."""
    pot = pot_vnosa(oznaka, mape)
    return os_programi.preberi_vnos(pot, namizja) if pot else None


def sprejme_datoteke(pot_vnosa_: str) -> bool:
    """Ali program zna sprejeti datoteko: ukaz `Exec` glavnega dela vnosa ima polje %f, %F, %u ali %U."""
    try:
        with open(pot_vnosa_, encoding="utf-8", errors="replace") as f:
            besedilo = f.read(65536)
    except OSError:
        return False
    glavni = besedilo.split("[Desktop Entry]", 1)[-1].split("\n[", 1)[0]
    m = re.search(r"^Exec\s*=\s*(.+)$", glavni, re.M)
    return bool(m and _POLJE_DATOTEKE.search(m.group(1)))


def vsi_programi(mape: Optional[List[str]] = None, namizja: Optional[List[str]] = None) -> List[dict]:
    """Vsi programi iz menija, ki znajo sprejeti datoteko - za »Drug program ...«. Nastavitve namizja in podobni
    vnosi, ki datoteke ne morejo odpreti, odpadejo."""
    najdeni = {}
    videni = set()
    for mapa in (mape if mape is not None else link_programi._mape_vnosov()):
        try:
            imena = sorted(os.listdir(mapa))
        except OSError:
            continue
        for ime in imena:
            if ime in najdeni or not _OZNAKA.match(ime):
                continue
            pot = os.path.join(mapa, ime)
            v = os_programi.preberi_vnos(pot, namizja)
            if v is None or not sprejme_datoteke(pot):
                continue
            # Isti program dvakrat (sistemski in Flatpak) je na seznamu samo zmeda: prvi obvelja, kot v meniju.
            kljuc = (v["ime"].lower(), v["ikona"])
            if kljuc in videni:
                continue
            videni.add(kljuc)
            najdeni[ime] = {"id": ime, "ime": v["ime"], "ikona": v["ikona"]}
    return sorted(najdeni.values(), key=lambda p: (p["ime"].lower(), p["id"]))[:NAJVEC_VSEH]


def programi_za(pot: str, mape: Optional[List[str]] = None, namizja: Optional[List[str]] = None,
                gio: Callable = _gio) -> dict:
    """Programi, ki so se prijavili za vrsto te datoteke; privzeti je prvi in oznacen."""
    pot = _pot(pot)
    if not os.path.exists(pot):
        return {"ok": False, "koda": "ni"}
    vrsta = vrsta_vsebine(pot, gio)
    privzeti, oznake = _programi_vrste(vrsta, gio) if vrsta else ("", [])
    programi = []
    for oznaka in oznake:
        v = _vnos(oznaka, mape, namizja)
        if v is None:
            continue
        programi.append({"id": oznaka, "ime": v["ime"], "ikona": v["ikona"], "privzet": oznaka == privzeti})
        if len(programi) >= NAJVEC_PROGRAMOV:
            break
    return {"ok": True, "vrsta": vrsta, "programi": programi}


def nastavi_privzetega(vrsta: str, oznaka: str, gio: Callable = _gio) -> bool:
    """Program postane privzeti za to vrsto datotek - v vsem namizju (mimeapps.list)."""
    if not _VRSTA.match(str(vrsta or "")) or not _OZNAKA.match(str(oznaka or "")):
        return False
    v_procesu = nastavi_v_procesu(vrsta, oznaka) if gio is _gio else None
    if v_procesu is not None:
        return v_procesu
    return gio(["mime", vrsta, oznaka])[0] == 0


def odpri_z(poti, oznaka: str, vedno: bool = False, zaganjalnik: Optional[Callable] = None,
            mape: Optional[List[str]] = None, namizja: Optional[List[str]] = None, gio: Callable = _gio) -> dict:
    """Odpre datoteke z izbranim programom; z `vedno` ga nastavi se za privzetega za vrsto prve datoteke.

    `zaganjalnik(pot_vnosa, datoteke) -> bool` zazene program iz Safeer OS (z okoljem namizja: novo okno pride v
    ospredje); brez njega ali ce ne uspe, `gio launch`."""
    datoteke = []
    for p in poti if isinstance(poti, (list, tuple)) else [poti]:
        p = _pot(p)
        if os.path.exists(p) and p not in datoteke:
            datoteke.append(p)
    datoteke = datoteke[:NAJVEC_DATOTEK]
    if not datoteke:
        return {"ok": False, "koda": "ni"}
    vnos = pot_vnosa(oznaka, mape)
    if vnos is None or os_programi.preberi_vnos(vnos, namizja) is None:
        return {"ok": False, "koda": "program"}
    ok = False
    if zaganjalnik is not None:
        try:
            ok = bool(zaganjalnik(vnos, datoteke))
        except Exception:
            ok = False
    if not ok and shutil.which("gio") is not None:
        ukaz = ["gio", "launch", vnos] + datoteke
        from core import varuh_procesov
        try:
            pid = varuh_procesov.zazeni_program(ukaz, zasebni_webkit.okolje_za_zunanje())
            if pid:
                ok = True
        except Exception:
            pass
        if not ok:
            try:
                subprocess.Popen(ukaz, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True, env=zasebni_webkit.okolje_za_zunanje())
                ok = True
            except Exception:
                ok = False
    if not ok:
        return {"ok": False, "koda": "zagon"}
    privzet = False
    if vedno:
        vrsta = vrsta_vsebine(datoteke[0], gio)
        privzet = bool(vrsta) and nastavi_privzetega(vrsta, oznaka, gio)
    return {"ok": True, "privzet": privzet}
