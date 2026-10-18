"""Zajem zaslona Wayland za Safeer Link: PipeWire (portal ScreenCast) -> surove slike BGRx -> ffmpeg -> stdout.

Zazene ga core/link_zaslon prek core/portal_zaslon.ukaz_zajema (en proces za sejo, kot x11grab na X11):

    python3 -m core.zajem_pipewire --fd 3 --vozlisce 42 --sirina 1920 --visina 1080 --fps 30 -- ffmpeg ...

GStreamer (pipewiresrc) slike pomanjsa na koncno velikost in jih z enakomernim ritmom (videorate) pise ffmpegu na
standardni vhod; ffmpeg jih kodira z istimi kodirniki kot na X11 (VAAPI ali x264) in pise na nas stdout. keepalive-time:
sestavljalnik poslje sliko samo ob spremembi, televizor pa pricakuje enakomeren tok (kot wf-recorder -D na drugem
zaslonu). Ob SIGTERM ali koncu ffmpega se ustavi oboje - noben proces ne ostane.
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys


def opis_cevi(fd: int, vozlisce: int, sirina: int, visina: int, fps: int, izhod_fd: int) -> str:
    """Opis cevi GStreamer (Gst.parse_launch); stevila so cela, nic ne pride iz omrezja."""
    ritem = max(1, int(1000 / max(1, fps)))
    return ("pipewiresrc fd=%d path=%d do-timestamp=true keepalive-time=%d always-copy=true ! "
            "videoconvert ! videoscale ! videorate ! "
            "video/x-raw,format=BGRx,width=%d,height=%d,framerate=%d/1,pixel-aspect-ratio=1/1 ! "
            "fdsink fd=%d sync=false"
            % (int(fd), int(vozlisce), ritem, int(sirina), int(visina), int(fps), int(izhod_fd)))


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="zajem_pipewire")
    for ime in ("--fd", "--vozlisce", "--sirina", "--visina", "--fps"):
        p.add_argument(ime, type=int, required=True)
    p.add_argument("ffmpeg", nargs=argparse.REMAINDER)
    a = p.parse_args(argv)
    ffmpeg = list(a.ffmpeg[1:] if a.ffmpeg[:1] == ["--"] else a.ffmpeg)
    if not ffmpeg:
        print("zajem_pipewire: manjka ukaz ffmpeg", file=sys.stderr)
        return 2
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import GLib, Gst
    Gst.init(None)
    kodirnik = subprocess.Popen(ffmpeg, stdin=subprocess.PIPE, stdout=None, stderr=None)
    cev = Gst.parse_launch(opis_cevi(a.fd, a.vozlisce, a.sirina, a.visina, a.fps, kodirnik.stdin.fileno()))
    zanka = GLib.MainLoop()
    koda = [0]

    def konec(k: int = 0) -> bool:
        koda[0] = koda[0] or k
        zanka.quit()
        return False

    def sporocilo(_vodilo, s) -> None:
        if s.type == Gst.MessageType.ERROR:
            napaka, _ = s.parse_error()
            print("zajem_pipewire:", napaka.message, file=sys.stderr, flush=True)
            konec(1)
        elif s.type == Gst.MessageType.EOS:
            konec(0)

    vodilo = cev.get_bus()
    vodilo.add_signal_watch()
    vodilo.connect("message", sporocilo)
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        GLib.unix_signal_add(GLib.PRIORITY_HIGH, sig, konec)
    # ffmpeg je koncal (televizor je odsel, napaka kodirnika): ni vec komu pisati.
    GLib.child_watch_add(GLib.PRIORITY_DEFAULT, kodirnik.pid, lambda *_a: konec(0))
    cev.set_state(Gst.State.PLAYING)
    try:
        zanka.run()
    finally:
        cev.set_state(Gst.State.NULL)
        try:
            kodirnik.stdin.close()
        except OSError:
            pass
        try:
            kodirnik.wait(timeout=3)
        except subprocess.TimeoutExpired:
            kodirnik.kill()
            kodirnik.wait(timeout=3)
        try:
            os.close(a.fd)
        except OSError:
            pass
    return koda[0]


if __name__ == "__main__":
    sys.exit(main())
