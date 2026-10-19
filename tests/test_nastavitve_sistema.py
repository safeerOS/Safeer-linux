"""Nastavitve Safeer OS odrazajo celotne nastavitve sistema (lastnik, 19. 10. 2026): vsak modul Cinnamona, orodje Minta
in plosca Nastavitev GNOME, ki jih racunalnik RES ima - brez mrtvih gumbov; ukaz za plosco GNOME samo iz varne vrstice
Exec sistemske namizne datoteke."""
import os
import re
from unittest import mock

import pytest

from core import os_sistem

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


def _namizna(mapa, ime, exec_, imena=None):
    vrstice = ["[Desktop Entry]", "Type=Application", "Name=" + (imena or {}).get("", ime), "Exec=" + exec_]
    vrstice += ["Name[%s]=%s" % (j, v) for j, v in (imena or {}).items() if j]
    (mapa / ime).write_text("\n".join(vrstice) + "\n[Desktop Action x]\nExec=rm -rf /\n", encoding="utf-8")


def test_moduli_iz_mape_cinnamona(tmp_path):
    moduli = tmp_path / "modules"
    moduli.mkdir()
    for ime in ("cs_info.py", "cs_online_accounts.py", "cs_nightlight.py", "cs_display.py", "cs_neznan.py", "__init__.py",
                "SettingsWidgets.py"):
        (moduli / ime).write_text("")
    assert os_sistem.moduli_cinnamon((str(moduli), str(tmp_path / "ni")), ()) == {"info", "online-accounts", "nightlight", "display"}


def test_moduli_iz_namiznih_datotek_in_rezerva(tmp_path):
    prog = tmp_path / "applications"
    prog.mkdir()
    for m in ("tiling", "sound", "users"):     # cinnamon-settings-users je orodje (Uporabniki in skupine), ne modul
        (prog / ("cinnamon-settings-%s.desktop" % m)).write_text("")
    assert os_sistem.moduli_cinnamon((str(tmp_path / "ni"),), (str(prog),)) == {"tiling", "sound"}
    # Ne mape ne namiznih datotek (Flatpak brez dostopa): samo moduli vseh razlicic 5.2-6.6.
    rezerva = os_sistem.moduli_cinnamon((str(tmp_path / "ni"),), (str(tmp_path / "ni"),))
    assert rezerva == os_sistem.MODULI_VEDNO and rezerva <= os_sistem.MODULI
    assert not {"nightlight", "thunderbolt", "tiling", "online-accounts", "actions", "gestures"} & rezerva


def test_plosce_gnome_samo_varen_exec(tmp_path):
    prog = tmp_path / "applications"
    prog.mkdir()
    _namizna(prog, "gnome-wifi-panel.desktop", "gnome-control-center wifi", {"": "Wi-Fi", "sl": "Brezžično"})
    _namizna(prog, "gnome-about-panel.desktop", "gnome-control-center system about", {"": "About", "sl": "O sistemu"})
    _namizna(prog, "gnome-zabava-panel.desktop", "/usr/bin/gnome-control-center zabava", {"": "Fun", "de": "Spaß"})
    _namizna(prog, "gnome-zlo-panel.desktop", "gnome-control-center zlo; rm -rf ~")
    _namizna(prog, "gnome-lupina-panel.desktop", "sh -c 'gnome-control-center x'")
    _namizna(prog, "gnome-drug-panel.desktop", "drug-program wifi")
    _namizna(prog, "gnome-VELIKE-panel.desktop", "gnome-control-center VELIKE")
    (prog / "gnome-prazno-panel.desktop").write_text("[Desktop Entry]\nName=x\n")
    p = os_sistem.plosce_gnome((str(prog),), "sl")
    assert sorted(p) == ["about", "wifi", "zabava"]
    assert p["about"]["ukaz"] == ["gnome-control-center", "system", "about"] and p["about"]["ime"] == "O sistemu"
    assert p["wifi"]["ukaz"] == ["gnome-control-center", "wifi"] and p["wifi"]["ime"] == "Brezžično"
    assert p["zabava"]["ime"] == "Fun", "brez prevoda angleško ime iz sistema"


def test_razpolozljivo_po_seji(tmp_path, monkeypatch):
    prog = tmp_path / "applications"
    prog.mkdir()
    _namizna(prog, "gnome-display-panel.desktop", "gnome-control-center display")
    _namizna(prog, "gnome-zabava-panel.desktop", "gnome-control-center zabava", {"": "Fun"})
    monkeypatch.setattr(os_sistem, "MAPE_PROGRAMOV", (str(prog),))
    monkeypatch.setattr(os_sistem, "MAPE_MODULOV", (str(tmp_path / "ni"),))
    programi = {"cinnamon-settings", "gnome-control-center", "mintupdate", "mintsources", "gufw"}
    monkeypatch.setattr(os_sistem.shutil, "which", lambda x: "/usr/bin/" + x if x in programi else None)
    # Seja Cinnamon: moduli Cinnamona, brez plosc GNOME.
    monkeypatch.setattr(os_sistem, "_gnome_seja", lambda: False)
    r = os_sistem.razpolozljivo("sl")
    assert r["moduli"] == sorted(os_sistem.MODULI_VEDNO) and r["plosce"] == []
    # »pkexec mintsources« samo, ce je tudi pkexec (sicer gumb ne bi naredil nicesar).
    assert r["orodja"] == ["posodobitve", "pozarni-zid"]
    programi.add("pkexec")
    assert "viri-programov" in os_sistem.razpolozljivo("sl")["orodja"]
    # Seja GNOME (Ubuntu): plosce GNOME, brez modulov Cinnamona; neznana plosca dobi ime iz sistema.
    monkeypatch.setattr(os_sistem, "_gnome_seja", lambda: True)
    r = os_sistem.razpolozljivo("sl")
    assert r["moduli"] == [] and r["plosce"] == ["display", "zabava"]
    assert r["imena"] == {"p:zabava": {"ime": "Fun", "kljucne": ""}}


def test_odpri_samo_znano(tmp_path, monkeypatch):
    prog = tmp_path / "applications"
    prog.mkdir()
    _namizna(prog, "gnome-about-panel.desktop", "gnome-control-center system about")
    monkeypatch.setattr(os_sistem, "MAPE_PROGRAMOV", (str(prog),))
    pognani = []
    monkeypatch.setattr(os_sistem, "_v_ozadju", lambda u: pognani.append(u) or True)
    monkeypatch.setattr(os_sistem.shutil, "which", lambda x: "/usr/bin/" + x)
    assert os_sistem.odpri_nastavitve("p:about")
    assert not os_sistem.odpri_nastavitve("p:wifi"), "plosce ni na racunalniku"
    assert not os_sistem.odpri_nastavitve("p:about; rm")
    assert os_sistem.odpri_nastavitve("info") and os_sistem.odpri_nastavitve("viri-programov")
    assert not os_sistem.odpri_nastavitve("--help")
    assert pognani == [["gnome-control-center", "system", "about"], ["cinnamon-settings", "info"], ["pkexec", "mintsources"]]


@pytest.fixture(scope="module")
def js():
    return _beri("assets", "os", "os.js")


def _skupine(js):
    blok = js[js.index("var SKUPINE_NASTAVITEV = ["):js.index("var IKONA_NASTAVITVE")]
    return re.findall(r'"((?:[op]:)?[\w-]+)"', blok)


def test_vsak_modul_orodje_in_plosca_ima_mesto_ime_in_ikono(js):
    vnosi = set(_skupine(js))
    besedila = _beri("assets", "os", "besedila.js")
    ikone = js[js.index("var IKONA_NASTAVITVE = {"):js.index("function kljucNastavitve")]
    for m in os_sistem.MODULI:
        assert m in vnosi, m
        assert besedila.count('m_%s:' % m) + besedila.count('"m_%s":' % m) == 6, m
    for o in os_sistem.ORODJA:
        if o == "warpinator":            # program za posiljanje datotek, ne nastavitev (ostane v Napravah)
            continue
        assert "o:" + o in vnosi, o
        assert besedila.count('"o_%s":' % o) == 6, o
    for p in os_sistem.PLOSCE_GNOME:
        assert "p:" + p in vnosi, p
        assert besedila.count('"p_%s":' % p) == 6, p
        assert '"p:%s":' % p in ikone, p


def test_omrezje_in_zvok_ostaneta_strani_safeer_os(js):
    odpri = js[js.index("  function odpriNastavitev(n) {"):js.index("  // ---- iskanje po Nastavitvah")]
    assert 'n.modul === "omrezje" || n.modul === "p:network" || n.modul === "p:wifi") { pojdi("omrezje")' in odpri
    assert 'n.modul === "sound" || n.modul === "p:sound") { pojdi("zvok")' in odpri


def test_zacetek_poslje_jezik():
    assert '"razpolozljivo": os_sistem.razpolozljivo(_jezik()),' in _beri("safeer_os.py")
