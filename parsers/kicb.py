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

def kicb(url='https://kicb.net/currency/'):
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')

        # Словарь вкладок: текст на кнопке -> тип для БД
        tabs = {
            "Наличные": "Наличный",
            "Безналичные": "Безналичный",
            "НБКР": "НБКР"
        }

        driver.get(url)

        def extract_current_table(rate_type):
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'exchange-table'))
            )
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            # Ищем таблицу внутри секции exchange
            table = soup.find('section', class_='exchange').find('table')
            if not table:
                return

            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    # Валюта (например, "USD Доллар США") -> берем только код "USD"
                    currency_text = cols[0].find('p', class_='val').get_text(strip=True)
                    currency = currency_text.split()[0] # Получаем USD, EUR и т.д.
                    
                    buy = cols[1].get_text(strip=True)
                    sell = cols[2].get_text(strip=True)

                    if currency and buy and sell:
                        all_data.append({
                            'bank_name': 'KICB',
                            'type': rate_type,
                            'currency': currency,
                            'buy': buy,
                            'sell': sell,
                            'date': today
                        })

        # Обходим все вкладки
        for tab_name, internal_type in tabs.items():
            try:
                # Ищем ссылку/кнопку в меню вкладок
                tab_button = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, f"//span[contains(text(), '{tab_name}')] | //a[contains(text(), '{tab_name}')]"))
                )
                driver.execute_script("arguments[0].click();", tab_button)
                time.sleep(2) # Даем время на подгрузку данных
                extract_current_table(internal_type)
            except Exception as tab_e:
                print(f"Ошибка при парсинге вкладки {tab_name}: {tab_e}")

        driver.quit()

        df = pd.DataFrame(all_data)
        if not df.empty:
            # Очистка данных
            df['buy'] = pd.to_numeric(df['buy'].str.replace(',', '.'), errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'].str.replace(',', '.'), errors='coerce')
            df = df.dropna(subset=['buy', 'sell'])
            
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]

    except Exception as e:
        print(f"KICB Error: {e}")
        return pd.DataFrame()

# Локальное тестирование
if __name__ == '__main__':
    print("Собираем данные KICB...")
    result = kicb()
    if not result.empty:
        print(result.to_string(index=False))
    else:
        print("Данные не найдены.")