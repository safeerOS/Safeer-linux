"""Paketi .deb se namestijo tudi na Linux Mint 23 / Ubuntu 26.04 in Debian 13 (21. 10. 2026: 1.0.130 se ni -
libicu74, libjxl0.7, libjpeg8 in libxml2 tam niso na voljo; izmerjeno v vsebnikih)."""
import os
import re
import unittest

KOREN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def beri(pot):
    with open(os.path.join(KOREN, pot), encoding="utf-8") as f:
        return f.read()


class PrenosniDeb(unittest.TestCase):
    def test_vgradi_vgradi_knjiznice_razlicnih_sistemov(self):
        s = beri("packaging/webkit-deb/vgradi.sh")
        m = re.search(r"^PRENOSNE='(.+)'$", s, re.M)
        self.assertIsNotNone(m, "vgradi.sh nima seznama PRENOSNE")
        vzorec = re.compile(m.group(1))
        for so in ("libicuuc.so.74", "libicui18n.so.74", "libicudata.so.74", "libjxl.so.0.7", "libhwy.so.1",
                   "libjpeg.so.8", "libxml2.so.2", "libxslt.so.1"):
            self.assertTrue(vzorec.match(so), so)
        for so in ("libc.so.6", "libgtk-4.so.1", "libglib-2.0.so.0", "libstdc++.so.6", "libsoup-3.0.so.0"):
            self.assertFalse(vzorec.match(so), so)        # sistemske knjiznice ostanejo odvisnosti
        self.assertIn("patchelf --set-rpath '$ORIGIN'", s)   # vgrajena najde vgrajeno (libjxl -> libhwy)
        self.assertIn("/usr/share/doc/$pkg/copyright", s)    # licence vgrajenih knjiznic v paketu
        # vgradi pred dpkg-shlibdeps, sicer bi Depends se vedno zahteval libicu74 ...
        self.assertLess(s.index("PRENOSNE="), s.index("&& dpkg-shlibdeps"))

    def test_ci_zavrne_depends_s_prenosno_knjiznico_in_preizkusi_mint23(self):
        s = beri(".github/workflows/linux-packages.yml")
        self.assertIn("Depends zahteva knjiznico, ki mora biti v paketu", s)
        self.assertRegex(s, r"mint: \[[^\]]*'23'")
        self.assertIn("patchelf", beri("packaging/webkit-deb/knjiznice.sh"))

    def test_posodobitev_preskocena_samo_ce_prejsnja_ni_namestljiva(self):
        s = beri("tools/mint_namestitev/v_vsebniku.sh")
        self.assertIn('grep -q "is not installable"', s)
        self.assertIn("--simulate", s)


if __name__ == "__main__":
    unittest.main()
