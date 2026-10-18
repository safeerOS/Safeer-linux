#!/usr/bin/env python3
"""Safeer DRM v paketu: pripet castLabs ECS, preverjen s SHA-256, ob gradnji paketa.

Lastnik, 18. 10. 2026: Safeer DRM je del paketov kot vse drugo in se med delovanjem ne prenasa vec (prej se je tiho
prenesel 45 s po zagonu v ~/.local/share/safeer-drm). Widevine CDM NI v paketu (odlocitev lastnika po FAQ castLabs:
vgrajen CDM odpre vprasanje licenc dekoderjev; CDM, ki ga ECS prenese z Googlovih streznikov, pokriva licenca Googla) -
ECS ga ob prvi zasciteni vsebini sam namesti v $XDG_CONFIG_HOME/Safeer DRM/WidevineCdm (assets/safeer_drm/main.js).

Uporaba:
  safeer_drm_paket.py pripravi CILJ [--zip ZIP] [--prenosi MAPA]
      Pripravi mapo Safeer DRM za paket: ECS iz pripetega zip (packaging/safeer-drm.json), logika predvajalnika iz
      assets/safeer_drm (resources/app) in OBVESTILO.txt. Brez --zip ga prenese (gradnja .deb in AppImage v CI); Flatpak
      ga dobi kot vir flatpak-builderja (brez omrezja med gradnjo). Zip se preveri s SHA-256, tudi ce je podan.
  safeer_drm_paket.py preveri MAPA
      Preveri namesceno mapo (npr. /usr/lib/safeer-os/safeer-drm): program s pripetim odtisom, brez setuid, brez CDM.
  safeer_drm_paket.py odvisnosti-deb
      Paketi sistema, ki jih ECS potrebuje (za Depends paketov .deb, ko je Safeer DRM v paketu).

Mapo nato namestita packaging/install_payload.sh in install_os_payload.sh (SAFEER_DRM_TOVOR=CILJ) v <tovor>/safeer-drm.
Samo standardna knjiznica Pythona (tece tudi v SDK-ju Flatpaka).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

KOREN = Path(__file__).resolve().parent.parent
#: SAFEER_DRM_PIN samo za preizkuse (tests/test_safeer_drm_paket.py: majhen lazni paket brez omrezja).
PIN = Path(os.environ.get("SAFEER_DRM_PIN") or KOREN / "packaging" / "safeer-drm.json")
LOGIKA = KOREN / "assets" / "safeer_drm"
OZNAKA = ".safeer-drm-tovor"


def pin() -> dict:
    return json.loads(PIN.read_text(encoding="utf-8"))


def _sha256(pot: Path) -> str:
    h = hashlib.sha256()
    with open(pot, "rb") as f:
        for kos in iter(lambda: f.read(1 << 20), b""):
            h.update(kos)
    return h.hexdigest()


def _preveri_datoteko(pot: Path, vnos: dict) -> None:
    velikost = pot.stat().st_size
    if velikost != vnos["velikost"]:
        raise SystemExit(f"safeer_drm_paket: {pot.name}: velikost {velikost}, pricakovana {vnos['velikost']}")
    odtis = _sha256(pot)
    if odtis != vnos["sha256"]:
        raise SystemExit(f"safeer_drm_paket: {pot.name}: SHA-256 {odtis} ni pripeti {vnos['sha256']}")


def prenesi(vnos: dict, mapa: Path) -> Path:
    """Pripeto datoteko prenese v mapo (ce je tam ze prava, je ne prenasa znova) in jo preveri."""
    mapa.mkdir(parents=True, exist_ok=True)
    cilj = mapa / vnos["datoteka"]
    if cilj.is_file():
        try:
            _preveri_datoteko(cilj, vnos)
            return cilj
        except SystemExit:
            cilj.unlink()
    zacasna = cilj.with_name(cilj.name + ".part")
    zahteva = urllib.request.Request(vnos["url"], headers={"User-Agent": "Safeer-gradnja"})
    with urllib.request.urlopen(zahteva, timeout=120) as odziv, open(zacasna, "wb") as izhod:
        shutil.copyfileobj(odziv, izhod, 1 << 20)
    try:
        _preveri_datoteko(zacasna, vnos)
    except SystemExit:
        zacasna.unlink()
        raise
    os.replace(zacasna, cilj)
    return cilj


def _pravice(pravice_v_arhivu: int, mapa: bool) -> int:
    """Samo branje za vse, izvajanje samo tam, kjer ga je imel arhiv; nikoli setuid/setgid (chrome-sandbox ni potreben,
    Chromium uporabi uporabniske imenske prostore)."""
    if mapa:
        return 0o755
    return 0o755 if pravice_v_arhivu & 0o111 else 0o644


def razpakiraj_ecs(zip_pot: Path, cilj: Path) -> None:
    with zipfile.ZipFile(zip_pot) as arhiv:
        for info in arhiv.infolist():
            pot = Path(info.filename)
            if pot.is_absolute() or ".." in pot.parts:
                raise SystemExit(f"safeer_drm_paket: nevarna pot v paketu: {info.filename}")
            if (info.external_attr >> 16) & 0o170000 == stat.S_IFLNK:
                raise SystemExit(f"safeer_drm_paket: simbolna povezava v paketu: {info.filename}")
            if pot.parts and pot.parts[0] == "WidevineCdm":
                raise SystemExit("safeer_drm_paket: Widevine CDM ne sme biti v paketu (namesti ga ECS z Googla)")
        for info in arhiv.infolist():
            arhiv.extract(info, cilj)
            os.chmod(cilj / info.filename, _pravice((info.external_attr >> 16) & 0o7777, info.is_dir()))
    if not (cilj / "safeer-drm").is_file():
        raise SystemExit("safeer_drm_paket: v paketu ni programa safeer-drm")


OBVESTILO = """Safeer DRM - obvestila o licencah / licence notices
=====================================================

Safeer DRM je predvajalnik zascitenih vsebin (Widevine) v paketih Safeer. Sestavljen je iz:

1. Electron for Content Security (ECS) {ecs}, castLabs GmbH: Electron (licenca MIT, datoteka LICENSE v tej mapi) in
   Chromium s komponentami tretjih oseb (licence v LICENSES.chromium.html v tej mapi).
2. Logika predvajalnika Safeer (resources/app): projekt Safeer.

Google Widevine Content Decryption Module (CDM) NI del tega paketa. Ob prvi zasciteni vsebini ga ECS sam prenese z
Googlovih streznikov (storitev posodobitev komponent Chromiuma) v uporabnikovo mapo ~/.config/Safeer DRM/WidevineCdm in
ga posodablja; zanj veljajo pogoji Googla (datoteka LICENSE ob prenesenem modulu). Widevine je blagovna znamka Google LLC.

Safeer DRM is the protected-content (Widevine) player in Safeer packages. It consists of:

1. Electron for Content Security (ECS) {ecs} by castLabs GmbH: Electron (MIT licence, file LICENSE in this folder)
   and Chromium with third-party components (licences in LICENSES.chromium.html in this folder).
2. The Safeer player logic (resources/app): the Safeer project.

The Google Widevine Content Decryption Module (CDM) is NOT part of this package. On the first protected content ECS
downloads it from Google's servers (Chromium's component update service) into the user's folder
~/.config/Safeer DRM/WidevineCdm and keeps it updated; Google's terms apply to it (the LICENSE file next to the
downloaded module). Widevine is a trademark of Google LLC.

Nothing in this folder is downloaded or updated while Safeer runs; it changes only with a Safeer package update.
"""


def pripravi(cilj: Path, zip_pot: "Path | None" = None, prenosi: "Path | None" = None) -> Path:
    p = pin()
    prenosi = prenosi or KOREN / "build" / "safeer-drm-prenosi"
    zip_pot = Path(zip_pot) if zip_pot else prenesi(p["safeer_drm"], prenosi)
    _preveri_datoteko(zip_pot, p["safeer_drm"])
    cilj = Path(cilj)
    if cilj.exists():
        if any(cilj.iterdir()) and not (cilj / OZNAKA).is_file():
            raise SystemExit(f"safeer_drm_paket: {cilj} ni prazna in ni mapa Safeer DRM - ne prepisem je")
        shutil.rmtree(cilj)
    cilj.parent.mkdir(parents=True, exist_ok=True)
    zacasna = Path(tempfile.mkdtemp(prefix=".safeer-drm-", dir=str(cilj.parent)))
    try:
        razpakiraj_ecs(zip_pot, zacasna)
        if _sha256(zacasna / "safeer-drm") != p["safeer_drm"]["program_sha256"]:
            raise SystemExit("safeer_drm_paket: program safeer-drm nima pripetega SHA-256")
        # Logika predvajalnika iz tega izvora (ne tista v zip): paket in koda Safeerja sta vedno ista razlicica.
        app = zacasna / "resources" / "app"
        app.mkdir(parents=True, exist_ok=True)
        for ime in ("main.js", "package.json"):
            shutil.copyfile(LOGIKA / ime, app / ime)
            os.chmod(app / ime, 0o644)
        os.chmod(app, 0o755)
        (zacasna / "OBVESTILO.txt").write_text(OBVESTILO.format(ecs=p["safeer_drm"]["ecs"]), encoding="utf-8")
        shutil.copyfile(PIN, zacasna / "safeer-drm.json")
        (zacasna / OZNAKA).write_text("", encoding="utf-8")
        for ime in ("OBVESTILO.txt", "safeer-drm.json", OZNAKA):
            os.chmod(zacasna / ime, 0o644)
        # Mape, ki jih zip nima kot vnose (nastanejo ob razpakiranju), dobijo pravice po umask - vse na 755.
        for koren, mape, _ in os.walk(zacasna):
            for ime in mape:
                os.chmod(os.path.join(koren, ime), 0o755)
        os.chmod(zacasna, 0o755)
        os.replace(zacasna, cilj)
    except BaseException:
        shutil.rmtree(zacasna, ignore_errors=True)
        raise
    return cilj


def preveri(mapa: Path) -> list:
    """Napake namescene mape Safeer DRM (prazen seznam = v redu)."""
    p, mapa, napake = pin(), Path(mapa), []
    exe = mapa / "safeer-drm"
    if not (exe.is_file() and os.access(exe, os.X_OK)):
        napake.append("program safeer-drm manjka ali ni izvrsljiv")
    elif _sha256(exe) != p["safeer_drm"]["program_sha256"]:
        napake.append("program safeer-drm nima pripetega SHA-256")
    for ime in ("resources/app/main.js", "resources/app/package.json", "OBVESTILO.txt", "LICENSE",
                "LICENSES.chromium.html"):
        if not (mapa / ime).is_file():
            napake.append(f"{ime} manjka")
    if (mapa / "WidevineCdm").exists() or any(mapa.rglob("libwidevinecdm.so")):
        napake.append("Widevine CDM je v paketu (ne sme biti: namesti ga ECS z Googlovih streznikov)")
    for koren, mape, datoteke in os.walk(mapa):
        for ime in mape + datoteke:
            st = os.lstat(os.path.join(koren, ime))
            if st.st_mode & (stat.S_ISUID | stat.S_ISGID):
                napake.append(f"setuid/setgid: {os.path.relpath(os.path.join(koren, ime), mapa)}")
            if stat.S_ISLNK(st.st_mode):
                napake.append(f"simbolna povezava: {os.path.relpath(os.path.join(koren, ime), mapa)}")
    return napake


def main(argv: list) -> int:
    if len(argv) >= 2 and argv[0] == "pripravi":
        moznosti = {"--zip": None, "--prenosi": None}
        cilj, i = None, 1
        while i < len(argv):
            if argv[i] in moznosti and i + 1 < len(argv):
                moznosti[argv[i]] = Path(argv[i + 1]); i += 2
            elif cilj is None and not argv[i].startswith("--"):
                cilj = Path(argv[i]); i += 1
            else:
                print(__doc__, file=sys.stderr); return 2
        if cilj is None:
            print(__doc__, file=sys.stderr); return 2
        mapa = pripravi(cilj, moznosti["--zip"], moznosti["--prenosi"])
        p = pin()
        print(f"Safeer DRM {p['safeer_drm']['verzija']} (ECS {p['safeer_drm']['ecs']}) pripravljen v {mapa}")
        return 0
    if len(argv) == 2 and argv[0] == "preveri":
        napake = preveri(Path(argv[1]))
        for n in napake:
            print("napaka:", n, file=sys.stderr)
        if not napake:
            print(f"Safeer DRM v {argv[1]}: v redu")
        return 1 if napake else 0
    if argv == ["odvisnosti-deb"]:
        print(", ".join(pin()["safeer_drm"]["deb_odvisnosti"]))
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
