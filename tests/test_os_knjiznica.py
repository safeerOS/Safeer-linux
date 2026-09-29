"""Lokalna knjižnica: indeksiranje samo iz izbrane mape in trajni podatki."""

import tempfile
import sqlite3
import unittest
from pathlib import Path

from core.os_knjiznica import Knjiznica, naslov_datoteke, vrsta_datoteke


class KnjiznicaTests(unittest.TestCase):
    def test_dodaj_mapo_razvrsti_in_preskoci_skrito(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mapa = root / "Mediji"
            (mapa / "Album").mkdir(parents=True)
            (mapa / ".skrito").mkdir()
            for rel in ("Album/Moja.pesem.flac", "Film_2026.mkv", "Serija.S02E03.mp4", "slika.jpg",
                        ".skrito/nevidna.mp3", "opombe.txt"):
                pot = mapa / rel
                pot.write_bytes(b"demo")
            knjiznica = Knjiznica(root / "baza.sqlite3")
            self.assertEqual(knjiznica.dodaj_mapo(mapa), 4)
            vnosi = knjiznica.seznam()
            self.assertEqual({v["vrsta"] for v in vnosi}, {"glasba", "filmi", "serije", "slike"})
            self.assertEqual({v["vrsta"] for v in knjiznica.seznam("video")}, {"filmi", "serije"})
            self.assertTrue(all(v["naVoljo"] for v in vnosi))
            self.assertEqual(Knjiznica(root / "baza.sqlite3").seznam("glasba")[0]["ime"], "Moja pesem")

    def test_iskanje_paginacija_in_manjkajoca_datoteka(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            knjiznica = Knjiznica(root / "baza.sqlite3")
            poti = []
            for ime in ("Polet.mp3", "Zima.mp3", "Poletje.mp4"):
                p = root / ime
                p.write_bytes(b"demo")
                poti.append(p)
            self.assertEqual(knjiznica.dodaj(poti), 3)
            self.assertEqual(len(knjiznica.seznam(meja=2)), 2)
            self.assertEqual(len(knjiznica.seznam(meja=2, odmik=2)), 1)
            self.assertEqual([v["ime"] for v in knjiznica.seznam(iskanje="Polet")], ["Polet", "Poletje"])
            sumnik = root / "Šuma.mp3"
            sumnik.write_bytes(b"demo")
            knjiznica.dodaj([sumnik])
            self.assertEqual(knjiznica.seznam(iskanje="šum")[0]["ime"], "Šuma")
            poti[0].unlink()
            self.assertFalse(knjiznica.dobi(str(poti[0])) is None)
            self.assertFalse(next(v for v in knjiznica.seznam() if v["ime"] == "Polet")["naVoljo"])
            knjiznica.odstrani(str(poti[0]))
            self.assertIsNone(knjiznica.dobi(str(poti[0])))

    def test_razvrstitev_ne_ugiba_serije_iz_poljubnega_ime(self):
        self.assertEqual(vrsta_datoteke(Path("Film.mp4")), "filmi")
        self.assertEqual(vrsta_datoteke(Path("Oddaja_S01E02.mkv")), "serije")
        self.assertEqual(vrsta_datoteke(Path("skripta.sh")), "")
        self.assertEqual(naslov_datoteke(Path("Moj_album.flac")), "Moj album")

    def test_shranjeni_tokovi_ostanejo_po_ponovnem_zagonu(self):
        with tempfile.TemporaryDirectory() as tmp:
            pot = Path(tmp) / "mediji.sqlite3"
            knjiznica = Knjiznica(pot)
            knjiznica.dodaj_tok("Moja TV", "https://example.test/tv.m3u8", "tv")
            knjiznica.dodaj_tok("Radio", "https://example.test/radio", "radio")
            knjiznica.dodaj_tok("Radio 2", "https://example.test/radio", "radio")
            vnosi = Knjiznica(pot).tokovi()
            self.assertEqual(len(vnosi), 2)
            self.assertEqual(knjiznica.dobi_tok("https://example.test/radio")["ime"], "Radio 2")
            self.assertTrue(knjiznica.odstrani_tok("https://example.test/radio"))
            self.assertFalse(knjiznica.odstrani_tok("https://example.test/radio"))
            self.assertEqual(len(Knjiznica(pot).tokovi()), 1)
            for ime, url, vrsta in (("", "https://example.test/live", "tv"),
                                     ("TV", "file:///home/user/video", "tv"),
                                     ("Radio", "https://example.test/radio", "other")):
                with self.assertRaises(ValueError):
                    knjiznica.dodaj_tok(ime, url, vrsta)

    def test_nadaljevanje_videa_in_nadgradnja_stare_baze(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pot_baze = root / "mediji.sqlite3"
            with sqlite3.connect(pot_baze) as baza:
                baza.execute("""CREATE TABLE mediji (
                    pot TEXT PRIMARY KEY, naslov TEXT NOT NULL, vrsta TEXT NOT NULL,
                    dodano INTEGER NOT NULL DEFAULT (unixepoch()), zadnjic INTEGER NOT NULL DEFAULT 0)""")
            knjiznica = Knjiznica(pot_baze)
            film, pesem = root / "Film.mp4", root / "Pesem.mp3"
            film.touch(); pesem.touch()
            knjiznica.dodaj([film, pesem])
            knjiznica.shrani_napredek(str(film), 62.8, 180)
            knjiznica.shrani_napredek(str(pesem), 62, 180)
            self.assertEqual(Knjiznica(pot_baze).dobi(str(film))["pozicija"], 62)
            self.assertEqual(knjiznica.dobi(str(pesem))["pozicija"], 0)
            self.assertEqual(knjiznica.seznam("filmi")[0]["trajanje"], 180)
            knjiznica.shrani_napredek(str(film), 170, 180)
            self.assertEqual(knjiznica.dobi(str(film))["pozicija"], 0)
            knjiznica.shrani_napredek(str(film), 70, 180)
            knjiznica.ponastavi_napredek(str(film))
            self.assertEqual(knjiznica.dobi(str(film))["pozicija"], 0)

    def test_album_predvaja_naslednje_skladbe_iste_mape(self):
        with tempfile.TemporaryDirectory() as tmp:
            koren = Path(tmp)
            (koren / "Album").mkdir()
            (koren / "Drug album").mkdir()
            poti = [koren / "Album" / ime for ime in ("01-Uvod.mp3", "02-Sredina.mp3", "03-Konec.mp3")]
            drugje = koren / "Drug album" / "04-Bonus.mp3"
            for pot in poti + [drugje]:
                pot.touch()
            knjiznica = Knjiznica(koren / "baza.sqlite3")
            knjiznica.dodaj(poti + [drugje])
            album = knjiznica.skladbe_iz_mape(str(poti[1]))
            self.assertEqual([v["pot"] for v in album], [str(p) for p in poti])
            self.assertEqual([v["izbrana"] for v in album], [False, True, False])
            # Zadnja skladba ima album pred sabo, da »nazaj« deluje.
            self.assertEqual(len(knjiznica.skladbe_iz_mape(str(poti[2]))), 3)
            poti[2].unlink()
            self.assertEqual(len(knjiznica.skladbe_iz_mape(str(poti[1]))), 2)

    def test_seznam_je_abecedno_urejen_in_predvajanje_ga_ne_premesa(self):
        with tempfile.TemporaryDirectory() as tmp:
            koren = Path(tmp)
            poti = [koren / ime for ime in ("zz top.mp3", "Čuki.mp3", "abba.mp3")]
            for pot in poti:
                pot.touch()
            knjiznica = Knjiznica(koren / "baza.sqlite3")
            knjiznica.dodaj(poti)
            knjiznica.predvajano(str(poti[0]))
            self.assertEqual([Path(v["pot"]).name for v in knjiznica.seznam()],
                             ["abba.mp3", "zz top.mp3", "Čuki.mp3"] if "Č".casefold() > "z" else
                             ["abba.mp3", "Čuki.mp3", "zz top.mp3"])

    def test_medijski_center_pokaze_samo_predvajalnike(self):
        from core import os_programi
        self.assertTrue(os_programi.je_predvajalnik(["AudioVideo", "Player", "Video", "TV"]))  # Celluloid
        self.assertTrue(os_programi.je_predvajalnik(["Audio", "AudioVideo"], "Shortwave Listen to internet radio"))
        self.assertFalse(os_programi.je_predvajalnik(["Graphics", "Photography", "Viewer"], "Pix"))
        self.assertFalse(os_programi.je_predvajalnik(["Graphics", "Scanning"], "Document Scanner"))
        self.assertFalse(os_programi.je_predvajalnik(["Utility", "RemoteAccess", "AudioVideo"], "Safeer Control"))
        self.assertFalse(os_programi.je_predvajalnik(["AudioVideo", "Audio"], "Easy Effects Audio effects"))
        with tempfile.TemporaryDirectory() as tmp:
            pot = Path(tmp) / "vlc.desktop"
            pot.write_text("[Desktop Entry]\nType=Application\nName=VLC\nExec=vlc\nCategories=AudioVideo;Player;\n")
            vnos = os_programi.preberi_vnos(str(pot))
            from core import os_media_besedila as mb
            self.assertEqual(mb.besedilo("premor", "de"), "Pause")
            self.assertEqual(mb.besedilo("premor", "xx"), "Pause")
            for jezik in mb.JEZIKI:
                self.assertEqual(set(mb.BESEDILA[jezik]), set(mb.BESEDILA["en"]), jezik)
            self.assertTrue(vnos["medij"])

    def test_odstranitev_mape_ne_brise_datotek_in_ohrani_nadmapo(self):
        with tempfile.TemporaryDirectory() as tmp:
            koren = Path(tmp)
            (koren / "Glasba" / "Album").mkdir(parents=True)
            a = koren / "Glasba" / "a.mp3"; b = koren / "Glasba" / "Album" / "b.mp3"
            a.touch(); b.touch()
            knjiznica = Knjiznica(koren / "baza.sqlite3")
            knjiznica.dodaj_mapo(koren / "Glasba" / "Album")
            knjiznica.dodaj_mapo(koren / "Glasba")
            self.assertEqual(knjiznica.odstrani_mapo(str((koren / "Glasba" / "Album").resolve())), 0)  # b pokriva nadmapa
            self.assertEqual(len(knjiznica.seznam()), 2)
            self.assertEqual(knjiznica.odstrani_mapo(str((koren / "Glasba").resolve())), 2)
            self.assertEqual(knjiznica.seznam(), [])
            self.assertTrue(a.exists() and b.exists())
            self.assertIsNone(knjiznica.odstrani_mapo("/ni/izbrana"))

    def test_osvezitev_pozabi_izbrisane_a_ne_odklopljenega_diska(self):
        with tempfile.TemporaryDirectory() as tmp:
            koren = Path(tmp)
            (koren / "M").mkdir(); (koren / "Disk").mkdir()
            ena = koren / "M" / "ena.mp3"; dve = koren / "M" / "dve.mp3"; disk = koren / "Disk" / "film.mkv"
            for p in (ena, dve, disk):
                p.touch()
            knjiznica = Knjiznica(koren / "baza.sqlite3")
            knjiznica.dodaj_mapo(koren / "M"); knjiznica.dodaj_mapo(koren / "Disk")
            dve.unlink()
            disk.unlink(); (koren / "Disk").rmdir()      # kot odklopljen disk
            knjiznica.osvezi_mape()
            imena = sorted(v["ime"] for v in knjiznica.seznam())
            self.assertEqual(imena, ["ena", "film"])
            mape = {Path(m["pot"]).name: m for m in knjiznica.mape_podrobno()}
            self.assertEqual((mape["M"]["stevilo"], mape["M"]["naVoljo"]), (1, True))
            self.assertEqual((mape["Disk"]["stevilo"], mape["Disk"]["naVoljo"]), (1, False))

    def test_osvezitev_izbrane_mape_najde_nove_datoteke(self):
        with tempfile.TemporaryDirectory() as tmp:
            koren = Path(tmp)
            mapa = koren / "Mediji"
            mapa.mkdir()
            knjiznica = Knjiznica(koren / "baza.sqlite3")
            self.assertEqual(knjiznica.dodaj_mapo(mapa), 0)
            self.assertEqual(Knjiznica(koren / "baza.sqlite3").seznam_map(), [str(mapa)])
            (mapa / "Nova.mp3").touch()
            self.assertEqual(knjiznica.osvezi_mape(), 1)
            self.assertEqual(knjiznica.seznam("glasba")[0]["ime"], "Nova")


if __name__ == "__main__":
    unittest.main()
