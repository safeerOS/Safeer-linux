#!/usr/bin/env python3
"""Tema ikon Safeer-Papirus-Dark: Papirus-Dark z lastnimi ikonami stanja Mintovega upravitelja posodobitev.

Lastnik, 17. 10. 2026: »Ikona v zgornjem pultu, ki izgleda kot scit, uporabnik misli, da je Safeer Scit, so pa
posodobitve.« Papirus mintupdate-* rise kot scit. Tu je krozna puscica (posodobitev), v sredini stanje: puscica navzdol
(na voljo, s piko v praznini loka), kljukica (posodobljeno), kazalca ure (preverjam), klicaj (napaka), puscica na crto
(namescam). Vse je zapolnjeno (brez potez): GTK simbolne ikone prebarva samo s »fill«, poteze bi ostale v barvi datoteke.

    python3 tools/ikone_posodobitev.py            # zapise packaging/tema-cinnamon/ikone/Safeer-Papirus-Dark
    python3 tools/ikone_posodobitev.py MAPA       # drugam (predogled)
"""
import math
import os
import sys

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IME = "Safeer-Papirus-Dark"
CILJ = os.path.join(KOREN, "packaging", "tema-cinnamon", "ikone", IME)
STANJA = ("updates-available", "up-to-date", "checking", "error", "installing")
#: Papirus-Dark ima mintupdate-* v teh mapah (Context=Status); poleg tega ena razsirljiva za ostale velikosti.
VELIKOSTI = (16, 22, 24)
# Barve kot v Papirus-Dark (ColorScheme-Text, NeutralText, NegativeText), da se ikona ujema s sosedi v pultu.
BESEDILO, OPOZORILO, NAPAKA = "#dfdfdf", "#ff9800", "#f44336"


def _t(x: float) -> str:
    return ("%.2f" % x).rstrip("0").rstrip(".")


def _tocka(c: float, r: float, kot: float) -> tuple:
    a = math.radians(kot)
    return c + r * math.cos(a), c + r * math.sin(a)


def lok(n: float) -> str:
    """Krozni lok s puscico (v smeri urinega kazalca), praznina zgoraj desno (tam je pika »na voljo«)."""
    c, R, d = n / 2, n * 0.45, n * 0.115
    r = R - d
    zacetek, konec = -12.0, 252.0          # stopinje, y navzdol: lok gre cez desno, spodaj, levo do vrha
    z1, z2 = _tocka(c, R, zacetek), _tocka(c, R, konec)
    n1, n2 = _tocka(c, r, konec), _tocka(c, r, zacetek)
    velik = 1 if (konec - zacetek) % 360 > 180 else 0
    pot = "M%s %sA%s %s 0 %d 1 %s %sL%s %sA%s %s 0 %d 0 %s %sZ" % (
        _t(z1[0]), _t(z1[1]), _t(R), _t(R), velik, _t(z2[0]), _t(z2[1]),
        _t(n1[0]), _t(n1[1]), _t(r), _t(r), velik, _t(n2[0]), _t(n2[1]))
    # Puscica na koncu loka: osnova pravokotno na lok, konica v smeri vrtenja (tangenta).
    sred = R - d / 2
    p = _tocka(c, sred, konec)
    a = math.radians(konec)
    tan, nor = (-math.sin(a), math.cos(a)), (math.cos(a), math.sin(a))
    s, h = d * 1.35, d * 1.9
    o1 = (p[0] + nor[0] * s, p[1] + nor[1] * s)
    o2 = (p[0] - nor[0] * s, p[1] - nor[1] * s)
    k = (p[0] + tan[0] * h, p[1] + tan[1] * h)
    pot += "M%s %sL%s %sL%s %sZ" % (_t(o1[0]), _t(o1[1]), _t(k[0]), _t(k[1]), _t(o2[0]), _t(o2[1]))
    return pot


def puscica_dol(n: float, crta: bool = False) -> str:
    c, d = n / 2, n * 0.13
    vrh, konica, sirina = c - n * 0.22, c + n * (0.12 if crta else 0.2), n * 0.19
    glava = konica - sirina
    pot = "M%s %sH%sV%sH%sL%s %sL%s %sH%sZ" % (
        _t(c - d / 2), _t(vrh), _t(c + d / 2), _t(glava), _t(c + sirina), _t(c), _t(konica),
        _t(c - sirina), _t(glava), _t(c - d / 2))
    if crta:
        pot += "M%s %sh%sv%sh%sZ" % (_t(c - n * 0.19), _t(c + n * 0.16), _t(n * 0.38), _t(d * 0.8), _t(-n * 0.38))
    return pot


def kljukica(n: float) -> str:
    # Debela kljukica pod 45 stopinj (mreza 24, pomanjsana na n).
    k = n / 24.0
    tocke = [(7, 12.4), (9, 10.4), (11, 12.4), (16, 7.4), (18, 9.4), (11, 16.4)]
    return "M" + "L".join("%s %s" % (_t(x * k), _t(y * k)) for x, y in tocke) + "Z"


def ura(n: float) -> str:
    c, d = n / 2, n * 0.12
    return "M%s %sh%sv%sh%sv%sh%sZ" % (_t(c - d / 2), _t(c - n * 0.21), _t(d), _t(n * 0.21 - d / 2),
                                       _t(n * 0.17), _t(d), _t(-n * 0.17 - d))


def klicaj(n: float) -> str:
    c, d = n / 2, n * 0.13
    pika = n * 0.08
    return ("M%s %sh%sv%sh%sZ" % (_t(c - d / 2), _t(c - n * 0.2), _t(d), _t(n * 0.25), _t(-d)) +
            "M%s %sa%s %s 0 1 0 %s 0a%s %s 0 1 0 %s 0Z" % (_t(c - pika), _t(c + n * 0.15), _t(pika), _t(pika),
                                                        _t(2 * pika), _t(pika), _t(pika), _t(-2 * pika)))


def ikona(stanje: str, n: int, simbolna: bool) -> str:
    """SVG ikone stanja velikosti n. Simbolna: barve dolocajo razredi (GTK jih prebarva), sicer barve Papirusa."""
    sredina = {"updates-available": puscica_dol(n), "up-to-date": kljukica(n), "checking": ura(n),
               "error": klicaj(n), "installing": puscica_dol(n, crta=True)}[stanje]
    barva_sredine = NAPAKA if stanje == "error" else BESEDILO
    razred_sredine = ' class="error"' if stanje == "error" else ""
    deli = []
    if simbolna:
        deli.append('<path fill="%s" d="%s"/>' % (BESEDILO, lok(n)))
        deli.append('<path fill="%s"%s d="%s"/>' % (barva_sredine, razred_sredine, sredina))
    else:
        deli.append('<path fill="%s" d="%s"/>' % (BESEDILO, lok(n)))
        deli.append('<path fill="%s" d="%s"/>' % (barva_sredine, sredina))
    if stanje == "updates-available":
        cx, cy = _tocka(n / 2, n * 0.4, -55)
        deli.append('<circle%s fill="%s" cx="%s" cy="%s" r="%s"/>' % (
            ' class="warning"' if simbolna else "", OPOZORILO, _t(cx), _t(cy), _t(n * 0.15)))
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">\n %s\n</svg>\n'
            % (n, n, n, n, "\n ".join(deli)))


def index_theme() -> str:
    mape = ["%dx%d/panel" % (v, v) for v in VELIKOSTI] + ["scalable/status"]
    deli = ["[Icon Theme]", "Name=%s" % IME,
            "Comment=Papirus-Dark with Safeer update status icons (Safeer Cinnamon)",
            # Vse ostale ikone iz Papirus-Dark; brez Papirusa safeer-cinnamon te teme ne izbere.
            "Inherits=Papirus-Dark,breeze-dark,hicolor", "Example=folder",
            "Directories=" + ",".join(mape), ""]
    for v in VELIKOSTI:
        deli += ["[%dx%d/panel]" % (v, v), "Context=Status", "Size=%d" % v, "Type=Fixed", ""]
    deli += ["[scalable/status]", "Context=Status", "Size=16", "MinSize=8", "MaxSize=512", "Type=Scalable", ""]
    return "\n".join(deli)


def zapisi(cilj: str = CILJ) -> list:
    zapisane = []
    for mapa, n in [("%dx%d/panel" % (v, v), v) for v in VELIKOSTI] + [("scalable/status", 16)]:
        os.makedirs(os.path.join(cilj, mapa), exist_ok=True)
        for stanje in STANJA:
            # mintUpdate 7 isce »…-symbolic«; starejsi in Papirus »mintupdate-<stanje>«: obe imeni, ista slika.
            for ime, simbolna in (("mintupdate-%s.svg" % stanje, False), ("mintupdate-%s-symbolic.svg" % stanje, True)):
                pot = os.path.join(cilj, mapa, ime)
                with open(pot, "w", encoding="utf-8") as f:
                    f.write(ikona(stanje, n, simbolna))
                zapisane.append(pot)
    with open(os.path.join(cilj, "index.theme"), "w", encoding="utf-8") as f:
        f.write(index_theme())
    return zapisane


if __name__ == "__main__":
    print(len(zapisi(sys.argv[1] if len(sys.argv) > 1 else CILJ)), "ikon")
