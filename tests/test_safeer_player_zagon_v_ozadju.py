"""Pregled 109, S1: Player ne sme podedovati zagona Safeer OS v ozadju (sistemske enote, D-Bus, skripte vzdrzevalca),
obrezi pa ne sme brisati zunaj drevesa prek simbolne povezave. Brez popravka v safeer_player_deb.py ti primeri padejo."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest

KOREN = Path(__file__).resolve().parents[1]
SKRIPTA = KOREN / "packaging" / "safeer_player_deb.py"
PLAYER = "usr/share/applications/safeer-os.Player.desktop"


def _modul():
    spec = importlib.util.spec_from_file_location("safeer_player_deb_s1", SKRIPTA)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _drevo(koren: Path, postinst: str = "#!/bin/sh\nset -e\n") -> Path:
    (koren / "DEBIAN").mkdir(parents=True)
    (koren / "DEBIAN/control").write_text(
        "Package: safeer-os-app\nVersion: 1.0.130\nArchitecture: amd64\nMaintainer: Safeer <info@safeer.si>\n"
        "Installed-Size: 1\nDescription: x\n x\n")
    (koren / "DEBIAN/postinst").write_text(postinst)
    (koren / "DEBIAN/postinst").chmod(0o755)
    (koren / "usr/share/applications").mkdir(parents=True)
    (koren / PLAYER).write_text("[Desktop Entry]\nName=Safeer Player\nExec=safeer-os --predvajalnik\n")
    (koren / "usr/lib/safeer-os").mkdir(parents=True)
    (koren / "usr/lib/safeer-os/safeer_os.py").write_text("print('os')\n")
    (koren / "usr/bin").mkdir(parents=True)
    (koren / "usr/bin/safeer-os").write_text("#!/bin/sh\nexit 0\n")
    (koren / "usr/bin/safeer-os").chmod(0o755)
    return koren


@pytest.mark.parametrize("enota", [
    "usr/lib/systemd/system/safeer-os.service",
    "usr/lib/systemd/user-preset/90-safeer.preset",
    "usr/share/dbus-1/services/si.safeer.OS.service",
    "etc/profile.d/safeer-os.sh",
])
def test_obrezi_zavrne_zagon_v_ozadju(tmp_path, enota):
    koren = _drevo(tmp_path / "koren")
    (koren / enota).parent.mkdir(parents=True, exist_ok=True)
    (koren / enota).write_text("ExecStart=/usr/bin/safeer-os\n")
    m = _modul()
    with pytest.raises(m.NapakaPaketa):
        m.obrezi(koren)


@pytest.mark.parametrize("vrstica", [
    "deb-systemd-helper --user enable safeer-os.service",
    "systemctl --global enable safeer-os.service",
    "update-alternatives --install /usr/bin/x-www-browser x-www-browser /usr/bin/safeer-os 90",
])
def test_obrezi_zavrne_skripto_z_zagonom(tmp_path, vrstica):
    koren = _drevo(tmp_path / "koren", f"#!/bin/sh\nset -e\n{vrstica}\n")
    m = _modul()
    with pytest.raises(m.NapakaPaketa):
        m.obrezi(koren)


def test_obrezi_ne_brise_zunaj_drevesa(tmp_path):
    zunaj = tmp_path / "zunaj"
    zunaj.mkdir()
    (zunaj / "tuja.desktop").write_text("x\n")
    koren = _drevo(tmp_path / "koren")
    shutil.copy(koren / PLAYER, zunaj / "safeer-os.Player.desktop")
    shutil.rmtree(koren / "usr/share/applications")
    (koren / "usr/share/applications").symlink_to(zunaj)
    m = _modul()
    try:
        m.obrezi(koren)
    except m.NapakaPaketa:
        pass
    assert (zunaj / "tuja.desktop").is_file(), "obrezi je prek simbolne povezave izbrisal datoteko zunaj drevesa"


@pytest.mark.skipif(not shutil.which("dpkg-deb"), reason="ni dpkg-deb")
def test_preveri_zavrne_skripto_v_koncnem_paketu(tmp_path):
    """Tudi ce bi zgradi obsel preverbo, preveri na koncnem .deb pogleda skripte vzdrzevalca."""
    m = _modul()
    app = _drevo(tmp_path / "app")
    subprocess.run(["dpkg-deb", "--root-owner-group", "-b", str(app), str(tmp_path / "app.deb")], check=True, capture_output=True)
    m.zgradi(tmp_path / "app.deb", tmp_path / "player.deb")
    r = tmp_path / "r"
    subprocess.run(["dpkg-deb", "-R", str(tmp_path / "player.deb"), str(r)], check=True)
    (r / "DEBIAN/postinst").write_text("#!/bin/sh\nset -e\nsystemctl --global enable safeer-os.service\n")
    subprocess.run(["dpkg-deb", "--root-owner-group", "-b", str(r), str(tmp_path / "player.deb")], check=True, capture_output=True)
    with pytest.raises(SystemExit):
        m.preveri(tmp_path / "app.deb", tmp_path / "player.deb")
