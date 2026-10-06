# Safeer Browser for Linux 1.0.103 · Safeer Control 2.1.59 · Safeer OS 0.4.61

## Safeer Link: a tap on the separate screen hits the button in full-screen games too (Safeer Control 2.1.59)

A program of this computer opened from a phone, tablet or TV runs on a separate, virtual screen. A touch on the phone or tablet puts the pointer of that screen on the touched point and clicks. In a full-screen game that hides the pointer this did not work: the tap moved the game's pointer somewhere else and the button did not react.

- **Cause (measured).** A game that runs full screen through XWayland and hides the pointer (here Extreme Tux Racer 0.8.4, built on SFML) asks for the pointer to be locked. The compositor of the separate screen (sway 1.9) granted the lock, and from then on an absolute move of the virtual pointer was not carried out: the game received only a relative move (target minus the locked position). `xinput test-xi2` on the separate screen showed RawMotion −878/−275 for a tap at (356, 300), and the pointer the game sees stayed in the corner.
- **Fix.** Programs on the separate screen can no longer lock the pointer (`seat seat0 pointer_constraint disable`), and the virtual mouse and keyboard are kept on the seat explicitly (`seat seat0 fallback true` – without it, any later seat command detached them and input stopped). Relative moves (TV remote, gamepad) reach the program as before. The real screen and the real pointer of the computer are not involved.

Measured live (this code in Safeer Control on a computer with Linux Mint and sway 1.9; a phone with Safeer OS for Android; separate screen 1236 × 576): after a fresh start of the separate screen, through Global Link, a tap on "Enter" opened the game's main menu (pointer at (617, 375) for a tap at (616, 375)) and a tap on "Help" opened the help screen (pointer at (617, 422)). Before the fix the same taps left the pointer at the edge of the screen and the menu did not react.

Verified: 912 automated tests of Safeer Link passed locally; the whole suite runs in CI. New test in `tests/test_link_sway.py`: the configuration of the separate screen contains both seat settings, in this order.

Not tested live: games that steer the view with a locked mouse, driven from a TV remote or a gamepad – relative moves are still delivered, but a game that re-centres the pointer by itself may behave differently without the lock; a TV and a tablet as the viewing device.

## Safeer OS 0.4.61 · Safeer Browser 1.0.103

- Released together with Safeer Control 2.1.59. No changes in Safeer OS and in browsing.

Slovensko: **Dotik na ločenem zaslonu zadene gumb tudi v igri čez cel zaslon.** Program tega računalnika, odprt s telefona, tablice ali televizorja, teče na ločenem, navideznem zaslonu; dotik na telefonu postavi kazalec tega zaslona na dotaknjeno mesto in klikne. V igri čez cel zaslon, ki kazalec skrije (izmerjeno: Extreme Tux Racer), to ni delovalo – igra si je kazalec zaklenila, zato je do nje prišel le relativni premik in dotik je zgrešil gumb. Zdaj si program na ločenem zaslonu kazalca ne more več zakleniti, navidezni miška in tipkovnica pa ostaneta izrecno pripeti. Izmerjeno prek Global Linka po svežem zagonu ločenega zaslona: dotik na »Enter« je odprl glavni meni igre, dotik na »Help« stran s pomočjo. Pravi zaslon in kazalec računalnika pri tem nista udeležena. Ni preizkušeno v živo: igre s pogledom, ki ga vodi zaklenjena miška (z daljincem ali ploščkom), televizor in tablica kot naprava, ki gleda.
