"""Vsebniki preizkusov ne ostanejo za sabo (AGENTS.md »Vsak preizkus za sabo pospravi«; tedenski pregled 4. 11. 2026,
N4: tools/scit_lab je zagnal vsebnika brez --rm, preizkus.sh ju je pospravil samo ob normalnem koncu)."""
import os
import re
import subprocess
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class DockerPospravi(unittest.TestCase):
    def test_vsak_docker_run_z_rm(self):
        datoteke = subprocess.run(["git", "-c", "safe.directory=" + KOREN, "-C", KOREN, "ls-files", "*.sh"],
                                  capture_output=True, text=True, timeout=30, check=True).stdout.split()
        brez = []
        for ime in datoteke:
            with open(os.path.join(KOREN, ime), encoding="utf-8", errors="ignore") as f:
                for st, vrstica in enumerate(f, 1):
                    koda = vrstica.split("#", 1)[0]
                    if re.search(r"\bdocker run\b", koda) and "--rm" not in koda:
                        brez.append("%s:%d" % (ime, st))
        self.assertEqual(brez, [])

    def test_preizkus_scita_pospravi_ob_vsakem_koncu(self):
        with open(os.path.join(KOREN, "tools", "scit_lab", "preizkus.sh"), encoding="utf-8") as f:
            s = f.read()
        self.assertRegex(s, r"""trap '\[ "\$\{PUSTI:-0\}" = 1 \] \|\| \$L dol >/dev/null' EXIT""")
        self.assertLess(s.index("trap "), s.index("$L gor"))
        self.assertIn('cd "$(dirname "$0")" || exit 1', s)


if __name__ == "__main__":
    unittest.main()
