# Safeer Browser for Linux 1.0.100 · Safeer Control 2.1.56 · Safeer OS 0.4.58

## Safeer Link: away from home like at home (Safeer Control 2.1.56, Safeer OS 0.4.58)

Global Link brings a device only as far as the door of this computer's hub. Until now the hub served shared files for reading; everything else worked only on the home network. Now the hub serves what the computer serves directly – with the same token and the same rules.

- **The screen of this computer away from home – same quality, with sound.** The viewer (phone, tablet, TV with Safeer OS 0.5.57) asks for the screen with `relay: true`; the computer confirms the path and the viewer reaches the hub with `GET /cast/desktop` (`Upgrade: safeer-desktop`, the one-time session token in a header). After `101` the hub hands the connection to the screen session and the very same stream runs over it: picture (up to 1920 × 1080 at 60 frames per second), sound, and input back. Quality is not lowered because of the path. The relay sees only encrypted bytes – TLS runs from the viewer to this computer, pinned to its certificate. A session gets exactly one viewer; a second one and one with a wrong token get 404.
- **Renaming, moving, deleting and rotating pictures away from home.** `POST /cast/d/<id>` on the hub does what `POST /d/<id>` does at home. The answer to `files.list` says so (`server.hub = 2`); a device then offers editing away from home too.
- **Thumbnails for videos and pictures, and dates.** `/thumb/<id>` (and `/cast/thumb/<id>` on the hub) returns a small JPEG: pictures are scaled with Pillow and turned the way they were taken (EXIF), videos give a frame from the third second (ffmpeg). A thumbnail is made once per file and kept in memory. The listing now says when a file was changed (`modified`), so the grid on a device groups files by day. Until now a phone downloaded the whole photo to draw a tile and videos had only an icon.
- **Streams over the hub.** A torrent stream (`/cast/m/…`) and a stream converted on the fly (`/cast/live/…`) are served by the hub as well.

Verified live (this code in Safeer Control on a computer with Linux Mint, a phone with Safeer OS 0.5.57):

- with the phone's setting "Test: also at home over the internet" (traffic through link.safeer.si): the screen connected 0.6 s after the computer answered; 1920 × 1080, 58–65 frames per second, 4.4–5.3 Mbit/s with a still desktop, sound stream present; ending the session on the phone stopped the capture on the computer;
- at home without that setting: direct connection in 23 ms, the same picture figures, the relay was not touched;
- over Global Link a file was renamed on the computer's disk from the phone; the grid showed thumbnails of three videos and a photo, grouped by day.

Verified: New tests run the whole path over TLS with a real hub on a free port and a temporary certificate: the screen session through the hub (same quality and sound as at home, input arrives, wrong token, no session, second viewer, the direct door still works) and eleven cases that compare the file server at home with the hub away from home (same content, same thumbnail, same answers to editing, same refusals).

Not tested live: a real foreign network (mobile data); touch and keyboard into the screen picture over this path from a phone (the automated test covers the way back with a real hub and a real encrypted connection); moving, deleting and rotating over the hub (automated tests cover renaming and moving); a torrent stream and a converted stream over the hub.

Known limits: a computer as the *viewer* of another computer's screen still needs the same network; Safeer for Windows does not have this path yet. With full motion the screen stream goes up to 24 Mbit/s, and that much data then passes through the relay and the mobile network.

## Safeer Browser 1.0.100

- Packaged with Safeer OS 0.4.58 and Safeer Control 2.1.56. No changes to browsing.

Details: `docs/LINK-MESH.md`, rule 10.

Slovensko: **Zdoma kot doma.** Global Link pripelje napravo samo do vrat središča tega računalnika; doslej je središče tam streglo samo branje deljenih datotek. Zdaj streže vse, kar računalnik streže neposredno: **sliko zaslona v isti kakovosti in z zvokom** (telefon, tablica ali televizor s Safeer OS 0.5.57), **preimenovanje, premik, brisanje in vrtenje slik**, **sličice videov in slik** ter tokove. Seznam datotek pove tudi čas spremembe, zato mreža na napravi razvrsti datoteke po dnevih. Preverjeno v živo s telefonom prek link.safeer.si: slika zaslona v 0,6 s, 1920 × 1080 pri 58–65 slikah na sekundo z zvočnim tokom; doma neposredno v 23 ms. V pravem tujem omrežju ni preizkušeno; Safeer za Windows te poti še nima.
