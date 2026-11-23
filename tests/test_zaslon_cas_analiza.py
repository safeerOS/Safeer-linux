"""Preizkusi za tools/zaslon_cas_analiza.py (pytest). Vsi podatki so izmisljeni (PRIMER iz
merjenje4s-izhod.md, razdelek 6, in iz njega izpeljani nasprotni primeri)."""

import os
import random
import subprocess
import sys

import pytest

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(KOREN, "tools"))

import zaslon_cas_analiza as z  # noqa: E402

ORODJE = os.path.join(KOREN, "tools", "zaslon_cas_analiza.py")

# PRIMER, IZMISLJENI PODATKI: dobesedno iz razdelka 6 (poskus A, RTT 4 ms).
PC_PRIMER = """\
SafeerZaslonCas dogodek=glava_poslana t_ms=1000000 wall_ms=... seja=7 zvok=1
SafeerZaslonCas dogodek=pred_popen_slika t_ms=1000001 seja=7
SafeerZaslonCas dogodek=po_popen_slika t_ms=1000004 seja=7 pid=4101
SafeerZaslonCas dogodek=pred_popen_zvok t_ms=1000004 seja=7
SafeerZaslonCas dogodek=po_popen_zvok t_ms=1000007 seja=7 pid=4102
SafeerZaslonCas dogodek=niti_zagnane t_ms=1000008 seja=7 niti=2
SafeerZaslonCas dogodek=prvo_branje_zvok t_ms=1000073 seja=7 bajti=1920
SafeerZaslonCas dogodek=prvi_zvok_neprazen t_ms=1000073 seja=7 bajti_skupaj=1920
SafeerZaslonCas dogodek=prvi_bajt_zvok t_ms=1000074 seja=7 bajti=1920 bajti_skupaj=1920
SafeerZaslonCas dogodek=prvi_okvir_slika t_ms=1000151 seja=7 bajti=32768
SafeerZaslonCas dogodek=prvi_bajt_slika t_ms=1000153 seja=7 bajti=32768 bajti_skupaj=32768
SafeerZaslonCas dogodek=zvok_po_5s t_ms=1005073 seja=7 bajti_skupaj=961920
""".splitlines()

TV_PRIMER = """\
SafeerZaslonCas dogodek=glava_prejeta t_ms=52000006 seja=1a2b-1 zvok=1 prek_huba=0
SafeerZaslonCas dogodek=audiotrack_ustvarjen t_ms=52000131 seja=1a2b-1 min_buffer_b=11520 velikost_b=11520 hz=48000 kanali=2 buffer_frames=2880 start_prag_frames=2880 play_state=1 glava_predvajanja=0 podtekov=0
SafeerZaslonCas dogodek=play t_ms=52000132 seja=1a2b-1 bajti_zapisano=0 buffer_frames=2880 ... play_state=3
SafeerZaslonCas dogodek=prvi_write t_ms=52000140 seja=1a2b-1 bajti=1920 sprejeto=1920 ponujeno_skupaj=1920 sprejeto_skupaj=1920 ...
SafeerZaslonCas dogodek=prvi_zvok_neprazen t_ms=52000140 seja=1a2b-1 ponujeno_skupaj=1920 sprejeto_skupaj=1920
SafeerZaslonCas dogodek=prva_slika_v_dekoder t_ms=52000222 seja=1a2b-1 bajti=30211 nal=5
SafeerZaslonCas dogodek=prva_slika_prikazana t_ms=52000249 seja=1a2b-1 velikost=3110400
SafeerZaslonCas dogodek=zvok_po_5s t_ms=52005140 seja=1a2b-1 ponujeno_skupaj=960000 sprejeto_skupaj=205120 buffer_frames=2880 play_state=3 glava_predvajanja=48400 podtekov=0
""".splitlines()


def zamenjaj(vrstice, dogodek, **polja):
    """Kopija vrstic, kjer ima dogodek nova polja (izmisljeni nasprotni primeri)."""
    izid = []
    for v in vrstice:
        if ("dogodek=%s " % dogodek) in v + " ":
            deli = v.split(" ")
            for i, d in enumerate(deli):
                k = d.split("=", 1)[0]
                if k in polja:
                    deli[i] = "%s=%s" % (k, polja[k])
            v = " ".join(deli)
        izid.append(v)
    return izid


def brez(vrstice, *dogodki):
    return [v for v in vrstice if not any(("dogodek=%s " % d) in v + " " for d in dogodki)]


def vr(r, st):
    return r["intervali"][st]["vrednost"]


def oz(r, st):
    return r["intervali"][st]["oznaka"]


# Normalen TV del (13 in 14 normalno) za nasprotna primera.
TV_NORMALEN = zamenjaj(TV_PRIMER, "zvok_po_5s", glava_predvajanja=235000, sprejeto_skupaj=951520)


# ------------------------------------------------------------------ PRIMER

def test_primer_tocne_vrednosti():
    r = z.analiziraj(PC_PRIMER, TV_PRIMER, rtt_ms=4)
    assert r["O"] == 51000004
    assert vr(r, 1) == 66
    assert vr(r, 2) == -79
    assert vr(r, 3) == 1
    assert vr(r, 4) == 0
    assert vr(r, 9) == 62
    assert vr(r, 10) == 65
    assert vr(r, 11) == 109
    assert round(vr(r, 13), 2) == 1.01
    assert round(r["intervali"][13]["primanjkljaj_s"], 2) == 3.99
    assert round(vr(r, 14), 2) == 3.93
    assert oz(r, 13) == "4 s" and oz(r, 14) == "4 s"
    for st in (1, 2, 3, 4, 6, 8, 9, 10, 11, 12, 15):
        assert oz(r, st) == "normalno", st
    assert oz(r, 5) == "ni uporabno"
    assert r["odlocitev"] == "(a)"


def test_primer_vrstica7_je_pol_rtt_ne_nic():
    # Po definiciji O = TV - PC - RTT/2 je #7 = RTT/2 (2 ms), ne 0, kot je pisalo v tabeli.
    r = z.analiziraj(PC_PRIMER, TV_PRIMER, rtt_ms=4)
    assert vr(r, 7) == 2
    assert oz(r, 7) == "normalno"


def test_primer_cli(tmp_path):
    pc, tv = tmp_path / "pc.log", tmp_path / "tv.log"
    pc.write_text("\n".join(PC_PRIMER) + "\n")
    tv.write_text("\n".join(TV_PRIMER) + "\n")
    p = subprocess.run([sys.executable, ORODJE, str(pc), str(tv), "--rtt-ms", "4"],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "O (odmik TV - PC): 51000004 ms" in p.stdout
    assert "ODLOCITEV: (a)" in p.stdout
    assert "1,01 s" in p.stdout and "3,93 s" in p.stdout


# ------------------------------------------------------------------ nasprotna primera

def test_b_poskus_B_ton():
    # Seja se zacne v tisini, ton ob t=1010073, PC neprazen zvok sele 4000 ms pozneje.
    pc = zamenjaj(PC_PRIMER, "prvi_zvok_neprazen", t_ms=1014073)
    r = z.analiziraj(pc, TV_NORMALEN, rtt_ms=4, ton_zacetek=1010073)
    assert r["poskus"] == "B"
    assert vr(r, 5) == 4000 and oz(r, 5) == "4 s"
    assert oz(r, 4) == "ni uporabno" and oz(r, 12) == "ni uporabno"
    assert oz(r, 13) == "normalno" and oz(r, 14) == "normalno"
    assert r["odlocitev"] == "(b)"


def test_b_ton_iz_dnevnika_pc():
    pc = zamenjaj(PC_PRIMER, "prvi_zvok_neprazen", t_ms=1014073) + ["ton_zacetek t_ms=1010073"]
    r = z.analiziraj(pc, TV_NORMALEN, rtt_ms=4)
    assert r["poskus"] == "B" and r["odlocitev"] == "(b)"


def test_b_sunek_bajtov():
    # 1 728 000 B v 5 s = 9 s zvoka: presezek 4 s (vrstica 6).
    pc = zamenjaj(PC_PRIMER, "zvok_po_5s", bajti_skupaj=1728000)
    r = z.analiziraj(pc, TV_NORMALEN, rtt_ms=4)
    assert round(r["intervali"][6]["presezek_s"], 2) == 4.0
    assert oz(r, 6) == "4 s"
    assert r["odlocitev"] == "(b)"


def test_omrezje():
    # Zvok in slika prideta na TV oba ~4 s pozneje (9 in 10), PC je normalen.
    tv = TV_NORMALEN
    for d, t in (("prvi_write", 52004140), ("prvi_zvok_neprazen", 52004140),
                 ("prva_slika_v_dekoder", 52004222), ("prva_slika_prikazana", 52004249),
                 ("zvok_po_5s", 52009140)):
        tv = zamenjaj(tv, d, t_ms=t)
    r = z.analiziraj(PC_PRIMER, tv, rtt_ms=4)
    assert vr(r, 9) == 4062 and oz(r, 9) == "4 s"
    assert vr(r, 10) == 4065 and oz(r, 10) == "4 s"
    assert oz(r, 13) == "normalno"
    assert r["odlocitev"] == "omrezje"


def test_vir_na_pc():
    pc = zamenjaj(PC_PRIMER, "prvi_zvok_neprazen", t_ms=1004073)
    tv = zamenjaj(TV_NORMALEN, "prvi_zvok_neprazen", t_ms=52004140)
    r = z.analiziraj(pc, tv, rtt_ms=4)
    assert oz(r, 4) == "4 s" and oz(r, 12) == "4 s"
    assert r["odlocitev"] == "vir na PC"


def test_vec_pravil_hkrati_ni_odlocitve():
    pc = zamenjaj(PC_PRIMER, "zvok_po_5s", bajti_skupaj=1728000)
    pc = zamenjaj(pc, "prvi_bajt_zvok", t_ms=1004074)
    r = z.analiziraj(pc, TV_NORMALEN, rtt_ms=4)
    assert r["odlocitev"] is None
    assert "nejasno" in r["razlog"]


def test_vse_normalno_brez_vzorca():
    r = z.analiziraj(PC_PRIMER, TV_NORMALEN, rtt_ms=4)
    assert r["odlocitev"] is None
    assert "noben vzorec" in r["razlog"]


# ------------------------------------------------------------------ manjkajoci podatki

def test_manjkajoci_dogodki():
    pc = brez(PC_PRIMER, "glava_poslana", "prvi_bajt_zvok")
    tv = brez(TV_PRIMER, "zvok_po_5s")
    r = z.analiziraj(pc, tv, rtt_ms=4)
    assert r["O"] is None
    for st in (2, 3, 7, 9, 10, 13, 14):
        assert oz(r, st) == "ni podatka", st
    assert r["odlocitev"] is None
    assert "podatkov ni dovolj" in r["razlog"]
    besedilo = z.izpis(r)
    assert "ni podatka" in besedilo


def test_prazna_dnevnika():
    r = z.analiziraj([], [], None)
    assert r["odlocitev"] is None
    assert "podatkov ni dovolj" in r["razlog"]
    assert any("ni veljavnih vrstic" in o for o in r["opozorila"])
    z.izpis(r)


def test_brez_rtt_opozorilo():
    r = z.analiziraj(PC_PRIMER, TV_PRIMER)
    assert r["O"] == 51000006
    assert any("RTT ni podan" in o for o in r["opozorila"])


def test_prvi_write_null():
    tv = zamenjaj(TV_PRIMER, "prvi_write", sprejeto="null")
    r = z.analiziraj(PC_PRIMER, tv, rtt_ms=4)
    assert oz(r, 15) == "sumljivo"


def test_ton_pred_neprazno():
    r = z.analiziraj(PC_PRIMER, TV_NORMALEN, rtt_ms=4, ton_zacetek=1000100)
    assert vr(r, 5) == -27 and oz(r, 5) == "sumljivo"


# ------------------------------------------------------------------ vrstni red, predpone, smeti

@pytest.mark.parametrize("seme", [1, 2, 3, 4, 5])
def test_napacni_vrstni_red(seme):
    pc, tv = list(PC_PRIMER), list(TV_PRIMER)
    random.Random(seme).shuffle(pc)
    random.Random(seme + 100).shuffle(tv)
    r = z.analiziraj(pc, tv, rtt_ms=4)
    assert r["O"] == 51000004
    assert [vr(r, s) for s in (1, 9, 10, 11)] == [66, 62, 65, 109]
    assert r["odlocitev"] == "(a)"


@pytest.mark.parametrize("predpona", [
    "  1234.567  4321  4333 I SafeerZaslonCas: ",            # -v monotonic
    "11-22 16:45:01.123  4321  4333 I SafeerZaslonCas: ",   # -v threadtime
    "I/SafeerZaslonCas( 4321): ",                           # -v brief
    "1763826301.123  4321  4333 I SafeerZaslonCas: ",       # -v epoch
    "",                                                     # gola vrstica
])
def test_predpone_logcat(predpona):
    tv = [predpona + v for v in TV_PRIMER]
    r = z.analiziraj(PC_PRIMER, tv, rtt_ms=4)
    assert r["O"] == 51000004 and r["odlocitev"] == "(a)"


def test_podvojen_dogodek_velja_najzgodnejsi():
    tv = TV_PRIMER + ["SafeerZaslonCas dogodek=prvi_write t_ms=52000900 seja=1a2b-1 bajti=1920 sprejeto=0"]
    r = z.analiziraj(PC_PRIMER, tv, rtt_ms=4)
    assert vr(r, 9) == 62 and oz(r, 15) == "normalno"


def test_smeti():
    smeti = ["--------- beginning of main", "", "   ", "dogodek=", "SafeerZaslonCas dogodek=prvi_write",
             "SafeerZaslonCas dogodek=prvi_write t_ms=abc seja=1a2b-1", "t_ms=5 brez dogodka",
             "x" * 100000, "\x00\x01\x02 dogodek=\x00", "\u0161umniki \u010d\u0107\u017e dogodek=\u017e t_ms=",
             b"\xff\xfe SafeerZaslonCas dogodek=glava_prejeta t_ms=\xff", None, 12345]
    pc = smeti[:6] + PC_PRIMER + smeti[6:]
    tv = smeti[6:] + TV_PRIMER + smeti[:6]
    r = z.analiziraj(pc, tv, rtt_ms=4)
    assert r["O"] == 51000004 and r["odlocitev"] == "(a)"


def test_nakljucni_vhod_ne_pade():
    g = random.Random(42)
    for _ in range(200):
        vrstice = []
        for _ in range(g.randint(0, 30)):
            dolzina = g.randint(0, 80)
            vrstice.append(bytes(g.randint(0, 255) for _ in range(dolzina)))
            vrstice.append("dogodek=%s t_ms=%s seja=%s glava_predvajanja=%s hz=%s" % (
                g.choice(["prvi_write", "zvok_po_5s", "glava_prejeta", "x"]),
                g.choice(["0", "-5", "99999999999999999999", "1e3", ""]),
                g.choice(["", "1", "a"]), g.choice(["0", "-1", "x"]), g.choice(["0", "-48000", "48000"])))
        r = z.analiziraj(vrstice, list(reversed(vrstice)), g.choice([None, 0, 4, -3]),
                         g.choice([None, 0, 10]), g.choice([None, "", ":", "1:a", "zz"]))
        assert isinstance(r, dict)
        assert isinstance(z.izpis(r), str)


# ------------------------------------------------------------------ seje in sidro

PC_STARA = [v.replace("seja=7", "seja=6") for v in zamenjaj(
    zamenjaj(PC_PRIMER, "prvo_branje_zvok", t_ms=1000507), "glava_poslana", t_ms=1000000)]
PC_STARA = [v.replace("t_ms=100", "t_ms=90", 1) for v in PC_STARA]   # 100 s prej
TV_STARA = [v.replace("seja=1a2b-1", "seja=1a2b-0").replace("t_ms=520", "t_ms=519", 1) for v in TV_PRIMER]


def test_podvojene_seje_izbere_zadnjo():
    r = z.analiziraj(PC_STARA + PC_PRIMER, TV_PRIMER + TV_STARA, rtt_ms=4)
    assert r["seja_pc"] == "7" and r["seja_tv"] == "1a2b-1"
    assert r["O"] == 51000004 and vr(r, 1) == 66
    assert any("vec sej" in o for o in r["opozorila"])


def test_podvojene_seje_parameter_seja():
    r = z.analiziraj(PC_STARA + PC_PRIMER, TV_PRIMER + TV_STARA, rtt_ms=4, seja="6:1a2b-0")
    assert r["seja_pc"] == "6" and r["seja_tv"] == "1a2b-0"
    assert vr(r, 1) == 500


def test_seja_samo_pc():
    r = z.analiziraj(PC_STARA + PC_PRIMER, TV_PRIMER + TV_STARA, rtt_ms=4, seja="6")
    assert r["seja_pc"] == "6" and r["seja_tv"] == "1a2b-1"


def test_neobstojeca_seja():
    r = z.analiziraj(PC_PRIMER, TV_PRIMER, rtt_ms=4, seja="99")
    assert any("seja 99 ni v dnevniku" in o for o in r["opozorila"])
    assert oz(r, 1) == "ni podatka"
    assert r["odlocitev"] is None


def test_prek_huba_sidro_ni_veljavno():
    tv = zamenjaj(TV_PRIMER, "glava_prejeta", prek_huba=1)
    r = z.analiziraj(PC_PRIMER, tv, rtt_ms=4)
    assert any("sidro ni veljavno" in o for o in r["opozorila"])
    assert "sidro ni veljavno" in z.izpis(r)
    assert r["sidro_veljavno"] is False
    assert r["odlocitev"] == "(a)"   # (a) ne potrebuje sidra


def test_prek_huba_omrezje_se_ne_uporabi():
    tv = zamenjaj(TV_NORMALEN, "glava_prejeta", prek_huba=1)
    for d, t in (("prvi_write", 52004140), ("prvi_zvok_neprazen", 52004140),
                 ("prva_slika_v_dekoder", 52004222), ("prva_slika_prikazana", 52004249),
                 ("zvok_po_5s", 52009140)):
        tv = zamenjaj(tv, d, t_ms=t)
    r = z.analiziraj(PC_PRIMER, tv, rtt_ms=4)
    assert oz(r, 9) == "4 s"          # izracunano, a ...
    assert r["odlocitev"] != "omrezje"  # ... ne uporabljeno


# ------------------------------------------------------------------ CLI

def test_cli_neobstojeca_datoteka(tmp_path):
    p = subprocess.run([sys.executable, ORODJE, str(tmp_path / "ni.log"), str(tmp_path / "tudi_ni.log")],
                       capture_output=True, text=True, timeout=60)
    assert p.returncode == 3
    assert "ni mogoce prebrati" in p.stdout


def test_cli_napacni_argumenti():
    p = subprocess.run([sys.executable, ORODJE, "--rtt-ms", "abc"], capture_output=True, text=True, timeout=60)
    assert p.returncode == 2


def test_cli_brez_odlocitve(tmp_path):
    pc, tv = tmp_path / "pc.log", tmp_path / "tv.log"
    pc.write_bytes(b"\xff\xfe smeti\n")
    tv.write_text("")
    p = subprocess.run([sys.executable, ORODJE, str(pc), str(tv)], capture_output=True, text=True, timeout=60)
    assert p.returncode == 1
    assert "podatkov ni dovolj" in p.stdout
