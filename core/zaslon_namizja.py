"""Na katerem zaslonu je namizje Safeer OS (cista pravila, brez Qt in Gtk).

Lastnik, 24. 11. 2026: prenosnik + TV na HDMI (primarni). TV v mirovanju X11 ne vidi (izmerjeno: HDMI »connected«,
DPMS On, /dev/cec* ni), zato je bilo namizje (pult, dock, okna) na ugasnjenem TV in prenosnik je kazal samo ozadje.
Lokalnega znaka ni, zato stanje pove TV sam v Safeer Linku (host.info -> zaslon.prizgan); izhod s TV povezemo po
znamki iz EDID (PNP »PHL« = Philips, ime monitorja »Philips FTV«; TV v Linku: znamka »Philips«).

Nastavitev »namizje_zaslon«: samodejno (privzeto), prenosnik (vedno vgrajeni zaslon), glavni (vedno primarni izhod).
Samodejno: primarni zunanji izhod, ki je zanesljivo nas TV in pravi prizgan=False, ob vgrajenem zaslonu -> vgrajeni;
TV spet prizgan -> nazaj; neznano -> primarni (kot doslej); pokrov zaprt (vgrajenega ni) -> primarni.

Pult Cinnamona in dock Plank sledita primarnemu izhodu RandR (izmerjeno 24. 11. v Cinnamon 6.6.9: panels-enabled
»1:0:top« je indeks Xinerama, X da primarni izhod na indeks 0; Plank s praznim kljucem monitor je na primarnem), zato
Straza v nacinu samodejno prestavi primarni izhod in prejsnjega vrne, ko se TV prizge."""

import re
from typing import Callable, Dict, Iterable, List, Optional

NASTAVITVE = ("samodejno", "prenosnik", "glavni")
KLJUC = "namizje_zaslon"
KLJUC_PREJ = "namizje_zaslon_prej"
INTERVAL_S = 3          # cilj lastnika: ugasnem TV -> v <= 5 s namizje na prenosniku

# Oznake proizvajalca PNP (EDID bajta 8-9) za znamke TV z Android TV / Google TV. Ime monitorja je rezerva.
PNP_ZNAMKE = {
    "PHL": "philips", "SAM": "samsung", "SEC": "samsung", "GSM": "lg", "SNY": "sony", "SHP": "sharp",
    "TCL": "tcl", "HEC": "hisense", "HSI": "hisense", "TSB": "toshiba", "MEI": "panasonic", "PAN": "panasonic",
    "XMI": "xiaomi", "VIZ": "vizio", "GRU": "grundig", "HAI": "haier", "SKW": "skyworth",
}
ZNAMKE = sorted(set(PNP_ZNAMKE.values()))

_VGRAJENI = ("eDP", "LVDS", "DSI")
_GLAVA_IZHODA = re.compile(r"^(\S+) (connected|disconnected|unknown connection)(?: primary)?(?: (\d+)x(\d+)\+(-?\d+)\+(-?\d+))?")
_HEX = re.compile(r"^[0-9a-fA-F]{32}$")
_MM = re.compile(r"(\d+)mm x (\d+)mm\s*$")
TV_SIRINA_MM = 900      # ~41" in vec: TV, ne namizni monitor (HDMI-1 lastnika: 1440 mm; monitorji 24-32": 530-710 mm)


_IME_IZHODA = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}")   # ne z »-«: bi bil argument xrandr


def varno_ime(ime) -> bool:
    """Ime izhoda, ki gre kot argument v xrandr (iz izpisa xrandr, a vseeno brez presenecenj)."""
    return isinstance(ime, str) and _IME_IZHODA.fullmatch(ime) is not None


def nastavitev(vrednost) -> str:
    return vrednost if vrednost in NASTAVITVE else NASTAVITVE[0]


def je_vgrajen(ime: str) -> bool:
    return bool(ime) and ime.startswith(_VGRAJENI)


def edid_podatki(edid: bytes) -> Dict[str, str]:
    """PNP proizvajalca in ime monitorja (opisnik 0xFC) iz EDID; pokvarjen EDID -> prazno."""
    if len(edid) < 128 or edid[:8] != b"\x00\xff\xff\xff\xff\xff\xff\x00":
        return {"pnp": "", "model": ""}
    v = (edid[8] << 8) | edid[9]
    pnp = "".join(chr(64 + ((v >> s) & 0x1F)) for s in (10, 5, 0))
    if not pnp.isalpha() or not pnp.isupper():
        pnp = ""
    model = ""
    for z in (54, 72, 90, 108):
        if edid[z:z + 3] == b"\x00\x00\x00" and edid[z + 3] == 0xFC:
            model = edid[z + 5:z + 18].split(b"\n")[0].decode("ascii", "replace").strip()
            break
    return {"pnp": pnp, "model": model}


def razcleni_xrandr(besedilo: str) -> List[dict]:
    """Izhodi iz `xrandr --current --prop`: ime, primarni, aktiven (ima sliko), pnp, model."""
    izhodi: List[dict] = []
    edid: Optional[bytearray] = None
    for vrstica in besedilo.splitlines():
        m = _GLAVA_IZHODA.match(vrstica)
        if m:
            mm = _MM.search(vrstica)
            izhodi.append({"ime": m.group(1), "primarni": " primary" in vrstica.split("(")[0],
                           "aktiven": m.group(2) == "connected" and m.group(3) is not None, "pnp": "", "model": "",
                           "sirina_mm": int(mm.group(1)) if mm else 0})
            edid = None
            continue
        s = vrstica.strip()
        if not izhodi:
            continue
        if s == "EDID:":
            edid = bytearray()
            continue
        if edid is not None:
            if _HEX.match(s):
                edid += bytes.fromhex(s)
                continue
            izhodi[-1].update(edid_podatki(bytes(edid)))
            edid = None
    if edid is not None and izhodi:
        izhodi[-1].update(edid_podatki(bytes(edid)))
    return izhodi


def znamka_izhoda(izhod: dict) -> str:
    znamka = PNP_ZNAMKE.get(str(izhod.get("pnp") or "").upper(), "")
    if znamka:
        return znamka
    besede = re.findall(r"[a-z]+", str(izhod.get("model") or "").lower())
    return next((b for b in besede if b in ZNAMKE), "")


def je_tv_izhod(izhod: dict) -> bool:
    """Zunanji izhod je TV (ne monitor iste znamke - Philips, LG, Samsung delajo oboje): »TV« v imenu EDID
    (»Philips FTV«, »LG TV«) ali sirina slike vsaj TV_SIRINA_MM."""
    return "tv" in str(izhod.get("model") or "").lower() or int(izhod.get("sirina_mm") or 0) >= TV_SIRINA_MM


def _aktivni(izhodi: Iterable[dict]) -> List[dict]:
    return [i for i in izhodi if i.get("aktiven")]


def vgrajen_izhod(izhodi: Iterable[dict]) -> str:
    return next((i["ime"] for i in _aktivni(izhodi) if je_vgrajen(i["ime"])), "")


def glavni_izhod(izhodi: Iterable[dict]) -> str:
    aktivni = _aktivni(izhodi)
    return next((i["ime"] for i in aktivni if i.get("primarni")), aktivni[0]["ime"] if aktivni else "")


def _izhod(izhodi: Iterable[dict], ime: str) -> Optional[dict]:
    return next((i for i in _aktivni(izhodi) if i["ime"] == ime), None)


def potrebno_preverjanje(izhodi: List[dict], glavni: str) -> bool:
    """TV sprasujemo samo, ko je glavni izhod zunanji z znano znamko TV in je vgrajeni zaslon prizgan."""
    izhod = _izhod(izhodi, glavni)
    return bool(izhod and not je_vgrajen(glavni) and vgrajen_izhod(izhodi) and znamka_izhoda(izhod)
                and je_tv_izhod(izhod))


def stanje_tv(izhod: Optional[dict], tv_naprave: Iterable[dict]) -> Optional[bool]:
    """prizgan TV na tem izhodu: True/False; None, ce ni natanko enega TV te znamke ali stanja ne pove."""
    znamka = znamka_izhoda(izhod) if izhod else ""
    if not znamka:
        return None
    ujemajoci = [t for t in tv_naprave if str(t.get("znamka") or "").strip().lower() == znamka]
    if len(ujemajoci) != 1:
        return None                    # dva TV iste znamke: ne vemo, kateri je na HDMI
    p = ujemajoci[0].get("prizgan")
    return p if isinstance(p, bool) else None


def izberi(izhodi: List[dict], tv_naprave: Iterable[dict], nast: str, glavni: str = "",
           zadrzi: bool = False) -> str:
    """Ime izhoda za namizje. zadrzi=True: namizje je ze na vgrajenem zaradi ugasnjenega TV - nazaj samo, ko TV pove
    prizgan=True (TV v mirovanju po nekaj minutah izgine iz omrezja; neznano ne sme vrniti namizja na temen TV)."""
    glavni = glavni or glavni_izhod(izhodi)
    vgrajen = vgrajen_izhod(izhodi)
    nast = nastavitev(nast)
    if nast == "glavni" or not vgrajen:
        return glavni
    if nast == "prenosnik":
        return vgrajen
    if glavni == vgrajen or not potrebno_preverjanje(izhodi, glavni):
        return glavni
    stanje = stanje_tv(_izhod(izhodi, glavni), tv_naprave)
    if stanje is False or (zadrzi and stanje is None):
        return vgrajen
    return glavni


class Straza:
    """En cikel na INTERVAL_S v glavnem procesu Safeer OS (klicatelj poskrbi za nit in casovnik).

    beri_izhode() -> razcleni_xrandr(...); beri_tv() -> [{"id", "znamka", "prizgan"}] (samo TV iz Linka);
    nastavi_primarni(ime) -> bool; ob_izbiri(ime, speci) - kje je namizje in kateri izhodi spijo (nova okna ne tja);
    shramba: slovar nastavitev Safeer OS (namizje_zaslon, namizje_zaslon_prej - prejsnji primarni prezivi ponovni zagon)."""

    def __init__(self, beri_izhode: Callable[[], List[dict]], beri_tv: Callable[[], List[dict]],
                 nastavi_primarni: Callable[[str], bool], ob_izbiri: Callable[[str, List[str]], None], shramba) -> None:
        self.beri_izhode = beri_izhode
        self.beri_tv = beri_tv
        self.nastavi_primarni = nastavi_primarni
        self.ob_izbiri = ob_izbiri
        self.shramba = shramba
        self._zadnja: Optional[tuple] = None
        self._premor = 0                 # ciklov brez novega poskusa po neuspelem xrandr --primary

    def _prej(self) -> Optional[dict]:
        p = self.shramba.get(KLJUC_PREJ)
        return p if isinstance(p, dict) and p.get("glavni") and p.get("vgrajen") else None

    def _pozabi(self) -> None:
        self.shramba.set(KLJUC_PREJ, None)

    def ponastavi(self) -> None:
        """Naslednji korak znova sporoci izbiro (klicatelj je namizje medtem vrnil na privzeti zaslon)."""
        self._zadnja = None

    def _poskusi(self, ime: str) -> bool:
        """xrandr --primary; po neuspehu 10 ciklov (30 s) premora, ne vsake 3 s znova."""
        if self._premor > 0:
            self._premor -= 1
            return False
        if self.nastavi_primarni(ime):
            return True
        self._premor = 10
        return False

    def vrni(self) -> None:
        """Uporabnik zapusca Safeer OS (Nazaj v Mint): primarni izhod nazaj, kot je bil pred nami."""
        prej = self._prej()
        if prej and self.nastavi_primarni(prej["glavni"]):
            self._pozabi()

    def korak(self) -> str:
        izhodi = self.beri_izhode()
        if not _aktivni(izhodi):
            return ""
        nast = nastavitev(self.shramba.get(KLJUC))
        trenutni = glavni_izhod(izhodi)
        prej = self._prej()
        if prej and (_izhod(izhodi, prej["glavni"]) is None or trenutni not in (prej["glavni"], prej["vgrajen"])):
            # TV odklopljen ali povsem drug primarni izhod: zacnemo znova. Zaprt pokrov ne (spodaj vrnemo primarni).
            self._pozabi()
            prej = None
        # Primarni spet na TV (uporabnik ali muffin ob ponovni postavitvi), TV pa se spi ali ne odgovarja: zadrzanje
        # ostane in namizje gre znova na prenosnik. Uporabnik, ki hoce TV kljub temu, izbere nastavitev »glavni«.
        glavni = prej["glavni"] if prej else trenutni
        tv = self.beri_tv() if nast == "samodejno" and potrebno_preverjanje(izhodi, glavni) else []
        ime = izberi(izhodi, tv, nast, glavni, zadrzi=bool(prej))
        x_primarni = next((i["ime"] for i in izhodi if i.get("primarni")), "")   # tudi ugasnjen (zaprt pokrov)
        if prej and (nast != "samodejno" or ime == glavni):
            if x_primarni == glavni or self._poskusi(glavni):
                self._pozabi()
                prej = None
        elif nast == "samodejno" and ime != trenutni and ime == vgrajen_izhod(izhodi):
            if self._poskusi(ime):
                self.shramba.set(KLJUC_PREJ, {"glavni": glavni, "vgrajen": ime})
                prej = self._prej()
        if nast == "samodejno" and ime != glavni:
            speci = [glavni]
        else:
            speci = []
        izbira = (ime, tuple(speci))
        if izbira != self._zadnja:
            self._zadnja = izbira
            self.ob_izbiri(ime, speci)
        return ime
