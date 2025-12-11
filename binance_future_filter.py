import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from datetime import datetime

# ---- Config ----
BASE = "https://fapi.binance.com"
EXCHANGE_INFO = f"{BASE}/fapi/v1/exchangeInfo"
KLINES = f"{BASE}/fapi/v1/klines"
TICKER_24H = f"{BASE}/fapi/v1/ticker/24hr"

INTERVAL_MAP = {
    "M1": "1m",
    "M15": "15m",
    "M30": "30m",
    "H1": "1h",
    "H4": "4h",
    "D1": "1d",
    "W1": "1w",
}

# ---- Session caches ----
if "symbols_cache" not in st.session_state:
    st.session_state["symbols_cache"] = None

if "candle_cache" not in st.session_state:
    st.session_state["candle_cache"] = {}

# ---- Fetch functions ----
@st.cache_data(ttl=300)
def fetch_exchange_symbols():
    r = requests.get(EXCHANGE_INFO, timeout=10)
    r.raise_for_status()
    data = r.json()
    return [
        s for s in data["symbols"]
        if s["quoteAsset"] == "USDT"
        and s["contractType"] == "PERPETUAL"
        and s["status"] == "TRADING"
    ]

@st.cache_data(ttl=12)
def fetch_all_tickers_24h():
    r = requests.get(TICKER_24H, timeout=10)
    r.raise_for_status()
    return r.json()

def get_klines_cached(symbol: str, interval: str, limit: int = 500):
    key = f"{symbol}_{interval}"
    if key in st.session_state["candle_cache"]:
        return st.session_state["candle_cache"][key]

    params = {"symbol": symbol, "interval": interval, "limit": limit}
    r = requests.get(KLINES, params=params, timeout=10)
    r.raise_for_status()
    arr = r.json()

    df = pd.DataFrame(arr, columns=[
        "openTime", "open", "high", "low", "close", "volume",
        "closeTime", "quoteAssetVolume", "nbrTrades",
        "takerBuyBase", "takerBuyQuote", "ignore"
    ])

    numeric_cols = ["open", "high", "low", "volume", "close"]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["openTime"] = pd.to_datetime(df["openTime"], unit="ms")
    df["closeTime"] = pd.to_datetime(df["closeTime"], unit="ms")

    st.session_state["candle_cache"][key] = df
    return df


# ---- UI ----
st.set_page_config(page_title="Binance Futures Filter", layout="wide")
st.title("Binance Futures – Lọc coin %PNL âm (24h)")

# ==== Sidebar lọc ====
st.sidebar.subheader("Bộ lọc")

interval_label_sidebar = st.sidebar.selectbox("Khung thời gian (Chart - Sidebar)", list(INTERVAL_MAP.keys()), index=3)
interval_sidebar = INTERVAL_MAP[interval_label_sidebar]

max_symbols = st.sidebar.number_input(
    "Số lượng coin cần lọc",
    min_value=1,
    max_value=2000,
    value=200,
    step=1
)

refresh = st.sidebar.button("Làm mới dữ liệu")

# ==== Auto-update ====
auto_refresh = st.sidebar.checkbox("Bật Auto Update (Real-time)")
refresh_rate = st.sidebar.number_input("Thời gian refresh (giây)", 1, 30, 5)

# Flag để reload dữ liệu
need_reload = refresh or auto_refresh

# ---- LOAD FILTER DATA
if need_reload:

    if st.session_state["symbols_cache"] is None or refresh:
        with st.spinner("Đang tải symbol từ Binance..."):
            st.session_state["symbols_cache"] = fetch_exchange_symbols()

    symbols_info = st.session_state["symbols_cache"][:max_symbols]
    symbol_list = [s["symbol"] for s in symbols_info]

    with st.spinner("Đang tải dữ liệu %PNL 24h..."):
        tickers = fetch_all_tickers_24h()

    tick_map = {t["symbol"]: t for t in tickers}

    rows = []
    progress = st.progress(0)
    total = len(symbol_list)

    for i, sym in enumerate(symbol_list):
        progress.progress(int((i + 1) / total * 100))

        if sym not in tick_map:
            continue

        t = tick_map[sym]
        pct = float(t["priceChangePercent"])

        if pct >= 0:
            continue

        try:
            params = {"symbol": sym, "interval": "1d", "limit": 1, "startTime": 0}
            r = requests.get(KLINES, params=params, timeout=10)
            if r.status_code == 200 and len(r.json()) > 0:
                first_ts = r.json()[0][0]
                listed = datetime.utcfromtimestamp(first_ts / 1000).strftime("%d/%m/%Y")
            else:
                listed = "N/A"
        except:
            listed = "N/A"

        rows.append({
            "symbol": sym,
            "% 24h": pct,
            "last_price": float(t["lastPrice"]),
            "volume (USDT)": float(t["quoteVolume"]),
            "listed_date": listed,
        })

    df = pd.DataFrame(rows).sort_values("% 24h").reset_index(drop=True)
    st.session_state["filtered_df"] = df


if "filtered_df" not in st.session_state:
    st.warning("Bấm 'Làm mới dữ liệu' để tải danh sách coin.")
    st.stop()

df = st.session_state["filtered_df"]

# ---- Table ----
st.subheader(f"Danh sách coin âm %PNL — {len(df)} kết quả")
st.dataframe(
    df.style.format({
        "last_price": "{:.6f}",
        "% 24h": "{:.2f}",
        "volume (USDT)": "{:,.2f}",
    }),
    height=560
)

# ===================== BIỂU ĐỒ NẾN =====================

st.markdown("## Biểu đồ nến")

selected = st.selectbox("Chọn coin để xem biểu đồ", df["symbol"].tolist())

# 🔥 THÊM KHUNG THỜI GIAN CHO CHART NGAY TRONG KHU VỰC CHART (YÊU CẦU CỦA BẠN)
chart_interval_label = st.radio(
    "Khung thời gian nến (Chart Timeframe)",
    list(INTERVAL_MAP.keys()),
    horizontal=True,
    index=3
)
chart_interval = INTERVAL_MAP[chart_interval_label]

# ---- Chart ----
if selected:
    try:
        dfk = get_klines_cached(selected, chart_interval)

        fig = go.Figure([
            go.Candlestick(
                x=dfk["closeTime"],
                open=dfk["open"],
                high=dfk["high"],
                low=dfk["low"],
                close=dfk["close"],
                increasing_line_color="#26a69a",
                decreasing_line_color="#ef5350",
            )
        ])

        fig.update_layout(
            height=700,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            dragmode="pan",
            uirevision=f"{selected}_{chart_interval}",  # Không reset chart khi đổi timeframe/coin
            title=f"{selected}",
        )

        st.plotly_chart(fig, use_container_width=True, config={
            "scrollZoom": True,            # Zoom bằng chuột
            "displayModeBar": True,        # Giống Binance
            "modeBarButtonsToAdd": ["drawline", "eraseshape"],
        })

    except Exception as e:
        st.error(f"Lỗi load chart: {e}")
