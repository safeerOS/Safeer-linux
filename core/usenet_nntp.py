"""Odjemalec NNTP prek TLS za lasten pogon Usenet (lastnik 25. 10. 2026 22:10: neposredno predvajanje z Useneta).

nntplib je v Pythonu 3.13 odstranjen (PEP 594), zato lasten odjemalec na ssl + socket - samo to, kar pogon potrebuje:
pozdrav, AUTHINFO USER/PASS (RFC 4643), BODY in STAT po message-id (RFC 3977), QUIT.

- TLS vedno (privzeta vrata 563, nikoli 119): ssl.create_default_context() s preverbo potrdila IN imena gostitelja, TLS
  najmanj 1.2. Kontekst brez preverbe (CERT_NONE, check_hostname=False) se zavrne - tudi ce ga poda klicatelj.
- Bazen: privzeto 8, najvec 50 povezav (pogosta meja ponudnikov na racun, preverjeno 25. 10. 2026); vsaka povezava ima
  naenkrat eno zahtevo (brez cevovoda). Povezava, ki jo je streznik medtem zaprl (nedejavnost), se enkrat samodejno
  zamenja s svezo; prekinitev sredi BODY tudi. Kaj naredi po napaki, pove ukrep_bazena (skupni primeri nntp_ukrep).
- Zaklep racuna (lastnik 26. 10. 2026 03:05: »Nevarnost zaklepa racuna je prioriteta«): dokler prijava ne uspe (in ni
  nobene prijavljene povezave), se odpira ena sama povezava naenkrat - napacno geslo pride do streznika enkrat, tudi pri
  8 hkratnih zahtevah. Zavrnjena prijava ustavi bazen (vse povezave zaprte) in zapre racun za ves proces, dokler
  uporabnik poverilnic ne vpise znova (dovoli_prijavo_znova). »Prevec povezav« bazen skrci na sprejete povezave in
  zacne premor novih povezav (nov_premor) - nikoli nov poskus prijave v zanki.
- Roki: povezava (TCP + TLS + pozdrav + prijava) in celotna zahteva imata vsak svoj rok do monotonega casa - streznik,
  ki posilja po kapljicah, zahteve ne zadrzi dlje od roka.
- Jasni izidi (NapakaNntp.izid): ni_clanka, prijava, zaseden, napaka_streznika, napaka_protokola, zaprto, omrezje, rok,
  potrdilo. Kode -> izid so skupne z Android-tv: tests/skupni-primeri/usenet-pogon.json (nntp_izid, nntp_telo).
- Geslo, uporabnisko ime in message-id NISO nikoli v dnevniku, izjemi ali repr; besedila odgovora streznika (lahko
  ponovi message-id) tudi ne. message-id pred posiljanjem preveri usenet_nzb.id_clanka (brez CR/LF - ukaza ni mogoce
  podaljsati).
"""

from __future__ import annotations

import hashlib
import logging
import os
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
#: Telo clanka (surovo). Izmerjeno 25. 10. 2026 na 5 pravih NZB (prototip): clanek povprecno 384-719 KiB;
#: 4 MiB je vec kot 5x najvecji, a 8 povezav x 4 MiB se vedno ustreze pomnilniku TV (skupni primeri: telo_bajtov).
NAJVEC_TELO_BAJTOV = 4 * 1024 * 1024
NAJVEC_VRSTICA_BAJTOV = 4096  # RFC 3977: odgovor najvec 512 oktetov - vec je napaka ali napad
NAJVEC_POVERILNICA_BAJTOV = 400  # RFC 3977: ukaz najvec 512 oktetov z »AUTHINFO PASS « in CRLF
#: Prosta povezava, nedejavna dlje od tega, se zapre (RFC 3977 priporoca vsaj 3 min; ponudniki zapirajo prej).
PROSTA_NAJDLJE_S = 60.0
#: Premor novih povezav po »prevec povezav« (ali zacasni napaki streznika): od 10 s, podvojen do 300 s.
PREMOR_OD_S = 10.0
PREMOR_BREZ_ODPRTIH_S = 60.0  # ni nobene druge odprte povezave, ki bi se sprostila
PREMOR_DO_S = 300.0
#: Bazen, zmanjsan zaradi meje povezav, po 10 min brez nove meje spet dobi eno mesto (druga naprava je morda koncala).
RAST_BAZENA_S = 600.0
#: Skupen proracun teles clankov na bazen (namizje; Android ima manj): 50 povezav x 4 MiB bi bilo 200 MiB samo
#: medpomnilnikov (pregled Grok 37 C7). Obicajen clanek (<1 MiB) ne caka nikoli.
PRORACUN_BAJTOV = 64 * 1024 * 1024
#: Osnova, ki jo zaseze vsako telo: clanek do ~1,25 MiB (izmerjeno 384-719 KiB) ne potrebuje vec.
OSNOVA_TELESA = 1536 * 1024
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
DOSTOP = "dostop"
OMREZJE = "omrezje"
ROK = "rok"
POTRDILO = "potrdilo"

_OK = {"POZDRAV": (200, 201), "AUTHINFO USER": (281,), "AUTHINFO PASS": (281,), "ARTICLE": (220,), "HEAD": (221,),
       "BODY": (222,), "STAT": (223,), "QUIT": (205,)}
_CLANEK = ("ARTICLE", "HEAD", "BODY", "STAT")
_AUTHINFO = ("AUTHINFO USER", "AUTHINFO PASS")
_MEJA = ("too many", "limit", "max", "exceed", "no more")
_ZAKLEP = ("lock", "ban", "block", "attempt", "suspend", "expire", "disable")
_NI_MEJA = ("fail", "pass", "invalid", "incorrect", "wrong") + _ZAKLEP

# Faze povezave za ukrep_bazena: povezava (TCP, TLS, pozdrav - nic AUTHINFO), prijava (od AUTHINFO USER do 281), ukaz.
FAZA_POVEZAVA = "povezava"
FAZA_PRIJAVA = "prijava"
FAZA_UKAZ = "ukaz"

# Ukrepi bazena (skupni primeri nntp_ukrep).
VRNI = "vrni"
ZNOVA = "znova"
NAPAKA = "napaka"
ZMANJSAJ_POCAKAJ = "zmanjsaj_pocakaj"
POCAKAJ = "pocakaj"
NEZNANA_PRIJAVA = "neznana_prijava"
USTAVI_RACUN = "ustavi_racun"
USTAVI_BAZEN = "ustavi_bazen"


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


def meja_povezav(besedilo: str) -> bool:
    """Ali besedilo odgovora jasno pove mejo povezav (»too many connections«). Ce omenja tudi napacno prijavo ali
    zaklep, NI meja: dvom pomeni zavrnjeno prijavo, ki se ne ponovi (lastnik 26. 10. 2026: zaklep je prioriteta)."""
    t = besedilo.lower()
    if any(b in t for b in _NI_MEJA):
        return False
    return "connection limit" in t or ("connections" in t and any(b in t for b in _MEJA))


def izid_odgovora(ukaz: str, vrstica: str, prijava_uspela: bool = False) -> str:
    """Statusna vrstica odgovora na [ukaz] -> izid. Ukazi: POZDRAV, AUTHINFO USER, AUTHINFO PASS, ARTICLE, HEAD, BODY,
    STAT, QUIT. Pri AUTHINFO je vse razen 281/381 in meje povezav PRIJAVA (RFC 4643 2.3.2: 481 zavrnjeno, 482 napacen
    vrstni red, 502 ni dovoljeno) - »481 Authentication failed for this connection« ni meja povezav. [prijava_uspela]:
    ista prijava je v bazenu ze uspela in prijavljena povezava je odprta - takrat je 480/481/502 meja povezav (ponudnik,
    uradna pomoc: prevec povezav = napaka prijave 480), razen ce besedilo omenja zaklep ali poskuse."""
    koda = koda_vrstice(vrstica)
    avtor = ukaz in _AUTHINFO
    if koda is None:
        return PRIJAVA if avtor else NAPAKA_PROTOKOLA
    if koda in _OK.get(ukaz, ()):
        return OK
    if ukaz == "AUTHINFO USER" and koda == 381:
        return GESLO
    if koda in (400, 480, 481, 482, 502) and meja_povezav(vrstica[4:]):
        return ZASEDEN
    if avtor:
        zaklep = any(b in vrstica[4:].lower() for b in _ZAKLEP)
        return ZASEDEN if prijava_uspela and koda in (480, 481, 502) and not zaklep else PRIJAVA
    if koda in (423, 430) and ukaz in _CLANEK:
        return NI_CLANKA
    if koda in (480, 481, 482):
        return PRIJAVA
    if koda == 400:
        return NAPAKA_STREZNIKA if ukaz == "POZDRAV" else ZAPRTO  # RFC 3977: zacasno / streznik zapira povezavo
    if koda == 502:
        return DOSTOP  # RFC 3977: trajno ali brez pravic - ponovitev ne pomaga
    if koda == 403:
        return NAPAKA_STREZNIKA
    if koda == 205:
        return ZAPRTO
    return NAPAKA_PROTOKOLA


def ukrep_bazena(izid: str, faza: str, stara: bool, poskus: int) -> str:
    """Kaj bazen naredi po napaki [izid] v [faza] (skupni primeri nntp_ukrep; Android isto). [stara] = povezava iz
    bazena, [poskus] 0 ali 1. Ponovitev (ZNOVA) je vedno z novo povezavo; po AUTHINFO nikoli ponovitev v zanki."""
    if faza == FAZA_POVEZAVA:
        if izid == OMREZJE:
            return ZNOVA if poskus == 0 else NAPAKA
        return {ZASEDEN: ZMANJSAJ_POCAKAJ, NAPAKA_STREZNIKA: POCAKAJ, DOSTOP: USTAVI_BAZEN, POTRDILO: USTAVI_BAZEN,
                PRIJAVA: USTAVI_RACUN}.get(izid, NAPAKA)
    if faza == FAZA_PRIJAVA:
        if izid == ZASEDEN:
            return ZMANJSAJ_POCAKAJ
        if izid in (OMREZJE, ROK, ZAPRTO, NAPAKA_PROTOKOLA):
            return NEZNANA_PRIJAVA  # geslo je morda prislo do streznika, odgovora pa ni
        return USTAVI_RACUN
    if izid == NI_CLANKA:
        return VRNI
    if izid == PRIJAVA:
        return USTAVI_RACUN
    if izid in (DOSTOP, POTRDILO):
        return USTAVI_BAZEN
    if izid == ZASEDEN:
        return ZNOVA if stara and poskus == 0 else ZMANJSAJ_POCAKAJ
    if izid in (OMREZJE, NAPAKA_STREZNIKA):
        return ZNOVA if poskus == 0 else NAPAKA
    return ZNOVA if stara and poskus == 0 else NAPAKA


def sme_odpreti(ustavljen: bool, premor: bool, odprtih: int, najvec: int, uspela: bool, sonda: bool) -> bool:
    """Ali bazen sme odpreti novo povezavo (skupni primeri nntp_sme_odpreti): dokler prijava ni uspela (ali ni nobena
    prijavljena povezava odprta), se odpira ena sama povezava naenkrat (sonda): napacno geslo gre k strezniku enkrat.
    """
    if ustavljen or premor or odprtih >= najvec:
        return False
    return True if uspela else not sonda


def nov_premor(najvec: int, odprtih: int, premor_s: float, tece: bool, zmanjsaj: bool) -> tuple:
    """(najvec, premor_s) po meji povezav ali zacasni napaki (skupni primeri nntp_premor). [odprtih] = DRUGE prijavljene
    odprte povezave (te je streznik sprejel): bazen pade nanje, najmanj 1 - hkratne zavrnitve ga ne skrcijo pod to.
    Premor 10 s ali 60 s (ni nobene druge), nato dvakrat daljsi do 300 s; [tece] (ista nesreca) ga ne podaljsa."""
    if zmanjsaj:
        najvec = max(1, min(najvec, odprtih))
    if tece:
        return najvec, premor_s
    if premor_s > 0:
        premor_s = min(PREMOR_DO_S, 2 * premor_s)
    else:
        premor_s = PREMOR_OD_S if odprtih > 0 else PREMOR_BREZ_ODPRTIH_S
    return najvec, premor_s


def varna_poverilnica(vrednost: object) -> bool:
    """Argument AUTHINFO (skupni primeri nntp_poverilnica): 1-400 bajtov UTF-8, brez znakov pod 0x20 in 0x7F."""
    if not isinstance(vrednost, str) or any(z < " " or z == "\x7f" for z in vrednost):
        return False
    try:
        n = len(vrednost.encode("utf-8"))
    except UnicodeEncodeError:  # osamljen nadomestni znak
        return False
    return 1 <= n <= NAJVEC_POVERILNICA_BAJTOV


def id_odgovora_ustreza(vrstica: str, message_id: str) -> bool:
    """Ali odgovor 222/223 velja za zahtevani clanek (skupni primeri nntp_id_odgovora): prvi <...> mora biti id."""
    i = vrstica.find("<")
    j = vrstica.find(">", i + 1) if i >= 0 else -1
    return i < 0 or j < 0 or vrstica[i + 1:j] == message_id


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
    if vrednost is not None and not varna_poverilnica(vrednost):
        raise ValueError("usenet nntp: neveljavna poverilnica")  # brez vrednosti (UnicodeError bi nosil celo vrednost)


def _preveri_gostitelja(gostitelj: object, vrata: object) -> None:
    """Gostitelj in vrata pred vsako povezavo (Grok 37 C8): sicer OverflowError, UnicodeError ali ValueError mimo
    NapakaNntp; »uporabnik:geslo@news.x« ali kljuc kot gostitelj ne gre v DNS. Sporocilo brez vrednosti."""
    g = gostitelj if isinstance(gostitelj, str) else ""
    if not 1 <= len(g) <= 253 or any(z in g for z in "@/\\ \t\r\n\x00[]"):
        raise ValueError("usenet nntp: neveljaven gostitelj")
    try:
        g.encode("idna")
        v = int(vrata)  # type: ignore[call-overload]
    except (UnicodeError, ValueError, TypeError):
        raise ValueError("usenet nntp: neveljaven gostitelj ali vrata") from None
    if not 1 <= v <= 65535:
        raise ValueError("usenet nntp: neveljavna vrata")


def _ukaz_z_id(ukaz: str, message_id: str) -> bytes:
    mid = id_clanka(message_id)
    if mid is None:
        raise ValueError("usenet nntp: neveljaven message-id")  # brez vrednosti
    return ("%s <%s>\r\n" % (ukaz, mid)).encode("ascii")


class Proracun:
    """Skupen proracun pomnilnika teles v bazenu (pregled Grok 37 C7, 35 Y3). Vsako telo pred branjem zaseze OSNOVO;
    vecje telo vzame se edini zeton rasti (prostor do NAJVEC_TELO_BAJTOV). Nihce ne caka, medtem ko drzi del rasti,
    zato zastoja ni: osnove imajo svoj del proracuna, rast pa vedno ima svojega (prej je zasezanje po delih 6 hkratnih
    teles po 1,2 MiB v 3 MiB zaklenilo do roka). Steje medpomnilnik telesa; statusna vrstica (do 256 KiB na povezavo) in
    kratkotrajna kopija ob vrnitvi nista steti."""

    def __init__(self, bajtov: int):
        self.osnova = OSNOVA_TELESA
        self.rast = max(0, NAJVEC_TELO_BAJTOV + _BERI - self.osnova)
        self.bajtov = max(int(bajtov), self.osnova + self.rast)
        self._osnov = 0
        self._rast = False
        self.najvec_zasedeno = 0  # za meritev in preizkus
        self._pogoj = threading.Condition(threading.Lock())

    @property
    def zasedeno(self) -> int:
        return self._osnov * self.osnova + (self.rast if self._rast else 0)

    def _cakaj(self, pogoj: Callable[[], bool], konec: float) -> bool:
        while not pogoj():
            ostane = konec - time.monotonic()
            if ostane <= 0:
                return False
            self._pogoj.wait(ostane)
        return True

    def zasezi(self, konec: float) -> bool:
        """Osnova za eno telo; False = ni prostora do [konec]."""
        with self._pogoj:
            if not self._cakaj(lambda: (self._osnov + 1) * self.osnova + self.rast <= self.bajtov, konec):
                return False
            self._osnov += 1
            self.najvec_zasedeno = max(self.najvec_zasedeno, self.zasedeno)
            return True

    def rasti(self, konec: float) -> bool:
        """Zeton rasti (telo vecje od osnove); drzi ga ena nit naenkrat."""
        with self._pogoj:
            if not self._cakaj(lambda: not self._rast, konec):
                return False
            self._rast = True
            self.najvec_zasedeno = max(self.najvec_zasedeno, self.zasedeno)
            return True

    def sprosti(self, rast: bool) -> None:
        with self._pogoj:
            self._osnov -= 1
            if rast:
                self._rast = False
            self._pogoj.notify_all()


class Povezava:
    """Ena povezava NNTP prek TLS z eno zahtevo naenkrat (vzporednost ureja Bazen)."""

    def __init__(self, gostitelj: str, vrata: int = VRATA, uporabnik: Optional[str] = None, geslo: Optional[str] = None,
                 kontekst: Optional[ssl.SSLContext] = None, rok_povezave: float = ROK_POVEZAVE_S,
                 rok: float = ROK_ZAHTEVE_S, pred_prijavo: Optional[Callable[[], tuple]] = None,
                 proracun: Optional[Proracun] = None):
        _preveri_poverilnico(uporabnik)
        _preveri_poverilnico(geslo)
        _preveri_gostitelja(gostitelj, vrata)
        self.gostitelj = str(gostitelj)
        self.vrata = int(vrata)
        self.__uporabnik = uporabnik
        self.__geslo = geslo
        self._kontekst = varen_kontekst(kontekst)
        self._rok_povezave = float(rok_povezave)
        self._rok = float(rok)
        self._sock: Optional[ssl.SSLSocket] = None
        self._surov: Optional[socket.socket] = None  # med vzpostavljanjem TCP (da ga prekini() lahko zbudi)
        self._prekinjeno = False
        self._medpomnilnik = bytearray()
        self._zadnja_vrstica = ""
        self.prijavljen = False
        #: Bazen: (ovira ali None, prijava_uspela) tik pred AUTHINFO - zavrnjen racun ne dobi gesla niti iz povezave,
        #: ki se je odpirala vzporedno.
        self._pred_prijavo = pred_prijavo
        self._proracun = proracun
        self.faza = FAZA_POVEZAVA  # kje je zadnja napaka nastala (ukrep_bazena)
        self.pripravljena = False  # pozdrav in prijava sta uspela
        self.sonda = False  # bazen: ta povezava je edina, ki se odpira, dokler prijava ne uspe
        self.zadnja_raba = 0.0

    def __repr__(self) -> str:
        return "Povezava(%s:%d, %s)" % (self.gostitelj, self.vrata, "odprta" if self.odprta else "zaprta")

    @property
    def odprta(self) -> bool:
        return self._sock is not None

    # -------------------------------------------------------------- nizka raven

    def _napaka(self, izid: str, koda: int = 0, vzrok: Optional[BaseException] = None) -> NapakaNntp:
        if izid != NI_CLANKA:
            self.zapri()
        # Brez gostitelja (ponudnik je zaseben podatek - Grok 37 C8), poverilnic, id in besedila streznika.
        (_log.debug if izid == NI_CLANKA else _log.info)(
            "usenet nntp: %s%s", izid, " (%s)" % type(vzrok).__name__ if vzrok else (" (%d)" % koda if koda else ""))
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
            if k > NAJVEC_VRSTICA_BAJTOV:
                raise self._napaka(NAPAKA_PROTOKOLA)  # tudi, ce je CRLF prisel v istem branju (Grok 37 C7)
            if k >= 0:
                vrstica = bytes(self._medpomnilnik[:k])
                del self._medpomnilnik[:k + 2]
                return vrstica.decode("latin-1")
            if len(self._medpomnilnik) > NAJVEC_VRSTICA_BAJTOV:
                raise self._napaka(NAPAKA_PROTOKOLA)
            iskano = len(self._medpomnilnik)
            self._beri(konec)

    def _odgovor(self, ukaz: str, konec: float, prijava_uspela: bool = False) -> tuple:
        vrstica = self._vrstica(konec)
        self._zadnja_vrstica = vrstica
        return izid_odgovora(ukaz, vrstica, prijava_uspela), koda_vrstice(vrstica) or 0

    def _telo(self, konec: float) -> bytes:
        if self._proracun is not None and not self._proracun.zasezi(konec):
            raise self._napaka(ROK)
        rast = False
        try:
            iskano = 0
            while True:
                k = konec_telesa(self._medpomnilnik, iskano)
                if k > NAJVEC_TELO_BAJTOV:
                    raise self._napaka(NAPAKA_PROTOKOLA)  # tudi celo telo, ki je prislo v enem kosu
                if k >= 0:
                    with memoryview(self._medpomnilnik)[:k] as m:
                        telo = brez_pik(bytes(m))  # ena kopija (bytes(bytearray[:k]) bi naredil dve)
                    del self._medpomnilnik[:k + 3]
                    return telo
                if len(self._medpomnilnik) > NAJVEC_TELO_BAJTOV:
                    raise self._napaka(NAPAKA_PROTOKOLA)
                if (self._proracun is not None and not rast
                        and len(self._medpomnilnik) + _BERI > self._proracun.osnova):
                    if not self._proracun.rasti(konec):
                        raise self._napaka(ROK)
                    rast = True
                iskano = len(self._medpomnilnik)
                self._beri(konec)
        finally:
            if self._proracun is not None:
                self._proracun.sprosti(rast)

    # -------------------------------------------------------------- povezava in prijava

    def _povezi(self, konec: float) -> socket.socket:
        """TCP v roku [konec]. Vticnik je v self._surov PRED connect: prekini() ga zbudi s shutdown (izmerjeno 26. 10.
        2026 na prenosniku: shutdown konca cakajoci connect v 0,5 s, close ga ne - caka do roka). DNS (getaddrinfo)
        ostane brez lastnega roka in neprekinljiv."""
        try:
            naslovi = socket.getaddrinfo(self.gostitelj, self.vrata, type=socket.SOCK_STREAM)
        except (OSError, UnicodeError) as e:
            raise self._napaka(OMREZJE, vzrok=e) from None
        zadnja: tuple = (OMREZJE, None)
        for i, (druzina, vrsta, proto, _, naslov) in enumerate(naslovi):
            ostane = konec - time.monotonic()
            if ostane <= 0:
                raise self._napaka(ROK)
            s = socket.socket(druzina, vrsta, proto)
            self._surov = s
            try:
                if self._prekinjeno:
                    raise self._napaka(ZAPRTO)
                s.settimeout(max(1.0, ostane / (len(naslovi) - i)) if i < len(naslovi) - 1 else ostane)
                s.connect(naslov)
                return s
            except NapakaNntp:
                s.close()
                raise
            except socket.timeout as e:
                s.close()
                zadnja = (ROK, e)
            except OSError as e:
                s.close()
                zadnja = (ZAPRTO if self._prekinjeno else OMREZJE, e)
            finally:
                self._surov = None
        raise self._napaka(zadnja[0], vzrok=zadnja[1])

    def odpri(self) -> None:
        """TCP + TLS (preverba potrdila in imena) + pozdrav + prijava, vse v roku povezave. prekini() iz druge niti
        zbudi vsak korak razen DNS (pregled Grok 37 C3: prej je rokovanje TLS cakalo do roka)."""
        self.zapri()
        self.faza = FAZA_POVEZAVA
        konec = time.monotonic() + self._rok_povezave
        surov = self._povezi(konec)
        try:
            if self._prekinjeno:
                raise self._napaka(ZAPRTO)
            # do_handshake_on_connect=False: SSLSocket je v self._sock PRED rokovanjem, zato ga prekini() zbudi
            # (wrap_socket surovi vticnik odklopi - shutdown nanj bi bil EBADF).
            s = self._kontekst.wrap_socket(surov, server_hostname=self.gostitelj, do_handshake_on_connect=False)
            self._sock = s
            if self._prekinjeno:
                raise self._napaka(ZAPRTO)
            s.settimeout(max(0.001, konec - time.monotonic()))
            s.do_handshake()
        except NapakaNntp:
            surov.close()
            raise
        except ssl.SSLCertVerificationError as e:
            surov.close()
            raise self._napaka(POTRDILO, vzrok=e) from None
        except socket.timeout as e:
            surov.close()
            raise self._napaka(ZAPRTO if self._prekinjeno else ROK, vzrok=e) from None
        except OSError as e:
            surov.close()
            raise self._napaka(ZAPRTO if self._prekinjeno else OMREZJE, vzrok=e) from None
        izid, koda = self._odgovor("POZDRAV", konec)
        if izid != OK:
            raise self._napaka(izid, koda)
        if self.__uporabnik is not None:
            self._prijava(konec)
        self.faza = FAZA_UKAZ
        self.pripravljena = True

    def _prijava(self, konec: float) -> None:
        ovira, uspela = self._pred_prijavo() if self._pred_prijavo is not None else (None, False)
        if ovira is not None:
            raise self._napaka(ovira)  # racun zavrnjen ali bazen zaprt: geslo ne gre k strezniku
        self.faza = FAZA_PRIJAVA
        self._poslji(b"AUTHINFO USER " + self.__uporabnik.encode("utf-8") + b"\r\n", konec)
        izid, koda = self._odgovor("AUTHINFO USER", konec, uspela)
        if izid == GESLO:
            if self.__geslo is None:
                raise self._napaka(PRIJAVA, koda)
            self._poslji(b"AUTHINFO PASS " + self.__geslo.encode("utf-8") + b"\r\n", konec)
            izid, koda = self._odgovor("AUTHINFO PASS", konec, uspela)
        if izid != OK:
            raise self._napaka(ZASEDEN if izid == ZASEDEN else PRIJAVA, koda)
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
        self.pripravljena = False
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

    def _zahteva(self, ukaz: str, vrstica: bytes, z_telesom: bool, mid: str) -> Optional[bytes]:
        if self._sock is None:
            self.odpri()
        konec = time.monotonic() + self._rok
        self._poslji(vrstica, konec)
        izid, koda = self._odgovor(ukaz, konec)
        # 480 pri ukazu NI povod za novo prijavo (prijava je ze bila ob odprtju): PRIJAVA ustavi bazen - geslo nikoli
        # ne gre k strezniku mimo vrat bazena (sonda, zapah).
        if izid != OK:
            raise self._napaka(izid, koda)
        if not id_odgovora_ustreza(self._zadnja_vrstica, mid):
            raise self._napaka(NAPAKA_PROTOKOLA, koda)  # odgovor za drug clanek (Grok 37 C9): povezava ni usklajena
        telo = self._telo(konec) if z_telesom else None
        if self._medpomnilnik:
            self.zapri()  # bajti za koncem odgovora: brez cevovoda jih ne sme biti - povezava ne gre v bazen
        return telo

    def telo(self, message_id: str) -> bytes:
        """BODY: telo clanka brez podvojenih pik (za usenet_yenc.dekodiraj)."""
        return self._zahteva("BODY", _ukaz_z_id("BODY", message_id), True, id_clanka(message_id))

    def stat(self, message_id: str) -> bool:
        """STAT: ali clanek obstaja (430/423 = False)."""
        try:
            self._zahteva("STAT", _ukaz_z_id("STAT", message_id), False, id_clanka(message_id))
            return True
        except NapakaNntp as e:
            if e.izid == NI_CLANKA:
                return False
            raise


#: Racuni (gostitelj, ime, geslo), ki jim je ponudnik zavrnil prijavo - samo v pomnilniku procesa, kot odtis s
#: sljo procesa (nikoli geslo). Nov Bazen z istimi poverilnicami ne poskusi znova (U-4); usklajevanje zapaha med
#: napravami kroga je korak 3.
_ZAVRNJENI: set = set()
_ZAVRNJENI_ZAKLEP = threading.Lock()
_SOL = os.urandom(16)


def _odtis_racuna(gostitelj: str, uporabnik: Optional[str], geslo: Optional[str]) -> Optional[bytes]:
    if uporabnik is None:
        return None
    h = hashlib.sha256(_SOL)
    for x in (str(gostitelj).strip().lower(), uporabnik, geslo or ""):
        b = x.encode("utf-8", "surrogatepass")
        h.update(len(b).to_bytes(4, "big") + b)
    return h.digest()


def prijava_zavrnjena(gostitelj: str, uporabnik: Optional[str], geslo: Optional[str]) -> bool:
    """Ali je ponudnik te poverilnice ze zavrnil (do ponovnega vpisa jih ne posiljamo)."""
    o = _odtis_racuna(gostitelj, uporabnik, geslo)
    with _ZAVRNJENI_ZAKLEP:
        return o is not None and o in _ZAVRNJENI


def dovoli_prijavo_znova(gostitelj: str, uporabnik: Optional[str], geslo: Optional[str]) -> None:
    """Uporabnik je poverilnice vpisal znova (tudi enake - npr. po podaljsanju narocnine): en nov poskus prijave je spet
    dovoljen. Klice ga samo izrecno dejanje uporabnika (shrani v nastavitvah), nikoli samodejno."""
    o = _odtis_racuna(gostitelj, uporabnik, geslo)
    with _ZAVRNJENI_ZAKLEP:
        _ZAVRNJENI.discard(o)


class Bazen:
    """Bazen povezav NNTP do enega ponudnika. Varen za vec niti; vsaka povezava ima naenkrat eno zahtevo.

    Vrata za nove povezave (sme_odpreti): dokler prijava ni uspela in ni prijavljene povezave, se odpira ena sama
    (sonda); po uspehu vzporedno do [najvec]. Ukrep po napaki je ukrep_bazena (skupni primeri nntp_ukrep)."""

    def __init__(self, gostitelj: str, vrata: int = VRATA, uporabnik: Optional[str] = None, geslo: Optional[str] = None,
                 povezav: int = PRIVZETO_POVEZAV, kontekst: Optional[ssl.SSLContext] = None,
                 rok_povezave: float = ROK_POVEZAVE_S, rok: float = ROK_ZAHTEVE_S,
                 proracun_bajtov: int = PRORACUN_BAJTOV):
        _preveri_poverilnico(uporabnik)
        _preveri_poverilnico(geslo)
        _preveri_gostitelja(gostitelj, vrata)
        kontekst = varen_kontekst(kontekst)  # en kontekst za vse povezave (wrap_socket je varen za niti)
        self.gostitelj = str(gostitelj)
        self.vrata = int(vrata)
        self._zgornja = max(1, min(NAJVEC_POVEZAV, int(povezav)))
        self.najvec = self._zgornja
        self._rok = float(rok)
        self._racun = _odtis_racuna(self.gostitelj, uporabnik, geslo)
        self.proracun = Proracun(proracun_bajtov)  # najmanj ena osnova in rast
        self.__nova: Callable[[], Povezava] = lambda: Povezava(gostitelj, vrata, uporabnik, geslo, kontekst,
                                                                 rok_povezave, rok, self._pred_prijavo, self.proracun)
        self._proste: list = []
        self._v_rabi: set = set()
        self._pogoj = threading.Condition(threading.Lock())
        self._zaprt = False
        self._ustavljen: Optional[str] = PRIJAVA if prijava_zavrnjena(self.gostitelj, uporabnik, geslo) else None
        self._sonda = False
        self._premor_s = 0.0
        self._premor_do = 0.0
        self._premor_izid = ZASEDEN
        self._zadnja_meja = 0.0
        self._neznanih_prijav = 0

    def __repr__(self) -> str:
        return "Bazen(%s:%d, %d povezav)" % (self.gostitelj, self.vrata, self.najvec)

    def __enter__(self) -> "Bazen":
        return self

    def __exit__(self, *_a) -> None:
        self.zapri()

    # -------------------------------------------------------------- stanje (vse pod self._pogoj)

    def _vse(self) -> list:
        return self._proste + list(self._v_rabi)

    def _prijavljenih(self) -> int:
        return sum(1 for x in self._vse() if x.pripravljena and x.odprta)

    def _pred_prijavo(self) -> tuple:
        """Povezava tik pred AUTHINFO: (ovira, prijava_uspela)."""
        with self._pogoj:
            if self._zaprt:
                return ZAPRTO, False
            if self._ustavljen is not None:
                return self._ustavljen, False
            return None, self._prijavljenih() > 0

    def nastavi_najvec(self, povezav: int) -> None:
        """Zgornja meja povezav od zunaj (korak 3: proracun povezav med napravami kroga, U-1). Zmanjsanje zapre odvecne
        proste povezave; povecanje velja takoj, razen ce je bazen zmanjsal ponudnik (rast po RAST_BAZENA_S)."""
        with self._pogoj:
            self._zgornja = max(1, min(NAJVEC_POVEZAV, int(povezav)))
            if self.najvec > self._zgornja or not self._zadnja_meja:
                self.najvec = self._zgornja
            odvec = self._odvec()
            self._pogoj.notify_all()
        for x in odvec:
            x.zapri(vljudno=True)

    def _odvec(self) -> list:
        """Proste povezave nad [najvec] (zapre jih klicatelj izven zaklepa)."""
        odvec = []
        while self._proste and self._prijavljenih() > self.najvec:  # povezave v odpiranju se ne stejejo
            odvec.append(self._proste.pop(0))
        return odvec

    def _vzemi(self, rok_do: float, sveza: bool = False) -> tuple:
        """(povezava, stara). Prosta povezava ali nova, ce jo vrata dovolijo; sicer caka do [rok_do]. [sveza]: drugi
        poskus vedno z novo povezavo - po premoru so lahko mrtve vse proste (pregled Grok 37 C1)."""
        zavrzi: list = []
        try:
            return self.__vzemi(rok_do, sveza, zavrzi)
        finally:
            for x in zavrzi:
                x.zapri(vljudno=True)

    def __vzemi(self, rok_do: float, sveza: bool, zavrzi: list) -> tuple:
        with self._pogoj:
            while True:
                if self._zaprt:
                    raise NapakaNntp(ZAPRTO)
                if self._ustavljen is not None:
                    raise NapakaNntp(self._ustavljen)
                zdaj = time.monotonic()
                if self.najvec < self._zgornja and self._zadnja_meja and zdaj - self._zadnja_meja >= RAST_BAZENA_S:
                    self.najvec += 1  # druga naprava je morda koncala: eno mesto nazaj na 10 min
                    self._zadnja_meja = zdaj
                # Ponudniki zapirajo nedejavne povezave (RFC 3977: streznik naj caka vsaj 3 min), NAT jih pozabi tiho:
                # prosta povezava, nedejavna dlje od PROSTA_NAJDLJE_S, gre stran, preden bi zahteva cakala nanjo.
                while self._proste and zdaj - self._proste[0].zadnja_raba > PROSTA_NAJDLJE_S:
                    zavrzi.append(self._proste.pop(0))
                if self._proste and not sveza:
                    p = self._proste.pop()
                    self._v_rabi.add(p)
                    return p, True
                if sveza and self._proste and len(self._proste) + len(self._v_rabi) >= self.najvec:
                    zavrzi.append(self._proste.pop(0))  # prostor za svezo povezavo: najstarejsa prosta gre
                    continue
                uspela = self._prijavljenih() > 0
                vseh = len(self._proste) + len(self._v_rabi)
                if sme_odpreti(False, zdaj < self._premor_do, vseh, self.najvec, uspela, self._sonda):
                    p = self.__nova()
                    p.sonda = not uspela
                    self._sonda = self._sonda or p.sonda
                    self._v_rabi.add(p)
                    return p, False
                if zdaj >= rok_do:
                    raise NapakaNntp(self._premor_izid if zdaj < self._premor_do else ROK)
                if not self._v_rabi and self._premor_do >= rok_do:
                    raise NapakaNntp(self._premor_izid)  # nobena povezava se ne sprosti pred rokom
                cakaj = rok_do - zdaj
                if zdaj < self._premor_do:
                    cakaj = min(cakaj, self._premor_do - zdaj)
                self._pogoj.wait(cakaj)

    def _vrni(self, p: Povezava) -> None:
        with self._pogoj:
            self._v_rabi.discard(p)
            if p.sonda:
                p.sonda = False
                self._sonda = False
            # Steje samo prijavljene povezave: povezava, ki se se odpira (in morda dobi »prevec povezav«), ne izrine
            # delujoce.
            obdrzi = (not self._zaprt and self._ustavljen is None and p.odprta and p.pripravljena
                      and self._prijavljenih() < self.najvec)
            if obdrzi:
                p.zadnja_raba = time.monotonic()
                self._proste.append(p)
            self._pogoj.notify_all()
        if not obdrzi:
            p.zapri(vljudno=True)

    def _zavrzi_starejse(self, zadnja_raba: float) -> None:
        """Stara povezava je bila mrtva: proste, nedejavne vsaj tako dolgo, so verjetno tudi (en premor, vse zaprte)."""
        with self._pogoj:
            stare = [x for x in self._proste if x.zadnja_raba <= zadnja_raba]
            self._proste = [x for x in self._proste if x.zadnja_raba > zadnja_raba]
        for x in stare:
            x.zapri()

    def _odprta(self) -> None:
        """Povezava je odprta in prijavljena: premor in stevec neznanih prijav nazaj na nic. Prijavljene povezave je
        streznik sprejel - bazen, skrcen ob hkratni zavrnitvi (ko ta se ni bila prijavljena), ni manjsi od njih."""
        with self._pogoj:
            self._premor_s = 0.0
            self._neznanih_prijav = 0
            self.najvec = max(self.najvec, min(self._zgornja, self._prijavljenih()))
            self._pogoj.notify_all()

    def _ustavi(self, izid: str, racun: bool = False) -> None:
        """Ustavi bazen (zavrnjena prijava, dostop, potrdilo): vse povezave zaprte, zahteve v teku prekinjene."""
        with self._pogoj:
            if self._ustavljen is None:
                self._ustavljen = izid
            if racun and self._racun is not None:
                with _ZAVRNJENI_ZAKLEP:
                    _ZAVRNJENI.add(self._racun)
            proste, self._proste = self._proste, []
            v_rabi = list(self._v_rabi)
            self._pogoj.notify_all()
        _log.warning("usenet nntp: bazen ustavljen (%s) - brez novih prijav", izid)
        for x in proste:
            x.zapri(vljudno=True)
        for x in v_rabi:
            x.prekini()

    def _premor(self, zmanjsaj: bool, izid: str) -> None:
        with self._pogoj:
            zdaj = time.monotonic()
            tece = zdaj < self._premor_do
            self.najvec, self._premor_s = nov_premor(self.najvec, self._prijavljenih(), self._premor_s, tece, zmanjsaj)
            if not tece:
                self._premor_do = zdaj + self._premor_s
            self._premor_izid = izid
            if zmanjsaj:
                self._zadnja_meja = zdaj
            odvec = self._odvec()
            self._pogoj.notify_all()
        for x in odvec:
            x.zapri(vljudno=True)

    def _neznana_prijava(self) -> None:
        """Prijava brez odgovora (geslo je morda prislo do streznika): prvic premor, drugic zapored zapah."""
        with self._pogoj:
            self._neznanih_prijav += 1
            drugic = self._neznanih_prijav >= 2
        if drugic:
            self._ustavi(PRIJAVA, racun=True)
        else:
            self._premor(False, OMREZJE)

    # -------------------------------------------------------------- zahteve

    def _izvedi(self, delo: Callable[[Povezava], object], sveza: bool = False):
        rok_do = time.monotonic() + self._rok
        for poskus in (0, 1):
            p, stara = self._vzemi(rok_do, sveza)
            try:
                if not stara:
                    p.odpri()
                    self._odprta()
                izid = delo(p)
            except NapakaNntp as e:
                u = ukrep_bazena(e.izid, p.faza, stara, poskus)
                if u != VRNI:
                    p.zapri()
                # Stanje bazena PRED sprostitvijo sonde: cakajoca nit ne sme poslati gesla, preden je zapah postavljen.
                if u == USTAVI_RACUN:
                    self._ustavi(PRIJAVA, racun=True)
                elif u == USTAVI_BAZEN:
                    self._ustavi(e.izid)
                elif u == NEZNANA_PRIJAVA:
                    self._neznana_prijava()
                elif u in (ZMANJSAJ_POCAKAJ, POCAKAJ):
                    self._premor(u == ZMANJSAJ_POCAKAJ, e.izid)
                elif u == ZNOVA and stara:
                    self._zavrzi_starejse(p.zadnja_raba)
                self._vrni(p)
                if self._zaprt:
                    raise NapakaNntp(ZAPRTO) from None  # bazen zaprt med zahtevo: ne odpiramo nove povezave
                if self._ustavljen is not None:
                    raise NapakaNntp(self._ustavljen, e.koda) from None
                if u in (VRNI, NAPAKA) or poskus == 1:
                    raise
                # ZNOVA: vedno nova povezava (C1); pri premoru caka prosto povezavo ali konec premora (_vzemi).
                sveza = u == ZNOVA
                continue
            except BaseException:
                p.zapri()  # nepricakovana napaka sredi zahteve: v medpomnilniku je lahko pol odgovora
                self._vrni(p)
                raise
            self._vrni(p)
            return izid

    def telo(self, message_id: str) -> bytes:
        _ukaz_z_id("BODY", message_id)  # neveljaven id ne zasede povezave
        return self._izvedi(lambda p: p.telo(message_id))

    def stat(self, message_id: str) -> bool:
        _ukaz_z_id("STAT", message_id)
        return self._izvedi(lambda p: p.stat(message_id))

    def preveri(self) -> None:
        """Vedno nova povezava s prijavo (»Preizkusi povezavo«; Grok 37 C9: prosta povezava ni dokaz, da streznik se
        dela). Zapah velja tudi tu: zavrnjen racun ne poskusi znova. Napaka: NapakaNntp."""
        self._izvedi(lambda p: None, sveza=True)

    def zapri(self) -> None:
        """Zapre proste povezave in prekine zahteve v teku (te vrnejo ZAPRTO) - zapiranje ne caka na rok."""
        with self._pogoj:
            self._zaprt = True
            proste, self._proste = self._proste, []
            v_rabi = list(self._v_rabi)
            self._pogoj.notify_all()
        for p in proste:
            p.zapri(vljudno=True)
        for p in v_rabi:
            p.prekini()
