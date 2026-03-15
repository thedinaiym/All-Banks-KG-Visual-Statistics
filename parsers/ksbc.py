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

def ksbc(url='https://ksbc.kg/'):
    try:
        # Запускаем скрытый браузер
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.get(url)
        
        # Ждем максимум 10 секунд, пока JS отрисует таблицы с классом currency-box__table
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, 'currency-box__table'))
        )
        
        # Забираем уже полностью прогруженный HTML
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Закрываем браузер, он нам больше не нужен
        driver.quit()
        
        tables = soup.find_all('table', class_='currency-box__table')
        
        if len(tables) < 2:
            return pd.DataFrame()
            
        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Внутренняя функция для обычных валют
        def parse_table(table, rate_type):
            # Ищем сразу 'tr', без 'tbody' — так надежнее, избегаем ошибок NoneType
            rows = table.find_all('tr')[1:] 
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    currency = cols[0].get_text(strip=True)
                    buy = cols[1].get_text(strip=True)
                    sell = cols[2].get_text(strip=True)
                    
                    if not buy or not sell or buy == '#REF!' or sell == '#REF!':
                        continue
                        
                    all_data.append({
                        'bank_name': 'КСБ Банк',
                        'type': rate_type,
                        'currency': currency,
                        'buy': buy,
                        'sell': sell,
                        'date': today
                    })

        # Первая таблица — Наличные
        if len(tables) >= 1:
            parse_table(tables[0], 'Наличный')
            
        # Вторая таблица — Безналичные
        if len(tables) >= 2:
            parse_table(tables[1], 'Безналичный')

        # Поиск и парсинг таблицы с золотом (Слитки)
        for table in tables:
            # Ищем заголовки таблицы, чтобы понять, что это металлы
            headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
            if any('вес' in h or 'грамм' in h for h in headers):
                rows = table.find_all('tr')[1:]
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 3:
                        weight_text = cols[0].get_text(strip=True) # например, "1 гр.", "31,1035 гр."
                        buy = cols[1].get_text(strip=True)
                        sell = cols[2].get_text(strip=True)
                        
                        if not buy or not sell or buy == '-' or sell == '-':
                            continue
                            
                        item_name = f"Золото {weight_text}"
                        
                        all_data.append({
                            'bank_name': 'КСБ Банк',
                            'type': 'Золото', # Помечаем тип, чтобы отправить в нужную таблицу БД
                            'currency': item_name,
                            'buy': buy,
                            'sell': sell,
                            'date': today
                        })
                break # Таблица с золотом найдена и распарсена, остальные можно не смотреть
            
        df = pd.DataFrame(all_data)
        if not df.empty:
            # Используем regex=True для \s+ чтобы надежно удалять неразрывные пробелы
            df['buy'] = pd.to_numeric(df['buy'].astype(str).str.replace(r'\s+', '', regex=True).str.replace(',', '.'), errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'].astype(str).str.replace(r'\s+', '', regex=True).str.replace(',', '.'), errors='coerce')
            df = df.dropna(subset=['buy', 'sell'])
            
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"KSBC Error: {e}")
        return pd.DataFrame()

if __name__ == '__main__':
    print("Собираем данные КСБ Банка...")
    print(ksbc())