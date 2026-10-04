# Preizkusno okolje za Scit (filtriranje DNS): pravi systemd + systemd-resolved + NetworkManager, kot na
# namiznem Linux Mintu 22 (osnova Ubuntu 24.04). Poganja se z --privileged in /sbin/init kot PID 1.
FROM ubuntu:24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update \
 && apt-get install -y --no-install-recommends systemd systemd-sysv systemd-resolved dbus network-manager polkitd \
      python3 python3-cryptography iproute2 iputils-ping dnsutils curl ca-certificates udev pkexec flatpak \
 && apt-get clean && rm -rf /var/lib/apt/lists/*
# NetworkManager naj upravlja ethernet (namizni Mint ima isto prazno datoteko) in veth vsebnika.
RUN : > /etc/NetworkManager/conf.d/10-globally-managed-devices.conf \
 && ln -sf /dev/null /etc/udev/rules.d/85-nm-unmanaged.rules \
 && systemctl enable systemd-resolved NetworkManager \
 && (systemctl mask systemd-networkd.service systemd-networkd-wait-online.service NetworkManager-wait-online.service \
      getty@tty1.service console-getty.service systemd-timesyncd.service || true)
STOPSIGNAL SIGRTMIN+3
CMD ["/sbin/init"]
