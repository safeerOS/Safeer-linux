"""Spletni katalog v domacem Safeer Playerju (GTK 3, brez WebKita).

Isti katalog kot Medijski center na strani Safeer OS (core/os_katalog.Katalog): kategorije, zvrsti, jezik vsebine,
razvrstitev, strani, plakati. Omrezje bere samo delovna nit; GTK se dotika samo glavna nit (GLib.idle_add).
Logika izbir je v core/os_player_katalog.py.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Callable, Optional

from gi.repository import GdkPixbuf, Gio, GLib, Gtk, Pango

from core import os_katalog, os_player_katalog as pk, os_programi

SIRINA_PLAKATA, VISINA_PLAKATA = 150, 220


def _jezik_vmesnika() -> str:
    j = (os.environ.get("SAFEER_OS_JEZIK") or os.environ.get("LANG") or "sl")[:2].lower()
    return j if j in pk.IMENA_JEZIKOV else "sl"


class KatalogPogled(Gtk.Box):
    """Mreza kartic spletnega kataloga z izbirami. predvajaj(uri, vrsta, ime, zacetek, podnapisi) -> bool se klice
    v glavni niti; sporocilo(besedilo) pokaze kratko obvestilo."""

    def __init__(self, predvajaj: Callable[..., bool], sporocilo: Callable[[str], None],
                 config_dir: Optional[str] = None, katalog=None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.set_border_width(12)
        self._predvajaj = predvajaj
        self._sporocilo = sporocilo
        self._config_dir = config_dir or os.path.join(os_programi.MAPA_NASTAVITEV, "media")
        self._katalog = katalog
        self.vrsta, self.zvrst, self.jezik, self.razvrsti, self.stran, self.iskanje = "vse", "", "", "", 1, ""
        self._skupaj_strani = 1
        self._zahteva = 0
        self._kljuc = ""
        self._plakati = pk.Plakati()
        self._slike: dict = {}          # url -> [Gtk.Image, ...] na zaslonu
        self._casovnik_iskanja = 0
        self._polnim_izbire = False
        self.zadnji_cas_nalaganja: Optional[float] = None
        self._zgradi()

    # ------------------------------------------------------------------ katalog (jedro)
    @property
    def katalog(self):
        if self._katalog is None:
            self._katalog = os_katalog.Katalog(
                self._config_dir, self._dogodek, GLib.idle_add, predvajaj=self._predvajaj_iz_kataloga,
                vdelano=self._odpri_zunaj, youtube=lambda url, _ime: self._odpri_zunaj(url),
                youtube_ukaz=lambda _u: False, jezik=_jezik_vmesnika)
        return self._katalog

    def _predvajaj_iz_kataloga(self, uri, vrsta, ime, zacetek, podnapisi, _prikazi) -> bool:
        return bool(self._predvajaj(uri, vrsta, ime, zacetek, podnapisi))

    @staticmethod
    def _odpri_zunaj(url: str) -> bool:
        """Vgrajena spletna vsebina (YouTube, vdelani predvajalnik): brez WebKita jo odpre privzeti brskalnik."""
        try:
            return bool(url) and Gio.AppInfo.launch_default_for_uri(url, None)
        except GLib.Error:
            return False

    def _dogodek(self, ime: str, podatki) -> None:
        # Klican iz delovnih niti jedra; v GTK samo prek idle_add.
        if ime == "mediaKatalogOsvezen" and isinstance(podatki, dict) and podatki.get("kljuc") == self._kljuc:
            GLib.idle_add(self._narisi, podatki, self._zahteva)

    # ------------------------------------------------------------------ vmesnik
    def _zgradi(self) -> None:
        vrstica = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        vrstica.get_style_context().add_class("vrstica-orodna")
        self.kat_gumbi = {}
        for vid, napis in pk.KATEGORIJE:
            g = Gtk.Button(label=napis)
            g.connect("clicked", lambda _b, v=vid: self.izberi_vrsto(v))
            vrstica.pack_start(g, False, False, 0)
            self.kat_gumbi[vid] = g
        self.pack_start(vrstica, False, False, 0)

        izbire = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.izbira_zvrsti = Gtk.ComboBoxText()
        self.izbira_zvrsti.set_tooltip_text("Zvrst")
        self.izbira_zvrsti.connect("changed", self._ob_izbiri)
        self.izbira_jezika = Gtk.ComboBoxText()
        self.izbira_jezika.set_tooltip_text("Jezik vsebine")
        for koda, ime in pk.jeziki(_jezik_vmesnika()):
            self.izbira_jezika.append(koda or "-", ime)
        self.izbira_jezika.set_active_id("-")
        self.izbira_jezika.connect("changed", self._ob_izbiri)
        self.izbira_razvrsti = Gtk.ComboBoxText()
        self.izbira_razvrsti.set_tooltip_text("Razvrsti")
        for koda, ime in pk.RAZVRSTITVE:
            self.izbira_razvrsti.append(koda or "-", ime)
        self.izbira_razvrsti.set_active_id("-")
        self.izbira_razvrsti.connect("changed", self._ob_izbiri)
        for w in (self.izbira_zvrsti, self.izbira_jezika, self.izbira_razvrsti):
            izbire.pack_start(w, False, False, 0)
        self.stanje = Gtk.Label(label="", xalign=0)
        self.stanje.get_style_context().add_class("medlo")
        self.stanje.set_ellipsize(Pango.EllipsizeMode.END)
        izbire.pack_start(self.stanje, True, True, 8)
        self.btn_prejsnja = Gtk.Button(label="◀")
        self.btn_prejsnja.set_tooltip_text("Prejšnja stran")
        self.btn_prejsnja.connect("clicked", lambda *_: self.pojdi_na_stran(self.stran - 1))
        self.lbl_stran = Gtk.Label(label="")
        self.lbl_stran.get_style_context().add_class("medlo")
        self.btn_naslednja = Gtk.Button(label="▶")
        self.btn_naslednja.set_tooltip_text("Naslednja stran")
        self.btn_naslednja.connect("clicked", lambda *_: self.pojdi_na_stran(self.stran + 1))
        for w in (self.btn_naslednja, self.lbl_stran, self.btn_prejsnja):   # pack_end: prvi je skrajno desno
            izbire.pack_end(w, False, False, 0)
        self.pack_start(izbire, False, False, 0)

        self.drsnik = Gtk.ScrolledWindow()
        self.drsnik.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.mreza = Gtk.FlowBox()
        self.mreza.set_valign(Gtk.Align.START)
        self.mreza.set_max_children_per_line(30)
        self.mreza.set_selection_mode(Gtk.SelectionMode.NONE)
        self.mreza.set_homogeneous(True)
        self.mreza.set_column_spacing(12)
        self.mreza.set_row_spacing(12)
        self.drsnik.add(self.mreza)
        self.pack_start(self.drsnik, True, True, 0)
        self._napolni_zvrsti()
        self._oznaci_vrsto()

    def _oznaci_vrsto(self) -> None:
        for vid, g in self.kat_gumbi.items():
            ctx = g.get_style_context()
            (ctx.add_class if vid == self.vrsta else ctx.remove_class)("kategorija-izbrana")
        self.izbira_jezika.set_visible(pk.jezik_velja(self.vrsta))

    def _napolni_zvrsti(self) -> None:
        self._polnim_izbire = True
        self.izbira_zvrsti.remove_all()
        seznam = pk.zvrsti(self.vrsta)
        for zid, ime in seznam:
            self.izbira_zvrsti.append(zid or "-", ime)
        self.izbira_zvrsti.set_active_id("-")
        self.izbira_zvrsti.set_visible(bool(seznam))
        self.izbira_zvrsti.set_no_show_all(not seznam)
        self._polnim_izbire = False

    # ------------------------------------------------------------------ izbire
    def izberi_vrsto(self, vrsta: str) -> None:
        self.vrsta, self.zvrst, self.stran = vrsta, "", 1
        self._napolni_zvrsti()
        self._oznaci_vrsto()
        self.nalozi()

    def _ob_izbiri(self, *_a) -> None:
        if self._polnim_izbire:
            return
        vrednost = lambda w: "" if (w.get_active_id() or "-") == "-" else w.get_active_id()  # noqa: E731
        self.zvrst, self.jezik, self.razvrsti = (vrednost(self.izbira_zvrsti), vrednost(self.izbira_jezika),
                                                 vrednost(self.izbira_razvrsti))
        self.stran = 1
        self.nalozi()

    def isci(self, besedilo: str) -> None:
        """Iskanje iz glave okna: pocaka 400 ms po zadnji tipki (ne nalagamo ob vsaki crki)."""
        self.iskanje = str(besedilo or "").strip()
        if self._casovnik_iskanja:
            GLib.source_remove(self._casovnik_iskanja)

        def zdaj():
            self._casovnik_iskanja = 0
            self.stran = 1
            self.nalozi()
            return False
        self._casovnik_iskanja = GLib.timeout_add(400, zdaj)

    def pojdi_na_stran(self, stran: int) -> None:
        stran = max(1, min(int(stran), self._skupaj_strani))
        if stran != self.stran:
            self.stran = stran
            self.nalozi()

    # ------------------------------------------------------------------ nalaganje
    def nalozi(self) -> None:
        self._zahteva += 1
        zahteva = self._zahteva
        self._plakati.rod += 1
        self.stanje.set_text("Nalagam katalog …")
        argumenti = pk.argumenti(self.iskanje, self.vrsta, self.zvrst, self.stran, self.razvrsti, self.jezik)
        zacetek = time.monotonic()

        def delo():
            try:
                rezultat = self.katalog.izvedi("mediaKatalog", argumenti)
            except Exception as e:  # noqa: BLE001 - omrezje, vir
                print("[SafeerPlayerGTK] katalog:", type(e).__name__, flush=True)
                rezultat = None
            GLib.idle_add(self._narisi, rezultat, zahteva, time.monotonic() - zacetek)

        threading.Thread(target=delo, name="safeer-katalog", daemon=True).start()

    def _narisi(self, rezultat, zahteva: int, trajanje: Optional[float] = None) -> bool:
        if zahteva != self._zahteva:
            return False                       # uporabnik je medtem izbral drugo
        if trajanje is not None:
            self.zadnji_cas_nalaganja = trajanje
            print("[SafeerPlayerGTK] katalog %s/%s/%s stran %d: %.2f s" % (self.vrsta, self.zvrst or "-",
                  self.jezik or "-", self.stran, trajanje), flush=True)
        for otrok in self.mreza.get_children():
            self.mreza.remove(otrok)
        self._slike.clear()
        if not isinstance(rezultat, dict):
            self.stanje.set_text("Kataloga trenutno ni mogoče naložiti.")
            return False
        self._kljuc = str(rezultat.get("kljuc") or "")
        self._skupaj_strani = pk.strani(rezultat)
        vnosi = [x for x in (rezultat.get("vnosi") or []) if isinstance(x, dict)]
        if not vnosi:
            ime = pk.IMENA_JEZIKOV.get(self.jezik, "")
            self.stanje.set_text(("Ni vsebin v jeziku: %s. Izberi drug jezik ali zvrst." % ime.lower()) if ime
                                 else "Ni zadetkov. Spremeni iskanje ali zvrst.")
        else:
            self.stanje.set_text("Vsebin: %d%s" % (len(vnosi), " · osvežujem …" if rezultat.get("osvezujem") else ""))
        self.lbl_stran.set_text("Stran %d od %d" % (self.stran, self._skupaj_strani))
        self.btn_prejsnja.set_sensitive(self.stran > 1)
        self.btn_naslednja.set_sensitive(self.stran < self._skupaj_strani)
        for item in vnosi:
            self._kartica(pk.kartica(item))
        self.mreza.show_all()
        self.drsnik.get_vadjustment().set_value(0)
        return False

    def _kartica(self, k: dict) -> None:
        gumb = Gtk.Button()
        gumb.get_style_context().add_class("media-kartica")
        gumb.set_tooltip_text(k["naslov"])
        skatla = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        slika = Gtk.Image()
        slika.set_size_request(SIRINA_PLAKATA, VISINA_PLAKATA)
        nadomestek = Gtk.Image.new_from_icon_name(k["ikona"], Gtk.IconSize.DIALOG)
        nadomestek.set_pixel_size(72)
        okvir = Gtk.Stack()
        okvir.add_named(nadomestek, "ikona")
        okvir.add_named(slika, "slika")
        okvir.set_size_request(SIRINA_PLAKATA, VISINA_PLAKATA)
        skatla.pack_start(okvir, False, False, 0)
        naslov = Gtk.Label(label=k["naslov"])
        naslov.set_ellipsize(Pango.EllipsizeMode.END)
        naslov.set_max_width_chars(18)
        skatla.pack_start(naslov, False, False, 0)
        pod = Gtk.Label(label=k["podnaslov"])
        pod.get_style_context().add_class("medlo")
        pod.set_ellipsize(Pango.EllipsizeMode.END)
        pod.set_max_width_chars(20)
        skatla.pack_start(pod, False, False, 0)
        gumb.add(skatla)
        gumb.connect("clicked", lambda *_: self.predvajaj_id(k["id"], k["naslov"]))
        self.mreza.add(gumb)
        okvir.show_all()
        okvir.set_visible_child_name("ikona")
        if k["slika"]:
            self._slike.setdefault(k["slika"], []).append((slika, okvir))
            self._plakati.zahtevaj(k["slika"], lambda url, p, rod: GLib.idle_add(self._plakat, url, p, rod))

    def _plakat(self, url: str, podatki: Optional[bytes], rod: int) -> bool:
        if rod != self._plakati.rod or not podatki:
            return False
        try:
            nalagalnik = GdkPixbuf.PixbufLoader()
            nalagalnik.write(podatki)
            nalagalnik.close()
            pix = nalagalnik.get_pixbuf()
        except GLib.Error:
            return False
        if pix is None:
            return False
        s, v = pix.get_width(), pix.get_height()
        merilo = min(SIRINA_PLAKATA / max(1, s), VISINA_PLAKATA / max(1, v))
        pix = pix.scale_simple(max(1, int(s * merilo)), max(1, int(v * merilo)), GdkPixbuf.InterpType.BILINEAR)
        for slika, okvir in self._slike.get(url, []):
            slika.set_from_pixbuf(pix)
            okvir.set_visible_child_name("slika")
        return False

    # ------------------------------------------------------------------ predvajanje
    def predvajaj_id(self, ident: str, naslov: str = "") -> None:
        if not ident:
            return
        self._sporocilo("Odpiram »%s« …" % naslov[:60])

        def delo():
            try:
                izid = self.katalog.izvedi("mediaPredvajaj", [ident])
            except Exception as e:  # noqa: BLE001
                print("[SafeerPlayerGTK] predvajanje:", type(e).__name__, flush=True)
                izid = None
            GLib.idle_add(self._po_predvajanju, izid, naslov)

        threading.Thread(target=delo, name="safeer-katalog-predvajaj", daemon=True).start()

    def _po_predvajanju(self, izid, naslov: str) -> bool:
        if not isinstance(izid, dict):
            self._sporocilo("Te vsebine trenutno ni mogoče odpreti.")
        elif izid.get("napaka_koda") == "ni_toka":
            self._sporocilo("»%s« trenutno ni na voljo v tvojih virih." % naslov[:60])
        elif izid.get("napaka_koda"):
            self._sporocilo("Te vsebine trenutno ni mogoče predvajati.")
        elif izid.get("napaka") or izid.get("sporocilo"):
            self._sporocilo(str(izid.get("napaka") or izid.get("sporocilo"))[:200])
        elif izid.get("stran") and not izid.get("native"):
            self._odpri_zunaj(str(izid["stran"]))
        return False

    def ustavi(self) -> None:
        self._zahteva += 1
        self._plakati.ustavi()
