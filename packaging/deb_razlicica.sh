#!/usr/bin/env bash
# Razlicica za polje Version paketa .deb iz razlicice Safeerja (packaging/VERSION*, oznaka izdaje).
#
#   1.0.127        -> 1.0.127          (stabilna: nespremenjena)
#   0.4.86-beta.2  -> 0.4.86~beta.2    (beta kanal, docs/BETA.md)
#
# Zakaj: dpkg bere »0.4.86-beta.2« kot 0.4.86 z revizijo »beta.2« in jo uredi ZA 0.4.86 (preverjeno 18. 10. 2026:
# dpkg --compare-versions 0.4.86-beta.2 gt 0.4.86 je res), zato koncna izdaja ne bi bila posodobitev bete in apt brez
# --allow-downgrades je ne bi namestil. Tilda je v dpkg pred vsem: 0.4.86~beta.2 < 0.4.86. Oznaka gita tilde ne dovoli,
# zato ostane povsod drugje »-beta.N« (imena datotek, --version, seznam razlicic); core/os_posodobitve.kljuc_razlicice
# razume obe obliki.
set -euo pipefail
[ $# -eq 1 ] || { echo "uporaba: $0 RAZLICICA" >&2; exit 2; }
printf '%s\n' "$1" | sed -E 's/-((alpha|beta|rc)(\.[0-9]+)?)$/~\1/'
