"""Priponke v Sporocilih (lastnik, 15. 10. 2026: »Sporocila morajo znati zaznati priloge in jih tudi prenesti … Uporabnik
ne sme pogresati na primer Gmail ali Outlook«).

Brez omrezja: imaplib in smtplib sta nadomescena. Zgradbe BODYSTRUCTURE so oblike, kot jih vracajo Gmail, Outlook
(Exchange Online) in Dovecot (RFC 3501 7.4.2), z gnezdenimi multipart, slikami v vrstici, imeni RFC 2231 / RFC 2047 in
posredovanim pismom.
"""
import base64
import email
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
        html = self.os.html_pisma("k", "uid:7", "sl")
        self.assertIn('src="file://' + str(self.dom / ".cache" / "safeer-os" / "priloge"), html)
        self.assertNotIn("sled.example", html)
        self.assertNotIn("x()", html)
        self.assertIn("Content-Security-Policy", html)

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
