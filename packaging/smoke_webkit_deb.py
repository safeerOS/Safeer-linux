"""Preizkus nasega WebKitGTK in libsoup v namescenem paketu .deb (packaging/webkit-deb).

Uporaba: python3 smoke_webkit_deb.py KOREN_PROGRAMA     npr. /usr/lib/safeer-browser, /usr/lib/safeer-os, /usr/lib/safeer-control
(vsi trije uporabijo skupni WebKit iz paketa safeer-webkit, /usr/lib/safeer-webkit)

Preveri, kar mora veljati na racunalniku uporabnika (tudi ce je namescen sistemski WebKitGTK 6.0 iz Ubuntuja):
  * core/zasebni_webkit.py najde predpono paketa in Python nalozi typelibe iz nje,
  * /proc/self/maps: libwebkitgtk-6.0, libjavascriptcoregtk-6.0 in libsoup-3.0 so iz predpone, nobena iz sistema,
  * libsoup >= 3.8, WebKitGTK je razlicica iz zapisa gradnje (gradnja.txt: Clang 22, ThinLTO, lld, PGO, BOLT, ta predpona),
    knjiznici libwebkitgtk in libjavascriptcoregtk imata zapis BOLT (.note.bolt_info) optimizacije s profilom,
  * stran prek HTTP se nalozi; spletni proces je WebKitWebProcess iz predpone in tece v peskovniku bubblewrap
    (predhodnik bwrap in lasten imenski prostor PID - NSpid v /proc/<pid>/status),
  * dekoder AV1 dav1ddec (packaging/webkit-deb/dav1d.sh): GStreamer ga v okolju, ki ga nastavi zasebni_webkit, najde v
    predponi z rangom nad drugimi dekoderji AV1; video AV1 v strani se predvaja in proces, ki ga dekodira, ima
    nalozen libgstdav1d.so iz predpone.
Izhod 0 in vrstica PASS, sicer FAIL: ... in izhod 1.
"""
import base64
import ctypes
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

KOREN = os.path.abspath(sys.argv[1])
sys.path.insert(0, KOREN)
from core import zasebni_webkit  # noqa: E402

PREDPONA = zasebni_webkit.nastavi(KOREN)
if not PREDPONA:
    print("FAIL: v %s ni nasega WebKita (core/zasebni_webkit.py)" % KOREN, flush=True)
    raise SystemExit(1)
# Namesceni programi (od 19. 10. 2026) tecejo na skupnem WebKitu iz paketa safeer-webkit, nikoli na ostanku lastne kopije
# starejsega paketa (/usr/lib/<program>/webkit): sicer bi dva programa spet imela vsak svoje strani kode.
if KOREN.startswith("/usr/lib/") and PREDPONA != "/usr/lib/safeer-webkit":
    print("FAIL: %s uporablja %s namesto /usr/lib/safeer-webkit" % (KOREN, PREDPONA), flush=True)
    raise SystemExit(1)

import gi  # noqa: E402
gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
gi.require_version("Soup", "3.0")
from gi.repository import Gio, GLib, Gtk, Soup, WebKit  # noqa: E402

NAPAKE = []
NASLOV = "Safeer WebKit deb smoke"
DAV1D = os.path.join(PREDPONA, "lib", "gstreamer-1.0", "libgstdav1d.so")
# 2 s AV1 (libaom, 96x54, 10 sl./s) v WebM, 1898 B, sha256 972c6817...6952 - vgrajen, ker posel mint v vsebnik
# Linux Minta prenese samo to datoteko.
AV1_WEBM = base64.b64decode("""
GkXfo59ChoEBQveBAULygQRC84EIQoKEd2VibUKHgQJChYECGFOAZwEAAAAAAAc6EU2bdLpNu4tTq4QVSalmU6yBoU27i1OrhBZU
rmtTrIHGTbuMU6uEElTDZ1OsggL+TbuMU6uEHFO7a1Osggck7AEAAAAAAABZAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAVSalmoCrXsYMPQkBNgIRM
YXZmV0GETGF2ZkSJiECfQAAAAAAAFlSua0IyrgEAAAAAAAIp14EBc8WIAAAAAAAAAAGcgQAitZyDdW5kiIEAhoVWX0FWMYOBASPj
g4QF9eEA4ImwgWC6gTaagQJjopCBAAwACgoAAAADLf1Nr5AE7AEAAAAAAAHVAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA
AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABJUw2fUc3PRY8CL
Y8WIAAAAAAAAAAFnyJxFo4dFTkNPREVSRIePTGF2YyBsaWJhb20tYXYxZ8ihRaOIRFVSQVRJT05Eh5MwMDowMDowMi4wMDAwMDAw
MDAAH0O2dUPH54EAo0FbgQAAgAoKAAAAAy39Ta+QBDLIAhQALEBgIIQYsCCg3F1KWNvmm4YAZW2oRzXSw/CaCoD6CblW7FLDUqPd
BSr4Sjo7VC5IZcKB2XIRuWaZoUVp2IcdJZlma4BSPZwssD4AjmiGB4UBbUrylf7Roh/6edot1EPGmEvVxkQo9V+CVBa+dogYWMoK
GSrlOtsFE0Fh6hQzyYOUHA3l9e/3QeGCeRG0pdy40+VK+sApsVw6bDymdqy5+gb5h9pNRERu9juynTUyToJI4bD4/LZCkdapJYG3
UaeM1SbtrRKvUuU0rS26OQc7lV8CTIilh3V8inXM63tetZivOtPXhumvxQksg7geQpkXULmitugAPc/UV+bpkEGW+lIYkLWEpL14
0i8pQhi6OOrFLeMXOnFs/qdvGvRFSDLSRmH0XByTk8eTQTtzq+ksbpKFZ1ZeG7qyfCncyxNiD51zQorf3U6jQLiBAGQAMlYhCfAg
AAABrlBgIIQYsuuIAM9aF9+VJHbHh+27dDKA7EuhUK6aqhkvmxSeecwLp8WsJS1btIMa4JIsOKfSeQhaxJi9GeDrSvKcCAnEU9F8
iqbbr76GkjIZKQTwQAAAQa8AYCCEGLAAFACY81nC7/GPoDIVKQJAgAAgQa+gAABYAA4AoCw9sZdhMhMpAUEAADRBr6AAAFgADgCi
WnFAMhMyAeQAEIyDX+AAALAAHACdLNOAo4eBAMgAGgHIo5eBASwAMhEyAygJQGiDX+AAALAAHACeYKOHgQGQABoBuKOrgQH0ADIS
KQMoA9AqQa9gAABYAA4An7YIMhEyBSQHoOiDX+AAALAAHACfwKOHgQJYABoB+KOYgQK8ADISMgciD1hYg1/AAACwABwApHeAo5eB
AyAAMhEyCAgJ6EyDX+AAALAAHACigKOHgQOEABoBqKPIgQPoADIXKQdAgtB6Qa/QYAALAAHAANVDMJOKRjgyEykFwgLQPkGv4AAA
WAAOAGvwayAyFDIKMAWgrINf4AAAsAAcAHobQ0h1o4eBBEwAGgHYo5eBBLAAMhEyDCIL0HiDX8AAALAAHACrhKOWgQUUADIQMg0I
CXhog1/gAACwABwAp6OHgQV4ABoBuKOqgQXcADISKQhAQ9BeQa/AAABYAA4AXgMIMhAyDzAHoFSDX+AAALAAHACpo4eBBkAAGgGo
o5iBBqQAMhIyESQF2NCDX8AAALAAHABkFxSjloEHCAAyEDISAgq4eINf4AAAsAAcAK6jmIEHbAAyEjITAAlQ7INf4AAAsAAIALmM
gBxTu2uRu4+zgQC3iveBAfGCA1fwgQM=
""")


def napaka(besedilo):
    NAPAKE.append(besedilo)
    print("FAIL:", besedilo, flush=True)


def knjiznice(pid="self"):
    with open("/proc/%s/maps" % pid) as f:
        return sorted({v.split()[-1] for v in f if any(k in v for k in ("libwebkitgtk-6.0", "libjavascriptcoregtk-6.0", "libsoup-3.0"))})


def preveri_knjiznice():
    # GI nalozi knjiznico typeliba sele ob prvem klicu funkcije: razlicici najprej, nato /proc/self/maps.
    soup = (Soup.get_major_version(), Soup.get_minor_version(), Soup.get_micro_version())
    wk = (WebKit.get_major_version(), WebKit.get_minor_version(), WebKit.get_micro_version())
    knj = knjiznice()
    print("predpona:", PREDPONA, flush=True)
    print("knjiznice:", knj, flush=True)
    for ime in ("libwebkitgtk-6.0", "libjavascriptcoregtk-6.0", "libsoup-3.0"):
        poti = [k for k in knj if ime in k]
        if not poti:
            napaka("%s ni nalozena" % ime)
        elif not all(k.startswith(PREDPONA + "/") for k in poti):
            napaka("%s ni iz %s: %s" % (ime, PREDPONA, poti))
    print("libsoup %d.%d.%d, WebKitGTK %d.%d.%d" % (soup + wk), flush=True)
    if soup < (3, 8, 0):
        napaka("libsoup %s < 3.8.0" % (soup,))
    with open(os.path.join(PREDPONA, "share", "webkitgtk-safeer", "gradnja.txt")) as f:
        gradnja = f.read()
    print(gradnja, flush=True)
    for vzorec in ("clang version 22.", "LTO_MODE:", "predpona: %s\n" % PREDPONA, "webkitgtk-%d.%d.%d " % wk):
        if vzorec not in gradnja:
            napaka("gradnja.txt nima %r" % vzorec)
    if "=thin" not in gradnja.split("LTO_MODE:", 1)[-1].split("\n", 1)[0]:
        napaka("gradnja.txt: LTO_MODE ni thin")
    if "build.ninja -fuse-ld=lld: 0" in gradnja:
        napaka("gradnja.txt: ni povezano z lld")
    # Izdaja je s PGO (lastnik, 15. 10. 2026): profil iz ucnega teka te gradnje (packaging/webkit-deb/ucni_tek.sh).
    if "USE_PGO_PROFILE:BOOL=ON\n" not in gradnja or "build.ninja -fprofile-use: 0" in gradnja \
            or "build.ninja -fprofile-use:" not in gradnja:
        napaka("gradnja.txt: WebKit ni preveden s profilom (PGO)")
    # BOLT v izdaji (lastnik, 18. 10. 2026): packaging/webkit-deb/bolt.sh po PGO; nalozeni knjiznici sta optimizirani
    # (zapis .note.bolt_info z --data=, ne instrumentirani z -instrument).
    if "\nbolt: da (" not in gradnja:
        napaka("gradnja.txt: WebKit ni optimiziran z BOLT")
    for pot in knjiznice():
        if "libsoup-3.0" in pot:
            continue
        # bolt.sh: ce BOLT z obema knjiznicama ne uspe, poskusi z eno; druga je v zapisu oznacena (19. 10. 2026).
        if "; %s brez BOLT" % os.path.basename(os.path.realpath(pot)) in gradnja:
            print("OPOZORILO: %s brez BOLT (gradnja.txt)" % pot, flush=True)
            continue
        with open(pot, "rb") as f:
            vsebina = f.read()
        i = vsebina.find(b"BOLT revision")
        zapis = vsebina[i:i + 4096] if i >= 0 else b""
        if not zapis or b"--data=" not in zapis or b"-instrument" in zapis:
            napaka("%s ni optimizirana z BOLT (%r)" % (pot, zapis[:200]))


def preveri_dav1d():
    """dav1ddec v GStreamerju sistema z okoljem programa (GST_PLUGIN_PATH iz zasebni_webkit.nastavi)."""
    vticniki = os.path.dirname(DAV1D)
    print("GST_PLUGIN_PATH:", os.environ.get("GST_PLUGIN_PATH"), flush=True)
    if vticniki not in os.environ.get("GST_PLUGIN_PATH", "").split(os.pathsep):
        napaka("GST_PLUGIN_PATH nima %s" % vticniki)
    if not os.path.isfile(DAV1D):
        napaka("v paketu ni %s" % DAV1D)
        return
    g = ctypes.CDLL("libgstreamer-1.0.so.0")
    g.gst_init(None, None)
    for ime, tip, argumenti in (("gst_element_factory_find", ctypes.c_void_p, [ctypes.c_char_p]),
                                ("gst_plugin_feature_get_rank", ctypes.c_uint, [ctypes.c_void_p]),
                                ("gst_plugin_feature_get_plugin", ctypes.c_void_p, [ctypes.c_void_p]),
                                ("gst_plugin_get_filename", ctypes.c_char_p, [ctypes.c_void_p])):
        getattr(g, ime).restype = tip
        getattr(g, ime).argtypes = argumenti
    rangi = {}
    for ime in (b"dav1ddec", b"av1dec", b"avdec_av1", b"avdec_libdav1d"):
        f = g.gst_element_factory_find(ime)
        if f:
            rangi[ime.decode()] = (g.gst_plugin_feature_get_rank(f),
                                   (g.gst_plugin_get_filename(g.gst_plugin_feature_get_plugin(f)) or b"").decode())
    print("gstreamer AV1:", rangi, flush=True)
    if "dav1ddec" not in rangi:
        napaka("GStreamer ne najde dav1ddec")
        return
    rang, pot = rangi.pop("dav1ddec")
    if pot != DAV1D:
        napaka("dav1ddec ni iz %s: %s" % (DAV1D, pot))
    if any(r >= rang for r, _p in rangi.values()):
        napaka("dav1ddec (rang %d) ni pred drugimi dekoderji AV1: %s" % (rang, rangi))
    print("gstreamer: dav1ddec rang %d iz %s" % (rang, pot), flush=True)
    # Brez gst-plugin-scanner GStreamer ob pregledu nalozi vticnik v ta proces: tak proces ni dokaz predvajanja.
    with open("/proc/self/maps") as f:
        izid["dav1d_prej"] = any("libgstdav1d" in v for v in f)


def preveri_dav1d_v_procesih():
    """Po predvajanju videa AV1: libgstdav1d.so je nalozen v procesu, ki dekodira (spletni ali ta proces)."""
    spletni_berljivi, z_dav1d = 0, []
    potomci = procesi_potomci()
    for pid in ([] if izid["dav1d_prej"] else ["self"]) + [str(p) for p in potomci]:
        try:
            with open("/proc/%s/maps" % pid) as f:
                poti = {v.split()[-1] for v in f if "libgstdav1d" in v}
        except OSError:
            continue
        if pid != "self" and os.path.basename(potomci[int(pid)][0]) == "WebKitWebProcess":
            spletni_berljivi += 1
        if poti:
            z_dav1d.append((pid, sorted(poti)))
    print("gstreamer: libgstdav1d.so v procesih %s (berljivih spletnih procesov %d)" % (z_dav1d, spletni_berljivi), flush=True)
    if z_dav1d and not all(p == [DAV1D] for _pid, p in z_dav1d):
        napaka("libgstdav1d.so ni iz %s: %s" % (DAV1D, z_dav1d))
    elif not z_dav1d and spletni_berljivi:
        napaka("video AV1 se je predvajal, a noben proces nima nalozenega %s" % DAV1D)
    elif not z_dav1d:
        # Maps spletnega procesa v peskovniku ni vedno berljiv (glej preveri_peskovnik): ostane preverba registra.
        print("gstreamer: maps spletnega procesa ni berljiv - dekoder v procesu ni preverljiv", flush=True)
    izid["dav1d_proces"] = bool(z_dav1d)


def procesi_potomci():
    """{pid: (argv0, ppid, nspid)} za vse potomce tega procesa."""
    vsi = {}
    for d in os.listdir("/proc"):
        if not d.isdigit():
            continue
        try:
            with open("/proc/%s/status" % d) as f:
                st = dict(v.rstrip("\n").split(":\t", 1) for v in f if ":\t" in v)
            with open("/proc/%s/cmdline" % d, "rb") as f:
                argv0 = f.read().split(b"\0", 1)[0].decode(errors="replace")
        except OSError:
            continue
        vsi[int(d)] = (argv0, int(st.get("PPid", "0")), st.get("NSpid", "").split())
    jaz, potomci = os.getpid(), {}
    for pid in vsi:
        p, veriga = pid, []
        while p in vsi and p != jaz and p > 1:
            veriga.append(p)
            p = vsi[p][1]
        if p == jaz:
            potomci[pid] = vsi[pid] + ([vsi[x][0] for x in veriga[1:]],)
    return potomci


def preveri_peskovnik():
    potomci = procesi_potomci()
    for pid, (argv0, _ppid, nspid, predniki) in sorted(potomci.items()):
        print("proces %d: %s nspid=%s predniki=%s" % (pid, argv0, nspid, [os.path.basename(p) for p in predniki]), flush=True)
    spletni = {pid: v for pid, v in potomci.items() if os.path.basename(v[0]) == "WebKitWebProcess"}
    omrezni = {pid: v for pid, v in potomci.items() if os.path.basename(v[0]) == "WebKitNetworkProcess"}
    if not spletni:
        napaka("ni procesa WebKitWebProcess")
    if not omrezni:
        napaka("ni procesa WebKitNetworkProcess")
    for pid, (argv0, _ppid, nspid, predniki) in list(spletni.items()) + list(omrezni.items()):
        if not argv0.startswith(PREDPONA + "/libexec/"):
            napaka("%s ni iz %s/libexec" % (argv0, PREDPONA))
    for pid, (argv0, _ppid, nspid, predniki) in spletni.items():
        if not any(os.path.basename(p) == "bwrap" for p in predniki) or len(nspid) < 2:
            napaka("spletni proces %d ne tece v peskovniku bubblewrap (predniki %s, NSpid %s)" % (pid, predniki, nspid))
        else:
            print("peskovnik: spletni proces %d v bwrap, NSpid %s" % (pid, nspid), flush=True)
        try:
            # Peskovnik poveze /usr na isto pot, zato so poti nasih knjiznic v spletnem procesu enake.
            knj = knjiznice(pid)
            print("spletni proces %d knjiznice: %s" % (pid, knj), flush=True)
            if not knj or not all(k.startswith(PREDPONA + "/") for k in knj):
                napaka("spletni proces %d ne uporablja knjiznic iz %s: %s" % (pid, PREDPONA, knj))
        except OSError as e:
            print("spletni proces %d: maps ni berljiv (%s) - pricakovano v peskovniku" % (pid, e), flush=True)


class Streznik(BaseHTTPRequestHandler):
    def log_message(self, *_a):
        pass

    def do_GET(self):
        if self.path == "/av1.webm":
            self.send_response(200)
            self.send_header("Content-Type", "video/webm")
            self.send_header("Content-Length", str(len(AV1_WEBM)))
            self.end_headers()
            self.wfile.write(AV1_WEBM)
            return
        if self.path == "/av1":
            # Naslov strani pove izid: predvajanje cez 0,5 s ali napaka predvajalnika.
            telo = ("<html><head><title>AV1</title></head><body><video id=v muted autoplay loop src=/av1.webm></video><script>"
                    "const v = document.getElementById('v');"
                    "v.addEventListener('timeupdate', () => { if (v.currentTime > 0.5) document.title = 'AV1 ok ' + "
                    "JSON.stringify(v.getVideoPlaybackQuality ? {sl: v.getVideoPlaybackQuality().totalVideoFrames, "
                    "izp: v.getVideoPlaybackQuality().droppedVideoFrames} : {}); });"
                    "v.addEventListener('error', () => { document.title = 'AV1 napaka ' + (v.error && v.error.code); });"
                    "document.title = 'AV1 ' + MediaSource.isTypeSupported('video/webm; codecs=\"av01.0.00M.08\"');"
                    "</script></body></html>")
        else:
            telo = "<html><head><title>%s</title></head><body>Safeer</body></html>" % NASLOV
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(telo.encode())


streznik = ThreadingHTTPServer(("127.0.0.1", 0), Streznik)
threading.Thread(target=streznik.serve_forever, daemon=True).start()
# NON_UNIQUE: brez imena na D-Bus (CI 38709018765: Gtk.Application brez dosegljivega imena pade).
app = Gtk.Application(application_id="io.github.memelandfaner.SafeerWebkitDeb", flags=Gio.ApplicationFlags.NON_UNIQUE)
izid = {"stran": False, "av1": None, "dav1d_prej": False, "dav1d_proces": False}


def ob_zagonu(app):
    okno = Gtk.ApplicationWindow(application=app, default_width=800, default_height=600)
    pogled = WebKit.WebView()
    okno.set_child(pogled)
    okno.present()

    def ob_naslovu(*_a):
        naslov = pogled.get_title() or ""
        if naslov == NASLOV and not izid["stran"]:
            izid["stran"] = True
            print("stran se je nalozila", flush=True)
            preveri_knjiznice()
            preveri_peskovnik()
            pogled.load_uri("http://127.0.0.1:%d/av1" % streznik.server_port)
        elif naslov.startswith("AV1 ") and izid["av1"] is None:
            print("stran AV1:", naslov, flush=True)
            if naslov.startswith("AV1 ok"):
                izid["av1"] = naslov
                preveri_dav1d_v_procesih()
                app.quit()
            elif naslov.startswith("AV1 napaka"):
                izid["av1"] = naslov
                napaka("video AV1 se ne predvaja: %s" % naslov)
                app.quit()
    pogled.connect("notify::title", ob_naslovu)
    pogled.load_uri("http://127.0.0.1:%d/" % streznik.server_port)

    def cas():
        if not izid["stran"]:
            napaka("stran se v 90 s ni nalozila (naslov %r)" % pogled.get_title())
        elif izid["av1"] is None:
            napaka("video AV1 se v 90 s ni predvajal (naslov %r)" % pogled.get_title())
        app.quit()
        return False
    GLib.timeout_add_seconds(90, cas)


preveri_dav1d()
app.connect("activate", ob_zagonu)
app.run([sys.argv[0]])
streznik.shutdown()
# Ena opomba posla GitHub (tudi iz vsebnika Linux Minta - runner bere stdout docker run).
print("::notice::dav1d %s: %s, dekoder v procesu %s" % (KOREN, izid["av1"], "da" if izid["dav1d_proces"] else "ni preverljiv"), flush=True)
if NAPAKE or not izid["stran"] or not izid["av1"]:
    print("FAIL: %d napak" % len(NAPAKE), flush=True)
    raise SystemExit(1)
print("PASS: nas WebKitGTK in libsoup iz %s, stran nalozena v peskovniku, AV1 z dav1ddec" % PREDPONA, flush=True)
