# Safeer Link: defence of the hub

Every device in Safeer Link runs its own hub (see `LINK-MESH.md`). A hub listens in the home network; only devices
of the circle of trust have any business there. This document describes what a hub does about everybody else.

## What a hub reveals today

Found in a review of the code on 4 October 2026 (Linux 1.0.93, Android 0.5.48):

| Channel | Who sees it | What |
| --- | --- | --- |
| mDNS advert `_safeercast._tcp` | everyone in the same network, also on a foreign Wi-Fi | device name, certificate fingerprint (`fp`), device id (`id`) — all three permanent |
| Hub port (8990 by default) | everyone in the same network | an open TLS port; the certificate with the permanent key goes to anyone who connects |
| Pairing paths (`/cast/pair/*`) | everyone in the same network | that a hub exists; five guesses of the code per sign-in |
| Relay (Global Link) | the relay operator | the device key, the ids of the circle (`allow`), the public IP address |

A hub never talks to the internet directly (only private addresses are accepted), a WebSocket needs a one-time
ticket, tokens travel only over TLS with a pinned fingerprint, and the relay carries the TLS of Safeer Link end to
end — it sees encrypted bytes only.

Until now nobody **counted** hostile behaviour: a device in the network could probe paths, guess pairing codes
(every start of a pairing shows the user a notification), send refused signatures and open connections without end.
Attempts were limited only inside one sign-in.

## Stage 1 (implemented): count, block, tell the user

`core/link_obramba.py` — pure logic, the same module for Linux and Windows.

Every hostile event has a weight. When the weights of one source (IP address) reach **400 within 60 seconds**, the
source is blocked.

| Event | Weight | Alone, this many per minute block the source |
| --- | --- | --- |
| accepted connection of a source that is not trusted | 1 | 400 |
| TLS handshake failed (not TLS, port scanner, silent connection) | 10 | 37 |
| probing: a path the hub does not have, a malformed request | 10 | 37 |
| refused signature, ticket or token; a QR code that does not exist | 20 | 20 |
| broken WebSocket frame | 20 | 20 |
| pairing: a wrong code, too many attempts, a start of a QR sign-in | 40 | 10 |
| pairing with a code: a start (each one shows the user a notification with the code) | 100 | 4 |

* **A block is silent.** The connection of a blocked source is closed right after it is accepted: no TLS handshake,
  no certificate, no answer.
* It lasts **10 minutes**, twice as long at every repetition (up to one hour); a day without a block resets the
  count.
* **A source that has just proved to be a member of the circle** (valid signature, ticket or token) is trusted for
  10 minutes: plain connections are not counted for it (a phone that browses a folder of pictures opens hundreds),
  hostile events count half.
* **The device itself** (127.0.0.1, ::1) is never blocked: its own programs and the channels of Global Link arrive
  from there.
* What is *not* hostile: HTTP 405 (it is part of how devices recognise a hub), 409 and 503 (state, not attack).
* A legitimate device that keeps signing in under an id the hub does not know — one refused challenge and one
  plain-HTTP probe every 15 seconds — stays far below the threshold (128 of 400).
* **Attack:** three different sources blocked within 30 minutes, or the same source blocked for the third time.

The user is told: a desktop notification says which address was stopped, why and for how long, and that their own
devices keep working; an attack gets its own notification. Both are also written to the log. If the hub knows a
device at that address, the notification names it and says to connect it again afterwards — then it is most
likely the user's own device with a broken sign-in, not a stranger. There is no list of blocked sources in the
interface yet; a block ends by itself.

Guessing the six-digit pairing code: before, five guesses per sign-in and as many sign-ins as the attacker liked.
Now a sign-in with its five wrong codes and the start of the next one block the source: about 15 guesses in the
first hour and about 5 per hour after that (the block grows to one hour), against a million possible codes and a
new code at every sign-in. The user sees at most four pairing notifications before the source is stopped.

## Planned (not implemented yet)

1. **Hidden advert.** The mDNS advert carries no name, fingerprint or id, only a label that changes every few
   hours and that only the circle can resolve. Advertising only in a trusted network or while the user has pairing
   open.
2. **Dark port.** A random port; a client introduces itself in the TLS handshake (SNI) with a value only the circle
   can compute. Without it the hub ends the handshake before it sends its certificate.
3. **Change of address.** On an attack the hub moves to a new port and a new label and tells the trusted devices
   over the connections that already exist.
4. **Relay.** A changing label instead of the id from the key, several interchangeable rendezvous points.

Stages 1–3 need no "flag day": a hub keeps the old fields and the default port for as long as one device of the
circle does not understand the new ones.
