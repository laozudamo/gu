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

@st.cache_data(ttl=60)  # Cache for 60 seconds
def get_market_snapshot() -> pd.DataFrame:
    """
    Fetch real-time data for all A-shares.
    Returns DataFrame with columns: 
    ['序号', '代码', '名称', '最新价', '涨跌幅', '涨跌额', '成交量', '成交额', 
     '振幅', '最高', '最低', '今开', '昨收', '量比', '换手率', '市盈率-动态', '市净率', '总市值', ...]
    """
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
        # Don't show error to user immediately to avoid flicker, just log or return empty
        print(f"Error fetching market snapshot: {e}")
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

@st.cache_data(ttl=3600*24)
def get_stock_financials(code: str) -> Dict[str, float]:
    """Fetch financial indicators like ROE."""
    try:
        df = ak.stock_financial_analysis_indicator(symbol=code)
        if not df.empty:
            df = df.sort_values('日期', ascending=False)
            latest = df.iloc[0]
            roe_col = [c for c in df.columns if '净资产收益率' in c]
            roe = latest[roe_col[0]] if roe_col else 0.0
            return {"ROE": roe}
    except:
        pass
    return {"ROE": 0.0}

@st.cache_data(ttl=3600)
def get_stock_history(code: str, period="daily") -> pd.DataFrame:
    """Fetch historical data for charts and indicators."""
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
        print(f"Error fetching history for {code}: {e}")
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

def update_stock_note(code: str, note: str):
    pool = load_stock_pool()
    for s in pool:
        if s['code'] == code:
            s['note'] = note
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
