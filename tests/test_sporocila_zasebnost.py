import os
import tempfile
import unittest
from pathlib import Path

from core.sporocila.storitev import StoritevSporocil


class ZasebnostBaze(unittest.TestCase):
    def test_baza_samo_za_lastnika(self):
        stara = os.umask(0o022)
        try:
            pot = Path(tempfile.mkdtemp()) / "sporocila" / "sporocila.sqlite3"
            pot.parent.mkdir(mode=0o755)
            pot.touch(mode=0o644)
            StoritevSporocil(pot).zapri()
            self.assertEqual(os.stat(pot).st_mode & 0o777, 0o600)
            self.assertEqual(os.stat(pot.parent).st_mode & 0o777, 0o700)
        finally:
            os.umask(stara)


if __name__ == "__main__":
    unittest.main()
