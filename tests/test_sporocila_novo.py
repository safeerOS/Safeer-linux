"""Novo e-sporocilo in osnutki v Sporocilih (lastnik, 14. 10. 2026: »manjka, da poslem novo sporocilo«)."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.sporocila.email import EmailAdapter
from core.sporocila.model import Kanal
from core.sporocila.storitev import StoritevSporocil

KOREN = Path(__file__).resolve().parents[1]


class NovoSporocilo(unittest.TestCase):
    def test_nova_nit_z_zadevo_brez_in_reply_to(self):
        smtp = MagicMock()
        with patch("core.sporocila.email.smtplib.SMTP_SSL", return_value=smtp):
            a = EmailAdapter("k", "jaz@example.test", "imap.example.test", "smtp.example.test", geslo="skrivno")
            a._zadnja_niti["ana@example.test"] = {"zadeva": "Stara", "message_id": "<staro@example.test>"}
            s = a.poslji("ana@example.test", "Pozdravljena", zadeva_nova="Nova tema")
        msg = smtp.send_message.call_args.args[0]
        self.assertEqual(msg["Subject"], "Nova tema")
        self.assertIsNone(msg["In-Reply-To"])
        self.assertEqual(msg["To"], "ana@example.test")
        self.assertEqual(s.smer, "ven")
        # odgovor iz te aplikacije nadaljuje novo nit
        self.assertEqual(a._zadnja_niti["ana@example.test"]["zadeva"], "Nova tema")

    def test_storitev_doda_pogovor_v_nabiralnik(self):
        smtp = MagicMock()
        with tempfile.TemporaryDirectory() as d, patch("core.sporocila.email.smtplib.SMTP_SSL", return_value=smtp):
            st = StoritevSporocil(Path(d) / "sporocila.db")
            a = EmailAdapter("k", "jaz@example.test", "imap.example.test", "smtp.example.test", geslo="skrivno")
            st.registriraj(Kanal("k", "email", "Test"), a, {"naslov": "jaz@example.test"})
            st.novo("k", "bob@example.test", "Porocilo", "Besedilo")
            pogovori = [p for p in st.pogovori() if p.id == "bob@example.test"]
            self.assertEqual(len(pogovori), 1)
            self.assertEqual(pogovori[0].zadeva, "Porocilo")
            st.zapri()

    def test_osnutki_in_preverjanje(self):
        from core.os_sporocila import SporocilaOS
        with tempfile.TemporaryDirectory() as d:
            sp = SporocilaOS(Path(d) / "sporocila.db", zazeni=False)
            seznam = sp.shrani_osnutek({"za": "bob@example.test", "zadeva": "a\nb", "besedilo": "x"})
            self.assertEqual(len(seznam), 1)
            self.assertEqual(seznam[0]["zadeva"], "a b")                    # brez nove vrstice v zadevi
            pot = Path(d) / "osnutki.json"
            self.assertEqual(pot.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):
                sp.novo("k", "ni-naslov", "z", "b")
            with self.assertRaises(ValueError):
                sp.novo("k", "bob@example.test", "z", "   ")
            self.assertEqual(sp.odstrani_osnutek(seznam[0]["id"]), [])
            sp.zapri()

    def test_vmesnik(self):
        html = (KOREN / "assets/os/index.html").read_text("utf-8")
        js = (KOREN / "assets/os/os.js").read_text("utf-8")
        for i in ("sporocilaNovo", "slojNovo", "obrazecNovo", "novoOd", "novoZa", "novoZadeva", "novoBesedilo", "stOsnutki"):
            self.assertEqual(html.count('id="%s"' % i), 1, i)
        for m in ("sporocilaNovo", "sporocilaOsnutki", "sporocilaShraniOsnutek", "sporocilaOdstraniOsnutek"):
            self.assertIn('klic("%s"' % m, js, m)
        most = (KOREN / "safeer_os.py").read_text("utf-8")
        for m in ("sporocilaNovo", "sporocilaOsnutki", "sporocilaShraniOsnutek", "sporocilaOdstraniOsnutek"):
            self.assertIn('"%s":' % m, most, m)


if __name__ == "__main__":
    unittest.main()


class OsnutkiNaStrezniku(unittest.TestCase):
    """Osnutek je tudi v mapi Osnutki e-postnega racuna (Gmail na telefonu ga vidi; lastnik, 14. 10. 2026)."""

    def _imap(self):
        imap = MagicMock()
        imap.list.return_value = ("OK", [b'(\\HasNoChildren \\Drafts) "/" "[Gmail]/Osnutki"',
                                         b'(\\HasNoChildren) "/" "INBOX"'])
        imap.append.return_value = ("OK", [b""])
        imap.select.return_value = ("OK", [b"1"])
        imap.uid.return_value = ("OK", [b"7"])
        return imap

    def test_append_v_mapo_drafts_in_zamenjava(self):
        imap = self._imap()
        with patch("core.sporocila.email.imaplib.IMAP4_SSL", return_value=imap):
            a = EmailAdapter("k", "jaz@example.test", "imap.example.test", "smtp.example.test", geslo="skrivno")
            mid = a.shrani_osnutek("bob@example.test", "Zadeva", "Besedilo", prejsnji_mid="<staro@example.test>")
        mapa, zastavice, _cas, telo = imap.append.call_args.args
        self.assertEqual(mapa, '"[Gmail]/Osnutki"')
        self.assertEqual(zastavice, "(\\Draft)")
        self.assertIn(b"Subject: Zadeva", telo)
        self.assertIn(mid.encode(), telo)
        iskanje = [c.args for c in imap.uid.call_args_list if c.args[0] == "search"][0]
        self.assertEqual(iskanje[-1], "<staro@example.test>")
        imap.expunge.assert_called_once()
        imap.logout.assert_called_once()

    def test_poslan_osnutek_izgine_tudi_s_streznika(self):
        from core.os_sporocila import SporocilaOS
        with tempfile.TemporaryDirectory() as d:
            sp = SporocilaOS(Path(d) / "sporocila.db", zazeni=False)
            adapter = MagicMock()
            adapter.shrani_osnutek.return_value = "<o1@example.test>"
            sp.storitev.adapterji["k"] = adapter
            o = sp.shrani_osnutek({"kanal_id": "k", "za": "bob@example.test", "zadeva": "z", "besedilo": "b"})[0]
            self.assertEqual(o["mid"], "<o1@example.test>")
            sp.shrani_osnutek(dict(o, besedilo="b2"))
            self.assertEqual(adapter.shrani_osnutek.call_args.args[3], "<o1@example.test>")   # zamenja prejsnjega
            sp.odstrani_osnutek(o["id"])
            adapter.odstrani_osnutek.assert_called_once()
            sp.zapri()

    def test_brez_streznika_ostane_krajevni(self):
        from core.os_sporocila import SporocilaOS
        with tempfile.TemporaryDirectory() as d:
            sp = SporocilaOS(Path(d) / "sporocila.db", zazeni=False)
            adapter = MagicMock()
            adapter.shrani_osnutek.side_effect = OSError("ni omrezja")
            sp.storitev.adapterji["k"] = adapter
            o = sp.shrani_osnutek({"kanal_id": "k", "za": "bob@example.test", "besedilo": "b"})
            self.assertEqual(len(o), 1)
            self.assertEqual(o[0]["mid"], "")
            sp.zapri()


class UskladitevOsnutkov(unittest.TestCase):
    def test_v_gmailu_poslan_osnutek_izgine(self):
        from core.os_sporocila import SporocilaOS
        with tempfile.TemporaryDirectory() as d:
            sp = SporocilaOS(Path(d) / "sporocila.db", zazeni=False)
            adapter = MagicMock()
            adapter.shrani_osnutek.side_effect = ["<a@x>", "<b@x>"]
            adapter.osnutki_na_strezniku.return_value = {"<b@x>"}
            sp.storitev.adapterji["k"] = adapter
            sp.shrani_osnutek({"kanal_id": "k", "za": "a@example.test", "besedilo": "a"})
            sp.shrani_osnutek({"kanal_id": "k", "za": "b@example.test", "besedilo": "b"})
            ostali = sp.uskladi_osnutke()
            self.assertEqual([o["za"] for o in ostali], ["b@example.test"])
            adapter.osnutki_na_strezniku.side_effect = OSError("brez omrezja")
            self.assertEqual(len(sp.uskladi_osnutke(najmanj_s=0)), 1)     # napaka ne brise nicesar
            sp.zapri()


class OsnutkiHkrati(unittest.TestCase):
    """Most shrani/odstrani/uskladi osnutke iz locenih niti (pregled 14. 10. 2026): noben osnutek se ne izgubi."""

    def test_hkratna_shranjevanja(self):
        import threading
        import time
        from core.os_sporocila import SporocilaOS
        with tempfile.TemporaryDirectory() as d:
            sp = SporocilaOS(Path(d) / "sporocila.db", zazeni=False)
            adapter = MagicMock()
            stevec = iter(range(1000))

            def shrani(*_a):
                time.sleep(0.02)          # IMAP APPEND traja: brez zaklepa sta oba zapisa prebrala isti seznam
                return "<%d@x>" % next(stevec)
            adapter.shrani_osnutek.side_effect = shrani
            sp.storitev.adapterji["k"] = adapter
            niti = [threading.Thread(target=sp.shrani_osnutek,
                                     args=({"id": "o%d" % i, "kanal_id": "k", "za": "a@example.test", "besedilo": str(i)},))
                    for i in range(8)]
            for n in niti:
                n.start()
            for n in niti:
                n.join()
            self.assertEqual(sorted(o["id"] for o in sp.osnutki()), sorted("o%d" % i for i in range(8)))
            self.assertEqual(len({o["mid"] for o in sp.osnutki()}), 8)
            sp.zapri()


class BrisanjeOsnutkaImap(unittest.TestCase):
    """Brisanje osnutka ne sme trajno izbrisati tujih sporocil z oznako \\Deleted v Osnutkih."""

    def _imap(self, zmoznosti, oznaceni=b"7"):
        imap = MagicMock()
        imap.capabilities = ("IMAP4REV1",)
        imap.capability.return_value = ("OK", [zmoznosti])
        imap.select.return_value = ("OK", [b"1"])

        def uid(ukaz, *a):
            if ukaz == "search" and a[-1] == "DELETED":
                return ("OK", [oznaceni])
            return ("OK", [b"7"])
        imap.uid.side_effect = uid
        return imap

    def test_uidplus_izbrise_samo_svoj_uid(self):
        imap = self._imap(b"IMAP4rev1 UIDPLUS MOVE")
        EmailAdapter._izbrisi_osnutek(EmailAdapter.__new__(EmailAdapter), imap, "Drafts", "<a@x>")
        self.assertIn(("expunge", "7"), [c.args for c in imap.uid.call_args_list])
        imap.expunge.assert_not_called()

    def test_brez_uidplus_ne_izbrise_tujih(self):
        imap = self._imap(b"IMAP4rev1", oznaceni=b"3 7")
        EmailAdapter._izbrisi_osnutek(EmailAdapter.__new__(EmailAdapter), imap, "Drafts", "<a@x>")
        imap.expunge.assert_not_called()
        imap = self._imap(b"IMAP4rev1", oznaceni=b"7")
        EmailAdapter._izbrisi_osnutek(EmailAdapter.__new__(EmailAdapter), imap, "Drafts", "<a@x>")
        imap.expunge.assert_called_once()

    def test_uskladitev_ne_steje_oznacenih(self):
        imap = MagicMock()
        imap.list.return_value = ("OK", [])
        imap.select.return_value = ("OK", [b"1"])
        imap.uid.return_value = ("OK", [b""])
        with patch("core.sporocila.email.imaplib.IMAP4_SSL", return_value=imap):
            a = EmailAdapter("k", "jaz@example.test", "imap.example.test", "smtp.example.test", geslo="skrivno")
            self.assertEqual(a.osnutki_na_strezniku(["<a@x>"]), set())
        self.assertEqual(imap.uid.call_args.args[:3], ("search", None, "UNDELETED"))
