"""Domači Safeer Player v GTK 3 (brez WebKit).

Ponuja popolnoma enak Medijski center kot spletni Safeer OS (knjižnica kartic,
iskanje, filtriranje po kategorijah, predvajanje videa z GStreamer gtksink/gtkglsink,
upravljanje zvoka, podnapisi in celozaslonski način).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GLib", "2.0")

try:
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
    Gst.init(None)
except Exception:
    Gst = None

from gi.repository import Gtk, Gdk, GLib, Pango

from core import os_knjiznica, os_predvajalnik

WMCLASS_PREDVAJALNIKA = ("safeer-os.Player", "Safeer Player")

CSS_PREDVAJALNIKA = b"""
window.safeer-player {
    background-color: #0c1821;
    color: #f0f4f3;
}
.safeer-player label {
    color: #f0f4f3;
}
.safeer-player label.kicker {
    color: #54d6a5;
    font-size: 11px;
    font-weight: 800;
}
.safeer-player label.naslov-glava {
    font-size: 22px;
    font-weight: 700;
    color: #f0f4f3;
}
.safeer-player label.medlo {
    color: #b0bdc4;
    font-size: 12px;
}
.safeer-player label.art-ikona {
    font-size: 48px;
    color: #54d6a5;
}
.safeer-player label.art-ikona-velika {
    font-size: 96px;
    color: #54d6a5;
}
/* Teme (Mint-Y, Adwaita) risejo gumbe z background-image: brez tega ostanejo gumbi svetli in napisi nevidni. */
.safeer-player button, .safeer-player combobox button, .safeer-player entry {
    background-image: none;
    text-shadow: none;
    box-shadow: none;
}
.safeer-player button label, .safeer-player combobox button label {
    color: inherit;
}
.safeer-player combobox button, .safeer-player menu, .safeer-player .menu {
    background-color: #1a3339;
    color: #edfff7;
}
.safeer-player button {
    background-color: #1a3339;
    color: #edfff7;
    border: 1px solid #3a6f65;
    border-radius: 10px;
    padding: 6px 12px;
}
.safeer-player button:hover {
    background-color: #275248;
    border-color: #54d6a5;
}
.safeer-player button.glavni {
    background-color: #54d6a5;
    color: #071e18;
    font-weight: 700;
    border-color: #54d6a5;
}
.safeer-player button.kategorija-izbrana {
    background-color: #54d6a5;
    color: #071e18;
    font-weight: 700;
}
.safeer-player button.media-kartica {
    background-color: rgba(24, 37, 47, 0.85);
    border: 1px solid rgba(95, 194, 164, 0.33);
    border-radius: 14px;
    padding: 10px;
    min-width: 170px;
    min-height: 150px;
}
.safeer-player button.media-kartica:hover {
    border-color: #54d6a5;
    background-color: rgba(28, 48, 58, 0.95);
}
.safeer-player entry {
    background-color: rgba(12, 24, 33, 0.85);
    color: #f0f4f3;
    border: 1px solid rgba(95, 194, 164, 0.33);
    border-radius: 8px;
    padding: 6px 10px;
}
.safeer-player entry:focus {
    border-color: #54d6a5;
}
.safeer-player scale highlight {
    background-color: #54d6a5;
}
.safeer-player scale slider {
    background-color: #54d6a5;
    min-width: 14px;
    min-height: 14px;
}
.safeer-player box.vrstica-orodna {
    background-color: rgba(8, 15, 23, 0.6);
    border: 1px solid rgba(95, 194, 164, 0.25);
    border-radius: 12px;
    padding: 4px;
}
.safeer-player box.predvajalnik-bar {
    background-color: rgba(12, 24, 33, 0.95);
    border-top: 1px solid rgba(95, 194, 164, 0.33);
    padding: 8px 16px;
}
"""


def _gumb_z_ikono(ikona: str, napis: str = "") -> Gtk.Button:
    """Gumb s simbolno ikono teme (emoji v napisih se brez pisave z emoji izrisejo kot kvadratki)."""
    gumb = Gtk.Button(label=napis) if napis else Gtk.Button()
    gumb.set_image(Gtk.Image.new_from_icon_name(ikona, Gtk.IconSize.BUTTON))
    gumb.set_always_show_image(True)
    return gumb


def _format_cas(sekunde: float | int) -> str:
    s = max(0, int(sekunde or 0))
    m, sec = divmod(s, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m}:{sec:02d}"


class SafeerPlayerOkno(Gtk.Window):
    """Glavno okno domačega GTK Medijskega centra."""

    def __init__(self, app: Optional[Gtk.Application] = None, iskanje: str = ""):
        if app is not None:
            super().__init__(application=app, title="Safeer Player")
        else:
            super().__init__(title="Safeer Player")

        self.set_wmclass(*WMCLASS_PREDVAJALNIKA)
        self.get_style_context().add_class("safeer-player")
        self.set_default_size(1152, 720)
        self.set_position(Gtk.WindowPosition.CENTER)

        self._uveljavi_css()
        self._ikona()

        # Zaledna knjižnica in predvajalnik
        self.knjiznica = os_knjiznica.Knjiznica()
        self.predvajalnik: Optional[os_predvajalnik.Predvajalnik] = None
        self._video_ponor = None
        self._video_widget = None

        if Gst is not None:
            try:
                self.predvajalnik = os_predvajalnik.Predvajalnik(
                    gst=Gst,
                    sprememba=self._ob_spremembi_predvajalnika,
                    konec=self._ob_koncu_predvajanja
                )
                self._iniciiraj_video_ponor()
            except Exception as e:
                print("[SafeerPlayerGTK] Napaka pri inicializaciji predvajalnika:", e)

        self.izbrana_kategorija = ""
        #: "zbirka" (krajevne datoteke) ali "katalog" (spletni katalog - isti kot Medijski center na strani).
        self.nacin = "zbirka"
        self.katalog_pogled = None
        self._casovnik_obvestila = 0
        self.trenutno_iskanje = str(iskanje or "").strip()
        self._v_premikanju_drsnika = False

        self._zgradi_vmesnik()

        self.connect("key-press-event", self._ob_tipki)
        self.connect("delete-event", self._ob_zapiranju)

        # Periodični časovnik za osvežitev napredka (1x na sekundo)
        GLib.timeout_add(500, self._osvezi_napredek)

        self.osvezi_zbirko()

    def _uveljavi_css(self):
        try:
            ponudnik = Gtk.CssProvider()
            ponudnik.load_from_data(CSS_PREDVAJALNIKA)
            Gtk.StyleContext.add_provider_for_screen(
                Gdk.Screen.get_default(),
                ponudnik,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        except Exception as e:
            print("[SafeerPlayerGTK] CSS napaka:", e)

    def _ikona(self):
        try:
            pot = Path(__file__).resolve().parent.parent / "assets" / "os" / "predvajalnik.svg"
            if pot.is_file():
                self.set_icon_from_file(str(pot))
            else:
                self.set_icon_name("safeer-player")
        except Exception:
            self.set_icon_name("safeer-player")

    def _iniciiraj_video_ponor(self):
        if self.predvajalnik is None or Gst is None:
            return
        for opis, sink_ime in [
            ("glupload ! gtkglsink name=safeersink", "safeersink"),
            ("videoconvert ! gtksink name=safeersink", "safeersink"),
        ]:
            try:
                bin_elem = Gst.parse_bin_from_description(opis, True)
                if bin_elem is not None:
                    sink = bin_elem.get_by_name(sink_ime)
                    if sink is not None:
                        widget = sink.get_property("widget")
                        if widget is not None:
                            self._video_ponor = bin_elem
                            self._video_widget = widget
                            self.predvajalnik.element.set_property("video-sink", bin_elem)
                            break
            except Exception:
                continue

    def _zgradi_vmesnik(self):
        glavni_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(glavni_box)

        # 1. Zgornja glava in orodna vrstica
        glava_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        glava_box.set_border_width(12)

        kicker_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        kicker_lbl = Gtk.Label(label="SAFEER PLAYER", xalign=0)
        kicker_lbl.get_style_context().add_class("kicker")
        naslov_lbl = Gtk.Label(label="Medijski center", xalign=0)
        naslov_lbl.get_style_context().add_class("naslov-glava")
        kicker_box.pack_start(kicker_lbl, False, False, 0)
        kicker_box.pack_start(naslov_lbl, False, False, 0)
        glava_box.pack_start(kicker_box, False, False, 0)

        # Moja zbirka | Katalog
        nacin_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        nacin_box.get_style_context().add_class("vrstica-orodna")
        self.btn_zbirka = Gtk.Button(label="Moja zbirka")
        self.btn_zbirka.connect("clicked", lambda *_: self.preklopi_nacin("zbirka"))
        self.btn_katalog = Gtk.Button(label="Katalog")
        self.btn_katalog.connect("clicked", lambda *_: self.preklopi_nacin("katalog"))
        self.btn_zbirka.get_style_context().add_class("kategorija-izbrana")
        nacin_box.pack_start(self.btn_zbirka, False, False, 0)
        nacin_box.pack_start(self.btn_katalog, False, False, 0)
        glava_box.pack_start(nacin_box, False, False, 8)

        # Kategorije
        kat_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        kat_box.get_style_context().add_class("vrstica-orodna")
        self.kat_gumbi = {}
        kategorije = [("", "Vse"), ("filmi", "Filmi"), ("serije", "Serije"),
                      ("glasba", "Glasba"), ("tokovi", "Tokovi")]
        for k_id, k_naziv in kategorije:
            btn = Gtk.Button(label=k_naziv)
            btn.connect("clicked", self._ob_izbiri_kategorije, k_id)
            if k_id == self.izbrana_kategorija:
                btn.get_style_context().add_class("kategorija-izbrana")
            kat_box.pack_start(btn, False, False, 0)
            self.kat_gumbi[k_id] = btn
        glava_box.pack_start(kat_box, False, False, 8)
        self.kat_box = kat_box

        # Iskalnik
        self.isci_entry = Gtk.SearchEntry()
        self.isci_entry.set_placeholder_text("Išči medije...")
        self.isci_entry.set_width_chars(20)
        if self.trenutno_iskanje:
            self.isci_entry.set_text(self.trenutno_iskanje)
        self.isci_entry.connect("search-changed", self._ob_spremembi_iskanja)
        glava_box.pack_start(self.isci_entry, False, False, 4)

        # Gumbi za dejanja
        dodaj_mapo_btn = _gumb_z_ikono("folder-new-symbolic", "Mapa")
        dodaj_mapo_btn.connect("clicked", self._dialog_dodaj_mapo)
        glava_box.pack_end(dodaj_mapo_btn, False, False, 0)

        odpri_dat_btn = _gumb_z_ikono("document-open-symbolic", "Datoteka")
        odpri_dat_btn.connect("clicked", self._dialog_odpri_datoteko)
        glava_box.pack_end(odpri_dat_btn, False, False, 0)

        glavni_box.pack_start(glava_box, False, False, 0)

        # Kratko obvestilo (odpiranje, vsebina ni na voljo ...) - izgine samo.
        self.obvestilo = Gtk.Label(label="", xalign=0)
        self.obvestilo.get_style_context().add_class("medlo")
        self.obvestilo.set_margin_start(16)
        self.obvestilo.set_no_show_all(True)
        glavni_box.pack_start(self.obvestilo, False, False, 0)

        # 2. Glavno območje (Stack: knjižnica / predvajanje)
        self.sklad = Gtk.Stack()
        self.sklad.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        glavni_box.pack_start(self.sklad, True, True, 0)

        # Pogled A: Knjižnica kartic
        knjiznica_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        knjiznica_box.set_border_width(12)

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_valign(Gtk.Align.START)
        self.flowbox.set_max_children_per_line(30)
        self.flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_column_spacing(12)
        self.flowbox.set_row_spacing(12)
        scroll.add(self.flowbox)

        # Prazno stanje
        self.prazno_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.CENTER)
        prazno_ikona = Gtk.Label(label="♫")
        prazno_ikona.get_style_context().add_class("art-ikona-velika")
        prazno_naslov = Gtk.Label(label="Tvoja zbirka je prazna")
        prazno_naslov.get_style_context().add_class("naslov-glava")
        prazno_namig = Gtk.Label(label="Dodaj mapo z mediji ali odpri datoteko za začetek predvajanja.")
        prazno_namig.get_style_context().add_class("medlo")
        prazno_gumb = Gtk.Button(label="＋ Dodaj mapo medijev")
        prazno_gumb.get_style_context().add_class("glavni")
        prazno_gumb.set_halign(Gtk.Align.CENTER)
        prazno_gumb.connect("clicked", self._dialog_dodaj_mapo)

        self.prazno_box.pack_start(prazno_ikona, False, False, 0)
        self.prazno_box.pack_start(prazno_naslov, False, False, 0)
        self.prazno_box.pack_start(prazno_namig, False, False, 0)
        self.prazno_box.pack_start(prazno_gumb, False, False, 8)

        knjiznica_box.pack_start(scroll, True, True, 0)
        knjiznica_box.pack_start(self.prazno_box, True, True, 0)
        self.sklad.add_named(knjiznica_box, "knjiznica")

        # Pogled B: Predvajalnik (video / zvok)
        predvajanje_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        self.video_sklad = Gtk.Stack()
        self.video_sklad.set_transition_type(Gtk.StackTransitionType.CROSSFADE)

        # Zvočni prikaz (ko ni videa)
        zvok_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, valign=Gtk.Align.CENTER)
        self.zvok_ikona = Gtk.Label(label="♫")
        self.zvok_ikona.get_style_context().add_class("art-ikona-velika")
        self.zvok_naslov = Gtk.Label()
        self.zvok_naslov.get_style_context().add_class("naslov-glava")
        self.zvok_podnaslov = Gtk.Label()
        self.zvok_podnaslov.get_style_context().add_class("medlo")
        zvok_box.pack_start(self.zvok_ikona, False, False, 0)
        zvok_box.pack_start(self.zvok_naslov, False, False, 0)
        zvok_box.pack_start(self.zvok_podnaslov, False, False, 0)
        self.video_sklad.add_named(zvok_box, "zvok")

        # Video prikaz
        if self._video_widget is not None:
            video_evbox = Gtk.EventBox()
            video_evbox.add(self._video_widget)
            video_evbox.connect("button-press-event", self._ob_kliku_videa)
            self.video_sklad.add_named(video_evbox, "video")
        else:
            nadomestek = Gtk.Label(label="Video ponor (gtksink) ni na voljo.")
            self.video_sklad.add_named(nadomestek, "video")

        predvajanje_box.pack_start(self.video_sklad, True, True, 0)
        self.sklad.add_named(predvajanje_box, "predvajanje")

        self.sklad.show_all()
        self.sklad.set_visible_child_name("knjiznica")
        self.video_sklad.set_visible_child_name("zvok")

        # 3. Spodnja nadzorna vrstica predvajalnika
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        bar.get_style_context().add_class("predvajalnik-bar")

        # Levo: Trenutni naslov in metapodatki
        meta_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        meta_box.set_size_request(240, -1)
        self.bar_naslov = Gtk.Label(label="Nič se ne predvaja", xalign=0)
        self.bar_naslov.set_ellipsize(Pango.EllipsizeMode.END)
        self.bar_podnaslov = Gtk.Label(label="", xalign=0)
        self.bar_podnaslov.get_style_context().add_class("medlo")
        self.bar_podnaslov.set_ellipsize(Pango.EllipsizeMode.END)
        meta_box.pack_start(self.bar_naslov, False, False, 0)
        meta_box.pack_start(self.bar_podnaslov, False, False, 0)
        bar.pack_start(meta_box, False, False, 0)

        # Sredina: Kontrolni gumbi in časovni drsnik
        sredina_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        gumbi_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.CENTER)

        self.btn_prejsnja = _gumb_z_ikono("media-skip-backward-symbolic")
        self.btn_prejsnja.connect("clicked", lambda *_: self._ukaz("prejsnja"))
        gumbi_box.pack_start(self.btn_prejsnja, False, False, 0)

        self.btn_premor = Gtk.Button(label="▶")
        self.btn_premor.get_style_context().add_class("glavni")
        self.btn_premor.connect("clicked", lambda *_: self._ukaz("premor"))
        gumbi_box.pack_start(self.btn_premor, False, False, 0)

        self.btn_naslednja = _gumb_z_ikono("media-skip-forward-symbolic")
        self.btn_naslednja.connect("clicked", lambda *_: self._ukaz("naslednja"))
        gumbi_box.pack_start(self.btn_naslednja, False, False, 0)

        self.btn_ustavi = _gumb_z_ikono("media-playback-stop-symbolic")
        self.btn_ustavi.connect("clicked", lambda *_: self._ukaz("ustavi"))
        gumbi_box.pack_start(self.btn_ustavi, False, False, 0)

        sredina_box.pack_start(gumbi_box, False, False, 0)

        # Časovni drsnik
        cas_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.lbl_trenutni_cas = Gtk.Label(label="0:00")
        self.lbl_trenutni_cas.get_style_context().add_class("medlo")
        cas_box.pack_start(self.lbl_trenutni_cas, False, False, 0)

        self.drsnik = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1000, 1)
        self.drsnik.set_draw_value(False)
        self.drsnik.set_hexpand(True)
        self.drsnik.connect("change-value", self._ob_spremembi_drsnika)
        self.drsnik.connect("button-press-event", lambda *_: setattr(self, "_v_premikanju_drsnika", True))
        self.drsnik.connect_after("button-release-event", self._ob_spustu_drsnika)
        cas_box.pack_start(self.drsnik, True, True, 0)

        self.lbl_skupni_cas = Gtk.Label(label="0:00")
        self.lbl_skupni_cas.get_style_context().add_class("medlo")
        cas_box.pack_start(self.lbl_skupni_cas, False, False, 0)

        sredina_box.pack_start(cas_box, False, False, 0)
        bar.pack_start(sredina_box, True, True, 12)

        # Desno: Dodatne kontrole (podnapisi, celozaslonski način, preklop pogledov)
        desno_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6, halign=Gtk.Align.END)
        self.btn_podnapisi = _gumb_z_ikono("media-view-subtitles-symbolic")
        self.btn_podnapisi.set_tooltip_text("Podnapisi [V]")
        self.btn_podnapisi.connect("clicked", lambda *_: self._cikel_podnapisov())
        desno_box.pack_start(self.btn_podnapisi, False, False, 0)

        self.btn_fullscreen = _gumb_z_ikono("view-fullscreen-symbolic")
        self.btn_fullscreen.set_tooltip_text("Celoten zaslon [F11 / F]")
        self.btn_fullscreen.connect("clicked", lambda *_: self._preklopi_fullscreen())
        desno_box.pack_start(self.btn_fullscreen, False, False, 0)

        self.btn_pogled = Gtk.Button(label="Nazaj na izbiro")
        self.btn_pogled.connect("clicked", lambda *_: self._preklopi_pogled())
        desno_box.pack_start(self.btn_pogled, False, False, 0)

        bar.pack_end(desno_box, False, False, 0)
        glavni_box.pack_end(bar, False, False, 0)

    # ------------------------------------------------------------------ Knjižnica in kartice

    def osvezi_zbirko(self):
        # Počisti obstoječe kartice
        for otrok in self.flowbox.get_children():
            self.flowbox.remove(otrok)

        vnosi = []
        if self.izbrana_kategorija == "tokovi":
            for t in self.knjiznica.tokovi():
                vnosi.append({"pot": t["url"], "naslov": t["ime"], "vrsta": t["vrsta"], "is_stream": True})
        else:
            vnosi = self.knjiznica.seznam(vrsta=self.izbrana_kategorija, iskanje=self.trenutno_iskanje)

        if not vnosi:
            self.flowbox.set_visible(False)
            self.prazno_box.set_visible(True)
            return

        self.prazno_box.set_visible(False)
        self.flowbox.set_visible(True)

        for item in vnosi:
            self._dodaj_kartico(item)

        self.flowbox.show_all()

    def _dodaj_kartico(self, item: dict):
        pot = item.get("pot", "")
        naslov = item.get("naslov", "Neznano")
        vrsta = item.get("vrsta", "medij")

        btn = Gtk.Button()
        btn.get_style_context().add_class("media-kartica")
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        ikona_tekst = "♫" if vrsta == "glasba" else ("📻" if vrsta == "radio" else ("📺" if vrsta == "tv" else "🎬"))
        ikona = Gtk.Label(label=ikona_tekst)
        ikona.get_style_context().add_class("art-ikona")
        box.pack_start(ikona, True, True, 4)

        lbl_naslov = Gtk.Label(label=naslov)
        lbl_naslov.set_ellipsize(Pango.EllipsizeMode.END)
        lbl_naslov.set_max_width_chars(18)
        lbl_naslov.set_line_wrap(False)
        box.pack_start(lbl_naslov, False, False, 0)

        vrsta_tekst = vrsta.capitalize()
        pozicija = item.get("pozicija", 0)
        if pozicija > 0:
            vrsta_tekst += f" · {_format_cas(pozicija)}"
        lbl_pod = Gtk.Label(label=vrsta_tekst)
        lbl_pod.get_style_context().add_class("medlo")
        box.pack_start(lbl_pod, False, False, 0)

        btn.add(box)
        btn.connect("clicked", lambda *_: self.predvajaj_pot(pot, naslov=naslov, vrsta=vrsta))
        self.flowbox.add(btn)

    def _ob_izbiri_kategorije(self, btn, kat_id: str):
        self.izbrana_kategorija = kat_id
        for kid, gumb in self.kat_gumbi.items():
            if kid == kat_id:
                gumb.get_style_context().add_class("kategorija-izbrana")
            else:
                gumb.get_style_context().remove_class("kategorija-izbrana")
        self.osvezi_zbirko()

    def _ob_spremembi_iskanja(self, entry):
        self.trenutno_iskanje = entry.get_text().strip()
        if self.nacin == "katalog" and self.katalog_pogled is not None:
            self.katalog_pogled.isci(self.trenutno_iskanje)
            return
        self.osvezi_zbirko()

    def _dialog_dodaj_mapo(self, *_):
        dialog = Gtk.FileChooserDialog(
            title="Izberi mapo z mediji",
            parent=self,
            action=Gtk.FileChooserAction.SELECT_FOLDER
        )
        dialog.add_button("Prekliči", Gtk.ResponseType.CANCEL)
        dialog.add_button("Izberi", Gtk.ResponseType.OK)
        if dialog.run() == Gtk.ResponseType.OK:
            mapa = dialog.get_filename()
            if mapa:
                self.knjiznica.dodaj_mapo(Path(mapa))
                self.osvezi_zbirko()
        dialog.destroy()

    def _dialog_odpri_datoteko(self, *_):
        dialog = Gtk.FileChooserDialog(
            title="Odpri medijsko datoteko",
            parent=self,
            action=Gtk.FileChooserAction.OPEN
        )
        dialog.add_button("Prekliči", Gtk.ResponseType.CANCEL)
        dialog.add_button("Odpri", Gtk.ResponseType.OK)
        if dialog.run() == Gtk.ResponseType.OK:
            dat = dialog.get_filename()
            if dat:
                self.predvajaj_pot(dat)
        dialog.destroy()

    # ------------------------------------------------------------------ Predvajanje

    def predvajaj_pot(self, pot: str, naslov: str = "", vrsta: str = "medij", zacetek: int = 0,
                      podnapisi: tuple = ()) -> bool:
        if self.predvajalnik is None:
            return False
        if not pot:
            return False

        if pot.startswith(("http://", "https://", "dvd://", "file:")):
            uri = pot
        else:
            uri = Path(pot).resolve().as_uri()

        if not naslov:
            naslov = Path(pot).stem if not pot.startswith("http") else pot

        if vrsta == "medij" and not pot.startswith(("http", "file:")):
            vrsta = os_knjiznica.vrsta_datoteke(Path(pot))

        self.sklad.set_visible_child_name("predvajanje")
        self.btn_pogled.set_label("Nazaj na izbiro")

        skladba = os_predvajalnik.medij(uri, vrsta=vrsta if vrsta in ("video", "tv", "radio") else "medij")
        skladba = os_predvajalnik.replace(skladba, naslov=naslov, zacetek=max(0, int(zacetek or 0)),
                                          podnapisi=tuple(podnapisi or ()))
        self.predvajalnik.zamenjaj_vrsto([skladba], zacni=0)

        # Preklop video/zvok sklada
        if vrsta in ("filmi", "serije", "video", "tv") and self._video_widget is not None:
            self.video_sklad.set_visible_child_name("video")
        else:
            self.zvok_naslov.set_text(naslov)
            self.zvok_podnaslov.set_text(vrsta.capitalize())
            self.video_sklad.set_visible_child_name("zvok")

        self.bar_naslov.set_text(naslov)
        self.bar_podnaslov.set_text(vrsta.capitalize())
        self.btn_premor.set_label("⏸")
        return True

    def _ukaz(self, ukaz: str, vrednost=None):
        if self.predvajalnik is None:
            return
        if ukaz == "premor":
            if self.predvajalnik.stanje == "predvaja":
                self.predvajalnik.element.set_state(Gst.State.PAUSED)
                self.predvajalnik.stanje = "pavza"
                self.btn_premor.set_label("▶")
            elif self.predvajalnik.stanje == "pavza":
                self.predvajalnik.element.set_state(Gst.State.PLAYING)
                self.predvajalnik.stanje = "predvaja"
                self.btn_premor.set_label("⏸")
            elif self.predvajalnik.vrsta:
                self.predvajalnik.predvajaj(max(0, self.predvajalnik.indeks))
        elif ukaz == "ustavi":
            self.predvajalnik.element.set_state(Gst.State.NULL)
            self.predvajalnik.stanje = "ustavljeno"
            self.btn_premor.set_label("▶")
            self.lbl_trenutni_cas.set_text("0:00")
            self.drsnik.set_value(0)
        elif ukaz == "skok":
            try:
                cilj_ns = int(float(vrednost) * Gst.SECOND)
                self.predvajalnik.element.seek_simple(
                    Gst.Format.TIME,
                    Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
                    cilj_ns
                )
            except Exception:
                pass
        elif ukaz == "naslednja":
            if self.predvajalnik.vrsta and self.predvajalnik.indeks + 1 < len(self.predvajalnik.vrsta):
                self.predvajalnik.predvajaj(self.predvajalnik.indeks + 1)
        elif ukaz == "prejsnja":
            if self.predvajalnik.vrsta and self.predvajalnik.indeks > 0:
                self.predvajalnik.predvajaj(self.predvajalnik.indeks - 1)

    def _osvezi_napredek(self) -> bool:
        if self.predvajalnik is None or self.predvajalnik.stanje not in ("predvaja", "pavza"):
            return True
        try:
            ok_pos, pos_ns = self.predvajalnik.element.query_position(Gst.Format.TIME)
            ok_dur, dur_ns = self.predvajalnik.element.query_duration(Gst.Format.TIME)
            if ok_pos and ok_dur and dur_ns > 0:
                pos_s = pos_ns / Gst.SECOND
                dur_s = dur_ns / Gst.SECOND
                self.lbl_trenutni_cas.set_text(_format_cas(pos_s))
                self.lbl_skupni_cas.set_text(_format_cas(dur_s))
                if not self._v_premikanju_drsnika:
                    delez = min(1000, max(0, int((pos_s / dur_s) * 1000)))
                    self.drsnik.set_value(delez)
        except Exception:
            pass
        return True

    def _ob_spremembi_drsnika(self, scale, scroll, value):
        return False

    def _ob_spustu_drsnika(self, scale, event):
        self._v_premikanju_drsnika = False
        if self.predvajalnik is None:
            return
        try:
            ok_dur, dur_ns = self.predvajalnik.element.query_duration(Gst.Format.TIME)
            if ok_dur and dur_ns > 0:
                dur_s = dur_ns / Gst.SECOND
                cilj_s = dur_s * (scale.get_value() / 1000.0)
                self._ukaz("skok", cilj_s)
        except Exception:
            pass

    def _cikel_podnapisov(self):
        if self.predvajalnik is None:
            return
        try:
            p = self.predvajalnik.podnapisi()
            moznosti = p.get("moznosti", [])
            trenutni = p.get("izbran", "izklop")
            if not moznosti:
                return
            indeksi = [m.get("oznaka", "") for m in moznosti]
            if trenutni in indeksi:
                idx = (indeksi.index(trenutni) + 1) % len(indeksi)
            else:
                idx = 0
            naslednji = indeksi[idx]
            self.predvajalnik.izberi_podnapise(naslednji)
            ime = next((m.get("ime", "") for m in moznosti if m.get("oznaka") == naslednji), naslednji)
            self.btn_podnapisi.set_tooltip_text(f"Podnapisi: {ime}")
        except Exception:
            pass

    def _preklopi_fullscreen(self):
        okno = self.get_window()
        if okno and okno.get_state() & Gdk.WindowState.FULLSCREEN:
            self.unfullscreen()
        else:
            self.fullscreen()

    def _pogled_brskanja(self) -> str:
        return "katalog" if self.nacin == "katalog" and self.katalog_pogled is not None else "knjiznica"

    def _preklopi_pogled(self):
        if self.sklad.get_visible_child_name() != "predvajanje":
            self.sklad.set_visible_child_name("predvajanje")
            self.btn_pogled.set_label("Nazaj na izbiro")
        else:
            self.sklad.set_visible_child_name(self._pogled_brskanja())
            self.btn_pogled.set_label("Predvajalnik")

    # ------------------------------------------------------------------ Spletni katalog

    def preklopi_nacin(self, nacin: str) -> None:
        """Moja zbirka (datoteke na disku) ali Katalog (spletni viri - isti kot Medijski center v Safeer OS).
        Katalog se ustvari ob prvem odprtju: zagon predvajalnika ga ne caka."""
        self.nacin = "katalog" if nacin == "katalog" else "zbirka"
        for gumb, izbran in ((self.btn_zbirka, self.nacin == "zbirka"), (self.btn_katalog, self.nacin == "katalog")):
            ctx = gumb.get_style_context()
            (ctx.add_class if izbran else ctx.remove_class)("kategorija-izbrana")
        self.kat_box.set_visible(self.nacin == "zbirka")
        if self.nacin == "katalog" and self.katalog_pogled is None:
            from core import os_player_gtk_katalog
            self.katalog_pogled = os_player_gtk_katalog.KatalogPogled(
                predvajaj=self._predvajaj_iz_kataloga, sporocilo=self.obvesti)
            self.sklad.add_named(self.katalog_pogled, "katalog")
            self.katalog_pogled.show_all()
            self.katalog_pogled.iskanje = self.trenutno_iskanje
            self.katalog_pogled.nalozi()
        self.sklad.set_visible_child_name(self._pogled_brskanja())
        self.btn_pogled.set_label("Predvajalnik")

    def _predvajaj_iz_kataloga(self, uri: str, vrsta: str, ime: str, zacetek: int = 0, podnapisi: tuple = ()) -> bool:
        # Katalog: "video"/"tv" se kaze v oknu, "medij"/"radio" je zvok.
        return self.predvajaj_pot(uri, naslov=ime, vrsta=vrsta or "medij", zacetek=zacetek, podnapisi=podnapisi)

    def obvesti(self, besedilo: str, sekund: int = 6) -> None:
        self.obvestilo.set_text(str(besedilo or ""))
        self.obvestilo.set_visible(bool(besedilo))
        if self._casovnik_obvestila:
            GLib.source_remove(self._casovnik_obvestila)

        def skrij():
            self._casovnik_obvestila = 0
            self.obvestilo.set_visible(False)
            return False
        self._casovnik_obvestila = GLib.timeout_add_seconds(sekund, skrij)

    def _ob_kliku_videa(self, widget, event):
        if event.type == Gdk.EventType._2BUTTON_PRESS:
            self._preklopi_fullscreen()
            return True
        return False

    def _ob_spremembi_predvajalnika(self):
        if self.predvajalnik and self.predvajalnik.trenutna:
            self.bar_naslov.set_text(self.predvajalnik.trenutna.naslov)
            stanje = self.predvajalnik.stanje
            self.btn_premor.set_label("⏸" if stanje == "predvaja" else "▶")

    def _ob_koncu_predvajanja(self, uri: str):
        self.btn_premor.set_label("▶")
        self.lbl_trenutni_cas.set_text("0:00")
        self.drsnik.set_value(0)

    # ------------------------------------------------------------------ Tipkovnica in bližnjice

    def _ob_tipki(self, widget, event) -> bool:
        tipka = Gdk.keyval_name(event.keyval)

        # Če ima fokus iskalnik, pusti običajen vnos besedila
        fokus = self.get_focus()
        if fokus is self.isci_entry and tipka not in ("Escape", "Return"):
            return False

        if tipka == "space":
            self._ukaz("premor")
            return True
        elif tipka == "Left":
            if self.predvajalnik:
                try:
                    ok, pos = self.predvajalnik.element.query_position(Gst.Format.TIME)
                    if ok:
                        self._ukaz("skok", max(0, (pos / Gst.SECOND) - 10))
                except Exception:
                    pass
            return True
        elif tipka == "Right":
            if self.predvajalnik:
                try:
                    ok, pos = self.predvajalnik.element.query_position(Gst.Format.TIME)
                    if ok:
                        self._ukaz("skok", (pos / Gst.SECOND) + 10)
                except Exception:
                    pass
            return True
        elif tipka in ("f", "F", "F11"):
            self._preklopi_fullscreen()
            return True
        elif tipka in ("v", "V") and not event.state & Gdk.ModifierType.CONTROL_MASK:
            self._cikel_podnapisov()
            return True
        elif tipka in ("n", "N"):
            self._ukaz("naslednja")
            return True
        elif tipka in ("p", "P"):
            self._ukaz("prejsnja")
            return True
        elif tipka == "Escape":
            okno = self.get_window()
            if okno and okno.get_state() & Gdk.WindowState.FULLSCREEN:
                self.unfullscreen()
                return True
            if self.sklad.get_visible_child_name() == "predvajanje":
                self._preklopi_pogled()
                return True
        return False

    def ustavi(self) -> None:
        """Popolnoma ustavi predvajanje in vrne predvajalnik v mirovanje."""
        if self.predvajalnik is not None:
            try:
                self.predvajalnik.ustavi()
            except Exception as e:
                print("[SafeerPlayerGTK] Napaka ob ustavitvi:", e)
        if hasattr(self, "btn_premor"):
            self.btn_premor.set_label("▶")
        if hasattr(self, "sklad"):
            self.sklad.set_visible_child_name(self._pogled_brskanja())
        if self.katalog_pogled is not None:
            self.katalog_pogled.ustavi()

    def _ob_zapiranju(self, widget, event) -> bool:
        self.ustavi()
        return False


def zazeni(pot_za_predvajanje: str = "", iskanje: str = ""):
    okno = SafeerPlayerOkno(iskanje=iskanje)
    if pot_za_predvajanje and os.path.exists(pot_za_predvajanje):
        okno.predvajaj_pot(pot_za_predvajanje)
    okno.show_all()
    Gtk.main()


if __name__ == "__main__":
    pot = sys.argv[1] if len(sys.argv) > 1 else ""
    zazeni(pot_za_predvajanje=pot)
