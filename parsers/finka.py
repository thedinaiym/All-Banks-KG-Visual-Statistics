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

BANK_LABEL = 'FINCA Bank'


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


def finca(url: str = 'https://fincabank.kg/kursy-valyut/') -> pd.DataFrame:
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

        # Wait for a <td> inside a table — means the JS-rendered rates are ready.
        # More specific than 'table' alone (which may appear before data loads).
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'table td'))
            )
        except Exception:
            pass
        time.sleep(1.5)

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        today = datetime.now().strftime('%Y-%m-%d')
        all_data = []

        # Strategy 1: original tab-panel structure (finca-ux-tab-panel)
        rates_widget = soup.find(id='finca-tab-1') or soup
        panels = rates_widget.find_all('div', class_='finca-ux-tab-panel')

        for panel in panels:
            raw_type = panel.get('data-title', '')
            if 'Наличные' in raw_type:
                rate_type = 'Наличный'
            elif 'Безналичные' in raw_type:
                rate_type = 'Безналичный'
            else:
                continue

            table = panel.find('table')
            if not table:
                continue
            tbody = table.find('tbody') or table
            for row in tbody.find_all('tr'):
                cols = row.find_all('td')
                if len(cols) < 3:
                    continue
                badge = cols[0].find('span', class_='finca-badge')
                currency = badge.get_text(strip=True) if badge else cols[0].get_text(strip=True)
                buy  = cols[1].get_text(strip=True)
                sell = cols[2].get_text(strip=True)
                if currency and buy and sell:
                    all_data.append({
                        'bank_name': BANK_LABEL,
                        'type':      rate_type,
                        'currency':  currency,
                        'buy':       buy,
                        'sell':      sell,
                        'date':      today,
                    })

        # Strategy 2: generic table fallback (handles site redesigns)
        if not all_data:
            for table in soup.find_all('table'):
                tbody = table.find('tbody') or table
                tds = tbody.find_all('td')
                if len(tds) < 3:
                    continue
                # Infer rate type from a heading near the table
                heading_text = ''
                for ancestor in table.parents:
                    h = ancestor.find(['h1', 'h2', 'h3', 'h4', 'strong', 'b'])
                    if h:
                        heading_text = h.get_text(strip=True)
                        break
                rate_type = 'Безналичный' if 'Безналичн' in heading_text else 'Наличный'

                for row in tbody.find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) < 3:
                        continue
                    currency = cols[0].get_text(strip=True)
                    buy      = cols[1].get_text(strip=True)
                    sell     = cols[2].get_text(strip=True)
                    if any(kw in currency.lower() for kw in ('валют', 'наим', 'currency')):
                        continue
                    if currency and buy and sell:
                        all_data.append({
                            'bank_name': BANK_LABEL,
                            'type':      rate_type,
                            'currency':  currency,
                            'buy':       buy,
                            'sell':      sell,
                            'date':      today,
                        })

        # Strategy 3: try clicking tab buttons if the page uses a JS tab widget
        # and neither strategy above found data yet
        if not all_data:
            tab_map = [
                ('Наличные',    'Наличный'),
                ('Безналичные', 'Безналичный'),
            ]
            for btn_text, rate_type in tab_map:
                try:
                    xpath = (
                        f"//button[normalize-space()='{btn_text}'] | "
                        f"//a[normalize-space()='{btn_text}'] | "
                        f"//li[normalize-space()='{btn_text}']"
                    )
                    btn = driver.find_element(By.XPATH, xpath)
                    driver.execute_script("arguments[0].click();", btn)
                    time.sleep(1.5)
                    soup2 = BeautifulSoup(driver.page_source, 'html.parser')
                    for table in soup2.find_all('table'):
                        tbody = table.find('tbody') or table
                        for row in tbody.find_all('tr'):
                            cols = row.find_all('td')
                            if len(cols) < 3:
                                continue
                            badge = cols[0].find('span', class_='finca-badge')
                            currency = badge.get_text(strip=True) if badge else cols[0].get_text(strip=True)
                            buy  = cols[1].get_text(strip=True)
                            sell = cols[2].get_text(strip=True)
                            if any(kw in currency.lower() for kw in ('валют', 'наим', 'currency')):
                                continue
                            if currency and buy and sell:
                                all_data.append({
                                    'bank_name': BANK_LABEL,
                                    'type':      rate_type,
                                    'currency':  currency,
                                    'buy':       buy,
                                    'sell':      sell,
                                    'date':      today,
                                })
                except Exception:
                    pass

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
        print(f"FINCA Bank Error: {e}")
        import traceback; traceback.print_exc()
        return pd.DataFrame()
    finally:
        if driver:
            driver.quit()


if __name__ == '__main__':
    print("Collecting FINCA Bank exchange rates...")
    result = finca()
    if result.empty:
        print("No data returned.")
    else:
        print(result.to_string(index=False))