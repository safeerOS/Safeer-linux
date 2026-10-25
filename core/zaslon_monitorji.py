"""Monitorji tega racunalnika in okvir naprave za Zaslone (lastnik 25. 10. 2026 12:07, zgledni video).

* Desni klik na napravo v Zaslonih -> »Prikazi na monitorju 2«: gledalec te naprave se odpre na izbranem FIZICNEM
  monitorju (celozaslonsko ali v oknu). To NI »naprava kot drugi monitor« (razsirjen zaslon, core/link_prostori).
* Telefon ali tablica se pokaze v okvirju svoje oblike (razmerje stranic naprave, zaobljeni robovi) na sredini
  monitorja nad namizjem - ne raztegnjeno cez celo namizje. Ostrina 1:1: okvir je natanko velik kot zaslon naprave,
  ce gre na monitor; sicer enakomerno pomanjsan (gledalec glajeno pomanjsa).

Cisti del (brez GTK: parametri, okvir, polozaj) je skupen z Windows; monitorji() bere Gdk 4 (Linux).
Preizkusi: tests/test_zaslon_monitorji.py (lazni monitorji).
"""
from __future__ import annotations

import json
from typing import List, Optional

#: Toliko visine (sirine) monitorja najvec zasede okvir naprave - namizje okrog ostane vidno.
DELEZ_OKVIRJA = 0.88
#: Ko velikost zaslona naprave se ni znana (preden pride prva slika): obicajni telefon in tablica pokonci.
PRIVZETO = {"telefon": (1080, 2340), "tablica": (1600, 2560)}
#: Vrste naprav, ki dobijo okvir (racunalnik in televizor odpremo celozaslonsko kot doslej).
Z_OKVIRJEM = frozenset(PRIVZETO)
NAJDALJSA_OZNAKA = 64


def _celo(v, privzeto: int = 0) -> int:
    try:
        n = int(v) if not isinstance(v, bool) else privzeto
    except (TypeError, ValueError):
        return privzeto
    return n


def monitorji(display=None) -> List[dict]:
    """Monitorji, kot jih vidi sistem (Gdk 4): [{st, oznaka (prikljucek, npr. HDMI-1), ime, x, y, w, h, merilo}].
    Brez zaslona ali GTK prazen seznam. `display` za preizkuse (lazni Gdk.Display)."""
    try:
        if display is None:
            import gi
            gi.require_version("Gdk", "4.0")
            from gi.repository import Gdk
            display = Gdk.Display.get_default()
        if display is None:
            return []
        model = display.get_monitors()
        izhod = []
        for i in range(model.get_n_items()):
            m = model.get_item(i)
            g = m.get_geometry()
            prikljucek = str(m.get_connector() or "")[:NAJDALJSA_OZNAKA]
            opis = ""
            for ime in ("get_description", "get_model"):
                try:
                    opis = str(getattr(m, ime)() or "")
                except Exception:  # noqa: BLE001 - starejsi GTK nima get_description
                    opis = ""
                if opis:
                    break
            izhod.append({"st": i + 1, "oznaka": prikljucek or "monitor-%d" % (i + 1), "ime": opis[:80],
                          "x": int(g.x), "y": int(g.y), "w": int(g.width), "h": int(g.height),
                          "merilo": _celo(m.get_scale_factor(), 1) or 1})
        return izhod
    except Exception:  # noqa: BLE001 - brez monitorjev ni izbire monitorja (en monitor kot doslej)
        return []


def najdi(seznam: List[dict], oznaka: str) -> Optional[dict]:
    """Monitor po oznaki (prikljucek) iz izbire na strani; neznana oznaka -> None (odpre se kot doslej)."""
    oznaka = str(oznaka or "")
    return next((m for m in seznam or [] if oznaka and m.get("oznaka") == oznaka), None)


def parametri_odpiranja(niz) -> dict:
    """Tretji parameter ProstorOdpri: "1" (celozaslonsko, kot doslej), "0" ali JSON
    {"celo": bool, "monitor": "<oznaka>", "okvir": bool}. Vse drugo je okno brez monitorja."""
    niz = str(niz or "")
    if niz in ("1", "0", ""):
        return {"celo": niz == "1", "monitor": "", "okvir": False}
    try:
        p = json.loads(niz)
    except ValueError:
        return {"celo": False, "monitor": "", "okvir": False}
    if not isinstance(p, dict):
        return {"celo": False, "monitor": "", "okvir": False}
    monitor = p.get("monitor") if isinstance(p.get("monitor"), str) else ""
    return {"celo": p.get("celo") is True, "monitor": monitor[:NAJDALJSA_OZNAKA], "okvir": p.get("okvir") is True}


def niz_odpiranja(celo: bool, monitor: str = "", okvir: bool = False) -> str:
    """Obratno od parametri_odpiranja; brez monitorja in okvirja ostane star zapis ("1"/"0") za starejsi Control."""
    if not monitor and not okvir:
        return "1" if celo else "0"
    return json.dumps({"celo": bool(celo), "monitor": str(monitor or ""), "okvir": bool(okvir)})


def velikost_naprave(vrsta: str, sirina=0, visina=0) -> tuple:
    """Velikost zaslona naprave v pikah: znana (iz slike) ali privzeta za vrsto."""
    s, v = _celo(sirina), _celo(visina)
    if s > 0 and v > 0:
        return s, v
    return PRIVZETO.get(str(vrsta or ""), PRIVZETO["telefon"])


def okvir_naprave(sirina: int, visina: int, monitor: dict, delez: float = DELEZ_OKVIRJA) -> dict:
    """Okno okvirja naprave na sredini monitorja: {x, y, w, h, merilo, polmer}. 1:1, ce zaslon naprave gre v `delez`
    monitorja; sicer enakomerno pomanjsan (razmerje stranic ostane - nikoli raztegnjeno). `polmer` zaobljenih robov
    sledi napravi (~ 5 % krajse stranice)."""
    mw, mh = max(1, _celo(monitor.get("w"), 1)), max(1, _celo(monitor.get("h"), 1))
    sw, sv = max(1, _celo(sirina, 1)), max(1, _celo(visina, 1))
    merilo = min(1.0, (mw * delez) / sw, (mh * delez) / sv)
    w, h = max(1, int(round(sw * merilo))), max(1, int(round(sv * merilo)))
    x = _celo(monitor.get("x")) + (mw - w) // 2
    y = _celo(monitor.get("y")) + (mh - h) // 2
    return {"x": x, "y": y, "w": w, "h": h, "merilo": round(merilo, 4), "polmer": max(8, int(min(w, h) * 0.05))}


def na_sredino(monitor: dict, sirina: int, visina: int) -> dict:
    """Okno dane velikosti na sredini monitorja (ce je vecje od monitorja, ga omeji na monitor)."""
    mw, mh = max(1, _celo(monitor.get("w"), 1)), max(1, _celo(monitor.get("h"), 1))
    w, h = min(mw, max(1, _celo(sirina, 1))), min(mh, max(1, _celo(visina, 1)))
    return {"x": _celo(monitor.get("x")) + (mw - w) // 2, "y": _celo(monitor.get("y")) + (mh - h) // 2, "w": w, "h": h}
