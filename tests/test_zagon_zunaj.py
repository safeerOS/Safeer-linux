"""Preizkusi zagona uporabnikovih programov prek varuha procesov (oom_score_adj 0).

Preveri, da vsi moduli (os_programi, os_odpri_z, os_datoteke, os_sistem, namizni_programi):
- poklicejo varuh_procesov.zazeni_program;
- ob uspehu vrnejo uspeh / PID brez zagona v svojem procesu;
- ob napaki ali nedosegljivem varuhu varno uporabijo nadomestno pot (zagon po starem).
"""
import os
import shutil
import tempfile
import unittest
from unittest import mock

from core import namizni_programi, os_datoteke, os_odpri_z, os_programi, os_sistem, varuh_procesov


class ZagonZunajTesti(unittest.TestCase):
    def setUp(self):
        self.mapa = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.mapa, ignore_errors=True)

    def test_os_programi_zazeni_prek_varuha(self):
        shramba = mock.MagicMock()
        shramba.get.return_value = {}
        p = os_programi.Programi(shramba)
        vnos = os.path.join(self.mapa, "test.desktop")
        with open(vnos, "w", encoding="utf-8") as f:
            f.write("[Desktop Entry]\nType=Application\nName=Test\nExec=true\n")
        with mock.patch.object(p, "pot", return_value=vnos), \
                mock.patch.object(varuh_procesov, "zazeni_program", return_value=12345) as mz, \
                mock.patch("shutil.which", return_value="/usr/bin/gio"), \
                mock.patch("subprocess.Popen") as mp:
            ok = p.zazeni("test.desktop")
            self.assertTrue(ok)
            mz.assert_called_once()
            mp.assert_not_called()

    def test_os_programi_zazeni_nadomestna_pot(self):
        shramba = mock.MagicMock()
        shramba.get.return_value = {}
        p = os_programi.Programi(shramba)
        vnos = os.path.join(self.mapa, "test.desktop")
        with open(vnos, "w", encoding="utf-8") as f:
            f.write("[Desktop Entry]\nType=Application\nName=Test\nExec=true\n")
        with mock.patch.object(p, "pot", return_value=vnos), \
                mock.patch.object(varuh_procesov, "zazeni_program", return_value=None) as mz, \
                mock.patch("shutil.which", return_value="/usr/bin/gio"), \
                mock.patch("subprocess.Popen") as mp:
            ok = p.zazeni("test.desktop")
            self.assertTrue(ok)
            mz.assert_called_once()
            mp.assert_called_once()

    def test_os_odpri_z_prek_varuha(self):
        dat = os.path.join(self.mapa, "test.txt")
        open(dat, "w").close()
        vnos = os.path.join(self.mapa, "app.desktop")
        with open(vnos, "w", encoding="utf-8") as f:
            f.write("[Desktop Entry]\nType=Application\nName=App\nExec=true\n")
        with mock.patch("core.os_odpri_z.pot_vnosa", return_value=vnos), \
                mock.patch("shutil.which", return_value="/usr/bin/gio"), \
                mock.patch.object(varuh_procesov, "zazeni_program", return_value=12345) as mz, \
                mock.patch("subprocess.Popen") as mp:
            izid = os_odpri_z.odpri_z([dat], "app.desktop")
            self.assertTrue(izid.get("ok"))
            mz.assert_called_once()
            mp.assert_not_called()

    def test_os_odpri_z_nadomestna_pot(self):
        dat = os.path.join(self.mapa, "test.txt")
        open(dat, "w").close()
        vnos = os.path.join(self.mapa, "app.desktop")
        with open(vnos, "w", encoding="utf-8") as f:
            f.write("[Desktop Entry]\nType=Application\nName=App\nExec=true\n")
        with mock.patch("core.os_odpri_z.pot_vnosa", return_value=vnos), \
                mock.patch("shutil.which", return_value="/usr/bin/gio"), \
                mock.patch.object(varuh_procesov, "zazeni_program", return_value=None) as mz, \
                mock.patch("subprocess.Popen") as mp:
            izid = os_odpri_z.odpri_z([dat], "app.desktop")
            self.assertTrue(izid.get("ok"))
            mz.assert_called_once()
            mp.assert_called_once()

    def test_os_datoteke_odpri_prek_varuha(self):
        dat = os.path.join(self.mapa, "test.txt")
        open(dat, "w").close()
        with mock.patch("shutil.which", return_value="/usr/bin/gio"), \
                mock.patch.object(varuh_procesov, "zazeni_program", return_value=12345) as mz, \
                mock.patch("core.zasebni_webkit.odpri_privzeto") as mo, \
                mock.patch("subprocess.Popen") as mp:
            ok = os_datoteke.odpri(dat)
            self.assertTrue(ok)
            mz.assert_called_once()
            mo.assert_not_called()
            mp.assert_not_called()

    def test_os_datoteke_pokazi_v_mapi_prek_varuha(self):
        dat = os.path.join(self.mapa, "test.txt")
        open(dat, "w").close()
        with mock.patch("shutil.which", return_value="/usr/bin/nemo"), \
                mock.patch.object(varuh_procesov, "zazeni_program", return_value=12345) as mz, \
                mock.patch("subprocess.Popen") as mp:
            ok = os_datoteke.pokazi_v_mapi(dat)
            self.assertTrue(ok)
            mz.assert_called_once()
            mp.assert_not_called()

    def test_os_sistem_v_ozadju_prek_varuha(self):
        with mock.patch("core.root_ukaz.sistemski_ukaz", return_value=["/usr/bin/gnome-terminal"]), \
                mock.patch.object(varuh_procesov, "zazeni_program", return_value=12345) as mz, \
                mock.patch("subprocess.Popen") as mp:
            ok = os_sistem._v_ozadju(["gnome-terminal"])
            self.assertTrue(ok)
            mz.assert_called_once()
            mp.assert_not_called()

    def test_namizni_programi_zazeni_prek_varuha(self):
        najdba = {"ukaz": ["/usr/bin/test-app"]}
        with mock.patch("core.gostitelj.v_flatpaku", return_value=False), \
                mock.patch.object(varuh_procesov, "zazeni_program", return_value=12345) as mz, \
                mock.patch("subprocess.Popen") as mp:
            p = namizni_programi.zazeni(najdba)
            self.assertIsNotNone(p)
            self.assertEqual(p.pid, 12345)
            mz.assert_called_once()
            mp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
