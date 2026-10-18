#!/usr/bin/env bash
# Safeer OS Flatpak bundle (Safeer OS + Safeer Control), same toolchain as the browser bundle.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
VERSION="$(cat packaging/VERSION_OS)"
BUILDER="${FLATPAK_BUILDER:-flatpak-builder}"
# CI (linux-packages.yml) poda manifest z WebKitom s PGO (packaging/webkit/pgo.py uporaba); lokalno brez PGO.
MANIFEST="${SAFEER_FLATPAK_MANIFEST:-io.github.memelandfaner.SafeerOS.yml}"
# Nas rqbit (vir build/rqbit v manifestu; CI: artefakt posla rqbit-deb). Brez njega Flatpak ne gradimo: tudi v njem mora
# delati magnet na racunalnikih brez IPv6.
if [ ! -f build/rqbit/gradnja.json ]; then
    echo "Ni build/rqbit (nas rqbit): python3 packaging/rqbit/rqbit_paket.py zgradi build/rqbit (~10 min, musl-tools)" >&2
    exit 1
fi
mkdir -p dist
"$BUILDER" --user --force-clean --repo=build/flatpak-repo-os build/flatpak-os "$MANIFEST"
flatpak build-bundle --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo build/flatpak-repo-os "dist/Safeer-OS-${VERSION}-x86_64.flatpak" io.github.memelandfaner.SafeerOS master
