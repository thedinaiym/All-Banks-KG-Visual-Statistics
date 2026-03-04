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

def kkb(url='https://kkb.kg/currency'):
    try:
        # Настраиваем браузер для фонового режима (без визуального открытия окна)
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        # Автоматическое скачивание и запуск нужной версии ChromeDriver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.get(url)
        
        # Ждем максимум 10 секунд, пока React отрисует таблицу на странице
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'table'))
        )
        
        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Внутренняя функция для парсинга HTML-таблицы
        def extract_table_data(html, rate_type):
            soup = BeautifulSoup(html, 'html.parser')
            table = soup.find('table')
            if not table:
                return
            
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) == 3:
                    # В коде KKB валюта лежит как "USDKGS", вытаскиваем первые 3 буквы
                    text_currency = cols[0].get_text(strip=True) 
                    currency = text_currency[:3] 
                    
                    buy = cols[1].get_text(strip=True)
                    sell = cols[2].get_text(strip=True)
                    
                    # Пропускаем строки с ошибками вроде #REF!
                    if buy == '#REF!' or sell == '#REF!':
                        continue
                        
                    all_data.append({
                        'bank_name': 'Кыргызкоммерц',
                        'type': rate_type,
                        'currency': currency,
                        'buy': buy,
                        'sell': sell,
                        'date': today
                    })
        
        # 1. Парсим "Наличные" (они открыты по умолчанию)
        extract_table_data(driver.page_source, 'Наличный')
        
        # 2. Ищем вкладку "Безналичные" и кликаем по ней
        tabs = driver.find_elements(By.XPATH, "//div[contains(text(), 'Безналичные')]")
        for tab in tabs:
            if tab.is_displayed():
                driver.execute_script("arguments[0].click();", tab)
                time.sleep(1.5) # Ждем 1.5 секунды, пока React обновит таблицу
                break
                
        # 3. Парсим "Безналичные"
        extract_table_data(driver.page_source, 'Безналичный')
        
        # Закрываем виртуальный браузер
        driver.quit()
        
        # Упаковываем в DataFrame
        df = pd.DataFrame(all_data)
        if not df.empty:
            df['buy'] = pd.to_numeric(df['buy'], errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'], errors='coerce')
            
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"KKB Error: {e}")
        return pd.DataFrame()

# Блок для отдельной проверки скрипта (если запустишь просто python kkb.py)
if __name__ == '__main__':
    print("Собираем данные KKB...")
    print(kkb())