"""Dejanja v seznamu pogovorov (lastnik, 17. 10. 2026): prebrano/neprebrano, zvezdica, arhiv, kos, nezeleno, mapa,
napaka streznika in hitri odgovor (Re:, In-Reply-To, References).

Samo lokalni nadomestni streznik (tests/lazni_imap.py na 127.0.0.1) - brez interneta in brez pravih racunov.
"""

import imaplib
import os
import sys
import tempfile
import unittest
from email import message_from_bytes, policy
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.sporocila.email import EmailAdapter
from core.sporocila.model import Kanal
from core.sporocila.storitev import StoritevSporocil
from lazni_imap import LazniImap, pismo


def _imap_brez_tls(host, port=993, ssl_context=None, timeout=None):
    return imaplib.IMAP4(host, port, timeout=timeout)


class _Osnova(unittest.TestCase):
    def setUp(self):
        self.imap_ssl = mock.patch.object(imaplib, "IMAP4_SSL", _imap_brez_tls)
        self.imap_ssl.start()
        self.streznik = LazniImap(idle=False)
        self.nab = self.streznik.nabiralnik
        self.mapa = tempfile.TemporaryDirectory()
        self.st = StoritevSporocil(os.path.join(self.mapa.name, "s.db"))
        self.a = EmailAdapter("e1", "jaz@example.test", "127.0.0.1", "127.0.0.1", self.streznik.vrata, 465, geslo="skrivno")
        self.st.registriraj(Kanal("e1", "email", "Posta", "nepovezan"), self.a, {"naslov": "jaz@example.test"})

    def tearDown(self):
        self.st.zapri()
        self.a.zapri()
        self.streznik.ustavi()
        self.imap_ssl.stop()
        self.mapa.cleanup()

    def _pogovori(self):
        return {p.id: p for p in self.st.pogovori("e1")}

    def _uidi(self, mapa=None):
        with self.nab.zaklep:
            pisma = self.nab.pisma if mapa is None else self.nab.mape[mapa][1]
            return [p["uid"] for p in pisma]


class TestPosebneMape(unittest.TestCase):
    def test_special_use_in_gmail(self):
        gmail = [("INBOX", set()), ("[Gmail]/All Mail", {"\\all", "\\haschildren"}), ("[Gmail]/Trash", {"\\trash"}),
                 ("[Gmail]/Spam", {"\\junk"}), ("[Gmail]", {"\\noselect"})]
        self.assertEqual(EmailAdapter.posebna_mapa(gmail, "arhiv"), "[Gmail]/All Mail")
        self.assertEqual(EmailAdapter.posebna_mapa(gmail, "izbrisi"), "[Gmail]/Trash")
        self.assertEqual(EmailAdapter.posebna_mapa(gmail, "nezeleno"), "[Gmail]/Spam")

    def test_archive_ima_prednost_pred_all(self):
        mape = [("Vse", {"\\all"}), ("Arhiv", {"\\archive"})]
        self.assertEqual(EmailAdapter.posebna_mapa(mape, "arhiv"), "Arhiv")

    def test_brez_oznak_po_imenu_in_brez_mape(self):
        mape = [("INBOX", set()), ("INBOX.Trash", set()), ("Spam", set())]
        self.assertEqual(EmailAdapter.posebna_mapa(mape, "izbrisi"), "INBOX.Trash")
        self.assertEqual(EmailAdapter.posebna_mapa(mape, "nezeleno"), "Spam")
        self.assertEqual(EmailAdapter.posebna_mapa(mape, "arhiv"), "")


class TestDejanjaImap(_Osnova):
    def setUp(self):
        super().setUp()
        self.nab.dodaj_mapo("Archive", "\\Archive")
        self.nab.dodaj_mapo("Trash", "\\Trash")
        self.nab.dodaj_mapo("Junk", "\\Junk")
        self.nab.dodaj_mapo("Projekti")
        self.ana = [self.nab.dodaj(pismo(mid="a%d" % i, telo="Ana %d" % i)) for i in range(3)]
        self.bor = self.nab.dodaj(pismo(od="Bor <bor@example.test>", mid="b1", telo="Bor"))
        self.st.sinhroniziraj("e1")

    def test_prebrano_in_neprebrano_na_strezniku(self):
        self.st.dejanje("e1", "ana@example.test", "prebrano")
        with self.nab.zaklep:
            self.assertTrue(all("\\Seen" in p["zastavice"] for p in self.nab.pisma if p["uid"] in self.ana))
        self.assertEqual(self._pogovori()["ana@example.test"].neprebrano, 0)
        self.st.dejanje("e1", "ana@example.test", "neprebrano")
        with self.nab.zaklep:
            zast = {p["uid"]: p["zastavice"] for p in self.nab.pisma}
        self.assertNotIn("\\Seen", zast[self.ana[-1]])          # samo zadnje pismo
        self.assertIn("\\Seen", zast[self.ana[0]])
        self.assertEqual(self._pogovori()["ana@example.test"].neprebrano, 1)

    def test_zvezdica(self):
        self.st.dejanje("e1", "bor@example.test", "zvezdica")
        with self.nab.zaklep:
            self.assertIn("\\Flagged", next(p for p in self.nab.pisma if p["uid"] == self.bor)["zastavice"])
        skupine = self.st.zdruzeni_pogovori("e1")
        zv = {p["id"]: p["zvezdica"] for s in skupine for p in s["pogovori"]}
        self.assertTrue(zv["bor@example.test"])
        self.assertFalse(zv["ana@example.test"])
        self.st.dejanje("e1", "bor@example.test", "brez_zvezdice")
        with self.nab.zaklep:
            self.assertNotIn("\\Flagged", next(p for p in self.nab.pisma if p["uid"] == self.bor)["zastavice"])

    def test_arhiv_z_move(self):
        self.st.dejanje("e1", "ana@example.test", "arhiv")
        self.assertEqual(self._uidi(), [self.bor])
        self.assertEqual(len(self._uidi("Archive")), 3)
        self.assertNotIn("ana@example.test", self._pogovori())
        self.assertEqual(sum(u.startswith("UID MOVE") for u in self.nab.ukazi), 1)

    def test_izbrisi_brez_move_copy_in_uid_expunge(self):
        self.nab.move = False
        self.st.dejanje("e1", "ana@example.test", "izbrisi")
        self.assertEqual(self._uidi(), [self.bor])
        self.assertEqual(len(self._uidi("Trash")), 3)
        self.assertTrue(any(u.startswith("UID COPY") for u in self.nab.ukazi))
        self.assertTrue(any(u.startswith("UID EXPUNGE") for u in self.nab.ukazi))
        self.assertNotIn("EXPUNGE", self.nab.ukazi)              # navadni EXPUNGE ni bil potreben

    def test_brez_uidplus_ne_izbrise_tujih_oznacenih(self):
        self.nab.move, self.nab.uidplus = False, False
        with self.nab.zaklep:
            next(p for p in self.nab.pisma if p["uid"] == self.bor)["zastavice"].add("\\Deleted")   # drug odjemalec
        self.st.dejanje("e1", "ana@example.test", "nezeleno")
        self.assertEqual(len(self._uidi("Junk")), 3)
        self.assertIn(self.bor, self._uidi())                    # tuje oznaceno pismo ostane

    def test_premakni_v_mapo_in_seznam_map(self):
        imena = {m["ime"]: m for m in self.a.mape()}
        self.assertIn("Projekti", imena)
        self.assertNotIn("INBOX", imena)
        self.assertEqual(imena["Trash"]["posebna"], "trash")
        self.st.dejanje("e1", "bor@example.test", "mapa", "Projekti")
        self.assertEqual(len(self._uidi("Projekti")), 1)
        with self.assertRaises(ValueError):
            self.st.dejanje("e1", "ana@example.test", "mapa", "Neobstojeca")

    def test_napaka_streznika_pusti_lokalno(self):
        self.nab.zavrni.add("MOVE")
        with self.assertRaises(RuntimeError):
            self.st.dejanje("e1", "ana@example.test", "arhiv")
        self.assertIn("ana@example.test", self._pogovori())      # vmesnik vrstico vrne
        self.assertEqual(len(self._uidi()), 4)

    def test_most_vrne_kode_napak_brez_besedila_streznika(self):
        from core.os_sporocila import SporocilaOS
        self.nab.zavrni.add("MOVE")
        os_ = SporocilaOS.__new__(SporocilaOS)
        os_.storitev = self.st
        with mock.patch.object(SporocilaOS, "seznam", return_value={"skupine": []}):
            izid = os_.dejanje([["e1", "ana@example.test"], ["e1", "bor@example.test"]], "arhiv")
        self.assertEqual([n["koda"] for n in izid["napake"]], ["streznik", "streznik"])
        self.nab.zavrni.clear()
        with mock.patch.object(SporocilaOS, "seznam", return_value={"skupine": []}):
            izid = os_.dejanje([["e1", "ana@example.test"], ["e1", "bor@example.test"]], "arhiv")
        self.assertEqual(izid["napake"], [])
        self.assertEqual(self._uidi(), [])
        self.assertEqual(sum(u.startswith("UID MOVE") for u in self.nab.ukazi), 2)   # en ukaz za oba pogovora (+1 zavrnjen)

    def test_nova_uidvalidity_ne_premakne_napacnih_pisem(self):
        with self.nab.zaklep:
            self.nab.uidvalidity += 1
        with self.assertRaises(RuntimeError):
            self.st.dejanje("e1", "ana@example.test", "izbrisi")
        self.assertEqual(len(self._uidi()), 4)

    def test_klepet_brez_strezniskih_dejanj(self):
        class Klepet:
            vrsta = "matrix"

            def obnovi(self, stanje):
                pass
        self.st.adapterji["m1"] = Klepet()
        self.assertNotIn("arhiv", self.st.dejanja_kanala("m1"))
        self.assertIn("neprebrano", self.st.dejanja_kanala("m1"))
        with self.assertRaises(ValueError):
            self.st.dejanje("m1", "soba", "izbrisi")
        self.assertIn("arhiv", self.st.dejanja_kanala("e1"))


class TestHitriOdgovor(_Osnova):
    def test_odgovor_nosi_re_in_in_reply_to(self):
        self.nab.dodaj(pismo(zadeva="Sestanek", mid="zadnje", telo="Ob 10?"))
        self.st.sinhroniziraj("e1")
        smtp = mock.MagicMock()
        with mock.patch("core.sporocila.email.smtplib.SMTP_SSL", return_value=smtp):
            s = self.st.poslji("e1", "ana@example.test", "Velja.")
        msg = smtp.send_message.call_args[0][0]
        msg = message_from_bytes(msg.as_bytes(), policy=policy.default)
        self.assertEqual(msg["Subject"], "Re: Sestanek")
        self.assertEqual(msg["In-Reply-To"], "<zadnje@example.test>")
        self.assertEqual(msg["References"], "<zadnje@example.test>")
        self.assertEqual(s.stanje, "poslano")


class TestStranSporocil(unittest.TestCase):
    """Stran: dejanja, tipke, razveljavi in hitri odgovor so povezani; besedila v vseh jezikih."""

    @classmethod
    def setUpClass(cls):
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(koren, "assets/os/os.js"), encoding="utf-8") as f:
            cls.js = f.read()
        with open(os.path.join(koren, "assets/os/besedila.js"), encoding="utf-8") as f:
            cls.besedila = f.read()

    def test_klici_in_tipke(self):
        for niz in ('"sporocilaDejanje"', '"sporocilaMapeRacuna"', "hitriOdgovorOkno", "razveljaviZadnje", "obvestiRazveljavi",
                    'kljucTipke === "e"', '"Delete"', '"#"', 'kljucTipke === "u"', 'kljucTipke === "s"',
                    'kljucTipke === "r"'):
            self.assertTrue(niz in self.js, niz)

    def test_besedila_v_vseh_jezikih(self):
        for kljuc in ("dejanjeArhiviraj", "dejanjeIzbrisi", "dejanjeNezeleno", "dejanjeZvezdica", "dejanjeNeprebrano",
                      "dejanjePremakni", "hitriOdgovorPoslano", "dejanjeRazveljavi", "dejanjeNapaka", "mapaZvezdica"):
            self.assertEqual(self.besedila.count('"%s":' % kljuc), 6, kljuc)


if __name__ == "__main__":
    unittest.main()
