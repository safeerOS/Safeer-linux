# Safeer Browser for Linux 1.0.98 · Safeer Control 2.1.54 · Safeer OS 0.4.56

## Safeer Link (Safeer Control 2.1.54, Safeer OS 0.4.56)

- **A file sent from another computer arrives.** With Link Mesh every device has its own hub, and a computer hands a file to the hub of the device it is for – so a file for this computer lands at this computer's own hub. The message about the file (`share.file`) does not say which hub holds it, and Safeer Control asked only the sender's hub whenever the sender was signed in at a neighbouring hub; a computer with its own hub is listed exactly like that. The file stayed in the hub's store and never reached the downloads folder. Safeer Control now asks its own hub first and the sender's hub next; the next one is asked only when the previous one answers 404.
- **"Screen" on the "Share with" panel works again.** The computer asked the hub it is signed in to – its own – to show its screen on the other device. The hub of a computer does not relay screens, and Safeer Control with its own hub has no pairing token, which the request demanded before anything else. Sharing now starts at the hub of the target device, signed in with the key of this computer, the same way a file is handed over. A device whose hub cannot show a shared screen – today another computer – gets a clear message ("This device cannot show this computer's screen yet") instead of the advice to update it.
- **Two computers in one network no longer advertise their hub under the same name.** The mDNS instance name was "safeer-" plus the last 8 characters of the id; the id of every Safeer Control ends in "-control", so two computers both announced "safeer--control" and the registration of the second one failed silently. The name now comes from the part of the id that differs, a taken name gets a suffix, and a failed registration is written to the log.
- **Another program on the hub's port no longer prevents hosting.** The hub refused to start whenever anything listened on 127.0.0.1:8990. It now refuses only when a Safeer hub answers there, or when that cannot be ruled out.
- **A pairing is not forgotten when signing in with the key fails for a passing reason.** Without a pairing token the connection then tried an empty token, got 401, and the caller dropped the pairing; the device stayed disconnected until somebody connected it again. A failed signature now counts as a refusal only on an explicit 401 or 403.
- **The "Share with" panel says why renaming failed.** After a failed rename the panel kept showing "Sending …"; the reason was printed only next to the device list.
- **One Safeer Link core for Linux and Windows.** Safeer OS for Windows carried its own, older copy of the hub. Eight core files are now identical in both repositories, and the tests of the core run on Windows as well.

Measured: with a Windows computer as the sender, Safeer Control 2.1.53 left the file in the hub's store; with 2.1.54 it arrived in the downloads folder. Screen sharing was run with this code against a phone in the home network with a drawn test pattern in place of the capture: 71 frames in 18 seconds, the viewer on the phone showed them and closed when sharing stopped.

Verified: 1703 automated tests. A new test runs the Safeer Link page itself (in Node, with stand-in page elements) and feeds it the events the backend sends; until now tests only searched the page for text.

Not tested live: starting screen sharing with the button in the Safeer Control window, and the capture of the real screen in that path (the capture code is unchanged).

Known limits: a phone whose Safeer app is in the background shows a notification instead of opening the shared screen (Android does not let an app open a window from the background). The screen of a computer cannot be shown on another computer yet: the hub of a computer does not relay screens, and the panel says so.

## Safeer Browser 1.0.98

- The built-in Safeer Link screen is the same page: the renaming message and the description of "Screen" (no "the system will ask for permission first" – on a computer it does not). Otherwise packaged with Safeer OS 0.4.56 and Safeer Control 2.1.54.

Details: `docs/LINK-MESH.md`.

Slovensko: **Datoteka, poslana z drugega računalnika, pride.** V Link Meshu računalnik datoteko odda središču naprave, ki ji je namenjena – torej našemu; Safeer Control jo je iskal samo pri pošiljateljevem središču in datoteka je ostala v zalogi središča. Zdaj najprej vpraša svoje središče, nato pošiljateljevo. **»Zaslon« na plošči »Deli z« spet deluje:** deljenje zaslona se začne pri središču ciljne naprave (prej pri središču računalnika, ki zaslona ne posreduje). Na drugem računalniku zaslona še ni mogoče pokazati; plošča to pove. **Dva računalnika v istem omrežju se ne oglašata več z istim imenom** (»safeer--control«), drugemu oglas prej ni uspel. Drug program na vratih 8990 ne prepreči več gostovanja središča; seznanitev se ne pozabi več, če prijava s ključem spodleti iz prehodnega razloga; plošča pove, zakaj preimenovanje ni uspelo. **Jedro Safeer Linka je zdaj isto v Linuxu in Windows.** Ni preizkušeno v živo: začetek deljenja zaslona z gumbom v oknu Safeer Controla.
