"""Video v Safeerju se dekodira programsko, ne s strojnimi dekoderji VA-API.

Izmerjeno 18. 10. 2026 na prenosniku lastnika (Intel Iris Xe, gonilnik iHD 24.1, GStreamer 1.24, nas WebKitGTK 2.54):
strojni dekoderji VA (vavp9dec, vaav1dec, vah264dec) so pri YouTubu nepredvidljivo odpovedali (»Media failed to
decode«, v dnevniku »driver bug«) - isti posnetek enkrat igra, drugic ne. Do 1.0.127 je to Safeer razumel kot
»vgradnja ni dovoljena« in je zavrnil 197 posnetkov. Programsko (vp9dec, avdec_h264, dav1ddec) so vsi igrali, 720p brez
izpuscenih slicic, priblizno cetrtina enega jedra (i5-1135G7).

Nastavitev velja za ves proces in procese, ki jih zazene (spletni procesi WebKita podedujejo okolje), zato jo poklicemo
na zacetku programa, pred prvim pogledom WebKit in pred Gst.init. Kdor zeli strojno dekodiranje (npr. z drugim
gonilnikom), zazene Safeer s SAFEER_STROJNO_DEKODIRANJE=1.
"""

from __future__ import annotations

import os
from typing import MutableMapping, Optional

#: Strojni video dekoderji GStreamerja (vticnik va in starejsi vaapi) za kodeke spleta.
STROJNI = ("vah264dec", "vah265dec", "vavp8dec", "vavp9dec", "vaav1dec",
           "vaapih264dec", "vaapih265dec", "vaapivp8dec", "vaapivp9dec", "vaapiav1dec")


def programsko(okolje: Optional[MutableMapping[str, str]] = None) -> bool:
    """V GST_PLUGIN_FEATURE_RANK doda rang NONE za strojne dekoderje (obstojece vrednosti ostanejo). Vrne True, ce je
    nastavitev v veljavi."""
    env = os.environ if okolje is None else okolje
    if env.get("SAFEER_STROJNO_DEKODIRANJE") == "1":
        return False
    obstojece = [d.strip() for d in str(env.get("GST_PLUGIN_FEATURE_RANK") or "").split(",") if d.strip()]
    imena = {d.split(":", 1)[0] for d in obstojece}
    dodaj = ["%s:NONE" % ime for ime in STROJNI if ime not in imena]
    nova = ",".join(obstojece + dodaj)
    if env.get("GST_PLUGIN_FEATURE_RANK") != nova:     # ponovni klic (Control v procesu Safeer OS): brez setenv med nitmi
        env["GST_PLUGIN_FEATURE_RANK"] = nova
    return True
