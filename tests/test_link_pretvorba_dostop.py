from core import link_pretvorba as lp


def test_zavrnjen_dostop_ni_ne_odgovori():
    naprave = [{"id": "a", "ime": "Telefon", "zmoznosti": ["files"], "platforma": "phone"}]
    razlogi = {}
    r = lp.razvrsti_naprave(naprave, lambda i, d, p: {"ok": False, "code": "ni_dovoljeno"}, 10, None, razlogi)
    assert r == [] and razlogi["Telefon"].startswith("ni dostopa")


def test_brez_odgovora_ostane():
    naprave = [{"id": "a", "ime": "Telefon", "zmoznosti": ["files"], "platforma": "phone"}]
    razlogi = {}
    lp.razvrsti_naprave(naprave, lambda i, d, p: {"ok": False}, 10, None, razlogi)
    assert razlogi["Telefon"] == "ne odgovori"
