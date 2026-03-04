import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

def baitushum(url='https://www.baitushum.kg/ru/'):
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

        # Словарь вкладок: ID элемента -> Название типа для БД
        tabs = {
            "cash-tab": "Наличный",
            "cashless-tab": "Безналичный",
            "btb24-tab": "Мобильный банкинг"
        }

        for tab_id, rate_type in tabs.items():
            try:
                # Находим кнопку вкладки по ID и кликаем
                tab_button = driver.find_element(By.ID, tab_id)
                driver.execute_script("arguments[0].click();", tab_button)
                time.sleep(1) # Ждем переключения контента

                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # Ищем активную панель (она получает класс 'active' и 'show')
                # В HTML байтушума контент лежит в div с id, соответствующим aria-controls кнопки
                target_pane_id = tab_button.get_attribute('aria-controls')
                pane = soup.find('div', id=target_pane_id)
                
                if not pane:
                    continue

                # Извлекаем строки курсов (пропускаем заголовок 'head')
                rows = pane.find_all('li', class_='rate-li')
                for row in rows:
                    if 'head' in row.get('class', []):
                        continue
                    
                    name_div = row.find('div', class_='rate-col rate-name')
                    buy_div = row.find('div', class_='rate-col rate-buy')
                    sell_div = row.find('div', class_='rate-col rate-sell')

                    if name_div and buy_div and sell_div:
                        currency = name_div.get_text(strip=True).upper()
                        buy = buy_div.get_text(strip=True)
                        sell = sell_div.get_text(strip=True)

                        if currency and buy and sell:
                            all_data.append({
                                'bank_name': 'Бай-Тушум',
                                'type': rate_type,
                                'currency': currency,
                                'buy': buy,
                                'sell': sell,
                                'date': today
                            })
            except Exception as e:
                print(f"Baitushum Tab {tab_id} Error: {e}")

        driver.quit()
        
        df = pd.DataFrame(all_data)
        if not df.empty:
            # Очистка и приведение к числам
            df['buy'] = pd.to_numeric(df['buy'].str.replace(',', '.'), errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'].str.replace(',', '.'), errors='coerce')
            df = df.dropna(subset=['buy', 'sell'])
            
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"Baitushum Error: {e}")
        return pd.DataFrame()

# Тестирование
if __name__ == '__main__':
    print("Собираем данные Банка Бай-Тушум...")
    result = baitushum()
    if not result.empty:
        print(result.to_string(index=False))
    else:
        print("Данные не найдены.")