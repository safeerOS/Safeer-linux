#!/usr/bin/env python3
"""HSTS state must not be readable cross-site (WebKitGTK 6.0 / GTK 4 API). Loopback only (::1 / 127.0.0.1, *.localhost).

A page on www.first.localhost (no HSTS policy) loads http:// images:
  - tracker.localhost     (CROSS-SITE) -> if it arrives over TLS, a third-party site reads HSTS state that belongs to
                                          another site (HSTS "supercookie", history sniffing). Expected: HTTP.
  - img.first.localhost   (SAME-SITE)  -> expected TLS (the HSTS upgrade of subresources the patch introduces).
  - control: top-level navigation to tracker.localhost -> TLS (proves that the policy was really stored and is read).

Usage:  xvfb-run -a python3 hsts_cross_site_en.py <empty temporary directory>
Output: one line per request class with TLS or HTTP (first byte 0x16 = TLS ClientHello).
"""
import json, os, socket, socketserver, ssl, subprocess, sys, threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("WebKit", "6.0")
gi.require_version("Soup", "3.0")
from gi.repository import GLib, Gtk, Soup, WebKit

base = sys.argv[1]
PAGE_HOST = sys.argv[2] if len(sys.argv) > 2 else "www.first.localhost"
data_dir, cache_dir = os.path.join(base, "data"), os.path.join(base, "cache")
os.makedirs(data_dir, exist_ok=True)
os.makedirs(os.path.join(cache_dir, "HSTS"), exist_ok=True)

# WebKit reads <cache dir>/HSTS/hsts-storage.sqlite
db = Soup.HSTSEnforcerDB.new(os.path.join(cache_dir, "HSTS", "hsts-storage.sqlite"))
for name in ("tracker.localhost", "img.first.localhost"):
    db.set_policy(Soup.HSTSPolicy.new(name, 3600, False))
del db

crt, key = os.path.join(base, "c.pem"), os.path.join(base, "k.pem")
subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=localhost",
                "-keyout", key, "-out", crt], check=True, capture_output=True)
tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
tls.load_cert_chain(crt, key)

result, lock = {}, threading.Lock()


def record(kind, what):
    with lock:
        result.setdefault(kind, set()).add(what)


def server(kind, respond):
    """respond(path, is_tls) -> (status, headers, body). One listener on ::1 and 127.0.0.1, same port."""
    class H(socketserver.BaseRequestHandler):
        def handle(self):
            try:
                first = self.request.recv(1, socket.MSG_PEEK)
            except OSError:
                return
            if not first:
                return
            s, is_tls = self.request, first == b"\x16"
            if is_tls:
                try:
                    s = tls.wrap_socket(s, server_side=True)
                except (ssl.SSLError, OSError):
                    return
            raw = b""
            while b"\r\n\r\n" not in raw and len(raw) < 65536:
                k = s.recv(65536)
                if not k:
                    break
                raw += k
            line = raw.split(b"\r\n", 1)[0].decode("latin-1")
            path = line.split(" ")[1] if " " in line else "/"
            record(kind, ("TLS " if is_tls else "HTTP ") + path.split("?")[0])
            status, headers, body = respond(path, is_tls)
            try:
                s.sendall(("HTTP/1.1 %s\r\n%sContent-Length: %d\r\nConnection: close\r\n\r\n"
                           % (status, "".join("%s: %s\r\n" % h for h in headers), len(body))).encode() + body)
            except OSError:
                pass

    class S6(socketserver.ThreadingTCPServer):
        address_family, allow_reuse_address, daemon_threads = socket.AF_INET6, True, True

    class S4(socketserver.ThreadingTCPServer):
        allow_reuse_address, daemon_threads = True, True

    s6 = S6(("::1", 0), H)
    port = s6.server_address[1]
    s4 = S4(("127.0.0.1", port), H)
    for srv in (s6, s4):
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    return port


GIF = bytes.fromhex("47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b")
image = lambda path, t: ("200 OK", [("Content-Type", "image/gif")], GIF)
port_cross = server("A cross-site   tracker.localhost (img)", image)
port_same = server("A same-site    img.first.localhost (img)", image)
port_top = server("A control: top-level navigation to tracker.localhost",
                  lambda path, t: ("200 OK", [("Content-Type", "text/html")], b"<p>top</p>"))
SCRIPT = lambda path, t: ("200 OK", [("Content-Type", "text/javascript")], b"1;")
FRAME = lambda path, t: ("200 OK", [("Content-Type", "text/html")], b"<p>frame</p>")
port_srcdoc = server("B cross-site   tracker.localhost (img in srcdoc iframe)", image)
port_sandbox = server("C cross-site   tracker.localhost (img in sandboxed srcdoc iframe)", image)
port_script = server("D cross-site   tracker.localhost (script)", SCRIPT)
port_xhr = server("E cross-site   tracker.localhost (xhr/fetch no-cors, Origin sent)", image)
port_redir_target = server("R target cross-site tracker.localhost (img, after redirect)", image)
port_redir = server("R redirector img.first.localhost (302 to cross-site)", lambda path, t: ("302 Found", [("Location", "http://tracker.localhost:%d/r.gif" % port_redir_target)], b""))
port_frame = server("F cross-site   tracker.localhost (iframe document)", FRAME)
page = ("<html><body><img src='http://tracker.localhost:%d/t.gif'><img src='http://img.first.localhost:%d/i.gif'>"
        "<iframe srcdoc=\"<img src='http://tracker.localhost:%d/s.gif'>\"></iframe>"
        "<iframe sandbox srcdoc=\"<img src='http://tracker.localhost:%d/b.gif'>\"></iframe>"
        "<script src='http://tracker.localhost:%d/x.js'></script>"
        "<iframe src='http://tracker.localhost:%d/f.html'></iframe>"
        "<script>fetch('http://tracker.localhost:%d/q', {mode:'no-cors'}).catch(function(){});"
        "var x=new XMLHttpRequest();x.open('GET','http://tracker.localhost:%d/x');x.send();</script>"
        "<img src=\x27http://img.first.localhost:%d/r.gif\x27></body></html>" % (port_cross, port_same, port_srcdoc, port_sandbox, port_script, port_frame, port_xhr, port_xhr, port_redir)).encode()
port_page = server("page (first site, no HSTS policy)", lambda path, t: ("200 OK", [("Content-Type", "text/html")], page))

session = WebKit.NetworkSession.new(data_dir, cache_dir)
session.set_tls_errors_policy(WebKit.TLSErrorsPolicy.IGNORE)     # self-signed local servers of this test
app = Gtk.Application(application_id="si.safeer.hstscrosssite")


def activate(a):
    window = Gtk.ApplicationWindow(application=a)
    view = WebKit.WebView(network_session=session)
    window.set_child(view)
    window.present()
    steps = ["http://tracker.localhost:%d/" % port_top, "http://%s:%d/" % (PAGE_HOST, port_page)]

    def step():
        if steps:
            view.load_uri(steps.pop(0))
            GLib.timeout_add_seconds(6, step)
        else:
            a.quit()
        return False

    step()


app.connect("activate", activate)
app.run([])

print("WebKitGTK %d.%d.%d" % (WebKit.get_major_version(), WebKit.get_minor_version(), WebKit.get_micro_version()))
for kind in sorted(result):
    print("%-56s %s" % (kind, ", ".join(sorted(result[kind]))))
print("JSON " + json.dumps({k: sorted(v) for k, v in result.items()}, sort_keys=True))
