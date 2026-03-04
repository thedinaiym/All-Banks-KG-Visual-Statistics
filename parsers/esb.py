import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime

def esb(url='https://esb.kg/'):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        # verify=False на всякий случай для локальных банков
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Находим контейнер со всеми вкладками (у него id wk-549)
        switcher = soup.find('ul', id='wk-549')
        if not switcher:
            return pd.DataFrame()
            
        # Находим все вкладки (<li>) внутри свитчера
        tabs = switcher.find_all('li', recursive=False)
        
        # Функция для парсинга отдельной таблицы
        def parse_table(tab_content, rate_type):
            table = tab_content.find('table')
            if not table:
                return
                
            # Ищем все строки в tbody
            tbody = table.find('tbody')
            if not tbody:
                return
                
            rows = tbody.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                
                # В таблице ESB 5 колонок: [0]Картинка, [1]Валюта, [2]Покупка, [3]Тире, [4]Продажа
                if len(cols) >= 5:
                    currency = cols[1].get_text(strip=True)
                    buy = cols[2].get_text(strip=True)
                    sell = cols[4].get_text(strip=True)
                    
                    if currency and buy and sell:
                        all_data.append({
                            'bank_name': 'ЕСБ',
                            'type': rate_type,
                            'currency': currency,
                            'buy': buy,
                            'sell': sell,
                            'date': today
                        })

        # 1. Первая вкладка (index 0) — Наличные
        if len(tabs) >= 1:
            parse_table(tabs[0], 'Наличный')
            
        # 2. Вторая вкладка (index 1) — Безналичные
        if len(tabs) >= 2:
            parse_table(tabs[1], 'Безналичный')
            
        # (Третья вкладка - это слитки, пока ее пропускаем, так как там другая структура таблицы: Масса, Покупка, Продажа)
        
        df = pd.DataFrame(all_data)
        
        if not df.empty:
            # Очищаем данные от мусора. 
            # В ESB часто используют запятую вместо точки для десятичных дробей (например, 87,30)
            df['buy'] = df['buy'].astype(str).str.replace(' ', '').str.replace(',', '.')
            df['sell'] = df['sell'].astype(str).str.replace(' ', '').str.replace(',', '.')
            
            # Конвертируем в числа
            df['buy'] = pd.to_numeric(df['buy'], errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'], errors='coerce')
            
            # Удаляем "битые" строки
            df = df.dropna(subset=['buy', 'sell'])
            
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"ESB Error: {e}")
        return pd.DataFrame()

# Блок для отдельной проверки скрипта
if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    print("Собираем данные Евразийского Сберегательного Банка...")
    print(esb())