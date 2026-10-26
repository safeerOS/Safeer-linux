"""Preizkusi stevca virov; vsi podatki so izmisljeni."""

import json
import os
import re
import stat
import threading
from datetime import datetime, timedelta

import pytest

from core import stevec_virov
from core.stevec_virov import MAX_BAJTOV, Stevec, percentil

ZDAJ = datetime(2026, 10, 20, 20, 0, 0)


@pytest.fixture
def pot(tmp_path):
    return tmp_path / "podatki" / "stevec.json"


def _ogled(s, vir="webtor", *, uspeh=True, cas=1200, traj=3600, zdaj=ZDAJ, storitev=None):
    return s.zabelezi(vir, uspeh=uspeh, cas_do_slike_ms=cas, trajanje_s=traj, zdaj=zdaj, storitev=storitev)


def _beri(pot):
    return json.loads(pot.read_text(encoding="utf-8"))


def test_kratek_ogled_ne_steje(pot):
    s = Stevec(pot)
    assert _ogled(s, traj=59)
    assert _ogled(s, traj=60)
    v = s.povzetek(zdaj=ZDAJ)["viri"]["webtor"]
    assert v["predvajal"] == 1
    assert v["kratki"] == 1


def test_neuspeh_steje_posebej(pot):
    s = Stevec(pot)
    _ogled(s, uspeh=False, traj=3600)
    p = s.povzetek(zdaj=ZDAJ)
    assert p["viri"]["webtor"]["neuspehi"] == 1
    assert p["skupaj_predvajal"] == 0


@pytest.mark.parametrize("vir", ["neznano", "", None, 42, "WEBTOR", "webtor "])
def test_neznan_vir_gre_v_drugo(pot, vir):
    s = Stevec(pot)
    assert _ogled(s, vir=vir)
    p = s.povzetek(zdaj=ZDAJ)
    assert p["viri"]["drugo"]["predvajal"] == 1
    assert p["viri"]["webtor"]["predvajal"] == 0


def test_cudni_vhodi_ne_dvignejo_izjeme(pot):
    s = Stevec(pot)
    assert s.zabelezi("p2p", uspeh=True, cas_do_slike_ms="x", trajanje_s="y", zdaj=ZDAJ)
    assert s.zabelezi("p2p", uspeh=True, cas_do_slike_ms=None, trajanje_s=None, zdaj=ZDAJ)
    assert s.zabelezi("p2p", uspeh=True, cas_do_slike_ms=1, trajanje_s=100, zdaj="ni datum") is False
    assert isinstance(s.povzetek(dni="x", zdaj="ni datum"), dict)


def test_rotacija_120_dni(pot):
    s = Stevec(pot)
    for n in range(150, -1, -1):
        _ogled(s, zdaj=ZDAJ - timedelta(days=n))
    dnevi = _beri(pot)["dnevi"]
    assert len(dnevi) == 120
    assert min(dnevi) == (ZDAJ - timedelta(days=119)).date().isoformat()
    assert max(dnevi) == ZDAJ.date().isoformat()
    assert s.povzetek(dni=1000, zdaj=ZDAJ)["skupaj_predvajal"] == 120


def test_meja_64_kib(pot, monkeypatch):
    # fsync izklopimo samo zaradi hitrosti; atomarnost preverja drug preizkus.
    monkeypatch.setattr(stevec_virov.os, "fsync", lambda fd: None)
    s = Stevec(pot)
    # Polni vzorci v vseh vedrih napihnejo dan (~5 KiB), da 30 dni preseze mejo.
    for n in range(29, -1, -1):
        zdaj = ZDAJ - timedelta(days=n)
        for vir in stevec_virov.VIRI:
            for i in range(50):
                _ogled(s, vir=vir, cas=100000 + i, zdaj=zdaj, storitev="torbox")
    assert os.path.getsize(pot) <= MAX_BAJTOV
    dnevi = _beri(pot)["dnevi"]
    assert 1 < len(dnevi) < 30
    # Najstarejsi gredo prvi: ostane strnjen niz zadnjih dni.
    assert max(dnevi) == ZDAJ.date().isoformat()
    pricakovani = {(ZDAJ - timedelta(days=n)).date().isoformat() for n in range(len(dnevi))}
    assert set(dnevi) == pricakovani


def test_nacin_0600(pot):
    s = Stevec(pot)
    _ogled(s)
    assert stat.S_IMODE(os.stat(pot).st_mode) == 0o600


@pytest.mark.parametrize(
    "vsebina",
    [
        b"{ni json",
        b"\xff\xfe\x00",
        b"[]",
        b'{"vrsta": "nekaj_drugega", "verzija": 1, "dnevi": {}}',
        b'{"vrsta": "safeer-stevec-virov", "verzija": 99, "dnevi": {}}',
        b'{"vrsta": "safeer-stevec-virov", "verzija": 1, "dnevi": {"x": {}}}',
        b'{"vrsta": "safeer-stevec-virov", "verzija": 1, "dnevi": {"2026-10-20": {"webtor": {"predvajal": -1}}}}',
    ],
)
def test_pokvarjena_datoteka(pot, vsebina):
    pot.parent.mkdir(parents=True)
    pot.write_bytes(vsebina)
    s = Stevec(pot)
    assert (pot.parent / "stevec.json.pokvarjeno").read_bytes() == vsebina
    assert s.povzetek(zdaj=ZDAJ)["skupaj_predvajal"] == 0
    assert _ogled(s)
    assert _beri(pot)["vrsta"] == "safeer-stevec-virov"


def test_pokvarjena_ne_prepise_prejsnje_kopije(pot):
    pot.parent.mkdir(parents=True)
    (pot.parent / "stevec.json.pokvarjeno").write_bytes(b"prva")
    pot.write_bytes(b"druga")
    Stevec(pot)
    assert (pot.parent / "stevec.json.pokvarjeno").read_bytes() == b"prva"
    assert (pot.parent / "stevec.json.pokvarjeno.1").read_bytes() == b"druga"


def test_ponovno_nalaganje(pot):
    s = Stevec(pot)
    _ogled(s, storitev="torbox", vir="debrid_takoj")
    p = Stevec(pot).povzetek(zdaj=ZDAJ)
    assert p["narocnine"]["torbox"]["predvajal"] == 1


@pytest.mark.parametrize("kje", ["write", "replace"])
def test_atomarnost(pot, monkeypatch, kje):
    s = Stevec(pot)
    _ogled(s)
    prej = pot.read_bytes()

    if kje == "replace":
        def napaka(*a, **k):
            raise OSError("simulirana napaka")
        monkeypatch.setattr(stevec_virov.os, "replace", napaka)
    else:
        pravi_fdopen = os.fdopen

        class Pokvarjen:
            def __init__(self, f):
                self._f = f

            def __enter__(self):
                return self

            def __exit__(self, *a):
                self._f.close()

            def fileno(self):
                return self._f.fileno()

            def write(self, b):
                # Polovica zapisana, nato napaka: simulira prekinitev.
                self._f.write(b[: len(b) // 2])
                raise OSError("disk poln")

            def flush(self):
                self._f.flush()

        monkeypatch.setattr(stevec_virov.os, "fdopen", lambda fd, m: Pokvarjen(pravi_fdopen(fd, m)))

    assert _ogled(s, vir="p2p") is False
    assert pot.read_bytes() == prej
    assert json.loads(prej)["vrsta"] == "safeer-stevec-virov"
    ostanki = [p.name for p in pot.parent.iterdir() if p.name.endswith(".tmp")]
    assert ostanki == []


def test_nic_osebnega_v_datoteki(pot):
    s = Stevec(pot)
    # Klicatelj ne more podtakniti vsebine: vse spremenljive vrednosti so omejene.
    _ogled(s, vir="Izmisljeni Film 2099 tt0000001 http://primer.invalid/x", storitev="http://primer.invalid")
    _ogled(s, vir="debrid_takoj", storitev="Izmisljena Serija S01E01")
    _ogled(s, vir="debrid_cakanje", storitev="torbox")
    besedilo = pot.read_text(encoding="utf-8")
    assert "Izmisljen" not in besedilo
    assert "http" not in besedilo
    assert "primer" not in besedilo
    assert not re.search(r"tt\d+", besedilo)
    assert "S01E01" not in besedilo
    # Dovoljeni so samo znani kljuci.
    podatki = json.loads(besedilo)
    assert set(podatki) == {"vrsta", "verzija", "dnevi"}
    for vedra in podatki["dnevi"].values():
        for kljuc, vedro in vedra.items():
            assert kljuc.split("+")[0] in stevec_virov.VIRI
            assert set(vedro) == {"predvajal", "kratki", "neuspehi", "sekunde", "casi"}


def test_povzetek_polja_in_delezi(pot):
    s = Stevec(pot)
    for _ in range(3):
        _ogled(s, vir="webtor", cas=1000, traj=1800)
    _ogled(s, vir="p2p", cas=3000, traj=3600)
    p = s.povzetek(dni=7, zdaj=ZDAJ)
    assert p["skupaj_predvajal"] == 4
    assert p["viri"]["webtor"] == {
        "predvajal": 3,
        "kratki": 0,
        "neuspehi": 0,
        "ure_gledanja": 1.5,
        "mediana_ms": 1000,
        "p90_ms": 1000,
        "delez": 0.75,
    }
    assert p["viri"]["p2p"]["delez"] == 0.25
    assert set(p["viri"]) == set(stevec_virov.VIRI)


def test_priporocilo_premalo_podatkov(pot):
    s = Stevec(pot)
    for _ in range(9):
        _ogled(s, vir="webtor")
    n = s.povzetek(zdaj=ZDAJ)["narocnine"]
    assert n["webtor"]["priporocilo"] == "premalo_podatkov"
    assert n["torbox"]["priporocilo"] == "premalo_podatkov"


def test_priporocilo_obdrzi_in_ni_rabe(pot):
    s = Stevec(pot)
    for _ in range(10):
        _ogled(s, vir="webtor")
    n = s.povzetek(zdaj=ZDAJ)["narocnine"]
    assert n["webtor"]["priporocilo"] == "obdrzi"
    assert n["torbox"]["priporocilo"] == "ni_rabe"


def test_priporocilo_torbox_iz_vseh_treh_virov(pot):
    s = Stevec(pot)
    for _ in range(4):
        _ogled(s, vir="debrid_takoj", storitev="TorBox")
        _ogled(s, vir="usenet_torbox")
        _ogled(s, vir="debrid_cakanje", storitev="torbox")
    _ogled(s, vir="debrid_takoj", storitev="izmisljena")
    n = s.povzetek(zdaj=ZDAJ)["narocnine"]
    assert n["torbox"]["predvajal"] == 12
    assert n["torbox"]["priporocilo"] == "obdrzi"
    assert n["webtor"]["priporocilo"] == "ni_rabe"


def test_percentil_najblizji_rang():
    assert percentil([], 50) is None
    assert percentil([5], 90) == 5
    assert percentil([4, 1, 3, 2], 50) == 2
    assert percentil([3, 1, 2], 50) == 2
    assert percentil(list(range(1, 11)), 90) == 9
    assert percentil(list(range(1, 101)), 90) == 90


def test_niti_8_po_500(pot):
    s = Stevec(pot)
    vrata = threading.Barrier(8)
    napake = []

    def delo(i):
        vrata.wait()
        for k in range(500):
            if not _ogled(s, vir=stevec_virov.VIRI[i % len(stevec_virov.VIRI)], cas=k):
                napake.append(i)

    niti = [threading.Thread(target=delo, args=(i,)) for i in range(8)]
    for n in niti:
        n.start()
    for n in niti:
        n.join()
    assert napake == []
    assert s.povzetek(zdaj=ZDAJ)["skupaj_predvajal"] == 4000
    # Tudi na disku mora biti tocno 4000.
    assert Stevec(pot).povzetek(zdaj=ZDAJ)["skupaj_predvajal"] == 4000
