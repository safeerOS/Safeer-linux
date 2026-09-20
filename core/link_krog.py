"""Krog zaupanja Safeer Linka na racunalniku (Safeer Control / brskalnik za Linux).

Isti zapis in ista pravila kot na Androidu (tv-browser-2, cast/KrogZaupanja.kt): vsaka naprava ima svoj
kljuc, krog je seznam javnih kljucev vseh seznanjenih naprav in ga hrani vsaka naprava. Kdorkoli iz
kroga je lahko hub; hub preveri podpis naprave, ne zetona.

Kljuc naprave je kljuc EC P-256, ki ga Control ze dela za svoje TLS potrdilo (core/link_datoteke.py,
`zagotovi_potrdilo`, openssl). Podpisujemo z openssl, zato ni nove odvisnosti.

Zapis kroga (samo objekti, brez seznamov - tako ga bere tudi JsonLahki na Androidu):
  {"v": 1,
   "clani": {"<id>": {"kljuc": "<base64 SPKI DER>", "ime": "...", "platforma": "linux",
                      "dodano": 1758300000.0, "dodal": "<id>"}},
   "umiki": {"<id>": {"umaknjeno": 1758300000.0, "umaknil": "<id>"}}}

Zdruzevanje je deterministicno: unija clanov po id (novejsi zapis zmaga), umik ima prednost pred
vnosom, ki je starejsi od njega; vnos, novejsi od umika, napravo vrne.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import threading
import time
from typing import Dict, Optional


def _mapa_nastavitev() -> str:
    from core import link_hub  # pozno: link_hub uvaza ta modul
    return link_hub.NASTAVITVE_MAPA


def _pot_kroga() -> str:
    return os.path.join(_mapa_nastavitev(), "krog.json")


# ------------------------------------------------------------------ kljuc naprave

def _pot_kljuca() -> str:
    from core import link_datoteke
    kljuc, _potrdilo, _odtis = link_datoteke.zagotovi_potrdilo()
    return kljuc


_javni: Optional[str] = None
_zaklep = threading.Lock()


def javni_kljuc_b64() -> str:
    """Javni kljuc te naprave, base64 zapisa SubjectPublicKeyInfo (DER)."""
    global _javni
    with _zaklep:
        if _javni:
            return _javni
        der = subprocess.run(["openssl", "pkey", "-in", _pot_kljuca(), "-pubout", "-outform", "DER"],
                             check=True, capture_output=True).stdout
        _javni = base64.b64encode(der).decode("ascii")
        return _javni


def podpisi(podatki: bytes) -> str:
    """Podpis SHA256withECDSA (DER), base64 - isto kot HubTls.podpisi na Androidu."""
    podpis = subprocess.run(["openssl", "dgst", "-sha256", "-sign", _pot_kljuca()],
                            input=podatki, check=True, capture_output=True).stdout
    return base64.b64encode(podpis).decode("ascii")


def preveri_podpis(kljuc_b64: str, podatki: bytes, podpis_b64: str) -> bool:
    """Ali je `podpis_b64` res podpis `podatki` s tem javnim kljucem (SHA256withECDSA)?

    Rabi ga hub, ko preverja prijavo naprave iz kroga - doslej je racunalnik znal samo podpisati,
    ker ni bil nikoli hub. Isto orodje kot pri podpisovanju (openssl), zato brez nove odvisnosti.
    Vsaka napaka pomeni False: neveljaven kljuc ali pokvarjen podpis nista izjema, ampak zavrnitev.
    """
    if not kljuc_b64 or not podpis_b64:
        return False
    try:
        der = base64.b64decode(kljuc_b64, validate=True)
        podpis = base64.b64decode(podpis_b64, validate=True)
    except Exception:
        return False
    if not podpis or not _veljaven_kljuc(kljuc_b64):
        return False
    import tempfile
    mapa = tempfile.mkdtemp(prefix="safeer-podpis-")
    try:
        pot_kljuca = os.path.join(mapa, "kljuc.der")
        pot_podpisa = os.path.join(mapa, "podpis.bin")
        with open(pot_kljuca, "wb") as d:
            d.write(der)
        with open(pot_podpisa, "wb") as d:
            d.write(podpis)
        r = subprocess.run(["openssl", "dgst", "-sha256", "-verify", pot_kljuca,
                            "-keyform", "DER", "-signature", pot_podpisa],
                           input=podatki, capture_output=True)
        return r.returncode == 0
    except Exception:
        return False
    finally:
        try:
            import shutil
            shutil.rmtree(mapa, ignore_errors=True)
        except Exception:
            pass


def podatki_za_podpis(odtis_huba: str, nonce: str, device_id: str) -> bytes:
    """Kar naprava podpise ob prijavi: vezano na odtis huba in enkratni izziv (HubUsmerjevalnik.podatkiZaPodpis)."""
    return f"safeer-link-auth\n{(odtis_huba or '').lower()}\n{nonce}\n{device_id}".encode("utf-8")


def id_iz_kljuca(kljuc_b64: str) -> str:
    """Id nove naprave iz javnega kljuca (KrogZaupanja.idIzKljuca): n- + 16 hex SHA-256."""
    return "n-" + hashlib.sha256(base64.b64decode(kljuc_b64)).hexdigest()[:16]


DOLZINA_ID_IZ_KLJUCA = 18


def je_id_iz_kljuca(device_id: str) -> bool:
    """Ali je id izpeljan iz kljuca (`n-<16 hex>`, po zelji s pripono `-control` ...)."""
    if len(device_id) < DOLZINA_ID_IZ_KLJUCA or not device_id.startswith("n-"):
        return False
    jedro = device_id[2:DOLZINA_ID_IZ_KLJUCA]
    if any(z not in "0123456789abcdef" for z in jedro):
        return False
    return len(device_id) == DOLZINA_ID_IZ_KLJUCA or device_id[DOLZINA_ID_IZ_KLJUCA] == "-"


# ------------------------------------------------------------------ krog

def _veljaven_kljuc(b64: str) -> bool:
    try:
        der = base64.b64decode(b64, validate=True)
    except Exception:
        return False
    # SPKI za P-256 (nestisnjena tocka) ima 91 bajtov; dovolimo razumen razpon, ne nesmisla.
    return 60 <= len(der) <= 200 and der[:1] == b"\x30"


class Krog:
    """Krog zaupanja te naprave; ob vsaki spremembi se zapise na disk (0600)."""

    def __init__(self, pot: Optional[str] = None) -> None:
        self.pot = pot
        self.clani: Dict[str, dict] = {}
        self.umiki: Dict[str, dict] = {}
        self._zaklep = threading.RLock()
        if pot:
            try:
                with open(pot, "r", encoding="utf-8") as d:
                    self.zdruzi(json.load(d), shrani=False)
            except Exception:
                pass

    # -- branje

    def _veljaven(self, c: dict) -> bool:
        u = self.umiki.get(c["id"])
        return not (u and u["umaknjeno"] > c["dodano"])

    def clan(self, device_id: str) -> Optional[dict]:
        with self._zaklep:
            c = self.clani.get(device_id)
            return dict(c) if c and self._veljaven(c) else None

    def je_clan(self, device_id: str) -> bool:
        return self.clan(device_id) is not None

    def clan_za_id(self, device_id: str) -> Optional[dict]:
        """Clan za id, tudi ce je id iz kljuca (n-...) in je ta kljuc v krogu pod drugim (starim) id-jem.

        Isto kot KrogZaupanja.clanZaId: id iz kljuca dokazuje isti kljuc, torej isto napravo.
        """
        c = self.clan(device_id)
        if c or not je_id_iz_kljuca(device_id):
            return c
        jedro = device_id[:DOLZINA_ID_IZ_KLJUCA]
        with self._zaklep:
            for i, c in self.clani.items():
                if self._veljaven(c) and id_iz_kljuca(c["kljuc"]) == jedro:
                    return dict(c)
        return None

    def stevilo(self) -> int:
        with self._zaklep:
            return sum(1 for c in self.clani.values() if self._veljaven(c))

    def json(self) -> dict:
        """Zapis kroga; clani in umiki po id, da je isti krog na vsaki napravi tudi isti zapis."""
        with self._zaklep:
            return {
                "v": 1,
                "clani": {i: {"kljuc": c["kljuc"], "ime": c["ime"], "platforma": c["platforma"],
                              "dodano": c["dodano"], "dodal": c["dodal"]} for i, c in sorted(self.clani.items())},
                "umiki": {i: {"umaknjeno": u["umaknjeno"], "umaknil": u["umaknil"]} for i, u in sorted(self.umiki.items())},
            }

    # -- pisanje

    def dodaj(self, device_id: str, kljuc: str, ime: str, platforma: str, dodal: str,
              dodano: Optional[float] = None) -> bool:
        if not device_id or not _veljaven_kljuc(kljuc):
            return False
        return self.zdruzi({"clani": {device_id: {"kljuc": kljuc, "ime": ime, "platforma": platforma,
                                                  "dodano": dodano if dodano is not None else time.time(),
                                                  "dodal": dodal}}})

    def umakni(self, device_id: str, kdo: str, ob: Optional[float] = None) -> bool:
        """Umakne clana (nadgrobnik ostane, da umik preide na vse naprave). Naprava, ki je ni v
        krogu, ne spremeni nicesar - sicer bi vsak tuj id pustil nadgrobnik."""
        if not self.je_clan(device_id):
            return False
        return self.zdruzi({"umiki": {device_id: {"umaknjeno": ob if ob is not None else time.time(), "umaknil": kdo}}})

    def zdruzi(self, tuj, shrani: bool = True) -> bool:
        """Zdruzi tuj krog (dict ali JSON niz). Vrne True, ce se je nas krog spremenil."""
        if isinstance(tuj, str):
            try:
                tuj = json.loads(tuj)
            except Exception:
                return False
        if not isinstance(tuj, dict):
            return False
        spremenjeno = False
        with self._zaklep:
            for i, u in (tuj.get("umiki") or {}).items():
                if not isinstance(u, dict):
                    continue
                try:
                    ob = float(u.get("umaknjeno"))
                except (TypeError, ValueError):
                    continue
                obstojeci = self.umiki.get(i)
                if obstojeci is None or obstojeci["umaknjeno"] < ob:
                    self.umiki[i] = {"umaknjeno": ob, "umaknil": str(u.get("umaknil") or "")}
                    spremenjeno = True
            for i, c in (tuj.get("clani") or {}).items():
                if not isinstance(c, dict) or not _veljaven_kljuc(str(c.get("kljuc") or "")):
                    continue
                try:
                    dodano = float(c.get("dodano") or 0.0)
                except (TypeError, ValueError):
                    dodano = 0.0
                nov = {"id": i, "kljuc": str(c["kljuc"]), "ime": str(c.get("ime") or i),
                       "platforma": str(c.get("platforma") or ""), "dodano": dodano,
                       "dodal": str(c.get("dodal") or "")}
                obstojeci = self.clani.get(i)
                if (obstojeci is None or obstojeci["dodano"] < dodano
                        or (obstojeci["dodano"] == dodano and obstojeci["kljuc"] != nov["kljuc"]
                            and obstojeci["kljuc"] < nov["kljuc"])):
                    self.clani[i] = nov
                    spremenjeno = True
                elif obstojeci["kljuc"] == nov["kljuc"] and obstojeci["dodano"] == dodano and obstojeci["ime"] != nov["ime"]:
                    obstojeci["ime"] = nov["ime"]
                    spremenjeno = True
            for i in list(self.umiki):
                c = self.clani.get(i)
                if c and c["dodano"] > self.umiki[i]["umaknjeno"]:
                    del self.umiki[i]
                    spremenjeno = True
            if spremenjeno and shrani:
                self._shrani()
        return spremenjeno

    def _shrani(self) -> None:
        if not self.pot:
            return
        try:
            os.makedirs(os.path.dirname(self.pot), exist_ok=True)
            zacasna = self.pot + ".tmp"
            with open(zacasna, "w", encoding="utf-8") as d:
                json.dump(self.json(), d, ensure_ascii=False, indent=1)
            os.chmod(zacasna, 0o600)
            os.replace(zacasna, self.pot)
        except Exception:
            pass


_krog: Optional[Krog] = None


def krog() -> Krog:
    global _krog
    with _zaklep:
        if _krog is None:
            _krog = Krog(_pot_kroga())
        return _krog


def sprejmi(tuj) -> bool:
    """Krog, ki ga je poslal hub (trust.update ali odgovor na prijavo)."""
    return krog().zdruzi(tuj)


def je_vpisan(device_id: str) -> bool:
    """Ali je ta naprava v krogu s SVOJIM trenutnim kljucem."""
    c = krog().clan(device_id)
    if not c:
        return False
    try:
        return c["kljuc"] == javni_kljuc_b64()
    except Exception:
        return False


def znan_id_za_nas_kljuc(razen: str = "") -> Optional[str]:
    """Kateri koli id (razen `razen`), pod katerim je nas kljuc ze v krogu (stari id, sorodnik), ali None."""
    try:
        kljuc = javni_kljuc_b64()
    except Exception:
        return None
    k = krog()
    with k._zaklep:
        for i, c in k.clani.items():
            if i != razen and k._veljaven(c) and c["kljuc"] == kljuc:
                return i
    return None


def lahko_s_podpisom(device_id: str) -> bool:
    """Ali se naprava lahko prijavi s podpisom: id je v krogu z nasim kljucem ali pa je nas kljuc v krogu
    pod drugim id-jem (stari id pred prehodom na id iz kljuca) - hub tak podpis sprejme in nov id vpise
    kot alias, seznanitev prezivi."""
    return je_vpisan(device_id) or znan_id_za_nas_kljuc(razen=device_id) is not None
