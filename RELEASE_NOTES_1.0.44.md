# Safeer Browser for Linux 1.0.44 · Safeer Control 2.1.0 · Safeer OS 0.4.2

**Safeer Control 2.1.0: your devices can edit the files you share.** A TV or tablet with Safeer OS (0.4.3 / 0.3.3 or newer) can rename, move and delete the files and folders you share, and rotate pictures.

- **Delete = Trash.** Nothing is destroyed: the file goes to the computer's Trash (freedesktop; `gio trash`), where you restore it as usual.
- **Rotate a picture** is saved on the computer: a JPEG with an EXIF orientation tag is rotated without touching a single pixel (only the tag changes, instantly); other images (PNG, WebP, JPEG without EXIF) are rotated by Pillow, EXIF and colour profile kept. `python3-pil` is recommended by the package.
- **Rename and move** stay inside the shared folders; an existing file is never overwritten; names with paths or hidden names are refused.
- Only over the same pinned TLS connection and per-device token as the file downloads (`POST /d/<id>`); the shared folders themselves cannot be deleted or renamed.

**Your computer can be the Safeer Link hub.** Until now the TV had to be on for your devices to see each other. When no hub answers on the network, the computer now hosts one itself — the same protocol, the same pinned TLS, the same trust circle and device tickets — and steps aside as soon as a hub with higher priority appears.

**A steadier connection.**

- **Fast discovery:** a hub is looked for at 0, 300, 800 and 1500 ms and the search ends at 3 s — as soon as one answers, connecting starts; after that the search continues quietly in the background. A known hub is tried at its last address first.
- **Waking up:** after suspend or a change of network (the clock jumps, the local address changes) the connection is re-established at once instead of waiting for the next retry.

**Safeer OS 0.4.2: stable, and it follows your screen.**

- **Fix: Safeer OS no longer crashes when it lists open windows.** The window list asked libwnck to rebuild itself on every read and freed objects that were still in use (a crash in `g_hash_table_remove`). Windows are now read once per change, always on the main thread.
- **The Mint panel is a safety net, not a hostage.** If Safeer OS ever ends abnormally, the Linux Mint panel is restored before the next start; after repeated crashes Safeer OS starts in safe mode and leaves the Mint panel visible. Crash traces are kept in `~/.cache/safeer-os/`.
- **Fix: the bar and the desktop follow a change of screen.** Close the laptop lid with a TV attached (3840×2160) and the bar used to stay at the old width (1920) and in the old place. Safeer OS now follows every change of screen or resolution, and keeps the space for the bar reserved.

Slovensko: **Safeer Control 2.1.0** – naprave (TV, tablica) lahko datoteke, ki jih deliš, **preimenujejo, premaknejo, izbrišejo** (v Smeti – nič se ne uniči) in **zavrtijo slike** (JPEG brez izgube). **Računalnik je lahko središče Safeer Linka:** ko v omrežju ni drugega središča, ga gosti sam – televizor ni več pogoj, da se naprave vidijo. **Stabilnejša povezava:** hitro iskanje (najdlje 3 s, nato tiho v ozadju) in takojšnja ponovna povezava po spanju ali menjavi omrežja. **Safeer OS 0.4.2:** odpravljeno sesutje ob seznamu odprtih oken; Mintov pult se po morebitnem sesutju vedno vrne, po ponovljenih sesutjih pa Safeer OS teče v varnem načinu. **Popravek:** vrstica in namizje sledita menjavi zaslona – ob zaprtem pokrovu in televizorju 3840×2160 je vrstica prej ostala široka 1920 in na starem mestu.
