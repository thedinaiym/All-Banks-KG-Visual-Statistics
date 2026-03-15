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
from selenium.webdriver.support.ui import Select
import time

os.environ.setdefault('WDM_SSL_VERIFY', '0')


def _get_service() -> Service:
    """
    Возвращает Service для ChromeDriver.
    Сначала пробует ChromeDriverManager (скачать/обновить),
    при сетевой ошибке ищет последний закешированный драйвер,
    иначе падает на системный chromedriver из PATH.
    """
    try:
        return Service(ChromeDriverManager().install())
    except Exception as e:
        print(f"[WDM] Не удалось загрузить драйвер ({e}), ищу кеш...")

    wdm_root = os.path.join(os.path.expanduser("~"), ".wdm", "drivers", "chromedriver")
    patterns = [
        os.path.join(wdm_root, "**", "chromedriver.exe"),   # Windows
        os.path.join(wdm_root, "**", "chromedriver"),        # Linux/Mac
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


def bakai(url='https://bakai.kg/ru/'):
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')

        service = _get_service()
        driver = webdriver.Chrome(service=service, options=options)

        driver.get(url)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'select'))
        )

        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')  # ISO-формат YYYY-MM-DD

        def extract_table(html, rate_type):
            soup = BeautifulSoup(html, 'html.parser')
            widget = soup.find('div', class_=lambda c: c and 'CurrencyWidget_table_content' in c)
            if not widget:
                return

            table = widget.find('table')
            if not table:
                return

            tbody = table.find('tbody')
            if not tbody:
                return

            for row in tbody.find_all('tr'):
                # Пропускаем строки золота (слитков), их мы спарсим отдельно
                row_classes = row.get('class', [])
                if row_classes and any('ingot_row' in c for c in row_classes):
                    continue

                cols = row.find_all('th')
                if len(cols) < 3:
                    continue

                img_tag = cols[0].find('img')
                if not (img_tag and 'alt' in img_tag.attrs):
                    continue
                currency = img_tag['alt']

                buy  = cols[1].get_text(strip=True)
                sell = cols[2].get_text(strip=True)

                if currency and buy and sell:
                    all_data.append({
                        'bank_name': 'Бакай',
                        'type':      rate_type,
                        'currency':  currency,
                        'buy':       buy,
                        'sell':      sell,
                        'date':      today,
                    })

        dropdown_element = driver.find_element(By.TAG_NAME, 'select')
        select = Select(dropdown_element)

        # 1. Парсинг Валют
        for value, label in [('cash', 'Наличный'), ('non_cash', 'Безналичный')]:
            try:
                select.select_by_value(value)
                time.sleep(1)
                extract_table(driver.page_source, label)
            except Exception as e:
                print(f"Bakai {value} error: {e}")

        # 2. Парсинг Золота (Слитки)
        try:
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            # Ищем строки, содержащие класс CurrencyWidget_ingot_row
            ingot_rows = soup.find_all('tr', class_=lambda c: c and 'CurrencyWidget_ingot_row' in c)
            
            for row in ingot_rows:
                cols = row.find_all('th')
                if len(cols) >= 3:
                    weight = cols[0].get_text(strip=True)
                    buy = cols[1].get_text(strip=True)
                    sell = cols[2].get_text(strip=True)

                    # Форматируем название (например, "1.0000" превращаем в "Золото 1 гр.")
                    try:
                        weight_float = float(weight)
                        item_name = f"Золото {weight_float:g} гр."
                    except ValueError:
                        item_name = f"Золото {weight}"

                    if buy and sell:
                        all_data.append({
                            'bank_name': 'Бакай',
                            'type': 'Золото', # Scheduler поймает это слово и отправит в gold_rates
                            'currency': item_name,
                            'buy': buy,
                            'sell': sell,
                            'date': today,
                        })
        except Exception as e:
            print(f"Bakai Gold error: {e}")

        driver.quit()

        # 3. Финализация DataFrame
        df = pd.DataFrame(all_data)
        if not df.empty:
            df['buy']  = pd.to_numeric(df['buy'].astype(str).str.replace(r'\s+', '', regex=True).str.replace(',', '.'), errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'].astype(str).str.replace(r'\s+', '', regex=True).str.replace(',', '.'), errors='coerce')
            df = df.dropna(subset=['buy', 'sell'])

        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]

    except Exception as e:
        print(f"Bakai Error: {e}")
        return pd.DataFrame()


if __name__ == '__main__':
    print("Собираем данные Бакай Банка...")
    print(bakai())