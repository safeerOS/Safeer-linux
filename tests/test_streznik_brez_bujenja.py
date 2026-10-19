"""Strezniki brez bujenja (core/os_deskriptorji.BrezBujenja): serve_forever v mirovanju ne zbuja procesa, shutdown()
se vedno takoj konca - tudi za Hub z ovitim vticnikom TLS in za streznik na vseh vmesnikih (0.0.0.0)."""
import http.server
import os
import socket
import ssl
import sys
import tempfile
import threading
import time
import unittest
import urllib.request

from core import os_deskriptorji


class _Odgovor(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")


class _Brez(os_deskriptorji.BrezBujenja, http.server.ThreadingHTTPServer):
    daemon_threads = True


def _ipv6_povratna() -> bool:
    """::1 je na povratni zanki. Sam /proc/net/if_inet6 ne zadostuje: vsebnik z jedrom IPv6 in lo brez ::1 bi streznik na
    »::« zagnal, bujenje na ::1 pa bi padlo in shutdown() bi cakal brez konca (ves tek CI do casovne omejitve)."""
    if not socket.has_ipv6:
        return False
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            s.bind(("::1", 0))
        return True
    except OSError:
        return False


def _prebujanja(tid: int) -> int:
    with open("/proc/self/task/%d/status" % tid) as f:
        return sum(int(v.split()[1]) for v in f if "ctxt_switches" in v)


class BrezBujenja(unittest.TestCase):
    def _zazeni(self, razred, naslov="127.0.0.1"):
        s = razred((naslov, 0), _Odgovor)
        nit = threading.Thread(target=s.serve_forever, daemon=True)
        nit.start()
        time.sleep(0.2)
        return s, nit

    def _ustavi(self, s, nit):
        t0 = time.monotonic()
        s.shutdown()
        trajanje = time.monotonic() - t0
        nit.join(2)
        s.server_close()
        self.assertFalse(nit.is_alive())
        return trajanje

    @unittest.skipUnless(sys.platform.startswith("linux"), "/proc")
    def test_v_mirovanju_ne_zbuja_in_streze(self):
        s, nit = self._zazeni(_Brez)
        p0 = _prebujanja(nit.native_id)
        time.sleep(2.0)
        brez = _prebujanja(nit.native_id) - p0
        z, nit_z = self._zazeni(http.server.ThreadingHTTPServer)
        p0 = _prebujanja(nit_z.native_id)
        time.sleep(2.0)
        privzeto = _prebujanja(nit_z.native_id) - p0
        print("\n[streznik] prebujanja v 2 s: privzeto %d, brez bujenja %d" % (privzeto, brez))
        self.assertGreaterEqual(privzeto, 3)              # serve_forever(0.5): 4 na 2 s
        self.assertEqual(brez, 0)
        with urllib.request.urlopen("http://127.0.0.1:%d/" % s.server_address[1], timeout=5) as o:
            self.assertEqual(o.read(), b"ok")
        self.assertLess(self._ustavi(s, nit), 1.0)
        self._ustavi(z, nit_z)

    def test_shutdown_na_vseh_vmesnikih_in_brez_odjemalca(self):
        s, nit = self._zazeni(_Brez, "0.0.0.0")
        self.assertLess(self._ustavi(s, nit), 1.0)

    @unittest.skipUnless(_ipv6_povratna(), "brez IPv6 na povratni zanki")
    def test_shutdown_ipv6(self):
        class V6(_Brez):
            address_family = socket.AF_INET6
        s, nit = self._zazeni(V6, "::")
        self.assertLess(self._ustavi(s, nit), 1.0)

    def test_shutdown_z_ovitim_tls(self):
        """Hub Safeer Linka ovije poslusalni vticnik s TLS (do_handshake_on_connect=False): prazna povezava za
        bujenje ni rokovanje, zanka jo zapusti pred sprejemom."""
        mapa = tempfile.mkdtemp()
        try:
            from core import link_tls
            kljuc, potrdilo = os.path.join(mapa, "k.pem"), os.path.join(mapa, "c.pem")
            if not _ustvari_potrdilo(kljuc, potrdilo):
                self.skipTest("ni orodja za potrdilo")

            class Tls(os_deskriptorji.BrezBujenja, link_tls.RokovanjeVNiti, http.server.ThreadingHTTPServer):
                daemon_threads = True
            s = Tls(("127.0.0.1", 0), _Odgovor)
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(potrdilo, kljuc)
            s.socket = ctx.wrap_socket(s.socket, server_side=True, do_handshake_on_connect=False)
            nit = threading.Thread(target=s.serve_forever, daemon=True)
            nit.start()
            time.sleep(0.2)
            odj = ssl.create_default_context()
            odj.check_hostname, odj.verify_mode = False, ssl.CERT_NONE
            with urllib.request.urlopen("https://127.0.0.1:%d/" % s.server_address[1], timeout=5, context=odj) as o:
                self.assertEqual(o.read(), b"ok")
            self.assertLess(self._ustavi(s, nit), 1.0)
        finally:
            import shutil
            shutil.rmtree(mapa, ignore_errors=True)


def _ustvari_potrdilo(kljuc: str, potrdilo: str) -> bool:
    try:
        import datetime
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID
    except ImportError:
        return False
    k = ec.generate_private_key(ec.SECP256R1())
    ime = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "safeer-preizkus")])
    zdaj = datetime.datetime.now(datetime.timezone.utc)
    c = (x509.CertificateBuilder().subject_name(ime).issuer_name(ime).public_key(k.public_key())
         .serial_number(1).not_valid_before(zdaj).not_valid_after(zdaj + datetime.timedelta(days=1)).sign(k, hashes.SHA256()))
    with open(kljuc, "wb") as f:
        f.write(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()))
    with open(potrdilo, "wb") as f:
        f.write(c.public_bytes(serialization.Encoding.PEM))
    return True


if __name__ == "__main__":
    unittest.main()
