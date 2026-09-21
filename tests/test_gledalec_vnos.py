"""Okno gledalca v Safeer Controlu: miska in tipkovnica na napravo, katere zaslon gledamo."""
import os
import re
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import safeer_control  # noqa: E402

JS = safeer_control.SafeerControl.GLEDALEC_VNOS_JS


class GledalecJs(unittest.TestCase):
    def test_posilja_samo_znana_dejanja(self):
        dejanja = set(re.findall(r'poslji\("(input\.[a-z]+)"', JS))
        # input.paste ostane na racunalniku (odlozisce); vse drugo razume naprava (Daljinec.DEJANJA).
        self.assertEqual(dejanja, {"input.tap", "input.swipe", "input.scroll", "input.key", "input.text", "input.paste"})

    def test_tipke_tipkovnice(self):
        for tipka, pomen in (("ArrowUp", "up"), ("ArrowLeft", "left"), ("Enter", "enter"),
                             ("Backspace", "backspace"), ("Delete", "delete"), ("Escape", "back")):
            self.assertIn('%s: "%s"' % (tipka, pomen), JS)

    def test_natipkano_pred_drugo_tipko(self):
        # Vrstni red: "abc" in takoj Vracalka mora izbrisati "c", ne znaka pred njim.
        self.assertIn('izprazni(); poslji("input.key"', JS)


class Prilepi(unittest.TestCase):
    def test_ctrl_v_poslje_besedilo_z_odlozisca(self):
        app = safeer_control.SafeerControl.__new__(safeer_control.SafeerControl)
        app.link = mock.Mock()
        app.gledalec = mock.Mock()
        odlozisce = mock.Mock()
        odlozisce.request_text.side_effect = lambda cb: cb(odlozisce, "geslo ni, samo besedilo")
        rezultat = mock.Mock()
        rezultat.get_js_value.return_value.to_string.return_value = '{"d": "input.paste", "p": {}}'
        with mock.patch.object(safeer_control.Gtk.Clipboard, "get_default", return_value=odlozisce):
            app._vnos_iz_gledalca(None, rezultat)
        app.link.poslji_vnos.assert_called_once_with("input.text", {"text": "geslo ni, samo besedilo"})

    def test_starejsa_naprava_dobi_kolesce_s_potegom(self):
        app = safeer_control.SafeerControl.__new__(safeer_control.SafeerControl)
        app.gledalec = mock.Mock()
        app._odziv_vnosa({"ok": False, "koda": "neznano_dejanje"})
        app.gledalec.get_child.return_value.run_javascript.assert_called_once()
        self.assertIn("safeerKolesceStaro", app.gledalec.get_child.return_value.run_javascript.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
