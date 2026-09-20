# Safeer Browser for Linux 1.0.44 · Safeer Control 2.1.0 · Safeer OS 0.4.2

**Safeer Control 2.1.0: your devices can edit the files you share.** A TV or tablet with Safeer OS (0.4.3 / 0.3.3 or newer) can rename, move and delete the files and folders you share, and rotate pictures.

- **Delete = Trash.** Nothing is destroyed: the file goes to the computer's Trash (freedesktop; `gio trash`), where you restore it as usual.
- **Rotate a picture** is saved on the computer: a JPEG with an EXIF orientation tag is rotated without touching a single pixel (only the tag changes, instantly); other images (PNG, WebP, JPEG without EXIF) are rotated by Pillow, EXIF and colour profile kept. `python3-pil` is recommended by the package.
- **Rename and move** stay inside the shared folders; an existing file is never overwritten; names with paths or hidden names are refused.
- Only over the same pinned TLS connection and per-device token as the file downloads (`POST /d/<id>`); the shared folders themselves cannot be deleted or renamed.

Safeer OS for Linux 0.4.2 and the browser: the same Safeer Link core, no other changes.

Slovensko: **Safeer Control 2.1.0** – naprave (TV, tablica s Safeer OS 0.4.3/0.3.3+) lahko datoteke, ki jih deliš, **preimenujejo, premaknejo in izbrišejo** (brisanje je premik v Smeti računalnika – nič se ne uniči) ter **zavrtijo slike** (JPEG brez izgube – samo oznaka EXIF; druge slike zavrti Pillow). Vse samo znotraj deljenih map, prek iste pripete povezave in žetona kot prenosi. Safeer OS za Linux 0.4.2 in brskalnik: brez drugih sprememb.
