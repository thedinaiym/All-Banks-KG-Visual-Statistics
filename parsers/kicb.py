import os
import glob
import re
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

os.environ.setdefault('WDM_SSL_VERIFY', '0')


def _get_service() -> Service:
    try:
        return Service(ChromeDriverManager().install())
    except Exception as e:
        print(f"[WDM] Failed to download driver ({e}), searching cache...")

    wdm_root = os.path.join(os.path.expanduser("~"), ".wdm", "drivers", "chromedriver")
    patterns = [
        os.path.join(wdm_root, "**", "chromedriver.exe"),
        os.path.join(wdm_root, "**", "chromedriver"),
    ]
    cached = []
    for pat in patterns:
        cached.extend(glob.glob(pat, recursive=True))

    if cached:
        driver_path = sorted(cached)[-1]
        print(f"[WDM] Using cached driver: {driver_path}")
        return Service(driver_path)

    print("[WDM] No cache found, using system chromedriver")
    return Service()


def _extract_currency(cell) -> str:
    """
    Extract the 3-4 letter ISO currency code from a table cell.

    The KICB site renders the code and name without a guaranteed space,
    e.g. the <p class="val"> may contain "USDДоллар США" or "USD Доллар США".
    We grab the leading run of ASCII uppercase letters (2-4 chars) to be safe.
    """
    # Prefer the dedicated .val paragraph if it exists
    val_p = cell.find('p', class_='val')
    raw = val_p.get_text(strip=True) if val_p else cell.get_text(strip=True)

    m = re.match(r'^([A-Z]{2,4})', raw)
    return m.group(1) if m else raw.split()[0]


def kicb(url: str = 'https://kicb.net/currency/') -> pd.DataFrame:
    driver = None
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        # NOTE: do NOT add --no-proxy-server; let Chrome use the system proxy

        driver = webdriver.Chrome(service=_get_service(), options=options)
        driver.get(url)

        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')

        tabs = {
            "Наличные":    "Наличный",
            "Безналичные": "Безналичный",
            "НБКР":        "НБКР",
        }

        def extract_current_table(rate_type: str) -> None:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'exchange-table'))
            )
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            section = soup.find('section', class_='exchange')
            if not section:
                return
            table = section.find('table')
            if not table:
                return
            tbody = table.find('tbody')
            if not tbody:
                return

            for row in tbody.find_all('tr'):
                cols = row.find_all('td')
                if len(cols) < 3:
                    continue

                currency = _extract_currency(cols[0])
                buy      = cols[1].get_text(strip=True)
                sell     = cols[2].get_text(strip=True)

                if currency and buy and sell:
                    all_data.append({
                        'bank_name': 'KICB',
                        'type':      rate_type,
                        'currency':  currency,
                        'buy':       buy,
                        'sell':      sell,
                        'date':      today,
                    })

        for tab_name, internal_type in tabs.items():
            try:
                tab_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((
                        By.XPATH,
                        f"//span[contains(text(), '{tab_name}')] | //a[contains(text(), '{tab_name}')]"
                    ))
                )
                driver.execute_script("arguments[0].click();", tab_button)
                time.sleep(2)
                extract_current_table(internal_type)
            except Exception as tab_e:
                print(f"KICB: ошибка на вкладке '{tab_name}': {tab_e}")

        driver.quit()
        driver = None

        df = pd.DataFrame(all_data)
        if not df.empty:
            df['buy']  = pd.to_numeric(df['buy'].str.replace(',', '.'),  errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'].str.replace(',', '.'), errors='coerce')
            df = df.dropna(subset=['buy', 'sell'])

        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]

    except Exception as e:
        print(f"KICB Error: {e}")
        return pd.DataFrame()
    finally:
        if driver:
            driver.quit()


if __name__ == '__main__':
    print("Собираем данные KICB...")
    result = kicb()
    if not result.empty:
        print(result.to_string(index=False))
    else:
        print("Данные не найдены.")