"""Zbiranje smeti samo na glavni niti (pregled 18. 10. 2026).

Sesutja Safeer OS 16. in 17. 10. (signal 5, koda 133): samodejni gc v delovni niti je sprostil predmet WebKit/GTK zunaj
glavne niti (WebKitov RELEASE_ASSERT(isMainThread) -> SIGTRAP). Vsi trije programi zato izklopijo samodejni gc in smeti
pobira glavna zanka (core/runtime_safety.py); nobena delovna nit ne klice gc.collect().
"""
import re
import unittest
from pathlib import Path

KOREN = Path(__file__).resolve().parent.parent


class GcNaGlavniNiti(unittest.TestCase):
    def test_vstopne_tocke_pred_zanko(self):
        for ime, zagon in (("safeer_os.py", "app.run([sys.argv[0]])"), ("safeer_control.py", "app.run(argv)"),
                           ("safeer_brskalnik.py", "app.run(argumenti)")):
            besedilo = (KOREN / ime).read_text(encoding="utf-8")
            self.assertIn("runtime_safety.install_main_thread_gc()", besedilo, ime)
            self.assertLess(besedilo.index("runtime_safety.install_main_thread_gc()"), besedilo.index(zagon), ime)

    def test_nobena_nit_ne_klice_gc_collect(self):
        dovoljeni = {"core/runtime_safety.py"}
        for pot in sorted((KOREN / "core").rglob("*.py")):
            rel = str(pot.relative_to(KOREN))
            if rel in dovoljeni:
                continue
            for i, vrstica in enumerate(pot.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"\bgc\.collect\(", vrstica) and not vrstica.lstrip().startswith("#") and "# glavna nit" not in vrstica:
                    self.fail("%s:%d klice gc.collect() - smeti pobira samo glavna nit (runtime_safety)" % (rel, i))

    def test_sled_ob_sigtrap(self):
        besedilo = (KOREN / "core/os_stabilnost.py").read_text(encoding="utf-8")
        self.assertIn("faulthandler.register(signal.SIGTRAP", besedilo)

    def test_zaprt_zavihek_pobere_glavna_nit(self):
        besedilo = (KOREN / "core/os_splet.py").read_text(encoding="utf-8")
        i = besedilo.index("def _unici_pogled")
        self.assertIn("GLib.idle_add(runtime_safety.collect_closed_views)", besedilo[i:i + 1200])

    def test_zbiranje_po_pragovih(self):
        """19. 10. 2026: prej gc.collect(0) vsaki 2 s in polno vsakih 30 s ne glede na delo (v mirovanju 66 ms glavne niti
        na 2 min, polno do 17,7 ms). Zdaj pragovi kot samodejni gc: brez novih predmetov nic."""
        import gc
        from unittest import mock
        from core import runtime_safety as rs
        ura = [10000.0]
        stevci = [(5, 0, 0)]
        with mock.patch.object(gc, "get_count", side_effect=lambda: stevci[0]), \
                mock.patch.object(gc, "get_threshold", return_value=(700, 10, 10)), \
                mock.patch.object(gc, "collect") as zberi, \
                mock.patch.dict(rs._stanje, {"polno": ura[0]}):
            ura_fn = lambda: ura[0]  # noqa: E731
            self.assertEqual(rs.korak(ura_fn), -1)                 # mirovanje: nic
            zberi.assert_not_called()
            stevci[0] = (701, 0, 0)
            self.assertEqual(rs.korak(ura_fn), 0)
            stevci[0] = (701, 11, 0)
            self.assertEqual(rs.korak(ura_fn), 1)
            stevci[0] = (701, 11, 11)
            self.assertEqual(rs.korak(ura_fn), 1)                  # polno po pragu sele po POLNO_NAJMANJ_S
            ura[0] += rs.POLNO_NAJMANJ_S
            self.assertEqual(rs.korak(ura_fn), 2)
            stevci[0] = (3, 1, 0)                                  # malo dela, nato dolgo mirovanje
            ura[0] += rs.POLNO_NAJVEC_S - 1
            self.assertEqual(rs.korak(ura_fn), -1)
            ura[0] += 1
            self.assertEqual(rs.korak(ura_fn), 2)                  # smeti starejse generacije ne cakajo ur
            stevci[0] = (3, 0, 0)
            ura[0] += 10 * rs.POLNO_NAJVEC_S
            self.assertEqual(rs.korak(ura_fn), -1)                 # brez dela tudi po dolgem casu nic
            self.assertEqual([c.args for c in zberi.call_args_list], [(0,), (1,), (1,), (2,), (2,)])
        # Utrip varuha in pregled gc se zdruzita v eno bujenje (timeout_add_seconds z istim taktom).
        from core import varuh_procesov
        self.assertEqual(rs.TIK_S, varuh_procesov.UTRIP_S)

    def test_runtime_safety_v_paketih(self):
        for skripta in ("packaging/install_os_payload.sh", "packaging/install_control_payload.sh"):
            self.assertIn(" runtime_safety ", (KOREN / skripta).read_text(encoding="utf-8"), skripta)


if __name__ == "__main__":
    unittest.main()
