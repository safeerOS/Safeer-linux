# Safeer Browser for Linux 1.0.114 · Safeer Control 2.1.70 · Safeer OS 0.4.72

**Stronger protection against ad-blocker detection.** Some sites (for example internet radio) still showed "we detected an ad blocker". The general protection (still the same for every site, no per-site rules) now also answers the checks that were missed: bait elements hidden with CSS now report a normal position, tracking-pixel images load instead of failing, and the ad-tag object (`googletag`) looks ready. Blocking of ads and threats is unchanged; YouTube is excluded.

**Solidarity circle: work moves on when a helper fails.** When a device that was converting a video for you drops off the network (for example a phone on another Wi-Fi) or its video decoder fails, the job now goes to the next available device instead of stopping with an error.
