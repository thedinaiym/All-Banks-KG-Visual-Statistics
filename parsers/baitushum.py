import os
import glob
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

os.environ.setdefault('WDM_SSL_VERIFY', '0')


def _get_service() -> Service:
    """
    Try to download/update chromedriver via WDM.
    If that fails (e.g. no internet access to reach the WDM endpoint),
    fall back to the most-recently cached driver on disk.
    """
    try:
        return Service(ChromeDriverManager().install())
    except Exception as e:
        print(f"[WDM] Не удалось загрузить драйвер ({e}), ищу кеш...")

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
        print(f"[WDM] Использую кеш: {driver_path}")
        return Service(driver_path)

    print("[WDM] Кеш не найден, использую системный chromedriver")
    return Service()


def baitushum(url='https://www.baitushum.kg/ru/'):
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
            "cash-tab":     "Наличный",
            "cashless-tab": "Безналичный",
            "btb24-tab":    "Мобильный банкинг",
        }

        for tab_id, rate_type in tabs.items():
            try:
                tab_button = driver.find_element(By.ID, tab_id)
                driver.execute_script("arguments[0].click();", tab_button)
                time.sleep(1)

                soup = BeautifulSoup(driver.page_source, 'html.parser')
                target_pane_id = tab_button.get_attribute('aria-controls')
                pane = soup.find('div', id=target_pane_id)

                if not pane:
                    continue

                rows = pane.find_all('li', class_='rate-li')
                for row in rows:
                    if 'head' in row.get('class', []):
                        continue

                    name_div = row.find('div', class_='rate-col rate-name')
                    buy_div  = row.find('div', class_='rate-col rate-buy')
                    sell_div = row.find('div', class_='rate-col rate-sell')

                    if name_div and buy_div and sell_div:
                        currency = name_div.get_text(strip=True).upper()
                        buy  = buy_div.get_text(strip=True)
                        sell = sell_div.get_text(strip=True)

                        if currency and buy and sell:
                            all_data.append({
                                'bank_name': 'Бай-Тушум',
                                'type':      rate_type,
                                'currency':  currency,
                                'buy':       buy,
                                'sell':      sell,
                                'date':      today,
                            })
            except Exception as e:
                print(f"Baitushum Tab {tab_id} Error: {e}")

        driver.quit()
        driver = None

        df = pd.DataFrame(all_data)
        if not df.empty:
            df['buy']  = pd.to_numeric(df['buy'].str.replace(',', '.'),  errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'].str.replace(',', '.'), errors='coerce')
            df = df.dropna(subset=['buy', 'sell'])

        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]

    except Exception as e:
        print(f"Baitushum Error: {e}")
        return pd.DataFrame()
    finally:
        if driver:
            driver.quit()


if __name__ == '__main__':
    print("Собираем данные Банка Бай-Тушум...")
    result = baitushum()
    if not result.empty:
        print(result.to_string(index=False))
    else:
        print("Данные не найдены.")