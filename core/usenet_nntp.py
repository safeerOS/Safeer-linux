"""Odjemalec NNTP prek TLS za lasten pogon Usenet (lastnik 25. 10. 2026 22:10: neposredno predvajanje z Useneta).

nntplib je v Pythonu 3.13 odstranjen (PEP 594), zato lasten odjemalec na ssl + socket - samo to, kar pogon potrebuje:
pozdrav, AUTHINFO USER/PASS (RFC 4643), BODY in STAT po message-id (RFC 3977), QUIT.

- TLS vedno (privzeta vrata 563, nikoli 119): ssl.create_default_context() s preverbo potrdila IN imena gostitelja, TLS
  najmanj 1.2. Kontekst brez preverbe (CERT_NONE, check_hostname=False) se zavrne - tudi ce ga poda klicatelj.
- Bazen: privzeto 8, najvec 50 povezav (pogosta meja ponudnikov na racun, preverjeno 25. 10. 2026); vsaka povezava ima
  naenkrat eno zahtevo (brez cevovoda). Povezava, ki jo je streznik medtem zaprl (nedejavnost), se enkrat samodejno
  zamenja s svezo; prekinitev sredi BODY tudi. Pozdrav »zaseden« (prevec povezav) trajno zmanjsa bazen za eno mesto.
- Roki: povezava (TCP + TLS + pozdrav + prijava) in celotna zahteva imata vsak svoj rok do monotonega casa - streznik,
  ki posilja po kapljicah, zahteve ne zadrzi dlje od roka.
- Jasni izidi (NapakaNntp.izid): ni_clanka, prijava, zaseden, napaka_streznika, napaka_protokola, zaprto, omrezje, rok,
  potrdilo. Kode -> izid so skupne z Android-tv: tests/skupni-primeri/usenet-pogon.json (nntp_izid, nntp_telo).
- Geslo, uporabnisko ime in message-id NISO nikoli v dnevniku, izjemi ali repr; besedila odgovora streznika (lahko
  ponovi message-id) tudi ne. message-id pred posiljanjem preveri usenet_nzb.id_clanka (brez CR/LF - ukaza ni mogoce
  podaljsati).
"""

from __future__ import annotations

import logging
import socket
import ssl
import threading
import time
from typing import Callable, Optional

from .usenet_nzb import id_clanka

_log = logging.getLogger("safeer.usenet")

VRATA = 563
PRIVZETO_POVEZAV = 8
NAJVEC_POVEZAV = 50
NAJVEC_TELO_BAJTOV = 16 * 1024 * 1024
NAJVEC_VRSTICA_BAJTOV = 4096  # RFC 3977: odgovor najvec 512 oktetov - vec je napaka ali napad
ROK_POVEZAVE_S = 10.0
ROK_ZAHTEVE_S = 30.0
_BERI = 256 * 1024

OK = "ok"
GESLO = "geslo"
NI_CLANKA = "ni_clanka"
PRIJAVA = "prijava"
ZASEDEN = "zaseden"
NAPAKA_STREZNIKA = "napaka_streznika"
NAPAKA_PROTOKOLA = "napaka_protokola"
ZAPRTO = "zaprto"
OMREZJE = "omrezje"
ROK = "rok"
POTRDILO = "potrdilo"

_OK = {"POZDRAV": (200, 201), "AUTHINFO USER": (281,), "AUTHINFO PASS": (281,), "ARTICLE": (220,), "HEAD": (221,),
       "BODY": (222,), "STAT": (223,), "QUIT": (205,)}
_CLANEK = ("ARTICLE", "HEAD", "BODY", "STAT")


class NapakaNntp(Exception):
    """Izid zahteve NNTP. Sporocilo ima samo izid in kodo - nikoli poverilnic, message-id ali besedila streznika."""

    def __init__(self, izid: str, koda: int = 0):
        super().__init__(izid, koda)
        self.izid = izid
        self.koda = koda

    def __str__(self) -> str:
        return "usenet nntp: %s%s" % (self.izid, " (%d)" % self.koda if self.koda else "")

    def __repr__(self) -> str:
        return "NapakaNntp(%r, %d)" % (self.izid, self.koda)


def koda_vrstice(vrstica: str) -> Optional[int]:
    """Koda statusne vrstice: tri stevke s prvo 1-5, za njimi presledek ali konec. None = ni veljavna."""
    if len(vrstica) < 3 or vrstica[0] not in "12345" or not all("0" <= z <= "9" for z in vrstica[:3]):
        return None
    if len(vrstica) > 3 and vrstica[3] != " ":
        return None
    return int(vrstica[:3])


def izid_odgovora(ukaz: str, vrstica: str) -> str:
    """Statusna vrstica odgovora na [ukaz] -> izid. Ukazi: POZDRAV, AUTHINFO USER, AUTHINFO PASS, ARTICLE, HEAD, BODY,
    STAT, QUIT."""
    koda = koda_vrstice(vrstica)
    if koda is None:
        return NAPAKA_PROTOKOLA
    if koda in _OK.get(ukaz, ()):
        return OK
    if ukaz == "AUTHINFO USER" and koda == 381:
        return GESLO
    # Ponudniki »prevec povezav« javljajo z razlicnimi kodami (400, 481, 482, 502), besedilo pa vedno omeni povezave.
    if koda in (400, 481, 482, 502) and "connection" in vrstica[4:].lower():
        return ZASEDEN
    if koda in (423, 430) and ukaz in _CLANEK:
        return NI_CLANKA
    if koda in (480, 481, 482) or (koda == 502 and ukaz.startswith("AUTHINFO")):
        return PRIJAVA
    if koda in (400, 502):
        return ZASEDEN
    if koda == 403:
        return NAPAKA_STREZNIKA
    if koda == 205:
        return ZAPRTO
    return NAPAKA_PROTOKOLA


def konec_telesa(medpomnilnik, od: int = 0) -> int:
    """Indeks zacetka zakljucne vrstice '.' v telesu (bajti po statusni vrstici): -1 = je se ni. Telo brez vrstic = 0
    (medpomnilnik se zacne z '.\\r\\n'). Iskanje od [od] (sproti prebrani del)."""
    if medpomnilnik[:3] == b".\r\n":
        return 0
    k = medpomnilnik.find(b"\r\n.\r\n", max(0, od - 4))
    return -1 if k < 0 else k + 2


def brez_pik(telo: bytes) -> bytes:
    """Vrstica, ki se zacne z '..', izgubi eno piko (RFC 3977 3.1.1); druge ostanejo."""
    if telo.startswith(b".."):
        telo = telo[1:]
    return telo.replace(b"\r\n..", b"\r\n.")


def odpakiraj_telo(surovo: bytes) -> Optional[tuple]:
    """(telo brez podvojenih pik, ostanek po koncu) ali None, ce konca se ni."""
    k = konec_telesa(surovo)
    if k < 0:
        return None
    return brez_pik(bytes(surovo[:k])), bytes(surovo[k + 3:])


def varen_kontekst(kontekst: Optional[ssl.SSLContext] = None) -> ssl.SSLContext:
    """Kontekst TLS s preverbo potrdila in imena gostitelja, najmanj TLS 1.2. Brez preverbe: ValueError."""
    k = kontekst if kontekst is not None else ssl.create_default_context()
    if k.verify_mode != ssl.CERT_REQUIRED or not k.check_hostname:
        raise ValueError("usenet nntp: TLS brez preverbe potrdila in imena gostitelja ni dovoljen")
    if k.minimum_version < ssl.TLSVersion.TLSv1_2:
        k.minimum_version = ssl.TLSVersion.TLSv1_2
    return k


def _preveri_poverilnico(vrednost: Optional[str]) -> None:
    if vrednost is not None and (not isinstance(vrednost, str) or any(z in vrednost for z in "\r\n\x00")):
        raise ValueError("usenet nntp: neveljavna poverilnica")  # brez vrednosti


def _ukaz_z_id(ukaz: str, message_id: str) -> bytes:
    mid = id_clanka(message_id)
    if mid is None:
        raise ValueError("usenet nntp: neveljaven message-id")  # brez vrednosti
    return ("%s <%s>\r\n" % (ukaz, mid)).encode("ascii")


class Povezava:
    """Ena povezava NNTP prek TLS z eno zahtevo naenkrat (vzporednost ureja Bazen)."""

    def __init__(self, gostitelj: str, vrata: int = VRATA, uporabnik: Optional[str] = None, geslo: Optional[str] = None,
                 kontekst: Optional[ssl.SSLContext] = None, rok_povezave: float = ROK_POVEZAVE_S,
                 rok: float = ROK_ZAHTEVE_S):
        _preveri_poverilnico(uporabnik)
        _preveri_poverilnico(geslo)
        self.gostitelj = str(gostitelj)
        self.vrata = int(vrata)
        self.__uporabnik = uporabnik
        self.__geslo = geslo
        self._kontekst = varen_kontekst(kontekst)
        self._rok_povezave = float(rok_povezave)
        self._rok = float(rok)
        self._sock: Optional[ssl.SSLSocket] = None
        self._surov: Optional[socket.socket] = None  # med rokovanjem TLS (da ga prekini() lahko zbudi)
        self._prekinjeno = False
        self._medpomnilnik = bytearray()
        self.prijavljen = False

    def __repr__(self) -> str:
        return "Povezava(%s:%d, %s)" % (self.gostitelj, self.vrata, "odprta" if self.odprta else "zaprta")

    @property
    def odprta(self) -> bool:
        return self._sock is not None

    # -------------------------------------------------------------- nizka raven

    def _napaka(self, izid: str, koda: int = 0, vzrok: Optional[BaseException] = None) -> NapakaNntp:
        if izid != NI_CLANKA:
            self.zapri()
        (_log.debug if izid == NI_CLANKA else _log.info)(
            "usenet nntp: %s %s%s", self.gostitelj, izid,
            " (%s)" % type(vzrok).__name__ if vzrok else (" (%d)" % koda if koda else ""))
        return NapakaNntp(izid, koda)

    def _beri(self, konec: float) -> None:
        if self._prekinjeno:
            raise self._napaka(ZAPRTO)
        ostane = konec - time.monotonic()
        if ostane <= 0:
            raise self._napaka(ROK)
        try:
            self._sock.settimeout(ostane)
            kos = self._sock.recv(_BERI)
        except socket.timeout as e:
            raise self._napaka(ROK, vzrok=e) from None
        except OSError as e:
            raise self._napaka(OMREZJE, vzrok=e) from None
        if not kos:
            raise self._napaka(OMREZJE)  # streznik je zaprl povezavo
        self._medpomnilnik += kos

    def _poslji(self, podatki: bytes, konec: float) -> None:
        if self._prekinjeno:
            raise self._napaka(ZAPRTO)
        ostane = konec - time.monotonic()
        if ostane <= 0:
            raise self._napaka(ROK)
        try:
            self._sock.settimeout(ostane)
            self._sock.sendall(podatki)
        except socket.timeout as e:
            raise self._napaka(ROK, vzrok=e) from None
        except OSError as e:
            raise self._napaka(OMREZJE, vzrok=e) from None

    def _vrstica(self, konec: float) -> str:
        iskano = 0
        while True:
            k = self._medpomnilnik.find(b"\r\n", max(0, iskano - 1))
            if k >= 0:
                vrstica = bytes(self._medpomnilnik[:k])
                del self._medpomnilnik[:k + 2]
                return vrstica.decode("latin-1")
            if len(self._medpomnilnik) > NAJVEC_VRSTICA_BAJTOV:
                raise self._napaka(NAPAKA_PROTOKOLA)
            iskano = len(self._medpomnilnik)
            self._beri(konec)

    def _odgovor(self, ukaz: str, konec: float) -> tuple:
        vrstica = self._vrstica(konec)
        return izid_odgovora(ukaz, vrstica), koda_vrstice(vrstica) or 0

    def _telo(self, konec: float) -> bytes:
        iskano = 0
        while True:
            k = konec_telesa(self._medpomnilnik, iskano)
            if k > NAJVEC_TELO_BAJTOV:
                raise self._napaka(NAPAKA_PROTOKOLA)  # tudi celo telo, ki je prislo v enem kosu
            if k >= 0:
                telo = brez_pik(bytes(self._medpomnilnik[:k]))
                del self._medpomnilnik[:k + 3]
                return telo
            if len(self._medpomnilnik) > NAJVEC_TELO_BAJTOV:
                raise self._napaka(NAPAKA_PROTOKOLA)
            iskano = len(self._medpomnilnik)
            self._beri(konec)

    # -------------------------------------------------------------- povezava in prijava

    def odpri(self) -> None:
        """TCP + TLS (preverba potrdila in imena) + pozdrav + prijava, vse v roku povezave."""
        self.zapri()
        konec = time.monotonic() + self._rok_povezave
        try:
            surov = socket.create_connection((self.gostitelj, self.vrata), timeout=self._rok_povezave)
        except socket.timeout as e:
            raise self._napaka(ROK, vzrok=e) from None
        except OSError as e:
            raise self._napaka(OMREZJE, vzrok=e) from None
        self._surov = surov
        try:
            if self._prekinjeno:
                raise self._napaka(ZAPRTO)
            self._sock = self._kontekst.wrap_socket(surov, server_hostname=self.gostitelj)
        except NapakaNntp:
            surov.close()
            raise
        except ssl.SSLCertVerificationError as e:
            surov.close()
            raise self._napaka(POTRDILO, vzrok=e) from None
        except socket.timeout as e:
            surov.close()
            raise self._napaka(ROK, vzrok=e) from None
        except OSError as e:
            surov.close()
            raise self._napaka(ZAPRTO if self._prekinjeno else OMREZJE, vzrok=e) from None
        finally:
            self._surov = None
        izid, koda = self._odgovor("POZDRAV", konec)
        if izid != OK:
            raise self._napaka(izid, koda)
        if self.__uporabnik is not None:
            self._prijava(konec)

    def _prijava(self, konec: float) -> None:
        self._poslji(b"AUTHINFO USER " + self.__uporabnik.encode("utf-8") + b"\r\n", konec)
        izid, koda = self._odgovor("AUTHINFO USER", konec)
        if izid == GESLO:
            if self.__geslo is None:
                raise self._napaka(PRIJAVA, koda)
            self._poslji(b"AUTHINFO PASS " + self.__geslo.encode("utf-8") + b"\r\n", konec)
            izid, koda = self._odgovor("AUTHINFO PASS", konec)
        if izid != OK:
            raise self._napaka(izid, koda)
        self.prijavljen = True

    def prekini(self) -> None:
        """Iz druge niti: zbudi branje ali pisanje, ki caka na streznik (zapiranje bazena ne caka na rok zahteve).
        shutdown na ravni vticnika - SSLSocket.shutdown bi med branjem druge niti zamenjal _sslobj."""
        self._prekinjeno = True
        for s in (self._sock, self._surov):
            if s is not None:
                try:
                    socket.socket.shutdown(s, socket.SHUT_RDWR)
                except OSError:
                    pass

    def zapri(self, vljudno: bool = False) -> None:
        s, self._sock = self._sock, None
        self._medpomnilnik = bytearray()
        self.prijavljen = False
        if s is None:
            return
        if vljudno:
            try:
                s.settimeout(1.0)
                s.sendall(b"QUIT\r\n")
            except OSError:
                pass
        try:
            s.close()
        except OSError:
            pass

    # -------------------------------------------------------------- zahteve

    def _zahteva(self, ukaz: str, vrstica: bytes, z_telesom: bool) -> Optional[bytes]:
        if self._sock is None:
            self.odpri()
        konec = time.monotonic() + self._rok
        self._poslji(vrstica, konec)
        izid, koda = self._odgovor(ukaz, konec)
        if izid == PRIJAVA and not self.prijavljen and self.__uporabnik is not None:
            self._prijava(konec)  # streznik zahteva prijavo sele pri ukazu (RFC 4643 480)
            self._poslji(vrstica, konec)
            izid, koda = self._odgovor(ukaz, konec)
        if izid != OK:
            raise self._napaka(izid, koda)
        return self._telo(konec) if z_telesom else None

    def telo(self, message_id: str) -> bytes:
        """BODY: telo clanka brez podvojenih pik (za usenet_yenc.dekodiraj)."""
        return self._zahteva("BODY", _ukaz_z_id("BODY", message_id), True)

    def stat(self, message_id: str) -> bool:
        """STAT: ali clanek obstaja (430/423 = False)."""
        try:
            self._zahteva("STAT", _ukaz_z_id("STAT", message_id), False)
            return True
        except NapakaNntp as e:
            if e.izid == NI_CLANKA:
                return False
            raise


#: Izidi, pri katerih je stara (ponovno uporabljena) povezava verjetno mrtva - enkrat znova s svezo.
_ZNOVA_STARA = (OMREZJE, ROK, ZAPRTO, ZASEDEN, NAPAKA_PROTOKOLA)


class Bazen:
    """Bazen povezav NNTP do enega ponudnika. Varen za vec niti; vsaka povezava ima naenkrat eno zahtevo."""

    def __init__(self, gostitelj: str, vrata: int = VRATA, uporabnik: Optional[str] = None, geslo: Optional[str] = None,
                 povezav: int = PRIVZETO_POVEZAV, kontekst: Optional[ssl.SSLContext] = None,
                 rok_povezave: float = ROK_POVEZAVE_S, rok: float = ROK_ZAHTEVE_S):
        _preveri_poverilnico(uporabnik)
        _preveri_poverilnico(geslo)
        kontekst = varen_kontekst(kontekst)  # en kontekst za vse povezave (wrap_socket je varen za niti)
        self.gostitelj = str(gostitelj)
        self.vrata = int(vrata)
        self.najvec = max(1, min(NAJVEC_POVEZAV, int(povezav)))
        self._rok = float(rok)
        self.__nova: Callable[[], Povezava] = lambda: Povezava(gostitelj, vrata, uporabnik, geslo, kontekst,
                                                                 rok_povezave, rok)
        self._proste: list = []
        self._v_rabi: set = set()
        self._zaklep = threading.Lock()
        self._mesta = threading.Semaphore(self.najvec)
        self._zaprt = False
        self._prijava_zavrnjena = False

    def __repr__(self) -> str:
        return "Bazen(%s:%d, %d povezav)" % (self.gostitelj, self.vrata, self.najvec)

    def __enter__(self) -> "Bazen":
        return self

    def __exit__(self, *_a) -> None:
        self.zapri()

    def _vrni(self, p: Povezava) -> None:
        with self._zaklep:
            self._v_rabi.discard(p)
            if not self._zaprt and p.odprta:
                self._proste.append(p)
                return
        p.zapri(vljudno=True)

    def _izvedi(self, delo: Callable[[Povezava], object]):
        if self._zaprt:
            raise NapakaNntp(ZAPRTO)
        if self._prijava_zavrnjena:
            raise NapakaNntp(PRIJAVA)  # ne ponavljamo napacnega gesla (ponudnik bi racun zaklenil)
        if not self._mesta.acquire(timeout=self._rok):
            raise NapakaNntp(ROK)
        sprosti = True
        try:
            for poskus in (0, 1):
                with self._zaklep:
                    if self._zaprt:
                        raise NapakaNntp(ZAPRTO)
                    p = self._proste.pop() if self._proste else None
                    stara = p is not None
                    p = p or self.__nova()
                    self._v_rabi.add(p)
                try:
                    izid = delo(p)
                except NapakaNntp as e:
                    if e.izid == NI_CLANKA:
                        self._vrni(p)
                        raise
                    p.zapri()
                    self._vrni(p)
                    if self._zaprt:
                        raise NapakaNntp(ZAPRTO) from None  # bazen zaprt med zahtevo: ne odpiramo nove povezave
                    if e.izid == PRIJAVA:
                        self._prijava_zavrnjena = True
                        raise
                    if poskus == 0 and ((stara and e.izid in _ZNOVA_STARA) or e.izid == OMREZJE):
                        continue
                    if e.izid == ZASEDEN and not stara:
                        with self._zaklep:
                            if self.najvec > 1:
                                self.najvec -= 1
                                sprosti = False  # mesto ostane zasedeno: ponudnik ne dovoli toliko povezav
                    raise
                except BaseException:
                    p.zapri()  # nepricakovana napaka sredi zahteve: v medpomnilniku je lahko pol odgovora
                    self._vrni(p)
                    raise
                self._vrni(p)
                return izid
        finally:
            if sprosti:
                self._mesta.release()

    def telo(self, message_id: str) -> bytes:
        _ukaz_z_id("BODY", message_id)  # neveljaven id ne zasede povezave
        return self._izvedi(lambda p: p.telo(message_id))

    def stat(self, message_id: str) -> bool:
        _ukaz_z_id("STAT", message_id)
        return self._izvedi(lambda p: p.stat(message_id))

    def preveri(self) -> None:
        """Ena povezava s prijavo (»Preizkusi povezavo« v nastavitvah). Napaka: NapakaNntp."""
        def odpri(p: Povezava) -> None:
            if not p.odprta:
                p.odpri()
        self._izvedi(odpri)

    def zapri(self) -> None:
        """Zapre proste povezave in prekine zahteve v teku (te vrnejo ZAPRTO) - zapiranje ne caka na rok."""
        with self._zaklep:
            self._zaprt = True
            proste, self._proste = self._proste, []
            v_rabi = list(self._v_rabi)
        for p in proste:
            p.zapri(vljudno=True)
        for p in v_rabi:
            p.prekini()
