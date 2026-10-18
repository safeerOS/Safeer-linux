"""Ucni tek za BOLT (packaging/webkit-deb/bolt.sh): ISTI tek kot za PGO (packaging/webkit/pgo_trening.py, Speedometer
3.1), le da se procesi WebKita koncajo normalno.

pgo_trening.py na koncu poklice WebView.terminate_web_process(): v gradnji s profilom LLVM WebKit poslje SIGTERM in
proces zapise profil, v navadni gradnji pa SIGKILL - knjiznica, instrumentirana z llvm-bolt, profil zapise sele ob
normalnem izhodu (DT_FINI). Brez tega klica se okno zapre, glavni proces konca, spletni in omrezni proces pa ob
zaprti povezavi ustavita zanko in normalno koncata (AuxiliaryProcess::didClose v GTK) - vsak zapise svoj .fdata.
pgo_trening.py ostane nespremenjen (je v kljucu predpomnilnika profila Flatpaka, packaging/webkit/pgo.py).

Uporaba: python3 bolt_trening.py URL [NAJDLJE_MINUT]   (izhod kot pgo_trening.py: 0 = veljaven rezultat Speedometra)
"""
import os
import runpy
import sys

import gi

gi.require_version("WebKit", "6.0")
from gi.repository import WebKit  # noqa: E402

TRENING = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "webkit", "pgo_trening.py")
WebKit.WebView.terminate_web_process = lambda self: None
sys.argv = [TRENING] + sys.argv[1:]
runpy.run_path(TRENING, run_name="__main__")
