"""Tovor Safeer OS in Safeer Control vsebuje VSE module core, ki jih koda v tovoru uvozi - tudi lene uvoze.

Seznama modulov v packaging/install_os_payload.sh in install_control_payload.sh sta ročna. tests/test_packaging.py
tovor namesti in uvozi glavno datoteko, lenih uvozov (znotraj funkcij) pa ne sproži. Tako je od prve izdaje
vgrajenega brskalnika do Safeer OS 0.4.65 v tovoru manjkal core/webkit_filters.py: core/os_splet.py se uvozi šele,
ko uporabnik odpre Splet, uvoz je padel (ImportError) in namesto strani se je pokazalo »Tega ni bilo mogoče
odpreti.« Pri zagonu iz repozitorija je bilo vse v redu, zato napake ni pokazal noben preizkus.

Tu z ast poiščemo uvoze core.* v datotekah tovora, na katerikoli globini:
  - `import core.x`, `from core import x`, `from core.x import y`, `from . import x`, `from .x import y` (v podpaketu
    tudi `from .. import x`);
  - `__import__("core.x", ...)` in `importlib.import_module("core.x")` z nizom kot prvim argumentom.
Neobvezen je samo uvoz znotraj `try`, ki lovi PRAV napako uvoza (ImportError ali ModuleNotFoundError) - primer: interni
core/os_jbl.py, ki ga uradni paket namenoma nima. `try/except Exception` uvoza ne naredi neobveznega: manjkajoč modul bi
tam pomenil tiho okrnjeno delovanje (brskalnik brez seznama groženj), ne pa pričakovane odsotnosti.

Česa preizkus NE vidi: uvoza z izračunanim imenom (`__import__(ime)`) in modulov zunaj core. Podatkovne datoteke, ki jih
moduli tovora berejo, preverja razred Podatki za znane primere (katalog bank, skripta BankGuarda, začetna stran Spleta).
"""
import ast
import os
import re
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PODPAKETI = ("sporocila",)
UVOZNE_NAPAKE = ("ImportError", "ModuleNotFoundError")


def beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


def seznam_modulov(skripta):
    s = beri("packaging", skripta)
    m = re.search(r"for modul in (.*?); do", s, re.S)
    assert m, skripta
    return set(m.group(1).replace("\\\n", " ").split())


def _lovi_napako_uvoza(vozel) -> bool:
    for lovilec in vozel.handlers:
        if lovilec.type is None:
            continue
        imena = [n.id for n in ast.walk(lovilec.type) if isinstance(n, ast.Name)]
        imena += [n.attr for n in ast.walk(lovilec.type) if isinstance(n, ast.Attribute)]
        if any(ime in UVOZNE_NAPAKE for ime in imena):
            return True
    return False


def _niz(vozel):
    return vozel.value if isinstance(vozel, ast.Constant) and isinstance(vozel.value, str) else None


def uvozi_core(pot, raven_core):
    """[(modul core, vrstica, neobvezen)] - vsi uvozi core.* v datoteki, tudi znotraj funkcij.

    raven_core: koliko pik relativnega uvoza pomeni paket core (1 za core/x.py, 2 za core/podpaket/x.py, 0 = datoteka
    ni v paketu core)."""
    with open(pot, encoding="utf-8") as f:
        drevo = ast.parse(f.read())
    najdeno = []

    def obisci(vozel, neobvezen):
        if isinstance(vozel, ast.Try):
            lovi = _lovi_napako_uvoza(vozel)
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
            elif raven_core and vozel.level == raven_core:
                if modul:
                    najdeno.append((modul.split(".")[0], vozel.lineno, neobvezen))
                else:
                    najdeno.extend((a.name, vozel.lineno, neobvezen) for a in vozel.names)
        elif isinstance(vozel, ast.Import):
            najdeno.extend((a.name.split(".")[1], vozel.lineno, neobvezen) for a in vozel.names if a.name.startswith("core."))
        elif isinstance(vozel, ast.Call):
            klicano = vozel.func.id if isinstance(vozel.func, ast.Name) else getattr(vozel.func, "attr", "")
            cilj = _niz(vozel.args[0]) if vozel.args else None
            if klicano in ("__import__", "import_module") and cilj:
                if cilj.startswith("core."):
                    najdeno.append((cilj.split(".")[1], vozel.lineno, neobvezen))
                elif cilj == "core":
                    for k in vozel.keywords:
                        if k.arg == "fromlist" and isinstance(k.value, (ast.List, ast.Tuple)):
                            najdeno.extend((_niz(e), vozel.lineno, neobvezen) for e in k.value.elts if _niz(e))
        for o in ast.iter_child_nodes(vozel):
            obisci(o, neobvezen)

    obisci(drevo, False)
    return najdeno


def manjkajoci(skripta, korenske):
    """{modul: [kje je uvozen]} za obvezne uvoze modulov core, ki jih v tovoru ni."""
    moduli = seznam_modulov(skripta)
    datoteke = [(os.path.join(KOREN, k), 0) for k in korenske]
    datoteke += [(os.path.join(KOREN, "core", m + ".py"), 1) for m in sorted(moduli)]
    for p in PODPAKETI:
        mapa = os.path.join(KOREN, "core", p)
        datoteke += [(os.path.join(mapa, f), 2) for f in sorted(os.listdir(mapa)) if f.endswith(".py")]
    manjka = {}
    for pot, raven in datoteke:
        for modul, vrstica, neobvezen in uvozi_core(pot, raven):
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

    def _uvozi(self, koda, raven):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(koda)
            pot = f.name
        try:
            return sorted((m, n) for m, _v, n in uvozi_core(pot, raven))
        finally:
            os.unlink(pot)

    def test_preizkus_vidi_len_uvoz(self):
        # Varovalka preizkusa samega: len uvoz v funkciji mora najti, neobveznega (try/except ImportError) spustiti.
        self.assertEqual(self._uvozi(
            "def f():\n    from core.len_modul import X\n    from . import sosed\n"
            "try:\n    from core import neobvezen\nexcept ImportError:\n    neobvezen = None\n"
            "import core.neposreden\n", 1),
            [("len_modul", False), ("neobvezen", True), ("neposreden", False), ("sosed", False)])

    def test_neobvezen_je_samo_uvoz_ki_lovi_napako_uvoza(self):
        # `except Exception` (ali goli except) napako samo pogoltne: modul je obvezen, sicer program tiho dela okrnjeno.
        self.assertEqual(self._uvozi(
            "try:\n    from core import pogoltnjen\nexcept Exception:\n    pass\n"
            "try:\n    from core import gol\nexcept:\n    pass\n"
            "try:\n    from core import dvojni\nexcept (OSError, ModuleNotFoundError):\n    pass\n"
            "try:\n    from core import z_imenom\nexcept builtins.ImportError as e:\n    pass\n"
            "try:\n    pass\nexcept ImportError:\n    from core import v_lovilcu\n", 1),
            [("dvojni", True), ("gol", False), ("pogoltnjen", False), ("v_lovilcu", False), ("z_imenom", True)])

    def test_uvoz_s_klicem(self):
        self.assertEqual(self._uvozi(
            "a = __import__('core.s_klicem', fromlist=['x']).x()\n"
            "import importlib\nb = importlib.import_module('core.z_importlib')\n"
            "c = __import__('core', fromlist=['iz_seznama', 'se_eden'])\n"
            "d = __import__('time').monotonic()\n"
            "e = __import__(ime)\n", 0),
            [("iz_seznama", False), ("s_klicem", False), ("se_eden", False), ("z_importlib", False)])

    def test_relativni_uvoz_iz_podpaketa(self):
        # V core/podpaket/x.py je `from . import a` sosed v podpaketu, `from .. import b` pa modul core.
        koda = "from . import sosed_v_podpaketu\nfrom .. import modul_core\nfrom ..drug_modul import X\n"
        self.assertEqual(self._uvozi(koda, 2), [("drug_modul", False), ("modul_core", False)])
        self.assertEqual(self._uvozi(koda, 1), [("sosed_v_podpaketu", False)])
        self.assertEqual(self._uvozi(koda, 0), [])


class Podatki(unittest.TestCase):
    """Datoteke, ki jih moduli tovora Safeer OS berejo, a niso moduli (uvoz jih ne razkrije)."""

    def setUp(self):
        self.skripta = beri("packaging", "install_os_payload.sh")

    def test_podatki_bank_guarda(self):
        # core/bank_guard.py bere svoje podatke z _find("ime"); vsaka taka datoteka mora biti v zanki »for dat in ...«.
        imena = set(re.findall(r'_find\("([^"]+)"\)', beri("core", "bank_guard.py")))
        self.assertTrue(imena, "core/bank_guard.py ne bere več z _find - preizkus je treba prilagoditi")
        zanka = re.search(r"for dat in (.*?); do", self.skripta)
        self.assertIsNotNone(zanka)
        for ime in sorted(imena):
            self.assertIn(ime, zanka.group(1).split(), ime)
            self.assertTrue(os.path.exists(os.path.join(KOREN, "core", ime)), ime)

    def test_zacetna_stran_spleta_z_vsem_kar_nalozi(self):
        # Začetna stran vgrajenega brskalnika (ui/splet.html) in datoteke, na katere se sklicuje, grejo v tovor skupaj.
        sklici = set(re.findall(r'(?:href|src)="([^":?#]+)"', beri("ui", "splet.html")))
        sklici |= set(re.findall(r'url\("?([^")]+)"?\)', beri("ui", "splet.css")))
        sklici = {s for s in sklici if not s.startswith(("data:", "http"))}
        self.assertTrue({"splet.css", "splet.js"} <= sklici, sklici)
        vrstica = [v for v in self.skripta.splitlines() if '"$ROOT"/ui/splet.html' in v]
        self.assertEqual(len(vrstica), 1)
        for ime in sorted(sklici | {"splet.html"}):
            self.assertIn('"$ROOT"/ui/' + ime, vrstica[0], ime)
            self.assertTrue(os.path.exists(os.path.join(KOREN, "ui", ime)), ime)


if __name__ == "__main__":
    unittest.main()
