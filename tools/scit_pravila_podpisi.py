#!/usr/bin/env python3
"""Podpise seznam pravil Scita (core/scit_pravila.py) za objavo na https://intel.safeer.si/v1/scit/.

Lastnik ga pozene na svojem racunalniku s produkcijskim kljucem (»safeer-prod-2026-09«, ki ga ni v nobenem repozitoriju):

    python3 tools/scit_pravila_podpisi.py --kljuc <zasebni kljuc PEM> --izhod <mapa> [--pravila pravila.json] [--dni 14]

Brez --pravila podpise vgrajeni seznam programa. V mapo zapise latest.json (podpisan manifest) in scit-<verzija>.json
(podpisan paket) - oba gresta na streznik v /v1/scit/. Odjemalci seznam preverijo z istim javnim kljucem kot vir groznj
(core/threat_intel.TRUSTED_KEYS); kar bi odjemalec zavrnil (core/scit_pravila.preveri_pravila), se tu sploh ne podpise.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import scit_pravila, signed_feed  # noqa: E402


def podpisi(pravila: dict, zasebni_kljuc, key_id: str, verzija: int, zdaj: datetime, dni: int = 14):
    """(manifest, paket) v bajtih. zasebni_kljuc: cryptography Ed25519PrivateKey."""
    paket, manifest = scit_pravila.zgradi_paket(pravila, verzija, zdaj, zdaj + timedelta(days=dni))
    podpis_paketa = zasebni_kljuc.sign(signed_feed.BUNDLE_CONTEXT + paket)
    manifest["bundle"]["signature"] = {"alg": "ed25519", "key_id": key_id,
                                       "sig": base64.b64encode(podpis_paketa).decode("ascii")}
    podpisano = signed_feed.canonical_json(manifest)
    podpis = zasebni_kljuc.sign(signed_feed.MANIFEST_CONTEXT + podpisano)
    ovojnica = {"signed": base64.b64encode(podpisano).decode("ascii"),
                "signatures": [{"alg": "ed25519", "key_id": key_id, "sig": base64.b64encode(podpis).decode("ascii")}]}
    return signed_feed.canonical_json(ovojnica), paket


def main() -> int:
    from cryptography.hazmat.primitives import serialization
    a = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    a.add_argument("--kljuc", required=True, help="zasebni kljuc Ed25519 (PEM, PKCS8)")
    a.add_argument("--key-id", default="safeer-prod-2026-09")
    a.add_argument("--izhod", required=True)
    a.add_argument("--pravila", help="JSON s pravili (privzeto vgrajeni seznam)")
    a.add_argument("--dni", type=int, default=14)
    arg = a.parse_args()
    with open(arg.kljuc, "rb") as f:
        kljuc = serialization.load_pem_private_key(f.read(), password=None)
    pravila = scit_pravila.VGRAJENA
    if arg.pravila:
        with open(arg.pravila, encoding="utf-8") as f:
            pravila = json.load(f)
    zdaj = datetime.now(timezone.utc).replace(microsecond=0)
    verzija = int(zdaj.strftime("%Y%m%d%H%M"))
    manifest, paket = podpisi(pravila, kljuc, arg.key_id, verzija, zdaj, arg.dni)
    os.makedirs(arg.izhod, exist_ok=True)
    with open(os.path.join(arg.izhod, "scit-%d.json" % verzija), "wb") as f:
        f.write(paket)
    with open(os.path.join(arg.izhod, "latest.json"), "wb") as f:
        f.write(manifest)
    print("verzija %d, %d pravil -> %s" % (verzija, scit_pravila.preveri_pravila(pravila, verzija, "orodje").stevilo(),
                                           arg.izhod))
    return 0


if __name__ == "__main__":
    sys.exit(main())
