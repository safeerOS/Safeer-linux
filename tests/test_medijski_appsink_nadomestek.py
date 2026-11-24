"""Medijski center brez vticnika gtk4paintablesink: video mora ostati v istem oknu (appsink), ne v loceni.

Izvor: 24. 11. 2026 je lastnik v Medijskem centru videl film v loceni oknu z napacnim naslovom, ker paket
safeer-webkit (gtk4paintablesink) ni bil v izdaji, nadomestne poti pa ni bilo.
"""
import pathlib
import re

import pytest

KOREN = pathlib.Path(__file__).resolve().parent.parent
OPIS = ("videoconvert ! video/x-raw,format=BGRA ! appsink name=safeer-media-appsink "
        "emit-signals=true max-buffers=1 drop=true sync=true")


def test_program_uporablja_opis_nadomestnega_ponora():
    koda = (KOREN / "safeer_os.py").read_text(encoding="utf-8")
    zlepljeno = re.sub(r'"\s*\n\s*"', "", koda)
    assert OPIS in zlepljeno, "nadomestni ponor v safeer_os.py se ne ujema z opisom v preizkusu"
    assert "_medijski_appsink_pripravi" in koda and "video v istem oknu prek appsink" in koda


def test_nadomestni_ponor_prejme_slike_bgra():
    gi = pytest.importorskip("gi")
    try:
        gi.require_version("Gst", "1.0")
        from gi.repository import GLib, Gst
    except (ValueError, ImportError):
        pytest.skip("GStreamer ni na voljo")
    Gst.init(None)
    for ime in ("videotestsrc", "videoconvert", "appsink"):
        if Gst.ElementFactory.find(ime) is None:
            pytest.skip(f"manjka element {ime}")
    cev = Gst.parse_launch("videotestsrc num-buffers=5 ! video/x-raw,width=64,height=48 ! "
                           "videoconvert ! video/x-raw,format=BGRA ! appsink name=a emit-signals=true "
                           "max-buffers=1 drop=true sync=false")
    prejete = []

    def nova(sink):
        vzorec = sink.emit("pull-sample")
        s = vzorec.get_caps().get_structure(0)
        prejete.append((s.get_value("width"), s.get_value("height"), s.get_string("format")))
        return Gst.FlowReturn.OK

    cev.get_by_name("a").connect("new-sample", nova)
    cev.set_state(Gst.State.PLAYING)
    cev.get_bus().timed_pop_filtered(5 * Gst.SECOND, Gst.MessageType.EOS | Gst.MessageType.ERROR)
    cev.set_state(Gst.State.NULL)
    assert prejete and prejete[0] == (64, 48, "BGRA")
    del GLib
