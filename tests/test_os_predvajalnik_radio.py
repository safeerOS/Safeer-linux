"""Radio v zivo: medpomnjenje, ponovna povezava in statistika - z nadomestnim GStreamerjem (brez zvocne naprave)."""

import unittest
from types import SimpleNamespace

from core import os_predvajalnik as op
from core.os_predvajalnik import Predvajalnik

RADIO = "https://cast1.torontocast.com:4610/stream"


class Element:
    """playbin, izvor ali izhod: lastnosti, stanja in signali."""

    def __init__(self, tovarna="playbin", vrsta="Generic/Bin/Player", lastnosti=()):
        self.stanja = []
        self.lastnosti = {}
        self.signali = {}
        self.skoki = []
        self.znane = set(lastnosti)
        self.tovarna = SimpleNamespace(get_name=lambda: tovarna, get_metadata=lambda _k: vrsta)
        self.vodilo = SimpleNamespace(add_signal_watch=lambda: None,
                                     remove_signal_watch=lambda: None, connect=lambda *_: None)

    def get_bus(self):
        return self.vodilo

    def get_factory(self):
        return self.tovarna

    def connect(self, signal, f):
        self.signali[signal] = f

    def find_property(self, ime):
        return ime if ime in self.znane else None

    def set_state(self, stanje):
        self.stanja.append(stanje)
        return "ok"

    def set_property(self, ime, vrednost):
        self.lastnosti[ime] = vrednost

    def get_property(self, ime):
        return self.lastnosti.get(ime, {"flags": 0x617, "n-text": 0, "current-text": -1}.get(ime))

    def emit(self, _signal, _i):
        return None

    def query_duration(self, _format):
        return False, 0

    def query_position(self, _format):
        return True, 0

    def seek_simple(self, *a):
        self.skoki.append(a)
        return True


def sporocilo(tip, **kw):
    return SimpleNamespace(type=tip, **kw)


def napaka():
    return sporocilo("error", parse_error=lambda: (SimpleNamespace(domain="gst-resource-error-quark", code=7), ""))


class RadioTests(unittest.TestCase):
    def setUp(self):
        self.element = Element()
        self.gst = SimpleNamespace(ElementFactory=SimpleNamespace(make=lambda *_: self.element),
                                   State=SimpleNamespace(NULL="null", READY="ready", PLAYING="playing", PAUSED="paused"),
                                   StateChangeReturn=SimpleNamespace(FAILURE="failure"),
                                   Format=SimpleNamespace(TIME="time"), SECOND=1_000_000_000,
                                   CLOCK_TIME_NONE=2**64 - 1,
                                   SeekFlags=SimpleNamespace(FLUSH=1, KEY_UNIT=2),
                                   MessageType=SimpleNamespace(EOS="eos", ERROR="error", ASYNC_DONE="async_done",
                                                               BUFFERING="buffering", QOS="qos"))
        self.player = Predvajalnik(self.gst)
        self.cas = [100.0]
        self.player._ura = lambda: self.cas[0]
        self.odlozeni = []
        self.player.cez = lambda s, f: self.odlozeni.append((s, f))
        self.konci = []
        self.player.konec = self.konci.append

    def radio(self):
        self.player.dodaj(RADIO, predvajaj=True, vrsta="radio", naslov="RdMix Classic Rock")

    def buffering(self, odstotek):
        self.player._sporocilo(None, sporocilo("buffering", parse_buffering=lambda: odstotek))

    def stalno_predvaja(self):
        self.buffering(10)
        self.buffering(100)

    def test_radio_dobi_medpomnjenje_datoteka_pa_privzete_nastavitve(self):
        self.player.dodaj("https://example.test/pesem.mp3")
        for ime in ("buffer-duration", "buffer-size", "connection-speed"):
            self.assertNotIn(ime, self.element.lastnosti)          # datoteke: playbin kot doslej
        self.radio()
        self.assertTrue(self.element.lastnosti["flags"] & op.ZASTAVICA_MEDPOMNJENJE)
        self.assertEqual(self.element.lastnosti["buffer-duration"], 10 * self.gst.SECOND)
        self.assertEqual(self.element.lastnosti["buffer-size"], 1 << 20)
        self.assertEqual(self.element.lastnosti["connection-speed"], 320)
        self.player.dodaj("https://example.test/film.mp4", predvajaj=True, vrsta="video")
        self.assertFalse(self.element.lastnosti["flags"] & op.ZASTAVICA_MEDPOMNJENJE)
        self.assertEqual(self.element.lastnosti["flags"] & 0x617, 0x617 & ~op.ZASTAVICA_BESEDILO)
        self.assertEqual(self.element.lastnosti["buffer-duration"], -1)
        self.assertEqual(self.element.lastnosti["buffer-size"], -1)
        self.assertEqual(self.element.lastnosti["connection-speed"], 0)

    def test_tv_ni_radio(self):
        self.player.dodaj("https://example.test/live.m3u8", vrsta="tv")
        self.assertFalse(self.player._zivo)
        self.assertNotIn("buffer-duration", self.element.lastnosti)

    def test_izvor_in_izhod_samo_za_radio(self):
        izvor = Element("souphttpsrc", "Source/Network", ("timeout", "retries", "keep-alive", "is-live"))
        izhod = Element("pulsesink", "Sink/Audio", ("buffer-time", "latency-time", "qos"))
        vrsta = Element("queue2", "Generic", ("use-buffering", "high-watermark"))
        self.player.dodaj("https://example.test/pesem.mp3")
        self.element.signali["source-setup"](self.element, izvor)
        self.element.signali["deep-element-added"](self.element, None, izhod)
        self.assertEqual(izvor.lastnosti, {})
        self.assertEqual(izhod.lastnosti, {})
        self.radio()
        self.element.signali["source-setup"](self.element, izvor)
        self.element.signali["deep-element-added"](self.element, None, izhod)
        self.element.signali["deep-element-added"](self.element, None, vrsta)
        self.assertEqual(izvor.lastnosti, {"timeout": 8, "retries": 3, "keep-alive": True, "is-live": False})
        self.assertEqual(izhod.lastnosti, {"buffer-time": 1_000_000, "latency-time": 50_000, "qos": True})
        self.assertEqual(vrsta.lastnosti, {"use-buffering": True, "high-watermark": 0.4})
        video = Element("xvimagesink", "Sink/Video", ("qos",))
        self.element.signali["deep-element-added"](self.element, None, video)
        self.assertEqual(video.lastnosti, {})

    def test_medpomnjenje_pocaka_in_nadaljuje_brez_spremembe_stanja(self):
        self.radio()
        self.buffering(20)
        self.assertEqual(self.element.stanja[-1], "paused")
        self.assertEqual(self.player.stanje, "predvaja")
        self.buffering(60)
        self.assertEqual(self.element.stanja.count("paused"), 1)
        self.buffering(100)
        self.assertEqual(self.element.stanja[-1], "playing")
        self.assertEqual(self.player.statistika["medpomnjenja"], 0)   # zacetno polnjenje ni zastoj
        self.buffering(0)
        self.cas[0] += 3
        self.buffering(100)
        self.assertEqual(self.player.statistika["medpomnjenja"], 1)
        self.assertAlmostEqual(self.player.statistika["zastoj_s"], 3.0)
        self.assertEqual(self.player.statistika["ponovne_povezave"], 0)

    def test_nakopicen_zaostanek_skoci_na_zivi_rob(self):
        self.radio()
        self.stalno_predvaja()
        for _ in range(3):
            self.buffering(0)
            self.cas[0] += 6
            self.buffering(100)
        self.assertEqual(self.player.statistika["skoki_na_zivo"], 1)
        self.assertEqual(self.player.statistika["ponovne_povezave"], 1)
        self.assertEqual(self.element.stanja[-2:], ["null", "playing"])
        self.assertEqual(self.player._zaostanek, 0)

    def test_napaka_tiho_poveze_znova_z_odmiki_nato_sporocilo(self):
        self.radio()
        self.stalno_predvaja()
        odmiki = []
        for _ in range(5):
            self.player._sporocilo(None, napaka())
            self.assertEqual(self.player.stanje, "predvaja")
            self.assertEqual(self.player.napaka, "")
            s, f = self.odlozeni.pop()
            odmiki.append(s)
            f()
            self.assertEqual(self.element.lastnosti["uri"], RADIO)
            self.assertEqual(self.element.stanja[-1], "playing")
        self.assertEqual(odmiki, [1, 2, 4, 8, 8])
        self.player._sporocilo(None, napaka())
        # Lastnik 18. 10. 2026: po zadnjem poskusu tiha ustavitev (sled v stderr), brez sporocila uporabniku.
        self.assertEqual(self.player.stanje, "ustavljeno")
        self.assertEqual(self.player.napaka, "")
        self.assertEqual(self.element.stanja[-1], "null")
        self.assertEqual(self.player.statistika["ponovne_povezave"], 5)
        stanja = len(self.element.stanja)
        for _, f in list(self.odlozeni):
            f()                                                      # stare odlozene povezave ne veljajo vec
        self.assertEqual(len(self.element.stanja), stanja)

    def _do_konca_poskusov(self):
        for _ in range(5):
            self.player._sporocilo(None, napaka())
            self.odlozeni.pop()[1]()
        self.player._sporocilo(None, napaka())

    def test_po_zadnjem_poskusu_naslednja_postaja(self):
        self.radio()
        self.player.dodaj("https://example.test/druga-postaja", vrsta="radio", naslov="Druga")
        self._do_konca_poskusov()
        self.assertEqual((self.player.trenutna.naslov, self.player.stanje, self.player.napaka), ("Druga", "predvaja", ""))
        self.assertEqual(self.element.lastnosti["uri"], "https://example.test/druga-postaja")

    def test_po_zadnjem_poskusu_ne_na_skladbo_ki_ni_postaja(self):
        self.radio()
        self.player.dodaj("https://example.test/pesem.mp3")
        self._do_konca_poskusov()
        self.assertEqual((self.player.trenutna.uri, self.player.stanje), (RADIO, "ustavljeno"))

    def test_trajna_napaka_brez_ponovnih_poskusov(self):
        """format/zascita: ponovna povezava ne pomaga (pregled 18. 10. 2026) - takoj tiho naprej."""
        for domena, koda in (("gst-stream-error-quark", 6), ("gst-stream-error-quark", 13)):
            self.radio()
            self.odlozeni.clear()
            trajna = sporocilo("error", parse_error=lambda d=domena, k=koda: (SimpleNamespace(domain=d, code=k), ""))
            self.player._sporocilo(None, trajna)
            self.assertEqual(self.odlozeni, [])
            self.assertEqual((self.player.stanje, self.player.napaka), ("ustavljeno", ""))
            self.assertEqual(self.player.statistika["ponovne_povezave"], 0)

    def test_eos_radia_ni_konec_vrste(self):
        self.radio()
        self.player.dodaj("https://example.test/naslednja.mp3")
        self.player._sporocilo(None, sporocilo("eos"))
        self.assertEqual(self.konci, [])
        self.assertEqual(self.player.trenutna.uri, RADIO)
        self.assertEqual(self.odlozeni[-1][0], 1)

    def test_stabilno_predvajanje_ponastavi_poskuse(self):
        self.radio()
        self.stalno_predvaja()
        self.player._sporocilo(None, napaka())
        self.odlozeni.pop()[1]()
        self.player._sporocilo(None, napaka())
        self.assertEqual(self.odlozeni.pop()[0], 2)
        self.player._povezi_znova()
        self.stalno_predvaja()
        self.cas[0] += 31
        self.player._sporocilo(None, napaka())
        self.assertEqual(self.odlozeni.pop()[0], 1)

    def test_ustavitev_preklice_cakajoco_povezavo(self):
        self.radio()
        self.player._sporocilo(None, napaka())
        self.player.ustavi()
        stanja = len(self.element.stanja)
        self.odlozeni.pop()[1]()
        self.assertEqual(len(self.element.stanja), stanja)
        self.assertEqual(self.player.stanje, "ustavljeno")

    def test_dolgo_medpomnjenje_sprozi_ponovno_povezavo(self):
        self.radio()
        self.stalno_predvaja()
        self.buffering(0)
        s, cuvaj = self.odlozeni.pop()
        self.assertEqual(s, op.ZIVO_ZASTOJ_MEJA_S)
        cuvaj()
        self.assertEqual(self.odlozeni[-1][0], 1)                  # ponovna povezava cez 1 s
        # Ce se medpomnjenje medtem konca, cuvaj ne naredi nicesar.
        self.player._povezi_znova()
        self.buffering(0)
        _, cuvaj = self.odlozeni.pop()
        self.buffering(100)
        cuvaj()
        self.assertEqual(self.element.stanja[-1], "playing")

    def test_premor_takoj_utisa_tok_tece_nadaljevanje_brez_stare_zaloge(self):
        """Lastnik 18. 10. 2026: premor zamuja, po nadaljevanju tisina ali stara pesem. Premor radia ne ustavi cevovoda
        (PAUSED je pustil zalogo starega zvoka), ampak ga takoj utisa; nadaljevanje utisanje odstrani - brez povezovanja."""
        self.radio()
        self.stalno_predvaja()
        stanja = len(self.element.stanja)
        self.player.premor()
        self.assertEqual(self.player.stanje, "premor")
        self.assertIs(self.element.lastnosti["mute"], True)
        self.assertNotIn("paused", self.element.stanja[stanja:])       # tok tece naprej (zivi rob)
        self.cas[0] += 12
        self.player.premor()
        self.assertEqual(self.player.stanje, "predvaja")
        self.assertIs(self.element.lastnosti["mute"], False)
        self.assertNotIn("paused", self.element.stanja[stanja:])
        self.assertEqual(self.player.statistika["ponovne_povezave"], 0)
        self.assertEqual(self.player.statistika["skoki_na_zivo"], 0)

    def test_dolg_premor_sprosti_povezavo_nadaljevanje_poveze_znova_na_zivi_rob(self):
        self.radio()
        self.stalno_predvaja()
        self.odlozeni.clear()
        self.player.premor()
        s, sprosti = self.odlozeni.pop()
        self.assertEqual(s, op.ZIVO_PREMOR_TOPLO_S)
        sprosti()
        self.assertEqual(self.element.stanja[-1], "null")             # omrezje in mesto pri strezniku sta prosta
        self.assertEqual(self.player.stanje, "premor")
        self.player.premor()
        self.assertEqual((self.player.stanje, self.element.stanja[-2:]), ("predvaja", ["null", "playing"]))
        self.assertEqual(self.element.lastnosti["uri"], RADIO)
        self.assertIs(self.element.lastnosti["mute"], False)
        self.assertEqual(self.player.statistika["ponovne_povezave"], 1)

    def test_nadaljevanje_po_sprostitvi_zacne_z_nizjo_zalogo(self):
        """Uporabnik caka na zvok: prvo polnjenje do 10 % (meritev: tisina 1,2 s -> 44 ms z izbruhom streznika)."""
        self.radio()
        self.stalno_predvaja()
        self.odlozeni.clear()
        self.player.premor()
        self.odlozeni.pop()[1]()                                       # sprostitev po ZIVO_PREMOR_TOPLO_S
        self.player.premor()
        vrsta = Element("queue2", "Generic", ("use-buffering", "high-watermark"))
        self.element.signali["deep-element-added"](self.element, None, vrsta)
        self.assertEqual(vrsta.lastnosti["high-watermark"], op.ZIVO_NADALJUJ_ZALOGA)
        self.stalno_predvaja()
        self.assertEqual(vrsta.lastnosti["high-watermark"], op.ZIVO_ZACETNA_ZALOGA)
        nova = Element("queue2", "Generic", ("use-buffering", "high-watermark"))
        self.radio()                                                   # nov zacetek: obicajna zaloga
        self.element.signali["deep-element-added"](self.element, None, nova)
        self.assertEqual(nova.lastnosti["high-watermark"], op.ZIVO_ZACETNA_ZALOGA)

    def test_sprostitev_po_nadaljevanju_ne_velja(self):
        self.radio()
        self.stalno_predvaja()
        self.odlozeni.clear()
        self.player.premor()
        _, sprosti = self.odlozeni.pop()
        self.player.premor()
        stanja = len(self.element.stanja)
        sprosti()
        self.assertEqual(len(self.element.stanja), stanja)
        self.assertEqual(self.player.stanje, "predvaja")

    def test_prekinitev_med_tihim_premorom_poveze_utisano(self):
        self.radio()
        self.stalno_predvaja()
        self.player.premor()
        self.odlozeni.clear()
        self.player._sporocilo(None, napaka())
        s, f = self.odlozeni.pop()
        self.assertEqual(s, 1)
        f()
        self.assertEqual((self.player.stanje, self.element.lastnosti["mute"]), ("premor", True))
        self.assertEqual(self.element.stanja[-1], "playing")
        self.player.premor()
        self.assertEqual((self.player.stanje, self.element.lastnosti["mute"]), ("predvaja", False))
        self.assertEqual(self.player.statistika["ponovne_povezave"], 1)

    def test_nadaljevanje_med_cakanjem_na_povezavo_poveze_takoj(self):
        self.radio()
        self.stalno_predvaja()
        self.player.premor()
        self.odlozeni.clear()
        self.player._sporocilo(None, napaka())
        _, odlozena = self.odlozeni.pop()
        self.player.premor()
        self.assertEqual(self.player.statistika["ponovne_povezave"], 1)
        self.assertEqual(self.element.stanja[-1], "playing")
        stanja = len(self.element.stanja)
        odlozena()                                                    # zastarela, ne poveze se drugic
        self.assertEqual(len(self.element.stanja), stanja)

    def test_zastoj_med_tihim_premorom_pocaka_in_tece_naprej(self):
        self.radio()
        self.stalno_predvaja()
        self.player.premor()
        self.buffering(0)
        self.assertEqual(self.element.stanja[-1], "paused")
        self.buffering(100)
        self.assertEqual((self.element.stanja[-1], self.player.stanje), ("playing", "premor"))

    def test_nov_posnetek_po_tihem_premoru_ni_utisan(self):
        self.radio()
        self.player.premor()
        self.player.dodaj("https://example.test/pesem.mp3", predvajaj=True)
        self.assertIs(self.element.lastnosti["mute"], False)
        self.radio()
        self.player.premor()
        self.player.ustavi()
        self.assertIs(self.element.lastnosti["mute"], False)

    def test_premor_datoteke_ostane_pravi_premor(self):
        self.player.dodaj("https://example.test/pesem.mp3")
        self.player.premor()
        self.assertEqual(self.element.stanja[-1], "paused")
        self.assertFalse(self.element.lastnosti.get("mute"))

    def test_podtoki_izhoda_se_stejejo(self):
        self.radio()
        izhod = Element("pulsesink", "Sink/Audio", ("buffer-time",))
        for _ in range(3):
            self.player._sporocilo(None, sporocilo("qos", src=izhod))
        self.player._sporocilo(None, sporocilo("qos", src=Element("x", "Sink/Video")))
        self.assertEqual(self.player.statistika["podtoki"], 3)

    def test_datoteka_ignorira_medpomnjenje(self):
        self.player.dodaj("https://example.test/pesem.mp3")
        self.buffering(10)
        self.assertNotIn("paused", self.element.stanja)


if __name__ == "__main__":
    unittest.main()
