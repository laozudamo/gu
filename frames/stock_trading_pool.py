import streamlit as st
from utils.stock_data import load_trading_pool, get_market_snapshot
from frames.components import render_stock_table_common

def stock_trading_pool():
    
    pool = load_trading_pool()
    
    with st.spinner("更新行情数据..."):
        market_data = get_market_snapshot()
        
    render_stock_table_common(pool, market_data, pool_type='trading')
