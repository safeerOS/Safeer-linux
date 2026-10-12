"""V Flatpaku Sporocila berejo in pisejo gesla v sistemsko zbirko (Secret Service), ne v libsecretovo zbirko Flatpaka."""
import unittest
from unittest import mock

from core.sporocila import skrivnosti as S


class Flatpak(unittest.TestCase):
    def test_v_flatpaku_secret_service(self):
        with mock.patch.object(S, "_v_flatpaku", return_value=True), \
             mock.patch.object(S, "_ss_preberi", return_value="geslo") as beri, \
             mock.patch.object(S, "_ss_shrani", return_value=True) as pisi, \
             mock.patch.object(S, "_ss_pozabi") as brisi, \
             mock.patch.object(S, "_secret", side_effect=AssertionError("libsecret se v Flatpaku ne sme uporabiti")):
            self.assertEqual(S.preberi("email:x"), "geslo")
            self.assertTrue(S.shrani("email:x", "g"))
            S.pozabi("email:x")
        beri.assert_called_once_with("email:x"); pisi.assert_called_once_with("email:x", "g"); brisi.assert_called_once_with("email:x")

    def test_napaka_vodila_ni_izjema(self):
        with mock.patch.object(S, "_v_flatpaku", return_value=True), \
             mock.patch.object(S, "_ss", side_effect=RuntimeError("ni vodila")):
            self.assertIsNone(S.preberi("email:x"))
            self.assertFalse(S.shrani("email:x", "g"))
            S.pozabi("email:x")

    def test_atributi_enaki_libsecret(self):
        self.assertEqual(S._ss_atributi("email:x"), {"application": S.STORITEV, "key": "email:x", "xdg:schema": "si.safeer.Sporocila"})


if __name__ == "__main__":
    unittest.main()
