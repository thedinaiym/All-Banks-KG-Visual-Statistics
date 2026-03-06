import os
import glob
import json
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import time

os.environ.setdefault('WDM_SSL_VERIFY', '0')

BANK_LABEL = 'Кыргызстан'  # MBank = Банк Кыргызстан


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


def mbank(url: str = 'https://mbank.kg/') -> pd.DataFrame:
    """
    Fetch MBank (Банк Кыргызстан) exchange rates via Selenium so that
    the corporate proxy (proxy.doscredobank.kg) is used automatically,
    the same as all other Selenium-based parsers in this project.

    Falls back to parsing the __NEXT_DATA__ JSON embedded in the page.
    """
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

        # Wait until the __NEXT_DATA__ script tag is present in the DOM
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, 'script#__NEXT_DATA__')
            )
        )
        time.sleep(0.5)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        script_tag = soup.find('script', {'id': '__NEXT_DATA__', 'type': 'application/json'})

        if not script_tag:
            print("MBank Error: __NEXT_DATA__ script tag not found")
            return pd.DataFrame()

        data = json.loads(script_tag.string)
        exchange_info = data['props']['pageProps']['mainPage']['exchange']
        cash_exchange = exchange_info.get('cash_exchange', [])

        cash_exchange_dfs = []
        for item in cash_exchange:
            df = pd.DataFrame(item['values'])
            df['type'] = item['operation_type']
            cash_exchange_dfs.append(df)

        if not cash_exchange_dfs:
            return pd.DataFrame()

        cash_exchange_df = pd.concat(cash_exchange_dfs, ignore_index=True)
        cash_exchange_df['bank_name'] = BANK_LABEL
        cash_exchange_df['date'] = datetime.now().strftime('%Y-%m-%d')

        # Normalise type labels
        cash_exchange_df['type'] = cash_exchange_df['type'].replace({
            'Для операций с наличными': 'Наличный',
            'Безналичные курсы':        'Безналичный',
        })

        # Drop internal columns not needed downstream
        for col in ('id', 'nbkr'):
            if col in cash_exchange_df.columns:
                cash_exchange_df = cash_exchange_df.drop(columns=[col])

        return cash_exchange_df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]

    except Exception as e:
        print(f"MBank Error: {e}")
        return pd.DataFrame()
    finally:
        if driver:
            driver.quit()


if __name__ == '__main__':
    print("Collecting MBank exchange rates...")
    result = mbank()
    if result.empty:
        print("No data returned.")
    else:
        print(result.to_string(index=False))