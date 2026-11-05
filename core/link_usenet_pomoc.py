"""Usenet za drugo napravo v Safeer Linku (lastnik 5. 11. 2026, zakon solidarnosti).

TV pod filtrom »⚡ Usenet« pokaze izdajo, katere kodeka sam ne zna, ce jo zna pretvoriti naprava v Linku. Najsibkejsa
naprava naj dela najmanj: TV ne bere NNTP/yEnc in pomocniku NE da naslova (njegov krajevni streznik 127.0.0.1 je za
pomocnika nedosegljiv in link_sprotno ga zavrne - nedovoljen_cilj), ampak samo identiteto izdaje v `video.stream`:
`usenet` = {guid, name, ix}. Ta racunalnik izdajo prenese in bere SAM s svojim racunom:

- `ix` (usenet_pravila.odtis_izdaj: shema + gostitelj indeksatorja, brez kljuca) mora biti odtis NASEGA indeksatorja
  (hmac.compare_digest) - guid velja samo pri istem indeksatorju; sicer `drug_indeksator`.
- NZB s kljucem TEGA racunalnika (Debrid.nzb_po_guid, Newznab t=get, predpomnjen 15 min); nikoli kljuc ali povezava
  NZB z druge naprave. Najvec NAJVEC_NZB_NA_URO prenosov NZB na uro za vse naprave skupaj (kvota indeksatorja je
  lastnikova) - novi guidi nad mejo dobijo `meja`.
- Bere lasten pogon (usenet_vezava, uporabnikov ponudnik NNTP) na 127.0.0.1 z zetonom; link_sprotno ga pretvori prek
  svojega posrednika, ki dovoli natanko ta vrata (_Vir.krajevna_vrata) - vgnezdene zahteve gredo skozi obicajne preverbe.
- Ce ta racunalnik ze predvaja drug film z Useneta (lastnik gleda tu), ga ne prekinemo: `preobremenjen`.

Kdo sme: samo naprava v ozjem krogu tega racunalnika (core/link_daljinec preveri link_dostop.v_ozjem_krogu PRED
klicem); nic iz dohodnega sporocila ne podeli dostopa. host.info dobi `usenet` samo naprava v ozjem krogu.
"""
from __future__ import annotations

import collections
import hmac
import logging
import re
import threading
import time
from typing import Callable, Optional

from . import debrid_pravila as P
from . import usenet_pravila as U

_log = logging.getLogger("safeer.link_usenet_pomoc")

#: Novih prenosov NZB na uro za vse naprave skupaj (NZBFinder: dnevna kvota prenosov racuna).
NAJVEC_NZB_NA_URO = 10
URA_S = 3600.0
_ODTIS = re.compile(r"[0-9a-f]{16}")

_zaklep = threading.Lock()
_debrid = None
_prenosi: "collections.deque[float]" = collections.deque()
_zadnji: Optional[tuple] = None          # (guid, naslov krajevnega streznika) zadnje izdaje za drugo napravo


class NapakaPomoci(Exception):
    """Kratka koda za napravo: napacna_zahteva, ni_usenet, drug_indeksator, meja, indeksator, preobremenjen, pogon."""


def nastavi(debrid) -> None:
    """Debrid Medijskega centra (os_katalog, ko je nastavljen lasten pogon); None = pomoci ni."""
    global _debrid
    with _zaklep:
        _debrid = debrid


def _indeksator() -> Optional[tuple]:
    """(osnova, kljuc) indeksatorja, ce smemo pomagati: kljuc ni zavrnjen ali zaklenjen in lasten pogon je na voljo."""
    d = _debrid
    if d is None:
        return None
    try:
        ix = d.indeksator()
        if not ix or not d.sme_klicati(P.INDEKSATOR) or not d.lastni_usenet_na_voljo():
            return None
        return ix
    except Exception:  # noqa: BLE001 - »ne vem« ni »da«
        return None


def zmoznost() -> Optional[dict]:
    """Za host.info (samo ozji krog): {"lahko": True, "ix": odtis indeksatorja} ali None. Brez omrezja."""
    ix = _indeksator()
    o = U.odtis_izdaj(ix[0]) if ix else None
    return {"lahko": True, "ix": o} if o else None


def identiteta(polje: object) -> tuple:
    """(guid, ime, ix) iz polja `usenet` ali NapakaPomoci("napacna_zahteva")."""
    if not isinstance(polje, dict):
        raise NapakaPomoci("napacna_zahteva")
    g = U.guid(polje.get("guid"))
    ix = str(polje.get("ix") or "")
    ime = " ".join(str(polje.get("name") or "").split())[:200]
    if not g or not _ODTIS.fullmatch(ix):
        raise NapakaPomoci("napacna_zahteva")
    return g, ime, ix


def _rezerviraj(zdaj: float) -> bool:
    """En nov prenos NZB, ce je pod mejo NAJVEC_NZB_NA_URO (drsece okno ene ure)."""
    with _zaklep:
        while _prenosi and zdaj - _prenosi[0] >= URA_S:
            _prenosi.popleft()
        if len(_prenosi) >= NAJVEC_NZB_NA_URO:
            return False
        _prenosi.append(zdaj)
        return True


_ena_hkrati = threading.Lock()


def vir(polje: object, ura: Callable[[], float] = time.monotonic) -> str:
    """Naslov krajevnega streznika (http://127.0.0.1:<vrata>/<zeton>/video.<k>) izdaje iz polja `usenet` ali
    NapakaPomoci. Blokirajoce (prenos NZB, prijava NNTP) - samo z delovne niti. Klicatelj je ze preveril ozji krog.
    Ena priprava hkrati (en film naenkrat, en bazen racuna): druga zahteva med pripravo dobi `preobremenjen`."""
    g, ime, ix = identiteta(polje)
    if not _ena_hkrati.acquire(blocking=False):
        raise NapakaPomoci("preobremenjen")
    try:
        return _vir(g, ime, ix, ura)
    finally:
        _ena_hkrati.release()


def _vir(g: str, ime: str, ix: str, ura: Callable[[], float]) -> str:
    global _zadnji
    d = _debrid
    nas = _indeksator()
    if d is None or nas is None:
        raise NapakaPomoci("ni_usenet")
    odtis = U.odtis_izdaj(nas[0]) or ""
    if not hmac.compare_digest(ix.encode(), odtis.encode()):
        raise NapakaPomoci("drug_indeksator")
    vezava = d.lastni_usenet
    with _zaklep:
        zadnji = _zadnji
    # Previjanje istega filma: tok, ki se tece, ne gre znova k indeksatorju in ne odpre novega bazena NNTP.
    zadnji_odprt = bool(zadnji) and vezava.odprt(zadnji[1])
    if zadnji_odprt and zadnji[0] == g:
        return zadnji[1]
    if vezava.predvaja() - (1 if zadnji_odprt else 0) > 0:
        raise NapakaPomoci("preobremenjen")       # lastnik gleda film z Useneta na tem racunalniku
    nzb = d._nzb_zapomnjen("guid:" + g)
    if nzb is None:
        if not _rezerviraj(ura()):
            _log.info("usenet pomoc: meja prenosov NZB na uro")
            raise NapakaPomoci("meja")
        nzb, napaka = d.nzb_po_guid(g)
        if nzb is None:
            _log.info("usenet pomoc: NZB ni (%s)", napaka)         # stalna koda, brez guida in kljuca
            raise NapakaPomoci("meja" if napaka == P.NAPAKA_MEJA else "indeksator")
    url, koda = vezava.predvajaj(nzb, ime)
    if not url:
        _log.info("usenet pomoc: lasten pogon ni predvajal (%s)", koda)
        raise NapakaPomoci("pogon")
    with _zaklep:
        _zadnji = (g, url)
    return url
