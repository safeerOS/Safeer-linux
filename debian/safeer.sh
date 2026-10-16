#!/usr/bin/env bash
export PULSE_LATENCY_MSEC=120
export GST_PULSE_BUFFER_MS=120
# Neuporabljen od 16. 10. 2026 (debian/rules namesti packaging/safeer-launcher); ostane GTK4 kot vsi paketi.
exec python3 /usr/lib/safeer-browser/safeer_brskalnik.py "$@"
