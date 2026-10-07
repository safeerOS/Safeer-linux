"""Prisilni temni način Safeer Browserja (uporabniški slog z barvnim filtrom): stran mora biti po njem berljiva.

Izmerjeno 7. 10. 2026 v WebKitGTK 2.52.6 (preizkusni zabojnik; dvanajst vrst strani, pogled priklopljen kot v izdelku,
slog kot uporabniški list in vbrizgan v stran, temna tema namizja). Filter na korenskem elementu obrne VSE, kar stran
nariše - tudi ozadje korena in osnovo pogleda pod njim:
  - slog do 1.0.107 je korenu vsilil »temno« ozadje #121212, ki je po filtru svetlo sivo (#d0d0d0). Stran brez svojega
    ozadja (privzeto črno besedilo je po filtru #dddddd) in stran s svojim svetlim ozadjem na korenu (vsiljeno ozadje
    ga je prepisalo) sta bili svetli s svetlim besedilom - neberljivi;
  - prvi popravek v izdaji 1.0.108 je vsilil belo ozadje in svetlo barvno shemo: strani s SVOJIM temnim ozadjem na
    korenu in svetlim besedilom so postale temne s temnim besedilom (četrti neodvisni pregled; potrjeno z meritvijo);
  - brez vsakega ozadja v slogu je berljivih vseh dvanajst: stran obdrži svoje ozadje (ali osnovo pogleda, ki je pod
    spletnimi stranmi bela - core/ozadje_strani.py), filter pa ga obrne skupaj z besedilom.
Zato slog korenu NE določa ne ozadja ne barvne sheme. Preizkus pripne to in lastnost filtra, od katere je berljivost
odvisna: svetla stran postane temna z dovolj razlike med ozadjem in besedilom.
"""
import re
import unittest

from core import adblock


def po_filtru(siva: int, obrat: float, kontrast: float) -> int:
    """Siva vrednost 0..255 po filtru invert(obrat) contrast(kontrast); zasuk odtenka sivin ne spremeni."""
    v = siva / 255.0
    v = v * (1 - 2 * obrat) + obrat
    v = (v - 0.5) * kontrast + 0.5
    return round(max(0.0, min(1.0, v)) * 255)


class Slog(unittest.TestCase):
    def setUp(self):
        self.css = adblock.FORCE_DARK_MODE_CSS
        self.pravila = re.sub(r"/\*.*?\*/", "", self.css, flags=re.S)
        self.koren = re.search(r"(?:^|\})\s*html\s*\{([^}]*)\}", self.pravila).group(1)

    def test_koren_ima_samo_filter(self):
        lastnosti = [d.split(":")[0].strip() for d in self.koren.split(";") if d.strip()]
        self.assertEqual(lastnosti, ["filter"], "ozadje ali barvna shema na korenu prepišeta, kar je določila stran")
        self.assertNotIn("background-color", self.pravila)
        self.assertNotIn("color-scheme", self.pravila)

    def test_filter_svetlo_stran_potemni_in_ostane_berljiva(self):
        m = re.search(r"filter:\s*invert\((\d+)%\)\s*hue-rotate\(180deg\)\s*contrast\((\d+)%\)\s*!important", self.koren)
        self.assertIsNotNone(m, self.koren)
        obrat, kontrast = int(m.group(1)) / 100.0, int(m.group(2)) / 100.0
        belo, crno = po_filtru(255, obrat, kontrast), po_filtru(0, obrat, kontrast)
        self.assertLess(belo, 0x40, "belo ozadje strani je po filtru temno")
        self.assertGreater(crno - belo, 150, "črno besedilo je na njem berljivo")
        self.assertEqual((belo, crno), (0x22, 0xdd))       # izmerjeno z istim filtrom: #222222 in #dddddd

    def test_slike_se_obrnejo_nazaj(self):
        self.assertRegex(self.pravila, r"img, video, canvas[^{]*\{\s*filter: invert\(100%\) hue-rotate\(180deg\) !important;")

    def test_slog_se_da_vbrizgati_v_stran(self):
        # safeer_mint.inject_dark_mode_js vstavi slog v predlogo JavaScript med znaka `: ta znaka, zaporedje ${ in
        # poševnica nazaj bi predlogo podrli ali spremenili.
        for znak in ("`", "${", "\\"):
            self.assertNotIn(znak, self.css, repr(znak))


if __name__ == "__main__":
    unittest.main()
