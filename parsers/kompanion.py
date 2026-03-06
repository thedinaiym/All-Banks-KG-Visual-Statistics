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

BANK_LABEL = 'Компаньон'


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


def _extract_date_from_soup(soup: BeautifulSoup) -> str:
    for tag in soup.find_all(['p', 'span', 'div']):
        text = tag.get_text(strip=True)
        m = re.search(r'\b(\d{2}\.\d{2}\.\d{4})\b', text)
        if m:
            return _parse_date(m.group(1))
    return datetime.now().strftime('%Y-%m-%d')


def _extract_rates_grid(soup: BeautifulSoup, rate_type: str, row_date: str) -> list[dict]:
    """Original strategy: grid-cols-3 divs with currency flag images."""
    rows = []
    for grid in soup.find_all('div', class_=lambda c: c and 'grid-cols-3' in c):
        children = [ch for ch in grid.children if ch.name]
        if len(children) != 3:
            continue
        currency_cell, buy_cell, sell_cell = children
        if currency_cell.name != 'div':
            continue
        img = currency_cell.find('img')
        if not img or not img.get('alt'):
            continue
        currency = img['alt'].strip().upper()
        buy  = buy_cell.get_text(strip=True)
        sell = sell_cell.get_text(strip=True)
        if currency and buy and sell:
            rows.append({
                'bank_name': BANK_LABEL,
                'type':      rate_type,
                'currency':  currency,
                'buy':       buy,
                'sell':      sell,
                'date':      row_date,
            })
    return rows


def _extract_rates_table(soup: BeautifulSoup, rate_type: str, row_date: str) -> list[dict]:
    """Fallback: plain HTML tables."""
    rows = []
    for table in soup.find_all('table'):
        tbody = table.find('tbody') or table
        for row in tbody.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) < 3:
                continue
            currency = cols[0].get_text(strip=True).upper()
            buy      = cols[1].get_text(strip=True)
            sell     = cols[2].get_text(strip=True)
            if any(kw in currency.lower() for kw in ('валют', 'наим', 'currency')):
                continue
            if currency and buy and sell:
                rows.append({
                    'bank_name': BANK_LABEL,
                    'type':      rate_type,
                    'currency':  currency,
                    'buy':       buy,
                    'sell':      sell,
                    'date':      row_date,
                })
    return rows


def _scrape_tab(driver, btn_text: str, rate_type: str, all_data: list) -> None:
    """Click a tab button and extract whatever data loads."""
    try:
        xpath = (
            f"//button[normalize-space()='{btn_text}'] | "
            f"//a[normalize-space()='{btn_text}'] | "
            f"//li[normalize-space()='{btn_text}']"
        )
        btn = driver.find_element(By.XPATH, xpath)
        driver.execute_script("arguments[0].click();", btn)
        # Wait for content to update after click
        time.sleep(1.5)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        row_date = _extract_date_from_soup(soup)
        data = _extract_rates_grid(soup, rate_type, row_date)
        if not data:
            data = _extract_rates_table(soup, rate_type, row_date)
        all_data.extend(data)
    except Exception as e:
        print(f"Kompanion: error on tab '{btn_text}': {e}")


def kompanion(url: str = 'https://www.kompanion.kg/ru/kursy/') -> pd.DataFrame:
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

        # Wait for actual rate data — a <td> inside a table, or a currency
        # image, whichever renders first.
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located(
                    (By.CSS_SELECTOR, 'table td, img[alt="USD"], img[alt="usd"]')
                )
            )
        except Exception:
            pass
        time.sleep(1.5)

        all_data = []

        # Try clicking Наличные / Безналичные tab buttons
        for btn_text, rate_type in [('Наличные', 'Наличный'), ('Безналичные', 'Безналичный')]:
            _scrape_tab(driver, btn_text, rate_type, all_data)

        # If tab-clicking yielded nothing, parse the current page as-is
        if not all_data:
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            row_date = _extract_date_from_soup(soup)
            all_data = _extract_rates_grid(soup, 'Наличный', row_date)
            if not all_data:
                all_data = _extract_rates_table(soup, 'Наличный', row_date)

        driver.quit()
        driver = None

        df = pd.DataFrame(all_data)
        if df.empty:
            return df

        for col in ['buy', 'sell']:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(r'\s+', '', regex=True).str.replace(',', '.'),
                errors='coerce',
            )
        df = df.dropna(subset=['buy', 'sell'])
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']].reset_index(drop=True)

    except Exception as e:
        print(f"Kompanion Main Error: {e}")
        import traceback; traceback.print_exc()
        return pd.DataFrame()
    finally:
        if driver:
            driver.quit()


if __name__ == '__main__':
    print("Collecting Kompanion Bank exchange rates...")
    result = kompanion()
    if result.empty:
        print("No data returned.")
    else:
        print(result.to_string(index=False))