"""Besedila za GTK poglede se berejo iz istega assets/os/besedila.js kot na strani (core/os_besedila.py)."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from core import os_besedila


class Besedila(unittest.TestCase):
    def test_vsi_jeziki_imajo_iste_kljuce(self):
        b = os_besedila.preberi()
        self.assertEqual(set(b), set(os_besedila.JEZIKI))
        kljuci = set(b["sl"])
        self.assertGreater(len(kljuci), 500)
        for jezik in os_besedila.JEZIKI:
            self.assertEqual(set(b[jezik]), kljuci, jezik)

    def test_prevajalnik_kot_na_strani(self):
        t = os_besedila.Prevajalnik("sl")
        self.assertEqual(t("katStran", a=1, b=3), "Stran 1 od 3")
        self.assertEqual(os_besedila.Prevajalnik("en")("katPredvajaj"), "▶ Play")
        self.assertEqual(t("ni_takega_kljuca"), "ni_takega_kljuca")
        self.assertEqual(os_besedila.Prevajalnik("xx").jezik in os_besedila.JEZIKI, True)

    def test_ubeznice_js(self):
        self.assertEqual(os_besedila._niz_js(r"a\"b\ncé\x41\'"), 'a"b\ncéA\'')

    @unittest.skipUnless(shutil.which("node"), "ni node")
    def test_enako_kot_javascript(self):
        # Primerjava z izvedbo besedila.js v Node: Python mora prebrati natanko isto.
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write("const fs=require('fs');eval(fs.readFileSync(process.argv[2],'utf8')+';globalThis.B=BESEDILA_OS');"
                    "process.stdout.write(JSON.stringify(B));")
        try:
            izhod = subprocess.run(["node", f.name, os_besedila.POT], capture_output=True, text=True, timeout=30)
        finally:
            os.unlink(f.name)
        self.assertEqual(izhod.returncode, 0, izhod.stderr)
        self.assertEqual(json.loads(izhod.stdout), os_besedila.preberi())
