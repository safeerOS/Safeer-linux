"""Global Link: hub zazna mrtvega ali starega poslusalca na releju in se takoj prijavi znova.

Izmerjeno 9. 11. 2026: prenosnik in testni PC sta v dnevniku pisala »hub je dosegljiv prek link.safeer.si«, rele pa
jima klicev ni dostavil (TLS prek releja: casovna omejitev ali HTTP 500); svez poslusalec je pot takoj popravil.
"""
import os
import sys
import time
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from core import link_rele  # noqa: E402


class LazniWs:
    def __init__(self, agent, najvec_pingov=3):
        self.agent, self.pingi, self.zaprt, self.najvec = agent, 0, False, najvec_pingov

    def besedilo(self, niz):
        self.pingi += 1
        if self.pingi >= self.najvec:          # brez popravka bi zanka pingala v nedogled - preizkus jo ustavi
            self.agent._ws = None

    def zapri(self):
        self.zaprt = True


def _agent():
    return link_rele.AgentHuba(vrata=lambda: 1234, vklopljen=lambda: True, krog_json=lambda: {}, dnevnik=lambda s: None)


def test_brez_odgovora_releja_poslusalca_zapre():
    a = _agent()
    ws = LazniWs(a)
    a._ws = ws
    a.zadnji_okvir = time.time() - link_rele.MRTEV_PO_S - 1      # zadnji pong davno
    with mock.patch.object(link_rele.time, "sleep"), mock.patch.object(a, "objavi"):
        a._vzdrzuj(ws)
    assert ws.zaprt and ws.pingi == 0
    assert a._obnovi == "mrtev"


def test_star_poslusalec_se_obnovi_tudi_s_pongom():
    a = _agent()
    ws = LazniWs(a)
    a._ws = ws
    a.zadnji_okvir = time.time()                                  # pong prihaja
    with mock.patch.object(link_rele.time, "sleep"), mock.patch.object(a, "objavi"):
        a._vzdrzuj(ws, zacetek=time.time() - link_rele.OBNOVI_POSLUSALCA_S - 1)
    assert ws.zaprt and a._obnovi == "star"


def test_ziv_poslusalec_ostane():
    a = _agent()
    ws = LazniWs(a)
    a._ws = ws
    with mock.patch.object(link_rele.time, "sleep"), mock.patch.object(a, "objavi"):
        a.zadnji_okvir = time.time()
        a._vzdrzuj(ws)
    assert not ws.zaprt and ws.pingi == 3


class _Ustavi(BaseException):
    pass


def test_obnova_brez_cakanja_in_brez_dnevnika():
    """Po namerni obnovi se hub prijavi takoj (ni 5 s brez poslusalca) in redna obnova ne pise v dnevnik."""
    dnevnik = []
    a = link_rele.AgentHuba(vrata=lambda: 1234, vklopljen=lambda: True, krog_json=lambda: {}, dnevnik=dnevnik.append)
    prijave = []

    class Ws:
        def __init__(self, *a_, **k):
            prijave.append(self)
            if len(prijave) > 2:
                raise _Ustavi()

        def prejmi(self):
            a._obnovi = "star"
            raise ConnectionError("zaprto")

        def zapri(self):
            pass

    spanje = []
    with mock.patch.object(link_rele, "WsOdjemalec", Ws), mock.patch.object(a, "objavi"), \
            mock.patch.object(link_rele.threading, "Thread"), mock.patch.object(link_rele.time, "sleep", spanje.append):
        try:
            a._zanka()
        except _Ustavi:
            pass
    assert len(prijave) == 3
    assert spanje == []
    assert dnevnik == ["[Global Link] hub je dosegljiv prek link.safeer.si"]
