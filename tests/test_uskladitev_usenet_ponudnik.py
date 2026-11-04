"""secrets.sync: ponudnik Usenet z geslom gre na naprave ozjega kroga in z njih sem (lastnik 4. 11. 2026: »API kljuc,
ki ga vnesem na eni napravi, velja za vse naprave«). Prej ga je namizje prezrlo - geslo je bilo treba vpisati na vsaki
napravi. Oblika vrednosti je Androidova (UskladitevKljucev.kt, naloga 42 G): {"ponudnik": {...}, "geslo": "..."}.
Brez omrezja: zbirka skrivnosti je nadomescena, prijave ni."""
import json
import logging
from unittest import mock

import pytest

from core import usenet_nntp as nntp
from core import usenet_ponudnik as up
from core import uskladitev_kljucev_pravila as P
from core.uskladitev_kljucev_mediji import VirMedijev
from core.uskladitev_kljucev_pravila import Zapis

GESLO = "Lazno-Geslo-sinh-91!"
PONUDNIK = up.Ponudnik(gostitelj="news.primer.invalid", uporabnik="uporabnik.primer91", vrata=563, ime="Primer")


class LaznaZbirka:
    def __init__(self):
        self.vnosi = {}

    def shrani(self, k, v):
        self.vnosi[k] = v
        return True

    def preberi(self, k):
        return self.vnosi.get(k)

    def pozabi(self, k):
        self.vnosi.pop(k, None)


class LazniMc:
    debrid = None

    def _load(self):
        return {}


@pytest.fixture
def napravi(monkeypatch, tmp_path):
    """Dve »napravi« v istem procesu: vsaka svoja datoteka in svoja zbirka (zamenjamo jo ob preklopu)."""
    zbirki = {"a": LaznaZbirka(), "b": LaznaZbirka()}
    nntp.nastavi_shrambo_zapaha(str(tmp_path / "zapah"))
    for m in (nntp._ZAVRNJENI, nntp._NEZNANE, up._PREVERBE, up._V_POMNILNIKU):
        m.clear()

    def na(ime):
        monkeypatch.setattr(up, "skrivnosti", zbirki[ime])
        return str(tmp_path / ime / "usenet-ponudnik.json")
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    return na, zbirki


def _vir(pot):
    v = VirMedijev(lambda: LazniMc(), pot)
    # Debrid in dodatki tu niso del preizkusa.
    v._dbr = lambda: mock.Mock(kljuc=lambda p: None, kljuc_velja=lambda p: False, indeksator=lambda: None,
                               stanje_kljuca=lambda p: None, _nastavitve=lambda: {})
    return v


def test_vnos_na_eni_napravi_velja_na_drugi(napravi):
    na, zbirki = napravi
    pot_a = na("a")
    assert up.za_uskladitev(pot_a) == (up.USKLADITEV_BREZ, None)
    up.shrani_ponudnika(PONUDNIK, GESLO, pot_a)
    vrednosti, neznani = _vir(pot_a).trenutne()
    v = vrednosti[P.KLJUC_USENET_PONUDNIK]
    assert json.loads(v) == {"ponudnik": PONUDNIK.v_slovar(), "geslo": GESLO}    # oblika kot na Androidu
    assert P.KLJUC_USENET_PONUDNIK not in neznani

    pot_b = na("b")
    vir_b = _vir(pot_b)
    z = Zapis(P.KLJUC_USENET_PONUDNIK, 5, "n-a", False, v)
    assert vir_b.veljavna_vrednost(z.kljuc, z.vrednost)
    with mock.patch.object(up, "_odkleni_racun") as odkleni:
        assert vir_b.pripravi(z)()
    odkleni.assert_not_called()                     # prejem ni uporabnikov vpis: zapaha ne odklene
    assert up.preberi_ponudnika(pot_b) == PONUDNIK
    assert zbirki["b"].preberi(PONUDNIK.kljuc_gesla) == GESLO       # geslo samo v zbirko, ne v datoteko
    with open(pot_b, encoding="utf-8") as f:
        assert GESLO not in f.read()
    assert up.za_uskladitev(pot_b) == (up.USKLADITEV_VREDNOST, v)

    # Odstranitev na drugi napravi (grob) odstrani ponudnika in geslo tudi tu.
    assert vir_b.pripravi(Zapis(P.KLJUC_USENET_PONUDNIK, 6, "n-a", True, ""))()
    assert up.preberi_ponudnika(pot_b) is None and zbirki["b"].vnosi == {}


def test_zavrnjeno_geslo_ni_potrjeno(napravi):
    """Zbirka gesel zavrne (zaklenjena, brez Secret Service): prejem vrne False, da ga uskladitev ne potrdi in poskusi
    znova - prej je vrnil True in zapis je veljal za prejetega brez gesla (CodeRabbit, 4. 11. 2026)."""
    na, zbirki = napravi
    pot_a = na("a")
    up.shrani_ponudnika(PONUDNIK, GESLO, pot_a)
    v = _vir(pot_a).trenutne()[0][P.KLJUC_USENET_PONUDNIK]
    pot_b = na("b")
    zbirki["b"].shrani = lambda k, g: False
    vir_b = _vir(pot_b)
    assert vir_b.pripravi(Zapis(P.KLJUC_USENET_PONUDNIK, 5, "n-a", False, v))() is False
    assert vir_b.obnovi(P.KLJUC_USENET_PONUDNIK, v) is False


def test_brez_berljivega_gesla_neznan_brez_groba(napravi):
    na, zbirki = napravi
    pot = na("a")
    up.shrani_iz_kroga(PONUDNIK, pot)            # prejet po lists.get, brez gesla
    vrednosti, neznani = _vir(pot).trenutne()
    assert P.KLJUC_USENET_PONUDNIK not in vrednosti and P.KLJUC_USENET_PONUDNIK in neznani


@pytest.mark.parametrize("ponudnik,geslo,dodatno", [
    (dict(PONUDNIK.v_slovar(), gostitelj="192.168.1.20", tls=False, nevarno_brez_tls=True), GESLO, {}),  # brez TLS, doma
    (dict(PONUDNIK.v_slovar(), gostitelj="10.0.0.5"), GESLO, {}),                  # domace omrezje (pregled 118 S1)
    (dict(PONUDNIK.v_slovar(), gostitelj="nas.lan"), GESLO, {}),
    (dict(PONUDNIK.v_slovar(), tuje="x"), GESLO, {}),                             # neznano polje
    (PONUDNIK.v_slovar(), "", {}),                                                # brez gesla
    (PONUDNIK.v_slovar(), "a\r\nQUIT", {}),                                       # nevarna poverilnica
    (PONUDNIK.v_slovar(), GESLO, {"vec": 1}),                                     # tuj kljuc v vrednosti
])
def test_neveljavna_vrednost_se_zavrne(napravi, ponudnik, geslo, dodatno):
    na, _z = napravi
    pot = na("b")
    vir = _vir(pot)
    v = json.dumps(dict({"ponudnik": ponudnik, "geslo": geslo}, **dodatno))
    assert not vir.veljavna_vrednost(P.KLJUC_USENET_PONUDNIK, v)
    assert vir.pripravi(Zapis(P.KLJUC_USENET_PONUDNIK, 5, "n-a", False, v)) is None
    assert up.preberi_ponudnika(pot) is None


def test_domaci_streznik_se_ne_poslje(napravi):
    """TLS na naslovu domacega omrezja: prejemnik ga zavrne, zato posiljatelj vrne NEZNAN (prej VREDNOST z geslom)."""
    na, _z = napravi
    pot = na("a")
    domaci = up.Ponudnik(gostitelj="10.0.0.5", uporabnik="uporabnik.primer91", vrata=563, ime="Doma")
    up.shrani_ponudnika(domaci, GESLO, pot)
    assert up.za_uskladitev(pot) == (up.USKLADITEV_NEZNAN, None)
    vrednosti, neznani = _vir(pot).trenutne()
    assert P.KLJUC_USENET_PONUDNIK not in vrednosti and P.KLJUC_USENET_PONUDNIK in neznani


def test_brez_poti_se_ne_usklajuje(napravi):
    na, _z = napravi
    pot = na("a")
    up.shrani_ponudnika(PONUDNIK, GESLO, pot)
    vir = VirMedijev(lambda: LazniMc())          # Windows in stari klici: brez poti nic ne posljemo in ne sprejmemo
    assert not vir.veljavna_vrednost(P.KLJUC_USENET_PONUDNIK, up.za_uskladitev(pot)[1])


def test_geslo_ni_v_dnevniku(napravi, caplog):
    na, _z = napravi
    caplog.set_level(logging.DEBUG)
    pot_a = na("a")
    up.shrani_ponudnika(PONUDNIK, GESLO, pot_a)
    v = _vir(pot_a).trenutne()[0][P.KLJUC_USENET_PONUDNIK]
    vir_b = _vir(na("b"))
    vir_b.pripravi(Zapis(P.KLJUC_USENET_PONUDNIK, 5, "n-a", False, v))()
    vir_b.ime_kljuca(P.KLJUC_USENET_PONUDNIK, v, "")
    assert GESLO not in caplog.text and PONUDNIK.uporabnik not in caplog.text


def test_safeer_control_poda_pot_in_pazi_nanjo():
    import os
    koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(koren, "safeer_control.py"), encoding="utf-8") as f:
        s = f.read()
    assert 'UM.VirMedijev(dobi_mc, pot_usenet)' in s
    assert 'pot_usenet = os.path.join(mapa, "usenet-ponudnik.json")' in s
    assert 'os.path.join(mapa, "media.json"), pot_usenet]' in s
    from core import usenet_vezava
    assert usenet_vezava.IME_DATOTEKE == "usenet-ponudnik.json"
