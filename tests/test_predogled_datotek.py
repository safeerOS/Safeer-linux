"""Predogled datotek (core/predogled_datotek.py): vrsta predogleda, nevarne datoteke, varna imena, preciscen HTML,
besedilo iz dokumentov brez LibreOffice in nikoli prazna stran (lastnik, 15. 10. 2026: »Ce je pdf dokument ali doc se
pripravi predogled«)."""
import os
import tempfile
import time
import unittest
import zipfile
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch

from core import predogled_datotek as pd


class Vrsta(unittest.TestCase):
    def test_usmerjanje(self):
        primeri = {
            ("racun.pdf", ""): "pdf", ("x", "application/pdf"): "pdf",
            ("slika.JPG", ""): "slika", ("x", "image/png"): "slika", ("risba.svg", ""): "slika",
            ("pogodba.docx", ""): "dokument", ("star.doc", ""): "dokument", ("tabela.xlsx", ""): "dokument",
            ("t.ods", ""): "dokument", ("p.pptx", ""): "dokument", ("p.odp", ""): "dokument", ("b.rtf", ""): "dokument",
            ("x", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"): "dokument",
            ("makro.docm", ""): "dokument",                 # predogled da (LibreOffice makrov ne zazene), odpiranje s potrditvijo
            ("podatki.csv", ""): "tabela", ("stran.html", ""): "html", ("zapis.txt", ""): "besedilo",
            ("x", "text/plain"): "besedilo", ("posredovano.eml", ""): "posta", ("x", "message/rfc822"): "posta",
            ("namesti.exe", ""): "nevarno", ("racun.pdf.exe", ""): "nevarno", ("x.desktop", ""): "nevarno",
            ("Program.AppImage", ""): "nevarno", ("skripta.js", ""): "nevarno", ("x.jar", ""): "nevarno",
            ("a.sh", ""): "nevarno", ("x", "application/x-msdownload"): "nevarno", ("arhiv.zip", ""): "",
            ("x.tiff", "image/tiff"): "",
        }
        for (ime, tip), vrsta in primeri.items():
            self.assertEqual(pd.vrsta_predogleda(ime, tip), vrsta, (ime, tip))

    def test_nevarne(self):
        for ime in ("a.exe", "A.EXE", "racun.pdf.exe", "x.scr", "x.vbs", "x.desktop", "x.AppImage", "x.jar",
                    "x.sh", "x.docm", "x.xlsm", "x.pptm", "x.lnk", "x.ps1", "x.bat", "x.msi", "x.apk", "x.deb", "x.exe. "):
            self.assertTrue(pd.je_nevarna(ime), ime)
        for ime in ("a.pdf", "a.docx", "a.jpg", "exe.txt", "a.zip"):
            self.assertFalse(pd.je_nevarna(ime), ime)
        self.assertTrue(pd.je_nevarna("racun", "application/x-msdownload; name=x"))

    def test_varno_ime(self):
        self.assertEqual(pd.varno_ime("../../etc/passwd"), "passwd")
        self.assertEqual(pd.varno_ime("..\\..\\x.txt"), "x.txt")
        self.assertEqual(pd.varno_ime("a\x00b\x1f.txt"), "ab.txt")
        self.assertEqual(pd.varno_ime("racun‮gpj.exe"), "racungpj.exe")     # znak za smer pisanja skrije .exe
        self.assertEqual(pd.varno_ime("CON.txt"), "_CON.txt")
        self.assertEqual(pd.varno_ime('a<b>:"|?*.txt'), "ab.txt")
        self.assertEqual(pd.varno_ime(""), "priponka")
        self.assertEqual(pd.varno_ime(".."), "priponka")
        self.assertLessEqual(len(pd.varno_ime("x" * 400 + ".pdf").encode()), 200)


class VarenHtml(unittest.TestCase):
    def test_brez_skript_dogodkov_okvirjev_in_oddaljenih_virov(self):
        html, skrite = pd.varen_html(
            '<p onclick="x()">Zivjo<script>alert(1)</script></p><img src="cid:logo@x"><img src="https://sled.example/p.gif">'
            '<a href="javascript:alert(1)">a</a><a href="https://safeer.si">b</a><iframe src="x">notri</iframe>'
            '<form action="https://x"><input name=a></form><style>@import url(https://x/a.css); p{background:url(https://y/b.png)}</style>'
            '<meta http-equiv="refresh" content="0;url=https://x"><object data="x"></object><svg><script>a()</script></svg>'
            '<div style="background:url(cid:logo@x)">d</div><img src="data:image/png;base64,AAAA"><img src="data:image/svg+xml,x">',
            {"logo@x": "file:///predpomnilnik/logo.png"})
        for prepovedano in ("<script", "onclick", "javascript:", "<iframe", "notri", "<form", "<input", "@import", "https://sled",
                            "https://y", "<meta", "<object", "alert", "data:image/svg"):
            self.assertNotIn(prepovedano, html, prepovedano)
        self.assertIn('src="file:///predpomnilnik/logo.png"', html)
        self.assertIn('href="https://safeer.si"', html)
        self.assertIn('url(&quot;file:///predpomnilnik/logo.png&quot;)', html)     # slog v atributu, ubezan
        self.assertIn("data:image/png;base64,AAAA", html)
        self.assertEqual(skrite, 2)

    def test_stran_ima_csp(self):
        s = pd.stran("<p>x</p>")
        self.assertIn("Content-Security-Policy", s)
        self.assertIn("default-src 'none'", s)
        self.assertLess(s.index("Content-Security-Policy"), s.index("<p>x</p>"))


def _docx(pot: Path, odstavki):
    xml = ('<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>' +
           "".join('<w:p><w:r><w:t>%s</w:t></w:r><w:r><w:tab/><w:t>x</w:t></w:r></w:p>' % o for o in odstavki) + "</w:body></w:document>")
    with zipfile.ZipFile(pot, "w") as z:
        z.writestr("word/document.xml", xml)


class Priprava(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.m = Path(self.d.name)
        self.okolje = patch.dict(os.environ, {"HOME": str(self.m), "XDG_CACHE_HOME": str(self.m / ".cache")})
        self.okolje.start()

    def tearDown(self):
        self.okolje.stop()
        self.d.cleanup()

    def test_pdf_in_slika(self):
        (self.m / "a.pdf").write_bytes(b"%PDF-1.4")
        self.assertEqual(pd.pripravi(str(self.m / "a.pdf"))["nacin"], "pdf")
        (self.m / "s.png").write_bytes(b"\x89PNG")
        r = pd.pripravi(str(self.m / "s.png"))
        self.assertEqual((r["nacin"], r["vrsta"]), ("html", "slika"))
        self.assertIn("<img src=\"file://", r["html"])

    def test_dokument_brez_libreoffice_besedilo(self):
        _docx(self.m / "p.docx", ["Prvi odstavek", "Drugi čšž"])
        r = pd.pripravi(str(self.m / "p.docx"), najdi=lambda _ime: None)
        self.assertEqual(r["nacin"], "html")
        self.assertIn("Prvi odstavek", r["html"])
        self.assertIn("Drugi čšž", r["html"])
        self.assertIn(pd.besedilo("brez_oblike"), r["html"])

    def test_dokument_brez_libreoffice_in_brez_besedila(self):
        (self.m / "star.doc").write_bytes(b"\xd0\xcf\x11\xe0 binarno")
        r = pd.pripravi(str(self.m / "star.doc"), najdi=lambda _ime: None)
        self.assertIn(pd.besedilo("brez_lo"), r["html"])            # jasno sporocilo, ne prazno okno

    def test_libreoffice_v_pdf_s_casovno_omejitvijo(self):
        _docx(self.m / "p.docx", ["x"])
        ukazi = []

        def zazeni(u, cas):
            ukazi.append((u, cas))
            izhod = u[u.index("--outdir") + 1]
            Path(izhod, "p.pdf").write_bytes(b"%PDF")
            return 0
        with patch("core.os_pretvorba_datotek._zazeni_s_koncem", side_effect=zazeni):
            r = pd.pripravi(str(self.m / "p.docx"), najdi=lambda ime: "/usr/bin/" + ime if ime == "soffice" else None)
            r2 = pd.pripravi(str(self.m / "p.docx"), najdi=lambda ime: "/usr/bin/" + ime if ime == "soffice" else None)
        self.assertEqual(r["nacin"], "pdf")
        self.assertTrue(r["pot"].endswith("p.pdf"))
        self.assertEqual(r2["pot"], r["pot"])
        self.assertEqual(len(ukazi), 1)                              # drugic iz predpomnilnika
        u, cas = ukazi[0]
        self.assertIn("--headless", u)
        self.assertEqual(u[u.index("--convert-to") + 1], "pdf")
        self.assertEqual(cas, pd.CAS_PRETVORBE_S)

    def test_pretvorba_v_vnosu_priponke_prezivi_lru_dotik(self):
        """Izmerjeno 15. 10. 2026: drugo odprtje je ponovno zagnalo LibreOffice, ker je dotik za LRU spremenil mtime."""
        _docx(self.m / "p.docx", ["x"])
        vnos = self.m / "vnos"
        vnos.mkdir()
        klici = []

        def zazeni(u, cas):
            klici.append(u)
            Path(u[u.index("--outdir") + 1], "p.pdf").write_bytes(b"%PDF")
            return 0
        najdi = lambda ime: "/usr/bin/soffice" if ime == "soffice" else None  # noqa: E731
        with patch("core.os_pretvorba_datotek._zazeni_s_koncem", side_effect=zazeni):
            r1 = pd.pripravi(str(self.m / "p.docx"), najdi=najdi, mapa_pretvorbe=str(vnos))
            os.utime(self.m / "p.docx", (time.time() + 50, time.time() + 50))
            r2 = pd.pripravi(str(self.m / "p.docx"), najdi=najdi, mapa_pretvorbe=str(vnos))
        self.assertEqual(len(klici), 1)
        self.assertEqual(r1["pot"], r2["pot"])
        self.assertEqual(os.path.dirname(r1["pot"]), str(vnos))
        self.assertEqual(os.stat(r1["pot"]).st_mode & 0o777, 0o600)

    def test_libreoffice_prepocasi(self):
        import subprocess
        _docx(self.m / "q.docx", ["Besedilo ostane"])
        with patch("core.os_pretvorba_datotek._zazeni_s_koncem", side_effect=subprocess.TimeoutExpired("soffice", 1)):
            r = pd.pripravi(str(self.m / "q.docx"), najdi=lambda ime: "/usr/bin/soffice" if ime == "soffice" else None)
        self.assertIn("Besedilo ostane", r["html"])

    def test_besedilo_csv_html(self):
        (self.m / "z.txt").write_text("<b>ni oznaka</b>", encoding="utf-8")
        self.assertIn("&lt;b&gt;ni oznaka", pd.pripravi(str(self.m / "z.txt"))["html"])
        (self.m / "t.csv").write_text("ime;znesek\nAna;12\n", encoding="utf-8")
        r = pd.pripravi(str(self.m / "t.csv"))["html"]
        self.assertIn("<td>Ana</td><td>12</td>", r)
        (self.m / "s.html").write_text("<h1>Naslov</h1><script>alert(1)</script>", encoding="utf-8")
        r = pd.pripravi(str(self.m / "s.html"))["html"]
        self.assertIn("<h1>Naslov</h1>", r)
        self.assertNotIn("alert", r)

    def test_nevarno_in_neznano_nikoli_prazno(self):
        r = pd.pripravi("", "namesti.exe")
        self.assertIn(pd.besedilo("nevarno_naslov"), r["html"])
        (self.m / "a.zip").write_bytes(b"PK")
        r = pd.pripravi(str(self.m / "a.zip"))
        self.assertIn(pd.besedilo("brez_naslov"), r["html"])
        self.assertIn("ZIP", r["html"])

    def test_posredovano_pismo_s_sliko_v_vrstici(self):
        m = EmailMessage()
        m["From"], m["Subject"] = "Ana <ana@example.test>", "Zapisnik"
        m.set_content("besedilo")
        m.add_alternative('<p>Glej <img src="cid:slika1"></p><script>x()</script>', subtype="html")
        m.get_payload()[1].add_related(b"\x89PNG", "image", "png", cid="<slika1>")
        m.add_attachment(b"%PDF", maintype="application", subtype="pdf", filename="priloga.pdf")
        (self.m / "f.eml").write_bytes(m.as_bytes())
        r = pd.pripravi(str(self.m / "f.eml"))["html"]
        self.assertIn("Zapisnik", r)
        self.assertIn('src="data:image/png;base64,', r)
        self.assertIn("priloga.pdf", r)
        self.assertNotIn("x()", r)

    def test_jeziki(self):
        for j in ("sl", "en", "de", "es", "fr", "it"):
            self.assertEqual(set(pd.BESEDILA_PREDOGLEDA[j]), set(pd.BESEDILA_PREDOGLEDA["sl"]), j)

    def test_ciscenje_predpomnilnika(self):
        star = Path(pd.pot_v_predpomnilniku("a", "star.pdf"))
        nov = Path(pd.pot_v_predpomnilniku("b", "nov.pdf"))
        star.write_bytes(b"x" * 10)
        nov.write_bytes(b"y" * 10)
        os.utime(star, (time.time() - 8 * 24 * 3600,) * 2)
        self.assertEqual(pd.pocisti_predpomnilnik(), 1)
        self.assertFalse(star.exists())
        self.assertTrue(nov.exists())
        self.assertEqual(pd.pocisti_predpomnilnik(najvec=5), 1)     # prek meje gredo najstarejse
        self.assertFalse(nov.exists())


if __name__ == "__main__":
    unittest.main()
