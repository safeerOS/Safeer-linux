"""Preizkus pravega Safeer DRM (castLabs Electron) v peskovniku Flatpaka Safeer Browserja (CI, od 1.0.127).

Uporaba (v Flatpaku):  python3 smoke_drm_peskovnik.py POT_DO_TOVORA

Po isti poti kot Splet (core/safeer_drm): prenese paket z izdaje (preveri SHA-256) v zasebno mapo Flatpaka, ga zazene
prek zypak-wrapper (ukaz_zagona, okolje_zagona) in izmeri:
  1. v paketu ni manjkajocih knjiznic (ldd v runtime-u GNOME 50),
  2. Electron nalozi stran (NAVIGATION_OK) brez sesutja procesa strani (PROCESS_FAILED),
  3. procesi strani tecejo v podpeskovniku: seccomp-bpf (Seccomp: 2), NoNewPrivs in svoj imenski prostor mount
     (zypak jih zazene prek portala Flatpak z expose-pids, zato so vidni tu),
  4. Widevine: prvi zagon prenese CDM (DRM_READY), drugi zagon stran dobi com.widevine.alpha (EME ok) - CDM se nalozi
     v peskovniku iz mape, ki jo zypak izpostavi (ZYPAK_EXPOSE_WIDEVINE_PATH).
Izpis je namenoma podroben (CI ne vidi vedno celega dnevnika): vsaka napaka je ena vrstica »FAIL: ...«.
"""
import json
import os
import subprocess
import sys
import tempfile
import time

LIB = os.path.abspath(sys.argv[1])
sys.path.insert(0, LIB)
from core import gostitelj, safeer_drm  # noqa: E402

URL = os.environ.get("SAFEER_DRM_SMOKE_URL", "https://example.com/")
napake = []


def fail(sporocilo: str) -> None:
    print("FAIL: " + sporocilo, flush=True)
    napake.append(sporocilo)


def dogodki(pot: str) -> list:
    try:
        with open(pot, encoding="utf-8") as f:
            return [json.loads(v) for v in f if v.strip()]
    except (OSError, ValueError):
        return []


def renderji(lastni_mnt: str) -> list:
    """(pid, seccomp, nonewprivs, svoj mnt) za procese strani Chromiuma, ki jih vidimo."""
    izid = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                ukaz = f.read().split(b"\0")
            if b"--type=renderer" not in ukaz:
                continue
            status = open(f"/proc/{pid}/status", encoding="utf-8").read()
            polja = dict(v.split(":", 1) for v in status.splitlines() if ":" in v)
            try:
                mnt = os.readlink(f"/proc/{pid}/ns/mnt")
            except OSError:
                mnt = "?"
            izid.append((int(pid), polja.get("Seccomp", "?").strip(), polja.get("NoNewPrivs", "?").strip(),
                         mnt != lastni_mnt))
        except OSError:
            continue
    return izid


def zazeni(exe, krog: int, cas: int) -> list:
    seja = tempfile.mkdtemp(prefix="drm-smoke-", dir=str(safeer_drm.mapa_sej()))
    stanje = os.path.join(seja, "events.jsonl")
    ukazi = os.path.join(seja, "command.txt")
    argumenti = [str(exe), "--parent=1", f"--url={URL}", f"--profile={os.path.join(seja, 'profil')}",
                 f"--state={stanje}", f"--command={ukazi}", f"--lastnik={os.getpid()}"]
    ukaz = safeer_drm.ukaz_zagona(argumenti)
    print(f"krog {krog}: ukaz", ukaz[:2], flush=True)
    if not ukaz or ukaz[0] != safeer_drm.ZYPAK:
        fail(f"Safeer DRM se ne zazene prek zypaka: {ukaz}")
        return [], []
    okolje = safeer_drm.okolje_zagona()
    print("ZYPAK_EXPOSE_WIDEVINE_PATH =", okolje.get("ZYPAK_EXPOSE_WIDEVINE_PATH"), flush=True)
    okolje["SAFEER_DRM_EME_PREIZKUS"] = "1"
    okolje["ZYPAK_DEBUG"] = "1"
    dnevnik = open(os.path.join(seja, "zypak.log"), "wb")
    proces = subprocess.Popen(ukaz, env=okolje, stdout=dnevnik, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    lastni_mnt = os.readlink("/proc/self/ns/mnt")
    videni = []
    konec = time.monotonic() + cas
    while time.monotonic() < konec and proces.poll() is None:
        time.sleep(1)
        d = dogodki(stanje)
        vrste = {x.get("type") for x in d}
        if "NAVIGATION_OK" in vrste and not videni:
            time.sleep(2)
            videni = renderji(lastni_mnt)
        if "NAVIGATION_OK" in vrste and videni and ("EME" in vrste if krog == 2 else bool(vrste & {"DRM_READY", "DRM_FAILED"})):
            break
    zivo = proces.poll() is None
    if zivo:
        proces.terminate()
        try:
            proces.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proces.kill()
    dnevnik.close()
    d = dogodki(stanje)
    print(f"krog {krog}: tekel do konca preizkusa: {zivo}, izhodna koda {proces.returncode}", flush=True)
    for x in d:
        print(f"krog {krog}: dogodek {x.get('type')} {x.get('detail', '')}"[:300], flush=True)
    print(f"krog {krog}: procesi strani (pid, Seccomp, NoNewPrivs, svoj mnt):", videni, flush=True)
    if not zivo or not d:
        try:
            print(open(os.path.join(seja, "zypak.log"), encoding="utf-8", errors="replace").read()[-3000:], flush=True)
        except OSError:
            pass
    return d, videni


def main() -> int:
    print("v peskovniku:", gostitelj.v_peskovniku(), "sme na gostitelja:", gostitelj.sme_na_gostitelja(), flush=True)
    if not gostitelj.v_peskovniku():
        fail("ne tece v peskovniku Flatpaka brez dostopa do gostitelja")
    print("koren Safeer DRM:", safeer_drm.koren(), flush=True)
    if not safeer_drm.prenesi():
        fail("prenos paketa Safeer DRM ni uspel")
        return 1
    exe = safeer_drm.izvrsljiva()
    safeer_drm.uskladi_logiko(exe)
    ldd = subprocess.run(["ldd", str(exe)], capture_output=True, text=True)
    manjka = [v.strip() for v in ldd.stdout.splitlines() if "not found" in v]
    print("ldd: manjkajoce knjiznice:", manjka or "nobene", flush=True)
    if manjka:
        fail("v runtime-u manjkajo knjiznice: " + ", ".join(manjka))
    d1, r1 = zazeni(exe, 1, 90)
    v1 = [x.get("type") for x in d1]
    if "NAVIGATION_OK" not in v1:
        fail("Electron ni nalozil strani (NAVIGATION_OK) v peskovniku")
    if "PROCESS_FAILED" in v1:
        fail("proces strani se je sesul (PROCESS_FAILED)")
    if not r1:
        fail("procesa strani ni videti (zypak brez expose-pids?) - peskovnika ni mogoce preveriti")
    for pid, seccomp, nnp, svoj_mnt in r1:
        if seccomp != "2" or nnp != "1" or not svoj_mnt:
            fail(f"proces strani {pid} ni v podpeskovniku: Seccomp={seccomp} NoNewPrivs={nnp} svoj mnt={svoj_mnt}")
    d2, _r2 = zazeni(exe, 2, 90)
    eme = [x.get("detail", "") for x in d2 if x.get("type") == "EME"]
    print("EME (com.widevine.alpha):", eme, flush=True)
    if eme[-1:] != ["ok"]:
        fail("Widevine v peskovniku ne dela: " + (eme[-1] if eme else "ni odgovora strani"))
    print("PASS" if not napake else "FAIL (%d)" % len(napake), flush=True)
    return 0 if not napake else 1


if __name__ == "__main__":
    sys.exit(main())
