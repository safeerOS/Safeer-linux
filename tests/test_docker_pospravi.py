"""Vsebniki preizkusov ne ostanejo za sabo (AGENTS.md »Vsak preizkus za sabo pospravi«; tedenski pregled 4. 11. 2026,
N4: tools/scit_lab je zagnal vsebnika brez --rm, preizkus.sh ju je pospravil samo ob normalnem koncu)."""
import os
import re
import subprocess
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def docker_run_brez_rm(besedilo: str) -> list:
    """Stevilke vrstic, kjer se zacne ukaz »docker run« brez --rm. Nadaljevanja z »\\« so del ukaza; komentar ne steje."""
    izid, ukaz, zacetek = [], "", 0
    for st, vrstica in enumerate(besedilo.splitlines(), 1):
        koda = vrstica.split("#", 1)[0]
        if not ukaz:
            zacetek = st
        if koda.rstrip().endswith("\\"):
            ukaz += koda.rstrip()[:-1] + " "
            continue
        ukaz += koda
        if re.search(r"\bdocker\s+run\b", ukaz) and not re.search(r"(^|\s)--rm(\s|$)", ukaz):
            izid.append(zacetek)
        ukaz = ""
    return izid


class DockerPospravi(unittest.TestCase):
    def test_vsak_docker_run_z_rm(self):
        datoteke = subprocess.run(["git", "-c", "safe.directory=" + KOREN, "-C", KOREN, "ls-files", "*.sh"],
                                  capture_output=True, text=True, timeout=30, check=True).stdout.split()
        brez = []
        for ime in datoteke:
            with open(os.path.join(KOREN, ime), encoding="utf-8", errors="ignore") as f:
                brez += ["%s:%d" % (ime, st) for st in docker_run_brez_rm(f.read())]
        self.assertEqual(brez, [])

    def test_ukaz_cez_vec_vrstic(self):
        """Celoten ukaz (nadaljevanje z »\\«), ne vrstica: --rm v naslednji vrstici velja, »docker \\ run« se ujame
        (CodeRabbit, 4. 11. 2026)."""
        self.assertEqual(docker_run_brez_rm("docker run --name x \\\n  --rm slika\n"), [])
        self.assertEqual(docker_run_brez_rm("echo\ndocker \\\n  run --name x slika\n"), [2])
        self.assertEqual(docker_run_brez_rm("docker run -d slika  # --rm v komentarju ne steje\n"), [1])

    def test_lab_pocaka_na_odstranitev_pred_novim_vsebnikom(self):
        """lab.sh gor/dol: z --rm je odstranitev lahko se v teku - nov »docker run --name« sele, ko ju ni vec."""
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            dnevnik, stanje = os.path.join(d, "dnevnik"), os.path.join(d, "se")
            with open(stanje, "w") as f:
                f.write("3")
            docker = os.path.join(d, "docker")
            with open(docker, "w") as f:
                f.write('#!/bin/bash\necho "$1" >> %s\nif [ "$1" = inspect ] && [ "$2" != scit95 ]; then\n'
                        '  n=$(cat %s); [ "$n" -gt 0 ] || exit 1; echo $((n-1)) > %s; exit 0\nfi\n'
                        '[ "$1" = network ] && [ "$2" = inspect ] && exit 0\nexit 0\n' % (dnevnik, stanje, stanje))
            os.chmod(docker, 0o755)
            okolje = dict(os.environ, PATH=d + os.pathsep + os.environ.get("PATH", ""))
            subprocess.run(["bash", os.path.join(KOREN, "tools", "scit_lab", "lab.sh"), "dol"], env=okolje,
                           capture_output=True, text=True, timeout=60, check=True)
            with open(dnevnik) as f:
                ukazi = f.read().split()
        self.assertEqual(ukazi[0], "rm")
        self.assertGreaterEqual(ukazi.count("inspect"), 4, ukazi)
        self.assertEqual(ukazi[-1], "network", "network rm sele, ko vsebnikov ni vec")

    def test_preizkus_scita_pospravi_ob_vsakem_koncu(self):
        with open(os.path.join(KOREN, "tools", "scit_lab", "preizkus.sh"), encoding="utf-8") as f:
            s = f.read()
        self.assertRegex(s, r"""trap '\[ "\$\{PUSTI:-0\}" = 1 \] \|\| \$L dol >/dev/null' EXIT""")
        self.assertLess(s.index("trap "), s.index("$L gor"))
        self.assertIn('cd "$(dirname "$0")" || exit 1', s)


if __name__ == "__main__":
    unittest.main()
