"""»Odpri z ...« v Datotekah (core/os_odpri_z.py): programi za vrsto datoteke, zagon z izbranim, privzeti program."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import os_odpri_z as O  # noqa: E402

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
            self.assertEqual(js.count(kljuc + ': "'), 2, "%s v slovenscini in anglescini" % kljuc)


if __name__ == "__main__":
    unittest.main()
