"""Safeer Shell: lupina namizja (QML) v svojem procesu - Python + PySide6, brez Gtk in WebKit.

Lastnik, 18. 10. 2026 (moznost B): sesutje ali zamrznitev Safeer OS (Medijski center, GStreamer, WebKit, Python) ne
sme podreti namizja. Ta proces pokaze isto namizje kot prej (assets/os/qml/Namizje.qml, os_lupina.Namizje: okno pod
vsemi okni, robovi pulta, dock, zasloni), klice pa poslje Safeer OS prek vticnice (core/lupina_most.py). Zazene ga
varuh (core/varuh_procesov.py), ki ga ob sesutju ali zamrznitvi (utrip WATCHDOG=1) zazene znova.

Ko Safeer OS ni na voljo (se znova zaganja), namizje dela naprej: ozadje, ura, iskanje po zgodovini, zaganjalnik
programov sistema (»zazeni« - tu, brez Safeer OS). Pripomocki, ki rabijo Safeer OS, dobijo dogodek »osStanje« in
namizje pokaze »Safeer OS se znova zaganja« (assets/os/besedila-namizja.js, 6 jezikov). Klici, ki pridejo med tem,
pocakajo (najvec CAKANJE_KLICA_S) in gredo Safeer OS, ko je spet na voljo - klik na Splet med ponovnim zagonom se zgodi.
"""
from __future__ import annotations

import os
import sys

if __name__ == "__main__" and not __package__:
    sys.path[0] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

import random
import socket
import time
from typing import Any, Dict, List, Optional, Tuple

from core import lupina_most, os_lupina, varuh_procesov

#: Klic, ki pride, ko Safeer OS ni povezan, caka najvec toliko; potem odgovor z napako (star klik se ne izvede pozneje).
CAKANJE_KLICA_S = 30
#: Ob prvem zagonu (prijava) se Safeer OS sele zaganja: obvestilo sele po toliko sekundah brez povezave.
PRVI_ZAGON_S = 6
PONOVNO_MS = 500
NAPAKA_OS = "safeerOsSeZaganja"


def zazeni_lokalno(oznaka: str) -> bool:
    """Program sistema (vnos .desktop) brez Safeer OS - isto kot os_programi.Programi.zazeni (gio launch, v Flatpaku na
    gostitelju), le brez beleženja uporabe, ki je v Safeer OS."""
    import shutil
    import subprocess
    ime = str(oznaka or "")
    if "/" in ime or not ime.endswith(".desktop"):
        return False
    from core import gostitelj, link_programi, zasebni_webkit
    for mapa in link_programi._mape_vnosov():
        pot = os.path.join(mapa, ime)
        if not os.path.isfile(pot):
            continue
        if gostitelj.v_flatpaku():
            return gostitelj.zazeni_vnos(pot)
        gio = shutil.which("gio")
        if not gio:
            return False
        try:
            subprocess.Popen([gio, "launch", pot], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, start_new_session=True, env=zasebni_webkit.okolje_za_zunanje())
            return True
        except OSError:
            return False
    return False


class Odjemalec:
    """Povezava lupine s Safeer OS: klici, odgovori, dogodki; ponovna povezava; stanje za obvestilo na namizju."""

    def __init__(self, lupina: "LupinaProces", pot: str) -> None:
        self.lupina = lupina
        self.pot = pot
        self.sock: Optional[socket.socket] = None
        self._dekoder = lupina_most.Dekoder()
        self._izhod = bytearray()
        self._branje = None
        self._pisanje = None
        # Id-ji na zici: id QML + zamik tega procesa. Odgovor na klic prejsnje lupine (nit ozadja v Safeer OS) zato ne
        # more zadeti klica nove lupine z istim stevilom.
        self._zamik = random.randint(1 << 24, 1 << 30)
        self._caka: Dict[int, Tuple[str, float]] = {}
        self._vrsta: List[Tuple[int, str, list, float]] = []
        self._bila_povezava = False
        self._zacetek = time.monotonic()
        self._stanje: Optional[str] = None
        self._casovnik = None

    # ------------------------------------------------------------------ povezava
    def zacni(self) -> None:
        from PySide6.QtCore import QTimer
        self._casovnik = QTimer()
        self._casovnik.setInterval(PONOVNO_MS)
        self._casovnik.timeout.connect(self._ob_casovniku)
        self._casovnik.start()
        self._poskusi()

    def povezan(self) -> bool:
        return self.sock is not None

    def _poskusi(self) -> bool:
        if self.sock is not None:
            return True
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM | socket.SOCK_CLOEXEC)
        try:
            s.settimeout(1.0)
            s.connect(self.pot)
        except OSError:
            s.close()
            return False
        if not lupina_most.nas_sogovornik(s):
            s.close()
            return False
        s.setblocking(False)
        self._povezi(s)
        return True

    def _povezi(self, s: socket.socket) -> None:
        from PySide6.QtCore import QSocketNotifier
        self.sock = s
        self._dekoder = lupina_most.Dekoder()
        self._izhod = bytearray()
        self._branje = QSocketNotifier(s.fileno(), QSocketNotifier.Type.Read)
        self._branje.activated.connect(lambda *_a: self._beri())
        self._pisanje = QSocketNotifier(s.fileno(), QSocketNotifier.Type.Write)
        self._pisanje.setEnabled(False)
        self._pisanje.activated.connect(lambda *_a: self._pisi())
        self._poslji(lupina_most.zdravo(self.lupina.zdravo()))
        ponovno = self._bila_povezava
        self._bila_povezava = True
        zdaj = time.monotonic()
        vrsta, self._vrsta = self._vrsta, []
        for klic_id, metoda, a, cas in vrsta:
            if zdaj - cas > CAKANJE_KLICA_S:
                self._odgovori(klic_id, False, NAPAKA_OS)
            else:
                self._poslji_klic(klic_id, metoda, a, cas)
        self._nastavi_stanje("", ponovno)
        if self._casovnik is not None:
            self._casovnik.stop()

    def _prekinjeno(self) -> None:
        for n in (self._branje, self._pisanje):
            if n is not None:
                n.setEnabled(False)
                n.deleteLater()
        self._branje = self._pisanje = None
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None
        self._izhod = bytearray()
        # Klici, na katere Safeer OS ni odgovoril (sesul se je med delom), dobijo napako - QML ne caka v nedogled.
        caka, self._caka = self._caka, {}
        for klic_id in caka:
            self._odgovori(klic_id, False, NAPAKA_OS)
        self._ob_casovniku()
        if self._casovnik is not None:
            self._casovnik.start()

    def _ob_casovniku(self) -> None:
        if self._poskusi():
            return
        zdaj = time.monotonic()
        ostanejo = []
        for klic_id, metoda, a, cas in self._vrsta:
            if zdaj - cas > CAKANJE_KLICA_S:
                self._odgovori(klic_id, False, NAPAKA_OS)
            else:
                ostanejo.append((klic_id, metoda, a, cas))
        self._vrsta = ostanejo
        self._nastavi_stanje(self.stanje_brez_povezave(zdaj))

    def stanje_brez_povezave(self, zdaj: float) -> str:
        """Kaj namizje pove, dokler Safeer OS ni povezan: varuh ve, ali caka na pomnilnik ali je odnehal."""
        os_stanje = ((lupina_most.beri_stanje_varuha().get("procesi") or {}).get("safeer-os") or {}).get("stanje")
        if os_stanje in ("pomnilnik", "obupal"):
            return os_stanje
        if self._bila_povezava:
            return "znova"
        return "zaganja" if zdaj - self._zacetek >= PRVI_ZAGON_S else ""

    def _nastavi_stanje(self, stanje: str, ponovno: bool = False) -> None:
        if stanje == self._stanje and not ponovno:
            return
        self._stanje = stanje
        self.lupina.dogodek("osStanje", {"stanje": stanje, "ponovno": bool(ponovno)})

    # ------------------------------------------------------------------ klici
    def klic(self, klic_id: int, metoda: str, a: list) -> None:
        if metoda == "varuhZnova":
            # Gumb »Zazeni znova« (varuh je odnehal): varuh poskusi znova.
            self._odgovori(klic_id, varuh_procesov.obvesti("SAFEER_ZNOVA=1"), None)
            return
        if self.sock is not None:
            self._poslji_klic(klic_id, metoda, a, time.monotonic())
            return
        if metoda == "zazeni":
            # Programi sistema se zazenejo tudi brez Safeer OS (lastnik: zaganjalnik dela naprej).
            self._odgovori(klic_id, zazeni_lokalno(str(a[0]) if a else ""), None)
            return
        self._vrsta.append((klic_id, metoda, list(a), time.monotonic()))

    def _poslji_klic(self, klic_id: int, metoda: str, a: list, cas: float) -> None:
        self._caka[klic_id] = (metoda, cas)
        self._poslji(lupina_most.klic(klic_id + self._zamik, metoda, a))

    def _odgovori(self, klic_id: int, ok: bool, podatki: Any) -> None:
        self.lupina.most.odgovor.emit(int(klic_id), bool(ok), lupina_most.besedilo_json(podatki))

    # ------------------------------------------------------------------ branje in pisanje
    def _beri(self) -> None:
        s = self.sock
        if s is None:
            return
        okvirji = []
        while True:
            try:
                podatki = s.recv(262144)
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                podatki = b""
            if not podatki:
                self._prekinjeno()
                break
            try:
                okvirji += self._dekoder.dodaj(podatki)
            except lupina_most.PrevelikOkvir:
                self._prekinjeno()
                break
        for vrsta, telo in okvirji:
            try:
                self._okvir(*lupina_most.razcleni(vrsta, telo))
            except (ValueError, KeyError) as e:
                print("[Safeer lupina] okvir:", e, flush=True)

    def _okvir(self, ime: str, vsebina) -> None:
        most = self.lupina.most
        if ime == "O":
            klic_id, ok, besedilo = vsebina
            klic_id -= self._zamik
            if self._caka.pop(klic_id, None) is not None:
                most.odgovor.emit(int(klic_id), bool(ok), besedilo)
        elif ime == "D":
            most.dogodek.emit(vsebina[0], vsebina[1])
        elif ime == "U" and isinstance(vsebina, dict):
            if vsebina.get("u") == "aktiviraj":
                self.lupina.okno.requestActivate()

    def _poslji(self, okvir: bytes) -> None:
        if self.sock is None:
            return
        self._izhod += okvir
        self._pisi()

    def _pisi(self) -> None:
        s = self.sock
        while s is not None and self._izhod:
            try:
                n = s.send(self._izhod)
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                self._prekinjeno()
                return
            del self._izhod[:n]
        if self._pisanje is not None:
            self._pisanje.setEnabled(bool(self._izhod))


class LupinaProces(os_lupina.Namizje):
    """Isto namizje kot os_lupina.Namizje (okno, zasloni, dock, robovi), klici pa gredo Safeer OS prek vticnice."""

    def __init__(self, pot: Optional[str] = None) -> None:
        # Odjemalec pred QML: Component.onCompleted ze ob nalaganju poklice »zacetek« (pocaka v vrsti do povezave).
        self.odjemalec = Odjemalec(self, pot or lupina_most.pot_vticnice())
        super().__init__(None)

    def _spremljaj_temo(self) -> None:
        pass        # temo in velikost besedila spremlja Safeer OS (Gio) in poslje dogodek »videz«

    def _gibanje_ob_zagonu(self) -> bool:
        # Brez Gio v tem procesu (+7 MB): zmanjsano gibanje pove Safeer OS v odgovoru »zacetek« (videz.gibanje) takoj po
        # povezavi; QML vstop panelov takrat konca (Namizje.qml uporabiVidez).
        return True

    def klic(self, klic_id: int, metoda: str, a: list) -> None:
        self.odjemalec.klic(klic_id, metoda, a)

    def zdravo(self) -> dict:
        try:
            from PySide6.QtGui import QGuiApplication
            platforma = QGuiApplication.platformName()
        except Exception:  # noqa: BLE001
            platforma = ""
        return {"pid": os.getpid(), "razmerje": self._razmerje_zaslona(), "platforma": platforma}


def main() -> int:
    import faulthandler
    import signal
    varuh_procesov.pripravi_obvestila()          # NOTIFY_SOCKET ne gre naprej programom, ki jih zazenemo
    # Sled vseh niti ob SIGABRT varuha (zamrznitev) ali sesutju v knjiznici C - stderr je sled.log (varuh).
    faulthandler.enable(all_threads=True)
    signal.signal(signal.SIGINT, signal.SIG_DFL)  # lupina nima stanja: SIGTERM/SIGINT jo koncata takoj
    # Kot v Safeer OS (core/pomnilnik.py, meritev 11. 10. 2026): najvec 2 areni malloc pred nitmi Qt in obrezovanje
    # praznih strani vsakih 90 s. V enem procesu je to Qt dobil od Safeer OS; brez tega lupina drzi sproscen pomnilnik.
    from core import pomnilnik
    pomnilnik.omeji_arene()
    if not os_lupina.pripravi(sys.argv[:1]):
        print("[Safeer lupina] Qt ni na voljo", flush=True)
        return 2
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    zacetek = time.monotonic()
    lupina = LupinaProces()
    lupina.pokazi()
    lupina.odjemalec.zacni()
    utrip = QTimer()
    utrip.setInterval(varuh_procesov.UTRIP_LUPINA_S * 1000)
    utrip.timeout.connect(lambda: varuh_procesov.obvesti("WATCHDOG=1"))
    utrip.start()
    obrezovanje = QTimer()
    obrezovanje.setInterval(90 * 1000)
    obrezovanje.timeout.connect(pomnilnik.obrezuj_ce_treba)
    obrezovanje.start()
    QTimer.singleShot(5000, pomnilnik.obrezuj)       # po nalaganju QML (zacasni pomnilnik prevajalnika QML)
    varuh_procesov.obvesti("READY=1", "STATUS=namizje prikazano")
    print("[Safeer lupina] namizje prikazano v %.2f s (pid %d)" % (time.monotonic() - zacetek, os.getpid()), flush=True)
    return QApplication.instance().exec()


if __name__ == "__main__":
    sys.exit(main())
