"""Pretvorba datotek v Datotekah (core/os_pretvorba_datotek.py): slike, zvok, dokumenti - lokalno, brez spleta."""
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from core import os_pretvorba_datotek as p

KOREN = Path(__file__).resolve().parent.parent


class Pravila(unittest.TestCase):
    def test_skupine_in_cilji(self):
        self.assertEqual(p.skupina("a/Slika.HEIC"), "slika")
        self.assertEqual(p.skupina("Pesem.flac"), "zvok")
        self.assertEqual(p.skupina("Porocilo.docx"), "besedilo")
        self.assertEqual(p.skupina("Tabela.ods"), "preglednica")
        self.assertEqual(p.skupina("Film.mkv"), "", "video ima svojo pot (Pretvori za televizor)")
        m = p.moznosti("Slika.jpeg", najdi=lambda x: "/usr/bin/" + x)
        self.assertNotIn("jpg", m["cilji"], "lastne oblike ne ponudimo")
        self.assertTrue(m["orodje"])
        self.assertFalse(p.moznosti("Pesem.mp3", najdi=lambda x: None)["orodje"])
        self.assertEqual(p.moznosti("x.exe")["cilji"], [])

    def test_izhodna_pot_enolicna(self):
        with tempfile.TemporaryDirectory() as t:
            Path(t, "Slika.webp").write_bytes(b"x")
            self.assertEqual(p.izhodna_pot(os.path.join(t, "Slika.png"), "webp"), os.path.join(t, "Slika (1).webp"))
            self.assertEqual(p.izhodna_pot(os.path.join(t, "Slika.png"), "jpg"), os.path.join(t, "Slika.jpg"))

    def test_ukazi_brez_lupine(self):
        u = p.ukaz("/a/b c.png", "jpg", "/t/izhod.jpg", "convert")
        self.assertEqual(u[:3], ["convert", "/a/b c.png[0]", "-auto-orient"])
        self.assertIn("white", u, "prozornost v JPG postane bela, ne crna")
        z = p.ukaz("/a/x.wav", "mp3", "/t/izhod.mp3", "ffmpeg")
        self.assertIn("libmp3lame", z)
        self.assertEqual(z[-1], "/t/izhod.mp3")
        d = p.ukaz("/a/x.docx", "pdf", "", "soffice", profil="/t/profil", zacasna="/t")
        self.assertIn("-env:UserInstallation=file:///t/profil", d, "lasten profil: ne trci z odprtim LibreOffice")
        self.assertEqual(d[-3:], ["--outdir", "/t", "/a/x.docx"])

    def test_zavrne_kar_ne_gre(self):
        P = p.Pretvorbe(najdi=lambda x: None)
        self.assertEqual(P.zacni("/ni/te.png", "jpg")["koda"], "ni_datoteke")
        with tempfile.TemporaryDirectory() as t:
            pot = os.path.join(t, "a.png")
            Path(pot).write_bytes(b"x")
            self.assertEqual(P.zacni(pot, "exe")["koda"], "ni_mogoce")
            self.assertEqual(P.zacni(pot, "jpg")["koda"], "ni_orodja")

    def test_neuspeh_orodja_ne_pusti_nicesar(self):
        with tempfile.TemporaryDirectory() as t:
            pot = os.path.join(t, "a.png")
            Path(pot).write_bytes(b"x")
            P = p.Pretvorbe(najdi=lambda x: "/bin/" + x,
                            zazeni=lambda *a, **k: subprocess.CompletedProcess(a[0], 1, b"", b"napaka"))
            r = P.zacni(pot, "jpg")
            for _ in range(100):
                if P.stanje(r["id"])["stanje"] in ("koncano", "napaka"):
                    break
                time.sleep(0.02)
            self.assertEqual((P.stanje(r["id"])["stanje"], P.stanje(r["id"])["koda"]), ("napaka", "ni_uspelo"))
            self.assertEqual(sorted(os.listdir(t)), ["a.png"])

    def test_stran_ima_ukaz_in_besedila(self):
        js = (KOREN / "assets/os/delovna.js").read_text(encoding="utf-8")
        self.assertIn('klic("pretvorbaMoznosti", [e.pot])', js)
        self.assertIn('klic("pretvoriDatoteko", [e.pot, c])', js)
        for k in ("pretvoriV", "ptdNaslov", "ptdIzberi", "ptdPretvarjam", "ptdKoncano", "ptdNapaka", "ptdNiOrodja"):
            self.assertEqual(js.count(k + ":"), 2, k)
        py = (KOREN / "safeer_os.py").read_text(encoding="utf-8")
        for k in ('"pretvorbaMoznosti"', '"pretvoriDatoteko"', '"pretvorbaDatotekeStanje"'):
            self.assertIn(k, py)
        self.assertIn("os_pretvorba_datotek", (KOREN / "packaging/install_os_payload.sh").read_text(encoding="utf-8"))


@unittest.skipUnless(shutil.which("ffmpeg") and (shutil.which("convert") or shutil.which("magick")), "ni ffmpeg/ImageMagick")
class ZOrodji(unittest.TestCase):
    def test_slika_in_zvok(self):
        with tempfile.TemporaryDirectory() as t:
            slika, ton = os.path.join(t, "Slika.png"), os.path.join(t, "Ton.wav")
            subprocess.run([shutil.which("convert") or shutil.which("magick"), "-size", "40x30", "xc:red", slika], check=True)
            subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=1", ton], check=True)
            P = p.Pretvorbe()
            dela = [P.zacni(slika, "webp"), P.zacni(ton, "mp3")]
            konec = time.time() + 30
            while time.time() < konec and any(P.stanje(d["id"])["stanje"] in ("caka", "pretvarjam") for d in dela):
                time.sleep(0.1)
            self.assertEqual([P.stanje(d["id"])["stanje"] for d in dela], ["koncano", "koncano"])
            self.assertTrue(os.path.getsize(os.path.join(t, "Slika.webp")) > 0)
            self.assertTrue(os.path.getsize(os.path.join(t, "Ton.mp3")) > 0)


if __name__ == "__main__":
    unittest.main()
