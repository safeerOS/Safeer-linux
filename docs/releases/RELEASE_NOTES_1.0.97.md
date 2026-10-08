# Safeer Browser for Linux 1.0.97 · Safeer Control 2.1.53 · Safeer OS 0.4.55

## Safeer Link (Safeer Control 2.1.53, Safeer OS 0.4.55)

- **After it starts, the computer is back in Safeer Link sooner.** For every pair of hubs there is one connection: the hub with the smaller id calls first and the other one waits up to 40 seconds. A hub that had just started therefore waited until its neighbours found it in their next search round (every 15 seconds) – the neighbours do not know that it was restarted. A hub now calls the neighbours it remembers from its previous run right after it starts, before the first mDNS search. If a neighbour calls at the same moment, both sides keep the connection opened by the smaller id, as before.
- **The computer tells the other device every address it has on the home network.** For "sound on a device" the computer listed only the address on its default route. A computer that sends all its traffic through a VPN told a device in the same network only the address of the tunnel, which that device cannot reach. The list now holds, most likely first and at most four: the address on the route to the hub, the addresses of the local network interfaces (the one on the default route first; interfaces of containers and virtual machines are left out), and the addresses of tunnels last.
- **The remote screen no longer depends on a single address.** The address of a device in the device list is assigned by the hub and can be wrong for a device the hub sees only indirectly (the 127.0.0.1 bug fixed in 1.0.96). In its answer to `screen.start` the computer now lists its own addresses (`hosts`); the viewer tries the address from the device list first and then the listed ones – each once, at most four, 4 seconds each when there are several. A connection is accepted only when the certificate matches the fingerprint from the answer, and the one-time token is sent only after that, so a device on a wrong address never sees it.
- **A readable sentence when a device cannot be reached**, instead of "timed out" or "[Errno 113] No route to host".
- **Files: a refused oversized request gets its answer.** The file server refused a request with a too large body with 413 before reading the body and closed the connection at once; a client that was still sending saw a broken connection instead of the answer. The server now reads and discards what the client is still sending (at most 256 KiB and 1 second) before it closes.

Measured: after a cold start of Safeer Control (stopped for 45 seconds) the device list was complete after 8.6 seconds before and after 5.2 seconds now (one run each). A Windows computer was back in Safeer Link 26 and 51 seconds after its program started before, 15 and 18 seconds now. With a deliberately wrong address from the device list the previous viewer failed with "No route to host"; the new one gave up on the wrong address after 3 seconds and showed the screen of a Windows computer through the address that computer had listed. Compatibility in both directions was checked with real devices: new viewer with a computer that does not list addresses yet, previous viewer with a computer that does.

Verified: 1621 automated tests. The order of the listed addresses with a VPN was checked with injected interface lists and on this computer, not with a real VPN.

Known limits: a device without an address in the device list (reachable only through Global Link) is still not asked for its screen.

## Safeer Browser 1.0.97

- No changes of its own; packaged with Safeer OS 0.4.55 and Safeer Control 2.1.53.

Details: `docs/LINK-MESH.md` (rules 7 and 8).

Slovensko: **Po zagonu je računalnik hitreje v Safeer Linku.** Središče po zagonu samo pokliče naprave, ki jih pozna iz prejšnjega teka, in ne čaka, da ga najdejo v svojem naslednjem krogu iskanja (hladen zagon Safeer Controla: seznam naprav poln po 8,6 s prej in po 5,2 s zdaj). **Računalnik drugi napravi našteje vse svoje naslove v domačem omrežju**, ne samo naslova na privzeti poti – pomembno za zvok na napravo in zaslon računalnika, kadar gre ves promet skozi VPN. **Oddaljeni zaslon poskusi vse naslove računalnika**: najprej naslov iz seznama naprav, nato tiste, ki jih računalnik našteje sam; z namenoma napačnim naslovom iz seznama se je zaslon računalnika z Windows odprl po 3 sekundah, prejšnja različica je javila »No route to host«. Namesto sistemske napake zdaj piše razumljiv stavek. **Datoteke:** zavrnjena prevelika zahteva dobi odgovor (413), ne prekinjene povezave.
