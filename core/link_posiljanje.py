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

Brez GTK in brez omrezja: funkcijo za oddajo dobi od klicatelja, zato je preizkusljiv sam.
"""

from __future__ import annotations

import os
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

    def slovar(self) -> dict:
        odstotek = 100 if self.stanje == "poslano" else (int(self.bajtov * 100 / self.skupaj) if self.skupaj else 0)
        return {"id": self.id, "stanje": self.stanje, "naprava": self.ime_naprave, "datotek": len(self.poti),
                "poslanih": self.poslanih, "ime": self.ime, "odstotek": max(0, min(100, odstotek)), "mape": self.mape,
                "koda": self.koda, "sporocilo": self.sporocilo, "zasedenaOd": self.zasedena_od,
                "idNaprave": self.naprava, "obvesti": self.obvesti}


class Posiljanje:
    def __init__(self, poslji: Callable[[str, str, Callable[[int], None]], Tuple[bool, Dict[str, str]]],
                 ime_naprave: Callable[[str], str] = lambda i: i,
                 dosegljiva: Optional[Callable[[str], bool]] = None,
                 ob_spremembi: Optional[Callable[[dict], None]] = None,
                 zabelezi: Optional[Callable[[str], None]] = None,
                 ura: Callable[[], float] = time.monotonic) -> None:
        """`dosegljiva(id)`: ali je naprava v Linku - z njo posiljka ob prehodni napaki pocaka in nadaljuje (brez nje
        prva napaka konca). `ob_spremembi(stanje)`: vsaka sprememba (zacetek datoteke, odstotek, caka, konec) - iz
        delovne niti. `zabelezi(id)`: naprava, ki ji je uporabnik pravkar poslal (zadnja naprava prva v menijih)."""
        self._poslji = poslji
        self._ime_naprave = ime_naprave
        self._dosegljiva = dosegljiva
        self._ob_spremembi = ob_spremembi
        self._zabelezi = zabelezi
        self._ura = ura
        self._zaklep = threading.Lock()
        self._posiljke: Dict[str, Posiljka] = {}

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
        """Posiljka caka, da bo naprava spet dosegljiva. True = poskusi znova, False = preklicano ali rok je potekel."""
        p.stanje = "caka"
        self._javi(p)
        najmanj = self._ura() + RAZMIKI_S[min(poskus, len(RAZMIKI_S) - 1)]
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

    def _teci(self, p: Posiljka) -> None:
        opravljeno = 0
        rok = self._ura() + CAKA_NAJVEC_S
        self._javi(p)
        i = 0
        poskus = 0
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
