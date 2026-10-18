#!/usr/bin/env bash
# Profila AppArmor nasih zaganjalnikov v paket .deb: /etc/apparmor.d/<profil> kot datoteka nastavitev (conffile - lastnik
# ali skrbnik jo sme spremeniti, dpkg njegove spremembe ne povozi). Nalozi ju postinst, odstrani postrm (build_os_deb.sh,
# build_deb.sh). Zakaj: glej packaging/apparmor/safeer-os in core/peskovnik_userns.py.
#   namesti.sh KOREN_PAKETA PROFIL...
set -euo pipefail
TU="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KOREN="${1:?Uporaba: namesti.sh KOREN_PAKETA PROFIL...}"
shift
install -d -m 755 "$KOREN/etc/apparmor.d" "$KOREN/DEBIAN"
for profil in "$@"; do
    install -m 644 "$TU/$profil" "$KOREN/etc/apparmor.d/$profil"
    grep -qxF "/etc/apparmor.d/$profil" "$KOREN/DEBIAN/conffiles" 2>/dev/null \
        || echo "/etc/apparmor.d/$profil" >> "$KOREN/DEBIAN/conffiles"
done
chmod 644 "$KOREN/DEBIAN/conffiles"
