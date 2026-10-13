"""Posrednik DoH: brez Naglovega zadrzevanja (TCP_NODELAY) in dovolj tunelov za velike strani."""
import socket
import unittest
from unittest import mock

from core import doh_proxy as D


class Hitrost(unittest.TestCase):
    def test_nodelay(self):
        v = mock.Mock()
        D._brez_zamika(v)
        v.setsockopt.assert_called_once_with(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def test_nodelay_ne_vrze(self):
        D._brez_zamika(object())

    def test_povezava_brez_zamika(self):
        p = D.LocalDoHProxy(mock.Mock())
        vtic = mock.Mock()
        with mock.patch("socket.create_connection", return_value=vtic):
            self.assertIs(p._vzpostavi_povezavo(mock.Mock(), "93.184.215.14", 443), vtic)
        vtic.setsockopt.assert_called_with(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def test_dovolj_tunelov(self):
        self.assertGreaterEqual(D.NAJVEC_POVEZAV, 256)


if __name__ == "__main__":
    unittest.main()
