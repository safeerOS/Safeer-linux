"""Obnovitev položaja kataloga po ponovnem izrisu mora biti takojšnja (#vsebina ima scroll-behavior: smooth)."""
import re
from pathlib import Path

OS_JS = (Path(__file__).resolve().parent.parent / "assets" / "os" / "os.js").read_text(encoding="utf-8")


def test_povrni_sidro_izklopi_gladko_drsenje():
    telo = OS_JS.split("function katPovrniSidro", 1)[1].split("function narisiKatalog", 1)[0]
    assert 'style.scrollBehavior = "auto"' in telo
    assert len(re.findall(r"style\.scrollBehavior = prej", telo)) >= 2
