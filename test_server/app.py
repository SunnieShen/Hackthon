import os
import json
import time
from typing import List, Dict, Any, Optional

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

import yfinance as yf
import pandas as pd

APP_DIR = os.path.dirname(os.path.abspath(__file__))
WATCHLIST_PATH = os.path.join(APP_DIR, "watchlist.json")

app = Flask(__name__, static_folder=os.path.join(APP_DIR, "static"), static_url_path="/")
CORS(app)  # Enable CORS for all routes during development

# Hot list and sector indices (ETF proxies) with sample constituents
HOT_LIST: List[str] = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "TSLA", "GOOG", "NFLX", "AMD", "AVGO"
]
INDICES: List[Dict[str, Any]] = [
    # 全球热门指数（使用 Yahoo Finance 符号）
    {"symbol": "^GSPC", "name": "标普500指数 (^GSPC)", "category": "global", "constituents": []},
    {"symbol": "^DJI", "name": "道琼斯工业平均指数 (^DJI)", "category": "global", "constituents": []},
    {"symbol": "^NDX", "name": "纳斯达克100指数 (^NDX)", "category": "global", "constituents": []},
    {"symbol": "^FTSE", "name": "富时100指数 (^FTSE)", "category": "global", "constituents": []},
    {"symbol": "^GDAXI", "name": "德国DAX指数 (^GDAXI)", "category": "global", "constituents": []},
    {"symbol": "^N225", "name": "日经225指数 (^N225)", "category": "global", "constituents": []},
    {"symbol": "^HSI", "name": "恒生指数 (^HSI)", "category": "global", "constituents": []},

    # 板块ETF（保留并标注分类）
    {"symbol": "XLK", "name": "科技板块ETF (XLK)", "category": "sector_etf", "constituents": ["AAPL","MSFT","NVDA","AVGO","ADBE","AMD","CRM"]},
    {"symbol": "XLF", "name": "金融板块ETF (XLF)", "category": "sector_etf", "constituents": ["JPM","BAC","WFC","GS","MS","SCHW","C"]},
    {"symbol": "XLE", "name": "能源板块ETF (XLE)", "category": "sector_etf", "constituents": ["XOM","CVX","COP","SLB","EOG","PSX","MPC"]},
    {"symbol": "XLV", "name": "医疗板块ETF (XLV)", "category": "sector_etf", "constituents": ["UNH","JNJ","LLY","ABBV","MRK","PFE","TMO"]},
    {"symbol": "XLY", "name": "可选消费板块ETF (XLY)", "category": "sector_etf", "constituents": ["AMZN","TSLA","MCD","NKE","SBUX","BKNG"]},
    {"symbol": "XLP", "name": "必选消费板块ETF (XLP)", "category": "sector_etf", "constituents": ["PG","KO","PEP","WMT","COST","MDLZ"]},
    {"symbol": "XLU", "name": "公用事业板块ETF (XLU)", "category": "sector_etf", "constituents": ["NEE","DUK","SO","D","AEP","EXC"]},
    {"symbol": "XLI", "name": "工业板块ETF (XLI)", "category": "sector_etf", "constituents": ["HON","UNP","RTX","CAT","LMT","GE"]},
    {"symbol": "IYR", "name": "房地产板块ETF (IYR)", "category": "sector_etf", "constituents": ["AMT","PLD","SPG","EQIX","WELL","O"]},
]


def _load_watchlist() -> List[str]:
    if not os.path.exists(WATCHLIST_PATH):
        _save_watchlist(["AAPL", "MSFT"])  # seed demo
    try:
        with open(WATCHLIST_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return sorted({str(s).upper().strip() for s in data if str(s).strip()})
    except Exception:
        return []


def _save_watchlist(symbols: List[str]) -> None:
    try:
        with open(WATCHLIST_PATH, "w", encoding="utf-8") as f:
            json.dump(sorted({str(s).upper().strip() for s in symbols}), f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to save watchlist: {e}")


def _safe_get(fi: Any, key: str) -> Optional[Any]:
    try:
        if fi is None:
            return None
        # fast_info is dict-like
        return fi.get(key)
    except Exception:
        return None


def _compute_indicators(close: pd.Series) -> Dict[str, Any]:
    indicators: Dict[str, Any] = {
        "sma20": None,
        "sma50": None,
        "rsi14": None,
        "macd": {"macd": None, "signal": None, "hist": None},
        "bbands": {"upper": None, "middle": None, "lower": None},
    }
    try:
        if close is None or close.empty:
            return indicators
        # SMA
        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean()
        indicators["sma20"] = float(sma20.iloc[-1]) if len(sma20) >= 20 and not pd.isna(sma20.iloc[-1]) else None
        indicators["sma50"] = float(sma50.iloc[-1]) if len(sma50) >= 50 and not pd.isna(sma50.iloc[-1]) else None

        # RSI14 (simple rolling version)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        if len(avg_gain) >= 14 and len(avg_loss) >= 14:
            ag = avg_gain.iloc[-1]
            al = avg_loss.iloc[-1]
            if not pd.isna(ag) and not pd.isna(al) and al != 0:
                rs = ag / al
                rsi = 100 - 100 / (1 + rs)
                indicators["rsi14"] = float(rsi)

        # MACD (12,26,9)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal = macd_line.ewm(span=9, adjust=False).mean()
        hist = macd_line - signal
        indicators["macd"]["macd"] = float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else None
        indicators["macd"]["signal"] = float(signal.iloc[-1]) if not pd.isna(signal.iloc[-1]) else None
        indicators["macd"]["hist"] = float(hist.iloc[-1]) if not pd.isna(hist.iloc[-1]) else None

        # Bollinger Bands (20, 2)
        if len(sma20) >= 20:
            std20 = close.rolling(20).std()
            middle = sma20.iloc[-1]
            stdv = std20.iloc[-1]
            if not pd.isna(middle) and not pd.isna(stdv):
                indicators["bbands"]["middle"] = float(middle)
                indicators["bbands"]["upper"] = float(middle + 2 * stdv)
                indicators["bbands"]["lower"] = float(middle - 2 * stdv)
    except Exception as e:
        print(f"Indicator calc error: {e}")
    return indicators


def _get_price_for_symbol(symbol: str) -> Dict[str, Any]:
    symbol = symbol.upper().strip()
    info: Dict[str, Any] = {
        "symbol": symbol,
        "price": None,
        "currency": None,
        "ts": int(time.time() * 1000),
        "change": None,
        "change_percent": None,
        "open": None,
        "high": None,
        "low": None,
        "prev_close": None,
        "volume": None,
        "market_cap": None,
        "year_high": None,
        "year_low": None,
        "indicators": {"sma20": None, "sma50": None, "rsi14": None, "macd": {"macd": None, "signal": None, "hist": None}, "bbands": {"upper": None, "middle": None, "lower": None}},
    }
    try:
        t = yf.Ticker(symbol)
        price = None
        currency = None
        fi = None
        try:
            fi = t.fast_info
            price = _safe_get(fi, "last_price")
            currency = _safe_get(fi, "currency")
            info["open"] = _safe_get(fi, "open")
            info["high"] = _safe_get(fi, "day_high")
            info["low"] = _safe_get(fi, "day_low")
            info["prev_close"] = _safe_get(fi, "previous_close")
            info["volume"] = _safe_get(fi, "last_volume") or _safe_get(fi, "volume")
            info["market_cap"] = _safe_get(fi, "market_cap")
            info["year_high"] = _safe_get(fi, "year_high")
            info["year_low"] = _safe_get(fi, "year_low")
        except Exception:
            pass

        if price is None:
            try:
                data = t.info or {}
                price = data.get("regularMarketPrice") or data.get("currentPrice")
                currency = currency or data.get("currency")
                info["open"] = info["open"] or data.get("open")
                info["high"] = info["high"] or data.get("dayHigh") or data.get("regularMarketDayHigh")
                info["low"] = info["low"] or data.get("dayLow") or data.get("regularMarketDayLow")
                info["prev_close"] = info["prev_close"] or data.get("previousClose") or data.get("regularMarketPreviousClose")
                info["volume"] = info["volume"] or data.get("volume")
                info["market_cap"] = info["market_cap"] or data.get("marketCap")
                info["year_high"] = info["year_high"] or data.get("fiftyTwoWeekHigh")
                info["year_low"] = info["year_low"] or data.get("fiftyTwoWeekLow")
            except Exception:
                pass

        # Fallback to last close if still None
        hist: pd.DataFrame = pd.DataFrame()
        if price is None:
            try:
                hist = t.history(period="1d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
            except Exception:
                pass

        # Compute change and indicators using broader history
        try:
            if hist.empty:
                hist = t.history(period="6mo", interval="1d")
            if not hist.empty:
                close = hist["Close"].dropna()
                # prev_close fallback
                if info["prev_close"] is None and len(close) >= 2:
                    info["prev_close"] = float(close.iloc[-2])
                # change
                if price is not None and info["prev_close"] is not None:
                    ch = float(price) - float(info["prev_close"])
                    info["change"] = ch
                    if info["prev_close"] != 0:
                        info["change_percent"] = ch / float(info["prev_close"]) * 100.0
                # indicators
                info["indicators"] = _compute_indicators(close)
        except Exception as e:
            print(f"History fetch/compute error for {symbol}: {e}")

        info["price"] = float(price) if price is not None else None
        info["currency"] = currency
        return info
    except Exception as e:
        info["error"] = str(e)
        return info


@app.get("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/api/watchlist")
def get_watchlist():
    return jsonify({"symbols": _load_watchlist()})


@app.post("/api/watchlist")
def add_symbol():
    data = request.get_json(force=True, silent=True) or {}
    symbol = str(data.get("symbol", "")).upper().strip()
    if not symbol:
        return jsonify({"error": "symbol is required"}), 400
    symbols = _load_watchlist()
    if symbol not in symbols:
        symbols.append(symbol)
        _save_watchlist(symbols)
    return jsonify({"symbols": symbols})


@app.delete("/api/watchlist/<symbol>")
def remove_symbol(symbol: str):
    sym = symbol.upper().strip()
    symbols = _load_watchlist()
    symbols = [s for s in symbols if s != sym]
    _save_watchlist(symbols)
    return jsonify({"symbols": symbols})


@app.get("/api/prices")
def get_prices():
    symbols_param = request.args.get("symbols")
    if symbols_param:
        symbols = [s.strip().upper() for s in symbols_param.split(",") if s.strip()]
    else:
        symbols = _load_watchlist()
    results = [_get_price_for_symbol(s) for s in symbols]
    return jsonify({"results": results})


@app.get("/api/hot")
def get_hot():
    results = [_get_price_for_symbol(s) for s in HOT_LIST]
    return jsonify({"results": results})


@app.get("/api/indices")
def get_indices():
    category = request.args.get("category")
    source = [i for i in INDICES if (not category or i.get("category") == category)]
    payload = []
    for idx in source:
        try:
            idx_info = _get_price_for_symbol(idx["symbol"]) if idx.get("symbol") else {}
        except Exception:
            idx_info = {}
        payload.append({
            "symbol": idx["symbol"],
            "name": idx["name"],
            "category": idx.get("category"),
            "price": idx_info.get("price"),
            "change_percent": idx_info.get("change_percent"),
            "indicators": idx_info.get("indicators"),
            "constituents": idx["constituents"],
        })
    return jsonify({"indices": payload})


@app.get("/api/indices/<symbol>/constituents")
def get_index_constituents(symbol: str):
    sym = symbol.upper().strip()
    idx = next((i for i in INDICES if i["symbol"] == sym), None)
    if not idx:
        return jsonify({"error": "index not found"}), 404
    return jsonify({"symbol": sym, "constituents": idx["constituents"]})


@app.get("/api/history/<symbol>")
def get_history(symbol: str):
    sym = symbol.upper().strip()
    period = request.args.get("period", "6mo")
    interval = request.args.get("interval", "1d")
    try:
        t = yf.Ticker(sym)
        df: pd.DataFrame = t.history(period=period, interval=interval)
        if df is None or df.empty:
            return jsonify({
                "symbol": sym,
                "ts": [],
                "open": [],
                "high": [],
                "low": [],
                "close": [],
                "volume": [],
                "indicators": {
                    "sma20": [],
                    "sma50": [],
                    "bbands": {"upper": [], "middle": [], "lower": []},
                    "rsi14": [],
                    "macd": {"macd": [], "signal": [], "hist": []},
                }
            })
        df = df.dropna()
        # Ensure index is datetime
        idx = df.index
        ts = [int(pd.Timestamp(i).timestamp() * 1000) for i in idx]
        close = df["Close"].astype(float)
        sma20 = close.rolling(20).mean()
        sma50 = close.rolling(50).mean()
        std20 = close.rolling(20).std()
        upper = sma20 + 2 * std20
        lower = sma20 - 2 * std20
        middle = sma20
        # RSI14 series
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.rolling(14).mean()
        avg_loss = loss.rolling(14).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - 100 / (1 + rs)
        # MACD series (12,26,9)
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        signal = macd_line.ewm(span=9, adjust=False).mean()
        hist = macd_line - signal
        # Convert to python floats or None
        def to_list(series: pd.Series):
            out = []
            for v in series:
                if pd.isna(v) or v is None:
                    out.append(None)
                else:
                    out.append(float(v))
            return out
        payload = {
            "symbol": sym,
            "ts": ts,
            "open": to_list(df["Open"]),
            "high": to_list(df["High"]),
            "low": to_list(df["Low"]),
            "close": to_list(df["Close"]),
            "volume": to_list(df["Volume"]),
            "indicators": {
                "sma20": to_list(sma20),
                "sma50": to_list(sma50),
                "bbands": {
                    "upper": to_list(upper),
                    "middle": to_list(middle),
                    "lower": to_list(lower),
                },
                "rsi14": to_list(rsi),
                "macd": {
                    "macd": to_list(macd_line),
                    "signal": to_list(signal),
                    "hist": to_list(hist),
                },
            },
        }
        return jsonify(payload)
    except Exception as e:
        return jsonify({"symbol": sym, "error": str(e)}), 500

# 新增：公司信息与最新新闻接口
@app.get("/api/company/<symbol>")
def get_company(symbol: str):
    sym = symbol.upper().strip()
    try:
        t = yf.Ticker(sym)
        data = {}
        try:
            data = t.get_info() or {}
        except Exception:
            try:
                data = t.info or {}
            except Exception:
                data = {}
        info = {
            "symbol": sym,
            "name": data.get("longName") or data.get("shortName"),
            "sector": data.get("sector"),
            "industry": data.get("industry"),
            "website": data.get("website"),
            "summary": data.get("longBusinessSummary"),
            "market_cap": data.get("marketCap"),
            "employees": data.get("fullTimeEmployees"),
            "country": data.get("country"),
            "city": data.get("city"),
        }
        # 基本面指标（尽量使用 info 中现成字段，缺失则为 None）
        fundamentals = {
            "pe": data.get("trailingPE"),
            "forward_pe": data.get("forwardPE"),
            "ps": data.get("priceToSalesTrailing12Months"),
            "pb": data.get("priceToBook"),
            "peg": data.get("pegRatio"),
            "beta": data.get("beta"),
            "dividend_yield": data.get("dividendYield"),
            "payout_ratio": data.get("payoutRatio"),
            "gross_margins": data.get("grossMargins"),
            "operating_margins": data.get("operatingMargins"),
            "profit_margins": data.get("profitMargins"),
            "revenue_ttm": data.get("totalRevenue"),
            "ebitda": data.get("ebitda"),
            "net_income_ttm": data.get("netIncomeToCommon"),
            "roe": data.get("returnOnEquity"),
            "roa": data.get("returnOnAssets"),
            "total_debt": data.get("totalDebt"),
            "debt_to_equity": data.get("debtToEquity"),
            "free_cash_flow": data.get("freeCashflow"),
        }
        # 财务报表快照（取最近一期数值）
        def last_value(df: pd.DataFrame, row_names: list[str]):
            try:
                if not isinstance(df, pd.DataFrame) or df.empty:
                    return None
                idx = df.index.astype(str).tolist()
                # 找到可用的行名
                target = None
                for name in row_names:
                    if name in df.index:
                        target = name
                        break
                if not target:
                    # 尝试大小写或近似匹配
                    for name in row_names:
                        for i in idx:
                            if i.strip().lower() == name.strip().lower():
                                target = i
                                break
                        if target:
                            break
                if not target:
                    return None
                series = df.loc[target]
                series = series.dropna()
                if series.empty:
                    return None
                # 列通常按最近日期在左或右，取第一个非空
                val = series.iloc[0]
                try:
                    return float(val)
                except Exception:
                    return None
            except Exception:
                return None
        try:
            fin = t.financials
        except Exception:
            fin = None
        try:
            bs = t.balance_sheet
        except Exception:
            bs = None
        try:
            cf = t.cashflow
        except Exception:
            cf = None
        financials = {
            "annual": {
                "revenue": last_value(fin, ["Total Revenue", "totalRevenue"]),
                "gross_profit": last_value(fin, ["Gross Profit", "grossProfit"]),
                "operating_income": last_value(fin, ["Operating Income", "operatingIncome"]),
                "net_income": last_value(fin, ["Net Income", "netIncome"]),
            },
            "balance_sheet": {
                "assets": last_value(bs, ["Total Assets", "totalAssets"]),
                "liabilities": last_value(bs, ["Total Liab", "Total Liabilities", "totalLiab", "totalLiabilities"]),
                "equity": last_value(bs, ["Total Stockholder Equity", "totalStockholderEquity", "Stockholders Equity"]),
            },
            "cashflow": {
                "operating_cash_flow": last_value(cf, ["Operating Cash Flow", "totalCashFromOperatingActivities", "operatingCashFlow"]),
                "capital_expenditures": last_value(cf, ["Capital Expenditures", "capitalExpenditures"]),
            },
        }
        # 计算自由现金流（如有数据，可用 operating + capex；注意 capex 通常为负数）
        ocf = financials["cashflow"].get("operating_cash_flow")
        capex = financials["cashflow"].get("capital_expenditures")
        if ocf is not None and capex is not None:
            financials["cashflow"]["free_cash_flow"] = float(ocf) + float(capex)
        else:
            financials["cashflow"]["free_cash_flow"] = fundamentals.get("free_cash_flow")
        return jsonify({"info": info, "fundamentals": fundamentals, "financials": financials})
    except Exception as e:
        return jsonify({"error": str(e), "info": {"symbol": sym}}), 500


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)