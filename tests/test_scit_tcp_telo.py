"""Scit TCP: odjemalec, ki poslje samo dolzino poizvedbe, mesta ne drzi dlje od kratkega roka (CodeRabbit, 5. 11. 2026).

Prej je imelo telo rok 10 s: 32 krajevnih odjemalcev z dolzino in brez telesa je zasedlo vse reze TCP Scita."""
import os
import socket
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core import os_scit  # noqa: E402


class TeloTcpTest(unittest.TestCase):
    def test_dolzina_brez_telesa_sprosti_mesto(self):
        self.assertLessEqual(os_scit.Razresevalnik.ROK_TELESA_TCP_S, os_scit.Razresevalnik.ROK_GLAVE_TCP_S)
        r = os_scit.Razresevalnik(lambda ime: None, lambda: [])
        t = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        t.bind(("127.0.0.1", 0))
        t.listen(4)
        r._tcp, r._tece = t, True
        zanka = threading.Thread(target=r._zanka_tcp, daemon=True)
        zanka.start()
        k = socket.create_connection(t.getsockname()[:2], timeout=15)
        try:
            zacetek = time.monotonic()
            k.sendall(b"\x00\x20")   # dolzina 32 bajtov, telesa ni
            self.assertEqual(k.recv(16), b"")   # Scit zapre povezavo
            trajalo = time.monotonic() - zacetek
            self.assertLess(trajalo, os_scit.Razresevalnik.ROK_TELESA_TCP_S + 1.5)
            # Reza je spet prosta: vseh NAJVEC_TCP mest je mogoce zasesti.
            konec = time.monotonic() + 1
            while True:
                zasedena = []
                for _ in range(r.NAJVEC_TCP):
                    if r._proste_tcp.acquire(blocking=False):
                        zasedena.append(1)
                for _ in zasedena:
                    r._proste_tcp.release()
                if len(zasedena) == r.NAJVEC_TCP or time.monotonic() > konec:
                    break
                time.sleep(0.05)
            self.assertEqual(len(zasedena), r.NAJVEC_TCP)
        finally:
            k.close()
            r._tece = False
            r._tcp = None
            t.close()
            zanka.join(3)


if __name__ == "__main__":
    unittest.main()
