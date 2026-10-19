"""Stevec Scita iz skript glavnega sveta (19. 10. 2026).

YOUTUBE_ADBLOCK_SCRIPT in ADGUARD_PROTECTION_SCRIPT spreminjata JS strani, zato tecejo v glavnem svetu. Most
safeer_stevec je samo v locenem svetu (stran ga ne doseze), zato se je vsak njun klic mostu izgubil - stevec je stel
samo kozmeticna skripta. Zdaj javita stevilo z dogodkom DOM, rele v locenem svetu (core/os_splet.namesti_stevec) ga
poslje v most. Stran lahko dogodek ponaredi (sprejeto, gre za prikaz): rele vzame samo celo stevilo 1..50 in najvec
500 na nalaganje okvirja.

Most »safeer« v glavnem svetu (vsi okvirji, brez zetona) stevca nikoli ne spremeni (koncni neodvisni pregled).

Zivi del tece v pravem WebKitGTK 6.0 (Xvfb, kot tests/test_link_most_zivo.py); brez zaslona ali WebKita se preskoci.
"""
import json
import os
import re
import sys
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

from core import adblock  # noqa: E402

YOUTUBE = ["*://*.youtube.com/*", "*://youtube.com/*"]
#: Dogovor med skriptami glavnega sveta in relejem (adblock.STEVEC_DOGODEK, STEVEC_NA_DOGODEK, STEVEC_NA_STRAN).
DOGODEK, NA_DOGODEK, NA_STRAN = "safeer-stevec", 50, 500
#: Ali stran v glavnem svetu vidi most stevca (ne sme ga).
JS_MOST = "!!(window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.%s)" % adblock.STEVEC_MOST

#: Tri elementi, ki jih odstrani ADGUARD_PROTECTION_SCRIPT (cleanAdguardCosmetics).
STRAN_ADGUARD = """<!doctype html><html><body>
<div class="adguard-banner">oglas</div><div class="adguard-banner">oglas</div><div data-ad-unit="1">oglas</div>
<p id="vsebina">vsebina</p></body></html>"""
#: Dva elementa, ki ju odstrani superviseYouTube (YOUTUBE_ADBLOCK_SCRIPT).
STRAN_YOUTUBE = """<!doctype html><html><body>
<div id="player-ads">oglas</div><div class="ytp-ad-overlay-container">oglas</div><p>vsebina</p></body></html>"""
_PONAREDI = "<script>function d(v){document.dispatchEvent(new CustomEvent(%r,{detail:v}));}%%s</script>" % DOGODEK
#: Neveljavni dogodki (prevelik, nic, negativen, decimalen, niz, NaN, neskoncno, predmet), nato en veljaven: 7.
STRAN_NEVELJAVNI = "<!doctype html><html><body>" + _PONAREDI % (
    "[51,0,-5,2.5,'7',NaN,Infinity,null,{count:5},[3]].forEach(d);d(7);") + "</body></html>"
#: Poplava: 30 x 50 = 1500, rele pusti skozi najvec 500.
STRAN_POPLAVA = "<!doctype html><html><body>" + _PONAREDI % "for(var i=0;i<30;i++)d(50);" + "</body></html>"


class SkriptiGlavnegaSveta(unittest.TestCase):
    """Hitri staticni del: v glavnem svetu mostu ni, zato ga skripte glavnega sveta ne smejo klicati."""

    def test_youtube_in_adguard_brez_klica_mostu(self):
        for ime in ("YOUTUBE_ADBLOCK_SCRIPT", "ADGUARD_PROTECTION_SCRIPT"):
            koda = getattr(adblock, ime)
            self.assertNotIn("messageHandlers.safeer_stevec", koda, ime)
            self.assertNotIn("messageHandlers", koda, ime)
            self.assertIn("javiStevec(", koda, ime)
            self.assertNotIn("@javiStevec@", koda, ime)

    def test_nobena_skripta_glavnega_sveta_v_spletu_ne_klice_mostu(self):
        with open(os.path.join(KOREN, "core", "os_splet.py"), encoding="utf-8") as f:
            izvor = f.read()
        imena = set(re.findall(r"self\._skripta\(upravitelj, adblock\.([A-Z_]+)", izvor))
        self.assertTrue({"YOUTUBE_ADBLOCK_SCRIPT", "ADGUARD_PROTECTION_SCRIPT"} <= imena, imena)
        for ime in imena:
            self.assertNotIn("messageHandlers", getattr(adblock, ime), ime)
        # Rele stevca je namescen v vsakem zavihku, z izjemami skript za oglase.
        self.assertIn("namesti_stevec(W, upravitelj, lambda _u, r: self._stevec(r), izvzemi_oglase)", izvor)

    def test_glavni_most_stevca_nikoli_ne_spremeni(self):
        """Most »safeer« (glavni svet, vsak okvir, brez zetona) stevca ne spremeni, tudi ce bi razcleni_sporocilo
        increment kdaj spustil skozi (koncni neodvisni pregled, 19. 10. 2026): stevec samo prek _stevec."""
        from core import os_splet
        splet = mock.MagicMock()
        pogled = mock.MagicMock()
        pogled.get_uri.return_value = "https://napadalec.test/"
        for dejanje in ("increment_ads", "increment_threats"):
            with mock.patch.object(os_splet, "razcleni_sporocilo", return_value={"action": dejanje, "count": 50}):
                os_splet.VdelaniSplet._sporocilo(splet, pogled, mock.MagicMock())
        splet.config.increment_ads_blocked.assert_not_called()
        splet.config.increment_threats_blocked.assert_not_called()
        self.assertIsNone(os_splet.razcleni_sporocilo({"action": "increment_ads", "count": 5}))

    def test_rele_v_locenem_svetu_z_mejami(self):
        r = adblock.STEVEC_RELE_SCRIPT
        self.assertIn("messageHandlers.%s" % adblock.STEVEC_MOST, r)
        self.assertIn("'%s'" % adblock.STEVEC_DOGODEK, r)
        self.assertIn("Number.isInteger(n) || n < 1 || n > %d" % adblock.STEVEC_NA_DOGODEK, r)
        self.assertIn("var ostane = %d;" % adblock.STEVEC_NA_STRAN, r)
        self.assertEqual((adblock.STEVEC_DOGODEK, adblock.STEVEC_NA_DOGODEK, adblock.STEVEC_NA_STRAN),
                         (DOGODEK, NA_DOGODEK, NA_STRAN))


def _webkit():
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        gi.require_version("WebKit", "6.0")
        from gi.repository import GLib, Gtk, WebKit
        return GLib, Gtk, WebKit
    except Exception:  # noqa: BLE001
        return None


@unittest.skipUnless(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"), "potrebuje zaslon")
@unittest.skipUnless(_webkit() is not None, "potrebuje WebKitGTK 6.0")
class ReleVZivo(unittest.TestCase):
    def _nalozi(self, stran: str, naslov: str, glavni=()):
        """Zavihek kot v Spletu (most in rele iz os_splet.namesti_stevec, skripte glavnega sveta kot _skripta).
        Vrne (stevila, ki so prisla do Pythona, ali stran vidi most v glavnem svetu)."""
        GLib, Gtk, WebKit = _webkit()
        from core import os_splet
        prejeto, izid = [], {}

        def ob_stevcu(_u, r):
            s = adblock.preveri_stevec(json.loads(r.to_json(0)))
            if s and s["action"] == "increment_ads":
                prejeto.append(s["count"])
        u = WebKit.UserContentManager()
        if hasattr(os_splet, "namesti_stevec"):
            os_splet.namesti_stevec(WebKit, u, ob_stevcu, adblock.AUTH_SCRIPT_EXCLUSIONS)
        else:   # vezava pred popravkom (samo most v locenem svetu): preizkus brez popravka pade na stetju, ne na uvozu
            os_splet.registriraj_most(u, adblock.STEVEC_MOST, adblock.STEVEC_SVET)
            u.connect("script-message-received::" + adblock.STEVEC_MOST, ob_stevcu)
        for koda, dovoljeni in glavni:
            u.add_script(WebKit.UserScript(koda, WebKit.UserContentInjectedFrames.ALL_FRAMES,
                                           WebKit.UserScriptInjectionTime.START, dovoljeni,
                                           adblock.AUTH_SCRIPT_EXCLUSIONS))
        pogled = WebKit.WebView(user_content_manager=u)
        okno = Gtk.Window()
        okno.set_child(pogled)
        okno.present()
        zanka = GLib.MainLoop()

        def po_js(p, rezultat, *_a):
            try:
                izid["most"] = p.evaluate_javascript_finish(rezultat).to_boolean()
            except Exception as e:  # noqa: BLE001
                izid["napaka"] = str(e)
            # Stetje skript pride v ~0,3 s; v CI (~5000 preizkusov v enem procesu) je spletni proces pocasnejsi.
            GLib.timeout_add(3000, lambda: (zanka.quit(), False)[1])

        def ob_nalaganju(_p, dogodek):
            if dogodek == WebKit.LoadEvent.FINISHED:
                GLib.timeout_add(500, lambda: (pogled.evaluate_javascript(JS_MOST, -1, None, None, None, po_js),
                                               False)[1])
        pogled.connect("load-changed", ob_nalaganju)
        pogled.load_html(stran, naslov)
        GLib.timeout_add_seconds(20, lambda: (izid.setdefault("napaka", "IZTEK"), zanka.quit(), False)[2])
        zanka.run()
        try:
            pogled.terminate_web_process()        # spletni proces ne ostane za drugimi preizkusi
        except Exception:  # noqa: BLE001
            pass
        okno.destroy()
        self.assertNotIn("napaka", izid, izid)
        self.assertIs(izid.get("most"), False, "stran v glavnem svetu vidi most stevca")
        return prejeto

    def test_adguard_steje(self):
        prejeto = self._nalozi(STRAN_ADGUARD, "https://stran.test/clanek",
                               [(adblock.ADGUARD_PROTECTION_SCRIPT, None)])
        self.assertEqual(sum(prejeto), 3, prejeto)

    def test_youtube_steje(self):
        prejeto = self._nalozi(STRAN_YOUTUBE, "https://www.youtube.com/watch?v=abcdefghijk",
                               [(adblock.YOUTUBE_ADBLOCK_SCRIPT, YOUTUBE)])
        self.assertEqual(sum(prejeto), 2, prejeto)

    def test_stran_neveljavnih_stevil_ne_poslje(self):
        self.assertEqual(self._nalozi(STRAN_NEVELJAVNI, "https://stran.test/"), [7])

    def test_stran_ne_preseze_meje_nalaganja(self):
        prejeto = self._nalozi(STRAN_POPLAVA, "https://stran.test/")
        self.assertEqual(sum(prejeto), NA_STRAN, prejeto)
        self.assertTrue(all(1 <= n <= NA_DOGODEK for n in prejeto), prejeto)


if __name__ == "__main__":
    unittest.main()
