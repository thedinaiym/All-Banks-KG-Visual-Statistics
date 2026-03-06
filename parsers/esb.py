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

BANK_LABEL = 'ЕСБ'


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


def _parse_date(raw: str) -> str:
    raw = raw.strip()
    for fmt in ('%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(raw, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return datetime.now().strftime('%Y-%m-%d')


def _extract_date_from_tab(tab_li) -> str:
    span = tab_li.find('span', style=lambda s: s and 'background-color: #ff0000' in s)
    if span:
        text = span.get_text(separator=' ', strip=True)
        m = re.search(r'\b(\d{2}\.\d{2}\.\d{4})\b', text)
        if m:
            return _parse_date(m.group(1))
    return datetime.now().strftime('%Y-%m-%d')


def _parse_currency_tab(tab_li, rate_type: str, row_date: str, all_data: list) -> None:
    table = tab_li.find('table')
    if not table:
        return
    tbody = table.find('tbody')
    if not tbody:
        return
    for row in tbody.find_all('tr'):
        cols = row.find_all('td')
        if len(cols) < 5:
            continue
        currency = cols[1].get_text(strip=True)
        buy      = cols[2].get_text(strip=True)
        sell     = cols[4].get_text(strip=True)
        if currency and buy and sell:
            all_data.append({
                'bank_name': BANK_LABEL,
                'type':      rate_type,
                'currency':  currency,
                'buy':       buy,
                'sell':      sell,
                'date':      row_date,
            })


def esb(url: str = 'https://esb.kg/') -> pd.DataFrame:
    """
    Scrapes ESB exchange rates via Selenium so the corporate proxy
    (proxy.doscredobank.kg) is used automatically, consistent with all
    other parsers in this project.
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

        # Wait until the UIkit switcher with exchange rate tables is present
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'ul.uk-switcher'))
            )
        except Exception:
            pass
        time.sleep(1.0)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        all_data = []

        switcher = soup.find('ul', class_='uk-switcher')
        if not switcher:
            print("ESB: uk-switcher not found")
            return pd.DataFrame()

        tabs = switcher.find_all('li', recursive=False)
        tab_map = {0: 'Наличный', 1: 'Безналичный'}

        for idx, rate_type in tab_map.items():
            if idx >= len(tabs):
                continue
            tab = tabs[idx]
            row_date = _extract_date_from_tab(tab)
            _parse_currency_tab(tab, rate_type, row_date, all_data)

        df = pd.DataFrame(all_data)
        if df.empty:
            return df

        for col in ['buy', 'sell']:
            df[col] = pd.to_numeric(
                df[col].astype(str)
                       .str.replace(r'\s+', '', regex=True)
                       .str.replace(',', '.'),
                errors='coerce',
            )

        df = df.dropna(subset=['buy', 'sell'])
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']].reset_index(drop=True)

    except Exception as e:
        print(f"ESB Error: {e}")
        import traceback; traceback.print_exc()
        return pd.DataFrame()
    finally:
        if driver:
            driver.quit()


if __name__ == '__main__':
    print("Collecting ESB exchange rates...")
    result = esb()
    if result.empty:
        print("No data returned.")
    else:
        print(result.to_string(index=False))