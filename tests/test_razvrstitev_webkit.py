"""Razvrstitev preizkusov CI po WebKitu (tests/razvrstitev_webkit.py, lastnik 25. 10. 2026): staticna analiza, razdelitev
hitrih vrat in straza, ki vsak poskus nalaganja WebKita v hitrih vratih glasno podre (nic ne zdrsne tiho)."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import types
import unittest
from pathlib import Path

KOREN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOREN / "tests"))
import razvrstitev_webkit as rw  # noqa: E402

#: Lazen gi: require_version in gi.repository brez pravih typelibov (preizkus straze brez PyGObject in brez WebKita).
LAZNI_GI = {
    "gi/__init__.py": "zahtevano = []\ndef require_version(ns, v):\n    zahtevano.append(ns)\n"
                      "def require_versions(d):\n    for k, v in d.items():\n        require_version(k, v)\n",
    "gi/repository/__init__.py": "",
    "gi/repository/Gtk.py": "IME = 'Gtk'\n",
    "gi/repository/Soup.py": "IME = 'Soup'\n",
}


def _zapisi(koren: Path, datoteke: dict) -> None:
    for ime, vsebina in datoteke.items():
        pot = koren / ime
        pot.parent.mkdir(parents=True, exist_ok=True)
        pot.write_text(textwrap.dedent(vsebina), encoding="utf-8")


class StaticnaAnaliza(unittest.TestCase):
    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.koren = Path(self._d.name)
        _zapisi(self.koren, {
            "core/__init__.py": "",
            "core/splet.py": "import gi\ngi.require_version('WebKit', '6.0')\nfrom gi.repository import WebKit\n",
            "core/okno.py": "from . import splet\n",                                 # posredno ob uvozu
            "core/lenobno.py": "def f():\n    from core import splet\n    return splet\n",
            "core/dns.py": "try:\n    import gi\n    gi.require_versions({'Soup': '3.0'})\nexcept ValueError:\n    pass\n",
            "core/cisto.py": "import json\n",
            # Klic ob uvozu (kot core/safeer_link.py: »Gdk, Gtk, WebKit2 = _nalozi_gtk()«), tudi prek druge funkcije.
            "core/vrh_klic.py": "import gi\ndef _nalozi():\n    gi.require_version('WebKit', '6.0')\n"
                                "def _pripravi():\n    return _nalozi()\nWK = _pripravi()\n",
            "core/tuji_klic.py": "from core.lenobno import f\nSPLET = f()\n",          # uvozena funkcija ob uvozu
            "core/klic_v_funkciji.py": "from core import lenobno\ndef g():\n    return lenobno.f()\n",
            "tests/test_i.py": "import core.vrh_klic\n",
            "tests/test_j.py": "from core import tuji_klic\n",
            "tests/test_k.py": "from core import klic_v_funkciji\ndef test_k():\n    klic_v_funkciji.g()\n",
            "program.py": "import core.okno\n",
            "tests/test_a.py": "import core.okno\ndef test_x():\n    pass\n",
            "tests/test_b.py": "from core import lenobno\ndef test_y():\n    lenobno.f()\n",
            "tests/test_c.py": "def test_z():\n    from gi.repository import JavaScriptCore\n",
            "tests/test_d.py": "import subprocess, sys\ndef test_p():\n"
                               "    subprocess.run([sys.executable, 'program.py'])\n",
            "tests/test_e.py": "def test_branje():\n    open('program.py').read()\n",            # branje ni zagon
            "tests/test_f.py": "import core.cisto\ndef test_q():\n    pass\n",
            "tests/test_g.py": "def test_v_funkciji():\n    import core.dns\n",
            "tests/test_h.py": "import subprocess, sys\ndef test_koda():\n"
                               "    subprocess.run([sys.executable, '-c', 'import sys; import program'])\n",
            "tests/test_rocno.py": "def test_r():\n    pass\n",
            "tests/test_l.py": "from core.lenobno import f\nX = f()\n",                  # klic uvozene funkcije ob uvozu
            # Koda za -c v spremenljivki (test_packaging: namescen tovor uvozi safeer_os v podprocesu).
            "tests/test_m.py": "import subprocess, sys\ndef test_tovor():\n    d = '/tmp/x'\n"
                               "    koda = f\"import sys; sys.path.insert(0, {d!r}); import program\"\n"
                               "    subprocess.run([sys.executable, '-c', koda])\n",
            "tests/test_n.py": "import subprocess\ndef test_besedilo():\n    koda = 'import program'\n"
                               "    print(koda)\n    subprocess.run(['true'])\n",              # niz ni argument zagona
            # Pregled M11: v podmapi z imenom datoteke na vrhu - analiza po poti, ne po imenu.
            "tests/podmapa/test_f.py": "import core.okno\ndef test_q():\n    pass\n",
            "tests/podmapa/test_c.py": "def test_z():\n    pass\n",
            "tests/webkit_preizkusi.txt": "# komentar\ntests/test_rocno.py\n",
        })

    def tearDown(self):
        self._d.cleanup()

    def test_razlogi(self):
        r, stevila = rw.razvrsti(self.koren)
        self.assertEqual(r["tests/test_a.py"], "uvoz core.okno")
        self.assertIsNone(r["tests/test_b.py"])               # lenoben uvoz: analiza ga ne vidi, ujame ga straza
        self.assertEqual(r["tests/test_c.py"], "neposredno")
        self.assertEqual(r["tests/test_d.py"], "podproces program")
        self.assertIsNone(r["tests/test_e.py"])
        self.assertIsNone(r["tests/test_f.py"])
        self.assertEqual(r["tests/test_g.py"], "uvoz core.dns")  # require_versions s Soup, uvoz v funkciji preizkusa
        self.assertEqual(r["tests/test_h.py"], "podproces program")
        self.assertEqual(r["tests/test_rocno.py"], "rocno (tests/webkit_preizkusi.txt)")
        self.assertEqual(r["tests/test_i.py"], "uvoz core.vrh_klic")
        self.assertEqual(r["tests/test_j.py"], "uvoz core.tuji_klic")    # klic core.lenobno.f (lenoben uvoz splet) ob uvozu
        self.assertIsNone(r["tests/test_k.py"])                           # klic sele v preizkusu: straza
        self.assertEqual(r["tests/test_l.py"], "uvoz (klic ob uvozu)")
        self.assertEqual(r["tests/test_m.py"], "podproces program")
        self.assertIsNone(r["tests/test_n.py"])
        self.assertEqual(r["tests/podmapa/test_f.py"], "uvoz core.okno")
        self.assertIsNone(r["tests/podmapa/test_c.py"])
        self.assertEqual(stevila["tests/test_a.py"], 1)

    def test_razdelitev_pokrije_vse_enkrat(self):
        datoteke = ["tests/test_%d.py" % i for i in range(23)]
        ocene = {f: float(i % 7 + 1) for i, f in enumerate(datoteke)}
        r = rw.razdeli(datoteke, 4, {}, ocene)
        self.assertEqual(set(r), set(datoteke))
        self.assertEqual(set(r.values()), {1, 2, 3, 4})
        vsote = rw.ocena_delov(r, {}, ocene)
        self.assertLessEqual(max(vsote.values()) - min(vsote.values()), max(ocene.values()))
        self.assertEqual(r, rw.razdeli(list(reversed(datoteke)), 4, {}, ocene))   # deterministicno

    def test_pravi_repozitorij(self):
        """Na pravem repozitoriju: znane datoteke z WebKitom so v poslu preizkusi-webkit, deli hitrih vrat in posel
        z WebKitom skupaj pokrijejo vsako datoteko preizkusov natanko enkrat."""
        r, stevila = rw.razvrsti(KOREN)
        webkit = {f for f, x in r.items() if x}
        for f in ("tests/test_safeer_brskalnik.py", "tests/test_network_errors.py", "tests/test_splet_spanje_zivo.py",
                  "tests/test_dns_scit.py"):
            self.assertIn(f, webkit)
        self.assertNotIn("tests/test_razvrstitev_webkit.py", webkit)
        brez = [f for f in r if f not in webkit]
        deli = rw.razdeli(brez, 6, stevila, rw.trajanja(KOREN))
        self.assertEqual(set(deli) | webkit, set(r))
        self.assertFalse(set(deli) & webkit)
        for f in rw.rocni_seznam(KOREN):
            self.assertTrue((KOREN / f).is_file(), "%s iz %s ne obstaja" % (f, rw.ROCNI_SEZNAM))

    def test_preslikane_knjiznice(self):
        maps = ("7f00-7f01 r-xp 0 08:01 1 /usr/lib/safeer-webkit/lib/libwebkitgtk-6.0.so.4.15.4\n"
                "7f01-7f02 r-xp 0 08:01 2 /usr/lib/x86_64-linux-gnu/libsoup-3.0.so.0.4.4 (deleted)\n"
                "7f02-7f03 r-xp 0 08:01 3 /usr/lib/x86_64-linux-gnu/libgtk-4.so.1\n")
        p = rw.preslikane_knjiznice(maps)
        self.assertEqual(sorted(p), ["libsoup-3.0", "libwebkitgtk-6.0"])
        self.assertEqual(rw.tuje_knjiznice(p, "/usr/lib/safeer-webkit"), ["/usr/lib/x86_64-linux-gnu/libsoup-3.0.so.0.4.4"])


class Preskok(unittest.TestCase):
    """Preskok, ker WebKita ni, je v obeh nacinih padec (pregled M6: tudi importorskip, »requires«, »brez WebKita«)."""

    def razlog(self, besedilo):
        return rw._razlog_preskoka(types.SimpleNamespace(skipped=True, longrepr=("f.py", 1, besedilo)))

    def test_tih_zdrs(self):
        for besedilo in ("Skipped: could not import 'gi.repository.WebKit': Namespace WebKit not available",
                         "requires WebKitGTK 6.0", "WebKit unavailable", "brez WebKita", "WebKitGTK manjka",
                         "no WebKit", "potrebuje WebKitGTK 6.0", "WebKitGTK is not installed", "ni WebKitGTK 6.0: x",
                         "Soup 3.0 ni na voljo", "cannot import JavaScriptCore",
                         # Ponovni pregled N7: besedila PyGObject in podobna, ki jih vzorec prej ni ujel.
                         "Typelib file for namespace 'WebKit', version '6.0' not found", "WebKitGTK absent",
                         "WebKit not found", "typelib WebKit ni najden"):
            with self.subTest(besedilo=besedilo):
                self.assertEqual(self.razlog(besedilo), besedilo)

    def test_drug_razlog(self):
        for besedilo in ("WebKit brez WebRTC: ni podpore", "ni xdotool", "brez python3-yaml", "samo na Windows",
                         "WebKit test traja predolgo"):
            with self.subTest(besedilo=besedilo):
                self.assertIsNone(self.razlog(besedilo))
        self.assertIsNone(rw._razlog_preskoka(types.SimpleNamespace(skipped=False, longrepr=None)))


class Trajanja(unittest.TestCase):
    """Pregled M12: zdruzi sprejme samo datoteke preizkusov in koncna nenegativna trajanja."""

    def test_zdruzi(self):
        with tempfile.TemporaryDirectory() as d:
            dobro, slabo = Path(d) / "dobro.json", Path(d) / "slabo.json"
            dobro.write_text(json.dumps({"tests/test_a.py": 2.5, "tests/test_b.py": 1}))
            izhod = io.StringIO()
            with contextlib.redirect_stdout(izhod):
                self.assertEqual(rw._glavni(["zdruzi", str(dobro), str(dobro)]), 0)
            self.assertEqual(json.loads(izhod.getvalue())["datoteke"], {"tests/test_a.py": 5.0, "tests/test_b.py": 2.0})
            for vsebina in ({"tests/test_a.py": "nan"}, {"tests/test_a.py": -1}, {"tests/test_a.py": "inf"},
                            {"core/x.py": 1}, {"tests/../etc/x.py": 1}, {"tests/test_a.py": "x"}):
                with self.subTest(vsebina=vsebina):
                    slabo.write_text(json.dumps(vsebina))
                    with self.assertRaises(SystemExit) as e, contextlib.redirect_stdout(io.StringIO()):
                        rw._glavni(["zdruzi", str(slabo)])
                    self.assertIn("zdruzi:", str(e.exception.code))


class Straza(unittest.TestCase):
    """Straza v loceni mapi z laznim gi, v podprocesu (okolja tega procesa ne spreminjamo, AGENTS.md)."""

    def setUp(self):
        self._d = tempfile.TemporaryDirectory()
        self.mapa = Path(self._d.name)
        _zapisi(self.mapa / "gi_lazni", LAZNI_GI)

    def tearDown(self):
        self._d.cleanup()

    def _python(self, koda: str) -> subprocess.CompletedProcess:
        # -I izpusti uporabnikove pakete; pytest (vticnik ga uvozi) je lahko v ~/.local, zato njegovo mapo dodamo na konec.
        import pytest
        paketi = str(Path(pytest.__file__).resolve().parents[1])
        uvod = "import sys\nsys.path[:0] = [%r, %r]\nsys.path.append(%r)\n" % (
            str(self.mapa / "gi_lazni"), str(KOREN / "tests"), paketi)
        return subprocess.run([sys.executable, "-I", "-c", uvod + textwrap.dedent(koda)], capture_output=True,
                              text=True, timeout=60, env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")})

    def test_zabelezi_in_zavrne(self):
        r = self._python("""
            import razvrstitev_webkit as rw
            s = rw.Straza().namesti()
            import gi
            gi.require_version('Gtk', '4.0')
            from gi.repository import Gtk
            for ns in ('WebKit', 'JavaScriptCore'):
                try:
                    gi.require_version(ns, '6.0')
                except ValueError as e:
                    print('zavrnjen', ns)
            try:
                gi.require_versions({'Soup': '3.0'})
            except ValueError:
                print('zavrnjen Soup')
            try:
                from gi.repository import Soup
            except ImportError:
                print('uvoz zavrnjen')
            print(sorted({p for _, p, _ in s.vzemi()}), gi.zahtevano)
        """)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("zavrnjen WebKit\nzavrnjen JavaScriptCore\nzavrnjen Soup\nuvoz zavrnjen\n", r.stdout)
        # Gtk gre skozi do pravega gi; prostori WebKita ne pridejo do njega.
        self.assertIn("['JavaScriptCore', 'Soup', 'WebKit'] ['Gtk']", r.stdout)

    def test_gi_ze_uvozen(self):
        r = self._python("""
            import gi
            import razvrstitev_webkit as rw
            s = rw.Straza().namesti()
            try:
                gi.require_version('WebKit', '6.0')
            except ValueError:
                pass
            print(len(s.vzemi()))
        """)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "1")

    def test_vticnik_podre_tih_zdrs(self):
        """pytest z vticnikom v nacinu brez: datoteka z WebKitom ob uvozu izpade (gre v preizkusi-webkit), lenobni uvoz
        z nadomestno potjo in preskok »potrebuje WebKitGTK« preizkus PODRETA, cist preizkus uspe."""
        repo = self.mapa / "repo"
        _zapisi(repo, {
            "core/__init__.py": "",
            "core/lenobno.py": """
                def ima_webkit():
                    import gi
                    try:
                        gi.require_version('WebKit', '6.0')
                        return True
                    except ValueError:
                        return False      # nadomestna pot: brez straze bi preizkus tiho uspel
            """,
            "tests/test_cisto.py": "def test_ok():\n    assert 1\n",
            "tests/test_ob_uvozu.py": "import gi\ngi.require_version('WebKit', '6.0')\ndef test_w():\n    pass\n",
            "tests/test_lenobno.py": """
                import sys, os
                sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from core import lenobno
                def test_nadomestno():
                    assert lenobno.ima_webkit() is False
            """,
            "tests/test_preskok.py": """
                import unittest
                @unittest.skipUnless(False, "potrebuje WebKitGTK 6.0")
                class T(unittest.TestCase):
                    def test_s(self):
                        pass
            """,
        })
        okolje = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                  "PYTHONPATH": os.pathsep.join([str(KOREN / "tests"), str(self.mapa / "gi_lazni")])}
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "razvrstitev_webkit",
                            "--safeer-webkit=brez", "--safeer-koren", str(repo), "-rA", str(repo / "tests")],
                           cwd=str(repo), capture_output=True, text=True, timeout=120, env=okolje)
        izpis = r.stdout + r.stderr
        self.assertEqual(r.returncode, 1, izpis)
        self.assertRegex(izpis, r"PASSED[^\n]*test_cisto.py::test_ok")
        self.assertRegex(izpis, r"FAILED[^\n]*test_lenobno.py::test_nadomestno")
        self.assertRegex(izpis, r"(FAILED|ERROR)[^\n]*test_preskok.py::T::test_s")   # preskok v setup: ERROR
        self.assertNotIn("test_ob_uvozu", izpis.split("short test summary", 1)[-1])
        self.assertIn("tests/test_lenobno.py", izpis)                         # povzetek: kaj dopisati na seznam
        self.assertIn("1 datotek z WebKitom", izpis)

        # Izrecno podana datoteka z WebKitom v nacinu brez se ne uvozi in ne tece - kot pri mapi tests/ v CI (25. 10. 2026:
        # ciljni tek s potmi je pognal test_packaging brez WebKita in pokazal padce, ki jih hitra vrata nimajo).
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", "-p", "razvrstitev_webkit",
                            "--safeer-webkit=brez", "--safeer-koren", str(repo), str(repo / "tests" / "test_ob_uvozu.py"),
                            str(repo / "tests" / "test_cisto.py")],
                           cwd=str(repo), capture_output=True, text=True, timeout=120, env=okolje)
        izpis = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, izpis)
        self.assertRegex(izpis, r"PASSED[^\n]*test_cisto.py::test_ok")
        self.assertNotIn("test_ob_uvozu.py::", izpis)
        self.assertNotIn("Straza", izpis)
        self.assertIn("izpusceno v tem teku 1", izpis)

        # Padli najprej (lastnik 25. 10. 2026): seznam padlih tega teka; naslednji tek pozene samo njih in hitro pade.
        padli = repo / "padli.json"
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "razvrstitev_webkit",
                            "--safeer-webkit=brez", "--safeer-koren", str(repo), "--safeer-padli", str(padli),
                            str(repo / "tests")], cwd=str(repo), capture_output=True, text=True, timeout=120, env=okolje)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(json.loads(padli.read_text()), ["tests/test_lenobno.py::test_nadomestno",
                                                         "tests/test_preskok.py::T::test_s"])
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", "-p", "razvrstitev_webkit",
                            "--safeer-webkit=brez", "--safeer-koren", str(repo), "--safeer-padli", str(padli),
                            "--safeer-najprej-padli", str(repo / "tests")],
                           cwd=str(repo), capture_output=True, text=True, timeout=120, env=okolje)
        izpis = r.stdout + r.stderr
        self.assertEqual(r.returncode, 1, izpis)
        self.assertNotIn("test_cisto", izpis.split("short test summary", 1)[-1])   # samo prej padli
        self.assertIn("najprej padli prejsnjega teka (2)", izpis)
        # Ko prej padlih v tem delu ni (popravljeni, premaknjeni), korak uspe takoj in tece cel del.
        padli.write_text(json.dumps(["tests/test_drugje.py::test_x"]))
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "razvrstitev_webkit",
                            "--safeer-webkit=brez", "--safeer-koren", str(repo), "--safeer-padli", str(padli),
                            "--safeer-najprej-padli", str(repo / "tests")],
                           cwd=str(repo), capture_output=True, text=True, timeout=120, env=okolje)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(padli.read_text()), [])

        # Nacin samo izbere samo datoteko z WebKitom (preverba nasega WebKita se tu preskoci: --collect-only).
        r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "razvrstitev_webkit",
                            "--safeer-webkit=samo", "--safeer-koren", str(repo), "--collect-only", str(repo / "tests")],
                           cwd=str(repo), capture_output=True, text=True, timeout=120, env=okolje)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("test_ob_uvozu.py::test_w", r.stdout)
        self.assertNotIn("test_cisto", r.stdout)


if __name__ == "__main__":
    unittest.main()
