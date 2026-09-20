"""Iskanje drugega Huba po izpadu: hitro (0-3 s, konec ob najdbi) in nato pocasno v ozadju.

Fiksno cakanje je najslabse od obojega: ce je drug Hub na voljo takoj, uporabnik po nepotrebnem
gleda prazen seznam; ce ga ni, pa eno samo iskanje pomeni, da se pozneje prizgana naprava ne
pojavi nikoli. Ti testi cuvajo oboje - zgornjo mejo in to, da iskanje ne preneha.
"""
import unittest

from core import link_iskanje


class Ura:
    """Lazna ura in spanje: cas tece samo, kadar 'spimo' - testi so zato hitri in natancni."""

    def __init__(self):
        self.zdaj = 0.0
        self.spanja = []

    def __call__(self):
        return self.zdaj

    def spi(self, sekunde):
        self.spanja.append(round(sekunde, 3))
        self.zdaj += sekunde


class Iskalec:
    def __init__(self, ura, najde_ob=None):
        self.ura = ura
        self.najde_ob = najde_ob
        self.casi = []
        self.najden = False
        self.neuspehi = 0

    def poskus(self):
        self.casi.append(round(self.ura.zdaj, 3))
        if self.najde_ob is not None and len(self.casi) >= self.najde_ob:
            self.najden = True
            return True
        return False

    def povezave_ni(self):
        return not self.najden

    def ob_neuspehu(self):
        self.neuspehi += 1


def _isci(i, ura, **kw):
    return link_iskanje.isci_hub(i.poskus, i.povezave_ni, i.ob_neuspehu,
                                 spi=ura.spi, ura=ura, **kw)


class HitroIskanje(unittest.TestCase):
    def test_prvi_poskus_gre_takoj(self):
        ura = Ura()
        i = Iskalec(ura, najde_ob=1)
        self.assertTrue(_isci(i, ura))
        self.assertEqual(i.casi, [0.0], "prvi poskus mora iti takoj, brez cakanja")

    def test_konca_takoj_ko_najde(self):
        """Najdba pri drugem poskusu pomeni konec - preostanka do meje ne cakamo."""
        ura = Ura()
        i = Iskalec(ura, najde_ob=2)
        self.assertTrue(_isci(i, ura))
        self.assertEqual(i.casi, [0.0, 0.3])
        self.assertLess(ura.zdaj, 1.0, "po najdbi ne smemo cakati do meje")
        self.assertEqual(i.neuspehi, 0, "ob uspehu ni sporocila »ni naprav«")

    def test_zamiki_so_po_nacrtu_in_znotraj_meje(self):
        ura = Ura()
        i = Iskalec(ura, najde_ob=5)          # najde sele v pocasnem delu
        self.assertTrue(_isci(i, ura))
        self.assertEqual(i.casi[:4], list(link_iskanje.HITRO))
        self.assertLessEqual(i.casi[3], link_iskanje.MEJA,
                             "hitro iskanje mora biti koncano v %s s" % link_iskanje.MEJA)

    def test_ob_neuspehu_javi_enkrat_in_isce_naprej(self):
        ura = Ura()
        i = Iskalec(ura, najde_ob=7)
        self.assertTrue(_isci(i, ura))
        self.assertEqual(i.neuspehi, 1, "»ni naprav« povemo natanko enkrat")
        self.assertEqual(len(i.casi), 7, "pocasno iskanje mora teci naprej")
        self.assertEqual(i.casi[4] - i.casi[3], link_iskanje.POCASNO)

    def test_nikoli_ne_najde_a_povezava_se_vrne_sama(self):
        """Ko se povezava vrne sama (drug del programa), iskanje neha."""
        ura = Ura()
        i = Iskalec(ura, najde_ob=None)
        konci = {"po": 3}

        def povezave_ni():
            return len(i.casi) < konci["po"]

        vrnjeno = link_iskanje.isci_hub(i.poskus, povezave_ni, i.ob_neuspehu, spi=ura.spi, ura=ura)
        self.assertFalse(vrnjeno)
        self.assertEqual(len(i.casi), 3)
        self.assertEqual(i.neuspehi, 0, "ce se povezava vrne, uporabniku ne javljamo neuspeha")

    def test_meja_ustavi_hitri_del_tudi_ce_poskusi_trajajo(self):
        """Ce sam poskus traja dolgo, hitri del neha po meji, ne po vseh zamikih."""
        ura = Ura()
        i = Iskalec(ura, najde_ob=None)
        pravi_poskus = i.poskus

        def pocasen_poskus():
            izid = pravi_poskus()
            ura.zdaj += 1.4        # poskus sam traja 1,4 s
            return izid

        link_iskanje.isci_hub(pocasen_poskus, lambda: len(i.casi) < 4, i.ob_neuspehu,
                              spi=ura.spi, ura=ura)
        hitri = [t for t in i.casi if t <= link_iskanje.MEJA]
        self.assertEqual(len(hitri), 3, "po meji hitrega dela ni vec hitrih poskusov: %s" % i.casi)
        self.assertGreater(i.casi[3], link_iskanje.MEJA, "cetrti poskus je ze pocasno iskanje")


if __name__ == "__main__":
    unittest.main()
