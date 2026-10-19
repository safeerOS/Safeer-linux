"""Streznik lupine v procesu Safeer OS: lupina namizja (core/lupina_proces.py) tece v svojem procesu in se poveze sem.

Namesto os_lupina.Namizje (QML v tem procesu) Safeer OS ustvari OddaljenaLupina. Zunaj je enaka (isti razred: metode
namizja - zacetek, videz, spletne, programi naprav ... - so podedovane, brez podvajanja), le da QML tece drugje:
klic pride prek vticnice (core/lupina_most.py), odgovor in dogodki gredo nazaj prek nje. V tem procesu ni Qt.

Vse se zgodi v glavni zanki GLib brez blokiranja: ce lupina obvisi ali je ustavljena, Safeer OS ne caka nanjo - izhodni
medpomnilnik raste do NAJVEC_IZHOD, nato se povezava prekine (lupina se ob vrnitvi poveze znova).
"""
from __future__ import annotations

import os
import socket
import threading
from typing import Any, Optional

from core import lupina_most, okolje_procesa, os_lupina, varuh_procesov

#: Ce lupina toliko bajtov ne prebere (zamrznjena), povezavo prekinemo - Safeer OS ne sme rasti zaradi nje.
NAJVEC_IZHOD = 32 * 1024 * 1024


_vtic: Optional[str] = None


def locena() -> bool:
    """Ali Safeer OS tece pod varuhom z lupino v svojem procesu (core/varuh_procesov.py nastavi SAFEER_LUPINA_VTIC).
    Spremenljivko prebere enkrat in jo odstrani iz okolja: programi, ki jih Safeer OS zazene, je ne podedujejo."""
    global _vtic
    if _vtic is None:
        _vtic = okolje_procesa.prevzemi("SAFEER_LUPINA_VTIC")     # prevzeto pred nitmi
    return bool(_vtic)


class _Pogled:
    """Klicatelj za SafeerOS._obdelaj_klic (kot os_lupina.QmlPogled): odgovori in dogodki gredo v vticnico.
    Klicati ga smejo iz katerekoli niti (odgovori iz niti ozadja) - zapis v vticnico je vedno v glavni niti."""

    def __init__(self, lupina: "OddaljenaLupina") -> None:
        self._lupina = lupina

    def qml_odgovor(self, klic_id: int, ok: bool, podatki: Any) -> None:
        self._lupina.poslji(lupina_most.odgovor(int(klic_id), bool(ok), lupina_most.besedilo_json(podatki)))

    def qml_dogodek(self, vrsta: str, podatki: Any) -> None:
        self._lupina.poslji(lupina_most.dogodek(str(vrsta), lupina_most.besedilo_json(podatki)))

    def get_uri(self) -> str:
        return "qml:namizje"

    def get_root(self):
        return None


class _Okno:
    """Okno namizja je v procesu lupine: Safeer OS ga lahko le prosi (ukaz prek vticnice)."""

    def __init__(self, lupina: "OddaljenaLupina") -> None:
        self._lupina = lupina

    def requestActivate(self) -> None:  # noqa: N802 - ime kot QWindow
        self._lupina.poslji(lupina_most.ukaz({"u": "aktiviraj"}))

    def isVisible(self) -> bool:  # noqa: N802
        return True

    def hide(self) -> None:
        pass

    def close(self) -> None:
        pass


class OddaljenaLupina(os_lupina.Namizje):
    """Namizje QML v drugem procesu. Podeduje logiko klicev namizja (_lastna, videz, _spletna ...) od os_lupina.Namizje,
    okno, zaslon in QML pa so v procesu lupine."""

    def __init__(self, safeer_os, pot: Optional[str] = None) -> None:  # noqa: D107 - Namizje.__init__ namenoma ne
        from gi.repository import GLib
        self._GLib = GLib
        self.os = safeer_os
        self.v_oknu = False
        self._ob_koncu = None
        self.pogled = _Pogled(self)
        self.okno = _Okno(self)
        self._razmerje = 1.0
        self.pot = pot or (_vtic if locena() else "") or lupina_most.pot_vticnice()
        self._povezava: Optional[socket.socket] = None
        self._dekoder = lupina_most.Dekoder()
        self._izhod = bytearray()
        self._viri: list = []
        self._vir_izhoda = 0
        self._vir_branja = 0
        self._glavna = threading.main_thread()
        self.stevec_povezav = 0
        self._streznik = self._poslusaj()
        self._spremljaj_temo()         # tema in velikost besedila sistema -> dogodek »videz« lupini (Gio je tu)

    # ------------------------------------------------------------------ vticnica
    def _poslusaj(self) -> socket.socket:
        try:
            os.unlink(self.pot)        # ostanek prejsnjega Safeer OS (sesutje): vticnica je samo nasa
        except FileNotFoundError:
            pass
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM | socket.SOCK_CLOEXEC | socket.SOCK_NONBLOCK)
        # Brez os.umask: velja za ves proces, kjer ze tecejo niti (mapa, ki jo druga nit ustvari v tem oknu, bi dobila
        # 0600). Vticnica je v $XDG_RUNTIME_DIR/safeer-os (0700) in sogovornika preverimo (lupina_most.sogovornik).
        s.bind(self.pot)
        os.chmod(self.pot, 0o600)
        s.listen(4)
        GLib = self._GLib
        self._viri.append(GLib.io_add_watch(s.fileno(), GLib.PRIORITY_DEFAULT, GLib.IO_IN, self._sprejmi))
        return s

    def _sprejmi(self, *_a) -> bool:
        try:
            nova, _ = self._streznik.accept()
        except (BlockingIOError, InterruptedError):
            return True
        except OSError as e:
            print("[SafeerOS lupina] sprejem:", e, flush=True)
            return True
        if not lupina_most.nas_sogovornik(nova):
            print("[SafeerOS lupina] tuj sogovornik zavrnjen", flush=True)
            nova.close()
            return True
        # Nova lupina (ponovni zagon lupine) zamenja staro povezavo.
        self._zapri_povezavo()
        nova.setblocking(False)
        self._povezava = nova
        self._dekoder = lupina_most.Dekoder()
        self._izhod = bytearray()
        self.stevec_povezav += 1
        GLib = self._GLib
        self._vir_branja = GLib.io_add_watch(nova.fileno(), GLib.PRIORITY_DEFAULT,
                                             GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self._beri)
        return True

    def _zapri_povezavo(self) -> None:
        GLib = self._GLib
        for ime in ("_vir_branja", "_vir_izhoda"):
            vir = getattr(self, ime, 0)
            if vir:
                GLib.source_remove(vir)
                setattr(self, ime, 0)
        if self._povezava is not None:
            try:
                self._povezava.close()
            except OSError:
                pass
        self._povezava = None
        self._izhod = bytearray()

    def _beri(self, _fd, pogoj) -> bool:
        s = self._povezava
        if s is None:
            return False
        okvirji = []
        while True:
            try:
                podatki = s.recv(262144)
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                podatki = b""
            if not podatki:
                self._vir_branja = 0
                self._zapri_povezavo()
                return False
            try:
                okvirji += self._dekoder.dodaj(podatki)
            except lupina_most.PrevelikOkvir:
                self._vir_branja = 0
                self._zapri_povezavo()
                return False
        for vrsta, telo in okvirji:
            self._obdelaj_okvir(vrsta, telo)
        return True

    def _obdelaj_okvir(self, vrsta: bytes, telo: bytes) -> None:
        try:
            ime, vsebina = lupina_most.razcleni(vrsta, telo)
        except (ValueError, KeyError) as e:
            print("[SafeerOS lupina] okvir:", e, flush=True)
            return
        if ime == "K" and isinstance(vsebina, dict):
            a = vsebina.get("a")
            self.klic(int(vsebina.get("k") or 0), str(vsebina.get("m") or ""), a if isinstance(a, list) else [])
        elif ime == "P":
            self.poslji(lupina_most.pong(vsebina))
        elif ime == "Z" and isinstance(vsebina, dict):
            try:
                self._razmerje = max(0.5, min(4.0, float(vsebina.get("razmerje") or 1.0)))
            except (TypeError, ValueError):
                self._razmerje = 1.0

    def poslji(self, okvir: bytes) -> None:
        """Iz katerekoli niti; zapis v vticnico vedno v glavni niti, brez cakanja na lupino."""
        if threading.current_thread() is not self._glavna:
            self._GLib.idle_add(lambda: (self._poslji(okvir), False)[1])
            return
        self._poslji(okvir)

    def _poslji(self, okvir: bytes) -> None:
        s = self._povezava
        if s is None:
            return                     # lupine ni (zaganja se): dogodek ni pomemben, ob povezavi vprasa sama
        self._izhod += okvir
        if len(self._izhod) > NAJVEC_IZHOD:
            print("[SafeerOS lupina] lupina ne bere (%d MB): povezava prekinjena" % (len(self._izhod) >> 20), flush=True)
            self._zapri_povezavo()
            return
        if not self._vir_izhoda:
            self._pisi()

    def _pisi(self, *_a) -> bool:
        s = self._povezava
        while s is not None and self._izhod:
            try:
                n = s.send(self._izhod)
            except (BlockingIOError, InterruptedError):
                break
            except OSError:
                self._vir_izhoda = 0
                self._zapri_povezavo()
                return False
            del self._izhod[:n]
        if self._izhod and s is not None:
            if not self._vir_izhoda:
                GLib = self._GLib
                self._vir_izhoda = GLib.io_add_watch(s.fileno(), GLib.PRIORITY_DEFAULT, GLib.IO_OUT, self._pisi)
            return True
        self._vir_izhoda = 0
        return False

    # ------------------------------------------------------------------ Namizje (podedovano) - deli, ki so v lupini
    def klic(self, klic_id: int, metoda: str, a: list) -> None:
        try:
            if not self._lastna(klic_id, metoda, a):
                self.os._obdelaj_klic(self.pogled, klic_id, metoda, a)
        except Exception as e:  # noqa: BLE001
            print("[SafeerOS lupina]", metoda, e, flush=True)
            self.pogled.qml_odgovor(klic_id, False, str(e))

    def _razmerje_zaslona(self) -> float:
        return self._razmerje

    def pokazi(self) -> None:
        """Streznik poslusa: Safeer OS je pripravljen (varuh) in utripa iz glavne zanke (zamrznitev)."""
        varuh_procesov.obvesti("READY=1", "STATUS=Safeer OS streze lupino")
        if not getattr(self, "_utrip", 0):
            self._utrip = varuh_procesov.utrip_glib(self._GLib)

    def postavi(self) -> None:
        pass

    def _zaslon_spremenjen(self) -> None:
        pass                           # zaslone spremlja lupina sama (Qt), skupaj z dockom

    def dvigni(self) -> None:
        self.okno.requestActivate()

    def zapri(self) -> None:
        self._zapri_povezavo()
        GLib = self._GLib
        for vir in self._viri:
            GLib.source_remove(vir)
        self._viri = []
        try:
            self._streznik.close()
            os.unlink(self.pot)
        except OSError:
            pass
