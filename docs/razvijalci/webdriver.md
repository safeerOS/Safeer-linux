# WebDriver za Safeer Browser / WebDriver for Safeer Browser

Ta dokument opisuje uporabo W3C WebDriverja za avtomatizirano testiranje spletnih strani in aplikacij v Safeer Browserju.
This document describes how to use W3C WebDriver for automated web testing and browser automation in Safeer Browser.

---

## 🇸🇮 Slovensko: Avtomatizacija in testiranje s Safeer Browserjem

### Pregled

Safeer Browser uporablja spletni pogon WebKitGTK 6.0 z vgrajeno podporo za standard W3C WebDriver prek programa `WebKitWebDriver` (podobno kot `safaridriver` pri brskalniku Apple Safari). To razvijalcem omogoča izvajanje avtomatiziranih testov s standardnimi orodji, kot so Selenium, Playwright ali WebDriverIO.

### Namestitev in lokacija programa

Program `WebKitWebDriver` je del paketa `safeer-webkit`:
- **Povezava/program:** `/usr/lib/safeer-webkit/bin/WebKitWebDriver`

Zaženete ga v terminalu z izrecno določenim lokalnim gostiteljem:
```bash
/usr/lib/safeer-webkit/bin/WebKitWebDriver --host=127.0.0.1 --port=4444
```

> [!WARNING]
> **Varnost omrežja:** Vedno uporabite `--host=127.0.0.1`. Nikoli ne uporabljajte `--host=all` ali `0.0.0.0`, saj to omogoči upravljanje brskalnika vsem napravam v lokalnem omrežju.

### Varnostna zastavica `--automation` in izolacija podatkov (K1)

Zaradi varnosti in zasebnosti uporabnika je avtomatizacija v Safeer Browserju privzeto strogo **izklopljena**. Brskalnik dovoli nadzor prek WebDriverja (`WebContext.set_automation_allowed(True)`) **izključno takrat**, ko je zagnan z zastavico:

```bash
safeer-browser --automation
```

Ko je zastavica `--automation` podana:
1. **Popolna ločitev in efemerna seja (`WebKit.NetworkSession.new_ephemeral()`):** Brskalnik uporabi čisto efemerno omrežno sejo. Piškotki, shramba spletnih mest in prijavljene seje (vključno z bančnimi in osebnimi računi uporabnika) niso dostopni in se ne berejo iz uporabnikovega profila.
2. **Začasna mapa nastavitev (`mktemp -d`):** Brskalnik ustvari izolirano začasno mapo nastavitev, ki se ob zaprtju brskalnika samodejno izbriše. Nič se ne zapisuje v uporabnikovo mapo `~/.config/safeer-mint`.
3. **Brez zgodovine, zaznamkov in gesel:** Zgodovina brskanja se v načinu avtomatizacije ne beleži, zaznamki in gesla uporabnika pa niso naloženi.
4. **Izoliran proces (`NON_UNIQUE`):** Brskalnik teče v svojem procesu, ne obnavlja prejšnjih zavihkov in ne prikazuje vrstice za privzeti brskalnik.

### Vidna oznaka avtomatizacije (V1)

Uporabnik vedno jasno vidi, da je brskalnik pod nadzorom avtomatizacije:
- **Trajna pasica:** Na vrhu brskalnika se prikaže trajna pasica »To okno upravlja program za samodejno preizkušanje (WebDriver)« (na voljo v vseh 6 podprtih jezikih).
- **Barva naslovne vrstice:** Naslovna vrstica prevzame opozorilno barvo iz oblikovnega sistema `assets/os/tokens.css` (`--opozorilo`, podobno kot oranžna vrstica v Safariju oziroma črtasta v Epiphanyju).

### Nastavitev Selenium (Python)

V Seleniumu uporabite zmogljivosti (capabilities) `webkitgtk:browserOptions`, kjer določite pot do brskalnika (`binary`) in obvezni argument `["--automation"]`:

```python
from selenium import webdriver
from selenium.webdriver.common.by import By

# Nastavitev možnosti za Safeer Browser prek WebKitGTK
moznosti = webdriver.WebKitGTKOptions()
moznosti.binary_location = "/usr/bin/safeer-browser"
moznosti.add_argument("--automation")

# Povezava na tekoči WebKitWebDriver strežnik (vedno 127.0.0.1)
driver = webdriver.Remote(
    command_executor="http://127.0.0.1:4444",
    options=moznosti
)

try:
    driver.get("https://safeer.si")
    print("Naslov strani:", driver.title)
    assert "Safeer" in driver.title
finally:
    driver.quit()
```

### Neposredna W3C WebDriver zahteva (cURL)

Novo sejo lahko ustvarite tudi z neposredno HTTP zahtevo po specifikaciji W3C:

```bash
curl -X POST http://127.0.0.1:4444/session -H "Content-Type: application/json" -d '{
  "capabilities": {
    "alwaysMatch": {
      "webkitgtk:browserOptions": {
        "binary": "/usr/bin/safeer-browser",
        "args": ["--automation"]
      }
    }
  }
}'
```

---

## 🇬🇧 English: Automation and Testing with Safeer Browser

### Overview

Safeer Browser is powered by WebKitGTK 6.0 with native support for the W3C WebDriver standard via `WebKitWebDriver` (identical to how `safaridriver` operates for Apple Safari). This allows developers to run automated end-to-end tests using industry-standard frameworks such as Selenium, Playwright, or WebDriverIO.

### Binary Location & Packaging

The `WebKitWebDriver` driver is included in the `safeer-webkit` package:
- **Binary path:** `/usr/lib/safeer-webkit/bin/WebKitWebDriver`

Start the standalone driver explicitly binding to localhost:
```bash
/usr/lib/safeer-webkit/bin/WebKitWebDriver --host=127.0.0.1 --port=4444
```

> [!WARNING]
> **Network Security:** Always bind to `--host=127.0.0.1`. Never use `--host=all` or `0.0.0.0` as this exposes browser control to unauthorized devices on the local network.

### The `--automation` Security Flag and Data Isolation (K1)

To protect user security and data privacy, remote automation is **disabled by default**. Safeer Browser will only enable automation support (`WebContext.set_automation_allowed(True)`) when explicitly launched with the command-line flag:

```bash
safeer-browser --automation
```

When started with `--automation`:
1. **Ephemeral Session (`WebKit.NetworkSession.new_ephemeral()`):** An ephemeral, in-memory network session is used. Personal cookies, site storage, and active sessions (such as banking or social media logins) are never loaded and cannot be accessed.
2. **Temporary Profile Directory (`mktemp -d`):** A disposable configuration directory is used and deleted on exit. No state or settings are saved to the user's personal configuration directory (`~/.config/safeer-mint`).
3. **No History, Bookmarks, or Saved Credentials:** Browsing history is not recorded in automation mode, and user bookmarks or saved passwords are not accessible.
4. **Isolated Process (`NON_UNIQUE`):** The browser runs in an independent process without restoring previous tabs and suppresses default browser prompt bars.

### Visible Automation Indicators (V1)

The user is always informed when automation controls the browser:
- **Persistent Banner:** A prominent banner stating "This window is being controlled by automated test software (WebDriver)" is displayed (localized across all 6 supported languages).
- **Distinct Titlebar Color:** The titlebar changes to a warning accent color defined in `assets/os/tokens.css` (`--opozorilo`, matching Safari and Epiphany conventions).

### Selenium Configuration (Python)

Configure Selenium using the `webkitgtk:browserOptions` capability dictionary, specifying the browser executable (`binary`) and the required `--automation` argument:

```python
from selenium import webdriver
from selenium.webdriver.common.by import By

options = webdriver.WebKitGTKOptions()
options.binary_location = "/usr/bin/safeer-browser"
options.add_argument("--automation")

driver = webdriver.Remote(
    command_executor="http://127.0.0.1:4444",
    options=options
)

try:
    driver.get("https://safeer.si")
    print("Page title:", driver.title)
    assert "Safeer" in driver.title
finally:
    driver.quit()
```

### Direct W3C Protocol Request (cURL)

You can initialize a session directly via the standard W3C endpoint:

```bash
curl -X POST http://127.0.0.1:4444/session -H "Content-Type: application/json" -d '{
  "capabilities": {
    "alwaysMatch": {
      "webkitgtk:browserOptions": {
        "binary": "/usr/bin/safeer-browser",
        "args": ["--automation"]
      }
    }
  }
}'
```
