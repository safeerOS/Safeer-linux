"""Namizni programi kot kanali Sporocil (Viber, Signal Desktop; lastnik, 15. 10. 2026): ali je program namescen, kako
ga zazenemo in po cem prepoznamo njegovo okno. Splosno - vnos v katalogu (core/spletni_klepeti.py) so le podatki:
imena zaganjalnikov (.desktop), ukaz, vzorec za AppImage, razredi okna (WM_CLASS) in argumenti za zagon v X11.

Zazna vse tri oblike namestitve: paket (.desktop v mapah menija in izvrsljiva datoteka na poti), Flatpak (izvozi
/var/lib/flatpak in ~/.local/share/flatpak) in AppImage (~/Applications, ~/Prejemi oz. mapa prenosov, ~/Downloads ali
pot, ki jo je uporabnik izbral sam). V Flatpaku Safeer OS se program zazene na racunalniku (flatpak-spawn --host).
GTK-ja modul ne potrebuje.
"""
from __future__ import annotations

import configparser
import fnmatch
import os
import shlex
import shutil
import subprocess
from typing import List, Optional

from core import gostitelj, zasebni_webkit

#: Mape, v katerih uporabniki navadno hranijo AppImage (poleg mape prenosov iz XDG).
MAPE_APPIMAGE = ("~/Applications", "~/Prejemi", "~/Downloads", "~/Prenosi", "~/.local/bin", "~/bin")


def _mape_vnosov() -> List[str]:
    from core import link_programi
    return link_programi._mape_vnosov()


def _beri_vnos(pot: str) -> Optional[dict]:
    b = configparser.RawConfigParser(interpolation=None, strict=False)
    b.optionxform = str
    try:
        with open(pot, encoding="utf-8", errors="replace") as f:
            b.read_file(f)
        v = b["Desktop Entry"]
    except Exception:  # noqa: BLE001 - pokvarjen ali neberljiv vnos
        return None
    return {"ukaz": ukaz_iz_exec(v.get("Exec", "") or ""), "razred": (v.get("StartupWMClass", "") or "").strip(),
            "ime": (v.get("Name", "") or "").strip()}


#: Kode polj v Exec (Desktop Entry Specification): datoteke, URL-ji, ikona, ime ... - ob zagonu brez datotek odpadejo.
_KODE_POLJ = set("fFuUdDnNickvm")


def ukaz_iz_exec(exec_: str) -> list:
    """Exec iz .desktop -> seznam argumentov brez kod polj (%f, %U, %i ...). Argument, ki je samo koda, odpade; koda
    sredi argumenta (»--file=%f«) se odstrani; »%%« je znak %. Neveljavni narekovaji ali prvi argument, ki ni program
    (prazen ali z »-« na zacetku - flatpak-spawn bi ga bral kot svojo moznost), pomenijo: vnosa ne uporabimo."""
    try:
        deli = shlex.split(str(exec_ or ""))
    except ValueError:
        return []
    izid = []
    for d in deli:
        if len(d) == 2 and d[0] == "%" and d[1] in _KODE_POLJ:
            continue
        nov, i = [], 0
        while i < len(d):
            if d[i] == "%" and i + 1 < len(d):
                if d[i + 1] == "%":
                    nov.append("%")
                elif d[i + 1] not in _KODE_POLJ:
                    nov.append(d[i:i + 2])
                i += 2
                continue
            nov.append(d[i])
            i += 1
        d = "".join(nov)
        if d:
            izid.append(d)
    if not izid or izid[0].startswith("-"):
        return []
    return izid


def _mape_appimage() -> List[str]:
    mape = [os.path.expanduser(m) for m in MAPE_APPIMAGE]
    try:
        prenosi = subprocess.run(["xdg-user-dir", "DOWNLOAD"], capture_output=True, text=True, timeout=2).stdout.strip()
        if prenosi and prenosi not in mape:
            mape.append(prenosi)
    except (OSError, subprocess.SubprocessError):
        pass
    return mape


def je_izvrsljiva(pot: str) -> bool:
    """Navadna izvrsljiva datoteka z ABSOLUTNO potjo (program, ki ga je izbral uporabnik, ali AppImage). Relativna pot
    bi bila odvisna od trenutne mape, »-« na zacetku bi ukaz bral kot moznost."""
    return (bool(pot) and isinstance(pot, str) and os.path.isabs(pot) and os.path.isfile(pot)
            and os.access(pot, os.X_OK))


def najdi(program: dict, izbrana_pot: str = "", mape_vnosov: Optional[List[str]] = None,
          mape_appimage: Optional[List[str]] = None) -> Optional[dict]:
    """Namestitev programa ali None. Vrne {"oblika": "pot"|"vnos"|"ukaz"|"appimage", "ukaz": [...], "razredi": [...]}.
    Prednost: pot, ki jo je izbral uporabnik; zaganjalnik .desktop (paket ali Flatpak); ukaz na poti; AppImage."""
    razredi = [r for r in (program.get("razredi") or []) if r]
    argumenti = list(program.get("argumenti") or [])
    if izbrana_pot and je_izvrsljiva(izbrana_pot):
        return {"oblika": "pot", "ukaz": [izbrana_pot] + argumenti, "razredi": razredi}
    imena = set(program.get("vnosi") or [])
    for mapa in (mape_vnosov if mape_vnosov is not None else _mape_vnosov()):
        for ime in sorted(imena):
            pot = os.path.join(mapa, ime)
            if not os.path.isfile(pot):
                continue
            vnos = _beri_vnos(pot)
            if not vnos or not vnos["ukaz"]:
                continue
            r = ([vnos["razred"]] if vnos["razred"] else []) + [x for x in razredi if x != vnos["razred"]]
            return {"oblika": "vnos", "ukaz": vnos["ukaz"] + argumenti, "razredi": r, "vnos": pot}
    for ukaz in program.get("ukazi") or []:
        pot = shutil.which(ukaz)
        if pot:
            return {"oblika": "ukaz", "ukaz": [pot] + argumenti, "razredi": razredi}
    vzorci = [v.lower() for v in (program.get("appimage") or [])]
    if vzorci:
        for mapa in (mape_appimage if mape_appimage is not None else _mape_appimage()):
            try:
                imena_dat = sorted(os.listdir(mapa))
            except OSError:
                continue
            for ime in imena_dat:
                if any(fnmatch.fnmatch(ime.lower(), v) for v in vzorci) and je_izvrsljiva(os.path.join(mapa, ime)):
                    return {"oblika": "appimage", "ukaz": [os.path.join(mapa, ime)] + argumenti, "razredi": razredi}
    return None


def zazeni(najdba: dict) -> Optional[subprocess.Popen]:
    """Zazene program (v Flatpaku Safeer OS na racunalniku); None, ce ne gre. Program tece kot samostojen proces - ob
    koncu Safeer OS ga ne ustavimo (okno se vrne na namizje). Brez lupine (seznam argumentov): nic iz vnosa ali imena
    datoteke se ne razlaga kot ukaz lupine."""
    ukaz = [str(d) for d in (najdba.get("ukaz") or [])]
    if not ukaz or not ukaz[0] or ukaz[0].startswith("-") or any("\0" in d for d in ukaz):
        return None
    ukaz[0] = gostitelj.na_gostitelju(ukaz[0])
    if gostitelj.v_flatpaku():
        if not shutil.which("flatpak-spawn"):
            return None
        # Brez »--«: GOption ga pusti v argv, ce mu sledi argument z »-« (npr. --ozone-platform=x11), in flatpak-spawn
        # bi zagnal »--«. Program z »-« na zacetku je zavrnjen zgoraj, zato ga flatpak-spawn ne more brati kot moznost.
        ukaz = ["flatpak-spawn", "--host"] + gostitelj.env_zaslona() + ukaz
    else:
        from core import varuh_procesov
        try:
            pid = varuh_procesov.zazeni_program(ukaz, zasebni_webkit.okolje_za_zunanje())
            if pid:
                class _ProcesOvoj:
                    def __init__(self, p: int) -> None:
                        self.pid = p
                    def poll(self) -> Optional[int]:
                        try:
                            os.kill(self.pid, 0)
                            return None
                        except OSError:
                            return 0
                    def wait(self, timeout: Optional[float] = None) -> Optional[int]:
                        return self.poll()
                return _ProcesOvoj(pid)
        except Exception:
            pass
    try:
        return subprocess.Popen(ukaz, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                                start_new_session=True, env=zasebni_webkit.okolje_za_zunanje())
    except OSError as e:
        print("[Sporocila] zagon programa:", e, flush=True)
        return None


def _proces(pid: int) -> Optional[dict]:
    """exe, argv[0] in stars procesa iz /proc; None, ce ga ne vidimo (drug imenski prostor PID - Flatpak - ali ga ni)."""
    try:
        with open("/proc/%d/stat" % pid, "rb") as f:
            stat = f.read().decode("utf-8", "replace")
        stars = int(stat.rsplit(")", 1)[1].split()[1])
    except (OSError, ValueError, IndexError):
        return None
    try:
        exe = os.readlink("/proc/%d/exe" % pid)
    except OSError:
        exe = ""
    try:
        with open("/proc/%d/cmdline" % pid, "rb") as f:
            argv0 = f.read().split(b"\0", 1)[0].decode("utf-8", "replace")
    except OSError:
        argv0 = ""
    return {"exe": exe, "argv0": argv0, "stars": stars}


def pripada_programu(pid: int, najdba: dict, program: dict, zagnani=()) -> bool:
    """Ali okno s _NET_WM_PID `pid` res pripada programu kanala (ne drugemu programu z enakim WM_CLASS):
      * pid je proces, ki ga je zagnal Safeer, ali njegov potomec; ali
      * izvrsljiva datoteka / argv[0] procesa vsebuje ime programa (ukaz, razred okna, ime iz kataloga).
    Kar preveriti ne moremo, sprejmemo (posteno: zasebnosti ne poslabsa - X11 tujih oken ne loci): okno brez PID,
    proces v drugem imenskem prostoru PID (Safeer OS v Flatpaku, program v Flatpaku - njegov _NET_WM_PID je stevilka
    v peskovniku) ali proces, ki ga ne vidimo. Nikoli: okno nasega procesa."""
    if not pid or pid <= 0:
        return True
    if pid == os.getpid():
        return False
    ukaz = list(najdba.get("ukaz") or [])
    if ukaz and os.path.basename(ukaz[0]) in ("flatpak", "flatpak-spawn"):
        return True
    p = _proces(pid)
    if p is None:
        return True
    zagnani = {int(z) for z in zagnani if z}
    korak, trenutni, info = 0, pid, p
    while trenutni > 1 and korak < 64:
        if trenutni in zagnani:
            return True
        info = _proces(trenutni) if korak else p
        if info is None:
            break
        trenutni, korak = info["stars"], korak + 1
    imena = {os.path.basename(str(x)).casefold() for x in list(program.get("ukazi") or []) + list(najdba.get("razredi") or [])
             + list(program.get("razredi") or []) + ([ukaz[0]] if ukaz else [])}
    imena = {i for i in imena if len(i) >= 3}
    poti = (p["exe"] + "\n" + p["argv0"]).casefold()
    return any(i in poti for i in imena)


def x11_seja() -> bool:
    """Ali je vgradnja okna mogoca (namizje X11). Na Waylandu se program odpre v svojem oknu ob Sporocilih.

    Odloci core/seja_prikaza: prej je seja z WAYLAND_DISPLAY in DISPLAY brez XDG_SESSION_TYPE (sway iz konzole) veljala
    za X11 in vgradnja je tiho odpovedala."""
    from core import seja_prikaza
    return seja_prikaza.je_x11() and seja_prikaza.gdk_x11()
