# Safeer Browser for Linux 1.0.59 · Safeer Control 2.1.15 · Safeer OS 0.4.17

**Live transcoding helper (Safeer Control 2.1.15)**
- Stremio streams that require request headers (`proxyHeaders`: User-Agent, Referer, cookies) can now be transcoded for a device: the device passes the headers along and Safeer Control sends them to the source.
- The transcoding module is now shared with Safeer OS for Windows (same protocol, encoder selection per platform).
- New D-Bus method `Naprave.Ukaz(device, action, params)` for any Safeer Link command (used by Safeer OS and for diagnostics).

Safeer Browser 1.0.59 has no changes to the browser itself.

Slovensko: **Pomočnik sprotnega pretvarjanja** – tokove Stremio z zahtevanimi glavami (`proxyHeaders`) zdaj računalnik pretvori za napravo (glave gredo izvirniku); modul je skupen s Safeer OS za Windows. Nova metoda D-Bus `Naprave.Ukaz` za poljuben ukaz Linka (Safeer OS, diagnostika). Brskalnik brez sprememb.
