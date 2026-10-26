"""Poganja VSE skupne primere iz stevec-virov.json proti core/stevec_virov.py.

Zakaj: isti primeri preverjajo tudi Kotlin (tests/StevecVirovTest.kt), zato
morata obe izvedbi dati enak povzetek. Vse vrednosti so izmisljene.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Koren repozitorija na pot, da core najdemo tudi brez conftest ali namestitve.
_KOREN = Path(__file__).resolve().parent.parent
if str(_KOREN) not in sys.path:
    sys.path.insert(0, str(_KOREN))

from core.stevec_virov import Stevec  # noqa: E402

POT = Path(__file__).parent / "skupni-primeri" / "stevec-virov.json"
DOKUMENT = json.loads(POT.read_text(encoding="utf-8"))
PRIMERI = DOKUMENT["primeri"]


def _podmnozica(pricakovano, dejansko, pot="povzetek"):
    """Primerja samo navedene kljuce; vrednost IN vrsta (1 ni 1.0)."""
    if isinstance(pricakovano, dict):
        assert isinstance(dejansko, dict), f"{pot} ni slovar"
        for kljuc, vrednost in pricakovano.items():
            assert kljuc in dejansko, f"{pot}.{kljuc} manjka"
            _podmnozica(vrednost, dejansko[kljuc], f"{pot}.{kljuc}")
    else:
        assert dejansko == pricakovano, f"{pot}: {dejansko!r} != {pricakovano!r}"
        assert type(dejansko) is type(pricakovano), f"{pot}: vrsta {type(dejansko).__name__}"


def test_dokument():
    assert DOKUMENT["verzija"] == 1
    assert PRIMERI, "ni primerov"
    imena = [p["ime"] for p in PRIMERI]
    assert len(imena) == len(set(imena)), "imena primerov niso enolicna"


@pytest.mark.parametrize("primer", PRIMERI, ids=[p["ime"] for p in PRIMERI])
def test_primer(tmp_path, primer):
    s = Stevec(tmp_path / "stevec.json")
    for i, z in enumerate(primer["zapisi"]):
        assert s.zabelezi(
            z["vir"],
            uspeh=z["uspeh"],
            cas_do_slike_ms=z["cas_do_slike_ms"],
            trajanje_s=z["trajanje_s"],
            zdaj=datetime.fromisoformat(z["zdaj"]),
            storitev=z.get("storitev"),
        ), f"zapis {i} vrnil False"
    klic = primer["povzetek"]
    dejansko = s.povzetek(dni=klic["dni"], zdaj=datetime.fromisoformat(klic["zdaj"]))
    _podmnozica(primer["pricakovano"], dejansko)
