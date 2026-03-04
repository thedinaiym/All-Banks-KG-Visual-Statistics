import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

def finca(url='https://fincabank.kg/'):
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.get(url)
        
        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')

        # Ждем немного для инициализации скриптов темы
        time.sleep(2)
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Находим все панели вкладок
        panels = soup.find_all('div', class_='finca-ux-tab-panel')
        
        for panel in panels:
            # Тип курса берем из атрибута data-title (Наличные / Безналичные)
            raw_type = panel.get('data-title', '')
            rate_type = "Наличный" if "Наличные" in raw_type else "Безналичный"
            
            table = panel.find('table')
            if not table:
                continue
                
            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    # Валюта находится внутри span с классом finca-badge
                    currency = cols[0].find('span', class_='finca-badge').get_text(strip=True)
                    buy = cols[1].get_text(strip=True)
                    sell = cols[2].get_text(strip=True)
                    
                    if currency and buy and sell:
                        all_data.append({
                            'bank_name': 'FINCA Bank',
                            'type': rate_type,
                            'currency': currency,
                            'buy': buy,
                            'sell': sell,
                            'date': today
                        })

        driver.quit()
        
        df = pd.DataFrame(all_data)
        if not df.empty:
            # Очистка данных
            df['buy'] = pd.to_numeric(df['buy'].str.replace(',', '.'), errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'].str.replace(',', '.'), errors='coerce')
            df = df.dropna(subset=['buy', 'sell'])
            
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"FINCA Bank Error: {e}")
        return pd.DataFrame()

# Тестирование
if __name__ == '__main__':
    print("Собираем данные FINCA Bank...")
    result = finca()
    if not result.empty:
        print(result.to_string(index=False))
    else:
        print("Данные не найдены.")