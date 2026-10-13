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


import os
import shutil
import subprocess
import time

import pytest


def _caka(o, koncna=("na_racunalniku", "napaka"), cas=60):
    t = time.time()
    while o.stanje not in koncna and time.time() - t < cas:
        time.sleep(0.1)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ni ffmpeg")
def test_ce_nobena_naprava_ne_more_pretvori_racunalnik(tmp_path):
    vir = tmp_path / "v.mkv"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=2560x1440:rate=10", "-t", "1",
                    "-c:v", "mpeg4", str(vir)], check=True)
    pr = lp.Pretvorba(lambda: [], lambda *a: {"ok": False}, datoteke=None, sonda=lambda p: None)
    r = pr.zacni(str(vir))
    o = pr.opravila[r["id"]]
    _caka(o)
    assert o.stanje == "na_racunalniku" and o.odstotek == 100
    assert os.path.basename(o.lokalno) == "v-1080p.mp4" and not os.path.exists(o.lokalno + ".part.mp4")
    v = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,width,height",
                        "-of", "csv=p=0", o.lokalno], capture_output=True, text=True).stdout.strip()
    assert v == "h264,1920,1080"


def test_brez_ffmpeg_ostane_napaka(tmp_path):
    vir = tmp_path / "v.mp4"
    vir.write_bytes(b"x" * 10)
    pr = lp.Pretvorba(lambda: [], lambda *a: {"ok": False}, datoteke=None, sonda=lambda p: None, ffmpeg="")
    o = pr.opravila[pr.zacni(str(vir))["id"]]
    _caka(o)
    assert o.stanje == "napaka" and o.napaka == "ni_naprave"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ni ffmpeg")
def test_pokvarjen_video_pusti_prvotni_razlog(tmp_path):
    vir = tmp_path / "v.mp4"
    vir.write_bytes(b"ni video" * 100)
    pr = lp.Pretvorba(lambda: [], lambda *a: {"ok": False}, datoteke=None, sonda=lambda p: None)
    o = pr.opravila[pr.zacni(str(vir))["id"]]
    _caka(o)
    assert o.stanje == "napaka" and o.napaka == "ni_naprave"
    assert [p.name for p in tmp_path.iterdir()] == ["v.mp4"]


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ni ffmpeg")
def test_skupina_brez_naprav_pretvori_tu(tmp_path):
    for i in (1, 2):
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=10", "-t", "1",
                        "-c:v", "mpeg4", str(tmp_path / f"v{i}.mkv")], check=True)
    pr = lp.Pretvorba(lambda: [], lambda *a: {"ok": False}, datoteke=None, sonda=lambda p: None, cakaj=0.05)
    g = pr.skupine[pr.zacni_vec([str(tmp_path)])["id"]]
    t = time.time()
    while not g.koncana and time.time() - t < 60:
        time.sleep(0.1)
    assert [o.stanje for o in g.opravila] == ["na_racunalniku", "na_racunalniku"]
    assert g.slovar()["uspesno"] == 2
