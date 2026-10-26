"""Paket safeer-player (naloga 103): v meniju samo Safeer Player, brez seje namizja in samodejnega zagona.

Zakaj ta preizkus: safeer-player nastane iz zgrajenega safeer-os-app (packaging/safeer_player_deb.py). Ce bi obrezovanje
spustilo vnos Safeer OS, sejo ali samodejni zagon, bi uporabnik, ki je hotel samo predvajalnik, dobil Safeer OS ob prijavi.
Preizkus na umetnem drevesu ne potrebuje dpkg-deb ne WebKita; ce je SAFEER_PLAYER_DEB nastavljen (CI ali vodja po
gradnji), preveri se pravi paket.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
from pathlib import Path

import pytest

KOREN = Path(__file__).resolve().parents[1]
SKRIPTA = KOREN / "packaging" / "safeer_player_deb.py"


def _modul():
    # Brez popravka datoteke ni: preizkus pade (to je namen - paketa safeer-player se ni).
    assert SKRIPTA.is_file(), "packaging/safeer_player_deb.py manjka: paketa safeer-player ni"
    spec = importlib.util.spec_from_file_location("safeer_player_deb", SKRIPTA)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


CONTROL_APP = """Package: safeer-os-app
Version: 1.0.130
Architecture: amd64
Maintainer: Safeer <info@safeer.si>
Installed-Size: 1
Depends: python3 (>= 3.12), bubblewrap, libnss3
Provides: safeer-webkit (= 2.50.1+vgrajen), safeer-control (= 1.0.90), safeer-os-app
Conflicts: safeer-os
Replaces: safeer-os
Description: Safeer OS - app in a window
 Long description line.
"""


def _zapisi(pot: Path, vsebina: str = "x\n") -> Path:
    pot.parent.mkdir(parents=True, exist_ok=True)
    pot.write_text(vsebina)
    return pot


@pytest.fixture
def drevo_app(tmp_path: Path) -> Path:
    """Drevo, kot ga da dpkg-deb -R safeer-os-app: vnosi, ki jih zapise install_os_payload.sh (ID=safeer-os)."""
    koren = tmp_path / "koren"
    prijave = KOREN / "packaging" / "safeer-player.desktop"
    # Kot install_os_payload.sh: sed "s/^Icon=.*/Icon=$ID.Player/" (ID=safeer-os).
    player = "".join(
        "Icon=safeer-os.Player\n" if v.startswith("Icon=") else v + "\n" for v in prijave.read_text().splitlines()
    )
    _zapisi(koren / "usr/share/applications/safeer-os.Player.desktop", player)
    for ime in ("safeer-os", "safeer-os.Magnet", "safeer-os.Stremio", "safeer-os.splet", "safeer-os.sporocila",
                "safeer-os.zapiski", "safeer-os.nastavitve", "safeer-os.scit", "safeer-control"):
        _zapisi(koren / f"usr/share/applications/{ime}.desktop", "[Desktop Entry]\nName=x\n")
    _zapisi(koren / "usr/share/xsessions/safeer-os.desktop")
    _zapisi(koren / "usr/share/wayland-sessions/safeer-os.desktop")
    _zapisi(koren / "etc/xdg/autostart/safeer-os.desktop")
    _zapisi(koren / "usr/share/metainfo/io.github.memelandfaner.SafeerOS.metainfo.xml")
    _zapisi(koren / "usr/lib/safeer-os/safeer_os.py", "print('safeer os')\n")
    _zapisi(koren / "usr/lib/safeer-os/core/os_predvajalnik.py")
    _zapisi(koren / "usr/share/icons/hicolor/scalable/apps/safeer-os.Player.svg", "<svg/>\n")
    _zapisi(koren / "usr/bin/safeer-os", "#!/bin/sh\n").chmod(0o755)
    _zapisi(koren / "etc/apparmor.d/safeer-os")
    _zapisi(koren / "DEBIAN/control", CONTROL_APP)
    _zapisi(koren / "DEBIAN/conffiles", "/etc/apparmor.d/safeer-os\n/etc/xdg/autostart/safeer-os.desktop\n")
    _zapisi(koren / "DEBIAN/md5sums", "staro\n")
    _zapisi(koren / "DEBIAN/postinst", "#!/bin/sh\nset -e\n")
    return koren


def _namizni(koren: Path) -> list[str]:
    return sorted(p.relative_to(koren).as_posix() for p in (koren / "usr/share").rglob("*.desktop"))


def test_v_meniju_samo_player_brez_seje_in_samodejnega_zagona(drevo_app: Path):
    _modul().obrezi(drevo_app)
    assert _namizni(drevo_app) == ["usr/share/applications/safeer-os.Player.desktop"]
    for mapa in ("usr/share/xsessions", "usr/share/wayland-sessions", "etc/xdg/autostart", "usr/share/metainfo"):
        assert not (drevo_app / mapa).exists(), mapa
    # Isti tovor kot aplikacija: koda, ikona Playerja, zaganjalnik safeer-os (Exec v vnosu) in profil AppArmor ostanejo.
    for pot in ("usr/lib/safeer-os/safeer_os.py", "usr/lib/safeer-os/core/os_predvajalnik.py", "usr/bin/safeer-os",
                "usr/share/icons/hicolor/scalable/apps/safeer-os.Player.svg", "etc/apparmor.d/safeer-os"):
        assert (drevo_app / pot).is_file(), pot
    vnos = (drevo_app / "usr/share/applications/safeer-os.Player.desktop").read_text()
    assert "Exec=safeer-os --predvajalnik" in vnos
    assert "NoDisplay=true" not in vnos


def test_ukaz_safeer_player_zazene_predvajalnik(drevo_app: Path):
    _modul().obrezi(drevo_app)
    zaganjalnik = drevo_app / "usr/bin/safeer-player"
    assert os.access(zaganjalnik, os.X_OK)
    assert 'exec /usr/bin/safeer-os --predvajalnik "$@"' in zaganjalnik.read_text()


def test_polja_paketa_zamenjata_os_in_aplikacijo(drevo_app: Path):
    modul = _modul()
    modul.obrezi(drevo_app)
    polja = dict(modul.beri_control((drevo_app / "DEBIAN/control").read_text()))
    assert polja["Package"] == "safeer-player"
    assert polja["Version"] == "1.0.130"
    assert polja["Depends"] == "python3 (>= 3.12), bubblewrap, libnss3"
    # Vgrajen WebKit in Control ostaneta ponujena; Player ne obljublja aplikacije.
    assert polja["Provides"] == "safeer-webkit (= 2.50.1+vgrajen), safeer-control (= 1.0.90)"
    assert polja["Conflicts"] == "safeer-os, safeer-os-app"
    assert polja["Replaces"] == "safeer-os, safeer-os-app"
    assert polja["Description"].startswith("Safeer Player")
    assert int(polja["Installed-Size"]) > 1


def test_conffiles_in_md5sums_ustrezata_vsebini(drevo_app: Path):
    _modul().obrezi(drevo_app)
    assert (drevo_app / "DEBIAN/conffiles").read_text() == "/etc/apparmor.d/safeer-os\n"
    md5 = (drevo_app / "DEBIAN/md5sums").read_text()
    assert "usr/share/applications/safeer-os.Player.desktop" in md5
    assert "usr/bin/safeer-player" in md5
    assert "xsessions" not in md5 and "autostart" not in md5 and "staro" not in md5


def test_seja_v_skripti_vzdrzevalca_ustavi_gradnjo(drevo_app: Path):
    modul = _modul()
    (drevo_app / "DEBIAN/postinst").write_text("#!/bin/sh\nupdate-alternatives --install /usr/bin/x-session-manager x\n")
    with pytest.raises(modul.NapakaPaketa):
        modul.obrezi(drevo_app)


def test_brez_vnosa_player_gradnja_pade(drevo_app: Path):
    modul = _modul()
    (drevo_app / "usr/share/applications/safeer-os.Player.desktop").unlink()
    with pytest.raises(modul.NapakaPaketa):
        modul.obrezi(drevo_app)


@pytest.mark.skipif(not os.environ.get("SAFEER_PLAYER_DEB") or not shutil.which("dpkg-deb"),
                    reason="SAFEER_PLAYER_DEB ni nastavljen (pravi paket preveri CI po gradnji)")
def test_pravi_paket_ima_samo_vnos_player():
    deb = os.environ["SAFEER_PLAYER_DEB"]
    vsebina = subprocess.run(["dpkg-deb", "-c", deb], check=True, capture_output=True, text=True).stdout
    poti = [v.split(None, 5)[5].split(" -> ")[0] for v in vsebina.splitlines()]
    assert [p for p in poti if p.endswith(".desktop")] == ["./usr/share/applications/safeer-os.Player.desktop"]
    assert not [p for p in poti if "/xsessions/" in p or "/wayland-sessions/" in p or "/xdg/autostart/" in p]
    paket = subprocess.run(["dpkg-deb", "-f", deb, "Package"], check=True, capture_output=True, text=True).stdout
    assert paket.strip() == "safeer-player"
