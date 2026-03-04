import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

def capital(url='https://www.capitalbank.kg/'):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        # Отключаем проверку SSL сертификата, так как иногда у локальных банков с этим проблемы
        response = requests.get(url, headers=headers, timeout=10, verify=False) 
        soup = BeautifulSoup(response.content, 'html.parser')
        
        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Функция для парсинга конкретной таблицы по ID её контейнера
        def parse_div_table(div_id, rate_type):
            container = soup.find('div', id=div_id)
            if not container:
                return
                
            table = container.find('table')
            if not table:
                return
                
            # Пропускаем первую строку (заголовки)
            rows = table.find_all('tr')[1:]
            
            for row in rows:
                cols = row.find_all('td')
                
                # Проверяем, что в строке достаточно колонок
                if len(cols) >= 5:
                    # Валюта обычно лежит во второй колонке в теге <strong>
                    currency_tag = cols[1].find('strong')
                    if not currency_tag:
                        continue
                        
                    currency = currency_tag.get_text(strip=True)
                    
                    # Покупка в 3-й колонке, Продажа в 5-й (или Учетный курс для НБКР)
                    buy_text = cols[2].get_text(strip=True)
                    sell_text = cols[4].get_text(strip=True)
                    
                    # Очищаем от тире и пробелов, если курс отсутствует
                    if buy_text == '-' or not buy_text:
                        buy_text = None
                    if sell_text == '-' or not sell_text:
                        sell_text = None
                        
                    # Для таблицы НБКР (div3) логика немного другая: покупка пустая, а продажа = Учетный курс
                    if div_id == 'div3':
                        buy_text = sell_text # У НБКР один курс, ставим его и в покупку, и в продажу
                        
                    if not buy_text and not sell_text:
                        continue

                    all_data.append({
                        'bank_name': 'Капитал',
                        'type': rate_type,
                        'currency': currency,
                        'buy': buy_text,
                        'sell': sell_text,
                        'date': today
                    })

        # Парсим три нужных блока
        parse_div_table('div1', 'Наличный')
        parse_div_table('div2', 'Безналичный')
        
        # Если в будущем захочешь выводить курсы НБКР по версии Капитал Банка
        # parse_div_table('div3', 'НБКР') 
        
        df = pd.DataFrame(all_data)
        
        if not df.empty:
            # Очищаем данные от лишних пробелов и приводим к float
            df['buy'] = pd.to_numeric(df['buy'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            
            # Удаляем строки, где нет ни покупки, ни продажи
            df = df.dropna(subset=['buy', 'sell'], how='all')

        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]

    except Exception as e:
        print(f"Capital Bank Error: {e}")
        return pd.DataFrame()

# Тестирование парсера напрямую
if __name__ == '__main__':
    # Скрываем предупреждения об отключенном SSL (verify=False)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    print("Собираем данные Capital Bank...")
    print(capital())