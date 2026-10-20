"""core/sqlite_baza: lastne baze v WAL z rokom cakanja (revizija stabilnosti 20. 10. 2026)."""
import os
import stat
import tempfile
import threading
import unittest

from core import sqlite_baza


class TestSqliteBaza(unittest.TestCase):
    def test_wal_in_rok(self):
        pot = os.path.join(tempfile.mkdtemp(), "b.sqlite3")
        b = sqlite_baza.odpri(pot)
        self.assertEqual(b.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(b.execute("PRAGMA busy_timeout").fetchone()[0], 5000)
        self.assertEqual(b.execute("PRAGMA synchronous").fetchone()[0], 1)    # NORMAL
        b.close()

    def test_dve_povezavi_ne_vrzeta_zaklenjeno(self):
        """Sporocila: storitev in graf identitet pisejo v isto bazo - druga povezava pocaka, ne vrze napake; bralec v
        WAL med pisanjem bere zadnje potrjeno stanje."""
        pot = os.path.join(tempfile.mkdtemp(), "b.sqlite3")
        a = sqlite_baza.odpri(pot, check_same_thread=False)
        b = sqlite_baza.odpri(pot, check_same_thread=False)
        a.execute("CREATE TABLE t (x INTEGER)")
        a.commit()
        a.execute("BEGIN IMMEDIATE")
        a.execute("INSERT INTO t VALUES (1)")
        self.assertEqual(b.execute("SELECT count(*) FROM t").fetchone()[0], 0)   # WAL: branje ne caka pisca
        threading.Timer(0.5, a.commit).start()
        b.execute("INSERT INTO t VALUES (2)")
        b.commit()
        self.assertEqual(sorted(r[0] for r in b.execute("SELECT x FROM t")), [1, 2])

    def test_wal_datoteke_zasebne_kot_baza(self):
        mapa = tempfile.mkdtemp()
        pot = os.path.join(mapa, "b.sqlite3")
        os.close(os.open(pot, os.O_CREAT | os.O_WRONLY, 0o600))
        b = sqlite_baza.odpri(pot)
        b.execute("CREATE TABLE t (x)")
        b.commit()
        self.assertEqual(stat.S_IMODE(os.stat(pot + "-wal").st_mode), 0o600)
        b.close()


if __name__ == "__main__":
    unittest.main()
