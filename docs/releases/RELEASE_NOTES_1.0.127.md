# Safeer Browser for Linux 1.0.127 · Safeer OS 0.4.85 (with Safeer Control 2.1.82)

**Safeer Browser on GTK 4.** The browser is rebuilt on GTK 4 and WebKitGTK 6.0. The Flatpak carries our own patched WebKitGTK 2.54.1 and libsoup 3.8.0, and Safeer DRM for protected video – it starts only after you click Play in Safeer DRM and never without the site's permission.

**Privacy like Firefox.** Tracking protection in three levels (Standard, Strict, Custom) and a shield to turn it off for one site; per-site permissions (camera, microphone, location, notifications, autoplay, protected content); choose your DNS-over-HTTPS provider; clear browsing data, also on exit. Unwanted pop-ups are blocked – sign-in and payment windows still open. A pop-up that opens empty and then jumps to another site is blocked too.

**A real browser.** Downloads to your Downloads folder with a question before running programs; find with a match counter; print; full screen; mute a tab; zoom; links to apps (e-mail, phone, magnet) open after you confirm; network and certificate error pages in six languages; offer to make Safeer your default browser.

**Media Center, redesigned.** A left menu with your real sources, a Home page with Continue watching, Recently added, Most played and Favourites, and a now-playing bar at the bottom. Automatic playlists from your own music (Most played, Not heard for a while, genres, artists, Discover) – made on your computer, no cloud. Hide what you don't use from the menu. Play on … sends music to a network speaker (DLNA) or to your devices in Safeer Link. Audio tracks, audio and subtitle delay, subtitles from a file or the web, equaliser. The film and series catalogue loads twice as fast; live TV shows every channel logo and RTV SLO plays again. Login tokens of your media servers (Jellyfin, Navidrome, Plex …) are never stored in playlists or sent to other devices; Jellyfin 12 is supported.

**One desktop, one process.** Safeer OS, Safeer Control, Safeer Link, the Media Center, the player and the web all run in one process (640 MiB measured on the test PC). The desktop speaks six languages, uses one colour theme, works with the keyboard and the TV remote, and now has everything the previous desktop had: file actions, Continue here, Show on …, voice and notes in search, largest files, dock editing. Notifications go one way, settings for Link, the web and the desktop are in Safeer OS Settings, and the desktop widget shows what is playing.

**Linux Mint.** The desktop no longer hides behind the Mint panel or the dock; a mouse applet in the panel replaces the misleading battery icon on desktop PCs.

**Our WebKit everywhere.** GTK 4 is the default everywhere, and the .deb packages now carry the same patched WebKitGTK 2.54.1 (profile-optimised) and libsoup 3.8.0 as the Flatpak. Our WebKit fix stops pages with many `backdrop-filter` layers (for example www.24ur.com) from eating memory and a whole CPU core; it is also proposed upstream to WebKit.

**Tabs like a modern browser.** Tabs shrink instead of breaking the layout, show the site icon and the full title on hover, and sit in the window's title bar. Web pages follow the system's dark mode (you can change it).

**DNS without limits.** Safeer Shield is the default DNS (blocks ads and threats, never challenge pages such as Cloudflare or hCaptcha), with Quad9, Cloudflare, Google, AdGuard and OpenDNS over encrypted DNS, your own address, or off – and an automatic fallback if a provider fails.

**Your accounts in the Media Center.** Sign in to YouTube once (in Splet, several accounts) and your playlists are available on all your linked devices. Spotify playlists, liked songs and podcasts play in our player with our controls, and Safeer Shield mutes and skips audio ads; signing in with Google lets you pick the Google account. Twitch plays in our player without inserted ads. Sign out of any of them inside Safeer OS.

**A fuller Media Center.** Home now has discovery shelves (popular films and series, music, your YouTube and Spotify playlists, Twitch live, radio); YouTube plays inside the Media Center window; playlists are shown as track lists; search is much faster and shows one card per title with the best stream; cards show quality, language and source. Adult add-ons appear only in the Private category, only when you turn it on and only on that device. Play on … is also in the video window, and picture and sound stay in sync on network speakers (adjustable delay).

**Messages.** Archive, delete, mark read or unread, star, move or label right in the list, several at once, with Undo; reply from the list without opening the conversation.

**Desktop.** Safeer Browser instead of Firefox in the dock, one Show desktop button, distinct icons for Messages and Splet.


**Stability.** Idle and unanswered network connections are closed after 10 seconds, so they no longer pile up and crash the desktop; Safeer Link keeps listening even after a temporary error. The desktop no longer stutters every 10 seconds when no Hub is connected, and starting a magnet stream, a handover or loading dock icons no longer freezes it. The side dock comes back by itself if it closes or crashes (at most three times in ten minutes). Network speakers keep playing when the TV turns on and grabs the speaker by itself (HDMI-CEC) – if you switch to the TV yourself, your choice wins. JetStream 3.0 runs to the end again: web pages now see your real language instead of »C«, and a page may use up to half of your RAM (was a quarter) – the memory guard now stops only a page whose memory keeps growing (a real leak), not a demanding page with a short peak.
