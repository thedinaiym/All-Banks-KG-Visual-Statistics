import pandas as pd
import requests
from bs4 import BeautifulSoup

def kyrgyz_altyn(url='https://ru.kyrgyzaltyn.kg/gold_bars/'):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        tables = soup.find_all('table', {'border': '1', 'cellpadding': '0', 'cellspacing': '0'})
        
        if len(tables) < 2:
            return pd.DataFrame()
            
        price_table = tables[1]
        rows = price_table.find_all('tr')
        
        data = []
        for row in rows[1:]:
            cols = row.find_all('td')
            if len(cols) == 4:
                data.append({
                    'date': cols[0].get_text(strip=True),
                    'item': cols[1].get_text(strip=True),  # Вес слитка
                    'buy': cols[2].get_text(strip=True),   # Цена выкупа
                    'sell': cols[3].get_text(strip=True),  # Цена продажи
                    'bank_name': 'Кыргызалтын',
                    'type': 'Золото'
                })
        
        df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame()
            
        # Очищаем данные от пробелов и приводим к числам для графиков
        df['buy'] = df['buy'].str.replace(' ', '').str.replace(',', '.').astype(float)
        df['sell'] = df['sell'].str.replace(' ', '').str.replace(',', '.').astype(float)
        
        return df[['bank_name', 'type', 'item', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"Kyrgyz Altyn Error: {e}")
        return pd.DataFrame()