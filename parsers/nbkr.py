import pandas as pd
import requests
from bs4 import BeautifulSoup

def nbkr(url='https://www.nbkr.kg/index1.jsp?item=2747&lang=RUS'):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        table = soup.find('table', attrs={'border': '1', 'width': '90%'})
        if not table:
            return pd.DataFrame()
            
        rows = table.find_all('tr')[1:] # Пропускаем строку с заголовками
        
        data = []
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 4:
                data.append({
                    'date': cols[0].get_text(strip=True),
                    'item': cols[1].get_text(strip=True),
                    'buy': cols[2].get_text(strip=True),
                    'sell': cols[3].get_text(strip=True),
                    'bank_name': 'НБКР',
                    'type': 'Золото'
                })
                
        df = pd.DataFrame(data)
        if df.empty:
            return pd.DataFrame()
            
        # Очищаем данные от пробелов для аналитики
        df['buy'] = df['buy'].str.replace(' ', '').str.replace(',', '.').astype(float)
        df['sell'] = df['sell'].str.replace(' ', '').str.replace(',', '.').astype(float)
        
        return df[['bank_name', 'type', 'item', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"NBKR Error: {e}")
        return pd.DataFrame()