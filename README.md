# 🇰🇬 Kyrgyz Republic Commercial Banks Exchange Rates Monitoring

An interactive dashboard and automated parsing system for tracking exchange rates and precious metals across commercial banks in Kyrgyzstan.

The project consists of a web interface based on **Streamlit** and a parser script that collects data from the official websites of over 20 banks, the National Bank of the Kyrgyz Republic (NBKR), and "Kyrgyzaltyn" (gold bars), saving it to a **Supabase** (PostgreSQL) database.

---

## ✨ Features

* **Extensive Coverage:** Data collection from 21+ commercial banks in the Kyrgyz Republic, as well as official NBKR rates and "Kyrgyzaltyn" bullion quotes.
* **Interactive Dashboard (`app.py`):**
  * Summary table of current currency buy and sell rates.
  * Bank matrix (scatter plot) to visually find the best offers.
  * Detailed market position analysis for a selected bank (default is *Dos-Credobank*).
  * Historical dynamics of currency and gold rates over a selected period.
* **Smart Parser Auto-Trigger:** If a user opens the dashboard and there is no data for the current day, the app automatically triggers a GitHub Actions workflow to run the parser.
* **Data Collection Modes (`scheduler.py`):**
  * Single run (ideal for cron / GitHub Actions).
  * Daemon mode (`--daemon`) with scheduling (e.g., at 08:00 and 16:00).

---

## 🛠 Tech Stack

* **Language:** Python 3.10+
* **Frontend / UI:** [Streamlit](https://streamlit.io/), [Plotly](https://plotly.com/python/)
* **Database:** [Supabase](https://supabase.com/) (PostgreSQL)
* **Data Manipulation:** Pandas
* **Automation:** Schedule, GitHub Actions API

---

## 🚀 Installation and Setup

### 1. Clone the repository
```bash
git clone https://github.com/thedinaiym/All-Banks-KG-Visual-Statistics
All-Banks-KG-Visual-Statistics
