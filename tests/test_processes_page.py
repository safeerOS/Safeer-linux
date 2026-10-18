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


SYSTEM = [
    {"kind": "glavni", "pid": 100, "name": "python3", "cpu": 0.02, "rss_mb": 410, "threads": 40,
     "avg_cpu": 0.01, "peak_cpu": 0.35, "avg_mb": 400, "peak_mb": 520},
    {"kind": "omrezni", "pid": 101, "name": "WebKitNetworkPr", "cpu": 0.0, "rss_mb": 30, "threads": 10},
    {"kind": "spletni", "pid": 102, "name": "WebKitWebProces", "cpu": 0.0, "rss_mb": 90, "threads": 20, "tab": "Pošta"},
    {"kind": "spletni", "pid": 103, "name": "WebKitWebProces", "cpu": 0.0, "rss_mb": 60, "threads": 18},
    {"kind": "drugo", "pid": 104, "name": "rqbit", "cpu": 0.0, "rss_mb": 45, "threads": 12, "service": "torrent"},
    {"kind": "zavihki", "count": 3, "cpu": 0.1, "rss_mb": 700, "threads": 60, "avg_cpu": 0.05, "avg_mb": 650},
    {"kind": "peskovnik", "count": 8, "cpu": 0.0, "rss_mb": 4, "threads": 8},
]
SERVICES = [
    {"ime": "torrent", "vrsta": "zahteva", "tece": True, "zadnja_raba_s": 130, "mirovanje_s": 600, "razlog": "", "pidi": [104]},
    {"ime": "teamwork", "vrsta": "zahteva", "tece": False, "zadnja_raba_s": None, "mirovanje_s": 60, "ustavitev": 0},
    {"ime": "torrent_naprave", "vrsta": "zahteva", "tece": False, "zadnja_raba_s": 7300, "mirovanje_s": 600, "ustavitev": 1},
    {"ime": "scit", "vrsta": "vedno", "tece": True, "zadnja_raba_s": None, "mirovanje_s": 0, "razlog": "varuje"},
    {"ime": "link", "vrsta": "vedno", "tece": False, "zadnja_raba_s": None, "mirovanje_s": 0, "razlog": "dosegljivost"},
    {"ime": "ciscenje_gledanja", "opravilo": True, "razmik_s": 10800, "tece": False, "zadnje_s": 45},
]


class WholeProgramTests(unittest.TestCase):
    """1.0.127: ves program (glavni, omrezni, spletni procesi, podprocesi, peskovnik), povprecje in vrh zadnje ure,
    storitve na zahtevo."""

    def test_history_columns_for_tabs(self):
        rows = [dict(ROWS[3], pid=55, avg_cpu=0.03, peak_cpu=0.9, avg_mb=280, peak_mb=1500)]
        page = processes_page.render(rows, "sl", sample_s=30)
        vrstica = page.split(">Novice</td>", 1)[1].split("</tr>", 1)[0]
        self.assertEqual(re.findall(r"<td[^>]*>([^<]*)</td>", vrstica)[:6],
                         ["1 %", "3 %", "90 %", "300 MB", "280 MB", "1,46 GB"])
        self.assertIn('scope="colgroup" colspan="3">CPU</th>', page)
        self.assertIn('<th scope="col">povprečje</th><th scope="col">vrh</th>', page)
        self.assertIn("Povprečje in vrh veljata za zadnjo uro (vzorec vsakih 30 s", page)
        self.assertIn("prvi vzorec", processes_page.render(rows, "sl", sample_s=30, history_ready=False))
        self.assertNotIn("<h2>", page)                  # brez podatkov programa in storitev ni teh razdelkov

    def test_system_table_names_every_process_and_sums(self):
        page = processes_page.render(ROWS, "sl", system=SYSTEM, app="Safeer OS")
        self.assertIn("<h2>Safeer OS: vsi procesi</h2>", page)
        self.assertIn("Safeer OS – lupina, Control, Splet in predvajalnik", page)
        self.assertIn("omrežni proces (piškotki, prenosi)", page)
        self.assertIn("spletni proces · zavihek: Pošta", page)
        self.assertIn("spletni proces · drugo okno, vdelan pogled ali vnaprej pripravljen proces", page)
        self.assertIn("podproces · storitev: Torrent (rqbit)", page)
        self.assertIn("peskovnik spletnih procesov · 8 procesov", page)
        self.assertIn("spletni procesi zavihkov in vdelanih aplikacij (podrobno zgoraj) · 3 procesov", page)
        tabela = page.split("vsi procesi</h2>", 1)[1]
        self.assertLess(tabela.index("lupina"), tabela.index("omrežni"))          # glavni najprej
        self.assertLess(tabela.index("omrežni"), tabela.index("peskovnik"))       # peskovnik zadnji
        skupaj = tabela.split("Skupaj Safeer OS</td>", 1)[1].split("</tr>", 1)[0]
        celice = re.findall(r"<td[^>]*>([^<]*)</td>", skupaj)
        self.assertEqual(celice[0], "12 %")              # 2 + 10 %
        self.assertEqual(celice[3], "1,31 GB")           # 410+30+90+60+45+700+4 MB
        self.assertEqual(celice[6], "168")               # niti
        brskalnik = processes_page.render(ROWS, "sl", system=SYSTEM, app="Safeer Browser")
        self.assertIn('<td class="t">Safeer Browser <span class="pid">100</span></td>', brskalnik)
        self.assertNotIn("lupina, Control", brskalnik)

    def test_services_states_last_use_and_when_they_stop(self):
        page = processes_page.render(ROWS, "sl", services=SERVICES)
        tabela = page.split("<h2>Storitve</h2>", 1)[1]
        vrstice = {re.findall(r'<td class="t">([^<]*)</td>', v)[0]: re.findall(r"<td>([^<]*)</td>", v)
                   for v in tabela.split("<tr")[2:]}
        self.assertEqual(vrstice["Torrent (rqbit)"], ["teče", "pred 2 min", "po 10 min mirovanja"])
        self.assertEqual(vrstice["Teamwork (skupno urejanje)"], ["ni zagnana", "v tem zagonu še ne", "po 1 min mirovanja"])
        self.assertEqual(vrstice["Torrent za druge naprave (rqbit)"], ["ustavljena", "pred 2 h", "po 10 min mirovanja"])
        self.assertEqual(vrstice["Ščit (zaščita DNS)"], ["teče", "—", "nikoli – varuje računalnik"])
        self.assertEqual(vrstice["Safeer Link (sprejem drugih naprav)"],
                         ["izklopljena", "—", "nikoli – druge naprave morajo računalnik najti"])
        self.assertEqual(vrstice["Čiščenje filmov, ki jih nihče ne gleda"], ["občasno", "pred 45 s", "teče vsake 3 h"])
        self.assertIn("se zažene šele, ko jo potrebuješ", page)

    def test_every_registered_service_has_a_name_in_every_language(self):
        """Ime vsake storitve in opravila iz kode (registriraj/opravilo v core/) je na strani v vseh jezikih - brez
        surovega kljuca v vmesniku."""
        import glob
        import os
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        imena = set()
        for pot in glob.glob(os.path.join(koren, "core", "*.py")):
            with open(pot, encoding="utf-8") as f:
                besedilo = f.read()
            imena |= set(re.findall(r'registriraj\(\s*"([a-z_]+)"', besedilo))
            imena |= set(re.findall(r'\.opravilo\(\s*"([a-z_]+)"', besedilo))
        self.assertTrue({"torrent", "torrent_naprave", "teamwork", "twitch", "doh", "scit", "link", "iskalnik",
                         "ciscenje_gledanja", "ciscenje_prenosov"} <= imena, imena)
        for lang, texts in processes_page._TEXT.items():
            for ime in imena:
                self.assertIn("svc_" + ime, texts, (lang, ime))

    def test_every_language_renders_all_sections(self):
        for lang in processes_page._TEXT:
            page = processes_page.render(ROWS, lang, system=SYSTEM, services=SERVICES, app="Safeer OS", sample_s=30)
            for kljuc in ("services", "now", "avg", "peak"):
                self.assertIn(processes_page._TEXT[lang][kljuc], page, (lang, kljuc))
            self.assertNotIn("svc_", page, lang)          # vsaka storitev ima ime v vsakem jeziku
            self.assertNotIn("kind_", page, lang)
            self.assertNotIn("{", page.split("<body>", 1)[1].split("<script")[0], lang)   # vsi nadomestki zapolnjeni


if __name__ == "__main__":
    unittest.main()
