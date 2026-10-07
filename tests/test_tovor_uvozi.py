"""Tovor Safeer OS in Safeer Control vsebuje VSE module core, ki jih koda v tovoru uvozi - tudi lene uvoze.

Seznama modulov v packaging/install_os_payload.sh in install_control_payload.sh sta ročna. tests/test_packaging.py
tovor namesti in uvozi glavno datoteko, lenih uvozov (znotraj funkcij) pa ne sproži. Tako je od prve izdaje
vgrajenega brskalnika do Safeer OS 0.4.65 v tovoru manjkal core/webkit_filters.py: core/os_splet.py se uvozi šele,
ko uporabnik odpre Splet, uvoz je padel (ImportError) in namesto strani se je pokazalo »Tega ni bilo mogoče
odpreti.« Pri zagonu iz repozitorija je bilo vse v redu, zato napake ni pokazal noben preizkus.

Tu z ast poiščemo vse uvoze core.* v datotekah tovora, na katerikoli globini. Uvoz znotraj try/except ImportError
šteje kot neobvezen (primer: interni core/os_jbl.py, ki ga uradni paket namenoma nima).
"""
import ast
import os
import re
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PODPAKETI = ("sporocila",)


def seznam_modulov(skripta):
    with open(os.path.join(KOREN, "packaging", skripta), encoding="utf-8") as f:
        s = f.read()
    m = re.search(r"for modul in (.*?); do", s, re.S)
    assert m, skripta
    return set(m.group(1).replace("\\\n", " ").split())


def uvozi_core(pot, v_paketu_core):
    """[(modul core, vrstica, neobvezen)] - vsi uvozi core.* v datoteki, tudi znotraj funkcij."""
    with open(pot, encoding="utf-8") as f:
        drevo = ast.parse(f.read())
    najdeno = []

    def obisci(vozel, neobvezen):
        if isinstance(vozel, ast.Try):
            lovi = any(h.type is None or "ImportError" in ast.dump(h.type) or "Exception" in ast.dump(h.type)
                       for h in vozel.handlers)
            for o in vozel.body:
                obisci(o, neobvezen or lovi)
            for o in vozel.handlers + vozel.orelse + vozel.finalbody:
                obisci(o, neobvezen)
            return
        if isinstance(vozel, ast.ImportFrom):
            modul = vozel.module or ""
            if vozel.level == 0 and modul == "core":
                najdeno.extend((a.name, vozel.lineno, neobvezen) for a in vozel.names)
            elif vozel.level == 0 and modul.startswith("core."):
                najdeno.append((modul.split(".")[1], vozel.lineno, neobvezen))
            elif vozel.level == 1 and v_paketu_core:
                if modul:
                    najdeno.append((modul.split(".")[0], vozel.lineno, neobvezen))
                else:
                    najdeno.extend((a.name, vozel.lineno, neobvezen) for a in vozel.names)
        elif isinstance(vozel, ast.Import):
            najdeno.extend((a.name.split(".")[1], vozel.lineno, neobvezen) for a in vozel.names if a.name.startswith("core."))
        for o in ast.iter_child_nodes(vozel):
            obisci(o, neobvezen)

    obisci(drevo, False)
    return najdeno


def manjkajoci(skripta, korenske):
    """{modul: [kje je uvozen]} za obvezne uvoze modulov core, ki jih v tovoru ni."""
    moduli = seznam_modulov(skripta)
    datoteke = [(os.path.join(KOREN, k), False) for k in korenske]
    datoteke += [(os.path.join(KOREN, "core", m + ".py"), True) for m in sorted(moduli)]
    for p in PODPAKETI:
        mapa = os.path.join(KOREN, "core", p)
        datoteke += [(os.path.join(mapa, f), False) for f in sorted(os.listdir(mapa)) if f.endswith(".py")]
    manjka = {}
    for pot, v_core in datoteke:
        for modul, vrstica, neobvezen in uvozi_core(pot, v_core):
            if neobvezen or modul in moduli or modul in PODPAKETI:
                continue
            if not (os.path.exists(os.path.join(KOREN, "core", modul + ".py")) or os.path.isdir(os.path.join(KOREN, "core", modul))):
                continue      # ime iz core/__init__.py, ne modul
            manjka.setdefault(modul, []).append("%s:%d" % (os.path.relpath(pot, KOREN), vrstica))
    return manjka


class TovorUvozi(unittest.TestCase):
    def test_safeer_os(self):
        self.assertEqual(manjkajoci("install_os_payload.sh", ["safeer_os.py"]), {})

    def test_safeer_control(self):
        self.assertEqual(manjkajoci("install_control_payload.sh", ["safeer_control.py", "safeerctl.py"]), {})

    def test_vsak_modul_s_seznama_obstaja(self):
        for skripta in ("install_os_payload.sh", "install_control_payload.sh"):
            for modul in sorted(seznam_modulov(skripta)):
                self.assertTrue(os.path.exists(os.path.join(KOREN, "core", modul + ".py")), "%s: %s" % (skripta, modul))

    def test_preizkus_vidi_len_uvoz(self):
        # Varovalka preizkusa samega: len uvoz v funkciji mora najti, neobveznega (try/except ImportError) spustiti.
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write("def f():\n    from core.len_modul import X\n    from . import sosed\n"
                    "try:\n    from core import neobvezen\nexcept ImportError:\n    neobvezen = None\n"
                    "import core.neposreden\n")
            pot = f.name
        try:
            self.assertEqual(sorted((m, n) for m, _v, n in uvozi_core(pot, True)),
                             [("len_modul", False), ("neobvezen", True), ("neposreden", False), ("sosed", False)])
        finally:
            os.unlink(pot)


if __name__ == "__main__":
    unittest.main()
