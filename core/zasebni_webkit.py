"""Nas WebKitGTK in libsoup v paketu .deb (lastnik, 15. 10. 2026: .deb ima isti hitri WebKit kot Flatpak).

WebKitGTK 6.0 in libsoup 3 s popravki Safeerja (packaging/webkit-deb) sta v paketu safeer-webkit v zasebni predponi
/usr/lib/safeer-webkit - nikoli namesto sistemskih knjiznic Ubuntuja. Paketa safeer-os in safeer-browser ga zahtevata
(lastnik, 19. 10. 2026: ena kopija namesto dveh - ko teceta oba programa, si delita strani kode WebKita). Predpona je
mapa safeer-webkit ob mapi programa (/usr/lib/safeer-os -> /usr/lib/safeer-webkit); iz izvorne mape (razvoj) je ni, zato
tam ostane WebKit sistema, kot doslej. Mapa webkit v mapi programa (paketi do 1.0.127~pred, razvoj) ima prednost.
Knjiznice najdejo druga drugo prek DT_RPATH, typelibi imajo absolutno pot do knjiznic (packaging/webkit-deb/typelibi.py);
Python mora le vedeti, kje so typelibi. nastavi() zato pred `import gi` doda PREDPONA/lib/girepository-1.0 na zacetek
GI_TYPELIB_PATH.

Paket ima v PREDPONA/lib/gstreamer-1.0 tudi dekoder AV1 dav1ddec (gst-plugins-rs, packaging/webkit-deb/dav1d.sh):
noble ima libdav1d7, nima pa vticnika GStreamer zanj - brez njega AV1 (YouTube) dekodira pocasni libaom av1dec.
nastavi() mapo doda na konec GST_PLUGIN_PATH (obstojeca vrednost ostane), WebKit jo poda spletnemu procesu v peskovniku
(lastnik, 18. 10. 2026: YouTube AV1 720p z dav1ddec 0 izpuscenih slicic in ~12 % manj CPU kot av1dec).

Spremenljivki ostaneta v okolju nasega procesa: WebKit ju poda svojim procesom (dav1ddec v spletnem procesu), programi,
ki jih Safeer zazene sam (Safeer Control iz Safeer OS, ponovni zagon, pomozni procesi), pa dobijo isti WebKit.
LD_LIBRARY_PATH se ne nastavlja. V Flatpaku in AppImage nastavi() ne naredi nicesar - tam je WebKit v /app oziroma v
AppImage (AppRun-os nastavi LD_LIBRARY_PATH, GI_TYPELIB_PATH, PYTHONHOME ... na $APPDIR).

Zunanji programi, ki jih uporabnik odpre iz Safeer OS (programi, datoteke, »Odpri z«, povezave, skripte), nasih
zasebnih poti ne smejo podedovati (lastnik, 18. 10. 2026): sistemski program z GI bi nalozil nas typelib WebKit,
GStreamer nas vticnik, program iz AppImage pa knjiznice AppImage namesto sistemskih. okolje_za_zunanje() in
kontekst_za_zunanje() vrneta okolje brez njih (vse poti v nasi predponi WebKit in v $APPDIR, iz vseh spremenljivk).
"""
from __future__ import annotations

import os
from typing import Mapping, Optional

TYPELIB = os.path.join("lib", "girepository-1.0", "WebKit-6.0.typelib")
GST_VTICNIKI = os.path.join("lib", "gstreamer-1.0")
#: Odtis gradnje skupnega WebKita (packaging/webkit-deb/paket.sh): drug odtis = nova gradnja knjiznic.
ODTIS = os.path.join("share", "webkitgtk-safeer", "odtis")
#: Ime mape skupnega WebKita ob mapah programov (paket safeer-webkit, /usr/lib/safeer-webkit).
SKUPNI = "safeer-webkit"
#: Predpone nasega WebKita v paketih .deb (packaging/webkit-deb): tudi ce je nastavi() klical drug nas proces. Stare
#: (lastna kopija v vsakem paketu, do 1.0.127~pred) ostanejo, ker jih ima lahko v okolju se tekoca starejsa razlicica.
PREDPONE_PAKETOV = ("/usr/lib/safeer-webkit", "/usr/lib/safeer-os/webkit", "/usr/lib/safeer-browser/webkit",
                    "/usr/lib/safeer-control/webkit")
#: Spremenljivke, ki jih postavi zaganjalnik AppImage (runtime in AppRun-os) in ne sodijo v zunanji program.
SAMO_APPIMAGE = ("APPIMAGE", "APPDIR", "ARGV0", "OWD", "SAFEER_PORTABLE", "PYTHONNOUSERSITE")
_nastavljena: Optional[str] = None


def predpona(koren: str) -> Optional[str]:
    """Mapa nasega WebKita za program v mapi koren (npr. /usr/lib/safeer-browser) ali None.

    Najprej koren/webkit (paket z lastno kopijo, razvoj), nato skupni safeer-webkit ob mapi programa: /usr/lib/safeer-os,
    /usr/lib/safeer-control (Safeer Control v paketu safeer-os) in /usr/lib/safeer-browser -> /usr/lib/safeer-webkit."""
    koren = os.path.abspath(koren)
    mape = [os.path.join(koren, "webkit"), os.path.join(os.path.dirname(koren), SKUPNI)]
    for mapa in mape:
        if os.path.isfile(os.path.join(mapa, TYPELIB)):
            return mapa
    return None


def nastavi(koren: str) -> Optional[str]:
    """Klici pred `import gi`. Vrne uporabljeno predpono ali None (Flatpak, AppImage, izvorna koda, ni nasega WebKita)."""
    global _nastavljena
    if os.environ.get("FLATPAK_ID") or os.environ.get("APPIMAGE") or os.environ.get("SAFEER_SISTEMSKI_WEBKIT"):
        return None
    mapa = predpona(koren)
    if mapa is None:
        return None
    _nastavljena = mapa
    typelibi = os.path.join(mapa, "lib", "girepository-1.0")
    poti = [p for p in os.environ.get("GI_TYPELIB_PATH", "").split(os.pathsep) if p and p != typelibi]
    os.environ["GI_TYPELIB_PATH"] = os.pathsep.join([typelibi] + poti)
    # Pred prvim zagonom GStreamerja in spletnega procesa: vticnik GStreamer bere poti ob Gst.init.
    vticniki = os.path.join(mapa, GST_VTICNIKI)
    if os.path.isdir(vticniki):
        poti = [p for p in os.environ.get("GST_PLUGIN_PATH", "").split(os.pathsep) if p and p != vticniki]
        os.environ["GST_PLUGIN_PATH"] = os.pathsep.join(poti + [vticniki])
    return mapa


def pot_odtisa() -> Optional[str]:
    """Datoteka z odtisom gradnje WebKita, ki ga uporablja ta proces (nastavi()), ali None (WebKit sistema, Flatpak,
    AppImage, paket brez odtisa). Safeer OS in Safeer Control jo spremljata (core/nova_razlicica.py): safeer-webkit lahko
    posodobi tudi drug program, medtem ko ta tece s staro knjiznico v pomnilniku."""
    if not _nastavljena:
        return None
    pot = os.path.join(_nastavljena, ODTIS)
    return pot if os.path.isfile(pot) else None


# ---------------------------------------------------------------------------------------- zunanji programi
def _zasebne_mape(okolje: Mapping[str, str]) -> list:
    mape = list(PREDPONE_PAKETOV)
    if _nastavljena:
        mape.append(_nastavljena)
    if okolje.get("APPIMAGE") and okolje.get("APPDIR"):
        mape.append(okolje["APPDIR"])
    return [os.path.normpath(m) for m in mape if m and os.path.isabs(m) and os.path.normpath(m) != os.sep]


def _v_mapi(pot: str, mape: list) -> bool:
    if not os.path.isabs(pot):
        return False
    pot = os.path.normpath(pot)
    return any(pot == m or pot.startswith(m + os.sep) for m in mape)


def okolje_za_zunanje(okolje: Optional[Mapping[str, str]] = None) -> dict:
    """Okolje za program, ki ga odpre uporabnik (ne nas pomozni proces): brez nasih zasebnih poti.

    Iz vsake spremenljivke s seznamom poti (GI_TYPELIB_PATH, GST_PLUGIN_PATH, LD_LIBRARY_PATH, PATH, XDG_DATA_DIRS,
    PYTHONHOME ...) odstrani poti v nasi predponi WebKit in v $APPDIR (AppImage); ce ne ostane nic, spremenljivke ni.
    Uporabnikove poti ostanejo, kot so bile. V Flatpaku ni nic odstranjeno (zunanji programi tecejo na gostitelju)."""
    okolje = dict(os.environ if okolje is None else okolje)
    mape = _zasebne_mape(okolje)
    for ime, vrednost in list(okolje.items()):
        if not vrednost or os.sep not in vrednost:
            continue
        deli = vrednost.split(os.pathsep)
        ostanek = [d for d in deli if not _v_mapi(d, mape)]
        if len(ostanek) == len(deli):
            continue
        ostanek = [d for d in ostanek if d]
        if ostanek:
            okolje[ime] = os.pathsep.join(ostanek)
        else:
            del okolje[ime]
    if okolje.get("APPIMAGE"):
        for ime in SAMO_APPIMAGE:
            okolje.pop(ime, None)
    return okolje


def kontekst_za_zunanje(Gio, kontekst=None):
    """Gio.AppLaunchContext (npr. Gdk.Display.get_app_launch_context()) z okoljem okolje_za_zunanje()."""
    if kontekst is None:
        kontekst = Gio.AppLaunchContext()
    cisto = okolje_za_zunanje()
    for ime in list(os.environ):
        if ime not in cisto:
            kontekst.unsetenv(ime)
    for ime, vrednost in cisto.items():
        if os.environ.get(ime) != vrednost:
            kontekst.setenv(ime, vrednost)
    return kontekst
