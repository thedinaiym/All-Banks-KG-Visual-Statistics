import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time

def kompanion(url='https://www.kompanion.kg/ru/kursy/'):
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

        # Типы курсов для парсинга
        # Ищем кнопки по тексту внутри контейнера переключателя
        rate_types = {
            "Наличные": "Наличный",
            "Безналичные": "Безналичный"
        }

        for btn_text, internal_name in rate_types.items():
            try:
                # Находим кнопку переключения (Наличные/Безналичные)
                xpath = f"//button[contains(text(), '{btn_text}')]"
                button = driver.find_element(By.XPATH, xpath)
                driver.execute_script("arguments[0].click();", button)
                time.sleep(1.5) # Ждем рендера таблицы

                soup = BeautifulSoup(driver.page_source, 'html.parser')
                
                # Таблица в Компаньоне реализована через flex-row div-ы, а не стандартный <table>
                # Ищем контейнер с данными (серый блок)
                container = soup.find('div', class_='rounded-[24px] bg-[#F6F8F9]')
                if not container:
                    continue

                # Каждая строка курса — это div с border-b-[1px]
                rows = container.find_all('div', class_='flex flex-row flex-nowrap items-center justify-between')
                
                for row in rows:
                    cols = row.find_all('p')
                    # В верстке: [0] Валюта (текст), [1] Наименование, [2] Покупка, [3] Продажа
                    if len(cols) >= 4:
                        currency = cols[0].get_text(strip=True)
                        buy = cols[2].get_text(strip=True)
                        sell = cols[3].get_text(strip=True)

                        if currency and buy and sell:
                            all_data.append({
                                'bank_name': 'Компаньон',
                                'type': internal_name,
                                'currency': currency,
                                'buy': buy,
                                'sell': sell,
                                'date': today
                            })
            except Exception as e:
                print(f"Kompanion Tab {btn_text} Error: {e}")

        driver.quit()
        
        df = pd.DataFrame(all_data)
        if not df.empty:
            # Очистка данных (удаление пробелов и замена запятых на точки)
            for col in ['buy', 'sell']:
                df[col] = df[col].astype(str).str.replace(r'\s+', '', regex=True).str.replace(',', '.')
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.dropna(subset=['buy', 'sell'])
            
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"Kompanion Main Error: {e}")
        return pd.DataFrame()

# Тестирование
if __name__ == '__main__':
    print("Собираем данные Банка Компаньон...")
    result = kompanion()
    if not result.empty:
        print(result.to_string(index=False))
    else:
        print("Данные не найдены.")