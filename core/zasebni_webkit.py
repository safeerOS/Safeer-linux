"""Nas WebKitGTK in libsoup v paketu .deb (lastnik, 15. 10. 2026: .deb ima isti hitri WebKit kot Flatpak).

Paketa safeer-browser in safeer-os imata WebKitGTK 6.0 in libsoup 3 s popravki Safeerja (packaging/webkit-deb) v
zasebni predponi /usr/lib/<paket>/webkit - nikoli namesto sistemskih knjiznic Ubuntuja. Knjiznice najdejo druga drugo
prek DT_RPATH, typelibi imajo absolutno pot do knjiznic (packaging/webkit-deb/typelibi.py); Python mora le vedeti, kje
so typelibi. nastavi() zato pred `import gi` doda PREDPONA/lib/girepository-1.0 na zacetek GI_TYPELIB_PATH.

Spremenljivka ostane v okolju: programi, ki jih Safeer zazene sam (Safeer Control iz Safeer OS, ponovni zagon,
pomozni procesi), dobijo isti WebKit. LD_LIBRARY_PATH se ne nastavlja (prenesel bi se v vse programe, ki jih uporabnik
odpre iz Safeer OS). V Flatpaku in AppImage ne naredi nicesar - tam je WebKit v /app oziroma sistemski.
"""
from __future__ import annotations

import os
from typing import Optional

TYPELIB = os.path.join("lib", "girepository-1.0", "WebKit-6.0.typelib")


def predpona(koren: str) -> Optional[str]:
    """Mapa nasega WebKita za program v mapi koren (npr. /usr/lib/safeer-browser) ali None.

    Safeer Control v paketu safeer-os tece iz /usr/lib/safeer-control in uporabi WebKit paketa safeer-os."""
    koren = os.path.abspath(koren)
    mape = [os.path.join(koren, "webkit")]
    if os.path.basename(koren) == "safeer-control":
        mape.append(os.path.join(os.path.dirname(koren), "safeer-os", "webkit"))
    for mapa in mape:
        if os.path.isfile(os.path.join(mapa, TYPELIB)):
            return mapa
    return None


def nastavi(koren: str) -> Optional[str]:
    """Klici pred `import gi`. Vrne uporabljeno predpono ali None (Flatpak, AppImage, izvorna koda, ni nasega WebKita)."""
    if os.environ.get("FLATPAK_ID") or os.environ.get("APPIMAGE") or os.environ.get("SAFEER_SISTEMSKI_WEBKIT"):
        return None
    mapa = predpona(koren)
    if mapa is None:
        return None
    typelibi = os.path.join(mapa, "lib", "girepository-1.0")
    poti = [p for p in os.environ.get("GI_TYPELIB_PATH", "").split(os.pathsep) if p and p != typelibi]
    os.environ["GI_TYPELIB_PATH"] = os.pathsep.join([typelibi] + poti)
    return mapa
