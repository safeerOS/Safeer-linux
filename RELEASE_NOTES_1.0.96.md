# Safeer Browser for Linux 1.0.96 · Safeer Control 2.1.52 · Safeer OS 0.4.54

## Safeer Link (Safeer Control 2.1.52, Safeer OS 0.4.54)

- **The screen of this computer opens from another device again.** "Connected screens" on a phone, tablet or TV asked the computer for its screen and then connected to itself instead of the computer. Every Safeer Link hub gives the address 127.0.0.1 to programs on its own machine, and that address travelled unchanged to other devices. The device kept retrying, and the computer opened a new session for every attempt. Other devices now get the address of the machine the program runs on; on the same machine nothing changes. The rule is applied when a hub sends a device list, when it receives one and when a program reads one, so one updated device on the path is enough.
- **A remote screen no longer drops while the mouse moves.** Viewing another computer from Safeer Control ended with "connection interrupted" after seconds or minutes of mouse movement. The picture was read and the input was sent over one encrypted connection from two threads, which such a connection does not tolerate.
- **A stuck screen-sharing session no longer blocks the next one.** When a viewer vanished without closing the connection (Wi-Fi drop, a TV going to sleep), the computer kept the old session. A new request was refused, or the old session ended the new one while cleaning up. A session whose viewer takes no picture for 20 seconds now ends by itself, and an old session can no longer stop a new one. A stray connection to the sharing port (wrong token, not TLS) no longer ends the session that is waiting for its viewer.
- **Sound on a device: a device that disappears does not leave the computer silent.** The same 20-second rule applies to the sound stream; the computer's own sound returns.
- **Small messages through Global Link no longer wait for each other.** Measured round trip through the relay: 71 ms before, 51 ms now (worst case 127 ms before, 58 ms now). Between the relay and the hub on the same machine: 41 ms before, 0.2 ms now.
- **A device that is reachable only through Global Link is not asked for its screen.** The picture travels directly between two devices in the same network. The viewer now says so at once; before, the device opened a port and waited in vain.

Verified: 1576 automated tests. with real devices – a phone whose app was not updated failed with "failed to connect to /127.0.0.1" before and viewed this computer's screen for 10 minutes without a drop after the computer was updated; a Windows computer viewed this computer's screen for more than 5 minutes on one connection while its mouse made 11,000 pointer movements. The message for a device reachable only through Global Link is covered by tests, not by a real device.

Known limits: screen and sound need a direct path in the same network. If neither the computer nor the hub the viewing device is attached to is updated, the old behaviour remains.

## Safeer Browser 1.0.96

- No changes of its own; packaged with Safeer OS 0.4.54 and Safeer Control 2.1.52.

Details: `docs/LINK-MESH.md` (rule 7).

Slovensko: **Zaslon tega računalnika se z druge naprave spet odpre.** »Povezani zasloni« na telefonu, tablici ali televizorju so računalnik prosili za sliko, nato pa so se povezali sami nase: vsako središče Safeer Linka programom na svoji napravi pripiše naslov 127.0.0.1 in ta naslov je nespremenjen potoval k drugim napravam. Zdaj dobijo naslov računalnika; zadošča ena posodobljena naprava na poti. **Oddaljeni zaslon se med premikanjem miške ne prekine več.** **Seja deljenja zaslona, ki obvisi, ne ustavi naslednje** – če gledalec 20 sekund ne prevzame slike, se seja konča sama. Enako velja za zvok na napravi. Drobna sporočila prek Global Linka ne čakajo več drugo na drugo (71 ms → 51 ms). Naprave, ki je dosegljiva samo prek Global Linka, za sliko ne prosimo – gledalec takoj pove, da slika deluje samo v istem omrežju.
