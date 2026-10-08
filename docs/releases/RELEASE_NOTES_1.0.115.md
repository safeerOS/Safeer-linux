# Safeer Browser for Linux 1.0.115 · Safeer Control 2.1.71 · Safeer OS 0.4.73

**Sites no longer detect the ad blocker when they replace the ad library.** Some sites (for example the internet radio liveone.com) replace the Google ad library (`googletag`) with a new object while loading and, a few seconds later, conclude that it was blocked. The general protection (the same for every site) now makes the replaced library look ready as well. Checked on the real site: one detection before, none now. Blocking of ads and threats is unchanged; YouTube is excluded.
