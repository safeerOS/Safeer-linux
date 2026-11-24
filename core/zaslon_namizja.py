"""Na katerem zaslonu je namizje Safeer OS (cista pravila, brez Qt in Gtk).

Pravilo lastnika (24. 11. 2026 ~20:15): »samo ko je prenos slike preko linka je lahko naprava katera predvaja glavni
zaslon; v vsakem drugacnem primeru se glavni zaslon vrne napravi kateri pripada«. Glavni zaslon (namizje, pult
Cinnamona, dock) pripada racunalniku - pri prenosniku vgrajenemu zaslonu (eDP/LVDS/DSI). Zunanji zaslon (TV, monitor) ni
glavni samo zato, ker je priklopljen ali je bil primarni (prej: TV v mirovanju je imel namizje, prenosnik samo ozadje -
X11 mirovanja TV ne vidi). Pokrov zaprt ali namizni PC (vgrajenega ni): ostane dosedanji primarni. Med prenosom slike
prek Linka se nic ne spremeni. Nastavitev »namizje_zaslon«: samodejno (pravilo, privzeto) ali glavni (Safeer se ne
vmesava).

Pult Cinnamona in dock Plank sledita primarnemu izhodu RandR (izmerjeno 24. 11. v Cinnamon 6.6.9: panels-enabled
»1:0:top« je indeks Xinerama, X da primarni izhod na indeks 0; Plank s praznim kljucem monitor je na primarnem), zato
Straza prestavi primarni izhod na vgrajen zaslon in si zapomni prejsnjega (vrne ga nastavitev »glavni« ali Nazaj v Mint)."""

import re
from typing import Callable, Iterable, List, Optional

NASTAVITVE = ("samodejno", "glavni")
KLJUC = "namizje_zaslon"
KLJUC_PREJ = "namizje_zaslon_prej"
INTERVAL_S = 3

_VGRAJENI = ("eDP", "LVDS", "DSI")
_GLAVA_IZHODA = re.compile(r"^(\S+) (connected|disconnected|unknown connection)(?: primary)?(?: (\d+)x(\d+)\+(-?\d+)\+(-?\d+))?")
_IME_IZHODA = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}")   # ne z »-«: bi bil argument xrandr


def varno_ime(ime) -> bool:
    """Ime izhoda, ki gre kot argument v xrandr (iz izpisa xrandr, a vseeno brez presenecenj)."""
    return isinstance(ime, str) and _IME_IZHODA.fullmatch(ime) is not None


def nastavitev(vrednost) -> str:
    # »prenosnik« iz prve razlicice (pred pravilom lastnika) je zdaj samodejno.
    return "glavni" if vrednost == "glavni" else "samodejno"


def je_vgrajen(ime: str) -> bool:
    return bool(ime) and ime.startswith(_VGRAJENI)


def razcleni_xrandr(besedilo: str) -> List[dict]:
    """Izhodi iz `xrandr --current`: ime, primarni, aktiven (ima sliko)."""
    izhodi = []
    for vrstica in besedilo.splitlines():
        m = _GLAVA_IZHODA.match(vrstica)
        if m:
            izhodi.append({"ime": m.group(1), "primarni": " primary" in vrstica.split("(")[0],
                           "aktiven": m.group(2) == "connected" and m.group(3) is not None})
    return izhodi


def _aktivni(izhodi: Iterable[dict]) -> List[dict]:
    return [i for i in izhodi if i.get("aktiven")]


def vgrajen_izhod(izhodi: Iterable[dict]) -> str:
    return next((i["ime"] for i in _aktivni(izhodi) if je_vgrajen(i["ime"])), "")


def glavni_izhod(izhodi: Iterable[dict]) -> str:
    aktivni = _aktivni(izhodi)
    return next((i["ime"] for i in aktivni if i.get("primarni")), aktivni[0]["ime"] if aktivni else "")


def izberi(izhodi: List[dict], nast: str) -> str:
    """Ime izhoda za namizje: vgrajen, ce je prizgan (samodejno); sicer dosedanji primarni."""
    vgrajen = vgrajen_izhod(izhodi)
    return vgrajen if nastavitev(nast) == "samodejno" and vgrajen else glavni_izhod(izhodi)


class Straza:
    """En cikel na INTERVAL_S v glavnem procesu Safeer OS (klicatelj poskrbi za nit in casovnik).

    beri_izhode() -> razcleni_xrandr(...); seja_linka() -> True med prenosom slike prek Linka; nastavi_primarni(ime)
    -> bool; ob_izbiri(ime) - kje je namizje; shramba: nastavitve Safeer OS (namizje_zaslon, namizje_zaslon_prej -
    primarni izhod pred nami prezivi ponovni zagon Safeer OS)."""

    def __init__(self, beri_izhode: Callable[[], List[dict]], seja_linka: Callable[[], bool],
                 nastavi_primarni: Callable[[str], bool], ob_izbiri: Callable[[str], None], shramba) -> None:
        self.beri_izhode = beri_izhode
        self.seja_linka = seja_linka
        self.nastavi_primarni = nastavi_primarni
        self.ob_izbiri = ob_izbiri
        self.shramba = shramba
        self._zadnja: Optional[str] = None
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
        if not _aktivni(izhodi) or self.seja_linka():
            return ""                    # med prenosom slike prek Linka primarnega izhoda ne spreminjamo
        nast = nastavitev(self.shramba.get(KLJUC))
        x_primarni = next((i["ime"] for i in izhodi if i.get("primarni")), "")   # tudi ugasnjen (zaprt pokrov)
        prej = self._prej()
        if prej and not any(i["ime"] == prej["glavni"] for i in _aktivni(izhodi)):
            self._pozabi()               # zunanji zaslon odklopljen: nimamo kam vrniti
            prej = None
        ime = izberi(izhodi, nast)
        if nast == "glavni":
            if prej and x_primarni == prej["vgrajen"] and self._poskusi(prej["glavni"]):
                ime = prej["glavni"]
            if prej and (x_primarni != prej["vgrajen"] or ime == prej["glavni"]):
                self._pozabi()
        elif ime != x_primarni and je_vgrajen(ime) and self._poskusi(ime) and not prej:
            self.shramba.set(KLJUC_PREJ, {"glavni": x_primarni or glavni_izhod(izhodi), "vgrajen": ime})
        if ime != self._zadnja:
            self._zadnja = ime
            self.ob_izbiri(ime)
        return ime
