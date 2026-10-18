"""CI in gradnja (18. 10. 2026): odvisnosti vticnika Qt xcb v najmanjsem vsebniku, pripet Clang 22 in preverjen kljuc
apt.llvm.org, Node.js in profili AppArmor v preizkusu na Linux Mintu."""
import os
import re
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover - CI ga nima vedno (python3-yaml), kot test_packaging
    yaml = None

KOREN = Path(__file__).resolve().parents[1]
DELOVNI_TOK = KOREN / ".github" / "workflows" / "linux-packages.yml"


def _posli():
    if yaml is None:
        raise unittest.SkipTest("python3-yaml ni namescen")
    return yaml.safe_load(DELOVNI_TOK.read_text(encoding="utf-8"))["jobs"]


class QtXcb(unittest.TestCase):
    def _zazeni(self, ldd_izpis: str, glx: bool = True, wayland: bool = True) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            qt = d / "vendor" / "PySide6" / "Qt" / "plugins"
            (qt / "platforms").mkdir(parents=True)
            (qt / "platforms" / "libqxcb.so").write_bytes(b"\x7fELF")
            if wayland:
                (qt / "platforms" / "libqwayland.so").write_bytes(b"\x7fELF")
            if glx:
                (qt / "xcbglintegrations").mkdir()
                (qt / "xcbglintegrations" / "libqxcb-glx-integration.so").write_bytes(b"\x7fELF")
            kos = d / "bin"
            kos.mkdir()
            ldd = kos / "ldd"
            ldd.write_text("#!/bin/sh\ncat <<'X'\n%s\nX\n" % ldd_izpis)
            ldd.chmod(ldd.stat().st_mode | stat.S_IXUSR)
            return subprocess.run(["bash", str(KOREN / "packaging" / "preveri_qxcb.sh"), str(d / "vendor")],
                                  capture_output=True, text=True, env={"PATH": "%s:/usr/bin:/bin" % kos}, timeout=30)

    def test_vse_knjiznice_najdene(self):
        r = self._zazeni("\tlibxcb-cursor.so.0 => /lib/x86_64-linux-gnu/libxcb-cursor.so.0 (0x1)")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("v redu: plugins/platforms/libqxcb.so", r.stdout)
        self.assertIn("v redu: plugins/platforms/libqwayland.so", r.stdout)

    def test_brez_vticnika_wayland_ustavi(self):
        """Ubuntu 24.04 GNOME (Wayland): lupina tece prek vticnika wayland - brez njega ali njegovih knjiznic napaka."""
        r = self._zazeni("\tlibc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x1)", wayland=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("libqwayland.so", r.stdout)

    def test_manjkajoca_knjiznica_ustavi(self):
        r = self._zazeni("\tlibxcb-cursor.so.0 => not found\n\tlibc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x1)")
        self.assertEqual(r.returncode, 1)
        self.assertIn("libxcb-cursor.so.0 => not found", r.stdout)

    def test_brez_integracij_gl_ustavi(self):
        r = self._zazeni("\tlibc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x1)", glx=False)
        self.assertEqual(r.returncode, 1)

    def test_ci_preveri_v_cistem_vsebniku_in_na_mintu(self):
        posli = _posli()
        qt = posli["qt-xcb"]
        self.assertEqual(qt["container"]["image"], "ubuntu:24.04")
        koraki = "\n".join(k.get("run", "") for k in qt["steps"])
        self.assertIn("apt-get install -y -q --no-install-recommends ./paketi/safeer-os_*_amd64.deb", koraki)
        self.assertIn("bash packaging/preveri_qxcb.sh /usr/lib/safeer-os/vendor", koraki)
        # Najmanjsi vsebnik: pred paketom se ne namesti nobena knjiznica.
        self.assertNotIn("libxcb", koraki)
        self.assertIn("qt-xcb", posli["release"]["needs"])
        mint = (KOREN / "tools" / "mint_namestitev" / "v_vsebniku.sh").read_text(encoding="utf-8")
        self.assertIn("bash /preveri_qxcb.sh /usr/lib/safeer-os/vendor", mint)
        self.assertIn("preveri_qxcb.sh:/preveri_qxcb.sh:ro", (KOREN / "tools" / "mint_namestitev" / "preizkus.sh").read_text())

    def test_paket_nasteje_knjiznice_vticnika(self):
        depends = re.search(r"^Depends: (.*)$", (KOREN / "build_os_deb.sh").read_text(encoding="utf-8"), re.M).group(1)
        for paket in ("libxcb-cursor0", "libxcb-icccm4", "libxcb-image0", "libxcb-keysyms1", "libxcb-randr0",
                      "libxcb-render-util0", "libxcb-shape0", "libxcb-util1", "libxcb-xkb1", "libxkbcommon-x11-0",
                      "libx11-xcb1", "libegl1", "libgl1"):
            self.assertRegex(depends, r"(^|, )%s(,|$| )" % re.escape(paket), paket)


class ClangInKljuc(unittest.TestCase):
    SKRIPTA = KOREN / "packaging" / "webkit-deb" / "odvisnosti.sh"

    def test_kljuc_preverjen_pred_zaupanjem(self):
        b = self.SKRIPTA.read_text(encoding="utf-8")
        self.assertIn('LLVM_KLJUC_ODTIS="6084F3CF814B57C1CF12EFD515CF4D18AF4F7421"', b)
        # Kljuc gre v /etc/apt/keyrings sele po preverbi prstnega odtisa (nikoli neposredno s curl).
        self.assertNotRegex(b, r"curl [^\n]*-o /etc/apt/keyrings")
        self.assertLess(b.index('if [ "$ODTISI" != "$LLVM_KLJUC_ODTIS" ]'),
                        b.index('install -m 644 "$ZACASNO/llvm.asc" /etc/apt/keyrings/apt.llvm.org.asc'))
        self.assertLess(b.index("/etc/apt/keyrings/apt.llvm.org.asc\necho"), b.index("apt-get update -q\nPONUDBA"))

    def test_clang_pripet(self):
        b = self.SKRIPTA.read_text(encoding="utf-8")
        razlicica = re.search(r'^LLVM_RAZLICICA="([\d.]+)"$', b, re.M).group(1)
        paket = re.search(r'^LLVM_PAKET="([^"]+)"$', b, re.M).group(1)
        self.assertTrue(paket.startswith("1:%s~" % razlicica), paket)
        for ime in ("clang-22", "lld-22", "llvm-22", "libclang-rt-22-dev"):
            self.assertIn('"%s=$LLVM_PAKET"' % ime, b)
        self.assertIn('[ "$(dpkg-query -W -f \'${Version}\' clang-22)" = "$LLVM_PAKET" ]', b)

    def test_preverba_odtisa(self):
        """Isti ukaz kot v skripti vrne samo odtise glavnih kljucev (ne podkljucev): en kljuc = ena vrstica."""
        if not shutil_which("gpg") or not shutil_which("gpgconf"):
            self.skipTest("ni gpg")
        b = self.SKRIPTA.read_text(encoding="utf-8")
        ukaz = re.search(r'ODTISI="\$\((gpg .*?)\)"\n', b, re.S).group(1).replace("\\\n", " ")
        with tempfile.TemporaryDirectory() as d, tempfile.TemporaryDirectory() as dom:
            def gpg(*a):
                return subprocess.run(["gpg", "--batch", "--homedir", dom, "--passphrase", "", "--pinentry-mode",
                                       "loopback", *a], capture_output=True, text=True, timeout=60, check=True).stdout
            try:
                odtisi = []
                for ime in ("Preizkus A <a@example.invalid>", "Preizkus B <b@example.invalid>"):
                    gpg("--quick-gen-key", ime, "ed25519", "sign", "1d")
                    fpr = re.findall(r"^fpr:+([0-9A-F]{40}):", gpg("--with-colons", "--list-keys", ime), re.M)[0]
                    gpg("--quick-add-key", fpr, "cv25519", "encr", "1d")       # podkljuc z lastnim odtisom
                    odtisi.append(fpr)
                Path(d, "llvm.asc").write_text(gpg("--armor", "--export", odtisi[0]))
                okolje = dict(os.environ, ZACASNO=d)
                izpis = subprocess.run(["bash", "-c", ukaz], capture_output=True, text=True, env=okolje, timeout=60)
                self.assertEqual(izpis.stdout.split(), [odtisi[0]])
                Path(d, "llvm.asc").write_text(gpg("--armor", "--export", *odtisi))
                izpis = subprocess.run(["bash", "-c", ukaz], capture_output=True, text=True, env=okolje, timeout=60)
                self.assertEqual(izpis.stdout.split(), odtisi)
            finally:
                for mapa in (d, dom):
                    subprocess.run(["gpgconf", "--homedir", mapa, "--kill", "all"], capture_output=True, timeout=30)

    def test_kljuc_predpomnilnika_vsebuje_skripto(self):
        """Sprememba prevajalnika mora spremeniti kljuc predpomnilnika WebKita (nova gradnja, ne star arhiv)."""
        besedilo = DELOVNI_TOK.read_text(encoding="utf-8")
        for posel in ("webkit-deb-profil-", "webkit-deb-pgo-"):
            vrstica = next(v for v in besedilo.splitlines() if "key: " + posel in v)
            self.assertIn("packaging/webkit-deb/odvisnosti.sh", vrstica)


def shutil_which(ime):
    import shutil
    return shutil.which(ime)


if __name__ == "__main__":
    unittest.main()
