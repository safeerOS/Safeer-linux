# Safeer Browser for Linux 1.0.104 · Safeer Control 2.1.60 · Safeer OS 0.4.62

## Safeer Link: the screen of the computer uses far less data; quality follows the path (Safeer Control 2.1.60)

The screen of this computer on a phone, tablet or TV now depends on how the viewing device reaches the computer.

- **At home (the device reaches the computer directly):** the highest quality, as before – H.264, quantiser 16, 60 frames per second. The home network is normally the fastest path.
- **Away from home (through Global Link):** quality tuned to an ordinary 4G connection – quantiser 20 at the full 60 frames per second – and one step higher (quantiser 18) when the device reports a 5G connection. The picture is sent as HEVC when the device decodes it in hardware and the graphics card of this computer encodes it. This applies to every device that is a guest in another network, not only to phones.
- A device on a mobile network slower than 4G does not start a session away from home at all (Safeer OS 0.5.61 for Android says why): better no service than a bad one.

What else changed:

- **A key frame every 10 seconds instead of every second** – for a viewing device that states it never drops parts of the stream. On a still screen the key frames were most of the traffic.
- **Silence is not sent.** Sound travels uncompressed (1.5 Mb/s). When the computer is completely silent, the sound stream pauses after 0.3 s and continues with the first sound.
- **A program that is already open on the desktop is shown there.** Programs started from a phone, tablet or TV open on a separate, virtual screen. A program that runs only once (it hands the request to its window that is already open on the desktop and exits) left that separate screen empty: the device showed an empty screen for 30 seconds and the session ended. Safeer Control now notices that the launched process has ended and that the program has a window on the desktop; the device switches to the desktop of the computer and that window is brought to the front. While a program is still opening, the device says so instead of showing an empty screen. An older device gets the same message as before, at once instead of after 30 seconds.
- A device with an older Safeer still gets H.264 with a key frame every second; through Global Link it now gets the quality for an ordinary 4G connection as well.

Measured on a laptop with Intel Xe graphics (driver iHD 24.1), picture only, 60 frames per second, in Mb/s. The same content was captured for 8–10 seconds with each setting.

| content | before (H.264, quantiser 16, key frame every second) | now at home (H.264, 16, key frame every 10 s) | now away, 5G (HEVC, 18) | now away, 4G (HEVC, 20) |
| --- | --- | --- | --- | --- |
| a still program window, 1236 × 576 | 0.53 | 0.40 | – | 0.11 (live) |
| a game menu with falling snow, 1236 × 576 | 11.44 | 10.75–10.95 | 5.30 | 3.28 |
| the desktop, 2560 × 1440 scaled to 1920 × 1080, almost still | 2.40 | 0.98 | – | – |

Before this release silent sound added another 1.54 Mb/s to every row. A device without a hardware HEVC decoder gets H.264 away from home too: 5.46 Mb/s for the game menu at quantiser 20.

Picture quality of the same settings on a losslessly recorded game scene (SSIM, 1 = identical): H.264 quantiser 16 0.9910; HEVC 16 0.9926; HEVC 18 0.9907; HEVC 20 0.9872; H.264 20 0.9854.

Why HEVC only away from home – measured on a TV (hardware HEVC decoder, 1920 × 1080 at 60 frames per second, direct path, a still program window): with H.264 the decoder returned pictures evenly (no gap longer than 50 ms, decoder delay 18–19 ms); with HEVC it returned them in bursts (9.7 gaps longer than 50 ms per second) and stamped its own times on them. On the screen the HEVC pictures were evenly spaced, but later. At home bandwidth is not scarce, and the H.264 decoder is proven on every device; the same TV session now needs 0.27 Mb/s instead of 1.95 Mb/s.

Measured live (this code in Safeer Control; a phone with Safeer OS 0.5.61 for Android, numbers from the phone's own counter): through Global Link a still program window 0.11 Mb/s at 60 frames per second (HEVC, quantiser 20); directly at home 0.29 Mb/s at 60 frames per second (H.264, quantiser 16). A 4-second tone played into an otherwise silent session: traffic 0.14 → 1.7 → 0.14 Mb/s, and the phone played 4.24 s of sound. A program that was already open on the desktop: 4.1 s from the tap to the desktop being ready on the phone.

Safety net: if a capture with HEVC ends by itself without a single picture, Safeer Control goes back to H.264 until it is restarted; the device asks for the session again by itself.

Verified: 967 automated tests of Safeer Link passed locally; the whole suite runs in CI. New tests in `tests/test_link_zagon.py` and `tests/test_zaslon_kodek.py`; extended `tests/test_link_sway.py` and `tests/test_zaslon_pogled.py`.

Not tested live: a viewing device on a mobile network (4G, 5G) – the test phone has no SIM card, so the 5G step and the behaviour on real mobile links are covered by tests only; a device with an older Safeer against this version (covered by tests – at home the capture command is identical to the previous one); the safety net for a failing HEVC capture; a tablet as the viewing device; a computer without hardware encoding (the quality step sets its bitrate: 8 Mb/s for 4G, 16 Mb/s for 5G).

## Safeer OS 0.4.62 · Safeer Browser 1.0.104

- Released together with Safeer Control 2.1.60. No changes in Safeer OS and in browsing.

Slovensko: **Zaslon računalnika porabi precej manj podatkov, kakovost pa je odvisna od poti.** Doma (naprava doseže računalnik neposredno) ostane najvišja kakovost: H.264, kvantizator 16, 60 slik na sekundo. Zdoma (prek Global Linka) je kakovost umerjena na običajno povezavo 4G (kvantizator 20 pri polnih 60 slikah na sekundo), na 5G je stopnjo višja (18); slika gre kot HEVC, kjer ga naprava strojno dekodira in grafična kartica kodira. To velja za vse naprave, ki gostujejo v drugem omrežju. Naprava na mobilnem omrežju, slabšem od 4G, seje zdoma ne začne. Ključna slika je na 10 sekund namesto vsako sekundo, tišine računalnik ne pošilja več (prej 1,5 Mb/s). Izmerjeno (samo slika): meni igre prej 11,44 Mb/s, zdaj doma 10,75, zdoma na 5G 5,30 in na 4G 3,28 Mb/s; mirno okno programa prej 0,53 Mb/s in 1,54 Mb/s tišine, zdaj zdoma 0,11 Mb/s. Televizor doma: 0,27 Mb/s namesto 1,95 Mb/s, enako gladko (dekoder 18–19 ms, brez presledkov nad 50 ms). **Program, ki je na namizju že odprt, se pokaže tam:** prej je naprava 30 sekund kazala prazen zaslon in sejo končala, zdaj v nekaj sekundah (izmerjeno 4,1 s) pokaže namizje računalnika z oknom tega programa v ospredju.
