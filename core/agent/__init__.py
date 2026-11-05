"""Safeer Agent: ukaz z glasom ali besedilom -> naloge -> dejanja na napravah prek Safeer Linka.

Nacela lastnika (13. 10. 2026):
* upravljanje mora biti enostavno in prirocno, delo s storitvijo v veselje;
* vec nalog v enem narocilu = agent naredi vse; uporabnik nastavi trajanje od 1 minute do neomejeno;
* agent ne hrani vsega, kar obdela - samo rezultate in okoliscine, ki jih potrebuje (kratki izidi, ne surovi podatki);
* upravljanje zaslona s klikanjem samo na izrecno narocilo.
Jezikovni model tece lokalno (testni telefon OnePlus, llama-server) - nic ne gre na internet.
"""

#: Lastnik, 5. 11. 2026: Safeer Agent za to izdajo ni pripravljen in je izlocen iz uradne izdaje na vseh napravah. Ena
#: zastavica za ves Linux: z False ga uporabnik ne vidi nikjer (iskalna lupa, Nastavitve, zmoznost v Safeer Linku, ukaz
#: agent.ask z druge naprave). Koda ostane; True vrne vse kot prej (tests/test_agent_izdaja.py).
NA_VOLJO_V_IZDAJI = False


def v_izdaji() -> bool:
    return bool(NA_VOLJO_V_IZDAJI)
