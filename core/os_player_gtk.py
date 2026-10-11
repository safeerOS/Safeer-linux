"""Safeer Player za Linux: Medijski center v domacem GTK oknu (brez WebKita).

Vsa logika (knjiznica, mape, tokovi, predvajalnik, katalog) je v Safeer OS in se klice po istem mostu kot iz spletne
strani (core/os_most_nativni.py); besedila so iz assets/os/besedila.js, ikone iz assets/os/os.js. Ta modul je samo
izris: ista razporeditev kot spletni Medijski center (glava z dejanji, kategorije in iskanje, tvoja knjiznica,
tvoje postaje, desno »Zdaj se predvaja« in cakalna vrsta, spodaj predvajalni trak).

Privzet postane, ko ima vse, kar ima spletni (safeer_os.player_gtk_vklopljen); do takrat ga vklopi
SAFEER_PLAYER_GTK=1 ali ~/.config/safeer-os/player.json {"player_gtk": true}.
"""
from __future__ import annotations

import os
import threading
from typing import Any, Callable, Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk, Pango  # noqa: E402

from core import os_besedila, os_most_nativni  # noqa: E402
from core import os_player_gtk_ikone as ikone  # noqa: E402

WMCLASS_PREDVAJALNIKA = ("safeer-os.Player", "Safeer Player")
KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Kategorije kot na strani (MEDIA_KATEGORIJE v os.js): (filter, ikona).
KATEGORIJE = (("vse", "programi"), ("glasba", "glasba"), ("video", "video"), ("filmi", "video"),
              ("serije", "video"), ("tv", "video"), ("radio", "radio"), ("slike", "slika"))
#: Toliko vnosov vrne knjiznica naenkrat (core/os_knjiznica: meja 120) - polna stran pomeni, da jih je morda vec.
STRAN_KNJIZNICE = 120

# Barve in oblike iz assets/os/delovna.css (:root) - ista tema kot namizje Safeer OS (lastnik 11. 10. 2026: »me
# pomirja«), namesto zeleno-crne spletnega Medijskega centra. Razred »sp-gtk« (ne »safeer-player«): okno videa v
# safeer_os.py ima svoj slog za window.safeer-player.
BARVA_BESEDILO = "#eaf2ff"
BARVA_POUDAREK = "#8ac7ff"
BARVA_NA_POUDARKU = "#0b1424"
BARVA_IKONA_KARTICE = "#b9dcff"

CSS = b"""
.sp-gtk { background-color: #0b1424; color: #eaf2ff; }
.sp-gtk .vsebina { background-color: transparent; }
.sp-gtk label { color: #eaf2ff; }
.sp-gtk .kicker { color: #8ac7ff; font-size: 11px; font-weight: 800; }
.sp-gtk .h1 { font-size: 30px; font-weight: 700; }
.sp-gtk .h2 { font-size: 21px; font-weight: 700; }
.sp-gtk .h3 { font-size: 17px; font-weight: 700; }
.sp-gtk .medlo, .sp-gtk .medlo label { color: #afbed4; font-size: 13px; }
.sp-gtk .drobno { color: #93a9c4; font-size: 12px; }
.sp-gtk button { background-image: none; text-shadow: none; box-shadow: none; color: #eaf2ff;
  background-color: rgba(16,26,43,.80); border: 1px solid rgba(211,229,255,.23); border-radius: 12px; padding: 8px 13px; }
.sp-gtk button:hover { background-color: rgba(104,168,229,.20); border-color: rgba(215,234,255,.34); }
.sp-gtk button:focus { border-color: #9dceff; }
.sp-gtk button:disabled { opacity: .45; }
.sp-gtk button.glavni { background-color: #8ac7ff; color: #0b1424; border-color: #8ac7ff; font-weight: 600; }
.sp-gtk button.glavni label { color: #0b1424; }
.sp-gtk button.kategorija { background-color: transparent; border-color: transparent; border-radius: 10px; padding: 9px 12px; }
.sp-gtk button.kategorija label { color: #afbed4; }
.sp-gtk button.kategorija.izbrana { background-color: rgba(104,168,229,.28); border-color: rgba(138,199,255,.6); }
.sp-gtk button.kategorija.izbrana label { color: #eaf2ff; font-weight: 700; }
.sp-gtk .orodna { background-color: rgba(16,26,43,.80); border: 1px solid rgba(211,229,255,.23); border-radius: 14px; padding: 5px; }
.sp-gtk entry { background-image: none; background-color: rgba(234,244,255,.06); color: #eaf2ff;
  border: 1px solid rgba(211,229,255,.23); border-radius: 10px; padding: 7px 10px; box-shadow: none; }
.sp-gtk entry:focus { border-color: #9dceff; }
.sp-gtk .hero { border: 1px solid rgba(211,229,255,.23); border-radius: 22px; padding: 28px 30px;
  background-image: linear-gradient(115deg, rgba(36,62,99,.88), rgba(16,26,43,.82) 60%, rgba(22,34,58,.85)); }
.sp-gtk .hero-znak { color: rgba(138,199,255,.85); font-size: 84px; }
.sp-gtk button.kartica { padding: 0; border-radius: 17px; background-color: rgba(16,26,43,.85); }
.sp-gtk button.kartica:hover { border-color: rgba(157,206,255,.65); }
.sp-gtk .kartica-art { background-image: linear-gradient(145deg, #2a4a74, #1a2b45); border-radius: 16px 16px 0 0; }
.sp-gtk .kartica-art.glasba { background-image: linear-gradient(145deg, #2c4d72, #1b2c47); }
.sp-gtk .kartica-art.slike { background-image: linear-gradient(145deg, #3b4170, #1d2a45); }
.sp-gtk .kartica-pod { padding: 10px 12px 12px 12px; }
.sp-gtk .kartica-ime { font-weight: 700; font-size: 14px; }
.sp-gtk .nadaljuj { background-color: rgba(11,20,36,.78); border-radius: 8px; padding: 3px 8px; font-size: 12px; }
.sp-gtk progressbar trough { min-height: 4px; background-color: rgba(234,244,255,.15); border: none; }
.sp-gtk progressbar progress { min-height: 4px; background-color: #8ac7ff; border: none; }
.sp-gtk button.odstrani { padding: 3px; border-radius: 50%; background-color: rgba(11,20,36,.82); }
.sp-gtk .prazno { border: 1px dashed rgba(211,229,255,.30); border-radius: 18px; padding: 30px; background-color: rgba(16,26,43,.6); }
.sp-gtk button.vrstica { border-radius: 14px; padding: 12px 14px; }
.sp-gtk .desni { background-color: rgba(16,26,43,.80); border-left: 1px solid rgba(213,232,250,.12); padding: 24px 20px; }
.sp-gtk .sedaj { border: 1px solid rgba(211,229,255,.23); border-radius: 18px; padding: 18px;
  background-image: linear-gradient(160deg, rgba(36,62,99,.85), rgba(16,26,43,.85)); }
.sp-gtk .sedaj-art { color: #8ac7ff; font-size: 64px; background-color: rgba(11,20,36,.5); border-radius: 16px; padding: 18px; }
.sp-gtk button.vrsta-vnos { background-color: transparent; border-color: transparent; padding: 8px 10px; }
.sp-gtk button.vrsta-vnos.izbran { background-color: rgba(104,168,229,.20); border-color: rgba(138,199,255,.45); }
.sp-gtk .trak { background-color: rgba(14,23,39,.96); border-top: 1px solid rgba(211,229,255,.23); padding: 10px 18px; }
.sp-gtk .trak button { padding: 6px 12px; }
.sp-gtk scale trough { min-height: 4px; background-color: rgba(234,244,255,.18); border: none; }
.sp-gtk scale highlight { background-color: #8ac7ff; border: none; }
.sp-gtk scale slider { background-image: none; background-color: #8ac7ff; min-width: 13px; min-height: 13px; border: none; }
.sp-gtk .obvestilo { background-color: rgba(14,23,39,.98); border: 1px solid #8ac7ff; border-radius: 12px; padding: 10px 16px; }
.sp-gtk .galerija { background-color: rgba(0,0,0,.94); }
"""


def ozadje_namizja() -> str:
    """Slika ozadja namizja (Cinnamon), da je Safeer Player na istem ozadju kot namizje; prazno, ce je ni."""
    try:
        from gi.repository import Gio
        vir = Gio.SettingsSchemaSource.get_default()
        if vir is None or vir.lookup("org.cinnamon.desktop.background", True) is None:
            return ""
        uri = Gio.Settings.new("org.cinnamon.desktop.background").get_string("picture-uri")
        pot = Gio.File.new_for_uri(uri).get_path() if uri else ""
        return pot if pot and os.path.isfile(pot) else ""
    except Exception:  # noqa: BLE001
        return ""


def css_ozadja(pot: str) -> bytes:
    """Ozadje okna: slika namizja pod temno tancico (kot #ozadje na namizju Safeer OS)."""
    if not pot or '"' in pot or "\\" in pot:
        return b""
    from gi.repository import GLib as _GLib
    uri = _GLib.filename_to_uri(pot, None)
    return ('.sp-gtk { background-image: linear-gradient(rgba(11,20,36,.55), rgba(11,20,36,.55)), url("%s"); '
            'background-size: cover; background-position: center; }' % uri).encode("utf-8")


def cas_medija(sekunde) -> str:
    """Kot casMedija na strani: m:ss."""
    try:
        s = max(0, int(float(sekunde or 0)))
    except (TypeError, ValueError):
        s = 0
    return "%d:%02d" % (s // 60, s % 60)


def ujema(besedilo: str, iskanje: str) -> bool:
    """Isto ujemanje kot knjiznica in stran: brez sumnikov in velikih crk, vse besede v poljubnem vrstnem redu."""
    from core.os_knjiznica import kljuc_imena
    kljuc = kljuc_imena(str(besedilo or ""))
    return all(b in kljuc for b in kljuc_imena(str(iskanje or "")).split())


def _gumb(napis: str = "", ikona: str = "", razred: str = "", velikost: int = 17) -> Gtk.Button:
    g = Gtk.Button()
    vsebina = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=7)
    if ikona:
        barva = BARVA_NA_POUDARKU if "glavni" in razred.split() else BARVA_BESEDILO
        slika = ikone.slika(ikona, velikost, barva)
        if slika is not None:
            vsebina.pack_start(slika, False, False, 0)
    if napis:
        vsebina.pack_start(Gtk.Label(label=napis), False, False, 0)
    g.add(vsebina)
    for r in razred.split():
        g.get_style_context().add_class(r)
    g.set_can_focus(True)
    return g


def _oznaka(besedilo: str = "", razred: str = "", xalign: float = 0.0, ovij: bool = False) -> Gtk.Label:
    l = Gtk.Label(label=besedilo, xalign=xalign)
    for r in razred.split():
        l.get_style_context().add_class(r)
    if ovij:
        l.set_line_wrap(True)
        l.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    return l


class SafeerPlayerOkno(Gtk.Window):
    """Glavno okno Safeer Playerja. ``most``: NativniPogled, ki ga ustvari Safeer OS (safeer_os._ustvari_predvajalnik)."""

    def __init__(self, app: Optional[Gtk.Application] = None, iskanje: str = "",
                 most: Optional[os_most_nativni.NativniPogled] = None) -> None:
        super().__init__(title="Safeer Player")
        if app is not None:
            self.set_application(app)
        self.set_wmclass(*WMCLASS_PREDVAJALNIKA)
        self.get_style_context().add_class("sp-gtk")
        self._ikona_okna()
        zaslon = Gdk.Screen.get_default()
        sirina, visina = 1440, 900
        try:
            mon = Gdk.Display.get_default().get_primary_monitor() or Gdk.Display.get_default().get_monitor(0)
            g = mon.get_workarea()
            sirina, visina = min(1440, int(g.width * .9)), min(900, int(g.height * .9))
        except Exception:  # noqa: BLE001
            pass
        self.set_default_size(sirina, visina)
        self.set_position(Gtk.WindowPosition.CENTER)
        if zaslon is not None:
            css = Gtk.CssProvider()
            try:
                css.load_from_data(CSS + css_ozadja(ozadje_namizja()))
                Gtk.StyleContext.add_provider_for_screen(zaslon, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
            except GLib.Error as e:      # okno brez sloga je se vedno uporabno
                print("[SafeerPlayer] slog:", e)

        self.most = most or os_most_nativni.NativniPogled(lambda p, i, m, a: p.odgovor(i, False, "brez mosta"))
        self.t = os_besedila.Prevajalnik()
        # Stanje kot S.media* na strani.
        self.filter = "vse"
        self.iskanje = str(iskanje or "").strip()
        self.odmik = 0
        self.lokalno: list = []
        self.ima_vec = False
        self.tokovi: list = []
        self.mape: list = []
        self.osvezuje = False
        self.dvd_pogon = ""
        self.p: dict = {}
        self.vlecenje = False
        self._zahteva = 0
        self._podpis_vrste = None
        self._casovnik_obvestila = 0
        self._galerija: Optional[dict] = None

        self._zgradi()
        self.connect("key-press-event", self._tipka)
        for vrsta, fn in (("predvajalnik", self.osvezi_predvajalnik), ("medijskaKnjiznica", lambda _p: self.nalozi()),
                          ("medijskoOsvezevanje", self._ob_osvezevanju),
                          ("medijskaNapaka", lambda _p: self.obvesti(self.t("niUspelo")))):
            self.most.naroci(vrsta, fn)
        self.nalozi()

    # ------------------------------------------------------------------ pomocniki
    def klic(self, metoda: str, argumenti: Optional[list] = None, gotovo: Optional[Callable[[Any], None]] = None,
             napaka: Optional[Callable[[str], None]] = None) -> None:
        self.most.klic(metoda, argumenti, gotovo, napaka)

    def _ikona_okna(self) -> None:
        try:
            self.set_icon_from_file(os.path.join(KOREN, "assets", "os", "predvajalnik.svg"))
        except Exception:  # noqa: BLE001
            self.set_icon_name("safeer-browser")

    def obvesti(self, besedilo: str, sekund: int = 5) -> None:
        self.obvestilo_napis.set_text(besedilo)
        self.obvestilo.set_no_show_all(False)
        self.obvestilo.show_all()
        if self._casovnik_obvestila:
            GLib.source_remove(self._casovnik_obvestila)

        def skrij():
            self._casovnik_obvestila = 0
            self.obvestilo.hide()
            return False
        self._casovnik_obvestila = GLib.timeout_add_seconds(sekund, skrij)

    def _ni_uspelo(self, *_a) -> None:
        self.obvesti(self.t("niUspelo"))

    # ------------------------------------------------------------------ gradnja
    def _zgradi(self) -> None:
        prekrivanje = Gtk.Overlay()
        self.add(prekrivanje)
        koren = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        koren.get_style_context().add_class("vsebina")
        prekrivanje.add(koren)

        sredina = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        koren.pack_start(sredina, True, True, 0)
        drsnik = Gtk.ScrolledWindow()
        drsnik.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sredina.pack_start(drsnik, True, True, 0)
        glavni = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)
        glavni.set_border_width(30)
        drsnik.add(glavni)
        self.glavni = glavni

        glavni.pack_start(self._zgradi_glavo(), False, False, 0)
        glavni.pack_start(self._zgradi_orodno(), False, False, 0)
        glavni.pack_start(self._zgradi_hero(), False, False, 0)
        glavni.pack_start(self._zgradi_knjiznico(), False, False, 0)
        #: Prostor za katalog (filmi, serije, glasba, radio, TV) - isti katalog kot na strani.
        self.katalog_mesto = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        glavni.pack_start(self.katalog_mesto, False, False, 0)
        from core import os_player_gtk_katalog
        self.katalog = os_player_gtk_katalog.KatalogBlok(self)
        self.katalog_mesto.pack_start(self.katalog, False, False, 0)
        glavni.pack_start(self._zgradi_tokove(), False, False, 0)

        sredina.pack_start(self._zgradi_desni(), False, False, 0)
        koren.pack_start(self._zgradi_trak(), False, False, 0)

        self.obvestilo = Gtk.Box()
        self.obvestilo.get_style_context().add_class("obvestilo")
        self.obvestilo_napis = _oznaka("", "", 0.5, True)
        self.obvestilo.pack_start(self.obvestilo_napis, True, True, 0)
        self.obvestilo.set_halign(Gtk.Align.CENTER)
        self.obvestilo.set_valign(Gtk.Align.END)
        self.obvestilo.set_margin_bottom(90)
        self.obvestilo.set_no_show_all(True)
        prekrivanje.add_overlay(self.obvestilo)
        prekrivanje.set_overlay_pass_through(self.obvestilo, True)

    def _zgradi_glavo(self) -> Gtk.Widget:
        glava = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=24)
        levo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        levo.pack_start(_oznaka("SAFEER PLAYER", "kicker"), False, False, 0)
        levo.pack_start(_oznaka(self.t("mediji"), "h1"), False, False, 0)
        levo.pack_start(_oznaka(self.t("medijiOpis"), "medlo", ovij=True), False, False, 0)
        glava.pack_start(levo, False, False, 0)
        dejanja = Gtk.FlowBox()
        dejanja.set_selection_mode(Gtk.SelectionMode.NONE)
        dejanja.set_max_children_per_line(4)
        dejanja.set_column_spacing(8)
        dejanja.set_row_spacing(8)
        dejanja.set_halign(Gtk.Align.END)
        dejanja.set_valign(Gtk.Align.START)
        g = _gumb(self.t("dodajMapoMedijev"), "mapa", "glavni")
        g.connect("clicked", lambda *_: self.dodaj_mapo())
        dejanja.add(g)
        g = _gumb(self.t("dodajLokalno"), "datoteka")
        g.connect("clicked", lambda *_: self.klic("lokalniMediji", [], None, self._ni_uspelo))
        dejanja.add(g)
        g = _gumb(self.t("dodajTok"), "radio")
        g.connect("clicked", lambda *_: self.dodaj_tok())
        dejanja.add(g)
        self.gumb_disk = _gumb(self.t("predvajajDisk"), "video")
        self.gumb_disk.connect("clicked", lambda *_: self.predvajaj_disk())
        self.gumb_disk.set_no_show_all(True)
        dejanja.add(self.gumb_disk)
        glava.pack_end(dejanja, True, True, 0)
        return glava

    def _zgradi_orodno(self) -> Gtk.Widget:
        orodna = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        kat = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=2)
        kat.get_style_context().add_class("orodna")
        self.gumbi_kategorij = {}
        for ime, ikona in KATEGORIJE:
            g = _gumb(self.t("media_" + ime), ikona, "kategorija", 15)
            g.connect("clicked", lambda _g, i=ime: self.izberi_filter(i))
            kat.pack_start(g, False, False, 0)
            self.gumbi_kategorij[ime] = g
        orodna.pack_start(kat, False, False, 0)
        self.isci_entry = Gtk.SearchEntry()
        self.isci_entry.set_placeholder_text(self.t("isciMedije"))
        self.isci_entry.set_text(self.iskanje)
        self.isci_entry.set_width_chars(28)
        self.isci_entry.connect("search-changed", self._ob_iskanju)
        orodna.pack_end(self.isci_entry, False, False, 0)
        self._oznaci_filter()
        return orodna

    def _zgradi_hero(self) -> Gtk.Widget:
        hero = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
        hero.get_style_context().add_class("hero")
        besedilo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        besedilo.pack_start(_oznaka(self.t("mediaMojaZbirka"), "kicker"), False, False, 0)
        self.hero_naslov = _oznaka(self.t("mediaHeroNaslov"), "h1", ovij=True)
        besedilo.pack_start(self.hero_naslov, False, False, 0)
        self.hero_opis = _oznaka(self.t("mediaHeroOpis"), "medlo", ovij=True)
        self.hero_opis.set_max_width_chars(70)
        besedilo.pack_start(self.hero_opis, False, False, 0)
        self.hero_gumb = _gumb(self.t("dodajMapoMedijev"), "plus", "glavni")
        self.hero_gumb.set_halign(Gtk.Align.START)
        self.hero_gumb.set_margin_top(8)
        self.hero_gumb.connect("clicked", lambda *_: self.dodaj_tok() if self.filter in ("tv", "radio") else self.dodaj_mapo())
        besedilo.pack_start(self.hero_gumb, False, False, 0)
        hero.pack_start(besedilo, True, True, 0)
        hero.pack_end(_oznaka("♫", "hero-znak", 0.5), False, False, 30)
        return hero

    def _zgradi_knjiznico(self) -> Gtk.Widget:
        blok = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        self.blok_knjiznice = blok
        glava = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        levo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        levo.pack_start(_oznaka(self.t("mediaLokalno"), "kicker"), False, False, 0)
        self.naslov_zbirke = _oznaka(self.t("mediaTvojaZbirka"), "h2")
        levo.pack_start(self.naslov_zbirke, False, False, 0)
        glava.pack_start(levo, False, False, 0)
        self.gumb_osvezi = _gumb("", "ponovno")
        self.gumb_osvezi.set_tooltip_text(self.t("mediaOsvezi"))
        self.gumb_osvezi.connect("clicked", lambda *_: self.osvezi_mape())
        glava.pack_end(self.gumb_osvezi, False, False, 0)
        g = _gumb("", "mapa")
        g.set_tooltip_text(self.t("mediaMape"))
        g.connect("clicked", lambda *_: self.okno_map())
        glava.pack_end(g, False, False, 0)
        self.stevec = _oznaka("", "medlo")
        glava.pack_end(self.stevec, False, False, 6)
        blok.pack_start(glava, False, False, 0)

        self.mreza = Gtk.FlowBox()
        self.mreza.set_selection_mode(Gtk.SelectionMode.NONE)
        self.mreza.set_homogeneous(True)
        self.mreza.set_min_children_per_line(2)
        self.mreza.set_max_children_per_line(8)
        self.mreza.set_column_spacing(14)
        self.mreza.set_row_spacing(14)
        self.mreza.set_valign(Gtk.Align.START)
        blok.pack_start(self.mreza, False, False, 0)

        self.prazno = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.prazno.get_style_context().add_class("prazno")
        slika = ikone.slika("glasba", 40, BARVA_POUDAREK)
        if slika is not None:
            self.prazno.pack_start(slika, False, False, 0)
        self.prazno_naslov = _oznaka("", "h3", 0.5)
        self.prazno_opis = _oznaka("", "medlo", 0.5, True)
        self.prazno.pack_start(self.prazno_naslov, False, False, 0)
        self.prazno.pack_start(self.prazno_opis, False, False, 0)
        self.prazno_gumb = _gumb(self.t("dodajMapoMedijev"), "mapa")
        self.prazno_gumb.set_halign(Gtk.Align.CENTER)
        self.prazno_gumb.connect("clicked", lambda *_: self.dodaj_mapo())
        self.prazno.pack_start(self.prazno_gumb, False, False, 0)
        self.prazno.set_no_show_all(True)
        blok.pack_start(self.prazno, False, False, 0)

        self.gumb_vec = _gumb(self.t("mediaNaloziVec"))
        self.gumb_vec.set_halign(Gtk.Align.CENTER)
        self.gumb_vec.connect("clicked", lambda *_: self.nalozi(veckrat=True))
        self.gumb_vec.set_no_show_all(True)
        blok.pack_start(self.gumb_vec, False, False, 0)
        return blok

    def _zgradi_tokove(self) -> Gtk.Widget:
        blok = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        glava = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        glava.pack_start(_oznaka(self.t("mediaShranjeniTokovi"), "kicker"), False, False, 0)
        glava.pack_start(_oznaka(self.t("mediaTvojePostaje"), "h2"), False, False, 0)
        blok.pack_start(glava, False, False, 0)
        self.seznam_tokov = Gtk.FlowBox()
        self.seznam_tokov.set_selection_mode(Gtk.SelectionMode.NONE)
        self.seznam_tokov.set_homogeneous(True)
        self.seznam_tokov.set_max_children_per_line(4)
        self.seznam_tokov.set_column_spacing(12)
        self.seznam_tokov.set_row_spacing(12)
        blok.pack_start(self.seznam_tokov, False, False, 0)
        blok.set_no_show_all(True)
        self.blok_tokov = blok
        return blok

    def _zgradi_desni(self) -> Gtk.Widget:
        desni = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=18)
        desni.get_style_context().add_class("desni")
        desni.set_size_request(320, -1)
        sedaj = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        sedaj.get_style_context().add_class("sedaj")
        sedaj.pack_start(_oznaka(self.t("mediaSedaj"), "kicker"), False, False, 0)
        self.sedaj_art = _oznaka("♫", "sedaj-art", 0.5)
        sedaj.pack_start(self.sedaj_art, False, False, 0)
        self.sedaj_naslov = _oznaka(self.t("mediaNicesar"), "h3", ovij=True)
        sedaj.pack_start(self.sedaj_naslov, False, False, 0)
        self.sedaj_pod = _oznaka(self.t("mediaSedajNamig"), "medlo", ovij=True)
        sedaj.pack_start(self.sedaj_pod, False, False, 0)
        self.gumb_odpri_video = _gumb(self.t("mediaOdpriVideo"), "video")
        self.gumb_odpri_video.connect("clicked", lambda *_: self.ukaz("odpri"))
        self.gumb_odpri_video.set_no_show_all(True)
        sedaj.pack_start(self.gumb_odpri_video, False, False, 0)
        desni.pack_start(sedaj, False, False, 0)

        glava = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        glava.pack_start(_oznaka(self.t("mediaCakalna"), "h3"), False, False, 0)
        self.vrsta_stevec = _oznaka("", "medlo")
        glava.pack_end(self.vrsta_stevec, False, False, 0)
        desni.pack_start(glava, False, False, 0)
        drsnik = Gtk.ScrolledWindow()
        drsnik.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.vrsta = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        drsnik.add(self.vrsta)
        desni.pack_start(drsnik, True, True, 0)
        return desni

    def _zgradi_trak(self) -> Gtk.Widget:
        trak = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        trak.get_style_context().add_class("trak")
        self.trak_art = Gtk.Button(label="♫")
        self.trak_art.set_tooltip_text(self.t("mediaOdpriVideo"))
        self.trak_art.connect("clicked", lambda *_: self.ukaz("odpri"))
        trak.pack_start(self.trak_art, False, False, 0)
        meta = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        meta.set_size_request(260, -1)
        self.trak_naslov = _oznaka("", "kartica-ime")
        self.trak_naslov.set_ellipsize(Pango.EllipsizeMode.END)
        self.trak_vrsta = _oznaka("", "drobno")
        self.trak_vrsta.set_ellipsize(Pango.EllipsizeMode.END)
        meta.pack_start(self.trak_naslov, False, False, 0)
        meta.pack_start(self.trak_vrsta, False, False, 0)
        trak.pack_start(meta, False, False, 0)
        self.trak_prejsnja = Gtk.Button(label="⏮")
        self.trak_premor = Gtk.Button(label="Ⅱ")
        self.trak_naslednja = Gtk.Button(label="⏭")
        for g, u in ((self.trak_prejsnja, "prejsnja"), (self.trak_premor, "premor"), (self.trak_naslednja, "naslednja")):
            g.connect("clicked", lambda _g, x=u: self.ukaz(x))
            trak.pack_start(g, False, False, 0)
        self.trak_cas = _oznaka("0:00", "drobno")
        trak.pack_start(self.trak_cas, False, False, 0)
        self.trak_napredek = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 1000, 1)
        self.trak_napredek.set_draw_value(False)
        self.trak_napredek.connect("button-press-event", lambda *_: setattr(self, "vlecenje", True))
        self.trak_napredek.connect("button-release-event", self._ob_spustu_drsnika)
        trak.pack_start(self.trak_napredek, True, True, 0)
        self.trak_trajanje = _oznaka("0:00", "drobno")
        trak.pack_start(self.trak_trajanje, False, False, 0)
        self.trak_ustavi = Gtk.Button(label="■")
        self.trak_ustavi.connect("clicked", lambda *_: self.ukaz("ustavi"))
        trak.pack_start(self.trak_ustavi, False, False, 0)
        trak.set_no_show_all(True)
        self.trak = trak
        return trak

    # ------------------------------------------------------------------ knjiznica
    def izberi_filter(self, ime: str) -> None:
        self.filter = ime
        self._oznaci_filter()
        self.nalozi()

    def _oznaci_filter(self) -> None:
        for ime, g in self.gumbi_kategorij.items():
            ctx = g.get_style_context()
            (ctx.add_class if ime == self.filter else ctx.remove_class)("izbrana")

    def _ob_iskanju(self, entry) -> None:
        self.iskanje = entry.get_text().strip()
        self.nalozi()

    def isci(self, besedilo: str) -> None:
        """Iskanje od zunaj (safeer-os --predvajalnik z iskanim nizom)."""
        self.isci_entry.set_text(str(besedilo or ""))

    @property
    def isci_entry_text(self) -> str:
        return self.isci_entry.get_text()

    def nalozi(self, veckrat: bool = False) -> None:
        """Kot naloziMedije na strani: disk, mape, tokovi, nato knjiznica po straneh."""
        if not veckrat:
            self.klic("dvdPogoni", [], self._ob_pogonih)
            self.klic("medijskeMape", [], self._ob_mapah)
            self.klic("tokoviMedijev", [], self._ob_tokovih)
            self.klic("predvajalnikStanje", [], self.osvezi_predvajalnik)
        if self.filter in ("tv", "radio"):
            self._zahteva += 1
            self.lokalno, self.ima_vec = [], False
            self.narisi()
            return
        if not veckrat:
            self.odmik, self.lokalno, self.ima_vec = 0, [], False
        self._zahteva += 1
        zahteva = self._zahteva

        def gotovo(seznam):
            if zahteva != self._zahteva:
                return
            seznam = seznam if isinstance(seznam, list) else []
            self.lokalno = (self.lokalno + seznam) if veckrat else seznam
            self.odmik += len(seznam)
            self.ima_vec = len(seznam) == STRAN_KNJIZNICE
            self.narisi()
        self.klic("knjiznicaMedijev", [self.filter, self.iskanje, self.odmik], gotovo)

    def _ob_pogonih(self, pogoni) -> None:
        disk = next((p for p in (pogoni if isinstance(pogoni, list) else []) if p.get("vstavljen")), None)
        self.dvd_pogon = (disk or {}).get("naprava", "")
        if disk:
            ime = disk.get("ime") or ""
            napis = self.t("predvajajDisk") + (" · " + ime if ime and ime != "DVD" else "")
            for otrok in self.gumb_disk.get_child().get_children():
                if isinstance(otrok, Gtk.Label):
                    otrok.set_text(napis)
            self.gumb_disk.set_no_show_all(False)
            self.gumb_disk.show_all()
        else:
            self.gumb_disk.hide()

    def _ob_mapah(self, mape) -> None:
        self.mape = mape if isinstance(mape, list) else []
        self.gumb_osvezi.set_sensitive(bool(self.mape) and not self.osvezuje)
        if getattr(self, "_okno_map", None) is not None:
            self._napolni_mape()

    def _ob_tokovih(self, vnosi) -> None:
        self.tokovi = vnosi if isinstance(vnosi, list) else []
        self.narisi()

    def _ob_osvezevanju(self, podatki) -> None:
        self.osvezuje = bool(podatki)
        self.gumb_osvezi.set_sensitive(bool(self.mape) and not self.osvezuje)

    def narisi(self) -> None:
        """Kot narisiMedije na strani."""
        vrsta, iskano = self.filter, self.iskanje
        prikaz = [v for v in self.lokalno if (vrsta == "vse" or v.get("vrsta") == vrsta or
                  vrsta == "video" and v.get("vrsta") in ("filmi", "serije")) and ujema(v.get("ime", ""), iskano)]
        tokovi = [v for v in self.tokovi if (vrsta == "vse" or v.get("vrsta") == vrsta) and ujema(v.get("ime", ""), iskano)]
        samo_viri = vrsta in ("tv", "radio")
        self.stevec.set_text(str(len(prikaz)) if prikaz else "")
        self.naslov_zbirke.set_text(self.t("mediaTvojaZbirka") if vrsta == "vse" else self.t("media_" + vrsta))
        self.hero_naslov.set_text(self.t("mediaHeroNaslov") if vrsta == "vse" else self.t("media_" + vrsta))
        self.hero_opis.set_text(self.t("mediaHeroOpis" if vrsta == "vse" and not self.lokalno and not self.mape
                                       else "mediaHeroOpisIzbor"))
        for otrok in self.hero_gumb.get_child().get_children():
            if isinstance(otrok, Gtk.Label):
                otrok.set_text(self.t("dodajTok" if samo_viri else "dodajMapoMedijev"))
        for otrok in self.mreza.get_children():
            self.mreza.remove(otrok)
        for v in prikaz:
            self.mreza.add(self._kartica(v, prikaz))
        self.mreza.show_all()
        self.blok_knjiznice.set_visible(not samo_viri)
        prazno = not samo_viri and not prikaz
        self.prazno_naslov.set_text(self.t("niZadetkov") if iskano else self.t("mediaPraznoNaslov"))
        self.prazno_opis.set_text("" if iskano else self.t("mediaPraznoOpis"))
        self.prazno_gumb.set_visible(not iskano)
        if prazno:
            self.prazno.set_no_show_all(False)
            self.prazno.show_all()
            self.prazno_gumb.set_visible(not iskano)
        else:
            self.prazno.hide()
        self.gumb_vec.set_visible(not samo_viri and self.ima_vec)
        self.gumb_osvezi.set_sensitive(bool(self.mape) and not self.osvezuje)
        for otrok in self.seznam_tokov.get_children():
            self.seznam_tokov.remove(otrok)
        for v in tokovi:
            self.seznam_tokov.add(self._tok(v))
        if tokovi:
            self.blok_tokov.set_no_show_all(False)
            self.blok_tokov.show_all()
        else:
            self.blok_tokov.hide()
        # Brez krajevnih vsebin v izbrani kategoriji gre katalog pred prazno knjiznico (kot »brez-krajevnega« na
        # strani), sicer bi ga prazna plosca odrivala navzdol.
        mesto_knjiznice = self.glavni.child_get_property(self.blok_knjiznice, "position")
        mesto_kataloga = self.glavni.child_get_property(self.katalog_mesto, "position")
        if (samo_viri or not prikaz) != (mesto_kataloga < mesto_knjiznice):
            # reorder_child najprej odstrani: na mestu knjiznice pride katalog pred njo ali (ce je bil pred njo) za njo.
            self.glavni.reorder_child(self.katalog_mesto, mesto_knjiznice)
        # Katalog sledi isti izbiri kot knjiznica (uskladiKatalog na strani).
        if getattr(self, "katalog", None) is not None:
            self.katalog.uskladi(self.filter, self.iskanje)

    def _kartica(self, v: dict, prikaz: list) -> Gtk.Widget:
        """Kot mediaKartica na strani: slika ali ikona, »Nadaljuj« z napredkom, ime, vrsta, odstrani."""
        vrsta = str(v.get("vrsta") or "")
        na_voljo = bool(v.get("naVoljo", True))
        prekrivanje = Gtk.Overlay()
        gumb = Gtk.Button()
        gumb.get_style_context().add_class("kartica")
        gumb.set_tooltip_text(str(v.get("pot") or ""))
        gumb.set_sensitive(na_voljo)
        telo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        art = Gtk.Overlay()
        art_ozadje = Gtk.Box()
        art_ozadje.get_style_context().add_class("kartica-art")
        if vrsta in ("glasba", "slike"):
            art_ozadje.get_style_context().add_class(vrsta)
        art_ozadje.set_size_request(190, 132)
        art.add(art_ozadje)
        ikona = ikone.slika("glasba" if vrsta == "glasba" else "slika" if vrsta == "slike" else "video", 42, BARVA_IKONA_KARTICE)
        if ikona is not None:
            ikona.set_halign(Gtk.Align.CENTER)
            ikona.set_valign(Gtk.Align.CENTER)
            art.add_overlay(ikona)
            art.set_overlay_pass_through(ikona, True)
        if vrsta == "slike" and na_voljo:
            self._slicica(art, str(v.get("pot") or ""))
        pozicija, trajanje = float(v.get("pozicija") or 0), float(v.get("trajanje") or 0)
        if vrsta in ("filmi", "serije") and pozicija >= 15 and trajanje > pozicija + 20:
            spodaj = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            spodaj.set_valign(Gtk.Align.END)
            spodaj.set_margin_start(10)
            spodaj.set_margin_end(10)
            spodaj.set_margin_bottom(8)
            n = _oznaka(self.t("mediaNadaljuj") + " · " + cas_medija(pozicija), "nadaljuj")
            n.set_halign(Gtk.Align.START)
            spodaj.pack_start(n, False, False, 0)
            merilo = Gtk.ProgressBar()
            merilo.set_fraction(min(1.0, pozicija / trajanje))
            spodaj.pack_start(merilo, False, False, 0)
            art.add_overlay(spodaj)
            art.set_overlay_pass_through(spodaj, True)
        telo.pack_start(art, False, False, 0)
        pod = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        pod.get_style_context().add_class("kartica-pod")
        ime = _oznaka(str(v.get("ime") or ""), "kartica-ime")
        ime.set_ellipsize(Pango.EllipsizeMode.END)
        ime.set_max_width_chars(22)
        pod.pack_start(ime, False, False, 0)
        opis = self.t("media_" + vrsta) + ("" if na_voljo else " · " + self.t("mediaManjka"))
        pod.pack_start(_oznaka(opis, "drobno"), False, False, 0)
        telo.pack_start(pod, False, False, 0)
        gumb.add(telo)
        gumb.connect("clicked", lambda *_: self.odpri_vnos(v, prikaz))
        prekrivanje.add(gumb)
        odstrani = _gumb("", "x", "odstrani", 13)
        odstrani.set_tooltip_text(self.t("odstrani"))
        odstrani.set_halign(Gtk.Align.END)
        odstrani.set_valign(Gtk.Align.START)
        odstrani.set_margin_top(8)
        odstrani.set_margin_end(8)
        odstrani.connect("clicked", lambda *_: self.klic("odstraniLokalniMedij", [v.get("pot")],
                                                          lambda ok: ok and self.nalozi()))
        prekrivanje.add_overlay(odstrani)
        return prekrivanje

    def _slicica(self, art: Gtk.Overlay, pot: str) -> None:
        """Slika v knjiznici pokaze sebe; berem jo v ozadju, da mreza ne caka na disk."""
        def beri():
            try:
                pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(pot, 380, 264, True)
            except Exception:  # noqa: BLE001 - pokvarjena slika: ostane ikona
                return
            GLib.idle_add(pokazi, pb)

        def pokazi(pb):
            slika = Gtk.Image.new_from_pixbuf(pb.scale_simple(max(1, pb.get_width() // 2), max(1, pb.get_height() // 2),
                                                              GdkPixbuf.InterpType.BILINEAR))
            art.add_overlay(slika)
            art.set_overlay_pass_through(slika, True)
            slika.show()
            return False
        threading.Thread(target=beri, daemon=True).start()

    def odpri_vnos(self, v: dict, prikaz: list) -> None:
        if v.get("vrsta") == "slike":
            slike = [x for x in prikaz if x.get("vrsta") == "slike" and x.get("naVoljo", True)]
            i = next((k for k, x in enumerate(slike) if x.get("pot") == v.get("pot")), 0)
            self.galerija(slike, i)
            return
        self.klic("odpriLokalniMedij", [v.get("pot")], lambda ok: ok or self._ni_uspelo(), self._ni_uspelo)

    def _tok(self, v: dict) -> Gtk.Widget:
        """Kot mediaTok na strani: postaja v zivo z gumbom za odstranitev."""
        prekrivanje = Gtk.Overlay()
        g = Gtk.Button()
        g.get_style_context().add_class("vrstica")
        g.set_tooltip_text(str(v.get("url") or ""))
        vrsta = str(v.get("vrsta") or "")
        vsebina = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        ikona = ikone.slika("radio" if vrsta == "radio" else "video", 26, BARVA_POUDAREK)
        if ikona is not None:
            vsebina.pack_start(ikona, False, False, 0)
        besedilo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        ime = _oznaka(str(v.get("ime") or ""), "kartica-ime")
        ime.set_ellipsize(Pango.EllipsizeMode.END)
        besedilo.pack_start(ime, False, False, 0)
        besedilo.pack_start(_oznaka(self.t("media_" + vrsta) + " · " + self.t("mediaVZivo"), "drobno"), False, False, 0)
        vsebina.pack_start(besedilo, True, True, 0)
        g.add(vsebina)
        g.connect("clicked", lambda *_: self.klic("odpriMedijskiTok", [v.get("url")], lambda ok: ok or self._ni_uspelo(),
                                                  self._ni_uspelo))
        prekrivanje.add(g)
        odstrani = _gumb("", "x", "odstrani", 13)
        odstrani.set_tooltip_text(self.t("odstrani"))
        odstrani.set_halign(Gtk.Align.END)
        odstrani.set_valign(Gtk.Align.CENTER)
        odstrani.set_margin_end(10)
        odstrani.connect("clicked", lambda *_: self.klic("odstraniMedijskiTok", [v.get("url")],
                                                          lambda ok: ok and self.nalozi()))
        prekrivanje.add_overlay(odstrani)
        return prekrivanje

    # ------------------------------------------------------------------ dejanja
    def dodaj_mapo(self) -> None:
        self.klic("medijskaMapa", [], None, self._ni_uspelo)

    def osvezi_mape(self) -> None:
        self.osvezuje = True
        self.gumb_osvezi.set_sensitive(False)

        def gotovo(ok):
            if not ok:
                self._ob_osvezevanju(False)

        def napaka(_e):
            self._ob_osvezevanju(False)
            self._ni_uspelo()
        self.klic("osveziMedijskeMape", [], gotovo, napaka)

    def predvajaj_disk(self) -> None:
        if self.dvd_pogon:
            self.klic("dvdPredvajaj", [self.dvd_pogon], lambda ok: ok or self.obvesti(self.t("mediaNapaka_dvd")))

    def dodaj_tok(self) -> None:
        """Kot sloj »Dodaj postajo« na strani: ime, neposredni naslov toka, vrsta (TV ali radio)."""
        d = Gtk.Dialog(title=self.t("mediaDodajPostajo"), transient_for=self, modal=True)
        d.get_style_context().add_class("sp-gtk")
        d.add_button(self.t("preklici"), Gtk.ResponseType.CANCEL)
        shrani = d.add_button(self.t("mediaShraniPredvajaj"), Gtk.ResponseType.OK)
        shrani.get_style_context().add_class("glavni")
        d.set_default_response(Gtk.ResponseType.OK)
        polje = d.get_content_area()
        polje.set_spacing(10)
        polje.set_border_width(18)
        polje.pack_start(_oznaka(self.t("mediaDodajPostajo"), "h3"), False, False, 0)
        ime = Gtk.Entry(placeholder_text=self.t("mediaImePostaje"), activates_default=True)
        url = Gtk.Entry(placeholder_text=self.t("mediaNaslovToka"), activates_default=True)
        url.set_width_chars(46)
        vrsta = Gtk.ComboBoxText()
        vrsta.append("tv", self.t("media_tv"))
        vrsta.append("radio", self.t("media_radio"))
        vrsta.set_active_id("radio" if self.filter == "radio" else "tv")
        for napis, w in ((self.t("mediaImePostaje"), ime), (self.t("mediaNaslovToka"), url), (self.t("mediaVrstaPostaje"), vrsta)):
            polje.pack_start(_oznaka(napis, "drobno"), False, False, 0)
            polje.pack_start(w, False, False, 0)
        polje.pack_start(_oznaka(self.t("mediaTokNamig"), "drobno", ovij=True), False, False, 0)
        d.show_all()
        while d.run() == Gtk.ResponseType.OK:
            i, u = ime.get_text().strip(), url.get_text().strip()
            if not i or not (u.lower().startswith("http://") or u.lower().startswith("https://")) or " " in u:
                self.obvesti(self.t("mediaNapacenTok"))
                continue
            d.destroy()
            self.klic("dodajMedijskiTok", [i, u, vrsta.get_active_id() or "tv"],
                      lambda ok: self.nalozi() if ok else self.obvesti(self.t("mediaNapacenTok")),
                      lambda _e: self.obvesti(self.t("mediaNapacenTok")))
            return
        d.destroy()

    def okno_map(self) -> None:
        """Kot sloj »Medijske mape« na strani: izbrane mape, stevilo vnosov, odstrani, dodaj."""
        d = Gtk.Dialog(title=self.t("mediaMape"), transient_for=self, modal=True)
        d.get_style_context().add_class("sp-gtk")
        d.set_default_size(560, 420)
        d.add_button(self.t("zapri"), Gtk.ResponseType.CLOSE)
        polje = d.get_content_area()
        polje.set_spacing(10)
        polje.set_border_width(18)
        polje.pack_start(_oznaka(self.t("mediaMape"), "h3"), False, False, 0)
        polje.pack_start(_oznaka(self.t("mediaMapeOpis"), "medlo", ovij=True), False, False, 0)
        drsnik = Gtk.ScrolledWindow()
        drsnik.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._seznam_map = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        drsnik.add(self._seznam_map)
        polje.pack_start(drsnik, True, True, 0)
        dodaj = _gumb(self.t("dodajMapoMedijev"), "mapa", "glavni")
        dodaj.set_halign(Gtk.Align.START)
        dodaj.connect("clicked", lambda *_: (d.response(Gtk.ResponseType.CLOSE), self.dodaj_mapo()))
        polje.pack_start(dodaj, False, False, 0)
        self._okno_map = d
        self._napolni_mape()
        d.show_all()
        self.klic("medijskeMape", [], self._ob_mapah)
        d.run()
        self._okno_map = None
        d.destroy()

    def _napolni_mape(self) -> None:
        seznam = self._seznam_map
        for otrok in seznam.get_children():
            seznam.remove(otrok)
        if not self.mape:
            seznam.pack_start(_oznaka(self.t("mediaMapeNi"), "drobno"), False, False, 0)
        for m in self.mape:
            pot = str(m.get("pot") or "")
            vrstica = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            ikona = ikone.slika("mapa", 22, BARVA_POUDAREK)
            if ikona is not None:
                vrstica.pack_start(ikona, False, False, 0)
            besedilo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            besedilo.set_tooltip_text(pot)
            besedilo.pack_start(_oznaka(pot.rstrip("/").split("/")[-1] or pot, "kartica-ime"), False, False, 0)
            stanje = self.t("mediaMapaVnosov", n=m.get("stevilo", 0)) if m.get("naVoljo") else self.t("mediaMapaNedosegljiva")
            opis = _oznaka(pot + " · " + stanje, "drobno")
            opis.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            besedilo.pack_start(opis, False, False, 0)
            vrstica.pack_start(besedilo, True, True, 0)
            g = _gumb(self.t("odstrani"))

            def odstrani(gumb, p=pot):
                gumb.set_sensitive(False)

                def gotovo(ok):
                    if not ok:
                        gumb.set_sensitive(True)
                        self._ni_uspelo()
                        return
                    self.obvesti(self.t("mediaMapaOdstranjena"))
                    self.klic("medijskeMape", [], self._ob_mapah)
                    self.nalozi()
                self.klic("odstraniMedijskoMapo", [p], gotovo, lambda _e: (gumb.set_sensitive(True), self._ni_uspelo()))
            g.connect("clicked", odstrani)
            vrstica.pack_end(g, False, False, 0)
            seznam.pack_start(vrstica, False, False, 0)
        seznam.show_all()

    # ------------------------------------------------------------------ galerija
    def galerija(self, slike: list, i: int) -> None:
        """Kot galerija na strani: slika cez okno, puscici, Esc zapre, »Odpri v aplikaciji«."""
        if not slike:
            return
        d = Gtk.Window(title=self.t("media_slike"), transient_for=self, modal=True)
        d.get_style_context().add_class("sp-gtk")
        d.get_style_context().add_class("galerija")
        d.set_default_size(*self.get_size())
        okvir = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        okvir.set_border_width(16)
        d.add(okvir)
        slika = Gtk.Image()
        okvir.pack_start(slika, True, True, 0)
        vrstica = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        nazaj = _gumb("", "nazaj")
        nazaj.set_tooltip_text(self.t("mediaPrejsnjaSlika"))
        naprej = _gumb("", "desno")
        naprej.set_tooltip_text(self.t("mediaNaslednjaSlika"))
        napis = _oznaka("", "medlo", 0.5)
        odpri = _gumb(self.t("mediaOdpriVAplikaciji"))
        zapri = _gumb(self.t("zapri"), "x")
        vrstica.pack_start(nazaj, False, False, 0)
        vrstica.pack_start(naprej, False, False, 0)
        vrstica.pack_start(napis, True, True, 0)
        vrstica.pack_end(zapri, False, False, 0)
        vrstica.pack_end(odpri, False, False, 0)
        okvir.pack_start(vrstica, False, False, 0)
        g = {"seznam": slike, "i": i}
        self._galerija = g

        def pokazi():
            v = g["seznam"][g["i"]]
            napis.set_text("%s · %d / %d" % (v.get("ime", ""), g["i"] + 1, len(g["seznam"])))
            w, h = d.get_size()
            try:
                slika.set_from_pixbuf(GdkPixbuf.Pixbuf.new_from_file_at_scale(str(v.get("pot")), max(64, w - 40),
                                                                               max(64, h - 110), True))
            except Exception:  # noqa: BLE001
                slika.clear()
                napis.set_text(self.t("mediaManjka"))

        def premakni(korak):
            g["i"] = (g["i"] + korak) % len(g["seznam"])
            pokazi()

        def tipka(_w, e):
            ime = Gdk.keyval_name(e.keyval)
            if ime == "Left":
                premakni(-1)
            elif ime in ("Right", "space"):
                premakni(1)
            elif ime == "Home":
                g["i"] = 0
                pokazi()
            elif ime == "End":
                g["i"] = len(g["seznam"]) - 1
                pokazi()
            elif ime == "Escape":
                d.destroy()
            else:
                return False
            return True
        nazaj.connect("clicked", lambda *_: premakni(-1))
        naprej.connect("clicked", lambda *_: premakni(1))
        zapri.connect("clicked", lambda *_: d.destroy())
        odpri.connect("clicked", lambda *_: self.klic("odpriLokalniMedij", [g["seznam"][g["i"]].get("pot")],
                                                      lambda ok: ok or self._ni_uspelo()))
        d.connect("key-press-event", tipka)
        d.connect("destroy", lambda *_: setattr(self, "_galerija", None))
        d.show_all()
        GLib.idle_add(lambda: (pokazi(), False)[1])

    # ------------------------------------------------------------------ predvajalnik
    def odpri_splet(self, naslov: str) -> None:
        """Vsebina, ki jo ponudnik daje samo na svoji strani: odpre jo Splet v Safeer OS (kot katSplet na strani)."""
        self.klic("odpriVBrskalniku", [naslov], lambda ok: ok or self._ni_uspelo(), self._ni_uspelo)

    def ukaz(self, ukaz: str, vrednost=None) -> None:
        self.klic("predvajalnikUkaz", [ukaz] + ([vrednost] if vrednost is not None else []))

    def _ob_spustu_drsnika(self, scale, _e) -> bool:
        self.vlecenje = False
        p = self.p
        trajanje = float(p.get("trajanje") or 0)
        if trajanje > 0 and p.get("vrsta") not in ("tv", "radio"):
            self.ukaz("skok", trajanje * scale.get_value() / 1000.0)
        return False

    def osvezi_predvajalnik(self, p) -> None:
        """Kot osveziPredvajalnik na strani: trak, »Zdaj se predvaja«, cakalna vrsta."""
        if not isinstance(p, dict):
            return
        self.p = p
        t = self.t
        ima = bool(p.get("naslov"))
        stanje, vrsta = p.get("stanje"), p.get("vrsta")
        zivo = vrsta in ("tv", "radio")
        if not ima:
            opis = t("mediaSedajNamig")
        elif stanje == "napaka":
            opis = t("mediaNapaka_" + (p.get("napaka") or "splosno"))
        elif stanje == "ustavljeno":
            opis = t("mediaUstavljeno")
        elif stanje == "premor":
            opis = t("mediaPremor")
        else:
            opis = t("mediaVZivo") if zivo else (p.get("izvor") or t("mediaTaRacunalnik"))
        trak_viden = ima and stanje != "ustavljeno"
        if trak_viden:
            self.trak.set_no_show_all(False)
            self.trak.show_all()
        else:
            self.trak.hide()
        naslov = p.get("naslov") if ima else t("mediaNicesar")
        self.trak_naslov.set_text(naslov)
        self.trak_vrsta.set_text(opis)
        self.sedaj_naslov.set_text(naslov)
        self.sedaj_pod.set_text(opis)
        znak = "▶" if vrsta in ("tv", "video") else "♫"
        self.sedaj_art.set_text(znak)
        self.trak_art.set_label(znak)
        self.trak_napredek.set_visible(trak_viden and not zivo)
        self.trak_trajanje.set_visible(trak_viden and not zivo)
        self.trak_premor.set_label("Ⅱ" if stanje == "predvaja" else "▶")
        self.trak_premor.set_sensitive(ima)
        indeks, skupaj = int(p.get("indeks", -1) or 0), int(p.get("skupaj") or 0)
        self.trak_prejsnja.set_sensitive(ima and indeks > 0)
        self.trak_naslednja.set_sensitive(ima and indeks < skupaj - 1)
        self.trak_ustavi.set_sensitive(ima and stanje != "ustavljeno")
        self.trak_cas.set_text(t("mediaVZivo") if zivo else cas_medija(p.get("pozicija")))
        self.trak_trajanje.set_text("" if zivo else cas_medija(p.get("trajanje")))
        trajanje = float(p.get("trajanje") or 0)
        self.trak_napredek.set_sensitive(trajanje > 0 and not zivo)
        if not self.vlecenje:
            self.trak_napredek.set_value(round(1000 * float(p.get("pozicija") or 0) / trajanje) if trajanje else 0)
        odpri = ima and stanje != "ustavljeno" and vrsta != "radio"
        if odpri:
            self.gumb_odpri_video.set_no_show_all(False)
            self.gumb_odpri_video.show_all()
        else:
            self.gumb_odpri_video.hide()
        self._narisi_vrsto(p)

    def _narisi_vrsto(self, p: dict) -> None:
        seznam = p.get("vrstaSeznam") or []
        zacetni, indeks = int(p.get("zacetniIndeks") or 0), int(p.get("indeks", -1) if p.get("indeks") is not None else -1)
        self.vrsta_stevec.set_text(str(p.get("skupaj") or len(seznam)))
        podpis = (indeks, zacetni, tuple((v.get("naslov"), v.get("vrsta")) for v in seznam))
        if podpis == self._podpis_vrste:
            return
        self._podpis_vrste = podpis
        for otrok in self.vrsta.get_children():
            self.vrsta.remove(otrok)
        if not seznam:
            self.vrsta.pack_start(_oznaka(self.t("mediaVrstaPrazna"), "drobno", ovij=True), False, False, 0)
        for i, v in enumerate(seznam):
            stevilka = i + zacetni
            g = Gtk.Button()
            g.get_style_context().add_class("vrsta-vnos")
            if stevilka == indeks:
                g.get_style_context().add_class("izbran")
            vrstica = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            vrstica.pack_start(_oznaka("♫" if stevilka == indeks else str(stevilka + 1), "medlo"), False, False, 0)
            besedilo = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
            ime = _oznaka(str(v.get("naslov") or ""), "kartica-ime")
            ime.set_ellipsize(Pango.EllipsizeMode.END)
            besedilo.pack_start(ime, False, False, 0)
            izvor = self.t("mediaVZivo") if v.get("vrsta") in ("tv", "radio") else (v.get("izvor") or self.t("mediaTaRacunalnik"))
            besedilo.pack_start(_oznaka(izvor, "drobno"), False, False, 0)
            vrstica.pack_start(besedilo, True, True, 0)
            g.add(vrstica)
            g.connect("clicked", lambda _g, s=stevilka: self.ukaz("predvajaj", s))
            self.vrsta.pack_start(g, False, False, 0)
        self.vrsta.show_all()

    # ------------------------------------------------------------------ tipke
    def _tipka(self, _w, e) -> bool:
        ime = Gdk.keyval_name(e.keyval)
        ctrl = bool(e.state & Gdk.ModifierType.CONTROL_MASK)
        if self.isci_entry.has_focus() and ime not in ("Escape",):
            return False
        if ctrl and ime in ("f", "k"):
            self.isci_entry.grab_focus()
            return True
        if ime == "Escape" and self.isci_entry.get_text():
            self.isci_entry.set_text("")
            return True
        if ime == "space" and self.p.get("naslov"):
            self.ukaz("premor")
            return True
        return False
