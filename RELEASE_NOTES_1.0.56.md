# Safeer Browser for Linux 1.0.56 · Safeer Control 2.1.12 · Safeer OS 0.4.14

**Convert for TV – devices in Safeer Link share their graphics (Safeer OS 0.4.14, Safeer Control 2.1.12)**
- **Convert for TV (1080p):** right click a video in Files → *Convert for TV (1080p) …*. The computer asks all devices at once and picks the one with the best hardware H.264 encoder that can help right now (battery, load, space) and can actually read the video (format and resolution, e.g. 4K HEVC). That device fetches the video over an encrypted, pinned connection, converts it to H.264/AAC MP4 up to 1080p – a format every TV plays – and saves it in *Downloads › Safeer Shramba*.
- **The original is never touched.** When the conversion is done you choose: *Copy to this computer* (saved next to the original as *name-1080p.mp4*) or *Leave it there* (visible in that device's Files in Safeer Link).
- If the best device declines at the last moment, the next best one takes over. If no device can read the video, Files says so right away instead of sending it around.
- Needs Safeer OS 0.5.18 (or Safeer Predvajalnik 0.2.10) on the Android device; `ffprobe` (package ffmpeg), when installed, lets the computer check the video format before sending it.

Safeer Browser 1.0.56 has no changes to the browser itself.

Slovensko: **Pretvori za televizor (1080p):** desni klik na video v Datotekah – naprava v Safeer Linku z najboljšim strojnim kodirnikom, ki ta trenutek sme pomagati in zna prebrati video, ga pretvori v H.264 do 1080p (predvaja ga vsak televizor) in shrani v *Prenosi › Safeer Shramba*. Izvirnik ostane nespremenjen; izbereš *Prenesi na ta računalnik* (zraven izvirnika) ali *Pusti tam*.
