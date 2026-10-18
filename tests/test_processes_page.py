"""safeer://procesi renders the monitor's data and its action links parse back (1.0.24; GTK4 Splet 1.0.127)."""
import re
import unittest

from core import processes_page


ROWS = [
    {"id": "t1", "title": "Facebook <script>", "cpu": 0.74, "rss_mb": 1229, "threads": 88, "active": True, "audio": False, "sleeping": False, "verdict": "hot"},
    {"id": "t2", "title": "YouTube Music", "cpu": 0.12, "rss_mb": 800, "threads": 45, "active": False, "audio": True, "sleeping": False, "verdict": "calm"},
    {"id": "t3", "title": "Stara stran", "cpu": 0.0, "rss_mb": 0, "threads": 0, "active": False, "audio": False, "sleeping": True, "verdict": "calm"},
    {"id": "t4", "title": "Novice", "cpu": 0.01, "rss_mb": 300, "threads": 20, "active": False, "audio": False, "sleeping": False, "verdict": "calm"},
]


class ProcessesPageTests(unittest.TestCase):
    def test_rows_are_escaped_sorted_and_summed(self):
        page = processes_page.render(ROWS, "sl", limit_mb=2048, cpu_budget=0.7)
        self.assertIn("Facebook &lt;script&gt;", page)
        self.assertLess(page.index("Facebook"), page.index("YouTube Music"))
        self.assertIn("74 %", page)
        self.assertIn("1,20 GB", page)
        self.assertIn("nad proračunom", page)
        self.assertIn("87 %", page)      # total CPU
        self.assertIn("2,27 GB", page)   # total memory
        self.assertIn("Meja pomnilnika na zavihek: 2048 MB", page)
        # 1.0.127: osvezitev z location.replace (brez vnosov v zgodovino), samo vidna in brez fokusa tipkovnice -
        # meta refresh je vsake 3 s vzel fokus in v ozadju osvezeval skrito stran.
        self.assertNotIn('http-equiv="refresh"', page)
        self.assertIn('location.replace("safeer://procesi")', page)
        self.assertIn("document.hidden", page)
        nonce = re.search(r"script-src 'nonce-([^']+)'", page).group(1)
        self.assertIn('<script nonce="%s">' % nonce, page)

    def test_actions_depend_on_state(self):
        page = processes_page.render(ROWS, "en", key="KLJUC")
        self.assertNotIn("safeer://procesi?spi=t1", page)   # active tab: no sleep link
        self.assertNotIn("safeer://procesi?spi=t2", page)   # sound: never sleeps, so no button that does nothing
        self.assertIn("safeer://procesi?spi=t4&amp;k=KLJUC", page)
        self.assertNotIn("safeer://procesi?spi=t3", page)   # already sleeping
        self.assertIn("safeer://procesi?zapri=t3", page)
        self.assertIn("sleeping", page)
        self.assertIn("1.20 GB", page)

    def test_action_links_parse_and_others_do_not(self):
        self.assertEqual(processes_page.parse_action("safeer://procesi?spi=t2"), ("spi", "t2"))
        self.assertEqual(processes_page.parse_action("safeer://procesi?zapri=t3"), ("zapri", "t3"))
        self.assertEqual(processes_page.parse_action("safeer://procesi"), (None, None))
        self.assertEqual(processes_page.parse_action("https://example.com/?spi=t2"), (None, None))
        self.assertEqual(processes_page.parse_action("safeer://home?spi=t2"), (None, None))
        self.assertEqual(processes_page.action_key("safeer://procesi?spi=t2&k=abc"), "abc")
        self.assertEqual(processes_page.action_key("safeer://procesi?spi=t2"), "")

    def test_reasons_apps_and_shared_process(self):
        rows = [
            {"id": "z1", "title": "Obrazec", "cpu": 0.0, "rss_mb": 200, "pid": 11, "reasons": ["form", "download"]},
            {"id": "z2", "title": "Prijava", "cpu": 0.1, "rss_mb": 300, "pid": 12, "reasons": ["linked"]},
            {"id": "z3", "title": "Okno prijave", "cpu": 0.0, "rss_mb": 300, "pid": 12, "reasons": ["linked"]},
            {"id": "a1", "title": "Klepet", "cpu": 0.0, "rss_mb": 150, "pid": 13, "app": True},
            {"id": "z4", "title": "Neizmerjen", "cpu": 0.0, "rss_mb": 0, "pid": 0},
        ]
        page = processes_page.render(rows, "sl", key="k")
        self.assertIn("urejen obrazec, prenos", page)
        self.assertIn("povezano okno", page)
        self.assertIn("vdelana aplikacija", page)
        for ident in ("z1", "z2", "z3"):
            self.assertNotIn("spi=" + ident, page)          # protected: no sleep link
        self.assertNotIn("zapri=a1", page)                   # embedded app: no actions at all
        self.assertIn("spi=z4", page)
        self.assertIn("<td>650 MB</td>", page)               # z2 and z3 share one process: counted once
        self.assertIn('<td class="t">Neizmerjen</td><td>—</td><td>—</td>', page)

    def test_rule_and_colours_from_tokens(self):
        page = processes_page.render(ROWS, "de", sleep_minutes=10)
        self.assertIn("10 Min.", page)
        self.assertNotIn("p class=\"rule\"", processes_page.render(ROWS, "de", sleep_minutes=0))
        css = page.split("</style>")[0].split("<style>")[1]
        lastni = css.split("}\n\n", 2)[-1]                    # pravila strani za blokoma tokens.css
        self.assertIn("var(--ozadje)", lastni)
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b", lastni), [])
        self.assertIn("a:focus-visible", lastni)

    def test_all_languages_have_all_texts(self):
        for lang, texts in processes_page._TEXT.items():
            self.assertEqual(set(texts), set(processes_page._TEXT["en"]), lang)
            self.assertIn("{min}", texts["rule"], lang)


if __name__ == "__main__":
    unittest.main()
