import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime

def optima(url='https://www.optimabank.kg/index.php?option=com_nbrates&view=default&lang=ru', date=None):
    if not date:
        date = datetime.now().strftime('%Y-%m-%d')
        
    form_data = {
        'option': 'com_nbrates',
        'view': 'default',
        'Itemid': '196',
        'mycalendar': date
    }
    
    all_data = []
    try:
        response = requests.post(url, data=form_data, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Наличные
        cash_tab = soup.find('div', {'id': 'tab-cash'})
        if cash_tab:
            rows = cash_tab.find_all('div', class_=['row0', 'row1'])
            for row in rows:
                currency = row.find('div', class_='code').text.strip()
                buy_rate = row.find('div', class_='rate buy').text.strip()
                sell_rate = row.find('div', class_='rate sell').text.strip()
                all_data.append({'date': date, 'currency': currency, 'buy': buy_rate, 'sell': sell_rate, 'type': 'Наличный'})
        
        # Безналичные
        cashless_tab = soup.find('div', {'id': 'tab-cashless'})
        if cashless_tab:
            rows = cashless_tab.find_all('div', class_=['row0', 'row1'])
            for row in rows:
                currency = row.find('div', class_='code').text.strip()
                buy_rate = row.find('div', class_='rate buy').text.strip()
                sell_rate = row.find('div', class_='rate sell').text.strip()
                all_data.append({'date': date, 'currency': currency, 'buy': buy_rate, 'sell': sell_rate, 'type': 'Безналичный'})
        
        df = pd.DataFrame(all_data)
        if df.empty:
            return pd.DataFrame()
            
        df['bank_name'] = 'Оптима'
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]
    
    except Exception as e:
        print(f"Optima Error: {e}")
        return pd.DataFrame()