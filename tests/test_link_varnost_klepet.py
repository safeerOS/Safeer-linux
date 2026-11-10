"""Varnost Linka, tocka 7 (pregled TV 10. 11. 2026): cas klepeta (created_at) iz prihodnosti se ne sprejme kot tak."""
import unittest
from datetime import datetime, timedelta, timezone

from core import os_sporocila


def _cas(niz):
    return datetime.fromisoformat(niz)


class CasKlepeta(unittest.TestCase):
    def test_prihodnost_dobi_cas_prejema(self):
        zdaj = datetime.now(timezone.utc)
        for vrednost in ("9999-12-31T23:59:59Z", (zdaj + timedelta(days=2)).isoformat(),
                         (zdaj + timedelta(seconds=os_sporocila.KLEPET_PREHITEVA_S + 60)).isoformat()):
            cas = _cas(os_sporocila._cas_klepeta(vrednost))
            self.assertLess(abs((cas - zdaj).total_seconds()), 5, vrednost)

    def test_preteklost_in_majhen_zamik_ure_ostaneta(self):
        zdaj = datetime.now(timezone.utc).replace(microsecond=0)
        prej = zdaj - timedelta(hours=3)
        self.assertEqual(os_sporocila._cas_klepeta(prej.isoformat()), prej.isoformat())
        malo = zdaj + timedelta(seconds=60)
        self.assertEqual(os_sporocila._cas_klepeta(malo.isoformat()), malo.isoformat())

    def test_smeti(self):
        zdaj = datetime.now(timezone.utc)
        for vrednost in ("", "jutri", "2026-11-10T10:00:00", None):
            self.assertLess(abs((_cas(os_sporocila._cas_klepeta(vrednost)) - zdaj).total_seconds()), 5, vrednost)


if __name__ == "__main__":
    unittest.main()
