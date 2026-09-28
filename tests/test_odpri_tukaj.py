"""Odpri tukaj: apps.launch s pretokom in varen sprejem share.screen."""

import unittest
from unittest import mock

import safeer_control
from core import safeer_link


class _LinkZaUkaz:
    def __init__(self, odgovor):
        self.odgovor = odgovor
        self.klici = []

    def ukaz_pocakaj(self, naprava, dejanje, parametri, cas=6.0):
        self.klici.append((naprava, dejanje, parametri, cas))
        return self.odgovor


class OdpriTukaj(unittest.TestCase):
    def test_control_poslje_stream_true_in_prepozna_pending(self):
        control = safeer_control.SafeerControl.__new__(safeer_control.SafeerControl)
        control.link = _LinkZaUkaz({"ok": True, "data": {"stream": "pending"}})

        izid = control._naprave_metoda("OdpriTukaj", ["telefon-1", "com.safeer.video"])

        self.assertEqual(control.link.klici, [
            ("telefon-1", "apps.launch", {"app": "com.safeer.video", "stream": True}, 8.0)
        ])
        self.assertEqual(izid, {"ok": True, "tu": True, "koda": "", "message": ""})

    def test_napaka_naprave_se_ohrani(self):
        control = safeer_control.SafeerControl.__new__(safeer_control.SafeerControl)
        control.link = _LinkZaUkaz({"ok": False, "code": "ni_dovoljenja", "message": "Dovoli deljenje."})

        izid = control._naprave_metoda("OdpriTukaj", ["telefon-1", "app"])

        self.assertFalse(izid["ok"])
        self.assertEqual((izid["koda"], izid["message"]), ("ni_dovoljenja", "Dovoli deljenje."))


    def test_racunalnik_odpre_oddaljeni_zaslon_tukaj(self):
        # Windows/Linux zaslona ne potisneta sama: Control po zagonu odpre gledalca namizja.
        control = safeer_control.SafeerControl.__new__(safeer_control.SafeerControl)
        control.link = _LinkZaUkaz({"ok": True, "message": "Paint se odpira", "data": {"stream": "pending"}})
        control.link.naprave = [{"id": "pc-1", "platforma": "windows", "vrsta": "control"}]
        control.upravljaj_racunalnik = mock.Mock(return_value={"ok": True})
        with mock.patch.object(safeer_control.time, "sleep"):
            izid = control._naprave_metoda("OdpriTukaj", ["pc-1", "win_app_1"])
            for nit in list(safeer_control.threading.enumerate()):
                if nit.name == "safeer-odpri-tukaj":
                    nit.join(2)
        self.assertTrue(izid["ok"] and izid["tu"])
        control.upravljaj_racunalnik.assert_called_once_with("pc-1")


class SprejemZaslona(unittest.TestCase):
    def _link(self):
        link = safeer_link.SafeerLink.__new__(safeer_link.SafeerLink)
        link.gledani_zaslon = ""
        link.gledani_zaslon_id = ""
        link.zapri_deljeni_zaslon = mock.Mock()
        link._hub = mock.Mock(return_value="wss://hub.local:9443/cast")
        link._odtis = mock.Mock(return_value="shranjeni-odtis")
        link._odziv = mock.Mock()
        link._v_ozadju = lambda delo: delo()
        link._odpri_zaslon_s_huba = mock.Mock()
        return link

    def test_share_screen_uporabi_url_in_odtis_iz_sporocila(self):
        link = self._link()

        link._prejmi_deljenje("share.screen", {
            "sender": "telefon-1", "sender_name": "Telefon",
            "payload": {"action": "start", "id": "tok-1",
                        "url": "https://telefon.local:9443/cast/screen/tok-1/view", "fp": "odtis-iz-sporocila"},
        })

        link._odpri_zaslon_s_huba.assert_called_once_with(
            "https://telefon.local:9443/cast/screen/tok-1/view", "odtis-iz-sporocila")
        self.assertEqual((link.gledani_zaslon, link.gledani_zaslon_id), ("telefon-1", "tok-1"))

    def test_stop_zapre_samo_tekoci_gledalec(self):
        link = self._link()
        link.gledani_zaslon = "telefon-1"
        link.gledani_zaslon_id = "tok-1"

        with mock.patch.object(safeer_link.GLib, "idle_add", side_effect=lambda delo, *a: delo(*a)):
            link._prejmi_deljenje("share.screen", {"sender": "telefon-1",
                                                    "payload": {"action": "stop", "id": "drug-tok"}})
            link.zapri_deljeni_zaslon.assert_not_called()
            link._prejmi_deljenje("share.screen", {"sender": "telefon-1",
                                                    "payload": {"action": "stop", "id": "tok-1"}})

        link.zapri_deljeni_zaslon.assert_called_once_with()
        self.assertEqual((link.gledani_zaslon, link.gledani_zaslon_id), ("", ""))

    def test_webkit_dobi_samo_preverjeno_potrdilo_tega_odtisa(self):
        link = self._link()
        link.dovoli_potrdilo = mock.Mock()
        link.odpri_naslov = mock.Mock()
        url = "https://telefon.local:9443/cast/screen/tok-1/view"

        with mock.patch.object(safeer_link.link_tls, "potrdilo_pem", return_value="PEM") as pem, \
                mock.patch.object(safeer_link.GLib, "idle_add", side_effect=lambda delo, *a: delo(*a)):
            link._odpri_zaslon_s_huba = safeer_link.SafeerLink._odpri_zaslon_s_huba.__get__(link)
            link._odpri_zaslon_s_huba(url, "odtis-iz-sporocila")

        pem.assert_called_once_with(url, "odtis-iz-sporocila")
        link.dovoli_potrdilo.assert_called_once_with("PEM", "telefon.local")
        link.odpri_naslov.assert_called_once_with(url)


if __name__ == "__main__":
    unittest.main()
