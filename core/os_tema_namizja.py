"""Spletne strani v Safeer OS sledijo temi namizja (prefers-color-scheme).

WebKitGTK sporoci strani temno temo samo, ce ima GTK vklopljen gtk-application-prefer-dark-theme. Safeer Cinnamon
je temen, GTK tema pa tega ne pove - strani so bile svetle na temnem namizju (lastnik, 12. 10. 2026).

Vrstni red virov:
  1. portal (org.freedesktop.appearance color-scheme: 1 = temno, 2 = svetlo) - deluje tudi v Flatpaku;
  2. org.gnome.desktop.interface color-scheme ('prefer-dark' / 'prefer-light');
  3. ime GTK teme (vsebuje »dark« ali je Safeer-Cinnamon, ki je temna).
Spremembe (preklop teme na namizju) se uveljavijo takoj, brez ponovnega zagona.
"""
from __future__ import annotations

TEMNE_TEME = ("safeer-cinnamon",)


def _portal(Gio, GLib):
    """1 = temno, 2 = svetlo, 0/None = brez izbire ali ni portala."""
    try:
        vodilo = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        for metoda in ("ReadOne", "Read"):
            try:
                r = vodilo.call_sync("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop",
                                     "org.freedesktop.portal.Settings", metoda,
                                     GLib.Variant("(ss)", ("org.freedesktop.appearance", "color-scheme")),
                                     None, Gio.DBusCallFlags.NONE, 1000, None)
                v = r.unpack()[0]
                while isinstance(v, GLib.Variant):      # Read vrne v(v)
                    v = v.unpack()
                return int(v)
            except Exception:
                continue
    except Exception:
        pass
    return None


def _gsettings(Gio):
    try:
        vir = Gio.SettingsSchemaSource.get_default()
        shema = vir.lookup("org.gnome.desktop.interface", True) if vir else None
        if shema is None or not shema.has_key("color-scheme"):
            return None
        return Gio.Settings.new("org.gnome.desktop.interface").get_string("color-scheme")
    except Exception:
        return None


def je_temno(Gtk, Gio, GLib) -> bool:
    p = _portal(Gio, GLib)
    if p == 1:
        return True
    if p == 2:
        return False
    g = _gsettings(Gio)
    if g == "prefer-dark":
        return True
    if g == "prefer-light":
        return False
    try:
        ime = (Gtk.Settings.get_default().props.gtk_theme_name or "").lower()
    except Exception:
        ime = ""
    return "dark" in ime or ime in TEMNE_TEME


def uskladi(Gtk, Gio, GLib) -> bool:
    """Nastavi GTK (in s tem prefers-color-scheme v WebKitu) po temi namizja. Vrne, ali je temno."""
    temno = je_temno(Gtk, Gio, GLib)
    try:
        nast = Gtk.Settings.get_default()
        if nast is not None and bool(nast.props.gtk_application_prefer_dark_theme) != temno:
            nast.props.gtk_application_prefer_dark_theme = temno
    except Exception:
        pass
    return temno


def sledi(Gtk, Gio, GLib) -> list:
    """Uskladi zdaj in ob vsaki spremembi teme namizja. Vrne predmete, ki jih mora klicatelj obdrzati (Gio.Settings)."""
    uskladi(Gtk, Gio, GLib)
    obdrzi = []

    def znova(*_a):
        uskladi(Gtk, Gio, GLib)

    try:
        vodilo = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        vodilo.signal_subscribe("org.freedesktop.portal.Desktop", "org.freedesktop.portal.Settings", "SettingChanged",
                                "/org/freedesktop/portal/desktop", "org.freedesktop.appearance",
                                Gio.DBusSignalFlags.NONE, lambda *a: znova(), None)
        obdrzi.append(vodilo)
    except Exception:
        pass
    if _gsettings(Gio) is not None:
        try:
            s = Gio.Settings.new("org.gnome.desktop.interface")
            s.connect("changed::color-scheme", znova)
            s.connect("changed::gtk-theme", znova)
            obdrzi.append(s)
        except Exception:
            pass
    try:
        # Tema, ki jo mi sami nastavimo, ne sme sprozati te iste funkcije v zanki: preverjamo samo ime teme.
        Gtk.Settings.get_default().connect("notify::gtk-theme-name", znova)
    except Exception:
        pass
    return obdrzi
