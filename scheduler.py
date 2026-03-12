"""
scheduler.py — Парсер курсов валют банков КР → Supabase

Использование:
  python scheduler.py           # однократный запуск (GitHub Actions)
  python scheduler.py --daemon  # режим демона, каждые 30 минут

SQL для Supabase (выполнить один раз):
─────────────────────────────────────────────────────────────────────
CREATE TABLE exchange_rates (
    id          BIGSERIAL PRIMARY KEY,
    bank_name   TEXT    NOT NULL,
    type        TEXT    NOT NULL,
    item        TEXT    NOT NULL,
    buy         NUMERIC,
    sell        NUMERIC,
    date        DATE    NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (bank_name, type, item, date)
);

CREATE TABLE gold_rates (
    id          BIGSERIAL PRIMARY KEY,
    bank_name   TEXT    NOT NULL,
    type        TEXT    NOT NULL,
    item        TEXT    NOT NULL,
    buy         NUMERIC,
    sell        NUMERIC,
    date        DATE    NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (bank_name, item, date)
);

CREATE INDEX idx_exchange_date ON exchange_rates(date);
CREATE INDEX idx_gold_date     ON gold_rates(date);
─────────────────────────────────────────────────────────────────────
"""

import sys
import os
import logging
from datetime import datetime

import pandas as pd
import schedule
import time
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

# ─── Логгирование ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ─── Пути ─────────────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# ─── Импорт парсеров ──────────────────────────────────────────────────────────
# Валютные парсеры
from parsers.ab          import bank_asia  as parse_ab
from parsers.baitushum   import baitushum  as parse_baitushum
from parsers.bakai       import bakai      as parse_bakai
from parsers.bank_asia   import bank_asia  as parse_bank_asia
from parsers.capital     import capital    as parse_capital
from parsers.dcb         import dcb        as parse_dcb
from parsers.demir       import demir      as parse_demir
from parsers.eib         import eib        as parse_eib
from parsers.eldik       import eldik      as parse_eldik
from parsers.esb         import esb        as parse_esb
from parsers.finka       import finca      as parse_finca
from parsers.fkb         import fcb        as parse_fcb
from parsers.keremet     import keremet    as parse_keremet
from parsers.kicb        import kicb       as parse_kicb
from parsers.kkb         import kkb        as parse_kkb
from parsers.kompanion   import kompanion  as parse_kompanion
from parsers.ksbc        import ksbc       as parse_ksbc
from parsers.mbank       import mbank      as parse_mbank
from parsers.obank       import obank      as parse_obank
from parsers.optima      import optima     as parse_optima
from parsers.tolubay     import tolubay    as parse_tolubay

# Золото
from parsers.nbkr        import nbkr          as parse_nbkr
from parsers.kyrgyz_altyn import kyrgyz_altyn as parse_kyrgyz_altyn

# ─── Список парсеров ──────────────────────────────────────────────────────────
# (display_name, callable_or_None)  None = специальный вызов
CURRENCY_PARSERS: list[tuple[str, object]] = [
    ("Айыл Банк",        parse_ab),
    ("Бай-Тушум",        parse_baitushum),
    ("Бакай Банк",       parse_bakai),
    ("Банк Азии",        parse_bank_asia),
    ("Капитал Банк",     parse_capital),
    ("Дос-Кредобанк",    parse_dcb),
    ("Демир Банк",       parse_demir),
    ("ЭкоИсламикБанк",   parse_eib),
    ("Элдик Банк",       parse_eldik),
    ("ЕСБ",              parse_esb),
    ("FINCA Bank",       parse_finca),
    ("ФинансКредитБанк", parse_fcb),
    ("Керемет Банк",     parse_keremet),   # фильтруем золото ниже
    ("KICB",             parse_kicb),
    ("Кыргызкоммерц",    parse_kkb),
    ("Компаньон",        parse_kompanion),
    ("КСБ Банк",         parse_ksbc),
    ("MBank",            parse_mbank),
    ("O!Bank",           parse_obank),
    ("Оптима Банк",      None),            # нужен параметр date
    ("Толубай Банк",     parse_tolubay),
]

GOLD_PARSERS: list[tuple[str, object]] = [
    ("НБКР",         parse_nbkr),
    ("Кыргызалтын",  parse_kyrgyz_altyn),
]

# Типы, которые считаются золотом/металлами (идут в gold_rates)
GOLD_TYPES = {"Золото", "Металлы", "Серебро", "Платина"}


# ─── Вспомогательные функции ──────────────────────────────────────────────────
def get_supabase() -> Client:
    url = os.environ.get("Project_URL")
    key = os.environ.get("Publishable_API_Key")
    if not url or not key:
        raise EnvironmentError("Переменные Project_URL / Publishable_API_Key не найдены")
    return create_client(url, key)


def normalize(df: pd.DataFrame, bank_name: str, today: str) -> pd.DataFrame:
    """Привести df к стандартным колонкам [bank_name, type, item, buy, sell, date]."""
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()

    # currency → item
    if "currency" in df.columns and "item" not in df.columns:
        df = df.rename(columns={"currency": "item"})

    required = {"type", "item", "buy", "sell"}
    if not required.issubset(df.columns):
        log.warning(f"  {bank_name}: отсутствуют колонки {required - set(df.columns)}")
        return pd.DataFrame()

    df["bank_name"] = bank_name
    df["item"]      = df["item"].astype(str).str.strip().str.upper()
    df["buy"]       = pd.to_numeric(df["buy"],  errors="coerce")
    df["sell"]      = pd.to_numeric(df["sell"], errors="coerce")
    df              = df.dropna(subset=["buy", "sell"])

    # Если в данных нет даты — подставляем сегодня
    if "date" not in df.columns:
        df["date"] = today

    # Конвертируем дату в ISO YYYY-MM-DD.
    # Кыргызалтын и некоторые другие парсеры отдают DD.MM.YYYY —
    # Supabase (тип DATE) принимает только ISO формат.
    def _to_iso(val: str) -> str:
        val = str(val).strip()
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(val, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return today  # fallback: не смогли распарсить — берём сегодня

    df["date"] = df["date"].apply(_to_iso)

    return df[["bank_name", "type", "item", "buy", "sell", "date"]]


# ✅ СТАЛО
def upsert(df: pd.DataFrame, table: str, conflict: str) -> None:
    if df.empty:
        return
    sb = get_supabase()
    df = df.copy()

    # Дедупликация — убираем дубли по ключевым полям внутри батча
    conflict_cols = [c.strip() for c in conflict.split(",")]
    df = df.drop_duplicates(subset=conflict_cols, keep="last")

    df["created_at"] = datetime.now().isoformat()
    records = df.where(pd.notnull(df), None).to_dict(orient="records")
    sb.table(table).upsert(records, on_conflict=conflict).execute()
    log.info(f"  💾 {table}: сохранено {len(records)} строк")

# ─── Парсинг ──────────────────────────────────────────────────────────────────
def run_currency_parsers(today: str) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """
    Возвращает (currency_df, gold_from_currency_df, errors).
    Некоторые банки (Керемет) возвращают золото вместе с валютами — разделяем.
    """
    currency_rows: list[pd.DataFrame] = []
    gold_rows:     list[pd.DataFrame] = []
    errors:        list[str]          = []

    for bank_name, func in CURRENCY_PARSERS:
        try:
            if bank_name == "Оптима Банк":
                raw = parse_optima(
                    "https://www.optimabank.kg/index.php?option=com_nbrates&view=default&lang=ru",
                    today,
                )
            else:
                raw = func()

            df = normalize(raw, bank_name, today)
            if df.empty:
                errors.append(f"{bank_name}: пустой результат")
                log.warning(f"  ⚠️  {bank_name}: пустой результат")
                continue

            # Разделяем валюты и металлы
            mask_gold   = df["type"].isin(GOLD_TYPES)
            currency_rows.append(df[~mask_gold])
            if mask_gold.any():
                gold_rows.append(df[mask_gold])

            log.info(f"  ✅ {bank_name}: {len(df)} строк")

        except Exception as exc:
            errors.append(f"{bank_name}: {exc}")
            log.error(f"  ❌ {bank_name}: {exc}")

    cur_df  = pd.concat(currency_rows, ignore_index=True) if currency_rows else pd.DataFrame()
    gold_df = pd.concat(gold_rows,     ignore_index=True) if gold_rows     else pd.DataFrame()
    return cur_df, gold_df, errors


def run_gold_parsers(today: str) -> pd.DataFrame:
    """Парсеры, которые возвращают только золото."""
    frames: list[pd.DataFrame] = []
    for bank_name, func in GOLD_PARSERS:
        try:
            raw = func()
            df  = normalize(raw, bank_name, today)
            if not df.empty:
                frames.append(df)
                log.info(f"  🥇 {bank_name} (золото): {len(df)} строк")
        except Exception as exc:
            log.error(f"  ❌ {bank_name} (золото): {exc}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


# ─── Основная задача ──────────────────────────────────────────────────────────
def job() -> None:
    today = datetime.now().strftime("%Y-%m-%d")
    log.info("=" * 60)
    log.info(f"🚀 Старт парсинга  [{today}]")

    # 1. Курсы валют
    log.info("── Валюты ──")
    cur_df, gold_from_banks, errors = run_currency_parsers(today)

    # 2. Золото (НБКР + Кыргызалтын)
    log.info("── Золото ──")
    gold_df = run_gold_parsers(today)

    # Объединяем всё золото
    all_gold = pd.concat(
        [df for df in [gold_df, gold_from_banks] if not df.empty],
        ignore_index=True,
    )

    # Оставляем только самую свежую дату — НБКР и Кыргызалтын
    # возвращают всю историческую выборку со страницы
    if not all_gold.empty:
        all_gold["date"] = all_gold["date"].astype(str)
        latest_date = all_gold["date"].max()
        all_gold = all_gold[all_gold["date"] == latest_date]
        log.info(f"  🥇 Золото: фильтр по дате {latest_date} → {len(all_gold)} строк")

    # 3. Сохраняем
    log.info("── Сохранение ──")
    upsert(cur_df,  "exchange_rates", "bank_name,type,item,date")
    upsert(all_gold, "gold_rates",    "bank_name,item,date")

    # 4. Итог
    log.info(f"✅ Завершено. Ошибок: {len(errors)}")
    for e in errors:
        log.warning(f"   · {e}")
    log.info("=" * 60)


# ─── Точка входа ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "--once"

    if mode == "--once":
        # GitHub Actions: однократный запуск
        job()
    elif mode == "--daemon":
        # Сервер: запуск по расписанию (каждые 30 минут)
        log.info("Планировщик запущен. Расписание: каждые 30 минут")
        job()                                      # сразу при старте
        schedule.every(30).minutes.do(job)
        while True:
            schedule.run_pending()
            time.sleep(60)
    else:
        print(__doc__)