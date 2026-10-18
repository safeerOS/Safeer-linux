import re
import unittest
from pathlib import Path

from core.external_apps import (
    DECLINE_QUIET_SECONDS, MAX_REMEMBERED_SITES, ExternalLinkGate, external_scheme, is_allowed, remember, site_of,
)

ROOT = Path(__file__).resolve().parents[1]


class ExternalSchemeTests(unittest.TestCase):
    def test_program_links_are_recognized(self):
        self.assertEqual(external_scheme("claude://claude.ai/login?code=abc&state=xyz"), "claude")
        self.assertEqual(external_scheme("CLAUDE://login"), "claude")
        self.assertEqual(external_scheme("mailto:info@safeer.si"), "mailto")
        self.assertEqual(external_scheme("zoommtg://zoom.us/join?confno=1"), "zoommtg")
        self.assertEqual(external_scheme("ms-teams:/l/meetup-join/x"), "ms-teams")
        self.assertEqual(external_scheme("web+safeer:x"), "web+safeer")

    def test_web_local_script_and_browser_links_never_leave_the_browser(self):
        for uri in ("https://claude.ai/", "http://example.org", "file:///etc/passwd", "javascript:alert(1)",
                    "JavaScript:alert(1)", "data:text/html,x", "blob:https://x/1", "about:blank",
                    "safeer://home", "view-source:https://x", "ws://x", "filesystem:https://x/temporary/a"):
            self.assertIsNone(external_scheme(uri), uri)

    def test_malformed_links_are_ignored(self):
        for uri in ("", None, "claude:", " claude://x", "claude://x\n", "claude://a\rb", "no scheme",
                    "1abc://x", "claude://" + "a" * 17000, "a" * 40 + "://x"):
            self.assertIsNone(external_scheme(uri), repr(uri)[:40])


class SiteAndPermissionTests(unittest.TestCase):
    def test_site_is_the_asking_web_page(self):
        self.assertEqual(site_of("https://Claude.AI./login?x=1"), "claude.ai")
        self.assertEqual(site_of("http://127.0.0.1:8080/"), "127.0.0.1")
        self.assertEqual(site_of("safeer://home"), "")
        self.assertEqual(site_of("file:///opt/safeer/ui/home.html"), "")
        self.assertEqual(site_of(None), "")

    def test_always_allow_is_per_site_and_program(self):
        permissions = remember({}, "claude.ai", "claude")
        self.assertTrue(is_allowed(permissions, "claude.ai", "claude"))
        self.assertFalse(is_allowed(permissions, "claude.ai", "mailto"))
        self.assertFalse(is_allowed(permissions, "evil.test", "claude"))
        self.assertFalse(is_allowed(permissions, "", "claude"))
        self.assertEqual(remember(permissions, "claude.ai", "claude"), permissions)
        self.assertEqual(remember(permissions, "", "claude"), permissions)
        self.assertFalse(is_allowed({"claude.ai": "claude"}, "claude.ai", "claude"))
        self.assertFalse(is_allowed(None, "claude.ai", "claude"))

    def test_remembered_sites_are_capped_and_input_is_not_modified(self):
        permissions = {}
        for i in range(MAX_REMEMBERED_SITES + 5):
            previous = permissions
            permissions = remember(permissions, f"site{i}.test", "mailto")
            self.assertIsNot(previous, permissions)
        self.assertEqual(len(permissions), MAX_REMEMBERED_SITES)
        self.assertNotIn("site0.test", permissions)
        self.assertIn(f"site{MAX_REMEMBERED_SITES + 4}.test", permissions)
        self.assertEqual(remember({"bad": 1, 2: ["x"]}, "a.test", "zoommtg"), {"a.test": ["zoommtg"]})


class GateTests(unittest.TestCase):
    def test_one_question_at_a_time_and_quiet_after_no(self):
        now = [100.0]
        gate = ExternalLinkGate(clock=lambda: now[0])
        self.assertTrue(gate.may_ask("claude.ai", "claude"))
        gate.asking()
        self.assertFalse(gate.may_ask("other.test", "mailto"))
        gate.answered("claude.ai", "claude", accepted=False)
        self.assertFalse(gate.may_ask("claude.ai", "claude"))
        self.assertTrue(gate.may_ask("claude.ai", "mailto"))
        now[0] += DECLINE_QUIET_SECONDS + 1
        self.assertTrue(gate.may_ask("claude.ai", "claude"))
        gate.asking()
        gate.answered("claude.ai", "claude", accepted=True)
        self.assertTrue(gate.may_ask("claude.ai", "claude"))


class BrowserWiringTests(unittest.TestCase):
    """Splet in Safeer Browser (GTK4, core/os_splet.py; GTK3 umaknjen 18. 10. 2026)."""

    def setUp(self):
        self.source = (ROOT / "core" / "os_splet.py").read_text()

    def _branch(self, start_marker, end_marker):
        start = self.source.index(start_marker)
        return self.source[start:self.source.index(end_marker, start)]

    def test_program_links_are_handled_before_they_are_blocked(self):
        policy = self._branch("def _politika", "def _odziv")
        self.assertIn("external_apps.external_scheme(naslov)", policy)
        self.assertLess(policy.index("external_apps.external_scheme(naslov)"), policy.index("adblock.is_threat_domain(naslov)"))
        self.assertIn("self._zunanji_program(naslov, shema", policy)

    def test_the_user_decides_and_safeer_never_opens_itself(self):
        method = self._branch("def _zunanji_program(", "def _zunanji_program_izid")
        self.assertIn("external_apps.is_allowed(", method)
        self.assertIn(".may_ask(gostitelj, shema)", method)
        self.assertIn('self._t("preklici")', method)


if __name__ == "__main__":
    unittest.main()
