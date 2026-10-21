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


def _nastavi_ce_drugacna(ime: str, vrednost: str) -> None:
    """Ponovni klic (Control, uvozen v procesu Safeer OS, kjer ze tecejo niti) da isto vrednost: brez setenv
    (core/okolje_procesa.py)."""
    if os.environ.get(ime) != vrednost:
        os.environ[ime] = vrednost


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
    _nastavi_ce_drugacna("GI_TYPELIB_PATH", os.pathsep.join([typelibi] + poti))
    # Pred prvim zagonom GStreamerja in spletnega procesa: vticnik GStreamer bere poti ob Gst.init.
    vticniki = os.path.join(mapa, GST_VTICNIKI)
    if os.path.isdir(vticniki):
        poti = [p for p in os.environ.get("GST_PLUGIN_PATH", "").split(os.pathsep) if p and p != vticniki]
        _nastavi_ce_drugacna("GST_PLUGIN_PATH", os.pathsep.join(poti + [vticniki]))
    rangi = rangi_brez_xml(mapa, os.environ.get("GST_PLUGIN_FEATURE_RANK", ""))
    if rangi is not None:
        _nastavi_ce_drugacna("GST_PLUGIN_FEATURE_RANK", rangi)
    return mapa


#: Elementi GStreamer, katerih vticniki so povezani s sistemskim libxml2 (Linux Mint 23 / Ubuntu 26.04: libxml2.so.16;
#: izmerjeno 21. 10. 2026: adaptivedemux2, dash, smoothstreaming, ttmlsubs). Paket ima svoj libxml2.so.2 (vgradi.sh,
#: prenosnost .deb); ce sistemski NI ISTE RAZLICICE (ali ga ni ali ni dolocljiva), bi vticnik v spletnem procesu svoje
#: nepoimenovane simbole libxml2 razresil na nasega (drug ABI) - sesutje (neodvisni pregled Gemini 1.0.131, VISOKA).
#: Primerjamo po razlicici (vgradi.sh zapise v share/doc/vgrajene/libxml2/razlicica realno ime npr. libxml2.so.2.9.14),
#: ne po SHA-256 (ta je po patchelf --set-rpath '$ORIGIN' vedno drugacen). Z rangom NONE jih samodejno sestavljanje
#: ne izbere; HLS prevzame hlsdemux (vticnik hls, brez libxml2 - preverjeno na Mint 23), DASH/MSS brez MSE in TTML
#: brskalniki tudi sicer ne predvajajo.
XML_ELEMENTI = ("dashdemux2", "hlsdemux2", "mssdemux2", "dashdemux", "mssdemux", "ttmlparse", "ttmlrender")
SISTEMSKI_LIBXML2 = "/usr/lib/x86_64-linux-gnu/libxml2.so.2"


def _vgrajena_razlicica_xml(mapa: str) -> Optional[str]:
    """Realno ime vgrajene knjiznice libxml2 (npr. libxml2.so.2.9.14) iz share/doc/vgrajene/libxml2/razlicica ali None."""
    pot = os.path.join(mapa, "share", "doc", "vgrajene", "libxml2", "razlicica")
    try:
        with open(pot, "r", encoding="utf-8") as f:
            v = f.read().strip()
            return v if v else None
    except OSError:
        return None


def _ista_razlicica_xml(mapa: str, sistemski: str) -> bool:
    """Ali je sistemski libxml2.so.2 iste razlicice kot vgrajeni v paketu safeer-webkit.

    Najpreprostejse zanesljivo (21. 10. 2026): brez nalaganja knjiznice v proces primerjamo realno ime
    datoteke sistemske povezave (os.path.realpath) z imenom, ki ga je vgradi.sh zapisal v
    share/doc/vgrajene/libxml2/razlicica (npr. libxml2.so.2.9.14). SHA-256 ni primeren, ker patchelf spremeni
    vgrajeno datoteko. Ce sistemske knjiznice ni ali razlicice ni mogoce dolociti, vrne False (varna stran - izklop)."""
    try:
        if not os.path.isfile(sistemski):
            return False
        vgrajena = _vgrajena_razlicica_xml(mapa)
        if not vgrajena:
            return False
        sistemska = os.path.basename(os.path.realpath(sistemski))
        return sistemska == vgrajena
    except OSError:
        return False


def rangi_brez_xml(mapa: str, obstojeci: str, sistemski: str = SISTEMSKI_LIBXML2) -> Optional[str]:
    """Nova vrednost GST_PLUGIN_FEATURE_RANK (XML_ELEMENTI z rangom NONE) ali None, ce ni potrebna: paket nima svojega
    libxml2 ali je sistemski iste razlicice (Linux Mint 22: isti libxml2.so.2.9.14). Obstojece nastavitve ostanejo."""
    nas = os.path.join(mapa, "lib", "libxml2.so.2")
    if not os.path.isfile(nas) or _ista_razlicica_xml(mapa, sistemski):
        return None
    deli = [d for d in obstojeci.split(",") if d.strip()]
    imena = {d.split(":", 1)[0].strip() for d in deli}
    return ",".join(deli + [f"{e}:NONE" for e in XML_ELEMENTI if e not in imena])


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
    # Rangi, ki jih je nastavi() dodal zaradi nasega libxml2, ne veljajo za sistemske programe (npr. predvajalnik s
    # sistemskim libxml2 naj DASH predvaja).
    rangi = okolje.get("GST_PLUGIN_FEATURE_RANK")
    if rangi is not None:
        nasi = {f"{e}:NONE" for e in XML_ELEMENTI}
        ostanek = [d for d in rangi.split(",") if d.strip() and d.strip() not in nasi]
        if ostanek:
            okolje["GST_PLUGIN_FEATURE_RANK"] = ",".join(ostanek)
        else:
            del okolje["GST_PLUGIN_FEATURE_RANK"]
    if okolje.get("APPIMAGE"):
        for ime in SAMO_APPIMAGE:
            okolje.pop(ime, None)
    # Izklop peskovnika WebKita, ki ga je ta proces dal sebi (core/peskovnik_userns.py), ne velja za druge programe.
    from core import okolje_procesa, peskovnik_userns
    return okolje_procesa.prazne_rezervacije(peskovnik_userns.okolje_brez_izklopa(okolje))


def gio_v_procesu():
    """Gio tega procesa za privzete programe namizja (vrsta vsebine, privzeti program, zagon) - isti klici, kot jih naredita
    `gio` in `xdg-open`/`xdg-mime` na Cinnamonu in GNOME (g_app_info_*), brez lupinske skripte in podprocesa (lastnik,
    19. 10. 2026: Omarchy je iskanje privzetega brskalnika z xdg-settings skrajsal z ~72 na ~10 ms). None v Flatpaku
    (programi racunalnika so vidni samo prek flatpak-spawn) in v AppImage (XDG_DATA_DIRS tega procesa ima $APPDIR,
    zunanji ukaz pa tece z okoljem racunalnika) - tam ostane zunanji ukaz."""
    if os.environ.get("FLATPAK_ID") or os.environ.get("APPIMAGE"):
        return None
    try:
        import gi
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio
        return Gio
    except (ImportError, ValueError):
        return None


def odpri_privzeto(pot: str) -> bool:
    """Datoteko ali mapo odpre privzeti program namizja v tem procesu: g_app_info_launch_default_for_uri, kot `gio open`
    (to na Cinnamonu klice xdg-open) - z okoljem okolje_za_zunanje(). False, ce tu ne gre (Flatpak, AppImage, ni programa
    za to vrsto, napaka): klicatelj takrat uporabi rezervo (xdg-open, gio open)."""
    Gio = gio_v_procesu()
    if Gio is None:
        return False
    try:
        return bool(Gio.AppInfo.launch_default_for_uri(Gio.File.new_for_path(pot).get_uri(), kontekst_za_zunanje(Gio)))
    except Exception:  # noqa: BLE001 - GLib.Error (ni privzetega programa) ali drugo: rezerva
        return False


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
