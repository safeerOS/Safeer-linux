"""Per-tab memory limit and the browser's own log file (1.0.24)."""
import importlib
import io
import os
import sys
import tempfile
import unittest


# Meja pomnilnika procesov strani v GTK4: core/pomnilnik (tests/test_splet_proces.py). Uspavanje zavihkov je imel samo
# umaknjeni brskalnik GTK3 (18. 10. 2026).


class LogFileTests(unittest.TestCase):
    def test_print_lines_land_in_the_rotating_log_and_still_reach_the_terminal(self):
        from core import log
        importlib.reload(log)
        original_out, original_err = sys.stdout, sys.stderr
        captured = io.StringIO()
        sys.__stdout__ = captured  # what the launcher's terminal (or /dev/null) would receive
        try:
            with tempfile.TemporaryDirectory() as config_dir:
                path = log.install(config_dir, "9.9.9")
                print("[Test] hello from stdout")
                print("[Test] warning on stderr", file=sys.stderr)
                sys.stdout.flush()
                with open(path, encoding="utf-8") as handle:
                    content = handle.read()
                self.assertIn("Safeer Browser 9.9.9 started", content)
                self.assertIn("I [Test] hello from stdout", content)
                self.assertIn("W [Test] warning on stderr", content)
                self.assertIn("hello from stdout", captured.getvalue())
                # Installing twice is harmless.
                self.assertEqual(log.install(config_dir), path)
        finally:
            sys.stdout, sys.stderr = original_out, original_err
            sys.__stdout__ = original_out
            for handler in list(__import__("logging").getLogger("safeer").handlers):
                __import__("logging").getLogger("safeer").removeHandler(handler)
                handler.close()


if __name__ == "__main__":
    unittest.main()


class LauncherScopeTests(unittest.TestCase):
    def test_launcher_runs_the_browser_in_a_user_scope_when_available(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, "packaging", "safeer-launcher"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("systemd-run --user --scope", text)
        self.assertIn("MemoryHigh=60%", text)
        self.assertIn("SAFEER_NO_SCOPE", text)          # opt-out and recursion guard
        self.assertIn("-- true >/dev/null 2>&1; then", text)  # probed first, silently skipped elsewhere
