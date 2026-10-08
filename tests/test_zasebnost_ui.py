"""Zacetne strani in vmesnik (ui/) ne smejo ob zagonu poizvedovati pri tretji osebi (ikone, sledilci).

Zunanji pregled 8. 10. 2026: ui/home.js je za vsako bliznjico nalozil ikono z icons.duckduckgo.com.
"""
import os
import re
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UI = os.path.join(KOREN, "ui")

# Znani ponudniki ikon in sledilci, ki jih zacetna stran ne sme klicati.
PREPOVEDANO = re.compile(
    r"icons\.duckduckgo\.com|google\.com/s2/favicons|gstatic\.com|www\.google\.com/s2|"
    r"favicon\.yandex|getfavicon|besticon|google-analytics|googletagmanager|duckduckgo\.com/ip3", re.I)


class ZasebnostUI(unittest.TestCase):
    def test_ui_ne_poizveduje_ikon_pri_tretji_osebi(self):
        najdbe = []
        for ime in sorted(os.listdir(UI)):
            if not ime.endswith((".js", ".html", ".css")):
                continue
            vsebina = open(os.path.join(UI, ime), encoding="utf-8").read()
            for m in PREPOVEDANO.finditer(vsebina):
                vrstica = vsebina[:m.start()].count("\n") + 1
                najdbe.append(f"{ime}:{vrstica}: {m.group(0)}")
        self.assertEqual(najdbe, [], "ui/ poizveduje pri tretji osebi: " + "; ".join(najdbe))


if __name__ == "__main__":
    unittest.main()
