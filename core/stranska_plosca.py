"""Stranska plosca Safeer Browserja (GTK4): spletni klepeti in posta ob strani, kot jih je imel Safeer Browser na GTK3
(safeer_mint.py, nastavitev »integrations«) - z istim katalogom kot Sporocila v Safeer OS (core/spletni_klepeti.py) in
z istim vgrajenim pogledom (core/os_splet.SpletnaAplikacija: ista seja, zascita, dovoljenja, pojavna okna za prijavo).
AGENTS.md: »vsaka izboljsava spletne izkusnje gre v vse brskalnike«.

Ozek pas ikon na desni (vklopljene storitve, »+« za izbiro iz kataloga); klik odpre storitev v plosci ob strani, drugi
klik jo skrije (stran tece naprej - obvestila in stevilo neprebranih ostanejo). Pogled storitve nastane ob prvem klicu.
"""
from __future__ import annotations

from core import spletni_klepeti

BESEDILA = {
    "sl": {"dodaj": "Storitve v stranski plošči", "zapri": "Skrij ploščo", "neprebranih": "{n} neprebranih"},
    "en": {"dodaj": "Services in the side panel", "zapri": "Hide panel", "neprebranih": "{n} unread"},
    "de": {"dodaj": "Dienste in der Seitenleiste", "zapri": "Leiste ausblenden", "neprebranih": "{n} ungelesen"},
    "es": {"dodaj": "Servicios del panel lateral", "zapri": "Ocultar panel", "neprebranih": "{n} sin leer"},
    "fr": {"dodaj": "Services du panneau latéral", "zapri": "Masquer le panneau", "neprebranih": "{n} non lus"},
    "it": {"dodaj": "Servizi nel pannello laterale", "zapri": "Nascondi pannello", "neprebranih": "{n} non letti"},
}
SIRINA = 420


class StranskaPlosca:
    def __init__(self, Gtk, Gio, splet, jezik) -> None:
        self.Gtk, self.Gio, self.splet, self.jezik = Gtk, Gio, splet, jezik
        self.config = splet.config
        self.aplikacije: dict = {}
        self.gumbi: dict = {}
        self.odprta = ""
        self.gradnik = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        self.gradnik.set_name("safeer-stranska")
        self.razkrij = Gtk.Revealer()
        self.razkrij.set_transition_type(Gtk.RevealerTransitionType.SLIDE_LEFT)
        self.sklad = Gtk.Stack()
        self.sklad.set_size_request(SIRINA, -1)
        self.sklad.set_vexpand(True)
        self.razkrij.set_child(self.sklad)
        self.pas = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.pas.set_name("safeer-stranska-pas")
        for stran in ("set_margin_bottom", "set_margin_start", "set_margin_end"):
            getattr(self.pas, stran)(6)
        # Zavihki so v glavi okna (safeer_brskalnik), pas je pod njimi; gumb ima ikono klepeta, ne »+« (lastnik,
        # 17. 10. 2026: dva enaka gumba »+« ob zavihkih).
        self.pas.set_margin_top(6)
        self.gradnik.append(self.razkrij)
        self.gradnik.append(self.pas)
        self.narisi()

    def _t(self, kljuc: str, **v) -> str:
        j = str(self.jezik() if callable(self.jezik) else self.jezik or "en")[:2]
        niz = BESEDILA.get(j, BESEDILA["en"]).get(kljuc, kljuc)
        return niz.format(**v) if v else niz

    def integracije(self) -> dict:
        """Storitve plosce iz nastavitev (katalog je dodan ob branju nastavitev, core/config.py); brez »remote_control«
        (to je stran na tem racunalniku, ne spletna storitev)."""
        izid = {}
        for kid, v in (self.config.get("integrations", {}) or {}).items():
            if not isinstance(v, dict):
                continue
            try:
                # Ista preverba kot lasten klepet v Sporocilih: samo https, brez imena/gesla v naslovu, gostitelj IDN
                # kot punycode (spletni_klepeti.preveri_naslov) - tudi za rocno vpisane naslove v nastavitvah.
                url = spletni_klepeti.preveri_naslov(spletni_klepeti.preseli_naslov(str(v.get("url") or "")))
            except spletni_klepeti.NeveljavenNaslov:
                continue
            if not str(v.get("url") or "").lower().startswith("https://"):
                continue
            izid[kid] = dict(v, url=url)
        return izid

    def narisi(self) -> None:
        Gtk = self.Gtk
        otrok = self.pas.get_first_child()
        while otrok is not None:
            naslednji = otrok.get_next_sibling()
            self.pas.remove(otrok)
            otrok = naslednji
        self.gumbi = {}
        for kid, v in self.integracije().items():
            if not v.get("enabled", False):
                continue
            g = Gtk.Button(label=(v.get("name") or "?")[:1].upper())
            g.add_css_class("nav")          # isti videz kot gumbi orodne vrstice Spleta (brez novih barv)
            g.set_tooltip_text(v.get("name") or v.get("url"))
            g.connect("clicked", lambda _g, kid=kid: self.preklopi(kid))
            self.pas.append(g)
            self.gumbi[kid] = g
        izbira = Gtk.MenuButton()
        izbira.set_icon_name("chat-message-new-symbolic")   # klepeti ob strani, ne nov zavihek
        izbira.set_tooltip_text(self._t("dodaj"))
        izbira.set_create_popup_func(lambda g, *_: g.set_popover(self._izbira()))
        self.pas.append(izbira)

    def _izbira(self):
        """Seznam storitev s stikali (vklopi ali izklopi storitev v plosci)."""
        Gtk = self.Gtk
        pop = Gtk.Popover()
        skatla = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        skatla.append(Gtk.Label(label=self._t("dodaj"), xalign=0))
        drsnik = Gtk.ScrolledWindow()
        drsnik.set_min_content_height(320)
        drsnik.set_propagate_natural_height(True)
        seznam = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        for kid, v in self.integracije().items():
            c = Gtk.CheckButton(label=v.get("name") or v.get("url"))
            c.set_active(bool(v.get("enabled", False)))
            c.connect("toggled", lambda c, kid=kid: self.vklopi(kid, c.get_active()))
            seznam.append(c)
        drsnik.set_child(seznam)
        skatla.append(drsnik)
        pop.set_child(skatla)
        return pop

    def vklopi(self, kid: str, vklop: bool) -> None:
        integracije = self.config.settings.setdefault("integrations", {})
        if kid not in integracije:
            return
        integracije[kid]["enabled"] = bool(vklop)
        self.config.save_settings()
        if not vklop:
            self.zapri_storitev(kid)
        self.narisi()

    def zapri_storitev(self, kid: str) -> None:
        a = self.aplikacije.pop(kid, None)
        if a is not None:
            if self.odprta == kid:
                self.razkrij.set_reveal_child(False)
                self.odprta = ""
            a.unici()

    def preklopi(self, kid: str) -> None:
        if self.odprta == kid and self.razkrij.get_reveal_child():
            self.razkrij.set_reveal_child(False)
            self.odprta = ""
            return
        v = self.integracije().get(kid)
        if v is None:
            return
        a = self.aplikacije.get(kid)
        if a is None:
            a = self.aplikacije[kid] = self.splet.aplikacija(v["url"], ob_naslovu=lambda n, kid=kid: self._znacka(kid, n))
            self.sklad.add_named(a.gradnik, kid)
        self.sklad.set_visible_child(a.gradnik)
        self.razkrij.set_reveal_child(True)
        self.odprta = kid
        a.pogled.grab_focus()

    def _znacka(self, kid: str, naslov: str) -> None:
        g = self.gumbi.get(kid)
        v = self.integracije().get(kid) or {}
        if g is None:
            return
        n = spletni_klepeti.neprebrano(naslov)
        ime = v.get("name") or ""
        g.set_label("%s %s" % (ime[:1].upper(), n if n < 100 else "99+") if n else ime[:1].upper())
        g.set_tooltip_text(ime + (" · " + self._t("neprebranih", n=n) if n else ""))
