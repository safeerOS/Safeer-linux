"""Profil kakovosti oddaljenega zaslona po IZMERJENIH razmerah (lastnik 25. 10. 2026: »boljse kot TeamViewer«).

Kakovost in kodek izbere RACUNALNIK, ko se gledalec poveze (sele takrat je pot znana; pravilo kroga 116). Nova merila:
  * pot: neposredno (LAN) ali prek sredisca (Global Link) - po tem, kje je gledalec prisel;
  * vmesnik tega racunalnika proti gledalcu (`ip route get`): zicni (ethernet) ali brezzicni, hitrost povezave
    (/sys/class/net/<vmesnik>/speed, Mb/s) - izmerjeno, ne ugibano;
  * omrezje gledalca, kot ga pove sam (`net`: ethernet, wifi, 5g, 4g ...);
  * zamik TCP takoj po povezavi (TCP_INFO rtt).

Profili:
  * ``lan_zicno``  - neposredno, oba konca zicno, povezava >= 1 Gb/s, zamik < 3 ms: IZVORNA locljivost in, ce
    gledalec to zna (`brezizgubno`), brezizgubno H.264 RGB (libx264rgb qp 0): mirna slika in drsenje sta pikselsko
    enaka izvoru (izmerjeno 25. 10. 2026: SSIM 1,0, 0 razlicnih pikslov, 11,5 Mb/s mirno, 18,8 Mb/s drsenje 2560x1440).
  * ``lan``        - neposredno, kaj drugega (Wi-Fi): izvorna locljivost, HEVC 4:4:4 na graficni, ce ga gledalec zna
    (`444` + kodek hevc; izmerjeno SSIM 0,997), sicer H.264 kot doslej.
  * ``zdoma``      - prek sredisca: kot doslej (kakovost_za_pot, 1080p, HEVC samo, ce ga gledalec ponudi).

Ta modul je cist (brez omrezja, razen branja /sys in `ip route get` v lokalno_omrezje); preizkusi:
tests/test_link_zaslon_profil.py.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Iterable, Optional

#: Zmoznosti gledalca (caps v screen.start).
IZVORNA = "izvorna"          # gledalec prikaze 1:1 in sam kakovostno pomanjsa, ko je okno manjse
BREZIZGUBNO = "brezizgubno"  # gledalec dekodira H.264 High 4:4:4 Predictive (RGB, brezizgubno; libavcodec/PyAV)
HEVC444 = "444"              # gledalec dekodira HEVC Main 4:4:4 (RExt)
PROFIL = "profil"            # gledalec pokaze vrstico s profilom (glava toka "profil")

LAN_ZICNO, LAN, ZDOMA = "lan_zicno", "lan", "zdoma"
#: Pogoji za zicni LAN: hitrost povezave tega racunalnika in najvecji zamik TCP ob povezavi.
NAJMANJ_MBPS = 1000
NAJVEC_RTT_MS = 3.0
#: Najvecja locljivost, ki jo posljemo v izvorni velikosti (vecji zaslon se pomanjsa).
IZVORNA_NAJVEC = (3840, 2160)


def _vrsta_vmesnika(ime: str, koren: str = "/sys/class/net") -> dict:
    pot = os.path.join(koren, ime)
    if not ime or not os.path.isdir(pot):
        return {"vmesnik": ime, "vrsta": "", "hitrost_mbps": 0}
    if os.path.isdir(os.path.join(pot, "wireless")) or os.path.isdir(os.path.join(pot, "phy80211")):
        vrsta = "wifi"
    elif ime == "lo":
        vrsta = "lo"
    else:
        vrsta = "ethernet"
    hitrost = 0
    try:
        with open(os.path.join(pot, "speed"), encoding="ascii") as d:
            hitrost = max(0, int(d.read().strip() or 0))
    except (OSError, ValueError):
        hitrost = 0
    return {"vmesnik": ime, "vrsta": vrsta, "hitrost_mbps": hitrost}


def lokalno_omrezje(naslov: str, zazeni=subprocess.run, koren: str = "/sys/class/net") -> dict:
    """Vmesnik tega racunalnika proti `naslov` (ip route get) in njegova vrsta/hitrost. Prazno, ce ne vemo."""
    if not naslov:
        return {"vmesnik": "", "vrsta": "", "hitrost_mbps": 0}
    try:
        r = zazeni(["ip", "-j", "route", "get", str(naslov)], capture_output=True, text=True, timeout=2)
        poti = json.loads(r.stdout or "[]") if getattr(r, "returncode", 1) == 0 else []
        ime = str((poti[0] if poti else {}).get("dev") or "")
    except (OSError, subprocess.SubprocessError, ValueError, AttributeError, IndexError):
        ime = ""
    return _vrsta_vmesnika(ime, koren)


def izberi(prek_huba: bool, omrezje_gledalca: str, lokalno: dict, rtt_ms: Optional[float],
           zmoznosti: Iterable[str], hevc444: bool = False) -> dict:
    """Profil seje: ime, pot, omrezje, hitrost, zamik, kodek ("h264rgb", "hevc444" ali "" = kot doslej), izvorna."""
    zm = {str(z) for z in (zmoznosti or [])}
    gledalec = str(omrezje_gledalca or "").strip().lower()
    vrsta = str((lokalno or {}).get("vrsta") or "")
    hitrost = int((lokalno or {}).get("hitrost_mbps") or 0)
    rtt = round(float(rtt_ms), 2) if isinstance(rtt_ms, (int, float)) and rtt_ms >= 0 else None
    if prek_huba:
        ime = ZDOMA
    elif (vrsta == "ethernet" and gledalec == "ethernet" and hitrost >= NAJMANJ_MBPS
          and (rtt is None or rtt < NAJVEC_RTT_MS)):
        ime = LAN_ZICNO
    else:
        ime = LAN
    kodek = ""
    if ime == LAN_ZICNO and BREZIZGUBNO in zm:
        kodek = "h264rgb"
    elif ime in (LAN_ZICNO, LAN) and HEVC444 in zm and hevc444:
        kodek = "hevc444"
    return {"ime": ime, "pot": "sredisce" if prek_huba else "neposredno",
            "omrezje": vrsta if not prek_huba else (gledalec or ""), "omrezje_gledalca": gledalec,
            "hitrost_mbps": hitrost if not prek_huba else 0, "rtt_ms": rtt, "kodek": kodek,
            "izvorna": IZVORNA in zm and ime != ZDOMA}


def velikost(izvor: tuple, profil: dict, privzeto: tuple) -> tuple:
    """Velikost slike: izvorna (do IZVORNA_NAJVEC) za gledalca, ki zna 1:1 v LAN, sicer `privzeto` (stara meja)."""
    sirina, visina = (IZVORNA_NAJVEC if profil.get("izvorna") else privzeto)
    s, v = int(izvor[0]), int(izvor[1])
    if s <= 0 or v <= 0:
        return int(privzeto[0]), int(privzeto[1])
    merilo = min(sirina / float(s), visina / float(v), 1.0)
    return max(2, int(s * merilo) // 2 * 2), max(2, int(v * merilo) // 2 * 2)


def ukaz_brezizgubno(ffmpeg: str, display: str, sirina: int, visina: int, fps: int, odmik: tuple = (0, 0),
                     kazalec_v_sliki: bool = True, gop: int = 0) -> list:
    """Brezizgubni zajem: x11grab -> libx264rgb qp 0 (RGB, brez pretvorbe v YUV, zato pikselsko enako izvoru).

    ultrafast + zerolatency (rezinske niti, brez cakanja na naslednje slike); CAVLC (ultrafast) gledalec dekodira
    hitreje kot CABAC. Kljucna slika redko (mirna slika ne stane nic), brez B-slik. Brez pomanjsave (izvorna)."""
    izvor = display + ("+%d,%d" % (int(odmik[0]), int(odmik[1])) if tuple(odmik) != (0, 0) else "")
    return [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin",
            "-f", "x11grab", "-draw_mouse", "1" if kazalec_v_sliki else "0", "-framerate", str(fps),
            "-video_size", "%dx%d" % (sirina, visina), "-i", izvor,
            "-vf", "format=bgr0", "-c:v", "libx264rgb", "-preset", "ultrafast", "-tune", "zerolatency", "-qp", "0",
            "-g", str(gop if gop > 0 else fps * 10), "-bf", "0", "-flags", "+low_delay", "-f", "h264", "-"]


def opis(profil: dict, sirina: int, visina: int, fps: int, navidezno: bool = False, merilo: float = 1.0) -> str:
    """Kratka vrstica za dnevnik in gledalca, ki ne sestavi svoje (lastnik 25. 10. 2026: »LAN · 1 Gb/s · neposredno ·
    navidezno namizje · locljivost · fps«). Navidezno namizje pove tudi DPI, ce ni 96 (merilo gledalca)."""
    deli = []
    ime = profil.get("ime")
    deli.append("Global Link" if ime == ZDOMA else ("LAN" if profil.get("omrezje") == "ethernet" else
                                                    ("Wi-Fi" if profil.get("omrezje") == "wifi" else "LAN")))
    h = int(profil.get("hitrost_mbps") or 0)
    if h:
        deli.append("%s Gb/s" % (h // 1000) if h >= 1000 and h % 1000 == 0 else "%d Mb/s" % h)
    deli.append("neposredno" if profil.get("pot") == "neposredno" else "prek središča")
    if navidezno:
        deli.append("navidezno namizje")
    deli.append("%d×%d" % (int(sirina), int(visina)))
    try:
        dpi = int(round(96 * float(merilo)))
    except (TypeError, ValueError):
        dpi = 96
    if navidezno and dpi != 96:
        deli.append("%d DPI" % dpi)
    deli.append("%d fps" % int(fps))
    if profil.get("kodek") == "h264rgb":
        deli.append("brezizgubno")
    elif profil.get("kodek") == "hevc444":
        deli.append("4:4:4")
    return " · ".join(deli)
