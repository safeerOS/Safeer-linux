"""Zaslon racunalnika na televizorju (core/link_zaslon.py): dovoljenje, ukaz, seja, zeton."""
import os
import socket
import ssl
import sys
import threading
import unittest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOREN)

from core import link_daljinec, link_zaslon  # noqa: E402


class Ukaz(unittest.TestCase):
    def test_strojno_kodiranje_brez_bitrate(self):
        """Intelov nizkoenergijski kodirnik zna samo CQP; z -b:v se sploh ne odpre."""
        u = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 30, "6M", "/dev/dri/renderD128", qp=24)
        self.assertIn("h264_vaapi", u)
        self.assertEqual(u[u.index("-profile:v") + 1], "high")   # boljse za drobno besedilo
        self.assertIn("-rc_mode", u)
        self.assertEqual(u[u.index("-rc_mode") + 1], "CQP")
        self.assertEqual(u[u.index("-qp") + 1], "24")
        self.assertNotIn("-b:v", u)
        # Varcnega nacina ne vsiljujemo: kjer obstaja boljsa pot, naj jo gonilnik izbere sam.
        self.assertNotIn("-low_power", u)
        self.assertEqual(u[-1], "-")

    def test_programsko_kodiranje_brez_zamika(self):
        u = link_zaslon.ukaz_ffmpeg(":0", 1280, 720, 1920, 1080, 24, "3M", None)
        self.assertIn("libx264", u)
        self.assertEqual(u[u.index("-tune") + 1], "zerolatency")
        self.assertEqual(u[u.index("-b:v") + 1], "3M")
        self.assertEqual(u[u.index("-bf") + 1], "0")      # brez B-slik: manjsa zakasnitev

    def test_brez_skaliranja_kadar_je_slika_ze_prava(self):
        """Prevzorcenje zmehca besedilo; kadar je zaslon ze prave velikosti, ga ne delamo."""
        enako = link_zaslon.ukaz_ffmpeg(":0", 1920, 1080, 1920, 1080, 30, "8M", "/dev/dri/renderD128")
        self.assertNotIn("scale=", " ".join(enako))
        manjse = link_zaslon.ukaz_ffmpeg(":0", 1280, 720, 1920, 1080, 30, "4M", "/dev/dri/renderD128")
        self.assertIn("scale=1280:720", " ".join(manjse))

    def test_kakovosti_so_stevilcno_smiselne(self):
        """Visja kakovost = nizji qp; imena so del dogovora s televizorjem."""
        qp = [link_zaslon.KAKOVOSTI[k]["qp"] for k in ("nizka", "srednja", "visoka", "najvisja")]
        self.assertEqual(qp, sorted(qp, reverse=True))
        self.assertIn(link_zaslon.PRIVZETA_KAKOVOST, link_zaslon.KAKOVOSTI)
        # Privzeto je najboljse, kar zmoremo: uporabnik kakovosti ne izbira.
        self.assertEqual(link_zaslon.PRIVZETA_KAKOVOST, "najvisja")
        self.assertEqual(min(k["qp"] for k in link_zaslon.KAKOVOSTI.values()),
                         link_zaslon.KAKOVOSTI[link_zaslon.PRIVZETA_KAKOVOST]["qp"])

    def test_slika_ohrani_razmerje_in_ne_povecuje(self):
        self.assertEqual(link_zaslon.Zaslon._prilagodi((3840, 2160), 1920, 1080), (1920, 1080))
        self.assertEqual(link_zaslon.Zaslon._prilagodi((1366, 768), 1920, 1080), (1366, 768))
        s, v = link_zaslon.Zaslon._prilagodi((1920, 1200), 1920, 1080)
        self.assertEqual((s, v), (1728, 1080))
        self.assertEqual((s % 2, v % 2), (0, 0))


class Dovoljenje(unittest.TestCase):
    def test_privzeto_izklopljeno(self):
        z = link_zaslon.Zaslon()
        self.assertFalse(z.vklopljeno)
        self.assertFalse(z.na_voljo()["dovoljeno"])
        with self.assertRaises(RuntimeError):
            z.zacni("tv-test")

    def test_ukaz_brez_dovoljenja_zavrnjen(self):
        z = link_zaslon.Zaslon()
        izidi = []
        link_daljinec.izvedi_control("screen.start", {}, lambda u: None, izidi.append, zaslon=z)
        self.assertFalse(izidi[0]["ok"])
        self.assertEqual(izidi[0]["code"], "ni_dovoljeno")

    def test_brez_modula_razumljiva_napaka(self):
        izidi = []
        link_daljinec.izvedi_control("screen.start", {}, lambda u: None, izidi.append)
        self.assertFalse(izidi[0]["ok"])
        self.assertEqual(izidi[0]["code"], "ni_na_racunalniku")

    def test_stanje_je_vedno_na_voljo(self):
        z = link_zaslon.Zaslon()
        izidi = []
        link_daljinec.izvedi_control("screen.status", {}, lambda u: None, izidi.append, zaslon=z)
        self.assertTrue(izidi[0]["ok"])
        self.assertFalse(izidi[0]["data"]["dovoljeno"])
        self.assertFalse(izidi[0]["data"]["tece"])

    def test_izklop_konca_sejo(self):
        z = link_zaslon.Zaslon()
        z.nastavi(True)
        self.assertTrue(z.vklopljeno)
        z.nastavi(False)
        self.assertFalse(z.vklopljeno)
        self.assertFalse(z.stanje()["tece"])

    def test_stanje_v_zmoznostih_samo_z_dovoljenjem(self):
        z = link_zaslon.Zaslon()
        izidi = []
        link_daljinec.izvedi_control("status", {}, lambda u: None, izidi.append, zaslon=z)
        self.assertNotIn("screen.start", izidi[0]["data"]["actions"])
        z.vklopljeno = True
        izidi.clear()
        link_daljinec.izvedi_control("status", {}, lambda u: None, izidi.append, zaslon=z)
        self.assertIn("screen.start", izidi[0]["data"]["actions"])


class Seja(unittest.TestCase):
    """Seja brez pravega zaslona: preverimo pozdrav, zeton in ciscenje, ne slike."""

    def setUp(self):
        self.z = link_zaslon.Zaslon(vklopljeno=True, ffmpeg="/bin/true")
        os.environ.setdefault("DISPLAY", ":0")

    def tearDown(self):
        self.z.ustavi()

    def test_napacen_zeton_ne_dobi_nicesar(self):
        seja = self.z.zacni("tv-test")
        self.assertIn("port", seja)
        self.assertEqual(len(seja["fp"]), 64)
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        s = ctx.wrap_socket(socket.create_connection(("127.0.0.1", seja["port"]), timeout=5))
        s.sendall(b"SAFEER-ZASLON napacen-zeton\n")
        self.assertEqual(s.recv(64), b"")     # povezava se zapre brez odgovora
        s.close()

    def test_pravi_zeton_dobi_glavo_slike(self):
        seja = self.z.zacni("tv-test")
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        s = ctx.wrap_socket(socket.create_connection(("127.0.0.1", seja["port"]), timeout=5))
        s.sendall(("SAFEER-ZASLON %s\n" % seja["token"]).encode())
        glava = b""
        while not glava.endswith(b"\n") and len(glava) < 200:
            k = s.recv(1)
            if not k:
                break
            glava += k
        self.assertIn(b'"w"', glava)
        self.assertIn(b'"fps"', glava)
        s.close()

    def test_ustavi_pozabi_zeton(self):
        """Po koncu seje stari zeton ne velja vec - tudi ce vticnica se ni docela sproscena."""
        seja = self.z.zacni("tv-test")
        self.z.ustavi()
        self.assertEqual(self.z.vrata, 0)
        self.assertEqual(self.z._zeton, "")
        try:
            s = socket.create_connection(("127.0.0.1", seja["port"]), timeout=2)
        except OSError:
            return                                   # vrata zaprta: se bolje
        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            o = ctx.wrap_socket(s)
            o.settimeout(3)
            o.sendall(("SAFEER-ZASLON %s\n" % seja["token"]).encode())
            self.assertEqual(o.recv(64), b"")        # nicesar ne dobi
            o.close()
        except (OSError, ssl.SSLError):
            pass                                     # povezava pade: prav tako v redu


if __name__ == "__main__":
    unittest.main(verbosity=2)


class Okvirji(unittest.TestCase):
    """Pretok v2: slika in zvok po isti povezavi, vsak v svojih okvirjih."""

    def test_zvok_je_surov_pcm_v_majhnih_koscih(self):
        u = link_zaslon.ukaz_zvok("izhod.monitor")
        self.assertIn("pulse", u)
        self.assertEqual(u[u.index("-i") + 1], "izhod.monitor")
        self.assertEqual(u[u.index("-f", u.index("-ar")) + 1], "s16le")
        self.assertEqual(u[u.index("-ar") + 1], str(link_zaslon.ZVOK_HZ))
        # 1920 bajtov = 10 ms stereo 48 kHz: zvok ne sme cakati za veliko sliko
        self.assertEqual(u[u.index("-fragment_size") + 1], "1920")

    def test_vrsti_okvirjev_sta_razlicni(self):
        self.assertNotEqual(link_zaslon.OKVIR_SLIKA, link_zaslon.OKVIR_ZVOK)

    def test_glava_pove_razlicico_in_zvok(self):
        z = link_zaslon.Zaslon(vklopljeno=True, ffmpeg="/bin/true")
        os.environ.setdefault("DISPLAY", ":0")
        seja = z.zacni("tv-test")
        try:
            self.assertEqual(seja["v"], 2)
            self.assertIn("input", seja)
            if seja["audio"] is not None:
                self.assertEqual(seja["audio"]["format"], "s16le")
        finally:
            z.ustavi()
