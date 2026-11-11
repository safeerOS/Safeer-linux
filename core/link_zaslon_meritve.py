"""Meritve ene seje deljenja zaslona (core/link_zaslon.py): koliko posiljamo, koliko casa pisemo, zamik do gledalca.

Cist modul: brez vticnic in niti, ura je vstavljena (preizkusi tecejo brez cakanja), vse pod eno kljucavnico. Klicejo
ga crpalki slike in zvoka (poslano), nit meritev (tcp, posnetek), nit utripa (ping_poslan) in nit vnosa (pong).

Nobena meritev ne potrebuje uskladjenih ur: cas meri stran, ki racuna, s svojo monotono uro; gledalec samo vrne
vrednosti, ki jih ne razume (`n`, `t`). V 1. fazi samo merimo - slika, poti in roki ostanejo kot doslej.

Brez gledalca (deluje z vsakim, tudi s starejsim televizorjem in z Windows):
  poslano_mbps, zvok_mbps   bajti, predani sendall v zadnji sekundi (slika, zvok)
  zasedenost                delez casa, ko crpalka slike caka v sendall (zadnja sekunda; sendall, ki se traja, steje
                            sproti - zacni_pisanje)
  najdaljse_pisanje_ms      najdaljsi posamezni sendall v zadnji sekundi (tudi tisti, ki se traja)
  neposlano_b, tcp_rtt_ms, delez_retrans
                            iz TCP_INFO (link_vticnik.tcp_info). Pomenijo kaj samo na neposredni povezavi: prek Huba
                            je vticnica zanka do AgentHuba (pot 'hub'), tam steje le neposlano_b.
Z gledalcem, ki zna 'rtt' (caps v screen.start, nato "rtt": true v glavi):
  rtt_ms                    od ping_poslan (PRED sendall: ping, ki obtici za vrsto, ze caka) do branja odmeva v
                            _beri_vnos - natanko zamik, ki ga vidi slika (vrste, rele, omrezje, gledalec, pot nazaj)
  rtt_med3_ms               mediana zadnjih treh (en skok Wi-Fi ne steje)
  rtt_osnova_ms             najmanjsi v zadnjih 300 s (kratko okno bi stalno vrsto vzelo za osnovo)
  cakanje_ms                med3 - osnova: kolikor cakamo v vrstah
  cakanje_eff_ms            max(cakanje, odprt_ping - osnova): ujame tudi popoln zastoj, ko odmevov ni
  odprt_ping_ms             starost najstarejsega neodgovorjenega pinga
  pozni                     pingi brez odmeva po 5 s (TCP izgube skrije; to je nas priblizek)
  dostava_mbps              d(b)/d(r) med zaporednima odmevoma: bajti in ura GLEDALCA (pot nazaj ne vpliva)
  oddaja_mbps               nasa hitrost med istima pingoma
  kapaciteta_mbps           najvecja dostava med zagozdenostjo v zadnjih 60 s
  gledalec                  fps, mbps, dek, zastoji, izpusceno iz odmeva; prvi odmev nosi se pot in rok
Zastoji gledalca (novejsi gledalec; starejsi teh polj ne poslje in so v povzetku None): zastoj je presledek > 50 ms
med zaporednima slikama na izhodu dekoderja (Android-tv ZaslonUtrip.ZASTOJ_MS); vsak odmev nosi zadnjo zaprto sekundo.
  zastoj_ms                 skupno trajanje zastojev v tej sekundi (cel presledek, ms)
  zastoji_100, zastoji_250  zastoji, daljsi od 100 ms oz. 250 ms
  zastoji_kljucna           zastoji, ki jih je koncala kljucna slika (velika slika prek releja, daljse dekodiranje)
"""

from __future__ import annotations

import collections
import math
import statistics
import threading
import time
from typing import Callable, Optional

from core import link_vticnik

#: Vrsti okvirjev, kot ju posiljata crpalki (link_zaslon.OKVIR_SLIKA, OKVIR_ZVOK).
SLIKA, ZVOK = 1, 2
#: Okno za hitrost, zasedenost in najdaljse pisanje.
OKNO_S = 1.0
#: Okno najmanjsega zamika (osnova). Vsaj 120 s: krajse bi stalno vrsto vzelo za osnovo.
OSNOVA_S = 300.0
#: Ping brez odmeva po tem casu je pozen.
POZNO_S = 5.0
#: Okno kapacitete in meja zagozdenosti (cakanje nad max(meja, osnova)).
KAPACITETA_S = 60.0
ZAGOZDENO_MS = 100.0
#: Najvec odprtih pingov (dve minuti utripa) in shranjenih vzorcev za povzetek seje.
NAJVEC_ODPRTIH = 256
NAJVEC_VZORCEV = 20000
#: Najvec sekund, za katere hranimo hitrost in zasedenost (dan).
NAJVEC_SEKUND = 24 * 3600


#: Smiselni razponi vrednosti gledalca (na sekundo oz. v ms); vrednost zunaj razpona pade, kot da je ni.
RAZPONI_GLEDALCA = {"fps": (0.0, 1000.0), "mbps": (0.0, 100_000.0), "dek": (0.0, 60_000.0),
                    "zastoji": (0.0, 10_000.0), "izpusceno": (0.0, 10_000.0), "rok": (0.0, 600_000.0),
                    "zastoj_ms": (0.0, 600_000.0), "zastoji_100": (0.0, 10_000.0), "zastoji_250": (0.0, 10_000.0),
                    "zastoji_kljucna": (0.0, 10_000.0)}
#: Polja zastojev iz odmeva (novejsi gledalec) -> ime v povzetku seje (na minuto, kot zastoji_na_min).
ZASTOJI_GLEDALCA = {"zastoj_ms": "zastoj_ms_na_min", "zastoji_100": "zastoji_100_na_min",
                    "zastoji_250": "zastoji_250_na_min", "zastoji_kljucna": "zastoji_kljucna_na_min"}


def _stevilo(v, najmanj: Optional[float] = None, najvec: Optional[float] = None) -> Optional[float]:
    """Koncno stevilo (v razponu najmanj..najvec, ce je podan) ali None (vrednosti gledalca so tuje: karkoli drugega,
    tudi ogromno celo stevilo iz JSON, pade)."""
    if isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(x):
        return None
    if (najmanj is not None and x < najmanj) or (najvec is not None and x > najvec):
        return None
    return x


def _hitrost_mbps(bajtov: float, ms: float) -> Optional[float]:
    """Mb/s iz bajtov v `ms` milisekundah; None, ce rezultat ni koncno stevilo v razponu gledalcevih mbps (tuje
    vrednosti gledalca: deljenje s skoraj nic ne sme dati neskoncne ali nesmiselne hitrosti)."""
    try:
        x = bajtov * 8.0 / (ms / 1000.0) / 1e6
    except (ZeroDivisionError, OverflowError):
        return None
    return x if math.isfinite(x) and 0.0 <= x <= RAZPONI_GLEDALCA["mbps"][1] else None


def _percentil(vrednosti, p: float) -> Optional[float]:
    """p-ti percentil (najblizji rang) ali None brez vrednosti."""
    s = sorted(vrednosti)
    if not s:
        return None
    k = int(math.ceil(p / 100.0 * len(s))) - 1
    return s[max(0, min(len(s) - 1, k))]


def _z(v, mest: int = 1):
    return None if v is None else round(v, mest)


class Meritve:
    """Meritve ene seje. Vse metode so varne za hkratne klice iz vec niti."""

    def __init__(self, ura: Callable[[], float] = time.monotonic, pot: str = "neposredno", kodek: str = "",
                 kakovost: str = "", kodirnik: str = "") -> None:
        self._ura = ura
        self._zaklep = threading.Lock()
        #: Opis seje za povzetek: pot ('neposredno' ali 'hub'), kodirnik ('vaapi', 'x264'), kodek, kakovost.
        self.opis = {"pot": pot, "kodirnik": kodirnik, "kodek": kodek, "kakovost": kakovost}
        self._zacetek = ura()
        #: Pisanja zadnje sekunde: (konec, vrsta, bajtov, cakal_s).
        self._pisanja: collections.deque = collections.deque()
        #: Pisanje, ki se traja (zacni_pisanje, se brez poslano): vrsta -> cas zacetka. Zastoj je viden, ko traja.
        self._pise: dict = {}
        #: Vsi bajti, predani sendall (za oddajo med pingoma), in bajti slike v celi seji.
        self._skupaj = 0
        self._slika_skupaj = 0
        #: Po sekundah seje: bajti slike in zvoka ter cas v sendall slike - za povzetek.
        self._sek_bajtov: list = []
        self._sek_zasedeno: list = []
        self._tcp: Optional[dict] = None
        self._tcp_prvi: Optional[dict] = None
        self._delez_retrans: Optional[float] = None
        #: Odprti pingi: n -> [t_tx_ms, bajtov poslanih do takrat, ze steto kot pozen].
        self._odprti: "collections.OrderedDict[int, list]" = collections.OrderedDict()
        self._pingov = 0
        self._pozni = 0
        self._rtt: Optional[float] = None
        self._zadnji3: collections.deque = collections.deque(maxlen=3)
        #: (t_s, rtt_ms) zadnjih OSNOVA_S.
        self._osnova: collections.deque = collections.deque()
        self._rtt_vzorci: collections.deque = collections.deque(maxlen=NAJVEC_VZORCEV)
        self._cakanje_vzorci: collections.deque = collections.deque(maxlen=NAJVEC_VZORCEV)
        self._zastoji: collections.deque = collections.deque(maxlen=NAJVEC_VZORCEV)
        #: Polje odmeva (ZASTOJI_GLEDALCA) -> vzorci na odmev; prazno pri starejsem gledalcu.
        self._zastoji_vec = {k: collections.deque(maxlen=NAJVEC_VZORCEV) for k in ZASTOJI_GLEDALCA}
        self._odmevov = 0
        #: Prejsnji odmev z r in b: (r, b, t_tx_ms, nasih bajtov ob pingu).
        self._prejsnji: Optional[tuple] = None
        self._dostava: Optional[float] = None
        self._oddaja: Optional[float] = None
        #: (t_s, dostava_mbps) med zagozdenostjo, zadnjih KAPACITETA_S.
        self._kapaciteta: collections.deque = collections.deque()
        self._gledalec: dict = {}

    # ------------------------------------------------------------------ posiljanje (crpalki)

    def zacni_pisanje(self, vrsta: int) -> None:
        """Crpalka zacenja sendall (klice se PRED njim): dokler ne pride poslano(), je pisanje v teku - posnetek() ga
        steje v zasedenost in najdaljse pisanje sproti, tudi ce obvisi za vec sekund."""
        zdaj = self._ura()
        with self._zaklep:
            if vrsta in (SLIKA, ZVOK):
                self._pise[vrsta] = zdaj

    def poslano(self, vrsta: int, bajtov: int, cakal_s: float) -> None:
        """Crpalka je predala `bajtov` (cel okvir) sendall, ki je trajal `cakal_s`. Klice se po sendall.

        Cas pisanja slike se razdeli po vseh sekundah, ki jih je pokrilo (od zdaj - cakal_s do zdaj): 4 s zastoja so
        stiri zasedene sekunde, ne ena (povzetek jo omeji na 1,0) - sicer bi zasedenost_p90 zastoje skrila."""
        zdaj = self._ura()
        cakal_s = max(0.0, float(cakal_s))
        with self._zaklep:
            self._pise.pop(vrsta, None)
            self._skupaj += int(bajtov)
            if vrsta not in (SLIKA, ZVOK):
                return
            if vrsta == SLIKA:
                self._slika_skupaj += int(bajtov)
            self._pisanja.append((zdaj, vrsta, int(bajtov), cakal_s))
            self._pocisti_pisanja(zdaj)
            i = int(max(0.0, zdaj - self._zacetek))
            if i < NAJVEC_SEKUND:
                if len(self._sek_bajtov) <= i:
                    self._sek_bajtov.extend([0] * (i + 1 - len(self._sek_bajtov)))
                self._sek_bajtov[i] += int(bajtov)
            if vrsta == SLIKA:
                self._razdeli(self._sek_zasedeno, zdaj - cakal_s, zdaj)

    def _razdeli(self, sekunde: list, od: float, do: float) -> None:
        """Interval pisanja [od, do] (nasa ura) razdeli po sekundah seje v `sekunde`. Klice se pod kljucavnico."""
        od = max(od, self._zacetek)
        if do <= od:
            return
        prva = int(od - self._zacetek)
        zadnja = min(int(do - self._zacetek), NAJVEC_SEKUND - 1)
        if len(sekunde) <= zadnja:
            sekunde.extend([0.0] * (zadnja + 1 - len(sekunde)))
        for i in range(prva, zadnja + 1):
            zacetek = self._zacetek + i
            delez = min(do, zacetek + 1.0) - max(od, zacetek)
            if delez > 0:
                sekunde[i] += delez

    def _pocisti_pisanja(self, zdaj: float) -> None:
        while self._pisanja and self._pisanja[0][0] < zdaj - OKNO_S:
            self._pisanja.popleft()

    # ------------------------------------------------------------------ TCP (nit meritev)

    def tcp(self, podatki: Optional[dict]) -> None:
        """Meritev TCP_INFO vticnice seje (link_vticnik.tcp_info), enkrat na sekundo. None se ne steje."""
        if not podatki:
            return
        with self._zaklep:
            d = link_vticnik.delez_retrans(self._tcp, podatki)
            if d is not None:
                self._delez_retrans = d
            self._tcp = dict(podatki)
            if self._tcp_prvi is None:
                self._tcp_prvi = dict(podatki)

    # ------------------------------------------------------------------ zamik (utrip in odmev)

    def ping_poslan(self, n: int, t_ms: float) -> None:
        """Ping `n` s casom `t_ms` (nasa monotona ura v ms) gre ven. Klice se PRED sendall."""
        with self._zaklep:
            self._odprti[int(n)] = [float(t_ms), self._skupaj, False]
            self._pingov += 1
            while len(self._odprti) > NAJVEC_ODPRTIH:
                _n, odprt = self._odprti.popitem(last=False)
                if not odprt[2]:
                    self._pozni += 1

    def pong(self, dogodek: dict, t: float) -> Optional[float]:
        """Odmev gledalca ({"vrsta":"rtt","n","t","r","b",...}), prebran ob `t` (nasa monotona ura v s).

        Vrne izmerjeni zamik v ms; neznan ali podvojen `n` (ali `t`, ki ni nas) ne spremeni nicesar in vrne None."""
        if not isinstance(dogodek, dict):
            return None
        n = _stevilo(dogodek.get("n"))
        if n is None or n != int(n):
            return None
        n = int(n)
        t_ms = float(t) * 1000.0
        with self._zaklep:
            odprt = self._odprti.get(n)
            if odprt is None:
                return None
            vrnjen = _stevilo(dogodek.get("t"))
            if dogodek.get("t") is not None and (vrnjen is None or abs(vrnjen - odprt[0]) > 1.0):
                return None
            # Tok je urejen (TCP, en izvrsevalec na gledalcu): na starejse pinge brez odmeva odmeva ne bo vec.
            for m in [m for m in self._odprti if m < n]:
                if not self._odprti.pop(m)[2]:
                    self._pozni += 1
            del self._odprti[n]
            rtt = max(0.0, t_ms - odprt[0])
            if rtt >= POZNO_S * 1000.0 and not odprt[2]:
                self._pozni += 1
            self._rtt = rtt
            self._odmevov += 1
            self._zadnji3.append(rtt)
            self._osnova.append((float(t), rtt))
            self._pocisti_osnovo(float(t))
            self._rtt_vzorci.append(rtt)
            osnova = min(r for _, r in self._osnova)
            cakanje = max(0.0, statistics.median(self._zadnji3) - osnova)
            self._cakanje_vzorci.append(cakanje)
            r, b = _stevilo(dogodek.get("r"), 0.0), _stevilo(dogodek.get("b"), 0.0)
            if r is not None and b is not None:
                prej = self._prejsnji
                if prej is not None:
                    dr, db = r - prej[0], b - prej[1]
                    dt, ds = odprt[0] - prej[2], odprt[1] - prej[3]
                    if dr > 0 and db >= 0:
                        dostava = _hitrost_mbps(db, dr)
                        if dostava is not None:
                            self._dostava = dostava
                            if cakanje > max(ZAGOZDENO_MS, osnova):
                                self._kapaciteta.append((float(t), dostava))
                    if dt > 0 and ds >= 0:
                        oddaja = _hitrost_mbps(ds, dt)
                        if oddaja is not None:
                            self._oddaja = oddaja
                self._prejsnji = (r, b, odprt[0], odprt[1])
            for kljuc in ("fps", "mbps", "dek", "zastoji", "izpusceno"):
                v = _stevilo(dogodek.get(kljuc), *RAZPONI_GLEDALCA[kljuc])
                if v is not None:
                    self._gledalec[kljuc] = v
                    if kljuc == "zastoji":
                        self._zastoji.append(v)
            for kljuc, vzorci in self._zastoji_vec.items():
                v = _stevilo(dogodek.get(kljuc), *RAZPONI_GLEDALCA[kljuc])
                if v is not None:
                    vzorci.append(v)
            pot = dogodek.get("pot")
            if isinstance(pot, str) and pot:
                self._gledalec["pot"] = pot[:16]
            rok = _stevilo(dogodek.get("rok"), *RAZPONI_GLEDALCA["rok"])
            if rok is not None:
                self._gledalec["rok_ms"] = rok
            return rtt

    def bajtov_slike(self) -> int:
        """Koliko bajtov slike je seja poslala (0: slika ni nikoli stekla)."""
        with self._zaklep:
            return self._slika_skupaj

    def zadnji_rtt(self) -> int:
        """Zadnji zamik v ms za prikaz na gledalcu (`z`); 0, dokler ga ni."""
        with self._zaklep:
            return int(round(self._rtt)) if self._rtt is not None else 0

    def _pocisti_osnovo(self, t: float) -> None:
        while self._osnova and self._osnova[0][0] < t - OSNOVA_S:
            self._osnova.popleft()

    def _preveri_pozne(self, zdaj_ms: float) -> None:
        for odprt in self._odprti.values():
            if not odprt[2] and zdaj_ms - odprt[0] >= POZNO_S * 1000.0:
                odprt[2] = True
                self._pozni += 1

    # ------------------------------------------------------------------ izpis

    def posnetek(self) -> dict:
        """Trenutne vrednosti (stanje()['meritve'], screen.status, dnevnik). Kar se ne da izmeriti, je None."""
        zdaj = self._ura()
        with self._zaklep:
            self._pocisti_pisanja(zdaj)
            self._pocisti_osnovo(zdaj)
            self._preveri_pozne(zdaj * 1000.0)
            okno = max(1e-3, min(OKNO_S, zdaj - self._zacetek))
            od = zdaj - okno
            slika = zvok = 0
            zasedeno = najdaljse = 0.0
            for konec, vrsta, bajtov, cakal in self._pisanja:
                if konec < od:
                    continue
                najdaljse = max(najdaljse, cakal)
                if vrsta == SLIKA:
                    slika += bajtov
                    zasedeno += max(0.0, min(konec, zdaj) - max(konec - cakal, od))
                else:
                    zvok += bajtov
            # Pisanje, ki se traja: zastoj je viden, medtem ko traja (ne sele, ko se sendall vrne).
            for vrsta, zacel in self._pise.items():
                najdaljse = max(najdaljse, zdaj - zacel)
                if vrsta == SLIKA:
                    zasedeno += max(0.0, zdaj - max(zacel, od))
            osnova = min((r for _, r in self._osnova), default=None)
            med3 = statistics.median(self._zadnji3) if self._zadnji3 else None
            odprt = (zdaj * 1000.0 - min(o[0] for o in self._odprti.values())) if self._odprti else 0.0
            odprt = max(0.0, odprt)
            cakanje = cakanje_eff = None
            if osnova is not None and med3 is not None:
                cakanje = max(0.0, med3 - osnova)
                cakanje_eff = max(cakanje, odprt - osnova)
            kapaciteta = max((d for t, d in self._kapaciteta if t >= zdaj - KAPACITETA_S), default=None)
            while self._kapaciteta and self._kapaciteta[0][0] < zdaj - KAPACITETA_S:
                self._kapaciteta.popleft()
            tcp = self._tcp or {}
            rtt_us = tcp.get("rtt_us")
            return {
                "pot": self.opis.get("pot"),
                "poslano_mbps": round(slika * 8.0 / okno / 1e6, 3),
                "zvok_mbps": round(zvok * 8.0 / okno / 1e6, 3),
                "zasedenost": round(max(0.0, min(1.0, zasedeno / okno)), 3),
                "najdaljse_pisanje_ms": round(najdaljse * 1000.0, 1),
                "neposlano_b": tcp.get("neposlano"),
                "tcp_rtt_ms": None if rtt_us is None else round(rtt_us / 1000.0, 2),
                "delez_retrans": _z(self._delez_retrans, 4),
                "rtt_ms": _z(self._rtt), "rtt_med3_ms": _z(med3), "rtt_osnova_ms": _z(osnova),
                "cakanje_ms": _z(cakanje), "cakanje_eff_ms": _z(cakanje_eff),
                "odprt_ping_ms": round(odprt, 1), "pozni": self._pozni,
                "dostava_mbps": _z(self._dostava, 3), "oddaja_mbps": _z(self._oddaja, 3),
                "kapaciteta_mbps": _z(kapaciteta, 3),
                "pingov": self._pingov, "odmevov": self._odmevov,
                "gledalec": dict(self._gledalec),
            }

    def povzetek(self) -> dict:
        """Ena vrstica za sejo (zaslon-seje.jsonl): opis, trajanje in porazdelitve (p50/p90/p95) cez celo sejo."""
        zdaj = self._ura()
        with self._zaklep:
            self._preveri_pozne(zdaj * 1000.0)
            trajanje = max(0.0, zdaj - self._zacetek)
            # Samo cele sekunde (zadnja je nepopolna); sekunda brez pisanja je 0 Mb/s.
            celih = min(int(trajanje), NAJVEC_SEKUND)
            sek_bajtov = (self._sek_bajtov + [0] * max(0, celih - len(self._sek_bajtov)))[:celih]
            sek_zasedeno = list(self._sek_zasedeno)
            if SLIKA in self._pise:
                # Seja se konca sredi pisanja slike (zastoj do konca): tudi ta cas je zaseden.
                self._razdeli(sek_zasedeno, self._pise[SLIKA], zdaj)
            sek_zasedeno = (sek_zasedeno + [0.0] * max(0, celih - len(sek_zasedeno)))[:celih]
            mbps = [b * 8.0 / 1e6 for b in sek_bajtov]
            zasedenost = [min(1.0, z) for z in sek_zasedeno]
            rtt = list(self._rtt_vzorci)
            delez = link_vticnik.delez_retrans(self._tcp_prvi, self._tcp)
            return dict(self.opis, **{
                "trajanje_s": round(trajanje, 1), "slika_mb": round(self._slika_skupaj / 1e6, 3),
                "mbps_p50": _z(_percentil(mbps, 50), 3), "mbps_p95": _z(_percentil(mbps, 95), 3),
                "rtt_min_ms": _z(min(rtt) if rtt else None), "rtt_p50_ms": _z(_percentil(rtt, 50)),
                "rtt_p90_ms": _z(_percentil(rtt, 90)),
                "cakanje_p90_ms": _z(_percentil(self._cakanje_vzorci, 90)),
                "zasedenost_p90": _z(_percentil(zasedenost, 90), 3),
                "zastoji_na_min": _z(60.0 * sum(self._zastoji) / len(self._zastoji)) if self._zastoji else None,
                **{ime: _z(60.0 * sum(self._zastoji_vec[k]) / len(self._zastoji_vec[k])) if self._zastoji_vec[k]
                   else None for k, ime in ZASTOJI_GLEDALCA.items()},
                "pozni": self._pozni, "pingov": self._pingov, "odmevov": self._odmevov,
                "delez_retrans": _z(delez, 4),
            })


def opis_posnetka(p: dict) -> str:
    """Kratka vrstica za dnevnik iz posnetek()."""
    deli = ["pot %s" % p.get("pot"), "slika %.2f Mb/s" % (p.get("poslano_mbps") or 0.0),
            "zvok %.2f Mb/s" % (p.get("zvok_mbps") or 0.0), "zasedenost %.2f" % (p.get("zasedenost") or 0.0),
            "najdaljse pisanje %s ms" % p.get("najdaljse_pisanje_ms")]
    if p.get("neposlano_b") is not None:
        deli.append("v jedru %s B" % p.get("neposlano_b"))
    if p.get("tcp_rtt_ms") is not None and p.get("pot") != "hub":
        deli.append("tcp rtt %s ms" % p.get("tcp_rtt_ms"))
    if p.get("pingov"):
        deli.append("rtt %s ms (osnova %s, cakanje %s, odprt %s), pozni %s"
                    % (p.get("rtt_ms"), p.get("rtt_osnova_ms"), p.get("cakanje_eff_ms"), p.get("odprt_ping_ms"),
                       p.get("pozni")))
    if p.get("dostava_mbps") is not None:
        deli.append("dostava %s / oddaja %s Mb/s" % (p.get("dostava_mbps"), p.get("oddaja_mbps")))
    g = p.get("gledalec") or {}
    if g:
        deli.append("gledalec %s slik/s, dekoder %s ms, zastoji %s" % (g.get("fps"), g.get("dek"), g.get("zastoji")))
    return ", ".join(deli)


__all__ = ["Meritve", "opis_posnetka"]
