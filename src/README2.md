# Taiwan Auto Trader

Automated stock trading bot for Taiwan markets using Fubon Neo API.
Supports MA Crossover, RSI, MACD, and Bollinger Bands strategies with paper trading mode.

---

## Requirements

- Python 3.13
- Fubon Securities account with API access
- Fubon Neo SDK `.whl` file (download from Fubon's portal)
- Fubon certificate file (`.pfx`)

---

## First-Time Setup

### 1. Activate the virtual environment

```bash
cd C:\MyWorkspace\taiwan-trader
.venv\Scripts\activate
```

You should see `(.venv)` appear at the start of your terminal prompt.

### 2. Set up credentials

Copy the example env file and fill in your details:

```bash
copy .env.example .env
```

Open `.env` and fill in:

```env
FUBON_ID=your_login_id
FUBON_PASSWORD=your_password
FUBON_CERT_PATH=C:\path\to\your\certificate.pfx
FUBON_CERT_PASSWORD=your_cert_password

# Keep this true until you are ready to trade with real money
PAPER_TRADING=true
```

### 3. Verify installation

```bash
python -c "from fubon_neo.sdk import FubonSDK; print('Fubon SDK OK')"
```

---

## Launch the Bot

```bash
cd C:\MyWorkspace\taiwan-trader
.venv\Scripts\activate
python main.py
```

The bot will:
- Connect to your Fubon account
- Check market hours automatically (Mon–Fri 09:00–13:30 Taiwan time)
- Run strategy signals every 60 seconds
- Print a portfolio summary at 13:35 every trading day
- Log all activity to `trader.log`
- Record every trade in `portfolio.db`

Press `Ctrl+C` to stop — it will print a final summary before exiting.

---

## Configuration

All parameters are in `config.py`. Key settings:

| Setting | Default | Description |
|---|---|---|
| `watchlist` | `["2330","2317","2454","2881","2382"]` | Stocks to trade |
| `paper_trading` | `true` (from `.env`) | Simulate orders without real money |
| `ma_short` / `ma_long` | `5` / `20` | MA crossover periods |
| `rsi_period` | `14` | RSI lookback period |
| `rsi_oversold` / `rsi_overbought` | `30` / `70` | RSI signal thresholds |
| `stop_loss_pct` | `0.05` | Exit if position loses 5% |
| `take_profit_pct` | `0.10` | Exit if position gains 10% |
| `max_daily_loss_pct` | `0.03` | Halt trading if daily loss exceeds 3% |
| `max_position_pct` | `0.10` | Max 10% of portfolio per stock |
| `check_interval_seconds` | `60` | How often to run strategy |

---

## Going Live

When you are confident in the strategy, set `PAPER_TRADING=false` in your `.env` file.

> **Warning:** Real orders will be placed immediately. Make sure you have tested thoroughly in paper trading mode first.

---

## Project Structure

```
taiwan-trader/
├── main.py                 # Entry point — run this
├── config.py               # All parameters in one place
├── risk.py                 # Position sizing, stop-loss, circuit breaker
├── requirements.txt
├── .env                    # Your credentials (never commit this)
├── broker/
│   └── fubon_client.py     # Fubon SDK wrapper
├── data/
│   └── market_data.py      # Historical price fetcher (yfinance)
├── strategy/
│   ├── base.py             # Signal base class
│   ├── ma_crossover.py     # MA5/MA20 golden cross strategy
│   └── technical.py        # RSI, MACD, Bollinger Bands + combined voting
└── portfolio/
    └── tracker.py          # SQLite trade log, P&L, win rate
```

---

## Output Files

| File | Description |
|---|---|
| `trader.log` | Full activity log with timestamps |
| `portfolio.db` | SQLite database of all trades and open positions |

---

## Checking Portfolio Stats

You can query your trade history anytime without running the bot:

```bash
python -c "from portfolio.tracker import print_summary; print_summary()"
```
