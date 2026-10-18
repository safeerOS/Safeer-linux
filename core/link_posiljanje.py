"""Posiljanje datotek s tega racunalnika na izbrano napravo v Safeer Linku.

Safeer OS (locen proces) poslje prek Controla (D-Bus ``Naprave.Poslji`` / ``Naprave.PosljiStanje``): uporabnik v
Datotekah povlece datoteke na napravo ali izbere »Poslji na napravo«. Vsaka datoteka gre po isti poti kot »Poslji
datoteko« v Controlu (``link_deljenje.poslji_datoteko``: oddaja sredisci, sredisce pove cilju, cilj jo prevzame in
preveri SHA-256); tu je samo vrsta z napredkom, ki jo stran bere.

Prekinjeno posiljanje se nadaljuje samo (lastnik, 18. 10. 2026: »lazje posiljanje datotek med napravami«): ce naprava
ni dosegljiva ali se povezava pretrga (koda v PREHODNE), posiljka preide v stanje »caka« in se nadaljuje pri isti
datoteki, ko je naprava spet v Linku (klicatelj poda `dosegljiva` in ob novem seznamu naprav poklice `zbudi`). Sredisce
ima ze prejeti del (HEAD /cast/file, link_deljenje.poslji_datoteko), zato gre cez omrezje samo se ostanek. Brez
`dosegljiva` je vedenje kot prej: prva napaka konca posiljanje.

Posiljke, ki se niso koncane, prezivijo ponovni zagon Safeer Controla (pregled 18. 10. 2026: vrsta je bila samo v
pomnilniku - ob ponovnem zagonu ali posodobitvi je cakajoca posiljka tiho izginila). Klicatelj poda `shramba` (pot
datoteke JSON ob nastavitvah); v njej so samo poti datotek tega racunalnika, id naprave in rok, brez zetonov.
Ob zagonu `obnovi()` nadaljuje pri prvi neposlani datoteki in pocaka na napravo, rok (CAKA_NAJVEC_S) ostane isti.

Brez GTK in brez omrezja: funkcijo za oddajo dobi od klicatelja, zato je preizkusljiv sam.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from typing import Callable, Dict, List, Optional, Tuple

#: Najvec datotek v enem posiljanju (izbira v Datotekah, skupaj z vsebino poslanih map).
NAJVEC_DATOTEK = 5000
#: Najvecja datoteka (link_hub_deljenje.NAJVECJA_DATOTEKA): prej 4 GB; zdaj meja le prostor na disku cilja.
NAJVECJA_DATOTEKA = 1024 ** 4
#: Koncanih posiljanj hranimo toliko, da stran se prebere zadnje stanje.
NAJVEC_KONCANIH = 20
#: Napake, po katerih ima nov poskus smisel, ko je naprava spet dosegljiva (izpad omrezja, naprava spi ali je ugasnjena,
#: sredisce zasedeno). Vse druge (napacen odtis, ni prostora, prevelika, naprava ni seznanjena ...) so koncne.
PREHODNE = frozenset({"naprava_ni_povezana", "sredisce_naprave_ni_dosegljivo", "posiljanje_ni_uspelo",
                      "prenos_prekinjen", "hub_ni_znan", "prevec_prenosov", "prevec_cakajocih", "ze_v_teku"})
#: Najdlje toliko cakamo, da se naprava vrne; potem posiljanje konca z zadnjo napako.
CAKA_NAJVEC_S = 24 * 3600.0
#: Razmiki med poskusi, ko naprava v seznamu je, sredisce pa je ne doseze (s, zadnji velja naprej).
RAZMIKI_S = (5.0, 10.0, 20.0, 40.0, 60.0)
#: Kako pogosto pogledamo, ali je naprava spet v Linku (zbudi() pride takoj ob novem seznamu naprav).
PREVERI_S = 15.0
#: Shranjena vrsta: najvec toliko nekoncanih posiljk, napredek najvec tako pogosto (vsaka datoteka zapise celo vrsto;
#: ob nenadnem koncu se znova poslje najvec, kar je bilo poslano v tem casu - sredisce ima ze prejeti del).
NAJVEC_SHRANJENIH = 50
SHRANI_NAJVEC_VSAKIH_S = 0.5
#: Oznaka naprave v shranjeni vrsti (kot link_nemo._VARNA_OZNAKA).
_VARNA_OZNAKA = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def datoteke_mape(mapa: str, najvec: int) -> List[Tuple[str, str]]:
    """[(pot datoteke, relativna mapa)] vseh datotek v mapi; relativna mapa se zacne z imenom mape same.
    Simbolnim povezavam ne sledimo (zanka, datoteke zunaj mape); skrite datoteke in mape ostanejo doma."""
    koren = os.path.dirname(os.path.realpath(mapa))
    izid: List[Tuple[str, str]] = []
    for pot, mape, imena in os.walk(mapa, followlinks=False):
        mape[:] = sorted(m for m in mape if not m.startswith("."))
        for ime in sorted(imena):
            dat = os.path.join(pot, ime)
            if ime.startswith(".") or os.path.islink(dat) or not os.path.isfile(dat):
                continue
            izid.append((os.path.realpath(dat), os.path.relpath(os.path.realpath(pot), koren).replace(os.sep, "/")))
            if len(izid) >= najvec:
                return izid
    return izid


class Posiljka:
    def __init__(self, naprava: str, ime_naprave: str, poti: List[str], map_: int,
                 podmape: Optional[List[str]] = None) -> None:
        self.id = uuid.uuid4().hex
        self.naprava = naprava
        self.ime_naprave = ime_naprave
        self.poti = poti
        #: Relativna mapa vsake datoteke pri posiljanju cele mape ("" = datoteka sama).
        self.podmape = list(podmape) if podmape else [""] * len(poti)
        self.velikosti = [os.path.getsize(p) for p in poti]
        self.skupaj = sum(self.velikosti)
        self.mape = map_                # poslane mape (z vso vsebino)
        self.stanje = "posiljam"        # posiljam | poslano | napaka
        self.poslanih = 0
        self.ime = os.path.basename(poti[0]) if poti else ""
        self.bajtov = 0
        self.koda = ""
        self.sporocilo = ""
        self.zasedena_od = ""
        #: Kdo je posiljanje zacel z zahtevo po obvestilu (Nemo, safeerctl --notify): Control obvesti o koncu.
        self.obvesti = False
        self.preklicano = False
        self.zbudi = threading.Event()
        #: Rok (unix cas), do katerega posiljka caka na napravo - prezivi ponovni zagon.
        self.rok = time.time() + CAKA_NAJVEC_S
        #: Datoteke, poslane pred ponovnim zagonom (obnovljena posiljka ima samo se neposlane), in prva neposlana.
        self.prej_poslanih = 0
        self.naslednja = 0

    def zapis(self) -> dict:
        """Za shranjeno vrsto: samo, kar je potrebno za nadaljevanje (brez zetonov in vsebine)."""
        return {"id": self.id, "naprava": self.naprava, "ime_naprave": self.ime_naprave,
                "poti": self.poti[self.naslednja:], "podmape": self.podmape[self.naslednja:], "mape": self.mape,
                "obvesti": bool(self.obvesti), "rok": float(self.rok), "poslanih": self.prej_poslanih + self.poslanih}

    def slovar(self) -> dict:
        odstotek = 100 if self.stanje == "poslano" else (int(self.bajtov * 100 / self.skupaj) if self.skupaj else 0)
        return {"id": self.id, "stanje": self.stanje, "naprava": self.ime_naprave,
                "datotek": self.prej_poslanih + len(self.poti), "poslanih": self.prej_poslanih + self.poslanih,
                "ime": self.ime, "odstotek": max(0, min(100, odstotek)), "mape": self.mape,
                "koda": self.koda, "sporocilo": self.sporocilo, "zasedenaOd": self.zasedena_od,
                "idNaprave": self.naprava, "obvesti": self.obvesti}


class Posiljanje:
    def __init__(self, poslji: Callable[[str, str, Callable[[int], None]], Tuple[bool, Dict[str, str]]],
                 ime_naprave: Callable[[str], str] = lambda i: i,
                 dosegljiva: Optional[Callable[[str], bool]] = None,
                 ob_spremembi: Optional[Callable[[dict], None]] = None,
                 zabelezi: Optional[Callable[[str], None]] = None,
                 ura: Callable[[], float] = time.monotonic,
                 shramba: Optional[str] = None,
                 cas: Callable[[], float] = time.time) -> None:
        """`dosegljiva(id)`: ali je naprava v Linku - z njo posiljka ob prehodni napaki pocaka in nadaljuje (brez nje
        prva napaka konca). `ob_spremembi(stanje)`: vsaka sprememba (zacetek datoteke, odstotek, caka, konec) - iz
        delovne niti. `zabelezi(id)`: naprava, ki ji je uporabnik pravkar poslal (zadnja naprava prva v menijih).
        `shramba`: datoteka JSON, v kateri nekoncane posiljke prezivijo ponovni zagon (obnovi())."""
        self._poslji = poslji
        self._ime_naprave = ime_naprave
        self._dosegljiva = dosegljiva
        self._ob_spremembi = ob_spremembi
        self._zabelezi = zabelezi
        self._ura = ura
        self._cas = cas
        self._shramba = shramba
        self._zaklep = threading.Lock()
        self._zaklep_shrambe = threading.Lock()
        self._zadnja_shranitev = 0.0
        self._posiljke: Dict[str, Posiljka] = {}

    # ------------------------------------------------------------------ shranjena vrsta
    def _shrani(self, takoj: bool = True) -> None:
        """Nekoncane posiljke v shrambo (atomarno, samo za uporabnika). `takoj=False`: najvec vsakih
        SHRANI_NAJVEC_VSAKIH_S (napredek); zacetek, cakanje in konec se zapisejo vedno."""
        if not self._shramba:
            return
        zdaj = self._ura()
        if not takoj and zdaj - self._zadnja_shranitev < SHRANI_NAJVEC_VSAKIH_S:
            return
        with self._zaklep:
            zapisi = [p.zapis() for p in self._posiljke.values()
                      if p.stanje in ("posiljam", "caka") and not p.preklicano and p.naslednja < len(p.poti)]
        with self._zaklep_shrambe:
            self._zadnja_shranitev = zdaj
            try:
                if not zapisi:
                    if os.path.exists(self._shramba):
                        os.remove(self._shramba)
                    return
                os.makedirs(os.path.dirname(self._shramba) or ".", exist_ok=True)
                zacasna = self._shramba + ".tmp"
                fd = os.open(zacasna, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as d:
                    json.dump({"v": 1, "posiljke": zapisi[:NAJVEC_SHRANJENIH]}, d, ensure_ascii=False)
                os.replace(zacasna, self._shramba)
            except OSError as e:
                print("[SafeerLink] vrste posiljanja ni bilo mogoce shraniti:", e, flush=True)

    def obnovi(self) -> int:
        """Ob zagonu: nekoncane posiljke iz shrambe nadaljujejo pri prvi neposlani datoteki (najprej pocakajo, da je
        naprava v Linku). Vrne stevilo obnovljenih. Kar ni veljavno (pot ni datoteka, potekel rok, cudna oznaka),
        izpade - shramba je nasa datoteka, a jo beremo, kot da ni."""
        if not self._shramba:
            return 0
        try:
            with open(self._shramba, encoding="utf-8") as d:
                vsebina = json.load(d)
        except (OSError, ValueError):
            return 0
        zapisi = vsebina.get("posiljke") if isinstance(vsebina, dict) else None
        obnovljene: List[Posiljka] = []
        zdaj = self._cas()
        for z in (zapisi if isinstance(zapisi, list) else [])[:NAJVEC_SHRANJENIH]:
            p = self._iz_zapisa(z, zdaj)
            if p is not None:
                obnovljene.append(p)
        with self._zaklep:
            for p in obnovljene:
                self._posiljke[p.id] = p
        self._shrani()
        for p in obnovljene:
            print("[SafeerLink] posiljanje se nadaljuje: %d datotek napravi %s" % (len(p.poti), p.naprava), flush=True)
            threading.Thread(target=self._teci, args=(p, True), name="safeer-posiljanje", daemon=True).start()
        return len(obnovljene)

    def _iz_zapisa(self, z, zdaj: float) -> Optional[Posiljka]:
        if not isinstance(z, dict):
            return None
        naprava = str(z.get("naprava") or "")
        poti, podmape = z.get("poti"), z.get("podmape")
        try:
            rok = float(z.get("rok"))
            prej = max(0, int(z.get("poslanih") or 0))
            mape = max(0, int(z.get("mape") or 0))
        except (TypeError, ValueError):
            return None
        if not _VARNA_OZNAKA.match(naprava) or naprava.startswith("-") or rok <= zdaj:
            return None
        if not isinstance(poti, list) or not isinstance(podmape, list) or len(poti) != len(podmape) \
                or not poti or len(poti) > NAJVEC_DATOTEK:
            return None
        ostanejo, mape_ostanejo = [], []
        for pot, pod in zip(poti, podmape):
            if not isinstance(pot, str) or not isinstance(pod, str) or not os.path.isabs(pot):
                return None
            pot = os.path.realpath(pot)
            if os.path.isfile(pot):
                ostanejo.append(pot)
                mape_ostanejo.append(pod)
        if not ostanejo:
            return None
        try:
            p = Posiljka(naprava, str(z.get("ime_naprave") or naprava)[:128], ostanejo, mape, mape_ostanejo)
        except OSError:
            return None
        p.obvesti = bool(z.get("obvesti"))
        p.rok = rok
        p.prej_poslanih = prej
        if len(ostanejo) < len(poti):
            print("[SafeerLink] posiljanje napravi %s: %d datotek ni vec na racunalniku" % (naprava, len(poti) - len(ostanejo)),
                  flush=True)
        p.stanje = "caka"
        return p

    def _javi(self, p: Posiljka) -> None:
        if self._ob_spremembi is None:
            return
        try:
            self._ob_spremembi(p.slovar())
        except Exception as e:  # noqa: BLE001 - obvestilo ali stran ne sme ustaviti posiljanja
            print("[SafeerLink] posiljanje (odziv):", e, flush=True)

    def zbudi(self, naprava: str = "") -> None:
        """Seznam naprav se je spremenil: cakajoce posiljke (tej napravi ali vsem) takoj poskusijo znova."""
        with self._zaklep:
            cakajo = [p for p in self._posiljke.values() if p.stanje == "caka" and (not naprava or p.naprava == naprava)]
        for p in cakajo:
            p.zbudi.set()

    def preklici(self, id_: str) -> dict:
        """Uporabnik ne zeli vec poslati (cakajoca ali tekoca posiljka): konca se pred naslednjim poskusom ali datoteko."""
        with self._zaklep:
            p = self._posiljke.get(str(id_ or ""))
        if p is None:
            return {"ok": False, "koda": "ni_posiljke"}
        if p.stanje in ("posiljam", "caka"):
            p.preklicano = True
            p.zbudi.set()
        return {"ok": True, **p.slovar()}

    def zacni(self, naprava: str, poti: List[str], obvesti: bool = False) -> dict:
        naprava = str(naprava or "").strip()
        if not naprava:
            return {"ok": False, "koda": "ni_naprave"}
        datoteke, podmape, mape = [], [], 0
        for p in poti if isinstance(poti, list) else []:
            p = os.path.realpath(str(p))
            if os.path.isdir(p):
                # Cela mapa (lastnik, 11. 10. 2026): vsaka datoteka z relativno mapo, cilj ustvari isto drevo.
                mape += 1
                for dat, pod in datoteke_mape(p, NAJVEC_DATOTEK + 1 - len(datoteke)):
                    if dat not in datoteke:
                        datoteke.append(dat)
                        podmape.append(pod)
            elif os.path.isfile(p) and p not in datoteke:
                datoteke.append(p)
                podmape.append("")
            if len(datoteke) > NAJVEC_DATOTEK:
                return {"ok": False, "koda": "prevec_datotek", "najvec": NAJVEC_DATOTEK}
        if not datoteke:
            return {"ok": False, "koda": "prazna_mapa" if mape else "ni_datoteke", "mape": mape}
        try:
            p = Posiljka(naprava, self._ime_naprave(naprava) or naprava, datoteke, mape, podmape)
        except OSError:
            return {"ok": False, "koda": "ni_datoteke"}
        if any(v > NAJVECJA_DATOTEKA for v in p.velikosti):
            return {"ok": False, "koda": "prevelika"}
        p.obvesti = bool(obvesti)
        p.rok = self._cas() + CAKA_NAJVEC_S
        if self._zabelezi is not None:
            try:
                self._zabelezi(naprava)
            except Exception as e:  # noqa: BLE001
                print("[SafeerLink] zadnja naprava:", e, flush=True)
        with self._zaklep:
            koncane = [i for i, x in self._posiljke.items() if x.stanje not in ("posiljam", "caka")]
            for i in koncane[:max(0, len(koncane) - NAJVEC_KONCANIH + 1)]:
                self._posiljke.pop(i, None)
            self._posiljke[p.id] = p
        self._shrani()
        threading.Thread(target=self._teci, args=(p,), name="safeer-posiljanje", daemon=True).start()
        return {"ok": True, **p.slovar()}

    def stanje(self, id_: str) -> dict:
        with self._zaklep:
            p = self._posiljke.get(str(id_ or ""))
        return {"ok": True, **p.slovar()} if p else {"ok": False, "koda": "ni_posiljke"}

    def _oddaj(self, p: Posiljka, pot: str, velikost: int, podmapa: str, opravljeno: int) -> Tuple[bool, dict]:
        zadnji = [-1]

        def napredek(odstotek: int, _o=opravljeno, _v=velikost) -> None:
            p.bajtov = _o + int(_v * max(0, min(100, int(odstotek))) / 100)
            if p.skupaj and int(p.bajtov * 100 / p.skupaj) != zadnji[0]:
                zadnji[0] = int(p.bajtov * 100 / p.skupaj)
                self._javi(p)

        try:
            # Brez mape klic ostane, kot je bil (tudi poslji, ki argumenta `mapa` ne pozna).
            ok, n = self._poslji(p.naprava, pot, napredek, mapa=podmapa) if podmapa else \
                self._poslji(p.naprava, pot, napredek)
        except Exception as e:  # noqa: BLE001 - posiljanje ne sme podreti Controla
            ok, n = False, {"sporocilo": str(e) or type(e).__name__, "koda": "posiljanje_ni_uspelo", "zasedenaOd": ""}
        return ok, (n if isinstance(n, dict) else {})

    def _pocakaj(self, p: Posiljka, rok: float, poskus: int) -> bool:
        """Posiljka caka, da bo naprava spet dosegljiva. True = poskusi znova, False = preklicano ali rok je potekel.
        `poskus` < 0: brez razmika (obnovljena posiljka nadaljuje, takoj ko je naprava v Linku)."""
        p.stanje = "caka"
        self._javi(p)
        self._shrani()
        najmanj = self._ura() + (RAZMIKI_S[min(poskus, len(RAZMIKI_S) - 1)] if poskus >= 0 else 0.0)
        while True:
            zdaj = self._ura()
            p.zbudi.wait(max(0.01, PREVERI_S if zdaj >= najmanj else min(PREVERI_S, najmanj - zdaj)))
            p.zbudi.clear()
            if p.preklicano or self._ura() >= rok:
                return False
            try:
                tu = bool(self._dosegljiva(p.naprava)) if self._dosegljiva is not None else False
            except Exception:  # noqa: BLE001
                tu = False
            if tu and self._ura() >= najmanj:
                p.stanje = "posiljam"
                self._javi(p)
                return True

    def _teci(self, p: Posiljka, obnovljena: bool = False) -> None:
        try:
            self._teci_vrsto(p, obnovljena)
        finally:
            self._shrani()                  # koncana (poslano, napaka, preklicano) izpade iz shrambe

    def _teci_vrsto(self, p: Posiljka, obnovljena: bool) -> None:
        opravljeno = 0
        rok = self._ura() + max(0.0, p.rok - self._cas())
        self._javi(p)
        i = 0
        poskus = 0
        if obnovljena and self._dosegljiva is not None:
            # Po ponovnem zagonu Controla seznama naprav se ni: ne poskusamo, preden je naprava v Linku.
            try:
                tu = bool(self._dosegljiva(p.naprava))
            except Exception:  # noqa: BLE001
                tu = False
            if not tu and not self._pocakaj(p, rok, -1):
                p.stanje, p.koda = "napaka", ("preklicano" if p.preklicano else (p.koda or "naprava_ni_povezana"))
                self._javi(p)
                return
        while i < len(p.poti):
            pot, velikost, podmapa = p.poti[i], p.velikosti[i], p.podmape[i]
            if p.preklicano:
                p.stanje, p.koda = "napaka", "preklicano"
                self._javi(p)
                return
            p.ime = os.path.basename(pot)
            ok, n = self._oddaj(p, pot, velikost, podmapa, opravljeno)
            if not ok:
                koda = str(n.get("koda") or "posiljanje_ni_uspelo")
                p.koda = koda
                p.sporocilo = str(n.get("sporocilo") or "")
                p.zasedena_od = str(n.get("zasedenaOd") or "")
                if (self._dosegljiva is not None and koda in PREHODNE and os.path.isfile(pot)
                        and self._pocakaj(p, rok, poskus)):
                    poskus += 1
                    p.bajtov = opravljeno
                    continue                # ista datoteka znova; sredisce pove, koliko ze ima
                if p.preklicano:
                    p.koda = "preklicano"
                elif koda in PREHODNE and not os.path.isfile(pot):
                    p.koda = "ni_datoteke"
                p.stanje = "napaka"
                self._javi(p)
                return
            poskus = 0
            p.koda = p.sporocilo = p.zasedena_od = ""
            opravljeno += velikost
            p.bajtov = opravljeno
            p.poslanih += 1
            i += 1
            p.naslednja = i
            self._shrani(takoj=False)
        p.stanje = "poslano"
        self._javi(p)


# ---------------------------------------------------------------------- zadnja naprava prva
#: Kljuc v nastavitvah Linka (link_hub.Nastavitve): id naprave -> unix cas zadnjega posiljanja.
KLJUC_ZADNJE = "posiljanje_zadnje"
NAJVEC_ZADNJIH = 32


def zabelezi_zadnjo(nastavitve, naprava: str, zdaj: Optional[float] = None) -> None:
    """Zapomni si, da je uporabnik pravkar poslal napravi `naprava` (meniji jo pokazejo prvo - en klik)."""
    naprava = str(naprava or "").strip()
    if not naprava or nastavitve is None:
        return
    zapis = nastavitve.get(KLJUC_ZADNJE) or {}
    zapis = {str(k): float(v) for k, v in zapis.items() if isinstance(v, (int, float))} if isinstance(zapis, dict) else {}
    zapis[naprava] = float(time.time() if zdaj is None else zdaj)
    if len(zapis) > NAJVEC_ZADNJIH:
        zapis = dict(sorted(zapis.items(), key=lambda x: -x[1])[:NAJVEC_ZADNJIH])
    nastavitve.podatki[KLJUC_ZADNJE] = zapis
    nastavitve.shrani()


def zadnjic(nastavitve, naprava: str) -> float:
    """Kdaj je uporabnik zadnjic poslal tej napravi (0 = se nikoli)."""
    zapis = nastavitve.get(KLJUC_ZADNJE) if nastavitve is not None else None
    try:
        return float((zapis or {}).get(str(naprava or ""), 0.0)) if isinstance(zapis, dict) else 0.0
    except (TypeError, ValueError):
        return 0.0


# ---------------------------------------------------------------------- znane naprave (tudi, ko jih zdaj ni)
#: Kljuc v nastavitvah Linka: id -> {"ime", "cas"} naprav, ki so ze sprejemale datoteke. Nemo jih ponudi tudi, ko jih
#: v Linku zdaj ni - posiljka pocaka nanje (PREHODNE, CAKA_NAJVEC_S) in se nadaljuje, ko se vrnejo.
KLJUC_ZNANE = "posiljanje_znane"
NAJVEC_ZNANIH = 32
#: Naprava, ki je toliko casa ni bilo v Linku, izpade iz menija (verjetno je ni vec).
ZNANA_VELJA_S = 90 * 86400.0
#: Cas zadnjega videnja zapisemo najvec enkrat na dan (seznam naprav pride ob vsaki spremembi - brez tega bi vsakic
#: pisali nastavitve na disk).
ZNANA_OSVEZI_S = 86400.0


def _znane(nastavitve) -> Dict[str, dict]:
    zapis = nastavitve.get(KLJUC_ZNANE) if nastavitve is not None else None
    if not isinstance(zapis, dict):
        return {}
    izid = {}
    for k, v in zapis.items():
        if isinstance(k, str) and _VARNA_OZNAKA.match(k) and isinstance(v, dict):
            try:
                izid[k] = {"ime": str(v.get("ime") or "")[:128], "cas": float(v.get("cas") or 0.0)}
            except (TypeError, ValueError):
                continue
    return izid


def zabelezi_znane(nastavitve, naprave: List[dict], zdaj: Optional[float] = None) -> bool:
    """Naprave, ki zdaj sprejmejo datoteke, si zapomnimo (ime, kdaj videna). Vrne True, ce se je zapis spremenil."""
    if nastavitve is None:
        return False
    zdaj = time.time() if zdaj is None else zdaj
    znane = _znane(nastavitve)
    spremenjeno = False
    for n in naprave or []:
        i = str(n.get("id") or "") if isinstance(n, dict) else ""
        if not _VARNA_OZNAKA.match(i) or i.startswith("-"):
            continue
        ime = str(n.get("ime") or "")[:128]
        star = znane.get(i)
        if star is None or star["ime"] != ime or zdaj - star["cas"] >= ZNANA_OSVEZI_S:
            znane[i] = {"ime": ime, "cas": zdaj}
            spremenjeno = True
    for i in [i for i, z in znane.items() if zdaj - z["cas"] > ZNANA_VELJA_S]:
        del znane[i]
        spremenjeno = True
    if len(znane) > NAJVEC_ZNANIH:
        znane = dict(sorted(znane.items(), key=lambda x: -x[1]["cas"])[:NAJVEC_ZNANIH])
        spremenjeno = True
    if spremenjeno:
        nastavitve.podatki[KLJUC_ZNANE] = znane
        nastavitve.shrani()
    return spremenjeno


def ime_znane(nastavitve, naprava: str) -> str:
    return (_znane(nastavitve).get(str(naprava or "")) or {}).get("ime", "")


def za_meni(zdaj_v_linku: List[dict], nastavitve, je_clan: Callable[[str], bool]) -> List[dict]:
    """Naprave za »Poslji na …« (Nemo): tiste, ki so zdaj v Linku (`dosegljiva` True), in znane, ki jih zdaj ni
    (`dosegljiva` False) - te samo, ce so se v krogu zaupanja (o tem odloca ta naprava, core/link_dostop).
    Zadnja uporabljena prva; pri enakem casu najprej dosegljive, potem po imenu."""
    izid, videne = [], set()
    for n in zdaj_v_linku or []:
        if isinstance(n, dict) and n.get("id"):
            izid.append(dict(n, dosegljiva=True))
            videne.add(str(n["id"]))
    for i, z in _znane(nastavitve).items():
        if i in videne:
            continue
        try:
            clan = bool(je_clan(i))
        except Exception:  # noqa: BLE001 - ob dvomu naprave ne ponudimo
            clan = False
        if clan:
            izid.append({"id": i, "ime": z["ime"] or i, "dosegljiva": False, "zadnjic": zadnjic(nastavitve, i)})

    def kljuc(n: dict):
        try:
            cas = float(n.get("zadnjic") or 0.0)
        except (TypeError, ValueError):
            cas = 0.0
        return (-cas, 0 if n.get("dosegljiva") else 1, str(n.get("ime") or n.get("id") or "").casefold())
    return sorted(izid, key=kljuc)


def razvrsti(naprave: List[dict], kljuc_casa: str = "zadnjic") -> List[dict]:
    """Naprave za »Poslji na napravo«: zadnja uporabljena prva, potem po imenu (stabilno, brez sumnikov v kljucu)."""
    def kljuc(n: dict):
        try:
            cas = float(n.get(kljuc_casa) or 0.0)
        except (TypeError, ValueError):
            cas = 0.0
        return (-cas, str(n.get("ime") or n.get("id") or "").casefold())
    return sorted([n for n in naprave if isinstance(n, dict)], key=kljuc)


# ---------------------------------------------------------------------- namizno obvestilo (posiljanje iz Nema)
BESEDILA_OBVESTIL = {
    "sl": {"posiljam": "Pošiljam napravi {naprava}", "caka": "Čakam na napravo {naprava}",
           "poslano": "Poslano napravi {naprava}", "datotek": "Datotek: {n}",
           "caka_telo": "{kaj} – pošiljanje se nadaljuje samo, ko bo naprava spet v Safeer Linku.", "preklici": "Prekliči"},
    "en": {"posiljam": "Sending to {naprava}", "caka": "Waiting for {naprava}",
           "poslano": "Sent to {naprava}", "datotek": "Files: {n}",
           "caka_telo": "{kaj} – sending resumes by itself when the device is back in Safeer Link.", "preklici": "Cancel"},
    "de": {"posiljam": "Sende an {naprava}", "caka": "Warte auf {naprava}",
           "poslano": "An {naprava} gesendet", "datotek": "Dateien: {n}",
           "caka_telo": "{kaj} – das Senden geht von selbst weiter, sobald das Gerät wieder in Safeer Link ist.",
           "preklici": "Abbrechen"},
    "es": {"posiljam": "Enviando a {naprava}", "caka": "Esperando a {naprava}",
           "poslano": "Enviado a {naprava}", "datotek": "Archivos: {n}",
           "caka_telo": "{kaj} – el envío continúa solo cuando el dispositivo vuelva a Safeer Link.", "preklici": "Cancelar"},
    "fr": {"posiljam": "Envoi vers {naprava}", "caka": "En attente de {naprava}",
           "poslano": "Envoyé à {naprava}", "datotek": "Fichiers : {n}",
           "caka_telo": "{kaj} – l'envoi reprend tout seul quand l'appareil revient dans Safeer Link.", "preklici": "Annuler"},
    "it": {"posiljam": "Invio a {naprava}", "caka": "In attesa di {naprava}",
           "poslano": "Inviato a {naprava}", "datotek": "File: {n}",
           "caka_telo": "{kaj} – l'invio riprende da solo quando il dispositivo torna in Safeer Link.", "preklici": "Annulla"},
}


def besedilo_obvestila(jezik: str, kljuc: str, **polja) -> str:
    slovar = BESEDILA_OBVESTIL.get(str(jezik or "")[:2].lower()) or BESEDILA_OBVESTIL["en"]
    return (slovar.get(kljuc) or BESEDILA_OBVESTIL["en"][kljuc]).format(**polja)


def obvestilo(jezik: str, s: dict) -> Tuple[str, str]:
    """(naslov, besedilo) obvestila za stanje posiljke (slovar Posiljka.slovar)."""
    naprava = str(s.get("naprava") or s.get("idNaprave") or "")
    datotek = int(s.get("datotek") or 0)
    kaj = besedilo_obvestila(jezik, "datotek", n=datotek) if datotek > 1 else str(s.get("ime") or "")
    stanje = str(s.get("stanje") or "posiljam")
    if stanje == "caka":
        return besedilo_obvestila(jezik, "caka", naprava=naprava), besedilo_obvestila(jezik, "caka_telo", kaj=kaj)
    return besedilo_obvestila(jezik, "poslano" if stanje == "poslano" else "posiljam", naprava=naprava), kaj
