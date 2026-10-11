"""Katalog Medijskega centra v GTK Safeer Playerju (filmi, serije, glasba, radio, TV v zivo).

Kot katalog na strani (assets/os/os.js: naloziKatalog, narisiKatalog, odpriKatalogPodrobnosti, odpriKatalogVnos):
iste metode mostu (mediaKatalog, mediaZvrsti, mediaPodrobnosti, mediaSezona, mediaEpizoda, mediaFilm, mediaPredvajaj),
isti dogodki (mediaKatalogOsvezen, mediaNiNaVoljo), ista besedila. Plakati se prenasajo v ozadju (os_player_katalog).
"""
from __future__ import annotations

from typing import Any, Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf, GLib, Gtk, Pango  # noqa: E402

from core import os_player_gtk_ikone as ikone  # noqa: E402
from core import os_player_katalog as pk  # noqa: E402

#: Kategorija Medijskega centra -> vrsta v katalogu (KAT_VRSTE v os.js); slike so samo krajevne.
KAT_VRSTE = {"vse": "vse", "glasba": "glasba", "video": "video", "filmi": "film", "serije": "serija",
             "tv": "tv-v-zivo", "radio": "radio", "slike": ""}
FILMSKI_ZANRI = (("28", "katZanr_akcija"), ("878", "katZanr_scifi"), ("35", "katZanr_komedija"),
                 ("27", "katZanr_grozljivka"), ("18", "katZanr_drama"), ("53", "katZanr_triler"),
                 ("16", "katZanr_animirani"), ("10749", "katZanr_romantika"))
RAZVRSTI = (("", "katRazPriporoceno"), ("novo", "katRazNovo"), ("staro", "katRazStaro"), ("az", "katRazAZ"),
            ("za", "katRazZA"))
OZNAKE = {"glasba": "media_glasba", "video": "media_video", "radio": "media_radio", "tv-v-zivo": "media_tv",
          "serija": "media_serije", "film": "media_filmi", "slika": "media_slike"}
SIRINA_PLAKATA, VISINA_PLAKATA = 168, 240


def skupina_zanrov(vrsta: str) -> str:
    if vrsta in ("film", "serija", "vse"):
        return "film"
    return vrsta if vrsta in ("glasba", "radio", "tv-v-zivo") else ""


def oznaka(t, vrsta: str) -> str:
    k = OZNAKE.get(vrsta)
    return t(k) if k else ("Podcast" if vrsta == "podcast" else t("media_filmi"))


def meta(t, x: dict) -> str:
    """Vrstica pod naslovom kartice kot na strani: vrsta, v zivo, kodek, SxxEyy, leto; pri skladbi izvajalec."""
    if x.get("vrsta") == "glasba" and x.get("izvajalec"):
        return str(x["izvajalec"])
    deli = [oznaka(t, str(x.get("vrsta") or ""))]
    if x.get("v_zivo"):
        deli.append(t("katVZivo"))
    if x.get("codec") or x.get("bitrate"):
        deli.append(" ".join(p for p in (str(x.get("codec") or ""), "%s kb/s" % x["bitrate"] if x.get("bitrate") else "") if p))
    if x.get("vrsta") == "serija" and (x.get("sezona") or x.get("epizoda")):
        deli.append("S%02dE%02d" % (int(x.get("sezona") or 1), int(x.get("epizoda") or 1)))
    if x.get("leto"):
        deli.append(str(x["leto"]))
    return " · ".join(deli)


def odpre_podrobnosti(x: dict) -> bool:
    """Kot klik na kartico na strani: film ali serija iz TMDB odpre podrobnosti, ostalo se predvaja takoj."""
    return bool(x.get("tmdb_id") or x.get("vrsta") == "serija" or (x.get("vrsta") == "film" and not x.get("peertube_uuid")))


class KatalogBlok(Gtk.Box):
    """Blok kataloga pod knjiznico. ``okno`` je SafeerPlayerOkno (klic, t, obvesti, odpri_splet)."""

    def __init__(self, okno) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.okno = okno
        self.t = okno.t
        self.vrsta = "vse"
        self.iskanje = ""
        self.zanr = ""
        self.stran = 1
        self.razvrsti = ""
        self.vnosi: list = []
        self.skupaj: Optional[int] = None
        self.skupaj_strani = 1
        self.kljuc = ""
        self.nalozen = False
        self._zahteva = 0
        self._zahteva_predvajanja = 0
        self._zanri_za = None
        self._casovnik = 0
        self.plakati = pk.Plakati()
        self._zgradi()
        okno.most.naroci("mediaKatalogOsvezen", self._ob_osvezenem)
        okno.most.naroci("mediaNiNaVoljo", self._ob_ni_na_voljo)
        self.connect("destroy", lambda *_: self.plakati.ustavi())

    # ------------------------------------------------------------------ gradnja
    def _zgradi(self) -> None:
        from core.os_player_gtk import _gumb, _oznaka
        t = self.t
        glava = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        levo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        levo.pack_start(_oznaka(t("katKicker"), "kicker"), False, False, 0)
        self.naslov = _oznaka(t("katVseVsebine"), "h2")
        levo.pack_start(self.naslov, False, False, 0)
        glava.pack_start(levo, False, False, 0)
        self.izbira_razvrsti = Gtk.ComboBoxText()
        for vrednost, kljuc in RAZVRSTI:
            self.izbira_razvrsti.append(vrednost or "-", t(kljuc))
        self.izbira_razvrsti.set_active_id("-")
        self.izbira_razvrsti.connect("changed", self._ob_razvrsti)
        glava.pack_end(self.izbira_razvrsti, False, False, 0)
        glava.pack_end(_oznaka(t("katRazvrsti"), "medlo"), False, False, 0)
        self.pack_start(glava, False, False, 0)

        self.zanri = Gtk.FlowBox()
        self.zanri.set_selection_mode(Gtk.SelectionMode.NONE)
        self.zanri.set_max_children_per_line(12)
        self.zanri.set_column_spacing(4)
        self.zanri.set_row_spacing(4)
        self.pack_start(self.zanri, False, False, 0)
        self.povzetek = _oznaka("", "medlo")
        self.pack_start(self.povzetek, False, False, 0)
        self.mreza = Gtk.FlowBox()
        self.mreza.set_selection_mode(Gtk.SelectionMode.NONE)
        self.mreza.set_homogeneous(True)
        self.mreza.set_min_children_per_line(2)
        self.mreza.set_max_children_per_line(10)
        self.mreza.set_column_spacing(14)
        self.mreza.set_row_spacing(16)
        self.pack_start(self.mreza, False, False, 0)
        self.prazno = _oznaka("", "medlo", 0.5, True)
        self.pack_start(self.prazno, False, False, 0)
        self.strani = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.strani.set_halign(Gtk.Align.CENTER)
        self.gumb_prej = _gumb(t("katPrejsnjaStran"))
        self.gumb_prej.connect("clicked", lambda *_: self.pojdi_na_stran(self.stran - 1))
        self.napis_strani = _oznaka("", "medlo")
        self.gumb_nasl = _gumb(t("katNaslednjaStran"))
        self.gumb_nasl.connect("clicked", lambda *_: self.pojdi_na_stran(self.stran + 1))
        for w in (self.gumb_prej, self.napis_strani, self.gumb_nasl):
            self.strani.pack_start(w, False, False, 0)
        self.pack_start(self.strani, False, False, 0)

    # ------------------------------------------------------------------ nalaganje
    def uskladi(self, filter_knjiznice: str, iskanje: str) -> None:
        """Kot uskladiKatalog: katalog sledi kategoriji in iskanju knjiznice (iskanje z zamikom 350 ms)."""
        vrsta = KAT_VRSTE.get(filter_knjiznice, "vse")
        iskanje = str(iskanje or "").strip()
        if self.nalozen and vrsta == self.vrsta and iskanje == self.iskanje:
            return
        samo_iskanje = self.nalozen and vrsta == self.vrsta
        self.vrsta, self.iskanje, self.stran = vrsta, iskanje, 1
        self.set_visible(bool(vrsta))
        if not vrsta:
            return
        if self._casovnik:
            GLib.source_remove(self._casovnik)
            self._casovnik = 0
        if not samo_iskanje:
            self.vnosi, self.nalozen, self.skupaj, self.skupaj_strani = [], False, None, 1
            self.narisi()
        if samo_iskanje:
            self._casovnik = GLib.timeout_add(350, lambda: (setattr(self, "_casovnik", 0), self.nalozi(), False)[2])
        else:
            self.nalozi()

    def nalozi(self) -> None:
        self.naslov.set_text(self.t("katVseVsebine") if self.vrsta == "vse" else oznaka(self.t, self.vrsta))
        self._narisi_zanre()
        self._zahteva += 1
        zahteva = self._zahteva
        if not self.vnosi:
            self.povzetek.set_text(self.t("katNalagam"))

        def gotovo(odgovor):
            if zahteva == self._zahteva:
                self._prevzemi(odgovor)

        def napaka(_e):
            if zahteva == self._zahteva:
                self.vnosi, self.nalozen = [], True
                self.narisi()
        self.okno.klic("mediaKatalog", [self.iskanje, self.vrsta, self.zanr, self.stran, self.razvrsti, [], False, [], ""],
                       gotovo, napaka)

    def _prevzemi(self, odgovor: Any) -> None:
        odgovor = odgovor if isinstance(odgovor, dict) else {}
        self.kljuc = str(odgovor.get("kljuc") or "")
        self.vnosi = list(odgovor.get("vnosi") or [])
        self.skupaj_strani = pk.strani(odgovor)
        self.skupaj = odgovor.get("skupaj") if isinstance(odgovor.get("skupaj"), int) else None
        self.nalozen = True
        self.narisi()

    def _ob_osvezenem(self, podatki) -> None:
        if isinstance(podatki, dict) and podatki.get("kljuc") and podatki.get("kljuc") == self.kljuc:
            self._prevzemi(podatki)

    def _ob_ni_na_voljo(self, podatki) -> None:
        idji = set((podatki or {}).get("idji") or []) if isinstance(podatki, dict) else set()
        prej = len(self.vnosi)
        self.vnosi = [x for x in self.vnosi if x.get("id") not in idji]
        if len(self.vnosi) != prej:
            if isinstance(self.skupaj, int):
                self.skupaj = max(len(self.vnosi), self.skupaj - (prej - len(self.vnosi)))
            self.narisi()

    def pojdi_na_stran(self, stran: int) -> None:
        if 1 <= stran <= self.skupaj_strani:
            self.stran = stran
            self.nalozi()

    def _ob_razvrsti(self, combo) -> None:
        self.razvrsti = "" if combo.get_active_id() in (None, "-") else combo.get_active_id()
        self.stran = 1
        if self.nalozen:
            self.nalozi()

    def _narisi_zanre(self) -> None:
        from core.os_player_gtk import _gumb
        skupina = skupina_zanrov(self.vrsta)
        if self._zanri_za == skupina:
            return
        self._zanri_za = skupina
        self.zanr = ""
        for o in self.zanri.get_children():
            self.zanri.remove(o)
        self.zanri.set_visible(bool(skupina))
        if not skupina:
            return

        def gumb(ident, napis):
            g = _gumb(napis, "", "kategorija", 14)
            g.ident = ident
            if ident == self.zanr:
                g.get_style_context().add_class("izbrana")
            g.connect("clicked", lambda _g: self._izberi_zanr(ident))
            self.zanri.add(g)
            g.show_all()
        vse = {"radio": "katVsePostaje", "tv-v-zivo": "katVseDrzave", "glasba": "katVsaGlasba"}.get(skupina, "katVseVsebine")
        gumb("", self.t(vse))
        if skupina == "film":
            for ident, kljuc in FILMSKI_ZANRI:
                gumb(ident, self.t(kljuc))
            return

        def zvrsti(seznam):
            if self._zanri_za != skupina:
                return
            for z in seznam if isinstance(seznam, list) else []:
                gumb(str(z.get("id") or ""), str(z.get("ime") or ""))
        self.okno.klic("mediaZvrsti", [skupina], zvrsti)

    def _izberi_zanr(self, ident: str) -> None:
        self.zanr, self.stran = ident, 1
        for o in self.zanri.get_children():
            g = o.get_child()
            ctx = g.get_style_context()
            (ctx.add_class if getattr(g, "ident", None) == ident else ctx.remove_class)("izbrana")
        self.nalozi()

    # ------------------------------------------------------------------ izris
    def narisi(self) -> None:
        t = self.t
        self.plakati.rod += 1
        for o in self.mreza.get_children():
            self.mreza.remove(o)
        for x in self.vnosi:
            self.mreza.add(self._kartica(x))
        self.mreza.show_all()
        self.prazno.set_text(t("katPrazno"))
        self.prazno.set_visible(self.nalozen and not self.vnosi)
        if self.nalozen:
            besedilo = t("katZadetkov", n=self.skupaj if self.skupaj is not None else len(self.vnosi))
            if self.skupaj_strani > 1:
                besedilo += " · " + t("katStran", a=self.stran, b=self.skupaj_strani)
            self.povzetek.set_text(besedilo)
        self.strani.set_visible(self.skupaj_strani > 1)
        self.gumb_prej.set_sensitive(self.stran > 1)
        self.gumb_nasl.set_sensitive(self.stran < self.skupaj_strani)
        self.napis_strani.set_text(t("katStran", a=self.stran, b=self.skupaj_strani))

    def _kartica(self, x: dict) -> Gtk.Widget:
        from core.os_player_gtk import BARVA_IKONA_KARTICE, _oznaka
        g = Gtk.Button()
        g.get_style_context().add_class("kartica")
        g.set_tooltip_text(str(x.get("naslov") or ""))
        telo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        art = Gtk.Overlay()
        ozadje = Gtk.Box()
        ozadje.get_style_context().add_class("kartica-art")
        ozadje.set_size_request(SIRINA_PLAKATA, VISINA_PLAKATA)
        art.add(ozadje)
        vrsta = str(x.get("vrsta") or "")
        ikona = ikone.slika("glasba" if vrsta in ("glasba", "podcast") else "radio" if vrsta == "radio" else "video",
                            40, BARVA_IKONA_KARTICE)
        if ikona is not None:
            ikona.set_halign(Gtk.Align.CENTER)
            ikona.set_valign(Gtk.Align.CENTER)
            art.add_overlay(ikona)
            art.set_overlay_pass_through(ikona, True)
        znacka = x.get("kakovost") or (self.t("katVZivo") if vrsta == "tv-v-zivo" else "")
        if znacka or float(x.get("ocena") or 0) > 0:
            napis = " · ".join(p for p in (str(znacka or ""), "★ %.1f" % float(x["ocena"]) if float(x.get("ocena") or 0) > 0 else "") if p)
            z = _oznaka(napis, "nadaljuj")
            z.set_halign(Gtk.Align.START)
            z.set_valign(Gtk.Align.START)
            z.set_margin_start(8)
            z.set_margin_top(8)
            art.add_overlay(z)
            art.set_overlay_pass_through(z, True)
        if x.get("slika"):
            self._plakat(art, str(x["slika"]), ikona)
        telo.pack_start(art, False, False, 0)
        pod = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        pod.get_style_context().add_class("kartica-pod")
        ime = _oznaka(str(x.get("naslov") or ""), "kartica-ime")
        ime.set_ellipsize(Pango.EllipsizeMode.END)
        ime.set_max_width_chars(18)
        pod.pack_start(ime, False, False, 0)
        m = _oznaka(meta(self.t, x), "drobno")
        m.set_ellipsize(Pango.EllipsizeMode.END)
        m.set_max_width_chars(22)
        pod.pack_start(m, False, False, 0)
        if int(x.get("stevilo_razlicic") or 0) > 1:
            pod.pack_start(_oznaka(self.t("katRazlicic", n=x["stevilo_razlicic"]), "drobno"), False, False, 0)
        telo.pack_start(pod, False, False, 0)
        g.add(telo)
        g.connect("clicked", lambda *_: self.izberi(x))
        return g

    def _plakat(self, art: Gtk.Overlay, url: str, ikona=None) -> None:
        def gotovo(_url, podatki, rod):
            if podatki:
                GLib.idle_add(pokazi, podatki, rod)

        def pokazi(podatki, rod):
            if rod != self.plakati.rod:
                return False
            try:
                nalagalnik = GdkPixbuf.PixbufLoader()
                nalagalnik.write(podatki)
                nalagalnik.close()
                pb = nalagalnik.get_pixbuf()
                merilo = max(SIRINA_PLAKATA / pb.get_width(), VISINA_PLAKATA / pb.get_height())
                pb = pb.scale_simple(max(1, int(pb.get_width() * merilo)), max(1, int(pb.get_height() * merilo)),
                                     GdkPixbuf.InterpType.BILINEAR)
                x0 = max(0, (pb.get_width() - SIRINA_PLAKATA) // 2)
                y0 = max(0, (pb.get_height() - VISINA_PLAKATA) // 2)
                pb = pb.new_subpixbuf(x0, y0, min(SIRINA_PLAKATA, pb.get_width()), min(VISINA_PLAKATA, pb.get_height()))
            except Exception:  # noqa: BLE001 - pokvarjen plakat: ostane ikona
                return False
            slika = Gtk.Image.new_from_pixbuf(pb)
            art.add_overlay(slika)
            art.set_overlay_pass_through(slika, True)
            # Plakat pod znacko (kakovost, ocena), ikona vrste pa izgine - kot na strani.
            art.reorder_overlay(slika, 0)
            if ikona is not None:
                ikona.hide()
            slika.show()
            return False
        self.plakati.zahtevaj(url, gotovo)

    # ------------------------------------------------------------------ dejanja
    def izberi(self, x: dict) -> None:
        if odpre_podrobnosti(x):
            self.podrobnosti(str(x.get("id") or ""))
        else:
            self.predvajaj(str(x.get("id") or ""))

    def predvajaj(self, ident: str) -> None:
        """Kot odpriKatalogVnos: mediaPredvajaj in obvestila ob napaki (ni toka, napaka vira, samo spletna stran)."""
        t = self.t
        znan = next((x for x in self.vnosi if x.get("id") == ident), None)
        if znan and znan.get("stran"):
            self.okno.odpri_splet(str(znan["stran"]))
            return
        self._zahteva_predvajanja += 1
        zahteva = self._zahteva_predvajanja

        def gotovo(item):
            if zahteva != self._zahteva_predvajanja:
                return
            if not isinstance(item, dict) or not item:
                self.okno.obvesti(t("katNapakaVira"))
                return
            if item.get("napaka_koda") == "ni_toka":
                self.okno.obvesti(t("mediaNapaka_ni_toka", ime=item.get("naslov") or ""))
                if item.get("vrsta") == "film":
                    self._ob_ni_na_voljo({"idji": [item.get("id"), ident]})
                return
            if item.get("napaka_koda"):
                self.okno.obvesti(t("mediaNapaka_" + str(item["napaka_koda"])))
                return
            if item.get("napaka") or item.get("sporocilo"):
                self.okno.obvesti(str(item.get("napaka") or item.get("sporocilo")))
                return
            if item.get("stran") and not item.get("native"):
                self.okno.odpri_splet(str(item["stran"]))
        self.okno.klic("mediaPredvajaj", [ident], gotovo,
                       lambda _e: zahteva == self._zahteva_predvajanja and self.okno.obvesti(t("katNapakaVira")))

    def podrobnosti(self, ident: str) -> None:
        """Kot odpriKatalogPodrobnosti: plakat, opis, sezone in epizode ali »Predvajaj«."""
        self.okno.klic("mediaPodrobnosti", [ident, self.t.jezik], self._pokazi_podrobnosti,
                       lambda _e: self.okno.obvesti(self.t("katNapakaVira")))

    def _pokazi_podrobnosti(self, item) -> None:
        from core.os_player_gtk import _gumb, _oznaka
        if not isinstance(item, dict) or not item:
            return
        t = self.t
        d = Gtk.Dialog(title=str(item.get("naslov") or ""), transient_for=self.okno, modal=True)
        d.get_style_context().add_class("sp-gtk")
        d.set_default_size(820, 640)
        d.add_button(t("zapri"), Gtk.ResponseType.CLOSE)
        drsnik = Gtk.ScrolledWindow()
        drsnik.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        d.get_content_area().pack_start(drsnik, True, True, 0)
        vsebina = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        vsebina.set_border_width(20)
        drsnik.add(vsebina)
        junak = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=18)
        plakat = Gtk.Overlay()
        okvir = Gtk.Box()
        okvir.get_style_context().add_class("kartica-art")
        okvir.set_size_request(SIRINA_PLAKATA, VISINA_PLAKATA)
        plakat.add(okvir)
        if item.get("slika"):
            self._plakat(plakat, str(item["slika"]))
        junak.pack_start(plakat, False, False, 0)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        info.pack_start(_oznaka(str(item.get("naslov") or ""), "h2", ovij=True), False, False, 0)
        jeserija = item.get("vrsta") == "serija"
        podatki = [str(item.get("leto") or ""), "★ %s" % item["ocena"] if item.get("ocena") else "",
                   t("katSerija" if jeserija else "katFilm")]
        info.pack_start(_oznaka(" · ".join(p for p in podatki if p), "medlo"), False, False, 0)
        if item.get("opis"):
            opis = _oznaka(str(item["opis"]), "", ovij=True)
            opis.set_max_width_chars(70)
            info.pack_start(opis, False, False, 0)
        junak.pack_start(info, True, True, 0)
        vsebina.pack_start(junak, False, False, 0)

        def predvajaj_vnos(vnos_id):
            d.response(Gtk.ResponseType.CLOSE)
            self.predvajaj(vnos_id)
        if not jeserija:
            vsebina.pack_start(_oznaka(t("katPredvajanje"), "h3"), False, False, 0)
            g = _gumb(t("katPredvajaj"), "", "glavni")
            g.set_halign(Gtk.Align.START)

            def film(*_):
                if item.get("tmdb_id"):
                    self.okno.klic("mediaFilm", [item["tmdb_id"], item.get("naslov") or ""],
                                   lambda e: predvajaj_vnos((e or {}).get("id") or item.get("id")),
                                   lambda _e: predvajaj_vnos(item.get("id")))
                else:
                    predvajaj_vnos(item.get("id"))
            g.connect("clicked", film)
            vsebina.pack_start(g, False, False, 0)
        else:
            vsebina.pack_start(_oznaka(t("katSezone"), "h3"), False, False, 0)
            sezone = Gtk.FlowBox()
            sezone.set_selection_mode(Gtk.SelectionMode.NONE)
            sezone.set_max_children_per_line(10)
            vsebina.pack_start(sezone, False, False, 0)
            naslov_epizod = _oznaka(t("katEpizode"), "h3")
            vsebina.pack_start(naslov_epizod, False, False, 0)
            epizode = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            vsebina.pack_start(epizode, False, False, 0)

            def nalozi_sezono(stevilka, napis, gumb):
                for o in sezone.get_children():
                    ctx = o.get_child().get_style_context()
                    (ctx.add_class if o.get_child() is gumb else ctx.remove_class)("izbrana")
                for o in epizode.get_children():
                    epizode.remove(o)
                epizode.pack_start(_oznaka(t("katNalagamEpizode"), "medlo"), False, False, 0)
                epizode.show_all()

                def narisi_epizode(odgovor):
                    for o in epizode.get_children():
                        epizode.remove(o)
                    naslov_epizod.set_text(t("katEpizode") + " · " + napis)
                    seznam = (odgovor or {}).get("epizode") or [] if isinstance(odgovor, dict) else []
                    for ep in seznam:
                        vrstica = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                        besedilo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                        besedilo.pack_start(_oznaka("E%02d  %s" % (int(ep.get("stevilka") or 0),
                                                                    ep.get("naslov") or t("katEpizoda")), "kartica-ime"),
                                            False, False, 0)
                        dodatno = [str(ep.get("datum") or ""), "%s min" % ep["trajanje"] if ep.get("trajanje") else "",
                                   "★ %s" % ep["ocena"] if ep.get("ocena") else ""]
                        besedilo.pack_start(_oznaka(" · ".join(p for p in dodatno if p), "drobno"), False, False, 0)
                        if ep.get("opis"):
                            o = _oznaka(str(ep["opis"]), "drobno", ovij=True)
                            o.set_max_width_chars(80)
                            besedilo.pack_start(o, False, False, 0)
                        vrstica.pack_start(besedilo, True, True, 0)
                        g = _gumb(t("katPredvajaj"), "", "glavni")
                        g.set_valign(Gtk.Align.CENTER)

                        def epizoda(_g, ep=ep):
                            self.okno.klic("mediaEpizoda", [item.get("tmdb_id"), stevilka, ep.get("stevilka"),
                                                            "%s · %s" % (item.get("naslov") or "", ep.get("naslov") or "")],
                                           lambda e: predvajaj_vnos(e["id"]) if isinstance(e, dict) and e.get("id")
                                           else self.okno.obvesti(t("mediaNapaka_ni_toka", ime=item.get("naslov") or "")),
                                           lambda _e: self.okno.obvesti(t("katNapakaVira")))
                        g.connect("clicked", epizoda)
                        vrstica.pack_end(g, False, False, 0)
                        epizode.pack_start(vrstica, False, False, 0)
                    if not seznam:
                        epizode.pack_start(_oznaka(t("katBrezEpizod"), "medlo"), False, False, 0)
                    epizode.show_all()
                self.okno.klic("mediaSezona", [item.get("tmdb_id"), stevilka], narisi_epizode,
                               lambda _e: narisi_epizode({}))
            prva = None
            for s in item.get("sezone") or []:
                napis = str(s.get("ime") or t("katSezona", n=s.get("stevilka")))
                g = _gumb(napis, "", "kategorija", 14)
                g.connect("clicked", lambda gg, st=s.get("stevilka"), n=napis: nalozi_sezono(st, n, gg))
                sezone.add(g)
                if prva is None:
                    prva = (s.get("stevilka"), napis, g)
            if prva is None:
                epizode.pack_start(_oznaka(t("katSezoneNi"), "medlo"), False, False, 0)
            d.show_all()
            if prva is not None:
                nalozi_sezono(*prva)
        d.show_all()
        d.run()
        d.destroy()
