#!/usr/bin/env python3
"""Analiza merilnih dnevnikov SafeerZaslonCas (zastoj zvoka ~4 s, PC -> TV).

Iz dnevnika PC (stderr posiljatelja) in dnevnika TV (adb logcat) izracuna odmik ur O iz sidra
(glava_poslana / glava_prejeta), vseh 15 intervalov iz tabele v merjenje4s-izhod.md (razdelek 5)
z oznako normalno / sumljivo / 4 s in na koncu odlocitev (a) / (b) / omrezje / vir na PC.

Samo standardna knjiznica. Orodje ne sme pasti na nobenem vhodu.

Izhodne kode:
    0  izracun je narejen in natanko eno pravilo odlocitve je izpolnjeno
    1  izracun je narejen, a odlocitve ni (premalo podatkov, nobeno ali vec pravil hkrati)
    2  napacni argumenti ukazne vrstice (argparse)
    3  vsaj enega dnevnika ni bilo mogoce prebrati (izpis se vseeno naredi s tem, kar je)
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import Dict, List, Optional, Tuple

OZNAKA = "SafeerZaslonCas"

# Oznake intervalov.
NORMALNO, SUMLJIVO, STIRI_S, NI_PODATKA, NI_UPORABNO = (
    "normalno", "sumljivo", "4 s", "ni podatka", "ni uporabno")

# Pas "4 s": 4 s +- 1 s (opazen zastoj je ~4 s). Vse zunaj normale in zunaj pasu je sumljivo.
PAS_4S_OD_MS, PAS_4S_DO_MS = 3000, 5000

# Privzeti zvok posiljatelja (link_zaslon_linux.py: ZVOK_HZ=48000, ZVOK_KANALI=2, s16le).
PRIVZETO_HZ, PRIVZETO_KANALI = 48000, 2

_POLJE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)=(\S*)")


# ------------------------------------------------------------------ razclenitev

def razcleni_vrstico(vrstica) -> Optional[Dict[str, str]]:
    """Ena vrstica -> slovar polj ali None (smeti).

    Sprejme golo vrstico, predpono logcat (-v monotonic, threadtime, brief, epoch ...) in
    vrstico "ton_zacetek t_ms=<n>" (poskus B). Zahteva dogodek in celostevilski t_ms.
    """
    try:
        if not isinstance(vrstica, str):
            vrstica = bytes(vrstica).decode("utf-8", "replace")
        vrstica = vrstica.replace("\x00", " ").strip()
        if not vrstica:
            return None
        i = vrstica.find("dogodek=")
        if i >= 0:
            # Vse pred "dogodek=" je predpona (logcat, oznaka): ne beremo je.
            polja = dict(_POLJE.findall(vrstica[i:]))
        elif vrstica.startswith("ton_zacetek") or " ton_zacetek " in (" " + vrstica + " "):
            j = vrstica.find("ton_zacetek")
            polja = dict(_POLJE.findall(vrstica[j:]))
            polja["dogodek"] = "ton_zacetek"
        else:
            return None
        if not polja.get("dogodek"):
            return None
        if _int(polja.get("t_ms")) is None:
            return None
        return polja
    except Exception:
        return None


def _int(v) -> Optional[int]:
    try:
        if v is None:
            return None
        return int(str(v).strip())
    except Exception:
        return None


def preberi_dogodke(vrstice) -> List[Dict[str, str]]:
    """Vse veljavne vrstice v vrstnem redu datoteke (smeti tiho izpusti)."""
    izid = []
    try:
        for v in vrstice:
            p = razcleni_vrstico(v)
            if p is not None:
                izid.append(p)
    except Exception:
        pass
    return izid


def izberi_sejo(dogodki: List[Dict[str, str]], seja: Optional[str]) -> Tuple[Optional[str], Dict[str, Dict[str, str]], List[str]]:
    """Izbere sejo in vrne (id seje, {dogodek: polja}, opozorila).

    Brez --seja: seja z najvecjim t_ms (kronolosko zadnja; pri enakem t_ms kasnejsa v datoteki).
    Znotraj seje so vrstice razvrscene po t_ms; pri podvojenem dogodku velja najzgodnejsi ("prvi").
    ton_zacetek nima seje in se ne izbira tu.
    """
    opozorila: List[str] = []
    po_sejah: Dict[str, List[Tuple[int, int, Dict[str, str]]]] = {}
    for zap, d in enumerate(dogodki):
        if d.get("dogodek") == "ton_zacetek":
            continue
        s = d.get("seja", "")
        po_sejah.setdefault(s, []).append((_int(d.get("t_ms")) or 0, zap, d))
    if not po_sejah:
        return None, {}, opozorila
    if seja is not None and seja != "":
        if seja not in po_sejah:
            opozorila.append("seja %s ni v dnevniku (na voljo: %s)" % (seja, ", ".join(sorted(po_sejah))))
            return seja, {}, opozorila
        izbrana = seja
    else:
        izbrana = max(po_sejah, key=lambda k: (max(t for t, _, _ in po_sejah[k]),
                                               max(z for _, z, _ in po_sejah[k])))
        if len(po_sejah) > 1:
            opozorila.append("vec sej (%s), izbrana zadnja: %s" % (", ".join(sorted(po_sejah)), izbrana))
    vrstice = sorted(po_sejah[izbrana], key=lambda x: (x[0], x[1]))
    po_imenu: Dict[str, Dict[str, str]] = {}
    for _, _, d in vrstice:
        po_imenu.setdefault(d["dogodek"], d)
    return izbrana, po_imenu, opozorila


def najdi_ton(dogodki: List[Dict[str, str]]) -> Optional[int]:
    """Zadnji ton_zacetek v dnevniku PC (ce ga je uporabnik tja zapisal)."""
    t = None
    for d in dogodki:
        if d.get("dogodek") == "ton_zacetek":
            t = _int(d.get("t_ms"))
    return t


# ------------------------------------------------------------------ izracun

def _t(sl: Dict[str, Dict[str, str]], ime: str) -> Optional[int]:
    d = sl.get(ime)
    return _int(d.get("t_ms")) if d else None


def _polje(sl: Dict[str, Dict[str, str]], ime: str, kljuc: str) -> Optional[str]:
    d = sl.get(ime)
    return d.get(kljuc) if d else None


def _razlika(a: Optional[int], b: Optional[int]) -> Optional[int]:
    return None if a is None or b is None else a - b


def oznaci(v: Optional[float], od: float, do: float) -> str:
    """normalno, ce je od <= v <= do; 4 s, ce je |v| v pasu 3-5 s; sicer sumljivo."""
    if v is None:
        return NI_PODATKA
    if od <= v <= do:
        return NORMALNO
    if PAS_4S_OD_MS <= abs(v) <= PAS_4S_DO_MS:
        return STIRI_S
    return SUMLJIVO


def analiziraj(pc_vrstice, tv_vrstice, rtt_ms: Optional[float] = None,
               ton_zacetek: Optional[int] = None, seja: Optional[str] = None) -> dict:
    """Glavni izracun. Vrne slovar z O, intervali, opozorili in odlocitvijo. Ne vrze izjeme."""
    try:
        return _analiziraj(pc_vrstice, tv_vrstice, rtt_ms, ton_zacetek, seja)
    except Exception as e:   # zadnja varovalka: orodje ne sme pasti
        return {"O": None, "intervali": {}, "opozorila": ["notranja napaka: %r" % (e,)],
                "odlocitev": None, "razlog": "notranja napaka orodja", "ujemanja": [],
                "seja_pc": None, "seja_tv": None, "poskus": "?"}


def _razcleni_sejo_arg(seja: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """--seja "PC", "PC:TV", ":TV" ali "PC:"; prazen del = zadnja seja."""
    if seja is None:
        return None, None
    s = str(seja)
    if ":" in s:
        a, b = s.split(":", 1)
        return (a or None), (b or None)
    return s or None, None


def _analiziraj(pc_vrstice, tv_vrstice, rtt_ms, ton_zacetek, seja) -> dict:
    opozorila: List[str] = []
    pc_vsi = preberi_dogodke(pc_vrstice or [])
    tv_vsi = preberi_dogodke(tv_vrstice or [])
    seja_pc_arg, seja_tv_arg = _razcleni_sejo_arg(seja)
    seja_pc, pc, op = izberi_sejo(pc_vsi, seja_pc_arg)
    opozorila += ["PC: " + o for o in op]
    seja_tv, tv, op = izberi_sejo(tv_vsi, seja_tv_arg)
    opozorila += ["TV: " + o for o in op]
    if not pc:
        opozorila.append("PC: ni veljavnih vrstic SafeerZaslonCas")
    if not tv:
        opozorila.append("TV: ni veljavnih vrstic SafeerZaslonCas")

    if ton_zacetek is None:
        ton_zacetek = najdi_ton(pc_vsi)
    poskus = "B" if ton_zacetek is not None else "A"

    # Odmik O = TV.glava_prejeta - PC.glava_poslana - RTT/2 (razdelek 4.4).
    if rtt_ms is None:
        opozorila.append("RTT ni podan: O je brez popravka RTT/2 (napaka do RTT/2)")
        pol_rtt = 0.0
    else:
        pol_rtt = float(rtt_ms) / 2.0
    tv_g, pc_g = _t(tv, "glava_prejeta"), _t(pc, "glava_poslana")
    O: Optional[float] = None
    if tv_g is not None and pc_g is not None:
        O = tv_g - pc_g - pol_rtt
        if O == int(O):
            O = int(O)
    else:
        opozorila.append("sidra ni (glava_poslana/glava_prejeta): intervali 7, 9, 10 ni podatka")
    sidro_veljavno = O is not None
    if _polje(tv, "glava_prejeta", "prek_huba") == "1":
        opozorila.append("sidro ni veljavno (prek_huba=1): intervali 7, 9, 10 se ne uporabijo za odlocitev")
        sidro_veljavno = False

    hz = _int(_polje(tv, "audiotrack_ustvarjen", "hz")) or PRIVZETO_HZ
    kanali = _int(_polje(tv, "audiotrack_ustvarjen", "kanali")) or PRIVZETO_KANALI
    bps = hz * kanali * 2
    if hz <= 0 or bps <= 0:
        hz, bps = PRIVZETO_HZ, PRIVZETO_HZ * PRIVZETO_KANALI * 2

    def preko(tv_ime, pc_ime):
        a, b = _t(tv, tv_ime), _t(pc, pc_ime)
        if a is None or b is None or O is None:
            return None
        v = a - (b + O)
        return int(v) if v == int(v) else v

    rtt_meja = max(100.0, float(rtt_ms or 0))
    I: Dict[int, dict] = {}

    def vpisi(st, opis, vrednost, oznaka, enota="ms", opomba=""):
        I[st] = {"opis": opis, "vrednost": vrednost, "oznaka": oznaka, "enota": enota, "opomba": opomba}

    v = _razlika(_t(pc, "prvo_branje_zvok"), _t(pc, "po_popen_zvok"))
    vpisi(1, "PC.prvo_branje_zvok - PC.po_popen_zvok", v, oznaci(v, 0, 300))
    v = _razlika(_t(pc, "prvi_bajt_zvok"), _t(pc, "prvi_bajt_slika"))
    vpisi(2, "PC.prvi_bajt_zvok - PC.prvi_bajt_slika", v, oznaci(v, -200, 200))
    v = _razlika(_t(pc, "prvi_bajt_zvok"), _t(pc, "prvo_branje_zvok"))
    vpisi(3, "PC.prvi_bajt_zvok - PC.prvo_branje_zvok", v, oznaci(v, 0, 50))
    v = _razlika(_t(pc, "prvi_zvok_neprazen"), _t(pc, "prvo_branje_zvok"))
    if poskus == "A":
        vpisi(4, "PC.prvi_zvok_neprazen - PC.prvo_branje_zvok (poskus A)", v, oznaci(v, 0, 100))
    else:
        vpisi(4, "PC.prvi_zvok_neprazen - PC.prvo_branje_zvok (poskus A)", v, NI_UPORABNO,
              opomba="poskus B: seja se zacne v tisini")
    if poskus == "B":
        v = _razlika(_t(pc, "prvi_zvok_neprazen"), ton_zacetek)
        oz = oznaci(v, 0, 100)
        opomba = ""
        if v is not None and v < 0:
            oz, opomba = SUMLJIVO, "neprazen zvok pred tonom: monitor ni tih, poskus B ne velja"
        vpisi(5, "PC.prvi_zvok_neprazen - ton_zacetek (poskus B)", v, oz, opomba=opomba)
    else:
        vpisi(5, "PC.prvi_zvok_neprazen - ton_zacetek (poskus B)", None, NI_UPORABNO,
              opomba="ni ton_zacetek: poskus A")
    # 6: presezek bajtov nad realnim casom v sekundah (bajti_skupaj proti casu od prvega branja).
    b6 = _int(_polje(pc, "zvok_po_5s", "bajti_skupaj"))
    t6 = _razlika(_t(pc, "zvok_po_5s"), _t(pc, "prvo_branje_zvok"))
    if b6 is not None and t6 is not None:
        pricakovano = t6 / 1000.0 * bps
        presezek_ms = (b6 - pricakovano) / bps * 1000.0
        vpisi(6, "PC.zvok_po_5s.bajti_skupaj (presezek nad realnim casom)", b6,
              oznaci(presezek_ms, -500, 500), enota="B",
              opomba="pricakovano %.0f B, presezek %s s" % (pricakovano, _s(presezek_ms / 1000.0)))
        I[6]["presezek_s"] = presezek_ms / 1000.0
    else:
        vpisi(6, "PC.zvok_po_5s.bajti_skupaj (presezek nad realnim casom)", None, NI_PODATKA, enota="B")
    # 7: po definiciji O je to natanko RTT/2 (glej porocilo: tabela je napacno navajala 0).
    v = preko("glava_prejeta", "glava_poslana")
    vpisi(7, "TV.glava_prejeta - (PC.glava_poslana + O)", v,
          NI_PODATKA if v is None else (NORMALNO if abs(v - pol_rtt) <= 1 else SUMLJIVO),
          opomba="po definiciji O = RTT/2")
    wp, wt = _int(_polje(pc, "glava_poslana", "wall_ms")), _int(_polje(tv, "glava_prejeta", "wall_ms"))
    if wp is not None and wt is not None:
        kontrola = wt - wp - pol_rtt
        I[7]["opomba"] += "; kontrola wall_ms: %s ms (|.| <= 50 je skladno z NTP)" % _fmt(kontrola)
    v = _razlika(_t(tv, "audiotrack_ustvarjen"), _t(tv, "glava_prejeta"))
    vpisi(8, "TV.audiotrack_ustvarjen - TV.glava_prejeta", v, oznaci(v, 0, 300))
    v = preko("prvi_write", "prvi_bajt_zvok")
    vpisi(9, "TV.prvi_write - (PC.prvi_bajt_zvok + O)", v, oznaci(v, -50, rtt_meja))
    v = preko("prva_slika_v_dekoder", "prvi_bajt_slika")
    vpisi(10, "TV.prva_slika_v_dekoder - (PC.prvi_bajt_slika + O)", v, oznaci(v, -50, rtt_meja))
    v = _razlika(_t(tv, "prva_slika_prikazana"), _t(tv, "prvi_write"))
    vpisi(11, "TV.prva_slika_prikazana - TV.prvi_write", v, oznaci(v, -200, 300))
    v = _razlika(_t(tv, "prvi_zvok_neprazen"), _t(tv, "prvi_write"))
    if poskus == "A":
        vpisi(12, "TV.prvi_zvok_neprazen - TV.prvi_write (poskus A)", v, oznaci(v, 0, 100))
    else:
        vpisi(12, "TV.prvi_zvok_neprazen - TV.prvi_write (poskus A)", v, NI_UPORABNO, opomba="poskus B")
    # 13: predvajano v prvih ~5 s; oznaka po primanjkljaju (cas od prvi_write - predvajano).
    gp = _int(_polje(tv, "zvok_po_5s", "glava_predvajanja"))
    t13 = _razlika(_t(tv, "zvok_po_5s"), _t(tv, "prvi_write"))
    if gp is not None and t13 is not None:
        predvajano = gp / float(hz)
        primanjkljaj_ms = t13 - predvajano * 1000.0
        vpisi(13, "TV.zvok_po_5s.glava_predvajanja / hz proti casu od prvi_write", predvajano,
              oznaci(primanjkljaj_ms, -500, 500), enota="s",
              opomba="cas %s s, primanjkljaj %s s, play_state=%s" % (
                  _s(t13 / 1000.0), _s(primanjkljaj_ms / 1000.0), _polje(tv, "zvok_po_5s", "play_state")))
        I[13]["primanjkljaj_s"] = primanjkljaj_ms / 1000.0
    else:
        vpisi(13, "TV.zvok_po_5s.glava_predvajanja / hz proti casu od prvi_write", None, NI_PODATKA, enota="s")
    pon = _int(_polje(tv, "zvok_po_5s", "ponujeno_skupaj"))
    spr = _int(_polje(tv, "zvok_po_5s", "sprejeto_skupaj"))
    if pon is not None and spr is not None:
        izpusceno = (pon - spr) / float(bps)
        vpisi(14, "TV.zvok_po_5s: (ponujeno_skupaj - sprejeto_skupaj) / B/s", izpusceno,
              oznaci(izpusceno * 1000.0, -200, 200), enota="s", opomba="B/s = %d" % bps)
    else:
        vpisi(14, "TV.zvok_po_5s: (ponujeno_skupaj - sprejeto_skupaj) / B/s", None, NI_PODATKA, enota="s")
    spr1, baj1 = _polje(tv, "prvi_write", "sprejeto"), _polje(tv, "prvi_write", "bajti")
    if spr1 is None:
        vpisi(15, "TV.prvi_write.sprejeto = bajti", None, NI_PODATKA, enota="")
    else:
        si, bi = _int(spr1), _int(baj1)
        if si is not None and bi is not None and si == bi:
            oz, op15 = NORMALNO, ""
        elif spr1 == "null":
            oz, op15 = SUMLJIVO, "AudioTrack ob prvem zvoku ne obstaja"
        elif si == 0:
            oz, op15 = SUMLJIVO, "medpomnilnik poln ali sled ne tece"
        else:
            oz, op15 = SUMLJIVO, "sprejeto != bajti"
        vpisi(15, "TV.prvi_write.sprejeto = bajti", "%s/%s" % (spr1, baj1), oz, enota="", opomba=op15)

    # Pri neveljavnem sidru se 7, 9, 10 ne uporabijo za odlocitev.
    def oz(st):
        if st in (7, 9, 10) and not sidro_veljavno:
            return NI_PODATKA
        return I[st]["oznaka"]

    odl = _odloci(oz, poskus)
    return {"O": O, "intervali": I, "opozorila": opozorila, "seja_pc": seja_pc, "seja_tv": seja_tv,
            "poskus": poskus, "sidro_veljavno": sidro_veljavno, **odl}


def _odloci(oz, poskus) -> dict:
    """Pravila iz razdelka 5 ("Odlocitev"). "priblizno 4 s" pomeni oznako "4 s"."""
    ujemanja: List[Tuple[str, str]] = []
    # (a) 1-6 normalno (kjer veljajo za poskus), 13 in 14 "4 s".
    vrstice_a = [1, 2, 3, 6] + ([4] if poskus == "A" else [5])
    if all(oz(i) == NORMALNO for i in vrstice_a) and oz(13) == STIRI_S and oz(14) == STIRI_S:
        ujemanja.append(("(a)", "1-6 normalno, 13 in 14 kazeta ~4 s: zvok pride pravocasno, "
                                "AudioTrack ali izhodna pot na TV ga zacne predvajati pozno"))
    # (b) 5 ali 6 "4 s".
    if oz(5) == STIRI_S or oz(6) == STIRI_S:
        ujemanja.append(("(b)", "5 ali 6 kaze ~4 s: zaostanek v pulse na PC"))
    # omrezje: 3 ali (9 in 10).
    if oz(3) == STIRI_S or (oz(9) == STIRI_S and oz(10) == STIRI_S):
        ujemanja.append(("omrezje", "3 ali 9 in 10 kazejo ~4 s: omrezje, TCP ali zanka branja TV"))
    # vir na PC: 4 ali 12 "4 s" ob normalnem 5 (v poskusu A 5 ne velja in ni "4 s").
    if (oz(4) == STIRI_S or oz(12) == STIRI_S) and oz(5) != STIRI_S:
        ujemanja.append(("vir na PC", "4 ali 12 kaze ~4 s tisine: vir zvoka na PC (monitor/usmerjanje)"))

    if len(ujemanja) == 1:
        return {"odlocitev": ujemanja[0][0], "razlog": ujemanja[0][1], "ujemanja": ujemanja}
    if len(ujemanja) > 1:
        return {"odlocitev": None, "ujemanja": ujemanja,
                "razlog": "nejasno: hkrati velja vec pravil (%s)" % ", ".join(u[0] for u in ujemanja)}
    kljucne = sorted(set([1, 2, 3, 6, 13, 14] + ([4, 12] if poskus == "A" else [5])))
    manjka = [i for i in kljucne if oz(i) == NI_PODATKA]
    if manjka:
        return {"odlocitev": None, "ujemanja": [],
                "razlog": "podatkov ni dovolj za odlocitev: ni podatka za interval(e) %s"
                          % ", ".join(str(i) for i in manjka)}
    return {"odlocitev": None, "ujemanja": [],
            "razlog": "noben vzorec iz pravil ni izpolnjen (zastoja ~4 s v teh podatkih ni ali je drugje)"}


# ------------------------------------------------------------------ izpis

def _s(x: float) -> str:
    return ("%.2f" % x).replace(".", ",")


def _fmt(v) -> str:
    if v is None:
        return "ni podatka"
    if isinstance(v, float) and v != int(v):
        return ("%.1f" % v).replace(".", ",")
    if isinstance(v, float):
        return str(int(v))
    return str(v)


def izpis(r: dict) -> str:
    vr = ["Analiza SafeerZaslonCas (zastoj zvoka ~4 s)",
          "seja PC: %s, seja TV: %s, poskus: %s" % (r.get("seja_pc"), r.get("seja_tv"), r.get("poskus")),
          "O (odmik TV - PC): %s" % (_fmt(r.get("O")) + (" ms" if r.get("O") is not None else ""))]
    for o in r.get("opozorila", []):
        vr.append("OPOZORILO: " + o)
    vr.append("")
    for st in sorted(r.get("intervali", {})):
        it = r["intervali"][st]
        v = it["vrednost"]
        if v is None:
            vs = "ni podatka"
        elif it["enota"] == "s":
            vs = _s(v) + " s"
        elif it["enota"] in ("", "B"):
            vs = str(v) + (" B" if it["enota"] == "B" else "")
        else:
            vs = _fmt(v) + " ms"
        vr.append("#%-2d %-60s %-14s [%s]%s" % (st, it["opis"], vs, it["oznaka"],
                                                (" - " + it["opomba"]) if it["opomba"] else ""))
    vr.append("")
    if r.get("odlocitev"):
        vr.append("ODLOCITEV: %s - %s" % (r["odlocitev"], r.get("razlog", "")))
    else:
        vr.append("ODLOCITEV: ni - %s" % r.get("razlog", ""))
    return "\n".join(vr)


def _beri(pot: str) -> Tuple[List[str], Optional[str]]:
    try:
        with open(pot, "rb") as f:
            return f.read().decode("utf-8", "replace").splitlines(), None
    except Exception as e:
        return [], "dnevnika %s ni mogoce prebrati: %s" % (pot, e.__class__.__name__)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Analiza dnevnikov SafeerZaslonCas (PC + TV).")
    p.add_argument("pc_dnevnik", help="dnevnik PC (stderr posiljatelja)")
    p.add_argument("tv_dnevnik", help="dnevnik TV (adb logcat -s SafeerZaslonCas)")
    p.add_argument("--rtt-ms", type=float, default=None, help="povprecni RTT (ping) v ms")
    p.add_argument("--ton-zacetek", type=int, default=None, help="t_ms ton_zacetek na uri PC (poskus B)")
    p.add_argument("--seja", default=None, help='seja: "PC", "PC:TV", ":TV" (privzeto zadnja)')
    try:
        a = p.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code not in (0, None) else 0
    pc, n1 = _beri(a.pc_dnevnik)
    tv, n2 = _beri(a.tv_dnevnik)
    r = analiziraj(pc, tv, a.rtt_ms, a.ton_zacetek, a.seja)
    for n in (n1, n2):
        if n:
            r.setdefault("opozorila", []).insert(0, n)
    try:
        print(izpis(r))
    except Exception:
        pass
    if n1 or n2:
        return 3
    return 0 if r.get("odlocitev") else 1


if __name__ == "__main__":
    sys.exit(main())
