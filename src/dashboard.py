import json
import os
import warnings
from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import yfinance as yf
from plotly.subplots import make_subplots

# ---------------------------------------------------------------------------
# Page config (must be first)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Taiwan Auto Trader",
    page_icon="📈",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Taiwan market color convention: Red = UP, Green = DOWN
# ---------------------------------------------------------------------------

TW_UP   = "#ef5350"
TW_DOWN = "#26a69a"

# ---------------------------------------------------------------------------
# Theme definitions
# ---------------------------------------------------------------------------

THEMES = {
    "dark": {
        "bg":           "#0e1117",
        "secondary_bg": "#1a1f2e",
        "card_bg":      "#1a1f2e",
        "plot_bg":      "#151b27",
        "text":         "#e8eaf0",
        "subtext":      "#a0aec0",
        "border":       "#2d3748",
        "grid":         "#2d3748",
        "hover_bg":     "#1a1f2e",
        "input_bg":     "#1a1f2e",
        "primary":      "#3b82f6",
        "plotly_tmpl":  "plotly_dark",
        "toggle_icon":  "☀️",
        "toggle_label": "淺色模式",
    },
    "light": {
        "bg":           "#ffffff",
        "secondary_bg": "#f1f5f9",
        "card_bg":      "#f1f5f9",
        "plot_bg":      "#ffffff",
        "text":         "#1a202c",
        "subtext":      "#4a5568",
        "border":       "#cbd5e0",
        "grid":         "#e2e8f0",
        "hover_bg":     "#ffffff",
        "input_bg":     "#ffffff",
        "primary":      "#2563eb",
        "plotly_tmpl":  "plotly_white",
        "toggle_icon":  "🌙",
        "toggle_label": "深色模式",
    },
}

# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

if "theme"              not in st.session_state: st.session_state.theme              = "dark"
if "selected_stock"     not in st.session_state: st.session_state.selected_stock     = None
if "active_view"        not in st.session_state: st.session_state.active_view        = "chart"
if "squeeze_results"     not in st.session_state: st.session_state.squeeze_results     = None
if "squeeze_scanned_at"  not in st.session_state: st.session_state.squeeze_scanned_at  = None
if "squeeze_params"      not in st.session_state: st.session_state.squeeze_params      = {}
if "breakout_results"    not in st.session_state: st.session_state.breakout_results    = None
if "breakout_scanned_at" not in st.session_state: st.session_state.breakout_scanned_at = None
if "breakout_params"     not in st.session_state: st.session_state.breakout_params     = {}

t = THEMES[st.session_state.theme]

# ---------------------------------------------------------------------------
# CSS injection
# ---------------------------------------------------------------------------

def inject_css(t: dict):
    st.markdown(f"""
    <style>
        .stApp, html, body {{
            background-color: {t['bg']} !important;
            color: {t['text']} !important;
        }}
        .main .block-container {{ background-color: {t['bg']} !important; padding-top: 1rem; }}
        [data-testid="stSidebar"] {{
            background-color: {t['secondary_bg']} !important;
            border-right: 1px solid {t['border']} !important;
        }}
        [data-testid="stSidebar"] * {{ color: {t['text']} !important; }}
        p, span, label, div, li, td, th {{ color: {t['text']} !important; }}
        h1 {{ color: {t['text']} !important; font-size: 1.8rem !important; font-weight: 700 !important; }}
        h2, h3 {{ color: {t['text']} !important; font-weight: 600 !important; }}
        [data-testid="metric-container"] {{
            background-color: {t['card_bg']} !important;
            border: 1px solid {t['border']} !important;
            border-radius: 10px !important;
            padding: 14px 18px !important;
        }}
        [data-testid="stMetricLabel"] > div {{
            color: {t['subtext']} !important; font-size: 0.82rem !important;
            font-weight: 500 !important; text-transform: uppercase !important;
        }}
        [data-testid="stMetricValue"] > div {{
            color: {t['text']} !important; font-size: 1.55rem !important; font-weight: 700 !important;
        }}
        [data-testid="stMetricDelta"] svg {{ display: none; }}
        [data-testid="stMetricDelta"] > div {{ font-size: 0.82rem !important; font-weight: 500 !important; }}
        [data-testid="stSelectbox"] > div > div {{
            background-color: {t['input_bg']} !important; border: 1px solid {t['border']} !important;
            color: {t['text']} !important; border-radius: 6px !important;
        }}
        [data-testid="stSelectbox"] label {{ color: {t['subtext']} !important; font-size: 0.85rem !important; }}
        [data-testid="stTextInput"] input {{
            background-color: {t['input_bg']} !important; border: 1px solid {t['border']} !important;
            color: {t['text']} !important; border-radius: 6px !important;
        }}
        [data-testid="stTextInput"] label {{ color: {t['subtext']} !important; font-size: 0.85rem !important; }}
        [data-testid="stCheckbox"] label {{ color: {t['text']} !important; }}
        [data-testid="stDataFrame"] {{
            border: 1px solid {t['border']} !important;
            border-radius: 8px !important; overflow: hidden !important;
        }}
        hr {{ border-color: {t['border']} !important; opacity: 0.5; }}
        [data-testid="stInfo"] {{
            background-color: {t['card_bg']} !important;
            border: 1px solid {t['primary']} !important;
            border-radius: 8px !important;
        }}
        [data-testid="stInfo"] * {{ color: {t['text']} !important; }}
        /* Buttons */
        div[data-testid="stButton"] > button {{
            background-color: {t['card_bg']} !important;
            color: {t['text']} !important;
            border: 1px solid {t['border']} !important;
            border-radius: 20px !important;
            padding: 6px 16px !important;
            font-size: 0.88rem !important;
            font-weight: 600 !important;
            width: 100% !important;
        }}
        div[data-testid="stButton"] > button:hover {{
            border-color: {t['primary']} !important;
            color: {t['primary']} !important;
        }}
        /* Fav card */
        .fav-card {{
            background-color: {t['card_bg']};
            border: 1px solid {t['border']};
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 4px;
            transition: border-color 0.2s;
        }}
        .fav-card:hover {{ border-color: {t['primary']}; }}
    </style>
    """, unsafe_allow_html=True)

inject_css(t)

# ---------------------------------------------------------------------------
# Favorites persistence
# ---------------------------------------------------------------------------

FAVORITES_FILE = "favorites.json"

def load_favorites() -> list:
    if os.path.exists(FAVORITES_FILE):
        try:
            with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_favorites(favs: list):
    with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
        json.dump(favs, f, ensure_ascii=False, indent=2)

# ---------------------------------------------------------------------------
# Fallback + full stock list
# ---------------------------------------------------------------------------

FALLBACK_WATCHLIST = {
    "2330 台積電": "2330.TW", "2317 鴻海": "2317.TW",
    "2454 聯發科": "2454.TW", "2881 富邦金": "2881.TW",
    "2303 聯電":   "2303.TW", "2882 國泰金": "2882.TW",
    "2308 台達電": "2308.TW", "3008 大立光": "3008.TW",
}

@st.cache_data(ttl=86400, show_spinner="載入台股清單…")
def load_all_tw_stocks() -> dict:
    warnings.filterwarnings("ignore", message="Unverified HTTPS")
    result = {}
    try:
        resp = requests.get(
            "https://openapi.twse.com.tw/v1/opendata/t187ap03_L",
            timeout=10, verify=False,
        )
        for row in resp.json():
            code = str(row.get("公司代號", "")).strip()
            name = str(row.get("公司簡稱", "")).strip()
            if code.isdigit() and name:
                result[f"{code} {name}"] = f"{code}.TW"
    except Exception:
        pass
    try:
        resp = requests.get(
            "https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O",
            timeout=10, verify=False,
        )
        for row in resp.json():
            code = str(row.get("SecuritiesCompanyCode", "")).strip()
            name = str(row.get("CompanyAbbreviation", "")).strip()
            if code.isdigit() and name and f"{code} {name}" not in result:
                result[f"{code} {name}"] = f"{code}.TWO"
    except Exception:
        pass
    return dict(sorted(result.items(), key=lambda x: x[0].split()[0])) if result else FALLBACK_WATCHLIST

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

_TW_TZ = timezone(timedelta(hours=8))  # Asia/Taipei — UTC+8, no DST


def _fetch_twse_latest(stock_code: str, is_otc: bool, date) -> dict:
    """Fallback: fetch OHLCV from TWSE/TPEX API when yfinance returns NaN prices for the latest date."""
    warnings.filterwarnings("ignore", message="Unverified HTTPS")
    try:
        if is_otc:
            roc_year = date.year - 1911
            d_str = f"{roc_year}/{date.month:02d}/{date.day:02d}"
            url = (
                f"https://www.tpex.org.tw/web/stock/aftertrading/daily_trading_info/"
                f"st43_result.php?l=zh-tw&d={d_str}&s={stock_code}&o=json"
            )
            resp = requests.get(url, timeout=10, verify=False)
            rows = resp.json().get("aaData", [])
            if rows:
                row = rows[-1]
                return {
                    "Open":   float(str(row[3]).replace(",", "")),
                    "High":   float(str(row[4]).replace(",", "")),
                    "Low":    float(str(row[5]).replace(",", "")),
                    "Close":  float(str(row[6]).replace(",", "")),
                    "Volume": float(str(row[1]).replace(",", "")),
                }
        else:
            date_str = date.strftime("%Y%m%d")
            url = (
                f"https://www.twse.com.tw/exchangeReport/STOCK_DAY"
                f"?response=json&date={date_str}&stockNo={stock_code}"
            )
            resp = requests.get(url, timeout=10, verify=False)
            data = resp.json()
            if data.get("stat") != "OK":
                return {}
            roc_date = f"{date.year - 1911}/{date.month:02d}/{date.day:02d}"
            for row in data.get("data", []):
                if row[0] == roc_date:
                    return {
                        "Open":   float(str(row[3]).replace(",", "")),
                        "High":   float(str(row[4]).replace(",", "")),
                        "Low":    float(str(row[5]).replace(",", "")),
                        "Close":  float(str(row[6]).replace(",", "")),
                        "Volume": float(str(row[1]).replace(",", "")),
                    }
    except Exception:
        pass
    return {}


@st.cache_data(ttl=60)
def load_data(ticker: str, days: int) -> pd.DataFrame:
    today = datetime.now(_TW_TZ).date()
    # end is exclusive in yfinance; using tomorrow in TW time guarantees today is included
    end_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")
    if days == 0:
        df = yf.download(ticker, period="max", progress=False, auto_adjust=True)
    else:
        start_str = (today - timedelta(days=days + 15)).strftime("%Y-%m-%d")
        df = yf.download(ticker, start=start_str, end=end_str, progress=False, auto_adjust=True)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    # Fill NaN prices for the latest date using TWSE/TPEX API
    if not df.empty and pd.isna(df["Close"].iloc[-1]):
        last_date = df.index[-1].date()
        is_otc = ticker.endswith(".TWO")
        code = ticker.replace(".TWO", "").replace(".TW", "")
        fallback = _fetch_twse_latest(code, is_otc, last_date)
        if fallback:
            for col, val in fallback.items():
                if col in df.columns:
                    df.at[df.index[-1], col] = val

    return df.dropna(subset=["Open", "High", "Low", "Close"])

@st.cache_data(ttl=60)
def load_quick(ticker: str) -> dict:
    """Returns latest price, prev close, and MA trend for a favorites card."""
    try:
        df = yf.download(ticker, period="1mo", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()
        if len(df) < 2:
            return {}
        close    = df["Close"].squeeze()
        latest   = float(close.iloc[-1])
        prev     = float(close.iloc[-2])
        change   = latest - prev
        pct      = change / prev * 100
        ma5      = float(close.rolling(5).mean().iloc[-1])
        ma20     = float(close.rolling(20).mean().iloc[-1])
        delta    = close.diff()
        gain     = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
        loss     = (-delta.clip(upper=0)).ewm(com=13, min_periods=14).mean()
        rsi_s    = 100 - (100 / (1 + gain / loss.replace(0, float("nan"))))
        rsi      = float(rsi_s.iloc[-1]) if not rsi_s.isna().all() else 0.0
        open_p   = float(df["Open"].squeeze().iloc[-1])
        high_p   = float(df["High"].squeeze().iloc[-1])
        low_p    = float(df["Low"].squeeze().iloc[-1])
        vol      = float(df["Volume"].squeeze().iloc[-1])
        vol_avg  = float(df["Volume"].squeeze().rolling(20).mean().iloc[-1])
        return {
            "price": latest, "change": change, "pct": pct,
            "ma5": ma5, "ma20": ma20, "rsi": rsi,
            "open": open_p, "high": high_p, "low": low_p,
            "volume": vol, "vol_avg20": vol_avg,
        }
    except Exception:
        return {}


@st.cache_data(ttl=60)
def load_intraday(ticker: str) -> pd.DataFrame:
    """Fetch 1-minute intraday data for today's Taiwan trading session (UTC+8)."""
    try:
        df = yf.download(ticker, period="1d", interval="1m", progress=False, auto_adjust=True)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna(subset=["Close"])
        if df.empty:
            return pd.DataFrame()
        if df.index.tz is not None:
            df.index = df.index.tz_convert("Asia/Taipei")
        else:
            df.index = df.index.tz_localize("UTC").tz_convert("Asia/Taipei")
        return df
    except Exception:
        return pd.DataFrame()


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------

def base_layout(height: int = 820) -> dict:
    return dict(
        height=height, template=t["plotly_tmpl"],
        paper_bgcolor=t["bg"], plot_bgcolor=t["plot_bg"],
        font=dict(color=t["text"], size=12),
        legend=dict(orientation="h", y=1.01, x=0,
                    font=dict(color=t["text"], size=12),
                    bgcolor="rgba(0,0,0,0)", bordercolor=t["border"], borderwidth=1),
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=50, b=10),
        hovermode="x unified",
        hoverlabel=dict(bgcolor=t["secondary_bg"], font_color=t["text"], bordercolor=t["primary"]),
    )

def style_axes(fig, rows: int):
    for i in range(1, rows + 1):
        fig.update_xaxes(showgrid=True, gridcolor=t["grid"], gridwidth=0.5,
                         tickfont=dict(color=t["subtext"], size=11), linecolor=t["border"], row=i, col=1)
        fig.update_yaxes(showgrid=True, gridcolor=t["grid"], gridwidth=0.5,
                         tickfont=dict(color=t["subtext"], size=11), linecolor=t["border"], row=i, col=1)
    for ann in fig.layout.annotations:
        ann.font = dict(color=t["text"], size=13)

# ---------------------------------------------------------------------------
# 均線糾結 scanner
# ---------------------------------------------------------------------------

def _scan_squeeze_batch(stocks_dict: dict, ma_periods: tuple, threshold_pct: float, pb) -> pd.DataFrame:
    """Batch-download stocks and return those whose MAs are within threshold_pct of each other."""
    all_labels  = list(stocks_dict.keys())
    all_tickers = list(stocks_dict.values())
    results: list[dict] = []
    CHUNK = 60
    n     = len(all_tickers)

    for start in range(0, n, CHUNK):
        chunk_labels  = all_labels[start:start + CHUNK]
        chunk_tickers = all_tickers[start:start + CHUNK]
        done          = min(start + CHUNK, n)
        pb.progress(done / n, text=f"掃描 {done:,} / {n:,} 支股票…")

        try:
            raw = yf.download(chunk_tickers, period="4mo",
                              progress=False, auto_adjust=True, group_by="ticker")
        except Exception:
            continue

        for label, tkr in zip(chunk_labels, chunk_tickers):
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    if tkr not in raw.columns.get_level_values(0):
                        continue
                    close = raw[tkr]["Close"].squeeze().dropna()
                else:
                    close = raw["Close"].squeeze().dropna()

                if len(close) < max(ma_periods):
                    continue
                latest = float(close.iloc[-1])
                if latest <= 0:
                    continue

                mas = {p: float(close.rolling(p).mean().iloc[-1]) for p in ma_periods}
                if any(pd.isna(v) for v in mas.values()):
                    continue

                ma_vals = list(mas.values())
                spread  = (max(ma_vals) - min(ma_vals)) / latest * 100

                if spread <= threshold_pct:
                    row: dict = {
                        "代號": label.split()[0],
                        "名稱": " ".join(label.split()[1:]),
                        "最新收盤": round(latest, 2),
                        **{f"MA{p}": round(v, 2) for p, v in sorted(mas.items())},
                        "糾結程度(%)": round(spread, 2),
                    }
                    results.append(row)
            except Exception:
                continue

    if not results:
        return pd.DataFrame()
    cols = ["代號", "名稱", "最新收盤"] + [f"MA{p}" for p in sorted(ma_periods)] + ["糾結程度(%)"]
    return pd.DataFrame(results)[cols].sort_values("糾結程度(%)", ignore_index=True)

# ---------------------------------------------------------------------------
# 強勢突破 scanner  (MA bullish alignment + price breakout + volume surge)
# ---------------------------------------------------------------------------

def _scan_breakout_batch(
    stocks_dict: dict,
    breakout_days: int,
    vol_multiplier: float,
    rsi_max: float,
    pb,
) -> pd.DataFrame:
    """Return stocks satisfying: MA5>MA20>MA60, close>N-day high, volume>avg*mult, RSI<rsi_max."""
    all_labels  = list(stocks_dict.keys())
    all_tickers = list(stocks_dict.values())
    results: list[dict] = []
    CHUNK = 60
    n     = len(all_tickers)

    for start in range(0, n, CHUNK):
        chunk_labels  = all_labels[start:start + CHUNK]
        chunk_tickers = all_tickers[start:start + CHUNK]
        done          = min(start + CHUNK, n)
        pb.progress(done / n, text=f"掃描 {done:,} / {n:,} 支股票…")

        try:
            raw = yf.download(chunk_tickers, period="6mo",
                              progress=False, auto_adjust=True, group_by="ticker")
        except Exception:
            continue

        for label, tkr in zip(chunk_labels, chunk_tickers):
            try:
                if isinstance(raw.columns, pd.MultiIndex):
                    if tkr not in raw.columns.get_level_values(0):
                        continue
                    sub = raw[tkr].dropna()
                else:
                    sub = raw.dropna()

                if len(sub) < 65:
                    continue

                close  = sub["Close"].squeeze()
                volume = sub["Volume"].squeeze()

                latest     = float(close.iloc[-1])
                latest_vol = float(volume.iloc[-1])
                if latest <= 0 or latest_vol <= 0:
                    continue

                # ── 1. MA bullish alignment ──────────────────────
                ma5  = float(close.rolling(5).mean().iloc[-1])
                ma20 = float(close.rolling(20).mean().iloc[-1])
                ma60 = float(close.rolling(60).mean().iloc[-1])
                if not (ma5 > ma20 > ma60):
                    continue

                # ── 2. Price breakout above N-day high ───────────
                lookback   = close.iloc[-(breakout_days + 1):-1]
                prev_high  = float(lookback.max())
                if latest <= prev_high:
                    continue
                breakout_pct = (latest - prev_high) / prev_high * 100

                # ── 3. Volume surge ──────────────────────────────
                vol_avg = float(volume.iloc[-21:-1].mean())
                if vol_avg <= 0:
                    continue
                vol_ratio = latest_vol / vol_avg
                if vol_ratio < vol_multiplier:
                    continue

                # ── 4. RSI not overbought ────────────────────────
                delta = close.diff()
                gain  = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
                loss  = (-delta.clip(upper=0)).ewm(com=13, min_periods=14).mean()
                rsi   = float((100 - 100 / (1 + gain / loss.replace(0, float("nan")))).iloc[-1])
                if pd.isna(rsi) or rsi > rsi_max:
                    continue

                # ── 5. KD (Stochastic) ───────────────────────────
                low9  = sub["Low"].squeeze().rolling(9).min()
                high9 = sub["High"].squeeze().rolling(9).max()
                rsv   = ((close - low9) / (high9 - low9).replace(0, float("nan")) * 100).fillna(50)
                k_ser = rsv.ewm(com=2, adjust=False).mean()   # 1/3 smoothing ≈ alpha=1/3, com=2
                d_ser = k_ser.ewm(com=2, adjust=False).mean()
                k_now = float(k_ser.iloc[-1])
                d_now = float(d_ser.iloc[-1])

                change_pct = (latest - float(close.iloc[-2])) / float(close.iloc[-2]) * 100

                results.append({
                    "代號":      label.split()[0],
                    "名稱":      " ".join(label.split()[1:]),
                    "最新收盤":  round(latest, 2),
                    "漲跌幅(%)": round(change_pct, 2),
                    "MA5":       round(ma5, 2),
                    "MA20":      round(ma20, 2),
                    "MA60":      round(ma60, 2),
                    "成交量比(×)": round(vol_ratio, 2),
                    "突破幅度(%)": round(breakout_pct, 2),
                    "RSI":       round(rsi, 1),
                    "K":         round(k_now, 1),
                    "D":         round(d_now, 1),
                })
            except Exception:
                continue

    if not results:
        return pd.DataFrame()
    cols = ["代號", "名稱", "最新收盤", "漲跌幅(%)", "MA5", "MA20", "MA60",
            "成交量比(×)", "突破幅度(%)", "RSI", "K", "D"]
    return pd.DataFrame(results)[cols].sort_values("成交量比(×)", ascending=False, ignore_index=True)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

st.sidebar.markdown("### ⚙️ 設定")

if st.sidebar.button(f"{t['toggle_icon']}  {t['toggle_label']}"):
    st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"
    st.rerun()

if st.sidebar.button("🔄 重新整理資料"):
    load_data.clear()
    load_quick.clear()
    st.rerun()

st.sidebar.divider()

ALL_STOCKS  = load_all_tw_stocks()
total_count = len(ALL_STOCKS)
all_keys    = list(ALL_STOCKS.keys())

search = st.sidebar.text_input("🔍 搜尋股票", placeholder="輸入代號或名稱，例如 2330 或 台積電")
if search.strip():
    kw       = search.strip().lower()
    filtered = {k: v for k, v in ALL_STOCKS.items() if kw in k.lower()}
else:
    filtered = ALL_STOCKS

if not filtered:
    st.sidebar.warning("No stocks matched.")
    filtered = ALL_STOCKS

st.sidebar.caption(f"顯示 {len(filtered):,} / {total_count:,} 支股票")

# Honour navigate-from-favorites selection
default_label = st.session_state.selected_stock
filtered_keys = list(filtered.keys())
default_idx   = filtered_keys.index(default_label) if default_label in filtered_keys else 0

selected_label = st.sidebar.selectbox("股票", filtered_keys, index=default_idx)
st.session_state.selected_stock = selected_label
ticker     = filtered[selected_label]
stock_code = selected_label.split()[0]

# --- Star / Favourite toggle ---
favs   = load_favorites()
is_fav = selected_label in favs

if st.sidebar.button("⭐ 已收藏  (點擊移除)" if is_fav else "☆  加入收藏"):
    if is_fav:
        favs.remove(selected_label)
    else:
        if selected_label not in favs:
            favs.append(selected_label)
    save_favorites(favs)
    st.rerun()

st.sidebar.divider()
st.sidebar.markdown("**技術指標**")
show_ma     = st.sidebar.checkbox("均線 (MA5 / MA20 / MA60)", value=True)
show_bb     = st.sidebar.checkbox("布林通道 (BB20)", value=True)
show_rsi    = st.sidebar.checkbox("RSI (14)", value=True)
show_macd   = st.sidebar.checkbox("MACD (12/26/9)", value=True)
show_volume = st.sidebar.checkbox("成交量", value=True)

period_options = {"1個月": 30, "3個月": 90, "6個月": 180, "1年": 365, "2年": 730, "5年": 1825, "全部": 0}
selected_period = st.sidebar.selectbox("期間", list(period_options.keys()), index=1)
days = period_options[selected_period]

# ---------------------------------------------------------------------------
# Navigation — two buttons with on_click (instant, no lag)
# ---------------------------------------------------------------------------

def _go_chart():     st.session_state.active_view = "chart"
def _go_favorites(): st.session_state.active_view = "favorites"
def _go_squeeze():   st.session_state.active_view = "squeeze"
def _go_breakout():  st.session_state.active_view = "breakout"

def _nav_to_stock(full_label: str):
    st.session_state.selected_stock = full_label
    st.session_state.active_view    = "chart"

is_chart     = st.session_state.active_view == "chart"
is_favorites = st.session_state.active_view == "favorites"
is_squeeze   = st.session_state.active_view == "squeeze"
is_breakout  = st.session_state.active_view == "breakout"

nav_c1, nav_c2, nav_c3, nav_c4, *_ = st.columns([1, 1, 1.2, 1.3, 1.5])
with nav_c1:
    st.button(
        "📈 市場",
        on_click=_go_chart,
        use_container_width=True,
        type="primary" if is_chart else "secondary",
    )
with nav_c2:
    st.button(
        f"⭐ 收藏 ({len(favs)})",
        on_click=_go_favorites,
        use_container_width=True,
        type="primary" if is_favorites else "secondary",
    )
with nav_c3:
    st.button(
        "📊 均線糾結",
        on_click=_go_squeeze,
        use_container_width=True,
        type="primary" if is_squeeze else "secondary",
    )
with nav_c4:
    st.button(
        "🚀 強勢突破",
        on_click=_go_breakout,
        use_container_width=True,
        type="primary" if is_breakout else "secondary",
    )

st.markdown(f"<hr style='margin:0.4rem 0 1rem; border-color:{t['border']};'>", unsafe_allow_html=True)

# ============================================================
# VIEW 1 — Chart
# ============================================================

if st.session_state.active_view == "chart":

    star_icon = "⭐" if is_fav else "☆"
    st.title(f"{star_icon} {selected_label}")

    df = load_data(ticker, days)

    if df.empty:
        st.error(f"找不到 {ticker} 的資料，請檢查網路連線。")
        st.stop()

    close = df["Close"].squeeze()
    df["MA5"]  = close.rolling(5).mean()
    df["MA20"] = close.rolling(20).mean()
    df["MA60"] = close.rolling(60).mean()
    df["BB_mid"]   = close.rolling(20).mean()
    df["BB_std"]   = close.rolling(20).std()
    df["BB_upper"] = df["BB_mid"] + 2 * df["BB_std"]
    df["BB_lower"] = df["BB_mid"] - 2 * df["BB_std"]
    delta = close.diff()
    gain  = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
    loss  = (-delta.clip(upper=0)).ewm(com=13, min_periods=14).mean()
    df["RSI"]        = 100 - (100 / (1 + gain / loss.replace(0, float("nan"))))
    ema12            = close.ewm(span=12, adjust=False).mean()
    ema26            = close.ewm(span=26, adjust=False).mean()
    df["MACD"]       = ema12 - ema26
    df["MACD_signal"]= df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"]  = df["MACD"] - df["MACD_signal"]

    latest     = float(close.iloc[-1])
    prev       = float(close.iloc[-2])
    change     = latest - prev
    change_pct = change / prev * 100
    rsi_now    = float(df["RSI"].iloc[-1]) if not df["RSI"].isna().all() else 0.0
    ma5_now    = float(df["MA5"].iloc[-1])
    ma20_now   = float(df["MA20"].iloc[-1])

    # String labels for x-axis — Plotly treats as categories, no weekend/holiday gaps
    date_labels = df.index.strftime("%Y-%m-%d").tolist()

    def badge(s): return {"BUY": "🔴 買進", "SELL": "🟢 賣出", "HOLD": "⚪ 觀望"}.get(s, s)

    # ── Sub-tabs inside 市場 view  (日線圖 is tab 0 → Streamlit default) ──
    tab_daily, tab_tech = st.tabs(["📊 日線圖", "📈 技術指標"])

    # ===========================================================
    # Sub-tab 1 — 日線圖 (Daily K-line, default)
    # ===========================================================
    with tab_daily:
        latest_date = df.index[-1].strftime("%Y-%m-%d")
        open_p   = float(df["Open"].squeeze().iloc[-1])
        high_p   = float(df["High"].squeeze().iloc[-1])
        low_p    = float(df["Low"].squeeze().iloc[-1])
        vol_p    = float(df["Volume"].squeeze().iloc[-1])
        vol_avg  = float(df["Volume"].squeeze().rolling(20).mean().iloc[-1])
        vol_ratio = vol_p / vol_avg if vol_avg > 0 else 0.0

        st.markdown(
            f"<p style='color:{t['subtext']}; font-size:0.85rem; margin:0 0 0.6rem;'>"
            f"最新資料日期：{latest_date}</p>",
            unsafe_allow_html=True,
        )

        d1, d2, d3, d4, d5, d6 = st.columns(6)
        d1.metric("收盤價", f"{latest:.2f}", f"{change:+.2f} ({change_pct:+.2f}%)")
        d2.metric("開盤", f"{open_p:.2f}")
        d3.metric("最高", f"{high_p:.2f}")
        d4.metric("最低", f"{low_p:.2f}")
        d5.metric("成交量 (張)", f"{vol_p / 1000:,.0f}")
        d6.metric("量比 (×20均)", f"{vol_ratio:.2f}×")

        st.markdown(
            f"<hr style='margin:0.5rem 0 0.8rem; border-color:{t['border']};'>",
            unsafe_allow_html=True,
        )

        # ── Intraday minute chart (即時走勢) ─────────────────────
        df_intra = load_intraday(ticker)

        if df_intra.empty:
            st.info("今日尚無即時分鐘資料（市場可能未開盤或資料延遲）")
        else:
            intra_close = df_intra["Close"].squeeze()
            intra_vol   = df_intra["Volume"].squeeze()

            # VWAP (均價)
            cum_vol = intra_vol.cumsum()
            vwap    = (intra_close * intra_vol).cumsum() / cum_vol.replace(0, float("nan"))

            time_labels  = df_intra.index.strftime("%H:%M").tolist()
            latest_intra = float(intra_close.iloc[-1])
            line_color   = TW_UP if latest_intra >= prev else TW_DOWN
            fill_color   = "rgba(239,83,80,0.12)" if latest_intra >= prev else "rgba(38,166,154,0.12)"
            vol_colors   = [TW_UP if float(p) >= prev else TW_DOWN for p in intra_close]

            fig_intra = make_subplots(
                rows=2, cols=1, shared_xaxes=True,
                vertical_spacing=0.04, row_heights=[0.75, 0.25],
                subplot_titles=["即時走勢", "成交量（張）"],
            )

            # Dashed previous-close reference line
            fig_intra.add_hline(
                y=prev,
                line=dict(color=t["subtext"], width=1.5, dash="dash"),
                row=1, col=1,
            )

            # Ghost trace at prev close level — used as fill baseline
            fig_intra.add_trace(go.Scatter(
                x=time_labels, y=[prev] * len(time_labels),
                line=dict(color="rgba(0,0,0,0)", width=0),
                showlegend=False, hoverinfo="skip",
            ), row=1, col=1)

            # Price line filled down to prev close
            fig_intra.add_trace(go.Scatter(
                x=time_labels, y=intra_close, name="成交價",
                line=dict(color=line_color, width=1.5),
                fill="tonexty", fillcolor=fill_color,
                hovertemplate="%{x}  %{y:.2f}<extra></extra>",
            ), row=1, col=1)

            # VWAP line
            fig_intra.add_trace(go.Scatter(
                x=time_labels, y=vwap, name="均價",
                line=dict(color="#f59e0b", width=1.2),
                hovertemplate="%{x}  均價 %{y:.2f}<extra></extra>",
            ), row=1, col=1)

            # Volume bars
            fig_intra.add_trace(go.Bar(
                x=time_labels, y=intra_vol / 1000, name="成交量(張)",
                marker_color=vol_colors, opacity=0.7,
                hovertemplate="%{x}  %{y:,.1f} 張<extra></extra>",
            ), row=2, col=1)
            fig_intra.update_yaxes(tickformat=",.1f", ticksuffix=" 張", row=2, col=1)

            fig_intra.update_layout(**base_layout(height=520))
            style_axes(fig_intra, 2)
            fig_intra.update_xaxes(type="category", nticks=8)
            st.plotly_chart(fig_intra, use_container_width=True)

    # ===========================================================
    # Sub-tab 2 — 技術指標 (full multi-panel technical chart)
    # ===========================================================
    with tab_tech:
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("最新收盤", f"{latest:.2f}", f"{change:+.2f} ({change_pct:+.2f}%)")
        c2.metric("區間高點", f"{float(close.max()):.2f}")
        c3.metric("區間低點", f"{float(close.min()):.2f}")
        c4.metric("RSI (14)", f"{rsi_now:.1f}",
                  "超買" if rsi_now > 70 else ("超賣" if rsi_now < 30 else "中性"))
        c5.metric("均線趨勢", "上漲趨勢 🔴" if ma5_now > ma20_now else "下跌趨勢 🟢")

        st.divider()

        # Build subplots
        row_heights    = [0.5]; subplot_titles = ["股價"]; num_rows = 1
        if show_rsi:    row_heights.append(0.15); subplot_titles.append("RSI (14)"); num_rows += 1
        if show_macd:   row_heights.append(0.20); subplot_titles.append("MACD");     num_rows += 1
        if show_volume: row_heights.append(0.15); subplot_titles.append("成交量（張）"); num_rows += 1

        fig = make_subplots(rows=num_rows, cols=1, shared_xaxes=True,
                            vertical_spacing=0.04, row_heights=row_heights,
                            subplot_titles=subplot_titles)

        fig.add_trace(go.Candlestick(
            x=date_labels,
            open=df["Open"].squeeze(), high=df["High"].squeeze(),
            low=df["Low"].squeeze(),   close=close, name="股價",
            increasing_line_color=TW_UP,   increasing_fillcolor=TW_UP,
            decreasing_line_color=TW_DOWN, decreasing_fillcolor=TW_DOWN,
        ), row=1, col=1)

        if show_ma:
            fig.add_trace(go.Scatter(x=date_labels, y=df["MA5"],  name="MA5",
                                     line=dict(color="#f59e0b", width=1.8)), row=1, col=1)
            fig.add_trace(go.Scatter(x=date_labels, y=df["MA20"], name="MA20",
                                     line=dict(color="#3b82f6", width=1.8)), row=1, col=1)
            fig.add_trace(go.Scatter(x=date_labels, y=df["MA60"], name="MA60",
                                     line=dict(color="#a855f7", width=1.8)), row=1, col=1)

        if show_bb:
            fig.add_trace(go.Scatter(x=date_labels, y=df["BB_upper"], name="布林上軌",
                                     line=dict(color="rgba(168,85,247,0.7)", width=1.2, dash="dash")), row=1, col=1)
            fig.add_trace(go.Scatter(x=date_labels, y=df["BB_lower"], name="布林下軌",
                                     line=dict(color="rgba(168,85,247,0.7)", width=1.2, dash="dash"),
                                     fill="tonexty", fillcolor="rgba(168,85,247,0.06)"), row=1, col=1)
            fig.add_trace(go.Scatter(x=date_labels, y=df["BB_mid"], name="布林中線",
                                     line=dict(color="rgba(168,85,247,0.5)", width=1)), row=1, col=1)

        cur = 2
        if show_rsi:
            fig.add_trace(go.Scatter(x=date_labels, y=df["RSI"], name="RSI",
                                     line=dict(color="#f59e0b", width=1.8)), row=cur, col=1)
            fig.add_hline(y=70, line=dict(color=TW_UP,   width=1, dash="dot"), row=cur, col=1)
            fig.add_hline(y=30, line=dict(color=TW_DOWN, width=1, dash="dot"), row=cur, col=1)
            fig.add_hrect(y0=70, y1=100, fillcolor=TW_UP,   opacity=0.06, row=cur, col=1)
            fig.add_hrect(y0=0,  y1=30,  fillcolor=TW_DOWN, opacity=0.06, row=cur, col=1)
            cur += 1

        if show_macd:
            hist_colors = [TW_UP if v >= 0 else TW_DOWN for v in df["MACD_hist"]]
            fig.add_trace(go.Bar(x=date_labels, y=df["MACD_hist"], name="柱狀圖",
                                 marker_color=hist_colors, opacity=0.75), row=cur, col=1)
            fig.add_trace(go.Scatter(x=date_labels, y=df["MACD"],        name="MACD",
                                     line=dict(color="#3b82f6", width=1.8)), row=cur, col=1)
            fig.add_trace(go.Scatter(x=date_labels, y=df["MACD_signal"], name="訊號線",
                                     line=dict(color="#f59e0b", width=1.8)), row=cur, col=1)
            cur += 1

        if show_volume:
            vol_colors = [TW_UP if c >= o else TW_DOWN
                          for c, o in zip(df["Close"].squeeze(), df["Open"].squeeze())]
            fig.add_trace(go.Bar(x=date_labels, y=df["Volume"].squeeze() / 1000, name="成交量(張)",
                                 marker_color=vol_colors, opacity=0.7,
                                 hovertemplate="%{x}  %{y:,.0f} 張<extra></extra>"), row=cur, col=1)
            fig.update_yaxes(tickformat=",.0f", ticksuffix=" 張", row=cur, col=1)

        fig.update_layout(**base_layout(height=820))
        style_axes(fig, num_rows)
        # Force categorical axis so only actual trading days appear — no weekend/holiday gaps
        fig.update_xaxes(type="category", nticks=10)
        st.plotly_chart(fig, use_container_width=True)

        # Signal table
        st.subheader("📊 當前訊號摘要")
        rsi_val      = float(df["RSI"].iloc[-1])
        macd_val     = float(df["MACD"].iloc[-1])
        sig_val      = float(df["MACD_signal"].iloc[-1])
        price_val    = float(close.iloc[-1])
        bb_upper_val = float(df["BB_upper"].iloc[-1])
        bb_lower_val = float(df["BB_lower"].iloc[-1])
        signals_df = pd.DataFrame([
            {"指標": "均線交叉 (MA5/MA20)",  "數值": f"MA5={ma5_now:.2f}  |  MA20={ma20_now:.2f}",           "訊號": badge("BUY" if ma5_now > ma20_now else "SELL")},
            {"指標": "RSI (14)",             "數值": f"{rsi_val:.1f}",                                        "訊號": badge("SELL" if rsi_val>70 else ("BUY" if rsi_val<30 else "HOLD"))},
            {"指標": "MACD (12/26/9)",       "數值": f"MACD={macd_val:.4f}  |  訊號={sig_val:.4f}",          "訊號": badge("BUY" if macd_val>sig_val else "SELL")},
            {"指標": "布林通道 (20)",         "數值": f"上軌={bb_upper_val:.2f}  |  下軌={bb_lower_val:.2f}", "訊號": badge("BUY" if price_val<bb_lower_val else ("SELL" if price_val>bb_upper_val else "HOLD"))},
        ])
        st.dataframe(signals_df, use_container_width=True, hide_index=True)


# ============================================================
# VIEW 2 — 收藏 (Favorites)
# ============================================================

elif st.session_state.active_view == "favorites":
    favs = load_favorites()   # reload in case they changed in tab 1

    if not favs:
        st.markdown(f"""
        <div style="text-align:center; padding:60px 20px; color:{t['subtext']};">
            <div style="font-size:3rem;">☆</div>
            <div style="font-size:1.2rem; margin-top:12px; font-weight:600;">收藏清單是空的</div>
            <div style="margin-top:8px; font-size:0.9rem;">
                到「📈 市場」頁面選擇股票，點擊側邊欄的 ☆ 加入收藏
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"### ⭐ 我的收藏  &nbsp; <span style='font-size:0.9rem; color:{t['subtext']};'>({len(favs)} 支股票)</span>",
                    unsafe_allow_html=True)
        st.markdown("")

        COLS = 4   # cards per row
        rows = [favs[i:i + COLS] for i in range(0, len(favs), COLS)]

        for row in rows:
            cols = st.columns(COLS)
            for col, label in zip(cols, row):
                with col:
                    tkr  = ALL_STOCKS.get(label, "")
                    code = label.split()[0]
                    name = " ".join(label.split()[1:])
                    data = load_quick(tkr) if tkr else {}

                    if data:
                        price     = data["price"]
                        chg       = data["change"]
                        pct       = data["pct"]
                        is_up     = chg >= 0
                        clr       = TW_UP if is_up else TW_DOWN
                        arrow     = "▲" if is_up else "▼"
                        trend     = "上漲趨勢 🔴" if data["ma5"] > data["ma20"] else "下跌趨勢 🟢"
                        rsi_v     = data["rsi"]
                        rsi_lbl   = ("超買" if rsi_v > 70 else ("超賣" if rsi_v < 30 else "中性"))
                        open_p    = data.get("open", 0.0)
                        high_p    = data.get("high", 0.0)
                        low_p     = data.get("low", 0.0)
                        vol_avg_v = data.get("vol_avg20", 0.0)
                        vol_ratio = data.get("volume", 0.0) / vol_avg_v if vol_avg_v > 0 else 0.0
                    else:
                        price = chg = pct = 0.0
                        clr   = t["subtext"]
                        arrow = "–"
                        trend = "–"
                        rsi_v = 0.0
                        rsi_lbl = "–"
                        open_p = high_p = low_p = vol_ratio = 0.0

                    ohlc_row = (
                        f'<span style="color:{t["subtext"]};">開</span> '
                        f'<span style="color:{t["text"]}; font-weight:600;">{open_p:.2f}</span>'
                        f'&ensp;<span style="color:{TW_UP};">高 {high_p:.2f}</span>'
                        f'&ensp;<span style="color:{TW_DOWN};">低 {low_p:.2f}</span>'
                    ) if open_p else "–"
                    vol_txt = f"{vol_ratio:.1f}× 均量" if vol_ratio else "–"

                    st.markdown(f"""
                    <div class="fav-card">
                        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                            <div>
                                <span style="font-size:1.3rem; font-weight:700; color:{t['text']};">{code}</span>
                                <span style="font-size:0.8rem; color:{t['subtext']}; margin-left:6px;">{name}</span>
                            </div>
                            <span style="font-size:1.1rem; color:#f59e0b;">⭐</span>
                        </div>
                        <div style="font-size:1.7rem; font-weight:700; color:{clr}; margin:10px 0 2px;">
                            {f"{price:.2f}" if price else "–"}
                        </div>
                        <div style="font-size:0.95rem; color:{clr}; font-weight:700;">
                            {arrow} {f"{chg:+.2f} ({pct:+.2f}%)" if price else "無資料"}
                        </div>
                        <div style="margin-top:8px; font-size:0.78rem; line-height:1.9;">
                            {ohlc_row}
                        </div>
                        <div style="font-size:0.78rem; color:{t['subtext']}; line-height:1.6;">
                            量: {vol_txt} &nbsp;|&nbsp; {trend}<br>
                            RSI: {f"{rsi_v:.1f}" if rsi_v else "–"} &nbsp;({rsi_lbl})
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    # Action buttons
                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button("📈 查看", key=f"view_{label}"):
                            st.session_state.selected_stock = label
                            st.session_state.active_view    = "chart"
                            st.rerun()
                    with btn_col2:
                        if st.button("移除 ☆", key=f"remove_{label}"):
                            favs.remove(label)
                            save_favorites(favs)
                            st.rerun()

# ============================================================
# VIEW 3 — 均線糾結掃描
# ============================================================

elif st.session_state.active_view == "squeeze":
    st.markdown("### 📊 均線糾結掃描")
    st.caption("篩選多條均線相互靠近（即將交叉）的股票，通常代表盤整後即將出現突破行情。")
    st.markdown("")

    cfg_l, cfg_r = st.columns([1, 1])
    with cfg_l:
        ma_choices = st.multiselect(
            "均線週期", options=[5, 10, 20, 60, 120, 240], default=[5, 20, 60], key="sq_ma",
        )
        threshold = st.slider(
            "糾結閾值 (%)", min_value=0.5, max_value=10.0, value=3.0, step=0.5, key="sq_thresh",
            help="(最高均線 − 最低均線) ÷ 收盤價 × 100，低於此值視為糾結",
        )
    with cfg_r:
        scope_label = st.radio(
            "掃描範圍", ["全部台股", "僅收藏清單"], index=0, horizontal=True, key="sq_scope",
        )
        fav_count = len(load_favorites())
        if scope_label == "全部台股":
            st.caption(f"共 {total_count:,} 支股票，約需 3–5 分鐘")
        else:
            st.caption(f"收藏清單共 {fav_count} 支股票")

    if st.button("🔍 開始掃描", type="primary", key="sq_run"):
        if not ma_choices:
            st.warning("請至少選擇一個均線週期。")
        else:
            if scope_label == "全部台股":
                scope_dict = ALL_STOCKS
            else:
                fav_now    = load_favorites()
                scope_dict = {k: v for k, v in ALL_STOCKS.items() if k in fav_now}

            if not scope_dict:
                st.warning("收藏清單是空的，請先到「📈 市場」頁面加入收藏。")
            else:
                pb     = st.progress(0, text="準備掃描…")
                df_sq  = _scan_squeeze_batch(scope_dict, tuple(sorted(ma_choices)), threshold, pb)
                pb.empty()
                st.session_state.squeeze_results    = df_sq
                st.session_state.squeeze_scanned_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                st.session_state.squeeze_params     = {"ma": sorted(ma_choices), "threshold": threshold}

    # ── Results ──────────────────────────────────────────────
    if st.session_state.squeeze_results is not None:
        df_sq     = st.session_state.squeeze_results
        scan_time = st.session_state.squeeze_scanned_at or ""
        params    = st.session_state.squeeze_params

        st.divider()
        hdr_l, hdr_r = st.columns([4, 1])
        if df_sq.empty:
            hdr_l.warning("沒有符合條件的股票，請調高閾值或減少均線週期數量。")
        else:
            ma_str = "、".join(f"MA{p}" for p in params.get("ma", []))
            hdr_l.success(
                f"找到 **{len(df_sq)}** 支符合條件的股票"
                f"（{ma_str}  |  閾值 {params.get('threshold', '')}%）"
            )
        hdr_r.caption(f"掃描時間\n{scan_time}")

        if not df_sq.empty:
            st.dataframe(df_sq, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.markdown("**點選股票可跳轉至走勢圖：**")
            NAV_COLS = 5
            groups   = [df_sq.iloc[i:i + NAV_COLS] for i in range(0, len(df_sq), NAV_COLS)]
            for grp in groups:
                btn_cs = st.columns(NAV_COLS)
                for bc, (_, row_data) in zip(btn_cs, grp.iterrows()):
                    code   = str(row_data["代號"])
                    name   = str(row_data["名稱"])
                    spread = float(row_data["糾結程度(%)"])
                    full   = f"{code} {name}"
                    bc.button(f"{code} {name}\n▣ {spread:.2f}%", key=f"sq_nav_{code}",
                              on_click=_nav_to_stock, args=(full,))

# ============================================================
# VIEW 4 — 強勢突破選股
# ============================================================

else:
    st.markdown("### 🚀 強勢突破選股")
    st.caption(
        "同時滿足「均線多頭排列（MA5 > MA20 > MA60）」、「突破近期高點」及「爆量」三條件，"
        "並可選擇性加入 RSI 過濾，找出主力介入跡象最明顯的股票。"
    )
    st.markdown("")

    # ── Settings ────────────────────────────────────────────
    s1, s2, s3 = st.columns(3)
    with s1:
        bk_days = st.select_slider(
            "突破天數 N（近 N 日最高）",
            options=[10, 20, 30, 60], value=20, key="bk_days",
            help="今日收盤 > 前 N 個交易日最高收盤價，才視為有效突破",
        )
        vol_mult = st.slider(
            "爆量倍數 (×20日均量)", min_value=1.0, max_value=5.0,
            value=1.5, step=0.1, key="bk_vol",
            help="當日成交量 ÷ 20 日平均量，高於此倍數才算爆量",
        )
    with s2:
        rsi_cap = st.slider(
            "RSI 上限（過濾追高）", min_value=50, max_value=90,
            value=75, step=5, key="bk_rsi",
            help="RSI 超過此值視為過熱，不納入結果",
        )
        st.markdown("")
        st.markdown(
            f"**篩選邏輯摘要**\n"
            f"- MA5 > MA20 > MA60\n"
            f"- 收盤 > 近 {bk_days} 日最高\n"
            f"- 量 > {vol_mult}× 均量\n"
            f"- RSI < {rsi_cap}"
        )
    with s3:
        bk_scope = st.radio(
            "掃描範圍", ["全部台股", "僅收藏清單"],
            index=0, horizontal=True, key="bk_scope",
        )
        bk_fav_count = len(load_favorites())
        if bk_scope == "全部台股":
            st.caption(f"共 {total_count:,} 支股票，約需 3–5 分鐘")
        else:
            st.caption(f"收藏清單共 {bk_fav_count} 支股票")

    if st.button("🔍 開始掃描", type="primary", key="bk_run"):
        if bk_scope == "全部台股":
            bk_scope_dict = ALL_STOCKS
        else:
            bk_fav_now    = load_favorites()
            bk_scope_dict = {k: v for k, v in ALL_STOCKS.items() if k in bk_fav_now}

        if not bk_scope_dict:
            st.warning("收藏清單是空的，請先到「📈 市場」頁面加入收藏。")
        else:
            pb_bk = st.progress(0, text="準備掃描…")
            df_bk = _scan_breakout_batch(bk_scope_dict, bk_days, vol_mult, rsi_cap, pb_bk)
            pb_bk.empty()
            st.session_state.breakout_results    = df_bk
            st.session_state.breakout_scanned_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state.breakout_params     = {
                "days": bk_days, "vol": vol_mult, "rsi": rsi_cap,
            }

    # ── Results ─────────────────────────────────────────────
    if st.session_state.breakout_results is not None:
        df_bk      = st.session_state.breakout_results
        bk_time    = st.session_state.breakout_scanned_at or ""
        bk_params  = st.session_state.breakout_params

        st.divider()
        bh_l, bh_r = st.columns([4, 1])
        if df_bk.empty:
            bh_l.warning("沒有符合所有條件的股票，請嘗試放寬爆量倍數或調高 RSI 上限。")
        else:
            bh_l.success(
                f"找到 **{len(df_bk)}** 支符合強勢突破條件的股票"
                f"（突破 {bk_params.get('days','')} 日高  |  "
                f"量 >{bk_params.get('vol','')}×  |  "
                f"RSI<{bk_params.get('rsi','')}）"
            )
        bh_r.caption(f"掃描時間\n{bk_time}")

        if not df_bk.empty:
            st.dataframe(df_bk, use_container_width=True, hide_index=True)

            # Volume surge bar chart
            st.markdown("")
            st.markdown("##### 成交量爆量強度")
            bar_fig = go.Figure(go.Bar(
                x=df_bk["代號"] + " " + df_bk["名稱"],
                y=df_bk["成交量比(×)"],
                marker_color=[TW_UP if v >= 0 else TW_DOWN for v in df_bk["漲跌幅(%)"]],
                text=df_bk["成交量比(×)"].apply(lambda x: f"{x:.1f}×"),
                textposition="outside",
            ))
            bar_fig.add_hline(
                y=bk_params.get("vol", 1.5),
                line=dict(color=t["subtext"], width=1.5, dash="dot"),
            )
            bar_fig.update_layout(
                **base_layout(height=280),
                xaxis_tickangle=-35,
                yaxis_title="成交量比 (×均量)",
            )
            bar_fig.update_xaxes(tickfont=dict(color=t["subtext"], size=10), gridcolor=t["grid"])
            bar_fig.update_yaxes(tickfont=dict(color=t["subtext"]), gridcolor=t["grid"],
                                 title_font=dict(color=t["text"]))
            st.plotly_chart(bar_fig, use_container_width=True)

            # Navigation buttons — on_click fires before rerun, most reliable pattern
            st.markdown("---")
            st.markdown("**點選股票可跳轉至走勢圖：**")
            BK_COLS = 5
            bk_grps = [df_bk.iloc[i:i + BK_COLS] for i in range(0, len(df_bk), BK_COLS)]
            for grp in bk_grps:
                btn_cs = st.columns(BK_COLS)
                for bc, (_, row_data) in zip(btn_cs, grp.iterrows()):
                    code  = str(row_data["代號"])
                    name  = str(row_data["名稱"])
                    vol_r = float(row_data["成交量比(×)"])
                    full  = f"{code} {name}"
                    bc.button(f"{code} {name}\n🔥 {vol_r:.1f}×", key=f"bk_nav_{code}",
                              on_click=_nav_to_stock, args=(full,))
