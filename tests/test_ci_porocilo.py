"""tools/ci_porocilo.py: mesecno porocilo CI (lastnik 25. 10. 2026) - izidi tekov, gradnje WebKita nad 45 min, vzroki
padcev po poslu in koraku, cas do prve napake; brez omrezja (lazni API)."""
import json
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

KOREN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOREN / "tools"))
import ci_porocilo as cp  # noqa: E402


def posel(ime, od, do, izid="success", koraki=(), tek=1):
    return {"name": ime, "started_at": od, "completed_at": do, "conclusion": izid, "run_id": tek,
            "steps": [{"name": n, "conclusion": c, "started_at": od, "completed_at": do} for n, c in koraki]}


class Porocilo(unittest.TestCase):
    def test_stetje(self):
        teki = [
            {"id": 1, "conclusion": "success", "head_branch": "a", "run_started_at": "2026-10-01T00:00:00Z",
             "updated_at": "2026-10-01T04:00:00Z"},
            {"id": 2, "conclusion": "failure", "head_branch": "b", "run_started_at": "2026-10-02T00:00:00Z",
             "updated_at": "2026-10-02T05:00:00Z"},
            {"id": 3, "conclusion": "cancelled", "head_branch": "b", "run_started_at": "2026-10-03T00:00:00Z"},
        ]
        posli = {
            1: [posel("webkit-deb", "2026-10-01T00:01:00Z", "2026-10-01T02:01:00Z", tek=1),
                posel("hitra-vrata (1)", "2026-10-01T00:00:00Z", "2026-10-01T00:06:00Z", tek=1)],
            2: [posel("hitra-vrata (3)", "2026-10-02T00:00:00Z", "2026-10-02T00:07:00Z", "failure",
                      [("Set up job", "success"), ("Unit tests without WebKit (part 3 of 6)", "failure")], tek=2),
                posel("flatpak", "2026-10-02T00:01:00Z", "2026-10-02T01:31:00Z", "failure",
                      [("Shield inside the sandbox of the package that was just built", "failure")], tek=2)],
            3: [],
        }
        md = cp.porocilo(teki, posli, "2026-10")
        self.assertIn("- 3 tekov: 1 uspesnih, 1 padlih, 1 preklicanih.", md)
        self.assertIn("Uspesnost brez preklicanih: 50 %", md)
        self.assertIn("- 2 tekov je gradilo WebKit (posel webkit-*/flatpak* nad 45 min); 2 takih poslov = 4 h.", md)
        self.assertIn("webkit-deb 1 (2 h; 1/0/0)", md)
        self.assertIn("- 1 hitra-vrata (3) :: Unit tests without WebKit (part 3 of 6)", md)
        self.assertIn("- 1 flatpak :: Shield inside the sandbox of the package that was just built", md)
        self.assertIn("Od tega nasi enotski preizkusi: 1.", md)
        # Prva napaka po 7 minutah (hitra vrata), ne po 90 (flatpak).
        self.assertIn("Do prve napake (padli teki, 1): mediana 7 min", md)
        self.assertIn("Do zelenega teka (1): mediana 4 h", md)
        self.assertIn("- Enotski preizkusi (1 tekov): zacetek mediana 0 min po zacetku teka (najkasneje 0 min), korak "
                      "traja mediana 7 min.", md)
        self.assertIn("- Prva napaka enotskega preizkusa (1 tekov): mediana 7 min po zacetku teka", md)
        self.assertIn("Veje z najvec padci: b 1.", md)

    def test_obdobja_po_tednih(self):
        od = datetime(2026, 10, 1, tzinfo=timezone.utc)
        do = datetime(2026, 11, 1, tzinfo=timezone.utc)
        obdobja = list(cp._obdobja(od, do))
        self.assertEqual(len(obdobja), 5)
        self.assertEqual(obdobja[0], "2026-10-01T00:00:00Z..2026-10-07T23:59:59Z")
        self.assertTrue(obdobja[-1].endswith("..2026-10-31T23:59:59Z"))

    def test_strani_in_predpomnilnik(self):
        klici = []

        def api(pot):
            klici.append(pot)
            if "/jobs?" in pot:
                stran = int(pot.rsplit("page=", 1)[1])
                return {"jobs": [{"name": "p%d" % i} for i in range(100 if stran == 1 else 3)]}
            stran = int(re.search(r"[?&]page=(\d+)", pot).group(1))
            return {"workflow_runs": [{"id": i + 1000 * stran} for i in range(100 if stran == 1 else 7)]}
        with tempfile.TemporaryDirectory() as d:
            tek = {"id": 5, "status": "completed"}
            self.assertEqual(len(cp.posli_teka(api, "r/r", tek, Path(d))), 103)
            n = len(klici)
            self.assertEqual(len(cp.posli_teka(api, "r/r", tek, Path(d))), 103)
            self.assertEqual(len(klici), n)                                  # drugic iz predpomnilnika
            self.assertEqual(len(json.loads((Path(d) / "5.json").read_text())), 103)
        teki = cp.teki_obdobja(api, "r/r", datetime(2026, 10, 1, tzinfo=timezone.utc),
                               datetime(2026, 10, 8, tzinfo=timezone.utc))
        self.assertEqual(len(teki), 107)
        self.assertIn("created=2026-10-01T00%3A00%3A00Z..2026-10-07T23%3A59%3A59Z", klici[-1])


if __name__ == "__main__":
    unittest.main()
