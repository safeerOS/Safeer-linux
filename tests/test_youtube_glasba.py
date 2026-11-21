"""Katalog YouTube Music: razclenjevanje iskanja in albuma (isti primeri kot os/YoutubeGlasba v Safeer OS)."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core import youtube_glasba as g  # noqa: E402


def _vrstica(stolpci, navigacija="", video="", cas=""):
    v = {"flexColumns": [{"musicResponsiveListItemFlexColumnRenderer": {"text": {"runs": [{"text": s}]}}} for s in stolpci]}
    if navigacija:
        v["navigationEndpoint"] = {"browseEndpoint": {"browseId": navigacija}}
    if video:
        v["playlistItemData"] = {"videoId": video}
    if cas:
        v["fixedColumns"] = [{"musicResponsiveListItemFixedColumnRenderer": {"text": {"runs": [{"text": cas}]}}}]
    return {"musicResponsiveListItemRenderer": v}


ISKANJE = {"contents": [{"a": [
    _vrstica(["Nirvana", "Artist • 65M monthly audience"], navigacija="UCrPe3hLA51968GwxHSZ1llw"),
    _vrstica(["Lithium", "Song • Nirvana • 3:40"], video="aaaaaaaaaaa"),
    _vrstica(["In Utero", "Album • Nirvana • 1993"], navigacija="MPREb_fOBl6NeUrW5"),
    _vrstica(["Intervju", "Episode • Aug 25, 2021 • Novice"], video="bbbbbbbbbbb"),
    _vrstica(["Nevermind demo", "Playlist • Nekdo • 48K views"], navigacija="VLPLD2AE2529FD26AC4C"),
    _vrstica(["Lithium (Audio)", "Video • Nirvana • 94M views"], video="ccccccccccc"),
    _vrstica(["Pokvarjen album", "Album • X • 2000"], navigacija="NI-ALBUM"),
]}]}
ALBUM = {"header": {"musicResponsiveHeaderRenderer": {
    "title": {"runs": [{"text": "In Utero"}]},
    "straplineTextOne": {"runs": [{"text": "Nirvana"}]},
    "subtitle": {"runs": [{"text": "Album"}, {"text": " • "}, {"text": "1993"}]}}},
    "rows": [
        _vrstica(["Serve The Servants", "", "21M plays"], video="nsYZiO1FotI", cas="3:38"),
        _vrstica(["Scentless Apprentice", "", "15M plays"], video="upr0CVDw8Co", cas="3:49"),
        _vrstica(["Nerazpolozljiva", "", ""], cas="1:00"),
    ]}


class YoutubeGlasba(unittest.TestCase):
    def test_iskanje(self):
        r = g.razclen_iskanje(ISKANJE)
        self.assertEqual([(e.vrsta, e.naslov) for e in r],
                         [(g.IZVAJALEC, "Nirvana"), (g.SKLADBA, "Lithium"), (g.ALBUM, "In Utero")])
        self.assertEqual(r[1].podnaslov, "Nirvana • 3:40")
        self.assertEqual(r[2].id, "MPREb_fOBl6NeUrW5")

    def test_album_po_vrsti(self):
        a = g.razclen_album(ALBUM, "MPREb_fOBl6NeUrW5")
        self.assertEqual((a.naslov, a.izvajalec, a.leto), ("In Utero", "Nirvana", "1993"))
        self.assertEqual([s.naslov for s in a.skladbe], ["Serve The Servants", "Scentless Apprentice"])
        self.assertEqual([s.sekund for s in a.skladbe], [218, 229])

    def test_prazno(self):
        self.assertEqual(g.razclen_iskanje({}), [])
        self.assertIsNone(g.razclen_album({}, "MPREb_fOBl6NeUrW5"))
        self.assertFalse(g.je_id_albuma("UCrPe3hLA51968GwxHSZ1llw"))
        self.assertEqual(g.isci("  "), [])

    def test_zahteva(self):
        self.assertEqual(g.zahteva_iskanja("x")["context"]["client"]["clientName"], "WEB_REMIX")

    @unittest.skipUnless(os.environ.get("SAFEER_YTM_ISKANJE") and os.environ.get("SAFEER_YTM_ALBUM"), "pravi odgovori niso podani")
    def test_pravi_odgovori(self):
        with open(os.environ["SAFEER_YTM_ISKANJE"], encoding="utf-8") as f:
            r = g.razclen_iskanje(json.load(f))
        self.assertTrue(any(e.vrsta == g.IZVAJALEC and e.naslov == "Nirvana" for e in r))
        with open(os.environ["SAFEER_YTM_ALBUM"], encoding="utf-8") as f:
            a = g.razclen_album(json.load(f), "MPREb_fOBl6NeUrW5")
        self.assertEqual((len(a.skladbe), a.skladbe[0].naslov, a.skladbe[-1].naslov, a.leto, a.izvajalec),
                         (12, "Serve The Servants", "All Apologies", "1993", "Nirvana"))


if __name__ == "__main__":
    unittest.main()
