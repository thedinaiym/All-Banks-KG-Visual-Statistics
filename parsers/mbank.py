import pandas as pd
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import json 

def mbank(url='https://mbank.kg/'):
    try:
        response = requests.get(url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        script_tag = soup.find('script', {'id': '__NEXT_DATA__', 'type': 'application/json'})
        
        if not script_tag:
            return pd.DataFrame()
        
        data = json.loads(script_tag.string)
        exchange_info = data['props']['pageProps']['mainPage']['exchange']
        cash_exchange = exchange_info.get('cash_exchange', [])

        cash_exchange_dfs = []
        for item in cash_exchange:
            df = pd.DataFrame(item['values'])
            df['type'] = item['operation_type']
            cash_exchange_dfs.append(df)
        
        if not cash_exchange_dfs:
            return pd.DataFrame()

        cash_exchange_df = pd.concat(cash_exchange_dfs, ignore_index=True)
        cash_exchange_df['bank_name'] = 'Кыргызстан' # MBank = Банк Кыргызстан
        cash_exchange_df['date'] = datetime.now().strftime('%Y-%m-%d')

        # Приводим типы к единому стандарту
        cash_exchange_df['type'] = cash_exchange_df['type'].replace(
            {'Для операций с наличными': 'Наличный', 'Безналичные курсы': 'Безналичный'}
        )

        # Оставляем только нужные колонки
        if 'id' in cash_exchange_df.columns:
            cash_exchange_df = cash_exchange_df.drop(columns=['id'])
        if 'nbkr' in cash_exchange_df.columns:
            cash_exchange_df = cash_exchange_df.drop(columns=['nbkr'])
            
        return cash_exchange_df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]

    except Exception as e:
        print(f"MBank Error: {e}")
        return pd.DataFrame()