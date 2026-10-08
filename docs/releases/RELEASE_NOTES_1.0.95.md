# Safeer Browser for Linux 1.0.95 · Safeer Control 2.1.51 · Safeer OS 0.4.53

## Safeer Link (Safeer Control 2.1.51, Safeer OS 0.4.53)

- **A stopped device can be released from the notification.** When the hub stops a device, the block ends by itself after 10 minutes to an hour. If the stopped device was one of yours, there was nothing to speed that up with. The notification now has the button **Release**: one click ends the block and a notification confirms that the device can connect again.
- **Pairing by code can be reopened from the notification.** When guessing closes pairing by code (for an hour, a day or a week), the notification has the button **Open pairing by code**. After reopening, the lower limits still apply and the next closure lasts longer – the guard does not forget that somebody was guessing.
- **The buttons work in the bubble and in the tray.** The desktop reports a notification as closed as soon as its bubble fades, although it stays in the notification tray; the button there works too. A button of a block that has already ended does nothing.

Verified: 1525 automated tests; in Cinnamon in a test container against a hub over a real network – the button in the bubble and the button in the tray both release the stopped device, the hub answers it again and a notification confirms the release.

Known limits: the buttons need a desktop that shows notification actions (Cinnamon does); the fallback through `notify-send` has none. There is still no list of stopped devices in the interface.

## Safeer Browser 1.0.95

- No changes of its own; packaged with Safeer OS 0.4.53 and Safeer Control 2.1.51.

Details: `docs/LINK-DEFENCE.md`.

Slovensko: **Ustavljeno napravo sprostiš kar iz obvestila.** Ko središče Safeer Linka ustavi napravo, zapora mine sama (10 minut do ene ure). Če je bila ustavljena tvoja naprava, doslej nisi imel s čim pohiteti: obvestilo ima zdaj gumb **Sprosti**. Obvestilo o zaprtem povezovanju s kodo ima gumb **Odpri povezovanje s kodo**; po odprtju še naprej veljata nižji meji in naslednja zapora je daljša. Gumba delujeta v oblačku obvestila in pozneje v pladnju obvestil. Preverjeno v Cinnamonu proti središču po pravem omrežju.
