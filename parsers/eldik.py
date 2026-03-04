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

def eldik(url='https://eldik.kg/'):
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.get(url)
        
        # Ждем, пока React отрендерит таблицу. 
        # Ищем по XPATH, игнорируя динамические хэши классов (вроде __Z10bv)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//table[contains(@class, 'table-exchange-rates_table')]"))
        )
        
        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Внутренняя функция для вытягивания данных из открытой вкладки
        def extract_table_data(html, rate_type):
            soup = BeautifulSoup(html, 'html.parser')
            # Ищем именно открытую панель (selected)
            active_panel = soup.find('div', class_='react-tabs__tab-panel--selected')
            if not active_panel:
                return
                
            table = active_panel.find('table')
            if not table:
                return
                
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    # Валюта в первой колонке (текст вместе с SVG картинкой, берем только текст)
                    currency = cols[0].get_text(strip=True)
                    # Покупка и продажа
                    buy = cols[1].get_text(strip=True)
                    sell = cols[2].get_text(strip=True)
                    
                    if currency and buy and sell:
                        all_data.append({
                            'bank_name': 'Элдик',
                            'type': rate_type,
                            'currency': currency,
                            'buy': buy,
                            'sell': sell,
                            'date': today
                        })
        
        # 1. Сразу парсим "Наличные" (открыты по умолчанию при загрузке страницы)
        extract_table_data(driver.page_source, 'Наличный')
        
        # 2. Ищем вкладку "Безналичные" (тег <li>)
        tabs = driver.find_elements(By.XPATH, "//li[contains(text(), 'Безналичные')]")
        for tab in tabs:
            if tab.is_displayed():
                # Прокручиваем до элемента на всякий случай и кликаем
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", tab)
                time.sleep(0.5)
                driver.execute_script("arguments[0].click();", tab)
                time.sleep(1.5) # Ждем, пока React подгрузит данные в пустой <div>
                break
                
        # 3. Парсим "Безналичные"
        extract_table_data(driver.page_source, 'Безналичный')
        
        # Обязательно закрываем браузер
        driver.quit()
        
        # Упаковываем в таблицу
        df = pd.DataFrame(all_data)
        if not df.empty:
            df['buy'] = pd.to_numeric(df['buy'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            df = df.dropna(subset=['buy', 'sell'])
            
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"Eldik Error: {e}")
        return pd.DataFrame()

# Тестовый запуск
if __name__ == '__main__':
    print("Собираем данные Элдик Банка...")
    print(eldik())