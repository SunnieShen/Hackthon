import os
import json
import time
from typing import List, Dict, Any, Optional

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

import yfinance as yf
import pandas as pd
import urllib.request
import urllib.error

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


# ----------------------
# 投资组合AI诊断（规则引擎）
# ----------------------
def _normalize_weights(holdings):
    total = sum(float(h.get('weight', 0) or 0) for h in holdings) or 0.0
    if total <= 0:
        n = len(holdings)
        if n == 0:
            return []
        return [{**h, 'weight': 1.0 / n} for h in holdings]
    return [{**h, 'weight': (float(h.get('weight', 0) or 0) / total)} for h in holdings]

def _portfolio_hhi(weights):
    return sum((w or 0.0) ** 2 for w in weights)

def _portfolio_diversity_score(weights):
    hhi = _portfolio_hhi(weights)
    score = max(0.0, min(1.0, 1.0 - hhi)) * 100.0
    return round(score, 1), hhi

def _fetch_company_basic(sym: str):
    try:
        t = yf.Ticker(sym)
        info = {}
        try:
            info = t.get_info() or {}
        except Exception:
            try:
                info = t.info or {}
            except Exception:
                info = {}
        sector = info.get('sector') or info.get('industry') or 'Unknown'
        pe = info.get('trailingPE') or info.get('forwardPE')
        if pe is None:
            pe = info.get('trailing_pe') or info.get('forward_pe')
        try:
            pe = float(pe) if pe is not None else None
        except Exception:
            pe = None
        return {'sector': sector, 'pe': pe}
    except Exception:
        return {'sector': 'Unknown', 'pe': None}

def _sector_concentration(holdings, sector_map):
    weights_by_sector = {}
    for h in holdings:
        sym = h.get('symbol')
        w = float(h.get('weight', 0) or 0)
        sec = (sector_map.get(sym) or 'Unknown')
        weights_by_sector[sec] = weights_by_sector.get(sec, 0.0) + w
    max_sec_weight = max(weights_by_sector.values()) if weights_by_sector else 0.0
    return round(max_sec_weight, 4), weights_by_sector

def _weighted_avg_pe(holdings, pe_map):
    num = 0.0
    den = 0.0
    for h in holdings:
        w = float(h.get('weight', 0) or 0)
        sym = h.get('symbol')
        pe = pe_map.get(sym)
        if pe is None or not (pe == pe):
            continue
        num += w * float(pe)
        den += w
    if den <= 1e-9:
        return None
    return round(num / den, 2)

def _assess_portfolio_risk(single_stock_weight, sector_conc, avg_pe):
    high = (single_stock_weight > 0.30) or (sector_conc > 0.70) or ((avg_pe or 0) > 25)
    if high:
        return '高'
    medium = (single_stock_weight > 0.20) or (sector_conc > 0.50) or ((avg_pe or 0) > 20)
    if medium:
        return '中'
    return '低'

@app.post("/api/portfolio/diagnostic")
def portfolio_diagnostic():
    try:
        data = request.get_json(force=True) or {}
        holdings = data.get('holdings') or []
        clean = []
        for h in holdings:
            sym = str(h.get('symbol', '')).upper().strip()
            w = float(h.get('weight', 0) or 0)
            if not sym:
                continue
            clean.append({'symbol': sym, 'weight': w})
        clean = _normalize_weights(clean)
        weights = [h['weight'] for h in clean]
        diversity_score, hhi = _portfolio_diversity_score(weights)
        single_stock_weight = max(weights) if weights else 0.0
        sector_map = {}
        pe_map = {}
        for h in clean:
            info = _fetch_company_basic(h['symbol'])
            sector_map[h['symbol']] = info.get('sector')
            pe_map[h['symbol']] = info.get('pe')
        sector_conc, sector_weights = _sector_concentration(clean, sector_map)
        avg_pe = _weighted_avg_pe(clean, pe_map)
        risk_level = _assess_portfolio_risk(single_stock_weight, sector_conc, avg_pe)

        analysis = {
            'diversity_score': diversity_score,
            'risk_level': risk_level,
            'main_issues': [],
            'suggestions': [],
            'metrics': {
                'hhi': round(hhi, 4),
                'single_stock_weight': round(single_stock_weight, 4),
                'sector_concentration': round(sector_conc, 4),
                'avg_pe': avg_pe,
            },
            'sector_weights': sector_weights,
        }

        if sector_conc > 0.70:
            analysis['main_issues'].append('行业过度集中')
            analysis['suggestions'].append('考虑加入消费、医疗、公用事业等防御性板块')
        elif sector_conc > 0.50:
            analysis['main_issues'].append('行业集中度偏高')
            analysis['suggestions'].append('适当引入跨行业标的，控制行业相关性')

        if single_stock_weight > 0.30:
            analysis['main_issues'].append('单一个股权重过高')
            analysis['suggestions'].append('建议单股不超过总仓位20%')
        elif single_stock_weight > 0.20:
            analysis['main_issues'].append('最大个股权重偏高')
            analysis['suggestions'].append('关注尾部标的补齐提升分散度')

        if (avg_pe or 0) > 25:
            analysis['main_issues'].append('整体估值偏高')
            analysis['suggestions'].append('关注低估值价值股或红利类资产平衡组合')
        elif (avg_pe or 0) > 20:
            analysis['main_issues'].append('估值处于偏高区间')
            analysis['suggestions'].append('适度降低成长风格权重，提升防御或现金流稳定标的')

        issues = '、'.join(analysis['main_issues']) if analysis['main_issues'] else '整体结构均衡'
        suggestions = '；'.join(analysis['suggestions']) if analysis['suggestions'] else '维持现有配置，关注个股基本面变化'
        summary_text = (
            f"多样性得分 {diversity_score}，风险等级 {risk_level}；"
            f"最大个股权重 {round(single_stock_weight*100,1)}%，行业集中度 {round(sector_conc*100,1)}%，"
            f"加权平均PE {avg_pe if avg_pe is not None else '-'}。主要问题：{issues}。建议：{suggestions}。"
        )

        return jsonify({'ok': True, 'analysis': analysis, 'summary_text': summary_text, 'holdings': clean})
    except Exception as e:
        return jsonify({'ok': False, 'error': 'portfolio_diagnostic_failed', 'detail': str(e)}), 500


# ---- AI 分析接口（DeepSeek/OpenAI兼容HTTP） ----
def _call_deepseek_chat(system_msg: str, user_msg: str) -> Dict[str, Any]:
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"error": "API key not configured. Set DEEPSEEK_API_KEY."}
    url = "https://api.deepseek.com/v1/chat/completions"
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 300,
        "temperature": 0.7,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read()
            j = json.loads(body.decode("utf-8"))
            # OpenAI兼容返回结构
            try:
                content = j["choices"][0]["message"]["content"].strip()
            except Exception:
                content = None
            return {"content": content, "raw": j}
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = str(e)
        return {"error": f"HTTP {e.code}: {err_body}"}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/ai_analysis")
def ai_analysis():
    data = request.get_json(force=True, silent=True) or {}
    symbol = str(data.get("symbol", "")).upper().strip()
    fin = data.get("financial_data") or {}
    # 兼容字段名
    current_price = fin.get("currentPrice")
    change_percent = fin.get("changePercent")
    pe_ratio = fin.get("peRatio")
    rsi14 = fin.get("rsi14")

    prompt = (
        f"作为投资顾问，请分析 {symbol}：\n\n"
        f"当前价格: ${current_price}\n"
        f"涨跌幅: {change_percent}%\n"
        f"市盈率: {pe_ratio if pe_ratio is not None else 'N/A'}\n"
        f"RSI: {rsi14 if rsi14 is not None else 'N/A'}\n\n"
        "请提供简短的投资建议，包括：\n"
        "1. 技术面分析\n"
        "2. 风险提示\n"
        "3. 操作建议\n\n"
        "要求：专业但易懂，150字以内。"
    )
    sys_msg = "你是一名专业的金融分析师，善于用通俗语言解释复杂概念"
    result = _call_deepseek_chat(sys_msg, prompt)
    if result.get("error"):
        err = str(result.get("error"))
        # 余额不足时降级到本地简化分析，返回200并携带warning
        if "HTTP 402" in err or "Insufficient Balance" in err:
            analysis = _local_ai_analysis(symbol, current_price, change_percent, pe_ratio, rsi14)
            return jsonify({"symbol": symbol, "analysis": analysis, "warning": "insufficient_balance", "source": "local"})
        # 其他错误：仍尝试返回本地简化分析，携带通用warning
        analysis = _local_ai_analysis(symbol, current_price, change_percent, pe_ratio, rsi14)
        return jsonify({"symbol": symbol, "analysis": analysis, "warning": "fallback", "source": "local", "error": err})
    return jsonify({"symbol": symbol, "analysis": result.get("content"), "source": "deepseek"})


def _local_ai_analysis(symbol: str, current_price: Any, change_percent: Any, pe_ratio: Any, rsi14: Any) -> str:
    """基于基础指标的简化本地分析，控制在约150字以内。"""
    try:
        price = current_price
        chg = change_percent
        pe = pe_ratio
        rsi = rsi14
        parts = []
        # 技术面
        tech = []
        if rsi is not None:
            try:
                r = float(rsi)
                if r <= 30:
                    tech.append("RSI低位，超卖偏强")
                elif r >= 70:
                    tech.append("RSI高位，超买风险")
                else:
                    tech.append("RSI中性")
            except Exception:
                tech.append("RSI数据有限")
        if chg is not None:
            try:
                c = float(chg)
                if c >= 2:
                    tech.append("短期上行动能较强")
                elif c <= -2:
                    tech.append("短期回撤压力显著")
            except Exception:
                pass
        if tech:
            parts.append("技术面：" + "，".join(tech))
        # 风险
        risk = []
        if pe is not None:
            try:
                p = float(pe)
                if p >= 30:
                    risk.append("估值偏高，波动或放大")
                elif p <= 10:
                    risk.append("估值偏低，但基本面需确认")
            except Exception:
                pass
        risk.append("注意事件风险与市场环境")
        parts.append("风险提示：" + "，".join(risk))
        # 操作建议
        op = []
        try:
            r = float(rsi) if rsi is not None else None
            if r is not None and r <= 30:
                op.append("轻仓试探，分批建仓")
            elif r is not None and r >= 70:
                op.append("谨慎减仓，等待回落")
            else:
                op.append("观望为主，关注支撑与成交量")
        except Exception:
            op.append("以风险控制为先，设定止损")
        parts.append("操作建议：" + "，".join(op))
        text = "；".join(parts)
        # 控制长度
        return text[:160]
    except Exception:
        return "数据有限，建议观望并做好风险控制。"


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)