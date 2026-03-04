import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime

def eib(url='https://eib.kg/'):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        # Отключаем проверку SSL на всякий случай
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        all_data = []
        today = datetime.now().strftime('%Y-%m-%d')
        
        def parse_panel(panel_class, rate_type):
            panel = soup.find('div', class_=panel_class)
            if not panel:
                return
            
            table = panel.find('div', class_='table')
            if not table:
                return
                
            # Ищем все строки (div с классом row), пропускаем первую (заголовки)
            rows = table.find_all('div', class_='row')[1:]
            
            for row in rows:
                cells = row.find_all('span', class_='cell')
                if len(cells) >= 3:
                    currency = cells[0].get_text(strip=True)
                    buy = cells[1].get_text(strip=True)
                    sell = cells[2].get_text(strip=True)
                    
                    if currency and buy and sell:
                        all_data.append({
                            'bank_name': 'ЭкоИсламик',
                            'type': rate_type,
                            'currency': currency,
                            'buy': buy,
                            'sell': sell,
                            'date': today
                        })

        # Ищем блок с наличными (имеет класс kursval-nal)
        parse_panel('kursval-nal', 'Наличный')
        
        # Ищем блок с безналичными (имеет класс kursval-beznal)
        parse_panel('kursval-beznal', 'Безналичный')
        
        df = pd.DataFrame(all_data)
        
        if not df.empty:
            # Очищаем от пробелов и превращаем во float
            df['buy'] = pd.to_numeric(df['buy'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            df['sell'] = pd.to_numeric(df['sell'].astype(str).str.replace(' ', '').str.replace(',', '.'), errors='coerce')
            
            # Удаляем строки с пустыми значениями
            df = df.dropna(subset=['buy', 'sell'])
            
        return df[['bank_name', 'type', 'currency', 'buy', 'sell', 'date']]
        
    except Exception as e:
        print(f"EIB Error: {e}")
        return pd.DataFrame()

# Блок для отдельной проверки скрипта
if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    print("Собираем данные ЭкоИсламикБанка...")
    print(eib())