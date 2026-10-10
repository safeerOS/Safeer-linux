#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kaj strojni kodirnik tega racunalnika res zmore (deljenje zaslona, core/link_zaslon.py).

Na vsaki dostopni napravi /dev/dri/renderD* naredi kratek preizkus (3 slike) za vsak nacin, ki ga seja uporablja
ali bi ga lahko: h264_vaapi CQP (danes), z -async_depth 1, z -aud 1, bitna hitrost VBR in CBR (4 Mb/s) ter
hevc_vaapi CQP. Izpise JSON - tako na vprasanje, ali gonilnik (HuC) zmore bitno hitrost, odgovorijo podatki.

Aplikacija tega orodja ne uvaza; zazene ga clovek:

  python3 tools/preveri-kodirnik.py [ffmpeg]

Namigi v izpisu (vainfo, dmesg, huc_info) povedo, kaj se pogledati rocno.
"""
from __future__ import annotations

import json
import os
import sys

KOREN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if KOREN not in sys.path:
    sys.path.insert(0, KOREN)

from core import link_zaslon  # noqa: E402


def main(argv) -> int:
    ffmpeg = argv[1] if len(argv) > 1 else None
    izid = link_zaslon.diagnoza_kodirnika(ffmpeg)
    print(json.dumps(izid, indent=2, ensure_ascii=False))
    return 0 if izid.get("naprave") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
