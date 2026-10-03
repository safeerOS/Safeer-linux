#!/usr/bin/env python3
"""Slike zagonskega zaslona Safeer za Plymouth (ponovljivo): python3 tools/plymouth_safeer.py [mapa]

Narise vse, kar potrebuje modul two-step: watermark.png (znak Safeer z napisom), throbber-00NN.png (vrteci lok),
animation-00NN.png (lok se sklene v krog), bullet.png, entry.png, lock.png, capslock.png in keyboard.png.
Brez zunanjih slik; znak je iz assets/safeer-mark.svg. Licenca: kot tema (GPL-3.0-or-later), lastno delo Safeer.
"""
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
POUDAREK = (138, 199, 255)       # #8ac7ff, poudarek Safeer Cinnamon
BESEDILO = (234, 242, 255)       # #eaf2ff
SLIK = 30
PISAVE = ("/usr/share/fonts/truetype/ubuntu/Ubuntu-L.ttf", "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
          "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def znak(velikost):
    """Znak Safeer iz SVG (GdkPixbuf + librsvg), kot RGBA slika."""
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    p = GdkPixbuf.Pixbuf.new_from_file_at_size(os.path.join(KOREN, "assets", "safeer-mark.svg"), velikost, velikost)
    return Image.frombytes("RGBA" if p.get_has_alpha() else "RGB", (p.get_width(), p.get_height()), p.get_pixels(),
                           "raw", "RGBA" if p.get_has_alpha() else "RGB", p.get_rowstride()).convert("RGBA")


def pisava(velikost):
    for pot in PISAVE:
        if os.path.exists(pot):
            return ImageFont.truetype(pot, velikost)
    return ImageFont.load_default()


def vodni_znak():
    z = znak(132)
    f = pisava(40)
    napis = "Safeer OS"
    sirina = int(ImageDraw.Draw(z).textlength(napis, font=f)) + 8
    s = Image.new("RGBA", (max(z.width, sirina), z.height + 70), (0, 0, 0, 0))
    s.alpha_composite(z, ((s.width - z.width) // 2, 0))
    ImageDraw.Draw(s).text((s.width / 2, z.height + 40), napis, font=f, fill=BESEDILO + (255,), anchor="mm")
    return s


def lok(zacetek, dolzina, velikost=64, debelina=5):
    """Krog z rahlo sledjo in poudarjenim lokom (koti v stopinjah, 0 = zgoraj, v smeri urinega kazalca)."""
    m = 4                                             # nadvzorcenje za gladke robove
    s = Image.new("RGBA", (velikost * m, velikost * m), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    rob = debelina * m
    okvir = (rob, rob, velikost * m - rob, velikost * m - rob)
    d.arc(okvir, 0, 360, fill=POUDAREK + (46,), width=debelina * m)
    if dolzina > 0:
        d.arc(okvir, zacetek - 90, zacetek - 90 + dolzina, fill=POUDAREK + (255,), width=debelina * m)
        if dolzina < 360:                             # zaobljena konca loka
            r = (velikost * m - 2 * rob) / 2 + 0.0
            sred = velikost * m / 2
            for kot in (zacetek, zacetek + dolzina):
                x = sred + (r - debelina * m / 2) * math.sin(math.radians(kot))
                y = sred - (r - debelina * m / 2) * math.cos(math.radians(kot))
                d.ellipse((x - rob / 2, y - rob / 2, x + rob / 2, y + rob / 2), fill=POUDAREK + (255,))
    return s.resize((velikost, velikost), Image.LANCZOS)


def vnos():
    s = Image.new("RGBA", (300 * 2, 40 * 2), (0, 0, 0, 0))
    ImageDraw.Draw(s).rounded_rectangle((2, 2, 597, 77), radius=18, fill=(255, 255, 255, 22), outline=POUDAREK + (120,), width=3)
    return s.resize((300, 40), Image.LANCZOS)


def pika():
    s = Image.new("RGBA", (56, 56), (0, 0, 0, 0))
    ImageDraw.Draw(s).ellipse((6, 6, 50, 50), fill=BESEDILO + (255,))
    return s.resize((14, 14), Image.LANCZOS)


def kljucavnica():
    s = Image.new("RGBA", (136, 136), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    d.arc((40, 14, 96, 82), 180, 360, fill=BESEDILO + (255,), width=10)
    d.line((45, 48, 45, 66), fill=BESEDILO + (255,), width=10)
    d.line((91, 48, 91, 66), fill=BESEDILO + (255,), width=10)
    d.rounded_rectangle((26, 62, 110, 122), radius=12, fill=BESEDILO + (255,))
    d.ellipse((60, 82, 76, 98), fill=(11, 20, 36, 255))
    return s.resize((34, 34), Image.LANCZOS)


def velike_crke():
    s = Image.new("RGBA", (136, 136), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    d.polygon([(68, 14), (118, 70), (90, 70), (90, 98), (46, 98), (46, 70), (18, 70)], fill=BESEDILO + (255,))
    d.rectangle((46, 108, 90, 122), fill=BESEDILO + (255,))
    return s.resize((34, 34), Image.LANCZOS)


def tipkovnica():
    s = Image.new("RGBA", (136, 136), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    d.rounded_rectangle((8, 34, 128, 104), radius=10, outline=BESEDILO + (255,), width=8)
    for vrsta, y in enumerate((52, 70)):
        for x in range(26 + vrsta * 8, 112, 18):
            d.rectangle((x, y, x + 8, y + 8), fill=BESEDILO + (255,))
    d.rectangle((40, 88, 96, 94), fill=BESEDILO + (255,))
    return s.resize((34, 34), Image.LANCZOS)


def main():
    mapa = sys.argv[1] if len(sys.argv) > 1 else os.path.join(KOREN, "packaging", "tema-cinnamon", "plymouth", "safeer")
    os.makedirs(mapa, exist_ok=True)
    vodni_znak().save(os.path.join(mapa, "watermark.png"), optimize=True)
    for i in range(SLIK):
        lok(i * 360 / SLIK, 100).save(os.path.join(mapa, "throbber-%04d.png" % (i + 1)), optimize=True)
        lok(0, (i + 1) * 360 / SLIK).save(os.path.join(mapa, "animation-%04d.png" % (i + 1)), optimize=True)
    vnos().save(os.path.join(mapa, "entry.png"), optimize=True)
    pika().save(os.path.join(mapa, "bullet.png"), optimize=True)
    kljucavnica().save(os.path.join(mapa, "lock.png"), optimize=True)
    velike_crke().save(os.path.join(mapa, "capslock.png"), optimize=True)
    tipkovnica().save(os.path.join(mapa, "keyboard.png"), optimize=True)
    print("OK:", mapa, len(os.listdir(mapa)), "datotek")


if __name__ == "__main__":
    main()
