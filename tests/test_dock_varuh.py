"""Varuh docka (safeer-cinnamon --dock-ozivi): Plank, ki ne tece, zazene znova - najvec 3-krat v 10 minutah.

Lastnik, 17. 10. 2026: stranski dock je izginil (Plank se ni vrnil) - »uporabnik ne zeli ostati brez docka«.
Preizkus tece z laznimi ukazi (plank, pgrep, xrandr, dconf, gsettings) v zacasni domaci mapi; resnicnega docka ne
zaganja.
"""
import os
import stat
import subprocess
import time

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKRIPTA = os.path.join(KOREN, "packaging", "tema-cinnamon", "safeer-cinnamon")


def _lazni(mapa, ime, vsebina):
    pot = mapa / ime
    pot.write_text("#!/bin/bash\n" + vsebina + "\n")
    pot.chmod(pot.stat().st_mode | stat.S_IEXEC)


def _okolje(tmp_path, plank_tece=False):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    zapis = tmp_path / "zagoni.txt"
    _lazni(bin_, "plank", f'echo zagon >> "{zapis}"')
    _lazni(bin_, "pgrep", "exit 0" if plank_tece else "exit 1")
    _lazni(bin_, "pkill", "exit 1")
    for ime in ("xrandr", "dconf", "gsettings", "xev"):
        _lazni(bin_, ime, "exit 0")
    dom = tmp_path / "dom"
    (dom / ".config" / "safeer-cinnamon").mkdir(parents=True)
    (dom / ".config" / "autostart").mkdir(parents=True)
    env = dict(os.environ, HOME=str(dom), XDG_CONFIG_HOME=str(dom / ".config"),
               XDG_DATA_HOME=str(dom / ".local" / "share"), PATH=f"{bin_}:/usr/bin:/bin",
               SAFEER_CINNAMON_KOREN=str(tmp_path / "koren"))
    return env, dom / ".config", zapis


def _vklopi(cfg):
    (cfg / "safeer-cinnamon" / "vklopljeno").write_text("")
    (cfg / "autostart" / "safeer-cinnamon-dock.desktop").write_text("[Desktop Entry]\n")


def _ozivi(env):
    subprocess.run(["bash", SKRIPTA, "--dock-ozivi"], env=env, check=True, timeout=30,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _zagoni(zapis):
    # plank tece v ozadju (setsid): pocakamo, da zapise
    for _ in range(50):
        if zapis.exists():
            break
        time.sleep(0.05)
    time.sleep(0.2)
    return zapis.read_text().count("zagon") if zapis.exists() else 0


def test_plank_ne_tece_zazene_znova(tmp_path):
    env, cfg, zapis = _okolje(tmp_path)
    _vklopi(cfg)
    _ozivi(env)
    assert _zagoni(zapis) == 1


def test_najvec_trikrat_v_desetih_minutah(tmp_path):
    env, cfg, zapis = _okolje(tmp_path)
    _vklopi(cfg)
    for _ in range(5):
        _ozivi(env)
    assert _zagoni(zapis) == 3


def test_stari_zagoni_ne_stejejo(tmp_path):
    env, cfg, zapis = _okolje(tmp_path)
    _vklopi(cfg)
    staro = int(time.time()) - 3600
    (cfg / "safeer-cinnamon" / "dock-ozivljen").write_text(f"{staro}\n{staro}\n{staro}\n")
    _ozivi(env)
    assert _zagoni(zapis) == 1


def test_plank_tece_nic(tmp_path):
    env, cfg, zapis = _okolje(tmp_path, plank_tece=True)
    _vklopi(cfg)
    _ozivi(env)
    assert _zagoni(zapis) == 0


def test_dock_izklopljen_nic(tmp_path):
    env, cfg, zapis = _okolje(tmp_path)
    (cfg / "safeer-cinnamon" / "vklopljeno").write_text("")   # Safeer Cinnamon vklopljen, dock ne
    _ozivi(env)
    assert _zagoni(zapis) == 0


def test_safeer_os_klice_varuha():
    with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
        koda = f.read()
    assert '"safeer-cinnamon", "--dock-ozivi"' in koda
    assert "self._varuh_docka()" in koda
