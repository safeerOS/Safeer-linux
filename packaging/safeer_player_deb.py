#!/usr/bin/env python3
"""Paket .deb »safeer-player« (Safeer Player, samo Medijski center) iz ze zgrajenega paketa safeer-os-app.

Zakaj izpeljava iz zgrajenega paketa in ne tretja gradnja z build_os_deb.sh: tovor (core/, assets, vgrajen Safeer
WebKit, rqbit, Safeer DRM, PySide6) je tako bajt za bajtom isti kot v safeer-os-app - nic podvojene logike gradnje,
ni druge ~ure gradnje in utrjenost ELF (readelf) je dokazljivo enaka (ukaz »preveri« primerja SHA-256 vsake datoteke).
Spremeni se samo to, kar loci Player od aplikacije: polja paketa in vnosi v meniju (ostane le safeer-os.Player.desktop),
brez seje namizja in samodejnega zagona.

Zakaj Conflicts + Replaces s safeer-os in safeer-os-app (in ne hkratna namestitev): vsi trije paketi namestijo isti
/usr/lib/safeer-os, safeer-os in safeer-os-app pa vnos Safeer Player ze imata (install_os_payload.sh). Hkratna
namestitev uporabniku ne bi dala nicesar, apt pa paket ob menjavi sam zamenja - tako kot ze safeer-os <-> safeer-os-app.

Uporaba:
  python3 packaging/safeer_player_deb.py zgradi safeer-os-app_X_amd64.deb safeer-player_X_amd64.deb
  python3 packaging/safeer_player_deb.py preveri safeer-os-app_X_amd64.deb safeer-player_X_amd64.deb
"""
from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

IME = "safeer-player"
# Ime vnosa iz install_os_payload.sh ($ID.Player.desktop, ID=safeer-os); StartupWMClass in ikona sta vezana nanj.
PLAYER_DESKTOP = "usr/share/applications/safeer-os.Player.desktop"
ZAGANJALNIK = "usr/bin/safeer-player"
KOREN_REPO = Path(__file__).resolve().parents[1]
VIR_ZAGANJALNIKA = KOREN_REPO / "packaging" / "safeer-player-launcher"
# Paketa z istim /usr/lib/safeer-os: Player ju zamenja in obratno (apt ob namestitvi enega odstrani drugega).
ZAMENJA = ("safeer-os", "safeer-os-app")
# Seja namizja, samodejni zagon in opis v trgovini (metainfo kaze na safeer-os.desktop, ki ga Player nima).
ODSTRANI = ("usr/share/xsessions", "usr/share/wayland-sessions", "etc/xdg/autostart", "usr/share/metainfo")
# Uporabniske enote systemd lahko zazenejo Safeer OS ob prijavi; ne ugibamo, ali so potrebne - gradnja se ustavi.
SYSTEMD_UPORABNIK = ("usr/lib/systemd/user", "etc/systemd/user")
# Ce bi skripta vzdrzevalca nastavljala sejo ali samodejni zagon, je ne smemo tiho prepisati v Player.
SEJA_V_SKRIPTAH = ("xsessions", "wayland-sessions", "xdg/autostart", "x-session-manager", "lightdm")
# Drugi nacini zagona v ozadju (sistemske enote, prednastavitve, aktivacija D-Bus, cron, prijavna lupina, udev): gradnja
# se ustavi, ne ugibamo. Seznam je namerno sirok - napacen alarm je poceni, tih zagon Safeer OS ob prijavi ni.
ZAGON_V_OZADJU = (
    "usr/lib/systemd/system", "lib/systemd/system", "etc/systemd/system",
    "usr/lib/systemd/user-preset", "usr/lib/systemd/system-preset", "usr/lib/systemd/user-generators",
    "usr/lib/systemd/user-environment-generators", "usr/lib/environment.d",
    "usr/share/dbus-1/services", "usr/share/dbus-1/system-services", "etc/cron.d", "etc/cron.daily",
    "etc/cron.hourly", "etc/profile.d", "etc/X11/Xsession.d", "usr/lib/udev/rules.d", "lib/udev/rules.d",
)
# Ukazi v skriptah vzdrzevalca, ki bi Player naredili za storitev ali privzeti brskalnik/sejo.
ZAGON_V_SKRIPTAH = (
    "systemctl", "deb-systemd-helper", "deb-systemd-invoke", "invoke-rc.d", "update-rc.d", "update-alternatives",
    "dbus-send", "gdbus", "loginctl", "crontab", "xdg-settings", "xdg-mime",
)
SKRIPTE = ("preinst", "postinst", "prerm", "postrm")
OPIS = (
    "Safeer Player - the Safeer OS Media Centre in its own window\n"
    " Films, series, music, radio and TV. The same payload as safeer-os-app (Safeer OS\n"
    " core, assets and the built-in Safeer WebKit); the menu has only the Safeer Player\n"
    " entry, with no desktop session and no autostart. It replaces safeer-os and\n"
    " safeer-os-app, which already include Safeer Player."
)


class NapakaPaketa(Exception):
    """Paket ni tak, kot ga Player pricakuje; gradnja se ustavi z razlogom (ne ugibamo)."""


def beri_control(besedilo: str) -> list[tuple[str, str]]:
    """DEBIAN/control (en odstavek) -> seznam (polje, vrednost); nadaljevalne vrstice ostanejo v vrednosti."""
    polja: list[tuple[str, str]] = []
    for vrstica in besedilo.splitlines():
        if not vrstica.strip():
            continue
        if vrstica[0] in " \t":
            if not polja:
                raise NapakaPaketa("control se zacne z nadaljevalno vrstico")
            ime, vrednost = polja[-1]
            polja[-1] = (ime, vrednost + "\n" + vrstica)
            continue
        ime, dvopicje, vrednost = vrstica.partition(":")
        if not dvopicje:
            raise NapakaPaketa(f"vrstica brez polja v control: {vrstica!r}")
        polja.append((ime.strip(), vrednost.strip()))
    return polja


def pisi_control(polja: list[tuple[str, str]]) -> str:
    return "".join(f"{ime}: {vrednost}\n" for ime, vrednost in polja)


def _ime_odvisnosti(odvisnost: str) -> str:
    # »safeer-webkit (= 2.50+vgrajen)« -> safeer-webkit; »paket:any« -> paket
    return odvisnost.split("(")[0].strip().split(":")[0]


def _seznam(vrednost: str) -> list[str]:
    return [d.strip() for d in vrednost.replace("\n", " ").split(",") if d.strip()]


def uredi_control(polja: list[tuple[str, str]], namesceno_kib: int | None = None) -> list[tuple[str, str]]:
    """Polja safeer-os-app -> safeer-player. Depends (vgrajen WebKit, bubblewrap ...) ostane enak kot v aplikaciji."""
    slovar = dict(polja)
    if "Package" not in slovar:
        raise NapakaPaketa("control nima polja Package")

    def brez_nasih(vrednost: str) -> list[str]:
        return [d for d in _seznam(vrednost) if _ime_odvisnosti(d) not in (IME, *ZAMENJA)]

    nova: dict[str, str] = {
        "Package": IME,
        "Description": OPIS,
        # Aplikacija lahko ponuja sebe ali safeer-os (navidezni paket); Player ne sme obljubljati namizja ali aplikacije.
        "Provides": ", ".join(brez_nasih(slovar.get("Provides", ""))),
        "Conflicts": ", ".join([*brez_nasih(slovar.get("Conflicts", "")), *ZAMENJA]),
        "Replaces": ", ".join([*brez_nasih(slovar.get("Replaces", "")), *ZAMENJA]),
    }
    if namesceno_kib is not None:
        nova["Installed-Size"] = str(namesceno_kib)
    izhod: list[tuple[str, str]] = []
    for ime, vrednost in polja:
        if ime in nova:
            if nova[ime]:
                izhod.append((ime, nova.pop(ime)))
            else:
                nova.pop(ime)
        else:
            izhod.append((ime, vrednost))
    izhod.extend((ime, vrednost) for ime, vrednost in nova.items() if vrednost)
    return izhod


def _odstrani_prazne_starse(pot: Path, koren: Path) -> None:
    stars = pot.parent
    while stars != koren and stars.is_dir() and not any(stars.iterdir()):
        stars.rmdir()
        stars = stars.parent


def _md5sums(koren: Path) -> str:
    vrstice = []
    for dat in sorted(koren.rglob("*")):
        rel = dat.relative_to(koren).as_posix()
        if rel.startswith("DEBIAN/") or dat.is_symlink() or not dat.is_file():
            continue
        vrstice.append(f"{hashlib.md5(dat.read_bytes()).hexdigest()}  {rel}\n")
    return "".join(vrstice)


def namesceno_kib(koren: Path) -> int:
    """Kot dpkg-gencontrol: vsaka datoteka zaokrozeno na KiB, vsaka mapa in povezava 1 KiB."""
    skupaj = 0
    for pot in koren.rglob("*"):
        if pot.relative_to(koren).parts[0] == "DEBIAN":
            continue
        if pot.is_file() and not pot.is_symlink():
            skupaj += (pot.stat().st_size + 1023) // 1024
        else:
            skupaj += 1
    return skupaj


def preveri_skripte(debian: Path) -> None:
    """Skripte vzdrzevalca ne smejo nastavljati seje ne zagona v ozadju (uporabi zgradi in preveri)."""
    for skripta in SKRIPTE:
        pot = debian / skripta
        if pot.is_file():
            besedilo = pot.read_text(errors="replace")
            for niz in SEJA_V_SKRIPTAH + ZAGON_V_SKRIPTAH:
                if niz in besedilo:
                    raise NapakaPaketa(f"DEBIAN/{skripta} omenja {niz!r}: seje ali zagona v ozadju ne prenesemo v Player")


def _brez_povezav(koren: Path, rel: str) -> None:
    """Mapa, ki jo obrezi bere ali brise, ne sme biti (ali lezati pod) simbolno povezavo: sicer brisemo zunaj drevesa."""
    pot = koren
    for del_poti in Path(rel).parts:
        pot = pot / del_poti
        if pot.is_symlink():
            raise NapakaPaketa(f"/{pot.relative_to(koren).as_posix()} je simbolna povezava: Player je ne obreze")


def obrezi(koren: Path, vir_zaganjalnika: Path = VIR_ZAGANJALNIKA) -> list[str]:
    """Razpakiran safeer-os-app (dpkg-deb -R) v koren -> drevo safeer-player. Vrne odstranjene poti."""
    for mapa in SYSTEMD_UPORABNIK + ZAGON_V_OZADJU:
        if (koren / mapa).exists() and any(not p.is_dir() for p in (koren / mapa).rglob("*")):
            raise NapakaPaketa(f"/{mapa} v paketu: odloci, ali sodi v Player (samodejni zagon?)")
    preveri_skripte(koren / "DEBIAN")
    for mapa in ("usr/share/applications", *ODSTRANI):
        _brez_povezav(koren, mapa)
    player = koren / PLAYER_DESKTOP
    if not player.is_file():
        raise NapakaPaketa(f"/{PLAYER_DESKTOP} ni v paketu (ime v install_os_payload.sh spremenjeno?)")
    vnos = player.read_text()
    if "--predvajalnik" not in vnos or any(v.strip() == "NoDisplay=true" for v in vnos.splitlines()):
        raise NapakaPaketa(f"/{PLAYER_DESKTOP} ne zazene vidnega Playerja (--predvajalnik, brez NoDisplay)")

    odstranjeno: list[str] = []
    # Samo en vnos v meniju: namizje, Magnet/Stremio, okna pulta (NoDisplay) in Safeer Control gredo ven.
    for dat in sorted((koren / "usr/share/applications").rglob("*")):
        if dat != player and (dat.is_file() or dat.is_symlink()):
            odstranjeno.append(dat.relative_to(koren).as_posix())
            dat.unlink()
            _odstrani_prazne_starse(dat, koren)
    for mapa in ODSTRANI:
        pot = koren / mapa
        if pot.exists():
            odstranjeno.extend(p.relative_to(koren).as_posix() for p in sorted(pot.rglob("*")) if not p.is_dir())
            shutil.rmtree(pot)
            _odstrani_prazne_starse(pot, koren)

    # Ukaz safeer-player za terminal; isti zagon kot vnos v meniju (Exec=safeer-os --predvajalnik).
    cilj = koren / ZAGANJALNIK
    cilj.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(vir_zaganjalnika, cilj)
    cilj.chmod(0o755)

    debian = koren / "DEBIAN"
    conffiles = debian / "conffiles"
    if conffiles.is_file():
        # Odstranjen conffile (npr. /etc/xdg/autostart/...) bi dpkg-deb -b zavrnil.
        ostanejo = [c for c in conffiles.read_text().splitlines() if c.strip() and (koren / c.strip().lstrip("/")).exists()]
        conffiles.write_text("".join(f"{c}\n" for c in ostanejo))
    (debian / "md5sums").write_text(_md5sums(koren))
    control = debian / "control"
    control.write_text(pisi_control(uredi_control(beri_control(control.read_text()), namesceno_kib(koren))))
    return odstranjeno


def _je_elf(pot: Path) -> bool:
    with pot.open("rb") as dat:
        return dat.read(4) == b"\x7fELF"


def _sha256(pot: Path) -> str:
    h = hashlib.sha256()
    with pot.open("rb") as dat:
        for kos in iter(lambda: dat.read(1 << 20), b""):
            h.update(kos)
    return h.hexdigest()


def _dpkg_deb(*argumenti: str) -> str:
    if not shutil.which("dpkg-deb"):
        raise NapakaPaketa("ni dpkg-deb")
    return subprocess.run(["dpkg-deb", *argumenti], check=True, capture_output=True, text=True).stdout


def zgradi(app_deb: Path, player_deb: Path) -> None:
    with tempfile.TemporaryDirectory(prefix="safeer-player-") as zacasno:
        koren = Path(zacasno) / "koren"
        _dpkg_deb("-R", str(app_deb), str(koren))
        odstranjeno = obrezi(koren)
        print(f"safeer-player: odstranjeno {len(odstranjeno)} poti iz safeer-os-app:")
        for pot in odstranjeno:
            print(f"  - /{pot}")
        # --root-owner-group: -R kot navaden uporabnik bi sicer zapisal lastnika gradnje.
        _dpkg_deb("--root-owner-group", "-b", str(koren), str(player_deb))
    print(f"zgrajen {player_deb}")


def _vsebina(deb: Path) -> dict[str, tuple[str, str]]:
    """dpkg-deb -c -> {pot: (pravice, lastnik)}."""
    izhod = {}
    for vrstica in _dpkg_deb("-c", str(deb)).splitlines():
        deli = vrstica.split(None, 5)
        pot = deli[5].split(" -> ")[0]
        izhod[pot.lstrip(".").lstrip("/").rstrip("/")] = (deli[0], deli[1])
    return izhod


def preveri(app_deb: Path, player_deb: Path) -> None:
    """Player = safeer-os-app brez menija/seje: vsaka skupna datoteka je bajt za bajtom ista (ista utrjenost ELF)."""
    napake: list[str] = []
    app, player = _vsebina(app_deb), _vsebina(player_deb)
    namizni = sorted(p for p in player if p.startswith("usr/share/applications/") and p.endswith(".desktop"))
    if namizni != [PLAYER_DESKTOP]:
        napake.append(f"vnosi .desktop: {namizni} (pricakovan samo {PLAYER_DESKTOP})")
    for pot in player:
        if any(pot == m or pot.startswith(m + "/") for m in ODSTRANI + SYSTEMD_UPORABNIK + ZAGON_V_OZADJU):
            napake.append(f"seja/samodejni zagon v paketu: /{pot}")
        elif pot != ZAGANJALNIK and pot not in app:
            napake.append(f"/{pot} ni v safeer-os-app")
        elif pot != ZAGANJALNIK and player[pot] != app[pot]:
            napake.append(f"/{pot}: pravice/lastnik {player[pot]} != {app[pot]}")
    with tempfile.TemporaryDirectory(prefix="safeer-player-preveri-") as zacasno:
        a, p = Path(zacasno) / "app", Path(zacasno) / "player"
        _dpkg_deb("-x", str(app_deb), str(a))
        _dpkg_deb("-x", str(player_deb), str(p))
        _dpkg_deb("-e", str(player_deb), str(Path(zacasno) / "DEBIAN"))
        try:
            preveri_skripte(Path(zacasno) / "DEBIAN")
        except NapakaPaketa as napaka:
            napake.append(str(napaka))
        elf_app = {d.relative_to(a).as_posix() for d in a.rglob("*") if d.is_file() and not d.is_symlink() and _je_elf(d)}
        elf_player = set()
        for dat in p.rglob("*"):
            rel = dat.relative_to(p).as_posix()
            if not dat.is_file() or dat.is_symlink() or rel == ZAGANJALNIK:
                continue
            if not (a / rel).is_file():
                continue  # ze zapisano zgoraj (ni v safeer-os-app)
            if _je_elf(dat):
                elf_player.add(rel)
            if _sha256(dat) != _sha256(a / rel):
                napake.append(f"/{rel} se razlikuje od safeer-os-app")
        if elf_player != elf_app:
            napake.append(f"ELF razlicni: samo v app {sorted(elf_app - elf_player)[:5]}, samo v player {sorted(elf_player - elf_app)[:5]}")
    if napake:
        for napaka in napake:
            print(f"::error::safeer-player: {napaka}")
        raise SystemExit(1)
    print(f"safeer-player: {len(player)} poti, {len(elf_player)} ELF bajt za bajtom enakih kot v safeer-os-app; meni: {PLAYER_DESKTOP}")


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[0] not in ("zgradi", "preveri"):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        (zgradi if argv[0] == "zgradi" else preveri)(Path(argv[1]), Path(argv[2]))
    except NapakaPaketa as napaka:
        print(f"::error::safeer-player: {napaka}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
