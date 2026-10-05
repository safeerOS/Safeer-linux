# Safeer Browser for Linux 1.0.99 · Safeer Control 2.1.55 · Safeer OS 0.4.57

## Safeer Link (Safeer Control 2.1.55, Safeer OS 0.4.57)

- **The screen of one computer can be shown on another computer.** The hub of a computer now relays a shared screen – the same protocol as the hub on Android (start and stop, the sender's stream of frames, a viewer page, an MJPEG stream). Until now "Screen" on the "Share with" panel answered "This device cannot show this computer's screen yet" when the other device was a computer.
- **The screen of a phone or tablet opens on the computer.** A phone starts sharing at its own hub, and the message reaches the computer through the neighbouring hubs. The computer looked for the viewer page only at its own hub and opened an error page (`{"error": "Ni te poti."}`). It now asks its own hub first and then the sender's – the same order as for a received file. Safeer Control shows the viewer in its own window wherever the page is; until now only a page from its own hub got that window and anything else went to the system browser.
- **Sharing ends when nobody is watching.** When the viewer on the other device is closed, the computer's hub ends the sharing after 10 seconds and tells the sender why. The panel says "The device is no longer showing the screen, so sharing has ended" instead of "Screen sharing failed", and the computer stops sending its screen.
- **One click in the viewer window is one tap on the device.** The viewer page that comes from a hub on Android has had its own mouse listeners since 27 September; the viewer window of Safeer Control sent the same click once more over Safeer Link. Measured in WebKit with the same listeners: one click was sent twice, and a click on the black border next to the picture was moved to the edge of the device's screen. The window now handles the mouse itself: one click, one tap; a click outside the picture does nothing.
- **A sharing that is cancelled right away leaves no window behind.** If the end arrives while the viewer page is still being looked up, the viewer is not opened.
- **A device with an older Safeer says what to do.** "This device cannot show the screen yet. Update Safeer on it." replaces "This device cannot show this computer's screen yet" – updating now helps.

Rules of the hub (as on Android unless noted): one shared screen per sender; one sender per device at a time, and the second one is told who is sharing; only the device that started a sharing may send frames; a viewer that cannot keep up loses older frames and nothing is stored; a screen is relayed only to a device signed in to this hub. The viewer page of a computer's hub is for viewing only – a computer is not controlled through it. New compared with Android: sharing also ends when the sender is silent for 20 seconds, when it does not open its stream within 20 seconds, and when nobody has watched for 10 seconds.

Verified live in a home network (Safeer Control with this code, a Windows computer with Safeer OS for Windows 1.0.40, a phone with the published app): Windows → Linux from the "Share with" panel – the real screen in the viewer window, and after the window was closed the panel on Windows showed the new message in less than half a minute; Linux → Windows with a drawn test pattern sent by the same sender code (112 frames in 28 seconds); phone → Linux and phone → Windows – the viewer page was at the phone's hub, and "Stop sharing" on the phone closed the viewer.

Verified: 1754 automated tests. One new test file runs the whole path over TLS – the real sender, a hub on a free port with a temporary certificate, an MJPEG viewer – without touching the computer's own identity; another runs the viewer window's script in real WebKit.

Not tested live: starting screen sharing with the button in the Safeer Control window (the capture of the real desktop; the sending code is the same as with the test pattern), and whether a device really performed two taps for one click (input is not enabled on the test phone – what was measured is that the click was sent twice).

Known limits: a phone whose Safeer app is in the background shows a notification instead of opening the shared screen (Android does not let an app open a window from the background), and that notification stays after the sharing has ended.

## Safeer Browser 1.0.99

- The built-in Safeer Link screen is the same page (the two new messages). Otherwise packaged with Safeer OS 0.4.57 and Safeer Control 2.1.55.

Details: `docs/LINK-MESH.md`, rule 9.

Slovensko: **Zaslon enega računalnika se pokaže na drugem.** Središče računalnika zdaj posreduje deljen zaslon (isti protokol kot središče na Androidu); doslej je »Zaslon« proti drugemu računalniku odgovoril »Ta naprava še ne more prikazati zaslona tega računalnika«. **Zaslon telefona ali tablice se na računalniku odpre** – telefon deljenje začne pri svojem središču, računalnik pa je stran gledalca iskal samo pri svojem in odprl stran z napako; zdaj vpraša najprej svoje, nato pošiljateljevo središče, Safeer Control pa gledalca vedno odpre v svojem oknu. **Deljenje se konča, ko ga nihče več ne gleda** (po 10 sekundah), plošča pove »Naprava zaslona ne prikazuje več, zato se je deljenje končalo«. **En klik v oknu gledalca je en dotik na napravi** – izmerjeno: klik sta poslali dve poti. Preverjeno v živo: Windows → Linux, Linux → Windows (narisan vzorec), telefon → Linux in telefon → Windows. Ni preverjeno v živo: gumb »Zaslon« v oknu Safeer Controla (zajem pravega namizja).
