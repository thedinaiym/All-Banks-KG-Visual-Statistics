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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

os.environ.setdefault('WDM_SSL_VERIFY', '0')

BANK_LABEL = 'Азия Банк'


def _get_service() -> Service:
    """
    Returns a ChromeDriver Service.
    Falls back to cached driver or system chromedriver if download fails.
    """
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
    """
    Normalizes a date string to ISO format YYYY-MM-DD.
    Accepts: 'DD.MM.YYYY', 'YYYY-MM-DD', 'DD/MM/YYYY'.
    """
    raw = raw.strip()
    for fmt in ('%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(raw, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return datetime.now().strftime('%Y-%m-%d')


def _extract_rates_from_html(html: str, rate_type: str, row_date: str) -> list[dict]:
    """
    Parses a <ul class="rate-ul"> block into a list of rate dicts.

    Expected structure per currency row:
        <li class="rate-li usd">
            <span class="rate-name">usd</span>
            <span class="rate-buy">87.4000</span>
            <span class="rate-sell">87.8000</span>
            <span class="rate-nbkr">87.4495</span>   ← optional
        </li>
    """
    soup = BeautifulSoup(html, 'html.parser')
    rows = []

    for li in soup.select('ul.rate-ul li.rate-li'):
        # Skip the header row that only contains <strong> tags
        if li.select('strong'):
            continue

        name_el = li.select_one('span.rate-name')
        buy_el  = li.select_one('span.rate-buy')
        sell_el = li.select_one('span.rate-sell')
        nbkr_el = li.select_one('span.rate-nbkr')

        if not (name_el and buy_el and sell_el):
            continue

        item = name_el.get_text(strip=True).upper()
        buy  = buy_el.get_text(strip=True)
        sell = sell_el.get_text(strip=True)

        if item and buy and sell:
            rows.append({
                'bank_name': BANK_LABEL,
                'type':      rate_type,
                'item':      item,
                'buy':       buy,
                'sell':      sell,
                'date':      row_date,
            })

            # Also store the НБКР (central bank) rate as a separate row
            if nbkr_el:
                nbkr_val = nbkr_el.get_text(strip=True)
                if nbkr_val:
                    rows.append({
                        'bank_name': BANK_LABEL,
                        'type':      'НБКР',
                        'item':      item,
                        'buy':       nbkr_val,
                        'sell':      nbkr_val,
                        'date':      row_date,
                    })

    return rows


def bank_asia(url: str = 'https://www.bankasia.kg/ru/glavnaja/') -> pd.DataFrame:
    """
    Scrapes cash and cashless exchange rates from Bank Asia's homepage.

    Returns a DataFrame with columns:
        bank_name | type | item | buy | sell | date
    """
    driver = None
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')

        driver = webdriver.Chrome(service=_get_service(), options=options)
        driver.get(url)

        # Wait until at least one rate list is present
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'ul.rate-ul'))
        )
        time.sleep(1.0)

        all_data = []

        # ── Resolve the update date ──────────────────────────────────────────
        today = datetime.now().strftime('%Y-%m-%d')
        try:
            tab_content = driver.find_element(By.CSS_SELECTOR, '[data-nbkr-update]')
            raw_date = tab_content.get_attribute('data-nbkr-update')  # e.g. "04.03.2026"
            row_date = _parse_date(raw_date) if raw_date else today
        except Exception:
            row_date = today

        # ── Tab definitions: (tab_panel_id, rate_type_label) ─────────────────
        tabs = [
            ('#pills-cash',     'Наличный'),
            ('#pills-cashless', 'Безналичный'),
        ]

        for panel_id, rate_type in tabs:
            try:
                # Activate the tab via its trigger button (data-bs-target attr)
                btn_sel = f'[data-bs-target="{panel_id}"]'
                btn = driver.find_element(By.CSS_SELECTOR, btn_sel)
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(0.8)

                panel = driver.find_element(By.CSS_SELECTOR, panel_id)
                html  = panel.get_attribute('innerHTML')
                all_data.extend(_extract_rates_from_html(html, rate_type, row_date))

            except Exception as e:
                print(f"AB: error processing tab '{rate_type}' ({panel_id}): {e}")

        # ── Build DataFrame ──────────────────────────────────────────────────
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
        df = df.drop_duplicates(subset=['bank_name', 'type', 'item'])

        return df[['bank_name', 'type', 'item', 'buy', 'sell', 'date']].reset_index(drop=True)

    except Exception as e:
        print(f"AB Main Error: {e}")
        import traceback; traceback.print_exc()
        return pd.DataFrame()

    finally:
        if driver:
            driver.quit()


if __name__ == '__main__':
    print("Collecting Bank Asia exchange rates...")
    result = bank_asia()
    if result.empty:
        print("No data returned.")
    else:
        print(result.to_string(index=False))