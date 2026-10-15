"""Majhen lokalni streznik IMAP za preizkuse (brez interneta): LOGIN, SELECT/EXAMINE, UID SEARCH/FETCH/STORE,
IDLE z obvestili EXISTS/FETCH, CONDSTORE (MODSEQ, CHANGEDSINCE, HIGHESTMODSEQ), UIDVALIDITY in prekinitev povezav.

Samo za preizkuse: brez TLS, en nabiralnik INBOX, vsebina pisem je umetna.
"""

from __future__ import annotations

import re
import socket
import socketserver
import threading


class Nabiralnik:
    def __init__(self, idle=True, condstore=True):
        self.zaklep = threading.RLock()
        self.uidvalidity = 1001
        self.pisma = []          # [{"uid", "zastavice": set, "surovo": bytes, "modseq"}]
        self.naslednji_uid = 1
        self.modseq = 1
        self.idle = idle
        self.condstore = condstore
        self.odjemalci = set()   # odprte seje
        self.ukazi = []          # zapisnik ukazov (brez gesel)

    def zmoznosti(self) -> str:
        z = ["IMAP4rev1", "AUTH=PLAIN", "UIDPLUS"]
        if self.idle:
            z.append("IDLE")
        if self.condstore:
            z.append("CONDSTORE")
        return " ".join(z)

    def dodaj(self, surovo: bytes, prebrano: bool = False) -> int:
        with self.zaklep:
            uid = self.naslednji_uid
            self.naslednji_uid += 1
            self.modseq += 1
            self.pisma.append({"uid": uid, "zastavice": {"\\Seen"} if prebrano else set(), "surovo": surovo,
                               "modseq": self.modseq})
            n = len(self.pisma)
            for o in list(self.odjemalci):
                o.obvesti(b"* %d EXISTS" % n)
            return uid

    def nastavi_prebrano(self, uid: int, prebrano: bool) -> None:
        with self.zaklep:
            for i, p in enumerate(self.pisma):
                if p["uid"] == uid:
                    if prebrano:
                        p["zastavice"].add("\\Seen")
                    else:
                        p["zastavice"].discard("\\Seen")
                    self.modseq += 1
                    p["modseq"] = self.modseq
                    for o in list(self.odjemalci):
                        o.obvesti(b"* %d FETCH (UID %d FLAGS (%s))" % (i + 1, uid, " ".join(sorted(p["zastavice"])).encode()))

    def ponastavi_uidvalidity(self) -> None:
        """Streznik mapo na novo ostevilci (npr. obnova iz varnostne kopije): novi UID-ji od 1 naprej."""
        with self.zaklep:
            self.uidvalidity += 1
            for i, p in enumerate(self.pisma):
                p["uid"] = i + 1
            self.naslednji_uid = len(self.pisma) + 1
        self.prekini_vse()

    def prekini_vse(self) -> None:
        """Izguba omrezja: vse povezave se nenadoma zaprejo."""
        with self.zaklep:
            odjemalci = list(self.odjemalci)
        for o in odjemalci:
            o.prekini()


def _mnozica(niz: str, najvisji: int):
    izid = set()
    for del_ in niz.split(","):
        if ":" in del_:
            a, b = del_.split(":")
            a = najvisji if a == "*" else int(a)
            b = najvisji if b == "*" else int(b)
            izid.update(range(min(a, b), max(a, b) + 1))
        else:
            izid.add(najvisji if del_ == "*" else int(del_))
    return izid


class _Seja(socketserver.StreamRequestHandler):
    def setup(self):
        super().setup()
        self.nab: Nabiralnik = self.server.nabiralnik
        self.v_idle = False
        self.izbrano = False
        self.pisalni = threading.Lock()

    def obvesti(self, vrstica: bytes) -> None:
        if self.izbrano:
            try:
                self._pisi(vrstica)
            except OSError:
                pass

    def prekini(self) -> None:
        try:
            self.request.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

    def _pisi(self, podatki: bytes) -> None:
        with self.pisalni:
            self.wfile.write(podatki + b"\r\n")
            self.wfile.flush()

    def handle(self):
        with self.nab.zaklep:
            self.nab.odjemalci.add(self)
        try:
            self._pisi(b"* OK [CAPABILITY " + self.nab.zmoznosti().encode() + b"] lazni streznik")
            while True:
                vrstica = self.rfile.readline()
                if not vrstica:
                    return
                vrstica = vrstica.rstrip(b"\r\n").decode("utf-8", "replace")
                if not vrstica:
                    continue
                oznaka, _, ostalo = vrstica.partition(" ")
                ukaz, _, arg = ostalo.partition(" ")
                ukaz = ukaz.upper()
                with self.nab.zaklep:
                    self.nab.ukazi.append(ukaz if ukaz in ("LOGIN", "AUTHENTICATE") else (ukaz + " " + arg).strip())
                if not self._ukaz(oznaka, ukaz, arg):
                    return
        except (OSError, ValueError):
            return
        finally:
            with self.nab.zaklep:
                self.nab.odjemalci.discard(self)

    def _ukaz(self, oznaka, ukaz, arg) -> bool:
        n = self.nab
        ok = lambda besedilo="OK": self._pisi(oznaka.encode() + b" OK " + besedilo.encode())  # noqa: E731
        if ukaz == "CAPABILITY":
            self._pisi(b"* CAPABILITY " + n.zmoznosti().encode()); ok()
        elif ukaz == "LOGIN":
            ok("LOGIN completed")
        elif ukaz == "AUTHENTICATE":
            self._pisi(b"+ ")
            self.rfile.readline()
            ok()
        elif ukaz in ("SELECT", "EXAMINE"):
            with n.zaklep:
                self._pisi(b"* %d EXISTS" % len(n.pisma))
                self._pisi(b"* OK [UIDVALIDITY %d] UIDs valid" % n.uidvalidity)
                self._pisi(b"* OK [UIDNEXT %d] next" % n.naslednji_uid)
                if n.condstore:
                    self._pisi(b"* OK [HIGHESTMODSEQ %d] modseq" % n.modseq)
            self.izbrano = True
            ok("[READ-%s] done" % ("ONLY" if ukaz == "EXAMINE" else "WRITE"))
        elif ukaz == "STATUS":
            with n.zaklep:
                neprebranih = sum(1 for p in n.pisma if "\\Seen" not in p["zastavice"])
            self._pisi(b'* STATUS "INBOX" (UNSEEN %d)' % neprebranih); ok()
        elif ukaz == "NOOP":
            ok()
        elif ukaz == "IDLE":
            if not n.idle:
                self._pisi(oznaka.encode() + b" BAD no idle"); return True
            self._pisi(b"+ idling")
            while True:
                v = self.rfile.readline()
                if not v:
                    return False
                if v.strip().upper() == b"DONE":
                    break
            ok("IDLE terminated")
        elif ukaz == "LOGOUT":
            self._pisi(b"* BYE"); ok(); return False
        elif ukaz == "UID":
            pod, _, arg2 = arg.partition(" ")
            pod = pod.upper()
            if pod == "SEARCH":
                with n.zaklep:
                    vsi = [p["uid"] for p in n.pisma]
                    najvisji = max(vsi) if vsi else 0
                m = re.match(r"UID (\S+)", arg2)
                uidi = sorted(u for u in vsi if not m or u in _mnozica(m.group(1), najvisji))
                self._pisi(b"* SEARCH" + b"".join(b" %d" % u for u in uidi)); ok()
            elif pod == "FETCH":
                self._fetch(arg2); ok()
            elif pod == "STORE":
                m = re.match(r"(\S+) ([+-])FLAGS(?:\.SILENT)? \((.*)\)", arg2)
                if m:
                    with n.zaklep:
                        najvisji = max([p["uid"] for p in n.pisma] or [0])
                        mn = _mnozica(m.group(1), najvisji)
                        for p in n.pisma:
                            if p["uid"] in mn:
                                for z in m.group(3).split():
                                    (p["zastavice"].add if m.group(2) == "+" else p["zastavice"].discard)(z)
                                n.modseq += 1
                                p["modseq"] = n.modseq
                ok()
            else:
                ok()
        else:
            ok()
        return True

    def _fetch(self, arg: str) -> None:
        n = self.nab
        mnoz, _, ostalo = arg.partition(" ")
        changedsince = re.search(r"\(CHANGEDSINCE (\d+)\)", ostalo)
        deli = ostalo.upper()
        m_body = re.search(r"BODY\.PEEK\[\]<0\.(\d+)>", deli)
        with n.zaklep:
            najvisji = max([p["uid"] for p in n.pisma] or [0])
            izbrani = _mnozica(mnoz, najvisji)
            pisma = [(i + 1, dict(p, zastavice=set(p["zastavice"]))) for i, p in enumerate(n.pisma) if p["uid"] in izbrani]
        for zap, p in pisma:
            if changedsince and p["modseq"] <= int(changedsince.group(1)):
                continue
            glava = b"* %d FETCH (UID %d FLAGS (%s)" % (zap, p["uid"], " ".join(sorted(p["zastavice"])).encode())
            if "MODSEQ" in deli or changedsince:
                glava += b" MODSEQ (%d)" % p["modseq"]
            if "RFC822.SIZE" in deli:
                glava += b" RFC822.SIZE %d" % len(p["surovo"])
            if m_body:
                vsebina = p["surovo"][:int(m_body.group(1))]
                with self.pisalni:
                    self.wfile.write(glava + b" BODY[]<0> {%d}\r\n" % len(vsebina) + vsebina + b")\r\n")
                    self.wfile.flush()
            else:
                self._pisi(glava + b")")


class LazniImap(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, idle=True, condstore=True):
        self.nabiralnik = Nabiralnik(idle=idle, condstore=condstore)
        super().__init__(("127.0.0.1", 0), _Seja)
        self.vrata = self.server_address[1]
        self._nit = threading.Thread(target=self.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        self._nit.start()

    def ustavi(self):
        self.nabiralnik.prekini_vse()
        self.shutdown()
        self.server_close()


def pismo(od="Ana <ana@example.test>", komu="jaz@example.test", zadeva="Pozdrav", mid="m1", telo="Zivjo") -> bytes:
    return ("From: %s\r\nTo: %s\r\nSubject: %s\r\nDate: Thu, 15 Oct 2026 10:00:00 +0000\r\nMessage-ID: <%s@example.test>\r\n"
            "Content-Type: text/plain; charset=utf-8\r\n\r\n%s\r\n" % (od, komu, zadeva, mid, telo)).encode("utf-8")
