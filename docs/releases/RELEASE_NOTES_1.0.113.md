# Safeer Browser for Linux 1.0.113 · Safeer Control 2.1.69 · Safeer OS 0.4.71

**Stronger protection against ad-blocker detection.** Some sites (for example internet radio) still showed "we detected an ad blocker". The general protection (still the same for every site, no per-site rules) now also answers the checks that were missed: bait elements hidden with CSS now report a normal position, tracking-pixel images load instead of failing, and the ad-tag object (`googletag`) looks ready. Blocking of ads and threats is unchanged; YouTube is excluded.
