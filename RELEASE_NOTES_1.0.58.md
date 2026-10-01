# Safeer Browser for Linux 1.0.58 · Safeer Control 2.1.14 · Safeer OS 0.4.16

**The computer helps with live transcoding (Safeer Control 2.1.14)**
- When a device in Safeer Link cannot play a video (4K HEVC on a Full HD decoder, AV1, unsupported audio), the computer can now convert it on the fly: Safeer Control reads the original over the pinned, encrypted connection, converts it with ffmpeg – hardware (VAAPI) when the graphics card supports it, otherwise on the CPU – and streams H.264/AAC to the device as it goes. The stream stops when nobody is watching or when disk space would run low; the computer only helps when it is not busy (load, memory, battery).
- Devices pick the best helper (hardware encoder first); the computer reports its encoders in Safeer Link. Needs ffmpeg installed (package `ffmpeg`) and Safeer OS 0.5.20 / Safeer Predvajalnik 0.2.12 on the device.

Safeer Browser 1.0.58 has no changes to the browser itself.

Slovensko: **Računalnik pomaga pri sprotnem pretvarjanju** – ko naprava v Safeer Linku videa ne zna predvajati, ga Safeer Control sproti pretvori (strojno z VAAPI ali s procesorjem) in ji ga pošlje kot tok; pretvarja le, ko ni zaseden, in neha, ko nihče ne gleda. Potrebuje paket `ffmpeg`.
