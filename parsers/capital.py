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
        response = requests.get(url, headers=headers, timeout=10, verify=False) 
        soup = BeautifulSoup(response.content, 'html.parser')
        
        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        def parse_div_table(div_id, rate_type):
            container = soup.find('div', id=div_id)
            if not container:
                return
                
            table = container.find('table')
            if not table:
                return
                
            rows = table.find_all('tr')[1:]
            
            for row in rows:
                cols = row.find_all('td')
                
                if len(cols) >= 5:
                    currency_tag = cols[1].find('strong')
                    if not currency_tag:
                        continue
                        
                    currency = currency_tag.get_text(strip=True)
                    
                    buy_text = cols[2].get_text(strip=True)
                    sell_text = cols[4].get_text(strip=True)
                    
                    if buy_text == '-' or not buy_text:
                        buy_text = None
                    if sell_text == '-' or not sell_text:
                        sell_text = None
                        
                    if div_id == 'div3':
                        buy_text = sell_text 
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

        parse_div_table('div1', 'Наличный')
        parse_div_table('div2', 'Безналичный')
        
        df = pd.DataFrame(all_data)
        
        if not df.empty:
            
            df['buy'] = pd.to_numeric(df['buy'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            
            df = df.dropna(subset=['buy', 'sell'], how='all')

        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]

    except Exception as e:
        print(f"Capital Bank Error: {e}")
        return pd.DataFrame()

if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    print("Собираем данные Capital Bank...")
    print(capital())