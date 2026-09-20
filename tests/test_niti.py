"""Delovne niti ne smejo klicati GTK, Gdk, WebKit ali Wnck - to je isti razred sesutja kot 20. 9. 2026.

Knjiznice C prek PyGObject so vezane na glavno nit z glavno zanko. Klic iz druge niti ne pade
vedno, pade pa takrat, ko se objekt pod njim spremeni - zato ga testi brez te straze spregledajo.
Pravilo je preprosto: nit sme racunati in brati, rezultat pa odda z `GLib.idle_add` (ali
`timeout_add`), ki ga izvede glavna nit.

Test poisce vsak `threading.Thread(target=...)` v namiznih programih, razresi telo tarce (imenovana
funkcija ali lambda) in zahteva, da v njem ni neposrednih klicev v te knjiznice. Koda v ugnezdeni
funkciji, ki gre v `GLib.idle_add`/`timeout_add`, je v redu - to je prav ta pravilna pot.
"""
import ast
import os
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOTEKE = ("safeer_os.py", "safeer_control.py", "safeer_mint.py")
#: Knjiznice, ki so vezane na glavno nit (PyGObject / GTK 3).
GLAVNA_NIT = ("Gtk", "Gdk", "GdkPixbuf", "WebKit2", "Wnck")
#: Klici, s katerimi nit pravilno preda delo glavni niti.
PREDAJA = ("idle_add", "timeout_add", "timeout_add_seconds")


def _je_predaja(vozlisce) -> bool:
    return (isinstance(vozlisce, ast.Call)
            and isinstance(vozlisce.func, ast.Attribute)
            and vozlisce.func.attr in PREDAJA)


def _predane_funkcije(telo) -> set:
    """Imena funkcij, ki so nekje v tem telesu predane GLib.idle_add/timeout_add."""
    imena = set()
    for v in ast.walk(telo):
        if _je_predaja(v):
            for arg in v.args:
                if isinstance(arg, ast.Name):
                    imena.add(arg.id)
    return imena


def _prepovedani_klici(telo) -> list:
    """Vrstice v telesu, ki neposredno kličejo knjižnico glavne niti (brez predaje)."""
    predane = _predane_funkcije(telo)
    napake = []

    def poglej(vozlisce, v_predaji: bool):
        for otrok in ast.iter_child_nodes(vozlisce):
            if isinstance(otrok, (ast.FunctionDef, ast.AsyncFunctionDef)):
                poglej(otrok, v_predaji or otrok.name in predane)
                continue
            if isinstance(otrok, ast.Lambda):
                poglej(otrok, v_predaji)
                continue
            if not v_predaji and isinstance(otrok, ast.Attribute):
                koren = otrok
                while isinstance(koren, ast.Attribute):
                    koren = koren.value
                if isinstance(koren, ast.Name) and koren.id in GLAVNA_NIT:
                    napake.append((otrok.lineno, ast.unparse(otrok)))
            poglej(otrok, v_predaji)

    poglej(telo, False)
    return napake


def _tarce(drevo):
    """(vrstica, ime_ali_None, vozlisce_tarce) za vsak threading.Thread(target=...)."""
    najdene = []
    for v in ast.walk(drevo):
        if not (isinstance(v, ast.Call) and ast.unparse(v.func).endswith("Thread")):
            continue
        for kw in v.keywords:
            if kw.arg != "target":
                continue
            if isinstance(kw.value, ast.Lambda):
                najdene.append((v.lineno, None, kw.value))
            elif isinstance(kw.value, (ast.Name, ast.Attribute)):
                najdene.append((v.lineno, ast.unparse(kw.value).split(".")[-1], None))
    return najdene


class Niti(unittest.TestCase):
    def test_nit_ne_klice_knjiznic_glavne_niti(self):
        tezave, pregledanih = [], 0
        for ime in DATOTEKE:
            pot = os.path.join(KOREN, ime)
            if not os.path.exists(pot):
                continue
            with open(pot, encoding="utf-8") as f:
                drevo = ast.parse(f.read())
            funkcije = {}
            for v in ast.walk(drevo):
                if isinstance(v, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    funkcije.setdefault(v.name, []).append(v)
            for vrstica, ime_tarce, lambda_vozlisce in _tarce(drevo):
                pregledanih += 1
                telesa = [lambda_vozlisce] if lambda_vozlisce is not None else funkcije.get(ime_tarce, [])
                for telo in telesa:
                    for napacna_vrstica, izraz in _prepovedani_klici(telo):
                        tezave.append("%s:%d (nit z vrstice %d) -> %s" % (ime, napacna_vrstica, vrstica, izraz))
        self.assertGreater(pregledanih, 0, "nobene niti nisem nasel - test ne varuje nicesar")
        self.assertEqual(tezave, [], "nit mora rezultat oddati prek GLib.idle_add, ne klicati knjiznice sama:\n"
                                     + "\n".join(tezave))

    def test_straza_res_lovi_napako(self):
        """Ce bi kdo iz niti klical WebKit neposredno, mora test pasti - sicer ne varuje nicesar."""
        slabo = ast.parse("def delo():\n    pogled.run_javascript('x')\n    Gtk.main_quit()\n")
        telo = slabo.body[0]
        self.assertTrue(_prepovedani_klici(telo))
        dobro = ast.parse("def delo():\n    rezultat = izracunaj()\n"
                          "    def naredi():\n        Gtk.main_quit()\n    GLib.idle_add(naredi)\n")
        self.assertEqual(_prepovedani_klici(dobro.body[0]), [])


if __name__ == "__main__":
    unittest.main()
