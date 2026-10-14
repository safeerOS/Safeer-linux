## What and why

<!-- What was broken or missing, and why this change is the right fix. -->

## How I checked it

<!-- Tests you ran, and the device / distribution where you saw it work. -->

- [ ] `PYTHONPATH=tests xvfb-run -a python3 -m pytest -q $(python3 tools/razdeli_teste.py gtk3 --poti)` passes
- [ ] `PYTHONPATH=tests xvfb-run -a python3 -m pytest -q $(python3 tools/razdeli_teste.py gtk4 --poti)` passes
- [ ] New behaviour has a test
- [ ] No code for one named website (CONTRIBUTING.md)
- [ ] User-visible text is in every language the file already has (or marked as English-only below)
- [ ] README updated if the change alters what Safeer does
- [ ] No personal data, keys or tokens in the diff
