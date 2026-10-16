#!/usr/bin/env bash
# Safeer OS Flatpak bundle (Safeer OS + Safeer Control), same toolchain as the browser bundle.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
VERSION="$(cat packaging/VERSION_OS)"
BUILDER="${FLATPAK_BUILDER:-flatpak-builder}"
# CI (linux-packages.yml) poda manifest z WebKitom s PGO (packaging/webkit/pgo.py uporaba); lokalno brez PGO.
MANIFEST="${SAFEER_FLATPAK_MANIFEST:-io.github.memelandfaner.SafeerOS.yml}"
mkdir -p dist
"$BUILDER" --user --force-clean --repo=build/flatpak-repo-os build/flatpak-os "$MANIFEST"
flatpak build-bundle --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo build/flatpak-repo-os "dist/Safeer-OS-${VERSION}-x86_64.flatpak" io.github.memelandfaner.SafeerOS master
