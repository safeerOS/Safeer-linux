# Zajem zaslona prek KMS: namestitev, preverba, vklop, odstranitev

KMS (kmsgrab) zajame sliko neposredno iz gonilnika DRM in jo brez kopije v pomnilnik da kodirniku VAAPI.
Za to potrebuje CAP_SYS_ADMIN. To zmoznost ima SAMO majhen pomocnik `core/link_kms_pomocnik.py`, ki tece kot ozka storitev systemd (`DynamicUser`, brez korena, samo `CAP_SYS_ADMIN`). Glavni program Safeer Link ostane neprivilegiran in od pomocnika dobi le bralni konec cevi s pretokom H.264.

Obstojecih namestitvenih skript ta dokument ne spreminja: spodaj so rocni koraki.

## Datoteke

| Datoteka v repozitoriju | Namen |
|---|---|
| `core/link_kms_pomocnik.py` | pomocnik (samo standardna knjiznica). Enota ga zazene kot `/usr/bin/python3 -I /usr/lib/safeer/core/link_kms_pomocnik.py` |
| `packaging/systemd/safeer-kms.socket` | vticnik `/run/safeer/kms.sock` (`SocketMode=0666`: vsak lokalni proces se lahko poveze, pomocnik pa sam preveri SO_PEERCRED in aktivno sejo logind) |
| `packaging/systemd/safeer-kms.service` | storitev: `DynamicUser=yes`, `SupplementaryGroups=video render`, `AmbientCapabilities=CAP_SYS_ADMIN` in `CapabilityBoundingSet=CAP_SYS_ADMIN`, filter sistemskih klicev, `ProtectHostname`, `ProtectClock`, `ProtectProc=invisible`, `PrivateIPC` |

Pomocnik klice fiksni poti `/usr/bin/ffmpeg` in `/usr/bin/loginctl`.

## Predpogoji

- seja X11 (Wayland pomocnik zavrne, Zaslon takrat ostane pri x11grab);
- naprava VAAPI (`/dev/dri/renderD128` ali `renderD129`) in `/dev/dri/card*`;
- `ffmpeg` s `kmsgrab` in `h264_vaapi` (ukaza spodaj);
- systemd >= 248, kar zahtevata `PrivateIPC` in `ProtectProc` (`systemctl --version`), in jedro >= 5.8 za `ProtectProc=invisible` (`uname -r`);
- skupini `video` in `render`: `getent group video render`.

Preverba ffmpeg:

    /usr/bin/ffmpeg -hide_banner -devices | grep kmsgrab
    /usr/bin/ffmpeg -hide_banner -encoders | grep h264_vaapi

## Namestitev

V korenu repozitorija:

    sudo install -d -m 0755 /usr/lib/safeer/core
    sudo install -m 0644 core/link_kms_pomocnik.py /usr/lib/safeer/core/link_kms_pomocnik.py
    sudo install -m 0644 packaging/systemd/safeer-kms.socket packaging/systemd/safeer-kms.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable --now safeer-kms.socket

Omogocimo samo vticnik: storitev se zazene ob prvi povezavi (socket activation; `safeer-kms.service` nima razdelka `[Install]`). Ce paket enote namesti v `/usr/lib/systemd/system/`, uporabite tisto pot namesto `/etc/systemd/system/`.

## Preverba po namestitvi

    systemd-analyze verify /etc/systemd/system/safeer-kms.socket /etc/systemd/system/safeer-kms.service
    systemd-analyze security safeer-kms.service
    systemctl status safeer-kms.socket
    ls -l /run/safeer/kms.sock

- `verify` ne sme izpisati napak. Opozorilo o neznani nastavitvi (npr. `PrivateIPC`) pomeni prestar systemd in s tem manjso zascito.
- `security` izpise celo preglednico nastavitev in skupno oceno izpostavljenosti. Preverite, da je med zmoznostmi oznacena samo `CAP_SYS_ADMIN` (vrstici `CapabilityBoundingSet=` in `AmbientCapabilities=`) in da je `DynamicUser=` oznacen kot izpolnjen; druge vrstice niso napaka namestitve.
- vticnik mora biti `active (listening)`, `ls` pa mora pokazati `srw-rw-rw-`.

Poskusni zajem in meritev (iz seje X, kot navaden uporabnik):

    python3 tools/zaslon_primerjava_zajema.py --trajanje 10
    sudo journalctl -u safeer-kms.service -n 20 --no-pager     # sistemski dnevnik navaden uporabnik obicajno ne vidi

- V dnevniku mora biti vrstica `kms: zajem uid=... 1920x1080@60 h264`.
- Ce orodje izpise `KMS zavrnjen`, razlog najdete v vrstici `SafeerZaslonCas dogodek=kms_zavrnjen ... razlog=...` na stderr (npr. `seja_wayland_(kms_samo_x11)`, `ffmpeg_koncal`).
- Ce ffmpeg v storitvi pade zaradi filtra sistemskih klicev, je v dnevniku `SIGSYS` ali `Operation not permitted`. To preverite z `systemd-analyze syscall-filter`.

## Vklop v programu: `Zaslon(kms=True)`

`core/link_zaslon.py`, razred `Zaslon`:
- konstruktor `Zaslon(tls_mapa=TLS_MAPA, ffmpeg=None, vklopljeno=False, kms=False)` shrani `self.kms = bool(kms)`. Privzeto je izklopljen, ker kmsgrab ne narise kazalca miske;
- `zacni()` za vsako sejo prebere `self.kms` in uporabi KMS samo, ce hkrati velja: ni locenega zaslona za programe, obstaja naprava VAAPI, vticnik obstaja (`kms_na_voljo()`), prizgan je natanko en monitor (`kms_monitorji() == 1`) in `seja_aktivna() is True` (potrebuje `XDG_SESSION_ID` in `loginctl`).

Vklopite torej tam, kjer Safeer Control ustvari Zaslon: `Zaslon(..., kms=True)`, ali pred naslednjo sejo nastavite `zaslon.kms = True`. Mesto ustvarjanja najdete z `grep -rn "Zaslon(" --include=*.py .`.

Ob vsaki zavrnitvi (pomocnik ni namescen, Wayland, zajem ze tece, ffmpeg ne stece) Zaslon brez napake uporabi x11grab. Ob menjavi seje med zajemom preklopi na x11grab in tujega pretoka ne poslje.

## Odstranitev

    sudo systemctl disable --now safeer-kms.socket safeer-kms.service
    sudo rm /etc/systemd/system/safeer-kms.socket /etc/systemd/system/safeer-kms.service
    sudo systemctl daemon-reload
    sudo rm /usr/lib/safeer/core/link_kms_pomocnik.py     # samo ce je bil namescen rocno, kot zgoraj

Ce je datoteke namestil paket (preverite z `dpkg -S /usr/lib/safeer/core/link_kms_pomocnik.py` ali `rpm -qf ...`), je ne brisite rocno; enako velja za enoti, ce sta v `/usr/lib/systemd/system/`.

- `/run/safeer/kms.sock` izgine ob ustavitvi vticnika ali ob ponovnem zagonu.
- Brez vticnika `kms_na_voljo()` vrne False in Zaslon uporablja samo x11grab. V programu ni treba spremeniti nicesar, `kms=True` lahko ostane.
