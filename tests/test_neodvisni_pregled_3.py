"""Popravki po drugem neodvisnem pregledu izdaje 1.0.128 (19. 10. 2026), drugi del.

- Most safeerLink (okno Link) sprejme samo sporocila z zetonom iz MOST_JS (glavni okvir), kot most safeerOs.
  Most safeerVnos (okno gledalca) je v locenem svetu - preizkus v pravem WebKitu je v test_gledalec_vnos_zivo.py.
- Agent: http samo v domace omrezje, zahteve na model ne sledijo preusmeritvam (kljuc v glavi Authorization).
- JBL: ukaz gre samo vrstici z odtisom potrdila, zapomnjenim ob vklopu; preverjeno pred posiljanjem.
- Prenosi z GitHuba preverijo vsak skok preusmeritve; openssl -subj dobi samo varno ime; pkill dobi ubezan izraz;
  odtisi in kljuci se primerjajo v stalnem casu.
Vsak preizkus brez svojega popravka pade.
"""
import hashlib
import http.server
import inspect
import json
import os
import shutil
import ssl
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest import mock

from core import link_gledalec, link_kripto, link_neposredno, link_sway, os_github_programi, os_jbl
from core.agent import nastavitve, razumevanje


class _Rezultat:
    def __init__(self, besedilo):
        self.besedilo = besedilo

    def to_string(self):
        return self.besedilo


class MostLinka(unittest.TestCase):
    def setUp(self):
        from core import safeer_link
        self.sl = safeer_link
        self.lazna = mock.MagicMock()

    def _poslji(self, sporocilo):
        self.sl.SafeerLink._na_sporocilo(self.lazna, None, _Rezultat(json.dumps(sporocilo)))

    def test_zeton_je_v_mostu(self):
        self.assertIn("t: zeton", self.sl.MOST_JS)
        self.assertIn(self.sl.ZETON_MOSTU, self.sl.MOST_JS)
        self.assertNotIn("__ZETON__", self.sl.MOST_JS)
        self.assertGreaterEqual(len(self.sl.ZETON_MOSTU), 32)

    def test_brez_zetona_ni_dejanja(self):
        """Vgrajen okvir (iframe) ali XSS na strani Linka nima zetona: seznanitev, odobritev kode ... ne gredo skozi."""
        self._poslji({"m": "zapri", "a": []})
        self._poslji({"m": "zapri", "a": [], "t": "ugibam"})
        self.lazna._zapri_okno.assert_not_called()

    def test_z_zetonom_dela(self):
        self._poslji({"m": "zapri", "a": [], "t": self.sl.ZETON_MOSTU})
        self.lazna._zapri_okno.assert_called_once()


class _Streznik(http.server.ThreadingHTTPServer):
    daemon_threads = True


def _zazeni_streznik(tls_kontekst=None, rokovalnik=None):
    zahteve = []

    class R(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _odgovor(self):
            dolzina = int(self.headers.get("Content-Length") or 0)
            zahteve.append((self.command, self.path, dict(self.headers), self.rfile.read(dolzina) if dolzina else b""))
            if rokovalnik is not None:
                return rokovalnik(self)
            telo = b'{"BT_MAC":"00:1B:44:11:3A:B8"}'
            self.send_response(200)
            self.send_header("Content-Length", str(len(telo)))
            self.end_headers()
            self.wfile.write(telo)

        do_GET = do_POST = _odgovor

    s = _Streznik(("127.0.0.1", 0), R)
    if tls_kontekst is not None:
        s.socket = tls_kontekst.wrap_socket(s.socket, server_side=True)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, zahteve


class AgentDomaceOmrezje(unittest.TestCase):
    def test_http_samo_v_domace_omrezje(self):
        for dober in ("http://192.168.1.20:8085", "http://10.0.0.5", "http://127.0.0.1:8085", "http://localhost:8085",
                      "http://telefon:8085", "http://model.local:8085", "http://[fd00::5]:8085",
                      "https://model.example.org", "https://203.0.113.5:8443"):
            self.assertTrue(nastavitve.preveri_naslov(dober), dober)
        for slab in ("http://model.example.org", "http://1.1.1.1:8085", "http://8.8.8.8", "http://[2606:4700::1111]"):
            with self.assertRaises(ValueError) as e:
                nastavitve.preveri_naslov(slab)
            self.assertEqual(str(e.exception), "http", slab)

    def test_naslov_iz_okolja_velja_isto(self):
        with mock.patch.dict(os.environ, {"SAFEER_AGENT": "http://model.example.org:8085"}), \
                mock.patch.object(nastavitve, "vklopljen", return_value=True):
            self.assertEqual(razumevanje.naslov_modela(), "")

    def test_kljuc_ne_gre_za_preusmeritvijo(self):
        cilj, prejel = _zazeni_streznik()

        def preusmeri(r):
            r.send_response(302)
            r.send_header("Location", "http://127.0.0.1:%d/v1/models" % cilj.server_address[1])
            r.send_header("Content-Length", "0")
            r.end_headers()
        izvor, _ = _zazeni_streznik(rokovalnik=preusmeri)
        mapa = tempfile.mkdtemp()
        try:
            with mock.patch.object(nastavitve, "MAPA", mapa):
                nastavitve._pisi("kljuc", "skrivni-kljuc")
                izid = nastavitve.dosegljivost("http://127.0.0.1:%d" % izvor.server_address[1], cas=3.0)
                self.assertFalse(izid["dosegljiv"], izid)
                klic = razumevanje.llama_server("http://127.0.0.1:%d" % izvor.server_address[1], "skrivni-kljuc", 3.0)
                with self.assertRaises(urllib.error.HTTPError):
                    klic([{"role": "user", "content": "utisaj televizor"}], {"type": "object"})
            self.assertEqual(prejel, [], "zahteva s kljucem je sla za preusmeritvijo")
        finally:
            cilj.shutdown()
            izvor.shutdown()
            shutil.rmtree(mapa, ignore_errors=True)


class JblOdtis(unittest.TestCase):
    """Lazna vrstica v domacem omrezju (TLS na 127.0.0.1): ukaz gre samo napravi z zapomnjenim odtisom."""

    def setUp(self):
        self.mapa = tempfile.mkdtemp()
        self.okolje = mock.patch.dict(os.environ, {"XDG_CONFIG_HOME": self.mapa})
        self.okolje.start()
        jbl = os_jbl.mapa()
        os.makedirs(jbl, mode=0o700)
        # Potrdilo odjemalca (namesto potrdila JBL One) in potrdilo lazne vrstice.
        link_kripto.ustvari_kljuc_in_potrdilo(os.path.join(jbl, "Key.pem"), os.path.join(jbl, "Cert.pem"), "odjemalec")
        odtisi = {}
        for ime in ("Cert.pem", "Key.pem"):
            with open(os.path.join(jbl, ime), "rb") as f:
                odtisi[ime] = hashlib.sha256(f.read()).hexdigest()
        self.odtisi = mock.patch.object(os_jbl, "ODTISI", odtisi)
        self.odtisi.start()
        kljuc, potrdilo = os.path.join(self.mapa, "v.key"), os.path.join(self.mapa, "v.pem")
        link_kripto.ustvari_kljuc_in_potrdilo(kljuc, potrdilo, "vrstica")
        kontekst = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        kontekst.load_cert_chain(potrdilo, kljuc)
        with open(potrdilo, encoding="ascii") as f:
            self.odtis_vrstice = hashlib.sha256(ssl.PEM_cert_to_DER_cert(f.read())).hexdigest()
        self.streznik, self.zahteve = _zazeni_streznik(kontekst)
        self.vrata = mock.patch.object(os_jbl, "VRATA", self.streznik.server_address[1])
        self.vrata.start()
        self.najdi = mock.patch.object(os_jbl, "najdi", return_value=[])
        self.najdi.start()

    def tearDown(self):
        for p in (self.najdi, self.vrata, self.odtisi, self.okolje):
            p.stop()
        self.streznik.shutdown()
        shutil.rmtree(self.mapa, ignore_errors=True)

    def _nastavi(self, **dodatno):
        os_jbl._shrani(dict({"vklop": True, "naslov": "127.0.0.1", "ime": "JBL BAR 300", "bt": "00:1B:44:11:3A:B8"},
                            **dodatno))

    def test_druga_naprava_ne_dobi_ukaza(self):
        self._nastavi(odtis="0" * 64)
        self.assertFalse(os_jbl.preklopi("tv"))
        self.assertEqual(self.zahteve, [], "ukaz je sel napravi z drugim potrdilom")

    def test_prava_vrstica_dobi_ukaz(self):
        self._nastavi(odtis=self.odtis_vrstice)
        self.assertTrue(os_jbl.preklopi("tv"))
        self.assertEqual(len(self.zahteve), 1)
        metoda, pot, _glave, telo = self.zahteve[0]
        self.assertEqual((metoda, pot), ("POST", "/httpapi.asp"))
        self.assertIn(b'"key_pressed":"source-tv"', telo)

    def test_vklop_si_zapomni_odtis(self):
        self.assertEqual(os_jbl.bt_naslov("127.0.0.1"), ("00:1B:44:11:3A:B8", self.odtis_vrstice))
        with mock.patch.object(os_jbl, "najdi", return_value=[{"ime": "JBL BAR 300", "naslov": "127.0.0.1", "mac": ""}]):
            izid = os_jbl.vklopi(True)
        self.assertTrue(izid["vklop"], izid)
        self.assertEqual(os_jbl.nastavitve()["odtis"], self.odtis_vrstice)

    def test_vklop_pred_posodobitvijo_si_odtis_zapomni_ob_prvem_ukazu(self):
        self._nastavi()
        self.assertTrue(os_jbl.preklopi("bluetooth"))
        self.assertEqual(os_jbl.nastavitve()["odtis"], self.odtis_vrstice)


class PreusmeritveGithuba(unittest.TestCase):
    def _skok(self, kam):
        z = urllib.request.Request("https://github.com/o/r/releases/download/v1/a.deb")
        return os_github_programi._Preusmeritve().redirect_request(z, None, 302, "Found", {}, kam)

    def test_vsak_skok_preverjen(self):
        for slab in ("http://10.0.0.1/admin", "https://169.254.169.254/latest", "http://github.com/x",
                     "https://evil.example/a.deb"):
            with self.assertRaises(urllib.error.HTTPError, msg=slab):
                self._skok(slab)
        self.assertIsNotNone(self._skok("https://release-assets.githubusercontent.com/a.deb?x=1"))

    def test_privzeto_odpiranje_je_varno(self):
        self.assertIs(inspect.signature(os_github_programi.Prenosi).parameters["odpri"].default,
                      os_github_programi.odpri_varno)


class DrobniPopravki(unittest.TestCase):
    def test_openssl_subj_brez_dodatnih_polj(self):
        klici = []
        with mock.patch.object(link_kripto, "_crypto", return_value=None), \
                mock.patch.object(link_kripto.subprocess, "run", side_effect=lambda a, **k: klici.append(a)):
            link_kripto.ustvari_kljuc_in_potrdilo("/nikjer/k", "/nikjer/p", "PC/O=Napadalec\n/CN=x")
        subj = klici[0][klici[0].index("-subj") + 1]
        self.assertEqual(subj.count("/"), 1, subj)
        self.assertNotIn("=Napadalec", subj)
        self.assertNotIn("\n", subj)

    def test_pkill_dobi_ubezan_izraz(self):
        izvor = inspect.getsource(link_sway)
        self.assertIn('"^sway -c " + re.escape(konf) + "$"', izvor)

    def test_odtisi_v_stalnem_casu(self):
        self.assertIn("hmac.compare_digest(dejanski", inspect.getsource(link_gledalec.Gledalec._odpri))
        self.assertIn("hmac.compare_digest(_kljuc_potrdila(der)", inspect.getsource(link_neposredno.odpri_neposredno))


if __name__ == "__main__":
    unittest.main()
