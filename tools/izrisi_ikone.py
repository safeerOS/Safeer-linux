#!/usr/bin/env python3
"""PNG ikon programov iz SVG za packaging/icons (tema hicolor; AppImage in pult brez podpore za SVG jih rabita).

    python3 tools/izrisi_ikone.py assets/brskalnik.svg packaging/icons/hicolor safeer-browser
"""
import os
import sys

import gi

gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf  # noqa: E402

VELIKOSTI = (16, 24, 32, 48, 64, 128, 256, 512)


def izrisi(svg: str, mapa: str, ime: str) -> list:
    poti = []
    for v in VELIKOSTI:
        cilj = os.path.join(mapa, "%dx%d" % (v, v), "apps", ime + ".png")
        os.makedirs(os.path.dirname(cilj), exist_ok=True)
        GdkPixbuf.Pixbuf.new_from_file_at_size(svg, v, v).savev(cilj, "png", [], [])
        poti.append(cilj)
    return poti


if __name__ == "__main__":
    print("\n".join(izrisi(*sys.argv[1:4])))
