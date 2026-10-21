#!/usr/bin/env python3
"""Orodje za meritve in preizkuse z nasim WebKitGTK (lastnik, 21. 10. 2026).

Nastavi okolje na nas WebKit (enako kot core/zasebni_webkit.nastavi) in izpise razlicico + pot knjiznice.
Meritve in preizkusi na napravah naj ga uporabljajo namesto rocnega LD_LIBRARY_PATH.

Uporaba:
    python3 tools/nas_webkit.py                       # izpise razlicico in pot nasega WebKita
    python3 tools/nas_webkit.py --export              # izpise export ukaze za shell (eval "$(...)")
    python3 tools/nas_webkit.py <ukaz> [argumenti...]  # zazene ukaz v okolju z nasim WebKitom
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

KOREN = Path(__file__).resolve().parents[1]
if str(KOREN) not in sys.path:
    sys.path.insert(0, str(KOREN))

from core import zasebni_webkit as zw  # noqa: E402


def pripravi_okolje(koren: str = str(KOREN)) -> tuple[dict, Optional[str]]:
    """Pripravi okolje z nasim WebKitom (enako kot nastavi()) in vrne (okolje, predpona)."""
    okolje = dict(os.environ)
    predpona = zw.poisci_nas_webkit(koren)
    if not predpona:
        if okolje.get("FLATPAK_ID"):
            return okolje, "/app"
        if okolje.get("APPDIR"):
            return okolje, okolje["APPDIR"]
        return okolje, None

    okolje["SAFEER_WEBKIT_PREDPONA"] = predpona
    typelibi = os.path.join(predpona, "lib", "girepository-1.0")
    poti = [p for p in okolje.get("GI_TYPELIB_PATH", "").split(os.pathsep) if p and p != typelibi]
    okolje["GI_TYPELIB_PATH"] = os.pathsep.join([typelibi] + poti)

    vticniki = os.path.join(predpona, zw.GST_VTICNIKI)
    if os.path.isdir(vticniki):
        poti = [p for p in okolje.get("GST_PLUGIN_PATH", "").split(os.pathsep) if p and p != vticniki]
        okolje["GST_PLUGIN_PATH"] = os.pathsep.join(poti + [vticniki])

    rangi = zw.rangi_brez_xml(predpona, okolje.get("GST_PLUGIN_FEATURE_RANK", ""))
    if rangi is not None:
        okolje["GST_PLUGIN_FEATURE_RANK"] = rangi

    return okolje, predpona


def ugotovi_webkit(okolje: dict, predpona: Optional[str]) -> tuple[bool, Optional[str], Optional[zw.Razlicica]]:
    """Ugotovi razlicico in pot knjiznice libwebkitgtk-6.0."""
    for k, v in okolje.items():
        if os.environ.get(k) != v:
            os.environ[k] = v

    try:
        import gi
        gi.require_version("WebKit", "6.0")
        from gi.repository import WebKit
    except Exception as e:
        print("[nas_webkit] Uvoz WebKit-6.0 ni uspel:", e, file=sys.stderr)
        return False, None, None

    return zw.preveri_nas_webkit(WebKit=WebKit, predpona=predpona, uveljavi=False)


def main(argv: list[str]) -> int:
    okolje, predpona = pripravi_okolje()

    if argv and argv[0] == "--export":
        for k in ("SAFEER_WEBKIT_PREDPONA", "GI_TYPELIB_PATH", "GST_PLUGIN_PATH", "GST_PLUGIN_FEATURE_RANK"):
            if k in okolje:
                print(f"export {k}={okolje[k]!r}")
        return 0

    if not argv or argv[0] == "--info":
        je_nas, pot, razlicica = ugotovi_webkit(okolje, predpona)
        if not pot:
            print("NAPAKA: libwebkitgtk-6.0 ni bilo mogoce najti v pomnilniku ali okolju.", file=sys.stderr)
            return 1
        oznaka = "nas WebKit" if je_nas else "SISTEMSKI WebKit (opozorilo: ni nas!)"
        print(f"WebKitGTK {razlicica} ({pot}) [{oznaka}]")
        # Vse tri knjiznice (WebKit, JSC, libsoup): meritev s sistemskim libsoup ali mesanim nalaganjem ni veljavna
        # (pregled izdaje 1.0.132, S2).
        try:
            with open("/proc/self/maps", encoding="utf-8", errors="replace") as f:
                nalozene = zw.nalozene_knjiznice(f.read())
        except OSError:
            nalozene = {}
        koren = zw._koren_nasega(predpona)
        for ime in zw.NASE_KNJIZNICE:
            for pot_k in sorted(nalozene.get(ime, ())):
                print(f"  {ime}: {pot_k}" + ("" if koren and zw._pod(pot_k, koren) else "  <- NI NASA"))
        return 0 if je_nas else 2

    # Izvedi ukaz z novim okoljem
    os.execvpe(argv[0], argv, okolje)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
