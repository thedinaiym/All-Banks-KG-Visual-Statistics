import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

def keremet(url='https://keremetbank.kg/'):
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

        # Словарь соответствия ID вкладок и типов
        tabs = {
            "rosin": "Наличный",
            "rosin_beznal": "Безналичный",
            "nbkr": "НБКР"
        }

        for tab_id, rate_type in tabs.items():
            try:
                # Находим кнопку переключения вкладки и кликаем
                tab_link = driver.find_element(By.XPATH, f"//a[@href='#{tab_id}']")
                driver.execute_script("arguments[0].click();", tab_link)
                time.sleep(1.5) # Ждем подгрузку/переключение

                soup = BeautifulSoup(driver.page_source, 'html.parser')
                tab_pane = soup.find('div', id=tab_id)
                
                if not tab_pane:
                    continue

                table = tab_pane.find('table', class_='course_table')
                if not table:
                    continue

                rows = table.find('tbody').find_all('tr')
                for row in rows:
                    cols = row.find_all('td')
                    
                    # Для НБКР в таблице 2 колонки, для остальных - 3
                    if rate_type == "НБКР" and len(cols) >= 2:
                        item = cols[0].get_text(strip=True)
                        value = cols[1].get_text(strip=True)
                        buy = sell = value
                    elif len(cols) >= 3:
                        item = cols[0].get_text(strip=True)
                        buy = cols[1].get_text(strip=True)
                        sell = cols[2].get_text(strip=True)
                    else:
                        continue

                    # Если это "Алтын", помечаем тип как Золото
                    final_type = "Золото" if "алтын" in item.lower() else rate_type

                    if item and buy and sell:
                        all_data.append({
                            'bank_name': 'Керемет Банк',
                            'type': final_type,
                            'item': item,
                            'buy': buy,
                            'sell': sell,
                            'date': today
                        })
            except Exception as e:
                print(f"Keremet Bank Tab {tab_id} Error: {e}")

        driver.quit()
        
        df = pd.DataFrame(all_data)
        if not df.empty:
            # Очистка числовых данных
            for col in ['buy', 'sell']:
                df[col] = df[col].astype(str).str.replace(r'\s+', '', regex=True).str.replace(',', '.')
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Убираем строки с нулевыми курсами (как "Алтын" 0.0000 в примере)
            df = df[(df['buy'] > 0) | (df['sell'] > 0)]
            
        return df[['bank_name', 'type', 'item', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"Keremet Bank Error: {e}")
        return pd.DataFrame()

if __name__ == '__main__':
    print("Собираем данные Керемет Банка...")
    result = keremet()
    if not result.empty:
        print(result.to_string(index=False))
    else:
        print("Данные не найдены.")