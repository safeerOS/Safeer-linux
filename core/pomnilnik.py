"""Manj RAM-a za Safeer OS in Control (lastnik, 11. 10. 2026: »porabo RAM-a zmanjsaj za polovico«).

Meritev (meritve-ram/izhodisce-2026-10-11.txt): proces namizja je po nekaj urah zrasel s 143 na 466 MiB PSS, skoraj vse
anonimni pomnilnik v mnogih areanah glibc (33 niti, vsaka si vzame svojo areno in je ne vrne). Zato:

* omeji_arene(): najvec 2 areni malloc (prej do 8 x st. jeder) - fragmentacija med nitmi izgine.
* obrezuj(): gc + malloc_trim(0) vrne prazne strani sistemu; periodicno, ko program miruje.
* tlak_webkit(): spletni procesi WebKita dobijo mejo pomnilnika - nad njo WebKit sam sprosti predpomnilnike.
"""
import ctypes
import os
import ctypes.util
import gc

_M_ARENA_MAX = -8
_libc = None


def _c():
    global _libc
    if _libc is None:
        try:
            _libc = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6")
        except OSError:
            _libc = False
    return _libc or None


def omeji_arene(st: int = 2) -> bool:
    """Klici cim prej (pred nitmi). Brez glibc (drug sistem) ne naredi nic."""
    c = _c()
    if c is None or not hasattr(c, "mallopt"):
        return False
    try:
        return bool(c.mallopt(_M_ARENA_MAX, int(st)))
    except Exception:  # noqa: BLE001
        return False


def obrezuj() -> bool:
    gc.collect()
    c = _c()
    if c is None or not hasattr(c, "malloc_trim"):
        return False
    try:
        return bool(c.malloc_trim(0))
    except Exception:  # noqa: BLE001
        return False


def obrezuj_periodicno(GLib, sekunde: int = 90) -> None:
    """Na glavni niti, vsakih `sekunde`: obrezovanje traja nekaj milisekund."""
    def korak():
        obrezuj()
        return True
    GLib.timeout_add_seconds(int(sekunde), korak)


def meja_strani_mb(skupaj_mb: int = 0) -> int:
    """Koliko pomnilnika sme porabiti en proces strani, preden ga WebKit ustavi: cetrtina RAM-a, najmanj 1,5 GB,
    najvec 4 GB. Meritev 13. 10. 2026 (testni racunalnik, 12 GB): en proces strani je zrasel na ~7 GB in sistem
    je moral ubijati programe (OOM); brez meje ena pozresna stran ustavi ves racunalnik."""
    if skupaj_mb <= 0:
        try:
            skupaj_mb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") // (1024 * 1024)
        except (ValueError, OSError, AttributeError):
            skupaj_mb = 8192
    return int(min(4096, max(1536, skupaj_mb // 4)))


def meja_sprostitve_mb(skupaj_mb: int = 0) -> int:
    """Meja, nad katero WebKit procesu strani sprosti predpomnilnike (njena tretjina, "conservative") - polovica meje
    ubijanja. Prej 350 MB: WebKit je predpomnilnike praznil ze pri ~115 MB, torej pri skoraj vsaki strani; meritev
    13. 10. 2026 (testni PC, 8 strani, isti proces izmenicno): toplo LCP Splet 752 ms proti 388 ms golega WebKita,
    z mejo 1500 MB 400 ms."""
    return meja_strani_mb(skupaj_mb) // 2


def tlak_webkit(WebKit2, meja_mb: int, ubij_mb: int = 0):
    """MemoryPressureSettings za WebContext (WebKitGTK 2.34+) ali None. ubij_mb > meja_mb: nad to porabo WebKit
    proces strani ustavi (Splet ga potem nalozi znova ali pokaze razlago - os_splet._proces_koncan)."""
    try:
        s = WebKit2.MemoryPressureSettings.new()
        s.set_memory_limit(int(meja_mb))
        if ubij_mb > meja_mb:
            s.set_kill_threshold(float(ubij_mb) / float(meja_mb))
            s.set_poll_interval(5.0)    # privzeto 30 s: pozresna stran bi medtem pobrala se gigabajte (preizkus: 1,6 GB/s)
        return s
    except Exception:  # noqa: BLE001
        return None


def kontekst(WebKit2, meja_mb: int, ubij_mb: int = 0, **lastnosti):
    """Nov WebContext z mejo pomnilnika za spletne procese; brez podpore navaden WebContext."""
    s = tlak_webkit(WebKit2, meja_mb, ubij_mb)
    if s is not None:
        try:
            return WebKit2.WebContext(memory_pressure_settings=s, **lastnosti)
        except Exception:  # noqa: BLE001
            pass
    return WebKit2.WebContext(**lastnosti)


def tlak_omrezja(WebKit2, meja_mb: int) -> bool:
    """Meja pomnilnika za omrezne procese WebKita (WebKitGTK 2.34+, velja za vse, ustvarjene po klicu).

    Stresni preizkus na lastnikovem racunalniku 12. 10. 2026: omrezni proces Spleta je v 15 minutah iskanja zrasel s
    187 na 278 MiB (vse anonimni pomnilnik), en zavihek, eno okno. Nad mejo WebKit omreznemu procesu sprosti
    predpomnilnike. Klicati pred prvim pogledom WebKit v procesu."""
    s = tlak_webkit(WebKit2, meja_mb)
    if s is None:
        return False
    # WebKitGTK 6.0 (GTK4): staticna metoda je na NetworkSession; 4.1: na WebsiteDataManager.
    for razred in ("NetworkSession", "WebsiteDataManager"):
        try:
            getattr(WebKit2, razred).set_memory_pressure_settings(s)
            return True
        except Exception:  # noqa: BLE001 - starejsi WebKitGTK ali drug API
            continue
    return False


def recikliraj_omrezni(*, okno_aktivno: bool, neaktivno_s: float, prenosi: bool, nalaganje: bool,
                       zvok: bool, pss_mb: float, meja_mb: float, mirovanje_s: float = 300.0) -> bool:
    """Ali Safeer Browser sme koncati svoj omrezni proces (WebKit takoj zazene novega).

    12. 10. 2026: libsoup 3.4.4-5ubuntu0.9 pri vsaki povezavi prek posrednika (nas DoH) pusti SoupConnection, zato
    omrezni proces raste. Uporabniku to ne sme nicesar pokvariti: nikoli med uporabo okna, prenosom, nalaganjem ali
    predvajanjem zvoka, in samo nad visoko mejo (ob koncu se izgubijo piskotki seje, trajni ostanejo)."""
    if meja_mb <= 0 or okno_aktivno or prenosi or nalaganje or zvok:
        return False
    return neaktivno_s >= mirovanje_s and pss_mb >= meja_mb
