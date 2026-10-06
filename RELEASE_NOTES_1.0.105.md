# Safeer Browser for Linux 1.0.105 · Safeer Control 2.1.61 · Safeer OS 0.4.63

## Security: pairing a device into Safeer Link is no longer permission to the content of this computer (Safeer Control 2.1.61)

Until this release every device paired into Safeer Link was equal. A phone of another person, added to the Link so that it helps with the connection, could at once browse the folders this computer shares (the whole disk, where that was shared), list and start its programs, see what is playing and continue it, and it received bookmark sync and playback state. Found on 6 October 2026 with such a phone.

Now there are two circles:

- **Safeer Link is the wider circle.** Every paired device helps with the connection (hub, relaying, a path over a mobile network) and receives what someone explicitly sends to it: text, a file, a chat message, an offer to play something (which starts only after the user accepts it).
- **Access to content is the narrower circle.** On each device separately, and for each other device separately, you decide what you open to it: **Files · Programs · Player · Screen and control**. Without that the computer refuses the request itself – it does not merely hide a button on the other device.
- **Where:** the Safeer Link window → a device → *What this device may do on this computer* (four switches, saved at once). The device list shows *full access*, *partial access* or *helps only* for every device.
- **Your devices keep working without a single click.** Devices that were in your Safeer Link with this computer before 6 October 2026 keep full access. Every device added later starts with no access.
- **Taking access away works at once** – without restarting anything, and also for a file-server token that was already issued (the device's access is checked on every request).

What is closed:

- Commands from other devices: files, programs, what is playing and continuing it, playlists and sources of the Media Centre, opening a page or a stream, help with playback (torrent and conversion streams), the screen, keys, the pointer, volume. A command the computer does not know needs all four.
- A page that opens here by itself needs *Player*; the screen of another device that opens here by itself needs *Screen and control*; bookmark sync is accepted only from a device that has all four.
- The hub on this computer no longer hands private broadcasts to everyone: playback state and sync go only to the devices their source lists. From a device with an older Safeer, which cannot say whom it trusts, they go on only inside the narrower circle of this computer.
- The catalogue of this computer's programs is no longer part of the device list that every member of the Link receives. A device gets the list of programs only if you opened *Programs* to it.
- What you explicitly send stays reachable: a file you send to a device yourself, or playback continued by a device that has *Player*, can be read by that device – that one file, read only.

Verified live (6 October 2026; Safeer Control 2.1.61 on a laptop, a phone with Safeer OS 0.5.62 for Android):

- On its first start the computer wrote down access for the 12 devices that were in the Link before; the phone added that day got none.
- With access taken away from a test phone, the computer refused its request for files by itself (log: `Zavrnjeno: … nima dostopa za files.list`) and the phone showed that the computer shares no folders. With access given back, the folders were there again at once.
- With *Programs* taken away from the computer on the phone, the phone refused the computer's request (`safeerctl apps` printed "The device does not share its apps."), while `safeerctl info` (*Player* still open) kept working.
- The phone of another person, added that day and updated to Safeer OS 0.5.62, refused this computer's requests for its programs and for its device details by itself (its log shows both refusals); it stayed in the Link and its Link services kept running.

Tests: 1012 automated tests of Safeer Link and of the packaging pass locally, the whole suite runs in CI. New: `tests/test_link_dostop.py` (rules, first start, the file server, the hub, refusal on the computer).

Not closed by this release:

- The hub sees the messages it routes. A device that hosts the hub and runs modified software could read routed commands or forge their sender. Closing this needs device-to-device protection of commands (planned).
- A device id is not yet bound to the device key on every path. A paired device running modified software could present an id that looks like another device's and get that device's access; on a device that has not started the new version yet it could enrol with a date before 6 October 2026 and inherit access. Device-to-device protection closes this too.
- Any member of the Link can still remove or rename a device, and sees the pairing code of a new device.
- The narrower circle is kept on each device separately – you set it on each of your devices. Agreeing it automatically among your own devices is the next step.
- A device with an older Safeer answers everyone until it is updated.
- The switches are in the Safeer Link window of Safeer Control and of the browser; Safeer OS for Linux does not show them yet.
- Safeer Control for Windows does not have this change yet.

Not tested live: a request sent by the device of another person to this computer (it was asleep during the test; the same refusal was exercised with a test phone whose access had been taken away); a page sent by a device without access and sync from such a device (covered by tests); a TV and a tablet with the new version.

## Safeer OS 0.4.63 · Safeer Browser 1.0.105

- Released together with Safeer Control 2.1.61. Safeer Link inside the browser uses the same rules. No other changes.

Slovensko: **Varnost: seznanitev v Safeer Link ni več dovoljenje za vsebine računalnika.** Do te izdaje je bila vsaka seznanjena naprava enakovredna: telefon druge osebe, dodan v Link zato, da pomaga pri povezavi, je takoj lahko brskal po deljenih mapah računalnika, videl in zagnal njegove programe, videl, kaj se predvaja, in to nadaljeval. Zdaj je Safeer Link širši krog (vsaka naprava pomaga pri povezavi in sprejme, kar ji kdo izrecno pošlje), dostop do vsebin pa ožji krog: na vsaki napravi posebej in za vsako drugo napravo posebej odločiš, kaj ji odpreš – Datoteke, Programi, Predvajalnik, Zaslon in upravljanje (okno Safeer Link → naprava). Brez tega računalnik zahtevo zavrne sam. Naprave, ki so bile v tvojem Linku pred 6. 10. 2026, obdržijo poln dostop; vsaka pozneje dodana začne brez dostopa. Odvzem velja takoj. Še ni zaprto: središče vidi sporočila, ki jih usmerja; oznaka naprave še ni na vseh poteh vezana na njen ključ (seznanjena naprava s predelano programsko opremo bi se lahko predstavila kot druga naprava); vsak član lahko odstrani ali preimenuje napravo; ožji krog nastaviš na vsaki napravi posebej; Safeer Control za Windows spremembe še nima.
