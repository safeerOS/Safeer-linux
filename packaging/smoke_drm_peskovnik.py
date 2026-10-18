"""Preizkus pravega Safeer DRM (castLabs Electron) v peskovniku Flatpaka Safeer Browserja (CI, od 1.0.127).

Uporaba (v Flatpaku):  python3 smoke_drm_peskovnik.py POT_DO_TOVORA

Po isti poti kot Splet (core/safeer_drm): Safeer DRM iz paketa (/app/lib/safeer-browser/safeer-drm, od 1.0.127 v paketu,
brez Widevine CDM), zagnan prek zypak-wrapper (ukaz_zagona, okolje_zagona). Izmeri:
  1. Safeer DRM je v paketu, samo za branje, brez CDM; v runtime-u ni manjkajocih knjiznic (ldd v GNOME 50),
  2. Electron nalozi stran (NAVIGATION_OK) brez sesutja procesa strani (PROCESS_FAILED),
  3. procesi strani tecejo v podpeskovniku: seccomp-bpf (Seccomp: 2), NoNewPrivs in svoj imenski prostor mount
     (zypak jih zazene prek portala Flatpak z expose-pids, zato so vidni tu),
  4. Widevine: prvi zagon s svezim profilom - ECS sam namesti CDM z Googlovih streznikov v uporabnikovo mapo
     (DRM_READY, WidevineCdm/<verzija>); najkasneje drugi zagon stran dobi com.widevine.alpha (EME ok) - CDM se nalozi v
     peskovniku iz mape, ki jo zypak izpostavi (ZYPAK_EXPOSE_WIDEVINE_PATH). Na Linuxu brez Flatpaka je bil EME ok ze ob
     prvem zagonu (izmerjeno 18. 10. 2026); prvi krog se zato izpise, a ga ne zahtevamo.
Izpis je namenoma podroben (CI ne vidi vedno celega dnevnika): vsaka napaka je ena vrstica »FAIL: ...«.
"""
import json
import os
import re
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


def procesi(lastni_mnt: str) -> dict:
    """Kar o peskovniku Chromiuma vidimo iz peskovnika brskalnika:
    - "renderji": (pid, Seccomp, NoNewPrivs, svoj mnt) procesov strani, ce so vidni (zypak spawn + expose-pids),
    - "podpeskovniki": zagoni flatpak-spawn --sandbox za procese Chromiuma (zypak mimic: zygote in z njim procesi
      strani tecejo v podpeskovniku portala, brez omrezja),
    - "brez_peskovnika": procesi z --no-sandbox (ne sme jih biti)."""
    izid = {"renderji": [], "podpeskovniki": [], "brez_peskovnika": [], "vsi": []}
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                surovo = [a.decode("utf-8", "replace") for a in f.read().split(b"\0") if a]
            # Chromium procesom strani prepise naslov procesa (setproctitle): ves ukaz je en niz s presledki - CI
            # 15. 10. 2026: »/…/Safeer DRM --type=renderer …« kot en argument. Zato razclenimo po presledkih.
            ukaz = surovo if len(surovo) > 1 else (surovo[0].split() if surovo else [])
        except OSError:
            continue
        izid["vsi"].append((int(pid), " ".join(ukaz[:3])[-90:]))
        if "--no-sandbox" in ukaz:
            izid["brez_peskovnika"].append((int(pid), " ".join(ukaz)[:200]))
        vrsta = next((a[len("--type="):] for a in ukaz if a.startswith("--type=")), "")
        if ukaz and os.path.basename(ukaz[0]) in ("flatpak-spawn", "bwrap") and "--sandbox" in ukaz and vrsta:
            izid["podpeskovniki"].append((int(pid), vrsta, "--no-network" in ukaz))
        elif vrsta == "renderer":
            try:
                with open(f"/proc/{pid}/status", encoding="utf-8") as f:
                    polja = dict(v.split(":", 1) for v in f.read().splitlines() if ":" in v)
            except OSError:
                continue
            # /proc/PID/ns je za proces strani nedosegljiv (Chromium ga oznaci kot ne-dumpable; CI 15. 10. 2026) -
            # tudi to je znak peskovnika. Ce je berljiv, mora biti imenski prostor mount drug kot nas.
            try:
                svoj_mnt = os.readlink(f"/proc/{pid}/ns/mnt") != lastni_mnt
            except OSError:
                svoj_mnt = True
            izid["renderji"].append((int(pid), polja.get("Seccomp", "?").strip(), polja.get("NoNewPrivs", "?").strip(),
                                     svoj_mnt))
    return izid


def zazeni(exe, krog: int, cas: int) -> list:
    safeer_drm.mapa_sej().mkdir(parents=True, exist_ok=True)
    seja = tempfile.mkdtemp(prefix="drm-smoke-", dir=str(safeer_drm.mapa_sej()))
    stanje = os.path.join(seja, "events.jsonl")
    ukazi = os.path.join(seja, "command.txt")
    argumenti = [str(exe), "--parent=1", f"--url={URL}", f"--profile={os.path.join(seja, 'profil')}",
                 f"--state={stanje}", f"--command={ukazi}", f"--lastnik={os.getpid()}"]
    ukaz = safeer_drm.ukaz_zagona(argumenti)
    print(f"krog {krog}: ukaz", ukaz[:2], flush=True)
    if not ukaz or ukaz[0] != safeer_drm.ZYPAK:
        fail(f"Safeer DRM se ne zazene prek zypaka: {ukaz}")
        return [], {"renderji": [], "podpeskovniki": [], "brez_peskovnika": []}
    okolje = safeer_drm.okolje_zagona()
    print("ZYPAK_EXPOSE_WIDEVINE_PATH =", okolje.get("ZYPAK_EXPOSE_WIDEVINE_PATH"), flush=True)
    okolje["SAFEER_DRM_EME_PREIZKUS"] = "1"
    okolje["ZYPAK_DEBUG"] = "1"
    dnevnik = open(os.path.join(seja, "zypak.log"), "wb")
    proces = subprocess.Popen(ukaz, env=okolje, stdout=dnevnik, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
    lastni_mnt = os.readlink("/proc/self/ns/mnt")
    videni = None
    konec = time.monotonic() + cas
    while time.monotonic() < konec and proces.poll() is None:
        time.sleep(1)
        d = dogodki(stanje)
        vrste = {x.get("type") for x in d}
        if "NAVIGATION_OK" in vrste and videni is None:
            time.sleep(2)
            videni = procesi(lastni_mnt)
        # EME (preizkus strani) pride po DRM_READY/DRM_FAILED: main.js stran odpre sele, ko je Widevine pripravljen.
        if "NAVIGATION_OK" in vrste and videni is not None and "EME" in vrste:
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
    print(f"krog {krog}: procesi:", videni, flush=True)
    if True:     # dnevnik zypaka (ZYPAK_DEBUG=1) vedno: strategija zagona podprocesov in klici portala
        try:
            with open(os.path.join(seja, "zypak.log"), encoding="utf-8", errors="replace") as f:
                vrstice = [v.rstrip() for v in f if v.strip()]
        except OSError:
            vrstice = ["(ni dnevnika)"]
        # Ena vrstica na vrstico dnevnika s predpono »zypak:« - CI jih zdruzi v eno opombo (glej workflow).
        kljucne = [v for v in vrstice if any(k in v.lower() for k in ("strateg", "spawn", "sandbox", "expose", "reject",
                                                                        "error", "fail", "zygote"))]
        for v in (kljucne or vrstice)[-30:]:
            print("zypak: " + v[:300], flush=True)
    return d, videni or {"renderji": [], "podpeskovniki": [], "brez_peskovnika": []}


def main() -> int:
    print("v peskovniku:", gostitelj.v_peskovniku(), "sme na gostitelja:", gostitelj.sme_na_gostitelja(), flush=True)
    if not gostitelj.v_peskovniku():
        fail("ne tece v peskovniku Flatpaka brez dostopa do gostitelja")
    exe = safeer_drm.izvrsljiva()
    print("Safeer DRM v paketu:", exe, flush=True)
    if exe is None:
        fail("Safeer DRM ni v paketu")
        return 1
    if not str(exe).startswith(LIB + "/safeer-drm/"):
        fail(f"Safeer DRM ni iz paketa: {exe}")
    if os.access(exe.parent, os.W_OK):
        fail("mapa Safeer DRM v paketu ni samo za branje")
    if (exe.parent / "WidevineCdm").exists():
        fail("Widevine CDM je v paketu (ne sme biti: namesti ga ECS z Googlovih streznikov)")
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
    if r1["brez_peskovnika"]:
        fail(f"procesi brez peskovnika (--no-sandbox): {r1['brez_peskovnika']}")
    for pid, seccomp, nnp, svoj_mnt in r1["renderji"]:
        if seccomp != "2" or nnp != "1" or not svoj_mnt:
            fail(f"proces strani {pid} ni v podpeskovniku: Seccomp={seccomp} NoNewPrivs={nnp} svoj mnt={svoj_mnt}")
    # Brez expose-pids procesov strani ne vidimo; potem mora biti viden zagon zygote v podpeskovniku portala.
    zygote = [x for x in r1["podpeskovniki"] if x[1] == "zygote" and x[2]]
    if not r1["renderji"] and not zygote:
        fail(f"ni dokaza o podpeskovniku Chromiuma (ne procesov strani ne flatpak-spawn --sandbox zygote): {r1}")
    pripravljen = [x.get("detail", "") for x in d1 if x.get("type") in ("DRM_READY", "DRM_FAILED")]
    print("krog 1: Widevine:", pripravljen, "EME:", [x.get("detail", "") for x in d1 if x.get("type") == "EME"], flush=True)
    if not pripravljen or not pripravljen[-1].startswith("widevine "):
        fail(f"ECS ni namestil Widevine CDM z Googlovih streznikov: {pripravljen}")
    wv = safeer_drm.mapa_widevine()
    vsebina = sorted(os.listdir(wv)) if wv.is_dir() else []
    print("uporabnikova mapa WidevineCdm:", vsebina, flush=True)
    if not any(re.fullmatch(r"\d+(\.\d+){3}", x) for x in vsebina):
        fail(f"v uporabnikovi mapi WidevineCdm ni CDM: {vsebina}")
    d2, _r2 = zazeni(exe, 2, 90)
    eme = [x.get("detail", "") for x in d2 if x.get("type") == "EME"]
    print("EME (com.widevine.alpha) v drugem zagonu:", eme, flush=True)
    if eme[-1:] != ["ok"]:
        fail("Widevine v peskovniku ne dela: " + (eme[-1] if eme else "ni odgovora strani"))
    print("PASS" if not napake else "FAIL (%d)" % len(napake), flush=True)
    return 0 if not napake else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as napaka:  # noqa: BLE001 - v CI mora biti vzrok v eni vrstici (opomba posla)
        import traceback
        traceback.print_exc()
        sled = traceback.extract_tb(napaka.__traceback__)[-1]
        print(f"FAIL: izjema {type(napaka).__name__}: {napaka} (vrstica {sled.lineno})", flush=True)
        sys.exit(1)
