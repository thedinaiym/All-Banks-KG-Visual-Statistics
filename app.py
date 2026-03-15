"""
app.py — Streamlit-дашборд курсов валют и золотых слитков банков КР
Данные читаются из Supabase. 
"""

import os
import sys
import logging
from datetime import datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
from dotenv import load_dotenv
from supabase import create_client, Client

# Настройка логирования
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

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
    "Дос-Кредобанк": "🟢", "Оптима Банк": "🔴",
    "Демир Банк": "🔵", "MBank": "🟣",
    "Керемет Банк": "🟡", "НБКР": "🏛️",
    "Кыргызалтын": "🥇"
}

DCB = "Дос-Кредобанк"

# ─── Инициализация БД ─────────────────────────────────────────────────────────
@st.cache_resource
def init_supabase() -> Client:
    url = os.environ.get("Project_URL") or os.environ.get("SUPABASE_URL")
    key = os.environ.get("Publishable_API_Key") or os.environ.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        st.error("❌ Ошибка: Не заданы переменные окружения Supabase (Project_URL / Publishable_API_Key)")
        st.stop()
    return create_client(url, key)

sb = init_supabase()

# ─── Вспомогательные функции ──────────────────────────────────────────────────
def fmt_currency(c: str) -> str:
    return CURRENCY_ICONS.get(c, c)

def fmt_bank(b: str) -> str:
    icon = BANK_ICONS.get(b, "🏦")
    return f"{icon} {b}"

@st.cache_data(ttl=600)
def load_current_data(table_name: str) -> pd.DataFrame:
    """Загружает данные за сегодня из указанной таблицы."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    res = sb.table(table_name).select("*").eq("date", today_str).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        # Приводим числовые колонки к float
        for col in ["buy", "sell"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
    return df

@st.cache_data(ttl=3600)
def load_history(table_name: str, item: str, item_col: str = "item", days: int = 90) -> pd.DataFrame:
    """Загружает историю из исторических таблиц за последние N дней."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    res = sb.table(table_name).select("*").gte("date", cutoff).eq(item_col, item).execute()
    df = pd.DataFrame(res.data)
    if not df.empty:
        for col in ["buy", "sell"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
    return df

# ─── Загрузка текущих данных ──────────────────────────────────────────────────
df_rates = load_current_data("exchange_rates")
df_gold = load_current_data("gold_rates")

# ─── Интерфейс ────────────────────────────────────────────────────────────────
st.title("📊 Сводный дашборд: Курсы валют и Драгоценные металлы")
st.markdown("Сравнение рыночных курсов с **Дос-Кредобанком**, НБКР и Кыргызалтыном.")

tab1, tab2, tab3 = st.tabs(["💱 Курсы валют", "🥇 Золотые слитки", "📈 История (Графики)"])

# ==============================================================================
# Вкладка 1: Курсы валют
# ==============================================================================
with tab1:
    if df_rates.empty:
        st.warning("⚠️ Данных по курсам валют за сегодня еще нет.")
    else:
        # Фильтры
        col_type, col_curr = st.columns(2)
        with col_type:
            types = sorted(df_rates["type"].dropna().unique().tolist())
            selected_type = st.selectbox("Тип операции", types, index=0 if "Безналичный" not in types else types.index("Безналичный"))
        with col_curr:
            currencies = sorted(df_rates["item"].dropna().unique().tolist())
            selected_curr = st.selectbox("Валюта", currencies, index=0 if "USD" not in currencies else currencies.index("USD"))

        df_filtered = df_rates[(df_rates["type"] == selected_type) & (df_rates["item"] == selected_curr)]
        
        if df_filtered.empty:
            st.info("Нет данных по выбранным фильтрам.")
        else:
            # Сравнительный блок с Дос-Кредобанком
            dcb_data = df_filtered[df_filtered["bank_name"] == DCB]
            nbkr_data = df_filtered[df_filtered["bank_name"] == "НБКР"]

            st.markdown(f"### Сравнение курсов: {fmt_currency(selected_curr)}")
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown(f"**{fmt_bank(DCB)}**")
                if not dcb_data.empty:
                    st.metric("Покупка", f"{dcb_data.iloc[0]['buy']:.2f}")
                    st.metric("Продажа", f"{dcb_data.iloc[0]['sell']:.2f}")
                else:
                    st.write("Нет данных")
                    
            with c2:
                st.markdown(f"**{fmt_bank('НБКР')}**")
                if not nbkr_data.empty:
                    # У НБКР обычно только один курс (учетный), выводим его
                    st.metric("Официальный курс", f"{nbkr_data.iloc[0]['buy']:.4f}")
                else:
                    st.write("Нет данных")
            
            with c3:
                # Лучшие курсы на рынке
                best_buy = df_filtered['buy'].max()
                best_sell = df_filtered[df_filtered['sell'] > 0]['sell'].min()
                st.markdown("**🏆 Лучшие на рынке**")
                st.metric("Макс. покупка", f"{best_buy:.2f}")
                st.metric("Мин. продажа", f"{best_sell:.2f}")

            st.divider()
            
            # Таблица всех банков
            st.markdown("#### Все банки")
            display_df = df_filtered[["bank_name", "buy", "sell"]].copy()
            display_df["bank_name"] = display_df["bank_name"].apply(fmt_bank)
            display_df.rename(columns={"bank_name": "Банк", "buy": "Покупка", "sell": "Продажа"}, inplace=True)
            st.dataframe(display_df.set_index("Банк"), use_container_width=True)

# ==============================================================================
# Вкладка 2: Золотые слитки
# ==============================================================================
with tab2:
    if df_gold.empty:
        st.warning("⚠️ Данных по золотым слиткам за сегодня еще нет.")
    else:
        # Унификация названий металлов (приведение к одному формату)
        df_gold['item'] = df_gold['item'].str.strip().str.capitalize()
        
        metals = sorted(df_gold["item"].dropna().unique().tolist())
        default_metal = "Золото 100 гр" if "Золото 100 гр" in metals else (metals[0] if metals else None)
        
        if not metals:
            st.info("Нет доступных видов слитков/металлов.")
        else:
            selected_metal = st.selectbox("Вид слитка / Металл", metals, index=metals.index(default_metal) if default_metal in metals else 0)
            
            df_g_filtered = df_gold[df_gold["item"] == selected_metal]
            
            # Сравнительный блок с Дос-Кредобанком и Кыргызалтыном
            dcb_gold = df_g_filtered[df_g_filtered["bank_name"] == DCB]
            kyrgyzaltyn = df_g_filtered[df_g_filtered["bank_name"] == "Кыргызалтын"]
            
            st.markdown(f"### Сравнение цен: {selected_metal}")
            
            gc1, gc2, gc3 = st.columns(3)
            with gc1:
                st.markdown(f"**{fmt_bank(DCB)}**")
                if not dcb_gold.empty:
                    buy_val = dcb_gold.iloc[0]['buy']
                    sell_val = dcb_gold.iloc[0]['sell']
                    st.metric("Покупка банка", f"{buy_val:,.2f} ⊆" if pd.notnull(buy_val) else "—")
                    st.metric("Продажа банка", f"{sell_val:,.2f} ⊆" if pd.notnull(sell_val) else "—")
                else:
                    st.write("Нет данных")
                    
            with gc2:
                st.markdown(f"**{fmt_bank('Кыргызалтын')}**")
                if not kyrgyzaltyn.empty:
                    buy_val = kyrgyzaltyn.iloc[0]['buy']
                    sell_val = kyrgyzaltyn.iloc[0]['sell']
                    st.metric("Выкуп", f"{buy_val:,.2f} ⊆" if pd.notnull(buy_val) else "—")
                    st.metric("Продажа", f"{sell_val:,.2f} ⊆" if pd.notnull(sell_val) else "—")
                else:
                    st.write("Нет данных")
                    
            with gc3:
                # Рыночный анализ
                best_g_buy = df_g_filtered['buy'].max()
                best_g_sell = df_g_filtered[df_g_filtered['sell'] > 0]['sell'].min()
                st.markdown("**🏆 Лучшие цены**")
                st.metric("Самая дорогая покупка", f"{best_g_buy:,.2f} ⊆" if pd.notnull(best_g_buy) else "—")
                st.metric("Самая дешевая продажа", f"{best_g_sell:,.2f} ⊆" if pd.notnull(best_g_sell) else "—")

            st.divider()
            
            # Таблица всех банков по слиткам
            st.markdown("#### Все предложения на рынке")
            display_g = df_g_filtered[["bank_name", "buy", "sell"]].copy()
            display_g["bank_name"] = display_g["bank_name"].apply(fmt_bank)
            display_g.rename(columns={"bank_name": "Учреждение", "buy": "Цена выкупа (KGS)", "sell": "Цена продажи (KGS)"}, inplace=True)
            
            # Форматируем числа для красоты
            for col in ["Цена выкупа (KGS)", "Цена продажи (KGS)"]:
                display_g[col] = display_g[col].apply(lambda x: f"{x:,.2f}" if pd.notnull(x) else "—")
                
            st.dataframe(display_g.set_index("Учреждение"), use_container_width=True)

# ==============================================================================
# Вкладка 3: История (Графики)
# ==============================================================================
with tab3:
    st.markdown("### Историческая динамика")
    
    h_mode = st.radio("Режим отображения", ["Курсы валют", "Золотые слитки"], horizontal=True)
    h_days = st.slider("Период (дней)", min_value=7, max_value=365, value=30, step=7)
    
    if h_mode == "Курсы валют":
        h_curr = st.selectbox("Выберите валюту для графика", ["USD", "EUR", "RUB", "KZT"])
        hist = load_history("historical_exchange_rates", h_curr, "item", h_days)
        
        if hist.empty:
            st.info("Нет исторических данных за выбранный период.")
        else:
            bank_filter = st.multiselect(
                "Банки для графика",
                sorted(hist["bank_name"].unique().tolist()),
                default=[DCB, "НБКР"] if DCB in hist["bank_name"].values else [],
            )

            if bank_filter:
                hist_f = hist[hist["bank_name"].isin(bank_filter)]

                fig_h = px.line(
                    hist_f, x="date", y="buy", color="bank_name", markers=True,
                    title=f"{fmt_currency(h_curr)} · Курс покупки ({h_days} дн.)",
                    labels={"buy": "Покупка", "date": "Дата", "bank_name": "Банк"}
                )
                st.plotly_chart(fig_h, use_container_width=True)

                fig_h2 = px.line(
                    hist_f, x="date", y="sell", color="bank_name", markers=True,
                    title=f"{fmt_currency(h_curr)} · Курс продажи ({h_days} дн.)",
                    labels={"sell": "Продажа", "date": "Дата", "bank_name": "Банк"}
                )
                st.plotly_chart(fig_h2, use_container_width=True)
            else:
                st.info("Выберите хотя бы один банк.")
                
    else:
        # Графики для золота
        hist_g_meta = load_history("historical_gold_rates", "Золото 100 гр", "item", 1) # Просто чтоб достать список
        # Так как для списка элементов нужно сделать отдельный запрос, временно берем хардкод или из текущих
        g_items = ["Золото 1 гр", "Золото 2 гр", "Золото 5 гр", "Золото 10 гр", "Золото 31.1 гр (Унция)", "Золото 100 гр"]
        if not df_gold.empty:
            g_items = sorted(df_gold["item"].dropna().unique().tolist())
            
        h_gold_item = st.selectbox("Выберите слиток", g_items)
        hist_gold = load_history("historical_gold_rates", h_gold_item, "item", h_days)
        
        if hist_gold.empty:
            st.info("Нет исторических данных по этому слитку за выбранный период.")
        else:
            g_bank_filter = st.multiselect(
                "Учреждения для графика",
                sorted(hist_gold["bank_name"].unique().tolist()),
                default=[DCB, "Кыргызалтын"] if DCB in hist_gold["bank_name"].values else [],
            )

            if g_bank_filter:
                hist_gf = hist_gold[hist_gold["bank_name"].isin(g_bank_filter)]

                fig_g1 = px.line(
                    hist_gf, x="date", y="sell", color="bank_name", markers=True,
                    title=f"{h_gold_item} · Цена продажи ({h_days} дн.)",
                    labels={"sell": "Цена продажи (KGS)", "date": "Дата", "bank_name": "Учреждение"}
                )
                st.plotly_chart(fig_g1, use_container_width=True)
            else:
                st.info("Выберите хотя бы одно учреждение.")

# ─── Футер ────────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    f"Данные собираются автоматически. "
    f"Текущая дата сервера: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)