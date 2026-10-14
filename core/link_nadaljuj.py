"""»Nadaljuj tukaj«: datoteko z druge naprave v Safeer Linku nadaljujes urejati na tem racunalniku.

Prenese se samo, cesar ta racunalnik se nima (core/link_delta): naprava da opis kosov datoteke (`/kosi/<id>` na njenem
strezniku datotek, isti zeton in ista pravica kot prenos), manjkajoce kose pa prenesemo z obicajnim `Range` GET /d/<id>.
Kose, ki so ze tu, vzamemo iz:
  - prejsnje kopije iste datoteke s te naprave (predpomnilnik ~/.cache/safeer-os/nadaljuj/<naprava>/<oznaka>),
  - delovne kopije (kamor smo datoteko nazadnje shranili; uporabnik jo je morda medtem urejal).

Kam gre datoteka: <Prejemi>/Safeer/Z drugih naprav/<ime naprave>/<pot, kot jo vidi uporabnik>. Ce je datoteka na drugi
napravi v mapi »Z drugih naprav/<ime TEGA racunalnika>/...«, je to nasa datoteka, ki se vraca: zapisemo jo nazaj na
izvirno mesto v deljeni mapi tega racunalnika (A -> B -> A nadaljuje isto datoteko, ne kopije kopije).

Nicesar ne izgubimo: datoteko, ki jo je uporabnik tukaj spremenil po zadnjem prenosu in se razlikuje od nove, pred
zamenjavo premaknemo v Smeti (iz njih jo lahko obnovi). Pot gre neposredno ali prek Global Linka (core/link_pretok).
Obratna smer (B -> A) je ista koda na drugem racunalniku: A naredi »Nadaljuj tukaj« na datoteki z B - B mora mapo
s svojo delovno kopijo deliti (ali dovoliti ves disk), sicer je A ne vidi.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
import threading
import time
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from core import link_delta

#: Mapa delovnih kopij v mapi Prejemi/Safeer (ista kot pri torrentih in pretvorbah: core/os_torrent.mapa_prenosov).
IME_MAPE = "Z drugih naprav"
#: Zgornja meja predpomnilnika prejsnjih kopij; najdlje neuporabljene gredo prve.
NAJVEC_PREDPOMNILNIKA = 2 * 1024 * 1024 * 1024
#: Najvecji opis kosov, ki ga sprejmemo (4 GiB datoteke je ~ 60 000 kosov, ~ 6 MB JSON).
NAJVEC_OPISA = 32 * 1024 * 1024
#: Najvec tolikih ravni poti (mape) sprejmemo od strani.
NAJVEC_RAVNI = 24
#: Opis velike datoteke naprava racuna nekaj casa (cisti Python ~ 6 MB/s).
ROK_OPISA_S = 300.0

_zaklepi: Dict[str, threading.Lock] = {}
_zaklepi_kljuc = threading.Lock()


class NapakaNadaljevanja(Exception):
    """Kratka koda za stran (ni_dovoljenja, ni_datoteke, ni_dosegljiva, napacen_streznik, ...)."""


# ------------------------------------------------------------------ poti

def varno_ime(ime: str, nadomestek: str = "datoteka") -> str:
    """Ena raven poti: brez locil poti, brez . in .., brez skritega imena (zacetna pika), najvec 180 znakov."""
    ime = str(ime or "").replace("/", "_").replace("\\", "_").replace("\x00", "").strip()
    ime = re.sub(r"[\x00-\x1f]", "", ime)
    while ime.startswith("."):
        ime = "_" + ime[1:]
    ime = ime[:180].strip()
    return ime if ime and ime not in (".", "..") else nadomestek


def komponente(pot_imen: Sequence) -> List[str]:
    """Pot, kot jo uporabnik vidi v Datotekah druge naprave (mape + ime datoteke), varno za ta disk."""
    deli = [varno_ime(str(d)) for d in (pot_imen or []) if str(d or "").strip()]
    return deli[-NAJVEC_RAVNI:]


def privzeta_mapa_dela() -> str:
    try:
        from core import os_torrent
        return os.path.join(os_torrent.mapa_prenosov(), IME_MAPE)
    except Exception:  # noqa: BLE001 - brez modula torrentov: Prejemi/Safeer po svoje
        return os.path.join(os.path.expanduser("~"), "Downloads", "Safeer", IME_MAPE)


def privzeta_mapa_predpomnilnika() -> str:
    return os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "safeer-os", "nadaljuj")


def deljene_mape_tega() -> List[str]:
    """Mape, ki jih ta racunalnik deli napravam (Safeer Control, control.json "deljene_mape")."""
    pot = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "safeer-control", "control.json")
    try:
        with open(pot, encoding="utf-8") as d:
            mape = json.load(d).get("deljene_mape")
        return [os.path.realpath(os.path.expanduser(str(m))) for m in mape if str(m or "")] if isinstance(mape, list) else []
    except (OSError, ValueError, AttributeError, TypeError):
        return []


def izvirnik(deli: Sequence[str], moje_ime: str, deljene: Sequence[str]) -> str:
    """Ce je datoteka na drugi napravi v »Z drugih naprav/<ime tega racunalnika>/<deljena mapa>/...«, je to datoteka
    tega racunalnika, ki se vraca: vrne njeno izvirno pot v deljeni mapi (mapa mora obstajati), sicer "". Pot ostane
    znotraj deljene mape (tudi prek simbolnih povezav ne ven)."""
    moje = varno_ime(moje_ime, "")
    if not moje:
        return ""
    for i in range(len(deli) - 2, -1, -1):
        if deli[i] == IME_MAPE and i + 1 < len(deli) and deli[i + 1] == moje:
            ostanek = list(deli[i + 2:])
            if len(ostanek) < 2:
                return ""
            for koren in deljene:
                if os.path.basename(koren.rstrip(os.sep)) != ostanek[0] or not os.path.isdir(koren):
                    continue
                cilj = os.path.join(koren, *ostanek[1:])
                stars = os.path.realpath(os.path.dirname(cilj))
                if not os.path.isdir(stars) or not (stars == koren or stars.startswith(koren.rstrip(os.sep) + os.sep)):
                    continue
                if os.path.islink(cilj) or os.path.isdir(cilj):
                    continue
                return cilj
            return ""
    return ""


def _jedro(id_naprave: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", str(id_naprave or "naprava"))[:80] or "naprava"


def _zaklep(kljuc: str) -> threading.Lock:
    with _zaklepi_kljuc:
        z = _zaklepi.get(kljuc)
        if z is None:
            z = _zaklepi[kljuc] = threading.Lock()
        return z


def _stat(pot: str) -> Optional[list]:
    try:
        s = os.stat(pot)
        return [s.st_size, s.st_mtime_ns]
    except OSError:
        return None


def _beri_json(pot: str) -> dict:
    try:
        with open(pot, encoding="utf-8") as d:
            v = json.load(d)
        return v if isinstance(v, dict) else {}
    except (OSError, ValueError):
        return {}


def _pisi_json(pot: str, vrednost: dict) -> None:
    zacasna = pot + ".tmp"
    with open(zacasna, "w", encoding="utf-8") as d:
        json.dump(vrednost, d, separators=(",", ":"))
    os.replace(zacasna, pot)


def pocisti_predpomnilnik(mapa: str, najvec: int = NAJVEC_PREDPOMNILNIKA, ohrani: str = "") -> None:
    """Prejsnje kopije nad mejo: najdlje neuporabljene gredo (vnos, ki ga pravkar rabimo, ostane)."""
    vnosi = []
    skupaj = 0
    try:
        for jedro in os.listdir(mapa):
            pj = os.path.join(mapa, jedro)
            if not os.path.isdir(pj):
                continue
            for k in os.listdir(pj):
                pk = os.path.join(pj, k)
                vel = sum(os.path.getsize(os.path.join(pk, f)) for f in os.listdir(pk) if os.path.isfile(os.path.join(pk, f)))
                vnosi.append((os.path.getmtime(pk), pk, vel))
                skupaj += vel
    except OSError:
        return
    for _, pk, vel in sorted(vnosi):
        if skupaj <= najvec:
            break
        if os.path.realpath(pk) == os.path.realpath(ohrani or "/nic"):
            continue
        shutil.rmtree(pk, ignore_errors=True)
        skupaj -= vel


# ------------------------------------------------------------------ omrezje

class _Odjemalec:
    """Zahteve do streznika datotek druge naprave (core/link_pretok: neposredno ali prek Global Linka) s stetjem bajtov."""

    def __init__(self, vir, pretok) -> None:
        self.vir = vir
        self.pretok = pretok
        self.opis_bajtov = 0

    def opis(self) -> Optional[dict]:
        """Opis kosov ali None, ce ga naprava ne zna (starejsa razlicica, Android). Napacen zeton -> NapakaNadaljevanja."""
        povezava, odgovor = self.pretok.odpri(self.vir, "GET", vrsta="kosi", rok=ROK_OPISA_S)
        try:
            if odgovor.status in (401, 403):
                raise NapakaNadaljevanja("ni_dovoljenja")
            if odgovor.status != 200:
                odgovor.read(64 * 1024)
                return None
            telo = odgovor.read(NAJVEC_OPISA + 1)
            self.opis_bajtov += len(telo)
            if len(telo) > NAJVEC_OPISA:
                return None
            try:
                m = json.loads(telo.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                return None
            return m if link_delta.preveri_manifest(m) else None
        finally:
            povezava.close()

    def velikost(self) -> int:
        povezava, odgovor = self.pretok.odpri(self.vir, "HEAD")
        try:
            if odgovor.status in (401, 403):
                raise NapakaNadaljevanja("ni_dovoljenja")
            if odgovor.status == 404:
                raise NapakaNadaljevanja("ni_datoteke")
            if odgovor.status != 200:
                raise NapakaNadaljevanja("ni_dosegljiva")
            return int(odgovor.getheader("Content-Length") or 0)
        finally:
            povezava.close()

    def obseg(self, odmik: int, dolzina: int) -> bytes:
        if dolzina <= 0:
            return b""
        povezava, odgovor = self.pretok.odpri(self.vir, "GET", "bytes=%d-%d" % (odmik, odmik + dolzina - 1))
        try:
            if odgovor.status in (401, 403):
                raise NapakaNadaljevanja("ni_dovoljenja")
            if odgovor.status == 206:
                obseg = str(odgovor.getheader("Content-Range") or "")
                m = re.match(r"bytes (\d+)-(\d+)/", obseg)
                if not m or int(m.group(1)) != odmik:
                    raise link_delta.NapakaDelte("napacen_obseg")
            elif not (odgovor.status == 200 and odmik == 0):
                raise link_delta.NapakaDelte("obseg_%d" % odgovor.status)
            podatki = odgovor.read(dolzina)
            return podatki
        finally:
            povezava.close()


# ------------------------------------------------------------------ glavno

def nadaljuj_tukaj(streznik: dict, kljuc: str, oznaka: str, id_naprave: str, ime_naprave: str, pot_imen: Sequence,
                   moje_ime: str = "", odpri: Optional[Callable[[str], bool]] = None, pretok=None,
                   mapa_dela: Optional[str] = None, mapa_predpomnilnika: Optional[str] = None,
                   deljene: Optional[Sequence[str]] = None) -> dict:
    """Datoteko `oznaka` z naprave (`streznik` iz odgovora files.list, `kljuc` iz kroga za Global Link) shrani na ta
    racunalnik s prenosom samo manjkajocih kosov in jo odpre s privzetim programom. Vrne meritve za stran:
    {ok, pot, ime, velikost, preneseno (po omrezju: opis + podatki), podatki, opis_bajtov, iz_lokalnih, kosov,
    kosov_lokalno, zahtev, delta, polno, razlog, cas_s, izvirnik, prejsnja_v_smeteh, odprto} ali {ok: False, koda}."""
    zacetek = time.monotonic()
    from core import link_pretok
    vir = link_pretok.vir_iz_streznika(streznik, str(oznaka or ""), str(kljuc or ""))
    if vir is None:
        return {"ok": False, "koda": "napacen_streznik"}
    deli = komponente(pot_imen) or [varno_ime(str(oznaka).replace(":", "/").rsplit("/", 1)[-1])]
    mapa_dela = mapa_dela or privzeta_mapa_dela()
    mapa_pp = mapa_predpomnilnika or privzeta_mapa_predpomnilnika()
    deljene = deljene_mape_tega() if deljene is None else [os.path.realpath(d) for d in deljene]
    pot_izvirnika = izvirnik(deli, moje_ime, deljene)
    cilj = pot_izvirnika or os.path.join(mapa_dela, varno_ime(ime_naprave, _jedro(id_naprave)), *deli)
    mapa_kopije = os.path.join(mapa_pp, _jedro(id_naprave), hashlib.sha256(str(oznaka).encode("utf-8")).hexdigest()[:32])
    with _zaklep(mapa_kopije):
        try:
            izid = _nadaljuj(_Odjemalec(vir, pretok or link_pretok.pretok()), cilj, mapa_kopije)
        except NapakaNadaljevanja as e:
            return {"ok": False, "koda": str(e)}
        except link_delta.NapakaDelte as e:
            return {"ok": False, "koda": "datoteka_se_spreminja" if str(e) == "datoteka_se_spreminja" else "prenos_ni_uspel"}
        except (ConnectionError, OSError) as e:
            return {"ok": False, "koda": "ni_dosegljiva" if isinstance(e, ConnectionError) else "disk", "message": str(e)}
        except Exception as e:  # noqa: BLE001 - stran dobi kratko kodo, ne sledi sklada
            return {"ok": False, "koda": "napaka", "message": str(e)}
    try:
        pocisti_predpomnilnik(mapa_pp, ohrani=mapa_kopije)
    except OSError:
        pass
    izid.update(ok=True, pot=cilj, ime=os.path.basename(cilj), izvirnik=bool(pot_izvirnika),
                cas_s=round(time.monotonic() - zacetek, 3))
    if odpri is None:
        from core import os_datoteke
        odpri = os_datoteke.odpri
    try:
        izid["odprto"] = bool(odpri(cilj))
    except Exception:  # noqa: BLE001 - datoteka je shranjena; odpre jo lahko uporabnik sam
        izid["odprto"] = False
    return izid


def _nadaljuj(odjemalec: _Odjemalec, cilj: str, mapa_kopije: str) -> dict:
    os.makedirs(mapa_kopije, exist_ok=True)
    kopija = os.path.join(mapa_kopije, "kopija")
    pot_zapisa = os.path.join(mapa_kopije, "zapis.json")
    zapis = _beri_json(pot_zapisa)
    # Lokalni viri z opisi: prejsnja kopija (opis iz zapisa, ce se datoteka ni spremenila) in delovna kopija.
    viri: List[Tuple[str, dict]] = []
    opis_kopije = zapis.get("opis") if isinstance(zapis.get("opis"), dict) else None
    if os.path.isfile(kopija):
        if opis_kopije is None or zapis.get("kopija_stat") != _stat(kopija) or not link_delta.preveri_manifest(opis_kopije):
            opis_kopije = link_delta.manifest(kopija)
        viri.append((kopija, opis_kopije))
    opis_cilja = None
    if os.path.isfile(cilj):
        if zapis.get("cilj") == cilj and zapis.get("cilj_stat") == _stat(cilj) and opis_kopije is not None:
            opis_cilja = opis_kopije           # delovna kopija je od zadnjega prenosa nespremenjena
        else:
            opis_cilja = link_delta.manifest(cilj)
        viri.append((cilj, opis_cilja))

    zacetek = time.monotonic()
    meritve = None
    opis = None
    if not viri:
        # Prvi prenos (tu ni nobene razlicice): kosov ni s cim primerjati - brez cakanja na opis naprave cela datoteka.
        # Opis prejsnje kopije izracunamo ob naslednjem »Nadaljuj tukaj«.
        meritve = link_delta.prenesi_celo(odjemalec.velikost(), odjemalec.obseg, kopija)
        meritve.update(delta=False, razlog="prvi_prenos")
    for poskus in range(0 if meritve is not None else 2):
        opis = odjemalec.opis()
        if opis is None:
            meritve = link_delta.prenesi_celo(odjemalec.velikost(), odjemalec.obseg, kopija)
            meritve["delta"] = False
            break
        try:
            meritve = link_delta.sestavi(opis, viri, odjemalec.obseg, kopija)
            meritve["delta"] = True
            break
        except link_delta.NapakaDelte as e:
            if str(e) != "datoteka_se_spreminja" or poskus:
                raise
            # Datoteka se je na drugi napravi spremenila med opisom in prenosom: nov opis, se enkrat.
    assert meritve is not None
    sha_nove = opis["sha256"] if opis is not None else ""

    # Delovna kopija: ce jo je uporabnik tu spremenil po zadnjem prenosu in je drugacna od nove, gre v Smeti.
    v_smeteh = False
    if opis_cilja is None or opis_cilja["sha256"] != sha_nove:
        mapa_cilja = os.path.dirname(cilj)
        os.makedirs(mapa_cilja, exist_ok=True)
        fd, zacasna = tempfile.mkstemp(prefix=".safeer-nadaljuj-", suffix=".part", dir=mapa_cilja)
        try:
            with os.fdopen(fd, "wb") as f, open(kopija, "rb") as vir:
                shutil.copyfileobj(vir, f, 1024 * 1024)
                f.flush()
                os.fsync(f.fileno())
            if os.path.isfile(cilj):
                nespremenjena = zapis.get("cilj") == cilj and zapis.get("cilj_stat") == _stat(cilj)
                if not nespremenjena:
                    from core import link_urejanje
                    try:
                        link_urejanje.v_smeti(cilj)
                    except Exception as e:  # noqa: BLE001 - brez Smeti datoteke ne zamenjamo (nic se ne izgubi)
                        raise NapakaNadaljevanja("smeti") from e
                    v_smeteh = True
            os.replace(zacasna, cilj)
        except Exception:
            try:
                os.remove(zacasna)
            except OSError:
                pass
            raise
    _pisi_json(pot_zapisa, {"opis": opis, "kopija_stat": _stat(kopija), "cilj": cilj, "cilj_stat": _stat(cilj),
                            "cas": time.time()})
    try:
        os.utime(mapa_kopije)                   # za ciscenje predpomnilnika: nazadnje rabljeno
    except OSError:
        pass
    meritve["opis_bajtov"] = odjemalec.opis_bajtov
    meritve["preneseno"] = meritve["podatki"] + odjemalec.opis_bajtov
    meritve["prejsnja_v_smeteh"] = v_smeteh
    meritve["cas_prenosa_s"] = round(time.monotonic() - zacetek, 3)
    return meritve
