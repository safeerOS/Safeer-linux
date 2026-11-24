"""Namizje na zaslonu (24. 11. 2026): vir stanja TV v Safeer OS (safeer_os._tv_v_linku). Loceno od cistih pravil
(tests/test_zaslon_namizja.py), ker uvoz safeer_os rabi nas WebKit (tools/pozeni-preizkuse.sh)."""

import unittest


class TvVLinku(unittest.TestCase):
    """Vir stanja: Safeer Control (Seznam + host.info samo za TV); Controla ne zaganjamo, pocasen TV je neznan."""

    def setUp(self):
        import safeer_os
        safeer_os._TV_ODGOVORI.clear()
        safeer_os._TV_STANJE.update(nit=None, tv=[])

    def _pozeni(self, odgovori, na_vodilu=True):
        from unittest import mock
        import safeer_os
        klici = []

        def naprave(metoda, *argumenti):
            klici.append((metoda,) + argumenti)
            if metoda == "Seznam":
                return {"ok": True, "naprave": [
                    {"id": "tv1", "platforma": "tv"}, {"id": "tel", "platforma": "android"},
                    {"id": "jaz", "platforma": "tv", "ta": True}]}
            return odgovori(argumenti[0])
        with mock.patch.object(safeer_os, "_control_na_vodilu", return_value=na_vodilu), \
                mock.patch.object(safeer_os, "_control_naprave", side_effect=naprave), \
                mock.patch.object(safeer_os.Gio, "bus_get_sync", return_value=None):
            return safeer_os._tv_v_linku(), klici

    def test_znamka_in_stanje(self):
        tv, klici = self._pozeni(lambda _id: {"ok": True, "data": {"znamka": "Philips", "zaslon": {"prizgan": False}}})
        self.assertEqual(tv, [{"id": "tv1", "znamka": "Philips", "prizgan": False}])
        self.assertEqual([k for k in klici if k[0] == "Ukaz"], [("Ukaz", "tv1", "host.info", "{}")])

    def test_starejsi_tv_brez_polja_zaslon(self):
        tv, _ = self._pozeni(lambda _id: {"ok": True, "data": {"znamka": "Philips"}})
        self.assertEqual(tv, [{"id": "tv1", "znamka": "Philips", "prizgan": None}])

    def test_pozen_odgovor_velja_v_naslednjem_ciklu(self):
        # TV v mirovanju odgovori pocasi: odgovor po roku ne sme biti izgubljen (sicer stanje za vedno »neznano«).
        import threading
        from unittest import mock
        import safeer_os
        sprosti = threading.Event()
        klici = []

        def pocasen(_id):
            klici.append(_id)
            sprosti.wait(5)
            return {"ok": True, "data": {"znamka": "Philips", "zaslon": {"prizgan": False}}}
        with mock.patch.object(safeer_os, "ROK_TV_S", 0.3):
            prvi, _ = self._pozeni(pocasen)
            drugi, _ = self._pozeni(pocasen)             # se v teku: ne sprasujemo znova
            sprosti.set()
            safeer_os._TV_STANJE["nit"].join(5)
            sprosti.clear()                                # tretji cikel: TV spet pocasen, velja shranjen odgovor
            tretji, _ = self._pozeni(pocasen)
            sprosti.set()
        self.assertEqual((prvi, drugi, klici), ([], [], ["tv1", "tv1"]))
        self.assertEqual(tretji, [{"id": "tv1", "znamka": "Philips", "prizgan": False}])

    def test_control_ne_tece(self):
        tv, klici = self._pozeni(lambda _id: {}, na_vodilu=False)
        self.assertEqual((tv, klici), ([], []))


if __name__ == "__main__":
    unittest.main()
