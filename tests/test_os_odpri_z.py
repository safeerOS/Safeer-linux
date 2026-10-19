"""»Odpri z ...« v Datotekah (core/os_odpri_z.py): programi za vrsto datoteke, zagon z izbranim, privzeti program."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import os_odpri_z as O  # noqa: E402
from besedila_namizja import besedila, stevilo  # noqa: E402 - skupni slovar namizja

IZPIS_MIME = """Default application for “text/plain”: urejevalnik.desktop
Registered applications:
\tpisarna.desktop
\turejevalnik.desktop
\tskrit.desktop
\tterminalski.desktop
\tni-ga-vec.desktop
Recommended applications:
\turejevalnik.desktop
\tpisarna.desktop
"""


def vnos(mapa, ime, vsebina):
    with open(os.path.join(mapa, ime), "w", encoding="utf-8") as f:
        f.write("[Desktop Entry]\nType=Application\n" + vsebina)


class LazniGio:
    def __init__(self, vrsta="text/plain", mime=IZPIS_MIME):
        self.vrsta, self.mime, self.klici = vrsta, mime, []

    def __call__(self, argumenti, cas=6.0):
        self.klici.append(list(argumenti))
        if argumenti[0] == "info":
            return (0, "uri: file:///x\nattributes:\n  standard::content-type: %s\n" % self.vrsta) if self.vrsta else (1, "")
        if argumenti[0] == "mime" and len(argumenti) == 2:
            return 0, self.mime
        return 0, ""


class OdpriZ(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.m = self._tmp.name
        self.programi = os.path.join(self.m, "applications")
        os.mkdir(self.programi)
        vnos(self.programi, "urejevalnik.desktop", "Name=Urejevalnik\nExec=true %U\nIcon=accessories-text-editor\n")
        vnos(self.programi, "pisarna.desktop", "Name=Pisarna\nExec=true %F\nIcon=pisarna\n")
        vnos(self.programi, "skrit.desktop", "Name=Skrit\nExec=true\nNoDisplay=true\n")
        vnos(self.programi, "terminalski.desktop", "Name=Terminalski\nExec=true\nTerminal=true\n")
        vnos(self.programi, "slike.desktop", "Name=Slike\nExec=true %f\n")
        self.datoteka = os.path.join(self.m, "zapiski.txt")
        with open(self.datoteka, "w", encoding="utf-8") as f:
            f.write("x")

    def tearDown(self):
        self._tmp.cleanup()

    def test_izpis_gio_mime(self):
        privzeti, vsi = O.razcleni_mime(IZPIS_MIME)
        self.assertEqual(privzeti, "urejevalnik.desktop")
        self.assertEqual(vsi, ["urejevalnik.desktop", "pisarna.desktop", "skrit.desktop", "terminalski.desktop", "ni-ga-vec.desktop"],
                         "privzeti prvi, nato priporoceni, nato drugi prijavljeni; brez dvojnikov")
        self.assertEqual(O.razcleni_mime("No default applications for “x/y”\nNo registered applications\n"), ("", []))
        # Vrstice, ki niso ime vnosa .desktop, odpadejo (pot, ukaz, karkoli z razmikom).
        self.assertEqual(O.razcleni_mime("Default application for “a/b”: /usr/bin/zlo\nRegistered applications:\n\t../a.desktop\n\trm -rf.desktop\n\tdobro.desktop\n"),
                         ("", ["dobro.desktop"]))

    def test_vrsta_vsebine(self):
        self.assertEqual(O.vrsta_vsebine(self.m, LazniGio()), "inode/directory")
        self.assertEqual(O.vrsta_vsebine(self.datoteka, LazniGio("text/markdown")), "text/markdown")
        self.assertEqual(O.vrsta_vsebine(self.datoteka, LazniGio("")), "text/plain", "brez gio: po koncnici")
        self.assertEqual(O.vrsta_vsebine(os.path.join(self.m, "brez-koncnice"), LazniGio("")), "")
        self.assertEqual(O.vrsta_vsebine(self.datoteka, LazniGio("ni vrsta")), "text/plain")

    def test_programi_za_datoteko(self):
        gio = LazniGio()
        r = O.programi_za(self.datoteka, mape=[self.programi], namizja=["X-Cinnamon"], gio=gio)
        self.assertEqual((r["ok"], r["vrsta"]), (True, "text/plain"))
        self.assertEqual([(p["id"], p["ime"], p["privzet"]) for p in r["programi"]],
                         [("urejevalnik.desktop", "Urejevalnik", True), ("pisarna.desktop", "Pisarna", False)],
                         "skriti, terminalski in odstranjeni programi odpadejo")
        self.assertEqual(r["programi"][0]["ikona"], "accessories-text-editor")
        self.assertEqual(gio.klici[-1], ["mime", "text/plain"])
        self.assertEqual(O.programi_za(os.path.join(self.m, "ni.txt"), mape=[self.programi], gio=gio), {"ok": False, "koda": "ni"})
        # Neznana vrsta: prazen seznam, ne napaka (uporabnik izbere »Drug program ...«).
        r = O.programi_za(self.datoteka, mape=[self.programi], gio=LazniGio(mime="No default applications for “text/plain”\n"))
        self.assertEqual((r["ok"], r["programi"]), (True, []))

    def test_drug_program_samo_tisti_ki_odprejo_datoteko(self):
        vnos(self.programi, "nastavitve.desktop", "Name=Nastavitve zaslona\nExec=nastavitve zaslon\n")
        vnos(self.programi, "z-dejanji.desktop", "Name=Z dejanji\nExec=program\n\n[Desktop Action Novo]\nName=Novo\nExec=program --novo %U\n")
        vsi = O.vsi_programi(mape=[self.programi, os.path.join(self.m, "ni-mape")], namizja=["X-Cinnamon"])
        self.assertEqual([p["id"] for p in vsi], ["pisarna.desktop", "slike.desktop", "urejevalnik.desktop"],
                         "po imenu; brez skritih, terminalskih in tistih, ki datoteke ne sprejmejo (tudi ce jo sprejme le dejanje)")
        self.assertEqual(vsi[0], {"id": "pisarna.desktop", "ime": "Pisarna", "ikona": "pisarna"})
        self.assertTrue(O.sprejme_datoteke(os.path.join(self.programi, "slike.desktop")))
        self.assertFalse(O.sprejme_datoteke(os.path.join(self.programi, "ni.desktop")))

    def test_odpre_z_izbranim(self):
        klici = []

        def zaganjalnik(pot_vnosa, datoteke):
            klici.append((pot_vnosa, list(datoteke)))
            return True
        druga = os.path.join(self.m, "druga.txt")
        open(druga, "w").close()
        gio = LazniGio()
        r = O.odpri_z([self.datoteka, druga, self.datoteka, os.path.join(self.m, "ni.txt")], "pisarna.desktop", False, zaganjalnik,
                      mape=[self.programi], namizja=["X-Cinnamon"], gio=gio)
        self.assertEqual(r, {"ok": True, "privzet": False})
        self.assertEqual(klici, [(os.path.join(self.programi, "pisarna.desktop"), [self.datoteka, druga])])
        self.assertEqual(gio.klici, [], "brez »vedno« se privzeti program ne spremeni")
        # Program, ki se za to vrsto ni prijavil, a je v meniju (»Drug program ...«), je dovoljen.
        self.assertTrue(O.odpri_z([self.datoteka], "slike.desktop", False, zaganjalnik, mape=[self.programi], gio=gio)["ok"])

    def test_vedno_nastavi_privzetega(self):
        gio = LazniGio()
        r = O.odpri_z([self.datoteka], "pisarna.desktop", True, lambda p, d: True, mape=[self.programi], gio=gio)
        self.assertEqual(r, {"ok": True, "privzet": True})
        self.assertEqual(gio.klici[-1], ["mime", "text/plain", "pisarna.desktop"])
        self.assertFalse(O.nastavi_privzetega("ni vrsta", "pisarna.desktop", gio))
        self.assertFalse(O.nastavi_privzetega("text/plain", "/usr/bin/zlo", gio))

    def test_zavrne_vse_drugo(self):
        klici = []
        zag = lambda p, d: klici.append(p) or True  # noqa: E731
        for oznaka in ("", "ni-ga.desktop", "../applications/pisarna.desktop", "/usr/bin/true", "pisarna", "skrit.desktop",
                       "terminalski.desktop", "pisarna.desktop; rm -rf ~"):
            r = O.odpri_z([self.datoteka], oznaka, True, zag, mape=[self.programi], gio=LazniGio())
            self.assertEqual(r, {"ok": False, "koda": "program"}, oznaka)
        self.assertEqual(O.odpri_z([os.path.join(self.m, "ni.txt")], "pisarna.desktop", False, zag, mape=[self.programi]),
                         {"ok": False, "koda": "ni"})
        self.assertEqual(O.odpri_z("ni seznam", "pisarna.desktop", False, zag, mape=[self.programi]), {"ok": False, "koda": "ni"})
        self.assertEqual(klici, [])

    def test_rezerva_gio_launch(self):
        zagnano = []
        izvirni_popen, izvirni_which = O.subprocess.Popen, O.shutil.which
        O.subprocess.Popen = lambda ukaz, **k: zagnano.append(list(ukaz))
        O.shutil.which = lambda ime: "/usr/bin/" + ime
        try:
            r = O.odpri_z([self.datoteka], "pisarna.desktop", False, lambda p, d: False, mape=[self.programi], gio=LazniGio())
            self.assertTrue(r["ok"])
            self.assertEqual(zagnano, [["gio", "launch", os.path.join(self.programi, "pisarna.desktop"), self.datoteka]])
            O.shutil.which = lambda ime: None
            self.assertEqual(O.odpri_z([self.datoteka], "pisarna.desktop", False, None, mape=[self.programi], gio=LazniGio()),
                             {"ok": False, "koda": "zagon"})
        finally:
            O.subprocess.Popen, O.shutil.which = izvirni_popen, izvirni_which

    def test_most_stran_in_paket(self):
        koren = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        def beri(*pot):
            with open(os.path.join(koren, *pot), encoding="utf-8") as f:
                return f.read()
        vir = beri("safeer_os.py")
        glavna, ozadje = vir[vir.index("glavna = {"):vir.index("ozadje = {")], vir[vir.index("ozadje = {"):]
        self.assertIn('"odpriZ": lambda: os_odpri_z.odpri_z(', glavna, "zagon programa na glavni niti (okolje namizja)")
        self.assertIn("self._zazeni_vnos_z)", glavna)
        self.assertIn('"programiZaDatoteko": lambda: os_odpri_z.programi_za(', ozadje, "gio info/mime v ozadju")
        self.assertIn("info.launch([Gio.File.new_for_path(d) for d in datoteke], kontekst)", vir)
        self.assertIn(" os_odpri_z ", beri("packaging", "install_os_payload.sh"))
        js = beri("assets", "os", "delovna.js")
        self.assertIn('m.push([t("odpriZ"), function () { odpriZ(e); }]);', js)
        self.assertIn('klic("programiZaDatoteko", [poti[0]])', js)
        self.assertIn('klic("odpriZ", [poti, p.id, trajno])', js)
        self.assertIn('"programiZaOdpiranje": os_odpri_z.vsi_programi,', ozadje)
        self.assertIn('klic("programiZaOdpiranje")', js)
        for kljuc in ("odpriZ", "privzetProgram", "drugProgram", "vednoSTem", "niProgramaZaVrsto", "odslejZ"):
            self.assertEqual(stevilo(kljuc), 6, "%s v vseh jezikih" % kljuc)


if __name__ == "__main__":
    unittest.main()


def test_izpis_gio_v_jeziku_racunalnika():
    """Flatpak: gio na gostitelju odgovori v jeziku racunalnika (testni PC 14. 10. 2026, slovenscina)."""
    from core import os_odpri_z
    izpis = ("Privzet program za »application/vnd.oasis.opendocument.text«: libreoffice-writer.desktop\n"
             "Vpisani programi:\n\tai.storyteller.wordcraft.desktop\n\tlibreoffice-writer.desktop\n\torg.gnome.FileRoller.desktop\n"
             "Priporočeni programi:\n\tai.storyteller.wordcraft.desktop\n\tlibreoffice-writer.desktop\n")
    privzeti, vsi = os_odpri_z.razcleni_mime(izpis)
    assert privzeti == "libreoffice-writer.desktop"
    assert vsi == ["libreoffice-writer.desktop", "ai.storyteller.wordcraft.desktop", "org.gnome.FileRoller.desktop"]


def test_program_za_shemo():
    import tempfile
    from core import os_odpri_z as oz
    with tempfile.TemporaryDirectory() as d:
        with open(os.path.join(d, "thunderbird.desktop"), "w") as f:
            f.write("[Desktop Entry]\nType=Application\nName=Thunderbird\nExec=thunderbird %u\n")
        izpis = "Default application for “x-scheme-handler/mailto”: thunderbird.desktop\n"
        p = oz.program_za_shemo("mailto", gio=lambda a: (0, izpis), mape=[d], namizja=["X-Cinnamon"])
        assert p == {"oznaka": "thunderbird.desktop", "ime": "Thunderbird"}
        assert oz.program_za_shemo("mailto", gio=lambda a: (1, ""), mape=[d]) is None
        assert oz.program_za_shemo("../x", gio=lambda a: (0, izpis), mape=[d]) is None


# ---------------------------------------------------------------------- GIO v procesu (19. 10. 2026)
# Privzeti programi, »Odpri z« in odpiranje datotek gredo v paketu .deb skozi GIO v procesu (isti klici g_app_info_*, kot
# jih naredita ukaza gio in xdg-open/xdg-mime na Cinnamonu), brez podprocesov. Vsak primer tece v svojem procesu z
# loceno mapo XDG (GIO bazo programov prebere enkrat na proces) in se primerja z ukazom gio v istem okolju.
import json as _json  # noqa: E402
import shutil as _shutil  # noqa: E402
import subprocess as _subprocess  # noqa: E402

import pytest  # noqa: E402

KOREN_GIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _okolje_gio(tmp, namizje="X-Cinnamon", **dodatno):
    """Locena mapa XDG: programi a, b (text/plain, zapisi.sh zapise argumente), c (Exec ni vec), mimeapps.list (b) in
    x-cinnamon-mimeapps.list (a) - namizna datoteka ima po specifikaciji prednost."""
    prog = os.path.join(tmp, "data", "applications")
    os.makedirs(prog)
    os.makedirs(os.path.join(tmp, "config"))
    os.makedirs(os.path.join(tmp, "prazno"))
    zapisi = os.path.join(tmp, "zapisi.sh")
    with open(zapisi, "w") as f:
        f.write('#!/bin/sh\necho "$@" >> "%s"\n' % os.path.join(tmp, "zapis.txt"))
    os.chmod(zapisi, 0o755)
    for ime, exe in (("a", zapisi), ("b", zapisi), ("c", "/nikjer/zbrisan-program")):
        with open(os.path.join(prog, ime + ".desktop"), "w") as f:
            f.write("[Desktop Entry]\nType=Application\nName=%s\nExec=%s %%f\nMimeType=text/plain;\n" % (ime.upper(), exe))
    with open(os.path.join(tmp, "config", "mimeapps.list"), "w") as f:
        f.write("[Default Applications]\ntext/plain=b.desktop\n")
    with open(os.path.join(tmp, "config", "x-cinnamon-mimeapps.list"), "w") as f:
        f.write("[Default Applications]\ntext/plain=a.desktop\n")
    okolje = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": tmp, "XDG_CONFIG_HOME": os.path.join(tmp, "config"),
              "XDG_DATA_HOME": os.path.join(tmp, "data"), "XDG_DATA_DIRS": os.path.join(tmp, "prazno") + ":/usr/share",
              "XDG_CURRENT_DESKTOP": namizje, "LC_ALL": "C.UTF-8"}
    okolje.update(dodatno)
    return okolje


def _v_procesu(okolje, koda):
    r = _subprocess.run([sys.executable, "-c", "import sys, json; sys.path.insert(0, %r)\n%s" % (KOREN_GIO, koda)],
                        env=okolje, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return _json.loads(r.stdout.strip().splitlines()[-1])


def _gio_ukaz(okolje, vrsta):
    r = _subprocess.run(["gio", "mime", vrsta], env=dict(okolje, LC_ALL="C", LANGUAGE="C"), capture_output=True,
                        text=True, timeout=30)
    return list(O.razcleni_mime(r.stdout)) if r.returncode == 0 else None


_PROGRAMI = ("from core import os_odpri_z as O\n"
             "print(json.dumps([O.programi_v_procesu('text/plain'), O._programi_vrste('text/plain', O._gio)]))")


@pytest.mark.skipif(_shutil.which("gio") is None, reason="brez ukaza gio")
@pytest.mark.parametrize("namizje,privzeti", [("X-Cinnamon", "a.desktop"), ("", "b.desktop")])
def test_v_procesu_kot_gio_namizni_mimeapps(tmp_path, namizje, privzeti):
    """Namizni mimeapps (XDG_CURRENT_DESKTOP=X-Cinnamon -> x-cinnamon-mimeapps.list) ima prednost, kot pri ukazu gio."""
    okolje = _okolje_gio(str(tmp_path), namizje)
    v_procesu, prek_vmesnika = _v_procesu(okolje, _PROGRAMI)
    assert v_procesu[0] == privzeti
    assert v_procesu == prek_vmesnika == _gio_ukaz(okolje, "text/plain")


@pytest.mark.skipif(_shutil.which("gio") is None, reason="brez ukaza gio")
def test_v_procesu_odstranjen_program(tmp_path):
    """Privzeti program, ki ga ni vec (Exec ni razresljiv ali vnosa .desktop ni), ni privzet ne na seznamu - kot gio."""
    okolje = _okolje_gio(str(tmp_path))
    for vrstica in ("text/plain=c.desktop\n", "text/plain=odstranjen.desktop;a.desktop\n"):
        with open(os.path.join(okolje["XDG_CONFIG_HOME"], "x-cinnamon-mimeapps.list"), "w") as f:
            f.write("[Default Applications]\n" + vrstica)
        v_procesu, _ = _v_procesu(okolje, _PROGRAMI)
        assert v_procesu == _gio_ukaz(okolje, "text/plain")
        assert "c.desktop" not in v_procesu[1] and "odstranjen.desktop" not in v_procesu[1]
        assert v_procesu[0] in ("a.desktop", "b.desktop")


@pytest.mark.parametrize("paket", [{"FLATPAK_ID": "io.github.memelandfaner.SafeerOS"},
                                   {"APPIMAGE": "/nikjer/Safeer-OS.AppImage", "APPDIR": "/nikjer/appdir"}])
def test_rezerva_ukaz_gio_v_flatpaku(tmp_path, paket):
    """Flatpak: GIO v procesu ne vidi programov racunalnika. AppImage: XDG_DATA_DIRS procesa ima $APPDIR/usr/share
    (packaging/AppRun-os) z nasimi vnosi .desktop (magnet, stremio), ki jih racunalnik nima. V obeh ostane ukaz gio
    (tu lazni v PATH) z okoljem racunalnika."""
    okolje = _okolje_gio(str(tmp_path), **paket)
    lazni = os.path.join(str(tmp_path), "bin")
    os.makedirs(lazni)
    with open(os.path.join(lazni, "gio"), "w") as f:
        f.write('#!/bin/sh\necho "$@" >> "%s/gio-klici.txt"\n'
                'printf "Default application for \\"text/plain\\": rezerva.desktop\\nRegistered applications:\\n'
                '\\trezerva.desktop\\n"\n' % tmp_path)
    os.chmod(os.path.join(lazni, "gio"), 0o755)
    okolje["PATH"] = lazni + ":" + okolje["PATH"]
    v_procesu, prek_vmesnika = _v_procesu(okolje, _PROGRAMI)
    assert v_procesu is None
    assert prek_vmesnika == ["rezerva.desktop", ["rezerva.desktop"]]
    assert open(os.path.join(str(tmp_path), "gio-klici.txt")).read().split() == ["mime", "text/plain"]
    # Odpiranje datoteke v Flatpaku tudi ne gre skozi GIO v procesu (klicatelj uporabi xdg-open).
    assert _v_procesu(okolje, "from core import zasebni_webkit as z\nprint(json.dumps(z.odpri_privzeto('/etc/hostname')))") is False


def test_odpri_privzeto_zazene_privzeti_program(tmp_path):
    """Datoteka se odpre s privzetim programom namizja (x-cinnamon-mimeapps.list: a) v procesu, brez xdg-open."""
    okolje = _okolje_gio(str(tmp_path))
    datoteka = os.path.join(str(tmp_path), "zapiski.txt")
    with open(datoteka, "w") as f:
        f.write("besedilo\n")
    lazni = os.path.join(str(tmp_path), "bin")
    os.makedirs(lazni)
    for ukaz in ("xdg-open", "gio"):        # rezerva se ne sme poklicati
        with open(os.path.join(lazni, ukaz), "w") as f:
            f.write('#!/bin/sh\necho "%s" >> "%s/rezerva.txt"\n' % (ukaz, tmp_path))
        os.chmod(os.path.join(lazni, ukaz), 0o755)
    okolje["PATH"] = lazni + ":" + okolje["PATH"]
    koda = ("from core import os_datoteke\nimport time, os\nok = os_datoteke.odpri(%r)\n"
            "for _ in range(100):\n    time.sleep(0.05)\n    if os.path.exists(%r): break\n"
            "print(json.dumps(ok))" % (datoteka, os.path.join(str(tmp_path), "zapis.txt")))
    assert _v_procesu(okolje, koda) is True
    assert open(os.path.join(str(tmp_path), "zapis.txt")).read().strip() == datoteka
    assert not os.path.exists(os.path.join(str(tmp_path), "rezerva.txt"))


def test_nastavi_privzetega_v_procesu(tmp_path):
    """»Vedno odpri s tem« zapise ~/.config/mimeapps.list kot `gio mime VRSTA PROGRAM`; ponovno branje ga vrne."""
    okolje = _okolje_gio(str(tmp_path), "")
    koda = ("from core import os_odpri_z as O\nok = O.nastavi_privzetega('text/plain', 'a.desktop')\n"
            "print(json.dumps([ok, O.programi_v_procesu('text/plain')[0]]))")
    assert _v_procesu(okolje, koda) == [True, "a.desktop"]
    assert "text/plain=a.desktop" in open(os.path.join(okolje["XDG_CONFIG_HOME"], "mimeapps.list")).read()


def test_sheme_magnet_stremio_skozi_gio_v_procesu():
    """Magnet in stremio (vsak zagon Safeer OS) ne zazeneta vec skripte xdg-mime, razen kot rezervo."""
    with open(os.path.join(KOREN_GIO, "safeer_os.py"), encoding="utf-8") as f:
        vir = f.read()
    telo = vir[vir.index("def magnet_privzeto"):vir.index("def naprave_z_datotekami")]
    assert telo.count("os_odpri_z.programi_v_procesu(vrsta)") == 1
    assert telo.count("os_odpri_z.nastavi_v_procesu(vrsta, nastavi)") == 1
    assert telo.count('"xdg-mime"') == 2                       # rezerva: query in default
