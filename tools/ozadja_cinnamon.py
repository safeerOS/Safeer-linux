#!/usr/bin/env python3
"""Ozadja Safeer Cinnamon (ponovljivo): python3 tools/ozadja_cinnamon.py [mapa] [sirina visina]

Narise tri ozadja (numpy + Pillow, brez zunanjih slik): Aurora, Zora nad jezerom in Globina.
Vsa so temna na sredini in svetlejsa na robovih, da so polprosojne plosce delovne povrsine berljive.
Licenca: kot tema (GPL-3.0-or-later), lastno delo Safeer.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

RNG = np.random.default_rng(7)


def navpicni(h, w, barve):
    """Navpicni preliv: barve = [(polozaj 0..1, (r,g,b)), ...]."""
    y = np.linspace(0, 1, h)[:, None]
    out = np.zeros((h, w, 3), np.float32)
    for k in range(3):
        xp = [p for p, _ in barve]
        fp = [c[k] for _, c in barve]
        out[..., k] = np.interp(y, xp, fp)
    return out


def greben(w, h, osnova, hrapavost, seed, gladkost=1.0):
    """Gorski greben: y-koordinata za vsak x (vecoktavni sum)."""
    r = np.random.default_rng(seed)
    x = np.linspace(0, 1, w)
    y = np.zeros(w)
    amp, freq = 1.0, 2.0
    for _ in range(7):
        faze = r.uniform(0, 2 * np.pi, 3)
        y += amp * (np.sin(x * freq * np.pi + faze[0]) * 0.6 + np.sin(x * freq * 1.7 * np.pi + faze[1]) * 0.4)
        amp *= 0.5 ** gladkost
        freq *= 2.1
    y = (y - y.min()) / (y.max() - y.min())
    return (osnova - y * hrapavost) * h


def nalozi_plast(img, greben_y, barva_zgoraj, barva_spodaj, meglica=0.0):
    h, w, _ = img.shape
    yy = np.arange(h)[:, None]
    maska = yy >= greben_y[None, :]
    t = np.clip((yy - greben_y[None, :]) / (h * 0.35), 0, 1)
    barva = np.array(barva_zgoraj, np.float32)[None, None] * (1 - t[..., None]) + \
        np.array(barva_spodaj, np.float32)[None, None] * t[..., None]
    if meglica:
        rob = np.clip(1 - (yy - greben_y[None, :]) / (h * 0.06), 0, 1) * meglica
        barva = barva * (1 - rob[..., None]) + img * rob[..., None]
    img[maska] = barva[maska]
    return img


def zvezde(img, n, zgornji_del):
    h, w, _ = img.shape
    for _ in range(n):
        x, y = RNG.integers(0, w), RNG.integers(0, int(h * zgornji_del))
        s = RNG.uniform(0.35, 1.0) ** 3
        img[y, x] = np.minimum(255, img[y, x] + 210 * s)
    return img


def sij(img, cx, cy, radij, barva, moc):
    h, w, _ = img.shape
    yy, xx = np.mgrid[0:h, 0:w]
    d = np.sqrt(((xx - cx) / radij) ** 2 + ((yy - cy) / radij) ** 2)
    a = np.exp(-d * d) * moc
    img += a[..., None] * np.array(barva, np.float32)[None, None]
    return img


def aurora(h, w):
    img = navpicni(h, w, [(0, (6, 10, 26)), (0.45, (12, 24, 52)), (0.62, (22, 44, 78)), (1, (8, 14, 28))])
    img = zvezde(img, int(w * h / 3500), 0.55)
    # zavese polarnega sija: vsaka je pas vzdolz sinusoide z navpicnim prelivom navzgor
    sloj = np.zeros((h, w, 3), np.float32)
    x = np.arange(w)
    for i, (barva, faza, visina, moc) in enumerate([
            ((40, 255, 170), 0.3, 0.30, 0.55), ((60, 210, 255), 1.9, 0.24, 0.45), ((150, 110, 255), 3.1, 0.20, 0.35)]):
        krivulja = (0.40 + 0.07 * np.sin(x / w * 2.6 * np.pi + faza) + 0.03 * np.sin(x / w * 9 * np.pi + faza * 2)) * h
        # zarki: nepravilni (vsota vec nakljucnih frekvenc), mehki - ne "crtna koda"
        r = np.random.default_rng(i + 40)
        zarki = np.zeros(w)
        for f in r.uniform(18, 70, 6):
            zarki += np.sin(x / w * f * np.pi + r.uniform(0, 6.3))
        zarki = 0.78 + 0.22 * zarki / 6
        jakost = (0.5 + 0.5 * np.sin(x / w * 3.3 * np.pi + faza * 1.3)) ** 1.5 * moc
        yy = np.arange(h)[:, None]
        nad = (krivulja[None, :] - yy) / (visina * h)
        profil = np.where(nad >= 0, np.exp(-nad * 3.0), np.exp(nad * 18.0))
        a = profil * (zarki * jakost)[None, :]
        sloj += a[..., None] * np.array(barva, np.float32)[None, None]
    sloj = np.asarray(Image.fromarray(np.clip(sloj, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(w / 400)), np.float32)
    img = img + sloj
    obzorje = int(h * 0.70)
    for seed, osnova, hrap, zg, sp in [(3, 0.69, 0.17, (20, 32, 58), (14, 22, 40)),
                                       (5, 0.705, 0.11, (11, 19, 36), (8, 13, 24)),
                                       (11, 0.71, 0.05, (6, 10, 19), (5, 8, 15))]:
        img = nalozi_plast(img, greben(w, h, osnova, hrap, seed), zg, sp)
    # jezero: zrcalo zgornjega dela, zatemnjeno in zamegljeno
    zrcalo = img[obzorje - (h - obzorje):obzorje][::-1].copy()
    zrcalo = np.asarray(Image.fromarray(np.clip(zrcalo, 0, 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(w / 900)), np.float32)
    t = np.linspace(0.55, 0.15, zrcalo.shape[0])[:, None, None]
    img[obzorje:] = zrcalo * t + np.array((5, 9, 18), np.float32) * (1 - t)
    return img


def zora(h, w):
    img = navpicni(h, w, [(0, (14, 26, 58)), (0.38, (46, 74, 128)), (0.58, (196, 150, 160)), (0.66, (250, 196, 150)),
                          (1, (30, 40, 70))])
    img = sij(img, w * 0.62, h * 0.64, w * 0.16, (255, 190, 120), 0.65)
    obzorje = int(h * 0.72)
    for seed, osnova, hrap, zg, sp in [(21, 0.62, 0.22, (120, 128, 170), (96, 104, 150)),
                                       (23, 0.68, 0.20, (70, 82, 128), (54, 64, 104)),
                                       (29, 0.73, 0.12, (34, 44, 80), (24, 32, 60))]:
        img = nalozi_plast(img, greben(w, h, osnova, hrap, seed, 1.1), zg, sp, meglica=0.3)
    zrcalo = img[obzorje - (h - obzorje):obzorje][::-1].copy()
    zrcalo = np.asarray(Image.fromarray(np.clip(zrcalo, 0, 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(w / 700)), np.float32)
    t = np.linspace(0.75, 0.35, zrcalo.shape[0])[:, None, None]
    img[obzorje:] = zrcalo * t + np.array((20, 28, 52), np.float32) * (1 - t)
    return img


def globina(h, w):
    img = navpicni(h, w, [(0, (9, 14, 30)), (1, (6, 10, 22))])
    for cx, cy, r, b, m in [(0.12, 0.18, 0.30, (40, 110, 220), 0.32), (0.90, 0.15, 0.28, (120, 70, 210), 0.26),
                            (0.78, 0.95, 0.32, (20, 170, 170), 0.22), (0.20, 0.98, 0.22, (60, 90, 200), 0.20)]:
        img = sij(img, w * cx, h * cy, w * r, b, m)
    return img


def shrani(img, pot):
    # rahel sum proti stopnicam v prelivih (JPEG)
    img = img + RNG.normal(0, 1.4, img.shape).astype(np.float32)
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).save(pot, quality=92, optimize=True, subsampling=0)


def main():
    mapa = sys.argv[1] if len(sys.argv) > 1 else "packaging/tema-cinnamon/ozadje"
    w, h = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else (3840, 2160)
    os.makedirs(mapa, exist_ok=True)
    for ime, fn in [("safeer-aurora", aurora), ("safeer-zora", zora), ("safeer-globina", globina)]:
        shrani(fn(h, w), os.path.join(mapa, ime + ".jpg"))
        print(ime)


if __name__ == "__main__":
    main()
