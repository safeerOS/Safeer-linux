"""Poslusalci Linka prezivijo prehodno pomanjkanje deskriptorjev (EMFILE).

16./17. 10. 2026 je Safeer OS dosegel mejo 1024 deskriptorjev; poslusalna zanka, ki je ob vsaki OSError iz accept()
koncala, bi ostala mrtva tudi po sprostitvi deskriptorjev (lokalni rele, poti od zunaj, posrednik interneta)."""
import errno
import os
import sys
import unittest
from unittest import mock

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

from core import link_internet_posrednik, link_neposredno, link_rele, os_deskriptorji  # noqa: E402


class _Streznik:
    """accept(): dvakrat EMFILE, nato povezava, nato EBADF (zaprt poslusalec - zanka mora koncati)."""

    def __init__(self):
        self.koraki = [OSError(errno.EMFILE, "Too many open files"), OSError(errno.EMFILE, "Too many open files"),
                       "povezava", OSError(errno.EBADF, "Bad file descriptor")]

    def accept(self):
        k = self.koraki.pop(0) if self.koraki else OSError(errno.EBADF, "zaprt")
        if isinstance(k, OSError):
            raise k
        return mock.Mock(name="tcp"), ("127.0.0.1", 40000)

    def settimeout(self, _t):
        pass

    def close(self):
        pass


class _Niti:
    def __init__(self):
        self.ciljev = []

    def __call__(self, target=None, args=(), **_k):
        nit = mock.Mock()
        nit.start = lambda: self.ciljev.append(target)
        return nit


class PoslusalciPrezivijo(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(os_deskriptorji, "PREMOR_PO_NAPAKI_ACCEPT_S", 0.0)
        p.start()
        self.addCleanup(p.stop)

    def test_lokalni_rele(self):
        r = link_rele.LokalniRele.__new__(link_rele.LokalniRele)
        r.streznik, r.vrata = _Streznik(), 1
        r._tece = True              # zapri() ga ugasne (3d55eab): zanka se konca tudi, ce accept() se vrne povezavo
        r._nas_proces = lambda _n: True
        niti = _Niti()
        with mock.patch.object(link_rele.threading, "Thread", niti):
            r._sprejemaj()
        self.assertEqual(niti.ciljev, [r._kanal])

    def test_od_zunaj(self):
        z = link_neposredno.LokalniOdZunaj.__new__(link_neposredno.LokalniOdZunaj)
        z._tece = True
        niti = _Niti()
        with mock.patch.object(link_neposredno.threading, "Thread", niti), \
                mock.patch.object(link_rele, "_uid_lokalne_povezave", return_value=None):
            z._sprejemaj(_Streznik(), 1, False)
        self.assertEqual(niti.ciljev, [z._povezava])

    def test_posrednik_interneta(self):
        p = link_internet_posrednik.Posrednik.__new__(link_internet_posrednik.Posrednik)
        s = _Streznik()
        p._tece, p._poslusalec = True, s
        niti = _Niti()
        with mock.patch.object(link_internet_posrednik.threading, "Thread", niti):
            p._sprejemaj(s)
        self.assertEqual(niti.ciljev, [p._obravnavaj])

    def test_prehodne_napake(self):
        self.assertTrue(os_deskriptorji.prehodna_napaka_accept(OSError(errno.EMFILE, "x")))
        self.assertFalse(os_deskriptorji.prehodna_napaka_accept(OSError(errno.EBADF, "x")))
        self.assertFalse(os_deskriptorji.prehodna_napaka_accept(OSError(errno.EINVAL, "x")))


if __name__ == "__main__":
    unittest.main()
