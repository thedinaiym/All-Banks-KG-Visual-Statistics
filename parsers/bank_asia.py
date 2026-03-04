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

def bank_asia(url='https://asiaonline.kg/'):
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.get(url)
        
        # Ждем появления таблицы с курсами
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'table'))
        )
        
        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        def extract_table(html, rate_type):
            soup = BeautifulSoup(html, 'html.parser')
            # Так как неактивная вкладка у них превращается в пустой span, 
            # на странице будет только одна таблица - текущая открытая
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
                    # Валюта лежит внутри тега span рядом с картинкой
                    currency_span = cols[0].find('span')
                    currency = currency_span.get_text(strip=True) if currency_span else cols[0].get_text(strip=True)
                    
                    buy = cols[1].get_text(strip=True)
                    sell = cols[2].get_text(strip=True)
                    
                    if currency and buy and sell:
                        all_data.append({
                            'bank_name': 'Банк Азии',
                            'type': rate_type,
                            'currency': currency,
                            'buy': buy,
                            'sell': sell,
                            'date': today
                        })

        # 1. Парсим вкладку по умолчанию (Наличные)
        extract_table(driver.page_source, 'Наличный')
        
        # 2. Ищем кнопку "Безналичные" и кликаем
        buttons = driver.find_elements(By.XPATH, "//button[contains(text(), 'Безналичные')]")
        for btn in buttons:
            if btn.is_displayed():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", btn)
                time.sleep(1.5)  # Ждем, пока React отрисует таблицу безналичных курсов
                break
                
        # 3. Парсим Безналичные
        extract_table(driver.page_source, 'Безналичный')
        
        driver.quit()
        
        df = pd.DataFrame(all_data)
        if not df.empty:
            df['buy'] = pd.to_numeric(df['buy'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            df = df.dropna(subset=['buy', 'sell'])
            
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"Bank Asia Error: {e}")
        return pd.DataFrame()

# Для локального теста:
if __name__ == '__main__':
    print("Собираем данные Банка Азии...")
    print(bank_asia())