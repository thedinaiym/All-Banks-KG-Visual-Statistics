import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime

def tolubay(url='https://www.tolubaybank.kg/index.php?option=com_nbrates&view=default&Itemid=131&lang=ru'):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        # verify=False отключает строгую проверку SSL (часто спасает от ошибок на региональных сайтах)
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Все таблицы лежат внутри тегов <dd class="tabs">
        tabs = soup.find_all('dd', class_='tabs')
        
        if len(tabs) < 2:
            return pd.DataFrame()
            
        def parse_table(tab, rate_type):
            table = tab.find('table', class_='currency_table')
            if not table:
                return
                
            # Ищем все строки таблицы внутри tbody
            tbody = table.find('tbody')
            if not tbody:
                return
                
            rows = tbody.find_all('tr')
            for row in rows:
                # Пропускаем строку со временем (у нее класс row-time)
                if 'row-time' in row.get('class', []):
                    continue
                    
                cols = row.find_all('td')
                if len(cols) >= 3:
                    currency = cols[0].get_text(strip=True)
                    buy = cols[1].get_text(strip=True)
                    sell = cols[2].get_text(strip=True)
                    
                    if currency and buy and sell:
                        all_data.append({
                            'bank_name': 'Толубай',
                            'type': rate_type,
                            'currency': currency,
                            'buy': buy,
                            'sell': sell,
                            'date': today
                        })

        # 1-я вкладка — Наличные, 2-я — Безналичные
        if len(tabs) >= 1:
            parse_table(tabs[0], 'Наличный')
        if len(tabs) >= 2:
            parse_table(tabs[1], 'Безналичный')
            
        df = pd.DataFrame(all_data)
        
        if not df.empty:
            # Очищаем курсы и переводим в числа
            df['buy'] = pd.to_numeric(df['buy'].str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'].str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            
            # Удаляем пустые строки
            df = df.dropna(subset=['buy', 'sell'])
            
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"Tolubay Error: {e}")
        return pd.DataFrame()

# Блок для отдельной проверки скрипта
if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    print("Собираем данные Tolubay Bank...")
    print(tolubay())