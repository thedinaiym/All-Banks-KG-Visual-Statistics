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
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.get(url)
        
        # Ждем, пока Vue.js отрендерит таблицу
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'table'))
        )
        
        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Функция для парсинга активной таблицы
        def extract_table(html, rate_type):
            soup = BeautifulSoup(html, 'html.parser')
            table = soup.find('table')
            if not table:
                return
                
            tbody = table.find('tbody')
            if not tbody:
                return
                
            rows = tbody.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    # Валюта лежит внутри тега span с классом currency
                    currency_span = cols[0].find('span', class_='currency')
                    currency = currency_span.get_text(strip=True) if currency_span else cols[0].get_text(strip=True)
                    
                    buy = cols[1].get_text(strip=True)
                    sell = cols[2].get_text(strip=True)
                    
                    if currency and buy and sell:
                        all_data.append({
                            'bank_name': 'O!Bank',
                            'type': rate_type,
                            'currency': currency,
                            'buy': buy,
                            'sell': sell,
                            'date': today
                        })

        # 1. Парсим открытую по умолчанию вкладку ("Наличные")
        extract_table(driver.page_source, 'Наличный')
        
        # 2. Ищем кнопку "Безналичные" и переключаем
        buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Безналичные')]")
        for btn in buttons:
            if btn.is_displayed():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1.5) # Ждем пока Vue.js обновит данные в DOM
                break
                
        # 3. Парсим вкладку "Безналичные"
        extract_table(driver.page_source, 'Безналичный')
        
        driver.quit()
        
        df = pd.DataFrame(all_data)
        if not df.empty:
            # Чистим данные (запятые превращаем в точки)
            df['buy'] = pd.to_numeric(df['buy'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            df = df.dropna(subset=['buy', 'sell'])
            
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"O!Bank Error: {e}")
        return pd.DataFrame()

# Локальное тестирование
if __name__ == '__main__':
    print("Собираем данные O!Bank...")
    print(obank())