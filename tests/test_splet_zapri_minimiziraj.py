"""Splet na namizju: ✕/Esc takoj ustavi predvajanje, minimiziranje ga ne ustavi, rok sprostitve (17. 11. 2026). Brez GTK."""
import os
import re
import types

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _izvor(pot: str) -> str:
    with open(os.path.join(KOREN, pot), encoding="utf-8") as f:
        return f.read()


def _telo(izvor: str, ime_funkcije: str) -> str:
    m = re.search(r"\n    def %s\(.*?(?=\n    def |\Z)" % re.escape(ime_funkcije), izvor, re.S)
    assert m, ime_funkcije
    return m.group(0)


def test_vsa_besedila_imajo_stiri_elemente_in_opis_minimiziranja():
    izvor = _izvor("safeer_os.py")
    blok = re.search(r"BESEDILA_SPLETA_NA_NAMIZJU = \{(.*?)\n\}", izvor, re.S).group(1)
    vrstice = re.findall(r'"(\w\w)": \((.*)\),', blok)
    assert {j for j, _ in vrstice} == {"sl", "en", "de", "es", "fr", "it"}
    for jezik, vsebina in vrstice:
        elementi = re.findall(r'"((?:[^"\\]|\\.)*)"', vsebina)
        assert len(elementi) == 4, jezik
        assert elementi[3].strip(), jezik


def test_skrij_ustavi_predvajanje_takoj_in_rok_je_dolg():
    telo = _telo(_izvor("safeer_os.py"), "_skrij_splet_na_namizju")
    assert "ustavi_predvajanje()" in telo
    assert telo.index("ustavi_predvajanje()") < telo.index("sprazni_predpomnilnik()")
    assert "SPROSTI_SPLET_PO_S" in telo and "timeout_add_seconds(60" not in telo
    assert int(re.search(r"^SPROSTI_SPLET_PO_S = (\d+)$", _izvor("safeer_os.py"), re.M).group(1)) == 600


def test_minimiziranje_ne_skrije_okna_in_ne_ustavi_predvajanja():
    izvor = _izvor("safeer_os.py")
    vrstica = re.search(r'minimiziraj\.connect\("clicked", (.*)\)\n', izvor).group(1)
    assert "minimize()" in vrstica
    for prepovedano in ("_skrij_splet_na_namizju", "ustavi_predvajanje", "sprosti", "set_visible"):
        assert prepovedano not in vrstica


def test_zapri_gumb_se_vedno_skrije_okno():
    izvor = _izvor("safeer_os.py")
    assert 'zapri.connect("clicked", lambda *_: self._skrij_splet_na_namizju())' in izvor


def test_ustavi_predvajanje_poslje_pavzo_vsem_zavihkom_in_prezivi_napako():
    from core.os_splet import VdelaniSplet
    klici = []

    class Pogled:
        def __init__(self, pokvarjen=False):
            self.pokvarjen = pokvarjen

        def evaluate_javascript(self, skripta, *args):
            if self.pokvarjen:
                raise RuntimeError("zavihek se zapira")
            klici.append(skripta)

    sam = types.SimpleNamespace(zavihki=[{"pogled": Pogled(True)}, {"pogled": Pogled()}, {"pogled": Pogled()}],
                                JS_USTAVI_PREDVAJANJE=VdelaniSplet.JS_USTAVI_PREDVAJANJE)
    assert VdelaniSplet.ustavi_predvajanje(sam) == 2
    assert len(klici) == 2 and all("pause()" in k and "video,audio" in k for k in klici)
