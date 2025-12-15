# Binance Futures Filter & Chart Dashboard

Ứng dụng **Streamlit** giúp lọc các cặp **Binance Futures USDT Perpetual** đang âm %PNL trong 24h và hiển thị **biểu đồ nến giống Binance** với nhiều khung thời gian (M1 → W1).

---

## ✨ Tính năng chính

- 🔍 Lọc coin Futures âm %PNL 24h
- 📊 Biểu đồ nến (Candlestick) realtime
- ⏱ Đầy đủ khung thời gian: M1, M15, M30, H1, H4, D1, W1
- 🔄 Khi đổi coin **giữ nguyên khung thời gian đang xem**
- ⚡ Cache dữ liệu giúp load nhanh
- 🖥 Giao diện tối (Dark mode) giống Binance

---

## 🧰 Công nghệ sử dụng

- Python 3.9+
- Streamlit
- Pandas
- Plotly
- Binance Futures API (public – không cần API key)

---

## 📦 Cài đặt & sử dụng (Windows)

### 1️⃣ Clone source code từ GitHub
```bash
   git clone https://github.com/VoThanhAn2808/binance_future.git
   cd binance_future
2️⃣ Tạo môi trường ảo (khuyến nghị)
   python -m venv .venv
Kích hoạt môi trường ảo:
   .venv\Scripts\activate
3️⃣ Cài đặt thư viện cần thiết
   pip install -r requirements.txt
4️⃣ Chạy ứng dụng
   streamlit run binance_future_filter.py