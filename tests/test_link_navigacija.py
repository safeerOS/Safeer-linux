# Obrambno varovalo navigacije Link pogleda (napadalski pregled 13. 11. 2026): most safeerLink je v
# namenskem pogledu z zetonom v TOP_FRAME zaprtju; _na_politiko sme ta pogled zadrzati samo na lokalni
# strani assets/link. Gol startswith je spustil sosednje ime (assets/link-evil) in .. izhod - tak lokalni
# dokument bi dobil window.SafeerLink z veljavnim zetonom. Preizkus pade brez naslov_v_korenu (kanonicna meja).
from core.safeer_link import naslov_v_korenu

KOREN = "/opt/safeer/assets/link"

def test_dovoli_lokalno_stran():
    assert naslov_v_korenu("file://" + KOREN + "/index.html", KOREN)
    assert naslov_v_korenu("file://" + KOREN + "/podmapa/x.html", KOREN)
    assert naslov_v_korenu("file://" + KOREN, KOREN)

def test_zavrni_sosednje_ime():
    assert not naslov_v_korenu("file://" + KOREN + "-evil/x.html", KOREN)

def test_zavrni_izhod_dot_dot():
    assert not naslov_v_korenu("file://" + KOREN + "/../../Prejemi/evil.html", KOREN)

def test_zavrni_splet():
    assert not naslov_v_korenu("http://napadalec.example/x", KOREN)
    assert not naslov_v_korenu("https://napadalec.example/x", KOREN)
