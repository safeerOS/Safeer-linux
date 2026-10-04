"""Safeer Internet Gateway - odjemalec na racunalniku (tokovi prek Safeer Linka).

Telefon s Safeer OS zna zaupani napravi posoditi svoj internet: na `internet.open` sam odpre povezavo
TCP po izbranem omrezju (mobilno ali Wi-Fi) in bajte prenasa po Safeer Linku. Ta modul je druga stran
iste zice: tok (Tok) med krajevno vticnico programa in ponudnikom, z nadzorom pretoka. Krajevni
posrednik, izbira poti in nastavitve so v core/link_internet_posrednik.py.

Protokol 2 (docs/INTERNET-GATEWAY.md). Vsa sporocila imajo `target`, `sender` vpise sredisce. Polja
so ploska, da jih sredisca prepisejo, ne da bi jih razumela:

    odjemalec -> ponudnik   internet.query                          kaj ponudnik dovoli (odgovor internet.status)
                            internet.open    stream_id host port path_id v
                            internet.data    stream_id off data(base64)   off = odmik kosa v toku
                            internet.window  stream_id bytes        koliko bajtov toka je prejemnik ze porabil
                            internet.eof     stream_id              program je nehal posiljati (pol-zaprtje)
                            internet.close   stream_id reason
    ponudnik -> odjemalec   internet.status  payload{...}
                            internet.opened  stream_id path_id kind
                            internet.data / internet.window / internet.eof / internet.close
                            internet.error   stream_id reason

Nadzor pretoka. Posiljatelj sme imeti na poti do ene naprave najvec PRORACUN_NAPRAVE bajtov in
NAJVEC_OKVIRJEV okvirjev (vsota vseh tokov) ter najvec OKNO_TOKA bajtov na tok. Meje so pod mejami
izhodne vrste sredisc (64 okvirjev, 512 KiB - core/link_ws.py, HubStreznik.kt): sredisce napravo, ki
ne bere, odklopi, zato tok brez nadzora pretoka ne podre samo sebe, ampak celo povezavo Linka.
Prejemnik potrdi (internet.window), ko porabi POTRDI_PO bajtov ali ko nima vec nicesar v vrsti -
potrditev je torej najvec toliko, kolikor je okvirjev na poti.

Vsak kos nosi svoj odmik v toku (`off`). Povezava med srediscema se lahko sredi prenosa obnovi in
kos se izgubi, ne da bi kateri od koncev to opazil; brez odmika bi program dobil tok z luknjo. Kos z
napacnim odmikom zato tok konca (»gap«) - program vidi prekinjeno povezavo in poskusi znova.

Tih tok ponovi zadnjo potrditev (po PONOVI_POTRDITEV_S, nato vsakic po dvakrat daljsem premoru). Tako
izgubljena potrditev toka ne ustavi za vedno, in stran, ki toka ne pozna vec (ponovni zagon), na
ponovitev odgovori z internet.close »gone«. Isti odgovor dobi kos za neznan tok.

Doba (`epoch` v internet.open in internet.query): stevilo, ki ga odjemalec zamenja ob vsaki izgubi
Linka. Ponudnik ob novi dobi zapre odjemalceve tokove prejsnje dobe - ti nimajo vec lastnika, do
izteka nedejavnosti pa bi drzali proracun naprave.

Ponudnik protokola 1 (Safeer OS do 0.5.46) oken ne pozna: z njim tok tece brez nadzora pretoka in je
namenjen samo diagnostiki (`okna=False`).
"""

from __future__ import annotations

import base64
import collections
import os
import socket
import threading
import time
from typing import Callable, Deque, Dict, List, Optional, Tuple

PROTOKOL = 2
#: Najvec surovih bajtov v enem internet.data (ponudnik vecjega kosa ne sprejme).
NAJVEC_KOS = 24 * 1024
OKNO_TOKA = 128 * 1024
PRORACUN_NAPRAVE = 256 * 1024
NAJVEC_OKVIRJEV = 20
POTRDI_PO = 32 * 1024
ROK_ODPIRANJA_S = 20.0
ROK_STANJA_S = 4.0
#: Tok brez prometa v nobeno smer se po tem casu zapre (ponudnik ima enako mejo).
NEDEJAVNOST_S = 300.0
NAJVEC_TOKOV = 48
#: Ponudnik brez oken: ce program ne bere, se vrsta ne sme polniti v nedogled.
NAJVEC_BREZ_OKEN = 8 * 1024 * 1024
#: Kako pogosto se blokirano branje/pisanje zbudi in preveri, ali tok se zivi.
BUDILKA_S = 5.0
#: Tih tok ponovi zadnjo potrditev po toliko sekundah, potem vsakic po dvakrat daljsem premoru.
PONOVI_POTRDITEV_S = 3.0
PONOVI_NAJVEC_S = 60.0
#: Koliko nedavno koncanih ali zavrnjenih tokov si zapomnimo (da zanje ne odgovarjamo dvakrat).
NEDAVNIH_TOKOV = 256

POT_MOBILNA = "mobile"
POT_WIFI = "wifi"
POT_KATERAKOLI = "any"

#: Razlogi, ki jih pozna vmesnik (vse drugo je »connect_failed«).
RAZLOGI = ("disabled", "permission_required", "denied", "not_trusted", "no_path", "mobile_off", "no_mobile",
           "roaming", "limit", "busy", "private_destination", "port_blocked", "dns_failed", "connect_failed",
           "timeout", "link", "busy_local", "old_provider", "old_requester", "idle", "local", "gap", "data", "gone",
           "restart")


def razlog_iz(besedilo: str) -> str:
    """Razlog ponudnika v eno od znanih kod. Ponudnik protokola 1 poslje sporocilo izjeme."""
    r = (besedilo or "").strip()
    if r in RAZLOGI:
        return r
    nizko = r.lower()
    if r == "rejected":
        return "disabled"
    if "private_destination" in nizko:
        return "private_destination"
    if "no_path" in nizko or "path_lost" in nizko:
        return "no_path"
    if "unable to resolve" in nizko or "unknownhost" in nizko or "no address" in nizko:
        return "dns_failed"
    if "timed out" in nizko or "timeout" in nizko:
        return "timeout"
    return "connect_failed"


class Proracun:
    """Koliko bajtov in okvirjev je hkrati na poti do ene naprave (vsota vseh tokov)."""

    def __init__(self, bajtov: int = PRORACUN_NAPRAVE, okvirjev: int = NAJVEC_OKVIRJEV) -> None:
        self.meja_bajtov = bajtov
        self.meja_okvirjev = okvirjev
        self.bajtov = 0
        self.okvirjev = 0
        self._pogoj = threading.Condition()

    def zakupi(self, n: int, preklic: Callable[[], bool]) -> bool:
        """Pocaka na prostor za okvir z `n` bajti. False, ko `preklic()` vrne True."""
        with self._pogoj:
            while self.okvirjev >= self.meja_okvirjev or (self.bajtov and self.bajtov + n > self.meja_bajtov):
                if preklic():
                    return False
                self._pogoj.wait(0.25)
            if preklic():
                return False
            self.bajtov += n
            self.okvirjev += 1
            return True

    def sprosti(self, n: int, okvirjev: int = 1) -> None:
        with self._pogoj:
            self.bajtov = max(0, self.bajtov - n)
            self.okvirjev = max(0, self.okvirjev - okvirjev)
            self._pogoj.notify_all()


class Tok:
    """En tok TCP: krajevna vticnica programa <-> ponudnik. Dve niti: gor (program -> ponudnik) in dol."""

    def __init__(self, upravitelj: "InternetPrekLinka", id_toka: str, naprava: str, host: str, port: int,
                 vticnik: socket.socket, okna: bool) -> None:
        self.u = upravitelj
        self.id = id_toka
        self.naprava = naprava
        self.host = host
        self.port = port
        self.vticnik = vticnik
        self.okna = okna
        self.pot_id = ""
        self.vrsta_poti = ""
        self.razlog = ""
        self.gor = 0
        self.dol = 0
        self.zacetek = time.monotonic()
        self.dejavnost = self.zacetek
        self._pogoj = threading.Condition()
        self._odprt = threading.Event()
        self._napaka_odpiranja = ""
        self._koncan = threading.Event()
        self._stevec = 0
        # gor
        self._poslano = 0
        self._potrjeno = 0
        self._v_letu: Deque[Tuple[int, int]] = collections.deque()
        self._konec_gor = False
        # dol
        self._vhod: Deque[bytes] = collections.deque()
        self._vhod_bajtov = 0
        self._prejeto_skupaj = 0            # bajti, ki so prisli s ponudnika (za preverjanje odmika kosov)
        self._porabljeno = 0
        self._javljeno = 0
        self._zadnji_glas = self.zacetek     # zadnji prejeti kos ali poslana potrditev
        self._ponovi_po = PONOVI_POTRDITEV_S
        self._konec_dol = False
        self._dol_koncal = False            # nit »dol« je program ze pol-zaprla in se koncala
        self._zagnan = False                # do zazeni() je vticnica klicateljeva (odgovoriti mora programu)
        self._ponudnik_zaprl = False
        self._prekinjen = False

    # ------------------------------------------------------------------ posiljanje sporocil

    def _sporocilo(self, tip: str, **polja) -> bool:
        with self._pogoj:
            self._stevec += 1
            n = self._stevec
        s = {"id": "ig-%s-%d" % (self.id, n), "type": tip, "target": self.naprava, "stream_id": self.id}
        s.update(polja)
        return self.u._oddaj(s)

    # ------------------------------------------------------------------ dogodki s ponudnika (bralna nit Linka)

    def _na_odprto(self, pot_id: str, vrsta: str) -> None:
        self.pot_id = pot_id
        self.vrsta_poti = vrsta
        self._odprt.set()

    def _na_napako(self, razlog: str) -> None:
        if not self._odprt.is_set():
            self._napaka_odpiranja = razlog or "connect_failed"
            self._odprt.set()
            return
        self._na_zaprtje(razlog)

    def _na_podatke(self, surovo: bytes, odmik: Optional[int] = None) -> None:
        prevec = False
        with self._pogoj:
            if self._prekinjen or self._konec_dol:
                return
            luknja = odmik is not None and odmik != self._prejeto_skupaj
            if not luknja:
                self._prejeto_skupaj += len(surovo)
        if luknja:
            # Kos se je na poti izgubil: tok z luknjo bi bil pokvarjen, zato ga koncamo.
            print("[SafeerInternet] tok %s: kos z odmikom %s, pricakovan %d (kos %d B)"
                  % (self.id[-6:], odmik, self._prejeto_skupaj, len(surovo)), flush=True)
            self.prekini("gap")
            return
        with self._pogoj:
            if self._prekinjen or self._konec_dol:
                return
            self._vhod.append(surovo)
            self._vhod_bajtov += len(surovo)
            self.dejavnost = self._zadnji_glas = time.monotonic()
            self._ponovi_po = PONOVI_POTRDITEV_S
            meja = OKNO_TOKA + PRORACUN_NAPRAVE if self.okna else NAJVEC_BREZ_OKEN
            prevec = self._vhod_bajtov > meja
            self._pogoj.notify_all()
        if prevec:
            # Ponudnik krsi okno (ali ga nima) in program ne bere: pomnilnik ne sme rasti.
            self.prekini("local")

    def _na_okno(self, bajti: int) -> None:
        sprosceno_b = sprosceno_o = 0
        with self._pogoj:
            if bajti <= self._potrjeno:
                return
            self._potrjeno = min(bajti, self._poslano)
            while self._v_letu and self._v_letu[0][0] <= self._potrjeno:
                _konec, n = self._v_letu.popleft()
                sprosceno_b += n
                sprosceno_o += 1
            self._pogoj.notify_all()
        if sprosceno_o:
            self.u._proracun(self.naprava).sprosti(sprosceno_b, sprosceno_o)

    def _na_eof(self) -> None:
        with self._pogoj:
            self._konec_dol = True
            self._pogoj.notify_all()

    def _na_zaprtje(self, razlog: str) -> None:
        """Ponudnik je tok zaprl v obe smeri. Kar je ze v vrsti, program se dobi."""
        with self._pogoj:
            self._ponudnik_zaprl = True
            self._konec_dol = True
            if not self.razlog:
                self.razlog = razlog or "closed"
            dol_koncal = self._dol_koncal
            self._pogoj.notify_all()
        if not self._odprt.is_set():
            self._napaka_odpiranja = razlog or "connect_failed"
            self._odprt.set()
        elif dol_koncal:
            # Streznik je ze koncal, program je se posiljal: zdaj nima vec komu.
            self.prekini(self.razlog, obvesti=False)

    # ------------------------------------------------------------------ zivljenje

    def zazeni(self, predpodatki: bytes = b"") -> None:
        """Zacne prenasati. Klicatelj prej programu odgovori, da je povezava vzpostavljena."""
        with self._pogoj:
            if self._prekinjen:
                # Tok se je koncal med klicateljevim odgovorom programu: vticnica je zdaj nasa, zapremo jo.
                self._zagnan = True
                zapri = True
            else:
                self._zagnan = True
                zapri = False
        if zapri:
            self._zapri_vticnico()
            return
        try:
            self.vticnik.settimeout(BUDILKA_S)
        except OSError:
            pass
        threading.Thread(target=self._crpaj_gor, args=(predpodatki,), name="safeer-internet-gor", daemon=True).start()
        threading.Thread(target=self._crpaj_dol, name="safeer-internet-dol", daemon=True).start()

    def pocakaj(self, cas: Optional[float] = None) -> bool:
        return self._koncan.wait(cas)

    @property
    def koncan(self) -> bool:
        return self._koncan.is_set()

    def _nedejaven(self) -> bool:
        return time.monotonic() - self.dejavnost > NEDEJAVNOST_S

    def _ustavljen_gor(self) -> bool:
        return self._prekinjen or self._ponudnik_zaprl

    def _crpaj_gor(self, predpodatki: bytes) -> None:
        cakajoci = predpodatki
        try:
            while True:
                with self._pogoj:
                    while self.okna and self._poslano - self._potrjeno >= OKNO_TOKA and not self._ustavljen_gor():
                        self._pogoj.wait(0.5)
                    if self._ustavljen_gor():
                        return
                if cakajoci:
                    kos, cakajoci = cakajoci[:NAJVEC_KOS], cakajoci[NAJVEC_KOS:]
                else:
                    try:
                        kos = self.vticnik.recv(NAJVEC_KOS)
                    except socket.timeout:
                        if self._nedejaven():
                            self.prekini("idle")
                            return
                        continue
                    except OSError:
                        self.prekini("local")
                        return
                    if not kos:
                        break
                if self.okna and not self.u._proracun(self.naprava).zakupi(len(kos), self._ustavljen_gor):
                    return
                with self._pogoj:
                    odmik = self._poslano
                    self._poslano += len(kos)
                    if self.okna:
                        self._v_letu.append((self._poslano, len(kos)))
                if self._prekinjen:
                    # Prekinitev med zakupom: prostor je ze sproscen s prekini() ali pa ga sprostimo tu.
                    self._sprosti_v_letu()
                    return
                if not self._sporocilo("internet.data", off=odmik, data=base64.b64encode(kos).decode("ascii")):
                    self.prekini("link", obvesti=False)
                    return
                self.gor += len(kos)
                self.dejavnost = time.monotonic()
                self.u._stej(self, len(kos), 0)
            with self._pogoj:
                self._konec_gor = True
            if self.okna and not self._ustavljen_gor():
                self._sporocilo("internet.eof")
            self._morda_koncaj()
        except Exception:  # noqa: BLE001
            self.prekini("local")

    def _pisi(self, kos: bytes) -> bool:
        """Zapise cel kos programu. Program sme brati pocasi; brez napredka NEDEJAVNOST_S je konec."""
        pogled = memoryview(kos)
        zadnji_napredek = time.monotonic()
        while len(pogled):
            if self._prekinjen:
                return False
            try:
                n = self.vticnik.send(pogled)
            except socket.timeout:
                if time.monotonic() - zadnji_napredek > NEDEJAVNOST_S:
                    return False
                continue
            except OSError:
                return False
            pogled = pogled[n:]
            zadnji_napredek = time.monotonic()
        return True

    def _ponovitev_potrditve(self) -> int:
        """Pod kljucavnico. Tok je tih: ali je cas, da ponudniku ponovimo, koliko smo porabili? -1 = ne."""
        if not self.okna or self._ponudnik_zaprl:
            return -1
        zdaj = time.monotonic()
        if zdaj - self._zadnji_glas < self._ponovi_po:
            return -1
        self._zadnji_glas = zdaj
        self._ponovi_po = min(self._ponovi_po * 2, PONOVI_NAJVEC_S)
        self._javljeno = self._porabljeno
        return self._porabljeno

    def _crpaj_dol(self) -> None:
        try:
            while True:
                kos = None
                ponovi = -1
                with self._pogoj:
                    while not self._vhod and not self._konec_dol and not self._prekinjen:
                        self._pogoj.wait(min(1.0, self._ponovi_po))
                        if self._vhod or self._konec_dol or self._prekinjen or self._nedejaven():
                            break
                        ponovi = self._ponovitev_potrditve()
                        if ponovi >= 0:
                            break
                    if self._prekinjen:
                        return
                    if self._vhod:
                        kos = self._vhod.popleft()
                        self._vhod_bajtov -= len(kos)
                    elif self._konec_dol:
                        break
                if kos is None and ponovi >= 0:
                    # Potrditev se ponovi: ce se je prejsnja izgubila, ponudnik spet posilja; ce toka ne
                    # pozna vec, odgovori z internet.close.
                    self._sporocilo("internet.window", bytes=ponovi)
                    continue
                if kos is None:
                    self.prekini("idle")
                    return
                if not self._pisi(kos):
                    self.prekini("local")
                    return
                self.dol += len(kos)
                self.dejavnost = time.monotonic()
                self.u._stej(self, 0, len(kos))
                javi = 0
                with self._pogoj:
                    self._porabljeno += len(kos)
                    if (self.okna and not self._ponudnik_zaprl
                            and (self._porabljeno - self._javljeno >= POTRDI_PO or not self._vhod)):
                        self._javljeno = javi = self._porabljeno
                        self._zadnji_glas = time.monotonic()
                if javi:
                    self._sporocilo("internet.window", bytes=javi)
            if self._ponudnik_zaprl:
                self.prekini(self.razlog or "closed", obvesti=False)
                return
            try:
                self.vticnik.shutdown(socket.SHUT_WR)
            except OSError:
                pass
            with self._pogoj:
                self._dol_koncal = True
                zaprl = self._ponudnik_zaprl
            if zaprl:
                self.prekini(self.razlog or "closed", obvesti=False)
                return
            self._morda_koncaj()
        except Exception:  # noqa: BLE001
            self.prekini("local")

    def _morda_koncaj(self) -> None:
        with self._pogoj:
            oboje = self._konec_gor and self._konec_dol and not self._vhod
        if oboje:
            self.prekini("done")

    def _sprosti_v_letu(self) -> None:
        with self._pogoj:
            v_letu = list(self._v_letu)
            self._v_letu.clear()
        if v_letu:
            self.u._proracun(self.naprava).sprosti(sum(n for _k, n in v_letu), len(v_letu))

    def prekini(self, razlog: str, obvesti: bool = True) -> None:
        """Konec toka z obeh strani. Varno iz katerekoli niti in veckrat."""
        with self._pogoj:
            if self._prekinjen:
                return
            self._prekinjen = True
            if not self.razlog:
                self.razlog = razlog
            self._vhod.clear()
            self._vhod_bajtov = 0
            self._pogoj.notify_all()
        self._sprosti_v_letu()
        if razlog not in ("done", "closed", "eof", "peer_closed", "local", "shutdown", "disabled"):
            # Nenavaden konec (luknja, link, nedejavnost): ena vrstica v dnevnik, da se vzrok da najti.
            print("[SafeerInternet] tok %s -> %s:%d konec: %s (gor %d B, dol %d B)"
                  % (self.id[-6:], self.host[:40], self.port, razlog, self.gor, self.dol), flush=True)
        if obvesti and not self._ponudnik_zaprl:
            self._sporocilo("internet.close", reason=razlog)
        with self._pogoj:
            zagnan = self._zagnan
        if zagnan:
            self._zapri_vticnico()
        self.u._odstrani(self)
        if not self._odprt.is_set():
            self._napaka_odpiranja = self._napaka_odpiranja or razlog
            self._odprt.set()
        self._koncan.set()

    def _zapri_vticnico(self) -> None:
        for korak in (lambda: self.vticnik.shutdown(socket.SHUT_RDWR), self.vticnik.close):
            try:
                korak()
            except OSError:
                pass

    def opis(self) -> dict:
        return {"id": self.id, "naprava": self.naprava, "cilj": "%s:%d" % (self.host, self.port),
                "pot": self.vrsta_poti, "gor": self.gor, "dol": self.dol,
                "trajanje": round(time.monotonic() - self.zacetek, 1)}


class InternetPrekLinka:
    """Vsi tokovi tega racunalnika prek ponudnikov v Linku in kar o ponudnikih vemo."""

    def __init__(self, oddaj: Callable[[dict], bool]) -> None:
        #: Poslje sporocilo v Link (Povezava.poslji). False, ko povezave ni.
        self._oddaj_v_link = oddaj
        self._zaklep = threading.RLock()
        self._tokovi: Dict[str, Tok] = {}
        self._proracuni: Dict[str, Proracun] = {}
        #: naprava -> {"protokol": int, "stanje": dict, "cas": monotonic}
        self._ponudniki: Dict[str, dict] = {}
        self._cakajo_stanje: Dict[str, threading.Event] = {}
        #: Doba: stevilo v internet.open/query; zamenja se ob vsaki izgubi Linka (ponudnik takrat zapre stare tokove).
        self._doba = int.from_bytes(os.urandom(4), "big") % 1_000_000_000 + 1
        #: Nedavno koncani ali zavrnjeni tokovi (id -> cas): zanje ponudniku ne odgovarjamo znova.
        self._nedavni: "collections.OrderedDict[str, float]" = collections.OrderedDict()
        #: (naprava, stanje) ob vsakem internet.status - tudi nenarocenem (dovoljenje, nastavitve telefona).
        self.ob_stanju: Optional[Callable[[str, dict], None]] = None
        #: (naprava, vrsta_poti, gor, dol) ob vsakem prenesenem kosu.
        self.ob_prometu: Optional[Callable[[str, str, int, int], None]] = None
        self.skupaj_gor = 0
        self.skupaj_dol = 0

    # ------------------------------------------------------------------ notranje

    def _oddaj(self, sporocilo: dict) -> bool:
        try:
            return bool(self._oddaj_v_link(sporocilo))
        except Exception:  # noqa: BLE001
            return False

    def _proracun(self, naprava: str) -> Proracun:
        with self._zaklep:
            p = self._proracuni.get(naprava)
            if p is None:
                p = self._proracuni[naprava] = Proracun()
            return p

    def _odstrani(self, tok: Tok) -> None:
        with self._zaklep:
            if self._tokovi.get(tok.id) is tok:
                del self._tokovi[tok.id]
            self._zapomni_nedavnega(tok.id)

    def _zapomni_nedavnega(self, id_toka: str) -> bool:
        """Pod kljucavnico. True, ce toka se ni bilo med nedavnimi."""
        nov = id_toka not in self._nedavni
        self._nedavni[id_toka] = time.monotonic()
        self._nedavni.move_to_end(id_toka)
        while len(self._nedavni) > NEDAVNIH_TOKOV:
            self._nedavni.popitem(last=False)
        return nov

    def _neznan_tok(self, naprava: str, id_toka: str) -> None:
        """Ponudnik posilja za tok, ki ga ne poznamo (npr. po nasem ponovnem zagonu): povemo mu, naj ga zapre."""
        if not naprava or not (8 <= len(id_toka) <= 96):
            return
        with self._zaklep:
            if not self._zapomni_nedavnega(id_toka):
                return                      # smo ga zaprli sami ali smo ze odgovorili
        self._oddaj({"id": "ig-x-" + os.urandom(4).hex(), "type": "internet.close", "target": naprava,
                     "stream_id": id_toka, "reason": "gone"})

    def _stej(self, tok: Tok, gor: int, dol: int) -> None:
        with self._zaklep:
            self.skupaj_gor += gor
            self.skupaj_dol += dol
        klic = self.ob_prometu
        if klic is not None:
            try:
                klic(tok.naprava, tok.vrsta_poti, gor, dol)
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------ sporocila iz Linka

    def obdelaj(self, s: dict) -> bool:
        """Sporocilo iz Linka. True, ce je bilo nase (internet.*)."""
        tip = str(s.get("type") or "")
        if not tip.startswith("internet."):
            return False
        od = str(s.get("sender") or "")
        if tip == "internet.status":
            tovor = s.get("payload")
            if od and isinstance(tovor, dict):
                self._na_stanje(od, tovor)
            return True
        if tip == "internet.ack":
            # Potrditev sredisca. Zanimiva je samo zavrnitev: cilja ni v Linku.
            if str(s.get("status") or "") not in ("", "accepted"):
                self._zavrnitev_sredisca(str(s.get("ref_id") or ""), str(s.get("error_code") or ""))
            return True
        id_toka = str(s.get("stream_id") or "")
        tok = self._tokovi.get(id_toka)
        if tok is None or tok.naprava != od:
            if tok is None and tip in ("internet.data", "internet.opened", "internet.window"):
                self._neznan_tok(od, id_toka)
            return True
        if tip == "internet.data":
            try:
                surovo = base64.b64decode(str(s.get("data") or ""), validate=True)
            except Exception:  # noqa: BLE001
                # Kos ni veljaven base64: na poti se je pokvaril. Toka ne nadaljujemo.
                tok.prekini("data")
                return True
            if surovo:
                odmik = s.get("off")
                tok._na_podatke(surovo, odmik if isinstance(odmik, int) and not isinstance(odmik, bool) else None)
        elif tip == "internet.window":
            try:
                tok._na_okno(int(s.get("bytes") or 0))
            except (TypeError, ValueError):
                pass
        elif tip == "internet.opened":
            tok._na_odprto(str(s.get("path_id") or ""), str(s.get("kind") or ""))
        elif tip == "internet.eof":
            tok._na_eof()
        elif tip == "internet.close":
            tok._na_zaprtje(str(s.get("reason") or "closed"))
        elif tip == "internet.error":
            tok._na_napako(razlog_iz(str(s.get("reason") or "")))
        return True

    def _zavrnitev_sredisca(self, ref: str, koda: str = "") -> None:
        if ref.startswith("ig-"):
            id_toka = ref[3:].rsplit("-", 1)[0]
            tok = self._tokovi.get(id_toka)
            if tok is not None:
                tok._ponudnik_zaprl = True      # ponudnika ni; nima smisla posiljati internet.close
                if not tok._odprt.is_set():
                    tok._napaka_odpiranja = "link"
                    tok._odprt.set()
                else:
                    print("[SafeerInternet] tok %s: sredisce je zavrnilo sporocilo (%s)" % (tok.id[-6:], koda), flush=True)
                    tok.prekini("link", obvesti=False)
        elif ref.startswith("iq-"):
            dogodek = self._cakajo_stanje.get(ref)
            if dogodek is not None:
                dogodek.set()

    def _na_stanje(self, naprava: str, tovor: dict) -> None:
        try:
            protokol = int(tovor.get("protocol") or 1)
        except (TypeError, ValueError):
            protokol = 1
        with self._zaklep:
            self._ponudniki[naprava] = {"protokol": protokol, "stanje": dict(tovor), "cas": time.monotonic()}
            dogodki = [d for k, d in self._cakajo_stanje.items() if k.startswith("iq-" + naprava + "-")]
        for d in dogodki:
            d.set()
        klic = self.ob_stanju
        if klic is not None:
            try:
                klic(naprava, dict(tovor))
            except Exception:  # noqa: BLE001
                pass

    def povezava_izgubljena(self) -> None:
        """Link je padel: tokovi nimajo kam, o ponudnikih ne vemo vec nicesar."""
        with self._zaklep:
            tokovi = list(self._tokovi.values())
            self._ponudniki.clear()
            # Ponudnik teh tokov ne bo izvedel, da jih ni vec: ob prvi naslednji zahtevi mu to pove nova doba.
            self._doba = self._doba % 1_000_000_000 + 1
        for t in tokovi:
            t._ponudnik_zaprl = True
            t.prekini("link", obvesti=False)

    # ------------------------------------------------------------------ javno

    def vprasaj(self, naprava: str, cas: float = ROK_STANJA_S) -> Optional[dict]:
        """Vprasa ponudnika, kaj dovoli. None, ce ne odgovori (ni ga, ali je protokol 1)."""
        ref = "iq-%s-%s" % (naprava, os.urandom(4).hex())
        dogodek = threading.Event()
        with self._zaklep:
            self._cakajo_stanje[ref] = dogodek
            prej = self._ponudniki.get(naprava, {}).get("cas", 0.0)
        try:
            if not self._oddaj({"id": ref, "type": "internet.query", "target": naprava, "v": PROTOKOL,
                                "epoch": self._doba}):
                return None
            dogodek.wait(cas)
        finally:
            with self._zaklep:
                self._cakajo_stanje.pop(ref, None)
        with self._zaklep:
            vnos = self._ponudniki.get(naprava)
            if vnos is None or vnos.get("cas", 0.0) <= prej:
                return None
            return dict(vnos["stanje"])

    def znano_stanje(self, naprava: str) -> Optional[dict]:
        with self._zaklep:
            vnos = self._ponudniki.get(naprava)
            return dict(vnos["stanje"]) if vnos else None

    def protokol(self, naprava: str) -> int:
        """Protokol ponudnika: 0 = se ne vemo, 1 = stari (brez oken), 2 = z okni."""
        with self._zaklep:
            vnos = self._ponudniki.get(naprava)
            return int(vnos["protokol"]) if vnos else 0

    def odpri(self, naprava: str, host: str, port: int, vticnik: socket.socket, pot: str = POT_MOBILNA,
              cas: float = ROK_ODPIRANJA_S, okna: Optional[bool] = None) -> Tuple[Optional[Tok], str]:
        """Odpre tok do `host:port` prek ponudnika. Vrne (tok, "") ali (None, razlog).

        Tok se ne prenasa, dokler klicatelj ne poklice `zazeni()` - prej mora programu odgovoriti, da
        je povezava vzpostavljena, sicer bi prvi bajti streznika prehiteli ta odgovor."""
        if okna is None:
            okna = self.protokol(naprava) >= 2
        with self._zaklep:
            if len(self._tokovi) >= NAJVEC_TOKOV:
                return None, "busy_local"
            id_toka = "s" + os.urandom(10).hex()
            tok = Tok(self, id_toka, naprava, host, int(port), vticnik, okna)
            self._tokovi[id_toka] = tok
        if not tok._sporocilo("internet.open", host=host, port=int(port), path_id=pot, v=PROTOKOL, epoch=self._doba):
            tok._ponudnik_zaprl = True
            tok.prekini("link", obvesti=False)
            return None, "link"
        if not tok._odprt.wait(cas):
            tok.prekini("timeout")
            return None, "timeout"
        if tok._napaka_odpiranja or tok._prekinjen:
            razlog = tok._napaka_odpiranja or tok.razlog or "connect_failed"
            tok._ponudnik_zaprl = True
            tok.prekini(razlog, obvesti=False)
            return None, razlog
        return tok, ""

    def tokovi(self) -> List[dict]:
        with self._zaklep:
            return [t.opis() for t in self._tokovi.values()]

    def stevilo_tokov(self) -> int:
        with self._zaklep:
            return len(self._tokovi)

    def zapri_vse(self, razlog: str = "shutdown") -> None:
        with self._zaklep:
            tokovi = list(self._tokovi.values())
        for t in tokovi:
            t.prekini(razlog)
