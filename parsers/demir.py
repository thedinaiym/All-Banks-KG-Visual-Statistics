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

def demir(url='https://demirbank.kg/ru'):
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.get(url)
        
        # Ждем, пока прогрузится секция с конвертером и курсами валют
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'rates-table'))
        )
        
        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        def extract_table(html, rate_type):
            soup = BeautifulSoup(html, 'html.parser')
            table = soup.find('div', class_='rates-table').find('table')
            
            if not table:
                return
                
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) == 3:
                    currency = cols[0].get_text(strip=True)
                    buy = cols[1].get_text(strip=True)
                    sell = cols[2].get_text(strip=True)
                    
                    if currency and buy and sell:
                        all_data.append({
                            'bank_name': 'Демир',
                            'type': rate_type,
                            'currency': currency,
                            'buy': buy,
                            'sell': sell,
                            'date': today
                        })
        
        # 1. Сначала парсим то, что открыто по умолчанию (обычно Наличные)
        extract_table(driver.page_source, 'Наличный')
        
        # 2. Ищем дропдаун (select-custom), кликаем по нему, чтобы открыть меню
        dropdown = driver.find_elements(By.CLASS_NAME, 'select-custom-field')
        if len(dropdown) > 1:
            # Второй дропдаун на странице относится к курсам (первый - в конвертере)
            driver.execute_script("arguments[0].click();", dropdown[1])
            time.sleep(1) # Ждем анимацию открытия
            
            # 3. Ищем опцию "Безналичные курсы" и кликаем
            # Примечание: У Демир банка выпадающий список реализован через <div>, а не <select>
            options_list = driver.find_elements(By.XPATH, "//div[contains(text(), 'Безналичные курсы')]")
            for option in options_list:
                if option.is_displayed():
                    driver.execute_script("arguments[0].click();", option)
                    time.sleep(1.5) # Ждем пока React обновит таблицу
                    break
            
            # 4. Парсим Безналичные
            extract_table(driver.page_source, 'Безналичный')
        
        driver.quit()
        
        df = pd.DataFrame(all_data)
        if not df.empty:
            df['buy'] = pd.to_numeric(df['buy'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            df = df.dropna(subset=['buy', 'sell'])
            
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"Demir Error: {e}")
        return pd.DataFrame()

# Тестируем
if __name__ == '__main__':
    print("Собираем данные Демир Банка...")
    print(demir())