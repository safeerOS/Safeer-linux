"""Dve poti v safeer_mint.py, ki sta zaradi manjkajocega imena tiho padli (pyflakes: undefined name).

- _ime_pdf: ime datoteke iz Content-Disposition (modul ni uvozil `re`, zato je vedno vzel ime iz naslova).
- apply_font_family: ce WebKit pisavo zavrne, je klic `logger` (ni definiran) prekinil metodo pred apply_css.
"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from safeer_mint import SafeerMintBrowser  # noqa: E402


class _Glave:
    def __init__(self, vrednost):
        self.vrednost = vrednost

    def get_one(self, ime):
        return self.vrednost if ime == "Content-Disposition" else None


class _Odgovor:
    def __init__(self, razpolaganje, uri="https://primer.si/prenos/dokument"):
        self.razpolaganje, self.uri = razpolaganje, uri

    def get_http_headers(self):
        return _Glave(self.razpolaganje)

    def get_uri(self):
        return self.uri


class ImePdf(unittest.TestCase):
    def test_ime_iz_content_disposition(self):
        self.assertEqual(SafeerMintBrowser._ime_pdf(_Odgovor('attachment; filename="porocilo.pdf"')), "porocilo.pdf")

    def test_ime_utf8_iz_content_disposition(self):
        odgovor = _Odgovor("attachment; filename*=UTF-8''%C4%8Dlanek%202026.pdf")
        self.assertEqual(SafeerMintBrowser._ime_pdf(odgovor), "članek 2026.pdf")

    def test_brez_glave_ime_iz_naslova(self):
        self.assertEqual(SafeerMintBrowser._ime_pdf(_Odgovor(None)), "dokument.pdf")


class _Nastavitve:
    def set_default_font_family(self, ime):
        raise RuntimeError("pisava ni na voljo")


class _Pogled:
    def get_settings(self):
        return _Nastavitve()


class _Okno:
    """Dovolj okna za apply_font_family: nastavitve, en zavihek in stevec klicev apply_css."""

    def __init__(self):
        self.config = {"font_family": "serif"}
        self.tabs = {1: {"webview": _Pogled()}}
        self.css = 0

    def apply_css(self):
        self.css += 1


class PisavaZavrnjena(unittest.TestCase):
    def test_zavrnjena_pisava_ne_prekine_css(self):
        okno = _Okno()
        SafeerMintBrowser.apply_font_family(okno)
        self.assertEqual(okno.css, 1)


if __name__ == "__main__":
    unittest.main()
