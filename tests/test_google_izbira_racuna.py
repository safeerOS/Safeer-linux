"""»Prijava z Googlom« na drugi strani (Spotify): Google pokaze izbiro racuna (lastnik, 17. 10. 2026)."""

import unittest
import urllib.parse

from core.os_splet import google_z_izbiro_racuna


class TestGoogleIzbiraRacuna(unittest.TestCase):
    def test_spotify_dobi_izbiro(self):
        n = ("https://accounts.google.com/o/oauth2/v2/auth?client_id=1.apps.googleusercontent.com&response_type=code"
             "&redirect_uri=https%3A%2F%2Faccounts.spotify.com%2Flogin%2Fgoogle%2Fredirect&scope=openid+email")
        nov = google_z_izbiro_racuna(n)
        q = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(nov).query))
        self.assertEqual(q["prompt"], "select_account")
        self.assertEqual(q["redirect_uri"], "https://accounts.spotify.com/login/google/redirect")
        self.assertTrue(google_z_izbiro_racuna("https://accounts.google.com/o/oauth2/auth?client_id=x"))

    def test_ne_spremeni(self):
        for n in ("https://accounts.google.com/o/oauth2/v2/auth?client_id=x&prompt=none",
                  "https://accounts.google.com/o/oauth2/v2/auth?client_id=x&prompt=consent",
                  "https://accounts.google.com/ServiceLogin?service=youtube",
                  "https://accounts.google.com/o/oauth2/iframe?client_id=x",
                  "http://accounts.google.com/o/oauth2/auth?client_id=x",
                  "https://accounts.google.com.evil.example/o/oauth2/auth?client_id=x",
                  "https://accounts.spotify.com/login", "nesmisel"):
            self.assertEqual(google_z_izbiro_racuna(n), "", n)


if __name__ == "__main__":
    unittest.main()
