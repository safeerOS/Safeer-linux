"""Pomocniki za preizkuse Safeer Internet Gatewaya: referencni ponudnik in »zica« namesto sredisc.

Ponudnik ima ista pravila kot AndroidApplicationGateway v Safeer OS Mobile (okna, proracun,
pol-zaprtje, razlogi zavrnitev) - je izvedljiva razlicica docs/INTERNET-GATEWAY.md. Zica ima izhodni
vrsti z mejama sredisca (64 okvirjev, 512 KiB): ce ju promet preseze, bi pravo sredisce napravo
odklopilo, zato si zica to zapomni (`prekoraceno`) in preizkus pade.
"""

from __future__ import annotations

import base64
import collections
import json
import socket
import threading
import time
from typing import Callable, Deque, Dict, Optional, Tuple

from core import link_internet as li

MEJA_OKVIRJEV = 64
MEJA_BAJTOV = 512 * 1024


class Smer:
    """Ena izhodna vrsta sredisca z eno nitjo, ki dostavlja."""

    def __init__(self, ime: str, posiljatelj: str, zamik: float = 0.0) -> None:
        self.ime = ime
        self.posiljatelj = posiljatelj
        self.zamik = zamik
        self.prejemnik: Optional[Callable[[dict], object]] = None
        self._vrsta: Deque[str] = collections.deque()
        self._bajtov = 0
        self._pogoj = threading.Condition()
        self.najvec_okvirjev = 0
        self.najvec_bajtov = 0
        self.prekoraceno = False
        self.sporocil = 0
        self.po_vrsti: Dict[str, int] = {}
        self.odprta = True
        self.ustavljena = False            # preizkus: dostava stoji (pocasna naprava)
        self.izgubi = None                 # preizkus: funkcija(sporocilo) -> True, ce se to sporocilo na poti izgubi
        threading.Thread(target=self._dostavljaj, name="zica-" + ime, daemon=True).start()

    def poslji(self, s: dict) -> bool:
        if not self.odprta:
            return False
        zapis = dict(s)
        zapis["sender"] = self.posiljatelj
        if self.izgubi is not None and self.izgubi(zapis):
            return True
        besedilo = json.dumps(zapis)
        with self._pogoj:
            self._vrsta.append(besedilo)
            self._bajtov += len(besedilo)
            self.sporocil += 1
            tip = str(s.get("type"))
            self.po_vrsti[tip] = self.po_vrsti.get(tip, 0) + 1
            self.najvec_okvirjev = max(self.najvec_okvirjev, len(self._vrsta))
            self.najvec_bajtov = max(self.najvec_bajtov, self._bajtov)
            if len(self._vrsta) > MEJA_OKVIRJEV or self._bajtov > MEJA_BAJTOV:
                self.prekoraceno = True
            self._pogoj.notify_all()
        return True

    def _dostavljaj(self) -> None:
        while True:
            with self._pogoj:
                while (not self._vrsta or self.ustavljena) and self.odprta:
                    self._pogoj.wait(0.05)
                if not self.odprta:
                    return
                besedilo = self._vrsta[0]
            if self.zamik:
                time.sleep(self.zamik)
            prejemnik = self.prejemnik
            if prejemnik is not None:
                try:
                    prejemnik(json.loads(besedilo))
                except Exception as e:  # noqa: BLE001
                    print("[zica %s] prejemnik: %r" % (self.ime, e))
            with self._pogoj:
                if self._vrsta and self._vrsta[0] is besedilo:
                    self._vrsta.popleft()
                    self._bajtov -= len(besedilo)

    def zapri(self) -> None:
        self.odprta = False
        with self._pogoj:
            self._pogoj.notify_all()


class Zica:
    """Odjemalec (pc) <-> ponudnik (tel) z vrstama sredisca v obe smeri."""

    def __init__(self, zamik: float = 0.0, odjemalec: str = "pc", ponudnik: str = "tel") -> None:
        self.gor = Smer("gor", odjemalec, zamik)       # odjemalec -> ponudnik
        self.dol = Smer("dol", ponudnik, zamik)        # ponudnik -> odjemalec

    @property
    def prekoraceno(self) -> bool:
        return self.gor.prekoraceno or self.dol.prekoraceno

    def zapri(self) -> None:
        self.gor.zapri()
        self.dol.zapri()


class _PTok:
    def __init__(self, id_toka: str, peer: str, vticnik: socket.socket, okna: bool) -> None:
        self.id = id_toka
        self.peer = peer
        self.vticnik = vticnik
        self.okna = okna
        self.pogoj = threading.Condition()
        self.poslano = 0
        self.potrjeno = 0
        self.v_letu: Deque[Tuple[int, int]] = collections.deque()
        self.vhod: Deque[bytes] = collections.deque()
        self.porabljeno = 0
        self.javljeno = 0
        self.konec_od_odjemalca = False     # odjemalec je poslal internet.eof
        self.konec_od_streznika = False     # streznik je zaprl svojo smer
        self.prejeto_skupaj = 0
        self.zaprt = False
        self.doba = 0                       # doba odjemalca, v kateri je bil tok odprt
        self.zadnji_glas = time.monotonic()
        self.ponovi_po = li.PONOVI_POTRDITEV_S


class Ponudnik:
    """Referencni ponudnik (telefon). `dovoli_zasebne=True`, ker preizkusi ciljajo 127.0.0.1."""

    def __init__(self, oddaj: Callable[[dict], bool], protokol: int = 2, dovoljenje: str = "allowed",
                 vklopljen: bool = True, vrsta_poti: str = "cellular") -> None:
        self._oddaj = oddaj
        self.protokol = protokol
        self.dovoljenje = dovoljenje
        self.vklopljen = vklopljen
        self.vrsta_poti = vrsta_poti
        self.tokovi: Dict[str, _PTok] = {}
        self.proracuni: Dict[str, li.Proracun] = {}
        self.zaklep = threading.RLock()
        self.odprtih_skupaj = 0
        self.zahtevane_poti = []
        self.napaka_odpiranja = ""          # preizkus: vsako odpiranje zavrni s tem razlogom
        self.molci = False                  # preizkus: na internet.open ne odgovori
        self.dobe: Dict[str, int] = {}      # odjemalec -> zadnja doba
        self.nedavni: Dict[str, float] = {} # nedavno zaprti ali zavrnjeni tokovi (zanje ne odgovarjamo znova)
        self.zaprti: Dict[str, str] = {}    # preizkus: id toka -> razlog, s katerim ga je ponudnik zaprl

    def _proracun(self, peer: str) -> li.Proracun:
        with self.zaklep:
            return self.proracuni.setdefault(peer, li.Proracun())

    def _poslji(self, peer: str, tip: str, **polja) -> bool:
        s = {"id": "p-%d" % time.monotonic_ns(), "type": tip, "target": peer}
        s.update(polja)
        return bool(self._oddaj(s))

    def stanje(self) -> dict:
        return {"protocol": self.protokol, "enabled": self.vklopljen, "permission": self.dovoljenje,
                "paths": [{"id": "pot-1", "kind": self.vrsta_poti, "validated": True, "metered": True,
                           "roaming": False, "allowed": True}],
                "cellular": {"allowed": True, "roaming_allowed": False, "limit_bytes": 0, "used_month": 0,
                             "used_today": 0},
                "streams": {"active": len(self.tokovi), "max": 64}}

    def obdelaj(self, s: dict) -> None:
        tip = str(s.get("type") or "")
        peer = str(s.get("sender") or "")
        if tip == "internet.query":
            if self.protokol >= 2:
                self._nova_doba(peer, s.get("epoch"))
                self._poslji(peer, "internet.status", payload=self.stanje())
            return
        id_toka = str(s.get("stream_id") or "")
        if tip == "internet.open":
            if self.protokol >= 2:
                self._nova_doba(peer, s.get("epoch"))
            self._odpri(peer, id_toka, s)
            return
        tok = self.tokovi.get(id_toka)
        if tok is None or tok.peer != peer:
            if tok is None and self.protokol >= 2 and tip in ("internet.data", "internet.window", "internet.eof"):
                self._neznan_tok(peer, id_toka)
            return
        if tip == "internet.data":
            surovo = base64.b64decode(str(s.get("data") or ""))
            odmik = s.get("off")
            with tok.pogoj:
                luknja = self.protokol >= 2 and isinstance(odmik, int) and odmik != tok.prejeto_skupaj
                if not luknja:
                    tok.prejeto_skupaj += len(surovo)
                    tok.vhod.append(surovo)
                    tok.pogoj.notify_all()
            if luknja:
                self._zapri(tok, "gap")
        elif tip == "internet.window" and self.protokol >= 2:
            self._okno(tok, int(s.get("bytes") or 0))
        elif tip == "internet.eof" and self.protokol >= 2:
            with tok.pogoj:
                tok.konec_od_odjemalca = True
                tok.pogoj.notify_all()
        elif tip == "internet.close":
            self._zapri(tok, "peer_closed", obvesti=False)

    def _nova_doba(self, peer: str, doba) -> None:
        """Odjemalec se je vrnil z drugo dobo (ponovni zagon, izguba Linka): njegovi stari tokovi nimajo lastnika."""
        if not isinstance(doba, int) or isinstance(doba, bool) or not doba or not peer:
            return
        with self.zaklep:
            prej = self.dobe.get(peer)
            self.dobe[peer] = doba
            stari = [t for t in self.tokovi.values() if t.peer == peer and t.doba != doba] if prej not in (None, doba) else []
        for t in stari:
            self._zapri(t, "restart", obvesti=False)

    def _neznan_tok(self, peer: str, id_toka: str) -> None:
        if not peer or not (8 <= len(id_toka) <= 96):
            return
        with self.zaklep:
            if id_toka in self.nedavni:
                return
            self.nedavni[id_toka] = time.monotonic()
        self._poslji(peer, "internet.close", stream_id=id_toka, reason="gone")

    def _odpri(self, peer: str, id_toka: str, s: dict) -> None:
        self.zahtevane_poti.append(str(s.get("path_id") or ""))
        if self.molci:
            return
        razlog = ""
        if not self.vklopljen:
            razlog = "disabled" if self.protokol >= 2 else "rejected"
        elif self.dovoljenje != "allowed":
            razlog = "permission_required" if self.dovoljenje == "pending" else "denied"
        elif self.napaka_odpiranja:
            razlog = self.napaka_odpiranja
        if razlog:
            self._poslji(peer, "internet.error", stream_id=id_toka, reason=razlog)
            return

        def delo() -> None:
            try:
                vticnik = socket.create_connection((str(s.get("host")), int(s.get("port") or 0)), timeout=5)
            except OSError as e:
                self._poslji(peer, "internet.error", stream_id=id_toka,
                             reason="connect_failed" if self.protokol >= 2 else str(e))
                return
            vticnik.settimeout(None)
            tok = _PTok(id_toka, peer, vticnik, self.protokol >= 2)
            tok.doba = s.get("epoch") if isinstance(s.get("epoch"), int) else 0
            with self.zaklep:
                self.tokovi[id_toka] = tok
                self.odprtih_skupaj += 1
            self._poslji(peer, "internet.opened", stream_id=id_toka, path_id="pot-1", kind=self.vrsta_poti)
            threading.Thread(target=self._pisi, args=(tok,), name="ponudnik-pisec", daemon=True).start()
            self._beri(tok)
        threading.Thread(target=delo, name="ponudnik-bralec", daemon=True).start()

    def _okno(self, tok: _PTok, bajti: int) -> None:
        b = o = 0
        with tok.pogoj:
            if bajti <= tok.potrjeno:
                return
            tok.potrjeno = min(bajti, tok.poslano)
            while tok.v_letu and tok.v_letu[0][0] <= tok.potrjeno:
                _k, n = tok.v_letu.popleft()
                b += n
                o += 1
            tok.pogoj.notify_all()
        if o:
            self._proracun(tok.peer).sprosti(b, o)

    def _beri(self, tok: _PTok) -> None:
        """Streznik -> odjemalec: bere samo, kolikor dovolita okno toka in proracun naprave."""
        try:
            while not tok.zaprt:
                with tok.pogoj:
                    while tok.okna and tok.poslano - tok.potrjeno >= li.OKNO_TOKA and not tok.zaprt:
                        tok.pogoj.wait(0.5)
                if tok.zaprt:
                    return
                try:
                    kos = tok.vticnik.recv(li.NAJVEC_KOS)
                except OSError:
                    kos = b""
                if not kos:
                    break
                if tok.okna and not self._proracun(tok.peer).zakupi(len(kos), lambda: tok.zaprt):
                    return
                with tok.pogoj:
                    odmik = tok.poslano
                    tok.poslano += len(kos)
                    if tok.okna:
                        tok.v_letu.append((tok.poslano, len(kos)))
                polja = {"off": odmik} if self.protokol >= 2 else {}
                if not self._poslji(tok.peer, "internet.data", stream_id=tok.id,
                                    data=base64.b64encode(kos).decode("ascii"), **polja):
                    self._zapri(tok, "link", obvesti=False)
                    return
            if not tok.okna:
                self._zapri(tok, "eof")
                return
            with tok.pogoj:
                tok.konec_od_streznika = True
                oboje = tok.konec_od_odjemalca and not tok.vhod
            self._poslji(tok.peer, "internet.eof", stream_id=tok.id)
            if oboje:
                self._zapri(tok, "done")
        except Exception as e:  # noqa: BLE001
            print("[ponudnik] bralec:", repr(e))
            self._zapri(tok, "error")

    def _pisi(self, tok: _PTok) -> None:
        """Odjemalec -> streznik: po vrsti, s potrditvami."""
        try:
            while True:
                ponovi = -1
                with tok.pogoj:
                    while not tok.vhod and not tok.konec_od_odjemalca and not tok.zaprt:
                        tok.pogoj.wait(0.1)
                        zdaj = time.monotonic()
                        if (tok.okna and not tok.vhod and not tok.konec_od_odjemalca and not tok.zaprt
                                and zdaj - tok.zadnji_glas >= tok.ponovi_po):
                            # Tih tok: zadnjo potrditev ponovimo (vsakic po dvakrat daljsem premoru).
                            tok.zadnji_glas = zdaj
                            tok.ponovi_po = min(tok.ponovi_po * 2, li.PONOVI_NAJVEC_S)
                            tok.javljeno = ponovi = tok.porabljeno
                            break
                    if tok.zaprt:
                        return
                    kos = tok.vhod.popleft() if tok.vhod else None
                if kos is None and ponovi >= 0:
                    self._poslji(tok.peer, "internet.window", stream_id=tok.id, bytes=ponovi)
                    continue
                if kos is None:
                    break
                tok.vticnik.sendall(kos)
                javi = 0
                with tok.pogoj:
                    tok.porabljeno += len(kos)
                    tok.zadnji_glas = time.monotonic()
                    tok.ponovi_po = li.PONOVI_POTRDITEV_S
                    if tok.okna and (tok.porabljeno - tok.javljeno >= li.POTRDI_PO or not tok.vhod):
                        tok.javljeno = javi = tok.porabljeno
                if javi:
                    self._poslji(tok.peer, "internet.window", stream_id=tok.id, bytes=javi)
            try:
                tok.vticnik.shutdown(socket.SHUT_WR)
            except OSError:
                pass
            with tok.pogoj:
                oboje = tok.konec_od_streznika
            if oboje:
                self._zapri(tok, "done")
        except OSError:
            self._zapri(tok, "write_failed")

    def _zapri(self, tok: _PTok, razlog: str, obvesti: bool = True) -> None:
        with self.zaklep:
            if self.tokovi.get(tok.id) is not tok:
                return
            del self.tokovi[tok.id]
            self.nedavni[tok.id] = time.monotonic()
            self.zaprti[tok.id] = razlog
        with tok.pogoj:
            tok.zaprt = True
            v_letu = list(tok.v_letu)
            tok.v_letu.clear()
            tok.pogoj.notify_all()
        if v_letu:
            self._proracun(tok.peer).sprosti(sum(n for _k, n in v_letu), len(v_letu))
        for korak in (lambda: tok.vticnik.shutdown(socket.SHUT_RDWR), tok.vticnik.close):
            try:
                korak()
            except OSError:
                pass
        if obvesti:
            self._poslji(tok.peer, "internet.close", stream_id=tok.id, reason=razlog)

    def zapri_vse(self, razlog: str = "shutdown") -> None:
        for tok in list(self.tokovi.values()):
            self._zapri(tok, razlog)


def povezi(zamik: float = 0.0, **ponudnik_kw):
    """(odjemalec InternetPrekLinka, ponudnik, zica), povezani med sabo."""
    zica = Zica(zamik)
    odjemalec = li.InternetPrekLinka(zica.gor.poslji)
    ponudnik = Ponudnik(zica.dol.poslji, **ponudnik_kw)
    zica.gor.prejemnik = ponudnik.obdelaj
    zica.dol.prejemnik = odjemalec.obdelaj
    return odjemalec, ponudnik, zica


class Streznik:
    """Krajevni streznik TCP za preizkuse: vsako povezavo preda `obravnava(vticnik)` v svoji niti."""

    def __init__(self, obravnava: Callable[[socket.socket], None]) -> None:
        self._obravnava = obravnava
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind(("127.0.0.1", 0))
        self.s.listen(32)
        self.vrata = self.s.getsockname()[1]
        self.povezav = 0
        threading.Thread(target=self._zanka, name="preizkusni-streznik", daemon=True).start()

    def _zanka(self) -> None:
        while True:
            try:
                c, _ = self.s.accept()
            except OSError:
                return
            self.povezav += 1
            threading.Thread(target=self._ena, args=(c,), daemon=True).start()

    def _ena(self, c: socket.socket) -> None:
        try:
            self._obravnava(c)
        except OSError:
            pass
        finally:
            try:
                c.close()
            except OSError:
                pass

    def zapri(self) -> None:
        try:
            self.s.close()
        except OSError:
            pass


def odmev(c: socket.socket) -> None:
    while True:
        kos = c.recv(65536)
        if not kos:
            return
        c.sendall(kos)


def preberi_vse(c: socket.socket, rok: float = 20.0) -> bytes:
    c.settimeout(rok)
    deli = []
    while True:
        kos = c.recv(65536)
        if not kos:
            return b"".join(deli)
        deli.append(kos)
