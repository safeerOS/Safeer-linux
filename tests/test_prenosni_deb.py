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
                   "libjpeg.so.8"):
            self.assertTrue(vzorec.match(so), so)
        # libxml2 in libxslt sta od 1.0.132 staticno v libwebkitgtk (ne v PRENOSNE); sistemske ostanejo odvisnosti
        for so in ("libxml2.so.2", "libxslt.so.1", "libexslt.so.0", "libc.so.6", "libgtk-4.so.1",
                   "libglib-2.0.so.0", "libstdc++.so.6", "libsoup-3.0.so.0"):
            self.assertFalse(vzorec.match(so), so)
        self.assertIn("patchelf --set-rpath '$ORIGIN'", s)   # vgrajena najde vgrajeno (libjxl -> libhwy)
        self.assertIn("/usr/share/doc/$pkg/copyright", s)    # licence vgrajenih knjiznic v paketu
        self.assertIn("share/doc/vgrajene/$pkg/razlicica", s)  # razlicica vgrajene knjiznice za primerjavo ABI
        # vgradi pred dpkg-shlibdeps, sicer bi Depends se vedno zahteval libicu74 ...
        self.assertLess(s.index("PRENOSNE="), s.index("&& dpkg-shlibdeps"))

    def test_ci_zavrne_depends_s_prenosno_knjiznico_in_preizkusi_nove_sisteme(self):
        s = beri(".github/workflows/linux-packages.yml")
        self.assertIn("Depends zahteva knjiznico, ki mora biti v paketu", s)
        self.assertIn("patchelf", beri("packaging/webkit-deb/knjiznice.sh"))
        self.assertRegex(s, r"slika: \['debian:13', 'ubuntu:26.04'\]")     # Gemini 1.0.131: trditev opomb preveri CI
        self.assertIn("nima GNU_STACK RW", s)
        # 1.0.132 preverbe za staticni libxml2/libxslt v CI
        self.assertIn("paket nosi dinamicni libxml2/libxslt", s)
        self.assertIn("ima NEEDED libxml2/libxslt/libexslt", s)
        self.assertIn("libwebkitgtk izvaza xml/xslt simbole", s)
        self.assertIn("'packaging/libxml2/**'", s)

    def test_staticni_libxml2_in_xslt_zgradi_in_paket(self):
        # zgradi.sh: staticna gradnja v $DELO/xml, -Wl,--exclude-libs,ALL, CMake definicije in zapis v gradnja.txt
        z = beri("packaging/webkit-deb/zgradi.sh")
        self.assertIn('XML_PREFIX="$DELO/xml"', z)
        self.assertIn("-Wl,--exclude-libs,ALL", z)
        self.assertIn('-DLIBXML2_LIBRARY="$XML_PREFIX/lib/libxml2.a"', z)
        self.assertIn('-DLIBXSLT_LIBRARY="$XML_PREFIX/lib/libxslt.a"', z)
        self.assertIn('echo "libxml2:', z)
        self.assertIn('echo "libxslt:', z)

        # nadaljuj.sh: zapis v gradnja.txt
        n = beri("packaging/webkit-deb/nadaljuj.sh")
        self.assertIn('echo "libxml2:', n)
        self.assertIn('echo "libxslt:', n)

        # paket.sh: copyright z MIT licenco za staticni libxml2/libxslt
        p = beri("packaging/webkit-deb/paket.sh")
        self.assertIn("LIBXML_RAZLICICA=", p)
        self.assertIn("LIBXSLT_RAZLICICA=", p)
        self.assertIn("Statically includes libxml2", p)
        self.assertIn("License: MIT", p)

        # modula libxml2 in libxslt: uradni viri z download.gnome.org in preverjeni vsoti SHA-256
        x = beri("packaging/libxml2/libxml2-safeer.yml")
        self.assertIn("98087fd181d9070724f3fbc65c7377db03038eb92bd882374daff44940138821", x)
        xs = beri("packaging/libxml2/libxslt-safeer.yml")
        self.assertIn("9acfe68419c4d06a45c550321b3212762d92f41465062ca4ea19e632ee5d216e", xs)

    def test_posodobitev_preskocena_samo_ce_prejsnja_ni_namestljiva(self):
        s = beri("tools/mint_namestitev/v_vsebniku.sh")
        self.assertIn("(libicu74|libjxl0\\.7|libjpeg8|libxml2)[ (].*is not installable", s)
        self.assertIn("--simulate", s)


if __name__ == "__main__":
    unittest.main()
