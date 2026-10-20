"""Sprotni zadetki spleta v lupi (core/spletni_zadetki.py, lastnik 20. 10. 2026): ciscenje podatkov tuje strani in pravi
WebKitGTK 6.0 (Xvfb) z lokalnim streznikom, ki posnema strani Googla (z oglasom) in DuckDuckGo (zadetki sele z
JavaScriptom). Brez zaslona ali WebKita se zivi del preskoci."""
import os
import socket
import sys
import threading
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

from core import spletni_zadetki as sz  # noqa: E402


def test_motor_iz_naslova():
    assert sz.motor_za("https://www.google.com/search?q=a") == "google"
    assert sz.motor_za("https://duckduckgo.com/?q=a") == "duckduckgo"
    assert sz.motor_za("https://search.brave.com/search?q=a") == "brave"
    assert sz.motor_za("https://example.org/?q=a") == ""


def test_ocisti_podatke_tuje_strani():
    surovo = [{"t": "ARSO  vreme", "u": "https://www.google.com/goto?url=x", "s": "Napoved\n vremena", "p": "https://vreme.arso.gov.si › napoved"},
              {"t": "zlo", "u": "javascript:alert(1)"}, {"t": "", "u": "https://a.si/"}, {"t": "datoteka", "u": "file:///etc/passwd"},
              "niz", {"t": "dolg", "u": "https://a.si/" + "x" * 3000},
              {"t": "Linux Mint", "u": "https://www.linuxmint.com/", "s": ""},
              {"t": "dvojnik", "u": "https://www.linuxmint.com/"},
              {"t": "tretji", "u": "https://b.si/"}, {"t": "cetrti", "u": "https://c.si/"}]
    z = sz.ocisti(surovo)
    assert [x["naslov"] for x in z] == ["ARSO vreme", "Linux Mint", "tretji"]
    assert z[0]["stran"] == "vreme.arso.gov.si"      # Google povezava prek /goto: stran iz prikazanega naslova
    assert z[0]["odlomek"] == "Napoved vremena"
    assert z[1]["stran"] == "linuxmint.com"
    assert sz.ocisti("ni seznam") == [] and sz.ocisti(None) == []


GOOGLE = """<html><body><div id="tads"><div class="MjjYud"><a href="https://oglas.si/"><h3>Oglas</h3></a></div></div>
<div id="rso"><div class="MjjYud"><a href="https://prvi.si/stran"><h3>Prvi zadetek</h3></a><cite>https://prvi.si › stran</cite>
<div class="VwiC3b">Odlomek prvega</div></div>
<div class="MjjYud"><a href="javascript:void(0)"><h3>Zlo</h3></a></div>
<div class="MjjYud"><a href="https://drugi.si/"><h3>Drugi zadetek</h3></a></div></div></body></html>"""
DDG = """<html><body><div id="r"></div><script>setTimeout(function(){document.getElementById('r').innerHTML=
'<article data-testid="result"><a data-testid="result-title-a" href="https://ddg-prvi.si/">DDG prvi</a><div data-result="snippet">Opis</div></article>'
},700)</script></body></html>"""


def _webkit():
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("WebKit", "6.0")
        from gi.repository import GLib, Gtk, WebKit
        return GLib, Gtk, WebKit
    except Exception:  # noqa: BLE001
        return None


class _Streznik:
    def __init__(self, strani, molci=False):
        self.strani, self.molci = strani, molci
        self.vtic = socket.socket()
        self.vtic.bind(("127.0.0.1", 0))
        self.vtic.listen(8)
        self.vrata = self.vtic.getsockname()[1]
        self.zahteve = []
        threading.Thread(target=self._tek, daemon=True).start()

    def _tek(self):
        while True:
            try:
                c, _ = self.vtic.accept()
            except OSError:
                return
            # Vsaka povezava v svoji niti: WebKit odpre tudi povezavo vnaprej (brez zahteve), ki bi zaporedni streznik
            # zadrzala in naslednja zahteva bi cakala do roka.
            threading.Thread(target=self._streci, args=(c,), daemon=True).start()

    def _streci(self, c):
        with c:
            glava = c.recv(65536).decode("latin1")
            if not glava:
                return
            pot = glava.split(" ")[1] if " " in glava else "/"
            self.zahteve.append(pot)
            if self.molci:
                threading.Event().wait(30)         # nikoli ne odgovori: rok
                return
            telo = self.strani.get(pot.split("?")[0], "").encode()
            c.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\nContent-Length: %d\r\n\r\n"
                      % len(telo) + telo)


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon")
@unittest.skipUnless(_webkit() is not None, "potrebuje WebKitGTK")
class PredogledVZivo(unittest.TestCase):
    def _isci(self, streznik, pot, motor, cakaj=10):
        GLib, Gtk, WebKit = _webkit()
        p = sz.PredogledIskanja(Gtk, WebKit, GLib, WebKit.NetworkSession.new_ephemeral())
        self.addCleanup(p.zapri)
        izid = []
        zanka = GLib.MainLoop()
        p.isci("http://127.0.0.1:%d%s" % (streznik.vrata, pot), lambda r: (izid.append(r), zanka.quit()), motor=motor)
        GLib.timeout_add(cakaj * 1000, lambda: (zanka.quit(), False)[1])
        zanka.run()
        return p, izid

    def test_google_brez_oglasa_in_zla(self):
        s = _Streznik({"/search": GOOGLE})
        p, izid = self._isci(s, "/search?q=a", "google")
        self.assertEqual(len(izid), 1)
        self.assertEqual([(z["naslov"], z["url"], z["stran"]) for z in izid[0]],
                         [("Prvi zadetek", "https://prvi.si/stran", "prvi.si"), ("Drugi zadetek", "https://drugi.si/", "drugi.si")])
        self.assertEqual(izid[0][0]["odlomek"], "Odlomek prvega")
        # Isti niz znova: iz predpomnilnika, brez nove zahteve.
        stevilo = len(s.zahteve)
        drugi = []
        p.isci("http://127.0.0.1:%d/search?q=a" % s.vrata, drugi.append, motor="google")
        self.assertEqual(drugi, [izid[0]])
        self.assertEqual(len(s.zahteve), stevilo)

    def test_duckduckgo_zadetki_sele_z_javascriptom(self):
        s = _Streznik({"/": DDG})
        _p, izid = self._isci(s, "/?q=a", "duckduckgo")
        self.assertEqual([z["naslov"] for z in izid[0]], ["DDG prvi"])

    def test_rok_vrne_prazno(self):
        s = _Streznik({}, molci=True)
        stari = sz.ROK_S
        sz.ROK_S = 1.0
        try:
            _p, izid = self._isci(s, "/search?q=a", "google", cakaj=5)
        finally:
            sz.ROK_S = stari
        self.assertEqual(izid, [[]])

    def test_novejse_iskanje_prekine_starejse(self):
        GLib, Gtk, WebKit = _webkit()
        s = _Streznik({"/search": GOOGLE})
        p = sz.PredogledIskanja(Gtk, WebKit, GLib, WebKit.NetworkSession.new_ephemeral())
        self.addCleanup(p.zapri)
        prvo, drugo = [], []
        zanka = GLib.MainLoop()
        p.isci("http://127.0.0.1:%d/search?q=a" % s.vrata, prvo.append, motor="google")
        p.isci("http://127.0.0.1:%d/search?q=ab" % s.vrata, lambda r: (drugo.append(r), zanka.quit()), motor="google")
        GLib.timeout_add(10000, lambda: (zanka.quit(), False)[1])
        zanka.run()
        self.assertEqual(prvo, [[]])                      # starejse takoj prazno (lupa ga zavrze)
        self.assertEqual(len(drugo[0]), 2)


    def test_pogled_dobi_zascito_spleta_in_se_odjavi(self):
        """OpenAI pregled 1.0.129: skriti pogled je bil surov WebView (brez EasyList, sledilcev, GPC). Splet ga zdaj
        pripravi kot zavihek (pripravi) in ve, kdaj ga ni vec (pozabi)."""
        GLib, Gtk, WebKit = _webkit()
        s = _Streznik({"/search": GOOGLE})
        pripravljeni, pozabljeni = [], []
        p = sz.PredogledIskanja(Gtk, WebKit, GLib, WebKit.NetworkSession.new_ephemeral(),
                                pripravi=pripravljeni.append, pozabi=pozabljeni.append)
        izid = []
        zanka = GLib.MainLoop()
        p.isci("http://127.0.0.1:%d/search?q=a" % s.vrata, lambda r: (izid.append(r), zanka.quit()), motor="google")
        GLib.timeout_add(10000, lambda: (zanka.quit(), False)[1])
        zanka.run()
        self.assertEqual(len(pripravljeni), 1)
        self.assertIs(pripravljeni[0], p.pogled)          # pripravljen PRED prvim nalaganjem
        self.assertEqual(len(izid[0]), 2)
        pogled = p.pogled
        p.zapri()
        self.assertEqual(pozabljeni, [pogled])

if __name__ == "__main__":
    unittest.main()


def test_isti_niz():
    assert sz.isti_niz("https://duckduckgo.com/?q=vreme%20ljubljana", "https://duckduckgo.com/?q=vreme+ljubljana&ia=web")
    assert not sz.isti_niz("https://duckduckgo.com/?q=vreme%20ljubljana", "https://duckduckgo.com/?q=vreme+lj&ia=web")
    assert sz.isti_niz("https://www.google.com/search?q=a", "https://www.google.com/sorry/index")   # ne vemo


def test_lupa_ne_poslje_poti_in_imen_datotek():
    """Webmaster pregled pomocnika 1.0.129: poti in imena datotek isce uporabnik na racunalniku - ne v sprotne zadetke."""
    import json
    import shutil
    import subprocess
    if shutil.which("node") is None:
        raise unittest.SkipTest("ni node")
    koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    primeri = {"vreme ljubljana": True, "python 3.12": True, "izvid-krvi-2026.pdf": False, "~/Dokumenti/davki": False,
               "/etc/fstab": False, "Proračun 2026.ods": False, "baza gesel.kdbx": False, "kopija server.pem": False,
               "moja pogodba.pages": False, "windows 11": True, "vreme 10.30": True, "dokumenti/davki": False, "safeer.si": False, "ab": False}
    js = ("const S=require(%s);const p=%s;const o={};for(const k in p)o[k]=S.smeSprotniSplet(k);console.log(JSON.stringify(o))"
          % (json.dumps(os.path.join(koren, "assets", "os", "iskanje.js")), json.dumps(primeri)))
    izid = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)
    assert izid == primeri
    qml = open(os.path.join(koren, "assets", "os", "qml", "Namizje.qml"), encoding="utf-8").read()
    assert "Iskanje.SafeerIskanje.smeSprotniSplet(q)" in qml


def test_vsak_iskalnik_ima_ime_za_oznako():
    """Oznaka pod sprotnimi zadetki (lastnik 20. 10. 2026) imenuje iskalnik - za vsak iskalnik iz nastavitev."""
    import ast
    koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    drevo = ast.parse(open(os.path.join(koren, "safeer_os.py"), encoding="utf-8").read())
    vrednosti = {}
    for n in drevo.body:
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in ("ISKALNIKI", "IMENA_ISKALNIKOV"):
            vrednosti[n.targets[0].id] = ast.literal_eval(n.value)
    assert set(vrednosti["ISKALNIKI"]) == set(vrednosti["IMENA_ISKALNIKOV"])
    vir = open(os.path.join(koren, "safeer_os.py"), encoding="utf-8").read()
    assert "dict(z, iskalnik=ime)" in vir


def _lazni_predogled(dokument):
    """PredogledIskanja z laznim pogledom: izvlecni skript vrne zadetke iz dokumenta dokument[0] = (naslov, zadetki)."""
    import json as _json
    import types
    LoadEvent = types.SimpleNamespace(STARTED=0, COMMITTED=2, FINISHED=3)
    WebKit = types.SimpleNamespace(LoadEvent=LoadEvent)
    casovniki = []
    GLib = types.SimpleNamespace(timeout_add=lambda ms, f: (casovniki.append(f) if ms == 250 else None) or 1,  # brez roka
                                 timeout_add_seconds=lambda *_a: 1, source_remove=lambda _i: None)
    p = sz.PredogledIskanja(None, WebKit, GLib)
    rezultat = types.SimpleNamespace(to_string=lambda: _json.dumps({"naslov": dokument[0][0], "zadetki": dokument[0][1]}))
    pogled = types.SimpleNamespace(load_uri=lambda _u: None, get_uri=lambda: "", stop_loading=lambda: None,
                                   evaluate_javascript=lambda js, _d, _s, _a, _b, cb: cb(pogled, "r"),
                                   evaluate_javascript_finish=lambda r: rezultat)
    p._pogled = lambda: (setattr(p, "pogled", pogled), pogled)[1]
    return p, LoadEvent, casovniki


ZADETEK = [{"t": "Vreme", "u": "https://vreme.si/", "p": "vreme.si", "s": "x"}]   # oblika izvlecnega skripta


def test_stari_dokument_ne_da_zadetkov_novemu_nizu():
    """Webmaster pregled pomocnika 1.0.129 + CI 21. 10.: ob novem nizu pride FINISHED prekinjenega starega nalaganja,
    v pogledu je stran PREJSNJEGA niza. Ali zadetki veljajo, pove dokument (location.href), ne vrstni red dogodkov."""
    dokument = [("https://duckduckgo.com/?q=vreme+lj", ZADETEK)]
    p, LoadEvent, casovniki = _lazni_predogled(dokument)
    prvo, drugo = [], []
    p.isci("https://duckduckgo.com/?q=vreme+lj", prvo.append, motor="duckduckgo")
    p.isci("https://duckduckgo.com/?q=vreme+ljubljana", drugo.append, motor="duckduckgo")
    p._nalozeno(p.pogled, LoadEvent.FINISHED)            # stari dokument
    assert drugo == [] and casovniki                      # ne kaze, caka (poskus znova)
    assert "https://duckduckgo.com/?q=vreme+ljubljana" not in p._shramba
    dokument[0] = ("https://duckduckgo.com/?q=vreme+ljubljana&ia=web", ZADETEK)
    casovniki.pop(0)()                                    # naslednji poskus: zdaj je v pogledu nov dokument
    assert len(drugo) == 1 and drugo[0][0]["naslov"] == "Vreme"


def test_stran_brez_niza_ne_da_zadetkov():
    """OpenAI pregled F: stran brez parametra q (soglasje, preusmeritev) ne potrdi iskanja z nizom."""
    dokument = [("https://www.google.com/sorry/index", ZADETEK)]
    p, LoadEvent, casovniki = _lazni_predogled(dokument)
    izid = []
    p.isci("https://www.google.com/search?q=ab", izid.append, motor="google")
    p._nalozeno(p.pogled, LoadEvent.FINISHED)
    for _ in range(sz.POSKUSOV + 2):
        if casovniki:
            casovniki.pop(0)()
    assert izid == [] and not p._shramba                  # brez zadetkov, nic shranjeno (rok konca prazno)
    assert sz.ta_niz("https://a/?q=x", "https://a/?q=x&ia=web") and not sz.ta_niz("https://a/?q=x", "https://a/sorry")
