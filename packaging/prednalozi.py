#!/usr/bin/env python3
"""Prednalaganje Safeer Browserja (.deb) po prijavi: nas WebKitGTK in koda brskalnika v predpomnilnik strani, da je prvi
zagon po prijavi tako hiter kot vsak naslednji.

Nas WebKitGTK (paket safeer-webkit, /usr/lib/safeer-webkit, ~135 MiB): po zagonu racunalnika ga ni v predpomnilniku strani,
zato prvi zagon brskalnika bere knjiznice z diska po kosih (napake strani). Meritev 18. 10. 2026 (testni PC i5-4590,
SATA SSD, Safeer Browser 1.0.127~pred13, cas od zagona do prvega izrisa lokalne strani, mediana [razpon]):
toplo 0,93 s [0,88-1,18] (n=6), hladno 1,30 s [1,29-1,73] (n=9), po tem prednalaganju 0,92 s [0,91-0,93] (n=3),
prednalaganje hkrati z zagonom 1,01 s [0,98-1,32] (n=6). Prednalaganje prebere 150 MiB v 0,50 s.

Zagon: /etc/xdg/autostart/safeer-browser-prednalaganje.desktop ob prijavi. Da ne tekmuje z zagonom namizja, pocaka
ZAMIK sekund in bere z najnizjo prioriteto V/I (razred idle) in procesorja. Nic ne naredi, ce brskalnik ze tece, ce ga
uporabnik ni uporabil v zadnjih NEUPORABA_DNI dneh (nastavitve se niso spremenile) ali ce je prostega pomnilnika malo
(predpomnilnik strani je sicer sproscljiv, a na tesnem sistemu ne izpodrinemo drugih podatkov).
"""
import ctypes
import os
import sys
import time

KOREN = "/usr/lib/safeer-browser"
#: Mape in datoteke, ki jih brskalnik prebere ob zagonu (Safeer DRM ne: nalozi se sele ob zasciteni vsebini).
VSEBINA = ("core", "ui", "assets", "safeer_brskalnik.py", "packaging")
#: Skupni WebKit (paket safeer-webkit) ob mapi programa; ce ga ni, mapa webkit v programu (paketi do 1.0.127~pred).
WEBKIT = ("../safeer-webkit", "webkit")
ZAMIK = 60
NEUPORABA_DNI = 14
NAJMANJ_PROSTEGA_MIB = 1024


def prosto_mib() -> int:
    try:
        with open("/proc/meminfo", encoding="ascii") as f:
            for v in f:
                if v.startswith("MemAvailable:"):
                    return int(v.split()[1]) // 1024
    except (OSError, ValueError):
        pass
    return 0


def brskalnik_tece() -> bool:
    vstop = os.path.join(KOREN, "safeer_brskalnik.py").encode()
    for p in os.listdir("/proc"):
        if p.isdigit():
            try:
                with open("/proc/%s/cmdline" % p, "rb") as f:
                    if vstop in f.read():
                        return True
            except OSError:
                continue
    return False


def nedavno_uporabljen(zdaj: float = 0.0) -> bool:
    """Nastavitve brskalnika (skupne .deb in Flatpaku, core/config.py) so se spremenile v zadnjih NEUPORABA_DNI dneh."""
    mapa = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "safeer-mint")
    try:
        cas = max(os.stat(os.path.join(mapa, ime)).st_mtime for ime in os.listdir(mapa))
    except (OSError, ValueError):
        return False
    return (zdaj or time.time()) - cas < NEUPORABA_DNI * 86400


def nizka_prioriteta() -> None:
    try:
        os.nice(19)
    except OSError:
        pass
    try:
        # ioprio_set(IOPRIO_WHO_PROCESS, 0, IOPRIO_CLASS_IDLE << 13); 251 = x86_64 (paket je amd64).
        ctypes.CDLL(None, use_errno=True).syscall(251, 1, 0, 3 << 13)
    except (OSError, AttributeError):
        pass


def webkit(koren: str = KOREN) -> str:
    for ime in WEBKIT:
        pot = os.path.normpath(os.path.join(koren, ime))
        if os.path.isdir(pot):
            return pot
    return ""


def datoteke(koren: str = KOREN):
    for pot in [webkit(koren)] + [os.path.join(koren, ime) for ime in VSEBINA]:
        if not pot:
            continue
        if os.path.isfile(pot) and not os.path.islink(pot):
            yield pot
        for k, _mape, dd in os.walk(pot):
            for d in dd:
                p = os.path.join(k, d)
                if os.path.isfile(p) and not os.path.islink(p):
                    yield p


def prednalozi(koren: str = KOREN) -> tuple:
    """Prebere datoteke (kot je bilo izmerjeno): vrne (stevilo datotek, bajtov)."""
    n = b = 0
    for p in datoteke(koren):
        try:
            with open(p, "rb", buffering=0) as f:
                while True:
                    kos = f.read(1 << 20)
                    if not kos:
                        break
                    b += len(kos)
            n += 1
        except OSError:
            continue
    return n, b


def main(argv) -> int:
    nizka_prioriteta()
    if "--zdaj" not in argv:
        time.sleep(ZAMIK)
    if brskalnik_tece() or not nedavno_uporabljen() or prosto_mib() < NAJMANJ_PROSTEGA_MIB:
        return 0
    t = time.monotonic()
    n, b = prednalozi()
    print("safeer-browser: prednalozeno %d datotek, %.0f MiB, %.2f s" % (n, b / 1048576, time.monotonic() - t))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
