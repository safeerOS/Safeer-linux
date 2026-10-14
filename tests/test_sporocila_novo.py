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
