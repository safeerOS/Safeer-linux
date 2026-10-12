"""Geslo za e-posto: prilepljeni nedeljivi presledki in znaki izven ASCII ne smejo dati »streznika ni mogoce doseci«."""
import imaplib
import unittest
from unittest import mock

from core.sporocila import email as em


class OcistiGeslo(unittest.TestCase):
    def test_geslo_za_aplikacije_brez_presledkov(self):
        self.assertEqual(em.ocisti_geslo(" abcd efgh ijkl​mnop ", brez_presledkov=True), "abcdefghijklmnop")

    def test_navadno_geslo_ohrani_presledek(self):
        self.assertEqual(em.ocisti_geslo(" moje geslo﻿ "), "moje geslo")


class PrijavaUtf8(unittest.TestCase):
    def _adapter(self, geslo):
        return em.EmailAdapter("k", "a@b.si", "imap.b.si", "smtp.b.si", 993, 465, "a@b.si", geslo)

    def test_ascii_uporabi_login(self):
        imap = mock.MagicMock()
        with mock.patch.object(em.imaplib, "IMAP4_SSL", return_value=imap):
            self._adapter("abc").povezi()
        imap.login.assert_called_once_with("a@b.si", "abc")
        imap.authenticate.assert_not_called()

    def test_utf8_uporabi_authenticate_plain(self):
        imap = mock.MagicMock()
        with mock.patch.object(em.imaplib, "IMAP4_SSL", return_value=imap):
            self._adapter("geslošč").povezi()
        imap.login.assert_not_called()
        meh, odgovor = imap.authenticate.call_args[0]
        self.assertEqual(meh, "PLAIN")
        self.assertEqual(odgovor(b""), b"\0a@b.si\0" + "geslošč".encode("utf-8"))

    def test_zavrnjena_prijava_je_napaka_prijave(self):
        imap = mock.MagicMock()
        imap.authenticate.side_effect = imaplib.IMAP4.error("AUTHENTICATIONFAILED")
        with mock.patch.object(em.imaplib, "IMAP4_SSL", return_value=imap):
            with self.assertRaises(em.NapakaPrijave):
                self._adapter("geslošč").povezi()


if __name__ == "__main__":
    unittest.main()
