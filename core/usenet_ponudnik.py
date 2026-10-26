"""Splosna nastavitev ponudnika NNTP (Usenet korak 3, del A; lastnik 26. 10. 2026).

Usenet se v vmesniku pokaze sele, ko uporabnik vpise SVOJEGA ponudnika: Safeer ne priporoca in ne vsebuje imen
ponudnikov. Uporabnik vir shrani in nanj pozabi; vprasa se ga samo ob resni spremembi (zavrnjena prijava, zapah).

- Geslo ni nikoli v nastavitvah, repr, izjemi ali dnevniku: samo v sistemski zbirki skrivnosti (skrivnosti.py) pod
  kljucem iz odtisa SHA-256 (gostitelj, uporabnik) - goli niz bi uporabnika pokazal v atributih zbirke.
- Zaklep racuna je prednost lastnika: preverba uporablja vrata prijave in zapah iz usenet_nntp (Bazen._pred_prijavo,
  _po_prijavi, _ustavi) - novih pravil tu ni. Zavrnjeno geslo gre k strezniku enkrat; nov poskus odklene samo nov
  vpis poverilnic (shrani_ponudnika).
- Brez omrezja na glavni niti in nic v ozadju: preverba je samo uporabnikov gumb, najvec 1 na minuto na racun.
- Trda meja racuna je najvec_povezav (vpise jo uporabnik); naprava, ki predvaja, dobi vse, delitve po napravah ni.
- TLS privzeto. Brez TLS samo z izrecnim nevarno_brez_tls=True in naslovom IP v domacem omrezju; usenet_nntp zna
  samo TLS, zato tak ponudnik ostane shranjen, povezava pa se jasno zavrne (brez omrezja).
"""

from __future__ import annotations

import dataclasses
import hashlib
import ipaddress
import json
import logging
import os
import re
import ssl
import tempfile
import threading
import time
from typing import Optional

from . import usenet_nntp as nntp
from .sporocila import skrivnosti

_log = logging.getLogger("safeer.usenet")

VRATA = nntp.VRATA
PRIVZETO_POVEZAV = nntp.PRIVZETO_POVEZAV
NAJVEC_POVEZAV_RACUNA = 100  # meja vnosa; Bazen sam ne gre cez nntp.NAJVEC_POVEZAV
NAJVEC_IME = 80
PREVERBA_NA_S = 60.0  # 1 preverba na minuto na racun (gumb »Preveri«)
NAJVEC_NASTAVITEV_BAJTOV = 64 * 1024  # datoteka nastavitev je majhna - vec je tuja ali pokvarjena
_VERZIJA = 1
_PREDPONA_KLJUCA = "usenet-ponudnik-"

# Izidi preverbe.
VELJA = "VELJA"
NE_VELJA = "NE_VELJA"
ZAKLENJEN = "ZAKLENJEN"
NI_ODGOVORA = "NI_ODGOVORA"
PREVEC_POVEZAV = "PREVEC_POVEZAV"
PREPOGOSTO = "PREPOGOSTO"  # gumb znova pred iztekom minute: brez omrezja
NEPREVERJEN = "NEPREVERJEN"  # samo stanje_za_vmesnik

# Razlogi NapakaPonudnika (brez vrednosti).
NI_GESLA = "ni_gesla"
BREZ_TLS = "brez_tls_ni_podprt"
RACUN_ZAKLENJEN = "racun_zaklenjen"

_POLJA = ("gostitelj", "uporabnik", "vrata", "tls", "najvec_povezav", "ime", "nevarno_brez_tls")
_OZNAKA = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


class NapakaPonudnika(Exception):
    """Jasna napaka brez omrezja. Nosi samo razlog - nikoli gesla, uporabnika ali gostitelja."""

    def __init__(self, razlog: str):
        super().__init__(razlog)
        self.razlog = razlog

    def __str__(self) -> str:
        return "usenet ponudnik: %s" % self.razlog

    def __repr__(self) -> str:
        return "NapakaPonudnika(%r)" % self.razlog


# ------------------------------------------------------------------ validacija

def _naslov_ip(g: str):
    try:
        return ipaddress.ip_address(g)
    except ValueError:
        return None


def _veljaven_gostitelj(g: object) -> bool:
    """Ime ali IP brez sheme, poti, vrat in presledkov. Najprej pravila usenet_nntp, nato oznake DNS."""
    try:
        nntp._preveri_gostitelja(g, VRATA)
    except ValueError:
        return False
    g = str(g)
    if _naslov_ip(g) is not None:
        return True
    try:
        ascii_ime = g.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return False
    oznake = ascii_ime.split(".")
    if len(ascii_ime) > 253 or not all(_OZNAKA.match(o) for o in oznake):
        return False  # tudi »news.x:563«, »x://y« in koncna pika
    return not all(o.isdigit() for o in oznake)  # »999.1.1.1« ni IP in ni ime


#: Domace omrezje: RFC 1918, lokalni in povezavni naslovi, IPv6 ULA. ipaddress.is_private bi spustil tudi
#: dokumentacijske in rezervirane obsege (npr. 203.0.113.0/24), zato izrecen seznam.
_DOMACA = tuple(ipaddress.ip_network(n) for n in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "127.0.0.0/8", "169.254.0.0/16", "::1/128", "fc00::/7",
    "fe80::/10"))


def domace_omrezje(gostitelj: str) -> bool:
    """Samo naslov IP v domacem obsegu. Ime ne velja: brez DNS (omrezje) ne vemo, kam kaze."""
    ip = _naslov_ip(gostitelj)
    if ip is None:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return any(ip.version == n.version and ip in n for n in _DOMACA)


def _je_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)  # True ni stevilo vrat


@dataclasses.dataclass(frozen=True, repr=False)
class Ponudnik:
    """Nastavitev ponudnika brez gesla. Neveljavne vrednosti ne morejo obstajati (ValueError brez vrednosti)."""

    gostitelj: str
    uporabnik: str
    vrata: int = VRATA
    tls: bool = True
    najvec_povezav: int = PRIVZETO_POVEZAV
    ime: str = ""
    nevarno_brez_tls: bool = False

    def __post_init__(self) -> None:
        if not _veljaven_gostitelj(self.gostitelj):
            raise ValueError("usenet ponudnik: neveljaven gostitelj")
        if not _je_int(self.vrata) or not 1 <= self.vrata <= 65535:
            raise ValueError("usenet ponudnik: neveljavna vrata")
        if not nntp.varna_poverilnica(self.uporabnik):
            raise ValueError("usenet ponudnik: neveljavno uporabnisko ime")
        if not _je_int(self.najvec_povezav) or not 1 <= self.najvec_povezav <= NAJVEC_POVEZAV_RACUNA:
            raise ValueError("usenet ponudnik: najvec_povezav mora biti 1-100")
        if (not isinstance(self.ime, str) or len(self.ime) > NAJVEC_IME
                or any(z < " " or z == "\x7f" for z in self.ime)):
            raise ValueError("usenet ponudnik: neveljavno ime")
        if not isinstance(self.tls, bool) or not isinstance(self.nevarno_brez_tls, bool):
            raise ValueError("usenet ponudnik: tls mora biti bool")
        if not self.tls:
            # Geslo v golem besedilu: samo izrecna odlocitev in samo doma (lastnik: TLS privzeto).
            if not self.nevarno_brez_tls:
                raise ValueError("usenet ponudnik: brez TLS samo z nevarno_brez_tls=True")
            if not domace_omrezje(self.gostitelj):
                raise ValueError("usenet ponudnik: brez TLS samo do naslova IP v domacem omrezju")

    def __repr__(self) -> str:
        # Uporabnik nikoli v celoti (pregledi: dnevnik in porocila o napakah gredo ven).
        return "Ponudnik(ime=%r, %s:%d, tls=%s, povezav=%d, uporabnik=<skrit>)" % (
            self.ime, self.gostitelj, self.vrata, self.tls, self.najvec_povezav)

    __str__ = __repr__

    @property
    def kljuc_gesla(self) -> str:
        """Kljuc v zbirki: odtis, ker so atributi zbirke berljivi brez odklepa."""
        h = hashlib.sha256()
        for x in (self.gostitelj.lower(), self.uporabnik):
            b = x.encode("utf-8")
            h.update(len(b).to_bytes(4, "big") + b)  # dolzina: »ab|c« in »a|bc« nista isti kljuc
        return _PREDPONA_KLJUCA + h.hexdigest()

    def v_slovar(self) -> dict:
        return {"gostitelj": self.gostitelj, "uporabnik": self.uporabnik, "vrata": self.vrata, "tls": self.tls,
                "najvec_povezav": self.najvec_povezav, "ime": self.ime, "nevarno_brez_tls": self.nevarno_brez_tls}

    @classmethod
    def iz_slovarja(cls, d: object) -> "Ponudnik":
        if not isinstance(d, dict) or set(d) - set(_POLJA):
            raise ValueError("usenet ponudnik: neveljaven zapis")  # neznano polje: tuj ali spremenjen zapis
        try:
            return cls(**{k: d[k] for k in _POLJA if k in d})
        except TypeError:
            raise ValueError("usenet ponudnik: neveljaven zapis") from None  # TypeError bi nosil ime polja


# ------------------------------------------------------------------ geslo (samo zbirka; brez nje samo pomnilnik)

#: Brez sistemske zbirke ostane geslo samo v pomnilniku procesa (kot priloga 2) - nikoli na disk.
_V_POMNILNIKU: dict = {}
_POMNILNIK_ZAKLEP = threading.Lock()


def _shrani_geslo(kljuc: str, geslo: str) -> bool:
    trajno = bool(skrivnosti.shrani(kljuc, geslo))
    with _POMNILNIK_ZAKLEP:
        if trajno:
            _V_POMNILNIKU.pop(kljuc, None)
        else:
            _V_POMNILNIKU[kljuc] = geslo
    return trajno


def _preberi_geslo(kljuc: str) -> Optional[str]:
    with _POMNILNIK_ZAKLEP:
        g = _V_POMNILNIKU.get(kljuc)
    if g is None:
        g = skrivnosti.preberi(kljuc)
    return g if nntp.varna_poverilnica(g) else None  # pokvarjen vnos zbirke ne gre v ukaz


def _pozabi_geslo(kljuc: str) -> None:
    with _POMNILNIK_ZAKLEP:
        _V_POMNILNIKU.pop(kljuc, None)
    skrivnosti.pozabi(kljuc)


# ------------------------------------------------------------------ nastavitve (JSON, atomarno, 0600)

def _beri_json(pot: str) -> Optional[dict]:
    try:
        with open(pot, "rb") as f:
            surovo = f.read(NAJVEC_NASTAVITEV_BAJTOV + 1)
    except FileNotFoundError:
        return None
    except OSError as e:
        _log.info("usenet ponudnik: nastavitev ni mogoce prebrati (%s)", type(e).__name__)
        return None
    if len(surovo) > NAJVEC_NASTAVITEV_BAJTOV:
        _log.info("usenet ponudnik: nastavitve so prevelike")
        return None
    try:
        d = json.loads(surovo.decode("utf-8"))
    except (UnicodeError, ValueError):
        _log.info("usenet ponudnik: nastavitve niso veljaven JSON")
        return None
    return d if isinstance(d, dict) and d.get("verzija") == _VERZIJA else None


def _pisi_json(pot: str, podatki: dict) -> None:
    """Atomarno (mkstemp 0600 + fsync + os.replace): sesutje ne pusti pol datoteke, drugi uporabniki je ne berejo."""
    mapa = os.path.dirname(os.path.abspath(pot))
    os.makedirs(mapa, mode=0o700, exist_ok=True)
    besedilo = json.dumps(podatki, ensure_ascii=False, sort_keys=True, indent=1) + "\n"
    fd, zacasna = tempfile.mkstemp(prefix=".usenet-ponudnik-", dir=mapa)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(besedilo)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(zacasna, 0o600)
        os.replace(zacasna, pot)
    except BaseException:
        try:
            os.unlink(zacasna)
        except OSError:
            pass
        raise


def _ponudnik_iz(d: Optional[dict]) -> Optional[Ponudnik]:
    if d is None:
        return None
    try:
        return Ponudnik.iz_slovarja(d.get("ponudnik"))
    except ValueError:
        _log.info("usenet ponudnik: shranjen ponudnik ni veljaven")
        return None


def shrani_ponudnika(ponudnik: Ponudnik, geslo: str, pot_nastavitev: str) -> bool:
    """Izrecni vpis uporabnika. Vrne True, ce je geslo v sistemski zbirki (False = samo do konca procesa).

    Nov vpis (tudi enakih poverilnic) je edino, kar odklene zapah racuna: dovoli_prijavo_znova."""
    if not isinstance(ponudnik, Ponudnik):
        raise ValueError("usenet ponudnik: pricakovan Ponudnik")
    if not nntp.varna_poverilnica(geslo):
        raise ValueError("usenet ponudnik: neveljavno geslo")  # brez vrednosti
    star = _ponudnik_iz(_beri_json(pot_nastavitev))
    _pisi_json(pot_nastavitev, {"verzija": _VERZIJA, "ponudnik": ponudnik.v_slovar(), "preverba": None})
    if star is not None and star.kljuc_gesla != ponudnik.kljuc_gesla:
        _pozabi_geslo(star.kljuc_gesla)  # zamenjan racun: staro geslo ne ostane v zbirki
    trajno = _shrani_geslo(ponudnik.kljuc_gesla, geslo)
    nntp.dovoli_prijavo_znova(ponudnik.gostitelj, ponudnik.uporabnik, geslo)
    with _PREVERBE_ZAKLEP:
        _PREVERBE.pop(_kljuc_racuna(ponudnik), None)  # nov vpis sme takoj na »Preveri«
    return trajno


def preberi_ponudnika(pot_nastavitev: str) -> Optional[Ponudnik]:
    """Shranjen ponudnik ali None (ni vpisan ali je zapis pokvarjen). Gesla ne bere."""
    return _ponudnik_iz(_beri_json(pot_nastavitev))


def pozabi_ponudnika(pot_nastavitev: str) -> None:
    """Zbrise nastavitev, geslo in trajni zapah racuna (uporabnik je racun odstranil)."""
    p = preberi_ponudnika(pot_nastavitev)
    if p is not None:
        geslo = _preberi_geslo(p.kljuc_gesla)
        nntp.dovoli_prijavo_znova(p.gostitelj, p.uporabnik, geslo)  # zapah v procesu in na disku
        _pozabi_geslo(p.kljuc_gesla)
        with _PREVERBE_ZAKLEP:
            _PREVERBE.pop(_kljuc_racuna(p), None)
    try:
        os.unlink(pot_nastavitev)
    except FileNotFoundError:
        pass


def _zapisi_preverbo(pot_nastavitev: str, ponudnik: Ponudnik, izid: str) -> None:
    d = _beri_json(pot_nastavitev)
    p = _ponudnik_iz(d)
    if d is None or p is None or p.kljuc_gesla != ponudnik.kljuc_gesla:
        return  # medtem zamenjan ponudnik: izid ne velja zanj
    d["preverba"] = {"izid": izid, "cas": int(time.time())}
    try:
        _pisi_json(pot_nastavitev, d)
    except OSError as e:
        _log.info("usenet ponudnik: izida ni mogoce shraniti (%s)", type(e).__name__)


# ------------------------------------------------------------------ preverba (gumb »Preveri«)

_PREVERBE: dict = {}  # kljuc racuna -> monotonic zadnje preverbe z omrezjem
_PREVERBE_ZAKLEP = threading.Lock()
_ura = time.monotonic  # preizkusi jo zamenjajo


def _kljuc_racuna(p: Ponudnik) -> str:
    # Racun pri ponudniku (kot vrata prijave v usenet_nntp): drugo ime streznika ne da nove preverbe.
    return hashlib.sha256(("%s\x00%s" % (nntp.ponudnik(p.gostitelj), p.uporabnik)).encode("utf-8")).hexdigest()


def _rezerviraj_preverbo(p: Ponudnik) -> bool:
    """Pod zaklepom: dva hkratna klika ne odpreta dveh povezav."""
    zdaj = _ura()
    k = _kljuc_racuna(p)
    with _PREVERBE_ZAKLEP:
        zadnja = _PREVERBE.get(k)
        if zadnja is not None and zdaj - zadnja < PREVERBA_NA_S:
            return False
        _PREVERBE[k] = zdaj
        for x in [x for x, t in _PREVERBE.items() if zdaj - t >= PREVERBA_NA_S and x != k]:
            del _PREVERBE[x]  # omejena velikost
    return True


def _ne_na_glavni_niti() -> None:
    if threading.current_thread() is threading.main_thread():
        raise RuntimeError("usenet ponudnik: omrezje ni dovoljeno na glavni niti")


def _samo_tls(p: Ponudnik) -> None:
    if not p.tls:
        raise NapakaPonudnika(BREZ_TLS)  # usenet_nntp zna samo TLS - brez omrezja


def preveri_ponudnika(ponudnik: Ponudnik, geslo: str, *, pot_nastavitev: Optional[str] = None,
                      kontekst: Optional[ssl.SSLContext] = None) -> str:
    """ENA povezava, ena prijava, QUIT. Samo na uporabnikov klik, nikoli na glavni niti ali v ozadju.

    Izid: VELJA, NE_VELJA, ZAKLENJEN, NI_ODGOVORA, PREVEC_POVEZAV ali PREPOGOSTO (manj kot minuta od zadnje).
    Zapah racuna NE odklene (to naredi samo nov vpis): po NE_VELJA je naslednja preverba ZAKLENJEN brez omrezja."""
    if not isinstance(ponudnik, Ponudnik):
        raise ValueError("usenet ponudnik: pricakovan Ponudnik")
    if not nntp.varna_poverilnica(geslo):
        raise ValueError("usenet ponudnik: neveljavno geslo")
    _ne_na_glavni_niti()
    _samo_tls(ponudnik)
    kontekst = nntp.varen_kontekst(kontekst)  # brez preverbe potrdila: ValueError pred omrezjem
    if nntp.prijava_zavrnjena(ponudnik.gostitelj, ponudnik.uporabnik, geslo):
        izid = ZAKLENJEN
    elif not _rezerviraj_preverbo(ponudnik):
        return PREPOGOSTO
    else:
        izid = _preveri_z_omrezjem(ponudnik, geslo, kontekst)
    _log.info("usenet ponudnik: preverba %s", izid)  # samo izid
    if pot_nastavitev is not None and izid in (VELJA, NE_VELJA, ZAKLENJEN):
        _zapisi_preverbo(pot_nastavitev, ponudnik, izid)
    return izid


def _preveri_z_omrezjem(p: Ponudnik, geslo: str, kontekst: ssl.SSLContext) -> str:
    # Bazen z eno povezavo da samo obstojeca pravila (vrata prijave, zapah, ustavitev drugih bazenov racuna);
    # povezavo odpremo sami, ker Bazen._izvedi po napaki omrezja odpre drugo (spec: ENA povezava).
    bazen = nntp.Bazen(p.gostitelj, p.vrata, p.uporabnik, geslo, povezav=1, kontekst=kontekst)
    pov = nntp.Povezava(p.gostitelj, p.vrata, p.uporabnik, geslo, kontekst,
                        pred_prijavo=bazen._pred_prijavo, po_prijavi=bazen._po_prijavi)
    try:
        pov.odpri()
        return VELJA
    except nntp.NapakaNntp as e:
        return _izid_napake(bazen, p, geslo, e, pov.faza)
    finally:
        pov.zapri(vljudno=True)  # QUIT
        bazen.zapri()


def _izid_napake(bazen: "nntp.Bazen", p: Ponudnik, geslo: str, e: "nntp.NapakaNntp", faza: str) -> str:
    if e.izid == nntp.ZASEDEN or (faza == nntp.FAZA_POVEZAVA and e.izid == nntp.DOSTOP):
        return PREVEC_POVEZAV  # 502 v pozdravu ali jasno besedilo o meji; geslo ni zavrnjeno
    if faza == nntp.FAZA_PRIJAVA:
        # _po_prijavi je izid ze zapisal (zapah ali stevec neznanih prijav) pred sprostitvijo vrat prijave.
        if nntp.prijava_zavrnjena(p.gostitelj, p.uporabnik, geslo):
            bazen._ustavi(nntp.PRIJAVA, racun=True)  # ustavi tudi zive bazene istega racuna (Grok 43 C3)
            return NE_VELJA if e.izid == nntp.PRIJAVA else ZAKLENJEN
        return NI_ODGOVORA  # geslo je morda prislo do streznika, odgovora ni (prvic: brez zapaha)
    if nntp.prijava_zavrnjena(p.gostitelj, p.uporabnik, geslo):
        return ZAKLENJEN  # zapah je medtem postavil drug bazen; geslo ni bilo poslano
    return NI_ODGOVORA  # omrezje, TLS, rok, tuj pozdrav


# ------------------------------------------------------------------ bazen za predvajanje

class _BazenRacuna(nntp.Bazen):
    """Bazen s trdo mejo racuna: tudi nastavi_najvec od zunaj ne gre cez uporabnikovo stevilo povezav."""

    def __init__(self, *a, meja_racuna: int, **k):
        self._meja_racuna = max(1, int(meja_racuna))
        super().__init__(*a, **k)

    def nastavi_najvec(self, povezav: int) -> None:
        super().nastavi_najvec(min(int(povezav), self._meja_racuna))


def ustvari_bazen(ponudnik: Ponudnik, *, kontekst: Optional[ssl.SSLContext] = None) -> "nntp.Bazen":
    """Bazen za predvajanje (povezave odpira sele zahteva). Geslo iz zbirke sele tu; brez gesla ali z zapahom
    NapakaPonudnika brez omrezja - Bazen bi sicer obstajal, a vsaka zahteva bi koncala z napako."""
    if not isinstance(ponudnik, Ponudnik):
        raise ValueError("usenet ponudnik: pricakovan Ponudnik")
    _samo_tls(ponudnik)
    geslo = _preberi_geslo(ponudnik.kljuc_gesla)
    if geslo is None:
        raise NapakaPonudnika(NI_GESLA)
    if nntp.prijava_zavrnjena(ponudnik.gostitelj, ponudnik.uporabnik, geslo):
        raise NapakaPonudnika(RACUN_ZAKLENJEN)
    meja = min(ponudnik.najvec_povezav, nntp.NAJVEC_POVEZAV)
    return _BazenRacuna(ponudnik.gostitelj, ponudnik.vrata, ponudnik.uporabnik, geslo, povezav=meja,
                        kontekst=kontekst, meja_racuna=meja)


# ------------------------------------------------------------------ vmesnik

_BESEDILA = {
    None: "Usenet se pokaže, ko v nastavitvah vpišeš svojega ponudnika NNTP.",
    NEPREVERJEN: "Ponudnik je shranjen. Klikni »Preveri«, če želiš preizkusiti prijavo.",
    NI_GESLA: "Geslo za ponudnika ni shranjeno. Vpiši ga znova v nastavitvah Useneta.",
    VELJA: "Prijava pri ponudniku deluje.",
    NE_VELJA: "Ponudnik je zavrnil prijavo. Preveri uporabniško ime in geslo in ju vpiši znova - "
              "do takrat Safeer gesla ne pošilja (zaščita pred zaklepom računa).",
    ZAKLENJEN: "Prijava je bila zavrnjena, zato Safeer gesla ne pošilja več. Ko poverilnice preveriš pri "
               "ponudniku, jih vpiši znova.",
}


def stanje_za_vmesnik(pot_nastavitev: str) -> dict:
    """Stanje za nastavitve in prikaz Useneta - brez gesla in uporabnika. Usenet je viden samo z vpisanim ponudnikom.

    Bere geslo iz zbirke samo za preverbo zapaha (odtis vsebuje geslo); brez omrezja."""
    d = _beri_json(pot_nastavitev)
    p = _ponudnik_iz(d)
    if p is None:
        return {"vpisan": False, "usenet_viden": False, "ime": None, "gostitelj": None, "vrata": None,
                "tls": None, "najvec_povezav": None, "geslo_shranjeno": False, "stanje": None,
                "besedilo": _BESEDILA[None]}
    pr = d.get("preverba") if isinstance(d.get("preverba"), dict) else {}
    zadnji = pr.get("izid") if pr.get("izid") in (VELJA, NE_VELJA, ZAKLENJEN) else None
    geslo = _preberi_geslo(p.kljuc_gesla)
    if geslo is not None and nntp.prijava_zavrnjena(p.gostitelj, p.uporabnik, geslo):
        stanje = NE_VELJA if zadnji == NE_VELJA else ZAKLENJEN  # zapah ima prednost pred staro VELJA
    elif zadnji == VELJA:
        stanje = VELJA
    else:
        stanje = NEPREVERJEN
    besedilo = _BESEDILA[NI_GESLA] if geslo is None and stanje == NEPREVERJEN else _BESEDILA[stanje]
    return {"vpisan": True, "usenet_viden": True, "ime": p.ime, "gostitelj": p.gostitelj, "vrata": p.vrata,
            "tls": p.tls, "najvec_povezav": p.najvec_povezav, "geslo_shranjeno": geslo is not None,
            "stanje": stanje, "besedilo": besedilo}
