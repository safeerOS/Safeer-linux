"""Katalog spletnih klepetov (core/spletni_klepeti.py): en vir za Sporocila in stranske plosce brskalnikov, stevilo
neprebranih iz naslova strani, preverba lastnega naslova, shramba kanalov, preselitev messenger.com (15. 10. 2026)."""
import ast
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from core import spletni_klepeti as sk
from core.sporocila import ponudniki

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JEZIKI = ("sl", "en", "de", "es", "fr", "it")
DOMENA = re.compile(r"[a-z0-9-]+\.(?:com|net|org|io|me|app|ch|si|chat)\b")


class _Shramba(dict):
    """Nadomestek ConfigManagerja (get/set)."""

    def set(self, k, v):
        self[k] = json.loads(json.dumps(v))   # kot zapis v JSON: brez skupnih predmetov


class Katalog(unittest.TestCase):
    def test_vnosi_so_veljavni(self):
        idji = [k["id"] for k in sk.KATALOG]
        self.assertEqual(len(idji), len(set(idji)), "id v katalogu morajo biti enolicni")
        for k in sk.KATALOG:
            self.assertTrue(k["ime"] and k["vrsta"] in (sk.KLEPET, sk.POSTA), k)
            for polje in ("splet", "prenos"):
                self.assertTrue(not k.get(polje) or k[polje].startswith("https://"), (k["id"], polje))
                if k.get(polje):
                    self.assertEqual(sk.preveri_naslov(k[polje]).split("://", 1)[1].split("/", 1)[0],
                                     k[polje].split("://", 1)[1].split("/", 1)[0])
            if k.get("program"):
                p = k["program"]
                self.assertTrue(p.get("razredi") and (p.get("vnosi") or p.get("ukazi")), k["id"])
                self.assertTrue(k["prenos"], "namizni program brez spletnega odjemalca mora imeti stran za prenos")
            elif not k.get("splet"):
                self.assertIn(k.get("razlog"), sk.RAZLOGI["sl"], "ne-vdeljiv vnos pove, zakaj")
                self.assertTrue(k["prenos"], k["id"])

    def test_izmerjeni_katalog_lastnika(self):
        # 15. 10. 2026 (testni PC, WebKitGTK 2.54.1): naslovi, ki se nalozijo do prijave ali kode QR.
        pricakovano = {"messenger": "https://www.facebook.com/messages/", "whatsapp": "https://web.whatsapp.com/",
                       "telegram": "https://web.telegram.org/a/", "google-messages": "https://messages.google.com/web/",
                       "instagram": "https://www.instagram.com/direct/inbox/", "discord": "https://discord.com/app",
                       "slack": "https://app.slack.com/client", "teams-osebni": "https://teams.live.com/",
                       "teams": "https://teams.microsoft.com/v2/", "google-chat": "https://chat.google.com/",
                       "element": "https://app.element.io/", "snapchat": "https://www.snapchat.com/web",
                       "x": "https://x.com/i/chat", "linkedin": "https://www.linkedin.com/messaging/",
                       "threema": "https://web.threema.com/", "wechat": "https://web.wechat.com/",
                       "gmail": "https://mail.google.com/mail/", "outlook": "https://outlook.live.com/mail/",
                       "proton": "https://mail.proton.me/", "tuta": "https://app.tuta.com/"}
        for kid, url in pricakovano.items():
            self.assertEqual(sk.po_id(kid)["splet"], url, kid)
        for kid in ("wire", "line"):
            self.assertFalse(sk.vdelljiv(sk.po_id(kid)), kid)
        for kid in ("signal", "viber"):
            self.assertTrue(sk.je_program(sk.po_id(kid)), kid)
        self.assertNotIn("messenger.com", json.dumps(sk.KATALOG))

    def test_prevodi_razlogov_in_pripisov(self):
        for slovar in (sk.RAZLOGI, sk.PRIPISI):
            self.assertEqual(set(slovar), set(JEZIKI))
            for j in JEZIKI:
                self.assertEqual(set(slovar[j]), set(slovar["sl"]), j)
        self.assertEqual(sk.ime(sk.po_id("teams-osebni"), "sl"), "Microsoft Teams (osebni)")
        self.assertEqual(sk.ime(sk.po_id("teams"), "en"), "Microsoft Teams (work or school)")
        vmesnik = sk.za_vmesnik("de")
        self.assertTrue(next(v for v in vmesnik if v["id"] == "wire")["razlog"])
        self.assertEqual(next(v for v in vmesnik if v["id"] == "telegram")["razlog"], "")

    def test_brez_kode_za_imenovane_strani(self):
        """CONTRIBUTING.md »brez receptov«: domene so samo v podatkih (KATALOG, PRESELJENI), nikjer v pogojih ali kodi
        novih modulov vgrajenih kanalov."""
        moduli = ("spletni_klepeti.py", "os_kanali_sporocil.py", "namizni_programi.py", "znacke_programov.py",
                  "vstavi_okno.py", "stranska_plosca.py")
        for ime in moduli:
            drevo = ast.parse(open(os.path.join(KOREN, "core", ime), encoding="utf-8").read())
            podatki = set()
            for v in ast.walk(drevo):
                if isinstance(v, (ast.Assign, ast.AnnAssign)):
                    cilji = v.targets if isinstance(v, ast.Assign) else [v.target]
                    if any(isinstance(c, ast.Name) and c.id in ("KATALOG", "PRESELJENI") for c in cilji):
                        podatki |= {id(x) for x in ast.walk(v)}
            for v in ast.walk(drevo):
                if isinstance(v, ast.Constant) and isinstance(v.value, str) and id(v) not in podatki:
                    besedilo = v.value
                    # docstringi in komentarji v nizih smejo omenjati storitve; pogoji in naslovi v kodi ne
                    if len(besedilo) < 120 and DOMENA.search(besedilo) and "://" in besedilo:
                        self.fail("%s: naslov storitve v kodi: %r" % (ime, besedilo))
                if isinstance(v, ast.Compare):
                    for c in [v.left] + list(v.comparators):
                        if isinstance(c, ast.Constant) and isinstance(c.value, str) and DOMENA.search(c.value):
                            self.fail("%s: primerjava z imenom gostitelja: %r" % (ime, c.value))


class Neprebrano(unittest.TestCase):
    def test_vzorci(self):
        primeri = {
            "(3) WhatsApp": 3, "[12] Element": 12, "(99+) Facebook": 99, " (7)  Telegram": 7,
            "4 · Klepet": 4, "7 - Pošta": 7, "Inbox (5) - ime@example.org - Gmail": 5, "Klepet (2)": 2,
            "(2) Chat | Microsoft Teams": 2, "* Slack | splošno": 1, "• Nekaj": 1, "! Omemba": 1,
        }
        for naslov, n in primeri.items():
            self.assertEqual(sk.neprebrano(naslov), n, naslov)

    def test_brez_vzorca_je_nic(self):
        for naslov in ("", None, "WhatsApp", "Telegram Web", "Srečanje (2026) - Teams", "Zoom 5.0", "2048 igra",
                       "Inbox - ime@example.org - Gmail", "Klepet | (3)", "x" * 2000, 42):
            self.assertEqual(sk.neprebrano(naslov), 0, naslov)

    def test_letnica_spredaj_ni_stevilo(self):
        # Pregled naloge 45 (28. 10. 2026): golo stevilo spredaj z locilom je najvec trimestno.
        self.assertEqual(sk.neprebrano("2024 - Koledar"), 0)
        self.assertEqual(sk.neprebrano("12345 · Klepet"), 0)
        self.assertEqual(sk.neprebrano("999 · Klepet"), 999)

    def test_meja(self):
        self.assertEqual(sk.neprebrano("(123456) X"), 0)
        self.assertEqual(sk.neprebrano("(99999) X"), sk.NAJVEC_NEPREBRANIH)


class LastenNaslov(unittest.TestCase):
    def test_veljavni(self):
        self.assertEqual(sk.preveri_naslov("https://chat.example.org"), "https://chat.example.org/")
        self.assertEqual(sk.preveri_naslov("chat.example.org/team"), "https://chat.example.org/team")
        self.assertEqual(sk.preveri_naslov("HTTPS://Chat.Example.ORG:8443/x?y=1#z"), "https://chat.example.org:8443/x?y=1#z")
        self.assertEqual(sk.preveri_naslov("https://192.168.1.5/"), "https://192.168.1.5/")
        idn = sk.preveri_naslov("https://čevapčiči.si/")
        self.assertEqual(idn, "https://" + "čevapčiči.si".encode("idna").decode() + "/")
        # homograf (cirilski »а« namesto latinskega »a«): shranjen in prikazan kot punycode, ne kot »apple.com«
        self.assertEqual(sk.preveri_naslov("https://аpple.com/"), "https://xn--pple-43d.com/")
        self.assertEqual(sk.ime_iz_naslova(sk.preveri_naslov("https://аpple.com/")), "xn--pple-43d.com")

    def test_neveljavni(self):
        primeri = {"": "prazno", "   ": "prazno", "http://chat.example.org": "https", "ftp://x.org": "https",
                   "javascript:alert(1)": "https", "file:///etc/passwd": "https",
                   "https://ime:geslo@chat.example.org": "poverilnice", "https://ime@chat.example.org": "poverilnice",
                   "https://": "gostitelj", "https://chat example.org": "gostitelj", "https://a\nb.org": "gostitelj",
                   "https://-x-.org": "gostitelj", "https://x.org:99999/": "gostitelj",
                   "https://x.org/" + "a" * 3000: "dolzina",
                   "data:text/html,<script>alert(1)</script>": "https", "JaVaScRiPt:alert(1)": "https",
                   "javascript://chat.example.org/%0aalert(1)": "https", "https://evil.example\\@chat.example.org": "poverilnice"}
        for url, koda in primeri.items():
            with self.assertRaises(sk.NeveljavenNaslov, msg=url) as e:
                sk.preveri_naslov(url)
            self.assertEqual(e.exception.args[0], koda, url)


class Shramba(unittest.TestCase):
    def setUp(self):
        self.s = _Shramba()
        self.k = sk.Kanali(self.s)

    def test_dodaj_iz_kataloga_in_lasten(self):
        a = self.k.dodaj(katalog="whatsapp", jezik="sl")
        self.assertEqual((a["id"], a["url"], a["vklopljen"], a["neprebrano"]), ("whatsapp", "https://web.whatsapp.com/", True, 0))
        b = self.k.dodaj(katalog="whatsapp")           # drugi racun iste storitve: svoj id
        self.assertNotEqual(b["id"], "whatsapp")
        c = self.k.dodaj(url="chat.example.org", ime_kanala="  Ekipa  ")
        self.assertEqual((c["ime"], c["url"]), ("Ekipa", "https://chat.example.org/"))
        self.assertEqual([x["id"] for x in self.k.seznam()], ["whatsapp", b["id"], c["id"]])
        with self.assertRaises(ValueError):
            self.k.dodaj(katalog="wire")               # ni ga mogoce vdelati
        with self.assertRaises(sk.NeveljavenNaslov):
            self.k.dodaj(url="http://x.org")

    def test_urejanje(self):
        for kid in ("telegram", "discord", "slack"):
            self.k.dodaj(katalog=kid)
        self.k.preimenuj("discord", "  Igre   in   klepet ")
        self.assertEqual(self.k.najdi("discord")["ime"], "Igre in klepet")
        with self.assertRaises(ValueError):
            self.k.preimenuj("discord", "   ")
        self.k.premakni("slack", -1)
        self.assertEqual([x["id"] for x in self.k.seznam()], ["telegram", "slack", "discord"])
        self.k.premakni("telegram", -1)           # prvi ostane prvi
        self.assertEqual(self.k.seznam()[0]["id"], "telegram")
        self.k.vklopi("slack", False)
        self.assertFalse(self.k.najdi("slack")["vklopljen"])
        self.assertTrue(self.k.zapomni_neprebrano("telegram", 4))
        self.assertFalse(self.k.zapomni_neprebrano("telegram", 4), "brez spremembe se ne pise")
        self.assertEqual(self.k.najdi("telegram")["neprebrano"], 4)
        self.assertTrue(self.k.odstrani("discord"))
        self.assertFalse(self.k.odstrani("discord"))
        with self.assertRaises(KeyError):
            self.k.vklopi("ni-ga", True)

    def test_preselitev_in_pokvarjeni_zapisi(self):
        self.s.set(sk.Kanali.KLJUC, [
            {"id": "m", "katalog": "", "ime": "Messenger", "url": "https://www.messenger.com/t/123"},
            {"id": "m", "url": "https://podvojen.example.org/"},
            {"id": "x", "url": "http://ni-varen.example.org/"},
            "smeti", {"url": "https://brez-id.example.org/"},
            {"id": "p", "katalog": "viber", "ime": "Viber", "url": "", "pot": "/x/Viber.AppImage", "neprebrano": "7"}])
        seznam = self.k.seznam()
        self.assertEqual([x["id"] for x in seznam], ["m", "p"])
        self.assertEqual(seznam[0]["url"], "https://www.facebook.com/messages/")
        self.assertEqual((seznam[1]["pot"], seznam[1]["neprebrano"], seznam[1]["url"]), ("/x/Viber.AppImage", 7, ""))
        self.assertEqual(len(self.s[sk.Kanali.KLJUC]), 2, "preseljeno in ocisceno se shrani")


class Brskalnik(unittest.TestCase):
    """Stranska plosca brskalnika bere isti katalog (core/config.py »integrations«)."""

    def test_preselitev_in_katalog_v_nastavitvah(self):
        from core import config
        n = {"language": "sl", "integrations": {
            "messenger": {"name": "Facebook Messenger", "url": "https://www.messenger.com", "enabled": True},
            "moj": {"name": "Moj", "url": "https://mail.google.com/mail/", "enabled": True}}}
        self.assertTrue(config.dodaj_katalog_integracijam(n))
        self.assertEqual(n["integrations"]["messenger"]["url"], "https://www.facebook.com/messages/")
        self.assertTrue(n["integrations"]["messenger"]["enabled"], "uporabnikova izbira ostane")
        self.assertNotIn("gmail", n["integrations"], "ista storitev (isti naslov) se ne podvoji")
        self.assertFalse(n["integrations"]["whatsapp"]["enabled"], "nove storitve so ponujene izklopljene")
        self.assertNotIn("signal", n["integrations"], "namizni programi niso za stransko plosco")
        del n["integrations"]["whatsapp"]
        self.assertFalse(config.dodaj_katalog_integracijam(n))
        self.assertNotIn("whatsapp", n["integrations"], "odstranjena storitev se ne vraca")

    def test_privzete_nastavitve_brez_messenger_com(self):
        from core import config
        self.assertEqual(config.DEFAULT_SETTINGS["integrations"]["messenger"]["url"], "https://www.facebook.com/messages/")
        for ime in (os.path.join("core", "config.py"), os.path.join("ui", "home.html")):
            self.assertNotRegex(open(os.path.join(KOREN, ime), encoding="utf-8").read(), r"//(www\.)?messenger\.com", ime)

    def test_stranska_plosca_gtk4_bere_katalog(self):
        vir = open(os.path.join(KOREN, "core", "stranska_plosca.py"), encoding="utf-8").read()
        self.assertIn('self.config.get("integrations"', vir)
        self.assertIn("self.splet.aplikacija(", vir)
        self.assertIn("from core.stranska_plosca import StranskaPlosca",
                      open(os.path.join(KOREN, "safeer_brskalnik.py"), encoding="utf-8").read())
        from core import stranska_plosca
        self.assertEqual(set(stranska_plosca.BESEDILA), set(JEZIKI))


class Carovnik(unittest.TestCase):
    def test_ponudniki_dajo_katalog(self):
        v = ponudniki.za_vmesnik("en")
        self.assertEqual({k["id"] for k in v["klepeti"]}, {k["id"] for k in sk.KATALOG})
        self.assertEqual({a["vrsta"] for a in v["aplikacije"]}, {"vec"})

    def test_besedila_vmesnika_v_vseh_jezikih(self):
        if not shutil.which("node"):
            self.skipTest("brez node")
        js = ("var BESEDILA_OS;" + open(os.path.join(KOREN, "assets", "os", "besedila.js"), encoding="utf-8").read() +
              ";process.stdout.write(JSON.stringify(BESEDILA_OS));")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(js)
        try:
            b = json.loads(subprocess.run(["node", f.name], capture_output=True, text=True, check=True).stdout)
        finally:
            os.unlink(f.name)
        os_js = open(os.path.join(KOREN, "assets", "os", "os.js"), encoding="utf-8").read()
        blok = os_js.split("==== Vgrajeni kanali Sporocil", 1)[1].split("==== konec: vgrajeni kanali Sporocil", 1)[0]
        kljuci = set(re.findall(r'\bt\("([A-Za-z]+)"', blok)) | set(re.findall(r': "(kanalNapaka[A-Za-z]*|sporocilaIzklopljena)"', blok))
        html = open(os.path.join(KOREN, "assets", "os", "index.html"), encoding="utf-8").read()
        kljuci |= set(re.findall(r'data-(?:t|naslov)="((?:kanal|vgrajen)[A-Za-z]*)"', html))
        kljuci |= {"ndSporocila", "ndSporocilaPod", "sporocilaIzklopljena", "kanalVklopljen", "kanalVklopljenPod"}
        self.assertGreater(len(kljuci), 30)
        for j in JEZIKI:
            manjka = sorted(k for k in kljuci if not b.get(j, {}).get(k))
            self.assertEqual(manjka, [], j)

    def test_preveri_prevode(self):
        r = subprocess.run(["python3", os.path.join(KOREN, "tools", "preveri-prevode.py"), KOREN], capture_output=True,
                           text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-2000:])


if __name__ == "__main__":
    unittest.main()
