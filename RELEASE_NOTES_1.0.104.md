# Safeer Browser for Linux 1.0.104 · Safeer Control 2.1.60 · Safeer OS 0.4.62

## Safeer Link: the screen of the computer uses far less data for the same picture (Safeer Control 2.1.60)

The screen of this computer on a phone, tablet or TV – at home, or away from home through Global Link – now needs far less data. The picture is not made worse to get there: the quantiser (16), the resolution and 60 frames per second stay as they were. A device with an older Safeer gets exactly the same stream as before.

- **HEVC where both sides support it.** The viewing device lists the codecs it decodes in hardware. If it offers HEVC and the graphics card of this computer encodes HEVC in hardware (checked once with a short test encode), the picture is sent as HEVC with the same quantiser. On a losslessly recorded game scene (1236 × 576, 60 frames per second) H.264 needed 9.75 Mb/s (SSIM 0.9910, PSNR 46.20 dB) and HEVC 6.56 Mb/s (SSIM 0.9926, PSNR 46.44 dB): fewer bytes for a picture that measures slightly better.
- **A key frame every 10 seconds instead of every second** – for a viewing device that states it never drops parts of the stream. On a still screen the key frames were most of the traffic.
- **Silence is not sent.** Sound travels uncompressed (1.5 Mb/s). When the computer is completely silent, the sound stream pauses after 0.3 s and continues with the first sound.
- **A program that is already open on the desktop is shown there.** Programs started from a phone, tablet or TV open on a separate, virtual screen. A program that runs only once (it hands the request to its window that is already open on the desktop and exits) left that separate screen empty: the device showed an empty screen for 30 seconds and the session ended. Safeer Control now notices that the launched process has ended and that the program has a window on the desktop; the device switches to the desktop of the computer and that window is brought to the front. While a program is still opening, the device says so instead of showing an empty screen. An older device gets the same message as before, at once instead of after 30 seconds.

Measured on a laptop with Intel Xe graphics (driver iHD 24.1): the same content captured for 10 seconds with each setting, picture only, in Mb/s.

| content | before: H.264, key frame every second | H.264, key frame every 10 s | now: HEVC, key frame every 10 s |
| --- | --- | --- | --- |
| a still program window on the separate screen, 1236 × 576 | 0.53 | 0.40 | 0.14 |
| a game menu with falling snow, 1236 × 576 | 11.44 | 10.95 | 6.65 |
| the desktop, 2560 × 1440 scaled to 1920 × 1080, almost still | 2.40 | 0.98 | 0.66 |

Before this release silent sound added another 1.54 Mb/s to each row.

Measured live (this code in Safeer Control; a phone with Safeer OS 0.5.61 for Android, through Global Link, numbers from the phone's own counter): a still program window 0.14 Mb/s at 60 frames per second; the game menu with music 8.5 Mb/s at 60.0 frames per second (20-second average); the desktop 0.34–0.44 Mb/s at 60 frames per second. A 4-second tone played into an otherwise silent session: traffic 0.14 → 1.7 → 0.14 Mb/s, and the phone played 4.24 s of sound. A program that was already open on the desktop: 4.1 s from the tap to the desktop being ready on the phone.

Safety net: if a capture with HEVC ends by itself without a single picture, Safeer Control goes back to H.264 until it is restarted; the device asks for the session again by itself.

Verified: 961 automated tests of Safeer Link passed locally; the whole suite runs in CI. New tests in `tests/test_link_zagon.py` and `tests/test_zaslon_kodek.py`; extended `tests/test_link_sway.py` and `tests/test_zaslon_pogled.py`.

Not tested live: a device with an older Safeer against this version (covered by tests – the capture command is identical to the previous one); the safety net for a failing HEVC capture; a TV and a tablet as the viewing device; a computer without hardware HEVC encoding (it keeps H.264).

## Safeer OS 0.4.62 · Safeer Browser 1.0.104

- Released together with Safeer Control 2.1.60. No changes in Safeer OS and in browsing.

Slovensko: **Zaslon računalnika porabi precej manj podatkov ob enaki sliki.** Slika tega računalnika na telefonu, tablici ali televizorju (doma ali zdoma prek Global Linka) zdaj potrebuje precej manj podatkov, ne da bi bila slabša: kvantizator (16), ločljivost in 60 slik na sekundo ostanejo. Kjer napravi to zmoreta, gre slika kot HEVC (izmerjeno na brezizgubnem posnetku igre: 9,75 → 6,56 Mb/s, SSIM 0,9910 → 0,9926); ključna slika je na 10 sekund namesto vsako sekundo; tišine računalnik ne pošilja več (prej 1,5 Mb/s). Mirno okno programa: prej 0,53 Mb/s slike in 1,54 Mb/s tišine, zdaj 0,14 Mb/s; meni igre: slika 11,44 → 6,65 Mb/s; skoraj mirno namizje: 2,40 → 0,66 Mb/s. **Program, ki je na namizju že odprt, se pokaže tam:** prej je naprava 30 sekund kazala prazen zaslon in sejo končala, zdaj v nekaj sekundah (izmerjeno 4,1 s) pokaže namizje računalnika z oknom tega programa v ospredju. Naprava s starejšim Safeerjem dobi enak tok kot doslej.
