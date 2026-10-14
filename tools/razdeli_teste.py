#!/usr/bin/env python3
"""Razdeli preizkuse na tiste za GTK 4 (Safeer OS, Safeer Control) in ostale (brskalnik GTK 3, brez GTK).

GTK 3 in GTK 4 ne moreta biti nalozena v istem procesu Python (gi: »Namespace Gtk is already loaded with version
3.0«). CI zato pozene vsako skupino v svojem procesu - in na svojem sistemu: brskalnik (GTK 3) na Ubuntu 22.04,
Safeer OS (GTK 4, WebKitGTK 6.0) na Ubuntu 24.04. Izmerjeno 14. 10. 2026: v enem procesu je padlo 94 preizkusov.

Skupina se doloci iz uvozov (ast), brez izvajanja kode:
  * modul je GTK 4, ce na ravni modula zahteva Gtk 4.0 ali ce je safeer_os.py / safeer_control.py;
  * modul je GTK 3, ce na ravni modula zahteva Gtk 3.0;
  * preizkus spada v skupino, do katere pridejo njegovi uvozi (v preizkusu katerikoli, v modulih tisti na ravni
    modula - prehodno). Preizkus, ki doseze obe skupini, je napaka (izpis na stderr, izhodna koda 2).

Uporaba: python3 tools/razdeli_teste.py gtk3|gtk4   -> imena modulov (test_x) za `python3 -m unittest`.
"""
import ast
import os
import re
import sys

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GTK4_DATOTEKE = {"safeer_os", "safeer_control"}


def _ime_modula(pot: str) -> str:
    rel = os.path.relpath(pot, KOREN)[:-3]
    return rel.replace(os.sep, ".")


def _moduli() -> dict:
    """ime -> pot za vse .py v korenu, core/ in podpaketih core."""
    izid = {}
    for ime in os.listdir(KOREN):
        if ime.endswith(".py"):
            izid[ime[:-3]] = os.path.join(KOREN, ime)
    for mapa, _, datoteke in os.walk(os.path.join(KOREN, "core")):
        if "__pycache__" in mapa:
            continue
        for d in datoteke:
            if d.endswith(".py"):
                p = os.path.join(mapa, d)
                izid[_ime_modula(p)] = p
    return izid


def _zahteva(vozel) -> str:
    """"4" / "3", ce je vozel klic gi.require_version("Gtk", "x.0")."""
    if isinstance(vozel, ast.Call) and getattr(vozel.func, "attr", "") == "require_version" and len(vozel.args) >= 2:
        a, b = vozel.args[0], vozel.args[1]
        if isinstance(a, ast.Constant) and a.value == "Gtk" and isinstance(b, ast.Constant) and isinstance(b.value, str):
            return b.value[:1]
    return ""


def _na_ravni_modula(drevo):
    """Vozli na ravni modula (tudi znotraj try/if na ravni modula), ne v funkcijah in razredih."""
    sklad = list(drevo.body)
    while sklad:
        v = sklad.pop()
        if isinstance(v, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield v
        for polje in ("body", "orelse", "finalbody", "handlers"):
            sklad.extend(getattr(v, polje, []) or [])
        if isinstance(v, (ast.Expr, ast.Assign)):
            yield from ast.walk(v)


def _uvozi(vozli, ime_modula: str, moduli: dict) -> set:
    izid = set()
    for v in vozli:
        if isinstance(v, ast.Import):
            for a in v.names:
                if a.name in moduli:
                    izid.add(a.name)
        elif isinstance(v, ast.ImportFrom):
            if v.level:
                osnova = ".".join(ime_modula.split(".")[:-v.level]) if v.level <= ime_modula.count(".") else ""
                mod = (osnova + "." + v.module) if v.module and osnova else (v.module or osnova)
            else:
                mod = v.module or ""
            if mod in moduli:
                izid.add(mod)
            for a in v.names:
                if (mod + "." + a.name) in moduli:
                    izid.add(mod + "." + a.name)
    return izid


def razdeli() -> tuple:
    moduli = _moduli()
    drevesa = {}
    for ime, pot in moduli.items():
        try:
            with open(pot, encoding="utf-8") as f:
                drevesa[ime] = ast.parse(f.read())
        except (SyntaxError, UnicodeDecodeError, OSError):
            drevesa[ime] = ast.parse("")
    lastno, sosedje = {}, {}
    for ime, d in drevesa.items():
        vozli = list(_na_ravni_modula(d))
        z = {_zahteva(v) for v in vozli} - {""}
        lastno[ime] = "4" if ime in GTK4_DATOTEKE or "4" in z else ("3" if "3" in z else "")
        sosedje[ime] = _uvozi(vozli, ime, moduli)

    pomnjeno = {}

    def doseze(ime, videno=None):
        if ime in pomnjeno:
            return pomnjeno[ime]
        videno = videno or set()
        if ime in videno:
            return set()
        videno.add(ime)
        izid = {lastno[ime]} - {""}
        for s in sosedje.get(ime, ()):
            izid |= doseze(s, videno)
        pomnjeno[ime] = izid
        return izid

    gtk3, gtk4, oboje = [], [], []
    mapa = os.path.join(KOREN, "tests")
    for d in sorted(os.listdir(mapa)):
        if not (d.startswith("test_") and d.endswith(".py")):
            continue
        with open(os.path.join(mapa, d), encoding="utf-8") as f:
            besedilo = f.read()
        drevo = ast.parse(besedilo)
        skupine = set()
        # Preizkus, ki Safeer OS ali Control uvozi v podprocesu (koda v nizu), potrebuje GTK 4 na sistemu.
        if re.search(r"import (safeer_os|safeer_control)\b", besedilo):
            skupine.add("4")
        for u in _uvozi(list(ast.walk(drevo)), "tests." + d[:-3], moduli):
            skupine |= doseze(u)
        # Preizkus, ki sam na ravni modula zahteva Gtk (gi.require_version("Gtk", "4.0")), spada v tisto skupino.
        skupine |= {_zahteva(v) for v in _na_ravni_modula(drevo)} - {""}
        ime = d[:-3]
        if skupine == {"3", "4"}:
            oboje.append(ime)
        (gtk4 if "4" in skupine else gtk3).append(ime)
    return gtk3, gtk4, oboje


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("gtk3", "gtk4"):
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        sys.exit(1)
    g3, g4, oboje = razdeli()
    for ime in oboje:
        print("preizkus %s uvaza GTK 3 in GTK 4 hkrati" % ime, file=sys.stderr)
    print(" ".join(g3 if sys.argv[1] == "gtk3" else g4))
    sys.exit(2 if oboje else 0)
