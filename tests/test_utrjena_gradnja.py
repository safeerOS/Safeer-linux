"""Utrjena gradnja nasega WebKita in libsoup (lastnik 21. 10. 2026: »ce imamo te ranljivosti, nismo zares Safeer«).
Izmerjeno 21. 10. na testnem PC: nas libwebkitgtk 2.54.1 brez BIND_NOW, 2 funkciji _chk (Ubuntu 10), brez CET; libsoup
brez __stack_chk_fail - cflags-override v modulu je odstranil zascite SDK, zgradi.sh je libsoup gradil samo z -O2."""
import json
import os
import subprocess
import sys
import unittest

KOREN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ZASTAVICE = ("-fstack-protector-strong", "-D_FORTIFY_SOURCE=3", "-fstack-clash-protection", "-fcf-protection=full")


def beri(pot):
    with open(os.path.join(KOREN, pot), encoding="utf-8") as f:
        return f.read()


class UtrjenaGradnja(unittest.TestCase):
    def test_modul_webkita_ima_zascite(self):
        r = subprocess.run([sys.executable, os.path.join(KOREN, "packaging/webkit-deb/modul.py"),
                            os.path.join(KOREN, "packaging/webkit/webkitgtk6-safeer.yml")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        m = json.loads(r.stdout)
        for z in ZASTAVICE:
            self.assertIn(z, m["cflags"])
            self.assertIn(z, m["cxxflags"])
        self.assertIn("-z,now", m["ldflags"])
        self.assertIn("relro", m["ldflags"])

    def test_libsoup_in_bolt_dobita_zascite(self):
        s = beri("packaging/webkit-deb/zgradi.sh")
        self.assertNotIn('CFLAGS="-O2" meson', s)
        self.assertIn('CFLAGS="$(polje cflags <<< "$WK_JSON")" meson setup', s)
        self.assertIn('export LDFLAGS="$(polje ldflags <<< "$WK_JSON") -Wl,--exclude-libs,ALL"', s)
        self.assertIn('-DCMAKE_SHARED_LINKER_FLAGS=$LDFLAGS -Wl,--emit-relocs', s)

    def test_ci_preveri_vsako_knjiznico(self):
        s = beri(".github/workflows/linux-packages.yml")
        for niz in ("brez BIND_NOW", "brez GNU_RELRO", "brez zascite sklada", "brez _FORTIFY_SOURCE", "ni PIE/DYN",
                    "libsoup-3.0.so.0", "libexec/webkitgtk-6.0/WebKitWebProcess", "libexec/webkitgtk-6.0/WebKitNetworkProcess"):
            self.assertIn(niz, s)

    def test_vse_elf_datoteke_in_dav1d(self):
        """Pregled 1.0.132: CI je preveril samo 5 datotek; dav1ddec (Rust) brez BIND_NOW."""
        s = beri(".github/workflows/linux-packages.yml")
        self.assertIn('done < <(find "$W" -type f -print0)', s)
        self.assertIn('RUSTFLAGS="-C link-arg=-Wl,-z,relro,-z,now"', beri("packaging/webkit-deb/dav1d.sh"))

    def test_agents_pravilo(self):
        self.assertIn("## Utrjena gradnja", beri("AGENTS.md"))


if __name__ == "__main__":
    unittest.main()
