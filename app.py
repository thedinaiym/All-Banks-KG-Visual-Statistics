import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import sys
import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

sys.path.append(os.path.abspath('./parsers'))
st.set_page_config(page_title="Аналитика курсов | Dos-Credobank", layout="wide", page_icon="🏦")

CURRENCY_ICONS = {
    "USD": "🇺🇸 USD", "EUR": "🇪🇺 EUR", "RUB": "🇷🇺 RUB", 
    "KZT": "🇰🇿 KZT", "CNY": "🇨🇳 CNY", "GBP": "🇬🇧 GBP",
    "Золото": "🥇 Золото", "Серебро": "🥈 Серебро", "Платина": "💿 Платина"
}

BANK_ICONS = {
    "Дос-Кредобанк": "🟢", "Оптима Банк": "🔴", "Демир Банк": "🔵", 
    "MBank": "🟣", "Керемет Банк": "🟠", "Банк Азии": "🟡",
    "FINCA Bank": "🟤", "Компаньон": "🟢", "Бай-Тушум": "🔵",
    "Бакай Банк": "⚪", "Элдик Банк": "🔵", "KICB": "🔴",
    "НБКР": "🏛️", "Кыргызалтын": "⛏️", "O!Bank": "🟣",
    "Кыргызкоммерц": "🔴", "Капитал Банк": "🟡", "Толубай Банк": "🔵"
}

def get_currency_label(curr):
    return CURRENCY_ICONS.get(curr, f"💵 {curr}")

def get_bank_label(bank):
    return f"{BANK_ICONS.get(bank, '🏦')} {bank}"

def save_to_supabase(df):
    if df.empty:
        return

    url = os.environ.get("Project_URL")
    key = os.environ.get("Publishable_API_Key")

    if not url or not key:
        st.sidebar.warning("⚠️ Ключи Supabase не найдены в .env. Сохранение истории отключено.")
        return

    try:
        supabase: Client = create_client(url, key)
        df_to_save = df.copy()
        
        df_to_save['created_at'] = datetime.now().isoformat()
        
        df_to_save = df_to_save.where(pd.notnull(df_to_save), None)
        
        records = df_to_save.to_dict(orient='records')
        supabase.table('historical_rates').insert(records).execute()
    except Exception as e:
        st.sidebar.error(f"⚠️ Ошибка сохранения в Supabase: {e}")

@st.cache_data(ttl=3600, show_spinner=False)
def load_currency_data():
    dfs = []
    failed_banks = []
    
    parsers_map = {
        "Айыл Банк": ("ab", "ab"),
        "Алма Кредит": ("alma", "alma"),
        "Бай-Тушум": ("baitushum", "baitushum"),
        "Бакай Банк": ("bakai", "bakai"),
        "Банк Азии": ("bank_asia", "bank_asia"),
        "Капитал Банк": ("capital", "capital"),
        "Дос-Кредобанк": ("dcb", "dcb"),
        "Демир Банк": ("demir", "demir"),
        "ЭкоИсламикБанк": ("eib", "eib"),
        "Элдик Банк": ("eldik", "eldik"),
        "ЕСБ": ("esb", "esb"),
        "FINCA Bank": ("finka", "finca"),  
        "ФинансКредитБанк": ("fkb", "fcb"), 
        "Керемет Банк": ("keremet", "keremet"),
        "KICB": ("kicb", "kicb"),
        "Кыргызкоммерц": ("kkb", "kkb"),
        "Компаньон": ("kompanion", "kompanion"),
        "КСБ Банк": ("ksbc", "ksbc"),
        "Кыргызалтын": ("kyrgyz_altyn", "kyrgyz_altyn"),
        "MBank": ("mbank", "mbank"),
        "НБКР": ("nbkr", "nbkr"),
        "O!Bank": ("obank", "obank"),
        "Оптима Банк": ("optima", "optima"),
        "Толубай Банк": ("tolubay", "tolubay")
    }

    for bank_name, (module_name, func_name) in parsers_map.items():
        try:
            module = __import__(f"parsers.{module_name}", fromlist=[module_name])
            parser_func = getattr(module, func_name)
            
            if module_name == "optima":
                today = datetime.now().strftime('%Y-%m-%d')
                df_bank = parser_func('https://www.optimabank.kg/index.php?option=com_nbrates&view=default&lang=ru', today)
            else:
                df_bank = parser_func()

            if df_bank is not None and not df_bank.empty:
                if 'currency' in df_bank.columns:
                    df_bank = df_bank.rename(columns={'currency': 'item'})
                
                df_bank['bank_name'] = bank_name
                dfs.append(df_bank)
            else:
                failed_banks.append(f"{bank_name} (Парсер вернул пустые данные)")
        except Exception as e:
            failed_banks.append(f"{bank_name}: {str(e)}")
            
    if dfs:
        master_df = pd.concat(dfs, ignore_index=True)
      
        master_df['buy'] = pd.to_numeric(master_df['buy'], errors='coerce')
        master_df['sell'] = pd.to_numeric(master_df['sell'], errors='coerce')
        if 'item' in master_df.columns:
            master_df['item'] = master_df['item'].astype(str).str.strip().str.upper()
            
        master_df = master_df.dropna(subset=['buy', 'sell'])
        
        save_to_supabase(master_df)
        
        return master_df, failed_banks
        
    return pd.DataFrame(), failed_banks

st.title("🏦 Платформа казначейства | Мониторинг курсов БВУ КР")

with st.spinner('Идет опрос 24 банков. Это займет некоторое время (около 30-60 сек)...'):
    df, failed_banks = load_currency_data()

if failed_banks:
    with st.expander("⚠️ Отчет об ошибках (Требуется корректировка парсеров)", expanded=True):
        st.markdown("Следующие банки не удалось опросить в текущем цикле. Возможные причины: изменилась верстка сайта или проблемы с сетью.")
        for error in failed_banks:
            st.error(error)

st.sidebar.markdown("### 🔄 Управление")
if st.sidebar.button("Запустить сбор данных сейчас", use_container_width=True, type="primary"):
    load_currency_data.clear() 
    st.rerun() 
st.sidebar.caption(f"Последнее обновление: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")

if df.empty:
    st.error("Критическая ошибка: не удалось получить данные ни с одного банка.")
    st.stop()
    
st.sidebar.header("⚙️ Фильтры")

available_types = df['type'].dropna().unique().tolist()
selected_type = st.sidebar.selectbox("Тип курса", ["Все"] + sorted(available_types))

available_items = df['item'].dropna().unique().tolist()
selected_item = st.sidebar.selectbox(
    "Валюта / Драг. металл", 
    ["Все"] + sorted(available_items),
    format_func=lambda x: get_currency_label(x) if x != "Все" else "Все"
)

filtered_df = df.copy()
if selected_type != "Все":
    filtered_df = filtered_df[filtered_df['type'] == selected_type]
if selected_item != "Все":
    filtered_df = filtered_df[filtered_df['item'] == selected_item]

st.subheader("📊 Позиция Дос-Кредобанка относительно рынка")

if selected_item != "Все" and selected_type != "Все" and not filtered_df.empty:
    doscredo_data = filtered_df[filtered_df['bank_name'] == "Дос-Кредобанк"]
    
    best_buy = filtered_df.loc[filtered_df['buy'].idxmax()]
    best_sell = filtered_df.loc[filtered_df['sell'].idxmin()]
    
    st.markdown(f"**Анализ по инструменту:** {get_currency_label(selected_item)} ({selected_type})")
    
    col1, col2, col3 = st.columns(3)
    
    if not doscredo_data.empty:
        dc_buy = doscredo_data.iloc[0]['buy']
        dc_sell = doscredo_data.iloc[0]['sell']
        
        diff_buy = round(dc_buy - best_buy['buy'], 4)
        diff_sell = round(dc_sell - best_sell['sell'], 4)
        
        col1.markdown(f"**{get_bank_label('Дос-Кредобанк')}**")
        col1.metric("Мы покупаем за", f"{dc_buy}", delta=f"{diff_buy} от макс. на рынке", delta_color="normal")
        col1.metric("Мы продаем за", f"{dc_sell}", delta=f"{diff_sell} от мин. на рынке", delta_color="inverse")
    else:
        col1.warning(f"Курсы Дос-Кредобанка для {selected_item} ({selected_type}) не найдены.")

    col2.markdown(f"**Рынок: Лучшая покупка у клиента**")
    col2.metric(f"{best_buy['bank_name']}", f"{best_buy['buy']}", delta="Максимум", delta_color="off")
    
    col3.markdown(f"**Рынок: Лучшая продажа клиенту**")
    col3.metric(f"{best_sell['bank_name']}", f"{best_sell['sell']}", delta="Минимум", delta_color="off")

elif selected_item == "Все":
    st.info("💡 Выберите конкретную валюту и тип курса в фильтрах слева для просмотра сводной аналитики по Дос-Кредобанку.")

st.divider()

col_table, col_chart = st.columns([1.2, 1])

with col_table:
    st.markdown("### 📋 Курсы всех банков")
    
    display_df = filtered_df[['bank_name', 'type', 'item', 'buy', 'sell']].sort_values(by=['buy', 'sell'], ascending=[False, True])
    
    display_df['bank_name'] = display_df['bank_name'].apply(get_bank_label)
    display_df['item'] = display_df['item'].apply(get_currency_label)
    display_df.columns = ['Банк', 'Тип', 'Инструмент', 'Покупка', 'Продажа']
    
    def highlight_doscredo(s):
        if "Дос-Кредобанк" in s['Банк']:
            return ['background-color: #e6f9ec'] * len(s)
        return [''] * len(s)
    
    st.dataframe(display_df.style.apply(highlight_doscredo, axis=1), use_container_width=True, hide_index=True, height=500)

with col_chart:
    st.markdown("### 📈 Разброс курсов на рынке")
    if selected_item != "Все" and not filtered_df.empty:
        chart_data = filtered_df.copy()
        
        fig = px.scatter(
            chart_data, x='buy', y='sell', color='bank_name', text='bank_name',
            title=f"Матрица конкурентов ({selected_item})",
            labels={'buy': 'Курс покупки', 'sell': 'Курс продажи', 'bank_name': 'Банк'},
            height=500
        )
        
        fig.update_traces(textposition='top center', marker=dict(size=12, opacity=0.8))
        
        if 'doscredo_data' in locals() and not doscredo_data.empty:
            fig.add_vline(x=dc_buy, line_dash="dash", line_color="green", annotation_text="DCB Покупка")
            fig.add_hline(y=dc_sell, line_dash="dash", line_color="red", annotation_text="DCB Продажа")
            
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("График доступен при выборе конкретной валюты.")