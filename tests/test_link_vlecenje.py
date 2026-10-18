"""Vlecenje datotek v okno Safeer Linka (in Datoteke Safeer OS) iz drugih programov (pregled 18. 10. 2026).

Program v drugem procesu (Nemo, program X11 prek XWayland, Electron) ponudi samo vrste MIME (text/uri-list), brez
GType Gdk.FileList; Flatpak dobi datoteke prek portala dokumentov (/run/user/<uid>/doc/...). Prej je okno bralo samo,
ce je Gdk.Drop ze nosil GType - datoteke iz drugih procesov niso prisle nikoli.

Gdk.Drop je lazen, pretvorba pa prava: GTK iz istih bajtov sestavi Gdk.FileList (Gdk.content_deserialize_async), kot
to naredi Gdk.Drop.read_value_async za program iz drugega procesa.
"""
import os
import shutil
import tempfile
import time
import types
import unittest
import urllib.parse

try:
    import gi
    gi.require_version("Gdk", "4.0")
    from gi.repository import Gdk, Gio, GLib
except Exception:  # noqa: BLE001
    Gdk = None

from core import os_datoteke


class LazniSpust:
    """Gdk.Drop programa iz drugega procesa: samo vrste MIME in bajti v teh vrstah."""

    def __init__(self, vrste, podatki: bytes, seznam=None):
        self.formati = Gdk.ContentFormats.new(list(vrste))
        if seznam is not None:
            # Flatpak: GTK v peskovniku sestavi FileList iz portala dokumentov (application/vnd.portal.filetransfer).
            self.formati = self.formati.union(Gdk.ContentFormats.new_for_gtype(Gdk.FileList.__gtype__))
        self.podatki = podatki
        self.seznam = seznam
        self._vrednost = None

    def get_formats(self):
        return self.formati

    def read_value_async(self, gtype, prio, _preklic, klic):
        if self.seznam is not None:
            self._vrednost = self.seznam
            GLib.idle_add(lambda: (klic(self, None), False)[1])
            return
        tok = Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(self.podatki))

        def konec(_o, izid):
            try:
                ok, vrednost = Gdk.content_deserialize_finish(izid)
                self._vrednost = vrednost if ok else None
            except GLib.Error:
                self._vrednost = None
            klic(self, izid)
        Gdk.content_deserialize_async(tok, "text/uri-list", gtype, prio, None, konec)

    def read_value_finish(self, _izid):
        if self._vrednost is None:
            raise GLib.Error("ni seznama")
        return self._vrednost

    def read_async(self, vrste, _prio, _preklic, klic):
        self._vrste = vrste
        GLib.idle_add(lambda: (klic(self, None), False)[1])

    def read_finish(self, _izid):
        return Gio.MemoryInputStream.new_from_bytes(GLib.Bytes.new(self.podatki)), "text/uri-list"


def _vrti(pogoj, rok=5.0):
    """Glavna zanka GLib, dokler pogoj ne velja (najvec `rok` sekund - brez visenja, ce odziva ni)."""
    ctx = GLib.MainContext.default()
    konec = time.monotonic() + rok
    while not pogoj() and time.monotonic() < konec:
        if not ctx.iteration(False):
            time.sleep(0.005)


@unittest.skipIf(Gdk is None, "GTK 4 ni na voljo")
class Vlecenje(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp(prefix="safeer-vlecenje-")
        self.a = os.path.join(self.mapa, "a b.txt")
        self.c = os.path.join(self.mapa, "č.txt")
        for p in (self.a, self.c):
            with open(p, "w") as d:
                d.write("x")

    def tearDown(self):
        shutil.rmtree(self.mapa, ignore_errors=True)

    def _preberi(self, spust):
        izid = {}
        os_datoteke.preberi_vlecene(spust, lambda s, poti: izid.setdefault("poti", poti))
        _vrti(lambda: "poti" in izid)
        return izid.get("poti")

    def test_program_iz_drugega_procesa_samo_mime(self):
        formati = Gdk.ContentFormats.new(["text/uri-list"])
        self.assertFalse(formati.contain_gtype(Gdk.FileList.__gtype__), "zato prejsnje preverjanje ni prebralo nic")
        self.assertEqual(os_datoteke.vrsta_vlecenja(formati), "seznam")
        self.assertEqual(os_datoteke.vrsta_vlecenja(Gdk.ContentFormats.new(["text/html"])), "")

    def test_xwayland_in_electron(self):
        # CRLF, odstotki, ime gostitelja localhost, NUL na koncu (X11) in naslov http, ki ni datoteka.
        bajti = ("file://%s\r\nfile://localhost%s\r\nhttps://primer.si/x\r\n\x00" % (
            urllib.parse.quote(self.a), self.c)).encode()
        poti = self._preberi(LazniSpust(["text/uri-list", "text/plain;charset=utf-8"], bajti))
        self.assertEqual(poti, [self.a, self.c])

    def test_flatpak_portal_dokumentov(self):
        doc = "/run/user/1000/doc/1a2b3c4d/Slika.png"
        seznam = Gdk.FileList.new_from_list([Gio.File.new_for_path(doc)])
        poti = self._preberi(LazniSpust(["application/vnd.portal.filetransfer"], b"", seznam=seznam))
        self.assertEqual(poti, [doc])

    def test_surove_poti_namesto_naslovov(self):
        # Nekateri programi (Java, starejsi Electron) v text/uri-list posljejo kar pot: GTK iz nje ne sestavi
        # datoteke, zato preberemo surovo. Pot, ki je na racunalniku ni, izpade.
        bajti = ("# komentar\n%s\n/ni/take/datoteke\n" % self.a).encode()
        poti = self._preberi(LazniSpust(["text/uri-list"], bajti))
        self.assertEqual(poti, [self.a])

    def test_okno_linka_prevzame_poti(self):
        from core import safeer_link
        okno = types.SimpleNamespace(_vleceno_kontekst=None, _vlecene_poti=[])
        spust = LazniSpust(["text/uri-list"], ("file://%s\r\n" % self.c).encode())
        safeer_link.SafeerLink._na_vlecene_datoteke(okno, spust)
        _vrti(lambda: okno._vlecene_poti)
        self.assertEqual(okno._vlecene_poti, [self.c])


class SeznamNaslovov(unittest.TestCase):
    def test_brez_gtk(self):
        self.assertEqual(os_datoteke.poti_iz_seznama_naslovov(b"file:///run/user/1000/doc/ab/x.txt\r\n\x00"),
                         ["/run/user/1000/doc/ab/x.txt"])
        self.assertEqual(os_datoteke.poti_iz_naslovov(["file:///a/b.txt\x00"]), ["/a/b.txt"])


if __name__ == "__main__":
    unittest.main()
