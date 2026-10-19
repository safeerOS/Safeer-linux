"""Varuh docka (safeer-cinnamon --dock-ozivi): sesuti Plank zazene znova - najvec 3-krat v 10 minutah; dock, ki ga
je uporabnik zaprl sam (izhod 0), ostane zaprt.

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


def _izhod(cfg, koda):
    (cfg / "safeer-cinnamon" / "plank-izhod").write_text(f"{koda}\n")


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


def test_sesut_plank_zazene_znova(tmp_path):
    env, cfg, zapis = _okolje(tmp_path)
    _vklopi(cfg)
    _izhod(cfg, 139)   # SIGSEGV
    _ozivi(env)
    assert _zagoni(zapis) == 1


def test_uporabnik_zaprl_ostane_zaprt(tmp_path):
    """Lastnik, 17. 10. 2026: »ce uporabnik namerno zapre dock, mora ostati zaprt - nic ne vsiljujemo«."""
    env, cfg, zapis = _okolje(tmp_path)
    _vklopi(cfg)
    _izhod(cfg, 0)
    _ozivi(env)
    assert _zagoni(zapis) == 0


def test_neznan_izhod_ne_vsiljuje(tmp_path):
    env, cfg, zapis = _okolje(tmp_path)
    _vklopi(cfg)
    _ozivi(env)
    assert _zagoni(zapis) == 0


def test_ovoj_zapise_izhodno_kodo(tmp_path):
    env, cfg, zapis = _okolje(tmp_path)
    subprocess.run(["bash", SKRIPTA, "--plank"], env=env, check=True, timeout=30)
    izhod = cfg / "safeer-cinnamon" / "plank-izhod"
    for _ in range(50):
        if izhod.exists():
            break
        time.sleep(0.05)
    assert izhod.read_text().strip() == "0"   # lazni plank konca normalno = kot uporabnikov Quit


def test_najvec_trikrat_v_desetih_minutah(tmp_path):
    env, cfg, zapis = _okolje(tmp_path)
    _vklopi(cfg)
    for _ in range(5):
        time.sleep(0.3)        # ovoj prejsnjega laznega Planka zapise svojo kodo
        _izhod(cfg, 139)
        _ozivi(env)
    assert _zagoni(zapis) == 3


def test_stari_zagoni_ne_stejejo(tmp_path):
    env, cfg, zapis = _okolje(tmp_path)
    _vklopi(cfg)
    staro = int(time.time()) - 3600
    (cfg / "safeer-cinnamon" / "dock-ozivljen").write_text(f"{staro}\n{staro}\n{staro}\n")
    _izhod(cfg, 139)
    _ozivi(env)
    assert _zagoni(zapis) == 1


def test_plank_tece_nic(tmp_path):
    env, cfg, zapis = _okolje(tmp_path, plank_tece=True)
    _vklopi(cfg)
    _izhod(cfg, 139)
    _ozivi(env)
    assert _zagoni(zapis) == 0


def test_dock_izklopljen_nic(tmp_path):
    env, cfg, zapis = _okolje(tmp_path)
    (cfg / "safeer-cinnamon" / "vklopljeno").write_text("")   # Safeer Cinnamon vklopljen, dock ne
    _izhod(cfg, 139)
    _ozivi(env)
    assert _zagoni(zapis) == 0


def test_safeer_os_klice_varuha():
    with open(os.path.join(KOREN, "safeer_os.py"), encoding="utf-8") as f:
        koda = f.read()
    assert '"safeer-cinnamon", "--dock-ozivi"' in koda
    # v _ob_namizju (vsaka delovna povrsina, tudi QML), ne v _preveri_robove (samo WebKit)
    ob_namizju = koda.split("def _ob_namizju", 1)[1].split("\n    def ", 1)[0]
    assert "self._varuh_docka()" in ob_namizju


def test_safeer_os_brez_podprocesa_ko_dock_ni_vklopljen_ali_plank_tece(tmp_path, monkeypatch):
    """19. 10. 2026: varuh docka v Safeer OS je vsakih 30 s zagnal skripto bash (1300 vrstic) s pgrep, tudi ko dock ni
    vklopljen ali Plank tece. Zdaj isti pogoj najprej preveri brez podprocesa (os_dock.dock_vklopljen, plank_tece)."""
    import sys
    sys.path.insert(0, KOREN)
    from core import en_proces, os_dock
    cfg = tmp_path / "cfg"
    (cfg / "safeer-cinnamon").mkdir(parents=True)
    (cfg / "autostart").mkdir(parents=True)
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    monkeypatch.setattr(en_proces, "mapa_nastavitev_racunalnika", lambda: str(cfg))
    assert not os_dock.dock_vklopljen()
    _vklopi(cfg)
    assert os_dock.dock_vklopljen()
    # Plank: zadnji znani PID se preveri v /proc (comm), pregled /proc samo, ce ga ni vec.
    pregledi = []
    monkeypatch.setattr(os_dock, "_plank_pid", lambda: (pregledi.append(1), None)[1])
    monkeypatch.setitem(os_dock._zadnji_plank, "pid", 0)
    assert not os_dock.plank_tece()
    assert pregledi == [1]
    jaz = os.getpid()
    pot = tmp_path / "comm"
    pot.write_text("plank\n")
    resnicni_open = open

    def lazni_open(ime, *a, **k):
        return resnicni_open(pot if ime == "/proc/%d/comm" % jaz else ime, *a, **k)
    monkeypatch.setitem(os_dock._zadnji_plank, "pid", jaz)
    monkeypatch.setattr("builtins.open", lazni_open)
    assert os_dock.plank_tece()
    assert pregledi == [1]                       # brez novega pregleda /proc
    monkeypatch.setattr("builtins.open", resnicni_open)
    # V Flatpaku procesov racunalnika ne vidimo: odloci safeer-cinnamon (kot prej).
    monkeypatch.setenv("FLATPAK_ID", "io.github.memelandfaner.SafeerOS")
    assert not os_dock.plank_tece()
