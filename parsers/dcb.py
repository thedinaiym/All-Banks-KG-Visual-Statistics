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
        
        # Ждем, пока загрузится блок с валютами
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'grid-currency'))
        )
        
        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        def extract_data(html, rate_type):
            soup = BeautifulSoup(html, 'html.parser')
            # Ищем контейнер с валютами
            container = soup.find('div', id='regular-currency-container')
            if not container:
                return
                
            # Ищем все строки с ценами
            rows = container.find_all('div', class_='grid-currency grid-price')
            for row in rows:
                items = row.find_all('div', class_='grid-item')
                # Проверяем, что есть все три колонки: Валюта, Покупка, Продажа
                if len(items) >= 3:
                    # get_text(strip=True) вытягивает текст даже если стоит display: none
                    currency = items[0].get_text(strip=True)
                    buy = items[1].get_text(strip=True)
                    sell = items[2].get_text(strip=True)
                    
                    if currency and buy and sell:
                        all_data.append({
                            'bank_name': 'Дос-Кредобанк',
                            'type': rate_type,
                            'currency': currency,
                            'buy': buy,
                            'sell': sell,
                            'date': today
                        })

        # 1. Наличные (открыты по умолчанию)
        extract_data(driver.page_source, 'Наличный')
        
        # 2. Кликаем на вкладку "Безналичный"
        try:
            beznal_tab = driver.find_element(By.ID, 'exchange-tab-2')
            # Скроллим до элемента, чтобы клик точно прошел
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", beznal_tab)
            time.sleep(0.5)
            # Кликаем через JS
            driver.execute_script("arguments[0].click();", beznal_tab)
            time.sleep(1.5) # Ждем, пока JS обновит курсы
            
            # Парсим безналичные
            extract_data(driver.page_source, 'Безналичный')
        except Exception as e:
            print(f"DCB Tab switch error: {e}")
            
        driver.quit()
        
        df = pd.DataFrame(all_data)
        if not df.empty:
            # Очищаем данные и превращаем их во float
            df['buy'] = pd.to_numeric(df['buy'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            df = df.dropna(subset=['buy', 'sell'])
            
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"DCB Error: {e}")
        return pd.DataFrame()

# Блок для отдельной проверки скрипта
if __name__ == '__main__':
    print("Собираем данные Дос-Кредобанка...")
    print(dcb())