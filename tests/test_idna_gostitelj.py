"""Seznami groznj in oglasov imajo unicode imena zapisana kot xn-- (IDNA); ujemanje mora veljati v obeh zapisih."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import adblock  # noqa: E402


class IdnaGostitelj(unittest.TestCase):

    def test_unicode_ime_ujame_vnos_xn(self):
        t = adblock.ReverseDomainTrie()
        t.insert("раураl.com".encode("idna").decode())  # cirilica, kot v seznamu: xn--...
        self.assertTrue(t.is_blocked("раураl.com"))
        self.assertTrue(t.is_blocked("login.РАУРАL.com."))
        self.assertFalse(t.is_blocked("paypal.com"))

    def test_vnos_v_unicode_ujame_xn(self):
        t = adblock.ReverseDomainTrie()
        t.insert(".bücher.de")
        self.assertTrue(t.is_blocked("www.xn--bcher-kva.de"))

    def test_gostitelj_iz_naslova(self):
        self.assertEqual(adblock._url_host("https://Bücher.DE/x"), "xn--bcher-kva.de")
        self.assertEqual(adblock._url_host("example.com"), "example.com")
        self.assertEqual(adblock.ascii_gostitelj("a..b\udcff"), "a..b\udcff")  # nezapisljivo ostane, ne pade


if __name__ == "__main__":
    unittest.main()
