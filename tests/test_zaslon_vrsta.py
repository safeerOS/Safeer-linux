import io
import queue
import threading
from types import SimpleNamespace
from unittest import mock

import pytest

from core import link_zaslon as z


def slika(n, kljuc=False, hevc=False):
    aud = b'\x00\x00\x00\x01' + (b'\x46\x01\x50' if hevc else b'\x09\xf0')
    nal = b'\x00\x00\x01' + (b'\x26\x01' if kljuc else b'\x02\x01') if hevc else b'\x00\x00\x01' + (b'\x65' if kljuc else b'\x41')
    return aud + nal + bytes([128 + n])


@pytest.mark.parametrize('hevc', [False, True])
def test_meje_slik_cez_vsak_bajt(hevc):
    slike = [slika(0, True, hevc), slika(1, False, hevc), slika(2, True, hevc)]
    prebrano = [0, False]
    dobljeno = list(z._slike(io.BytesIO(b''.join(slike)), 1, 'hevc' if hevc else 'h264', prebrano))
    assert dobljeno == list(zip(slike, [True, False, True]))
    assert prebrano == [sum(map(len, slike)), True]


@pytest.mark.parametrize('fps', [30, 60])
def test_vrsta_izpusti_odvisne_in_obdrzi_najnovejsi_kljuc(fps):
    opis = {}
    vrsta = z._VrstaSlik(fps, opis)
    for n in range(100):
        vrsta.dodaj(bytes([n]), n % 10 == 0)
        assert len(vrsta.slike) <= vrsta.meja
    vrsta.dodaj(b'nov', True)
    vrsta.zapri()
    assert vrsta.vzemi() == b'nov'
    assert vrsta.vzemi() is None
    assert opis['izpuscene_slike'] == 100
    assert opis['najvec_vrsta_slik'] == vrsta.meja + 1


def test_pocasen_posiljatelj_ne_ustavi_branja_zajema():
    kosi = queue.Queue()
    blokiran, sprosti, prebrano_vse = threading.Event(), threading.Event(), threading.Event()
    poslano = []

    def beri(_):
        kos = kosi.get(timeout=3)
        if not kos:
            prebrano_vse.set()
        return kos

    def poslji(okvir):
        if not poslano:
            blokiran.set()
            assert sprosti.wait(3)
        poslano.append(okvir[5:])

    merilo = z.link_zaslon_meritve.Meritve()
    nit = threading.Thread(target=z.Zaslon(vklopljeno=True)._crpaj,
                           args=(SimpleNamespace(stdout=SimpleNamespace(read=beri)), z.OKVIR_SLIKA,
                                 SimpleNamespace(sendall=poslji), 32768),
                           kwargs=dict(kodek='h264', fps=60, merilo=merilo))
    aud = slika(1)[:6]
    kosi.put(slika(0, True) + aud)
    nit.start()
    try:
        assert blokiran.wait(3)
        kosi.put(slika(1)[6:] + b''.join(slika(n, n == 10) for n in range(2, 13)))
        kosi.put(b'')
        assert prebrano_vse.wait(3)
    finally:
        sprosti.set()
        nit.join(3)
    assert not nit.is_alive()
    assert poslano == [slika(0, True), slika(10, True), slika(11), slika(12)]
    assert merilo.opis['izpuscene_slike'] == 9


def test_seja_ne_nastavi_medpomnilnika():
    seja = z.Zaslon(vklopljeno=True)
    odjemalec = mock.Mock()
    with mock.patch.object(seja, '_sprejmi', return_value=(odjemalec, None)):
        seja._streci(mock.Mock(), None, [], -1)
    odjemalec.setsockopt.assert_not_called()


@pytest.mark.parametrize('kodek', ['h264', 'hevc'])
def test_kodirnik_doda_meje_za_varno_izpuscanje(kodek):
    ukaz = z.ukaz_ffmpeg(':0', 1280, 720, 1280, 720, 60, '8M', '/dev/dri/renderD128', kodek=kodek)
    assert ukaz[ukaz.index('-bsf:v') + 1] == kodek + '_metadata=aud=insert'


def test_stevca_v_obstojeci_vrstici_meritev(capsys):
    merilo = z.link_zaslon_meritve.Meritve()
    merilo.opis.update(izpuscene_slike=17, najvec_vrsta_slik=7)
    konec = mock.Mock()
    konec.wait.side_effect = [False, True]
    with mock.patch.object(z, 'MERITVE_DNEVNIK_S', 0), mock.patch.object(z.link_vticnik, 'tcp_info', return_value={}):
        z.Zaslon(vklopljeno=True)._meri(None, merilo, konec)
    vrstica = capsys.readouterr().out
    assert '[zaslon] meritve:' in vrstica
    assert 'izpuscene_slike=17 najvec_vrsta_slik=7' in vrstica


def test_jedro_zavrze_tudi_stari_kljuc_in_pocaka_novega():
    neposlano = [0]
    opis = {}
    vrsta = z._VrstaSlik(60, opis, lambda: neposlano[0])
    vrsta.dodaj(b'stari kljuc', True)
    neposlano[0] = 300_000
    vrsta.dodaj(b'odvisna', False)
    vrsta.dodaj(b'kljuc med zastojem', True)
    assert not vrsta.slike
    neposlano[0] = 0
    vrsta.dodaj(b'odvisna po zastoju', False)
    vrsta.dodaj(b'nov kljuc', True)
    vrsta.zapri()
    assert vrsta.vzemi() == b'nov kljuc'
    assert vrsta.vzemi() is None
    assert opis['izpuscene_slike'] == 4
    assert opis['najvec_neposlanih_bajtov'] == 300_000


def test_zastoj_pred_posiljanjem_ne_spusti_ze_zbranega_kljuca():
    neposlano = [0]
    vrsta = z._VrstaSlik(60, {}, lambda: neposlano[0])
    vrsta.dodaj(b'stari kljuc', True)
    neposlano[0] = 300_000
    vrsta.zapri()
    assert vrsta.vzemi() is None
    assert vrsta.opis['izpuscene_slike'] == 1


def test_meja_sledi_dvosekundnemu_povprecju_in_ima_spodnjo_mejo():
    with mock.patch.object(z.time, 'monotonic', return_value=0) as ura:
        vrsta = z._VrstaSlik(60, {})
        assert vrsta.meja_bajtov() == 256 * 1024
        ura.return_value = 1
        vrsta.poslano(10_000_000)
        assert vrsta.meja_bajtov() == 1_000_000
        ura.return_value = 2
        vrsta.poslano(10_000_000)
        assert vrsta.meja_bajtov() == 1_000_000
        ura.return_value = 3.1
        assert vrsta.meja_bajtov() == 500_000
        ura.return_value = 4.1
        assert vrsta.meja_bajtov() == 256 * 1024


def test_tiocoutq_prebere_pravo_vrsto_jedra():
    if not z.sys.platform.startswith('linux'):
        pytest.skip('TIOCOUTQ samo na Linuxu')
    prvi, drugi = z.socket.socketpair()
    try:
        assert z._neposlani_bajti(prvi) == 0
        prvi.sendall(bytes(1000))
        assert z._neposlani_bajti(prvi) >= 1000
        assert len(drugi.recv(1000)) == 1000
        assert z._neposlani_bajti(prvi) == 0
    finally:
        prvi.close()
        drugi.close()


@pytest.mark.parametrize('napaka', [OSError, ValueError, TypeError, AttributeError])
def test_nedostopen_ioctl_je_neusodna_meritev(napaka):
    import fcntl
    with mock.patch.object(fcntl, 'ioctl', side_effect=napaka):
        assert z._neposlani_bajti(SimpleNamespace(fileno=lambda: 7)) == 0


def test_tiocoutq_se_ne_uporabi_izven_linuxa():
    import fcntl
    with mock.patch.object(z.sys, 'platform', 'darwin'), mock.patch.object(fcntl, 'ioctl') as klic:
        assert z._neposlani_bajti(None) == 0
        klic.assert_not_called()


def test_meritve_izpisejo_najvec_neposlanih_bajtov(capsys):
    merilo = z.link_zaslon_meritve.Meritve()
    merilo.opis['najvec_neposlanih_bajtov'] = 400_000
    konec = mock.Mock()
    konec.wait.side_effect = [False, True]
    with mock.patch.object(z, 'MERITVE_DNEVNIK_S', 0), mock.patch.object(z.link_vticnik, 'tcp_info', return_value={}):
        z.Zaslon(vklopljeno=True)._meri(None, merilo, konec)
    assert 'najvec_neposlanih_bajtov=400000' in capsys.readouterr().out


def test_crpalka_uporabi_jedrno_vrsto_tudi_brez_merila():
    izhod = io.BytesIO(slika(0, True) + slika(1))
    poslano = []
    with mock.patch.object(z, '_neposlani_bajti', return_value=300_000, create=True) as meritev:
        z.Zaslon(vklopljeno=True)._crpaj(SimpleNamespace(stdout=izhod), z.OKVIR_SLIKA,
                                      SimpleNamespace(sendall=poslano.append), 32768, kodek='h264')
    assert not poslano
    assert meritev.call_count >= 2


def test_trajen_zastoj_ohrani_obstojeci_rok_pisanja():
    with mock.patch.object(z.time, 'monotonic', return_value=0) as ura:
        vrsta = z._VrstaSlik(60, {}, lambda: 300_000)
        vrsta.dodaj(b'odvisna', False)
        ura.return_value = z.ROK_PISANJA_S + 0.01
        with pytest.raises(TimeoutError):
            vrsta.dodaj(b'kljuc', True)


def test_obstal_pisalec_javi_enkrat_po_roku():
    # 25. 11. 2026 17:43: pisalec slike je obstal (jedro brez neposlanih bajtov, poslano stoji), vrsta je 2 min
    # zavrgla vse slike, seja pa se ni koncala - slika in miska na TV sta zamrznili. Vrsta mora obstanek javiti.
    javljeno = []
    with mock.patch.object(z.time, 'monotonic', return_value=100.0) as ura:
        vrsta = z._VrstaSlik(60, {}, ob_obstanku=lambda: javljeno.append(1))
        vrsta.dodaj(b'kljuc', True)
        assert vrsta.vzemi() == b'kljuc'
        for i in range(20):
            ura.return_value = 100.0 + 0.1 * i
            vrsta.dodaj(b'x', i % 10 == 0)
        assert javljeno == [], 'pred rokom ni obstanka'
        ura.return_value = 100.0 + z.OBSTANEK_PISALCA_S + 0.5
        vrsta.dodaj(b'y', True)
        vrsta.dodaj(b'z', True)
        assert javljeno == [1], 'en klic po roku'


def test_pisalec_ki_jemlje_ni_obstal():
    javljeno = []
    with mock.patch.object(z.time, 'monotonic', return_value=0.0) as ura:
        vrsta = z._VrstaSlik(60, {}, ob_obstanku=lambda: javljeno.append(1))
        for i in range(200):
            ura.return_value = 0.1 * i
            vrsta.dodaj(b'k', True)
            assert vrsta.vzemi() == b'k'
        assert javljeno == []


def test_obstanek_tudi_ko_vrsta_caka_kljuc():
    # 25. 11. 2026 19:07: zastoj ob nalaganju plakatov - vrsta je bila prazna (cakala na kljuc ali zastoj jedra) in je
    # zavrgla vsako sliko; prvi nadzor (samo polna vrsta) se ni sprozil. Javi ga tudi zavracanje brez jemanja.
    javljeno = []
    neposlano = [0]
    opis = {}
    with mock.patch.object(z.time, 'monotonic', return_value=50.0) as ura:
        vrsta = z._VrstaSlik(60, opis, lambda: neposlano[0], ob_obstanku=lambda: javljeno.append(1))
        vrsta.dodaj(b'k', True)
        assert vrsta.vzemi() == b'k'
        neposlano[0] = 300_000
        vrsta.dodaj(b'kljuc med zastojem', True)
        neposlano[0] = 0
        for i in range(10):
            ura.return_value = 50.0 + i
            vrsta.dodaj(b'odvisna', False)
        assert javljeno == [1]
        assert opis['izpust_zastoj'] == 1 and opis['izpust_kljuc'] == 10
