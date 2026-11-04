"""install_os_payload.sh: zacasna mapa tovora Control izgine tudi ob napaki (trap EXIT; tedenski pregled 4. 11. 2026, N6)."""
import os
import re
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TovorOsZacasna(unittest.TestCase):
    def test_trap_takoj_po_mktemp(self):
        with open(os.path.join(KOREN, "packaging", "install_os_payload.sh"), encoding="utf-8") as f:
            s = f.read()
        m = re.search(r'TOVOR_CONTROL="\$\(mktemp -d\)"\n(?:#[^\n]*\n)*trap \'rm -rf "\$TOVOR_CONTROL"\' EXIT\n', s)
        self.assertTrue(m, "trap EXIT mora slediti mktemp, preden se karkoli lahko zalomi")


if __name__ == "__main__":
    unittest.main()
