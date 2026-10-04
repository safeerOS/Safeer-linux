# safeerctl — Safeer Link from the command line

`safeerctl` ships with Safeer Control. It does nothing by itself: it talks to the Safeer Control that is
running in the background (D-Bus, the same interface Safeer OS uses), so it sees exactly the devices in your
Safeer Link and needs no keys or tokens of its own. Nothing leaves your home network.

```
safeerctl devices                         devices in Safeer Link
safeerctl capabilities DEVICE             what a device can do
safeerctl info DEVICE                     processor, memory, storage, battery (alias: resources)
safeerctl apps DEVICE                     apps the device shares
safeerctl run APP --on DEVICE             start an app on the device
safeerctl send FILE... --to DEVICE        send files to the device
safeerctl text TEXT --to DEVICE           send text or a link to the device
safeerctl rename DEVICE NAME              rename the device for every device in Safeer Link
safeerctl internet                        internet through a phone in Safeer Link: status
safeerctl internet mode off|failover|always [--via DEVICE] [--system-proxy on|off]
safeerctl internet test [--via DEVICE] [--path mobile|wifi|any]
safeerctl internet env                    proxy variables for this shell
```

`DEVICE` is the id or the name. A unique part of the name is enough; case and diacritics do not matter
(`safeerctl info "dnevna"` finds “Dnevna soba”). If several devices match, the command says which and stops.
`APP` is resolved the same way against the apps of that device.

`rename DEVICE ""` gives the device back the name it reports about itself.

## Where it is

| Package | Command |
| --- | --- |
| `.deb` | `safeerctl …` |
| AppImage | `./Safeer-OS-*.AppImage --ctl …` |
| Flatpak | `flatpak run --command=safeerctl io.github.memelandfaner.SafeerOS …` |

Safeer Control has to be running (`safeer-control --ozadje`; Safeer OS starts it by itself). `safeerctl`
never starts it. It also works from an SSH session, cron or an agent: when the environment has no
`DBUS_SESSION_BUS_ADDRESS`, it uses the session bus at `/run/user/UID/bus`.

## For scripts and agents: `--json`

Every command accepts `--json` (before or after the command) and then prints exactly one JSON object on
standard output — also when it fails.

```
$ safeerctl devices --json
{"ok": true, "devices": [{"id": "n-…", "name": "Dnevna soba", "platform": "tv", "kind": "screen",
                          "capabilities": ["url", "text", "file", "remote", "media"], "this": false}]}

$ safeerctl capabilities "dnevna soba" --json
{"ok": true, "id": "n-…", "name": "Dnevna soba",
 "capabilities": [{"name": "url", "description": "opens a web address you send to it", "known": true}]}

$ safeerctl info telefon --json
{"ok": true, "id": "n-…", "name": "…", "info": {"hostname": "…", "sistem": "…",
 "cpu": {"jedra": 8, "model": "…", "obremenitev": 0.4}, "ram": {"skupaj": 0, "prosto": 0},
 "disk": {"skupaj": 0, "prosto": 0}, "baterija": {"raven": 92, "polni": true},
 "pomoc": {"lahko": true, "razlog": ""}}}

$ safeerctl send posnetek.mp4 --to "dnevna soba" --json
{"ok": true, "id": "n-…", "name": "Dnevna soba", "files": 1, "sent": 1, "skipped_folders": 0}

$ safeerctl info kuhinja --json
{"ok": false, "error": "There is no device “kuhinja” in Safeer Link.", "code": "ni_naprave"}
```

`info` is what the device reports about itself (`host.info` in Safeer Link): sizes are bytes, `obremenitev`
is the load, `pomoc.lahko` says whether the device may help others right now (a laptop on a low battery
does not). A device reports only what it knows — fields can be missing.

`capabilities` lists the names a device announced when it joined (`core/link_zmoznosti.py` is the registry
of names and meanings). `known: false` is a capability of a newer device that this version does not
describe yet.

Other successful answers: `apps` → `{"apps": [{"id", "name", "group"}]}`, `run` → `{"app": {…}}`,
`text` and `rename` → `{"id", "name"}`.

## Internet through a phone

A phone with Safeer OS Mobile can lend its internet to this computer over Safeer Link — no hotspot, the
phone opens each connection itself on its mobile network. Safeer Control runs a local proxy for it
(`docs/INTERNET-GATEWAY.md` has the protocol and the limits).

```
safeerctl internet mode failover          use the phone only while the home internet is down
safeerctl internet mode always --via "Phone"
safeerctl internet mode off
safeerctl internet test                   one real request through the phone: which network, which public address
eval "$(safeerctl internet env)"          this shell's programs use the proxy (curl, git, apt …)
```

The phone has to allow this computer once; the question appears on the phone the first time the computer
asks. While traffic goes through the phone Safeer sets the desktop's system proxy and restores it afterwards
(`--system-proxy off` turns that off). Destinations in the home network always go directly.

```
$ safeerctl internet --json
{"ok": true, "nacin": "izpad", "telefon": "n-…", "prek_telefona": false,
 "posrednik": {"tece": true, "naslov": "127.0.0.1", "vrata": 47890}, "fiksna": {"dela": true},
 "poraba": {"danes": 0, "mesec": 0}, "sistemski": {"vklopljen": true, "podprt": true, "nastavljen": false},
 "ponudnik": {"protocol": 2, "enabled": true, "permission": "allowed", "cellular": {"allowed": true, …}}}

$ safeerctl internet test --json
{"ok": true, "vrsta_poti": "cellular", "naslov_prek_telefona": "…", "naslov_neposredno": "…", "druga_pot": true,
 "odprto_ms": 180, "skupaj_ms": 420}
```

`nacin` is `izklopljeno`, `izpad` (failover) or `vedno` (always). A failed `test` carries the phone's reason
in `code`: `permission_required`, `denied`, `disabled`, `no_mobile`, `mobile_off`, `roaming`, `limit`,
`old_provider` (the phone runs a Safeer OS older than 0.5.47) and so on.

## Exit codes

| Code | Meaning |
| --- | --- |
| 0 | done |
| 1 | the action failed; the reason is printed (`code` in JSON) |
| 2 | wrong usage |
| 3 | Safeer Control is not running, or it is an older one that does not know the command |

`code` values `safeerctl` produces itself: `ni_controla`, `stari_control`, `ni_naprave`, `vec_naprav`,
`ni_zmoznosti` (the device did not announce the capability the command needs), `ni_programa`,
`vec_programov`, `ni_odgovora`. Other values come from Safeer Link unchanged.

## Limits

- Folders are not sent (`skipped_folders` counts them); up to 100 files per command.
- `send` needs the `file` capability and `text` the `text` capability of the target device.
- Messages are in Slovenian when the system language is Slovenian, otherwise in English. JSON field names
  and codes never change with the language.
