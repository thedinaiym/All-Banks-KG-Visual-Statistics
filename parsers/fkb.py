import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fcb(url='https://www.fkb.kg/'):
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        all_data = []
        # Извлекаем дату с сайта, если она есть (в вашем HTML это 27.02.2026)
        date_span = soup.find('div', class_='pricing-switcher-wrap')
        today = date_span.get_text(strip=True) if date_span else datetime.now().strftime('%d.%m.%Y')

        # Находим все блоки с таблицами
        pricing_wraps = soup.find_all('div', class_='pricing-wrap')
        
        for wrap in pricing_wraps:
            title_h3 = wrap.find('h3')
            if not title_h3:
                continue
                
            title = title_h3.get_text(strip=True)
            
            # Определяем тип операции
            if "наличными" in title.lower():
                rate_type = "Наличный"
            elif "безналичные" in title.lower():
                rate_type = "Безналичный"
            elif "нбкр" in title.lower():
                rate_type = "НБКР"
            elif "металлы" in title.lower():
                rate_type = "Металлы"
            else:
                continue

            table = wrap.find('table')
            if not table:
                continue

            rows = table.find('tbody').find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                
                # Логика для валют (обычно 3 колонки: Валюта, Покупка, Продажа)
                if rate_type in ["Наличный", "Безналичный"] and len(cols) >= 3:
                    currency = cols[0].get_text(strip=True)
                    buy = cols[1].get_text(strip=True)
                    sell = cols[2].get_text(strip=True)
                    
                    if currency and (buy or sell):
                        all_data.append({
                            'bank_name': 'ФинансКредитБанк',
                            'type': rate_type,
                            'item': currency,
                            'buy': buy,
                            'sell': sell,
                            'date': today
                        })
                
                # Логика для НБКР (обычно 2 колонки: Валюта, Курс)
                elif rate_type == "НБКР" and len(cols) >= 2:
                    currency = cols[0].get_text(strip=True)
                    rate = cols[1].get_text(strip=True)
                    all_data.append({
                        'bank_name': 'ФинансКредитБанк',
                        'type': rate_type,
                        'item': currency,
                        'buy': rate,
                        'sell': rate,
                        'date': today
                    })

                # Логика для Металлов (Вид металла, Надбавка, Наценка)
                elif rate_type == "Металлы" and len(cols) >= 1:
                    metal_name = cols[0].get_text(strip=True)
                    # В вашем HTML значения пустые <td></td>, но структуру мы закладываем
                    buy_val = cols[1].get_text(strip=True) if len(cols) > 1 else "0"
                    sell_val = cols[2].get_text(strip=True) if len(cols) > 2 else "0"
                    
                    if metal_name:
                        all_data.append({
                            'bank_name': 'ФинансКредитBank',
                            'type': 'Металлы',
                            'item': metal_name,
                            'buy': buy_val,
                            'sell': sell_val,
                            'date': today
                        })

        df = pd.DataFrame(all_data)
        if not df.empty:
            # Очистка числовых данных
            for col in ['buy', 'sell']:
                df[col] = df[col].astype(str).str.replace(' ', '').str.replace(',', '.')
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Удаляем строки, где нет никаких цен
            df = df.dropna(subset=['buy', 'sell'], how='all')
            
        return df[['bank_name', 'type', 'item', 'buy', 'sell', 'date']]

    except Exception as e:
        print(f"FCB (FKB) Error: {e}")
        return pd.DataFrame()

if __name__ == '__main__':
    print("Собираем данные ФинансКредитБанка...")
    result = fcb()
    if not result.empty:
        print(result.to_string(index=False))
    else:
        print("Данные не найдены или таблицы пусты.")