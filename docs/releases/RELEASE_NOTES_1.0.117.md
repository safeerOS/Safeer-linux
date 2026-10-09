# Safeer Browser for Linux 1.0.117 · Safeer Control 2.1.73 · Safeer OS 0.4.75

**Firefox stays behind the Shield.** Firefox may switch on its own DNS over HTTPS and then resolve ad and dangerous domains past the Shield filter. Before doing so it checks the canary domain `use-application-dns.net`; the Shield now answers that the name does not exist, so Firefox keeps using the filtered system DNS (unless you switched DNS over HTTPS on yourself). This is not counted as a blocked ad.

**Clear message when a screen is taken over.** A computer shares its screen with one device at a time. When another device opens it, Safeer Control now shows the computer's sentence (for example "Another device is now viewing the screen.") instead of the bare code.
