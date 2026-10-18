# rqbit: predlog popravka gorvodno (IPv4, ko jedro nima IPv6)

**Za lastnika (pred oddajo):**

1. rqbit ima pravila za AI (`AI_POLICY.md`): vsaka uporaba AI mora biti razkrita, sicer veljajo pravila projekta
   Ghostty. Po teh pravilih (kolikor jih poznamo; strani https://github.com/ghostty-org/ghostty/blob/main/AI_POLICY.md
   tu ni bilo mogoce prebrati - preberi jo pred oddajo) so PR, narejeni s pomocjo AI, sprejeti samo za **sprejet issue**.
   Zato: najprej odpri issue (besedilo 1), pocakaj, da ga avtor potrdi, sele nato PR (besedilo 2) s sklicem nanj.
2. Pravila zahtevajo, da delo preveri clovek: pred oddajo na svojem racunalniku pozeni teste (ukazi v besedilu 2).
3. Pred issuejem preveri, ali tak issue ze obstaja (iskanje »ipv6« med issueji ikatson/rqbit) - tu dostopa do
   issuejev ni bilo, splosno spletno iskanje 18. 10. 2026 ni naslo nicesar.
4. Ko posel CI `rqbit-deb` uspe (isti prenos pod filtrom seccomp, ki zapre IPv6, na runnerju z IPv6), lahko v PR pod
   »Tested on« dodas: »the same download test in CI under a seccomp filter that makes `socket(AF_INET6, ...)` return
   `EAFNOSUPPORT` on a host that has IPv6«. Pred tem tega ne pisi - se ni preverjeno.
5. Popravek je `packaging/rqbit/ipv4-fallback-without-ipv6.patch` (za `git am`, avtor `Safeer <info@safeer.si>`).
   Velja za oznako v9.0.1 in tudi za trenutni `main` (`git apply --check` na commitu 57e95d1 z dne 8. 10. 2026).
   Koraki: fork ikatson/rqbit pod racunom Safeer, veja `ipv4-fallback-without-ipv6` iz `main`,
   `git am <pot>/ipv4-fallback-without-ipv6.patch`, testi, push, PR.

---

## 1. Issue

**Title:** rqbit does not start on Linux without IPv6 (`ipv6.disable=1`): the UDP tracker client binds `[::]:0` even with `--ipv4-only`

**Body:**

On a Linux kernel booted with `ipv6.disable=1` (also some containers and hardened systems), creating any
`AF_INET6` socket fails with `EAFNOSUPPORT`. rqbit 9.0.1 (official `rqbit-linux-amd64` release binary) does not
start there at all.

Steps (`server start`, the same with `download`):

```
$ python3 -c "import socket; socket.socket(socket.AF_INET6)"
OSError: [Errno 97] Address family not supported by protocol
$ rqbit --http-api-listen-addr 127.0.0.1:3030 server start /tmp/rqbit
ERROR rqbit: error running rqbit: error initializing rqbit session

Caused by:
    0: error starting listeners
    1: error starting TCP listener
    2: error creating socket: Address family not supported by protocol (os error 97)
```

`--listen-ip 0.0.0.0` moves the error to the DHT, and `--ipv4-only` gets the listener and the DHT going, but the UDP
tracker client still fails:

```
$ rqbit --http-api-listen-addr 127.0.0.1:3030 --ipv4-only server start /tmp/rqbit
INFO librqbit::listen: Listening on TCP 0.0.0.0:4240 for incoming peer connections
INFO librqbit_dht::dht: DHT listening on 0.0.0.0:52990
ERROR rqbit: error running rqbit: error initializing rqbit session

Caused by:
    0: error creating UDP tracker client
    1: error creating UDP socket at [::]:0
    2: error creating socket: Address family not supported by protocol (os error 97)
```

There is no option that makes rqbit start on such a system: `UdpTrackerClient::new`
(`crates/tracker_comms/src/tracker_comms_udp.rs`, line 272 in v9.0.1) always binds `[::]:0` and is created
unconditionally in `Session::new_with_opts` (`crates/librqbit/src/session.rs`, line 761), even with `--disable-trackers`.
The other `[::]` defaults are the listener (`--listen-ip` default `::`, `ListenerOptions::default()`), the DHT
(`dht_listen_addr`) and LSD (`[::]:6771`).

For the same reason three existing tests fail on such a host: `tests::e2e::test_e2e_download_tcp`,
`tests::e2e::test_e2e_download_utp` and `tests::e2e_stream::test_e2e_stream` (they listen on 127.0.0.1 with DHT
disabled, and still fail in `error creating UDP tracker client`).

Expected: rqbit uses IPv4 only when the OS has no IPv6, and `--ipv4-only` does not touch IPv6 at all.

We have a tested fix and can send a PR if you are fine with the approach (below).

*Disclosure: this report was prepared by the Safeer team with AI assistance (Claude Code); we reproduced it ourselves.*

---

## 2. Pull request

**Title:** Fall back to IPv4 when the OS has no IPv6 support

**Body:**

Fixes #<issue>.

On an OS without IPv6 support (Linux with `ipv6.disable=1`, some containers) every `[::]` bind fails with
`EAFNOSUPPORT` and the session does not start; `--ipv4-only` does not help because the UDP tracker client always
binds `[::]:0`. Details and the exact errors are in the issue.

Changes:

- `Session::new_with_opts` probes once whether an IPv6 socket can be created
  (`socket2::Socket::new(Domain::IPV6, Type::DGRAM, None)`). Only on `EAFNOSUPPORT` it logs a warning
  (`IPv6 is not available on this system (...), using IPv4 only`) and behaves as if `ipv4_only` was set, for the
  listener too. If IPv6 is available, or the probe fails for any other reason, nothing changes. The probe is skipped
  when everything is already IPv4 only. It is `cfg(unix)` (errno via `nix`); other platforms are unchanged.
- `UdpTrackerClient::new` takes `ipv4_only` and binds `0.0.0.0:0` when it is set (this also makes `--ipv4-only`
  keep the UDP tracker client off IPv6). This changes the signature of a public function of
  `librqbit-tracker-comms`; the only caller in the workspace is the session.
- `LocalServiceDiscoveryOptions` gets `ipv4_only` (default `false`); LSD then binds `0.0.0.0:6771` and joins only
  the IPv4 multicast group (`MulticastUdpSocket` already supports an IPv4 bind address).
- `rqbit share`: the default HTTP API address is `0.0.0.0:0` instead of `[::]:0` when the session is IPv4 only.

Behaviour with IPv6 available is unchanged (the probe succeeds and no option is touched).

Tests:

- `session::tests::test_fallback_to_ipv4_only_if_no_ipv6` - the decision with an injected probe:
  `EAFNOSUPPORT` -> IPv4 only (session and listener), success or another error (`EMFILE`) -> unchanged, already IPv4
  only -> no probe.
- `session::tests::test_session_starts_with_default_listen_addr` - a session with the default listener (`[::]`)
  starts; the listen address is IPv6 exactly when IPv6 sockets can be created.
- `tracker_comms_udp::tests::test_ipv4_only_binds_ipv4` - with `ipv4_only` the client binds an IPv4,
  non-dual-stack socket.

```
cargo test -p librqbit -p librqbit-tracker-comms -p librqbit-lsd
cargo clippy -p librqbit -p librqbit-tracker-comms -p librqbit-lsd --all-targets
cargo fmt --all -- --check
```

Tested on Linux x86_64 (Ubuntu 24.04 userland, Rust 1.95.0):

- kernel booted with `ipv6.disable=1`: before the change `test_session_starts_with_default_listen_addr` and the three
  e2e tests from the issue fail with `Address family not supported by protocol (os error 97)`; with it
  `librqbit` has 33 passed, 0 failed (5 ignored) and `librqbit-tracker-comms` 5 passed (1 ignored); clippy and
  rustfmt are clean.
  `rqbit server start` starts (`WARN ... IPv6 is not available on this system (Address family not supported by
  protocol (os error 97)), using IPv4 only`), listens on TCP `0.0.0.0:4240`, DHT on `0.0.0.0`, and a second rqbit
  downloads a torrent from it through a UDP tracker on 127.0.0.1 (static musl build, `--no-default-features
  --features rust-tls`).

Not tested on macOS, BSD or Windows; the fallback is limited to `cfg(unix)` and does not run elsewhere.

*Disclosure: prepared by the Safeer team with AI assistance (Claude Code was used for the root-cause analysis, the
code and the tests). A member of our team reproduced the bug and ran the tests above before submitting.*
