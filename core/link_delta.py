"""Prenos samo spremenjenih delov datoteke (»Nadaljuj na drugi napravi«): razrez po vsebini in sestava.

Datoteko razrezemo na kose, katerih meje doloca vsebina (ne odmik): vstavljen ali izbrisan bajt premakne samo meje okoli
sebe, vsi drugi kosi ostanejo enaki. Povprecna dolzina kosa P je potenca 2 blizu velikost/128 (4-64 KiB, gre v opis),
kos je dolg najmanj P/4 in najvec 4P. Meja je za bajtom i, kadar je okenska zgoscena vrednost zadnjih 32 bajtov (gear, 32 bitov) na zgornjih
bitih nicelna - pred povprecno dolzino s strozjo masko, po njej z blazjo (normaliziran razrez kot pri FastCDC).

Vrednost je odvisna SAMO od 32 bajtov okna, zato da cisti Python in numpy (ce je namescen, je hitrejsi) iste meje -
streznik in odjemalec morata rezati enako, sicer se kosi ne ujemajo (pravilnost ostane, prihranka ni).

Vsak kos ima SHA-256, cela datoteka tudi. Odjemalec iz opisa (manifest) druge naprave sestavi datoteko: kose, ki jih
ze ima v lokalnih virih (prejsnja kopija iste datoteke, delovna kopija), vzame z diska, manjkajoce prenese z obsegi
(`Range`; sosednji manjkajoci kosi gredo v eno zahtevo). Vsak kos in celo datoteko preveri; ob neujemanju datoteko
prenese v celoti. Pisanje gre v zacasno datoteko, ki na koncu atomsko zamenja cilj.

Modul je cist: brez omrezja (prenos poda klicatelj kot funkcijo) in brez GTK.
"""
from __future__ import annotations

import hashlib
import math
import os
import tempfile
import time
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

#: Razlicica razreza (gre v opis). v1: stalno povprecje 64 KiB (opis brez polja "povprecno"); v2: povprecje po velikosti.
ALGORITEM_V1 = "gear32-okno32-v1"
ALGORITEM = "gear32-okno32-v2"
OKNO = 32
_M32 = 0xFFFFFFFF
#: Povprecna dolzina kosa je potenca 2 blizu velikost/128, med tema mejama: majhne in srednje datoteke (PhotoCraft .pcraft
#: ~0,5 MB: 64 KiB kosov se je ob vsaki spremembi dotaknila cisto vsakega) dobijo drobne kose, velike majhen opis.
NAJMANJSE_POVPRECJE = 4 * 1024
NAJVECJE_POVPRECJE = 64 * 1024
KOSOV_NA_DATOTEKO = 128
#: Opis v1 (starejsa naprava) ima te stalne meje - enake kot v2 s povprecjem 64 KiB.
POVPRECNO = NAJVECJE_POVPRECJE
NAJMANJ = POVPRECNO // 4
#: Najdaljsi kos pri katerihkoli parametrih (povprecje * 4).
NAJVEC = NAJVECJE_POVPRECJE * 4


class Parametri(tuple):
    """(povprecno, najmanj, najvec, maska_stroga, maska_blaga) za eno povprecno dolzino kosa (potenca 2).

    Normaliziran razrez (FastCDC): pred povprecjem mora biti nicelnih log2(povprecno)+2 zgornjih bitov okenske vrednosti
    (redkeje), po njem log2(povprecno)-2 (pogosteje) - dolzine so tako blizje povprecju."""

    def __new__(cls, povprecno: int):
        povprecno = int(povprecno)
        if povprecno < NAJMANJSE_POVPRECJE or povprecno > NAJVECJE_POVPRECJE or povprecno & (povprecno - 1):
            raise ValueError("napacno povprecje kosa")
        biti = povprecno.bit_length() - 1
        stroga = ((1 << (biti + 2)) - 1) << (32 - (biti + 2))
        blaga = ((1 << (biti - 2)) - 1) << (32 - (biti - 2))
        return super().__new__(cls, (povprecno, povprecno // 4, povprecno * 4, stroga, blaga))

    povprecno = property(lambda self: self[0])
    najmanj = property(lambda self: self[1])
    najvec = property(lambda self: self[2])
    maska_stroga = property(lambda self: self[3])
    maska_blaga = property(lambda self: self[4])


def izberi_povprecno(velikost: int) -> int:
    """Povprecna dolzina kosa za datoteko te velikosti: potenca 2 najblizje velikost/128, med 4 in 64 KiB."""
    cilj = max(1.0, float(velikost) / KOSOV_NA_DATOTEKO)
    biti = round(math.log2(cilj))
    return int(min(NAJVECJE_POVPRECJE, max(NAJMANJSE_POVPRECJE, 1 << max(0, biti))))


def povprecno_opisa(m: dict) -> int:
    """Povprecje, s katerim je opis narejen (v1 nima polja: 64 KiB). ValueError za neznan razrez."""
    alg = m.get("alg")
    if alg in (None, ALGORITEM_V1) and "povprecno" not in m:
        return POVPRECNO
    if alg != ALGORITEM:
        raise ValueError("neznan razrez")
    return Parametri(int(m["povprecno"])).povprecno


#: Branje datoteke po tolikih bajtih (pomnilnik ostane omejen ne glede na velikost datoteke).
BLOK = 1024 * 1024
#: Najvec toliko bajtov v eni zahtevi za manjkajoce kose (zdruzeni sosednji kosi); tudi meja pomnilnika pri sestavi.
NAJVEC_OBSEG = 8 * 1024 * 1024
#: Nad to velikostjo opisa ne delamo (to ni dokument za urejanje); odjemalec prenese datoteko v celoti.
NAJVEC_VELIKOST = 4 * 1024 * 1024 * 1024


def _gear() -> List[int]:
    """Stalna tabela 256 nakljucnih 32-bitnih vrednosti, izpeljana iz SHA-256 (enaka na vsaki napravi in razlicici)."""
    return [int.from_bytes(hashlib.sha256(b"safeer-delta-gear:%d" % i).digest()[:4], "big") for i in range(256)]


GEAR = _gear()

try:  # numpy je neobvezen: z njim je razrez nekajkrat hitrejsi, meje so enake
    import numpy as _np  # type: ignore
    _GEAR_NP = _np.array(GEAR, dtype=_np.uint32)
except ImportError:  # pragma: no cover - odvisno od namestitve
    _np = None
    _GEAR_NP = None


class NapakaDelte(Exception):
    """Sestava ni uspela (kos ali cela datoteka se ne ujema, prenos ni dal pricakovanega)."""


# ------------------------------------------------------------------ razrez

def _meja_python(buf, z: int, konec_strogo: int, konec: int, maska_stroga: int, maska_blaga: int) -> int:
    """Prvi i v [z, konec) z ustrezno okensko vrednostjo; vrne dolzino do i+1 od zacetka iskanja (relativno na buf)
    ali -1. Okno se zacne OKNO-1 bajtov pred z (buf ga mora imeti)."""
    g = GEAR
    h = 0
    for b in buf[z - (OKNO - 1):z]:
        h = ((h << 1) + g[b]) & _M32
    i = z
    for b in buf[z:konec_strogo]:
        h = ((h << 1) + g[b]) & _M32
        if not h & maska_stroga:
            return i
        i += 1
    for b in buf[konec_strogo:konec]:
        h = ((h << 1) + g[b]) & _M32
        if not h & maska_blaga:
            return i
        i += 1
    return -1


def _okenske(buf, od: int, do: int):
    """Okenske vrednosti za polozaje od..do-1 (numpy, uint32): vsota GEAR[b_(i-k)] << k za k = 0..31."""
    a = _np.frombuffer(buf, dtype=_np.uint8, count=do - (od - OKNO + 1), offset=od - OKNO + 1)
    h = _GEAR_NP[a]
    # Podvajanje: po koraku s je v h[t] vsota zadnjih 2s clenov; pet korakov (1, 2, 4, 8, 16) da okno 32.
    for s in (1, 2, 4, 8, 16):
        h = h[s:] + (h[:-s] << _np.uint32(s))
    return h


def _meja_numpy(buf, z: int, konec_strogo: int, konec: int, maska_stroga: int, maska_blaga: int) -> int:
    if konec_strogo > z:
        h = _okenske(buf, z, konec_strogo)
        zadetki = _np.flatnonzero((h & _np.uint32(maska_stroga)) == 0)
        if zadetki.size:
            return z + int(zadetki[0])
    if konec > konec_strogo:
        h = _okenske(buf, konec_strogo, konec)
        zadetki = _np.flatnonzero((h & _np.uint32(maska_blaga)) == 0)
        if zadetki.size:
            return konec_strogo + int(zadetki[0])
    return -1


def _dolzina_kosa(buf, s: int, n: int, hitro: bool, par: Parametri) -> int:
    """Dolzina kosa, ki se zacne pri s (n bajtov je na voljo v buf od s naprej, oziroma do konca datoteke)."""
    if n <= par.najmanj:
        return n
    konec = s + min(n, par.najvec)
    konec_strogo = s + min(n, par.povprecno)
    z = s + par.najmanj
    meja = (_meja_numpy if hitro else _meja_python)(buf, z, konec_strogo, konec, par.maska_stroga, par.maska_blaga)
    return (meja + 1 - s) if meja >= 0 else (konec - s)


def razrezi_tok(beri: Callable[[int], bytes], hitro: Optional[bool] = None,
                povprecno: int = POVPRECNO) -> Iterator[Tuple[int, bytes]]:
    """Kosi toka (odmik, podatki). `beri(n)` vrne naslednjih najvec n bajtov (b"" na koncu). V pomnilniku je najvec
    nekaj BLOK-ov in en kos. `hitro`: numpy (None = ce je na voljo; False = cisti Python, preizkusi)."""
    par = Parametri(povprecno)
    hitro = (_np is not None) if hitro is None else (bool(hitro) and _np is not None)
    buf = bytearray()
    zacetek_buf = 0        # odmik buf[0] v datoteki
    s = 0                  # zacetek naslednjega kosa (v datoteki)
    konec_toka = False
    while True:
        # V buf naj bo okno pred s in vsaj najdaljsi kos za njim (ali konec toka).
        while not konec_toka and (zacetek_buf + len(buf)) - s < par.najvec:
            d = beri(BLOK)
            if not d:
                konec_toka = True
                break
            buf += d
        na_voljo = zacetek_buf + len(buf) - s
        if na_voljo <= 0:
            return
        rel = s - zacetek_buf
        # Iskanje meje se zacne pri rel + najmanj (>= 1 KiB); okno pred tem (OKNO-1 bajtov) je vedno v buf.
        dolzina = _dolzina_kosa(buf, rel, na_voljo, hitro, par)
        yield s, bytes(buf[rel:rel + dolzina])
        s += dolzina
        # Odvecni zacetek buf zavrzemo, okno (OKNO-1 bajtov pred s) ostane.
        odvec = s - (OKNO - 1) - zacetek_buf
        if odvec > BLOK:
            del buf[:odvec]
            zacetek_buf += odvec


def manifest_toka(beri: Callable[[int], bytes], hitro: Optional[bool] = None, povprecno: int = POVPRECNO) -> dict:
    """Opis toka: {"v", "alg", "povprecno", "velikost", "sha256", "kosi": [[odmik, dolzina, sha256], ...]}."""
    celota = hashlib.sha256()
    kosi: List[list] = []
    velikost = 0
    for odmik, podatki in razrezi_tok(beri, hitro, povprecno):
        celota.update(podatki)
        kosi.append([odmik, len(podatki), hashlib.sha256(podatki).hexdigest()])
        velikost = odmik + len(podatki)
    return {"v": 1, "alg": ALGORITEM, "povprecno": int(povprecno), "velikost": velikost, "sha256": celota.hexdigest(),
            "kosi": kosi}


def manifest(pot: str, hitro: Optional[bool] = None, povprecno: Optional[int] = None) -> dict:
    """Opis datoteke na disku (bere jo po BLOK-ih; pomnilnik je omejen ne glede na velikost). Brez `povprecno` se
    povprecje izbere po velikosti datoteke (izberi_povprecno); odjemalec za lokalne vire poda povprecje prejetega opisa."""
    with open(pot, "rb") as d:
        if povprecno is None:
            povprecno = izberi_povprecno(os.fstat(d.fileno()).st_size)
        return manifest_toka(d.read, hitro, povprecno)


def preveri_manifest(m) -> bool:
    """Ali je opis z druge naprave smiseln: znan razrez (v1 ali v2), kosi se drzijo drug drugega in niso daljsi od
    najdaljsega kosa tega razreza, vsota je velikost, zgoscene vrednosti hex."""
    try:
        if not isinstance(m, dict) or int(m.get("v", 0)) != 1:
            return False
        najvec = Parametri(povprecno_opisa(m)).najvec
        velikost = int(m["velikost"])
        if velikost < 0 or velikost > NAJVEC_VELIKOST or not _hex64(m.get("sha256")):
            return False
        naslednji = 0
        for k in m["kosi"]:
            odmik, dolzina, h = int(k[0]), int(k[1]), k[2]
            if odmik != naslednji or dolzina <= 0 or dolzina > najvec or not _hex64(h):
                return False
            naslednji += dolzina
        return naslednji == velikost
    except (KeyError, TypeError, ValueError, IndexError):
        return False


def _hex64(h) -> bool:
    return isinstance(h, str) and len(h) == 64 and all(c in "0123456789abcdef" for c in h)


# ------------------------------------------------------------------ sestava

def zdruzi_obsege(manjkajoci: Sequence[Tuple[int, int]], najvec: int = NAJVEC_OBSEG) -> List[Tuple[int, int]]:
    """Sosednje manjkajoce kose (odmik, dolzina) zdruzi v obsege za eno zahtevo, vsak najvec `najvec` bajtov
    (en sam kos, daljsi od meje, ostane cel)."""
    izid: List[Tuple[int, int]] = []
    for odmik, dolzina in sorted(manjkajoci):
        if izid and izid[-1][0] + izid[-1][1] == odmik and izid[-1][1] + dolzina <= najvec:
            izid[-1] = (izid[-1][0], izid[-1][1] + dolzina)
        else:
            izid.append((odmik, dolzina))
    return izid


class _LokalniKosi:
    """Kazalo kosov lokalnih virov: sha256 -> (pot, odmik, dolzina). Vir je pot ali (pot, opis ali None).

    Lokalni vir mora biti razrezan z ISTIM povprecjem kot prejeti opis (sicer se noben kos ne ujema): opis z drugim
    povprecjem (ali brez opisa) izracunamo znova s povprecjem prejetega."""

    def __init__(self, viri: Iterable, povprecno: int = POVPRECNO) -> None:
        self.kazalo: Dict[str, Tuple[str, int, int]] = {}
        self._odprte: Dict[str, object] = {}
        for vir in viri or ():
            pot, opis = (vir, None) if isinstance(vir, str) else (vir[0], vir[1])
            try:
                if not pot or not os.path.isfile(pot):
                    continue
                if opis is None or povprecno_opisa(opis) != povprecno:
                    opis = manifest(pot, povprecno=povprecno)
                for odmik, dolzina, h in opis.get("kosi") or []:
                    self.kazalo.setdefault(h, (pot, int(odmik), int(dolzina)))
            except (OSError, ValueError, TypeError):
                continue

    def beri(self, h: str, dolzina: int) -> Optional[bytes]:
        """Podatki kosa z diska, ce ga imamo in se se ujema (datoteka se je lahko medtem spremenila)."""
        v = self.kazalo.get(h)
        if v is None or v[2] != dolzina:
            return None
        pot, odmik, _ = v
        try:
            d = self._odprte.get(pot)
            if d is None:
                d = self._odprte[pot] = open(pot, "rb")
            d.seek(odmik)  # type: ignore[attr-defined]
            podatki = d.read(dolzina)  # type: ignore[attr-defined]
        except OSError:
            return None
        if len(podatki) != dolzina or hashlib.sha256(podatki).hexdigest() != h:
            self.kazalo.pop(h, None)
            return None
        return podatki

    def zapri(self) -> None:
        for d in self._odprte.values():
            try:
                d.close()  # type: ignore[attr-defined]
            except OSError:
                pass
        self._odprte.clear()


def _zacasna_ob(cilj: str):
    mapa = os.path.dirname(os.path.abspath(cilj)) or "."
    os.makedirs(mapa, exist_ok=True)
    fd, pot = tempfile.mkstemp(prefix=".safeer-delta-", suffix=".part", dir=mapa)
    return os.fdopen(fd, "wb"), pot


def _sestavi_delta(m: dict, lokalni: _LokalniKosi, prenesi_obseg, f, meritve: dict) -> str:
    """Zapise datoteko v f po opisu; vrne sha256 zapisanega. Kos z napacno vrednostjo -> NapakaDelte."""
    celota = hashlib.sha256()
    kosi = m["kosi"]
    i = 0
    while i < len(kosi):
        odmik, dolzina, h = int(kosi[i][0]), int(kosi[i][1]), kosi[i][2]
        podatki = lokalni.beri(h, dolzina)
        if podatki is not None:
            f.write(podatki)
            celota.update(podatki)
            meritve["kosov_lokalno"] += 1
            meritve["iz_lokalnih"] += dolzina
            i += 1
            continue
        # Niz zaporednih manjkajocih kosov do meje obsega: ena zahteva.
        j, skupaj = i, 0
        while j < len(kosi) and (j == i or skupaj + int(kosi[j][1]) <= NAJVEC_OBSEG):
            if j > i and lokalni.kazalo.get(kosi[j][2]) is not None:
                break
            skupaj += int(kosi[j][1])
            j += 1
        podatki = prenesi_obseg(odmik, skupaj)
        meritve["zahtev"] += 1
        meritve["podatki"] += len(podatki or b"")
        if not isinstance(podatki, (bytes, bytearray)) or len(podatki) != skupaj:
            raise NapakaDelte("obseg_napacne_dolzine")
        mv = memoryview(podatki)
        pos = 0
        for k in range(i, j):
            dl = int(kosi[k][1])
            if hashlib.sha256(mv[pos:pos + dl]).hexdigest() != kosi[k][2]:
                raise NapakaDelte("kos_se_ne_ujema")
            pos += dl
        f.write(podatki)
        celota.update(podatki)
        meritve["kosov_preneseno"] += j - i
        i = j
    return celota.hexdigest()


def _prenesi_vse(velikost: int, prenesi_obseg, f, meritve: dict) -> str:
    celota = hashlib.sha256()
    odmik = 0
    while odmik < velikost:
        dolzina = min(NAJVEC_OBSEG, velikost - odmik)
        podatki = prenesi_obseg(odmik, dolzina)
        meritve["zahtev"] += 1
        meritve["podatki"] += len(podatki or b"")
        if not isinstance(podatki, (bytes, bytearray)) or len(podatki) != dolzina:
            raise NapakaDelte("obseg_napacne_dolzine")
        f.write(podatki)
        celota.update(podatki)
        odmik += dolzina
    return celota.hexdigest()


def nove_meritve() -> dict:
    return {"velikost": 0, "podatki": 0, "iz_lokalnih": 0, "kosov": 0, "kosov_lokalno": 0, "kosov_preneseno": 0,
            "zahtev": 0, "polno": False, "razlog": "", "cas_s": 0.0}


def sestavi(m: dict, lokalni_viri: Iterable, prenesi_obseg: Callable[[int, int], bytes], cilj: str,
            polno_ob_napaki: bool = True) -> dict:
    """Iz opisa `m` sestavi datoteko `cilj`: kose iz `lokalni_viri` (poti ali (pot, opis)) vzame z diska, manjkajoce
    prenese s `prenesi_obseg(odmik, dolzina) -> bytes`. Pise v zacasno datoteko ob cilju in jo na koncu atomsko
    premakne na cilj. Ob neujemanju kosa ali cele datoteke (in `polno_ob_napaki`) datoteko prenese v celoti in jo
    preveri z opisom. Vrne meritve (podatki = bajti po omrezju, iz_lokalnih = bajti z diska ...). NapakaDelte, ce
    datoteke ni mogoce dobiti take, kot jo opisuje opis (npr. se je na drugi napravi medtem spremenila)."""
    if not preveri_manifest(m):
        raise NapakaDelte("napacen_opis")
    zacetek = time.monotonic()
    meritve = nove_meritve()
    meritve["velikost"] = int(m["velikost"])
    meritve["kosov"] = len(m["kosi"])
    lokalni = _LokalniKosi(lokalni_viri, povprecno_opisa(m))
    f, zacasna = _zacasna_ob(cilj)
    try:
        try:
            dobljen = _sestavi_delta(m, lokalni, prenesi_obseg, f, meritve)
            if dobljen != m["sha256"]:
                raise NapakaDelte("celota_se_ne_ujema")
        except NapakaDelte as e:
            if not polno_ob_napaki:
                raise
            meritve["polno"], meritve["razlog"] = True, str(e)
            f.seek(0)
            f.truncate()
            meritve["iz_lokalnih"] = meritve["kosov_lokalno"] = 0
            meritve["kosov_preneseno"] = meritve["kosov"]
            if _prenesi_vse(int(m["velikost"]), prenesi_obseg, f, meritve) != m["sha256"]:
                raise NapakaDelte("datoteka_se_spreminja")
        f.flush()
        os.fsync(f.fileno())
        f.close()
        os.replace(zacasna, cilj)
    except BaseException:
        try:
            f.close()
        except OSError:
            pass
        try:
            os.remove(zacasna)
        except OSError:
            pass
        raise
    finally:
        lokalni.zapri()
    meritve["cas_s"] = round(time.monotonic() - zacetek, 3)
    return meritve


def prenesi_celo(velikost: int, prenesi_obseg: Callable[[int, int], bytes], cilj: str) -> dict:
    """Naprava brez opisov (starejsa ali Android): datoteka v celoti, po obsegih, z atomsko zamenjavo cilja."""
    zacetek = time.monotonic()
    meritve = nove_meritve()
    meritve.update(velikost=int(velikost), polno=True, razlog="naprava_brez_opisa")
    f, zacasna = _zacasna_ob(cilj)
    try:
        _prenesi_vse(int(velikost), prenesi_obseg, f, meritve)
        f.flush()
        os.fsync(f.fileno())
        f.close()
        os.replace(zacasna, cilj)
    except BaseException:
        try:
            f.close()
        except OSError:
            pass
        try:
            os.remove(zacasna)
        except OSError:
            pass
        raise
    meritve["cas_s"] = round(time.monotonic() - zacetek, 3)
    return meritve


def ocena(m_novi: dict, m_lokalni: Iterable[dict]) -> dict:
    """Koliko bi prenos novega opisa stal glede na lokalne opise (brez branja datotek): za meritve in orodje."""
    znani = set()
    for o in m_lokalni:
        for _, _, h in o.get("kosi") or []:
            znani.add(h)
    manjkajoci = [(int(k[0]), int(k[1])) for k in m_novi["kosi"] if k[2] not in znani]
    return {"velikost": int(m_novi["velikost"]), "kosov": len(m_novi["kosi"]),
            "kosov_lokalno": len(m_novi["kosi"]) - len(manjkajoci),
            "podatki": sum(d for _, d in manjkajoci), "zahtev": len(zdruzi_obsege(manjkajoci))}
