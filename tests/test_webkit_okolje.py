"""packaging/webkit-okolje.sh: brez izrisovalnika DMA-BUF le na starejsih grafikah Intel; uporabnik ima prednost."""
import os
import subprocess

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _zazeni(tmp_path, kartice, okolje=None):
    for i, (vendor, device) in enumerate(kartice):
        d = tmp_path / "class" / "drm" / f"card{i}" / "device"
        d.mkdir(parents=True)
        (d / "vendor").write_text(vendor + "\n")
        (d / "device").write_text(device + "\n")
    env = {"PATH": os.environ["PATH"], "SAFEER_SYS_KOREN": str(tmp_path), **(okolje or {})}
    r = subprocess.run(["sh", "-c", f'. "{KOREN}/packaging/webkit-okolje.sh"; safeer_webkit_okolje; '
                        'echo "${WEBKIT_DISABLE_DMABUF_RENDERER-ni}"'], env=env, capture_output=True, text=True)
    return r.stdout.strip()


def test_haswell(tmp_path):
    assert _zazeni(tmp_path, [("0x8086", "0x0412")]) == "1"


def test_velike_crke_in_druga_kartica(tmp_path):
    assert _zazeni(tmp_path, [("0x10de", "0x2484"), ("0x8086", "0x0A16")]) == "1"


def test_novejsi_intel_in_amd(tmp_path):
    assert _zazeni(tmp_path, [("0x8086", "0x9a49"), ("0x1002", "0x15d8")]) == "ni"   # Tiger Lake, Raven


def test_uporabnik_ima_prednost(tmp_path):
    assert _zazeni(tmp_path, [("0x8086", "0x0412")], {"WEBKIT_DISABLE_DMABUF_RENDERER": "0"}) == "0"


def test_brez_sysfs(tmp_path):
    assert _zazeni(tmp_path, []) == "ni"


def test_v_paketu():
    besedilo = open(os.path.join(KOREN, "packaging", "install_os_payload.sh")).read()
    assert "webkit-okolje.sh" in besedilo
    assert "webkit-okolje.sh" in open(os.path.join(KOREN, "packaging", "safeer-os-launcher")).read()


def test_v_paketu_brskalnika():
    assert "webkit-okolje.sh" in open(os.path.join(KOREN, "packaging", "install_payload.sh")).read()
    assert "safeer_webkit_okolje" in open(os.path.join(KOREN, "packaging", "safeer-launcher")).read()
