"""Preizkus nasega WebKitGTK in libsoup v namescenem paketu .deb (packaging/webkit-deb).

Uporaba: python3 smoke_webkit_deb.py KOREN_PROGRAMA     npr. /usr/lib/safeer-browser, /usr/lib/safeer-os, /usr/lib/safeer-control

Preveri, kar mora veljati na racunalniku uporabnika (tudi ce je namescen sistemski WebKitGTK 6.0 iz Ubuntuja):
  * core/zasebni_webkit.py najde predpono paketa in Python nalozi typelibe iz nje,
  * /proc/self/maps: libwebkitgtk-6.0, libjavascriptcoregtk-6.0 in libsoup-3.0 so iz predpone, nobena iz sistema,
  * libsoup >= 3.8, WebKitGTK je razlicica iz zapisa gradnje (gradnja.txt: Clang 22, ThinLTO, lld, ta predpona),
  * stran prek HTTP se nalozi; spletni proces je WebKitWebProcess iz predpone in tece v peskovniku bubblewrap
    (predhodnik bwrap in lasten imenski prostor PID - NSpid v /proc/<pid>/status).
Izhod 0 in vrstica PASS, sicer FAIL: ... in izhod 1.
"""
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

import gi  # noqa: E402
gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
gi.require_version("Soup", "3.0")
from gi.repository import Gio, GLib, Gtk, Soup, WebKit  # noqa: E402

NAPAKE = []
NASLOV = "Safeer WebKit deb smoke"


def napaka(besedilo):
    NAPAKE.append(besedilo)
    print("FAIL:", besedilo, flush=True)


def knjiznice(pid="self"):
    with open("/proc/%s/maps" % pid) as f:
        return sorted({v.split()[-1] for v in f if any(k in v for k in ("libwebkitgtk-6.0", "libjavascriptcoregtk-6.0", "libsoup-3.0"))})


def preveri_knjiznice():
    knj = knjiznice()
    print("predpona:", PREDPONA, flush=True)
    print("knjiznice:", knj, flush=True)
    for ime in ("libwebkitgtk-6.0", "libjavascriptcoregtk-6.0", "libsoup-3.0"):
        poti = [k for k in knj if ime in k]
        if not poti:
            napaka("%s ni nalozena" % ime)
        elif not all(k.startswith(PREDPONA + "/") for k in poti):
            napaka("%s ni iz %s: %s" % (ime, PREDPONA, poti))
    soup = (Soup.get_major_version(), Soup.get_minor_version(), Soup.get_micro_version())
    wk = (WebKit.get_major_version(), WebKit.get_minor_version(), WebKit.get_micro_version())
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
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(("<html><head><title>%s</title></head><body>Safeer</body></html>" % NASLOV).encode())


streznik = ThreadingHTTPServer(("127.0.0.1", 0), Streznik)
threading.Thread(target=streznik.serve_forever, daemon=True).start()
# NON_UNIQUE: brez imena na D-Bus (CI 38709018765: Gtk.Application brez dosegljivega imena pade).
app = Gtk.Application(application_id="io.github.memelandfaner.SafeerWebkitDeb", flags=Gio.ApplicationFlags.NON_UNIQUE)
izid = {"stran": False}


def ob_zagonu(app):
    okno = Gtk.ApplicationWindow(application=app, default_width=800, default_height=600)
    pogled = WebKit.WebView()
    okno.set_child(pogled)
    okno.present()

    def ob_naslovu(*_a):
        if pogled.get_title() == NASLOV and not izid["stran"]:
            izid["stran"] = True
            print("stran se je nalozila", flush=True)
            preveri_knjiznice()
            preveri_peskovnik()
            app.quit()
    pogled.connect("notify::title", ob_naslovu)
    pogled.load_uri("http://127.0.0.1:%d/" % streznik.server_port)

    def cas():
        if not izid["stran"]:
            napaka("stran se v 60 s ni nalozila (naslov %r)" % pogled.get_title())
            app.quit()
        return False
    GLib.timeout_add_seconds(60, cas)


app.connect("activate", ob_zagonu)
app.run([sys.argv[0]])
streznik.shutdown()
if NAPAKE or not izid["stran"]:
    print("FAIL: %d napak" % len(NAPAKE), flush=True)
    raise SystemExit(1)
print("PASS: nas WebKitGTK in libsoup iz %s, stran nalozena v peskovniku" % PREDPONA, flush=True)
