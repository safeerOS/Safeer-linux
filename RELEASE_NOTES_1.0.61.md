# Safeer Browser for Linux 1.0.61 · Safeer Control 2.1.17 · Safeer OS 0.4.19

**Continue on another device – the computer as the source (Safeer Control 2.1.17, Safeer OS 0.4.19)**
- Your phone or TV can now ask this computer what Safeer OS is playing and continue at the same second ("Continue from another device" in the media centre on Android). Nothing happens on its own: the computer only answers when a device in your trust circle asks, and keeps playing unless you choose "continue here and stop there" (then it just pauses).
- A file leaves the computer only if it is in a folder shared with devices (same server, token and certificate as "Files"); a web stream is passed on with its address; when nothing is playing, the last unfinished film from the library is offered.
- "Playback for other devices" in the Safeer Control tray menu switches this off.
- `safeer-os --predvajaj <file>` opens a video or music file in the Safeer OS player (from the terminal or a launcher).
- The file server no longer logs a trace when a device closes a connection mid-stream.

Safeer Browser 1.0.61 has no changes to the browser itself.

Slovensko: **Nadaljuj z druge naprave – računalnik kot vir.** Telefon ali televizor vpraša, kaj Safeer OS na tem računalniku predvaja, in nadaljuje pri isti sekundi; nič ne gre ven brez vprašanja naprave v krogu zaupanja, datoteke le iz deljenih map. Izklop: »Predvajanje za druge naprave« v meniju Controla. `safeer-os --predvajaj <datoteka>` odpre datoteko v predvajalniku. Brskalnik brez sprememb.
