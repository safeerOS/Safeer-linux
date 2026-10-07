"""Safeer Link: zascita ukazov od naprave do naprave (E2E v1). Ista pravila kot cast/E2e.kt na Androidu.

Zakaj. Naprava, ki vsebino hrani, je posiljatelja doslej prepoznala po oznaki, ki jo sporocilu vpise sredisce. Oznaka,
ki je le podobna oznaki druge naprave, je dobila njen dostop (izmerjeno 7. 10. 2026 krajevno); sredisce pa ta sporocila
posreduje nesifrirana in posiljatelja vpise samo - kdor ga gosti, bi jih lahko bral in ponarejal (sledi iz zgradbe).
Tu napravi dokazeta KLJUC: vsaka podpise svoj del dogovora s kljucem naprave, druga ga preveri s kljucem iz SVOJEGA
kroga zaupanja. Dostop se potem veze na ta kljuc, ne na oznako; sredisce vidi samo podpisan dogovor in sifrirane kose.

Prenos. Sporocila potujejo v ze obstojecih `data.offer` / `data.answer` / `data.chunk` / `data.error`, ki jih vsa
sredisca (tudi starejsa) samo posredujejo po polju `target` in tovora ne razlagajo. Namen (`purpose`) je "link".

Dogovor (A zacne, B odgovori):
    data.offer   {session_id, purpose:"link", v:2, from:A, to:B, nonce, epk, ts, sig}
                 sig = podpis A nad  "safeer-link-e2e-offer-v1\\n<session_id>\\n<A>\\n<B>\\n<nonce>\\n<epk>"
    data.answer  {session_id, purpose:"link", v:2, from:B, to:A, offer_nonce, nonce, epk, ts, sig}
                 sig = podpis B nad  "safeer-link-e2e-answer-v1\\n<session_id>\\n<B>\\n<A>\\n<offer_nonce>\\n<nonce>\\n<epk A>\\n<epk B>"
    epk je ENKRATNI javni kljuc P-256 (base64 SPKI DER) - kljuc naprave samo podpisuje (na Androidu drugega ne zna in
    ne sme), skupna skrivnost pa je ECDH med enkratnima kljucema. `ts` je samo za dnevnik: svezost dajeta nonca, zato
    zascita ni odvisna od ure naprav.
    Z = ECDH(enkratni A, enkratni B);  gradivo = HKDF-SHA256(Z, sol = SHA-256(session_id),
        info = "safeer-link-e2e-v1\\n" + nonce A + nonce B + "\\n<A>\\n<B>", 72 bajtov)
        = kljuc A->B (32) | predpona nonca A->B (4) | kljuc B->A (32) | predpona nonca B->A (4)

Sporocilo (v obe smeri, vsaka smer s svojim kljucem in stevcem):
    data.chunk   {session_id, seq, m, i, n, data}
                 data = AES-256-GCM(kljuc smeri, nonce = predpona | seq (8 bajtov), del cistopisa,
                                    aad = "safeer-link-e2e-msg-v1\\n<session_id>\\n<smer>\\n<seq>\\n<m>\\n<i>\\n<n>")
    Cistopis je JSON notranjega sporocila ({type, id, ref_id, payload ...}); dolgo sporocilo gre v vec delih
    (m = stevilka sporocila, i = del, n = stevilo delov). seq mora v vsaki smeri strogo narascati.
    data.error   {session_id, code:"ni_seje", seq}  - prejemnik seje ne pozna (znova se je zagnal): posiljatelj se
                 dogovori znova in se nepotrjena zadnja sporocila poslje se enkrat.
    data.ack     potrditev SREDISCA za nase sporocilo prenosa (ref_id "e2e-..."). Zavrnitev (naprave ni v Linku ...)
                 prevedemo v zavrnitev notranjega sporocila, da klicatelj izve takoj in ne caka na iztek casa; sprejem
                 sporocila (ne ponudbe dogovora) javimo kot sprejem notranjega sporocila.

Ta modul ne pozna sredisca, datotek ali kroga: podpis, preverbo, posiljanje in uro dobi od klicatelja, zato tece v
preizkusih brez omrezja. Kriptografija: cryptography (ECDH, AES-GCM); brez nje zascite ni in `poslji` vrne False -
nesifriranega nadomestka ni.
"""
from __future__ import annotations

import base64
import hashlib
import hmac as _hmac
import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

NAMEN = "link"
RAZLICICA = 2
#: Zmoznost, ki jo naprava prijavi srediscu: zna zascito od naprave do naprave.
ZMOZNOST = "e2e1"
#: Sporocila, ki med napravama z zascito nikoli ne gredo nezascitena: ukazi, njihovi odgovori in vse, kar na napravi samo
#: odpre stran ali predvajanje (stran, nadzor predvajanja, »nadaljuj na napravi«).
ZASCITENI_TIPI = frozenset({"control.command", "control.result", "cast.url", "cast.control", "handoff.request"})
TIPI_PRENOSA = frozenset({"data.offer", "data.answer", "data.chunk", "data.error"})
#: Predpona oznak nasih sporocil prenosa: po njej prepoznamo potrditev sredisca (data.ack) zanje.
PREDPONA_OZNAK = "e2e-"
NAJVEC_IZHODNIH = 256             # za koliko zadnjih sporocil prenosa vemo, katera notranja sporocila nosijo
IZHODNA_VELJAJO_S = 30.0          # potrditev sredisca pride v milisekundah; po tem casu zapis zavrzemo

# Cistopis enega dela. Sredisce na Androidu sprejme sporocilo do 256 KiB in ima za vsako povezavo vrsto 512 KiB: del z
# base64 in ovojnico meri ~64 KiB, sporocilo, ki je doslej slo v enem kosu (do 256 KiB), pa tudi v delih ostane pod vrsto.
DOLZINA_DELA = 48 * 1024
NAJVEC_DELOV = 24                 # najvec ~1,1 MiB za eno notranje sporocilo (vec, kot je slo doslej nezasciteno)
DOGOVOR_CAKA_S = 8.0              # po tem casu brez odgovora se dogovor zacne znova
NAJVEC_V_VRSTI = 64               # sporocil, ki cakajo na dogovor z eno napravo
SEJA_VELJA_S = 12 * 3600.0
NAJVEC_SEJ = 256
HRANI_ZADNJIH = 16                # zadnja poslana sporocila za ponovitev po "ni_seje"
PONOVI_MLAJSE_OD_S = 5.0          # starejsega ukaza ne ponavljamo: uporabnik ga je ze opustil ali ponovil sam
NEDOKONCANA_VELJAJO_S = 30.0


class Napaka(Exception):
    """Neveljaven dogovor ali sporocilo (podpis, cilj, stevec, sifropis). Vzrok je v besedilu."""


# ---------------------------------------------------------------------------------------------- kriptografija

def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _iz_b64(s: str, kaj: str) -> bytes:
    try:
        return base64.b64decode(s, validate=True)
    except Exception as e:  # noqa: BLE001
        raise Napaka(f"neveljaven zapis ({kaj})") from e


def nov_par() -> Tuple[object, str]:
    """Enkratni par P-256: (zasebni kljuc, javni kljuc kot base64 SPKI DER)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    zasebni = ec.generate_private_key(ec.SECP256R1())
    der = zasebni.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return zasebni, _b64(der)


def ecdh(zasebni: object, tuj_javni_b64: str) -> bytes:
    """Skupna skrivnost (koordinata x, 32 bajtov) med nasim enkratnim zasebnim in tujim enkratnim javnim kljucem."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    try:
        tuj = serialization.load_der_public_key(_iz_b64(tuj_javni_b64, "epk"))
        if not isinstance(tuj, ec.EllipticCurvePublicKey) or tuj.curve.name != "secp256r1":
            raise Napaka("enkratni kljuc ni P-256")
        return zasebni.exchange(ec.ECDH(), tuj)  # type: ignore[attr-defined]
    except Napaka:
        raise
    except Exception as e:  # noqa: BLE001
        raise Napaka("ECDH ni uspel") from e


def hkdf(ikm: bytes, sol: bytes, info: bytes, dolzina: int) -> bytes:
    """HKDF-SHA256 (RFC 5869)."""
    prk = _hmac.new(sol if sol else b"\x00" * 32, ikm, hashlib.sha256).digest()
    izhod, blok, i = b"", b"", 1
    while len(izhod) < dolzina:
        blok = _hmac.new(prk, blok + info + bytes([i]), hashlib.sha256).digest()
        izhod += blok
        i += 1
    return izhod[:dolzina]


@dataclass(frozen=True)
class Kljuci:
    """Gradivo ene seje. Smer "ab" je od zacetnika (A) k odgovarjajocemu (B), "ba" nazaj."""
    k_ab: bytes
    p_ab: bytes
    k_ba: bytes
    p_ba: bytes

    def smer(self, smer: str) -> Tuple[bytes, bytes]:
        return (self.k_ab, self.p_ab) if smer == "ab" else (self.k_ba, self.p_ba)


def izpelji(skrivnost: bytes, session_id: str, nonce_a_b64: str, nonce_b_b64: str, a_id: str, b_id: str) -> Kljuci:
    info = (b"safeer-link-e2e-v1\n" + _iz_b64(nonce_a_b64, "nonce") + _iz_b64(nonce_b_b64, "nonce")
            + ("\n%s\n%s" % (a_id, b_id)).encode("utf-8"))
    g = hkdf(skrivnost, hashlib.sha256(session_id.encode("utf-8")).digest(), info, 72)
    return Kljuci(k_ab=g[0:32], p_ab=g[32:36], k_ba=g[36:68], p_ba=g[68:72])


def podatki_ponudbe(session_id: str, od_id: str, do_id: str, nonce_b64: str, epk_b64: str) -> bytes:
    return ("safeer-link-e2e-offer-v1\n%s\n%s\n%s\n%s\n%s" % (session_id, od_id, do_id, nonce_b64, epk_b64)).encode("utf-8")


def podatki_odgovora(session_id: str, od_id: str, do_id: str, nonce_ponudbe_b64: str, nonce_b64: str,
                     epk_a_b64: str, epk_b_b64: str) -> bytes:
    return ("safeer-link-e2e-answer-v1\n%s\n%s\n%s\n%s\n%s\n%s\n%s"
            % (session_id, od_id, do_id, nonce_ponudbe_b64, nonce_b64, epk_a_b64, epk_b_b64)).encode("utf-8")


def aad(session_id: str, smer: str, seq: int, m: int, i: int, n: int) -> bytes:
    return ("safeer-link-e2e-msg-v1\n%s\n%s\n%d\n%d\n%d\n%d" % (session_id, smer, seq, m, i, n)).encode("utf-8")


def _nonce(predpona: bytes, seq: int) -> bytes:
    if seq < 0 or seq > 0xFFFFFFFFFFFFFFFF:
        raise Napaka("neveljaven stevec")
    return predpona + seq.to_bytes(8, "big")


def sifriraj(kljuc: bytes, predpona: bytes, seq: int, cistopis: bytes, dodatno: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return AESGCM(kljuc).encrypt(_nonce(predpona, seq), cistopis, dodatno)


def desifriraj(kljuc: bytes, predpona: bytes, seq: int, sifropis: bytes, dodatno: bytes) -> bytes:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    try:
        return AESGCM(kljuc).decrypt(_nonce(predpona, seq), sifropis, dodatno)
    except Napaka:
        raise
    except Exception as e:  # noqa: BLE001
        raise Napaka("sporocilo se ni desifriralo (pokvarjeno ali podtaknjeno)") from e


def na_voljo() -> bool:
    """Ali je kriptografija na voljo (brez nje zascite ni - in tudi nezascitenega nadomestka ne)."""
    try:
        from cryptography.hazmat.primitives.asymmetric import ec  # noqa: F401
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------------------------- seja

@dataclass
class Seja:
    session_id: str
    moj_id: str
    tuj_id: str
    vloga: str                      # "a" = zaceli smo mi, "b" = zacela je druga naprava
    kljuci: Kljuci
    jedro: str                      # jedro naprave iz PREVERJENEGA kljuca (na to se veze dostop)
    nastala: float
    seq_ven: int = 0
    st_sporocila: int = 0
    zadnji_noter: int = -1
    zadnja: List[Tuple[int, float, dict]] = field(default_factory=list)     # (prvi seq, cas, notranje sporocilo)
    deli: Dict[int, Tuple[float, int, Dict[int, bytes]]] = field(default_factory=dict)   # m -> (cas, n, {i: del})

    @property
    def smer_ven(self) -> str:
        return "ab" if self.vloga == "a" else "ba"

    @property
    def smer_noter(self) -> str:
        return "ba" if self.vloga == "a" else "ab"


@dataclass
class _Dogovor:
    session_id: str
    tuj_id: str
    zasebni: object
    epk: str
    nonce: str
    zacet: float
    vrsta: List[dict] = field(default_factory=list)


class Upravitelj:
    """Seje zascite z drugimi napravami za EN program te naprave (en id v Linku).

    moj_id        -> id, pod katerim je ta program prijavljen v Link
    poslji        -> poslje sporocilo (dict) srediscu; True, ce je slo v vrsto
    podpisi       -> podpis bajtov s kljucem TE naprave (base64, SHA256withECDSA DER)
    kljuc_za      -> javni kljuc naprave z danim id-jem iz NASEGA kroga zaupanja (base64 SPKI DER) ali None
    preveri       -> (kljuc, bajti, podpis) -> bool
    id_iz_kljuca  -> jedro naprave iz kljuca (n-<16 hex>)
    ob_sporocilu  -> (notranje sporocilo, id posiljatelja, jedro iz preverjenega kljuca): sporocilo je prislo zasciteno
    ob_seji       -> (jedro): z napravo je vzpostavljena preverjena seja (klicatelj si zapomni, da naprava zascito zna)
    ob_zavrnitvi  -> (notranje sporocilo, besedilo, koda): sredisce sporocila ni moglo dostaviti (naprave ni v Linku ...)
    ob_sprejemu   -> (notranje sporocilo): sredisce je sporocilo sprejelo v posredovanje ciljni napravi
    """

    def __init__(self, moj_id: Callable[[], str], poslji: Callable[[dict], bool], podpisi: Callable[[bytes], str],
                 kljuc_za: Callable[[str], Optional[str]], preveri: Callable[[str, bytes, str], bool],
                 id_iz_kljuca: Callable[[str], str], ob_sporocilu: Callable[[dict, str, str], None],
                 ob_seji: Optional[Callable[[str], None]] = None, ura: Callable[[], float] = time.monotonic,
                 ob_zavrnitvi: Optional[Callable[[dict, str, str], None]] = None,
                 ob_sprejemu: Optional[Callable[[dict], None]] = None) -> None:
        self._moj_id = moj_id
        self._poslji = poslji
        self._podpisi = podpisi
        self._kljuc_za = kljuc_za
        self._preveri = preveri
        self._id_iz_kljuca = id_iz_kljuca
        self._ob_sporocilu = ob_sporocilu
        self._ob_seji = ob_seji
        self._ob_zavrnitvi = ob_zavrnitvi
        self._ob_sprejemu = ob_sprejemu
        self._ura = ura
        # oznaka sporocila prenosa -> (cas, ali je ponudba dogovora, notranja sporocila, ki jih nosi ali nanj cakajo)
        self._izhodna: Dict[str, Tuple[float, bool, List[dict]]] = {}
        self._zaklep = threading.RLock()
        self._seje: Dict[str, Seja] = {}            # session_id -> seja
        self._za: Dict[str, str] = {}               # id druge naprave -> session_id seje, po kateri posiljamo
        self._dogovori: Dict[str, _Dogovor] = {}    # id druge naprave -> dogovor, ki ga cakamo

    # ------------------------------------------------------------------ posiljanje

    def ima_sejo(self, tuj_id: str) -> bool:
        with self._zaklep:
            return self._seja_za(tuj_id) is not None

    def jedro_seje(self, tuj_id: str) -> str:
        with self._zaklep:
            s = self._seja_za(tuj_id)
            return s.jedro if s is not None else ""

    def dogovori_se(self, tuj_id: str) -> bool:
        """Zacne dogovor z napravo, ne da bi zanjo imeli sporocilo: napravi si dokazeta kljuc, se preden je poslan prvi
        ukaz (klicatelj si prek `ob_seji` zapomni, da naprava zascito zna). True: seja ze obstaja ali je dogovor na poti."""
        if not tuj_id or not na_voljo():
            return False
        with self._zaklep:
            if self._seja_za(tuj_id) is not None:
                return True
            d = self._dogovori.get(tuj_id)
            if d is not None and self._ura() - d.zacet <= DOGOVOR_CAKA_S:
                return True
            return self._zacni_dogovor(tuj_id, [])

    def _seja_za(self, tuj_id: str) -> Optional[Seja]:
        sid = self._za.get(tuj_id)
        s = self._seje.get(sid) if sid else None
        if s is not None and self._ura() - s.nastala > SEJA_VELJA_S:
            self._odstrani(s)
            return None
        return s

    def _odstrani(self, s: Seja) -> None:
        self._seje.pop(s.session_id, None)
        if self._za.get(s.tuj_id) == s.session_id:
            self._za.pop(s.tuj_id, None)

    def pozabi(self, tuj_id: str) -> None:
        """Naprava je odsla ali se zamenjala: njene seje in cakajoci dogovor ne veljajo vec."""
        with self._zaklep:
            for s in [s for s in self._seje.values() if s.tuj_id == tuj_id]:
                self._odstrani(s)
            self._dogovori.pop(tuj_id, None)

    def pozabi_vse(self) -> None:
        with self._zaklep:
            self._seje.clear()
            self._za.clear()
            self._dogovori.clear()
            self._izhodna.clear()

    def poslji(self, tuj_id: str, sporocilo: dict) -> bool:
        """Poslje notranje sporocilo napravi `tuj_id` zasciteno. Ce seje se ni, zacne dogovor in sporocilo pocaka nanj.
        False: zascita ni mogoca (ni kriptografije, kljuca naprave ne poznamo, vrsta je polna) - klicatelj NE sme
        poslati nezasciteno, razen ce naprava zascite sploh ne zna."""
        if not tuj_id or not na_voljo():
            return False
        with self._zaklep:
            s = self._seja_za(tuj_id)
            if s is not None:
                return self._poslji_po_seji(s, sporocilo)
            d = self._dogovori.get(tuj_id)
            if d is not None and self._ura() - d.zacet <= DOGOVOR_CAKA_S:
                if len(d.vrsta) >= NAJVEC_V_VRSTI:
                    return False
                d.vrsta.append(sporocilo)
                return True
            # Dogovora se ni ali pa nanj cakamo predolgo: zacnemo znova. Kar je cakalo na starega, zavrzemo - ukaz, ki bi
            # se izvedel cez vec sekund, je slabsi od ukaza, ki se ne izvede (klicatelj je medtem ze javil napako).
            return self._zacni_dogovor(tuj_id, [sporocilo])

    def _zacni_dogovor(self, tuj_id: str, vrsta: List[dict]) -> bool:
        if not self._kljuc_za(tuj_id):
            return False            # naprave ni v nasem krogu: nimamo s cim preveriti njenega odgovora
        moj = self._moj_id()
        if not moj:
            return False
        try:
            zasebni, epk = nov_par()
            session_id = base64.urlsafe_b64encode(os.urandom(16)).decode("ascii").rstrip("=")
            nonce = _b64(os.urandom(16))
            podpis = self._podpisi(podatki_ponudbe(session_id, moj, tuj_id, nonce, epk))
        except Exception:  # noqa: BLE001
            return False
        if not podpis:
            return False
        dogovor = _Dogovor(session_id, tuj_id, zasebni, epk, nonce, self._ura(), vrsta[-NAJVEC_V_VRSTI:])
        self._dogovori[tuj_id] = dogovor
        self._zapomni_izhodno(PREDPONA_OZNAK + session_id[:10], dogovor.vrsta, dogovor=True)
        ok = self._poslji({"id": PREDPONA_OZNAK + session_id[:10], "type": "data.offer", "target": tuj_id,
                           "payload": {"session_id": session_id, "purpose": NAMEN, "v": RAZLICICA, "from": moj,
                                       "to": tuj_id, "nonce": nonce, "epk": epk, "ts": round(time.time(), 3),
                                       "sig": podpis}})
        if not ok:
            self._dogovori.pop(tuj_id, None)
        return ok

    def _poslji_po_seji(self, s: Seja, sporocilo: dict, zapomni: bool = True) -> bool:
        try:
            cistopis = json.dumps(sporocilo, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        except Exception:  # noqa: BLE001
            return False
        deli = [cistopis[i:i + DOLZINA_DELA] for i in range(0, len(cistopis), DOLZINA_DELA)] or [b""]
        if len(deli) > NAJVEC_DELOV:
            return False
        kljuc, predpona = s.kljuci.smer(s.smer_ven)
        m = s.st_sporocila
        s.st_sporocila += 1
        prvi = s.seq_ven
        s.seq_ven += len(deli)
        # Zapomnimo si PRED posiljanjem: odgovor »ni seje« lahko pride, se preden se posiljanje vrne.
        if zapomni:
            zdaj = self._ura()
            s.zadnja[:] = [z for z in s.zadnja if zdaj - z[1] <= PONOVI_MLAJSE_OD_S]
            s.zadnja.append((prvi, zdaj, sporocilo))
            del s.zadnja[:-HRANI_ZADNJIH]
        self._zapomni_izhodno("%s%s-%d" % (PREDPONA_OZNAK, s.session_id[:8], prvi), [sporocilo])
        for i, kos in enumerate(deli):
            seq = prvi + i
            podatki = sifriraj(kljuc, predpona, seq, kos, aad(s.session_id, s.smer_ven, seq, m, i, len(deli)))
            if not self._poslji({"id": "%s%s-%d" % (PREDPONA_OZNAK, s.session_id[:8], seq), "type": "data.chunk", "target": s.tuj_id,
                                 "payload": {"session_id": s.session_id, "seq": seq, "m": m, "i": i, "n": len(deli),
                                             "data": _b64(podatki)}}):
                return False
        return True

    def _zapomni_izhodno(self, oznaka: str, notranja: List[dict], dogovor: bool = False) -> None:
        zdaj = self._ura()
        for stara in [o for o, v in self._izhodna.items() if zdaj - v[0] > IZHODNA_VELJAJO_S]:
            self._izhodna.pop(stara, None)
        self._izhodna[oznaka] = (zdaj, dogovor, notranja)
        while len(self._izhodna) > NAJVEC_IZHODNIH:
            self._izhodna.pop(next(iter(self._izhodna)))

    # ------------------------------------------------------------------ prejem

    def _prejmi_potrditev(self, sporocilo: dict) -> bool:
        """Potrditev sredisca za nase sporocilo prenosa. Sprejeto: notranje sporocilo je na poti - javimo sprejem (za
        ponudbo dogovora nic: sporocila se cakajo na odgovor naprave). Zavrnjeno: notranja sporocila, ki jih je nosilo
        ali so nanj cakala, javimo klicatelju kot zavrnjena."""
        oznaka = str(sporocilo.get("ref_id") or "")
        if not oznaka.startswith(PREDPONA_OZNAK) or sporocilo.get("sender"):
            return False
        stanje = str(sporocilo.get("status") or "")
        with self._zaklep:
            vnos = self._izhodna.pop(oznaka, None)
            if vnos is None:
                return True
            je_dogovor, notranja = vnos[1], list(vnos[2])
            if stanje not in ("accepted", "queued"):
                for tuj_id, d in list(self._dogovori.items()):
                    if PREDPONA_OZNAK + d.session_id[:10] == oznaka:
                        self._dogovori.pop(tuj_id, None)
        if stanje in ("accepted", "queued"):
            if stanje == "accepted" and not je_dogovor and self._ob_sprejemu is not None:
                for n in notranja:
                    try:
                        self._ob_sprejemu(n)
                    except Exception:  # noqa: BLE001
                        pass
            return True
        if self._ob_zavrnitvi is not None:
            for n in notranja:
                try:
                    self._ob_zavrnitvi(n, str(sporocilo.get("error") or ""), str(sporocilo.get("error_code") or ""))
                except Exception:  # noqa: BLE001
                    pass
        return True

    def prejmi(self, sporocilo: dict) -> bool:
        """Obdela prejeto data.offer / data.answer / data.chunk / data.error z namenom "link" in potrditev sredisca
        (data.ack) za nasa sporocila prenosa. True: sporocilo je bilo nase (klicatelj ga ne obravnava naprej); False:
        ni del zascite Linka (npr. prenos datoteke)."""
        tip = str(sporocilo.get("type") or "")
        if tip == "data.ack":
            return self._prejmi_potrditev(sporocilo)
        if tip not in TIPI_PRENOSA:
            return False
        tovor = sporocilo.get("payload")
        if not isinstance(tovor, dict):
            return False
        posiljatelj = str(sporocilo.get("sender") or "")
        try:
            if tip == "data.offer":
                if str(tovor.get("purpose") or "") != NAMEN:
                    return False
                self._prejmi_ponudbo(tovor, posiljatelj)
                return True
            if tip == "data.answer":
                if str(tovor.get("purpose") or "") != NAMEN:
                    return False
                self._prejmi_odgovor(tovor, posiljatelj)
                return True
            sid = str(tovor.get("session_id") or "")
            if tip == "data.chunk":
                with self._zaklep:
                    s = self._seje.get(sid)
                if s is None:
                    if "m" not in tovor:
                        return False            # kos drugega prenosa (datoteka), ne nase seje
                    self._javi_ni_seje(posiljatelj, sid, tovor.get("seq"))
                    return True
                self._prejmi_kos(s, tovor, posiljatelj)
                return True
            if tip == "data.error":
                return self._prejmi_napako(tovor, posiljatelj)
        except Napaka as e:
            print("[SafeerE2E] zavrnjeno (%s od %s): %s" % (tip, _zakrij(posiljatelj), e), flush=True)
            return True
        return False

    def _kljuc_ali_napaka(self, tuj_id: str) -> str:
        kljuc = self._kljuc_za(tuj_id)
        if not kljuc:
            raise Napaka("naprave ni v krogu zaupanja")
        return kljuc

    def _prejmi_ponudbo(self, t: dict, posiljatelj: str) -> None:
        if not na_voljo():
            raise Napaka("kriptografija ni na voljo")
        session_id, od_id, do_id = str(t.get("session_id") or ""), str(t.get("from") or ""), str(t.get("to") or "")
        nonce, epk, sig = str(t.get("nonce") or ""), str(t.get("epk") or ""), str(t.get("sig") or "")
        moj = self._moj_id()
        if not (session_id and od_id and nonce and epk and sig) or _celo(t.get("v")) != RAZLICICA:
            raise Napaka("ponudbi manjka polje ali ima drugo razlicico")
        if len(session_id) > 64 or len(nonce) > 64 or len(epk) > 400:
            raise Napaka("ponudba ima predolgo polje")
        if do_id != moj:
            raise Napaka("ponudba ni namenjena temu programu")
        if posiljatelj and posiljatelj != od_id:
            raise Napaka("posiljatelj sredisca se ne ujema s podpisano ponudbo")
        kljuc = self._kljuc_ali_napaka(od_id)
        if not self._preveri(kljuc, podatki_ponudbe(session_id, od_id, do_id, nonce, epk), sig):
            raise Napaka("podpis ponudbe se ne ujema s kljucem naprave v krogu")
        zasebni, moj_epk = nov_par()
        moj_nonce = _b64(os.urandom(16))
        podpis = self._podpisi(podatki_odgovora(session_id, moj, od_id, nonce, moj_nonce, epk, moj_epk))
        if not podpis:
            raise Napaka("odgovora ni bilo mogoce podpisati")
        kljuci = izpelji(ecdh(zasebni, epk), session_id, nonce, moj_nonce, od_id, moj)
        seja = Seja(session_id, moj, od_id, "b", kljuci, self._id_iz_kljuca(kljuc), self._ura())
        with self._zaklep:
            if session_id in self._seje:
                raise Napaka("seja s to oznako ze obstaja")
            self._omeji_seje()
            self._seje[session_id] = seja
            # Po tej seji tudi posiljamo, razen ce ravno cakamo na odgovor na SVOJO ponudbo (takrat velja nasa).
            if od_id not in self._dogovori:
                self._za[od_id] = session_id
        self._poslji({"id": "e2e-" + session_id[:10] + "-o", "type": "data.answer", "target": od_id,
                      "payload": {"session_id": session_id, "purpose": NAMEN, "v": RAZLICICA, "from": moj, "to": od_id,
                                  "offer_nonce": nonce, "nonce": moj_nonce, "epk": moj_epk,
                                  "ts": round(time.time(), 3), "sig": podpis}})
        self._javi_sejo(seja)

    def _prejmi_odgovor(self, t: dict, posiljatelj: str) -> None:
        session_id, od_id, do_id = str(t.get("session_id") or ""), str(t.get("from") or ""), str(t.get("to") or "")
        nonce, epk, sig = str(t.get("nonce") or ""), str(t.get("epk") or ""), str(t.get("sig") or "")
        with self._zaklep:
            d = self._dogovori.get(od_id)
            if d is None or d.session_id != session_id:
                raise Napaka("odgovor ne pripada dogovoru, ki ga cakamo")
        moj = self._moj_id()
        if not (nonce and epk and sig) or do_id != moj or len(nonce) > 64 or len(epk) > 400:
            raise Napaka("odgovoru manjka polje ali ni namenjen temu programu")
        if posiljatelj and posiljatelj != od_id:
            raise Napaka("posiljatelj sredisca se ne ujema s podpisanim odgovorom")
        if str(t.get("offer_nonce") or "") != d.nonce:
            raise Napaka("odgovor ne veze nase ponudbe")
        kljuc = self._kljuc_ali_napaka(od_id)
        if not self._preveri(kljuc, podatki_odgovora(session_id, od_id, moj, d.nonce, nonce, d.epk, epk), sig):
            raise Napaka("podpis odgovora se ne ujema s kljucem naprave v krogu")
        kljuci = izpelji(ecdh(d.zasebni, epk), session_id, d.nonce, nonce, moj, od_id)
        seja = Seja(session_id, moj, od_id, "a", kljuci, self._id_iz_kljuca(kljuc), self._ura())
        with self._zaklep:
            if self._dogovori.get(od_id) is not d:
                raise Napaka("dogovor se je medtem zamenjal")
            self._dogovori.pop(od_id, None)
            self._izhodna.pop(PREDPONA_OZNAK + session_id[:10], None)
            self._omeji_seje()
            self._seje[session_id] = seja
            self._za[od_id] = session_id
            vrsta, d.vrsta = d.vrsta, []
            for sporocilo in vrsta:
                self._poslji_po_seji(seja, sporocilo)
        self._javi_sejo(seja)

    def _javi_sejo(self, seja: Seja) -> None:
        if self._ob_seji is not None:
            try:
                self._ob_seji(seja.jedro)
            except Exception:  # noqa: BLE001
                pass

    def _omeji_seje(self) -> None:
        zdaj = self._ura()
        for s in [s for s in self._seje.values() if zdaj - s.nastala > SEJA_VELJA_S]:
            self._odstrani(s)
        while len(self._seje) >= NAJVEC_SEJ:
            self._odstrani(min(self._seje.values(), key=lambda s: s.nastala))

    def _prejmi_kos(self, s: Seja, t: dict, posiljatelj: str) -> None:
        if posiljatelj and posiljatelj != s.tuj_id:
            raise Napaka("kos je prisel od druge naprave kot seja")
        seq, m, i, n = _celo(t.get("seq")), _celo(t.get("m")), _celo(t.get("i")), _celo(t.get("n"))
        if seq < 0 or n < 1 or n > NAJVEC_DELOV or i < 0 or i >= n or m < 0:
            raise Napaka("neveljavna delitev sporocila")
        sifropis = _iz_b64(str(t.get("data") or ""), "data")
        kljuc, predpona = s.kljuci.smer(s.smer_noter)
        with self._zaklep:
            if seq <= s.zadnji_noter:
                raise Napaka("stevec se ponavlja ali gre nazaj")
            kos = desifriraj(kljuc, predpona, seq, sifropis, aad(s.session_id, s.smer_noter, seq, m, i, n))
            s.zadnji_noter = seq
            zdaj = self._ura()
            for stari in [k for k, v in s.deli.items() if zdaj - v[0] > NEDOKONCANA_VELJAJO_S]:
                s.deli.pop(stari, None)
            if n == 1:
                cistopis: Optional[bytes] = kos
            else:
                _cas, _n, zbrani = s.deli.setdefault(m, (zdaj, n, {}))
                if _n != n:
                    s.deli.pop(m, None)
                    raise Napaka("deli sporocila se ne ujemajo")
                zbrani[i] = kos
                if len(zbrani) < n:
                    return
                s.deli.pop(m, None)
                cistopis = b"".join(zbrani[j] for j in range(n))
        try:
            notranje = json.loads(cistopis.decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            raise Napaka("notranje sporocilo ni JSON") from e
        if not isinstance(notranje, dict) or str(notranje.get("type") or "") in TIPI_PRENOSA:
            raise Napaka("neveljavno notranje sporocilo")
        self._ob_sporocilu(notranje, s.tuj_id, s.jedro)

    def _javi_ni_seje(self, cilj: str, session_id: str, seq: object) -> None:
        if not cilj or not session_id:
            return
        self._poslji({"id": "e2e-err-" + session_id[:8], "type": "data.error", "target": cilj,
                      "payload": {"session_id": session_id[:64], "code": "ni_seje", "seq": _celo(seq)}})

    def _prejmi_napako(self, t: dict, posiljatelj: str) -> bool:
        """Druga naprava seje ne pozna vec. Sporocilo ni podpisano (kdor ga ponaredi, doseze le nov dogovor), zato
        naredimo samo to: sejo zavrzemo, se dogovorimo znova in sveza nepotrjena sporocila posljemo se enkrat."""
        sid = str(t.get("session_id") or "")
        with self._zaklep:
            s = self._seje.get(sid)
            if s is None:
                return any(d.session_id == sid for d in self._dogovori.values())
            if posiljatelj and posiljatelj != s.tuj_id:
                return True
            if str(t.get("code") or "") != "ni_seje":
                return True
            od = _celo(t.get("seq"))
            zdaj = self._ura()
            ponovi = [sp for prvi, cas, sp in s.zadnja if prvi >= od >= 0 and zdaj - cas <= PONOVI_MLAJSE_OD_S]
            self._odstrani(s)
            if ponovi and s.tuj_id not in self._dogovori:
                self._zacni_dogovor(s.tuj_id, ponovi)
        return True


def _celo(vrednost: object, privzeto: int = -1) -> int:
    """Celo stevilo iz polja sporocila; karkoli drugega (niz, None, decimalka, bool) da `privzeto`."""
    return vrednost if isinstance(vrednost, int) and not isinstance(vrednost, bool) else privzeto


def _zakrij(device_id: str) -> str:
    """Oznaka naprave za dnevnik: brez sredine (dnevniki se kopirajo v porocila)."""
    d = str(device_id or "")
    return d if len(d) < 12 else d[:2] + "…" + d[14:]
