"""Filter vira Usenet v mrezi Medijskega centra (lastnik 10. 11. 2026: kot TV). Brez omrezja: indeksator je nadomestek,
ki steje klice. Preverja stevilo zahtev (ne vec kot TV za isto mrezo), zapise (NA_VOLJO ne potece, negativni 6 h),
precisceno mrezo (vrstni red, znacka, napis prazne mreze) in predvajanje samo prek Useneta."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import debrid, debrid_pravila as P, filter_vira_pravila as F, os_katalog, os_media, usenet_filter as UF
from core import usenet_pravila as U

GB = 1073741824


class Ura:
    def __init__(self):
        self.ms = 1_800_000_000_000

    def __call__(self):
        return self.ms

    def spi(self, s):
        self.ms += int(s * 1000)


class Vrsta:
    """Izvajalec, ki dela ne pozene sam: preizkus ga pozene korak za korakom (kot dve delovni niti, a ponovljivo)."""

    def __init__(self):
        self.dela = []
        self.najvec_hkrati = 0

    def submit(self, f, *a):
        self.dela.append((f, a))
        self.najvec_hkrati = max(self.najvec_hkrati, len(self.dela))

    def pozeni(self, najvec=10_000):
        n = 0
        while self.dela and n < najvec:
            f, a = self.dela.pop(0)
            f(*a)
            n += 1
        return n


class Indeksator:
    """Nadomestek indeksatorja: [izdaje] po id-ju (None = ni odgovora), privzeto ena 1080p izdaja."""

    def __init__(self, izdaje=None, meja=False):
        self.klici = []
        self.izdaje = izdaje or {}
        self.meja = meja
        self.racun = True

    def filter_racun(self):
        return self.racun

    def odtis_racuna(self):
        return "odtis1"

    def filter_iskanje(self, ident, rok=8.0):
        self.klici.append(ident)
        if self.meja:
            return debrid.IzidIskanja(None, True, "meja")
        z = self.izdaje.get(ident, [U.Zadetek("Film.2020.1080p.WEB-DL.x264", "https://ix.primer/n", 4 * GB)])
        return debrid.IzidIskanja(z)


def _vnos(n, tip="movie"):
    ident = "tt%07d" % n
    vrsta = "film" if tip == "movie" else "serija"
    return {"id": "stremio:d:%s:%s" % (tip, ident), "naslov": "Naslov %d" % n, "vrsta": vrsta,
            "url": "stremio:https://d.primer|%s|%s" % (tip, ident), "kakovost": "4K"}


def _filter(td=None, izdaje=None):
    ura, vrsta, ix = Ura(), Vrsta(), Indeksator(izdaje)
    pot = Path(td) / UF.IME_DATOTEKE if td else None
    f = UF.UsenetFilter(pot, ix, ura=ura, izvajalec=vrsta, spi=ura.spi)
    m = UF.FilterMreze(f, os_media.MediaCenter._kljuc_razpolozljivosti, os_media.MediaCenter._stremio_naslov_vnosa,
                       lambda: UF.tok_izbira.Zmoznosti())
    m.casovniki = False
    return f, m, ura, vrsta, ix


def _rezultat(vnosi, kljuc="k1"):
    return {"vnosi": vnosi, "kljuc": kljuc, "skupaj": len(vnosi), "skupaj_strani": 9}


class SteviloZahtev(unittest.TestCase):
    """TV GlasbaActivity.preveriUsenet: PRORACUN_MREZE na zahtevo + enkrat VNAPREJ_MREZE, najvec HKRATI hkrati,
    NA_MINUTO - REZERVIRANO_UPORABNIKU preverb na minuto."""

    def test_ena_mreza_ne_vec_kot_tv(self):
        f, m, ura, vrsta, ix = _filter()
        osvezeno = []
        m.prikazi("mreza", 1, _rezultat([_vnos(i) for i in range(100)]), True, osvezeno.append)
        vrsta.pozeni()
        # V prvi minuti: kvota preverb (60 - 5 za klik); proracun mreze bi dovolil 40 + 20.
        self.assertEqual(len(ix.klici), F.NA_MINUTO - F.REZERVIRANO_UPORABNIKU)
        self.assertLessEqual(vrsta.najvec_hkrati, F.HKRATI)
        # Tiha osvezitev kataloga (ista zahteva) ne da novega proracuna.
        ura.ms += 61_000
        m.prikazi("mreza", 1, _rezultat([_vnos(i) for i in range(100)]), False, osvezeno.append)
        vrsta.pozeni()
        # Kot TV: preverba, ki je med cakanjem v vrsti izgubila mesto kvote, porabi proracun brez zahteve.
        poslanih = len(ix.klici)
        self.assertGreater(poslanih, F.NA_MINUTO - F.REZERVIRANO_UPORABNIKU)
        self.assertLessEqual(poslanih, F.PRORACUN_MREZE + F.VNAPREJ_MREZE)
        self.assertEqual(m.mreza.proracun.ostalo, 0)
        for _ in range(3):
            ura.ms += 61_000
            m.preveri(m.mreza)
            vrsta.pozeni()
        self.assertEqual(len(ix.klici), poslanih, "po proracunu nic vec")
        self.assertEqual(len(set(ix.klici)), len(ix.klici), "noben naslov dvakrat")
        self.assertEqual(ix.klici[:3], ["tt0000000", "tt0000001", "tt0000002"], "vrstni red mreze")
        self.assertTrue(osvezeno, "izid preverbe osvezi mrezo")

    def test_nalozi_vec_nova_zahteva_sele_po_porabljenem(self):
        f, m, ura, vrsta, ix = _filter()
        m.prikazi("mreza", 1, _rezultat([_vnos(i) for i in range(24)]), True)
        vrsta.pozeni()
        self.assertEqual(len(ix.klici), 24)            # cela stran; ostanek proracuna caka na kandidate
        # Druga stran: ista zahteva (proracun se ni porabljen) - porabi samo ostanek (40 - 24 = 16, nato 20 vnaprej).
        m.prikazi("mreza", 2, _rezultat([_vnos(100 + i) for i in range(24)], "k2"), True)
        vrsta.pozeni()
        self.assertEqual(len(ix.klici), 24 + 24)
        ura.ms += 61_000
        m.prikazi("mreza", 3, _rezultat([_vnos(200 + i) for i in range(24)], "k3"), True)
        vrsta.pozeni()
        self.assertEqual(len(ix.klici), F.PRORACUN_MREZE + F.VNAPREJ_MREZE)
        # Proracun in vnaprej porabljena: naslednja stran je nova zahteva (TV »Nalozi vec«) - ura naprej zaradi kvote.
        ura.ms += 61_000
        m.prikazi("mreza", 4, _rezultat([_vnos(300 + i) for i in range(24)], "k4"), True)
        vrsta.pozeni()
        # Nova zahteva (40) pokrije 12 se nepreverjenih naslovov 3. strani in vseh 24 na 4. strani.
        self.assertEqual(len(ix.klici), F.PRORACUN_MREZE + F.VNAPREJ_MREZE + 12 + 24)

    def test_meja_ustavi_vse(self):
        f, m, ura, vrsta, ix = _filter()
        ix.meja = True
        m.prikazi("mreza", 1, _rezultat([_vnos(i) for i in range(30)]), True)
        vrsta.pozeni()
        # Prva zahteva dobi mejo, druga je ze v vrsti (HKRATI); nato premor - nobena nova.
        self.assertLessEqual(len(ix.klici), F.HKRATI)
        self.assertTrue(f.v_premoru())
        self.assertEqual(m.prazno(m.mreza), F.Prazno.NE_ODGOVARJA)

    def test_brez_racuna_ni_zahtev(self):
        f, m, ura, vrsta, ix = _filter()
        ix.racun = False
        r = m.prikazi("mreza", 1, _rezultat([_vnos(i) for i in range(10)]), True)
        vrsta.pozeni()
        self.assertEqual(ix.klici, [])
        self.assertEqual(r["vnosi"], [])
        self.assertEqual(r["usenet_filter"]["prazno"], "ne_odgovarja")


class EnNaslov(unittest.TestCase):
    def test_tretji_hkrati_ne_gre(self):
        # TV UsenetFilter.preveri: vTeku >= HKRATI -> false (brez zapisa, brez klica ob_koncu); vsak klicatelj, ne le mreza.
        f, m, ura, vrsta, ix = _filter()
        konci = []
        z = UF.tok_izbira.Zmoznosti()
        izidi = [f.preveri("k%d" % i, (lambda i=i: "tt%07d" % i), z, lambda: True, lambda: konci.append(1)) for i in range(3)]
        self.assertEqual(izidi, [True, True, False])
        self.assertFalse(f.preveri("k0", lambda: "tt0000000", z, lambda: True, lambda: None), "ze v teku")
        vrsta.pozeni()
        self.assertEqual(ix.klici, ["tt0000000", "tt0000001"])
        self.assertEqual(len(konci), 2)


class PraveNiti(unittest.TestCase):
    def test_najvec_dve_hkrati(self):
        import threading
        import time as _t
        zaklep, tece, najvec = threading.Lock(), [0], [0]

        class Pocasen(Indeksator):
            def filter_iskanje(self, ident, rok=8.0):
                with zaklep:
                    tece[0] += 1
                    najvec[0] = max(najvec[0], tece[0])
                _t.sleep(0.02)
                with zaklep:
                    tece[0] -= 1
                return super().filter_iskanje(ident, rok)

        ix = Pocasen()
        f = UF.UsenetFilter(None, ix, spi=lambda s: None)
        m = UF.FilterMreze(f, os_media.MediaCenter._kljuc_razpolozljivosti, os_media.MediaCenter._stremio_naslov_vnosa,
                           lambda: UF.tok_izbira.Zmoznosti())
        m.casovniki = False
        m.prikazi("mreza", 1, _rezultat([_vnos(i) for i in range(12)]), True)
        konec = _t.monotonic() + 10
        while len(ix.klici) < 12 and _t.monotonic() < konec:
            _t.sleep(0.01)
        self.assertEqual(len(ix.klici), 12)
        self.assertLessEqual(najvec[0], F.HKRATI)


class Zapisi(unittest.TestCase):
    def test_na_voljo_ne_potece_negativni_6_ur_in_disk(self):
        with tempfile.TemporaryDirectory() as td:
            nic = {"tt0000002": []}
            f, m, ura, vrsta, ix = _filter(td, nic)
            m.prikazi("mreza", 1, _rezultat([_vnos(1), _vnos(2)]), True)
            vrsta.pozeni()
            self.assertEqual(ix.klici, ["tt0000001", "tt0000002"])
            # Nov zagon (nov objekt, ista datoteka): zapisi z diska, brez zahtev.
            ura.ms += 6 * 3600_000 - 1000
            f2, m2, _, vrsta2, ix2 = _filter(td, nic)
            f2.ura = ura
            r = m2.prikazi("mreza", 1, _rezultat([_vnos(1), _vnos(2)]), True)
            vrsta2.pozeni()
            self.assertEqual(ix2.klici, [])
            self.assertEqual([x["id"] for x in r["vnosi"]], [_vnos(1)["id"]])
            # Po 6 h negativni zapis potece (vprasamo znova), NA_VOLJO ne (tudi po letu).
            ura.ms += 2000
            m2.prikazi("mreza", 1, _rezultat([_vnos(1), _vnos(2)]), True)
            vrsta2.pozeni()
            self.assertEqual(ix2.klici, ["tt0000002"])
            ura.ms += 365 * 24 * 3600_000
            self.assertTrue(f2.pokazi(m2._kljuc(_vnos(1))))
            vsebina = (Path(td) / UF.IME_DATOTEKE).read_text(encoding="utf-8")
            self.assertNotIn("ix.primer", vsebina)                 # povezav indeksatorja ni na disku

    def test_pozabi(self):
        f, m, ura, vrsta, ix = _filter()
        m.prikazi("mreza", 1, _rezultat([_vnos(1)]), True)
        vrsta.pozeni()
        k = m._kljuc(_vnos(1))
        self.assertTrue(f.pokazi(k))
        f.pozabi(k)
        self.assertFalse(f.pokazi(k))
        self.assertTrue(f.vprasati(k))


class Mreza(unittest.TestCase):
    def test_samo_na_voljo_vrstni_red_in_znacka(self):
        izdaje = {"tt0000002": [U.Zadetek("Film.2160p.WEB-DL.x265", "https://ix.primer/a", 9 * GB)],
                  "tt0000003": [U.Zadetek("Film.1080p.x264", "https://ix.primer/b", 30 * GB)],    # nad 15 GB
                  "tt0000004": [U.Zadetek("Film.1080p.x264", "https://ix.primer/c", 2 * GB, True)],  # z geslom
                  "tt0000005": [U.Zadetek("Film.CAM.x264", "https://ix.primer/d", 1 * GB)]}
        f, m, ura, vrsta, ix = _filter(izdaje=izdaje)
        vnosi = [_vnos(i) for i in (1, 2, 3, 4, 5)] + [{"id": "lokalno", "naslov": "Lokalno", "vrsta": "film",
                                                         "url": "file:///x.mkv", "tmdb_id": 5}]
        r = m.prikazi("mreza", 1, _rezultat(vnosi), True)
        self.assertEqual(r["vnosi"], [])
        self.assertEqual(r["usenet_filter"]["prazno"], "iscem")
        self.assertNotIn("skupaj", r)
        vrsta.pozeni()
        r = m.preciscen(m.mreza, _rezultat(vnosi))
        self.assertEqual([x["id"] for x in r["vnosi"]], [_vnos(i)["id"] for i in (1, 2, 5)])
        self.assertEqual([x["oznaka_vira"] for x in r["vnosi"]], ["★ Full HD", "★ 4K", "⚠ CAM"])
        self.assertEqual(r["vnosi"][0]["kakovost"], "4K")         # podatki kataloga ostanejo, znacka je oznaka_vira

    def test_prazno_ni_naslovov(self):
        f, m, ura, vrsta, ix = _filter(izdaje={"tt0000001": []})
        m.prikazi("mreza", 1, _rezultat([_vnos(1)]), True)
        vrsta.pozeni()
        self.assertEqual(m.preciscen(m.mreza, _rezultat([_vnos(1)]))["usenet_filter"]["prazno"], "ni_naslovov")

    def test_serija_vprasa_prvo_epizodo(self):
        f, m, ura, vrsta, ix = _filter()
        m.prikazi("mreza", 1, _rezultat([_vnos(7, "series")]), True)
        vrsta.pozeni()
        self.assertEqual(ix.klici, ["tt0000007:1:1"])


class LastniPonudnik:
    def na_voljo(self):
        return True


def _sifriraj(s):
    return "enc:" + s[::-1]


def _desifriraj(s):
    return s[4:][::-1] if s.startswith("enc:") else ""


class Izbira(unittest.TestCase):
    """Izbirnik kot TV (GlasbaActivity, izbira »debrid«) in OsPravila.samoUsenetIzbran."""

    def _d(self):
        shramba = {"d": {}}
        d = debrid.Debrid(lambda: shramba["d"], lambda x: shramba.__setitem__("d", x), _sifriraj, _desifriraj)
        d.lastni_usenet = LastniPonudnik()
        return d

    def test_preslikava(self):
        d = self._d()
        self.assertTrue(d.nastavi_kljuc(P.TORBOX, "0f0e0d0c-0b0a-0908-0706-050403020100"))
        self.assertTrue(d.nastavi_izbiro("usenet"))
        self.assertEqual((d.usenet_izbran(), d.aktivna()), (True, None))
        self.assertTrue(d.samo_usenet())
        self.assertTrue(d.nastavi_izbiro("vsi"))
        self.assertEqual((d.usenet_izbran(), d.aktivna()), (True, P.TORBOX))
        self.assertFalse(d.samo_usenet())                          # »Vsi viri« ne omeji predvajanja
        self.assertTrue(d.nastavi_izbiro(P.TORBOX))
        self.assertEqual((d.usenet_izbran(), d.aktivna()), (False, P.TORBOX))
        self.assertTrue(d.nastavi_izbiro(""))
        self.assertEqual((d.usenet_izbran(), d.aktivna()), (False, None))
        self.assertFalse(d.nastavi_izbiro("neznano"))
        st = debrid.most(d, ["izbira", "usenet"])
        self.assertTrue(st["ok"])
        self.assertTrue(st["usenet_izbran"])
        self.assertTrue(st["usenet_lastni"])

    def test_brez_lastnega_ponudnika_ni_filtra(self):
        d = self._d()
        d.lastni_usenet = None
        d.nastavi_izbiro("usenet")
        self.assertFalse(d.samo_usenet())

    def test_odtis_brez_kljuca(self):
        d = self._d()
        self.assertEqual(d.odtis_racuna(), "")
        d.nastavi_indeksator("https://ix.primer", "0123456789abcdef0123456789abcdef")
        o = d.odtis_racuna()
        self.assertEqual(len(o), 12)
        self.assertNotIn("0123456789abcdef", o)


class PredvajanjeSamoUsenet(unittest.TestCase):
    """TV izbranSamoUsenet: klik predvaja SAMO prek Useneta; 0 izdaj pozabi zapis filtra, meja ne."""

    def _center(self, td):
        center = os_media.MediaCenter(td, roots=[], secret_encryptor=_sifriraj, secret_decryptor=_desifriraj)
        center._stremio_tokovi_vseh = mock.Mock(return_value=[{"url": "https://splet.primer/f.mp4", "opis": "720p"}])
        center._zivi_naprej = lambda t: t
        item = _vnos(1)
        center._dynamic_items[item["id"]] = item
        center.debrid.lastni_usenet = LastniPonudnik()
        center.debrid.nastavi_indeksator("https://ix.primer", "0123456789abcdef0123456789abcdef")
        center.debrid.nastavi_izbiro("usenet")
        center.usenet_filter.spi = lambda s: None
        return center, item

    def _zapis(self, center, item):
        k = center.usenet_filter_mreze._kljuc(item)
        center.usenet_filter._shrani(k, F.Zapis(F.Izid.NA_VOLJO, center.usenet_filter.ura()))
        return k

    def test_ni_izdaj_pozabi_in_brez_drugih_virov(self):
        with tempfile.TemporaryDirectory() as td:
            center, item = self._center(td)
            k = self._zapis(center, item)
            with mock.patch.object(debrid, "usenet_iskanje", return_value=debrid.IzidIskanja([])):
                r = center.resolve(item["id"])
            self.assertEqual(r["napaka_koda"], "usenet_ni_izdaj")
            center._stremio_tokovi_vseh.assert_not_called()
            self.assertFalse(center.usenet_filter.pokazi(k))

    def test_meja_ne_pozabi(self):
        with tempfile.TemporaryDirectory() as td:
            center, item = self._center(td)
            k = self._zapis(center, item)
            with mock.patch.object(debrid, "usenet_iskanje", return_value=debrid.IzidIskanja(None, True, "meja")):
                r = center.resolve(item["id"])
            self.assertEqual(r["napaka_koda"], "usenet_ne_odgovarja")
            center._stremio_tokovi_vseh.assert_not_called()
            self.assertTrue(center.usenet_filter.pokazi(k))

    def test_izdaja_predvaja_prek_useneta(self):
        with tempfile.TemporaryDirectory() as td:
            center, item = self._center(td)
            z = [U.Zadetek("Film.1080p.x264", "https://ix.primer/getnzb/a", 2 * GB)]
            with mock.patch.object(debrid, "usenet_iskanje", return_value=debrid.IzidIskanja(z)) as isk, \
                    mock.patch.object(center.debrid, "usenet_tok",
                                      return_value=debrid.Izid(url="http://127.0.0.1:1/z/video.mkv",
                                                               ponudnik=debrid.LASTNI_USENET)):
                r = center.resolve(item["id"])
            self.assertEqual(r["url"], "http://127.0.0.1:1/z/video.mkv")
            self.assertTrue(r["usenet"])
            self.assertEqual(isk.call_count, 1, "indeksator enkrat na klik")
            center._stremio_tokovi_vseh.assert_not_called()

    def test_vsi_viri_ni_omejitve(self):
        with tempfile.TemporaryDirectory() as td:
            center, item = self._center(td)
            center.debrid.nastavi_izbiro("")
            with mock.patch.object(debrid, "usenet_iskanje", return_value=debrid.IzidIskanja([])):
                r = center.resolve(item["id"])
            self.assertEqual(r["url"], "https://splet.primer/f.mp4")
            center._stremio_tokovi_vseh.assert_called()


class Katalog(unittest.TestCase):
    """Most mediaKatalog (os_katalog._katalog): filter velja samo za Filme in Serije z izbranim »⚡ Usenet«; izid preverbe
    pride na stran kot mediaKatalogOsvezen z istim kljucem strani (tiha zamenjava)."""

    def _katalog(self, td, izbira="usenet"):
        dogodki = []
        k = os_katalog.Katalog(td, lambda ime, p: dogodki.append((ime, p)), lambda f: f(), lambda *a, **kw: True,
                               lambda u: True, lambda a, b: True, lambda u: True)
        center = os_media.MediaCenter(td, roots=[], secret_encryptor=_sifriraj, secret_decryptor=_desifriraj)
        center.debrid.lastni_usenet = LastniPonudnik()
        center.debrid.nastavi_indeksator("https://ix.primer", "0123456789abcdef0123456789abcdef")
        center.debrid.nastavi_izbiro(izbira)
        ura, vrsta, ix = Ura(), Vrsta(), Indeksator({"tt0000002": []})
        center.__dict__["_usenet_filter"] = UF.UsenetFilter(None, ix, ura=ura, izvajalec=vrsta, spi=ura.spi)
        center.usenet_filter.dbr.odtis_racuna = center.debrid.odtis_racuna
        center.usenet_filter_mreze.casovniki = False
        osvezi = []

        def catalog_hitro(q, kind, genre, page, ob_osvezitvi=None, **kw):
            osvezi.append(ob_osvezitvi)
            return _rezultat([_vnos(1), _vnos(2), _vnos(3)], "kljuc-%s-%d" % (kind, page))
        center.catalog_hitro = catalog_hitro
        k._mc = center
        return k, dogodki, vrsta, ix, osvezi

    def test_film_filtriran_in_osvezen(self):
        with tempfile.TemporaryDirectory() as td:
            k, dogodki, vrsta, ix, osvezi = self._katalog(td)
            r = k._katalog(["", "film", "", 1, "", [], False, [], "", ""])
            self.assertEqual(r["vnosi"], [])
            self.assertEqual(r["usenet_filter"], {"prazno": "iscem"})
            vrsta.pozeni()
            self.assertEqual(ix.klici, ["tt0000001", "tt0000002", "tt0000003"])
            zadnji = [p for ime, p in dogodki if ime == "mediaKatalogOsvezen"][-1]
            self.assertEqual(zadnji["kljuc"], "kljuc-film-1")
            self.assertEqual([x["id"] for x in zadnji["vnosi"]], [_vnos(1)["id"], _vnos(3)["id"]])
            # Osvezitev kataloga v ozadju (ista stran): precisceno, brez novih zahtev.
            osvezi[0]("kljuc-film-1", _rezultat([_vnos(1), _vnos(2), _vnos(3)], "kljuc-film-1"))
            vrsta.pozeni()
            self.assertEqual(len(ix.klici), 3)
            self.assertEqual(len(dogodki[-1][1]["vnosi"]), 2)

    def test_glasba_in_vsi_viri_brez_filtra(self):
        with tempfile.TemporaryDirectory() as td:
            k, dogodki, vrsta, ix, osvezi = self._katalog(td)
            r = k._katalog(["", "glasba", "", 1, "", [], False, [], "", ""])
            self.assertEqual(len(r["vnosi"]), 3)
            self.assertNotIn("usenet_filter", r)
        with tempfile.TemporaryDirectory() as td:
            k, dogodki, vrsta, ix, osvezi = self._katalog(td, "vsi")
            r = k._katalog(["", "film", "", 1, "", [], False, [], "", ""])
            vrsta.pozeni()
            self.assertEqual(ix.klici, [])
            self.assertNotIn("usenet_filter", r)


class Geslo(unittest.TestCase):
    def test_atribut_password(self):
        xml = ('<rss xmlns:newznab="http://www.newznab.com/DTD/2010/feeds/attributes/"><channel>'
               '<item><title>A.1080p</title><link>https://ix.primer/a</link>'
               '<newznab:attr name="size" value="100"/><newznab:attr name="password" value="1"/></item>'
               '<item><title>B.1080p</title><link>https://ix.primer/b</link><newznab:attr name="password" value="0"/></item>'
               '<item><title>C.1080p</title><link>https://ix.primer/c</link></item></channel></rss>')
        z = U.zadetki(xml, "https://ix.primer")
        self.assertEqual([x.geslo for x in z], [True, False, None])


if __name__ == "__main__":
    unittest.main()
