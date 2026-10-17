import os

from core import splet_varuh as v


def _proces(koren, pid, comm, rss_mb, ppid):
    d = koren / str(pid)
    d.mkdir()
    (d / "comm").write_text(comm + "\n")
    (d / "status").write_text(f"Name:\t{comm}\nPPid:\t{ppid}\nVmRSS:\t{rss_mb * 1024} kB\n")


def test_flatpak_vsi_vidni_so_nasi(tmp_path):
    _proces(tmp_path, 10, "WebKitWebProces", 3000, 2)
    _proces(tmp_path, 11, "WebKitWebProces", 300, 2)
    _proces(tmp_path, 12, "python3", 9000, 1)
    ubiti = []
    assert v.preglej(2000, 99, True, lambda p, s: ubiti.append(p), str(tmp_path)) == 10
    assert ubiti == [10]


def test_deb_samo_potomci(tmp_path):
    _proces(tmp_path, 50, "python3", 100, 1)          # mi
    _proces(tmp_path, 51, "bwrap", 1, 50)
    _proces(tmp_path, 52, "WebKitWebProces", 2500, 51)  # nas (prek bwrap)
    _proces(tmp_path, 60, "WebKitWebProces", 5000, 1)   # tuj (drug program)
    assert sorted(v.nasi_procesi(50, False, str(tmp_path))) == [(52, 2500)]
    ubiti = []
    assert v.preglej(2000, 50, False, lambda p, s: ubiti.append(p), str(tmp_path)) == 52


def test_pod_mejo_nic(tmp_path):
    _proces(tmp_path, 10, "WebKitWebProces", 500, 2)
    assert v.preglej(2000, 99, True, lambda p, s: None, str(tmp_path)) is None


def test_pravi_proc_brez_napake():
    assert isinstance(v.nasi_procesi(os.getpid(), False), list)


def _rss(koren, pid, rss_mb):
    (koren / str(pid) / "status").write_text(f"Name:\tWebKitWebProces\nPPid:\t2\nVmRSS:\t{rss_mb * 1024} kB\n")


def test_zgodovina_kratek_vrh_ni_ustavljen(tmp_path):
    """Zahtevna stran (JetStream): kratek vrh nad mejo, nato padec - varuh z zgodovino je ne ustavi."""
    z, ubiti = {}, []
    _proces(tmp_path, 10, "WebKitWebProces", 3000, 2)
    for rss in (3000, 3200, 1100, 3300, 3400):
        _rss(tmp_path, 10, rss)
        assert v.preglej(2000, 99, True, lambda p, s: ubiti.append(p), str(tmp_path), zgodovina=z) is None
    assert ubiti == []


def test_zgodovina_puscanje_ustavljeno(tmp_path):
    """Puscanje: nad mejo VZORCEV_RASTI zaporednih pregledov in ves cas raste - ustavljen."""
    z, ubiti = {}, []
    _proces(tmp_path, 10, "WebKitWebProces", 2100, 2)
    izidi = []
    for i in range(v.VZORCEV_RASTI):
        _rss(tmp_path, 10, 2100 + 450 * i)
        izidi.append(v.preglej(2000, 99, True, lambda p, s: ubiti.append(p), str(tmp_path), zgodovina=z))
    assert izidi[:-1] == [None] * (v.VZORCEV_RASTI - 1) and izidi[-1] == 10
    assert ubiti == [10] and 10 not in z


def test_zgodovina_mrtvi_procesi_pocisceni(tmp_path):
    z = {77: [3000, 3100]}
    _proces(tmp_path, 10, "WebKitWebProces", 500, 2)
    v.preglej(2000, 99, True, lambda p, s: None, str(tmp_path), zgodovina=z)
    assert z == {}
