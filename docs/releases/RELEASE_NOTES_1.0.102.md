# Safeer Browser for Linux 1.0.102 · Safeer Control 2.1.58 · Safeer OS 0.4.60

## Safeer Link: the picture adapts to the screen of the device that shows it (Safeer Control 2.1.58)

When you open a program of this computer from a phone, tablet or TV, it runs on a separate, virtual screen and only that screen is sent to the device. Until now this screen was always 1920 × 1080: on a phone with a longer screen black bars stayed at the sides, on a 16:10 tablet at the top and bottom, and on a dense phone screen the buttons of desktop programs were tiny.

- **The separate screen takes the shape and size of the device's screen.** The device tells the computer the area where the picture will be shown (`view` in `screen.start`; Safeer OS 0.5.59 for Android). The separate screen is made exactly that large, so the picture fills the device's screen without black bars and without resampling. Limits: 640 × 360 to 3840 × 2160; an older device gets the size it got before.
- **Larger buttons on a dense screen.** The output of the separate screen gets a scale computed from the density of the device's screen (density / 1.5, in quarter steps, 1 to 3), but only as far as programs keep at least 540 logical points on the shorter side – so that windows stay whole. A TV stays at 1. The picture that is sent keeps its size and sharpness.
- **Larger or smaller content during a session.** The device can ask for another scale (event `merilo`); the computer changes the scale of the separate screen, the session keeps running, and the device learns the largest scale that still leaves programs whole (`scale_max`).
- **The real screen of the computer is never changed.** When a device watches the real desktop, nothing on the computer is adjusted to the device – not the resolution, not the scale, not the windows. Adapting the picture there is done by the device itself.

Measured live (this code in Safeer Control on a computer with Linux Mint; a phone with a 576 × 1280 screen and Safeer OS 0.5.59):

- a program of the computer (Calculator) opened from the phone: separate screen 1236 × 576 (the phone's screen without the camera cutout), the phone's decoder runs at 1236 × 576 and 60 frames per second, the picture covers 96.6 % of the phone's screen – the rest is the strip beside the camera cutout;
- the same through Global Link (traffic via link.safeer.si): same size and coverage; a tap on the "7" button of the calculator hit the button;
- scale 1.25 asked from the phone: the separate screen switched to 988 × 460 logical points while capture kept running; on this small screen the two bottom rows of the calculator fell out of the picture – hence the limit of 540 points, after which this phone no longer offers larger content.

Verified: 911 automated tests of Safeer Link passed locally; the whole suite runs in CI. New tests in `tests/test_zaslon_pogled.py`: size and scale for a device, a session with a fake separate screen, the `screen.start` command, scale during a session and its limits, the real screen left alone.

Not tested live: a phone with a dense screen (scale 2), a tablet, a TV; a game with a fixed canvas after a scale change.

Known limits: programs that run through XWayland are not drawn at the scale themselves - the compositor enlarges them, so at a scale above 1 they can look less sharp than native Wayland programs (expected from how the compositor works, not measured here); Safeer for Windows does not have this yet (a device gets the size it got before).

## Safeer OS 0.4.60 · Safeer Browser 1.0.102

- Released together with Safeer Control 2.1.58. No changes in Safeer OS and in browsing.

Slovensko: **Slika se prilagodi zaslonu naprave, ki jo kaže.** Program tega računalnika, odprt s telefona, tablice ali televizorja, teče na ločenem, navideznem zaslonu. Ta je bil doslej vedno 1920 × 1080; zdaj dobi obliko in velikost zaslona naprave (naprava jo pove ob začetku seje), zato slika zapolni njen zaslon brez črnih robov in brez prevzorčenja. Na gostem zaslonu telefona so gumbi programov narisani večje (merilo iz gostote naprave, le toliko, da programom ostane vsaj 540 navideznih točk); napravi je mogoče med sejo izbrati večjo ali manjšo vsebino. Pravi zaslon računalnika se nikoli ne spremeni – ne ločljivost, ne merilo, ne okna. Izmerjeno v živo s telefonom z zaslonom 576 × 1280: ločeni zaslon 1236 × 576, slika pokrije 96,6 % zaslona telefona (ostanek je pas ob izrezu kamere), enako prek Global Linka; dotik na gumb kalkulatorja je zadel gumb. Ni preizkušeno v živo: telefon z gostim zaslonom (merilo 2), tablica, televizor.
