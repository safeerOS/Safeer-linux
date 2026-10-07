# Safeer Browser for Linux 1.0.106 · Safeer Control 2.1.62 · Safeer OS 0.4.64

## Security: commands between devices are signed with the device key and encrypted from device to device (Safeer Control 2.1.62)

Release 1.0.105 made every device decide for itself what each other device may reach on it. That decision, however, still rested on the device id which the hub writes into a message it routes. Measured on 7 October 2026 in a local test: an id that merely looks like the id of another device was given that device's access. And by construction a hub routes these messages unencrypted and writes the sender into them itself, so whoever hosts a hub could read the commands and answers it routes (file lists, what is playing, addresses and tokens of the file server) and name any sender.

From this release two devices prove their keys to each other, and the device that holds the content decides by the key:

- **A protected session between two programs.** Each side signs its part of the handshake with the device key – the key that is already in your circle of trust – and the other side verifies it with the key from *its own* copy of the circle. The session key comes from a one-time ECDH exchange (P-256), so the device key only ever signs. Messages are encrypted with AES-256-GCM, each direction with its own key and a strictly increasing counter.
- **What travels protected:** commands (`control.command`), their answers (`control.result`), a page or a stream that opens by itself (`cast.url`), playback control (`cast.control`) and "continue on this device" (`handoff.request`). The hub forwards a signed handshake and encrypted pieces; it sees neither the command nor the answer. The address, the certificate fingerprint and the token of the file server arrive inside the protected answer.
- **Access is decided by the key.** For a protected message the computer looks up access by the id derived from the *verified key*, not by the id written into the message.
- **No way back to unprotected.** Once a device has proven its key to this computer, the computer no longer accepts these messages unprotected in that device's name – from anyone. A device that announces protection is asked to prove its key as soon as it appears in the device list, not only at the first command.
- **An answer must come from the device that was asked.** An answer to a protected command is accepted only from the verified session of that device.
- **An id that carries another device's name gets nothing.** An id derived from a key (`n-…`) under which the circle of trust holds a *different* key has no access at all – on the unprotected path too. A file you send explicitly to such an id is not reachable by any other id.
- **Only the agreed message types travel protected.** A paired device cannot use the protected path to send what otherwise only a hub sends (the device list, the circle of trust, a pairing code).
- **Older devices keep working as before** until they are updated – and are only as protected as before. When a program without protection sends a command in the name of a device that has it, it receives the answer "The command did not arrive protected. Update Safeer on the device that sends it."

Both devices need this release for protection: Safeer Control 2.1.62 / Safeer Browser 1.0.106 on a computer, Safeer OS 0.5.64 on a TV, tablet or phone. Update all Safeer programs on one device together – they share the device key, and once one of them has proven it, updated devices refuse commands from an older program of the same device.

**Measured live on 7 October 2026** (a computer with Safeer Control 2.1.62 built from this code and a test phone with Safeer OS 0.5.64, in a Link whose other devices were still on older versions):

- The two devices proved their keys to each other at first sight, without any command; both recorded it.
- Commands from the computer to the phone and their answers (device information, the list of programs) travelled protected; a short command with its answer took 0.02–0.03 s.
- The phone received the list of folders the computer shares – also after the program on the computer had been restarted twice. That this command travelled protected follows from the rules (a sender does not send an unprotected command to a device that announces protection, and the computer does not accept one in the name of a device that has proven its key); it was not measured separately in this direction.
- With the previous release of the program put back on the computer (2.1.61, without protection) the phone refused the same commands with the message quoted above; with this release they worked again.
- A long message from the computer to the phone: 120 kB in 3 pieces (answered after 0.10 s) and 700 kB in 15 pieces (0.32 s).
- After the program on the phone had been restarted, the first command took 0.13 s (a new handshake and a resend), the next one 0.02 s again.
- Older devices in the same Link worked as before: a TV on an older version answered over the unprotected path, and a device with 0.5.63 decided by its own access rules as before.

**Not measured live** (covered by code tests only): a page or a stream that opens by itself, playback control and "continue on this device" over the protected path; a long message from a phone to the computer; a hub's refusal for a device that has left; a forged sender or a look-alike id in a real Link (checked by code tests and in a separate test hub); that a hub cannot read the messages (code tests; traffic was not captured); Global Link; a TV, a tablet and other phones with this release; control of a shared screen.

Tests: The whole suite passes locally both ways it is run: 1075 tests with pytest (10 skipped) and 1913 tests with unittest, the way CI runs it (23 skipped). New: `tests/test_link_e2e.py` (fixed test vectors shared with the Android implementation, the handshake, a hostile hub, look-alike ids, the connection of a program); `tests/test_link_dostop.py` extended (access by key, refusal of unprotected commands, storage keyed by id).

Not closed by this release:

- A device that has not been updated can still be impersonated towards other devices by whoever hosts a hub or presents its id – exactly as before this release. Update every device.
- Sync (bookmarks, open pages, positions in films – `sync.data`), a shared screen (`share.screen`) and playback state (`cast.status`) still travel as before: a hub sees them and could forge them.
- What you send explicitly (text, a file, a chat message) is forwarded and seen by the hub as before.
- Content itself (files, video and audio streams, the picture of a screen) travels over its own connections as before; this release does not change them.
- A hub can still drop or delay messages.
- Any member of the Link can still remove or rename a device, and sees the pairing code of a new device.
- The narrower circle is still set on each device separately.
- Safeer Control for Windows and Safeer Browser for Android (the mobile browser) do not have protection yet.

## Safeer OS 0.4.64 · Safeer Browser 1.0.106

- Released together with Safeer Control 2.1.62. Safeer Link inside the browser uses the same protection. No other changes.

Slovensko: **Varnost: ukazi med napravami so podpisani s ključem naprave in šifrirani od naprave do naprave.** Izdaja 1.0.105 je uvedla, da vsaka naprava sama odloča, kaj ji druga naprava sme. Ta odločitev pa je še vedno slonela na oznaki naprave, ki jo v posredovano sporočilo vpiše središče. Izmerjeno 7. 10. 2026 v krajevnem preizkusu: oznaka, ki je le podobna oznaki druge naprave, je dobila njen dostop. Iz zgradbe pa sledi: središče ta sporočila posreduje nešifrirana in pošiljatelja vpiše samo, zato bi jih, kdor središče gosti, lahko bral in vanje vpisal kateregakoli pošiljatelja. Zdaj si napravi pred ukazom dokažeta ključ: vsaka podpiše svoj del dogovora s ključem naprave, druga ga preveri s ključem iz svojega kroga zaupanja; sporočila so šifrirana (AES-256-GCM), ključ seje nastane iz enkratne izmenjave ECDH. Zaščiteno gredo ukazi, odgovori nanje, stran ali pretok, ki se odpre sam, nadzor predvajanja in »nadaljuj na napravi«; naslov, prstni odtis in žeton strežnika datotek pridejo v zaščitenem odgovoru. O dostopu odloča ključ, ne oznaka. Ko naprava ključ enkrat dokaže, računalnik v njenem imenu ne sprejme več nezaščitenega ukaza – od nikogar; naprava, ki zaščito napove, ključ dokaže takoj, ko se pojavi v seznamu naprav. Odgovor na zaščiten ukaz velja samo iz seje naprave, ki smo jo vprašali. Starejše naprave delajo kot prej, dokler jih ne posodobiš – in so zaščitene le toliko kot prej. Zaščita deluje, ko imata obe napravi to izdajo (računalnik: Safeer Control 2.1.62; Android: Safeer OS 0.5.64); vse programe Safeer na eni napravi posodobi skupaj. Kaj ostaja odprto, je našteto zgoraj (»Not closed by this release«).
