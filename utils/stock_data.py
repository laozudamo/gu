import json
import os
from typing import List, Dict, Optional, Tuple, Any
import akshare as ak
import pandas as pd
import streamlit as st
import numpy as np
from datetime import datetime

DATA_DIR = "data"
STOCK_POOL_FILE = os.path.join(DATA_DIR, "stock_pool.json")
WATCHING_POOL_FILE = os.path.join(DATA_DIR, "watching_pool.json")

# Try to import pypinyin
try:
    from pypinyin import lazy_pinyin
    HAS_PYPINYIN = True
except ImportError:
    HAS_PYPINYIN = False

def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

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

@st.cache_data(ttl=60)  # Cache for 60 seconds
def get_market_snapshot() -> pd.DataFrame:
    """
    Fetch real-time data for all A-shares.
    Tries stock_zh_a_spot_em first, falls back to stock_info_a_code_name.
    """
    # 1. Try Spot Data (Full Info)
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
        print(f"Error fetching market snapshot (spot): {e}")
        
    # 2. Fallback to Basic List (Code & Name only)
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
    result = {"ROE": 0.0, "GrossMargin": 0.0, "NetMargin": 0.0}
    
    # Method 1: Financial Analysis Indicator
    try:
        df = ak.stock_financial_analysis_indicator(symbol=code)
        if not df.empty:
            df = df.sort_values('日期', ascending=False)
            latest = df.iloc[0]
            
            def get_val(col_keyword):
                cols = [c for c in df.columns if col_keyword in c]
                return float(latest[cols[0]]) if cols else 0.0
                
            result["ROE"] = get_val('净资产收益率')
            result["GrossMargin"] = get_val('销售毛利率')
            result["NetMargin"] = get_val('销售净利率')
            return result
    except Exception as e:
        print(f"Financial analysis failed for {code}: {e}")

    # Method 2: Fallback (e.g. Abstract or just return 0s to avoid crash)
    # We could try other APIs here if needed
    
    return result

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

def update_stock_note(code: str, note_data: Any):
    pool = load_stock_pool()
    for s in pool:
        if s['code'] == code:
            if isinstance(s.get('note'), str):
                s['note'] = {
                    "content": s['note'],
                    # "images": [], # Removed
                    "updated_at": datetime.now().isoformat()
                }
            
            if isinstance(note_data, dict):
                # Update existing dict
                if isinstance(s['note'], dict):
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
                if isinstance(s['note'], dict):
                    s['note']['content'] = str(note_data)
                    s['note'].pop('images', None)
                    s['note']['updated_at'] = datetime.now().isoformat()
                else:
                    s['note'] = {
                        "content": str(note_data),
                        # "images": [], # Removed
                        "updated_at": datetime.now().isoformat()
                    }
            break
    save_stock_pool(pool)

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
