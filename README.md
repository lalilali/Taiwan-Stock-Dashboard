# Taiwan Auto Trader — Dashboard

A Streamlit-based web dashboard for monitoring Taiwan stock market data, technical indicators, and running market scanners.

## Features

### Stock Universe
- Loads the full list of Taiwan Stock Exchange (TWSE) and OTC/TPEx stocks on startup via public APIs
- Falls back to a built-in watchlist of 8 major stocks if the APIs are unavailable
- Search by stock code (e.g. `2330`) or company name (e.g. `台積電`)

### Theme
- Toggle between **dark** and **light** mode from the sidebar
- All charts and UI components respond to the active theme

---

## Views

### 📈 Market (市場)

The main chart view for a selected stock. Contains two sub-tabs:

**Daily K-line (日線圖)**
- Intraday minute-by-minute price chart for the current trading session
- VWAP (均價) overlay on the intraday chart
- Volume bars coloured by up/down tick
- Dashed reference line at the previous close
- Key metrics: close price, open, high, low, volume (lots), and volume vs. 20-day average

**Technical Indicators (技術指標)**
- Candlestick chart with selectable overlays:
  - Moving Averages — MA5, MA20, MA60
  - Bollinger Bands — BB20 (upper / mid / lower)
- Separate panels (each toggleable from the sidebar):
  - RSI (14) with overbought (70) and oversold (30) zones
  - MACD (12/26/9) — histogram, MACD line, and signal line
  - Volume bars
- Signal summary table showing the current BUY / SELL / HOLD verdict from each indicator

Period selector: 1 month / 3 months / 6 months / 1 year / 2 years / 5 years / All

---

### ⭐ Favorites (收藏)

Displays saved stocks as cards in a 4-column grid. Each card shows:

| Field | Detail |
|---|---|
| Price | Latest close with change and % change |
| OHLC | Open, High, Low for the latest session |
| Volume | Today vs. 20-day average (e.g. `2.3× 均量`) |
| MA trend | Bullish or bearish based on MA5 vs. MA20 |
| RSI | Current RSI value with overbought / oversold label |
| KD | Stochastic K and D values |

- Click **查看** to jump to the full chart for that stock
- Click **移除** to remove it from favorites
- Favorites are persisted in `favorites.json`

---

### 📊 MA Squeeze Scanner (均線糾結掃描)

Scans for stocks where multiple moving averages are converging — a pattern that often precedes a breakout.

**Settings**
- MA periods — choose any combination of MA5, MA10, MA20, MA60, MA120, MA240
- Squeeze threshold (%) — stocks where `(max MA − min MA) ÷ close × 100` is below this value are included

**Scope**
- Full Taiwan market (~1,700+ stocks, ~3–5 minutes)
- Favorites list only (fast)

Results are sorted by squeeze tightness ascending. Clicking any result navigates directly to its chart.

---

### 🚀 Breakout Scanner (強勢突破選股)

Scans for stocks that satisfy all of the following conditions simultaneously:

1. **Bullish MA alignment** — MA5 > MA20 > MA60
2. **Price breakout** — today's close exceeds the highest close over the past N trading days
3. **Volume surge** — today's volume exceeds the 20-day average by a configurable multiplier
4. **RSI filter** — RSI is below a configurable cap to avoid chasing overheated stocks

**Settings**

| Parameter | Default | Description |
|---|---|---|
| Breakout days N | 20 | Today must close above the prior N-day high |
| Volume multiplier | 1.5× | Minimum ratio of today's volume to 20-day average |
| RSI cap | 75 | Exclude stocks with RSI above this value |

**Scope** — full market or favorites list only

Results are sorted by volume ratio descending and include a bar chart of volume surge strength. Clicking any result navigates to its chart.

---

## Data Sources

| Source | Used for |
|---|---|
| [yfinance](https://github.com/ranaroussi/yfinance) | Historical OHLCV and intraday (1-min) data |
| [TWSE OpenAPI](https://openapi.twse.com.tw) | Full list of listed stocks |
| [TPEX OpenAPI](https://www.tpex.org.tw/openapi) | Full list of OTC stocks |
| TWSE / TPEX daily report APIs | Fallback for NaN close prices on the latest date |

---

## Running Locally

```bash
pip install -r requirements.txt
streamlit run dashboard.py
```

## Running with Docker

```bash
docker build -t ts00328685/heloword-taiwan-trader:1.0 .
docker run -p 80:80 ts00328685/heloword-taiwan-trader:1.0
```

Then open `http://localhost` in your browser.

> **Persistent data:** `favorites.json` is stored inside the container. Mount a volume if you want favorites to survive container restarts:
> ```bash
> docker run -p 80:80 -v $(pwd)/favorites.json:/app/favorites.json ts00328685/heloword-taiwan-trader:1.0
> ```
