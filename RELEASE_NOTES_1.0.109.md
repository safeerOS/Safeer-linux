# Safeer Browser for Linux 1.0.109 · Safeer Control 2.1.65 · Safeer OS 0.4.67

Security release. After several review rounds, an independent code review (8 October 2026) of the browser, Safeer OS and Safeer Control found the issues below; this release fixes them. Each fix has a test, and the main finding of the review of the fixes themselves (F1 — update freshness) was fixed and re-verified before release. No change to everyday browsing or the media centre beyond what is listed.

## Updates: signed version list, mandatory checksum, and anti-rollback

The in-app update check (Safeer OS and Safeer Control, "a new version is available") now trusts the version list on safeer.si only when it is genuine **and fresh**.

- **Signed version list.** `razlicice.json` is signed with our Ed25519 key (`razlicice.json.sig` from the same host); a list without a valid signature is refused. The signature is separated by its own context from the threat-list signatures, so one can never pass as the other.
- **Checksum is mandatory.** A package is downloaded only with a valid 64-character SHA-256 taken from the signed list; a missing or malformed checksum no longer turns the check off. Everything goes over HTTPS only, and a redirect must stay on the same host for the list; packages from a mirror (GitHub) are allowed because their integrity is the signed SHA-256.
- **No downgrade.** `apt-get install` no longer runs with `--allow-downgrades`.
- **Freshness and anti-rollback (F1).** The signed list now carries a signed issue time and expiry (`izdano`, `potece`). The app refuses an expired list and any list older than the newest it has already seen. This closes a replay in which someone who controls the host (but not our signing key) serves a genuine **older** version to pin a computer to a known-vulnerable release and suppress real updates. Someone who has never updated is still bounded by the expiry.

## "Whole disk" no longer exposes system directories

When you turn on browsing the whole computer for a device, the file server now refuses the system trees `/proc`, `/sys`, `/dev`, `/run`, `/etc`, `/root` and `lost+found` — both in the root listing and when a label points straight at them (also through a symbolic link resolved by the real path). `/proc/<pid>/environ`, which holds process environment and tokens, is no longer reachable. Hidden files (names starting with a dot) stay hidden as before.

## DoH: the answer must match the question

The DNS-over-HTTPS proxy now checks that an `A` record actually belongs to the name that was asked (directly or through a CNAME chain), instead of taking the first address in the answer. Name compression is expanded by the DNS rules, including a pointer in the middle of a name, with a guard against pointer loops. A forged answer for an unrelated owner is rejected.

## The shield counter can no longer be inflated by a page

The counters of blocked ads and threats are now driven only by the injected scripts in a separate, isolated world (like user scripts); an ordinary page can no longer post to the counter handler. The security of blocking is unchanged.

## The start page makes no third-party request

Shortcut icons on the start page are taken from the page's own `favicon.ico` (own-scheme icons only) or a generic mark; the previous per-shortcut request to `icons.duckduckgo.com` at start-up is gone. A browser that promises to report nothing about your browsing now makes no such request when the start page opens.

## Pairing QR: the full certificate fingerprint

The QR pairing code now carries the full 64-character certificate fingerprint, compared in full by the device that scans it (it was the first 16 characters before; equality is stronger than a prefix).
