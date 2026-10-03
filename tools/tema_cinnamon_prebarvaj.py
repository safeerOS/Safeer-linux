#!/usr/bin/env python3
"""Safeer Cinnamon: prebarvanje osnove Mint-Y-Dark-Blue v paleto Safeer.

Tema Safeer Cinnamon osnovo uvozi (@import) in jo dopolni z rocno pisanimi pravili. Mint-Y ima barve zapisane
neposredno v pravilih (prevedeno iz SASS), zato so povsod, kjer nasih pravil ni, ostale Mintove sivine in nasicena modra
(drsniki, napredek, zavihki, polja v orodnih vrsticah, pogovorna okna lupine ...). To orodje prebere osnovo in za vsako
pravilo z Mintovo sivino ali modro izpise ISTI selektor z istimi lastnostmi v paleti Safeer:

    python3 tools/tema_cinnamon_prebarvaj.py [--osnova [OZNAKA=]/usr/share/themes/Mint-Y-Dark-Blue] ...

Mint-Y se med izdajami Linux Minta spreminja (22.0 ima mint-themes 2.1.8, 22.3 ze 2.3.8 z dosti vec pravili za lupino),
uporabniki pa imajo razlicne izdaje. Zato --osnova navedemo veckrat, od NAJSTAREJSE do NAJNOVEJSE: izid je unija
pravil vseh razlicic (za isti selektor velja lastnost iz najnovejse, ki jo ima). Pravilo za selektor, ki ga
uporabnikova razlicica nima, ne naredi nic.

Izid (prebarvano.css v gtk-3.0, gtk-4.0 in cinnamon) je v repozitoriju; orodje pozenemo znova, ko Mint izda novo temo.
Do takrat nova Mintova pravila ostanejo v Mintovih barvah - nic se ne pokvari. Selektorji so Mintovi (GPL-3.0, glej
packaging/tema-cinnamon/COPYING).

Pravila preslikave:
  * sivina (r = g = b) gre po svetlosti na modro-sivo lestvico Safeer (LESTVICA); crna in bela ostaneta;
  * Mintova modra (odtenek okoli 210 stopinj) postane poudarek Safeer #8ac7ff, temnejsi in svetlejsi odtenki ob njem;
  * temna sivina v vlogi roba (border*, box-shadow, outline) postane svetel mehak rob Safeer - temen rob na temno modri
    povrsini se ne vidi (okvirji, locila, polja bi se zlili s podlago);
  * bela pisava na Mintovi modri podlagi postane temna (#0b1424), ker je poudarek Safeer svetel;
  * potrditvena polja, izbirni gumbi in stikala so v osnovi SLIKE v Mintovi modri: tu jih narisemo s CSS v paleti
    (isti selektorji, zato veljajo v vseh stanjih, ki jih osnova pozna);
  * druge lastnosti s sliko (url) preskocimo: pot do slike bi iz nase datoteke kazala v prazno.
"""
from __future__ import annotations

import argparse
import colorsys
import re
import sys
from pathlib import Path

KOREN = Path(__file__).resolve().parent.parent
CILJ = KOREN / "packaging" / "tema-cinnamon" / "Safeer-Cinnamon"
DELI = ("gtk-3.0/gtk.css", "gtk-4.0/gtk.css", "cinnamon/cinnamon.css")

#: Svetlost Mintove sivine (0-255) -> barva Safeer. Vmes linearno. Vrstni red svetlosti ostane (robovi temnejsi od
#: povrsin, gumbi svetlejsi), zato se razmerja v Mintovi temi ohranijo.
LESTVICA = ((0x0d, "#060b13"), (0x21, "#09101b"), (0x29, "#0b1422"), (0x2f, "#0d1626"), (0x38, "#0e1727"), (0x40, "#0f1a2a"),
            (0x45, "#16243b"), (0x52, "#1e3050"), (0x60, "#2a4068"), (0x80, "#4f6a94"), (0xa0, "#8ea3c2"), (0xc3, "#d5e6fa"),
            (0xda, "#eaf2ff"), (0xf2, "#f6faff"))
#: Temna sivina (do te svetlosti) v vlogi roba: poln rob in prosojen rob (delez Mintove prosojnosti).
ROB_DO = 0x33
ROB = (0x22, 0x34, 0x4f)
ROB_PROSOJEN = (215, 234, 255)
ROB_DELEZ = 0.42
POUDAREK = (0x8a, 0xc7, 0xff)
NA_POUDARKU = "#0b1424"

HEX = re.compile(r"#([0-9a-fA-F]{6})\b")
RGBA = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(,\s*[0-9.]+\s*)?\)")
BELA = re.compile(r"^\s*(#fff(fff)?|white|rgba\(\s*255\s*,\s*255\s*,\s*255\s*,\s*(0\.[89]\d*|1(\.0*)?)\s*\))\s*(!important)?\s*$", re.I)


def _rgb(hex6: str) -> tuple:
    h = hex6.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def je_siva(r: int, g: int, b: int) -> bool:
    return max(r, g, b) - min(r, g, b) <= 6


def je_mintova_modra(r: int, g: int, b: int) -> bool:
    h, l, s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    return 0.54 <= h <= 0.63 and s >= 0.45 and 0.15 <= l <= 0.93


def siva_v_safeer(svetlost: int) -> tuple:
    if svetlost <= LESTVICA[0][0]:
        return _rgb(LESTVICA[0][1])
    for (a, ba), (b, bb) in zip(LESTVICA, LESTVICA[1:]):
        if a <= svetlost <= b:
            t = (svetlost - a) / float(b - a)
            ra, rb = _rgb(ba), _rgb(bb)
            return tuple(int(round(ra[i] + (rb[i] - ra[i]) * t)) for i in range(3))
    return _rgb(LESTVICA[-1][1])


def modra_v_safeer(r: int, g: int, b: int) -> tuple:
    """Mintova modra #0c75de (svetlost 0,46) -> #8ac7ff (0,77); temnejsi in svetlejsi odtenki sorazmerno ob njem."""
    _h, l, _s = colorsys.rgb_to_hls(r / 255.0, g / 255.0, b / 255.0)
    h0, l0, s0 = colorsys.rgb_to_hls(*(c / 255.0 for c in POUDAREK))
    nova = max(0.50, min(0.93, l0 + (l - 0.46) * 0.55))
    return tuple(int(round(c * 255)) for c in colorsys.hls_to_rgb(h0, nova, s0))


def preslikaj(r: int, g: int, b: int):
    """Nova barva ali None, ce barva ostane (crna, bela, rdeca, zelena ...)."""
    if je_siva(r, g, b):
        svetlost = (r + g + b) // 3
        if svetlost <= 4 or svetlost >= 250:
            return None
        return siva_v_safeer(svetlost)
    if je_mintova_modra(r, g, b):
        return modra_v_safeer(r, g, b)
    return None


def je_rob(ime: str) -> bool:
    return ime.startswith("border") or ime in ("box-shadow", "outline-color", "outline")


def prebarvaj_vrednost(vrednost: str, ime: str = ""):
    """(nova vrednost, ali je bila v njej Mintova modra) ali (None, False), ce ni kaj spremeniti."""
    modra = False
    spremenjeno = False
    rob = je_rob(ime)

    def hex_(m):
        nonlocal modra, spremenjeno
        r, g, b = _rgb(m.group(1))
        if rob and je_siva(r, g, b) and 4 < (r + g + b) // 3 <= ROB_DO:
            spremenjeno = True
            return "#%02x%02x%02x" % ROB
        n = preslikaj(r, g, b)
        if n is None:
            return m.group(0)
        spremenjeno = True
        modra = modra or je_mintova_modra(r, g, b)
        return "#%02x%02x%02x" % n

    def rgba_(m):
        nonlocal modra, spremenjeno
        r, g, b = (min(255, int(m.group(i))) for i in (1, 2, 3))
        if rob and m.group(4) and je_siva(r, g, b) and 4 < (r + g + b) // 3 <= ROB_DO:
            spremenjeno = True
            delez = float(m.group(4).strip(" ,")) * ROB_DELEZ
            return "rgba(%d, %d, %d, %s)" % (ROB_PROSOJEN + (("%.2f" % delez).rstrip("0").rstrip("."),))
        n = preslikaj(r, g, b)
        if n is None:
            return m.group(0)
        spremenjeno = True
        modra = modra or je_mintova_modra(r, g, b)
        return ("rgba(%d, %d, %d%s)" % (n + (m.group(4),))) if m.group(4) else "rgb(%d, %d, %d)" % n

    nova = RGBA.sub(rgba_, HEX.sub(hex_, vrednost))
    return (nova, modra) if spremenjeno else (None, False)


SLIKA_POLJA = re.compile(r"assets/(checkbox|radio)-(checked|unchecked|mixed|selectionmode)(-selectionmode)?(-insensitive)?(-selected|-dark)?(@2)?\.png")
SLIKA_STIKALA = re.compile(r"assets/switch(-active)?(-insensitive)?(-header|-selected)?(-dark)?(@2)?\.png")
#: Selektor, ki se zacne z golim razredom .check/.radio (brez imena gradnika).
GOLI_RAZRED = re.compile(r"^\.(check|radio)(?![\w-])")


def slika_v_css(ime: str, vrednost: str):
    """Lastnosti, ki sliko gradnika iz osnove nadomestijo z risbo v paleti Safeer; None, ce to ni taka slika."""
    m = SLIKA_POLJA.search(vrednost) if ime == "-gtk-icon-source" else None
    if m:
        radio, stanje, izbrano = m.group(1) == "radio", m.group(2), m.group(5) == "-selected"
        if stanje == "selectionmode":
            stanje = "unchecked"
        temna, svetla = NA_POUDARKU, "#8ac7ff"
        polno, znak = (temna, svetla) if izbrano else (svetla, temna)        # v izbrani vrstici je podlaga ze svetlo modra
        rob = temna if izbrano else "rgba(215, 234, 255, 0.45)"
        d = [("border-radius", "100%" if radio else "4px"), ("box-shadow", "none")]
        if stanje == "unchecked":
            d += [("-gtk-icon-source", "none"), ("min-width", "14px"), ("min-height", "14px"), ("border", "1px solid " + rob),
                  ("background-color", "transparent" if izbrano else "#0f1a2a"), ("color", "transparent")]
        elif radio and stanje == "checked":
            # Krog v barvi poudarka s temno piko (krozni preliv): enaka velikost kot prazen, brez slike in brez ikone.
            d += [("-gtk-icon-source", "none"), ("min-width", "14px"), ("min-height", "14px"), ("border", "1px solid " + polno),
                  ("background-color", polno),
                  ("background-image", "radial-gradient(circle closest-side, %s 0%%, %s 34%%, %s 46%%)" % (znak, znak, polno)),
                  ("color", "transparent")]
        else:
            ikona = "object-select-symbolic" if stanje == "checked" else "list-remove-symbolic"
            d += [("-gtk-icon-source", '-gtk-icontheme("%s")' % ikona), ("min-width", "14px"), ("min-height", "14px"),
                  ("border", "1px solid " + polno), ("background-color", polno), ("color", znak)]
        if m.group(4):
            d.append(("opacity", "0.45"))
        return d
    m = SLIKA_STIKALA.search(vrednost) if ime == "background-image" else None
    if m:
        vklopljeno, izbrano = bool(m.group(1)), m.group(3) == "-selected"
        if izbrano:
            barva = NA_POUDARKU if vklopljeno else "rgba(11, 20, 36, 0.35)"
        else:
            barva = "#8ac7ff" if vklopljeno else "rgba(215, 234, 255, 0.18)"
        d = [("background-image", "none"), ("background-color", barva), ("border-radius", "12px")]
        if m.group(2):
            d.append(("opacity", "0.45"))
        return d
    return None


def pravila(css: str):
    """(selektor, telo) za pravila na vrhnji ravni; bloke @keyframes ipd. preskoci."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j == -1:
            return
        globina, k = 1, j + 1
        while k < n and globina:
            globina += 1 if css[k] == "{" else -1 if css[k] == "}" else 0
            k += 1
        selektor = css[i:j].rsplit(";", 1)[-1].strip()
        telo = css[j + 1:k - 1]
        if selektor and not selektor.startswith("@") and "{" not in telo:
            yield " ".join(selektor.split()), telo
        i = k


def lastnosti(telo: str):
    """(ime, vrednost) lastnosti pravila; podpicje v oklepajih (url) ne loci."""
    del_, globina = [], 0
    for znak in telo + ";":
        if znak == "(":
            globina += 1
        elif znak == ")":
            globina = max(0, globina - 1)
        if znak == ";" and globina == 0:
            d = "".join(del_).strip()
            del_ = []
            if ":" in d:
                ime, vrednost = d.split(":", 1)
                yield ime.strip(), " ".join(vrednost.split())
        else:
            del_.append(znak)


def prebarvana_pravila(css: str):
    """(selektor, {lastnost: vrednost}) za vsako pravilo osnove, ki ima kaj za prebarvati - v vrstnem redu osnove."""
    for selektor, telo in pravila(css):
        nove, podlaga_modra, bela_pisava, polje = [], False, None, False
        for ime, vrednost in lastnosti(telo):
            if "url(" in vrednost:
                risba = slika_v_css(ime, vrednost)
                polje = polje or bool(risba and ime == "-gtk-icon-source")
                nove += risba or []
                continue
            if ime == "color" and BELA.match(vrednost):
                bela_pisava = vrednost
            nova, modra = prebarvaj_vrednost(vrednost, ime)
            if nova is None:
                continue
            if modra and ime in ("background", "background-color", "background-image"):
                podlaga_modra = True
            nove.append((ime, nova))
        if podlaga_modra and bela_pisava is not None:
            nove.append(("color", NA_POUDARKU + (" !important" if "!important" in bela_pisava else "")))
        if nove and polje:
            # Goli razred .check/.radio nosijo tudi GUMBI (izbirni gumb v obliki gumba, preklopniki pogledov): risba
            # polja (velikost, rob, prosojna pisava) bi jim skrila napis. Tam ostane Mintovo pravilo (slika se na gumbu
            # ne rise), risbo dobijo samo pravi gradniki (check, radio, treeview.check ...).
            selektor = ", ".join(s for s in (d.strip() for d in selektor.split(",")) if not GOLI_RAZRED.match(s))
            if not selektor:
                continue
        if nove:
            # Osnova isto lastnost veckrat ponovi (rezervna vrednost, slika za gost zaslon): velja zadnja.
            zadnje = {}
            for ime, vrednost in nove:
                zadnje.pop(ime, None)
                zadnje[ime] = vrednost
            yield selektor, zadnje


def zdruzi(seznami) -> list:
    """Unija pravil vec razlicic osnove (od najstarejse do najnovejse). Isti selektor: lastnosti se zdruzijo, vrednost
    iz novejse razlicice prepise starejso. Vrstni red: kot v najnovejsi razlicici, pravila samo iz starejsih na koncu
    (v njihovem vrstnem redu) - tako kaskada ostane taka, kot jo ima vecina uporabnikov."""
    zdruzeno, zaporedja = {}, []
    for seznam in seznami:
        # Osnova isti selektor ponovi na vec mestih: vsaka ponovitev ostane svoje pravilo na svojem mestu.
        stevci, kljuci = {}, []
        for selektor, lastnosti_ in seznam:
            k = stevci.get(selektor, 0)
            stevci[selektor] = k + 1
            zdruzeno.setdefault((selektor, k), {}).update(lastnosti_)
            kljuci.append((selektor, k))
        zaporedja.append(kljuci)
    vrstni_red, videni = [], set()
    for kljuci in reversed(zaporedja):
        for kljuc in kljuci:
            if kljuc not in videni:
                videni.add(kljuc)
                vrstni_red.append(kljuc)
    return [(s, zdruzeno[(s, k)]) for s, k in vrstni_red]


def izpisi(pravila_: list) -> str:
    return "".join("%s {\n%s}\n" % (s, "".join("  %s: %s;\n" % p for p in l.items())) for s, l in pravila_)


def prebarvaj(css: str) -> str:
    return izpisi(list(prebarvana_pravila(css)))


GLAVA = """/* Safeer Cinnamon - {del_}: Mintove sivine in modra v paleti Safeer.
   SAMODEJNO: tools/tema_cinnamon_prebarvaj.py iz Mint-Y-Dark-Blue ({osnove}); {pravil} pravil.
   Ne urejaj rocno - rocna pravila so v {rocna}. Selektorji: Mint-Y (Linux Mint, GPL-3.0). */
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--osnova", action="append", metavar="[OZNAKA=]MAPA",
                   help="mapa teme Mint-Y-Dark-Blue; veckrat, od najstarejse do najnovejse razlicice (oznaka gre v glavo)")
    p.add_argument("--cilj", default=str(CILJ))
    a = p.parse_args()
    osnove = []
    for o in a.osnova or ["/usr/share/themes/Mint-Y-Dark-Blue"]:
        oznaka, _, mapa = o.rpartition("=")
        osnove.append((oznaka or Path(mapa).name, Path(mapa)))
    for del_ in DELI:
        seznami = []
        for oznaka, mapa in osnove:
            vir = mapa / del_
            if not vir.is_file():
                print("ni osnove:", vir, file=sys.stderr)
                return 1
            seznami.append(list(prebarvana_pravila(vir.read_text(encoding="utf-8"))))
        skupaj = zdruzi(seznami)
        cilj = Path(a.cilj) / Path(del_).parent / "prebarvano.css"
        cilj.parent.mkdir(parents=True, exist_ok=True)
        cilj.write_text(GLAVA.format(del_=Path(del_).parent, osnove=", ".join(o for o, _ in osnove), pravil=len(skupaj),
                                     rocna=Path(del_).name) + izpisi(skupaj), encoding="utf-8")
        print("%s: %d pravil (%s), %d bajtov" % (cilj, len(skupaj), " + ".join(str(len(s)) for s in seznami), cilj.stat().st_size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
