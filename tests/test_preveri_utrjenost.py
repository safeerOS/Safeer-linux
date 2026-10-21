"""Skupna preverba utrjenosti (tools/preveri_utrjenost.sh, naloga 40): CET (IBT, SHSTK) je napaka za nase knjiznice in
pomozna procesa; isti skript v poslih webkit-deb, flatpak in flatpak-brskalnik.

Lazno drevo predpone se prevede z gcc (majhne knjiznice in programi z utrjenimi zastavicami ali brez CET/BIND_NOW)."""
import os
import re
import shutil
import subprocess
import tempfile
import unittest

KOREN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SKRIPT = os.path.join(KOREN, "tools", "preveri_utrjenost.sh")
UTRJENO = ["-O2", "-fstack-protector-strong", "-U_FORTIFY_SOURCE", "-D_FORTIFY_SOURCE=3", "-fstack-clash-protection",
           "-fcf-protection=full", "-Wl,-z,relro,-z,now"]
# Lokalno polje in strcpy: -fstack-protector-strong da __stack_chk_fail, _FORTIFY_SOURCE pa __strcpy_chk.
KNJIZNICA = r"""
#include <string.h>
int safeer_kopiraj(const char *v, char *izhod, unsigned n) {
    char vmesnik[64];
    strcpy(vmesnik, v);
    strncpy(izhod, vmesnik, n);
    return (int)strlen(vmesnik);
}
"""
PROGRAM = "int main(void) { return 0; }\n"
ORODJA = ("gcc", "readelf", "nm", "file")


def beri(pot):
    with open(os.path.join(KOREN, pot), encoding="utf-8") as f:
        return f.read()


@unittest.skipUnless(all(shutil.which(o) for o in ORODJA), "ni gcc/binutils/file")
class LaznoDrevo(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="utrjenost-")
        self.addCleanup(shutil.rmtree, self.d)
        for vir, ime in ((KNJIZNICA, "k.c"), (PROGRAM, "p.c")):
            with open(os.path.join(self.d, ime), "w") as f:
                f.write(vir)
        self.koren = os.path.join(self.d, "predpona")
        os.makedirs(os.path.join(self.koren, "lib", "webkitgtk-6.0", "injected-bundle"))
        os.makedirs(os.path.join(self.koren, "libexec", "webkitgtk-6.0"))
        for ime in ("libwebkitgtk-6.0.so.4", "libjavascriptcoregtk-6.0.so.1", "libsoup-3.0.so.0"):
            self.knjiznica(os.path.join("lib", ime))
        os.symlink("libwebkitgtk-6.0.so.4", os.path.join(self.koren, "lib", "libwebkitgtk-6.0.so"))
        self.knjiznica(os.path.join("lib", "webkitgtk-6.0", "injected-bundle", "libwebkitgtkinjectedbundle.so"))
        for ime in ("WebKitWebProcess", "WebKitNetworkProcess"):
            self.program(os.path.join("libexec", "webkitgtk-6.0", ime))
        with open(os.path.join(self.koren, "lib", "beri.txt"), "w") as f:
            f.write("ni ELF\n")

    def _gcc(self, args):
        subprocess.run(["gcc"] + args, check=True, capture_output=True)

    def knjiznica(self, rel, zastavice=None):
        self._gcc((zastavice or UTRJENO) + ["-shared", "-fPIC", "-o", os.path.join(self.koren, rel),
                                            os.path.join(self.d, "k.c")])

    def program(self, rel, zastavice=None):
        self._gcc((zastavice or UTRJENO) + ["-fPIE", "-pie", "-o", os.path.join(self.koren, rel),
                                            os.path.join(self.d, "p.c")])

    def pozeni(self, *podmape):
        return subprocess.run(["bash", SKRIPT, self.koren, *podmape], capture_output=True, text=True)

    def _cet_na_voljo(self):
        izpis = subprocess.run(["readelf", "-nW", os.path.join(self.koren, "lib", "libsoup-3.0.so.0")],
                               capture_output=True, text=True).stdout
        if not re.search(r"x86 feature:.*IBT.*SHSTK", izpis):
            self.skipTest("prevajalnik ali crt tega sistema ne dasta CET")

    def test_utrjeno_preide(self):
        self._cet_na_voljo()
        r = self.pozeni()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("CET=IBT,SHSTK", r.stdout)
        self.assertIn("utrjeno: 5 glavnih in", r.stdout)

    def test_brez_cet_pade(self):
        """Pred naloga 40 je bil CET samo ::warning:: - libsoup brez IBT/SHSTK je sel skozi."""
        self._cet_na_voljo()
        self.knjiznica(os.path.join("lib", "libsoup-3.0.so.0"),
                       [z for z in UTRJENO if not z.startswith("-fcf-protection")] + ["-fcf-protection=none"])
        r = self.pozeni()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("libsoup-3.0.so.0 brez CET (IBT, SHSTK)", r.stdout)

    def test_pomozni_proces_brez_cet_pade(self):
        self._cet_na_voljo()
        self.program(os.path.join("libexec", "webkitgtk-6.0", "WebKitNetworkProcess"),
                     [z for z in UTRJENO if not z.startswith("-fcf-protection")] + ["-fcf-protection=none"])
        r = self.pozeni()
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("WebKitNetworkProcess brez CET", r.stdout)

    def test_brez_bind_now_in_izvrsljiv_sklad(self):
        self._cet_na_voljo()
        self.knjiznica(os.path.join("lib", "libjavascriptcoregtk-6.0.so.1"),
                       [z for z in UTRJENO if "-z,now" not in z] + ["-Wl,-z,relro,-z,lazy"])
        r = self.pozeni()
        self.assertEqual(r.returncode, 1)
        self.assertIn("libjavascriptcoregtk-6.0.so.1 brez BIND_NOW", r.stdout)
        self.knjiznica(os.path.join("lib", "libjavascriptcoregtk-6.0.so.1"))
        # Ostale datoteke: vticnik spletnega procesa z izvrsljivim skladom.
        self.knjiznica(os.path.join("lib", "webkitgtk-6.0", "injected-bundle", "libwebkitgtkinjectedbundle.so"),
                       UTRJENO + ["-Wl,-z,execstack"])
        r = self.pozeni("lib/webkitgtk-6.0", "libexec/webkitgtk-6.0")
        self.assertEqual(r.returncode, 1)
        self.assertIn("libwebkitgtkinjectedbundle.so nima GNU_STACK RW", r.stdout)

    def test_podmape_omejijo_ostale(self):
        """Flatpak: v /app so tudi programi drugih projektov (PySide6 ...) - preverijo se samo podane podmape."""
        self._cet_na_voljo()
        os.makedirs(os.path.join(self.koren, "lib", "python3", "pyside6"))
        self.knjiznica(os.path.join("lib", "python3", "pyside6", "libtuja.so"), ["-O2", "-shared", "-Wl,-z,lazy"])
        self.assertEqual(self.pozeni().returncode, 1)
        r = self.pozeni("lib/webkitgtk-6.0", "libexec/webkitgtk-6.0")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_manjkajoca_glavna_datoteka(self):
        os.unlink(os.path.join(self.koren, "libexec", "webkitgtk-6.0", "WebKitWebProcess"))
        r = self.pozeni()
        self.assertEqual(r.returncode, 1)
        self.assertIn("WebKitWebProcess manjka", r.stdout)


class Posli(unittest.TestCase):
    def test_vsi_trije_posli_klicejo_skript(self):
        s = beri(".github/workflows/linux-packages.yml")
        posli = re.split(r"\n  (?=[a-z][a-z0-9-]*:\n)", s)
        po_imenu = {p.split(":", 1)[0]: p for p in posli}
        self.assertIn('bash tools/preveri_utrjenost.sh "$X/usr/lib/safeer-webkit"\n', po_imenu["webkit-deb"])
        for posel in ("flatpak", "flatpak-brskalnik"):
            with self.subTest(posel=posel):
                self.assertIn('bash tools/preveri_utrjenost.sh "$WK/.." lib/webkitgtk-6.0 libexec/webkitgtk-6.0\n',
                              po_imenu[posel])
                p = po_imenu[posel]
                self.assertLess(p.index('WK="$(flatpak info --show-location'), p.index("tools/preveri_utrjenost.sh"))
        # Logika ni podvojena v yml (ena kopija pravil).
        self.assertNotIn("x86 feature", s)
        self.assertNotIn("::warning::$f brez CET", s)

    def test_cet_je_napaka(self):
        s = beri("tools/preveri_utrjenost.sh")
        self.assertIn('|| napaka "$f brez CET (IBT, SHSTK)"', s)
        self.assertNotIn("::warning::", s)


if __name__ == "__main__":
    unittest.main()
