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

def dcb(url='https://www.dcb.kg/ru/'):
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.get(url)
        
        # Ждем загрузки контейнера с валютами
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'grid-currency'))
        )
        
        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        def extract_data(html, rate_type):
            soup = BeautifulSoup(html, 'html.parser')
            
            # Для золота отдельный контейнер
            if rate_type == 'Золото':
                container = soup.find('div', id='gold-currency-container')
            else:
                container = soup.find('div', id='regular-currency-container')
                
            if not container:
                return
                
            rows = container.find_all('div', class_='grid-currency grid-price')
            for row in rows:
                items = row.find_all('div', class_='grid-item')
                # Для валют часто скрывают одни цены и показывают другие (display-none),
                # поэтому берем просто текстовое содержимое, игнорируя пустые. 
                # У золота структура проще: 1 колонка - вес, 2 - покупка, 3 - продажа
                if len(items) >= 3:
                    raw_name = items[0].get_text(strip=True)
                    buy = items[1].get_text(strip=True)
                    sell = items[2].get_text(strip=True)
                    
                    if rate_type == 'Золото':
                        # Преобразуем "1 г", "31.1035 г" в формат "Золото 1 гр."
                        weight = raw_name.replace(' г', '').strip()
                        currency = f"Золото {weight} гр."
                    else:
                        currency = raw_name
                    
                    # Проверяем, что есть хоть какие-то данные для записи
                    if currency and (buy or sell):
                        all_data.append({
                            'bank_name': 'Дос-Кредобанк',
                            'type': rate_type,
                            'currency': currency,
                            'buy': buy,
                            'sell': sell,
                            'date': today
                        })

        # 1. Наличные (по умолчанию)
        extract_data(driver.page_source, 'Наличный')
        
        # 2. Безналичные
        try:
            beznal_tab = driver.find_element(By.ID, 'exchange-tab-2')
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", beznal_tab)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", beznal_tab)
            time.sleep(1.5) 
            
            extract_data(driver.page_source, 'Безналичный')
        except Exception as e:
            print(f"DCB Tab switch error (Beznal): {e}")

        # 3. Золото (Мерные слитки НБКР)
        try:
            gold_tab = driver.find_element(By.ID, 'exchange-tab-4')
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", gold_tab)
            time.sleep(0.5)
            driver.execute_script("arguments[0].click();", gold_tab)
            time.sleep(1.5) 
            
            extract_data(driver.page_source, 'Золото')
        except Exception as e:
            print(f"DCB Tab switch error (Gold): {e}")
            
        driver.quit()
        
        df = pd.DataFrame(all_data)
        if not df.empty:
            df['buy'] = pd.to_numeric(df['buy'].astype(str).str.replace(r'\s+', '', regex=True).str.replace(',', '.'), errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'].astype(str).str.replace(r'\s+', '', regex=True).str.replace(',', '.'), errors='coerce')
            df = df.dropna(subset=['buy', 'sell'])
            
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"DCB Error: {e}")
        return pd.DataFrame()

if __name__ == '__main__':
    print("Собираем данные Дос-Кредобанка...")
    print(dcb())