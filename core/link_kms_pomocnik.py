"""Pomocnik za zajem zaslona prek KMS (kmsgrab), edini del Safeer Linka s CAP_SYS_ADMIN.

Tece kot systemd storitev (packaging/systemd/safeer-kms.*) z DynamicUser in samo z ambientno
zmoznostjo CAP_SYS_ADMIN (brez korena). Glavni program ostane neprivilegiran: posreduje samo
velikost, sliko na sekundo, kodek in qp; ukaz ffmpeg sestavi pomocnik iz fiksnih delov in
klicatelju vrne bralni konec cevi (SCM_RIGHTS). Samo standardna knjiznica.
"""

from __future__ import annotations

import errno
import glob
import json
import os
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
from typing import List, Optional, Tuple

FFMPEG = "/usr/bin/ffmpeg"
LOGINCTL = "/usr/bin/loginctl"
NAJVEC_ZAHTEVA = 512
#: Najmanj sekund med dvema zagonoma za istega uporabnika.
PREMOR_ZAGONA_S = 1.0
#: Najvec hkratnih povezav; dodatne zavrne zanka sprejema brez niti in brez loginctl.
NAJVEC_POVEZAV = 4
#: Kako dolgo velja zadnji znani lastnik in tip aktivne seje (s), preden znova vprasamo loginctl.
PREDPOMNILNIK_SEJE_S = 2.0
#: KMS zajame fizicni zaslon mimo portala, zato samo za seje X11 (Wayland: x11grab/portal).
DOVOLJENI_TIPI_SEJE = ("x11",)
DOVOLJENI_FPS = (30, 60)
DOVOLJENI_KODEKI = {"h264": ("h264_vaapi", "high", "h264"), "hevc": ("hevc_vaapi", "main", "hevc")}
#: Najvec sekund za celo vrstico zahteve (ne za posamezen recv), da en klicatelj ne drzi mesta.
ROK_ZAHTEVE_S = 2.0
#: Zavrnitev istega uid gre v dnevnik najvec enkrat na toliko sekund (ostale se samo stejejo).
ZAVRNITEV_DNEVNIK_S = 10.0
#: Napake accept(), po katerih storitev tece naprej (zmanjka deskriptorjev, prekinjena povezava).
PREHODNE_NAPAKE_ACCEPT = (errno.EMFILE, errno.ENFILE, errno.ENOBUFS, errno.ENOMEM, errno.ECONNABORTED,
                          errno.EPROTO)

_zadnji_zagon: dict = {}
_kljucavnica = threading.Lock()
#: Zajem je rezerviran (ali tece); nastavi in preveri se v istem zaklepu (brez TOCTOU).
_zaseden = False
#: (cas, uid lastnika, tip seje) zadnje poizvedbe loginctl; uid in tip sta lahko None.
_seja: Optional[Tuple[float, Optional[int], str]] = None
#: Zadnja poizvedba loginctl, ki jo je sprozil posamezen uid (omejitev pred zagonom loginctl).
_zadnja_poizvedba: dict = {}
_kljucavnica_seje = threading.Lock()
#: uid -> (cas zadnjega izpisa zavrnitve, stevilo izpuscenih od takrat).
_zadnja_zavrnitev: dict = {}


def _kartica() -> Optional[str]:
    kartice = sorted(glob.glob("/dev/dri/card[0-9]*"))
    return kartice[0] if kartice else None


def _klicatelj(povezava: socket.socket) -> Tuple[int, int, int]:
    """(pid, uid, gid) klicatelja iz jedra (SO_PEERCRED), ne iz sporocila."""
    podatki = povezava.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    return struct.unpack("3i", podatki)


def _lastnik_aktivne_seje() -> Tuple[Optional[int], str]:
    """(UID, tip seje) uporabnika, cigar seja je ta trenutek na zaslonu (seat0)."""
    try:
        seja = subprocess.run([LOGINCTL, "show-seat", "seat0", "-p", "ActiveSession", "--value"],
                              text=True, capture_output=True, timeout=3).stdout.strip()
        if not seja:
            return None, ""
        # Brez --value: vrstice "Kljuc=vrednost", vrstni red ni pomemben.
        izpis = subprocess.run([LOGINCTL, "show-session", seja, "-p", "User", "-p", "Type"],
                               text=True, capture_output=True, timeout=3).stdout
        lastnosti = dict(v.split("=", 1) for v in izpis.splitlines() if "=" in v)
        return int(lastnosti.get("User", "")), lastnosti.get("Type", "").strip()
    except (OSError, ValueError, subprocess.SubprocessError):
        return None, ""


def _seja_za(uid: int) -> Optional[Tuple[Optional[int], str]]:
    """Lastnik in tip aktivne seje iz predpomnilnika (2 s); None = uid prepogosto sprasuje.

    loginctl se zazene samo, ko je predpomnilnik star, in najvec enkrat na PREMOR_ZAGONA_S za
    isti uid; hkratne povezave pocakajo na eno poizvedbo namesto da vsaka zazene svojo.
    """
    global _seja
    with _kljucavnica_seje:
        zdaj = time.monotonic()
        if _seja is not None and 0 <= zdaj - _seja[0] < PREDPOMNILNIK_SEJE_S:
            return _seja[1], _seja[2]
        if zdaj - _zadnja_poizvedba.get(uid, -PREMOR_ZAGONA_S) < PREMOR_ZAGONA_S:
            return None
        _zadnja_poizvedba[uid] = zdaj
        lastnik, tip = _lastnik_aktivne_seje()
        _seja = (time.monotonic(), lastnik, tip)
        return lastnik, tip


def _seja_med_zajemom() -> Tuple[Optional[int], str]:
    """Lastnik in tip aktivne seje med tekocim zajemom: predpomnilnik ali nova poizvedba.

    Brez omejitve na uid (kot v _seja_za): zajem ze tece in preverba je namenjena prav temu, da ga
    ustavimo; klicatelj je ne more sprozati pogosteje kot enkrat na krog zanke zajema.
    """
    global _seja
    with _kljucavnica_seje:
        zdaj = time.monotonic()
        if _seja is not None and 0 <= zdaj - _seja[0] < PREDPOMNILNIK_SEJE_S:
            return _seja[1], _seja[2]
        lastnik, tip = _lastnik_aktivne_seje()
        _seja = (time.monotonic(), lastnik, tip)
        return lastnik, tip


def _zavrnitev_v_dnevnik(uid: int, besedilo: str) -> None:
    """Izpis zavrnitve najvec enkrat na ZAVRNITEV_DNEVNIK_S za isti uid (vticnik je 0666)."""
    with _kljucavnica:
        zdaj = time.monotonic()
        cas, izpusceno = _zadnja_zavrnitev.get(uid, (None, 0))
        if cas is not None and 0 <= zdaj - cas < ZAVRNITEV_DNEVNIK_S:
            _zadnja_zavrnitev[uid] = (cas, izpusceno + 1)
            return
        _zadnja_zavrnitev[uid] = (zdaj, 0)
    if izpusceno:
        besedilo += " (izpuscenih %d)" % izpusceno
    print(besedilo, flush=True)


def preveri_zahtevo(zahteva: object) -> Optional[dict]:
    """Samo cela stevila v mejah in kodek s seznama; vse drugo zavrne."""
    if not isinstance(zahteva, dict) or set(zahteva) != {"w", "h", "fps", "kodek", "qp"}:
        return None
    w, h, fps, qp, kodek = zahteva["w"], zahteva["h"], zahteva["fps"], zahteva["qp"], zahteva["kodek"]
    if not all(type(v) is int for v in (w, h, fps, qp)):
        return None
    if not (320 <= w <= 3840 and 240 <= h <= 2160 and w % 2 == 0 and h % 2 == 0):
        return None
    if fps not in DOVOLJENI_FPS or not 10 <= qp <= 40 or kodek not in DOVOLJENI_KODEKI:
        return None
    return {"w": w, "h": h, "fps": fps, "qp": qp, "kodek": kodek}


def ukaz_kms(z: dict, kartica: str, ffmpeg: str = FFMPEG) -> List[str]:
    """Fiksni ukaz: kmsgrab -> VAAPI (brez kopije v pomnilnik) -> h264/hevc na stdout."""
    kodirnik, profil, oblika = DOVOLJENI_KODEKI[z["kodek"]]
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-device", kartica, "-f", "kmsgrab", "-framerate", str(z["fps"]), "-i", "-",
            "-vf", "hwmap=derive_device=vaapi,scale_vaapi=w=%d:h=%d:format=nv12" % (z["w"], z["h"]),
            "-c:v", kodirnik, "-profile:v", profil, "-rc_mode", "CQP", "-qp", str(z["qp"]),
            "-g", str(z["fps"]), "-bf", "0", "-f", oblika, "-"]


def _odgovori(povezava: socket.socket, besedilo: str) -> None:
    try:
        povezava.sendall(besedilo.encode("utf-8") + b"\n")
    except OSError:
        pass


def _beri_vrstico(povezava: socket.socket) -> bytes:
    zbrano = b""
    # Rok velja za celo vrstico: po en bajt tik pred iztekom recv bi sicer drzal mesto ~16 min.
    konec = time.monotonic() + ROK_ZAHTEVE_S
    while len(zbrano) < NAJVEC_ZAHTEVA and not zbrano.endswith(b"\n"):
        ostane = konec - time.monotonic()
        if ostane <= 0:
            raise socket.timeout("zahteva prepocasna")     # OSError: ujame ga obdelaj
        povezava.settimeout(ostane)
        kos = povezava.recv(NAJVEC_ZAHTEVA - len(zbrano))
        if not kos:
            break
        zbrano += kos
    return zbrano


def _prepogosto(uid: int, zdaj: float) -> bool:
    return zdaj - _zadnji_zagon.get(uid, -PREMOR_ZAGONA_S) < PREMOR_ZAGONA_S


def obdelaj(povezava: socket.socket) -> None:
    global _zaseden
    proces = None
    rezervirano = False
    try:
        povezava.settimeout(2)
        pid, uid, _ = _klicatelj(povezava)
        # Hitra zavrnitev brez loginctl; dokoncno se preveri ob rezervaciji spodaj.
        with _kljucavnica:
            if _prepogosto(uid, time.monotonic()):
                _odgovori(povezava, "napaka: prepogosto")
                return
        seja = _seja_za(uid)
        if seja is None:
            _odgovori(povezava, "napaka: prepogosto")
            return
        lastnik, tip = seja
        if uid != lastnik:
            _zavrnitev_v_dnevnik(uid, "kms: zavrnjeno uid=%d pid=%d (ni aktivna seja)" % (uid, pid))
            _odgovori(povezava, "napaka: ni aktivna seja")
            return
        if tip not in DOVOLJENI_TIPI_SEJE:
            # Klicatelj (odpri_kms) na vsak odgovor brez "ok" preklopi na x11grab.
            _zavrnitev_v_dnevnik(uid, "kms: zavrnjeno uid=%d pid=%d (seja %s)" % (uid, pid, tip or "?"))
            _odgovori(povezava, "napaka: seja %s (kms samo x11)" % (tip or "neznana"))
            return
        try:
            z = preveri_zahtevo(json.loads(_beri_vrstico(povezava).decode("utf-8")))
        except ValueError:
            z = None
        povezava.settimeout(2)          # _beri_vrstico je pustil ostanek roka (lahko skoraj 0)
        kartica = _kartica()
        if z is None or kartica is None:
            _odgovori(povezava, "napaka: zahteva")
            return
        # Premor in "zajem ze tece" se preverita in rezervirata v istem zaklepu, sele po
        # uspesni preverbi zahteve (neveljavna zahteva ne porabi premora).
        with _kljucavnica:
            zdaj = time.monotonic()
            if _prepogosto(uid, zdaj):
                _odgovori(povezava, "napaka: prepogosto")
                return
            if _zaseden:
                _odgovori(povezava, "napaka: zajem ze tece")
                return
            _zaseden = rezervirano = True
            _zadnji_zagon[uid] = zdaj
        bralni, pisalni = os.pipe()
        try:
            proces = subprocess.Popen(ukaz_kms(z, kartica), stdin=subprocess.DEVNULL, stdout=pisalni,
                                      stderr=subprocess.DEVNULL, close_fds=True,
                                      env={"PATH": "/usr/bin:/bin"})
        finally:
            os.close(pisalni)
        print("kms: zajem uid=%d pid=%d %dx%d@%d %s" % (uid, pid, z["w"], z["h"], z["fps"], z["kodek"]),
              flush=True)
        try:
            socket.send_fds(povezava, [b"ok\n"], [bralni])
        finally:
            os.close(bralni)
        # Zajem tece, dokler klicatelj ne zapre vticnika, se ffmpeg ne konca ali seja ni vec njegova:
        # kmsgrab zajame fizicni zaslon, po menjavi uporabnika (ali na Wayland) bi zajemal tujega.
        povezava.settimeout(1.0)
        while proces.poll() is None:
            try:
                if not povezava.recv(64):
                    break
            except socket.timeout:
                pass
            lastnik, tip = _seja_med_zajemom()
            if lastnik != uid or tip not in DOVOLJENI_TIPI_SEJE:
                print("kms: zajem ustavljen uid=%d pid=%d (seja ni vec njegova)" % (uid, pid), flush=True)
                break
    except OSError:
        pass
    finally:
        if proces is not None and proces.poll() is None:
            proces.send_signal(signal.SIGTERM)
            try:
                proces.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proces.kill()
                try:
                    proces.wait(timeout=3)      # pobere proces, da ne ostane zombi
                except subprocess.TimeoutExpired:
                    pass
        if rezervirano:
            with _kljucavnica:
                _zaseden = False
        try:
            povezava.close()
        except OSError:
            pass


def _obdelaj_omejeno(povezava: socket.socket, povezave: threading.BoundedSemaphore) -> None:
    try:
        obdelaj(povezava)
    finally:
        povezave.release()


def main() -> int:
    # systemd socket activation: poslusajoci vticnik je fd 3 (LISTEN_FDS=1).
    if os.environ.get("LISTEN_FDS") != "1" or os.environ.get("LISTEN_PID") != str(os.getpid()):
        print("kms: zagnati prek safeer-kms.socket", file=sys.stderr)
        return 2
    _sprejemaj(socket.socket(fileno=3))
    return 0


def _sprejemaj(posluh: socket.socket) -> None:
    """Zanka sprejema; prehodna napaka accept() ne konca storitve (in z njo vseh tekocih zajemov)."""
    povezave = threading.BoundedSemaphore(NAJVEC_POVEZAV)
    zadnja_napaka = None
    while True:
        try:
            povezava, _ = posluh.accept()
        except OSError as napaka:
            if napaka.errno not in PREHODNE_NAPAKE_ACCEPT:
                raise
            if napaka.errno != zadnja_napaka:       # en izpis na niz enakih napak
                print("kms: accept %s" % errno.errorcode.get(napaka.errno, "?"), file=sys.stderr, flush=True)
            zadnja_napaka = napaka.errno
            time.sleep(0.1)
            continue
        zadnja_napaka = None
        if not povezave.acquire(blocking=False):
            povezava.settimeout(0.2)
            _odgovori(povezava, "napaka: zasedeno")
            povezava.close()
            continue
        try:
            threading.Thread(target=_obdelaj_omejeno, args=(povezava, povezave), name="kms",
                             daemon=True).start()
        except RuntimeError:
            povezave.release()
            povezava.close()


if __name__ == "__main__":
    sys.exit(main())
