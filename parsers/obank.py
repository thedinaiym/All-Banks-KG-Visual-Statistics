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

def obank(url='https://obank.kg/ru'):
    driver = None
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        # Некоторые Vue-сайты блокируют headless по дефолтному UA
        options.add_argument(
            'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)

        # Ждём появления хотя бы одной строки таблицы
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'table tbody tr'))
        )
        time.sleep(1)  # доп. пауза для полного рендера Vue

        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')

        def extract_table(html, rate_type):
            soup = BeautifulSoup(html, 'html.parser')
            table = soup.find('table')
            if not table:
                print(f"O!Bank: таблица не найдена для '{rate_type}'")
                return

            tbody = table.find('tbody')
            if not tbody:
                return

            rows = tbody.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) < 3:
                    continue

                # Валюта: ищем span с классом currency (может быть многоклассовым)
                currency_span = cols[0].find('span', class_='currency')
                if currency_span:
                    currency = currency_span.get_text(strip=True)
                else:
                    spans = cols[0].find_all('span')
                    currency = spans[-1].get_text(strip=True) if spans else cols[0].get_text(strip=True)

                buy  = cols[1].get_text(strip=True)
                sell = cols[2].get_text(strip=True)

                if currency and buy and sell:
                    all_data.append({
                        'bank_name': 'O!Bank',
                        'type':      rate_type,
                        'currency':  currency,
                        'buy':       buy,
                        'sell':      sell,
                        'date':      today,
                    })

        # 1. Наличные (вкладка по умолчанию)
        extract_table(driver.page_source, 'Наличный')

        # 2. Переключаемся на «Безналичные»
        switched = False
        for xpath in [
            "//button[contains(., 'Безналичные')]",
            "//button[contains(., 'безналичные')]",
            "//*[contains(@class,'tab') and contains(., 'Безналичные')]",
        ]:
            btns = driver.find_elements(By.XPATH, xpath)
            for btn in btns:
                try:
                    if btn.is_displayed():
                        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
                        time.sleep(0.3)
                        driver.execute_script("arguments[0].click();", btn)
                        time.sleep(2)  # Vue.js обновляет DOM асинхронно
                        switched = True
                        break
                except Exception:
                    pass
            if switched:
                break

        if switched:
            extract_table(driver.page_source, 'Безналичный')
        else:
            print("O!Bank: не удалось найти кнопку 'Безналичные'")

        df = pd.DataFrame(all_data)
        if not df.empty:
            df['buy']  = pd.to_numeric(
                df['buy'].astype(str).str.replace(r'\s+', '', regex=True).str.replace(',', '.'),
                errors='coerce'
            )
            df['sell'] = pd.to_numeric(
                df['sell'].astype(str).str.replace(r'\s+', '', regex=True).str.replace(',', '.'),
                errors='coerce'
            )
            df = df.dropna(subset=['buy', 'sell'])

        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]

    except Exception as e:
        print(f"O!Bank Error: {e}")
        import traceback; traceback.print_exc()
        return pd.DataFrame()
    finally:
        if driver:
            driver.quit()


if __name__ == '__main__':
    print("Собираем данные O!Bank...")
    print(obank())