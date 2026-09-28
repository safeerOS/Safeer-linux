#!/usr/bin/env python3
"""Zgradi samostojno temo Safeer-OS iz izvorne kode Linux Mint (mint-themes, Mint-Y-Dark).

Tema je izpeljanka Mint-Y (GPL-3+): uporabimo Mintove SASS vire in orodje generate-themes.py,
dodamo barvno razlicico »Safeer« (poudarek #54d6a5, temno modre podlage) in rezultat
shranimo kot popolno temo za GTK2/3/4, libadwaita in Cinnamon - brez @import tujih tem in
brez odvisnosti od paketa mint-themes.

Uporaba:
    python3 packaging/tema/zgradi_temo.py POT/DO/mint-themes [IZHOD]

IZHOD je privzeto packaging/tema/Safeer-OS. Potrebno: python3 z numpy in Pillow, pysassc (libsass).
Inkscape NI potreben: slike (PNG) izpeljemo iz Mintove razlicice Teal s prebarvanjem.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

MINT_COMMIT = "a022d8d99c3c33d9f1b0c823eeb3a89530f20ab7"

POUDAREK = "#54d6a5"          # Safeer zelena
NA_POUDARKU = "#06231a"        # besedilo na zeleni podlagi (kontrast 9:1; bela bi imela le 1,9:1)
IZVOR_PNG = "#199ca8"          # Mintov Teal, iz katerega prebarvamo slike
IME = "Safeer-OS"

# Temna paleta Safeer OS (enaka kot v vmesniku Safeer OS)
GTK_TEMNO = {
    "base_color": "#111a26",
    "text_color": "#e6ecea",
    "header_bg": "#090d15",
    "header_highlight": "#1a2533",
    "osd_bg_color": "#0f1823",
    "wm_title_unfocused": "#7f8c89",
    "wm_button_hover_bg": "#1c2a38",
    "wm_button_active_bg": "#2a3a4a",
    "wm_icon_bg": "#a8b5b1",
    "wm_icon_unfocused_bg": "#3c4a57",
    "wm_icon_hover_bg": "#d6e2de",
}
GTK_SPLOSNO = {
    "selected_fg_color": NA_POUDARKU,
    "suggested_color": POUDAREK,
    "xfce_panel_bg": "#0f1823",
    "panel_bg": "#090d15",
    "terminal_bg": "#090d15",
    "link_color": "#7fb8ff",
    "link_visited_color": "#a89bff",
}
CINNAMON_TEMNO = {
    "bg_color": "#0c121c",
    "text_color": "#dfe7e4",
    "panel_fg": "#e6ecea",
    "fg_color": "#e6ecea",
}
CINNAMON_SPLOSNO = {"selected_fg_color": NA_POUDARKU}
OBVEZNE = {"base_color", "header_bg", "bg_color", "selected_fg_color"}

# Svetla zelena potrebuje temno besedilo (Mint na gumbu »predlagano dejanje« vedno pise belo).
GTK_DODATKI = """
/* Safeer OS: videz kot v vmesniku Safeer OS (zaobljeno, zeleni poudarki, mehka izbira) */
button.suggested-action, button.suggested-action:hover, button.suggested-action:active,
button.suggested-action:checked, button.suggested-action label { color: %(na)s; }
button, entry, spinbutton, combobox button { border-radius: 10px; }
notebook > header > tabs > tab { border-radius: 10px 10px 0 0; }
menu, .menu, .context-menu, popover.background { border-radius: 12px; }
menu menuitem { border-radius: 8px; }
tooltip.background, tooltip { border-radius: 10px; }
placessidebar row, stacksidebar row, .sidebar row, .navigation-sidebar row { border-radius: 10px; }
placessidebar row:selected, stacksidebar row:selected, .sidebar row:selected, .navigation-sidebar row:selected,
placessidebar row:selected label, stacksidebar row:selected label, .sidebar row:selected label {
  background-color: rgba(84, 214, 165, 0.16); color: %(p)s; }
scale trough, scale highlight, progressbar trough, progressbar progress, levelbar block { border-radius: 99px; }
frame > border, .frame, list, .view.frame { border-radius: 12px; }
switch { border-radius: 99px; }
switch slider { border-radius: 99px; }
""" % {"na": NA_POUDARKU, "p": POUDAREK}

# Dodatki Safeer, ki jih Mint-Y nima (zaobljen meni, tanka zelena crta plosce).
CINNAMON_DODATKI = """
/* Safeer OS */
#panel { background-color: rgba(9, 13, 21, 0.94); border-top: 1px solid rgba(84, 214, 165, 0.22); }
.menu, .popup-menu, .popup-menu-boxpointer { border-radius: 16px; }
.popup-menu, .menu { border: 1px solid rgba(84, 214, 165, 0.22); }
.popup-menu-item, .menu-application-button, .menu-category-button { border-radius: 10px; }
.popup-menu-item:active, .menu-application-button-selected, .menu-category-button-selected {
  background-color: rgba(84, 214, 165, 0.16); color: #54d6a5; }
.applet-box, .window-list-item-box, .grouped-window-list-item-box { border-radius: 8px; }
.tooltip, .notification, .osd-window, .info-osd { border-radius: 14px; }
.modal-dialog, .cinnamon-dialog { border-radius: 16px; }
"""


def _zamenjaj_blok(besedilo: str, vrednosti: dict, samo_temni: bool) -> str:
    """Zamenja `$ime: vrednost;` - v temnem bloku (@else) ali v celotni datoteki."""
    if samo_temni:
        i = besedilo.index("} @else {")
        glava, telo = besedilo[:i], besedilo[i:]
    else:
        glava, telo = "", besedilo
    for ime, vrednost in vrednosti.items():
        telo, n = re.subn(r"(\$%s:\s*)[^;]+;" % re.escape(ime), r"\g<1>%s;" % vrednost, telo, count=1)
        if n != 1:
            if ime in OBVEZNE:
                raise SystemExit("V SASS ni spremenljivke $%s" % ime)
            print("  (ni v tej datoteki: $%s)" % ime)
    return glava + telo


def _hsv(rgb: np.ndarray) -> np.ndarray:
    r, g, b = (rgb[..., i] / 255.0 for i in range(3))
    mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-6
    rc = np.where(m, (mx - r) / np.where(m, d, 1), 0)
    gc = np.where(m, (mx - g) / np.where(m, d, 1), 0)
    bc = np.where(m, (mx - b) / np.where(m, d, 1), 0)
    h = np.where(r == mx, bc - gc, np.where(g == mx, 2.0 + rc - bc, 4.0 + gc - rc))
    h = np.where(m, (h / 6.0) % 1.0, 0)
    s = np.where(mx > 0, d / np.where(mx > 0, mx, 1), 0)
    return np.stack([h, s, mx], axis=-1)


def _rgb(hsv: np.ndarray) -> np.ndarray:
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    i = np.floor(h * 6.0).astype(int) % 6
    f = h * 6.0 - np.floor(h * 6.0)
    p, q, t = v * (1 - s), v * (1 - s * f), v * (1 - s * (1 - f))
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.clip(np.stack([r, g, b], axis=-1) * 255.0 + 0.5, 0, 255).astype(np.uint8)


def _hex_hsv(barva: str) -> np.ndarray:
    return _hsv(np.array([[[int(barva[i:i + 2], 16) for i in (1, 3, 5)]]], dtype=float))[0, 0]


def prebarvaj_png(pot: Path, izvor: str = IZVOR_PNG, cilj: str = POUDAREK) -> bool:
    """Piksle v odtenku izvorne barve preslika v ciljno (odtenek, nasicenost, svetlost sorazmerno)."""
    slika = Image.open(pot)
    nacin = slika.mode
    rgba = np.array(slika.convert("RGBA")).astype(float)
    hsv = _hsv(rgba[..., :3])
    hi, si, vi = _hex_hsv(izvor)
    hc, sc, vc = _hex_hsv(cilj)
    razlika = np.abs(((hsv[..., 0] - hi) + 0.5) % 1.0 - 0.5)
    maska = (razlika < 25 / 360) & (hsv[..., 1] > 0.18) & (rgba[..., 3] > 0)
    if not maska.any():
        return False
    novo = hsv.copy()
    novo[..., 0] = np.where(maska, hc, hsv[..., 0])
    novo[..., 1] = np.where(maska, np.clip(hsv[..., 1] * sc / si, 0, 1), hsv[..., 1])
    novo[..., 2] = np.where(maska, np.clip(hsv[..., 2] * vc / vi, 0, 1), hsv[..., 2])
    rgba[..., :3] = np.where(maska[..., None], _rgb(novo), rgba[..., :3])
    izhod = Image.fromarray(rgba.astype(np.uint8), "RGBA")
    if nacin not in ("RGBA", "LA"):
        izhod = izhod.convert(nacin) if nacin != "P" else izhod
    izhod.save(pot, optimize=True)
    return True


def zgradi(mint: Path, izhod: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        delo = Path(tmp) / "mint-themes"
        shutil.copytree(mint, delo, ignore=lambda d, imena: [i for i in imena if i == ".git" or (Path(d) == mint and i == "usr")])

        # 1) Nova barvna razlicica »Safeer« (ime brez presledkov, ker ga Mint uporablja v poteh)
        with open(delo / "constants.py", "a", encoding="utf-8") as f:
            f.write('\ny_hex_colors1["Safeer"] = "%s"\ny_hex_colors2["Safeer"] = "%s"\n' % (POUDAREK, POUDAREK))
        teal = delo / "src/Mint-Y/variations/Teal"
        safeer = delo / "src/Mint-Y/variations/Safeer"
        shutil.copytree(teal, safeer)
        for svg in safeer.rglob("*.svg"):
            besedilo = svg.read_text(encoding="utf-8")
            svg.write_text(re.sub(re.escape(IZVOR_PNG), POUDAREK, besedilo, flags=re.I), encoding="utf-8")
        prebarvanih = sum(prebarvaj_png(p) for p in safeer.rglob("*.png"))
        print("Prebarvanih slik:", prebarvanih)

        # 2) Temna paleta Safeer v SASS virih (GTK3, GTK4, Cinnamon)
        for pot in ("src/Mint-Y/gtk-3.0/sass/_colors.scss", "src/Mint-Y/gtk-4.0/sass/_colors.scss"):
            p = delo / pot
            besedilo = _zamenjaj_blok(p.read_text(encoding="utf-8"), GTK_TEMNO, True)
            p.write_text(_zamenjaj_blok(besedilo, GTK_SPLOSNO, False), encoding="utf-8")
        p = delo / "src/Mint-Y/cinnamon/sass/_colors.scss"
        besedilo = _zamenjaj_blok(p.read_text(encoding="utf-8"), CINNAMON_TEMNO, True)
        p.write_text(_zamenjaj_blok(besedilo, CINNAMON_SPLOSNO, False), encoding="utf-8")

        # 3) Mintovo orodje zgradi vse razlicice; vzamemo Mint-Y-Dark-Safeer
        okolje = dict(os.environ, PATH=os.path.expanduser("~/.local/bin") + os.pathsep + os.environ.get("PATH", ""))
        subprocess.run([sys.executable, "generate-themes.py"], cwd=delo, env=okolje, check=True,
                       stdout=subprocess.DEVNULL)
        vir = delo / "usr/share/themes/Mint-Y-Dark-Safeer"
        if not (vir / "gtk-3.0/gtk.css").is_file():
            raise SystemExit("Mint ni zgradil Mint-Y-Dark-Safeer")

        # 4) Izhod: popolna tema Safeer-OS (lastni okvirji oken metacity-1 ostanejo nasi)
        metacity = izhod / "metacity-1"
        ohrani = Path(tempfile.mkdtemp()) / "metacity-1"
        if metacity.is_dir():
            shutil.copytree(metacity, ohrani)
        if izhod.exists():
            shutil.rmtree(izhod)
        shutil.copytree(vir, izhod)
        if ohrani.is_dir():
            shutil.copytree(ohrani, izhod / "metacity-1")
            shutil.rmtree(ohrani.parent)
        for css in ("gtk-3.0/gtk.css", "gtk-3.0/gtk-dark.css", "gtk-4.0/gtk.css", "gtk-4.0/gtk-dark.css"):
            with open(izhod / css, "a", encoding="utf-8") as f:
                f.write(GTK_DODATKI)
        with open(izhod / "cinnamon/cinnamon.css", "a", encoding="utf-8") as f:
            f.write(CINNAMON_DODATKI)
        (izhod / "index.theme").write_text(
            "[Desktop Entry]\nType=X-GNOME-Metatheme\nName=%s\nComment=Safeer OS tema za Linux Mint (izpeljana iz Mint-Y)\n"
            "Encoding=UTF-8\n\n[X-GNOME-Metatheme]\nGtkTheme=%s\nMetacityTheme=%s\nIconTheme=Papirus-Dark\n"
            "CursorTheme=DMZ-Black\nButtonLayout=:minimize,maximize,close\n" % (IME, IME, IME), encoding="utf-8")
        shutil.copy(delo / "debian/copyright", izhod / "COPYRIGHT.mint-themes")
        (izhod / "README").write_text(
            "Safeer-OS je izpeljanka teme Mint-Y iz projekta Linux Mint mint-themes\n"
            "(https://github.com/linuxmint/mint-themes, commit %s), licenca GPL-3+.\n"
            "Spremembe: barvna razlicica Safeer (poudarek %s, besedilo na poudarku %s), temno modre podlage,\n"
            "okvirji oken metacity-1 in manjsi dodatki za Cinnamon. Ustvari: packaging/tema/zgradi_temo.py\n"
            % (MINT_COMMIT, POUDAREK, NA_POUDARKU), encoding="utf-8")
        print("Tema:", izhod)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    koren = Path(__file__).resolve().parent
    zgradi(Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve() if len(sys.argv) > 2 else koren / IME)
