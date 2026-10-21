"""Preverjanje nasega WebKitGTK v procesu (core/zasebni_webkit.preveri_nas_webkit).

Pravilo lastnika, 21. 10. 2026: »vedno se uporablja nas WebKit«.
Program, meritev in preizkus z drugim WebKitom niso veljavni.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

from core import zasebni_webkit as zw  # noqa: E402


MOCK_MAPS_SISTEM = """\
55a12000-55a23000 r--p 00000000 08:01 1234 /usr/bin/python3
7f100000-7f120000 r--p 00000000 08:01 5678 /usr/lib/x86_64-linux-gnu/libwebkitgtk-6.0.so.4.3.5
7f120000-7f140000 r-xp 00020000 08:01 5678 /usr/lib/x86_64-linux-gnu/libwebkitgtk-6.0.so.4.3.5
"""

MOCK_MAPS_NAS_PREDPONA = """\
55a12000-55a23000 r--p 00000000 08:01 1234 /usr/bin/python3
7f100000-7f120000 r--p 00000000 08:01 5678 /usr/lib/safeer-webkit/lib/libwebkitgtk-6.0.so.4.19.4
7f120000-7f140000 r-xp 00020000 08:01 5678 /usr/lib/safeer-webkit/lib/libwebkitgtk-6.0.so.4.19.4
"""

MOCK_MAPS_FLATPAK_APP = """\
55a12000-55a23000 r--p 00000000 08:01 1234 /app/bin/python3
7f100000-7f120000 r--p 00000000 08:01 5678 /app/lib/libwebkitgtk-6.0.so.4.19.4
7f120000-7f140000 r-xp 00020000 08:01 5678 /app/lib/libwebkitgtk-6.0.so.4.19.4
"""

MOCK_MAPS_FLATPAK_USR = """\
55a12000-55a23000 r--p 00000000 08:01 1234 /app/bin/python3
7f100000-7f120000 r--p 00000000 08:01 5678 /usr/lib/x86_64-linux-gnu/libwebkitgtk-6.0.so.4.3.5
"""

MOCK_MAPS_APPIMAGE = """\
55a12000-55a23000 r--p 00000000 08:01 1234 /tmp/.mount_safeer123/usr/bin/python3
7f100000-7f120000 r--p 00000000 08:01 5678 /tmp/.mount_safeer123/usr/lib/libwebkitgtk-6.0.so.4.19.4
"""


class PreveriNasWebKitTest(unittest.TestCase):
    def setUp(self):
        self.mock_wk = mock.Mock()
        self.mock_wk.get_major_version.return_value = 2
        self.mock_wk.get_minor_version.return_value = 54
        self.mock_wk.get_micro_version.return_value = 1

    def test_maps_sistemska_pot_ni_nas(self):
        """Sistemski WebKitGTK (npr. /usr/lib/x86_64-linux-gnu/...) -> ni nas."""
        je_nas, pot, raz = zw.preveri_nas_webkit(
            WebKit=self.mock_wk,
            maps_vsebina=MOCK_MAPS_SISTEM,
            predpona="/usr/lib/safeer-webkit",
            uveljavi=False,
        )
        self.assertFalse(je_nas)
        self.assertEqual(pot, "/usr/lib/x86_64-linux-gnu/libwebkitgtk-6.0.so.4.3.5")
        self.assertEqual(raz, (2, 54, 1))

    def test_maps_s_predpono_je_nas(self):
        """WebKitGTK pod predpono paketa -> je nas."""
        je_nas, pot, raz = zw.preveri_nas_webkit(
            WebKit=self.mock_wk,
            maps_vsebina=MOCK_MAPS_NAS_PREDPONA,
            predpona="/usr/lib/safeer-webkit",
            uveljavi=False,
        )
        self.assertTrue(je_nas)
        self.assertEqual(pot, "/usr/lib/safeer-webkit/lib/libwebkitgtk-6.0.so.4.19.4")
        self.assertEqual(raz, (2, 54, 1))

    def test_maps_zgresena_predpona_ni_nas(self):
        """Ce knjiznica ni pod nastavljeno predpono, ni nasa."""
        je_nas, pot, _raz = zw.preveri_nas_webkit(
            WebKit=self.mock_wk,
            maps_vsebina=MOCK_MAPS_NAS_PREDPONA,
            predpona="/druga/predpona",
            uveljavi=False,
        )
        self.assertFalse(je_nas)

    def test_flatpak_app_je_nas(self):
        """Flatpak: WebKitGTK iz /app/ je nas."""
        with mock.patch.dict(os.environ, {"FLATPAK_ID": "io.github.memelandfaner.SafeerOS"}):
            je_nas, pot, _raz = zw.preveri_nas_webkit(
                WebKit=self.mock_wk,
                maps_vsebina=MOCK_MAPS_FLATPAK_APP,
                predpona=None,
                uveljavi=False,
            )
            self.assertTrue(je_nas)
            self.assertEqual(pot, "/app/lib/libwebkitgtk-6.0.so.4.19.4")

    def test_flatpak_usr_ni_nas(self):
        """Flatpak: WebKitGTK iz /usr (runtime namesto /app) ni nas."""
        with mock.patch.dict(os.environ, {"FLATPAK_ID": "io.github.memelandfaner.SafeerOS"}):
            je_nas, pot, _raz = zw.preveri_nas_webkit(
                WebKit=self.mock_wk,
                maps_vsebina=MOCK_MAPS_FLATPAK_USR,
                predpona=None,
                uveljavi=False,
            )
            self.assertFalse(je_nas)

    def test_appimage_appdir_je_nas(self):
        """AppImage: WebKitGTK pod $APPDIR je nas."""
        with mock.patch.dict(os.environ, {"APPDIR": "/tmp/.mount_safeer123"}):
            je_nas, pot, _raz = zw.preveri_nas_webkit(
                WebKit=self.mock_wk,
                maps_vsebina=MOCK_MAPS_APPIMAGE,
                predpona=None,
                uveljavi=False,
            )
            self.assertTrue(je_nas)
            self.assertEqual(pot, "/tmp/.mount_safeer123/usr/lib/libwebkitgtk-6.0.so.4.19.4")

    def test_uveljavi_sistemski_brez_dovoljenja_izhod(self):
        """Ce ni nas in ni SAFEER_SISTEMSKI_WEBKIT=1, uveljavi izpise napako in konca program."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SAFEER_SISTEMSKI_WEBKIT", None)
            with mock.patch.object(zw, "obvesti_uporabnika") as mock_obvesti, \
                    mock.patch.object(zw, "_namescen", return_value=True):
                with self.assertRaises(SystemExit) as cm:
                    zw.preveri_nas_webkit(
                        WebKit=self.mock_wk,
                        maps_vsebina=MOCK_MAPS_SISTEM,
                        predpona="/usr/lib/safeer-webkit",
                        uveljavi=True,
                    )
                self.assertEqual(cm.exception.code, 1)
                self.assertTrue(mock_obvesti.called)

    def test_izvorna_koda_samo_opozori(self):
        """Razvoj in CI (izvorna koda, sistemski gir1.2-webkit-6.0) se ne ustavita; namesceni program pa (zgoraj)."""
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SAFEER_SISTEMSKI_WEBKIT", None)
            with mock.patch.object(zw, "obvesti_uporabnika") as mock_obvesti, \
                    mock.patch.object(zw, "_namescen", return_value=False):
                je_nas, _, _ = zw.preveri_nas_webkit(WebKit=self.mock_wk, maps_vsebina=MOCK_MAPS_SISTEM,
                                                     predpona="/usr/lib/safeer-webkit", uveljavi=True)
                self.assertFalse(je_nas)
                self.assertFalse(mock_obvesti.called)

    def test_namescen_po_poti_programa(self):
        import types
        with mock.patch.dict(sys.modules, {"__main__": types.SimpleNamespace(__file__="/usr/lib/safeer-os/safeer_os.py")}), \
                mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FLATPAK_ID", None); os.environ.pop("APPIMAGE", None)
            self.assertTrue(zw._namescen())
        with mock.patch.dict(sys.modules, {"__main__": types.SimpleNamespace(__file__="/home/x/Safeer-linux/safeer_os.py")}), \
                mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FLATPAK_ID", None); os.environ.pop("APPIMAGE", None)
            self.assertFalse(zw._namescen())

    def test_uveljavi_sistemski_z_dovoljenjem_nadaljuje(self):
        """SAFEER_SISTEMSKI_WEBKIT=1 dovoli sistemski WebKit (samo razvoj) brez izhoda."""
        with mock.patch.dict(os.environ, {"SAFEER_SISTEMSKI_WEBKIT": "1"}):
            with mock.patch.object(zw, "obvesti_uporabnika") as mock_obvesti:
                je_nas, pot, raz = zw.preveri_nas_webkit(
                    WebKit=self.mock_wk,
                    maps_vsebina=MOCK_MAPS_SISTEM,
                    predpona="/usr/lib/safeer-webkit",
                    uveljavi=True,
                )
                self.assertFalse(je_nas)
                self.assertEqual(pot, "/usr/lib/x86_64-linux-gnu/libwebkitgtk-6.0.so.4.3.5")
                self.assertFalse(mock_obvesti.called)

    def test_uveljavi_nas_webkit_nadaljuje(self):
        """Nas WebKit se uveljavi brez napak in program se nadaljuje."""
        with mock.patch.object(zw, "obvesti_uporabnika") as mock_obvesti:
            je_nas, pot, raz = zw.preveri_nas_webkit(
                WebKit=self.mock_wk,
                maps_vsebina=MOCK_MAPS_NAS_PREDPONA,
                predpona="/usr/lib/safeer-webkit",
                uveljavi=True,
            )
            self.assertTrue(je_nas)
            self.assertFalse(mock_obvesti.called)

    def test_sporocilo_napake_jeziki(self):
        """Obvestilo uporabniku je prevedeno v vseh 6 jezikih vmesnika."""
        for j in ("sl", "en", "de", "es", "fr", "it"):
            besedilo = zw.sporocilo_napake(j)
            self.assertTrue(bool(besedilo))
            self.assertIn("Safeer", besedilo)
        self.assertIn("Safeer ne najde svojega spletnega pogona - znova namestite paket", zw.sporocilo_napake("sl"))

    def test_razlicica_struktura(self):
        """Razlicica se obnasa kot nabor in se oblikuje v niz."""
        r = zw.Razlicica((2, 54, 1))
        self.assertEqual(r, (2, 54, 1))
        self.assertEqual(str(r), "2.54.1")
        self.assertEqual(r[0], 2)
        self.assertEqual("%d.%d.%d" % r, "2.54.1")


if __name__ == "__main__":
    unittest.main()
