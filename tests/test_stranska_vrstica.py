"""Stranska vrstica in iskalna lupa okna Safeer OS (lastnik, 19. 10. 2026): ena moznost (trak z ikonami, kot meni
Medijskega centra), gumb vedno na istem mestu, samodejni trak v ozkem oknu, zmanjsano gibanje, barve iz tokens.css.
Delovanje v pravem WebKitu preverja tests/test_stranska_vrstica_zivo.py."""
import os
import re

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _beri(*deli):
    with open(os.path.join(KOREN, *deli), encoding="utf-8") as f:
        return f.read()


HTML, JS, CSS = _beri("assets", "os", "index.html"), _beri("assets", "os", "os.js"), _beri("assets", "os", "os.css")


def _blok(besedilo, zacetek, konec):
    return besedilo[besedilo.index(zacetek):besedilo.index(konec, besedilo.index(zacetek))]


def test_ena_moznost_brez_rocaja():
    for odstranjeno in ("rocajVrstice", "gumbSkrijVrstico", "rocaj-vrstice", "skrij-vrstico", "vrstica-skrita"):
        assert odstranjeno not in HTML + JS + CSS, odstranjeno
    assert 'id="gumbVrstica" type="button" aria-controls="stranska" aria-expanded="true"' in HTML
    assert ".znamka .skrci-vrstico { order: -1;" in CSS, "gumb levo zgoraj, ime ga ne prekriva"


def test_samodejno_in_zapomnjeno():
    vrstica = _blok(JS, "var VRSTICA_KLJUC", "  function $(id)")
    assert 'var VRSTICA_KLJUC = "safeer_vrstica", VRSTICA_MEJA = 1200;' in vrstica
    assert "function vrsticaSkrcena() { return vrsticaIzbira === \"skrcena\" || vrsticaOzko(); }" in vrstica
    # Ozko okno: razsiritev je zacasna (nic se ne shrani), siroko: izbira gre v localStorage.
    assert "vrsticaPlava = !vrsticaPlava;      // ozko okno: zacasno, nic se ne shrani" in vrstica
    assert "try { localStorage.setItem(VRSTICA_KLJUC, vrsticaIzbira); } catch (e) {}" in vrstica
    # Dotik: poteg z levega roba.
    assert 'if (e.pointerType === "mouse") return;' in vrstica and "dx > 60" in vrstica


def test_vsebina_ne_skoci_in_zmanjsano_gibanje():
    assert "#glavno { grid-column: 2; }" in CSS
    assert "body.vrstica-plava:not(.nacin-splet) #stranska {\n  position: fixed;" in CSS
    gibanje = _blok(CSS, "@media (prefers-reduced-motion: no-preference) {\n  /* Samo po prvem izrisu", "@keyframes vrstica-noter")
    assert "body.vrstica-gibanje #aplikacija { transition" in gibanje and "animation: vrstica-noter" in gibanje
    assert "@media (prefers-reduced-motion: no-preference) { .iskanje { transition:" in CSS


def test_nacin_splet_meri_razsirjeno():
    so = _beri("safeer_os.py")
    assert "if(!b.classList.contains('nacin-splet'))b.classList.remove('vrstica-skrcena','vrstica-plava');" in so
    assert "body.nacin-splet .znamka .skrci-vrstico { display: none; }" in CSS


def test_nove_barve_samo_iz_tokens():
    novo = _blok(CSS, "/* Stranska vrstica (os.js vrsticaUredi)", "/* WebKitGTK privzeto riše <select>")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", novo), re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)", novo)


def test_lupa_in_okna_razdelkov():
    assert 'aria-keyshortcuts="Control+K"' in HTML
    assert '<kbd class="bliznjica-lupe" aria-hidden="true">Ctrl+K</kbd>' in HTML
    polje = _blok(JS, "  function poljeIskanjaOkna() {", "  function agentNaVoljo()")
    assert '{ nastavitve: "nastavitveIskanje", zapiski: "zapiskiIskanje", sporocila: "sporocilaIskanje" }[EN_RAZDELEK]' in polje
    tipka = _blok(JS, "  function jeTipkaZaIskanje(e) {", "  // Iskalno polje tega okna")
    assert 'e.key !== " " && !e.ctrlKey && !e.altKey && !e.metaKey && !e.isComposing' in tipka


def test_stikalo_lupe_v_nastavitvah():
    # Namizje QML tece: Nastavitve -> Namizje -> »Zlozena iskalna lupa« (core/priljubljeno.py »lupa«).
    assert 'stikalo("isci", "ndLupa", "lupa", d.lupa !== "razsirjena")' in JS
