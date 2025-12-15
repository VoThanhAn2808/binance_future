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

# ---- Session ----
if "symbols_cache" not in st.session_state:
    st.session_state["symbols_cache"] = None

if "candle_cache" not in st.session_state:
    st.session_state["candle_cache"] = {}

if "selected_from_table" not in st.session_state:
    st.session_state["selected_from_table"] = None

# ✅ FIX LỖI: khởi tạo timeframe chart
if "chart_interval_label" not in st.session_state:
    st.session_state["chart_interval_label"] = None

# ---- Fetch functions ----
@st.cache_data(ttl=300)
def fetch_exchange_symbols():
    try:
        r = requests.get(EXCHANGE_INFO, timeout=10)
        if r.status_code != 200:
            st.error(f"Binance trả về lỗi: {r.status_code}")
            return []
        data = r.json()
    except Exception as e:
        st.error(f"Lỗi kết nối Binance: {e}")
        return []

    return [
        s for s in data.get("symbols", [])
        if s.get("quoteAsset") == "USDT"
        and s.get("contractType") == "PERPETUAL"
        and s.get("status") == "TRADING"
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

    numeric_cols = ["open", "high", "low", "close", "volume"]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["openTime"] = pd.to_datetime(df["openTime"], unit="ms")
    df["closeTime"] = pd.to_datetime(df["closeTime"], unit="ms")

    st.session_state["candle_cache"][key] = df
    return df


# ---- UI ----
st.set_page_config(page_title="DTV Holdings Future", layout="wide")
st.title("DTV Holdings Futures – Lọc coin %PNL âm (24h)")

# ==== Sidebar ====
st.sidebar.subheader("Bộ lọc")

interval_label_sidebar = st.sidebar.selectbox("Khung thời gian (Chart - Sidebar)", list(INTERVAL_MAP.keys()), index=3)
interval_sidebar = INTERVAL_MAP[interval_label_sidebar]

max_symbols = st.sidebar.number_input(
    "Số lượng coin cần lọc", 1, 2000, 200
)

refresh = st.sidebar.button("Tìm kiếm dữ liệu")

auto_refresh = st.sidebar.checkbox("Auto Update (Real-time)")
refresh_rate = st.sidebar.number_input("Thời gian refresh (giây)", 1, 30, 5)

need_reload = refresh or auto_refresh


# ---- Load data ----
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
            r = requests.get(KLINES, params={"symbol": sym, "interval": "1d", "limit": 1, "startTime": 0}, timeout=10)
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
    st.warning("Bấm 'Tìm kiếm dữ liệu' để tải danh sách coin.")
    st.stop()

df = st.session_state["filtered_df"]

st.markdown("""
<style>
/* Xoá border table giả lập bằng columns */
[data-testid="stVerticalBlock"] div {
    border: none !important;
}

/* Xoá border button */
button {
    border: none !important;
    box-shadow: none !important;
}

/* Xoá đường kẻ ngăn cách */
hr {
    display: none;
}
</style>
""", unsafe_allow_html=True)

# ---- TABLE + VIEW BUTTON ----
st.subheader(f"Danh sách coin âm %PNL — {len(df)} kết quả")

# 👇 BỌC BẢNG TRONG CONTAINER CÓ HEIGHT
table_container = st.container(height=560)

with table_container:
    header_cols = st.columns([1, 2, 2, 2, 2, 1])
    header_cols[0].write("No.")
    header_cols[1].write("Symbol")
    header_cols[2].write("Last Price")
    header_cols[3].write("% 24h")
    header_cols[4].write("Listed Date")
    header_cols[5].write("Xem")

    for idx, row in df.iterrows():
        c0, c1, c2, c3, c4, c5 = st.columns([1, 2, 2, 2, 2, 1])
        c0.write(idx + 1)
        c1.write(row["symbol"])
        c2.write(f'{row["last_price"]:.6f}')
        c3.write(f'{row["% 24h"]:.2f}')
        c4.write(row["listed_date"])

        if c5.button("View", key=f"view_{row['symbol']}"):
            st.session_state["selected_from_table"] = row["symbol"]
            st.rerun()

# ===================== BIỂU ĐỒ =====================
st.markdown("## 📊 Biểu đồ nến")

selected_coin = st.session_state.get("selected_from_table")

if not selected_coin:
    st.write("")
else:
    interval_keys = list(INTERVAL_MAP.keys())

    # ===== INIT TIMEFRAME LẦN ĐẦU TIÊN =====
    if st.session_state["chart_interval_label"] is None:
        st.session_state["chart_interval_label"] = "H4"   # chỉ dùng khi CHƯA từng chọn

    # ===== RADIO LUÔN ĂN THEO SESSION =====
    chart_interval_label = st.radio(
        "⏱ Khung thời gian nến",
        interval_keys,
        horizontal=True,
        key="chart_interval_label"
    )

    chart_interval = INTERVAL_MAP[chart_interval_label]

    # ===== HIỂN THỊ ĐANG XEM =====
    st.caption(
        f"🔍 Đang xem **{selected_coin}** | Khung: **{chart_interval_label}**"
    )

    # ===== LOAD CHART =====
    try:
        dfk = get_klines_cached(selected_coin, chart_interval)

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
            title=f"{selected_coin} — {chart_interval_label}",
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
            config={
                "scrollZoom": True,
                "displayModeBar": True,
                "modeBarButtonsToAdd": ["drawline", "eraseshape"],
            }
        )

    except Exception as e:
        st.error(f"Lỗi load chart: {e}")
