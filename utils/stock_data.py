import json
import os
from typing import List, Dict, Optional, Tuple, Any
import akshare as ak
import pandas as pd
import streamlit as st
import numpy as np
from datetime import datetime
from utils.cache_manager import get_cache_manager

DATA_DIR = "data"
STOCK_POOL_FILE = os.path.join(DATA_DIR, "stock_pool.json")
WATCHING_POOL_FILE = os.path.join(DATA_DIR, "watching_pool.json")
TRADING_POOL_FILE = os.path.join(DATA_DIR, "trading_pool.json")

# Try to import pypinyin
try:
    from pypinyin import lazy_pinyin
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

# Trigger Cache Update (Lazy or Async in real app, here we check on load)
# Ideally this should be a background thread, but Streamlit execution model is script-based.
# We can use st.cache_resource to hold the manager and check update.
@st.cache_resource
def _init_cache_manager():
    cm = get_cache_manager()
    # Attempt update if needed (non-blocking if possible, but here we block briefly to ensure data)
    try:
        cm.update_cache()
    except:
        pass
    return cm

# Initialize on module load/first use
_init_cache_manager()

@st.cache_data(ttl=60)
def get_market_status() -> Dict[str, str]:
    """
    Determine current market status (A-share).
    Returns: {
        "status": "OPEN" | "CLOSED" | "BREAK", 
        "color": "green" | "red" | "orange",
        "message": "...",
        "next_open": "..."
    }
    """
    now = datetime.now()
    weekday = now.weekday() # 0=Mon, 6=Sun
    time_now = now.time()
    
    # 1. Weekend Check
    if weekday >= 5:
        return {
            "status": "CLOSED",
            "color": "red",
            "message": "休市中 (周末)",
            "next_open": "下周一 09:30"
        }
    
    # 2. Time Check
    t_9_30 = datetime.strptime("09:30", "%H:%M").time()
    t_11_30 = datetime.strptime("11:30", "%H:%M").time()
    t_13_00 = datetime.strptime("13:00", "%H:%M").time()
    t_15_00 = datetime.strptime("15:00", "%H:%M").time()
    
    if t_9_30 <= time_now <= t_11_30:
        return {"status": "OPEN", "color": "green", "message": "交易中 (早盘)", "next_open": ""}
    elif t_13_00 <= time_now <= t_15_00:
        return {"status": "OPEN", "color": "green", "message": "交易中 (午盘)", "next_open": ""}
    elif t_11_30 < time_now < t_13_00:
        return {"status": "BREAK", "color": "orange", "message": "午间休市", "next_open": "13:00"}
    elif time_now > t_15_00:
         return {"status": "CLOSED", "color": "red", "message": "已收盘", "next_open": "明日 09:30"}
    else: # Before 9:30
         return {"status": "CLOSED", "color": "red", "message": "未开盘", "next_open": "09:30"}

@st.cache_data(ttl=60)
def get_all_stock_list() -> pd.DataFrame:
    """
    Fetch basic list of all A-shares (Code & Name) for search.
    Uses the persistent JSON cache for speed and offline capability.
    """
    cm = get_cache_manager()
    # Try update if stale (lazy check)
    try:
        cm.update_cache()
    except:
        pass
        
    data = cm.get_all_companies()
    if not data:
        # Fallback if cache empty
        return pd.DataFrame()
        
    # Convert JSON cache to DataFrame for compatibility
    rows = []
    for code, info in data.items():
        base = info.get('base', {})
        rows.append({
            "代码": base.get('code'),
            "名称": base.get('name'),
            "pinyin": base.get('pinyin', '')
        })
    
    return pd.DataFrame(rows)

@st.cache_data(ttl=60)  # Cache for 60 seconds
def get_market_snapshot() -> pd.DataFrame:
    """
    Fetch real-time data for all A-shares.
    Uses persistent cache first, updates if needed.
    """
    cm = get_cache_manager()
    try:
        cm.update_cache() # Check and update if > 10 min
    except:
        pass
        
    data = cm.get_all_companies()
    if not data:
         # Direct Fetch Fallback
         # 1. Try Spot Data (Full Info - EM)
         try:
             df = ak.stock_zh_a_spot_em()
             # ... (Original fallback logic kept for safety or if cache fails completely)
             # But here we just return the original logic if cache is empty
             # For brevity, I'll rely on the original implementation below if cache is empty?
             # No, let's keep the original implementation as a robust fallback in the `except` blocks of cache manager
             # But here, let's try to construct DF from cache first.
             pass
         except:
             pass
    
    if data:
        rows = []
        for code, info in data.items():
            base = info.get('base', {})
            quote = info.get('quote', {})
            rows.append({
                "代码": base.get('code'),
                "名称": base.get('name'),
                "pinyin": base.get('pinyin', ''),
                "最新价": quote.get('price'),
                "涨跌幅": quote.get('change_pct'),
                "成交量": quote.get('volume'),
                "成交额": quote.get('amount'),
                "市盈率-动态": quote.get('pe', '-'),
                "市净率": quote.get('pb', '-')
            })
        return pd.DataFrame(rows)

    # Fallback to direct API if cache totally failed
    # 1. Try Spot Data (Full Info - EM)
    try:
        df = ak.stock_zh_a_spot_em()
        # Ensure code is string
        df['代码'] = df['代码'].astype(str)
        
        # Add Pinyin if available
        if HAS_PYPINYIN:
            def get_pinyin_abbr(name):
                try:
                    return "".join([w[0] for w in lazy_pinyin(name)]).upper()
                except:
                    return ""
            df['pinyin'] = df['名称'].apply(get_pinyin_abbr)
        else:
            df['pinyin'] = ""
            
        return df
    except Exception as e:
        print(f"Error fetching market snapshot (spot EM): {e}")
    
    # 2. Try Spot Data (Fallback - Sina)
    try:
        df = ak.stock_zh_a_spot()
        # Columns: 代码, 名称, 最新价, 涨跌额, 涨跌幅, ...
        # Normalize to match EM structure where possible
        df['代码'] = df['代码'].astype(str)
        
        # Sina returns codes with prefixes (e.g. sh600519, bj920000). 
        # We need to strip these to match our 6-digit format in stock_pool.json
        # Using regex to keep only digits might be safest, or just slicing.
        # Assuming standard A-shares, last 6 digits are the code.
        import re
        def clean_code(c):
            # Extract last 6 digits if possible, or just digits
            digits = re.findall(r'\d+', c)
            if digits:
                return digits[-1][-6:] # Take last 6 digits of the last number found
            return c
            
        df['代码'] = df['代码'].apply(clean_code)
        
        # Add missing columns expected by app
        df['市盈率-动态'] = "-"
        df['市净率'] = "-"
        
        if HAS_PYPINYIN:
            def get_pinyin_abbr(name):
                try:
                    return "".join([w[0] for w in lazy_pinyin(name)]).upper()
                except:
                    return ""
            df['pinyin'] = df['名称'].apply(get_pinyin_abbr)
        else:
            df['pinyin'] = ""
            
        return df
    except Exception as e:
        print(f"Error fetching market snapshot (spot Sina): {e}")
        
    # 3. Fallback to Basic List (Code & Name only)
    try:
        df = ak.stock_info_a_code_name()
        df = df.rename(columns={"code": "代码", "name": "名称"})
        df['代码'] = df['代码'].astype(str)
        
        if HAS_PYPINYIN:
            def get_pinyin_abbr(name):
                try:
                    return "".join([w[0] for w in lazy_pinyin(name)]).upper()
                except:
                    return ""
            df['pinyin'] = df['名称'].apply(get_pinyin_abbr)
        else:
            df['pinyin'] = ""
            
        return df
    except Exception as e:
        print(f"Error fetching market snapshot (fallback): {e}")
        
    return pd.DataFrame()

@st.cache_data(ttl=3600*24)
def get_stock_sector(code: str) -> str:
    """Fetch stock sector."""
    try:
        df = ak.stock_individual_info_em(symbol=code)
        sector_row = df[df['item'] == '行业']
        if not sector_row.empty:
            return sector_row.iloc[0]['value']
        return "未知"
    except:
        return "未知"

@st.cache_data(ttl=60)
def get_realtime_price(code: str) -> Dict[str, Any]:
    """Fetch realtime price for a single stock (fallback)."""
    # Debug: Check if fallback is triggered
    print(f"[DEBUG] Fetching realtime price for {code}...")
    try:
        # Fallback to daily history (latest) if spot is down
        df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
        if not df.empty:
            last_row = df.iloc[-1]
            # Try to calculate change
            prev_close = df.iloc[-2]['收盘'] if len(df) > 1 else last_row['开盘']
            change_pct = ((last_row['收盘'] - prev_close) / prev_close) * 100
            
            return {
                "latest": last_row['收盘'],
                "change": round(change_pct, 2),
                "pe": "-",  # History doesn't have PE
                "pb": "-"
            }
        
        # 2nd Fallback: Try stock_zh_a_daily (if standard hist fails)
        prefix = "sh" if code.startswith("6") else "sz" if code.startswith(("0", "3")) else ""
        if prefix:
            df = ak.stock_zh_a_daily(symbol=f"{prefix}{code}")
            if not df.empty:
                last_row = df.iloc[-1]
                prev_close = df.iloc[-2]['close'] if len(df) > 1 else last_row['open']
                change_pct = ((last_row['close'] - prev_close) / prev_close) * 100
                
                return {
                    "latest": last_row['close'],
                    "change": round(change_pct, 2),
                    "pe": "-", 
                    "pb": "-"
                }

    except:
        pass
    return {}

@st.cache_data(ttl=3600*24)
def get_stock_financials(code: str) -> Dict[str, float]:
    """Fetch financial indicators like ROE, Gross Margin."""
    # Use Cache Manager for persistent storage
    cm = get_cache_manager()
    return cm.get_financials(code)

@st.cache_data(ttl=3600)
def get_stock_history(code: str, period="daily") -> pd.DataFrame:
    """Fetch historical data for charts and indicators."""
    # 1. Try Standard History (Fastest/Best)
    try:
        df = ak.stock_zh_a_hist(symbol=code, period=period, adjust="qfq")
        if not df.empty:
            df = df.rename(columns={
                "日期": "date", "开盘": "open", "收盘": "close", 
                "最高": "high", "最低": "low", "成交量": "volume"
            })
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            return df
    except Exception as e:
        print(f"Error fetching history (standard) for {code}: {e}")
        
    # 2. Fallback for Daily: stock_zh_a_daily (Slower but robust)
    if period == "daily":
        try:
            # Need to format code for this API: 'sh600519' or 'sz000001'
            prefix = "sh" if code.startswith("6") else "sz" if code.startswith(("0", "3")) else ""
            if prefix:
                df = ak.stock_zh_a_daily(symbol=f"{prefix}{code}")
                if not df.empty:
                    df = df.rename(columns={
                        "date": "date", "open": "open", "close": "close", 
                        "high": "high", "low": "low", "volume": "volume"
                    })
                    df['date'] = pd.to_datetime(df['date'])
                    df.set_index('date', inplace=True)
                    # This API returns raw volume, ensure numeric
                    for col in ['open', 'close', 'high', 'low', 'volume']:
                        df[col] = pd.to_numeric(df[col], errors='coerce')
                    return df
        except Exception as e:
            print(f"Error fetching history (fallback) for {code}: {e}")
            
    return pd.DataFrame()

def load_stock_pool() -> List[Dict[str, Any]]:
    """
    Load stock pool. Each item: {'code': str, 'name': str, 'note': str, 'added_at': str}
    """
    ensure_data_dir()
    if not os.path.exists(STOCK_POOL_FILE):
        return []
    try:
        with open(STOCK_POOL_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading stock pool: {e}")
        return []

def save_stock_pool(pool: List[Dict[str, Any]]):
    ensure_data_dir()
    try:
        with open(STOCK_POOL_FILE, 'w', encoding='utf-8') as f:
            json.dump(pool, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.error(f"Error saving stock pool: {e}")

def add_to_pool(code: str, name: str):
    pool = load_stock_pool()
    if any(s['code'] == code for s in pool):
        return False, f"{name} ({code}) 已经在选股池中。"
    
    pool.append({
        'code': code, 
        'name': name, 
        'note': '', 
        'added_at': datetime.now().isoformat()
    })
    save_stock_pool(pool)
    return True, f"已添加 {name} ({code}) 到选股池。"

def remove_from_pool(code: str):
    pool = load_stock_pool()
    pool = [s for s in pool if s['code'] != code]
    save_stock_pool(pool)
    return True, f"已移除 {code}。"

def update_stock_note(code: str, note_data: Any, pool_type: str = 'picking'):
    if pool_type == 'picking':
        pool = load_stock_pool()
        save_func = save_stock_pool
    elif pool_type == 'watching':
        pool = load_watching_pool()
        save_func = save_watching_pool
    elif pool_type == 'trading':
        pool = load_trading_pool()
        save_func = save_trading_pool
    else:
        return

    for s in pool:
        if s['code'] == code:
            if isinstance(s.get('note'), str):
                s['note'] = {
                    "content": s['note'],
                    "updated_at": datetime.now().isoformat()
                }
            
            if isinstance(note_data, dict):
                # Update existing dict
                if isinstance(s.get('note'), dict):
                    # Remove 'images' if it exists in input or existing data to clean up
                    note_data.pop('images', None)
                    s['note'].pop('images', None)
                    s['note'].update(note_data)
                else:
                    note_data.pop('images', None)
                    s['note'] = note_data
                s['note']['updated_at'] = datetime.now().isoformat()
            else:
                # Fallback for string input (just content)
                if isinstance(s.get('note'), dict):
                    s['note']['content'] = str(note_data)
                    s['note'].pop('images', None)
                    s['note']['updated_at'] = datetime.now().isoformat()
                else:
                    s['note'] = {
                        "content": str(note_data),
                        "updated_at": datetime.now().isoformat()
                    }
            break
    save_func(pool)

def update_stock_tags(code: str, tags: List[str], pool_type: str = 'picking'):
    if pool_type == 'picking':
        pool = load_stock_pool()
        save_func = save_stock_pool
    elif pool_type == 'watching':
        pool = load_watching_pool()
        save_func = save_watching_pool
    elif pool_type == 'trading':
        pool = load_trading_pool()
        save_func = save_trading_pool
    else:
        return

    for s in pool:
        if s['code'] == code:
            s['tags'] = tags
            break
    save_func(pool)

# --- Watching Pool Functions ---

def load_watching_pool() -> List[Dict[str, Any]]:
    ensure_data_dir()
    if not os.path.exists(WATCHING_POOL_FILE):
        return []
    try:
        with open(WATCHING_POOL_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return []

def save_watching_pool(pool: List[Dict[str, Any]]):
    ensure_data_dir()
    try:
        with open(WATCHING_POOL_FILE, 'w', encoding='utf-8') as f:
            json.dump(pool, f, ensure_ascii=False, indent=2)
    except Exception as e:
        pass

def move_to_watching_pool(code: str):
    # 1. Get stock info from picking pool
    picking_pool = load_stock_pool()
    stock = next((s for s in picking_pool if s['code'] == code), None)
    
    if not stock:
        return False, "股票不在选股池中"
    
    # 2. Add to watching pool
    watching_pool = load_watching_pool()
    if not any(s['code'] == code for s in watching_pool):
        watching_pool.append(stock)
        save_watching_pool(watching_pool)
    
    # 3. Remove from picking pool
    remove_from_pool(code)
    
    return True, f"已将 {stock['name']} 移入观察池"

def get_pool_financials(pool: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Fetch financial data for all stocks in the pool.
    """
    cm = get_cache_manager()
    data = []
    
    for stock in pool:
        code = stock['code']
        # This will use cache or fetch if missing
        fin = cm.get_financials(code) 
        fin['code'] = code
        data.append(fin)
        
    if not data:
        return pd.DataFrame()
        
    return pd.DataFrame(data)

def remove_from_watching_pool(code: str):
    pool = load_watching_pool()
    pool = [s for s in pool if s['code'] != code]
    save_watching_pool(pool)
    return True, f"已移除 {code}。"

# --- Trading Pool Functions ---

def load_trading_pool() -> List[Dict[str, Any]]:
    ensure_data_dir()
    if not os.path.exists(TRADING_POOL_FILE):
        return []
    try:
        with open(TRADING_POOL_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return []

def save_trading_pool(pool: List[Dict[str, Any]]):
    ensure_data_dir()
    try:
        with open(TRADING_POOL_FILE, 'w', encoding='utf-8') as f:
            json.dump(pool, f, ensure_ascii=False, indent=2)
    except Exception as e:
        pass

def move_to_trading_pool(code: str):
    # Try from Watching Pool first
    watching_pool = load_watching_pool()
    stock = next((s for s in watching_pool if s['code'] == code), None)
    from_pool = 'watching'
    
    if not stock:
        # Try from Picking Pool
        picking_pool = load_stock_pool()
        stock = next((s for s in picking_pool if s['code'] == code), None)
        from_pool = 'picking'
        
    if not stock:
        return False, "股票不在观察池或选股池中"
    
    # Add to Trading Pool
    trading_pool = load_trading_pool()
    if not any(s['code'] == code for s in trading_pool):
        # Initialize holding data if needed?
        # For now just copy the basic info + note + tags
        stock['added_to_trading_at'] = datetime.now().isoformat()
        trading_pool.append(stock)
        save_trading_pool(trading_pool)
    
    # Remove from source pool
    if from_pool == 'watching':
        remove_from_watching_pool(code)
    else:
        remove_from_pool(code)
        
    return True, f"已将 {stock['name']} 移入交易池"

def remove_from_trading_pool(code: str):
    pool = load_trading_pool()
    pool = [s for s in pool if s['code'] != code]
    save_trading_pool(pool)
    return True, f"已移除 {code}。"

def move_from_trading_to_watching(code: str):
    trading_pool = load_trading_pool()
    stock = next((s for s in trading_pool if s['code'] == code), None)
    
    if not stock:
        return False, "股票不在交易池中"
        
    watching_pool = load_watching_pool()
    if not any(s['code'] == code for s in watching_pool):
        watching_pool.append(stock)
        save_watching_pool(watching_pool)
        
    remove_from_trading_pool(code)
    return True, f"已将 {stock['name']} 移回观察池"

def add_transaction(code: str, trans_type: str, price: float, volume: int, plan: Optional[Dict[str, float]] = None):
    """
    Record a transaction and update holdings.
    trans_type: 'buy' or 'sell'
    plan: Optional dict with keys 'stop_loss', 'take_profit', 'expected_buy'
    """
    pool = load_trading_pool()
    stock = next((s for s in pool if s['code'] == code), None)
    
    if not stock:
        return False, "股票不在交易池中"
    
    # Initialize fields if missing
    if 'transactions' not in stock:
        stock['transactions'] = []
    if 'holdings' not in stock:
        stock['holdings'] = {'volume': 0, 'avg_cost': 0.0, 'total_cost': 0.0}
    
    # Record Transaction
    timestamp = datetime.now().isoformat()
    transaction = {
        'type': trans_type,
        'price': price,
        'volume': volume,
        'time': timestamp
    }
    if plan:
        transaction['plan'] = plan
        
    stock['transactions'].append(transaction)
    
    # Update Holdings
    current_vol = stock['holdings'].get('volume', 0)
    current_cost = stock['holdings'].get('total_cost', 0.0)
    
    if trans_type == 'buy':
        new_vol = current_vol + volume
        new_total_cost = current_cost + (price * volume)
        new_avg_cost = new_total_cost / new_vol if new_vol > 0 else 0.0
        
        stock['holdings']['volume'] = new_vol
        stock['holdings']['total_cost'] = new_total_cost
        stock['holdings']['avg_cost'] = new_avg_cost
        
        # Update active plan if provided
        if plan:
            stock['holdings']['plan'] = plan
        
    elif trans_type == 'sell':
        if volume > current_vol:
            return False, "卖出数量超过持仓量"
        
        # FIFO or Weighted Average? 
        # Weighted Average: Cost basis reduces proportionally.
        # Realized PnL = (Sell Price - Avg Cost) * Sell Volume
        avg_cost = stock['holdings'].get('avg_cost', 0.0)
        
        new_vol = current_vol - volume
        # Cost reduces proportionally to volume reduction
        new_total_cost = current_cost * (new_vol / current_vol) if current_vol > 0 else 0.0
        
        stock['holdings']['volume'] = new_vol
        stock['holdings']['total_cost'] = new_total_cost
        # Avg cost remains same after sell in Weighted Average method, unless volume becomes 0
        stock['holdings']['avg_cost'] = avg_cost if new_vol > 0 else 0.0

    save_trading_pool(pool)
    return True, "交易已记录"
