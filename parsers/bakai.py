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
from selenium.webdriver.support.ui import Select
import time

def bakai(url='https://bakai.kg/ru/'): # Добавил /ru/ на всякий случай
    try:
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.get(url)
        
        # Ждем, пока загрузится виджет с валютами
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'select'))
        )
        
        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        def extract_table(html, rate_type):
            soup = BeautifulSoup(html, 'html.parser')
            # Ищем таблицу внутри виджета
            widget = soup.find('div', class_=lambda c: c and 'CurrencyWidget_table_content' in c)
            if not widget:
                return
                
            table = widget.find('table')
            if not table:
                return
                
            tbody = table.find('tbody')
            if not tbody:
                return
                
            rows = tbody.find_all('tr')
            for row in rows:
                cols = row.find_all('th') # У Бакай Банка в tbody почему-то теги <th> вместо <td>
                if len(cols) >= 3:
                    # Валюта лежит в alt-атрибуте картинки в первой колонке
                    img_tag = cols[0].find('img')
                    if img_tag and 'alt' in img_tag.attrs:
                        currency = img_tag['alt']
                    else:
                        continue # Если нет картинки с валютой, пропускаем
                        
                    # В колонках с цифрами тоже есть картинки (стрелочки вверх/вниз), берем только текст
                    buy = cols[1].get_text(strip=True)
                    sell = cols[2].get_text(strip=True)
                    
                    if currency and buy and sell:
                        all_data.append({
                            'bank_name': 'Бакай',
                            'type': rate_type,
                            'currency': currency,
                            'buy': buy,
                            'sell': sell,
                            'date': today
                        })

        # Находим dropdown элемент
        dropdown_element = driver.find_element(By.TAG_NAME, 'select')
        select = Select(dropdown_element)
        
        # 1. Выбираем "Наличные" и парсим
        try:
            select.select_by_value('cash')
            time.sleep(1) # Ждем пока React обновит таблицу
            extract_table(driver.page_source, 'Наличный')
        except Exception as e:
            print(f"Bakai cash error: {e}")
            
        # 2. Выбираем "Безналичные" и парсим
        try:
            select.select_by_value('non_cash')
            time.sleep(1)
            extract_table(driver.page_source, 'Безналичный')
        except Exception as e:
            print(f"Bakai non_cash error: {e}")
            
        driver.quit()
        
        df = pd.DataFrame(all_data)
        if not df.empty:
            df['buy'] = pd.to_numeric(df['buy'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            df = df.dropna(subset=['buy', 'sell'])
            
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"Bakai Error: {e}")
        return pd.DataFrame()

if __name__ == '__main__':
    print("Собираем данные Бакай Банка...")
    print(bakai())