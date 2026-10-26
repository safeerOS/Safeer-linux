"""Lokalni stevec virov predvajanja.

Zakaj: odlocitev o narocninah mora temeljiti na meritvi, kateri vir je
res predvajal. Podatki ostanejo samo na napravi in ne vsebujejo nic o
vsebini: samo vir, dan, stevila, vsota trajanja in omejen vzorec casov.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import date, datetime, timedelta

VIRI = (
    "debrid_takoj",
    "usenet_torbox",
    "usenet_lasten",
    "usenet_cakanje",
    "webtor",
    "debrid_cakanje",
    "p2p",
    "iptv",
    "drugo",
)
NAROCNINE = ("webtor", "torbox")

# Viri, pri katerih je storitev lahko torbox; zastavico hranimo v kljucu.
_VIRI_S_STORITVIJO = ("debrid_takoj", "debrid_cakanje")
_PRIPONA_TORBOX = "+torbox"

VRSTA = "safeer-stevec-virov"
VERZIJA = 1
MIN_TRAJANJE_S = 60
MAX_DNI = 120
MAX_BAJTOV = 64 * 1024
MAX_VZOREC = 50
MIN_PREDVAJANJ = 10

_POLJA = ("predvajal", "kratki", "neuspehi", "sekunde")


def normaliziraj_vir(vir) -> str:
    """Neznan ali napacen vir gre v drugo, da klic nikoli ne pade."""
    if isinstance(vir, str) and vir in VIRI:
        return vir
    return "drugo"


def je_torbox(storitev) -> bool:
    """Primerjamo brez velikosti crk in presledkov; drugega ne hranimo."""
    return isinstance(storitev, str) and storitev.strip().lower() == "torbox"


def percentil(vrednosti, p: int):
    """Najblizji rang: rang = ceil(p/100 * n), brez interpolacije.

    Zakaj: rezultat je vedno izmerjena vrednost in ga Kotlin izracuna enako
    s celimi stevili. Pri sodem n je mediana spodnja od srednjih dveh.
    """
    if not vrednosti:
        return None
    urejene = sorted(vrednosti)
    n = len(urejene)
    rang = (p * n + 99) // 100
    rang = max(1, min(n, rang))
    return urejene[rang - 1]


def _zaokrozi(stevec: int, imenovalec: int, mest: int) -> float:
    """Zaokrozi pol navzgor s celimi stevili, da ni razlik med jeziki."""
    if imenovalec <= 0:
        return 0.0
    faktor = 10 ** mest
    celo = (2 * stevec * faktor + imenovalec) // (2 * imenovalec)
    return celo / faktor


def _v_int(vrednost):
    """Bool in neveljavne vrednosti zavrnemo, ker niso meritev."""
    if isinstance(vrednost, bool):
        return None
    if isinstance(vrednost, int):
        return vrednost
    if isinstance(vrednost, float) and vrednost == vrednost and abs(vrednost) < 1e15:
        return int(vrednost)
    return None


def _lokalni_dan(zdaj) -> date:
    """Naivni cas je ze lokalni; zavedni cas pretvorimo v lokalni pas."""
    if zdaj is None:
        return datetime.now().date()
    if isinstance(zdaj, datetime):
        if zdaj.tzinfo is not None:
            return zdaj.astimezone().date()
        return zdaj.date()
    if isinstance(zdaj, date):
        return zdaj
    raise TypeError("zdaj")


def _prazni_podatki() -> dict:
    return {"vrsta": VRSTA, "verzija": VERZIJA, "dnevi": {}}


def _veljaven_vedro(vedro) -> bool:
    if not isinstance(vedro, dict):
        return False
    for polje in _POLJA:
        v = vedro.get(polje)
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            return False
    casi = vedro.get("casi")
    if not isinstance(casi, list) or len(casi) > MAX_VZOREC:
        return False
    return all(isinstance(c, int) and not isinstance(c, bool) and c >= 0 for c in casi)


def _veljavni_kljuci_veder() -> set:
    kljuci = set(VIRI)
    kljuci.update(v + _PRIPONA_TORBOX for v in _VIRI_S_STORITVIJO)
    return kljuci


_KLJUCI_VEDER = _veljavni_kljuci_veder()


def _preveri(podatki) -> bool:
    """Tujo ali pokvarjeno datoteko prepoznamo, preden jo prepisemo."""
    if not isinstance(podatki, dict):
        return False
    if podatki.get("vrsta") != VRSTA or podatki.get("verzija") != VERZIJA:
        return False
    dnevi = podatki.get("dnevi")
    if not isinstance(dnevi, dict):
        return False
    for dan, vedra in dnevi.items():
        try:
            date.fromisoformat(dan)
        except (TypeError, ValueError):
            return False
        if not isinstance(vedra, dict):
            return False
        for kljuc, vedro in vedra.items():
            if kljuc not in _KLJUCI_VEDER or not _veljaven_vedro(vedro):
                return False
    return True


class Stevec:
    """Stevec ogledov po virih, varen za vec niti v enem procesu."""

    def __init__(self, pot):
        self._pot = os.fspath(pot)
        self._zaklep = threading.Lock()
        self._podatki = self._nalozi()

    # --- shranjevanje ---

    def _nalozi(self) -> dict:
        """Nikoli izjema: brez datoteke ali ob napaki zacnemo znova."""
        try:
            with open(self._pot, "rb") as f:
                surovo = f.read(MAX_BAJTOV * 4 + 1)
        except FileNotFoundError:
            return _prazni_podatki()
        except OSError:
            self._odmakni_pokvarjeno()
            return _prazni_podatki()
        try:
            podatki = json.loads(surovo.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, RecursionError):
            podatki = None
        if not _preveri(podatki):
            self._odmakni_pokvarjeno()
            return _prazni_podatki()
        return podatki

    def _odmakni_pokvarjeno(self) -> None:
        """Staro datoteko ohranimo za pregled, da se nic ne izgubi tiho."""
        cilj = self._pot + ".pokvarjeno"
        i = 1
        while os.path.exists(cilj):
            cilj = f"{self._pot}.pokvarjeno.{i}"
            i += 1
        try:
            os.replace(self._pot, cilj)
        except OSError:
            pass

    def _obrezi(self, danes: date) -> bytes:
        """Najprej starost, nato velikost: najstarejsi dnevi gredo prvi."""
        dnevi = self._podatki["dnevi"]
        meja = (danes - timedelta(days=MAX_DNI - 1)).isoformat()
        for dan in [d for d in dnevi if d < meja]:
            del dnevi[dan]
        while True:
            vsebina = json.dumps(
                self._podatki, separators=(",", ":"), sort_keys=True
            ).encode("utf-8")
            if len(vsebina) <= MAX_BAJTOV or len(dnevi) <= 1:
                return vsebina
            del dnevi[min(dnevi)]

    def _zapisi_atomarno(self, vsebina: bytes) -> None:
        """Zacasna datoteka + os.replace: bralec vidi staro ali novo, nikoli pol."""
        mapa = os.path.dirname(os.path.abspath(self._pot))
        os.makedirs(mapa, mode=0o700, exist_ok=True)
        fd, zacasna = tempfile.mkstemp(
            prefix=".stevec-", suffix=".tmp", dir=mapa
        )
        try:
            with os.fdopen(fd, "wb") as f:
                os.fchmod(f.fileno(), 0o600)
                f.write(vsebina)
                f.flush()
                os.fsync(f.fileno())
            os.replace(zacasna, self._pot)
        except BaseException:
            try:
                os.unlink(zacasna)
            except OSError:
                pass
            raise

    # --- javni vmesnik ---

    def zabelezi(
        self,
        vir,
        *,
        uspeh: bool,
        cas_do_slike_ms: int | None,
        trajanje_s: int,
        zdaj=None,
        storitev: str | None = None,
    ) -> bool:
        """Zabelezi en ogled. Vrne False ob napaki, izjeme ne spusti ven.

        Predvajal steje le uspeh z vsaj 60 s, ker kratek preizkus ni raba.
        """
        try:
            danes = _lokalni_dan(zdaj)
            vir = normaliziraj_vir(vir)
            kljuc = vir
            if vir in _VIRI_S_STORITVIJO and je_torbox(storitev):
                kljuc = vir + _PRIPONA_TORBOX
            trajanje = _v_int(trajanje_s)
            trajanje = trajanje if trajanje is not None and trajanje > 0 else 0
            cas = _v_int(cas_do_slike_ms)
            if cas is not None and cas < 0:
                cas = None
            uspeh = bool(uspeh)
        except Exception:
            return False
        with self._zaklep:
            try:
                dan = self._podatki["dnevi"].setdefault(danes.isoformat(), {})
                vedro = dan.setdefault(
                    kljuc,
                    {"predvajal": 0, "kratki": 0, "neuspehi": 0, "sekunde": 0, "casi": []},
                )
                if not uspeh:
                    vedro["neuspehi"] += 1
                else:
                    if trajanje >= MIN_TRAJANJE_S:
                        vedro["predvajal"] += 1
                        vedro["sekunde"] += trajanje
                    else:
                        vedro["kratki"] += 1
                    # Prvih 50 vrednosti je dovolj za oceno in ohrani velikost.
                    if cas is not None and len(vedro["casi"]) < MAX_VZOREC:
                        vedro["casi"].append(cas)
                vsebina = self._obrezi(danes)
                self._zapisi_atomarno(vsebina)
                return True
            except Exception:
                return False

    def povzetek(self, dni: int = 7, zdaj=None) -> dict:
        """Povzetek zadnjih dni (vkljucno z danes) in priporocila narocnin."""
        try:
            danes = _lokalni_dan(zdaj)
        except Exception:
            danes = datetime.now().date()
        dni_int = _v_int(dni)
        dni_int = max(1, dni_int if dni_int is not None else 7)
        od = danes - timedelta(days=dni_int - 1)
        od_iso, do_iso = od.isoformat(), danes.isoformat()

        zbir = {
            v: {"predvajal": 0, "kratki": 0, "neuspehi": 0, "sekunde": 0, "casi": []}
            for v in VIRI
        }
        torbox_predvajal = 0
        with self._zaklep:
            for dan in sorted(self._podatki["dnevi"]):
                if not (od_iso <= dan <= do_iso):
                    continue
                for kljuc, vedro in self._podatki["dnevi"][dan].items():
                    vir = kljuc.split("+", 1)[0]
                    cilj = zbir[vir]
                    for polje in _POLJA:
                        cilj[polje] += vedro[polje]
                    cilj["casi"].extend(vedro["casi"])
                    if kljuc.endswith(_PRIPONA_TORBOX) or vir == "usenet_torbox":
                        torbox_predvajal += vedro["predvajal"]

        skupaj = sum(z["predvajal"] for z in zbir.values())
        viri = {}
        for vir, z in zbir.items():
            viri[vir] = {
                "predvajal": z["predvajal"],
                "kratki": z["kratki"],
                "neuspehi": z["neuspehi"],
                "ure_gledanja": _zaokrozi(z["sekunde"], 3600, 2),
                "mediana_ms": percentil(z["casi"], 50),
                "p90_ms": percentil(z["casi"], 90),
                "delez": _zaokrozi(z["predvajal"], skupaj, 4),
            }

        def priporocilo(predvajal: int) -> str:
            if skupaj < MIN_PREDVAJANJ:
                return "premalo_podatkov"
            if predvajal == 0:
                return "ni_rabe"
            return "obdrzi"

        narocnine = {}
        for ime, predvajal in (
            ("webtor", zbir["webtor"]["predvajal"]),
            ("torbox", torbox_predvajal),
        ):
            narocnine[ime] = {
                "predvajal": predvajal,
                "delez": _zaokrozi(predvajal, skupaj, 4),
                "priporocilo": priporocilo(predvajal),
            }

        return {
            "dni": dni_int,
            "od": od_iso,
            "do": do_iso,
            "skupaj_predvajal": skupaj,
            "skupaj_neuspehi": sum(z["neuspehi"] for z in zbir.values()),
            "viri": viri,
            "narocnine": narocnine,
        }
