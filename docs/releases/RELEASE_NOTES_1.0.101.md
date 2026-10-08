# Safeer Browser for Linux 1.0.101 · Safeer Control 2.1.57 · Safeer OS 0.4.59

## Safeer Link: from this computer to a device that is away from home (Safeer Control 2.1.57, Safeer OS 0.4.59)

The previous release fixed the way from a device to this computer. This one fixes the other direction – what the computer starts towards a device that is not on the home network (Global Link).

- **Sending a file to a device away from home.** The computer looked for the hub of the device only on the home network; for a phone on mobile data it answered "Naprava v tem omrežju ni dosegljiva." Now, when the neighbouring hub is not on this network, its address is the local end of the relay to it. Trust is the same as at home: the key in the hub's certificate must be the key of that member of the circle. A short connection attempt (0.7 s) tells whether the neighbour is on this network. The same path is used for fetching a file a device has sent and for the viewer page of a screen a device shares.
- **A device without a home network address.** A device with Safeer OS 0.5.58 for Android on mobile data describes its file server with an address from the documentation range (192.0.2.1): the only way to it is through its hub. The computer no longer tries such an address directly (that cost 2.5 s before the first file) – it goes through the hub at once.

Verified live (this code on a computer with Linux Mint at home):

- a phone on mobile data (4G), before: sending a file failed after 3.4 s with "Naprava v tem omrežju ni dosegljiva."; with this code the phone's hub accepted the file in 4.2 s;
- in the same setup, without any change needed: device information in 0.3 s, the list of apps in 2.5 s, text sent to the phone in 0.3 s, the list of the phone's file collections in 0.2 s;
- a TV with Safeer OS 0.5.58 at home as the file source, described with the address without a home network, traffic through link.safeer.si: first request answered in 1.5 s, the first 64 KiB read in 0.9 s, path through the hub.

Verified: 896 automated tests of Safeer Link passed locally; the whole suite runs in CI. New tests: the hub of a device reached through the relay (at home directly without touching the relay, away from home through the relay, a stranger at the old address, trust through the relay), and a device without a home network address (no direct attempt, reading through a real hub over TLS, no path without the key from the circle).

Not tested live: a phone that really is on mobile data as a file source (needs Safeer OS 0.5.58 on that phone); the screen of a phone shown on the computer while the phone is away from home; fetching a file sent by a device away from home.

Known limits: a computer as the viewer of another computer's screen still needs the same network; a torrent stream held by another device is read only on the home network; Safeer for Windows does not have these paths yet.

## Safeer Browser 1.0.101

- Packaged with Safeer OS 0.4.59 and Safeer Control 2.1.57. No changes to browsing.

Details: `docs/LINK-MESH.md`, rule 10.

Slovensko: **Od računalnika do naprave, ki ni doma.** Prejšnja izdaja je uredila pot od naprave do računalnika, ta ureja obratno smer. Pošiljanje datoteke z računalnika napravi zdoma: računalnik je središče naprave iskal samo v domačem omrežju in za telefon na mobilnih podatkih odgovoril »Naprava v tem omrežju ni dosegljiva.«; zdaj gre do njenega središča prek posrednika, z istim zaupanjem kot doma (ključ v potrdilu mora biti ključ člana kroga). Po isti poti gresta prevzem datoteke, ki jo je naprava poslala, in stran gledalca deljenega zaslona. Naprave brez domačega omrežja (Safeer OS 0.5.58 za Android na mobilnih podatkih) računalnik ne poskuša več neposredno (prej 2,5 s čakanja pred prvo datoteko) – gre takoj prek njenega središča. Preverjeno v živo: datoteka z računalnika do telefona na mobilnih podatkih (prej napaka po 3,4 s, zdaj sprejeta v 4,2 s); branje datoteke s televizorja z naslovom brez domačega omrežja prek link.safeer.si (prva zahteva 1,5 s, prvih 64 KiB v 0,9 s). Ni preizkušeno v živo: telefon na mobilnih podatkih kot vir datotek, zaslon telefona na računalniku zdoma, prevzem datoteke, ki jo pošlje naprava zdoma.
