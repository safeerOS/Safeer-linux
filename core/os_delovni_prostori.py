"""Lokalna navidezna namizja (delovni prostori Cinnamona/Muffina) v preklopniku Prostori.

Zamisel lastnika (20. 10. 2026, SAFEER-ZNANJE.md »SAFEER LINK SPACES, razsiritev«): povrsine so lokalna navidezna
namizja te naprave IN zasloni povezanih naprav, v ENEM preklopniku. Lokalna namizja niso lasten sistem, ampak delovni
prostori upravljalnika oken (EWMH na X11: _NET_NUMBER_OF_DESKTOPS, _NET_CURRENT_DESKTOP, _NET_DESKTOP_NAMES), ki jih
Cinnamon ze ima - bliznjice Cinnamona (Ctrl+Alt+levo/desno) zato delujejo naprej in se s Prostori ujemajo.

Orodje je `wmctrl` (paket je v Mintu privzeto, Safeer OS ga ze uporablja za okna). Brez X11 (Wayland) ali brez
wmctrl namizij ni - preklopnik pokaze samo »Ta racunalnik«, kot v MVP.

Slicica namizja je SHEMA: ozadje + pravokotniki oken na tistem namizju (polozaj in velikost iz wmctrl -lG). Pravega
posnetka namizja, ki ni na zaslonu, na X11 brez kompozitorja ni (okna drugih namizij niso narisana), in zajem trenutnega
bi pokazal sam preklopnik. Shema ne potrebuje nobenega dovoljenja in ne stane nic.

Ta modul je brez GTK in omrezja; razclenjevanje izpisa in postavitev so ciste funkcije (tests/test_os_delovni_prostori.py).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import time
from typing import Callable, Dict, List, Optional

#: Toliko namizij najvec (Cinnamon ima bliznjice switch-to-workspace-1 .. 12).
NAJVEC_NAMIZIJ = 12
#: Toliko oken na namizje pokaze shema (vec jih na 196 px sirokih ploscicah ni mogoce razlociti).
NAJVEC_OKEN = 12
#: Manjsa okna (npr. pomozna, 1 px) v shemi ne stejejo.
NAJMANJSE_OKNO = 24
#: Rok enega klica wmctrl (s): klic tece v niti ozadja, a ne sme viseti, ce X ne odgovori.
ROK_S = 3.0
_NAJDALJSE_IME = 60
_NAJDALJSI_NASLOV = 80

# Novo namizje ima nekaj casa delovno povrsino »WA: N/A« (izmerjeno 25. 10. 2026 v Xvfb z Muffinom) - tudi taka vrstica
# je namizje; prej je izraz zahteval stevilke in novo namizje je bilo »nevidno«.
_VRSTICA_NAMIZJA = re.compile(
    r"^(\d+)\s+([*-])\s+DG:\s*(?:(\d+)x(\d+)|N/A)\s+VP:\s*\S+\s+WA:\s*(?:-?\d+,-?\d+\s+\d+x\d+|N/A)\s*(.*)$")
_VRSTICA_OKNA = re.compile(r"^(0x[0-9a-fA-F]+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s?(.*)$")


def _niz(v, najvec: int) -> str:
    return str(v or "").replace("\n", " ").replace("\t", " ").strip()[:najvec]


def razcleni_namizja(izpis: str) -> List[dict]:
    """`wmctrl -d` -> [{st, trenutno, ime, sirina, visina}] v vrstnem redu stevilk; pokvarjene vrstice se izpustijo."""
    izhod: Dict[int, dict] = {}
    for vrstica in str(izpis or "").splitlines():
        m = _VRSTICA_NAMIZJA.match(vrstica.strip())
        if not m:
            continue
        st = int(m.group(1))
        if st >= NAJVEC_NAMIZIJ * 4 or st in izhod:
            continue
        izhod[st] = {"st": st, "trenutno": m.group(2) == "*", "ime": _niz(m.group(5), _NAJDALJSE_IME),
                     "sirina": int(m.group(3) or 0), "visina": int(m.group(4) or 0)}
    return [izhod[k] for k in sorted(izhod)]


def razcleni_okna(izpis: str) -> List[dict]:
    """`wmctrl -lG` -> [{id, namizje, x, y, w, h, naslov}]; namizje -1 = okno na vseh namizjih (lepljivo)."""
    okna = []
    for vrstica in str(izpis or "").splitlines():
        m = _VRSTICA_OKNA.match(vrstica.strip())
        if not m:
            continue
        okna.append({"id": m.group(1).lower(), "namizje": int(m.group(2)), "x": int(m.group(3)), "y": int(m.group(4)),
                     "w": int(m.group(5)), "h": int(m.group(6)), "naslov": _niz(m.group(8), _NAJDALJSI_NASLOV)})
    return okna


def _delez(v: float) -> float:
    return round(max(0.0, min(1.0, v)), 4)


def postavitev(namizja: List[dict], okna: List[dict], izloci: Optional[set] = None) -> List[dict]:
    """Namizja za preklopnik: [{st, ime, trenutno, okna: [{x, y, w, h, naslov}]}] - polozaj okna je delez zaslona
    (0..1), da ga stran narise v poljubno veliko slicico. Lepljiva okna (-1, npr. pult, namizje) in okna z id-ji iz
    `izloci` (lastna okna, ki jih ne zelimo v shemi) se ne pokazejo; manjsa od NAJMANJSE_OKNO tudi ne."""
    izloci = {str(x).lower() for x in (izloci or ())}
    izhod = []
    # Namizje brez znane velikosti (DG: N/A) dobi velikost najvecjega znanega - vsa so na istem zaslonu.
    privzeta = max(((int(n.get("sirina") or 0), int(n.get("visina") or 0)) for n in namizja), default=(1, 1))
    for n in namizja[:NAJVEC_NAMIZIJ]:
        sirina = max(1, int(n.get("sirina") or privzeta[0] or 1))
        visina = max(1, int(n.get("visina") or privzeta[1] or 1))
        moja = []
        for o in okna:
            if o.get("namizje") != n["st"] or o.get("id") in izloci:
                continue
            w, h = int(o.get("w") or 0), int(o.get("h") or 0)
            if w < NAJMANJSE_OKNO or h < NAJMANJSE_OKNO:
                continue
            x0, y0 = max(0, int(o.get("x") or 0)), max(0, int(o.get("y") or 0))
            x1, y1 = min(sirina, int(o.get("x") or 0) + w), min(visina, int(o.get("y") or 0) + h)
            if x1 - x0 < NAJMANJSE_OKNO // 2 or y1 - y0 < NAJMANJSE_OKNO // 2:
                continue        # okno je skoraj v celoti zunaj zaslona (npr. na drugem monitorju zunaj DG)
            moja.append({"x": _delez(x0 / sirina), "y": _delez(y0 / visina), "w": _delez((x1 - x0) / sirina),
                         "h": _delez((y1 - y0) / visina), "naslov": o.get("naslov") or ""})
            if len(moja) >= NAJVEC_OKEN:
                break
        izhod.append({"st": n["st"], "ime": n.get("ime") or "", "trenutno": bool(n.get("trenutno")), "okna": moja})
    return izhod


def _je_x11(okolje: Optional[dict] = None) -> bool:
    okolje = os.environ if okolje is None else okolje
    if not okolje.get("DISPLAY"):
        return False
    return not (okolje.get("WAYLAND_DISPLAY") or str(okolje.get("XDG_SESSION_TYPE") or "").lower() == "wayland")


class Namizja:
    """Delovni prostori upravljalnika oken prek wmctrl. Vsi klici so kratki (ROK_S) in naj tecejo v niti ozadja."""

    def __init__(self, zazeni: Callable = subprocess.run, wmctrl: Optional[str] = None,
                 okolje: Optional[dict] = None, cakaj: Callable[[float], None] = time.sleep) -> None:
        self._zazeni = zazeni
        self._cakaj = cakaj
        self._wmctrl = wmctrl if wmctrl is not None else (shutil.which("wmctrl") or "")
        self._okolje = okolje

    def na_voljo(self) -> bool:
        return bool(self._wmctrl) and _je_x11(self._okolje)

    def _klic(self, *argumenti: str) -> Optional[str]:
        if not self.na_voljo():
            return None
        try:
            r = self._zazeni([self._wmctrl, *argumenti], capture_output=True, text=True, timeout=ROK_S,
                             env=self._okolje)
        except (OSError, subprocess.SubprocessError) as e:
            print("[SafeerOS] wmctrl", argumenti[:1], e, flush=True)
            return None
        if getattr(r, "returncode", 1) != 0:
            return None
        return str(getattr(r, "stdout", "") or "")

    def seznam(self, izloci: Optional[set] = None) -> List[dict]:
        """Namizja s shemo oken ali [] (ni X11 / wmctrl, ali upravljalnik oken namizij ne podpira)."""
        izpis = self._klic("-d")
        if izpis is None:
            return []
        namizja = razcleni_namizja(izpis)
        if not namizja:
            return []
        okna = razcleni_okna(self._klic("-lG") or "")
        return postavitev(namizja, okna, izloci)

    def preklopi(self, st) -> dict:
        """Preklopi na namizje `st` (stevilka iz seznam()). Stevilka se preveri tu, ne v strani."""
        if isinstance(st, bool) or not isinstance(st, int):
            return {"ok": False, "koda": "napacna_zahteva"}
        namizja = razcleni_namizja(self._klic("-d") or "")
        if not any(n["st"] == st for n in namizja):
            return {"ok": False, "koda": "ni_namizja"}
        return {"ok": self._klic("-s", str(st)) is not None, "st": st}

    def _pocakaj(self, st: int, krat: int) -> bool:
        for _ in range(krat):
            if any(n["st"] == st for n in razcleni_namizja(self._klic("-d") or "")):
                return True
            self._cakaj(0.05)
        return False

    def dodaj(self) -> dict:
        """Novo namizje na koncu in preklop nanj (kot »+« v pregledu namizij Cinnamona). Najvec NAJVEC_NAMIZIJ.

        EWMH: _NET_NUMBER_OF_DESKTOPS (wmctrl -n). Muffin to zapise v nastavitve Cinnamona (num-workspaces), zato
        namizje ostane tudi po ponovni prijavi - tako, kot ce bi ga uporabnik dodal v Cinnamonu."""
        namizja = razcleni_namizja(self._klic("-d") or "")
        if not namizja:
            return {"ok": False, "koda": "ni_na_voljo"}
        if len(namizja) >= NAJVEC_NAMIZIJ:
            return {"ok": False, "koda": "najvec"}
        novo = len(namizja)
        if self._klic("-n", str(novo + 1)) is None:
            return {"ok": False, "koda": "napaka"}
        # Muffin sporocilo zapise v nastavitev num-workspaces in doda namizje (izmerjeno v Xvfb: < 0,5 s); prvi zapis v
        # seji lahko caka na zagon dconf, zato najvec 2 s.
        if not self._pocakaj(novo, 40):
            return {"ok": False, "koda": "ni_dodano"}
        self._klic("-s", str(novo))
        return {"ok": True, "st": novo}
