"""
app.py — Streamlit-дашборд курсов валют банков КР
Данные читаются из Supabase. Если за сегодня данных нет — запускает парсинг сам.
"""

import os
import sys
import logging
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# ─── Конфиг страницы ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Курсы БВУ КР",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Константы ────────────────────────────────────────────────────────────────
CURRENCY_ICONS = {
    "USD": "🇺🇸 USD", "EUR": "🇪🇺 EUR", "RUB": "🇷🇺 RUB",
    "KZT": "🇰🇿 KZT", "CNY": "🇨🇳 CNY", "GBP": "🇬🇧 GBP",
    "CHF": "🇨🇭 CHF", "JPY": "🇯🇵 JPY", "TRY": "🇹🇷 TRY",
    "AED": "🇦🇪 AED", "CAD": "🇨🇦 CAD",
}

BANK_ICONS = {
    "Дос-Кредобанк":    "🟢", "Оптима Банк":    "🔴",
    "Демир Банк":       "🔵", "MBank":          "🟣",
    "Керемет Банк":     "🟠", "Банк Азии":      "🟡",
    "FINCA Bank":       "🟤", "Компаньон":      "🟢",
    "Бай-Тушум":        "🔵", "Бакай Банк":     "⚪",
    "Элдик Банк":       "🔵", "KICB":           "🔴",
    "Кыргызалтын":      "⛏️", "O!Bank":         "🟣",
    "Кыргызкоммерц":    "🔴", "Капитал Банк":   "🟡",
    "Толубай Банк":     "🔵", "Айыл Банк":      "🟢",
    "ЭкоИсламикБанк":   "🟤", "ЕСБ":            "🔵",
    "ФинансКредитБанк": "🟠", "КСБ Банк":       "🟡",
    "НБКР":             "🏛️",
}

DCB = "Дос-Кредобанк"  # Главный банк для анализа позиции


def fmt_currency(code: str) -> str:
    return CURRENCY_ICONS.get(code, f"💵 {code}")


def fmt_bank(name: str) -> str:
    return f"{BANK_ICONS.get(name, '🏦')} {name}"


# ─── Supabase ─────────────────────────────────────────────────────────────────
@st.cache_resource
def get_supabase() -> Client:
    url = os.environ.get("Project_URL")
    key = os.environ.get("Publishable_API_Key")
    if not url or not key:
        st.error("❌ Переменные Project_URL / Publishable_API_Key не заданы.")
        st.stop()
    return create_client(url, key)


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def has_data_today(table: str) -> bool:
    """Проверяем — есть ли в таблице хоть одна запись за сегодня."""
    sb = get_supabase()
    res = sb.table(table).select("id").eq("date", today_str()).limit(1).execute()
    return bool(res.data)


def fetch_exchange_today() -> pd.DataFrame:
    """Загрузить все курсы валют за сегодня."""
    sb  = get_supabase()
    res = sb.table("exchange_rates").select("*").eq("date", today_str()).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()


def fetch_gold_latest(days: int = 30) -> pd.DataFrame:
    """Загрузить золотые котировки за последние N дней."""
    from datetime import timedelta
    sb       = get_supabase()
    cutoff   = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    res      = sb.table("gold_rates").select("*").gte("date", cutoff)\
                 .order("date", desc=True).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()


def save_to_supabase(df: pd.DataFrame, table: str, conflict: str) -> None:
    if df.empty:
        return
    sb = get_supabase()
    df = df.copy()
    df["created_at"] = datetime.now().isoformat()
    records = df.where(pd.notnull(df), None).to_dict(orient="records")
    sb.table(table).upsert(records, on_conflict=conflict).execute()


# ─── Парсинг (fallback, если нет данных за сегодня) ──────────────────────────
def run_parsers_and_save() -> tuple[pd.DataFrame, list[str]]:
    """
    Импортируем scheduler.job логику прямо здесь,
    чтобы не дублировать код.
    """
    # Импортируем функции из scheduler (он лежит рядом)
    try:
        from scheduler import run_currency_parsers, run_gold_parsers, GOLD_TYPES
    except ImportError:
        st.error("Не удалось импортировать scheduler.py — убедитесь, что он в той же папке.")
        return pd.DataFrame(), ["Ошибка импорта scheduler"]

    today = today_str()
    cur_df, gold_from_banks, errors = run_currency_parsers(today)
    gold_df = run_gold_parsers(today)

    all_gold = pd.concat(
        [df for df in [gold_df, gold_from_banks] if not df.empty],
        ignore_index=True,
    )

    save_to_supabase(cur_df,   "exchange_rates", "bank_name,type,item,date")
    save_to_supabase(all_gold, "gold_rates",     "bank_name,item,date")

    return cur_df, errors


# ─── Загрузка данных (кэш 5 минут) ───────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def load_exchange() -> tuple[pd.DataFrame, list[str]]:
    errors: list[str] = []

    if has_data_today("exchange_rates"):
        df = fetch_exchange_today()
        return df, errors
    else:
        # Данных нет — парсим сейчас
        df, errors = run_parsers_and_save()
        return df, errors


@st.cache_data(ttl=3600, show_spinner=False)
def load_gold() -> pd.DataFrame:
    return fetch_gold_latest(days=30)


# ─── Интерфейс ────────────────────────────────────────────────────────────────
st.title("🏦 Мониторинг курсов БВУ Кыргызстана")
st.caption(f"Данные за: **{today_str()}**  |  Источник: сайты банков")

# Боковая панель — управление
st.sidebar.header("⚙️ Управление")

if st.sidebar.button("🔄 Обновить данные", use_container_width=True, type="primary"):
    load_exchange.clear()
    load_gold.clear()
    st.rerun()

st.sidebar.caption(f"Последнее обращение: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
st.sidebar.divider()

# ─── Загрузка ─────────────────────────────────────────────────────────────────
with st.spinner("Загрузка данных…"):
    df, failed = load_exchange()
    gold_df    = load_gold()

# Ошибки парсеров (если был fallback)
if failed:
    with st.expander(f"⚠️ Ошибки парсеров ({len(failed)})", expanded=False):
        for e in failed:
            st.warning(e)

if df.empty:
    st.error("Нет данных за сегодня. Попробуйте нажать «Обновить данные».")
    st.stop()

# ─── Фильтры ──────────────────────────────────────────────────────────────────
st.sidebar.header("🔍 Фильтры")

rate_types     = sorted(df["type"].dropna().unique().tolist())
_default_type  = "Наличный" if "Наличный" in rate_types else "Все"
selected_type  = st.sidebar.selectbox(
    "Тип курса",
    ["Все"] + rate_types,
    index=(["Все"] + rate_types).index(_default_type),
)

currencies     = sorted(df["item"].dropna().unique().tolist())
_default_item  = "USD" if "USD" in currencies else ("Все" if not currencies else currencies[0])
selected_item  = st.sidebar.selectbox(
    "Валюта",
    ["Все"] + currencies,
    index=(["Все"] + currencies).index(_default_item) if _default_item in ["Все"] + currencies else 0,
    format_func=lambda x: fmt_currency(x) if x != "Все" else "Все",
)

banks          = sorted(df["bank_name"].dropna().unique().tolist())
selected_banks = st.sidebar.multiselect("Банки", banks, default=banks)

# Применяем фильтры
fdf = df.copy()
if selected_type  != "Все":           fdf = fdf[fdf["type"]      == selected_type]
if selected_item  != "Все":           fdf = fdf[fdf["item"]      == selected_item]
if selected_banks:                    fdf = fdf[fdf["bank_name"].isin(selected_banks)]

# ─── Вкладки ──────────────────────────────────────────────────────────────────
tab_rates, tab_gold, tab_history = st.tabs(["💱 Курсы валют", "🥇 Золото", "📈 История"])


# ══════════════════════════════════════════════════════════════════════════════
# Вкладка 1: Курсы валют
# ══════════════════════════════════════════════════════════════════════════════
with tab_rates:

    # ── Блок позиции DCB ──────────────────────────────────────────────────────
    if selected_item != "Все" and selected_type != "Все" and not fdf.empty:
        st.subheader(f"📊 Позиция {DCB} | {fmt_currency(selected_item)} · {selected_type}")

        dcb_row = fdf[fdf["bank_name"] == DCB]
        col1, col2, col3, col4 = st.columns(4)

        best_buy_row  = fdf.loc[fdf["buy"].idxmax()]
        best_sell_row = fdf.loc[fdf["sell"].idxmin()]
        mkt_avg_buy   = fdf["buy"].mean()
        mkt_avg_sell  = fdf["sell"].mean()

        if not dcb_row.empty:
            dc_buy  = float(dcb_row.iloc[0]["buy"])
            dc_sell = float(dcb_row.iloc[0]["sell"])

            col1.metric(
                "DCB покупает",
                f"{dc_buy:.4f}",
                delta=f"{dc_buy - mkt_avg_buy:+.4f} от ср. рынка",
                delta_color="normal",
                help="Положительное δ = мы платим больше рынка → выгодно клиенту",
            )
            col2.metric(
                "DCB продаёт",
                f"{dc_sell:.4f}",
                delta=f"{dc_sell - mkt_avg_sell:+.4f} от ср. рынка",
                delta_color="inverse",
                help="Отрицательное δ = мы продаём дешевле рынка → выгодно клиенту",
            )
        else:
            col1.warning("Нет данных DCB")
            col2.empty()

        col3.metric(
            f"Лучшая покупка: {best_buy_row['bank_name']}",
            f"{best_buy_row['buy']:.4f}",
            delta="↑ максимум",
            delta_color="off",
        )
        col4.metric(
            f"Лучшая продажа: {best_sell_row['bank_name']}",
            f"{best_sell_row['sell']:.4f}",
            delta="↓ минимум",
            delta_color="off",
        )

        st.divider()

    elif selected_item == "Все":
        st.info("💡 Выберите конкретную валюту и тип курса для детального анализа позиции.")

    # ── Таблица + график ──────────────────────────────────────────────────────
    col_tbl, col_chart = st.columns([1.3, 1])

    with col_tbl:
        st.markdown("### 📋 Все курсы")

        display = fdf[["bank_name", "type", "item", "buy", "sell"]].copy()
        display = display.sort_values("buy", ascending=False)
        display["bank_name"] = display["bank_name"].apply(fmt_bank)
        display["item"]      = display["item"].apply(fmt_currency)
        display.columns      = ["Банк", "Тип", "Валюта", "Покупка", "Продажа"]

        def _highlight(row):
            if DCB in row["Банк"]:
                return ["background-color:#e6f9ec"] * len(row)
            return [""] * len(row)

        st.dataframe(
            display.style.apply(_highlight, axis=1).format({"Покупка": "{:.4f}", "Продажа": "{:.4f}"}),
            use_container_width=True,
            hide_index=True,
            height=520,
        )

    with col_chart:
        st.markdown("### 📈 Матрица банков")

        if selected_item != "Все" and not fdf.empty:
            fig = px.scatter(
                fdf,
                x="buy", y="sell",
                color="bank_name",
                text="bank_name",
                title=f"{fmt_currency(selected_item)} — покупка vs продажа",
                labels={"buy": "Покупка", "sell": "Продажа", "bank_name": "Банк"},
                height=520,
            )
            fig.update_traces(textposition="top center", marker=dict(size=12, opacity=0.85))
            fig.update_layout(showlegend=False)

            # Линии DCB
            dcb_row = fdf[fdf["bank_name"] == DCB]
            if not dcb_row.empty:
                fig.add_vline(
                    x=float(dcb_row.iloc[0]["buy"]),
                    line_dash="dash", line_color="green",
                    annotation_text="DCB buy",
                )
                fig.add_hline(
                    y=float(dcb_row.iloc[0]["sell"]),
                    line_dash="dash", line_color="tomato",
                    annotation_text="DCB sell",
                )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Выберите одну валюту для отображения графика.")

    # ── Сводная таблица лучших курсов ─────────────────────────────────────────
    if selected_item != "Все" and not fdf.empty:
        st.markdown("### 🏆 Топ-5 банков")
        c1, c2 = st.columns(2)

        top_buy = (
            fdf[["bank_name", "buy"]].sort_values("buy", ascending=False)
            .head(5).reset_index(drop=True)
        )
        top_buy.index += 1
        top_buy.columns = ["Банк", "Покупает (макс.)"]

        top_sell = (
            fdf[["bank_name", "sell"]].sort_values("sell")
            .head(5).reset_index(drop=True)
        )
        top_sell.index += 1
        top_sell.columns = ["Банк", "Продаёт (мин.)"]

        c1.dataframe(top_buy.style.format({"Покупает (макс.)": "{:.4f}"}), use_container_width=True)
        c2.dataframe(top_sell.style.format({"Продаёт (мин.)": "{:.4f}"}), use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# Вкладка 2: Золото
# ══════════════════════════════════════════════════════════════════════════════
with tab_gold:
    st.subheader("🥇 Котировки золота и драгоценных металлов")

    if gold_df.empty:
        st.warning("Нет данных о золоте за последние 30 дней.")
    else:
        # Разделяем по источнику
        nbkr_df     = gold_df[gold_df["bank_name"] == "НБКР"].copy()
        altyn_df    = gold_df[gold_df["bank_name"] == "Кыргызалтын"].copy()
        others_df   = gold_df[~gold_df["bank_name"].isin(["НБКР", "Кыргызалтын"])].copy()

        col_a, col_b = st.columns(2)

        # НБКР
        with col_a:
            st.markdown("#### 🏛️ НБКР — учётные цены")
            if not nbkr_df.empty:
                latest_nbkr = nbkr_df.sort_values("date", ascending=False)
                st.dataframe(
                    latest_nbkr[["date", "item", "buy", "sell"]].rename(
                        columns={"date": "Дата", "item": "Металл/Номинал",
                                 "buy": "Покупка", "sell": "Продажа"}
                    ).style.format({"Покупка": "{:.2f}", "Продажа": "{:.2f}"}),
                    use_container_width=True,
                    hide_index=True,
                    height=350,
                )
            else:
                st.info("Нет данных НБКР")

        # Кыргызалтын
        with col_b:
            st.markdown("#### ⛏️ Кыргызалтын — золотые слитки")
            if not altyn_df.empty:
                latest_altyn = altyn_df.sort_values("date", ascending=False)
                st.dataframe(
                    latest_altyn[["date", "item", "buy", "sell"]].rename(
                        columns={"date": "Дата", "item": "Вес слитка",
                                 "buy": "Выкуп", "sell": "Продажа"}
                    ).style.format({"Выкуп": "{:.2f}", "Продажа": "{:.2f}"}),
                    use_container_width=True,
                    hide_index=True,
                    height=350,
                )
            else:
                st.info("Нет данных Кыргызалтын")

        # График динамики НБКР
        if not nbkr_df.empty and len(nbkr_df["date"].unique()) > 1:
            st.markdown("#### 📈 Динамика учётной цены НБКР")
            items_available = nbkr_df["item"].unique().tolist()
            sel_item = st.selectbox("Инструмент", items_available, key="gold_item")
            plot_data = nbkr_df[nbkr_df["item"] == sel_item].sort_values("date")
            fig_gold = px.line(
                plot_data, x="date", y=["buy", "sell"],
                title=f"НБКР · {sel_item}",
                labels={"value": "Цена (сом)", "date": "Дата", "variable": ""},
                height=350,
            )
            fig_gold.update_layout(legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig_gold, use_container_width=True)

        # Остальные банки (если есть металлы)
        if not others_df.empty:
            st.markdown("#### 🏦 Металлы других банков")
            st.dataframe(
                others_df[["bank_name", "date", "type", "item", "buy", "sell"]].rename(
                    columns={"bank_name": "Банк", "date": "Дата", "type": "Тип",
                             "item": "Металл", "buy": "Покупка", "sell": "Продажа"}
                ).sort_values("Дата", ascending=False)
                .style.format({"Покупка": "{:.4f}", "Продажа": "{:.4f}"}),
                use_container_width=True,
                hide_index=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
# Вкладка 3: История
# ══════════════════════════════════════════════════════════════════════════════
with tab_history:
    st.subheader("📈 Историческая динамика курсов")

    if selected_item == "Все":
        st.info("Выберите конкретную валюту в фильтрах слева для просмотра истории.")
    else:
        sb = get_supabase()

        @st.cache_data(ttl=3600, show_spinner=False)
        def load_history(item: str, rate_type: str, days: int = 90) -> pd.DataFrame:
            from datetime import timedelta
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            q = sb.table("exchange_rates").select("bank_name,type,item,buy,sell,date")\
                  .eq("item", item).gte("date", cutoff)
            if rate_type != "Все":
                q = q.eq("type", rate_type)
            res = q.order("date").execute()
            return pd.DataFrame(res.data) if res.data else pd.DataFrame()

        h_days = st.slider("Период (дней)", 7, 180, 90, step=7)
        hist   = load_history(selected_item, selected_type, h_days)

        if hist.empty:
            st.warning("Нет исторических данных для выбранного инструмента.")
        else:
            bank_filter = st.multiselect(
                "Банки для графика",
                sorted(hist["bank_name"].unique().tolist()),
                default=[DCB] if DCB in hist["bank_name"].values else [],
            )

            if bank_filter:
                hist_f = hist[hist["bank_name"].isin(bank_filter)]

                fig_h = px.line(
                    hist_f, x="date", y="buy",
                    color="bank_name",
                    title=f"{fmt_currency(selected_item)} · Курс покупки ({h_days} дн.)",
                    labels={"buy": "Покупка", "date": "Дата", "bank_name": "Банк"},
                    height=400,
                )
                st.plotly_chart(fig_h, use_container_width=True)

                fig_h2 = px.line(
                    hist_f, x="date", y="sell",
                    color="bank_name",
                    title=f"{fmt_currency(selected_item)} · Курс продажи ({h_days} дн.)",
                    labels={"sell": "Продажа", "date": "Дата", "bank_name": "Банк"},
                    height=400,
                )
                st.plotly_chart(fig_h2, use_container_width=True)
            else:
                st.info("Выберите хотя бы один банк.")

# ─── Футер ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "Данные собираются автоматически с официальных сайтов банков. "
    "Обновление: 08:00 и 16:00 по Бишкеку. "
    f"Всего банков в базе сегодня: **{df['bank_name'].nunique()}**"
)