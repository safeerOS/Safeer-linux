"""Scit se vklopi sam, ko ovira izgine; gumb »Popravi« za ostanek Pi-hole (lastnik 2. 11. 2026: brez terminala).

Izmerjeno na prenosniku lastnika (safeer-os 0.4.92): po »ni mozno« ob zagonu Scit ni nikoli vec preveril ovire.
"""
import tempfile
import threading
import time
import unittest
from unittest import mock

from core import os_scit, root_ukaz
from core.shramba_json import Shramba


def _scit(mapa):
    return os_scit.Scit(Shramba(mapa + "/nastavitve.json"), mapa=mapa)


def _systemctl(aktivno_resolved=True, aktivno_ftl=False):
    def z(ukaz, cas=8.0):
        if ukaz[-1] == "systemd-resolved":
            return (0, "active") if aktivno_resolved else (3, "inactive")
        if ukaz[-1] == "pihole-FTL":
            return (0, "active") if aktivno_ftl else (3, "inactive")
        return (0, "")
    return z


class ScitStraza(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.mapa = self._tmp.name
        self.addCleanup(self._tmp.cleanup)

    def test_vklop_ob_oviri_velja_in_scit_zacne_ko_ovira_izgine(self):
        scit = _scit(self.mapa)
        ovira = threading.Event()
        ovira.set()
        zagnan = threading.Event()
        with mock.patch.object(os_scit, "razlog_nemoznosti", side_effect=lambda: "pihole_ostanek" if ovira.is_set() else ""), \
                mock.patch.object(os_scit, "pravilo_namesceno", return_value=True), \
                mock.patch.object(os_scit.Scit, "CAKAJ_MOZNO_S", 0.01), \
                mock.patch.object(os_scit.Scit, "_zazeni", side_effect=lambda *a, **k: zagnan.set()):
            stanje = scit.nastavi(True)
            self.assertEqual(stanje["razlog"], "pihole_ostanek")
            self.assertTrue(scit.vklopljen, "uporabnikova izbira velja, ceprav Scit se ne more delati")
            self.assertFalse(zagnan.is_set())
            ovira.clear()                                  # uporabnik pritisne Popravi ali odstrani ostanek
            self.assertTrue(zagnan.wait(2.0), "Scit se ni vklopil sam, ko je ovira izginila")
            scit._caka.join(1.0)
            self.assertEqual(scit.napaka, "")

    def test_zagon_ob_oviri_caka_namesto_da_obstane(self):
        scit = _scit(self.mapa)
        scit.shramba.set("scit", True)
        razlogi = ["lastni_dns", "lastni_dns", ""]
        zagnan = threading.Event()
        with mock.patch.object(os_scit, "razlog_nemoznosti", side_effect=lambda: razlogi.pop(0) if razlogi else ""), \
                mock.patch.object(os_scit.Scit, "CAKAJ_MOZNO_S", 0.01), \
                mock.patch.object(os_scit.Scit, "_zazeni", side_effect=lambda *a, **k: zagnan.set()):
            scit._zagon()
            self.assertTrue(zagnan.wait(2.0), "po zacetni oviri Scit ni nikoli vec preveril (napaka 0.4.92)")

    def test_izklopljen_ne_caka(self):
        scit = _scit(self.mapa)
        with mock.patch.object(os_scit, "razlog_nemoznosti", return_value="lastni_dns"), \
                mock.patch.object(os_scit.Scit, "_zazeni") as z:
            scit._zagon()
            time.sleep(0.05)
            self.assertFalse(z.called)
            self.assertIsNone(scit._caka)

    def test_popravi_fiksen_ukaz_prek_root_ukaz(self):
        scit = _scit(self.mapa)
        razlogi = ["pihole_ostanek"]
        with mock.patch.object(os_scit, "razlog_nemoznosti", side_effect=lambda: razlogi.pop(0) if razlogi else "lastni_dns"), \
                mock.patch.object(os_scit, "pravilo_namesceno", return_value=True), \
                mock.patch.object(os_scit, "_zazeni", return_value=(0, "")) as z:
            scit.popravi()
        ukaz = z.call_args_list[0][0][0]
        self.assertEqual(ukaz, root_ukaz.ukaz(root_ukaz.SH, "-c", os_scit.POPRAVI_PIHOLE_UKAZ))
        self.assertTrue(ukaz[0].startswith("/"), "pkexec z absolutno potjo")
        for p in os_scit.PIHOLE_OSTANKI:
            self.assertIn(p, os_scit.POPRAVI_PIHOLE_UKAZ)
        self.assertNotIn("~", os_scit.POPRAVI_PIHOLE_UKAZ)
        self.assertNotIn("/home", os_scit.POPRAVI_PIHOLE_UKAZ)

    def test_popravi_brez_ostanka_ne_klice_roota(self):
        scit = _scit(self.mapa)
        with mock.patch.object(os_scit, "razlog_nemoznosti", return_value="lastni_dns"), \
                mock.patch.object(os_scit, "pravilo_namesceno", return_value=True), \
                mock.patch.object(os_scit, "_zazeni", return_value=(0, "")) as z:
            scit.popravi()
        self.assertFalse(z.called, "Popravi ne sme zagnati roota, kadar ni znanega ostanka")

    def _razlog(self, ostanek, ftl):
        with mock.patch.object(os_scit.shutil, "which", return_value="/usr/bin/x"), \
                mock.patch.object(os_scit, "_zazeni", side_effect=_systemctl(aktivno_ftl=ftl)), \
                mock.patch.object(os_scit, "programi_uporabljajo_resolved", return_value=False), \
                mock.patch.object(os_scit, "vsebina_gostitelja",
                                  side_effect=lambda p: "DNSStubListener=no" if ostanek and "pi-hole" in p else None):
            return os_scit.razlog_nemoznosti()

    def test_razlog_pihole_ostanek(self):
        self.assertEqual(self._razlog(ostanek=True, ftl=False), "pihole_ostanek")

    def test_delujoc_pihole_ostane_lastni_dns(self):
        self.assertEqual(self._razlog(ostanek=True, ftl=True), "lastni_dns", "delujocega Pi-hole Scit ne pospravlja")
        self.assertEqual(self._razlog(ostanek=False, ftl=False), "lastni_dns")


if __name__ == "__main__":
    unittest.main()
