"""Preizkus namescenega GTK4 brskalnika (safeer_brskalnik.py) v paketu: .deb, AppImage in Flatpak.

Uporaba: python3 smoke_brskalnik.py POT_DO_TOVORA   (npr. /usr/lib/safeer-browser ali /app/lib/safeer-browser)

Preveri, kar uporabnik potrebuje takoj po namestitvi: stran prek HTTP se izrise, prenos zapise tocne bajte v mapo
prenosov, nastavitve ostanejo, WebKitGTK 6.0 je v Flatpaku nas (/app, packaging/webkit) in Safeer DRM se vstavi v okno
brskalnika (X11). Namesto pravega Safeer DRM (v paketu, ~280 MB) tece nadomestni program z istim vmesnikom
(--parent, --state ... in dogodek WINDOW_HANDLE), zagnan po isti poti kot pravi: v Flatpaku (od 1.0.127) v peskovniku
brskalnika prek zypak-wrapper, nikoli na gostitelju. V Flatpaku preveri se, da brskalnik ne more na gostitelja in da
povezave drugim programom (mailto: ...) gredo portalu (Gtk.UriLauncher). Vsi podatki so v zacasni mapi.
"""
import ctypes
import json
import os
import pathlib
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

V_FLATPAKU = os.path.exists("/.flatpak-info")
DOM = tempfile.mkdtemp(prefix="safeer-smoke-")
os.environ.update(HOME=DOM, XDG_CONFIG_HOME=os.path.join(DOM, ".config"), XDG_DATA_HOME=os.path.join(DOM, ".local", "share"),
                  XDG_CACHE_HOME=os.path.join(DOM, ".cache"))
nastavitve = pathlib.Path(DOM, ".config", "safeer-mint")
nastavitve.mkdir(parents=True)
(nastavitve / "settings.json").write_text(json.dumps({
    "first_run_completed": True, "check_default_browser": False, "sidebar_enabled": False, "doh_enabled": False,
    "session_restore": False}))

LIB = os.path.abspath(sys.argv[1])
sys.path.insert(0, LIB)
import safeer_brskalnik as B  # noqa: E402
from gi.repository import GLib  # noqa: E402
from core import safeer_drm, splet_prenosi  # noqa: E402
from core.config import ConfigManager  # noqa: E402

WebKit = B.WebKit2
VSEBINA = b"Safeer download fixture"
NASLOV = "Safeer packaging smoke"


class Streznik(BaseHTTPRequestHandler):
    def log_message(self, *_a):
        pass

    def do_GET(self):
        self.send_response(200)
        if self.path == "/download":
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", 'attachment; filename="smoke.txt"')
            telo = VSEBINA
        else:
            self.send_header("Content-Type", "text/html")
            telo = ("<html><head><title>%s</title></head><body>Safeer</body></html>" % NASLOV).encode()
        self.end_headers()
        self.wfile.write(telo)


streznik = ThreadingHTTPServer(("127.0.0.1", 0), Streznik)
threading.Thread(target=streznik.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:%d/" % streznik.server_port

# Nadomestni Safeer DRM: ustvari X okno, sporoci WINDOW_HANDLE in caka, da ga brskalnik vstavi in ustavi.
NADOMESTNI_DRM = r'''#!/usr/bin/env python3
import ctypes, json, sys, time
a = dict(x[2:].split("=", 1) for x in sys.argv[1:] if x.startswith("--") and "=" in x)
X = ctypes.cdll.LoadLibrary("libX11.so.6")
X.XOpenDisplay.restype = ctypes.c_void_p; X.XOpenDisplay.argtypes = [ctypes.c_char_p]
X.XDefaultRootWindow.restype = ctypes.c_ulong; X.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
X.XCreateSimpleWindow.restype = ctypes.c_ulong
X.XCreateSimpleWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong] + [ctypes.c_int] * 2 + [ctypes.c_uint] * 3 + [ctypes.c_ulong] * 2
X.XMapWindow.argtypes = [ctypes.c_void_p, ctypes.c_ulong]; X.XFlush.argtypes = [ctypes.c_void_p]
d = X.XOpenDisplay(None)
with open(a["state"], "a") as f:
    if not d:
        f.write(json.dumps({"type": "SMOKE_NO_DISPLAY"}) + "\n"); sys.exit(3)
    w = X.XCreateSimpleWindow(d, X.XDefaultRootWindow(d), 0, 0, 320, 200, 0, 0, 0)
    X.XMapWindow(d, w); X.XFlush(d)
    f.write(json.dumps({"type": "WINDOW_HANDLE", "detail": str(w)}) + "\n")
for _ in range(600):
    time.sleep(0.1)
'''


class Xlib:
    def __init__(self):
        self.L = L = ctypes.cdll.LoadLibrary("libX11.so.6")
        L.XOpenDisplay.restype = ctypes.c_void_p
        L.XOpenDisplay.argtypes = [ctypes.c_char_p]
        L.XQueryTree.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
                                 ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_void_p),
                                 ctypes.POINTER(ctypes.c_uint)]
        L.XFree.argtypes = [ctypes.c_void_p]
        self.d = L.XOpenDisplay(None)

    def stars(self, okno: int) -> int:
        koren, stars, otroci, n = ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_void_p(), ctypes.c_uint()
        if not self.L.XQueryTree(self.d, okno, ctypes.byref(koren), ctypes.byref(stars), ctypes.byref(otroci),
                                 ctypes.byref(n)):
            return 0
        if otroci.value:
            self.L.XFree(otroci)
        return stars.value


izid = {"stran": False, "prenos": False, "nastavitve": False, "webkit": False, "drm": None, "portal": None,
        "peskovnik": None}
stanje = {"prenos_zacet": False, "drm": None}


def koncaj():
    gost = stanje.get("drm")
    if gost is not None:
        gost.unici()
    app.quit()
    return False


def preveri_webkit():
    v = (WebKit.get_major_version(), WebKit.get_minor_version(), WebKit.get_micro_version())
    with open("/proc/self/maps") as f:
        knjiznice = sorted({v_.split()[-1] for v_ in f if "libwebkitgtk-6.0" in v_})
    print("WebKitGTK %d.%d.%d" % v, knjiznice, flush=True)
    # V Flatpaku mora biti nas WebKit (/app), ne tisti iz runtime-a org.gnome.Platform; v paketu .deb z nasim WebKitom
    # (packaging/webkit-deb) iz /usr/lib/safeer-browser/webkit, tudi ce je namescen sistemski WebKitGTK 6.0.
    from core import zasebni_webkit
    predpona = None if V_FLATPAKU else zasebni_webkit.predpona(LIB)
    if predpona:
        print("nas WebKit .deb:", predpona, flush=True)
    izid["webkit"] = bool(knjiznice) and (not V_FLATPAKU or all(k.startswith("/app/") for k in knjiznice)) \
        and (not predpona or all(k.startswith(predpona + "/") for k in knjiznice))


def preveri_peskovnik():
    """Flatpak: brez dovoljenja org.freedesktop.Flatpak, Safeer DRM prek zypaka v peskovniku."""
    if not V_FLATPAKU:
        return
    from core import gostitelj
    ukaz = safeer_drm.ukaz_zagona(["/x/safeer-drm", "--url=https://a.test/"])
    with open("/.flatpak-info", encoding="utf-8") as f:
        info = f.read()
    izid["peskovnik"] = (gostitelj.v_peskovniku() and not gostitelj.sme_na_gostitelja()
                         and "org.freedesktop.Flatpak=" not in info and not os.path.exists("/app/host-bin")
                         and ukaz is not None and ukaz[0] == "/app/bin/zypak-wrapper" and "flatpak-spawn" not in ukaz)
    print("peskovnik:", izid["peskovnik"], "ukaz Safeer DRM:", ukaz, flush=True)


def preveri_portal():
    """mailto: s strani: vprasanje Safeerja, nato Gtk.UriLauncher (v Flatpaku portal OpenURI), brez iskanja programa
    na gostitelju. UriLauncher zamenjamo z zapisovalnikom, da se v CI ne odpre nic."""
    splet = app.splet
    zapis = {"vprasanje": None, "launch": None}

    class Zaganjalnik:
        def __init__(self, uri):
            self.uri = uri

        def launch(self, okno, preklic, povratni, podatki):
            zapis["launch"] = self.uri

    class GtkZapis:
        def __getattr__(self, ime):
            return Zaganjalnik_razred if ime == "UriLauncher" else getattr(pravi_gtk, ime)

    class Zaganjalnik_razred:
        @staticmethod
        def new(uri):
            return Zaganjalnik(uri)

    pravi_gtk, pravi_vprasaj = splet.Gtk, splet._vprasaj

    def vprasaj(naslov, opis, gumbi, odgovor=None):
        zapis["vprasanje"] = naslov
        if odgovor:
            odgovor(1)        # »Odpri program«
    splet.Gtk, splet._vprasaj = GtkZapis(), vprasaj
    try:
        splet._zunanji_program("mailto:smoke@safeer.test", "mailto", "https://stran.safeer.test/", True)
    finally:
        splet.Gtk, splet._vprasaj = pravi_gtk, pravi_vprasaj
    from core.i18n import TRANSLATIONS
    vprasanja = {j["external_app_portal_title"].format(scheme="mailto") for j in TRANSLATIONS.values()}
    izid["portal"] = zapis["launch"] == "mailto:smoke@safeer.test" and zapis["vprasanje"] in vprasanja
    print("portal:", zapis, izid["portal"], flush=True)


def prenos_koncan(_prenos):
    pot = pathlib.Path(splet_prenosi.mapa_prenosov(GLib)) / "smoke.txt"
    izid["prenos"] = pot.is_file() and pot.read_bytes() == VSEBINA
    print("prenos:", pot, izid["prenos"], flush=True)
    app.splet.config.set("packaging_smoke_marker", "persistent")
    izid["nastavitve"] = ConfigManager().get("packaging_smoke_marker") == "persistent"
    preveri_peskovnik()
    if V_FLATPAKU:
        preveri_portal()
    zacni_drm()


def zacni_drm():
    """Safeer DRM po isti poti kot v Spletu (core/safeer_drm.Gostitelj), z nadomestnim programom."""
    from gi.repository import Gdk, Gtk
    if not os.path.isfile(os.path.join(LIB, "assets", "safeer_drm", "main.js")):
        print("FAIL: assets/safeer_drm/main.js ni v tovoru", flush=True)
        izid["drm"] = False
        return koncaj()
    try:
        import gi
        gi.require_version("GdkX11", "4.0")
        from gi.repository import GdkX11
        x11 = isinstance(Gdk.Display.get_default(), GdkX11.X11Display)
    except (ImportError, ValueError):
        x11 = False
    if not x11:
        print("DRM: zaslon ni X11 - vstavitev ni mogoca, Safeer DRM bi se odprl v svojem oknu (preskoceno)", flush=True)
        return koncaj()
    # Pravi Safeer DRM je od 1.0.127 v paketu (<tovor>/safeer-drm; preizkus z Widevine: smoke_drm_peskovnik.py). Tu tece
    # nadomestni program v enaki postavitvi, podan s SAFEER_DRM_MAPA.
    pravi = safeer_drm.vgrajena_mapa()
    print("Safeer DRM v paketu:", pravi if (pravi / "safeer-drm").is_file() else "ni (gradnja brez SAFEER_DRM_TOVOR)",
          flush=True)
    mapa = pathlib.Path(DOM, "safeer-drm-nadomestni")
    mapa.mkdir(parents=True, exist_ok=True)
    exe = mapa / "safeer-drm"
    exe.write_text(NADOMESTNI_DRM)
    exe.chmod(0o755)
    os.environ[safeer_drm.SPREMENLJIVKA_MAPE] = str(mapa)
    okno = Gtk.Window(title="Safeer DRM smoke")
    okno.set_default_size(640, 400)
    gost = safeer_drm.Gostitelj(Gtk, Gdk, GLib)
    okno.set_child(gost.gradnik)
    okno.present()
    stanje["drm"] = gost

    def ko_je_okno():
        if not gost.zacni("https://drm.safeer.test/"):
            print("FAIL: Safeer DRM se ni zagnal", flush=True)
            izid["drm"] = False
            return koncaj()
        GLib.timeout_add(200, preveri_drm, okno, Xlib(), [0])
        return False
    GLib.timeout_add(500, ko_je_okno)


def preveri_drm(okno, x, stevec):
    gost = stanje["drm"]
    stevec[0] += 1
    try:
        with open(gost.stanje or os.devnull) as f:
            if "SMOKE_NO_DISPLAY" in f.read():
                print("FAIL: Safeer DRM ni dobil zaslona (DISPLAY)", flush=True)
                izid["drm"] = False
                return koncaj()
    except OSError:
        pass
    if gost._okno:
        from gi.repository import GdkX11  # noqa: F401
        vrh = okno.get_surface().get_xid()
        stars = x.stars(gost._okno)
        izid["drm"] = stars == vrh
        print("DRM: okno 0x%x vstavljeno v 0x%x (vrhnje okno 0x%x): %s" % (gost._okno, stars, vrh, izid["drm"]), flush=True)
        return koncaj()
    if stevec[0] > 75 or gost.proces is None:
        print("FAIL: Safeer DRM ni sporocil okna (proces %s)" % (gost.proces.poll() if gost.proces else "koncan"), flush=True)
        izid["drm"] = False
        return koncaj()
    return True


def korak():
    splet = app.splet
    pogled = splet.trenutni() if splet is not None else None
    if pogled is not None and not stanje["prenos_zacet"] and pogled.get_title() == NASLOV:
        izid["stran"] = True
        preveri_webkit()
        stanje["prenos_zacet"] = True
        prenos = splet.seja.download_uri(URL + "download")
        prenos.connect("finished", prenos_koncan)
        prenos.connect("failed", lambda _p, e: (print("FAIL: prenos:", e.message, flush=True), koncaj()))
    return not stanje["prenos_zacet"]


def cas_potekel():
    pogled = app.splet.trenutni() if app.splet is not None else None
    print("FAIL: cas je potekel; naslov=%r izid=%r" % (pogled.get_title() if pogled else None, izid), flush=True)
    izid["potekel"] = True
    return koncaj()


app = B.SafeerBrskalnik()
GLib.timeout_add(200, korak)
GLib.timeout_add_seconds(90, cas_potekel)
app.run([sys.argv[0], URL])
streznik.shutdown()
print("izid:", izid, flush=True)
ok = (not izid.get("potekel") and izid["stran"] and izid["prenos"] and izid["nastavitve"] and izid["webkit"]
      and izid["drm"] is not False and (not V_FLATPAKU or (izid["peskovnik"] and izid["portal"])))
if ok:
    print("PASS: GTK4 brskalnik je izrisal stran, prenesel tocne bajte, ohranil nastavitve%s" %
          (" in vstavil Safeer DRM" if izid["drm"] else ""), flush=True)
import shutil  # noqa: E402
shutil.rmtree(DOM, ignore_errors=True)
raise SystemExit(0 if ok else 1)
