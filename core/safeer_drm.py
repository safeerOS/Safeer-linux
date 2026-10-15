"""Safeer DRM (Widevine prek castLabs ECS) vdelan v Splet Safeer OS na Linuxu.

WebKitGTK nima Widevine. Prej (11. 10. 2026) se je stran z Widevine odprla v drugem brskalniku (Brave ...). Lastnik,
13. 10. 2026: zasciten video naj se predvaja v Spletu in v nasem predvajalniku, kot en predvajalnik - uporabnik ne sme
opaziti menjave. Zato: ko stran zaprosi za Widevine, se ista stran odpre v Safeer DRM, katerega okno je vstavljeno
(X11 XReparentWindow) v isti zavihek Spleta. Zavihek, naslovna vrstica in gumbi ostanejo; Nazaj in Osvezi delujeta.

Paket (~120 MB, castLabs ECS za linux-x64; Linux ne potrebuje VMP podpisa) se prenese enkrat ob prvi potrebi, preveri se
SHA-256. Logika (main.js) pride s Safeer OS (assets/safeer_drm) in se uskladi ob vsakem zagonu. Safeer OS v Flatpaku
Safeer DRM zazene na gostitelju (flatpak-spawn --host), da ostane peskovnik Chromiuma v celoti vklopljen.
Brez X11 (Wayland) okna ni mogoce vstaviti: Safeer DRM se odpre v svojem oknu.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

from core import vstavi_okno

VERZIJA = "0.2.0"
URL = ("https://github.com/safeerOS/Safeer-linux/releases/download/"
       f"safeer-drm-v{VERZIJA}/SafeerDRM-{VERZIJA}-linux-x64.zip")
SHA256 = "018cdfc0d1b4061fa9b7972ce5588be39d70d42ea47a2494a698f6b601737396"
OZNAKA = ".preverjeno"
_zaklep = threading.Lock()


def koren() -> Path:
    # Pot na gostitelju (ne ~/.var/app/...): Safeer DRM v Flatpaku tece na gostitelju.
    return Path(os.path.expanduser("~/.local/share/safeer-drm"))


def mapa_verzije() -> Path:
    return koren() / VERZIJA


def izvrsljiva() -> Optional[Path]:
    exe = mapa_verzije() / "safeer-drm"
    return exe if (mapa_verzije() / OZNAKA).is_file() and exe.is_file() else None


def vir_logike() -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / "safeer_drm"


def uskladi_logiko(exe: Path, vir: Optional[Path] = None) -> None:
    vir = vir or vir_logike()
    cilj = exe.parent / "resources" / "app"
    for ime in ("main.js", "package.json"):
        izvor = vir / ime
        if not izvor.is_file():
            continue
        try:
            if (cilj / ime).is_file() and (cilj / ime).read_bytes() == izvor.read_bytes():
                continue
            cilj.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(izvor, cilj / ime)
        except OSError:
            pass


def _varno_razpakiraj(paket: Path, cilj: Path) -> None:
    with zipfile.ZipFile(paket) as arhiv:
        for info in arhiv.infolist():
            pot = Path(info.filename)
            if pot.is_absolute() or ".." in pot.parts:
                raise ValueError(f"nevarna pot v paketu: {info.filename}")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f"simbolna povezava v paketu: {info.filename}")
        for info in arhiv.infolist():
            arhiv.extract(info, cilj)
            pravice = (info.external_attr >> 16) & 0o777
            if pravice and not info.is_dir():
                # Brez setuid/setgid: chrome-sandbox ni potreben, Chromium uporabi uporabniske imenske prostore.
                os.chmod(cilj / info.filename, pravice & 0o755)


def prenesi(url: str = URL, sha256: str = SHA256) -> bool:
    with _zaklep:
        if izvrsljiva() is not None:
            return True
        koren().mkdir(parents=True, exist_ok=True)
        zacasno = koren() / f"prenos-{VERZIJA}.part"
        nova = koren() / f"{VERZIJA}.nova"
        try:
            odtis = hashlib.sha256()
            zahteva = urllib.request.Request(url, headers={"User-Agent": "SafeerOS"})
            with urllib.request.urlopen(zahteva, timeout=60) as odziv, open(zacasno, "wb") as izhod:
                while True:
                    kos = odziv.read(1 << 20)
                    if not kos:
                        break
                    odtis.update(kos)
                    izhod.write(kos)
            if odtis.hexdigest() != sha256:
                print("[SafeerDRM] SHA-256 se ne ujema, paket zavrzen", flush=True)
                return False
            shutil.rmtree(nova, ignore_errors=True)
            _varno_razpakiraj(zacasno, nova)
            if not (nova / "safeer-drm").is_file():
                return False
            (nova / OZNAKA).write_text(sha256, encoding="utf-8")
            shutil.rmtree(mapa_verzije(), ignore_errors=True)
            os.replace(nova, mapa_verzije())
            for stara in koren().iterdir():
                if stara.is_dir() and stara.name != VERZIJA:
                    shutil.rmtree(stara, ignore_errors=True)
            print(f"[SafeerDRM] {VERZIJA} pripravljen", flush=True)
            return True
        except Exception as e:  # noqa: BLE001 - brez Safeer DRM stran ostane v Spletu
            print(f"[SafeerDRM] prenos ni uspel: {e}", flush=True)
            return False
        finally:
            try:
                zacasno.unlink()
            except OSError:
                pass
            shutil.rmtree(nova, ignore_errors=True)


def prenesi_v_ozadju(ko_koncano: Optional[Callable[[bool], None]] = None) -> None:
    def delo():
        izid = prenesi()
        if ko_koncano:
            ko_koncano(izid)
    threading.Thread(target=delo, name="safeer-drm-prenos", daemon=True).start()


#: Storitve z narocnino: stalen profil (prijava ostane), brez samodejnega klika, prosto premikanje po https.
STORITVE = (
    "netflix.com", "primevideo.com", "amazon.com", "disneyplus.com", "max.com", "hbomax.com", "skyshowtime.com",
    "tv.apple.com", "voyo.si", "paramountplus.com", "dazn.com", "crunchyroll.com", "mubi.com", "rakuten.tv",
    "spotify.com", "tidal.com", "deezer.com",
)


def je_storitev(url: str) -> bool:
    import urllib.parse
    try:
        gost = (urllib.parse.urlsplit(url).hostname or "").lower()
    except ValueError:
        return False
    return any(gost == d or gost.endswith("." + d) for d in STORITVE)


def v_flatpaku() -> bool:
    return os.path.exists("/.flatpak-info")


#: Xlib za vstavitev okna je skupen s Sporocili (vgrajeni namizni programi): core/vstavi_okno.py - ena izvedba.
_X11 = vstavi_okno.X11


class Gostitelj:
    """Gradnik GTK4, nad katerim je okno Safeer DRM. En gostitelj = ena seja (en zavihek).

    GTK4 nima X okna na gradnik: okno Safeer DRM postane otrok X okna vrhnjega okna (Safeer OS / Splet) na mestu in
    v velikosti tega gradnika; mesto se preveri ob vsaki spremembi velikosti in ob branju stanja (200 ms)."""

    def __init__(self, Gtk, Gdk, GLib, ob_celozaslonu: Optional[Callable[[bool], None]] = None,
                 ob_koncu: Optional[Callable[[], None]] = None) -> None:
        self.Gtk, self.Gdk, self.GLib = Gtk, Gdk, GLib
        self.ob_celozaslonu, self.ob_koncu = ob_celozaslonu, ob_koncu
        #: GTK3 (Safeer Browser, safeer_mint.py): gradnik ima svoje X okno - okno DRM je njegov otrok na (0, 0)
        #: (tako je delovalo pred prehodom na GTK4, 3995d62). GTK4: otrok vrhnjega okna na mestu gradnika.
        self._gtk3 = Gtk.get_major_version() == 3
        self.gradnik = Gtk.DrawingArea()
        self.gradnik.set_name("safeer-drm")
        self.gradnik.set_hexpand(True); self.gradnik.set_vexpand(True)
        if self._gtk3:
            self.gradnik.set_can_focus(True)
            self.gradnik.connect("size-allocate", lambda *_: self._prilagodi())
            self.gradnik.connect("draw", lambda _g, cr: self._risi(_g, cr))
            self.gradnik.add_events(Gdk.EventMask.KEY_PRESS_MASK)
        else:
            self.gradnik.set_focusable(True)
            self.gradnik.connect("resize", lambda *_: self._prilagodi())
            self.gradnik.set_draw_func(lambda _g, cr, *_: self._risi(_g, cr))
        self._mesto = None
        self._mesto_gradnika = vstavi_okno.Mesto(Gtk, self.gradnik)
        # Okno DRM je otrok vrhnjega okna, zato ga ob skritju gradnika (drug zavihek, Splet skrit) skrijemo sami.
        self.gradnik.connect("map", lambda *_: self._vidno(True))
        self.gradnik.connect("unmap", lambda *_: self._vidno(False))
        self.proces: Optional[subprocess.Popen] = None
        self.seja = ""
        self.stanje = ""
        self.ukazi = ""
        self._odmik = 0
        self._okno = 0
        self._x11: Optional[_X11] = None
        self._casovnik = 0
        self.url = ""

    def _risi(self, _g, cr) -> bool:
        cr.set_source_rgb(0, 0, 0)
        cr.paint()
        return False

    @staticmethod
    def na_voljo() -> bool:
        return izvrsljiva() is not None

    def _xid_starsa(self) -> int:
        return self._mesto_gradnika.xid_starsa()

    def _pravokotnik(self):
        """(x, y, sirina, visina) gradnika v X pikah povrsine vrhnjega okna (core/vstavi_okno.Mesto)."""
        return self._mesto_gradnika.pravokotnik()

    def zacni(self, url: str, storitev: bool = False) -> bool:
        exe = izvrsljiva()
        if exe is None or not url.startswith("https://"):
            return False
        self.ustavi()
        uskladi_logiko(exe)
        self.url = url
        if self._gtk3:
            self.gradnik.realize()   # GTK3: X okno gradnika mora obstajati, preden ga damo procesu DRM kot starsa
        stars = self._xid_starsa()
        mapa_sej = Path(os.path.expanduser("~/.cache/safeer-drm"))
        mapa_sej.mkdir(parents=True, exist_ok=True)
        self.seja = tempfile.mkdtemp(prefix="seja-", dir=str(mapa_sej))
        self.stanje = os.path.join(self.seja, "events.jsonl")
        self.ukazi = os.path.join(self.seja, "command.txt")
        profil = (os.path.expanduser("~/.local/share/safeer-drm/profil") if storitev
                  else os.path.join(self.seja, "profil"))
        args = [str(exe), f"--parent={stars or 1}", f"--url={url}", f"--profile={profil}",
                f"--state={self.stanje}", f"--command={self.ukazi}"]
        if storitev:
            args.append("--storitev=1")
        if not stars:
            args = [str(exe), url]   # brez X11: lastno okno (samostojni nacin)
        if v_flatpaku():
            # --watch-bus: konca se s Safeer OS. Zaslon izrecno (kot core/os_dock.py): sicer okno Safeer DRM nastane le,
            # ce je DISPLAY v okolju aktivacije D-Bus seje (pregled paketa 14. 10. 2026).
            args = ["flatpak-spawn", "--host", "--watch-bus",
                    "--env=DISPLAY=" + os.environ.get("DISPLAY", ""),
                    "--env=WAYLAND_DISPLAY=" + os.environ.get("WAYLAND_DISPLAY", "")] + args
        elif stars:
            args.append(f"--lastnik={os.getpid()}")
        try:
            self.proces = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                           stdin=subprocess.DEVNULL, start_new_session=True)
        except OSError as e:
            print("[SafeerDRM] zagon ni uspel:", e, flush=True)
            return False
        self._odmik, self._okno = 0, 0
        self._casovnik = self.GLib.timeout_add(200, self._beri)
        self.gradnik.grab_focus()
        return True

    def ukaz(self, ime: str) -> None:
        if self.proces is None or not self.ukazi:
            return
        try:
            with open(self.ukazi, "a", encoding="utf-8") as f:   # vec ukazov hitro zapored (tipke) se ne izgubi
                f.write(ime + "\n")
        except OSError:
            pass

    _TIPKE = {"Escape": "Escape", "space": "Space", "Left": "Left", "Right": "Right", "Up": "Up", "Down": "Down",
              "Return": "Enter", "KP_Enter": "Enter", "BackSpace": "Backspace", "Home": "Home", "End": "End",
              "Page_Up": "PageUp", "Page_Down": "PageDown", "Tab": "Tab", "Delete": "Delete"}

    def tipka(self, dogodek) -> bool:
        """Tipka, ki jo dobi Safeer OS, gre v Safeer DRM (vstavljeno okno X11 tipkovnice ne dobi samo)."""
        ime = self.Gdk.keyval_name(dogodek.keyval) or ""
        koda = self._TIPKE.get(ime) or (ime if len(ime) == 1 and ime.isalnum() else "")
        if not koda or self.proces is None:
            return False
        self.ukaz("key:" + koda)
        return True

    def _beri(self) -> bool:
        if self.proces is None:
            self._casovnik = 0
            return False
        if self.proces.poll() is not None:
            self._casovnik = 0
            self._pospravi()
            if self.ob_koncu:
                self.ob_koncu()
            return False
        try:
            with open(self.stanje, "r", encoding="utf-8") as f:
                f.seek(self._odmik)
                novo = f.read()
                self._odmik = f.tell()
        except OSError:
            return True
        for vrstica in novo.splitlines():
            try:
                d = json.loads(vrstica)
            except ValueError:
                continue
            vrsta = d.get("type")
            if vrsta == "WINDOW_HANDLE" and not self._okno:
                try:
                    self._vstavi(int(str(d.get("detail") or "0")))
                except (ValueError, OSError) as e:
                    print("[SafeerDRM] vstavitev okna:", e, flush=True)
            elif vrsta in ("FULLSCREEN_ON", "FULLSCREEN_OFF") and self.ob_celozaslonu:
                self.ob_celozaslonu(vrsta == "FULLSCREEN_ON")
                self.GLib.timeout_add(300, lambda: (self._prilagodi(), False)[1])
        self._prilagodi()   # gradnik se premakne tudi brez spremembe velikosti (vrstica zavihkov skrita/prikazana)
        return True

    def _vstavi(self, okno: int) -> None:
        stars = self._xid_starsa()
        if not okno or not stars:
            return
        mesto = self._pravokotnik()
        if mesto is None:
            return
        if self._x11 is None:
            self._x11 = _X11()
        self._x11.vstavi(okno, stars, *mesto)
        self._okno, self._mesto = okno, mesto

    def _vidno(self, vidno: bool) -> None:
        if self._x11 is not None and self._okno:
            self._mesto = None
            self._x11.pokazi(self._okno, vidno)
            if vidno:
                self._prilagodi()

    def _prilagodi(self) -> None:
        if self._x11 is None or not self._okno:
            return
        mesto = self._pravokotnik()
        if mesto is None or mesto == self._mesto:
            return
        self._mesto = mesto
        self._x11.velikost(self._okno, *mesto)

    def _pospravi(self) -> None:
        if self.seja:
            shutil.rmtree(self.seja, ignore_errors=True)
        self.seja = self.stanje = self.ukazi = ""
        self._okno = 0
        self.proces = None

    def ustavi(self) -> None:
        if self._casovnik:
            self.GLib.source_remove(self._casovnik)
            self._casovnik = 0
        if self.proces is not None and self.proces.poll() is None:
            self.proces.terminate()
            try:
                self.proces.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proces.kill()
        self._pospravi()

    def unici(self) -> None:
        self.ustavi()
        if self._x11 is not None:
            self._x11.zapri()
            self._x11 = None
