"""Priponke v Sporocilih (lastnik, 15. 10. 2026: »Sporocila morajo znati zaznati priloge in jih tudi prenesti … Uporabnik
ne sme pogresati na primer Gmail ali Outlook«).

Brez omrezja: imaplib in smtplib sta nadomescena. Zgradbe BODYSTRUCTURE so oblike, kot jih vracajo Gmail, Outlook
(Exchange Online) in Dovecot (RFC 3501 7.4.2), z gnezdenimi multipart, slikami v vrstici, imeni RFC 2231 / RFC 2047 in
posredovanim pismom.
"""
import base64
import email
import json
import os
import quopri
import tempfile
import unittest
from email import policy
from pathlib import Path
from unittest.mock import MagicMock, patch

from core import os_sporocila
from core.sporocila import priponke as pr
from core.sporocila.email import EmailAdapter
from core.sporocila.model import Kanal, Sporocilo
from core.sporocila.storitev import StoritevSporocil

B64_IME = base64.b64encode("Poročilo.docx".encode()).decode()

GMAIL = (b'((("text" "plain" ("charset" "UTF-8") NIL NIL "quoted-printable" 120 5 NIL NIL NIL)'
         b'("text" "html" ("charset" "UTF-8") NIL NIL "quoted-printable" 400 8 NIL NIL NIL) "alternative" ("boundary" "000") NIL NIL)'
         b'("application" "pdf" ("name" "Ra\xc4\x8dun.pdf") "<f_abc>" NIL "base64" 78000 NIL ("attachment" ("filename" "Ra\xc4\x8dun.pdf")) NIL)'
         b' "mixed" ("boundary" "111") NIL NIL)')
OUTLOOK = ('((("text" "plain" ("charset" "us-ascii") NIL NIL "quoted-printable" 50 3 NIL NIL NIL NIL)'
           '("text" "html" ("charset" "us-ascii") NIL NIL "quoted-printable" 300 10 NIL NIL NIL NIL) "alternative" ("boundary" "_000_") NIL NIL NIL)'
           '("application" "vnd.openxmlformats-officedocument.wordprocessingml.document" ("name" "=?utf-8?B?%s?=") NIL'
           ' "=?utf-8?B?%s?=" "base64" 156000 NIL NIL NIL NIL) "mixed" ("boundary" "_004_") NIL "sl-SI" NIL)' % (B64_IME, B64_IME)).encode()
GNEZDENO = (b'(((("text" "plain" ("charset" "utf-8") NIL NIL "7bit" 10 1 NIL NIL NIL)("text" "html" ("charset" "utf-8") NIL NIL "7bit" 40 1 NIL NIL NIL)'
            b' "alternative")("image" "png" ("name" "image001.png") "<image001.png@01DA>" NIL "base64" 30000 NIL ("inline" ("filename" "image001.png")) NIL)'
            b' "related")("application" "pdf" ("name" "a.pdf") NIL NIL "base64" 1000 NIL ("attachment" ("filename" "a.pdf" "size" "700")) NIL)'
            b'("message" "rfc822" NIL NIL NIL "7bit" 2000 ("Mon, 1 Jan 2026 10:00:00 +0000" "Fwd: Zapisnik" ((NIL NIL "a" "example.test")) NIL NIL NIL NIL NIL NIL "<x@y>")'
            b' ("text" "plain" ("charset" "utf-8") NIL NIL "7bit" 20 2 NIL NIL NIL) 40 NIL NIL NIL NIL) "mixed")')
RFC2231 = (b'(("text" "plain" ("charset" "utf-8") NIL NIL "7bit" 10 1 NIL NIL NIL)("text" "plain" ("charset" "utf-8") NIL NIL "base64" 78 1 NIL'
           b' ("attachment" ("filename*0*" "utf-8\'\'%C4%8Drke%20" "filename*1*" "in%20%C5%A1umniki.txt" "filename" "fallback.txt")) NIL) "mixed")')
PODPISANO = (b'(("text" "plain" ("charset" "utf-8") NIL NIL "7bit" 10 1 NIL NIL NIL)("application" "pgp-signature" ("name" "signature.asc") NIL'
             b' "OpenPGP digital signature" "7bit" 300 NIL ("attachment" ("filename" "signature.asc")) NIL) "signed" ("protocol" "application/pgp-signature"))')


def _zg(bs: bytes) -> dict:
    return pr.zgradba(pr.razcleni(bs))


class Zgradba(unittest.TestCase):
    def test_gmail_mixed_alternative_pdf(self):
        z = _zg(GMAIL)
        self.assertEqual(z["besedilo"]["del"], "1.1")
        self.assertEqual(z["html"]["del"], "1.2")
        self.assertEqual(len(z["priponke"]), 1)
        p = z["priponke"][0]
        self.assertEqual((p["ime"], p["tip"], p["del"], p["kodiranje"], p["inline"]),
                         ("Račun.pdf", "application/pdf", "2", "base64", False))
        self.assertEqual(p["velikost"], 78000 * 57 // 78)          # velikost datoteke, ne kodiranega dela
        self.assertEqual(p["kodirano"], 78000)

    def test_outlook_brez_dispozicije_samo_name_kodirano_ime(self):
        p = _zg(OUTLOOK)["priponke"]
        self.assertEqual([(x["ime"], x["del"]) for x in p], [("Poročilo.docx", "2")])

    def test_gnezdeno_related_slika_v_vrstici_in_posredovano_pismo(self):
        z = _zg(GNEZDENO)
        self.assertEqual(z["besedilo"]["del"], "1.1.1")
        self.assertEqual(z["html"]["del"], "1.1.2")
        po_delu = {p["del"]: p for p in z["priponke"]}
        self.assertTrue(po_delu["1.2"]["inline"])
        self.assertEqual(po_delu["1.2"]["cid"], "image001.png@01DA")
        self.assertEqual(po_delu["2"]["ime"], "a.pdf")
        self.assertFalse(po_delu["2"]["inline"])
        self.assertEqual(po_delu["3"]["ime"], "Fwd: Zapisnik.eml")
        self.assertEqual(po_delu["3"]["tip"], "message/rfc822")

    def test_rfc2231_nadaljevanja_imajo_prednost(self):
        self.assertEqual(_zg(RFC2231)["priponke"][0]["ime"], "črke in šumniki.txt")

    def test_podpis_ni_priponka(self):
        z = _zg(PODPISANO)
        self.assertEqual(z["priponke"], [])
        self.assertEqual(z["besedilo"]["del"], "1")

    def test_enodelno_pismo(self):
        z = _zg(b'("application" "pdf" ("name" "x.pdf") NIL NIL "base64" 780 NIL ("attachment" ("filename" "x.pdf")) NIL)')
        self.assertEqual([(p["ime"], p["del"]) for p in z["priponke"]], [("x.pdf", "1")])
        z = _zg(b'("text" "plain" ("charset" "utf-8") NIL NIL "7bit" 10 1 NIL NIL NIL)')
        self.assertEqual((z["priponke"], z["besedilo"]["del"]), ([], "1"))

    def test_slika_brez_imena_in_brez_dispozicije_dobi_ime(self):
        z = _zg(b'(("text" "plain" NIL NIL NIL "7bit" 1 1 NIL NIL NIL)("image" "jpeg" NIL NIL NIL "base64" 100 NIL NIL NIL) "mixed")')
        self.assertEqual(z["priponke"][0]["ime"], "slika.jpg")

    def test_kodirano_ime_rfc2047_v_parametru(self):
        self.assertEqual(pr.parametri([b"name", b"=?UTF-8?B?xI1ydGEucGRm?="]), {"name": "črta.pdf"})
        self.assertEqual(pr.parametri([b"filename*", b"iso-8859-2''%E8rke.txt"]), {"filename": "črke.txt"})


class OdgovorFetch(unittest.TestCase):
    def test_dobesedni_niz_v_bodystructure_in_vec_pisem(self):
        podatki = [(b'1 (UID 7 FLAGS (\\Seen) BODYSTRUCTURE (("text" "plain" NIL NIL NIL "7bit" 3 1 NIL NIL NIL)'
                    b'("application" "octet-stream" ("name" {6}', b'a b.cz'),
                   (b') NIL NIL "base64" 100 NIL NIL NIL) "mixed" NIL NIL NIL) BODY[]<0> {5}', b'hello'), b')',
                   b'3 (FLAGS (\\Seen))',                              # nenaroceni FETCH brez UID
                   (b'2 (UID 9 BODY[]<0> {2}', b'hi'), b')']
        odg = pr.razcleni_fetch(podatki)
        self.assertEqual(odg[0]["UID"], "7")
        self.assertEqual(pr.vsebina_dela(odg[0]), b"hello")
        self.assertEqual(pr.zgradba(odg[0]["BODYSTRUCTURE"])["priponke"][0]["ime"], "a b.cz")
        self.assertNotIn("UID", odg[1])
        self.assertEqual((odg[2]["UID"], pr.vsebina_dela(odg[2])), ("9", b"hi"))

    def test_pokvarjen_odgovor_ne_podre(self):
        self.assertEqual(pr.razcleni_fetch([b"1 (UID 4 BODYSTRUCTURE ((((("]), [])
        self.assertEqual(pr.razcleni_fetch([b'1 (UID "neznan"']), [])


class Dekodiranje(unittest.TestCase):
    def test_base64_po_poljubnih_kosih(self):
        vsebina = os.urandom(5000)
        kodirano = base64.encodebytes(vsebina)                  # vrstice po 76 znakov
        for kos in (1, 3, 7, 77, 1000):
            d = pr.Dekodirnik("base64")
            izhod = b"".join(d.vnesi(kodirano[i:i + kos]) for i in range(0, len(kodirano), kos)) + d.koncaj()
            self.assertEqual(izhod, vsebina, kos)

    def test_base64_zlepljeni_kosi_s_polnilom(self):
        self.assertEqual(pr.dekodiraj(b"aGk=\r\naGk=\r\n", "base64"), b"hihi")

    def test_quoted_printable_po_kosih(self):
        besedilo = ("Šumniki čšž in dolga vrstica " * 20 + "\n") * 5
        kodirano = quopri.encodestring(besedilo.encode("utf-8"))
        for kos in (1, 5, 64):
            d = pr.Dekodirnik("quoted-printable")
            izhod = b"".join(d.vnesi(kodirano[i:i + kos]) for i in range(0, len(kodirano), kos)) + d.koncaj()
            self.assertEqual(izhod.decode("utf-8"), besedilo, kos)

    def test_brez_kodiranja(self):
        self.assertEqual(pr.dekodiraj(b"abc", "7bit"), b"abc")
        self.assertEqual(pr.dekodiraj(b"\x00\xff", "binary"), b"\x00\xff")


def _imap_s_deli(deli: dict):
    """IMAP, ki na BODY.PEEK[del]<odmik.dolzina> vrne kos dela (kot Dovecot/Gmail)."""
    imap = MagicMock()
    imap.noop.return_value = ("OK", [b""])
    imap.select.return_value = ("OK", [b"1"])
    klici = []

    def uid(ukaz, *a):
        klici.append((ukaz,) + a)
        if ukaz == "fetch":
            import re
            m = re.search(r"BODY\.PEEK\[([\d.]+)\]<(\d+)\.(\d+)>", a[1])
            if m:
                vsebina = deli[m.group(1)][int(m.group(2)):int(m.group(2)) + int(m.group(3))]
                return ("OK", [(b"1 (UID 7 BODY[%s]<%s> {%d}" % (m.group(1).encode(), m.group(2).encode(), len(vsebina)), vsebina), b")"])
        return ("OK", [None])
    imap.uid.side_effect = uid
    return imap, klici


class PrenosDela(unittest.TestCase):
    def test_prenos_po_kosih_z_napredkom_brez_oznacevanja(self):
        datoteka = os.urandom(3000)
        imap, klici = _imap_s_deli({"2": base64.encodebytes(datoteka)})
        napredek, izhod = [], []
        with patch("core.sporocila.email.imaplib.IMAP4_SSL", return_value=imap), patch.object(pr, "KOS_PRENOSA", 1000):
            a = EmailAdapter("k", "jaz@example.test", "imap.example.test", "smtp.example.test", geslo="skrivno")
            n = a.prenesi_priponko("uid:7", {"ime": "x.bin", "del": "2", "kodiranje": "base64"}, izhod.append, napredek.append)
        self.assertEqual(b"".join(izhod), datoteka)
        self.assertEqual(n, len(datoteka))
        self.assertGreater(len(napredek), 2)                        # vec kosov = vec korakov napredka
        imap.select.assert_called_with("INBOX", readonly=True)    # EXAMINE: prenos ne oznaci pisma kot prebranega
        self.assertTrue(all("BODY.PEEK[2]" in k[2] for k in klici if k[0] == "fetch"))

    def test_neveljaven_del_in_poslano_pismo(self):
        a = EmailAdapter("k", "jaz@example.test", "imap.example.test", "smtp.example.test", geslo="skrivno")
        with self.assertRaises(ValueError):
            a.prenesi_del(7, "2) (BODY[]", "", lambda b: None)        # vrinjanje v ukaz IMAP
        with self.assertRaises(ValueError):
            a.prenesi_priponko("mid:abc@x", {"del": "2"}, lambda b: None)

    def test_starejsa_priponka_brez_dela_po_imenu(self):
        imap, _ = _imap_s_deli({"2": base64.encodebytes(b"PDF")})
        bs = GMAIL

        def uid(ukaz, *a, _staro=imap.uid.side_effect):
            if ukaz == "fetch" and "BODYSTRUCTURE" in a[1]:
                return ("OK", [b"1 (UID 7 BODYSTRUCTURE " + bs + b")"])
            return _staro(ukaz, *a)
        imap.uid.side_effect = uid
        izhod = []
        with patch("core.sporocila.email.imaplib.IMAP4_SSL", return_value=imap):
            a = EmailAdapter("k", "jaz@example.test", "imap.example.test", "smtp.example.test", geslo="skrivno")
            a.prenesi_priponko("uid:7", {"ime": "Račun.pdf", "tip": "application/pdf"}, izhod.append)
        self.assertEqual(b"".join(izhod), b"PDF")


class Sinhronizacija(unittest.TestCase):
    def test_priponke_iz_bodystructure_in_besedilo_iz_dela(self):
        bs = (b'(("application" "zip" ("name" "arhiv.zip") NIL NIL "base64" 300000 NIL ("attachment" ("filename" "arhiv.zip")) NIL)'
              b'("text" "plain" ("charset" "utf-8") NIL NIL "quoted-printable" 30 1 NIL NIL NIL) "mixed")')
        glava = (b"From: Ana <ana@example.test>\r\nTo: jaz@example.test\r\nSubject: Arhiv\r\nMessage-ID: <z@example.test>\r\n"
                 b"Date: Mon, 28 Sep 2026 10:00:00 +0000\r\nContent-Type: multipart/mixed; boundary=b\r\n\r\n--b\r\n"
                 b"Content-Type: application/zip\r\nContent-Transfer-Encoding: base64\r\n\r\n" + b"QUJD" * 16000)  # odrezano pri 64 KB
        imap = MagicMock()
        imap.noop.return_value = ("OK", [b""])

        def uid(ukaz, *a):
            if ukaz == "search":
                return ("OK", [b"7"])
            if ukaz == "fetch" and "BODYSTRUCTURE" in a[1]:
                return ("OK", [(b"7 (UID 7 FLAGS () BODYSTRUCTURE " + bs + b" BODY[]<0> {1}", glava), b")"])
            if ukaz == "fetch" and "BODY.PEEK[2]" in a[1]:
                return ("OK", [(b"7 (UID 7 BODY[2]<0> {1}", b"Pozdrav, priponka je =C4=8Dez meje.\r\n"), b")"])
            return ("OK", [b""])
        imap.uid.side_effect = uid
        with patch("core.sporocila.email.imaplib.IMAP4_SSL", return_value=imap):
            a = EmailAdapter("k", "jaz@example.test", "imap.example.test", "smtp.example.test", geslo="skrivno")
            pogovori = list(a.pogovori())
        s = a.sporocila("ana@example.test")[0]
        self.assertEqual(s.besedilo, "Pozdrav, priponka je čez meje.")
        self.assertEqual([(p["ime"], p["del"]) for p in s.priponke], [("arhiv.zip", "1")])
        self.assertEqual(pogovori[0].zadnje_sporocilo, "Pozdrav, priponka je čez meje.")


class PosiljanjePrilog(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.mapa = Path(self.d.name)

    def tearDown(self):
        self.d.cleanup()

    def _adapter(self):
        return EmailAdapter("k", "jaz@example.test", "imap.example.test", "smtp.example.test", geslo="skrivno")

    def test_priloga_v_multipart(self):
        pot = self.mapa / "Poročilo.pdf"
        pot.write_bytes(b"%PDF-1.4 vsebina")
        (self.mapa / "brez").write_bytes(b"\x00\x01")
        smtp = MagicMock()
        with patch("core.sporocila.email.smtplib.SMTP_SSL", return_value=smtp):
            s = self._adapter().poslji("ana@example.test", "Glej prilogo", [{"pot": str(pot)}, {"pot": str(self.mapa / "brez")}])
        msg = smtp.send_message.call_args.args[0]
        self.assertTrue(msg.is_multipart())
        priloge = list(msg.iter_attachments())
        self.assertEqual([p.get_filename() for p in priloge], ["Poročilo.pdf", "brez"])
        self.assertEqual(priloge[0].get_content_type(), "application/pdf")
        self.assertEqual(priloge[1].get_content_type(), "application/octet-stream")
        self.assertEqual(priloge[0].get_payload(decode=True), b"%PDF-1.4 vsebina")
        # Prejemnik dobi pismo, ki ga razume katerikoli odjemalec (kodirano ime po RFC 2231).
        znova = email.message_from_bytes(msg.as_bytes(policy=policy.SMTP), policy=policy.default)
        self.assertEqual(next(znova.iter_attachments()).get_filename(), "Poročilo.pdf")
        self.assertEqual([p["ime"] for p in s.priponke], ["Poročilo.pdf", "brez"])
        self.assertEqual(s.priponke[0]["lokalno"], str(pot.resolve()))

    def test_prevelike_priloge_zavrnjene_pred_povezavo(self):
        velika = self.mapa / "velika.bin"
        with open(velika, "wb") as f:
            f.truncate(pr.NAJVEC_PRILOG + 1)
        with patch("core.sporocila.email.smtplib.SMTP_SSL") as smtp:
            with self.assertRaisesRegex(ValueError, "priloge_prevelike"):
                self._adapter().poslji("ana@example.test", "x", [{"pot": str(velika)}])
            smtp.assert_not_called()

    def test_manjkajoca_priloga(self):
        with patch("core.sporocila.email.smtplib.SMTP_SSL") as smtp:
            with self.assertRaisesRegex(ValueError, "prilog_ni"):
                self._adapter().poslji("ana@example.test", "x", [{"pot": str(self.mapa / "ni.pdf")}])
            smtp.assert_not_called()


class OsnutekSPrilogami(unittest.TestCase):
    def test_osnutek_hrani_priloge_in_jih_poslje_na_streznik(self):
        with tempfile.TemporaryDirectory() as d:
            priloga = Path(d) / "skica.png"
            priloga.write_bytes(b"\x89PNG")
            sp = os_sporocila.SporocilaOS(Path(d) / "sp.db", zazeni=False)
            adapter = MagicMock()
            adapter.shrani_osnutek.return_value = "<o@x>"
            sp.storitev.adapterji["k"] = adapter
            o = sp.shrani_osnutek({"kanal_id": "k", "za": "bob@example.test", "besedilo": "b",
                                   "priloge": [str(priloga), str(Path(d) / "ni.pdf"), 5]})[0]
            self.assertEqual(o["priloge"], [str(priloga.resolve())])          # samo obstojece datoteke
            self.assertEqual(adapter.shrani_osnutek.call_args.args[4], [{"pot": str(priloga.resolve())}])
            sp.zapri()

    def test_imap_osnutek_s_prilogo(self):
        with tempfile.TemporaryDirectory() as d:
            priloga = Path(d) / "skica.png"
            priloga.write_bytes(b"\x89PNG")
            imap = MagicMock()
            imap.list.return_value = ("OK", [b'(\\HasNoChildren \\Drafts) "/" "Drafts"'])
            imap.append.return_value = ("OK", [b""])
            with patch("core.sporocila.email.imaplib.IMAP4_SSL", return_value=imap):
                EmailAdapter("k", "jaz@example.test", "i.example.test", "s.example.test", geslo="x").shrani_osnutek(
                    "bob@example.test", "Z", "B", "", [{"pot": str(priloga)}])
            telo = imap.append.call_args.args[3]
            msg = email.message_from_bytes(telo, policy=policy.default)
            self.assertEqual([p.get_filename() for p in msg.iter_attachments()], ["skica.png"])


class DrugiKanali(unittest.TestCase):
    def test_telegram_najvecja_fotografija_in_getfile(self):
        from core.sporocila.telegram_bot import TelegramBotAdapter
        p = TelegramBotAdapter._priponka("photo", [{"file_id": "maj", "file_size": 10}, {"file_id": "vel", "file_size": 900}], "5")
        self.assertEqual((p["ime"], p["tip"], p["file_id"], p["velikost"]), ("foto_5.jpg", "image/jpeg", "vel", 900))
        a = TelegramBotAdapter("t", zeton="123:abc")
        with patch.object(a, "_api", return_value={"file_path": "photos/f.jpg"}) as api, \
                patch("core.sporocila.telegram_bot.prenesi_url", return_value=3) as prenos:
            a.prenesi_priponko("5", p, lambda b: None)
        api.assert_called_once_with("getFile", {"file_id": "vel"})
        self.assertEqual(prenos.call_args.args[0], "https://api.telegram.org/file/bot123:abc/photos/f.jpg")
        with patch.object(a, "_api", return_value={"file_path": "../x"}), self.assertRaises(ValueError):
            a.prenesi_priponko("5", p, lambda b: None)

    def test_matrix_overjeni_prenos_mxc(self):
        from core.sporocila.matrix import MatrixAdapter
        a = MatrixAdapter("m", "https://matrix.example.test", zeton="tok")
        with patch("core.sporocila.matrix.prenesi_url", return_value=1) as prenos:
            a.prenesi_priponko("$e", {"url": "mxc://example.test/AbC"}, lambda b: None)
        self.assertEqual(prenos.call_args.args[0], "https://matrix.example.test/_matrix/client/v1/media/download/example.test/AbC")
        self.assertEqual(prenos.call_args.args[3], {"Authorization": "Bearer tok"})
        for slab in ("https://drugje/x", "mxc://a/b/../c", "mxc://"):
            with self.assertRaises(ValueError):
                a.prenesi_priponko("$e", {"url": slab}, lambda b: None)

    def test_prenos_url_samo_https(self):
        from core.sporocila.adapter import prenesi_url
        with self.assertRaisesRegex(ValueError, "ni_varno"):
            prenesi_url("http://zunaj.example/datoteka", lambda b: None)


class _Adapter:
    vrsta = "email"
    zmore = {"poslji", "priloge"}

    def __init__(self, vsebina: bytes):
        self.vsebina, self.klici = vsebina, 0

    def prenesi_priponko(self, sid, p, pisi, napredek=None):
        self.klici += 1
        pisi(self.vsebina[:3])
        if napredek:
            napredek(3)
        pisi(self.vsebina[3:])
        return len(self.vsebina)

    def oznaci_prebrano(self, _):
        pass

    def html_pisma(self, sid, del_):
        return '<p>Pozdrav</p><img src="cid:logo@x"><img src="https://sled.example/p.gif"><script>x()</script>'


class SporocilaOSPriponke(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.koren = Path(self.d.name)
        self.dom = self.koren / "dom"
        (self.dom / ".config").mkdir(parents=True)
        (self.dom / "Prejemi").mkdir()
        (self.dom / ".config" / "user-dirs.dirs").write_text('XDG_DOWNLOAD_DIR="$HOME/Prejemi"\n', encoding="utf-8")
        self.okolje = patch.dict(os.environ, {"HOME": str(self.dom), "XDG_CONFIG_HOME": str(self.dom / ".config"),
                                              "XDG_CACHE_HOME": str(self.dom / ".cache")})
        self.okolje.start()
        self.os = os_sporocila.SporocilaOS(self.koren / "sp.db", zazeni=False)
        self.adapter = _Adapter(b"VSEBINA PDF")
        st = self.os.storitev
        st.registriraj(Kanal("k", "email", "Test"), self.adapter, {"naslov": "jaz@example.test"})
        with st.db:
            st._shrani_sporocilo("k", Sporocilo("uid:7", "ana@example.test", "noter", "", "2026-10-15T08:00:00+00:00", [
                {"ime": "../../.bashrc", "tip": "text/plain", "velikost": 11, "kodirano": 11, "del": "2", "kodiranje": "7bit"},
                {"ime": "Račun.pdf", "tip": "application/pdf", "velikost": 11, "del": "3", "kodiranje": "base64"},
                {"ime": "namesti.sh", "tip": "application/x-sh", "velikost": 11, "del": "4"},
                {"ime": "logo.png", "tip": "image/png", "velikost": 900, "del": "1.2", "inline": True, "cid": "logo@x"},
            ], "prejeto", "1.1"))
            st.db.execute("INSERT INTO pogovori(id,kanal_id,oseba_id,zadeva,zadnje_sporocilo,neprebrano,cas,identiteta) "
                          "VALUES('ana@example.test','k','o1','Racun','',0,'2026-10-15T08:00:00+00:00','ana@example.test')")

    def tearDown(self):
        self.os.storitev.zapri()
        self.okolje.stop()
        self.d.cleanup()

    def test_mapa_prejemov_po_xdg(self):
        self.assertEqual(os_sporocila.mapa_prejemov(), str(self.dom / "Prejemi"))

    def test_pogovor_da_opis_brez_lokalnih_podatkov(self):
        s = self.os.pogovor("k", "ana@example.test")[0]
        self.assertEqual(s["html"], "1.1")
        po_imenu = {p["ime"]: p for p in s["priponke"]}
        self.assertEqual(po_imenu["Račun.pdf"]["kljuc"], "3")
        self.assertEqual(po_imenu["Račun.pdf"]["predogled"], "pdf")
        self.assertTrue(po_imenu["namesti.sh"]["nevarna"])
        self.assertEqual(po_imenu["namesti.sh"]["predogled"], "nevarno")
        self.assertTrue(po_imenu["logo.png"]["inline"])
        self.assertNotIn("del", po_imenu["Račun.pdf"])
        # Sponka v seznamu pogovorov: ima pravo priponko (ne samo logotip v vrstici).
        p = self.os.seznam()["skupine"][0]["pogovori"][0]
        self.assertTrue(p["priponke"])

    def test_prenos_v_prejemi_varno_in_edinstveno_ime(self):
        napredek = []
        r1 = self.os.priponka_prenesi("k", "uid:7", "2", napredek.append)
        r2 = self.os.priponka_prenesi("k", "uid:7", "2")
        self.assertEqual(Path(r1["pot"]).parent, self.dom / "Prejemi")          # ../../ ne uide iz mape
        self.assertEqual(r1["ime"], "bashrc")                                   # brez poti in brez skrite pike
        self.assertEqual(r2["ime"], "bashrc (1)")
        self.assertEqual(Path(r1["pot"]).read_bytes(), b"VSEBINA PDF")
        self.assertEqual(napredek[-1], 1.0)
        self.assertFalse(list((self.dom / "Prejemi").glob("*.part")))

    def test_predpomnilnik_enkrat_in_prenos_iz_njega(self):
        pot, _p = self.os.priponka_v_predpomnilnik("k", "uid:7", "3")
        pot2, _p = self.os.priponka_v_predpomnilnik("k", "uid:7", "3")
        self.assertEqual(pot, pot2)
        self.assertEqual(self.adapter.klici, 1)                                  # drugic iz predpomnilnika
        self.assertTrue(pot.startswith(str(self.dom / ".cache" / "safeer-os" / "priloge")))
        self.assertEqual(os.stat(os.path.dirname(pot)).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(pot).st_mode & 0o777, 0o600)
        r = self.os.priponka_prenesi("k", "uid:7", "3")
        self.assertEqual(self.adapter.klici, 1)                                  # »Prenesi« po predogledu: brez omrezja
        self.assertFalse(os.path.exists(pot))                                    # ni dvojnika v predpomnilniku
        pot3, _p = self.os.priponka_v_predpomnilnik("k", "uid:7", "3")
        self.assertEqual(pot3, r["pot"])                                         # predogled bere iz Prejemov
        self.assertEqual(self.adapter.klici, 1)
        Path(r["pot"]).write_bytes(b"spremenjeno besedilo")                     # druga velikost: Prejemi ne veljajo
        pot4, _p = self.os.priponka_v_predpomnilnik("k", "uid:7", "3")
        self.assertNotEqual(pot4, r["pot"])
        self.assertEqual(self.adapter.klici, 2)

    def test_odstranjen_kanal_izbrise_predpomnilnik(self):
        pot, _p = self.os.priponka_v_predpomnilnik("k", "uid:7", "3")
        self.os.odstrani_kanal("k")
        self.assertFalse(os.path.exists(pot))

    def test_prenesi_vse_brez_slik_v_vrstici(self):
        r = self.os.priponke_prenesi_vse("k", "uid:7")
        self.assertEqual(len(r["poti"]), 3)
        self.assertFalse(any(p.endswith("logo.png") for p in r["poti"]))

    def test_neznana_priponka(self):
        with self.assertRaises(ValueError):
            self.os.priponka_prenesi("k", "uid:7", "99")
        with self.assertRaises(ValueError):
            self.os.priponka_prenesi("k", "uid:8", "2")

    def test_priloge_samo_za_eposto(self):
        with self.assertRaisesRegex(ValueError, "priloge_ni_podprto"):
            self.os._priloge("drug", ["/tmp/x"])
        self.assertEqual(self.os._priloge("k", [{"pot": "/a"}, "/b"]), [{"pot": "/a"}, {"pot": "/b"}])

    def test_izvirnik_s_slikami_v_vrstici_iz_predpomnilnika(self):
        r = self.os.html_pisma("k", "uid:7", "sl")
        html = r["html"]
        self.assertEqual((r["skritih"], r["posiljatelj"], r["prikazane"]), (1, "ana@example.test", False))
        self.assertIn('src="file://' + str(self.dom / ".cache" / "safeer-os" / "priloge"), html)
        self.assertNotIn("sled.example", html)
        self.assertNotIn("x()", html)
        self.assertIn("Content-Security-Policy", html)

    def test_izvirnik_vedno_prikazi_od_posiljatelja(self):
        self.os.nastavi_slike_od("ana@example.test", True)
        blok = lambda u: False  # noqa: E731
        with patch("core.sporocila.slike.prenesi_slike", return_value={"https://sled.example/p.gif": "file:///c/p.gif"}) as prenos:
            r = self.os.html_pisma("k", "uid:7", "sl", je_blokirano=blok)
        self.assertTrue(r["prikazane"])
        self.assertEqual(prenos.call_args.args[0], ["https://sled.example/p.gif"])
        self.assertIs(prenos.call_args.args[2], blok)                    # seznami Safeer gredo zraven
        self.assertIn('src="file:///c/p.gif"', r["html"])
        self.assertIn("ana@example.test", self.os.seznam()["slike_od"])
        self.os.nastavi_slike_od("ana@example.test", False)                # preklic v podoknu osebe
        self.assertFalse(self.os.html_pisma("k", "uid:7", "sl")["prikazane"])

    def test_storitev_hrani_html_in_priponke(self):
        s = self.os.storitev.sporocilo("k", "uid:7")
        self.assertEqual(s.html, "1.1")
        self.assertEqual(len(s.priponke), 4)
        self.assertEqual(Sporocilo.iz_slovarja(dict(s.slovar(), neznano=1)).html, "1.1")   # stanje novejse razlicice


class Predpomnilnik(unittest.TestCase):
    """Kljuc (kanal_id, mapa, UIDVALIDITY, UID, del), LRU do meje, ciscenje ob odstranitvi kanala in novi UIDVALIDITY."""

    def setUp(self):
        from core.sporocila import predpomnilnik
        self.pp = predpomnilnik
        self.d = tempfile.TemporaryDirectory()
        self.okolje = patch.dict(os.environ, {"XDG_CACHE_HOME": self.d.name})
        self.okolje.start()

    def tearDown(self):
        self.okolje.stop()
        self.d.cleanup()

    def _vnos(self, kanal="k", mapa="INBOX", uidv="100", uid="7", del_="2", vsebina=b"x" * 10, cas=None):
        v = self.pp.mapa_vnosa(kanal, mapa, uidv, uid, del_)
        f = Path(v) / "a.pdf"
        f.write_bytes(vsebina)
        if cas is not None:
            os.utime(f, (cas, cas))
        return v

    def test_kljuc(self):
        osnova = self.pp.mapa_vnosa("k", "INBOX", "100", "7", "2")
        self.assertEqual(osnova, self.pp.mapa_vnosa("k", "INBOX", "100", "7", "2"))
        for drug in (("k2", "INBOX", "100", "7", "2"), ("k", "Sent", "100", "7", "2"), ("k", "INBOX", "101", "7", "2"),
                     ("k", "INBOX", "100", "8", "2"), ("k", "INBOX", "100", "7", "2.1")):
            self.assertNotEqual(self.pp.mapa_vnosa(*drug), osnova, drug)
        self.assertTrue(osnova.startswith(os.path.join(self.d.name, "safeer-os", "priloge") + os.sep))
        self.assertNotIn("INBOX", osnova)                                        # imena so zgoscena
        self.assertEqual(os.stat(osnova).st_mode & 0o777, 0o700)
        zlo = self.pp.mapa_vnosa("../../x", "../..", "../1", "../", "..")      # nic ne uide iz korena
        self.assertTrue(os.path.realpath(zlo).startswith(os.path.realpath(self.pp.koren())))

    def test_lru_do_meje(self):
        import time as _t
        zdaj = _t.time()
        star = self._vnos(uid="1", cas=zdaj - 300)
        srednji = self._vnos(uid="2", cas=zdaj - 200)
        nov = self._vnos(uid="3", cas=zdaj - 100)
        self.pp.uporabi(str(Path(star) / "a.pdf"))                              # star je bil pravkar uporabljen
        self.assertEqual(self.pp.pocisti(najvec=25), 1)
        self.assertFalse(os.path.exists(srednji))                                # najdlje neuporabljen gre prvi
        self.assertTrue(os.path.exists(star) and os.path.exists(nov))
        self.assertEqual(self.pp.pocisti(najvec=25), 0)

    def test_odstranitev_kanala(self):
        a, b = self._vnos(kanal="a"), self._vnos(kanal="b")
        self.pp.odstrani_kanal("a")
        self.assertFalse(os.path.exists(a))
        self.assertTrue(os.path.exists(b))

    def test_nova_uidvalidity(self):
        stari, nov, druga_mapa = self._vnos(uidv="100"), self._vnos(uidv="200", uid="9"), self._vnos(mapa="Sent", uidv="100")
        self.assertEqual(self.pp.velja("k", "INBOX", "200"), 1)
        self.assertFalse(os.path.exists(stari))
        self.assertTrue(os.path.exists(nov) and os.path.exists(druga_mapa))
        self.assertEqual(self.pp.velja("k", "INBOX", ""), 0)                    # neznana: nic ne brisemo

    def test_sinhronizacija_razveljavi_staro_uidvalidity(self):
        with tempfile.TemporaryDirectory() as d:
            sp = os_sporocila.SporocilaOS(Path(d) / "sp.db", zazeni=False)
            a = MagicMock()
            a.uidvalidity_priponk, a.MAPA_PRIPONK = "200", "INBOX"
            sp.storitev.adapterji["k"] = a
            stari = self._vnos(uidv="100")
            sp._po_sinhronizaciji()
            self.assertFalse(os.path.exists(stari))
            sp.zapri()

    def test_prenos_zavrne_drugo_uidvalidity(self):
        imap, _ = _imap_s_deli({"2": b"abc"})
        imap.untagged_responses = {"UIDVALIDITY": [b"200"]}
        with patch("core.sporocila.email.imaplib.IMAP4_SSL", return_value=imap):
            a = EmailAdapter("k", "jaz@example.test", "imap.example.test", "smtp.example.test", geslo="skrivno")
            with self.assertRaisesRegex(RuntimeError, "ni_pisma"):
                a.prenesi_priponko("uid:7", {"del": "2", "kodiranje": "7bit", "uidvalidity": "100"}, lambda b: None)
            izhod = []
            a.prenesi_priponko("uid:7", {"del": "2", "kodiranje": "7bit", "uidvalidity": "200"}, izhod.append)
            self.assertEqual(b"".join(izhod), b"abc")

    def test_sinhronizacija_zapise_uidvalidity_v_priponke(self):
        imap = MagicMock()
        imap.noop.return_value = ("OK", [b""])
        imap.untagged_responses = {"UIDVALIDITY": [b"555"]}

        def uid(ukaz, *a):
            if ukaz == "search":
                return ("OK", [b"7"])
            if ukaz == "fetch":
                return ("OK", [(b"7 (UID 7 FLAGS () BODYSTRUCTURE " + GMAIL + b" BODY[]<0> {1}",
                                b"From: a@example.test\r\nSubject: x\r\n\r\nzivjo\r\n"), b")"])
            return ("OK", [b""])
        imap.uid.side_effect = uid
        with patch("core.sporocila.email.imaplib.IMAP4_SSL", return_value=imap):
            a = EmailAdapter("k", "jaz@example.test", "imap.example.test", "smtp.example.test", geslo="skrivno")
            list(a.pogovori())
        p = a.sporocila("a@example.test")[0].priponke[0]
        self.assertEqual((p["mapa"], p["uidvalidity"]), ("INBOX", "555"))
        self.assertEqual(a.uidvalidity_priponk, "555")


def _tg(rezultat):
    """Nadomestek urlopen za Telegram: zapise zahtevo in vrne {"ok": true, "result": rezultat}."""
    zahteve = []

    class Odg:
        def __init__(self, z):
            zahteve.append(z)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return json.dumps({"ok": True, "result": rezultat}).encode()
    return zahteve, (lambda z, timeout=None: Odg(z))


class PosiljanjeTelegramMatrix(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.m = Path(self.d.name)
        (self.m / "racun.pdf").write_bytes(b"%PDF-1.4 x")
        (self.m / "slika.jpg").write_bytes(b"\xff\xd8\xff jpeg")

    def tearDown(self):
        self.d.cleanup()

    def test_telegram_dokument_s_napisom_in_fotografija(self):
        from core.sporocila.telegram_bot import TelegramBotAdapter
        a = TelegramBotAdapter("t", zeton="123:abc")
        zahteve, odpri = _tg({"message_id": 9, "date": 1760000000, "document": {"file_id": "F1"}})
        with patch("core.sporocila.telegram_bot.urlopen", side_effect=odpri):
            s = a.poslji("42", "Racun v prilogi", [{"pot": str(self.m / "racun.pdf")}, {"pot": str(self.m / "slika.jpg")}])
        self.assertEqual([z.full_url.rsplit("/", 1)[1] for z in zahteve], ["sendDocument", "sendPhoto"])
        prvi = email.message_from_bytes(b"Content-Type: " + zahteve[0].headers["Content-type"].encode() + b"\r\n\r\n" + zahteve[0].data)
        polja = {d.get_param("name", header="content-disposition"): d for d in prvi.get_payload()}
        self.assertEqual(polja["caption"].get_payload(), "Racun v prilogi")       # besedilo je napis prve priloge
        self.assertEqual(polja["chat_id"].get_payload(), "42")
        self.assertEqual(polja["document"].get_filename(), "racun.pdf")
        self.assertEqual(polja["document"].get_payload(decode=True), b"%PDF-1.4 x")
        self.assertEqual([p["ime"] for p in s.priponke], ["racun.pdf", "slika.jpg"])

    def test_telegram_meja_50_mb_pred_omrezjem(self):
        from core.sporocila import telegram_bot
        velika = self.m / "velika.bin"
        with open(velika, "wb") as f:
            f.truncate(telegram_bot.NAJVEC_DATOTEKA + 1)
        a = telegram_bot.TelegramBotAdapter("t", zeton="123:abc")
        with patch("core.sporocila.telegram_bot.urlopen") as odpri, self.assertRaisesRegex(ValueError, "priloga_prevelika_kanal"):
            a.poslji("42", "x", [{"pot": str(velika)}])
        odpri.assert_not_called()

    def test_matrix_sifrirana_soba_zavrne_nicesar_ne_nalozi(self):
        from core.sporocila.matrix import MatrixAdapter
        a = MatrixAdapter("m", "https://matrix.example.test", zeton="tok")
        with patch.object(a, "_api", return_value={"algorithm": "m.megolm.v1.aes-sha2"}) as api, \
                patch("core.sporocila.matrix.urlopen") as odpri, self.assertRaisesRegex(ValueError, "priloge_e2ee"):
            a.poslji("!s:example.test", "x", [{"pot": str(self.m / "racun.pdf")}])
        odpri.assert_not_called()                                                  # nic nesifriranega na streznik
        self.assertEqual(api.call_count, 1)

    def test_matrix_nalaganje_in_dogodek(self):
        from core.sporocila.matrix import MatrixAdapter
        a = MatrixAdapter("m", "https://matrix.example.test", zeton="tok")
        napaka404 = type("E404", (Exception,), {"code": 404})
        klici = []

        def api(pot, metoda="GET", podatki=None, *ar, **kw):
            klici.append((pot, metoda, podatki))
            if "/state/m.room.encryption" in pot:
                raise napaka404()
            return {"event_id": "$e%d" % len(klici)}
        zahteve = []

        class Odg:
            def __init__(self, z):
                zahteve.append(z)
                self.z = z

            def __enter__(self):
                return self

            def __exit__(self, *x):
                return False

            def read(self):
                if "config" in self.z.full_url:
                    return json.dumps({"m.upload.size": 1000}).encode()
                return json.dumps({"content_uri": "mxc://example.test/abc"}).encode()
        with patch.object(a, "_api", side_effect=api), patch("core.sporocila.matrix.urlopen", side_effect=lambda z, timeout=None: Odg(z)):
            s = a.poslji("!s:example.test", "Glej", [{"pot": str(self.m / "racun.pdf")}])
        self.assertIn("/_matrix/client/v1/media/config", zahteve[0].full_url)
        nalaganje = zahteve[1]
        self.assertIn("/_matrix/media/v3/upload?filename=racun.pdf", nalaganje.full_url)
        self.assertEqual(nalaganje.headers["Content-type"], "application/pdf")
        self.assertEqual(nalaganje.data, b"%PDF-1.4 x")
        dogodki = [k[2] for k in klici if k[1] == "PUT"]
        self.assertEqual(dogodki[0], {"msgtype": "m.text", "body": "Glej"})
        self.assertEqual(dogodki[1]["msgtype"], "m.file")
        self.assertEqual(dogodki[1]["url"], "mxc://example.test/abc")
        self.assertEqual(dogodki[1]["info"], {"mimetype": "application/pdf", "size": 10})
        self.assertEqual(s.priponke[0]["url"], "mxc://example.test/abc")
        (self.m / "vecja.bin").write_bytes(b"x" * 1001)                           # meja iz /media/config (1000 B)
        with patch.object(a, "_api", side_effect=api), self.assertRaisesRegex(ValueError, "priloga_prevelika_kanal"):
            a.poslji("!s:example.test", "", [{"pot": str(self.m / "vecja.bin")}])

    def test_gumb_prilozi_samo_kjer_kanal_zna(self):
        from core.sporocila.chatwoot import ChatwootAdapter
        from core.sporocila.matrix import MatrixAdapter
        from core.sporocila.telegram_bot import TelegramBotAdapter
        sp = os_sporocila.SporocilaOS(self.m / "sp.db", zazeni=False)
        for kid, vrsta, a in (("e", "email", EmailAdapter("e", "a@example.test", "i", "s")),
                              ("t", "telegram_bot", TelegramBotAdapter("t")),
                              ("m", "matrix", MatrixAdapter("m", "https://x.example.test")),
                              ("c", "chatwoot", ChatwootAdapter("c", "https://x.example.test", 1))):
            sp.storitev.registriraj(Kanal(kid, vrsta, kid), a, {})
        kanali = {k["id"]: k["priloge"] for k in sp.seznam()["kanali"]}
        self.assertEqual(kanali, {"e": True, "t": True, "m": True, "c": False})
        with self.assertRaisesRegex(ValueError, "priloge_ni_podprto"):
            sp._priloge("c", ["/x"])
        sp.zapri()


def _png(sirina: int, visina: int) -> bytes:
    """Veljaven PNG brez Pillow (enobarvna slika)."""
    import struct
    import zlib

    def kos(vrsta, podatki):
        return struct.pack(">I", len(podatki)) + vrsta + podatki + struct.pack(">I", zlib.crc32(vrsta + podatki))
    surovo = b"".join(b"\x00" + b"\xc8\x0a\x0a" * sirina for _ in range(visina))
    return (b"\x89PNG\r\n\x1a\n" + kos(b"IHDR", struct.pack(">IIBBBBB", sirina, visina, 8, 2, 0, 0, 0)) +
            kos(b"IDAT", zlib.compress(surovo)) + kos(b"IEND", b""))


class SlikeSSpleta(unittest.TestCase):
    """Oddaljene slike v HTML pismih: privzeto skrite; ob prikazu prek zascite Safeer (core/sporocila/slike.py)."""

    def setUp(self):
        from core.sporocila import slike
        self.sl = slike
        self.d = tempfile.TemporaryDirectory()
        self.m = self.d.name

    def tearDown(self):
        self.d.cleanup()

    @staticmethod
    def _razresi(gost, _p):
        return [(0, 0, 0, "", ({"lan.example": "192.168.1.1", "zanka.example": "127.0.0.1"}.get(gost, "93.184.216.34"), 0))]

    def _odpri(self, tip="image/png", vsebina=None, preusmeritve=None):
        """Nadomestek povezave (slike.povezi): zapise ime, IP, vrata in glave; preusmeritve: {pot: Location}."""
        zahteve = []
        if vsebina is None:
            vsebina = _png(40, 30)

        class Odg:
            def __init__(self, status, glave):
                self.status, self._glave = status, glave

            def getheader(self, ime, privzeto=None):
                return self._glave.get(ime, privzeto)

            def read(self, n=-1):
                return vsebina

        class Pov:
            def __init__(self, ime, ip, vrata, https, cas):
                self.z = {"ime": ime, "ip": ip, "vrata": vrata, "https": https}
                zahteve.append(self.z)

            def request(self, metoda, pot, headers=None):
                self.z.update(metoda=metoda, pot=pot, glave=dict(headers or {}))

            def getresponse(self):
                if preusmeritve and self.z["pot"] in preusmeritve:
                    return Odg(302, {"Location": preusmeritve[self.z["pot"]]})
                return Odg(200, {"Content-Type": tip})

            def close(self):
                pass
        return zahteve, Pov

    def test_sledilci_in_domace_omrezje(self):
        self.assertTrue(self.sl.je_sledilec("https://x.list-manage.com/track/open.php?u=1"))
        self.assertTrue(self.sl.je_sledilec("https://mailtrack.io/trace/mail/abc.png"))
        self.assertTrue(self.sl.je_sledilec("https://cdn.example.test/a.png", lambda u: "cdn.example" in u))  # seznami Safeer
        self.assertFalse(self.sl.je_sledilec("https://cdn.example.test/logo.png"))
        self.assertFalse(self.sl.javni_gostitelj("lan.example", self._razresi))
        self.assertFalse(self.sl.javni_gostitelj("zanka.example", self._razresi))
        self.assertTrue(self.sl.javni_gostitelj("cdn.example.test", self._razresi))

    def test_prenos_brez_piskotkov_in_referer(self):
        zahteve, odpri = self._odpri()
        pot = self.sl.prenesi_sliko("https://cdn.example.test/foto.png", self.m, self._razresi, odpri)
        self.assertTrue(pot.endswith(".png") and os.path.getsize(pot) > 0)
        self.assertEqual(os.stat(pot).st_mode & 0o777, 0o600)
        glave = {k.lower() for k in zahteve[0]["glave"]}
        self.assertNotIn("referer", glave)
        self.assertNotIn("cookie", glave)
        self.assertEqual(self.sl.prenesi_sliko("https://cdn.example.test/foto.png", self.m, self._razresi, odpri), pot)
        self.assertEqual(len(zahteve), 1)                                     # drugic iz predpomnilnika

    def test_blokirano(self):
        _z, piksel = self._odpri("image/gif", b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04"
                                 b"\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;")
        self.assertEqual(self.sl.prenesi_sliko("https://a.example.test/x.gif", self.m, self._razresi, piksel), "")
        _z, piksel = self._odpri("image/png", _png(1, 1))
        self.assertEqual(self.sl.prenesi_sliko("https://a.example.test/x.gif", self.m, self._razresi, piksel), "")
        _z, html = self._odpri("text/html", b"<html>")
        self.assertEqual(self.sl.prenesi_sliko("https://a.example.test/y", self.m, self._razresi, html), "")
        zahteve, odpri = self._odpri()
        self.assertEqual(self.sl.prenesi_sliko("http://lan.example/router.png", self.m, self._razresi, odpri), "")
        self.assertEqual(self.sl.prenesi_sliko("file:///etc/passwd", self.m, self._razresi, odpri), "")
        self.assertEqual(self.sl.prenesi_sliko("https://u:p@cdn.example.test/a.png", self.m, self._razresi, odpri), "")
        self.assertEqual(zahteve, [])

    def test_dns_rebinding_poveze_na_preverjeni_naslov(self):
        """Lazni razresevalnik: prvic javni naslov, nato 192.168.x - povezava gre na prvega ali nikamor."""
        klici = []

        def razresi(gost, _p):
            klici.append(gost)
            return [(0, 0, 0, "", ("93.184.216.34" if len(klici) == 1 else "192.168.1.1", 0))]
        zahteve, povezi = self._odpri()
        pot = self.sl.prenesi_sliko("https://rebind.example.test/a.png", self.m, razresi, povezi)
        self.assertTrue(pot)
        self.assertEqual(klici, ["rebind.example.test"])                        # ime razreseno samo enkrat
        self.assertEqual((zahteve[0]["ime"], zahteve[0]["ip"], zahteve[0]["vrata"], zahteve[0]["https"]),
                         ("rebind.example.test", "93.184.216.34", 443, True))
        # Mesan odgovor (javni + zasebni naslov): zavrnjeno, brez povezave.
        zahteve2, povezi2 = self._odpri()
        mesano = lambda g, p: [(0, 0, 0, "", ("93.184.216.34", 0)), (0, 0, 0, "", ("10.0.0.1", 0))]  # noqa: E731
        self.assertEqual(self.sl.prenesi_sliko("https://mesano.example.test/a.png", self.m, mesano, povezi2), "")
        self.assertEqual(zahteve2, [])

    def test_preusmeritev_v_domace_omrezje_zavrnjena(self):
        zahteve, povezi = self._odpri(preusmeritve={"/a.png": "http://lan.example/router.png"})
        self.assertEqual(self.sl.prenesi_sliko("https://cdn.example.test/a.png", self.m, self._razresi, povezi), "")
        self.assertEqual([z["ime"] for z in zahteve], ["cdn.example.test"])     # na lan.example ni povezave
        zahteve, povezi = self._odpri(preusmeritve={"/b.png": "/c.png"})
        self.assertTrue(self.sl.prenesi_sliko("https://cdn.example.test/b.png", self.m, self._razresi, povezi))
        self.assertEqual([z["pot"] for z in zahteve], ["/b.png", "/c.png"])

    def test_s_posrednikom_ne_mimo_njega(self):
        """Nastavljen posrednik: slika gre prek njega (ime razresi posrednik), nikoli neposredno; zascita domacega
        omrezja velja za ime pred zahtevo."""
        zahteve, povezi = self._odpri()
        prek = []

        def povezi_prek(posrednik, ime, vrata, https, cas):
            prek.append((posrednik, ime, vrata, https))
            return povezi(ime, "", vrata, https, cas), False
        posrednik = lambda url: "socks5h://127.0.0.1:9050"  # noqa: E731
        pot = self.sl.prenesi_sliko("https://cdn.example.test/p.png", self.m, self._razresi, povezi=lambda *a: self.fail("mimo"),
                                    posrednik=posrednik, povezi_prek=povezi_prek)
        self.assertTrue(pot)
        self.assertEqual(prek, [("socks5h://127.0.0.1:9050", "cdn.example.test", 443, True)])
        self.assertNotIn("referer", {k.lower() for k in zahteve[0]["glave"]})
        self.assertEqual(self.sl.prenesi_sliko("http://lan.example/r.png", self.m, self._razresi,
                                               posrednik=posrednik, povezi_prek=povezi_prek), "")
        self.assertEqual(len(prek), 1)                                         # domace omrezje: niti do posrednika
        # Posrednik, ki ga ne znamo (SOCKS4): slike ni - in tudi neposredne povezave ne.
        self.assertEqual(self.sl.prenesi_sliko("https://cdn.example.test/q.png", self.m, self._razresi,
                                               povezi=lambda *a: self.fail("mimo"), posrednik=lambda u: "socks4://p:1080"), "")

    def _vticnica(self, odgovori):
        poslano = bytearray()

        class V:
            def __init__(self):
                self.ostanek = b"".join(odgovori)

            def sendall(self, b):
                poslano.extend(b)

            def recv(self, n):
                kos, self.ostanek = self.ostanek[:n], self.ostanek[n:]
                return kos

            def close(self):
                pass
        naslovi = []

        def odpri(naslov, cas):
            naslovi.append(naslov)
            return V()
        return poslano, naslovi, odpri

    def test_http_connect_tunel(self):
        poslano, naslovi, odpri = self._vticnica([b"HTTP/1.1 200 Connection established\r\n\r\n"])
        pov, absolutno = self.sl._povezava_prek("http://upo:ge%40slo@proxy.example:3128", "cdn.example.test", 443, True, 5, odpri)
        self.assertFalse(absolutno)
        self.assertEqual(pov.host, "cdn.example.test")                          # TLS do slike z imenom (SNI)
        pov._create_connection(("cdn.example.test", 443), 5)
        self.assertEqual(naslovi, [("proxy.example", 3128)])
        self.assertTrue(bytes(poslano).startswith(b"CONNECT cdn.example.test:443 HTTP/1.1\r\n"))
        import base64
        self.assertIn(b"Proxy-Authorization: Basic " + base64.b64encode(b"upo:ge@slo"), bytes(poslano))
        poslano, _n, odpri = self._vticnica([b"HTTP/1.1 403 Forbidden\r\n\r\n"])
        pov, _a = self.sl._povezava_prek("http://proxy.example:3128", "cdn.example.test", 443, True, 5, odpri)
        with self.assertRaises(OSError):
            pov._create_connection(("cdn.example.test", 443), 5)

    def test_socks5_ime_razresi_posrednik(self):
        poslano, naslovi, odpri = self._vticnica([b"\x05\x00", b"\x05\x00\x00\x01\x01\x02\x03\x04\x01\xbb"])
        pov, absolutno = self.sl._povezava_prek("socks5h://127.0.0.1:9050", "cdn.example.test", 443, True, 5, odpri)
        pov._create_connection(("cdn.example.test", 443), 5)
        self.assertEqual(naslovi, [("127.0.0.1", 9050)])
        self.assertEqual(bytes(poslano), b"\x05\x01\x00" + b"\x05\x01\x00\x03\x10cdn.example.test\x01\xbb")

    def test_http_posrednik_http_slika_absolutna_pot(self):
        _p, _n, odpri = self._vticnica([])
        pov, absolutno = self.sl._povezava_prek("http://a:b@proxy.example:8080", "cdn.example.test", 80, False, 5, odpri)
        self.assertTrue(absolutno)
        self.assertEqual(pov.host, "proxy.example")
        self.assertIn("Proxy-Authorization", pov._safeer_glave)

    def test_prava_povezava_ip_in_ime_za_sni(self):
        """http.client: vticnica na preverjeni IP, ime ostane za Host, SNI in preverjanje potrdila."""
        pov = self.sl._povezava("cdn.example.test", "93.184.216.34", 443, True, 5)
        self.assertEqual(pov.host, "cdn.example.test")
        with patch("core.sporocila.slike.socket.create_connection", return_value="vticnica") as cc:
            self.assertEqual(pov._create_connection(("cdn.example.test", 443), 5), "vticnica")
        self.assertEqual(cc.call_args.args[0], ("93.184.216.34", 443))
        self.assertTrue(pov._context.check_hostname)

    def test_varen_html_z_oddaljenimi(self):
        from core import predogled_datotek as pd
        vir = ('<img src="https://cdn.example.test/foto.png"><img src="https://sled.example.test/p.gif" width="1" height="1">'
               '<img src="https://cdn.example.test/blok.png" style="width:1px;height:1px">')
        self.assertEqual(pd.oddaljene_slike(vir), ["https://cdn.example.test/foto.png"])   # piksli niso niti kandidati
        html, skrite = pd.varen_html(vir)
        self.assertEqual((skrite, "https://" in html), (1, False))
        html, skrite = pd.varen_html(vir, oddaljene={"https://cdn.example.test/foto.png": "file:///c/f.png"})
        self.assertIn('src="file:///c/f.png"', html)
        self.assertEqual(skrite, 0)

    def test_vedno_od_posiljatelja(self):
        v = self.sl.DovoljeniPosiljatelji(os.path.join(self.m, "s.json"))
        self.assertFalse(v.dovoljen("Ana@Example.test"))
        self.assertEqual(v.nastavi("Ana@Example.test", True), ["ana@example.test"])
        self.assertTrue(self.sl.DovoljeniPosiljatelji(os.path.join(self.m, "s.json")).dovoljen("ana@example.test"))
        self.assertEqual(os.stat(os.path.join(self.m, "s.json")).st_mode & 0o777, 0o600)
        self.assertEqual(v.nastavi("ana@example.test", False), [])
        with self.assertRaises(ValueError):
            v.nastavi("ni-naslov", True)


class StaraBaza(unittest.TestCase):
    def test_baza_brez_stolpca_html_se_nadgradi(self):
        import sqlite3
        with tempfile.TemporaryDirectory() as d:
            pot = Path(d) / "sp.db"
            db = sqlite3.connect(pot)
            db.execute("CREATE TABLE sporocila(id TEXT,pogovor_id TEXT,kanal_id TEXT,smer TEXT,besedilo TEXT,cas TEXT,"
                       "priponke TEXT,stanje TEXT,PRIMARY KEY(id,kanal_id))")
            db.execute("INSERT INTO sporocila VALUES('1','p','k','noter','b','c','[]','prejeto')")
            db.commit()
            db.close()
            st = StoritevSporocil(pot)
            self.assertEqual(st.sporocila("k", "p")[0].html, "")
            st._shrani_sporocilo("k", Sporocilo("2", "p", "noter", "b", "d", [], "prejeto", "2"))
            self.assertEqual(st.sporocilo("k", "2").html, "2")
            st.zapri()


if __name__ == "__main__":
    unittest.main()
