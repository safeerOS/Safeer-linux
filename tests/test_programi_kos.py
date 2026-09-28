"""Odgovor apps.list z ikonami ne sme preseci omejitve sporocila v Safeer Linku (256 kB)."""
import json
from unittest import mock

from core import link_programi


def test_kos_z_ikonami_ostane_pod_mejo():
    p = link_programi.Programi(True)
    vnosi = {f"app{i}.desktop": {"ime": f"Program {i:03d}", "opis": "", "ikona": "x"} for i in range(80)}
    with mock.patch.object(p, "_preberi", return_value=vnosi), \
            mock.patch.object(p, "_ikona", return_value="A" * 20000):
        prvi = p.seznam(True, 0, 50)
        assert len(json.dumps(prvi)) < 256 * 1024
        assert 0 < len(prvi["items"]) < 50
        drugi = p.seznam(True, len(prvi["items"]), 50)
        assert drugi["items"][0]["name"] == f"Program {len(prvi['items']):03d}"
