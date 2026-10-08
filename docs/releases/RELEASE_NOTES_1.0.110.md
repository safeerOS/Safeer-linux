# Safeer Browser for Linux 1.0.110 · Safeer Control 2.1.66 · Safeer OS 0.4.68

Hardening release for DNS-over-HTTPS and housekeeping. Each change has a test.

## DNS-over-HTTPS: IPv6-only sites and the local network

- **IPv6-only sites now resolve.** The DoH resolver asked only for IPv4 (A) records, so a site that exists only over IPv6 failed with DoH switched on. It now asks for IPv6 (AAAA) as well, but only when there is no IPv4 answer, so ordinary sites behave exactly as before. A resolver error is never retried as AAAA.
- **Local network is refused by default.** A custom DoH server (Pi-hole, router) can answer a public-looking name with a home-network address. By default such targets (10/8, 172.16/12, 192.168/16, 100.64/10, fc00::/7) are now refused; loopback, link-local and unspecified addresses are always refused. A new setting, **Allow the local network (router, NAS, Pi-hole)**, turns this on for people who really use names that resolve to their home network. It is off by default, in all six languages.
- Traffic to literal home-network addresses and `.local` names never went through the DoH proxy and is unchanged.

## Housekeeping

- **Per-site ad-block recipe removed.** The built-in per-site recipe (Hookshot) went against our own contribution rule that behaviour must not be special-cased per website; the shield now relies on the filter lists only. A test guards against recipes for individual sites.
- **Release notes moved to `docs/releases/`**, so the repository root stays readable. `CONTRIBUTING.md` and `tests/README.md` describe the new place.

## Known limit

The ad counter can still undercount in rare cases (requests blocked before the page reports them); it is never inflated.
