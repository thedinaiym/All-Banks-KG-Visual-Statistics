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

def bank_asia(url='https://www.ab.kg/'):
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

        # 1. Парсим ВАЛЮТЫ (Наличные, Безналичные, НБКР)
        # Находим табы в левой части
        currency_tabs = driver.find_elements(By.CSS_SELECTOR, ".course__left .tabs-descr__caption li")
        currency_contents = driver.find_elements(By.CSS_SELECTOR, ".course__left .tabs-descr__content")
        
        tab_names = ["Наличный", "Безналичный", "НБКР"]

        for i in range(len(tab_names)):
            try:
                # Кликаем по табу
                driver.execute_script("arguments[0].click();", currency_tabs[i])
                time.sleep(1) # Ждем анимацию переключения
                
                soup = BeautifulSoup(currency_contents[i].get_attribute('innerHTML'), 'html.parser')
                table = soup.find('table', class_='course__table')
                if not table: continue
                
                rows = table.find('tbody').find_all('tr')
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 3:
                        # Извлекаем код валюты (USD, EUR...)
                        currency = row.find('span', class_='course__name').get_text(strip=True)
                        buy = cols[1].get_text(strip=True)
                        sell = cols[2].get_text(strip=True)
                        
                        all_data.append({
                            'bank_name': 'Азия Банк',
                            'type': tab_names[i],
                            'item': currency,
                            'buy': buy,
                            'sell': sell,
                            'date': today
                        })
            except Exception as e:
                print(f"Aiyl Bank Currency Tab {i} Error: {e}")

        # 2. Парсим МЕТАЛЛЫ
        try:
            # Находим секцию металлов (правая колонка)
            metal_content = driver.find_element(By.CSS_SELECTOR, ".course__right .tabs-descr__content.act")
            soup_metals = BeautifulSoup(metal_content.get_attribute('innerHTML'), 'html.parser')
            metal_table = soup_metals.find('table', class_='course__table')
            
            if metal_table:
                m_rows = metal_table.find('tbody').find_all('tr')
                for m_row in m_rows:
                    m_cols = m_row.find_all('td')
                    if len(m_cols) >= 3:
                        metal_name = m_row.find('span', class_='course__name').get_text(strip=True)
                        m_buy = m_cols[1].get_text(strip=True)
                        m_sell = m_cols[2].get_text(strip=True)
                        
                        all_data.append({
                            'bank_name': 'Азия Банк',
                            'type': 'Металлы',
                            'item': metal_name,
                            'buy': m_buy,
                            'sell': m_sell,
                            'date': today
                        })
        except Exception as e:
            print(f"Aiyl Bank Metals Error: {e}")

        driver.quit()
        
        df = pd.DataFrame(all_data)
        if not df.empty:
            # Чистим числа (убираем пробелы, меняем запятые)
            for col in ['buy', 'sell']:
                df[col] = df[col].astype(str).str.replace(r'\s+', '', regex=True).str.replace(',', '.')
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.dropna(subset=['buy', 'sell'])
            
        return df[['bank_name', 'type', 'item', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"Aiyl Bank Main Error: {e}")
        return pd.DataFrame()

if __name__ == '__main__':
    print("Собираем данные Aiyl Bank...")
    print(bank_asia())