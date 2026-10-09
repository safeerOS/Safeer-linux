"""Scit za Safeer OS na Linuxu: razresevalnik DNS, nabor domen, seznami (brez omrezja in brez resolvectl)."""
import os
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import os_scit  # noqa: E402


def vprasanje(ime: str, id_: int = 0x1234, vrsta: int = 1) -> bytes:
    telo = b"".join(struct.pack("B", len(d)) + d.encode() for d in ime.split(".")) + b"\x00"
    return struct.pack("!HHHHHH", id_, 0x0100, 1, 0, 0, 0) + telo + struct.pack("!HH", vrsta, 1)


class Paketi(unittest.TestCase):
    def test_ime_poizvedbe(self):
        self.assertEqual(os_scit.ime_poizvedbe(vprasanje("Ads.Example.COM")), "ads.example.com")
        self.assertEqual(os_scit.ime_poizvedbe(b"\x00" * 10), "")
        odgovor = bytearray(vprasanje("a.si"))
        odgovor[2] |= 0x80
        self.assertEqual(os_scit.ime_poizvedbe(bytes(odgovor)), "")

    def test_odgovor_zavrnjeno(self):
        p = vprasanje("bad.example", id_=0xBEEF)
        o = os_scit.odgovor_zavrnjeno(p)
        self.assertEqual(o[:2], b"\xbe\xef")
        zastavice, vprasanj, odgovorov = struct.unpack("!HHH", o[2:8])
        self.assertEqual(zastavice & 0x8000, 0x8000)   # odgovor
        self.assertEqual(zastavice & 0x000F, 3)        # NXDOMAIN
        self.assertEqual((vprasanj, odgovorov), (1, 0))
        self.assertEqual(o[12:], p[12:])               # vprasanje ponovljeno v celoti
        self.assertEqual(os_scit.ime_poizvedbe(bytes([o[0], o[1], 0x01]) + o[3:]), "bad.example")


class NaborDomen(unittest.TestCase):
    def test_razcleni_seznam(self):
        besedilo = "# komentar\n0.0.0.0 ads.example.com\n127.0.0.1 localhost\nplain.example\n" \
                   "phish.example.si CNAME .\n*.wild.example\n! easylist\n||ne.sme.com^\nlocalhost\n"
        self.assertEqual(list(os_scit.razcleni_seznam(besedilo)),
                         ["ads.example.com", "plain.example", "phish.example.si", "wild.example"])

    def test_nabor_poddomene_in_kategorija(self):
        n = os_scit.Nabor.iz_domen([("ads.example.com", "oglasi"), ("bad.example", "malware"),
                                    ("bad.example", "oglasi")])
        self.assertEqual(n.kategorija("ads.example.com"), "oglasi")
        self.assertEqual(n.kategorija("cdn.ads.example.com"), "oglasi")
        self.assertIsNone(n.kategorija("example.com"))
        self.assertEqual(n.kategorija("x.bad.example"), "malware")   # nevarnejsa kategorija prevlada
        self.assertIsNone(n.kategorija("safe.example"))

    def test_nabor_shrani_nalozi(self):
        n = os_scit.Nabor.iz_domen([("a.example", "phishing"), ("b.example", "groznje")])
        with tempfile.TemporaryDirectory() as m:
            pot = os.path.join(m, "domene.bin")
            n.shrani(pot)
            n2 = os_scit.Nabor.nalozi(pot)
            self.assertEqual(len(n2), 2)
            self.assertEqual(n2.kategorija("www.a.example"), "phishing")
            self.assertEqual(n2.kategorija("b.example"), "groznje")
            with open(pot, "wb") as f:
                f.write(b"smeti")
            self.assertIsNone(os_scit.Nabor.nalozi(pot))


class SeznamiTest(unittest.TestCase):
    def test_osvezi_iz_lokalnih_prenosov(self):
        vsebine = {
            "hagezi-pro": "\n".join("ad%d.example" % i for i in range(1200)),
            "hagezi-tif": "\n".join("t%d.example" % i for i in range(1100)),
            "hagezi-fake": "\n".join("f%d.example" % i for i in range(1050)),
            "urlhaus": "# urlhaus\n127.0.0.1 mal.example\n",
            "phishing-army": "phish.example\n",
            "si-cert": "cert.example CNAME .\n",
        }
        # Zastrupljen seznam (npr. prek CDN-ja) bi zaprl posodobitve - te ostanejo odprte.
        vsebine["phishing-army"] += "archive.ubuntu.com\ngithub.com\npackages.linuxmint.com\n"
        klici = []

        def prenesi(url, etag, cas=60.0):
            oznaka = [o for o, u, _k in os_scit.VIRI if u == url][0]
            klici.append((oznaka, etag))
            if etag == "e-" + oznaka:
                return 304, b"", etag
            return 200, vsebine[oznaka].encode(), "e-" + oznaka

        with tempfile.TemporaryDirectory() as m:
            s = os_scit.Seznami(m, prenesi_fn=prenesi)
            self.assertTrue(s.osvezi())
            self.assertEqual(len(s.nabor), 1200 + 1100 + 1050 + 6)
            self.assertEqual(s.kategorija("ad7.example"), "oglasi")
            self.assertEqual(s.kategorija("x.mal.example"), "malware")
            self.assertEqual(s.kategorija("cert.example"), "phishing")
            self.assertIsNone(s.kategorija("printer.local"))
            self.assertIsNone(s.kategorija("safeer.si"))
            self.assertIsNone(s.kategorija("ad7.example.safeer.si"))
            for ime in ("archive.ubuntu.com", "si.archive.ubuntu.com", "github.com", "packages.linuxmint.com"):
                self.assertIsNone(s.kategorija(ime), ime)
            # Drugi zagon iz iste mape: nabor je na disku, brez prenosa; osvezitev vrne 304 in nic ne prezida.
            s2 = os_scit.Seznami(m, prenesi_fn=prenesi)
            self.assertEqual(len(s2.nabor), len(s.nabor))
            self.assertTrue(s2.osvezi())
            self.assertEqual(klici[-1][1], "e-si-cert")
            self.assertEqual(s2.stanje()["seznami"]["urlhaus"], 1)

    def test_preusmeritev_na_drug_streznik_ni_sprejeta(self):
        from core.signed_feed import isti_gostitelj
        self.assertTrue(isti_gostitelj("https://cdn.jsdelivr.net/gh/a", "https://cdn.jsdelivr.net/gh/b"))
        self.assertFalse(isti_gostitelj("https://cdn.jsdelivr.net/gh/a", "https://zlo.example/a"))
        self.assertFalse(isti_gostitelj("https://phishing.army/x", "https://phishing.army.zlo.example/x"))

    def test_napaka_prenosa_ohrani_nabor(self):
        def prenesi(url, etag, cas=60.0):
            raise OSError("ni omrezja")
        with tempfile.TemporaryDirectory() as m:
            s = os_scit.Seznami(m, prenesi_fn=prenesi)
            self.assertFalse(s.osvezi())
            self.assertIn("hagezi-pro: OSError", s.napaka)
            self.assertEqual(len(s.nabor), 0)


class LazniUpstream:
    """Streznik DNS na 127.0.0.1, ki na vsako vprasanje vrne odgovor z istim id in zastavico odgovora."""

    def __init__(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.s.bind(("127.0.0.1", 0))
        self.vrata = self.s.getsockname()[1]
        self.prejeto = []
        threading.Thread(target=self._tek, daemon=True).start()

    def _tek(self):
        while True:
            try:
                p, od = self.s.recvfrom(4096)
            except OSError:
                return
            self.prejeto.append(os_scit.ime_poizvedbe(p))
            self.s.sendto(p[:2] + b"\x81\x80" + p[4:], od)

    def zapri(self):
        self.s.close()


class RazresevalnikTest(unittest.TestCase):
    def test_zavrne_in_posreduje(self):
        gor = LazniUpstream()
        r = os_scit.Razresevalnik(lambda ime: "oglasi" if ime.endswith("ads.example") else None, lambda: ["127.0.0.1"])
        # Upstream na drugih vratih: posredovanje preusmerimo na lazni streznik.
        izvirni = r._posreduj

        def posreduj(paket, tcp):
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.sendto(paket, ("127.0.0.1", gor.vrata))
            o, _ = s.recvfrom(4096)
            s.close()
            return o
        r._posreduj = posreduj
        vrata = r.zazeni()
        self.assertIn(vrata, os_scit.VRATA)
        try:
            k = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            k.settimeout(3)
            k.sendto(vprasanje("x.ads.example", id_=7), (os_scit.NASLOV, vrata))
            o, _ = k.recvfrom(4096)
            self.assertEqual(o[:2], b"\x00\x07")
            self.assertEqual(struct.unpack("!H", o[2:4])[0] & 0xF, 3)
            k.sendto(vprasanje("safeer.si", id_=8), (os_scit.NASLOV, vrata))
            o, _ = k.recvfrom(4096)
            self.assertEqual(o[:2], b"\x00\x08")
            self.assertEqual(o[2:4], b"\x81\x80")
            self.assertEqual(gor.prejeto, ["safeer.si"])
            # TCP: dolzina + paket.
            with socket.create_connection((os_scit.NASLOV, vrata), timeout=3) as t:
                p = vprasanje("y.ads.example", id_=9)
                t.sendall(struct.pack("!H", len(p)) + p)
                n = struct.unpack("!H", t.recv(2))[0]
                o = t.recv(n)
            self.assertEqual(o[:2], b"\x00\x09")
            self.assertEqual(r.blokiranih, 2)
            self.assertEqual(r.poizvedb, 3)
            self.assertEqual([z["ime"] for z in r.zadnje], ["y.ads.example", "x.ads.example"])
            k.close()
        finally:
            izvirni  # noqa: B018 - le da ostane sklic
            r.ustavi()
            gor.zapri()
        self.assertEqual(r.vrata, 0)


class UsmeriTest(unittest.TestCase):
    def test_rezerva_za_docker(self):
        """resolvectl dobi nas razresevalnik PRVI in streznike usmerjevalnika kot rezervo: brez njih bi
        /run/systemd/resolve/resolv.conf ostal brez uporabnega streznika (Docker izpusti loopback).

        V dveh korakih - najprej samo nas: systemd-resolved obdrzi streznik, ki ga trenutno uporablja, ce je ta tudi
        na novem seznamu, in bi v enem koraku ostal pri usmerjevalniku (Scit ne bi dobil nobene poizvedbe).
        Iskalnih domen se ne dotikamo (»~.« je prej izrinil domeno iz DHCP in kratka domaca imena niso delala)."""
        klici = []

        def zazeni(ukaz, cas=8.0):
            klici.append(ukaz)
            return 0, ""
        izvirni = os_scit._zazeni
        os_scit._zazeni = zazeni
        try:
            self.assertTrue(os_scit.usmeri("eth9", 5354, ["192.168.0.1", "1.1.1.1"]))
            self.assertEqual(klici, [["resolvectl", "dns", "eth9", "127.0.0.1:5354"],
                                     ["resolvectl", "dns", "eth9", "127.0.0.1:5354", "192.168.0.1", "1.1.1.1"]])
            del klici[:]
            self.assertTrue(os_scit.usmeri("eth9", 5355, []))
            self.assertEqual(klici, [["resolvectl", "dns", "eth9", "127.0.0.1:5355"]])
            # Prvi korak ne uspe (ni dovoljenja): drugega ni.
            del klici[:]
            os_scit._zazeni = lambda ukaz, cas=8.0: (klici.append(ukaz), (1, ""))[1]
            self.assertFalse(os_scit.usmeri("eth9", 5354, ["192.168.0.1"]))
            self.assertEqual(len(klici), 1)
        finally:
            os_scit._zazeni = izvirni
        self.assertFalse([k for k in klici if "domain" in k or "revert" in k])

    def test_trenutni_streznik(self):
        izvirni = os_scit._zazeni
        os_scit._zazeni = lambda ukaz, cas=8.0: (0, "Link 2 (eth9)\n    Current DNS Server: 192.168.0.1\n       DNS Servers: 127.0.0.1:5354 192.168.0.1\n")
        try:
            self.assertEqual(os_scit.trenutni_streznik("eth9"), "192.168.0.1")
        finally:
            os_scit._zazeni = izvirni


class ScitTest(unittest.TestCase):
    def test_stanje_brez_sistema(self):
        class Shramba(dict):
            def get(self, k, d=None):
                return dict.get(self, k, d)

            def set(self, k, v):
                self[k] = v
        with tempfile.TemporaryDirectory() as m:
            sc = os_scit.Scit(Shramba(), mapa=m)
            st = sc.stanje()
            self.assertFalse(st["vklop"])
            self.assertFalse(st["tece"])
            self.assertEqual(st["blokiranih"], 0)
            self.assertIn("pravilo", st)
            # Izklop brez vklopa nic ne pokvari.
            self.assertFalse(sc.nastavi(False)["vklop"])


class IzjemeInPremor(unittest.TestCase):
    """Uporabnik dovoli domeno, ki je bila pravkar blokirana, ali da Ščit za nekaj minut na premor - namesto da ga
    izklopi v celoti."""

    class Shramba(dict):
        def get(self, k, d=None):
            return dict.get(self, k, d)

        def set(self, k, v):
            self[k] = v

    class Seznami:
        def kategorija(self, ime):
            if ime.endswith("lazna-banka.example"):
                return "phishing"
            return "oglasi" if ime.endswith("ads.example") or ime.endswith("dovoljena.example") else None

        def stanje(self):
            return {}

    def test_cista_domena(self):
        self.assertEqual(os_scit.cista_domena(" Primer.SI. "), "primer.si")
        self.assertEqual(os_scit.cista_domena("a_b.x-y.example"), "a_b.x-y.example")
        for slabo in ("", None, "localhost", "http://x.si", "x..si", "-a.si", "a-.si", "x.si/pot", "a b.si", "x." + "a" * 64 + ".si",
                      ".".join(["abc"] * 80)):
            self.assertEqual(os_scit.cista_domena(slabo), "", slabo)

    def test_izjeme(self):
        with tempfile.TemporaryDirectory() as m:
            shramba = self.Shramba({"scit_izjeme": ["Dovoljena.Example.", "ni domena", 5, "dovoljena.example"]})
            sc = os_scit.Scit(shramba, mapa=m)
            sc.seznami = self.Seznami()
            self.assertEqual(sc.stanje()["izjeme"], ["dovoljena.example"])
            self.assertEqual(sc._kategorija("x.ads.example"), "oglasi")
            self.assertIsNone(sc._kategorija("dovoljena.example"))
            self.assertIsNone(sc._kategorija("cdn.dovoljena.example"), "izjema velja tudi za poddomene")
            self.assertEqual(sc._kategorija("nedovoljena.example"), "oglasi", "ne pa za ime, ki se samo konča enako")
            # Dovoliti je mogoče samo ime, ki je bilo pravkar blokirano.
            sc.razresevalnik = os_scit.Razresevalnik(sc._kategorija, lambda: [])
            sc.razresevalnik.zadnje = [{"ime": "y.x.ads.example", "kategorija": "oglasi", "cas": 2.0},
                                       {"ime": "x.ads.example", "kategorija": "oglasi", "cas": 1.0},
                                       {"ime": "z.ads.example", "kategorija": "oglasi", "cas": 0.5}]
            self.assertEqual(sc.dovoli("poljubna.example")["izjeme"], ["dovoljena.example"])
            self.assertEqual(sc.dovoli("ni domena")["izjeme"], ["dovoljena.example"])
            st = sc.dovoli("X.ADS.example.")
            self.assertEqual(st["izjeme"], ["dovoljena.example", "x.ads.example"])
            self.assertEqual([z["ime"] for z in st["zadnje"]], ["z.ads.example"], "dovoljena in njene poddomene gredo s seznama")
            self.assertEqual(shramba["scit_izjeme"], ["dovoljena.example", "x.ads.example"])
            self.assertIsNone(sc._kategorija("y.x.ads.example"))
            self.assertEqual(sc._kategorija("z.ads.example"), "oglasi")
            # Nov zagon prebere shranjene izjeme.
            self.assertEqual(os_scit.Scit(shramba, mapa=m).stanje()["izjeme"], ["dovoljena.example", "x.ads.example"])
            # »Blokiraj spet« izjemo odstrani.
            self.assertEqual(sc.dovoli("x.ads.example", False)["izjeme"], ["dovoljena.example"])
            self.assertEqual(sc._kategorija("x.ads.example"), "oglasi")

    def test_premor(self):
        with tempfile.TemporaryDirectory() as m:
            sc = os_scit.Scit(self.Shramba(), mapa=m)
            sc.seznami = self.Seznami()
            self.assertEqual(sc.stanje()["premor"], 0)
            st = sc.premor(15)
            self.assertTrue(890 < st["premor"] <= 901, st["premor"])
            self.assertIsNone(sc._kategorija("x.ads.example"), "med premorom oglasi in sledilci niso blokirani")
            self.assertEqual(sc._kategorija("prijava.lazna-banka.example"), "phishing", "nevarne strani ostanejo blokirane")
            sc._premor_do = time.monotonic() - 1                      # premor je potekel: Ščit nadaljuje sam
            self.assertEqual(sc._kategorija("x.ads.example"), "oglasi")
            self.assertEqual(sc.stanje()["premor"], 0)
            self.assertLessEqual(sc.premor(600)["premor"], os_scit.NAJDALJSI_PREMOR_MIN * 60 + 1, "največ ena ura")
            self.assertEqual(sc.premor(0)["premor"], 0)
            self.assertEqual(sc._kategorija("x.ads.example"), "oglasi")
            for slabo in ("x", None, -5):
                self.assertEqual(sc.premor(slabo)["premor"], 0)

    def test_most_in_stran(self):
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(koren, "safeer_os.py"), encoding="utf-8") as f:
            vir = f.read()
        self.assertIn('"scitDovoli": lambda: self.scit.dovoli(', vir)
        self.assertIn('"scitPremor": lambda: self.scit.premor(', vir)
        with open(os.path.join(koren, "assets", "os", "os.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn('klic("scitDovoli", [x.ime, true])', js)
        self.assertIn('klic("scitDovoli", [d, false])', js)
        self.assertIn('klic("scitPremor", [s.premor > 0 ? 0 : 15])', js)
        self.assertIn('if (x.kategorija !== "oglasi" && !gd.dataset.potrdi) {', js)   # nevarna domena: drugi klik
        with open(os.path.join(koren, "assets", "os", "besedila.js"), encoding="utf-8") as f:
            besedila = f.read()
        for kljuc in ("scitDovoli", "scitDovoliRes", "scitDovoljeno", "scitIzjeme", "scitBlokirajSpet", "scitPremor", "scitNadaljuj", "scitPremorTece"):
            self.assertEqual(besedila.count(kljuc + ': "'), 6, "%s mora biti v vseh šestih jezikih" % kljuc)


class Zamenjave:
    """Zacasno zamenja funkcije modula os_scit (klici sistema) in jih na koncu vrne."""

    def __init__(self, **nove):
        self.nove = nove
        self.stare = {}

    def __enter__(self):
        for ime, f in self.nove.items():
            self.stare[ime] = getattr(os_scit, ime)
            setattr(os_scit, ime, f)
        return self

    def __exit__(self, *a):
        for ime, f in self.stare.items():
            setattr(os_scit, ime, f)


class Sistem:
    """Lazni nmcli/resolvectl: odgovori po zacetku ukaza, vsak klic se zapise."""

    def __init__(self, odgovori):
        self.odgovori = odgovori
        self.klici = []

    def __call__(self, ukaz, cas=8.0):
        self.klici.append(list(ukaz))
        for zacetek, izid in self.odgovori:
            if ukaz[:len(zacetek)] == zacetek:
                return izid
        return 0, ""

    def nastavitve(self):
        return [k for k in self.klici if k[0] == "resolvectl" and len(k) > 3 or k[:2] == ["resolvectl", "revert"]]


class VrnitevDns(unittest.TestCase):
    """Ob izklopu Scita ali izhodu iz Safeer OS vmesnik dobi nazaj streznike NetworkManagerja. `resolvectl revert`
    bi pobrisal tudi te - NetworkManager jih znova poslje sele ob naslednji povezavi, racunalnik pa bi bil do takrat
    brez DNS (preverjeno na pravem systemd-resolved: tools/scit_lab)."""

    def test_strezniki_networkmanagerja(self):
        s = Sistem([(["nmcli", "-g", "IP4.DNS,IP6.DNS"], (0, "192.168.0.1 | 192.168.0.2\n2001\\:db8\\:\\:1 | fe80\\:\\:1\n"))])
        with Zamenjave(_zazeni=s):
            self.assertEqual(os_scit.upstream_strezniki("eth9"), ["192.168.0.1", "192.168.0.2", "2001:db8::1", "fe80::1"])
        s = Sistem([(["nmcli"], (0, "127.0.0.1 | 192.168.0.1 | 192.168.0.1 | ni-naslov | 0.0.0.0\n\\:\\:1\n"))])
        with Zamenjave(_zazeni=s):
            self.assertEqual(os_scit.upstream_strezniki("eth9"), ["192.168.0.1"], "brez povratne zanke, dvojnikov in smeti")
        with Zamenjave(_zazeni=Sistem([(["nmcli"], (10, ""))])):
            self.assertEqual(os_scit.upstream_strezniki("eth9"), [])
        self.assertEqual(os_scit.za_vticnico("fe80::1", "wlan0"), "fe80::1%wlan0")
        self.assertEqual(os_scit.za_vticnico("2001:db8::1", "wlan0"), "2001:db8::1")
        self.assertEqual(os_scit.za_vticnico("192.168.0.1", "wlan0"), "192.168.0.1")
        self.assertEqual(os_scit.za_vticnico("169.254.1.1", "wlan0"), "169.254.1.1")

    def test_povrni(self):
        s = Sistem([(["nmcli", "-g", "IP4.DNS,IP6.DNS"], (0, "192.168.0.1\nfe80\\:\\:1\n")),
                    (["resolvectl", "domain", "eth9"], (0, "Link 2 (eth9): lan\n"))])
        with Zamenjave(_zazeni=s):
            self.assertTrue(os_scit.povrni("eth9"))
        self.assertEqual(s.nastavitve(), [["resolvectl", "dns", "eth9", "192.168.0.1", "fe80::1"]])
        # NetworkManager za vmesnik nima streznikov: takrat (in samo takrat) revert.
        s = Sistem([(["nmcli"], (0, "\n\n"))])
        with Zamenjave(_zazeni=s):
            self.assertTrue(os_scit.povrni("eth9"))
        self.assertEqual(s.nastavitve(), [["resolvectl", "revert", "eth9"]])

    def test_iskalne_domene(self):
        def sistem(trenutne, nm):
            return Sistem([(["resolvectl", "domain", "eth9", ], (0, "Link 2 (eth9): %s\n" % trenutne)),
                           (["nmcli", "-g", "IP4.DOMAIN,IP6.DOMAIN,IP4.SEARCHES,IP6.SEARCHES"], (0, nm))])
        # Stara razlicica je iskalno domeno zamenjala z »~.«: vrnemo tisto iz NetworkManagerja.
        s = sistem("~.", "lan\n\n\n\n")
        with Zamenjave(_zazeni=s):
            os_scit.uredi_domene("eth9")
        self.assertEqual(s.klici[-1], ["resolvectl", "domain", "eth9", "lan"])
        # Stari izklop (revert) jih je pobrisal.
        s = sistem("", "lan | doma.example\n\n\n\n")
        with Zamenjave(_zazeni=s):
            os_scit.uredi_domene("eth9")
        self.assertEqual(s.klici[-1], ["resolvectl", "domain", "eth9", "lan", "doma.example"])
        # »~.« brez domen v NetworkManagerju: pocistimo.
        s = sistem("~.", "\n\n\n\n")
        with Zamenjave(_zazeni=s):
            os_scit.uredi_domene("eth9")
        self.assertEqual(s.klici[-1], ["resolvectl", "domain", "eth9", ""])
        # Domene so, kot jih je nastavil NetworkManager (ali uporabnik): ne dotikamo se.
        for trenutne, nm in (("lan", "lan\n\n\n\n"), ("podjetje.example ~vpn.example", "lan\n\n\n\n"), ("", "\n\n\n\n")):
            s = sistem(trenutne, nm)
            with Zamenjave(_zazeni=s):
                os_scit.uredi_domene("eth9")
            self.assertFalse(s.nastavitve(), trenutne)
        # Starejsi NetworkManager polja SEARCHES ne pozna.
        s = Sistem([(["nmcli", "-g", "IP4.DOMAIN,IP6.DOMAIN,IP4.SEARCHES,IP6.SEARCHES"], (2, "")),
                    (["nmcli", "-g", "IP4.DOMAIN,IP6.DOMAIN"], (0, "lan\n\n"))])
        with Zamenjave(_zazeni=s):
            self.assertEqual(os_scit.nm_domene("eth9"), ["lan"])

    def test_ostanek(self):
        with Zamenjave(dns_vmesnika=lambda v: "", nekdo_poslusa=lambda vrata: False):
            self.assertTrue(os_scit.je_ostanek("eth9"), "vmesnik brez streznikov (stari revert)")
        with Zamenjave(dns_vmesnika=lambda v: "127.0.0.1:5354 192.168.0.1", nekdo_poslusa=lambda vrata: False):
            self.assertTrue(os_scit.je_ostanek("eth9"), "nas streznik, na katerem nihce ne poslusa (sesutje)")
        with Zamenjave(dns_vmesnika=lambda v: "127.0.0.1:5354 192.168.0.1", nekdo_poslusa=lambda vrata: True):
            self.assertFalse(os_scit.je_ostanek("eth9"), "tam tece Scit drugega prijavljenega uporabnika")
        with Zamenjave(dns_vmesnika=lambda v: "192.168.0.1", nekdo_poslusa=lambda vrata: False):
            self.assertFalse(os_scit.je_ostanek("eth9"))
        with Zamenjave(dns_vmesnika=lambda v: "127.0.0.1:9999 192.168.0.1", nekdo_poslusa=lambda vrata: False):
            self.assertFalse(os_scit.je_ostanek("eth9"), "tuja nastavitev, ne nasa")
        self.assertFalse(os_scit.nekdo_poslusa(1))


class Flatpak(unittest.TestCase):
    """V peskovniku Flatpak sistemska orodja tecejo na gostitelju (flatpak-spawn --host). Dvoje je tam drugace:
    pkcheck v peskovniku ne obstaja (in nas PID gostitelju nic ne pomeni), /tmp pa je zaseben."""

    def test_dovoljenje_vprasamo_na_gostitelju(self):
        s = Sistem([(["flatpak-spawn"], (0, ""))])
        with Zamenjave(_zazeni=s, v_flatpaku=lambda: True, PRAVILO_POT="/ni/te/poti.rules"):
            self.assertTrue(os_scit.pravilo_namesceno())
        self.assertEqual(s.klici, [["flatpak-spawn", "--host", "sh", "-c", 'exec pkcheck --action-id "$0" --process $$',
                                    "org.freedesktop.resolve1.set-dns-servers"]])
        s = Sistem([(["flatpak-spawn"], (2, ""))])
        with Zamenjave(_zazeni=s, v_flatpaku=lambda: True, PRAVILO_POT="/ni/te/poti.rules"):
            self.assertFalse(os_scit.pravilo_namesceno())

    def test_pravilo_iz_mape_ki_jo_vidi_gostitelj(self):
        klici = []

        def zazeni(ukaz, cas=8.0):
            klici.append(list(ukaz))
            if ukaz[0] == "pkexec":
                self.assertTrue(os.path.isfile(ukaz[-2]), "datoteka mora obstajati, ko jo `install` bere")
                with open(ukaz[-2], encoding="utf-8") as f:
                    self.assertIn("org.freedesktop.resolve1.set-dns-servers", f.read())
            return 0, ""
        with tempfile.TemporaryDirectory() as m:
            okolje = {"XDG_CACHE_HOME": os.path.join(m, "cache"), "XDG_CONFIG_HOME": os.path.join(m, "config")}
            stare = {k: os.environ.get(k) for k in okolje}
            os.environ.update(okolje)
            izvirni_which = os_scit.shutil.which
            os_scit.shutil.which = lambda ime: "/app/host-bin/" + ime
            try:
                with Zamenjave(_zazeni=zazeni, v_flatpaku=lambda: True, PRAVILO_POT="/ni/te/poti.rules"):
                    self.assertTrue(os_scit.namesti_pravilo())
            finally:
                os_scit.shutil.which = izvirni_which
                for k, v in stare.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
            pkexec = [k for k in klici if k[0] == "pkexec"][0]
            self.assertEqual(pkexec[:8], ["pkexec", "install", "-m", "644", "-o", "root", "-g", "root"])
            self.assertTrue(pkexec[-2].startswith(os.path.join(m, "cache") + os.sep), "ne v /tmp, ki je v peskovniku zaseben")
            self.assertFalse(os.path.exists(pkexec[-2]), "zacasna datoteka se pospravi")
            self.assertTrue(os.path.isfile(os.path.join(m, "config", "safeer-os", "scit-pravilo")))

    def test_nastavitve_gostitelja_beremo_na_gostitelju(self):
        """Zrcalo /etc/resolv.conf v peskovniku zamuja, nsswitch.conf pa je tam od runtime-a: oboje preberemo zunaj."""
        s = Sistem([(["flatpak-spawn", "--host", "cat", "/etc/nsswitch.conf"], (0, "hosts: files dns\n")),
                    (["flatpak-spawn", "--host", "cat", "/etc/resolv.conf"], (0, "search .\n"))])
        with Zamenjave(_zazeni=s, v_flatpaku=lambda: True):
            self.assertFalse(os_scit.programi_uporabljajo_resolved(), "gostitelj ima svoj streznik DNS")
        self.assertEqual(len(s.klici), 2)
        s = Sistem([(["flatpak-spawn", "--host", "cat", "/etc/nsswitch.conf"], (0, "hosts: files dns\n")),
                    (["flatpak-spawn", "--host", "cat", "/etc/resolv.conf"], (0, "nameserver 127.0.0.53\nsearch lan\n"))])
        with Zamenjave(_zazeni=s, v_flatpaku=lambda: True):
            self.assertTrue(os_scit.programi_uporabljajo_resolved())
        with Zamenjave(_zazeni=Sistem([(["flatpak-spawn"], (1, ""))]), v_flatpaku=lambda: True):
            self.assertFalse(os_scit.programi_uporabljajo_resolved(), "ce gostitelja ne moremo vprasati, se DNS ne dotikamo")

    def test_zunaj_peskovnika_kot_prej(self):
        s = Sistem([(["pkcheck"], (0, ""))])
        izvirni_which = os_scit.shutil.which
        os_scit.shutil.which = lambda ime: "/usr/bin/" + ime
        try:
            with Zamenjave(_zazeni=s, v_flatpaku=lambda: False, PRAVILO_POT="/ni/te/poti.rules"):
                self.assertTrue(os_scit.pravilo_namesceno())
        finally:
            os_scit.shutil.which = izvirni_which
        self.assertEqual(s.klici, [["pkcheck", "--action-id", "org.freedesktop.resolve1.set-dns-servers", "--process", str(os.getpid())]])


class LastniDns(unittest.TestCase):
    """Racunalnik, kjer programi ne sprasujejo systemd-resolved (Pi-hole, AdGuard Home ...): Scit tam ne more
    filtrirati; z nastavitvijo v resolved bi celo zaobsel uporabnikov filter. Zato se DNS ne dotakne in to pove."""

    def test_kdo_razresuje(self):
        with tempfile.TemporaryDirectory() as m:
            r, n = os.path.join(m, "resolv.conf"), os.path.join(m, "nsswitch.conf")

            def primer(resolv, nsswitch="hosts: files mdns4_minimal [NOTFOUND=return] dns myhostname mymachines\n"):
                with open(r, "w", encoding="utf-8") as f:
                    f.write(resolv)
                with open(n, "w", encoding="utf-8") as f:
                    f.write(nsswitch)
                return os_scit.programi_uporabljajo_resolved(r, n)
            self.assertTrue(primer("# stub\nnameserver 127.0.0.53\noptions edns0 trust-ad\nsearch lan\n"))
            self.assertTrue(primer("nameserver 127.0.0.54\n"))
            self.assertFalse(primer("search .\n"), "brez streznika glibc vprasa 127.0.0.1 (lasten streznik DNS)")
            self.assertFalse(primer("nameserver 192.168.0.1\n"))
            self.assertFalse(primer("nameserver 127.0.0.53\nnameserver 192.168.0.1\n"))
            self.assertFalse(primer("nameserver 127.0.0.1\n"))
            self.assertFalse(primer("# nameserver 127.0.0.53\n"))
            self.assertTrue(primer("nameserver 192.168.0.1\n", "hosts: mymachines resolve [!UNAVAIL=return] files myhostname dns\n"))
            self.assertFalse(primer("nameserver 192.168.0.1\n", "hosts: files dns # resolve\n"))
            self.assertFalse(os_scit.programi_uporabljajo_resolved(os.path.join(m, "ni"), os.path.join(m, "ni")))

    def test_ne_dotakne_se_dns(self):
        klici = []
        with tempfile.TemporaryDirectory() as m, Zamenjave(
                razlog_nemoznosti=lambda: "lastni_dns", pravilo_namesceno=lambda: True,
                namesti_pravilo=lambda: klici.append("pravilo") or True,
                vmesniki_povezani=lambda: klici.append("vmesniki") or ["eth9"],
                usmeri=lambda *a: klici.append("usmeri") or True, povrni=lambda v: klici.append("povrni") or True):
            shramba = IzjemeInPremor.Shramba({"scit": True})
            sc = os_scit.Scit(shramba, mapa=m)
            st = sc.stanje()
            self.assertEqual((st["mozno"], st["razlog"], st["tece"]), (False, "lastni_dns", False))
            sc._zagon()                                   # ob zagonu Safeer OS z vklopljenim Scitom v nastavitvah
            self.assertIsNone(sc.razresevalnik)
            st = sc.nastavi(True)
            self.assertEqual(st["napaka"], "lastni_dns")
            self.assertIsNone(sc.razresevalnik)
            sc2 = os_scit.Scit(IzjemeInPremor.Shramba(), mapa=m)
            self.assertEqual(sc2.nastavi(True)["napaka"], "lastni_dns")
            self.assertFalse(sc2.vklopljen)
            sc2._zagon()                                  # izklopljen: tudi ostankov ne pospravlja
        self.assertEqual(klici, [], "nobenega klica, ki bi spremenil ali sploh pregledoval DNS")

    def test_napaka_izgine_ko_je_spet_mozno(self):
        with tempfile.TemporaryDirectory() as m:
            sc = os_scit.Scit(IzjemeInPremor.Shramba(), mapa=m)
            sc.napaka = "lastni_dns"
            with Zamenjave(razlog_nemoznosti=lambda: "lastni_dns", pravilo_namesceno=lambda: False):
                self.assertEqual(sc.stanje()["napaka"], "lastni_dns")
            with Zamenjave(razlog_nemoznosti=lambda: "", pravilo_namesceno=lambda: False):
                self.assertEqual(sc.stanje()["napaka"], "")


class UporabiTest(unittest.TestCase):
    """Zivljenje Scita brez sistema: kdaj nastavi, kdaj vrne, kdaj ne sme nicesar."""

    class Razresevalnik:
        vrata = 5354
        blokiranih = poizvedb = 0
        zadnje: list = []

        def ustavi(self):
            self.vrata = 0

    def _scit(self, m, **shramba):
        sc = os_scit.Scit(IzjemeInPremor.Shramba(shramba), mapa=m)
        sc.razresevalnik = self.Razresevalnik()
        return sc

    def test_nastavi_in_strazi(self):
        dns = {"eth9": "192.168.0.1"}
        trenutni = {"eth9": "192.168.0.1"}
        klici = []

        def usmeri(v, vrata, rezerva):
            # Kam posredujemo, mora biti znano, preden resolved poslje prvo poizvedbo.
            self.assertEqual(sc.strezniki, ["192.168.0.1", "fe80::1%eth9"])
            klici.append(("usmeri", v, vrata, tuple(rezerva)))
            dns[v] = "127.0.0.1:%d %s" % (vrata, " ".join(rezerva))
            trenutni[v] = ""
            return True
        with tempfile.TemporaryDirectory() as m, Zamenjave(
                vmesniki_povezani=lambda: ["eth9"], upstream_strezniki=lambda v: ["192.168.0.1", "fe80::1"],
                dns_vmesnika=lambda v: dns[v], trenutni_streznik=lambda v: trenutni[v], usmeri=usmeri,
                pravilo_namesceno=lambda: True, uredi_domene=lambda v: klici.append(("domene", v)),
                izprazni_predpomnilnik=lambda: klici.append(("predpomnilnik",))):
            sc = self._scit(m, scit=True)
            sc._uporabi()
            self.assertEqual(klici, [("usmeri", "eth9", 5354, ("192.168.0.1", "fe80::1")), ("domene", "eth9"), ("predpomnilnik",)])
            self.assertEqual((sc.vmesniki, sc.napaka), (["eth9"], ""))
            # Vse je na mestu: naslednji pregled nicesar ne nastavlja.
            del klici[:]
            trenutni["eth9"] = "127.0.0.1:5354"
            sc._uporabi()
            self.assertEqual(klici, [])
            # resolved je presel na rezervo (nas razresevalnik mu ni odgovoril pravocasno): nastavimo znova.
            trenutni["eth9"] = "192.168.0.1"
            sc._uporabi()
            self.assertEqual([k[0] for k in klici], ["usmeri", "predpomnilnik"])
            # NetworkManager je po novi povezavi poslal svoje streznike.
            del klici[:]
            dns["eth9"] = "192.168.0.1"
            sc._uporabi()
            self.assertEqual([k[0] for k in klici], ["usmeri", "predpomnilnik"])

    def test_brez_dovoljenja_ni_okna_za_geslo(self):
        """resolvectl bi brez pravila polkit odprl okno za geslo (iz straze vsakih 20 s): brez dovoljenja ga ne klicemo."""
        klici = []
        with tempfile.TemporaryDirectory() as m, Zamenjave(
                vmesniki_povezani=lambda: ["eth9"], upstream_strezniki=lambda v: ["192.168.0.1"],
                dns_vmesnika=lambda v: "192.168.0.1", trenutni_streznik=lambda v: "192.168.0.1",
                usmeri=lambda *a: klici.append("usmeri") or True, povrni=lambda v: klici.append("povrni") or True,
                pravilo_namesceno=lambda: False, uredi_domene=lambda v: None, izprazni_predpomnilnik=lambda: None):
            sc = self._scit(m, scit=True)
            sc._uporabi()
            self.assertEqual((sc.vmesniki, sc.napaka), ([], "pravilo"))
            sc.vmesniki = ["eth9"]
            sc._ustavi()                                   # tudi ob izhodu brez okna za geslo
        self.assertEqual(klici, [])

    def test_dva_uporabnika_ne_tekmujeta(self):
        """Vmesnik, ki ga ze varuje delujoc Scit drugega prijavljenega uporabnika (druga vrata), pustimo pri miru -
        sicer bi strazi obeh nastavitev izmenicno prepisovali."""
        klici = []
        dns = {"eth9": "127.0.0.1:5355 192.168.0.1"}
        poslusa = {5355: True}
        with tempfile.TemporaryDirectory() as m, Zamenjave(
                vmesniki_povezani=lambda: ["eth9"], upstream_strezniki=lambda v: ["192.168.0.1"],
                dns_vmesnika=lambda v: dns[v], trenutni_streznik=lambda v: "127.0.0.1:5355",
                nekdo_poslusa=lambda vrata: poslusa.get(vrata, False),
                usmeri=lambda *a: klici.append("usmeri") or True, pravilo_namesceno=lambda: True,
                uredi_domene=lambda v: None, izprazni_predpomnilnik=lambda: None):
            sc = self._scit(m, scit=True)
            sc._uporabi()
            self.assertEqual((klici, sc.vmesniki, sc.napaka), ([], [], ""))
            # Njegov Safeer OS se je koncal brez pospravljanja (nihce vec ne poslusa): vmesnik prevzamemo.
            poslusa[5355] = False
            sc._uporabi()
            self.assertEqual((klici, sc.vmesniki), (["usmeri"], ["eth9"]))
        self.assertFalse(os_scit.tuj_scit("127.0.0.1:5354 192.168.0.1", 5354), "to smo mi")
        self.assertFalse(os_scit.tuj_scit("192.168.0.1", 5354))
        self.assertFalse(os_scit.tuj_scit("", 5354))

    def test_brez_omrezja_in_pozneje_povezan(self):
        povezani = []
        with tempfile.TemporaryDirectory() as m, Zamenjave(
                vmesniki_povezani=lambda: list(povezani), upstream_strezniki=lambda v: ["192.168.0.1"],
                dns_vmesnika=lambda v: "192.168.0.1", trenutni_streznik=lambda v: "", usmeri=lambda *a: True,
                pravilo_namesceno=lambda: True, uredi_domene=lambda v: None, izprazni_predpomnilnik=lambda: None):
            sc = self._scit(m)
            sc._uporabi()
            self.assertEqual((sc.vmesniki, sc.napaka, sc.strezniki), ([], "ni_omrezja", ["1.1.1.1", "9.9.9.9"]))
            povezani.append("wlan0")
            sc._uporabi()
            self.assertEqual((sc.vmesniki, sc.napaka, sc.strezniki), (["wlan0"], "", ["192.168.0.1"]))
            del povezani[:]
            sc._uporabi()
            self.assertEqual((sc.vmesniki, sc.napaka), ([], "ni_omrezja"))

    def test_izklop_vrne_streznike(self):
        klici = []
        with tempfile.TemporaryDirectory() as m, Zamenjave(
                razlog_nemoznosti=lambda: "", pravilo_namesceno=lambda: True, povrni=lambda v: klici.append(v) or True):
            sc = self._scit(m, scit=True)
            sc.vmesniki = ["eth9", "wlan0"]
            st = sc.nastavi(False)
            self.assertEqual(klici, ["eth9", "wlan0"])
            self.assertEqual((st["vklop"], st["tece"], st["vmesniki"]), (False, False, []))
            # Izhod iz Safeer OS (koncaj) po izklopu nicesar vec ne spreminja.
            sc.koncaj()
            self.assertEqual(klici, ["eth9", "wlan0"])

    def test_ostanki_ob_zagonu(self):
        """Scit je izklopljen, vmesnik pa je ostal brez DNS za starejso razlicico: ob zagonu ga popravimo - samo kjer
        smemo brez gesla in samo vmesnike, ki so res nas ostanek."""
        klici = []
        with tempfile.TemporaryDirectory() as m, Zamenjave(
                razlog_nemoznosti=lambda: "", vmesniki_povezani=lambda: ["eth9", "wlan0", "eth1"],
                upstream_strezniki=lambda v: [] if v == "eth1" else ["192.168.0.1"],
                je_ostanek=lambda v: v != "wlan0", pravilo_namesceno=lambda: True,
                povrni=lambda v: klici.append(v) or True):
            sc = os_scit.Scit(IzjemeInPremor.Shramba(), mapa=m)
            sc._zagon()
            self.assertEqual(klici, ["eth9"])
            self.assertIsNone(sc.razresevalnik, "izklopljen Scit se ob zagonu ne zazene")
        del klici[:]
        with tempfile.TemporaryDirectory() as m, Zamenjave(
                razlog_nemoznosti=lambda: "", vmesniki_povezani=lambda: ["eth9"], upstream_strezniki=lambda v: ["192.168.0.1"],
                je_ostanek=lambda v: True, pravilo_namesceno=lambda: False, povrni=lambda v: klici.append(v) or True):
            os_scit.Scit(IzjemeInPremor.Shramba(), mapa=m)._zagon()
        self.assertEqual(klici, [], "brez pravila polkit (Scit ni bil nikoli vklopljen) nicesar")

    def test_posredovanje_ipv6(self):
        try:
            gor = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
            gor.bind(("::1", 0))
        except OSError:
            self.skipTest("ni IPv6 na povratni zanki")
        vrata = gor.getsockname()[1]

        def tek():
            try:
                p, od = gor.recvfrom(4096)
                gor.sendto(p[:2] + b"\x81\x80" + p[4:], od)
            except OSError:
                pass
        threading.Thread(target=tek, daemon=True).start()
        r = os_scit.Razresevalnik(lambda ime: None, lambda: ["::1"])
        izvirni = socket.getaddrinfo
        socket.getaddrinfo = lambda g, v, *a, **k: izvirni(g, vrata if v == 53 else v, *a, **k)
        try:
            o = r._posreduj(vprasanje("safeer.si", id_=0x77), False)
        finally:
            socket.getaddrinfo = izvirni
            gor.close()
        self.assertEqual(o[:4], b"\x00\x77\x81\x80")

    def test_straza_in_delovna(self):
        self.assertEqual(len(os_scit.znak_dns()), 2)
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(koren, "safeer_os.py"), encoding="utf-8") as f:
            vir = f.read()
        # Scit se zazene tudi, kadar Safeer OS tece kot delovna povrsina (--delovna); prej se tam ni nikoli. Tretje
        # mesto je _vklopi_delovno: delovna povrsina se vklopi v procesu, ki ze tece kot okno Safeer Player.
        self.assertEqual(vir.count("self.scit.zacni_ce_vklopljen()"), 3)
        delovna = vir[vir.index("if self.delovna and self.okno_delovna is None:"):]
        self.assertLess(delovna.index("self.scit.zacni_ce_vklopljen()"), delovna.index("return"))
        with open(os.path.join(koren, "assets", "os", "os.js"), encoding="utf-8") as f:
            js = f.read()
        self.assertIn('s.razlog === "lastni_dns" ? "scitNapaka_lastni_dns" : "scitNiMozno"', js)
        self.assertIn('.scit-zadnje:hover, .scit-zadnje button:focus', js)
        with open(os.path.join(koren, "assets", "os", "besedila.js"), encoding="utf-8") as f:
            self.assertEqual(f.read().count('scitNapaka_lastni_dns: "'), 6)


if __name__ == "__main__":
    unittest.main()
