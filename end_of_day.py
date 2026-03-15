"""
end_of_day.py — Скрипт закрытия дня.
Переносит данные из текущих таблиц в исторические и очищает текущие.
"""

import os
import sys
import logging
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

def get_supabase() -> Client:
    url = os.environ.get("Project_URL")
    key = os.environ.get("Publishable_API_Key")
    if not url or not key:
        raise EnvironmentError("Переменные Project_URL / Publishable_API_Key не найдены")
    return create_client(url, key)

def move_to_history(source_table: str, hist_table: str):
    sb = get_supabase()
    
    # 1. Забираем все данные из текущей таблицы
    log.info(f"Читаем данные из {source_table}...")
    res = sb.table(source_table).select("*").execute()
    data = res.data
    
    if not data:
        log.info(f"  └ Таблица {source_table} пуста, переносить нечего.")
        return

    log.info(f"  └ Найдено {len(data)} записей. Переносим в {hist_table}...")

    # 2. Удаляем ID, чтобы историческая таблица сгенерировала свои
    for row in data:
        if 'id' in row:
            del row['id']
            
    # 3. Вставляем в историю
    sb.table(hist_table).insert(data).execute()
    log.info(f"  └ Успешно скопировано в {hist_table}.")

    # 4. Очищаем текущую таблицу по датам, которые перенесли
    dates = list(set([row['date'] for row in data]))
    for d in dates:
        sb.table(source_table).delete().eq("date", d).execute()
    
    log.info(f"  └ Текущая таблица {source_table} очищена от перенесенных данных.")

def main():
    log.info("=== Запуск процедуры закрытия дня ===")
    try:
        move_to_history("exchange_rates", "historical_exchange_rates")
        move_to_history("gold_rates", "historical_gold_rates")
        log.info("=== Процедура успешно завершена ===")
    except Exception as e:
        log.error(f"❌ Ошибка при переносе данных: {e}")

if __name__ == "__main__":
    main()