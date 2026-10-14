"""Dock (Plank) iz Safeer OS: kaj je v docku, dodaj, odstrani, razvrsti.

Lastnik, 11. 10. 2026: »Uporabnik si naj lahko enostavno razvrsti prikaz programov na docku in jih tudi enostavno lahko
doda ali odstrani.« Plank sam zna vlecenje ikon, a tega uporabnik ne ve, z daljincem pa ne gre. Zato Safeer OS ponudi
isto v svojih menijih (Programi › desni klik › Dodaj v dock; Prilagodi dock › puscici gor/dol, odstrani).

Plank hrani dock v dveh delih: datoteke <ime>.dockitem v ~/.config/plank/dock1/launchers (kaj je v docku) in
dconf kljuc dock-items (vrstni red). Plank vrstni red prebere ob zagonu, zato ga po spremembi zazenemo znova - le ce
je tekel (ce dock ni vklopljen, ga ne vklapljamo).
"""
import ast
import os
import signal
import subprocess
import urllib.parse
from typing import List, Optional

PLANK_DOCK = "/net/launchpad/plank/docks/dock1/"
KONCNICA = ".dockitem"


def _v_flatpaku() -> bool:
    return bool(os.environ.get("FLATPAK_ID"))


def _gostitelj(argumenti: List[str]) -> List[str]:
    """Plank, dconf in kill tecejo na racunalniku: v Flatpaku prek flatpak-spawn --host (testni PC 14. 10. 2026: v
    peskovniku je bil dock »nenamescen« - plank in njegov dconf nista vidna, /proc kaze samo peskovnik)."""
    if not _v_flatpaku():
        return list(argumenti)
    # Kot ovoji v /app/host-bin: Plank potrebuje zaslon (pregled 14. 10.: brez tega se po ponovnem zagonu ne bi prikazal).
    return ["flatpak-spawn", "--host", "--env=DISPLAY=" + os.environ.get("DISPLAY", ""),
            "--env=WAYLAND_DISPLAY=" + os.environ.get("WAYLAND_DISPLAY", "")] + list(argumenti)


def pot_za_gostitelja(pot: str) -> str:
    """Program racunalnika je v Flatpaku viden pod /run/host; Plank na racunalniku potrebuje pravo pot."""
    return pot[len("/run/host"):] if pot.startswith("/run/host/") else pot


def mapa_launcherjev() -> str:
    # V Flatpaku XDG_CONFIG_HOME kaze v peskovnik (~/.var/app/...); Plank bere ~/.config racunalnika.
    koren = (None if _v_flatpaku() else os.environ.get("XDG_CONFIG_HOME")) or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(koren, "plank", "dock1", "launchers")


def je_namescen() -> bool:
    """Ali je dock Plank na racunalniku (tudi iz Flatpaka)."""
    import shutil
    if shutil.which("plank") or os.path.lexists("/run/host/usr/bin/plank"):
        return True
    return _plank_pid() is not None


def _dconf_beri(kljuc: str) -> str:
    try:
        r = subprocess.run(_gostitelj(["dconf", "read", PLANK_DOCK + kljuc]), capture_output=True, text=True, timeout=5)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _dconf_pisi(kljuc: str, vrednost: str) -> bool:
    try:
        return subprocess.run(_gostitelj(["dconf", "write", PLANK_DOCK + kljuc, vrednost]), capture_output=True,
                              timeout=5).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def razcleni_seznam(besedilo: str) -> List[str]:
    """GVariant seznam nizov (npr. "['a.dockitem', 'b.dockitem']" ali "@as []") v Pythonov seznam."""
    s = (besedilo or "").strip()
    if s.startswith("@as"):
        s = s[3:].strip()
    if not s:
        return []
    try:
        v = ast.literal_eval(s)
    except (ValueError, SyntaxError):
        return []
    return [str(x) for x in v if isinstance(x, str)] if isinstance(v, (list, tuple)) else []


def zapisi_seznam(imena: List[str]) -> str:
    return "[" + ", ".join("'" + i.replace("\\", "\\\\").replace("'", "\\'") + "'" for i in imena) + "]"


def _veljavno_ime(ime: str) -> bool:
    return bool(ime) and ime.endswith(KONCNICA) and "/" not in ime and ime not in (KONCNICA, "." + KONCNICA)


def launcher(pot_dockitem: str) -> str:
    """Pot .desktop datoteke, na katero kaze dockitem (Launcher=file://...); prazno, ce je ni."""
    try:
        with open(pot_dockitem, encoding="utf-8", errors="replace") as f:
            for vrstica in f:
                if vrstica.startswith("Launcher="):
                    url = vrstica.split("=", 1)[1].strip()
                    if url.startswith("file://"):
                        return urllib.parse.unquote(url[len("file://"):])
                    return ""
    except OSError:
        pass
    return ""


def elementi() -> List[dict]:
    """Programi v docku po vrsti: [{dockitem, pot, id}] (id = ime .desktop datoteke, kot ga uporablja seznam programov).
    Datoteke, ki jih ni v dock-items, Plank pokaze na koncu - tako tudi tu."""
    mapa = mapa_launcherjev()
    try:
        datoteke = sorted(f for f in os.listdir(mapa) if _veljavno_ime(f))
    except OSError:
        datoteke = []
    vrsta = [i for i in razcleni_seznam(_dconf_beri("dock-items")) if i in datoteke]
    vrsta += [f for f in datoteke if f not in vrsta]
    izhod = []
    for ime in vrsta:
        pot = launcher(os.path.join(mapa, ime))
        if pot:
            izhod.append({"dockitem": ime, "pot": pot, "id": os.path.basename(pot)})
    return izhod


def _plank_pid() -> Optional[int]:
    if _v_flatpaku():
        try:
            r = subprocess.run(_gostitelj(["pgrep", "-u", str(os.getuid()), "-x", "plank"]), capture_output=True,
                               text=True, timeout=5)
            vrstice = [v for v in r.stdout.split() if v.isdigit()]
            return int(vrstice[0]) if vrstice else None
        except (OSError, subprocess.SubprocessError, ValueError):
            return None
    for ime in os.listdir("/proc"):
        if not ime.isdigit():
            continue
        try:
            with open("/proc/%s/comm" % ime) as f:
                if f.read().strip() == "plank" and os.stat("/proc/" + ime).st_uid == os.getuid():
                    return int(ime)
        except OSError:
            continue
    return None


def osvezi() -> None:
    """Plank prebere vrstni red ob zagonu: ce tece, ga zazenemo znova (dock za trenutek izgine in se vrne)."""
    pid = _plank_pid()
    if pid is None:
        return
    try:
        if _v_flatpaku():
            subprocess.run(_gostitelj(["kill", str(pid)]), capture_output=True, timeout=5)
        else:
            os.kill(pid, signal.SIGTERM)
    except (OSError, subprocess.SubprocessError):
        return
    import time
    for _ in range(30):
        if _plank_pid() is None:
            break
        time.sleep(0.05)
    try:
        subprocess.Popen(_gostitelj(["plank"]), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError:
        pass


def _ime_za(pot_desktop: str) -> str:
    osnova = os.path.basename(pot_desktop)
    if osnova.endswith(".desktop"):
        osnova = osnova[: -len(".desktop")]
    return osnova + KONCNICA


def dodaj(pot_desktop: str, osvezi_dock=True) -> dict:
    """Doda program (pot .desktop) na konec docka. Ce je ze v docku, ne naredi nicesar."""
    if not pot_desktop or not os.path.isabs(pot_desktop) or not pot_desktop.endswith(".desktop") or not os.path.isfile(pot_desktop):
        return {"ok": False}
    for e in elementi():
        if os.path.realpath(e["pot"]) == os.path.realpath(pot_desktop) or e["id"] == os.path.basename(pot_desktop):
            return {"ok": True, "ze": True}
    mapa = mapa_launcherjev()
    os.makedirs(mapa, exist_ok=True)
    ime = _ime_za(pot_desktop)
    with open(os.path.join(mapa, ime), "w", encoding="utf-8") as f:
        f.write("[PlankDockItemPreferences]\nLauncher=file://%s\n" % urllib.parse.quote(pot_za_gostitelja(pot_desktop)))
    vrsta = [e["dockitem"] for e in elementi() if e["dockitem"] != ime] + [ime]
    _dconf_pisi("dock-items", zapisi_seznam(vrsta))
    if osvezi_dock:
        osvezi()
    return {"ok": True}


def odstrani(oznaka: str, osvezi_dock=True) -> dict:
    """Odstrani program iz docka (oznaka = ime .desktop ali .dockitem). Program sam ostane namescen."""
    ime = None
    for e in elementi():
        if oznaka in (e["dockitem"], e["id"]):
            ime = e["dockitem"]
            break
    if ime is None:
        return {"ok": False}
    try:
        os.remove(os.path.join(mapa_launcherjev(), ime))
    except OSError:
        return {"ok": False}
    _dconf_pisi("dock-items", zapisi_seznam([e["dockitem"] for e in elementi()]))
    if osvezi_dock:
        osvezi()
    return {"ok": True}


def razvrsti(vrsta: List[str], osvezi_dock=True) -> dict:
    """Nov vrstni red (seznam .dockitem ali .desktop imen). Neznana imena izpusti, manjkajoce doda na konec."""
    zdaj = elementi()
    po_imenu = {}
    for e in zdaj:
        po_imenu[e["dockitem"]] = e["dockitem"]
        po_imenu[e["id"]] = e["dockitem"]
    nova = []
    for x in vrsta or []:
        d = po_imenu.get(str(x))
        if d and d not in nova:
            nova.append(d)
    nova += [e["dockitem"] for e in zdaj if e["dockitem"] not in nova]
    if nova == [e["dockitem"] for e in zdaj]:
        return {"ok": True}
    ok = _dconf_pisi("dock-items", zapisi_seznam(nova))
    if ok and osvezi_dock:
        osvezi()
    return {"ok": ok}
